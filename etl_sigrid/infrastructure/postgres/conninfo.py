# etl_sigrid/infrastructure/postgres/conninfo.py
"""
Construcción de la cadena de conexión a Postgres y redactado seguro para logs.

Este módulo es deliberadamente una hoja: no importa nada de `config` en tiempo
de ejecución (solo para anotar tipos), de manera que `config/settings.py` pueda
importarlo sin ciclos.

Dos ideas que justifican que esto no sea un f-string en `settings.py`:

  1. La cadena se cita con `psycopg.conninfo.make_conninfo`. Con el plan B de
     autenticación (contraseña generada y guardada en Key Vault) la contraseña
     puede contener espacios o comillas, y un f-string sin citar produciría una
     cadena inválida o, peor, una conexión a otro sitio.
  2. Con `PG_AUTH_MODE=entra` la "contraseña" es un token que caduca, así que
     lo que se le pasa al cliente no es una cadena sino un proveedor callable
     que la resuelve en cada conexión.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from psycopg.conninfo import make_conninfo

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import PostgresSettings


# Sufijo DNS de los Azure Database for PostgreSQL Flexible Server.
AZURE_PG_HOST_SUFFIX = ".postgres.database.azure.com"

# Modos de TLS que dejan la conexión sin cifrar o permiten degradarla. Contra
# un servidor de Azure accesible por endpoint público son inaceptables.
SSLMODES_DEBILES = ("disable", "allow", "prefer")

# Lo que se emite cuando no se configura PG_SSLMODE.
SSLMODE_AZURE = "require"
SSLMODE_LOCAL = "prefer"  # el valor por defecto de libpq: no cambia nada en local


def is_azure_host(host: str) -> bool:
    """True si el host es un Flexible Server de Azure (por su sufijo DNS)."""
    return host.strip().lower().endswith(AZURE_PG_HOST_SUFFIX)


def default_sslmode(host: str) -> str:
    """Modo TLS que se aplica cuando `PG_SSLMODE` está vacío (R1)."""
    return SSLMODE_AZURE if is_azure_host(host) else SSLMODE_LOCAL


def build_conninfo(pg: PostgresSettings, password: str, *, dbname: str | None = None) -> str:
    """
    Cadena de conexión psycopg-compatible.

    `password` se recibe ya resuelta (contraseña o token de Entra) en vez de
    leerse de la configuración: así este módulo no decide el modo de
    autenticación y se puede probar sin credenciales.
    """
    return make_conninfo(
        host=pg.host,
        port=pg.port,
        dbname=dbname or pg.db,
        user=pg.user,
        password=password,
        sslmode=pg.effective_sslmode,
    )


def resolve_password(pg: PostgresSettings) -> str:
    """
    Devuelve la contraseña a usar según `PG_AUTH_MODE`.

    En modo `entra` NO se lee `PG_PASSWORD` (R3): se pide un token de acceso.
    Si no se puede obtener, se propaga el error sin recurrir a la contraseña
    (R5): degradar en silencio a otro modelo de autenticación es peor que
    fallar.
    """
    if pg.auth_mode == "entra":
        from etl_sigrid.infrastructure.azure.entra_token import get_default_token_provider

        return get_default_token_provider().get_token()
    return pg.password.get_secret_value()


def make_conninfo_provider(pg: PostgresSettings) -> Callable[[], str]:
    """
    Proveedor de cadena de conexión a la base del datamart.

    Es un callable y no una cadena porque el token de Entra caduca (~1 h) y el
    ETL abre conexiones a lo largo de toda la ejecución: una cadena fija
    fallaría a mitad de la carga inicial, que es la ejecución más larga.
    """

    def _provider() -> str:
        return build_conninfo(pg, resolve_password(pg))

    return _provider


def make_admin_conninfo_provider(pg: PostgresSettings) -> Callable[[], str]:
    """Igual que `make_conninfo_provider` pero contra la base administrativa."""

    def _provider() -> str:
        return build_conninfo(pg, resolve_password(pg), dbname=pg.admin_db)

    return _provider


# Captura `password=` seguido de un valor citado ('...' con escapes) o de una
# secuencia sin espacios. Cubre las dos formas que emite make_conninfo.
_PASSWORD_RE = re.compile(
    r"(?i)\b(password)\s*=\s*(?:'(?:\\.|[^'\\])*'|\S*)",
)


def safe_dsn(conninfo: str) -> str:
    """
    Versión de la cadena de conexión apta para logs y mensajes de error (R6).

    Sustituye el valor de `password` por asteriscos. Es lo ÚNICO que se registra:
    ni la contraseña ni el token de Entra deben aparecer nunca en un log.
    """
    return _PASSWORD_RE.sub(r"\1=***", conninfo)
