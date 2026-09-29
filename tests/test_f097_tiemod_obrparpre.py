# tests/test_f097_tiemod_obrparpre.py
"""
F-097 · R29: `obrparpre` no tiene `tiemod`, y la ingesta no puede afirmar lo
contrario.

Medido por el spec-author el 2026-09-27 contra `INFORMATION_SCHEMA` de Sigrid:
`obrparpre` tiene 22 columnas y ninguna es `tiemod`. La entrada de
`config/tables_sigrid.yaml` la declaraba como `incremental_column`, y la
ingesta la degradaba a `None` en silencio (`ingest_raw_step.py`, al elegir
`tiemod_col`), asi que `raw.obrparpre._source_tiemod` quedaba a NULL. Mismo
arreglo que F-074 con `com`/`comlin`/`comprv`. Las otras 13 tablas con el mismo
defecto son F-115 (D14), fuera de esta feature.
"""

from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
YAML_INGESTA = RAIZ / "config" / "tables_sigrid.yaml"


def _entrada_y_bloque(tabla: str) -> tuple[dict, str]:
    texto = YAML_INGESTA.read_text(encoding="utf-8")
    entradas = {t["source_table"]: t for t in yaml.safe_load(texto)["tables"]}
    inicio = texto.index(f"  - source_table: {tabla}\n")
    fin = texto.find("\n  - source_table:", inicio + 10)
    return entradas[tabla], texto[inicio: fin if fin != -1 else len(texto)]


def test_f097_r29_obrparpre_no_declara_tiemod() -> None:
    entrada, _ = _entrada_y_bloque("obrparpre")
    assert entrada["incremental_column"] is None, (
        "obrparpre no tiene tiemod en Sigrid (22 columnas, medido el 2026-09-27)"
    )


def test_f097_r29_el_comentario_dice_lo_medido() -> None:
    _, bloque = _entrada_y_bloque("obrparpre")
    for dato in ("22 columnas", "tiemod", "_source_tiemod", "ingest_raw_step.py:279",
                 "2026-09-27", "F-115"):
        assert dato in bloque, f"el comentario de obrparpre no dice «{dato}»"


def test_f097_r29_lo_demas_de_la_entrada_no_cambia() -> None:
    entrada, _ = _entrada_y_bloque("obrparpre")
    assert entrada["target_table"] == "obrparpre"
    assert entrada["id_column"] == "ide"
    assert entrada["where"] is None
    assert entrada["exclude_columns"] == ["tex", "med", "des"]
    assert entrada["page_size"] == 5000


def test_f097_r29_la_ingesta_sin_tiemod_no_escribe_source_tiemod() -> None:
    """Con `incremental_column: null` el paso no pide `_source_tiemod` al COPY."""
    from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep

    entrada, _ = _entrada_y_bloque("obrparpre")
    spec = IngestRawStep._build_table_spec(None, entrada)  # type: ignore[arg-type]
    assert spec.incremental_column is None
