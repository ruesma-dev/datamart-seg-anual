# tests/test_f132_diccionario.py
"""
F-132 · Las fichas del diccionario y los textos del repositorio (R18-R23).

Quien consulta el datamart es un agente que NO PUEDE PREGUNTAR. La premisa
falsa de F-067 («Sigrid no guarda cuándo cambia el estado de un documento»)
le hacía responder «al menos N días desde el despliegue» a una pregunta que
`rac` contesta al segundo. Aquí se fija que las fichas dicen de dónde sale la
fecha, qué significa cada origen y qué NO se puede fechar, y que ningún texto
vigente sigue afirmando la premisa (R22).

Ningún test toca red ni BBDD: se lee el YAML y los documentos del árbol.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

from etl_sigrid.domain.estado_documentos import (
    FAMILIAS_ESTADO,
    ORIGENES_FECHA,
)
from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Las columnas de la vista, en su orden (R2); las mismas que fija el SQL.
COLUMNAS_VISTA = [
    "documento_id", "tipo_documento_codigo", "tipo_documento", "codigo_documento",
    "estado_id", "estado_codigo", "estado", "en_estado_desde", "origen_fecha",
    "dias_en_estado", "cambio_posterior_a", "paso_id", "proceso", "usuario",
    "nombre_usuario",
]


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _plano(texto: str | None) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _ficha(nombre: str):
    ficha = _diccionario().por_nombre.get(nombre)
    assert ficha is not None, f"no hay ficha de {nombre}"
    return ficha


def _columna(nombre: str, columna: str):
    for c in _ficha(nombre).columnas:
        if c.nombre == columna:
            return c
    raise AssertionError(f"`{nombre}.{columna}` no tiene ficha")


def _texto_columna(nombre: str, columna: str) -> str:
    c = _columna(nombre, columna)
    return _plano(f"{c.significado} {c.nulo_significa or ''}")


def _ficha_entera(nombre: str) -> str:
    ficha = _ficha(nombre)
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [f"{c.significado} {c.nulo_significa or ''}" for c in ficha.columnas]
    partes += list(ficha.ejemplos_preguntas or [])
    return _plano(" ".join(partes))


# ===========================================================================
# R18 · `compras.v_estado_documentos`, reescrita
# ===========================================================================

VISTA = "compras.v_estado_documentos"


def test_f132_r18_vista_ficha_con_las_columnas_de_la_vista_en_orden() -> None:
    assert [c.nombre for c in _ficha(VISTA).columnas] == COLUMNAS_VISTA
    assert _ficha(VISTA).tipo == "vista"
    assert list(_ficha(VISTA).clave_negocio) == ["documento_id"]


def test_f132_r18_vista_la_fecha_sale_de_rac_y_no_de_la_foto() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "compras.documento_procesos" in texto and "rac" in texto
    assert "99,4 %" in texto
    assert "foto" not in _plano(_ficha(VISTA).grano)
    # Lo que la vista de F-067 decía y ya no es cierto.
    for frase in ("la historia empieza el dia del despliegue", "al menos n dias",
                  "cambio_observado_tras", "antiguedad_es_minima", "ultima_foto"):
        assert frase not in _ficha_entera(VISTA), frase


def test_f132_r18_vista_los_tres_origenes_y_lo_que_significan() -> None:
    origen = _columna(VISTA, "origen_fecha")
    assert list(origen.valores) == list(ORIGENES_FECHA)
    texto = _texto_columna(VISTA, "origen_fecha")
    assert "estado inicial" in texto and "dia de alta" in texto
    assert "sin fecha" in texto


def test_f132_r18_vista_historia_neta_y_el_deshacer_no_se_fecha() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "historia neta" in texto
    assert "deshacer proceso" in texto and "f-105" in texto


def test_f132_r18_vista_fuera_de_proceso_sin_fecha_y_con_cota() -> None:
    assert "fuera_de_proceso" in _texto_columna(VISTA, "en_estado_desde")
    cota = _texto_columna(VISTA, "cambio_posterior_a")
    assert "despues de" in cota and "fuera_de_proceso" in cota
    assert "fuera_de_proceso" in _texto_columna(VISTA, "dias_en_estado")


def test_f132_r18_vista_tres_familias() -> None:
    assert list(_columna(VISTA, "tipo_documento").valores) == list(FAMILIAS_ESTADO.values())
    assert list(_columna(VISTA, "tipo_documento_codigo").valores) == [
        str(t) for t in FAMILIAS_ESTADO
    ]
    destinos = {r.a for r in _ficha(VISTA).relaciones}
    assert {
        "compras.contratos.contrato_id",
        "compras.facturas.factura_id",
        "compras.comparativos.comparativo_id",
    } <= destinos


def test_f132_r18_vista_los_envios_antiguos_sin_cerrar() -> None:
    texto = _plano(_ficha(VISTA).descripcion)
    assert "estado_codigo = 'epf'" in texto and "dias_en_estado > 21" in texto
    assert "785" in texto and "2025" in texto


def test_f132_r18_vista_el_nombre_es_dato_personal() -> None:
    assert "dato personal" in _texto_columna(VISTA, "nombre_usuario")
