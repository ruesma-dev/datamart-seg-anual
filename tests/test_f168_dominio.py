# tests/test_f168_dominio.py
"""
F-168 · El dominio del texto largo (`etl_sigrid/domain/texto_largo.py`).

Una sola limpieza (R5), una sola identidad (R6), el tope y el patrón de control
escritos una vez (R7), la marca de recortado (R8) y la expresión que pide la
columna recortada a Sigrid (R3). Sin red ni BBDD.
"""

from __future__ import annotations

import hashlib
import re
import uuid

import pytest

from etl_sigrid.domain import texto_largo as tl

# ---------------------------------------------------------------------------
# R7 · los literales
# ---------------------------------------------------------------------------


def test_f168_r7_tope_y_patron_de_control() -> None:
    assert tl.TOPE_CARACTERES == 16000
    assert tl.PATRON_CONTROL == r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]"
    # Ni el tabulador ni el salto de línea son «control» a quitar.
    assert not re.search(tl.PATRON_CONTROL, "\t\n")
    for codigo in (*range(0x01, 0x09), 0x0B, 0x0C, *range(0x0E, 0x20), 0x7F):
        assert re.fullmatch(tl.PATRON_CONTROL, chr(codigo)), hex(codigo)


# ---------------------------------------------------------------------------
# R5 · la limpieza
# ---------------------------------------------------------------------------


def test_f168_r5_crlf_y_cr_pasan_a_salto() -> None:
    assert tl.limpiar("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_f168_r5_quita_los_controles_salvo_tab_y_salto() -> None:
    assert tl.limpiar("a\x01b\x07c\td\x1fe\x7ff\x0bg\x0ch\ni") == "abc\tdefgh\ni"


def test_f168_r5_recorta_los_extremos() -> None:
    assert tl.limpiar("  \t\n hormigón HA-25 \n\t  ") == "hormigón HA-25"
    # Por dentro no se toca nada.
    assert tl.limpiar("a  \n\n  b") == "a  \n\n  b"


@pytest.mark.parametrize("vacio", [None, "", "   ", "\r\n\t ", "\x01\x02", " \x7f \r "])
def test_f168_r5_vacio_es_none(vacio: str | None) -> None:
    assert tl.limpiar(vacio) is None


def test_f168_r5_corta_a_tope_caracteres() -> None:
    largo = "á" * (tl.TOPE_CARACTERES + 50)
    limpio = tl.limpiar(largo)
    assert limpio is not None and len(limpio) == tl.TOPE_CARACTERES


def test_f168_r5_el_corte_no_deja_espacios_al_final() -> None:
    texto = "x" * (tl.TOPE_CARACTERES - 2) + "   resto"
    assert tl.limpiar(texto) == "x" * (tl.TOPE_CARACTERES - 2)


def test_f168_r5_los_extremos_se_quitan_antes_del_corte() -> None:
    texto = "\n" * 10 + "y" * tl.TOPE_CARACTERES
    assert tl.limpiar(texto) == "y" * tl.TOPE_CARACTERES


# ---------------------------------------------------------------------------
# R6 · la identidad
# ---------------------------------------------------------------------------


def test_f168_r6_texto_id_es_el_md5_del_texto_limpio() -> None:
    texto = "FORJ. RETICULAR 35+10\nhormigón"
    esperado = uuid.UUID(hashlib.md5(texto.encode("utf-8")).hexdigest())
    assert tl.texto_id(texto) == esperado


def test_f168_r6_texto_id_estable_y_distinto() -> None:
    assert tl.texto_id("a") == tl.texto_id("a")
    assert tl.texto_id("a") != tl.texto_id("b")
    assert tl.texto_id(None) is None


def test_f168_r6_mismo_texto_limpio_mismo_id() -> None:
    assert tl.texto_id(tl.limpiar("  a\r\nb ")) == tl.texto_id(tl.limpiar("a\nb"))


# ---------------------------------------------------------------------------
# R8 · recortado
# ---------------------------------------------------------------------------


def test_f168_r8_recortado_desde_tope() -> None:
    assert tl.es_recortado("x" * tl.TOPE_CARACTERES)
    assert tl.es_recortado("x" * (tl.TOPE_CARACTERES + 1))
    assert not tl.es_recortado("x" * (tl.TOPE_CARACTERES - 1))
    assert not tl.es_recortado(None)


# ---------------------------------------------------------------------------
# R3 · la expresión de recorte
# ---------------------------------------------------------------------------


def test_f168_r3_expresion_recorte_literal() -> None:
    assert tl.expresion_recorte("tex", 16000) == (
        "CAST(REPLACE(SUBSTRING(CAST([tex] AS VARCHAR(MAX)), 1, 16000) "
        "COLLATE Latin1_General_BIN, CHAR(0), '') AS VARCHAR(MAX)) AS [tex]"
    )


@pytest.mark.parametrize("columna", ["", "te x", "tex]", "tex;--", "[tex]"])
def test_f168_r3_expresion_recorte_rechaza_columnas_raras(columna: str) -> None:
    with pytest.raises(ValueError, match="columna"):
        tl.expresion_recorte(columna, 16000)


@pytest.mark.parametrize("tope", [0, -1, True, 1.5, "16000", None])
def test_f168_r3_expresion_recorte_rechaza_topes_raros(tope: object) -> None:
    with pytest.raises(ValueError, match="tope"):
        tl.expresion_recorte("tex", tope)  # type: ignore[arg-type]
