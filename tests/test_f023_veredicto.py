# tests/test_f023_veredicto.py
"""F-023 · Un solo criterio de muerte: código 1 de pytest (R1–R13, R21, R22).

Hasta F-023 morían también el mutante que no compila y el que revienta la
recolección con la base verde, y sobrevivía el que deja la suite sin tests
(código 5). Aquí, con dobles de test y sin lanzar ningún pytest, se fija el
criterio nuevo: muere solo lo que un test caza; lo demás es `indeterminado`,
con su código de salida en el informe.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import mutacion
from harness.alcance import Alcance
from harness.mutacion import (
    INDETERMINADO,
    MUERTO,
    PYTEST_FALLOS,
    PYTEST_OK,
    PYTEST_SIN_TESTS,
    SUPERVIVIENTE,
    TIMEOUT,
    EjecutorPytest,
    InformeMutacion,
    Mutante,
    ResultadoSuite,
    _leer,
    ejecutar_campania,
)

FUENTE = "# app.py\ndef bandera():\n    return True\n"

#: Mutante válido de la línea 3: `True` → `False`.
VALIDO = Mutante("app.py", 3, 11, "return True", "return False", "booleano", 4, "False")

#: Mutante que deja un paréntesis desparejado, como el de datamart F-148.
ROTO = Mutante("app.py", 3, 11, "return True", "return (", "booleano", 4, "(")


class Juez:
    """Doble con `juzgar`: devuelve `(veredicto, código)` del guion."""

    def __init__(self, juicios: list[tuple[str, str]], bases: list[ResultadoSuite] | None = None,
                 raiz: str = ".") -> None:
        self.raiz = raiz
        self._juicios = list(juicios)
        self._bases = list(bases or [])
        self.juzgados = 0

    def identidad(self) -> tuple[str, str]:
        return (self.raiz, "juez")

    def juzgar(self, timeout_s: int) -> tuple[str, str]:
        self.juzgados += 1
        return self._juicios.pop(0)

    def ejecutar(self, timeout_s: int) -> str:
        return self.juzgar(timeout_s)[0]

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        if self._bases:
            return self._bases.pop(0)
        return ResultadoSuite(codigo=PYTEST_OK)


class SoloEjecutar:
    """Doble a la antigua (R10): sin `juzgar`, como las subclases de proyecto."""

    def __init__(self, veredictos: list[str], raiz: str = ".") -> None:
        self.raiz = raiz
        self._veredictos = list(veredictos)

    def identidad(self) -> tuple[str, str]:
        return (self.raiz, "antiguo")

    def ejecutar(self, timeout_s: int) -> str:
        return self._veredictos.pop(0)

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        return ResultadoSuite(codigo=PYTEST_OK)


@pytest.fixture
def arbol(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "dev", str(tmp_path)], check=True)
    for clave, valor in (("user.email", "arnes@ruesma.es"), ("user.name", "Arnes")):
        subprocess.run(["git", "-C", str(tmp_path), "config", clave, valor], check=True)
    (tmp_path / "app.py").write_text(FUENTE, encoding="utf-8", newline="")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "inicial"], check=True)
    return tmp_path


def _alcance() -> Alcance:
    return Alcance(feature="F-999", origen="rama", ref_diff=("dev", "feature/F-999-x"),
                   lineas={"app.py": {3}})


def _campania(arbol: Path, ejecutor: object, mutantes: list[Mutante] | None = None,
              eco: list[str] | None = None) -> InformeMutacion:
    return ejecutar_campania(
        _alcance(), ejecutor, raiz=str(arbol), mutantes=mutantes or [VALIDO],
        eco=eco.append if eco is not None else None,
    )


# --- R1 · el ejecutor real: código → (veredicto, código) --------------------


def test_f023_r1_juzgar_traduce_cada_codigo_con_su_hecho() -> None:
    ejecutor = EjecutorPytest()
    esperados = {
        PYTEST_OK: (SUPERVIVIENTE, "0"),
        PYTEST_FALLOS: (MUERTO, "1"),
        2: (INDETERMINADO, "2"),
        3: (INDETERMINADO, "3"),
        4: (INDETERMINADO, "4"),
        PYTEST_SIN_TESTS: (INDETERMINADO, "5"),
    }
    for codigo, esperado in esperados.items():
        ejecutor.correr = lambda _t, _a=None, _c=codigo: ResultadoSuite(codigo=_c)  # type: ignore[method-assign]
        assert ejecutor.juzgar(1) == esperado, f"código {codigo}"
        assert ejecutor.ejecutar(1) == esperado[0], f"código {codigo}"

    ejecutor.correr = lambda _t, _a=None: ResultadoSuite(codigo=-1, expirado=True)  # type: ignore[method-assign]
    assert ejecutor.juzgar(1) == (TIMEOUT, mutacion.CODIGO_TIMEOUT)


def test_f023_r1_verde_es_solo_el_codigo_0_y_la_base_admite_el_5() -> None:
    assert ResultadoSuite(codigo=PYTEST_OK).verde
    assert not ResultadoSuite(codigo=PYTEST_SIN_TESTS).verde
    assert ResultadoSuite(codigo=PYTEST_SIN_TESTS).base_utilizable
    assert ResultadoSuite(codigo=PYTEST_OK).base_utilizable
    assert not ResultadoSuite(codigo=PYTEST_FALLOS).base_utilizable
    assert not ResultadoSuite(codigo=-1, expirado=True).base_utilizable


# --- R1–R4 · la campaña con un solo criterio --------------------------------


def test_f023_r1_criterio_solo_el_codigo_1_mata(arbol: Path) -> None:
    informe = _campania(arbol, Juez([(MUERTO, "1")]))

    assert informe.muertos == 1
    assert informe.indeterminados == []


def test_f023_r2_criterio_codigo_5_es_indeterminado(arbol: Path) -> None:
    informe = _campania(arbol, Juez([(INDETERMINADO, "5")]))

    assert informe.supervivientes == []
    assert informe.muertos == 0
    assert informe.indeterminados == [VALIDO]
    assert informe.codigos[mutacion.clave_de_orden(VALIDO)] == "5"


@pytest.mark.parametrize("codigo", ["2", "3", "4"])
@pytest.mark.parametrize("base", [PYTEST_OK, PYTEST_SIN_TESTS])
def test_f023_r3_criterio_codigo_2_a_4_con_base_utilizable_es_indeterminado(
    arbol: Path, codigo: str, base: int
) -> None:
    bases = [ResultadoSuite(codigo=PYTEST_OK)] + [ResultadoSuite(codigo=base)] * 2
    informe = _campania(arbol, Juez([(INDETERMINADO, codigo)], bases=bases))

    assert informe.muertos == 0, "un error de recolección ya no es una muerte"
    assert informe.indeterminados == [VALIDO]
    assert informe.base_rota == []
    assert informe.codigos[mutacion.clave_de_orden(VALIDO)] == codigo
    assert informe.fiable


def test_f023_r4_criterio_codigo_2_con_base_rota_sigue_siendo_base_rota(arbol: Path) -> None:
    bases = [ResultadoSuite(codigo=PYTEST_OK), ResultadoSuite(codigo=PYTEST_FALLOS),
             ResultadoSuite(codigo=PYTEST_OK)]
    informe = _campania(arbol, Juez([(INDETERMINADO, "2")], bases=bases))

    assert informe.base_rota == [VALIDO]
    assert informe.indeterminados == []
    assert informe.muertos == 0
    assert informe.codigos[mutacion.clave_de_orden(VALIDO)] == "2"
    assert not informe.fiable


# --- R5 · el mutante que no compila -----------------------------------------


def test_f023_r5_compila_no_compila_es_indeterminado_sin_tocar_disco(
    arbol: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    escrituras: list[str] = []
    original = mutacion._escribir

    def espia(ruta: Path, texto: str):
        escrituras.append(texto)
        return original(ruta, texto)

    monkeypatch.setattr(mutacion, "_escribir", espia)
    juez = Juez([])
    eco: list[str] = []

    informe = _campania(arbol, juez, mutantes=[ROTO], eco=eco)

    assert juez.juzgados == 0, "no se lanza la suite de un mutante que no compila"
    assert all("return (" not in texto for texto in escrituras), "no se escribe en disco"
    assert informe.muertos == 0
    assert informe.indeterminados == [ROTO]
    assert informe.codigos[mutacion.clave_de_orden(ROTO)] == mutacion.NO_COMPILA
    assert any("indeterminado" in linea and "(no compila)" in linea for linea in eco), eco
    assert _leer(arbol / "app.py") == FUENTE


def test_f023_r5_compila_helper() -> None:
    assert mutacion.compila(FUENTE, "app.py")
    assert not mutacion.compila(FUENTE.replace("True", "("), "app.py")


# --- R6, R7 · base sin tests y fiabilidad ------------------------------------


def test_f023_r6_criterio_base_sin_tests_no_aborta(arbol: Path) -> None:
    bases = [ResultadoSuite(codigo=PYTEST_SIN_TESTS)] * 3
    informe = _campania(arbol, Juez([(INDETERMINADO, "5")], bases=bases))

    assert informe.indeterminados == [VALIDO]
    assert informe.fiable


def test_f023_r7_criterio_indeterminados_no_invalidan_ni_cuentan(
    arbol: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    informe = InformeMutacion(feature="F-999", alcance=_alcance(), generados=1,
                              mutantes_evaluados=[VALIDO])
    informe.indeterminados = [VALIDO]
    assert informe.fiable

    monkeypatch.setattr(mutacion, "alcance_de_feature", lambda *a, **k: _alcance())
    monkeypatch.setattr(mutacion, "ejecutar_campania", lambda *a, **k: informe)
    salida = tmp_path / "progress" / "mutacion_F-999.md"

    codigo = mutacion.main(["--feature", "F-999", "--raiz", str(arbol), "--workers", "1",
                            "--salida", str(salida)], ejecutor=Juez([]))

    assert codigo == 0, "un indeterminado no es un superviviente"


# --- R10 · ejecutores sin `juzgar` -------------------------------------------


def test_f023_r10_codigo_nd_con_un_ejecutor_que_solo_ejecuta(arbol: Path) -> None:
    informe = _campania(arbol, SoloEjecutar([SUPERVIVIENTE]))

    assert informe.supervivientes == [VALIDO]
    assert informe.codigos[mutacion.clave_de_orden(VALIDO)] == mutacion.CODIGO_ND


def test_f023_r10_codigo_nd_y_el_indeterminado_antiguo_se_resuelve_igual(arbol: Path) -> None:
    informe = _campania(arbol, SoloEjecutar([INDETERMINADO]))

    assert informe.muertos == 0
    assert informe.indeterminados == [VALIDO]
    assert informe.codigos[mutacion.clave_de_orden(VALIDO)] == mutacion.CODIGO_ND


# --- R8, R9 · el código de salida, en el informe ----------------------------

#: Más mutantes de la misma línea, con claves distintas, para la tabla.
OTRO = Mutante("app.py", 3, 11, "return True", "return 1", "otro", 4, "1")
ROTO_2 = Mutante("app.py", 3, 4, "return True", "ret(urn True", "roto", 0, "(")


def _informe_con_no_muertos(arbol: Path, eco: list[str] | None = None) -> InformeMutacion:
    juez = Juez([(SUPERVIVIENTE, "0"), (TIMEOUT, mutacion.CODIGO_TIMEOUT), (MUERTO, "1")])
    muerto = Mutante("app.py", 3, 11, "return True", "return 0", "zcero", 4, "0")
    return _campania(arbol, juez, mutantes=[ROTO_2, VALIDO, OTRO, muerto], eco=eco)


def test_f023_r8_codigos_de_cada_no_muerto(arbol: Path) -> None:
    eco: list[str] = []
    informe = _informe_con_no_muertos(arbol, eco)

    assert informe.codigos == {
        mutacion.clave_de_orden(ROTO_2): mutacion.NO_COMPILA,
        mutacion.clave_de_orden(VALIDO): "0",
        mutacion.clave_de_orden(OTRO): mutacion.CODIGO_TIMEOUT,
    }, "solo los no muertos llevan código"
    assert any("superviviente" in linea and "(código 0)" in linea for linea in eco), eco
    assert any("timeout" in linea and "(código timeout)" in linea for linea in eco), eco
    assert not any("muerto " in linea and "código" in linea for linea in eco), eco


def test_f023_r9_informe_fila_indeterminados_y_tabla_de_codigos(
    arbol: Path, tmp_path: Path
) -> None:
    informe = _informe_con_no_muertos(arbol)
    ruta = tmp_path / "mutacion_F-999.md"

    mutacion.escribir_informe(informe, ruta)

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    timeouts = lineas.index("| Timeouts | 1 |")
    assert lineas[timeouts + 1] == "| Indeterminados | 1 |", "la fila va tras «Timeouts»"
    titulo = lineas.index("## No muertos: código de salida")
    assert titulo > lineas.index("## Supervivientes"), "la tabla va tras las fichas"
    tabla = lineas[titulo + 2: titulo + 7]
    assert tabla == [
        "| Fichero:línea | Operador | Veredicto | Código |",
        "|---|---|---|---|",
        "| `app.py:3` | roto | indeterminado | no compila |",
        "| `app.py:3` | booleano | superviviente | 0 |",
        "| `app.py:3` | otro | timeout | timeout |",
    ]


def test_f023_r9_informe_sin_no_muertos_no_trae_la_tabla(arbol: Path, tmp_path: Path) -> None:
    informe = _campania(arbol, Juez([(MUERTO, "1")]))
    ruta = tmp_path / "mutacion_F-999.md"

    mutacion.escribir_informe(informe, ruta)

    texto = ruta.read_text(encoding="utf-8")
    assert "| Indeterminados | 0 |" in texto
    assert "## No muertos: código de salida" not in texto


# --- R11 · el estado de campaña ---------------------------------------------


def _informe_juzgado() -> InformeMutacion:
    muerto = Mutante("app.py", 3, 11, "return True", "return 0", "zcero", 4, "0")
    return InformeMutacion(
        feature="F-999", alcance=_alcance(), generados=4, sha_head="abc",
        mutantes_evaluados=[ROTO_2, VALIDO, OTRO, muerto], muertos=1,
        supervivientes=[VALIDO], timeouts=[OTRO], indeterminados=[ROTO_2],
    )


def test_f023_r11_estado_registra_indeterminados_version_1_y_criterio(tmp_path: Path) -> None:
    ruta = tmp_path / "mutacion_F-999.json"

    assert mutacion.escribir_estado(_informe_juzgado(), ruta)

    estado = mutacion.leer_estado(ruta)
    assert estado["version"] == 1
    assert estado["criterio"] == "codigo_1" == mutacion.CRITERIO_ESTADO
    veredictos = {(e["col"], e["operador"]): e["veredicto"] for e in estado["evaluados"]}
    assert veredictos == {(4, "roto"): INDETERMINADO, (11, "booleano"): SUPERVIVIENTE,
                          (11, "otro"): TIMEOUT, (11, "zcero"): MUERTO}


def test_f023_r11_estado_incremental_reevalua_los_indeterminados(tmp_path: Path) -> None:
    informe = _informe_juzgado()
    ruta = tmp_path / "mutacion_F-999.json"
    mutacion.escribir_estado(informe, ruta)

    plan = mutacion.plan_incremental(mutacion.leer_estado(ruta), None, None, None,
                                     list(informe.mutantes_evaluados), (0.1, 1))

    assert not isinstance(plan, str), plan
    assert ROTO_2 in plan.reevaluar
    assert {VALIDO, OTRO} <= set(plan.reevaluar)


# --- R13 · la paralela fusiona lo nuevo -------------------------------------


def test_f023_r13_fusion_junta_indeterminados_codigos_y_pyc(arbol: Path) -> None:
    from harness.mutacion_paralela import fusionar

    uno = InformeMutacion(feature="F-999", alcance=_alcance(), indeterminados=[VALIDO],
                          codigos={mutacion.clave_de_orden(VALIDO): "5"},
                          pyc_no_borrados=["a.pyc: x"])
    otro = InformeMutacion(feature="F-999", alcance=_alcance(), indeterminados=[ROTO_2],
                           codigos={mutacion.clave_de_orden(ROTO_2): mutacion.NO_COMPILA},
                           pyc_no_borrados=["b.pyc: y"])

    junto = fusionar(_alcance(), [uno, otro], generados=2, segundos=1.0)

    assert junto.indeterminados == [ROTO_2, VALIDO], "en el orden de la serie"
    assert junto.codigos == {**uno.codigos, **otro.codigos}
    assert sorted(junto.pyc_no_borrados) == ["a.pyc: x", "b.pyc: y"]


def test_f023_r13_repaso_trae_indeterminados_codigos_y_base_rota() -> None:
    from harness.mutacion_paralela import reemplazar_timeouts

    muerto = Mutante("app.py", 3, 11, "return True", "return 0", "zcero", 4, "0")
    campania = InformeMutacion(
        feature="F-999", alcance=_alcance(), mutantes_evaluados=[VALIDO, OTRO, muerto],
        timeouts=[VALIDO, OTRO, muerto],
        codigos={mutacion.clave_de_orden(m): mutacion.CODIGO_TIMEOUT
                 for m in (VALIDO, OTRO, muerto)},
    )
    repaso = InformeMutacion(
        feature="F-999", alcance=_alcance(), mutantes_evaluados=[VALIDO, OTRO, muerto],
        indeterminados=[OTRO], base_rota=[VALIDO], muertos=1,
        codigos={mutacion.clave_de_orden(OTRO): "2", mutacion.clave_de_orden(VALIDO): "3"},
        pyc_no_borrados=["c.pyc: z"],
    )

    corregido = reemplazar_timeouts(campania, repaso)

    assert corregido.timeouts == []
    assert corregido.indeterminados == [OTRO]
    assert corregido.base_rota == [VALIDO], "el repaso ya no pierde su base rota"
    assert corregido.muertos == 1
    assert corregido.codigos == {
        mutacion.clave_de_orden(VALIDO): "3",
        mutacion.clave_de_orden(OTRO): "2",
    }, "el del repaso pisa al del timeout, y el muerto no lleva código"
    assert corregido.pyc_no_borrados == ["c.pyc: z"]
    assert corregido.aviso_base is not None, "sin aviso, la cabecera NO VÁLIDA no explica nada"
    assert "1 mutante(s) del repaso" in corregido.aviso_base


def test_f023_r13_repaso_con_base_rota_conserva_su_propio_aviso() -> None:
    from harness.mutacion_paralela import reemplazar_timeouts

    campania = InformeMutacion(
        feature="F-999", alcance=_alcance(), mutantes_evaluados=[VALIDO], timeouts=[VALIDO],
    )
    repaso = InformeMutacion(
        feature="F-999", alcance=_alcance(), mutantes_evaluados=[VALIDO],
        base_rota=[VALIDO], aviso_base="LÍNEA BASE EN ROJO en el repaso",
    )

    corregido = reemplazar_timeouts(campania, repaso)

    assert corregido.aviso_base == "LÍNEA BASE EN ROJO en el repaso"


# --- R21, R22 · la línea base con la misma invocación ------------------------


def test_f023_r21_linea_base_acotada_como_los_mutantes() -> None:
    ejecutor = EjecutorPytest(
        argumentos=["-x", "-q", "tests/unit", "-k", "rapido", "-m", "no lento",
                    "--maxfail=3", "--maxfail", "2", "--exitfirst", "-p", "no:cacheprovider"],
        ruta="tests",
    )

    assert ejecutor.argumentos_linea_base() == (
        "-q", "tests/unit", "-k", "rapido", "-m", "no lento", "-p", "no:cacheprovider", "-rfE",
    )


def test_f023_r21_linea_base_no_duplica_el_resumen() -> None:
    ejecutor = EjecutorPytest(argumentos=["-q", "-rfE", "-k", "x"])

    assert ejecutor.argumentos_linea_base() == ("-q", "-rfE", "-k", "x")


def test_f023_r21_linea_base_usa_esos_argumentos_y_la_ruta() -> None:
    ejecutor = EjecutorPytest(argumentos=["-x", "-q", "-k", "rapido"], ruta="tests")
    pedidos: list[tuple] = []
    ejecutor.correr = lambda _t, argumentos=None: (  # type: ignore[method-assign]
        pedidos.append(argumentos) or ResultadoSuite(codigo=PYTEST_OK)
    )

    ejecutor.linea_base(1)

    assert pedidos == [("-q", "-k", "rapido", "-rfE")]


def test_f023_r22_linea_base_por_defecto_es_la_de_hoy() -> None:
    assert EjecutorPytest().argumentos_linea_base() == mutacion.ARGUMENTOS_LINEA_BASE
