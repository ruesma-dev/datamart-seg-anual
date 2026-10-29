# tests/test_f150_albaranes.py
"""
F-150 · Los albaranes pendientes de facturar NETOS por proveedor (N11, R33-R35)
y la parte de coste proporcional de la cartera (N12, R36).

Lo que suma `compras.v_pbi_albaranes_sin_facturar` (solo líneas > 0: 56,9 M EUR
en las 21 obras el 29-10) no es lo que queda por facturar: 48,2 de esos millones
ya están SOBREFACTURADOS al mismo proveedor en otras líneas (pendiente < 0). Lo
real es el NETO por (obra, proveedor), con suelo 0 (8,76 M EUR). Para fecharlo
(H20, H27) se supone FIFO: lo sobrefacturado compensa primero las entregas más
antiguas.

Primero el dominio (`neto_fifo`, el oráculo); después el SQL leído como texto
(literales = dominio, patrón de F-135): ni red ni BBDD.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import neto_fifo

D = Decimal


# ===========================================================================
# R33 · neto_fifo: lo sobrefacturado compensa primero lo más antiguo
# ===========================================================================


def test_f150_r33_todo_positivo_queda_entero() -> None:
    assert neto_fifo([D("100.00"), D("50.00")]) == [D("100.00"), D("50.00")]


def test_f150_r33_todo_negativo_da_ceros() -> None:
    """Sobrefacturado sin nada que compensar: el residuo no es caja (suelo 0)."""
    assert neto_fifo([D("-100.00"), D("-5.00")]) == [D("0"), D("0")]


def test_f150_r33_los_negativos_cubren_justo_lo_positivo() -> None:
    assert neto_fifo([D("100.00"), D("-60.00"), D("50.00"), D("-90.00")]) == [
        D("0"), D("0"), D("0"), D("0"),
    ]


def test_f150_r33_los_negativos_sobran() -> None:
    assert neto_fifo([D("100.00"), D("-500.00"), D("50.00")]) == [D("0"), D("0"), D("0")]


def test_f150_r33_los_negativos_faltan_y_compensan_primero_lo_antiguo() -> None:
    # N = 130: compensa entera la primera (100) y 30 de la segunda (50 -> 20); la
    # cuarta, intacta. FIFO, no LIFO (LIFO dejaría 60 en la primera y 0 en las demás).
    assert neto_fifo([D("100.00"), D("50.00"), D("-130.00"), D("40.00")]) == [
        D("0"), D("20.00"), D("0"), D("40.00"),
    ]


def test_f150_r33_el_orden_manda_no_el_tamano() -> None:
    """Con los mismos importes en otro orden, el resto cae en la otra línea."""
    assert neto_fifo([D("10"), D("90"), D("-50")]) == [D("0"), D("50"), D("0")]
    assert neto_fifo([D("90"), D("10"), D("-50")]) == [D("40"), D("10"), D("0")]


def test_f150_r33_la_posicion_del_negativo_no_importa() -> None:
    """Σ |negativos| es del (obra, proveedor) entero: un abono de hoy compensa
    la entrega de hace un año (FIFO sobre las POSITIVAS)."""
    assert neto_fifo([D("-30"), D("100"), D("20")]) == [D("0"), D("70"), D("20")]
    assert neto_fifo([D("100"), D("20"), D("-30")]) == [D("70"), D("20"), D("0")]


def test_f150_r33_none_y_cero_dan_cero_y_no_compensan() -> None:
    assert neto_fifo([None, D("100"), D("0"), None, D("-40")]) == [
        D("0"), D("60"), D("0"), D("0"), D("0"),
    ]


def test_f150_r33_lista_vacia() -> None:
    assert neto_fifo([]) == []


def test_f150_r33_al_centimo() -> None:
    assert neto_fifo([D("0.01"), D("0.02"), D("-0.02")]) == [D("0"), D("0.01"), D("0")]
    assert neto_fifo([D("1234.56"), D("-1234.55")]) == [D("0.01"), D("0")]


@pytest.mark.parametrize("importes", [
    [D("100"), D("-30"), D("20.55"), D("-0.01"), D("7.45")],
    [D("-5"), D("-5"), D("3"), D("4")],
    [D("12.34"), None, D("-12.34"), D("0.66")],
    [D("1"), D("2"), D("3"), D("-10")],
    [D("0.01")] * 7 + [D("-0.03")],
])
def test_f150_r33_suma_es_max_cero_y_cada_resto_entre_cero_y_su_linea(importes) -> None:
    restos = neto_fifo(importes)
    assert len(restos) == len(importes)
    total = sum((x for x in importes if x is not None), D(0))
    assert sum(restos, D(0)) == max(D(0), total)
    for x, r in zip(importes, restos):
        tope = x if x is not None and x > 0 else D(0)
        assert D(0) <= r <= tope


def test_f150_r33_no_modifica_la_entrada() -> None:
    importes = [D("10"), D("-5")]
    neto_fifo(importes)
    assert importes == [D("10"), D("-5")]


def test_f150_r33_los_literales_del_sql() -> None:
    """`AC` = ALBARAN y `PROF` = PROFORMA (`compras.fn_tipo_documento`); NOTA (`NTC`)
    no lleva pendiente en las 21 obras. El umbral es el de `R-ALBARAN-ABSURDO`."""
    assert dom.SERIES_ALBARAN_PENDIENTE == ("AC", "PROF")
    assert dom.UMBRAL_IMPORTE_ABSURDO == 1e8
