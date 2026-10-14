<!-- progress/impl_F-037.md -->
# F-037 · Informe del implementer (fase 1: la cartera de cobros y pagos)

Rama `feature/F-037-tesoreria` (desde `22f6209`). Rigor **crítico**. Spec aprobada entera
(D1-D11 con la A). Fecha: 2026-10-13. Un commit por tarea (`F-037 T1` … `F-037 T11`).

## Qué cambió

| Tarea | Ficheros | Qué |
|---|---|---|
| T1 | `etl_sigrid/domain/tesoreria.py` (nuevo) | Oráculo: `EfectoTesoreria`, `motivo_restriccion_efecto` (NATURALEZA > CUENTA > CUENTA_SIN_RESOLVER > TERCERO_EMPLEADO > DOCUMENTO_NOMINA), `es_efecto_restringido`, `estado_tesoreria`, `importe_flujo`, `fecha_limite_previsto_antiguo`, `es_previsto_antiguo`. Importa `REGEX_CUENTA_RESTRINGIDA` y `es_cuenta_restringida` de F-135 (no copia) |
| T2 | `sql/tesoreria/00_setup.sql`, `01_efectos_completo.sql` | Dos esquemas, `fn_fecha`/`fn_serie` (copias de compras), tres tablas `IF NOT EXISTS` con PK e índices; la completa = `UNION ALL` pag/cob, sin `WHERE`, dos CTE (`efectos` y `marcados`: el estado y el motivo se calculan UNA vez) |
| T3 | `02_efectos_general.sql`, `03_efectos_restringidos_mes.sql` | General `WHERE NOT restringido`, remesa mixta a NULL, guarda `DO` (criterio recalculado desde `raw` + recuentos); recuentos sin importes |
| T4 | `application/steps/build_tesoreria_step.py` (nuevo), `main.py` | Paso `build_tesoreria` (`build_aux`, `["ingest_raw"]`) entre maestros y compras; comando `build-tesoreria`; docstrings de `run-all` («ocho build») |
| T5 | `sql/compras/05_vencimientos.sql` | De tabla a VISTA de `tesoreria.efectos` (`PAGO` y `es_factura_compra`), `DO` que borra tabla o vista por `relkind`, `COMMENT ON VIEW` con las dos trampas |
| T6 | `config/settings.py`, `.env.example` | `tesoreria` en consumo; `tesoreria_restringida` en vetados y restringidos |
| T7 | — (solo tests) | `apply_grants` ya es de listas (design §6): ningún cambio de código |
| T8 | `infra/sql/02_roles.sql` | Crea los dos esquemas como `sigrid_dm_etl`, `tesoreria` en el bucle, `tesoreria_restringida` en los dos vetos al estándar (NO al total), concesión y privilegio por defecto al autorizado, comprobaciones finales |
| T9 | `config/diccionario/tesoreria.yaml`, `tesoreria_restringida.yaml` (nuevos), `compras.yaml`, `00_global.yaml`, `domain/diccionario.py` | 5 fichas, `vencimientos` como vista, dos esquemas, `R-TESORERIA-ESTADO`, `R-TESORERIA-RESTRINGIDA` (hermana), `R-FRESCURA` ampliada, **versión 51** |
| T10 | `docs/ARCHITECTURE.md`, `CLAUDE.md`, `azure-apps/datamart_seg_anual.md`, `azure-apps/mcp_bbdd.md` | Capas, roles, quince pasos, contrato de lista blanca. **`azure-apps` commit local `a781704`, sin push** |
| T11 | `tests/test_f037_paso.py` | Tests para el guardián `target_schema AND target_table` y la duración; campaña de mutación |

Tests nuevos: `tests/test_f037_{dominio,sql,paso,grants,diccionario}.py`. Adaptados SIN cambiar
lo que comprueban (listas que crecen): `test_f006_{frescura,publicacion,formato,reglas,fichas*}`,
`test_f024_cli`, `test_f047_nocturna`, `test_f056`, `test_f057`, `test_f080_sql`,
`test_f097`, `test_f135_grants`, `test_f136_login_total`. Doc histórico:
`specs/F-006-mcp-azure/design_detalle.md` (enmienda con el inventario 217/1795/104, lo exige
`test_f006_r24`).

## Decisiones de diseño y desviaciones (justificadas)

1. **`tesoreria.fn_fecha` copia el cuerpo de `compras.fn_sigrid_date`** (la spec dice «fn_fecha
   copiada de compras», pero en compras se llama `fn_sigrid_date`; el nombre `fn_fecha` es el de
   los demás esquemas módulo). El test compara cuerpos.
2. **`01` usa el alias `p` para el efecto en las DOS ramas** (`raw.pag p` / `raw.cob p`): así las
   expresiones de F-080 se copian tal cual y un test las fija igual en las dos ramas.
