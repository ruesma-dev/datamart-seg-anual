# tests/test_f135_dominio.py
"""
F-135 · El criterio de lo restringido, como dominio puro (R1, R2, R3, R7).

Es el oráculo: el SQL de `contabilidad_restringida.mayor` NO llama a este
módulo, pero tiene que decir lo mismo (R4 lo compara literal a literal en
`test_f135_sql.py`). Aquí se fija qué es una cuenta restringida (CR), qué es
un asiento de personal (AP) y qué motivo lleva cada apunte.

Ningún test de este fichero abre red ni BBDD.
"""

from __future__ import annotations

import re

import pytest

from etl_sigrid.domain.restriccion_personal import (
    CLASE_NORMAL,
    MOTIVO_ASIENTO_PERSONAL,
    MOTIVO_CUENTA,
    MOTIVO_CUENTA_SIN_RESOLVER,
    PATRON_CONCEPTO_NOMINA,
    PREFIJOS_CUENTA_RESTRINGIDA,
    REGEX_CUENTA_RESTRINGIDA,
    TEXTO_CUENTA_ENMASCARADA,
    ApunteContable,
    concepto_es_de_nomina,
    cuenta_sin_resolver,
    es_apunte_restringido,
    es_asiento_de_personal,
    es_cuenta_restringida,
    motivo_restriccion,
)

#: Los catorce prefijos aprobados (D1-b, D11), escritos aquí A MANO a propósito:
#: si alguien cambia la tupla del dominio, este test lo denuncia.
PREFIJOS_APROBADOS = (
    "640", "641", "642", "643", "644", "645", "649",
    "465", "466", "476", "460", "461", "544", "4753",
)


def _ap(codigo: str | None, concepto: str | None = None, clase: str = "NORMAL") -> ApunteContable:
    return ApunteContable(codigo_cuenta=codigo, clase_asiento=clase, concepto=concepto)


# ===========================================================================
# R1 · la cuenta restringida (CR)
# ===========================================================================


def test_f135_r1_los_catorce_prefijos_aprobados() -> None:
    assert PREFIJOS_CUENTA_RESTRINGIDA == PREFIJOS_APROBADOS


@pytest.mark.parametrize("prefijo", PREFIJOS_APROBADOS)
def test_f135_r1_cada_prefijo_restringe_su_cuenta_auxiliar(prefijo: str) -> None:
    codigo = (prefijo + "0000000000")[:10]
    assert es_cuenta_restringida(codigo), f"{codigo} deberia ser CR"
    assert es_cuenta_restringida(prefijo), "el propio grupo tambien empieza por el prefijo"


@pytest.mark.parametrize(
    "codigo",
    [
        "4751000001",  # retenciones de profesionales: fuera (D12)
        "4750000001",
        "4752000001",
        "4754000001",
        "5700000001",  # cajas: solo dentro de un AP (D9)
        "6460000001",  # 646 y 648 no estan en la lista aprobada
        "6480000001",
        "4620000001",
    ],
)
def test_f135_r1_cuentas_cercanas_que_no_son_cr(codigo: str) -> None:
    assert not es_cuenta_restringida(codigo)


@pytest.mark.parametrize(
    "codigo",
    ["4753000001", "4753", "6400000123", "4650000009", "5440000001", "6450000001"],
)
def test_f135_r1_cuentas_cr(codigo: str) -> None:
    assert es_cuenta_restringida(codigo)


@pytest.mark.parametrize("codigo", [None, "", "64", "6", "47", "475", "1640000000", " 640"])
def test_f135_r1_sin_codigo_o_prefijo_en_medio_no_es_cr(codigo: str | None) -> None:
    """El prefijo va ANCLADO al principio, como el `^` del SQL; `None` (apunte
    sin cuenta, `cueide = 0`) no es CR."""
    assert not es_cuenta_restringida(codigo)


def test_f135_r1_la_regex_del_sql_se_construye_desde_la_tupla() -> None:
    assert REGEX_CUENTA_RESTRINGIDA == "^(" + "|".join(PREFIJOS_APROBADOS) + ")"


@pytest.mark.parametrize(
    "codigo",
    ["4753000001", "4751000001", "6400000001", "5700000001", "1640000000", "", "64", "4753"],
)
def test_f135_r1_la_regex_y_la_funcion_dicen_lo_mismo(codigo: str) -> None:
    """La regex es lo que lleva el SQL; la función, lo que usan los tests. Si
    divergieran, el oráculo no serviría de nada."""
    assert bool(re.match(REGEX_CUENTA_RESTRINGIDA, codigo)) == es_cuenta_restringida(codigo)


