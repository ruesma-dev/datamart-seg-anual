<!-- progress/impl_F-118.md -->
# F-118 · Informe del implementer

Rama `feature/F-118-cruce-cierre-agosto` · 2026-09-29/30 · rigor `critico` ·
spec `specs/F-118-cruce-cierre-agosto/` (F-051 y F-103 absorbidas). Hechas
T1-T25 y T32; T26-T31 son MANUAL (humano) y están, con comando y resultado
esperado, en `progress/current.md` (sección F-118). Nada escrito en Azure ni en
Sigrid: las lecturas de contraste fueron SELECT en transacción `READ ONLY`.

## Qué cambió (por bloque)

| Bloque | Tareas | Resultado |
|---|---|---|
| A · el mes | T1-T4 | `domain/mes_fase.py`: `parse_mes_fase`, `mes_de_fase` (cascada texto → fin → inicio → archivado), `meses_relleno` |
| B · serie densa | T5-T7 | `domain/serie_real.py`: `serie_densa` (cierre sin fila → 0 y se deshace; relleno arrastra; D3) e invariante con 400 obras-ámbito generadas |
| C · `stg` | T8-T15 | `stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase`; `es_relleno`/`es_deshacer`; rama de reales reescrita (`reales_final`); `00_functions.sql` en el sello; huella `--propuesta` sobre `reales_final`; `check-cierres` sin apartados (R37) |
| D · `mart`/`cierre` | T16-T19 | `nombre_mes` de `anio_mes` en las ramas reales; marcas en `mart` y `v_pbi_fact`; `cierre` agrupa por `pm.anio_mes`, publica `es_relleno` y arrastra el ejecutado (R38); `cierre.fn_mes_de_fase` envuelve la de `stg`; `v_pbi_planif_vs_real` blindada |
| E · coeficientes | T20-T22 | venta final con `importe`; `final_importe_con_coeficientes` (solo VENTA y master); columna en el resumen (fila VENTA) y dos en la cabecera |
| F · cierre | T23-T25, T32 | `check-mes-fase`; diccionario v38 con `R-VENTA-COEFICIENTES`; `ARCHITECTURE.md`; `init.sh` |

Ficheros: SQL `stg/00_functions.sql`, `stg/01_ddl.sql`, `stg/08_plan_mensual.sql`,
`mart/01_ddl.sql`, `02_build_fact.sql`, `05_views_powerbi.sql`, `cierre/00_setup.sql`,
`01_ddl_fact.sql`, `02_build_fact.sql`, `03_views.sql`, `04_views_detalle.sql`,
`05_views_cabecera.sql`, `06_views_planif_vs_real.sql`; Python `domain/mes_fase.py`,
`domain/serie_real.py` (nuevos), `domain/cierres.py`, `infrastructure/postgres/
cierres_sql.py`, `huella_obras.py`, `mes_fase_sql.py` (nuevo),
`application/steps/build_stg_step.py`, `main.py`; `config/diccionario/{stg,mart,
cierre,00_global}.yaml`; `docs/ARCHITECTURE.md`; enmienda de recuentos en
`specs/F-006-mcp-azure/design*.md`; tests `test_f118_*` (6 nuevos) y los de
F-042, F-025, F-073, F-019, F-006, F-079 y F-097 que fijaban lo que cambia.

## Decisiones y desviaciones (para el reviewer)

1. **El mes se calcula por FASE, no por fila** (`reales_cierres`, no
   `reales_base`): una llamada a la función plpgsql por fase y no por partida.
   `make_date(f.anio, f.mes, 1)` sigue en el texto, pero solo como cuarto
   argumento (el mes archivado de la cascada, R6); el test prohíbe que sea el
   origen de `anio_mes`, que es lo que pedía T8. El filtro `anio/mes IS NOT
   NULL` se conserva: el universo de fases no cambia.
