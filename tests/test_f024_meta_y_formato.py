# tests/test_f024_meta_y_formato.py
"""
F-024 · Tests del DDL de `_meta` (R2, R13, R16, R17) y de los formatos de
salida (R6, R19, R20).

Los del DDL son ESTÁTICOS: leen `sql/ddl/00_meta.sql` como texto. No validan
SQL —eso lo hacen las verificaciones MANUAL contra BBDD real de R25 y R26—,
pero convierten en rojo inmediato la regresión más probable: que alguien
sustituya la migración idempotente por un `DROP` y se lleve por delante el
histórico de `_meta.etl_runs` en producción, o que renombre una columna que
leen el MCP y Power BI.

Ese fichero lo ejecuta `_bootstrap_schemas_and_meta` en la PRIMERA conexión de
cada proceso. O sea: cada noche, y cada vez que alguien lanza un comando. Por
eso todo lo que hay dentro tiene que ser idempotente, y por eso hay un test
que lo comprueba sentencia a sentencia.

Ninguno abre red ni BBDD.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from etl_sigrid.domain.coherencia import EstadoPaso, EstadoTablaRaw
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.postgres.frescura import FilaFrescura
from etl_sigrid.infrastructure.postgres.postgres_client import (
    PostgresClient,
    _split_sql_statements,
)
from etl_sigrid.infrastructure.postgres.step_run_recorder import PostgresStepRunRecorder
from tests.test_f019_tramos import CursorFalso, cliente_con

REPO_ROOT = Path(__file__).resolve().parents[1]
RUTA_META = (
    REPO_ROOT
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "ddl" / "00_meta.sql"
)


def sql_meta() -> str:
    return RUTA_META.read_text(encoding="utf-8")


def sentencias() -> list[str]:
    """Las sentencias del fichero, sin comentarios de línea."""
    limpias = []
    for stmt in _split_sql_statements(sql_meta()):
        sin_comentarios = re.sub(r"(?m)^\s*--.*$", "", stmt).strip()
        if sin_comentarios:
            limpias.append(sin_comentarios)
    return limpias


# ---------------------------------------------------------------------------
# R2 · `_meta.etl_runs` conserva el histórico y gana `batch_id`
# ---------------------------------------------------------------------------


def test_f024_r2_ddl_meta_migra_sin_destruir() -> None:
    """La columna se AÑADE. Ni un `DROP`, ni una recreación de la tabla.

    El histórico de `_meta.etl_runs` es el único sitio donde consta cuánto tardó
    cada carga y qué pasó las noches que fallaron. Recrear la tabla para añadir
    una columna lo borraría, en producción, y en silencio.
    """
    texto = sql_meta()

    assert re.search(
        r"ALTER\s+TABLE\s+_meta\.etl_runs\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+"
        r"batch_id\s+TEXT",
        texto,
        re.IGNORECASE,
    ), "no se añade batch_id de forma idempotente"

    assert re.search(
        r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+\w+\s+ON\s+_meta\.etl_runs\s*\(\s*batch_id",
        texto,
        re.IGNORECASE,
    ), "batch_id no tiene índice idempotente"

    # El histórico se conserva: nada que borre datos ni estructura.
    for prohibido in ("DROP TABLE", "DROP COLUMN", "TRUNCATE", "DELETE FROM"):
        assert prohibido not in texto.upper(), (
            f"00_meta.sql contiene '{prohibido}': se ejecuta en CADA arranque de "
            f"CADA proceso contra el datamart de producción"
        )

    # Y la tabla se sigue creando solo si no existe.
    assert re.search(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+_meta\.etl_runs", texto, re.IGNORECASE
    )


def test_f024_r2_batch_id_admite_nulos() -> None:
    """`NULL` es el valor del histórico anterior a F-024, y `timings` tiene que
    seguir funcionando sobre él. Un `NOT NULL` sin default rompería el ALTER."""
    texto = sql_meta()
    columna = re.search(
        r"ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+batch_id\s+TEXT([^;]*)",
        texto,
        re.IGNORECASE,
    )
    assert columna is not None
    assert "NOT NULL" not in columna.group(1).upper()


def test_f024_r2_todas_las_sentencias_del_ddl_son_idempotentes() -> None:
    """Cada sentencia del fichero, una por una.

    No es un test de estilo: `_bootstrap_schemas_and_meta` ejecuta este fichero
    entero en la primera conexión de cada proceso. Una sentencia no idempotente
    aquí es un error en cada ejecución del pipeline a partir de la segunda.
    """
    idempotente = re.compile(
        r"^(CREATE\s+(OR\s+REPLACE\s+)?VIEW|"
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS|"
        r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS|"
        r"ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS)",
        re.IGNORECASE,
    )
    for stmt in sentencias():
        assert idempotente.match(stmt), (
            f"sentencia no idempotente en 00_meta.sql: {stmt[:80]!r}"
        )


def test_f024_r2_el_ddl_no_lleva_bloques_que_el_troceador_no_sabe_partir() -> None:
    """Sin `$$` ni comentarios de bloque: `_split_sql_statements` no los maneja
    y lo dice en su propio docstring."""
    texto = sql_meta()
    assert "$$" not in texto
    assert "/*" not in texto


# ---------------------------------------------------------------------------
# R13 · Vista `_meta.v_raw_state`
# ---------------------------------------------------------------------------


def test_f024_r13_vista_raw_state_definida_en_el_ddl() -> None:
    """Última ingesta por tabla. `CREATE OR REPLACE` porque el fichero se
    ejecuta en cada arranque."""
    texto = sql_meta()

    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_raw_state", texto, re.IGNORECASE
    ), "falta la vista _meta.v_raw_state"

    vista = _cuerpo_de_vista("v_raw_state")

    # Una fila por tabla: la más reciente manda.
    assert re.search(r"DISTINCT\s+ON\s*\(\s*step\s*\)", vista, re.IGNORECASE)
    # Solo las filas de ingesta, y el nombre de la tabla es el sufijo del step.
    assert "ingest_raw." in vista
    assert re.search(r"WHERE\s+step\s+LIKE", vista, re.IGNORECASE)
    # Desempate estable: sin el `id DESC` dos filas del mismo segundo bailan.
    assert re.search(
        r"ORDER\s+BY\s+step\s*,\s*started_at\s+DESC\s*,\s*id\s+DESC", vista, re.IGNORECASE
    )

    for columna in ("tabla", "status", "batch_id", "started_at", "finished_at", "filas"):
        assert re.search(rf"\b{columna}\b", vista), (
            f"v_raw_state no expone la columna '{columna}'"
        )


# ---------------------------------------------------------------------------
# R16 · Vista `_meta.v_frescura`
# ---------------------------------------------------------------------------

#: Las ocho columnas que consumen `check-frescura`, el MCP y Power BI. Se
#: escriben aquí como contrato: renombrar una en el SQL sin actualizar a sus
#: consumidores es exactamente el fallo que este test convierte en rojo.
COLUMNAS_FRESCURA = (
    "paso",
    "ultimo_ok_finished_at",
    "ultimo_ok_batch_id",
    "ultimo_ok_filas",
    "horas_desde_ultimo_ok",
    "ultimo_intento_started_at",
    "ultimo_intento_status",
    "ultimo_intento_error",
)


def test_f024_r16_vista_frescura_columnas_y_or_replace() -> None:
    texto = sql_meta()

    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.v_frescura", texto, re.IGNORECASE
    ), "falta la vista _meta.v_frescura"

    vista = _cuerpo_de_vista("v_frescura")

    for columna in COLUMNAS_FRESCURA:
        assert re.search(rf"\bAS\s+{columna}\b", vista, re.IGNORECASE), (
            f"v_frescura no expone la columna '{columna}' con ese nombre exacto"
        )


def test_f024_r16_frescura_separa_ultimo_ok_de_ultimo_intento() -> None:
    """No son la misma noticia: un `build_mart` que falló esta noche deja
    `mart` con lo de ayer, y el consumidor tiene que ver las dos cosas.

    Por eso el JOIN es LEFT: un paso que nunca terminó bien sigue apareciendo,
    con `ultimo_ok_*` a nulo. Un INNER JOIN lo escondería, que es justo el
    silencio que esta feature elimina.
    """
    vista = _cuerpo_de_vista("v_frescura")

    assert re.search(r"status\s*=\s*'SUCCESS'", vista, re.IGNORECASE), (
        "el bloque de 'último OK' no filtra por SUCCESS"
    )
    assert re.search(r"LEFT\s+JOIN", vista, re.IGNORECASE), (
        "el JOIN debe ser LEFT: un paso sin ningún OK tiene que seguir saliendo"
    )


def test_f024_r16_frescura_solo_mira_pasos_de_pipeline() -> None:
    """Pasos de nivel de pipeline (`step` sin punto), no sub-pasos ni tramos.

    Sin este filtro, `v_frescura` tendría una fila por cada uno de los 60
    tramos de `build_plan_mensual` y dejaría de ser legible.
    """
    vista = _cuerpo_de_vista("v_frescura")
    assert re.search(r"position\s*\(\s*'\.'\s+IN\s+step\s*\)\s*=\s*0", vista, re.IGNORECASE)


def test_f024_r16_las_horas_se_calculan_en_utc() -> None:
    """`started_at`/`finished_at` son TIMESTAMP sin zona escritos con
    `datetime.utcnow()`. Comparar contra un `now()` local daría el desfase
    horario de España como «antigüedad», y en verano son dos horas."""
    vista = _cuerpo_de_vista("v_frescura")
    assert re.search(r"now\(\)\s+AT\s+TIME\s+ZONE\s+'UTC'", vista, re.IGNORECASE)
    # Segundos a horas.
    assert "3600" in vista


def test_f024_r16_ninguna_vista_de_meta_lee_de_otra_capa() -> None:
    """Cero coste sobre el servidor compartido: las vistas solo tocan `_meta`.

    Si una vista de `_meta` leyera de `raw` o de `mart`, cada refresco de Power
    BI dispararía un escaneo sobre las tablas grandes del servidor que comparten
    `albaranes` y `partes`.
    """
    # Se miran los ORÍGENES (FROM / JOIN), no el texto entero: `ingest_raw.`
    # contiene `raw.` y buscar la subcadena a pelo daría un falso positivo.
    ajenos = {"raw", "stg", "mart", "cierre", "compras", "maestro", "retenciones", "aux"}

    for nombre in ("v_raw_state", "v_frescura"):
        vista = _cuerpo_de_vista(nombre)
        origenes = re.findall(
            r"(?:FROM|JOIN)\s+([A-Za-z_][\w.]*)", vista, re.IGNORECASE
        )
        assert origenes, f"{nombre} no lee de ningún sitio: ¿se ha vaciado la vista?"

        for origen in origenes:
            esquema = origen.split(".")[0] if "." in origen else ""
            assert esquema not in ajenos, (
                f"{nombre} lee de '{origen}': las vistas de _meta solo leen de _meta"
            )


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------


def _cuerpo_de_vista(nombre: str) -> str:
    """La sentencia completa que define una vista, sin sus comentarios."""
    for stmt in sentencias():
        if re.search(rf"CREATE\s+OR\s+REPLACE\s+VIEW\s+_meta\.{nombre}\b", stmt, re.I):
            return stmt
    pytest.fail(f"no hay ninguna sentencia que defina _meta.{nombre}")


# ---------------------------------------------------------------------------
# El cliente Postgres contra dobles de cursor (R2, R4, R13, R16)
#
# Desviación menor respecto a `design.md`, que repartía estos tests entre
# `test_f024_steps.py` y `test_f024_cli.py`: todos los que sustituyen
# `PostgresClient.connection` viven juntos aquí. Son la misma técnica y el
# mismo contrato —el SQL que se envía y el mapeo de filas a objetos—, y
# separarlos obligaba a duplicar los dobles en dos ficheros.
#
# NINGUNO abre una conexión: se sustituye `PostgresClient.connection`, que es
# el único punto por el que el cliente llega a la BBDD. El doble se reutiliza
# de F-019 en vez de copiarse.
# ---------------------------------------------------------------------------


class CursorEspia(CursorFalso):
    """`CursorFalso` de F-019 que además guarda los PARÁMETROS.

    F-019 solo necesitaba saber qué SQL se enviaba. Aquí hace falta el
    contenido: el motivo del `ABORTED` lleva dentro el `batch_id` y la hora, y
    eso es precisamente lo que hay que comprobar.
    """

    def __init__(self, filas: list[tuple] | None = None) -> None:
        super().__init__(filas=filas)
        self.parametros: list[object] = []

    def execute(self, sql: str, params: object = None) -> None:
        super().execute(sql, params)
        self.parametros.append(params)


def cliente_espia(filas: list[tuple] | None = None) -> tuple[PostgresClient, CursorEspia]:
    cursor = CursorEspia(filas=filas)
    cliente, _ = cliente_con(cursor)
    return cliente, cursor


# --- R2 · `batch_id` opcional en el registro de runs -------------------------


def test_f024_r2_record_run_escribe_batch_id_si_lo_recibe() -> None:
    """`record_run_start` y `record_run_completed` estampan la ejecución."""
    batch = "20260818T020000Z-abc123"

    cliente, cursor = cliente_espia(filas=[(77,)])
    assert cliente.record_run_start("ingest", "ingest_raw.con", batch_id=batch) == 77

    assert "batch_id" in cursor.ejecutado[0]
    assert batch in cursor.parametros[0]

    cliente, cursor = cliente_espia(filas=[(88,)])
    ident = cliente.record_run_completed(
        stage="build_mart",
        step="build_mart",
        started_at=datetime(2026, 8, 18, 5, 0, 0),
        finished_at=datetime(2026, 8, 18, 5, 25, 0),
        status="SUCCESS",
        rows_processed=1_234,
        batch_id=batch,
    )

    assert ident == 88
    assert "batch_id" in cursor.ejecutado[0]
    assert batch in cursor.parametros[0]


def test_f024_r2_llamantes_sin_batch_siguen_funcionando() -> None:
    """Los llamantes anteriores a F-024 no pasan batch y escriben NULL.

    Importa porque `record_run_start` lo llaman los sub-pasos y los 60 tramos
    de `build_stg`: si el parámetro fuera obligatorio, la firma rompería a
    todos a la vez.
    """
    cliente, cursor = cliente_espia(filas=[(1,)])
    assert cliente.record_run_start("stage", "build_stg.build_obras") == 1
    assert None in cursor.parametros[0]

    cliente, cursor = cliente_espia(filas=[(2,)])
    assert (
        cliente.record_run_completed(
            stage="ingest",
            step="ingest_raw",
            started_at=datetime(2026, 8, 18, 2, 0, 0),
            finished_at=datetime(2026, 8, 18, 2, 33, 0),
            status="SUCCESS",
        )
        == 2
    )
    assert None in cursor.parametros[0]


def test_f024_r2_el_grabador_de_pasos_propaga_su_batch() -> None:
    """`PostgresStepRunRecorder` es quien estampa las filas de PASO, que son
    las que después lee `v_frescura`."""
    registradas: list[dict] = []

    class ClienteEspia:
        def record_run_completed(self, **kwargs: object) -> int:
            registradas.append(kwargs)
            return 1

    resultado = StepResult(
        step_name="build_mart",
        status=StepStatus.SUCCESS,
        started_at=datetime(2026, 8, 18, 5, 0, 0),
        finished_at=datetime(2026, 8, 18, 5, 25, 0),
        rows_processed=42,
    )

    PostgresStepRunRecorder(ClienteEspia(), "20260818T020000Z-abc123").record(
        "build_mart", resultado
    )
    assert registradas[0]["batch_id"] == "20260818T020000Z-abc123"

    # Sin batch (uso anterior a F-024) sigue grabando, con NULL.
    registradas.clear()
    PostgresStepRunRecorder(ClienteEspia()).record("build_mart", resultado)
    assert registradas[0]["batch_id"] is None
    assert registradas[0]["status"] == "SUCCESS"
    assert registradas[0]["rows_processed"] == 42


# --- R4 · La marca de huérfanas, en SQL --------------------------------------


def test_f024_r4_la_marca_actualiza_solo_filas_running() -> None:
    """Solo `RUNNING`, y el motivo lleva quién y cuándo.

    Que el `WHERE` sea exactamente `status = 'RUNNING'` no es cosmético: sin
    él, una ejecución nueva reescribiría como ABORTED el histórico entero de
    `_meta.etl_runs`, incluidos los SUCCESS de las cargas buenas.
    """
    cliente, cursor = cliente_espia(
        filas=[
            (901, "build_stg.build_plan_mensual", datetime(2026, 8, 18, 3, 10, 0)),
            (902, "build_stg.build_plan_mensual.tramo_39", datetime(2026, 8, 18, 3, 55, 0)),
        ]
    )

    marcadas = cliente.abortar_runs_huerfanos(
        "20260819T020000Z-def456", ahora=datetime(2026, 8, 19, 2, 0, 1)
    )

    consulta = cursor.ejecutado[0]
    assert re.search(r"UPDATE\s+_meta\.etl_runs", consulta, re.IGNORECASE)
    assert re.search(r"status\s*=\s*'ABORTED'", consulta, re.IGNORECASE)
    assert re.search(r"WHERE\s+status\s*=\s*'RUNNING'", consulta, re.IGNORECASE)
    assert re.search(r"RETURNING\s+id\s*,\s*step\s*,\s*started_at", consulta, re.IGNORECASE)

    # El motivo, con la ejecución que las marcó y el instante.
    parametros = cursor.parametros[0]
    assert parametros["ahora"] == datetime(2026, 8, 19, 2, 0, 1)
    assert "20260819T020000Z-def456" in parametros["motivo"]
    assert "2026-08-19 02:00:01" in parametros["motivo"]
    assert "huérfana" in parametros["motivo"]

    # Y devuelve lo marcado, para poder emitir un WARNING por fila (R4).
    assert marcadas == [
        (901, "build_stg.build_plan_mensual", datetime(2026, 8, 18, 3, 10, 0)),
        (902, "build_stg.build_plan_mensual.tramo_39", datetime(2026, 8, 18, 3, 55, 0)),
    ]


def test_f024_r4_sin_huerfanas_no_devuelve_nada() -> None:
    """La noche normal: nadie dejó filas abiertas."""
    cliente, _ = cliente_espia(filas=[])
    assert cliente.abortar_runs_huerfanos("20260819T020000Z-def456") == []


# --- R13 · Lectura del estado de `raw` ---------------------------------------


def test_f024_r13_fetch_estado_raw_mapea_filas() -> None:
    """Lee de la VISTA, no de `etl_runs`: la misma que ve el rol del MCP."""
    cliente, cursor = cliente_espia(
        filas=[
            (
                "con", "SUCCESS", "20260818T020000Z-aaaaaa",
                datetime(2026, 8, 18, 2, 0, 0), datetime(2026, 8, 18, 2, 5, 0), 12_345,
            ),
            # Una tabla que murió a medias: sin fin, sin filas y sin batch.
            ("obr", "ABORTED", None, datetime(2026, 8, 18, 2, 5, 0), None, None),
        ]
    )

    estados = cliente.fetch_estado_raw()

    assert "_meta.v_raw_state" in cursor.ejecutado[0]

    assert estados[0] == EstadoTablaRaw(
        tabla="con",
        status="SUCCESS",
        batch_id="20260818T020000Z-aaaaaa",
        started_at=datetime(2026, 8, 18, 2, 0, 0),
        finished_at=datetime(2026, 8, 18, 2, 5, 0),
        filas=12_345,
    )
    assert estados[1] == EstadoTablaRaw(
        tabla="obr",
        status="ABORTED",
        batch_id=None,
        started_at=datetime(2026, 8, 18, 2, 5, 0),
        finished_at=None,
        filas=0,
    )


def test_f024_r13_fetch_ultimo_intento_stg_coge_la_fila_de_mayor_id() -> None:
    """`ORDER BY id DESC LIMIT 1` sobre `step LIKE 'build_stg%'`.

    Por `id` y no por fecha: la fila de PASO se inserta al terminar, y su
    `started_at` es el del arranque del step, anterior al de sus sub-pasos.
    Ordenar por fecha devolvería el último tramo aunque el paso ya hubiera
    cerrado.
    """
    cliente, cursor = cliente_espia(
        filas=[
            (
                1234, "build_stg", "SUCCESS", "20260818T020000Z-aaaaaa",
                datetime(2026, 8, 18, 2, 40, 0), datetime(2026, 8, 18, 4, 30, 0),
            )
        ]
    )

    ultimo = cliente.fetch_ultimo_intento_stg()

    consulta = cursor.ejecutado[0]
    assert "build_stg%" in consulta
    assert re.search(r"ORDER\s+BY\s+id\s+DESC", consulta, re.IGNORECASE)
    assert re.search(r"LIMIT\s+1", consulta, re.IGNORECASE)

    assert ultimo == EstadoPaso(
        id=1234,
        step="build_stg",
        status="SUCCESS",
        batch_id="20260818T020000Z-aaaaaa",
        started_at=datetime(2026, 8, 18, 2, 40, 0),
        finished_at=datetime(2026, 8, 18, 4, 30, 0),
    )


def test_f024_r13_sin_filas_de_stg_no_hay_ultimo_intento() -> None:
    """`stg` nunca construido: la puerta de `mart` lo tiene que ver como KO,
    no como «no sé»."""
    cliente, _ = cliente_espia(filas=[])
    assert cliente.fetch_ultimo_intento_stg() is None


# --- R16 · Lectura de la frescura --------------------------------------------


def test_f024_r16_fetch_frescura_mapea_las_ocho_columnas() -> None:
    cliente, cursor = cliente_espia(
        filas=[
            (
                "build_mart",
                datetime(2026, 8, 18, 5, 25, 0),
                "20260818T020000Z-aaaaaa",
                987_654,
                Decimal("3.5"),
                datetime(2026, 8, 19, 2, 40, 0),
                "FAILED",
                "se acabo el disco",
            ),
            # Un paso que NUNCA terminó bien: todo el bloque de «último OK» a
            # nulo, y aun así sale (por eso el JOIN de la vista es LEFT).
            ("load_excel_aux", None, None, None, None,
             datetime(2026, 8, 19, 2, 35, 0), "RUNNING", None),
        ]
    )

    filas = cliente.fetch_frescura()

    assert "_meta.v_frescura" in cursor.ejecutado[0]

    assert filas[0] == FilaFrescura(
        paso="build_mart",
        ultimo_ok_finished_at=datetime(2026, 8, 18, 5, 25, 0),
        ultimo_ok_batch_id="20260818T020000Z-aaaaaa",
        ultimo_ok_filas=987_654,
        horas_desde_ultimo_ok=3.5,
        ultimo_intento_started_at=datetime(2026, 8, 19, 2, 40, 0),
        ultimo_intento_status="FAILED",
        ultimo_intento_error="se acabo el disco",
    )
    # Y las horas llegan como float, no como Decimal: `format_frescura` las
    # compara con un umbral entero.
    assert isinstance(filas[0].horas_desde_ultimo_ok, float)

    assert filas[1].paso == "load_excel_aux"
    assert filas[1].ultimo_ok_finished_at is None
    assert filas[1].horas_desde_ultimo_ok is None
    assert filas[1].ultimo_intento_status == "RUNNING"
