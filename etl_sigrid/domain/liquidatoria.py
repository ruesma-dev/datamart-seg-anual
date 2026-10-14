# etl_sigrid/domain/liquidatoria.py
"""
Las ALARMAS de los documentos de Sigrid y la marca «liquidatoria» (F-138).

En Sigrid la factura liquidatoria NO es un campo del documento: es una ALARMA
de texto libre pegada a él (`conala`: `conide` -> `con`, `alaide` -> `auxala`,
`tex` el texto, `creusu`/`crefec`/`crehor` quién y cuándo la creó). Medido en
solo lectura el 2026-10-14: 46.242 alarmas, 697 variantes de texto que
empiezan por `LIQ` (`progress/spec_F-138.md`).

PARA QUÉ (D1 del humano, 2026-10-14): saber si se han TERMINADO las facturas
de un contrato, el IVA (con la liquidatoria ya no se difiere más) y AVISAR si
llega una factura DESPUÉS. «CARTA LIQUIDACIÓN» es que la última factura no
decía «liquidatoria» y hay que pedir la carta: cierra el contrato, pendiente.

LA REGLA LA EJECUTA SQL (`sql/compras/15_alarmas_liquidatoria.sql`) y la
ingesta la filtra en origen (`config/tables_sigrid.yaml`). Aquí está escrita
**una sola vez** como oráculo puro: las familias, la traducción de caracteres,
los cinco patrones y la precedencia. `tests/test_f138_ingesta_sql.py`
comprueba que el YAML y el SQL llevan LOS MISMOS literales (patrón de F-090 y
F-080).

LOS PATRONES SON VÁLIDOS EN `re` DE PYTHON Y EN EL `~` DE POSTGRESQL: sin
`\\b` (en PostgreSQL es RETROCESO, no frontera de palabra), sin `\\w` y sin
`(?`. La frontera de palabra es `(^| )` sobre el texto NORMALIZADO, que solo
tiene letras ASCII, cifras y espacios sueltos.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Final

#: Las familias de documento (`con.tip`) cuyas alarmas se ingieren y su nombre
#: publicado (D3 del humano: todas las medidas MENOS la 43, empleados).
#:
#: LISTA EXPLÍCITA y no `tip <> 43`: ante una familia NUEVA con alarmas la
#: lista falla CERRADA (no entra hasta que alguien la añade y decide si es
#: restringida); la exclusión fallaría ABIERTA (una alarma de una nómina
#: entraría sola en `raw` y en `compras`). ÚNICA FUENTE del `IN` del filtro de
#: ingesta y del `CASE` de `familia` en el SQL.
FAMILIAS_ALARMAS: Final[dict[int, str]] = {
    1: "INFORME",
    4: "CLIENTE",
    5: "PROVEEDOR",
    11: "FACTURA_VENTA",
    12: "OFERTA",
    14: "ALBARAN",
    15: "FACTURA",
    17: "CUENTA_AUXILIAR",
    20: "ASIENTO",
    25: "EFECTO_PAGO",
    33: "RECURSO",
    35: "PARTE_TRABAJO",
    40: "OTRA",
    42: "OBRA",
    44: "CONTRATO",
    46: "COMPARATIVO",
    54: "CONTRATO_VENTA",
}

#: Empleados (personal). Sus alarmas NO entran nunca, ni en `raw` (R3).
FAMILIA_EMPLEADOS: Final[int] = 43

#: Las familias que llevan la MARCA liquidatoria: albaranes, proformas y notas
#: (14) y facturas (15).
FAMILIAS_MARCA: Final[tuple[int, ...]] = (14, 15)

#: Recursos (33) y partes de trabajo (35): sus alarmas nombran trabajadores y
#: bajas. Solo las lee el perfil total, en `compras_restringida` (D9). La 25
#: (efectos de pago) NO: sus 88 efectos son de la cartera general (R32).
FAMILIAS_RESTRINGIDAS: Final[frozenset[int]] = frozenset({33, 35})

#: Traducción de las vocales acentuadas (agudas, graves, circunflejas y con
#: diéresis), la `ñ` y la `ç`, en minúscula y mayúscula: 44 caracteres cada una.
#: Es el `translate` de `compras.fn_texto_normalizado`, carácter a carácter.
TRADUCCION_ORIGEN: Final[str] = (
    "áéíóúàèìòùâêîôûäëïöü" "ÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜ" "ñÑçÇ"
)
TRADUCCION_DESTINO: Final[str] = (
    "aeiouaeiouaeiouaeiou" "AEIOUAEIOUAEIOUAEIOU" "nNcC"
)

#: Cada tramo que no es letra ASCII ni cifra se queda en UN espacio.
PATRON_NO_ALFANUMERICO: Final[str] = "[^A-Za-z0-9]+"

#: Los cinco patrones (R7), sobre el texto NORMALIZADO.
PATRON_MENCION: Final[str] = "(^| )LIQ"
PATRON_NEGADA: Final[str] = "(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ"
PATRON_CARTA: Final[str] = "(^| )CARTA (DE )?LIQ"
PATRON_DUDOSA: Final[str] = "PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI"
PATRON_REMITE: Final[str] = "(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)"

#: Las clases de una alarma (`clase_liquidacion`).
CLASE_LIQUIDATORIA: Final[str] = "LIQUIDATORIA"
CLASE_NEGADA: Final[str] = "NEGADA"
CLASE_CARTA: Final[str] = "CARTA_LIQUIDACION"
CLASE_DUDOSA: Final[str] = "DUDOSA"
CLASE_REMITE: Final[str] = "REMITE"

#: La marca de un DOCUMENTO es la clase de mayor precedencia entre sus alarmas
#: (R9). La negación explícita gana; la declarada gana a la carta porque la
#: carta se pide justo cuando la factura NO lo decía.
PRECEDENCIA: Final[tuple[str, ...]] = (
    CLASE_NEGADA,
    CLASE_LIQUIDATORIA,
    CLASE_CARTA,
    CLASE_DUDOSA,
    CLASE_REMITE,
)

#: Las clases que CIERRAN el contrato (`cierra_contrato`).
CLASES_CIERRE: Final[frozenset[str]] = frozenset({CLASE_LIQUIDATORIA, CLASE_CARTA})

_TABLA_TRADUCCION: Final[dict[int, str]] = str.maketrans(TRADUCCION_ORIGEN, TRADUCCION_DESTINO)
_RE_NO_ALFANUMERICO: Final[re.Pattern[str]] = re.compile(PATRON_NO_ALFANUMERICO)
_RE_MENCION: Final[re.Pattern[str]] = re.compile(PATRON_MENCION)
_RE_REMITE: Final[re.Pattern[str]] = re.compile(PATRON_REMITE)
#: Las ramas de una alarma que menciona `LIQ`, en su orden (R6).
_RAMAS: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(PATRON_NEGADA), CLASE_NEGADA),
    (re.compile(PATRON_CARTA), CLASE_CARTA),
    (re.compile(PATRON_DUDOSA), CLASE_DUDOSA),
)


def filtro_conala() -> str:
    """El `where` de `conala` en `tables_sigrid.yaml` (R1): las familias de R4."""
    familias = ", ".join(str(tip) for tip in sorted(FAMILIAS_ALARMAS))
    return f"conide IN (SELECT ide FROM dbo.con WHERE tip IN ({familias}))"


def es_restringida(tip: int) -> bool:
    """True si las alarmas de esa familia solo las lee el perfil total (D9)."""
    return tip in FAMILIAS_RESTRINGIDAS


def normalizar(texto: str | None) -> str:
    """El texto normalizado de R5: traducir, no alfanumérico a un espacio,
    mayúsculas y recortar. `None` es la cadena vacía.

    El `upper` va DESPUÉS de dejar solo ASCII, para que Python y PostgreSQL
    coincidan con cualquier `LC_CTYPE`.
    """
    if texto is None:
        return ""
    traducido = texto.translate(_TABLA_TRADUCCION)
    return _RE_NO_ALFANUMERICO.sub(" ", traducido).upper().strip()


def clasificar(texto: str | None) -> str | None:
    """La clase de UNA alarma (R6), o `None` si no dice nada de liquidación.

    Sin mención de `LIQ`: `REMITE` si remite a otro sitio («VER TEXTO»,
    «MIRAR NOTA»), si no `None`. Con mención: la primera que case de NEGADA,
    CARTA_LIQUIDACION y DUDOSA; si ninguna, LIQUIDATORIA.
    """
    normalizado = normalizar(texto)
    if not _RE_MENCION.search(normalizado):
        return CLASE_REMITE if _RE_REMITE.search(normalizado) else None
    for patron, clase in _RAMAS:
        if patron.search(normalizado):
            return clase
    return CLASE_LIQUIDATORIA


def marca_documento(clases: Iterable[str | None]) -> str | None:
    """La marca del documento: la clase de mayor `PRECEDENCIA` presente (R9)."""
    presentes = set(clases)
    for clase in PRECEDENCIA:
        if clase in presentes:
            return clase
    return None


def fecha_hora_creacion(crefec: int | None, crehor: int | None) -> datetime | None:
    """`creada_el` de la alarma: AAAAMMDD + HHMMSS (R10), oráculo del SQL.

    `None`, 0 o un valor imposible en CUALQUIERA de los dos campos -> `None`.
    Medido el 2026-10-14: los dos informados en el 100 %, `crehor` nunca 0 y
    ninguna hora imposible; la guarda existe para que el SQL no reviente.
    """
    if not crefec or not crehor or crefec < 0 or crehor < 0:
        return None
    anio, resto = divmod(crefec, 10_000)
    mes, dia = divmod(resto, 100)
    hora, resto = divmod(crehor, 10_000)
    minuto, segundo = divmod(resto, 100)
    try:
        return datetime(anio, mes, dia, hora, minuto, segundo)
    except ValueError:
        return None
