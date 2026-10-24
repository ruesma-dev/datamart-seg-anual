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
from click.testing import CliRunner

import main
from etl_sigrid.application.orchestrator import Orchestrator
from etl_sigrid.domain.entities import StepResult, StepStatus
from tests.test_f024_cli import STEPS_POR_COMANDO, PgFalso, paso_falso, settings_falsos


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


# ---------------------------------------------------------------------------
# Composición en main: `_permisos_tras_paso` y `run-all` (T10)
# ---------------------------------------------------------------------------

DIEZ_BUILD = (
    "build_stg",
    "build_mart",
    "build_maestros",
    "build_tesoreria",
    "build_compras",
    "build_retenciones",
    "build_personal",
    "build_contabilidad",
    "build_descompuestos",
    "build_cierre",
)


class Grabador:
    def __init__(self) -> None:
        self.filas: list[tuple[str, StepResult]] = []

    def record(self, stage: str, resultado: StepResult) -> None:
        self.filas.append((stage, resultado))


def _permisos_falsos(
    estado: StepStatus = StepStatus.SUCCESS, revienta: Exception | None = None
) -> tuple[type, list[tuple]]:
    """Sustituto de `ApplyGrantsStep`: anota con qué se construye y cuándo corre."""
    llamadas: list[tuple] = []

    class _Permisos:
        def __init__(self, settings: object, client: object = None) -> None:
            self._settings = settings
            self._client = client

        @property
        def stage(self) -> str:
            return "grants"

        def run(self) -> StepResult:
            llamadas.append((self._settings, self._client))
            if revienta is not None:
                raise revienta
            return StepResult(
                step_name="apply_grants",
                status=estado,
                started_at=datetime(2026, 10, 23, 1),
                finished_at=datetime(2026, 10, 23, 1, 0, 30),
                rows_processed=42,
                error_message=None if estado is StepStatus.SUCCESS else "veto",
                metadata={"rol": "x"},
            )

    return _Permisos, llamadas


def _tras(monkeypatch: pytest.MonkeyPatch, **kwargs: object):
    clase, llamadas = _permisos_falsos(**kwargs)  # type: ignore[arg-type]
    monkeypatch.setattr(main, "ApplyGrantsStep", clase)
    registro = LoggerFalso()
    monkeypatch.setattr(main, "get_logger", lambda _n: registro)
    grabador = Grabador()
    ajustes, pg = object(), object()
    return (
        main._permisos_tras_paso(ajustes, pg, grabador),
        llamadas,
        grabador,
        registro,
        (ajustes, pg),
    )


# ---------------------------------------------------------------------------
# R25 · tras cada uno de los diez build, los permisos completos
# ---------------------------------------------------------------------------


def test_f148_r25_los_diez_build_son_los_de_la_composicion() -> None:
    pasos = main.build_pipeline_steps(settings_falsos())
    nombres_build = {p.name for p in pasos if p.name.startswith("build_")}

    assert main.PASOS_CON_PERMISOS == DIEZ_BUILD
    assert set(main.PASOS_CON_PERMISOS) == nombres_build


@pytest.mark.parametrize("paso", DIEZ_BUILD)
def test_f148_r25_tras_un_build_se_aplican_y_se_graban(
    monkeypatch: pytest.MonkeyPatch, paso: str
) -> None:
    tras, llamadas, grabador, registro, (ajustes, pg) = _tras(monkeypatch)
    resultado_paso = Paso(paso).run()

    tras(Paso(paso), resultado_paso)

    assert llamadas == [(ajustes, pg)]
    ((etapa, fila),) = grabador.filas
    assert etapa == "grants"
    assert fila.step_name == f"apply_grants.tras_{paso}"
    assert (fila.status, fila.rows_processed, fila.metadata) == (
        StepStatus.SUCCESS,
        42,
        {"rol": "x"},
    )
    assert resultado_paso.step_name == paso, "el resultado del paso no se toca"
    assert registro.de("permisos_tras_paso_fallidos") == []


@pytest.mark.parametrize(
    "paso",
    [
        "ingest_raw",
        "load_excel_aux",
        "publicar_diccionario",
        "ingest_descompuestos",
        "apply_grants",
    ],
)
def test_f148_r25_los_demas_pasos_no_aplican_permisos(
    monkeypatch: pytest.MonkeyPatch, paso: str
) -> None:
    tras, llamadas, grabador, _r, _a = _tras(monkeypatch)

    tras(Paso(paso), Paso(paso).run())

    assert llamadas == []
    assert grabador.filas == []


def test_f148_r25_tambien_tras_un_build_que_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    tras, llamadas, grabador, _r, _a = _tras(monkeypatch)

    tras(Paso("build_cierre"), Paso("build_cierre", StepStatus.FAILED).run())

    assert len(llamadas) == 1
    assert grabador.filas[0][1].step_name == "apply_grants.tras_build_cierre"


# ---------------------------------------------------------------------------
# R26 · si fallan, avisan y la noche sigue
# ---------------------------------------------------------------------------