2. **Reglas del parser** (design §4 dejaba ambiguo qué años sustituyen en un
   rango): cuatro cifras 2000-2099 siempre; DOS cifras justo detrás de un
   nombre de mes (cubre «Mayo-17», «DICIEMBRE 09 A FEBRERO 2010»); dos cifras
   20-99 sin año todavía (lo de `cierre`); 1-12 sin mes todavía es el mes. Para
   leer «AGOSTO17» (R4) se separan letras y cifras pegadas, y todo lo que no es
   letra ni cifra separa tokens. Contraste local SQL = oráculo: **20.030 textos,
   0 diferencias** (los de la spec más 20.000 aleatorios).
3. **Dos fases de rango que quieren el mismo mes**: lo rellena la de mes del
   texto más cercano (la que cierra antes). La spec no lo trataba y sin regla la
   clave (partida, mes) se repetiría; oráculo y SQL hacen lo mismo (test).
4. **D3 afinado** (lo destapó el contraste local, no la spec): un relleno se
   publica si su acumulado no es 0 o si la partida TIENE FILA de Sigrid que se
   mueve en la fase generadora; un deshacer en esa fase no cuenta (no hay fila
   de la que tomar presupuesto y precio: violaba el NOT NULL).
5. **El deshacer se publica si mueve cualquiera de los cuatro acumulados**
   (importe, raw, cantidad, incurrido): así telescopean los cuatro, no solo el
   importe. `check-mes-fase` cuenta «sin movimiento» con los cuatro.
6. **Sin LEFT JOIN a las filas de Sigrid**: la serie se arma con UNION ALL +
   GROUP BY y el alta sale de las propias filas. Con JOIN, las CTE sin
   estadísticas llevaban al optimizador a un bucle anidado: 28 s para 11.000
   filas en local; con la forma nueva, 0,9 s.
7. **`check-cierres`**, además del telescopio de R37: los candidatos salen con
   el mes del texto y lo publicado sin relleno. Sin eso la regla de F-042 sobre
   el mes del texto (R8) daría una discrepancia por cada fase de rango.
   `hay_hueco_de_origen` y `orden_de_los_publicados` se retiran con sus 5 tests.
8. **Rama master**: sus CTE no cambian (hash de F-042 intacto); su SELECT gana
   `NULL::BOOLEAN` × 2. El hash del SELECT se calcula ahora sin esas dos líneas,
   así que cualquier otro cambio lo sigue cazando.
9. `DROP FUNCTION IF EXISTS cierre.fn_mes_de_fase(DATE, TEXT) CASCADE`: la
   firma vieja haría ambigua la nueva; las vistas de detalle que la usaban se
   recrean en el mismo build (el mismo patrón que el `DROP TABLE ... CASCADE`
   de `01_ddl_fact.sql`).
10. `es_relleno` del fact de `cierre` es NULL cuando el concepto no tiene filas
    ese mes (su ejecutado arrastra la fila anterior, R38).
11. `stg/06_presupuesto.sql` no se toca (R44 y hash de F-073): su comentario
    «lo usa el cierre» sobre `importe_oficial` queda desfasado; lo corrige la
    ficha del diccionario.
12. **Testigos de design §9 a corregir en T29**: con el mes del texto la 0371 f29
    cae en **2015-05** (relleno feb-abr), no en 2015-02, y la 0606 f16 en
    **2021-05**, no en 2021-09 (F-051 D2). Las cifras no cambian (sonda abajo).

## Tests de F-042 reescritos (T12 y T15), uno a uno

