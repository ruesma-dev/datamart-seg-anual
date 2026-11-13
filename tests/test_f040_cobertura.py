# tests/test_f040_cobertura.py
"""F-040: cobertura informativa. Se mide igual que si se exigiera y no bloquea.

Mismo montaje que `test_base_de_la_puerta.py`: repositorio de juguete y
configuración de rigor inyectada, nunca el `harness/rigor.json` del proyecto.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import cobertura

RAMA = "feature/F-900-x"
RIGOR = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": True},
        "rapido": {"fase_red": False, "cobertura": False, "mutacion": False,
                   "informativas": ["cobertura"]},
        "documental": {"fase_red": False, "cobertura": False, "mutacion": False},
    },
}
#: Dos líneas ejecutables, una cubierta: 50 %, bajo el umbral.
COV_BAJA = {"files": {"app/nuevo.py": {"executed_lines": [2], "missing_lines": [3]}}}
COV_ALTA = {"files": {"app/nuevo.py": {"executed_lines": [2, 3], "missing_lines": []}}}


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(raiz), "-c", "user.name=Arnes",
         "-c", "user.email=arnes@ejemplo.invalid", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    (raiz / "app").mkdir()
    (raiz / "app" / "base.py").write_text("X = 1\n", encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "inicio")
    _git(raiz, "checkout", "-q", "-b", RAMA)
    (raiz / "app" / "nuevo.py").write_text(
        "# app/nuevo.py\ndef nuevo():\n    return 3\n", encoding="utf-8", newline="\n")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "F-900 T1: nuevo")
    return raiz


def _puerta(raiz: Path, nivel: str = "rapido", cov: object = COV_BAJA,
            rigor: dict | None = None, base: str = "dev") -> int:
    fuera = raiz.parent
    ficha = {"id": "F-900", "title": "T", "status": "in_progress", "sdd": False,
             "rigor": nivel, "branch": RAMA}
    (fuera / "features.json").write_text(json.dumps({"features": [ficha]}), encoding="utf-8")
    (fuera / "rigor.json").write_text(json.dumps(rigor or RIGOR), encoding="utf-8")
    ruta_cov = fuera / "coverage.json"
    if isinstance(cov, str):
        ruta_cov.write_text(cov, encoding="utf-8")
    elif cov is not None:
        ruta_cov.write_text(json.dumps(cov), encoding="utf-8")
    return cobertura.main(["--base", base, "--config", str(fuera / "rigor.json"),
                           "--features", str(fuera / "features.json"),
                           "--cov", str(ruta_cov), "--raiz", str(raiz)])


# --- R21: bajo el umbral, aviso y 0 ------------------------------------------


def test_f040_r21_bajo_el_umbral_avisa_con_la_medida_y_sale_0(repo, capsys) -> None:
    assert _puerta(repo) == 0

    salida = capsys.readouterr().out
    assert salida.startswith("PUERTA COBERTURA: AVISO (")
    assert "no bloquea" in salida and "nivel rapido" in salida
    assert "50.0% de 2 líneas" in salida and "umbral 80%" in salida


def test_f040_r21_sobre_el_umbral_es_la_linea_de_siempre(repo, capsys) -> None:
    assert _puerta(repo, cov=COV_ALTA) == 0

    salida = capsys.readouterr().out
    assert salida.startswith("PUERTA COBERTURA: 100.0% de 2 líneas")
    assert "AVISO" not in salida


def test_f040_r21_el_mismo_diff_en_un_nivel_que_exige_sigue_en_rojo(repo, capsys) -> None:
    assert _puerta(repo, nivel="estandar") == 1

    captura = capsys.readouterr()
    assert "AVISO" not in captura.out + captura.err
    assert "50.0% de 2 líneas" in captura.err


# --- R22: ninguna causa bloquea en modo informativo --------------------------


def test_f040_r22_base_rezagada_avisa(repo, capsys) -> None:
    _git(repo, "branch", "main")

    assert _puerta(repo) == 0
    salida = capsys.readouterr().out
    assert salida.startswith("PUERTA COBERTURA: AVISO (")
    assert "se ha quedado por detrás" in salida


def test_f040_r22_sin_informe_de_cobertura_avisa(repo, capsys) -> None:
    assert _puerta(repo, cov=None) == 0
    salida = capsys.readouterr().out
    assert salida.startswith("PUERTA COBERTURA: AVISO (")
    assert cobertura.MENSAJE_INSTALACION in salida


def test_f040_r22_sin_coverage_instalado_avisa(repo, capsys, monkeypatch) -> None:
    monkeypatch.setattr(cobertura, "hay_coverage", lambda: False)

    assert _puerta(repo) == 0
    assert "AVISO" in capsys.readouterr().out


def test_f040_r22_informe_ilegible_avisa(repo, capsys) -> None:
    assert _puerta(repo, cov="{roto") == 0
    salida = capsys.readouterr().out
    assert salida.startswith("PUERTA COBERTURA: AVISO (")
    assert "no es JSON válido" in salida


def test_f040_r22_servicios_rotos_avisa(repo, capsys) -> None:
    (repo / "harness").mkdir()
    (repo / "harness" / "servicios.json").write_text("{roto", encoding="utf-8")

    assert _puerta(repo) == 0
    assert "AVISO" in capsys.readouterr().out


def test_f040_r22_sin_umbral_declarado_avisa(repo, capsys) -> None:
    rigor = {**RIGOR, "cobertura": {}}

    assert _puerta(repo, rigor=rigor) == 0
    assert "AVISO" in capsys.readouterr().out


def test_f040_r22_sin_umbral_en_un_nivel_que_exige_es_rojo(repo, capsys) -> None:
    rigor = {**RIGOR, "cobertura": {}}

    assert _puerta(repo, nivel="estandar", rigor=rigor) == 1
    assert "umbral_lineas_cambiadas" in capsys.readouterr().err


# --- R24: sin `cobertura` ni `informativas`, el N/A de hoy --------------------


def test_f040_r24_nivel_sin_cobertura_da_el_na_literal(repo, capsys) -> None:
    assert _puerta(repo, nivel="documental") == 0

    assert capsys.readouterr().out == (
        "PUERTA COBERTURA: N/A (F-900 es de nivel documental: no exige cobertura)\n"
    )
