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

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from etl_sigrid.domain.coherencia import (
    EstadoPaso,
    EstadoTablaRaw,
    evaluar_coherencia_raw,
)
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.postgres.frescura import (
    MARCA_INCOHERENTE,
    UMBRAL_FRESCURA_HORAS,
    FilaFrescura,
    format_estado_raw,
    format_frescura,
)
from etl_sigrid.infrastructure.postgres.postgres_client import (
    PostgresClient,
    _split_sql_statements,
)
from etl_sigrid.infrastructure.postgres.step_run_recorder import PostgresStepRunRecorder
from etl_sigrid.infrastructure.postgres.timings import (
    UMBRAL_HUERFANA_HORAS,
    Timing,
    format_timings,
)
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


# ---------------------------------------------------------------------------
# R6 · `timings` enseña ABORTED y avisa de las RUNNING sospechosas
# ---------------------------------------------------------------------------

AHORA = datetime(2026, 8, 19, 9, 0, 0)


def medicion(
    step: str,
    status: str = "SUCCESS",
    inicio: datetime | None = None,
    fin: datetime | None = None,
) -> Timing:
    return Timing(
        stage="stage",
        step=step,
        started_at=inicio if inicio is not None else datetime(2026, 8, 19, 8, 0, 0),
        finished_at=fin,
        status=status,
        rows_processed=10,
    )


def test_f024_r6_timings_muestra_aborted() -> None:
    """`ABORTED` sale en la columna de estado como cualquier otro estado.

    Es la mitad visible de la feature: hasta ahora, una fila que quedó abierta
    seguía diciendo RUNNING para siempre y `timings` mentía.
    """
    salida = format_timings(
        [
            medicion("build_stg.build_plan_mensual", status="ABORTED",
                     fin=datetime(2026, 8, 19, 8, 30, 0)),
        ],
        ahora=AHORA,
    )

    assert "ABORTED" in salida
    assert "build_stg.build_plan_mensual" in salida


def test_f024_r6_timings_avisa_de_running_antiguas() -> None:
    """Más de 6 h en RUNNING: casi seguro huérfana de un proceso muerto."""
    salida = format_timings(
        [
            medicion("build_stg.build_plan_mensual", status="RUNNING",
                     inicio=datetime(2026, 8, 18, 3, 10, 0)),
            medicion("build_stg.build_plan_mensual.tramo_39", status="RUNNING",
                     inicio=datetime(2026, 8, 18, 3, 55, 0)),
        ],
        ahora=AHORA,
    )

    assert "2 fila" in salida, "el aviso no dice cuántas son"
    assert "RUNNING" in salida
    assert f"{UMBRAL_HUERFANA_HORAS} h" in salida
    assert "ABORTED" in salida, "el aviso no dice qué va a pasar con ellas"
    # Va al PIE, no en una columna nueva: no rompe a quien parsee la tabla.
    assert salida.splitlines()[-1].strip() != ""
    assert "AVISO" in salida.splitlines()[-1] or "AVISO" in salida.splitlines()[-2]


def test_f024_r6_timings_no_avisa_de_running_recientes() -> None:
    """Un paso que lleva media hora corriendo está, sencillamente, corriendo."""
    salida = format_timings(
        [
            medicion("build_stg", status="RUNNING",
                     inicio=datetime(2026, 8, 19, 8, 30, 0)),
        ],
        ahora=AHORA,
    )

    assert "AVISO" not in salida
    assert "RUNNING" in salida


def test_f024_r6_timings_no_avisa_de_pasos_antiguos_ya_cerrados() -> None:
    """Solo `RUNNING`. Un SUCCESS de hace tres días no es ninguna huérfana."""
    for estado_cerrado in ("SUCCESS", "FAILED", "ABORTED", "SKIPPED"):
        salida = format_timings(
            [
                medicion("build_stg", status=estado_cerrado,
                         inicio=datetime(2026, 8, 16, 2, 0, 0),
                         fin=datetime(2026, 8, 16, 4, 0, 0)),
            ],
            ahora=AHORA,
        )
        assert "AVISO" not in salida, f"avisa por un paso {estado_cerrado}"


