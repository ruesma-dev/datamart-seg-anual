<!-- specs/F-024-coherencia-cargas-truncadas/tasks.md -->
# F-024 · Coherencia del datamart ante cargas truncadas — Tareas

Rama: `feature/F-024-coherencia-cargas-truncadas`. Un commit por tarea
(`F-024 Tn: ...`). Rigor `critico`.

**Regla de hierro**: NINGÚN agente abre conexión a BBDD ni a Azure. Todo lo
que exija BBDD real o Azure es `MANUAL (humano)` con su comando exacto en
`requirements.md`. `.env` del puesto apunta a Azure: los tests no lo tocan.

## Fase A · Medir y decidir (humano, antes de escribir código)

- [x] **T1** (cerrada 2026-08-18, «aprobado con las recomendadas»): Cerrar DA-1, DA-2, DA-5, DA-6, DA-7 (mecanismo, política de
      la puerta, puerta de `stg`, registro de comandos sueltos, quién marca)
      y anotar la decisión con fecha en `requirements.md` §Decisiones.
      | Verificación: MANUAL (humano) — las cinco DA tienen «CERRADA
      <fecha>: opción X» escrita.
- [x] **T2** (cerrada 2026-08-18: DA-3 = A, DA-4 = 30 h): Cerrar DA-3 (mecanismo de la alerta) y DA-4 (umbral). Si es
      A, `az extension add --name scheduled-query` en el puesto y ejecutar a
      mano la KQL de R23 paso 1 (confirma columna del job, `has_all` y que
      devuelve ≥ 1 tras la última noche buena). Si es B, el spec-author
      enmienda R21/R22 antes de seguir. | Verificación: MANUAL (humano) —
      DA-3 y DA-4 cerradas; salida real de la KQL pegada en
      `progress/current.md`.
