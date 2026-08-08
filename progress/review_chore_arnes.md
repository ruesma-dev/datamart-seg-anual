<!-- progress/review_chore_arnes.md -->
# Review · Mantenimiento del arnés (`chore/mantenimiento-arnes`)

- **Fecha:** 2026-08-08
- **Rama revisada:** `chore/mantenimiento-arnes` (HEAD `b979b82`)
- **Naturaleza:** mantenimiento, sin spec SDD. No aplica trazabilidad EARS.
- **Estado de los cambios:** en índice (staged), sin commitear.
- **Veredicto:** **APROBADO**

Ficheros en el cambio (`git diff --cached --name-status`):

```
M  .gitattributes
M  CLAUDE.md
M  harness/init.sh
M  main.py
M  pyproject.toml
A  requirements-dev.txt
```

`requirements.txt` y `Dockerfile` NO se han tocado (verificado con
`git diff HEAD --stat -- requirements.txt Dockerfile` → 0 líneas), coherente
con lo que promete la cabecera de `requirements-dev.txt`.

---

## 1. `.gitattributes` — finales de línea

### Hallazgo previo confirmado

Clonado no destructivo del repo del usuario al scratchpad:

```bash
git clone --local --no-hardlinks --branch chore/mantenimiento-arnes \
  C:/Users/pgris/PycharmProjects/datamart-seg-anual "$SCRATCH/eol1"
cd "$SCRATCH/eol1" && file -b infra/*.ps1
```

Resultado con el `.gitattributes` **antiguo** (`* text=auto eol=lf`): los 5
`.ps1` salen `UTF-8 (with BOM) text`, **sin** `with CRLF line terminators`,
es decir en LF. Incumple `docs/CONVENTIONS.md:41` («PowerShell: UTF-8 con BOM
y CRLF»). Hallazgo válido.

### La regla nueva funciona

Se copió el `.gitattributes` staged al clon 1, se commiteó allí y se volvió a
clonar (`eol2`) para forzar un checkout limpio bajo las reglas nuevas:

```bash
git --git-dir=<repo>/.git show :.gitattributes > .gitattributes
git add .gitattributes && git commit -m "test eol"
git clone --local --no-hardlinks "$SCRATCH/eol1" "$SCRATCH/eol2"
cd "$SCRATCH/eol2" && file -b infra/*.ps1 harness/init.sh
```

| Fichero | Resultado en checkout limpio |
|---|---|
| `infra/00_vars.ps1` | UTF-8 **with BOM**, **CRLF** (21 líneas CR) |
| `infra/10_create_rg.ps1` | UTF-8 **with BOM**, **CRLF** (7) |
| `infra/20_build_image.ps1` | UTF-8 **with BOM**, **CRLF** (8) |
| `infra/30_create_job.ps1` | UTF-8 **with BOM**, **CRLF** (19) |
| `infra/40_update_job.ps1` | UTF-8 **with BOM**, **CRLF** (8) |
| `harness/init.sh` | LF (`grep -c $'\r$'` → **0**) |

- BOM verificado byte a byte: `head -c3 | od -An -tx1` → `efbbbf` en los 5.
- Los blobs en el repo siguen normalizados a LF
  (`git show HEAD:infra/00_vars.ps1 | grep -c $'\r$'` → 0), que es lo correcto:
  la conversión a CRLF es de checkout, no de almacenamiento.

**Ningún fichero del repo del usuario fue borrado ni modificado.** Todo el
trabajo se hizo sobre clones en el scratchpad.

---

## 2. `main.py` — checkpoint C3

```bash
head -c 60 main.py | od -c
```

Primeros bytes: `#   m a i n . p y \n` — sin BOM y sin líneas en blanco
previas. La primera línea es el comentario con la ruta relativa. C3 cumplido
para este fichero.

---

## 3. `ruff` — lint informativo

```bash
bash harness/init.sh; echo "EXIT: $?"
```

- **Exit code 0** → `ENTORNO LISTO. Puedes trabajar.`
- Línea emitida: `[AVISO] ruff: 122 avisos (deuda previa, no bloquea).`
- Es `warn()`, no `ko()`: no incrementa `FALLOS`. No bloquea, como se pedía.

