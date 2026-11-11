# Exploración · 0698 Montealto, v24 del máster de coste ausente del catálogo

- Fecha: 2026-11-10, consultas entre las 23:25 y las 23:44 UTC, antes de la
  nocturna. Los datos son los de la nocturna del 2026-11-10: `raw.obrparpre`
  ingerido a las 00:18 y `stg.presupuesto` construido a las 00:41.
- Tipo: investigación de solo lectura. No se ha tocado código ni datos.
- Incidencia: la reporta Control de Costes el 2026-11-10.
- Lecturas: Postgres de Azure con `filas_solo_lectura` y
  `_bootstrap_done = True`, más una lectura en Sigrid con
  `SigridApiClient.leer_sql` para confirmar el origen.

## 1. Síntoma reproducido

`obra_id` de Sigrid de la 0698: 2491958.

| Capa | v24 coste (ámbito 8) | v24 venta (ámbito 11) |
|---|---|---|
| `raw.obrfasamb` (cabecera) | fila: `tex` = 'CIERRE SEPTIEMBRE-26', `fec` = 20261013, `plafec` = 20250501, `planif` (entero) = 14 | fila: `tex` vacío, la misma fecha y el mismo `plafec` |
| `stg.presupuesto` | **776 líneas, 2.107.662,97 €** | 688 líneas, 1.808.375,61 € |
| `stg.plan_mensual` | **0 filas** | 4.218 filas, `version_fec_efectiva` = 2026-10-13 |
| `mart.master_versiones_tipadas` y su vista | **ausente** | presente, 'Cierre mensual' |

v22 y v23 aparecen en los dos ámbitos, con 4.487 filas de coste en
`plan_mensual` cada una. Se reproduce lo que describe Control de Costes: el
catálogo de coste salta de la v23 (CIERRE AGOSTO-26) a nada.

**La fecha efectiva no es el problema.**
`stg.fn_master_fecha_efectiva('CIERRE SEPTIEMBRE-26', 'Versión 24 (13/10/2026)', DATE '2026-10-13')`
devuelve 2026-10-13, la misma que la v24 de venta.

## 2. Causa raíz

Ninguna de las 776 líneas de la v24 de coste tiene planificación temporal: la
columna `obrparpre.planif`, el texto `pct|pct|...` que reparte la partida en
el tiempo, viene **a NULL en todas**.

| obra 0698 | `planif` informado | `planif` NULL |
|---|---|---|
| coste v23 | 751 | 52 |
| **coste v24** | **0** | **776** |
| venta v23 | 676 | 12 |
| venta v24 | 676 | 12 |

**Está así en el propio Sigrid, no es un fallo de ingesta.** Lectura directa
en `dbo.obrparpre` con `obride = 2491958`, `amb = 8` y `fas = 24`: 776 filas,
todas con `planif` NULL (`truncated = False`). El ámbito 9 también está a
NULL, en la v23 y en la v24. Los importes sí están bien en Sigrid, como dice
Control de Costes, pero la v24 de coste no tiene reparto mensual. Dos indicios
de que la versión se generó de otra forma: tiene 27 líneas menos que la v23
(776 frente a 803) y su cabecera es idéntica a la de las anteriores (`planif`
= 14, el mismo `plafec`). Es una hipótesis que hay que confirmar con quien
creó la versión.

Dónde cae la versión:

1. **`etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql:224-225`**,
   en la CTE `master_planif` (rama A, máster):
   ```sql
   AND op.planif IS NOT NULL
   AND length(trim(op.planif)) >= 1
   ```
   Las 776 líneas se descartan aquí y la versión no deja ninguna fila en
   `stg.plan_mensual`. El filtro es razonable para lo que hace ese fichero:
   sin `planif` no hay meses que explotar.
