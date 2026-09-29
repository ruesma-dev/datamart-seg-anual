# tests/test_f118_regla_mes.py
"""
F-118 (F-051 absorbida) · La regla del mes de un cierre real, en dominio puro.

El mes de una fila real lo da el TEXTO de su fase (`obrfas.res`), no el
`ano`/`mes` que archiva Sigrid. Estos tests fijan el oráculo
`etl_sigrid.domain.mes_fase`, contra el que se contrasta el SQL de
`stg.fn_parse_mes_texto` y `stg.fn_mes_de_fase` (`check-mes-fase`).

Los textos son los reales de `progress/spec_F-051.md` §3: los que el parser de
`cierre` no leía (año de dos cifras, punto de millar, rangos) y los testigos
que la spec cita por obra y fase. Dominio puro: ni red ni BBDD.
"""

from __future__ import annotations

from datetime import date

import pytest

from etl_sigrid.domain.mes_fase import mes_de_fase, parse_mes_fase

# ---------------------------------------------------------------------------
# R2-R4 · el parser del texto
# ---------------------------------------------------------------------------

#: (texto real, mes esperado). Los de un solo mes dan lo mismo que el parser de
#: `cierre`; los demás son los que D4 cambia.
TEXTOS = (
    # un solo mes: igual que hoy
    ("Septiembre 2023", date(2023, 9, 1)),
    ("Octubre 2025", date(2025, 10, 1)),
    ("sep-23", date(2023, 9, 1)),
    ("Febrero 2026", date(2026, 2, 1)),  # 0692 f14
    ("Mayo 2015", date(2015, 5, 1)),  # 0440 f3
    ("Diciembre-24", date(2024, 12, 1)),  # 0673 f8
    ("Agosto 2026", date(2026, 8, 1)),  # 0709 f12
    # R4 · año de dos cifras 00-19 tras un mes
    ("Mayo-17", date(2017, 5, 1)),  # 0444 f21
    ("Abril-19", date(2019, 4, 1)),
    ("DICIEMBRE-13", date(2013, 12, 1)),
    ("DICIEMBRE-19", date(2019, 12, 1)),
    ("AGOSTO17", date(2017, 8, 1)),  # sin separador entre mes y año
    ("ENERO-09", date(2009, 1, 1)),
    # R4 · punto de millar
    ("Abril 2.013", date(2013, 4, 1)),
    ("AGOSTO 2.010", date(2010, 8, 1)),
    # R3 · rango: el ÚLTIMO mes con el último año visto
    ("Enero 2020-Abril 2020", date(2020, 4, 1)),  # 0571 f21
    ("Mayo-Julio 2012", date(2012, 7, 1)),
    ("Diciembre 2014 - Enero 2015", date(2015, 1, 1)),
    ("Enero-Febrero 2011", date(2011, 2, 1)),
    ("Junio-Julio-1 2017", date(2017, 7, 1)),
    ("DICIEMBRE 09 A FEBRERO 2010", date(2010, 2, 1)),  # 0249 f6
)

#: Textos que NO se leen: pasan a la cascada de fechas (R6).
ILEGIBLES = (
    None,
    "",
    "   ",
    "AÑO 2012",
    "2012",
    "POSTVENTA 2009",
    "LEVANTAMIENTO",
    "Dciiembre 2018",
    "SEPTIEMBRE-DICIEMBRE",
)


@pytest.mark.parametrize(("texto", "esperado"), TEXTOS)
def test_f118_r3_r4_parse_lee_el_texto_real(texto: str, esperado: date) -> None:
    assert parse_mes_fase(texto) == esperado


@pytest.mark.parametrize("texto", ILEGIBLES)
def test_f118_r6_parse_devuelve_none_si_no_hay_mes_y_anio(texto: str | None) -> None:
    assert parse_mes_fase(texto) is None


def test_f118_r3_parse_un_rango_sin_anio_final_toma_el_ultimo_anio_visto() -> None:
    """«Enero 2020 - Marzo» → marzo de 2020: el mes cambia y el año se queda."""
    assert parse_mes_fase("Enero 2020 - Marzo") == date(2020, 3, 1)


def test_f118_r4_parse_un_numero_suelto_sin_mes_previo_es_el_mes() -> None:
    """La lógica de hoy se conserva: un 1-12 sin mes delante es el mes."""
    assert parse_mes_fase("03/2021") == date(2021, 3, 1)


def test_f118_r4_parse_dos_cifras_00_19_sin_mes_previo_no_son_anio() -> None:
    """«15 2021» no tiene mes: 15 no es mes (13+) ni año (no hay mes delante)."""
    assert parse_mes_fase("15 2021") is None


def test_f118_r4_parse_un_digito_tras_el_mes_no_es_anio() -> None:
    """«Junio-Julio-1» sin año de cuatro cifras no inventa el 2001."""
    assert parse_mes_fase("Junio-Julio-1") is None


# ---------------------------------------------------------------------------
# R2 + R6 · la cascada: texto → fecha fin → fecha inicio → mes archivado
# ---------------------------------------------------------------------------


def test_f118_r2_manda_el_texto_aunque_caiga_fuera_de_las_fechas() -> None:
    """0673 f8 «Diciembre-24» con fechas de marzo de 2024 → diciembre."""
    assert mes_de_fase(
        date(2024, 3, 1), "Diciembre-24", date(2024, 3, 31)
    ) == date(2024, 12, 1)


def test_f118_r2_manda_el_texto_en_una_fase_de_un_mes() -> None:
    """0440 f3 «Mayo 2015» archivada en marzo → mayo."""
    assert mes_de_fase(
        date(2015, 3, 1), "Mayo 2015", date(2015, 3, 31), date(2015, 3, 1)
    ) == date(2015, 5, 1)


def test_f118_r2_con_fechas_invertidas_manda_el_texto() -> None:
    """0444 f21 «Mayo-17», del 01-12-2017 al 31-05-2017."""
    assert mes_de_fase(
        date(2017, 12, 1), "Mayo-17", date(2017, 5, 31)
    ) == date(2017, 5, 1)


def test_f118_r6_texto_ilegible_manda_la_fecha_fin() -> None:
    assert mes_de_fase(
        date(2012, 1, 16), "LEVANTAMIENTO", date(2012, 6, 30), date(2012, 1, 1)
    ) == date(2012, 6, 1)


def test_f118_r6_sin_fecha_fin_manda_la_fecha_inicio() -> None:
    assert mes_de_fase(
        date(2012, 1, 16), "POSTVENTA 2009", None, date(2011, 12, 1)
    ) == date(2012, 1, 1)


def test_f118_r6_sin_fechas_manda_el_mes_archivado() -> None:
    assert mes_de_fase(None, None, None, date(2011, 12, 15)) == date(2011, 12, 1)


def test_f118_r6_sin_nada_no_hay_mes() -> None:
    assert mes_de_fase(None, "LEVANTAMIENTO") is None


def test_f118_r7_una_fase_normal_da_su_mes() -> None:
    """0709 f12 «Agosto 2026», 01-08 a 31-08: agosto, como hoy."""
    assert mes_de_fase(
        date(2026, 8, 1), "Agosto 2026", date(2026, 8, 31), date(2026, 8, 1)
    ) == date(2026, 8, 1)