3. **Dos CTE en `01`** (`efectos` → `marcados`): `previsto_antiguo` lee `estado_tesoreria` y
   `restringido` lee `motivo_restriccion`; no pueden discrepar.
4. **El estado lee `fecrea`/`fecbaj` CRUDOS** (`fecrea_efecto`, `fecbaj_efecto`, no publicados):
   `fn_fecha` da NULL a una fecha inválida y el estado no puede depender de eso.
5. **`centro_coste_id` = `NULLIF(cenide, 0)`** aunque el centro no resuelva (igual que F-080); la
   obra sí sale NULL. Así `compras.vencimientos` no cambia.
6. **`efectos_restringidos_mes`**: además de año/mes 0, `empresa_id` 0 si faltara (hoy 0 casos).
7. **`compras.vencimientos.paso_etl` sigue `build_compras`** (el objeto lo crea ese paso y
   `test_f006_r14` lo exige para todo `compras`); la ficha dice que su frescura es la de
   `build_tesoreria`, y `R-FRESCURA` también.
8. **Regla hermana `R-TESORERIA-RESTRINGIDA`** en vez de ampliar `R-CONTABILIDAD-RESTRINGIDA`
   (design lo dejaba al implementer): el título de la contable dice «Usa contabilidad;» y
   `test_f136` lo fija.
9. **`test_f047_steps.py` no se toca** (tasks lo citaba): su tabla exige `stage == name`, y el paso
   usa `build_aux` como contabilidad. La lista de quince pasos vive en `test_f047_nocturna.py`,
   `test_f006_frescura.py` y `test_f006_publicacion.py`, que sí se actualizan; el paso tiene sus
   tests en `test_f037_paso.py`.
10. **Ejemplos de «esquema inexistente»** en `test_f006_formato`/`test_f006_reglas` usaban
    `tesoreria`; pasan a `flujo_caja` (anotado en el docstring).
11. **`test_f136_r32_version_50`** pasa de `== 50` a `>= 50` («al menos», lección de F-073/F-080).
12. Sin guarda de recuento contra `raw` en `01` (no la pide la spec): el `JOIN raw.con c` de F-080
    dejaría fuera un efecto sin ficha; medido hoy 0 (T12: 256.952 + 21.914 = raw).

**Incidente sin daño**: un `git stash`/`stash pop` de comprobación (para medir ruff) sacó un
stash antiguo de otra rama y dejó conflicto en `BACKLOG.md` y `features.json`; se restauraron
con `git checkout HEAD --` y el stash sigue intacto en `stash@{0}`. Nada se perdió.

## Fase RED (trazas reales, comando exacto)