2. **`etl_sigrid/infrastructure/postgres/sql/mart/06_cp_tipologia.sql:117-143`**:
   `mart.master_versiones_tipadas` construye el catálogo con un
   `SELECT DISTINCT` **sobre `stg.plan_mensual`**
   (`WHERE ambito_id IN (8, 11) AND version_fec_efectiva IS NOT NULL`). Una
   versión sin filas en `plan_mensual` no existe para el catálogo, y
   `mart.v_master_versiones_tipadas` (líneas 424-434) solo envuelve esa tabla.

El defecto de fondo es que **el catálogo de versiones se deduce de la tabla de
reparto mensual, no de las cabeceras de versión**. Por eso hereda todos sus
filtros. Hay un segundo filtro con el mismo efecto, en
`08_plan_mensual.sql:217` y `:226`: la cabecera sin `plafec`, el ancla del
mes 1, también saca la versión del catálogo (ver el punto 3).

`mart.fact_seguimiento_mensual` monta su propio catálogo de la misma forma, en
`sql/mart/02_build_fact.sql:55-68` (`versiones_master`, sobre
`stg.plan_mensual`). Las dos copias se comportan igual.

## 3. ¿Caso aislado o sistémico?

**Es sistémico, y la v24 de la 0698 no es la única de este año.**

Consulta: el universo son las versiones con líneas en `stg.presupuesto` de los
ámbitos 8 y 11, cruzadas con `raw.obrfasamb` y con `raw.obrparpre`, para
comprobar si existen en `mart.master_versiones_tipadas`:

```sql
WITH v AS (
  SELECT pp.obra_id, pp.ambito_id, pp.fase_num, count(*) n_lineas, sum(pp.importe) importe,
         count(*) FILTER (WHERE op.planif IS NOT NULL AND length(trim(op.planif))>=1) n_planif
  FROM stg.presupuesto pp JOIN raw.obrparpre op ON op.ide=pp.presupuesto_id
  WHERE pp.ambito_id IN (8,11) GROUP BY 1,2,3
), c AS (
  SELECT v.*, fa.plafec, fa.fec, stg.fn_sigrid_date_to_date(fa.fec) fec_date,
         EXISTS (SELECT 1 FROM mart.master_versiones_tipadas t
                 WHERE t.obra_id=v.obra_id AND t.ambito_id=v.ambito_id AND t.version=v.fase_num) en_catalogo
  FROM v LEFT JOIN raw.obrfasamb fa ON fa.obride=v.obra_id AND fa.amb=v.ambito_id AND fa.fas=v.fase_num
)
SELECT ambito_id,
  CASE WHEN en_catalogo THEN '0 en catalogo'
       WHEN plafec IS NULL AND fec IS NULL THEN '1 sin cabecera obrfasamb'
       WHEN plafec IS NULL OR plafec<=0 THEN '2 plafec vacio'
       WHEN n_planif=0 THEN '3 ninguna linea con planif'
       WHEN fec_date IS NULL THEN '4 fec_efectiva nula'
       ELSE '5 otro' END motivo,
  count(*) versiones, count(DISTINCT obra_id) obras, round(sum(importe)::numeric,2) importe
FROM c GROUP BY 1,2 ORDER BY 1,2;
```

| Ámbito | Motivo | Versiones | Obras |
|---|---|---|---|
| 8 | en catálogo | 2.266 | 132 |
| 8 | **ninguna línea con `planif`** (el caso de la 0698) | **29** | 16 |
| 8 | cabecera sin `plafec` | 927 | 234 |
| 8 | sin cabecera en `obrfasamb` | 2 | 2 |
| 8 | otro | 3 | 1 |
| 11 | en catálogo | 2.260 | 132 |
| 11 | **ninguna línea con `planif`** | **20** | 10 |
| 11 | cabecera sin `plafec` | 927 | 222 |
| 11 | otro | 3 | 1 |

En ningún caso el motivo es la fecha efectiva nula: el motivo 4 sale con 0
versiones.

### 3a. Las 49 versiones sin ningún `planif`: el mismo mecanismo que la 0698

Afectan a 21 obras. Las de obras VIVAS (criterio `R-OBRA-ACTIVA`) son estas:

