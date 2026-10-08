# tests/test_f067_diccionario.py
"""
F-067 · Las fichas del diccionario: lo que el MCP lee antes de responder.

Quien lee estas fichas es un agente que NO PUEDE PREGUNTAR. Las frases que se
fijan aquí son las que separan una respuesta cierta de una plausible y falsa:

- el «código 2» se llama así para Negocio, lo pone el jefe de obra y viaja de
  la necesidad al albarán (R22, R23);
- el documento de necesidades es el DPC, uno por obra, y su estado no informa
  (R24);
- la foto de estados empieza el día del despliegue (R11; la antigüedad del
  estado sale de `rac` desde F-132, ver `test_f132_diccionario.py`);
- `con.tiemod` NO es la fecha del cambio de estado (R14, D2) y la penalización
  no es un campo (R15).

Ningún test toca red ni BBDD: se lee el YAML del árbol.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


def _plano(texto: str | None) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados: la frase se
    encuentra esté como esté ajustada la línea."""
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


def _relaciones(nombre: str) -> set[tuple[str, str, str]]:
    return {(r.de, r.a, r.cardinalidad) for r in _ficha(nombre).relaciones}


# ===========================================================================
# R28 · cada objeto nuevo con su ficha y su clave
# ===========================================================================

CLAVES = {
    "compras.historial_estados": ("documento_id", "desde"),
    "compras.historial_estados_fotos": ("observado_en",),
    "compras.v_estado_documentos": ("documento_id",),
    "compras.necesidades": ("necesidad_id",),
}


@pytest.mark.parametrize(("nombre", "clave"), sorted(CLAVES.items()))
def test_f067_r28_objeto_nuevo_con_ficha_de_consumo_y_clave(
    nombre: str, clave: tuple[str, ...]
) -> None:
    ficha = _ficha(nombre)
    assert ficha.clave_negocio == clave
    assert ficha.consumo_recomendado is True
    assert ficha.paso_etl == "build_compras"
    assert ficha.refresco == "nocturno"


def test_f067_r28_la_funcion_nueva_tiene_ficha_de_operacion() -> None:
    ficha = _ficha("compras.fn_sigrid_tiempo")
    assert ficha.tipo == "funcion" and ficha.consumo_recomendado is False
    assert "1899-12-30" in ficha.descripcion and "dos dias mas" in _plano(ficha.descripcion)


# ===========================================================================
# R22 · R23 · el «código 2»
# ===========================================================================

LINEAS_COMPRAS = ("compras.albaran_lineas", "compras.contrato_lineas", "compras.factura_lineas")
VISTAS_DESCOMPUESTOS = (
    "descompuestos.lineas",
    "descompuestos.v_pbi_estudio",
    "descompuestos.v_pbi_planif_jo",
    "descompuestos.v_pbi_master_planif_jo",
    "descompuestos.v_pbi_master_estudio",
)


@pytest.mark.parametrize("nombre", LINEAS_COMPRAS + VISTAS_DESCOMPUESTOS)
def test_f067_r22_codigo_alternativo_se_llama_codigo_2(nombre: str) -> None:
    assert "codigo 2" in _texto_columna(nombre, "codigo_alternativo")


@pytest.mark.parametrize("nombre", LINEAS_COMPRAS)
def test_f067_r22_codigo_2_lo_pone_el_jefe_de_obra_y_viaja_de_la_necesidad(
    nombre: str,
) -> None:
    texto = _texto_columna(nombre, "codigo_alternativo")
    for frase in ("jefe de obra", "agrupar o filtrar", "(dpc)", "99,9 %", "295.210"):
        assert frase in texto, frase
    assert "sin normalizar" in texto, "los valores son libres: HORMIGON, HORM, HORM."


def test_f067_r23_en_descompuestos_es_el_codigo_2_en_los_cuatro_origenes() -> None:
    texto = _texto_columna("descompuestos.lineas", "codigo_alternativo")
    for frase in ("cuatro origenes", "campo 7", "dncpro.cod2", "fecha de la version"):
        assert frase in texto, frase


@pytest.mark.parametrize("nombre", LINEAS_COMPRAS)
def test_f067_r17_la_necesidad_en_las_lineas(nombre: str) -> None:
    assert "dpc" in _texto_columna(nombre, "necesidad_id")
    assert "dncpro" in _texto_columna(nombre, "necesidad_linea_id")


# ===========================================================================
# R24 · R25 · el documento de necesidades
# ===========================================================================


def test_f067_r24_necesidades_es_el_dpc_uno_por_obra_sin_estado() -> None:
    texto = _plano(_ficha("compras.necesidades").descripcion)
    for frase in ("documento de planificacion de compras (dpc)", "uno por obra",
                  "271", "277", "en curso", "no se publica su estado"):
        assert frase in texto, frase


def test_f067_r25_relaciones_del_albaran_con_la_necesidad() -> None:
    relaciones = _relaciones("compras.albaran_lineas")
    assert ("necesidad_id", "compras.necesidades.necesidad_id", "N:1") in relaciones
    assert (
        "necesidad_linea_id", "descompuestos.v_pbi_planif_jo.dncpro_id", "N:N"
    ) in relaciones


