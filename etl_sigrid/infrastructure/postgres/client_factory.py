# etl_sigrid/infrastructure/postgres/client_factory.py
"""
Única forma de construir un `PostgresClient` a partir de la configuración.

Existe porque los steps del pipeline construyen su propio cliente (cada uno
abre y cierra sus conexiones) y todos deben heredar las mismas garantías:

  - la cadena de conexión se resuelve en cada conexión (token de Entra), no una
    sola vez al arrancar;
  - `PG_SET_ROLE` se aplica como primera sentencia de cada sesión, de modo que
    los objetos que crea el humano y los que crea el job nocturno tengan el
    mismo propietario;
  - `PG_AUTO_CREATE_DB=false` desactiva de verdad el `CREATE DATABASE`, también
    dentro de los steps.

Si un step construyera el cliente por su cuenta con la cadena de conexión
"pelada", esas tres garantías se perderían justo en el pipeline nocturno, que
es donde importan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from etl_sigrid.infrastructure.postgres.conninfo import (
    make_admin_conninfo_provider,
    make_conninfo_provider,
)
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import PostgresSettings, Settings


def build_postgres_client(settings: Settings) -> PostgresClient:
    """Cliente Postgres configurado desde el bundle de `Settings`."""
    return build_postgres_client_from(settings.postgres)


def build_postgres_client_from(pg: PostgresSettings) -> PostgresClient:
    """Cliente Postgres configurado desde `PostgresSettings`."""
    return PostgresClient(
        conninfo=make_conninfo_provider(pg),
        admin_conninfo=make_admin_conninfo_provider(pg),
        target_db=pg.db,
        auto_create_db=pg.auto_create_db,
        set_role=pg.set_role,
    )
