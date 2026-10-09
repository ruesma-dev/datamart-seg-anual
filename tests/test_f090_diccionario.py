# tests/test_f090_diccionario.py
"""
F-090 · Las fichas del diccionario y los documentos (R19-R25).

Quien consulta el datamart es un agente que no puede preguntar: lo que la ficha
no diga —que la AUSENCIA de fila es «Sigrid no tiene adjunto», que el fichero
está en `ruesma_rep` y no aquí, que la clase sale de la extensión, que
`subido_por` es un login— lo va a suponer. Aquí se fija que lo dice, con las
cifras medidas el 2026-10-09 (`progress/spec_F-090.md`).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import pytest
import yaml

from etl_sigrid.domain.documento_adjuntos import EXTENSIONES_POR_CLASE, FAMILIAS_ADJUNTOS

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_ARQUITECTURA = RAIZ / "docs" / "ARCHITECTURE.md"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

COLUMNAS = [
    "adjunto_id", "documento_id", "tipo_documento_codigo", "familia",
    "codigo_documento", "comparativo_id", "grafico_id", "cod_repositorio",
    "empresa_repositorio", "nombre_fichero", "extension", "clase_fichero",
    "descripcion", "fecha_alta", "subido_por", "posicion",
]

#: Las fichas de los documentos que apuntan al índice, con su clave.
DOCUMENTOS = {
    "facturas": "factura_id",
    "contratos": "contrato_id",
    "comparativos": "comparativo_id",
    "comparativo_ofertas": "oferta_id",
    "albaranes": "albaran_id",
}


@cache
def _yaml(nombre: str) -> dict:
    return yaml.safe_load((DIR_DICCIONARIO / nombre).read_text(encoding="utf-8"))


def _ficha(esquema: str, objeto: str) -> dict:
    objetos = _yaml(f"{esquema}.yaml")["objetos"]
    assert objeto in objetos, f"falta la ficha de {esquema}.{objeto}"
    return objetos[objeto]


def _texto(ficha: dict) -> str:
    return yaml.safe_dump(ficha, allow_unicode=True, width=10_000)


def _adjuntos() -> dict:
    return _ficha("compras", "documento_adjuntos")


# ===========================================================================
# R19-R23 · `compras.documento_adjuntos`
# ===========================================================================


def test_f090_r19_la_ficha_existe_con_su_grano_y_su_clave() -> None:
    ficha = _adjuntos()
    assert ficha["tipo"] == "tabla"
    assert ficha["capa"] == "consumo"
    assert ficha["consumo_recomendado"] is True
    assert ficha["clave_negocio"] == ["adjunto_id"]
    assert ficha["paso_etl"] == "build_compras"
    assert ficha["refresco"] == "nocturno"
    assert "enlace" in ficha["grano"].lower()
    for familia in FAMILIAS_ADJUNTOS.values():
        assert familia in ficha["grano"], f"el grano no nombra {familia}"


def test_f090_r19_todas_las_columnas_en_su_orden() -> None:
    assert list(_adjuntos()["columnas"]) == COLUMNAS


def test_f090_r19_valores_de_familia_y_clase_son_los_del_dominio() -> None:
    columnas = _adjuntos()["columnas"]
    assert set(columnas["familia"]["valores"]) == set(FAMILIAS_ADJUNTOS.values())
    assert set(columnas["tipo_documento_codigo"]["valores"]) == set(FAMILIAS_ADJUNTOS)
    assert set(columnas["clase_fichero"]["valores"]) == (
        set(EXTENSIONES_POR_CLASE) | {"OTRO", "SIN_EXTENSION"}
    )


def test_f090_r19_la_cobertura_medida_por_familia() -> None:
    descripcion = _adjuntos()["descripcion"]
    for cifra in ("62,8 %", "96,1 %", "2019", "2017", "92,4 %", "25,1 %",
                  "14,3 %", "21,4 %", "2022", "0,2 %"):
        assert cifra in descripcion, f"la cobertura no dice «{cifra}» (R19)"


def test_f090_r20_la_ausencia_de_fila_no_es_un_fallo() -> None:
    descripcion = _adjuntos()["descripcion"]
    assert "Sigrid no tiene adjunto" in descripcion, "R20"
    assert "no un fallo del ETL" in descripcion, "R20"


def test_f090_r21_donde_esta_el_binario_y_como_se_pide() -> None:
    texto = _texto(_adjuntos())
    for dato in ("ruesma_rep", "sigrid-api", "documents/read", "cod_repositorio",
                 "0,23 %", "11 %", "nombre_fichero", "blob_column: ima"):
        assert dato in texto, f"la ficha no dice «{dato}» (R21)"
    assert "EL FICHERO NO ESTA EN EL DATAMART" in _adjuntos()["descripcion"], "R21"


def test_f090_r22_la_clase_sale_de_la_extension_y_las_fechas_imposibles() -> None:
    texto = _texto(_adjuntos())
    for dato in ("EXTENSION", "gratipide", "100 %", "2250"):
        assert dato in texto, f"la ficha no dice «{dato}» (R22)"


def test_f090_r23_el_dato_personal() -> None:
    texto = _texto(_adjuntos())
    assert "LOGIN" in texto and "99,8 %" in texto, "R23"
    assert "DATO PERSONAL" in _adjuntos()["columnas"]["subido_por"]["significado"], "R23"


def test_f090_r27_ejemplos_de_las_tres_preguntas() -> None:
    preguntas = " | ".join(_adjuntos()["ejemplos_preguntas"]).lower()
    assert "factura" in preguntas
    assert "sin adjunto" in preguntas or "no tienen" in preguntas
    assert "excel" in preguntas and "0720" in preguntas


def test_f090_r19_relaciones_del_indice_a_los_documentos() -> None:
    destinos = {r["a"] for r in _adjuntos()["relaciones"]}
    for objeto, clave in DOCUMENTOS.items():
        assert f"compras.{objeto}.{clave}" in destinos, f"el índice no se une a {objeto}"


@pytest.mark.parametrize("objeto", sorted(DOCUMENTOS))
def test_f090_r19_cada_documento_apunta_al_indice(objeto: str) -> None:
    relaciones = _ficha("compras", objeto).get("relaciones") or []
    hacia = [r for r in relaciones if r["a"] == "compras.documento_adjuntos.documento_id"]
    assert len(hacia) == 1, f"compras.{objeto} no apunta a su índice de adjuntos"
    assert hacia[0]["de"] == DOCUMENTOS[objeto]
    assert hacia[0]["cardinalidad"] == "1:N"


# ===========================================================================
# R24 · `raw.yaml` y `00_global.yaml`
# ===========================================================================


@pytest.mark.parametrize("tabla", ["gra", "rcg"])
def test_f090_r24_fichas_de_raw(tabla: str) -> None:
    ficha = _ficha("raw", tabla)
    assert ficha["capa"] == "origen"
    assert ficha["consumo_recomendado"] is False
    texto = _texto(ficha)
    for dato in ("F-090", "D2", "199.042", "compras.documento_adjuntos"):
        assert dato in texto, f"raw.{tabla} no dice «{dato}» (R24)"


def test_f090_r24_la_ficha_de_gra_da_las_exclusiones() -> None:
    texto = _ficha("raw", "gra")["descripcion"]
    for columna in ("ima", "pul", "tex", "cam"):
        assert f"`{columna}`" in texto, f"raw.gra no cita la exclusión de `{columna}` (R24)"
    assert "ruesma_rep" in texto


def test_f090_r24_raw_yaml_cuenta_74() -> None:
    assert "Son 74 tablas" in (DIR_DICCIONARIO / "raw.yaml").read_text(encoding="utf-8")


def test_f090_r24_global_version_y_recuento() -> None:
    glob = _yaml("00_global.yaml")
    assert int(glob["version"]) >= 48, "F-090 sube la versión del diccionario"
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "version 48 (F-090" in texto
    assert "las 74 tablas" in texto
    assert glob["pendientes"] == []


# ===========================================================================
# R25 · ARCHITECTURE y azure-apps
# ===========================================================================

DATOS_DOCUMENTOS = ("74 tablas", "F-090", "`gra`", "`rcg`", "compras.documento_adjuntos",
                    "ruesma_rep", "documents/read", "sigrid-api")


def test_f090_r25_arquitectura() -> None:
    texto = DOC_ARQUITECTURA.read_text(encoding="utf-8")
    for dato in DATOS_DOCUMENTOS:
        assert dato in texto, f"ARCHITECTURE.md no dice «{dato}» (R25)"


def test_f090_r25_azure_apps() -> None:
    if not DOC_AZURE_APPS.exists():
        pytest.skip("azure-apps no esta junto a este repositorio")
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    for dato in DATOS_DOCUMENTOS:
        assert dato in texto, f"azure-apps no dice «{dato}» (R25)"