# ===========================================================================
# R3 · el concepto de nómina
# ===========================================================================


def test_f135_r3_el_patron_es_el_de_postgresql() -> None:
    assert PATRON_CONCEPTO_NOMINA == r"\mn[oóÓ]minas?\M"


@pytest.mark.parametrize(
    "concepto",
    [
        "nómina",
        "nomina",
        "NÓMINAS",
        "NOMINA ENERO",
        "Pago nóminas marzo 2025",
        "Nómina extra julio",
        "ANTICIPO NOMINA",
        "nomina.",
        "(nominas)",
    ],
)
def test_f135_r3_casa_las_formas_de_nomina(concepto: str) -> None:
    assert concepto_es_de_nomina(concepto)


@pytest.mark.parametrize(
    "concepto",
    [
        "denominación",
        "DENOMINACION SOCIAL",
        "nominación",
        "nominal",
        "pronominal",
        "nóminasx",
        "nmina",
        "",
        None,
        "factura proveedor",
    ],
)
def test_f135_r3_no_casa_palabras_que_la_contienen(concepto: str | None) -> None:
    assert not concepto_es_de_nomina(concepto)


# ===========================================================================
# R2 · el asiento de personal (AP)
# ===========================================================================


def test_f135_r2_asiento_con_una_cuenta_cr_es_ap() -> None:
    assert es_asiento_de_personal([_ap("6400000001"), _ap("5720000001"), _ap("4751000001")])


def test_f135_r2_asiento_solo_con_concepto_de_nomina_es_ap() -> None:
    """Los 371 asientos de nómina sin cuentas N2 (anticipos contra banco)."""
    assert es_asiento_de_personal([_ap("5720000001", "Pago nomina Fulano"), _ap("4100000001")])


def test_f135_r2_un_apunte_de_regularizacion_lo_saca_de_ap() -> None:
    """Los 243 asientos no normales con cuentas 640-476 arrastrarían todo el
    grupo 6 y 7: basta UN apunte no NORMAL para que el asiento no sea AP."""
    apuntes = [_ap("6400000001"), _ap("1290000000", clase="REGULARIZACION")]
    assert not es_asiento_de_personal(apuntes)


@pytest.mark.parametrize("clase", ["CIERRE", "APERTURA", "SALDO_INICIAL", "REGULARIZACION"])
def test_f135_r2_ninguna_clase_distinta_de_normal_es_ap(clase: str) -> None:
    assert not es_asiento_de_personal([_ap("6400000001", "nomina", clase=clase)])


def test_f135_r2_asiento_sin_cr_ni_concepto_no_es_ap() -> None:
    assert not es_asiento_de_personal(
        [_ap("4000000001", "factura"), _ap("5720000001", "denominación"), _ap(None)]
    )


def test_f135_r2_asiento_vacio_no_es_ap() -> None:
    assert not es_asiento_de_personal([])


def test_f135_r2_la_570_sola_no_hace_ap() -> None:
    """D9: la caja solo cae dentro de un AP; por sí sola no lo crea."""
    assert not es_asiento_de_personal([_ap("5700000001"), _ap("5720000001")])
    assert es_asiento_de_personal([_ap("5700000001"), _ap("4650000001")])


def test_f135_r2_la_clase_normal_es_la_del_mayor() -> None:
    assert CLASE_NORMAL == "NORMAL"


# ===========================================================================
# R7 · el motivo de cada apunte
# ===========================================================================


def test_f135_r7_cuenta_gana_a_asiento_personal() -> None:
    assert motivo_restriccion(_ap("6400000001"), asiento_es_personal=True) == MOTIVO_CUENTA
    assert motivo_restriccion(_ap("6400000001"), asiento_es_personal=False) == MOTIVO_CUENTA


def test_f135_r7_cuenta_cr_restringida_en_cualquier_clase() -> None:
    """La CR se restringe entera, también en cierres y aperturas."""
    apunte = _ap("4650000001", clase="CIERRE")
    assert motivo_restriccion(apunte, asiento_es_personal=False) == MOTIVO_CUENTA
    assert es_apunte_restringido(apunte, asiento_es_personal=False)


def test_f135_r7_solo_el_asiento_da_asiento_personal() -> None:
    assert (
        motivo_restriccion(_ap("5720000001"), asiento_es_personal=True)
        == MOTIVO_ASIENTO_PERSONAL
    )