| Test antiguo | Qué fijaba | Sustituto |
|---|---|---|
| `test_f042_sql` `…_rama_master_no_cambia_ni_un_byte[SELECT]` | hash del SELECT master | mismo hash, sin las dos columnas NULL de F-118 |
| `…_existen_las_tres_cte_de_la_regla` | `reales_orden` | `…_existen_las_cte_de_la_regla` (cierres, vigente) |
| `…_el_orden_se_desplaza_por_descartes…` | desplazamiento, sin dense_rank | `…_sin_dense_rank_ni_desplazamiento_de_fases` |
| `…_la_ventana_del_desplazamiento_particiona…` | ventana de `reales_orden` | `…_el_relleno_y_los_vigentes_se_deciden_por_obra_y_ambito` |
| `…_los_cuatro_case_del_lag_comparan_orden_fase` | el `CASE` del defecto | `…_los_cuatro_movimientos_restan_el_mes_anterior_de_la_serie` |
| `…_la_ventana_del_lag_ordena_por_orden_fase` | `ORDER BY orden_fase` | `…_la_ventana_del_lag_ordena_por_mes` |
| `…_reales_con_lag_lee_solo_los_cierres_que_viven` | `WHERE o.vive` | `…_las_filas_de_sigrid_son_solo_las_de_los_cierres_que_viven` |
| `…_los_marcadores_delimitan_el_bloque…` | lista de CTE con `reales_orden` | misma, con `reales_final` |
| `test_f042_huella` (2) | `LAG(orden_fase)` en la propuesta | leen `reales_final` y el LAG nuevo |
| `test_f042_regla` `…_r6_…_suma_por_tramos` | el DEFECTO (hueco que no telescopea) | `…_r6_…_la_serie_densa_telescopea` |
| `test_f042_check_cierres` 5 de hueco + `…_aparta_…` | el apartado | `test_f118_check.py` (R37) |

## Fase RED (trazas reales, comando exacto)

`.venv/Scripts/python.exe -m pytest <fichero> -q`, antes del código:

```
T1  tests/test_f118_regla_mes.py
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.mes_fase'
1 error in 1.27s
T3  tests/test_f118_regla_mes.py -k relleno
E   ImportError: cannot import name 'FaseReal' from 'etl_sigrid.domain.mes_fase'
T5  tests/test_f118_serie_densa.py
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.serie_real'
T7  (mutante en COPIA aislada del scratchpad: `filas.get(mes, _CERO)` ->
    `filas.get(mes, ultimo_cierre)`, es decir, el cierre ausente arrastra)
E   assert Decimal('101.29') == Decimal('0')
FAILED …::test_f118_r21_la_suma_telescopea_al_ultimo_cierre_del_ambito
2 failed in 0.33s
T8  tests/test_f118_sql.py            -> 27 failed, 7 passed in 2.70s
    (funciones, DDL, serie densa, sello: p. ej. …_r9_stg_sin_orden_fase_ni_case…)
T13 tests/test_f118_sql.py -k sello
E   AssertionError: assert ('06_presupue..._mensual.sql') == ('00_function..._mensual.sql')
T14 tests/test_f042_huella.py
E   AssertionError: assert 'FROM reales_final rf' in 'WITH\nreales_base AS (…'
2 failed, 49 passed in 4.24s
T15 tests/test_f118_check.py          -> 8 failed in 3.25s (telescopio y R8)
T16 tests/test_f118_sql.py -k "mart or cierre or vista" -> 17 failed, 4 passed
T20 tests/test_f118_coeficientes.py   -> 11 failed, 7 passed in 1.64s
E   SUM(pres.importe_oficial)::NUMERIC(18,2) AS final_importe,   (rama VENTA)
T23 tests/test_f118_check.py          -> 8 failed, 14 passed (sin comando)
```

El diccionario (T24) y la vista (T19) se escribieron con su test en el mismo
paso; no son requisitos centrales.

## Verificación ejecutada (resultado real)

**Cluster Postgres 16 desechable en el scratchpad** (puerto 55434, no es el del
`.env`), con el SQL del árbol tal cual:

- Parser: 20.030 textos, SQL = oráculo, 0 diferencias; cascada con fechas, OK.
- Rama de reales frente al oráculo (`serie_densa` + F-042 + `meses_relleno`)
  sobre obras sintéticas con rangos, solapes, colisiones de mes, huecos de
  numeración y fases sin filas de un ámbito, construidas en DOS tramos:

