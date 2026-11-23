# etl_sigrid/domain/texto_largo.py
"""
F-168 · El texto largo de la partida y de cada línea del flujo de obra.

UNA sola limpieza y UNA sola identidad para todo el texto largo que publica el
datamart (`stg.partida_texto`, `compras.linea_texto`/`compras.textos` y
`descompuestos.textos`). El SQL (`sql/stg/11_texto_largo.sql`) es la versión
que corre de noche; esto es su espejo, donde se prueba sin base de datos, y el
ÚNICO sitio donde se escriben los literales (R7): el tope, el patrón de
control y la expresión de recorte que se manda a Sigrid. Un test comprueba que
el SQL y `config/tables_sigrid.yaml` usan estos mismos.

Medido por el spec-author el 2026-11-23 (`progress/spec_F-168.md`): todo es
texto PLANO (0 RTF); 16.000 caracteres no cortan ninguna línea del flujo y solo
cortan 8 partidas, todas basura (una de 24,8 MB). Los NUL harían caer el `COPY`
de la tabla entera: la expresión de recorte los quita ya en Sigrid.

Puro: sin dependencias externas.
"""

from __future__ import annotations

import hashlib
import re
import uuid

#: Tope de caracteres del texto, en `raw` (lo corta Sigrid) y al publicar (D4).
TOPE_CARACTERES = 16000

#: Los caracteres de control que se quitan al publicar: todos salvo el
#: tabulador (\x09), el salto de línea (\x0A) y el retorno (\x0D), que antes se
#: ha convertido en salto. Vale literal en Python y en el motor ARE de Postgres.
PATRON_CONTROL = r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]"

#: Lo que se recorta en los extremos (el `btrim` del SQL).
EXTREMOS = " \t\n"

_RE_CONTROL = re.compile(PATRON_CONTROL)
_COLUMNA = re.compile(r"^[a-z][a-z0-9_]*$")


def limpiar(texto: str | None) -> str | None:
    """El texto limpio (R5): el mismo resultado que `stg.fn_texto_largo`.

    En este orden: `\\r\\n` y `\\r` pasan a `\\n`; fuera los controles de
    `PATRON_CONTROL`; fuera espacios, tabuladores y saltos de los extremos;
    corte a `TOPE_CARACTERES`; otra vez los extremos (el corte puede dejar un
    espacio al final); y vacío es `None`.
    """
    if texto is None:
        return None
    limpio = texto.replace("\r\n", "\n").replace("\r", "\n")
    limpio = _RE_CONTROL.sub("", limpio)
    limpio = limpio.strip(EXTREMOS)[:TOPE_CARACTERES].strip(EXTREMOS)
    return limpio or None


def texto_id(texto: str | None) -> uuid.UUID | None:
    """La identidad de un texto YA limpio (R6): `md5(texto)::uuid`.

    Mismo `texto_id`, mismo texto, en `stg`, `compras` y `descompuestos`.
    """
    if texto is None:
        return None
    return uuid.UUID(hashlib.md5(texto.encode("utf-8")).hexdigest())


def es_recortado(texto_raw: str | None) -> bool:
    """El texto de `raw` mide el tope o más (R8): Sigrid lo ha cortado.

    Con 16.000 justos no se distingue un texto que medía eso de uno cortado; se
    marca igual, a propósito: `recortado` es «puede faltar texto».
    """
    return texto_raw is not None and len(texto_raw) >= TOPE_CARACTERES


def expresion_recorte(columna: str, tope: int) -> str:
    """La columna como se pide a Sigrid (R3): cortada a `tope` y sin NUL.

    `SUBSTRING` corta en origen (no viajan los 24,8 MB de basura) y el
    `REPLACE` de `CHAR(0)` con colación binaria quita los NUL, que harían caer
    el `COPY`. El alias conserva el nombre de la columna.
    """
    if not isinstance(columna, str) or not _COLUMNA.fullmatch(columna):
        raise ValueError(f"nombre de columna no admitido para el recorte: {columna!r}")
    if type(tope) is not int or tope <= 0:
        raise ValueError(f"el tope del recorte tiene que ser un entero positivo y es {tope!r}")
    return (
        f"CAST(REPLACE(SUBSTRING(CAST([{columna}] AS VARCHAR(MAX)), 1, {tope}) "
        f"COLLATE Latin1_General_BIN, CHAR(0), '') AS VARCHAR(MAX)) AS [{columna}]"
    )
