# tests/test_f168_diccionario.py
"""F-168 · Diccionario del texto largo (R24, R25).

Sin red ni BBDD. Lo que cada ficha tiene que decir (design §7), porque quien la
lee es un agente que no puede preguntar: el texto de la partida es uno para
todos los ámbitos; «igual a» compara el texto limpio; `recortado` es desde el
tope; los catálogos de textos se leen desde sus líneas. Y que nada de esto toca
un esquema restringido ni un permiso (D6).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICC = RAIZ / "config" / "diccionario"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"

VERSION_ANTERIOR = 81

#: Los ficheros SQL que F-168 crea o cambia.
SQL_F168 = (
    "stg/11_texto_largo.sql", "stg/12_partida_texto.sql", "compras/07_texto.sql",
    "compras/16_textos_linea.sql", "descompuestos/01_troceado.sql",
    "descompuestos/02_lineas_coste.sql", "descompuestos/03_lineas_master.sql",
)

#: Las fichas nuevas, con si se recomiendan para consulta.
FICHAS_NUEVAS = {
    ("stg", "partida_texto"): True,
    ("compras", "v_linea_texto"): True,
    ("compras", "linea_texto"): False,
    ("compras", "textos"): False,
    ("descompuestos", "textos"): False,
}


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICC / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    return _yaml(f"{esquema}.yaml")["objetos"][objeto]


def _plano(texto: object) -> str:
    return re.sub(r"\s+", " ", str(texto))


# --- R25 · versión y fichas ------------------------------------------------------


def test_f168_r25_la_version_sube() -> None:
    assert _yaml("00_global.yaml")["version"] >= VERSION_ANTERIOR + 1
    cabecera = (DIR_DICC / "00_global.yaml").read_text(encoding="utf-8").split("\nversion:", 1)[0]
    assert "# version 82 (F-168, 2026-11-23)" in cabecera


@pytest.mark.parametrize(("esquema", "objeto"), sorted(FICHAS_NUEVAS))
def test_f168_r25_ficha_de_cada_objeto_nuevo(esquema: str, objeto: str) -> None:
    ficha = _ficha(esquema, objeto)
    assert ficha["consumo_recomendado"] is FICHAS_NUEVAS[(esquema, objeto)]
    assert len(ficha.get("ejemplos_preguntas") or []) <= 2, "PRESUPUESTO_MAX (design §7)"
    assert "F-168" in _plano(ficha["descripcion"])


def test_f168_r25_partida_texto_un_texto_para_todos_los_ambitos() -> None:
    ficha = _ficha("stg", "partida_texto")
    descripcion = _plano(ficha["descripcion"])
    assert "Un texto para TODOS los ambitos" in descripcion
    assert "Solo el texto VIGENTE" in descripcion, "D9: sin historia"
    assert "16000 caracteres o mas" in _plano(ficha["columnas"]["recortado"]["significado"])


def test_f168_r25_igual_a_compara_el_texto_limpio() -> None:
    for objeto in ("linea_texto", "v_linea_texto"):
        columnas = _ficha("compras", objeto)["columnas"]
        for columna in ("igual_a_partida", "igual_a_necesidad"):
            assert "texto limpio" in _plano(columnas[columna]["significado"]), (objeto, columna)


def test_f168_r25_los_catalogos_se_leen_desde_sus_lineas() -> None:
    assert "desde `compras.linea_texto`" in _plano(_ficha("compras", "textos")["motivo_no_consumo"])
    textos = _ficha("descompuestos", "textos")
    assert "DESDE `descompuestos.lineas`" in _plano(textos["motivo_no_consumo"])
    assert "NUNCA se vacia" in _plano(textos["descripcion"])


def test_f168_r25_columna_texto_id_en_las_lineas_de_descompuestos() -> None:
    lineas = _ficha("descompuestos", "lineas")
    assert list(lineas["columnas"])[-1] == "texto_id"
    assert {"de": "texto_id", "a": "descompuestos.textos.texto_id"}.items() <= next(
        r for r in lineas["relaciones"] if r["de"] == "texto_id").items()


def test_f168_r25_las_fichas_tocadas_apuntan_al_texto() -> None:
    corta = _plano(_ficha("stg", "partidas")["columnas"]["descripcion_corta"]["significado"])
    assert "`stg.partida_texto`" in corta
    for objeto in ("contrato_lineas", "albaran_lineas", "factura_lineas",
                   "comparativo_oferta_lineas", "comparativo_lineas"):
        assert "compras.v_linea_texto" in _plano(_ficha("compras", objeto)["descripcion"]), objeto
    assert _ficha("compras", "documento_texto")["columnas"]["tipo_documento_codigo"]["valores"] == [
        12, 15, 44, 46]


# --- R24 · sin máscara y sin tocar lo restringido ---------------------------------


@pytest.mark.parametrize("fichero", SQL_F168)
def test_f168_r24_sin_permisos_ni_esquema_restringido(fichero: str) -> None:
    texto = (DIR_SQL / fichero).read_text(encoding="utf-8")
    for vetado in (r"\bGRANT\b", r"\bREVOKE\b", r"_restringida\b", r"fn_enmascarar"):
        assert not re.search(vetado, texto), (fichero, vetado)


def test_f168_r24_ninguna_ficha_restringida_nombra_el_texto() -> None:
    for ruta in sorted(DIR_DICC.glob("*_restringida.yaml")):
        texto = ruta.read_text(encoding="utf-8")
        for objeto in ("partida_texto", "linea_texto", "v_linea_texto", "texto_id"):
            assert objeto not in texto, (ruta.name, objeto)
