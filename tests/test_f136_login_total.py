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
