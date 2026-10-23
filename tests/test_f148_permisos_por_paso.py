# tests/test_f148_permisos_por_paso.py
"""
F-148 · Permisos que no dependen del final (R25-R28).

Los diez build recrean vistas con DROP + CREATE y un DROP se lleva los GRANT.
Hasta F-148 solo los devolvía `apply_grants`, el ÚLTIMO paso: una noche que
moría a medias dejaba esquemas sin permisos (incidencia del 2026-10-20). Ahora
`run-all` aplica los permisos completos tras cada build ejecutado, como
sub-fila `apply_grants.tras_<paso>`, y el `apply_grants` final sigue siendo el
que decide.

Sin red ni BBDD: `ApplyGrantsStep` y el grabador se doblan.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from etl_sigrid.application.orchestrator import Orchestrator
from etl_sigrid.domain.entities import StepResult, StepStatus


class LoggerFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    warning = info
    error = info
    debug = info
    exception = info

    def de(self, evento: str) -> list[dict]:
        return [c for e, c in self.eventos if e == evento]


class Paso:
    def __init__(
        self,
        nombre: str,
        estado: StepStatus = StepStatus.SUCCESS,
        revienta: BaseException | None = None,
        deps: list[str] | None = None,
    ) -> None:
        self._nombre = nombre
        self._estado = estado
        self._revienta = revienta
        self._deps = deps or []

    @property
    def name(self) -> str:
        return self._nombre

    @property
    def stage(self) -> str:
        return self._nombre

    @property
    def depends_on(self) -> list[str]:
        return self._deps

    def run(self) -> StepResult:
        if self._revienta is not None:
            raise self._revienta
        return StepResult(
            step_name=self._nombre,
            status=self._estado,
            started_at=datetime(2026, 10, 23),
            finished_at=datetime(2026, 10, 23),
        )


class MuerteDelProceso(BaseException):
    """Lo que no captura el orquestador: el contenedor que muere."""


class Gancho:
    """`tras_paso` que solo anota con qué paso y qué resultado se le llamó."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, str, StepStatus]] = []

    def __call__(self, paso: Paso, resultado: StepResult) -> None:
        self.llamadas.append((paso.name, resultado.step_name, resultado.status))


# ---------------------------------------------------------------------------
# Orquestador: el gancho `tras_paso` (T8)
# ---------------------------------------------------------------------------


def test_f148_r25_el_gancho_corre_tras_cada_paso_ejecutado() -> None:
    """También tras un FAILED y tras un paso que lanza; nunca tras un SKIPPED."""
    gancho = Gancho()
    pasos = [
        Paso("a"),
        Paso("b", StepStatus.FAILED),
        Paso("c", deps=["b"]),
        Paso("d", revienta=RuntimeError("x")),
    ]

    resultados = Orchestrator(pasos, tras_paso=gancho).run_all()

    assert [r.status for r in resultados] == [
        StepStatus.SUCCESS,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.FAILED,
    ]
    assert gancho.llamadas == [
        ("a", "a", StepStatus.SUCCESS),
        ("b", "b", StepStatus.FAILED),
        ("d", "d", StepStatus.FAILED),
    ]


def test_f148_r25_sin_gancho_todo_como_hoy() -> None:
    resultados = Orchestrator([Paso("a"), Paso("b", deps=["a"])]).run_all()

    assert [r.status for r in resultados] == [StepStatus.SUCCESS, StepStatus.SUCCESS]


def test_f148_r26_si_el_gancho_mismo_revienta_el_orquestador_sigue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etl_sigrid.application import orchestrator

    registro = LoggerFalso()
    monkeypatch.setattr(orchestrator, "logger", registro)

    def gancho(_paso: object, _r: object) -> None:
        raise RuntimeError("el grabador no responde")

    resultados = Orchestrator([Paso("a"), Paso("b", deps=["a"])], tras_paso=gancho).run_all()

    assert [r.status for r in resultados] == [StepStatus.SUCCESS, StepStatus.SUCCESS]
    avisos = registro.de("tras_paso_fallido")
    assert [a["step"] for a in avisos] == ["a", "b"]
    assert "el grabador no responde" in avisos[0]["error"]


def test_f148_r27_el_gancho_ya_corrio_cuando_la_noche_muere_despues() -> None:
    gancho = Gancho()
    pasos = [
        Paso("build_stg"),
        Paso("build_mart", deps=["build_stg"]),
        Paso("build_cierre", deps=["build_mart"], revienta=MuerteDelProceso()),
    ]

    with pytest.raises(MuerteDelProceso):
        Orchestrator(pasos, tras_paso=gancho).run_all()

    assert [paso for paso, _n, _s in gancho.llamadas] == ["build_stg", "build_mart"]


def test_f148_r28_un_paso_omitido_no_llama_al_gancho() -> None:
    gancho = Gancho()
    pasos = [Paso("build_stg"), Paso("build_mart", deps=["build_stg"])]

    Orchestrator(pasos, tras_paso=gancho, terminados_en_lote=frozenset({"build_stg"})).run_all()

    assert [paso for paso, _n, _s in gancho.llamadas] == ["build_mart"]
