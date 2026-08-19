<!-- progress/impl_F-024.md -->
# F-024 · Coherencia del datamart ante cargas truncadas — Informe de implementación (Fase B, T5–T16)

**Rama**: `feature/F-024-coherencia-cargas-truncadas`. **Rigor**: `critico`.
**Alcance**: Fase B completa (T5–T16). T1–T4 ya estaban cerradas por el humano
y el líder; **T17–T20 son de Fase C y NO se han ejecutado**: exigen BBDD y
Azure reales, y ningún agente abre esas conexiones.

---

## 1 · Qué cambió, en una frase

El pipeline pasa de «construye con lo que haya» a «acredita de qué carga viene
cada tabla, o se niega». Ninguna transacción larga nueva: la coherencia se
gana por **verificación** (dos puertas antes de escribir) y **visibilidad**
(identidad de ejecución, estado honesto en `_meta`, dos vistas consultables y
una alerta externa).

---

## 2 · Ficheros tocados

### Creados

| Fichero | Qué es |
|---|---|
| `etl_sigrid/domain/ejecucion.py` | `Ejecucion`, `nueva_ejecucion`, `MOTIVO_HUERFANA`. Dominio puro. |
| `etl_sigrid/domain/coherencia.py` | `EstadoTablaRaw`, `EstadoPaso`, `VeredictoCoherencia`, `evaluar_coherencia_raw/stg`, `formatear_veredicto_raw/stg`. Dominio puro. |
| `etl_sigrid/infrastructure/postgres/frescura.py` | `FilaFrescura`, `format_frescura`, `format_estado_raw`, `UMBRAL_FRESCURA_HORAS`. |
| `infra/95_create_alert_frescura.ps1` | Alerta de frescura (regla de consulta programada). UTF-8 BOM + CRLF. |
| `tests/test_f024_dominio.py` | R1, R4 (vocabulario), R8, R9, R15 (dominio). |
| `tests/test_f024_steps.py` | R3, R10, R11 (step), R12, R15. |
| `tests/test_f024_cli.py` | R3, R4, R5, R7, R11 (opción), R14, R18, R19. |
| `tests/test_f024_meta_y_formato.py` | R2, R6, R13, R16, R19 (formato), R20. |
| `tests/test_f024_infra_alerta.py` | R21 (los dos extremos), R22. |

### Modificados

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/domain/entities.py` | `StepStatus.ABORTED`. |
| `.../postgres/sql/ddl/00_meta.sql` | `batch_id` + índice (idempotentes), vistas `_meta.v_raw_state` y `_meta.v_frescura`. |
| `.../postgres/postgres_client.py` | `batch_id` opcional en `record_run_start`/`record_run_completed`; `abortar_runs_huerfanos`, `fetch_estado_raw`, `fetch_ultimo_intento_stg`, `fetch_frescura`; SQL en constantes de módulo. |
| `.../postgres/step_run_recorder.py` | `batch_id` opcional; se propaga a la fila de paso. |
| `.../postgres/timings.py` | `format_timings(timings, ahora)`, `UMBRAL_HUERFANA_HORAS`, aviso al pie (R6). |
| `.../steps/ingest_raw_step.py` | `batch_id` → fila de cada tabla. |
| `.../steps/build_stg_step.py` | `batch_id`, `omitir_puerta`, `_puerta_raw` antes del pre-flight. |
| `.../steps/build_mart_step.py` | `batch_id`, `omitir_puerta`, `_puerta_stg` antes del primer SQL. |
| `main.py` | `_arrancar_ejecucion`, `_ejecutar_paso`, comandos migrados, `--sin-puerta`, `check-coherencia`, `check-frescura`. |
| `infra/env/dev.json` | `frescuraUmbralHoras` (30), `frescuraAlertName`, su `$aviso_frescura`. |
| `infra/00_vars.ps1` | Las dos claves nuevas pasan a obligatorias. |
| `infra/README.md` | Fila del script 95, sección de prueba de la alerta, sección de diagnóstico, y **corrección de `ContainerAppName_s` → `ContainerJobName_s`**. |
| `docs/ARCHITECTURE.md` | Sección «Coherencia ante cargas truncadas (F-024)» + corrección de DA-8. |
| `tests/test_f003_infra.py` | Conoce las dos claves nuevas (obligatoria y nombre de recurso). |
| `tests/test_f019_tramos.py` | Dobles actualizados a la firma real del cliente. |
| `tests/test_f016_huecos_alto_f005.py` | Doble de `apply-grants` con cliente. |
| `azure-apps/datamart_seg_anual.md` (otro repo) | Lo que exponemos: las dos vistas, la alerta, la puerta. Commit `aba68fa`. |

---

## 3 · Fase RED (obligatoria en `critico`): trazas reales

Todos los tests se escribieron ANTES del código. Estas son las salidas reales
del fallo, con el comando exacto.

### T5 · `domain/ejecucion.py` y `StepStatus.ABORTED`

```
$ python -m pytest tests/test_f024_dominio.py -q
tests\test_f024_dominio.py:21: in <module>
    from etl_sigrid.domain.ejecucion import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.ejecucion'
