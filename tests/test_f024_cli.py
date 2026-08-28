# tests/test_f024_cli.py
"""
F-024 · Tests de la CLI: marca de huérfanas (R4, R5, R7), registro de los
comandos sueltos (R18), la opción `--sin-puerta` (R11) y los dos comandos
nuevos de diagnóstico, `check-coherencia` (R14) y `check-frescura` (R19).

La afirmación central de este fichero es una lista: EXACTAMENTE qué comandos
escriben y cuáles no. Es lo que decide quién puede tocar `_meta` y quién no, y
es lo que se olvida al añadir un comando nuevo dentro de seis meses. Por eso
los tests van parametrizados sobre las dos listas y no comando a comando.

Ninguno abre red ni BBDD: se sustituyen `main.get_settings`, `main._get_pg` y
las clases de step por dobles.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.coherencia import EstadoPaso, EstadoTablaRaw
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.postgres.frescura import (
    UMBRAL_FRESCURA_HORAS,
    FilaFrescura,
)

BATCH_ANTERIOR = "20260818T020000Z-bbbbbb"

# Los pasos que cada comando construye, y con qué doble hay que sustituirlos.
# La clave es el nombre del atributo en `main`.
STEPS_POR_COMANDO = {
    "ingest": ("IngestRawStep", "ingest_raw", "ingest"),
    "load-aux": ("LoadExcelAuxStep", "load_excel_aux", "load_aux"),
    "stage": ("BuildStgStep", "build_stg", "stage"),
    "build-mart": ("BuildMartStep", "build_mart", "build_mart"),
    "build-cierre": ("BuildCierreStep", "build_cierre", "build_cierre"),
    "build-maestros": ("BuildMaestrosStep", "build_maestros", "build_maestros"),
    # F-047: los dos que faltaban. `build-compras` y `build-retenciones`
    # ejecutaban su SQL EN LÍNEA, sin step, así que marcaban huérfanas pero no
    # registraban paso y quedaban fuera de `v_frescura` (era el DA-6 de F-024).
    # Al entrar los cuatro esquemas en la carga nocturna eso dejó de ser
    # tolerable: sin fila en `_meta.etl_runs` no hay fecha de build que citar.
    "build-compras": ("BuildComprasStep", "build_compras", "build_compras"),
    "build-retenciones": (
        "BuildRetencionesStep", "build_retenciones", "build_retenciones",
    ),
    "apply-grants": ("ApplyGrantsStep", "apply_grants", "apply_grants"),
}

#: Comandos que ESCRIBEN y por tanto tienen que marcar las huérfanas (R4).
COMANDOS_QUE_ESCRIBEN = (*STEPS_POR_COMANDO, "run-all")

#: Comandos de SOLO LECTURA: no pueden escribir ni una fila en `_meta` (R5).
#: `bootstrap` está aquí porque solo ejecuta DDL idempotente: se lanza «para
#: ver si conecta» y no debe dejar rastro de ejecución (§9.7 del diseño).
COMANDOS_DE_LECTURA = (
    "timings",
    "status",
    "check-pg",
    "check-coherencia",
    "check-frescura",
    "bootstrap",
)


# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class CursorFalso:
    def __enter__(self) -> CursorFalso:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> None:
        return None

    def fetchone(self) -> tuple:
        return (0,)

    def fetchall(self) -> list[tuple]:
        return []


class ConexionFalsa:
    def __enter__(self) -> ConexionFalsa:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def cursor(self) -> CursorFalso:
        return CursorFalso()

    def commit(self) -> None:
        return None


class PgFalso:
    """Doble del cliente para la CLI. Anota si le piden marcar huérfanas.

    F-006 añadió `publicar_diccionario` al pipeline de `run-all`, así que este
    doble tiene que saber responder a lo que ese paso le pide. Se quedan como
    no-op deliberados: lo que aquí se prueba es la propagación del `batch_id`,
    no la publicación, que tiene su propio fichero de tests.
    """

    def execute_sql_file(self, path, **_kwargs) -> None:
        return None

    def publicar_diccionario(self, *_args, **_kwargs) -> int:
        return 0

    def __init__(
        self,
        huerfanas: list[tuple[int, str, datetime]] | None = None,
        estados: list[EstadoTablaRaw] | None = None,
        ultimo_stg: EstadoPaso | None = None,
        frescura: list[FilaFrescura] | None = None,
        error_al_abortar: Exception | None = None,
        error_al_leer: Exception | None = None,
        catalogo: list[tuple[str, str, str]] | None = None,
    ) -> None:
        self._catalogo = catalogo
        self._huerfanas = huerfanas or []
        self._estados = estados if estados is not None else []
        self._ultimo_stg = ultimo_stg
        self._frescura = frescura if frescura is not None else []
        self._error_al_abortar = error_al_abortar
        self._error_al_leer = error_al_leer

        self.batches_de_la_marca: list[str] = []
        self.pasos_registrados: list[tuple[str, str, str | None]] = []

    # --- lo que solo pueden pedir los comandos que escriben ---
    def abortar_runs_huerfanos(
        self, batch_id: str, ahora: datetime | None = None
    ) -> list[tuple[int, str, datetime]]:
        self.batches_de_la_marca.append(batch_id)
        if self._error_al_abortar is not None:
            raise self._error_al_abortar
        return list(self._huerfanas)

    def record_run_completed(self, **kwargs: object) -> int:
        self.pasos_registrados.append(
            (str(kwargs["step"]), str(kwargs["status"]), kwargs["batch_id"])  # type: ignore[arg-type]
        )
        return 1

    def record_run_start(self, stage: str, step: str, batch_id: str | None = None) -> int:
        return 1

    def record_run_end(self, *args: object, **kwargs: object) -> None:
        return None

    # --- lecturas ---
    def list_objetos_catalogo(self, schemas: object) -> list[tuple[str, str, str]]:
        """Lo que el guardián de F-047 pide al terminar `run-all`.

        Devuelve por defecto EXACTAMENTE lo que el repositorio declara, que es
        la única respuesta que deja `run-all` en verde. No es complacencia con
        el test: un `run-all` que termina sin haber construido lo que el
        repositorio declara TIENE que salir con código 1, y eso lo comprueban
        los tests de `tests/test_f047_nocturna.py` quitando objetos de aquí.
        """
        from etl_sigrid.infrastructure.inventario_repositorio import (
            inventario_del_repositorio,
        )

        if self._catalogo is not None:
            return list(self._catalogo)
        return [(o.esquema, o.objeto, o.tipo) for o in inventario_del_repositorio()]

    def fetch_estado_raw(self) -> list[EstadoTablaRaw]:
        if self._error_al_leer is not None:
            raise self._error_al_leer
        return list(self._estados)

    def fetch_ultimo_intento_stg(self) -> EstadoPaso | None:
        if self._error_al_leer is not None:
            raise self._error_al_leer
        return self._ultimo_stg

    def fetch_frescura(self) -> list[FilaFrescura]:
        if self._error_al_leer is not None:
            raise self._error_al_leer
        return list(self._frescura)

    def fetch_timings(self, last: int = 1) -> list:
        return []

    # --- lo que usan los comandos de lectura y los de SQL en línea ---
    def check_connectivity(self) -> str:
        return "PostgreSQL de mentira"

    def force_bootstrap(self) -> None:
        return None

    def table_exists(self, schema: str, table: str) -> bool:
        return False

    def count_rows(self, schema: str, table: str) -> int:
        return 0

    def get_max_id(self, schema: str, table: str, id_column: str = "ide") -> int:
        return 0

    def connection(self) -> ConexionFalsa:
        return ConexionFalsa()


def paso_falso(
    nombre: str,
    stage: str,
    estado: StepStatus = StepStatus.SUCCESS,
    construcciones: list[dict] | None = None,
) -> type:
    """Clase que sustituye a un step: registra cómo la construyeron."""

    class _PasoFalso:
        def __init__(self, settings: object, *args: object, **kwargs: object) -> None:
            if construcciones is not None:
                construcciones.append(dict(kwargs))

        @property
        def name(self) -> str:
            return nombre

        @property
        def stage(self) -> str:
            return stage

        @property
        def depends_on(self) -> list[str]:
            return []

        def run(self) -> StepResult:
            return StepResult(
                step_name=nombre,
                status=estado,
                started_at=datetime(2026, 8, 19, 2, 0, 0),
                finished_at=datetime(2026, 8, 19, 2, 30, 0),
                rows_processed=7,
            )

    return _PasoFalso


def settings_falsos(tablas: tuple[str, ...] = ("con",)) -> SimpleNamespace:
    return SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console"),
        tables_sigrid={
            "tables": [{"source_table": t, "target_table": t} for t in tablas]
        },
    )


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    """Deja la CLI lista para invocarse sin red, sin BBDD y sin .env."""

    def _preparar(
        pg: PgFalso,
        estado: StepStatus = StepStatus.SUCCESS,
        construcciones: list[dict] | None = None,
        tablas: tuple[str, ...] = ("con",),
    ) -> CliRunner:
        monkeypatch.setattr(main, "get_settings", lambda: settings_falsos(tablas))
        monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
        monkeypatch.setattr(main, "_get_pg", lambda: pg)

        for atributo, nombre, stage in STEPS_POR_COMANDO.values():
            monkeypatch.setattr(
                main,
                atributo,
                paso_falso(nombre, stage, estado, construcciones),
            )
        return CliRunner()

    return _preparar


# ---------------------------------------------------------------------------
# R4 · Todo comando que escribe marca las huérfanas ANTES de actuar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", COMANDOS_QUE_ESCRIBEN)
def test_f024_r4_cada_comando_que_escribe_marca_huerfanas_antes_de_actuar(
    cli, comando: str
) -> None:
    """Uno por comando de la lista de convenciones. Sin excepciones.

    La lista es el requisito: añadir un comando que escriba sin meterlo aquí
    es exactamente el hueco por el que se cuela otra fila huérfana eterna.
    """
    pg = PgFalso()
    resultado = cli(pg).invoke(main.cli, [comando])

    assert resultado.exit_code == 0, resultado.output
    assert len(pg.batches_de_la_marca) == 1, (
        f"'{comando}' no marcó las huérfanas (o las marcó más de una vez)"
    )
    # Y con un batch de verdad, no con una cadena vacía.
    assert pg.batches_de_la_marca[0].endswith(
        pg.batches_de_la_marca[0].split("-")[-1]
    )
    assert len(pg.batches_de_la_marca[0]) == len("20260819T020000Z-abc123")


def test_f024_r4_warning_por_fila_marcada(cli, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un WARNING estructurado POR FILA, con id, step y arranque.

    Sin esto, la marca sería silenciosa: las dos filas del 18-ago pasarían de
    RUNNING a ABORTED sin que nadie llegara a enterarse de que hubo un muerto.
    """
    eventos: list[tuple[str, dict]] = []

    class _LoggerFalso:
        def warning(self, evento: str, **kwargs: object) -> None:
            eventos.append((evento, dict(kwargs)))

        def info(self, evento: str, **kwargs: object) -> None:
            return None

        def error(self, evento: str, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(main, "get_logger", lambda _n=None: _LoggerFalso())

    pg = PgFalso(
        huerfanas=[
            (901, "build_stg.build_plan_mensual", datetime(2026, 8, 18, 3, 10, 0)),
            (902, "build_stg.build_plan_mensual.tramo_39", datetime(2026, 8, 18, 3, 55, 0)),
        ]
    )
    cli(pg).invoke(main.cli, ["stage"])

    marcadas = [kw for nombre, kw in eventos if nombre == "etl_run_huerfana_abortada"]
    assert len(marcadas) == 2
    assert marcadas[0]["id"] == 901
    assert marcadas[0]["step"] == "build_stg.build_plan_mensual"
    assert "started_at" in marcadas[0]


# ---------------------------------------------------------------------------
# R5 · Los comandos de solo lectura no escriben nada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", COMANDOS_DE_LECTURA)
def test_f024_r5_los_comandos_de_lectura_no_marcan_huerfanas(
    cli, comando: str
) -> None:
    """El doble estalla si le piden abortar: no basta con «no lo hace hoy».

    `timings` es el caso que importa (DA-7): se ejecuta contra Azure para
    diagnosticar, y un comando de diagnóstico que escribe en la tabla que está
    diagnosticando es una trampa.
    """

    class PgQueNoAdmiteEscrituras(PgFalso):
        def abortar_runs_huerfanos(self, batch_id: str, ahora: datetime | None = None):
            raise AssertionError(
                f"'{comando}' es de solo lectura y ha intentado marcar huérfanas"
            )

        def record_run_completed(self, **kwargs: object) -> int:
            raise AssertionError(
                f"'{comando}' es de solo lectura y ha intentado registrar un paso"
            )

    pg = PgQueNoAdmiteEscrituras()
    resultado = cli(pg).invoke(main.cli, [comando])

    # El código de salida no importa aquí (check-coherencia sale 1 con raw
    # vacío); lo que importa es que no haya saltado ninguna AssertionError.
    assert not isinstance(resultado.exception, AssertionError), resultado.exception


# ---------------------------------------------------------------------------
# R7 · Marcar huérfanas nunca tumba la carga
# ---------------------------------------------------------------------------


def test_f024_r7_fallo_al_marcar_huerfanas_no_impide_el_comando(
    cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Es contabilidad. Si falla, se avisa y se sigue.

    El paso que venga detrás fallará por sí mismo si la BBDD no está; abortar
    aquí convertiría un problema de permisos sobre `_meta` en una noche sin
    carga.
    """
    eventos: list[str] = []

    class _LoggerFalso:
        def warning(self, evento: str, **kwargs: object) -> None:
            eventos.append(evento)

        def info(self, evento: str, **kwargs: object) -> None:
            return None

        def error(self, evento: str, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(main, "get_logger", lambda _n=None: _LoggerFalso())

    pg = PgFalso(error_al_abortar=RuntimeError("permission denied for table etl_runs"))
    resultado = cli(pg).invoke(main.cli, ["stage"])

    assert resultado.exit_code == 0, resultado.output
    assert "huerfanas_no_marcadas" in eventos
    # Y el paso se ejecutó igual.
    assert pg.pasos_registrados


# ---------------------------------------------------------------------------
# R18 · Los comandos sueltos registran su paso, con su batch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", list(STEPS_POR_COMANDO))
def test_f024_r18_comandos_sueltos_registran_el_paso(cli, comando: str) -> None:
    """Sin esto, `v_frescura` solo diría la verdad de lo que corre en `run-all`."""
    pg = PgFalso()
    resultado = cli(pg).invoke(main.cli, [comando])

    assert resultado.exit_code == 0, resultado.output
    assert len(pg.pasos_registrados) == 1, f"'{comando}' no registró su paso"

    step, estado, batch = pg.pasos_registrados[0]
    assert step == STEPS_POR_COMANDO[comando][1]
    assert estado == "SUCCESS"
    assert batch == pg.batches_de_la_marca[0], (
        "el paso se registró con un batch distinto del de la marca de huérfanas"
    )


def test_f024_r18_un_paso_fallido_registra_y_sale_uno(cli) -> None:
    """El registro va DESPUÉS de ejecutar y ANTES de salir: un FAILED también
    tiene que quedar escrito, que es cuando más falta hace."""
    pg = PgFalso()
    resultado = cli(pg, estado=StepStatus.FAILED).invoke(main.cli, ["stage"])

    assert resultado.exit_code == 1
    assert pg.pasos_registrados[0][1] == "FAILED"


def test_f024_r18_un_fallo_del_registro_no_cambia_el_codigo_de_salida(
    cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    class PgQueNoSabeRegistrar(PgFalso):
        def record_run_completed(self, **kwargs: object) -> int:
            raise RuntimeError("no hay sitio en el disco")

    pg = PgQueNoSabeRegistrar()
    resultado = cli(pg).invoke(main.cli, ["stage"])

    assert resultado.exit_code == 0, resultado.output


# ---------------------------------------------------------------------------
# R3 · `run-all` propaga UN SOLO batch a todo
# ---------------------------------------------------------------------------


def test_f024_r3_run_all_un_solo_batch_para_todas_las_filas(cli) -> None:
    """Los pasos y el grabador comparten batch. Es lo que hace que
    `v_raw_state` pueda decir «estas tablas son de la misma carga»."""
    construcciones: list[dict] = []
    pg = PgFalso()

    resultado = cli(pg, construcciones=construcciones).invoke(main.cli, ["run-all"])
    assert resultado.exit_code == 0, resultado.output

    batch = pg.batches_de_la_marca[0]

    # Los steps que aceptan batch lo recibieron, y es el mismo.
    batches_de_steps = {c["batch_id"] for c in construcciones if "batch_id" in c}
    assert batches_de_steps == {batch}, batches_de_steps

    # Y todas las filas de paso se escribieron con ese mismo batch.
    assert {b for _step, _estado, b in pg.pasos_registrados} == {batch}
    # El número NO se escribe a mano: era 6, F-047 lo dejó en 10 y la constante
    # se quedó atrás. Se ancla a la composición real, que es la que manda.
    esperados = len(main.build_pipeline_steps(settings_falsos()))
    assert len(pg.pasos_registrados) == esperados, (
        f"se registraron {len(pg.pasos_registrados)} filas y el pipeline tiene "
        f"{esperados} pasos: alguno no dejó rastro en `_meta.etl_runs`"
    )


def test_f024_r3_dos_ejecuciones_no_comparten_batch(cli) -> None:
    pg = PgFalso()
    corredor = cli(pg)
    corredor.invoke(main.cli, ["stage"])
    corredor.invoke(main.cli, ["stage"])

    assert len(set(pg.batches_de_la_marca)) == 2


# ---------------------------------------------------------------------------
# R11 · `--sin-puerta`: solo en los comandos sueltos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", ["stage", "build-mart"])
def test_f024_r11_los_comandos_sueltos_admiten_sin_puerta(
    cli, comando: str
) -> None:
    construcciones: list[dict] = []
    pg = PgFalso()

    resultado = cli(pg, construcciones=construcciones).invoke(
        main.cli, [comando, "--sin-puerta"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert construcciones[0]["omitir_puerta"] is True


@pytest.mark.parametrize("comando", ["stage", "build-mart"])
def test_f024_r11_sin_la_opcion_la_puerta_se_aplica(cli, comando: str) -> None:
    construcciones: list[dict] = []
    pg = PgFalso()

    cli(pg, construcciones=construcciones).invoke(main.cli, [comando])

    assert construcciones[0]["omitir_puerta"] is False


def test_f024_r11_run_all_no_admite_sin_puerta(cli) -> None:
    """El pipeline nocturno NO tiene vía de escape. A propósito: nadie está
    delante a las 02:00 para valorar si saltarse la puerta es razonable."""
    pg = PgFalso()
    resultado = cli(pg).invoke(main.cli, ["run-all", "--sin-puerta"])

    assert resultado.exit_code != 0
    assert "no such option" in resultado.output.lower() or "sin-puerta" in resultado.output


# ---------------------------------------------------------------------------
# R14 · `check-coherencia`
# ---------------------------------------------------------------------------


def estado_raw(tabla: str, status: str = "SUCCESS", batch: str | None = "b1") -> EstadoTablaRaw:
    return EstadoTablaRaw(
        tabla=tabla,
        status=status,
        batch_id=batch,
        started_at=datetime(2026, 8, 19, 2, 0, 0),
        finished_at=datetime(2026, 8, 19, 2, 30, 0),
        filas=10,
    )


def paso_stg(step: str = "build_stg", status: str = "SUCCESS") -> EstadoPaso:
    return EstadoPaso(
        id=1,
        step=step,
        status=status,
        batch_id="b1",
        started_at=datetime(2026, 8, 19, 2, 40, 0),
        finished_at=datetime(2026, 8, 19, 4, 30, 0),
    )


@pytest.mark.parametrize(
    ("caso", "pg_factoria", "codigo"),
    [
        (
            "raw y stg coherentes",
            lambda: PgFalso(estados=[estado_raw("con")], ultimo_stg=paso_stg()),
            0,
        ),
        (
            "raw incoherente",
            lambda: PgFalso(
                estados=[estado_raw("con", status="ABORTED")], ultimo_stg=paso_stg()
            ),
            1,
        ),
        (
            "stg a medias",
            lambda: PgFalso(
                estados=[estado_raw("con")],
                ultimo_stg=paso_stg("build_stg.build_obras", "RUNNING"),
            ),
            1,
        ),
        (
            "no se puede leer",
            lambda: PgFalso(error_al_leer=RuntimeError("connection refused")),
            2,
        ),
    ],
)
def test_f024_r14_check_coherencia_codigos_de_salida(
    cli, caso: str, pg_factoria, codigo: int
) -> None:
    """0 si todo OK, 1 si algún veredicto es KO, 2 si no puede ni leer.

    El 2 se distingue del 1 a propósito: «el datamart es incoherente» y «no he
    podido comprobarlo» exigen cosas distintas de quien lo lea.
    """
    resultado = cli(pg_factoria()).invoke(main.cli, ["check-coherencia"])
    assert resultado.exit_code == codigo, f"{caso}: {resultado.output}"


def test_f024_r14_check_coherencia_explica_por_que(cli) -> None:
    """La salida es el diagnóstico, no un código de salida a secas."""
    pg = PgFalso(
        estados=[estado_raw("con"), estado_raw("obr", batch="b2")],
        ultimo_stg=paso_stg(),
    )
    resultado = cli(pg, tablas=("con", "obr")).invoke(main.cli, ["check-coherencia"])

    assert resultado.exit_code == 1
    assert "con" in resultado.output
    assert "obr" in resultado.output
    assert "python main.py ingest --full" in resultado.output


def test_f024_r14_check_coherencia_no_escribe(cli) -> None:
    """Ni marca huérfanas ni registra paso: es un comando de diagnóstico."""
    pg = PgFalso(estados=[estado_raw("con")], ultimo_stg=paso_stg())
    cli(pg).invoke(main.cli, ["check-coherencia"])

    assert pg.batches_de_la_marca == []
    assert pg.pasos_registrados == []


# ---------------------------------------------------------------------------
# R19 · `check-frescura`
# ---------------------------------------------------------------------------


def fila(paso: str = "build_mart", horas: float | None = 1.0) -> FilaFrescura:
    ultimo_ok = (
        None if horas is None else datetime.utcnow() - timedelta(hours=horas)
    )
    return FilaFrescura(
        paso=paso,
        ultimo_ok_finished_at=ultimo_ok,
        ultimo_ok_batch_id="b1" if ultimo_ok else None,
        ultimo_ok_filas=100 if ultimo_ok else None,
        horas_desde_ultimo_ok=horas,
        ultimo_intento_started_at=datetime.utcnow(),
        ultimo_intento_status="SUCCESS",
        ultimo_intento_error=None,
    )


@pytest.mark.parametrize(
    ("caso", "pg_factoria", "codigo"),
    [
        ("fresco", lambda: PgFalso(frescura=[fila(horas=2.0)]), 0),
        ("caducado", lambda: PgFalso(frescura=[fila(horas=100.0)]), 1),
        ("sin build", lambda: PgFalso(frescura=[fila(horas=None)]), 1),
        ("sin filas", lambda: PgFalso(frescura=[]), 1),
        (
            "no se puede leer",
            lambda: PgFalso(error_al_leer=RuntimeError("connection refused")),
            2,
        ),
    ],
)
def test_f024_r19_check_frescura_codigos_de_salida(
    cli, caso: str, pg_factoria, codigo: int
) -> None:
    resultado = cli(pg_factoria()).invoke(main.cli, ["check-frescura"])
    assert resultado.exit_code == codigo, f"{caso}: {resultado.output}"


def test_f024_r19_check_frescura_admite_umbral_y_paso(cli) -> None:
    """Con un umbral más ancho, lo mismo pasa a estar fresco."""
    pg = PgFalso(frescura=[fila(paso="build_cierre", horas=40.0)])

    caducado = cli(pg).invoke(main.cli, ["check-frescura", "--paso", "build_cierre"])
    assert caducado.exit_code == 1
    assert "CADUCADO" in caducado.output

    fresco = cli(pg).invoke(
        main.cli, ["check-frescura", "--paso", "build_cierre", "--umbral-horas", "48"]
    )
    assert fresco.exit_code == 0
    assert "FRESCO" in fresco.output


def test_f024_r19_check_frescura_no_escribe(cli) -> None:
    pg = PgFalso(frescura=[fila()])
    cli(pg).invoke(main.cli, ["check-frescura"])

    assert pg.batches_de_la_marca == []
    assert pg.pasos_registrados == []


# ---------------------------------------------------------------------------
# Descubribilidad: los comandos nuevos existen y se documentan
# ---------------------------------------------------------------------------


def test_f024_r14_r19_los_comandos_nuevos_estan_en_la_ayuda() -> None:
    salida = CliRunner().invoke(main.cli, ["--help"]).output
    assert "check-coherencia" in salida
    assert "check-frescura" in salida


def test_f024_la_docstring_de_main_nombra_los_comandos_nuevos() -> None:
    """La cabecera de `main.py` es el índice del CLI: un comando que no está
    ahí no existe para quien abre el fichero."""
    assert "check-coherencia" in (main.__doc__ or "")
    assert "check-frescura" in (main.__doc__ or "")


# ---------------------------------------------------------------------------
# Huecos cerrados tras la campaña de mutación
# ---------------------------------------------------------------------------


def test_f024_r3_el_pipeline_es_incremental_salvo_que_se_pida_lo_contrario(
    cli,
) -> None:
    """El default de `build_pipeline_steps` es `full_refresh=False`.

    Importa aunque `run-all --full` sea lo que corre cada noche: el default es
    lo que se aplica a cualquier llamante que no opine, y una ingesta completa
    por descuido son ~33 min y un TRUNCATE de todas las tablas de `raw` contra
    el servidor compartido.
    """
    construcciones: list[dict] = []
    pg = PgFalso()
    corredor = cli(pg, construcciones=construcciones)

    main.build_pipeline_steps(settings_falsos())
    assert construcciones[0]["full_refresh"] is False

    construcciones.clear()
    main.build_pipeline_steps(settings_falsos(), True)
    assert construcciones[0]["full_refresh"] is True

    del corredor  # el runner solo estaba para instalar los dobles


@pytest.mark.parametrize(
    ("comando", "fragmento"),
    [
        ("check-coherencia", "estado de _meta"),
        ("check-frescura", "_meta.v_frescura"),
    ],
)
def test_f024_r14_r19_el_error_de_lectura_va_a_stderr(
    cli, comando: str, fragmento: str
) -> None:
    """Los dos comandos son de diagnóstico y se pipean.

    Si el «no se pudo leer» saliera por stdout se mezclaría con la tabla que
    alguien esté redirigiendo a un fichero, y el código 2 llegaría acompañado
    de un informe corrupto.
    """
    pg = PgFalso(error_al_leer=RuntimeError("connection refused"))
    resultado = cli(pg).invoke(main.cli, [comando])

    assert resultado.exit_code == 2
    assert fragmento in resultado.stderr
    assert fragmento not in resultado.stdout


def test_f024_r19_la_ayuda_ensena_el_umbral_y_el_paso_por_defecto() -> None:
    """`--help` tiene que decir contra qué se está juzgando.

    Un `check-frescura` que dice CADUCADO sin decir el umbral obliga a abrir el
    código para saber si son 24 h o 30.
    """
    salida = CliRunner().invoke(main.cli, ["check-frescura", "--help"]).output

    assert str(UMBRAL_FRESCURA_HORAS) in salida
    assert "build_mart" in salida
    # `show_default` de click las imprime así; sin él no aparece el bloque.
    assert salida.count("default:") >= 2


# ---------------------------------------------------------------------------
# R11 / DA-2 · run-all NO tiene vía de escape (bloqueante B1 del reviewer)
# ---------------------------------------------------------------------------
#
# El test anterior de R11 comprobaba que click rechaza `--sin-puerta` en
# `run-all`. Eso protege la superficie de la CLI, no la composición del
# pipeline: si alguien construye BuildStgStep/BuildMartStep con
# `omitir_puerta=True` dentro de `build_pipeline_steps`, la opción sigue
# rechazándose y las dos puertas quedan desactivadas todas las noches. El
# reviewer lo demostró aplicando ese mutante a mano: 587 tests en verde.
# Este test mira los objetos, no la opción.


def test_f024_r11_el_pipeline_nocturno_lleva_las_dos_puertas_activas() -> None:
    from etl_sigrid.application.steps.build_mart_step import BuildMartStep
    from etl_sigrid.application.steps.build_stg_step import BuildStgStep

    pasos = main.build_pipeline_steps(settings_falsos(), False, "20260818T020000-prueba")

    stg = [p for p in pasos if isinstance(p, BuildStgStep)]
    mart = [p for p in pasos if isinstance(p, BuildMartStep)]
    assert len(stg) == 1 and len(mart) == 1, "el pipeline lleva un stage y un mart"
    assert stg[0]._omitir_puerta is False, "run-all no puede saltarse la puerta de raw"
    assert mart[0]._omitir_puerta is False, "run-all no puede saltarse la puerta de stg"


def test_f024_r11_las_puertas_del_pipeline_no_se_desactivan_ni_con_full_refresh() -> None:
    from etl_sigrid.application.steps.build_mart_step import BuildMartStep
    from etl_sigrid.application.steps.build_stg_step import BuildStgStep

    pasos = main.build_pipeline_steps(settings_falsos(), True)
    for p in pasos:
        if isinstance(p, (BuildStgStep, BuildMartStep)):
            assert p._omitir_puerta is False
