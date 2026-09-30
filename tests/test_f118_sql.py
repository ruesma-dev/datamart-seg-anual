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
    "reales_relleno",
    "reales_meses",
    "reales_vigente_alta",
    "reales_filas",
    "reales_alta",
    "reales_rejilla",
    "reales_esqueleto",
    "reales_grupos",
    "reales_serie",
    "reales_con_lag",
    "reales_generador",
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


# ---------------------------------------------------------------------------
# `mart` (R15, R17)
# ---------------------------------------------------------------------------

_ARRAY_MESES = re.compile(r"\(ARRAY\['Enero',.*?'Diciembre'\]\)", re.DOTALL)


def _rama_mart(nombre: str) -> str:
    texto = _leer("mart/02_build_fact.sql")
    marcas = {
        "coste_real": ("-- ---- 1) COSTE REAL ----", "-- ---- 2) VENTA REAL ----"),
        "venta_real": ("-- ---- 2) VENTA REAL ----", "-- ---- 3) COSTE PLANIFICADO ----"),
        "coste_plan": ("-- ---- 3) COSTE PLANIFICADO ----", "-- ---- 4) VENTA PLANIFICADA ----"),
        "venta_plan": ("-- ---- 4) VENTA PLANIFICADA ----", ";"),
    }
    inicio, fin = marcas[nombre]
    return _entre(texto, inicio, fin)


@pytest.mark.parametrize("rama", ("coste_real", "venta_real"))
def test_f118_r17_mart_las_ramas_reales_derivan_nombre_mes_de_anio_mes(rama: str) -> None:
    """El texto de la fase ya no es el nombre del mes: va a `version_descripcion`."""
    cuerpo = _rama_mart(rama)
    assert _ARRAY_MESES.search(cuerpo), cuerpo
    assert "[EXTRACT(MONTH FROM pm.anio_mes)::INT]" in cuerpo
    assert re.search(r"pm\.version_descripcion,\s*'(Coste|Venta) Real'", cuerpo) is None
    assert "pm.version_descripcion, NULL::TEXT" in cuerpo


@pytest.mark.parametrize("rama", ("coste_real", "venta_real"))
def test_f118_r15_mart_las_ramas_reales_publican_las_dos_marcas(rama: str) -> None:
    cuerpo = _rama_mart(rama)
    assert "pm.es_relleno" in cuerpo and "pm.es_deshacer" in cuerpo


@pytest.mark.parametrize("rama", ("coste_plan", "venta_plan"))
def test_f118_r15_mart_las_ramas_planificadas_publican_null(rama: str) -> None:
    assert _rama_mart(rama).count("NULL::BOOLEAN") == 2


@pytest.mark.parametrize("columna", ("es_relleno", "es_deshacer"))
def test_f118_r15_mart_ddl_y_v_pbi_fact_publican_la_columna(columna: str) -> None:
    ddl = _leer("mart/01_ddl.sql")
    assert re.search(rf"\b{columna}\s+BOOLEAN", ddl), columna
    insert = _entre(_leer("mart/02_build_fact.sql"), "INSERT INTO", "-- ---- 1)")
    assert columna in insert
    vista = _entre(_leer("mart/05_views_powerbi.sql"), "CREATE VIEW mart.v_pbi_fact AS", ";")
    assert re.search(rf"\b{columna}\b", vista), vista


# ---------------------------------------------------------------------------
# `cierre` (R1, R15, R16, R38)
# ---------------------------------------------------------------------------


def test_f118_r1_cierre_fn_mes_de_fase_envuelve_la_de_stg() -> None:
    setup = _leer("cierre/00_setup.sql")
    funcion = _funcion(setup, "cierre.fn_mes_de_fase")
    assert "stg.fn_mes_de_fase(fecha_inicio, nombre_mes, fecha_fin, mes_archivado)" in funcion
    assert re.search(r"fecha_fin\s+DATE\s+DEFAULT\s+NULL", funcion)
    # La firma de dos argumentos se borra: convivir con la de cuatro con
    # DEFAULT haría ambigua cualquier llamada de dos argumentos.
    assert "DROP FUNCTION IF EXISTS cierre.fn_mes_de_fase(DATE, TEXT)" in setup


