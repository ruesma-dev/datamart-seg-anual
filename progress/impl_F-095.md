<!-- progress/impl_F-095.md -->
# F-095 · Informe del implementer (2026-09-24)

Rama `feature/F-095-retenciones-contabilidad-fin-obra` (reapuntada a `main`
249b683 con `git branch -f` antes de sacarla, sin cambiar ningun fichero del
arbol del humano). `sdd: true`, rigor `critico`. Spec aprobada:
`specs/F-095-retenciones-contabilidad-fin-obra/` + H1-H7 de
`progress/spec_F-095.md`. Un commit por tarea (`F-095 T0` ... `T20`, mas dos
ajustes `F-095:`). `main` avanzo durante el trabajo (F-108, F-109, F-107 M1-M8):
la rama NO esta rebasada; el merge lo hace el humano/lider (conflictos
previsibles solo en `harness/features.json`, `BACKLOG.md` y `progress/current.md`).

## Que cambio

**SQL nuevo** en `etl_sigrid/infrastructure/postgres/sql/retenciones/`, cuatro
sub-pasos detras de `02_views.sql` (que, como `00` y `01`, no se toca):

| Fichero | Construye | Nucleo |
|---|---|---|
| `03_apuntes_contables.sql` | `cuentas_proveedor`, `apuntes_contables` | cuentas por `prv.cueretide` (R1); un apunte por fila, `importe = hab - deb` (R3); clase CIERRE/SALDO_INICIAL/APERTURA/ALTA/BAJA por cuenta (R4-R5); `es_prescripcion` marca (R6); obra por cascada APUNTE -> FACTURA -> EFECTO -> PROVEEDOR_UNA_OBRA -> SIN_OBRA con `rac` pre-agregada y centro -> obra solo por `maestro.centros_coste` (R7-R10); PK `apunte_id`, cuenta UNIQUE |
| `04_saldo_contable.sql` | `saldo_contable` | proveedor x obra con fila sin obra (UNIQUE NULLS NOT DISTINCT), `saldo = altas + bajas + saldo_inicial`, `saldo_anterior_2016` (R11, R13) |
| `05_fin_obra.sql` | `fin_obra` | guarda `DO $$` (R21); garantia `obrctr` -> `obr` (R17); informativas en su columna con la regla de fin real de cierre replicada (D5); ultimo cierre con `ejecutado_mes <> 0` (R18); fin de obra y fuente (R19-R20); plazo `plaret` -> `plagar` -> constante 12 (R22); vencimiento = fin + plazo (R23) |
| `06_views_contables.sql` | `v_cuadre_proveedor`, `v_retencion_contable_obra` | cuadre que LEE `movimientos.estado = 'VIVA'`, FULL JOIN y 5 categorias en orden (R14-R15); estado de vencimiento al consultar (R24) |

**Propagacion**: `build_retenciones_step.py` (4 `_SubStep` + docstring; `name`,
`stage` y `depends_on` intactos); `config/tables_sigrid.yaml` (`rac` con
`where: "asiide <> 0"`, sin `tex`, sin `tiemod`); `config/diccionario/`
(`retenciones.yaml` seis fichas + la fuente que manda en `movimientos` y los 5
`v_pbi_*`; `raw.yaml` ficha `rac` y cabecera 71; `00_global.yaml` version 31,
orden de magnitud contable primero, esquema, `R-CODIGO-POR-EMPRESA` y punto 3 de
`R-SIGRID-CON`); `docs/ARCHITECTURE.md` (71 tablas y la semantica contable);
`specs/F-006-mcp-azure/design.md` (fila de inventario 172);
`azure-apps/datamart_seg_anual.md` (commit local a698815 en `azure-apps`).
`main.py`, orquestador, `apply_grants`, `settings`, `objetos_pendientes.yaml`:
sin cambios, verificado por test (R27, R29).

**Tests**: nuevo `tests/test_f095_retenciones_contables.py` (54 funciones, 66
casos con parametrizacion, offline). Tocados: `test_f066`/`test_f074`
(`TOTAL_TABLAS` 71), `test_f107` (los pines de 70 pasan a `>= 70`),
`test_f047_steps.py` (lista completa de ficheros del paso).

## Decisiones de diseno y desviaciones

Detalle y justificacion en `progress/current.md` §F-095 «Desviaciones» (8
puntos). Resumen: censo 70 -> 71 (la spec decia 68 -> 69, anterior a F-102 y
F-107); SALDO_INICIAL como anti-join (misma semantica; el `NOT EXISTS` dentro
del CASE costaba 2,7e11 en el EXPLAIN); FACTURA estricta (un efecto sin centro
cuenta como otro valor); universo del cuadre >= 1 EUR (el de H7); `empresa_id` +
`clave_obra` por R-CODIGO-POR-EMPRESA; criterio de magnitud `saldo_vivo` por
vocabulario cerrado; `apu` en el punto 3 de R-SIGRID-CON; fila de inventario en
F-006. Ademas: se probo materializar el puente centro -> obra una sola vez y se
descarto (el CTE materializado pierde estadisticas: estimacion de 1.350 M de
filas); la vista de F-073 cuesta ~1 s y se consulta cuatro veces.

## Verificaciones reales (solo lectura, contra el Postgres del `.env`)

Todo en transaccion `READ ONLY`, scripts en el scratchpad de la sesion (`f095/`):

- **EXPLAIN** de los seis SELECT (con `raw.rac` sustituida por un stub vacio,
  porque no existe aun): los seis compilan contra el catalogo real.
- **La guarda `DO $$`** ejecutada en solo lectura: pasa (la tabla del cierre
  tiene filas).
