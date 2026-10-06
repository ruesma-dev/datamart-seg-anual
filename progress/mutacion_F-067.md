<!-- progress/mutacion_F-067.md -->
# F-067 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-067` el 2026-10-06 18:28.

## Alcance

Origen del diff: **rama** (`ba9e8300cc944012362de30e60ff9a8c005131c2` .. `feature/F-067-compras-seguimiento-mcp`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 33 |
| `etl_sigrid/domain/historial_estados.py` | 202 |
| **Total** | **235** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 50 |
| Mutantes evaluados | 50 |
| Muertos | 44 |
| Supervivientes | 5 |
| Timeouts | 1 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 15340.2 s |
| SHA de HEAD medido | `d088327029b1b38f29cad6595e9d2056f9b1f060` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-067_4eq5fkmd/wk_0` | 1099.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-067_4eq5fkmd/wk_1` | 1088.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-067_4eq5fkmd/wk_2` | 1098.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-067_4eq5fkmd/wk_3` | 1087.8 |
| Media por mutante evaluado (s) | 306.8 |
| Timeout efectivo por mutante (s) | 1800 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 1800 |
| Workers | 4 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/historial_estados.py:121` [comparacion]

- Original: `if n_abiertos > 0 and len(vigentes) < UMBRAL_PRESENCIA * n_abiertos:`
- Mutado:   `if n_abiertos >= 0 and len(vigentes) < UMBRAL_PRESENCIA * n_abiertos:`

#### Análisis

> Por qué ningún test lo caza: es EQUIVALENTE. Con `n_abiertos == 0` la otra
> mitad es `len(vigentes) < 0`, que nunca se cumple, así que `> 0` y `>= 0` dan
> lo mismo para toda entrada.
> Decisión: se quita la condición redundante en `d698881` (`if len(vigentes) <
> UMBRAL_PRESENCIA * n_abiertos:`, comentado); el mutante deja de existir y los
> de la línea nueva (`<=`, `//`...) mueren (`progress/mutacion_dominio_F-067.py`,
> 17/45 y 18/45). El SQL mantiene `v_abiertos > 0 AND` por legibilidad.

### 2. `etl_sigrid/domain/historial_estados.py:121` [entero]

- Original: `if n_abiertos > 0 and len(vigentes) < UMBRAL_PRESENCIA * n_abiertos:`
- Mutado:   `if n_abiertos > 1 and len(vigentes) < UMBRAL_PRESENCIA * n_abiertos:`

#### Análisis

> Por qué ningún test lo caza: hueco REAL. Ningún caso tenía exactamente UN
> tramo abierto y cero documentos; con `> 1` esa ingesta vacía no paraba.
> Decisión: test nuevo `test_f067_r6_con_un_solo_tramo_abierto_tambien_hay_guarda`
> (`d698881`). Aplicado a mano sobre el código de `d088327`: 1 fallo, ese test.
> La línea cambió después (superviviente 1) y su mutante ya no existe.

### 3. `etl_sigrid/domain/historial_estados.py:125` [aritmetico]

- Original: `f"menos del {UMBRAL_PRESENCIA * 100} %. No se toma la foto."`
- Mutado:   `f"menos del {UMBRAL_PRESENCIA // 100} %. No se toma la foto."`

#### Análisis

> Por qué ningún test lo caza: el test de la guarda solo comprobaba que el
> mensaje llevara 979 y 1000, no el porcentaje.
> Decisión: el mensaje formatea `f"{UMBRAL_PRESENCIA:.0%}"` (sin aritmética que
> mutar) y el test exige `"menos del 98%."` (`d698881`). Re-verificado: 0
> supervivientes en la línea.

### 4. `etl_sigrid/domain/historial_estados.py:125` [entero]

- Original: `f"menos del {UMBRAL_PRESENCIA * 100} %. No se toma la foto."`
- Mutado:   `f"menos del {UMBRAL_PRESENCIA * 101} %. No se toma la foto."`

#### Análisis

> Por qué ningún test lo caza: el mismo que el 3 (`* 101` da 98.98 y el test
> no miraba el porcentaje).
> Decisión: la misma que el 3 (`d698881`).

### 5. `etl_sigrid/domain/historial_estados.py:173` [comparacion]

