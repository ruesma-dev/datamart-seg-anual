# etl_sigrid/domain/tesoreria.py
"""
Qué efecto de cobro o de pago es de PERSONAL, y en qué estado está (F-037, fase 1).

Un EFECTO es una fila de `raw.pag` (sentido `PAGO`, `con.tip = 25`) o de
`raw.cob` (sentido `COBRO`, `con.tip = 24`), y es un documento: su código, su
estado y su baja se leen de su propia fila en `raw.con`. Este módulo es el
ORÁCULO de `tesoreria_restringida.efectos`: el SQL de `01_efectos_completo.sql`
no lo llama, pero lleva los mismos literales (`REGEX_CUENTA_RESTRINGIDA`, 43,
306, 10, 14, 15 y los dos años), y `tests/test_f037_sql.py` los compara.

**Efecto de personal** (decisión del humano del 2026-10-13: «los pagos de
nominas deben quedar restringidos»). Es la UNIÓN de cuatro criterios más el
fallo cerrado, y el motivo es el primero que casa, en este orden:

1. `NATURALEZA`: `natide <> 0` (`raw.auxnap`: NOMINAS, EMBARGO, CUOTAS).
2. `CUENTA`: la cuenta del efecto empieza por un prefijo de F-135
   (`REGEX_CUENTA_RESTRINGIDA`, importada: no se copia).
3. `CUENTA_SIN_RESOLVER`: el efecto trae cuenta pero su código no resuelve:
   no se sabe si es de personal, así que se restringe (falla cerrado; hoy 0).
4. `TERCERO_EMPLEADO`: el tercero es un empleado (`con.tip = 43`).
5. `DOCUMENTO_NOMINA`: el documento origen es una nómina (`con.tip = 306`).

Medido el 2026-10-13: los cuatro criterios dan EXACTAMENTE los 37.053 pagos de
`natide <> 0`, y 0 cobros. La unión no restringe más hoy: es la red para el
día en que alguien olvide la naturaleza (D7).

**Estado** (`estado_tesoreria`, precedencia de F-094, igual en los dos
sentidos): `BAJA` si el efecto tiene fecha de baja o `est` 14/15
(sustituido: dividido o agrupado); si no, `REALIZADO` si tiene fecha real o
`est = 10` (desde 2020 el pago por remesa marca el estado y no puntea la
fecha); si no, `PREVISTO`.

**Previsto antiguo** (D11-A): `PREVISTO` con vencimiento anterior a la fecha
del build menos dos años. Es deuda sin puntear que la contabilidad ya no
sostiene, no caja.

Dominio puro: sin dependencias de infraestructura.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# R2: el criterio de cuenta es el de F-135, importado y no copiado. La regex se
# reexporta para que el test del SQL la compare con el literal de `01`.
from etl_sigrid.domain.restriccion_personal import (  # noqa: F401
    REGEX_CUENTA_RESTRINGIDA,
    es_cuenta_restringida,
)

#: Los dos sentidos del efecto (`tesoreria.efectos.sentido`).
SENTIDO_PAGO = "PAGO"
SENTIDO_COBRO = "COBRO"

#: `con.tip` del propio efecto: 25 en los 256.952 de `raw.pag`, 24 en los
#: 21.914 de `raw.cob` (2026-10-13). Es el `tip` con el que se traduce su
#: estado en `raw.conest`.
TIP_EFECTO_PAGO = 25
TIP_EFECTO_COBRO = 24

#: `con.tip` de un empleado (tercero) y de una nómina (documento origen).
TIP_TERCERO_EMPLEADO = 43
TIP_DOCUMENTO_NOMINA = 306

#: `con.est` = Pagado / Cobrado, y los dos estados de un efecto sustituido.
EST_PAGADO = 10
EST_SUSTITUIDO: tuple[int, ...] = (14, 15)

#: Valores de `estado_tesoreria`.
ESTADO_PREVISTO = "PREVISTO"
ESTADO_REALIZADO = "REALIZADO"
ESTADO_BAJA = "BAJA"

#: Valores de `motivo_restriccion`, en su orden de precedencia (R1).
MOTIVO_NATURALEZA = "NATURALEZA"
MOTIVO_CUENTA = "CUENTA"
MOTIVO_CUENTA_SIN_RESOLVER = "CUENTA_SIN_RESOLVER"
MOTIVO_TERCERO_EMPLEADO = "TERCERO_EMPLEADO"
MOTIVO_DOCUMENTO_NOMINA = "DOCUMENTO_NOMINA"
MOTIVOS_EN_ORDEN: tuple[str, ...] = (
    MOTIVO_NATURALEZA,
    MOTIVO_CUENTA,
    MOTIVO_CUENTA_SIN_RESOLVER,
    MOTIVO_TERCERO_EMPLEADO,
    MOTIVO_DOCUMENTO_NOMINA,
)

#: Un PREVISTO vencido hace más de estos años es `previsto_antiguo` (D11-A):
#: el umbral con el que cuadran al céntimo 223 cuentas de proveedor.
ANIOS_PREVISTO_ANTIGUO = 2


@dataclass(frozen=True, slots=True)
class EfectoTesoreria:
    """Lo que el criterio de personal mira de un efecto.

    `None` (y `0` en los identificadores, como el `NULLIF(x, 0)` del SQL) es
    «no informado». `codigo_cuenta` es el código de la cuenta en `raw.con`
    (`None` si no resuelve); `tip_tercero` y `tip_documento`, el `con.tip` del
    tercero y del documento origen.
    """

    natide: int | None
    cuenta_id: int | None
    codigo_cuenta: str | None
    tip_tercero: int | None
    tip_documento: int | None


def _informado(valor: int | None) -> bool:
    """`None` y `0` son «sin valor», como el `NULLIF(x, 0)` del SQL."""
    return valor is not None and valor != 0


def motivo_restriccion_efecto(efecto: EfectoTesoreria) -> str | None:
    """El primer motivo de personal que casa, en el orden de R1, o `None`.

    Mismo orden que el `CASE` de `01_efectos_completo.sql`. `CUENTA` y
    `CUENTA_SIN_RESOLVER` no pueden darse a la vez: una cuenta que no resuelve
    no tiene código.
    """
    if _informado(efecto.natide):
        return MOTIVO_NATURALEZA
    if es_cuenta_restringida(efecto.codigo_cuenta):
        return MOTIVO_CUENTA
    if _informado(efecto.cuenta_id) and efecto.codigo_cuenta is None:
        return MOTIVO_CUENTA_SIN_RESOLVER
    if efecto.tip_tercero == TIP_TERCERO_EMPLEADO:
        return MOTIVO_TERCERO_EMPLEADO
    if efecto.tip_documento == TIP_DOCUMENTO_NOMINA:
        return MOTIVO_DOCUMENTO_NOMINA
    return None


def es_efecto_restringido(efecto: EfectoTesoreria) -> bool:
    """True si el efecto es de personal (no lo lee el rol estándar)."""
    return motivo_restriccion_efecto(efecto) is not None


def estado_tesoreria(est: int | None, fecrea: int | None, fecbaj: int | None) -> str:
    """`BAJA`, `REALIZADO` o `PREVISTO` (R3). `None` y `0` son «sin valor».

    La BAJA gana: un efecto dividido o agrupado puede tener fecha real y no es
    caja (F-094). `est = 10` sin fecha real es REALIZADO: desde 2020 el pago
    por remesa marca el estado y no puntea la fecha.
    """
    if _informado(fecbaj) or est in EST_SUSTITUIDO:
        return ESTADO_BAJA
    if _informado(fecrea) or est == EST_PAGADO:
        return ESTADO_REALIZADO
    return ESTADO_PREVISTO


def importe_flujo(sentido: str, importe: Decimal | None) -> Decimal:
    """`+importe` en COBRO y `-importe` en PAGO, con el signo de origen (R4).

    `None` es 0, como el `COALESCE(tot, 0)` del SQL. Un sentido que no es
    ninguno de los dos es un error: no hay signo que adivinar.
    """
    valor = Decimal(0) if importe is None else importe
    if sentido == SENTIDO_COBRO:
        return valor
    if sentido == SENTIDO_PAGO:
        return -valor
    raise ValueError(f"sentido de efecto desconocido: {sentido!r}")


def fecha_limite_previsto_antiguo(fecha_build: date) -> date:
    """La fecha del build menos dos años, como `CURRENT_DATE - INTERVAL '2 years'`.

    PostgreSQL lleva el 29 de febrero al 28 cuando el año destino no es
    bisiesto; aquí, igual.
    """
    anio = fecha_build.year - ANIOS_PREVISTO_ANTIGUO
    try:
        return fecha_build.replace(year=anio)
    except ValueError:  # 29 de febrero hacia un año no bisiesto
        return fecha_build.replace(year=anio, day=28)


def es_previsto_antiguo(estado: str, vencimiento: date | None, fecha_build: date) -> bool:
    """True si es PREVISTO y venció ANTES de la fecha límite (R25 bis).

    Vencido justo en la fecha límite no es antiguo (`<`, no `<=`). Sin
    vencimiento no se puede decir que sea antiguo.
    """
    return (
        estado == ESTADO_PREVISTO
        and vencimiento is not None
        and vencimiento < fecha_limite_previsto_antiguo(fecha_build)
    )
