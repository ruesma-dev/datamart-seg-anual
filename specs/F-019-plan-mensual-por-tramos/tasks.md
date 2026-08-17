<!-- specs/F-019-plan-mensual-por-tramos/tasks.md -->
# F-019 · Build de stg.plan_mensual por tramos — Tareas

Rama: `feature/F-019-plan-mensual-por-tramos`. Un commit por tarea
(`F-019 Tn: ...`). Rigor `critico`.

**Regla de hierro de esta feature**: NINGÚN agente abre conexión a BBDD.
Todo lo que exija una BBDD real es `MANUAL (humano)` con su comando exacto
en `requirements.md`. Y sigue vigente el «PROHIBIDO relanzar stage contra
Azure» hasta T12, que es la primera ejecución autorizada del build nuevo.

## Fase A · Medir (humano, local)

- [x] **T1 (hecha 2026-08-11)**: mediciones en `design.md` §2, columna
      «medido» completa (29,09 M filas, 7.532 MB, explosión ×18,4, obra
      más pesada 298.053 filas). Derrame medido después en T11:
      ~0,47 KB/fila. La línea base de R2 del 22-jul quedó ANULADA por la
      reingesta del 30-jul y se rehizo en T11 contra worktree `2cb6de7`.
- [x] **T2 (hecha 2026-08-11)**: los números de T1 no contradicen ninguna
      constante (obra más pesada 298.053 filas ≪ 1 M); derivación anotada
      en `design.md` §2, defaults confirmados sin cambios.

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

- [x] **T11 (hecha 2026-08-13, SUPERADA por enmienda de R13)**: el
      checksum dio FALLO (`ec74147e` vs `c58b928d`), se declaró sin
      racionalizar y la investigación aprobada por el humano probó la
      equivalencia semántica (causa: versiones master duplicadas
      preexistentes; ver enmienda de R13 y
      `docs/referencia/05_caso_obrfasamb_version_duplicada.md`). Decisión
      del humano: opción C. Commits `acee46b`…`181e01e`.
- [x] **T12 (hecha 2026-08-14/15)**: `stage` SUCCESS 6.851,8 s, 60/60
      tramos sin abortos, pico de disco 46,55 % (límite 80 %),
      `build-mart` y `apply-grants` SUCCESS, `timings` por tramo anotado.
      Cierra paso 8 de F-005 y da el veredicto del 9: el B1ms aguanta.
      Commit `c74b65b`.
- [x] **T13 (hecha 2026-08-15/17, SUPERADA por enmienda de R15)**: tres
      iteraciones con capturas sincronizadas y `--periodo-hasta 2026-05`;
      destaparon y corrigieron 3 defectos reales (raw local con esquema
      legado; `TMMonth`/locale, commit `42e128d`; claves sustitutas en la
      huella, `65c52aa`). Resultado final: 0 fallos en todo lo
      determinista y 5 residuales probados fila a fila como una edición
      real del Previsto (obra 2313811, +632,74 €). Decisión del humano:
      opción A. Commits `8582485`, `2d95980`.
- [ ] **T14** (queda `[ ]` A PROPÓSITO: es posterior al `done` y pertenece
      operativamente a F-003): con T12/T13 en verde y F-019 marcada `done` por el líder, el
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
