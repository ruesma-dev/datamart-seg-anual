# F-019 · T13 · Arreglo de los defectos 2 y 3 de la comparación de huellas

**Fecha:** 2026-08-16 · **Rama:** `feature/F-019-plan-mensual-por-tramos`
**Alcance:** los defectos **2** (`nombre_mes` dependiente del locale) y **3**
(`sum_fact_id`) del intento 2 de T13. El defecto **1** (tipos de `compras.*`)
es del humano y **no se toca aquí**: su arreglo es recrear el raw local.
**Commits:** `42e128d` (A), `65c52aa` (B).

---

## 1 · Qué cambió

### TAREA A — el nombre del mes sin locale

`to_char(fecha, 'TMMonth YYYY')` traduce con `lc_time` **del servidor**. En
Azure (`en_US.utf8`) devuelve «May 2026»; el texto libre de las fases de
Sigrid trae «Mayo 2026». Las vistas que agrupan por `nombre_mes` partían cada
grupo en dos: `cierre.v_pbi_planif_vs_real` daba 24.736 filas en local y
36.657 en Azure (bloque cerrado) con la misma tabla base.

**8 apariciones** sustituidas — dos más de las conocidas en el encargo, las de
`cierre/04_views_detalle.sql`, encontradas con `grep -rn "TMMonth" etl_sigrid/`:

| Fichero (bajo `etl_sigrid/infrastructure/postgres/sql/`) | Línea original | Qué era |
|---|---|---|
| `cierre/02_build_fact.sql` | 323 | `nombre_mes` del CTE `combinado` |
| `cierre/04_views_detalle.sql` | 420 | `nombre_mes` (detalle por subcategoría) |
| `cierre/04_views_detalle.sql` | 571 | `nombre_mes` (detalle por tipología) |
| `mart/02_build_fact.sql` | 271 | `nombre_mes`, rama COSTE PLANIFICADO |
| `mart/02_build_fact.sql` | 297 | `nombre_mes`, rama VENTA PLANIFICADA |
| `mart/04_view_periodificado.sql` | 167 | `nombre_mes` del periodificado |
| `mart/05_views_powerbi.sql` | 112 | `nombre_mes_solo` (**mes suelto, sin año**) |
| `mart/05_views_powerbi.sql` | 113 | `nombre_mes_anio` |

Todas pasan a la misma derivación determinista, **inline** (sin funciones
nuevas, para no crear dependencias entre capas) y con un comentario del porqué
en cada sitio:

```sql
(ARRAY['Enero','Febrero','Marzo','Abril','Mayo','Junio',
       'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])
      [EXTRACT(MONTH FROM <fecha>)::INT]
    || ' ' || EXTRACT(YEAR FROM <fecha>)::INT AS nombre_mes
```

Decisiones y por qué:

- **Texto idéntico al anterior.** `TM` ya suprime el relleno de espacios de
  `Month` (PostgreSQL no rellena en modo localizado), así que «Mayo 2026» era
  y sigue siendo la salida exacta, con mayúscula inicial y sin padding.
- **Sin cast a VARCHAR.** El resultado es `text`, que es justo lo que devolvía
  `to_char`. Castear habría cambiado el tipo expuesto de las vistas
  (`text` → `character varying`) y eso es un FALLO del bloque `estructura` de
  la huella. Los `INSERT` a columnas `VARCHAR(48)` (`mart.fact_*`,
  `cierre.fact_*`) siguen funcionando por conversión implícita.
- **`NULL` se comporta igual.** Con `anio_mes` nulo, `EXTRACT` da `NULL`, el
  subíndice nulo da `NULL` y la concatenación da `NULL`, exactamente como
  `to_char(NULL, ...)`.
- **`nombre_mes_solo` sigue sin año** y `nombre_mes_anio` sigue con él: son dos
  columnas distintas de `mart.v_pbi_dim_fecha` y hay un test que lo fija.

### TAREA B — la huella no suma claves sustitutas

`etl_sigrid/infrastructure/postgres/fingerprint.py`:

