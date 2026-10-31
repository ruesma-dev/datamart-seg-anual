<!-- progress/impl_F-150.md -->
# F-150 · Informe del implementer · cuarta tanda (T36-T45): personal a fin de mes y coste por contrato

Tandas anteriores: fase 1 (T1-T16) en [`impl_F-150_fase1.md`](impl_F-150_fase1.md); N11-N15
(T17-T35) en [`impl_F-150_tanda2_3.md`](impl_F-150_tanda2_3.md). Spec: R44-R52, `design.md`
§5.10-§5.11, `progress/spec_F-150.md` §11. Rama `feature/F-150-receta-caja` (desde `b98c830`), sin push.

## 1. Qué cambió (un commit por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T36 | `133a305` | Dominio: `cuota_personal`, `fuente_personal`, `pendiente_personal`, `FUENTES_PERSONAL` (R44) |
| T37 | `fa7ac48` | `07`: `_dev_personal` (partes PERSONA interna hasta el cierre, mismo filtro que `10`), cuota por partida COSTE (CP → 0), personal en el reparto; columnas en `00_setup` y fichas (R45, R46) |
| T38 | `aad4236` | Dominio: `fracciones_contrato`, `repartir_por_contratos` (R48) |
| T39 | `7026120` | `tesoreria.devengo_pendiente_contrato_mes` (00_setup + `07` §5 bis), guarda R50, `pendiente_enlazado_contrato` en el corte, ficha nueva (R49, R50) |
| T39 bis | `3efb069` | Solo los (partida, mes) con importe > 0 van a contrato: un mes negativo, entero sin contrato (§3) |
| T40 | — | Contraste de solo lectura en Azure y sandbox (§3, §4); marcada en `f79669d` |
| T41 | `9fe7ba1` | `hipotesis_caja.yaml`: H01, H02, H06 y H13; H01/H06 con el ingrediente nuevo; siguen 30 (R47, R51) |
| T42 | `a71b37c` | Receta pasos 1, 4, 5 y 6 (fuera N13-b), `R-CAJA-HIPOTESIS` (ámbito y regla), diccionario **v67** (R47, R51) |
| T43 | `f79669d` | `ARCHITECTURE.md`, `CLAUDE.md`; `azure-apps` `9488087` (local, sin push) |
| T44 | (este informe) | Mutación incremental: `progress/mutacion_F-150_n16_n17.md` |

Producción tocada: `etl_sigrid/domain/proyeccion_caja.py`, `sql/tesoreria/00_setup.sql`,
`sql/tesoreria/07_devengo_pendiente.sql`, `config/hipotesis_caja.yaml`,
`config/diccionario/{00_global,tesoreria}.yaml`. Tests nuevos: `test_f150_personal.py`,
`test_f150_contrato_compra.py`; ampliados `test_f150_{sql,receta,diccionario}.py`,
`test_f140_sql.py`, `test_f141_perfil_restringido.py`, `test_f147_presupuesto_contexto.py`.
Sin tablas de Sigrid nuevas: `raw.hmores`, `res`, `ctrpro`, `ctr` y `con` ya se ingieren.

## 2. Decisiones y desviaciones (justificadas)

1. **Redondeo por ACUMULADO** en `repartir_por_contratos` (R48 decía `ROUND(importe × f, 2)` por
   contrato): el ROUND contrato a contrato puede pasarse en céntimos (0,335 + 0,335 + 0,329 de
   1 EUR → 1,01) y dejar un resto negativo, que R48 prohíbe. Por acumulado en orden de contrato la
   suma es exacta y el resto ≥ 0 (test `..._el_round_contrato_a_contrato_dejaria_resto_negativo`).
2. **Mes negativo o cero → entero sin contrato** (T39 bis, `design.md` §5.11 paso 3 «con `np` > 0»;
   mi T39 repartía todo mes ≠ 0). Lo destapó el contraste: el 31-10 la 1-0702 (partida 387660,
   noviembre, CI) tenía −0,11 EUR en el plan de V; repartido daba 4 trozos negativos (−0,02, −0,06,
   −0,01, −0,02) y **R50 habría tumbado `build-tesoreria` esa noche**. Con la regla del diseño:
   **0 grupos negativos** (mínimo +0,13 EUR) en las 21 obras, medido en solo lectura. La guarda R50
   sigue intacta: si un día la fila SIN contrato de un grupo queda negativa, falla (sandbox §4).
