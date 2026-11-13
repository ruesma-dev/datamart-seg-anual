# tests/test_f019_plugin.py
"""F-019 · El mapa medido de verdad: coverage, el plugin del arnés y el volcado.

Un proyecto de juguete en `tmp_path`, con su suite real, y `EjecutorPytest.
medir_mapa` lanzando coverage y pytest de verdad (R1–R3), con las cuatro
formas de ejecutar una línea que distingue la spec (§1.2 de su informe):
desde un test, solo desde un subproceso, desde una COPIA del fichero y nunca.
Y la degradación (R18): sin coverage, coverage viejo, suite roja, reloj
agotado y mapa sin ningún contexto de test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness import mapa_tests
from harness.mapa_tests import Degradado, MapaTests, construir_mapa
from harness.mutacion import EjecutorPytest
from harness.tiempos import escalar_timeout

pytest.importorskip("coverage", reason="el mapa necesita coverage en el intérprete")

TIMEOUT_S = escalar_timeout(240)

MOD = """\
def a(x):
    return x + 1


def b(x):
    return x * 2


def c(x):
    return x - 3


def d(x):
    return x // 4
"""

TESTS = """\
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pkg import mod

RAIZ = Path(__file__).resolve().parents[1]


def test_a():
    assert mod.a(1) == 2


@pytest.mark.parametrize("v", [1, 2])
def test_param(v):
    assert mod.a(v) == v + 1


def test_subproceso():
    subprocess.run(
        [sys.executable, "-c", "from pkg import mod; assert mod.b(2) == 4"],
        cwd=RAIZ, check=True,
    )


def test_copia(tmp_path):
    destino = tmp_path / "copia" / "pkg"
    shutil.copytree(RAIZ / "pkg", destino)
    spec = importlib.util.spec_from_file_location("copia_mod", destino / "mod.py")
    copia = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copia)
    assert copia.c(5) == 2
