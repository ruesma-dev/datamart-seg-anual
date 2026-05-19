# etl_sigrid/application/steps/load_excel_aux_step.py
"""
Step que carga los Excels auxiliares a aux.*.

Pendiente de implementar en la próxima iteración. Stub que indica el estado
y deja el DAG completo desde el inicio para que el orquestador funcione.
"""

from __future__ import annotations

from datetime import datetime

from config.settings import Settings
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus


class LoadExcelAuxStep(PipelineStep):
    """Carga TipoPartida.xlsx, TipoCoste.xlsx, mapeo_proporcionales.xlsx a aux.*."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def name(self) -> str:
        return "load_excel_aux"

    @property
    def stage(self) -> str:
        return "load_aux"

    def run(self) -> StepResult:
        result = self._new_result()
        result.status = StepStatus.SKIPPED
        result.finished_at = datetime.utcnow()
        result.error_message = "No implementado todavía (pendiente próxima iteración)"
        return result
