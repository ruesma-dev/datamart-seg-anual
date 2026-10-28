# tests/test_f150_ingesta.py
"""
F-150 · La ingesta con lista blanca (`include_columns`, R17) y las dos tablas
nuevas de `raw`: el catálogo `iva` y la CABECERA de `dvf` (R16).

`dvf` tiene 151 columnas en Sigrid (medido en T1, `progress/impl_F-150.md` §3)
y el hueco de facturación de H26 solo necesita nueve: el ingestor solo sabía
EXCLUIR, así que gana una lista blanca. Sin red ni BBDD: esquema falso y
dobles con la forma del cliente real.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
from etl_sigrid.domain.entities import ColumnSpec, TableSpec
from etl_sigrid.infrastructure.postgres.sesion_carga import MedidaPagina
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiError

RAIZ = Path(__file__).resolve().parents[1]
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
FICHERO_RAW = RAIZ / "config" / "diccionario" / "raw.yaml"

#: La cabecera de `dvf` que necesita el hueco de H26 (`design.md` §5.1).
COLUMNAS_DVF = ("ide", "cla", "entide", "cenide", "ctride", "fecdoc", "totbas", "totiva", "totdoc")


def _col(nombre: str) -> ColumnSpec:
    return ColumnSpec(nombre, "int", None, 10, 0, True)


class _ApiFalsa:
    """Imita `SigridApiClient` en lo que usa la ingesta: esquema y páginas."""

    def __init__(self, columnas: list[str]) -> None:
        self._columnas = columnas
        self.pedidas: list[str] | None = None

    def fetch_table_schema(self, source_table: str, schema: str = "dbo") -> list[ColumnSpec]:
        return [_col(c) for c in self._columnas]

    def stream_table(self, source_table, *, columns, id_column="ide", where=None,
                     schema="dbo", start_id=0, page_size=None):
        self.pedidas = list(columns)
        yield [{c: 1 for c in columns}]


class _PgFalso:
    """Imita `PostgresClient` en lo que usa `_ingest_one_table`."""

    def __init__(self) -> None:
        self.traza: list[str] = []
        self.columnas_creadas: list[str] | None = None
        self.columnas_copiadas: list[str] | None = None

    def record_run_start(self, stage, step, batch_id=None) -> int:
        return 1

    def record_run_end(self, run_id, status, rows_processed=0, error_message=None) -> None:
        self.traza.append(f"fin {status}")

    def ensure_raw_table(self, target_table, columns, *, primary_key="ide") -> None:
        self.traza.append("ensure")
        self.columnas_creadas = [c.name for c in columns]

    def truncate_table(self, schema, table) -> None:
        self.traza.append("truncate")

    def get_max_id(self, schema, table, id_column="ide") -> int:
        return 0

    @contextmanager
    def sesion_de_carga(self, schema, table, columns, *, id_column, tiemod_column=None):
        self.columnas_copiadas = list(columns)
        traza = self.traza

        class _Sesion:
            def copiar_pagina(self, filas):
                traza.append("copy")
                return MedidaPagina(filas=len(filas), copy_s=0.0, pg_connect_s=0.0, reintentos=0)

        yield _Sesion()


def _paso() -> IngestRawStep:
    ajustes = SimpleNamespace(sigrid_api=SimpleNamespace(page_size=10_000))
    return IngestRawStep(ajustes, full_refresh=True, batch_id="b")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# R17 · la lista blanca
# ---------------------------------------------------------------------------


def test_f150_r17_table_spec_tiene_include_columns_vacio_por_defecto() -> None:
    spec = TableSpec(source_table="x", target_table="x")
    assert spec.include_columns == ()


def test_f150_r17_la_ingesta_trae_solo_las_incluidas_en_el_orden_de_sigrid() -> None:
    api = _ApiFalsa(["ide", "cla", "tex", "cenide", "pagtex", "totbas"])
    pg = _PgFalso()
    spec = TableSpec(source_table="dvf", target_table="dvf",
                     include_columns=("totbas", "ide", "cenide"))

    filas = _paso()._ingest_one_table(spec, api, pg)

    assert filas == 1
    assert pg.columnas_creadas == ["ide", "cenide", "totbas"]
    assert pg.columnas_copiadas == ["ide", "cenide", "totbas"]
    assert api.pedidas == ["ide", "cenide", "totbas"], "a Sigrid solo se piden las incluidas"


def test_f150_r17_sin_lista_blanca_la_ingesta_no_cambia() -> None:
    api = _ApiFalsa(["ide", "cla", "tex"])
    pg = _PgFalso()
    spec = TableSpec(source_table="x", target_table="x", exclude_columns=["tex"])

    _paso()._ingest_one_table(spec, api, pg)

    assert pg.columnas_creadas == ["ide", "cla"]


def test_f150_r17_incluir_y_excluir_a_la_vez_falla_antes_de_crear_nada() -> None:
    api = _ApiFalsa(["ide", "cla", "tex"])
    pg = _PgFalso()
    spec = TableSpec(source_table="dvf", target_table="dvf",
                     include_columns=("ide", "cla"), exclude_columns=["tex"])

    with pytest.raises(SigridApiError, match="include_columns y exclude_columns"):
        _paso()._ingest_one_table(spec, api, pg)

    assert "ensure" not in pg.traza and "truncate" not in pg.traza
    assert pg.traza == ["fin FAILED"], "el tramo queda FAILED en `_meta`"


def test_f150_r17_una_incluida_que_no_existe_en_sigrid_falla_antes_de_crear_nada() -> None:
    api = _ApiFalsa(["ide", "cla"])
    pg = _PgFalso()
    spec = TableSpec(source_table="dvf", target_table="dvf",
                     include_columns=("ide", "cla", "totbas", "obride"))

    with pytest.raises(SigridApiError, match=r"no existen en Sigrid: \['obride', 'totbas'\]"):
        _paso()._ingest_one_table(spec, api, pg)

    assert "ensure" not in pg.traza and "truncate" not in pg.traza


def test_f150_r17_build_table_spec_lee_include_columns_del_yaml() -> None:
    paso = _paso()
    spec = paso._build_table_spec(
        {"source_table": "dvf", "target_table": "dvf", "include_columns": ["ide", "totbas"]}
    )
    assert spec.include_columns == ("ide", "totbas")
    assert paso._build_table_spec({"source_table": "x", "target_table": "x"}).include_columns == ()


# ---------------------------------------------------------------------------
# R16 · las dos tablas nuevas en `config/tables_sigrid.yaml`
# ---------------------------------------------------------------------------


def _ingesta() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


def test_f150_r16_iva_entera_y_sin_tiemod() -> None:
    iva = _ingesta()["iva"]
    assert iva["target_table"] == "iva" and iva["id_column"] == "ide"
    assert iva["incremental_column"] is None, "medido en T1: `iva` no tiene tiemod"
    assert iva["exclude_columns"] == [] and "include_columns" not in iva
    assert iva.get("where") is None


def test_f150_r16_dvf_solo_la_cabecera_y_sin_tiemod() -> None:
    dvf = _ingesta()["dvf"]
    assert dvf["target_table"] == "dvf" and dvf["id_column"] == "ide"
    assert dvf["incremental_column"] is None, "medido en T1: `dvf` no tiene tiemod"
    assert tuple(dvf["include_columns"]) == COLUMNAS_DVF
    assert not dvf.get("exclude_columns"), "lista blanca o negra, nunca las dos (R17)"
    assert dvf.get("where") is None, "todas las facturas: rectificativas incluidas"


def test_f150_r16_solo_dvf_usa_lista_blanca() -> None:
    con_lista = sorted(n for n, t in _ingesta().items() if t.get("include_columns"))
    assert con_lista == ["dvf"]


@pytest.mark.parametrize("tabla", ["iva", "dvf"])
def test_f150_r16_cada_tabla_nueva_tiene_su_ficha_en_raw(tabla: str) -> None:
    fichas = yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]
    assert tabla in fichas
    texto = fichas[tabla]["descripcion"]
    assert "F-150" in texto


def test_f150_r16_la_ficha_de_dvf_dice_que_solo_trae_la_cabecera() -> None:
    fichas = yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]
    texto = fichas["dvf"]["descripcion"]
    assert "Solo se traen 9" in texto
    for columna in COLUMNAS_DVF:
        assert f"`{columna}`" in texto, columna
