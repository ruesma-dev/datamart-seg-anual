# Arnés 1.7.7 → 1.10.0 · Informe del implementer

Tarea de mantenimiento del arnés (no es feature de `features.json`). Rama
`chore/arnes-1.10.0`, nacida de `main` en `911657c`. Solo commits locales, sin push.

## Commits

| Commit | Bloque |
|---|---|
| `883c64a` | Lo que trae el instalador (`-Modo actualizar`, mixtos conservados) |
| `8fd5645` | Fusión a mano de los mixtos |
| `ad81a09` | Tests propios ajustados al criterio nuevo |
| `8ef361c` | `BACKLOG.md` regenerado (orden nuevo de columnas, F-070) |

**Paso 4 (F-162 a `human_review`), OMITIDO por orden del líder.** Lo había
cambiado en el árbol sin commit. Lo revertí con `git checkout -- harness/features.json`:
F-162 sigue en `in_progress` y `features.json` no cambia en esta rama.

## 1. Instalador

`.\instalar_arnes.ps1 -Destino <worktree> -Modo actualizar`, sin `-Forzar`.
Como no hay consola, cada mixto salió con «Sin consola de la que leer: se
CONSERVA», que es lo que se buscaba. La salida completa (`instalar.txt`) está
en el scratchpad de la sesión, fuera del repositorio.

- **Actualizados**: los 4 agentes, más el nuevo `qa-e2e.md`; `harness/*.py`;
  `rigor.json`, que no tenía afinado propio; `servicios.ejemplo.json`;
  `specs/SPECS.md`; `harness/VERSION`; `ARNES_VERSION.md`; los tests del payload.
- **Nuevos**: `cache_suites.py`, `carril.py`, `e2e.py`, `estados.py`,
  `mapa_tests.py`, `tiempos.py`, `pytest_arnes/`, `plantillas_e2e/` y 57 tests.
- **Conservados (mixtos)**: `CLAUDE.md`, `CHECKPOINTS.md`, `harness/init.sh`,
  `.claude/settings.json`, `docs/CONVENTIONS.md` y `docs/referencia/README.md`.
- **Protegidos**: `features.json`, `BACKLOG.md`, `ARCHITECTURE.md` y `current.md`.
- Aviso del instalador: la rama va 104 commits por detrás de `dev`. Es lo
  esperado aquí, porque `dev` es el espejo parado y `RAMA_BASE=main`.

### Lo propio que el instalador pisó en ficheros `arnes_puro`

Comparé el `911657c` con el payload 1.7.7 (`62acb62` de arnes-base) y con el
1.10.0. Las líneas que eran solo del proyecto:

- `harness/alcance.py`, `cobertura.py`, `mutacion.py` y `rutas_sensibles.py`:
  solo comentarios «(F-112)». Su lógica ya está en el genérico desde la 1.7.14,
  que nació aquí. No se pierde nada.
- `harness/backlog.py` y `tests/test_backlog_md.py`: versión anterior del
  tablero, sustituida por la de F-042/F-070. No se pierde nada.
- `tests/test_tamano.py` y `test_mutacion_env_al_worktree.py`: comentarios que
  citaban F-047. No se pierde nada.
- **`.claude/agents/leader.md`, sección «Ramas»**: era la versión de este
  repositorio. Decía que la integración va a `main`, que `dev` es un espejo
  (F-112), que **el espejo lo adelanta el HUMANO** y que el líder solo lo
  recuerda con el comando. La sustituye la genérica, que dice lo contrario: «la
  adelanta el líder **sin preguntar**». No la restauré, porque
  `test_f070_d3_la_rama_espejo_la_adelanta_el_lider` exige el texto nuevo. **Ver
  el riesgo R1.**
- `.claude/agents/reviewer.md`: la nota «`git diff main...HEAD` … era `dev`
  hasta F-112». El genérico ya dice `<base>` (la `RAMA_BASE`). No se pierde nada.

## 2. Fusión de los mixtos

