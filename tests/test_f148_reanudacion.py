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

import pytest

from etl_sigrid.domain.ejecucion import Ejecucion, ejecucion_desde_batch, nueva_ejecucion
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
        batch_id="20261023T000312Z-a1b2c3", iniciada_en=datetime(2026, 10, 23, 0, 3, 12)
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
