# tests/test_f005_verificacion.py
"""
F-005 · Medición de tiempos y verificación de vistas (R28-R30, R32-R35).

Sin red ni BBDD: el grabador es un doble, las consultas se comprueban como
texto y los CSV se escriben en ficheros temporales.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.application.orchestrator import Orchestrator
from etl_sigrid.application.steps.base import PipelineStep
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.postgres.timings import Timing, format_timings

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------

class _PasoFalso(PipelineStep):
    """Paso que devuelve lo que se le diga, sin tocar nada."""

    def __init__(
        self,
        nombre: str,
        etapa: str,
        *,
        depende_de: list[str] | None = None,
        estado: StepStatus = StepStatus.SUCCESS,
        filas: int = 0,
        duracion_s: float = 1.0,
        revienta: bool = False,
    ) -> None:
        self._nombre = nombre
        self._etapa = etapa
        self._depende_de = depende_de or []
        self._estado = estado
        self._filas = filas
        self._duracion_s = duracion_s
        self._revienta = revienta

    @property
    def name(self) -> str:
        return self._nombre

    @property
    def stage(self) -> str:
        return self._etapa

    @property
    def depends_on(self) -> list[str]:
        return self._depende_de

    def run(self) -> StepResult:
        if self._revienta:
            raise RuntimeError("el paso ha fallado")
        inicio = datetime(2026, 8, 8, 3, 0, 0)
        return StepResult(
            step_name=self._nombre,
            status=self._estado,
            started_at=inicio,
            finished_at=inicio + timedelta(seconds=self._duracion_s),
            rows_processed=self._filas,
        )


class _GrabadorFalso:
    """Grabador que apunta lo que recibe."""

    def __init__(self) -> None:
        self.registros: list[tuple[str, StepResult]] = []

    def record(self, stage: str, result: StepResult) -> None:
        self.registros.append((stage, result))


class _GrabadorRoto:
    """Grabador que revienta, como reventaría si se cae la BBDD a media noche."""

    def __init__(self) -> None:
        self.intentos = 0

    def record(self, stage: str, result: StepResult) -> None:
        self.intentos += 1
        raise RuntimeError("no hay conexión con _meta.etl_runs")


# ---------------------------------------------------------------------------
# R28 · el orquestador registra cada paso
# ---------------------------------------------------------------------------

def test_f005_r28_orquestador_registra_cada_paso() -> None:
    """
    Un registro por paso, con etapa, nombre, marcas de tiempo, estado y filas.
    Hoy build_mart y build_cierre no dejan rastro por dentro: este es el que lo
    deja.
    """
    grabador = _GrabadorFalso()
    pasos = [
        _PasoFalso("ingest_raw", "ingest", filas=1000, duracion_s=120.0),
        _PasoFalso("build_stg", "stage", depende_de=["ingest_raw"], filas=900, duracion_s=60.0),
        _PasoFalso("build_mart", "build_mart", depende_de=["build_stg"], filas=800, duracion_s=300.0),
    ]

    resultados = Orchestrator(pasos, recorder=grabador).run_all()

    assert len(grabador.registros) == len(resultados) == 3
    etapas = [etapa for etapa, _ in grabador.registros]
    assert etapas == ["ingest", "stage", "build_mart"]

    for (etapa, registro), resultado in zip(grabador.registros, resultados, strict=True):
        assert registro.step_name == resultado.step_name
        assert registro.status == StepStatus.SUCCESS
        assert registro.started_at is not None
        assert registro.finished_at is not None
        assert registro.duration_seconds > 0
        assert etapa

    # El paso pesado queda medido, que es el objetivo del requisito.
    _, mart = grabador.registros[2]
    assert mart.duration_seconds == 300.0
    assert mart.rows_processed == 800


def test_f005_r28_tambien_se_registran_los_pasos_fallidos_y_saltados() -> None:
    """Un paso que falla y los que se saltan por su culpa también dejan rastro."""
    grabador = _GrabadorFalso()
    pasos = [
        _PasoFalso("build_stg", "stage", revienta=True),
        _PasoFalso("build_mart", "build_mart", depende_de=["build_stg"]),
    ]

    Orchestrator(pasos, recorder=grabador).run_all()

    estados = [r.status for _, r in grabador.registros]
    assert estados == [StepStatus.FAILED, StepStatus.SKIPPED]
    assert "el paso ha fallado" in (grabador.registros[0][1].error_message or "")


def test_f005_r28_sin_grabador_el_pipeline_sigue_funcionando() -> None:
    """El grabador es opcional: sin él, el orquestador se comporta como siempre."""
    resultados = Orchestrator([_PasoFalso("ingest_raw", "ingest")]).run_all()
    assert [r.status for r in resultados] == [StepStatus.SUCCESS]


# ---------------------------------------------------------------------------
# R29 · si falla la telemetría, el pipeline continúa
# ---------------------------------------------------------------------------

def test_f005_r29_fallo_del_grabador_no_rompe_el_pipeline() -> None:
    """
    Una caída midiendo no puede tumbar una carga de horas: se avisa en el log
    y se sigue con el resto de los pasos.
    """
    grabador = _GrabadorRoto()
    pasos = [
        _PasoFalso("ingest_raw", "ingest", filas=10),
        _PasoFalso("build_stg", "stage", depende_de=["ingest_raw"], filas=20),
    ]

    resultados = Orchestrator(pasos, recorder=grabador).run_all()

    assert [r.status for r in resultados] == [StepStatus.SUCCESS, StepStatus.SUCCESS]
    assert [r.rows_processed for r in resultados] == [10, 20]
    assert grabador.intentos == 2, "se intentó registrar cada paso, no solo el primero"


# ---------------------------------------------------------------------------
# R30 · el comando timings
# ---------------------------------------------------------------------------

def _timing(
    stage: str,
    step: str,
    minuto: int,
    duracion_s: float,
    filas: int,
    status: str = "SUCCESS",
) -> Timing:
    inicio = datetime(2026, 8, 8, 3, minuto, 0)
    return Timing(
        stage=stage,
        step=step,
        started_at=inicio,
        finished_at=inicio + timedelta(seconds=duracion_s),
        status=status,
        rows_processed=filas,
    )


def test_f005_r30_timings_formatea_la_tabla() -> None:
    """Etapa, paso, duración, filas y estado, en orden cronológico y con total."""
    mediciones = [
        # A propósito desordenadas: el formateador las ordena.
        _timing("build_mart", "build_mart", 20, 300.5, 800),
        _timing("ingest", "ingest_raw", 0, 120.0, 1000),
        _timing("stage", "build_stg", 10, 60.0, 900),
    ]

    salida = format_timings(mediciones)
    lineas = salida.splitlines()

    for columna in ("etapa", "paso", "inicio", "duración_s", "filas", "estado"):
        assert columna in lineas[0]

    filas_datos = [ln for ln in lineas if "2026-08-08" in ln]
    assert [ln.split()[1] for ln in filas_datos] == [
        "ingest_raw",
        "build_stg",
        "build_mart",
    ], "orden cronológico, no el de la lista de entrada"

    assert "300.5" in salida
    assert "SUCCESS" in salida

    total = [ln for ln in lineas if ln.startswith("TOTAL")]
    assert len(total) == 1
    assert "480.5" in total[0], "el total suma 120 + 60 + 300,5 segundos"
    assert "2,700" in total[0], "y las filas de los tres pasos"


def test_f005_r30_timings_sin_mediciones_lo_dice() -> None:
    """Una tabla vacía no es una tabla vacía: es un aviso de que no hay datos."""
    salida = format_timings([])
    assert "Sin mediciones" in salida
    assert "run-all" in salida


def test_f005_r30_timings_tolera_pasos_sin_cerrar() -> None:
    """Un paso interrumpido (sin finished_at) no rompe la tabla."""
    abierto = Timing(
        stage="ingest",
        step="ingest_raw",
        started_at=datetime(2026, 8, 8, 3, 0, 0),
        finished_at=None,
        status="RUNNING",
        rows_processed=0,
    )
    salida = format_timings([abierto])
    assert "RUNNING" in salida
    assert "0.0" in salida


def test_f005_r30_comando_timings_imprime_la_tabla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El comando existe, lee del cliente y escribe la tabla. Sin BBDD."""
    mediciones = [_timing("build_cierre", "build_cierre", 30, 45.0, 77)]

    class _ClienteFalso:
        def fetch_timings(self, last: int = 1) -> list[Timing]:
            self.last = last
            return mediciones

    cliente = _ClienteFalso()
    monkeypatch.setattr(main, "get_settings", lambda: _settings_minimo())
    monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(main, "_get_pg", lambda: cliente)

    resultado = CliRunner().invoke(main.cli, ["timings", "--last", "3"])

    assert resultado.exit_code == 0, resultado.output
    assert "build_cierre" in resultado.output
    assert "TOTAL" in resultado.output
    assert cliente.last == 3


def _settings_minimo() -> SimpleNamespace:
    """Lo justo para que el grupo de comandos arranque sin leer .env."""
    return SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console")
    )
