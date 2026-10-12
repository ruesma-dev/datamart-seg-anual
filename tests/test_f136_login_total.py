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


# ===========================================================================
# El paso (T3-T4): cliente falso que apunta lo que se le pide
# ===========================================================================


class _ClienteFalso:
    def __init__(
        self,
        existen: tuple[str, ...] = (ESTANDAR, AUTORIZADO, TOTAL),
        indebidas: dict[str, list[str]] | None = None,
        sin_usage: list[str] | None = None,
        falla_en: str = "",
    ) -> None:
        self.existen = existen
        self.indebidas = indebidas or {}
        self.sin_usage = sin_usage or []
        self.falla_en = falla_en
        self.llamadas: list[tuple] = []

    def _quizas_falla(self, que: str) -> None:
        if self.falla_en == que:
            raise RuntimeError(f"se cayó la conexión en {que}")

    def role_exists(self, role):  # noqa: ANN001, ANN201
        self.llamadas.append(("role_exists", role))
        return role in self.existen

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):  # noqa: ANN001, ANN201
        self.llamadas.append(("general", readonly_role))
        return ["G1", "G2"]

    def apply_restricted_grants(self, role, owner_role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("autorizado", role))
        return ["A1"]

    def apply_veto(self, role, owner_role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("veto", role, owner_role, list(schemas)))
        self._quizas_falla("veto")
        return ["V1", "V2", "V3"]

    def lecturas_indebidas(self, role, schemas, tables):  # noqa: ANN001, ANN201
        self.llamadas.append(("verifica", role, list(schemas), list(tables)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("usage", role, list(schemas)))
        self._quizas_falla("usage")
        return list(self.sin_usage)


def _settings(**pg: object):  # noqa: ANN202
    from types import SimpleNamespace

    base: dict[str, object] = {
        "readonly_role": ESTANDAR,
        "set_role": DUENO,
        "consumption_schema_list": ["mart", "contabilidad"],
        "excluded_table_list": ["raw.emp"],
        "vetoed_schema_list": [RESTR, "raw"],
        "restricted_role": AUTORIZADO,
        "restricted_schema_list": [RESTR],
        "total_role": TOTAL,
        "total_vetoed_schema_list": ["raw"],
    }
    base.update(pg)
    return SimpleNamespace(postgres=SimpleNamespace(**base))


def _paso(cliente: _ClienteFalso, **pg: object):  # noqa: ANN202
    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    return ApplyGrantsStep(_settings(**pg), client=cliente).run()


class _Log:
    def __init__(self) -> None:
        self.avisos: list[tuple[str, dict]] = []
        self.errores: list[tuple[str, dict]] = []

    def info(self, *a: object, **k: object) -> None: ...

    def warning(self, evento: str, **datos: object) -> None:
        self.avisos.append((evento, datos))

    def error(self, evento: str, **datos: object) -> None:
        self.errores.append((evento, datos))


@pytest.fixture
def log(monkeypatch: pytest.MonkeyPatch) -> _Log:
    from etl_sigrid.application.steps import apply_grants_step

    falso = _Log()
    monkeypatch.setattr(apply_grants_step, "logger", falso)
    return falso


# --- R2-R4 · guardas antes de abrir conexión (T3) --------------------------


@pytest.mark.parametrize(
    ("campo", "variable"),
    [("readonly_role", "PG_READONLY_ROLE"), ("restricted_role", "PG_RESTRICTED_ROLE"),
     ("set_role", "PG_SET_ROLE")],
)
def test_f136_r2_total_igual_a_otro_rol_para_en_seco(campo: str, variable: str) -> None:
    cliente = _ClienteFalso()
    otros = {"readonly_role": ESTANDAR, "restricted_role": AUTORIZADO, "set_role": DUENO}
    resultado = _paso(cliente, total_role=f" {otros[campo]} ")
    assert resultado.status.name == "FAILED"
    assert cliente.llamadas == [], "ni una sentencia, ni una pregunta al servidor"
    mensaje = resultado.error_message or ""
    assert "PG_TOTAL_ROLE" in mensaje and variable in mensaje
    for otra in {"PG_READONLY_ROLE", "PG_RESTRICTED_ROLE", "PG_SET_ROLE"} - {variable}:
        assert otra not in mensaje, "nombra la variable que choca, no las demás"
    assert resultado.finished_at is not None


def test_f136_r2_un_total_vacio_no_choca_con_un_autorizado_vacio() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, total_role="  ", restricted_role="", set_role="")
    assert resultado.status.name == "SUCCESS"


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"total_vetoed_schema_list": ["raw", RESTR]}, RESTR),  # en lo restringido
        ({"total_vetoed_schema_list": ["raw", "mart"], "vetoed_schema_list": [RESTR, "raw", "mart"],
          "consumption_schema_list": ["mart"]}, None),  # rompe antes la guarda de F-135
        ({"total_vetoed_schema_list": ["raw", "stg"]}, "stg"),  # no vetado al general
        ({"total_vetoed_schema_list": ["raw", "contabilidad"]}, "contabilidad"),  # en consumo
    ],
)
def test_f136_r3_vetados_del_total_incoherentes_para_en_seco(
    cambios: dict, esperado: str | None
) -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, **cambios)
    assert resultado.status.name == "FAILED"
    assert cliente.llamadas == []
    if esperado:
        mensaje = resultado.error_message or ""
        assert "PG_TOTAL_VETOED_SCHEMAS" in mensaje
        assert f"({esperado})" in mensaje, "la lista de esquemas en conflicto, y solo ellos"


