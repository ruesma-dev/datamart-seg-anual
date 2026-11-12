# tests/test_f019_plugin_en_proceso.py
"""F-019 · El plugin y el volcado, probados en el proceso de la suite (R2, R3).

`test_f019_plugin.py` los prueba de verdad, pero en subprocesos de coverage
que la puerta de cobertura no ve. Aquí se importan como módulos y se llaman
sus funciones con dobles: el contrato de cada hook, el `pytest_configure` que
saca la variable del orden del entorno y el formato del volcado compacto.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.mapa_tests import DIRECTORIO_PLUGIN

sys.path.insert(0, str(DIRECTORIO_PLUGIN))
import arnes_contextos
import arnes_volcar_mapa


class CoverageDoble:
    def __init__(self) -> None:
        self.contextos: list[str] = []

    def switch_context(self, contexto: str) -> None:
        self.contextos.append(contexto)


def _item(nodeid: str, raiz: Path, invocacion: Path) -> SimpleNamespace:
    config = SimpleNamespace(rootpath=raiz, invocation_params=SimpleNamespace(dir=invocacion))
    return SimpleNamespace(nodeid=nodeid, config=config)


def test_f019_r2_relativo_igual_si_se_lanzo_desde_la_raiz(tmp_path: Path) -> None:
    assert arnes_contextos.relativo("tests/t.py::a[1]", tmp_path, tmp_path) == "tests/t.py::a[1]"


def test_f019_r2_relativo_al_directorio_de_lanzamiento(tmp_path: Path) -> None:
    (tmp_path / "svc").mkdir()

    assert arnes_contextos.relativo("svc/tests/t.py::a", tmp_path, tmp_path / "svc") == "tests/t.py::a"


def test_f019_r2_configure_se_queda_la_variable_y_la_quita_del_entorno(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destino = str(tmp_path / "orden.json")
    monkeypatch.setattr(arnes_contextos, "_destino", None)
    monkeypatch.setenv(arnes_contextos.VARIABLE_ORDEN, destino)

    arnes_contextos.pytest_configure(None)  # type: ignore[arg-type]

    assert arnes_contextos._destino == destino
    assert arnes_contextos.VARIABLE_ORDEN not in os.environ


def test_f019_r2_escribe_el_orden_de_recoleccion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destino = tmp_path / "orden.json"
    monkeypatch.setattr(arnes_contextos, "_destino", str(destino))
    items = [_item("tests/t.py::b", tmp_path, tmp_path), _item("tests/t.py::año", tmp_path, tmp_path)]

    arnes_contextos.pytest_collection_finish(SimpleNamespace(items=items))  # type: ignore[arg-type]

    assert json.loads(destino.read_text(encoding="utf-8")) == ["tests/t.py::b", "tests/t.py::año"]
    assert "año" in destino.read_text(encoding="utf-8"), "UTF-8 legible, sin escapes"


def test_f019_r2_sin_variable_no_escribe_nada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(arnes_contextos, "_destino", None)

    arnes_contextos.pytest_collection_finish(SimpleNamespace(items=[]))  # type: ignore[arg-type]

    assert list(tmp_path.iterdir()) == []


def test_f019_r2_cada_fase_del_test_cambia_al_nodeid_y_al_final_al_vacio(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    doble = CoverageDoble()
    monkeypatch.setattr(arnes_contextos, "_coverage", lambda: doble)
    item = _item("tests/t.py::a", tmp_path, tmp_path)

    arnes_contextos.pytest_runtest_setup(item)  # type: ignore[arg-type]
    arnes_contextos.pytest_runtest_call(item)  # type: ignore[arg-type]
    arnes_contextos.pytest_runtest_teardown(item)  # type: ignore[arg-type]
    arnes_contextos.pytest_runtest_logfinish("tests/t.py::a", None)

    assert doble.contextos == ["tests/t.py::a"] * 3 + [""]


def test_f019_r2_sin_coverage_activo_no_hace_nada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(arnes_contextos, "_coverage", lambda: None)

    arnes_contextos.pytest_runtest_call(_item("tests/t.py::a", tmp_path, tmp_path))  # type: ignore[arg-type]


def test_f019_r2_sin_coverage_instalado_no_hay_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "coverage", None)

    assert arnes_contextos._coverage() is None


# --- El volcado compacto ------------------------------------------------------


def _datos(tmp_path: Path) -> tuple[Path, str]:
    coverage = pytest.importorskip("coverage")
    base = tmp_path / ".coverage"
    fichero = str(tmp_path / "mod.py")
    datos = coverage.CoverageData(basename=str(base))
    datos.set_context("t::a")
    datos.add_lines({fichero: [1, 2]})
    datos.set_context("")
    datos.add_lines({fichero: [2, 3]})
    datos.write()
    return base, fichero


def test_f019_r3_el_volcado_da_contextos_por_linea_con_indices(tmp_path: Path) -> None:
    base, fichero = _datos(tmp_path)
    salida = tmp_path / "volcado.json"

    arnes_volcar_mapa.volcar(str(base), str(salida))

    volcado = json.loads(salida.read_text(encoding="utf-8"))
    assert volcado["contextos"] == ["", "t::a"]
    assert volcado["ficheros"] == {fichero: {"1": [1], "2": [0, 1], "3": [0]}}


def test_f019_r3_el_volcado_se_lanza_como_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    base, _ = _datos(tmp_path)
    salida = tmp_path / "volcado.json"
    monkeypatch.setattr(sys, "argv", ["arnes_volcar_mapa.py", str(base), str(salida)])

    runpy.run_path(str(DIRECTORIO_PLUGIN / "arnes_volcar_mapa.py"), run_name="__main__")

    assert json.loads(salida.read_text(encoding="utf-8"))["contextos"] == ["", "t::a"]
