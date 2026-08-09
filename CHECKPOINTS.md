<!-- CHECKPOINTS.md -->
# CHECKPOINTS — Evaluación del estado final

> No se evalúa el camino, se evalúa el destino. El reviewer recorre estos
> checkboxes al cerrar cada feature y rechaza el cierre si queda alguno
> vacío en C1–C5. El humano puede usarlos igual antes de mergear a dev.

> **Features `sdd=false`.** No tienen `specs/F-XXX-slug/`, así que léase
> `acceptance` de `harness/features.json` donde estos checkpoints digan
> «requisito EARS» o «spec», y `F-XXX: <descripción>` como formato mínimo de
> mensaje de commit donde digan `F-XXX Tn:`. Lo que dependa de `tasks.md` es
> N/A. Marcar N/A es legítimo, pero **hay que justificarlo por escrito** en el
> informe de review: un N/A sin motivo se trata como checkbox vacío.

> **La regla del N/A vale también para las puertas de verificación.** Ninguna
> de las puertas de C4 bis —campaña de **mutación**, **fase RED** y
> **cobertura** de las líneas cambiadas— puede saltarse marcando N/A a secas.
> Para declararlas N/A hay que justificar por escrito en el informe de review
> *por qué* no aplican en esta feature (por ejemplo: nivel `documental`, o la
> puerta de cobertura se declaró N/A con su motivo impreso por `init.sh`). Un
> N/A sin motivo escrito se trata como checkbox vacío, y un checkbox vacío en
> C1–C5 es CHANGES_REQUESTED. Omitir la herramienta —no instalar `coverage`,
> no lanzar la campaña— no es un motivo: es el hueco que esto viene a tapar.

## Niveles de rigor

No todas las features merecen la misma vigilancia. Cada una declara su nivel
en el campo `rigor` de su entrada de `harness/features.json`; lo que exige
cada nivel vive en `harness/rigor.json` y lo valida `bash harness/init.sh`.

**Si una feature no declara nivel se le aplica el más exigente (`critico`).**
La omisión no puede ser la vía fácil para saltarse las puertas.

| Nivel | Para qué features | Exige |
|---|---|---|
| **documental** | Solo documentación, specs o notas de sesión: ni código ni SQL | C1–C3, C3 bis y C5. **Sin** fase RED, **sin** cobertura y **sin** mutación: una feature documental no puede requerir mutation testing |
| **estandar** | Código sin riesgo sobre sistemas compartidos | Todo lo anterior + tests trazables (C4) + **fase RED** en los requisitos centrales + **cobertura** de las líneas cambiadas ≥ umbral + **campaña de mutación** con los supervivientes documentados y analizados |
| **critico** | Infraestructura compartida, producción, seguridad o dinero | Todo lo de `estandar` + **cero supervivientes** sin justificación escrita aceptada por el humano + verificaciones `MANUAL (humano)` listadas con su comando exacto y su resultado real |

Comandos de las puertas:

```bash
bash harness/init.sh                        # cobertura de las líneas cambiadas
python -m harness.mutacion --feature F-XXX  # campaña de mutación
```

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

## C3 bis — Los documentos que entran de fuera son seguros

Aplica a toda feature que añada o modifique ficheros en `docs/referencia/`.
Si no toca ninguno, es N/A.

- [ ] Cada documento nuevo lleva cabecera con **origen y fecha** del original,
      según la plantilla de `docs/referencia/README.md`.
- [ ] Los originales en PDF u ofimática **no** están en el repositorio ni en
      el árbol de trabajo (compruébalo también con `git log --diff-filter=A`:
      no basta con que no estén ahora).
- [ ] Se ha ejecutado un **barrido de datos sensibles** sobre los documentos
      nuevos —correos, IPs, GUID de suscripción o tenant, credenciales,
      tokens, cadenas tipo clave— y **su resultado consta en el informe de
      review**, con los patrones usados. El barrido lo ejecuta el reviewer:
      no vale darlo por bueno leyendo el informe del implementer.
- [ ] Lo que se haya redactado está anotado en la cabecera del documento.

## C4 — La verificación es real

- [ ] Cada requisito EARS de la spec tiene >= 1 test trazable
      (`test_fXXX_rN_*`) y todos pasan.
- [ ] Los unit tests no tocan red ni BBDD (mocks/fixtures).
- [ ] Las verificaciones `MANUAL (humano)` están listadas en
      `progress/current.md` con su comando exacto, pendientes de que el
      humano las ejecute.

## C4 bis — El rigor declarado se cumple

Comprobar que los tests son de verdad, no solo que pasan. El reviewer resuelve
primero el nivel de la feature (campo `rigor`, o `critico` por omisión) y
recorre estos puntos **contra ese nivel**.

- [ ] La feature declara `rigor` en `harness/features.json` con un valor
      válido, o consta por escrito que se le aplica el más exigente.
- [ ] **Fase RED** (niveles `estandar` y `critico`): el informe
      `progress/impl_F-XXX.md` contiene, para los requisitos centrales, la
      **salida real** del fallo del test antes de existir el código. No vale
      «se hizo TDD»: vale la traza pegada.
- [ ] **Cobertura** (niveles `estandar` y `critico`): la puerta de
      `bash harness/init.sh` sale en `[OK]` con el porcentaje de las líneas
      cambiadas, o en `N/A` **con el motivo impreso**.
- [ ] **Mutación** (niveles `estandar` y `critico`): existe
      `progress/mutacion_F-XXX.md`, generado por la herramienta, con sus
      totales reales, **verificados de forma independiente por el reviewer**
      (alcance y nº de mutantes recalculados con `harness.alcance` y
      `harness.mutacion`; cálculo puro, sin ejecutar la suite).
- [ ] Cada superviviente de esa campaña tiene su sección de análisis
      **completada** (ninguna en `PENDIENTE`). En nivel `critico`, además,
      cero supervivientes salvo justificación escrita aceptada por el humano.
- [ ] El informe del implementer trae la sección **«Evidencias»** con los
      cuatro números: tests ejecutados y resultado, cobertura de las líneas
      cambiadas, mutantes generados y supervivientes, y tiempo de la suite.
- [ ] Ningún punto de este bloque marcado N/A sin justificación escrita.

## C5 — La sesión se cerró bien

- [ ] `tasks.md` de la spec con todas las tareas `[x]` y un commit
      `F-XXX Tn: ...` por tarea.
- [ ] Sin ficheros temporales ni artefactos sin trackear sospechosos.
- [ ] `features.json` refleja el estado real de la feature.
