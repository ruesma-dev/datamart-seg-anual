# tests/test_f168_sql.py
"""
F-168 · El SQL del texto largo, leído sin base de datos.

- `stg/11_texto_largo.sql`: las funciones de limpieza e identidad, con los
  literales del dominio (R5-R8).
- `stg/12_partida_texto.sql`: el texto de la partida, sin filtro de ámbito
  (R9, R10, R23).
- `compras/16_textos_linea.sql`: las cinco fuentes del flujo, el catálogo
  deduplicado y la vista (R12-R17, R23).
- `compras/07_texto.sql`: el memo de comparativos y ofertas (R18).
- Los sub-pasos nuevos en `build_stg` y `build_compras`.

Lo que hace el SQL de verdad lo prueba `tests/test_f168_sandbox.py` contra un
Postgres de usar y tirar.
"""

from __future__ import annotations

import re
from pathlib import Path

from etl_sigrid.domain import texto_largo as tl

RAIZ = Path(__file__).resolve().parents[1]
DIR_SQL = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql"
TEXTO_LARGO = DIR_SQL / "stg" / "11_texto_largo.sql"
PARTIDA_TEXTO = DIR_SQL / "stg" / "12_partida_texto.sql"
STEP_STG = RAIZ / "etl_sigrid" / "application" / "steps" / "build_stg_step.py"