- Constante nueva `COLUMNAS_SUSTITUTAS = frozenset({"fact_id", "fact_cat_id"})`
  con el comentario largo del porqué: son BIGSERIAL asignados por orden de
  inserción, los builds no llevan `ORDER BY`, y por tanto **la misma carga en
  dos máquinas reparte identificadores distintos**.
- Función nueva `columnas_a_sumar(columnas)`: numéricas menos sustitutas. Es
  el único punto donde se decide qué se agrega, y `construir_huella` la usa.
- Docstring del módulo ampliado con qué queda fuera de los agregados.

**Criterio elegido: lista explícita, no consulta al catálogo.** El criterio
«preferido» del encargo (detectar `nextval(...)` en el default de la columna
de origen) no es fiable aquí: la huella se toma sobre **vistas**, y rastrear
una columna de vista hasta la columna de tabla que la alimenta exige recorrer
`pg_rewrite`/`pg_depend` y falla en cuanto la columna es una expresión —y una
de ellas lo es: `mart.v_fact_periodificado` expone `NULL::BIGINT AS fact_id`
en una de sus ramas—. El encargo admite explícitamente la alternativa.

**Lo que NO se excluye, y es la mitad del valor del arreglo:** `obra_id`,
`partida_id`, `albaran_id`, `linea_id`, `proveedor_id`, `cliente_id`,
`contrato_id`, `entidad_id`, `estado_id`, `movimiento_id`, `ambito_id` son
claves **naturales** de Sigrid, iguales en las dos máquinas, y siguen
sumándose. Excluir por sufijo `_id` habría cegado la huella.

**La estructura no cambia:** `fact_id` y `fact_cat_id` siguen apareciendo en
el bloque `estructura` con su tipo. Si desaparecen de una vista o cambian de
tipo, sigue siendo FALLO.

Candidatas a entrar en la lista si algún día llegan a una vista de consumo
(hoy no llegan, verificado): `cierre_id`, `plan_id`, `regla_id`. Queda escrito
en el propio módulo.

---

## 2 · Fase RED (rigor `critico`)

### A · el locale

Los tests se escribieron y se ejecutaron **antes** de tocar un solo `.sql`.

```
$ python -m pytest tests/test_f019_t13_portabilidad.py -q
FFFFFFFFFFF.FF..FF                                                       [100%]
================================== FAILURES ===================================
_______ test_f019_t13_ningun_sql_deriva_el_nombre_del_mes_con_el_locale _______
[...]
>       assert culpables == [], (
            "el nombre del mes no puede depender de lc_time del servidor; "
            f"quedan máscaras TM en: {culpables}"
        )
E       AssertionError: el nombre del mes no puede depender de lc_time del servidor; quedan máscaras TM en: ['infrastructure\\postgres\\sql\\cierre\\02_build_fact.sql:323', 'infrastructure\\postgres\\sql\\cierre\\04_views_detalle.sql:420', 'infrastructure\\postgres\\sql\\cierre\\04_views_detalle.sql:571', 'infrastructure\\postgres\\sql\\mart\\02_build_fact.sql:271', 'infrastructure\\postgres\\sql\\mart\\02_build_fact.sql:297', 'infrastructure\\postgres\\sql\\mart\\04_view_periodificado.sql:167', 'infrastructure\\postgres\\sql\\mart\\05_views_powerbi.sql:112', 'infrastructure\\postgres\\sql\\mart\\05_views_powerbi.sql:113']
E       assert ['infrastruct...sql:167', ...] == []
E         Left contains 8 more items, first extra item: 'infrastructure\\postgres\\sql\\cierre\\02_build_fact.sql:323'

tests\test_f019_t13_portabilidad.py:88: AssertionError
_ test_f019_t13_cada_derivacion_usa_el_array_de_meses[infrastructure/postgres/sql/cierre/02_build_fact.sql-1] _
[...]
>       assert len(PATRON_ARRAY_MESES.findall(texto)) == veces
E       AssertionError: assert 0 == 1
E        +  where 0 = len([])
[...]
15 failed, 3 passed in 0.46s
```

(Los 3 que ya pasaban entonces eran los de no-regresión de la parte B, que en
ese momento vivían en el mismo fichero; después se separaron en dos ficheros
para que cada commit quedase en verde por sí solo.)

