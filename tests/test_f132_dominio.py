# tests/test_f132_dominio.py
"""
F-132 · El oráculo de la antigüedad del estado (`domain/estado_documentos.py`).

La regla la ejecuta SQL (`sql/compras/13_estado_documentos.sql`) y aquí se
prueba caso a caso sobre su oráculo puro: de dónde sale `en_estado_desde`
(PASO, ALTA o FUERA_DE_PROCESO), la cota `cambio_posterior_a` y los días.
`tests/test_f132_sql.py` fija que el SQL lleva LOS MISMOS literales.

Los casos del contraste (R13, R14) son documentos REALES de la noche del 07-10
al 08-10, leídos en solo lectura el 2026-10-08: sus pasos de `rac` tal como
los publica `compras.documento_procesos` (hora de Madrid, CEST = UTC+2) y la
ventana de la foto (`observado_antes`, `desde`] en UTC.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from etl_sigrid.domain.estado_documentos import (
    CLASES_CAMBIO,
    CLASES_NO_VISTO,
    ESTADOS_INICIALES,
    FAMILIAS_ESTADO,
    ORIGENES_FECHA,
    FechaEstado,
    PasoEstado,
    clasificar_cambio,
    clasificar_no_visto,
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


# ===========================================================================
# R13 · cada cambio que vio la foto, clasificado contra `rac`
# ===========================================================================

#: Octubre y septiembre de 2026 van en horario de verano: Madrid = UTC+2.
CEST = timezone(timedelta(hours=2))

#: La ventana real de la segunda foto: (línea base, nocturna del 08-10].
INICIO = datetime(2026, 10, 7, 0, 3, 0, tzinfo=UTC)
FIN = datetime(2026, 10, 8, 0, 3, 1, 945572, tzinfo=UTC)


def _madrid(*partes: int) -> datetime:
    """Un `momento` de `rac` (hora de Madrid) pasado a UTC, como el SQL."""
    return datetime(*partes, tzinfo=CEST).astimezone(UTC)


def _pasos(*cadena: tuple[int, tuple[int, ...]]) -> list[PasoEstado]:
    return [
        PasoEstado(orden=orden, destino=destino, momento=_madrid(*momento))
        for orden, (destino, momento) in enumerate(cadena, start=1)
    ]


#: Factura 2808958, 5 -> 6: el paso 5>6 se dio el 07-10 a las 12:43:10.
FACTURA_PASO = _pasos(
    (2, (2026, 7, 31, 9, 9, 23)),
    (3, (2026, 7, 31, 9, 9, 38)),
    (4, (2026, 7, 31, 15, 3, 3)),
    (5, (2026, 8, 3, 17, 37, 8)),
    (6, (2026, 10, 7, 12, 43, 10)),
)
#: Contrato 2844510, 1 -> 3: el envío del 07-10 a las 12:11:10.
CONTRATO_PASO = _pasos((3, (2026, 10, 7, 12, 11, 10)))
#: Factura 2831855, 6 -> 5: el 5>6 se deshizo; su último paso es el 4>5 del 08-09.
FACTURA_DESHECHO = _pasos(
    (2, (2026, 9, 8, 12, 44, 8)),
    (3, (2026, 9, 8, 12, 44, 15)),
    (4, (2026, 9, 8, 13, 15, 22)),
    (5, (2026, 9, 8, 13, 17, 59)),
)
#: Contrato 2833636, 7 -> 5: deshechos el 5>6 y el 6>7; queda el 3>5 del 10-09.
CONTRATO_DESHECHO = _pasos(
    (3, (2026, 9, 10, 13, 18, 30)),
    (5, (2026, 9, 10, 13, 18, 35)),
)
#: Contrato 2652534 (7 en las dos fotos): la cadena 1>3>5>6>7 deshecha y
#: rehecha en segundos el 07-10, sin que la foto viera cambio.
CONTRATO_IDA_Y_VUELTA = _pasos(
    (3, (2026, 10, 7, 8, 56, 28)),
    (5, (2026, 10, 7, 8, 56, 33)),
    (6, (2026, 10, 7, 8, 56, 41)),
    (7, (2026, 10, 7, 8, 56, 48)),
)
#: Factura 2849508: nació el 07-10 y la foto la vio nacer ya en 4.
FACTURA_ALTA = _pasos(
    (2, (2026, 10, 7, 8, 7, 16)),
    (3, (2026, 10, 7, 8, 8, 30)),
    (4, (2026, 10, 7, 8, 42, 18)),
)


def test_f132_r13_las_clases_del_cambio_en_su_orden_de_prioridad() -> None:
    assert CLASES_CAMBIO == (
        "PASO", "DESHECHO", "VUELTA_AL_INICIAL", "FUERA_DE_PROCESO", "DISCREPANCIA"
    )
    assert CLASES_NO_VISTO == ("ALTA", "IDA_Y_VUELTA", "DISCREPANCIA")


@pytest.mark.parametrize(
    ("tipo", "estado_nuevo", "pasos"),
    [(15, 6, FACTURA_PASO), (44, 3, CONTRATO_PASO)],
    ids=["factura_2808958", "contrato_2844510"],
)
def test_f132_r13_paso_hay_un_paso_al_estado_nuevo_en_la_ventana(
    tipo: int, estado_nuevo: int, pasos: list[PasoEstado]
) -> None:
    assert clasificar_cambio(tipo, estado_nuevo, INICIO, FIN, pasos) == "PASO"


@pytest.mark.parametrize(
    ("tipo", "estado_nuevo", "pasos"),
    [(15, 5, FACTURA_DESHECHO), (44, 5, CONTRATO_DESHECHO)],
    ids=["factura_2831855", "contrato_2833636"],
)
def test_f132_r13_deshecho_el_ultimo_paso_ya_llevaba_al_estado_nuevo(
    tipo: int, estado_nuevo: int, pasos: list[PasoEstado]
) -> None:
    assert clasificar_cambio(tipo, estado_nuevo, INICIO, FIN, pasos) == "DESHECHO"


def test_f132_r13_los_pasos_pueden_llegar_en_cualquier_orden() -> None:
    desordenados = list(reversed(CONTRATO_DESHECHO))

    assert clasificar_cambio(44, 5, INICIO, FIN, desordenados) == "DESHECHO"
    # Por posición en la lista el «último» sería el 1>3 y saldría DESHECHO;
    # por `orden` es el 3>5, que lleva a otro estado.
    assert clasificar_cambio(44, 3, INICIO, FIN, desordenados) == "FUERA_DE_PROCESO"


def test_f132_r13_vuelta_al_inicial_sin_un_solo_paso() -> None:
    """Contrato 2775496: FIR (7) -> PFP (1) con la cadena entera deshecha."""
    assert clasificar_cambio(44, 1, INICIO, FIN, []) == "VUELTA_AL_INICIAL"


def test_f132_r13_sin_pasos_y_estado_nuevo_no_inicial_es_discrepancia() -> None:
    assert clasificar_cambio(44, 5, INICIO, FIN, []) == "DISCREPANCIA"
    assert clasificar_cambio(44, 20, INICIO, FIN, []) == "DISCREPANCIA"


def test_f132_r13_fuera_de_proceso_el_ultimo_paso_lleva_a_otro_estado() -> None:
    """Construido: la factura pasa a 10 y su último paso la dejó en 6."""
    assert clasificar_cambio(15, 10, INICIO, FIN, FACTURA_PASO) == "FUERA_DE_PROCESO"


def test_f132_r13_discrepancia_el_paso_existe_pero_despues_de_la_foto() -> None:
    """Construido: la foto ya vio el 7 y el paso 6>7 es POSTERIOR (reloj o zona)."""
    tarde = [*CONTRATO_PASO, PasoEstado(orden=2, destino=7, momento=FIN + timedelta(hours=8))]

    assert clasificar_cambio(44, 7, INICIO, FIN, tarde) == "DISCREPANCIA"


def test_f132_r13_la_ventana_es_abierta_por_abajo_y_cerrada_por_arriba() -> None:
    en_el_fin = [PasoEstado(orden=1, destino=3, momento=FIN)]
    en_el_inicio = [PasoEstado(orden=1, destino=3, momento=INICIO)]
    antes = [PasoEstado(orden=1, destino=3, momento=INICIO - timedelta(seconds=1))]
    despues = [PasoEstado(orden=1, destino=3, momento=FIN + timedelta(microseconds=1))]

    assert clasificar_cambio(44, 3, INICIO, FIN, en_el_fin) == "PASO"
    # En el inicio o antes: el paso ya estaba cuando la foto anterior miró.
    assert clasificar_cambio(44, 3, INICIO, FIN, en_el_inicio) == "DESHECHO"
    assert clasificar_cambio(44, 3, INICIO, FIN, antes) == "DESHECHO"
    assert clasificar_cambio(44, 3, INICIO, FIN, despues) == "DISCREPANCIA"


def test_f132_r13_el_paso_manda_sobre_el_deshecho() -> None:
    """Contrato 2456588, 7 -> 8: cadena entera el 07-10 y el último a 8."""
    cadena = _pasos(
        (3, (2026, 10, 7, 13, 17, 59)),
        (5, (2026, 10, 7, 13, 18, 7)),
        (6, (2026, 10, 7, 13, 18, 20)),
        (7, (2026, 10, 7, 13, 18, 29)),
        (8, (2026, 10, 7, 13, 18, 40)),
    )

    assert clasificar_cambio(44, 8, INICIO, FIN, cadena) == "PASO"


def test_f132_r13_un_paso_en_la_ventana_a_otro_estado_no_es_paso() -> None:
    """El paso de la ventana tiene que llevar AL ESTADO NUEVO, no a cualquiera."""
    assert clasificar_cambio(44, 5, INICIO, FIN, CONTRATO_PASO) == "FUERA_DE_PROCESO"


def test_f132_r13_un_paso_sin_hora_no_cuenta_en_ninguna_ventana() -> None:
    sin_hora = [PasoEstado(orden=1, destino=3, momento=None)]

    assert clasificar_cambio(44, 3, INICIO, FIN, sin_hora) == "DISCREPANCIA"
    assert clasificar_cambio(44, 1, INICIO, FIN, sin_hora) == "VUELTA_AL_INICIAL"


def test_f132_r13_fuera_de_proceso_exige_que_ningun_paso_posterior_lleve_al_nuevo() -> None:
    otro_y_luego_el_nuevo = [
        *CONTRATO_PASO,
        PasoEstado(orden=2, destino=7, momento=FIN + timedelta(days=1)),
    ]
    otro_y_luego_otro = [
        *CONTRATO_PASO,
        PasoEstado(orden=2, destino=5, momento=FIN + timedelta(days=1)),
    ]

    assert clasificar_cambio(44, 7, INICIO, FIN, otro_y_luego_el_nuevo) == "DISCREPANCIA"
    assert clasificar_cambio(44, 7, INICIO, FIN, otro_y_luego_otro) == "FUERA_DE_PROCESO"


# ===========================================================================
# R14 · los pasos de la ventana que la foto NO vio cambiar
# ===========================================================================


def test_f132_r14_alta_la_foto_le_abrio_tramo_ese_dia() -> None:
    """Factura 2849508: nace el 07-10 y la foto la ve nacer ya en 4."""
    assert clasificar_no_visto(4, True, FIN, FACTURA_ALTA) == "ALTA"
    # El alta manda aunque el estado no case: la foto la vio nacer.
    assert clasificar_no_visto(9, True, FIN, FACTURA_ALTA) == "ALTA"


def test_f132_r14_ida_y_vuelta_el_ultimo_paso_deja_el_estado_de_la_foto() -> None:
    """Contrato 2652534: 7 en las dos fotos, la cadena rehecha el 07-10."""
    assert clasificar_no_visto(7, False, FIN, CONTRATO_IDA_Y_VUELTA) == "IDA_Y_VUELTA"
    assert clasificar_no_visto(7, False, FIN, list(reversed(CONTRATO_IDA_Y_VUELTA))) == (
        "IDA_Y_VUELTA"
    )


def test_f132_r14_solo_cuentan_los_pasos_hasta_el_fin_de_la_ventana() -> None:
    despues = [
        *CONTRATO_IDA_Y_VUELTA,
        PasoEstado(orden=5, destino=8, momento=FIN + timedelta(seconds=1)),
    ]

    assert clasificar_no_visto(7, False, FIN, despues) == "IDA_Y_VUELTA"
    assert clasificar_no_visto(8, False, FIN, despues) == "DISCREPANCIA"


def test_f132_r14_discrepancia_si_el_ultimo_paso_lleva_a_otro_estado() -> None:
    assert clasificar_no_visto(5, False, FIN, CONTRATO_IDA_Y_VUELTA) == "DISCREPANCIA"
    assert clasificar_no_visto(7, False, FIN, []) == "DISCREPANCIA"