| Semilla / obras | Filas publicadas | Faltan | Distintas | Claves repetidas | Series rotas (4 medidas) |
|---|---|---|---|---|---|
| 5 / 3.000 | 127.489 (46.786 relleno, 10.580 deshacer) | 0 | 0 | 0 | 0 de 22.286 |
| 2026 / 1.500 | 62.933 | 0 | 0 | 0 | 0 de 11.051 |
| 118 / 400 y 7 / 400 | 16.941 y 16.622 | 0 | 0 | 0 | 0 |

  «Sobran» respecto al oráculo 424 / 262 / 48 / 64 filas: todas de deshacer con
  importe 0 que mueven cantidad o incurrido (decisión 5).
- `mart` y `cierre` completos (01-06) construyen; VENTA arrastrada (R38) = el
  acumulado del último mes con filas en las 12.013 filas-mes; `check-cierres`
  local: 0 discrepancias y 11.051 series, 0 rotas; `check-mes-fase` local:
  9.030 fases, 0 discrepancias, 0 claves repetidas, 0/0/0 en las marcas.
- Fallo 2 con un master sintético (venta 1.000 y con coeficientes 1.190 por
  partida): venta final 5.000,00 y `final_importe_con_coeficientes` 5.950,00;
  pendiente y BENEFICIO salen de 5.000; coste sin la columna; cabecera
  5.000 / 5.950; 0 filas con la columna fuera de VENTA/master.
- Tiempo de la rama (3.000 obras sintéticas): 2,80 s antes, 9,70 s después
  (1,9x filas por el relleno sintético). En real se mide en T27.

**Sondas de SOLO LECTURA en Azure** (el bloque de reales tal cual, con
`stg.fn_mes_de_fase` sustituida por su cascada con el parser de `cierre`,
porque la función aún no existe allí):

- **0709** venta: jul-26 396.768,08; **ago-26 377.492,30** (1 fila de deshacer);
  **sep-26 0,00**. Partida 417031: -58.000 (jul), **+58.000 deshacer** (ago), 0
  (sep): suma 0 (R35).
- **0371** coste: f29 en 2015-05, **-441.229,31** (R36); venta f29: 0.
- **0606**: coste -9.053.263,61 y venta -9.188.957,62 en **2021-05** (decisión 12).

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests | 6.149 passed, 219 skipped, 0 failed (suite entera, `init.sh`) |
| Tests de F-118 | 205 en `test_f118_*` (+ los reescritos de F-042) |
| Cobertura de las líneas cambiadas | **97,9 %** (237/242, umbral 80 %, nivel critico; diff desde 94e8fc2b68) |
| Mutación | N/A: exención heredada de F-051 D7 (como F-042), sustituida por huellas (T26-T29) e invariante R21 (T7, más el contraste local de 4 semillas). Sin campaña, sin workers |
| Tiempo de la suite | 700,66 s con cobertura (`init.sh`); 381,77 s sin ella |
| `bash harness/init.sh` | **exit 0**: pytest en verde, PUERTA COBERTURA OK, PUERTA TAMAÑO OK (impl 192/220), ruff 234 avisos previos (no bloquea), sobre c31ce51 |

Nota: la primera `init.sh` (precondición) dio pytest en verde (5.938 passed) y
su puerta de cobertura en KO 0/154 porque los commits T1-T4 entraron mientras
corría (medía un árbol y juzgaba otro); no es un rojo del árbol de partida.

## Fuera de alcance y pendiente

- T26-T31 MANUAL (humano), en `progress/current.md`: huellas antes/después,
  funciones en Azure y `--propuesta`, aviso a Juan, despliegue con
  reconstrucción completa, hoja de cierre de agosto y publicar diccionario v38.
- No cambia `azure-apps/datamart_seg_anual.md` (no lista columnas) ni
  `arnes-base` (nada del arnés). F-099 (coeficientes por contrato) y F-096
  (rama master) quedan fuera, como dice la spec.
