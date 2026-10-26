# tests/test_f140_dominio.py
"""
F-140 · El dominio de los ingredientes de caja: la fórmula de plazo, el
pendiente de una partida y su reparto en el tiempo (R7, R8, R12, R14, R16).

Dominio puro: ni red ni BBDD. Los casos de la fórmula son los de
`specs/F-140-proyeccion-caja-ingredientes/design.md` §3 y las fórmulas reales
medidas en `progress/spec_F-140.md` §1.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import (
    PlazoFormula,
    leer_formula_plazo,
    pendiente_partida,
    repartir_pendiente,
)

D = Decimal


# ===========================================================================
# R7 · la fórmula reconocida
# ===========================================================================

@pytest.mark.parametrize(
    ("formula", "dias", "retencion"),
    [
        ("30 60 90", (30, 60, 90), None),
        ("90  450R", (90,), 450),
        ("450R", (), 450),
        ("0", (0,), None),
        ("120 450R", (120,), 450),
        ("150 450R", (150,), 450),
        (" 30 ", (30,), None),
        ("60 30", (60, 30), None),
        ("450R 30", (30,), 450),
    ],
)
def test_f140_r7_formula_reconocida(formula: str, dias: tuple, retencion) -> None:
    assert leer_formula_plazo(formula) == PlazoFormula(dias, retencion, True)


def test_f140_r7_los_dias_van_en_el_orden_escrito() -> None:
    """No se ordenan: «60 30» son dos vencimientos, el primero a 60."""
    assert leer_formula_plazo("60 30 90").dias_vencimientos == (60, 30, 90)


def test_f140_r7_blancos_repetidos_separan_como_uno() -> None:
    assert leer_formula_plazo("30   60") == leer_formula_plazo("30 60")


def test_f140_r7_el_resultado_es_inmutable() -> None:
    plazo = leer_formula_plazo("30")
    with pytest.raises(AttributeError):
        plazo.reconocida = False  # type: ignore[misc]


# ===========================================================================
# R8 · falla cerrado
# ===========================================================================

@pytest.mark.parametrize(
    "formula",
    [None, "", "   ", "30 x", "30R 450R", "x", "30,60", "R", "30 R", "-30", "30.5",
     "30r", "\t30"],
)
def test_f140_r8_formula_no_reconocida(formula) -> None:
    assert leer_formula_plazo(formula) == PlazoFormula((), None, False)


def test_f140_r8_los_regex_son_los_del_diseno() -> None:
    """El SQL de `00_setup.sql` lleva estos mismos literales (test del SQL)."""
    assert dom.REGEX_TOKEN_DIAS == r"^[0-9]+$"
    assert dom.REGEX_TOKEN_RETENCION == r"^[0-9]+R$"


def test_f140_r8_el_separador_es_el_del_sql() -> None:
    """`regexp_split_to_array(btrim(f), '\\s+')`: btrim quita solo espacios."""
    assert dom.SEPARADOR_TOKENS == r"\s+"
    # un tabulador al principio deja un token vacío, que no casa: no reconocida
    assert not leer_formula_plazo("\t30").reconocida
    # un tabulador ENTRE tokens separa, como cualquier blanco
    assert leer_formula_plazo("30\t60") == PlazoFormula((30, 60), None, True)


# ===========================================================================
# R12 · el pendiente de una partida
# ===========================================================================

@pytest.mark.parametrize(
    ("plan", "ejecutado", "pendiente", "sobre"),
    [
        (D("100"), D("30"), D("70"), D("0")),
        (D("100"), D("100"), D("0"), D("0")),
        (D("100"), D("130"), D("0"), D("30")),
        (D("0"), D("0"), D("0"), D("0")),
        (D("0"), D("25.5"), D("0"), D("25.5")),
        (D("-10"), D("0"), D("0"), D("10")),
        (D("50"), D("-5"), D("55"), D("0")),
    ],
)
def test_f140_r12_pendiente_y_sobre_ejecutado(plan, ejecutado, pendiente, sobre) -> None:
    assert pendiente_partida(plan, ejecutado) == (pendiente, sobre)


def test_f140_r12_pendiente_y_sobre_no_se_dan_a_la_vez() -> None:
    for plan, eje in ((D(5), D(3)), (D(3), D(5)), (D(4), D(4))):
        pendiente, sobre = pendiente_partida(plan, eje)
        assert pendiente == 0 or sobre == 0
        assert pendiente - sobre == plan - eje


# ===========================================================================
# R14 · el reparto del pendiente en el tiempo (D19)
# ===========================================================================

ENE, FEB, MAR, ABR = (date(2027, m, 1) for m in (1, 2, 3, 4))
PRIMERO = date(2026, 11, 1)


def test_f140_r14_proporcional_al_perfil() -> None:
    reparto = repartir_pendiente(D("100"), [(ENE, D("10")), (FEB, D("30"))], PRIMERO)
    assert reparto == [(ENE, D("25.00"), False), (FEB, D("75.00"), False)]


def test_f140_r14_el_ultimo_mes_absorbe_el_redondeo() -> None:
    """100 / 3 no divide exacto: 33,33 + 33,33 + 33,34."""
    reparto = repartir_pendiente(
        D("100"), [(ENE, D("1")), (FEB, D("1")), (MAR, D("1"))], PRIMERO
    )
    assert reparto == [
        (ENE, D("33.33"), False), (FEB, D("33.33"), False), (MAR, D("33.34"), False)
    ]


@pytest.mark.parametrize(
    "pendiente", [D("0.01"), D("0.05"), D("10"), D("1234567.89"), D("99.99"), D("7")]
)
def test_f140_r14_la_suma_iguala_el_pendiente_al_centimo(pendiente) -> None:
    perfil = [(ENE, D("3.3333")), (FEB, D("7")), (MAR, D("0.0001")), (ABR, D("13"))]
    reparto = repartir_pendiente(pendiente, perfil, PRIMERO)
    assert sum(importe for _mes, importe, _r in reparto) == pendiente
    assert all(importe == importe.quantize(D("0.01")) for _m, importe, _r in reparto)


def test_f140_r14_el_ultimo_es_el_mes_mas_tardio_aunque_venga_desordenado() -> None:
    reparto = repartir_pendiente(
        D("100"), [(MAR, D("1")), (ENE, D("1")), (FEB, D("1"))], PRIMERO
    )
    assert reparto == [
        (ENE, D("33.33"), False), (FEB, D("33.33"), False), (MAR, D("33.34"), False)
    ]


def test_f140_r14_redondeo_de_la_mitad_hacia_arriba_como_round_de_postgres() -> None:
    """`ROUND(numeric, 2)` lleva la mitad lejos del cero: 0,125 -> 0,13."""
    reparto = repartir_pendiente(D("0.25"), [(ENE, D("1")), (FEB, D("1"))], PRIMERO)
    assert reparto == [(ENE, D("0.13"), False), (FEB, D("0.12"), False)]


def test_f140_r14_perfil_vacio_todo_al_primer_mes_como_retraso() -> None:
    assert repartir_pendiente(D("80"), [], PRIMERO) == [(PRIMERO, D("80"), True)]


def test_f140_r14_perfil_a_cero_todo_al_primer_mes_como_retraso() -> None:
    perfil = [(ENE, D("0")), (FEB, D("0"))]
    assert repartir_pendiente(D("80"), perfil, PRIMERO) == [(PRIMERO, D("80"), True)]


def test_f140_r14_perfil_neto_negativo_no_reparte() -> None:
    """Un perfil que suma menos que cero daría importes de signo contrario."""
    perfil = [(ENE, D("10")), (FEB, D("-30"))]
    assert repartir_pendiente(D("80"), perfil, PRIMERO) == [(PRIMERO, D("80"), True)]


def test_f140_r14_los_meses_a_cero_del_perfil_no_son_perfil() -> None:
    """La cola a cero no es plan (criterio de F-110): ni fila ni último mes."""
    perfil = [(ENE, D("1")), (FEB, D("1")), (MAR, D("0"))]
    reparto = repartir_pendiente(D("1"), perfil, PRIMERO)
    assert reparto == [(ENE, D("0.50"), False), (FEB, D("0.50"), False)]


def test_f140_r14_sin_pendiente_no_hay_reparto() -> None:
    assert repartir_pendiente(D("0"), [(ENE, D("5"))], PRIMERO) == []
    assert repartir_pendiente(D("0"), [], PRIMERO) == []


def test_f140_r14_un_solo_mes_se_lo_lleva_todo() -> None:
    assert repartir_pendiente(D("12.345"), [(FEB, D("2"))], PRIMERO) == [
        (FEB, D("12.345"), False)
    ]


# ===========================================================================
# R16 · el patrón de una columna de caja
# ===========================================================================

def test_f140_r16_el_patron_es_el_del_diseno() -> None:
    assert dom.PATRON_COLUMNA_DE_CAJA == r"caja|flujo|previst|fecha_pago|fecha_cobro|con_iva"


@pytest.mark.parametrize(
    "columna",
    ["caja_mes", "importe_flujo", "pago_previsto", "fecha_pago_estimada",
     "fecha_cobro", "importe_con_iva", "CAJA"],
)
def test_f140_r16_el_patron_caza_las_columnas_de_caja(columna: str) -> None:
    assert dom.es_columna_de_caja(columna)


@pytest.mark.parametrize(
    "columna",
    ["importe_pendiente", "plazo_formula", "dias_retencion", "cartera_viva",
     "mes_ultimo_cierre", "importe_iva", "valor"],
)
def test_f140_r16_el_patron_no_caza_los_ingredientes(columna: str) -> None:
    assert not dom.es_columna_de_caja(columna)


def test_f140_r16_el_patron_es_un_regex_valido() -> None:
    re.compile(dom.PATRON_COLUMNA_DE_CAJA)


# ===========================================================================
# R17 · la obra de un efecto sin centro (D10-A, la cascada)
# ===========================================================================

from etl_sigrid.domain import tesoreria as dom_tes  # noqa: E402
from etl_sigrid.domain.tesoreria import obra_del_efecto  # noqa: E402


def test_f140_r17_las_vias_y_su_orden() -> None:
    assert dom_tes.VIA_CENTRO == "CENTRO"
    assert dom_tes.VIA_CONTRATO == "CONTRATO"
    assert dom_tes.VIA_FACTURA_CABECERA == "FACTURA_CABECERA"
    assert dom_tes.VIA_FACTURA_LINEAS == "FACTURA_LINEAS"
    assert dom_tes.VIAS_EN_ORDEN == (
        "CENTRO", "CONTRATO", "FACTURA_CABECERA", "FACTURA_LINEAS"
    )


def test_f140_r17_el_centro_con_obra_manda() -> None:
    assert obra_del_efecto(7, True, [8], 9, [10]) == (7, "CENTRO")


def test_f140_r17_el_centro_sin_obra_no_sigue_la_cascada() -> None:
    """Un centro que no es obra (estructura, delegación) dice que NO es de obra."""
    assert obra_del_efecto(None, True, [8], 9, [10]) == (None, None)


def test_f140_r17_sin_centro_el_contrato_unico() -> None:
    assert obra_del_efecto(None, False, [8, 8], 9, [10]) == (8, "CONTRATO")


def test_f140_r17_dos_obras_de_contrato_no_deciden() -> None:
    assert obra_del_efecto(None, False, [8, 11], 9, [10]) == (9, "FACTURA_CABECERA")


def test_f140_r17_sin_contrato_la_cabecera() -> None:
    assert obra_del_efecto(None, False, [], 9, [10]) == (9, "FACTURA_CABECERA")


@pytest.mark.parametrize("cabecera", [None, 0])
def test_f140_r17_sin_cabecera_las_lineas_si_son_una_obra(cabecera) -> None:
    assert obra_del_efecto(None, False, [], cabecera, [10, 10, None]) == (10, "FACTURA_LINEAS")


def test_f140_r17_lineas_de_varias_obras_no_deciden() -> None:
    assert obra_del_efecto(None, False, [], None, [10, 12]) == (None, None)


def test_f140_r17_nada_que_mirar() -> None:
    assert obra_del_efecto(None, False, [], None, []) == (None, None)


def test_f140_r17_los_ceros_y_nulos_no_son_obra() -> None:
    """`NULLIF(x, 0)` del SQL: un 0 de Sigrid es «sin obra»."""
    assert obra_del_efecto(None, False, [0, None], 0, [0]) == (None, None)
    assert obra_del_efecto(None, False, [0, 8], None, []) == (8, "CONTRATO")
    assert obra_del_efecto(0, True, [8], 9, [10]) == (None, None)
