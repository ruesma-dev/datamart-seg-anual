# tests/test_f006_raw_ingesta.py
"""
Lo que las fichas de `raw` dicen de la INGESTA se contrasta con la ingesta (T25).

Las fichas de `raw` afirman dos cosas que no están en el SQL sino en
`config/tables_sigrid.yaml`: si la tabla se carga **incremental por `tiemod`** o
se recarga entera cada noche, y **qué columnas no se traen**.

Las dos son afirmaciones caras de equivocar y baratas de derivar. La segunda,
además, es de las que no fallan con un dato raro: preguntar en `raw` por una
columna excluida no devuelve nulo, devuelve «columna inexistente».

Escribiéndolas a mano se me quedaron dos sin decir —`raw.con` es incremental y
`raw.conext` se recarga entera— y ninguna comprobación lo habría notado. Este
fichero cierra ese hueco para siempre, y de paso obliga a que una tabla nueva
declare cómo se carga.
"""

from __future__ import annotations

import pathlib
import re
from functools import lru_cache

import pytest
import yaml

RAIZ = pathlib.Path(__file__).resolve().parents[1]
FICHERO_RAW = RAIZ / "config" / "diccionario" / "raw.yaml"
FICHERO_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"

#: Cómo dice una ficha que la carga es incremental, y cómo que es completa. Son
#: frases fijas justamente para poder comprobarlas.
FRASE_INCREMENTAL = "incremental por `tiemod`"
FRASES_COMPLETA = ("recarga entera", "recarga entero")


@lru_cache(maxsize=1)
def _ingesta() -> dict[str, dict]:
    datos = yaml.safe_load(FICHERO_TABLAS.read_text(encoding="utf-8"))
    return {t["source_table"]: t for t in datos["tables"]}


@lru_cache(maxsize=1)
def _fichas() -> dict[str, dict]:
    return yaml.safe_load(FICHERO_RAW.read_text(encoding="utf-8"))["objetos"]


def _nombres() -> list[str]:
    return sorted(_fichas())


def test_f006_r26_hay_una_ficha_por_tabla_ingerida() -> None:
    """Ni de más ni de menos: `raw` es exactamente lo que se ingiere."""
    assert set(_fichas()) == set(_ingesta())


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r13_la_ficha_dice_como_se_carga_la_tabla(nombre: str) -> None:
    """Incremental o completa, pero dicho, y dicho bien."""
    texto = _fichas()[nombre]["descripcion"]
    incremental = _ingesta()[nombre]["incremental_column"] == "tiemod"

    dice_incremental = FRASE_INCREMENTAL in texto
    dice_completa = any(f in texto for f in FRASES_COMPLETA)

    assert dice_incremental != dice_completa, (
        f"la ficha de raw.{nombre} tiene que decir UNA de las dos cosas: que la "
        f"carga es «{FRASE_INCREMENTAL}» o que se «recarga entera» cada noche"
    )
    assert dice_incremental == incremental, (
        f"raw.{nombre} se carga "
        f"{'incremental por tiemod' if incremental else 'entera cada noche'} "
        f"según config/tables_sigrid.yaml, y su ficha dice lo contrario"
    )


@pytest.mark.parametrize("nombre", _nombres())
def test_f006_r26_las_columnas_que_la_ficha_da_por_excluidas_lo_estan(
    nombre: str,
) -> None:
    """Citar una columna como no traída cuando sí se trae es peor que callar.

    No se exige que la ficha las liste todas —hay tablas con veinticinco
    exclusiones y listarlas no aporta—, pero **lo que cite tiene que ser
    cierto**.
    """
    texto = _fichas()[nombre]["descripcion"]
    citadas: set[str] = set()
    for trozo in re.findall(r"\*\*No se traen?\*\* (.+?)\.", texto, re.S):
        citadas |= set(re.findall(r"`(\w+)`", trozo))

    excluidas = set(_ingesta()[nombre]["exclude_columns"])
    assert citadas <= excluidas, (
        f"la ficha de raw.{nombre} dice que no se traen "
        f"{sorted(citadas - excluidas)}, y esas columnas SÍ se ingieren"
    )
