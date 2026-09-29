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
from decimal import Decimal

import pytest

from etl_sigrid.domain.cierres import Cierre, plan_de_cierres
from etl_sigrid.domain.mes_fase import (
    FaseReal,
    mes_de_fase,
    meses_relleno,
    parse_mes_fase,
)

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


# ---------------------------------------------------------------------------
# R10-R14 · el relleno de las fases de rango (F-051 T3)
# ---------------------------------------------------------------------------

def _m(anio: int, mes: int) -> date:
    return date(anio, mes, 1)


def test_f118_r10_relleno_desde_el_mes_de_inicio_hasta_el_anterior_al_texto() -> None:
    """0650 f20 «JUNIO 24», del 01-02 al 30-06-2024: relleno feb-may."""
    fases = [
        FaseReal(19, _m(2024, 1), date(2024, 1, 1), date(2024, 1, 31)),
        FaseReal(20, _m(2024, 6), date(2024, 2, 1), date(2024, 6, 30)),
    ]
    assert meses_relleno(fases) == {
        20: (_m(2024, 2), _m(2024, 3), _m(2024, 4), _m(2024, 5)),
    }


def test_f118_r11_el_relleno_no_pisa_un_mes_con_cierre_propio() -> None:
    """Un cierre vigente de otra fase en julio (aunque valga 0) no se rellena."""
    fases = [
        FaseReal(27, _m(2025, 7), date(2025, 7, 1), date(2025, 7, 31)),
        FaseReal(28, _m(2025, 12), date(2025, 5, 1), date(2025, 12, 31)),
    ]
    assert meses_relleno(fases) == {
        28: (_m(2025, 5), _m(2025, 6), _m(2025, 8), _m(2025, 9), _m(2025, 10),
             _m(2025, 11)),
    }


def test_f118_r14_texto_en_el_primer_mes_no_rellena_nada() -> None:
    fases = [FaseReal(3, _m(2024, 6), date(2024, 6, 16), date(2024, 8, 15))]
    assert meses_relleno(fases) == {}


def test_f118_r14_texto_intermedio_rellena_hasta_el_texto_y_nada_despues() -> None:
    fases = [FaseReal(3, _m(2024, 7), date(2024, 6, 1), date(2024, 9, 30))]
    assert meses_relleno(fases) == {3: (_m(2024, 6),)}


def test_f118_r10_una_fase_de_un_mes_no_rellena() -> None:
    """0440 f3: el texto la lleva a mayo, pero sus fechas son de un solo mes."""
    fases = [FaseReal(3, _m(2015, 5), date(2015, 3, 1), date(2015, 3, 31))]
    assert meses_relleno(fases) == {}


def test_f118_r10_texto_antes_de_las_fechas_no_rellena() -> None:
    """0337 f1 «Marzo 2011», de oct-2011 a mar-2012: manda el texto, sin relleno."""
    fases = [FaseReal(1, _m(2011, 3), date(2011, 10, 1), date(2012, 3, 31))]
    assert meses_relleno(fases) == {}


def test_f118_r10_sin_fecha_fin_no_hay_rango() -> None:
    fases = [FaseReal(4, _m(2012, 6), date(2012, 1, 1), None)]
    assert meses_relleno(fases) == {}


def test_f118_r3_r10_0571_dos_fases_de_rango_seguidas() -> None:
    """0571: f21 «Enero 2020-Abril 2020» (ene-abr) y f22 «Agosto 2020» (may-ago)."""
    fases = [
        FaseReal(21, _m(2020, 4), date(2020, 1, 1), date(2020, 4, 30)),
        FaseReal(22, _m(2020, 8), date(2020, 5, 1), date(2020, 8, 31)),
    ]
    assert meses_relleno(fases) == {
        21: (_m(2020, 1), _m(2020, 2), _m(2020, 3)),
        22: (_m(2020, 5), _m(2020, 6), _m(2020, 7)),
    }


def test_f118_r11_ningun_mes_de_relleno_se_repite_entre_dos_fases() -> None:
    """Dos fases de rango solapadas: el mes lo rellena la de texto más cercano.

    f5 «Marzo» (ene-mar) y f6 «Junio» (feb-jun) quieren las dos febrero. Lo
    genera f5, cuyo cierre es el siguiente; f6 se queda con abril y mayo.
    """
    fases = [
        FaseReal(5, _m(2019, 3), date(2019, 1, 1), date(2019, 3, 31)),
        FaseReal(6, _m(2019, 6), date(2019, 2, 1), date(2019, 6, 30)),
    ]
    relleno = meses_relleno(fases)
    assert relleno == {
        5: (_m(2019, 1), _m(2019, 2)),
        6: (_m(2019, 4), _m(2019, 5)),
    }
    todos = [mes for meses in relleno.values() for mes in meses]
    assert len(todos) == len(set(todos))


def _vigentes(fases: list[FaseReal], acumulados: dict[int, int]) -> list[FaseReal]:
    plan = plan_de_cierres(
        [Cierre(f.numero_fase, f.anio_mes, Decimal(acumulados[f.numero_fase]))
         for f in fases]
    )
    vivas = set(plan.vigente_por_mes.values())
    return [f for f in fases if f.numero_fase in vivas]


def test_f118_r8_r11_la_fase_que_pierde_el_mes_no_genera_relleno() -> None:
    """R8 (F-042 sobre el mes del texto) antes que R10: la perdedora no rellena.

    f5 de rango (ene-mar) y f6 de un mes comparten «Marzo». Con las dos a
    distinto de cero manda f6, que no es de rango: enero y febrero no se
    rellenan.
    """
    fases = [
        FaseReal(5, _m(2019, 3), date(2019, 1, 1), date(2019, 3, 31)),
        FaseReal(6, _m(2019, 3), date(2019, 3, 1), date(2019, 3, 31)),
    ]
    assert meses_relleno(_vigentes(fases, {5: 100, 6: 200})) == {}


def test_f118_r8_r11_si_la_de_rango_gana_el_mes_rellena_lo_suyo() -> None:
    """Misma pareja con f6 a cero: manda f5 y rellena enero y febrero."""
    fases = [
        FaseReal(5, _m(2019, 3), date(2019, 1, 1), date(2019, 3, 31)),
        FaseReal(6, _m(2019, 3), date(2019, 3, 1), date(2019, 3, 31)),
    ]
    assert meses_relleno(_vigentes(fases, {5: 100, 6: 0})) == {
        5: (_m(2019, 1), _m(2019, 2)),
    }


def test_f118_r11_meses_relleno_rechaza_dos_fases_con_el_mismo_mes() -> None:
    """Recibir dos vigentes del mismo mes es un error de quien llama (R8 antes)."""
    fases = [
        FaseReal(5, _m(2019, 3), date(2019, 1, 1), date(2019, 3, 31)),
        FaseReal(6, _m(2019, 3), date(2019, 3, 1), date(2019, 3, 31)),
    ]
    with pytest.raises(ValueError, match="mismo mes"):
        meses_relleno(fases)