T1 — sin el módulo, y luego con el esqueleto de firmas (`NotImplementedError`):
```
$ python -m pytest tests/test_f037_dominio.py -q -p no:cacheprovider
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.tesoreria'
1 error in 0.32s
# con el esqueleto:
FAILED tests/test_f037_dominio.py::test_f037_r1_sin_nada_no_es_de_personal - ...
FAILED tests/test_f037_dominio.py::test_f037_r1_naturaleza_sola[1] - NotImple...
FAILED tests/test_f037_dominio.py::test_f037_r1_cuenta_sola[4753] - NotImplem...
67 failed, 5 passed in 1.27s
```
T2 — sin `00_setup.sql` ni `01_efectos_completo.sql`:
```
$ python -m pytest tests/test_f037_sql.py -q -p no:cacheprovider -k "r2 or r5 or r6 or r7 or r8 or r9 or r14 or funciones"
     28 E       AssertionError: SQL no encontrado: ...\sql\tesoreria\00_setup.sql
     21 E       AssertionError: SQL no encontrado: ...\sql\tesoreria\01_efectos_completo.sql
49 failed, 7 deselected in 1.50s
```
T3:
```
$ python -m pytest tests/test_f037_sql.py -q -p no:cacheprovider -k "r10 or r11 or r12 or r13"
FAILED tests/test_f037_sql.py::test_f037_r11_la_remesa_mixta_pierde_su_importe
FAILED tests/test_f037_sql.py::test_f037_r12_la_guarda_recalcula_el_criterio_desde_raw
FAILED tests/test_f037_sql.py::test_f037_r13_solo_recuentos_de_los_restringidos
13 failed, 3 passed, 59 deselected in 0.80s
```
T4 (sin `build_tesoreria_step.py`):
```
$ python -m pytest tests/test_f037_paso.py -q -p no:cacheprovider
ERROR tests/test_f037_paso.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.46s
```
T5 (con el `05` de F-080, la tabla, en su sitio; el nombre del test se pasó luego a minúsculas):
```
$ python -m pytest tests/test_f037_sql.py tests/test_f080_sql.py -q -p no:cacheprovider -k "r15 or r16 or r7_los or r8_la_vista"
FAILED tests/test_f037_sql.py::test_f037_r15_la_vista_publica_la_lista_de_f080
FAILED tests/test_f037_sql.py::test_f037_r15_los_tipos_de_la_general_son_los_de_f080
FAILED tests/test_f037_sql.py::test_f037_r16_borra_tabla_o_vista_segun_relkind
FAILED tests/test_f080_sql.py::test_f080_r7_los_vencimientos_son_una_VISTA_de_la_cartera_de_f037
8 failed, 4 passed, 205 deselected in 0.35s
```
T6:
```
$ python -m pytest tests/test_f037_grants.py -q -p no:cacheprovider -k settings
E       AssertionError: assert 'tesoreria' in ['mart', 'cierre', 'compras', 'maestro', 'retenciones', 'personal', ...]
E       AssertionError: assert 'contabilidad_restringida,raw' == 'contabilidad...stringida,raw'
3 failed, 1 passed in 0.85s
```
T7 (no hay código nuevo: RED con el `settings.py` de antes de T6):
```
$ python -m pytest tests/test_f037_grants.py -q -p no:cacheprovider -k "r21"
FAILED tests/test_f037_grants.py::test_f037_r21_el_estandar_recibe_tesoreria_y_se_le_veta_la_restringida
FAILED tests/test_f037_grants.py::test_f037_r21_el_total_sin_grant_propio_lee_la_restringida_y_no_raw
4 failed, 2 passed, 4 deselected, 10 warnings in 0.91s
```
T8:
```
$ python -m pytest tests/test_f037_grants.py tests/test_f135_grants.py -q -p no:cacheprovider -k "r22 or r20"
FAILED tests/test_f037_grants.py::test_f037_r22_la_restringida_vetada_al_estandar_con_los_dos_concedentes
FAILED tests/test_f135_grants.py::test_f135_r20_los_vetados_son_los_de_settings_y_con_dos_concedentes
7 failed, 11 passed, 38 deselected in 1.04s
```
T9 (con el diccionario de antes: sin fichas, versión 50, sin los dos esquemas):
```
$ python -m pytest tests/test_f037_diccionario.py -q -p no:cacheprovider -k "not docs"
FAILED tests/test_f037_diccionario.py::test_f037_r25_regla_del_estado - Asser...
FAILED tests/test_f037_diccionario.py::test_f037_r26_regla_hermana_de_la_contable
18 failed, 1 passed, 2 deselected in 10.50s
```
Todas en verde después (resultado real en «Evidencias»).

## T12 · Contraste de SOLO LECTURA contra Azure (2026-10-13 15:08 UTC)

`main._get_pg()`, `_bootstrap_done = True`, `filas_solo_lectura` (transacción READ ONLY). El
`SELECT` de `01` sin `INSERT`, con `compras.fn_sigrid_date`/`compras.fn_serie` en lugar de las
funciones de `tesoreria` (cuerpos idénticos, test; no existen aún en Azure). Solo agregados.

| Medida | Resultado | Esperado (spec) |
|---|---|---|
| PAGO / COBRO en la completa | 256.952 / 21.914 (= `raw.pag` / `raw.cob`) | 256.952 / 21.914 ✓ |
| Restringidos (todos NATURALEZA) / cobros restringidos | 37.053 / 0 | 37.053 / 0 ✓ |
| BAJA / REALIZADO / PREVISTO pagos; cobros | 89.779 / 147.410 / 19.763; 8.548 / 12.349 / 1.017 | ✓ |
| Con obra: pagos / cobros | 200.143 / 17.102 | ✓ |
| `previsto_antiguo` no personal: pagos / cobros | 2.361 (3,89 M€) / 398 (2,20 M€) | 2.361 (3,9) / 398 (2,2) ✓ |
| PREVISTO no personal: pagos / cobros | 80,09 M€ / 40,20 M€ | 80,1 / 40,2 ✓ |
| General; `PAGO`+factura en la general; `compras.vencimientos` hoy | 241.813; 197.190; 197.190 | R16 ✓ |
| Guarda R12 recalculada desde `raw` sobre la general | 0 | 0 ✓ |
| Remesas mixtas (efectos visibles; de factura) | 1 (7; 6) | 1 ✓ |
| Vista frente a la tabla de F-080 (`EXCEPT` en los dos sentidos) | 6 / 6 = los 6 de la remesa mixta; sin el NULL de D8, 0 / 0 | D8 ✓ |
| `efectos_restringidos_mes`: filas / suma | 928 / 37.053 (57 efectos sin vencimiento → año/mes 0) | ✓ |
| `efecto_id` repetidos | 0 | 0 ✓ |

