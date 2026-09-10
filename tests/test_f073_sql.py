# tests/test_f073_sql.py
"""
F-073 · El SQL nuevo y el ampliado, comprobado sobre su TEXTO.

Ninguna de estas vistas se puede ejecutar aquí: `CREATE OR REPLACE VIEW` escribe
en un Postgres compartido con `albaranes` y `partes` **en producción**, y la
convención del proyecto es que los unit tests no toquen red ni BBDD. Lo que sí
se puede es fijar por escrito las decisiones que el diseño tomó midiendo contra
la base, de modo que un refactor que se lleve por delante cualquiera de ellas
rompa la suite y no la nocturna. Mismo criterio que `tests/test_f052_sql.py` y
`tests/test_f042_sql.py`.

Los nombres de columna de origen NO se suponen: están medidos en la T1 y
anotados en `progress/impl_F-073.md` (`conest.tip/est/res`, `auxefp.res` —y no
`auxefp.est`, que está vacío—, y los cuatro campos de dirección de `raw.obr`).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pytest

DIRECTORIO_SQL = (
    Path(__file__).resolve().parents[1]
    / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
)
RUTA_CENTROS = DIRECTORIO_SQL / "maestro" / "04_centros_coste.sql"


@lru_cache(maxsize=None)
def _sql(ruta: Path) -> str:
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    """El texto ejecutable: sin las líneas `--` de comentario."""
    return "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("--")
    )


def _compacto(texto: str) -> str:
    """Una sola línea, espacios colapsados: para buscar expresiones SQL."""
    return re.sub(r"\s+", " ", _sin_comentarios(texto))


# ---------------------------------------------------------------------------
# R1 · la vista existe y expone las siete columnas del puente
# ---------------------------------------------------------------------------


def test_f073_r1_la_vista_de_centros_de_coste_se_crea_como_vista() -> None:
    assert "CREATE OR REPLACE VIEW maestro.centros_coste" in _compacto(
        _sql(RUTA_CENTROS)
    )


@pytest.mark.parametrize(
    "columna",
    [
        "centro_coste_id",
        "codigo_centro",
        "nombre_centro",
        "empresa",
        "obra_id",
        "codigo_obra",
        "nombre_obra",
    ],
)
def test_f073_r1_expone_las_siete_columnas_del_puente(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _compacto(_sql(RUTA_CENTROS))), (
        f"maestro.centros_coste debe exponer {columna} (R1)"
    )


def test_f073_r1_una_fila_por_fila_de_raw_cen() -> None:
    """El grano es `raw.cen`: la tabla de la que se parte, sin filtro."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "FROM raw.cen" in compacto
    assert "WHERE" not in compacto.split("FROM raw.cen")[1].split("LEFT JOIN LATERAL")[0]


# ---------------------------------------------------------------------------
# R2 · el puente resuelve por misma empresa y mismo código en `raw.con`
# ---------------------------------------------------------------------------


def test_f073_r2_el_puente_cruza_por_empresa_y_codigo() -> None:
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "co.emp = cc.emp" in compacto, "falta el cruce por empresa (R2)"
    assert "co.cod = cc.cod" in compacto, "falta el cruce por código (R2)"


def test_f073_r2_el_lateral_exige_ficha_de_obra() -> None:
    """`JOIN raw.obr` dentro del lateral: descarta la propia fila `con` del centro."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    lateral = compacto[compacto.index("LEFT JOIN LATERAL") :]
    assert "raw.obr" in lateral, (
        "el lateral debe unir a raw.obr o resolvería contra el propio centro (R2)"
    )


def test_f073_r2_el_centro_toma_codigo_nombre_y_empresa_de_raw_con() -> None:
    """`raw.cen` no tiene `cod`, `res` ni `emp`: salen de su `raw.con` (T1)."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "JOIN raw.con" in compacto
    assert "cc.ide = n.ide" in compacto or "n.ide = cc.ide" in compacto


# ---------------------------------------------------------------------------
# R3 · ni `cen.obride` ni aritmética sobre el `ide`
# ---------------------------------------------------------------------------


def test_f073_r3_no_usa_cen_obride() -> None:
    """Está a 0 en las 804 filas (medido en T1): usarlo daría NULL siempre."""
    assert "obride" not in _sin_comentarios(_sql(RUTA_CENTROS)), (
        "cen.obride está a 0 en las 804 filas y no puede resolver el puente (R3)"
    )


