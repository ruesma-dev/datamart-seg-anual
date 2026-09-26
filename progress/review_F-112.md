<!-- progress/review_F-112.md -->
Revisión incremental desde fe83de3 (pasada 2) · delta `fe83de3..85e5c26`

# F-112 · Review · la puerta de cobertura medía contra `dev`, parada

**Veredicto: CHANGES_REQUESTED.** Solo queda un cambio de texto: las tres
reglas nuevas sobre `dev` no dicen lo mismo sobre **quién** adelanta el espejo,
y una choca con una regla dura de `CLAUDE.md`. Código, tests, puertas y
mutación siguen aprobados desde la pasada 1.

**Nivel de rigor:** `estandar` (declarado). Exige RED, cobertura ≥ 80 % y
mutación sin supervivientes en `PENDIENTE`: cumplido en la pasada 1, y el delta
no toca código (`harness/*.py`, `init.sh` y `tests/` sin cambios desde
`fe83de3`), así que nada de lo aprobado se invalida.

## Lo que se ejecutó en esta pasada

- `bash harness/init.sh` tal cual en `feature/F-112-cobertura-contra-main`
  (HEAD `85e5c26`, árbol limpio): **exit 0**, `5562 passed, 203 skipped` en
  596,53 s; `PUERTA COBERTURA: 100.0% de 69 (69/69, umbral 80%; diff desde
  fb52d96e14, merge-base con main)`; `PUERTA TAMAÑO: impl 218/220, review
  140/140`; `ENTORNO LISTO`.
- Delta leído: `.claude/agents/leader.md`, `docs/CONVENTIONS.md`,
  `progress/current.md`, `progress/impl_F-112.md` (y mi propio informe, que el
  implementer commiteó). En `arnes-base`: el commit nuevo `2b7b373`
  (`leader.md` genérico y la línea en `GUIA_INSTALACION.md`).
- F-114 existe en `main` (`pending`, «Rescatar dos peticiones de `mcp-bbdd`
  que solo vivían en la rama `dev`»): la petición del líder de no exigir el
  rescate en esta rama está justificada.

## Estado de los cambios de la pasada 1

1. **Verificaciones MANUAL en `current.md`**: [x] atendido. Bloque con cuatro
   acciones y su comando exacto (primer adelantamiento de `dev`, las dos
   peticiones de `mcp-bbdd`, actualización 1.7.7 → 1.7.14, push de
   `arnes-base` `2c3a7fe..2b7b373`).
2. **Acceptance 3, decidido y escrito**: [x] atendido. Opción B del humano
   (`dev` espejo de `main`, ninguna feature nace de ella) escrita en
   `CONVENTIONS.md:78-83` y `leader.md:80-90`; `impl_F-112.md` la registra.
   **Pero** abre la incoherencia del cambio 1 de abajo.
3. **`CONVENTIONS.md`, «merge a dev»**: [x] ahora dice «merge a main».

## Checkpoints (solo lo que mueve el delta; el resto, como en la pasada 1)

- C1 [x] `init.sh` exit 0 (arriba).
- C2 [x] una sola `in_progress` · [x] rama correcta · [x] `current.md` añade
  solo lo de F-112.
- C3 [x] primera línea con ruta en los ficheros tocados · [ ] **coherencia de
  las convenciones**: ver cambio 1.
- C4 [x] verificaciones MANUAL listadas con comando exacto · [x] cada
  `acceptance` con su test (tabla de la pasada 1, intacta).
- C4 bis [x] sin cambios en el alcance medido: la campaña (`25795cc`) sigue
  valiendo por RM1; nada que volver a medir.
- C4 ter N/A: el repositorio no declara `harness/rutas_sensibles.json`.
- C5 N/A `tasks.md` (`sdd=false`, T0-T7 `[x]` en `current.md`) · [x] sin
  temporales · [x] `features.json` en `in_progress`, lo real hasta el cierre.

## Cambios requeridos

