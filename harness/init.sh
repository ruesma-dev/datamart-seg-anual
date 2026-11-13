#!/usr/bin/env bash
# harness/init.sh
# Portero del arnés: decide si el proyecto está apto para que un agente
# trabaje. Cualquier fallo => exit 1 => el agente NO trabaja.
# Compatible con Git Bash (Windows) y Linux.
#
# QUÉ EXIGE Y QUÉ NO
# ------------------
# Lo que SIEMPRE se comprueba (vale para cualquier lenguaje): que estén los
# ficheros del arnés, que `harness/features.json` sea válido y tenga como
# mucho una feature activa (`in_progress`, `in_review` o `human_review`), que
# exista `.env` si el proyecto lo usa, y que no estés trabajando en `main`.
#
# Lo que depende del lenguaje (compilación, lint, tests) se activa solo si el
# proyecto es Python. En un proyecto que no lo sea, esas secciones se saltan
# con un AVISO y se ejecuta `COMANDO_TESTS` si lo has definido. Es a propósito:
# el valor del arnés —la máquina de estados de features, los checkpoints, la
# memoria en `progress/`— no tiene nada de Python, y hacerlo fallar en un repo
# de otro lenguaje solo consigue que alguien comente la comprobación.
#
# Para validar `features.json` se usa el primer intérprete disponible: python,
# node o jq. Si no hay ninguno, la validación DEGRADA a una comprobación por
# texto (avisa de ello) en vez de fallar.

# --- Configuración de este proyecto (adaptación resuelta) -------------------
PROYECTO_PYTHON=1        # ETL en Python 3.12; no hace falta detectarlo
REQUIERE_ENV=1           # config/settings.py lee .env (pydantic-settings)
RUTAS_PYTHON="main.py config etl_sigrid scripts tests harness"
                         # rutas a compilar: el árbol de código real. Se
                         # enumeran para no arrastrar infra/, docs/ ni .venv.
COMANDO_TESTS=""         # no aplica: la suite es pytest sobre tests/
LINT_BLOQUEA=0           # ruff avisa pero no tumba: hay deuda previa en el
                         # repositorio y ponerlo en 1 impediría cerrar nada
RAMA_BASE=main           # rama donde se INTEGRA el trabajo. Las puertas miden
                         # el diff desde el merge-base de la rama con ella, y
                         # se ponen en rojo si ese diff trae commits que ya
                         # viven en otra rama de larga vida (base rezagada).
                         # Era `dev` hasta F-112: `dev` está parada desde el
                         # 2026-09-03 (a1845db) y todo se integra en `main`;
                         # la cobertura «de la feature» medía semanas ajenas.
                         # `harness.mutacion` y compañía la leen de aquí.
COMPROBACIONES_EXTRA=0   # sin comprobaciones extra en la sección 9

# Modo ligero (para hooks): con ARNES_SALTAR_SUITES=1 el portero salta las
# suites de tests y la puerta de cobertura, avisándolo en cada sección. NO
# vale para cerrar una feature: el cierre exige el portero completo
# (`bash harness/init.sh` a secas).
SALTAR_SUITES="${ARNES_SALTAR_SUITES:-0}"

# Sin caché: con ARNES_SIN_CACHE=1 las suites de los servicios (sección 7 bis)
# se ejecutan aunque haya un verde reutilizable, y lo refrescan si salen en verde.
SIN_CACHE="${ARNES_SIN_CACHE:-0}"

set -u
cd "$(dirname "$0")/.." || exit 1

ROJO='\033[0;31m'; VERDE='\033[0;32m'; AMARILLO='\033[0;33m'; NC='\033[0m'
FALLOS=0

ok()   { printf "${VERDE}[OK]${NC} %s\n" "$1"; }
warn() { printf "${AMARILLO}[AVISO]${NC} %s\n" "$1"; }
ko()   { printf "${ROJO}[KO]${NC} %s\n" "$1"; FALLOS=$((FALLOS + 1)); }

# --- 0. Versión del arnés ---------------------------------------------------
# Lo primero que se imprime: si algo del arnés se comporta raro, lo primero
# que hay que saber es qué versión lleva este repositorio.
if [ -f "harness/VERSION" ]; then
    ARNES_VERSION=""; ARNES_FECHA=""
    # shellcheck disable=SC1091
    . ./harness/VERSION 2>/dev/null
    if [ -n "${ARNES_VERSION:-}" ]; then
        ok "Arnés v${ARNES_VERSION} (${ARNES_FECHA:-fecha desconocida})"
    else
        warn "harness/VERSION existe pero no define ARNES_VERSION"
    fi
else
    warn "Sin harness/VERSION: arnés anterior al versionado. Actualízalo desde arnes-base."
fi

# --- 1. Tipo de proyecto e intérpretes disponibles --------------------------
# El venv del proyecto manda sobre el PATH. Sin esto, `python` es el que
# hubiera en el PATH de esa terminal concreta y el arnés salía verde o rojo
# según cómo se hubiera abierto: misma rama, mismo árbol, distinto veredicto.
# Se antepone al PATH en vez de guardar la ruta en $PY porque así siguen
# valiendo todos los usos de `$PY` de más abajo y las rutas con espacios no
# rompen nada. Un venv ya activado ($VIRTUAL_ENV) es una decisión explícita
# de quien ejecuta y no se pisa.
VENV_DEL_PROYECTO=""
if [ -z "${VIRTUAL_ENV:-}" ]; then
    for _venv_dir in .venv venv; do
        for _venv_bin in "$_venv_dir/bin" "$_venv_dir/Scripts"; do
            if [ -x "$_venv_bin/python" ] || [ -x "$_venv_bin/python.exe" ]; then
                PATH="$PWD/$_venv_bin:$PATH"
                export PATH
                VENV_DEL_PROYECTO="$_venv_bin"
                break 2
            fi
        done
    done
