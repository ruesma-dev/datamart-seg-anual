# tests/test_f058_cobertura.py
"""F-058 · R20–R22: el umbral de cobertura puede ser del nivel.

Mismo montaje que `test_f040_cobertura.py`: repositorio de juguete y
configuración de rigor inyectada, nunca el `harness/rigor.json` del proyecto.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from harness import cobertura
from harness.rigor import (
    cargar_rigor,
    umbral_cobertura,
    umbral_cobertura_con_origen,
    umbrales_por_nivel,
)
from harness.rigor import main as rigor_main

RAMA = "feature/F-900-x"
RIGOR = {
    "nivel_por_defecto": "estandar",
    "cobertura": {"umbral_lineas_cambiadas": 80},
    "niveles": {
        "estandar": {"fase_red": True, "cobertura": True, "mutacion": True},
        "critico": {"fase_red": True, "cobertura": True, "mutacion": True,
                    "umbral_cobertura": 40},
        "estricto": {"fase_red": True, "cobertura": True, "mutacion": True,
                     "umbral_cobertura": 100},
    },
}
#: Dos líneas ejecutables, una cubierta: 50 %.
COV = {"files": {"app/nuevo.py": {"executed_lines": [2], "missing_lines": [3]}}}


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


def _puerta(raiz: Path, nivel: str) -> int:
    fuera = raiz.parent
    ficha = {"id": "F-900", "title": "T", "status": "in_progress", "sdd": False,
             "rigor": nivel, "branch": RAMA}
    (fuera / "features.json").write_text(json.dumps({"features": [ficha]}), encoding="utf-8")
    (fuera / "rigor.json").write_text(json.dumps(RIGOR), encoding="utf-8")
    (fuera / "coverage.json").write_text(json.dumps(COV), encoding="utf-8")
    return cobertura.main(["--base", "dev", "--config", str(fuera / "rigor.json"),
                           "--features", str(fuera / "features.json"),
                           "--cov", str(fuera / "coverage.json"), "--raiz", str(raiz)])


# --- R20 ------------------------------------------------------------------------


def test_f058_r20_el_umbral_del_nivel_pisa_al_global() -> None:
    assert umbral_cobertura(RIGOR, "critico") == 40
    assert umbral_cobertura_con_origen(RIGOR, "critico") == (40, "nivel")


def test_f058_r20_sin_umbral_propio_manda_el_global() -> None:
    assert umbral_cobertura(RIGOR, "estandar") == 80
    assert umbral_cobertura_con_origen(RIGOR, "estandar") == (80, "global")
    assert umbral_cobertura_con_origen(RIGOR, "inventado") == (80, "global")
    assert umbral_cobertura(RIGOR) == 80


def test_f058_r20_un_umbral_de_cero_es_un_umbral() -> None:
    rigor = {**RIGOR, "niveles": {"cero": {"umbral_cobertura": 0}}}

    assert umbral_cobertura_con_origen(rigor, "cero") == (0, "nivel")


def test_f058_r20_el_nivel_sin_global_sigue_valiendo() -> None:
    rigor = {**RIGOR, "cobertura": {}}

    assert umbral_cobertura_con_origen(rigor, "critico") == (40, "nivel")
    with pytest.raises(ValueError, match="umbral_lineas_cambiadas"):
        umbral_cobertura_con_origen(rigor, "estandar")


def test_f058_r20_r22_la_puerta_usa_el_del_nivel_y_lo_dice(repo: Path, capsys) -> None:
    assert _puerta(repo, "critico") == 0

    salida = capsys.readouterr().out
    assert "50.0% de 2 líneas" in salida
    assert "umbral 40% (del nivel critico)" in salida


def test_f058_r20_r22_la_puerta_usa_el_global_y_lo_dice(repo: Path, capsys) -> None:
    assert _puerta(repo, "estandar") == 1

    assert "umbral 80% (global)" in capsys.readouterr().err


def test_f058_r20_un_umbral_de_nivel_mas_alto_bloquea(repo: Path, capsys) -> None:
    assert _puerta(repo, "estricto") == 1

    assert "umbral 100% (del nivel estricto)" in capsys.readouterr().err


# --- R21 ------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [101, -1, True, 80.5, "80", None])
def test_f058_r21_un_umbral_de_nivel_raro_es_error(valor: object, tmp_path: Path) -> None:
    datos = json.loads(json.dumps(RIGOR))
    datos["niveles"]["critico"]["umbral_cobertura"] = valor
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    with pytest.raises(ValueError) as error:
        cargar_rigor(ruta)
    assert "'critico'" in str(error.value) and "umbral_cobertura" in str(error.value)


@pytest.mark.parametrize("valor", [0, 100, 90])
def test_f058_r21_los_umbrales_legitimos_pasan(valor: int, tmp_path: Path) -> None:
    datos = json.loads(json.dumps(RIGOR))
    datos["niveles"]["critico"]["umbral_cobertura"] = valor
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    assert cargar_rigor(ruta)["niveles"]["critico"]["umbral_cobertura"] == valor


# --- R22: --validar lista los que pisan el global -------------------------------


def test_f058_r22_umbrales_por_nivel() -> None:
    assert umbrales_por_nivel(RIGOR) == {"critico": 40, "estricto": 100}
    assert umbrales_por_nivel({"niveles": {"a": {}}}) == {}


def test_f058_r22_validar_dice_que_niveles_pisan_el_global(tmp_path: Path, capsys) -> None:
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(RIGOR), encoding="utf-8")
    features = tmp_path / "features.json"
    features.write_text('{"features": []}', encoding="utf-8")

    assert rigor_main(["--validar", "--config", str(ruta), "--features", str(features)]) == 0

    salida = capsys.readouterr().out
    assert ("umbral de cobertura 80%; pisan el global: critico 40%, estricto 100%"
            in salida)


def test_f058_r22_sin_umbrales_de_nivel_la_linea_de_hoy(tmp_path: Path, capsys) -> None:
    datos = json.loads(json.dumps(RIGOR))
    for definicion in datos["niveles"].values():
        definicion.pop("umbral_cobertura", None)
    ruta = tmp_path / "rigor.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    features = tmp_path / "features.json"
    features.write_text('{"features": []}', encoding="utf-8")

    rigor_main(["--validar", "--config", str(ruta), "--features", str(features)])

    assert capsys.readouterr().out == (
        "    niveles: critico, estandar, estricto; por defecto estandar; umbral de "
        "cobertura 80%\n"
    )