def test_f135_r7_ni_cuenta_ni_asiento_es_visible() -> None:
    assert motivo_restriccion(_ap("5720000001"), asiento_es_personal=False) is None
    assert motivo_restriccion(_ap(None), asiento_es_personal=False) is None
    assert not es_apunte_restringido(_ap("5720000001"), asiento_es_personal=False)


def test_f135_r7_restringido_es_tener_motivo() -> None:
    assert es_apunte_restringido(_ap("5720000001"), asiento_es_personal=True)
    assert es_apunte_restringido(_ap("4753000001"), asiento_es_personal=False)


def test_f135_r7_valores_de_los_motivos() -> None:
    assert (MOTIVO_CUENTA, MOTIVO_ASIENTO_PERSONAL) == ("CUENTA", "ASIENTO_PERSONAL")


def test_f135_r12_texto_de_la_mascara() -> None:
    assert TEXTO_CUENTA_ENMASCARADA == "(cuenta restringida)"


def test_f135_r1_el_dominio_no_importa_infraestructura() -> None:
    """Hexagonal: el módulo de dominio no depende de nada externo."""
    from pathlib import Path

    texto = (
        Path(__file__).resolve().parents[1]
        / "etl_sigrid" / "domain" / "restriccion_personal.py"
    ).read_text(encoding="utf-8")
    assert "infrastructure" not in texto
    assert "psycopg" not in texto
    assert texto.splitlines()[0] == "# etl_sigrid/domain/restriccion_personal.py"


# ===========================================================================
# Review pasada 1, cambio 1: la cuenta que no resuelve en el plan, FALLA CERRADO
# ===========================================================================


def test_f135_r7_cuenta_sin_resolver_es_restringida_con_su_motivo() -> None:
    """Un apunte con `cuenta_id` cuya cuenta no está en el plan (código NULL) no
    se sabe si es de personal: se restringe (criterio de Juan, «restringe de
    más»), con un motivo propio para poder contarlo aparte."""
    apunte = ApunteContable(codigo_cuenta=None, clase_asiento="NORMAL", concepto="x", cuenta_id=465)
    assert cuenta_sin_resolver(apunte)
    assert motivo_restriccion(apunte, asiento_es_personal=False) == MOTIVO_CUENTA_SIN_RESOLVER
    assert motivo_restriccion(apunte, asiento_es_personal=True) == MOTIVO_CUENTA_SIN_RESOLVER
    assert es_apunte_restringido(apunte, asiento_es_personal=False)
    assert MOTIVO_CUENTA_SIN_RESOLVER == "CUENTA_SIN_RESOLVER"


def test_f135_r7_sin_cuenta_no_es_cuenta_sin_resolver() -> None:
    """`cueide = 0` (cuenta_id NULL, 294 apuntes de importe cero) NO es eso: no
    hay cuenta que resolver."""
    apunte = ApunteContable(codigo_cuenta=None, clase_asiento="NORMAL", concepto=None, cuenta_id=None)
    assert not cuenta_sin_resolver(apunte)
    assert motivo_restriccion(apunte, asiento_es_personal=False) is None
    resuelta = ApunteContable(codigo_cuenta="5720000001", clase_asiento="NORMAL", concepto=None, cuenta_id=7)
    assert not cuenta_sin_resolver(resuelta)
    assert motivo_restriccion(resuelta, asiento_es_personal=False) is None


def test_f135_r2_cuenta_sin_resolver_hace_ap_al_asiento() -> None:
    """Falla cerrado también en el asiento: la cuenta podría ser una 465, y su
    banco no puede quedar visible (lo que reprodujo el reviewer)."""
    sin_resolver = ApunteContable(codigo_cuenta=None, clase_asiento="NORMAL", concepto="pago", cuenta_id=9)
    banco = ApunteContable(codigo_cuenta="5720000001", clase_asiento="NORMAL", concepto="pago", cuenta_id=8)
    assert es_asiento_de_personal([sin_resolver, banco])
    assert motivo_restriccion(banco, asiento_es_personal=True) == MOTIVO_ASIENTO_PERSONAL
    # en un asiento no NORMAL, la propia cuenta se restringe igual, pero el asiento no es AP
    cierre = ApunteContable(codigo_cuenta=None, clase_asiento="CIERRE", concepto="x", cuenta_id=9)
    assert not es_asiento_de_personal([cierre])
    assert motivo_restriccion(cierre, asiento_es_personal=False) == MOTIVO_CUENTA_SIN_RESOLVER


def test_f135_r7_el_constructor_de_siempre_sigue_valiendo() -> None:
    """`cuenta_id` es opcional: sin él, el apunte se juzga como antes."""
    assert ApunteContable("6400000001", "NORMAL", None).cuenta_id is None
