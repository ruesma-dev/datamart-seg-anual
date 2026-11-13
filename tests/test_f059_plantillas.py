# tests/test_f059_plantillas.py
"""F-059 · R18–R20: plantillas de la capa e2e, solo bajo petición.

Viajan con `harness/` con extensión `.plantilla` (ni pytest, ni compileall, ni
ruff, ni la mutación las ven) y `python -m harness.e2e --plantilla` las coloca
en el servicio sin pisar nada. Sin red y sin Playwright: el conftest se prueba
con pytest real, mirando solo qué colecta.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness import e2e
from harness.servicios import BloqueE2E, Servicio
from harness.tiempos import escalar_timeout

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLAS = RAIZ / "harness" / "plantillas_e2e"


def _servicio(runner: str = "pytest-playwright", ruta_tests: str = "tests_e2e") -> Servicio:
    return Servicio(nombre="web", ruta="web", lenguaje="python" if runner.startswith("pytest")
                    else "otro", e2e=BloqueE2E("http://localhost:8000", ("**",), runner=runner,
                                               ruta_tests=ruta_tests))


def _declarar(raiz: Path, bloque: dict | None, lenguaje: str = "python") -> None:
    (raiz / "web").mkdir(parents=True, exist_ok=True)
    (raiz / "harness").mkdir(exist_ok=True)
    entrada = {"nombre": "web", "ruta": "web", "lenguaje": lenguaje}
    if bloque is not None:
        entrada["e2e"] = bloque
    (raiz / "harness" / "servicios.json").write_text(
        json.dumps({"servicios": [entrada]}), encoding="utf-8")


# --- R18: copia sin pisar y sin instalar --------------------------------------


def test_f059_r18_copia_las_de_pytest_playwright(tmp_path: Path) -> None:
    copiados, omitidos = e2e.copiar_plantillas(_servicio(), str(tmp_path))

    assert copiados == ["web/tests_e2e/conftest.py", "web/tests_e2e/test_f000_r1_smoke.py"]
    assert omitidos == []
    conftest = (tmp_path / "web" / "tests_e2e" / "conftest.py").read_text(encoding="utf-8")
    assert conftest.startswith("# tests_e2e/conftest.py\n")


def test_f059_r18_copia_las_de_playwright_test_con_su_ruta_de_tests(tmp_path: Path) -> None:
    copiados, _ = e2e.copiar_plantillas(_servicio("playwright-test", "pruebas/e2e"),
                                        str(tmp_path))

    assert copiados == ["web/playwright.config.ts", "web/pruebas/e2e/f000_r1_smoke.spec.ts"]
    config = (tmp_path / "web" / "playwright.config.ts").read_text(encoding="utf-8")
    assert "testDir: './pruebas/e2e'" in config and "__RUTA_TESTS__" not in config
    assert "retain-on-failure" in config and "ARNES_E2E_URL_BASE" in config
    assert "ARNES_E2E_SALIDA" in config


def test_f059_r18_no_pisa_lo_que_existe(tmp_path: Path) -> None:
    propio = tmp_path / "web" / "tests_e2e" / "conftest.py"
    propio.parent.mkdir(parents=True)
    propio.write_text("# mío\n", encoding="utf-8")

    copiados, omitidos = e2e.copiar_plantillas(_servicio(), str(tmp_path))

    assert omitidos == ["web/tests_e2e/conftest.py"]
    assert copiados == ["web/tests_e2e/test_f000_r1_smoke.py"]
    assert propio.read_text(encoding="utf-8") == "# mío\n"


def test_f059_r18_la_orden_lista_copiados_y_omitidos(tmp_path: Path, capsys, monkeypatch) -> None:
    _declarar(tmp_path, {"url_base": "http://localhost:8000", "rutas_ui": ["**"]})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("no instala nada"))

    assert e2e.main(["--plantilla", "--servicio", "web", "--raiz", str(tmp_path)]) == 0
    primera = capsys.readouterr().out
    assert e2e.main(["--plantilla", "--servicio", "web", "--raiz", str(tmp_path)]) == 0
    segunda = capsys.readouterr().out

    assert "web/tests_e2e/conftest.py" in primera and "copiad" in primera
    assert "omitid" in segunda and "web/tests_e2e/test_f000_r1_smoke.py" in segunda
    assert "pip install pytest-playwright" in primera


@pytest.mark.parametrize("args", [["--plantilla"], ["--plantilla", "--servicio", "nadie"]],
                         ids=["sin servicio", "inexistente"])
def test_f059_r18_sin_servicio_valido_es_configuracion(tmp_path: Path, args) -> None:
    _declarar(tmp_path, {"url_base": "http://localhost:8000", "rutas_ui": ["**"]})

    assert e2e.main([*args, "--raiz", str(tmp_path)]) == 4


def test_f059_r18_un_servicio_sin_bloque_no_recibe_plantillas(tmp_path: Path) -> None:
    _declarar(tmp_path, None)

    assert e2e.main(["--plantilla", "--servicio", "web", "--raiz", str(tmp_path)]) == 4
    assert not (tmp_path / "web" / "tests_e2e").exists()


# --- R19: la extensión .plantilla ---------------------------------------------


def test_f059_r19_todas_llevan_la_extension_y_hay_las_de_los_dos_runners() -> None:
    ficheros = sorted(p.relative_to(PLANTILLAS).as_posix()
                      for p in PLANTILLAS.rglob("*") if p.is_file())

    assert ficheros == [
        "playwright-test/e2e/f000_r1_smoke.spec.ts.plantilla",
        "playwright-test/playwright.config.ts.plantilla",
        "pytest-playwright/tests_e2e/conftest.py.plantilla",
        "pytest-playwright/tests_e2e/test_f000_r1_smoke.py.plantilla",
    ]


def test_f059_r19_pytest_no_colecta_nada_del_payload(tmp_path: Path) -> None:
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         str(PLANTILLAS)], cwd=tmp_path, capture_output=True, text=True, timeout=escalar_timeout(120),
        env={k: v for k, v in os.environ.items() if k != "ARNES_E2E"}, check=False)

    assert proceso.returncode == 5, proceso.stdout + proceso.stderr


def test_f059_r19_al_copiarse_pierden_la_extension(tmp_path: Path) -> None:
    for runner in ("pytest-playwright", "playwright-test"):
        copiados, _ = e2e.copiar_plantillas(_servicio(runner), str(tmp_path / runner))
        assert copiados and not any(c.endswith(".plantilla") for c in copiados)


# --- R20: sin ARNES_E2E=1, pytest no colecta la carpeta ------------------------


def _colectar(raiz: Path, con_variable: bool) -> subprocess.CompletedProcess:
    entorno = {k: v for k, v in os.environ.items() if k != "ARNES_E2E"}
    if con_variable:
        entorno["ARNES_E2E"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=raiz / "web", capture_output=True, text=True, timeout=escalar_timeout(120), env=entorno,
        check=False)


def test_f059_r20_el_conftest_esconde_la_carpeta_sin_la_variable(tmp_path: Path) -> None:
    e2e.copiar_plantillas(_servicio(), str(tmp_path))
    (tmp_path / "web" / "tests").mkdir()
    (tmp_path / "web" / "tests" / "test_unit.py").write_text(
        "def test_unit():\n    assert True\n", encoding="utf-8")

    sin = _colectar(tmp_path, con_variable=False)
    con = _colectar(tmp_path, con_variable=True)

    assert sin.returncode == 0, sin.stdout + sin.stderr
    assert "test_unit" in sin.stdout and "smoke" not in sin.stdout + sin.stderr
    assert "test_f000_r1_smoke" in con.stdout + con.stderr
