# etl_sigrid/domain/master_versiones.py
"""
El catálogo de versiones master: el oráculo puro (F-161).

Repite en Python tres reglas que el SQL aplica en
`sql/stg/10_master_versiones.sql` y `sql/mart/01b_master_versiones.sql`, para
que los tests y la sandbox puedan compararlas sin base de datos:

- `tipo_master`: el tipo de una versión por el texto libre del jefe de obra,
  con prioridad estricta (ABC > Planif Inicial > Cuatrimestral > Cierre mensual
  > Sin clasificar). Es la cascada de `mart/02_build_fact.sql` hasta F-161.
- `clasificar_reparto`: NINGUNO si la versión no tiene filas en
  `stg.plan_mensual`; COMPLETO si las tiene y ninguna línea con importe distinto
  de cero se queda sin ellas; PARCIAL en el resto (R3, D7).
- `version_vigente`: la versión que rige un mes.
  - `temporal=False` es el ÚLTIMO CIERRE (D8): la última de CUALQUIER tipo,
    versión >= 1, con líneas y con fecha efectiva.
  - `temporal=True` es la que elige `02_build_fact.sql` (R10, D4): con reparto,
    con las dos fechas y de tipo Planif Inicial, ABC o Cuatrimestral.
  En los dos modos rige si `fec_efectiva < primer día del mes siguiente`, y se
  elige por fecha efectiva y versión descendentes.

Sin dependencias: dominio puro.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

#: Los tres tipos que pueden regir el mensual (los «Cierre mensual» no).
TIPOS_TEMPORALES = ("Planif Inicial", "ABC", "Cuatrimestral")

NINGUNO = "NINGUNO"
COMPLETO = "COMPLETO"
PARCIAL = "PARCIAL"


@dataclass(frozen=True, slots=True)
class VersionMaster:
    """Una versión del catálogo, con lo que hace falta para elegirla."""

    version: int
    fec_efectiva: date | None
    tipo: str
    n_lineas: int
    tiene_reparto: bool
    importe_total: Decimal
    # El temporal exige también la fecha de creación (el filtro de `02`).
    fec_creacion: date | None


def tipo_master(tex: str | None) -> str:
    """La cascada del tipo. `trim` de PostgreSQL quita solo espacios."""
    if tex is None or len(tex.strip(" ")) == 0:
        return "Sin clasificar"
    texto = tex.upper()
    if "ABC" in texto:
        return "ABC"
    if "INICIAL" in texto and "VALORADA" in texto:
        return "Planif Inicial"
    if "CUATRIM" in texto or "VALORADA" in texto:
        return "Cuatrimestral"
    if "CIERRE" in texto:
        return "Cierre mensual"
    return "Sin clasificar"


def clasificar_reparto(
    lineas: Sequence[tuple[Decimal | None, bool]], tiene_reparto: bool
) -> str:
    """NINGUNO, COMPLETO o PARCIAL. Cada línea es (`importe`, `con_reparto`).

    Un importe nulo no cuenta como importe: en SQL `NULL <> 0` es NULL y
    `BOOL_OR` lo ignora.
    """
    if not tiene_reparto:
        return NINGUNO
    if any(not con and importe is not None and importe != 0 for importe, con in lineas):
        return PARCIAL
    return COMPLETO


def _mes_siguiente(mes: date) -> date:
    if mes.month == 12:
        return date(mes.year + 1, 1, 1)
    return date(mes.year, mes.month + 1, 1)


def _elegible(v: VersionMaster, temporal: bool) -> bool:
    if v.fec_efectiva is None:
        return False
    if temporal:
        return v.tiene_reparto and v.fec_creacion is not None and v.tipo in TIPOS_TEMPORALES
    return v.version >= 1 and v.n_lineas > 0


def version_vigente(
    versiones: Iterable[VersionMaster], mes: date, *, temporal: bool
) -> VersionMaster | None:
    """La versión que rige `mes` (cualquier día del mes vale), o None."""
    limite = _mes_siguiente(date(mes.year, mes.month, 1))
    candidatas = [
        v
        for v in versiones
        if _elegible(v, temporal) and v.fec_efectiva is not None and v.fec_efectiva < limite
    ]
    if not candidatas:
        return None
    return max(candidatas, key=lambda v: (v.fec_efectiva, v.version))
