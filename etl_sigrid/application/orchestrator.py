# etl_sigrid/application/orchestrator.py
"""
Orchestrator del pipeline. Resuelve el DAG de Steps (con sus depends_on)
mediante orden topológico y los ejecuta secuencialmente.

Diseño deliberado: secuencial, no paralelo. La complejidad de paralelizar
no compensa para este volumen de datos. Y secuencial es mucho más fácil
de debuggear.

F-148 le añade dos cosas, las dos opcionales (sin ellas, todo como antes):

  - `terminados_en_lote`: lo que la réplica anterior de la misma ejecución del
    job ya dejó en SUCCESS. Esos pasos se omiten —sin ejecutarse ni grabar
    fila— si sus dependencias también se omiten (R21-R22).
  - `tras_paso`: un gancho que corre tras cada paso EJECUTADO, haya ido bien o
    mal. `run-all` lo usa para devolver los permisos tras cada build (R25).
"""

from __future__ import annotations

from collections.abc import Callable, Set
from datetime import datetime

from etl_sigrid.application.ports import StepRunRecorder
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.domain.reanudacion import pasos_a_omitir
from etl_sigrid.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Ejecuta una colección de Steps respetando sus dependencias."""

    def __init__(
        self,
        steps: list[PipelineStep],
        recorder: StepRunRecorder | None = None,
        *,
        terminados_en_lote: Set[str] = frozenset(),
        tras_paso: Callable[[PipelineStep, StepResult], None] | None = None,
    ) -> None:
        self._steps = steps
        self._by_name = {s.name: s for s in steps}
        self._recorder = recorder
        self._terminados_en_lote = terminados_en_lote
        self._tras_paso = tras_paso
        self._validate_dag()

    def _record(self, stage: str, result: StepResult) -> None:
        """
        Deja rastro del paso en el grabador, si hay.

        Envuelto en try/except a propósito (R29): una caída midiendo no puede
        tumbar una carga de horas. Se avisa en el log y se sigue.
        """
        if self._recorder is None:
            return
        try:
            self._recorder.record(stage, result)
        except Exception as e:  # medir nunca rompe el pipeline
            logger.warning(
                "step_run_no_registrado",
                step=result.step_name,
                stage=stage,
                error=str(e),
            )

    def _tras(self, step: PipelineStep, result: StepResult) -> None:
        """Llama al gancho `tras_paso`, si hay (F-148, R25-R26).

        Envuelto como `_record`: un gancho que revienta avisa y la noche sigue.
        Lo que haga el gancho no cambia el resultado del paso.
        """
        if self._tras_paso is None:
            return
        try:
            self._tras_paso(step, result)
        except Exception as e:  # el gancho nunca rompe el pipeline
            logger.warning("tras_paso_fallido", step=step.name, error=str(e))

    def run_all(self) -> list[StepResult]:
        """Ejecuta todos los Steps en orden topológico."""
        ordered = self._topological_sort()
        results: list[StepResult] = []
        omitidos = pasos_a_omitir(
            [(s.name, s.depends_on) for s in ordered], self._terminados_en_lote
        )

        for step in ordered:
            if step.name in omitidos:
                # F-148, R22: ni se ejecuta ni graba fila (`v_frescura` sigue
                # diciendo cuándo se construyó de verdad), y cuenta como
                # SUCCESS para sus dependientes.
                ahora = datetime.utcnow()
                logger.info("paso_reanudado", step=step.name)
                results.append(
                    StepResult(
                        step_name=step.name,
                        status=StepStatus.SUCCESS,
                        started_at=ahora,
                        finished_at=ahora,
                        metadata={"reanudado": True},
                    )
                )
                continue

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
                self._record(step.stage, skipped)
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
            self._record(step.stage, r)
            self._tras(step, r)

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
