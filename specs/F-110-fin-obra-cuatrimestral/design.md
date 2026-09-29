<!-- specs/F-110-fin-obra-cuatrimestral/design.md -->
# F-110 · Diseno tecnico

`sql/` = `etl_sigrid/infrastructure/postgres/sql/`. Todo medido el 2026-09-25 en
solo lectura sobre el build del 25 (diccionario v32); consultas en
`progress/spec_F-110.md` §Consultas. Cambio **acotado a `retenciones.fin_obra`**:
ni objetos nuevos ni objetos que desaparezcan. **APROBADA por el humano el
2026-09-25** (§Decisiones del humano).

## Medidas que fijan el diseno

**Las cuatrimestrales.** 131 fichas de obra tienen alguna version master y **117
alguna `Cuatrimestral`** (404 versiones por ambito), las 117 en `raw.obr` y 81 de
ellas ya con inicio de garantia; 805 de las 922 no tienen ninguna. En las 117 la
de mayor numero = la de mayor fecha efectiva = la de mayor fecha de creacion (0
discrepancias). La marca de Sigrid (`stg.version_master_vigente`, `conext` 15)
coincide en 107; en 7 apunta a una version posterior que no es cuatrimestral (5
«Sin clasificar», 2 «Cierre mensual») y 3 no tienen marca.

**El ultimo mes y la cola a cero.** El coste acaba despues que la venta en 20
obras y nunca al reves; rango 2019-11 a 2028-03. En **15 de 117 obras** la
version arrastra meses finales con `importe_mes = 0` (porcentaje congelado): la
ultima fila queda 1 a 10 meses despues del ultimo mes planificado. Solo pesan en
**7**, las que toman fecha por cuatrimestral y tienen retencion viva (2.006.420,81
€): con la regla aprobada su fin queda ANTES que tomando la ultima fila, en
`1-0678` 5 meses (170.019,37 €), `1-0686` 3 (1.058.925,82 €), `1-0696` 2
(676.656,98 €) y `1-0588`, `1-0619`, `1-0697`, `1-0702` 1 mes (100.818,64 €).
Ninguna cambia de estado por ello (las cinco en curso vencen en 2027-2028 con
cualquiera de las dos; las dos terminadas, vencidas con las dos). Las otras 8
tienen inicio de garantia (`1-0693`, la de 10 meses, entre ellas) o no tienen
retencion viva.

**Efecto sobre la retencion viva de los efectos** (8.247.267,15 € con obra, 179
obras; la misma base que la ficha de F-095):

| Fuente | Antes (F-095) | Despues (F-110) |
|---|---|---|
| INICIO_GARANTIA | 97 obras · 5.026.655,18 € | 97 · 5.026.655,18 € (igual) |
| ULTIMO_CIERRE_MAS_1_MES | 67 · 3.120.260,42 € | — |
| ULTIMO_CUATRIMESTRAL_MAS_1_MES | — | **32 · 2.960.583,38 €** |
| Sin fecha | 15 · 100.351,55 € | **50 · 260.028,59 €** |

De las 67 del ultimo cierre, 32 toman fecha por cuatrimestral y **35 se quedan
sin fecha (159.677,04 €)**: 29 terminadas (111.389,14 €, con su ultimo cierre
entre 2015 y 2022, casi todas antes de que hubiera cuatrimestrales), 4 en curso
sin cuatrimestral (`1-0723`, `1-0721`, `1-0720`, `1-0719`: 45.577,49 €) y 2 en
estado 17 (2.710,41 €). `terminada_sin_fin_obra` sobre lo vivo: 8 obras /
42.647,96 € -> **37 / 154.037,10 €**. En las 922 obras: 198 / 150 / 574 ->
198 / **36** / **688** (34 del cierre y 2 que no tenian fecha).

**Como se mueve la fecha en las 32:** 15 obras EN CURSO (2.724.514,73 €) pasan a
un fin de obra **posterior**, +1 a +19 meses (media +6,6): es el caso que motivo
la decision. 16 pasan a uno **anterior** (211.549,15 €): 14 terminadas (-1 a
-20 meses, media -5,3) y 2 en curso (`1-0692`, `31-0606`), porque su ultima
cuatrimestral acaba antes que su ultimo cierre (la obra se alargo sobre el plan;
18 obras de las 36 estan asi). 1 igual.