Contraste del recuento:

```bash
python -m ruff check . --output-format=concise | grep -cE ":[0-9]+:[0-9]+:"   # 122
python -m ruff check . --output-format=concise | tail -1                      # Found 122 errors.
```

**Coinciden: 122 = 122.** El `grep -cE` no cuenta la línea resumen
`Found N errors.` ni la de `[*] fixable`, por lo que el conteo es exacto.
`ruff 0.16.2`.

Exclusión de `patches` en `pyproject.toml` efectiva:
`python -m ruff check . --output-format=concise | grep -ci patches` → **0**,
mientras que analizarlo explícitamente (`ruff check patches`) da 51 errores.
Esos 51 quedan fuera de los 122, que es la intención declarada.

`ruff` está solo en `requirements-dev.txt`, no en `requirements.txt`
(`grep -inE "ruff|pytest" requirements.txt` → solo `pytest>=8.0.0`), así que
la imagen de contenedor no lo arrastra y el comentario del fichero es veraz.

---

## 4. `CLAUDE.md` — autorización de subagentes

La sección añadida es coherente y honesta: no solo concede la autorización,
también obliga a **declarar en el primer mensaje** si el entorno impide
delegar, en lugar de asumir el trabajo en silencio. La condición técnica que
cita es real en este entorno: `env | grep CLAUDE_CODE_CHILD` →
`CLAUDE_CODE_CHILD_SESSION=1`.

Ver observación O4 más abajo sobre la firma humana de este punto.

---

## 5. Secretos, tests y estado

```bash
git diff --cached | grep -inE "password|secret|token|api[_-]?key|BEGIN .*PRIVATE KEY|postgres://|..."
```
→ **sin coincidencias**. Ningún secreto en el cambio.

- `.env` sigue ignorado (`git check-ignore -v .env` → `.gitignore:2`) y no
  trackeado.
- Sin `print()` nuevos (`git diff --cached | grep -nE "^\+.*print\("` → nada).
- `python -m pytest -q` → **15 passed in 0.92s**. Los de humo no tocan red ni
  BBDD.
- `harness/features.json` **intacto**: `git diff HEAD -- harness/features.json`
  → 0 líneas; sigue con las 3 features originales
  (`F-001`, `F-002`, `F-003`, todas `pending`).

---

## Checkpoints (`CHECKPOINTS.md`)

### C1 — El arnés está completo y en verde
- [x] `bash harness/init.sh` termina con exit code 0.
- [x] Existen los 8 ficheros del arnés (init.sh los verifica uno a uno, todos `[OK]`).

### C2 — El estado es coherente
- [x] Ninguna feature `in_progress` (0 ≤ 1).
- [x] Rama `chore/mantenimiento-arnes`, no `main`. *Nota:* no encaja el patrón
      `feature/F-XXX-slug` porque no es una feature; el guardarraíl real del
      checkpoint (no trabajar en `main`) se respeta.
- [x] `progress/current.md` está en plantilla vacía, sin restos.
- [x] No hay features `done` nuevas que resumir en `history.md`.

### C3 — El código respeta arquitectura y convenciones
- [x] No se toca dominio ni SQL: el cambio no altera arquitectura.
- [x] Primera línea de `main.py` = su ruta relativa (era el objetivo del cambio).
- [x] Sin `print()` de debug, sin secretos hardcodeados.
- [x] Dependencia nueva (`ruff`): no hay spec que la previera, pero es el
      propósito declarado del mantenimiento, es dev-only y queda fuera de la
      imagen. Aceptable y documentada.
- [x] Semántica Sigrid: no aplica, no se toca lógica de negocio.

### C4 — La verificación es real
- [~] Trazabilidad EARS: **no aplica** (mantenimiento sin spec).
- [x] Los tests no tocan red ni BBDD; 15 pasan.
- [x] Verificaciones manuales: ninguna pendiente. Las comprobaciones de EOL,
      BOM y recuento de lint se han ejecutado en esta review, no se delegan al
      humano.

### C5 — La sesión se cerró bien
- [~] `tasks.md` y commits `F-XXX Tn:`: **no aplica**, no es una feature.
- [x] Sin ficheros temporales ni untracked sospechosos en el repo
      (`git status --porcelain -uall` → solo los 6 ficheros staged). Los clones
      de verificación viven en el scratchpad, fuera del repo.
