# tests/test_f153_dominio.py
"""
F-153 · El oráculo del tipo 14 en `domain/estado_documentos.py`.

Los albaranes (con proformas y notas) entran en `compras.v_estado_documentos`
sin pasos en `compras.documento_procesos` (F-133). Aquí se prueba cada rama de
R7 y su ORDEN: PASO > FACTURACION > ALTA > SIN_HISTORIAL > FUERA_DE_PROCESO.
`tests/test_f153_sql.py` fija que el SQL lleva los mismos literales.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from etl_sigrid.domain.estado_documentos import (
    ESTADO_FACTURADO_ALBARAN,
    ESTADOS_INICIALES,
    FAMILIAS_ESTADO,
    FAMILIAS_SIN_HISTORIAL,
    ORIGENES_FECHA,
    TIPO_ALBARAN,
    TIPOS_DOCUMENTO_ALBARAN,
    FechaEstado,
    PasoEstado,
    dias_en_estado,
    fecha_estado,
)

ALTA_DOC = date(2024, 3, 1)
DIA_PASO = date(2024, 4, 2)
DIA_FACT = date(2024, 5, 3)
MOMENTO = datetime(2024, 4, 2, 10, 11, 12)

#: «Comprobar» (1 -> 2) y «Contabilizar» (2 -> 3), los pasos reales de `rac`.
A_COMPROBADO = PasoEstado(orden=1, destino=2, momento=MOMENTO)
A_CONTABILIZADO = PasoEstado(orden=2, destino=3, momento=MOMENTO)
A_FACTURADO = PasoEstado(orden=3, destino=10, momento=MOMENTO)


def test_f153_r10_constantes_del_tipo_14() -> None:
    assert TIPO_ALBARAN == 14
    assert ESTADO_FACTURADO_ALBARAN == 10
    assert TIPOS_DOCUMENTO_ALBARAN == ("ALBARAN", "PROFORMA", "NOTA", "OTRO")
    assert frozenset({14}) == FAMILIAS_SIN_HISTORIAL
    assert ESTADOS_INICIALES[14] == frozenset({1})


def test_f153_r7_los_cinco_origenes_en_el_orden_de_la_regla() -> None:
    assert ORIGENES_FECHA == ("PASO", "FACTURACION", "ALTA", "SIN_HISTORIAL", "FUERA_DE_PROCESO")


def test_f153_r10_familias_estado_no_cambia_el_14_va_por_tipo_documento() -> None:
    assert 14 not in FAMILIAS_ESTADO


# --- R7.1 · PASO ---------------------------------------------------------------


def test_f153_r7_paso_gana_a_facturacion_si_el_ultimo_paso_lleva_a_10() -> None:
    assert fecha_estado(
        14, 10, A_FACTURADO, DIA_PASO, ALTA_DOC, fecha_facturacion=DIA_FACT
    ) == FechaEstado(MOMENTO, "PASO", None)


@pytest.mark.parametrize(("estado", "paso"), [(2, A_COMPROBADO), (3, A_CONTABILIZADO)])
def test_f153_r8_con_f133_com_y_con_pasan_solos_a_paso(estado: int, paso: PasoEstado) -> None:
    assert fecha_estado(14, estado, paso, DIA_PASO, ALTA_DOC) == FechaEstado(
        MOMENTO, "PASO", None
    )


# --- R7.2 · FACTURACION --------------------------------------------------------


def test_f153_r7_facturado_con_fecha_y_sin_pasos_cuenta_desde_ese_dia() -> None:
    assert fecha_estado(14, 10, None, None, ALTA_DOC, fecha_facturacion=DIA_FACT) == FechaEstado(
        datetime(2024, 5, 3, 0, 0), "FACTURACION", None
    )


def test_f153_r7_facturacion_gana_a_un_ultimo_paso_que_lleva_a_otro_estado() -> None:
    """Lo normal: FAC cuyo último paso de `rac` es «Contabilizar» (2 -> 3)."""
    assert fecha_estado(
        14, 10, A_CONTABILIZADO, DIA_PASO, ALTA_DOC, fecha_facturacion=DIA_FACT
    ) == FechaEstado(datetime(2024, 5, 3, 0, 0), "FACTURACION", None)


@pytest.mark.parametrize("tipo", [15, 44, 46])
def test_f153_r7_facturacion_es_solo_del_tipo_14(tipo: int) -> None:
    fecha = fecha_estado(tipo, 10, None, None, ALTA_DOC, fecha_facturacion=DIA_FACT)

    assert fecha == FechaEstado(None, "FUERA_DE_PROCESO", None)


@pytest.mark.parametrize("estado", [1, 2, 3])
def test_f153_r7_fecha_de_facturacion_en_otro_estado_no_es_facturacion(estado: int) -> None:
    """Los 185 con `estfac` = 1 y estado distinto de 10: manda el estado."""
    fecha = fecha_estado(14, estado, None, None, ALTA_DOC, fecha_facturacion=DIA_FACT)

    assert fecha.origen != "FACTURACION"


# --- R7.3 · ALTA ---------------------------------------------------------------


def test_f153_r7_pendiente_sin_pasos_cuenta_desde_el_alta() -> None:
    assert fecha_estado(14, 1, None, None, ALTA_DOC) == FechaEstado(
        datetime(2024, 3, 1, 0, 0), "ALTA", None
    )


# --- R7.4 · SIN_HISTORIAL ------------------------------------------------------


@pytest.mark.parametrize(
    "estado",
    [
        2,  # COM: el paso existe en `rac`, pero aún no se publica
        3,  # CON: ídem
        10,  # FAC sin `fecfac`
        0,  # los 10 fuera de catálogo
        None,
    ],
)
def test_f153_r7_tipo_14_sin_pasos_no_tiene_fecha_ni_cota(estado: int | None) -> None:
    fecha = fecha_estado(14, estado, None, None, ALTA_DOC)

    assert fecha == FechaEstado(None, "SIN_HISTORIAL", None)
    assert dias_en_estado(fecha.en_estado_desde, date(2026, 11, 2)) is None


# --- R7.5 · FUERA_DE_PROCESO ---------------------------------------------------


def test_f153_r7_fac_sin_fecha_con_paso_a_otro_estado_da_la_cota() -> None:
    """Riesgo de design §8: tras F-133, ~35.000 FAC sin `fecfac` caen aquí."""
    assert fecha_estado(14, 10, A_CONTABILIZADO, DIA_PASO, ALTA_DOC) == FechaEstado(
        None, "FUERA_DE_PROCESO", MOMENTO
    )


def test_f153_r7_con_paso_sin_hora_la_cota_es_su_dia() -> None:
    sin_hora = PasoEstado(orden=1, destino=2, momento=None)

    fecha = fecha_estado(14, 10, sin_hora, DIA_PASO, ALTA_DOC)

    assert fecha == FechaEstado(None, "FUERA_DE_PROCESO", datetime(2024, 4, 2, 0, 0))


def test_f153_r8_sin_historial_no_alcanza_a_las_familias_con_pasos() -> None:
    assert fecha_estado(15, 7, None, None, ALTA_DOC).origen == "FUERA_DE_PROCESO"


def test_f153_r7_el_argumento_nuevo_tiene_defecto_y_no_rompe_llamadas() -> None:
    assert fecha_estado(15, 1, None, None, ALTA_DOC).origen == "ALTA"
