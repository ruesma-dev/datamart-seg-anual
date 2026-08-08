<!-- CHECKPOINTS.md -->
# CHECKPOINTS — Evaluación del estado final

> No se evalúa el camino, se evalúa el destino. El reviewer recorre estos
> checkboxes al cerrar cada feature y rechaza el cierre si queda alguno
> vacío en C1–C5. El humano puede usarlos igual antes de mergear a dev.

## C1 — El arnés está completo y en verde

- [ ] `bash harness/init.sh` termina con exit code 0.
- [ ] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

## C2 — El estado es coherente

- [ ] Como mucho UNA feature en `in_progress` en `harness/features.json`.
- [ ] La rama actual es `feature/F-XXX-slug` de la feature en curso
      (nunca `main`).
- [ ] `progress/current.md` describe SOLO la sesión activa (sin restos de
      sesiones anteriores) o está en plantilla vacía.
- [ ] Toda feature `done` tiene su resumen en `progress/history.md`.

## C3 — El código respeta arquitectura y convenciones

- [ ] Dominio sin imports de infraestructura; SQL en su capa correcta
      (`stg`/`mart`/`cierre`/...) con numeración `NN_nombre.sql`.
- [ ] Primera línea de cada fichero Python: comentario con su ruta relativa.
- [ ] Sin `print()` de debug, sin TODOs sin contexto, sin secretos
      hardcodeados, sin dependencias nuevas no previstas en la spec.
- [ ] Semántica Sigrid respetada (amb/fas, importe_origen vs importe_mes,
      `fasnum` vs `fas`) según `docs/ARCHITECTURE.md`.

## C4 — La verificación es real

- [ ] Cada requisito EARS de la spec tiene >= 1 test trazable
      (`test_fXXX_rN_*`) y todos pasan.
- [ ] Los unit tests no tocan red ni BBDD (mocks/fixtures).
- [ ] Las verificaciones `MANUAL (humano)` están listadas en
      `progress/current.md` con su comando exacto, pendientes de que el
      humano las ejecute.

## C5 — La sesión se cerró bien

- [ ] `tasks.md` de la spec con todas las tareas `[x]` y un commit
      `F-XXX Tn: ...` por tarea.
- [ ] Sin ficheros temporales ni artefactos sin trackear sospechosos.
- [ ] `features.json` refleja el estado real de la feature.
