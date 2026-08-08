# etl_sigrid/application/ports.py
"""
Puertos de la capa de aplicación: lo que el pipeline necesita del mundo
exterior, expresado sin nombrar ninguna tecnología.

Las implementaciones viven en `etl_sigrid/infrastructure/` y se inyectan desde
`main.py`, que es donde se compone el pipeline.
"""

from __future__ import annotations

from typing import Protocol

from etl_sigrid.domain.entities import StepResult


class StepRunRecorder(Protocol):
    """
    Registra la ejecución de un paso ya terminado.

    Existe porque hoy solo `ingest_raw` y `build_stg` escriben en
    `_meta.etl_runs` desde dentro, y los pasos pesados —`build_mart`,
    `build_cierre`— no dejan rastro persistente. Son justamente los que hay que
    medir en un SKU de 1 vCPU y 2 GB de RAM.
    """

    def record(self, stage: str, result: StepResult) -> None:
        """Persiste el resultado. No debe lanzar: medir no puede tumbar la carga."""
        ...
