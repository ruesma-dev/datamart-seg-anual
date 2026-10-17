# tests/test_f141_perfil_restringido.py
"""
F-141 · El perfil RESTRINGIDO del datamart (administrativos): ve MENOS que el estándar.

Vocabulario de la spec: ESTÁNDAR = `mcp_sigrid_dm_ro`; AUTORIZADO = el grupo NOLOGIN que lee
las `*_restringida` (tras F-141, `sigrid_dm_autorizado_ro`); TOTAL = `mcp_sigrid_dm_total`;
RESTRINGIDO = el grupo `sigrid_dm_perfil_restringido_ro` (lleva los permisos) y su login
miembro `mcp_sigrid_dm_restringido`. Regla del humano (2026-10-16 y 17): «ven como el
estándar, menos el mayor, menos el mayor analítico, menos la cartera de cobros (pero sí a
retenciones)» y «personal también quítalo, y saldos cuenta también».

Ningún test abre red ni BBDD: el cliente se simula. La prueba con PostgreSQL 16 real está en
`progress/impl_F-141.md` (T11).
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ESTANDAR = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_autorizado_ro"
#: el nombre que F-141 retira (D6). Solo puede aparecer en 02_roles.sql, la guarda R3 y aquí.
RETIRADO = "sigrid_dm_restringido_ro"
TOTAL = "mcp_sigrid_dm_total"
GRUPO = "sigrid_dm_perfil_restringido_ro"
LOGIN = "mcp_sigrid_dm_restringido"
DUENO = "sigrid_dm_etl"
ESQUEMAS_R = ["mart", "cierre", "compras", "maestro", "retenciones", "contabilidad",
              "descompuestos", "stg", "aux", "_meta"]
EXCLUIDAS_R = ["contabilidad.mayor", "contabilidad.saldos_cuenta_mes"]
EXCEPCIONES = ("compras.vencimientos", "compras.v_facturas_pago", "compras.v_control_forma_pago")


# ===========================================================================
# R1-R2 · configuración (T1)
# ===========================================================================


def test_f141_r1_defectos_del_vocabulario() -> None:
    from config.settings import (
        DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES,
        DEFAULT_PERFIL_RESTRINGIDO_GROUP,
        DEFAULT_PERFIL_RESTRINGIDO_LOGIN,
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_PERFIL_RESTRINGIDO_GROUP == GRUPO
    assert DEFAULT_PERFIL_RESTRINGIDO_LOGIN == LOGIN
    assert DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS == ",".join(ESQUEMAS_R)
    assert DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES == ",".join(EXCLUIDAS_R)
    pg = PostgresSettings(_env_file=None)
    assert pg.perfil_restringido_group == GRUPO
    assert pg.perfil_restringido_login == LOGIN
    assert pg.perfil_restringido_schema_list == ESQUEMAS_R
    assert pg.perfil_restringido_excluded_table_list == EXCLUIDAS_R


def test_f141_r1_los_esquemas_son_el_consumo_menos_tesoreria_y_personal() -> None:
    """Lista EXPLÍCITA, pero hoy tiene que ser exactamente eso (D3, P2)."""
    from config.settings import PostgresSettings

    pg = PostgresSettings(_env_file=None)
    esperado = [s for s in pg.consumption_schema_list if s not in ("tesoreria", "personal")]
    assert pg.perfil_restringido_schema_list == esperado


def test_f141_r1_listas_sin_blancos_ni_vacios() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(
        _env_file=None,
        perfil_restringido_schemas=" mart ,, _meta ,",
        perfil_restringido_excluded_tables=" contabilidad.mayor , ,x.y,",
    )
    assert pg.perfil_restringido_schema_list == ["mart", "_meta"]
    assert pg.perfil_restringido_excluded_table_list == ["contabilidad.mayor", "x.y"]
    vacio = PostgresSettings(_env_file=None, perfil_restringido_schemas=" , ",
                             perfil_restringido_excluded_tables="")
    assert vacio.perfil_restringido_schema_list == []
    assert vacio.perfil_restringido_excluded_table_list == []


def test_f141_r1_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import PostgresSettings

    monkeypatch.setenv("PG_PERFIL_RESTRINGIDO_GROUP", "g_x")
    monkeypatch.setenv("PG_PERFIL_RESTRINGIDO_LOGIN", "l_x")
    monkeypatch.setenv("PG_PERFIL_RESTRINGIDO_SCHEMAS", "mart,_meta")
    monkeypatch.setenv("PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES", "mart.a")
    pg = PostgresSettings(_env_file=None)
    assert (pg.perfil_restringido_group, pg.perfil_restringido_login) == ("g_x", "l_x")
    assert pg.perfil_restringido_schema_list == ["mart", "_meta"]
    assert pg.perfil_restringido_excluded_table_list == ["mart.a"]


def _env_example() -> dict[str, str]:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    return dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )


def test_f141_r1_env_example_documenta_las_cuatro() -> None:
    lineas = _env_example()
    assert lineas["PG_PERFIL_RESTRINGIDO_GROUP"] == GRUPO
    assert lineas["PG_PERFIL_RESTRINGIDO_LOGIN"] == LOGIN
    assert lineas["PG_PERFIL_RESTRINGIDO_SCHEMAS"] == ",".join(ESQUEMAS_R)
    assert lineas["PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES"] == ",".join(EXCLUIDAS_R)
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    bloque = texto.split("PG_PERFIL_RESTRINGIDO_GROUP=")[0].rsplit("\n\n", 1)[-1]
    assert "F-141" in bloque, "las variables llevan su porqué delante"


def test_f141_r1_el_job_no_necesita_variables_nuevas() -> None:
    """Los defectos viven en el código: ni `dev.json` ni el job cambian."""
    for ruta in (RAIZ / "infra" / "env" / "dev.json", RAIZ / "infra" / "80_create_job.ps1"):
        texto = ruta.read_text(encoding="utf-8-sig")
        assert "PG_PERFIL_RESTRINGIDO" not in texto and "PG_RESTRICTED_ROLE" not in texto, ruta.name


def test_f141_r1_comentario_con_la_regla_literal_del_humano() -> None:
    import re

    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    bloque = texto.split("DEFAULT_PERFIL_RESTRINGIDO_GROUP =")[0].rsplit("\n\n", 1)[-1]
    plano = re.sub(r"\s*#\s*", " ", bloque)
    for cita in (
        "«ven como el estándar, menos el mayor, menos el mayor analítico, menos la cartera "
        "de cobros (pero sí a retenciones)»",
        "«personal también quítalo, y saldos cuenta también»",
        "F-141",
    ):
        assert cita in plano, f"el comentario no cita {cita}"
    assert "_restringida" in plano and "MÁS" in plano, (
        "avisa de que los esquemas *_restringida ven MÁS, al revés que este perfil"
    )


def test_f141_r2_el_autorizado_se_llama_ya_sigrid_dm_autorizado_ro() -> None:
    from config.settings import (
        DEFAULT_RESTRICTED_ROLE,
        NOMBRE_AUTORIZADO_RETIRADO,
        PostgresSettings,
    )

    assert DEFAULT_RESTRICTED_ROLE == AUTORIZADO
    assert NOMBRE_AUTORIZADO_RETIRADO == RETIRADO
    assert PostgresSettings(_env_file=None).restricted_role == AUTORIZADO
    assert _env_example()["PG_RESTRICTED_ROLE"] == AUTORIZADO
