# tests/test_f084_diccionario.py
"""
F-084 · La ficha de `compras.contratos`: el estado, y las DOS cosas que no se
pueden responder con el.

`config/diccionario/` es lo que el MCP lee por SQL antes de contestar, y quien
lo lee es un agente que **no puede preguntar**. Publicar el estado sin la ficha
que lo acota es el peor de los dos mundos: el agente ve una columna `estado`,
ve un valor «Enviado», y contesta la pregunta de Compras —«que contratos llevan
mas de tres semanas enviados sin firmar»— con un numero que no significa eso.

TRES COSAS QUE LA FICHA TIENE QUE DEJAR CERRADAS, y las tres salen de una
medicion, no de una opinion:

1. **El estado SE PUEDE responder**: 818 contratos en «Enviado» el 2026-09-16.
   Esa mitad de la pregunta se contesta desde hoy.
2. **La ANTIGUEDAD no.** El datamart no guarda cuando cambio el estado. Lo
   unico que hay en el origen es `con.tiemod`, la ultima modificacion del
   documento, que **NO es la fecha del cambio de estado**: un contrato al que
   se le toco una linea ayer «lleva un dia» aunque se enviara en 2019. La foto
   diaria que daria la antiguedad de verdad es F-067.
3. **El circuito de firma NO sirve para el contrato**, y esto es un hallazgo,
   no una limitacion conocida: de las 70.346 firmas de `raw.confir` medidas el
   2026-09-16 hay **CERO de contrato**. Sin decirlo, el siguiente agente —o el
   siguiente humano— gastara media tarde buscando ahi.

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

#: Las quince columnas que `compras.contratos` publica tras F-084, en orden.
COLUMNAS_PUBLICADAS = (
    "contrato_id",
    "codigo_contrato",
    "serie",
    "descripcion",
    "fecha",
    "obra_id",
    "codigo_obra",
    "nombre_obra",
    "proveedor_id",
    "proveedor_nombre",
    "proveedor_cif",
    "comparativo_id",
    "estado_id",
    "estado_codigo",
    "estado",
)

#: Los SIETE estados del tipo 44 con su reparto medido el 2026-09-16 sobre los
#: 18.978 contratos. Los siete se usan: aqui no hay ninguno a cero, al reves
#: que en las facturas del tipo 15 (donde tres del catalogo no los usa nadie).
REPARTO_MEDIDO = (
    ("Firmado", "13.459"),
    ("Terminado", "3.179"),
    ("Enviado", "818"),
    ("Pdt. envio de firma", "564"),
    ("Recibido", "550"),
    ("Comprobada documentacion", "232"),
    ("Rescindido", "176"),
)

#: Los mnemonicos del catalogo del tipo 44, que es el vocabulario con el que se
#: puede filtrar sin depender del literal.
MNEMONICOS = ("PFP", "EPF", "RFP", "COMD", "FIR", "TER", "RES")


@lru_cache(maxsize=1)
def _diccionario():
    dicc, _ = cargar_diccionario(DIR_DICCIONARIO)
    return dicc


@lru_cache(maxsize=1)
def _ficha_contratos():
    for ficha in _diccionario().fichas:
        if ficha.nombre == "compras.contratos":
            return ficha
    raise AssertionError("no hay ficha de compras.contratos")


def _columna(nombre: str):
    for columna in _ficha_contratos().columnas:
        if columna.nombre == nombre:
            return columna
    return None


def _texto_de_columna(nombre: str) -> str:
    columna = _columna(nombre)
    assert columna is not None, f"`compras.contratos.{nombre}` no tiene ficha"
    return normalizado(f"{columna.significado or ''} {columna.nulo_significa or ''}")


def _texto_de_la_ficha() -> str:
    ficha = _ficha_contratos()
    partes = [ficha.descripcion, ficha.grano or ""]
    partes += [c.significado or "" for c in ficha.columnas]
    partes += [c.nulo_significa or "" for c in ficha.columnas]
    partes += list(ficha.ejemplos_preguntas or [])
    return normalizado(" ".join(partes))


# ===========================================================================
# Las quince columnas, todas con ficha
# ===========================================================================


@pytest.mark.parametrize("columna", COLUMNAS_PUBLICADAS)
def test_f084_c1_la_ficha_describe_todas_las_columnas_publicadas(
    columna: str,
) -> None:
    ficha = _columna(columna)
    assert ficha is not None, (
        f"`compras.contratos` publica `{columna}` y la ficha no lo describe: "
        "el agente lo vera en el catalogo y se inventara su significado"
    )
    assert normalizado(ficha.significado or "").strip(), (
        f"`{columna}` tiene entrada vacia en la ficha"
    )


# ===========================================================================
# Criterio 1 · la traduccion va por la PAREJA, y la ficha lo dice
# ===========================================================================


def test_f084_c1_la_ficha_manda_traducir_por_la_pareja_tipo_estado() -> None:
    texto = _texto_de_columna("estado_id")
    assert "44" in texto, (
        "`estado_id` es un codigo interno que solo significa algo dentro del "
        "tipo de documento 44: su ficha tiene que decirlo, o alguien lo "
        "traducira contra los estados de obra o de factura"
    )


def test_f084_c1_la_ficha_del_codigo_enumera_los_mnemonicos() -> None:
    """El codigo es lo unico estable: el literal lo puede reescribir Sigrid."""
    texto = _texto_de_columna("estado_codigo")
    faltan = [codigo for codigo in MNEMONICOS if codigo not in texto]
    assert not faltan, (
        f"`estado_codigo` no enumera {faltan}: son los siete mnemonicos del "
        "tipo 44, y es por donde hay que filtrar para no depender del literal"
    )


# ===========================================================================
# Criterio 3 · el reparto medido, escrito en la ficha
# ===========================================================================


@pytest.mark.parametrize(("literal", "cuantos"), REPARTO_MEDIDO)
def test_f084_c3_la_ficha_publica_el_reparto_medido(
    literal: str, cuantos: str
) -> None:
    """Con los siete literales y sus siete cifras.

    Una ficha sin numeros no sirve para dimensionar una respuesta: el agente no
    sabe si «Enviado» son cuatro contratos o cuatro mil, y por tanto no sabe si
    conviene listarlos o contarlos.
    """
    texto = _texto_de_columna("estado")
    assert literal in texto, (
        f"la ficha de `estado` no nombra «{literal}», uno de los siete estados "
        "del tipo 44 medidos el 2026-09-16"
    )
    assert cuantos in texto, (
        f"la ficha no trae cuantos contratos hay en «{literal}» ({cuantos}), "
        "medido el 2026-09-16 sobre los 18.978 contratos"
    )


def test_f084_c3_la_ficha_declara_que_los_siete_estados_se_usan() -> None:
    """Contraste explicito con `compras.facturas`, donde tres estan a cero.

    Importa porque la respuesta «ninguno» significa cosas distintas en las dos
    tablas: aqui, si un estado sale vacio en una consulta, es el filtro, no el
    catalogo.
    """
    texto = _texto_de_columna("estado")
    assert "los siete" in texto.lower() or "7 estados" in texto, (
        "la ficha tiene que decir que los SIETE estados del catalogo del tipo "
        "44 los usa algun contrato, al reves que en `compras.facturas`"
    )


# ===========================================================================
# Criterio 4 · la ANTIGUEDAD del estado no se puede responder hoy
# ===========================================================================


def test_f084_c4_la_ficha_declara_el_proxy_de_antiguedad_y_su_trampa() -> None:
    """Las palabras que el criterio 4 pide, y las pide con esas palabras.

    Sin esto, «que contratos llevan mas de tres semanas enviados» se contesta
    con un numero que parece la respuesta y no lo es.
    """
    texto = _texto_de_la_ficha()
    assert "con.tiemod" in texto, (
        "la ficha tiene que nombrar `con.tiemod` como la UNICA aproximacion a "
        "la antiguedad del estado (criterio 4)"
    )
    plano = texto.lower()
    assert "no es la fecha del cambio de estado" in plano, (
        "la ficha tiene que decir, con esas palabras, que `con.tiemod` NO es "
        "la fecha del cambio de estado: es la ultima modificacion del "
        "documento, y confundirlas da «lleva X dias enviado» con un numero "
        "que no significa eso (criterio 4)"
    )


def test_f084_c4_la_ficha_dice_que_la_antiguedad_no_esta_publicada() -> None:
    """Y que quien la traera es F-067, para que nadie la busque aqui.

    Mandar al agente a una columna que el datamart no publica es peor que
    callarse: `con.tiemod` esta en `raw`, y el MCP no ve `raw`.
    """
    texto = _texto_de_la_ficha()
    assert "F-067" in texto, (
        "la ficha tiene que decir que la foto diaria que daria la antiguedad "
        "REAL del estado es F-067 y todavia no existe (criterio 4)"
    )


def test_f084_c4_los_ejemplos_recogen_la_pregunta_de_compras() -> None:
    ejemplos = normalizado(" ".join(_ficha_contratos().ejemplos_preguntas or []))
    plano = ejemplos.lower()
    assert "enviado" in plano and "firmar" in plano, (
        "`ejemplos_preguntas` tiene que traer la pregunta que origino la "
        "feature —que contratos estan enviados y sin firmar—, que es como el "
        "MCP encuentra esta tabla sin que nadie se lo explique (criterio 4)"
    )


# ===========================================================================
# Criterio 5 · el circuito de firma no sirve para el contrato
# ===========================================================================


def test_f084_c5_la_ficha_declara_que_no_hay_firmas_de_contrato() -> None:
    """Con la cifra: cero firmas de contrato sobre 70.346.

    Es el hallazgo caro de la feature. La via natural para «enviado sin
    firmar» era el circuito de firma, y esta vacio para este documento: las
    70.346 firmas son de comparativos, facturas y obras.
    """
    texto = _texto_de_la_ficha()
    assert "70.346" in texto, (
        "la ficha tiene que traer la cifra medida el 2026-09-16: CERO firmas "
        "de contrato sobre las 70.346 de `raw.confir` (criterio 5)"
    )
    plano = texto.lower()
    assert "cero" in plano and "firma" in plano, (
        "la ficha tiene que decir que el circuito de firma NO sirve para el "
        "contrato: no hay ni una firma de contrato, asi que «enviado sin "
        "firmar» solo se puede responder por el ESTADO (criterio 5)"
    )
