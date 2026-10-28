# tests/test_f150_coeficiente.py
"""
F-150 · El coeficiente de VENTA de cada partida (R9, D3, D4) y los importes que
salen de él (R14, R20), en el dominio.

Manda el del CONTRATO de la partida; sin él, el del master: certificación
(ámbito 9) si tiene importe y, si no, venta (ámbito 11); sin ninguno, `SIN`
(y el SQL falla si esa partida tiene pendiente, D6). El importe con
coeficientes se reparte en el tiempo con el MISMO `repartir_pendiente` de
F-140, al céntimo. Dominio puro: sin BBDD.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.proyeccion_caja import (
    AMBITO_COEFICIENTE,
    FUENTES_COEFICIENTE,
    FUENTES_DATO_CONTRATO,
    MOTIVO_H12_FICHA,
    coeficiente_venta,
    importe_con_coeficiente,
    importe_por_porcentaje,
    repartir_pendiente,
)

D = Decimal


# ---------------------------------------------------------------------------
# R9 · los literales
# ---------------------------------------------------------------------------


def test_f150_r9_las_fuentes_y_sus_ambitos() -> None:
    assert FUENTES_COEFICIENTE == ("CONTRATO", "MASTER_CERT", "MASTER_VENTA", "SIN")
    assert AMBITO_COEFICIENTE == {"MASTER_CERT": 9, "MASTER_VENTA": 11}
    assert FUENTES_DATO_CONTRATO == ("CONTRATO", "SIN")
    assert MOTIVO_H12_FICHA == "Ficha de la obra (tipo de IVA)"


# ---------------------------------------------------------------------------
# R9 · el orden: contrato > certificación > venta > SIN
# ---------------------------------------------------------------------------


def test_f150_r9_manda_el_contrato_aunque_haya_master() -> None:
    assert coeficiente_venta(D("1.19"), D("100"), D("150"), D("100"), D("130")) == (
        D("1.19"), "CONTRATO",
    )


def test_f150_r9_sin_contrato_el_de_certificacion() -> None:
    assert coeficiente_venta(None, D("100"), D("119"), D("100"), D("130")) == (
        D("1.190000"), "MASTER_CERT",
    )


@pytest.mark.parametrize("importe_cert", [None, D("0"), 0])
def test_f150_r9_certificacion_sin_importe_cae_a_venta(importe_cert) -> None:
    assert coeficiente_venta(None, importe_cert, D("119"), D("200"), D("260")) == (
        D("1.300000"), "MASTER_VENTA",
    )


@pytest.mark.parametrize("importe_venta", [None, D("0")])
def test_f150_r9_sin_nada_es_sin(importe_venta) -> None:
    assert coeficiente_venta(None, None, None, importe_venta, D("5")) == (None, "SIN")


def test_f150_r9_oficial_ausente_es_el_importe() -> None:
    assert coeficiente_venta(None, D("100"), None, None, None) == (D("1.000000"), "MASTER_CERT")
    assert coeficiente_venta(None, None, None, D("100"), None) == (D("1.000000"), "MASTER_VENTA")


def test_f150_r9_redondea_a_seis_decimales_la_mitad_hacia_arriba() -> None:
    assert coeficiente_venta(None, D("3"), D("4"), None, None) == (D("1.333333"), "MASTER_CERT")
    # 1,0000005 -> 1,000001 (HALF_UP); en banca sería 1,000000
    assert coeficiente_venta(None, D("2000000"), D("2000001"), None, None)[0] == D("1.000001")


def test_f150_r9_un_importe_negativo_tambien_vale() -> None:
    """Partidas en negativo (abonos): el cociente sigue siendo el coeficiente."""
    assert coeficiente_venta(None, D("-100"), D("-119"), None, None) == (D("1.190000"), "MASTER_CERT")


# ---------------------------------------------------------------------------
# R11 / R20 · los importes, redondeados al céntimo
# ---------------------------------------------------------------------------


def test_f150_r11_importe_con_coeficiente() -> None:
    assert importe_con_coeficiente(D("1000.00"), D("1.19")) == D("1190.00")
    assert importe_con_coeficiente(D("0.05"), D("1.1")) == D("0.06"), "0,055 -> 0,06 (HALF_UP)"
    assert importe_con_coeficiente(D("100"), None) is None


def test_f150_r20_importe_por_porcentaje() -> None:
    assert importe_por_porcentaje(D("1190.00"), D("21.0000")) == D("249.90")
    assert importe_por_porcentaje(D("0.50"), D("1")) == D("0.01"), "0,005 -> 0,01 (HALF_UP)"
    assert importe_por_porcentaje(D("1190.00"), D("0")) == D("0.00")
    assert importe_por_porcentaje(D("1190.00"), None) is None


# ---------------------------------------------------------------------------
# R14 · el reparto en el tiempo con coeficientes: el mismo de F-140
# ---------------------------------------------------------------------------

PERFIL = [(date(2026, 11, 1), D("100")), (date(2026, 12, 1), D("200")),
          (date(2027, 1, 1), D("0")), (date(2027, 2, 1), D("33"))]


def test_f150_r14_el_reparto_con_coeficientes_suma_exacto() -> None:
    pendiente = D("1000.00")
    con = importe_con_coeficiente(pendiente, D("1.237900"))
    reparto = repartir_pendiente(con, PERFIL, date(2026, 11, 1))
    assert sum(i for _m, i, _r in reparto) == con == D("1237.90")
    assert [m for m, _i, _r in reparto] == [date(2026, 11, 1), date(2026, 12, 1), date(2027, 2, 1)]
    # cada mes es el de F-140 con el pendiente con coeficientes: 1237,90 x 100/333 ...
    assert [i for _m, i, _r in reparto] == [D("371.74"), D("743.48"), D("122.68")]


def test_f150_r14_el_reparto_sin_perfil_va_entero_al_primer_mes() -> None:
    con = importe_con_coeficiente(D("10.00"), D("1.19"))
    assert repartir_pendiente(con, [], date(2026, 11, 1)) == [(date(2026, 11, 1), D("11.90"), True)]


def test_f150_r14_el_cociente_por_mes_no_es_el_coeficiente_de_la_partida_al_centimo() -> None:
    """Por eso `devengo_pendiente_obra_mes` publica el COCIENTE a 6 decimales."""
    con = importe_con_coeficiente(D("1000.00"), D("1.237900"))
    sin = repartir_pendiente(D("1000.00"), PERFIL, date(2026, 11, 1))
    con_rep = repartir_pendiente(con, PERFIL, date(2026, 11, 1))
    cocientes = [(c / s).quantize(D("0.000001")) for (_m, c, _r), (_n, s, _q) in zip(con_rep, sin, strict=True)]
    assert cocientes[0] != D("1.237900") or cocientes[-1] != D("1.237900")
