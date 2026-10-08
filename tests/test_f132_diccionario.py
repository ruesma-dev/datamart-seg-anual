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

import pytest

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


# ===========================================================================
# R18 · las demás fichas de `compras`: la fecha del cambio sale de `rac`
# ===========================================================================


def test_f132_r18_contratos_la_antiguedad_sale_de_rac() -> None:
    texto = _plano(_ficha("compras.contratos").descripcion)
    assert "sigrid no guarda cuando cambio" not in texto
    assert "foto diaria" not in texto
    assert "compras.v_estado_documentos" in texto
    assert "rac" in texto and "f-132" in texto


def test_f132_r18_contratos_el_ejemplo_de_tres_semanas_da_la_fecha_del_envio() -> None:
    ejemplos = [_plano(e) for e in _ficha("compras.contratos").ejemplos_preguntas]
    tres_semanas = [e for e in ejemplos if "tres semanas" in e]
    assert len(tres_semanas) == 1, tres_semanas
    assert "despliegue" not in tres_semanas[0] and "foto" not in tres_semanas[0]
    assert "desde cuando" in tres_semanas[0]
    assert "compras.v_estado_documentos" in tres_semanas[0]


@pytest.mark.parametrize(
    "nombre", ["compras.historial_estados", "compras.historial_estados_fotos"]
)
def test_f132_r18_la_foto_es_el_respaldo_en_contraste(nombre: str) -> None:
    texto = _plano(_ficha(nombre).descripcion)
    assert "respaldo" in texto and "f-132" in texto
    assert "contraste-estados" in texto
    assert "compras.v_estado_documentos" in texto
    for frase in ("lo unico del datamart que sabe", "esa fecha no existe",
                  "no existe en sigrid", "no hay copia en sigrid"):
        assert frase not in texto, frase


def test_f132_r18_historial_lo_que_solo_ve_la_foto_es_el_deshacer() -> None:
    texto = _plano(_ficha("compras.historial_estados").descripcion)
    assert "deshacer" in texto or "deshech" in texto
    # Lo que F-067 fija de la foto sigue siendo cierto y se mantiene.
    assert "no se reconstruye" in texto
    assert "la historia empieza el dia del despliegue" in texto


def test_f132_r18_historial_el_cambio_de_estado_se_pregunta_a_la_vista() -> None:
    ejemplos = " | ".join(_plano(e) for e in _ficha("compras.historial_estados").ejemplos_preguntas)
    assert "cuando cambio de estado la factura x" not in ejemplos


def test_f132_r18_fn_sigrid_tiempo_remite_a_la_vista_desde_rac() -> None:
    texto = _plano(_ficha("compras.fn_sigrid_tiempo").descripcion)
    assert "compras.v_estado_documentos" in texto
    assert "rac" in texto and "f-132" in texto
    assert "(f-067)" not in texto


# ===========================================================================
# R19 · la ficha de `raw.conest`
# ===========================================================================


def test_f132_r19_conest_ya_no_dice_que_nadie_guarde_el_cuando() -> None:
    ficha = _ficha("raw.conest")
    texto = _plano(f"{ficha.descripcion} {ficha.motivo_no_consumo or ''}")
    assert "ni esta tabla ni ninguna otra guardan" not in texto
    assert "aproximacion" not in texto
    assert "tiemod" not in texto and "ultima modificacion" not in texto
    assert "rac" in texto and "compras.v_estado_documentos" in texto
    assert "lo resolvera f-067" not in texto


# ===========================================================================
# R20 · `00_global.yaml`: versión 46, esquema `compras`, P23 y P24
# ===========================================================================


def _global() -> dict:
    return _diccionario().global_raw


def _pregunta(identificador: str) -> dict:
    for pregunta in _global()["preguntas_aceptacion"]:
        if pregunta["id"] == identificador:
            return pregunta
    raise AssertionError(f"no está la pregunta {identificador}")


def test_f132_r20_la_version_sube_a_46_con_su_historia() -> None:
    assert int(_diccionario().version) >= 46
    texto = (DIR_DICCIONARIO / "00_global.yaml").read_text(encoding="utf-8")
    historia = texto.split("\nversion:", 1)[0]
    assert "# version 46 (F-132, 2026-10-08)" in historia


def test_f132_r20_el_esquema_compras_cita_la_vista_desde_rac() -> None:
    texto = _plano(_global()["esquemas"]["compras"]["para_que_sirve"])
    assert "compras.v_estado_documentos" in texto
    assert "rac" in texto and "f-132" in texto
    assert "con los dias en el estado" not in texto


def test_f132_r20_p23_respondible_con_la_fecha_del_envio() -> None:
    p23 = _pregunta("P23")
    assert p23["estado"] == "respondible"
    assert "bloqueada_por" not in p23
    assert "nota" not in p23, "la nota decía cuándo dejaba de ser parcial"
    assert "compras.v_estado_documentos" in p23["objetos_esperados"]
    respuesta = _plano(p23["respuesta_correcta"])
    assert "estado_codigo = 'epf'" in respuesta and "dias_en_estado > 21" in respuesta
    assert "en_estado_desde" in respuesta and "fecha del envio" in respuesta
    assert "envios antiguos" in respuesta and "sin cerrar" in respuesta
    for viejo in ("minimo", "despliegue", "ultima_foto", "antiguedad_es_minima"):
        assert viejo not in respuesta, viejo


def test_f132_r20_p24_espera_documento_procesos() -> None:
    p24 = _pregunta("P24")
    assert p24["estado"] == "respondible"
    assert p24["objetos_esperados"][0] == "compras.documento_procesos"
    respuesta = _plano(p24["respuesta_correcta"])
    assert "compras.documento_procesos" in respuesta and "orden" in respuesta
    assert "historia neta" in respuesta
    assert "ventana" not in respuesta.split("deshech")[0], (
        "el cambio se da con su fecha y hora, no como una ventana entre fotos"
    )
