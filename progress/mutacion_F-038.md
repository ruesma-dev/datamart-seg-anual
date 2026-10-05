<!-- progress/mutacion_F-038.md -->
# F-038 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-038` el 2026-10-04 17:00.

## Alcance

Origen del diff: **rama** (`4dfe8c70b52d3774a8a302c5d0abae185157a509` .. `feature/F-038-comparativos`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 16 |
| `etl_sigrid/domain/comparativos.py` | 119 |
| **Total** | **135** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 14 |
| Mutantes evaluados | 14 |
| Muertos | 13 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3011.4 s |
| SHA de HEAD medido | `9a738095ec3f2a6a091627b9afc2b6f79f0a7cff` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-038_7itw3jy2/wk_0` | 393.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-038_7itw3jy2/wk_1` | 397.7 |
| Media por mutante evaluado (s) | 215.1 |
| Timeout efectivo por mutante (s) | 796 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/comparativos.py:117` [entero]

- Original: `if adjudicado is None or mayor_oferta is None or mayor_oferta <= 0:`
- Mutado:   `if adjudicado is None or mayor_oferta is None or mayor_oferta <= 1:`

#### Análisis del implementer

> Por qué ningún test lo caza: los casos de `test_f038_r16_es_adjudicado_atipico`
> usaban como mayor oferta 0, -5 o importes de 10 € para arriba; ninguno caía en
> (0, 1], que es justo la franja donde `<= 0` y `<= 1` discrepan. **Hueco real,
> no equivalente**: una mayor oferta de 0,50 € SÍ permite juzgar el atípico
> (el SQL hace `CASE WHEN mayor_oferta > 0`), y el mutante devolvería NULL.
> Decisión: **test nuevo** en `tests/test_f038_dominio.py`, dos casos con mayor
> oferta 0,50 € (→ True) y 0,01 € (→ False). Reverificado a mano en serie sobre
> el árbol: con el mutante, `2 failed, 67 passed`; sin él, `69 passed`.

## Anexo · campaña MANUAL sobre el SQL (no la genera `harness.mutacion`)

`harness.mutacion` solo muta Python y la lógica de F-038 vive sobre todo en SQL.
Script versionado: `progress/mutacion_sql_F-038.py` (mutantes = sustituciones de
texto exactas). Worktree desechable `git worktree add --detach` de
`47cc859a654fd7a5066231af861d8e3c7e4ff559` (el SQL no ha cambiado desde entonces),
**1 worker, en serie**, tests `test_f038_sql`, `test_f038_dominio`,
`test_f038_diccionario`, `test_f084_sql` y `test_f006_fichas` sin `-x`. Línea
base antes y después: 0 fallos (934 passed). **24 mutantes, 24 muertos, 0
supervivientes.** Columna «fallos» = nº de tests FAILED.

| Id | fichero:línea | original -> mutado | fallos |
|---|---|---|---|
| M01 | `00_setup.sql:124` | `x.c NOT IN ('A99999999', 'A00000000')` -> `x.c NOT IN ('A99999999')` | 1 |
| M02 | `00_setup.sql:128` | `WHEN x.n ~ 'CUATRIM' THEN` -> `WHEN x.n ~ 'CUATRI' THEN` | 1 |
| M03 | `00_setup.sql:114` | `'[^A-Z0-9]+', ' ', 'g'` -> `'[^A-Z]+', ' ', 'g'` | 1 |
| M04 | `00_setup.sql:125` | `'PLANIFICACION DE ESPACIOS') > 0 THEN NULL` -> `... >= 0 THEN NULL` | 1 |
| M05 | `00_setup.sql:133` | `WHEN x.c = 'A00000000' THEN 'OFICINA_TECNICA'` -> `... THEN 'OBJETIVO'` | 1 |
| M06 | `08_comparativos.sql:51` | `WHERE l.ctride > 0` (guarda) -> `WHERE l.ctride >= 0` | 1 |
| M07 | `08_comparativos.sql:53` | `HAVING count(DISTINCT l.ctride) > 1` -> `... > 2` | 1 |
| M08 | `08_comparativos.sql:84` | `COALESCE(c.est = 6, FALSE)` -> `COALESCE(c.est = 5, FALSE)` | 1 |
| M09 | `08_comparativos.sql:85` | `d.totbas::NUMERIC(18, 2)` -> `d.totdoc::NUMERIC(18, 2)` | 2 |
| M10 | `08_comparativos.sql:98` | `WHERE lp.comlinide > 0` -> `WHERE lp.comlinide >= 0` | 1 |
| M11 | `08_comparativos.sql:105` | `fn_estado_documento(12, c.est)` -> `fn_estado_documento(46, c.est)` | 1 |
| M12 | `08_comparativos.sql:127` | `FILTER (WHERE NOT o.es_ficticia) AS n_ofertas_reales` -> `FILTER (WHERE o.es_ficticia) ...` | 1 |
| M13 | `08_comparativos.sql:130` | `MIN(...) FILTER (WHERE NOT o.es_ficticia AND ` -> `MIN(...) FILTER (WHERE ` | 1 |
| M14 | `08_comparativos.sql:142` | `a.n_ofertas_ganadoras = 1` -> `a.n_ofertas_ganadoras >= 1` | 1 |
| M15 | `08_comparativos.sql:214` | `> 10 * oft.mayor_oferta` -> `> 3 * oft.mayor_oferta` | 1 |
| M16 | `08_comparativos.sql:219` | `>= 2 THEN oft.maxima_real - oft.minima_real` -> `>= 1 THEN ...` | 1 |
| M17 | `08_comparativos.sql:182` | `WHERE f.fir <> 0` -> `WHERE f.fir = 0` | 1 |
| M18 | `08_comparativos.sql:183` | `f.fec DESC NULLS LAST` -> `f.fec ASC NULLS LAST` | 1 |
| M19 | `08_comparativos.sql:225` | `CASE WHEN fi.estado_es_final THEN uf.fecha END` -> `CASE WHEN TRUE THEN uf.fecha END` | 1 |
| M20 | `08_comparativos.sql:231` | `LEFT JOIN raw.auxpronat a ON` -> `JOIN raw.auxpronat a ON` | 3 |
| M21 | `08_comparativos.sql:169` | `bool_or(f.estfin = fc.est)` -> `bool_and(f.estfin = fc.est)` | 1 |
| M22 | `08_comparativos.sql:90` | `JOIN raw.con c ON c.ide = d.ide` -> `JOIN raw.con c ON c.ide = p.ide` | 1 |
| M23 | `08_comparativos.sql:168` | `FILTER (WHERE f.fir = 0) AS n_firmas_pendientes` -> `FILTER (WHERE f.fir = 1) ...` | 1 |
| M24 | `08_comparativos.sql:237` | `ct.contrato_id = li.contrato_id` -> `ct.contrato_id = m.ide` | 1 |

**Límite declarado**: los tests leen el TEXTO del SQL, así que matan cualquier
desviación del texto esperado; no prueban que el SQL corra ni sus cifras. Eso es
MANUAL del humano tras la nocturna (T21-T23).