Tras el cambio:

```
$ python -m pytest tests/test_f019_t13_portabilidad.py -q
.............                                                            [100%]
13 passed in 0.07s
```

### B · las claves sustitutas

```
$ python -m pytest tests/test_f019_t13_huella.py -q
[...]
>       assert {"fact_id", "fact_cat_id"} <= set(fp.COLUMNAS_SUSTITUTAS)
                                                 ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'etl_sigrid.infrastructure.postgres.fingerprint' has no attribute 'COLUMNAS_SUSTITUTAS'

tests\test_f019_t13_huella.py:93: AttributeError
_______ test_f019_t13_una_vista_solo_de_sustitutas_conserva_su_recuento _______
[...]
>       assert [m.metrica for m in metricas if m.bloque == fp.BLOQUE_VIVO] == [
            fp.METRICA_COUNT
        ]
E       AssertionError: assert ['count', 'sum_fact_id'] == ['count']
E         Left contains one more item: 'sum_fact_id'
________ test_f019_t13_la_exclusion_no_depende_del_tipo_ni_de_la_vista ________
[...]
E       AssertionError: assert not [Metrica(esquema='mart', vista='v_pbi_fact_categoria', bloque='vivo', metrica='sum_fact_cat_id', valor='1'), Metrica(esquema='cierre', vista='v_otra', bloque='vivo', metrica='sum_fact_cat_id', valor='1')]

=========================== short test summary info ===========================
FAILED tests/test_f019_t13_huella.py::test_f019_t13_la_huella_no_suma_las_claves_sustitutas
FAILED tests/test_f019_t13_huella.py::test_f019_t13_la_lista_de_sustitutas_es_explicita_y_cerrada
FAILED tests/test_f019_t13_huella.py::test_f019_t13_una_vista_solo_de_sustitutas_conserva_su_recuento
FAILED tests/test_f019_t13_huella.py::test_f019_t13_la_exclusion_no_depende_del_tipo_ni_de_la_vista
4 failed, 2 passed in 0.36s
```

Los 2 que pasaban desde el principio son los de **no regresión**
(`las_claves_naturales_se_siguen_sumando` y
`las_sustitutas_siguen_en_el_bloque_estructura`): están para que el arreglo no
se pase de frenada, no para pasar de rojo a verde.

Tras el cambio:

```
$ python -m pytest tests/test_f019_t13_huella.py tests/test_f005_verificacion.py -q
.......................                                                  [100%]
23 passed in 1.40s
```

---

## 3 · Cómo se verificó, con números

### El arreglo B, medido sobre las huellas reales de T13

Reprocesando `huella_local_t13.csv` y `huella_azure_t13.csv` **sin sumar las
sustitutas** (mismos CSV, criterio nuevo):

| | FALLOS |
|---|---|
| Antes | **22** |
| Después | **20** |

Los dos que caen son exactamente los dos falsos:

```
mart.v_fact_periodificado · cerrado · sum_fact_id
mart.v_pbi_fact           · cerrado · sum_fact_id
```

Con `count` idéntico y **todas** las sumas de negocio idénticas en esas dos
vistas: 12.268.877.267.673 (local) contra 12.268.948.757.630 (Azure) era la
única discrepancia. Ninguna otra métrica cambia de veredicto: la exclusión no
tapa nada más.

### El arreglo A: pendiente de reconstrucción

Los 9 fallos de `cierre.v_pbi_planif_vs_real` **siguen apareciendo** en esa
comparación, y tienen que seguir apareciendo: los CSV se sacaron de vistas
construidas con el SQL viejo. Se irán cuando el humano reconstruya los dos
lados (ver §5).

Los 11 restantes son el **defecto 1** (tipos `bigint`/`text` en local contra
`integer`/`character varying` en Azure en `compras.v_pbi_albaranes_sin_facturar`,
`compras.v_pbi_partida_coste` y `compras.v_pbi_proveedor_obra`), ya
diagnosticado en `current.md` y fuera de este encargo.

### Verificación estática del SQL

