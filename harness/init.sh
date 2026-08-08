#!/usr/bin/env bash
# harness/init.sh
# Portero del arnés: decide si el proyecto está en estado apto para que un
# agente empiece a trabajar. Cualquier fallo => exit 1 => el agente NO trabaja.
# Compatible con Git Bash (Windows) y Linux.

set -u
cd "$(dirname "$0")/.." || exit 1

ROJO='\033[0;31m'; VERDE='\033[0;32m'; AMARILLO='\033[0;33m'; NC='\033[0m'
FALLOS=0

ok()   { printf "${VERDE}[OK]${NC} %s\n" "$1"; }
warn() { printf "${AMARILLO}[AVISO]${NC} %s\n" "$1"; }
ko()   { printf "${ROJO}[KO]${NC} %s\n" "$1"; FALLOS=$((FALLOS + 1)); }

# --- 1. Python disponible --------------------------------------------------
if command -v python >/dev/null 2>&1; then
    PY=python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    ko "Python no encontrado en PATH"
    exit 1
fi
ok "Python: $($PY --version 2>&1)"

# --- 2. Ficheros del arnés -------------------------------------------------
for f in CLAUDE.md CHECKPOINTS.md harness/features.json specs/SPECS.md \
         progress/current.md progress/history.md \
         docs/ARCHITECTURE.md docs/CONVENTIONS.md; do
    if [ -f "$f" ]; then ok "Existe $f"; else ko "Falta $f"; fi
done

# --- 3. features.json: esquema, estados y UNA sola in_progress --------------
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
if [ $? -eq 0 ]; then ok "features.json válido"; else ko "features.json inválido (o >1 in_progress)"; fi

# --- 4. Aviso de features bloqueadas (no bloquea, pero se ve) ---------------
if $PY -c "import json,sys; d=json.load(open('harness/features.json',encoding='utf-8')); sys.exit(0 if any(f['status']=='blocked' for f in d['features']) else 1)" 2>/dev/null; then
    warn "Hay features en estado blocked: revisa progress/current.md"
fi

# --- 5. .env presente (no se valida contenido, no se imprime) ---------------
if [ -f ".env" ]; then ok "Existe .env (no versionado)"; else ko "Falta .env — copiar de .env.example"; fi

# --- 6. Compilación de todo el código Python --------------------------------
if $PY -m compileall -q main.py config etl_sigrid scripts tests >/dev/null 2>&1; then
    ok "compileall: sin errores de sintaxis"
else
    ko "compileall: errores de sintaxis"
fi

# --- 6b. Lint (informativo: hay deuda previa, no bloquea el arnés) ----------
# ruff está configurado en pyproject.toml y se instala con requirements-dev.txt.
# No es bloqueante a propósito: el repo arrastra errores anteriores y ponerlo
# en rojo impediría cerrar cualquier feature. Sirve para que la deuda se vea.
if $PY -m ruff --version >/dev/null 2>&1; then
    ERRORES_LINT=$($PY -m ruff check . --output-format=concise 2>/dev/null | grep -cE ":[0-9]+:[0-9]+:")
    ERRORES_LINT=${ERRORES_LINT:-0}   # si `ruff check` peta, no rompas la comparación
    if [ "$ERRORES_LINT" -eq 0 ]; then
        ok "ruff: sin avisos"
    else
        warn "ruff: $ERRORES_LINT avisos (deuda previa, no bloquea). Detalle: python -m ruff check ."
    fi
else
    warn "ruff no instalado: pip install -r requirements-dev.txt"
fi

# --- 7. Tests (los de humo no necesitan red ni BBDD) ------------------------
if $PY -m pytest -q --tb=short -x; then
    ok "pytest en verde"
else
    ko "pytest en rojo"
fi

# --- 8. Rama actual (informativo + guardarraíl) -----------------------------
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
