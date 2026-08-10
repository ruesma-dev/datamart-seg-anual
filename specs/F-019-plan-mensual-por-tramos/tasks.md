<!-- specs/F-019-plan-mensual-por-tramos/tasks.md -->
# F-019 · Build de stg.plan_mensual por tramos — Tareas

Rama: `feature/F-019-plan-mensual-por-tramos`. Un commit por tarea
(`F-019 Tn: ...`). Rigor `critico`.

**Regla de hierro de esta feature**: NINGÚN agente abre conexión a BBDD.
Todo lo que exija una BBDD real es `MANUAL (humano)` con su comando exacto
en `requirements.md`. Y sigue vigente el «PROHIBIDO relanzar stage contra
Azure» hasta T12, que es la primera ejecución autorizada del build nuevo.

## Fase A · Medir (humano, local)

- [ ] **T1**: Mediciones previas en el Postgres local (R1) y captura de la
      línea base de equivalencia (R2: checksum + `fingerprint-views` con el
      build ACTUAL). | Verificación: MANUAL (humano) — comandos exactos en
      R1/R2; resultados anotados en `design.md` §Mediciones (columna
      «medido») y CSV/checksum guardados en el puesto.
- [ ] **T2**: Confirmar o corregir las constantes (`PG_TRAMO_MAX_FILAS`,
      `PG_DISCO_TOTAL_GB`, `PG_DISCO_LIMITE_PCT`) con los números de T1;
      anotar la derivación final en `design.md` §2. Si T1 contradice el
      corte elegido (p. ej. obra gigante dominante), PARAR y reproponer al
      humano antes de seguir. | Verificación: `design.md` §Mediciones sin
      celdas «medido» vacías y constantes justificadas con esos números.

## Fase B · Implementar (implementer; tests primero, fase RED con evidencia)

- [x] **T3**: `etl_sigrid/domain/tramos.py` con `planificar_tramos` +
      `Tramo`, y sus tests ANTES (RED documentada en el informe).
      | Verificación: `pytest tests/test_f019_tramos.py -k "r3 or r4 or r5"`
      en verde; salida RED previa en `progress/impl_F-019.md`.
- [x] **T4**: Settings nuevos en `config/settings.py` con defaults de T2.
      | Verificación: `test_f019_r4_maximo_configurable_desde_settings`.
- [x] **T5**: Refactor de `08_plan_mensual.sql`: marcador
      `/*F019_FILTRO_OBRAS*/` en las DOS ramas, TRUNCATE fuera, lógica de
      negocio intacta (diff solo añade el filtro y quita el TRUNCATE).
      | Verificación: `pytest -k "f019_r6"` (tests estáticos) y revisión
      del diff del fichero: cero líneas de lógica cambiadas.
- [x] **T6**: Composición segura del filtro (solo enteros; sin marcador ⇒
      fallo antes de tocar BBDD) y `execute_sql_text` +
      `fetch_pesos_plan_mensual` + `medir_ocupacion_disco_pct` en
      `postgres_client.py`. | Verificación: `pytest -k "f019_r7"`.
- [x] **T7**: Orquestación en `build_stg_step.py`:
      `_build_plan_mensual_por_tramos` con TRUNCATE inicial, puerta de
      disco antes de CADA tramo, transacción por tramo, aborto limpio
      (tabla vacía + FAILED en `_meta`), fail-safe de medición, logging y
      registro por tramo. Todo con dobles de `PostgresClient`.
      | Verificación: `pytest -k "f019_r8 or f019_r9 or f019_r10 or f019_r11 or f019_r12"`.
- [x] **T8**: Documentación: `docs/ARCHITECTURE.md` (build por tramos,
      puerta de disco, settings) y `azure-apps/datamart_seg_anual.md`
      (protección del servidor compartido), en el mismo trabajo.
      | Verificación: ambos ficheros mencionan tramos, límite 80 % y el
      incidente 2026-08-09; `bash harness/init.sh` sin falsos positivos del
      barrido de secretos.
- [x] **T9**: Campaña de mutación sobre el alcance de la feature e informe
      de evidencias (rigor `critico`: cero supervivientes sin justificación
      escrita). | Verificación: `progress/mutacion_F-019.md` con totales
      verificables; supervivientes 0 o justificados uno a uno.
- [x] **T10**: Ejecutar `bash harness/init.sh` en verde (pytest completo,
      cobertura del diff, sin red ni BBDD). | Verificación:
      `bash harness/init.sh` termina en verde.

## Fase C · Verificar contra BBDD real (humano; después del APPROVED del reviewer sobre Fase B)

- [ ] **T11**: Equivalencia funcional en LOCAL (R13): `python main.py stage`
      con `.env` local, checksum idéntico al de T1 y
      `compare-fingerprints` sin diferencias. Cualquier diferencia ⇒
      feature `blocked`, no se racionaliza. | Verificación: MANUAL (humano)
      — comandos en R13; checksum y veredicto anotados en el informe.
- [ ] **T12**: Verificación en AZURE (R14): pre-check de la medición de
      ocupación con `sigrid_dm_app`, luego `stage` + `build-mart` +
      `apply-grants` vigilando `storage_percent`, en horario acordado.
      Anotar pico de disco, duración total y `timings` por tramo (cierra
      paso 8 y alimenta el veredicto del paso 9 de F-005).
      | Verificación: MANUAL (humano) — comandos en R14; SUCCESS en los
      tres pasos y pico < `PG_DISCO_LIMITE_PCT`.
- [ ] **T13**: Huella local vs Azure (R15): `fingerprint-views` en Azure y
      `compare-fingerprints` contra la huella local de T11 (cierra paso 10
      de F-005). | Verificación: MANUAL (humano) — sin diferencias.
- [ ] **T14**: Con T12/T13 en verde y F-019 marcada `done` por el líder, el
      humano pone `jobProgramable: true` en `infra/env/dev.json` y retoma
      la tanda 2 de F-003 (T23–T26). Esta tarea NO la ejecuta ningún agente
      de F-019. | Verificación: MANUAL (humano) —
      `pytest tests/test_f003_infra.py` en verde tras el cambio.

## Notas de orden

- T1–T2 van ANTES que cualquier código: la feature exige empezar midiendo.
- T10 es la última tarea del implementer (regla de SPECS.md); T11–T14 son
  la verificación del humano y quedan fuera de su alcance.
- El cierre de la feature (`done`) exige: init.sh verde + APPROVED del
  reviewer contra CHECKPOINTS.md nivel `critico` + T11/T12/T13 ejecutadas
  con resultado real anotado (las verificaciones MANUAL de nivel `critico`
  no pueden quedar en «pendiente» al cerrar).