def test_f136_r3_un_raw_en_lo_restringido_tambien_lo_para() -> None:
    """El caso que motiva D4: `raw` añadido a lo restringido lo heredaría el total."""
    cliente = _ClienteFalso()
    resultado = _paso(cliente, restricted_schema_list=[RESTR, "raw"])
    assert resultado.status.name == "FAILED"
    assert cliente.llamadas == []
    assert "PG_TOTAL_VETOED_SCHEMAS" in (resultado.error_message or "")
    assert "(raw)" in (resultado.error_message or "")


def test_f136_r4_sin_rol_estandar_no_pregunta_por_el_total() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, readonly_role="", total_role=ESTANDAR,
                      total_vetoed_schema_list=["mart"])
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == []
    assert resultado.rows_processed == 0



# --- R5-R11 · el bloque del total (T4) -------------------------------------

_CAMINO_ESTANDAR = [
    ("role_exists", ESTANDAR),
    ("general", ESTANDAR),
    ("role_exists", AUTORIZADO),
    ("autorizado", AUTORIZADO),
]


def test_f136_r7_camino_normal_en_orden_y_sin_grant_al_total() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == _CAMINO_ESTANDAR + [
        ("role_exists", TOTAL),
        ("veto", TOTAL, DUENO, ["raw"]),
        ("verifica", TOTAL, ["raw"], ["raw.emp"]),
        ("usage", TOTAL, ["mart", "contabilidad", RESTR]),
        ("verifica", ESTANDAR, [RESTR, "raw"], ["raw.emp"]),
    ], "el veto del total va DESPUÉS de las concesiones al estándar y al autorizado"
    assert not any(c[0] in ("general", "autorizado") and c[1] == TOTAL for c in cliente.llamadas), (
        "ningún GRANT al total: lee por pertenencia"
    )
    assert resultado.metadata["rol_total"] == TOTAL
    assert resultado.metadata["verificacion_total"] == "ok"
    assert resultado.metadata["acceso_total"] == "ok"
    assert resultado.metadata["verificacion"] == "ok"


def test_f136_r11_rows_processed_suma_el_veto_del_total() -> None:
    resultado = _paso(_ClienteFalso())
    assert resultado.rows_processed == 2 + 1 + 3


def test_f136_r5_sin_total_configurado_no_se_toca(log: _Log) -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, total_role="  ")
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == _CAMINO_ESTANDAR + [("verifica", ESTANDAR, [RESTR, "raw"], ["raw.emp"])]
    assert resultado.metadata["rol_total"] == "(sin configurar)"
    assert resultado.metadata["verificacion_total"] == "no aplica"
    assert resultado.metadata["acceso_total"] == "no aplica"
    assert resultado.rows_processed == 3
    assert log.avisos == []


def test_f136_r6_total_inexistente_avisa_y_sigue(log: _Log) -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, AUTORIZADO))
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == _CAMINO_ESTANDAR + [
        ("role_exists", TOTAL),
        ("verifica", ESTANDAR, [RESTR, "raw"], ["raw.emp"]),
    ], "ninguna sentencia ni pregunta sobre un login que no existe"
    assert log.avisos == [("apply_grants_login_total_inexistente",
                           {"role": TOTAL, "detalle": "créalo con infra/sql/02_roles.sql"})]
    assert resultado.metadata["rol_total"] == f"{TOTAL} (no existe)"
    assert resultado.metadata["verificacion_total"] == "no aplica"
    assert resultado.metadata["acceso_total"] == "no aplica"
    assert resultado.rows_processed == 3


