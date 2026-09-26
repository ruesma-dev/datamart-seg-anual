<!-- progress/review_F-112.md -->
Revisión incremental desde 85e5c26 (pasada 3) · delta `85e5c26..c14c8ab`

# F-112 · Review · la puerta de cobertura medía contra `dev`, parada

**Veredicto: APPROVED.**

**Nivel de rigor:** `estandar` (declarado en `features.json`). Exige fase RED,
cobertura de líneas cambiadas ≥ 80 % y campaña de mutación sin supervivientes
en `PENDIENTE`. Todo cumplido en la pasada 1. Desde entonces ningún delta ha
tocado código: `harness/*.py`, `harness/init.sh` y `tests/` no cambian desde
`fe83de3`, así que la campaña medida en `25795cc` sigue valiendo (RM1).

## Pasada 3 · lo que se ejecutó y se leyó

- `bash harness/init.sh` tal cual en `feature/F-112-cobertura-contra-main`
  (HEAD `c14c8ab`, árbol limpio): **exit 0**, `5562 passed, 203 skipped` en
  581,86 s. `PUERTA COBERTURA: 100.0% de 69 (69/69, umbral 80%; diff desde
  fb52d96e14, merge-base con main)`. `PUERTA TAMAÑO: impl 218/220, review
  127/140`. `ENTORNO LISTO`.
- Delta (`b29e259`, `2a83f04`, `c14c8ab`): solo texto, en `leader.md`,
  `CONVENTIONS.md`, `current.md` e `impl_F-112.md`, más el commit de mi informe
  de la pasada 2. En `arnes-base`: `aa8f85a` (`leader.md` genérico y la línea
  de ficheros de la 1.7.14 en `GUIA_INSTALACION.md`).

## Cambio de la pasada 2 · ¿quién adelanta `dev`?

[x] **Atendido con la opción (a), y coherente en todos los sitios:**
- `.claude/agents/leader.md:87-91`: «El espejo lo adelanta el HUMANO, no un
  agente». Invoca la regla dura. El líder se lo **recuerda** en la PARADA 2 con
  el comando exacto.
- `docs/CONVENTIONS.md:79-84`: lo adelanta el humano y el líder se lo
  recuerda. Casa con `:85-86`: los agentes solo hacen commit en ramas feature,
  y el merge es del humano.
- `CLAUDE.md:205-206` (nunca commits directos a `dev` ni a `main`): sin tocar
  y ya sin contradicción.
- `progress/current.md` §F-112, MANUAL: el primer adelantamiento lo hace el
  humano, con merge y push en un mismo comando, igual que en los otros dos
  sitios.
- `arnes-base` `aa8f85a`: el `leader.md` genérico dice lo mismo, con
  `<espejo>`/`<RAMA_BASE>` en vez de nombres de rama. Ahora casa con su
  `CLAUDE.md:132-133` y su `docs/CONVENTIONS.md:48-49`. Commit local, sin push.

La observación de la pasada 2 también está atendida: `current.md` marca `[x]`
las dos peticiones de `mcp-bbdd`, rescatadas como F-114 en `main` (`01193f1`).

## Checkpoints

- C1 [x] `init.sh` exit 0 · [x] ficheros del arnés presentes.
- C2 [x] una sola `in_progress` (F-112) · [x] rama `feature/F-112-...` ·
  [x] `current.md`: F-112 solo añade su sección · N/A `history.md`: F-112 aún
  no está `done`, la entrada llega al cerrarla.
- C3 [x] todo en `harness/`, `tests/` y documentos del arnés, sin dominio ·
  [x] primera línea con ruta · [x] sin prints ni secretos. El único aviso de
  ruff en lo tocado (N818, `rutas_sensibles.py:57`) ya estaba en `main` ·
  [x] convenciones coherentes entre sí (cerrado en esta pasada) · N/A
  semántica Sigrid: no toca el ETL.
- C3 bis N/A: no entra ningún documento de fuera.
- C4 [x] cada `acceptance` con test (tabla abajo) · [x] sin red ni BBDD: git
  local en `tmp_path` y lecturas del propio repositorio · [x] no introduce
  dobles · [x] verificaciones MANUAL en `current.md` con su comando exacto.
