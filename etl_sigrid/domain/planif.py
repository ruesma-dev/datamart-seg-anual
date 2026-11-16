# etl_sigrid/domain/planif.py
"""
La explosión del `planif` de una partida en meses: el oráculo puro (F-157).

`raw.obrparpre.planif` es un texto con el % ACUMULADO de cada mes separado por
`|` (`0|0|0.15|0.85|1`). La regla para leerlo es la del master de
`sql/stg/08_plan_mensual.sql`, validada al céntimo contra Sigrid, y la aplica
también `stg.fn_explotar_planif` (`sql/stg/00_functions.sql`) a la fase 0. Este
módulo la repite posición a posición para que los tests y la sandbox puedan
comparar las dos sin base de datos:

- Se parte por `|` numerando desde 1; las posiciones vacías se quitan pero NO
  renumeran (como `WITH ORDINALITY` + `length(trim(v)) > 0`).
- Valor numérico si casa `^-?\\d+([.,]\\d+)?$` (coma decimal admitida) y
  redondeado a 6 decimales como `NUMERIC(18,6)`; si no, cuenta como no positivo.
- Positivo: literal. No positivo con un positivo DESPUÉS: 0 (estorno). No
  positivo final tras un positivo: el ÚLTIMO positivo (no el máximo). Sin
  positivo antes: 0.
- `pct_mes` = acumulado − el de la posición conservada anterior (0 la primera).

`conservar` es el descarte del master (R6): fuera las posiciones a 0 sin
movimiento y las de acumulado > 2,5.

Sin dependencias: dominio puro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_NUMERO = re.compile(r"-?[0-9]+([.,][0-9]+)?")
_SEIS_DECIMALES = Decimal("0.000001")
_CERO = Decimal("0")
_TOPE_CORDURA = Decimal("2.5")


@dataclass(frozen=True, slots=True)
class PosicionPlanif:
    """Un mes del reparto: su posición (1 = el mes de `plafec`) y sus %."""

    posicion_mes: int
    pct_acumulado: Decimal
    pct_mes: Decimal


def _valor(texto: str) -> Decimal | None:
    if not _NUMERO.fullmatch(texto):
        return None
    return Decimal(texto.replace(",", ".")).quantize(_SEIS_DECIMALES, ROUND_HALF_UP)


def explotar_planif(texto: str | None) -> list[PosicionPlanif]:
    """Las posiciones con valor de un `planif`, con su % acumulado y del mes."""
    if texto is None:
        return []

    posiciones = [
        (numero, _valor(valor))
        for numero, valor in enumerate(texto.split("|"), start=1)
        if valor.strip()
    ]

    resultado: list[PosicionPlanif] = []
    ultimo_positivo: Decimal | None = None
    anterior = _CERO
    for indice, (numero, bruto) in enumerate(posiciones):
        if bruto is not None and bruto > 0:
            ultimo_positivo = bruto
            efectivo = bruto
        elif any(v is not None and v > 0 for _, v in posiciones[indice + 1 :]):
            efectivo = _CERO
        elif ultimo_positivo is not None:
            efectivo = ultimo_positivo
        else:
            efectivo = _CERO
        resultado.append(PosicionPlanif(numero, efectivo, efectivo - anterior))
        anterior = efectivo
    return resultado


def conservar(posicion: PosicionPlanif) -> bool:
    """El descarte del master: ni pre-arranque sin movimiento ni más de 250 %."""
    sin_nada = posicion.pct_acumulado == 0 and posicion.pct_mes == 0
    return not sin_nada and posicion.pct_acumulado <= _TOPE_CORDURA
