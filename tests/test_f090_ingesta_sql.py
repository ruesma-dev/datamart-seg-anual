# tests/test_f090_ingesta_sql.py
"""
F-090 · La ingesta de `rcg` y `gra` (filtradas en origen a las familias de
compras, sin binario) y el SQL de `compras.documento_adjuntos`, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f085_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ningún adjunto de personal entra en `raw`** (R3, R5): los dos filtros
   llevan exactamente las familias del dominio y `auxgra` no se ingiere.
2. **Ningún binario entra en el datamart** (R2, R4, R18): `ima`, `pul`, `tex` y
   `cam` fuera de la ingesta, y el SQL no nombra `ruesma_rep` ni el binario.
3. **Los literales del SQL son los del dominio** (R14): familias y extensiones.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain.documento_adjuntos import (
    COLUMNAS_EXCLUIDAS_GRA,
    FAMILIAS_ADJUNTOS,
    filtro_gra,
    filtro_rcg,
)
from etl_sigrid.infrastructure.sigrid.bench_extraccion import construir_sql_de_pagina

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str, largo: int = 4000) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    cortes = [i for i in (trozo.find("- source_table:"), trozo.find("# ====")) if i >= 0]
    return trozo[: min(cortes) if cortes else largo]


def _familias_de(filtro: str) -> set[int]:
    casa = re.search(r"tip IN \(([^)]*)\)", filtro)
    assert casa, f"el filtro no lleva `tip IN (...)`: {filtro!r}"
    return {int(x) for x in casa.group(1).split(",")}


# ===========================================================================
# A · La ingesta: R1-R6
# ===========================================================================


def test_f090_r1_rcg_filtrada_en_origen_sin_tiemod() -> None:
    rcg = _tablas()["rcg"]
    assert rcg["target_table"] == "rcg"
    assert rcg["id_column"] == "ide"
    assert rcg["incremental_column"] is None, "`rcg` no tiene tiemod (R1)"
    assert rcg["where"] == filtro_rcg(), "el filtro de `rcg` no es el del dominio (R1)"
    assert rcg["exclude_columns"] == []


def test_f090_r2_gra_filtrada_en_origen_sin_tiemod() -> None:
    gra = _tablas()["gra"]
    assert gra["target_table"] == "gra"
    assert gra["id_column"] == "ide"
    assert gra["incremental_column"] is None, "`gra` no tiene tiemod (R2)"
    assert gra["where"] == filtro_gra(), "el filtro de `gra` no es el del dominio (R2)"


def test_f090_r2_gra_excluye_exactamente_binario_y_texto_ilimitado() -> None:
    excluidas = _tablas()["gra"]["exclude_columns"]
    assert len(excluidas) == len(set(excluidas)), "columna repetida (R2)"
    assert set(excluidas) == COLUMNAS_EXCLUIDAS_GRA, (
        f"`gra` excluye {sorted(excluidas)}; lo decidido es "
        f"{sorted(COLUMNAS_EXCLUIDAS_GRA)} (R2)"
    )


def test_f090_r2_gra_va_detras_de_rcg() -> None:
    """Un enlace nuevo durante la noche trae su gráfico (design, ingesta)."""
    orden = [t["source_table"] for t in _lista_tablas()]
    assert orden.index("rcg") < orden.index("gra"), "`gra` tiene que ir DETRÁS de `rcg`"


def test_f090_r2_el_comentario_de_gra_da_el_motivo_de_cada_exclusion() -> None:
    comentario = _comentario_de("gra").lower()
    for columna in sorted(COLUMNAS_EXCLUIDAS_GRA):
        assert re.search(rf"- {columna}\b[^\n]*#", comentario), (
            f"la exclusión de `{columna}` no lleva su motivo al lado (R2)"
        )
    for dato in ("f-090", "ruesma_rep", "d2", "199.042", "41,5 s"):
        assert dato in comentario, f"el comentario de `gra` no dice «{dato}» (R2)"


def test_f090_r1_el_comentario_de_rcg_da_cifras_y_motivo() -> None:
    comentario = _comentario_de("rcg").lower()
    for dato in ("f-090", "199.042", "289.451", "7,2 s", "d2", "nominas"):
        assert dato in comentario, f"el comentario de `rcg` no dice «{dato}» (R1)"


def test_f090_r3_los_dos_filtros_llevan_exactamente_las_familias() -> None:
    for tabla in ("rcg", "gra"):
        familias = _familias_de(_tablas()[tabla]["where"])
        assert familias == set(FAMILIAS_ADJUNTOS), (
            f"`{tabla}` filtra {sorted(familias)}; el dominio dice "
            f"{sorted(FAMILIAS_ADJUNTOS)} (R3)"
        )


def test_f090_r3_los_filtros_salen_como_lectura_hacia_sigrid() -> None:
    """La página que compone la ingesta con el filtro es una lectura (R23 de F-024)."""
    for tabla in ("rcg", "gra"):
        sql = construir_sql_de_pagina(
            tabla, ["ide", "con" if tabla == "rcg" else "nom"], 10_000,
            where=_tablas()[tabla]["where"],
        )
        assert sql.startswith("SELECT TOP 10000")


def test_f090_r4_ninguna_columna_de_binario_se_ingiere() -> None:
    """Si alguna de las cuatro deja de estar excluida, el test la NOMBRA."""
    excluidas = set(_tablas()["gra"]["exclude_columns"])
    for columna in ("ima", "pul", "tex", "cam"):
        assert columna in excluidas, f"`gra.{columna}` SE INGIERE: tiene que ir excluida (R4)"


def test_f090_r5_no_se_ingiere_auxgra() -> None:
    assert "auxgra" not in _tablas(), "`auxgra` no se ingiere (D4, R5)"


def test_f090_r5_ninguna_familia_de_personal_o_posventa_en_los_filtros() -> None:
    for tabla in ("rcg", "gra"):
        familias = _familias_de(_tablas()[tabla]["where"])
        for tip in (43, 306, 708):
            assert tip not in familias, f"`{tabla}` trae la familia {tip} (D2, R5)"


def test_f090_r6_el_censo_pasa_a_74() -> None:
    assert len(_tablas()) == 74
    assert len(_lista_tablas()) == 74, "tabla declarada dos veces"
    assert {"rcg", "gra"} <= set(_tablas())


# ===========================================================================
# B · El SQL de `compras.documento_adjuntos`: R11-R18
# ===========================================================================

DIRECTORIO_COMPRAS = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
RUTA_ADJUNTOS = DIRECTORIO_COMPRAS / "14_documento_adjuntos.sql"
RUTA_DOCUMENTOS = DIRECTORIO_COMPRAS / "01_documentos.sql"

#: Las columnas publicadas, en su orden (R12).
COLUMNAS = (
    "adjunto_id", "documento_id", "tipo_documento_codigo", "familia",
    "codigo_documento", "comparativo_id", "grafico_id", "cod_repositorio",
    "empresa_repositorio", "nombre_fichero", "extension", "clase_fichero",
    "descripcion", "fecha_alta", "subido_por", "posicion",
)


def _sin_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _compacto(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _sql() -> str:
    return _compacto(_texto(RUTA_ADJUNTOS))


def _create() -> str:
    """El `CREATE TABLE ... AS` entero, hasta el primer `;`."""
    sql = _sql()
    inicio = sql.index("CREATE TABLE compras.documento_adjuntos AS")
    return sql[inicio: sql.index(";", inicio)]


def _select_final() -> str:
    """La lista de columnas del SELECT final (tras el CTE `base`)."""
    create = _create()
    cuerpo = create[create.rindex("SELECT ") + len("SELECT "):]
    return cuerpo[: cuerpo.rindex(" FROM base b")]


def _base() -> str:
    """El CTE `base`: de dónde sale cada fila."""
    create = _create()
    inicio = create.index("WITH base AS (")
    return create[inicio: create.rindex(" SELECT ")]


def test_f090_r11_una_fila_por_enlace_de_rcg_con_join_y_no_left_join() -> None:
    base = _base()
    assert "FROM raw.rcg r" in base, "la tabla sale de `raw.rcg` (R11)"
    assert re.search(
        r"(?<!LEFT )JOIN raw\.con c ON c\.ide = r\.con AND c\.tip IN \(12, 14, 15, 44, 46\)",
        base,
    ), "el documento se une con JOIN y filtra las familias (R11)"
    assert re.search(r"(?<!LEFT )JOIN raw\.gra g ON g\.ide = r\.gra", base), (
        "el gráfico se une con JOIN, no LEFT JOIN (R11)"
    )
    assert "LEFT JOIN raw.gra" not in base
    assert "FROM base b" in _create() and "JOIN" not in _create().split("FROM base b", 1)[1], (
        "el SELECT final no une nada más: una fila por enlace (R11)"
    )


def test_f090_r11_la_clave_es_el_enlace() -> None:
    assert "r.ide AS adjunto_id" in _base()
    assert "ALTER TABLE compras.documento_adjuntos ADD PRIMARY KEY (adjunto_id);" in _sql()


def test_f090_r12_publica_exactamente_las_columnas_en_su_orden() -> None:
    columnas = [c.strip() for c in re.split(r",(?![^(]*\))", _select_final())]
    nombres = tuple(re.sub(r"^.* AS ", "", c).replace("b.", "") for c in columnas)
    assert nombres == COLUMNAS, f"columnas publicadas: {nombres} (R12)"


def test_f090_r12_cada_columna_sale_de_su_campo() -> None:
    sql = _sql()
    for expresion in (
        "r.ide AS adjunto_id",
        "r.con AS documento_id",
        "c.tip AS tipo_documento_codigo",
        "c.cod AS codigo_documento",
        "g.ide AS grafico_id",
        "g.cod AS cod_repositorio",
        "g.emp AS empresa_repositorio",
        "NULLIF(BTRIM(g.nom), '') AS nombre_fichero",
        "NULLIF(BTRIM(g.res), '') AS descripcion",
        "compras.fn_sigrid_date(g.fec) AS fecha_alta",
        "NULLIF(BTRIM(g.usu), '') AS subido_por",
        "r.pos AS posicion",
    ):
        assert expresion in sql, f"falta «{expresion}» (R12)"


def test_f090_r13_comparativo_id_por_familia() -> None:
    sql = _sql()
    assert (
        "CASE c.tip WHEN 46 THEN r.con WHEN 12 THEN p.comide END AS comparativo_id"
        in sql
    ), "comparativo: el propio documento; oferta: `comprv.comide`; resto: NULL (R13)"
    assert "LEFT JOIN raw.comprv p ON p.docide = r.con AND c.tip = 12" in sql, (
        "la oferta se une a su comparativo por `comprv.docide` (R13)"
    )


def test_f090_r14_las_familias_del_sql_son_las_del_dominio() -> None:
    sql = _sql()
    listas = re.findall(r"tip IN \(([^)]*)\)", sql)
    assert len(listas) >= 2, "el `IN` de familias va en la guarda y en la tabla"
    for lista in listas:
        assert {int(x) for x in lista.split(",")} == set(FAMILIAS_ADJUNTOS), (
            f"`IN ({lista})` no son las familias del dominio (R14)"
        )
    casos = re.search(r"CASE c\.tip ((?:WHEN \d+ THEN '\w+' )+)END::TEXT AS familia", sql)
    assert casos, "falta el CASE de `familia` (R14)"
    pares = {int(t): n for t, n in re.findall(r"WHEN (\d+) THEN '(\w+)'", casos.group(1))}
    assert pares == FAMILIAS_ADJUNTOS, f"el CASE de familia dice {pares} (R14)"


def test_f090_r14_las_extensiones_del_sql_son_las_del_dominio() -> None:
    from etl_sigrid.domain.documento_adjuntos import (
        CLASE_OTRO,
        CLASE_SIN_EXTENSION,
        EXTENSIONES_POR_CLASE,
    )

    sql = _sql()
    casos = re.search(r"CASE (WHEN b\.extension IS NULL.*?) END::TEXT AS clase_fichero", sql)
    assert casos, "falta el CASE de `clase_fichero` (R14)"
    texto = casos.group(1)
    assert f"WHEN b.extension IS NULL THEN '{CLASE_SIN_EXTENSION}'" in texto
    assert texto.rstrip().endswith(f"ELSE '{CLASE_OTRO}'")
    en_sql = {
        clase: frozenset(re.findall(r"'(\w+)'", lista))
        for lista, clase in re.findall(r"WHEN b\.extension IN \(([^)]*)\) THEN '(\w+)'", texto)
    }
    assert en_sql == EXTENSIONES_POR_CLASE, f"el CASE de clase dice {en_sql} (R14)"


def test_f090_r14_la_extension_del_sql_es_la_del_dominio() -> None:
    """Misma expresión regular: `$` en Postgres es `\\Z` en Python."""
    from etl_sigrid.domain import documento_adjuntos

    patron_sql = r"\.([^.\s]+)$"
    assert f"lower(substring(btrim(g.nom) from '{patron_sql}')) AS extension" in _sql()
    assert documento_adjuntos._RE_EXTENSION.pattern == patron_sql[:-1] + r"\Z"


def test_f090_r15_guarda_de_huerfanos_antes_de_construir() -> None:
    sql = _sql()
    guarda = re.search(r"DO \$\$(.*?)\$\$;", sql)
    assert guarda, "falta el bloque DO de la guarda (R15)"
    cuerpo = guarda.group(1)
    assert (
        "FROM raw.rcg r JOIN raw.con c ON c.ide = r.con AND c.tip IN (12, 14, 15, 44, 46)"
        in cuerpo
    )
    assert "LEFT JOIN raw.gra g ON g.ide = r.gra" in cuerpo
    assert "count(*) FILTER (WHERE g.ide IS NULL)" in cuerpo
    assert "v_huerf > v_total * 0.01" in cuerpo, "el umbral es el 1 % (R15)"
    assert re.search(r"RAISE EXCEPTION 'F-090 R15: % de % [^']*', v_huerf, v_total", cuerpo), (
        "el error nombra F-090 y la cifra (R15)"
    )
    assert sql.index("DO $$") < sql.index("DROP TABLE"), "la guarda va ANTES del DROP (R15)"


def test_f090_r17_ningun_otro_sql_de_compras_lee_gra_ni_rcg() -> None:
    assert not re.search(r"raw\.(gra|rcg)\b", _texto(RUTA_DOCUMENTOS)), (
        "`01_documentos.sql` (compras.facturas) no se toca (D6, R17)"
    )
    for ruta in sorted(DIRECTORIO_COMPRAS.glob("*.sql")):
        if ruta == RUTA_ADJUNTOS:
            continue
        assert not re.search(r"raw\.(gra|rcg)\b", _texto(ruta)), f"{ruta.name} lee gra/rcg (R17)"


def test_f090_r17_el_sql_solo_construye_su_tabla() -> None:
    sql = _sql()
    tocados = set(
        re.findall(r"(?:CREATE|DROP|ALTER|COMMENT ON) (?:TABLE|VIEW|INDEX)[^;]*?compras\.(\w+)", sql)
    )
    assert tocados == {"documento_adjuntos"}, f"el SQL toca {sorted(tocados)} (R17)"
    assert "compras.facturas" not in sql


def test_f090_r18_idempotente_con_indices() -> None:
    sql = _sql()
    assert "DROP TABLE IF EXISTS compras.documento_adjuntos CASCADE;" in sql
    assert sql.index("DROP TABLE IF EXISTS") < sql.index("CREATE TABLE compras.documento_adjuntos AS")
    assert re.search(r"CREATE INDEX \w+ ON compras\.documento_adjuntos \(documento_id\);", sql)
    assert re.search(r"CREATE INDEX \w+ ON compras\.documento_adjuntos \(comparativo_id\);", sql)


def test_f090_r18_no_lee_ruesma_rep_ni_binarios() -> None:
    """Lo EJECUTABLE: el texto del `COMMENT ON` puede decir dónde está el binario."""
    sql = re.sub(r"COMMENT ON TABLE .*? IS '[^']*';", "", _sql()).lower()
    assert "ruesma_rep" not in sql, "el ETL no lee la base documental (R18)"
    for columna in sorted(COLUMNAS_EXCLUIDAS_GRA):
        assert not re.search(rf"\bg\.{columna}\b", sql), f"el SQL lee `gra.{columna}` (R18)"
    assert "documents/read" not in sql


def test_f090_r18_cabecera_con_ruta_y_fuentes() -> None:
    texto = _texto(RUTA_ADJUNTOS)
    assert texto.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/14_documento_adjuntos.sql"
    )
    for dato in ("raw.rcg", "raw.gra", "raw.con", "raw.comprv", "ruesma_rep", "F-090"):
        assert dato in texto, f"la cabecera no cita «{dato}»"
