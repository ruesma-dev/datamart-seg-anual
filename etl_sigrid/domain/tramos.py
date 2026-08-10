# etl_sigrid/domain/tramos.py
"""
Planificador de tramos del build de `stg.plan_mensual` (F-019).

Por qué existe: el build de `stg.plan_mensual` explota `raw.obrparpre` con
`CROSS JOIN LATERAL unnest(...)` y encadena cinco ventanas. En el
`Standard_B1ms` de Azure (2 GB de RAM) esos sorts derraman a ficheros
temporales sobre un disco de 32 GB **compartido con `albaranes` y `partes` en
producción**: el 2026-08-09 llegaron a llenarlo al 93,4 % y el servidor quedó
en solo-lectura diez minutos.

La observación que hace posible el troceo es estructural, no casual: **ninguna
ventana del SQL cruza obras** (todas particionan por `presupuesto_id` o por
`(obra_id, partida_id, ambito_id)`). Ejecutar el mismo statement N veces con
un filtro por obra disjunto y completo da exactamente las mismas filas que una
pasada única, y el pico de temporales de cada pasada es proporcional al peso
del tramo, no al total.

Capa **domain**: función pura, cero imports de infraestructura, cero logging.
El WARNING de la obra sobredimensionada lo emite quien llama (el step).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tramo:
    """Un lote de obras que se construye en una sola transacción.

    `indice` empieza en 1 y es correlativo: se usa tal cual en los logs
    (`3/14`) y en el nombre del registro de `_meta.etl_runs`
    (`build_stg.build_plan_mensual.tramo_03`).
    """

    indice: int
    obras: tuple[int, ...]
    peso: int


def _clave_de_empaquetado(par: tuple[int, int]) -> tuple[int, int]:
    """Orden estable del empaquetado: peso descendente y, a igual peso, obra.

    El desempate por `obra_id` es lo que hace el plan **determinista** (R5):
    sin él, dos obras del mismo peso podrían salir en cualquier orden según el
    orden de iteración del diccionario de entrada.
    """
    obra_id, peso = par
    return (-peso, obra_id)


def planificar_tramos(
    pesos_por_obra: Mapping[int, int], max_filas: int
) -> list[Tramo]:
    """Reparte las obras en tramos de peso acotado.

    `pesos_por_obra` es {obra_id: filas estimadas} y `max_filas` el tope de
    peso por tramo (`PG_TRAMO_MAX_FILAS`).

    Garantías (R3, R4, R5):

    - **Partición**: cada obra en exactamente un tramo, ningún tramo vacío y
      la unión de los tramos es el conjunto entero de obras.
    - **Acotado**: ningún tramo supera `max_filas`, salvo el caso en que una
      obra sola ya lo supere; entonces va en un **tramo unitario**, que es el
      mínimo físico posible (no se aborta: se avisa, ver
      `tramos_sobredimensionados`).
    - **Determinista**: mismos pesos y mismo máximo producen exactamente el
      mismo plan, sea cual sea el orden del diccionario de entrada.

    El empaquetado es voraz sobre la lista ordenada de mayor a menor peso: se
    van acumulando obras mientras quepan y se cierra el tramo en cuanto la
    siguiente no cabe.
    """
    if max_filas <= 0:
        raise ValueError(
            f"PG_TRAMO_MAX_FILAS debe ser un entero positivo, y vale {max_filas}. "
            f"Sin tope no hay troceo: el build volvería a ser el de una sola "
            f"pasada, que es el que llenó el disco del servidor compartido."
        )

    tramos: list[Tramo] = []
    obras_del_tramo: list[int] = []
    peso_del_tramo = 0

    for obra_id, peso in sorted(pesos_por_obra.items(), key=_clave_de_empaquetado):
        # La obra sola por encima del máximo queda aislada por construcción:
        # entra en un tramo recién abierto y la siguiente obra ya no cabe.
        if obras_del_tramo and peso_del_tramo + peso > max_filas:
            tramos.append(_cerrar_tramo(tramos, obras_del_tramo, peso_del_tramo))
            obras_del_tramo = []
            peso_del_tramo = 0

        obras_del_tramo.append(obra_id)
        peso_del_tramo += peso

    if obras_del_tramo:
        tramos.append(_cerrar_tramo(tramos, obras_del_tramo, peso_del_tramo))

    return tramos


def _cerrar_tramo(
    tramos_previos: Sequence[Tramo], obras: Sequence[int], peso: int
) -> Tramo:
    """Construye el tramo que sigue a `tramos_previos` (índices desde 1)."""
    return Tramo(
        indice=len(tramos_previos) + 1,
        obras=tuple(obras),
        peso=peso,
    )


def tramos_sobredimensionados(
    tramos: Sequence[Tramo], max_filas: int
) -> list[Tramo]:
    """Tramos cuyo peso supera el máximo: obras que no caben ni solas (R4).

    Solo puede ocurrir con tramos unitarios, por construcción de
    `planificar_tramos`. Quien llama emite el WARNING con el peso: el dominio
    no loguea.
    """
    return [tramo for tramo in tramos if tramo.peso > max_filas]
