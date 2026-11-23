# tests/test_f168_ingesta.py
"""
F-168 · La ingesta del texto largo: `recortar_columnas` (R1-R4).

Seis tablas dejan de excluir `tex` y lo piden a Sigrid cortado a 16.000
caracteres y sin NUL (R1, R3); el resto de textos sigue fuera (R2); y una
declaración que no casa con el origen falla antes de crear nada (R4). Sin red
ni BBDD: esquema falso, dobles con la forma del cliente real y un transporte
HTTP simulado para el SQL de página.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
from etl_sigrid.domain.entities import ColumnSpec, TableSpec
from etl_sigrid.domain.texto_largo import TOPE_CARACTERES, expresion_recorte
from etl_sigrid.infrastructure.postgres.sesion_carga import MedidaPagina
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import SigridApiClient, SigridApiError

RAIZ = Path(__file__).resolve().parents[1]
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"

#: Las seis tablas que ingieren su `tex` (R1).
SEIS = ("obrparpar", "dncpro", "dcopro", "ctrpro", "dcapro", "dcfpro")

#: Cabeceras y textos que siguen fuera (R2).
CABECERAS = ("dco", "ctr", "dca", "dcf", "com", "obrctr")
OTROS_TEXTOS = ("obs", "desesp", "texcom", "dirtex", "emptex", "eiotex", "texobs")


def _tablas() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


def _col(nombre: str) -> ColumnSpec:
    return ColumnSpec(nombre, "text" if nombre == "tex" else "int", None, 10, 0, True)


class _ApiFalsa:
    def __init__(self, columnas: list[str]) -> None:
        self._columnas = columnas
        self.pedidas: list[str] | None = None
        self.recortes: dict | None = None

    def fetch_table_schema(self, source_table: str, schema: str = "dbo") -> list[ColumnSpec]:
        return [_col(c) for c in self._columnas]

    def stream_table(self, source_table, *, columns, id_column="ide", where=None,
                     schema="dbo", start_id=0, page_size=None, recortes=None):
        self.pedidas = list(columns)
        self.recortes = recortes
        yield [{c: 1 for c in columns}]


class _PgFalso:
    def __init__(self) -> None:
        self.traza: list[str] = []
        self.columnas_creadas: list[str] | None = None

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
# R1 · R2 · el YAML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabla", SEIS)
def test_f168_r1_las_seis_tablas_ingieren_tex_recortado(tabla: str) -> None:
    cfg = _tablas()[tabla]
    assert "tex" not in (cfg.get("exclude_columns") or []), f"{tabla} sigue excluyendo tex"
    assert cfg.get("recortar_columnas") == {"tex": TOPE_CARACTERES}, (
        f"{tabla} debe declarar recortar_columnas: {{tex: {TOPE_CARACTERES}}} (R1)"
    )


def test_f168_r2_solo_las_seis_declaran_recorte() -> None:
    con_recorte = {n for n, c in _tablas().items() if c.get("recortar_columnas")}
    assert con_recorte == set(SEIS)


@pytest.mark.parametrize("tabla", CABECERAS)
def test_f168_r2_las_cabeceras_siguen_sin_tex(tabla: str) -> None:
    cfg = _tablas()[tabla]
    assert "tex" in (cfg.get("exclude_columns") or []), f"{tabla} no debe ingerir tex (R2)"


@pytest.mark.parametrize("tabla", SEIS)
def test_f168_r2_los_demas_textos_de_las_seis_siguen_fuera(tabla: str) -> None:
    excluidas = set(_tablas()[tabla].get("exclude_columns") or [])
    assert "med" in excluidas and "des" in excluidas, tabla
    if tabla != "obrparpar":
        assert set(OTROS_TEXTOS) <= excluidas, f"{tabla} deja de excluir algún texto (R2)"


# ---------------------------------------------------------------------------
# R4 · la validación, antes de crear nada
# ---------------------------------------------------------------------------


def test_f168_r4_table_spec_sin_recortes_por_defecto() -> None:
    assert TableSpec(source_table="x", target_table="x").recortar_columnas == {}


def test_f168_r4_el_yaml_llega_a_la_spec() -> None:
    spec = _paso()._build_table_spec(
        {"source_table": "dcfpro", "target_table": "dcfpro", "recortar_columnas": {"tex": 16000}}
    )
    assert spec.recortar_columnas == {"tex": 16000}


def test_f168_r4_la_ingesta_pasa_los_recortes_a_sigrid() -> None:
    api = _ApiFalsa(["ide", "res", "tex", "med"])
    pg = _PgFalso()
    spec = TableSpec(source_table="dcfpro", target_table="dcfpro", exclude_columns=["med"],
                     recortar_columnas={"tex": 16000})

    assert _paso()._ingest_one_table(spec, api, pg) == 1
    assert pg.columnas_creadas == ["ide", "res", "tex"]
    assert api.recortes == {"tex": 16000}


def test_f168_r4_sin_recortes_no_cambia_nada() -> None:
    api = _ApiFalsa(["ide", "res"])
    pg = _PgFalso()
    _paso()._ingest_one_table(TableSpec(source_table="x", target_table="x"), api, pg)
    assert not api.recortes


@pytest.mark.parametrize(
    ("spec_kw", "mensaje"),
    [
        ({"exclude_columns": ["tex"], "recortar_columnas": {"tex": 16000}}, "excluida"),
        ({"recortar_columnas": {"txt": 16000}}, "no existe en Sigrid"),
        ({"include_columns": ("ide", "res"), "recortar_columnas": {"tex": 16000}},
         "include_columns"),
        ({"recortar_columnas": {"tex": 0}}, "entero positivo"),
        ({"recortar_columnas": {"tex": -5}}, "entero positivo"),
        ({"recortar_columnas": {"tex": "16000"}}, "entero positivo"),
        ({"recortar_columnas": {"tex": True}}, "entero positivo"),
        ({"recortar_columnas": {"tex": 1.5}}, "entero positivo"),
    ],
)
def test_f168_r4_recorte_mal_declarado_falla_antes_de_crear_nada(
    spec_kw: dict, mensaje: str
) -> None:
    api = _ApiFalsa(["ide", "res", "tex"])
    pg = _PgFalso()
    spec = TableSpec(source_table="dcfpro", target_table="dcfpro", **spec_kw)

    with pytest.raises(SigridApiError, match=mensaje) as error:
        _paso()._ingest_one_table(spec, api, pg)

    assert "dcfpro" in str(error.value)
    columna = next(iter(spec.recortar_columnas))
    assert columna in str(error.value)
    assert "ensure" not in pg.traza and "truncate" not in pg.traza, "no se crea ni vacía nada"
    assert pg.traza == ["fin FAILED"]


# ---------------------------------------------------------------------------
# R3 · el SQL de página
# ---------------------------------------------------------------------------


def _cliente_que_graba(sql_enviadas: list[str]) -> SigridApiClient:
    def responder(peticion: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(peticion.content)
        sql_enviadas.append(cuerpo["sql"])
        return httpx.Response(
            200,
            json={"ok": True, "columns": ["ide", "res", "tex"],
                  "rows": [[1, "a", "b"]], "row_count": 1},
        )

    cliente = SigridApiClient(base_url="http://sigrid.invalid", function_key="k",
                              database="d", page_size=5)
    cliente._client = httpx.Client(transport=httpx.MockTransport(responder),  # noqa: SLF001
                                   base_url="http://sigrid.invalid")
    return cliente


def test_f168_r3_stream_table_pide_la_columna_recortada() -> None:
    enviadas: list[str] = []
    cliente = _cliente_que_graba(enviadas)
    paginas = list(cliente.stream_table("dcfpro", columns=["ide", "res", "tex"],
                                        recortes={"tex": 16000}))

    assert paginas == [[{"ide": 1, "res": "a", "tex": "b"}]]
    assert enviadas[0].startswith(
        "SELECT TOP 5 [ide], [res], " + expresion_recorte("tex", 16000) + " FROM [dbo].[dcfpro] "
    )


def test_f168_r3_sin_recortes_el_sql_es_el_de_siempre() -> None:
    enviadas: list[str] = []
    cliente = _cliente_que_graba(enviadas)
    list(cliente.stream_table("dcfpro", columns=["ide", "res", "tex"]))
    assert enviadas[0].startswith("SELECT TOP 5 [ide], [res], [tex] FROM [dbo].[dcfpro] ")


def test_f168_r3_recorte_de_una_columna_que_no_se_pide_falla() -> None:
    cliente = _cliente_que_graba([])
    with pytest.raises(ValueError, match="tex"):
        list(cliente.stream_table("dcfpro", columns=["ide", "res"], recortes={"tex": 16000}))
