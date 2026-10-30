<!-- progress/impl_F-150.md -->
# F-150 · Informe del implementer · segunda y tercera tanda (T17-T35)

La fase 1 (T1-T16, el arreglo del despliegue del 29-10, su RED y sus evidencias) está en
[`impl_F-150_fase1.md`](impl_F-150_fase1.md); la PARADA de T11, en `impl_F-150_parada_T11.md`.
Este informe cubre el ajuste del 29-10 (N11-N13), el saldo de partida (N14) y el IVA con
inversión del sujeto pasivo (N15). Rama `feature/F-150-receta-caja`, sin push.

## 1. Qué cambió (un commit por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T17 | `1b3e96a` | Dominio: `neto_fifo`, `SERIES_ALBARAN_PENDIENTE`, `UMBRAL_IMPORTE_ABSURDO` (R33) |
| T18 | `5864298` | `tesoreria.albaranes_pendientes_neto` (00_setup + `09_albaranes_pendientes.sql`), sub-paso `albaranes_pendientes` (R34, R35) |
| T19 | `98b050e` | `07`: cuota CP de la cartera de pago (`cartera_viva_coste_proporcional`, `cartera_emitida_tras_cierre_coste_proporcional`) (R36) |
| T20 | `3389999` | Contraste de solo lectura en Azure de `09` y de la cuota CP; la vista de partidas `MATERIALIZED` (205 s → 10 s) |
| T21 | `6f227ac` | YAML: H02 sin `CP`; H20/H27 con los albaranes netos (N11, N12) |
| T22 | `ea73489` | Diccionario v64: receta, ficha nueva, CP fuera, personal por el recurso (R3, R4, R34, R36, R37) |
| T23 | `514e965` | ARCHITECTURE, CLAUDE.md; `azure-apps` `c57c52e` |
| T27 | `23ad2bd` | `PASOS_RECETA` con `SALDO` delante (ocho); H28 y H29 (R39) |
| T28-T29 | `ac3b1b2` | `tesoreria.saldo_partida_obra` (00_setup + `10_saldo_partida.sql`), sub-paso `saldo_partida`, ficha, inventario 254, presupuesto F-147 31.129; contraste (R38) |
| T30 | `ea47886` | Receta paso 0 SALDO y paso 7 con los originales; regla; recuentos 29 derivados del YAML en los tests; v65; `azure-apps` `d3cafe9` (R40) |
| T32 | `500a4ea` | H13 SIGRID por obra: `iva_efectivo_compra`, `UMBRAL_BASE_H13`, `MOTIVO_H13_COMPRAS`, rama en `08` (R41) |
| T33 | `1c84fd9` | H30 (defecto `MENSUAL_REDEME`, decisión del humano) y la spec corregida (R42) |
| T34 | `34639c6` | El IVA del saldo (6 columnas), receta paso 0 y 6, fichas, v66; `azure-apps` `3ca37bf` (R43) |
| T24/T31/T35 | (este informe) | Mutación incremental, `init.sh` y pasos MANUAL (en `current.md`) |

Ficheros de producción tocados: `etl_sigrid/domain/proyeccion_caja.py`,
`etl_sigrid/application/steps/build_tesoreria_step.py`, `sql/tesoreria/00_setup.sql`, `07`, `08`,
`09_albaranes_pendientes.sql` (nuevo), `10_saldo_partida.sql` (nuevo), `config/hipotesis_caja.yaml`,
`config/diccionario/{00_global,tesoreria,compras}.yaml`. Tests nuevos: `test_f150_albaranes.py`,
`test_f150_saldo.py`, `test_f150_iva_isp.py`; ampliados los de F-037, F-140, F-147 y F-150.

## 2. Decisiones y desviaciones (justificadas)

1. **Decisión del humano (29-10), N15**: H30 por defecto `MENSUAL_REDEME` (vuelve a los 4 meses del
   mes liquidado; mediana de la 4700), `validado: false`; el saldo suma el IVA NETO recuperado
   (soportado − repercutido). La spec decía `COMPENSA_EMPRESA`: corregida en `requirements.md` R42/R43,
   `design.md` §5.9 y §6 y `spec_F-150.md` §10.6 (T33). El defecto es un dato del YAML: ni el SQL ni
   el dominio lo nombran (test `test_f150_r43_el_sql_no_elige_h30`).
2. **Columnas `_hasta_4m`** (desviación de §5.9, que solo traía `_hasta_4t`): sin ellas
   `MENSUAL_REDEME` no se puede aplicar. Pagado o cobrado en un mes 4 o más meses antes del mes del
   build (aritmética de meses con `date_part`, sin `interval`).
3. **Columna extra `agrupados_vencidos_coste_proporcional`**: la parte CP de los originales vencidos
   va aparte para que, con H29 = `AGR`, el CP del saldo siga siendo exacto. Fórmula de la receta: CP
   = `pagado_coste_proporcional` (+ esa columna con `ORIGINALES`).
