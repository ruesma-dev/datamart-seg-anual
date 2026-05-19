# etl_sigrid/application/orchestrator.py
"""
Orchestrator del pipeline. Resuelve el DAG de Steps (con sus depends_on)
mediante orden topológico y los ejecuta secuencialmente.

Diseño deliberado: secuencial, no paralelo. La complejidad de paralelizar
no compensa para este volumen de datos. Y secuencial es mucho más fácil
de debuggear.
"""

from __future__ import annotations

from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Ejecuta una colección de Steps respetando sus dependencias."""

    def __init__(self, steps: list[PipelineStep]) -> None:
        self._steps = steps
        self._by_name = {s.name: s for s in steps}
        self._validate_dag()

    def run_all(self) -> list[StepResult]:
        """Ejecuta todos los Steps en orden topológico."""
        ordered = self._topological_sort()
        results: list[StepResult] = []

        for step in ordered:
            # Si alguna dependencia falló, marcamos este como SKIPPED
            if any(
                r.step_name in step.depends_on and r.status != StepStatus.SUCCESS
                for r in results
            ):
                skipped = StepResult(
                    step_name=step.name,
                    status=StepStatus.SKIPPED,
                    started_at=results[-1].finished_at if results else None,  # type: ignore[arg-type]
                    finished_at=results[-1].finished_at if results else None,
                    error_message="Saltado porque una dependencia falló",
                )
                logger.warning("step_skipped", step=step.name)
                results.append(skipped)
                continue

            logger.info("step_starting", step=step.name, stage=step.stage)
            try:
                r = step.run()
            except Exception as e:  # captura cualquier excepción no manejada
                logger.exception("step_unhandled_exception", step=step.name)
                r = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    started_at=results[-1].finished_at if results else None,  # type: ignore[arg-type]
                    error_message=str(e),
                )

            logger.info(
                "step_finished",
                step=step.name,
                status=r.status.value,
                rows=r.rows_processed,
                duration_s=round(r.duration_seconds, 2),
            )
            results.append(r)

        return results

    def run_one(self, name: str) -> StepResult:
        """Ejecuta un Step concreto por nombre (ignora sus dependencias)."""
        if name not in self._by_name:
            raise KeyError(f"Step '{name}' no registrado")
        step = self._by_name[name]
        logger.info("step_starting_single", step=name)
        return step.run()

    # ---------------------------------------------------------------------
    # DAG topológico
    # ---------------------------------------------------------------------

    def _validate_dag(self) -> None:
        names = set(self._by_name)
        for s in self._steps:
            for dep in s.depends_on:
                if dep not in names:
                    raise ValueError(f"Step '{s.name}' depende de '{dep}' que no existe")

    def _topological_sort(self) -> list[PipelineStep]:
        """Devuelve los Steps ordenados topológicamente (DFS post-order)."""
        visited: set[str] = set()
        temp: set[str] = set()
        result: list[PipelineStep] = []

        def visit(node: PipelineStep) -> None:
            if node.name in visited:
                return
            if node.name in temp:
                raise ValueError(f"Ciclo detectado en el DAG en torno a '{node.name}'")
            temp.add(node.name)
            for dep_name in node.depends_on:
                visit(self._by_name[dep_name])
            temp.discard(node.name)
            visited.add(node.name)
            result.append(node)

        for s in self._steps:
            visit(s)
        return result