- C4 bis [x] rigor declarado · [x] RED con salida real (9 rojos contra stubs
  en `ea6f454`, y el rojo en el repositorio real «552 de los 554 ya están en
  main») · [x] cobertura 100 % (69/69) · [x] mutación: 27 generados, 20
  evaluados (muestreo `estandar`), 18 muertos, 2 supervivientes analizados y
  muertos después con tests endurecidos, 0 timeouts, 0 sin veredicto ·
  [x] campaña no reejecutada: 3.611,7 s (60 min) según el informe. Recálculo
  puro propio: 191 líneas y 27 mutantes, coinciden · [x] RM1, RM2, RM3 y RM6 ·
  N/A RM5, porque el rigor es `estandar` · [x] RM4 hecho sobre una copia: cada
  superviviente pone ahora su test en rojo · [x] «Evidencias» completa.
- C4 ter N/A: el repositorio no declara `harness/rutas_sensibles.json`.
- C5 N/A `tasks.md` (`sdd=false`); T0-T7 están `[x]` en `current.md` con
  commits `F-112 Tn:` · [x] sin temporales · [x] `features.json` en
  `in_progress` hasta que el líder lo cierre.

## Cobertura acceptance → test

| # | Acceptance | Evidencia |
|---|---|---|
| 1 | Puertas contra `main` | `r1_contra_main_el_alcance_es_solo_de_la_rama`, `r2_puerta_cobertura_mide_solo_la_rama_contra_main`, `r2_sin_base_explicita_se_usa_la_de_init_sh`, `r2_este_repositorio_integra_en_main`, `r2_init_sh_pasa_la_base_configurada_a_las_dos_puertas`, `r2_puerta_rutas_sensibles_ko_con_la_base_rezagada` |
| 2 | Test que falla con base rezagada | `r2_en_este_repositorio_la_base_no_esta_rezagada` (rojo real con `dev`), `r1_diagnostico_base_rezagada`, `r2_puerta_cobertura_ko_con_la_base_rezagada` |
| 3 | Decidido y escrito qué se hace con `dev` | Opción B del humano (espejo, lo adelanta el humano), escrita igual en `leader.md`, `CONVENTIONS.md` y `current.md` |
| 4 | Porte a `arnes-base` y versión | 1.7.14 (`2c3a7fe`..`aa8f85a`), `VERSION` y guía; `tests/test_base_de_la_puerta.py`; instalador `-SoloDiff` verificado |
| 5 | Remedición F-107..F-110 | Recalculada: F-107 y F-110 sin líneas ejecutables, F-109 sin `.py` de producción, F-108 al 100 %. Ninguna bajo el 80 % |

## Historial de pasadas (detalle en `git show <sha>:progress/review_F-112.md`)

- **Pasada 1** (`fe83de3`, CHANGES_REQUESTED, solo documental). Código y
  puertas aprobados:
  - `RAMA_BASE=main` es la única fuente.
  - Sonda propia en repositorios desechables: rama nacida de `dev` o que
    mergea `dev` → rojo; merges ajenos y rama integrada → bien medidos; por
    debajo del umbral → código 1.
  - Porte genérico y propagable.
  - Remedición recalculada y `dev` intacta.
  - Faltaban la lista MANUAL, la decisión sobre `dev` y la línea «merge a
    dev» de `CONVENTIONS.md`.
- **Pasada 2** (`85e5c26`, CHANGES_REQUESTED). Lo de la pasada 1 quedó
  atendido, pero `leader.md` mandaba al líder hacer el merge en `dev`, en
  contra de `CLAUDE.md` y `CONVENTIONS.md`, y lo mismo en `arnes-base`.

## Observaciones (no bloquean; candidatos a encargo en `arnes-base`)

- El texto del diagnóstico culpa a «la base» también cuando lo rezagado es la
  rama nacida de `dev`. El rojo es correcto; el texto se puede mejorar.
- Siguen sin detectarse, igual que antes de F-112 y fuera de sus `acceptance`:
  - una rama nacida de otra feature sin integrar;
  - una rama integrada por fast-forward.

  Aquí se integra con `--no-ff`.
- `init.sh` se ejecutó en el árbol principal, que es donde está la rama. El
  worktree de esta sesión está bloqueado, en HEAD separado, y ahí la puerta
  habría salido N/A.

**Automejora (no aplicada):** en `reviewer.md`, si la feature cambia la
puerta que la revisa, pedir una sonda en repositorio desechable con los casos
límite. Fue lo que en la pasada 1 separó «tests verdes» de «sin agujero».