**Estados de vencimiento, hoy (2026-09-25):**

| Cambio | Efectos vivos | Saldo contable (`v_retencion_contable_obra`) |
|---|---|---|
| VENCIDA -> PENDIENTE | **0** | **0** |
| PENDIENTE -> VENCIDA | 1 obra (`1-0692`) · 43.476,54 € | 1 obra · 3 filas · 43.476,54 € |
| VENCIDA -> SIN_FIN_OBRA | 31 · 114.099,55 € | 102 obras · 770 filas · 643.734,57 € |
| PENDIENTE -> SIN_FIN_OBRA | 4 · 45.577,49 € | 4 obras · 17 filas · 45.577,49 € |
| SIN_FIN_OBRA -> VENCIDA | 0 | 1 obra · 1 fila · -12.571,28 € |

**Ningun vencimiento pasa de VENCIDA a PENDIENTE hoy**: en las obras en curso el
respaldo viejo (agosto de 2026 + 1 + 12 meses = septiembre de 2027) ya caia en el
futuro; lo que cambia es la FECHA (medio ano mas tarde de media). Saldo contable
por fuente (filas con obra, 10.518.015,66 €): antes 178 / 6.496.375,95 ·
140 / 3.819.683,33 · 81 / 201.956,38; despues 178 / 6.496.375,95 ·
**35 / 3.117.799,99 · 186 / 903.839,72**.

**Coste.** El cruce version -> `stg.plan_mensual` de las 117 obras (1,23 M filas
de 30 M) tardo 11 s por el MCP y ~36 s la medicion completa por una conexion de
solo lectura: se estima **+15-40 s** al sub-paso `fin_obra` (hoy el paso entero
tarda 65 s).

## Decisiones del humano (2026-09-25)

**D1 · Version = la ultima `Cuatrimestral` por numero** en
`mart.master_versiones_tipadas`. Descartadas: incluir Planif Inicial/ABC (+3
obras con fecha: `1-0723`, `1-0630`, `1-0719`, +29.184,48 €) y la marca de Sigrid
(en 7 obras es un cierre mensual o una version sin clasificar, 3 sin marca).

**D2 · «Ultimo mes planificado» = el ultimo mes del cuatrimestral con importe
planificado**, de coste o de venta; los meses finales a cero no cuentan. Ejemplo
literal del humano: «el cuatrimestral de junio 26 puede tener planificada la obra
hasta marzo 28; entonces el dia a partir del que contar las retenciones seria el
30 de abril». Efecto de la cola a cero, en §Medidas.

**D3 · «+ 1 mes» = ultimo dia del mes siguiente** (30-04-2028 en el ejemplo), la
convencion del respaldo de F-095: `(mes + INTERVAL '2 months' - INTERVAL '1
day')::DATE`.

**D4 · Se lee `mart.master_versiones_tipadas` (que version) y
`stg.plan_mensual` (que meses), con `depends_on` intacto (`["ingest_raw"]`).**
La tabla de 4.447 filas ya clasifica las versiones (F-078): leerla evita una
tercera copia del `CASE` de `tipo_master` y barrer ~12 M filas master. En
`run-all`, `build_stg` y `build_mart` van antes que `build_retenciones` (DFS
sobre la lista, R16): **el fin de obra sale de la MISMA noche**. Si `build_stg`
o `build_mart` fallan, `build_retenciones` corre con las tablas de la noche
anterior (ninguna se dropea fuera de su build y `execute_sql_file` corre cada
fichero en una transaccion). Patron de D3/D7 de F-095. Descartadas: solo `stg`
replicando el `CASE`, y declarar `build_mart` (un fallo de `stg` dejaria sin
construir TODO `retenciones`).

**D5 · `ultimo_cierre` SE QUEDA como dato INFORMATIVO** en `retenciones.fin_obra`,
con su regla de F-095 (CTE `cierres` sin cambio), y su ficha lo dice: ya no
interviene en el fin de obra. Se mantiene por tanto la lectura de
`cierre.fact_cierre_mensual`, de la noche anterior. **Consecuencia derivada que
escribe el spec-author (R14)**: la guarda de F-095 que abortaba con esa tabla
VACIA se retira —una columna informativa no debe tumbar el vencimiento—; se
conserva la de existencia, porque sin la tabla el SQL fallaria igual, pero con
peor mensaje. Si el humano prefiere conservar las dos, es cambiar una linea.

