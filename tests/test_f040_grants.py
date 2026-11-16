# tests/test_f040_grants.py
"""F-040 · Permisos de `ventas` y `ventas_restringida` (R27-R29), sin red ni BBDD.

Patrón «módulo + `_restringida`» de F-135, F-037, F-138 y F-156: `ventas` (sin
lo personal del cliente) es consumo y la leen el estándar, Power BI y el total;
`ventas_restringida` (NIF de la persona física, direcciones, teléfonos, correos
y la cabecera de la factura, D2/D6 del humano) está VETADA al estándar, es del
autorizado y el total la lee por pertenencia. El perfil restringido y el de
postventa no leen ninguna de las dos: sus listas son explícitas y
`apply_grants` les veta cada noche lo que no esté en ellas.
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
GENERAL = "ventas"
RESTR = "ventas_restringida"


def _lineas_env_example() -> dict[str, str]:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    return dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )


# ===========================================================================
# R27 · `ventas` es consumo, y de nadie más
# ===========================================================================


def test_f040_r27_ventas_en_el_consumo_y_en_ningun_perfil() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS, PostgresSettings

    assert GENERAL in DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    pg = PostgresSettings(_env_file=None)
    assert GENERAL in pg.consumption_schema_list
    for lista in (pg.vetoed_schema_list, pg.restricted_schema_list, pg.total_vetoed_schema_list,
                  pg.perfil_restringido_schema_list, pg.perfil_postventa_schema_list):
        assert GENERAL not in lista


def test_f040_r27_la_lista_de_consumo_completa() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    assert DEFAULT_CONSUMPTION_SCHEMAS == (
        "mart,cierre,compras,maestro,retenciones,personal,contabilidad,tesoreria,"
        "descompuestos,postventa,ventas,stg,aux,_meta"
    )


def test_f040_r27_env_example_igual_que_los_defectos() -> None:
    from config.settings import (
        DEFAULT_CONSUMPTION_SCHEMAS,
        DEFAULT_PERFIL_POSTVENTA_SCHEMAS,
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
    )

    lineas = _lineas_env_example()
    assert lineas["PG_CONSUMPTION_SCHEMAS"] == DEFAULT_CONSUMPTION_SCHEMAS
    assert lineas["PG_PERFIL_RESTRINGIDO_SCHEMAS"] == DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS
    assert lineas["PG_PERFIL_POSTVENTA_SCHEMAS"] == DEFAULT_PERFIL_POSTVENTA_SCHEMAS


def test_f040_r27_r28_los_dos_son_esquemas_del_datamart() -> None:
    from etl_sigrid.domain import diccionario

    assert GENERAL in diccionario.ESQUEMAS_DEL_DATAMART
    assert RESTR in diccionario.ESQUEMAS_DEL_DATAMART
    assert len(diccionario.ESQUEMAS_DEL_DATAMART) == 20
    assert list(diccionario.ESQUEMAS_DEL_DATAMART) == sorted(diccionario.ESQUEMAS_DEL_DATAMART)
    texto = (RAIZ / "etl_sigrid" / "domain" / "diccionario.py").read_text(encoding="utf-8")
    assert "F-040" in texto.split("ESQUEMAS_DEL_DATAMART = (")[0]


# ===========================================================================
# R28 · `ventas_restringida` vetada al estándar, del autorizado y del total
# ===========================================================================


def test_f040_r28_vetada_y_del_autorizado_pero_no_del_total() -> None:
    from config.settings import (
        DEFAULT_RESTRICTED_SCHEMAS,
        DEFAULT_TOTAL_VETOED_SCHEMAS,
        DEFAULT_VETOED_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_VETOED_SCHEMAS == (
        "contabilidad_restringida,tesoreria_restringida,compras_restringida,"
        "postventa_restringida,ventas_restringida,raw"
    )
    assert DEFAULT_RESTRICTED_SCHEMAS == (
        "contabilidad_restringida,tesoreria_restringida,compras_restringida,"
        "postventa_restringida,ventas_restringida"
    )
    assert DEFAULT_TOTAL_VETOED_SCHEMAS == "raw", "el total SÍ lee ventas_restringida"
    pg = PostgresSettings(_env_file=None)
    assert RESTR in pg.vetoed_schema_list and RESTR in pg.restricted_schema_list
    for lista in (pg.consumption_schema_list, pg.total_vetoed_schema_list,
                  pg.perfil_restringido_schema_list, pg.perfil_postventa_schema_list):
        assert RESTR not in lista


def test_f040_r28_env_example_igual_que_los_defectos() -> None:
    from config.settings import DEFAULT_RESTRICTED_SCHEMAS, DEFAULT_VETOED_SCHEMAS

    lineas = _lineas_env_example()
    assert lineas["PG_VETOED_SCHEMAS"] == DEFAULT_VETOED_SCHEMAS
    assert lineas["PG_RESTRICTED_SCHEMAS"] == DEFAULT_RESTRICTED_SCHEMAS
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert "F-040" in texto.split("PG_VETOED_SCHEMAS=")[0].split("PG_EXCLUDED_TABLES=")[1], (
        "el comentario de PG_VETOED_SCHEMAS explica F-040"
    )


def test_f040_r28_los_comentarios_de_settings_lo_explican() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    consumo = texto.split("DEFAULT_CONSUMPTION_SCHEMAS = (")[0].rsplit("\n\n", 1)[-1]
    assert "F-040" in consumo and GENERAL in consumo
    vetados = texto.split("DEFAULT_VETOED_SCHEMAS =")[0].split("DEFAULT_CONSUMPTION_SCHEMAS = (")[1]
    assert RESTR in vetados and "F-040" in vetados
    restringidos = texto.split("DEFAULT_RESTRICTED_SCHEMAS =")[0].split("DEFAULT_VETOED_SCHEMAS =")[1]
    assert RESTR in restringidos and "F-040" in restringidos


def test_f040_r28_sin_conflicto_entre_consumo_y_vetados() -> None:
    from config.settings import PostgresSettings
    from etl_sigrid.infrastructure.postgres import grants

    pg = PostgresSettings(_env_file=None)
    assert grants.esquemas_en_conflicto(pg.consumption_schema_list, pg.vetoed_schema_list) == []


def test_f040_r28_las_sentencias_reales_vetan_y_conceden_sin_tocar_grants() -> None:
    """`grants.py` no cambia: las sentencias salen de las listas de `settings`."""
    from config.settings import PostgresSettings
    from etl_sigrid.infrastructure.postgres import grants

    pg = PostgresSettings(_env_file=None)
    veto = grants.build_veto_statements(ESTANDAR, DUENO, pg.vetoed_schema_list)
    assert f'REVOKE ALL PRIVILEGES ON SCHEMA "{RESTR}" FROM "{ESTANDAR}"' in veto
    assert f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "{RESTR}" FROM "{ESTANDAR}"' in veto
    assert not [s for s in veto if f'"{GENERAL}"' in s], "a `ventas` no se le veta nada"
    concesion = grants.build_restricted_grant_statements(AUTORIZADO, DUENO, pg.restricted_schema_list)
    assert f'GRANT USAGE ON SCHEMA "{RESTR}" TO "{AUTORIZADO}"' in concesion
    assert f'GRANT SELECT ON ALL TABLES IN SCHEMA "{RESTR}" TO "{AUTORIZADO}"' in concesion
    assert (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "{RESTR}" '
        f'GRANT SELECT ON TABLES TO "{AUTORIZADO}"'
    ) in concesion


def test_f040_r28_apply_grants_al_estandar_ventas_si_y_la_restringida_no() -> None:
    from etl_sigrid.domain.entities import StepStatus

    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    general = _llamada(cliente, "general", ESTANDAR)
    assert GENERAL in general[3] and RESTR not in general[3]
    assert RESTR in general[4], "se le veta"
    assert RESTR in _llamada(cliente, "verifica", ESTANDAR)[2], (
        "la postcondición pregunta al catálogo también por ventas_restringida"
    )
    assert RESTR in _llamada(cliente, "autorizado", AUTORIZADO)[3]


def test_f040_r28_el_total_la_lee_por_pertenencia_y_se_comprueba() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente).run()
    assert _llamada(cliente, "veto", TOTAL)[3] == ["raw"]
    usage = _llamada(cliente, "usage", TOTAL)[2]
    assert GENERAL in usage and RESTR in usage
    assert resultado.metadata["acceso_total"] == "ok"


def test_f040_r28_si_el_estandar_la_lee_el_paso_falla() -> None:
    from etl_sigrid.domain.entities import StepStatus

    resultado = _paso(_ClienteFalso(indebidas={ESTANDAR: [
        "ventas_restringida.clientes_contacto (SELECT)",
    ]})).run()
    assert resultado.status == StepStatus.FAILED
    assert "ventas_restringida.clientes_contacto (SELECT)" in (resultado.error_message or "")


# ===========================================================================
# R29 · infra/sql/02_roles.sql casa con settings
# ===========================================================================


def _roles_sql() -> str:
    return (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")


def test_f040_r29_crea_los_dos_esquemas_como_dueno() -> None:
    tramo = _roles_sql().split("SET ROLE sigrid_dm_etl;", 1)[1].split("RESET ROLE;", 1)[0]
    assert f"CREATE SCHEMA IF NOT EXISTS {GENERAL};" in tramo
    assert f"CREATE SCHEMA IF NOT EXISTS {RESTR};" in tramo
    assert "F-040" in tramo


def test_f040_r29_ventas_en_el_bucle_de_consumo() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    bucle = re.search(r"FOREACH esquema IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert bucle
    concedidos = re.findall(r"'(\w+)'", bucle.group(1))
    assert concedidos == DEFAULT_CONSUMPTION_SCHEMAS.split(",")
    assert GENERAL in concedidos and RESTR not in concedidos


def test_f040_r29_vetada_al_estandar_con_los_dos_concedentes() -> None:
    from config.settings import DEFAULT_VETOED_SCHEMAS

    listas = re.findall(r"FOREACH vetado IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == DEFAULT_VETOED_SCHEMAS.split(",")


def test_f040_r29_no_se_veta_al_total() -> None:
    listas = re.findall(r"FOREACH vetado_total IN ARRAY ARRAY\[(.*?)\]", _roles_sql(), re.DOTALL)
    assert len(listas) == 2
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == ["raw"]


def test_f040_r29_el_autorizado_la_recibe() -> None:
    tramo = _roles_sql().split("-- 5 ter.")[1].split("-- 5 quater.")[0]
    for sentencia in (
        f"GRANT USAGE ON SCHEMA {RESTR} TO sigrid_dm_autorizado_ro;",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {RESTR} TO sigrid_dm_autorizado_ro;",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA {RESTR} "
        "GRANT SELECT ON TABLES TO sigrid_dm_autorizado_ro;",
    ):
        assert sentencia in tramo, f"falta: {sentencia}"
    assert tramo.index(f"GRANT USAGE ON SCHEMA {RESTR}") > tramo.index("SET ROLE sigrid_dm_etl;")
    assert "F-040: y lo personal del cliente, igual" in tramo
    assert RESTR in tramo.split("DO $$", 1)[0], "el comentario del 5 ter la nombra"


def test_f040_r29_las_comprobaciones_finales_la_miran() -> None:
    final = _roles_sql().split("\nCOMMIT;", 1)[1]
    vetados = ("('contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', "
               "'postventa_restringida', 'ventas_restringida', 'raw')")
    assert f"WHERE grantee = 'mcp_sigrid_dm_ro'\n  AND table_schema IN {vetados}" in final
    assert f"WHERE nspname IN {vetados}" in final
    assert "seis filas" in final
    propietarios = final.split("FROM pg_namespace", 1)[1].split("ORDER BY nspname;", 1)[0]
    assert f"'{GENERAL}'" in propietarios and f"'{RESTR}'" in propietarios
    assert "veinte esquemas" in final
    assert f"has_schema_privilege('mcp_sigrid_dm_total', '{RESTR}', 'USAGE')" in final
    for login in ("mcp_sigrid_dm_restringido", "mcp_sigrid_dm_postventa"):
        for esquema in (GENERAL, RESTR):
            assert f"has_schema_privilege('{login}', '{esquema}', 'USAGE')" in final, (login, esquema)


def test_f040_r29_los_perfiles_vetan_lo_que_no_esta_en_su_lista() -> None:
    """Los bucles del restringido y del postventa no cambian: `ventas` cae en el veto."""
    sql = _roles_sql()
    for tramo in re.findall(r"WHERE nspname <> ALL \(ARRAY\[(.*?)\]\)", sql, re.DOTALL):
        assert f"'{GENERAL}'" not in tramo and f"'{RESTR}'" not in tramo


def test_f040_r29_la_cabecera_cuenta_los_esquemas() -> None:
    cuatro = _roles_sql().split("-- 4. Esquemas del datamart.", 1)[1].split("SET ROLE", 1)[0]
    assert "veinte" in cuatro


def test_f040_r29_sin_contrasenas_ni_variables_nuevas() -> None:
    sql = _roles_sql()
    assert len(re.findall(r"\\getenv ", sql)) == 5, "F-040 no añade login ni contraseña"
