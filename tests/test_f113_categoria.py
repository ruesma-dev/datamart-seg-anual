# tests/test_f113_categoria.py
"""
F-113 · La categoría CD/CI/CP sale del capítulo, no de letras sueltas (R1-R6, R9).

Hasta F-113 la categoría se decidía con `LIKE '%CD%'`, `'%CI%'`, `'%CP%'` sobre
el código del capítulo raíz, así que `AVDA_FRANCIA`, `P1414_PCI` y
`P1414_PISCIN` caían en COSTE INDIRECTO por llevar «CI» dentro. La regla nueva
(opción A, elegida por el humano el 2026-10-03):

* **raíz** por PREFIJO: empieza por `CD` → CD; por `CI` → CI; por `CP` → CP; si
  no, numérica pura distinta de 34 y 99 → CD; el resto → OTRO;
* **intermedio** por código EXACTO (sin puntos ni espacios) `CD`/`CI`/`CP`:
  manda sobre su subárbol, y el más cercano a la partida gana;
* cualquier otro intermedio —también el colapsado, sin código— hereda.

Los códigos de los parámetros **no son inventados**: son los medidos en
`raw.obrparpar` el 2026-10-03 (`progress/spec_F-113.md` §2). Ni red ni BBDD.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.arbol_partidas import Nodo, construir_arbol
from etl_sigrid.domain.categoria_partida import (
    CARACTERES_IGNORADOS_EN_INTERMEDIO,
    CATEGORIA_DE_RAIZ_NUMERICA,
    CATEGORIAS_DE_CAPITULO,
    OTRO,
    RAICES_NUMERICAS_FUERA,
    categoria_de_raiz,
    categoria_heredada,
)

OBRA = 1


# ---------------------------------------------------------------------------
# Las constantes: son las que el SQL tiene que repetir (R10)
# ---------------------------------------------------------------------------


def test_f113_r10_constantes_de_la_regla():
    """Si alguien cambia una de estas, `tests/test_f113_sql.py` exige que el SQL
    cambie con ella; aquí se fija que valen lo que la spec dice."""
    assert CATEGORIAS_DE_CAPITULO == ("CD", "CI", "CP")
    assert RAICES_NUMERICAS_FUERA == ("34", "99")
    assert CARACTERES_IGNORADOS_EN_INTERMEDIO == (".", " ")
    assert CATEGORIA_DE_RAIZ_NUMERICA == "CD"
    assert OTRO == "OTRO"


# ---------------------------------------------------------------------------
# R1 · la raíz, por prefijo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "codigo", ("AVDA_FRANCIA", "P1414_PCI", "P1414_PISCIN", "LEV.PISC")
)
def test_f113_r1_las_letras_en_mitad_del_codigo_no_cuentan(codigo: str):
    """El fallo de hoy: 253 partidas de dos obras en CI por llevar «CI» dentro."""
    assert categoria_de_raiz(codigo) == OTRO


@pytest.mark.parametrize(
    ("codigo", "esperada"),
    (
        ("CD", "CD"),
        ("CD'", "CD"),
        ("CD1", "CD"),
        ("CD-FII", "CD"),
        ("CD ", "CD"),
        ("CDP", "CD"),
        ("CI", "CI"),
        ("CI0", "CI"),
        ("CIA", "CI"),
        ("CI_F1", "CI"),
        ("CI.F2", "CI"),
        ("CI_F2", "CI"),
        ("CI-FII", "CI"),
        ("CI.II", "CI"),
        ("CIP", "CI"),
        ("CIPD", "CI"),
        ("CP", "CP"),
        ("CP.00", "CP"),
    ),
)
def test_f113_r1_las_variantes_medidas_conservan_su_categoria(
    codigo: str, esperada: str
):
    """Las 15 variantes de raíz medidas son todas capítulos CD/CI/CP por su
    descripción: el prefijo las cubre sin lista cerrada."""
    assert categoria_de_raiz(codigo) == esperada


@pytest.mark.parametrize(
    ("codigo", "esperada"),
    (("cd", "CD"), ("ci", "CI"), ("cp", "CP"), ("Cd-fii", "CD"), ("cI.f2", "CI")),
)
def test_f113_r1_minusculas_igual_que_mayusculas(codigo: str, esperada: str):
    assert categoria_de_raiz(codigo) == esperada


@pytest.mark.parametrize("codigo", (" CD", "_CI", "XCP", "1CD", ".CI"))
def test_f113_r1_el_prefijo_es_el_principio_del_codigo(codigo: str):
    """Ni un carácter delante: `LIKE 'CD%'`, no `LIKE '%CD%'`."""
    assert categoria_de_raiz(codigo) == OTRO


# ---------------------------------------------------------------------------
# R2 · la raíz que no empieza por CD/CI/CP: la regla de hoy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("codigo", ("01", "1", "02", "113", "340", "034", "9", "999"))
def test_f113_r2_raiz_numerica_pura_es_cd(codigo: str):
    assert categoria_de_raiz(codigo) == "CD"


@pytest.mark.parametrize("codigo", ("34", "99"))
def test_f113_r2_las_raices_34_y_99_son_otro(codigo: str):
    """34 es la Orden de Cambio y 99 el cajón de varios: OTRO, igual que hoy."""
    assert categoria_de_raiz(codigo) == OTRO


@pytest.mark.parametrize(
    "codigo",
    ("PD", "MP", "LEV", "GG", "MC", "TN", "OTROS", "POSVENTA", "1a", "01.", "²", ""),
)
def test_f113_r2_el_resto_es_otro(codigo: str):
    """Las raíces que hoy quedan en OTRO siguen en OTRO (decisión del humano del
    2026-10-03: `PD`, `MP`, `LEV`… no se tocan). `²` es numérico para
    `str.isdigit` y no para `^[0-9]+$`: el dominio usa lo segundo, como el SQL."""
    assert categoria_de_raiz(codigo) == OTRO


# ---------------------------------------------------------------------------
# R4 · el intermedio de código exacto manda sobre su subárbol
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("codigo", "esperada"),
    (
        ("CD", "CD"),
        ("CI", "CI"),
        ("CP", "CP"),
        ("C.I.", "CI"),
        ("C.D.", "CD"),
        ("C.P", "CP"),
        ("ci", "CI"),
        ("C I", "CI"),
        (" CP ", "CP"),
    ),
)
def test_f113_r4_codigo_exacto_sin_puntos_ni_espacios(codigo: str, esperada: str):
    for padre in ("CD", "CI", "CP", OTRO):
        assert categoria_heredada(codigo, padre) == esperada


# ---------------------------------------------------------------------------
# R5 · el intermedio que solo EMPIEZA por CD/CI/CP no cambia nada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "codigo",
    (
        "CI10",
        "CI-0036",
        "CP110",
        "CPI8001",
        "CIMENT",
        "CIERRE",
        "CI.7",
        "CP.10",
        "CI.05.00",
        "CI.01",
        "CDP",
        "C",
        "D",
        "CDCI",
        "01",
        "AVDA_FRANCIA",
        "C_I",
        "C-I",
    ),
)
def test_f113_r5_codigos_de_catalogo_heredan(codigo: str):
    """391 nodos `CI…` y 191 `CP…` bajo raíces CD son partidas de catálogo
    (`CI10` acero, `CPI8001` pilote, `CP110` puerta): con prefijo en los
    intermedios, 582 partidas de coste directo pasarían a CI/CP."""
    for padre in ("CD", "CI", "CP", OTRO):
        assert categoria_heredada(codigo, padre) == padre


# ---------------------------------------------------------------------------
# R6 · el colapsado (sin código) arrastra la del padre
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("padre", ("CD", "CI", "CP", OTRO))
def test_f113_r6_el_codigo_vacio_hereda(padre: str):
    assert categoria_heredada("", padre) == padre


# ---------------------------------------------------------------------------
# R3, R4, R5, R6, R9 · el árbol publica la categoría en cada partida
# ---------------------------------------------------------------------------


def _cadena(*codigos: str) -> list[Nodo]:
    """Una cadena lineal raíz > hijo > nieto…, con ide 1, 2, 3…"""
    return [
        Nodo(ide=i, padide=i - 1 if i > 1 else 0, cod=cod, obra_id=OBRA)
        for i, cod in enumerate(codigos, start=1)
    ]


def _categorias(nodos: list[Nodo]) -> dict[int, str]:
    return {p.partida_id: p.categoria for p in construir_arbol(nodos).publicadas}


@pytest.mark.parametrize(
    ("codigos", "esperadas"),
    (
        # R4: el intermedio exacto manda, y el más cercano gana.
        (("CD", "CI", "CI.01"), ("CD", "CI", "CI")),
        (("99", "CI", "CI.1"), (OTRO, "CI", "CI")),
        (("CD", "C.I.", "CI.01"), ("CD", "CI", "CI")),
        (("CD", "CP", "X"), ("CD", "CP", "CP")),
        (("CI", "CI", "CI"), ("CI", "CI", "CI")),
        (("CD", "F1", "CD"), ("CD", "CD", "CD")),
        (("CD", "CI", "CD", "01"), ("CD", "CI", "CD", "CD")),
        (("TN", "CI", "01"), (OTRO, "CI", "CI")),
        # R5: los códigos de catálogo heredan la de su raíz.
        (("CD", "02", "CI10"), ("CD", "CD", "CD")),
        (("CD", "02", "CI-0036"), ("CD", "CD", "CD")),
        (("CD", "07", "CP110"), ("CD", "CD", "CD")),
        (("CD", "AE04", "CPI8001"), ("CD", "CD", "CD")),
        (("CD", "45", "CIMENT"), ("CD", "CD", "CD")),
        (("113", "CIERRE"), ("CD", "CD")),
        (("CI", "CI.7", "CP.10"), ("CI", "CI", "CI")),
        (("OTROS", "CI.05.00"), (OTRO, OTRO)),
        # R1: la raíz por prefijo, y su categoría baja entera.
        (("AVDA_FRANCIA", "01", "01.01"), (OTRO, OTRO, OTRO)),
        (("P1414_PISCIN", "PCI"), (OTRO, OTRO)),
        (("CD-FII", "01"), ("CD", "CD")),
        (("34", "01"), (OTRO, OTRO)),
    ),
)
def test_f113_r3_r4_r5_r9_construir_arbol_publica_la_categoria(
    codigos: tuple[str, ...], esperadas: tuple[str, ...]
):
    categorias = _categorias(_cadena(*codigos))
    assert [categorias[i] for i in range(1, len(codigos) + 1)] == list(esperadas)


def test_f113_r6_el_colapsado_pasa_la_categoria_sin_cambiarla():
    """`CI > '' > 01`: el nodo sin código no se publica, pero su hijo hereda CI
    a través de él (F-052 lo atraviesa)."""
    arbol = construir_arbol(_cadena("CI", "", "01", "01.01"))

    assert arbol.descartadas_sin_codigo == (2,)
    assert {p.partida_id: p.categoria for p in arbol.publicadas} == {
        1: "CI",
        3: "CI",
        4: "CI",
    }


def test_f113_r4_r6_intermedio_exacto_tras_un_colapsado():
    """`CD > '' > CI > 01`: el colapsado no rompe la cadena y el intermedio
    exacto manda debajo de él."""
    arbol = construir_arbol(_cadena("CD", "", "CI", "01"))
    assert {p.partida_id: p.categoria for p in arbol.publicadas} == {
        1: "CD",
        3: "CI",
        4: "CI",
    }


def test_f113_r4_hermanos_no_se_contagian():
    """El intermedio `CI` manda en SU subárbol, no en el de su hermano: bajo la
    raíz CD de la 0500, `CI` y `01` son hermanos y `01` sigue en CD."""
    nodos = [
        Nodo(ide=1, padide=0, cod="CD", obra_id=OBRA),
        Nodo(ide=2, padide=1, cod="CI", obra_id=OBRA),
        Nodo(ide=3, padide=2, cod="CI.01", obra_id=OBRA),
        Nodo(ide=4, padide=1, cod="01", obra_id=OBRA),
        Nodo(ide=5, padide=4, cod="01.01", obra_id=OBRA),
    ]
    assert _categorias(nodos) == {1: "CD", 2: "CI", 3: "CI", 4: "CD", 5: "CD"}


def test_f113_r8_la_categoria_no_cambia_las_demas_columnas():
    """La categoría es una columna más: ruta, nivel, raíz y padre siguen siendo
    los de F-052."""
    arbol = construir_arbol(_cadena("CD", "", "CI", "01"))
    hoja = arbol.por_id(4)

    assert hoja is not None
    assert hoja.ruta_capitulos == "CD > CI > 01"
    assert hoja.nivel == 2
    assert hoja.capitulo_raiz_id == 1
    assert hoja.capitulo_raiz_cod == "CD"
    assert hoja.capitulo_padre_id == 3
    assert hoja.codigo_partida == "01"
