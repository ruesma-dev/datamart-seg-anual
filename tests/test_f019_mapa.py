# tests/test_f019_mapa.py
"""F-019 · Dominio del mapa línea -> tests (`harness.mapa_tests`), con datos fijos.

Sin coverage, sin pytest anidado y sin disco: solo la clasificación. Lo que
está en juego es la garantía dura de R12 —un mutante cuya sentencia se ejecuta
en algún proceso JAMÁS se poda— y que el subconjunto sea seleccionable.
"""

from __future__ import annotations

import pytest

from harness.mapa_tests import (
    TOPE_CARACTERES_ORDEN,
    Degradado,
    MapaTests,
    cabe_en_orden,
    clasificar,
    contextos_de,
    leer_volcado,
    lineas_de_sentencia,
    version_de_coverage_suficiente,
)

# --- R7: la sentencia, no la línea suelta ------------------------------------

PLEGADO = """\
valores = (1,
           2,
           3)
llamada = h(
    x,
    True,
)
"""


def test_f019_r7_constante_plegada_cuenta_la_sentencia_entera() -> None:
    """Hallazgo b de la spec: las líneas 2 y 3 no tienen evento de línea."""
    assert lineas_de_sentencia(PLEGADO, 2) == {1, 2, 3}
    assert lineas_de_sentencia(PLEGADO, 3) == {1, 2, 3}
    assert lineas_de_sentencia(PLEGADO, 6) == {4, 5, 6, 7}


COMPUESTAS = """\
@decorador(1 + 2)
def f(
    a=1,
):
    if (a >
            2):
        return a * 3
    elif a < 0:
        return 0
    else:
        return 1


class C:
    def g(self):
        try:
            x = 1
        except (ValueError if x > 1 else KeyError):
            pass
        for i in range(
                4):
            yield i
"""


def test_f019_r7_compuesta_cabecera_y_decoradores_sin_cuerpo() -> None:
    assert lineas_de_sentencia(COMPUESTAS, 1) == {1, 2, 3, 4}
    assert lineas_de_sentencia(COMPUESTAS, 3) == {1, 2, 3, 4}
    assert lineas_de_sentencia(COMPUESTAS, 6) == {5, 6}


def test_f019_r7_la_sentencia_simple_mas_interna_manda() -> None:
    assert lineas_de_sentencia(COMPUESTAS, 7) == {7}
    assert lineas_de_sentencia(COMPUESTAS, 17) == {17}
    assert lineas_de_sentencia(COMPUESTAS, 22) == {22}


def test_f019_r7_elif_except_y_for_multilinea_son_cabeceras() -> None:
    assert lineas_de_sentencia(COMPUESTAS, 8) == {8}
    assert lineas_de_sentencia(COMPUESTAS, 18) == {18}
    assert lineas_de_sentencia(COMPUESTAS, 21) == {20, 21}


def test_f019_r7_una_linea_fuera_de_toda_sentencia_es_ella_misma() -> None:
    assert lineas_de_sentencia(COMPUESTAS, 12) == {12}
    assert lineas_de_sentencia("x = (\n", 1) == {1}, "fuente que no compila"


def test_f019_r7_la_linea_pedida_siempre_entra() -> None:
    """`else:` no es sentencia: cae en la cabecera del `if` y en sí misma."""
    assert 10 in lineas_de_sentencia(COMPUESTAS, 10)


# --- R8, R10, R11, R12: clasificar -------------------------------------------

ORDEN = ("tests/test_a.py::test_1", "tests/test_a.py::test_2", "tests/test_b.py::test_3")


def test_f019_r8_sin_ninguna_ejecucion_se_poda() -> None:
    assert clasificar(frozenset(), ORDEN) == ("podar", ())


def test_f019_r10_solo_contexto_vacio_es_suite_entera() -> None:
    assert clasificar(frozenset({""}), ORDEN) == ("suite", ())


def test_f019_r9_con_tests_es_subconjunto_en_orden_de_recoleccion() -> None:
    clase, ids = clasificar(
        frozenset({"tests/test_b.py::test_3", "", "tests/test_a.py::test_1"}), ORDEN
    )
    assert clase == "subconjunto"
    assert ids == ("tests/test_a.py::test_1", "tests/test_b.py::test_3")


def test_f019_r11_si_el_subconjunto_es_la_suite_entera_va_la_suite() -> None:
    assert clasificar(frozenset(ORDEN), ORDEN) == ("suite", ())


def test_f019_r11_si_no_cabe_en_la_orden_va_la_suite() -> None:
    largos = tuple(f"tests/test_{i:05d}.py::" + "x" * 200 for i in range(200))
    contextos = frozenset(largos[:150])
    assert not cabe_en_orden(largos[:150])
    assert clasificar(contextos, largos)[0] == "suite"


def test_f019_r11_cabe_en_orden_mide_caracteres_con_separador() -> None:
    assert TOPE_CARACTERES_ORDEN == 24_000
    assert cabe_en_orden(("a" * 9,), tope=10)
    assert not cabe_en_orden(("a" * 10,), tope=10)
    assert cabe_en_orden(("a" * 4, "b" * 4), tope=10)