- **Apuntes y R5** (el SELECT de `03` sin la cascada, 20 s): 2.250 cuentas,
  **49.511 apuntes** (spec 49.505), saldo **8.775.052,87** (spec 8.760.524,49
  el 22-09), **0 cuentas que violen R5**, SALDO_INICIAL **72 apuntes / 642.775,50,
  todos de 2008** (exacto a la spec), apertura 2016 **1.427.463,67** (exacto),
  ALTA 26.843 / 25,71 M, BAJA 4.856 / -17,58 M, CIERRE y APERTURA 8.870 / 52,12 M
  por lado, prescrito 329.278,72.
- **Fin de obra** (el SELECT entero de `05`): 922 filas = `raw.obr`; sobre la
  viva de los efectos (8.359.284,62 hoy): INICIO_GARANTIA **46 obras / 24,3 %**,
  ULTIMO_CIERRE_MAS_1_MES **116 / 72,7 %**, sin fecha **17 obras / 132.544,84 EUR,
  9 terminadas** (identico a la spec). La spec daba 44 + 118 (20,9 + 76,1): hoy
  hay 2 obras mas con garantia. Plazo: 81 obras `plaret` (40,5 % del vivo con
  obra), 12 `plagar` (22,3 %), 86 fijo 12 (37,3 %): 93 con plazo del cliente,
  como en H2.
- No medible sin `rac`: reparto de `via_obra`, FERMALUX, categorias del cuadre.
  Son MANUAL (M4).

## Fase RED (T1, antes de escribir ningun SQL)

Comando: `python -m pytest tests/test_f095_retenciones_contables.py -q -p no:cacheprovider -W ignore`
-> **64 failed, 2 passed** (los 2 que pasaban: `d3_centros_coste_solo_raw` y
`r29_declarados_y_pendientes`, guardas de lo que ya existia). Traza de los
requisitos centrales (`--tb=line -k "r1_ or r4_ or r5_ or r7_cascada or r9_rac
or r11_saldo or r14_ or r15_categorias or r19_fin or r21_guarda or r22_plazo or
r23_vencimiento or r24_ or r27_sub"`):

```
E   FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\pgris\\PycharmProjects\\datamart-seg-anual\\etl_sigrid\\infrastructure\\postgres\\sql\\retenciones\\06_views_contables.sql'
E   AssertionError: assert ['00_setup.sq...02_views.sql'] == ['00_setup.sq...bra.sql', ...]
      Right contains 4 more items, first extra item: '03_apuntes_contables.sql'
C:\...\tests\test_f095_retenciones_contables.py:609: AssertionError
FAILED tests/test_f095_retenciones_contables.py::test_f095_r1_cuentas_por_cueretide_no_por_prefijo
FAILED tests/test_f095_retenciones_contables.py::test_f095_r4_clase_de_apunte
FAILED tests/test_f095_retenciones_contables.py::test_f095_r5_saldo_inicial_por_cuenta
FAILED tests/test_f095_retenciones_contables.py::test_f095_r7_cascada_de_obra
FAILED tests/test_f095_retenciones_contables.py::test_f095_r9_rac_declarada_con_filtro
FAILED tests/test_f095_retenciones_contables.py::test_f095_r11_saldo_sin_cierre_ni_apertura
FAILED tests/test_f095_retenciones_contables.py::test_f095_r21_guarda_cierre_vacio
FAILED tests/test_f095_retenciones_contables.py::test_f095_r19_fin_obra_y_fuente
FAILED tests/test_f095_retenciones_contables.py::test_f095_r22_plazo_y_fuente
FAILED tests/test_f095_retenciones_contables.py::test_f095_r23_vencimiento_desde_el_fin_de_obra
FAILED tests/test_f095_retenciones_contables.py::test_f095_r14_cuadre_no_recalcula_viva
FAILED tests/test_f095_retenciones_contables.py::test_f095_r15_categorias_en_orden
FAILED tests/test_f095_retenciones_contables.py::test_f095_r24_estados_de_vencimiento
FAILED tests/test_f095_retenciones_contables.py::test_f095_r27_sub_pasos_y_dependencias
14 failed, 52 deselected in 2.05s
```

Y los del YAML (`-k "r9_rac or r12_ or r28_raw"`):

```
E   AssertionError: raw.rac no esta declarada en tables_sigrid.yaml (R9)
E   AssertionError: la ficha de movimientos no dice que el saldo vivo lo manda la contabilidad (R12)
E   AssertionError: falta la ficha de raw.rac
```

VERDE: cada tarea T2-T20 cerro con sus tests en verde antes del commit (p. ej.
T6: `-k "r1_ or ... r10_"` -> 13 passed; T12: 10 passed). Dos tests se
AJUSTARON durante el verde, con motivo: `r4`/`r5` (anti-join, desviacion 2) y
`r10` (cuenta `JOIN maestro.centros_coste`, porque el COMMENT de la tabla nombra
la vista).

## Evidencias

EVIDENCIAS_PENDIENTES

## Lo que queda fuera del alcance

Cliente (4308, `cob`): F-104 (H5). F-059 retirada como absorbida (H6): es el
lider quien cambia su ficha. No se toca `01_movimientos.sql` ni `02_views.sql`
(R25), ni nada de `cierre`/`maestro`. No se construyo ni escribio nada contra la
base ni contra Sigrid.

## Lo que falta (del humano)

T23-T25 = M1-M6 de `progress/current.md` §F-095, con comandos y resultados
esperados: foto ANTES, `ingest --table rac --full`, `build-retenciones` +
`apply-grants`, las cifras (R5, FERMALUX, `via_obra`, categorias, fuentes),
`check-*`, pregunta al MCP, `publicar-diccionario` y el despliegue de la imagen.
