# tests/test_f025_precedencia.py
"""
F-025 · Las precedencias, y la invariante que sostiene la feature (R16-R18, R25).

**La invariante:** ningún mecanismo puede SACAR una obra de la lista de
reconstrucción. Los cuatro —completa, sello, sin_filas y firma— solo añaden. La
asimetría es deliberada y tiene un porqué escrito: equivocarse por exceso cuesta
tiempo de CPU una noche; equivocarse por defecto deja un dato viejo publicado sin
que nadie se entere, que es exactamente el modo de fallo de F-052 y lo que esta
feature no puede reintroducir.

Aquí se prueba con el conjunto entero: se toma un censo y se comprueba que
activar cualquier mecanismo produce un superconjunto de lo que había. Un test
por caso probaría lo mismo peor.

Y la precedencia importa por una razón que no es cosmética: el motivo que gana
es el que se escribe en `_meta.obra_build.motivo` y el que va a leer, dentro de
tres meses, quien pregunte por qué la 0599 no se actualizó.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pytest

from etl_sigrid.domain.ventana import (
    DIAS_MAXIMOS_SIN_COMPLETA,
    DOMINGO,
    MOTIVO_COMPLETA,
    MOTIVO_FIRMA,
    MOTIVO_SELLO,
    MOTIVO_SIN_FILAS,
    MOTIVO_VENTANA,
    MOTIVOS,
    Criterio,
    ObraCensada,
    clasificar_obras,
    toca_reconstruccion_completa,
)

HOY = date(2026, 9, 2)
SELLO = "a" * 64
OTRO_SELLO = "b" * 64

CRITERIO = Criterio(
    estados_que_congelan=frozenset({1, 11, 25}),
    patron_codigo="^[0-9]{6}$",
    meses_sin_actividad=12,
)


def congelada(obra_id: int = 1, **extra: object) -> ObraCensada:
    """Una obra que el criterio congela: CERRADA, construida y al día."""
    datos: dict = {
        "obra_id": obra_id,
        "codigo_obra": f"05{obra_id:02d}",
        "estado_id": 25,
        "ultima_actividad": date(2019, 6, 1),
        "tiene_filas": True,
        "registrada": True,
        "sello_registrado": SELLO,
        "firma_origen": "f1",
        "firma_registrada": "f1",
    }
    datos.update(extra)
    return ObraCensada(**datos)  # type: ignore[arg-type]


def plan_de(obras, **kwargs: object):
    return clasificar_obras(obras, CRITERIO, HOY, SELLO, **kwargs)  # type: ignore[arg-type]


#: Un censo variado: vivas, congeladas por cada una de las tres reglas, sin
#: filas, sin registro, con el sello viejo y con la firma movida.
CENSO = (
    congelada(1, estado_id=15, ultima_actividad=date(2026, 8, 1), codigo_obra="0710"),
    congelada(2),
    congelada(3, estado_id=15, codigo_obra="201503", ultima_actividad=HOY),
    congelada(4, estado_id=15, codigo_obra="0711", ultima_actividad=None),
    congelada(5, tiene_filas=False),
    congelada(6, registrada=False),
    congelada(7, sello_registrado=OTRO_SELLO),
    congelada(8, firma_origen="MOVIDA"),
)


# ---------------------------------------------------------------------------
# La invariante: los mecanismos solo AÑADEN
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "encendido", [{"completa": True}, {"rescate": True}], ids=["completa", "rescate"]
)
def test_f025_r18_ningun_mecanismo_saca_una_obra_de_la_lista(
    encendido: dict,
) -> None:
    """**La invariante de la feature.** Encender cualquier mecanismo produce un
    SUPERCONJUNTO de lo que se reconstruía antes, nunca un subconjunto."""
    base = set(plan_de(CENSO).obras_a_reconstruir)
    con_mecanismo = set(plan_de(CENSO, **encendido).obras_a_reconstruir)

    assert base <= con_mecanismo


def test_f025_r17_un_sello_nuevo_solo_puede_ANADIR_obras() -> None:  # noqa: N802
    """Cambiar el SQL nunca puede dejar de reconstruir algo que ya se
    reconstruía."""
    censo_con_sello_viejo = tuple(
        replace(o, sello_registrado=OTRO_SELLO) for o in CENSO
    )

    base = set(plan_de(CENSO).obras_a_reconstruir)
    con_sello = set(plan_de(censo_con_sello_viejo).obras_a_reconstruir)

    assert base <= con_sello
    assert con_sello == {o.obra_id for o in CENSO}


def test_f025_r25_la_completa_es_el_superconjunto_maximo() -> None:
    """No hay nada que pueda reconstruirse más que «todo»."""
    plan = plan_de(CENSO, completa=True)

    assert set(plan.obras_a_reconstruir) == {o.obra_id for o in CENSO}
    assert plan.congelar == ()


# ---------------------------------------------------------------------------
# La precedencia: qué motivo gana, y por qué importa cuál
# ---------------------------------------------------------------------------


def test_f025_r25_completa_gana_a_todo() -> None:
    obra = congelada(1, tiene_filas=False, sello_registrado=OTRO_SELLO,
                     firma_origen="MOVIDA")
    plan = plan_de([obra], completa=True, rescate=True)

    assert plan.reconstruir[0].motivo == MOTIVO_COMPLETA


def test_f025_r18_sin_filas_gana_al_sello() -> None:
    """«No existe» explica mejor que «el sello no coincide», que es su
    consecuencia: una obra sin construir nunca tuvo sello que comparar."""
    obra = congelada(1, tiene_filas=False, sello_registrado=OTRO_SELLO)

    assert plan_de([obra]).reconstruir[0].motivo == MOTIVO_SIN_FILAS


def test_f025_r17_el_sello_gana_a_la_firma() -> None:
    """R17 por encima de R16: si el SQL cambió, da igual que además se haya
    movido el origen. Y el sello reconstruye SIEMPRE; la firma, solo con
    rescate."""
    obra = congelada(1, sello_registrado=OTRO_SELLO, firma_origen="MOVIDA")

    assert plan_de([obra], rescate=True).reconstruir[0].motivo == MOTIVO_SELLO


def test_f025_r16_la_firma_gana_al_criterio_solo_con_rescate() -> None:
    obra = congelada(1, firma_origen="MOVIDA")

    assert plan_de([obra], rescate=True).reconstruir[0].motivo == MOTIVO_FIRMA
    assert plan_de([obra]).obras_congeladas == (1,)


def test_f025_r2_el_criterio_es_el_ultimo_en_decidir() -> None:
    """Cuando ningún mecanismo entra, decide la ventana. Es el caso normal de
    880 de las 920 obras."""
    plan = plan_de([congelada(1), congelada(2, estado_id=15,
                                            ultima_actividad=date(2026, 8, 1),
                                            codigo_obra="0710")])

    assert plan.congelar[0].motivo == MOTIVO_VENTANA
    assert plan.reconstruir[0].motivo == MOTIVO_VENTANA


def test_f025_r1_todo_motivo_emitido_esta_en_la_lista_publicada() -> None:
    """`motivo` viaja a `_meta.obra_build`, que es superficie consultable: un
    valor fuera de la lista sería un contrato roto sin avisar."""
    plan = plan_de(CENSO, rescate=True)

    for decision in plan.reconstruir + plan.congelar:
        assert decision.motivo in MOTIVOS


def test_f025_r1_el_recuento_por_motivo_cuadra_con_las_dos_listas() -> None:
    plan = plan_de(CENSO)

    assert sum(plan.por_motivo.values()) == len(plan.reconstruir) + len(plan.congelar)


# ---------------------------------------------------------------------------
# R25, DA-4 · Cuándo toca la reconstrucción completa
# ---------------------------------------------------------------------------

DOMINGO_2026_09_06 = datetime(2026, 9, 6, 2, 0)
LUNES_2026_09_07 = datetime(2026, 9, 7, 2, 0)


def test_f025_r25_sin_ninguna_completa_registrada_toca() -> None:
    toca, motivo = toca_reconstruccion_completa(None, LUNES_2026_09_07)

    assert toca is True
    assert "ninguna" in motivo


def test_f025_r25_el_domingo_toca() -> None:
    assert DOMINGO_2026_09_06.weekday() == DOMINGO

    toca, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 5, 2, 0), DOMINGO_2026_09_06
    )
    assert toca is True


def test_f025_r25_el_domingo_solo_toca_UNA_vez() -> None:  # noqa: N802
    """Si ya se hizo hoy, no se repite: la completa cuesta lo que costaba la
    nocturna entera, y hacerla dos veces la misma noche vaciaría la hucha de
    créditos, que es la avería que esta feature repara."""
    toca, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 6, 2, 5), datetime(2026, 9, 6, 23, 0)
    )
    assert toca is False


def test_f025_r25_entre_semana_no_toca() -> None:
    toca, motivo = toca_reconstruccion_completa(
        datetime(2026, 9, 6, 2, 0), LUNES_2026_09_07
    )

    assert toca is False
    assert "1.0 dias" in motivo


def test_f025_r25_un_domingo_perdido_lo_recoge_la_antiguedad() -> None:
    """**La red del domingo perdido.** Si el job no corrió ese domingo, la
    completa entra igual el día que se pase de los siete días. Sin esto, las 880
    obras se quedarían congeladas dos semanas y el «hasta 6 días» que el humano
    aceptó dejaría de ser cierto."""
    toca, motivo = toca_reconstruccion_completa(
        datetime(2026, 8, 30, 2, 0), datetime(2026, 9, 8, 2, 0)
    )

    assert toca is True
    assert "maximo" in motivo


def test_f025_r25_justo_en_el_maximo_ya_toca() -> None:
    ultima = datetime(2026, 9, 1, 2, 0)
    ahora = datetime(2026, 9, 1 + DIAS_MAXIMOS_SIN_COMPLETA, 2, 0)

    toca, _ = toca_reconstruccion_completa(ultima, ahora)
    assert toca is True


def test_f025_r25_el_dia_de_la_completa_es_configurable() -> None:
    """`PG_VENTANA_DIA_COMPLETA`: cambiar de día no debe exigir tocar código."""
    miercoles = datetime(2026, 9, 2, 2, 0)
    assert miercoles.weekday() == 2

    toca, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 1, 2, 0), miercoles, dia_semana=2
    )
    assert toca is True

    toca_domingo, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 1, 2, 0), miercoles, dia_semana=DOMINGO
    )
    assert toca_domingo is False


def test_f025_r3_el_tope_de_dias_es_el_que_sostiene_el_HASTA_6_DIAS() -> None:  # noqa: N802
    """**El numero que el humano acepto, cruzado con la constante que lo
    produce.** R3 dice que una obra congelada puede llevar "hasta 6 dias" de
    antiguedad, y eso no es una estimacion: sale de que la reconstruccion
    completa se dispara al llegar a los 7. Si alguien sube la constante a 8, el
    "hasta 6 dias" de la spec, del diccionario y del documento del ecosistema
    deja de ser cierto, y nadie se entera.

    Lo delato la campana de mutacion de T26: `DIAS_MAXIMOS_SIN_COMPLETA = 7 ->
    8` sobrevivia porque ningun test fijaba el valor.
    """
    assert DIAS_MAXIMOS_SIN_COMPLETA == 7

    # Con la completa hecha hace 6 dias todavia NO toca: esa es la antiguedad
    # maxima que puede tener una obra congelada.
    # `dia_semana=DOMINGO` y ninguna de las dos fechas es domingo (el 7 es
    # lunes y el 8, martes): asi lo unico que decide es el tope de dias.
    seis, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 1, 2, 0), datetime(2026, 9, 7, 2, 0), dia_semana=DOMINGO
    )
    assert seis is False, "a los 6 dias todavia no toca: por eso el tope es 6"

    siete, motivo = toca_reconstruccion_completa(
        datetime(2026, 9, 1, 2, 0), datetime(2026, 9, 8, 2, 0), dia_semana=DOMINGO
    )
    assert siete is True
    assert "7" in motivo


def test_f025_r25_el_dia_de_la_semana_se_lee_como_lo_lee_python() -> None:
    """`DOMINGO` tiene que ser el 6 de `date.weekday()` (lunes = 0). Con el
    valor de `isoweekday()` -donde domingo es 7- la completa no se dispararia
    NUNCA por calendario, y solo la salvaria el tope de los siete dias."""
    assert DOMINGO == 6
    assert datetime(2026, 9, 6).weekday() == DOMINGO
    assert datetime(2026, 9, 6).strftime("%w") == "0"


def test_f025_r25_una_completa_del_mismo_dia_no_se_repite_ni_por_horas() -> None:
    """Dos veces la misma noche vaciaria la hucha de creditos de CPU, que es la
    averia que esta feature repara. La comparacion es por FECHA, no por horas
    transcurridas."""
    toca, _ = toca_reconstruccion_completa(
        datetime(2026, 9, 6, 0, 5), datetime(2026, 9, 6, 23, 55)
    )
    assert toca is False