- Original: `1 for t in tramos if t.hasta == observado_en and t.motivo_cierre == _CAMBIO`
- Mutado:   `1 for t in tramos if t.hasta == observado_en and t.motivo_cierre != _CAMBIO`

#### Análisis

> Por qué ningún test lo caza: hueco REAL. El único test de contadores tenía UN
> cambio y UN desaparecido: contar «cerrados que no son CAMBIO» daba el mismo 1.
> Decisión: test nuevo `test_f067_r8_cambios_y_desaparecidos_se_cuentan_por_separado`
> (3 cambios, 1 desaparecido, 2 altas; `d698881`). Aplicado a mano: 1 fallo.
> Re-verificado 28/45 y 30/45 en `progress/mutacion_dominio_F-067.py`.

## Timeouts

Análisis del timeout: el mismo hueco que el superviviente 5, del lado
DESAPARECIDO (con un cambio y un desaparecido, `!= _DESAPARECIDO` contaba el
cambio: mismo 1). El timeout de 1.800 s es de la máquina con 4 workers, no un
bucle. Lo mata el test nuevo del 5: 32/45 y 34/45 en la re-verificación.

- `etl_sigrid/domain/historial_estados.py:176` [comparacion] 1 for t in tramos if t.hasta == observado_en and t.motivo_cierre == _DESAPARECIDO -> 1 for t in tramos if t.hasta == observado_en and t.motivo_cierre != _DESAPARECIDO

## Re-verificación del dominio tras cerrar los supervivientes (`d698881`)

`progress/mutacion_dominio_F-067.py` (versionado): genera los mutantes con el
MISMO generador (`harness.mutacion.generar_mutantes`, TODAS las líneas de
`domain/historial_estados.py`) y los evalúa contra `test_f067_dominio`,
`test_f067_sql` y `test_f006_dataclasses_inmutables` —un subconjunto de la
suite: lo que muere aquí muere con la suite entera—. 1 worker, en serie, sobre
el árbol de `d698881` y restaurando el fichero. **45 mutantes, 45 muertos, 0
supervivientes**; línea base antes y después: 0 fallos (276 passed, 3
skipped). No se repitió la campaña completa (~4 h con la suite entera por
mutante); el reviewer puede relanzarla con `python -m harness.mutacion
--feature F-067 --timeout 1800 --workers 4`.

## Anexo · campaña MANUAL sobre el SQL (no la genera `harness.mutacion`)

Script versionado: `progress/mutacion_sql_F-067.py` (40 sustituciones de texto
exactas). Worktree desechable `git worktree add --detach` de
`cc8113ad5499622eabda245bd39fa33c3113e396`, **1 worker, en serie**, tests
`test_f067_sql`, `test_f067_dominio`, `test_f067_diccionario`, `test_f084_sql`,
`test_f083_sql`, `test_f047_steps`, `test_f097_descompuestos`,
`test_f120_factor`, `test_f123_origenes` y `test_f006_fichas`, sin `-x`;
`test_f073_sql` FUERA a propósito (su hash de `01_documentos.sql` mataría todo
mutante de ese fichero sin decir nada de los tests de F-067). Línea base antes
y después: 0 fallos (1197 passed, 223 skipped). **40 mutantes, 40 muertos, 0
supervivientes.** La primera pasada (sobre `57a2940`) dejó vivo M21
(`NOT h.es_linea_base`): el test buscaba la proyección con `in` y la cadena
mutada la contenía; ahora compara el elemento exacto (`cc8113a`). Columna
«fallos» = nº de tests FAILED.