3. **Línea con `can` = 0** cuenta entera como no servida (`COALESCE(..., 0)` de la segunda suma).
4. **Excepción a R18 de F-140** (`test_f140_sql.py`): `07` lee `raw.hmores` (2 veces, agregado por
   partida, igual que `10`/N14); el mart ya expone el coste real por partida. Test con su porqué.
5. Alias `cl` para `raw.ctrpro` (el test r36 caza `l.tot` sin cast: es el de `raw.dcfpro`).
6. `_dev_real` calcula los dos conceptos (antes solo VENTA); `_dev_contrato` y el hueco filtran
   `concepto = 'VENTA'` (test r23 actualizado).
7. Las fichas de las columnas nuevas entraron en T37/T39 (no en T42) para que cada commit pasara la
   puerta del diccionario; la nota de dependencia de `mart.fact_seguimiento_mensual` (F-042) en la
   ficha nueva; F-141: la tabla nueva en la lista del perfil restringido; `PRESUPUESTO_MAX`
   31.287 (+158) con su línea de historia; inventario F-006: 255 objetos (enmienda en
   `design_detalle.md`).

**PARADA (R52)**: ninguna; todas las cifras dentro del 5 % (§3).

## 3. Contraste de SOLO LECTURA en Azure (T40, 31-10, 03:30 y 04:50 UTC)

`_bootstrap_done = True` y `filas_solo_lectura`, los `SELECT` de §5.10-§5.11 sin `INSERT`.

| Pieza | Spec §11 | Medido |
|---|---|---|
| Personal del devengo, 21 obras (M EUR) | ~5,64 de 118,49 | **5,65** de 118,49 (+0,2 %) |
| Personal 0686 | ~0,21 de 2,60 | **0,21** de 2,60 |
| Partidas con cuota > 0 / a 1 / partes sin real | — | 268 / 184 / 3 |
| Coste sin CP ni personal enlazado por contrato | ~48,9 de 112,85 (43 %) | **48,90 de 112,84 (43,3 %)** |
| 0686 enlazado | ~1,64 de 2,39 (69 %) | **1,64 de 2,39 (68,6 %)** |
| 0608 y 0715 | 0 | **0** y **0** |
| Partidas con varios contratos | — | 1.371 |
| Grupos (obra, mes, cat., contrato) negativos | — | 4 con el T39; **0** con T39 bis |

Las mismas cifras con la variante `l.sql` de la spec (48,90). Sin negativos hoy en `obra_mes`.

## 4. Verificación semántica del SQL (Postgres 16 desechable, tipos reales de Azure)

`sandbox_n16_n17.py` (docker `postgres:16`, `raw` con `double precision` en importes y
cantidades, `integer` en ids y fechas, `smallint` en `res.cla`), con el dominio como oráculo:
**37 comprobaciones OK, 0 fallos**. Cuota/pendiente/fuente por partida (partes ≥ real → 1; CP → 0;
sin partes; partes sin real; proveedor, máquina y otra obra fuera; partes tras el cierre fuera),
personal por obra-mes, contrato-mes = dominio (contratos vivos 501/502/506/507; Terminado,
Rescindido, otra obra y sin condiciones fuera; línea sin partida y línea absurda > 1e8 fuera),
corte (personal 533,33, enlazado 4.006,66), suma = pendiente sin CP ni personal, **idempotente**
(2 vueltas), **mes negativo de −100** (vuelta 3: la 202 de noviembre sin trozos de contrato, la fila
sin contrato ≥ 0, todo = dominio), **guarda R50** (mes de −500: la fila sin contrato de
CD-noviembre < 0 → `RAISE` «1 importes negativos» y las filas de ayer intactas, 14) y guarda de
entrada (sin `raw.ctrpro`, falla).

## 5. Fase RED (comando exacto y salida real del fallo)