def test_f148_r26_permisos_en_failed_avisan_y_se_graban(monkeypatch: pytest.MonkeyPatch) -> None:
    tras, _l, grabador, registro, _a = _tras(monkeypatch, estado=StepStatus.FAILED)

    tras(Paso("build_mart"), Paso("build_mart").run())

    (aviso,) = registro.de("permisos_tras_paso_fallidos")
    assert aviso["paso"] == "build_mart"
    assert aviso["error"] == "veto"
    ((_e, fila),) = grabador.filas
    assert (fila.step_name, fila.status) == ("apply_grants.tras_build_mart", StepStatus.FAILED)


def test_f148_r26_permisos_que_lanzan_avisan_y_graban_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tras, _l, grabador, registro, _a = _tras(monkeypatch, revienta=RuntimeError("sin conexión"))

    tras(Paso("build_stg"), Paso("build_stg").run())

    (aviso,) = registro.de("permisos_tras_paso_fallidos")
    assert aviso == {"paso": "build_stg", "error": "sin conexión"}
    ((etapa, fila),) = grabador.filas
    assert etapa == "grants"
    assert (fila.step_name, fila.status, fila.error_message) == (
        "apply_grants.tras_build_stg",
        StepStatus.FAILED,
        "sin conexión",
    )
    assert fila.finished_at is not None


def test_f148_r26_un_fallo_de_permisos_no_cambia_el_resultado_ni_para(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tras, _l, _g, _r, _a = _tras(monkeypatch, revienta=RuntimeError("x"))
    pasos = [Paso("build_stg"), Paso("build_mart", deps=["build_stg"])]

    resultados = Orchestrator(pasos, tras_paso=tras).run_all()

    assert [(r.step_name, r.status) for r in resultados] == [
        ("build_stg", StepStatus.SUCCESS),
        ("build_mart", StepStatus.SUCCESS),
    ]


def test_f148_r27_los_permisos_quedan_aunque_la_noche_muera_despues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tras, llamadas, grabador, _r, _a = _tras(monkeypatch)
    pasos = [
        Paso("build_stg"),
        Paso("build_mart", deps=["build_stg"]),
        Paso("build_cierre", deps=["build_mart"], revienta=MuerteDelProceso()),
    ]

    with pytest.raises(MuerteDelProceso):
        Orchestrator(pasos, tras_paso=tras).run_all()

    assert len(llamadas) == 2
    assert [f.step_name for _e, f in grabador.filas] == [
        "apply_grants.tras_build_stg",
        "apply_grants.tras_build_mart",
    ]


def test_f148_r28_un_paso_omitido_no_aplica_permisos(monkeypatch: pytest.MonkeyPatch) -> None:
    tras, llamadas, grabador, _r, _a = _tras(monkeypatch)
    pasos = [Paso("build_stg"), Paso("build_mart", deps=["build_stg"])]

    Orchestrator(pasos, tras_paso=tras, terminados_en_lote=frozenset({"build_stg"})).run_all()

    assert len(llamadas) == 1
    assert [f.step_name for _e, f in grabador.filas] == ["apply_grants.tras_build_mart"]


def test_f148_r28_un_paso_saltado_por_dependencia_tampoco(monkeypatch: pytest.MonkeyPatch) -> None:
    tras, llamadas, _g, _r, _a = _tras(monkeypatch)
    pasos = [Paso("ingest_raw", StepStatus.FAILED), Paso("build_stg", deps=["ingest_raw"])]

    resultados = Orchestrator(pasos, tras_paso=tras).run_all()

    assert resultados[1].status is StepStatus.SKIPPED
    assert llamadas == []


def test_f148_r25_tambien_si_el_build_lanza(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un build que revienta deja su esquema a medias: es cuando más falta hacen."""
    tras, llamadas, _g, _r, _a = _tras(monkeypatch)

    Orchestrator([Paso("build_compras", revienta=RuntimeError("x"))], tras_paso=tras).run_all()

    assert len(llamadas) == 1


# ---------------------------------------------------------------------------
# run-all compone el gancho
# ---------------------------------------------------------------------------


def test_f148_r25_run_all_graba_una_fila_por_build(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgFalso()
    construcciones: list[dict] = []
    monkeypatch.setattr(main, "get_settings", lambda: settings_falsos())
    monkeypatch.setattr(main, "configure_logging", lambda **_k: None)
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.delenv("CONTAINER_APP_JOB_EXECUTION_NAME", raising=False)
    for atributo, nombre, etapa in STEPS_POR_COMANDO.values():
        monkeypatch.setattr(
            main, atributo, paso_falso(nombre, etapa, construcciones=construcciones)
        )

    resultado = CliRunner().invoke(main.cli, ["run-all"])

    assert resultado.exit_code == 0, resultado.output
    tras = [p for p, _e, _b in pg.pasos_registrados if p.startswith("apply_grants.tras_")]
    assert tras == [
        f"apply_grants.tras_{p}"
        for p in (
            "build_stg",
            "build_mart",
            "build_maestros",
            "build_tesoreria",
            "build_compras",
            "build_retenciones",
            "build_personal",
            "build_contabilidad",
            "build_descompuestos",
            "build_cierre",
        )
    ]
    # el apply_grants que construye el gancho reutiliza el cliente de run-all
    assert sum(1 for c in construcciones if c.get("client") is pg) == len(DIEZ_BUILD)
    batch = pg.batches_de_la_marca[0]
    assert {b for _p, _e, b in pg.pasos_registrados} == {batch}