def test_f073_r3_no_hace_aritmetica_sobre_el_ide() -> None:
    """`obride + 1` acertaba el 64 %: una coincidencia, no una relación."""
    ejecutable = _sin_comentarios(_sql(RUTA_CENTROS))
    assert not re.search(r"ide\s*[+-]\s*\d", ejecutable), (
        "la aritmética sobre el ide acierta el 64 %: no es el puente (R3)"
    )


# ---------------------------------------------------------------------------
# R4 · los 121 centros que no son obra se publican igual, con `obra_id` NULL
# ---------------------------------------------------------------------------


def test_f073_r4_el_lateral_es_left_join_y_no_join() -> None:
    compacto = _compacto(_sql(RUTA_CENTROS))
    assert "LEFT JOIN LATERAL" in compacto, (
        "con JOIN LATERAL se perderían los 121 centros sin obra (R4)"
    )
    assert re.search(r"LEFT JOIN LATERAL \(.*\) \w+ ON TRUE", compacto), (
        "el lateral debe colgar con ON TRUE para no filtrar (R4)"
    )


def test_f073_r4_no_filtra_los_centros_sin_obra() -> None:
    """Ningún `WHERE` fuera del lateral: no se descarta ninguna fila de `raw.cen`."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    tras_lateral = compacto[compacto.index(") o ON TRUE") :]
    assert "WHERE" not in tras_lateral, (
        "un WHERE final filtraría los 121 centros de estructura y servicios (R4)"
    )


# ---------------------------------------------------------------------------
# R5 · `centro_coste_id` es único POR CONSTRUCCIÓN
# ---------------------------------------------------------------------------


def test_f073_r5_el_lateral_no_puede_multiplicar_filas() -> None:
    """Hoy el puente es 1:1 sobre 683 pares; la vista no puede depender de eso."""
    compacto = _compacto(_sql(RUTA_CENTROS))
    lateral = compacto[
        compacto.index("LEFT JOIN LATERAL") : compacto.index(") o ON TRUE")
    ]
    assert "LIMIT 1" in lateral, (
        "sin LIMIT 1 la vista multiplicaría filas el día que el origen deje de "
        "ser 1:1 (R5)"
    )
    assert "ORDER BY" in lateral, (
        "LIMIT 1 sin ORDER BY declarado elige una fila al azar (R5)"
    )


# ===========================================================================
# `maestro.estados_documento` (05) · R19 y R20
# ===========================================================================

RUTA_ESTADOS = DIRECTORIO_SQL / "maestro" / "05_estados_documento.sql"


def test_f073_r19_la_vista_de_estados_se_crea_como_vista() -> None:
    assert "CREATE OR REPLACE VIEW maestro.estados_documento" in _compacto(
        _sql(RUTA_ESTADOS)
    )


@pytest.mark.parametrize(
    "columna",
    ["estado_documento_id", "tipo_documento", "estado_id", "codigo_estado", "estado"],
)
def test_f073_r19_expone_tipo_codigo_y_nombre(columna: str) -> None:
    assert re.search(rf"AS {columna}\b", _compacto(_sql(RUTA_ESTADOS))), (
        f"maestro.estados_documento debe exponer {columna} (R19)"
    )


def test_f073_r19_lee_de_raw_conest_con_los_nombres_medidos() -> None:
    """T1: `tip` es el tipo, `est` el código del estado y `res` el nombre."""
    compacto = _compacto(_sql(RUTA_ESTADOS))
    assert "FROM raw.conest" in compacto
    for origen in ("tip", "est", "res"):
        assert re.search(rf"\.{origen}\s+AS ", compacto), (
            f"conest.{origen} no se proyecta (R19)"
        )


def test_f073_r19_no_filtra_por_tipo_de_documento() -> None:
    """Las 193 filas, no las 14 de obra: es una dimensión, no un lookup."""
    compacto = _compacto(_sql(RUTA_ESTADOS))
    cuerpo = compacto[
        compacto.index("CREATE OR REPLACE VIEW maestro.estados_documento") :
    ].split(";")[0]
    assert "WHERE" not in cuerpo, (
        "filtrar por tipo dejaría fuera contratos, facturas y comparativos (R19)"
    )
    assert "42" not in cuerpo, "el tipo de obra no se cablea aquí (R19)"


def test_f073_r20_el_comment_avisa_de_que_la_traduccion_va_por_tipo() -> None:
    """La misma cifra significa cosas distintas en un contrato y en una factura."""
    comentario = _sql(RUTA_ESTADOS)
    comentario = comentario[comentario.index("COMMENT ON VIEW maestro.estados_documento") :]
    assert "tipo de documento" in comentario.lower(), (
        "el COMMENT debe advertir de que la traducción va por tipo (R20)"
    )