fi

PY=""
if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
fi

if [ "$PROYECTO_PYTHON" = "auto" ]; then
    if [ -f "pyproject.toml" ] || [ -f "requirements.txt" ] || [ -f "setup.py" ] \
       || [ -n "$(find . -maxdepth 3 -name '*.py' -not -path './.venv/*' -not -path './.git/*' -print -quit 2>/dev/null)" ]; then
        ES_PYTHON=1
    else
        ES_PYTHON=0
    fi
else
    ES_PYTHON="$PROYECTO_PYTHON"
fi

if [ "$ES_PYTHON" -eq 1 ]; then
    if [ -n "$PY" ]; then
        if [ -n "$VENV_DEL_PROYECTO" ]; then
            ok "Python: $($PY --version 2>&1) (venv del proyecto: $VENV_DEL_PROYECTO)"
        else
            ok "Python: $($PY --version 2>&1)"
        fi
    else
        ko "Proyecto Python pero no hay intérprete en PATH (¿venv sin activar?)"
        exit 1
    fi
else
    warn "Proyecto no Python: se saltan compilación, lint y pytest (ver cabecera de este fichero)"
fi

# --- 1 bis. ¿Hay una campaña de mutación en curso? --------------------------
# Mientras una campaña de mutación corre, puede haber un mutante APLICADO en el
# árbol: un `!=` donde el código dice `==`. Todo lo que este portero mida a
# partir de ahí —compilación, lint, tests, cobertura— estaría midiendo ese
# mutante, no el código, y su rojo no significa nada. Pasó el 2026-08-19: un
# agente lanzó init.sh mientras otro tenía una campaña corriendo, salió en rojo
# y la reacción natural —restaurar el fichero— habría contaminado la campaña
# ajena.
#
# La campaña deja constancia en un centinela (.arnes_cache/mutacion_en_curso.json,
# ver harness/mutacion.py) y aquí se lee con `--estado`, que devuelve 0 (no hay
# campaña), 3 (la hay, pero muta en worktrees aparte) o 4 (la hay y el árbol
# principal tiene un mutante escrito AHORA MISMO). El 4 es KO: no se puede dar
# por bueno ni por malo un veredicto medido sobre un mutante.
if [ -f ".arnes_cache/mutacion_en_curso.json" ]; then
    if [ -n "$PY" ]; then
        ESTADO_MUTACION=$($PY -m harness.mutacion --estado 2>&1)
        case "$?" in
            0) : ;;   # el centinela desapareció entre el test y la lectura
            3) warn "$ESTADO_MUTACION" ;;
            *) ko "$ESTADO_MUTACION" ;;
        esac
    else
        ko "Hay un centinela de campaña de mutación (.arnes_cache/mutacion_en_curso.json) y sin Python no se puede leer: el árbol puede tener un mutante aplicado y NADA de lo que mida este portero es de fiar"
    fi
fi

# --- 2. Ficheros del arnés --------------------------------------------------
for f in CLAUDE.md CHECKPOINTS.md harness/features.json harness/rigor.json \
         specs/SPECS.md progress/current.md progress/history.md \
         docs/ARCHITECTURE.md docs/CONVENTIONS.md; do
    if [ -f "$f" ]; then ok "Existe $f"; else ko "Falta $f"; fi
done

# --- 3. features.json: esquema, estados y UNA sola feature activa -----------
# Se valida con el primer intérprete disponible. Sin ninguno, degrada a texto.
#
# Los ocho estados y los tres activos (`in_progress`, `in_review`,
# `human_review`; `todo` no lo es) se repiten en cada validador porque node y
# jq no pueden importar harness/estados.py, que es la fuente única. Que las listas
# coincidan lo vigila la suite (tests/test_init_sh_estados.py). No se lee
# `rules.valid_status`: en un proyecto instalado es su copia vieja.
VALIDADOR=""
if [ -n "$PY" ]; then VALIDADOR=python
elif command -v node >/dev/null 2>&1; then VALIDADOR=node
elif command -v jq >/dev/null 2>&1; then VALIDADOR=jq
fi

case "$VALIDADOR" in
python)
    $PY - <<'EOF'
import json, sys
try:
    with open("harness/features.json", encoding="utf-8") as fh:
        data = json.load(fh)
    estados = {"pending", "todo", "spec_ready", "in_progress", "in_review", "human_review", "done", "blocked"}
    activos = {"in_progress", "in_review", "human_review"}
    activas = []
    for f in data["features"]:
        assert {"id", "title", "status", "sdd"} <= set(f), f"Feature incompleta: {f}"
        assert f["status"] in estados, f"Estado inválido en {f['id']}: {f['status']}"
        if f["status"] in activos:
            activas.append(f["id"])
    if len(activas) > 1:
        print(f"Hay {len(activas)} features activas (in_progress/in_review/human_review): "
              f"{', '.join(activas)}. Máximo 1.", file=sys.stderr)
        sys.exit(1)
    bloqueadas = [f["id"] for f in data["features"] if f["status"] == "blocked"]
    abiertas = sum(1 for f in data["features"] if f["status"] != "done")
    print(f"    {len(data['features'])} features, {abiertas} abiertas, "
          f"activa: {activas or 'ninguna'}, bloqueadas: {bloqueadas or 'ninguna'}")
except Exception as exc:  # noqa: BLE001
    print(f"features.json inválido: {exc}", file=sys.stderr)
    sys.exit(1)
EOF
    RES=$?
    ;;
node)
    node -e '
