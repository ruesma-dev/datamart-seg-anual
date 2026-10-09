# tests/test_f132_dominio.py
"""
F-132 · El oráculo de la antigüedad del estado (`domain/estado_documentos.py`).

La regla la ejecuta SQL (`sql/compras/13_estado_documentos.sql`) y aquí se
prueba caso a caso sobre su oráculo puro: de dónde sale `en_estado_desde`
(PASO, ALTA o FUERA_DE_PROCESO), la cota `cambio_posterior_a` y los días.
`tests/test_f132_sql.py` fija que el SQL lleva LOS MISMOS literales.
"""

from __future__ import annotations

import ast
from datetime import date, datetime
from pathlib import Path

import pytest

from etl_sigrid.domain.estado_documentos import (
    ESTADOS_INICIALES,
    FAMILIAS_ESTADO,
    ORIGENES_FECHA,
    FechaEstado,
    PasoEstado,
    dias_en_estado,
    fecha_estado,
)

RUTA_DOMINIO = (
    Path(__file__).resolve().parents[1] / "etl_sigrid" / "domain" / "estado_documentos.py"
)


# ===========================================================================
# R11 · las familias, los estados iniciales y los orígenes, una sola vez
# ===========================================================================


def test_f132_r11_familias_de_la_vista() -> None:
    assert FAMILIAS_ESTADO == {44: "CONTRATO", 15: "FACTURA", 46: "COMPARATIVO"}


def test_f132_r11_estados_iniciales_medidos() -> None:
    assert {
        15: frozenset({1, 20}),
        44: frozenset({1}),
        46: frozenset({1, 11, 100}),
    } == ESTADOS_INICIALES
    assert set(ESTADOS_INICIALES) == set(FAMILIAS_ESTADO)


def test_f132_r11_los_tres_origenes_en_orden() -> None:
    assert ORIGENES_FECHA == ("PASO", "ALTA", "FUERA_DE_PROCESO")


