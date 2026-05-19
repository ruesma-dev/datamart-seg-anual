# tests/test_sql_split.py
"""
Tests de los helpers de split de SQL en PostgresClient.

Estos helpers son críticos: permiten ejecutar archivos SQL con múltiples
statements cuando se pasan parámetros (psycopg no admite prepared statements
con múltiples comandos).
"""

from __future__ import annotations

from etl_sigrid.infrastructure.postgres.postgres_client import (
    _split_sql_statements,
    _statement_has_placeholders,
)


def test_split_simple_two_statements() -> None:
    """Caso típico: dos statements separados por ;."""
    sql = "TRUNCATE TABLE foo; INSERT INTO foo VALUES (1);"
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2
    assert stmts[0] == "TRUNCATE TABLE foo"
    assert stmts[1] == "INSERT INTO foo VALUES (1)"


def test_split_ignores_semicolons_in_strings() -> None:
    """Los ; dentro de strings literales no son separadores."""
    sql = "INSERT INTO foo VALUES ('a;b;c'); SELECT 1;"
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2
    assert "'a;b;c'" in stmts[0]


def test_split_ignores_semicolons_in_line_comments() -> None:
    """Los ; dentro de comentarios -- no son separadores."""
    sql = "INSERT INTO foo VALUES (1); -- esto es ;ignorado\nSELECT 1;"
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2


def test_split_empty_lines_dont_create_empty_statements() -> None:
    """Las líneas en blanco y los ;; consecutivos no crean statements vacíos."""
    sql = "SELECT 1;\n\n\nSELECT 2;;\n;\nSELECT 3;"
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 3
    assert stmts == ["SELECT 1", "SELECT 2", "SELECT 3"]


def test_split_handles_double_quotes_in_strings() -> None:
    """Las comillas simples dobles '' dentro de un string son escape, no fin."""
    sql = "INSERT INTO t VALUES ('it''s'); SELECT 1;"
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2


def test_has_placeholders_dict_match() -> None:
    """Detecta placeholders nombrados cuando existen claves en el dict."""
    assert _statement_has_placeholders(
        "WHERE cod = %(cod)s AND val = %(val)s",
        {"cod": "15", "val": 1},
    )


def test_has_placeholders_dict_no_match() -> None:
    """No detecta placeholders si las claves del dict no aparecen en el SQL."""
    assert not _statement_has_placeholders(
        "TRUNCATE TABLE foo",
        {"cod": "15"},
    )


def test_has_placeholders_ignores_comments() -> None:
    """Los placeholders en comentarios NO cuentan."""
    assert not _statement_has_placeholders(
        "TRUNCATE TABLE foo -- el placeholder %(cod)s no debe contar",
        {"cod": "15"},
    )


def test_has_placeholders_tuple_match() -> None:
    """Detecta placeholders posicionales %s."""
    assert _statement_has_placeholders("WHERE cod = %s", ("15",))


def test_has_placeholders_tuple_no_match() -> None:
    """No detecta placeholders posicionales si no hay %s."""
    assert not _statement_has_placeholders("TRUNCATE TABLE foo", ("15",))


def test_real_world_case_truncate_plus_parametrized_insert() -> None:
    """Caso real del fichero 07_version_master_vigente.sql."""
    sql = """
    TRUNCATE TABLE stg.version_master_vigente;

    INSERT INTO stg.version_master_vigente (obra_id, version_vigente)
    SELECT conide, MAX(valn::INTEGER)
    FROM raw.conext
    WHERE cod = %(cod)s
      AND valn IS NOT NULL
    GROUP BY conide;
    """
    stmts = _split_sql_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("TRUNCATE")
    assert stmts[1].startswith("INSERT")

    params = {"cod": "15"}
    assert not _statement_has_placeholders(stmts[0], params)
    assert _statement_has_placeholders(stmts[1], params)
