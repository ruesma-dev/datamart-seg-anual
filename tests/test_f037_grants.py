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

import pytest

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
