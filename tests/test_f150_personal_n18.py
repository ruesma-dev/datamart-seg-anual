# tests/test_f150_personal_n18.py
"""
F-150 · N18 (quinta tanda, 31-10): el personal pendiente se paga en DOS tramos,
el NETO el último día del mes de su devengo y el IRPF + la Seguridad Social el
último día del mes SIGUIENTE (R53-R61; corrige la decisión (f) de N16).

La parte de IRPF + SS sale de la CONTABILIDAD de la empresa (abonos NORMAL de
12 meses de 4652000000 Nóminas Pdtes de Pago, 4751000000 H.P. Acree. Reten.
Trabajo y 4760000000 Seguridad Social Acreedora, leídos de `raw.apu`): medido
el 31-10, empresa 1, 0,4419. Se publica solo la CUOTA (las cuentas son CR,
`R-PERFILES`): `tesoreria.reparto_pago_personal` no lleva importes.

Primero el dominio (el oráculo); después el SQL de `07` y `10` leído como
texto (literales = dominio, patrón de F-135): ni red ni BBDD.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from etl_sigrid.domain import proyeccion_caja as dom

D = Decimal


# ===========================================================================
# R53 · cuota_irpf_ss: (irpf + ss) / (neto + irpf + ss), a 6 decimales
# ===========================================================================


def test_f150_r53_la_cuota_medida_de_la_empresa_1() -> None:
    """12 meses oct-25..sep-26 (miles de EUR): 7.715,3 / 2.143,0 / 3.966,1."""
    assert dom.cuota_irpf_ss(D("7715.3"), D("2143.0"), D("3966.1")) == D("0.441907")


def test_f150_r53_redondea_a_seis_decimales_la_mitad_lejos_del_cero() -> None:
    assert dom.cuota_irpf_ss(D("2"), D("1"), D("0")) == D("0.333333")
    assert dom.cuota_irpf_ss(D("1"), D("1"), D("1")) == D("0.666667")
    # 1 / 2.000.000 = 0,0000005 exacto: sube (ROUND de PostgreSQL), no al par.
    assert dom.cuota_irpf_ss(D("1999999"), D("1"), D("0")) == D("0.000001")


def test_f150_r53_sin_irpf_ni_ss_la_cuota_es_cero() -> None:
    assert dom.cuota_irpf_ss(D("100"), D("0"), D("0")) == D("0.000000")


@pytest.mark.parametrize(
    ("neto", "irpf", "ss"),
    [
        (D("0"), D("10"), D("10")),       # sin neto: no hay nómina que partir
        (D("-5"), D("10"), D("10")),      # neto negativo (anulaciones)
        (None, D("10"), D("10")),
        (D("100"), D("-60"), D("-50")),   # IRPF + SS < -neto: cociente > 1
        (D("100"), D("-50"), D("-50")),   # denominador 0: no se divide
        (D("100"), D("-10"), D("0")),     # cuota negativa
        (D("100"), None, D("10")),
        (D("100"), D("10"), None),
    ],
)
def test_f150_r53_fuera_de_rango_o_sin_neto_devuelve_none(neto, irpf, ss) -> None:
    assert dom.cuota_irpf_ss(neto, irpf, ss) is None


def test_f150_r53_los_extremos_del_rango_valen() -> None:
    assert dom.cuota_irpf_ss(D("100"), D("0"), D("0")) == D("0")
    # neto > 0 diminuto frente a irpf + ss: 0,999999..., redondea a 1 y vale.
    assert dom.cuota_irpf_ss(D("0.0000001"), D("100"), D("0")) == D("1")


# ===========================================================================
# R54 · reparto_pago_personal: (cuota, fuente, motivo)
# ===========================================================================

NETO, IRPF, SS = D("7715.3"), D("2143.0"), D("3966.1")


def test_f150_r54_las_constantes() -> None:
    assert dom.CUENTAS_NOMINA == {"NETO": "4652000000", "IRPF": "4751000000", "SS": "4760000000"}
    assert dom.MESES_VENTANA_NOMINA == 12
    assert dom.MESES_MAX_SIN_NOMINA == 3
    assert dom.MIN_PERSONAS_REPARTO == 10
    assert dom.FUENTES_REPARTO_PERSONAL == ("CONTABILIDAD", "CONTABILIDAD_PARCIAL", "DEFECTO")
    assert dom.MOTIVOS_REPARTO_PERSONAL == (
        "SIN_NOMINA_RECIENTE", "POCAS_PERSONAS", "CUOTA_FUERA_DE_RANGO")


def test_f150_r54_doce_meses_es_contabilidad() -> None:
    assert dom.reparto_pago_personal(12, 273, NETO, IRPF, SS) == (D("0.441907"), "CONTABILIDAD", None)


@pytest.mark.parametrize("meses", [1, 6, 11])
def test_f150_r54_de_uno_a_once_meses_es_parcial_y_se_aplica(meses: int) -> None:
    assert dom.reparto_pago_personal(meses, 273, NETO, IRPF, SS) == (
        D("0.441907"), "CONTABILIDAD_PARCIAL", None)


def test_f150_r54_sin_nomina_reciente_es_defecto_cero() -> None:
    """Sin abono en 4652000000 en los 3 meses anteriores al build no hay
    ventana: 0 meses. Defecto = N16: todo a fin del mes de devengo."""
    assert dom.reparto_pago_personal(0, 273, None, None, None) == (
        D("0"), "DEFECTO", "SIN_NOMINA_RECIENTE")
    assert dom.reparto_pago_personal(0, 273, NETO, IRPF, SS) == (
        D("0"), "DEFECTO", "SIN_NOMINA_RECIENTE")


def test_f150_r54_nueve_personas_es_defecto_diez_no() -> None:
    """Con menos de 10 personas la cuota delataría el IRPF de alguien."""
    assert dom.reparto_pago_personal(12, 9, NETO, IRPF, SS) == (D("0"), "DEFECTO", "POCAS_PERSONAS")
    assert dom.reparto_pago_personal(12, 0, NETO, IRPF, SS) == (D("0"), "DEFECTO", "POCAS_PERSONAS")
    assert dom.reparto_pago_personal(12, 10, NETO, IRPF, SS)[1] == "CONTABILIDAD"


def test_f150_r54_cuota_fuera_de_rango_es_defecto() -> None:
    assert dom.reparto_pago_personal(12, 273, D("0"), IRPF, SS) == (
        D("0"), "DEFECTO", "CUOTA_FUERA_DE_RANGO")
    assert dom.reparto_pago_personal(5, 273, D("100"), D("-60"), D("-50")) == (
        D("0"), "DEFECTO", "CUOTA_FUERA_DE_RANGO")


def test_f150_r54_el_orden_de_los_motivos() -> None:
    """Sin nómina manda sobre pocas personas, y pocas personas sobre el rango."""
    assert dom.reparto_pago_personal(0, 3, D("0"), D("1"), D("1"))[2] == "SIN_NOMINA_RECIENTE"
    assert dom.reparto_pago_personal(12, 3, D("0"), D("1"), D("1"))[2] == "POCAS_PERSONAS"


def test_f150_r54_fuente_y_motivo_siempre_del_catalogo() -> None:
    for meses, personas, n in [(12, 273, NETO), (3, 50, NETO), (0, 50, NETO), (12, 2, NETO),
                               (12, 50, D("-1"))]:
        cuota, fuente, motivo = dom.reparto_pago_personal(meses, personas, n, IRPF, SS)
        assert fuente in dom.FUENTES_REPARTO_PERSONAL
        assert (motivo is None) == (fuente != "DEFECTO")
        assert motivo is None or motivo in dom.MOTIVOS_REPARTO_PERSONAL
        assert D("0") <= cuota <= D("1")


# ===========================================================================
# R55 · partir_personal: irpf_ss al céntimo y el neto, la resta
# ===========================================================================


def test_f150_r55_la_0686_de_noviembre() -> None:
    """0,2104 M EUR de personal en 2026-11 con 0,441907."""
    neto, irpf_ss = dom.partir_personal(D("210400.00"), D("0.441907"))
    assert irpf_ss == D("92977.23")
    assert neto == D("117422.77")


def test_f150_r55_redondeo_al_centimo_la_mitad_lejos_del_cero() -> None:
    assert dom.partir_personal(D("0.01"), D("0.5")) == (D("0.00"), D("0.01"))
    assert dom.partir_personal(D("-0.01"), D("0.5")) == (D("0.00"), D("-0.01"))
    assert dom.partir_personal(D("100.00"), D("0.333333")) == (D("66.67"), D("33.33"))


@pytest.mark.parametrize("importe", [D("0"), D("0.00"), D("-123.45"), D("0.03"), D("999999.99")])
@pytest.mark.parametrize("cuota", [D("0"), D("0.441907"), D("0.5"), D("1"), D("0.000001")])
def test_f150_r55_la_suma_es_exacta_al_centimo(importe: Decimal, cuota: Decimal) -> None:
    neto, irpf_ss = dom.partir_personal(importe, cuota)
    assert neto + irpf_ss == importe
    assert irpf_ss == irpf_ss.quantize(D("0.01"))


def test_f150_r55_cuota_cero_es_todo_neto_y_uno_todo_al_mes_siguiente() -> None:
    assert dom.partir_personal(D("500.00"), D("0")) == (D("500.00"), D("0.00"))
    assert dom.partir_personal(D("500.00"), D("1")) == (D("0.00"), D("500.00"))