def test_f136_r8_si_el_total_lee_algo_vetado_falla_con_la_lista() -> None:
    cliente = _ClienteFalso(indebidas={TOTAL: ["raw (USAGE)", "raw.apu (SELECT)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    mensaje = resultado.error_message or ""
    assert f"'{TOTAL}'" in mensaje and "raw (USAGE), raw.apu (SELECT)" in mensaje
    assert f"'{ESTANDAR}' sigue leyendo" not in mensaje, "el estándar no lee nada"
    assert "5 quater" in mensaje and "02_roles.sql" in mensaje
    assert resultado.metadata["verificacion_total"] == ["raw (USAGE)", "raw.apu (SELECT)"]
    assert resultado.metadata["verificacion"] == "ok"
    assert resultado.metadata["rol_total"] == TOTAL
    assert resultado.finished_at is not None


def test_f136_r8_las_excluidas_tambien_cuentan() -> None:
    """`PG_EXCLUDED_TABLES` se le pregunta también al total (R8)."""
    cliente = _ClienteFalso()
    _paso(cliente, excluded_table_list=["raw.emp", "raw.res"])
    assert ("verifica", TOTAL, ["raw"], ["raw.emp", "raw.res"]) in cliente.llamadas


def test_f136_r9_los_dos_leen_algo_un_solo_mensaje_con_las_dos_listas() -> None:
    cliente = _ClienteFalso(indebidas={ESTANDAR: ["raw.pag (SELECT)"], TOTAL: ["raw (USAGE)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    mensaje = resultado.error_message or ""
    assert f"'{ESTANDAR}' sigue leyendo lo vetado: raw.pag (SELECT)" in mensaje
    assert f"'{TOTAL}' lee lo vetado: raw (USAGE)" in mensaje
    assert resultado.metadata["verificacion"] == ["raw.pag (SELECT)"]
    assert resultado.metadata["verificacion_total"] == ["raw (USAGE)"]


def test_f136_r9_solo_el_estandar_el_mensaje_de_f135_no_cambia() -> None:
    cliente = _ClienteFalso(indebidas={ESTANDAR: ["raw (USAGE)"]})
    resultado = _paso(cliente)
    mensaje = resultado.error_message or ""
    assert resultado.status.name == "FAILED"
    assert mensaje.startswith(f"el rol '{ESTANDAR}' sigue leyendo lo vetado: raw (USAGE). ")
    assert f"'{TOTAL}'" not in mensaje
    assert resultado.metadata["verificacion_total"] == "ok"


def test_f136_r10_al_total_le_falta_lectura_avisa_sin_fallar(log: _Log) -> None:
    cliente = _ClienteFalso(sin_usage=[RESTR])
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", "D5: que lea de menos no expone nada"
    assert resultado.metadata["acceso_total"] == [RESTR]
    assert resultado.metadata["verificacion_total"] == "ok"
    assert len(log.avisos) == 1
    evento, datos = log.avisos[0]
    assert evento == "apply_grants_login_total_incompleto"
    assert datos["role"] == TOTAL and datos["faltan"] == [RESTR]
    assert "5 quater" in str(datos["detalle"])


def test_f136_r10_incompleto_y_ademas_lee_lo_vetado() -> None:
    cliente = _ClienteFalso(sin_usage=["mart"], indebidas={TOTAL: ["raw (USAGE)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    assert resultado.metadata["acceso_total"] == ["mart"]


def test_f136_paso_el_total_se_mira_aunque_falte_el_autorizado(log: _Log) -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, TOTAL), sin_usage=[RESTR])
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    assert ("veto", TOTAL, DUENO, ["raw"]) in cliente.llamadas
    assert resultado.metadata["acceso_total"] == [RESTR]
    assert [e for e, _ in log.avisos] == [
        "apply_grants_rol_autorizado_inexistente", "apply_grants_login_total_incompleto",
    ]


def test_f136_paso_sin_estandar_sale_antes_y_no_mira_el_total() -> None:
    cliente = _ClienteFalso(existen=(AUTORIZADO, TOTAL))
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == [("role_exists", ESTANDAR)]


@pytest.mark.parametrize("donde", ["veto", "usage"])
def test_f136_paso_un_fallo_del_cliente_en_el_total_es_failed(donde: str) -> None:
    cliente = _ClienteFalso(falla_en=donde)
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    assert f"se cayó la conexión en {donde}" in (resultado.error_message or "")
    assert ("verifica", ESTANDAR, [RESTR, "raw"], ["raw.emp"]) not in cliente.llamadas


def test_f136_paso_sin_nombres_a_mano_y_docstring() -> None:
    from etl_sigrid.application.steps import apply_grants_step

    fuente = Path(apply_grants_step.__file__).read_text(encoding="utf-8")
    ejecutable = "\n".join(f for f in fuente.splitlines() if not f.lstrip().startswith("#"))
    codigo = ejecutable.split('"""', 2)[2]
    assert TOTAL not in codigo, "el nombre sale de PG_TOTAL_ROLE, no del paso"
    for campo in ("total_role", "total_vetoed_schema_list"):
        assert campo in codigo
    doc = apply_grants_step.__doc__ or ""
    assert "F-136" in doc and "total" in doc


# ===========================================================================
# R12-R19 · infra/sql/02_roles.sql (T5): contrato textual. La prueba con
# PostgreSQL 16 real y el psql.exe de Windows está en impl_F-136.md (T10).
# ===========================================================================

ROLES_SQL = RAIZ / "infra" / "sql" / "02_roles.sql"
LOGINS = (("sigrid_dm_app", "app_pwd", "APP_PWD"), (ESTANDAR, "mcp_pwd", "MCP_PWD"),
          (TOTAL, "total_pwd", "TOTAL_PWD"))


def _roles_crudo() -> str:
    return ROLES_SQL.read_text(encoding="utf-8")


def _roles_sql() -> str:
    """El fichero sin las líneas de comentario: una cita no ejecuta nada."""
    return "\n".join(
        linea for linea in _roles_crudo().splitlines() if not linea.lstrip().startswith("--")
    )


def test_f136_r12_crea_el_total_login_idempotente() -> None:
    sql = _roles_sql()
    assert (
        f"SELECT 'CREATE ROLE {TOTAL} LOGIN'\n"
        f"WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{TOTAL}')\n\\gexec"
    ) in sql
    assert f"ALTER ROLE {TOTAL} WITH LOGIN NOCREATEDB NOCREATEROLE;" in sql
    assert "NOSUPERUSER" not in sql, "Azure no lo admite: CREATE ROLE ya lo da"


def test_f136_r12_la_comprobacion_final_mira_rolsuper_de_los_cinco() -> None:
    import re

    sql = _roles_sql()
    consulta = re.search(r"SELECT rolname, rolcanlogin, rolsuper.*?;", sql, re.DOTALL)
    assert consulta
    roles = set(re.findall(r"'(\w+)'", consulta.group(0)))
    assert roles == {DUENO, "sigrid_dm_app", ESTANDAR, AUTORIZADO, TOTAL}


def _tramo_transaccion(sql: str) -> tuple[int, int]:
    return sql.index("\nBEGIN;"), sql.index("\nCOMMIT;")


def test_f136_r13_las_dos_pertenencias_como_administrador_en_la_transaccion() -> None:
    sql = _roles_sql()
    apertura, cierre = _tramo_transaccion(sql)
    for grupo in (ESTANDAR, AUTORIZADO):
        sentencia = f"GRANT {grupo} TO {TOTAL} WITH INHERIT TRUE, SET FALSE;"
        assert sql.count(sentencia) == 1, f"falta: {sentencia}"
        pos = sql.index(sentencia)
        assert apertura < pos < cierre, "fuera de la transacción"
        antes = sql[:pos]
        assert antes.rindex("RESET ROLE;") > antes.rindex("SET ROLE sigrid_dm_etl;"), (
            "como el ADMINISTRADOR, que tiene ADMIN OPTION; sigrid_dm_etl no"
        )
        ultimo_veto = antes.rfind(f"FROM {TOTAL}")
        assert ultimo_veto != -1, "después del veto del 5 ter: nunca hereda un raw abierto"


def test_f136_r14_raw_vetado_al_total_con_los_dos_concedentes() -> None:
    import re

    from config.settings import DEFAULT_TOTAL_VETOED_SCHEMAS

    sql = _roles_sql()
    listas = re.findall(r"FOREACH vetado_total IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert len(listas) == 2, "una vez como administrador y otra como sigrid_dm_etl"
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == DEFAULT_TOTAL_VETOED_SCHEMAS.split(",")
    for sentencia in (
        f"REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM {TOTAL}",
        f"REVOKE ALL PRIVILEGES ON SCHEMA %I FROM {TOTAL}",
    ):
        assert sql.count(sentencia) == 2, f"«{sentencia}» con los dos concedentes"
    assert sql.count(f"REVOKE ALL ON TABLES FROM {TOTAL}") == 1, "privilegio por defecto, como dueño"
    assert sql.count("IF to_regnamespace(vetado_total) IS NOT NULL THEN") == 2
    apertura, cierre = _tramo_transaccion(sql)
    posiciones = [m.start() for m in re.finditer(r"FOREACH vetado_total IN ARRAY", sql)]
    assert all(apertura < p < cierre for p in posiciones)
    assert "FOREACH vetado_total IN ARRAY" in sql.split("SET ROLE sigrid_dm_etl;")[-1]


def test_f136_r15_ningun_grant_al_total_salvo_las_pertenencias() -> None:
    import re

    sql = _roles_sql()
    concesiones = re.findall(rf"GRANT\b[^;]*?\bTO\s+{TOTAL}\b[^;]*;", sql)
    assert concesiones == [
        f"GRANT {ESTANDAR} TO {TOTAL} WITH INHERIT TRUE, SET FALSE;",
        f"GRANT {AUTORIZADO} TO {TOTAL} WITH INHERIT TRUE, SET FALSE;",
    ]
    assert not re.search(rf"\bTO\s+{TOTAL}\b'", sql), "ni dentro de un format() de un DO"


def test_f136_r16_contrasenas_por_getenv_y_silencio_antes() -> None:
    sql = _roles_sql()
    primera = sql.index("PASSWORD")
    for orden in ("\\set ECHO none", "\\set VERBOSITY terse", "\\set SHOW_CONTEXT never",
                  "\\set ON_ERROR_STOP on"):
        assert orden in sql and sql.index(orden) < primera, f"{orden} antes de la primera contraseña"
    for _, variable, entorno in LOGINS:
        linea = f"\\getenv {variable} {entorno}"
        assert linea in sql and sql.index(linea) < primera


def test_f136_r16_la_cabecera_no_pasa_contrasenas_con_v() -> None:
    import re

    assert not re.search(r"-v\s+\w*_?pwd", _roles_crudo(), re.IGNORECASE)


def test_f136_r17_cada_contrasena_es_opcional_y_se_anuncia_sin_valor() -> None:
    sql = _roles_sql()
    for login, variable, _ in LOGINS:
        bloque = (
            f"\\if :{{?{variable}}}\n"
            f"ALTER ROLE {login} WITH LOGIN PASSWORD :'{variable}';\n"
            f"\\echo '{login}: contraseña fijada'\n"
            "\\else\n"
            f"\\echo '{login}: contraseña SIN CAMBIOS'\n"
            "\\endif"
        )
        assert bloque in sql, f"falta el bloque de {login}"
        assert sql.count(f"PASSWORD :'{variable}'") == 1
    assert sql.count("PASSWORD") == 3, "ninguna otra sentencia con contraseña"


def test_f136_r18_guarda_antes_de_crear_nada() -> None:
    sql = _roles_sql()
    primera_escritura = min(sql.index("CREATE ROLE"), sql.index("ALTER ROLE"))
    guarda = sql.index("\\gset")
    assert guarda < primera_escritura
    for login, variable, entorno in LOGINS:
        clave = f"falta_{variable.removesuffix('_pwd')}"
        assert f"NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{login}') AS {clave}" in sql
        bloque = (
            f"\\if :{clave}\n"
            f"\\if :{{?{variable}}}\n"
            "\\else\n"
            f"DO $$ BEGIN RAISE EXCEPTION 'F-136: {login} no existe y falta {entorno} "
            "en el entorno (runbook §12)'; END $$;\n"
            "\\endif\n"
            "\\endif"
        )
        assert bloque in sql, f"falta la guarda de {login}"
        assert sql.index(bloque) < primera_escritura


def test_f136_r19_comprobacion_final_del_total() -> None:
    sql = _roles_sql()
    final = sql.split("\nCOMMIT;", 1)[1]
    assert (
        "FROM pg_auth_members AS m\n"
        "JOIN pg_roles AS r ON r.oid = m.member\n"
        "JOIN pg_roles AS g ON g.oid = m.roleid\n"
        f"WHERE r.rolname = '{TOTAL}'"
    ) in final
    for esquema in ("raw", RESTR, "contabilidad"):
        assert f"has_schema_privilege('{TOTAL}', '{esquema}', 'USAGE')" in final
    assert f"has_database_privilege('{TOTAL}', current_database(), 'CONNECT')" in final
    assert f"WHERE grantee = '{TOTAL}'" in final


def test_f136_r12_r19_la_cabecera_explica_el_total_y_el_uso_nuevo() -> None:
    cabecera = _roles_crudo().split("\\set ON_ERROR_STOP on")[0]
    for texto in (TOTAL, "TOTAL_PWD", "\\getenv", "2026-10-12", "-X -v ON_ERROR_STOP=1 -f"):
        assert texto in cabecera, f"la cabecera no cita {texto}"


# ===========================================================================
# R20-R21 · psql con las opciones DELANTE y sin contraseñas con -v (T6)
# ===========================================================================

PROVISION = RAIZ / "infra" / "15_provision_db.ps1"
RUNBOOK = RAIZ / "docs" / "runbook_postgres_azure.md"


def _unir_continuaciones(lineas: list[str]) -> list[str]:
    """Une las líneas partidas con `\\` (bash) o con acento grave (PowerShell)."""
    unidas: list[str] = []
    actual = ""
    for linea in lineas:
        cuerpo = linea.rstrip()
        if cuerpo.endswith("\\") or cuerpo.endswith("`"):
            actual += cuerpo[:-1] + " "
            continue
        unidas.append(actual + cuerpo)
        actual = ""
    if actual:
        unidas.append(actual)
    return unidas


def _codigo_del_runbook() -> list[str]:
    lineas: list[str] = []
    dentro = False
    for linea in RUNBOOK.read_text(encoding="utf-8").splitlines():
        if linea.lstrip().startswith("```"):
            dentro = not dentro
            continue
        if dentro and not linea.lstrip().startswith("#"):
            lineas.append(linea)
    return _unir_continuaciones(lineas)


def _codigo_de_provision() -> list[str]:
    lineas = [
        linea for linea in PROVISION.read_text(encoding="utf-8-sig").splitlines()
        if not linea.lstrip().startswith("#")
    ]
    return _unir_continuaciones(lineas)


def _uso_de_02_roles() -> list[str]:
    return [
        linea.lstrip("- ").strip() for linea in _roles_crudo().splitlines()
        if linea.startswith("--") and linea.lstrip("- ").startswith("psql ")
    ]


def _llamadas_psql(lineas: list[str]) -> list[str]:
    import re

    return [
        linea[m.start(1):] for linea in lineas
        for m in [re.search(r"(?:^|[\s(;&|{])(psql(?:\.exe)?)\s", linea)] if m
    ]


#: la cadena de conexión: literal entre comillas o una variable `$dsn...`
_CADENA = r"(\"host=[^\"]*\"|\"?\$dsn\w*\"?)"


def _opciones_tras_la_cadena(llamada: str) -> str | None:
    """Lo que venga DETRÁS de la cadena de conexión con pinta de opción, o None."""
    import re

    m = re.search(_CADENA, llamada)
    if not m:
        return None
    resto = llamada[m.end():]
    # el final de la llamada: tubería, redirección, separador o cierre de bloque
    resto = re.split(r"\s[|;}>]|\s*#|\s2>", resto)[0]
    opcion = re.search(r"(?:^|\s)(-{1,2}[A-Za-z][\w-]*)", resto)
    return opcion.group(1) if opcion else ""


@pytest.mark.parametrize(
    "origen", ["runbook", "15_provision_db.ps1", "02_roles.sql"],
)
def test_f136_r20_psql_con_las_opciones_antes_de_la_cadena(origen: str) -> None:
    lineas = {
        "runbook": _codigo_del_runbook,
        "15_provision_db.ps1": _codigo_de_provision,
        "02_roles.sql": _uso_de_02_roles,
    }[origen]()
    llamadas = _llamadas_psql(lineas)
    assert llamadas, f"{origen}: no se encontró ninguna llamada a psql"
    for llamada in llamadas:
        if llamada.split()[1:2] == ["--version"]:
            continue
        tras = _opciones_tras_la_cadena(llamada)
        assert tras is not None, f"{origen}: llamada sin cadena de conexión: {llamada}"
        assert tras == "", f"{origen}: «{tras}» va detrás de la cadena: {llamada}"


@pytest.mark.parametrize("ruta", [PROVISION, RUNBOOK, ROLES_SQL])
def test_f136_r20_ninguna_contrasena_con_v(ruta: Path) -> None:
    import re

    texto = ruta.read_text(encoding="utf-8-sig")
    assert not re.search(r"-v\s+\w*pwd", texto, re.IGNORECASE), ruta.name
    assert not re.search(r"-v\s+\w*(password|clave)", texto, re.IGNORECASE), ruta.name


def test_f136_r20_el_detector_caza_la_incidencia() -> None:
    """La forma del 2026-10-12 y la de `15_provision_db.ps1` antes de F-136."""
    assert _opciones_tras_la_cadena('psql "host=h dbname=d" -v ON_ERROR_STOP=1 -f x.sql') == "-v"
    assert _opciones_tras_la_cadena('psql "$dsnAdmin" -f (Join-Path $d "x.sql")') == "-f"
    assert _opciones_tras_la_cadena('psql -X -c "SELECT 1" $dsnT') == ""
    assert _opciones_tras_la_cadena('psql -X -f x.sql "host=h user=u"') == ""
    assert _opciones_tras_la_cadena("psql -X -c 'SELECT 1'") is None
    assert _llamadas_psql(["  & psql -X -f a $dsn"]) == ["psql -X -f a $dsn"]
    assert _llamadas_psql(["el `psql` de Windows"]) == []
    assert _unir_continuaciones(["psql -X `", "  -f a `", "  $dsn"]) == ["psql -X    -f a    $dsn"]


def test_f136_r21_provision_exige_las_tres_y_no_las_pasa() -> None:
    texto = PROVISION.read_text(encoding="utf-8-sig")
    codigo = "\n".join(_codigo_de_provision())
    for variable in ("APP_PWD", "MCP_PWD", "TOTAL_PWD"):
        assert f"-not $env:{variable}" in codigo, f"-Ejecutar no exige {variable}"
    for llamada in _llamadas_psql(_codigo_de_provision()):
        assert "PWD" not in llamada.upper(), (
            f"la contraseña llega a psql por herencia del entorno, no por argumento: {llamada}"
        )
        assert llamada.startswith("psql -X "), f"sin -X (psqlrc) : {llamada}"
    assert TOTAL in texto, "el rótulo de roles nombra el total"


# ===========================================================================
# R22 y R25 · el procedimiento MANUAL del runbook, §12 (T7)
# ===========================================================================


def _seccion_12() -> str:
    texto = RUNBOOK.read_text(encoding="utf-8")
    assert "\n## 12. " in texto, "falta la §12 del runbook"
    return texto.split("\n## 12. ", 1)[1].split("\n## ", 1)[0]


def _bloques_de_codigo(texto: str) -> list[str]:
    bloques: list[str] = []
    actual: list[str] | None = None
    for linea in texto.splitlines():
        if linea.lstrip().startswith("```"):
            if actual is None:
                actual = []
            else:
                bloques.append("\n".join(actual))
                actual = None
            continue
        if actual is not None:
            actual.append(linea)
    return bloques


def _lineas_de_codigo_del_runbook() -> list[str]:
    """Las líneas de los bloques de código: la prosa puede citar los comandos."""
    return [
        linea for bloque in _bloques_de_codigo(RUNBOOK.read_text(encoding="utf-8"))
        for linea in bloque.splitlines()
    ]


def test_f136_r22_todo_show_es_una_asignacion() -> None:
    import re

    lineas = [
        linea for linea in _lineas_de_codigo_del_runbook()
        if "az keyvault secret show" in linea and not linea.lstrip().startswith("#")
    ]
    assert lineas, "el runbook no lee ningún secreto: ¿se ha movido el procedimiento?"
    for linea in lineas:
        assert re.match(r"^\s*\$[\w:]+\s*=\s*az keyvault secret show\b", linea), (
            f"un `show` sin asignar imprime el valor: {linea.strip()}"
        )


def test_f136_r22_todo_set_lleva_o_none() -> None:
    lineas = [
        linea for linea in _lineas_de_codigo_del_runbook()
        if "az keyvault secret set" in linea and not linea.lstrip().startswith("#")
    ]
    assert len(lineas) >= 6, "§4 (dos) y §12 P2 (cuatro)"
    for linea in lineas:
        assert linea.rstrip().endswith("-o none"), f"un `set` sin -o none devuelve el valor: {linea}"


def test_f136_r22_lineas_cortas_en_la_seccion_12() -> None:
    largas = [
        linea for bloque in _bloques_de_codigo(_seccion_12()) for linea in bloque.splitlines()
        if len(linea) > 100
    ]
    assert largas == []


def test_f136_r22_sin_query_que_rompa_az_cmd() -> None:
    """`az.cmd` en Windows parte un `--query` con `&`, `|` o `(`."""
    import re

    for bloque in _bloques_de_codigo(_seccion_12()):
        for consulta in re.findall(r'--query\s+"([^"]*)"', bloque):
            assert not set(consulta) & set("&|("), consulta


def test_f136_r25_el_procedimiento_en_orden() -> None:
    seccion = _seccion_12()
    pasos = [f"### P{n} " for n in range(14)]
    posiciones = [seccion.find(p) for p in pasos]
    assert -1 not in posiciones, [p for p, pos in zip(pasos, posiciones) if pos == -1]
    assert posiciones == sorted(posiciones), "P0 a P13, en orden"
    assert "### Vuelta atrás" in seccion
    assert "PowerShell 5.1" in seccion


def _paso_12(seccion: str, n: int) -> str:
    return seccion.split(f"### P{n} ", 1)[1].split("\n### ", 1)[0]


def test_f136_r25_vault_primero_con_los_cuatro_secretos() -> None:
    seccion = _seccion_12()
    p2 = _paso_12(seccion, 2)
    for vault, secreto in (
        ("$kvDm", "pg-sigrid-dm-app"), ("$kvDm", "pg-mcp-sigrid-dm-ro"),
        ("$kvMcp", "pg-password"), ("$kvMcp", "pg-password-total"),
    ):
        assert f"--vault-name {vault} --name {secreto} --value $v -o none" in p2, secreto
    assert p2.count("$LASTEXITCODE") == 4
    assert p2.rstrip("`\n ").endswith("$v = $null")
    estandar = p2.split("pg-mcp-sigrid-dm-ro --value $v", 1)[1].split("Nueva-Clave", 1)[0]
    assert "--name pg-password --value $v" in estandar, "el estándar: el MISMO valor en los dos vaults"
    p1 = _paso_12(seccion, 1)
    assert '$kvDm  = "kv-datamart-seg-dev"' in p1 and '$kvMcp = "kv-mcp-bbdd-dev"' in p1
    assert "RandomNumberGenerator" in p1 and '"x2"' in p1


def test_f136_r25_releer_ejecutar_borrar_y_reiniciar() -> None:
    seccion = _seccion_12()
    p3 = _paso_12(seccion, 3)
    for variable in ("APP_PWD", "MCP_PWD", "TOTAL_PWD"):
        assert f"$env:{variable} = az keyvault secret show" in p3
    assert "-ne $env:MCP_PWD" in p3 and "64" in p3, "las dos copias del estándar y la longitud"
    assert "psql -X -v ON_ERROR_STOP=1 -f $roles $dsn" in _paso_12(seccion, 4)
    assert "Remove-Item Env:APP_PWD, Env:MCP_PWD, Env:TOTAL_PWD" in _paso_12(seccion, 5)
    p6 = _paso_12(seccion, 6)
    assert "az containerapp revision restart" in p6 and "ca-mcp-bbdd-dev" in p6
    p7 = _paso_12(seccion, 7)
    for cosa in (".env", ".env.azure.bak", "mcp-bbdd", "python main.py check-pg", "Set-Clipboard"):
        assert cosa in p7, cosa
    assert "Power BI" in _paso_12(seccion, 8)


def test_f136_r26_r28_las_pruebas_del_procedimiento() -> None:
    seccion = _seccion_12()
    p9 = _paso_12(seccion, 9)
    assert "list-versions" in p9 and "ConvertFrom-Json" in p9
    assert "password authentication failed" in p9
    assert "Remove-Item Env:PGPASSWORD" in p9
    p10 = _paso_12(seccion, 10)
    assert 'foreach ($t in "apu", "pag", "asi", "rac", "hmores", "con", "apa")' in p10
    assert "permission denied" in p10 and "CREATE TABLE contabilidad." in p10
    assert "contabilidad_restringida.mayor" in p10 and "contabilidad.mayor" in p10
    assert "raw.apu" in p10 and "Remove-Item Env:PGPASSWORD" in p10
    assert "python main.py apply-grants" in _paso_12(seccion, 11)
    p12 = _paso_12(seccion, 12)
    assert '--args "main.py,check-pg"' in p12 and "verificacion_total" in p12
    assert "kv-albaranes-rs9k2" in _paso_12(seccion, 13)


def test_f136_r25_la_tabla_de_roles_tiene_los_cinco() -> None:
    texto = RUNBOOK.read_text(encoding="utf-8")
    tabla = texto.split("## 1. Autenticación", 1)[1].split("\n## ", 1)[0]
    for rol in (DUENO, "sigrid_dm_app", ESTANDAR, AUTORIZADO, TOTAL):
        assert f"| `{rol}` |" in tabla, rol
