# etl_sigrid/domain/entities.py
"""
Entidades de dominio del pipeline. No dependen de ninguna tecnología concreta
(ni psycopg, ni httpx). Solo describen QUÉ pasa, no CÓMO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    """Estado posible de la ejecución de un Step."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    # F-024. Vocabulario, no un estado que devuelva ningún `StepResult` vivo:
    # lo escribe la marca de huérfanas sobre filas que quedaron en RUNNING
    # porque el proceso que las abrió murió DESDE FUERA (deadline de Azure,
    # OOM, reinicio de nodo) y no llegó a cerrarlas. Distinguirlo de FAILED
    # importa: FAILED es «el paso se ejecutó y salió mal»; ABORTED es «nadie
    # sabe qué pasó con este paso».
    ABORTED = "ABORTED"


@dataclass(slots=True)
class StepResult:
    """Resultado de la ejecución de un Step."""

    step_name: str
    status: StepStatus
    started_at: datetime
    finished_at: datetime | None = None
    rows_processed: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(slots=True)
class TableSpec:
    """Especificación de una tabla a extraer de Sigrid."""

    source_table: str
    target_table: str
    id_column: str = "ide"
    incremental_column: str | None = "tiemod"
    where: str | None = None
    exclude_columns: list[str] = field(default_factory=list)
    page_size_override: int | None = None  # si None, usa el default del cliente


@dataclass(slots=True)
class ColumnSpec:
    """Metadata de una columna obtenida de INFORMATION_SCHEMA.COLUMNS de Sigrid."""

    name: str
    sql_server_type: str
    char_max_length: int | None
    numeric_precision: int | None
    numeric_scale: int | None
    is_nullable: bool

    @property
    def postgres_type(self) -> str:
        """Mapea el tipo SQL Server al tipo Postgres equivalente."""
        mt = self.sql_server_type.lower()

        if mt in ("bigint",):
            return "BIGINT"
        if mt in ("int", "integer"):
            return "INTEGER"
        if mt in ("smallint",):
            return "SMALLINT"
        if mt in ("tinyint",):
            return "SMALLINT"
        if mt == "bit":
            return "BOOLEAN"
        if mt in ("float", "real"):
            return "DOUBLE PRECISION"
        if mt in ("decimal", "numeric", "money", "smallmoney"):
            p = self.numeric_precision or 18
            s = self.numeric_scale or 4
            return f"NUMERIC({p},{s})"
        if mt in ("char", "nchar", "varchar", "nvarchar"):
            if self.char_max_length is None or self.char_max_length <= 0 or self.char_max_length > 4000:
                return "TEXT"
            return f"VARCHAR({self.char_max_length})"
        if mt in ("text", "ntext"):
            return "TEXT"
        if mt == "date":
            return "DATE"
        if mt in ("datetime", "datetime2", "smalldatetime", "datetimeoffset"):
            return "TIMESTAMP"
        if mt == "time":
            return "TIME"
        if mt in ("binary", "varbinary", "image"):
            return "BYTEA"
        if mt == "uniqueidentifier":
            return "UUID"

        # Fallback seguro: TEXT preserva el dato sin truncar
        return "TEXT"
