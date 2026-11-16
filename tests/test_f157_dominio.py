# tests/test_f157_dominio.py
"""
F-157 · El oráculo de la explosión del `planif` (R5, R6, R8-R10).

`etl_sigrid/domain/planif.py::explotar_planif` repite, posición a posición, la
regla del master de `sql/stg/08_plan_mensual.sql` que ahora aplica también
`stg.fn_explotar_planif` a la fase 0. Los casos son los que ese fichero
documenta (validados al céntimo contra Sigrid) y los de la 0726 que motivan la
feature. Sin red ni BBDD.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from etl_sigrid.domain.planif import PosicionPlanif, conservar, explotar_planif


def _tri(texto: str | None) -> list[tuple[int, D, D]]:
    return [(p.posicion_mes, p.pct_acumulado, p.pct_mes) for p in explotar_planif(texto)]


def _conservadas(texto: str) -> list[tuple[int, D, D]]:
    return [
        (p.posicion_mes, p.pct_acumulado, p.pct_mes)
        for p in explotar_planif(texto)
        if conservar(p)
    ]


# --- R9 · los casos documentados en 08_plan_mensual.sql --------------------


def test_f157_r9_0726_arranque_tardio_y_cierre_en_1() -> None:
    """`0|0|0|0|0.15|0.85|1`: cuatro meses de pre-arranque que no se publican."""
    assert _conservadas("0|0|0|0|0.15|0.85|1") == [
        (5, D("0.15"), D("0.15")),
        (6, D("0.85"), D("0.70")),
        (7, D("1"), D("0.15")),
    ]


def test_f157_r9_0726_dos_meses() -> None:
    assert _conservadas("0.3439|1") == [
        (1, D("0.3439"), D("0.3439")),
        (2, D("1"), D("0.6561")),
    ]


def test_f157_r9_0696_cero_intermedio_es_estorno() -> None:
    """P5.19.04.01: los ceros con un positivo DESPUÉS bajan a 0 (estorno)."""
    filas = _tri("0.501|0.501|0|0|0.2|1")
    assert filas == [
        (1, D("0.501"), D("0.501")),
        (2, D("0.501"), D("0")),
        (3, D("0"), D("-0.501")),
        (4, D("0"), D("0")),
        (5, D("0.2"), D("0.2")),
        (6, D("1"), D("0.8")),
    ]


def test_f157_r9_0677_cero_final_arrastra_el_ultimo_positivo() -> None:
    """40.04.04 `…|0.93|0|0`: se queda en 0,93, no se estorna."""
    assert _tri("0.5|0.93|0|0") == [
        (1, D("0.5"), D("0.5")),
        (2, D("0.93"), D("0.43")),
        (3, D("0.93"), D("0")),
        (4, D("0.93"), D("0")),
    ]


def test_f157_r9_p4_03_06_sobrepaso_arrastra_el_ultimo_no_el_maximo() -> None:
    """Último positivo 1,0 con máximo 1,054: el arrastre es 1,0."""
    filas = _tri("0.5|1.054|1.0|0")
    assert filas[-1] == (4, D("1.0"), D("0"))
    assert filas[2] == (3, D("1.0"), D("-0.054"))


def test_f157_r9_posiciones_vacias_al_final_quedan_fuera() -> None:
    assert _tri("0.5|1||") == [(1, D("0.5"), D("0.5")), (2, D("1"), D("0.5"))]


def test_f157_r5_un_hueco_intermedio_no_renumera() -> None:
    """Como `WITH ORDINALITY` + `length(trim(v)) > 0`: la posición 2 no existe."""
    assert _tri("0.5| |1") == [(1, D("0.5"), D("0.5")), (3, D("1"), D("0.5"))]


# --- R5 · bordes de la regla -----------------------------------------------


def test_f157_r5_no_numerico_cuenta_como_cero() -> None:
    assert _tri("0.5|x|1") == [
        (1, D("0.5"), D("0.5")),
        (2, D("0"), D("-0.5")),
        (3, D("1"), D("1")),
    ]
    # Al final, arrastra el último positivo como un 0 final.
    assert _tri("0.5|x")[-1] == (2, D("0.5"), D("0"))


def test_f157_r5_coma_decimal() -> None:
    assert _tri("0,25|1") == [(1, D("0.25"), D("0.25")), (2, D("1"), D("0.75"))]


def test_f157_r5_negativo_se_trata_como_no_positivo() -> None:
    assert _tri("0.5|-0.2|1")[1] == (2, D("0"), D("-0.5"))
    assert _tri("0.5|-0.2")[1] == (2, D("0.5"), D("0"))
    assert _tri("-0.2|0.5")[0] == (1, D("0"), D("0"))


def test_f157_r5_cero_final_con_negativo_despues_arrastra() -> None:
    """`max_posterior` del master es el MÁXIMO de lo que sigue, no si existe."""
    assert _tri("0.5|0|-0.1") == [
        (1, D("0.5"), D("0.5")),
        (2, D("0.5"), D("0")),
        (3, D("0.5"), D("0")),
    ]


def test_f157_r5_seis_decimales_como_numeric_18_6() -> None:
    assert _tri("0.1234567")[0][1] == D("0.123457")


def test_f157_r5_espacio_alrededor_no_es_numero() -> None:
    """El regex del master se aplica al valor sin recortar: ` 1` no casa."""
    assert _tri("0.5| 1")[1] == (2, D("0.5"), D("0"))


# --- R10 · sin reparto no hay filas ----------------------------------------


@pytest.mark.parametrize("texto", [None, "", "   ", "|", "||"])
def test_f157_r10_sin_planif_no_hay_posiciones(texto: str | None) -> None:
    assert explotar_planif(texto) == []


def test_f157_r10_todo_a_cero_no_conserva_nada() -> None:
    assert _tri("0|0|0") == [(1, D("0"), D("0")), (2, D("0"), D("0")), (3, D("0"), D("0"))]
    assert _conservadas("0|0|0") == []


# --- R6 · el descarte ------------------------------------------------------


def test_f157_r6_mas_de_250_por_ciento_se_descarta_pero_cuenta_para_el_siguiente() -> None:
    """El master calcula el LAG ANTES del `WHERE`: el mes siguiente baja 2."""
    assert _conservadas("1|3|1") == [(1, D("1"), D("1")), (3, D("1"), D("-2"))]


def test_f157_r6_conservar() -> None:
    assert conservar(PosicionPlanif(1, D("0"), D("-0.5")))
    assert conservar(PosicionPlanif(1, D("2.5"), D("0")))
    assert not conservar(PosicionPlanif(1, D("0"), D("0")))
    assert not conservar(PosicionPlanif(1, D("2.500001"), D("1")))


def test_f157_r8_posicion_es_inmutable() -> None:
    p = PosicionPlanif(1, D("1"), D("1"))
    with pytest.raises(AttributeError):
        p.pct_mes = D("0")  # type: ignore[misc]
