<!-- progress/mutacion_F-038.md -->
# F-038 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-038` el 2026-10-05 14:44.

## Alcance

Origen del diff: **rama** (`e9c5507390fffa56229a5ae825442cf09e136930` .. `feature/F-038-comparativos`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 19 |
| `etl_sigrid/domain/comparativos.py` | 65 |
| **Total** | **84** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 13 |
| Mutantes evaluados | 13 |
| Muertos | 13 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3665.0 s |
| SHA de HEAD medido | `d2d1d34d94a1d344c0015033b3fa5dd023fbc9a2` |
| Línea base (s) — `.` | 419.4 |
| Media por mutante evaluado (s) | 281.9 |
| Timeout efectivo por mutante (s) | 839 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Ninguno: cada mutación aplicada la cazó al menos un test.

## Anexo · campaña MANUAL sobre el SQL de la Fase 2 (no la genera `harness.mutacion`)

`harness.mutacion` solo muta Python y la lógica de la Fase 2 vive sobre todo en
SQL. Script versionado: `progress/mutacion_sql_F-038_fase2.py` (mutantes =
sustituciones de texto exactas). Worktree desechable `git worktree add --detach`
de `d2d1d34d94a1d344c0015033b3fa5dd023fbc9a2` (el SQL no ha cambiado desde
entonces), **1 worker, en serie**, tests `test_f038_sql`, `test_f038_dominio`,
`test_f038_diccionario` y `test_f006_fichas` sin `-x`. Línea base antes y
después: 0 fallos (1073 passed, 221 skipped). **25 mutantes, 25 muertos, 0
supervivientes.** Columna «fallos» = nº de tests FAILED. La campaña de la Fase 1
(M01-M24, 24/24) está en `progress/mutacion_F-038_fase1.md`.

| Id | fichero:línea | original -> mutado | fallos |
|---|---|---|---|
| M25 | `00_setup.sql:152` | `WHEN t ~ '^-?[0-9]+(,[0-9]+)?%$' THEN` -> `WHEN t ~ '^-?[0-9]+(,[0-9]+)?%' THEN` | 1 |
| M26 | `00_setup.sql:152` | `replace(replace(t, '%', ''), ',', '.')::NUMERIC` -> `replace(t, '%', '')::NUMERIC` | 1 |
| M27 | `09_comparativos_detalle.sql:62` | `FROM raw.comlin l\nLEFT JOIN raw.dncpro n` -> `FROM raw.comlin l\nJOIN raw.dncpro n` | 1 |
| M28 | `09_comparativos_detalle.sql:57` | `NULLIF(n.paride, 0)` -> `NULLIF(n.ide, 0)` | 1 |
| M29 | `09_comparativos_detalle.sql:106` | `WHERE lp.comlinide > 0` -> `WHERE lp.comlinide >= 0` | 1 |
| M30 | `09_comparativos_detalle.sql:79` | `WHERE d.es_primera_abc\nGROUP BY d.obra_id` -> `WHERE d.es_vigente\nGROUP BY d.obra_id` | 2 |
| M31 | `09_comparativos_detalle.sql:124` | `WHERE lo.familia_ficticia = 'OBJETIVO' AND lo.porcentaje_descuento IS NOT NULL` -> `WHERE lo.es_ficticia AND lo.porcentaje_descuento IS NOT NULL` | 1 |
| M32 | `09_comparativos_detalle.sql:139` | `<= 0.011 + 0.002 * abs(ob.precio)` -> `<= 0.011 + 0.02 * abs(ob.precio)` | 1 |
| M33 | `09_comparativos_detalle.sql:142` | `AND d.fase_num <= ob.fase_abc)` -> `AND d.fase_num >= 0)` | 1 |
| M34 | `09_comparativos_detalle.sql:142` | `'MASTER_ESTUDIO', 'ESTUDIO', 'MASTER_PRE_ABC')` -> `'MASTER_ESTUDIO', 'ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')` | 1 |
| M35 | `09_comparativos_detalle.sql:143` | `OR (ob.fase_abc IS NULL AND d.origen IN ('MASTER_ESTUDIO', 'ESTUDIO'))` -> `OR (ob.fase_abc IS NULL)` | 1 |
| M36 | `09_comparativos_detalle.sql:158` | `c.por_dncpro DESC, c.casa DESC, c.orden` -> `c.casa DESC, c.por_dncpro DESC, c.orden` | 1 |
| M37 | `09_comparativos_detalle.sql:175` | `e.casa DESC, e.fase_num DESC, e.origen` -> `e.casa DESC, e.fase_num ASC, e.origen` | 1 |
| M38 | `09_comparativos_detalle.sql:174` | `WHERE e.casa OR e.es_primera_abc OR ob.fase_abc IS NULL` -> `WHERE TRUE` | 1 |
| M39 | `09_comparativos_detalle.sql:200` | `WHEN cd.linea_oferta_id IS NOT NULL THEN FALSE END AS casa_base` -> `ELSE FALSE END AS casa_base` | 1 |
| M40 | `09_comparativos_detalle.sql:138` | `COALESCE(d.dncpro_id = ob.dncpro_id, FALSE)` -> `COALESCE(d.producto_id = ob.dncpro_id, FALSE)` | 1 |
| M41 | `09_comparativos_detalle.sql:225` | `ORDER BY o.fecha_oferta DESC NULLS LAST, o.oferta_id DESC` -> `ORDER BY o.fecha_oferta ASC NULLS LAST, o.oferta_id DESC` | 1 |
| M42 | `09_comparativos_detalle.sql:246` | `CASE WHEN cp.n_porcentajes = 1 THEN` -> `CASE WHEN cp.n_porcentajes >= 1 THEN` | 1 |
| M43 | `09_comparativos_detalle.sql:236` | `FILTER (WHERE l.casa_base)` -> `FILTER (WHERE l.casa_base IS NOT NULL)` | 1 |
| M44 | `09_comparativos_detalle.sql:254` | `WHERE ob.orden = 1;` -> `WHERE ob.orden >= 1;` | 1 |
| M45 | `09_comparativos_detalle.sql:275` | `COALESCE(f.fir = 0, FALSE)` -> `COALESCE(f.fir = 1, FALSE)` | 1 |
| M46 | `09_comparativos_detalle.sql:279` | `JOIN raw.com m ON m.ide = f.conide;` -> `LEFT JOIN raw.com m ON m.ide = f.conide;` | 1 |
| M47 | `09_comparativos_detalle.sql:76` | `CREATE TEMP TABLE _f038_obra_abc ON COMMIT DROP AS` -> `CREATE TEMP TABLE _f038_obra_abc AS` | 1 |
| M48 | `09_comparativos_detalle.sql:199` | `CASE WHEN el.es_primera_abc THEN 'ABC' ELSE el.origen END \|\| ' v' \|\| el.fase_num` -> `el.origen \|\| ' v' \|\| el.fase_num` | 1 |
| M49 | `09_comparativos_detalle.sql:226` | `FROM compras.comparativo_ofertas o\n    WHERE o.familia_ficticia = 'OBJETIVO'` -> `FROM compras.comparativo_ofertas o\n    WHERE o.es_ficticia` | 1 |

**Límite declarado**: los tests leen el TEXTO del SQL, así que matan cualquier
desviación del texto esperado; no prueban que el SQL corra ni sus cifras. Eso es
MANUAL del humano tras el despliegue (cifras de D4 y T25 en `progress/current.md`).
