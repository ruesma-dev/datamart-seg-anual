# tests/test_f127_mayor_analitico.py
"""
F-127 · El mayor analítico (`raw.apa`) en dos esquemas, como F-135.

`contabilidad_restringida` lleva el mayor analítico COMPLETO y sus saldos (08,
09); `contabilidad`, el GENERAL sin lo restringido (10, 11) y solo RECUENTOS de
lo que falta (12). Qué fila analítica es restringida lo dice el oráculo de
`etl_sigrid/domain/restriccion_personal.py` (R7-R9), y el SQL lleva sus mismos
literales (R10).

Ningún test de este fichero abre red ni BBDD: se comprueba el dominio y el
TEXTO del SQL. La ejecución real de los SELECT contra el `raw` de Azure, en una
transacción de solo lectura, está en `progress/impl_F-127.md`.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.restriccion_personal import (
    MOTIVO_APUNTE_RESTRINGIDO,
    MOTIVO_APUNTE_SIN_RESOLVER,
    MOTIVO_ASIENTO_PERSONAL,
    MOTIVO_CONTRAPARTIDA,
    TIPO_ASIENTO_ANALITICO,
    TIPO_ASIENTO_CONTABLE,
    TIPO_ASIENTO_OTRO,
    TIPO_CON_ASIENTO,
    TIPO_CON_ASIENTO_ANALITICO,
    FilaAnalitica,
    centros_de_contrapartida,
    es_apunte_analitico_restringido,
    es_cuenta_contrapartida,
    motivo_apunte_analitico,
    obra_imputada,
    tipo_asiento,
)


def _fila(
    apunte_id: int | None = None,
    resuelto: bool = False,
    restringido: bool = False,
    personal: bool = False,
    cp: bool = False,
) -> FilaAnalitica:
    return FilaAnalitica(
        apunte_id=apunte_id,
        apunte_resuelto=resuelto,
        apunte_restringido=restringido,
        asiento_personal=personal,
        cuenta_es_contrapartida=cp,
    )


# ===========================================================================
# R3 · el tipo del asiento (`con.tip`)
# ===========================================================================


def test_f127_r3_los_literales_de_con_tip() -> None:
    """Escritos A MANO: 20 es el asiento contable y 32 el analítico puro."""
    assert (TIPO_CON_ASIENTO, TIPO_CON_ASIENTO_ANALITICO) == (20, 32)
    assert (TIPO_ASIENTO_CONTABLE, TIPO_ASIENTO_ANALITICO, TIPO_ASIENTO_OTRO) == (
        "CONTABLE", "ANALITICO", "OTRO",
    )


@pytest.mark.parametrize(
    ("tip", "esperado"),
    [(20, "CONTABLE"), (32, "ANALITICO"), (16, "OTRO"), (19, "OTRO"), (0, "OTRO"),
     (None, "OTRO"), (21, "OTRO"), (31, "OTRO"), (33, "OTRO")],
)
def test_f127_r3_tipo_de_asiento(tip: int | None, esperado: str) -> None:
    assert tipo_asiento(tip) == esperado


# ===========================================================================
# R7 · qué fila analítica es restringida (C1, C2, C3)
# ===========================================================================


def test_f127_r7_una_fila_sin_nada_es_visible() -> None:
    assert not es_apunte_analitico_restringido(_fila())
    assert not es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True))


def test_f127_r7_c1_apunte_restringido() -> None:
    assert es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True, restringido=True))


def test_f127_r7_c2_asiento_de_personal() -> None:
    assert es_apunte_analitico_restringido(_fila(apunte_id=7, resuelto=True, personal=True))


def test_f127_r7_c3_cuenta_de_contrapartida() -> None:
    """También sin apunte financiero: el abono de los asientos `ANALITICO`."""
    assert es_apunte_analitico_restringido(_fila(cp=True))


@pytest.mark.parametrize("cp", [False, True])
@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("restringido", [False, True])
def test_f127_r7_cualquiera_de_las_tres_restringe(cp: bool, personal: bool, restringido: bool) -> None:
    fila = _fila(apunte_id=7, resuelto=True, restringido=restringido, personal=personal, cp=cp)
    assert es_apunte_analitico_restringido(fila) == (cp or personal or restringido)


# --- C3 con D7-b: la CP actual del recurso o una cuenta antigua de su centro ---


def test_f127_r7_c3_la_cp_actual_del_recurso() -> None:
    assert es_cuenta_contrapartida(
        10, centro_coste_id=None, abonada_en_analitico=False,
        contrapartidas={10, 11}, centros_contrapartida=frozenset(),
    )


def test_f127_r7_c3_d7_cuenta_antigua_del_centro_de_cp_con_abono_analitico() -> None:
    """D7-b: una cuenta de un centro de CP con abono en un asiento `ANALITICO`
    es una CP de antes que el recurso ya no declara: falla cerrado."""
    assert es_cuenta_contrapartida(
        99, centro_coste_id=5, abonada_en_analitico=True,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


@pytest.mark.parametrize(
    ("centro", "abonada"),
    [(5, False), (6, True), (None, True), (None, False)],
    ids=["centro-cp-sin-abono", "centro-de-obra", "sin-centro", "nada"],
)
def test_f127_r7_c3_d7_no_alcanza_a_otras_cuentas(centro: int | None, abonada: bool) -> None:
    """Sin abono analítico, o en un centro de obra (los 9 cargos corregidos de
    D7), o sin centro: no es CP."""
    assert not es_cuenta_contrapartida(
        99, centro_coste_id=centro, abonada_en_analitico=abonada,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


def test_f127_r7_c3_sin_cuenta_no_es_cp() -> None:
    """`cueide = 0` (NULL): no es CP aunque su centro lo sea."""
    assert not es_cuenta_contrapartida(
        None, centro_coste_id=5, abonada_en_analitico=True,
        contrapartidas={10}, centros_contrapartida=frozenset({5}),
    )


def test_f127_r7_c3_los_centros_de_cp_son_los_de_las_cp_actuales() -> None:
    centro_de_cuenta = {10: 5, 11: 5, 12: 8, 13: None, 20: 6}
    assert centros_de_contrapartida({10, 11, 12, 13, 14}, centro_de_cuenta) == frozenset({5, 8})


def test_f127_r7_c3_sin_cp_no_hay_centros() -> None:
    assert centros_de_contrapartida(set(), {10: 5}) == frozenset()


# ===========================================================================
# R8 · la precedencia del motivo
# ===========================================================================


def test_f127_r8_visible_no_tiene_motivo() -> None:
    assert motivo_apunte_analitico(_fila(apunte_id=7, resuelto=True)) is None
    assert motivo_apunte_analitico(_fila()) is None


@pytest.mark.parametrize(
    ("fila", "motivo"),
    [
        (_fila(apunte_id=7, resuelto=True, restringido=True, personal=True, cp=True), "CONTRAPARTIDA"),
        (_fila(apunte_id=7, resuelto=False, personal=True, cp=True), "CONTRAPARTIDA"),
        (_fila(apunte_id=7, resuelto=False, personal=True), "APUNTE_SIN_RESOLVER"),
        (_fila(apunte_id=7, resuelto=True, restringido=True, personal=True), "APUNTE_RESTRINGIDO"),
        (_fila(apunte_id=7, resuelto=True, restringido=True), "APUNTE_RESTRINGIDO"),
        (_fila(apunte_id=7, resuelto=True, personal=True), "ASIENTO_PERSONAL"),
        (_fila(personal=True), "ASIENTO_PERSONAL"),
        (_fila(cp=True), "CONTRAPARTIDA"),
    ],
)
def test_f127_r8_precedencia(fila: FilaAnalitica, motivo: str) -> None:
    """CONTRAPARTIDA > APUNTE_SIN_RESOLVER > APUNTE_RESTRINGIDO > ASIENTO_PERSONAL."""
    assert motivo_apunte_analitico(fila) == motivo


def test_f127_r8_los_literales_de_motivo() -> None:
    assert (
        MOTIVO_CONTRAPARTIDA, MOTIVO_APUNTE_SIN_RESOLVER, MOTIVO_APUNTE_RESTRINGIDO,
        MOTIVO_ASIENTO_PERSONAL,
    ) == ("CONTRAPARTIDA", "APUNTE_SIN_RESOLVER", "APUNTE_RESTRINGIDO", "ASIENTO_PERSONAL")


# ===========================================================================
# R9 · falla cerrado: el apunte que no está en el mayor completo
# ===========================================================================


def test_f127_r9_apunte_sin_resolver_es_restringido() -> None:
    fila = _fila(apunte_id=7, resuelto=False)
    assert motivo_apunte_analitico(fila) == MOTIVO_APUNTE_SIN_RESOLVER
    assert es_apunte_analitico_restringido(fila)


def test_f127_r9_sin_apunte_financiero_no_es_sin_resolver() -> None:
    """`apuide = 0` (los asientos `ANALITICO`): no hay apunte que resolver."""
    assert motivo_apunte_analitico(_fila(apunte_id=None, resuelto=False)) is None


# ===========================================================================
# R6 · la obra imputada de un asiento ANALITICO (D4)
# ===========================================================================


@pytest.mark.parametrize(
    ("obras", "esperada"),
    [
        ([4, 4, 4], 4),
        ([4, None, 4], 4),
        ([4], 4),
        ([4, 5], None),
        ([None, None], None),
        ([], None),
    ],
    ids=["una", "una-y-sin-obra", "sola", "dos", "ninguna", "vacio"],
)
def test_f127_r6_la_unica_obra_de_cargo(obras: list[int | None], esperada: int | None) -> None:
    assert obra_imputada(obras) == esperada