const fs = require("fs");
try {
  const d = JSON.parse(fs.readFileSync("harness/features.json", "utf8"));
  const estados = ["pending","todo","spec_ready","in_progress","in_review","human_review","done","blocked"];
  const activos = ["in_progress","in_review","human_review"];
  const activas = [];
  for (const f of d.features) {
    for (const k of ["id","title","status","sdd"]) {
      if (!(k in f)) throw new Error("Feature incompleta, falta " + k + ": " + JSON.stringify(f));
    }
    if (!estados.includes(f.status)) throw new Error("Estado inválido en " + f.id + ": " + f.status);
    if (activos.includes(f.status)) activas.push(f.id);
  }
  if (activas.length > 1) {
    console.error("Hay " + activas.length + " features activas (in_progress/in_review/human_review): " +
                  activas.join(", ") + ". Máximo 1.");
    process.exit(1);
  }
  const bloq = d.features.filter(f => f.status === "blocked").map(f => f.id);
  const abiertas = d.features.filter(f => f.status !== "done").length;
  console.log("    " + d.features.length + " features, " + abiertas + " abiertas, activa: " +
              (activas.length ? activas.join(", ") : "ninguna") + ", bloqueadas: " +
              (bloq.length ? bloq.join(", ") : "ninguna"));
} catch (e) { console.error("features.json inválido: " + e.message); process.exit(1); }
'
    RES=$?
    ;;
jq)
    # `.status as $s | [...] | index($s)`: la forma `[...] | index(.status)`
    # evaluaba `.status` contra el array y fallaba con cualquier fichero.
    ACTIVAS_JQ=$(jq -r '[.features[] | select(.status as $s | ["in_progress","in_review","human_review"] | index($s)) | .id] | join(", ")' harness/features.json 2>/dev/null)
    N_ACTIVAS_JQ=$(jq '[.features[] | select(.status as $s | ["in_progress","in_review","human_review"] | index($s))] | length' harness/features.json 2>/dev/null)
    if [ "${N_ACTIVAS_JQ:-0}" -gt 1 ] 2>/dev/null; then
        echo "Hay $N_ACTIVAS_JQ features activas (in_progress/in_review/human_review): $ACTIVAS_JQ. Máximo 1." >&2
        RES=1
    elif jq -e '
        (.features | length) > 0
        and all(.features[]; (has("id") and has("title") and has("status") and has("sdd"))
                and (.status as $s | ["pending","todo","spec_ready","in_progress","in_review","human_review","done","blocked"] | index($s)))
    ' harness/features.json >/dev/null 2>&1; then
        printf "    %s features, activa: %s\n" \
            "$(jq '.features | length' harness/features.json)" \
            "${ACTIVAS_JQ:-ninguna}"
        RES=0
    else
        INVALIDAS_JQ=$(jq -r '[.features[] | select((.status as $s | ["pending","todo","spec_ready","in_progress","in_review","human_review","done","blocked"] | index($s)) | not) | "\(.id): \(.status)"] | join(", ")' harness/features.json 2>/dev/null)
        echo "features.json inválido (JSON roto, feature incompleta o estado inválido${INVALIDAS_JQ:+: $INVALIDAS_JQ})" >&2
        RES=1
    fi
    ;;
