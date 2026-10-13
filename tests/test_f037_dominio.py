# tests/test_f037_dominio.py
"""
F-037 · El criterio de personal, el estado y el signo de un efecto (R1-R4, R25 bis).

Es el oráculo de `tesoreria_restringida.efectos`: el SQL de
`01_efectos_completo.sql` NO llama a este módulo, pero lleva los mismos
literales, y `test_f037_sql.py` los compara uno a uno (R2).

Ningún test de este fichero abre red ni BBDD.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from etl_sigrid.domain import restriccion_personal
from etl_sigrid.domain.tesoreria import (
    ANIOS_PREVISTO_ANTIGUO,
    EST_PAGADO,
    EST_SUSTITUIDO,
    ESTADO_BAJA,
    ESTADO_PREVISTO,
    ESTADO_REALIZADO,
    MOTIVO_CUENTA,
    MOTIVO_CUENTA_SIN_RESOLVER,
    MOTIVO_DOCUMENTO_NOMINA,
    MOTIVO_NATURALEZA,
    MOTIVO_TERCERO_EMPLEADO,
    MOTIVOS_EN_ORDEN,
    REGEX_CUENTA_RESTRINGIDA,
    SENTIDO_COBRO,
    SENTIDO_PAGO,
    TIP_DOCUMENTO_NOMINA,
    TIP_EFECTO_COBRO,
    TIP_EFECTO_PAGO,
    TIP_TERCERO_EMPLEADO,
    EfectoTesoreria,
    es_efecto_restringido,
    es_previsto_antiguo,
    estado_tesoreria,
    fecha_limite_previsto_antiguo,
    importe_flujo,
    motivo_restriccion_efecto,
)


def _ef(
    natide: int | None = None,
    cuenta_id: int | None = None,
    codigo_cuenta: str | None = None,
    tip_tercero: int | None = None,
    tip_documento: int | None = None,
) -> EfectoTesoreria:
    return EfectoTesoreria(
        natide=natide,
        cuenta_id=cuenta_id,
        codigo_cuenta=codigo_cuenta,
        tip_tercero=tip_tercero,
        tip_documento=tip_documento,
    )


# ===========================================================================
# Constantes: los valores medidos y aprobados, escritos A MANO a propósito
# ===========================================================================

def test_f037_r1_constantes_de_sigrid() -> None:
    assert (SENTIDO_PAGO, SENTIDO_COBRO) == ("PAGO", "COBRO")
    assert (TIP_EFECTO_PAGO, TIP_EFECTO_COBRO) == (25, 24)
    assert TIP_TERCERO_EMPLEADO == 43
    assert TIP_DOCUMENTO_NOMINA == 306
    assert EST_PAGADO == 10
    assert EST_SUSTITUIDO == (14, 15)
    assert (ESTADO_PREVISTO, ESTADO_REALIZADO, ESTADO_BAJA) == (
        "PREVISTO", "REALIZADO", "BAJA",
    )
    assert ANIOS_PREVISTO_ANTIGUO == 2


def test_f037_r1_motivos_y_su_precedencia() -> None:
    assert MOTIVOS_EN_ORDEN == (
        "NATURALEZA", "CUENTA", "CUENTA_SIN_RESOLVER",
        "TERCERO_EMPLEADO", "DOCUMENTO_NOMINA",
    )
    assert MOTIVOS_EN_ORDEN == (
        MOTIVO_NATURALEZA, MOTIVO_CUENTA, MOTIVO_CUENTA_SIN_RESOLVER,
        MOTIVO_TERCERO_EMPLEADO, MOTIVO_DOCUMENTO_NOMINA,
    )


def test_f037_r2_la_regex_es_la_de_f135_no_una_copia() -> None:
    """R2: el mismo objeto, importado; no un literal reescrito."""
    assert REGEX_CUENTA_RESTRINGIDA is restriccion_personal.REGEX_CUENTA_RESTRINGIDA
    texto = (
        Path(__file__).resolve().parents[1] / "etl_sigrid" / "domain" / "tesoreria.py"
    ).read_text(encoding="utf-8")
    assert "4753" not in texto, "los prefijos viven en restriccion_personal"
    assert "from etl_sigrid.domain.restriccion_personal import" in texto


def test_f037_r1_el_dominio_no_importa_infraestructura() -> None:
    texto = (
        Path(__file__).resolve().parents[1] / "etl_sigrid" / "domain" / "tesoreria.py"
    ).read_text(encoding="utf-8")
    assert texto.splitlines()[0] == "# etl_sigrid/domain/tesoreria.py"
    assert "infrastructure" not in texto
    assert "psycopg" not in texto


def test_f037_r1_el_efecto_es_inmutable() -> None:
    e = _ef(natide=1)
    with pytest.raises(AttributeError):
        e.natide = 0  # type: ignore[misc]


# ===========================================================================
# R1 · cada motivo, solo
# ===========================================================================

def test_f037_r1_sin_nada_no_es_de_personal() -> None:
    e = _ef()
    assert motivo_restriccion_efecto(e) is None
    assert es_efecto_restringido(e) is False


def test_f037_r1_ceros_no_son_informados() -> None:
    """`natide = 0` y `cueide = 0` son «sin valor», como `NULLIF(x, 0)` del SQL."""
    e = _ef(natide=0, cuenta_id=0, codigo_cuenta=None, tip_tercero=5, tip_documento=15)
    assert motivo_restriccion_efecto(e) is None
    assert es_efecto_restringido(e) is False


@pytest.mark.parametrize("natide", [1, 2, 3, 999_999])
def test_f037_r1_naturaleza_sola(natide: int) -> None:
    e = _ef(natide=natide)
    assert motivo_restriccion_efecto(e) == "NATURALEZA"
    assert es_efecto_restringido(e) is True


@pytest.mark.parametrize("codigo", ["465", "4650001", "466000123", "4753", "47530001", "640"])
def test_f037_r1_cuenta_sola(codigo: str) -> None:
    e = _ef(cuenta_id=7, codigo_cuenta=codigo)
    assert motivo_restriccion_efecto(e) == "CUENTA"
    assert es_efecto_restringido(e) is True


@pytest.mark.parametrize("codigo", ["4751", "47510001", "4752", "400000123", "410", "475", "5720"])
def test_f037_r1_cuentas_que_no_son_de_personal(codigo: str) -> None:
    """`4751` no y `4753` sí: el criterio de F-135, importado (D12 de F-135)."""
    assert motivo_restriccion_efecto(_ef(cuenta_id=7, codigo_cuenta=codigo)) is None


def test_f037_r1_cuenta_sin_resolver_falla_cerrado() -> None:
    e = _ef(cuenta_id=7, codigo_cuenta=None)
    assert motivo_restriccion_efecto(e) == "CUENTA_SIN_RESOLVER"
    assert es_efecto_restringido(e) is True


def test_f037_r1_tercero_empleado_solo() -> None:
    e = _ef(tip_tercero=43)
    assert motivo_restriccion_efecto(e) == "TERCERO_EMPLEADO"
    assert es_efecto_restringido(e) is True


@pytest.mark.parametrize("tip", [5, 42, 44, 306, None])
def test_f037_r1_otro_tercero_no_restringe(tip: int | None) -> None:
    assert motivo_restriccion_efecto(_ef(tip_tercero=tip)) is None


def test_f037_r1_documento_nomina_solo() -> None:
    e = _ef(tip_documento=306)
    assert motivo_restriccion_efecto(e) == "DOCUMENTO_NOMINA"
    assert es_efecto_restringido(e) is True


@pytest.mark.parametrize("tip", [11, 15, 43, 305, 307, None])
def test_f037_r1_otro_documento_no_restringe(tip: int | None) -> None:
    assert motivo_restriccion_efecto(_ef(tip_documento=tip)) is None


# ===========================================================================
# R1 · precedencia NATURALEZA > CUENTA > CUENTA_SIN_RESOLVER > TERCERO > DOCUMENTO
# ===========================================================================

def test_f037_r1_los_cuatro_a_la_vez_es_naturaleza() -> None:
    """El caso medido de 32.807 pagos: los cuatro criterios a la vez."""
    e = _ef(natide=1, cuenta_id=7, codigo_cuenta="4650001", tip_tercero=43, tip_documento=306)
    assert motivo_restriccion_efecto(e) == "NATURALEZA"


def test_f037_r1_cuenta_gana_a_tercero_y_documento() -> None:
    e = _ef(cuenta_id=7, codigo_cuenta="4650001", tip_tercero=43, tip_documento=306)
    assert motivo_restriccion_efecto(e) == "CUENTA"


def test_f037_r1_sin_resolver_gana_a_tercero_y_documento() -> None:
    e = _ef(cuenta_id=7, codigo_cuenta=None, tip_tercero=43, tip_documento=306)
    assert motivo_restriccion_efecto(e) == "CUENTA_SIN_RESOLVER"


def test_f037_r1_tercero_gana_a_documento() -> None:
    e = _ef(tip_tercero=43, tip_documento=306)
    assert motivo_restriccion_efecto(e) == "TERCERO_EMPLEADO"


def test_f037_r1_naturaleza_gana_a_sin_resolver() -> None:
    e = _ef(natide=3, cuenta_id=7, codigo_cuenta=None)
    assert motivo_restriccion_efecto(e) == "NATURALEZA"


def test_f037_r1_cuenta_normal_no_tapa_al_tercero() -> None:
    """Una cuenta resuelta y no restringida no corta la cascada."""
    e = _ef(cuenta_id=7, codigo_cuenta="400000123", tip_documento=306)
    assert motivo_restriccion_efecto(e) == "DOCUMENTO_NOMINA"


# ===========================================================================
# R3 · el estado, igual en los dos sentidos (precedencia de F-094)
# ===========================================================================

def test_f037_r3_sin_nada_es_previsto() -> None:
    assert estado_tesoreria(est=1, fecrea=0, fecbaj=0) == "PREVISTO"


def test_f037_r3_none_y_cero_son_iguales() -> None:
    assert estado_tesoreria(est=None, fecrea=None, fecbaj=None) == "PREVISTO"
    assert estado_tesoreria(est=None, fecrea=0, fecbaj=None) == "PREVISTO"
    assert estado_tesoreria(est=1, fecrea=None, fecbaj=0) == "PREVISTO"


def test_f037_r3_fecha_real_es_realizado() -> None:
    assert estado_tesoreria(est=1, fecrea=20240115, fecbaj=0) == "REALIZADO"


def test_f037_r3_est_10_sin_fecrea_es_realizado() -> None:
    """Desde 2020 el pago por remesa deja `est = 10` sin `fecrea` (41.884 pagos)."""
    assert estado_tesoreria(est=10, fecrea=0, fecbaj=0) == "REALIZADO"
    assert estado_tesoreria(est=10, fecrea=None, fecbaj=None) == "REALIZADO"


@pytest.mark.parametrize("est", [9, 11, 13, 16])
def test_f037_r3_estados_vecinos_no_cambian_nada(est: int) -> None:
    assert estado_tesoreria(est=est, fecrea=0, fecbaj=0) == "PREVISTO"


def test_f037_r3_baja_por_fecha_de_baja() -> None:
    assert estado_tesoreria(est=1, fecrea=0, fecbaj=20240115) == "BAJA"


@pytest.mark.parametrize("est", [14, 15])
def test_f037_r3_est_14_15_sin_fecbaj_es_baja(est: int) -> None:
    assert estado_tesoreria(est=est, fecrea=0, fecbaj=0) == "BAJA"
    assert estado_tesoreria(est=est, fecrea=None, fecbaj=None) == "BAJA"


def test_f037_r3_baja_gana_a_realizado() -> None:
    """fecbaj y fecrea a la vez: BAJA (F-094)."""
    assert estado_tesoreria(est=1, fecrea=20240115, fecbaj=20240120) == "BAJA"
    assert estado_tesoreria(est=10, fecrea=20240115, fecbaj=20240120) == "BAJA"
    assert estado_tesoreria(est=14, fecrea=20240115, fecbaj=0) == "BAJA"


# ===========================================================================
# R4 · importe_flujo: + en COBRO, - en PAGO, con el signo de origen
# ===========================================================================

def test_f037_r4_cobro_es_positivo() -> None:
    assert importe_flujo("COBRO", Decimal("1234.56")) == Decimal("1234.56")


def test_f037_r4_pago_es_negativo() -> None:
    assert importe_flujo("PAGO", Decimal("1234.56")) == Decimal("-1234.56")


def test_f037_r4_negativos_conservan_su_signo() -> None:
    """Un abono (importe negativo) invierte el flujo; no se toma el valor absoluto."""
    assert importe_flujo("PAGO", Decimal("-50.00")) == Decimal("50.00")
    assert importe_flujo("COBRO", Decimal("-50.00")) == Decimal("-50.00")


def test_f037_r4_none_es_cero_como_el_coalesce() -> None:
    assert importe_flujo("PAGO", None) == Decimal("0")
    assert importe_flujo("COBRO", None) == Decimal("0")


@pytest.mark.parametrize("sentido", ["pago", "cobro", "", "CLIENTE", "PROVEEDOR"])
def test_f037_r4_sentido_desconocido_es_error(sentido: str) -> None:
    with pytest.raises(ValueError, match="sentido"):
        importe_flujo(sentido, Decimal("1"))


# ===========================================================================
# R25 bis (D11-A) · el previsto antiguo: PREVISTO vencido hace más de 2 años
# ===========================================================================

BUILD = date(2026, 10, 13)


def test_f037_r25bis_fecha_limite_son_dos_anios() -> None:
    assert fecha_limite_previsto_antiguo(BUILD) == date(2024, 10, 13)


def test_f037_r25bis_29_de_febrero_como_postgresql() -> None:
    """`DATE '2028-02-29' - INTERVAL '2 years'` = 2026-02-28 en PostgreSQL."""
    assert fecha_limite_previsto_antiguo(date(2028, 2, 29)) == date(2026, 2, 28)


def test_f037_r25bis_frontera_exacta() -> None:
    """Vencido JUSTO hace 2 años no es antiguo; un día antes, sí."""
    assert es_previsto_antiguo("PREVISTO", date(2024, 10, 13), BUILD) is False
    assert es_previsto_antiguo("PREVISTO", date(2024, 10, 12), BUILD) is True
    assert es_previsto_antiguo("PREVISTO", date(2024, 10, 14), BUILD) is False


def test_f037_r25bis_muy_antiguo_y_futuro() -> None:
    assert es_previsto_antiguo("PREVISTO", date(2010, 1, 1), BUILD) is True
    assert es_previsto_antiguo("PREVISTO", date(2027, 1, 1), BUILD) is False


@pytest.mark.parametrize("estado", ["REALIZADO", "BAJA"])
def test_f037_r25bis_solo_previsto(estado: str) -> None:
    assert es_previsto_antiguo(estado, date(2010, 1, 1), BUILD) is False


def test_f037_r25bis_sin_vencimiento_no_es_antiguo() -> None:
    assert es_previsto_antiguo("PREVISTO", None, BUILD) is False