Fusión a tres bandas con `diff3`: base, el payload 1.7.7 (`62acb62`); nuestra
parte, el proyecto; la otra, el payload 1.10.0. Así entran también los cambios
de la 1.7.8 a la 1.7.16 que las tablas de 1.8/1.9/1.10 no repiten.

| Fichero | Aceptado (genérico) | Conservado (propio) |
|---|---|---|
| `CLAUDE.md` | `qa-e2e` entre los subagentes; primera parada = resumen de la spec; ritmo con push del humano y la línea final; orden de prioridad de los ocho estados y «una activa»; regla `ARNES_SIN_CACHE=1`; «allí solo llegan merges»; regla dura nueva del push (F-070); protocolo del repositorio del ecosistema y las cuentas de GitHub | todo el mapa del repositorio, la autorización de subagentes, «Documentos que llegan de fuera», las reglas duras de Sigrid, Postgres y `.env`, y el LÍMITE DE RESPONSABILIDAD propio (no el «LÍMITE DE MICROSERVICIO» genérico) |
| `CHECKPOINTS.md` | todo lo genérico de 1.8/1.9/1.10: niveles con `express` y carriles, C1 `ARNES_SIN_CACHE`, C2 con los estados, C3 ter, C3 quater, C4 bis con el criterio de muerte, `indeterminado`, la casilla «reproducir a mano», RM2 con la media de la suite entera, PODADO y «Dos pasadas», e2e y la capa local | C3 bis tal cual (ya era genérico). La casilla de los dobles (1.7.9) ya estaba igual en los dos lados: único conflicto y sin diferencias |
| `harness/init.sh` | secciones 3 y 3 ter (F-042), 3b con aviso F-063, 7 bis con la caché (F-028), 7 quinquies (carril), 7 sexies (e2e), 1.7.14-1.7.16. `bash -n` OK | el bloque de configuración del proyecto (único conflicto): `PROYECTO_PYTHON=1`, `RUTAS_PYTHON`, `LINT_BLOQUEA=0`, `RAMA_BASE=main` con su historia de F-112. No había más líneas propias (comprobado: 0 perdidas y 0 duplicadas) |
| `.claude/settings.json` | `model` y `effortLevel: high`, `$adaptar` nuevo; fuera el hook `PostToolUse`; `ARNES_SIN_CACHE=1 bash harness/init.sh` y los ocho permisos del reviewer | hooks `SessionStart`/`SessionEnd` (`despierto_hook.sh`), el `Stop` y la allowlist previa. Fusión limpia |
| `docs/CONVENTIONS.md` | la viñeta de «Git» de F-070: merges a `dev` y a la rama espejo sin preguntar, a `main` preguntando, y el push siempre del humano | la viñeta de `dev` como espejo de `main` (F-112), que dice que **la adelanta el humano**. **Ver el riesgo R1** |
| `docs/referencia/README.md` | no cambia entre 1.7.7 y 1.10.0 | se queda igual |

**Cambio de estructura en `CLAUDE.md`.** Los tests de F-070 exigen el bloque
marcado `INICIO/FIN · ENTORNO DE RUESMA` con `### El ecosistema: azure-apps/`.
Las secciones propias «Los otros proyectos: `azure-apps/`» y «El arnés
genérico: `arnes-base`» pasan, **con su texto íntegro**, a ese bloque, al final
del fichero (como en el payload). Pasan a ser `###` dentro de «## Convenios del
entorno de Ruesma». El protocolo del ecosistema (`git pull --rebase`, solo el
documento propio, commit aparte, push del humano, PARAR ante un conflicto) y las
cuentas `ruesma-dev`/`pablogris` van dentro de la subsección de azure-apps.

## 3. Tests propios ajustados (`ad81a09`)

Pasar la suite tras la fusión dio 18 rojos en tests propios que fijaban
criterios viejos. Todos vienen de cambios que documenta la guía:

| Test | Criterio nuevo |
|---|---|
| `test_f020_r16_exit_5_es_superviviente` → `_es_indeterminado` | código 5 = INDETERMINADO (1.9.0, F-023): el caso que la guía cita |
| `test_f015_r7_mutante_que_no_compila_cuenta_como_muerto` → `_es_indeterminado` | lo que no compila es INDETERMINADO (F-023) |
| 6 de `test_f015_mutacion` (r1, r3, r7) | `if a > b:` da también `negacion`: 4 mutantes, no 3 (1.9.0, F-026) |
| `test_f015_r2_tests_y_no_python_quedan_fuera`, 4 de `test_f020_alcance` | `harness/` sale del alcance automático (1.7.8; guía, «El arnés sale del alcance») |
| 2 de `test_f015_rigor` r15 | la mutación de `estandar` es informativa (1.8.0, F-040); `critico` la sigue exigiendo |
| `test_f015_r19…` y `test_f020_r17…` (genericidad) | falsos positivos sobre código genérico: `cierre.toordinal()`/`.year`/`.isoformat()` (variable de fecha de `backlog.py`) y la variable `partes` de `mutacion.py`. El patrón `cierre\.` gana un lookahead que excluye esos métodos, y `partes` sale de la lista de palabras sueltas (mismo criterio que `cierre`) |
| 2 de `test_f020_init_multiservicio` | el bucle de servicios lleva dentro el de la caché (`done <<EOF_CACHE`, F-028), y la sección e2e (7 sexies) cita `servicios.json` en un comentario |

Las specs y reviews cerradas de F-015/F-020 siguen citando los nombres viejos.
No las toqué, porque son históricas.

## 4. Verificación

- `python harness/backlog.py` → «BACKLOG.md regenerado».
- Tests de textos y adaptados de 1.8/1.9/1.10 (`test_f070_*`, `test_f019_informe`,
  `test_f023_textos`, `test_f040_textos`, `test_f059_textos`, `test_f058_textos`,
  `test_f063_textos`, `test_f026_textos`, `test_f028_reviewer_sin_cache`,
  `test_f004_settings`, `test_estados`, `test_backlog_md`,
  `test_documentos_del_arnes`): **336 passed, 18 skipped en 17,9 s**. Todos los
  skips son «la guía es del taller», «rigor.json y la guía son del taller», «los
  adaptados son los del proyecto» o, en `test_f070_compatibilidad`, «sin rama
  `dev`».
- Tests propios del arnés, tras el ajuste: `test_f015_*`, `test_f020_*` y
  `test_f112_base_de_la_puerta` en verde (35 + 26 + 16 + 34 + 12 ejecutados por
  bloques, sin rojos).
- **Suite completa del worktree** (`python -m pytest -q -p no:cacheprovider tests`):
  **122 failed, 12893 passed, 2528 skipped en 2860 s (47 min 40 s)**. Desglose:
  - **112 por falta de `.env`** (`SigridApiSettings`: faltan `base_url` y
    `function_key`), en f006_comandos, f006_reglas, f024/f025_cli, f025_huella,
    f042, f047_guardian_puerta, f052, f066, f067, f078, f108, f118 y f132.
    Reproducido a mano en `check-frescura --help`, que sale con 1 y la
    ValidationError. Los que no imprimen la ValidationError siguen el mismo
    patrón (la CLI sale antes de llamar al doble), pero no los comprobé uno a uno.
    En la copia con `.env` del líder no deberían salir.
  - **1 mío, ya corregido**: `test_f003_r4` encontró un GUID en este informe (la
    ruta del scratchpad). La quité, y el test pasa en local.
  - **9 del arnés que NO arreglé (ver R6 y R7)**: 8 de
    `test_f019_por_defecto.py::test_f019_r19_el_cli_resuelve_y_pasa_la_seleccion`
    y `test_f019_tiempos.py::test_f019_r22_ningun_test_lanza_subprocesos_con_timeout_literal`.
    **El portero completo del líder dará rojo por ellos.**
- `bash harness/init.sh` completo: no se ejecutó. El worktree no tiene `.env`, así
  que daría rojo por eso. Lo pasa el líder fuera, en una copia con `.env`.