*)
    warn "Sin python, node ni jq: validación de features.json DEGRADADA (solo texto)"
    # Empareja cada "status" activo con el último "id" visto antes que él.
    ACTIVAS_TXT=$(grep -oE '"(id|status)"[[:space:]]*:[[:space:]]*"[^"]*"' harness/features.json 2>/dev/null \
        | awk -F'"' '$2 == "id" { id = $4 }
                     $2 == "status" && ($4 == "in_progress" || $4 == "in_review" || $4 == "human_review") {
                         n++; lista = lista sep id; sep = ", " }
                     END { print n + 0 "|" lista }')
    N_ACTIVAS_TXT=${ACTIVAS_TXT%%|*}
    if [ "${N_ACTIVAS_TXT:-0}" -gt 1 ]; then
        echo "Hay $N_ACTIVAS_TXT features activas (in_progress/in_review/human_review): ${ACTIVAS_TXT#*|}. Máximo 1." >&2
        RES=1
    else
        RES=0
    fi
    ;;
esac
if [ "$RES" -eq 0 ]; then ok "features.json válido"; else ko "features.json inválido (o más de una feature activa)"; fi

# --- 3 bis. BACKLOG.md: proyección legible de features.json -----------------
# features.json es la fuente de verdad, pero nadie lee un JSON de un vistazo.
# BACKLOG.md es su proyección en Markdown, GENERADA: no se edita a mano. Se
# regenera aquí para que esté siempre al día sin que nadie se acuerde.
#
# La salida es función pura de features.json (sin fecha de generación), así
# que este paso NO ensucia el árbol salvo que el backlog haya cambiado de
# verdad; cuando cambia, avisa para que entre en el mismo commit.
# Necesita Python: sin él, degrada con aviso.
if [ -n "$PY" ]; then
    SALIDA_BACKLOG=$($PY harness/backlog.py 2>&1)
    if [ $? -eq 0 ]; then
        if [ -n "$SALIDA_BACKLOG" ]; then
            warn "BACKLOG.md regenerado desde features.json: inclúyelo en el commit"
        else
            ok "BACKLOG.md al día"
        fi
    else
        warn "No se pudo generar BACKLOG.md: $SALIDA_BACKLOG"
    fi
else
    warn "Sin Python: no se regenera BACKLOG.md desde features.json"
fi

# --- 3 ter. Estado y fechas de la feature de la rama (solo avisos) -----------
# Una feature `done` lleva `ok_humano` (el día del OK del humano a la PARADA
# 2) y una `sdd: true` activa o `done` lleva `spec_aprobada`. Se mira SOLO la
# feature de la rama (la que la declara; si ninguna, la activa): las `done`
# anteriores a estos campos quedan amnistiadas por construcción, como en la
# puerta de tamaño. Son avisos, nunca rojo. Las transiciones (de qué estado se
# viene) no se validan: esa regla vive en .claude/agents/leader.md.
if [ -n "$PY" ] && [ -f "harness/estados.py" ]; then
    AVISOS_ESTADO=$($PY -m harness.estados --avisos 2>&1)
    if [ $? -ne 0 ]; then
        warn "AVISOS DE ESTADO: no se pudieron calcular (python -m harness.estados --avisos): $AVISOS_ESTADO"
    elif [ -n "$AVISOS_ESTADO" ]; then
        while IFS= read -r LINEA_ESTADO; do
            [ -n "$LINEA_ESTADO" ] && warn "$LINEA_ESTADO"
        done <<EOF_ESTADO
$AVISOS_ESTADO
EOF_ESTADO
    fi
elif [ -z "$PY" ]; then
    warn "AVISOS DE ESTADO: N/A (no hay intérprete de Python en el PATH: no se comprueban ok_humano ni spec_aprobada de la feature de la rama)"
else
    warn "AVISOS DE ESTADO: N/A (no existe harness/estados.py: arnés anterior a los ocho estados)"
fi

# --- 3b. Niveles de rigor: configuración válida y niveles declarados válidos -
# Lo que exige cada nivel vive en harness/rigor.json. Una feature que no
# declara nivel NO es un error: se le aplica el nivel por defecto. Declarar uno
# inexistente sí lo es. Necesita Python: sin él, degrada con aviso.
# Capa local (F-063): harness/rigor.local.json, si existe, pisa a rigor.json
# clave a clave; --validar la valida, la fusiona e imprime sus claves. Si la
# capa cambia en esta rama respecto a $RAMA_BASE (o no está versionada), se
# avisa: rebajar una puerta en la misma feature que se beneficia necesita el OK
# explícito del humano, y lo comprueba el reviewer. Sin git o sin la rama base,
# no se avisa.
if [ -n "$PY" ]; then
    if $PY -m harness.rigor --validar; then
        ok "harness/rigor.json y niveles declarados: válidos"
    else
        ko "harness/rigor.json o el campo 'rigor' de alguna feature no son válidos"
    fi
else
    warn "Sin Python: no se validan los niveles de rigor de harness/rigor.json"
fi
if [ -f "harness/rigor.local.json" ] && command -v git >/dev/null 2>&1 \
    && git rev-parse --verify --quiet "$RAMA_BASE^{commit}" >/dev/null 2>&1; then
    if ! git ls-files --error-unmatch harness/rigor.local.json >/dev/null 2>&1 \
        || ! git diff --quiet "$RAMA_BASE" -- harness/rigor.local.json >/dev/null 2>&1; then
        warn "CAPA LOCAL DE RIGOR: harness/rigor.local.json cambia en esta rama respecto a $RAMA_BASE (o no está versionada): el cambio necesita el OK explícito del humano antes de cerrar la feature"
    fi
fi

# --- 4. Aviso de features bloqueadas (no bloquea, pero se ve) ---------------
if grep -q '"status"[[:space:]]*:[[:space:]]*"blocked"' harness/features.json 2>/dev/null; then
    warn "Hay features en estado blocked: revisa progress/current.md"
fi

# --- 5. .env presente (no se valida contenido, no se imprime) ---------------
if [ "$REQUIERE_ENV" -eq 1 ]; then
    if [ -f ".env" ]; then ok "Existe .env (no versionado)"; else ko "Falta .env — copiar de .env.example"; fi
fi

# --- 6. Compilación de todo el código Python --------------------------------
if [ "$ES_PYTHON" -eq 1 ]; then
    if [ -n "$RUTAS_PYTHON" ]; then
        # shellcheck disable=SC2086
        COMPILA=$($PY -m compileall -q $RUTAS_PYTHON 2>&1)
    else
        COMPILA=$($PY -m compileall -q . -x '(\.venv|__pycache__|\.git|node_modules)' 2>&1)
    fi
    if [ $? -eq 0 ]; then
        ok "compileall: sin errores de sintaxis"
    else
        ko "compileall: errores de sintaxis"
        echo "$COMPILA" | head -5
    fi
fi

# --- 6b. Lint (informativo por defecto: la deuda previa no debe bloquear) ---
# ruff se configura en pyproject.toml y se instala con requirements-dev.txt.
# Por defecto avisa y no bloquea: un repo con deuda anterior no podría cerrar
# ninguna feature. Pon LINT_BLOQUEA=1 en un proyecto nuevo, que empieza limpio.
if [ "$ES_PYTHON" -eq 1 ]; then
    if $PY -m ruff --version >/dev/null 2>&1; then
        ERRORES_LINT=$($PY -m ruff check . --output-format=concise 2>/dev/null | grep -cE ":[0-9]+:[0-9]+:")
        ERRORES_LINT=${ERRORES_LINT:-0}   # si `ruff check` peta, no rompas la comparación
        if [ "$ERRORES_LINT" -eq 0 ]; then
            ok "ruff: sin avisos"
        elif [ "$LINT_BLOQUEA" -eq 1 ]; then
            ko "ruff: $ERRORES_LINT avisos. Detalle: python -m ruff check ."
        else
            warn "ruff: $ERRORES_LINT avisos (deuda previa, no bloquea). Detalle: python -m ruff check ."
        fi
    else
        warn "ruff no instalado: pip install -r requirements-dev.txt"
    fi
fi

# --- 7. Tests (los unit tests no necesitan red ni BBDD) ---------------------
# Si la medición de cobertura está disponible, la suite se ejecuta bajo ella
# para que la puerta de la sección 7b tenga datos con los que trabajar.
if [ "$SALTAR_SUITES" -eq 1 ]; then
    warn "Portero ligero (ARNES_SALTAR_SUITES=1): suite de la raíz saltada — NO vale para cerrar una feature"
elif [ "$ES_PYTHON" -eq 1 ]; then
    if [ -d "tests" ]; then
        if $PY -c "import coverage" >/dev/null 2>&1; then
            rm -f coverage.json
            # La ruta `tests` acota la recolección a la suite de la raíz: sin
            # ella, en un monorepo pytest arrastra los tests de los servicios
            # y los ejecuta con un intérprete que no es el suyo (y dos veces:
            # aquí y en la sección 7 bis).
            if $PY -m coverage run -m pytest tests -q --tb=short -x; then
                ok "pytest en verde (con medición de cobertura)"
            else
                ko "pytest en rojo (¿pytest instalado en el venv?)"
            fi
            $PY -m coverage json -q -o coverage.json >/dev/null 2>&1 \
                || warn "coverage no pudo escribir coverage.json"
        else
            warn "coverage no instalado: pip install -r requirements-dev.txt"
            if $PY -m pytest tests -q --tb=short -x; then
                ok "pytest en verde"
            else
                ko "pytest en rojo (¿pytest instalado en el venv?)"
            fi
        fi
    else
        warn "No existe tests/ todavía — créala en la primera feature"
    fi
elif [ -n "$COMANDO_TESTS" ]; then
    if eval "$COMANDO_TESTS"; then
        ok "tests en verde ($COMANDO_TESTS)"
    else
        ko "tests en rojo ($COMANDO_TESTS)"
    fi
else
    warn "Sin COMANDO_TESTS definido: NADIE está comprobando los tests. Defínelo en la cabecera de este fichero."
fi

# --- 7 bis. SERVICIOS DEL MONOREPO (solo si harness/servicios.json existe) --
# Un repositorio con un único proyecto en la raíz no declara nada y esta
# sección entera no se ejecuta: lo de arriba es todo lo que hay. Con
# declaración, cada servicio se comprueba con SU intérprete desde SU directorio
# y deja su propia línea [OK]/[AVISO]/[KO]; un KO en cualquiera hace KO el
# veredicto global, porque `ko` es lo que suma a FALLOS.
#
# La declaración rota NO degrada a mono-proyecto: sería dejar servicios enteros
# sin comprobar mientras el portero imprime que todo va bien. El esquema y un
# ejemplo comentado están en harness/servicios.ejemplo.json.
#
# Caché de suites: la decide `python -m harness.cache_suites`, no este bash. Su
# clave reúne el árbol del servicio en HEAD, el de cada ruta de `depende_de`, el
# intérprete, dónde resuelve ese intérprete cada módulo de `importa` y la huella
# (metadatos, nunca el contenido) de los .env y las `entradas_no_versionadas`.
# Con cambios sin commitear no hay clave; con un módulo importado desde fuera
# del repositorio, tampoco, y lo dice con un [AVISO]. Si el módulo falla, la
# suite se ejecuta y no se guarda nada: el error va al lado seguro. Las rutas
# de `ejecutar_siempre` (líneas SIEMPRE|, F-028) se ejecutan aunque se sirva la
# caché: son los barridos de todo el repositorio que ninguna clave ve cambiar.
if [ -f "harness/servicios.json" ]; then
    [ "$SIN_CACHE" = "1" ] && warn "ARNES_SIN_CACHE=1: las suites de los servicios se ejecutan sin caché (y la refrescan si salen en verde)"
    if [ -z "$PY" ]; then
        warn "Sin Python: no se puede leer harness/servicios.json y NADIE está comprobando los servicios"
    elif ! $PY -m harness.servicios --validar; then
        ko "harness/servicios.json, o el venv de algún servicio, no son válidos: el arnés no degrada a mono-proyecto en silencio"
    else
        ok "harness/servicios.json válido"
        SERVICIOS=$($PY -m harness.servicios --shell)
        if [ $? -ne 0 ]; then
            ko "harness/servicios.json: no se pudo resolver el intérprete de algún servicio"
            SERVICIOS=""
        fi
        # Sin tubería a propósito: en un subshell los `ko` no sumarían a FALLOS
        # y un servicio en rojo acabaría dando el veredicto en verde.
        while IFS='|' read -r NOMBRE RUTA LENGUAJE INTERPRETE COMANDO; do
            [ -z "$NOMBRE" ] && continue
            if [ "$LENGUAJE" = "python" ]; then
                if [ ! -d "$RUTA/tests" ]; then
                    warn "servicio $NOMBRE ($RUTA): sin directorio de tests — NADIE está comprobando los tests de $NOMBRE"
                    continue
                fi
                if [ "$SALTAR_SUITES" -eq 1 ]; then
                    warn "servicio $NOMBRE ($RUTA): suite saltada (portero ligero)"
                    continue
                fi
                # Caché de suite (ver el comentario de la sección). `</dev/null`:
                # ni el módulo ni su sonda pueden comerse la entrada del bucle.
                OPCION_CACHE=""
                [ "$SIN_CACHE" = "1" ] && OPCION_CACHE="--sin-cache"
                CLAVE_SRV=""
                FECHA_VERDE=""
                SIEMPRE_SRV=()
                if DECISION=$($PY -m harness.cache_suites --servicio "$NOMBRE" $OPCION_CACHE </dev/null); then
                    while IFS='|' read -r TIPO VALOR; do
                        # En Windows, Python escribe `\r\n` a una tubería y
                        # `$(…)` solo quita el último salto: sin recortar el
                        # `\r`, pytest recibiría `tests/x\r`, que no existe.
                        # Siempre cae en VALOR, el último campo: toda línea
                        # del protocolo lleva `|`.
                        VALOR=${VALOR%$'\r'}
                        case "$TIPO" in
                            AVISO)    warn "servicio $NOMBRE ($RUTA): $VALOR" ;;
                            SIEMPRE)  SIEMPRE_SRV+=("$VALOR") ;;
                            SERVIR)   FECHA_VERDE="$VALOR" ;;
                            EJECUTAR) CLAVE_SRV="$VALOR" ;;
                        esac
                    done <<EOF_CACHE
