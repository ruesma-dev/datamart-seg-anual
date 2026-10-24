# tests/test_f148_documentacion.py
"""
F-148 · Lo que se escribe de la feature (R29-R30).

Un `batch_id` deja de ser «un proceso»: abarca la ejecución del job CON su
reintento, y pueden convivir dos filas del mismo paso en un lote. Quien lea
`_meta.etl_runs` por SQL —el MCP, una persona a las 8 de la mañana— tiene que
saberlo por la ficha, y quien mantenga el ETL, por la arquitectura.

Estáticos: leen ficheros, no abren nada.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
FICHA_META = RAIZ / "config" / "diccionario" / "_meta.yaml"
GLOBAL = RAIZ / "config" / "diccionario" / "00_global.yaml"
ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"


@lru_cache(maxsize=1)
def _columnas_etl_runs() -> dict:
    doc = yaml.safe_load(FICHA_META.read_text(encoding="utf-8"))
    return doc["objetos"]["etl_runs"]["columnas"]


def _plano(texto: str) -> str:
    return " ".join(texto.split()).lower()


def test_f148_r29_batch_id_abarca_el_reintento() -> None:
    texto = _plano(_columnas_etl_runs()["batch_id"]["significado"])

    assert "reintento" in texto
    assert "dos filas del mismo paso" in texto


def test_f148_r29_step_explica_las_filas_de_permisos() -> None:
    texto = _plano(_columnas_etl_runs()["step"]["significado"])

    assert "apply_grants.tras_" in texto


def test_f148_r29_version_del_diccionario() -> None:
    assert int(yaml.safe_load(GLOBAL.read_text(encoding="utf-8"))["version"]) >= 60


def test_f148_r30_la_arquitectura_cuenta_la_nueva_ingesta() -> None:
    texto = _plano(ARQUITECTURA.read_text(encoding="utf-8"))

    for frase in (
        "una conexión por tabla",
        "connect_timeout",
        "keepalives",
        "container_app_job_execution_name",
        "apply_grants.tras_",
    ):
        assert frase in texto, f"docs/ARCHITECTURE.md no dice «{frase}»"
    assert "cada página de 10.000 filas abren su propia conexión" not in texto, (
        "el párrafo DA-8 sigue describiendo la conexión por página"
    )


def test_f148_r30_azure_apps_cuenta_lo_que_consume_del_postgres() -> None:
    if not AZURE_APPS.exists():
        pytest.skip("azure-apps no está junto a este repositorio (worktree o CI)")
    texto = _plano(AZURE_APPS.read_text(encoding="utf-8"))

    for frase in (
        "connect_timeout",
        "keepalives",
        "una conexión por tabla",
        "reanud",
        "apply_grants.tras_",
    ):
        assert frase in texto, f"azure-apps/datamart_seg_anual.md no dice «{frase}»"