Tiempos de lectura: 3,5-15 s por consulta; la guarda recalculada, 40 s (estimación de su coste
en el build: del orden de decenas de segundos).

## Verificaciones MANUAL pendientes (no ejecutables por un agente)

- **T13** despliegue (design §7, en ese orden): job sin `PG_*_SCHEMAS` fijadas; imagen fechada y
  tag del job; `02_roles.sql`; `build-tesoreria` (anotar duración, R29) → `build-compras` →
  `apply-grants`.
- **T14** prueba negativa con el login estándar (`permission denied` en
  `tesoreria_restringida.efectos`; 0 con `naturaleza_pago_id` en `tesoreria.efectos`), positiva con
  el total (= `raw.pag` + `raw.cob`), R16 (197.190) y R30 en la base desplegada.
- **T15** `publicar-diccionario` (v51), `check-diccionario`, `check-declarados`, `check-unicidad`;
  reiniciar el MCP; avisar a `mcp-bbdd` del contrato (lista blanca).
- **T16** al día siguiente: `apply_grants` SUCCESS con `verificacion = ok` y la negativa repetida.

## Qué queda fuera

Fase 2 (devengo de obra, plazos, retención de contrato); ventas (F-040); la duda de las bajas de
cobro con retención (19,9 M€, declarada); `mcp-bbdd` (lista blanca) y el rol de Power BI (F-087).

## Evidencias

Medidas el 2026-10-14. `init.sh` vuelve a correr sobre `2abde26` tras la campaña repetida, con todo commiteado.

| Evidencia | Resultado real |
|---|---|
| `bash harness/init.sh` (sobre `2abde26`) | **ENTORNO LISTO** (salida 0): todas las puertas en `[OK]`; ruff, 271 avisos de deuda previa |
| Tests ejecutados (suite completa, dentro de `init.sh`) | **7.826 passed, 242 skipped, 0 failed** |
| Tiempo de la suite | **1.014 s (16 min 54 s)** con medición de cobertura (antes, 1.144 s) |
| Tests de la feature | `test_f037_{dominio,sql,paso,grants,diccionario}.py`: 72 + 96 + 19 + 16 + 23 = 226 passed |
| Cobertura de líneas cambiadas | **PUERTA COBERTURA: 100,0 % de 136 líneas (136/136)**, umbral 80 %, nivel crítico |
| Tamaño | requirements 149/150, design 249/250, impl 216/220, review 139/140 |
| Mutación (`domain/tesoreria.py` + `build_tesoreria_step.py`, campaña completa) | **45 generados, 45 muertos, 0 supervivientes, 0 timeouts, 0 sin veredicto**: informe VÁLIDO |

**Mutación, ciclo de corrección de la review pasada 1** (detalle en `progress/mutacion_F-037.md`).
La primera campaña (`--workers 4`) salió **NO VÁLIDA**: la línea base de cierre agotó 12.000 s
porque la campaña cruzó una suspensión de la máquina (23.686 s en total). Se repitió **sin tocar
código** y con el mismo alcance:
`python -m harness.mutacion --feature F-037 --ficheros etl_sigrid/application/steps/build_tesoreria_step.py,etl_sigrid/domain/tesoreria.py --workers 2 --timeout 2400`.
Se lanzó desacoplada de la sesión y con `SetThreadExecutionState` para que el equipo no se
suspendiera (sin `powercfg`). Corrió de 00:46 a 02:50 UTC del 14-10, salida 0, y el informe sale
**sin la cabecera «⚠ CAMPAÑA NO VÁLIDA»**:

| Métrica | Valor |
|---|---|
| Generados / evaluados / muertos | 45 / 45 / 45 |
| Supervivientes / timeouts / base rota | 0 / 0 / 0 |
| SHA de HEAD medido | `b475edb` (= HEAD al lanzar; después solo cambian `progress/`) |
| Tiempo total | 7.428,3 s (2 h 04 min), 2 workers |
| Línea base por worker | 490,6 s y 491,3 s |
| Media por mutante | 165,1 s (× 2 workers = 330 s, por debajo de la base: cada mutante corre con `-x` y se corta en el primer fallo, mientras que la base corre la suite entera) |
| Timeout por mutante | 2.400 s, con `--timeout` (sin el flag la base tendría 120 × 5 = 600 s, justos para ~490 s) |

`--timeout 2400` es el mismo de la primera campaña. Sin él, la base habría corrido con 600 s de
margen y medía ~490 s. Los 2 `timeout` de la primera campaña (`tesoreria.py:192` y `:193`) salen
ahora **muertos**: eran efecto de la suspensión. Como dijo la primera reverificación en serie, los
3 mutantes de las banderas `slots`/`frozen` de `@dataclass` los mata la guarda genérica
`tests/test_f006_dataclasses_inmutables.py`. Ningún superviviente que analizar.
