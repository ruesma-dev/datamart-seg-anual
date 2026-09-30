# etl_sigrid/infrastructure/postgres/mes_fase_sql.py
"""
F-118 (F-051 absorbida) · Las consultas de `check-mes-fase`. **Solo construyen
texto**; las ejecuta el comando en una transacción `READ ONLY` con su
`statement_timeout`, porque corren contra el Postgres compartido en producción.

Tres preguntas:

1. **Las fases** — cada fase de `stg.fases` con el mes que le da
   `stg.fn_mes_de_fase` en la base. El comando lo compara con el oráculo
   `domain.mes_fase.mes_de_fase` (R25): dos implementaciones de la misma regla
   que tienen que coincidir en todas las fases.
2. **Las claves** — ninguna (obra, ámbito, partida, mes) repetida en las filas
   reales de `stg.plan_mensual`.
3. **Las marcas** — el relleno siempre con movimiento 0, el deshacer siempre
   con movimiento, y ningún mes que mezcle relleno con cierre (un relleno en un
   mes con cierre propio, o un deshacer en un mes de relleno).
"""

from __future__ import annotations

from collections.abc import Sequence

from etl_sigrid.infrastructure.postgres.cierres_sql import _filtro_de_obras

#: Las columnas que lee `FaseLeida`, en su orden.
COLUMNAS_FASES = (
    "obra_id",
    "codigo_obra",
    "numero_fase",
    "fecha_inicio",
    "nombre_mes",
    "fecha_fin",
    "mes_archivado",
    "mes_sql",
)


def sql_fases(obras: Sequence[int] | None = None) -> str:
    """Las fases reales (`numero_fase >= 1`, `anio`/`mes` no nulos, el universo
    de `reales_base`) con su mes según `stg.fn_mes_de_fase`."""
    return (
        "SELECT f.obra_id,\n"
        "       o.codigo_obra,\n"
        "       f.numero_fase,\n"
        "       f.fecha_inicio,\n"
        "       f.nombre_mes,\n"
        "       f.fecha_fin,\n"
        "       make_date(f.anio, f.mes, 1) AS mes_archivado,\n"
        "       stg.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes, f.fecha_fin,\n"
        "                          make_date(f.anio, f.mes, 1)) AS mes_sql\n"
        "FROM stg.fases f\n"
        "LEFT JOIN stg.obras o ON o.obra_id = f.obra_id\n"
        "WHERE f.numero_fase >= 1\n"
        "  AND f.anio IS NOT NULL\n"
        "  AND f.mes  IS NOT NULL"
        f"{_filtro_de_obras(obras, 'f')}\n"
        "ORDER BY 1, 3"
    )


def sql_claves_repetidas(obras: Sequence[int] | None = None) -> str:
    """Cuántas (obra, ámbito, partida, mes) reales tienen más de una fila."""
    return (
        "SELECT count(*) FROM (\n"
        "    SELECT obra_id, ambito_id, partida_id, anio_mes\n"
        "    FROM stg.plan_mensual\n"
        "    WHERE ambito_id IN (3, 7)"
        f"{_filtro_de_obras(obras)}\n"
        "    GROUP BY obra_id, ambito_id, partida_id, anio_mes\n"
        "    HAVING count(*) > 1\n"
        ") repetidas"
    )


def sql_marcas(obras: Sequence[int] | None = None) -> str:
    """Tres números: relleno que mueve, deshacer que no mueve, meses mixtos."""
    return (
        "WITH reales AS (\n"
        "    SELECT obra_id, ambito_id, anio_mes, es_relleno, es_deshacer,\n"
        "           (importe_mes <> 0 OR COALESCE(importe_mes_raw, 0) <> 0\n"
        "            OR can_mes <> 0 OR COALESCE(total_incurrido_mes, 0) <> 0) AS mueve\n"
        "    FROM stg.plan_mensual\n"
        "    WHERE ambito_id IN (3, 7)"
        f"{_filtro_de_obras(obras)}\n"
        "),\n"
        "meses AS (\n"
        "    SELECT obra_id, ambito_id, anio_mes\n"
        "    FROM reales\n"
        "    GROUP BY obra_id, ambito_id, anio_mes\n"
        "    HAVING bool_or(COALESCE(es_relleno, FALSE))\n"
        "       AND bool_or(NOT COALESCE(es_relleno, FALSE))\n"
        ")\n"
        "SELECT (SELECT count(*) FROM reales WHERE es_relleno AND mueve)\n"
        "           AS relleno_con_movimiento,\n"
        "       (SELECT count(*) FROM reales WHERE es_deshacer AND NOT mueve)\n"
        "           AS deshacer_sin_movimiento,\n"
        "       (SELECT count(*) FROM meses) AS meses_mixtos"
    )