- [x] `features.json` intacto, como exigía el encargo.

**Ningún `[ ]` en C1–C5.**

---

## Observaciones (NO bloqueantes)

**O1 — El `.gitattributes` nuevo reintroduce la dependencia de `core.autocrlf`
para todo lo que no sea `.ps1`/`.sh`.** Al sustituir el fichero entero se
perdieron `* text=auto eol=lf` y las reglas por tipo (`*.py`, `*.sql`, `*.yaml`,
`*.md`, `*.toml`, `*.txt`). Verificado en el clon limpio `eol2`: con
`core.autocrlf=true`, `orchestrator.py`, `config/settings.py`, `CLAUDE.md`,
`pyproject.toml` y `requirements.txt` ahora llegan **con CRLF**, cuando antes
llegaban en LF. Es exactamente la causa raíz que el cambio decía corregir,
resuelta para dos extensiones y reabierta para el resto.

Comprobado que hoy **no rompe nada**: `init.sh` no hace comprobaciones de
contenido línea a línea sobre los `.py` (el chequeo de primera línea no existe
en el script), el `ENTRYPOINT` del Dockerfile es `python`, no un `.sh`, y los
blobs siguen guardándose en LF. Por eso no bloquea. Recomendación: reponer
`* text=auto eol=lf` como línea base y dejar `*.ps1 text eol=crlf` como
excepción encima; se conserva la corrección y se recupera el determinismo.

**O2 — Se perdieron las declaraciones `binary`** (`*.png`, `*.jpg`, `*.jpeg`,
`*.pdf`, `*.xlsx`, `*.xls`, `*.docx`, `*.zip`). Hoy es latente: el repo no
trackea ningún fichero de esas extensiones (`git ls-files | grep -iE ...` →
vacío), y Git detecta binarios por heurística de bytes NUL. Reponerlas cuesta
7 líneas y evita una corrupción silenciosa el día que se añada un `.xlsx`.

**O3 — Robustez menor en `harness/init.sh:82`.** Si `ruff --version` responde
pero `ruff check` peta, `ERRORES_LINT` queda vacío y `[ "" -eq 0 ]` escribe
`integer expression expected` en stderr. No es fatal (no hay `set -e`), pero
un `ERRORES_LINT=${ERRORES_LINT:-0}` lo deja limpio.

**O4 — Gobernanza de `CLAUDE.md`.** La sección añadida concede una
autorización permanente y para todas las sesiones futuras sobre el
comportamiento de los agentes. Un agente no puede autoconcederse eso: el
contenido es correcto y bien redactado, pero **debe llevar la confirmación
explícita del humano antes de commitear**, no la del líder que encargó el
mantenimiento. Se aprueba el texto; la firma es del humano.

**O5 — Deuda C3 preexistente, fuera de alcance.** 14 de 36 `.py` trackeados no
tienen su ruta en la primera línea: los 8 `__init__.py` vacíos (discutible si
aplica), `scripts/refresh_presupuesto.py`, y 4 scripts sueltos en la raíz
(`diagnose_feb_2026.py`, `inspect_0696_master_may25.py`,
`inspect_0696_may25.py`, `validate_all_fixes.py`) que empiezan por docstring.
Esos 4 de raíz, además, parecen scripts de diagnóstico puntuales que quizá
deberían vivir en `scripts/`. No es responsabilidad de este cambio.

---

## Propuesta de automejora del protocolo (no aplicada)

`CHECKPOINTS.md` asume que todo trabajo es una feature con spec: C2 exige rama
`feature/F-XXX-slug` y C5 exige `tasks.md` con commits `F-XXX Tn:`. El
mantenimiento del arnés no encaja y obliga al reviewer a improvisar «no
aplica». Sugerencia para que la valide el humano: añadir a `CHECKPOINTS.md` una
nota de alcance del tipo «para trabajos de mantenimiento sin spec (rama
`chore/...`), C4 y C5 se limitan a: tests en verde, sin secretos, sin
artefactos sueltos y `features.json` sin tocar».