| Id | fichero:línea | original -> mutado | fallos |
|---|---|---|---|
| M01 | `compras/00_setup.sql:174` | `"TIMESTAMP '1899-12-30' + v"` -> `"TIMESTAMP '1900-01-01' + v"` | 1 |
| M02 | `compras/00_setup.sql:174` | `'CASE WHEN v > 0 THEN TIMESTAMP'` -> `'CASE WHEN v >= 0 THEN TIMESTAMP'` | 1 |
| M03 | `compras/00_setup.sql:174` | `"+ v * INTERVAL '1 day' END"` -> `"+ floor(v) * INTERVAL '1 day' END"` | 1 |
| M04 | `compras/11_historial_estados.sql:81` | `'IF v_obs IS NULL OR v_obs <= v_ult THEN'` -> `'IF v_obs IS NULL OR v_obs < v_ult THEN'` | 1 |
| M05 | `compras/11_historial_estados.sql:91` | `'v_actual < 0.98 * v_abiertos'` -> `'v_actual < 0.9 * v_abiertos'` | 1 |
| M06 | `compras/11_historial_estados.sql:92` | `"RAISE EXCEPTION 'F-067: raw.con trae"` -> `"RAISE NOTICE 'F-067: raw.con trae"` | 1 |
| M07 | `compras/11_historial_estados.sql:89` | `'SELECT count(*) INTO v_actual FROM raw.con c WHERE c.tip IN (44, 15);'` -> `'SELECT count(*) INTO v_actual FROM raw.con c;'` | 1 |
| M08 | `compras/11_historial_estados.sql:103` | `'AND  c.est IS DISTINCT FROM h.estado_id;'` -> `'AND  c.est <> h.estado_id;'` | 1 |
| M09 | `compras/11_historial_estados.sql:102` | `'AND  c.tip = h.tipo_documento_codigo\n      AND  c.est'` -> `'AND  c.est'` | 1 |
| M10 | `compras/11_historial_estados.sql:113` | `'WHERE  c.ide = h.documento_id AND c.tip = h.tipo_documento_codigo\n'` -> `'WHERE  c.ide = h.documento_id\n'` | 1 |
| M11 | `compras/11_historial_estados.sql:109` | `"SET    hasta = v_obs, motivo_cierre = 'DESAPARECIDO'"` -> `"SET    hasta = v_obs, motivo_cierre = 'CAMBIO'"` | 2 |
| M12 | `compras/11_historial_estados.sql:124` | `'v_obs, NULL, v_ult, (v_ult IS NULL), NULL'` -> `'v_obs, NULL, v_ult, TRUE, NULL'` | 1 |
| M13 | `compras/11_historial_estados.sql:124` | `'v_obs, NULL, v_ult, (v_ult IS NULL), NULL'` -> `'v_obs, NULL, NULL, (v_ult IS NULL), NULL'` | 1 |
| M14 | `compras/11_historial_estados.sql:126` | `'WHERE  c.tip IN (44, 15)\n      AND  NOT EXISTS'` -> `'WHERE  c.tip IN (44, 15, 46)\n      AND  NOT EXISTS'` | 1 |
| M15 | `compras/11_historial_estados.sql:129` | `'WHERE  h.documento_id = c.ide AND h.hasta IS NULL\n'` -> `'WHERE  h.documento_id = c.ide\n'` | 1 |
| M16 | `compras/11_historial_estados.sql:138` | `'v_insertados - v_cambios, v_desaparecid'` -> `'v_insertados, v_desaparecid'` | 1 |
| M17 | `compras/11_historial_estados.sql:46` | `'CREATE TABLE IF NOT EXISTS compras.historial_estados ('` -> `'DROP TABLE IF EXISTS compras.historial_estados;\nCREATE TABLE compras.historial_estados ('` | 4 |
| M18 | `compras/11_historial_estados.sql:59` | `'CREATE UNIQUE INDEX IF NOT EXISTS ux_hist_est_abierto'` -> `'CREATE INDEX IF NOT EXISTS ux_hist_est_abierto'` | 1 |
| M19 | `compras/11_historial_estados.sql:169` | `'est ON TRUE\nWHERE h.hasta IS NULL;'` -> `'est ON TRUE;'` | 1 |
| M20 | `compras/11_historial_estados.sql:161` | `"((now() AT TIME ZONE 'Europe/Madrid')::date"` -> `'((now())::date'` | 1 |
| M21 | `compras/11_historial_estados.sql:160` | `'h.es_linea_base                                    AS antiguedad_es_minima'` -> `'NOT h.es_linea_base                                AS antiguedad_es_minima'` | 1 |
| M22 | `compras/11_historial_estados.sql:154` | `"WHEN 44 THEN 'CONTRATO' WHEN 15 THEN 'FACTURA'"` -> `"WHEN 15 THEN 'CONTRATO' WHEN 44 THEN 'FACTURA'"` | 1 |
| M23 | `compras/11_historial_estados.sql:169` | `'compras.fn_estado_documento(h.tipo_documento_codigo, h.estado_id)'` -> `'compras.fn_estado_documento(44, h.estado_id)'` | 1 |
| M24 | `compras/01_documentos.sql:153` | `"AND x.cod LIKE 'RET%'"` -> `"AND x.cod LIKE 'RE%'"` | 1 |
| M25 | `compras/01_documentos.sql:154` | `'ORDER  BY r.pos, r.ide'` -> `'ORDER  BY r.ide'` | 1 |
| M26 | `compras/01_documentos.sql:155` | `'    LIMIT  1\n) ret ON TRUE;'` -> `') ret ON TRUE;'` | 1 |
| M27 | `compras/01_documentos.sql:148` | `'ROUND((r.valpor * 100)::NUMERIC, 4)'` -> `'ROUND((r.valpor)::NUMERIC, 4)'` | 1 |
| M28 | `compras/01_documentos.sql:130` | `'LEFT JOIN raw.auxpag pag  ON'` -> `'JOIN raw.auxpag pag  ON'` | 2 |
| M29 | `compras/01_documentos.sql:122` | `'compras.fn_sigrid_tiempo(con.tiemod)'` -> `'compras.fn_sigrid_date(con.fec)'` | 1 |
| M30 | `compras/01_documentos.sql:118` | `'NULLIF(c.pagide, 0)                     AS forma_pago_id'` -> `'c.pagide                                AS forma_pago_id'` | 2 |
| M31 | `compras/01_documentos.sql:247` | `"AS importe_pendiente_facturar,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.\n    NULLIF(btrim(l.cod2), '')"` -> `'AS importe_pendiente_facturar,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.\n    l.cod2                   '` | 2 |
| M32 | `compras/01_documentos.sql:333` | `"AS contrato_id_directo,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.\n    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»\n    NULLIF(l.dncide, 0)"` -> `"AS contrato_id_directo,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.\n    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»\n    NULLIF(l.dncproide, 0)"` | 1 |
| M33 | `compras/01_documentos.sql:181` | `'AS necesidad_id,        -- dnc: el DPC\n    NULLIF(l.dncproide, 0)                  AS necesidad_linea_id   -- dncpro\nFROM raw.ctrpro l'` -> `'AS necesidad_id,        -- dnc: el DPC\n    NULLIF(l.dncide, 0)                     AS necesidad_linea_id   -- dncpro\nFROM raw.ctrpro l'` | 1 |
| M34 | `compras/01_documentos.sql:262` | `'compras.albaran_lineas (necesidad_linea_id);'` -> `'compras.albaran_lineas (necesidad_id);'` | 1 |
| M35 | `compras/10_necesidades.sql:31` | `'COALESCE(o.dncide = d.ide, FALSE)'` -> `'COALESCE(o.dncide = d.obride, FALSE)'` | 1 |
| M36 | `compras/10_necesidades.sql:42` | `') nl ON nl.dncide = d.ide;'` -> `') nl ON nl.dncide = d.obride;'` | 1 |
| M37 | `compras/10_necesidades.sql:34` | `'JOIN raw.con c            ON c.ide = d.ide'` -> `'JOIN raw.con c            ON c.ide = d.obride'` | 1 |
| M38 | `compras/10_necesidades.sql:32` | `'COALESCE(nl.n, 0)'` -> `'nl.n'` | 1 |
| M39 | `descompuestos/06_views.sql:56` | `"n.ide = lineas.dncpro_id) AS necesidad_id\nFROM descompuestos.lineas WHERE origen = 'PLANIF_JO';"` -> `"n.ide = lineas.producto_id) AS necesidad_id\nFROM descompuestos.lineas WHERE origen = 'PLANIF_JO';"` | 1 |
| M40 | `descompuestos/06_views.sql:67` | `"(SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) AS necesidad_id\nFROM descompuestos.lineas WHERE origen = 'MASTER_PLANIF_JO';"` -> `"(SELECT NULLIF(n.ide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) AS necesidad_id\nFROM descompuestos.lineas WHERE origen = 'MASTER_PLANIF_JO';"` | 2 |

**Límite declarado**: los tests leen el TEXTO del SQL; matan cualquier
desviación del texto esperado pero no prueban que el SQL corra ni sus cifras.
Eso es MANUAL tras el despliegue (T17-T20 de `tasks.md`).
