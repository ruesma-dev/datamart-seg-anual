# tests/test_f019_prueba_de_verdad.py
"""F-019 · R30: la prueba de verdad de la selección de tests.

Un repositorio git de juguete con su suite REAL —pytest, coverage y git de
verdad— y la MISMA campaña dos veces, con selección y sin ella, mismo alcance
y sin muestreo: el veredicto de cada mutante tiene que coincidir. La campaña
con selección, además, tiene que podar, revalidar y descartar un subconjunto.
Y lo mismo en paralelo con dos workers.

Los seis casos de la spec, uno por función de `pkg/mod.py`:

1. `con_test`: línea que ejecuta un test en el proceso → subconjunto que mata.
2. `solo_subproceso`: solo la ejecuta un subproceso → contexto vacío → suite.
3. `nunca`: no la ejecuta nadie → PODADO, superviviente sin correr nada.
4. `plegado`: constante plegada de una tupla multilínea (sin evento de línea)
   → por SENTENCIA tiene test → subconjunto que mata, nunca podado.
5. `copiado`: solo la ejecuta una COPIA del fichero en un temporal → suite.
6. `depende`: su test depende de otro → el subconjunto sale rojo SIN mutar →
   descartado → suite.

Y dos para la revalidación: `sin_asercion` (el subconjunto no mata, la suite
tampoco: superviviente medido) y `mixto` (el subconjunto no mata y la suite
sí, por un subproceso: muere al revalidar).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.alcance import Alcance
from harness.mutacion import (
    BASE_ROTA,
    INDETERMINADO,
    MUERTO,
    SUPERVIVIENTE,
    TIMEOUT,
    EjecutorPytest,
    InformeMutacion,
    _leer,
    clave_de_orden,
    ejecutar_campania,
)
from harness.mutacion_paralela import ejecutar_campania_paralela
from harness.tiempos import escalar_timeout

pytest.importorskip("coverage", reason="la selección de tests necesita coverage")

#: Suelo por mutante; el efectivo se deriva de la línea base de juguete.
TIMEOUT_S = escalar_timeout(240)

MOD = """\
ESTADO = {}


def con_test(x):
    return x + 1  # alcance


def solo_subproceso(x):
    return x * 2  # alcance


def nunca(x):
    return x - 3  # alcance


def plegado():
    valores = (1,
               2,  # alcance
               3)
    return sum(valores)


def copiado(x):
    return x // 4  # alcance


def poner(valor):
    ESTADO["x"] = valor


def depende():
    return ESTADO["x"] + 10  # alcance


def sin_asercion(x):
    return x + 100  # alcance


def mixto(x):
    return x - 7  # alcance
"""

TESTS = """\
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from pkg import mod

RAIZ = Path(__file__).resolve().parents[1]


def test_con_test():
    assert mod.con_test(1) == 2


def test_subproceso():
    subprocess.run(
        [sys.executable, "-c",
         "from pkg import mod; assert mod.solo_subproceso(3) == 6; "
         "assert mod.mixto(10) == 3"],
        cwd=RAIZ, check=True,
    )


def test_plegado():
    assert mod.plegado() == 6


def test_copia(tmp_path):
    destino = tmp_path / "copia" / "pkg"
    shutil.copytree(RAIZ / "pkg", destino)
    spec = importlib.util.spec_from_file_location("copia_mod", destino / "mod.py")
    copia = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copia)
    assert copia.copiado(8) == 2


def test_poner():
    mod.poner(5)


def test_depende():
    assert mod.depende() == 15


def test_sin_asercion():
    mod.sin_asercion(1)


def test_mixto_sin_asercion():
    mod.mixto(1)