| Obra | Ámbito | Versión | Fecha | Texto |
|---|---|---|---|---|
| **0698** | 8 | 24 | 13/10/2026 | CIERRE SEPTIEMBRE-26 |
| **0722** | 8 y 11 | 7 | 13/10/2026 | CIERRE SEPTIEMBRE-26 |
| **0705** | 8 | 18 | 05/08/2026 | CIERRE JULIO-26 |
| **0705** | 8 | 17 | 15/07/2026 | CIERRE JUNIO-26 |
| **0693** | 11 | 20 | 15/01/2026 | CIERRE DICIEMBRE-25 |
| 0693 | 11 | 17, 18 y 19 | nov.-dic. 2025 | CIERRE OCTUBRE / NOVIEMBRE-25 |
| 0676-B | 11 | 9 y 10 | ago.-sep. 2025 | CIERRE JULIO / AGOSTO-25 |

Las otras 15 obras están cerradas (`estado_id` 25), con versiones de 2019 a
2025.

**Contradice que la 0698 sea la única de este año.** Solo entre las obras
vivas y en 2026 hay otras cuatro versiones perdidas: la 0722 v7, en coste y en
venta, y del mismo día que la de la 0698; la 0705 v17 y v18 de coste, y la 0693
v20 de venta.

### 3b. Las versiones cuya cabecera no tiene `plafec`

Son 927 por ámbito. Una cabecera sin `plafec` o con `plafec = 0` no tiene ancla
temporal, y `08_plan_mensual.sql:217` la descarta. Unas 400 por ámbito son la
v0 y la v1 ('CIERRE INICIAL_ESTUDIO' y 'CIERRE INICIAL_OBRA'), que
`02_build_fact.sql:74-75` documenta como descartadas a propósito. El resto
(527 de coste y 543 de venta, en 79 obras) son versiones v2 o posteriores con
`obrfasamb.planif = 0`. En 2026 son 16 filas de la v2 en adelante:

- 0712 v2;
- 0718 v2 a v4: la 0718 no tiene ninguna versión en el catálogo;
- 0719 v2 a v4;
- 0722 v2 ('VENTA CONTRATO').

### 3c. Lo que no se pierde: el planificado vigente

