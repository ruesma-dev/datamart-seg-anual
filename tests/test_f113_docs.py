# tests/test_f113_docs.py
"""
F-113 · La documentación de la categoría dice la regla nueva (R14, R15).

Una ficha que describe la regla de antes no es documentación incompleta: es una
afirmación falsa, y quien la lee es un agente que no puede preguntar. Aquí se
fija que el diccionario (`stg`, `mart`, `raw`, versión 41), el `README.md` y el
comentario de `auxobrtca` en `config/tables_sigrid.yaml` dejaron de hablar de la
«heurística sobre el código del capítulo raíz» y explican lo que hay: el
capítulo CD/CI/CP más cercano, la raíz por prefijo y el intermedio por código
exacto; y que Sigrid no trae la marca (`tcaide` = 0, `auxobrtca` son oficios).

Se leen los ficheros por su ruta y sin base de datos.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from tests._texto import contiene, normalizado

RAIZ = Path(__file__).resolve().parents[1]
DICCIONARIO = RAIZ / "config" / "diccionario"

#: Las seis columnas `categoria` publicadas en `mart` (design §4).
OBJETOS_MART_CON_CATEGORIA = (
    "fact_seguimiento_mensual",
    "fact_seguimiento_categoria",
    "v_pbi_fact_categoria",
    "v_pbi_dim_partida",
    "v_pbi_dim_partida_niveles",
    "v_fact_periodificado",
)


@cache
def _texto(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load(_texto(DICCIONARIO / nombre))


def _significado(columna: object) -> str:
    if isinstance(columna, dict):
        return str(columna.get("significado", ""))
    return str(columna)


def _bajo(texto: str) -> str:
    return normalizado(texto).lower()


def _seccion(texto: str, desde: str, hasta: str) -> str:
    inicio = texto.index(desde)
    return texto[inicio : texto.index(hasta, inicio)]


# ---------------------------------------------------------------------------
# R14 · el diccionario
# ---------------------------------------------------------------------------


def test_f113_r14_la_version_del_diccionario_sube_a_41_con_su_nota():
    assert _yaml("00_global.yaml")["version"] >= 41
    assert re.search(r"^# version 41 \(F-113", _texto(DICCIONARIO / "00_global.yaml"), re.M), (
        "falta la nota de la version 41 en la cabecera de 00_global.yaml"
    )


def test_f113_r14_stg_la_nota_4_de_cabecera_dice_la_regla_nueva():
    cabecera = _texto(DICCIONARIO / "stg.yaml").split("\nversion:")[0]
    nota = _bajo(_seccion(cabecera, "# 4.", "# 5."))

    assert "heuristica" not in nota
    assert "mas cercano" in nota
    assert "prefijo" in nota and "exacto" in nota


@pytest.mark.parametrize("columna", ("categoria", "capitulo_raiz_cod"))
def test_f113_r14_stg_las_fichas_de_partidas_dejan_la_heuristica(columna: str):
    texto = _bajo(_significado(_yaml("stg.yaml")["objetos"]["partidas"]["columnas"][columna]))

    assert "heuristica" not in texto, f"stg.partidas.{columna} sigue diciendo HEURISTICA"
    assert "entrada" not in texto, f"stg.partidas.{columna} sigue llamándose la ENTRADA"


def test_f113_r14_stg_la_categoria_explica_el_mas_cercano():
    texto = _bajo(_significado(_yaml("stg.yaml")["objetos"]["partidas"]["columnas"]["categoria"]))

    assert "mas cercano" in texto
    assert "prefijo" in texto and "exactamente" in texto
    assert "tcaide" in texto, "no dice que Sigrid no trae la marca"


def test_f113_r14_stg_el_codigo_raiz_es_informativo():
    texto = _bajo(
        _significado(_yaml("stg.yaml")["objetos"]["partidas"]["columnas"]["capitulo_raiz_cod"])
    )
    assert "informativo" in texto


@pytest.mark.parametrize("objeto", OBJETOS_MART_CON_CATEGORIA)
def test_f113_r14_mart_las_seis_categorias_dicen_la_regla_nueva(objeto: str):
    columnas = _yaml("mart.yaml")["objetos"][objeto]["columnas"]
    texto = _bajo(_significado(columnas["categoria"]))

    assert "heuristica" not in texto, f"mart.{objeto}.categoria sigue diciendo heuristica"
    assert "mas cercano" in texto, f"mart.{objeto}.categoria no dice el CD/CI/CP mas cercano"


def test_f113_r14_raw_auxobrtca_deja_de_ser_el_catalogo_bueno():
    ficha = _yaml("raw.yaml")["objetos"]["auxobrtca"]
    texto = _bajo(str(ficha["descripcion"]) + " " + str(ficha.get("motivo_no_consumo", "")))

    assert "catalogo oficial" not in texto
    assert "catalogo bueno" not in texto
    assert "heuristica" not in texto
    assert "tcaide" in texto
    assert contiene(texto, "tres oficios")


def test_f113_r14_raw_obrparpar_cita_tcaide():
    texto = _bajo(str(_yaml("raw.yaml")["objetos"]["obrparpar"]["descripcion"]))

    assert "heuristica" not in texto
    assert "tcaide" in texto


# ---------------------------------------------------------------------------
# R15 · el README y el comentario de `tables_sigrid.yaml`
# ---------------------------------------------------------------------------


def test_f113_r15_readme_6_3_explica_la_regla_nueva():
    seccion = _seccion(_texto(RAIZ / "README.md"), "### 6.3", "### 6.4")
    bajo = _bajo(seccion)

    assert "LIKE '%CD%'" not in seccion, "§6.3 sigue enseñando la regla vieja"
    assert "prefijo" in bajo
    assert "exacto" in bajo or "exactamente" in bajo
    assert "más cercano" in bajo


def test_f113_r15_readme_5_3_1_deja_la_heuristica():
    seccion = _bajo(_seccion(_texto(RAIZ / "README.md"), "#### 5.3.1", "#### 5.3.2"))

    assert "heurística sobre el código del raíz" not in seccion
    assert "derivado del código del raíz" not in seccion
    assert "tcaide" in seccion


def test_f113_r15_el_comentario_de_auxobrtca_cita_tcaide():
    texto = _texto(RAIZ / "config" / "tables_sigrid.yaml")
    bloque = _bajo(_seccion(texto, "- source_table: auxobrtca", "# ====="))

    assert "sin depender de heurísticas" not in bloque
    assert "tcaide" in bloque
    assert "oficios" in bloque
