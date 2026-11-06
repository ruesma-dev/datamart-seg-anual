# tests/test_f157_sql.py
"""
F-157 · El SQL de la fase 0 planificada, leído como texto (R1-R4, R6-R8, R11,
R13, R16, R18, R19).

La equivalencia con el master se vigila aquí comparando las EXPRESIONES (el
`CASE` de la regla, el regex, el descarte y las fórmulas de importe) de
`08_plan_mensual.sql` con las de `stg.fn_explotar_planif` y del 09, una vez
normalizadas. La equivalencia de RESULTADOS la da `test_f157_sandbox.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    FICHEROS_DEL_SELLO,
    MARCADOR_FILTRO_FASE0,
)
from etl_sigrid.infrastructure.postgres.postgres_client import TABLAS_ACOTADAS

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIO_SQL = DIRECTORIO_SQL_STG.parent


def _sql(nombre: str) -> str:
    return (DIRECTORIO_SQL_STG / nombre).read_text(encoding="utf-8")


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*(?!F\d+_)[\s\S]*?\*/", " ", texto)
    return "\n".join(re.sub(r"--.*$", "", linea) for linea in texto.splitlines())


def _normal(texto: str) -> str:
    return re.sub(r"\s+", " ", _sin_comentarios(texto)).strip()


def _funcion() -> str:
    """El cuerpo de `stg.fn_explotar_planif` dentro de `00_functions.sql`."""
    texto = _sql("00_functions.sql")
    inicio = texto.index("-- fn_explotar_planif (F-157)")
    fin = texto.index("$$;", texto.index("AS $$", inicio)) + 3
    return texto[inicio:fin]


def _tabla_ddl() -> str:
    texto = _sql("01_ddl.sql")
    inicio = texto.index("CREATE TABLE IF NOT EXISTS stg.plan_mensual_fase0")
    return texto[inicio : texto.index(");", inicio) + 2]


def _vista_ddl() -> str:
    texto = _sql("01_ddl.sql")
    inicio = texto.index("CREATE OR REPLACE VIEW stg.v_plan_mensual_fase0_cobertura")
    return texto[inicio : texto.index(";", inicio) + 1]


# El CASE de la regla tal y como lo escribe el master (R5).
_CASE_MASTER = re.compile(
    r"CASE\s+WHEN pct_acumulado_raw IS NOT NULL AND pct_acumulado_raw > 0[\s\S]*?END AS pct_acumulado\b"
)
_CASE_REGEX = re.compile(r"CASE\s+WHEN u\.valor ~[\s\S]*?END AS pct_acumulado_raw")


def _bloque(patron: re.Pattern[str], texto: str) -> str:
    hallado = patron.search(_sin_comentarios(texto))
    assert hallado, f"no se encuentra {patron.pattern[:40]}"
    return re.sub(r"\s+", " ", hallado.group(0)).strip()


# --- R8 · la función ---------------------------------------------------------


def test_f157_r8_funcion_firma() -> None:
    f = _normal(_funcion())
    assert "stg.fn_explotar_planif(p_planif TEXT)" in f
    assert (
        "RETURNS TABLE (posicion_mes INTEGER, pct_acumulado NUMERIC(18,6), "
        "pct_mes NUMERIC(18,6))" in f
    )
    assert "LANGUAGE sql IMMUTABLE PARALLEL SAFE" in f


def test_f157_r5_funcion_mismo_case_que_el_master() -> None:
    assert _bloque(_CASE_MASTER, _funcion()) == _bloque(
        _CASE_MASTER, _sql("08_plan_mensual.sql")
    )


def test_f157_r5_funcion_mismo_regex_que_el_master() -> None:
    assert _bloque(_CASE_REGEX, _funcion()) == _bloque(
        _CASE_REGEX, _sql("08_plan_mensual.sql")
    )


def test_f157_r5_funcion_mismas_ventanas_sin_cruzar_partidas() -> None:
    """Las ventanas del master sin `presupuesto_id`: la función ve un solo planif."""
    f = _normal(_funcion())
    assert "presupuesto_id" not in f
    assert "unnest(string_to_array(p_planif, '|')) WITH ORDINALITY AS u(valor, position)" in f
    assert "WHERE u.valor IS NOT NULL AND length(trim(u.valor)) > 0" in f
    assert "ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING ) AS max_posterior" in f
    assert "COUNT(pct_positivo) OVER" in f
    assert "PARTITION BY grupo_positivo" in f
    assert "LAG(pct_acumulado) OVER" in f
    # Las únicas particiones: la del grupo del último positivo.
    assert re.findall(r"PARTITION BY (\w+)", f) == ["grupo_positivo"]


def test_f157_r8_funcion_no_filtra() -> None:
    """El descarte de R6 lo aplica el 09: la sandbox compara todas las posiciones."""
    assert "2.5" not in _normal(_funcion())


def test_f157_r8_funcion_avisa_de_su_gemela() -> None:
    assert "08_plan_mensual.sql" in _funcion()
    assert "test_f157_sql.py" in _funcion()


# --- R1, R11 · el DDL --------------------------------------------------------


COLUMNAS_R1 = [
    ("presupuesto_id", "BIGINT"),
    ("obra_id", "BIGINT"),
    ("partida_id", "BIGINT"),
    ("ambito_id", "INTEGER"),
    ("mes_inicio", "DATE"),
    ("anio_mes", "DATE"),
    ("posicion_mes", "INTEGER"),
    ("pct_acumulado", "NUMERIC(18,6)"),
    ("pct_mes", "NUMERIC(18,6)"),
    ("precio_unitario", "NUMERIC(20,6)"),
    ("can_mes", "NUMERIC(20,6)"),
    ("can_origen", "NUMERIC(20,6)"),
    ("importe_mes", "NUMERIC(18,2)"),
    ("importe_origen", "NUMERIC(18,2)"),
    ("importe_mes_raw", "NUMERIC(18,2)"),
    ("importe_origen_raw", "NUMERIC(18,2)"),
    ("importe_partida", "NUMERIC(18,2)"),
    ("_built_at", "TIMESTAMP"),
]


@pytest.mark.parametrize(("columna", "tipo"), COLUMNAS_R1)
def test_f157_r1_columna_con_su_tipo(columna: str, tipo: str) -> None:
    assert re.search(rf"^\s*{columna}\s+{re.escape(tipo)}\b", _tabla_ddl(), re.M), columna


def test_f157_r1_sin_columnas_de_mas_ni_version() -> None:
    nombres = re.findall(r"^\s*([a-z_]+)\s+[A-Z]", _tabla_ddl(), re.M)
    assert nombres == [c for c, _ in COLUMNAS_R1]
    assert "version" not in nombres


def test_f157_r1_clave_primaria_de_negocio_y_check_de_ambito() -> None:
    t = _normal(_tabla_ddl())
    assert "PRIMARY KEY (obra_id, ambito_id, partida_id, anio_mes)" in t
    assert "CHECK (ambito_id IN (3, 7))" in t
    assert "BIGSERIAL" not in t


def test_f157_r1_va_detras_de_plan_mensual() -> None:
    texto = _sql("01_ddl.sql")
    assert texto.index("CREATE TABLE IF NOT EXISTS stg.plan_mensual (") < texto.index(
        "CREATE TABLE IF NOT EXISTS stg.plan_mensual_fase0"
    )


def test_f157_r11_vista_de_cobertura() -> None:
    v = _normal(_vista_ddl())
    for columna in (
        "obra_id",
        "ambito_id",
        "mes_inicio",
        "partidas",
        "partidas_planificadas",
        "importe_fase0",
        "importe_planificado",
        "importe_sin_planificar",
    ):
        assert re.search(rf"\b{columna}\b", v), columna
    assert "FROM stg.presupuesto" in v
    assert "LEFT JOIN" in v
    assert "pp.fase_num = 0" in v
    assert "pp.ambito_id IN (3, 7)" in v
    assert "GROUP BY pp.obra_id, pp.ambito_id" in v


# --- R2-R4, R6, R7, R10, R13 · el 09 -----------------------------------------


def _09() -> str:
    return _sql("09_plan_mensual_fase0.sql")


def test_f157_r12_cabecera_con_su_ruta() -> None:
    assert _09().splitlines()[0] == (
        "-- etl_sigrid/infrastructure/postgres/sql/stg/09_plan_mensual_fase0.sql"
    )


def test_f157_r13_marcador_una_vez_dentro_de_un_any() -> None:
    assert _09().count(MARCADOR_FILTRO_FASE0) == 1
    assert re.search(r"=\s*ANY\s*\(\s*/\*F157_FILTRO_OBRAS\*/\s*\)", _09())


def test_f157_r13_sin_truncate_ni_drop_ni_ventanas() -> None:
    codigo = _sin_comentarios(_09()).upper()
    assert "TRUNCATE" not in codigo
    assert "DROP" not in codigo
    assert "PARTITION BY" not in codigo
    assert " OVER " not in codigo and " OVER(" not in codigo


def test_f157_r2_r3_solo_fase_0_de_3_y_7_con_plafec_la_de_ide_mayor() -> None:
    c = _normal(_09())
    assert "fa.fas = 0" in c
    assert "fa.amb IN (3, 7)" in c
    assert "fa.plafec > 0" in c
    assert "DISTINCT ON (fa.obride, fa.amb)" in c
    assert "ORDER BY fa.obride, fa.amb, fa.ide DESC" in c
    assert "pp.fase_num = 0" in c
    assert "pp.ambito_id IN (3, 7)" in c
    assert "op.planif IS NOT NULL AND length(trim(op.planif)) >= 1" in c


def test_f157_r13_el_marcador_filtra_en_fa0() -> None:
    """Solo en la CTE de `obrfasamb`: filtra por obra antes del JOIN."""
    c = _sin_comentarios(_09())
    fa0 = c[c.index("fa0 AS (") : c.index("base AS (")]
    assert MARCADOR_FILTRO_FASE0 in fa0


def test_f157_r4_mes_de_inicio_y_anio_mes() -> None:
    c = _normal(_09())
    assert "date_trunc('month', stg.fn_sigrid_date_to_date(fa0.plafec))::DATE AS mes_inicio" in c
    assert "(mes_inicio + ((posicion_mes - 1) * INTERVAL '1 month'))::DATE AS anio_mes" in c


def test_f157_r8_usa_la_funcion() -> None:
    assert "CROSS JOIN LATERAL stg.fn_explotar_planif(b.planif) e" in _normal(_09())


def test_f157_r6_mismo_descarte_que_el_master() -> None:
    descarte = "WHERE NOT (pct_acumulado = 0 AND pct_mes = 0) AND pct_acumulado <= 2.5"
    assert descarte in _normal(_sql("08_plan_mensual.sql"))
    assert descarte in _normal(_09())


FORMULAS_MASTER = [
    "ROUND((cantidad * pct_mes)::NUMERIC, 6) AS can_mes",
    "ROUND((cantidad * pct_acumulado)::NUMERIC, 6) AS can_origen",
    "ROUND( (cantidad * pct_mes) * ROUND(precio::NUMERIC, dec_precios), dec_importes ) AS importe_mes",
    "ROUND( (cantidad * pct_acumulado) * ROUND(precio::NUMERIC, dec_precios), dec_importes ) AS importe_origen",
    "ROUND((cantidad * pct_mes * precio)::NUMERIC, 2) AS importe_mes_raw",
    "ROUND((cantidad * pct_acumulado * precio)::NUMERIC, 2) AS importe_origen_raw",
]


@pytest.mark.parametrize("formula", FORMULAS_MASTER)
def test_f157_r7_formula_literal_del_master(formula: str) -> None:
    assert formula in _normal(_sql("08_plan_mensual.sql")), "la referencia ha cambiado"
    assert formula in _normal(_09())


def test_f157_r7_importe_partida_es_el_de_presupuesto() -> None:
    assert "importe AS importe_partida" in _normal(_09())


def test_f157_r2_inserta_en_la_tabla_nueva() -> None:
    assert "INSERT INTO stg.plan_mensual_fase0" in _normal(_09())
    assert "INSERT INTO stg.plan_mensual " not in _normal(_09())


# --- R16 · el sello y las tablas acotadas ------------------------------------


def test_f157_r16_el_09_entra_en_el_sello_tras_el_08() -> None:
    assert FICHEROS_DEL_SELLO == (
        "00_functions.sql",
        "06_presupuesto.sql",
        "08_plan_mensual.sql",
        "09_plan_mensual_fase0.sql",
    )


def test_f157_r16_tabla_acotada() -> None:
    assert "plan_mensual_fase0" in TABLAS_ACOTADAS


# --- R18, R19 · sin regresión -------------------------------------------------


def test_f157_r18_el_08_no_la_menciona() -> None:
    assert "plan_mensual_fase0" not in _sql("08_plan_mensual.sql")
    assert "fn_explotar_planif" not in _sql("08_plan_mensual.sql")


def test_f157_r18_el_08_sigue_fijado_por_su_huella() -> None:
    """El 08 no cambia: ya lo fija `test_f073_sql.py` con el sha256 del fichero.

    No se añade aquí un `git diff` contra la base: sería un test permanente que
    prohibiría cambiar `mart/` o `cierre/` a cualquier feature futura. El diff
    contra `main` de T7 queda en el informe de F-157.
    """
    from tests import test_f073_sql

    assert hasattr(test_f073_sql, "HASH_08_PLAN_MENSUAL")


def test_f157_r19_nadie_fuera_de_stg_lee_la_tabla() -> None:
    """Ni un SQL fuera de `sql/stg/` ni un `.py` de infraestructura (salvo el cliente)."""
    culpables = [
        str(p.relative_to(RAIZ))
        for p in DIRECTORIO_SQL.rglob("*.sql")
        if "stg" not in p.relative_to(DIRECTORIO_SQL).parts[:1]
        and "plan_mensual_fase0" in p.read_text(encoding="utf-8")
    ]
    permitidos = {"postgres_client.py"}
    culpables += [
        str(p.relative_to(RAIZ))
        for p in (RAIZ / "etl_sigrid" / "infrastructure").rglob("*.py")
        if p.name not in permitidos
        and "plan_mensual_fase0" in p.read_text(encoding="utf-8")
    ]
    assert culpables == []