4. **Paso 0**: la receta numera SALDO como 0 (los pasos 1-7 conservan su número). El tramo del
   SALDO nombra también H30 (el IVA recuperado): el test r2 lo admite de forma explícita.
5. **H13, 12 meses sin aritmética de fechas** (el test de F-140 la prohíbe en `08`):
   `fn_fecha(c.fec) <= CURRENT_DATE AND date_part('year', age(CURRENT_DATE, fn_fecha(c.fec))) = 0`.
   La medida `ROUND(100 * x.cuota / x.base, 2)` es la segunda cuenta tolerada en `08` (como el ×100
   de H12): mide un porcentaje, no aplica una hipótesis. El motivo dice «entre» y no «/» por eso.
6. `09`: el `COMMENT` va en `09` y no en `00_setup`; `tras_cierre` con `COALESCE(..., FALSE)`; la
   vista de partidas como CTE `MATERIALIZED` (también en `10`).
7. **Recuentos de hipótesis**: los tests leen la cifra del YAML (`_n_hipotesis()`) en vez de repetir
   27/29/30. **Inventario F-006**: enmienda en `design_detalle.md` (254 objetos); el guardián pasaba
   antes por coincidencia de subcadena.
8. El `init.sh` inicial de esta sesión se saltó (verde en `289fedb`, urgencia del líder); el final sí.
9. Lint: corregidos los avisos de ruff de mis ficheros (`zip(strict=True)`, signos «−»/«×»).

**PARADA**: ninguna. Las cifras de T29 y T34 están dentro del 5 % (§3).

## 3. Contrastes de SOLO LECTURA en Azure

**T20 (N11-N12, 29-10)**: 30.533 líneas; bruto 56,876 M EUR, sobrefacturado 48,166, compensado
48,120, **neto 8,756** (= el de compras), 3.356 filas, 20 obras; 0686 bruto 8,781 neto 0,193;
>6 meses 0,518; `tras_cierre` 0,470 en 7 obras. Cartera viva 38,560; CP prorrateado −0,0037 (~0).

**T29 (N14, 30-10)**, frente a §10.5 (29-10):

| Pieza | 21 obras (spec / medido) | 0686 (spec / medido) |
|---|---|---|
| Cobrado REALIZADO | 97,4 / **98,30** (+0,9 %) | 30,21 / **30,21** |
| Pagado sin AGR | 64,0 / **63,99** | 21,96 / **21,96** |
| AGR con obra | 2,2 / **2,22** | 0,32 / **0,32** |
| Originales vencidos / pendientes | 8,63 / 2,21 · **8,63 / 2,21** | 1,32 / 0,27 · **1,32 / 0,27** |
| Personal de los partes | 11,55 / **11,65** (+0,9 %) | 2,07 / **2,13** |
| CP de lo pagado | ~0 / −0,117 | — / −0,102 |

La nocturna del 30-10 movió el último cierre de la 0686 (y otras) a 2026-10: por eso el personal
incluye octubre (0686 +0,065). Saldo con H28 `CON_SALDO`, H29 `ORIGINALES`, sin IVA: **21 obras
13,91 M EUR (spec 13,18) y 0686 4,70 (4,86)**: la diferencia es el cobro nuevo, el personal de
octubre y el CP, no el método.

**T32 (H13, 30-10)**: **16 de 21 obras** con valor SIGRID (0608, 0690, 0699, 0715, 0724 bajo el
umbral); **0686 2,37 %** (2,36 el 29-10); toda la base 146,52 M EUR, 5,33 % (spec 150,10 / 5,46).
Observación: 0704 7,52 % (spec 8,33) y 0710 4,13 (4,55): no lo explica la ventana de fechas
(probado con tres comienzos); quedan fuera del contraste pactado.

**T34 (IVA del saldo, 30-10)**, frente a §10.6: soportado **4,141** M EUR (spec 4,14; 0686 **0,800**,
spec 0,80); pagado antes de 2026 **1,424** (1,42; 0686 **0,437**, 0,44); repercutido **0,338**
(0,34; 0686 0,016). `_hasta_4m`: soportado 3,051, repercutido 0,259 (0686 0,676 y 0,016).

**El saldo, recalculado (decisión del humano)**:

| Saldo de partida (M EUR) | 21 obras | 0686 |
|---|---|---|
| Spec §10.6 con `COMPENSA_EMPRESA` (base 29-10) | ~16,98 | ~5,64 |
| Medido 30-10 con `COMPENSA_EMPRESA` (todo el IVA neto: +3,803 / +0,784) | **17,71** | **5,49** |
| Medido 30-10 con **`MENSUAL_REDEME`** (defecto; `_hasta_4m`: +2,792 / +0,660) | **16,70** | **5,36** |
| `MENSUAL_REDEME` sobre la base de la spec (13,18 / 4,86) | 15,97 | 5,52 |

