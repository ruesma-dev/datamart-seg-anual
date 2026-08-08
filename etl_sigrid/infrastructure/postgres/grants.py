# etl_sigrid/infrastructure/postgres/grants.py
"""
Generación de las sentencias de permisos del rol de solo lectura (el del MCP).

Por qué esto es Python y no un fichero .sql: haría falta un bloque
`DO $$ ... $$` con el nombre del rol parametrizado, y `_split_sql_statements`
de `postgres_client.py` no sabe manejar `$$` — está escrito en su propio
docstring. Generarlo aquí evita la trampa y hace la unidad comprobable sin BBDD.

Por qué hay que reaplicarlos en cada ejecución: siete ficheros SQL de `mart`,
`cierre` y `compras` hacen `DROP VIEW ... CASCADE` seguido de `CREATE VIEW`, y
un DROP se lleva por delante los GRANT concedidos sobre esa vista. El
`ALTER DEFAULT PRIVILEGES` cubre lo que se cree DESPUÉS, no lo ya existente:
son complementarios, no alternativos.
"""

from __future__ import annotations

from collections.abc import Sequence

from psycopg import sql


def build_readonly_grant_statements(
    readonly_role: str,
    owner_role: str,
    schemas: Sequence[str],
    *,
    database: str | None = None,
) -> list[str]:
    """
    Sentencias que dejan a `readonly_role` con lectura sobre `schemas`.

    Función pura: devuelve texto SQL con los identificadores ya citados, sin
    tocar ninguna conexión.

    `owner_role` es el rol de grupo propietario de los objetos. Se necesita
    para `ALTER DEFAULT PRIVILEGES FOR ROLE`, porque los privilegios por
    defecto se declaran POR rol creador: si el ETL crea las vistas como
    `sigrid_dm_etl`, la regla tiene que estar puesta para ese rol y no para
    quien ejecute este código. Si viene vacío, se omite la cláusula `FOR ROLE`
    y la regla aplica al rol de la sesión (caso de desarrollo local).
    """
    ro = sql.Identifier(readonly_role)
    sentencias: list[sql.Composable] = []

    if database:
        sentencias.append(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), ro
            )
        )

    for esquema in schemas:
        esq = sql.Identifier(esquema)
        sentencias.append(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(esq, ro))
        sentencias.append(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(esq, ro)
        )
        if owner_role:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA {} "
                    "GRANT SELECT ON TABLES TO {}"
                ).format(sql.Identifier(owner_role), esq, ro)
            )
        else:
            sentencias.append(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}"
                ).format(esq, ro)
            )

    return [s.as_string(None) for s in sentencias]