@pytest.mark.parametrize(
    "relativo", ("cierre/02_build_fact.sql", "cierre/04_views_detalle.sql")
)
def test_f118_r16_cierre_no_recalcula_el_mes_y_agrupa_por_pm_anio_mes(relativo: str) -> None:
    texto = _sin_comentarios(_leer(relativo))
    assert "fn_mes_de_fase(" not in texto
    assert "mes_canonico" not in texto
    assert re.search(r"GROUP BY pm\.obra_id, pm\.anio_mes", texto), relativo


def test_f118_r15_cierre_publica_es_relleno() -> None:
    ddl = _entre(_leer("cierre/01_ddl_fact.sql"), "CREATE TABLE cierre.fact_cierre_mensual (", ");")
    assert re.search(r"\bes_relleno\s+BOOLEAN", ddl)
    build = _sin_comentarios(_leer("cierre/02_build_fact.sql"))
    assert build.count("bool_and(pm.es_relleno)") == 4
    assert re.search(r"INSERT INTO cierre\.fact_cierre_mensual \([^;]*es_relleno", build)


def test_f118_r38_cierre_arrastra_el_ejecutado_de_un_concepto_sin_filas() -> None:
    """Un concepto sin filas en un mes con cierre de otro concepto conserva el
    ejecutado del mes anterior (D5), no cae a 0 para rebotar al siguiente."""
    build = _sin_comentarios(_leer("cierre/02_build_fact.sql"))
    assert "COALESCE(e.ejecutado_origen, 0)" not in build
    assert re.search(
        r"COUNT\(ejecutado_propio\) OVER \(\s*PARTITION BY obra_id, concepto ORDER BY anio_mes",
        build,
    ), build
    assert re.search(
        r"MAX\(ejecutado_propio\) OVER \(\s*PARTITION BY obra_id, concepto, grupo_ejecutado\s*\)",
        build,
    ), build


# ---------------------------------------------------------------------------
# `cierre.v_pbi_planif_vs_real`, blindada (R18, R19)
# ---------------------------------------------------------------------------


def _vista() -> str:
    return _sin_comentarios(_leer("cierre/06_views_planif_vs_real.sql"))


def test_f118_r18_vista_ningun_group_by_ni_join_usa_nombre_mes() -> None:
    texto = _vista()
    for grupo in re.findall(r"GROUP BY[^\n]*(?:\n\s+[^\n]*)*?\n\)", texto):
        assert "nombre_mes" not in grupo, grupo
    for union in re.findall(r"\bON\b[^\n]*(?:\n\s+AND[^\n]*)*", texto):
        assert "nombre_mes" not in union, union


def test_f118_r18_vista_base_agrupa_por_obra_mes_categoria_concepto() -> None:
    base = _entre(_vista(), "base AS (", "producc AS (")
    assert re.search(
        r"GROUP BY f\.obra_id, f\.anio_mes, f\.categoria, f\.concepto\s*\)", base
    ), base


def test_f118_r19_vista_beneficio_une_al_mismo_grano_que_agregan() -> None:
    texto = _vista()
    for cte, fin in (("producc AS (", "costes AS ("), ("total_costes AS (", "beneficio AS (")):
        assert re.search(r"GROUP BY obra_id, anio_mes\s*\)", _entre(texto, cte, fin)), cte
    beneficio = _entre(texto, "beneficio AS (", "todos AS (")
    assert re.search(
        r"ON tc\.obra_id\s+= p\.obra_id\s+AND tc\.anio_mes = p\.anio_mes\s*\)", beneficio
    ), beneficio


def test_f118_r18_vista_nombre_mes_sale_de_anio_mes_en_la_select_final() -> None:
    texto = _vista()
    final = texto[texto.rindex("SELECT") :]
    assert _ARRAY_MESES.search(final), final
    assert "[EXTRACT(MONTH FROM anio_mes)::INT]" in final
    # Ninguna CTE arrastra nombre_mes.
    assert "nombre_mes" not in texto[: texto.rindex("SELECT")]
