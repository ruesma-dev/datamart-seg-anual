# tests/test_f019_supervivientes.py
"""F-019 · Pasada 5: tests que cierran los huecos reales de la campaña oficial C4 bis.

La campaña de `progress/mutacion_F-019.md` (motor del portero, serie, 40
mutantes) dejó 12 supervivientes. Cada test de aquí mata uno que era un hueco
real; los equivalentes llevan su demostración ejecutable al final (RM5).
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness import mapa_tests, mutacion
from harness.alcance import Alcance
from harness.mapa_tests import (
    DIRECTORIO_PLUGIN,
    Degradado,
    MapaTests,
    lineas_de_sentencia,
)
from harness.mutacion import InformeMutacion, filas_de_seleccion

sys.path.insert(0, str(DIRECTORIO_PLUGIN))
import arnes_contextos

# --- mapa_tests.py:83 · `Degradado` es inmutable y hashable --------------------


def test_f019_r18_degradado_es_un_valor_inmutable() -> None:
    motivo = Degradado("sin coverage")

    with pytest.raises(dataclasses.FrozenInstanceError):
        motivo.motivo = "otro"  # type: ignore[misc]
    assert {motivo, Degradado("sin coverage")} == {motivo}, "hashable: sirve de valor"


# --- mapa_tests.py:104 · el final de un `case` es su última sentencia -----------

CON_MATCH = """\
def f(x):
    match x:
        case 1:
            a = 1
            b = 2
        case _:
            c = 3
"""


def test_f019_r7_una_sentencia_dentro_de_un_case_es_solo_ella() -> None:
    assert lineas_de_sentencia(CON_MATCH, 5) == {5}
    assert lineas_de_sentencia(CON_MATCH, 7) == {7}


# --- mapa_tests.py:150 · un decorador multilínea entra entero -------------------

CON_DECORADOR = """\
@decorador(
    1,
    2,
)
def g():
    return 1
