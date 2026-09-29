# tests/test_f118_sql.py
"""
F-118 · Aserciones sobre el TEXTO del SQL que construye la serie real.

Sin conexión: se comprueba que los ficheros que ejecuta el build dicen lo que la
spec exige. Los nombres llevan la capa (`funciones`, `ddl`, `stg`, `sello`,
`mart`, `cierre`, `vista`, `diccionario`) para poder lanzar cada bloque con
`-k`, como pide `tasks.md`.

La lógica se prueba contra los oráculos puros (`test_f118_regla_mes.py`,
`test_f118_serie_densa.py`, `test_f118_invariante.py`); aquí se fija que el SQL
tiene la forma que hace posible esa equivalencia y que no conserva nada del
cálculo que producía el defecto.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    FICHEROS_DEL_SELLO,
    MARCADOR_FILTRO_OBRAS,
)
from etl_sigrid.domain import mes_fase

MARCADOR_INICIO_REALES = "/*F042_INICIO_REALES*/"
MARCADOR_FIN_REALES = "/*F042_FIN_REALES*/"

SQL = DIRECTORIO_SQL_STG.parent


@lru_cache(maxsize=None)
def _leer(relativo: str) -> str:
    return (SQL / relativo).read_bytes().decode("utf-8").replace("\r\n", "\n")


def _sin_comentarios(texto: str) -> str:
    return "\n".join(
        linea.split("--", 1)[0] if not linea.lstrip().startswith("--") else ""
        for linea in texto.splitlines()
    )


def _entre(texto: str, inicio: str, fin: str) -> str:
    desde = texto.index(inicio)
    return texto[desde : texto.index(fin, desde)]


def _funcion(texto: str, nombre: str) -> str:
    desde = texto.index(f"CREATE OR REPLACE FUNCTION {nombre}(")
    return texto[desde : texto.index("$$;", desde) + 3]


def _plan() -> str:
    return _leer("stg/08_plan_mensual.sql")


def _bloque_reales() -> str:
    texto = _plan()
    desde = texto.index(MARCADOR_INICIO_REALES) + len(MARCADOR_INICIO_REALES)
    return texto[desde : texto.index(MARCADOR_FIN_REALES)]


def _cte(nombre: str) -> str:
    """El cuerpo de una CTE del bloque de reales, hasta la siguiente."""
    bloque = _bloque_reales()
    desde = bloque.index(f"{nombre} AS (")
    siguiente = re.search(r"\n\w+ AS \(", bloque[desde + 1 :])
    fin = desde + 1 + siguiente.start() if siguiente else len(bloque)
    return _sin_comentarios(bloque[desde:fin])


# ---------------------------------------------------------------------------
# Las dos funciones de `stg` (R1-R6)
# ---------------------------------------------------------------------------


def _funciones_stg() -> str:
    return _leer("stg/00_functions.sql")


def test_f118_r1_funciones_stg_define_el_parser_y_la_cascada() -> None:
    texto = _funciones_stg()
    parser = _funcion(texto, "stg.fn_parse_mes_texto")
    cascada = _funcion(texto, "stg.fn_mes_de_fase")

    assert re.search(r"stg\.fn_parse_mes_texto\(\s*texto\s+TEXT\s*\)", parser)
    assert "IMMUTABLE" in parser and "RETURNS DATE" in parser
    assert re.search(
        r"fecha_inicio\s+DATE,\s*nombre_mes\s+TEXT,\s*fecha_fin\s+DATE\s+DEFAULT\s+NULL,"
        r"\s*mes_archivado\s+DATE\s+DEFAULT\s+NULL",
        cascada,
    ), cascada
    assert "IMMUTABLE" in cascada and "RETURNS DATE" in cascada


def test_f118_r6_funciones_la_cascada_va_texto_fin_inicio_archivado() -> None:
    cascada = _sin_comentarios(_funcion(_funciones_stg(), "stg.fn_mes_de_fase"))
    cuerpo = cascada[cascada.index("BEGIN") :]
    posiciones = [
        cuerpo.index("stg.fn_parse_mes_texto(nombre_mes)"),
        cuerpo.index("fecha_fin"),
        cuerpo.index("fecha_inicio"),
        cuerpo.index("mes_archivado"),
    ]
    assert posiciones == sorted(posiciones), cuerpo


def _prefijos_sql() -> list[tuple[str, int]]:
    parser = _funcion(_funciones_stg(), "stg.fn_parse_mes_texto")
    return [
        (prefijo, int(numero))
        for prefijo, numero in re.findall(
            r"WHEN tok LIKE '([A-Z]+)%' THEN mes_tok := (\d+);", parser
        )
    ]


def test_f118_r25_funciones_los_prefijos_de_mes_son_los_del_oraculo() -> None:
    """El parser SQL y el oráculo reconocen los mismos meses, en el mismo orden."""
    assert _prefijos_sql() == list(mes_fase._PREFIJOS_MES)
    parser = _funcion(_funciones_stg(), "stg.fn_parse_mes_texto")
    assert "tok = 'SEP' OR tok LIKE 'SEPT%' OR tok LIKE 'SET%'" in parser


@pytest.mark.parametrize(
    "patron",
    (
        mes_fase._MILLAR.pattern,
        mes_fase._LETRA_CIFRA.pattern,
        mes_fase._CIFRA_LETRA.pattern,
        mes_fase._SEPARADOR.pattern,
    ),
)
def test_f118_r4_funciones_la_normalizacion_es_la_del_oraculo(patron: str) -> None:
    """Punto de millar, letras y cifras pegadas y separadores: mismos patrones."""
    parser = _funcion(_funciones_stg(), "stg.fn_parse_mes_texto")
    assert f"'{patron}'" in parser, patron


def test_f118_r3_r4_funciones_las_reglas_del_anio_son_las_del_oraculo() -> None:
    """Cuatro cifras 2000-2099; dos cifras tras un mes; dos 20-99 sin año."""
    parser = _sin_comentarios(_funcion(_funciones_stg(), "stg.fn_parse_mes_texto"))
    assert "length(tok) = 4 AND tmp BETWEEN 2000 AND 2099" in parser
    assert "length(tok) = 2 AND tras_mes" in parser
    assert "length(tok) = 2 AND tmp >= 20 AND anio_int IS NULL" in parser
    assert "length(tok) <= 2 AND tmp BETWEEN 1 AND 12 AND mes_int IS NULL" in parser


HASH_CIERRE_PARSE = "fd3e56bcf8667e9ef31c3825178c9ab7df30e14f04796386e208bd637738cabe"
HASH_CIERRE_MES_MASTER = "dbaa95764f66a0938f4f706d12a3c019d7444ea1d64d7a25ba3d584a60d9e586"


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    (
        ("cierre.fn_parse_mes_fase", HASH_CIERRE_PARSE),
        ("cierre.fn_mes_de_version_master", HASH_CIERRE_MES_MASTER),
    ),
)
def test_f118_r5_funciones_el_parser_de_los_master_no_cambia(nombre, esperado) -> None:
    """R5: las versiones master siguen con el parser de `cierre`, byte a byte."""
    cuerpo = _funcion(_leer("cierre/00_setup.sql"), nombre)
    assert hashlib.sha256(cuerpo.encode("utf-8")).hexdigest() == esperado


# ---------------------------------------------------------------------------
# DDL (R15, R31)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("columna", ("es_relleno", "es_deshacer"))
def test_f118_r15_ddl_stg_plan_mensual_publica_la_columna(columna: str) -> None:
    ddl = _leer("stg/01_ddl.sql")
    tabla = _entre(ddl, "CREATE TABLE IF NOT EXISTS stg.plan_mensual (", ");")
    assert re.search(rf"\b{columna}\s+BOOLEAN\s+NULL", tabla), tabla
    # Y la migración para la tabla que ya existe en Azure.
    assert f"column_name = '{columna}'" in ddl
    assert f"ALTER TABLE stg.plan_mensual ADD COLUMN {columna} BOOLEAN NULL" in ddl


# ---------------------------------------------------------------------------
# La rama de reales de `08_plan_mensual.sql` (R7, R9, R29-R34)
# ---------------------------------------------------------------------------

CTE_DE_LA_SERIE = (
    "reales_base",
    "reales_cierres",
    "reales_vigente",
    "reales_filas",
    "reales_relleno",
    "reales_meses",
    "reales_alta",
    "reales_esqueleto",
    "reales_grupos",
    "reales_serie",
    "reales_con_lag",
    "reales_final",
)


@pytest.mark.parametrize("cte", CTE_DE_LA_SERIE)
def test_f118_r22_stg_la_serie_vive_entera_dentro_de_los_marcadores(cte: str) -> None:
    """`huella-obras --propuesta` reejecuta este bloque tal cual."""
    assert f"{cte} AS (" in _bloque_reales(), f"{cte} fuera del bloque de reales"


def test_f118_r22_stg_reales_final_es_la_ultima_cte_del_bloque() -> None:
    bloque = _bloque_reales().rstrip()
    ultima = re.findall(r"\n(\w+) AS \(", bloque)[-1]
    assert ultima == "reales_final"
    assert "INSERT INTO" not in bloque and not bloque.endswith(",")


def test_f118_r22_stg_un_solo_marcador_de_tramo_en_el_bloque() -> None:
    """La huella sustituye el marcador UNA vez; el fichero lo lleva dos (dos ramas)."""
    assert _bloque_reales().count(MARCADOR_FILTRO_OBRAS) == 1
    assert _plan().count(MARCADOR_FILTRO_OBRAS) == 2


def test_f118_r7_stg_el_mes_de_la_fila_real_sale_del_texto_de_su_fase() -> None:
    cierres = _cte("reales_cierres")
    assert re.search(
        r"stg\.fn_mes_de_fase\(\s*f\.fecha_inicio,\s*f\.nombre_mes,\s*f\.fecha_fin",
        cierres,
    ), cierres
    assert not re.search(
        r"make_date\(f\.anio,\s*f\.mes,\s*1\)\s+AS\s+anio_mes", _bloque_reales()
    ), "el mes de la fila real ya no es el ano/mes archivado"


def test_f118_r9_stg_sin_orden_fase_ni_case_de_consecutividad() -> None:
    """El defecto era publicar el acumulado entero cuando la fila anterior no
    era de la fase consecutiva. Ni `orden_fase` ni ese `CASE` quedan."""
    bloque = _sin_comentarios(_bloque_reales())
    assert "orden_fase" not in bloque
    assert "reales_orden" not in bloque
    assert not re.search(r"CASE\s+WHEN\s+LAG", bloque)
    assert "mes_fase_num - 1" not in bloque


def test_f118_r9_stg_el_movimiento_es_la_diferencia_con_el_mes_anterior() -> None:
    con_lag = _cte("reales_con_lag")
    for acumulado in (
        "importe_origen_round",
        "importe_origen_raw",
        "cantidad",
        "total_incurrido_raw",
    ):
        assert re.search(
            rf"{acumulado}\s*-\s*COALESCE\(LAG\({acumulado}\) OVER w, 0\)", con_lag
        ), acumulado
    assert re.search(
        r"WINDOW w AS \(\s*PARTITION BY obra_id, partida_id, ambito_id\s+"
        r"ORDER BY anio_mes\s*\)",
        con_lag,
    ), con_lag


def test_f118_r29_stg_un_cierre_sin_fila_vale_cero_y_el_relleno_arrastra() -> None:
    grupos = _cte("reales_grupos")
    serie = _cte("reales_serie")
    # El grupo del arrastre cuenta los meses que NO son de relleno (cierres,
    # con o sin fila): el relleno hereda del último cierre, ya deshecho.
    assert re.search(r"COUNT\(CASE WHEN NOT es_relleno THEN 1 END\) OVER", grupos)
    # Un cierre sin fila: 0. Con fila: su valor, aunque sea NULL.
    assert re.search(
        r"WHEN tiene_fila THEN importe_origen_round\s+ELSE 0", grupos
    ), grupos
    assert "PARTITION BY obra_id, partida_id, ambito_id, grupo_cierre" in serie


def test_f118_r34_stg_los_meses_son_por_obra_y_ambito() -> None:
    """Una fase sin filas del ámbito no es mes de ese ámbito: los meses salen
    de `reales_vigente`, que agrupa por (obra, ámbito)."""
    meses = _cte("reales_meses")
    assert "FROM reales_vigente" in meses
    relleno = _cte("reales_relleno")
    assert "DISTINCT ON (v.obra_id, v.ambito_id, gs.mes)" in relleno
    assert "NOT EXISTS" in relleno


def test_f118_r32_stg_reales_final_solo_publica_lo_que_mueve() -> None:
    final = _cte("reales_final")
    assert "WHERE tiene_fila" in final
    assert re.search(r"OR \(es_relleno AND", final)
    assert re.search(r"OR \(NOT es_relleno AND NOT tiene_fila AND", final)


def test_f118_r15_stg_el_insert_lee_reales_final_y_escribe_las_dos_marcas() -> None:
    texto = _plan()
    insert = _entre(texto, "INSERT INTO stg.plan_mensual (", ")")
    assert "es_relleno" in insert and "es_deshacer" in insert
    reales = texto[texto.index("-- ---- reales ----") :]
    assert "FROM reales_final;" in reales
    assert re.search(r"\bes_relleno\b", reales) and re.search(r"\bes_deshacer\b", reales)
    master = _entre(texto, "-- ---- master ----", "UNION ALL")
    assert re.search(r"NULL::BOOLEAN\s+AS es_relleno", master)
    assert re.search(r"NULL::BOOLEAN\s+AS es_deshacer", master)


# ---------------------------------------------------------------------------
# El sello (R28)
# ---------------------------------------------------------------------------


def test_f118_r28_sello_incluye_las_funciones_de_stg() -> None:
    """`00_functions.sql` da forma a `plan_mensual`: si cambia, se reconstruye todo."""
    assert FICHEROS_DEL_SELLO == (
        "00_functions.sql",
        "06_presupuesto.sql",
        "08_plan_mensual.sql",
    )
    for nombre in FICHEROS_DEL_SELLO:
        assert Path(DIRECTORIO_SQL_STG / nombre).is_file()