def test_f024_r6_el_umbral_de_la_huerfana_son_seis_horas_exactas() -> None:
    """El límite es SUPERARLO, no alcanzarlo.

    Seis horas justas es una carga larga que sigue viva (el pipeline entero
    tarda ~3 h 15, pero el timeout del job es de 5 h): no se acusa de huérfana
    a algo que todavía puede estar trabajando.
    """
    assert UMBRAL_HUERFANA_HORAS == 6

    justo = AHORA - timedelta(hours=UMBRAL_HUERFANA_HORAS)
    un_poco_mas = justo - timedelta(minutes=30)

    assert "AVISO" not in format_timings(
        [medicion("build_stg", status="RUNNING", inicio=justo)], ahora=AHORA
    )
    assert "AVISO" in format_timings(
        [medicion("build_stg", status="RUNNING", inicio=un_poco_mas)], ahora=AHORA
    )


def test_f024_r6_sin_ahora_se_usa_el_reloj() -> None:
    """En producción nadie inyecta `ahora`: sale de `datetime.utcnow()`."""
    hace_un_dia = datetime.utcnow() - timedelta(days=1)
    salida = format_timings([medicion("build_stg", status="RUNNING", inicio=hace_un_dia)])
    assert "AVISO" in salida


def test_f024_r6_sin_mediciones_no_hay_aviso_que_dar() -> None:
    """El mensaje de «sin mediciones» de F-005 sigue intacto."""
    salida = format_timings([], ahora=AHORA)
    assert "Sin mediciones" in salida
    assert "AVISO" not in salida


# ---------------------------------------------------------------------------
# R19 · Formato y veredicto de frescura
# ---------------------------------------------------------------------------


def fila_frescura(
    paso: str = "build_mart",
    ultimo_ok: datetime | None = datetime(2026, 8, 19, 5, 25, 0),
    estado_intento: str = "SUCCESS",
) -> FilaFrescura:
    return FilaFrescura(
        paso=paso,
        ultimo_ok_finished_at=ultimo_ok,
        ultimo_ok_batch_id="20260819T020000Z-aaaaaa" if ultimo_ok else None,
        ultimo_ok_filas=987_654 if ultimo_ok else None,
        horas_desde_ultimo_ok=None,
        ultimo_intento_started_at=datetime(2026, 8, 19, 2, 40, 0),
        ultimo_intento_status=estado_intento,
        ultimo_intento_error=None,
    )


@pytest.mark.parametrize(
    ("horas_desde_el_ok", "esperado"),
    [
        (0.5, "FRESCO"),
        (29.9, "FRESCO"),
        (30.0, "FRESCO"),     # el límite es superarlo, no alcanzarlo
        (30.1, "CADUCADO"),
        (72.0, "CADUCADO"),
    ],
)
def test_f024_r19_format_frescura_veredictos(
    horas_desde_el_ok: float, esperado: str
) -> None:
    ultimo_ok = AHORA - timedelta(hours=horas_desde_el_ok)
    _, veredicto = format_frescura(
        [fila_frescura(ultimo_ok=ultimo_ok)],
        umbral_horas=UMBRAL_FRESCURA_HORAS,
        paso="build_mart",
        ahora=AHORA,
    )
    assert veredicto == esperado


def test_f024_r19_sin_ningun_ok_el_veredicto_lo_dice() -> None:
    """`SIN BUILD REGISTRADO` no es lo mismo que `CADUCADO`: uno significa
    «lo que ves es viejo» y el otro «no hay nada que ver»."""
    _, veredicto = format_frescura(
        [fila_frescura(ultimo_ok=None, estado_intento="FAILED")],
        umbral_horas=UMBRAL_FRESCURA_HORAS,
        paso="build_mart",
        ahora=AHORA,
    )
    assert veredicto == "SIN BUILD REGISTRADO"


def test_f024_r19_un_paso_que_no_esta_en_la_vista_no_tiene_build() -> None:
    """Preguntar por un paso que nunca corrió no es un error: es la respuesta."""
    _, veredicto = format_frescura(
        [fila_frescura(paso="build_stg")],
        umbral_horas=UMBRAL_FRESCURA_HORAS,
        paso="build_mart",
        ahora=AHORA,
    )
    assert veredicto == "SIN BUILD REGISTRADO"


