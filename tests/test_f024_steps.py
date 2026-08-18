# tests/test_f024_steps.py
"""
F-024 · Tests de las puertas dentro de los steps: `raw` antes de `build_stg`
(R10-R12) y `stg` antes de `build_mart` (R15), más la propagación del
`batch_id` (R3).

Lo que se comprueba aquí NO es el veredicto —eso es dominio puro y vive en
`test_f024_dominio.py`— sino la ORQUESTACIÓN: que la puerta se evalúe antes de
tocar nada, que un KO no deje ni un `TRUNCATE` ejecutado, y que el veredicto
quede escrito en `_meta.etl_runs` pase lo que pase.

Por eso el doble lleva una traza ordenada: la afirmación importante de R10 no
es «falló», es «falló ANTES». Un `TRUNCATE stg.obras` ya ejecutado no se
deshace porque el step devuelva FAILED después.

Ningún test abre red ni BBDD: se sustituye `build_postgres_client` en el
módulo del step, que es por donde el step consigue su cliente.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.build_mart_step import BuildMartStep
from etl_sigrid.application.steps.build_stg_step import BuildStgStep
from etl_sigrid.domain.coherencia import EstadoPaso, EstadoTablaRaw
from etl_sigrid.domain.entities import StepStatus
from tests.test_f019_tramos import LoggerFalso

BATCH = "20260819T020000Z-abc123"
BATCH_VIEJO = "20260818T020000Z-bbbbbb"

#: Las tres tablas que declara el YAML falso de estos tests.
TABLAS = ("con", "obr", "obrparpre")


def estado_raw(
    tabla: str, status: str = "SUCCESS", batch_id: str | None = BATCH
) -> EstadoTablaRaw:
    return EstadoTablaRaw(
        tabla=tabla,
        status=status,
        batch_id=batch_id,
        started_at=datetime(2026, 8, 19, 2, 0, 0),
        finished_at=datetime(2026, 8, 19, 2, 30, 0),
        filas=1_000,
    )


def raw_coherente() -> list[EstadoTablaRaw]:
    return [estado_raw(t) for t in TABLAS]


class PgFalso:
    """Doble de `PostgresClient` con traza ORDENADA de lo que se le pide.

    No hereda de `PostgresClient` a propósito (mismo criterio que F-019): si un
    step llamara a un método que este doble no implementa, el test tiene que
    fallar, no acabar abriendo una conexión real.
    """

    def __init__(
        self,
        estados: list[EstadoTablaRaw] | None = None,
        ultimo_stg: EstadoPaso | None = None,
    ) -> None:
        self._estados = raw_coherente() if estados is None else list(estados)
        self._ultimo_stg = ultimo_stg

        self.traza: list[str] = []
        self.arranques: list[tuple[str, str, str | None]] = []
        self.cierres: list[tuple[int, str, int, str | None]] = []
        self._ultimo_run = 0

    # --- lo que consultan las puertas ---
    def fetch_estado_raw(self) -> list[EstadoTablaRaw]:
        self.traza.append("estado_raw")
        return list(self._estados)

    def fetch_ultimo_intento_stg(self) -> EstadoPaso | None:
        self.traza.append("ultimo_stg")
        return self._ultimo_stg

    # --- registro en _meta.etl_runs ---
    def record_run_start(
        self, stage: str, step: str, batch_id: str | None = None
    ) -> int:
        self.traza.append(f"start:{step}")
        self.arranques.append((stage, step, batch_id))
        self._ultimo_run += 1
        return self._ultimo_run

    def record_run_end(
        self,
        run_id: int,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.traza.append(f"end:{status}")
        self.cierres.append((run_id, status, rows_processed, error_message))

    # --- lo que NO debe pasar tras un KO ---
    def execute_sql_file(self, path: object, params: object = None) -> None:
        self.traza.append("fichero")

    def execute_sql_text(self, sql_text: str) -> int:
        self.traza.append("sql")
        return 0

    def truncate_table(self, schema: str, table: str) -> None:
        self.traza.append("truncate")

    # --- resto del andamiaje que usan los steps ---
    def assert_columns_exist(self, schema: str, table: str, cols: list[str]) -> None:
        self.traza.append("preflight")

    def count_rows(self, schema: str, table: str) -> int:
        return 0

    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        self.traza.append("pesos")
        return {1: 10}

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        self.traza.append("medicion")
        return 1.0

    # --- ayudas de aserción ---
    @property
    def escrituras(self) -> list[str]:
        """Todo lo que TOCA datos. Es lo que un KO no puede haber hecho."""
        return [t for t in self.traza if t in ("fichero", "sql", "truncate")]

    def cierre_de(self, paso: str) -> tuple[int, str, int, str | None]:
        """El `record_run_end` que corresponde al `record_run_start` de `paso`."""
        for indice, (_stage, step, _batch) in enumerate(self.arranques, start=1):
            if step == paso:
                for cierre in self.cierres:
                    if cierre[0] == indice:
                        return cierre
        pytest.fail(f"no se registró ningún cierre para el paso {paso!r}")


def settings_falsos(tablas: tuple[str, ...] = TABLAS) -> SimpleNamespace:
    return SimpleNamespace(
        postgres=SimpleNamespace(
            tramo_max_filas=1_000_000,
            disco_total_gb=32,
            disco_limite_pct=80.0,
        ),
        business_rules={
            "sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}}
        },
        tables_sigrid={
            "tables": [
                {"source_table": t, "target_table": t} for t in tablas
            ]
        },
        # Solo se usa para el tamaño de página del log de la ingesta: ningún
        # test de este fichero abre una conexión HTTP.
        sigrid_api=SimpleNamespace(page_size=10_000),
    )


@pytest.fixture
def stg(monkeypatch: pytest.MonkeyPatch):
    """Fábrica de `BuildStgStep` con el cliente sustituido por el doble."""
    import etl_sigrid.application.steps.build_stg_step as modulo

    def _construir(pg: PgFalso, **kwargs: object) -> BuildStgStep:
        monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)
        return BuildStgStep(settings_falsos(), **kwargs)  # type: ignore[arg-type]

    return _construir


# ---------------------------------------------------------------------------
# R10 · La puerta va ANTES de cualquier escritura de `build_stg`
# ---------------------------------------------------------------------------


def test_f024_r10_puerta_ko_no_toca_stg_y_falla(stg) -> None:
    """El caso del 18-ago: una tabla del batch viejo, otra muerta a medias.

    Lo que se afirma no es solo que falle, sino que no llegó a EJECUTAR nada.
    """
    pg = PgFalso(
        estados=[
            estado_raw("con"),
            estado_raw("obr", status="ABORTED"),
            estado_raw("obrparpre", batch_id=BATCH_VIEJO),
        ]
    )

    resultado = stg(pg, batch_id=BATCH).run()

    assert resultado.status is StepStatus.FAILED
    assert pg.escrituras == [], (
        "la puerta dejó pasar alguna escritura antes de negarse"
    )
    assert "preflight" not in pg.traza

    # El mensaje que llega al humano es el accionable de R9.
    assert "KO" in (resultado.error_message or "")
    assert "python main.py ingest --full" in (resultado.error_message or "")

    # Y el veredicto queda escrito, con su motivo.
    assert ("stage", "build_stg.puerta_raw", BATCH) in pg.arranques
    _, estado, _, motivo = pg.cierre_de("build_stg.puerta_raw")
    assert estado == "FAILED"
    assert "python main.py ingest --full" in (motivo or "")


@pytest.mark.parametrize(
    ("descripcion", "estados"),
    [
        ("falta una tabla", [estado_raw("con"), estado_raw("obr")]),
        ("una en RUNNING", [estado_raw("con"), estado_raw("obr", status="RUNNING"),
                            estado_raw("obrparpre")]),
        ("histórico sin batch", [estado_raw(t, batch_id=None) for t in TABLAS]),
        ("raw vacío", []),
    ],
)
def test_f024_r10_ningun_raw_incoherente_llega_a_construir(
    stg, descripcion: str, estados: list[EstadoTablaRaw]
) -> None:
    pg = PgFalso(estados=estados)
    resultado = stg(pg, batch_id=BATCH).run()

    assert resultado.status is StepStatus.FAILED, descripcion
    assert pg.escrituras == [], descripcion


def test_f024_r10_puerta_ok_registra_y_continua(stg) -> None:
    """Noche normal: la puerta pasa, deja su fila SUCCESS y el step construye."""
    pg = PgFalso()

    resultado = stg(pg, batch_id=BATCH).run()

    assert resultado.status is StepStatus.SUCCESS
    assert resultado.metadata["raw_batch_id"] == BATCH

    _, estado, _, motivo = pg.cierre_de("build_stg.puerta_raw")
    assert estado == "SUCCESS"
    assert motivo is None

    # Y sí construyó: los ficheros SQL de stg se ejecutaron.
    assert pg.traza.count("fichero") >= 8


def test_f024_r10_la_puerta_precede_al_preflight(stg) -> None:
    """El ORDEN exacto: puerta, luego pre-flight, luego el primer sub-paso.

    El pre-flight de F-002 solo lee columnas, pero es una consulta por tabla
    contra el servidor compartido. Si el raw ya es incoherente, ni eso.
    """
    pg = PgFalso()
    stg(pg, batch_id=BATCH).run()

    assert pg.traza[:4] == [
        "start:build_stg.puerta_raw",
        "estado_raw",
        "end:SUCCESS",
        "preflight",
    ]
    # Y el primer sub-paso arranca después de todos los pre-flight.
    assert pg.traza.index("start:build_stg.functions") > _ultimo_indice(pg.traza, "preflight")


# ---------------------------------------------------------------------------
# R11 · `--sin-puerta` se evalúa igual, se registra y avisa
# ---------------------------------------------------------------------------


def test_f024_r11_stage_sin_puerta_registra_skipped_y_continua(
    stg, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La vía de escape deja rastro por escrito. Ese es el trato."""
    import etl_sigrid.application.steps.build_stg_step as modulo

    registro = LoggerFalso()
    monkeypatch.setattr(modulo, "logger", registro)

    pg = PgFalso(estados=[estado_raw(t, batch_id=None) for t in TABLAS])
    resultado = stg(pg, batch_id=BATCH, omitir_puerta=True).run()

    assert resultado.status is StepStatus.SUCCESS, "con --sin-puerta debe construir"
    assert pg.escrituras, "no construyó nada"

    # La puerta se evaluó igual y su veredicto quedó registrado.
    assert "estado_raw" in pg.traza
    _, estado, _, motivo = pg.cierre_de("build_stg.puerta_raw")
    assert estado == "SKIPPED"
    assert "--sin-puerta" in (motivo or "")
    assert "F-024" in (motivo or ""), "el motivo no incluye el veredicto real"

    # Y un WARNING, que es lo que se ve en los logs de Azure.
    assert registro.de("puerta_omitida"), "no se avisó de que la puerta se omitió"