**Ninguna de las 49 versiones del 3a puede ser vigente.** Sus textos dan
'Cierre mensual' (CIERRE ...) o 'Sin clasificar' (texto vacío, 'PRESUPUESTO
VENTA DEFINITIVO', etc.). Ninguno da 'Planif Inicial', 'ABC' ni
'Cuatrimestral', que son los tres tipos con los que `02_build_fact.sql:168` y
`06_cp_tipologia.sql:187` eligen la versión vigente. Por eso hoy **no cambia
ninguna cifra** de:

- `mart.fact_seguimiento_mensual`;
- `mart.master_vigente_anual`: la 0698 en 2026 tiene la v20 Cuatrimestral, que
  sigue siendo correcta;
- `mart.fact_cp_tipologia`;
- `retenciones.fin_obra`;
- `tesoreria.devengo_*`.

Lo que se pierde es la **visibilidad** en `v_master_versiones_tipadas`, que
según su ficha «explica por qué una obra tiene o no tiene plan vigente en un
mes». Si mañana una cuatrimestral llegara sin `planif`, desaparecería del
catálogo y **la anterior seguiría vigente en silencio**. Ese es el riesgo
latente.

### 3d. Un hallazgo aparte (no es el mecanismo de la 0698)

Las 3+3 versiones del motivo «otro» son de la obra `obra_id` 1562946, de 2020,
con 34 líneas y `planif` informado. Esa obra **no está en `stg.obras`**, así
que ningún tramo de F-019 la incluye y no deja filas en `plan_mensual`. Son
restos en `stg.presupuesto` de una obra fuera del censo. No afecta a nada vivo.

## 4. ¿Es un filtro intencionado?

**Ninguna feature lo decidió para el catálogo: el catálogo lo hereda.**

- `git blame`: las líneas 224-226 de `08_plan_mensual.sql` (`planif` no nulo y
  `plafec`) están en el commit inicial `ba18868` (2026-05-19). Ninguna spec ni
  `progress/history.md` las discute. Su sentido es local: no hay meses que
  explotar sin `planif`.
- El catálogo sobre `stg.plan_mensual` existe desde la primera vista de CP
  (`bf36af1`, 2026-05-25, «generales»). F-078 (2026-09-15) lo materializó
  **sin tocar la lógica**: el SQL viajó tal cual desde la vista, y
  `tests/test_f078_sql.py:263-295` fija esas cadenas, entre ellas
  `WHERE ambito_id IN (8, 11)` y la cascada del tipo.
- La ficha `config/diccionario/mart.yaml:1230-1233` declara el grano como
  «solo ámbitos 8 y 11, y solo versiones con fecha efectiva resuelta». **No
  dice que también queden fuera las versiones sin reparto mensual (sin
  `planif` o sin `plafec`).** Por eso Control de Costes sospechó de la fecha
  efectiva: la ficha le señalaba la condición equivocada.
- `R-VERSION-MASTER` (`00_global.yaml:1566`) y la pregunta P18
  (`00_global.yaml:2472`) asumen que el catálogo enumera todas las versiones
  de la obra. P18 («obras mal configuradas, sin planificado») sería
  justamente la pregunta que debería ver estos casos.

## 5. Opciones de solución

### Opción A · Catálogo desde las cabeceras de versión

En `sql/mart/06_cp_tipologia.sql`, sección 1, construir
`master_versiones_tipadas` desde `raw.obrfasamb` (ámbitos 8 y 11) con al menos
una línea en `stg.presupuesto`, en lugar de desde `stg.plan_mensual`:

- La fecha efectiva con `stg.fn_master_fecha_efectiva` y el mismo
  `COALESCE` del texto de venta al de coste que usa `08_plan_mensual.sql:194-210`.
- Una columna nueva `tiene_reparto` (o `filas_plan`) que diga si la versión
  tiene filas en `plan_mensual`.
- Hay que decidir qué hacer con `plafec = 0` (v0 y v1).
- Hay que tratar las cabeceras duplicadas de `obrfasamb`
  (`docs/referencia/05_caso_obrfasamb_version_duplicada.md`).

| | |
|---|---|
| Ficheros | `06_cp_tipologia.sql`; `tests/test_f078_sql.py` (comprueba el `FROM` y el `WHERE ambito_id IN (8, 11)` del cuerpo); `config/diccionario/mart.yaml`, fichas de `master_versiones_tipadas` y `v_master_versiones_tipadas` (grano y columna nueva); `azure-apps/datamart_seg_anual.md` si cambian las columnas o lo que se lee. |
| A favor | El catálogo pasa a ser completo y responde a P18. Además se calcula sobre unos pocos miles de cabeceras, no sobre 29,8 M de filas. |
| Riesgo | Arrastra a todo lo que lee el catálogo, si no se filtra por `tiene_reparto`: `master_vigente_anual` (y con ella `fact_cp_tipologia`), `retenciones/05_fin_obra.sql:156-173` y `tesoreria/07_devengo_pendiente.sql:215-221`. Con fin_obra hay una **regresión concreta**: si la última cuatrimestral no tiene reparto, `ultimo_mes_planificado` queda NULL y la obra pierde su fecha de fin. Además el catálogo de `fact_seguimiento_mensual` (`02_build_fact.sql:55-68`) dejaría de coincidir con este, salvo que se cambie también. |
| Tests | Mantener las cadenas de tipado de `test_f078`; uno que compruebe que el `FROM` es la cabecera; uno de fixture con una versión sin `planif` que sale en el catálogo con `tiene_reparto = FALSE`. En Azure: las 2.266 + 2.260 versiones de hoy se mantienen y aparecen las 49 del punto 3a. |

### Opción B · Catálogo completo con vigencia intacta (A, contenida)

Es la opción A, pero los tres consumidores filtran
`WHERE tiene_reparto`: `master_vigente_anual` en la misma sección 2 de
`06_cp_tipologia.sql`, `05_fin_obra.sql` y `07_devengo_pendiente.sql`. El
catálogo y su vista muestran todas las versiones, y todo lo que calcula
vigencias o cifras se comporta byte a byte como hoy.

| | |
|---|---|
| Ficheros | Los de A, más `05_fin_obra.sql`, `07_devengo_pendiente.sql` y sus tests (`test_f110_*` y los de F-140). |
| A favor | Arregla la visibilidad sin mover ninguna cifra. La regla de negocio queda explícita en el SQL: «una versión sin reparto no rige», en vez de un efecto lateral. |
| Riesgo | Bajo, pero hay que decidir con Negocio si una cuatrimestral sin reparto debe regir con planificado 0, que es la filosofía de `02_build_fact.sql:8-16`, o no regir, que es lo que pasa hoy. B congela lo de hoy. |
| Tests | Los de A, más uno que fije el filtro `tiene_reparto` en cada consumidor. En Azure: comparar la huella de `master_vigente_anual`, `fact_cp_tipologia`, `fin_obra` y `devengo_*` antes y después; tiene que ser idéntica. |

### Opción C · No tocar el catálogo: documentar y vigilar

- Corregir el grano en `mart.yaml:1230-1233` («solo versiones con reparto
  mensual: `planif` en alguna línea y `plafec` en la cabecera»).
- Añadir a `R-VERSION-MASTER` o a P18 dónde mirar las versiones excluidas.
- Opcional: un aviso no bloqueante que liste las versiones de obras vivas con
  líneas en `stg.presupuesto` y sin filas en `plan_mensual`.

| | |
|---|---|
| Ficheros | `config/diccionario/mart.yaml`, `00_global.yaml` y, si se añade el aviso, un SQL o comando de comprobación con su test. |
| A favor | Riesgo nulo sobre las cifras. Hace honesta la ficha, que hoy apunta a la fecha efectiva. |
| En contra | El catálogo sigue incompleto y el riesgo latente del punto 3c (una cuatrimestral sin `planif` que desaparece en silencio) solo queda vigilado, no resuelto. |

### Descartada · Filas «centinela» en `stg.plan_mensual`

Meter una fila sin importe por cada versión sin `planif` contaminaría la tabla
de 29,8 M de filas. Todas las sumas y `R-VERSION-MASTER` tendrían que
excluirla. Es un parche en la capa equivocada.

## 6. Recomendación

1. **Inmediato, sin código:** responder a Control de Costes que la v24 de
   coste de la 0698 **no tiene planificación temporal en Sigrid**: `planif`
   está vacío en las 776 líneas (verificado en el origen). Por eso no deja
   reparto mensual y el catálogo, que se construye desde ese reparto, no la
   ve. La fecha efectiva se resuelve bien. Al ser un 'Cierre mensual', no
   altera el planificado vigente (la v20 Cuatrimestral). Avisar de que no es
   la única: 0722 v7 (las dos), 0705 v17 y v18 y 0693 v20 están igual, y
   preguntar si esas versiones deberían tener planificación (es posible que
   se generasen sin copiar el reparto).
2. **Feature:** la **opción B**. Completa el catálogo con la columna
   `tiene_reparto`, mantiene byte a byte las vigencias y las cifras de hoy,
   corrige la ficha (lo de la opción C va incluido) y deja para Negocio la
   decisión de si una cuatrimestral sin reparto debe regir. Conviene que la
   misma feature decida si `02_build_fact.sql:55-68` pasa a leer el catálogo
   materializado, para no mantener dos catálogos iguales que pueden divergir.
3. **Aparte, menor:** las 6 versiones de la obra 1562946 (fuera de
   `stg.obras` y con restos en `stg.presupuesto`) merecen una nota en el
   backlog. No tienen que ver con esta incidencia.