Lo que `MENSUAL_REDEME` deja fuera (1,01 M EUR en 21 obras, 0,12 en la 0686) es el IVA de los
últimos meses aún no devuelto: caja futura, no saldo.

## 4. Verificación semántica del SQL (Postgres 16 desechable, tipos reales de Azure)

`raw` con `double precision` en importes e `integer` en ids y fechas. `09` (sandbox N11): 23
comprobaciones, 0 fallos. `10` (`sandbox_n14.py`): **14 comprobaciones, 0 fallos**: universo
COSTE (la obra solo VENTA fuera), cada columna con su filtro (incluida una BAJA de otro estado y un
AGR antiguo que no cuentan), cuota CP 0,75 y 0,5, personal (proveedor, otra clase y sin obra
fuera; hasta el cierre; obra sin cierre a 0), el IVA (pago de hoy ni `_4t` ni `_4m`; original de
2000 y cobro de 2020 en los dos), idempotente en dos vueltas y la guarda (sin `raw.res`, falla sin
vaciar). El docker se paró al terminar.

## 5. Fase RED (comando exacto y salida real del fallo)

Trazas completas en el scratchpad de la sesión; aquí el comando y el resumen real de pytest.

- T17: `pytest tests/test_f150_albaranes.py -k r33` con `neto_fifo` como stub →
  `E       NotImplementedError` … **17 failed in 2.26s**.
- T18: `pytest tests/test_f150_albaranes.py -k "r34 or r35"` →
  `E       AssertionError: falta la tabla en 00_setup.sql` … **15 failed, 12 passed, 17 deselected**.
- T19: `pytest tests/test_f150_albaranes.py tests/test_f150_sql.py -k r36` →
  `E  AssertionError: assert 'ALTER TABLE tesoreria.devengo_corte_obra ADD COLUMN IF NOT EXISTS
  cartera_viva_coste_proporcional NUMERIC(18,2);' in ...` … **7 failed, 25 passed**.
- T21: `pytest tests/test_f140_hipotesis.py tests/test_f150_receta.py` →
  `E  AssertionError: assert 'compras.v_pb..._sin_facturar' == 'tesoreria.al...ndientes_neto'` … **4 failed, 176 passed**.
- T22: `pytest tests/test_f150_diccionario.py` →
  `E  AssertionError: tesoreria.albaranes_pendientes_neto` … **9 failed, 8 passed**.
- T27: `pytest tests/test_f150_receta.py tests/test_f150_saldo.py -k "r1 or r39"` →
  `E       AssertionError: assert 'DEVENGO' == 'SALDO'` … **4 failed**.
- T28: `pytest tests/test_f150_saldo.py -k r38` →
  `FAILED ...::test_f150_r38_setup_crea_la_tabla_con_sus_columnas` … **11 failed, 14 passed**.
- T30: `pytest tests/test_f150_diccionario.py tests/test_f140_diccionario.py tests/test_f150_sql.py
  tests/test_f150_receta.py tests/test_f150_albaranes.py` →
  `FAILED ...::test_f150_r40_el_paso_0_da_la_formula_del_saldo` … **12 failed, 235 passed**.
- T32: `pytest tests/test_f150_iva_isp.py` →
  `FAILED ...::test_f150_r41_el_umbral_y_el_motivo - AttributeError` … **18 failed in 0.99s**.
- T33: `pytest tests/test_f150_receta.py tests/test_f140_hipotesis.py tests/test_f140_paso.py
  tests/test_f140_sql.py` → `FAILED ...::test_f150_r42_h30_cuando_vuelve_el_iva_a_devolver` …
  **7 failed, 355 passed**.
- T34: `pytest tests/test_f150_saldo.py tests/test_f150_diccionario.py` →
  `FAILED ...::test_f150_r43_la_fraccion_de_iva_de_cada_factura` … **14 failed, 56 passed**.

Tras cada implementación, las mismas órdenes en verde; antes de cada commit, las familias del
diccionario (F-006, F-147), F-037, F-140 y F-150: **1.991 passed, 262 skipped** (T34, 739 s).

## 6. Verificaciones MANUAL pendientes y qué falta

- **Redespliegue** (humano): pasos con comando exacto en `progress/current.md`, sección «F-150 ·
  Redespliegue MANUAL de N11-N15». Incluye `build-tesoreria` (sub-pasos 09 y 10 nuevos), las cifras
  a comprobar, `publicar-diccionario` v66, los `check-*` y el reinicio del MCP.
- **R31** con el MCP: la 0686 con y sin saldo, H13 2,37 %, H30 declarada.
- **Para validar por el humano y AdP**: H30 (`validado: false`) y H13 por obra.
- Fuera de alcance: la caja del CP (F-154); la caja proyectada (F-151); `R-ALBARAN-ABSURDO`.
- Falta: review (C1-C4 sobre T17-T35) y despliegue.

## Evidencias

PENDIENTE_EVIDENCIAS
