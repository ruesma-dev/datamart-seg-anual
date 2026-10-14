# tests/test_f138_ingesta_sql.py
"""
F-138 · La ingesta de `conala` y `auxala`, el SQL de las alarmas y la marca
«liquidatoria», y su sub-paso, sobre su TEXTO.

Los SQL construyen objetos en un Postgres **compartido con producción**, así
que aquí no se ejecutan: se leen. Mismo criterio que `tests/test_f090_ingesta_sql.py`.

LO QUE ESTE FICHERO DEFIENDE, por orden de lo que costaría un error:

1. **Ninguna alarma de empleados entra en `raw`** (R3) y las de recursos y
   partes NO llegan a la general (R11, R14, D9).
2. **Los literales del SQL y del YAML son los del dominio** (R13): familias,
   traducción, patrones y precedencia.
3. **Lo existente no se toca** (R21): `01_` y `07_` no nombran las alarmas.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from etl_sigrid.domain import liquidatoria as liq
from etl_sigrid.infrastructure.sigrid.bench_extraccion import construir_sql_de_pagina

RAIZ = Path(__file__).resolve().parents[1]
RUTA_TABLAS = RAIZ / "config" / "tables_sigrid.yaml"
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"
RUTA_SQL = DIR_SQL / "15_alarmas_liquidatoria.sql"


@cache
def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"no encontrado: {ruta}"
    return ruta.read_text(encoding="utf-8")


@cache
def _lista_tablas() -> tuple[dict, ...]:
    return tuple(yaml.safe_load(_texto(RUTA_TABLAS))["tables"])


def _tablas() -> dict[str, dict]:
    return {t["source_table"]: t for t in _lista_tablas()}


def _comentario_de(tabla: str) -> str:
    """El bloque de texto (comentarios incluidos) de una entrada del YAML."""
    trozo = _texto(RUTA_TABLAS).split(f"source_table: {tabla}\n", 1)[1]
    corte = trozo.find("- source_table:")
    return trozo[:corte] if corte >= 0 else trozo


def _familias_de(filtro: str) -> list[int]:
    casa = re.search(r"tip IN \(([^)]*)\)", filtro)
    assert casa, f"el filtro no lleva `tip IN (...)`: {filtro!r}"
    return [int(x) for x in casa.group(1).split(",")]


# ===========================================================================
# R1-R3 · la ingesta
# ===========================================================================


def test_f138_r1_conala_filtrada_en_origen_sin_tiemod() -> None:
    conala = _tablas()["conala"]
    assert conala["target_table"] == "conala"
    assert conala["id_column"] == "ide"
    assert conala["incremental_column"] is None, "`conala` no tiene tiemod (R1)"
    assert conala["where"] == liq.filtro_conala(), "el filtro de `conala` no es el del dominio (R1)"
    assert conala["exclude_columns"] == [], "`conala` entra sin columnas excluidas (R1)"


def test_f138_r1_auxala_entera_con_tiemod() -> None:
    auxala = _tablas()["auxala"]
    assert auxala["target_table"] == "auxala"
    assert auxala["id_column"] == "ide"
    assert auxala["incremental_column"] == "tiemod"
    assert auxala["where"] is None
    assert auxala["exclude_columns"] == []


def test_f138_r1_el_comentario_de_conala_da_cifras_y_motivos() -> None:
    comentario = _comentario_de("conala").lower()
    for dato in ("f-138", "45.747", "1,79 mb", "~2 s", "d3", "43", "fallar cerrada",
                 "d9", "compras_restringida", "`fec1`", "`fec2`", "`creusu`", "login",
                 "filtro_conala()"):
        assert dato in comentario, f"el comentario de `conala` no dice «{dato}» (R1)"


def test_f138_r1_el_filtro_sale_como_lectura_hacia_sigrid() -> None:
    sql = construir_sql_de_pagina("conala", ["ide", "conide", "tex"], 10_000,
                                  where=_tablas()["conala"]["where"])
    assert sql.startswith("SELECT TOP 10000")


def test_f138_r3_la_familia_43_no_esta_en_el_filtro_de_ingesta() -> None:
    familias = _familias_de(_tablas()["conala"]["where"])
    assert liq.FAMILIA_EMPLEADOS not in familias, "las alarmas de empleados entrarían en raw (R3)"
    assert familias == sorted(liq.FAMILIAS_ALARMAS), "el filtro no es la lista explícita (R4)"
    assert "<>" not in _tablas()["conala"]["where"], "lista explícita, no exclusión (D3)"


def test_f138_r3_la_43_tampoco_en_el_sql() -> None:
    sql = _texto(RUTA_SQL)
    assert not re.search(r"\bWHEN 43\b", sql)
    for lista in re.findall(r"tip IN \(([^)]*)\)", sql):
        assert "43" not in [x.strip() for x in lista.split(",")], lista


# ===========================================================================
# R2 · el censo
# ===========================================================================


def test_f138_r2_el_censo_pasa_a_76() -> None:
    assert len(_tablas()) == 76
    assert len(_lista_tablas()) == 76, "tabla declarada dos veces"
    assert {"conala", "auxala"} <= set(_tablas())


# ===========================================================================
# R11-R14 · las alarmas en dos esquemas (T5)
# ===========================================================================

COLUMNAS_GENERAL = [
    "alarma_id", "documento_id", "tipo_documento_codigo", "familia", "tipo_documento",
    "codigo_documento", "tipo_alarma_codigo", "tipo_alarma", "texto", "ver_al_abrir",
    "creada_el", "creada_por", "clase_liquidacion",
]
COLUMNAS_COMPLETA = [*COLUMNAS_GENERAL, "restringido", "motivo_restriccion"]


def _sql() -> str:
    return _texto(RUTA_SQL)


def _plano(texto: str) -> str:
    return re.sub(r"\s+", " ", texto)


def _bloque(objeto: str) -> str:
    """Desde el `CREATE TABLE <objeto> AS` hasta el `;` que cierra la sentencia."""
    sql = _sql()
    inicio = sql.index(f"CREATE TABLE {objeto} AS")
    return sql[inicio: sql.index(";\n", inicio)]


def _alias_finales(bloque: str) -> list[str]:
    """Las columnas del SELECT exterior: el último `AS x` (o el nombre) de cada línea."""
    exterior = bloque.rsplit("\nSELECT", 1)[1].split("\nFROM", 1)[0]
    columnas = []
    for linea in exterior.splitlines():
        linea = linea.split("--")[0].strip().rstrip(",")
        if not linea:
            continue
        casa = re.search(r"\bAS (\w+)$", linea) or re.fullmatch(r"(?:\w+\.)?(\w+)", linea)
        assert casa, f"línea del SELECT que no sé leer: {linea!r}"
        columnas.append(casa.group(1))
    return columnas


def test_f138_r11_las_dos_tablas_se_reconstruyen_cada_noche() -> None:
    sql = _sql()
    for objeto in ("compras_restringida.documento_alarmas", "compras.documento_alarmas"):
        assert f"DROP TABLE IF EXISTS {objeto} CASCADE;" in sql
        assert sql.index(f"DROP TABLE IF EXISTS {objeto} CASCADE;") < sql.index(
            f"CREATE TABLE {objeto} AS")
        assert f"ALTER TABLE {objeto} ADD PRIMARY KEY (alarma_id);" in sql
    assert sql.index("CREATE TABLE compras_restringida.documento_alarmas AS") < sql.index(
        "CREATE TABLE compras.documento_alarmas AS"), "la general sale de la completa"


def test_f138_r11_la_completa_sale_de_conala_con_su_documento() -> None:
    bloque = _bloque("compras_restringida.documento_alarmas")
    assert "FROM      raw.conala a" in bloque
    assert "JOIN      raw.con c ON c.ide = a.conide" in bloque
    assert "LEFT JOIN raw.auxala x ON x.ide = NULLIF(a.alaide, 0)" in bloque


def test_f138_r11_la_general_es_la_completa_sin_las_restringidas() -> None:
    bloque = _bloque("compras.documento_alarmas")
    assert "FROM compras_restringida.documento_alarmas" in bloque
    assert "WHERE NOT restringido" in bloque


def test_f138_r12_columnas_de_las_dos() -> None:
    assert _alias_finales(_bloque("compras_restringida.documento_alarmas")) == COLUMNAS_COMPLETA
    assert _alias_finales(_bloque("compras.documento_alarmas")) == COLUMNAS_GENERAL


def test_f138_r12_expresiones_de_la_completa() -> None:
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    for expresion in (
        "CASE WHEN c.tip IN (14, 15, 44) THEN compras.fn_tipo_documento(c.tip, "
        "compras.fn_serie(c.cod)) END",
        "x.cod AS tipo_alarma_codigo",
        "x.res AS tipo_alarma",
        "a.tex AS texto",
        "COALESCE(a.tipabr, 0) = 1 AS ver_al_abrir",
        "NULLIF(btrim(a.creusu), '') AS creada_por",
        "compras.fn_clase_liquidacion(a.tex) AS clase_liquidacion",
    ):
        assert expresion in bloque, f"falta «{expresion}» (R12)"
    for prohibida in ("fec1", "fec2", "a.usu", "a.rol"):
        assert prohibida not in bloque, f"`{prohibida}` no se publica (R24)"


def test_f138_r10_creada_el_en_sql_es_el_oraculo() -> None:
    """Fecha 0 o imposible (la de `fn_sigrid_date`) u hora imposible: NULL."""
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    assert ("CASE WHEN a.crehor BETWEEN 1 AND 235959 AND a.crehor % 10000 / 100 < 60 "
            "AND a.crehor % 100 < 60 THEN compras.fn_sigrid_date(a.crefec) + make_interval("
            "hours => a.crehor / 10000, mins => a.crehor % 10000 / 100, secs => a.crehor % 100) "
            "END AS creada_el") in bloque


def test_f138_r13_la_traduccion_es_la_del_dominio() -> None:
    cuerpo = _sql().split("FUNCTION compras.fn_texto_normalizado")[1].split("$$;")[0]
    assert (f"translate(COALESCE(t, ''), '{liq.TRADUCCION_ORIGEN}', "
            f"'{liq.TRADUCCION_DESTINO}')") in cuerpo
    assert f"'{liq.PATRON_NO_ALFANUMERICO}', ' ', 'g'" in cuerpo
    # el orden de R5: translate -> regexp_replace -> upper -> btrim
    assert "btrim(upper(regexp_replace(translate(" in cuerpo
    assert "IMMUTABLE" in cuerpo


def _cuerpo_clase() -> str:
    return _sql().split("FUNCTION compras.fn_clase_liquidacion")[1].split("$$;")[0]


def _ramas_sql() -> list[tuple[str, str, str]]:
    """(operador, patrón, clase) de cada `WHEN` de `fn_clase_liquidacion`, en orden."""
    return re.findall(r"WHEN x\.n (!?~) '([^']*)' THEN (?:'(\w+)'|CASE)", _cuerpo_clase())


def test_f138_r13_los_patrones_en_el_orden_de_r6() -> None:
    assert _ramas_sql() == [
        ("!~", liq.PATRON_MENCION, ""),
        ("~", liq.PATRON_REMITE, "REMITE"),
        ("~", liq.PATRON_NEGADA, "NEGADA"),
        ("~", liq.PATRON_CARTA, "CARTA_LIQUIDACION"),
        ("~", liq.PATRON_DUDOSA, "DUDOSA"),
    ]
    assert "ELSE 'LIQUIDATORIA'" in _cuerpo_clase()
    assert "compras.fn_texto_normalizado(t) AS n" in _cuerpo_clase()
    assert "IMMUTABLE" in _cuerpo_clase()


def _clasificar_como_el_sql(texto: str | None) -> str | None:
    """Ejecuta en Python las ramas tal como están escritas en el SQL."""
    n = liq.normalizar(texto)
    ramas = _ramas_sql()
    if not re.search(ramas[0][1], n):
        return "REMITE" if re.search(ramas[1][1], n) else None
    for _, patron, clase in ramas[2:]:
        if re.search(patron, n):
            return clase
    return "LIQUIDATORIA"


def test_f138_r13_el_sql_clasifica_como_el_oraculo() -> None:
    from tests.test_f138_dominio import test_f138_r6_la_regla_en_los_bordes as bordes
    from tests.test_f138_dominio import test_f138_r8_casos_de_la_spec as spec

    casos = [m.args[1] for t in (spec, bordes) for m in t.pytestmark if m.name == "parametrize"]
    textos = [texto for lista in casos for texto, _ in lista]
    assert len(textos) > 30
    for texto in textos:
        assert _clasificar_como_el_sql(texto) == liq.clasificar(texto), texto


def test_f138_r13_las_familias_son_las_del_dominio() -> None:
    bloque = _bloque("compras_restringida.documento_alarmas")
    caso = bloque.split("CASE c.tip", 1)[1].split("END", 1)[0]
    parejas = {int(t): n for t, n in re.findall(r"WHEN (\d+) THEN '(\w+)'", caso)}
    assert parejas == liq.FAMILIAS_ALARMAS
    tips = ", ".join(str(t) for t in sorted(liq.FAMILIAS_ALARMAS))
    assert f"WHERE c.tip IN ({tips})" in _plano(bloque), "la completa falla cerrada, como la ingesta"


def test_f138_r13_las_restringidas_son_las_del_dominio() -> None:
    restringidas = ", ".join(str(t) for t in sorted(liq.FAMILIAS_RESTRINGIDAS))
    bloque = _plano(_bloque("compras_restringida.documento_alarmas"))
    assert f"c.tip IN ({restringidas}) AS restringido" in bloque
    assert "CASE WHEN b.restringido THEN b.familia END AS motivo_restriccion" in bloque
    guarda = _sql().split("R14 · la guarda de la restricción")[1]
    assert f"c.tip IN ({restringidas})" in guarda


def test_f138_r14_guarda_de_ingesta_antes_de_construir() -> None:
    sql = _sql()
    guarda = sql[: sql.index("CREATE TABLE")]
    assert "raw.conala" in guarda and "c.tip = 15" in guarda
    assert "RAISE EXCEPTION 'F-138" in guarda


def test_f138_r14_guarda_de_la_restriccion_tras_la_general() -> None:
    sql = _sql()
    inicio = sql.index("R14 · la guarda de la restricción")
    assert inicio > sql.index("CREATE TABLE compras.documento_alarmas AS")
    guarda = sql[inicio: sql.index("END $$;", inicio)]
    assert "JOIN raw.con c ON c.ide = g.documento_id" in guarda, "recalcula desde raw.con"
    assert "v_general + v_restringidas <> v_completa" in guarda
    assert "RAISE EXCEPTION 'F-138" in guarda


def test_f138_r20_un_solo_fichero_sin_control_de_transaccion() -> None:
    sql = _sql()
    assert not re.search(r"^\s*(COMMIT|BEGIN|ROLLBACK)\s*;", sql, re.MULTILINE | re.IGNORECASE)
    assert sql.startswith(
        "-- etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql")


def test_f138_r11_00_setup_crea_el_esquema_restringido() -> None:
    assert "CREATE SCHEMA IF NOT EXISTS compras_restringida;" in _texto(DIR_SQL / "00_setup.sql")