$DECISION
EOF_CACHE
                else
                    warn "servicio $NOMBRE ($RUTA): no se pudo decidir la caché (python -m harness.cache_suites --servicio $NOMBRE); se ejecuta la suite y no se guarda"
                fi
                if [ -n "$FECHA_VERDE" ]; then
                    # `ejecutar_siempre` se ejecuta aunque se sirva la caché, sin
                    # coverage (el coverage.json del verde sigue siendo el de la
                    # clave) y sin tocar la caché: si sale en rojo, el siguiente
                    # portero vuelve a ejecutarlo. El array solo se expande con
                    # elementos: vacío y con `set -u`, bash < 4.4 revienta.
                    if [ "${#SIEMPRE_SRV[@]}" -gt 0 ]; then
                        ( cd "$RUTA" && "$INTERPRETE" -m pytest -q --tb=short -p no:cacheprovider \
                            "${SIEMPRE_SRV[@]}" </dev/null )
                        if [ $? -eq 0 ]; then
                            ok "servicio $NOMBRE ($RUTA): pytest en verde (caché: ni el servicio ni sus dependencias han cambiado desde el verde del $FECHA_VERDE; ejecutar_siempre: ${#SIEMPRE_SRV[@]} rutas en verde)"
                        else
                            ko "servicio $NOMBRE ($RUTA): ejecutar_siempre en rojo con la caché válida del $FECHA_VERDE"
                        fi
                    else
                        ok "servicio $NOMBRE ($RUTA): pytest en verde (caché: ni el servicio ni sus dependencias han cambiado desde el verde del $FECHA_VERDE)"
                    fi
                    continue
                fi
                if "$INTERPRETE" -c "import coverage" >/dev/null 2>&1; then
                    ( cd "$RUTA" && rm -f coverage.json \
                      && "$INTERPRETE" -m coverage run -m pytest -q --tb=short -x )
                    RESULTADO=$?
                    ( cd "$RUTA" && "$INTERPRETE" -m coverage json -q -o coverage.json ) \
                        >/dev/null 2>&1 \
                        || warn "servicio $NOMBRE ($RUTA): coverage no pudo escribir su coverage.json"
                else
                    ( cd "$RUTA" && "$INTERPRETE" -m pytest -q --tb=short -x )
                    RESULTADO=$?
                fi
                if [ "$RESULTADO" -eq 0 ]; then
                    ok "servicio $NOMBRE ($RUTA): pytest en verde"
                    # Solo se cachea con clave: sin ella (árbol sucio, módulo
                    # de fuera, sonda rota) el verde no describe nada fijo.
                    [ -n "$CLAVE_SRV" ] && mkdir -p .arnes_cache && printf '%s' "$CLAVE_SRV" > ".arnes_cache/suite_${NOMBRE}.ok"
                else
                    ko "servicio $NOMBRE ($RUTA): pytest en rojo"
                fi
            elif [ -n "$COMANDO" ]; then
                if [ "$SALTAR_SUITES" -eq 1 ]; then
                    warn "servicio $NOMBRE ($RUTA): tests saltados (portero ligero)"
                    continue
                fi
                warn "servicio $NOMBRE ($RUTA): lenguaje '$LENGUAJE', se saltan compilación, lint y pytest"
                ( cd "$RUTA" && eval "$COMANDO" )
                RESULTADO=$?
                if [ "$RESULTADO" -eq 0 ]; then
                    ok "servicio $NOMBRE ($RUTA): tests en verde ($COMANDO)"
                else
                    ko "servicio $NOMBRE ($RUTA): tests en rojo ($COMANDO)"
                fi
            else
                warn "servicio $NOMBRE ($RUTA): lenguaje '$LENGUAJE' y sin comando_tests — NADIE está comprobando los tests de $NOMBRE"
            fi
        done <<EOF_SERVICIOS
