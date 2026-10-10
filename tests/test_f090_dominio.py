# tests/test_f090_dominio.py
"""
F-090 · El oráculo puro del índice de adjuntos (`domain/documento_adjuntos.py`):
las familias de compras, la clase de fichero por extensión y los filtros de
ingesta de `rcg` y `gra`. R7-R10 (y el literal de los filtros que usan R1-R3).

Sin red ni base: el dominio no tiene dependencias.
"""

from __future__ import annotations

import pytest

from etl_sigrid.domain.documento_adjuntos import (
    CLASE_OTRO,
    CLASE_SIN_EXTENSION,
    COLUMNAS_EXCLUIDAS_GRA,
    EXTENSIONES_POR_CLASE,
    FAMILIAS_ADJUNTOS,
    clase_fichero,
    extension,
    filtro_gra,
    filtro_rcg,
    lista_familias_sql,
)

# ===========================================================================
# R7 · Las familias
# ===========================================================================


def test_f090_r7_familias_son_las_cinco_de_compras() -> None:
    assert FAMILIAS_ADJUNTOS == {
        15: "FACTURA",
        44: "CONTRATO",
        46: "COMPARATIVO",
        12: "OFERTA",
        14: "ALBARAN",
    }


def test_f090_r7_ninguna_familia_de_personal_ni_posventa() -> None:
    """D2: empleados (43), nóminas (306) y posventa (708) no entran nunca."""
    for tip in (43, 306, 708, 5, 20, 42):
        assert tip not in FAMILIAS_ADJUNTOS, f"la familia {tip} no es de compras (R5)"


def test_f090_r7_lista_sql_ordenada_y_determinista() -> None:
    assert lista_familias_sql() == "12, 14, 15, 44, 46"


# ===========================================================================
# R8 · extension()
# ===========================================================================


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("factura.pdf", "pdf"),
        ("FACTURA.PDF", "pdf"),
        ("Comparativo 0720.v2.XLSX", "xlsx"),
        ("  oferta.Docx  ", "docx"),
        ("archivo.tar.gz", "gz"),
        (".pdf", "pdf"),
        ("sin extension", None),
        ("acaba en punto.", None),
        ("espacio tras punto. pdf", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_f090_r8_extension(nombre: str | None, esperado: str | None) -> None:
    assert extension(nombre) == esperado


def test_f090_r8_extension_sin_espacios_y_en_minusculas() -> None:
    resultado = extension("Mi Fichero.PdF ")
    assert resultado == "pdf"
    assert resultado is not None and " " not in resultado


# ===========================================================================
# R9 · clase_fichero()
# ===========================================================================


@pytest.mark.parametrize(
    ("nombre", "clase"),
    [
        ("a.pdf", "PDF"),
        ("a.xls", "EXCEL"),
        ("a.xlsx", "EXCEL"),
        ("a.xlsm", "EXCEL"),
        ("a.xlsb", "EXCEL"),
        ("a.csv", "EXCEL"),
        ("a.doc", "WORD"),
        ("a.docx", "WORD"),
        ("a.rtf", "WORD"),
        ("a.odt", "WORD"),
        ("a.msg", "CORREO"),
        ("a.eml", "CORREO"),
        ("a.jpg", "IMAGEN"),
        ("a.jpeg", "IMAGEN"),
        ("a.png", "IMAGEN"),
        ("a.tif", "IMAGEN"),
        ("a.tiff", "IMAGEN"),
        ("a.gif", "IMAGEN"),
        ("a.bmp", "IMAGEN"),
        ("a.zip", "OTRO"),
        ("a.dwg", "OTRO"),
        ("sin punto", "SIN_EXTENSION"),
        ("acaba.", "SIN_EXTENSION"),
        ("", "SIN_EXTENSION"),
        (None, "SIN_EXTENSION"),
    ],
)
def test_f090_r9_clase_fichero(nombre: str | None, clase: str) -> None:
    assert clase_fichero(nombre) == clase


def test_f090_r9_constantes_de_clase() -> None:
    assert CLASE_OTRO == "OTRO"
    assert CLASE_SIN_EXTENSION == "SIN_EXTENSION"


def test_f090_r9_la_clase_ignora_mayusculas() -> None:
    assert clase_fichero("CONCURSO.XLSX") == "EXCEL"


# ===========================================================================
# R10 · Un único dict, sin extensiones repetidas
# ===========================================================================


def test_f090_r10_clases_exactas() -> None:
    assert set(EXTENSIONES_POR_CLASE) == {"PDF", "EXCEL", "WORD", "CORREO", "IMAGEN"}
    assert EXTENSIONES_POR_CLASE["PDF"] == frozenset({"pdf"})
    assert EXTENSIONES_POR_CLASE["EXCEL"] == frozenset({"xls", "xlsx", "xlsm", "xlsb", "csv"})
    assert EXTENSIONES_POR_CLASE["WORD"] == frozenset({"doc", "docx", "rtf", "odt"})
    assert EXTENSIONES_POR_CLASE["CORREO"] == frozenset({"msg", "eml"})
    assert EXTENSIONES_POR_CLASE["IMAGEN"] == frozenset(
        {"jpg", "jpeg", "png", "tif", "tiff", "gif", "bmp"}
    )


def test_f090_r10_ninguna_extension_en_dos_clases() -> None:
    vistas: dict[str, str] = {}
    for clase, extensiones in EXTENSIONES_POR_CLASE.items():
        for ext in extensiones:
            assert ext not in vistas, f"`{ext}` está en {vistas[ext]} y en {clase} (R10)"
            vistas[ext] = clase


def test_f090_r10_las_clases_reservadas_no_son_clases_de_extension() -> None:
    assert CLASE_OTRO not in EXTENSIONES_POR_CLASE
    assert CLASE_SIN_EXTENSION not in EXTENSIONES_POR_CLASE


def test_f090_r10_extensiones_en_minusculas_y_sin_punto() -> None:
    for extensiones in EXTENSIONES_POR_CLASE.values():
        for ext in extensiones:
            assert ext == ext.lower().strip() and "." not in ext


# ===========================================================================
# Filtros de ingesta y columnas excluidas (los usan R1-R4)
# ===========================================================================


def test_f090_r1_filtro_rcg_literal() -> None:
    assert filtro_rcg() == "con IN (SELECT ide FROM dbo.con WHERE tip IN (12, 14, 15, 44, 46))"


def test_f090_r2_filtro_gra_literal() -> None:
    assert filtro_gra() == (
        "ide IN (SELECT r.gra FROM dbo.rcg r JOIN dbo.con c ON c.ide = r.con "
        "WHERE c.tip IN (12, 14, 15, 44, 46))"
    )


def test_f090_r2_columnas_excluidas_de_gra() -> None:
    assert frozenset({"ima", "pul", "tex", "cam"}) == COLUMNAS_EXCLUIDAS_GRA
