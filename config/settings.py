# config/settings.py
"""
Configuración centralizada del ETL. Lee de .env y de YAMLs en config/.

Usa pydantic-settings para validación estricta. Si falta una variable obligatoria,
la app aborta al arrancar con un mensaje claro en lugar de fallar a mitad del pipeline.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from etl_sigrid.infrastructure.postgres.conninfo import (
    SSLMODES_DEBILES,
    default_sslmode,
    is_azure_host,
    make_admin_conninfo_provider,
    make_conninfo_provider,
)

# Versión del ETL. Mantener sincronizada con [project].version de pyproject.toml.
ETL_VERSION = "0.1.0"

# Marca de "no desplegado": el valor que toman los metadatos de build cuando
# el ETL corre desde el repositorio en vez de desde una imagen de contenedor.
BUILD_UNKNOWN = "local"


def get_build_info() -> dict[str, str]:
    """
    Metadatos de la build en curso, para diagnóstico.

    En Azure los inyecta el Dockerfile como variables de entorno en tiempo de
    build (ver infra/70_build_image.ps1). Ejecutando desde el repositorio no
    existen, y entonces valen BUILD_UNKNOWN.
    """
    return {
        "version": ETL_VERSION,
        "image_tag": os.getenv("IMAGE_TAG") or BUILD_UNKNOWN,
        "build_date": os.getenv("BUILD_DATE") or BUILD_UNKNOWN,
    }


# Máximo que acepta sigrid-api para timeout_seconds (ver azure-apps/sigrid_api.md).
SIGRID_API_TIMEOUT_MAX_S = 230.0


class SigridApiSettings(BaseSettings):
    """Conexión a la Function App sigrid-api."""

    model_config = SettingsConfigDict(env_prefix="SIGRID_API_", env_file=".env", extra="ignore")

    base_url: str = Field(..., description="URL completa de la Function App")
    function_key: SecretStr = Field(..., description="Cabecera x-functions-key")
    database: str = Field("ruesma", description="Nombre BBDD on-prem (debe estar en ALLOWED_DATABASES)")
    # TECHO DE SIGRID-API: su balanceador corta a los 230 s y la API valida
    # `timeout_seconds <= 230` (HTTP 400 si se supera). Este default vale para
    # el job de Azure, que no lleva .env: la noche del 2026-08-18 el valor 300
    # heredado hizo fallar las 31 tablas de la ingesta antes de leer una fila.
    timeout_s: float = Field(
        SIGRID_API_TIMEOUT_MAX_S, le=SIGRID_API_TIMEOUT_MAX_S,
        description="Timeout HTTP por petición SQL (máximo 230, techo de sigrid-api)",
    )
    page_size: int = Field(10000, description="Filas por petición (<= MAX_ALLOWED_ROWS de la API)")
    max_retries: int = Field(3, description="Reintentos automáticos en errores transitorios")


# Esquemas sobre los que se concede lectura al rol del MCP.
#
# La spec de F-005 proponía restringirlo a los cinco esquemas de consumo
# (mart, cierre, compras, maestro, retenciones). El humano decidió el
# 2026-08-08 que, de momento, el MCP lee todo; se revisará al rediseñar el MCP
# en F-006. Sigue siendo un parámetro (PG_CONSUMPTION_SCHEMAS) precisamente
# para poder estrecharlo entonces sin tocar código.
DEFAULT_CONSUMPTION_SCHEMAS = (
    "mart,cierre,compras,maestro,retenciones,raw,stg,aux,_meta"
)

AUTH_MODES = ("password", "entra")


class PostgresSettings(BaseSettings):
    """Conexión a Postgres destino."""

    model_config = SettingsConfigDict(env_prefix="PG_", env_file=".env", extra="ignore")

    host: str = Field("localhost")
    port: int = Field(5432)
    db: str = Field("sigrid_dm")
    user: str = Field("postgres")
    password: SecretStr = Field(SecretStr(""))
    admin_db: str = Field(
        "postgres",
        description="BBDD a la que conectarse para crear la nuestra si no existe. "
                    "Por defecto 'postgres', que siempre existe en cualquier servidor.",
    )
    sslmode: str = Field(
        "",
        description="Modo TLS de libpq. Vacío = 'require' si el host es de Azure, "
                    "'prefer' (el defecto de libpq) si no.",
    )
    auth_mode: str = Field(
        "password",
        description="'password' (contraseña de PG_PASSWORD, que en Azure viene de "
                    "Key Vault) o 'entra' (token de identidad gestionada).",
    )
    auto_create_db: bool = Field(
        True,
        description="Si es False, el ETL nunca ejecuta CREATE DATABASE ni abre "
                    "conexión contra la BBDD admin. Obligatorio contra el servidor "
                    "compartido de Azure, donde viven albaranes y partes.",
    )
    set_role: str = Field(
        "",
        description="Rol de grupo al que se hace SET ROLE al abrir cada sesión, para "
                    "que todos los objetos tengan el mismo propietario conecte quien "
                    "conecte. Contra Azure: 'sigrid_dm_etl'.",
    )
    readonly_role: str = Field(
        "",
        description="Rol de solo lectura al que se le reaplican los GRANT tras cada "
                    "ejecución. Vacío (desarrollo local) = no se aplica nada.",
    )
    consumption_schemas: str = Field(
        DEFAULT_CONSUMPTION_SCHEMAS,
        description="Esquemas, separados por comas, sobre los que el rol de solo "
                    "lectura recibe USAGE + SELECT.",
    )
    # --- Troceo del build de stg.plan_mensual (F-019) ----------------------
    # El 2026-08-09 ese build llenó el disco del servidor compartido (93,4 %) y
    # dejó a albaranes y partes en solo-lectura diez minutos. Estos tres valores
    # son los que acotan el pico y frenan el build antes de repetirlo.
    tramo_max_filas: int = Field(
        1_000_000,
        description="Peso máximo de un tramo, medido en filas de raw.obrparpre "
                    "atribuibles a sus obras. Una obra que sola lo supere va en "
                    "un tramo unitario, con aviso.",
    )
    disco_total_gb: int = Field(
        32,
        description="Tamaño total del disco del servidor Postgres, en GB. No se "
                    "cablea: el servidor puede crecer sin que cambie el código.",
    )
    disco_limite_pct: float = Field(
        80.0,
        description="Ocupación por encima de la cual el build de plan_mensual "
                    "aborta ANTES de lanzar el siguiente tramo. La protección de "
                    "Azure salta hacia el 95 %; el incidente tocó el 93,4 %.",
    )

    @field_validator("auth_mode")
    @classmethod
    def _validar_auth_mode(cls, v: str) -> str:
        modo = v.strip().lower()
        if modo not in AUTH_MODES:
            raise ValueError(
                f"PG_AUTH_MODE='{v}' no es válido. Valores admitidos: "
                f"{', '.join(AUTH_MODES)}."
            )
        return modo

    @field_validator("sslmode")
    @classmethod
    def _normalizar_sslmode(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _rechazar_tls_debil_contra_azure(self) -> PostgresSettings:
        """
        R2: contra un servidor de Azure con endpoint público, un sslmode que
        permita conexión en claro se rechaza al construir la configuración.
        Abortar aquí es preferible a descubrirlo cuando la contraseña ya ha
        viajado sin cifrar.
        """
        if self.sslmode and self.sslmode in SSLMODES_DEBILES and is_azure_host(self.host):
            raise ValueError(
                f"PG_SSLMODE='{self.sslmode}' deja la conexión sin cifrar y el host "
                f"'{self.host}' es un servidor de Azure. Usa PG_SSLMODE=require "
                f"(o déjalo vacío: contra Azure el valor por defecto ya es 'require')."
            )
        return self

    @property
    def effective_sslmode(self) -> str:
        """Modo TLS efectivo: el configurado, o el que corresponde al host (R1)."""
        return self.sslmode or default_sslmode(self.host)

    @property
    def consumption_schema_list(self) -> list[str]:
        """`consumption_schemas` como lista, sin blancos ni entradas vacías."""
        return [s.strip() for s in self.consumption_schemas.split(",") if s.strip()]

    @property
    def conninfo(self) -> str:
        """
        Cadena de conexión psycopg-compatible a la BBDD del data mart.

        Se mantiene por compatibilidad con el código existente. Con
        PG_AUTH_MODE=entra resuelve un token en cada acceso; el camino
        recomendado es el proveedor callable de `conninfo.make_conninfo_provider`.
        """
        return make_conninfo_provider(self)()

    @property
    def admin_conninfo(self) -> str:
        """Cadena de conexión a la BBDD admin (para CREATE DATABASE si hace falta)."""
        return make_admin_conninfo_provider(self)()


class AuxExcelSettings(BaseSettings):
    """
    Ubicación de los Excels auxiliares que lee el step load_aux.

    Cada valor admite DOS formas, y el step decide por la forma del valor (no
    hay variable de modo que mantener coherente):

    - Ruta del sistema de ficheros: Windows (``C:/datos/X.xlsx``), POSIX
      (``/datos/X.xlsx``) o de red UNC (``\\\\servidor\\recurso\\X.xlsx``).
    - URI de Azure Blob Storage:
      ``https://<cuenta>.blob.core.windows.net/<contenedor>/<blob>``. Se lee
      con identidad gestionada (``DefaultAzureCredential``); NO se admiten
      cadenas de conexión, claves de cuenta ni tokens SAS.

    Vacío = ese fichero se omite. Las tres vacías = el step queda SKIPPED.
    """

    model_config = SettingsConfigDict(env_prefix="AUX_EXCEL_", env_file=".env", extra="ignore")

    tipo_partida: str = Field("", description="Ruta local o URI de blob de TipoPartida.xlsx")
    tipo_coste: str = Field("", description="Ruta local o URI de blob de TipoCoste.xlsx")
    mapeo_proporcionales: str = Field(
        "", description="Ruta local o URI de blob de mapeo_proporcionales.xlsx"
    )

    def entries(self) -> tuple[tuple[str, str, str], ...]:
        """
        (nombre_lógico, variable_de_entorno, valor) de los tres ficheros.

        Existe para que el step no tenga que repetir los nombres `AUX_EXCEL_*`:
        el mensaje de error que apunta a la variable responsable (R8-R10) sale
        de aquí, no de una lista duplicada en otro módulo.
        """
        prefijo = str(self.model_config.get("env_prefix") or "")
        return tuple(
            (nombre, f"{prefijo}{nombre.upper()}", str(getattr(self, nombre)))
            for nombre in type(self).model_fields
        )


class LoggingSettings(BaseSettings):
    """Configuración de logging structlog."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = Field("INFO")
    log_format: str = Field("console", description="'console' (legible) o 'json' (producción)")


class Settings:
    """Bundle único con todas las configuraciones del proyecto."""

    def __init__(self) -> None:
        self.sigrid_api = SigridApiSettings()
        self.postgres = PostgresSettings()
        self.aux_excel = AuxExcelSettings()
        self.logging = LoggingSettings()

        config_dir = Path(__file__).resolve().parent
        self.tables_sigrid = self._load_yaml(config_dir / "tables_sigrid.yaml")
        self.business_rules = self._load_yaml(config_dir / "business_rules.yaml")

    @staticmethod
    def _load_yaml(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Falta archivo de configuración: {path}")
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton de Settings. Se carga una sola vez."""
    return Settings()
