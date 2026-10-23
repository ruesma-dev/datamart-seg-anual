# tests/test_f148_reanudacion.py
"""
F-148 · Reanudar en vez de repetir (R18-R24).

El reintento del job (`replicaRetryLimit` 1) volvía a empezar por la ingesta
entera: el 22-10 la noche terminó a las 04:31. Ahora las dos réplicas de una
misma ejecución del job comparten `batch_id` —el sufijo sale del nombre de la
ejecución— y la segunda omite lo que la primera ya dejó en SUCCESS: pasos cuyas
dependencias también se omiten y tablas de `raw` ya cargadas.

Sin red ni BBDD: `_meta.etl_runs` se dobla, el entorno se fija con
`monkeypatch` y la CLI se invoca con los dobles de F-024.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import main
from etl_sigrid.application.orchestrator import Orchestrator
from etl_sigrid.application.steps import ingest_raw_step
from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
from etl_sigrid.domain.coherencia import EstadoTablaRaw, evaluar_coherencia_raw
from etl_sigrid.domain.ejecucion import Ejecucion, ejecucion_desde_batch, nueva_ejecucion
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.domain.reanudacion import (
    PASOS_NUNCA_OMITIBLES,
    VENTANA_REANUDACION,
    pasos_a_omitir,
    sufijo_de_ejecucion_job,
    tablas_a_omitir,
)
from etl_sigrid.infrastructure.postgres.postgres_client import (
    SQL_LOTE_REANUDABLE,
    SQL_TERMINADOS_EN_LOTE,
    PostgresClient,
)
from tests.test_f024_cli import STEPS_POR_COMANDO, PgFalso, paso_falso, settings_falsos

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE_JOB = "caj-etl-sigrid-dev-r7k2p9q"
SUFIJO = hashlib.sha256(NOMBRE_JOB.encode("utf-8")).hexdigest()[:6]
VARIABLE = "CONTAINER_APP_JOB_EXECUTION_NAME"


class LoggerFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    warning = info
    error = info
    debug = info

    def exception(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    def de(self, evento: str) -> list[dict]:
        return [c for e, c in self.eventos if e == evento]


# ===========================================================================
# Dominio (T6)
# ===========================================================================


def test_f148_dominio_sufijo_es_el_sha256_del_nombre() -> None:
    assert sufijo_de_ejecucion_job(NOMBRE_JOB) == SUFIJO
    assert len(SUFIJO) == 6
    assert sufijo_de_ejecucion_job(NOMBRE_JOB + "x") != SUFIJO


def test_f148_dominio_el_sufijo_cabe_donde_el_aleatorio() -> None:
    """Mismo ancho que el sufijo aleatorio de F-024: el batch sigue ordenando."""
    assert len(sufijo_de_ejecucion_job("a")) == len(nueva_ejecucion().batch_id.split("-")[1])


def test_f148_dominio_ventana_de_ocho_horas_y_mayor_que_el_techo_del_job() -> None:
    """Una réplica no puede vivir más que `replicaTimeout`: la ventana lo cubre."""
    techo = json.loads((RAIZ / "infra" / "env" / "dev.json").read_text(encoding="utf-8"))[
        "replicaTimeoutSeconds"
    ]
    assert timedelta(hours=8) == VENTANA_REANUDACION
    assert timedelta(seconds=techo) < VENTANA_REANUDACION


def test_f148_dominio_apply_grants_nunca_se_omite() -> None:
    assert frozenset({"apply_grants"}) == PASOS_NUNCA_OMITIBLES


ORDEN = [
    ("ingest_raw", []),
    ("load_excel_aux", []),
    ("build_stg", ["ingest_raw", "load_excel_aux"]),
    ("build_mart", ["build_stg"]),
    ("build_cierre", ["build_mart"]),
    ("apply_grants", ["build_mart"]),
]


def test_f148_r21_omite_lo_terminado_con_dependencias_omitidas() -> None:
    terminados = {"ingest_raw", "load_excel_aux", "build_stg", "build_mart"}

    assert pasos_a_omitir(ORDEN, terminados) == frozenset(terminados)


def test_f148_r21_no_omite_si_una_dependencia_se_repite() -> None:
    """`build_stg` terminó, pero la ingesta no: hay que reconstruir encima."""
    terminados = {"load_excel_aux", "build_stg", "build_mart"}

    assert pasos_a_omitir(ORDEN, terminados) == frozenset({"load_excel_aux"})


def test_f148_r21_apply_grants_no_se_omite_aunque_termino() -> None:
    terminados = {name for name, _d in ORDEN}

    omitidos = pasos_a_omitir(ORDEN, terminados)

    assert "apply_grants" not in omitidos
    assert omitidos == frozenset(terminados - {"apply_grants"})


def test_f148_r21_lo_que_depende_de_apply_grants_tampoco() -> None:
    orden = [("apply_grants", []), ("despues", ["apply_grants"])]

    assert pasos_a_omitir(orden, {"apply_grants", "despues"}) == frozenset()


def test_f148_r21_solo_cuentan_las_filas_de_paso_sin_punto() -> None:
    """`ingest_raw.con` es un tramo: no acredita que `ingest_raw` terminara."""
    assert pasos_a_omitir(ORDEN, {"ingest_raw.con", "ingest_raw.firma_origen"}) == frozenset()


def test_f148_r21_sin_terminados_no_se_omite_nada() -> None:
    assert pasos_a_omitir(ORDEN, set()) == frozenset()


def test_f148_r23_tablas_a_omitir_son_las_declaradas_en_success() -> None:
    terminados = {
        "ingest_raw.con",
        "ingest_raw.apu",
        "ingest_raw.firma_origen",
        "ingest_raw",
        "build_stg",
        "ingest_raw.no_declarada",
    }

    assert tablas_a_omitir(["con", "obrparpre", "apu"], terminados) == frozenset({"con", "apu"})


def test_f148_dominio_ejecucion_desde_batch() -> None:
    ejecucion = ejecucion_desde_batch("20261023T000312Z-a1b2c3")

    assert ejecucion == Ejecucion(
        batch_id="20261023T000312Z-a1b2c3",
        iniciada_en=datetime(2026, 10, 23, 0, 3, 12),
        reanudada=True,
    )


@pytest.mark.parametrize(
    "basura",
    ["basura-a1b2c3", "2026-10-23-a1b2c3", "", "20261023T000312Z", "20261023T000312Z-"],
)
def test_f148_dominio_ejecucion_desde_batch_rechaza_lo_que_no_casa(basura: str) -> None:
    with pytest.raises(ValueError):
        ejecucion_desde_batch(basura)


# ===========================================================================
# SQL (T7)
# ===========================================================================


def test_f148_sql_lote_reanudable_es_el_del_diseno() -> None:
    texto = " ".join(SQL_LOTE_REANUDABLE.split())
    assert texto == (
        "SELECT batch_id FROM _meta.etl_runs WHERE right(batch_id, 7) = %(cola)s "
        "AND started_at >= %(desde)s ORDER BY batch_id DESC LIMIT 1"
    )
    assert "LIKE" not in SQL_LOTE_REANUDABLE.upper()


def test_f148_sql_terminados_en_lote_es_el_del_diseno() -> None:
    texto = " ".join(SQL_TERMINADOS_EN_LOTE.split())
    assert texto == (
        "SELECT DISTINCT step FROM _meta.etl_runs WHERE batch_id = %(batch)s AND status = 'SUCCESS'"
    )


class Cursor:
    def __init__(self, filas: list[tuple]) -> None:
        self._filas = filas
        self.enviado: list[tuple[str, object]] = []

    def __enter__(self) -> Cursor:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sentencia: str, parametros: object = None) -> None:
        self.enviado.append((sentencia, parametros))

    def fetchone(self) -> tuple | None:
        return self._filas[0] if self._filas else None

    def fetchall(self) -> list[tuple]:
        return list(self._filas)


class Conexion:
    def __init__(self, cursor: Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> Conexion:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def cursor(self) -> Cursor:
        return self._cursor


def _cliente(filas: list[tuple]) -> tuple[PostgresClient, Cursor]:
    cursor = Cursor(filas)
    cliente = PostgresClient("dbname=x", "dbname=admin", "sigrid_dm")
    cliente.connection = lambda: Conexion(cursor)  # type: ignore[method-assign]
    return cliente, cursor


def test_f148_sql_buscar_lote_reanudable_envia_la_cola_y_el_desde() -> None:
    cliente, cursor = _cliente([("20261023T000312Z-" + SUFIJO,)])
    desde = datetime(2026, 10, 22, 16, 0, 0)

    lote = cliente.buscar_lote_reanudable(SUFIJO, desde)

    assert lote == "20261023T000312Z-" + SUFIJO
    assert cursor.enviado == [(SQL_LOTE_REANUDABLE, {"cola": "-" + SUFIJO, "desde": desde})]


def test_f148_sql_buscar_lote_reanudable_sin_lote_es_none() -> None:
    cliente, _cursor = _cliente([])

    assert cliente.buscar_lote_reanudable(SUFIJO, datetime(2026, 1, 1)) is None


def test_f148_sql_fetch_terminados_en_lote() -> None:
    cliente, cursor = _cliente([("ingest_raw.con",), ("build_stg",)])

    terminados = cliente.fetch_terminados_en_lote("b1")

    assert terminados == frozenset({"ingest_raw.con", "build_stg"})
    assert cursor.enviado == [(SQL_TERMINADOS_EN_LOTE, {"batch": "b1"})]


# ===========================================================================
# Orquestador (T8)
# ===========================================================================


class Paso:
    def __init__(
        self,
        nombre: str,
        deps: list[str] | None = None,
        estado: StepStatus = StepStatus.SUCCESS,
        revienta: BaseException | None = None,
        ejecutados: list[str] | None = None,
    ) -> None:
        self._nombre = nombre
        self._deps = deps or []
        self._estado = estado
        self._revienta = revienta
        self.ejecutados = ejecutados if ejecutados is not None else []

    @property
    def name(self) -> str:
        return self._nombre

    @property
    def stage(self) -> str:
        return "etapa_" + self._nombre

    @property
    def depends_on(self) -> list[str]:
        return self._deps

    def run(self) -> StepResult:
        self.ejecutados.append(self._nombre)
        if self._revienta is not None:
            raise self._revienta
        return StepResult(
            step_name=self._nombre,
            status=self._estado,
            started_at=datetime(2026, 10, 23),
            finished_at=datetime(2026, 10, 23),
        )


class Grabador:
    def __init__(self) -> None:
        self.filas: list[tuple[str, str, str]] = []

    def record(self, stage: str, resultado: StepResult) -> None:
        self.filas.append((stage, resultado.step_name, resultado.status.value))


def _cadena(ejecutados: list[str]) -> list[Paso]:
    return [
        Paso("a", ejecutados=ejecutados),
        Paso("b", ["a"], ejecutados=ejecutados),
        Paso("c", ["b"], ejecutados=ejecutados),
    ]


def test_f148_r21_r22_el_orquestador_omite_sin_ejecutar_ni_grabar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etl_sigrid.application import orchestrator

    registro = LoggerFalso()
    monkeypatch.setattr(orchestrator, "logger", registro)
    ejecutados: list[str] = []
    grabador = Grabador()

    resultados = Orchestrator(
        _cadena(ejecutados), recorder=grabador, terminados_en_lote=frozenset({"a", "b"})
    ).run_all()

    assert ejecutados == ["c"]
    assert grabador.filas == [("etapa_c", "c", "SUCCESS")]
    assert [(r.step_name, r.status) for r in resultados] == [
        ("a", StepStatus.SUCCESS),
        ("b", StepStatus.SUCCESS),
        ("c", StepStatus.SUCCESS),
    ]
    assert resultados[0].metadata == {"reanudado": True}
    assert resultados[0].finished_at is not None
    assert resultados[2].metadata == {}
    assert [c["step"] for c in registro.de("paso_reanudado")] == ["a", "b"]


def test_f148_r21_el_orquestador_no_omite_si_la_dependencia_se_repite() -> None:
    ejecutados: list[str] = []

    Orchestrator(_cadena(ejecutados), terminados_en_lote=frozenset({"b", "c"})).run_all()

    assert ejecutados == ["a", "b", "c"]


def test_f148_r21_apply_grants_se_ejecuta_aunque_termino() -> None:
    ejecutados: list[str] = []
    pasos = [
        Paso("build_mart", ejecutados=ejecutados),
        Paso("apply_grants", ["build_mart"], ejecutados=ejecutados),
    ]

    Orchestrator(pasos, terminados_en_lote=frozenset({"build_mart", "apply_grants"})).run_all()

    assert ejecutados == ["apply_grants"]


def test_f148_r22_sin_terminados_todo_como_hoy() -> None:
    ejecutados: list[str] = []
    grabador = Grabador()

    Orchestrator(_cadena(ejecutados), recorder=grabador).run_all()

    assert ejecutados == ["a", "b", "c"]
    assert len(grabador.filas) == 3


# ===========================================================================
# IngestRawStep reanudado (T9, R23-R24)
# ===========================================================================


class PgIngesta:
    def __init__(self) -> None:
        self.conexiones_abiertas = 0
        self.truncadas: list[str] = []

    def record_run_start(self, *a: object, **k: object) -> int:
        return 1

    def record_run_end(self, *a: object, **k: object) -> None:
        return None

    def fetch_firma_origen(self) -> dict:
        return {}

    def registrar_firmas_actuales(self, firmas: dict) -> int:
        return 0


class Api:
    def __init__(self, *_a: object, **_k: object) -> None:
        pass

    def __enter__(self) -> Api:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def _settings_ingesta(tablas: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(
        sigrid_api=SimpleNamespace(
            page_size=10,
            base_url="http://x",
            database="ruesma",
            timeout_s=1.0,
            max_retries=1,
            function_key=SimpleNamespace(get_secret_value=lambda: "k"),
        ),
        tables_sigrid={"tables": [{"source_table": t, "target_table": t} for t in tablas]},
    )


def test_f148_r23_la_ingesta_omite_las_tablas_terminadas(monkeypatch: pytest.MonkeyPatch) -> None:
    registro = LoggerFalso()
    monkeypatch.setattr(ingest_raw_step, "logger", registro)
    monkeypatch.setattr(ingest_raw_step, "build_postgres_client", lambda _s: PgIngesta())
    monkeypatch.setattr(ingest_raw_step, "SigridApiClient", Api)
    cargadas: list[str] = []
    monkeypatch.setattr(
        IngestRawStep,
        "_ingest_one_table",
        lambda self, spec, api, pg: cargadas.append(spec.source_table) or 4,
    )
    paso = IngestRawStep(
        _settings_ingesta(("con", "obrparpre", "apu")),  # type: ignore[arg-type]
        batch_id="b",
        tablas_terminadas=frozenset({"con", "apu"}),
    )

    resultado = paso.run()

    assert cargadas == ["obrparpre"]
    assert resultado.status is StepStatus.SUCCESS
    assert resultado.rows_processed == 4
    assert resultado.metadata["tablas_reanudadas"] == ["apu", "con"]
    assert [c["table"] for c in registro.de("ingest_raw_tabla_reanudada")] == ["con", "apu"]


def test_f148_r23_sin_reanudar_carga_todas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest_raw_step, "build_postgres_client", lambda _s: PgIngesta())
    monkeypatch.setattr(ingest_raw_step, "SigridApiClient", Api)
    cargadas: list[str] = []
    monkeypatch.setattr(
        IngestRawStep,
        "_ingest_one_table",
        lambda self, spec, api, pg: cargadas.append(spec.source_table) or 1,
    )

    resultado = IngestRawStep(_settings_ingesta(("con", "apu")), batch_id="b").run()  # type: ignore[arg-type]

    assert cargadas == ["con", "apu"]
    assert resultado.metadata["tablas_reanudadas"] == []


def _v_raw_state(filas: list[tuple[int, str, str, str, datetime]]) -> list[EstadoTablaRaw]:
    """Lo que hace `_meta.v_raw_state`: la última fila de cada tabla, por
    `started_at DESC, id DESC`. Filas: (id, tabla, status, batch, started_at)."""
    ultima: dict[str, tuple] = {}
    for fila in sorted(filas, key=lambda f: (f[4], f[0])):
        ultima[fila[1]] = fila
    return [
        EstadoTablaRaw(tabla=t, status=s, batch_id=b, started_at=ini, finished_at=ini, filas=1)
        for (_i, t, s, b, ini) in ultima.values()
    ]


def test_f148_r24_la_puerta_de_stg_acepta_una_ingesta_reanudada() -> None:
    """Primer intento: `con` en SUCCESS y `obrparpre` FAILED. El reintento adopta
    el lote, omite `con` y recarga `obrparpre`: un solo lote, puerta OK."""
    lote = "20261023T000312Z-" + SUFIJO
    t0 = datetime(2026, 10, 23, 0, 3)
    filas = [
        (1, "con", "SUCCESS", lote, t0),
        (2, "obrparpre", "FAILED", lote, t0 + timedelta(minutes=1)),
        # el reintento: `con` omitida (sin fila), `obrparpre` otra vez
        (3, "obrparpre", "SUCCESS", lote, t0 + timedelta(hours=1)),
    ]

    veredicto = evaluar_coherencia_raw(_v_raw_state(filas), ["con", "obrparpre"])

    assert veredicto.ok is True
    assert veredicto.batch_id == lote


def test_f148_r24_control_sin_adoptar_el_lote_la_puerta_rechaza() -> None:
    """Por qué hace falta adoptar: omitir tablas con un lote NUEVO mezclaría dos."""
    t0 = datetime(2026, 10, 23, 0, 3)
    filas = [
        (1, "con", "SUCCESS", "20261023T000312Z-aaaaaa", t0),
        (3, "obrparpre", "SUCCESS", "20261023T010000Z-bbbbbb", t0 + timedelta(hours=1)),
    ]

    assert evaluar_coherencia_raw(_v_raw_state(filas), ["con", "obrparpre"]).ok is False


# ===========================================================================
# main: identidad del lote y composición (T10, R18-R20)
# ===========================================================================


class PgReanuda(PgFalso):
    def __init__(
        self,
        lote: str | None = None,
        terminados: frozenset[str] = frozenset(),
        error_buscar: Exception | None = None,
        error_terminados: Exception | None = None,
    ) -> None:
        super().__init__()
        self._lote = lote
        self._terminados = terminados
        self._error_buscar = error_buscar
        self._error_terminados = error_terminados
        self.busquedas: list[tuple[str, datetime]] = []
        self.lotes_leidos: list[str] = []

    def buscar_lote_reanudable(self, sufijo: str, desde: datetime) -> str | None:
        self.busquedas.append((sufijo, desde))
        if self._error_buscar is not None:
            raise self._error_buscar
        return self._lote

    def fetch_terminados_en_lote(self, batch_id: str) -> frozenset[str]:
        self.lotes_leidos.append(batch_id)
        if self._error_terminados is not None:
            raise self._error_terminados
        return self._terminados


def _preparar(
    monkeypatch: pytest.MonkeyPatch,
    pg: PgFalso,
    construcciones: list[dict],
    nombre: str | None = NOMBRE_JOB,
) -> LoggerFalso:
    from click.testing import CliRunner  # noqa: F401  (lo usa quien llama)

    registro = LoggerFalso()
    monkeypatch.setattr(main, "get_settings", lambda: settings_falsos())
    monkeypatch.setattr(main, "configure_logging", lambda **_k: None)
    monkeypatch.setattr(main, "_get_pg", lambda: pg)
    monkeypatch.setattr(main, "get_logger", lambda _n: registro)
    for atributo, paso, etapa in STEPS_POR_COMANDO.values():
        monkeypatch.setattr(main, atributo, paso_falso(paso, etapa, construcciones=construcciones))
    if nombre is None:
        monkeypatch.delenv(VARIABLE, raising=False)
    else:
        monkeypatch.setenv(VARIABLE, nombre)
    return registro


def _invocar(*argumentos: str):
    from click.testing import CliRunner

    return CliRunner().invoke(main.cli, list(argumentos))


def _batch_de(construcciones: list[dict]) -> str:
    (batch,) = {c["batch_id"] for c in construcciones if "batch_id" in c}
    return batch


def test_f148_r18_sin_lote_previo_el_batch_lleva_el_sufijo_del_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgReanuda()
    construcciones: list[dict] = []
    _preparar(monkeypatch, pg, construcciones)
    antes = datetime.utcnow()

    resultado = _invocar("run-all")
    despues = datetime.utcnow()

    assert resultado.exit_code == 0, resultado.output
    batch = _batch_de(construcciones)
    assert batch.endswith("-" + SUFIJO)
    assert batch[:16] >= antes.strftime("%Y%m%dT%H%M%SZ")
    ((sufijo, desde),) = pg.busquedas
    assert sufijo == SUFIJO
    assert antes - timedelta(hours=8) <= desde <= despues - timedelta(hours=8)
    assert pg.batches_de_la_marca == [batch]


def test_f148_r18_con_lote_previo_lo_adopta_y_lee_lo_terminado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lote = "20261023T000312Z-" + SUFIJO
    pg = PgReanuda(lote=lote, terminados=frozenset({"load_excel_aux", "ingest_raw.con"}))
    construcciones: list[dict] = []
    registro = _preparar(monkeypatch, pg, construcciones)

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    assert _batch_de(construcciones) == lote
    assert pg.batches_de_la_marca == [lote]
    assert pg.lotes_leidos == [lote]
    (aviso,) = registro.de("ejecucion_reanudada")
    assert aviso["batch_id"] == lote
    # la ingesta recibe las tablas ya cargadas; el orquestador omite el paso
    (ingesta,) = [c for c in construcciones if "tablas_terminadas" in c]
    assert ingesta["tablas_terminadas"] == frozenset({"con"})
    pasos = [p for p, _e, _b in pg.pasos_registrados]
    assert "load_excel_aux" not in pasos
    assert "ingest_raw" in pasos
    assert {b for _p, _e, b in pg.pasos_registrados} == {lote}


def test_f148_r18_el_arranque_dice_la_ejecucion_del_job(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgReanuda()
    registro = _preparar(monkeypatch, pg, [])

    _invocar("run-all")

    (aviso,) = registro.de("ejecucion_job")
    assert aviso == {"ejecucion_job": NOMBRE_JOB, "sufijo": SUFIJO}


def test_f148_r19_sin_la_variable_todo_como_hoy(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgReanuda(lote="20261023T000312Z-" + SUFIJO)
    construcciones: list[dict] = []
    _preparar(monkeypatch, pg, construcciones, nombre=None)

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    assert pg.busquedas == []
    assert pg.lotes_leidos == []
    assert not _batch_de(construcciones).endswith("-" + SUFIJO)
    (ingesta,) = [c for c in construcciones if "tablas_terminadas" in c]
    assert ingesta["tablas_terminadas"] == frozenset()


def test_f148_r19_variable_vacia_es_como_sin_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgReanuda()
    _preparar(monkeypatch, pg, [], nombre="")

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    assert pg.busquedas == []


@pytest.mark.parametrize("comando", ["ingest", "stage", "build-mart", "apply-grants"])
def test_f148_r19_los_comandos_sueltos_nunca_reanudan(
    monkeypatch: pytest.MonkeyPatch, comando: str
) -> None:
    pg = PgReanuda(lote="20261023T000312Z-" + SUFIJO)
    _preparar(monkeypatch, pg, [])

    resultado = _invocar(comando)

    assert resultado.exit_code == 0, resultado.output
    assert pg.busquedas == []
    assert not pg.batches_de_la_marca[0].endswith("-" + SUFIJO)


def test_f148_r19_sin_lote_previo_no_se_omite_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgReanuda(lote=None, terminados=frozenset({"load_excel_aux"}))
    construcciones: list[dict] = []
    _preparar(monkeypatch, pg, construcciones)

    _invocar("run-all")

    assert "load_excel_aux" in [p for p, _e, _b in pg.pasos_registrados]


def test_f148_r20_si_la_busqueda_falla_avisa_y_arranca_lote_nuevo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pg = PgReanuda(error_buscar=RuntimeError("_meta no responde"))
    construcciones: list[dict] = []
    registro = _preparar(monkeypatch, pg, construcciones)

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    (aviso,) = registro.de("reanudacion_no_disponible")
    assert "_meta no responde" in aviso["error"]
    assert _batch_de(construcciones).endswith("-" + SUFIJO)
    assert pg.lotes_leidos == []


def test_f148_r20_un_lote_con_formato_raro_no_se_adopta(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgReanuda(lote="basura-" + SUFIJO)
    construcciones: list[dict] = []
    registro = _preparar(monkeypatch, pg, construcciones)

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    assert registro.de("reanudacion_no_disponible")
    assert _batch_de(construcciones) != "basura-" + SUFIJO


def test_f148_r20_si_falla_leer_lo_terminado_no_se_omite_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lote = "20261023T000312Z-" + SUFIJO
    pg = PgReanuda(lote=lote, error_terminados=RuntimeError("se cae"))
    construcciones: list[dict] = []
    registro = _preparar(monkeypatch, pg, construcciones)

    resultado = _invocar("run-all")

    assert resultado.exit_code == 0, resultado.output
    (aviso,) = registro.de("reanudacion_no_disponible")
    assert "se cae" in aviso["error"]
    assert _batch_de(construcciones) == lote
    assert "load_excel_aux" in [p for p, _e, _b in pg.pasos_registrados]


def test_f148_dominio_una_ejecucion_nueva_no_es_reanudada() -> None:
    assert nueva_ejecucion().reanudada is False
