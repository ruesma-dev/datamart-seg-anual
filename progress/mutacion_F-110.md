<!-- progress/mutacion_F-110.md -->
# F-110 · Campana de mutacion (rigor critico)

**Campana MANUAL y SISTEMATICA**, como la de F-095 tras su review: la
herramienta genera **0 mutantes** para F-110 (ver «Control del cero») porque el
cambio es SQL, YAML y documentacion, y el Python que toca son docstring y
comentarios. Los mutantes NO los elige quien escribio los tests: los genera un
script (`campana.py`, scratchpad de la sesion, con el `sqlmap.py` de F-095) sobre
lo que F-110 toca:

- en `05_fin_obra.sql`, **el CREATE entero de `retenciones.fin_obra`** (los ocho
  SELECT, CTE incluidos, tambien los que F-110 no cambia): una por **expresion
  proyectada** (-> `NULL` conservando el alias), por **FILTER** (quitado), por
  **condicion** de cada `WHERE` (-> `TRUE`) y por **JOIN** (tipo LEFT -> INNER y
  cada condicion de su `ON` -> `TRUE`);
- en la **guarda** `DO $$`: cada condicion `IF` -> `FALSE`, cada bloque `IF`
  quitado, cada prefijo `fin_obra: ` del mensaje quitado, y la guarda movida
  DETRAS del `DROP`;
- **S1-S16**, mutantes semanticos de la regla (MIN en vez de MAX, otro
  `tipo_master`, un solo ambito, `importe_mes > 0`, '1 month', volver al ultimo
  cierre, un `ELSE` que inventa fecha, la guarda de cierre vacio de vuelta...);
- **P1-P16**, la propagacion: `depends_on` con `build_mart`, las tres lecturas
  borradas del docstring y del comentario del step, el comentario de la vista,
  `version: 33`, los `valores` de las dos fichas, INFORMATIVA, la columna nueva,
  el ejemplo del humano, el texto de SIN_FIN_OBRA y `ARCHITECTURE.md`.

Juez: `tests/test_f110_fin_obra_cuatrimestral.py`, `test_f095_retenciones_contables.py`,
`test_f047_steps.py` y `test_f047_nocturna.py`, en una COPIA por worker
(`git archive HEAD`, con `azure-apps/datamart_seg_anual.md` al lado para que el
test de R23 juzgue y no se salte), restaurando tras cada mutante. El arbol del
repositorio no se toca. Cada mutante de Python se compila antes de juzgarlo.

| Dato | Valor |
|---|---|
| SHA de HEAD medido | `5d06b283f60b935e90867df7aadc74cd3a63fb64` |
| Workers | 3 (una copia por worker, en paralelo) |
| Linea base (por copia, antes de mutar) | 18.0 s (146 passed in 16.69s), 11.1 s (146 passed in 10.01s), 12.9 s (146 passed in 11.63s) |
| Timeout por mutante | 180 s |
| Tiempo total | 516.7 s (8.6 min) |
| Mutantes generados | **114** |
| Muertos | **114** |
| Supervivientes | **0** |
| Timeouts | 0 |
| Mortinatos (no compilan) | 0 |

Por tipo: FILTER 1, condicion del ON 7, condicion del WHERE 2, expresion 54, guarda: IF quitado 4, guarda: condicion 4, guarda: detras del DROP 1, guarda: sin nombre del sub-paso 4, semantico 32, tipo de JOIN 5.

## Control del cero automatico

`python -m harness.mutacion --feature F-110 --base main` -> «CERO MUTANTES en
F-110: el alcance tiene 27 linea(s) de produccion pero no se ha generado ni un
mutante» (exit 3, sin informe): las 27 lineas son el docstring y el comentario
de `depends_on` de `build_retenciones_step.py`. **Control**, calculo puro con
`harness.mutacion.generar_mutantes` sobre el fichero ENTERO: **12 mutantes**, en
las lineas 57, 149, 153, 156, 168, 171, 178, 179, 181 y 185 (el `_SubStep` y el
`run()`, que F-110 no toca). El generador funciona: el 0 es legitimo y esta
campana lo sustituye.

## Supervivientes y equivalentes

