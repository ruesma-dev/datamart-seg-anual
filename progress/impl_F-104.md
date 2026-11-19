# F-104 · Informe del implementer (`estandar`)

Rama `feature/F-104-retenciones-cliente`. Spec aprobada con D1-D8 recomendadas (D6 = 0686),
D3 a, D9 a, D10 b, D11 a, D12 a. Commits `7ae1e00` (T1) … `516926d` (T11); `azure-apps`: `4621627`.

## Qué cambió

- **`retenciones.movimientos` CLIENTE saneado** (`01_movimientos.sql`): el estado sigue la precedencia
  de F-094 (BAJA > LIQUIDADA > VIVA, con la ficha `raw.con` del efecto), porque en `cob` el original
  agrupado se queda en `est 1` con `fecbaj` = fecha del AGR (caso 4308001150 / AGR20/0010 / 57.973,72
  en la cabecera). El universo CLIENTE es `retide <> 0` **o** `cueide` en `retenciones.cuentas_cliente`
  (entran los AGR y DIV). Dos columnas nuevas AL FINAL de las dos ramas: `origen_retencion`
  (`EFECTO_RETENCION` / `CUENTA_RETENCION`) y `cuenta_id`; `tipo_id` NULL en CLIENTE sin tipo; índice
  `idx_ret_mov_cuenta`. PROVEEDOR no cambia de filas ni de estado (sandbox R9).
- **`retenciones.cuentas_cliente`** (nueva, en `01`, antes de `movimientos`): `cli.cueretide` ∪ 43x8 de
  `con.tip = 17`, PK `cuenta_id` y guarda DO que tumba el build si sale vacía (R4, R5).
- **`08_saldo_cliente.sql`** (nuevo, último sub-paso `saldo_cliente`): `saldo_contable_cliente` (desde
  `raw.apu`, `deb - hab`, la misma clase de apunte que `03`) y `v_cuadre_cliente` (la `categoria` de
  `v_cuadre_proveedor`). LA MANDA LA CONTABILIDAD.
- **`ventas/06b_retencion_cliente.sql`** (nuevo, sub-paso `retencion_cliente` entre `restringida` y
  `guardas`): guarda R33 (antes de borrar nada), `ventas.retencion_factura` (con `motivo`),
  `ventas.retencion_cuenta` y `ventas.v_retencion_cliente`. Lee `retenciones` de la misma noche por
  POSICIÓN en `run-all`; `depends_on` sin cambios (documentado en el docstring del step).
- **Diccionario v80**: fichas de los seis objetos, `movimientos` con sus dos columnas y textos de estado,
  `entidad_cif` (D9), órdenes de magnitud de cliente (16,0 M contabilidad / 10,5 M efectos / 3.461 filas),
  nota de versión, R-VENTAS-TRES-CIFRAS sin «hasta F-104». **326 objetos, 2819 columnas, 163 de consumo.**
- Textos: `ventas.yaml` (cabecera, `v_factura_cobro`, `cobertura_enlace`), frontera y viñeta de cliente
  en `docs/ARCHITECTURE.md`, comentario RETENCIONES de `config/tables_sigrid.yaml`, docstrings de
  `build_retenciones_step.py`, `build_ventas_step.py` y `main.py`.
- **`azure-apps/datamart_seg_anual.md`**: sección «Retención de cliente saneada y conciliada» y la
  frontera de F-040 cumplida. Commit `4621627` en `main` de `azure-apps` (tras `git pull --rebase`, sin
  conflicto). **Sin push.**

## Ficheros

- SQL: `retenciones/01_movimientos.sql`, `retenciones/08_saldo_cliente.sql` (nuevo),
  `ventas/06b_retencion_cliente.sql` (nuevo).
- Steps: `build_retenciones_step.py` (SUB_PASOS + docstring), `build_ventas_step.py`; `main.py` (docstring).
- Diccionario: `retenciones.yaml`, `ventas.yaml`, `00_global.yaml`. Docs: `ARCHITECTURE.md`,
  `config/tables_sigrid.yaml`, `specs/F-006-mcp-azure/design_detalle.md` (enmienda, inventario 326).
- Tests nuevos: `test_f104_retenciones_cliente.py`, `test_f104_ventas_retencion.py`, `test_f104_sandbox.py`.
- Tests adaptados (enumeran sub-pasos, ficheros, objetos o cifras que F-104 cambia a propósito):
  `test_f094_retenciones_estado.py` (el de `fecrea` pasa a `..._usa_la_ficha_del_efecto_desde_f104`),
  `test_f040_frontera.py` (TOCADOS_DESPUES + 01 y 08), `test_f040_pipeline.py`, `test_f040_sql.py`,
  `test_f040_sandbox.py` (06b fuera de esa sandbox), `test_f040_diccionario.py` (19 → 22 objetos),
  `test_f047_steps.py`, `test_f095_retenciones_contables.py`, `test_f110_fin_obra_cuatrimestral.py`,
  `test_f128_sql.py` (cuadre_factura pasa a penúltimo), `test_f006_reglas.py` (21,9 M → 10,5 M),
  `test_f147_presupuesto_contexto.py` (tope 37.356 → 37.914, SUBIDO con su motivo: seis fichas de
  consumo con una pregunta cada una).

