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
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Versión del ETL. Mantener sincronizada con [project].version de pyproject.toml.
ETL_VERSION = "0.1.0"

# Marca de "no desplegado": el valor que toman los metadatos de build cuando
# el ETL corre desde el repositorio en vez de desde una imagen de contenedor.
BUILD_UNKNOWN = "local"


def get_build_info() -> dict[str, str]:
    """
    Metadatos de la build en curso, para diagnóstico.

    En Azure los inyecta el Dockerfile como variables de entorno en tiempo de
    build (ver infra/20_build_image.ps1). Ejecutando desde el repositorio no
    existen, y entonces valen BUILD_UNKNOWN.
    """
    return {
        "version": ETL_VERSION,
        "image_tag": os.getenv("IMAGE_TAG") or BUILD_UNKNOWN,
        "build_date": os.getenv("BUILD_DATE") or BUILD_UNKNOWN,
    }


class SigridApiSettings(BaseSettings):
    """Conexión a la Function App sigrid-api."""

    model_config = SettingsConfigDict(env_prefix="SIGRID_API_", env_file=".env", extra="ignore")

    base_url: str = Field(..., description="URL completa de la Function App")
    function_key: SecretStr = Field(..., description="Cabecera x-functions-key")
    database: str = Field("ruesma", description="Nombre BBDD on-prem (debe estar en ALLOWED_DATABASES)")
    timeout_s: float = Field(300.0, description="Timeout HTTP por petición SQL")
    page_size: int = Field(10000, description="Filas por petición (<= MAX_ALLOWED_ROWS de la API)")
    max_retries: int = Field(3, description="Reintentos automáticos en errores transitorios")


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

    @property
    def conninfo(self) -> str:
        """Cadena de conexión psycopg-compatible a la BBDD del data mart."""
        return (
            f"host={self.host} port={self.port} dbname={self.db} "
            f"user={self.user} password={self.password.get_secret_value()}"
        )

    @property
    def admin_conninfo(self) -> str:
        """Cadena de conexión a la BBDD admin (para CREATE DATABASE si hace falta)."""
        return (
            f"host={self.host} port={self.port} dbname={self.admin_db} "
            f"user={self.user} password={self.password.get_secret_value()}"
        )


class AuxExcelSettings(BaseSettings):
    """Rutas locales (o de red) de los Excels que carga el step load_aux."""

    model_config = SettingsConfigDict(env_prefix="AUX_EXCEL_", env_file=".env", extra="ignore")

    tipo_partida: str = Field("", description="Ruta a TipoPartida.xlsx")
    tipo_coste: str = Field("", description="Ruta a TipoCoste.xlsx")
    mapeo_proporcionales: str = Field("", description="Ruta a mapeo_proporcionales.xlsx")


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