1. **¿Quién adelanta `dev`? Tres textos, tres respuestas, y una regla dura en
   contra.**
   - `.claude/agents/leader.md:87-90`: «**Paso del líder** en cada cierre…
     `git checkout dev && git merge --no-ff main`». El líder es un agente y
     haría un commit (de merge) en `dev`.
   - `CLAUDE.md:205-206`, regla dura no negociable: «Nunca commits directos a
     `dev` ni a `main`». Y `docs/CONVENTIONS.md:85-86`: «Los agentes solo hacen
     commit local en ramas feature. Push, merge a main y PRs: siempre el
     humano».
   - `progress/current.md` §F-112, Verificaciones MANUAL: el **humano** hace el
     primer adelantamiento, merge y push en el mismo comando.

   El próximo líder, al cerrar una feature, o incumple un PROHIBIDO de
   `CLAUDE.md` o se salta el paso que le manda `leader.md`: es exactamente
   como `dev` acabó parada. Elegir UNA de estas dos y escribirla igual en los
   tres sitios:
   - (a) **El humano adelanta `dev`** tras cada merge a `main`: `leader.md`
     dice que el líder se lo **recuerda** con el comando, sin ejecutarlo; es
     coherente con «merge… siempre el humano» y no toca `CLAUDE.md`.
   - (b) **El líder lo hace**: entonces `CLAUDE.md:205-206` y
     `CONVENTIONS.md:85-86` llevan la excepción explícita («salvo el merge de
     `main` en el espejo `dev`, que hace el líder al cerrar»), y esa excepción
     la tiene que autorizar el humano, porque es una regla dura.

   Lo mismo en `arnes-base` (`2b7b373`): su `leader.md` genérico dice «adelantarla
   es un paso del líder» y su `CLAUDE.md:132-133` y `docs/CONVENTIONS.md:48-49`
   dicen lo contrario. Corregirlo allí con la misma opción, en un commit local
   más de la 1.7.14.

## Observaciones (no bloquean)

- `current.md` §F-112 dice de las dos peticiones de `mcp-bbdd` «NO se han
  fichado»; en `main` ya son F-114. Al integrar F-112 en `main`, el líder
  debería dejar esa línea apuntando a F-114 para que no parezcan perdidas.
- De la pasada 1 siguen en pie, fuera de los `acceptance`: el texto del
  diagnóstico culpa a la base cuando lo rezagado es la rama nacida de `dev`;
  una rama nacida de otra feature sin integrar y una rama integrada por
  fast-forward siguen sin detectarse (aquí se integra con `--no-ff`).
  Candidatos a encargo en `arnes-base`.
- `init.sh` se ejecutó en el árbol principal, donde está la rama: el worktree
  de esta sesión (`.claude/worktrees/agent-a7e46bca863639aea`) no tiene la
  rama y está bloqueado por otra sesión; ejecutarlo allí en HEAD separado
  habría dado la puerta de cobertura en N/A. Árbol principal limpio antes y
  después, salvo este informe.

## Pasada 1 (resumen; el informe completo, en `git show 85e5c26:progress/review_F-112.md`)

Revisión completa de `git diff main...HEAD` en `fe83de3`: init.sh verde
(5562 passed). Los seis puntos del líder:
- **Base.** `RAMA_BASE=main` es la única fuente, sin agujero en rama desde
  `dev`, merge de `dev`, merges ajenos ni rama integrada (sonda propia en
  repos desechables).
- **Sigue fallando cuando debe.** Bajo el umbral da código 1
  (`test_f015_r10_exit_1_bajo_el_umbral` y la sonda).
- **Porte 1.7.14.** Genérico y propagado por el instalador en `-SoloDiff`.
- **Remedición.** F-107..F-110 recalculadas: ninguna bajo el 80 %.
- **`dev` intacta** (`a1845db`).
- **Mutación.** Recálculo 191 líneas y 27 mutantes, coincide; los dos
  supervivientes rehechos en copia (RM4), ahora muertos; RM1, RM2 y RM6 [x];
  campaña no reejecutada, 3.611,7 s según el informe.

| # | Acceptance | Estado |
|---|---|---|
| 1 | Puertas contra `main` | [x] tests r1/r2 de `test_f112_base_de_la_puerta.py` |
| 2 | Test que falla con base rezagada | [x] `r2_en_este_repositorio_la_base_no_esta_rezagada` (rojo real con `dev`) |
| 3 | Decidido y escrito qué se hace con `dev` | [x] decidido (opción B); escrito con la incoherencia del cambio 1 |
| 4 | Porte a `arnes-base` y versión | [x] 1.7.14, más `2b7b373`, que arrastra la misma incoherencia |
| 5 | Remedición F-107..F-110 | [x] ninguna bajo el umbral |