- **Ningun superviviente.** Nada que declarar equivalente.
- Muertos por un solo test (41): #2, #9, #23, #25, #27, #38, #41, #42, #43, #44, #49, #50, #51, #52, #53, #54, #55, #59, #60, #61, #62, #65, #68, #70, #76, #82, #95, #100, #101, #102, #103, #104, #105, #106, #107, #108, #109, #110, #111, #113, #114. Son
  los que solo ve el contrato expresion a expresion (p. ej. un JOIN de un CTE
  que no cambia de semantica en el texto) o un unico test de propagacion; el
  contrato fija la formula, no el alias, y por eso basta.

## Tabla completa

| # | fichero:linea | tipo | original -> mutado | fallos | resultado |
|---|---|---|---|---|---|
| 1 | `05_fin_obra.sql:134` | expresion | `12` -> `NULL` | 3 | MUERTO |
| 2 | `05_fin_obra.sql:139` | expresion | `c.obride` -> `NULL` | 1 | MUERTO |
| 3 | `05_fin_obra.sql:140` | expresion | `MAX(NULLIF(c.fecinigar, 0))` -> `NULL` | 2 | MUERTO |
| 4 | `05_fin_obra.sql:141` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecreafin, 0)))` -> `NULL` | 2 | MUERTO |
| 5 | `05_fin_obra.sql:142` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0)))` -> `NULL` | 2 | MUERTO |
| 6 | `05_fin_obra.sql:143` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0)))` -> `NULL` | 2 | MUERTO |
| 7 | `05_fin_obra.sql:144` | expresion | `NULLIF(MAX(c.plaret), 0)` -> `NULL` | 2 | MUERTO |
| 8 | `05_fin_obra.sql:145` | expresion | `NULLIF(MAX(c.plagar), 0)` -> `NULL` | 2 | MUERTO |
| 9 | `05_fin_obra.sql:146` | expresion | `COUNT(*)` -> `NULL` | 1 | MUERTO |
| 10 | `05_fin_obra.sql:151` | expresion | `f.obra_id` -> `NULL AS obra_id` | 3 | MUERTO |
| 11 | `05_fin_obra.sql:151` | expresion | `MAX(f.anio_mes)` -> `NULL` | 3 | MUERTO |
| 12 | `05_fin_obra.sql:153` | condicion del WHERE | `f.ejecutado_mes <> 0` -> `TRUE` | 3 | MUERTO |
| 13 | `05_fin_obra.sql:158` | expresion | `v.obra_id` -> `NULL AS obra_id` | 2 | MUERTO |
| 14 | `05_fin_obra.sql:158` | expresion | `MAX(v.version)` -> `NULL` | 2 | MUERTO |
| 15 | `05_fin_obra.sql:160` | condicion del WHERE | `v.tipo_master = 'Cuatrimestral'` -> `TRUE` | 3 | MUERTO |
| 16 | `05_fin_obra.sql:166` | expresion | `c.obra_id` -> `NULL AS obra_id` | 2 | MUERTO |
| 17 | `05_fin_obra.sql:166` | expresion | `c.version_cuatrimestral` -> `NULL AS version_cuatrimestral` | 2 | MUERTO |
| 18 | `05_fin_obra.sql:167` | expresion | `MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0)` -> `NULL` | 3 | MUERTO |
| 19 | `05_fin_obra.sql:169` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 20 | `05_fin_obra.sql:170` | condicion del ON | `pm.obra_id = c.obra_id` -> `TRUE` | 2 | MUERTO |
| 21 | `05_fin_obra.sql:171` | condicion del ON | `pm.version = c.version_cuatrimestral` -> `TRUE` | 2 | MUERTO |
| 22 | `05_fin_obra.sql:172` | condicion del ON | `pm.ambito_id IN (8, 11)` -> `TRUE` | 2 | MUERTO |
| 23 | `05_fin_obra.sql:177` | expresion | `obr.ide` -> `NULL` | 1 | MUERTO |
| 24 | `05_fin_obra.sql:178` | expresion | `con.emp` -> `NULL` | 2 | MUERTO |
| 25 | `05_fin_obra.sql:179` | expresion | `con.cod` -> `NULL` | 1 | MUERTO |
| 26 | `05_fin_obra.sql:180` | expresion | `con.emp::text \|\| '-' \|\| con.cod` -> `NULL` | 2 | MUERTO |
| 27 | `05_fin_obra.sql:181` | expresion | `con.res` -> `NULL` | 1 | MUERTO |
| 28 | `05_fin_obra.sql:182` | expresion | `con.est` -> `NULL` | 2 | MUERTO |
| 29 | `05_fin_obra.sql:183` | expresion | `COALESCE(retenciones.fn_sigrid_date(oc.fec_inicio_garantia), retenciones.fn_sigrid_date(ob...` -> `NULL` | 2 | MUERTO |
| 30 | `05_fin_obra.sql:185` | expresion | `ci.ultimo_cierre` -> `NULL` | 2 | MUERTO |
| 31 | `05_fin_obra.sql:186` | expresion | `pl.version_cuatrimestral` -> `NULL` | 2 | MUERTO |
| 32 | `05_fin_obra.sql:187` | expresion | `pl.ultimo_mes_planificado` -> `NULL` | 2 | MUERTO |
| 33 | `05_fin_obra.sql:189` | expresion | `COALESCE( oc.fec_real_fin, retenciones.fn_sigrid_date(obr.fecfinrea) )` -> `NULL` | 2 | MUERTO |
| 34 | `05_fin_obra.sql:193` | expresion | `oc.fec_recepcion_provisional` -> `NULL` | 2 | MUERTO |
| 35 | `05_fin_obra.sql:194` | expresion | `COALESCE( oc.fec_prev_fin, retenciones.fn_sigrid_date(obr.fecfinpre) )` -> `NULL` | 2 | MUERTO |
| 36 | `05_fin_obra.sql:198` | expresion | `COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT` -> `NULL` | 3 | MUERTO |
| 37 | `05_fin_obra.sql:199` | expresion | `CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE' WHEN oc.plazo_gara...` -> `NULL` | 4 | MUERTO |
| 38 | `05_fin_obra.sql:202` | expresion | `COALESCE(oc.num_contratos_obra, 0)` -> `NULL` | 1 | MUERTO |
| 39 | `05_fin_obra.sql:204` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 40 | `05_fin_obra.sql:204` | condicion del ON | `con.ide = obr.ide` -> `TRUE` | 2 | MUERTO |
| 41 | `05_fin_obra.sql:205` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 42 | `05_fin_obra.sql:205` | condicion del ON | `oc.obra_id = obr.ide` -> `TRUE` | 1 | MUERTO |
| 43 | `05_fin_obra.sql:206` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 44 | `05_fin_obra.sql:206` | condicion del ON | `ci.obra_id = obr.ide` -> `TRUE` | 1 | MUERTO |
| 45 | `05_fin_obra.sql:207` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 46 | `05_fin_obra.sql:207` | condicion del ON | `pl.obra_id = obr.ide` -> `TRUE` | 2 | MUERTO |
| 47 | `05_fin_obra.sql:215` | expresion | `CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia WHEN b.ultimo_m...` -> `NULL` | 5 | MUERTO |
| 48 | `05_fin_obra.sql:219` | expresion | `CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' WHEN b.ultimo_mes_pla...` -> `NULL` | 3 | MUERTO |
| 49 | `05_fin_obra.sql:225` | expresion | `f.obra_id` -> `NULL AS obra_id` | 1 | MUERTO |
| 50 | `05_fin_obra.sql:226` | expresion | `f.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO |
| 51 | `05_fin_obra.sql:227` | expresion | `f.codigo_obra` -> `NULL AS codigo_obra` | 1 | MUERTO |
| 52 | `05_fin_obra.sql:228` | expresion | `f.clave_obra` -> `NULL AS clave_obra` | 1 | MUERTO |
| 53 | `05_fin_obra.sql:229` | expresion | `f.nombre_obra` -> `NULL AS nombre_obra` | 1 | MUERTO |
| 54 | `05_fin_obra.sql:230` | expresion | `f.estado_obra` -> `NULL AS estado_obra` | 1 | MUERTO |
| 55 | `05_fin_obra.sql:231` | expresion | `f.fecha_inicio_garantia` -> `NULL AS fecha_inicio_garantia` | 1 | MUERTO |
| 56 | `05_fin_obra.sql:232` | expresion | `f.ultimo_cierre` -> `NULL AS ultimo_cierre` | 2 | MUERTO |
| 57 | `05_fin_obra.sql:233` | expresion | `f.version_cuatrimestral` -> `NULL AS version_cuatrimestral` | 2 | MUERTO |
| 58 | `05_fin_obra.sql:234` | expresion | `f.ultimo_mes_planificado` -> `NULL AS ultimo_mes_planificado` | 2 | MUERTO |
| 59 | `05_fin_obra.sql:235` | expresion | `f.fecha_fin_real` -> `NULL AS fecha_fin_real` | 1 | MUERTO |
| 60 | `05_fin_obra.sql:236` | expresion | `f.fecha_recepcion_provisional` -> `NULL AS fecha_recepcion_provisional` | 1 | MUERTO |
| 61 | `05_fin_obra.sql:237` | expresion | `f.fecha_fin_prevista` -> `NULL AS fecha_fin_prevista` | 1 | MUERTO |
| 62 | `05_fin_obra.sql:238` | expresion | `f.fecha_fin_obra` -> `NULL AS fecha_fin_obra` | 1 | MUERTO |
| 63 | `05_fin_obra.sql:239` | expresion | `f.fuente_fin_obra` -> `NULL AS fuente_fin_obra` | 2 | MUERTO |
| 64 | `05_fin_obra.sql:240` | expresion | `(f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25))` -> `NULL` | 4 | MUERTO |
| 65 | `05_fin_obra.sql:241` | expresion | `f.plazo_meses` -> `NULL AS plazo_meses` | 1 | MUERTO |
| 66 | `05_fin_obra.sql:242` | expresion | `f.fuente_plazo` -> `NULL AS fuente_plazo` | 4 | MUERTO |
| 67 | `05_fin_obra.sql:243` | expresion | `(f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE` -> `NULL` | 6 | MUERTO |
| 68 | `05_fin_obra.sql:244` | expresion | `f.num_contratos_obra` -> `NULL AS num_contratos_obra` | 1 | MUERTO |
| 69 | `05_fin_obra.sql:167` | FILTER | `FILTER (WHERE pm.importe_mes <> 0)` -> (nada) | 3 | MUERTO |
| 70 | `05_fin_obra.sql:116` | guarda: condicion | `to_regclass('mart.master_versiones_tipadas') IS NULL` -> `FALSE` | 1 | MUERTO |
| 71 | `05_fin_obra.sql:116` | guarda: IF quitado | `IF to_regclass('mart.master_versiones_tipadas') IS NULL THEN RAISE EXCEPTION 'fin_obra: no...` -> (nada) | 3 | MUERTO |
| 72 | `05_fin_obra.sql:117` | guarda: sin nombre del sub-paso | `fin_obra:` -> (nada) | 3 | MUERTO |
| 73 | `05_fin_obra.sql:119` | guarda: condicion | `NOT EXISTS (SELECT 1 FROM mart.master_versiones_tipadas WHERE tipo_master = 'Cuatrimestral...` -> `FALSE` | 2 | MUERTO |
| 74 | `05_fin_obra.sql:119` | guarda: IF quitado | `IF NOT EXISTS (SELECT 1 FROM mart.master_versiones_tipadas WHERE tipo_master = 'Cuatrimest...` -> (nada) | 4 | MUERTO |
| 75 | `05_fin_obra.sql:120` | guarda: sin nombre del sub-paso | `fin_obra:` -> (nada) | 3 | MUERTO |
| 76 | `05_fin_obra.sql:122` | guarda: condicion | `NOT EXISTS (SELECT 1 FROM stg.plan_mensual WHERE ambito_id IN (8, 11))` -> `FALSE` | 1 | MUERTO |
| 77 | `05_fin_obra.sql:122` | guarda: IF quitado | `IF NOT EXISTS (SELECT 1 FROM stg.plan_mensual WHERE ambito_id IN (8, 11)) THEN RAISE EXCEP...` -> (nada) | 3 | MUERTO |
| 78 | `05_fin_obra.sql:123` | guarda: sin nombre del sub-paso | `fin_obra:` -> (nada) | 3 | MUERTO |
| 79 | `05_fin_obra.sql:125` | guarda: condicion | `to_regclass('cierre.fact_cierre_mensual') IS NULL` -> `FALSE` | 2 | MUERTO |
| 80 | `05_fin_obra.sql:125` | guarda: IF quitado | `IF to_regclass('cierre.fact_cierre_mensual') IS NULL THEN RAISE EXCEPTION 'fin_obra: no ex...` -> (nada) | 3 | MUERTO |
| 81 | `05_fin_obra.sql:126` | guarda: sin nombre del sub-paso | `fin_obra:` -> (nada) | 3 | MUERTO |
| 82 | `05_fin_obra.sql:114` | guarda: detras del DROP | `DO $$ BEGIN IF to_regclass('mart.master_versiones_tipadas') IS NULL THEN RAISE EXCEPTION '...` -> `DROP TABLE IF EXISTS retenciones.fin_obra CASCADE; DO $$ BEGIN IF to_regclass('mart.master...` | 1 | MUERTO |
| 83 | `05_fin_obra.sql:158` | semantico S1 | `MAX(v.version) AS version_cuatrimestral` -> `MIN(v.version) AS version_cuatrimestral` | 2 | MUERTO |
| 84 | `05_fin_obra.sql:160` | semantico S2 | `WHERE v.tipo_master = 'Cuatrimestral'` -> `WHERE v.tipo_master = 'ABC'` | 2 | MUERTO |
| 85 | `05_fin_obra.sql:160` | semantico S3 | `WHERE v.tipo_master = 'Cuatrimestral'` -> `WHERE v.tipo_master = 'Cuatrimestral' AND v.ambito_id = 11` | 2 | MUERTO |
| 86 | `05_fin_obra.sql:167` | semantico S4 | `FILTER (WHERE pm.importe_mes <> 0)` -> `FILTER (WHERE pm.importe_mes > 0)` | 3 | MUERTO |
| 87 | `05_fin_obra.sql:172` | semantico S5 | `AND pm.ambito_id IN (8, 11)` -> `AND pm.ambito_id IN (11)` | 2 | MUERTO |
| 88 | `05_fin_obra.sql:171` | semantico S6 | `AND pm.version = c.version_cuatrimestral` -> `AND pm.version >= c.version_cuatrimestral` | 2 | MUERTO |
| 89 | `05_fin_obra.sql:217` | semantico S7 | `(b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE` -> `(b.ultimo_mes_planificado + INTERVAL '1 month' - INTERVAL '1 day')::DATE` | 4 | MUERTO |
| 90 | `05_fin_obra.sql:217` | semantico S8 | `(b.ultimo_mes_planificado + INTERVAL '2 months' - INTERVAL '1 day')::DATE` -> `(b.ultimo_mes_planificado + INTERVAL '1 month')::DATE` | 4 | MUERTO |
| 91 | `05_fin_obra.sql:217` | semantico S9 | `(b.ultimo_mes_planificado + INTERVAL` -> `(COALESCE(b.ultimo_mes_planificado, b.ultimo_cierre) + INTERVAL` | 5 | MUERTO |
| 92 | `05_fin_obra.sql:215` | semantico S10 | `CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia` -> `CASE WHEN FALSE THEN b.fecha_inicio_garantia` | 3 | MUERTO |
| 93 | `05_fin_obra.sql:220` | semantico S11 | `'ULTIMO_CUATRIMESTRAL_MAS_1_MES'` -> `'ULTIMO_CIERRE_MAS_1_MES'` | 3 | MUERTO |
| 94 | `05_fin_obra.sql:218` | semantico S12 | `END AS fecha_fin_obra,` -> `ELSE (b.ultimo_cierre + INTERVAL '2 months' - INTERVAL '1 day')::DATE END AS fecha_fin_obr...` | 6 | MUERTO |
| 95 | `05_fin_obra.sql:122` | semantico S13 | `WHERE ambito_id IN (8, 11)) THEN` -> `WHERE ambito_id IN (3, 7)) THEN` | 1 | MUERTO |
| 96 | `05_fin_obra.sql:125` | semantico S14 | `IF to_regclass('cierre.fact_cierre_mensual') IS NULL THEN` -> `IF NOT EXISTS (SELECT 1 FROM cierre.fact_cierre_mensual) THEN RAISE EXCEPTION 'fin_obra: c...` | 3 | MUERTO |
| 97 | `05_fin_obra.sql:207` | semantico S15 | `LEFT JOIN plan pl ON pl.obra_id = obr.ide` -> `LEFT JOIN plan pl ON pl.obra_id = con.cod::BIGINT` | 2 | MUERTO |
| 98 | `05_fin_obra.sql:233` | semantico S16 | `f.version_cuatrimestral, f.ultimo_mes_planificado,` -> (nada) | 3 | MUERTO |
| 99 | `build_retenciones_step.py:142` | semantico P1 | `return ["ingest_raw"]` -> `return ["ingest_raw", "build_mart"]` | 4 | MUERTO |
| 100 | `build_retenciones_step.py:23` | semantico P2 | `'mart.master_versiones_tipadas'` -> `la tabla de versiones` | 1 | MUERTO |
| 101 | `build_retenciones_step.py:24` | semantico P3 | `'stg.plan_mensual'` -> `el plan mensual` | 1 | MUERTO |
| 102 | `build_retenciones_step.py:27` | semantico P4 | `'cierre.fact_cierre_mensual'` -> `el cierre` | 1 | MUERTO |
| 103 | `build_retenciones_step.py:136` | semantico P5 | `'mart.master_versiones_tipadas'` -> `la tabla de versiones` | 1 | MUERTO |
| 104 | `build_retenciones_step.py:137` | semantico P6 | `'stg.plan_mensual'` -> `el plan mensual` | 1 | MUERTO |
| 105 | `build_retenciones_step.py:132` | semantico P7 | `'cierre.fact_cierre_mensual'` -> `el cierre` | 1 | MUERTO |
| 106 | `06_views_contables.sql:35` | semantico P8 | `ni cuatrimestral con plan` -> `ni cierre con movimiento` | 1 | MUERTO |
| 107 | `00_global.yaml:371` | semantico P9 | `version: 34` -> `version: 33` | 1 | MUERTO |
| 108 | `retenciones.yaml:1427` | semantico P10 | `valores: [INICIO_GARANTIA, ULTIMO_CUATRIMESTRAL_MAS_1_MES]` -> `valores: [INICIO_GARANTIA, ULTIMO_CIERRE_MAS_1_MES]` | 1 | MUERTO |
| 109 | `retenciones.yaml:1594` | semantico P11 | `valores: [INICIO_GARANTIA, ULTIMO_CUATRIMESTRAL_MAS_1_MES]` -> `valores: [INICIO_GARANTIA, ULTIMO_CIERRE_MAS_1_MES]` | 1 | MUERTO |
| 110 | `retenciones.yaml:1382` | semantico P12 | `INFORMATIVA desde F-110: no interviene en el fin de obra ni en el` -> `Desde F-110 no interviene en el fin de obra ni en el` | 1 | MUERTO |
| 111 | `retenciones.yaml:1390` | semantico P13 | `version_cuatrimestral:` -> `version_cuatrimestral_x:` | 1 | MUERTO |
| 112 | `retenciones.yaml:1290` | semantico P14 | `cuatrimestral de junio 26 puede tener planificada la obra hasta marzo 28;` -> `cuatrimestral de junio 26 puede tener planificada la obra hasta abril 28;` | 2 | MUERTO |
| 113 | `retenciones.yaml:1548` | semantico P15 | `ni inicio de garantia ni cuatrimestral con plan, F-110` -> `ni inicio de garantia ni cierre con movimiento` | 1 | MUERTO |
| 114 | `ARCHITECTURE.md:164` | semantico P16 | `'stg.plan_mensual' qué` -> `el plan qué` | 1 | MUERTO |