$SERVICIOS
EOF_SERVICIOS
    fi
fi

# --- 7b. Puerta de cobertura de las LÍNEAS CAMBIADAS por la feature ---------
# Comprobar que los tests pasan no es comprobar que sean tests de verdad. Esta
# puerta mide la cobertura de lo que la feature acaba de escribir (no la
# global, que es deuda histórica). Decide sola si aplica —rama actual, diff
# frente a la rama de integración y nivel de rigor de la feature— y explica el
# motivo cuando se declara N/A. El umbral vive en harness/rigor.json: aquí no
# hay ningún número que tocar.
#
# La campaña de mutación NO corre aquí: es cara (minutos). Se lanza aparte con
#     python -m harness.mutacion --feature F-XXX
# y el reviewer la comprueba por progress/mutacion_F-XXX.md (ver C4 bis).
if [ "$SALTAR_SUITES" -eq 1 ]; then
    warn "PUERTA COBERTURA saltada (portero ligero): corre en el portero completo"
elif [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ]; then
    SALIDA_COBERTURA=$($PY -m harness.cobertura --base "$RAMA_BASE" --config harness/rigor.json 2>&1)
    if [ $? -eq 0 ]; then
        # Una cobertura informativa (F-040) sale con 0 y este prefijo. Va por
        # prefijo a propósito: el CR final de Windows no le afecta.
        case "$SALIDA_COBERTURA" in
            "PUERTA COBERTURA: AVISO"*) warn "$SALIDA_COBERTURA" ;;
            *) ok "$SALIDA_COBERTURA" ;;
        esac
    else
        ko "$SALIDA_COBERTURA"
    fi