**D6 · Aceptado**: sin cuatrimestral, sin fecha (35 obras vivas / 159.677,04 € y
102 de saldo contable / 643.734,57 € pasan a SIN_FIN_OBRA; `1-0692` pasa a
VENCIDA, 43.476,54 €).

## Ficheros a crear

1. `tests/test_f110_fin_obra_cuatrimestral.py` — suite offline por requisito
   (texto del SQL sin comentarios `--`, YAML, cableado del step y orden
   topologico de `main.build_pipeline_steps`), al estilo de `test_f095_*`.

## Ficheros a modificar

- `sql/retenciones/05_fin_obra.sql` — cabecera reescrita (regla [H], D1-D6,
  ejemplo, medidas); guarda nueva (abajo); CTE `cierres` y columna
  `ultimo_cierre` **sin cambio**; nuevos CTE `cuatrimestral` y `plan`; en `base`,
  `version_cuatrimestral` y `ultimo_mes_planificado` justo detras de
  `ultimo_cierre`; en `fin`, los dos `CASE` nuevos; `COMMENT ON TABLE` al dia.
  `constantes`, `oc`, plazo, vencimiento e informativas, **sin tocar**.
- `sql/retenciones/06_views_contables.sql` — solo el comentario de la linea
  `SIN_FIN_OBRA` (R18). Ni una linea de SQL.
- `etl_sigrid/application/steps/build_retenciones_step.py` — docstring y
  comentario de `depends_on` (R17). Codigo, `SUB_PASOS`, `name`, `stage` y
  `depends_on`, iguales.
- `tests/test_f095_retenciones_contables.py` — los tests que fijan la regla vieja,
  reescritos a la nueva (R21; lista cerrada en `tasks.md` T3), y la entrada
  `fin_obra` del contrato `CONTRATO_SQL`.
- `config/diccionario/retenciones.yaml` — ficha `fin_obra` (descripcion con la
  regla y el ejemplo, cifras antes/despues, columnas `version_cuatrimestral` y
  `ultimo_mes_planificado`, `ultimo_cierre` rotulada INFORMATIVA, valores de
  `fuente_fin_obra`); ficha `v_retencion_contable_obra` (`fuente_fin_obra.valores`,
  texto de SIN_FIN_OBRA).
- `config/diccionario/00_global.yaml` — `version` +1 y linea de historia. **Si
  F-108 o F-109 suben antes la version, se toma la siguiente al fusionar.**
- `docs/ARCHITECTURE.md` — la vineta «La retencion de proveedor la manda la
  contabilidad»: fin de obra = garantia -> ultimo cuatrimestral + 1 mes, leidos
  de la misma noche; el ultimo cierre queda informativo y con una noche de desfase.
- `azure-apps/datamart_seg_anual.md` — fila de `retenciones.fin_obra` y parrafo de
  dependencias: lee ademas `mart.master_versiones_tipadas` y `stg.plan_mensual`;
  `cierre.fact_cierre_mensual` solo para la columna informativa, y ya no falla si
  esta vacia. Commit en `azure-apps`.

## Ficheros que NO se tocan

- `sql/retenciones/00`-`04`: movimientos, apuntes y saldo no cambian.
- `sql/mart/06_cp_tipologia.sql` y `sql/mart/02_build_fact.sql`: se LEE la
  tabla que construye el primero; la regla de `tipo_master` no se toca.
- `sql/stg/08_plan_mensual.sql`, `sql/stg/07_version_master_vigente.sql`,
  `sql/cierre/*`.
- `main.py`, `orchestrator.py`, `apply_grants_step.py`: la composicion ya pone
  `build_stg` y `build_mart` antes; se verifica con test (R16).
- `tests/test_f047_nocturna.py`: `depends_on == ["ingest_raw"]` sigue siendo cierto.
- `config/objetos_pendientes.yaml`: ningun objeto nuevo ni retirado.

## SQL de `05_fin_obra.sql` (capa `retenciones`, mismo numero de fichero)