No hay Postgres local levantado, ni docker en marcha, ni `sqlglot` instalado
(y no se añaden dependencias). La comprobación del SQL es por texto y por
revisión: los tests exigen que el array lleve los doce meses en orden y con la
ortografía exacta, y que el subíndice salga de `EXTRACT(MONTH FROM ...)`. **La
ejecución real contra BBDD es la reconstrucción del §5.**

---

## 4 · Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados y resultado | **398 passed, 0 failed** (`python -m pytest -q` dentro de `bash harness/init.sh`); eran 379 antes del cambio, **+19** |
| Cobertura de las líneas cambiadas | **100,0 %** — 4/4 líneas, umbral 80 %, nivel `critico` (línea `PUERTA COBERTURA` de `init.sh`) |
| Mutantes generados y supervivientes | **1 generado, 1 muerto, 0 supervivientes, 0 timeouts** en 3,6 s (`python -m harness.mutacion --feature F-019` → `progress/mutacion_F-019.md`). El mutante: `fingerprint.py:165`, `and` → `or` en `if tipo in TIPOS_NUMERICOS and c not in COLUMNAS_SUSTITUTAS`; lo mata `test_f019_t13_la_huella_no_suma_las_claves_sustitutas` |
| Tiempo de la suite | **6,03 s** (pytest completo) |
| `bash harness/init.sh` | **ENTORNO LISTO** (verde) |

Las líneas de producción medidas son 4 porque el cambio en Python es pequeño y
concentrado (`columnas_a_sumar` + la constante); la tarea A es SQL, que ni la
cobertura ni la mutación instrumentan — de ahí que su red de seguridad sean
los 13 tests de texto sobre el árbol de `.sql`.

---

## 5 · Qué queda fuera (lo hace el humano)

1. **Reconstruir los dos lados y repetir la huella.** Nada de lo anterior
   cambia una sola fila hasta que se relancen `build-mart` y `build-cierre`
   (y los `apply-grants` que toquen) en **local y en Azure**, y se repita
   `compare-fingerprints`. Criterio de éxito esperado: los 9 fallos de
   `cierre.v_pbi_planif_vs_real` desaparecen y su `count` converge; los 2 de
   `sum_fact_id` ya no pueden aparecer porque la métrica deja de existir.
2. **Defecto 1 (tipos de `compras.*`).** Sigue abierto: el desviado es el raw
   **local**, y el arreglo es drop + re-ingesta + rebuild de compras. No se ha
   tocado nada suyo.
3. **Los CSV de huella de la raíz** (`huella_local_t13.csv`,
   `huella_azure_t13.csv`, `huella_azure_f019.csv`,
   `huella_local_cerrados_f019.csv`, `huella_build_viejo_f019.csv`,
   `huella_build_nuevo_f019.csv`) siguen **sin versionar**, como estaban. Solo
   se han leído. Los nuevos quedarán obsoletos tras la reconstrucción.
4. **Reglas de firewall** `-2026-08-16` y `-16b`: siguen vigentes y hay que
   limpiarlas al cerrar, según `current.md`.
5. **Ninguna verificación MANUAL pendiente** más allá de la reconstrucción del
   punto 1.

## 6 · Ficheros tocados

**Producción**

- `etl_sigrid/infrastructure/postgres/sql/cierre/02_build_fact.sql`
- `etl_sigrid/infrastructure/postgres/sql/cierre/04_views_detalle.sql`
- `etl_sigrid/infrastructure/postgres/sql/mart/02_build_fact.sql`
- `etl_sigrid/infrastructure/postgres/sql/mart/04_view_periodificado.sql`
- `etl_sigrid/infrastructure/postgres/sql/mart/05_views_powerbi.sql`
- `etl_sigrid/infrastructure/postgres/fingerprint.py`

**Tests (nuevos)**

- `tests/test_f019_t13_portabilidad.py` — 13 tests, tarea A
- `tests/test_f019_t13_huella.py` — 6 tests, tarea B

No se tocó `.env`, ni `requirements.txt`, ni `harness/features.json`, ni nada
de `infra/`. No se ejecutó ningún comando contra BBDD, ni local ni remota.
