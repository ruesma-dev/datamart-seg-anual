# tests/test_f138_ingesta_sql.py
"""
F-138 · La ingesta de `conala` y `auxala`, el SQL de las alarmas y la marca
«liquidatoria», y su sub-paso, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f090_ingesta_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ninguna alarma de empleados entra en `raw`** (R3) y las de recursos y
   partes NO llegan a la general (R11, R14, D9).
2. **Los literales del SQL y del YAML son los del dominio** (R13): familias,
   traducción, patrones y precedencia.
3. **Lo existente no se toca** (R21): `01_` y `07_` no nombran las alarmas.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import liquidatoria as liq
from etl_sigrid.infrastructure.sigrid.bench_extraccion import construir_sql_de_pagina

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
RUTA_SQL = DIR_SQL / "15_alarmas_liquidatoria.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    corte = trozo.find("- source_table:")
    return trozo[:corte] if corte >= 0 else trozo


def _familias_de(filtro: str) -> list[int]:
    casa = re.search(r"tip IN \(([^)]*)\)", filtro)
    assert casa, f"el filtro no lleva `tip IN (...)`: {filtro!r}"
    return [int(x) for x in casa.group(1).split(",")]


# ===========================================================================
# R1-R3 · la ingesta
# ===========================================================================


def test_f138_r1_conala_filtrada_en_origen_sin_tiemod() -> None:
    conala = _tablas()["conala"]
    assert conala["target_table"] == "conala"
    assert conala["id_column"] == "ide"
    assert conala["incremental_column"] is None, "`conala` no tiene tiemod (R1)"
    assert conala["where"] == liq.filtro_conala(), "el filtro de `conala` no es el del dominio (R1)"
    assert conala["exclude_columns"] == [], "`conala` entra sin columnas excluidas (R1)"


def test_f138_r1_auxala_entera_con_tiemod() -> None:
    auxala = _tablas()["auxala"]
    assert auxala["target_table"] == "auxala"
    assert auxala["id_column"] == "ide"
    assert auxala["incremental_column"] == "tiemod"
    assert auxala["where"] is None
    assert auxala["exclude_columns"] == []


def test_f138_r1_el_comentario_de_conala_da_cifras_y_motivos() -> None:
    comentario = _comentario_de("conala").lower()
    for dato in ("f-138", "45.747", "1,79 mb", "~2 s", "d3", "43", "fallar cerrada",
                 "d9", "compras_restringida", "`fec1`", "`fec2`", "`creusu`", "login",
                 "filtro_conala()"):
        assert dato in comentario, f"el comentario de `conala` no dice «{dato}» (R1)"


def test_f138_r1_el_filtro_sale_como_lectura_hacia_sigrid() -> None:
    sql = construir_sql_de_pagina("conala", ["ide", "conide", "tex"], 10_000,
                                  where=_tablas()["conala"]["where"])
    assert sql.startswith("SELECT TOP 10000")


def test_f138_r3_la_familia_43_no_esta_en_el_filtro_de_ingesta() -> None:
    familias = _familias_de(_tablas()["conala"]["where"])
    assert liq.FAMILIA_EMPLEADOS not in familias, "las alarmas de empleados entrarían en raw (R3)"
    assert familias == sorted(liq.FAMILIAS_ALARMAS), "el filtro no es la lista explícita (R4)"
    assert "<>" not in _tablas()["conala"]["where"], "lista explícita, no exclusión (D3)"


def test_f138_r3_la_43_tampoco_en_el_sql() -> None:
    sql = _texto(RUTA_SQL)
    assert not re.search(r"\bWHEN 43\b", sql)
    for lista in re.findall(r"tip IN \(([^)]*)\)", sql):
        assert "43" not in [x.strip() for x in lista.split(",")], lista


# ===========================================================================
# R2 · el censo
# ===========================================================================


def test_f138_r2_el_censo_pasa_a_76() -> None:
    assert len(_tablas()) == 76
    assert len(_lista_tablas()) == 76, "tabla declarada dos veces"
    assert {"conala", "auxala"} <= set(_tablas())