def _crudo(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    return re.sub(r"--[^\n]*", "", texto)


def _compacto(ruta: Path) -> str:
    return " ".join(_sin_comentarios(_crudo(ruta)).split())


# ---------------------------------------------------------------------------
# R5 · R6 · R7 · R8 · las funciones de stg/11
# ---------------------------------------------------------------------------


def test_f168_r7_cabecera_con_la_ruta() -> None:
    for ruta in (TEXTO_LARGO, PARTIDA_TEXTO):
        primera = _crudo(ruta).splitlines()[0]
        assert primera == f"-- {ruta.relative_to(RAIZ).as_posix()}"


def test_f168_r7_el_sql_usa_los_literales_del_dominio() -> None:
    sql = _sin_comentarios(_crudo(TEXTO_LARGO))
    assert f"'{tl.PATRON_CONTROL}'" in sql, "el patrón de control es el del dominio"
    # Todo número de 4 o más cifras del fichero es el tope del dominio.
    numeros = set(re.findall(r"\b\d{4,}\b", sql))
    assert numeros == {str(tl.TOPE_CARACTERES)}, numeros
    extremos = "E'" + tl.EXTREMOS.replace("\t", "\\t").replace("\n", "\\n") + "'"
    assert sql.count(extremos) == 2, "btrim de los extremos antes y después del corte"


def test_f168_r5_el_orden_de_la_limpieza() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    esperado = (
        "SELECT NULLIF( btrim( left( btrim( regexp_replace( "
        "replace(replace(t, E'\\r\\n', E'\\n'), E'\\r', E'\\n'), "
        f"'{tl.PATRON_CONTROL}', '', 'g' ), E' \\t\\n' ), {tl.TOPE_CARACTERES} ), "
        "E' \\t\\n' ), '' )"
    )
    assert esperado in cuerpo


def test_f168_r6_texto_id_es_md5_uuid() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert "CREATE OR REPLACE FUNCTION stg.fn_texto_id(t TEXT) RETURNS UUID" in cuerpo
    assert "SELECT md5(t)::uuid" in cuerpo


def test_f168_r8_recortado_es_mayor_o_igual_que_el_tope() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert "CREATE OR REPLACE FUNCTION stg.fn_texto_recortado(t TEXT) RETURNS BOOLEAN" in cuerpo
    assert f"SELECT COALESCE(char_length(t) >= {tl.TOPE_CARACTERES}, FALSE)" in cuerpo


def test_f168_r5_funciones_inmutables_y_solo_funciones() -> None:
    cuerpo = _compacto(TEXTO_LARGO)
    assert cuerpo.count("IMMUTABLE PARALLEL SAFE") == 3
    for prohibido in ("CREATE TABLE", "DROP TABLE", "INSERT", "DELETE", "TRUNCATE"):
        assert prohibido not in cuerpo, f"stg/11 entra en el sello: solo funciones ({prohibido})"


# ---------------------------------------------------------------------------
# R9 · R10 · R23 · stg.partida_texto
# ---------------------------------------------------------------------------


def test_f168_r9_partida_texto_columnas_y_clave() -> None:
    cuerpo = _compacto(PARTIDA_TEXTO)
    for columna in ("partida_id", "obra_id", "codigo_partida", "descripcion_corta", "texto",
                    "texto_id", "bytes", "recortado"):
        assert re.search(rf"AS {columna}\b", cuerpo), columna
    assert "ALTER TABLE stg.partida_texto ADD PRIMARY KEY (partida_id);" in cuerpo
    assert "FROM raw.obrparpar o" in cuerpo
    assert "LEFT JOIN stg.partidas p ON p.partida_id = o.ide" in cuerpo
    assert "stg.fn_texto_largo(o.tex)" in cuerpo
    assert "stg.fn_texto_recortado(o.tex) AS recortado" in cuerpo
    assert "WHERE l.texto IS NOT NULL" in cuerpo


def test_f168_r10_sin_filtro_de_ambito_fase_ni_tipo() -> None:
    compacto = _compacto(PARTIDA_TEXTO)
    inicio = compacto.index("CREATE TABLE stg.partida_texto AS")
    cuerpo = compacto[inicio:compacto.index(";", inicio)]
    for vetado in ("amb", "fas", "tip", "tipdes", "obrparpre", "ambito_id", "fase_num"):
        assert not re.search(rf"\b{vetado}\b", cuerpo), (
            f"stg.partida_texto no filtra por {vetado} (R10)"
        )
    assert cuerpo.count("WHERE") == 1, "un solo filtro: el de texto no nulo"


def test_f168_r23_drop_y_create_en_un_solo_fichero_sin_commit() -> None:
    cuerpo = _compacto(PARTIDA_TEXTO)
    assert cuerpo.index("DROP TABLE IF EXISTS stg.partida_texto") < cuerpo.index(
        "CREATE TABLE stg.partida_texto AS"
    )
    for vetado in ("COMMIT", "BEGIN;", "ROLLBACK"):
        assert vetado not in cuerpo, "una sola transacción: la de execute_sql_file (R23)"


# ---------------------------------------------------------------------------
# Los sub-pasos de build_stg
# ---------------------------------------------------------------------------


def _sub_pasos_stg() -> list[tuple[str, str]]:
    return re.findall(r'_SubStep\(\s*"(\w+)",\s*"([\w.]*)"', _crudo(STEP_STG))


def test_f168_los_sub_pasos_de_stg_van_detras_de_master_versiones() -> None:
    pasos = _sub_pasos_stg()
    assert pasos[-3:] == [
        ("build_master_versiones", "10_master_versiones.sql"),
        ("texto_largo", "11_texto_largo.sql"),
        ("build_partida_texto", "12_partida_texto.sql"),
    ]
    bloque = re.search(r'_SubStep\(\s*"build_partida_texto".*?\)', _crudo(STEP_STG), re.S)
    assert bloque and '"stg"' in bloque.group(0) and '"partida_texto"' in bloque.group(0)
    for marca in ("acotado", "por_tramos", "es_plan_ventana"):
        assert marca not in bloque.group(0), f"{marca}: se ejecuta entero"


def test_f168_fuera_del_sello_de_stg_y_de_la_ventana() -> None:
    from etl_sigrid.application.steps.build_stg_step import FICHEROS_DEL_SELLO
    from etl_sigrid.infrastructure.postgres.postgres_client import TABLAS_ACOTADAS

    assert "11_texto_largo.sql" not in FICHEROS_DEL_SELLO
    assert "12_partida_texto.sql" not in FICHEROS_DEL_SELLO
    assert "partida_texto" not in TABLAS_ACOTADAS


def test_f168_el_preflight_exige_tex_en_obrparpar() -> None:
    texto = _crudo(STEP_STG)
    linea = re.search(r'\("raw", "obrparpar"\):\s*\[[^\]]*\]', texto)
    assert linea and '"tex"' in linea.group(0)

