<!-- progress/review_F-112.md -->
Revisión completa (pasada 1) · `git diff main...HEAD`, HEAD `fe83de3`

# F-112 · Review · la puerta de cobertura medía contra `dev`, parada

**Veredicto: CHANGES_REQUESTED** (solo documental: código y verificación bien;
falta dejar a la vista del humano lo que queda en sus manos).

**Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED,
cobertura de líneas cambiadas ≥ 80 % y campaña de mutación sin supervivientes
en `PENDIENTE`. `sdd=false`: se revisa contra los 5 `acceptance`.

## Lo que se ejecutó

- `bash harness/init.sh` tal cual: **exit 0**, `5562 passed, 203 skipped` en
  824,55 s; `PUERTA COBERTURA: 100.0% de 69 líneas (69/69, umbral 80%; diff desde
  fb52d96e14, merge-base con main)`. La puerta de rutas sensibles no imprime
  línea: el repositorio no tiene `harness/rutas_sensibles.json`.
- Sonda propia en repos git desechables (scratchpad): (1) cobertura 2/4 con
  base sana y git real → **código 1**; (2) rama nacida de `dev` y (3) feature
  que mergea `dev` → **rojo**; (4) feature que mergea `main` → sana, alcance
  solo suyo; (5) rama nacida de otra feature sin integrar y (6) rama integrada
  por fast-forward → no detectados (previo a F-112: ver observaciones).
- Instalador `-Modo actualizar -SoloDiff` contra este repo: v1.7.7 → v1.7.14;
  en las piezas de F-112 solo difieren comentarios (`F-112` → `1.7.14`) y el
  test genérico sale `[NUEVO]`: propaga. Árbol limpio después.

## Los seis puntos del líder

1. **Base única y sin agujero en los casos pedidos.** `RAMA_BASE=main`
   (`init.sh:34`) y las tres CLI la leen con `rama_base_configurada()` cuando
   no hay `--base`; `init.sh:492` y `:520` la pasan explícita (test
   `..._init_sh_pasa_la_base_configurada_a_las_dos_puertas`). Los defectos
   `base="dev"` que quedan (`alcance.py:253,403`, `rutas_sensibles.py:259,309`)
   son de funciones de biblioteca; todos los llamadores de producción pasan la
   base. `diagnosticar_base()` caza rama desde `dev`, merge de `dev` y base
   inexistente; los merges ajenos no cuentan (`--no-merges`), y
   `merge_que_integra()` descarta los merges de otras features y la rama sobre
   la línea principal (tests r5, verdes).
2. **Falla cuando debe.** `test_f015_r10_exit_1_bajo_el_umbral` recorre el
   `cobertura.main` modificado (fuera de git el diagnóstico devuelve `None`) y
   sigue en verde; mi sonda 1 lo confirma con git real y base sana.
3. **Porte 1.7.14.** Genérico (sin features ni Sigrid en código ni tests; el
   defecto genérico sigue `dev` con el aviso «si integras en main, pon main»),
   `arnes-base/harness/VERSION` = 1.7.14 / 2026-09-26, sección en
   `GUIA_INSTALACION.md` con caso, AVISO del rojo nuevo y qué revisar. Número
   1.7.14 justificado (1.7.11-13 son encargos). Commits locales, sin push.
   Aquí `harness/VERSION` sigue 1.7.7 con el cambio a mano: correcto no
   editarlo; aplicar la actualización completa queda para el humano.
4. **Remedición.** Recalculada por mi cuenta: F-107 (`d26f843`) 14 líneas y
   **0 ejecutables**; F-110 (`b40f012`) 27 y **0**; F-109 (`42d4b05`) sin `.py`
   de producción; F-108 (`79a4505`) 238 líneas en 5 ficheros (yo cuento 88
   ejecutables por AST frente a sus 84 de `coverage.json`: diferencia de
   criterio de sentencia, no cambia nada). **Ninguna por debajo de 80 %.**
5. **`dev` intacta**: `dev` = `origin/dev` = `a1845db`, reflog sin entradas
   nuevas. La propuesta (retirarla, rescatando antes dos peticiones que solo
   viven allí) está escrita como decisión del humano en `impl_F-112.md` y
   `CONVENTIONS.md:77-80`… pero **no en `progress/current.md`** (cambio 1).
6. **Mutación**: ver C4 bis.
## Checkpoints

- C1 [x] init.sh exit 0 · [x] ficheros del arnés presentes.
- C2 [x] una sola `in_progress` (F-112) · [x] rama `feature/F-112-...` ·
  [x] `current.md`: F-112 añade solo su sección; el tamaño (2.315 líneas con
  sesiones anteriores) es deuda previa, no de esta feature · N/A `history.md`:
  F-112 no está `done`.
- C3 [x] capa: todo en `harness/` y `tests/`, sin tocar dominio · [x] primera
  línea con ruta en el test nuevo · [x] sin prints ni secretos (el único aviso
  de ruff, N818 en `rutas_sensibles.py:57`, ya existía en `main`) · N/A
  semántica Sigrid: no toca el ETL.
- C3 bis N/A: no entra ningún documento de fuera.
- C4 [x] cada `acceptance` con test (tabla abajo) · [x] sin red ni BBDD (git
  local en `tmp_path` y lecturas del propio repo) · [x] no introduce dobles ·
  **[ ] verificaciones MANUAL en `current.md`**: las tres acciones del humano
  (decidir `dev` y las dos peticiones perdidas, actualización 1.7.7→1.7.14,
  push de `arnes-base`) solo constan en `impl_F-112.md`.
