# tests/test_f025_ventana.py
"""
F-025 · El criterio de obra congelada, en dominio puro (R1, R2, R3, R18).

**Lo que estos tests protegen, en una frase del humano:** *«que no se
reconstruyan las obras cerradas, pero que no se borren, y que la información
esté consultable»*. Aquí se cubre la primera mitad —quién se reconstruye y quién
no, y por qué—; que no se borre es `tests/test_f025_build.py`.

Un superviviente aquí es **una obra que se congela cuando no debía**, o al revés:
una obra viva que deja de actualizarse sin que nadie lo sepa. Por eso la feature
lleva campaña de mutación sobre `domain/ventana.py` (DA-6) además de las cinco
huellas.

El criterio lo fijó el humano el 2026-09-02 (DA-1) y son **tres reglas en
UNIÓN**: estado EN ESTUDIO (1), NO PRESENTADA (11) o CERRADA (25); código de
seis dígitos; o sin actividad en 12 meses. Ninguna de las tres se toca aquí sin
volver a preguntarle.

Sin BBDD, sin ficheros y sin reloj del sistema: `hoy` entra siempre por
parámetro, porque un test que dependa de la fecha real deja de probar lo mismo
mañana.
"""

from __future__ import annotations

from datetime import date

import pytest

from etl_sigrid.domain.ventana import (
    MOTIVO_COMPLETA,
    MOTIVO_FIRMA,
    MOTIVO_SELLO,
    MOTIVO_SIN_FILAS,
    MOTIVO_VENTANA,
    Criterio,
    ObraCensada,
    clasificar_obras,
    motivo_de_congelacion,
)

HOY = date(2026, 9, 2)

#: El criterio decidido por el humano (DA-1). Se construye aquí a mano, y no se
#: lee de `business_rules.yaml`, para que un cambio accidental en el YAML rompa
#: `tests/test_f025_settings.py` —que es quien lo vigila— y no estos, que son
#: sobre la lógica.
CRITERIO = Criterio(
    estados_que_congelan=frozenset({1, 11, 25}),
    patron_codigo="^[0-9]{6}$",
    meses_sin_actividad=12,
)

SELLO = "a" * 64
OTRO_SELLO = "b" * 64


def obra(
    obra_id: int = 1,
    codigo_obra: str = "0710",
    estado_id: int | None = 15,
    ultima_actividad: date | None = date(2026, 8, 1),
    **extra: object,
) -> ObraCensada:
    """Una obra VIVA por defecto: EN CURSO, código de cuatro dígitos y actividad
    del mes pasado. Cada test cambia solo lo que quiere probar."""
    datos: dict = {
        "obra_id": obra_id,
        "codigo_obra": codigo_obra,
        "estado_id": estado_id,
        "ultima_actividad": ultima_actividad,
        "tiene_filas": True,
        "registrada": True,
        "sello_registrado": SELLO,
        "firma_origen": "f1",
        "firma_registrada": "f1",
    }
    datos.update(extra)
    return ObraCensada(**datos)  # type: ignore[arg-type]


