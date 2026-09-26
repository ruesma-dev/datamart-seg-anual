# F-112 · Informe del implementer · la puerta de cobertura medía contra `dev`, parada

Rama `feature/F-112-cobertura-contra-main` (desde `main` fb52d96). `sdd=false`,
rigor `estandar`. Tareas derivadas de los cinco `acceptance` (T0-T7 en
`progress/current.md`). Commits: `3994de9` T0, `ea6f454` T1 (RED), `57c2ab7` T2,
`2e1b4cd` T3, `472429b` T4, `f5cb73e` T5, `959c959` T6, `25795cc`/`90e787e`/
`3912100`/`48499f4` T7 (informe y tests de huecos), y el del cierre. En
`arnes-base`: `2c3a7fe`, `fac838a`, `c5666fc`, `ab0df0f` (1.7.14), commits
locales en `main`, sin push.

## Qué cambió

| Fichero | Cambio | Acceptance |
|---|---|---|
| `harness/init.sh` | `RAMA_BASE=main` (era `dev`), con el porqué en el comentario | 1 |
| `harness/alcance.py` | `rama_base_configurada()` lee `RAMA_BASE` de `init.sh` (única fuente; `dev` solo como último recurso); `diagnosticar_base()` dice si el diff de la puerta traería commits que ya viven en otra rama de larga vida (`main`, `master`, `dev`, `develop`) o si la base no existe; `merge_que_integra()` y `resolver_refs`: una rama ya integrada se mide por su merge (antes, diff vacío) | 1, 2, 5 |
| `harness/cobertura.py` | `--base` por defecto = `RAMA_BASE`; KO con el motivo si la base está rezagada; la línea dice contra qué midió (`diff desde <sha>, merge-base con main`) | 1, 2 |
| `harness/rutas_sensibles.py` | mismo defecto de `--base` y mismo KO en `evaluar_puerta` | 1, 2 |
| `harness/mutacion.py` | `--base` por defecto = `RAMA_BASE` (antes `dev` cableado) | 1 |
| `tests/test_f112_base_de_la_puerta.py` | 20 tests offline (repo git de juguete en `tmp_path` + 2 lecturas git del propio repo) | 1, 2, 5 |
| `.claude/agents/reviewer.md`, `docs/CONVENTIONS.md` | la primera pasada del reviewer es `git diff main...HEAD`; el modelo de ramas es `main` ← `feature/*`, `dev` parada y pendiente de decisión | 1, 3 |
| `harness/features.json`, `BACKLOG.md`, `progress/current.md` | ficha `in_progress`, backlog regenerado, seguimiento | — |

## Decisiones de diseño

1. **La base es el merge-base con la rama configurada, no una rama fija.**
   `harness.alcance` ya calculaba `merge-base(base, rama)..rama`; lo roto era la
   base (`dev`). Se deja `RAMA_BASE` en `init.sh` como ÚNICA fuente (es el
   fichero que el instalador pregunta antes de pisar, así que la adaptación
   sobrevive a una actualización) y las tres herramientas la leen de ahí cuando
   se lanzan a mano. No se renombró la variable: renombrarla rompía los
   `init.sh` ya adaptados de otros proyectos.
2. **Qué es «base por detrás» y por qué se mira así.** No basta con «`dev` es
   ancestro de `main`»: aquí `dev` NO es ancestro de `main` (tiene 2 commits
   propios, ver «dev»). El criterio operativo es el que importa para la puerta:
   de los commits (sin merges) que se medirían desde el merge-base, ¿cuántos ya
   están en otra rama de larga vida? Si alguno, la puerta mediría trabajo ajeno
   → **KO con número y rama**. Los merges no cuentan para no dar un falso rojo
   con el merge de release de un flujo `main` ← `dev`. Medido hoy con la base
   vieja: «552 de los 554 ya están en «main»» (traza abajo).
3. **Base inexistente = rojo.** Antes, sin la rama base, `git diff` fallaba, el
   alcance salía vacío y la puerta declaraba N/A en silencio. Fuera de un repo
   git el diagnóstico no dice nada (las puertas ya declaran su N/A).
4. **Rama ya integrada → su merge.** Con base `main`, `merge-base(main, rama)`
   de una rama ya mergeada es su propia punta y el diff sale vacío: remedir o
   mutar una feature cerrada no medía nada. Ahora se busca por ascendencia (no
   por el mensaje) el merge de la línea principal que la integró y se mide
   `merge^1..merge`. La búsqueda por mensaje (`--grep F-XXX`) queda para ramas
   borradas, y es frágil: para F-107 y F-109 el merge más reciente que las
   menciona es un `chore` posterior (`2eca21c`, `fb52d96`), no su merge.