def test_f067_r25_la_necesidad_va_a_su_obra() -> None:
    assert ("obra_id", "maestro.obras.obra_id", "N:1") in _relaciones("compras.necesidades")


# ===========================================================================
# R10 · R11 · la antigüedad del estado
# ===========================================================================


def _ficha_entera(nombre: str) -> str:
    ficha = _ficha(nombre)
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [f"{c.significado} {c.nulo_significa or ''}" for c in ficha.columnas]
    partes += list(ficha.ejemplos_preguntas or [])
    return _plano(" ".join(partes))


# R10 y la parte de R11 sobre la vista: RETIRADOS por F-132. La vista ya no
# sale de la foto (no hay línea base, ni mínimo, ni «entre dos fotos»): la
# fecha sale de `rac`, y su ficha la fija `tests/test_f132_diccionario.py`.


def test_f067_r11_la_historia_de_la_foto_empieza_al_desplegar() -> None:
    assert "la historia empieza el dia del despliegue" in _plano(
        _ficha("compras.historial_estados").descripcion
    )


def test_f067_r8_la_ficha_avisa_de_que_la_historia_no_se_reconstruye() -> None:
    for nombre in ("compras.historial_estados", "compras.historial_estados_fotos"):
        assert "no se reconstruye" in _plano(_ficha(nombre).descripcion), nombre


# ===========================================================================
# R14 · R15 · R16 · la ficha del contrato
# ===========================================================================


def test_f067_r14_la_ultima_modificacion_no_es_el_cambio_de_estado() -> None:
    texto = _texto_columna("compras.contratos", "fecha_ultima_modificacion")
    assert "no es la fecha del cambio de estado" in texto
    assert "con.tiemod" in texto and "85 %" in texto
    assert "compras.v_estado_documentos" in texto


def test_f067_r15_la_penalizacion_no_es_un_campo() -> None:
    texto = _plano(_ficha("compras.contratos").descripcion)
    assert "penalizacion no es un campo de sigrid" in texto
    assert "compras.documento_texto" in texto and "9 contratos" in texto


def test_f067_r16_la_antiguedad_ya_no_es_imposible_y_remite_a_la_vista() -> None:
    texto = _ficha_entera("compras.contratos")
    assert "no se puede saber" not in texto
    assert "compras.v_estado_documentos" in _plano(_ficha("compras.contratos").descripcion)
    ejemplos = [_plano(e) for e in _ficha("compras.contratos").ejemplos_preguntas]
    tres_semanas = [e for e in ejemplos if "tres semanas" in e]
    assert tres_semanas and all("no" not in e.split() for e in tres_semanas), tres_semanas


def test_f067_r12_las_condiciones_del_contrato_tienen_ficha() -> None:
    for columna in ("forma_pago_id", "forma_pago", "retencion_garantia_porcentaje",
                    "retencion_garantia_concepto", "fecha_ultima_modificacion"):
        assert _columna("compras.contratos", columna).significado
    assert "tanto por cien" in _texto_columna("compras.contratos", "retencion_garantia_porcentaje")


# ===========================================================================
# R26 · los comparativos ya responden el acceptance 3
# ===========================================================================


def test_f067_r26_comparativos_por_actividad_y_adjudicatarios_repetidos() -> None:
    ejemplos = " | ".join(_plano(e) for e in _ficha("compras.comparativos").ejemplos_preguntas)
    assert "por actividad" in ejemplos
    assert "mas de una actividad" in ejemplos
    texto = _plano(_ficha("compras.comparativos").descripcion)
    assert "877" in texto and "contrato_id" in texto


# ===========================================================================
# R27 · `00_global.yaml`: versión y preguntas de aceptación
# ===========================================================================


def _pregunta(identificador: str) -> dict:
    for pregunta in _diccionario().global_raw["preguntas_aceptacion"]:
        if pregunta["id"] == identificador:
            return pregunta
    raise AssertionError(f"no está la pregunta {identificador}")


def test_f067_r27_la_version_sube_a_44() -> None:
    # F-085 la sube a 45: lo que se fija es que F-067 la subio.
    assert int(_diccionario().version) >= 44


def test_f067_r27_p23_tres_semanas_parcial_hasta_21_dias_despues() -> None:
    p23 = _pregunta("P23")
    assert p23["estado"] == "parcial" and p23["bloqueada_por"] == "F-067"
    assert "compras.v_estado_documentos" in p23["objetos_esperados"]
    respuesta = _plano(p23["respuesta_correcta"])
    assert "minimo" in respuesta and "dia del despliegue" in respuesta


@pytest.mark.parametrize(
    ("identificador", "objeto"),
    [
        ("P24", "compras.historial_estados"),
        ("P25", "compras.comparativos"),
        ("P26", "compras.albaran_lineas"),
    ],
)
def test_f067_r27_p24_a_p26_respondibles(identificador: str, objeto: str) -> None:
    pregunta = _pregunta(identificador)
    assert pregunta["estado"] == "respondible"
    assert objeto in pregunta["objetos_esperados"]