def test_f132_r11_el_dominio_no_importa_infraestructura_ni_configuracion() -> None:
    arbol = ast.parse(RUTA_DOMINIO.read_text(encoding="utf-8"))
    modulos = {
        n.module or "" for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)
    } | {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
    prohibidos = [m for m in modulos if "infrastructure" in m or m.startswith("config")]
    assert not prohibidos, prohibidos


# ===========================================================================
# R4 · PASO: el último paso lleva al estado actual
# ===========================================================================

#: El CTSB25/... de 2834162: su único paso, el envío (1 -> 3) del 21-09.
ENVIO = PasoEstado(orden=1, destino=3, momento=datetime(2026, 9, 21, 16, 40, 6))


def test_f132_r4_paso_fecha_al_segundo_del_ultimo_paso() -> None:
    assert fecha_estado(44, 3, ENVIO, date(2026, 9, 21), date(2026, 9, 1)) == FechaEstado(
        en_estado_desde=datetime(2026, 9, 21, 16, 40, 6),
        origen="PASO",
        cambio_posterior_a=None,
    )


def test_f132_r4_paso_sin_hora_cuenta_desde_su_fecha_a_las_cero() -> None:
    sin_hora = PasoEstado(orden=2, destino=5, momento=None)

    fecha = fecha_estado(15, 5, sin_hora, date(2026, 3, 4), date(2026, 3, 1))

    assert fecha.en_estado_desde == datetime(2026, 3, 4, 0, 0)
    assert fecha.origen == "PASO"
    assert fecha.cambio_posterior_a is None


def test_f132_r4_paso_aunque_el_estado_sea_inicial() -> None:
    """Un comparativo devuelto a 1 por un paso cuenta desde el paso, no del alta."""
    vuelta = PasoEstado(orden=4, destino=1, momento=datetime(2026, 5, 6, 9, 0, 0))

    fecha = fecha_estado(46, 1, vuelta, date(2026, 5, 6), date(2020, 1, 1))

    assert (fecha.origen, fecha.en_estado_desde) == ("PASO", datetime(2026, 5, 6, 9, 0))


# ===========================================================================
# R5, R8 · ALTA: sin pasos y en un estado inicial de su tipo
# ===========================================================================


@pytest.mark.parametrize(
    ("tipo", "estado"), [(15, 1), (15, 20), (44, 1), (46, 1), (46, 11), (46, 100)]
)
def test_f132_r5_alta_cuenta_desde_el_dia_de_alta(tipo: int, estado: int) -> None:
    assert fecha_estado(tipo, estado, None, None, date(2024, 2, 29)) == FechaEstado(
        en_estado_desde=datetime(2024, 2, 29, 0, 0),
        origen="ALTA",
        cambio_posterior_a=None,
    )


def test_f132_r8_alta_sin_fecha_de_alta_no_tiene_fecha_ni_dias() -> None:
    fecha = fecha_estado(44, 1, None, None, None)

    assert fecha == FechaEstado(en_estado_desde=None, origen="ALTA", cambio_posterior_a=None)
    assert dias_en_estado(fecha.en_estado_desde, date(2026, 10, 8)) is None


# ===========================================================================
# R6, R7 · FUERA_DE_PROCESO: sin fecha y con la cota «cambió después de»
# ===========================================================================


def test_f132_r6_fuera_de_proceso_si_el_ultimo_paso_lleva_a_otro_estado() -> None:
    """Las facturas que pasaron de 6 a 10 sin un solo paso (75 en el stock)."""
    ultimo = PasoEstado(orden=5, destino=6, momento=datetime(2019, 3, 2, 11, 5, 0))

    assert fecha_estado(15, 10, ultimo, date(2019, 3, 2), date(2019, 1, 7)) == FechaEstado(
        en_estado_desde=None,
        origen="FUERA_DE_PROCESO",
        cambio_posterior_a=datetime(2019, 3, 2, 11, 5, 0),
    )


def test_f132_r6_fuera_de_proceso_con_ultimo_paso_sin_hora_la_cota_es_su_dia() -> None:
    ultimo = PasoEstado(orden=1, destino=2, momento=None)

    fecha = fecha_estado(15, 50, ultimo, date(2012, 6, 1), date(2012, 5, 30))

    assert fecha.cambio_posterior_a == datetime(2012, 6, 1, 0, 0)
    assert fecha.en_estado_desde is None


@pytest.mark.parametrize(
    ("tipo", "estado"),
    [
        (44, 5),  # contrato fuera de su estado inicial y sin pasos
        (44, 20),  # el 20 es inicial de FACTURA, no de CONTRATO
        (15, 11),  # el 11 es inicial de COMPARATIVO, no de FACTURA
        (44, None),  # un estado nulo no es inicial de nada
        (42, 1),  # un tipo fuera de la vista no tiene estados iniciales
    ],
)
def test_f132_r6_fuera_de_proceso_sin_pasos_y_estado_no_inicial(
    tipo: int, estado: int | None
) -> None:
    assert fecha_estado(tipo, estado, None, None, date(2020, 1, 1)) == FechaEstado(
        en_estado_desde=None, origen="FUERA_DE_PROCESO", cambio_posterior_a=None
    )


def test_f132_r6_el_estado_nulo_casa_con_un_destino_nulo() -> None:
    """`IS NOT DISTINCT FROM`: un destino nulo explica un estado nulo."""
    nulo = PasoEstado(orden=1, destino=None, momento=datetime(2026, 1, 2, 3, 4, 5))

    assert fecha_estado(44, None, nulo, date(2026, 1, 2), None).origen == "PASO"


# ===========================================================================
# R9 · los días se cuentan al consultar, en días de calendario
# ===========================================================================


@pytest.mark.parametrize(
    ("desde", "hoy", "dias"),
    [
        (datetime(2026, 9, 21, 16, 40, 6), date(2026, 10, 8), 17),
        (datetime(2026, 10, 8, 23, 59, 59), date(2026, 10, 8), 0),
        (datetime(2026, 10, 7, 23, 59, 59), date(2026, 10, 8), 1),
        (datetime(2018, 1, 1, 0, 0), date(2026, 10, 8), 3202),
    ],
)
def test_f132_r9_dias_de_calendario_entre_la_fecha_y_hoy(
    desde: datetime, hoy: date, dias: int
) -> None:
    assert dias_en_estado(desde, hoy) == dias


def test_f132_r9_sin_fecha_no_hay_dias() -> None:
    assert dias_en_estado(None, date(2026, 10, 8)) is None


def test_f132_r7_cambio_posterior_a_solo_en_fuera_de_proceso() -> None:
    con_paso = fecha_estado(44, 3, ENVIO, date(2026, 9, 21), None)
    de_alta = fecha_estado(44, 1, None, None, date(2026, 9, 1))
    fuera = fecha_estado(44, 7, ENVIO, date(2026, 9, 21), None)

    assert con_paso.cambio_posterior_a is None
    assert de_alta.cambio_posterior_a is None
    assert fuera.cambio_posterior_a == ENVIO.momento
    assert {con_paso.origen, de_alta.origen, fuera.origen} == set(ORIGENES_FECHA)


# R13 y R14 (el contraste con la foto diaria): RETIRADOS con la foto. La Fase B
# de F-132 (rama BORRAR, 2026-10-09) borró el contraste y su dominio;
# `tests/test_f132_retirada.py` fija que ya no están.