5. **La línea de la puerta dice contra qué midió.** F-110 y F-109 dieron la
   misma cifra al decimal y nadie podía verlo; ahora sale el sha del merge-base.
6. **`mutacion.py` solo cambia el defecto de `--base`**, sin el diagnóstico:
   meterlo en `main` obligaba a tocar los dobles de sus ~20 ficheros de tests.
   La puerta de `init.sh` ya para una base rezagada antes de que nadie mute.
7. **Real-repo test**: `test_f112_r2_en_este_repositorio_la_base_no_esta_rezagada`
   diagnostica HEAD contra `RAMA_BASE`; se salta en una rama de larga vida
   (allí la puerta es N/A y compararía `main` con `dev`) y sin la rama base.

## Fase RED (trazas reales)

Tests escritos antes que el código, contra stubs que reproducían el
comportamiento de antes (`rama_base_configurada` → `"dev"`, `diagnosticar_base`
→ `None`; commit `ea6f454`). Comando exacto:
`.venv/Scripts/python -m pytest tests/test_f112_base_de_la_puerta.py -q --tb=line -p no:cacheprovider`

```
..F.F.FFFFFF..F.                                                         [100%]
tests/test_f112_base_de_la_puerta.py:189: assert None is not None
tests/test_f112_base_de_la_puerta.py:206: assert (None is not None)
tests/test_f112_base_de_la_puerta.py:224: AssertionError: PUERTA COBERTURA: 100.0% de 6 líneas cambiadas cubiertas (6/6, umbral 80%, nivel estandar)
    assert 0 == 1
tests/test_f112_base_de_la_puerta.py:240: AssertionError: assert 'd8a6b18866' in 'PUERTA COBERTURA: 100.0% de 2 líneas cambiadas cubiertas (2/2, umbral 80%, nivel estandar)\n'
tests/test_f112_base_de_la_puerta.py:249: AssertionError: assert 'de 2 líneas cambiadas' in 'PUERTA COBERTURA: 100.0% de 6 líneas cambiadas cubiertas (6/6, umbral 80%, nivel estandar)\n'
tests/test_f112_base_de_la_puerta.py:269: AssertionError: assert ('main' in 'PUERTA RUTAS SENSIBLES [prompts]: FALTA la evidencia de 1 ruta(s) sensible(s) tocada(s):\n      - app/ajeno.py (prompt de IA)\n ...')
tests/test_f112_base_de_la_puerta.py:280: AssertionError: assert 'dev' == 'trunk'
tests/test_f112_base_de_la_puerta.py:286: AssertionError: assert 'dev' == 'main'
tests/test_f112_base_de_la_puerta.py:325: AssertionError: assert ('426b0db1503...00-x', 'rama') == ('73d9db7b6ab...651', 'merge')
FAILED ...::test_f112_r1_diagnostico_base_rezagada
FAILED ...::test_f112_r1_diagnostico_base_inexistente
FAILED ...::test_f112_r2_puerta_cobertura_ko_con_la_base_rezagada
FAILED ...::test_f112_r2_puerta_cobertura_mide_solo_la_rama_contra_main
FAILED ...::test_f112_r2_sin_base_explicita_se_usa_la_de_init_sh
FAILED ...::test_f112_r2_puerta_rutas_sensibles_ko_con_la_base_rezagada
FAILED ...::test_f112_r2_rama_base_configurada_sale_de_init_sh
FAILED ...::test_f112_r2_este_repositorio_integra_en_main
FAILED ...::test_f112_r5_rama_integrada_se_mide_por_el_merge_que_la_integro
9 failed, 7 passed in 10.35s
```

La línea 224 es el defecto en estado puro: contra `dev`, la puerta de antes
salía **verde (100 % de 6 líneas)** habiendo medido 4 líneas que no eran de la
rama. Y el test del propio repositorio, con `diagnosticar_base` ya escrito y
`init.sh` todavía en `dev` (entre T2 y T3), sobre el repositorio real:

```
.venv/Scripts/python -m pytest "tests/test_f112_base_de_la_puerta.py::test_f112_r2_en_este_repositorio_la_base_no_esta_rezagada" -q --tb=line -p no:cacheprovider
tests/test_f112_base_de_la_puerta.py:310: AssertionError: assert 'la base «dev» se ha quedado por detrás: de los commits que se medirían desde su merge-base con HEAD, 552 de los 554 ya están en «main» y no son de esta rama. Pon en RAMA_BASE (harness/init.sh) la rama donde se integra el trabajo' is None
1 failed in 0.55s
```

