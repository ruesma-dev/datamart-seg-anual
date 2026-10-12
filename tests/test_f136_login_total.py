# tests/test_f136_login_total.py
"""
F-136 · El login de acceso TOTAL del MCP (`mcp_sigrid_dm_total`) y la higiene
de `psql` con las contraseñas.

Vocabulario de la spec: ESTÁNDAR = `mcp_sigrid_dm_ro` (MCP y Power BI);
AUTORIZADO = `sigrid_dm_restringido_ro` (grupo NOLOGIN de F-135); TOTAL =
`mcp_sigrid_dm_total` (login nuevo, miembro de los dos); VETADOS DEL TOTAL =
`PG_TOTAL_VETOED_SCHEMAS` (`raw`, decisión del humano: «siempre fuera»).

Ningún test abre red ni BBDD: el cliente se simula. La prueba con PostgreSQL 16
real está en `progress/impl_F-136.md` (T10).
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ESTANDAR = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_restringido_ro"
TOTAL = "mcp_sigrid_dm_total"
DUENO = "sigrid_dm_etl"
RESTR = "contabilidad_restringida"


# ===========================================================================
# R1 · configuración (T1)
# ===========================================================================


def test_f136_r1_settings_por_defecto() -> None:
    from config.settings import (
        DEFAULT_TOTAL_ROLE,
        DEFAULT_TOTAL_VETOED_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_TOTAL_ROLE == TOTAL
    assert DEFAULT_TOTAL_VETOED_SCHEMAS == "raw"
    pg = PostgresSettings(_env_file=None)
    assert pg.total_role == TOTAL
    assert pg.total_vetoed_schemas == "raw"
    assert pg.total_vetoed_schema_list == ["raw"]


def test_f136_r1_settings_lista_sin_blancos_ni_vacios() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(_env_file=None, total_vetoed_schemas=" raw ,, otro ,")
    assert pg.total_vetoed_schema_list == ["raw", "otro"]
    assert PostgresSettings(_env_file=None, total_vetoed_schemas="").total_vetoed_schema_list == []
    assert PostgresSettings(_env_file=None, total_vetoed_schemas=" , ").total_vetoed_schema_list == []


def test_f136_r1_settings_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import PostgresSettings

    monkeypatch.setenv("PG_TOTAL_ROLE", "rol_total_x")
    monkeypatch.setenv("PG_TOTAL_VETOED_SCHEMAS", "raw,stg")
    pg = PostgresSettings(_env_file=None)
    assert (pg.total_role, pg.total_vetoed_schema_list) == ("rol_total_x", ["raw", "stg"])


def test_f136_r1_settings_vacio_desactiva_el_total(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import PostgresSettings

    monkeypatch.setenv("PG_TOTAL_ROLE", "")
    assert PostgresSettings(_env_file=None).total_role == ""


def test_f136_r1_env_example_documenta_las_dos() -> None:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    lineas = dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )
    assert lineas["PG_TOTAL_ROLE"] == TOTAL
    assert lineas["PG_TOTAL_VETOED_SCHEMAS"] == "raw"
    bloque = texto.split("PG_TOTAL_ROLE=")[0].rsplit("\n\n", 1)[-1]
    assert "F-136" in bloque, "la variable lleva su porqué delante"


def test_f136_r1_settings_comentario_con_la_decision_del_humano() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    bloque = texto.split("DEFAULT_TOTAL_VETOED_SCHEMAS =")[0].rsplit("\n\n", 1)[-1]
    assert "F-136" in bloque and "siempre fuera" in bloque, (
        "quien quiera dar raw al total tiene que leer que el humano lo prohibió"
    )


def test_f136_r1_el_job_no_necesita_variables_nuevas() -> None:
    """Los defectos viven en el código: ni `dev.json` ni el job cambian."""
    for ruta in (RAIZ / "infra" / "env" / "dev.json", RAIZ / "infra" / "80_create_job.ps1"):
        assert "PG_TOTAL" not in ruta.read_text(encoding="utf-8-sig"), ruta.name


# ===========================================================================
# El cliente (T2): con conexión simulada, sin BBDD
# ===========================================================================


class _Cursor:
    def __init__(self, registro: list, filas: list) -> None:
        self._registro = registro
        self._filas = filas

    def execute(self, stmt: object, params: object = None) -> None:
        self._registro.append((stmt, params))

    def fetchall(self) -> list:
        return list(self._filas)

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *a: object) -> None:
        return None


class _Conn:
    def __init__(self, registro: list, filas: list, aperturas: list) -> None:
        self._registro = registro
        self._filas = filas
        aperturas.append(1)

    def cursor(self) -> _Cursor:
        return _Cursor(self._registro, self._filas)

    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *a: object) -> None:
        return None


def _cliente(esquemas: list[str], filas: list | None = None) -> tuple[object, list, list]:
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    registro: list = []
    aperturas: list = []
    cliente = PostgresClient.__new__(PostgresClient)
    cliente._target_db = "sigrid_dm"  # type: ignore[attr-defined]
    cliente.list_schemas = lambda: esquemas  # type: ignore[method-assign]
    cliente.connection = lambda: _Conn(registro, filas or [], aperturas)  # type: ignore[method-assign]
    return cliente, registro, aperturas


def test_f136_cliente_apply_veto_solo_sobre_lo_que_existe() -> None:
    from etl_sigrid.infrastructure.postgres import grants

    cliente, registro, _ = _cliente(["mart", "raw"])
    sentencias = cliente.apply_veto(TOTAL, DUENO, ["raw", "fantasma"])  # type: ignore[attr-defined]
    assert sentencias == grants.build_veto_statements(TOTAL, DUENO, ["raw"])
    assert [s for s, _ in registro] == sentencias, "ejecuta exactamente lo que devuelve"
    assert len(sentencias) == 3, "tablas, USAGE y privilegio por defecto"


def test_f136_cliente_apply_veto_vacio_no_abre_cursor() -> None:
    cliente, registro, aperturas = _cliente(["mart"])
    assert cliente.apply_veto(TOTAL, DUENO, ["raw"]) == []  # type: ignore[attr-defined]
    assert cliente.apply_veto(TOTAL, DUENO, []) == []  # type: ignore[attr-defined]
    assert registro == [] and aperturas == [], "sin esquemas que vetar, ni conexión"


def test_f136_cliente_apply_veto_lo_anota(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.infrastructure.postgres import postgres_client

    anotado: list[tuple[str, dict]] = []

    class _Log:
        def info(self, evento: str, **datos: object) -> None:
            anotado.append((evento, datos))

    monkeypatch.setattr(postgres_client, "logger", _Log())
    cliente, _, _ = _cliente(["raw"])
    cliente.apply_veto(TOTAL, DUENO, ["raw"])  # type: ignore[attr-defined]
    assert anotado == [("grants_veto_aplicado", {"role": TOTAL, "schemas": ["raw"], "statements": 3})]


def test_f136_cliente_esquemas_sin_usage_pregunta_al_catalogo() -> None:
    cliente, registro, _ = _cliente([], filas=[(RESTR,)])
    faltan = cliente.esquemas_sin_usage(TOTAL, ["mart", RESTR])  # type: ignore[attr-defined]
    assert faltan == [RESTR]
    ((sql, params),) = registro
    assert params == (["mart", RESTR], TOTAL)
    plano = " ".join(sql.split())
    assert "n.nspname = ANY(%s)" in plano
    assert "NOT has_schema_privilege(%s, n.oid, 'USAGE')" in plano
    assert plano.startswith("SELECT") and plano.endswith("ORDER BY 1"), "solo catálogo"


def test_f136_cliente_esquemas_sin_usage_vacia_si_tiene_todo() -> None:
    cliente, _, _ = _cliente([], filas=[])
    assert cliente.esquemas_sin_usage(TOTAL, ["mart"]) == []  # type: ignore[attr-defined]


def test_f136_cliente_esquemas_sin_usage_sin_lista_no_abre_cursor() -> None:
    cliente, registro, aperturas = _cliente([], filas=[("x",)])
    assert cliente.esquemas_sin_usage(TOTAL, []) == []  # type: ignore[attr-defined]
    assert registro == [] and aperturas == []


def test_f136_cliente_sql_esquemas_sin_usage_es_la_del_diseno() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_ESQUEMAS_SIN_USAGE

    assert " ".join(SQL_ESQUEMAS_SIN_USAGE.split()) == (
        "SELECT n.nspname FROM pg_namespace n WHERE n.nspname = ANY(%s) "
        "AND NOT has_schema_privilege(%s, n.oid, 'USAGE') ORDER BY 1"
    )
