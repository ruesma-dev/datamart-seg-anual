# tests/test_f070_compatibilidad.py
"""F-070 · R29–R30 punta a punta: un proyecto que conserva sus adaptados.

Sobre una copia del payload sin `politica_ficheros.json` al lado (como en un
proyecto), con `CHECKPOINTS.md`, `CLAUDE.md`, `.claude/settings.json` y
`docs/CONVENTIONS.md` en su versión de antes de F-070 (la de la rama `dev`): un
único rojo por fichero, con la instrucción de qué aceptar, y sus dependientes
saltados con ese motivo.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
ADAPTADOS = ("CHECKPOINTS.md", "CLAUDE.md", ".claude/settings.json", "docs/CONVENTIONS.md")
FICHEROS = ("test_f070_textos.py", "test_f070_modelo_y_esfuerzo.py")
ROJOS = {
    "test_f070_r29_el_checkpoints_instalado_trae_c3_quater_y_evidencias":
        "acepta esos bloques del diff de CHECKPOINTS.md",
    "test_f070_r30_el_claude_md_instalado_trae_paradas_y_ecosistema":
        "acepta esos bloques del diff de CLAUDE.md",
    "test_f070_r30_el_settings_instalado_trae_model_y_effortlevel":
        "acepta las claves `model` y `effortLevel` del diff de .claude/settings.json",
    "test_f070_d3_el_conventions_instalado_dice_quien_hace_cada_merge":
        "acepta la sección «Git» del diff de docs/CONVENTIONS.md",
}
DEPENDIENTES = {
    "test_f070_r7_": "CLAUDE.md", "test_f070_r8_": "CLAUDE.md",
    "test_f070_r30_un_claude_md_": "CLAUDE.md",
    "test_f070_r12_c3_quater_": "CHECKPOINTS.md", "test_f070_r26_": "CHECKPOINTS.md",
    "test_f070_r29_un_checkpoints_": "CHECKPOINTS.md",
    "test_f070_r19_": ".claude/settings.json", "test_f070_r20_settings_": ".claude/settings.json",
    "test_f070_r30_un_settings_": ".claude/settings.json",
    "test_f070_d3_claude_md_": "CLAUDE.md", "test_f070_d3_conventions_merges": "docs/CONVENTIONS.md",
}


def _version_de_dev(relativa: str) -> str | None:
    """El fichero del payload en `dev` (antes de F-070), o None sin git o sin rama."""
    try:
        salida = subprocess.run(
            ["git", "show", f"dev:arnes-base/{relativa}"], cwd=RAIZ, capture_output=True,
            timeout=escalar_timeout(60), check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if salida.returncode != 0:
        return None
    return salida.stdout.decode("utf-8")


def _casos(ruta: Path) -> dict[str, tuple[str, str]]:
    casos = {}
    for caso in ET.parse(ruta).iter("testcase"):
        resultado, mensaje = "passed", ""
        for hijo in caso:
            if hijo.tag in ("failure", "error", "skipped"):
                resultado, mensaje = hijo.tag, hijo.get("message", "")
        casos[caso.get("name", "")] = (resultado, mensaje)
    return casos


def test_f070_r29_r30_con_los_adaptados_viejos_un_rojo_por_fichero(tmp_path: Path) -> None:
    viejos = {relativa: _version_de_dev(relativa) for relativa in ADAPTADOS}
    if any(texto is None for texto in viejos.values()):
        pytest.skip("sin git o sin rama `dev`: no hay versión anterior a F-070 que poner")
    if all(texto == (RAIZ / r).read_text(encoding="utf-8") for r, texto in viejos.items()):
        pytest.skip("`dev` ya trae F-070: no hay versión anterior con la que probar")
    proyecto = tmp_path / "proyecto"
    for carpeta in ("harness", ".claude", "specs"):
        shutil.copytree(RAIZ / carpeta, proyecto / carpeta, ignore=shutil.ignore_patterns(
            "__pycache__", "settings.local.json"))
    (proyecto / "tests").mkdir()
    for nombre in FICHEROS:
        shutil.copy2(RAIZ / "tests" / nombre, proyecto / "tests" / nombre)
    for relativa, texto in viejos.items():
        (proyecto / relativa).parent.mkdir(parents=True, exist_ok=True)
        (proyecto / relativa).write_text(texto or "", encoding="utf-8", newline="\n")
    informe = tmp_path / "junit.xml"

    subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
         f"--junitxml={informe}", *(f"tests/{nombre}" for nombre in FICHEROS)],
        cwd=proyecto, capture_output=True, text=True, timeout=escalar_timeout(300), check=False,
    )

    casos = _casos(informe)
    rojos = {n: m for n, (r, m) in casos.items() if r in ("failure", "error")}
    assert sorted(rojos) == sorted(ROJOS), rojos
    for nombre, instruccion in ROJOS.items():
        assert instruccion in rojos[nombre], (nombre, rojos[nombre])
    for prefijo, fichero in DEPENDIENTES.items():
        saltados = {n: v for n, v in casos.items() if n.startswith(prefijo)}
        assert saltados, prefijo
        for nombre, (resultado, mensaje) in saltados.items():
            assert resultado == "skipped", (nombre, resultado)
            assert "acepta" in mensaje and f"diff de {fichero}" in mensaje, (nombre, mensaje)
