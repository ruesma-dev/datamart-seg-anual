# tests/test_f004_settings.py
"""F-004 · Arreglos mecánicos de `.claude/settings.json` y de los agentes.

El payload no lanza la suite completa en un hook por edición (`PostToolUse`):
la verificación por turno la hace el portero ligero del hook `Stop`. El
reviewer puede recalcular alcance, cobertura, tamaño y mutación sin pedir
permiso, y `implementer.md` / `reviewer.md` no cablean un alias de modelo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SETTINGS = RAIZ / ".claude" / "settings.json"
AGENTES = RAIZ / ".claude" / "agents"

PERMISOS_DEL_REVIEWER = [
    "Bash(python -m harness.alcance*)",
    "Bash(python -m harness.cobertura*)",
    "Bash(python -m harness.mutacion*)",
    "Bash(python -m harness.rigor*)",
    "Bash(python -m harness.servicios*)",
    "Bash(python -m harness.tamano*)",
    "Bash(python harness/backlog.py*)",
    "Bash(git checkout -b*)",
]


def _settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def test_f004_el_payload_no_lanza_la_suite_en_un_hook_por_edicion():
    assert "PostToolUse" not in _settings()["hooks"]


def test_f004_el_adaptar_ya_no_habla_de_un_comando_pytest():
    texto = _settings()["$adaptar"]
    assert "PostToolUse" not in texto
    assert "Stop" in texto


def test_f004_se_conserva_el_portero_ligero_del_stop():
    hooks = _settings()["hooks"]
    comandos = [h["command"] for b in hooks["Stop"] for h in b["hooks"]]
    assert any("ARNES_SALTAR_SUITES=1 bash harness/init.sh" in c for c in comandos)
    assert "SessionStart" in hooks and "SessionEnd" in hooks


@pytest.mark.parametrize("permiso", PERMISOS_DEL_REVIEWER)
def test_f004_el_reviewer_recalcula_sin_pedir_permiso(permiso):
    assert permiso in _settings()["permissions"]["allow"]


@pytest.mark.parametrize("agente", [
    "leader.md", "spec-author.md", "implementer.md", "reviewer.md", "qa-e2e.md"])
def test_f004_los_agentes_no_cablean_un_alias_de_modelo(agente):
    # F-004 los dejó en `inherit`; F-070 (humano, 2026-11-12) fija el ID
    # completo en los cinco. Sigue sin valer un alias.
    texto = (AGENTES / agente).read_text(encoding="utf-8")
    modelo = re.search(r"^model:\s*(\S+)\s*$", texto, re.MULTILINE)
    assert modelo is not None
    assert modelo.group(1) == "claude-opus-5-5"
