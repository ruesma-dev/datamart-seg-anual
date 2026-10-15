# tests/test_f138_dominio.py
"""
F-138 · El oráculo de las alarmas y de la marca «liquidatoria» (R3-R10).

`etl_sigrid/domain/liquidatoria.py` es la ÚNICA fuente de las familias, la
traducción, los patrones y la precedencia; el SQL y el YAML los copian y
`tests/test_f138_ingesta_sql.py` vigila que sean los mismos. Aquí se prueba la
regla con los textos MEDIDOS en Sigrid el 2026-10-14 (`progress/spec_F-138.md`).

Sin red ni BBDD.
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from etl_sigrid.domain import liquidatoria as liq

# ===========================================================================
# R3-R4 · las familias
# ===========================================================================


def test_f138_r4_las_diecisiete_familias_con_su_nombre() -> None:
    assert liq.FAMILIAS_ALARMAS == {
        1: "INFORME", 4: "CLIENTE", 5: "PROVEEDOR", 11: "FACTURA_VENTA",
        12: "OFERTA", 14: "ALBARAN", 15: "FACTURA", 17: "CUENTA_AUXILIAR",
        20: "ASIENTO", 25: "EFECTO_PAGO", 33: "RECURSO", 35: "PARTE_TRABAJO",
        40: "OTRA", 42: "OBRA", 44: "CONTRATO", 46: "COMPARATIVO",
        54: "CONTRATO_VENTA",
    }
    assert len(liq.FAMILIAS_ALARMAS) == 17


def test_f138_r3_la_43_no_entra_nunca() -> None:
    assert liq.FAMILIA_EMPLEADOS == 43
    assert 43 not in liq.FAMILIAS_ALARMAS
    tips = re.search(r"tip IN \(([^)]*)\)", liq.filtro_conala())
    assert tips, liq.filtro_conala()
    assert "43" not in [t.strip() for t in tips.group(1).split(",")]


def test_f138_r1_el_filtro_de_conala_es_la_lista_explicita_ordenada() -> None:
    assert liq.filtro_conala() == (
        "conide IN (SELECT ide FROM dbo.con WHERE tip IN "
        "(1, 4, 5, 11, 12, 14, 15, 17, 20, 25, 33, 35, 40, 42, 44, 46, 54))"
    )


def test_f138_r4_familias_de_la_marca_y_restringidas() -> None:
    assert liq.FAMILIAS_MARCA == (14, 15)
    assert liq.FAMILIAS_RESTRINGIDAS == frozenset({33, 35})
    assert liq.FAMILIAS_RESTRINGIDAS <= set(liq.FAMILIAS_ALARMAS)
    assert not set(liq.FAMILIAS_MARCA) & liq.FAMILIAS_RESTRINGIDAS


@pytest.mark.parametrize("tip", [33, 35])
def test_f138_r4_recursos_y_partes_son_restringidas(tip: int) -> None:
    assert liq.es_restringida(tip) is True


@pytest.mark.parametrize("tip", [25, 14, 15, 44, 11, 43, 0])
def test_f138_r32_el_resto_no_es_restringida_ni_la_25(tip: int) -> None:
    assert liq.es_restringida(tip) is False


# ===========================================================================
# R5 · normalizar
# ===========================================================================


def test_f138_r5_la_traduccion_tiene_44_caracteres_por_lado() -> None:
    assert len(liq.TRADUCCION_ORIGEN) == 44
    assert len(liq.TRADUCCION_DESTINO) == 44
    assert len(set(liq.TRADUCCION_ORIGEN)) == 44, "un carácter repetido en el origen"
    assert liq.TRADUCCION_DESTINO.isascii()
    for caracter in "áéíóúÁÉÍÓÚàÀüÜñÑçÇâÔ":
        assert caracter in liq.TRADUCCION_ORIGEN


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (None, ""),
        ("", ""),
        ("   ", ""),
        ("Única y liquidatoria.", "UNICA Y LIQUIDATORIA"),
        ("ES LIQUIDACIÓN.", "ES LIQUIDACION"),
        ('"Carta liquidación."', "CARTA LIQUIDACION"),
        ("LIQUIDATORIA\r\n", "LIQUIDATORIA"),
        ("fra.  única\ty   liquidatoria", "FRA UNICA Y LIQUIDATORIA"),
        ("Pingüino, ñandú, garçon, crème, côte", "PINGUINO NANDU GARCON CREME COTE"),
        ("ÀÈÌÒÙ ÂÊÎÔÛ ÄËÏÖÜ Ç Ñ", "AEIOU AEIOU AEIOU C N"),
        ("FR26/10035 - 1ª", "FR26 10035 1"),
        ("€€abc€€", "ABC"),
    ],
)
def test_f138_r5_normalizar(texto: str | None, esperado: str) -> None:
    assert liq.normalizar(texto) == esperado


def test_f138_r5_el_upper_va_despues_de_dejar_solo_ascii() -> None:
    # La «ß» se iría a «SS» con un upper ANTES de limpiar; aquí es un separador.
    assert liq.normalizar("aßb") == "A B"
    assert liq.normalizar("ǅ liq") == "LIQ"


# ===========================================================================
# R6-R8 · clasificar, con los casos medidos
# ===========================================================================


@pytest.mark.parametrize(
    ("texto", "clase"),
    [
        ("FACTURA LIQUIDATORIA", "LIQUIDATORIA"),
        ("Única y liquidatoria.", "LIQUIDATORIA"),
        ("ES LIQUIDACIÓN.", "LIQUIDATORIA"),
        ("ULTIMA Y LIQ", "LIQUIDATORIA"),
        ("LIQUDATORIA", "LIQUIDATORIA"),
        ("NO ES LIQUIDATORIA", "NEGADA"),
        ("Aunque no es liquidación no difiero el IVA", "NEGADA"),
        ("CARTA LIQUIDACIÓN", "CARTA_LIQUIDACION"),
        ('"Carta liquidación."', "CARTA_LIQUIDACION"),
        ("TRABAJOS POSTERIORES A LA LIQUIDACION", "DUDOSA"),
        ("PREVISIÓN DE LIQUIDACIÓN", "DUDOSA"),
        ("NO SE SI ES LIQUIDACION", "DUDOSA"),
        ("VER TEXTO", "REMITE"),
        ("MIRAR NOTA", "REMITE"),
        ("INVERSION SUJETO PASIVO", None),
        ("", None),
        (None, None),
    ],
)
def test_f138_r8_casos_de_la_spec(texto: str | None, clase: str | None) -> None:
    assert liq.clasificar(texto) == clase


@pytest.mark.parametrize(
    ("texto", "clase"),
    [
        # mención solo al principio de palabra
        ("PLIQUE", None),
        ("APLIQUESE DESCUENTO", None),
        ("liquidatoria", "LIQUIDATORIA"),
        ("FRA. LIQUIDATORIA", "LIQUIDATORIA"),
        # la negación admite «SERA» y una palabra entre medias
        ("NO SERA LIQUIDATORIA", "NEGADA"),
        ("NO FACTURA LIQUIDATORIA", "NEGADA"),
        ("NO ES FRA LIQUIDATORIA", "NEGADA"),
        ("FINALMENTE NO ES LIQUIDACION", "NEGADA"),
        # pero no dos palabras: entonces no es negación
        ("NO HAY MAS LIQUIDATORIA", "LIQUIDATORIA"),
        # «NO» dentro de otra palabra no niega
        ("ANO ES LIQUIDATORIA", "LIQUIDATORIA"),
        # la negación gana a la carta y a la dudosa
        ("NO ES LIQUIDATORIA, PEDIR CARTA LIQUIDACION", "NEGADA"),
        ("NO ES LIQUIDATORIA, PREVISION", "NEGADA"),
        # la carta gana a la dudosa
        ("CARTA DE LIQUIDACION POSTERIOR", "CARTA_LIQUIDACION"),
        ("CARTA DE LIQUIDACION", "CARTA_LIQUIDACION"),
        ("DESCARTA LIQUIDACION", "LIQUIDATORIA"),
        # dudosas
        ("TIENE QUE VENIR COMO LIQUIDACION", "DUDOSA"),
        ("QUEDA PENDIENTE LIQUIDATORIA", "DUDOSA"),
        # remite: solo sin mención y con palabra completa
        ("VER EL TEXTO", "REMITE"),
        ("30 DIAS VER NOTA", "REMITE"),
        ("VER TEXTOS", None),
        ("VER TEXTO LIQUIDATORIA", "LIQUIDATORIA"),
        ("REVER TEXTO", None),
        ("VERNOTA", None),
    ],
)
def test_f138_r6_la_regla_en_los_bordes(texto: str, clase: str | None) -> None:
    assert liq.clasificar(texto) == clase


@pytest.mark.parametrize(
    "patron",
    ["PATRON_MENCION", "PATRON_NEGADA", "PATRON_CARTA", "PATRON_DUDOSA", "PATRON_REMITE",
     "PATRON_NO_ALFANUMERICO"],
)
def test_f138_r7_patrones_validos_en_python_y_postgres(patron: str) -> None:
    texto = getattr(liq, patron)
    re.compile(texto)
    for prohibido in ("\\b", "\\w", "(?", "\\s", "\\d"):
        assert prohibido not in texto, f"{patron} lleva {prohibido}"
    assert "'" not in texto, "una comilla rompería el literal del SQL"


def test_f138_r7_los_literales_de_la_spec() -> None:
    assert liq.PATRON_MENCION == "(^| )LIQ"
    assert liq.PATRON_NEGADA == "(^| )NO (ES |SERA )?([A-Z0-9]+ )?LIQ"
    assert liq.PATRON_CARTA == "(^| )CARTA (DE )?LIQ"
    assert liq.PATRON_DUDOSA == "PREVISION|POSTERIOR|TIENE QUE VENIR|QUEDA PENDIENTE|NO SE SI"
    assert liq.PATRON_REMITE == "(^| )(VER|MIRAR) (EL )?(TEXTO|NOTA)( |$)"


# ===========================================================================
# R9 · la marca del documento
# ===========================================================================


def test_f138_r9_precedencia_y_clases_de_cierre() -> None:
    assert liq.PRECEDENCIA == (
        "NEGADA", "LIQUIDATORIA", "CARTA_LIQUIDACION", "DUDOSA", "REMITE",
    )
    assert liq.CLASES_CIERRE == frozenset({"LIQUIDATORIA", "CARTA_LIQUIDACION"})


@pytest.mark.parametrize(
    ("clases", "marca"),
    [
        ([], None),
        ([None, None], None),
        (["REMITE"], "REMITE"),
        (["REMITE", "DUDOSA"], "DUDOSA"),
        (["DUDOSA", "CARTA_LIQUIDACION"], "CARTA_LIQUIDACION"),
        (["CARTA_LIQUIDACION", "LIQUIDATORIA", None], "LIQUIDATORIA"),
        (["LIQUIDATORIA", "NEGADA"], "NEGADA"),
        (["REMITE", "DUDOSA", "CARTA_LIQUIDACION", "LIQUIDATORIA", "NEGADA"], "NEGADA"),
        (("LIQUIDATORIA",), "LIQUIDATORIA"),
        (["OTRA_COSA"], None),
    ],
)
def test_f138_r9_marca_documento(clases: list[str | None], marca: str | None) -> None:
    assert liq.marca_documento(clases) == marca


def test_f138_r9_marca_documento_acepta_un_generador() -> None:
    assert liq.marca_documento(c for c in ["REMITE", "LIQUIDATORIA"]) == "LIQUIDATORIA"


# ===========================================================================
# R10 · creada_el
# ===========================================================================


@pytest.mark.parametrize(
    ("crefec", "crehor", "esperado"),
    [
        (20260929, 73806, datetime(2026, 9, 29, 7, 38, 6)),   # la FR26/10035 del correo
        (20081204, 235959, datetime(2008, 12, 4, 23, 59, 59)),
        (20240229, 1, datetime(2024, 2, 29, 0, 0, 1)),
        (20231231, 120000, datetime(2023, 12, 31, 12, 0, 0)),
        (0, 73806, None),
        (None, 73806, None),
        (20260929, 0, None),
        (20260929, None, None),
        (20230229, 73806, None),       # no bisiesto
        (20261301, 73806, None),       # mes 13
        (20261000, 73806, None),       # día 0
        (20260929, 240000, None),      # hora 24
        (20260929, 76006, None),       # minuto 60
        (20260929, 73860, None),       # segundo 60
        (-20260929, 73806, None),
        (20260929, -73806, None),
    ],
)
def test_f138_r10_fecha_hora_creacion(
    crefec: int | None, crehor: int | None, esperado: datetime | None,
) -> None:
    assert liq.fecha_hora_creacion(crefec, crehor) == esperado
