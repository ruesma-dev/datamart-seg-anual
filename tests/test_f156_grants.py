# tests/test_f156_grants.py
"""F-156 · Permisos de postventa y el perfil POSTVENTA (R28-R31), sin red ni BBDD.

`postventa` es consumo (estándar, Power BI, total) y del perfil restringido;
`postventa_restringida` (los datos personales, «d1 ok» del humano el
2026-11-03) está vetada al general y es del autorizado, y la lee además el
perfil POSTVENTA: el restringido + `postventa_restringida`, ni más ni menos.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]

ESTANDAR = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_autorizado_ro"
TOTAL = "mcp_sigrid_dm_total"
GRUPO_R = "sigrid_dm_perfil_restringido_ro"
LOGIN_R = "mcp_sigrid_dm_restringido"
GRUPO_PV = "sigrid_dm_perfil_postventa_ro"
LOGIN_PV = "mcp_sigrid_dm_postventa"
DUENO = "sigrid_dm_etl"

ESQUEMAS_R = ["mart", "cierre", "compras", "maestro", "retenciones", "descompuestos", "postventa",
              "stg", "aux", "_meta"]
ESQUEMAS_PV = [*ESQUEMAS_R, "postventa_restringida"]
CONSUMO = [*ESQUEMAS_R, "contabilidad", "tesoreria", "personal", "ventas"]  # + F-040
RESTRINGIDOS = ["contabilidad_restringida", "tesoreria_restringida", "compras_restringida",
                "postventa_restringida", "ventas_restringida"]  # + F-040
VETADOS = [*RESTRINGIDOS, "raw"]
EXCEPCIONES = ("compras.vencimientos", "compras.v_facturas_pago", "compras.v_control_forma_pago")


# ===========================================================================
# R28 · las listas de esquemas
# ===========================================================================


def test_f156_r28_postventa_es_consumo_y_del_restringido() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(_env_file=None)
    assert "postventa" in pg.consumption_schema_list
    assert "postventa" in pg.perfil_restringido_schema_list
    assert "postventa" not in pg.vetoed_schema_list
    assert "postventa" not in pg.restricted_schema_list


def test_f156_r28_postventa_restringida_vetada_y_del_autorizado() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(_env_file=None)
    assert "postventa_restringida" in pg.vetoed_schema_list
    assert "postventa_restringida" in pg.restricted_schema_list
    for otra in (pg.consumption_schema_list, pg.perfil_restringido_schema_list,
                 pg.total_vetoed_schema_list):
        assert "postventa_restringida" not in otra


def test_f156_r28_las_listas_completas() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(_env_file=None)
    assert pg.perfil_restringido_schema_list == ESQUEMAS_R
    assert pg.restricted_schema_list == RESTRINGIDOS
    assert pg.vetoed_schema_list == VETADOS
    assert set(pg.consumption_schema_list) == set(CONSUMO)


# ===========================================================================
# R29 · el perfil postventa en settings
# ===========================================================================


def test_f156_r29_defectos_del_perfil_postventa() -> None:
    from config.settings import (
        DEFAULT_PERFIL_POSTVENTA_GROUP,
        DEFAULT_PERFIL_POSTVENTA_LOGIN,
        DEFAULT_PERFIL_POSTVENTA_SCHEMAS,
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
        PostgresSettings,
    )

    assert DEFAULT_PERFIL_POSTVENTA_GROUP == GRUPO_PV
    assert DEFAULT_PERFIL_POSTVENTA_LOGIN == LOGIN_PV
    assert DEFAULT_PERFIL_POSTVENTA_SCHEMAS == ",".join(ESQUEMAS_PV)
    assert DEFAULT_PERFIL_POSTVENTA_SCHEMAS == DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS + ",postventa_restringida"
    pg = PostgresSettings(_env_file=None)
    assert (pg.perfil_postventa_group, pg.perfil_postventa_login) == (GRUPO_PV, LOGIN_PV)
    assert pg.perfil_postventa_schema_list == ESQUEMAS_PV


def test_f156_r29_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import PostgresSettings

    monkeypatch.setenv("PG_PERFIL_POSTVENTA_GROUP", "g_pv")
    monkeypatch.setenv("PG_PERFIL_POSTVENTA_LOGIN", "l_pv")
    monkeypatch.setenv("PG_PERFIL_POSTVENTA_SCHEMAS", " mart ,, _meta ,")
    pg = PostgresSettings(_env_file=None)
    assert (pg.perfil_postventa_group, pg.perfil_postventa_login) == ("g_pv", "l_pv")
    assert pg.perfil_postventa_schema_list == ["mart", "_meta"]


def test_f156_r29_perfil_postventa_en_conflicto_los_defectos_no_chocan() -> None:
    from etl_sigrid.infrastructure.postgres.grants import perfil_postventa_en_conflicto

    assert perfil_postventa_en_conflicto(
        ESQUEMAS_PV, restringido=ESQUEMAS_R, vetados=VETADOS, restringidos=RESTRINGIDOS,
    ) == []


@pytest.mark.parametrize(
    ("esquemas", "cambios", "esperado"),
    [
        ([*ESQUEMAS_PV, "tesoreria"], {}, ["tesoreria"]),           # uno de más
        ([*ESQUEMAS_R], {}, ["postventa_restringida"]),             # le falta lo suyo
        ([e for e in ESQUEMAS_PV if e != "compras"], {}, ["compras"]),  # le falta uno del restringido
        ([*ESQUEMAS_PV, "contabilidad_restringida"], {}, ["contabilidad_restringida"]),
        (ESQUEMAS_PV, {"vetados": [e for e in VETADOS if e != "postventa_restringida"]},
         ["postventa_restringida"]),
        (ESQUEMAS_PV, {"restringidos": [e for e in RESTRINGIDOS if e != "postventa_restringida"]},
         ["postventa_restringida"]),
    ],
)
def test_f156_r29_perfil_postventa_en_conflicto(esquemas, cambios, esperado) -> None:
    from etl_sigrid.infrastructure.postgres.grants import perfil_postventa_en_conflicto

    argumentos = {"restringido": ESQUEMAS_R, "vetados": VETADOS, "restringidos": RESTRINGIDOS}
    argumentos.update(cambios)
    assert perfil_postventa_en_conflicto(esquemas, **argumentos) == esperado


def test_f156_r29_propios_del_perfil_son_los_restringidos_de_postventa() -> None:
    from etl_sigrid.infrastructure.postgres.grants import ESQUEMAS_PROPIOS_POSTVENTA

    assert ESQUEMAS_PROPIOS_POSTVENTA == ("postventa_restringida",)


# ===========================================================================
# R29-R30 · el bloque del perfil postventa en apply_grants (con dobles)
# ===========================================================================

CATALOGO = [*CONSUMO, *VETADOS, "public", "pg_catalog", "information_schema", "pg_toast"]
AJENOS_PV = sorted({"contabilidad", "tesoreria", "personal", "raw", "contabilidad_restringida",
                    "tesoreria_restringida", "compras_restringida",
                    "ventas", "ventas_restringida"})  # + F-040
AJENOS_R = sorted([*AJENOS_PV, "postventa_restringida"])
FILAS_HOY = [(v, "tesoreria.efectos") for v in EXCEPCIONES]


class _ClienteFalso:
    def __init__(
        self,
        existen: tuple[str, ...] = (ESTANDAR, AUTORIZADO, TOTAL, GRUPO_R, LOGIN_R, GRUPO_PV,
                                    LOGIN_PV),
        indebidas: dict[str, list[str]] | None = None,
        pertenencias: dict[str, list[str]] | None = None,
        filas: list[tuple[str, str]] | None = None,
    ) -> None:
        self.existen = existen
        self.indebidas = indebidas or {}
        self.pert = ({LOGIN_R: [GRUPO_R], LOGIN_PV: [GRUPO_PV]}
                     if pertenencias is None else pertenencias)
        self.filas = FILAS_HOY if filas is None else filas
        self.llamadas: list[tuple] = []

    def role_exists(self, role):
        self.llamadas.append(("role_exists", role))
        return role in self.existen

    def list_schemas(self):
        return list(CATALOGO)

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):
        return ["G"]

    def apply_restricted_grants(self, role, owner_role, schemas):
        self.llamadas.append(("autorizado", role, list(schemas)))
        return ["A"]

    def apply_veto(self, role, owner_role, schemas):
        self.llamadas.append(("veto", role, list(schemas)))
        return ["V"]

    def lecturas_indebidas(self, role, schemas, tables):
        self.llamadas.append(("verifica", role, list(schemas)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):
        return []

    def vistas_que_filtran(self, schemas, foreign_schemas, tables):
        self.llamadas.append(("filtran", list(schemas), list(foreign_schemas)))
        return list(self.filas)

    def objetos_vigilados(self, schemas, pattern):
        return []

    def pertenencias(self, role):
        return list(self.pert.get(role, []))

    def apply_perfil_restringido(self, role, owner_role, schemas, revoked):
        self.llamadas.append(("perfil", role, list(schemas), list(revoked)))
        return ["P"]


def _settings(**pg: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "readonly_role": ESTANDAR,
        "set_role": DUENO,
        "consumption_schema_list": list(CONSUMO),
        "excluded_table_list": [],
        "vetoed_schema_list": list(VETADOS),
        "restricted_role": AUTORIZADO,
        "restricted_schema_list": list(RESTRINGIDOS),
        "total_role": TOTAL,
        "total_vetoed_schema_list": ["raw"],
        "perfil_restringido_group": GRUPO_R,
        "perfil_restringido_login": LOGIN_R,
        "perfil_restringido_schema_list": list(ESQUEMAS_R),
        "perfil_restringido_excluded_table_list": [],
        "perfil_postventa_group": GRUPO_PV,
        "perfil_postventa_login": LOGIN_PV,
        "perfil_postventa_schema_list": list(ESQUEMAS_PV),
    }
    base.update(pg)
    return SimpleNamespace(postgres=SimpleNamespace(**base))


def _paso(cliente: _ClienteFalso, **pg: object):
    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    return ApplyGrantsStep(_settings(**pg), client=cliente).run()


def _para_en_seco(cliente: _ClienteFalso, resultado) -> str:
    assert resultado.status.name == "FAILED"
    assert cliente.llamadas == [], "ni una sentencia, ni una pregunta al servidor"
    mensaje = resultado.error_message or ""
    assert "no se ha ejecutado nada" in mensaje and "F-156" in mensaje
    return mensaje


def test_f156_r29_lista_que_no_es_la_del_restringido_mas_lo_suyo_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(
        cliente, perfil_postventa_schema_list=[*ESQUEMAS_PV, "tesoreria"]))
    assert "PG_PERFIL_POSTVENTA_SCHEMAS" in mensaje and "tesoreria" in mensaje


def test_f156_r29_sin_lo_suyo_tambien_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(cliente, perfil_postventa_schema_list=list(ESQUEMAS_R)))
    assert "postventa_restringida" in mensaje


@pytest.mark.parametrize("otro", [ESTANDAR, AUTORIZADO, TOTAL, DUENO, GRUPO_R, LOGIN_R])
@pytest.mark.parametrize("variable", ["perfil_postventa_group", "perfil_postventa_login"])
def test_f156_r29_grupo_o_login_igual_a_otro_rol_para_en_seco(variable: str, otro: str) -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(cliente, **{variable: otro}))
    assert f"PG_{variable.upper()}" in mensaje and otro in mensaje


def test_f156_r29_login_igual_al_grupo_para_en_seco() -> None:
    cliente = _ClienteFalso()
    _para_en_seco(cliente, _paso(cliente, perfil_postventa_login=GRUPO_PV))


def test_f156_r30_concede_lo_suyo_y_veta_lo_ajeno_del_catalogo() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", resultado.error_message
    perfiles = [c for c in cliente.llamadas if c[0] == "perfil"]
    assert [p[1] for p in perfiles] == [GRUPO_R, GRUPO_PV], "el postventa va DETRÁS"
    assert perfiles[1][2] == ESQUEMAS_PV
    vetos = {c[1]: c[2] for c in cliente.llamadas if c[0] == "veto"}
    assert vetos[GRUPO_PV] == AJENOS_PV
    assert vetos[GRUPO_R] == AJENOS_R
    verificados = {c[1] for c in cliente.llamadas if c[0] == "verifica"}
    assert {GRUPO_PV, LOGIN_PV} <= verificados
    filtran = [c for c in cliente.llamadas if c[0] == "filtran"]
    assert filtran[-1][1] == ESQUEMAS_PV and "raw" not in filtran[-1][2]
    md = resultado.metadata
    assert md["rol_postventa"] == GRUPO_PV and md["login_postventa"] == LOGIN_PV
    for clave in ("verificacion_postventa", "pertenencias_postventa", "filtraciones_postventa",
                  "acceso_postventa"):
        assert md[clave] == "ok", clave
    assert md["verificacion_restringido"] == "ok"


def test_f156_r30_lecturas_indebidas_y_pertenencias_fallan_en_el_mismo_mensaje() -> None:
    cliente = _ClienteFalso(
        indebidas={ESTANDAR: ["raw"], LOGIN_PV: ["tesoreria"]},
        pertenencias={LOGIN_R: [GRUPO_R], LOGIN_PV: [GRUPO_PV, AUTORIZADO]},
    )
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    mensaje = resultado.error_message
    assert mensaje.index(ESTANDAR) < mensaje.index(LOGIN_PV), "el estándar primero"
    assert "perfil postventa" in mensaje and "tesoreria" in mensaje
    assert f"{LOGIN_PV} -> {AUTORIZADO}" in mensaje and "5 sexies" in mensaje
    assert resultado.metadata["verificacion_postventa"] == {LOGIN_PV: ["tesoreria"]}


def test_f156_r30_una_vista_que_filtra_se_revoca_y_falla() -> None:
    cliente = _ClienteFalso(filas=[*FILAS_HOY, ("postventa.v_x", "personal.partes")])
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    perfiles = [c for c in cliente.llamadas if c[0] == "perfil"]
    assert "postventa.v_x" in perfiles[1][3]
    assert "perfil postventa" in resultado.error_message


def test_f156_r30_grupo_inexistente_avisa_y_sigue() -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, AUTORIZADO, TOTAL, GRUPO_R, LOGIN_R))
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", resultado.error_message
    assert resultado.metadata["rol_postventa"] == f"{GRUPO_PV} (no existe)"
    assert resultado.metadata["verificacion_postventa"] == "no aplica"
    assert not [c for c in cliente.llamadas if c[0] == "perfil" and c[1] == GRUPO_PV]


def test_f156_r30_sin_grupo_no_se_mira() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_postventa_group="")
    assert resultado.status.name == "SUCCESS"
    assert resultado.metadata["rol_postventa"] == "(sin configurar)"
    assert ("role_exists", GRUPO_PV) not in cliente.llamadas


def test_f156_r30_configuracion_anterior_sin_perfil_postventa_no_se_mira() -> None:
    """Una configuración sin los campos (las de F-141) es «sin configurar»."""
    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    ajustes = _settings()
    for campo in ("perfil_postventa_group", "perfil_postventa_login",
                  "perfil_postventa_schema_list"):
        delattr(ajustes.postgres, campo)
    resultado = ApplyGrantsStep(ajustes, client=_ClienteFalso()).run()
    assert resultado.status.name == "SUCCESS"
    assert resultado.metadata["rol_postventa"] == "(sin configurar)"


# ===========================================================================
# R31 · `.env.example` y `02_roles.sql`
# ===========================================================================


def _env_example() -> dict[str, str]:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    return dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )


def test_f156_r31_env_example_casa_con_settings() -> None:
    from config import settings as s

    env = _env_example()
    assert env["PG_CONSUMPTION_SCHEMAS"] == s.DEFAULT_CONSUMPTION_SCHEMAS
    assert env["PG_VETOED_SCHEMAS"] == s.DEFAULT_VETOED_SCHEMAS
    assert env["PG_RESTRICTED_SCHEMAS"] == s.DEFAULT_RESTRICTED_SCHEMAS
    assert env["PG_PERFIL_RESTRINGIDO_SCHEMAS"] == s.DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS
    assert env["PG_PERFIL_POSTVENTA_GROUP"] == s.DEFAULT_PERFIL_POSTVENTA_GROUP
    assert env["PG_PERFIL_POSTVENTA_LOGIN"] == s.DEFAULT_PERFIL_POSTVENTA_LOGIN
    assert env["PG_PERFIL_POSTVENTA_SCHEMAS"] == s.DEFAULT_PERFIL_POSTVENTA_SCHEMAS
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    bloque = texto.split("PG_PERFIL_POSTVENTA_GROUP=")[0].rsplit("\n\n", 1)[-1]
    assert "F-156" in bloque, "las variables llevan su porqué delante"


def test_f156_r31_el_job_no_necesita_variables_nuevas() -> None:
    for ruta in (RAIZ / "infra" / "env" / "dev.json", RAIZ / "infra" / "80_create_job.ps1"):
        texto = ruta.read_text(encoding="utf-8-sig")
        assert "PG_PERFIL_POSTVENTA" not in texto and "POSTVENTA_PWD" not in texto, ruta.name


def _roles() -> str:
    return (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")


def test_f156_r31_roles_crea_grupo_y_login_con_su_variable() -> None:
    sql = _roles()
    assert r"\getenv postventa_pwd POSTVENTA_PWD" in sql
    assert re.search(r"CREATE ROLE mcp_sigrid_dm_postventa\s+LOGIN", sql)
    assert re.search(r"CREATE ROLE sigrid_dm_perfil_postventa_ro\s+NOLOGIN", sql)
    assert re.search(
        r"GRANT sigrid_dm_perfil_postventa_ro TO mcp_sigrid_dm_postventa\s+"
        r"WITH INHERIT TRUE, SET FALSE", sql)
    assert "5 sexies" in sql
    assert "GRANT CONNECT ON DATABASE sigrid_dm TO sigrid_dm_perfil_postventa_ro;" in sql
    assert "TO mcp_sigrid_dm_postventa;" not in sql, "el login no tiene GRANT propio: hereda"


def test_f156_r31_roles_postventa_restringida_vetada_y_del_autorizado() -> None:
    sql = _roles()
    assert "CREATE SCHEMA IF NOT EXISTS postventa_restringida" in sql
    arrays = re.findall(r"ARRAY\[([^\]]*)\]", sql)
    vetados = [a for a in arrays if "'tesoreria_restringida'" in a and "'raw'" in a]
    assert vetados and all("'postventa_restringida'" in a for a in vetados)
    assert "GRANT USAGE ON SCHEMA postventa_restringida TO sigrid_dm_autorizado_ro" in sql
    assert re.search(r"IN SCHEMA postventa_restringida\s+GRANT SELECT ON TABLES TO "
                     r"sigrid_dm_autorizado_ro", sql)


def test_f156_r31_roles_sin_contrasenas_escritas() -> None:
    sql = _roles()
    for linea in sql.splitlines():
        if "postventa" in linea.lower() and "PASSWORD" in linea.upper():
            assert ":'postventa_pwd'" in linea or linea.lstrip().startswith("--"), linea