Guarda, antes del `DROP` (R14), en el mismo `DO $$` que hoy, cuatro `RAISE
EXCEPTION 'fin_obra: ...'`: `to_regclass('mart.master_versiones_tipadas') IS
NULL` (con «lanza build-mart antes de build-retenciones»); `NOT EXISTS (... WHERE
tipo_master = 'Cuatrimestral')`; `NOT EXISTS (SELECT 1 FROM stg.plan_mensual
WHERE ambito_id IN (8, 11))`; y la de F-095 `to_regclass('cierre.fact_cierre_mensual')
IS NULL`, que se conserva. Se retira `IF NOT EXISTS (SELECT 1 FROM
cierre.fact_cierre_mensual)`.

```sql
cuatrimestral AS (   -- D1: la ultima por numero, en 8 u 11
    SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral
    FROM mart.master_versiones_tipadas v
    WHERE v.tipo_master = 'Cuatrimestral'
    GROUP BY v.obra_id
),
plan AS (            -- D2: ultimo mes del cuatrimestral con importe planificado
    SELECT c.obra_id, c.version_cuatrimestral,
           MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ultimo_mes_planificado
    FROM cuatrimestral c
    LEFT JOIN stg.plan_mensual pm
           ON pm.obra_id = c.obra_id
          AND pm.version = c.version_cuatrimestral
          AND pm.ambito_id IN (8, 11)
    GROUP BY c.obra_id, c.version_cuatrimestral
),
```

En `base`: `LEFT JOIN plan pl ON pl.obra_id = obr.ide` (solo `obra_id`, R3) y
`pl.version_cuatrimestral`, `pl.ultimo_mes_planificado`. En `fin`:
`CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia WHEN
b.ultimo_mes_planificado IS NOT NULL THEN (b.ultimo_mes_planificado + INTERVAL
'2 months' - INTERVAL '1 day')::DATE END AS fecha_fin_obra`, y su gemelo con
`'INICIO_GARANTIA'` / `'ULTIMO_CUATRIMESTRAL_MAS_1_MES'`, sin `ELSE`;
`b.ultimo_cierre` no aparece en `fin` (R10, R12). Columnas publicadas: las de hoy
mas `version_cuatrimestral, ultimo_mes_planificado` detras de `ultimo_cierre`. PK
`(obra_id)` sin cambio.

## Riesgos

**(a) Cuatrimestral vieja.** La ultima cuatrimestral puede acabar antes que la
obra (18 de 36 obras): el fin de obra ADELANTA respecto al cierre (`1-0692`, D6).
Es la regla decidida; la ficha lo dice y `ultimo_cierre` informativo lo deja ver.
**(b) Frescura de `stg.plan_mensual`** (F-025): una obra congelada lleva hasta 6
dias; congelar exige no tener actividad, y una cuatrimestral nueva es actividad.
**(c) Coste** +15-40 s de la nocturna sobre el Postgres compartido (creditos de
CPU); se mide en la verificacion. **(d) Orden sin `depends_on`**: si alguien
moviera `build_retenciones` delante de `build_mart`, leeria la tabla de la noche
anterior sin error; el test de R16 lo impide. **(e) `cierre` vacia** ya no para
el paso: `ultimo_cierre` saldria NULL en todas y la ficha lo avisa. **(f) Version
del diccionario** en carrera con F-108/F-109 (se resuelve al fusionar).

## Plan de verificacion (MANUAL, humano, en el entorno que autorice)

**Antes** (solo lectura): las consultas de `progress/spec_F-110.md` §Consultas
reproducen §Medidas. **Despues** de `python main.py build-retenciones` y
`python main.py apply-grants`: (1) `fin_obra` = 922 filas (= `raw.obr`) y
sub-paso `fin_obra` < 2 min en el log; (2) por fuente en las 922: ~198 / ~36 /
~688, y `ultimo_cierre` informado en ~304 obras como hoy; (3) sobre la viva de
los efectos, ~97 / 5,03 M, ~32 / 2,96 M y ~50 / 0,26 M; (4) `SELECT
estado_vencimiento, COUNT(*), SUM(saldo) FROM retenciones.v_retencion_contable_obra
GROUP BY 1` frente a §Medidas; (5) `1-0686`: `ultimo_mes_planificado` 2026-11-01,
fin 2026-12-31, vencimiento 2027-12-31 (su ultima fila es 2027-02: la cola a cero
no cuenta); (6) `check-declarados`, `check-unicidad`, `check-relaciones`,
`check-diccionario` verdes; `publicar-diccionario` y reinicio del MCP; (7) nueva
imagen desplegada (sin ella la nocturna sigue con la regla vieja).
