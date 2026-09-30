# etl_sigrid/domain/serie_real.py
"""
F-118 · La serie real densa de una partida (R9, R29-R34; F-103 absorbida).

## El defecto

El `importe_mes` de los ámbitos reales (3 coste, 7 venta) no viene de Sigrid: lo
calcula el ETL como acumulado del mes menos acumulado anterior. Hasta F-118 lo
hacía fila a fila sobre lo que Sigrid guarda, y **solo** si la fila anterior de
la partida era de la fase inmediatamente anterior; si no, publicaba el
acumulado entero. Dos huecos rompían así la suma:

- **la partida que desaparece de un cierre** (fallo 1 del correo de Juan Romero
  del 2026-09-29): la 0709, partida 417031, tiene -58.000 en julio, ninguna
  fila en agosto y 0 en septiembre. En agosto nadie deshacía los -58.000 y en
  septiembre se publicaba el acumulado (0) en vez de +58.000;
- **el número de fase que Sigrid se salta** (F-103): la 0371 pasa de la f27 a
  la f29 y la f29 publicaba el acumulado entero (+4,29 M€) en vez de la
  diferencia (-441.229,31).

`cierre` acertaba porque suma acumulados por (obra, mes, concepto) y resta
meses: la partida ausente no suma. La serie densa hace lo mismo a grano de
partida.

## La regla

La serie de una (obra, ámbito, partida) recorre, desde su alta, **todos** los
meses del ámbito sin huecos:

- en un **cierre** del ámbito (mes con fase vigente del ámbito): la fila de
  Sigrid si la hay; si no, acumulado **0** — la partida se **deshace** (R29) y,
  si vuelve, se calcula contra ese 0 (R30);
- en un mes de **relleno** (F-051, R10-R14): el acumulado del último cierre,
  ya deshecho si lo estaba (R33). La ausencia no deshace;
- una fase de la obra sin ninguna fila del ámbito **no es cierre de ese
  ámbito** (R34, D3): no está en la lista de cierres y no deshace nada.

El movimiento es la diferencia con el mes anterior de la serie; el primero, el
acumulado entero (R9). Se publican las filas de Sigrid, las de relleno con
acumulado distinto de 0 o con fila de Sigrid que se mueve en su fase generadora
(D3 de F-051) y
las de deshacer que mueven algo (R32: una sola, la que lleva el acumulado a 0).

Invariante por construcción (R21): la suma de los movimientos publicados es el
acumulado del último cierre del ámbito (0 si la partida ya no está), porque la
serie telescopea y lo que no se publica tiene movimiento 0.

Es el **oráculo** contra el que se contrasta la rama de reales de
`sql/stg/08_plan_mensual.sql`. Capa domain: funciones puras.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_CERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class FilaSerie:
    """Una fila publicada de la serie de una partida."""

    mes: date
    acumulado: Decimal
    movimiento: Decimal
    es_relleno: bool
    es_deshacer: bool


def relleno_por_mes(
    relleno_por_fase: Mapping[int, Sequence[date]], mes_de_la_fase: Mapping[int, date]
) -> dict[date, date]:
    """`mes de relleno → mes del cierre que lo genera`, desde `meses_relleno`."""
    return {
        mes: mes_de_la_fase[fase]
        for fase, meses in relleno_por_fase.items()
        for mes in meses
    }


def serie_densa(
    filas: Mapping[date, Decimal],
    cierres_del_ambito: Sequence[date],
    meses_relleno: Mapping[date, date] | None = None,
) -> list[FilaSerie]:
    """Las filas que publica una (obra, ámbito, partida).

    - `filas`: el acumulado de Sigrid de la partida en cada cierre donde tiene
      fila (`mes → acumulado`).
    - `cierres_del_ambito`: los meses de los cierres VIGENTES de la (obra,
      ámbito), tras F-042 y sobre el mes del texto (R8).
    - `meses_relleno`: `mes de relleno → mes de su cierre generador`, de
      `mes_fase.meses_relleno` (ver `relleno_por_mes`).
    """
    relleno = dict(meses_relleno or {})
    cierres = set(cierres_del_ambito)
    _validar(filas, cierres, relleno)

    # Alta: el primer mes con fila de Sigrid, o el primer relleno de un cierre
    # donde la partida tiene fila (D3 de F-051: nace con su relleno).
    candidatos_alta = set(filas) | {
        mes for mes, generador in relleno.items() if generador in filas
    }
    if not candidatos_alta:
        return []
    alta = min(candidatos_alta)
    meses = sorted(m for m in cierres | set(relleno) if m >= alta)

    # 1) Acumulado por hueco: fila propia, 0 en un cierre sin fila, arrastre en
    #    un relleno (0 si no hay cierre anterior).
    acumulados: dict[date, Decimal] = {}
    ultimo_cierre = _CERO
    for mes in meses:
        if mes in relleno:
            acumulados[mes] = ultimo_cierre
        else:
            ultimo_cierre = filas.get(mes, _CERO)
            acumulados[mes] = ultimo_cierre

    # 2) Movimiento: diferencia con el mes anterior de la serie (R9).
    movimientos: dict[date, Decimal] = {}
    anterior = _CERO
    for mes in meses:
        movimientos[mes] = acumulados[mes] - anterior
        anterior = acumulados[mes]

    # 3) Qué se publica.
    publicadas: list[FilaSerie] = []
    for mes in meses:
        acumulado, movimiento = acumulados[mes], movimientos[mes]
        if mes in relleno:
            generador = relleno[mes]
            # D3 de F-051: acumulado arrastrado distinto de 0, o la partida
            # tiene fila de Sigrid con movimiento en el cierre que lo genera.
            # Un deshacer en ese cierre no cuenta: la partida no está en él.
            mueve_en_su_fase = generador in filas and movimientos[generador] != 0
            if acumulado != 0 or mueve_en_su_fase:
                publicadas.append(FilaSerie(mes, acumulado, movimiento, True, False))
        elif mes in filas:
            publicadas.append(FilaSerie(mes, acumulado, movimiento, False, False))
        elif movimiento != 0:
            publicadas.append(FilaSerie(mes, acumulado, movimiento, False, True))
    return publicadas


def _validar(
    filas: Mapping[date, Decimal], cierres: set[date], relleno: Mapping[date, date]
) -> None:
    fuera = sorted(m for m in filas if m not in cierres)
    if fuera:
        raise ValueError(
            f"fila de Sigrid en {fuera[0]:%Y-%m}, que no es un cierre vigente del "
            f"ambito: una fila solo puede vivir en el mes de su fase"
        )
    for mes, generador in relleno.items():
        if mes in cierres:
            raise ValueError(
                f"{mes:%Y-%m} es un mes de relleno y a la vez un cierre: el "
                f"relleno nunca pisa un mes con cierre propio (R11)"
            )
        if generador not in cierres or generador <= mes:
            raise ValueError(
                f"el relleno de {mes:%Y-%m} apunta al generador {generador:%Y-%m}, "
                f"que no es un cierre posterior del ambito (R14)"
            )
