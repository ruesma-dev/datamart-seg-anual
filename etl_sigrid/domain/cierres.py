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
`importe_origen - LAG(importe_origen)`, y **solo** si la fase anterior es la
inmediatamente consecutiva; si no lo es, se queda con el acumulado entero
(`sql/stg/08_plan_mensual.sql`). Descartar la fase 20 de la 0499 sin más dejaría
a la 21 sin `LAG` consecutivo —19 no es 21-1— y el movimiento de febrero de 2018
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


# ---------------------------------------------------------------------------
# El contraste de R17: lo que hay contra lo que debería haber
# ---------------------------------------------------------------------------

#: Una fila de cierre tal y como sale de la base:
#: `(obra_id, ambito_id, anio_mes, numero_fase, acumulado)`.
FilaDeCierre = tuple[int, int, date, int, Decimal | None]


@dataclass(frozen=True, slots=True)
class Discrepancia:
    """Un mes en el que `stg.plan_mensual` no dice lo que la regla exige.

    Lleva **obra, ámbito, mes y las dos listas de fases** porque un mensaje de
    «hay discrepancias» que no se puede investigar sin volver a la base no sirve
    de nada: quien lo lea tiene que poder ir a Sigrid con esos números.
    """

    obra_id: int
    ambito_id: int
    anio_mes: date
    #: Las fases que `stg.plan_mensual` publica en ese mes, ordenadas.
    publicado: tuple[int, ...]
    #: Las que debería publicar según el oráculo. Siempre cero o una.
    esperado: tuple[int, ...]
    motivo: str


def agrupar(filas: Sequence[FilaDeCierre]) -> dict[tuple[int, int], list[Cierre]]:
    """Reparte las filas por (obra, ámbito), que es el alcance de la regla.

    La regla decide por mes pero **renumera por (obra, ámbito)**: un descarte de
    enero desplaza a todas las fases posteriores de esa obra y ámbito. Agrupar
    por menos que eso daría un orden falso.
    """
    grupos: dict[tuple[int, int], list[Cierre]] = {}
    for obra_id, ambito_id, anio_mes, numero_fase, acumulado in filas:
        grupos.setdefault((obra_id, ambito_id), []).append(
            Cierre(numero_fase=numero_fase, anio_mes=anio_mes, acumulado=acumulado)
        )
    return grupos


def contrastar(
    candidatos: Mapping[tuple[int, int], Sequence[Cierre]],
    publicados: Mapping[tuple[int, int], Sequence[Cierre]],
) -> tuple[Discrepancia, ...]:
    """Qué debería haber (`candidatos`) contra qué hay (`publicados`).

    `candidatos` son **todas** las fases que `reales_base` vería, recompuestas
    desde `stg.presupuesto` ⨝ `stg.fases`; `publicados`, lo que `stg.plan_mensual`
    tiene de verdad. El contraste solo vale porque los dos caminos son
    independientes: si los candidatos salieran de `plan_mensual`, la
    comprobación se estaría preguntando a sí misma.

    Se reportan cuatro cosas, y las cuatro importan: un mes con **más de un**
    cierre (el defecto de hoy), un mes con **el cierre equivocado** —que un
    recuento de duplicados no vería—, un mes **que desaparece entero**
    (descartar de más es tan grave como descartar de menos) y un mes publicado
    **sin candidato** que lo sostenga.
    """
    discrepancias: list[Discrepancia] = []

    for clave in sorted(set(candidatos) | set(publicados)):
        obra_id, ambito_id = clave
        del_mes_publicado: dict[date, list[int]] = {}
        for cierre in publicados.get(clave, ()):
            del_mes_publicado.setdefault(cierre.anio_mes, []).append(cierre.numero_fase)

        plan = plan_de_cierres(list(candidatos.get(clave, ())))

        for mes in sorted(set(plan.vigente_por_mes) | set(del_mes_publicado)):
            publicado = tuple(sorted(del_mes_publicado.get(mes, ())))
            esperado = (
                (plan.vigente_por_mes[mes],) if mes in plan.vigente_por_mes else ()
            )
            if publicado == esperado:
                continue
            discrepancias.append(
                Discrepancia(
                    obra_id=obra_id,
                    ambito_id=ambito_id,
                    anio_mes=mes,
                    publicado=publicado,
                    esperado=esperado,
                    motivo=_motivo(publicado, esperado),
                )
            )

    return tuple(discrepancias)


def _motivo(publicado: tuple[int, ...], esperado: tuple[int, ...]) -> str:
    if len(publicado) > 1:
        return (
            f"mas de un cierre publicado en el mes ({', '.join(map(str, publicado))}): "
            f"la clave de mart.fact_seguimiento_mensual no identifica una fila y "
            f"todo SUM del acumulado a origen cuenta dos veces"
        )
    if not publicado:
        return (
            "el mes no tiene ningun cierre publicado y deberia tener el "
            f"{esperado[0]}: descartar de mas hace desaparecer un mes entero"
        )
    if not esperado:
        return (
            f"el mes publica el cierre {publicado[0]} y stg.presupuesto no "
            f"sostiene ninguno: plan_mensual va por delante de su origen"
        )
    return (
        f"manda el cierre {publicado[0]} y deberia mandar el {esperado[0]}: "
        f"un solo cierre por mes, si, pero el que no era"
    )
