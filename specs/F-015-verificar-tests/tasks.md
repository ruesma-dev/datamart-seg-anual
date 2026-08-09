<!-- specs/F-015-verificar-tests/tasks.md -->
# F-015 · Verificar que los tests son de verdad — Tareas

> Requisito previo: el humano ha cerrado DA-1..DA-6 de `design.md`.
> Fase RED aplicada a la propia feature: en T1–T7 el test se escribe ANTES que
> el código y su fallo real se pega en `progress/impl_F-015.md`.
> Ninguna tarea abre conexión a red ni a BBDD (hay una carga contra Azure en
> curso: pytest y git, sí; `check-pg`, `run-all`, `status`, no).

- [ ] T1: Crear `harness/__init__.py` y `harness/alcance.py` (parser de diff,
      filtro de producción, `resolver_refs`, `alcance_de_feature`) con
      `tests/test_f015_alcance.py`.
      | Verificación: `python -m pytest -q -k "f015_r2 or f015_r4"` en verde
      (RED primero: los tests fallan sin el módulo).
- [ ] T2: Operadores de mutación y generación de mutantes en
      `harness/mutacion.py` (`Mutante`, `generar_mutantes`, `aplicar_mutante`)
      con los tests de R6.
      | Verificación: `python -m pytest -q -k f015_r6` en verde.
- [ ] T3: Campaña, restauración garantizada, timeout e informe
      (`EjecutorPytest`, `ejecutar_campania`, `escribir_informe`, `main`) con
      los tests de R1, R3, R5 y R7 (ejecutor mockeado).
      | Verificación: `python -m pytest -q -k "f015_r1 or f015_r3 or f015_r5 or f015_r7"` en verde.
- [ ] T4: `harness/rigor.json` y `harness/rigor.py` (carga, validación,
      `nivel_de_feature` con default el más exigente, `exige`) con los tests
      de R11 y R15 (parte unit).
      | Verificación: `python -m pytest -q -k "f015_r11 or f015_r15"` en verde.
- [ ] T5: `harness/cobertura.py` (cruce coverage×diff, decisión aplica/N-A,
      exit codes) con los tests de R10, R12 y R13 (fixtures de coverage.json
      y de diff; sin ejecutar coverage de verdad).
      | Verificación: `python -m pytest -q -k "f015_r10 or f015_r12 or f015_r13"` en verde.
- [ ] T6: Integrar en `harness/init.sh`: validación de `rigor.json` y del
      campo `rigor`, `harness` en `compileall`, `coverage run -m pytest` +
      puerta `python -m harness.cobertura`; añadir `coverage>=7.4` a
      `requirements-dev.txt` e instalarlo. Tests textuales de R10/R11/R13/R15
      sobre `init.sh`.
      | Verificación: `bash harness/init.sh` en verde en la rama de F-015 con
      la puerta de cobertura ejecutándose de verdad (su salida, al informe).
- [ ] T7: `CHECKPOINTS.md`: sección «Niveles de rigor», bloque C4 bis y
      ampliación de la nota de N/A, con los tests textuales de R14 y R17.
      | Verificación: `python -m pytest -q -k "f015_r14 or f015_r17"` en verde.
- [ ] T8: `.claude/agents/implementer.md`: fase RED obligatoria y sección
      «Evidencias», con los tests textuales de R8 y R9.
      | Verificación: `python -m pytest -q -k "f015_r8 or f015_r9"` en verde.
- [ ] T9: `.claude/agents/reviewer.md`: validación contra el nivel de rigor
      declarado, con el test textual de R16.
      | Verificación: `python -m pytest -q -k f015_r16` en verde.
- [ ] T10: Test de genericidad R19 (las herramientas del arnés no mencionan
      nada del datamart).
      | Verificación: `python -m pytest -q -k f015_r19` en verde.
- [ ] T11: Línea base: `python -m harness.mutacion --feature F-005` (alcance
      reconstruido desde el merge `c7500d4`; opciones según DA-5) →
      `progress/mutacion_F-005.md` con totales y supervivientes analizados;
      test de R18.
      | Verificación: `python -m pytest -q -k f015_r18` en verde y el número
      de supervivientes anotado también en `progress/impl_F-015.md`.
- [ ] T12: Autoaplicación: `python -m harness.mutacion --feature F-015` sobre
      la propia rama → `progress/mutacion_F-015.md`; sección «Evidencias» del
      informe del implementer completa (tests, cobertura de líneas cambiadas,
      supervivientes, tiempo).
      | Verificación: existe `progress/mutacion_F-015.md` y las evidencias
      llevan números reales.
- [ ] T13: Portar a `arnes-base` (R20): herramientas genéricas, `init.sh`,
      `CHECKPOINTS.md`, agentes, `VERSION` → `1.2.0`, sección nueva en
      `GUIA_INSTALACION.md`; commit local en ese repositorio.
      | Verificación: MANUAL (humano) — los cuatro comandos de R20 en
      `requirements.md`.
- [ ] T14: Si el humano aprobó DA-4: declarar `rigor` en las entradas de
      `harness/features.json` según la lista acordada (si no la aprobó,
      saltar esta tarea y dejarlo anotado en `progress/current.md`).
      | Verificación: `bash harness/init.sh` valida los valores.
- [ ] T15: Actualizar `progress/current.md` (estado, verificaciones MANUAL
      pendientes) y escribir `progress/impl_F-015.md` con las salidas RED
      reales y la sección «Evidencias».
      | Verificación: ficheros presentes y completos.
- [ ] T16: Ejecutar `bash harness/init.sh` en verde.
      | Verificación: exit code 0, salida pegada en el informe.