def test_f024_r19_el_texto_ensena_todos_los_pasos() -> None:
    """La tabla sale entera aunque el veredicto sea de un paso: el diagnóstico
    de «mart está viejo» suele estar en la fila de `ingest_raw`."""
    texto, veredicto = format_frescura(
        [
            fila_frescura(paso="build_mart", ultimo_ok=AHORA - timedelta(hours=50)),
            fila_frescura(paso="ingest_raw", ultimo_ok=None, estado_intento="FAILED"),
        ],
        umbral_horas=UMBRAL_FRESCURA_HORAS,
        paso="build_mart",
        ahora=AHORA,
    )

    assert "build_mart" in texto
    assert "ingest_raw" in texto
    assert veredicto == "CADUCADO"
    assert "CADUCADO" in texto, "el veredicto tiene que salir también en el texto"
    assert str(UMBRAL_FRESCURA_HORAS) in texto, "no se dice contra qué umbral se juzga"
    assert "50" in texto, "no se dice cuántas horas lleva sin build"


def test_f024_r19_sin_ninguna_fila_lo_dice_en_vez_de_petar() -> None:
    texto, veredicto = format_frescura(
        [], umbral_horas=UMBRAL_FRESCURA_HORAS, paso="build_mart", ahora=AHORA
    )
    assert veredicto == "SIN BUILD REGISTRADO"
    assert texto.strip()


def test_f024_r19_umbral_por_defecto_coincide_con_dev_json() -> None:
    """El umbral vive en UN sitio conceptual y aparece en dos.

    El contenedor no lleva `infra/env/dev.json`, así que el código no puede
    leerlo en tiempo de ejecución: la constante y el fichero se escriben por
    separado y este test es lo único que impide que diverjan. Si divergen, la
    alerta de Azure vigila una ventana y `check-frescura` juzga con otra, y
    nadie se entera hasta que falta un correo.
    """
    dev = json.loads(
        (REPO_ROOT / "infra" / "env" / "dev.json").read_text(encoding="utf-8-sig")
    )
    assert dev["frescuraUmbralHoras"] == UMBRAL_FRESCURA_HORAS


# ---------------------------------------------------------------------------
# R20 · Formato del estado por tabla
# ---------------------------------------------------------------------------


def test_f024_r20_format_estado_raw_marca_las_incoherentes() -> None:
    """Una línea por tabla, y las que rompen la coherencia, señaladas.

    Sin la marca visual hay que comparar 32 batch_id a ojo, que es justo lo que
    nadie hace a las 8 de la mañana.
    """
    buena = EstadoTablaRaw(
        tabla="con", status="SUCCESS", batch_id="20260819T020000Z-aaaaaa",
        started_at=datetime(2026, 8, 19, 2, 0, 0),
        finished_at=datetime(2026, 8, 19, 2, 5, 0), filas=12_345,
    )
    muerta = EstadoTablaRaw(
        tabla="obr", status="ABORTED", batch_id=None,
        started_at=datetime(2026, 8, 19, 2, 5, 0), finished_at=None, filas=0,
    )
    vieja = EstadoTablaRaw(
        tabla="obrparpre", status="SUCCESS", batch_id="20260818T020000Z-bbbbbb",
        started_at=datetime(2026, 8, 18, 2, 0, 0),
        finished_at=datetime(2026, 8, 18, 2, 40, 0), filas=999,
    )

    veredicto = evaluar_coherencia_raw(
        [buena, muerta, vieja], ("con", "obr", "obrparpre", "obrfas")
    )
    texto = format_estado_raw([buena, muerta, vieja], veredicto)

    # Cada tabla, con su estado, su batch, su fin y sus filas.
    assert "con" in texto and "12,345" in texto
    assert "obr" in texto and "ABORTED" in texto
    assert "obrparpre" in texto and "20260818T020000Z-bbbbbb" in texto
    assert "2026-08-19 02:05" in texto

    # Con los batches MEZCLADOS van marcadas TODAS las que participan del
    # reparto, incluidas las del batch nuevo. Es deliberado: cuando hay dos
    # ejecuciones repartidas por raw no hay forma de saber cuál es la buena, y
    # marcar solo un lado sería fabricar una certeza que nadie tiene. El
    # veredicto de debajo desglosa batch por batch.
    assert _linea_de(texto, "con").startswith(MARCA_INCOHERENTE)
    assert _linea_de(texto, "obr").startswith(MARCA_INCOHERENTE)
    assert _linea_de(texto, "obrparpre").startswith(MARCA_INCOHERENTE)

    # Y cierra con el veredicto y el mensaje accionable de R9.
    assert "KO" in texto
    assert "python main.py ingest --full" in texto
    assert "obrfas" in texto, "la tabla que falta no aparece por ningún sitio"


