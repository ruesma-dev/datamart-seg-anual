# tests/test_f135_grants.py
"""
F-135 · Los permisos, cada noche (R15-R20).

El rol GENERAL (`mcp_sigrid_dm_ro`, el del MCP y Power BI) no puede leer
`contabilidad_restringida` ni `raw`; el rol AUTORIZADO
(`sigrid_dm_restringido_ro`, grupo NOLOGIN) lee la contabilidad completa. Todo
vive en `apply_grants`, que corre cada noche, y en `infra/sql/02_roles.sql`,
que provisiona: hecho a mano contra la base, la nocturna lo desharía (F-068).

Ningún test abre red ni BBDD: el cliente se simula.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.infrastructure.postgres import grants
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements

RAIZ = Path(__file__).resolve().parents[1]
ROL = "mcp_sigrid_dm_ro"
AUTORIZADO = "sigrid_dm_restringido_ro"
DUENO = "sigrid_dm_etl"
RESTR = "contabilidad_restringida"


# ===========================================================================
# R19 y la configuración (T5)
# ===========================================================================


def test_f135_r19_raw_fuera_de_los_esquemas_de_consumo() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    consumo = [s.strip() for s in DEFAULT_CONSUMPTION_SCHEMAS.split(",")]
    assert "raw" not in consumo, "D3-A: raw fuera entero del rol general"
    assert RESTR not in consumo
    assert consumo == [
        "mart", "cierre", "compras", "maestro", "retenciones", "personal",
        # F-037 añade `tesoreria` (la general; la restringida, vetada)
        "contabilidad", "tesoreria", "descompuestos", "stg", "aux", "_meta",
    ], "el resto, igual que antes de F-135"


def test_f135_r19_las_exclusiones_de_f068_se_conservan() -> None:
    from config.settings import DEFAULT_EXCLUDED_TABLES

    assert DEFAULT_EXCLUDED_TABLES == "raw.emp,raw.res,raw.reshor,raw.emphis"


def test_f135_settings_vetados_por_defecto() -> None:
    from config.settings import DEFAULT_VETOED_SCHEMAS, PostgresSettings

    # F-037 añade `tesoreria_restringida` a los dos: vetada y del autorizado;
    # F-138, `compras_restringida`.
    assert DEFAULT_VETOED_SCHEMAS == "contabilidad_restringida,tesoreria_restringida,compras_restringida,raw"
    pg = PostgresSettings(_env_file=None)
    assert pg.vetoed_schema_list == [RESTR, "tesoreria_restringida", "compras_restringida", "raw"]
    assert pg.restricted_role == AUTORIZADO
    assert pg.restricted_schema_list == [RESTR, "tesoreria_restringida", "compras_restringida"]


def test_f135_settings_parametrizables_y_limpias() -> None:
    from config.settings import PostgresSettings

    pg = PostgresSettings(
        _env_file=None,
        vetoed_schemas=" contabilidad_restringida , raw ,, otro ",
        restricted_schemas=" contabilidad_restringida ,",
        restricted_role="otro_rol",
    )
    assert pg.vetoed_schema_list == [RESTR, "raw", "otro"]
    assert pg.restricted_schema_list == [RESTR]
    assert pg.restricted_role == "otro_rol"
    assert PostgresSettings(_env_file=None, vetoed_schemas="").vetoed_schema_list == []


def test_f135_settings_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from config.settings import PostgresSettings

    monkeypatch.setenv("PG_VETOED_SCHEMAS", "raw")
    monkeypatch.setenv("PG_RESTRICTED_ROLE", "rol_x")
    monkeypatch.setenv("PG_RESTRICTED_SCHEMAS", "esq_x")
    pg = PostgresSettings(_env_file=None)
    assert (pg.vetoed_schema_list, pg.restricted_role, pg.restricted_schema_list) == (
        ["raw"], "rol_x", ["esq_x"]
    )


def test_f135_settings_env_example_documenta_las_tres() -> None:
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    lineas = dict(
        linea.split("=", 1) for linea in texto.splitlines()
        if linea and not linea.startswith("#") and "=" in linea
    )
    # F-037: con `tesoreria_restringida` en las dos listas.
    assert lineas["PG_VETOED_SCHEMAS"] == "contabilidad_restringida,tesoreria_restringida,compras_restringida,raw"
    assert lineas["PG_RESTRICTED_ROLE"] == AUTORIZADO
    assert lineas["PG_RESTRICTED_SCHEMAS"] == f"{RESTR},tesoreria_restringida,compras_restringida"
    assert "raw" not in lineas["PG_CONSUMPTION_SCHEMAS"].split(","), (
        "el .env.example no puede reabrir raw: R17 tumbaría apply_grants"
    )


def test_f135_settings_el_comentario_de_f068_avisa_de_f135() -> None:
    texto = (RAIZ / "config" / "settings.py").read_text(encoding="utf-8")
    bloque = texto.split("DEFAULT_EXCLUDED_TABLES =")[0]
    assert "F-135" in bloque and "PG_VETOED_SCHEMAS" in bloque, (
        "quien quiera devolver raw tiene que saber que ahora está vetado"
    )


# ===========================================================================
# R15-R17 · las sentencias (T6)
# ===========================================================================


def test_f135_r17_conflicto_entre_consumo_y_vetados() -> None:
    assert grants.esquemas_en_conflicto(["mart", "raw", "stg"], ["contabilidad_restringida", "raw"]) == ["raw"]
    assert grants.esquemas_en_conflicto(["raw", "mart", "raw", RESTR], [RESTR, "raw"]) == ["raw", RESTR]
    assert grants.esquemas_en_conflicto(["mart", "stg"], [RESTR, "raw"]) == []
    assert grants.esquemas_en_conflicto([], ["raw"]) == []
    assert grants.esquemas_en_conflicto(["raw"], []) == []


def test_f135_r16_veto_con_propietario() -> None:
    assert grants.build_veto_statements(ROL, DUENO, [RESTR, "raw"]) == [
        f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "{RESTR}" FROM "{ROL}"',
        f'REVOKE ALL PRIVILEGES ON SCHEMA "{RESTR}" FROM "{ROL}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "{RESTR}" REVOKE ALL ON TABLES FROM "{ROL}"',
        f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "raw" FROM "{ROL}"',
        f'REVOKE ALL PRIVILEGES ON SCHEMA "raw" FROM "{ROL}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" REVOKE ALL ON TABLES FROM "{ROL}"',
    ]


def test_f135_r16_veto_sin_propietario() -> None:
    assert grants.build_veto_statements(ROL, "", ["raw"]) == [
        f'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA "raw" FROM "{ROL}"',
        f'REVOKE ALL PRIVILEGES ON SCHEMA "raw" FROM "{ROL}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA "raw" REVOKE ALL ON TABLES FROM "{ROL}"',
    ]


def test_f135_r16_veto_vacio_y_citado() -> None:
    assert grants.build_veto_statements(ROL, DUENO, []) == []
    sentencias = grants.build_veto_statements('rol"raro', 'due"no', ['esq"x'])
    assert all('"rol""raro"' in s for s in sentencias)
    assert all('"esq""x"' in s for s in sentencias)
    assert '"due""no"' in sentencias[2]
    assert not any(s.startswith("GRANT") or " GRANT " in s for s in sentencias), "un veto nunca concede"


def test_f135_r15_concesiones_del_rol_autorizado() -> None:
    assert grants.build_restricted_grant_statements(AUTORIZADO, DUENO, [RESTR]) == [
        f'GRANT USAGE ON SCHEMA "{RESTR}" TO "{AUTORIZADO}"',
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "{RESTR}" TO "{AUTORIZADO}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "{RESTR}" GRANT SELECT ON TABLES TO "{AUTORIZADO}"',
    ]
    assert grants.build_restricted_grant_statements(AUTORIZADO, "", [RESTR])[2] == (
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{RESTR}" GRANT SELECT ON TABLES TO "{AUTORIZADO}"'
    )
    assert grants.build_restricted_grant_statements(AUTORIZADO, DUENO, []) == []
    texto = "\n".join(grants.build_restricted_grant_statements(AUTORIZADO, DUENO, [RESTR, "otro"]))
    for prohibido in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALL PRIVILEGES", "REVOKE"):
        assert prohibido not in texto, "el autorizado solo LEE"
    assert texto.count('"otro"') == 3


def test_f135_r15_el_autorizado_citado() -> None:
    sentencias = grants.build_restricted_grant_statements('a"b', DUENO, [RESTR])
    assert all('"a""b"' in s for s in sentencias)


def test_f135_r16_la_concesion_general_no_cambia() -> None:
    """F-068 intacto: `build_readonly_grant_statements` no sabe nada de vetos."""
    assert build_readonly_grant_statements(ROL, DUENO, ["mart"]) == [
        f'GRANT USAGE ON SCHEMA "mart" TO "{ROL}"',
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "mart" TO "{ROL}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "mart" GRANT SELECT ON TABLES TO "{ROL}"',
    ]


# ===========================================================================
# El cliente (T7): con conexión simulada, sin BBDD
# ===========================================================================


class _Cursor:
    def __init__(self, registro: list, respuestas: dict) -> None:
        self._registro = registro
        self._respuestas = respuestas
        self._ultimo: list = []

    def execute(self, stmt: str, params: object = None) -> None:
        self._registro.append((stmt, params))
        clave = "esquemas" if "has_schema_privilege" in stmt else (
            "tablas" if "has_table_privilege" in stmt else None
        )
        self._ultimo = list(self._respuestas.get(clave, [])) if clave else []

    def fetchall(self) -> list:
        return self._ultimo

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *a: object) -> None:
        return None


class _Conn:
    def __init__(self, registro: list, respuestas: dict) -> None:
        self._registro = registro
        self._respuestas = respuestas

    def cursor(self) -> _Cursor:
        return _Cursor(self._registro, self._respuestas)

    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *a: object) -> None:
        return None


def _cliente(esquemas: list[str], respuestas: dict | None = None) -> tuple[object, list]:
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    registro: list = []
    cliente = PostgresClient.__new__(PostgresClient)
    cliente._target_db = "sigrid_dm"  # type: ignore[attr-defined]
    cliente.list_schemas = lambda: esquemas  # type: ignore[method-assign]
    cliente.table_exists = lambda esquema, tabla: True  # type: ignore[method-assign]
    cliente.connection = lambda: _Conn(registro, respuestas or {})  # type: ignore[method-assign]
    return cliente, registro


def test_f135_cliente_veta_despues_de_conceder_y_solo_lo_que_existe() -> None:
    cliente, registro = _cliente(["mart", "raw"])
    sentencias = cliente.apply_readonly_grants(  # type: ignore[attr-defined]
        readonly_role=ROL, owner_role=DUENO, schemas=["mart"],
        vetoed_schemas=[RESTR, "raw"],
    )
    ejecutadas = [s for s, _ in registro]
    assert ejecutadas == sentencias
    assert sentencias[-3:] == grants.build_veto_statements(ROL, DUENO, ["raw"]), (
        "el veto va DETRÁS de todo GRANT, y solo sobre esquemas que existen"
    )
    assert not any(RESTR in s for s in sentencias), "un REVOKE sobre un esquema ausente falla"
    ultimo_grant = max(i for i, s in enumerate(sentencias) if s.startswith("GRANT"))
    primer_veto = sentencias.index(grants.build_veto_statements(ROL, DUENO, ["raw"])[0])
    assert ultimo_grant < primer_veto


def test_f135_cliente_sin_vetos_es_lo_de_siempre() -> None:
    cliente, registro = _cliente(["mart"])
    sentencias = cliente.apply_readonly_grants(  # type: ignore[attr-defined]
        readonly_role=ROL, owner_role=DUENO, schemas=["mart"],
    )
    assert sentencias == build_readonly_grant_statements(
        ROL, DUENO, ["mart"], database="sigrid_dm"
    )


def test_f135_cliente_concede_al_autorizado_solo_lo_que_existe() -> None:
    cliente, registro = _cliente(["mart", RESTR])
    sentencias = cliente.apply_restricted_grants(AUTORIZADO, DUENO, [RESTR, "fantasma"])  # type: ignore[attr-defined]
    assert sentencias == grants.build_restricted_grant_statements(AUTORIZADO, DUENO, [RESTR])
    assert [s for s, _ in registro] == sentencias


def test_f135_cliente_autorizado_sin_esquema_no_ejecuta_nada() -> None:
    cliente, registro = _cliente(["mart"])
    assert cliente.apply_restricted_grants(AUTORIZADO, DUENO, [RESTR]) == []  # type: ignore[attr-defined]
    assert registro == []


def test_f135_cliente_lecturas_indebidas_pregunta_al_catalogo() -> None:
    cliente, registro = _cliente(
        ["raw"],
        {"esquemas": [("raw",)], "tablas": [("raw.apu",), ("raw.emp",)]},
    )
    indebidas = cliente.lecturas_indebidas(ROL, [RESTR, "raw"], ["raw.emp"])  # type: ignore[attr-defined]
    assert indebidas == ["raw (USAGE)", "raw.apu (SELECT)", "raw.emp (SELECT)"]
    (sql_esq, p_esq), (sql_tab, p_tab) = registro
    assert "has_schema_privilege(%s, n.oid, 'USAGE')" in sql_esq
    assert p_esq == ([RESTR, "raw"], ROL)
    assert "has_table_privilege(%s, c.oid, 'SELECT')" in sql_tab
    assert "n.nspname = ANY(%s)" in sql_tab and "= ANY(%s)" in sql_tab
    assert p_tab == ([RESTR, "raw"], ["raw.emp"], ROL)
    for s in (sql_esq, sql_tab):
        assert s.lstrip().upper().startswith("SELECT"), "solo catálogo, nada que escriba"


def test_f135_cliente_lecturas_indebidas_vacia_si_no_lee_nada() -> None:
    cliente, _ = _cliente(["raw"], {"esquemas": [], "tablas": []})
    assert cliente.lecturas_indebidas(ROL, ["raw"], []) == []  # type: ignore[attr-defined]


def test_f135_cliente_la_consulta_de_tablas_cubre_todas_las_clases() -> None:
    """Tablas, vistas, materializadas, particionadas y foráneas: todo lo que se lee."""
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_LECTURAS_TABLAS

    assert "c.relkind IN ('r', 'v', 'm', 'p', 'f')" in re.sub(r"\s+", " ", SQL_LECTURAS_TABLAS)


# ===========================================================================
# El paso (T8)
# ===========================================================================


class _ClienteFalso:
    """Cliente de mentira: apunta lo que se le pide."""

    def __init__(
        self,
        existen: tuple[str, ...] = (ROL, AUTORIZADO),
        indebidas: list[str] | None = None,
        falla: bool = False,
    ) -> None:
        self.existen = existen
        self.indebidas = indebidas or []
        self.falla = falla
        self.llamadas: list[tuple] = []

    def role_exists(self, role: str) -> bool:
        self.llamadas.append(("role_exists", role))
        return role in self.existen

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):  # noqa: ANN001, ANN201
        self.llamadas.append(("general", readonly_role, owner_role, list(schemas),
                              list(excluded_tables), list(vetoed_schemas)))
        if self.falla:
            raise RuntimeError("se cayó la conexión")
        return ["G1", "G2"]

    def apply_restricted_grants(self, role, owner_role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("autorizado", role, owner_role, list(schemas)))
        return ["A1"]

    def lecturas_indebidas(self, role, schemas, tables):  # noqa: ANN001, ANN201
        self.llamadas.append(("verifica", role, list(schemas), list(tables)))
        return list(self.indebidas)


def _settings(**pg: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "readonly_role": ROL,
        "set_role": DUENO,
        "consumption_schema_list": ["mart", "contabilidad"],
        "excluded_table_list": ["raw.emp"],
        "vetoed_schema_list": [RESTR, "raw"],
        "restricted_role": AUTORIZADO,
        "restricted_schema_list": [RESTR],
        # F-136: sin login total, el paso es el de F-135 tal cual
        "total_role": "",
        "total_vetoed_schema_list": ["raw"],
    }
    base.update(pg)
    return SimpleNamespace(postgres=SimpleNamespace(**base))


def test_f135_paso_camino_normal_en_orden() -> None:
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(_settings(), client=cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    assert cliente.llamadas == [
        ("role_exists", ROL),
        ("general", ROL, DUENO, ["mart", "contabilidad"], ["raw.emp"], [RESTR, "raw"]),
        ("role_exists", AUTORIZADO),
        ("autorizado", AUTORIZADO, DUENO, [RESTR]),
        ("verifica", ROL, [RESTR, "raw"], ["raw.emp"]),
    ]
    assert resultado.rows_processed == 3
    assert resultado.metadata["vetados"] == [RESTR, "raw"]
    assert resultado.metadata["rol_autorizado"] == AUTORIZADO
    assert resultado.metadata["verificacion"] == "ok"
    assert resultado.metadata["esquemas"] == ["mart", "contabilidad"]
    assert resultado.metadata["tablas_excluidas"] == ["raw.emp"]
    assert resultado.finished_at is not None


@pytest.mark.parametrize(
    ("consumo", "esperado"),
    [(["mart", "raw"], "raw"), (["mart", RESTR, "stg"], RESTR)],
)
def test_f135_r17_un_env_viejo_para_en_seco(consumo: list[str], esperado: str) -> None:
    """Un `.env` que aún lista `raw` (ya pasó con `personal`): FAILED, sin
    ejecutar NADA y nombrando el esquema."""
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(_settings(consumption_schema_list=consumo), client=cliente).run()
    assert resultado.status == StepStatus.FAILED
    assert cliente.llamadas == [], "ni una sentencia, ni una pregunta al servidor"
    assert esperado in (resultado.error_message or "")
    assert "PG_CONSUMPTION_SCHEMAS" in (resultado.error_message or "")
    assert resultado.finished_at is not None


def test_f135_r17_un_esquema_restringido_sin_vetar_para_en_seco() -> None:
    """Si el esquema del autorizado no está vetado, el general podría leerlo."""
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(_settings(vetoed_schema_list=["raw"]), client=cliente).run()
    assert resultado.status == StepStatus.FAILED
    assert cliente.llamadas == []
    assert RESTR in (resultado.error_message or "")
    assert "PG_VETOED_SCHEMAS" in (resultado.error_message or "")


def test_f135_r17_sin_rol_general_sigue_siendo_noop() -> None:
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(
        _settings(readonly_role="", consumption_schema_list=["raw"]), client=cliente
    ).run()
    assert resultado.status == StepStatus.SUCCESS
    assert cliente.llamadas == []


def test_f135_r15_sin_rol_autorizado_avisa_y_sigue(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.application.steps import apply_grants_step

    avisos: list[tuple[str, dict]] = []

    class _Log:
        def info(self, *a: object, **k: object) -> None: ...
        def error(self, *a: object, **k: object) -> None: ...
        def warning(self, evento: str, **datos: object) -> None:
            avisos.append((evento, datos))

    monkeypatch.setattr(apply_grants_step, "logger", _Log())
    cliente = _ClienteFalso(existen=(ROL,))
    resultado = ApplyGrantsStep(_settings(), client=cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    assert not any(c[0] == "autorizado" for c in cliente.llamadas)
    assert ("verifica", ROL, [RESTR, "raw"], ["raw.emp"]) in cliente.llamadas, (
        "la verificación corre igual: su ausencia no expone nada, pero hay que comprobarlo"
    )
    assert avisos == [("apply_grants_rol_autorizado_inexistente",
                       {"role": AUTORIZADO, "detalle": "créalo con infra/sql/02_roles.sql"})]
    assert resultado.metadata["rol_autorizado"] == f"{AUTORIZADO} (no existe)"
    assert resultado.rows_processed == 2


def test_f135_r15_rol_autorizado_vacio_no_se_pregunta() -> None:
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(_settings(restricted_role="  "), client=cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    assert ("role_exists", "") not in cliente.llamadas
    assert not any(c[0] == "autorizado" for c in cliente.llamadas)
    assert resultado.metadata["rol_autorizado"] == "(sin configurar)"


def test_f135_r18_si_el_general_lee_algo_vetado_falla_con_la_lista() -> None:
    cliente = _ClienteFalso(indebidas=["raw (USAGE)", "raw.apu (SELECT)"])
    resultado = ApplyGrantsStep(_settings(), client=cliente).run()
    assert resultado.status == StepStatus.FAILED
    mensaje = resultado.error_message or ""
    assert "raw (USAGE)" in mensaje and "raw.apu (SELECT)" in mensaje
    assert ROL in mensaje
    assert "02_roles.sql" in mensaje, "la salida: concesiones de otro concedente (F-068)"
    assert resultado.metadata["verificacion"] == ["raw (USAGE)", "raw.apu (SELECT)"]
    assert resultado.finished_at is not None


def test_f135_paso_rol_general_inexistente_no_verifica_nada() -> None:
    cliente = _ClienteFalso(existen=())
    resultado = ApplyGrantsStep(_settings(), client=cliente).run()
    assert resultado.status == StepStatus.SUCCESS
    assert cliente.llamadas == [("role_exists", ROL)]


def test_f135_paso_un_fallo_del_cliente_es_failed() -> None:
    cliente = _ClienteFalso(falla=True)
    resultado = ApplyGrantsStep(_settings(), client=cliente).run()
    assert resultado.status == StepStatus.FAILED
    assert "se cayó la conexión" in (resultado.error_message or "")
    assert not any(c[0] == "verifica" for c in cliente.llamadas)


def test_f135_paso_sin_listas_a_mano() -> None:
    """Las listas salen de la configuración, nunca escritas en el paso."""
    from etl_sigrid.application.steps import apply_grants_step

    fuente = Path(apply_grants_step.__file__).read_text(encoding="utf-8")
    ejecutable = "\n".join(f for f in fuente.splitlines() if not f.lstrip().startswith("#"))
    for literal in ('"raw"', f'"{RESTR}"', f'"{AUTORIZADO}"'):
        assert literal not in ejecutable
    for campo in ("vetoed_schema_list", "restricted_role", "restricted_schema_list"):
        assert campo in ejecutable


# ===========================================================================
# R20 · infra/sql/02_roles.sql (T9)
# ===========================================================================


def _roles_sql() -> str:
    crudo = (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    return "\n".join(
        linea for linea in crudo.splitlines() if not linea.lstrip().startswith("--")
    )


def test_f135_r20_crea_el_rol_autorizado_nologin_con_connect() -> None:
    sql = _roles_sql()
    assert (
        f"SELECT 'CREATE ROLE {AUTORIZADO} NOLOGIN'\n"
        f"WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{AUTORIZADO}')\n\\gexec"
    ) in sql
    assert f"ALTER ROLE {AUTORIZADO} WITH NOLOGIN NOCREATEDB NOCREATEROLE;" in sql
    assert f"GRANT CONNECT ON DATABASE sigrid_dm TO {AUTORIZADO};" in sql
    assert f"{AUTORIZADO} WITH LOGIN" not in sql and f"{AUTORIZADO} LOGIN" not in sql
    assert "PASSWORD" not in sql.split(f"ROLE {AUTORIZADO}")[1].split(";")[0]


def test_f135_r20_el_bucle_del_general_es_la_lista_de_consumo() -> None:
    from config.settings import DEFAULT_CONSUMPTION_SCHEMAS

    sql = _roles_sql()
    bucle = re.search(r"FOREACH esquema IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert bucle
    concedidos = re.findall(r"'(\w+)'", bucle.group(1))
    assert concedidos == DEFAULT_CONSUMPTION_SCHEMAS.split(","), (
        "el punto 5 concede EXACTAMENTE lo que concede la nocturna"
    )


def test_f135_r20_el_autorizado_recibe_el_esquema_restringido() -> None:
    sql = _roles_sql()
    for sentencia in (
        f"GRANT USAGE ON SCHEMA {RESTR} TO {AUTORIZADO};",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA {RESTR} TO {AUTORIZADO};",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA {RESTR} GRANT SELECT ON TABLES TO {AUTORIZADO};",
    ):
        assert sentencia in sql, f"falta: {sentencia}"


def _bloque_veto(sql: str) -> list[str]:
    """Los dos DO del punto 5 ter: el del administrador y el de sigrid_dm_etl."""
    return re.findall(r"FOREACH vetado IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)


def test_f135_r20_los_vetados_son_los_de_settings_y_con_dos_concedentes() -> None:
    from config.settings import DEFAULT_VETOED_SCHEMAS

    sql = _roles_sql()
    listas = _bloque_veto(sql)
    assert len(listas) == 2, "una vez como administrador y otra como sigrid_dm_etl (F-068)"
    for lista in listas:
        assert re.findall(r"'(\w+)'", lista) == DEFAULT_VETOED_SCHEMAS.split(",")
    tramo_etl = sql.split("SET ROLE sigrid_dm_etl;")[-1]
    assert "FOREACH vetado IN ARRAY ARRAY[" in tramo_etl, "el segundo DO va con SET ROLE sigrid_dm_etl"
    for sentencia in (
        "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM mcp_sigrid_dm_ro",
        "REVOKE ALL PRIVILEGES ON SCHEMA %I FROM mcp_sigrid_dm_ro",
    ):
        assert sql.count(sentencia) == 2, f"«{sentencia}» con los dos concedentes"
    assert sql.count(
        "'ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA %I '\n"
        "                'REVOKE ALL ON TABLES FROM mcp_sigrid_dm_ro'"
    ) == 1


def test_f135_r20_el_veto_dentro_de_la_transaccion_y_tras_los_grant() -> None:
    sql = _roles_sql()
    apertura = sql.index("\nBEGIN;")
    cierre = sql.index("\nCOMMIT;")
    ultimo_grant_general = sql.rindex("GRANT SELECT ON ALL TABLES IN SCHEMA %I TO mcp_sigrid_dm_ro")
    for m in re.finditer(r"FOREACH vetado IN ARRAY", sql):
        assert apertura < m.start() < cierre, "el veto fuera de la transacción"
        assert m.start() > ultimo_grant_general, "el veto antes del GRANT no sirve"


def test_f135_r20_el_veto_solo_sobre_esquemas_que_existen() -> None:
    sql = _roles_sql()
    assert sql.count("IF to_regnamespace(vetado) IS NOT NULL THEN") == 2


def test_f135_r20_crea_el_esquema_restringido_como_dueno() -> None:
    sql = _roles_sql()
    tramo = sql.split("SET ROLE sigrid_dm_etl;", 1)[1].split("RESET ROLE;", 1)[0]
    assert f"CREATE SCHEMA IF NOT EXISTS {RESTR};" in tramo


def test_f135_r20_comprobacion_final() -> None:
    sql = _roles_sql()
    assert (
        "WHERE grantee = 'mcp_sigrid_dm_ro'\n"
        "  AND table_schema IN ('contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw')"  # F-037, F-138
    ) in sql
    assert (
        "SELECT nspname, has_schema_privilege('mcp_sigrid_dm_ro', nspname, 'USAGE') AS lee"
    ) in sql
