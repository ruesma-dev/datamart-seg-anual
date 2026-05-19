# tests/test_smoke.py
"""
Tests de humo: validan que los imports funcionan y las clases se pueden instanciar.
No tocan red ni BBDD, así que corren en cualquier máquina sin .env configurado.
"""

from __future__ import annotations

from etl_sigrid.domain.entities import ColumnSpec, StepResult, StepStatus, TableSpec


def test_imports() -> None:
    """Importar los módulos principales no debe lanzar excepciones."""
    from etl_sigrid.application.orchestrator import Orchestrator  # noqa: F401
    from etl_sigrid.application.steps.base import PipelineStep  # noqa: F401
    from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep  # noqa: F401
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient  # noqa: F401
    from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiClient  # noqa: F401


def test_column_spec_mapping_basic_types() -> None:
    """Mapeo SQL Server → Postgres para tipos comunes."""
    c = ColumnSpec("ide", "bigint", None, None, None, False)
    assert c.postgres_type == "BIGINT"

    c = ColumnSpec("cod", "varchar", 24, None, None, True)
    assert c.postgres_type == "VARCHAR(24)"

    c = ColumnSpec("tex", "varchar", -1, None, None, True)
    assert c.postgres_type == "TEXT"

    c = ColumnSpec("tot", "decimal", None, 18, 2, True)
    assert c.postgres_type == "NUMERIC(18,2)"

    c = ColumnSpec("hay", "bit", None, None, None, False)
    assert c.postgres_type == "BOOLEAN"

    c = ColumnSpec("fec", "datetime", None, None, None, True)
    assert c.postgres_type == "TIMESTAMP"


def test_step_result_duration() -> None:
    """StepResult.duration_seconds funciona con fechas válidas."""
    from datetime import datetime, timedelta

    started = datetime(2024, 1, 1, 12, 0, 0)
    finished = started + timedelta(seconds=42)
    r = StepResult(
        step_name="test",
        status=StepStatus.SUCCESS,
        started_at=started,
        finished_at=finished,
    )
    assert r.duration_seconds == 42.0


def test_table_spec_defaults() -> None:
    """TableSpec con defaults razonables."""
    spec = TableSpec(source_table="obr", target_table="obr")
    assert spec.id_column == "ide"
    assert spec.incremental_column == "tiemod"
    assert spec.exclude_columns == []
    assert spec.where is None