## 5. Riesgos y pendientes para el humano

- **R1 · ¿Quién adelanta el espejo `dev`? Contradicción abierta, no resuelta por
  mí.** El `leader.md` genérico (F-070, arnes_puro, vigilado por un test) dice
  que el líder hace el merge de la feature a `RAMA_BASE`, presentada como «`dev`
  (la `RAMA_BASE`)», sin preguntar; el de la rama espejo, sin preguntar; y el de
  `main`, preguntando. Aquí `RAMA_BASE` es `main` y el espejo es `dev`, y el
  `CONVENTIONS.md` propio (F-112, decisión del humano del 2026-09-26) dice que **el
  espejo lo adelanta el humano**. Ahora conviven las dos frases. Lectura prudente
  mientras se decide: el merge a `main` se pregunta, y `dev` lo adelanta el
  humano. Hay que elegir y dejar una sola versión en `CONVENTIONS.md`: (a)
  aceptar F-070 y quitar la viñeta de F-112, o (b) mantener F-112, y entonces
  `leader.md` contradice al proyecto hasta que el genérico admita «espejo
  adelantado por el humano».
- **R2**: `features.json` sin tocar. `python -m harness.estados --avisos` ya
  avisa (es un aviso, no un rojo): «F-162 tiene sdd: true y estado in_progress
  sin spec_aprobada». Al cerrarla, conviene anotar `spec_aprobada` y
  `ok_humano` en la rama donde el humano la pase a `done`.
- **R3**: el alcance automático ya no mide `harness/`. Una feature de este
  repositorio que toque el arnés deja de contar esas líneas en cobertura y
  mutación (1.7.8). Es lo previsto.
- **R4**: la mutación de `estandar` pasa a informativa (20 mutantes con semilla
  fija). Las campañas nuevas no son comparables con las anteriores (F-058).
- **R6 · `test_f019_r19` (8 rojos): fallo del payload, no del proyecto.** El
  test simula un alcance `dev..x` pero `mutacion.main` resuelve la base con
  `rama_base_configurada(raiz)`, que lee el `RAMA_BASE` del `init.sh` real del
  repositorio. Aquí es `main`, así que la cabecera del informe lleva `--base main`
  y el test espera el comando sin él. Solo pasa en repositorios con
  `RAMA_BASE=dev`. Es un test `arnes_puro`: si lo arreglo aquí, el instalador
  lo pisa en la siguiente actualización. **El arreglo va en arnes-base** (fijar
  `RAMA_BASE` en el test o leer la base desde `tmp_path`) y luego se reinstala.
  No lo improvisé.
- **R7 · `test_f019_r22` (1 rojo): 13 tests propios con `timeout=<literal>`.**
  `test_f006_relaciones`, `f006_unicidad`, `f011_alcance`, `f015_mutacion`,
  `f020_mutacion`, `f024_infra_alerta`, `f025_marcador`, `f042_check_cierres`,
  `f052_marcador`, `f128_diccionario`, `f128_restringida`, `f145_adjuntos_clave`
  y `f146_restringido_sin_contabilidad`. El barrido es textual (`timeout\s*=\s*\d`):
  junta subprocesos de verdad (p. ej. `f128_diccionario`, `subprocess.run(...,
  timeout=30)`), que sí deben pasar a `harness.tiempos.escalar_timeout`, con
  valores por defecto de funciones o argumentos de dobles (p. ej.
  `f006_relaciones`, `def _comprobar(..., timeout=30)`) cuyo literal comprueban
  los propios asserts. Separar unos de otros fichero a fichero es una decisión
  sobre trece features cerradas, y no la tomé. Opciones: (a) una feature corta
  que migre los subprocesos reales y ajuste el resto; (b) pedir en arnes-base
  que el barrido mire solo las llamadas a `subprocess`.
- **R5 (regla de propagación)**: los ajustes de los tests de genericidad son
  propios de este proyecto (sus listas de vocabulario). No hay nada que portar a
  arnes-base. La contradicción R1 sí merece una nota en arnes-base si se elige (b).
