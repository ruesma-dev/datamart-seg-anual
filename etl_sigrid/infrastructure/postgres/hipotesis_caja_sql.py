# etl_sigrid/infrastructure/postgres/hipotesis_caja_sql.py
"""
El SQL y las filas de la carga de hipótesis de caja (F-140, R3 y R4).

`build_tesoreria` lee y valida `config/hipotesis_caja.yaml`; si no hay
errores, `PostgresClient.cargar_hipotesis_caja` vacía y llena las dos tablas
con esto, en UNA transacción. Los valores van como JSONB (`Json`): un DIAS, un
PORCENTAJE, una OPCION o un MAPA_DIAS caben en la misma columna, y nada se
interpola en el texto del SQL.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from psycopg.types.json import Json

from etl_sigrid.domain.proyeccion_caja import Hipotesis

#: Las dos tablas de la carga, y solo ellas.
SQL_VACIAR = "TRUNCATE tesoreria.hipotesis_caja, tesoreria.hipotesis_caja_manual"

SQL_INSERT_CATALOGO = (
    "INSERT INTO tesoreria.hipotesis_caja (codigo, sentido, descripcion, unidad, "
    "valor_defecto, opciones, fuente_defecto, ingrediente, validado, fecha_validacion, "
    "admite_obra) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

SQL_INSERT_MANUAL = (
    "INSERT INTO tesoreria.hipotesis_caja_manual (clave_obra, codigo, valor, motivo, fecha) "
    "VALUES (%s, %s, %s, %s, %s)"
)


def filas_catalogo(catalogo: Iterable[Hipotesis]) -> list[tuple[Any, ...]]:
    """Una tupla por hipótesis, en el orden de las columnas de `hipotesis_caja`."""
    return [
        (
            h.codigo, h.sentido, h.descripcion, h.unidad,
            Json(h.valor_defecto),
            Json(list(h.opciones)) if h.opciones else None,
            h.fuente_defecto, h.ingrediente, h.validado, h.fecha_validacion,
            h.admite_obra,
        )
        for h in catalogo
    ]


def filas_manuales(obras: Sequence[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    """Una tupla por valor de obra del YAML (ya validado), en el orden de la tabla."""
    return [
        (o["clave_obra"], o["codigo"], Json(o["valor"]), o["motivo"], o["fecha"])
        for o in obras
    ]
