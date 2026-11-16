# harness/pytest_arnes/arnes_contextos.py
"""Plugin de pytest del arnés: atribuye a cada test las líneas que ejecuta (F-019).

Se carga con `-p arnes_contextos` y el directorio de este fichero antepuesto a
`PYTHONPATH`; por eso vive fuera del paquete `harness` y sin `__init__.py`: el
venv de un servicio no ve `harness`, pero sí este directorio.

Bajo `coverage run`, cambia el contexto dinámico de coverage al nodeid del
test durante su setup, su llamada y su teardown, y lo vuelve a `""` al
terminar: lo que se ejecuta fuera de un test (recolección, importación) queda
sin test atribuible. El nodeid va RELATIVO al directorio desde el que se lanzó
pytest, para poder pasarlo tal cual en la orden de un subconjunto.

`dynamic_context = test_function` de coverage no sirve: da nombres sin ruta ni
parámetros (`test_x.TestClase.test_d`), que no se pueden seleccionar.

Sin coverage activo no hace nada. Solo biblioteca estándar y pytest.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

#: Variable con la ruta donde se escribe el orden de recolección (JSON).
VARIABLE_ORDEN = "ARNES_CONTEXTOS_ORDEN"


def _coverage() -> object | None:
    try:
        import coverage
    except ImportError:
        return None
    return coverage.Coverage.current()


def _cambiar(contexto: str) -> None:
    actual = _coverage()
    if actual is not None:
        actual.switch_context(contexto)  # type: ignore[attr-defined]


def relativo(nodeid: str, raiz: Path, invocacion: Path) -> str:
    """El nodeid de pytest (relativo a `rootdir`) relativo a `invocacion`."""
    if Path(raiz).resolve() == Path(invocacion).resolve():
        return nodeid
    fichero, separador, resto = nodeid.partition("::")
    ruta = os.path.relpath(Path(raiz) / fichero, invocacion).replace(os.sep, "/")
    return f"{ruta}{separador}{resto}"


def _de(item: pytest.Item) -> str:
    return relativo(item.nodeid, item.config.rootpath, item.config.invocation_params.dir)


#: Dónde escribe ESTE proceso el orden; se lee una vez, en `pytest_configure`.
_destino: str | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Se queda la variable del orden y la QUITA del entorno.

    Una suite que lanza pytest dentro de sus tests (la del propio arnés lo
    hace) heredaría la variable, y el pytest anidado sobrescribiría el orden de
    la suite medida con el suyo: ningún nodeid real estaría en el orden y todo
    mutante iría a la suite entera (hallazgo de T15 de F-019).
    """
    global _destino
    _destino = os.environ.pop(VARIABLE_ORDEN, None)


def pytest_collection_finish(session: pytest.Session) -> None:
    destino = _destino
    if not destino:
        return
    orden = [_de(item) for item in session.items]
    Path(destino).write_text(json.dumps(orden, ensure_ascii=False), encoding="utf-8")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    _cambiar(_de(item))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    _cambiar(_de(item))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    _cambiar(_de(item))


def pytest_runtest_logfinish(nodeid: str, location: object) -> None:
    _cambiar("")
