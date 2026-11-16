# tests/test_f019_tiempos.py
"""F-019 · Timeouts bajo carga: `harness.tiempos` y su uso en la suite.

R21: `escalar_timeout` multiplica por `ARNES_FACTOR_TIMEOUT_TESTS` (número ≥ 1;
ausente, no numérico o menor que 1 cuenta como 1) y redondea hacia arriba.
R22: ningún test del payload lanza un subproceso con un timeout literal sin
pasarlo por `escalar_timeout`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness.tiempos import VARIABLE_FACTOR, escalar_timeout, factor_timeout_tests

TESTS = Path(__file__).resolve().parent


# --- R21 ---------------------------------------------------------------------


def test_f019_r21_sin_variable_el_factor_es_uno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE_FACTOR, raising=False)
    assert factor_timeout_tests() == 1
    assert escalar_timeout(120) == 120


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("2", 240), ("3", 360), ("1.5", 180), ("1", 120), ("2.01", 242)],
)
def test_f019_r21_multiplica_y_redondea_hacia_arriba(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: int
) -> None:
    monkeypatch.setenv(VARIABLE_FACTOR, valor)
    assert escalar_timeout(120) == esperado


@pytest.mark.parametrize("valor", ["", "dos", "0", "0.5", "-3", "nan", "inf", "-inf"])
def test_f019_r21_valor_invalido_o_menor_que_uno_cuenta_como_uno(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    monkeypatch.setenv(VARIABLE_FACTOR, valor)
    assert factor_timeout_tests() == 1
    assert escalar_timeout(60) == 60


def test_f019_r21_redondea_hacia_arriba_con_segundos_fraccionarios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(VARIABLE_FACTOR, "1")
    assert escalar_timeout(0.2) == 1
    assert isinstance(escalar_timeout(10), int)


def test_f019_r21_lee_un_entorno_explicito() -> None:
    assert factor_timeout_tests({VARIABLE_FACTOR: "4"}) == 4
    assert factor_timeout_tests({}) == 1


# --- R22 ---------------------------------------------------------------------

# F-074 (R7 de la 1.10.1): el barrido era textual (`timeout\s*=\s*\d`) y
# daba falsos positivos con los valores por defecto de un `def` y con los
# argumentos de los dobles. Ahora es sobre el AST: solo cuenta un `timeout=` con
# literal numérico en una llamada que lanza o espera un subproceso de verdad.

#: Funciones de `subprocess` que lanzan un proceso (también importadas sueltas).
_FUNCIONES_SUBPROCESO = frozenset({"run", "Popen", "check_output", "check_call", "call"})
#: Métodos de un proceso ya lanzado que aceptan `timeout`.
_METODOS_DE_PROCESO = frozenset({"communicate", "wait"})
#: Constante de módulo que fija un timeout.
_CONSTANTE = "TIMEOUT_S"


def _es_literal_numerico(nodo: ast.expr | None) -> bool:
    return (
        isinstance(nodo, ast.Constant)
        and isinstance(nodo.value, (int, float))
        and not isinstance(nodo.value, bool)
    )


def _nombres_de_subprocess(arbol: ast.Module) -> tuple[set[str], set[str]]:
    """Los alias del módulo `subprocess` y las funciones suyas importadas sueltas."""
    modulos: set[str] = set()
    sueltas: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(a.asname or a.name for a in nodo.names if a.name == "subprocess")
        elif isinstance(nodo, ast.ImportFrom) and nodo.module == "subprocess":
            sueltas.update(
                a.asname or a.name for a in nodo.names if a.name in _FUNCIONES_SUBPROCESO
            )
    return modulos, sueltas


def _es_llamada_de_subproceso(llamada: ast.Call, modulos: set[str], sueltas: set[str]) -> bool:
    funcion = llamada.func
    if isinstance(funcion, ast.Name):
        return funcion.id in sueltas
    if isinstance(funcion, ast.Attribute):
        if funcion.attr in _METODOS_DE_PROCESO:
            return True
        return (
            funcion.attr in _FUNCIONES_SUBPROCESO
            and isinstance(funcion.value, ast.Name)
            and funcion.value.id in modulos
        )
    return False


def _ofensas(texto: str) -> list[str]:
    arbol = ast.parse(texto)
    modulos, sueltas = _nombres_de_subprocess(arbol)
    ofensas = [
        f"línea {nodo.lineno}: {ast.unparse(nodo.func)}(timeout={clave.value.value})"
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call) and _es_llamada_de_subproceso(nodo, modulos, sueltas)
        for clave in nodo.keywords
        if clave.arg == "timeout" and _es_literal_numerico(clave.value)
    ]
    for nodo in arbol.body:  # solo el nivel de módulo
        if isinstance(nodo, ast.Assign):
            objetivos, valor = nodo.targets, nodo.value
        elif isinstance(nodo, ast.AnnAssign):
            objetivos, valor = [nodo.target], nodo.value
        else:
            continue
        if _es_literal_numerico(valor) and any(
            isinstance(o, ast.Name) and o.id == _CONSTANTE for o in objetivos
        ):
            ofensas.append(f"línea {nodo.lineno}: {_CONSTANTE} = {valor.value}")
    return ofensas


@pytest.mark.parametrize(
    "codigo",
    [
        "import subprocess\nsubprocess.run(x, timeout=60, check=False)\n",
        "import subprocess\nsubprocess.check_output(x, timeout=1.5)\n",
        "import subprocess\nsubprocess.check_call(x, timeout=5)\n",
        "import subprocess\nsubprocess.call(x, timeout=5)\n",
        "import subprocess as sp\nsp.Popen(x, timeout=5)\n",
        "from subprocess import run\nrun(x, timeout=60)\n",
        "from subprocess import check_output as co\nco(x, timeout=60)\n",
        "proceso.communicate(timeout=30)\n",
        "proceso.wait(timeout=30)\n",
        "TIMEOUT_S = 240\n",
        "TIMEOUT_S: int = 240\n",
    ],
)
def test_f019_r22_el_barrido_detecta_un_literal(codigo: str) -> None:
    """Control del barrido: sin esto, un patrón roto daría un verde vacío."""
    assert _ofensas(codigo), codigo


@pytest.mark.parametrize(
    "codigo",
    [
        "import subprocess\nsubprocess.run(x, timeout=escalar_timeout(60))\n",
        "TIMEOUT_S = escalar_timeout(240)\n",
        # Valor por defecto de una función: lo que comprueban sus propios asserts.
        "def _comprobar(x, timeout=30):\n    return x\n",
        "def _comprobar(x, *, timeout: int = 30) -> int:\n    return x\n",
        # Argumentos a dobles o a funciones que no son de subprocess.
        "doble(timeout=30)\n",
        "doble.ejecutar(x, timeout=30)\n",
        "requests.get(url, timeout=10)\n",
        # `run` sin importar de subprocess es otra función.
        "run(x, timeout=60)\n",
        "otro.run(x, timeout=60)\n",
        # La constante dentro de una función no es de módulo.
        "def f():\n    TIMEOUT_S = 240\n",
        "import subprocess\nsubprocess.run(x, timeout=None)\n",
    ],
)
def test_f019_r22_el_barrido_no_marca_lo_que_no_es_un_subproceso(codigo: str) -> None:
    """Control negativo (F-074): los falsos positivos que vio datamart, en verde."""
    assert not _ofensas(codigo), (codigo, _ofensas(codigo))


def test_f019_r22_ningun_test_lanza_subprocesos_con_timeout_literal() -> None:
    ofensores = {
        fichero.name: _ofensas(fichero.read_text(encoding="utf-8"))
        for fichero in sorted(TESTS.glob("test_*.py"))
        if fichero.name != Path(__file__).name
    }
    ofensores = {nombre: lista for nombre, lista in ofensores.items() if lista}
    assert not ofensores, (
        "timeouts fijos sin escalar_timeout (R22 de F-019): bajo una campaña con "
        f"W workers cada suite avanza hasta W veces más despacio: {ofensores}"
    )


# --- R20 ---------------------------------------------------------------------

from harness.alcance import Alcance
from harness.mutacion import (
    FACTOR_HOLGURA_BASE,
    MUERTO,
    InformeMutacion,
    ResultadoSuite,
    ejecutar_campania,
    timeout_de_linea_base,
)


@pytest.mark.parametrize(
    ("suelo", "workers", "esperado"),
    [(120, 1, 600), (120, 2, 1200), (120, 6, 3600), (120, 0, 600), (30, 3, 450)],
)
def test_f019_r20_base_y_mapa_con_suelo_por_holgura_por_workers(
    suelo: int, workers: int, esperado: int
) -> None:
    assert timeout_de_linea_base(suelo, workers) == esperado
    assert esperado == suelo * FACTOR_HOLGURA_BASE * max(1, workers)


def test_f019_r20_sin_workers_es_el_de_siempre() -> None:
    assert timeout_de_linea_base(120) == 600


class _DobleBase:
    """Doble que apunta con qué timeout se le pidió la línea base."""

    def __init__(self) -> None:
        self.raiz = "doble"
        self.timeouts_de_base: list[int] = []

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        self.timeouts_de_base.append(timeout_s)
        return ResultadoSuite(codigo=0)

    def ejecutar(self, timeout_s: int) -> str:
        return MUERTO


def test_f019_r20_la_campania_da_a_la_base_el_reloj_con_workers(tmp_path: Path) -> None:
    (tmp_path / "codigo.py").write_text("def f(a):\n    return a + 1\n", encoding="utf-8")
    alcance = Alcance(
        feature="F-019", origen="rama", ref_diff=("dev", "x"), lineas={"codigo.py": {2}}
    )
    doble = _DobleBase()

    ejecutar_campania(
        alcance, doble, timeout_s=10, raiz=str(tmp_path), comprobar_arbol=False, workers=3
    )

    assert doble.timeouts_de_base, "la campaña no corrió la línea base"
    assert set(doble.timeouts_de_base) == {10 * FACTOR_HOLGURA_BASE * 3}


def test_f019_r20_el_cli_calcula_la_base_con_los_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recibidos: list[dict] = []
    alcance = Alcance(
        feature="F-019", origen="rama", ref_diff=("dev", "x"),
        lineas={"harness/mutacion.py": {1}},
    )

    def _campania(alc: Alcance, *_a: object, **kwargs: object) -> InformeMutacion:
        recibidos.append(dict(kwargs))
        return InformeMutacion(feature=alc.feature, alcance=alc, generados=1)

    monkeypatch.setattr("harness.mutacion.alcance_de_feature", lambda *_a, **_k: alcance)
    monkeypatch.setattr(
        "harness.mutacion_paralela.ejecutar_campania_paralela", _campania
    )
    from harness.mutacion import main

    main(["--feature", "F-019", "--workers", "3", "--salida", str(tmp_path / "informe.md")])

    suelo = recibidos[0]["timeout_s"]
    assert recibidos[0]["timeout_base_s"] == suelo * FACTOR_HOLGURA_BASE * 3
    assert f"dispone de {suelo * FACTOR_HOLGURA_BASE * 3} s" in capsys.readouterr().out


# --- R23 ---------------------------------------------------------------------

from harness import mutacion
from harness.mutacion import EjecutorPytest, fijar_factor_tests


@pytest.fixture
def factor_limpio() -> object:
    fijar_factor_tests(None)
    yield
    fijar_factor_tests(None)


def test_f019_r23_el_entorno_lleva_el_factor_de_la_campania(
    monkeypatch: pytest.MonkeyPatch, factor_limpio: object, tmp_path: Path
) -> None:
    monkeypatch.delenv(VARIABLE_FACTOR, raising=False)
    fijar_factor_tests(3)

    entorno = EjecutorPytest(raiz=str(tmp_path)).entorno()

    assert entorno[VARIABLE_FACTOR] == "3"
    assert entorno["PYTHONDONTWRITEBYTECODE"] == "1"
    assert entorno["PYTHONPYCACHEPREFIX"]


def test_f019_r23_manda_el_del_entorno_si_ya_lo_trae(
    monkeypatch: pytest.MonkeyPatch, factor_limpio: object, tmp_path: Path
) -> None:
    monkeypatch.setenv(VARIABLE_FACTOR, "7")
    fijar_factor_tests(2)

    assert EjecutorPytest(raiz=str(tmp_path)).entorno()[VARIABLE_FACTOR] == "7"


def test_f019_r23_fuera_de_una_campania_no_se_inventa_el_factor(
    monkeypatch: pytest.MonkeyPatch, factor_limpio: object, tmp_path: Path
) -> None:
    monkeypatch.delenv(VARIABLE_FACTOR, raising=False)

    assert VARIABLE_FACTOR not in EjecutorPytest(raiz=str(tmp_path)).entorno()


def test_f019_r23_correr_lanza_la_suite_con_ese_entorno(
    monkeypatch: pytest.MonkeyPatch, factor_limpio: object, tmp_path: Path
) -> None:
    monkeypatch.delenv(VARIABLE_FACTOR, raising=False)
    vistos: list[dict] = []

    class _Proceso:
        returncode = 0
        stdout = b""
        stderr = b""

    def _run(*_a: object, **kwargs: object) -> _Proceso:
        vistos.append(dict(kwargs["env"]))  # type: ignore[arg-type]
        return _Proceso()

    monkeypatch.setattr("harness.mutacion.subprocess.run", _run)
    fijar_factor_tests(2)
    ejecutor = EjecutorPytest(raiz=str(tmp_path))

    ejecutor.correr(10)
    ejecutor.linea_base(10)

    assert [v[VARIABLE_FACTOR] for v in vistos] == ["2", "2"]


def test_f019_r23_el_cli_fija_el_factor_con_los_workers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, factor_limpio: object
) -> None:
    vistos: list[int | None] = []
    alcance = Alcance(
        feature="F-019", origen="rama", ref_diff=("dev", "x"),
        lineas={"harness/mutacion.py": {1}},
    )

    def _campania(alc: Alcance, *_a: object, **_k: object) -> InformeMutacion:
        vistos.append(mutacion._FACTOR_TESTS)
        return InformeMutacion(feature=alc.feature, alcance=alc, generados=1)

    monkeypatch.setattr("harness.mutacion.alcance_de_feature", lambda *_a, **_k: alcance)
    monkeypatch.setattr("harness.mutacion_paralela.ejecutar_campania_paralela", _campania)
    monkeypatch.setattr("harness.mutacion.ejecutar_campania", _campania)

    mutacion.main(["--feature", "F-019", "--workers", "2",
                   "--salida", str(tmp_path / "a.md")])
    mutacion.main(["--feature", "F-019", "--workers", "1",
                   "--salida", str(tmp_path / "b.md")])

    assert vistos == [2, 1]
    assert mutacion._FACTOR_TESTS is None, "main deja el factor como estaba al salir"
