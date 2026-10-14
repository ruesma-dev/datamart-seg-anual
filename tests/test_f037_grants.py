# tests/test_f037_grants.py
"""
F-037 · Los permisos de `tesoreria` y `tesoreria_restringida` (R20-R22).

Patrón de F-135/F-136: el rol ESTÁNDAR (`mcp_sigrid_dm_ro`) lee `tesoreria` y
nunca `tesoreria_restringida`; el AUTORIZADO (`sigrid_dm_restringido_ro`) la
lee; el TOTAL (`mcp_sigrid_dm_total`) la lee por pertenencia, sin GRANT propio,
y sigue sin leer `raw`. Todo vive en `config/settings.py` (listas), en
`apply_grants` (cada noche) y en `infra/sql/02_roles.sql` (provisión).

Ningún test abre red ni BBDD: el cliente se simula.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GENERAL = "tesoreria"
RESTR_T = "tesoreria_restringida"
RESTR_C = "contabilidad_restringida"


# ===========================================================================
# R20 · settings y .env.example (T6)
# ===========================================================================

def test_f037_r20_settings_tesoreria_en_consumo_y_no_la_restringida() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    consumo = DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    assert GENERAL in consumo
    assert RESTR_T not in consumo
    assert consumo == [
        "mart", "cierre", "compras", "maestro", "retenciones", "personal",
        "contabilidad", "tesoreria", "descompuestos", "stg", "aux", "_meta",
    ]


def test_f037_r20_settings_la_restringida_vetada_y_del_autorizado() -> None:
    from config.settings import (
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_TOTAL_VETOED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_VETOED_SCHEMAS == "contabilidad_restringida,tesoreria_restringida,raw"
    assert DEFAULT_RESTRICTED_SCHEMAS == "contabilidad_restringida,tesoreria_restringida"
    assert DEFAULT_TOTAL_VETOED_SCHEMAS == "raw", "el total SÍ lee tesoreria_restringida"
    pg = PostgresSettings(_env_file=None)
    assert pg.vetoed_schema_list == [RESTR_C, RESTR_T, "raw"]
    assert pg.restricted_schema_list == [RESTR_C, RESTR_T]
    assert GENERAL in pg.consumption_schema_list


def test_f037_r20_settings_env_example_igual_que_los_defectos() -> None:
    from config.settings import (
        DEFAULT_CONSUMPTION_SCHEMAS,
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
    )

    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    lineas = dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )
    assert lineas["PG_CONSUMPTION_SCHEMAS"] == DEFAULT_CONSUMPTION_SCHEMAS
    assert lineas["PG_VETOED_SCHEMAS"] == DEFAULT_VETOED_SCHEMAS
    assert lineas["PG_RESTRICTED_SCHEMAS"] == DEFAULT_RESTRICTED_SCHEMAS


def test_f037_r20_settings_los_comentarios_lo_explican() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    consumo = texto.split("DEFAULT_CONSUMPTION_SCHEMAS = (")[0]
    assert "F-037" in consumo and "tesoreria" in consumo
    vetados = texto.split("DEFAULT_VETOED_SCHEMAS =")[0].split("DEFAULT_CONSUMPTION_SCHEMAS = (")[1]
    assert "tesoreria_restringida" in vetados


# ===========================================================================
# R21 · apply_grants con las listas nuevas, cliente simulado (T7)
# ===========================================================================

ESTANDAR = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_restringido_ro"
TOTAL = "mcp_sigrid_dm_total"
DUENO = "sigrid_dm_etl"


class _ClienteFalso:
    """Apunta lo que se le pide; `indebidas` y `sin_usage` por rol."""

    def __init__(
        self,
        indebidas: dict[str, list[str]] | None = None,
        sin_usage: list[str] | None = None,
    ) -> None:
        self.indebidas = indebidas or {}
        self.sin_usage = sin_usage or []
        self.llamadas: list[tuple] = []

    def role_exists(self, role):
        self.llamadas.append(("role_exists", role))
        return role in (ESTANDAR, AUTORIZADO, TOTAL)

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):
        self.llamadas.append(("general", readonly_role, owner_role, list(schemas),
                              list(vetoed_schemas)))
        return ["G"]

    def apply_restricted_grants(self, role, owner_role, schemas):
        self.llamadas.append(("autorizado", role, owner_role, list(schemas)))
        return ["A"]

    def apply_veto(self, role, owner_role, schemas):
        self.llamadas.append(("veto", role, owner_role, list(schemas)))
        return ["V"]

    def lecturas_indebidas(self, role, schemas, tables):
        self.llamadas.append(("verifica", role, list(schemas)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):
        self.llamadas.append(("usage", role, list(schemas)))
        return list(self.sin_usage)


def _paso(cliente: _ClienteFalso):
    """El paso con los DEFECTOS reales de `settings` (sin `.env`)."""
    from types import SimpleNamespace

    from config.settings import PostgresSettings
    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    pg = PostgresSettings(
        _env_file=None, readonly_role=ESTANDAR, set_role=DUENO, total_role=TOTAL,
    )
    return ApplyGrantsStep(SimpleNamespace(postgres=pg), client=cliente)


def _llamada(cliente: _ClienteFalso, tipo: str, rol: str) -> tuple:
    encontradas = [c for c in cliente.llamadas if c[0] == tipo and c[1] == rol]
    assert len(encontradas) == 1, (tipo, rol, cliente.llamadas)
    return encontradas[0]


def test_f037_r21_el_estandar_recibe_tesoreria_y_se_le_veta_la_restringida() -> None:
    from etl_sigrid.domain.entities import StepStatus

    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    general = _llamada(cliente, "general", ESTANDAR)
    assert GENERAL in general[3] and RESTR_T not in general[3]
    assert general[4] == [RESTR_C, RESTR_T, "raw"]
    assert _llamada(cliente, "verifica", ESTANDAR)[2] == [RESTR_C, RESTR_T, "raw"], (
        "la postcondición pregunta al catálogo también por tesoreria_restringida"
    )
    assert resultado.metadata["verificacion"] == "ok"


def test_f037_r21_el_autorizado_recibe_la_restringida() -> None:
    cliente = _ClienteFalso()
    _paso(cliente).run()
    assert _llamada(cliente, "autorizado", AUTORIZADO) == (
        "autorizado", AUTORIZADO, DUENO, [RESTR_C, RESTR_T],
    )


def test_f037_r21_si_el_estandar_lee_la_restringida_failed_con_la_lista() -> None:
    from etl_sigrid.domain.entities import StepStatus

    cliente = _ClienteFalso(indebidas={ESTANDAR: [
        "tesoreria_restringida (USAGE)", "tesoreria_restringida.efectos (SELECT)",
    ]})
    resultado = _paso(cliente).run()
    assert resultado.status == StepStatus.FAILED
    mensaje = resultado.error_message or ""
    assert "tesoreria_restringida (USAGE)" in mensaje
    assert "tesoreria_restringida.efectos (SELECT)" in mensaje
    assert ESTANDAR in mensaje


def test_f037_r21_el_total_sin_grant_propio_lee_la_restringida_y_no_raw() -> None:
    from etl_sigrid.domain.entities import StepStatus

    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    assert not [c for c in cliente.llamadas if c[0] in ("general", "autorizado") and c[1] == TOTAL], (
        "el total no recibe GRANT propio: lee por pertenencia"
    )
    assert _llamada(cliente, "veto", TOTAL) == ("veto", TOTAL, DUENO, ["raw"]), (
        "al total solo se le veta raw: tesoreria_restringida la LEE"
    )
    assert _llamada(cliente, "verifica", TOTAL)[2] == ["raw"]
    usage = _llamada(cliente, "usage", TOTAL)[2]
    assert GENERAL in usage and RESTR_T in usage, (
        "se comprueba que el total llega a las dos carteras (R10 de F-136)"
    )
    assert resultado.metadata["verificacion_total"] == "ok"
    assert resultado.metadata["acceso_total"] == "ok"


def test_f037_r21_el_total_que_lee_raw_sigue_siendo_failed() -> None:
    from etl_sigrid.domain.entities import StepStatus

    resultado = _paso(_ClienteFalso(indebidas={TOTAL: ["raw.pag (SELECT)"]})).run()
    assert resultado.status == StepStatus.FAILED
    assert "raw.pag (SELECT)" in (resultado.error_message or "")


def test_f037_r21_las_sentencias_reales_vetan_y_conceden_la_restringida() -> None:
    """Las sentencias que salen de las listas: REVOKE al estándar, GRANT al autorizado."""
    from config.settings import PostgresSettings
    from etl_sigrid.infrastructure.postgres import grants

    pg = PostgresSettings(_env_file=None)
    veto = grants.build_veto_statements(ESTANDAR, DUENO, pg.vetoed_schema_list)
    assert f'REVOKE ALL PRIVILEGES ON SCHEMA "{RESTR_T}" FROM "{ESTANDAR}"' in veto
    assert f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "{RESTR_T}" FROM "{ESTANDAR}"' in veto
    concesion = grants.build_restricted_grant_statements(AUTORIZADO, DUENO, pg.restricted_schema_list)
    assert f'GRANT USAGE ON SCHEMA "{RESTR_T}" TO "{AUTORIZADO}"' in concesion
    assert f'GRANT SELECT ON ALL TABLES IN SCHEMA "{RESTR_T}" TO "{AUTORIZADO}"' in concesion
    assert (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "{RESTR_T}" '
        f'GRANT SELECT ON TABLES TO "{AUTORIZADO}"'
    ) in concesion
    assert grants.esquemas_en_conflicto(pg.consumption_schema_list, pg.vetoed_schema_list) == []


# ===========================================================================
# R22 · infra/sql/02_roles.sql casa con settings (T8)
# ===========================================================================

def _roles_sql() -> str:
    return (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")


def test_f037_r22_crea_los_dos_esquemas_como_dueno() -> None:
    tramo = _roles_sql().split("SET ROLE sigrid_dm_etl;", 1)[1].split("RESET ROLE;", 1)[0]
    assert "CREATE SCHEMA IF NOT EXISTS tesoreria;" in tramo
    assert "CREATE SCHEMA IF NOT EXISTS tesoreria_restringida;" in tramo


def test_f037_r22_tesoreria_en_el_bucle_de_consumo() -> None:
    import re

    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    bucle = re.search(r"FOREACH esquema IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert bucle
    concedidos = re.findall(r"'(\w+)'", bucle.group(1))
    assert concedidos == DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    assert GENERAL in concedidos and RESTR_T not in concedidos


def test_f037_r22_la_restringida_vetada_al_estandar_con_los_dos_concedentes() -> None:
    import re

    from config.settings import DEFAULT_VETOED_SCHEMAS

    listas = re.findall(r"FOREACH vetado IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        esquemas = re.findall(r"'(\w+)'", lista)
        assert esquemas == DEFAULT_VETOED_SCHEMAS.split(",")
        assert RESTR_T in esquemas


def test_f037_r22_la_restringida_no_se_veta_al_total() -> None:
    import re

    from config.settings import DEFAULT_TOTAL_VETOED_SCHEMAS

    listas = re.findall(r"FOREACH vetado_total IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == DEFAULT_TOTAL_VETOED_SCHEMAS.split(",")


def test_f037_r22_el_autorizado_recibe_la_restringida() -> None:
    sql = _roles_sql()
    tramo = sql.split("-- 5 ter.")[1].split("-- 5 quater.")[0]
    for sentencia in (
        f"GRANT USAGE ON SCHEMA {RESTR_T} TO sigrid_dm_restringido_ro;",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {RESTR_T} TO sigrid_dm_restringido_ro;",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA {RESTR_T} "
        "GRANT SELECT ON TABLES TO sigrid_dm_restringido_ro;",
    ):
        assert sentencia in tramo, f"falta: {sentencia}"
    assert tramo.index(f"GRANT USAGE ON SCHEMA {RESTR_T}") > tramo.index("SET ROLE sigrid_dm_etl;")


def test_f037_r22_las_comprobaciones_finales_miran_la_restringida() -> None:
    sql = _roles_sql()
    final = sql.split("\nCOMMIT;", 1)[1]
    assert (
        "WHERE grantee = 'mcp_sigrid_dm_ro'\n"
        "  AND table_schema IN ('contabilidad_restringida', 'tesoreria_restringida', 'raw')"
    ) in final
    assert "WHERE nspname IN ('contabilidad_restringida', 'tesoreria_restringida', 'raw')" in final
    assert "'tesoreria', 'tesoreria_restringida'" in final, "los esquemas del punto 6"
    assert (
        "has_schema_privilege('mcp_sigrid_dm_total', 'tesoreria_restringida', 'USAGE')" in final
    )
