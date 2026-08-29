# etl_sigrid/domain/cierres.py
"""
F-042 · «Un solo cierre por mes» en los ámbitos reales (3 Coste, 7 Venta).

Veintidós obras tienen dos fases que Sigrid guarda con el mismo año y el mismo
mes. Al proyectarlas al mismo `anio_mes` salen dos filas indistinguibles, la
clave de `mart.fact_seguimiento_mensual` deja de identificar una fila y todo
`SUM` sobre el acumulado a origen **cuenta dos veces**: 8.778 claves duplicadas
y 30.425.881,56 € publicados de más (medido, `progress/explore_F-042.md`).

La decisión de Negocio del 2026-08-28 fue: **el mes no se parte en dos, manda el
cierre más moderno**, con el matiz confirmado el 2026-08-29 de que un cierre con
el acumulado a **cero** no puede desbancar a otro que sí tiene dato (si no,
0606 · PUY DU FOU pasaría a publicar cero en febrero de 2021).

## Por qué no basta con descartar la fila

`importe_mes` de los reales **no viene de Sigrid**: lo calcula el ETL como
`importe_origen − LAG(importe_origen)`, y **solo** si la fase anterior es la
inmediatamente consecutiva; si no lo es, se queda con el acumulado entero
(`sql/stg/08_plan_mensual.sql`). Descartar la fase 20 de la 0499 sin más dejaría
a la 21 sin `LAG` consecutivo —19 no es 21−1— y el movimiento de febrero de 2018
pasaría de 975.249,98 € a 5.688.073,92 €: se arreglaría el acumulado y se
rompería el movimiento. Por eso hay que **renumerar el orden interno**.

## Por qué se desplaza y no se hace `dense_rank()`

`dense_rank()` cerraría *todos* los huecos, incluidos los que Sigrid ya trae. Una
obra con fases 1, 2 y 4 pasaría a 1, 2, 3 y el `importe_mes` de la 4 cambiaría de
«acumulado entero» a «diferencia», **en una obra que hoy está bien**. El
desplazamiento cuenta **solo descartes**, así que un hueco de origen sigue siendo
un hueco.

## Qué es este módulo y qué no

Es un **oráculo independiente**, no una copia del SQL: recibe los acumulados
leídos de la base y dice qué debería haber quedado. Si el SQL y el oráculo
discrepan, `python main.py check-cierres` falla, y ese es su valor. Capa
**domain**: funciones puras, cero imports de infraestructura, cero logging.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType

#: Lo que devuelve `SUM(importe_origen_round)` cuando el grupo no tiene ni un
#: importe: `NULL`. En Postgres `NULL <> 0` no es cierto **ni falso**, y en un
#: `ORDER BY ... DESC` los nulos van PRIMERO, así que una fase sin dato ganaría
#: el mes. El SQL lo tapa con `COALESCE(..., 0)` y aquí se hace lo mismo.
_SIN_DATO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Cierre:
    """Una fase de una (obra, ámbito) real, con su acumulado a origen.

    `acumulado` es la suma de `importe_origen` de **todas las partidas** de esa
    fase: la regla decide por fase entera, no partida a partida, porque lo que
    sobra o falta es el cierre completo.
    """

    numero_fase: int
    anio_mes: date
    acumulado: Decimal | None


@dataclass(frozen=True, slots=True)
class PlanCierres:
    """El veredicto para UNA (obra, ámbito): qué se queda, qué se va y en qué orden.

    * `vigente_por_mes` — qué fase manda en cada mes. Es lo que contrasta R17.
    * `descartadas` — las fases que no llegan a `stg.plan_mensual`, ordenadas.
      Siguen existiendo en `raw` y en `stg.fases`: ahí está el rastro.
    * `orden` — `numero_fase → orden_fase` de los **supervivientes**. Es el
      número que usa el `LAG` para decidir si el mes anterior es consecutivo.
      **No es lo que se publica**: `version` conserva el número original de
      Sigrid (R7), porque seis `JOIN` de `cierre/` lo cruzan contra
      `stg.fases.numero_fase`.
    """

    vigente_por_mes: Mapping[date, int]
    descartadas: tuple[int, ...]
    orden: Mapping[int, int]


def plan_de_cierres(cierres: Sequence[Cierre]) -> PlanCierres:
    """Aplica la regla a los cierres de UNA (obra, ámbito).

    Reglas, en el orden en que se aplican:

    1. Se agrupan los cierres por mes (R1).
    2. En cada mes gana el de **mayor `numero_fase` entre los que tienen el
       acumulado distinto de cero** (R1, R11). Vale para N cierres, no solo para
       dos (R4).
    3. Si **todos** los del mes están a cero, gana el de mayor `numero_fase`
       (R2). Un mes con un solo cierre se queda con él, valga cero o no (R3).
    4. El orden de cada superviviente es su `numero_fase` **menos cuántos
       descartes hay por debajo** (R5). Los huecos que ya traía Sigrid no se
       tocan (R6).

    Recibir dos veces la misma fase es un error de quien llama —una fase
    pertenece a un único mes en `stg.fases`—, y se levanta `ValueError` en vez de
    producir un orden silenciosamente falso.
    """
    numeros = [c.numero_fase for c in cierres]
    repetidas = sorted({n for n in numeros if numeros.count(n) > 1})
    if repetidas:
        raise ValueError(
            f"fase(s) repetida(s) en la misma (obra, ambito): {repetidas}. Una "
            f"fase pertenece a un solo mes en stg.fases; si llegan dos, quien "
            f"llama ha mezclado obras o ambitos y el orden saldria falso"
        )

    por_mes: dict[date, list[Cierre]] = {}
    for cierre in cierres:
        por_mes.setdefault(cierre.anio_mes, []).append(cierre)

    vigente_por_mes = {
        mes: _vigente_del_mes(delmes) for mes, delmes in sorted(por_mes.items())
    }
    vigentes = set(vigente_por_mes.values())
    descartadas = tuple(sorted(n for n in numeros if n not in vigentes))

    orden = {
        numero: numero - sum(1 for d in descartadas if d < numero)
        for numero in sorted(vigentes)
    }

    return PlanCierres(
        vigente_por_mes=MappingProxyType(vigente_por_mes),
        descartadas=descartadas,
        orden=MappingProxyType(orden),
    )


def _vigente_del_mes(cierres_del_mes: Sequence[Cierre]) -> int:
    """El cierre que manda en un mes.

    El criterio es el mismo `ORDER BY (acumulado <> 0) DESC, mes_fase_num DESC`
    del SQL, escrito como clave de ordenación: primero los que tienen dato y,
    dentro de cada grupo, el número de fase más alto.
    """
    return max(
        cierres_del_mes,
        key=lambda c: ((c.acumulado or _SIN_DATO) != 0, c.numero_fase),
    ).numero_fase