VERDE tras T3 (mismo comando): `16 passed in 16.66s`; con los 4 de T7, `20 passed in 28.06s`. Suites vecinas del arnés
(`test_f015_*`, `test_f020_*`, `test_mutacion_informe`, cobertura de F-006 y
F-052): `140 passed`, sin tocar ninguna.

## Qué se hace con `dev` (DECISIÓN DEL HUMANO; no se ha tocado)

Estado medido hoy: `dev` = `origin/dev` = `a1845db` (2026-09-03). Le faltan 552
commits sin merge de `main`, y tiene **2 commits que `main` no tiene**
(`a1a3df2`, `a1845db`): la «Petición desde mcp-bbdd» con dos avisos que este
proyecto no publica, fichados allí como F-057 y F-058 (regla del aviso de las
columnas `_raw`; orden de magnitud de `stg.presupuesto`, ~13,6 M de filas). En
`main` esos números son otras features (F-057 = esquema `personal`) y **no
encuentro esas dos peticiones en el backlog de `main`** ni por título ni por
contenido: si nadie las rescató por otra vía, están perdidas en `dev`.

Propuesta: **retirar `dev`**, en este orden: (1) rescatar las dos peticiones a
`features.json` de `main` con números nuevos (o descartarlas a sabiendas);
(2) etiquetar la punta para no perder nada (`git tag archivo/dev-2026-09-03
a1845db`); (3) borrar `dev` local y, con push autorizado, la remota. Con
`RAMA_BASE=main` y el diagnóstico nuevo, mantenerla ya no rompe la puerta (una
`dev` parada solo daría rojo si una feature naciera de ella), pero sigue
invitando a crear ramas desde código de hace tres semanas, que es lo que
`leader.md` ya advierte. Alternativa: mantenerla como espejo y adelantarla a
`main` tras cada cierre, lo que exige un merge (no es fast-forward por esos 2
commits) y un paso más en cada cierre que nadie ha hecho desde el 03-09.
Nota: `arnes-base` también tiene una rama `dev` local y remota; no la he mirado.

## Porte a `arnes-base` (1.7.14)

Commit `2c3a7fe` en `arnes-base` (`main`, local, sin push; no toqué `codex/` ni
`instalar_arnes_dual.ps1`, que estaban sin versionar y no son míos). Portado
**pieza a pieza** (este proyecto va por la 1.7.7 y el payload por la 1.7.10):
el mismo parche de `alcance.py`, `cobertura.py` y `rutas_sensibles.py` aplicó
limpio con `git apply --directory=arnes-base`; `mutacion.py` a mano
(`BASE_POR_DEFECTO` pasa a ser el último recurso); `init.sh` solo el comentario
de `RAMA_BASE` (el defecto genérico sigue siendo `dev`); `reviewer.md` genérico;
test `tests/test_base_de_la_puerta.py` (el mío sin el caso propio de este
proyecto y sin citar features, regla de la 1.7.5; 18 passed, 1 skipped). `harness/VERSION` → **1.7.14,
2026-09-26**, y sección nueva en `GUIA_INSTALACION.md` con el caso, el AVISO del
rojo nuevo y qué revisar al actualizar. **Por qué 1.7.14**: 1.7.11-1.7.13 son
encargos sin entregar (`ENCARGO_*.md`); tomé el siguiente número libre y lo
digo en la guía. Suite del payload: `362 passed, 2 skipped in 89.95s`.

Modo actualizar del instalador, **solo `-SoloDiff`** (lectura) contra este
proyecto: detecta v1.7.7 instalada → v1.7.14; `Nuevos 5 | Ya iguales 24 |
Iguales salvo finales de línea 4 | Conservados 16 | Protegidos 5`. Los 16 que
difieren incluyen `CLAUDE.md`, `CHECKPOINTS.md`, `leader.md`, `init.sh` y
`mutacion_paralela.py`: es la deuda de la 1.7.8-1.7.10 más adaptaciones
locales. **No lo apliqué**: arrastraría tres versiones ajenas a F-112 (p. ej.
`harness` sale del alcance de la mutación) y pide decidir fichero a fichero.
Este repositorio queda en **1.7.7 + el cambio de la 1.7.14 hecho a mano**
(`harness/VERSION` dice 1.7.7: no se edita a mano). Pendiente para el humano.

## Remedición de F-107..F-110 contra `main`