def plan_de(*obras: ObraCensada, **kwargs: object):
    return clasificar_obras(
        obras, CRITERIO, HOY, SELLO, **kwargs  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# R2 · Las tres reglas, cada una por separado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("estado", [1, 11, 25])
def test_f025_r2_regla_1_los_tres_estados_congelan(estado: int) -> None:
    """EN ESTUDIO (1), NO PRESENTADA (11) y CERRADA (25). El catálogo está
    verificado contra `conest` tipo 42 (DA-1 bis): no es una suposición."""
    assert motivo_de_congelacion(obra(estado_id=estado), CRITERIO, HOY) is not None


@pytest.mark.parametrize("estado", [9, 15, 17, 19, 21, 23, 999])
def test_f025_r2_regla_1_los_demas_estados_no_congelan_por_si_solos(
    estado: int,
) -> None:
    """Los otros siete estados con obras vivas en el catálogo. Que no congelen
    POR ESTADO no significa que no caigan por las otras dos reglas."""
    assert motivo_de_congelacion(obra(estado_id=estado), CRITERIO, HOY) is None


def test_f025_r2_regla_2_seis_digitos_congela_aunque_este_viva() -> None:
    """DA-3: 222 obras administrativas, y NINGUNA llega al fact."""
    motivo = motivo_de_congelacion(
        obra(codigo_obra="201503", estado_id=15, ultima_actividad=HOY),
        CRITERIO,
        HOY,
    )
    assert motivo is not None
    assert "seis" in motivo or "dígitos" in motivo or "digitos" in motivo


@pytest.mark.parametrize("codigo", ["0710", "12345", "1234567", "07100", "A12345"])
def test_f025_r2_regla_2_solo_seis_digitos_exactos(codigo: str) -> None:
    """Cinco dígitos no, siete tampoco, y una letra delante menos. El patrón va
    anclado por los dos extremos o congelaría media obra del maestro."""
    assert motivo_de_congelacion(obra(codigo_obra=codigo), CRITERIO, HOY) is None


def test_f025_r2_regla_3_sin_actividad_en_doce_meses_congela() -> None:
    assert (
        motivo_de_congelacion(
            obra(ultima_actividad=date(2025, 3, 1)), CRITERIO, HOY
        )
        is not None
    )


def test_f025_r2_regla_3_una_obra_sin_ninguna_fase_esta_sin_actividad() -> None:
    """217 obras del universo no tienen ni una fase. `None` no es «reciente»."""
    assert motivo_de_congelacion(obra(ultima_actividad=None), CRITERIO, HOY) is not None


def test_f025_r2_regla_3_el_limite_de_los_doce_meses_no_congela() -> None:
    """Justo en el borde se considera CON actividad: se prefiere trabajar de más
    a dejar un dato viejo, que es el modo de fallo de F-052."""
    assert (
        motivo_de_congelacion(
            obra(ultima_actividad=date(2025, 9, 2)), CRITERIO, HOY
        )
        is None
    )


def test_f025_r2_un_dia_antes_del_limite_si_congela() -> None:
    assert (
        motivo_de_congelacion(
            obra(ultima_actividad=date(2025, 9, 1)), CRITERIO, HOY
        )
        is not None
    )


def test_f025_r2_las_tres_reglas_van_en_UNION_no_en_interseccion() -> None:  # noqa: N802
    """Basta con UNA. Una obra EN CURSO, con código de cuatro dígitos y con
    actividad de ayer es la única que se salva."""
    viva = obra(estado_id=15, codigo_obra="0710", ultima_actividad=date(2026, 9, 1))
    assert motivo_de_congelacion(viva, CRITERIO, HOY) is None

    for cambio in (
        {"estado_id": 25},
        {"codigo_obra": "201503"},
        {"ultima_actividad": date(2020, 1, 1)},
    ):
        base: dict = {
            "estado_id": 15,
            "codigo_obra": "0710",
            "ultima_actividad": date(2026, 9, 1),
        }
        base.update(cambio)
        assert motivo_de_congelacion(obra(**base), CRITERIO, HOY) is not None, cambio


# ---------------------------------------------------------------------------
# R1 · El plan: dos listas y el MOTIVO de cada obra
# ---------------------------------------------------------------------------


def test_f025_r1_el_plan_separa_reconstruir_de_congelar() -> None:
    plan = plan_de(obra(1, "0710"), obra(2, "0599", estado_id=25))

    assert plan.obras_a_reconstruir == (1,)
    assert plan.obras_congeladas == (2,)


def test_f025_r1_toda_obra_lleva_su_motivo_escrito() -> None:
    """R1 lo exige literalmente: «dejar escrito el motivo de cada una». Un plan
    sin motivos convierte el «por qué no se actualizó la 0599» en arqueología."""
    plan = plan_de(obra(1, "0710"), obra(2, "0599", estado_id=25))

    for decision in plan.reconstruir + plan.congelar:
        assert decision.motivo
        assert decision.detalle.strip(), (
            f"la obra {decision.codigo_obra} no dice POR QUE se decidió lo que "
            f"se decidió"
        )


def test_f025_r1_es_una_funcion_pura_y_no_pierde_ni_duplica_obras() -> None:
    """Partición: cada obra en exactamente una de las dos listas."""
    obras = [obra(i, f"07{i:02d}", estado_id=25 if i % 2 else 15) for i in range(1, 11)]
    plan = plan_de(*obras)

    ids = sorted(plan.obras_a_reconstruir + plan.obras_congeladas)
    assert ids == [o.obra_id for o in obras]
    assert not set(plan.obras_a_reconstruir) & set(plan.obras_congeladas)


def test_f025_r1_el_mismo_censo_da_el_mismo_plan() -> None:
    """Determinista: sin esto, dos noches seguidas podrían reconstruir cosas
    distintas con el mismo dato delante."""
    obras = [obra(3, "0003"), obra(1, "0001", estado_id=25), obra(2, "0002")]
    assert plan_de(*obras) == plan_de(*obras)


def test_f025_r1_un_censo_vacio_da_un_plan_vacio() -> None:
    """R9: sin obras que reconstruir el sub-paso no toca la tabla. Que esto
    devuelva un plan vacío en vez de reventar es lo que lo hace posible."""
    plan = plan_de()

    assert plan.obras_a_reconstruir == ()
    assert plan.obras_congeladas == ()


# ---------------------------------------------------------------------------
# R18 · No se congela lo que no está construido
# ---------------------------------------------------------------------------


def test_f025_r18_una_obra_congelada_sin_filas_se_reconstruye() -> None:
    """«Completar no es actualizar»: una obra cerrada que no está en la tabla
    tiene que entrar, o la ventana la dejaría fuera para siempre."""
    plan = plan_de(obra(1, "0599", estado_id=25, tiene_filas=False))

    assert plan.obras_a_reconstruir == (1,)
    assert plan.reconstruir[0].motivo == MOTIVO_SIN_FILAS


def test_f025_r18_una_obra_sin_registro_se_reconstruye() -> None:
    """«O el registro no la cubre». Una obra que nunca pasó por
    `_meta.obra_build` no tiene con qué comparar nada."""
    plan = plan_de(obra(1, "0599", estado_id=25, registrada=False))

    assert plan.obras_a_reconstruir == (1,)
    assert plan.reconstruir[0].motivo == MOTIVO_SIN_FILAS


# ---------------------------------------------------------------------------
# R17 · El sello del SQL: si cambia, se reconstruye TODO
# ---------------------------------------------------------------------------


def test_f025_r17_un_sello_distinto_reconstruye_una_obra_congelada() -> None:
    """Sin esto, un arreglo de SQL como el de F-052 solo alcanzaría a las 40
    obras vivas y las otras 880 seguirían publicando lo de antes."""
    plan = plan_de(obra(1, "0599", estado_id=25, sello_registrado=OTRO_SELLO))

    assert plan.obras_a_reconstruir == (1,)
    assert plan.reconstruir[0].motivo == MOTIVO_SELLO


def test_f025_r17_el_sello_alcanza_a_TODAS_las_congeladas() -> None:  # noqa: N802
    congeladas = [
        obra(i, f"20150{i}", estado_id=25, sello_registrado=OTRO_SELLO)
        for i in range(1, 6)
    ]
    plan = plan_de(*congeladas)

    assert len(plan.reconstruir) == 5
    assert plan.congelar == ()


# ---------------------------------------------------------------------------
# R16, §3.1 · La firma DENUNCIA, no rescata
# ---------------------------------------------------------------------------


def test_f025_r16_una_firma_distinta_NO_reconstruye_por_su_cuenta() -> None:  # noqa: N802
    """**El punto más delicado de la feature.** El humano congela 40 obras con
    actividad reciente sabiéndolo (R3) y acepta hasta 6 días de antigüedad:
    rescatarlas aquí contradiría su decisión."""
    plan = plan_de(
        obra(1, "0599", estado_id=25, firma_origen="NUEVA", firma_registrada="f1")
    )

    assert plan.obras_a_reconstruir == ()
    assert plan.obras_congeladas == (1,)


def test_f025_r16_pero_la_nombra() -> None:
    """Denuncia: el modo de fallo a impedir es el de F-052, un dato que
    envejece sin que nadie se entere (R28)."""
    plan = plan_de(
        obra(1, "0599", estado_id=25, firma_origen="NUEVA", firma_registrada="f1")
    )

    assert [d.codigo_obra for d in plan.denunciadas] == ["0599"]
    assert plan.congelar[0].firma_divergente is True


def test_f025_r16_una_obra_congelada_que_no_cambia_no_se_denuncia() -> None:
    plan = plan_de(obra(1, "0599", estado_id=25))

    assert plan.denunciadas == ()


def test_f025_r16_con_rescate_activado_si_se_reconstruye() -> None:
    """El interruptor `PG_VENTANA_RESCATE` (default off) por si el humano
    cambia de idea, y sin tocar código."""
    plan = plan_de(
        obra(1, "0599", estado_id=25, firma_origen="NUEVA", firma_registrada="f1"),
        rescate=True,
    )

    assert plan.obras_a_reconstruir == (1,)
    assert plan.reconstruir[0].motivo == MOTIVO_FIRMA


def test_f025_r16_el_rescate_no_toca_a_las_obras_cuya_firma_no_cambia() -> None:
    plan = plan_de(obra(1, "0599", estado_id=25), rescate=True)

    assert plan.obras_congeladas == (1,)


# ---------------------------------------------------------------------------
# R25, DA-4 · La reconstrucción completa lo reconstruye todo
# ---------------------------------------------------------------------------


def test_f025_r25_la_completa_reconstruye_hasta_lo_mas_congelado() -> None:
    plan = plan_de(
        obra(1, "201503", estado_id=25, ultima_actividad=None), completa=True
    )

    assert plan.obras_a_reconstruir == (1,)
    assert plan.congelar == ()
    assert plan.reconstruir[0].motivo == MOTIVO_COMPLETA


def test_f025_r25_la_completa_tambien_deja_escrito_su_motivo() -> None:
    plan = plan_de(obra(1, "0710"), completa=True)
    assert plan.reconstruir[0].motivo == MOTIVO_COMPLETA


# ---------------------------------------------------------------------------
# R5 · Con la ventana desactivada, el comportamiento es el de hoy
# ---------------------------------------------------------------------------


def test_f025_r5_una_obra_viva_se_reconstruye_por_la_ventana() -> None:
    """El motivo `ventana` no es solo para congelar: también dice por qué una
    obra viva entra."""
    plan = plan_de(obra(1, "0710"))

    assert plan.reconstruir[0].motivo == MOTIVO_VENTANA
    assert plan.reconstruir[0].firma_divergente is False


# ---------------------------------------------------------------------------
# El criterio, como objeto de configuración
# ---------------------------------------------------------------------------


def test_f025_r2_un_criterio_sin_meses_no_es_criterio() -> None:
    with pytest.raises(ValueError, match="meses"):
        Criterio(
            estados_que_congelan=frozenset({25}),
            patron_codigo="^[0-9]{6}$",
            meses_sin_actividad=0,
        )


def test_f025_r2_un_patron_de_codigo_invalido_falla_al_construir_no_al_usar() -> None:
    """Sale de un YAML editable a mano: si no compila, se dice aquí y no en
    mitad de la nocturna.

    El patrón de prueba es un juego de corchetes sin cerrar y no `^[0-9]{6`,
    que era el candidato obvio: Python trata una llave sin cerrar como carácter
    literal y lo acepta sin rechistar, así que ese ejemplo no probaba nada.
    """
    with pytest.raises(ValueError, match="patrón|patron"):
        Criterio(
            estados_que_congelan=frozenset({25}),
            patron_codigo="^[0-9",
            meses_sin_actividad=12,
        )


def test_f025_r2_un_criterio_sin_ninguna_regla_de_estado_sigue_siendo_valido() -> None:
    """Vaciar la lista de estados es una decisión legítima de Negocio: quedan
    las otras dos reglas. Lo que no es legítimo es que reviente en producción."""
    criterio = Criterio(
        estados_que_congelan=frozenset(),
        patron_codigo="^[0-9]{6}$",
        meses_sin_actividad=12,
    )
    assert motivo_de_congelacion(obra(estado_id=25), criterio, HOY) is None