"""

LINEAS = {n for n, linea in enumerate(MOD.splitlines(), start=1) if "# alcance" in linea}
LINEA_NUNCA = next(n for n, l in enumerate(MOD.splitlines(), 1) if "x - 3" in l)
LINEA_PLEGADA = next(n for n, l in enumerate(MOD.splitlines(), 1) if l.strip() == "2,  # alcance")


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(raiz), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _repositorio(destino: Path) -> Path:
    (destino / "pkg").mkdir(parents=True)
    (destino / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (destino / "pkg" / "mod.py").write_text(MOD, encoding="utf-8", newline="")
    (destino / "tests").mkdir()
    (destino / "tests" / "test_mod.py").write_text(TESTS, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "dev", str(destino)], check=True,
                   capture_output=True)
    _git(destino, "config", "user.email", "arnes@ruesma.es")
    _git(destino, "config", "user.name", "Arnes")
    _git(destino, "add", "-A")
    _git(destino, "commit", "-q", "-m", "inicial")
    return destino


def _alcance() -> Alcance:
    return Alcance(feature="F-019", origen="rama", ref_diff=("dev", "x"),
                   lineas={"pkg/mod.py": set(LINEAS)})


def _veredictos(informe: InformeMutacion) -> dict[tuple, str]:
    otros: dict[tuple, str] = {}
    for veredicto, lista in ((SUPERVIVIENTE, informe.supervivientes),
                             (TIMEOUT, informe.timeouts),
                             (INDETERMINADO, informe.indeterminados),
                             (BASE_ROTA, informe.base_rota)):
        otros.update({clave_de_orden(m): veredicto for m in lista})
    return {
        clave_de_orden(m): otros.get(clave_de_orden(m), MUERTO)
        for m in informe.mutantes_evaluados
    }


def _serie(raiz: Path, seleccion: bool) -> InformeMutacion:
    return ejecutar_campania(
        _alcance(), EjecutorPytest(raiz=str(raiz), ruta="tests"),
        timeout_s=TIMEOUT_S, raiz=str(raiz), seleccion=seleccion,
    )


@pytest.fixture(scope="module")
def campanias(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    raiz = _repositorio(tmp_path_factory.mktemp("f019_verdad") / "repo")
    resultado: dict[str, object] = {"raiz": raiz}
    resultado["sin"] = _serie(raiz, seleccion=False)
    resultado["con"] = _serie(raiz, seleccion=True)
    resultado["paralela"] = ejecutar_campania_paralela(
        _alcance(), [], timeout_s=TIMEOUT_S, raiz=str(raiz), workers=2, seleccion=True,
    )
    return resultado


def test_f019_r30_el_juguete_tiene_los_seis_casos(campanias) -> None:
    sin = campanias["sin"]
    assert sin.seleccion == "desactivada"
    assert sin.evaluados >= 14
    assert not sin.indeterminados and not sin.base_rota and not sin.timeouts
    vistos = _veredictos(sin)
    assert {v for k, v in vistos.items() if k[1] == LINEA_NUNCA} == {SUPERVIVIENTE}
    assert {v for k, v in vistos.items() if k[1] == LINEA_PLEGADA} == {MUERTO}


def test_f019_r30_con_y_sin_seleccion_mismo_veredicto_por_mutante(campanias) -> None:
    sin, con = campanias["sin"], campanias["con"]

    assert con.seleccion == "activa", con.motivos_degradado
    assert [clave_de_orden(m) for m in con.mutantes_evaluados] == [
        clave_de_orden(m) for m in sin.mutantes_evaluados
    ], "mismo alcance, mismos mutantes"
    assert _veredictos(con) == _veredictos(sin)


def test_f019_r30_la_seleccion_poda_revalida_y_descarta(campanias) -> None:
    con = campanias["con"]

    assert con.podados, "ningún mutante podado"
    assert {m.linea for m in con.podados} == {LINEA_NUNCA}, "solo se poda lo que nadie ejecuta"
    assert con.revalidados >= 1
    assert con.muertos_al_revalidar >= 1, "el de `mixto` muere al revalidar"
    assert con.subconjuntos_descartados >= 1, "el de `depende` no sale verde sin mutar"
    assert con.tamanos_subconjunto, "ningún mutante se juzgó con subconjunto"
    assert con.juzgados_suite_entera < campanias["sin"].juzgados_suite_entera


def test_f019_r30_la_constante_plegada_no_se_poda(campanias) -> None:
    con = campanias["con"]

    assert not [m for m in con.podados if m.linea == LINEA_PLEGADA]


def test_f019_r30_en_paralelo_con_dos_workers_tambien(campanias) -> None:
    paralela, sin = campanias["paralela"], campanias["sin"]

    assert paralela.workers == 2
    assert paralela.seleccion == "activa", paralela.motivos_degradado
    assert _veredictos(paralela) == _veredictos(sin)
    assert {m.linea for m in paralela.podados} == {LINEA_NUNCA}


def test_f019_r30_el_arbol_queda_como_estaba(campanias) -> None:
    raiz = campanias["raiz"]

    assert _leer(raiz / "pkg" / "mod.py") == MOD
    assert _git(raiz, "status", "--porcelain") == ""
