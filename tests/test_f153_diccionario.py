# tests/test_f153_diccionario.py
"""
F-153 · Lo que las fichas declaran del estado de los albaranes (R11-R15).

El lector es un agente que no puede preguntar: si la ficha sigue diciendo
«contrato, factura y comparativo», responde con el universo de ayer. Ningún test
toca red ni BBDD: se lee el YAML y los documentos del árbol.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.domain.estado_documentos import (
    FAMILIAS_ESTADO,
    ORIGENES_FECHA,
    TIPOS_DOCUMENTO_ALBARAN,
)
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"
DOC_AZURE_APPS = RAIZ.parent / "azure-apps" / "datamart_seg_anual.md"

ALBARANES = "compras.albaranes"
VISTA = "compras.v_estado_documentos"


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _plano(texto: str | None) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _ficha(nombre: str):
    return _diccionario().por_nombre[nombre]


def _columna(nombre: str, columna: str):
    return next(c for c in _ficha(nombre).columnas if c.nombre == columna)


def _texto_columna(nombre: str, columna: str) -> str:
    c = _columna(nombre, columna)
    return _plano(f"{c.significado} {c.nulo_significa or ''}")


# --- R11 · la ficha de `compras.albaranes` ---------------------------------------


def test_f153_r11_las_tres_columnas_al_final_de_la_ficha() -> None:
    nombres = [c.nombre for c in _ficha(ALBARANES).columnas]
    assert nombres[-3:] == ["estado_id", "estado_codigo", "estado"]
    assert _columna(ALBARANES, "estado_id").agregacion == "no_sumable"


def test_f153_r11_los_cuatro_estados_del_tipo_14() -> None:
    assert list(_columna(ALBARANES, "estado_codigo").valores) == ["PDT", "COM", "CON", "FAC"]
    for columna in ("estado_codigo", "estado"):
        assert _columna(ALBARANES, columna).nulo_significa, columna


def test_f153_r11_declara_reparto_fuera_de_catalogo_y_facturado_sigrid() -> None:
    texto = _plano(_ficha(ALBARANES).descripcion)
    for dato in ("7.689", "410", "37.598", "270.177"):
        assert dato in texto, dato
    assert "2.660" in texto and "por `tipo_documento`" in texto, "el reparto por serie"
    assert "fuera de catalogo" in texto and "`estado_id` 0" in texto
    assert "`facturado_sigrid`" in texto and "185" in texto


def test_f153_r11_el_estado_no_dice_desde_cuando() -> None:
    texto = _plano(_ficha(ALBARANES).descripcion)
    assert "no dice desde cuando" in texto and VISTA in texto


def test_f153_r11_relacion_y_ejemplo() -> None:
    relaciones = {r.a: r for r in _ficha(ALBARANES).relaciones}
    assert relaciones[f"{VISTA}.documento_id"].cardinalidad == "1:1"
    assert "Que albaranes estan pendientes de comprobar" in _ficha(ALBARANES).ejemplos_preguntas
    assert _ficha(ALBARANES).ejemplos_preguntas[0] != (
        "Que albaranes estan pendientes de comprobar"
    ), "las 2 primeras enrutan: la nueva va detrás"


def test_f153_r11_fn_estado_documento_nombra_albaranes() -> None:
    assert "compras.albaranes" in _plano(_ficha("compras.fn_estado_documento").descripcion)


# --- R12 · la ficha de la vista ---------------------------------------------------


def test_f153_r12_los_cinco_origenes() -> None:
    assert list(_columna(VISTA, "origen_fecha").valores) == list(ORIGENES_FECHA)
    texto = _texto_columna(VISTA, "origen_fecha")
    for origen in ORIGENES_FECHA:
        assert origen.lower() in texto, origen


def test_f153_r12_tipo_14_se_filtra_por_codigo() -> None:
    assert "`tipo_documento_codigo = 14`" in _plano(_ficha(VISTA).descripcion)
    aviso = _texto_columna(VISTA, "tipo_documento")
    assert "tipo_documento_codigo = 14" in aviso and "no es toda la familia" in aviso


def test_f153_r12_valores_contra_el_dominio() -> None:
    assert list(_columna(VISTA, "tipo_documento").valores) == [
        *FAMILIAS_ESTADO.values(), *TIPOS_DOCUMENTO_ALBARAN,
    ]
    assert list(_columna(VISTA, "tipo_documento_codigo").valores) == [
        *(str(t) for t in FAMILIAS_ESTADO), "14",
    ]


def test_f153_r12_que_parte_tiene_fecha_y_cual_no() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "77 %" in texto and "f-133" in texto
    assert "comprobado" in texto and "contabilizado" in texto
    assert "aunque el paso exista" in texto


def test_f153_r12_facturado_no_sale_de_rac_y_es_de_dia() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "`dca.fecfac`" in texto and "no sale de `rac`" in texto
    assert "de dia" in texto and "no es la fecha de la factura" in texto


def test_f153_r12_el_tamano_y_la_relacion_con_la_cabecera() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "524.000" in texto and "208.000" in texto
    relacion = {r.a: r for r in _ficha(VISTA).relaciones}[f"{ALBARANES}.albaran_id"]
    assert relacion.cardinalidad == "1:1"
    assert "`tipo_documento_codigo = 14`" in _plano(relacion.porque)


def test_f153_r12_los_nulos_nombran_los_origenes_nuevos() -> None:
    for columna in ("en_estado_desde", "dias_en_estado"):
        assert "sin_historial" in _texto_columna(VISTA, columna), columna
    for columna in ("cambio_posterior_a", "paso_id", "proceso", "usuario", "nombre_usuario"):
        texto = _texto_columna(VISTA, columna)
        assert "facturacion" in texto and "sin_historial" in texto, columna
    assert "facturacion" in _texto_columna(VISTA, "en_estado_desde")


def test_f153_r12_el_ejemplo_va_detras_de_los_actuales() -> None:
    ejemplos = list(_ficha(VISTA).ejemplos_preguntas)
    assert ejemplos[-1] == "Que albaranes llevan mas de un mes pendientes de comprobar"
    assert ejemplos[0].startswith("Que contratos llevan mas de tres semanas")


# --- R13 · nadie afirma el universo de ayer ---------------------------------------


def test_f153_r13_la_vista_ya_no_son_tres_familias() -> None:
    ficha = _ficha(VISTA)
    assert "contrato, factura y comparativo y desde" not in _plano(ficha.descripcion)
    assert "compras.albaranes" in _plano(ficha.grano)


def test_f153_r13_global_y_architecture_nombran_los_albaranes() -> None:
    esquema = _plano(_diccionario().global_raw["esquemas"]["compras"]["para_que_sirve"])
    assert "albaran" in esquema.split("estado", 1)[1] or "f-153" in esquema
    arquitectura = _plano((RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8"))
    assert "una fila por contrato, factura y comparativo con su estado" not in arquitectura
    assert "f-153" in arquitectura


# --- R14, R15 --------------------------------------------------------------------


def test_f153_r14_la_version_sube_a_70_con_su_nota() -> None:
    assert int(_diccionario().version) >= 70
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    assert "# version 70 (F-153, 2026-11-" in texto.split("\nversion:", 1)[0]


def test_f153_r14_ningun_objeto_nuevo_y_tres_columnas_mas() -> None:
    fichas = _diccionario().por_nombre.values()
    assert len(fichas) >= 256
    assert sum(len(f.columnas) for f in fichas) >= 2243
    assert len(_ficha(ALBARANES).columnas) == 49


@pytest.mark.skipif(not DOC_AZURE_APPS.exists(), reason="azure-apps no esta junto a este repositorio")
def test_f153_r15_azure_apps_recoge_el_cambio() -> None:
    texto = DOC_AZURE_APPS.read_text(encoding="utf-8")
    bloque = texto.split("(F-153, 2026-11-02", 1)[1].split("\n### ", 1)[0]
    assert "compras.albaranes" in bloque and "compras.v_estado_documentos" in bloque
    for origen in ("FACTURACION", "SIN_HISTORIAL"):
        assert origen in bloque, origen
    assert "tipo_documento_codigo = 14" in bloque and "versión 70" in bloque
