# tests/test_f038_dominio.py
"""
F-038 · El oráculo del comparativo: ofertas ficticias y adjudicado atípico.

La regla vive escrita UNA vez en `etl_sigrid/domain/comparativos.py` (R11) y la
ejecuta Postgres desde `compras.fn_familia_ficticia` (`sql/compras/00_setup.sql`);
`tests/test_f038_sql.py` comprueba que el SQL lleva **los mismos** literales.
Aquí se prueba el oráculo sobre los nombres MEDIDOS el 2026-10-04
(`progress/spec_F-038.md` §2): ni uno inventado.

POR QUÉ IMPORTA. Una oferta ficticia —el OBJETIVO, la OFICINA TÉCNICA, la
PLANIFICACIÓN— contada como real estropea el número de ofertantes, la oferta
más barata y el ahorro del concurso. Y el CIF falso solo cubre el 30 % de las
32.899 ficticias: 172 entidades ficticias tienen el CIF VACÍO, así que la
familia la dice el NOMBRE de la oferta (`dco.entres`), normalizado.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest

from etl_sigrid.domain.comparativos import (
    CIF_FALSOS,
    EXCLUSIONES,
    FACTOR_ATIPICO,
    MINIMO_ATIPICO,
    NO_ALFANUMERICO,
    PATRONES_FAMILIA,
    TILDES_DESTINO,
    TILDES_ORIGEN,
    es_adjudicado_atipico,
    familia_ficticia,
    normalizar_nombre,
)

CIF_OBJETIVO = "A99999999"
CIF_OFICINA = "A00000000"
CIF_REAL = "B12345678"


# ===========================================================================
# R9 · normalizar el nombre: mayúsculas, sin tildes ni signos
# ===========================================================================


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("OBJETIVO-RUESMA", "OBJETIVO RUESMA"),
        ("*OBJETIVO*", "OBJETIVO"),
        ("oficina tecnica", "OFICINA TECNICA"),
        ("OFICINA TÉCNICA", "OFICINA TECNICA"),
        ("PLANIFICACIÓN ABC", "PLANIFICACION ABC"),
        ('PLANIFICACION " FASE 0 "', "PLANIFICACION FASE 0"),
        ('PLANIFICADO FASE "0"', "PLANIFICADO FASE 0"),
        ("PLANIFICADO_RUESMA", "PLANIFICADO RUESMA"),
        ("MAT PLANIFICACION DE ESPACIOS, S.L.", "MAT PLANIFICACION DE ESPACIOS S L"),
        ("  cigüeña  ñandú ", "CIGUENA NANDU"),
        ("º", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_f038_r9_normalizar_nombre(texto: str | None, esperado: str) -> None:
    assert normalizar_nombre(texto) == esperado


def test_f038_r9_los_literales_de_la_normalizacion_son_posix_y_simetricos() -> None:
    """Los mismos literales viajan al `translate` y al `regexp_replace` del SQL."""
    assert TILDES_ORIGEN == "ÁÉÍÓÚÜÑ"
    assert TILDES_DESTINO == "AEIOUUN"
    assert len(TILDES_ORIGEN) == len(TILDES_DESTINO)
    assert NO_ALFANUMERICO == "[^A-Z0-9]+"


# ===========================================================================
# R8-R10 · familia ficticia: las fixtures medidas (design §3)
# ===========================================================================


@pytest.mark.parametrize(
    ("cif", "nombre", "familia"),
    [
        # OBJETIVO
        (None, "OBJETIVO-RUESMA", "OBJETIVO"),
        ("", "*OBJETIVO*", "OBJETIVO"),
        (CIF_OFICINA, "OBJE", "OBJETIVO"),
        (CIF_OBJETIVO, "º", "OBJETIVO"),
        (CIF_OBJETIVO, "OBJETIVO RUESMA", "OBJETIVO"),
        # OFICINA_TECNICA
        (None, "OFICINA TÉCNICA", "OFICINA_TECNICA"),
        ("", "oficina tecnica", "OFICINA_TECNICA"),
        (CIF_OBJETIVO, "OFICINA TENICA", "OFICINA_TECNICA"),
        # CUATRIMESTRAL (antes que PLANIFICACION: el orden manda)
        (None, "PLANIFICACION CUATRIMESTRAL", "CUATRIMESTRAL"),
        (None, "CUATRIMESTRAL JUNIO 2023", "CUATRIMESTRAL"),
        # FASE_0
        (None, 'PLANIFICACION " FASE 0 "', "FASE_0"),
        (None, 'PLANIFICADO FASE "0"', "FASE_0"),
        (None, 'PLANIFICACION "0"', "FASE_0"),
        # ABC
        (None, "PLANIFICACIÓN ABC", "ABC"),
        (None, "ABC DEF MASTER COSTE 3", "ABC"),
        # PLANIFICACION
        (None, "PLANIFICADO_RUESMA", "PLANIFICACION"),
        (None, "PLANIFICACION", "PLANIFICACION"),
    ],
)
def test_f038_r8_r9_familia_de_los_nombres_medidos(
    cif: str | None, nombre: str, familia: str
) -> None:
    assert familia_ficticia(cif, nombre) == familia


@pytest.mark.parametrize(
    ("cif", "nombre"),
    [
        # R10: la exclusion, con CIF y sin el (3 ofertas medidas sin CIF)
        (None, "MAT PLANIFICACION DE ESPACIOS, S.L."),
        ("", "MAT PLANIFICACION DE ESPACIOS, S.L."),
        (CIF_REAL, "MAT PLANIFICACION DE ESPACIOS, S.L."),
        # R8: con CIF real nunca es ficticia, aunque el nombre case familia
        (CIF_REAL, "ABC INSTALACIONES Y MONTAJES, S.L."),
        (CIF_REAL, "3 DE 3 OFICINA TECNICA, S.L."),
        (CIF_REAL, "OBJETIVO RUESMA"),
        # Proveedor real sin CIF y sin nombre de familia
        (None, "CERRAJERIA RIANSA"),
        ("", "CERRAJERIA RIANSA"),
        ("   ", "CERRAJERIA RIANSA"),
        (None, None),
    ],
)
def test_f038_r8_r10_ofertas_reales(cif: str | None, nombre: str | None) -> None:
    assert familia_ficticia(cif, nombre) is None


def test_f038_r9_cif_falso_sin_nombre_reconocible_cae_en_su_familia() -> None:
    """`A99999999` → OBJETIVO y `A00000000` → OFICINA_TECNICA (180 ofertas)."""
    assert familia_ficticia(CIF_OBJETIVO, "TRANIDE") == "OBJETIVO"
    assert familia_ficticia(CIF_OFICINA, "TRANIDE") == "OFICINA_TECNICA"
    assert familia_ficticia(CIF_OFICINA, None) == "OFICINA_TECNICA"


def test_f038_r8_el_cif_se_compara_recortado_y_en_mayusculas() -> None:
    assert familia_ficticia(" a99999999 ", "º") == "OBJETIVO"
    assert familia_ficticia(" b12345678 ", "OBJETIVO") is None


def test_f038_r9_el_nombre_manda_sobre_el_cif_falso() -> None:
    """La 977371 (CIF `A00000000`) firma como OFICINA TECNICA, OBJETIVO y
    PLANIFICADO: la familia la dice el nombre de la oferta, no el proveedor."""
    assert familia_ficticia(CIF_OFICINA, "OBJETIVO RUESMA") == "OBJETIVO"
    assert familia_ficticia(CIF_OFICINA, "PLANIFICADO") == "PLANIFICACION"
    assert familia_ficticia(CIF_OBJETIVO, "OFICINA TECNICA") == "OFICINA_TECNICA"


def test_f038_r10_la_exclusion_manda_aunque_el_cif_sea_falso() -> None:
    """Orden de design §3: CIF real → real; excluido → real; luego familia."""
    assert familia_ficticia(CIF_OBJETIVO, "MAT PLANIFICACION DE ESPACIOS") is None


@pytest.mark.parametrize(
    "nombre",
    ["OBJETOS DE OBRA SL", "SOBJETIVO", "CABCO", "ABCD SL", "FASE 05 SL", "MOBJE"],
)
def test_f038_r9_los_patrones_respetan_la_frontera_de_palabra(nombre: str) -> None:
    """`(^| )` hace de frontera: OBJE solo al principio de palabra, ABC suelta.

    `OBJETOS DE OBRA` empieza por OBJE y por eso SÍ es OBJETIVO sin CIF: el
    patrón es el medido y la consulta de control de la ficha es la defensa.
    """
    esperado = "OBJETIVO" if nombre.startswith("OBJE") else None
    assert familia_ficticia(None, nombre) == esperado


def test_f038_r9_el_orden_de_las_familias_es_el_de_la_spec() -> None:
    assert [familia for familia, _ in PATRONES_FAMILIA] == [
        "OBJETIVO",
        "OFICINA_TECNICA",
        "CUATRIMESTRAL",
        "FASE_0",
        "ABC",
        "PLANIFICACION",
    ]


def test_f038_r11_los_patrones_son_posix_sin_construcciones_de_python() -> None:
    """Postgres no tiene lookarounds ni `\\m`; `re` no tiene `\\m`: nada de eso."""
    for _, patron in PATRONES_FAMILIA:
        re.compile(patron)
        for prohibido in ("(?", "\\m", "\\M", "\\b", "'"):
            assert prohibido not in patron, (patron, prohibido)


def test_f038_r9_los_cif_falsos_y_las_exclusiones() -> None:
    assert CIF_FALSOS == {CIF_OBJETIVO: "OBJETIVO", CIF_OFICINA: "OFICINA_TECNICA"}
    assert EXCLUSIONES == ("PLANIFICACION DE ESPACIOS",)
    for exclusion in EXCLUSIONES:
        assert normalizar_nombre(exclusion) == exclusion, (
            "la exclusion se compara con el nombre YA normalizado"
        )


# ===========================================================================
# R16 · adjudicado atípico: 10 veces la mayor oferta Y 100.000 €
# ===========================================================================


def test_f038_r16_umbrales() -> None:
    assert FACTOR_ATIPICO == 10
    assert MINIMO_ATIPICO == Decimal("100000")


@pytest.mark.parametrize(
    ("adjudicado", "mayor", "esperado"),
    [
        # La cabeza medida: 1610000 (363,2 M€ contra 2.200 €)
        (Decimal("363200000"), Decimal("2200"), True),
        # 2834916 (66,9 M€ / 100.575 €)
        (Decimal("66900000"), Decimal("100575"), True),
        # Borde del factor: exactamente 10 veces NO es atípico
        (Decimal("1000000"), Decimal("100000"), False),
        (Decimal("1000000.01"), Decimal("100000"), True),
        # Borde del mínimo: 100.000 exactos NO es atípico aunque sea 10×
        (Decimal("100000"), Decimal("100"), False),
        (Decimal("100000.01"), Decimal("100"), True),
        # 10× pero por debajo del mínimo
        (Decimal("50000"), Decimal("10"), False),
        # Por encima del mínimo pero no 10×
        (Decimal("500000"), Decimal("400000"), False),
        # Sin oferta con importe con que comparar: NULL, no False
        (Decimal("500000"), Decimal("0"), None),
        (Decimal("500000"), Decimal("-5"), None),
        (Decimal("500000"), None, None),
        # Sin adjudicado (comparativo sin líneas): NULL, como en SQL
        (None, Decimal("1000"), None),
    ],
)
def test_f038_r16_es_adjudicado_atipico(
    adjudicado: Decimal | None, mayor: Decimal | None, esperado: bool | None
) -> None:
    assert es_adjudicado_atipico(adjudicado, mayor) is esperado