Desde la raíz del repo; trazas completas en el scratchpad de la sesión (`red_t*.txt`).

- T36 (R44): `python -m pytest tests/test_f150_personal.py -k r44 -q -p no:cacheprovider` →
  `E       NotImplementedError` … **14 failed, 1 passed, 24 deselected in 0.98s**.
- T37 (R45, R46): `python -m pytest tests/test_f150_personal.py -k "r45 or r46" -q -p no:cacheprovider` →
  `E  AssertionError: assert 'ALTER TABLE tesoreria.devengo_pendiente_partida ADD COLUMN IF NOT EXISTS
  cuota_personal NUMERIC(12,6);' in ' CREATE SCHEMA IF NOT EXISTS tesoreria; ...'` … **18 failed, 6 passed**.
- T38 (R48): `python -m pytest tests/test_f150_contrato_compra.py -k r48 -q -p no:cacheprovider` →
  `__ test_f150_r48_sin_contratos_nada_enlazado __` `E       NotImplementedError` … **21 failed, 22 deselected**.
- T39 (R49, R50): `python -m pytest tests/test_f150_contrato_compra.py -k "r49 or r50" -q -p no:cacheprovider` →
  `E       AssertionError: falta la tabla en 00_setup.sql` … **13 failed, 9 passed, 21 deselected**.
- T39 bis: `python -m pytest tests/test_f150_contrato_compra.py -q -p no:cacheprovider` →
  `E  AssertionError: assert {1: Decimal('...imal('-0.03')} == {None: Decimal('-0.11')}` /
  `E    Left contains 2 more items: {1: Decimal('-0.06'), 2: Decimal('-0.02')}` … **4 failed, 42 passed**.
- T41 (R47, R51): `python -m pytest tests/test_f150_receta.py -k "r47 or r51" -q -p no:cacheprovider` →
  `E  AssertionError: assert 'tesoreria.co...ntrato_compra' == 'tesoreria.de..._contrato_mes'` …
  **4 failed, 1 passed, 42 deselected**.
- T42 (R47, R51): `python -m pytest tests/test_f150_diccionario.py -q -p no:cacheprovider` →
  `E  AssertionError: assert 'se paga con H02 `CI`' not in ' 4. PLAZO: ...BRA) y dilo.'` …
  **8 failed, 26 passed in 8.39s**.

Tras cada implementación, las mismas órdenes en verde; antes de cada commit, las familias F-140 y
F-150 (958 passed tras T39 bis) y, tras T42, las del diccionario (F-006, F-147, F-141, F-037,
F-138, F-128, F-140, F-150): **4.745 passed, 266 skipped** (820 s).

## 6. Verificaciones MANUAL pendientes y qué falta

- **T45, redespliegue** (humano, tras APROBADO y merge): pasos con comando exacto en
  `progress/current.md`, sección «F-150 · Redespliegue MANUAL de N11-N17». Sustituye a la de
  N11-N15 (mismo despliegue; añade las cifras de N16-N17 y el diccionario v67).
- **R31** con el MCP en la 0686: personal ~0,21 a fin de mes, ~1,64 por contrato con H01, el
  resto con H02, sin H02 `CI` para el personal.
- **Para validar por el humano** (no bloquean, de la spec): las cargas sociales se pagan en
  realidad al mes siguiente (se aplica «fin de mes siempre»); la 0715 (sin partes) va por contrato
  o H02 hasta que tenga partes.
- Fuera de alcance: la caja proyectada (F-151), la caja del CP (F-154), lo contratado pendiente de
  servir que supera el devengo (15,34 M EUR: no es devengo).
- Falta: review (C1-C4 sobre T36-T44) y el despliegue.

## Evidencias

| Evidencia | Valor real |
|---|---|
| `bash harness/init.sh` | PENDIENTE_INIT |
| Tiempo de la suite | PENDIENTE_TIEMPO |
| Cobertura de las líneas cambiadas | PENDIENTE_COBERTURA |
| Mutación incremental | PENDIENTE_MUTACION |
| Verificación semántica del SQL | `07`: 37 OK, 0 fallos (Postgres 16, tipos de Azure) |
