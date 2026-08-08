# etl_sigrid/infrastructure/azure/entra_token.py
"""
Obtención de tokens de Microsoft Entra para autenticarse contra Azure Database
for PostgreSQL (`PG_AUTH_MODE=entra`).

ESTADO OPERATIVO (2026-08-08): implementado y probado, pero **inactivo**. El
humano descartó habilitar la autenticación Entra en `psql-albaranes-rs9k2`
porque es una operación de servidor y ese servidor sirve además a `albaranes` y
`partes`, ambas en uso. El modo en producción es `password`, con la contraseña
en Key Vault, igual que hacen esas dos bases. Este módulo queda listo para el
día que se habilite; mientras tanto nadie lo invoca.

Dos decisiones que conviene no deshacer:

  - `azure.identity` se importa DENTRO de las funciones, no en el módulo: el
    desarrollo local no necesita el paquete y el ETL debe arrancar sin él.
  - Si el token no se puede obtener, se levanta un error explicando el plan B.
    NUNCA se recurre a la contraseña por detrás: eso convertiría un fallo de
    configuración en un cambio silencioso del modelo de seguridad.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from etl_sigrid.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

# Ámbito OAuth de Azure Database for PostgreSQL.
RESOURCE = "https://ossrdbms-aad.database.windows.net/.default"

# Texto único del plan B, para que el operador lea siempre lo mismo.
PLAN_B = (
    "PG_AUTH_MODE=entra está configurado pero no se ha podido obtener un token de "
    "Microsoft Entra. No se recurre a la contraseña automáticamente. Plan B: usar "
    "PG_AUTH_MODE=password con la contraseña del rol nativo guardada en Key Vault "
    "(nunca en el repositorio). Ver docs/runbook_postgres_azure.md."
)


@dataclass(frozen=True, slots=True)
class _TokenCacheado:
    """Token en memoria con su instante de caducidad (epoch en segundos)."""

    valor: str
    expires_on: float


class EntraTokenProvider:
    """
    Proveedor de tokens con caché.

    `credential` es inyectable para poder probar sin red. `margin_s` es el
    colchón con el que se considera que un token está a punto de caducar: se
    pide uno nuevo antes de que expire, no cuando ya ha expirado.
    """

    RESOURCE = RESOURCE

    def __init__(self, credential: Any | None = None, margin_s: int = 300) -> None:
        self._credential = credential
        self._margin_s = margin_s
        self._cache: _TokenCacheado | None = None

    def get_token(self) -> str:
        """
        Devuelve un token válido. Reutiliza el cacheado mientras le queden más
        de `margin_s` segundos de vida (R4).
        """
        cache = self._cache
        if cache is not None and cache.expires_on - time.time() > self._margin_s:
            return cache.valor

        credencial = self._get_credential()
        try:
            token = credencial.get_token(self.RESOURCE)
        except Exception as e:  # se re-lanza con el texto del plan B
            raise RuntimeError(f"{PLAN_B} Detalle: {e}") from e

        self._cache = _TokenCacheado(valor=token.token, expires_on=float(token.expires_on))
        logger.debug("entra_token_obtenido", expires_on=self._cache.expires_on)
        return self._cache.valor

    def _get_credential(self) -> Any:
        """Credencial inyectada o `DefaultAzureCredential` construida al vuelo."""
        if self._credential is not None:
            return self._credential

        try:
            from azure.identity import DefaultAzureCredential
        except ImportError as e:
            raise RuntimeError(
                f"{PLAN_B} Detalle: el paquete 'azure-identity' no está instalado."
            ) from e

        self._credential = DefaultAzureCredential()
        return self._credential


# Instancia compartida por todo el proceso: la caché del token solo sirve de
# algo si las conexiones sucesivas del ETL preguntan al mismo proveedor.
_default_provider: EntraTokenProvider | None = None


def get_default_token_provider() -> EntraTokenProvider:
    """Proveedor por defecto del proceso (perezoso, único)."""
    global _default_provider
    if _default_provider is None:
        _default_provider = EntraTokenProvider()
    return _default_provider