def test_f024_r11_sin_puerta_no_es_una_excusa_para_no_mirar(stg) -> None:
    """Con `--sin-puerta` y un raw perfecto, la fila sigue siendo SKIPPED.

    Es deliberado: lo que la fila cuenta es «este build se hizo SIN puerta»,
    no lo que la puerta habría dictaminado. Quien audite `_meta.etl_runs`
    tiene que poder distinguir un build verificado de uno que no lo fue.
    """
    pg = PgFalso()
    resultado = stg(pg, batch_id=BATCH, omitir_puerta=True).run()

    assert resultado.status is StepStatus.SUCCESS
    assert pg.cierre_de("build_stg.puerta_raw")[1] == "SKIPPED"


# ---------------------------------------------------------------------------
# R12 · Las tablas requeridas salen del YAML, sin lista paralela en código
# ---------------------------------------------------------------------------


def test_f024_r12_las_requeridas_salen_del_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lo que exige la puerta es exactamente lo que ingiere `run-all`.

    Una lista paralela en código se desincroniza el día que alguien añade una
    tabla al YAML, y entonces la puerta acredita una carga a la que le falta
    justo la tabla nueva.
    """
    import etl_sigrid.application.steps.build_stg_step as modulo

    recibidas: list[object] = []
    original = modulo.evaluar_coherencia_raw

    def espia(estados: object, requeridas: object):
        recibidas.append(list(requeridas))
        return original(estados, requeridas)

    monkeypatch.setattr(modulo, "evaluar_coherencia_raw", espia)

    pg = PgFalso(estados=[estado_raw("una"), estado_raw("otra"), estado_raw("tercera")])
    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)

    BuildStgStep(  # type: ignore[arg-type]
        settings_falsos(tablas=("una", "otra", "tercera")), batch_id=BATCH
    ).run()

    assert recibidas == [["una", "otra", "tercera"]]


# ---------------------------------------------------------------------------
# R3 · El batch viaja a TODAS las filas que escribe el step
# ---------------------------------------------------------------------------


def test_f024_r3_los_subpasos_y_tramos_llevan_el_batch(stg) -> None:
    """Sub-pasos y tramos incluidos: si uno se quedara sin batch, la fila
    huérfana que deje una muerte externa no se podría atribuir a nadie."""
    pg = PgFalso()
    stg(pg, batch_id=BATCH).run()

    pasos = [step for _stage, step, _batch in pg.arranques]
    assert "build_stg.puerta_raw" in pasos
    assert "build_stg.build_obras" in pasos
    assert any(p.startswith("build_stg.build_plan_mensual.tramo_") for p in pasos)

    sin_batch = [step for _s, step, batch in pg.arranques if batch != BATCH]
    assert sin_batch == [], f"estas filas se escribieron sin batch: {sin_batch}"


def test_f024_r3_sin_batch_el_step_sigue_funcionando(stg) -> None:
    """Compatibilidad: `BuildStgStep(settings)` sin batch sigue construyendo.

    Importa porque es como lo llaman los tests de F-019 y como lo llamaría
    cualquier código anterior a esta feature.
    """
    pg = PgFalso()
    resultado = stg(pg).run()

    assert resultado.status is StepStatus.SUCCESS
    assert all(batch is None for _s, _step, batch in pg.arranques)


# ---------------------------------------------------------------------------
# R15 · `build_mart` exige un stage completo (DA-5)
# ---------------------------------------------------------------------------


def paso_stg(step: str, status: str, ident: int = 500) -> EstadoPaso:
    return EstadoPaso(
        id=ident,
        step=step,
        status=status,
        batch_id=BATCH,
        started_at=datetime(2026, 8, 19, 2, 40, 0),
        finished_at=datetime(2026, 8, 19, 4, 30, 0),
    )


@pytest.fixture
def mart(monkeypatch: pytest.MonkeyPatch):
    """Fábrica de `BuildMartStep` con el cliente sustituido por el doble."""
    import etl_sigrid.application.steps.build_mart_step as modulo

    def _construir(pg: PgFalso, **kwargs: object) -> BuildMartStep:
        monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)
        return BuildMartStep(settings_falsos(), **kwargs)  # type: ignore[arg-type]

    return _construir


@pytest.mark.parametrize(
    ("caso", "ultimo"),
    [
        ("sin ninguna fila de stg", None),
        ("sub-paso abortado", paso_stg("build_stg.build_presupuesto", "ABORTED")),
        ("tramo en curso", paso_stg("build_stg.build_plan_mensual.tramo_39", "RUNNING")),
        ("el paso fallo", paso_stg("build_stg", "FAILED")),
        # El caso del 18-ago: el proceso murió y la última fila es un sub-paso
        # que sí había terminado bien. `stg` quedó a medias igualmente.
        ("sub-paso terminado, paso no", paso_stg("build_stg.build_obras", "SUCCESS")),
    ],
)
def test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino(
    mart, caso: str, ultimo: EstadoPaso | None
) -> None:
    """Un `stg` mezclado no llega a `mart`. Y no se ejecuta ni un SQL.

    `mart/01_ddl.sql` empieza con un DROP + CREATE de la tabla de hechos: si
    la puerta se evaluara después, el primer fichero ya se habría llevado por
    delante el `mart` bueno de la noche anterior.
    """
    pg = PgFalso(ultimo_stg=ultimo)

    resultado = mart(pg, batch_id=BATCH).run()

    assert resultado.status is StepStatus.FAILED, caso
    assert pg.escrituras == [], caso

    _, estado, _, motivo = pg.cierre_de("build_mart.puerta_stg")
    assert estado == "FAILED", caso
    assert "python main.py stage" in (motivo or ""), caso
    assert "KO" in (resultado.error_message or ""), caso


def test_f024_r15_build_mart_ok_si_stage_success(mart) -> None:
    """La noche normal: el último `build_stg` terminó, así que se construye."""
    pg = PgFalso(ultimo_stg=paso_stg("build_stg", "SUCCESS"))

    resultado = mart(pg, batch_id=BATCH).run()

    assert resultado.status is StepStatus.SUCCESS
    assert pg.traza.count("fichero") >= 7, "no construyó mart"

    assert ("build_mart", "build_mart.puerta_stg", BATCH) in pg.arranques
    assert pg.cierre_de("build_mart.puerta_stg")[1] == "SUCCESS"


def test_f024_r15_la_puerta_precede_al_primer_sql_de_mart(mart) -> None:
    """El ORDEN: puerta cerrada antes de tocar el primer fichero."""
    pg = PgFalso(ultimo_stg=paso_stg("build_stg", "SUCCESS"))
    mart(pg, batch_id=BATCH).run()

    assert pg.traza[:3] == [
        "start:build_mart.puerta_stg",
        "ultimo_stg",
        "end:SUCCESS",
    ]
    assert pg.traza[3] == "fichero"


def test_f024_r15_build_mart_sin_puerta_registra_y_continua(
    mart, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Misma vía de escape que en `stage`, y con el mismo precio: queda escrito."""
    import etl_sigrid.application.steps.build_mart_step as modulo

    registro = LoggerFalso()
    monkeypatch.setattr(modulo, "logger", registro)

    pg = PgFalso(ultimo_stg=paso_stg("build_stg.build_plan_mensual", "ABORTED"))
    resultado = mart(pg, batch_id=BATCH, omitir_puerta=True).run()

    assert resultado.status is StepStatus.SUCCESS
    assert pg.escrituras, "no construyó nada"

    _, estado, _, motivo = pg.cierre_de("build_mart.puerta_stg")
    assert estado == "SKIPPED"
    assert "--sin-puerta" in (motivo or "")
    assert "build_stg.build_plan_mensual" in (motivo or "")
    assert registro.de("puerta_omitida")