def test_f024_r20_la_marca_discrimina_cuando_hay_una_sola_culpable() -> None:
    """Una tabla que murió a medias y el resto del mismo batch: solo ella.

    Es el contraste del test anterior. Si la marca saliera siempre en todas
    las líneas no señalaría nada, y esto lo impide.
    """
    sanas = [
        EstadoTablaRaw(
            tabla=t, status="SUCCESS", batch_id="20260819T020000Z-aaaaaa",
            started_at=datetime(2026, 8, 19, 2, 0, 0),
            finished_at=datetime(2026, 8, 19, 2, 5, 0), filas=10,
        )
        for t in ("con", "obrparpre")
    ]
    rota = EstadoTablaRaw(
        tabla="obr", status="RUNNING", batch_id="20260819T020000Z-aaaaaa",
        started_at=datetime(2026, 8, 19, 2, 5, 0), finished_at=None, filas=0,
    )

    estados = [sanas[0], rota, sanas[1]]
    texto = format_estado_raw(
        estados, evaluar_coherencia_raw(estados, ("con", "obr", "obrparpre"))
    )

    assert _linea_de(texto, "obr").startswith(MARCA_INCOHERENTE)
    assert not _linea_de(texto, "con").startswith(MARCA_INCOHERENTE)
    assert not _linea_de(texto, "obrparpre").startswith(MARCA_INCOHERENTE)


def test_f024_r20_con_todo_coherente_no_marca_nada() -> None:
    estados = [
        EstadoTablaRaw(
            tabla=t, status="SUCCESS", batch_id="20260819T020000Z-aaaaaa",
            started_at=datetime(2026, 8, 19, 2, 0, 0),
            finished_at=datetime(2026, 8, 19, 2, 5, 0), filas=10,
        )
        for t in ("con", "obr")
    ]
    veredicto = evaluar_coherencia_raw(estados, ("con", "obr"))
    texto = format_estado_raw(estados, veredicto)

    assert MARCA_INCOHERENTE not in texto
    assert "OK" in texto
    assert "--sin-puerta" not in texto


def test_f024_r20_sin_estados_lo_dice() -> None:
    """`raw` vacío: es el caso de un datamart recién creado."""
    veredicto = evaluar_coherencia_raw([], ("con",))
    texto = format_estado_raw([], veredicto)

    assert texto.strip()
    assert "KO" in texto


def _linea_de(texto: str, tabla: str) -> str:
    """La línea de la tabla pedida, sin el margen izquierdo."""
    for linea in texto.splitlines():
        if linea.strip().lstrip(MARCA_INCOHERENTE).strip().startswith(tabla.strip()):
            return linea.strip()
    pytest.fail(f"no hay línea para la tabla {tabla!r} en:\n{texto}")


def test_f024_r20_un_raw_completamente_vacio_lo_dice() -> None:
    """Datamart recién creado: ni tablas ingeridas ni tablas exigidas.

    Distinto del test anterior, donde `raw` está vacío pero el YAML sí declara
    tablas (y entonces salen como faltantes). Aquí no hay NADA que listar, y la
    tabla no puede quedarse en blanco sin explicar por qué.
    """
    veredicto = evaluar_coherencia_raw([], ())
    texto = format_estado_raw([], veredicto)

    assert "_meta.v_raw_state" in texto
    assert "vacío" in texto
    assert MARCA_INCOHERENTE not in texto
