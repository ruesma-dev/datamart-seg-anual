# tests/test_f080_texto.py
"""
F-080 · El parseo del memo de la pestaña «Texto», sobre la función pura.

EL PARSEO DE VERDAD VA EN SQL (DA-1): el memo ya está en Postgres y son 30,6
MB; llevárselo a Python y devolverlo es ida y vuelta por nada. **Pero el
oráculo es Python**: los dos literales y la semántica viven en
`etl_sigrid/domain/texto_comentarios.py`, se prueban aquí sobre fixtures, y
`tests/test_f080_sql.py` comprueba que el SQL usa esos mismos literales. Es el
patrón de F-052, y le da a la campaña de mutación código real que morder.

FORMATO MEDIDO (2026-09-10, sobre `con.cod = 'FR26/06051'` y otras): los
comentarios se concatenan en **orden descendente** —el más reciente primero—
separados por una línea de guiones, y cada uno se cierra con
`[dd/mm/aaaa hh:mm:ss Usuario: <login>]`. El cuerpo lleva saltos `\\r\\n`, y el
último bloque puede traer una línea automática de la aplicación con OTRO
formato (`fecha hora<TAB>Línea no procedente de Albarán: N`).

LO QUE NO SE PUEDE PERDER (R25, R26, DA-2): nada de lo que no casa con el
sello. El sello solo **añade** columnas; el bloque sale entero pase lo que
pase, y unir los bloques en su orden reproduce el memo original.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from etl_sigrid.domain.texto_comentarios import (
    SELLO_COMENTARIO,
    SEPARADOR_BLOQUES,
    SEPARADOR_CANONICO,
    partir_memo,
)

RUTA_MODULO = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "domain" / "texto_comentarios.py"
)


# ---------------------------------------------------------------------------
# Fixtures: memos como los que llegan, armados con el separador medido
# ---------------------------------------------------------------------------

#: Un comentario con su sello, tal y como lo cierra Sigrid.
BLOQUE_NUEVO = (
    "Recibida la factura y conformada por Juan.\r\n"
    "Pendiente de la retencion del 5%.\r\n"
    "[11/09/2026 09:14:32 Usuario: jromero]"
)
BLOQUE_MEDIO = (
    "Se reclama al proveedor el albaran que falta.\r\n"
    "[03/09/2026 17:02:10 Usuario: mlopez]"
)
BLOQUE_VIEJO = "Alta del documento.\r\n[28/08/2026 08:00:00 Usuario: admin]"

#: La línea que añade la propia aplicación: otro formato, sin sello.
LINEA_AUTOMATICA = "28/08/2026 08:00:01\tLinea no procedente de Albaran: 3"

#: Texto escrito a mano, sin sello de ningún tipo.
BLOQUE_SIN_SELLO = "ojo con este proveedor, factura dos veces el mismo albaran"


def _memo(*bloques: str) -> str:
    return SEPARADOR_CANONICO.join(bloques)


MEMO_TRES = _memo(BLOQUE_NUEVO, BLOQUE_MEDIO, BLOQUE_VIEJO)


# ---------------------------------------------------------------------------
# R24 · los literales, escritos una sola vez y utilizables en POSIX
# ---------------------------------------------------------------------------


def test_f080_r24_los_dos_literales_son_regex_sin_lookarounds() -> None:
    """POSIX (el motor de Postgres) NO tiene lookarounds (DA-1).

    Si el oráculo los usara, el SQL no podría usar el mismo literal y las dos
    implementaciones divergirían en silencio, que es justo lo que R24 evita.
    """
    for literal in (SEPARADOR_BLOQUES, SELLO_COMENTARIO):
        for prohibido in ("(?=", "(?!", "(?<=", "(?<!", "(?P<"):
            assert prohibido not in literal, (
                f"«{prohibido}» no existe en POSIX: el SQL no podría usar este "
                "mismo literal (R24, DA-1)"
            )


def test_f080_r24_los_literales_se_pueden_embeber_en_sql() -> None:
    """Una comilla simple dentro obligaría a duplicarla en el SQL, y el test de
    R24 compararía dos cadenas distintas creyendo que son la misma."""
    for literal in (SEPARADOR_BLOQUES, SELLO_COMENTARIO, SEPARADOR_CANONICO):
        assert "'" not in literal, (
            "el literal viaja dentro de una cadena SQL: sin comillas simples (R24)"
        )


def test_f080_r24_el_sello_captura_fecha_hora_y_usuario() -> None:
    """Tres grupos, en ese orden: el SQL lee `regexp_match(...)[1..3]`."""
    casado = re.search(SELLO_COMENTARIO, BLOQUE_NUEVO)
    assert casado is not None
    assert casado.groups() == ("11/09/2026", "09:14:32", "jromero")


def test_f080_r24_el_modulo_de_dominio_no_importa_infraestructura() -> None:
    """`domain` no depende de nada (convención de arquitectura hexagonal)."""
    fuente = RUTA_MODULO.read_text(encoding="utf-8")
    for prohibido in ("infrastructure", "psycopg", "requests", "config.settings"):
        assert prohibido not in fuente, (
            f"`{prohibido}` en la capa domain rompe la arquitectura y convierte "
            "el oráculo en algo que necesita una BBDD para probarse"
        )


# ---------------------------------------------------------------------------
# R23 · el orden: 1 es el más reciente
# ---------------------------------------------------------------------------


def test_f080_r23_los_tres_comentarios_salen_en_orden_descendente() -> None:
    """Sigrid concatena el más nuevo arriba, y el split conserva ese orden.

    Invertirlo pondría el comentario de alta como «el último estado del
    documento», que es la lectura contraria a la verdadera.
    """
    bloques = partir_memo(MEMO_TRES)
    assert [b.orden for b in bloques] == [1, 2, 3]
    assert [b.fecha for b in bloques] == [
        dt.date(2026, 9, 11),
        dt.date(2026, 9, 3),
        dt.date(2026, 8, 28),
    ]
    assert bloques[0].fecha > bloques[-1].fecha, (
        "orden 1 tiene que ser el MÁS RECIENTE (R23)"
    )


def test_f080_r23_cada_bloque_trae_su_hora_y_su_usuario() -> None:
    bloques = partir_memo(MEMO_TRES)
    assert [b.hora for b in bloques] == ["09:14:32", "17:02:10", "08:00:00"]
    assert [b.usuario for b in bloques] == ["jromero", "mlopez", "admin"]
    assert all(b.sello_reconocido for b in bloques)


def test_f080_r23_el_cuerpo_es_el_bloque_sin_el_sello() -> None:
    """El sello es metadato: se publica en columnas, y además el bloque entero
    queda disponible para reconstruir (DA-2)."""
    primero = partir_memo(MEMO_TRES)[0]
    assert primero.cuerpo == (
        "Recibida la factura y conformada por Juan.\r\n"
        "Pendiente de la retencion del 5%."
    )
    assert primero.bloque == BLOQUE_NUEVO
    assert "Usuario:" not in primero.cuerpo


# ---------------------------------------------------------------------------
# R25 · lo que no casa se publica igual
# ---------------------------------------------------------------------------


def test_f080_r25_un_bloque_sin_sello_se_publica_entero() -> None:
    """Texto a mano, sin plantilla: fecha y usuario a NULL, cuerpo completo.

    Descartarlo sería perder el comentario más interesante de todos —el que
    alguien escribió fuera del formulario— sin que nadie se enterara.
    """
    bloques = partir_memo(_memo(BLOQUE_NUEVO, BLOQUE_SIN_SELLO))
    assert len(bloques) == 2
    raro = bloques[1]
    assert raro.sello_reconocido is False
    assert raro.fecha is None
    assert raro.hora is None
    assert raro.usuario is None
    assert raro.cuerpo == BLOQUE_SIN_SELLO, (
        "sin sello, el CUERPO es el bloque entero (R25)"
    )
    assert raro.bloque == BLOQUE_SIN_SELLO


def test_f080_r25_la_linea_automatica_de_la_aplicacion_no_es_un_sello() -> None:
    """Trae fecha y hora, pero en otro formato y sin `Usuario:`.

    Dejarla casar «a la buena de Dios» daría un comentario con autor inventado.
    """
    bloques = partir_memo(_memo(BLOQUE_NUEVO, BLOQUE_VIEJO, LINEA_AUTOMATICA))
    assert len(bloques) == 3
    automatica = bloques[2]
    assert automatica.sello_reconocido is False
    assert automatica.fecha is None
    assert automatica.usuario is None
    assert automatica.cuerpo == LINEA_AUTOMATICA


def test_f080_r25_un_sello_a_medias_tampoco_cuela() -> None:
    """Una fecha suelta entre corchetes no es el sello: sin hora y sin usuario
    no hay autoría que publicar."""
    bloque = "cambio de forma de pago [11/09/2026]"
    (unico,) = partir_memo(bloque)
    assert unico.sello_reconocido is False
    assert unico.cuerpo == bloque


# ---------------------------------------------------------------------------
# R26 · el invariante de reconstrucción
# ---------------------------------------------------------------------------


def test_f080_r26_unir_los_bloques_reproduce_el_memo_original() -> None:
    """NI UN CARÁCTER PERDIDO fuera de los separadores.

    Es la verificación que hace innecesario fiarse del parseo: si el memo se
    reconstruye, no se ha tirado nada por el camino.
    """
    for memo in (
        MEMO_TRES,
        _memo(BLOQUE_NUEVO),
        _memo(BLOQUE_NUEVO, BLOQUE_SIN_SELLO),
        _memo(BLOQUE_NUEVO, BLOQUE_VIEJO, LINEA_AUTOMATICA),
    ):
        rehecho = SEPARADOR_CANONICO.join(b.bloque for b in partir_memo(memo))
        assert rehecho == memo, "el memo no se reconstruye: se ha perdido algo (R26)"


def test_f080_r26_la_suma_de_los_cuerpos_no_pierde_caracteres() -> None:
    """Versión fuerte del invariante, independiente del separador: todo lo que
    no es separador está en algún bloque, y en el mismo orden."""
    bloques = partir_memo(MEMO_TRES)
    sin_separadores = "".join(re.split(SEPARADOR_BLOQUES, MEMO_TRES))
    assert "".join(b.bloque for b in bloques) == sin_separadores


# ---------------------------------------------------------------------------
# DA-3 · el separador se reconoce con tolerancia
# ---------------------------------------------------------------------------


def test_f080_da3_el_separador_medido_es_el_canonico() -> None:
    """Lo medido es una línea de 33 guiones con un espacio a cada lado."""
    assert SEPARADOR_CANONICO == "\n --------------------------------- \n"
    assert re.fullmatch(SEPARADOR_BLOQUES, SEPARADOR_CANONICO), (
        "el patrón tolerante tiene que reconocer el separador medido (DA-3)"
    )


@pytest.mark.parametrize(
    "separador",
    [
        "\n---\n",                       # tres guiones pelados: el mínimo
        "\n-----\n",                     # otra longitud
        "\n   ----------   \n",          # con más espacios
        "\r\n ---------- \r\n",          # con CRLF, que es lo que trae el cuerpo
    ],
)
def test_f080_da3_otras_longitudes_de_separador_tambien_parten(separador: str) -> None:
    """Nada garantiza los 33 guiones: parta de más o de menos, el bloque se
    publica entero (DA-2)."""
    memo = f"{BLOQUE_NUEVO}{separador}{BLOQUE_VIEJO}"
    bloques = partir_memo(memo)
    assert len(bloques) == 2, f"«{separador!r}» tendría que partir el memo (DA-3)"
    assert bloques[0].bloque == BLOQUE_NUEVO
    assert bloques[1].bloque == BLOQUE_VIEJO


def test_f080_da3_dos_guiones_dentro_del_texto_no_parten_nada() -> None:
    """Un guion de diálogo o una resta no son un separador: hacen falta tres
    guiones SOLOS en su línea."""
    memo = "precio -- revisado\r\nsaldo - 200 EUR\r\n[11/09/2026 09:14:32 Usuario: jromero]"
    assert len(partir_memo(memo)) == 1


# ---------------------------------------------------------------------------
# El memo vacío y el de un solo bloque
# ---------------------------------------------------------------------------


def test_f080_r22_un_solo_comentario_da_un_solo_bloque() -> None:
    (unico,) = partir_memo(BLOQUE_NUEVO)
    assert unico.orden == 1
    assert unico.sello_reconocido is True
    assert unico.usuario == "jromero"


@pytest.mark.parametrize("vacio", [None, "", "   ", "\r\n", "\n \n"])
def test_f080_r22_un_memo_vacio_no_da_comentarios(vacio: str | None) -> None:
    """Sin esto, los 2,06 M de documentos sin texto publicarían una fila con un
    comentario en blanco cada uno."""
    assert partir_memo(vacio) == []


def test_f080_r22_un_separador_suelto_no_inventa_bloques_vacios() -> None:
    """Un memo que empieza o acaba con separador no produce comentarios vacíos,
    pero tampoco descoloca el orden de los reales."""
    bloques = partir_memo(f"{SEPARADOR_CANONICO}{BLOQUE_NUEVO}{SEPARADOR_CANONICO}")
    assert [b.orden for b in bloques] == [1]
    assert bloques[0].bloque == BLOQUE_NUEVO
