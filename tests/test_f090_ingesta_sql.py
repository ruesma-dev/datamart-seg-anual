# tests/test_f090_ingesta_sql.py
"""
F-090 · La ingesta de `rcg` y `gra` (filtradas en origen a las familias de
compras, sin binario) y el SQL de `compras.documento_adjuntos`, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f085_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ningún adjunto de personal entra en `raw`** (R3, R5): los dos filtros
   llevan exactamente las familias del dominio y `auxgra` no se ingiere.
2. **Ningún binario entra en el datamart** (R2, R4, R18): `ima`, `pul`, `tex` y
   `cam` fuera de la ingesta, y el SQL no nombra `ruesma_rep` ni el binario.
3. **Los literales del SQL son los del dominio** (R14): familias y extensiones.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain.documento_adjuntos import (
    COLUMNAS_EXCLUIDAS_GRA,
    FAMILIAS_ADJUNTOS,
    filtro_gra,
    filtro_rcg,
)
from etl_sigrid.infrastructure.sigrid.bench_extraccion import construir_sql_de_pagina

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str, largo: int = 4000) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    cortes = [i for i in (trozo.find("- source_table:"), trozo.find("# ====")) if i >= 0]
    return trozo[: min(cortes) if cortes else largo]


def _familias_de(filtro: str) -> set[int]:
    casa = re.search(r"tip IN \(([^)]*)\)", filtro)
    assert casa, f"el filtro no lleva `tip IN (...)`: {filtro!r}"
    return {int(x) for x in casa.group(1).split(",")}


# ===========================================================================
# A · La ingesta: R1-R6
# ===========================================================================


def test_f090_r1_rcg_filtrada_en_origen_sin_tiemod() -> None:
    rcg = _tablas()["rcg"]
    assert rcg["target_table"] == "rcg"
    assert rcg["id_column"] == "ide"
    assert rcg["incremental_column"] is None, "`rcg` no tiene tiemod (R1)"
    assert rcg["where"] == filtro_rcg(), "el filtro de `rcg` no es el del dominio (R1)"
    assert rcg["exclude_columns"] == []


def test_f090_r2_gra_filtrada_en_origen_sin_tiemod() -> None:
    gra = _tablas()["gra"]
    assert gra["target_table"] == "gra"
    assert gra["id_column"] == "ide"
    assert gra["incremental_column"] is None, "`gra` no tiene tiemod (R2)"
    assert gra["where"] == filtro_gra(), "el filtro de `gra` no es el del dominio (R2)"


def test_f090_r2_gra_excluye_exactamente_binario_y_texto_ilimitado() -> None:
    excluidas = _tablas()["gra"]["exclude_columns"]
    assert len(excluidas) == len(set(excluidas)), "columna repetida (R2)"
    assert set(excluidas) == COLUMNAS_EXCLUIDAS_GRA, (
        f"`gra` excluye {sorted(excluidas)}; lo decidido es "
        f"{sorted(COLUMNAS_EXCLUIDAS_GRA)} (R2)"
    )


def test_f090_r2_gra_va_detras_de_rcg() -> None:
    """Un enlace nuevo durante la noche trae su gráfico (design, ingesta)."""
    orden = [t["source_table"] for t in _lista_tablas()]
    assert orden.index("rcg") < orden.index("gra"), "`gra` tiene que ir DETRÁS de `rcg`"


def test_f090_r2_el_comentario_de_gra_da_el_motivo_de_cada_exclusion() -> None:
    comentario = _comentario_de("gra").lower()
    for columna in sorted(COLUMNAS_EXCLUIDAS_GRA):
        assert re.search(rf"- {columna}\b[^\n]*#", comentario), (
            f"la exclusión de `{columna}` no lleva su motivo al lado (R2)"
        )
    for dato in ("f-090", "ruesma_rep", "d2", "199.042", "41,5 s"):
        assert dato in comentario, f"el comentario de `gra` no dice «{dato}» (R2)"


def test_f090_r1_el_comentario_de_rcg_da_cifras_y_motivo() -> None:
    comentario = _comentario_de("rcg").lower()
    for dato in ("f-090", "199.042", "289.451", "7,2 s", "d2", "nominas"):
        assert dato in comentario, f"el comentario de `rcg` no dice «{dato}» (R1)"


def test_f090_r3_los_dos_filtros_llevan_exactamente_las_familias() -> None:
    for tabla in ("rcg", "gra"):
        familias = _familias_de(_tablas()[tabla]["where"])
        assert familias == set(FAMILIAS_ADJUNTOS), (
            f"`{tabla}` filtra {sorted(familias)}; el dominio dice "
            f"{sorted(FAMILIAS_ADJUNTOS)} (R3)"
        )


def test_f090_r3_los_filtros_salen_como_lectura_hacia_sigrid() -> None:
    """La página que compone la ingesta con el filtro es una lectura (R23 de F-024)."""
    for tabla in ("rcg", "gra"):
        sql = construir_sql_de_pagina(
            tabla, ["ide", "con" if tabla == "rcg" else "nom"], 10_000,
            where=_tablas()[tabla]["where"],
        )
        assert sql.startswith("SELECT TOP 10000")


def test_f090_r4_ninguna_columna_de_binario_se_ingiere() -> None:
    """Si alguna de las cuatro deja de estar excluida, el test la NOMBRA."""
    excluidas = set(_tablas()["gra"]["exclude_columns"])
    for columna in ("ima", "pul", "tex", "cam"):
        assert columna in excluidas, f"`gra.{columna}` SE INGIERE: tiene que ir excluida (R4)"


def test_f090_r5_no_se_ingiere_auxgra() -> None:
    assert "auxgra" not in _tablas(), "`auxgra` no se ingiere (D4, R5)"


def test_f090_r5_ninguna_familia_de_personal_o_posventa_en_los_filtros() -> None:
    for tabla in ("rcg", "gra"):
        familias = _familias_de(_tablas()[tabla]["where"])
        for tip in (43, 306, 708):
            assert tip not in familias, f"`{tabla}` trae la familia {tip} (D2, R5)"


def test_f090_r6_el_censo_pasa_a_74() -> None:
    assert len(_tablas()) == 74
    assert len(_lista_tablas()) == 74, "tabla declarada dos veces"
    assert {"rcg", "gra"} <= set(_tablas())
