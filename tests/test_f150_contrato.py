# tests/test_f150_contrato.py
"""
F-150 · Los coeficientes del CONTRATO con el cliente (R7, N1, N10) y su IVA
(R18, N2), en el dominio.

`raw.obrctr.coestr` es una LÍNEA por concepto (`\\r\\n`), cada una
`CODIGO|etiqueta|valor||base`. Se lee POR CÓDIGO: GG y BI se SUMAN, la baja de
adjudicación va en CASCADA sobre el subtotal de contrata y las retenciones
`RET*` no son coeficiente (van aparte). Lo que no se entiende falla cerrado:
la partida cae al coeficiente del master. Las formas de abajo son las REALES de
`progress/impl_F-150.md` §1.2, medidas en Azure el 2026-10-27.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from etl_sigrid.domain.proyeccion_caja import (
    CLASE_POR_CODIGO,
    REGEX_PORCENTAJE_COEF,
    SEPARADOR_CAMPOS,
    SEPARADOR_LINEAS,
    CoeficientesContrato,
    factor_coeficientes,
    leer_coeficientes_contrato,
    porcentaje_iva,
)

D = Decimal

#: La forma más frecuente (7.015 partidas VENTA de las 21 obras).
GG_BI = "COEF_RECGG|Gastos Generales|13||\r\nCOEF_RECBI|Beneficio Industrial|6||\r\n"
#: La de la base `TOTAL EJECUCION CONTRATA` (1.071 partidas), literal.
GG_BI_BASE = ("COEF_RECGG|Gastos Generales|13||\r\n"
              "COEF_RECBI|Beneficio Industrial|6||TOTAL EJECUCION CONTRATA\r\n")
#: La combinada (972 partidas): código de GG, etiqueta de los dos.
COMBINADA = "COEF_RECGG|Gastos Generales+Beneficio Industrial|23.79||\r\n"
#: La baja en cascada (8 contratos, fuera de las 21 obras).
CON_BAJA = ("COEF_RECGG|Gastos Generales|13||\r\n"
            "COEF_RECBI|Beneficio Industrial|6||TOTAL EJECUCIÓN POR CONTRATA\r\n"
            "COEF_DESADJ|Coeficiente (Baja) de Adjudicación|-12.77||TOTAL ADJUDICACIÓN\r\n")
#: Una retención dentro de `coestr` (35 contratos con `RETN`).
CON_RETN = ("COEF_RECGG|Gastos Generales|13||\r\nCOEF_RECBI|Beneficio Industrial|6||\r\n"
            "RETN|Retención garantía 5% (sobre base imponible)|5||\r\n")


# ---------------------------------------------------------------------------
# R7 · los literales (el SQL de `00_setup.sql` lleva los mismos)
# ---------------------------------------------------------------------------


def test_f150_r7_los_literales_de_la_gramatica() -> None:
    assert SEPARADOR_LINEAS == r"\r?\n"
    assert SEPARADOR_CAMPOS == "|"
    assert REGEX_PORCENTAJE_COEF == r"^-?[0-9]+(\.[0-9]+)?$"
    assert CLASE_POR_CODIGO == {
        "COEF_RECGG": "gg", "COEF_RECBI": "bi", "COEF_RECCC": "otros",
        "COEF_RECSYS": "otros", "COEF_DESADJ": "baja", "RETN": "retencion",
        "RETESP": "retencion", "RETNT": "retencion",
    }
    assert CoeficientesContrato._fields == ("gg", "bi", "otros", "baja", "retencion", "reconocido")


# ---------------------------------------------------------------------------
# R7 · las formas reales
# ---------------------------------------------------------------------------


def test_f150_r7_gg_y_bi_se_suman_y_dan_1_19() -> None:
    c = leer_coeficientes_contrato(GG_BI)
    assert c == CoeficientesContrato(D("13"), D("6"), None, None, None, True)
    assert factor_coeficientes(c) == D("1.190000")


def test_f150_r7_la_base_del_ultimo_campo_no_estorba() -> None:
    c = leer_coeficientes_contrato(GG_BI_BASE)
    assert (c.gg, c.bi, c.reconocido) == (D("13"), D("6"), True)
    assert factor_coeficientes(c) == D("1.19")


def test_f150_r7_la_combinada_va_a_gg_por_su_codigo() -> None:
    c = leer_coeficientes_contrato(COMBINADA)
    assert c == CoeficientesContrato(D("23.79"), None, None, None, None, True)
    assert factor_coeficientes(c) == D("1.237900")


def test_f150_r7_la_baja_va_en_cascada_sobre_el_subtotal_de_contrata() -> None:
    c = leer_coeficientes_contrato(CON_BAJA)
    assert c.baja == D("-12.77") and c.reconocido
    # 1,19 x (1 - 0,1277) = 1,038037; sumada daría 1,0623
    assert factor_coeficientes(c) == D("1.038037")


def test_f150_r7_la_retencion_no_es_coeficiente() -> None:
    c = leer_coeficientes_contrato(CON_RETN)
    assert c.retencion == D("5") and c.reconocido
    assert factor_coeficientes(c) == D("1.19"), "la retención del 5 % no suma al coeficiente"


def test_f150_r7_solo_retencion_es_reconocido_pero_sin_factor() -> None:
    c = leer_coeficientes_contrato("RETN|Retención garantía 5%|5||\r\n")
    assert c == CoeficientesContrato(None, None, None, None, D("5"), True)
    assert factor_coeficientes(c) is None, "sin coeficiente, la partida cae al master"


def test_f150_r7_control_de_calidad_y_seguridad_suman_en_otros() -> None:
    c = leer_coeficientes_contrato(
        "COEF_RECGG|GG|13||\r\nCOEF_RECCC|Control de calidad|1||\r\n"
        "COEF_RECSYS|Seguridad y salud|1.5||\r\n"
    )
    assert (c.gg, c.otros) == (D("13"), D("2.5"))
    assert factor_coeficientes(c) == D("1.155000")


def test_f150_r7_solo_bi_con_otra_etiqueta() -> None:
    """`COEF_RECBI|Mortero|7` (4 partidas): manda el código, no la etiqueta."""
    c = leer_coeficientes_contrato("COEF_RECBI|Mortero|7||\r\n")
    assert c == CoeficientesContrato(None, D("7"), None, None, None, True)
    assert factor_coeficientes(c) == D("1.07")


def test_f150_r7_dos_lineas_de_la_misma_clase_se_suman() -> None:
    c = leer_coeficientes_contrato("RETN|a|5||\nRETESP|b|2.5||\n")
    assert c.retencion == D("7.5")


@pytest.mark.parametrize("texto", [
    "COEF_RECGG|Gastos Generales|13||\nCOEF_RECBI|Beneficio Industrial|6||\n",
    "COEF_RECGG|Gastos Generales|13||\r\nCOEF_RECBI|Beneficio Industrial|6||",
    "  COEF_RECGG|Gastos Generales|13||  \r\n\r\n\r\nCOEF_RECBI|Beneficio Industrial| 6 ||\r\n",
])
def test_f150_r7_saltos_de_linea_y_blancos(texto: str) -> None:
    c = leer_coeficientes_contrato(texto)
    assert (c.gg, c.bi, c.reconocido) == (D("13"), D("6"), True)


# ---------------------------------------------------------------------------
# R7 · sin dato y fallo cerrado
# ---------------------------------------------------------------------------

_SIN_NADA = CoeficientesContrato(None, None, None, None, None, False)


@pytest.mark.parametrize("texto", [None, "", "   ", "\r\n", "\r\n  \r\n"])
def test_f150_r7_vacio_o_null_es_sin_dato(texto) -> None:
    assert leer_coeficientes_contrato(texto) == _SIN_NADA
    assert factor_coeficientes(leer_coeficientes_contrato(texto)) is None


@pytest.mark.parametrize("texto", [
    "COEF_NUEVO|Algo|3||\r\n",
    "COEF_RECGG|Gastos Generales|13||\r\nCOEF_NUEVO|Algo|3||\r\n",
    "coef_recgg|Gastos Generales|13||\r\n",
    "COEF_RECGG|Gastos Generales|13%||\r\n",
    "COEF_RECGG|Gastos Generales|13,5||\r\n",
    "COEF_RECGG|Gastos Generales|||\r\n",
    "COEF_RECGG|Gastos Generales\r\n",
    "COEF_RECGG|Gastos Generales|.5||\r\n",
    "COEF_RECGG|Gastos Generales|5.||\r\n",
    "COEF_RECGG|Gastos Generales|+5||\r\n",
    "COEF_RECGG|Gastos Generales|1e2||\r\n",
    "13 6",
])
def test_f150_r7_codigo_desconocido_o_valor_no_numerico_no_se_reconoce(texto: str) -> None:
    """Falla cerrado: ni un trozo de lo que sí se entiende."""
    assert leer_coeficientes_contrato(texto) == _SIN_NADA
    assert factor_coeficientes(leer_coeficientes_contrato(texto)) is None


def test_f150_r7_el_factor_redondea_a_seis_decimales_la_mitad_hacia_arriba() -> None:
    # 1,1 x (1 - 0,000005) = 1,0999945 -> 1,099995 (HALF_UP)
    c = CoeficientesContrato(D("10"), None, None, D("-0.0005"), None, True)
    assert factor_coeficientes(c) == D("1.099995")


def test_f150_r7_no_reconocido_no_da_factor_aunque_traiga_numeros() -> None:
    assert factor_coeficientes(CoeficientesContrato(D("13"), D("6"), None, None, None, False)) is None


def test_f150_r7_solo_baja_es_un_factor() -> None:
    c = CoeficientesContrato(None, None, None, D("-10"), None, True)
    assert factor_coeficientes(c) == D("0.9")


# ---------------------------------------------------------------------------
# R18 · el porcentaje de IVA del catálogo `iva` (en tanto por uno)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("fraccion", "esperado"), [
    (D("0.21"), D("21.0000")),
    (D("0.1"), D("10.0000")),
    (D("0"), D("0.0000")),
    (D("0.123456"), D("12.3456")),
    (D("0.0000005"), D("0.0001")),
    (0.21, D("21.0000")),
])
def test_f150_r18_porcentaje_iva(fraccion, esperado) -> None:
    resultado = porcentaje_iva(fraccion)
    assert resultado == esperado and resultado.as_tuple().exponent == -4


def test_f150_r18_cero_es_cero_y_none_es_none() -> None:
    """0 es la inversión del sujeto pasivo: un valor, no la falta de él."""
    assert porcentaje_iva(D("0")) == 0
    assert porcentaje_iva(None) is None