def test_f024_r15_build_mart_sin_batch_sigue_funcionando(mart) -> None:
    """Compatibilidad con los llamantes anteriores a F-024."""
    pg = PgFalso(ultimo_stg=paso_stg("build_stg", "SUCCESS"))
    resultado = mart(pg).run()

    assert resultado.status is StepStatus.SUCCESS
    assert all(batch is None for _s, _step, batch in pg.arranques)


def _ultimo_indice(traza: list[str], valor: str) -> int:
    return len(traza) - 1 - traza[::-1].index(valor)


# ---------------------------------------------------------------------------
# R3 · La ingesta estampa el batch en la fila de CADA tabla
# ---------------------------------------------------------------------------


def test_f024_r3_la_ingesta_estampa_el_batch_por_tabla() -> None:
    """Es la fila que después lee `_meta.v_raw_state`, y con ella la puerta.

    Sin batch aquí, toda la feature se cae: `v_raw_state` no podría decir de
    qué carga viene cada tabla y la puerta rechazaría siempre por `sin_batch`.
    """
    from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
    from etl_sigrid.domain.entities import ColumnSpec, TableSpec

    class _ApiFalsa:
        def fetch_table_schema(self, tabla: str) -> list[ColumnSpec]:
            return [
                ColumnSpec(
                    name="ide",
                    sql_server_type="int",
                    char_max_length=None,
                    numeric_precision=None,
                    numeric_scale=None,
                    is_nullable=False,
                )
            ]

        def stream_table(self, *args: object, **kwargs: object):
            yield [{"ide": 1}, {"ide": 2}]

    class _PgFalso(PgFalso):
        def ensure_raw_table(self, *args: object, **kwargs: object) -> None:
            self.traza.append("ensure")

        def get_max_id(self, schema: str, table: str, id_column: str = "ide") -> int:
            return 0

        def copy_rows(self, **kwargs: object) -> int:
            self.traza.append("copy")
            return 2

    pg = _PgFalso()
    paso = IngestRawStep(settings_falsos(), batch_id=BATCH)  # type: ignore[arg-type]

    filas = paso._ingest_one_table(
        TableSpec(source_table="con", target_table="con"), _ApiFalsa(), pg
    )

    assert filas == 2
    assert pg.arranques == [("ingest", "ingest_raw.con", BATCH)]
    assert pg.cierres[0][1] == "SUCCESS"


def test_f024_r3_una_tabla_que_falla_tambien_deja_su_batch() -> None:
    """La fila FAILED lleva batch igual: es la que delata de qué carga viene el
    intento que rompió la coherencia."""
    from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
    from etl_sigrid.domain.entities import TableSpec

    class _ApiQueFalla:
        def fetch_table_schema(self, tabla: str) -> list:
            raise RuntimeError("sigrid-api no responde")

    pg = PgFalso()
    paso = IngestRawStep(settings_falsos(), batch_id=BATCH)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="sigrid-api"):
        paso._ingest_one_table(
            TableSpec(source_table="con", target_table="con"), _ApiQueFalla(), pg
        )

    assert pg.arranques == [("ingest", "ingest_raw.con", BATCH)]
    assert pg.cierres[0][1] == "FAILED"
