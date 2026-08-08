# etl_sigrid/application/steps/apply_grants_step.py
"""
Step que reaplica los permisos de lectura del rol del MCP.

No es cosmético y no se puede saltar: las vistas de `mart`, `cierre`, `compras`
y `retenciones` se construyen con `DROP VIEW ... CASCADE` seguido de `CREATE`,
y un DROP se lleva por delante los GRANT. Sin este paso, el MCP deja de ver los
datos la primera noche que corre el ETL.

Dos comportamientos deliberados, ambos para que un problema de permisos no
tumbe el pipeline nocturno:

  - sin `PG_READONLY_ROLE` configurado (desarrollo local), el paso es un no-op
    que ni siquiera abre conexión;
  - si el rol está configurado pero no existe en el servidor, se avisa en el
    log y se termina en SUCCESS.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.client_factory import build_postgres_client

if TYPE_CHECKING:  # pragma: no cover - solo para anotaciones
    from config.settings import Settings
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

logger = get_logger(__name__)


class ApplyGrantsStep(PipelineStep):
    """Reaplica USAGE + SELECT del rol de solo lectura tras reconstruir las vistas."""

    def __init__(self, settings: Settings, client: PostgresClient | None = None) -> None:
        self._settings = settings
        # `client` existe para poder probar el paso sin BBDD. En producción es
        # None y el cliente lo construye la factoría.
        self._client = client

    @property
    def name(self) -> str:
        return "apply_grants"

    @property
    def stage(self) -> str:
        return "grants"

    @property
    def depends_on(self) -> list[str]:
        return ["build_mart"]

    def run(self) -> StepResult:
        result = self._new_result()
        pg_settings = self._settings.postgres
        rol = (pg_settings.readonly_role or "").strip()

        if not rol:
            logger.info("apply_grants_sin_rol_configurado")
            result.status = StepStatus.SUCCESS
            result.rows_processed = 0
            result.metadata["motivo"] = "PG_READONLY_ROLE vacío: nada que aplicar"
            result.finished_at = datetime.utcnow()
            return result

        pg = self._client or build_postgres_client(self._settings)

        try:
            if not pg.role_exists(rol):
                logger.warning(
                    "apply_grants_rol_inexistente",
                    role=rol,
                    detalle="créalo con infra/sql/02_roles.sql",
                )
                result.status = StepStatus.SUCCESS
                result.rows_processed = 0
                result.metadata["motivo"] = f"el rol '{rol}' no existe en el servidor"
                result.finished_at = datetime.utcnow()
                return result

            sentencias = pg.apply_readonly_grants(
                readonly_role=rol,
                owner_role=(pg_settings.set_role or "").strip(),
                schemas=pg_settings.consumption_schema_list,
            )
        except Exception as e:  # el resto del pipeline ya ha terminado bien
            logger.error("apply_grants_fallido", role=rol, error=str(e))
            result.status = StepStatus.FAILED
            result.error_message = str(e)
            result.finished_at = datetime.utcnow()
            return result

        result.status = StepStatus.SUCCESS
        result.rows_processed = len(sentencias)
        result.metadata["esquemas"] = pg_settings.consumption_schema_list
        result.finished_at = datetime.utcnow()
        return result