- [x] **T3** (hecha por el líder 2026-08-18: sintaxis ##h##m##s, columna ContainerJobName_s): (solo si DA-3 = A) Confirmar la sintaxis de `az monitor
      scheduled-query create` (`--condition`, `--condition-query`,
      formato de `--window-size`) con `--help`, sin crear nada, y anotar en
      `design.md` §8 la forma definitiva. | Verificación: MANUAL (humano) —
      §8 enmendado o confirmado con fecha.
- [x] **T4** (hecha por el líder 2026-08-18: commit POR PÁGINA, no por tabla; anotado en requirements): DA-8: confirmar si la ingesta hace commit por página
      (leyendo `copy_rows` o con el `SELECT count(*)` de R26 durante un
      `ingest --full` local) y anotar el resultado en `requirements.md`.
      | Verificación: MANUAL (humano).

## Fase B · Implementar (implementer; tests primero, fase RED con evidencia)

- [x] **T5**: `etl_sigrid/domain/ejecucion.py` (`Ejecucion`,
      `nueva_ejecucion`, `MOTIVO_HUERFANA`) y `StepStatus.ABORTED`, con
      sus tests ANTES (RED documentada en `progress/impl_F-024.md`).
      | Verificación: `pytest tests/test_f024_dominio.py -k r1` en verde.
- [x] **T6**: `etl_sigrid/domain/coherencia.py` (`EstadoTablaRaw`,
      `EstadoPaso`, `VeredictoCoherencia`, `evaluar_coherencia_raw`,
      `formatear_veredicto_raw`, `evaluar_coherencia_stg`,
      `formatear_veredicto_stg`) con tests R8–R9 antes.
      | Verificación: `pytest tests/test_f024_dominio.py -k "r8 or r9"`.
- [x] **T7**: DDL de `_meta` (`00_meta.sql`: `batch_id`, índice,
      `v_raw_state`, `v_frescura`) y sus tests estáticos R2/R13/R16.
      | Verificación: `pytest tests/test_f024_meta_y_formato.py -k "r2 or r13 or r16"`.
- [x] **T8**: `postgres_client.py`: `batch_id` opcional en
      `record_run_start`/`record_run_completed`, `abortar_runs_huerfanos`,
      `fetch_estado_raw`, `fetch_ultimo_intento_stg`, `fetch_frescura`
      (constantes SQL de módulo); `step_run_recorder.py` con `batch_id`.
      Tests con doble de cursor. | Verificación: `pytest -k "f024_r2 or f024_r4_la_marca or f024_r13_fetch"`.
- [x] **T9**: `timings.py`: `format_timings(timings, ahora)` con el aviso
      de R6 y `UMBRAL_HUERFANA_HORAS`; `frescura.py` con `FilaFrescura`,
      `format_frescura`, `format_estado_raw`, `UMBRAL_FRESCURA_HORAS`
      (R6, R19 formato, R20, cruce con `dev.json`).
      | Verificación: `pytest tests/test_f024_meta_y_formato.py -k "r6 or r19 or r20"`.
- [x] **T10**: `ingest_raw_step.py` (`batch_id`) y `build_stg_step.py`
      (`batch_id`, `omitir_puerta`, `_puerta_raw` antes del preflight,
      registro `build_stg.puerta_raw` SUCCESS/FAILED/SKIPPED). Tests R3
      (parte stg), R10, R11 (step), R12 con `PgFalso`.
      | Verificación: `pytest tests/test_f024_steps.py -k "r10 or r11 or r12"`.
- [x] **T11**: (DA-5) `build_mart_step.py` con `_puerta_stg` y registro
      `build_mart.puerta_stg`. Tests R15. | Verificación:
      `pytest tests/test_f024_steps.py -k r15`.
- [x] **T12**: `main.py`: `_arrancar_ejecucion`, `_ejecutar_paso`, los
      comandos que escriben migrados al helper (R4, R7, R18), `run-all`
      con batch único (R3), `--sin-puerta` en `stage`/`build-mart` y NO en
      `run-all` (R11), `timings` con `ahora`, comandos nuevos
      `check-coherencia` (R14) y `check-frescura` (R19), comandos de
      lectura sin marca (R5). Tests con `CliRunner` y dobles.
      | Verificación: `pytest tests/test_f024_cli.py` y
      `pytest tests/test_f024_steps.py -k r3`.
- [x] **T13**: (DA-3 = A) `infra/95_create_alert_frescura.ps1`,
      `infra/env/dev.json` (`frescuraAlertName`, `frescuraUmbralHoras`),
      fila y sección en `infra/README.md`; test R21 (orquestador +
      script) y R22. `tests/test_f003_infra.py` debe seguir en verde (BOM,
      CRLF, sin nombres, README en orden). | Verificación:
      `pytest tests/test_f024_infra_alerta.py tests/test_f003_infra.py`.
- [x] **T14**: Documentación: `docs/ARCHITECTURE.md` (sección F-024 y
      corrección de DA-8 si procede) y `azure-apps/datamart_seg_anual.md`
      (vistas de `_meta` expuestas, alerta de frescura), en el mismo
      trabajo. | Verificación: ambos mencionan `v_frescura`,
      `v_raw_state`, `--sin-puerta`, `ABORTED` y el umbral;
      `bash harness/init.sh` sin falsos positivos del barrido.
- [x] **T15** (2026-08-18: 108/106/2 equivalentes justificados, commit 6305b64): Campaña de mutación sobre el alcance de la feature e
      informe de evidencias (rigor `critico`: cero supervivientes sin
      justificación escrita aceptada). | Verificación:
      `python -m harness.mutacion --feature F-024` →
      `progress/mutacion_F-024.md` con totales; supervivientes 0 o
      justificados uno a uno.
- [x] **T16** (2026-08-18: 587 passed, cobertura 100 % de 372 líneas, ENTORNO LISTO): Ejecutar `bash harness/init.sh` en verde (pytest completo,
      cobertura de las líneas cambiadas ≥ umbral, sin red ni BBDD).
      | Verificación: `bash harness/init.sh` termina en verde.

## Fase C · Verificar en Azure y en local (humano; tras el APPROVED del reviewer sobre Fase B)

- [ ] **T17**: Construir la imagen (`70_build_image.ps1`), actualizar el
      job (`85_update_job.ps1`) y ejecutar R25: primera ejecución con
      F-024, huérfanas del 18-ago en `ABORTED`, `apply-grants`, y las dos
      vistas legibles con `mcp_sigrid_dm_ro`. | Verificación: MANUAL
      (humano) — comandos de R25; salida anotada en `progress/current.md`.
- [ ] **T18**: R24: muerte externa controlada durante la ingesta
      (`az containerapp job stop`), `timings` → `check-coherencia` KO →
      `stage` FAILED en la puerta sin tocar `stg` → `ABORTED` visibles →
      `check-frescura` FRESCO → recuperación con la carga completa y buzón
      sin Activated. | Verificación: MANUAL (humano) — comandos de R24 con
      horas y salidas reales.
- [ ] **T19**: (DA-3 = A) R23: crear la regla con el script 95, ventana
      corta (`1h`) para provocar el correo Activated, restaurar a `48h`
      —la ventana real de la regla, ver la enmienda de DA-4 del
      2026-08-19—, Deactivated tras la siguiente noche buena.
      | Verificación: MANUAL (humano) — horas de Activated/Deactivated en
      `progress/current.md`.
      - [x] **T19 bis** (2026-08-19, AUTO): el primer intento de creación lo
            rechazó el ARM (`WindowSize of 1800 minutes is not supported`).
            Arreglado en `infra/95_create_alert_frescura.ps1`: la ventana la
            deriva `Resolver-VentanaAdmitida` de la lista de granularidades
            admitidas y el criterio de 30 h viaja en la KQL como
            `ago(30h)`. | Verificación: `python -m pytest
            tests/test_f024_infra_alerta.py` (30 passed; tres de ellos
            ejecutan la función del `.ps1` con `powershell`).
- [ ] **T20**: R26 en local: `check-coherencia` KO por `sin_batch` sobre
      el raw anterior, `stage` se niega, `ingest --full` (o
      `stage --sin-puerta` registrado) y construye. | Verificación: MANUAL
      (humano).

## Notas de orden

- T1–T4 van ANTES que cualquier código: la feature tiene decisiones
  abiertas reales (mecanismo de alerta, política de la puerta) y
  escribirlas dos veces es lo que se quiere evitar.
- T16 es la última tarea del implementer (regla de SPECS.md); T17–T20 son
  la verificación del humano y quedan fuera de su alcance.
- El cierre de la feature (`done`) exige: init.sh verde + APPROVED del
  reviewer contra CHECKPOINTS.md nivel `critico` + T17–T20 ejecutadas con
  resultado real anotado (las verificaciones MANUAL de nivel `critico` no
  pueden quedar en «pendiente» al cerrar).
- Si el humano elige DA-3 = B, T13 y T19 se sustituyen por la enmienda
  correspondiente (segundo job + alerta de métrica) antes de arrancar
  Fase B; T2 lo deja escrito.