elif [ -z "$PY" ]; then
    warn "PUERTA COBERTURA: N/A (no hay intérprete de Python en el PATH: la puerta no se puede medir)"
else
    warn "PUERTA COBERTURA: N/A (proyecto sin Python: harness.cobertura solo mide líneas cambiadas de .py)"
fi

# --- 7 ter. Puerta de RUTAS SENSIBLES (solo si hay declaración) -------------
# Hay ficheros cuyo cambio no lo cubre ningún test unitario por bien escrito
# que esté: un prompt de IA, un schema que un modelo rellena, el cliente de un
# proveedor externo, una migración. Un repositorio puede declararlos en
# harness/rutas_sensibles.json junto con la verificación extra que exigen; si
# el diff de la feature los toca, esta puerta reclama la evidencia.
#
# Misma regla de oro que la sección 7 bis: SIN harness/rutas_sensibles.json no
# se ejecuta ni una línea (el arnés se comporta como siempre), y con el fichero
# roto el arnés cae en KO, porque degradar a "sin puerta" en silencio dejaría
# zonas enteras sin vigilar mientras el portero imprime que todo va bien.
#
# La puerta NUNCA ejecuta la verificación declarada: solo lee su informe.
# Ejecutarla aquí encarecería cada arranque del arnés. El esquema y un ejemplo
# comentado están en harness/rutas_sensibles.ejemplo.json.
if [ -f "harness/rutas_sensibles.json" ] && [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ]; then
    SALIDA_SENSIBLES=$($PY -m harness.rutas_sensibles --puerta --base "$RAMA_BASE" 2>&1)
    CODIGO_SENSIBLES=$?
    case "$CODIGO_SENSIBLES" in
        0) ok "$SALIDA_SENSIBLES" ;;
        3) warn "$SALIDA_SENSIBLES" ;;
        *) ko "$SALIDA_SENSIBLES" ;;
    esac
fi

# --- 7 quater. Puerta de TAMAÑO del papeleo de la feature en curso ----------
# Cada línea de una spec se paga TRES veces: la escribe el spec-author, la lee
# el implementer y la relee el reviewer. El arnés no decía nada del tamaño y
# por eso los agentes escribían cuanto se les ocurría (978 líneas de spec para
# arreglar un script PowerShell). Los topes viven en el bloque `tamano` de
# harness/rigor.json: aquí no hay ningún número que tocar.
#
# Se mide SOLO la feature en curso, a propósito: las specs anteriores exceden
# hoy los topes y medirlas dejaría el portero en rojo permanente o exigiría una
# lista de excepciones que mantener. Lo viejo queda amnistiado por
# construcción; lo que se retome y se edite pasará a medirse.
#
# «En curso» excluye las `done`: una feature cerrada es papeleo cerrado. Sin
# esa exclusión, la amnistía se cae justo en la rama base -donde arranca cada
# sesión- en cuanto una feature cerrada declara esa rama como suya, que es lo
# que pasó con F-015 de `porcentajes`, hecha directamente en `dev`: 546 líneas
# de un review anterior a los topes dejaban `dev` en rojo para siempre.
#
# Códigos de harness.tamano: 0 cabe, 1 se pasa (KO: el portero se pone rojo),
# 2 no aplica (sin configuración o sin bloque `tamano`) => AVISO con el motivo
# impreso, nunca un verde silencioso.
#
# Y por eso hay rama para CADA caso en que la puerta no puede medir, incluido
# el proyecto sin Python: CHECKPOINTS.md promete un N/A "con su motivo impreso"
# y un tramo mudo convierte esa promesa en un checkbox que nadie puede marcar.
if [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ] && [ -f "harness/tamano.py" ]; then
    FEATURE_TAMANO=$($PY - <<'EOF'
from harness.alcance import ejecutar_git
from harness.rigor import cargar_features, feature_de_rama

rama = ejecutar_git(["branch", "--show-current"]).strip()
ficha = feature_de_rama(rama, cargar_features())
if ficha and ficha.get("status") == "done":
    ficha = None  # papeleo cerrado: no hay nada que se vaya a escribir
print(ficha.get("id", "") if ficha else "")
EOF
)
    if [ -z "$FEATURE_TAMANO" ]; then
        warn "PUERTA TAMAÑO: N/A (no hay papeleo abierto que medir: ni la rama actual corresponde a una feature sin cerrar ni hay ninguna activa)"
    else
        SALIDA_TAMANO=$($PY -m harness.tamano --feature "$FEATURE_TAMANO" 2>&1)
        case "$?" in
            0) ok "$SALIDA_TAMANO" ;;
            1) ko "$SALIDA_TAMANO" ;;
            *) warn "$SALIDA_TAMANO" ;;
        esac
    fi
elif [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ]; then
    warn "PUERTA TAMAÑO: N/A (no existe harness/tamano.py: arnés anterior a la puerta de tamaño)"
elif [ -z "$PY" ]; then
    warn "PUERTA TAMAÑO: N/A (no hay intérprete de Python en el PATH: la puerta no se puede medir)"