"""


def test_f019_r7_la_cabecera_con_decorador_multilinea_lo_incluye_entero() -> None:
    assert lineas_de_sentencia(CON_DECORADOR, 5) == {1, 2, 3, 4, 5}


# --- mapa_tests.py:399 y :405 · combinar o volcar que falla es un Degradado -----


class _Ejecutor:
    ejecutable = "py"
    ruta = "tests"

    def __init__(self, raiz: Path) -> None:
        self.raiz = str(raiz)

    def entorno(self) -> dict[str, str]:
        return {}

    def argumentos_linea_base(self) -> tuple[str, ...]:
        return ("-q",)


@pytest.mark.parametrize(
    ("falla", "codigos"),
    [("combine", "(códigos 1 y 0)"), ("arnes_volcar_mapa.py", "(códigos 0 y 1)")],
)
def test_f019_r18_combinar_o_volcar_que_falla_degrada_y_no_revienta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, falla: str, codigos: str
) -> None:
    def _run(orden: list[str], *_a: object, check: bool = False, **_k: object):
        # Como `subprocess.run` de verdad: con `check=True`, un código distinto
        # de 0 es una excepción, no un resultado.
        codigo = 1 if any(falla in str(parte) for parte in orden) else 0
        if check and codigo:
            raise subprocess.CalledProcessError(codigo, orden)
        return SimpleNamespace(returncode=codigo, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        mapa_tests,
        "_version_de_coverage",
        lambda _e, _env: (0, "Coverage.py, version 7.15.4"),
    )
    monkeypatch.setattr(mapa_tests.subprocess, "run", _run)

    resultado = mapa_tests.medir(_Ejecutor(tmp_path), ["pkg/mod.py"], 60)

    assert isinstance(resultado, Degradado)
    assert resultado.motivo == f"no se pudo combinar o volcar el mapa {codigos}"


# --- mutacion.py:1733 · el aviso de otro HEAD dice el SHA del mapa --------------


def test_f019_r6_el_aviso_de_otro_head_nombra_los_dos_sha() -> None:
    mapa = MapaTests(sha="abc123", orden=("t::a",), contextos={}, segundos=1.0)
    avisos: list[str] = []

    vigentes = mutacion._mapas_vigentes(
        {(".", "py", ""): mapa}, "def456", ".", avisos.append
    )

    motivo = vigentes[(".", "py", "")].motivo  # type: ignore[union-attr]
    assert "(def456)" in motivo and "(abc123)" in motivo
    assert avisos and "abc123" in avisos[0]


# --- mutacion.py:2723 · sin mapa, el tamaño del subconjunto es n/d --------------


def test_f019_r25_sin_mapa_el_tamano_del_subconjunto_es_n_d_aunque_haya_tamanos() -> (
    None
):
    alcance = Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"), lineas={})
    informe = InformeMutacion(
        feature="F-019", alcance=alcance, seleccion="degradada", tamanos_subconjunto=[3]
    )

    assert "| Tamaño medio del subconjunto | n/d |" in filas_de_seleccion(informe)


# --- mutacion.py:3614 · una configuración ilegible deja la selección apagada ----


def test_f019_r19_rigor_ilegible_apaga_la_seleccion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _ilegible(_ruta: object) -> dict:
        raise ValueError("rigor.json no es JSON")

    monkeypatch.setattr(mutacion, "cargar_rigor", _ilegible)

    assert mutacion._seleccion_configurada() is False


# --- Equivalentes: demostración ejecutable (RM5) -------------------------------


def test_f019_rm5_text_false_con_encoding_sigue_siendo_texto() -> None:
    """mapa_tests.py:292: con `encoding`, `text=False` no cambia nada."""
    proceso = subprocess.run(
        [sys.executable, "-c", "print('á')"],
        capture_output=True,
        text=False,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert proceso.stdout.strip() == "á"


def test_f019_rm5_un_coverage_es_siempre_verdadero() -> None:
    """arnes_contextos.py:42: `Coverage` no define `__bool__` ni `__len__`."""
    coverage = pytest.importorskip("coverage")

    assert not hasattr(coverage.Coverage, "__bool__") and not hasattr(
        coverage.Coverage, "__len__"
    )
    assert bool(coverage.Coverage(data_file=None))


def test_f019_rm5_medir_mapas_no_usa_el_ejecutor_por_defecto_si_hay_fabrica() -> None:
    """mutacion_paralela.py:950: con `ejecutor_de`, el `ejecutor` no se lee."""

    class Explota:
        def __getattr__(self, nombre: str) -> object:
            raise AssertionError(f"se leyó {nombre} del ejecutor por defecto")

    medido = SimpleNamespace(
        raiz=".",
        ejecutable="py",
        ruta=None,
        medir_mapa=lambda rutas, t: Degradado("doble"),
    )

    mapas = mutacion.medir_mapas(["pkg/mod.py"], Explota(), lambda _f: medido, ".", 5)

    assert list(mapas.values()) == [Degradado("doble")]


def test_f019_rm5_el_teardown_ya_corre_con_el_nodeid_antes_de_su_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """arnes_contextos.py:83: `tryfirst` en el teardown solo ordena un cambio redundante.

    Tras setup y call el contexto ya es el nodeid, y solo `logfinish` (que
    pytest llama después del teardown entero) lo devuelve a `""`: lo que
    ejecute el teardown de pytest antes o después del hook del plugin se
    atribuye al test igual.
    """
    contextos: list[str] = []
    monkeypatch.setattr(
        arnes_contextos,
        "_coverage",
        lambda: SimpleNamespace(switch_context=contextos.append),
    )
    config = SimpleNamespace(
        rootpath=tmp_path, invocation_params=SimpleNamespace(dir=tmp_path)
    )
    item = SimpleNamespace(nodeid="tests/t.py::a", config=config)

    arnes_contextos.pytest_runtest_setup(item)  # type: ignore[arg-type]
    arnes_contextos.pytest_runtest_call(item)  # type: ignore[arg-type]
    antes_del_teardown = contextos[-1]
    arnes_contextos.pytest_runtest_teardown(item)  # type: ignore[arg-type]

    assert antes_del_teardown == contextos[-1] == "tests/t.py::a"
    assert "" not in contextos, "nada vuelve al contexto vacío antes de logfinish"
