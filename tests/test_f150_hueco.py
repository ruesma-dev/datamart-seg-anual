# tests/test_f150_hueco.py
"""
F-150 · El hueco de facturación de H26 (R22, N6, N9), en el dominio.

Lo ejecutado y no facturado también se cobra: el hueco de una obra es lo real
a origen con coeficientes menos lo facturado, NETO POR OBRA y nunca por
contrato. Lo facturado por delante NUNCA es caja a cobrar: se publica aparte y
el hueco se queda en 0. La venta real sin coeficiente entra con la media
ponderada de su obra (`MEDIA_OBRA`). Dominio puro: sin BBDD.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from etl_sigrid.domain.proyeccion_caja import (
    FUENTE_MEDIA_OBRA,
    coeficiente_medio,
    hueco_facturacion,
)

D = Decimal


# ---------------------------------------------------------------------------
# R22 · el hueco, neto y con suelo 0
# ---------------------------------------------------------------------------


def test_f150_r22_lo_real_por_encima_de_lo_facturado_es_hueco() -> None:
    assert hueco_facturacion(D("1500.00"), D("1000.00")) == (D("500.00"), D("0.00"))


def test_f150_r22_lo_facturado_por_delante_no_es_hueco() -> None:
    assert hueco_facturacion(D("1000.00"), D("1500.00")) == (D("0.00"), D("500.00"))


def test_f150_r22_igual_es_cero_y_cero() -> None:
    assert hueco_facturacion(D("1000"), D("1000")) == (D("0.00"), D("0.00"))


@pytest.mark.parametrize(("real", "facturado", "esperado"), [
    (None, D("300"), (D("0.00"), D("300.00"))),
    (D("300"), None, (D("300.00"), D("0.00"))),
    (None, None, (D("0.00"), D("0.00"))),
])
def test_f150_r22_none_cuenta_cero(real, facturado, esperado) -> None:
    assert hueco_facturacion(real, facturado) == esperado


def test_f150_r22_al_centimo_la_mitad_hacia_arriba() -> None:
    assert hueco_facturacion(D("100.005"), D("0")) == (D("100.01"), D("0.00"))
    assert hueco_facturacion(D("0"), D("100.005")) == (D("0.00"), D("100.01"))
    pendiente, por_delante = hueco_facturacion(D("1"), D("0"))
    assert pendiente.as_tuple().exponent == -2 and por_delante.as_tuple().exponent == -2


def test_f150_r22_facturado_negativo_por_rectificativas() -> None:
    """Las rectificativas (`cla` 1024) ya restan en `totbas`: el neto puede ser negativo."""
    assert hueco_facturacion(D("100"), D("-50")) == (D("150.00"), D("0.00"))


# ---------------------------------------------------------------------------
# R22 · el coeficiente medio de la obra (MEDIA_OBRA)
# ---------------------------------------------------------------------------


def test_f150_r22_la_fuente_de_la_media() -> None:
    assert FUENTE_MEDIA_OBRA == "MEDIA_OBRA"


def test_f150_r22_coeficiente_medio_ponderado_por_lo_real() -> None:
    # (100 x 1,19 + 300 x 1,00) / 400 = 1,0475
    assert coeficiente_medio([(D("100"), D("1.19")), (D("300"), D("1"))]) == D("1.047500")


def test_f150_r22_coeficiente_medio_a_seis_decimales() -> None:
    # (1 x 1 + 2 x 1,5) / 3 = 1,3333333...
    resultado = coeficiente_medio([(D("1"), D("1")), (D("2"), D("1.5"))])
    assert resultado == D("1.333333") and resultado.as_tuple().exponent == -6


def test_f150_r22_coeficiente_medio_sin_real_es_none() -> None:
    assert coeficiente_medio([]) is None
    assert coeficiente_medio([(D("0"), D("1.19"))]) is None
    assert coeficiente_medio([(D("100"), D("1.19")), (D("-100"), D("1"))]) is None


def test_f150_r22_coeficiente_medio_ignora_los_pares_sin_coeficiente() -> None:
    """Las partidas sin coeficiente son las que RECIBEN la media, no las que la hacen."""
    assert coeficiente_medio([(D("100"), D("1.19")), (D("500"), None)]) == D("1.190000")
    assert coeficiente_medio([(None, D("1.19")), (D("100"), D("1.1"))]) == D("1.100000")