Método: alcance = diff del merge que integró cada feature (`merge^1..merge`,
el que ahora calcula la puerta para una rama integrada); suite ENTERA bajo
`coverage` en un worktree desechable en ese merge (variables del `.env`
volcadas al proceso como hace la campaña paralela, el fichero no se copió);
cruce con `harness.cobertura.cobertura_lineas_cambiadas`. Script y salidas en
el scratchpad de la sesión; worktrees ya borrados.

| Feature | Rigor / umbral | Merge | Lo que dijo la puerta (contra `dev`) | Líneas `.py` de producción del merge | Ejecutables | Cobertura real | Suite en el merge |
|---|---|---|---|---|---|---|---|
| F-107 | estandar / 80 % | `d26f843` | 94,7 % de 1.022 | 14 (`build_maestros_step.py`) | 0 | **N/A** | 5.296 passed, 197 skipped |
| F-108 | estandar / 80 % | `79a4505` | 95,1 % de 1.106 | 238 en 5 ficheros | 84 | **100,0 % (84/84)** | 5.480 passed, 209 skipped |
| F-109 | estandar / 80 % | `42d4b05` | 95,1 % de 1.106 | 0 (solo YAML, Markdown y tests) | 0 | **N/A** | no hizo falta |
| F-110 | critico / 80 % | `b40f012` | 95,1 % de 1.106 | 27 (`build_retenciones_step.py`) | 0 | **N/A** | 5.512 passed, 210 skipped |

**Ninguna queda por debajo del umbral.** F-107 y F-110 solo cambian en Python
docstrings, comentarios y entradas dentro de una tupla literal (sin sentencias
propias); F-109 no toca Python. Su entregable es SQL/YAML, que la puerta de
cobertura no mide (es el hueco del encargo 1.7.11 de `arnes-base`, no de F-112).
Las cifras antiguas eran las de 25 ficheros y ~4.900 líneas de trabajo ajeno.
(En los worktrees se saltan 7 tests de `azure-apps`, que leen Markdown hermano.)

## Verificaciones MANUAL pendientes

- Humano: decidir qué se hace con `dev` (arriba) y rescatar o descartar las
  dos peticiones de mcp-bbdd que viven solo allí.
- Humano: si se aplica la actualización completa del arnés (1.7.7 → 1.7.14).
- Humano: push de `arnes-base` (`2c3a7fe`) cuando lo autorice.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-112 | 20 passed (`tests/test_f112_base_de_la_puerta.py`) |
| Suite completa (`bash harness/init.sh`) | **5.562 passed, 203 skipped**, exit 0 (`ENTORNO LISTO`) |
| Cobertura de las líneas cambiadas | **100,0 % (69/69)**, diff desde `fb52d96e14`, merge-base con `main` (la ejecución anterior, antes de los tests de T7, dio 92,8 % 64/69) |
| Mutación | `python -m harness.mutacion --feature F-112 --workers 3 --timeout 2400`: **27 generados, 20 evaluados (muestreo `estandar`, semilla 20260820), 18 muertos, 2 supervivientes, 0 timeouts**, 3.611,7 s, medida en HEAD `25795cc`. Detalle: `progress/mutacion_F-112.md` |
| Supervivientes | los 2, `cobertura.py:167/168` (`[:10]` -> `[:11]` del sha en la línea de la puerta): **huecos reales**, ahora muertos por tests endurecidos (`3912100`, `48499f4`); rejugados a mano, ROJO con el mutante |
| Tiempo de la suite | 766,01 s (0:12:46), lo que imprime pytest bajo coverage |

Sobre la campaña: el primer intento (`--feature F-112` a secas, 4 workers por
defecto) abortó sin informe porque la línea base limpia no cupo en sus 600 s
con 4 suites compitiendo. Relanzada con 3 workers y `--timeout 2400` (F-108 ya
usó `--timeout 1800`); líneas base de 518-531 s, todas verdes. El cierre de la
1.7.8 (un timeout es un reintento) no está en este proyecto (1.7.7).

Resultado real de `bash harness/init.sh` (última ejecución, HEAD `01f1f7b`):

```
[OK] Arnés v1.7.7 (2026-08-26)
5562 passed, 203 skipped, 1484 warnings in 766.01s (0:12:46)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 69 líneas cambiadas cubiertas (69/69, umbral 80%, nivel estandar; diff desde fb52d96e14, merge-base con main)
[OK] PUERTA TAMAÑO: F-112 dentro de los topes (impl 206/220)
[OK] Rama actual: feature/F-112-cobertura-contra-main
ENTORNO LISTO. Puedes trabajar.   (exit 0; avisos previos: F-052 blocked, 233 de ruff)
```