- C4 bis [x] rigor declarado · [x] **RED** con salida real (9 rojos contra
  stubs, `ea6f454`, y el rojo del repo real «552 de los 554 ya están en main») ·
  [x] **cobertura** 100 % (69/69) · [x] **mutación**: 27 generados, 20
  evaluados (muestreo `estandar`), 18 muertos, 2 supervivientes, 0 timeouts,
  0 sin veredicto, sin cabecera de campaña no válida · [x] **campaña no
  reejecutada: 3.611,7 s (60 min) según el informe**; recálculo puro propio:
  alcance **191 líneas** (131/38/7/15) y **27 mutantes**, coinciden; los dos
  supervivientes existen tal cual (`cobertura.py:167/168`, operador `entero`,
  `[:10]`→`[:11]`) · [x] coste por mutante 3.611,7×3/20 = 541,8 s ≥ suite ·
  [x] RM1: medido en `25795cc`; de ahí a HEAD solo cambian `tests/` y
  `progress/`, el alcance es el mismo · [x] RM2: media 180,6 s frente a línea
  base 518-531 s (0,34, sin salto de orden) y 20×180,6 = 3.612 ≈ total ·
  [x] RM3: ningún equivalente declarado · N/A RM5 (rigor `estandar`) · [x] RM6:
  no se quitó ninguna guarda; los dos se matan endureciendo tests · [x] RM4
  aplicado: sobre una COPIA en el scratchpad, cada mutante pone en rojo su test
  (`1 failed, 18 passed`) y restaurado, verde · [x] supervivientes analizados,
  ninguno `PENDIENTE` · [x] «Evidencias» con los cuatro números y los workers.
- C4 ter N/A: sin `harness/rutas_sensibles.json`, no hay rutas declaradas.
- C5 N/A `tasks.md` (`sdd=false`): T0-T7 en `current.md`, todas `[x]`, con
  commits `F-112 Tn:` · [x] sin temporales sin trackear · [x] `features.json`
  en `in_progress`, que es lo real hasta el cierre.

## Cobertura acceptance → test

| # | Acceptance | Tests (todos verdes) |
|---|---|---|
| 1 | Las dos puertas miden contra `main` | `r1_contra_main_el_alcance_es_solo_de_la_rama`, `r2_puerta_cobertura_mide_solo_la_rama_contra_main`, `r2_sin_base_explicita_se_usa_la_de_init_sh`, `r2_este_repositorio_integra_en_main`, `r2_init_sh_pasa_la_base_configurada_a_las_dos_puertas`, `r2_puerta_rutas_sensibles_ko_con_la_base_rezagada` |
| 2 | Un test falla si la base está por detrás | `r2_en_este_repositorio_la_base_no_esta_rezagada` (su rojo real con `dev`, en el informe), `r1_diagnostico_base_rezagada`, `r2_puerta_cobertura_ko_con_la_base_rezagada` |
| 3 | Decidido y escrito qué se hace con `dev` | **Escrito como propuesta; sin decidir** (decisión del humano: cambio 2) |
| 4 | Portado a `arnes-base`, versión anotada | `arnes-base/tests/test_base_de_la_puerta.py` (18+1 skip según el informe); `-SoloDiff` verificado por mí |
| 5 | Remedida F-107..F-110 | tabla del informe, recalculada arriba; tests r5 del alcance por merge |

## Cambios requeridos

1. `progress/current.md`, sección F-112 (tras la l. 29): añadir un bloque
   «Verificaciones MANUAL (humano)» con cada acción y su **comando exacto**:
   (a) rescatar o descartar las dos peticiones de mcp-bbdd que solo viven en
   `dev` (`git show a1a3df2 a1845db -- harness/features.json`); (b) si se
   retira `dev`: `git tag archivo/dev-2026-09-03 a1845db` y `git branch -d dev`
   (la remota, solo con push autorizado); (c) actualización completa del arnés:
   `.\instalar_arnes.ps1 -Destino "<este repo>" -Modo actualizar`; (d) push de
   `arnes-base` (`2c3a7fe`..`ab0df0f`). Sin esto, el riesgo de perder esas dos
   peticiones depende de que alguien relea un informe de implementer.
2. Acceptance 3 dice «**Decidido** y escrito». Hoy es una propuesta. El líder
   debe obtener la decisión del humano y dejarla escrita en
   `docs/CONVENTIONS.md:77-80` (sustituir «lo decide el humano») y en
   `.claude/agents/leader.md:80-81`, que aún dice que `dev` «se mantiene como
   espejo», cosa que nadie hace desde el 03-09. Si el humano prefiere cerrar
   F-112 con la decisión aplazada, que conste así en `current.md`.
3. `docs/CONVENTIONS.md:82`: «merge a dev» → «merge a main» (la sección que
   F-112 reescribe se contradice).

## Observaciones (no bloquean)

- El diagnóstico culpa a la base («la base «main» se ha quedado por detrás»)
  también cuando lo rezagado es la rama nacida de `dev`: rojo correcto, texto
  mejorable.
- Huecos previos, fuera de los `acceptance`: rama nacida de otra feature sin
  integrar (mide líneas ajenas sin avisar) y rama integrada por fast-forward
  (diff vacío). Aquí se integra con `--no-ff`. Candidatos a encargo en
  `arnes-base`, igual que nombrar en la guía el rojo de un clon sin `main` local.

**Automejora (no aplicada):** en `reviewer.md`, si la feature cambia la puerta
que la revisa, pedir una sonda en repo desechable con los casos límite.