=========================== short test summary info ===========================
ERROR tests/test_f024_dominio.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.30s
```

Segunda RED, ya de comportamiento, tras crear el módulo y **antes** de tocar
`StepStatus` (se dejó a propósito para no quedarse en el fallo de importación):

```
$ python -m pytest tests/test_f024_dominio.py -q
>       assert StepStatus.ABORTED.value == "ABORTED"
E       AttributeError: type object 'StepStatus' has no attribute 'ABORTED'
tests\test_f024_dominio.py:151: AttributeError
FAILED tests/test_f024_dominio.py::test_f024_r1_el_instante_inyectado_manda_sobre_el_reloj
FAILED tests/test_f024_dominio.py::test_f024_r1_dos_ejecuciones_iguales_son_iguales
FAILED tests/test_f024_dominio.py::test_f024_r4_aborted_es_parte_del_vocabulario_de_estados
3 failed, 6 passed, 505 warnings in 0.18s
```

**La fase RED cazó un error mío**, que es exactamente para lo que sirve: dos de
esos tres fallos eran literales equivocados en el TEST (olvidé la `Z` del
formato `YYYYMMDDTHHMMSSZ`), no en el código:

```
>       assert ejecucion.batch_id == "20260818T020005-0f1e2d"
E       AssertionError: assert '20260818T020005Z-0f1e2d' == '20260818T020005-0f1e2d'
E         - 20260818T020005-0f1e2d
E         + 20260818T020005Z-0f1e2d
E         ?                +
```

Escrito el test después, habría «ajustado» el valor esperado sin enterarme de
que el formato publicado no era el que yo creía.

### T6 · `domain/coherencia.py`

```
$ python -m pytest tests/test_f024_dominio.py -q
tests\test_f024_dominio.py:28: in <module>
    from etl_sigrid.domain.coherencia import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.coherencia'
