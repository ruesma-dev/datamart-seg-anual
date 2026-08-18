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
# mucho una feature `in_progress`, que exista `.env` si el proyecto lo usa, y
# que no estés trabajando en `main`.
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
RAMA_BASE=dev            # rama de integración contra la que se calcula el
                         # diff de la feature (puerta de cobertura y mutación)
COMPROBACIONES_EXTRA=0   # sin comprobaciones extra en la sección 9

# Modo ligero (para hooks): con ARNES_SALTAR_SUITES=1 el portero salta las
# suites de tests y la puerta de cobertura, avisándolo en cada sección. NO
# vale para cerrar una feature: el cierre exige el portero completo
# (`bash harness/init.sh` a secas).
SALTAR_SUITES="${ARNES_SALTAR_SUITES:-0}"

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
        ok "Python: $($PY --version 2>&1)"
    else
        ko "Proyecto Python pero no hay intérprete en PATH (¿venv sin activar?)"
        exit 1
    fi
else
    warn "Proyecto no Python: se saltan compilación, lint y pytest (ver cabecera de este fichero)"
fi

# --- 2. Ficheros del arnés --------------------------------------------------
for f in CLAUDE.md CHECKPOINTS.md harness/features.json harness/rigor.json \
         specs/SPECS.md progress/current.md progress/history.md \
         docs/ARCHITECTURE.md docs/CONVENTIONS.md; do
    if [ -f "$f" ]; then ok "Existe $f"; else ko "Falta $f"; fi
done

# --- 3. features.json: esquema, estados y UNA sola in_progress --------------
# Se valida con el primer intérprete disponible. Sin ninguno, degrada a texto.
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
    estados = {"pending", "spec_ready", "in_progress", "done", "blocked"}
    en_curso = []
    for f in data["features"]:
        assert {"id", "title", "status", "sdd"} <= set(f), f"Feature incompleta: {f}"
        assert f["status"] in estados, f"Estado inválido en {f['id']}: {f['status']}"
        if f["status"] == "in_progress":
            en_curso.append(f["id"])
    if len(en_curso) > 1:
        print(f"Hay {len(en_curso)} features in_progress ({', '.join(en_curso)}). Máximo 1.",
              file=sys.stderr)
        sys.exit(1)
    bloqueadas = [f["id"] for f in data["features"] if f["status"] == "blocked"]
    abiertas = sum(1 for f in data["features"] if f["status"] != "done")
    print(f"    {len(data['features'])} features, {abiertas} abiertas, "
          f"en curso: {en_curso or 'ninguna'}, bloqueadas: {bloqueadas or 'ninguna'}")
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
  const estados = ["pending","spec_ready","in_progress","done","blocked"];
  const enCurso = [];
  for (const f of d.features) {
    for (const k of ["id","title","status","sdd"]) {
      if (!(k in f)) throw new Error("Feature incompleta, falta " + k + ": " + JSON.stringify(f));
    }
    if (!estados.includes(f.status)) throw new Error("Estado inválido en " + f.id + ": " + f.status);
    if (f.status === "in_progress") enCurso.push(f.id);
  }
  if (enCurso.length > 1) {
    console.error("Hay " + enCurso.length + " features in_progress (" + enCurso.join(", ") + "). Máximo 1.");
    process.exit(1);
  }
  const bloq = d.features.filter(f => f.status === "blocked").map(f => f.id);
  const abiertas = d.features.filter(f => f.status !== "done").length;
  console.log("    " + d.features.length + " features, " + abiertas + " abiertas, en curso: " +
              (enCurso.length ? enCurso.join(", ") : "ninguna") + ", bloqueadas: " +
              (bloq.length ? bloq.join(", ") : "ninguna"));
} catch (e) { console.error("features.json inválido: " + e.message); process.exit(1); }
'
    RES=$?
    ;;
jq)
    if jq -e '
        (.features | length) > 0
        and ([.features[] | select(.status == "in_progress")] | length) <= 1
        and all(.features[]; (has("id") and has("title") and has("status") and has("sdd"))
                and (["pending","spec_ready","in_progress","done","blocked"] | index(.status)))
    ' harness/features.json >/dev/null 2>&1; then
        printf "    %s features, en curso: %s\n" \
            "$(jq '.features | length' harness/features.json)" \
            "$(jq -r '[.features[] | select(.status=="in_progress") | .id] | if length == 0 then "ninguna" else join(", ") end' harness/features.json)"
        RES=0
    else
        echo "features.json inválido, o más de una feature in_progress" >&2
        RES=1
    fi
    ;;
*)
    warn "Sin python, node ni jq: validación de features.json DEGRADADA (solo texto)"
    EN_CURSO=$(grep -o '"status"[[:space:]]*:[[:space:]]*"in_progress"' harness/features.json 2>/dev/null | wc -l)
    if [ "${EN_CURSO:-0}" -gt 1 ]; then
        echo "Hay $EN_CURSO features in_progress. Máximo 1." >&2
        RES=1
    else
        RES=0
    fi
    ;;
esac
if [ "$RES" -eq 0 ]; then ok "features.json válido"; else ko "features.json inválido (o >1 in_progress)"; fi

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

# --- 3b. Niveles de rigor: configuración válida y niveles declarados válidos -
# Lo que exige cada nivel vive en harness/rigor.json. Una feature que no
# declara nivel NO es un error: se le aplica el más exigente. Declarar uno
# inexistente sí lo es. Necesita Python: sin él, degrada con aviso.
if [ -n "$PY" ]; then
    if $PY -m harness.rigor --validar; then
        ok "harness/rigor.json y niveles declarados: válidos"
    else
        ko "harness/rigor.json o el campo 'rigor' de alguna feature no son válidos"
    fi
else
    warn "Sin Python: no se validan los niveles de rigor de harness/rigor.json"
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
if [ -f "harness/servicios.json" ]; then
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
                # Caché de suite: si el árbol del servicio no ha cambiado desde
                # su último verde (mismo árbol commiteado y sin ficheros sucios
                # en su ruta), la suite se salta. Cualquier edición, commit o
                # fichero nuevo bajo la ruta del servicio invalida la caché.
                HASH_SRV=$(git rev-parse "HEAD:$RUTA" 2>/dev/null)
                SUCIO_SRV=$(git status --porcelain -- "$RUTA" 2>/dev/null | head -n 1)
                CACHE_SRV=".arnes_cache/suite_${NOMBRE}.ok"
                if [ -n "$HASH_SRV" ] && [ -z "$SUCIO_SRV" ] && [ -f "$CACHE_SRV" ] \
                   && [ "$(cat "$CACHE_SRV" 2>/dev/null)" = "$HASH_SRV" ]; then
                    # Con coverage disponible, solo vale la caché si el
                    # coverage.json de ese mismo árbol sigue ahí (la puerta
                    # de la sección 7b puede necesitarlo).
                    if ! "$INTERPRETE" -c "import coverage" >/dev/null 2>&1 \
                       || [ -f "$RUTA/coverage.json" ]; then
                        ok "servicio $NOMBRE ($RUTA): pytest en verde (caché: árbol sin cambios desde el último verde)"
                        continue
                    fi
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
                    # Solo se cachea un verde de árbol limpio: el hash describe
                    # el árbol commiteado, no el estado sucio.
                    if [ -n "$HASH_SRV" ] && [ -z "$SUCIO_SRV" ]; then
                        mkdir -p .arnes_cache && printf '%s' "$HASH_SRV" > "$CACHE_SRV"
                    fi
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
        ok "$SALIDA_COBERTURA"
    else
        ko "$SALIDA_COBERTURA"
    fi
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