## Decisiones y desviaciones (justificadas también en `progress/current.md`)

1. CTE `prefijo` de `cuentas_cliente` con alias `pc` en vez de `cue`: el guardián R2 de F-006 lee
   `FROM raw.con cue` como proyección directa de `raw` y acusaba a `codigo_cuenta`/`nombre_cuenta`, que
   sí pueden ser NULL (llegan por LEFT JOIN). Mismo SQL, otro alias.
2. `tipo_id` sin `nulo_significa`: lo prohíbe `test_f006_r2_los_filtros_que_pierden_filas_se_declaran`
   (la rama PROVEEDOR proyecta `p.retide` en crudo). El NULL de CLIENTE se explica en `significado`.
3. `cuentas_cliente` es de consumo (`consumo_recomendado: true`), no de preparación: evita meterla en el
   inventario de no-consumo de F-079 y es lo que un agente pregunta («la cuenta de retención de C»).
4. Relación `cuentas_cliente.cliente_id → ventas.clientes` `N:1` (el validador R5 rechazó `1:1`).
5. T2 y T3 tocan el mismo fichero: un solo commit `F-104 T2-T3`. El cambio de alias del test de R4 entró
   por error en `bca5c22` (un `commit -a` de la nota de current.md); es una línea, se deja así.
6. T10 (mutación, INFORMATIVA en `estandar`): hecha en la pasada de campaña tras el APPROVED (abajo).
   T11 es MANUAL del humano (comandos en `progress/current.md`).

## Fase RED (T1, antes de escribir SQL)

Comando: `.venv/Scripts/python.exe -m pytest tests/test_f104_retenciones_cliente.py
tests/test_f104_ventas_retencion.py tests/test_f104_sandbox.py -q --tb=line` (con `F104_SANDBOX_DSN`):

```
FFFFFFFFFFFFFFFFFFF...FFFFFFFFFFFFFFFFFFFFFFFFEEEEEEEEEEEE               [100%]
E   FileNotFoundError: [Errno 2] No such file or directory: '...\sql\retenciones\08_saldo_cliente.sql'
tests\test_f104_retenciones_cliente.py:160: assert "CASE WHEN CO...IQUIDADA' END" == "CASE WHEN CO...SE 'VIVA' END"
tests\test_f104_retenciones_cliente.py:173: AssertionError: COALESCE(efe.fecbaj, 0) = 0
tests\test_f104_retenciones_cliente.py:179: AssertionError: 4308001150
tests\test_f104_retenciones_cliente.py:110: AssertionError: falta «CREATE TABLE retenciones.cuentas_cliente AS»
FAILED tests/test_f104_retenciones_cliente.py::test_f104_r1_estado_de_cliente_con_la_precedencia_de_f094
FAILED tests/test_f104_retenciones_cliente.py::test_f104_r2_vencida_solo_si_viva_en_cliente
FAILED tests/test_f104_retenciones_cliente.py::test_f104_r4_cuentas_cliente_es_la_union_de_cueretide_y_43x8
FAILED tests/test_f104_retenciones_cliente.py::test_f104_r6_el_universo_de_cliente_incluye_las_cuentas
ERROR tests/test_f104_sandbox.py::test_f104_sandbox_r33_sin_cuadre_de_cliente_falla_antes_de_borrar
43 failed, 3 passed, 12 errors in 9.82s
```

Los 3 que ya pasaban en RED comprueban lo que F-104 NO debe cambiar (la traza `-q` no los nombra).
Tras el código, en verde: `46 passed` (estáticos) y `12 passed` (sandbox).

## T9 · sandbox (PostgreSQL 16 local desechable, `raw` sintético con tipos reales `double precision`)

`F104_SANDBOX_DSN=postgresql://postgres@127.0.0.1:55104/postgres pytest tests/test_f104_sandbox.py -v`
→ **12 passed in 1.23s**: unión de cuentas (CUERETIDE y PREFIJO_43X8), AGR con originales en `est 1` +
`fecbaj` → BAJA, DIV vivo `CUENTA_RETENCION`, PROVEEDOR intacto, saldo con apertura sin cierre previo,
las cinco `categoria`, los cinco `motivo` (RETESP a 4308 sin efecto → SIN_EFECTO; efecto vivo sin
documento → `viva_sin_factura`), `diferencia_sin_explicar`, vistas PBI que siguen construyendo, y las
tres guardas (cuentas vacías, dos clientes con la misma cuenta, `06b` sin `retenciones`).

## Tests afectados (antes de la puerta)

Batería de F-104 + todos los ficheros que enumeran sub-pasos, diccionario, F-006, F-079, F-147 y F-003:
`1 failed, 1941 passed, 2421 skipped en 11 min 38 s`; el fallo era `test_f040_r30` por
`08_saldo_cliente.sql` aún sin seguimiento en git, y tras el commit `4 passed`.

## Salida de `init.sh`