ERROR tests/test_f024_dominio.py
1 error in 0.42s
```

### T7 · DDL de `_meta`

```
$ python -m pytest tests/test_f024_meta_y_formato.py -q
E       Failed: no hay ninguna sentencia que defina _meta.v_raw_state
FAILED tests/test_f024_meta_y_formato.py::test_f024_r2_ddl_meta_migra_sin_destruir
FAILED tests/test_f024_meta_y_formato.py::test_f024_r2_batch_id_admite_nulos
FAILED tests/test_f024_meta_y_formato.py::test_f024_r13_vista_raw_state_definida_en_el_ddl
FAILED tests/test_f024_meta_y_formato.py::test_f024_r16_vista_frescura_columnas_y_or_replace
FAILED tests/test_f024_meta_y_formato.py::test_f024_r16_frescura_separa_ultimo_ok_de_ultimo_intento
FAILED tests/test_f024_meta_y_formato.py::test_f024_r16_frescura_solo_mira_pasos_de_pipeline
FAILED tests/test_f024_meta_y_formato.py::test_f024_r16_las_horas_se_calculan_en_utc
FAILED tests/test_f024_meta_y_formato.py::test_f024_r16_ninguna_vista_de_meta_lee_de_otra_capa
8 failed, 2 passed in 0.44s
```

### T8 · Cliente Postgres

```
$ python -m pytest tests/test_f024_meta_y_formato.py -q
tests\test_f024_meta_y_formato.py:32: in <module>
    from etl_sigrid.infrastructure.postgres.frescura import FilaFrescura
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.postgres.frescura'
ERROR tests/test_f024_meta_y_formato.py
1 error in 0.27s
```

### T9 · Formatos (`timings` y frescura)

```
$ python -m pytest tests/test_f024_meta_y_formato.py -q
tests\test_f024_meta_y_formato.py:37: in <module>
    from etl_sigrid.infrastructure.postgres.frescura import (
E   ImportError: cannot import name 'MARCA_INCOHERENTE' from
    'etl_sigrid.infrastructure.postgres.frescura'
ERROR tests/test_f024_meta_y_formato.py
1 error in 0.30s
```

### T10 · Puerta de `raw` en `build_stg`

```
$ python -m pytest tests/test_f024_steps.py -q
E       TypeError: BuildStgStep.__init__() got an unexpected keyword argument 'batch_id'
tests\test_f024_steps.py:173: TypeError
FAILED tests/test_f024_steps.py::test_f024_r10_puerta_ko_no_toca_stg_y_falla
FAILED tests/test_f024_steps.py::test_f024_r10_ningun_raw_incoherente_llega_a_construir[falta una tabla-estados0]
FAILED tests/test_f024_steps.py::test_f024_r10_ningun_raw_incoherente_llega_a_construir[una en RUNNING-estados1]
FAILED tests/test_f024_steps.py::test_f024_r10_ningun_raw_incoherente_llega_a_construir[histórico sin batch-estados2]
FAILED tests/test_f024_steps.py::test_f024_r10_ningun_raw_incoherente_llega_a_construir[raw vacío-estados3]
FAILED tests/test_f024_steps.py::test_f024_r10_puerta_ok_registra_y_continua
FAILED tests/test_f024_steps.py::test_f024_r10_la_puerta_precede_al_preflight
FAILED tests/test_f024_steps.py::test_f024_r11_stage_sin_puerta_registra_skipped_y_continua
FAILED tests/test_f024_steps.py::test_f024_r11_sin_puerta_no_es_una_excusa_para_no_mirar
FAILED tests/test_f024_steps.py::test_f024_r12_las_requeridas_salen_del_yaml
FAILED tests/test_f024_steps.py::test_f024_r3_los_subpasos_y_tramos_llevan_el_batch
11 failed, 1 passed in 1.36s
```

### T11 · Puerta de `stg` en `build_mart`

```
$ python -m pytest tests/test_f024_steps.py -q
tests\test_f024_steps.py:405: TypeError
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino[sin ninguna fila de stg-None]
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino[sub-paso abortado-ultimo1]
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino[tramo en curso-ultimo2]
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino[el paso fallo-ultimo3]
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino[sub-paso terminado, paso no-ultimo4]
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_ok_si_stage_success
FAILED tests/test_f024_steps.py::test_f024_r15_la_puerta_precede_al_primer_sql_de_mart
FAILED tests/test_f024_steps.py::test_f024_r15_build_mart_sin_puerta_registra_y_continua
8 failed, 13 passed in 1.48s
```

### T12 · CLI

```
$ python -m pytest tests/test_f024_cli.py -q
FAILED tests/test_f024_cli.py::test_f024_r18_comandos_sueltos_registran_el_paso[apply-grants]
FAILED tests/test_f024_cli.py::test_f024_r18_un_paso_fallido_registra_y_sale_uno
FAILED tests/test_f024_cli.py::test_f024_r3_run_all_un_solo_batch_para_todas_las_filas
FAILED tests/test_f024_cli.py::test_f024_r3_dos_ejecuciones_no_comparten_batch
FAILED tests/test_f024_cli.py::test_f024_r11_los_comandos_sueltos_admiten_sin_puerta[stage]
FAILED tests/test_f024_cli.py::test_f024_r11_los_comandos_sueltos_admiten_sin_puerta[build-mart]
FAILED tests/test_f024_cli.py::test_f024_r11_sin_la_opcion_la_puerta_se_aplica[stage]
FAILED tests/test_f024_cli.py::test_f024_r11_sin_la_opcion_la_puerta_se_aplica[build-mart]
FAILED tests/test_f024_cli.py::test_f024_r14_check_coherencia_codigos_de_salida[raw y stg coherentes-<lambda>-0]
FAILED tests/test_f024_cli.py::test_f024_r14_check_coherencia_codigos_de_salida[raw incoherente-<lambda>-1]
FAILED tests/test_f024_cli.py::test_f024_r14_check_coherencia_codigos_de_salida[stg a medias-<lambda>-1]
FAILED tests/test_f024_cli.py::test_f024_r14_check_coherencia_explica_por_que
FAILED tests/test_f024_cli.py::test_f024_r19_check_frescura_codigos_de_salida[fresco-<lambda>-0]
FAILED tests/test_f024_cli.py::test_f024_r19_check_frescura_codigos_de_salida[caducado-<lambda>-1]
FAILED tests/test_f024_cli.py::test_f024_r19_check_frescura_codigos_de_salida[sin build-<lambda>-1]
FAILED tests/test_f024_cli.py::test_f024_r19_check_frescura_codigos_de_salida[sin filas-<lambda>-1]
FAILED tests/test_f024_cli.py::test_f024_r19_check_frescura_admite_umbral_y_paso
FAILED tests/test_f024_cli.py::test_f024_r14_r19_los_comandos_nuevos_estan_en_la_ayuda
FAILED tests/test_f024_cli.py::test_f024_la_docstring_de_main_nombra_los_comandos_nuevos
37 failed, 12 passed in 1.47s
```

### T13 · Alerta de frescura

```
$ python -m pytest tests/test_f024_infra_alerta.py -q
E       AssertionError: assert '95_create_alert_frescura.ps1' in ['00_vars.ps1', '05_check_prereqs.ps1', ...]
FAILED tests/test_f024_infra_alerta.py::test_f024_r21_la_alerta_filtra_por_los_tres_terminos
FAILED tests/test_f024_infra_alerta.py::test_f024_r21_la_alerta_mira_el_job_por_la_columna_real
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_script_alerta_frescura_lee_de_cfg_y_sin_nombres
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_la_alerta_es_idempotente
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_la_ventana_sale_del_umbral_y_no_es_iso_8601
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_la_alerta_dispara_por_ausencia_y_se_desactiva_sola
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_script_alerta_frescura_bom_crlf_cabecera
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_ninguna_variable_se_llama_como_las_de_00_vars
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_readme_documenta_el_script_en_orden
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_dev_json_declara_umbral_y_nombre
FAILED tests/test_f024_infra_alerta.py::test_f024_r22_el_script_esta_en_la_lista_de_los_ps1
11 failed, 1 passed in 1.38s
```

El único que pasó en verde es
`test_f024_r21_orquestador_emite_step_finished_con_step_y_status`, y es
información útil: el extremo del ETL del contrato de R21 **ya existía**; lo que
faltaba era el otro extremo y su amarre.

---

## 4 · Decisiones de diseño que conviene conocer

1. **La puerta va la PRIMERA, antes incluso del pre-flight.** No es un detalle
   de orden. `stg` empieza con `TRUNCATE` y `mart/01_ddl.sql` con un `DROP`, y
   eso no se deshace porque el step devuelva `FAILED` después. Los tests no
   afirman «falló», afirman «falló ANTES»: el doble lleva traza ordenada y se
   comprueba que la lista de escrituras está vacía.
2. **Con `--sin-puerta` la fila queda `SKIPPED` aunque el veredicto sea OK.**
   Lo que esa fila cuenta es que el build se hizo **sin** puerta, no lo que la
   puerta habría dictaminado. Quien audite `_meta.etl_runs` tiene que poder
   distinguir un build verificado de uno que no lo fue. Es la lectura literal
   de R11.
3. **`fetch_ultimo_intento_stg` ordena por `id DESC`, no por fecha.** La fila
   de PASO se inserta al TERMINAR el step, y su `started_at` es anterior al de
   todos sus sub-pasos. Por fecha, un stage terminado devolvería su último
   tramo y la puerta de `mart` lo tomaría por incompleto: la puerta fallaría
   justo las noches buenas.
4. **Un YAML sin tablas da KO.** `evaluar_coherencia_raw(estados, ())` no
   devuelve OK: no hay batch único que acreditar. Un `tables_sigrid.yaml`
   vacío es un error de configuración, no una carga coherente.
5. **Con batches mezclados se marcan TODAS las tablas implicadas**, también
   las del batch nuevo. Cuando hay dos ejecuciones repartidas por `raw` no hay
   forma de saber cuál es la buena, y marcar un solo lado fabricaría una
   certeza que nadie tiene. Hay un test de contraste
   (`test_f024_r20_la_marca_discrimina_cuando_hay_una_sola_culpable`) que
   impide que la marca acabe saliendo siempre y deje de señalar nada.
6. **`--window-size 30h`, no `PT30H`.** Confirmado en T3. Hay un test que
   rechaza el ISO 8601 y otro que exige que la ventana se DERIVE de
   `frescuraUmbralHoras` en vez de escribirse a mano, que es como divergirían
   la alerta y `check-frescura`.
7. **El umbral está duplicado a propósito** (constante en Python y clave en
   `dev.json`) porque el contenedor no lleva `infra/env/`. Lo único que impide
   que diverjan es `test_f024_r19_umbral_por_defecto_coincide_con_dev_json`.

---

## 5 · Desviaciones respecto a la spec, con su motivo

Ninguna cambia el comportamiento exigido. Se anotan las cuatro:

1. **Reparto de tests entre ficheros.** `design.md` §3 ponía el mapeo de
   `fetch_estado_raw` en `test_f024_steps.py` y el test del orquestador (R21)
   en `test_f024_meta_y_formato.py`. Están, respectivamente, en
   `test_f024_meta_y_formato.py` (con el resto de tests que sustituyen
   `PostgresClient.connection`, para no duplicar los dobles en dos ficheros) y
   en `test_f024_infra_alerta.py` (junto al test del script: R21 existe
   precisamente para amarrar los DOS extremos, y separarlos deja cada mitad
   sin constancia de la otra). Todos los requisitos siguen cubiertos y los
   nombres siguen siendo trazables.
2. **`frescuraUmbralHoras` entró en `dev.json` en T9, no en T13.** El test de
   cruce con la constante es de T9 y sin la clave no habría podido estar en
   verde ese commit. `frescuraAlertName` sí entró en T13.
3. **`load-aux` pasa a salir con código 1 si su paso falla.** Antes solo
   imprimía el resultado. Es consecuencia de migrarlo a `_ejecutar_paso`, que
   es lo que pide `design.md` §4 para los siete comandos; queda anotado por si
   alguien depende del código de salida anterior.
4. **`build-compras` y `build-retenciones` marcan huérfanas pero NO registran
   paso.** Es lo que dice DA-6 (ejecutan SQL en línea sin step y quedan fuera
   de `v_frescura`), pero conviene que conste: aparecerán como «sin registro»
   en la vista hasta que otra feature los convierta en steps.

### Efectos colaterales en tests de otras features (los tres, justificados)

- `tests/test_f019_tramos.py`: el doble `PgFalso` no admitía el tercer
  argumento de `record_run_start`, que ahora sí acepta el cliente real, y no
  tenía `fetch_estado_raw`. Se actualiza a la firma real y declara un `raw`
  coherente para que la puerta nueva lo deje pasar: esos tests miden la puerta
  de **disco**, no la de coherencia.
- `tests/test_f016_huecos_alto_f005.py`: `apply-grants` ahora pasa por el
  cliente para marcar y registrar. El doble se amplía; el test sigue midiendo
  exactamente lo mismo (el código de salida).
- `tests/test_f003_infra.py`: conoce las dos claves nuevas del fichero de
  entorno. `frescuraAlertName` entra además en `CLAVES_NOMBRE_DE_RECURSO`, así
  que queda prohibido escribirlo en un `.ps1`.

### Corrección de hecho encontrada de paso

`infra/README.md` documentaba la consulta de logs con `ContainerAppName_s`,
columna que **no existe** en `ContainerAppConsoleLogs_CL` para un job
(verificado con `getschema` en T3). Devolvía cero filas siempre, que es
indistinguible de «el job no dejó logs». Corregido a `ContainerJobName_s`, con
nota fechada.

---

## 6 · Evidencias

| Evidencia | Valor | Cómo se obtiene |
|---|---|---|
| Tests ejecutados y resultado | **587 passed, 0 failed** (tras los tests de caza de supervivientes de T15) | `python -m pytest -q` dentro de `bash harness/init.sh` |
| Cobertura de las líneas cambiadas | **100,0 % (372/372)**, umbral 80 %, nivel `critico` | línea `PUERTA COBERTURA` de `bash harness/init.sh` |
| Mutantes generados / supervivientes | **108 generados, 106 muertos, 2 supervivientes justificados como equivalentes** (0 sin análisis) | `python -m harness.mutacion --feature F-024` |
| Tiempo de ejecución de la suite | **7,54 s** (suite completa, 587 tests) | el que imprime pytest |

Los tests `test_f024_*` aportan **176** de esos 587. Ninguno
abre red ni BBDD (R27).

### 6.1 · Campaña de mutación

`progress/mutacion_F-024.md`, generado el 2026-08-18 15:15: alcance 1.268
líneas en 12 ficheros (dominio, cliente Postgres, steps, CLI, settings),
**108 mutantes, 106 muertos, 2 supervivientes**, 604 s de campaña
completa (sin muestreo). Una primera pasada dejó más supervivientes en
dominio, `_meta`/formato y CLI; se cazaron con tests nuevos
(`test_f024_dominio.py`, `test_f024_meta_y_formato.py`, `test_f024_cli.py`,
+254 líneas, commit T15). Los 2 restantes son `bold=True → False` en dos
`click.secho` de cabeceras decorativas de `check-coherencia`
(`main.py:564,567`): presentación pura, sin dato, veredicto ni código de
salida; **justificados como equivalentes** en el informe (fijar el atributo
de negrita sería testear `click`). El implementer se quedó colgado
esperando el final de la campaña; T15 y T16 los cerró el líder con los
números reales.

---

## 7 · Lo que queda para el humano (Fase C)

Ninguna se ha ejecutado: todas exigen BBDD o Azure reales.

| Tarea | Qué hay que hacer | Dónde está el comando exacto |
|---|---|---|
| **T17** | Construir imagen (`70_build_image.ps1`), actualizar el job (`85_update_job.ps1`) y comprobar R25: primera ejecución con F-024, las dos filas `RUNNING` del 18-ago en `ABORTED`, `apply-grants`, y las dos vistas legibles con `mcp_sigrid_dm_ro`. | `requirements.md` R25 |
| **T18** | R24: muerte externa controlada durante la ingesta (`az containerapp job stop`), `timings` → `check-coherencia` KO → `stage` FAILED en la puerta **sin tocar `stg`** → `ABORTED` visibles → `check-frescura` FRESCO → recuperación con carga completa y buzón sin Activated. | `requirements.md` R24 |
| **T19** | R23: `az extension add --name scheduled-query`, crear la regla con `infra/95_create_alert_frescura.ps1`, acortar la ventana para provocar el «Activated», restaurar y comprobar el «Deactivated». Anotar horas. | `infra/README.md` §«Probar la alerta de frescura» y `requirements.md` R23 |
| **T20** | R26 en local: `check-coherencia` KO por `sin_batch` sobre el `raw` anterior, `stage` se niega, `ingest --full` (o `stage --sin-puerta`) y construye. | `requirements.md` R26 |

### Avisos para quien ejecute la Fase C

- **`az extension add --name scheduled-query` es requisito del puesto**, no del
  repositorio. El script 95 aborta con un mensaje explícito si falta.
- **El script 95 no se ha ejecutado nunca contra Azure.** La sintaxis
  (`--condition` / `--condition-query`, formato `##h##m##s`, columna
  `ContainerJobName_s`) es la confirmada en T3 con `--help` y `getschema`; el
  resto de parámetros (`--location`, `--tags`, `--auto-mitigate`) siguen el
  patrón de `90_create_alert.ps1`. Si `az` rechazara alguno, **no improvisar**:
  anotarlo y volver a la spec.
