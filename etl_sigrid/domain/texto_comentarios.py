# etl_sigrid/domain/texto_comentarios.py
"""
El memo de la pestaña «Texto» de un documento de Sigrid, partido en comentarios.

POR QUÉ ESTE MÓDULO EXISTE SI EL PARSEO VA EN SQL (F-080, R24, DA-1). El memo
ya está en Postgres y son 30,6 MB: llevárselo a Python para partirlo y
devolverlo es ida y vuelta por nada, así que la tabla
`compras.documento_comentarios` la construye `sql/compras/07_texto.sql` con
`regexp_split_to_table` y `regexp_match`. Lo que NO puede pasar es que los dos
literales —el separador y el sello— vivan escritos en el SQL y en ningún otro
sitio: ahí nadie los prueba, nadie sabe de dónde salieron y cambiarlos no rompe
nada. Aquí están escritos **una sola vez**, probados sobre fixtures en
`tests/test_f080_texto.py`, y `tests/test_f080_sql.py` comprueba que el SQL usa
**estos mismos**. Esta función es el oráculo ejecutable de lo que el SQL hace.

LOS DOS LITERALES SON REGEX POSIX, no de Python: los tiene que poder ejecutar
el motor de Postgres, que no tiene lookarounds. Por eso no hay ni un `(?=` ni
un `(?P<nombre>`, y por eso los grupos son posicionales (`regexp_match` los
devuelve como array `[1..3]`).

EL FORMATO, MEDIDO el 2026-09-10 (F-080, exploración): los comentarios se
concatenan en **orden descendente** —el más reciente primero—, separados por una
línea de guiones, y cada uno se cierra con
`[dd/mm/aaaa hh:mm:ss Usuario: <login>]`. El cuerpo lleva saltos `\\r\\n`, y el
último bloque puede traer una línea que añade la propia aplicación con otro
formato (`fecha hora<TAB>Línea no procedente de Albarán: N`).

LA REGLA QUE MANDA SOBRE TODO LO DEMÁS (R25, R26, DA-2): **nada se pierde**. El
sello solo AÑADE columnas; cuando no casa —texto escrito a mano, la línea
automática, un sello a medias—, el bloque se publica entero con fecha y usuario
a NULL. Unir los bloques en su orden reproduce el memo original.

Capa `domain`: sin un solo import de infraestructura ni de configuración.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

#: El separador de bloques, TOLERANTE (DA-3). Lo medido es una línea de 33
#: guiones con un espacio a cada lado, pero nada garantiza esa longitud: se
#: reconoce una línea de **tres o más** guiones con espacios opcionales, en
#: `\n` o en `\r\n`. Parta de más o de menos, el bloque se publica entero.
#: Tres guiones SOLOS en su línea: un guion de diálogo o una resta no parten.
SEPARADOR_BLOQUES = r"\r?\n *-{3,} *\r?\n"

#: El separador tal y como lo escribe Sigrid. Es el que se usa para
#: **reconstruir** el memo (R26) y el que arma las fixtures de los tests.
SEPARADOR_CANONICO = "\n --------------------------------- \n"

#: El sello que cierra cada comentario, con sus TRES grupos de captura en orden:
#: fecha (dd/mm/aaaa), hora (hh:mm:ss) y login del usuario. El ` +` admite más
#: de un espacio; el `[^]]*` coge el login entero hasta el corchete de cierre.
#: Ni comillas simples ni lookarounds: este literal viaja dentro de una cadena
#: SQL y lo ejecuta el motor de Postgres (R24).
SELLO_COMENTARIO = (
    r"\[([0-9]{2}/[0-9]{2}/[0-9]{4}) +([0-9]{2}:[0-9]{2}:[0-9]{2}) +"
    r"Usuario: *([^]]*)\]"
)

#: El formato de la fecha del sello, para el oráculo. El SQL usa el equivalente
#: `to_date(..., 'DD/MM/YYYY')` con la comprobación de ida y vuelta que hace
#: aquí `strptime`: una fecha que no existe en el calendario NO es un sello
#: reconocido, ni aquí ni allí.
FORMATO_FECHA_SELLO = "%d/%m/%Y"


@dataclass(slots=True, frozen=True)
class Bloque:
    """Un comentario del memo, con lo que el sello añade si se reconoce.

    `bloque` es el trozo ÍNTEGRO tal y como sale del corte: es lo que garantiza
    el invariante de reconstrucción de R26. `cuerpo` es lo mismo sin el sello
    cuando hay sello, y el bloque entero cuando no (R25).
    """

    orden: int
    bloque: str
    cuerpo: str
    fecha: dt.date | None
    hora: str | None
    usuario: str | None
    sello_reconocido: bool


def _fecha_del_sello(texto: str) -> dt.date | None:
    """La fecha del sello, o None si no existe en el calendario.

    `31/02/2026` casa con el patrón y no es una fecha: publicarla normalizada a
    marzo sería inventarse el día en que alguien escribió el comentario.
    """
    try:
        return dt.datetime.strptime(texto, FORMATO_FECHA_SELLO).date()
    except ValueError:
        return None


def _bloque(orden: int, texto: str) -> Bloque:
    casado = re.search(SELLO_COMENTARIO, texto)
    fecha = _fecha_del_sello(casado.group(1)) if casado else None
    if casado is None or fecha is None:
        # R25: sin sello utilizable, el bloque ENTERO es el cuerpo y la autoría
        # se queda a NULL. Descartarlo perdería el comentario más interesante
        # —el que alguien escribió fuera del formulario— sin avisar a nadie.
        return Bloque(
            orden=orden,
            bloque=texto,
            cuerpo=texto,
            fecha=None,
            hora=None,
            usuario=None,
            sello_reconocido=False,
        )
    cuerpo = (texto[: casado.start()] + texto[casado.end():]).strip()
    return Bloque(
        orden=orden,
        bloque=texto,
        cuerpo=cuerpo,
        fecha=fecha,
        hora=casado.group(2),
        usuario=casado.group(3),
        sello_reconocido=True,
    )


def partir_memo(texto: str | None) -> list[Bloque]:
    """Parte el memo en comentarios, del más reciente al más antiguo.

    `orden` 1 es el MÁS RECIENTE, porque Sigrid concatena en descendente y el
    corte conserva ese orden. Invertirlo pondría el comentario de alta como si
    fuera el último estado del documento, que es la lectura contraria.

    Un memo vacío o en blanco no da ningún comentario: si diera uno, los 2,06 M
    de documentos sin texto publicarían una fila en blanco cada uno.
    """
    if texto is None or not texto.strip():
        return []
    trozos = [t for t in re.split(SEPARADOR_BLOQUES, texto) if t.strip()]
    return [_bloque(orden, trozo) for orden, trozo in enumerate(trozos, start=1)]