"""


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(raiz), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _proyecto(destino: Path, tests: str = TESTS) -> Path:
    (destino / "pkg").mkdir(parents=True)
    (destino / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (destino / "pkg" / "mod.py").write_text(MOD, encoding="utf-8")
    (destino / "tests").mkdir()
    (destino / "tests" / "test_x.py").write_text(tests, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "dev", str(destino)], check=True,
                   capture_output=True)
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")
    return destino


@pytest.fixture(scope="module")
def medido(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, MapaTests | Degradado]:
    raiz = _proyecto(tmp_path_factory.mktemp("f019_plugin") / "proyecto")
    ejecutor = EjecutorPytest(raiz=str(raiz), ruta="tests")
    return raiz, ejecutor.medir_mapa(["pkg/mod.py"], TIMEOUT_S)


def test_f019_r1_mide_el_mapa_con_el_sha_de_head(medido) -> None:
    raiz, mapa = medido
    assert isinstance(mapa, MapaTests), mapa
    assert mapa.sha == _git(raiz, "rev-parse", "HEAD")
    assert mapa.segundos > 0


def test_f019_r1_no_deja_nada_en_el_arbol(medido) -> None:
    raiz, _ = medido
    assert _git(raiz, "status", "--porcelain", "--ignored") == ""


def test_f019_r2_nodeids_de_pytest_relativos_al_lanzamiento(medido) -> None:
    _, mapa = medido
    assert mapa.orden == (
        "tests/test_x.py::test_a",
        "tests/test_x.py::test_param[1]",
        "tests/test_x.py::test_param[2]",
        "tests/test_x.py::test_subproceso",
        "tests/test_x.py::test_copia",
    )
    assert mapa.contextos["pkg/mod.py"][2] == frozenset(
        {"tests/test_x.py::test_a", "tests/test_x.py::test_param[1]",
         "tests/test_x.py::test_param[2]"}
    )


def test_f019_r2_lo_que_corre_fuera_de_un_test_es_contexto_vacio(medido) -> None:
    """La importación del módulo ocurre en la recolección: `def` sin test."""
    _, mapa = medido
    assert "" in mapa.contextos["pkg/mod.py"][1]


def test_f019_r3_una_linea_solo_de_subproceso_queda_con_contexto_vacio(medido) -> None:
    _, mapa = medido
    assert mapa.contextos["pkg/mod.py"][6] == frozenset({""})


def test_f019_r3_una_linea_nunca_ejecutada_no_esta(medido) -> None:
    _, mapa = medido
    assert 14 not in mapa.contextos["pkg/mod.py"]


def test_f019_r4_una_copia_en_un_temporal_cuenta_sin_test(medido) -> None:
    _, mapa = medido
    assert mapa.contextos["pkg/mod.py"][10] == frozenset({""})


# --- R18: degradación --------------------------------------------------------


def test_f019_r18_sin_coverage_en_el_interprete_degrada(tmp_path: Path) -> None:
    ejecutor = EjecutorPytest(raiz=str(tmp_path), ejecutable=str(tmp_path / "no_existe.exe"))

    resultado = ejecutor.medir_mapa(["pkg/mod.py"], 30)

    assert isinstance(resultado, Degradado)
    assert "coverage" in resultado.motivo


def test_f019_r18_coverage_sin_el_modulo_degrada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mapa_tests, "_version_de_coverage", lambda _e, _env: (1, "No module"))

    resultado = EjecutorPytest(raiz=str(tmp_path)).medir_mapa(["pkg/mod.py"], 30)

    assert isinstance(resultado, Degradado)
    assert "no tiene coverage" in resultado.motivo


def test_f019_r18_coverage_anterior_a_7_10_degrada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mapa_tests, "_version_de_coverage",
        lambda _e, _env: (0, "Coverage.py, version 7.9.2 with C extension"),
    )

    resultado = EjecutorPytest(raiz=str(tmp_path)).medir_mapa(["pkg/mod.py"], 30)

    assert isinstance(resultado, Degradado)
    assert "7.10" in resultado.motivo


def test_f019_r18_suite_roja_degrada(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path / "rojo", tests="from pkg import mod\n\n\ndef test_rojo():\n"
                     "    assert mod.a(1) == 3\n")

    resultado = EjecutorPytest(raiz=str(raiz), ruta="tests").medir_mapa(
        ["pkg/mod.py"], TIMEOUT_S
    )

    assert isinstance(resultado, Degradado)
    assert "código 1" in resultado.motivo


def test_f019_r18_medicion_que_expira_degrada(tmp_path: Path) -> None:
    raiz = _proyecto(tmp_path / "lento", tests="import time\n\n\ndef test_lento():\n"
                     "    time.sleep(60)\n")

    resultado = EjecutorPytest(raiz=str(raiz), ruta="tests").medir_mapa(["pkg/mod.py"], 3)

    assert isinstance(resultado, Degradado)
    assert "expiró" in resultado.motivo


def test_f019_r18_mapa_sin_ningun_contexto_de_test_degrada(tmp_path: Path) -> None:
    datos = {"contextos": [""], "ficheros": {str(tmp_path / "pkg" / "mod.py"): {"1": [0]}}}

    resultado = construir_mapa(datos, ["tests/test_x.py::test_a"], str(tmp_path),
                               ["pkg/mod.py"], "abc", 1.0)

    assert isinstance(resultado, Degradado)
    assert "ningún contexto de test" in resultado.motivo


def test_f019_r18_sin_tests_recogidos_degrada(tmp_path: Path) -> None:
    datos = {"contextos": ["", "t::x"], "ficheros": {}}

    resultado = construir_mapa(datos, [], str(tmp_path), ["pkg/mod.py"], "abc", 1.0)

    assert isinstance(resultado, Degradado)


def test_f019_r2_el_plugin_sin_coverage_no_hace_nada(tmp_path: Path) -> None:
    """Cargado en una suite normal (sin `coverage run`), el plugin no estorba."""
    raiz = _proyecto(tmp_path / "normal")
    entorno = EjecutorPytest(raiz=str(raiz)).entorno()
    entorno["PYTHONPATH"] = str(mapa_tests.DIRECTORIO_PLUGIN)
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "arnes_contextos", "-p",
         "no:cacheprovider", "tests"],
        cwd=raiz, capture_output=True, text=True, env=entorno, timeout=TIMEOUT_S, check=False,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr


# --- R9 con pytest de verdad -------------------------------------------------


def test_f019_r9_el_subconjunto_corre_solo_esos_tests(medido) -> None:
    raiz, _ = medido
    ejecutor = EjecutorPytest(raiz=str(raiz), ruta="tests")

    assert ejecutor.subconjunto_verde(("tests/test_x.py::test_param[2]",), TIMEOUT_S)
    resultado = ejecutor.correr(TIMEOUT_S, ids=("tests/test_x.py::test_a",))
    assert resultado.codigo == 0
    assert "1 passed" in resultado.salida


def test_f019_r13_un_nodeid_que_no_existe_no_es_un_subconjunto_verde(medido) -> None:
    raiz, _ = medido
    ejecutor = EjecutorPytest(raiz=str(raiz), ruta="tests")

    assert not ejecutor.subconjunto_verde(("tests/test_x.py::no_existe",), TIMEOUT_S)


# --- Una suite que lanza pytest dentro de sus tests (hallazgo de T15) ---------

TESTS_ANIDADOS = TESTS + '''

def test_lanza_otro_pytest():
    # Como la suite del propio arnés: un test que corre pytest en otro proyecto
    # heredando el entorno, plugin y variable del orden incluidos.
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-p", "arnes_contextos", "interno"],
        cwd=RAIZ, check=True,
    )
'''


def test_f019_r2_un_pytest_anidado_no_pisa_el_orden_de_recoleccion(tmp_path: Path) -> None:
    raiz = tmp_path / "proyecto"
    (raiz / "interno").mkdir(parents=True)
    (raiz / "interno" / "test_y.py").write_text("def test_y():\n    pass\n", encoding="utf-8")
    _proyecto(raiz, tests=TESTS_ANIDADOS)

    mapa = EjecutorPytest(raiz=str(raiz), ruta="tests").medir_mapa(["pkg/mod.py"], TIMEOUT_S)

    assert isinstance(mapa, MapaTests), mapa
    assert "interno/test_y.py::test_y" not in mapa.orden
    assert mapa.orden[-1] == "tests/test_x.py::test_lanza_otro_pytest"
    assert len(mapa.orden) == 6
