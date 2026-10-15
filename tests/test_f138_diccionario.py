# tests/test_f138_diccionario.py
"""
F-138 · Las fichas del diccionario y los documentos (R24-R27).

Quien consulta el datamart es un agente que no puede preguntar: lo que la ficha
no diga —que la marca es TEXTO LIBRE de una alarma, que «CARTA LIQUIDACIÓN»
cierra el contrato, que sin fila es «no marcado», que `fec1`/`fec2` no son
fechas, que recursos y partes viven en `compras_restringida`— lo va a suponer.
Aquí se fija que lo dice, con las cifras medidas el 2026-10-14
(`progress/spec_F-138.md`).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import pytest
import yaml

from tests.test_f138_ingesta_sql import (
    COLUMNAS_COMPLETA,
    COLUMNAS_CONTRATO,
    COLUMNAS_GENERAL,
    COLUMNAS_LIQUIDATORIA,
    COLUMNAS_TRAS,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_CLAUDE = RAIZ / "CLAUDE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    objetos = _yaml(f"{esquema}.yaml")["objetos"]
    assert objeto in objetos, f"falta la ficha de {esquema}.{objeto}"
    return objetos[objeto]


def _texto(ficha: dict) -> str:
    return re.sub(r"\s+", " ", yaml.safe_dump(ficha, allow_unicode=True, width=10_000))


# ===========================================================================
# R24 · las fichas, con las columnas del SQL
# ===========================================================================


@pytest.mark.parametrize(
    ("esquema", "objeto", "columnas", "clave"),
    [
        ("compras", "documento_alarmas", COLUMNAS_GENERAL, ["alarma_id"]),
        ("compras_restringida", "documento_alarmas", COLUMNAS_COMPLETA, ["alarma_id"]),
        ("compras", "documento_liquidatoria", COLUMNAS_LIQUIDATORIA, ["documento_id"]),
        ("compras", "contrato_liquidacion", COLUMNAS_CONTRATO, ["contrato_id"]),
        ("compras", "facturas_tras_liquidacion", COLUMNAS_TRAS, ["contrato_id", "factura_id"]),
    ],
)
def test_f138_r24_fichas_con_las_columnas_del_sql(
    esquema: str, objeto: str, columnas: list[str], clave: list[str],
) -> None:
    ficha = _ficha(esquema, objeto)
    assert list(ficha["columnas"]) == columnas, f"{esquema}.{objeto}: columnas del SQL"
    assert ficha["clave_negocio"] == clave
    assert ficha["tipo"] == "tabla" and ficha["capa"] == "consumo"
    assert ficha["paso_etl"] == "build_compras" and ficha["refresco"] == "nocturno"
    assert ficha["ejemplos_preguntas"], "una tabla de consumo trae preguntas de ejemplo"


@pytest.mark.parametrize("funcion", ["fn_texto_normalizado", "fn_clase_liquidacion"])
def test_f138_r24_fichas_de_las_funciones(funcion: str) -> None:
    ficha = _ficha("compras", funcion)
    assert ficha["tipo"] == "funcion"
    assert ficha["consumo_recomendado"] is False
    assert "liquidatoria.py" in ficha["descripcion"]


def test_f138_r24_la_regla_en_palabras_y_el_para_que() -> None:
    marca = _texto(_ficha("compras", "documento_liquidatoria"))
    for dato in ("TEXTO LIBRE", "NEGADA > LIQUIDATORIA > CARTA_LIQUIDACION > DUDOSA > REMITE",
                 "CARTA LIQUIDACION", "IVA", "TERMINADO", "DESPUES", "sin acentos",
                 "SIN FILA AQUI = NO MARCADO", "COALESCE"):
        assert dato in marca, f"la ficha de documento_liquidatoria no dice «{dato}» (R24)"
    clase = _texto(_ficha("compras", "fn_clase_liquidacion"))
    for dato in ("LIQ", "REMITE", "NEGADA", "CARTA_LIQUIDACION", "DUDOSA", "PREVISION",
                 "HEURISTICA"):
        assert dato in clase, f"la ficha de fn_clase_liquidacion no dice «{dato}» (R24)"


def test_f138_r24_las_fechas_que_no_se_publican() -> None:
    alarmas = _texto(_ficha("compras", "documento_alarmas"))
    assert "`fec1`" in alarmas and "`fec2`" in alarmas and "NO se publican" in alarmas
    assert "fec1" not in _ficha("compras", "documento_alarmas")["columnas"]
    assert "LOGIN" in _ficha("compras", "documento_alarmas")["columnas"]["creada_por"]["significado"]


def test_f138_r24_la_general_dice_lo_que_le_falta() -> None:
    alarmas = _texto(_ficha("compras", "documento_alarmas"))
    for dato in ("recursos", "partes de trabajo", "27", "compras_restringida",
                 "R-COMPRAS-RESTRINGIDA"):
        assert dato in alarmas, f"la ficha de la general no dice «{dato}» (D9)"


def test_f138_r24_la_restringida_empieza_por_el_aviso() -> None:
    descripcion = _ficha("compras_restringida", "documento_alarmas")["descripcion"]
    assert descripcion.startswith("**ACCESO RESTRINGIDO: solo el perfil total del MCP.**")
    assert "compras.documento_alarmas" in descripcion.split("\n")[0] + descripcion[:400]
    assert "NUNCA se suman" in descripcion
    cabecera = (DIR_DICCIONARIO / "compras_restringida.yaml").read_text(encoding="utf-8")
    assert cabecera.startswith("# config/diccionario/compras_restringida.yaml")
    assert _yaml("compras_restringida.yaml")["esquema"] == "compras_restringida"


def test_f138_r24_relaciones_desde_los_documentos() -> None:
    destinos = {
        objeto: {r["a"] for r in _ficha("compras", objeto)["relaciones"]}
        for objeto in ("facturas", "albaranes", "contratos")
    }
    assert "compras.documento_liquidatoria.documento_id" in destinos["facturas"]
    assert "compras.documento_liquidatoria.documento_id" in destinos["albaranes"]
    assert "compras.contrato_liquidacion.contrato_id" in destinos["contratos"]


# ===========================================================================
# R25 · la cobertura declarada
# ===========================================================================


def test_f138_r25_cobertura_de_la_marca() -> None:
    marca = _texto(_ficha("compras", "documento_liquidatoria"))
    for dato in ("8.653", "99", "4.586", "proformas 55", "notas 0", "~5 %", "2018",
                 "2008-12-04", "458", "46", "NEGADOS", "DUDOSOS", "VER TEXTO"):
        assert dato in marca, f"la ficha de documento_liquidatoria no declara «{dato}» (R25)"


def test_f138_r25_marcas_que_se_leen_en_las_alarmas() -> None:
    alarmas = _texto(_ficha("compras", "documento_alarmas"))
    for dato in ("668", "contratos de compra (31", "comparativos (veintidos)"):
        assert dato in alarmas, f"la ficha de documento_alarmas no dice «{dato}» (R25)"


def test_f138_r29_cifras_de_los_contratos() -> None:
    contrato = _texto(_ficha("compras", "contrato_liquidacion"))
    for dato in ("5.611", "81", "722", "1.167", "5.281", "v_pbi_contrato_consumo"):
        assert dato in contrato, f"la ficha de contrato_liquidacion no dice «{dato}»"


# ===========================================================================
# R26 · 00_global.yaml y raw.yaml
# ===========================================================================


def test_f138_r26_el_esquema_restringido_en_el_global() -> None:
    esquemas = _yaml("00_global.yaml")["esquemas"]
    assert "compras_restringida" in esquemas
    assert "perfil total" in esquemas["compras_restringida"]["titulo"]
    assert esquemas["compras_restringida"]["pasos_etl"] == ["build_compras"]


def test_f138_r26_la_regla_dura() -> None:
    reglas = {r["codigo"]: r for r in _yaml("00_global.yaml")["reglas"]}
    regla = reglas["R-COMPRAS-RESTRINGIDA"]
    assert regla["severidad"] == "bloqueante"
    assert set(regla["ambito"]) == {"compras.documento_alarmas", "compras_restringida"}
    assert "compras_restringida" in regla["titulo"] and "perfil total" in regla["titulo"]
    texto = re.sub(r"\s+", " ", regla["regla"])
    assert "permission denied" in texto and "NUNCA se suman" in texto
    assert "D9" in regla["motivo"]
    hermana = reglas["R-TESORERIA-RESTRINGIDA"]
    assert hermana["severidad"] == regla["severidad"]


def test_f138_r26_version_recuento_y_pendientes() -> None:
    glob = _yaml("00_global.yaml")
    assert int(glob["version"]) >= 52, "F-138 sube la versión del diccionario"
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "version 52 (F-138" in texto
    assert "las 76 tablas" in texto
    assert glob["pendientes"] == []
    frescura = {r["codigo"]: r for r in glob["reglas"]}["R-FRESCURA"]
    assert "compras_restringida" in frescura["ambito"]


def test_f138_r26_raw_yaml() -> None:
    texto = (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")
    assert "Son 76 tablas" in texto
    conala = _texto(_ficha("raw", "conala"))
    for dato in ("F-138", "45.747", "D3", "43", "`fec1`", "`creusu`", "LOGIN",
                 "compras_restringida", "grep -n \"^| conala \" azure-apps/sigrid_tablas.md"):
        assert dato in conala, f"la ficha de raw.conala no dice «{dato}» (R26)"
    auxala = _texto(_ficha("raw", "auxala"))
    assert "INFORMATIVA" in auxala and "sigrid_tablas.md" in auxala


# ===========================================================================
# R27 · ARCHITECTURE, CLAUDE.md y azure-apps
# ===========================================================================

DATOS_DOCUMENTOS = ("76 tablas", "F-138", "`conala`", "`auxala`", "compras_restringida",
                    "compras.documento_alarmas", "compras.documento_liquidatoria",
                    "compras.contrato_liquidacion", "compras.facturas_tras_liquidacion")


def test_f138_r27_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for dato in DATOS_DOCUMENTOS:
        assert dato in texto, f"ARCHITECTURE.md no dice «{dato}» (R27)"


def test_f138_r27_claude_md() -> None:
    texto = DOC_CLAUDE.read_text(encoding="utf-8")
    for dato in ("F-138", "compras_restringida", "conala"):
        assert dato in texto, f"CLAUDE.md no dice «{dato}» (R27)"


def test_f138_r27_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for dato in DATOS_DOCUMENTOS:
        assert dato in texto, f"azure-apps no dice «{dato}» (R27)"
    assert re.search(r"mcp-bbdd[^\n]*compras_restringida|compras_restringida[^\n]*mcp-bbdd", texto), (
        "el contrato con mcp-bbdd: añadir compras_restringida a su lista blanca"
    )
