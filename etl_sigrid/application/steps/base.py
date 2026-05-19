# etl_sigrid/application/steps/base.py
"""
Clase base de los Steps del pipeline. Define el contrato:
  - name           : identificador único
  - stage          : a qué stage pertenece (ingest, stage, build_aux, build_mart)
  - depends_on     : lista de nombres de Steps que deben haber corrido antes
  - run(context)   : ejecuta el Step. Debe ser idempotente.

El Orchestrator usa estas propiedades para resolver el DAG y ejecutarlos en orden.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from etl_sigrid.domain.entities import StepResult, StepStatus


class PipelineStep(ABC):
    """Contrato de un paso del pipeline."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador único del Step."""

    @property
    @abstractmethod
    def stage(self) -> str:
        """Nombre del stage al que pertenece (ingest/stage/build_aux/build_mart)."""

    @property
    def depends_on(self) -> list[str]:
        """Steps que deben haber terminado antes de ejecutar este. Por defecto, ninguno."""
        return []

    @abstractmethod
    def run(self) -> StepResult:
        """Ejecuta el Step. Devuelve un StepResult con métricas."""

    def _new_result(self) -> StepResult:
        """Helper para crear un StepResult arrancando ahora."""
        return StepResult(
            step_name=self.name,
            status=StepStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
