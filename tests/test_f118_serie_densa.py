# tests/test_f118_serie_densa.py
"""
F-118 · La serie real densa de una partida, en dominio puro (R9, R29-R34).

El `importe_mes` real de una (obra, ámbito, partida) es su acumulado del mes
menos el del mes anterior **de su propia serie**, y esa serie no tiene huecos:
en cada cierre del ámbito la partida tiene su fila de Sigrid, o una fila de
deshacer a 0 si ha desaparecido (R29), y en cada mes de relleno arrastra el
acumulado anterior (R33). Estos tests fijan el oráculo
`etl_sigrid.domain.serie_real.serie_densa` con los casos reales de
`progress/spec_F-118.md`. Ni red ni BBDD.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.serie_real import FilaSerie, serie_densa


def _m(anio: int, mes: int) -> date:
    return date(anio, mes, 1)


def _d(valor: str | int) -> Decimal:
    return Decimal(str(valor))


def _movimientos(filas: list[FilaSerie]) -> list[tuple[date, Decimal, Decimal, str]]:
    def tipo(f: FilaSerie) -> str:
        if f.es_deshacer:
            return "deshacer"
        return "relleno" if f.es_relleno else "sigrid"

    return [(f.mes, f.acumulado, f.movimiento, tipo(f)) for f in filas]


def _suma(filas: list[FilaSerie]) -> Decimal:
    return sum((f.movimiento for f in filas), Decimal(0))


# ---------------------------------------------------------------------------
# R29 + R30 · el caso de Juan: 0709, partida 417031 (27.01 AJUSTE VENTA)
# ---------------------------------------------------------------------------


def test_f118_r29_r35_0709_417031_se_deshace_en_agosto_y_suma_cero() -> None:
    """f11 jul -58.000, sin fila en f12 (ago), f13 sep a 0.

    Hoy `stg` publica -58.000 y 0 (suma -58.000, acumulado real 0). Con la
    serie densa: -58.000 en julio, +58.000 en agosto (deshacer) y 0 en
    septiembre.
    """
    filas = serie_densa(
        {_m(2026, 7): _d(-58000), _m(2026, 9): _d(0)},
        [_m(2026, 7), _m(2026, 8), _m(2026, 9)],
    )
    assert _movimientos(filas) == [
        (_m(2026, 7), _d(-58000), _d(-58000), "sigrid"),
        (_m(2026, 8), _d(0), _d(58000), "deshacer"),
        (_m(2026, 9), _d(0), _d(0), "sigrid"),
    ]
    assert _suma(filas) == 0


def test_f118_r29_la_partida_que_sale_en_el_ultimo_cierre_se_deshace_en_el() -> None:
    filas = serie_densa(
        {_m(2024, 1): _d(100), _m(2024, 2): _d(150)},
        [_m(2024, 1), _m(2024, 2), _m(2024, 3)],
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(150), _d(50), "sigrid"),
        (_m(2024, 3), _d(0), _d(-150), "deshacer"),
    ]
    assert _suma(filas) == 0


def test_f118_r30_la_partida_que_vuelve_se_calcula_contra_lo_deshecho() -> None:
    filas = serie_densa(
        {_m(2024, 1): _d(100), _m(2024, 3): _d(120)},
        [_m(2024, 1), _m(2024, 2), _m(2024, 3)],
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(0), _d(-100), "deshacer"),
        (_m(2024, 3), _d(120), _d(120), "sigrid"),
    ]
    assert _suma(filas) == 120


def test_f118_r32_mientras_sigue_ausente_no_hay_mas_filas() -> None:
    filas = serie_densa(
        {_m(2024, 1): _d(100)},
        [_m(2024, 1), _m(2024, 2), _m(2024, 3), _m(2024, 4)],
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(0), _d(-100), "deshacer"),
    ]


def test_f118_r29_una_partida_a_cero_que_desaparece_no_deja_fila() -> None:
    """Deshacer un acumulado 0 no mueve nada: no hay fila (R32)."""
    filas = serie_densa(
        {_m(2024, 1): _d(0)},
        [_m(2024, 1), _m(2024, 2)],
    )
    assert _movimientos(filas) == [(_m(2024, 1), _d(0), _d(0), "sigrid")]


def test_f118_r9_el_primer_mes_publica_el_acumulado_entero() -> None:
    filas = serie_densa({_m(2024, 2): _d(75)}, [_m(2024, 1), _m(2024, 2)])
    assert _movimientos(filas) == [(_m(2024, 2), _d(75), _d(75), "sigrid")]


# ---------------------------------------------------------------------------
# R33 · el relleno arrastra, no deshace
# ---------------------------------------------------------------------------


def test_f118_r33_el_relleno_arrastra_el_acumulado_del_cierre_anterior() -> None:
    """ene 100; feb y mar de relleno de la fase de abril; abr 130."""
    filas = serie_densa(
        {_m(2024, 1): _d(100), _m(2024, 4): _d(130)},
        [_m(2024, 1), _m(2024, 4)],
        {_m(2024, 2): _m(2024, 4), _m(2024, 3): _m(2024, 4)},
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(100), _d(0), "relleno"),
        (_m(2024, 3), _d(100), _d(0), "relleno"),
        (_m(2024, 4), _d(130), _d(30), "sigrid"),
    ]


def test_f118_r33_en_un_mes_de_relleno_la_ausencia_no_deshace() -> None:
    """La partida falta en la fase de abril: se deshace en abril, no antes."""
    filas = serie_densa(
        {_m(2024, 1): _d(100)},
        [_m(2024, 1), _m(2024, 4)],
        {_m(2024, 2): _m(2024, 4), _m(2024, 3): _m(2024, 4)},
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(100), _d(0), "relleno"),
        (_m(2024, 3), _d(100), _d(0), "relleno"),
        (_m(2024, 4), _d(0), _d(-100), "deshacer"),
    ]


def test_f118_r33_relleno_tras_un_deshacer_arrastra_el_cero() -> None:
    """ene 100, feb deshecha; mar y abr de relleno de mayo, donde vuelve con 50.

    El relleno arrastra el acumulado YA deshecho (0), no el 100 de enero, y se
    publica porque la partida tiene movimiento en su fase generadora (D3).
    """
    filas = serie_densa(
        {_m(2024, 1): _d(100), _m(2024, 5): _d(50)},
        [_m(2024, 1), _m(2024, 2), _m(2024, 5)],
        {_m(2024, 3): _m(2024, 5), _m(2024, 4): _m(2024, 5)},
    )
    assert _movimientos(filas) == [
        (_m(2024, 1), _d(100), _d(100), "sigrid"),
        (_m(2024, 2), _d(0), _d(-100), "deshacer"),
        (_m(2024, 3), _d(0), _d(0), "relleno"),
        (_m(2024, 4), _d(0), _d(0), "relleno"),
        (_m(2024, 5), _d(50), _d(50), "sigrid"),
    ]
    assert _suma(filas) == 50


def test_f118_r13_relleno_a_cero_sin_movimiento_en_su_fase_no_se_publica() -> None:
    """Deshecha y sin volver: el relleno valdría 0 y no mueve nada (D3)."""
    filas = serie_densa(
        {_m(2024, 1): _d(100), _m(2024, 5): _d(0)},
        [_m(2024, 1), _m(2024, 2), _m(2024, 5)],
        {_m(2024, 3): _m(2024, 5), _m(2024, 4): _m(2024, 5)},
    )
    assert [f.mes for f in filas] == [_m(2024, 1), _m(2024, 2), _m(2024, 5)]


def test_f118_r13_la_partida_que_nace_en_una_fase_de_rango_lleva_su_relleno() -> None:
    """D3 de F-051: sin acumulado anterior, pero con movimiento en la fase."""
    filas = serie_densa(
        {_m(2024, 4): _d(80)},
        [_m(2024, 1), _m(2024, 4)],
        {_m(2024, 2): _m(2024, 4), _m(2024, 3): _m(2024, 4)},
    )
    assert _movimientos(filas) == [
        (_m(2024, 2), _d(0), _d(0), "relleno"),
        (_m(2024, 3), _d(0), _d(0), "relleno"),
        (_m(2024, 4), _d(80), _d(80), "sigrid"),
    ]


def test_f118_r13_un_deshacer_en_la_fase_generadora_no_publica_relleno_a_cero() -> None:
    """Fases solapadas: el relleno de enero lo genera la fase de junio, pero
    entre medias está el cierre de marzo. La partida entra en marzo y falta en
    junio: se deshace en junio. Enero valdría 0 y la partida no está en la fase
    que lo genera, así que no se publica (y no tendría fila de la que tomar
    presupuesto y precio)."""
    filas = serie_densa(
        {_m(2024, 3): _d(40)},
        [_m(2024, 3), _m(2024, 6)],
        {_m(2024, 1): _m(2024, 6), _m(2024, 4): _m(2024, 6), _m(2024, 5): _m(2024, 6)},
    )
    assert _movimientos(filas) == [
        (_m(2024, 3), _d(40), _d(40), "sigrid"),
        (_m(2024, 4), _d(40), _d(0), "relleno"),
        (_m(2024, 5), _d(40), _d(0), "relleno"),
        (_m(2024, 6), _d(0), _d(-40), "deshacer"),
    ]


# ---------------------------------------------------------------------------
# R34 y F-103 · la serie no mira el número de fase
# ---------------------------------------------------------------------------


def test_f118_r34_una_fase_sin_filas_del_ambito_no_es_cierre_de_ese_ambito() -> None:
    """0247: la f9 existe en la obra pero no tiene venta; la f10 resta a la f8.

    Los meses que recibe `serie_densa` son los cierres DEL ÁMBITO: la f9 no está
    y por eso no se deshace nada en ella.
    """
    filas = serie_densa(
        {_m(2015, 8): _d(1000), _m(2015, 10): _d(1500)},
        [_m(2015, 8), _m(2015, 10)],
    )
    assert _movimientos(filas) == [
        (_m(2015, 8), _d(1000), _d(1000), "sigrid"),
        (_m(2015, 10), _d(1500), _d(500), "sigrid"),
    ]


def test_f118_r36_hueco_de_numeracion_de_sigrid_publica_la_diferencia() -> None:
    """F-103 · 0371: Sigrid salta de la f27 a la f29. La f29 publica la diferencia.

    Acumulados de la obra (coste) en f27 y f29: 4.735.135,20 y 4.293.905,89.
    Hoy `stg` publica el acumulado entero (+4.293.905,89); con la serie densa,
    -441.229,31, lo mismo que `cierre`.
    """
    filas = serie_densa(
        {_m(2015, 1): _d("4735135.20"), _m(2015, 2): _d("4293905.89")},
        [_m(2015, 1), _m(2015, 2)],
    )
    assert filas[-1].movimiento == _d("-441229.31")


# ---------------------------------------------------------------------------
# Contrato
# ---------------------------------------------------------------------------


def test_f118_r21_la_suma_es_el_acumulado_del_ultimo_cierre_del_ambito() -> None:
    cierres = [_m(2024, m) for m in range(1, 7)]
    filas_sigrid = {_m(2024, 1): _d(10), _m(2024, 3): _d(40), _m(2024, 4): _d(35)}
    filas = serie_densa(filas_sigrid, cierres)
    assert _suma(filas) == 0  # no está en junio, el último cierre


def test_f118_r29_una_fila_de_sigrid_fuera_de_los_cierres_es_un_error() -> None:
    with pytest.raises(ValueError, match="no es un cierre"):
        serie_densa({_m(2024, 2): _d(1)}, [_m(2024, 1)])


def test_f118_r11_un_mes_de_relleno_que_es_cierre_es_un_error() -> None:
    with pytest.raises(ValueError, match="relleno"):
        serie_densa({_m(2024, 1): _d(1)}, [_m(2024, 1)], {_m(2024, 1): _m(2024, 1)})


def test_f118_r14_un_relleno_debe_ir_antes_de_su_cierre_generador() -> None:
    with pytest.raises(ValueError, match="generador"):
        serie_densa(
            {_m(2024, 1): _d(1)}, [_m(2024, 1)], {_m(2024, 2): _m(2024, 1)}
        )


def test_f118_la_fila_de_la_serie_es_inmutable() -> None:
    fila = serie_densa({_m(2024, 1): _d(1)}, [_m(2024, 1)])[0]
    with pytest.raises(AttributeError):
        fila.acumulado = _d(2)  # type: ignore[misc]