else
    warn "PUERTA TAMAÑO: N/A (proyecto sin Python: harness.tamano necesita el intérprete del arnés)"
fi

# --- 7 quinquies. Puerta de CARRIL: límites del nivel de la feature ---------
# Un nivel que declara `limites` en harness/rigor.json promete un cambio pequeño
# y sin riesgo; harness.carril lo comprueba contra el diff comprometido. Los
# números viven en rigor.json: aquí no hay ninguno que tocar. Sin `limites` en
# el nivel de la feature, la puerta dice N/A con su motivo.
#
# Python no le pasa a bash ningún valor: bash decide por el código de salida
# (0 cabe o no aplica, 1 se sale, otro no se pudo leer la configuración) y el
# texto solo se imprime, sin el CR que Python escribe en Windows. No depende de
# el portero ligero, igual que la 7 quater: mide git, no ejecuta tests.
if [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ] && [ -f "harness/carril.py" ]; then
    SALIDA_CARRIL=$($PY -m harness.carril --base "$RAMA_BASE" 2>&1)
    CODIGO_CARRIL=$?
    SALIDA_CARRIL=${SALIDA_CARRIL//$'\r'/}
    case "$CODIGO_CARRIL" in
        0) ok "$SALIDA_CARRIL" ;;
        1) ko "$SALIDA_CARRIL" ;;
        *) warn "$SALIDA_CARRIL" ;;
    esac
elif [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ]; then
    warn "PUERTA CARRIL: N/A (no existe harness/carril.py: arnés anterior a la puerta de carril)"
elif [ -z "$PY" ]; then
    warn "PUERTA CARRIL: N/A (no hay intérprete de Python en el PATH: la puerta no se puede medir)"
else
    warn "PUERTA CARRIL: N/A (proyecto sin Python: harness.carril necesita el intérprete del arnés)"
fi

# --- 7 sexies. CAPA E2E: ¿aplica a la feature y está su resumen en verde? ----
# La capa e2e (tests Playwright versionados) la ejecuta `python -m harness.e2e
# --feature F-XXX`, que lanza el agente qa-e2e: es cara (levanta la aplicación
# y un navegador) y por eso esta sección NUNCA la ejecuta. Solo pregunta con
# --estado si aplica (algún servicio declara el bloque `e2e` en
# harness/servicios.json, el nivel la exige o la informa, y el diff toca sus
# `rutas_ui` o la spec marca requisitos `(capa: e2e)`) y si el resumen de
# progress/e2e_F-XXX.md está en verde. Mismo contrato que la 7 ter: 0 OK o
# N/A con su motivo, 3 AVISO (capa informativa), cualquier otro KO. No depende
# del portero ligero: mide git y lee un fichero.
if [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ] && [ -f "harness/e2e.py" ]; then
    SALIDA_E2E=$($PY -m harness.e2e --estado --base "$RAMA_BASE" 2>&1)
    CODIGO_E2E=$?
    SALIDA_E2E=${SALIDA_E2E//$'\r'/}
    case "$CODIGO_E2E" in
        0) ok "$SALIDA_E2E" ;;
        3) warn "$SALIDA_E2E" ;;
        *) ko "$SALIDA_E2E" ;;
    esac
elif [ "$ES_PYTHON" -eq 1 ] && [ -n "$PY" ]; then
    warn "CAPA E2E: N/A (no existe harness/e2e.py: arnés anterior a la capa e2e)"
elif [ -z "$PY" ]; then
    warn "CAPA E2E: N/A (no hay intérprete de Python en el PATH: la capa no se puede consultar)"
else
    warn "CAPA E2E: N/A (proyecto sin Python: harness.e2e necesita el intérprete del arnés)"
fi

# --- 8. Marcas de adaptación sin resolver -----------------------------------
# Un arnés recién instalado y sin adaptar engaña: parece configurado y no lo
# está. Esto no bloquea, pero lo dice en cada arranque hasta que se resuelva.
# La marca se construye partida: si esta sección contuviera el literal, este
# propio fichero saldría señalado como pendiente para siempre en TODOS los
# proyectos, incluso con la adaptación terminada.
MARCA='ADAP''TAR'
PENDIENTES=$(grep -rl "$MARCA" CLAUDE.md CHECKPOINTS.md docs harness specs 2>/dev/null | tr '\n' ' ')
if [ -n "$PENDIENTES" ]; then
    warn "Marcas [$MARCA] sin resolver en: $PENDIENTES"
fi

# --- 9. Comprobaciones específicas del proyecto -----------------------------
# Decisión de este repositorio: NO hay comprobaciones extra. Lo que se podría
# comprobar aquí —que `config/tables_sigrid.yaml` parsea, que sigrid-api
# responde— o ya lo cubren los tests sin tocar red, o exigiría salir a la red
# en cada arranque del portero, que es justo lo que no queremos.
if [ "$COMPROBACIONES_EXTRA" -eq 1 ]; then
    warn "COMPROBACIONES_EXTRA activado pero sin implementar: edita la sección 9"
fi

# --- 10. Rama actual (informativo + guardarraíl) ----------------------------
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    RAMA=$(git branch --show-current)
    ok "Rama actual: ${RAMA:-'(detached)'}"
    if [ "$RAMA" = "main" ]; then
        ko "Estás en 'main'. Los agentes no trabajan en main."
    fi
fi

# --- Veredicto --------------------------------------------------------------
echo "----------------------------------------"
if [ "$FALLOS" -eq 0 ]; then
    printf "${VERDE}ENTORNO LISTO. Puedes trabajar.${NC}\n"
    exit 0
else
    printf "${ROJO}%d comprobaciones fallidas. NO empieces a trabajar.${NC}\n" "$FALLOS"
    exit 1
fi
