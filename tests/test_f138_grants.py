# tests/test_f138_grants.py
"""
F-138 · Los permisos de `compras_restringida` (R22-R23, D9).

Patrón «módulo + `_restringida`» de F-135 y F-037: el rol ESTÁNDAR
(`mcp_sigrid_dm_ro`, MCP y Power BI) nunca lee `compras_restringida`, donde
viven las alarmas de recursos (33) y partes (35); el AUTORIZADO
(`sigrid_dm_autorizado_ro`) la lee; el TOTAL (`mcp_sigrid_dm_total`) la lee
por pertenencia, sin GRANT propio. Todo vive en `config/settings.py` (listas),
en `apply_grants` (cada noche) y en `infra/sql/02_roles.sql` (provisión).

Ningún test abre red ni BBDD: el cliente se simula.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.test_f037_grants import (
    AUTORIZADO,
    DUENO,
    ESTANDAR,
    TOTAL,
    _ClienteFalso,
    _llamada,
    _paso,
)

RAIZ = Path(__file__).resolve().parents[1]
RESTR = "compras_restringida"


# ===========================================================================
# R22 · settings, .env.example y ESQUEMAS_DEL_DATAMART
# ===========================================================================


def test_f138_r22_vetada_al_estandar_y_del_autorizado() -> None:
    from config.settings import (
        DEFAULT_CONSUMPTION_SCHEMAS,
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_TOTAL_VETOED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_VETOED_SCHEMAS == (
        "contabilidad_restringida,tesoreria_restringida,compras_restringida,raw"
    )
    assert DEFAULT_RESTRICTED_SCHEMAS == (
        "contabilidad_restringida,tesoreria_restringida,compras_restringida"
    )
    assert RESTR not in DEFAULT_CONSUMPTION_SCHEMAS.split(","), "nunca en el consumo"
    assert DEFAULT_TOTAL_VETOED_SCHEMAS == "raw", "el total SÍ lee compras_restringida"
    pg = PostgresSettings(_env_file=None)
    assert RESTR in pg.vetoed_schema_list
    assert RESTR in pg.restricted_schema_list
    assert RESTR not in pg.total_vetoed_schema_list
    assert "compras" in pg.consumption_schema_list, "la general sigue en el consumo"


def test_f138_r22_env_example_igual_que_los_defectos() -> None:
    from config.settings import DEFAULT_RESTRICTED_SCHEMAS, DEFAULT_VETOED_SCHEMAS

    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    lineas = dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )
    assert lineas["PG_VETOED_SCHEMAS"] == DEFAULT_VETOED_SCHEMAS
    assert lineas["PG_RESTRICTED_SCHEMAS"] == DEFAULT_RESTRICTED_SCHEMAS
    assert "F-138" in texto.split("PG_VETOED_SCHEMAS=")[0].split("PG_EXCLUDED_TABLES=")[1], (
        "el comentario de PG_VETOED_SCHEMAS explica F-138"
    )


def test_f138_r22_los_comentarios_de_settings_lo_explican() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    vetados = texto.split("DEFAULT_VETOED_SCHEMAS =")[0].split("DEFAULT_CONSUMPTION_SCHEMAS = (")[1]
    assert RESTR in vetados and "F-138" in vetados
    restringidos = texto.split("DEFAULT_RESTRICTED_SCHEMAS =")[0].split("DEFAULT_VETOED_SCHEMAS =")[1]
    assert RESTR in restringidos


def test_f138_r22_es_un_esquema_del_datamart() -> None:
    from etl_sigrid.domain import diccionario

    assert RESTR in diccionario.ESQUEMAS_DEL_DATAMART
    assert len(diccionario.ESQUEMAS_DEL_DATAMART) == 16
    assert list(diccionario.ESQUEMAS_DEL_DATAMART) == sorted(diccionario.ESQUEMAS_DEL_DATAMART)
    texto = (RAIZ / "etl_sigrid" / "domain" / "diccionario.py").read_text(encoding="utf-8")
    assert "F-138" in texto.split("ESQUEMAS_DEL_DATAMART = (")[0]


# ===========================================================================
# R22 · apply_grants con las listas nuevas, cliente simulado
# ===========================================================================


def test_f138_r22_al_estandar_se_le_veta_y_se_comprueba() -> None:
    from etl_sigrid.domain.entities import StepStatus

    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    general = _llamada(cliente, "general", ESTANDAR)
    assert RESTR not in general[3], "el estándar no recibe GRANT de compras_restringida"
    assert RESTR in general[4], "y se le veta"
    assert RESTR in _llamada(cliente, "verifica", ESTANDAR)[2], (
        "la postcondición pregunta al catálogo también por compras_restringida"
    )


def test_f138_r22_el_autorizado_la_recibe() -> None:
    cliente = _ClienteFalso()
    _paso(cliente).run()
    assert RESTR in _llamada(cliente, "autorizado", AUTORIZADO)[3]
    assert _llamada(cliente, "autorizado", AUTORIZADO)[2] == DUENO


def test_f138_r22_el_total_la_lee_por_pertenencia_y_se_comprueba() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert _llamada(cliente, "veto", TOTAL)[3] == ["raw"]
    assert RESTR in _llamada(cliente, "usage", TOTAL)[2]
    assert resultado.metadata["acceso_total"] == "ok"


def test_f138_r22_si_el_estandar_la_lee_el_paso_falla() -> None:
    from etl_sigrid.domain.entities import StepStatus

    resultado = _paso(_ClienteFalso(indebidas={ESTANDAR: [
        "compras_restringida.documento_alarmas (SELECT)",
    ]})).run()
    assert resultado.status == StepStatus.FAILED
    assert "compras_restringida.documento_alarmas (SELECT)" in (resultado.error_message or "")


# ===========================================================================
# R23 · infra/sql/02_roles.sql casa con settings
# ===========================================================================


def _roles_sql() -> str:
    return (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")


def test_f138_r23_crea_el_esquema_como_dueno() -> None:
    tramo = _roles_sql().split("SET ROLE sigrid_dm_etl;", 1)[1].split("RESET ROLE;", 1)[0]
    assert f"CREATE SCHEMA IF NOT EXISTS {RESTR};" in tramo


def test_f138_r23_vetada_al_estandar_con_los_dos_concedentes() -> None:
    from config.settings import DEFAULT_VETOED_SCHEMAS

    listas = re.findall(r"FOREACH vetado IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == DEFAULT_VETOED_SCHEMAS.split(",")


def test_f138_r23_no_se_veta_al_total() -> None:
    listas = re.findall(r"FOREACH vetado_total IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        assert RESTR not in lista


def test_f138_r23_el_autorizado_la_recibe() -> None:
    tramo = _roles_sql().split("-- 5 ter.")[1].split("-- 5 quater.")[0]
    for sentencia in (
        f"GRANT USAGE ON SCHEMA {RESTR} TO sigrid_dm_autorizado_ro;",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {RESTR} TO sigrid_dm_autorizado_ro;",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA {RESTR} "
        "GRANT SELECT ON TABLES TO sigrid_dm_autorizado_ro;",
    ):
        assert sentencia in tramo, f"falta: {sentencia}"
    assert tramo.index(f"GRANT USAGE ON SCHEMA {RESTR}") > tramo.index("SET ROLE sigrid_dm_etl;")


def test_f138_r23_las_comprobaciones_finales_la_miran() -> None:
    final = _roles_sql().split("\nCOMMIT;", 1)[1]
    vetados = "('contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw')"
    assert f"WHERE grantee = 'mcp_sigrid_dm_ro'\n  AND table_schema IN {vetados}" in final
    assert f"WHERE nspname IN {vetados}" in final
    assert "'tesoreria', 'tesoreria_restringida', 'compras_restringida')" in final, (
        "el propietario de los esquemas (punto 6)"
    )
    assert f"has_schema_privilege('mcp_sigrid_dm_total', '{RESTR}', 'USAGE')" in final