def test_f019_r12_un_test_que_no_esta_en_el_orden_no_se_inventa() -> None:
    """Si un contexto no casa con un test recogido, la suite entera, nunca poda."""
    assert clasificar(frozenset({"tests/test_z.py::fantasma"}), ORDEN) == ("suite", ())


@pytest.mark.parametrize(
    "contextos",
    [
        frozenset({""}),
        frozenset({"tests/test_a.py::test_1"}),
        frozenset({"", "tests/test_a.py::test_2"}),
        frozenset({"tests/test_z.py::fantasma"}),
        frozenset(ORDEN),
    ],
)
def test_f019_r12_con_alguna_ejecucion_jamas_se_poda(contextos: frozenset[str]) -> None:
    assert clasificar(contextos, ORDEN)[0] != "podar"


# --- contextos_de y R5 -------------------------------------------------------


def _mapa() -> MapaTests:
    return MapaTests(
        sha="abc",
        orden=ORDEN,
        contextos={
            "pkg/mod.py": {
                1: frozenset({""}),
                2: frozenset({"tests/test_a.py::test_1"}),
                3: frozenset({"tests/test_b.py::test_3", ""}),
            }
        },
        segundos=1.5,
    )


def test_f019_r7_contextos_de_une_los_de_todas_las_lineas() -> None:
    mapa = _mapa()
    assert contextos_de(mapa, "pkg/mod.py", {2, 3}) == frozenset(
        {"tests/test_a.py::test_1", "tests/test_b.py::test_3", ""}
    )
    assert contextos_de(mapa, "pkg/mod.py", {9}) == frozenset()
    assert contextos_de(mapa, "otro.py", {1}) == frozenset()


def test_f019_r5_el_mismo_mapa_vale_para_cualquier_mutante() -> None:
    """Inmutable y sin estado: lo comparten mutantes y workers sin copiarlo."""
    mapa = _mapa()
    with pytest.raises(AttributeError):
        mapa.sha = "otro"  # type: ignore[misc]
    assert contextos_de(mapa, "pkg/mod.py", {2}) == contextos_de(mapa, "pkg/mod.py", {2})
    assert Degradado("x").motivo == "x"


# --- R4: copias del fichero fuera del árbol ----------------------------------


def _volcado(ficheros: dict[str, dict[str, list[int]]]) -> dict:
    return {"contextos": ["", "tests/test_a.py::test_1"], "ficheros": ficheros}


def test_f019_r4_el_fichero_del_arbol_conserva_sus_contextos(tmp_path) -> None:
    raiz = tmp_path / "proyecto"
    raiz.mkdir()
    medido = str(raiz / "pkg" / "mod.py")
    datos = _volcado({medido: {"2": [1], "3": [0, 1]}})

    leido = leer_volcado(datos, str(raiz), ["pkg/mod.py"])

    assert leido == {
        "pkg/mod.py": {
            2: frozenset({"tests/test_a.py::test_1"}),
            3: frozenset({"", "tests/test_a.py::test_1"}),
        }
    }


def test_f019_r4_una_copia_fuera_del_arbol_cuenta_sin_test_atribuible(tmp_path) -> None:
    raiz = tmp_path / "proyecto"
    copia = tmp_path / "temporal" / "otra" / "pkg" / "mod.py"
    datos = _volcado({str(copia): {"10": [1]}, str(raiz / "pkg" / "mod.py"): {"2": [1]}})

    leido = leer_volcado(datos, str(raiz), ["pkg/mod.py"])

    assert leido["pkg/mod.py"][10] == frozenset({""}), "la copia NO atribuye el test"
    assert leido["pkg/mod.py"][2] == frozenset({"tests/test_a.py::test_1"})


def test_f019_r4_separadores_y_mayusculas_normalizados() -> None:
    datos = _volcado({"C:\\Repo\\Pkg\\Mod.py": {"2": [1]}})

    sin = leer_volcado(datos, "c:/repo", ["pkg/mod.py"], sin_mayusculas=True)
    con = leer_volcado(datos, "c:/repo", ["pkg/mod.py"], sin_mayusculas=False)

    assert sin["pkg/mod.py"] == {2: frozenset({"tests/test_a.py::test_1"})}
    assert con["pkg/mod.py"] == {}, "con mayúsculas distintas no es el mismo fichero"


def test_f019_r4_un_fichero_que_no_termina_en_la_ruta_no_cuenta(tmp_path) -> None:
    datos = _volcado({str(tmp_path / "pkg" / "otromod.py"): {"2": [1]}})

    assert leer_volcado(datos, str(tmp_path / "x"), ["pkg/mod.py"]) == {"pkg/mod.py": {}}


# --- R18: versión de coverage ------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "suficiente"),
    [
        ("Coverage.py, version 7.15.4 with C extension", True),
        ("Coverage.py, version 7.10.0 with C extension", True),
        ("Coverage.py, version 7.9.2 with C extension", False),
        ("Coverage.py, version 6.5.0", False),
        ("Coverage.py, version 8.0.1", True),
        ("No module named coverage", False),
        ("", False),
    ],
)
def test_f019_r18_version_minima_de_coverage(texto: str, suficiente: bool) -> None:
    assert version_de_coverage_suficiente(texto) is suficiente
