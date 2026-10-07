# tests/test_f067_dominio.py
"""
F-067 · El oráculo de la FOTO DIARIA de estados y de la fecha de Delphi.

La foto vive en SQL (`sql/compras/11_historial_estados.sql`, un bloque `DO`
que corre cada noche dentro de `build_compras`) y NO se puede ejecutar en los
tests: la base es compartida con producción. Así que la regla se escribe UNA
vez en `etl_sigrid/domain/historial_estados.py` y se prueba aquí, caso a caso
(design §4 y §8); `tests/test_f067_sql.py` comprueba que el SQL lleva **los
mismos** literales. Mismo patrón que `domain/comparativos.py` (F-038).

Lo que estos casos defienden, porque no se puede rehacer: la historia de los
estados NO EXISTE en Sigrid (`concam` no audita `est`). Lo que la foto escriba
mal una noche se queda mal para siempre, y lo que no escriba se pierde.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from etl_sigrid.domain.historial_estados import (
    EPOCA_DELPHI,
    MOTIVOS_CIERRE,
    TIPOS_HISTORIAL,
    UMBRAL_PRESENCIA,
    FotoIncompletaError,
    ResumenFoto,
    Tramo,
    aplicar_foto,
    dias_en_estado,
    fecha_delphi,
    resumir_foto,
)

CONTRATO, FACTURA, ALBARAN = 44, 15, 14
ENVIADO, FIRMADO = 3, 7

T1 = datetime(2026, 10, 7, 0, 41, tzinfo=UTC)
T2 = T1 + timedelta(days=1)
T3 = T2 + timedelta(days=1)


def _abierto(ide: int, tip: int, est: int | None, desde: datetime = T1,
             antes: datetime | None = None, base: bool = True) -> Tramo:
    return Tramo(
        documento_id=ide, tipo=tip, estado_id=est, desde=desde,
        hasta=None, observado_antes=antes, es_linea_base=base, motivo_cierre=None,
    )


def _por_documento(tramos: list[Tramo]) -> dict[int, list[Tramo]]:
    por: dict[int, list[Tramo]] = {}
    for t in tramos:
        por.setdefault(t.documento_id, []).append(t)
    return por


# ===========================================================================
# R1 · los literales, una sola vez
# ===========================================================================


def test_f067_r1_los_tipos_son_contrato_y_factura() -> None:
    assert TIPOS_HISTORIAL == (44, 15)


def test_f067_r6_el_umbral_es_el_98_por_ciento() -> None:
    assert Decimal("0.98") == UMBRAL_PRESENCIA


def test_f067_r5_los_dos_motivos_de_cierre() -> None:
    assert MOTIVOS_CIERRE == ("CAMBIO", "DESAPARECIDO")


def test_f067_r14_la_epoca_es_la_de_delphi() -> None:
    assert date(1899, 12, 30) == EPOCA_DELPHI


# ===========================================================================
# R4 · la primera foto es la LÍNEA BASE
# ===========================================================================


def test_f067_r4_la_primera_foto_abre_un_tramo_de_linea_base_por_documento() -> None:
    actuales = {1: (CONTRATO, ENVIADO), 2: (FACTURA, FIRMADO)}

    tramos = aplicar_foto([], actuales, T1, None)

    assert tramos == [
        Tramo(1, CONTRATO, ENVIADO, T1, None, None, True, None),
        Tramo(2, FACTURA, FIRMADO, T1, None, None, True, None),
    ]


def test_f067_r4_la_linea_base_no_sabe_desde_cuando_observado_antes_nulo() -> None:
    tramos = aplicar_foto([], {7: (CONTRATO, ENVIADO)}, T1, None)

    assert tramos[0].observado_antes is None
    assert tramos[0].es_linea_base is True


def test_f067_r4_sin_documentos_ni_tramos_la_primera_foto_no_abre_nada() -> None:
    assert aplicar_foto([], {}, T1, None) == []


# ===========================================================================
# R2 · un cambio de estado cierra el tramo y abre otro
# ===========================================================================


def test_f067_r2_un_cambio_cierra_el_tramo_y_abre_otro() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    tramos = aplicar_foto(antes, {1: (CONTRATO, FIRMADO)}, T2, T1)

    assert tramos == [
        Tramo(1, CONTRATO, ENVIADO, T1, T2, None, True, "CAMBIO"),
        Tramo(1, CONTRATO, FIRMADO, T2, None, T1, False, None),
    ]


def test_f067_r2_sin_cambio_el_tramo_sigue_abierto_y_no_se_duplica() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    assert aplicar_foto(antes, {1: (CONTRATO, ENVIADO)}, T2, T1) == antes


def test_f067_r2_el_estado_nulo_se_compara_como_is_distinct_from() -> None:
    """`NULL -> 3` es un cambio y `NULL -> NULL` no lo es (IS DISTINCT FROM)."""
    antes = [_abierto(1, CONTRATO, None), _abierto(2, FACTURA, None)]

    tramos = aplicar_foto(antes, {1: (CONTRATO, ENVIADO), 2: (FACTURA, None)}, T2, T1)

    por = _por_documento(tramos)
    assert [t.motivo_cierre for t in por[1]] == ["CAMBIO", None]
    assert por[1][1].estado_id == ENVIADO
    assert por[2] == [antes[1]]


def test_f067_r2_un_estado_que_pasa_a_nulo_tambien_es_cambio() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    tramos = aplicar_foto(antes, {1: (CONTRATO, None)}, T2, T1)

    assert tramos[0].motivo_cierre == "CAMBIO"
    assert tramos[1].estado_id is None


# ===========================================================================
# R3 · un documento nuevo después de la línea base
# ===========================================================================


def test_f067_r3_un_alta_abre_tramo_sin_linea_base() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    tramos = aplicar_foto(antes, {1: (CONTRATO, ENVIADO), 9: (FACTURA, FIRMADO)}, T2, T1)

    assert tramos == [antes[0], Tramo(9, FACTURA, FIRMADO, T2, None, T1, False, None)]


# ===========================================================================
# R5 · el documento que desaparece de `raw.con`
# ===========================================================================


def test_f067_r5_un_documento_que_desaparece_se_cierra_y_no_se_reabre() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO), _abierto(2, FACTURA, FIRMADO)]
    actuales = {1: (CONTRATO, ENVIADO)}
    # 1 de 2 está por debajo del 98 %: la guarda lo pararía. Se le da volumen.
    antes += [_abierto(100 + i, FACTURA, FIRMADO) for i in range(60)]
    actuales |= {100 + i: (FACTURA, FIRMADO) for i in range(60)}

    tramos = aplicar_foto(antes, actuales, T2, T1)

    assert _por_documento(tramos)[2] == [
        Tramo(2, FACTURA, FIRMADO, T1, T2, None, True, "DESAPARECIDO")
    ]


def test_f067_r5_el_que_reaparece_abre_un_tramo_nuevo_sin_linea_base() -> None:
    cerrado = Tramo(2, FACTURA, FIRMADO, T1, T2, None, True, "DESAPARECIDO")

    tramos = aplicar_foto([cerrado], {2: (FACTURA, FIRMADO)}, T3, T2)

    assert tramos == [cerrado, Tramo(2, FACTURA, FIRMADO, T3, None, T2, False, None)]


def test_f067_r5_un_cambio_de_tipo_es_desaparecer_y_volver_a_entrar() -> None:
    """Mismo `ide` con otro `tip`: el SQL une por los dos (`ide` y `tip`)."""
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    tramos = aplicar_foto(antes, {1: (FACTURA, ENVIADO)}, T2, T1)

    assert tramos == [
        Tramo(1, CONTRATO, ENVIADO, T1, T2, None, True, "DESAPARECIDO"),
        Tramo(1, FACTURA, ENVIADO, T2, None, T1, False, None),
    ]


def test_f067_r5_los_tramos_cerrados_no_se_tocan() -> None:
    cerrado = Tramo(1, CONTRATO, ENVIADO, T1, T2, None, True, "CAMBIO")
    abierto = _abierto(1, CONTRATO, FIRMADO, desde=T2, antes=T1, base=False)

    tramos = aplicar_foto([cerrado, abierto], {1: (CONTRATO, FIRMADO)}, T3, T2)

    assert tramos == [cerrado, abierto]


# ===========================================================================
# R1 · solo contratos y facturas
# ===========================================================================


def test_f067_r1_los_tipos_que_no_son_de_la_foto_se_ignoran() -> None:
    tramos = aplicar_foto([], {1: (ALBARAN, ENVIADO), 2: (CONTRATO, ENVIADO)}, T1, None)

    assert [t.documento_id for t in tramos] == [2]


def test_f067_r1_un_documento_que_pasa_a_un_tipo_ajeno_desaparece() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)] + [
        _abierto(100 + i, FACTURA, FIRMADO) for i in range(60)
    ]
    actuales = {1: (ALBARAN, ENVIADO)} | {100 + i: (FACTURA, FIRMADO) for i in range(60)}

    tramos = aplicar_foto(antes, actuales, T2, T1)

    assert _por_documento(tramos)[1] == [
        Tramo(1, CONTRATO, ENVIADO, T1, T2, None, True, "DESAPARECIDO")
    ]


def test_f067_r2_los_documentos_nuevos_salen_ordenados_por_id() -> None:
    tramos = aplicar_foto([], {5: (CONTRATO, 1), 3: (FACTURA, 1), 4: (CONTRATO, 1)}, T1, None)

    assert [t.documento_id for t in tramos] == [3, 4, 5]


def test_f067_r2_no_modifica_la_lista_de_entrada() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]
    copia = list(antes)

    aplicar_foto(antes, {1: (CONTRATO, FIRMADO)}, T2, T1)

    assert antes == copia


# ===========================================================================
# R7 · sin foto nueva no se escribe nada
# ===========================================================================


@pytest.mark.parametrize("observado", [T1, T1 - timedelta(seconds=1)])
def test_f067_r7_una_foto_que_no_es_mas_nueva_no_devuelve_nada(observado: datetime) -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO)]

    assert aplicar_foto(antes, {1: (CONTRATO, FIRMADO)}, observado, T1) is None


def test_f067_r7_sin_instante_observado_no_hay_foto() -> None:
    assert aplicar_foto([], {1: (CONTRATO, ENVIADO)}, None, None) is None


def test_f067_r7_un_segundo_mas_nueva_ya_es_foto() -> None:
    tramos = aplicar_foto([], {1: (CONTRATO, ENVIADO)}, T1 + timedelta(seconds=1), T1)

    assert tramos is not None and tramos[0].es_linea_base is False


# ===========================================================================
# R6 · la guarda contra una ingesta a medias, en el borde
# ===========================================================================


def _mil_abiertos() -> list[Tramo]:
    return [_abierto(i, FACTURA, FIRMADO) for i in range(1000)]


def test_f067_r6_con_el_97_9_por_ciento_la_foto_falla() -> None:
    actuales = {i: (FACTURA, FIRMADO) for i in range(979)}

    with pytest.raises(FotoIncompletaError) as error:
        aplicar_foto(_mil_abiertos(), actuales, T2, T1)

    mensaje = str(error.value)
    assert "trae 979 documentos" in mensaje and "tiene 1000 tramos abiertos" in mensaje
    assert "menos del 98%." in mensaje, mensaje


def test_f067_r6_con_el_98_por_ciento_justo_la_foto_pasa() -> None:
    actuales = {i: (FACTURA, FIRMADO) for i in range(980)}

    tramos = aplicar_foto(_mil_abiertos(), actuales, T2, T1)

    assert sum(t.motivo_cierre == "DESAPARECIDO" for t in tramos) == 20


def test_f067_r6_los_tipos_ajenos_no_cuentan_para_la_guarda() -> None:
    """979 facturas más un albarán son 979 documentos de la foto, no 980."""
    actuales = {i: (FACTURA, FIRMADO) for i in range(979)} | {5000: (ALBARAN, 1)}

    with pytest.raises(FotoIncompletaError):
        aplicar_foto(_mil_abiertos(), actuales, T2, T1)


def test_f067_r6_los_tramos_cerrados_no_cuentan_como_abiertos() -> None:
    cerrados = [
        Tramo(5000 + i, FACTURA, FIRMADO, T1, T2, None, True, "CAMBIO") for i in range(500)
    ]
    actuales = {i: (FACTURA, FIRMADO) for i in range(980)}

    assert aplicar_foto(_mil_abiertos() + cerrados, actuales, T3, T2) is not None


def test_f067_r6_con_un_solo_tramo_abierto_tambien_hay_guarda() -> None:
    """El borde de abajo: UN tramo abierto y ningún documento es una ingesta
    vacía, no un desaparecido. Lo cazó la campaña de mutación (`> 0` → `> 1`
    sobrevivía: ningún caso tenía exactamente un tramo abierto y cero
    documentos)."""
    with pytest.raises(FotoIncompletaError):
        aplicar_foto([_abierto(1, CONTRATO, ENVIADO)], {}, T2, T1)


def test_f067_r6_en_la_linea_base_no_hay_guarda() -> None:
    """Sin tramos abiertos no hay contra qué medir: la primera foto pasa."""
    assert aplicar_foto([], {}, T1, None) == []


# ===========================================================================
# R8 · los contadores de la foto
# ===========================================================================


def test_f067_r8_el_resumen_cuenta_documentos_cambios_altas_y_desaparecidos() -> None:
    antes = [_abierto(1, CONTRATO, ENVIADO), _abierto(2, FACTURA, FIRMADO)] + [
        _abierto(100 + i, FACTURA, FIRMADO) for i in range(60)
    ]
    actuales = {1: (CONTRATO, FIRMADO), 9: (FACTURA, 1)} | {
        100 + i: (FACTURA, FIRMADO) for i in range(60)
    }

    tramos = aplicar_foto(antes, actuales, T2, T1)

    assert resumir_foto(tramos, T2) == ResumenFoto(
        n_documentos=62, n_cambios=1, n_altas=1, n_desaparecidos=1
    )


def test_f067_r8_cambios_y_desaparecidos_se_cuentan_por_separado() -> None:
    """Con cifras DISTINTAS: tres cambios, un desaparecido y dos altas. Con uno
    de cada, contar «cerrados que no son CAMBIO» daba el mismo 1 y el mutante
    sobrevivía a la campaña."""
    antes = [_abierto(i, CONTRATO, ENVIADO) for i in (1, 2, 3, 4)] + [
        _abierto(100 + i, FACTURA, FIRMADO) for i in range(60)
    ]
    actuales = {1: (CONTRATO, FIRMADO), 2: (CONTRATO, FIRMADO), 3: (CONTRATO, FIRMADO)}
    actuales |= {8: (FACTURA, 1), 9: (FACTURA, 1)}
    actuales |= {100 + i: (FACTURA, FIRMADO) for i in range(60)}

    tramos = aplicar_foto(antes, actuales, T2, T1)

    assert resumir_foto(tramos, T2) == ResumenFoto(
        n_documentos=65, n_cambios=3, n_altas=2, n_desaparecidos=1
    )


def test_f067_r8_en_la_linea_base_todo_son_altas() -> None:
    tramos = aplicar_foto([], {1: (CONTRATO, 1), 2: (FACTURA, 1)}, T1, None)

    assert resumir_foto(tramos, T1) == ResumenFoto(2, 0, 2, 0)


def test_f067_r8_el_resumen_solo_cuenta_lo_de_esa_foto() -> None:
    viejo = Tramo(1, CONTRATO, ENVIADO, T1, T2, None, True, "CAMBIO")
    abierto = _abierto(1, CONTRATO, FIRMADO, desde=T2, antes=T1, base=False)
    viejo_desaparecido = Tramo(3, FACTURA, 1, T1, T2, None, True, "DESAPARECIDO")

    assert resumir_foto([viejo, abierto, viejo_desaparecido], T3) == ResumenFoto(1, 0, 0, 0)


# ===========================================================================
# R10 · los días en el estado
# ===========================================================================


@pytest.mark.parametrize(
    ("desde", "hoy", "dias"),
    [
        (date(2026, 10, 7), date(2026, 10, 7), 0),
        (date(2026, 10, 7), date(2026, 10, 8), 1),
        (date(2026, 10, 7), date(2026, 10, 28), 21),
        (date(2025, 12, 31), date(2026, 1, 1), 1),
    ],
)
def test_f067_r10_dias_en_estado(desde: date, hoy: date, dias: int) -> None:
    assert dias_en_estado(desde, hoy) == dias


# ===========================================================================
# R14 · la fecha de Delphi de `con.tiemod`
# ===========================================================================


def test_f067_r14_la_fila_modificada_el_5_de_octubre() -> None:
    """Medido en Sigrid: 46300,537627 es el 2026-10-05 a las 12:54:10.

    Con la época de SQL Server (1900-01-01) saldría el 7 de octubre, dos días
    después: imposible el día de la medición. La buena es la de Delphi.
    """
    valor = fecha_delphi(46300.537627)

    assert valor is not None
    assert valor.replace(microsecond=0) == datetime(2026, 10, 5, 12, 54, 10)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (1.0, datetime(1899, 12, 31)),
        (0.5, datetime(1899, 12, 30, 12, 0)),
        (2.25, datetime(1900, 1, 1, 6, 0)),
    ],
)
def test_f067_r14_la_hora_va_en_la_parte_decimal(valor: float, esperado: datetime) -> None:
    assert fecha_delphi(valor) == esperado


@pytest.mark.parametrize("valor", [None, 0, 0.0, -1.0])
def test_f067_r14_cero_nulo_o_negativo_no_es_una_fecha(valor: float | None) -> None:
    assert fecha_delphi(valor) is None


def test_f067_r14_el_tramo_es_inmutable() -> None:
    tramo = _abierto(1, CONTRATO, ENVIADO)

    with pytest.raises(AttributeError):
        tramo.estado_id = FIRMADO  # type: ignore[misc]