- **La primera ejecución en Azure cerrará las huérfanas del 18-ago.** Conviene
  capturar `python main.py timings --last 3` ANTES para tener la foto previa.
- **Tras el despliegue hace falta `apply-grants`** (o esperar a la primera
  noche completa) para que `mcp_sigrid_dm_ro` vea las dos vistas nuevas.

### Una corrección pendiente que no es mía

`progress/current.md` afirma en tres sitios que la ingesta es «transaccional
por tabla» (líneas ~60, ~112 y ~391; la última la usa para razonar sobre una
recuperación). DA-8 lo desmiente: es **commit por página**. Lo he corregido
donde vive permanentemente (`docs/ARCHITECTURE.md`), pero `progress/current.md`
es del líder y estaba siendo editado en paralelo, así que no lo he tocado.

---

## 8 · Verificación final

```
$ bash harness/init.sh
[OK] PUERTA COBERTURA: 100.0% de 372 líneas cambiadas cubiertas (372/372, umbral 80%, nivel critico)
ENTORNO LISTO. Puedes trabajar.
```

`ruff` no es bloqueante en este arnés y arrastra deuda previa. Mis ficheros
nuevos pasan `ruff check` limpios; en `main.py` los 3 avisos añadidos son
`RUF100` sobre `# noqa: E402` en los tres imports nuevos, el mismo patrón que
ya llevan los otros 18 imports del fichero.