Precondición (2026-11-19, `bca5c22`, sin código de F-104): rojo TRANSITORIO en
`test_f052_r28_el_marcador_llega_a_la_consulta_que_se_envia_de_verdad`: powershell.exe salió con
3221225794 (0xC0000142, STATUS_DLL_INIT_FAILED, no llegó a arrancar) con el puesto cargado por otra
suite. El líder lo repitió solo (17 passed en `tests/test_f052_marcador.py`) y decidió no repetir la puerta.
Antes, `init2` cayó por un GUID de sesión que yo había dejado en `current.md` (`test_f003`): corregido
en `bca5c22`.

Puerta final (2026-11-19, sobre `7e7376f`): **`bash harness/init.sh` EXIT 0, todo [OK]**:
`13620 passed, 2549 skipped, 2787 warnings in 9762.75s (2:42:42)`; `PUERTA COBERTURA: N/A (F-104: las
líneas cambiadas no contienen sentencias ejecutables)`; `PUERTA TAMAÑO` dentro de topes (impl 132/220);
`PUERTA CARRIL: N/A (estandar)`; `CAPA E2E: N/A`. Sin repetir de 0xC0000142 en esta pasada.

## Pendiente

- T11 MANUAL (humano): build, comprobaciones de R20, R21, R35 y R37,
  `publicar-diccionario` con la imagen del job y reinicio de `mcp-bbdd`; push de la rama y de
  `azure-apps` (`4621627`) por el humano.
- Fuera de alcance (spec): atribuir lo cobrado por un AGR a facturas (D11), repartir el saldo contable
  por obra (D5), corregir en Sigrid la ficha de UNEXUM (4308001593 frente a 4338001593).

## T10 · pasada de campaña: mutación manual (2026-11-19, sobre `e51e692`, código aprobado)

Por qué manual y no `python -m harness.mutacion --feature F-104`: la herramienta muta solo las líneas
Python que cambia la feature, y las de F-104 son docstrings y tuplas de `SUB_PASOS` (la puerta da la
cobertura N/A por eso); los tres puntos que pide la spec están en SQL. Es la «mutación manual
documentada» que prevé T10. Script: un mutante cada vez sobre el fichero real, se corren
`tests/test_f104_sandbox.py` (PG16 local) y los dos ficheros estáticos de F-104 por separado, y se
restaura (árbol limpio al terminar, `git status` sin cambios). Base: `58 passed in 4.53s`.

| Id | Mutante | Sandbox | Estáticos |
|---|---|---|---|
| E1 | CLIENTE: BAJA sin `fecbaj` (solo `est` 14/15) | muerto | muerto |
| E2 | CLIENTE: BAJA sin el `est` 15 | muerto | muerto |
| E3 | CLIENTE: LIQUIDADA sin `est` 10 | muerto | muerto |
| E4 | CLIENTE: LIQUIDADA evaluada antes que BAJA | **vive** | muerto |
| U1 | R4: prefijo sin `tip = 17` | muerto | muerto |
| U2 | R4: `^43[0-9]` en vez de `^43[0-9]8` | muerto | muerto |
| U3 | R4: declaradas con `cueretide >= 0` | muerto | **vive** |
| U4 | R4: `LEFT JOIN` en vez de `FULL JOIN` (sin la unión) | muerto | muerto |
| U5 | R6: `OR` → `AND` en el universo de CLIENTE | muerto | muerto |
| M1 | R28: tolerancia de CUADRA 0,01 → 1000 | muerto | muerto |
| M2 | R28: SIN_EFECTO solo si `retencion > 0` | **vive** | muerto |
| M3 | R28: EFECTO_SIN_RETENCION con `num_efectos > 1` | muerto | muerto |
| M4 | R28: DIFIERE con `num_efectos >= 0` | muerto | muerto |

Totales: **13 generados, 13 muertos por la batería de F-104, 0 supervivientes.** Por capa, informativo:
la sandbox sola mata 11 (E4: no hay efecto con `fecbaj` Y `fecrea`/`est 10` a la vez; M2: no hay
factura con retención NEGATIVA sin efecto) y los estáticos solos 12 (U3: fijan el texto de la unión,
no el `<> 0` de `cueretide`; lo mata la sandbox con su cliente de `cueretide = 0`). No son
equivalentes, pero cada uno lo caza la otra capa: no se ha tocado código de producción.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests de F-104 | 46 estáticos + 12 sandbox, todos en verde |
| Suite completa (puerta final) | 13.620 passed, 2.549 skipped, 0 failed (puerta final) |
| Cobertura de las líneas cambiadas | N/A según `PUERTA COBERTURA`: las líneas Python cambiadas son docstrings y tuplas de `SUB_PASOS`, sin sentencias ejecutables; el SQL lo cubren los 46 + 12 tests de F-104 |
| Mutación (T10, manual, informativa) | **13 mutantes, 13 muertos, 0 supervivientes** con los tests de F-104 (ver «T10» abajo) |
| Tiempo de la suite | 2 h 42 min 42 s (9.762,75 s, con el puesto compartido con otras suites) |
| Capa e2e | N/A (línea `CAPA E2E` de `init.sh`: sin `harness/servicios.json`) |
