# tests/test_f083_diccionario.py
"""
F-083 · La ficha de `compras.facturas`: cinco columnas nuevas y dos confusiones.

`config/diccionario/` es lo que el MCP lee por SQL antes de contestar, y quien
lo lee es un agente que **no puede preguntar**. Esta feature nace justo de ahi:
Administracion pidio el estado de la factura y lo que habia publicado era el
estado del **efecto de pago**. La ficha no tiene que describir la columna: tiene
que **impedir la confusion**.

Son dos confusiones distintas y las dos hay que cerrarlas por escrito:

1. **El estado.** `compras.facturas.estado` es el del documento en el circuito
   de aprobacion (CON, APJO, APRADM, APR, RECH). `compras.vencimientos.estado_pago`
   es el del EFECTO de pago. Un listado de «facturas sin aprobar» hecho con el
   segundo mide otra cosa.
2. **Las tres fechas.** `fecha` (la de siempre, que es la de ALTA), `fecha_alta`
   (la misma con nombre inequivoco) y `fecha_factura` (la que el proveedor pone
   en su documento). Se separan en el **77,8 %** de las facturas, con mediana de
   cuatro dias y p95 de 42: elegir la equivocada da un numero falso con aspecto
   de dato.

Ningun test toca red ni BBDD: se lee el YAML del arbol.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.infrastructure.diccionario.cargador_yaml import cargar_diccionario
from tests._texto import normalizado

RAIZ = Path(__file__).resolve().parents[1]
DIR_DICCIONARIO = RAIZ / "config" / "diccionario"

#: Las quince columnas que `compras.facturas` publica tras F-083, en orden.
COLUMNAS_PUBLICADAS = (
    "factura_id",
    "codigo_factura",
    "serie",
    "tipo_documento",
    "descripcion",
    "fecha",
    "proveedor_id",
    "proveedor_nombre",
    "proveedor_cif",
    "referencia_proveedor",
    "estado_id",
    "estado_codigo",
    "estado",
    "fecha_factura",
    "fecha_alta",
)

LAS_TRES_FECHAS = ("fecha", "fecha_factura", "fecha_alta")


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


@lru_cache(maxsize=1)
def _ficha_facturas():
    for ficha in _diccionario().fichas:
        if ficha.nombre == "compras.facturas":
            return ficha
    raise AssertionError("no hay ficha de compras.facturas")


def _columna(nombre: str):
    for columna in _ficha_facturas().columnas:
        if columna.nombre == nombre:
            return columna
    return None


def _texto_de_columna(nombre: str) -> str:
    columna = _columna(nombre)
    assert columna is not None, f"`compras.facturas.{nombre}` no tiene ficha"
    return normalizado(f"{columna.significado or ''} {columna.nulo_significa or ''}")


def _texto_de_la_ficha() -> str:
    ficha = _ficha_facturas()
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [c.significado or "" for c in ficha.columnas]
    partes += [c.nulo_significa or "" for c in ficha.columnas]
    return normalizado(" ".join(partes))


# ===========================================================================
# Las quince columnas, todas con ficha
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_PUBLICADAS)
def test_f083_la_ficha_describe_todas_las_columnas_publicadas(columna: str) -> None:
    ficha = _columna(columna)
    assert ficha is not None, (
        f"`compras.facturas` publica `{columna}` y la ficha no lo describe: el "
        "agente lo vera en el catalogo y se inventara su significado"
    )
    assert normalizado(ficha.significado or "").strip(), (
        f"`{columna}` tiene entrada vacia en la ficha"
    )


# ===========================================================================
# Criterio 5 · el estado de la FACTURA no es el del EFECTO
# ===========================================================================


def test_f083_la_ficha_nombra_las_dos_columnas_que_se_confunden() -> None:
    """Las dos, con su nombre completo, para que el MCP no las mezcle."""
    texto = _texto_de_la_ficha()
    assert "compras.vencimientos" in texto, (
        "la ficha de `compras.facturas` tiene que nombrar "
        "`compras.vencimientos` para separar el estado de la factura del "
        "estado del efecto de pago (criterio 5)"
    )
    assert "estado_pago" in texto, (
        "la ficha tiene que nombrar `estado_pago` por su nombre: decir «el "
        "estado del efecto» no basta para que el agente encuentre la otra "
        "columna y la descarte (criterio 5)"
    )


def test_f083_la_ficha_del_estado_dice_que_no_es_el_del_efecto() -> None:
    """Y lo dice en la propia columna, no solo en la descripcion del objeto."""
    texto = _texto_de_columna("estado")
    assert "vencimientos" in texto or "efecto" in texto, (
        "`compras.facturas.estado` tiene que declarar EN SU PROPIA FICHA que "
        "no es el estado del efecto de pago: quien lee una columna suelta en "
        "el catalogo no lee la descripcion del objeto entero (criterio 5)"
    )


def test_f083_la_ficha_del_estado_declara_el_circuito_de_aprobacion() -> None:
    """Los codigos del correo, para que una pregunta en su vocabulario acierte."""
    texto = _texto_de_columna("estado_codigo")
    assert all(codigo in texto for codigo in ("CON", "APJO", "APRADM", "APR")), (
        "`estado_codigo` publica el mnemonico de Sigrid (APR, CON, APJO, "
        "APRADM...) y su ficha tiene que enumerarlos: es el vocabulario en el "
        "que Administracion hace la pregunta"
    )


def test_f083_la_ficha_declara_que_hay_estados_sin_usar() -> None:
    """Tres de los 21 no los usa ninguna factura, `FRARET` entre ellos.

    El correo pregunta por las **retenidas**, y la respuesta correcta hoy es
    «cero», no «no se puede saber». Sin declararlo, un agente que no encuentre
    ninguna concluye que la columna esta mal.
    """
    texto = _texto_de_la_ficha()
    assert "FRARET" in texto, (
        "la ficha tiene que decir que `FRARET` (factura retenida) existe en el "
        "catalogo y hoy no lo usa ninguna factura (criterio 4)"
    )


def test_f083_la_ficha_manda_traducir_por_la_pareja_tipo_estado() -> None:
    texto = _texto_de_columna("estado_id")
    assert "15" in texto, (
        "`estado_id` es un codigo interno que solo significa algo dentro del "
        "tipo de documento 15: su ficha tiene que decirlo, o alguien lo "
        "traducira contra los estados de obra"
    )


# ===========================================================================
# Ampliacion del humano · las tres fechas, cada una con su ficha
# ===========================================================================


@pytest.mark.parametrize("fecha", LAS_TRES_FECHAS)
def test_f083_cada_fecha_declara_de_donde_sale(fecha: str) -> None:
    """De donde sale, con el campo de Sigrid escrito."""
    texto = _texto_de_columna(fecha)
    assert "fecdoc" in texto or "con.fec" in texto, (
        f"la ficha de `{fecha}` tiene que decir de que campo de Sigrid sale "
        "(`dcf.fecdoc` o `con.fec`): son tres fechas que se confunden y el "
        "origen es lo que las distingue"
    )


@pytest.mark.parametrize("fecha", LAS_TRES_FECHAS)
def test_f083_cada_fecha_se_distingue_de_las_otras_dos(fecha: str) -> None:
    """Cada ficha nombra a sus dos hermanas. Es lo que el humano subrayo."""
    texto = _texto_de_columna(fecha)
    otras = [otra for otra in LAS_TRES_FECHAS if otra != fecha]
    faltan = [otra for otra in otras if f"`{otra}`" not in texto]
    assert not faltan, (
        f"la ficha de `{fecha}` no nombra a {faltan}: tres fechas parecidas en "
        "la misma tabla se eligen mal salvo que cada una diga en que se "
        "diferencia de las otras dos"
    )


def test_f083_la_ficha_declara_que_fecha_se_conserva_por_compatibilidad() -> None:
    texto = _texto_de_columna("fecha")
    plano = texto.lower()
    assert "compatibilidad" in plano, (
        "`fecha` no se quita ni se renombra porque la consumen Power BI y el "
        "MCP, y su ficha tiene que decir que se conserva por compatibilidad y "
        "que es la MISMA que `fecha_alta`"
    )


def test_f083_la_ficha_avisa_de_que_las_dos_fechas_casi_nunca_coinciden() -> None:
    """Con la cifra medida: 77,8 %. Una ficha sin numero no convence a nadie."""
    texto = _texto_de_la_ficha()
    assert "77,8" in texto, (
        "la ficha tiene que traer la cifra medida el 2026-09-16: las dos "
        "fechas se separan en el 77,8 % de las facturas (129.012 de 165.783), "
        "con mediana de 4 dias y p95 de 42"
    )
