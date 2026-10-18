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
    assert ",".join(ESQUEMAS_R) == DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS
    assert ",".join(EXCLUIDAS_R) == DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES
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


# ===========================================================================
# R24 · el nombre retirado no queda en el árbol (T2)
# ===========================================================================

#: lo que R24 deja fuera del barrido: la memoria del arnés, las specs y el backlog
_FUERA_DEL_BARRIDO = ("progress/", "specs/")
_FICHEROS_FUERA = {"harness/features.json", "BACKLOG.md"}


def _ficheros_del_arbol() -> list[str]:
    import subprocess

    salida = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=RAIZ, capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout
    return [
        f for f in salida.splitlines()
        if f and not f.startswith(_FUERA_DEL_BARRIDO) and f not in _FICHEROS_FUERA
    ]


def _con_el_nombre_retirado() -> dict[str, list[str]]:
    hallados: dict[str, list[str]] = {}
    for relativo in _ficheros_del_arbol():
        ruta = RAIZ / relativo
        if not ruta.is_file():  # borrado en el árbol y aún en el índice
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # binarios: no llevan nombres de rol
            continue
        lineas = [linea for linea in texto.splitlines() if RETIRADO in linea]
        if lineas:
            hallados[relativo] = lineas
    return hallados


def test_f141_r24_el_nombre_retirado_solo_en_el_renombre_la_guarda_y_su_test() -> None:
    hallados = _con_el_nombre_retirado()
    permitidos = {"infra/sql/02_roles.sql", "config/settings.py",
                  "tests/test_f141_perfil_restringido.py"}
    assert set(hallados) <= permitidos, sorted(set(hallados) - permitidos)
    assert hallados.get("config/settings.py") == [
        f'NOMBRE_AUTORIZADO_RETIRADO = "{RETIRADO}"'
    ], "en settings solo la constante de la guarda R3"


def test_f141_r20_r24_en_02_roles_solo_dentro_del_renombre() -> None:
    texto = (RAIZ / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    desde = texto.rindex("\\getenv")
    hasta = texto.index("SELECT 'CREATE ROLE")
    posiciones = [i for i in range(len(texto)) if texto.startswith(RETIRADO, i)]
    assert posiciones, "el renombre tiene que nombrar el rol viejo"
    assert all(desde < p < hasta for p in posiciones), (
        "solo entre la carga de variables y el primer CREATE ROLE: el renombre y su guarda"
    )


# ===========================================================================
# T3 · grants.py: constantes y funciones puras
# ===========================================================================


def test_f141_grants_excepciones_nominales_de_d4() -> None:
    from etl_sigrid.infrastructure.postgres import grants

    assert {v: "tesoreria" for v in EXCEPCIONES} == grants.EXCEPCIONES_FILTRACION_RESTRINGIDO
    assert grants.PATRON_VIGILADO_RESTRINGIDO == "mayor"
    assert grants.ESQUEMAS_ORIGEN_DE_VISTAS == ("raw",)


def _cuerpo_de_vista(sql: str, vista: str) -> str:
    """El texto de `CREATE ... VIEW <vista> AS` hasta su `;` final, sin comentarios."""
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in sql.splitlines())
    inicio = sin_comentarios.index(f"VIEW {vista} AS")
    return sin_comentarios[inicio:sin_comentarios.index(";", inicio)]


_SQL_COMPRAS = RAIZ / "etl_sigrid" / "infrastructure" / "postgres" / "sql" / "compras"


def test_f141_excepciones_vivas_vencimientos_lee_tesoreria() -> None:
    """Si `compras.vencimientos` deja de leer la cartera, la excepción sobra (D4)."""
    sql = (_SQL_COMPRAS / "05_vencimientos.sql").read_text(encoding="utf-8")
    assert "FROM tesoreria." in _cuerpo_de_vista(sql, "compras.vencimientos")


def test_f141_excepciones_vivas_las_dos_de_pago_leen_vencimientos() -> None:
    sql = (_SQL_COMPRAS / "06_pago_factura.sql").read_text(encoding="utf-8")
    assert "compras.vencimientos" in _cuerpo_de_vista(sql, "compras.v_facturas_pago")
    assert "compras.v_facturas_pago" in _cuerpo_de_vista(sql, "compras.v_control_forma_pago"), (
        "v_control_forma_pago llega a la cartera por v_facturas_pago"
    )


def test_f141_excepciones_vivas_ninguna_otra_vista_de_compras_lee_la_cartera() -> None:
    """La lista nominal es exacta: otra vista que lea la cartera no está exceptuada."""
    import re

    lectoras: set[str] = set()
    for fichero in sorted(_SQL_COMPRAS.glob("*.sql")):
        sql = "\n".join(linea.split("--", 1)[0] for linea in
                        fichero.read_text(encoding="utf-8").splitlines())
        for m in re.finditer(r"VIEW\s+(compras\.\w+)\s+AS(.*?);", sql, re.DOTALL):
            if re.search(r"(tesoreria\.|compras\.vencimientos\b|compras\.v_facturas_pago\b)",
                         m.group(2)):
                lectoras.add(m.group(1))
    assert lectoras == set(EXCEPCIONES)


def test_f141_grants_tablas_origen_de_adjuntos_casan_con_f139() -> None:
    from etl_sigrid.infrastructure.postgres import grants
    from tests.test_f139_limite import ORIGEN_POR_FAMILIA

    assert tuple(
        f"compras.{tabla}" for tabla, _ in ORIGEN_POR_FAMILIA.values()
    ) == grants.TABLAS_ORIGEN_ADJUNTOS
    assert grants.OBJETO_ADJUNTOS == "compras.documento_adjuntos"


# --- R5 · perfil_restringido_en_conflicto -----------------------------------

_VETADOS = ["contabilidad_restringida", "tesoreria_restringida", "compras_restringida", "raw"]
_RESTRINGIDOS = ["contabilidad_restringida", "tesoreria_restringida", "compras_restringida"]


def _conflicto(esquemas: list[str], **cambios: list[str]) -> list[str]:
    from etl_sigrid.infrastructure.postgres.grants import perfil_restringido_en_conflicto

    listas = {
        "consumo": [*ESQUEMAS_R, "tesoreria", "personal"],
        "vetados": _VETADOS,
        "restringidos": _RESTRINGIDOS,
        "total_vetados": ["raw"],
    }
    listas.update(cambios)
    return perfil_restringido_en_conflicto(esquemas, **listas)


def test_f141_grants_r5_los_defectos_no_chocan() -> None:
    assert _conflicto(ESQUEMAS_R) == []


@pytest.mark.parametrize(
    ("extra", "cambios"),
    [
        ("otro", {}),  # fuera del consumo
        ("raw", {"consumo": [*ESQUEMAS_R, "raw"]}),  # vetado al estándar
        ("compras_restringida", {"consumo": [*ESQUEMAS_R, "compras_restringida"],
                                 "vetados": ["raw"]}),  # de lo restringido
        ("stg2", {"consumo": [*ESQUEMAS_R, "stg2"], "total_vetados": ["raw", "stg2"]}),
    ],
    ids=["fuera-del-consumo", "vetado", "restringido", "vetado-al-total"],
)
def test_f141_grants_r5_cada_lista_que_choca(extra: str, cambios: dict) -> None:
    assert _conflicto([*ESQUEMAS_R, extra, extra], **cambios) == [extra], (
        "en orden y sin repetir, solo los que chocan"
    )


# --- R7 · objetos excluidos mal escritos o fuera de lo concedido -----------


def test_f141_grants_r7_excluidas_invalidas() -> None:
    from etl_sigrid.infrastructure.postgres.grants import excluidas_invalidas

    assert excluidas_invalidas(EXCLUIDAS_R, ESQUEMAS_R) == []
    assert excluidas_invalidas(
        ["contabilidad.mayor", "mayor", "a.b.c", ".x", "tesoreria.efectos", "mayor"], ESQUEMAS_R,
    ) == ["mayor", "a.b.c", ".x", "tesoreria.efectos"]
    assert excluidas_invalidas([], []) == []


# --- R8 · F-139 D1: los adjuntos no se leen sin sus documentos de origen ---


def test_f141_grants_r8_origenes_de_adjuntos() -> None:
    from etl_sigrid.infrastructure.postgres.grants import origenes_de_adjuntos_sin_leer

    assert origenes_de_adjuntos_sin_leer(ESQUEMAS_R, EXCLUIDAS_R) == []
    assert origenes_de_adjuntos_sin_leer(ESQUEMAS_R, [*EXCLUIDAS_R, "compras.facturas"]) == [
        "compras.facturas"
    ]
    sin_compras = [s for s in ESQUEMAS_R if s != "compras"]
    assert origenes_de_adjuntos_sin_leer(sin_compras, []) == [
        "compras.facturas", "compras.contratos", "compras.comparativos",
        "compras.comparativo_ofertas", "compras.albaranes",
    ]
    assert origenes_de_adjuntos_sin_leer(
        ESQUEMAS_R, ["compras.facturas", "compras.documento_adjuntos"]
    ) == [], "excluir también los adjuntos cumple la regla"


# --- R12 · lo que no es suyo sale del CATÁLOGO -----------------------------


def test_f141_grants_r12_esquemas_ajenos_del_catalogo() -> None:
    from etl_sigrid.infrastructure.postgres.grants import esquemas_ajenos

    catalogo = [*ESQUEMAS_R, "tesoreria", "personal", "raw", "contabilidad_restringida", "pg_catalog", "information_schema", "pg_toast", "pg_temp_3", "pg_toast_temp_3", "public", "nuevo", "tesoreria"]
    assert esquemas_ajenos(catalogo, ESQUEMAS_R) == [
        "contabilidad_restringida", "nuevo", "personal", "raw", "tesoreria",
    ], "ordenados, sin repetir y sin los del sistema"


# --- R13 y R15 · las tres excepciones de D4 --------------------------------


def test_f141_grants_r13_separar_excepciones() -> None:
    from etl_sigrid.infrastructure.postgres.grants import separar_excepciones

    filas = [
        ("compras.vencimientos", "tesoreria.efectos"),
        ("compras.v_facturas_pago", "tesoreria.efectos"),
        ("compras.v_control_forma_pago", "tesoreria.efectos"),
        ("compras.vencimientos", "personal.recursos"),  # la excepción NO cubre otro esquema
        ("mart.v_nueva", "tesoreria.efectos"),
    ]
    filtraciones, sobrantes = separar_excepciones(filas)
    assert filtraciones == [
        ("compras.vencimientos", "personal.recursos"), ("mart.v_nueva", "tesoreria.efectos"),
    ]
    assert sobrantes == []


def test_f141_grants_r15_excepcion_sobrante() -> None:
    from etl_sigrid.infrastructure.postgres.grants import separar_excepciones

    filtraciones, sobrantes = separar_excepciones([
        ("compras.vencimientos", "tesoreria.efectos"),
        ("compras.v_facturas_pago", "personal.x"),
        ("compras.v_control_forma_pago", "tesoreria_restringida.efectos"),
    ])
    assert filtraciones == [
        ("compras.v_facturas_pago", "personal.x"),
        ("compras.v_control_forma_pago", "tesoreria_restringida.efectos"),
    ], "la excepción es el ESQUEMA exacto, no un prefijo"
    assert sobrantes == ["compras.v_control_forma_pago", "compras.v_facturas_pago"], (
        "leer otra cosa no es leer la cartera: sobra igual"
    )
    assert separar_excepciones([]) == ([], sorted(EXCEPCIONES))


# --- R11 · build_perfil_restringido_statements -----------------------------


def test_f141_r11_build_sentencias_en_orden() -> None:
    from etl_sigrid.infrastructure.postgres.grants import build_perfil_restringido_statements

    sentencias = build_perfil_restringido_statements(
        GRUPO, DUENO, ["mart", "contabilidad"], database="sigrid_dm",
        excluded=["contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "mart.v_x",
                  "contabilidad.mayor", "otro.y"],
        missing=["contabilidad.saldos_cuenta_mes"],
    )
    assert sentencias == [
        f'GRANT CONNECT ON DATABASE "sigrid_dm" TO "{GRUPO}"',
        f'GRANT USAGE ON SCHEMA "mart" TO "{GRUPO}"',
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "mart" TO "{GRUPO}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "mart" '
        f'REVOKE SELECT ON TABLES FROM "{GRUPO}"',
        f'GRANT USAGE ON SCHEMA "contabilidad" TO "{GRUPO}"',
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "contabilidad" TO "{GRUPO}"',
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "contabilidad" '
        f'REVOKE SELECT ON TABLES FROM "{GRUPO}"',
        f'REVOKE ALL PRIVILEGES ON TABLE "contabilidad"."mayor" FROM "{GRUPO}"',
        f'REVOKE ALL PRIVILEGES ON TABLE "mart"."v_x" FROM "{GRUPO}"',
    ], "los REVOKE al final, sin repetir, sin los ausentes ni los de esquemas no concedidos"


def test_f141_r11_build_sin_dueno_ni_base() -> None:
    from etl_sigrid.infrastructure.postgres.grants import build_perfil_restringido_statements

    assert build_perfil_restringido_statements(GRUPO, "", ["mart"]) == [
        f'GRANT USAGE ON SCHEMA "mart" TO "{GRUPO}"',
        f'GRANT SELECT ON ALL TABLES IN SCHEMA "mart" TO "{GRUPO}"',
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA "mart" REVOKE SELECT ON TABLES FROM "{GRUPO}"',
    ]
    assert build_perfil_restringido_statements(GRUPO, DUENO, []) == []


def test_f141_r11_build_nunca_un_grant_por_defecto_ni_escritura() -> None:
    from etl_sigrid.infrastructure.postgres.grants import build_perfil_restringido_statements

    sentencias = build_perfil_restringido_statements(
        GRUPO, DUENO, ESQUEMAS_R, database="sigrid_dm", excluded=EXCLUIDAS_R,
    )
    for s in sentencias:
        assert "GRANT SELECT ON TABLES" not in s, "lo que nazca no lo lee hasta la comprobación"
        for palabra in ("INSERT", "UPDATE", "DELETE", "CREATE", "ALL PRIVILEGES"):
            assert not (s.startswith("GRANT") and palabra in s), s
    assert len(sentencias) == 1 + 3 * len(ESQUEMAS_R) + 2


def test_f141_r11_build_una_excluida_mal_escrita_revienta() -> None:
    from etl_sigrid.infrastructure.postgres.grants import build_perfil_restringido_statements

    with pytest.raises(ValueError, match="mal declarada"):
        build_perfil_restringido_statements(GRUPO, DUENO, ["mart"], excluded=["mayor"])


# ===========================================================================
# T4 · PostgresClient: con conexión simulada, sin BBDD
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


def _cliente(
    esquemas: list[str] | None = None,
    filas: list | None = None,
    tablas: set[str] | None = None,
) -> tuple[object, list, list]:
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    registro: list = []
    aperturas: list = []
    cliente = PostgresClient.__new__(PostgresClient)
    cliente._target_db = "sigrid_dm"  # type: ignore[attr-defined]
    cliente.list_schemas = lambda: list(esquemas or [])  # type: ignore[method-assign]
    cliente.connection = lambda: _Conn(registro, filas or [], aperturas)  # type: ignore[method-assign]
    existentes = tablas if tablas is not None else set()
    cliente.table_exists = lambda e, t: f"{e}.{t}" in existentes  # type: ignore[method-assign]
    return cliente, registro, aperturas


def _plano(texto: str) -> str:
    return " ".join(texto.split())


def test_f141_cliente_vistas_que_filtran_pregunta_al_catalogo() -> None:
    cliente, registro, _ = _cliente(filas=[("compras.vencimientos", "tesoreria.efectos")])
    filas = cliente.vistas_que_filtran(  # type: ignore[attr-defined]
        ["compras", "mart"], ["tesoreria", "personal"], EXCLUIDAS_R,
    )
    assert filas == [("compras.vencimientos", "tesoreria.efectos")]
    ((sql, params),) = registro
    assert params == (["compras", "mart"], ["tesoreria", "personal"], EXCLUIDAS_R)
    plano = _plano(sql)
    assert plano.startswith("WITH RECURSIVE") and plano.endswith("ORDER BY 1, 2"), "solo catálogo"


def test_f141_cliente_sql_vistas_que_filtran_es_la_clausura_del_diseno() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_VISTAS_QUE_FILTRAN

    plano = _plano(SQL_VISTAS_QUE_FILTRAN)
    for trozo in (
        "FROM pg_rewrite r JOIN pg_depend d ON d.classid = 'pg_rewrite'::regclass",
        "AND d.objid = r.oid AND d.refclassid = 'pg_class'::regclass",
        "AND d.refobjid <> r.ev_class",  # la regla depende de su propia vista
        "WHERE nvis.nspname = ANY(%s) UNION SELECT a.vista, l.objeto FROM alcance a "
        "JOIN lecturas l ON l.vista = a.objeto",  # vista sobre vista
        "WHERE nobj.nspname = ANY(%s) OR nobj.nspname || '.' || obj.relname = ANY(%s)",
    ):
        assert trozo in plano, trozo
    for escritura in ("INSERT", "UPDATE", "DELETE", "GRANT", "REVOKE"):
        assert escritura not in plano


def test_f141_cliente_vistas_que_filtran_sin_esquemas_no_abre_conexion() -> None:
    cliente, registro, aperturas = _cliente(filas=[("x.y", "z.w")])
    assert cliente.vistas_que_filtran([], ["tesoreria"], []) == []  # type: ignore[attr-defined]
    assert registro == [] and aperturas == []


def test_f141_cliente_objetos_vigilados() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_OBJETOS_VIGILADOS

    cliente, registro, _ = _cliente(filas=[("contabilidad.mayor",)])
    assert cliente.objetos_vigilados(["contabilidad"], "mayor") == [  # type: ignore[attr-defined]
        "contabilidad.mayor"
    ]
    assert registro == [(SQL_OBJETOS_VIGILADOS, (["contabilidad"], "mayor"))]
    assert _plano(SQL_OBJETOS_VIGILADOS) == (
        "SELECT n.nspname || '.' || c.relname FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f') AND n.nspname = ANY(%s) "
        "AND c.relname ~* %s ORDER BY 1"
    )


def test_f141_cliente_objetos_vigilados_sin_esquemas_no_abre_conexion() -> None:
    cliente, registro, aperturas = _cliente(filas=[("x.mayor",)])
    assert cliente.objetos_vigilados([], "mayor") == []  # type: ignore[attr-defined]
    assert registro == [] and aperturas == []


def test_f141_cliente_pertenencias() -> None:
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_PERTENENCIAS

    cliente, registro, _ = _cliente(filas=[(GRUPO,), (ESTANDAR,)])
    assert cliente.pertenencias(LOGIN) == [GRUPO, ESTANDAR]  # type: ignore[attr-defined]
    assert registro == [(SQL_PERTENENCIAS, (LOGIN,))]
    assert _plano(SQL_PERTENENCIAS) == (
        "SELECT DISTINCT g.rolname FROM pg_auth_members m "
        "JOIN pg_roles g ON g.oid = m.roleid JOIN pg_roles u ON u.oid = m.member "
        "WHERE u.rolname = %s ORDER BY 1"
    ), "los roles de los que ES miembro, no sus miembros (el administrador lo es del grupo)"


def test_f141_cliente_apply_perfil_restringido_solo_lo_que_existe() -> None:
    from etl_sigrid.infrastructure.postgres import grants

    cliente, registro, _ = _cliente(
        esquemas=["mart", "contabilidad", "tesoreria"],
        tablas={"contabilidad.mayor", "mart.v_x"},
    )
    sentencias = cliente.apply_perfil_restringido(  # type: ignore[attr-defined]
        GRUPO, DUENO, ["mart", "contabilidad", "fantasma"],
        ["contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "mart.v_x", "fantasma.t"],
    )
    assert sentencias == grants.build_perfil_restringido_statements(
        GRUPO, DUENO, ["mart", "contabilidad"], database="sigrid_dm",
        excluded=["contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "mart.v_x",
                  "fantasma.t"],
        missing=["contabilidad.saldos_cuenta_mes"],
    )
    assert [s for s, _ in registro] == sentencias, "ejecuta exactamente lo que devuelve"
    assert sentencias[-2:] == [
        f'REVOKE ALL PRIVILEGES ON TABLE "contabilidad"."mayor" FROM "{GRUPO}"',
        f'REVOKE ALL PRIVILEGES ON TABLE "mart"."v_x" FROM "{GRUPO}"',
    ]


def test_f141_cliente_apply_perfil_restringido_lo_anota(monkeypatch: pytest.MonkeyPatch) -> None:
    from etl_sigrid.infrastructure.postgres import postgres_client

    anotado: list[tuple[str, dict]] = []

    class _Log:
        def info(self, evento: str, **datos: object) -> None:
            anotado.append((evento, datos))

        def warning(self, evento: str, **datos: object) -> None:
            anotado.append((evento, datos))

    monkeypatch.setattr(postgres_client, "logger", _Log())
    cliente, _, _ = _cliente(esquemas=["mart"], tablas=set())
    cliente.apply_perfil_restringido(GRUPO, DUENO, ["mart", "otro"], ["mart.t"])  # type: ignore[attr-defined]
    assert anotado == [
        ("grants_perfil_restringido_esquemas_inexistentes", {"role": GRUPO, "schemas": ["otro"]}),
        ("grants_perfil_restringido_aplicados",
         {"role": GRUPO, "schemas": ["mart"], "revocados": [], "ausentes": ["mart.t"],
          "statements": 4}),
    ]


def test_f141_cliente_apply_perfil_restringido_anota_lo_revocado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Superviviente 4 de la campaña de mutación: el log nombra lo que SÍ se revoca."""
    from etl_sigrid.infrastructure.postgres import postgres_client

    anotado: list[tuple[str, dict]] = []

    class _Log:
        def info(self, evento: str, **datos: object) -> None:
            anotado.append((evento, datos))

        def warning(self, evento: str, **datos: object) -> None:
            anotado.append((evento, datos))

    monkeypatch.setattr(postgres_client, "logger", _Log())
    cliente, _, _ = _cliente(esquemas=["mart", "contabilidad"], tablas={"contabilidad.mayor"})
    cliente.apply_perfil_restringido(  # type: ignore[attr-defined]
        GRUPO, DUENO, ["mart", "contabilidad"],
        ["contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "otro.t"],
    )
    ((evento, datos),) = anotado
    assert evento == "grants_perfil_restringido_aplicados"
    assert datos["revocados"] == ["contabilidad.mayor"], "el existente, de un esquema concedido"
    assert datos["ausentes"] == ["contabilidad.saldos_cuenta_mes"]


def test_f141_cliente_apply_perfil_restringido_sin_esquemas_no_abre_conexion() -> None:
    cliente, registro, aperturas = _cliente(esquemas=["mart"])
    assert cliente.apply_perfil_restringido(GRUPO, DUENO, ["otro"], []) == [  # type: ignore[attr-defined]
    ], "sin esquemas existentes no hay nada que conceder (ni siquiera CONNECT)"
    assert registro == [] and aperturas == []


# ===========================================================================
# El paso (T5-T6): cliente falso que apunta lo que se le pide
# ===========================================================================

RESTR_C = "contabilidad_restringida"
#: lo que hoy hay en el catálogo (informe del spec-author §1-§2) más el sistema
CATALOGO = [*ESQUEMAS_R, "tesoreria", "personal", "raw", RESTR_C, "tesoreria_restringida", "compras_restringida", "public", "pg_catalog", "information_schema", "pg_toast"]
AJENOS = ["compras_restringida", RESTR_C, "personal", "raw", "tesoreria",
          "tesoreria_restringida"]
#: lo que hoy devuelve la clausura en Azure (informe §9-§10): solo las tres de D4
FILAS_HOY = [(v, "tesoreria.efectos") for v in EXCEPCIONES]


class _ClienteFalso:
    def __init__(
        self,
        existen: tuple[str, ...] = (ESTANDAR, AUTORIZADO, TOTAL, GRUPO, LOGIN),
        filas: list[tuple[str, str]] | None = None,
        vigilados: list[str] | None = None,
        indebidas: dict[str, list[str]] | None = None,
        pertenencias: dict[str, list[str]] | None = None,
        sin_usage: dict[str, list[str]] | None = None,
        falla_en: str = "",
    ) -> None:
        self.existen = existen
        self.filas = FILAS_HOY if filas is None else filas
        self.vigilados = ["contabilidad.mayor"] if vigilados is None else vigilados
        self.indebidas = indebidas or {}
        self.pert = {LOGIN: [GRUPO]} if pertenencias is None else pertenencias
        self.sin_usage = sin_usage or {}
        self.falla_en = falla_en
        self.llamadas: list[tuple] = []

    def _quizas_falla(self, que: str) -> None:
        if self.falla_en == que:
            raise RuntimeError(f"se cayó la conexión en {que}")

    def role_exists(self, role):
        self.llamadas.append(("role_exists", role))
        return role in self.existen

    def list_schemas(self):
        self.llamadas.append(("catalogo",))
        return list(CATALOGO)

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):
        self.llamadas.append(("general", readonly_role))
        return ["G1", "G2"]

    def apply_restricted_grants(self, role, owner_role, schemas):
        self.llamadas.append(("autorizado", role))
        return ["A1"]

    def apply_veto(self, role, owner_role, schemas):
        self.llamadas.append(("veto", role, owner_role, list(schemas)))
        return ["V"] * len(list(schemas))

    def lecturas_indebidas(self, role, schemas, tables):
        self.llamadas.append(("verifica", role, list(schemas), list(tables)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):
        self.llamadas.append(("usage", role, list(schemas)))
        return list(self.sin_usage.get(role, []))

    def vistas_que_filtran(self, schemas, foreign_schemas, tables):
        self.llamadas.append(("filtran", list(schemas), list(foreign_schemas), list(tables)))
        self._quizas_falla("filtran")
        return list(self.filas)

    def objetos_vigilados(self, schemas, pattern):
        self.llamadas.append(("vigilados", list(schemas), pattern))
        return list(self.vigilados)

    def pertenencias(self, role):
        self.llamadas.append(("pertenencias", role))
        return list(self.pert.get(role, []))

    def apply_perfil_restringido(self, role, owner_role, schemas, revoked):
        self.llamadas.append(("perfil", role, owner_role, list(schemas), list(revoked)))
        return ["R1", "R2", "R3"]


def _settings(**pg: object):
    from types import SimpleNamespace

    base: dict[str, object] = {
        "readonly_role": ESTANDAR,
        "set_role": DUENO,
        "consumption_schema_list": [*ESQUEMAS_R, "tesoreria", "personal"],
        "excluded_table_list": ["raw.emp"],
        "vetoed_schema_list": [RESTR_C, "tesoreria_restringida", "compras_restringida", "raw"],
        "restricted_role": AUTORIZADO,
        "restricted_schema_list": [RESTR_C, "tesoreria_restringida", "compras_restringida"],
        "total_role": TOTAL,
        "total_vetoed_schema_list": ["raw"],
        "perfil_restringido_group": GRUPO,
        "perfil_restringido_login": LOGIN,
        "perfil_restringido_schema_list": list(ESQUEMAS_R),
        "perfil_restringido_excluded_table_list": list(EXCLUIDAS_R),
    }
    base.update(pg)
    return SimpleNamespace(postgres=SimpleNamespace(**base))


def _paso(cliente: _ClienteFalso, **pg: object):
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


def _para_en_seco(cliente: _ClienteFalso, resultado: object) -> str:
    assert resultado.status.name == "FAILED"  # type: ignore[attr-defined]
    assert cliente.llamadas == [], "ni una sentencia, ni una pregunta al servidor"
    assert resultado.finished_at is not None  # type: ignore[attr-defined]
    mensaje = resultado.error_message or ""  # type: ignore[attr-defined]
    assert "no se ha ejecutado nada" in mensaje
    return mensaje


# --- R3 · el nombre retirado ------------------------------------------------


def test_f141_r3_el_nombre_retirado_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(cliente, restricted_role=f" {RETIRADO} "))
    assert "PG_RESTRICTED_ROLE" in mensaje and RETIRADO in mensaje
    assert AUTORIZADO in mensaje and "F-141" in mensaje, "dice cuál es el nombre nuevo"


def test_f141_r3_tambien_sin_perfil_restringido() -> None:
    """La guarda es del AUTORIZADO: vale aunque el perfil restringido no esté configurado."""
    cliente = _ClienteFalso()
    _para_en_seco(cliente, _paso(cliente, restricted_role=RETIRADO,
                                 perfil_restringido_group=""))


# --- R4 · el grupo y el login, roles propios --------------------------------


@pytest.mark.parametrize(
    ("campo", "valor", "variable"),
    [
        ("perfil_restringido_group", ESTANDAR, "PG_READONLY_ROLE"),
        ("perfil_restringido_group", AUTORIZADO, "PG_RESTRICTED_ROLE"),
        ("perfil_restringido_group", TOTAL, "PG_TOTAL_ROLE"),
        ("perfil_restringido_group", DUENO, "PG_SET_ROLE"),
        ("perfil_restringido_login", ESTANDAR, "PG_READONLY_ROLE"),
        ("perfil_restringido_login", AUTORIZADO, "PG_RESTRICTED_ROLE"),
        ("perfil_restringido_login", TOTAL, "PG_TOTAL_ROLE"),
        ("perfil_restringido_login", DUENO, "PG_SET_ROLE"),
        ("perfil_restringido_login", GRUPO, "PG_PERFIL_RESTRINGIDO_GROUP"),
    ],
)
def test_f141_r4_grupo_o_login_igual_a_otro_rol_para_en_seco(
    campo: str, valor: str, variable: str,
) -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(cliente, **{campo: f" {valor} "}))
    propia = "PG_PERFIL_RESTRINGIDO_" + campo.removeprefix("perfil_restringido_").upper()
    assert f"{propia} ('{valor}') coincide con {variable}" in mensaje


def test_f141_r4_vacios_no_chocan_entre_si() -> None:
    """Un dueño, un total o un login vacíos no son «el mismo rol»."""
    cliente = _ClienteFalso()
    resultado = _paso(cliente, set_role="", total_role="", perfil_restringido_login="")
    assert resultado.status.name == "SUCCESS"


# --- R5-R8 · la configuración del perfil -----------------------------------


def test_f141_r5_esquemas_que_no_puede_tener_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(
        cliente, perfil_restringido_schema_list=[*ESQUEMAS_R, "raw", "nuevo"],
    ))
    assert "PG_PERFIL_RESTRINGIDO_SCHEMAS" in mensaje and "(raw, nuevo)" in mensaje


def test_f141_r5_tesoreria_entera_tambien() -> None:
    """Dársela es configuración válida del consumo, pero sigue en el consumo: no choca."""
    cliente = _ClienteFalso(filas=[])
    resultado = _paso(cliente, perfil_restringido_schema_list=[*ESQUEMAS_R, "tesoreria"])
    assert resultado.status.name == "SUCCESS", "R5 mira el consumo y los vetos, no la regla"


def test_f141_r6_sin_meta_para_en_seco() -> None:
    cliente = _ClienteFalso()
    sin_meta = [s for s in ESQUEMAS_R if s != "_meta"]
    mensaje = _para_en_seco(cliente, _paso(cliente, perfil_restringido_schema_list=sin_meta))
    assert "_meta" in mensaje and "diccionario" in mensaje


@pytest.mark.parametrize("mala", ["mayor", "tesoreria.efectos", "a.b.c"])
def test_f141_r7_excluida_mal_escrita_o_ajena_para_en_seco(mala: str) -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(
        cliente, perfil_restringido_excluded_table_list=[*EXCLUIDAS_R, mala],
    ))
    assert "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES" in mensaje and f"({mala})" in mensaje


def test_f141_r8_un_origen_de_adjuntos_excluido_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(
        cliente, perfil_restringido_excluded_table_list=[*EXCLUIDAS_R, "compras.contratos"],
    ))
    assert "compras.documento_adjuntos" in mensaje and "(compras.contratos)" in mensaje
    assert "F-139" in mensaje


def test_f141_r8_excluyendo_tambien_los_adjuntos_pasa() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_restringido_excluded_table_list=[*EXCLUIDAS_R, "compras.contratos", "compras.documento_adjuntos"])
    assert resultado.status.name == "SUCCESS"


def test_f141_r3_r8_sin_rol_estandar_ni_siquiera_mira_las_guardas() -> None:
    """Desarrollo local: sin PG_READONLY_ROLE el paso es un no-op, como desde F-005."""
    cliente = _ClienteFalso()
    resultado = _paso(cliente, readonly_role="", restricted_role=RETIRADO,
                      perfil_restringido_group=ESTANDAR)
    assert resultado.status.name == "SUCCESS" and cliente.llamadas == []


def test_f141_r4_r8_sin_grupo_no_mira_su_configuracion() -> None:
    """Grupo vacío: nada del restringido, tampoco sus guardas (R9)."""
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_restringido_group="  ", perfil_restringido_login=ESTANDAR,
                      perfil_restringido_schema_list=["raw"])
    assert resultado.status.name == "SUCCESS"


# --- R9-R19 · el bloque del restringido (T6) --------------------------------

_SIN_RAW = [s for s in AJENOS if s != "raw"]
#: lo de antes, tal cual: estándar, autorizado, total y la postcondición del estándar
_CAMINO_ANTERIOR = [
    ("role_exists", ESTANDAR),
    ("general", ESTANDAR),
    ("role_exists", AUTORIZADO),
    ("autorizado", AUTORIZADO),
    ("role_exists", TOTAL),
    ("veto", TOTAL, DUENO, ["raw"]),
    ("verifica", TOTAL, ["raw"], ["raw.emp"]),
    ("usage", TOTAL, [*ESQUEMAS_R, "tesoreria", "personal", RESTR_C, "tesoreria_restringida", "compras_restringida"]),
    ("verifica", ESTANDAR, [RESTR_C, "tesoreria_restringida", "compras_restringida", "raw"],
     ["raw.emp"]),
]


def _claves_restringido(resultado: object) -> dict:
    return {k: v for k, v in resultado.metadata.items()  # type: ignore[attr-defined]
            if k.endswith("_restringido") or k == "excepciones_sobrantes"}


def test_f141_r11_r12_camino_normal_en_orden_y_el_ultimo(log: _Log) -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", resultado.error_message
    assert cliente.llamadas == [*_CAMINO_ANTERIOR, ("role_exists", GRUPO), ("role_exists", LOGIN), ("catalogo",), ("filtran", ESQUEMAS_R, _SIN_RAW, EXCLUIDAS_R), ("vigilados", ESQUEMAS_R, "mayor"), ("perfil", GRUPO, DUENO, ESQUEMAS_R, EXCLUIDAS_R), ("veto", GRUPO, DUENO, AJENOS), ("verifica", GRUPO, AJENOS, EXCLUIDAS_R), ("verifica", LOGIN, AJENOS, EXCLUIDAS_R), ("pertenencias", LOGIN), ("pertenencias", GRUPO), ("usage", LOGIN, ESQUEMAS_R)], "el bloque del restringido es el ÚLTIMO; al login no se le concede nada"
    assert _claves_restringido(resultado) == {
        "rol_restringido": GRUPO,
        "login_restringido": LOGIN,
        "verificacion_restringido": "ok",
        "filtraciones_restringido": "ok",
        "vigilados_restringido": "ok",
        "pertenencias_restringido": "ok",
        "acceso_restringido": "ok",
        "excepciones_sobrantes": "ok",
    }
    assert log.avisos == []


def test_f141_r19_rows_processed_suma_las_del_restringido() -> None:
    resultado = _paso(_ClienteFalso())
    assert resultado.rows_processed == 2 + 1 + 1 + 3 + len(AJENOS)


def test_f141_r9_sin_grupo_no_se_toca_nada(log: _Log) -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_restringido_group="")
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == _CAMINO_ANTERIOR
    assert _claves_restringido(resultado) == {
        "rol_restringido": "(sin configurar)",
        **{k: "no aplica" for k in ("login_restringido", "verificacion_restringido",
                                    "filtraciones_restringido", "vigilados_restringido",
                                    "pertenencias_restringido", "acceso_restringido",
                                    "excepciones_sobrantes")},
    }
    assert resultado.rows_processed == 2 + 1 + 1
    assert log.avisos == []


def test_f141_r9_una_configuracion_anterior_a_f141_es_sin_configurar() -> None:
    """Sin los campos nuevos (la de un test de F-136, o un objeto viejo): sin configurar."""
    from types import SimpleNamespace

    from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep

    ajustes = vars(_settings().postgres)
    viejos = {k: v for k, v in ajustes.items() if not k.startswith("perfil_restringido")}
    cliente = _ClienteFalso()
    resultado = ApplyGrantsStep(SimpleNamespace(postgres=SimpleNamespace(**viejos)),
                                client=cliente).run()
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == _CAMINO_ANTERIOR
    assert resultado.metadata["rol_restringido"] == "(sin configurar)"


def test_f141_r10_grupo_inexistente_avisa_y_sigue(log: _Log) -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, AUTORIZADO, TOTAL, LOGIN))
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    assert cliente.llamadas == [*_CAMINO_ANTERIOR, ("role_exists", GRUPO)], (
        "ninguna sentencia ni pregunta sobre un grupo que no existe"
    )
    assert log.avisos == [("apply_grants_restringido_inexistente",
                           {"role": GRUPO, "detalle": "créalo con infra/sql/02_roles.sql"})]
    assert resultado.metadata["rol_restringido"] == f"{GRUPO} (no existe)"
    assert resultado.metadata["verificacion_restringido"] == "no aplica"
    assert resultado.metadata["excepciones_sobrantes"] == "no aplica"
    assert resultado.rows_processed == 2 + 1 + 1


def test_f141_r10_grupo_inexistente_no_tapa_un_fallo_del_estandar() -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, AUTORIZADO, TOTAL),
                            indebidas={ESTANDAR: ["raw (USAGE)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    assert (resultado.error_message or "").startswith(f"el rol '{ESTANDAR}' sigue leyendo")


def test_f141_r13_una_vista_que_filtra_se_revoca_y_falla() -> None:
    filas = [*FILAS_HOY, ("mart.v_nueva", "tesoreria.efectos"), ("mart.v_nueva", "personal.recursos"), ("compras.vencimientos", "personal.recursos")]
    cliente = _ClienteFalso(filas=filas)
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    revocar = [*EXCLUIDAS_R, "mart.v_nueva", "compras.vencimientos"]
    assert ("perfil", GRUPO, DUENO, ESQUEMAS_R, revocar) in cliente.llamadas, (
        "revocada ANTES de terminar, cada vista una vez: es la alarma, no la protección"
    )
    assert ("verifica", GRUPO, AJENOS, revocar) in cliente.llamadas
    mensaje = resultado.error_message or ""
    assert (
        "mart.v_nueva -> tesoreria.efectos, mart.v_nueva -> personal.recursos, "
        "compras.vencimientos -> personal.recursos"
    ) in mensaje, "cada vista y lo que alcanza"
    assert f"'{GRUPO}'" in mensaje and "F-141" in mensaje
    assert resultado.metadata["filtraciones_restringido"] == [
        "mart.v_nueva -> tesoreria.efectos", "mart.v_nueva -> personal.recursos",
        "compras.vencimientos -> personal.recursos",
    ]
    assert resultado.metadata["excepciones_sobrantes"] == "ok"


def test_f141_r13_raw_no_es_filtracion_y_lo_no_suyo_sale_del_catalogo() -> None:
    cliente = _ClienteFalso()
    _paso(cliente)
    ((_, _, ajenos, _),) = [c for c in cliente.llamadas if c[0] == "filtran"]
    assert "raw" not in ajenos and "tesoreria" in ajenos and "personal" in ajenos


def test_f141_r14_un_vigilado_sin_excluir_se_revoca_y_falla() -> None:
    cliente = _ClienteFalso(vigilados=["contabilidad.mayor", "mart.mayor_analitico"])
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    revocar = [*EXCLUIDAS_R, "mart.mayor_analitico"]
    assert ("perfil", GRUPO, DUENO, ESQUEMAS_R, revocar) in cliente.llamadas
    mensaje = resultado.error_message or ""
    assert "mart.mayor_analitico" in mensaje and "contabilidad.mayor," not in mensaje
    assert "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES" in mensaje and "F-127" in mensaje
    assert resultado.metadata["vigilados_restringido"] == ["mart.mayor_analitico"]


def test_f141_r14_una_vista_que_filtra_y_es_vigilada_se_revoca_una_vez() -> None:
    cliente = _ClienteFalso(filas=[*FILAS_HOY, ("mart.mayor_x", "tesoreria.efectos")],
                            vigilados=["mart.mayor_x"])
    _paso(cliente)
    assert ("perfil", GRUPO, DUENO, ESQUEMAS_R, [*EXCLUIDAS_R, "mart.mayor_x"]) in cliente.llamadas


def test_f141_r15_excepcion_sobrante_avisa_y_no_falla(log: _Log) -> None:
    cliente = _ClienteFalso(filas=FILAS_HOY[:1])
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    sobrantes = ["compras.v_control_forma_pago", "compras.v_facturas_pago"]
    assert resultado.metadata["excepciones_sobrantes"] == sobrantes
    assert ("apply_grants_restringido_excepcion_sobrante",
            {"role": GRUPO, "excepciones": sobrantes,
             "detalle": "ya no leen la cartera: quítalas de EXCEPCIONES_FILTRACION_RESTRINGIDO"},
            ) in log.avisos


@pytest.mark.parametrize("quien", [GRUPO, LOGIN])
def test_f141_r16_si_el_grupo_o_el_login_leen_algo_falla_con_la_lista(quien: str) -> None:
    cliente = _ClienteFalso(indebidas={quien: ["tesoreria (USAGE)", "personal.recursos (SELECT)"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    mensaje = resultado.error_message or ""
    assert (f"el perfil restringido '{quien}' lee lo que no debe: tesoreria (USAGE), "
            "personal.recursos (SELECT)") in mensaje
    assert "5 quinquies" in mensaje and "PUBLIC" in mensaje
    assert resultado.metadata["verificacion_restringido"] == {
        quien: ["tesoreria (USAGE)", "personal.recursos (SELECT)"]
    }


def test_f141_r17_pertenencias_indebidas_fallan() -> None:
    cliente = _ClienteFalso(pertenencias={LOGIN: [GRUPO, ESTANDAR], GRUPO: [TOTAL]})
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    indebidas = [f"{LOGIN} -> {ESTANDAR}", f"{GRUPO} -> {TOTAL}"]
    assert resultado.metadata["pertenencias_restringido"] == indebidas
    mensaje = resultado.error_message or ""
    assert ", ".join(indebidas) in mensaje and "5 quinquies" in mensaje


def test_f141_r18_login_inexistente_avisa_y_mira_solo_el_grupo(log: _Log) -> None:
    cliente = _ClienteFalso(existen=(ESTANDAR, AUTORIZADO, TOTAL, GRUPO))
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS"
    restringido = cliente.llamadas[len(_CAMINO_ANTERIOR):]
    assert ("verifica", LOGIN, AJENOS, EXCLUIDAS_R) not in restringido
    assert ("pertenencias", LOGIN) not in restringido
    assert ("pertenencias", GRUPO) in restringido and ("usage", GRUPO, ESQUEMAS_R) in restringido
    assert ("apply_grants_restringido_login_inexistente",
            {"role": LOGIN, "detalle": "créalo con infra/sql/02_roles.sql"}) in log.avisos
    assert resultado.metadata["login_restringido"] == f"{LOGIN} (no existe)"
    assert resultado.metadata["pertenencias_restringido"] == "ok"


def test_f141_r18_login_sin_configurar_mira_solo_el_grupo(log: _Log) -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_restringido_login=" ")
    assert resultado.status.name == "SUCCESS"
    assert ("role_exists", "") not in cliente.llamadas
    assert resultado.metadata["login_restringido"] == "(sin configurar)"
    assert ("usage", GRUPO, ESQUEMAS_R) in cliente.llamadas
    assert log.avisos == []


def test_f141_r18_le_falta_usage_solo_avisa(log: _Log) -> None:
    cliente = _ClienteFalso(sin_usage={LOGIN: ["stg"]})
    resultado = _paso(cliente)
    assert resultado.status.name == "SUCCESS", "leer de menos no expone nada"
    assert resultado.metadata["acceso_restringido"] == ["stg"]
    assert ("apply_grants_restringido_incompleto",
            {"role": LOGIN, "faltan": ["stg"],
             "detalle": "le falta la pertenencia o el GRANT: punto 5 quinquies de "
                        "infra/sql/02_roles.sql"}) in log.avisos


def test_f141_r19_los_tres_fallan_un_solo_mensaje_en_orden() -> None:
    cliente = _ClienteFalso(
        indebidas={ESTANDAR: ["raw.pag (SELECT)"], TOTAL: ["raw (USAGE)"],
                   GRUPO: ["personal (USAGE)"]},
        vigilados=["mart.mayor_y"],
    )
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    mensaje = resultado.error_message or ""
    posiciones = [mensaje.index(t) for t in (
        f"el rol '{ESTANDAR}' sigue leyendo lo vetado: raw.pag (SELECT)",
        f"el login total '{TOTAL}' lee lo vetado: raw (USAGE)",
        "mart.mayor_y",
        f"el perfil restringido '{GRUPO}' lee lo que no debe: personal (USAGE)",
    )]
    assert posiciones == sorted(posiciones), "estándar, total y restringido, en ese orden"
    assert resultado.metadata["verificacion"] == ["raw.pag (SELECT)"]
    assert resultado.metadata["verificacion_total"] == ["raw (USAGE)"]


def test_f141_r19_lo_del_estandar_el_autorizado_y_el_total_no_cambia() -> None:
    con = _ClienteFalso()
    sin = _ClienteFalso()
    _paso(con)
    _paso(sin, perfil_restringido_group="")
    assert con.llamadas[:len(_CAMINO_ANTERIOR)] == sin.llamadas == _CAMINO_ANTERIOR


def test_f141_paso_un_fallo_del_cliente_en_el_restringido_es_failed() -> None:
    cliente = _ClienteFalso(falla_en="filtran")
    resultado = _paso(cliente)
    assert resultado.status.name == "FAILED"
    assert "se cayó la conexión en filtran" in (resultado.error_message or "")
    assert not [c for c in cliente.llamadas if c[0] == "perfil"], "nada concedido a medias"


def test_f141_paso_sin_nombres_a_mano_y_docstring() -> None:
    from etl_sigrid.application.steps import apply_grants_step

    fuente = Path(apply_grants_step.__file__).read_text(encoding="utf-8")
    ejecutable = "\n".join(f for f in fuente.splitlines() if not f.lstrip().startswith("#"))
    codigo = ejecutable.split('"""', 2)[2]
    for nombre in (GRUPO, LOGIN, AUTORIZADO, RETIRADO):
        assert nombre not in codigo, "los nombres salen de la configuración, no del paso"
    doc = apply_grants_step.__doc__ or ""
    for cosa in ("F-141", "restringido", "5 quinquies", "excepciones", "mayor"):
        assert cosa in doc, f"el docstring no explica {cosa}"


# ===========================================================================
# R20-R23 · infra/sql/02_roles.sql (T7): contrato textual. La prueba con
# PostgreSQL 16 real y el psql.exe de Windows está en impl_F-141.md (T11).
# ===========================================================================

ROLES_SQL = RAIZ / "infra" / "sql" / "02_roles.sql"
PROVISION = RAIZ / "infra" / "15_provision_db.ps1"


def _roles_crudo() -> str:
    return ROLES_SQL.read_text(encoding="utf-8")


def _roles_sql() -> str:
    """El fichero sin las líneas de comentario: una cita no ejecuta nada."""
    return "\n".join(
        linea for linea in _roles_crudo().splitlines() if not linea.lstrip().startswith("--")
    )


def _primera_escritura(sql: str) -> int:
    return min(sql.index("CREATE ROLE"), sql.index("ALTER ROLE"))


def test_f141_r20_renombre_condicionado_y_antes_de_crear_nada() -> None:
    sql = _roles_sql()
    consulta = (
        f"SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{RETIRADO}') "
        "AS existe_nombre_viejo,\n"
        f"       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{AUTORIZADO}') "
        "AS existe_nombre_nuevo\n\\gset"
    )
    assert consulta in sql
    los_dos = (
        "\\if :existe_nombre_viejo\n\\if :existe_nombre_nuevo\n"
        f"DO $$ BEGIN RAISE EXCEPTION 'F-141: existen {RETIRADO} y {AUTORIZADO}"
    )
    assert los_dos in sql, "con los dos, falla"
    renombre = (
        "\\if :existe_nombre_viejo\n"
        f"ALTER ROLE {RETIRADO} RENAME TO {AUTORIZADO};\n"
    )
    assert sql.count(f"RENAME TO {AUTORIZADO}") == 1 and renombre in sql
    escritura = _primera_escritura(sql)
    assert sql.index(los_dos) < escritura, "la guarda de los dos, antes de cambiar nada"
    assert escritura == sql.index(f"ALTER ROLE {RETIRADO} RENAME"), "el renombre, lo primero"
    assert sql.index(renombre) > sql.rindex("RAISE EXCEPTION 'F-136"), (
        "detrás de las guardas de contraseña: si una para, no se ha cambiado nada (R21)"
    )
    assert sql.index(renombre) < sql.index("SELECT 'CREATE ROLE"), (
        "antes de crear el autorizado: si no, existirían los dos"
    )


def test_f141_r21_crea_el_grupo_y_el_login_idempotentes() -> None:
    sql = _roles_sql()
    for rol, tipo in ((GRUPO, "NOLOGIN"), (LOGIN, "LOGIN")):
        assert (
            f"SELECT 'CREATE ROLE {rol} {tipo}'\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}')\n\\gexec"
        ) in sql
    assert f"ALTER ROLE {GRUPO} WITH NOLOGIN NOCREATEDB NOCREATEROLE;" in sql
    assert f"ALTER ROLE {LOGIN} WITH LOGIN NOCREATEDB NOCREATEROLE;" in sql
    assert "NOSUPERUSER" not in sql, "Azure no lo admite: CREATE ROLE ya lo da"
    assert "PASSWORD" not in sql.split(f"ROLE {GRUPO}")[1].split(";")[0], "el grupo, sin contraseña"


def test_f141_r21_la_contrasena_solo_del_entorno_y_sin_valor() -> None:
    sql = _roles_sql()
    primera = sql.index("PASSWORD")
    linea = "\\getenv restringido_pwd RESTRINGIDO_PWD"
    assert linea in sql and sql.index("\\set ECHO none") < sql.index(linea) < primera
    bloque = (
        "\\if :{?restringido_pwd}\n"
        f"ALTER ROLE {LOGIN} WITH LOGIN PASSWORD :'restringido_pwd';\n"
        f"\\echo '{LOGIN}: contraseña fijada'\n"
        "\\else\n"
        f"\\echo '{LOGIN}: contraseña SIN CAMBIOS'\n"
        "\\endif"
    )
    assert bloque in sql
    assert sql.count("PASSWORD :'restringido_pwd'") == 1
    assert sql.count("PASSWORD") == 4, "las tres de antes y la del login restringido"


def test_f141_r21_guarda_antes_de_crear_o_cambiar_nada() -> None:
    sql = _roles_sql()
    assert (
        f"NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{LOGIN}') AS falta_restringido"
    ) in sql
    bloque = (
        "\\if :falta_restringido\n"
        "\\if :{?restringido_pwd}\n"
        "\\else\n"
        f"DO $$ BEGIN RAISE EXCEPTION 'F-141: {LOGIN} no existe y falta RESTRINGIDO_PWD "
        "en el entorno (runbook §13)'; END $$;\n"
        "\\endif\n"
        "\\endif"
    )
    assert bloque in sql and sql.index(bloque) < _primera_escritura(sql)


def test_f141_r22_connect_al_grupo_y_ningun_grant_al_login_salvo_la_pertenencia() -> None:
    import re

    sql = _roles_sql()
    assert f"GRANT CONNECT ON DATABASE sigrid_dm TO {GRUPO};" in sql
    concesiones = re.findall(rf"GRANT\b[^;]*?\bTO\s+{LOGIN}\b[^;]*;", sql)
    assert concesiones == [f"GRANT {GRUPO} TO {LOGIN} WITH INHERIT TRUE, SET FALSE;"]
    assert not re.search(rf"\bTO\s+{LOGIN}\b'", sql), "ni dentro de un format() de un DO"
    assert f"GRANT SELECT ON TABLES TO {GRUPO}" not in sql, "ningún privilegio por defecto en GRANT"


def _tramo_transaccion(sql: str) -> tuple[int, int]:
    return sql.index("\nBEGIN;"), sql.index("\nCOMMIT;")


def test_f141_r22_la_mitad_del_dueno_en_la_transaccion_y_como_dueno() -> None:
    import re

    from config.settings import (
        DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES,
        DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS,
    )

    sql = _roles_sql()
    apertura, cierre = _tramo_transaccion(sql)
    bucle = re.search(r"FOREACH esquema_r IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert bucle and apertura < bucle.start() < cierre
    assert re.findall(r"'(\w+)'", bucle.group(1)) == DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS.split(",")
    antes = sql[:bucle.start()]
    assert antes.rindex("SET ROLE sigrid_dm_etl;") > antes.rindex("RESET ROLE;"), (
        "como sigrid_dm_etl, el mismo concedente que la nocturna: así ella puede revocar"
    )
    for sentencia in (
        f"'GRANT USAGE ON SCHEMA %I TO {GRUPO}'",
        f"'GRANT SELECT ON ALL TABLES IN SCHEMA %I TO {GRUPO}'",
        f"'REVOKE SELECT ON TABLES FROM {GRUPO}'",
    ):
        assert sentencia in sql, sentencia
    excluidas = re.search(r"FOREACH excluida_r IN ARRAY ARRAY\[(.*?)\]", sql, re.DOTALL)
    assert excluidas and re.findall(r"'([\w.]+)'", excluidas.group(1)) == (
        DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES.split(",")
    )
    assert excluidas.start() > bucle.start(), "los REVOKE de lo excluido, detrás de los GRANT"


def test_f141_r22_el_veto_sale_del_catalogo_con_los_dos_concedentes() -> None:
    import re

    sql = _roles_sql()
    apertura, cierre = _tramo_transaccion(sql)
    vetos = [m.start() for m in re.finditer(r"FOR ajeno_r IN", sql)]
    assert len(vetos) == 2, "una vez como dueño y otra como administrador"
    assert all(apertura < p < cierre for p in vetos)
    for sentencia in (
        f"'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA %I FROM {GRUPO}'",
        f"'REVOKE ALL PRIVILEGES ON SCHEMA %I FROM {GRUPO}'",
    ):
        assert sql.count(sentencia) == 2, sentencia
    assert sql.count(f"'REVOKE ALL ON TABLES FROM {GRUPO}'") == 1, "privilegio por defecto, como dueño"
    for p in vetos:
        consulta = sql[p:sql.index("LOOP", p)]
        for suyo in ESQUEMAS_R:
            assert f"'{suyo}'" in consulta, f"el veto no excluye {suyo}"
        assert "'information_schema', 'public'" in consulta and "'pg\\_%'" in consulta


def test_f141_r22_la_pertenencia_como_administrador_al_final_de_la_transaccion() -> None:
    sql = _roles_sql()
    apertura, cierre = _tramo_transaccion(sql)
    sentencia = f"GRANT {GRUPO} TO {LOGIN} WITH INHERIT TRUE, SET FALSE;"
    pos = sql.index(sentencia)
    assert apertura < pos < cierre
    antes = sql[:pos]
    assert antes.rindex("RESET ROLE;") > antes.rindex("SET ROLE sigrid_dm_etl;"), (
        "como el ADMINISTRADOR, que tiene ADMIN OPTION; sigrid_dm_etl no"
    )
    assert pos > max(m for m in (sql.rfind("FOR ajeno_r IN"),)), "después de los vetos"


def test_f141_r23_comprobacion_final() -> None:
    import re

    sql = _roles_sql()
    final = sql.split("\nCOMMIT;", 1)[1]
    consulta = re.search(r"SELECT rolname, rolcanlogin, rolsuper.*?;", final, re.DOTALL)
    assert consulta
    assert set(re.findall(r"'(\w+)'", consulta.group(0))) == {
        DUENO, "sigrid_dm_app", ESTANDAR, AUTORIZADO, TOTAL, GRUPO, LOGIN,
    }, "los siete roles, con rolsuper"
    assert (
        "FROM pg_auth_members AS m\n"
        "JOIN pg_roles AS r ON r.oid = m.member\n"
        "JOIN pg_roles AS g ON g.oid = m.roleid\n"
        f"WHERE r.rolname = '{LOGIN}'"
    ) in final, "las pertenencias del login: solo el grupo"
    for esquema in [*ESQUEMAS_R, "tesoreria", "personal", "raw", RESTR_C,
                    "tesoreria_restringida", "compras_restringida"]:
        assert f"has_schema_privilege('{LOGIN}', '{esquema}', 'USAGE')" in final, esquema
    for tabla in ("contabilidad.mayor", "contabilidad.saldos_cuenta_mes",
                  "contabilidad.plan_cuentas", "compras.vencimientos"):
        assert f"has_table_privilege('{LOGIN}', to_regclass('{tabla}'), 'SELECT')" in final
    assert f"has_database_privilege('{LOGIN}', current_database(), 'CONNECT')" in final
    assert f"WHERE grantee = '{LOGIN}'" in final


def test_f141_r20_r23_la_cabecera_explica_el_perfil_y_el_renombre() -> None:
    cabecera = _roles_crudo().split("\\set ON_ERROR_STOP on")[0]
    for texto in (GRUPO, LOGIN, "RESTRINGIDO_PWD", "F-141", AUTORIZADO, "5 quinquies",
                  "runbook §13"):
        assert texto in cabecera, f"la cabecera no cita {texto}"


def test_f141_r21_provision_exige_restringido_pwd_y_no_la_pasa() -> None:
    texto = PROVISION.read_text(encoding="utf-8-sig")
    codigo = "\n".join(
        linea for linea in texto.splitlines() if not linea.lstrip().startswith("#")
    )
    assert "-not $env:RESTRINGIDO_PWD" in codigo, "-Ejecutar no exige RESTRINGIDO_PWD"
    assert "RESTRINGIDO_PWD" in texto.split("[CmdletBinding()]")[0], "la cabecera la pide"
    assert "perfil restringido del MCP (F-141)" in codigo, "el rótulo de roles lo nombra"
    for linea in codigo.splitlines():
        if "psql" in linea:
            assert "PWD" not in linea.upper(), linea


# ===========================================================================
# R25 · ni contraseña, ni oid, ni UPN, ni login de persona en lo de F-141 (T8)
# ===========================================================================

#: un oid de Entra (y cualquier GUID: suscripción, tenant)
_PATRON_GUID = r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
#: un UPN o un correo: algo@dominio.tld
_PATRON_UPN = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
#: las personas del perfil total (F-136): el diccionario y los papeles dicen «perfil total»
_PERSONAS = ("Antonio", "Vicente", "Pablo", "Gris")
#: los únicos roles que `02_roles.sql` puede crear o a los que puede conceder
_ROLES_DEL_REPOSITORIO = {DUENO, "sigrid_dm_app", ESTANDAR, AUTORIZADO, TOTAL, GRUPO, LOGIN}


def _ficheros_de_f141() -> list[Path]:
    fijos = [
        RAIZ / "infra" / "sql" / "02_roles.sql",
        RAIZ / "infra" / "15_provision_db.ps1",
        RAIZ / "docs" / "runbook_postgres_azure.md",
        RAIZ / "progress" / "spec_F-141.md",
    ]
    spec = sorted((RAIZ / "specs").glob("F-141-*/*.md"))
    # `mutacion_F-141.md` no: lo escribe el arnés con SHA de git y rutas de worktree.
    informes = [r for r in (RAIZ / "progress" / "impl_F-141.md",
                            RAIZ / "progress" / "review_F-141.md") if r.exists()]
    return fijos + spec + informes


def _hallazgos(texto: str) -> list[str]:
    import re

    from tests.test_f005_grants import buscar_secretos

    # La ruta de la spec («perfil-restringido/requirements») tiene la forma de
    # una clave generada para el patrón de F-005: se quita, y solo ella.
    texto = texto.replace("specs/F-141-perfil-restringido/", "specs/F-141/")
    return (
        buscar_secretos(texto)
        + re.findall(_PATRON_GUID, texto)
        + re.findall(_PATRON_UPN, texto)
        + [p for p in _PERSONAS if re.search(rf"\b{p}\b", texto)]
    )


def test_f141_r25_los_ficheros_vigilados_existen() -> None:
    ficheros = _ficheros_de_f141()
    assert all(ruta.exists() for ruta in ficheros)
    assert len([r for r in ficheros if "specs" in r.parts]) == 3, "requirements, design y tasks"


@pytest.mark.parametrize("ruta", _ficheros_de_f141(), ids=lambda r: r.name)
def test_f141_r25_sin_secretos_oid_upn_ni_personas(ruta: Path) -> None:
    assert _hallazgos(ruta.read_text(encoding="utf-8-sig")) == []


def test_f141_r25_02_roles_solo_crea_y_concede_a_roles_del_repositorio() -> None:
    """Un login de persona entraría por un `CREATE ROLE` o un `GRANT ... TO` suyo."""
    import re

    sql = _roles_sql()
    creados = set(re.findall(r"CREATE ROLE (\w+)", sql))
    concedidos = set(re.findall(r"\bTO\s+(\w+)\s*(?:WITH\b|;|')", sql))
    concedidos -= {"TABLES"}  # `GRANT SELECT ON TABLES TO x` deja `TABLES` delante
    assert creados == _ROLES_DEL_REPOSITORIO - {DUENO}, creados
    assert concedidos <= _ROLES_DEL_REPOSITORIO, concedidos - _ROLES_DEL_REPOSITORIO


def test_f141_r25_el_barrido_caza_lo_que_debe() -> None:
    """Muestras SINTÉTICAS, construidas aquí para no dejar ninguna en el árbol."""
    guid = "-".join("0" * n for n in (8, 4, 4, 4, 12)).replace("0", "a", 1)
    upn = "nombre" + "@" + "empresa.es"
    hexa = "ab12" * 16
    for muestra in (guid, upn, hexa, "PASSWORD 'algo'", "Pablo"):
        assert _hallazgos(f"texto {muestra} texto"), muestra
    for legitimo in ("$env:RESTRINGIDO_PWD", "PASSWORD :'restringido_pwd'",
                     "pg-password-restringido", "<otro>"):
        assert _hallazgos(legitimo) == [], legitimo


# ===========================================================================
# R26-R29 · el diccionario (T9, D7)
# ===========================================================================

DICC = RAIZ / "config" / "diccionario"
AVISO = "No disponible para el perfil restringido"
#: los objetos de tabla o vista que el restringido no lee (R28); las funciones no cuentan
NO_DISPONIBLES = {
    "contabilidad.yaml": ["mayor", "saldos_cuenta_mes"],
    "tesoreria.yaml": ["efectos", "efectos_restringidos_mes"],
    "personal.yaml": ["recursos", "partes_lineas", "v_pbi_horas_obra_mes", "partes",
                      "recursos_tipos_hora", "usuarios_sigrid"],
}


def _yaml_dicc(nombre: str) -> dict:
    import yaml

    return yaml.safe_load((DICC / nombre).read_text(encoding="utf-8"))


def _reglas() -> dict[str, dict]:
    return {r["codigo"]: r for r in _yaml_dicc("00_global.yaml")["reglas"]}


def _plano_yaml(texto: str) -> str:
    import re

    return re.sub(r"\s+", " ", texto)


def test_f141_r26_la_regla_nueva_es_bloqueante_y_corta_de_titulo() -> None:
    regla = _reglas()["R-PERFIL-RESTRINGIDO"]
    assert regla["severidad"] == "bloqueante"
    assert len(regla["titulo"]) <= 87, "no más largo que el título más largo ya publicado"
    assert "restringido" in regla["titulo"].lower() and "menos" in regla["titulo"].lower()
    assert regla["motivo"].strip()


def test_f141_r26_la_regla_dice_lo_que_pidio_el_humano() -> None:
    texto = _plano_yaml(_reglas()["R-PERFIL-RESTRINGIDO"]["regla"])
    assert texto.index("TOTAL") < texto.index("ESTANDAR") < texto.index("RESTRINGIDO"), (
        "los tres perfiles, de más a menos"
    )
    for termino in (
        "TOTAL ⊃ ESTANDAR ⊃ RESTRINGIDO", "administrativos",
        "`contabilidad.mayor`", "`contabilidad.saldos_cuenta_mes`", "`tesoreria`", "`personal`",
        "mayor analitico", "`retenciones`",
        "`*_restringida`", "son del perfil TOTAL y NO del perfil restringido",
        "«permission denied»", "no se rodea",
        "`retenciones.apuntes_contables`", "`compras.vencimientos`", "logins de `compras`",
        "el perfil no lo incluye",
    ):
        assert termino in texto, f"la regla no dice «{termino}»"


def test_f141_r26_el_ambito_alcanza_lo_que_no_ve_y_los_atajos() -> None:
    ambito = set(_reglas()["R-PERFIL-RESTRINGIDO"]["ambito"])
    assert ambito >= {
        "contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "tesoreria", "personal",
        "retenciones.apuntes_contables", *EXCEPCIONES,
    }


@pytest.mark.parametrize(
    ("codigo", "titulo"),
    [
        ("R-CONTABILIDAD-RESTRINGIDA",
         "Usa contabilidad; contabilidad_restringida es solo para el perfil total del MCP"),
        ("R-TESORERIA-RESTRINGIDA",
         "Usa tesoreria; tesoreria_restringida es solo para el perfil total del MCP"),
        ("R-COMPRAS-RESTRINGIDA",
         "Usa compras.documento_alarmas; compras_restringida es solo para el perfil total del MCP"),
    ],
)
def test_f141_r27_cada_restringida_dice_que_no_es_del_perfil_restringido(
    codigo: str, titulo: str,
) -> None:
    regla = _reglas()[codigo]
    assert regla["titulo"] == titulo, "títulos sin cambio (D7)"
    texto = _plano_yaml(regla["regla"])
    assert f"`{AUTORIZADO}`" in texto and RETIRADO not in texto
    assert (
        "«restringida» = reservada al perfil total; el perfil RESTRINGIDO (administrativos) "
        "ve MENOS que el estandar y no lee este esquema"
    ) in texto


def test_f141_r27_en_tesoreria_tampoco_la_general() -> None:
    texto = _plano_yaml(_reglas()["R-TESORERIA-RESTRINGIDA"]["regla"])
    assert "tampoco la general (`tesoreria`)" in texto


@pytest.mark.parametrize(
    ("fichero", "objeto"),
    [(f, o) for f, objetos in NO_DISPONIBLES.items() for o in objetos],
)
def test_f141_r28_la_ficha_empieza_por_el_aviso(fichero: str, objeto: str) -> None:
    descripcion = _yaml_dicc(fichero)["objetos"][objeto]["descripcion"]
    primera = _plano_yaml(descripcion.split("\n", 1)[0])
    assert primera.startswith(f"**{AVISO}**"), primera
    assert "permission denied" in primera and "`R-PERFIL-RESTRINGIDO`" in primera


def test_f141_r28_ninguna_otra_ficha_lleva_el_aviso() -> None:
    import yaml

    con_aviso = set()
    for ruta in sorted(DICC.glob("*.yaml")):
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
        for objeto, ficha in (datos.get("objetos") or {}).items():
            if AVISO in str(ficha.get("descripcion", "")):
                con_aviso.add((ruta.name, objeto))
    assert con_aviso == {(f, o) for f, objetos in NO_DISPONIBLES.items() for o in objetos}


@pytest.mark.parametrize("vista", ["vencimientos", "v_facturas_pago", "v_control_forma_pago"])
def test_f141_r28_las_tres_excepciones_dicen_que_el_restringido_las_lee(vista: str) -> None:
    descripcion = _yaml_dicc("compras.yaml")["objetos"][vista]["descripcion"]
    primera = _plano_yaml(descripcion.split("\n", 1)[0])
    assert primera.startswith("**El perfil restringido SI la lee**"), primera
    for termino in ("estado de pago", "aunque no lea la cartera", "`R-PERFIL-RESTRINGIDO`"):
        assert termino in primera, termino


@pytest.mark.parametrize(
    "fichero", ["contabilidad_restringida.yaml", "tesoreria_restringida.yaml",
                "compras_restringida.yaml"],
)
def test_f141_r27_cabecera_de_los_yaml_restringida(fichero: str) -> None:
    cabecera = _plano_yaml(
        (DICC / fichero).read_text(encoding="utf-8").split("\nversion:")[0].replace("#", " ")
    )
    assert f"`{AUTORIZADO}`" in cabecera
    assert "F-141" in cabecera and "perfil restringido" in cabecera and "NO la lee" in cabecera


#: La versión que F-141 publicó. Hasta F-144 los dos tests de R29 la comparaban con la de
#: `main` («la siguiente a la de main») y con la versión VIGENTE: en la rama eran ciertos, pero
#: tras el merge `main` ya lleva la 54 (54 >= 55, rojo) y la siguiente feature que suba la
#: versión deja sin entrada F-141 a la vigente. Se fija la 54, como hace F-139 con la 53.
VERSION_F141 = 54


def test_f141_r29_version_la_siguiente_a_la_de_main() -> None:
    assert int(_yaml_dicc("00_global.yaml")["version"]) >= VERSION_F141


def test_f141_r29_la_historia_de_versiones_cuenta_f141() -> None:
    texto = (DICC / "00_global.yaml").read_text(encoding="utf-8")
    assert f"# version {VERSION_F141} (F-141, " in texto


def test_f141_r26_r28_sin_nombres_oid_ni_upn_en_el_diccionario() -> None:
    textos = [str(_reglas()["R-PERFIL-RESTRINGIDO"])] + [
        str(_yaml_dicc(f)["objetos"][o]) for f, objetos in NO_DISPONIBLES.items() for o in objetos
    ]
    for texto in textos:
        assert _hallazgos(texto) == []


# ===========================================================================
# R30 · documentación y contrato (T10)
# ===========================================================================

RUNBOOK = RAIZ / "docs" / "runbook_postgres_azure.md"
AZURE_APPS = RAIZ.parent / "azure-apps"


def _seccion_13() -> str:
    texto = RUNBOOK.read_text(encoding="utf-8")
    assert "\n## 13. " in texto, "falta la §13 del runbook"
    return texto.split("\n## 13. ", 1)[1].split("\n## ", 1)[0]


def _paso_13(n: int) -> str:
    return _seccion_13().split(f"### P{n} ", 1)[1].split("\n### ", 1)[0]


def _bloques(texto: str) -> list[str]:
    import re

    return re.findall(r"```(?:powershell|sql)?\n(.*?)```", texto, re.DOTALL)


def test_f141_r30_runbook_tabla_de_roles_con_los_siete() -> None:
    texto = RUNBOOK.read_text(encoding="utf-8")
    tabla = texto.split("## 1. Autenticación", 1)[1].split("\n## ", 1)[0]
    for rol in (DUENO, "sigrid_dm_app", ESTANDAR, AUTORIZADO, TOTAL, GRUPO, LOGIN):
        assert f"| `{rol}` |" in tabla, rol
    assert "pg-password-restringido" in tabla and "§13" in tabla


def test_f141_r30_runbook_seccion_13_en_orden() -> None:
    seccion = _seccion_13()
    posiciones = [seccion.find(f"### P{n} ") for n in range(10)]
    assert -1 not in posiciones and posiciones == sorted(posiciones), "P0 a P9, en orden"
    assert "### Vuelta atrás" in seccion and "PowerShell 5.1" in seccion
    assert "MISMO día" in seccion, "la imagen y 02_roles.sql el mismo día, entre nocturnas"


def test_f141_r30_runbook_p0_a_p5() -> None:
    p0 = _paso_13(0)
    for cosa in ("07:00", "21:00", "az containerapp job execution list",
                 "properties.template.containers[0].image", "F-141"):
        assert cosa in p0, cosa
    assert "RandomNumberGenerator" in _paso_13(1)
    p2 = _paso_13(2)
    assert "--vault-name $kvMcp --name pg-password-restringido --value $v -o none" in p2
    assert p2.count("$LASTEXITCODE") == 1 and "$v = $null" in p2
    p3 = _paso_13(3)
    assert "$env:RESTRINGIDO_PWD = az keyvault secret show" in p3 and "64" in p3
    p4 = _paso_13(4)
    assert "psql -X -v ON_ERROR_STOP=1 -f $roles $dsn" in p4
    assert p4.index("$antes") < p4.index("psql -X -v ON_ERROR_STOP=1 -f $roles $dsn"), (
        "R33: la huella del estándar y el total ANTES de tocar la base"
    )
    assert "Remove-Item Env:RESTRINGIDO_PWD" in _paso_13(5)


def test_f141_r30_runbook_p6_negativa_y_positiva() -> None:
    p6 = _paso_13(6)
    for objeto in ("contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "tesoreria.efectos",
                   "personal.recursos", "raw.obr", "contabilidad_restringida.mayor",
                   "tesoreria_restringida.efectos", "compras_restringida.documento_alarmas",
                   "compras.vencimientos", "compras.v_facturas_pago", "contabilidad.plan_cuentas",
                   "retenciones.movimientos", "mart.fact_seguimiento_mensual",
                   "_meta.v_diccionario", "compras.documento_adjuntos"):
        assert objeto in p6, objeto
    assert "CREATE TABLE compras." in p6 and "ROLLBACK" in p6
    assert "python main.py apply-grants" in p6 and "verificacion_restringido" in p6
    assert "Remove-Item Env:PGPASSWORD" in p6 and "PG_RESTRICTED_ROLE" in p6


def test_f141_r30_runbook_p7_a_p9() -> None:
    p7 = _paso_13(7)
    assert "$despues" in p7 and "Compare-Object" in p7, "R33: estándar y total, iguales"
    assert "python main.py publicar-diccionario" in p7 and "az containerapp revision restart" in p7
    p8 = _paso_13(8)
    for clave in ("verificacion", "verificacion_total", "verificacion_restringido",
                  "pertenencias_restringido"):
        assert f"'{clave}'" in p8, clave
    p9 = _paso_13(9)
    assert "azure-apps/datamart_seg_anual.md" in p9 and "E1" in p9 and "F-127" in p9


def test_f141_r30_runbook_higiene_de_la_seccion_13() -> None:
    import re

    lineas = [linea for b in _bloques(_seccion_13()) for linea in b.splitlines()]
    assert lineas, "la §13 trae su código"
    for linea in lineas:
        assert len(linea) <= 100, linea
        if "az keyvault secret show" in linea and not linea.lstrip().startswith("#"):
            assert re.match(r"\s*\$[\w:]+\s*=", linea), f"un `show` sin asignar imprime: {linea}"
        if "az keyvault secret set" in linea:
            assert linea.rstrip().endswith("-o none"), linea
        for consulta in re.findall(r'--query\s+"([^"]*)"', linea):
            assert not set(consulta) & set("&|("), consulta
    assert RETIRADO not in _seccion_13(), "R24: la vuelta atrás nombra la constante, no el rol"
    assert "NOMBRE_AUTORIZADO_RETIRADO" in _seccion_13()


def test_f141_r30_arquitectura_siete_roles_y_el_restringido() -> None:
    texto = (RAIZ / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "**Siete roles.**" in texto and "**Cinco roles.**" not in texto
    roles = texto.split("**Siete roles.**", 1)[1].split("\n- **", 1)[0]
    for cosa in (GRUPO, LOGIN, "pg-password-restringido", AUTORIZADO, "F-141"):
        assert cosa in roles, cosa
    for cosa in ("PG_PERFIL_RESTRINGIDO_GROUP", "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES",
                 "verificacion_restringido", "pertenencias_restringido",
                 "EXCEPCIONES_FILTRACION_RESTRINGIDO", "5 quinquies"):
        assert cosa in texto, f"ARCHITECTURE no explica {cosa}"
    f127 = texto.split("F-127", 1)
    assert len(f127) == 2 and "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES" in texto.split(
        "**El mayor analítico y F-127", 1)[1].split("\n- **", 1)[0], "la obligación de F-127"


def _azure_apps(nombre: str) -> str:
    ruta = AZURE_APPS / nombre
    if not ruta.exists():  # pragma: no cover - solo en un puesto sin el repositorio hermano
        pytest.skip(f"no está {ruta}: azure-apps es otro repositorio")
    return ruta.read_text(encoding="utf-8")


def test_f141_r30_azure_apps_describe_el_perfil_y_el_contrato() -> None:
    texto = _azure_apps("datamart_seg_anual.md")
    assert RETIRADO not in texto, "el nombre retirado tampoco en el contrato"
    contrato = texto.split("F-141", 1)[1]
    for cosa in (GRUPO, LOGIN, "pg-password-restringido", "kv-mcp-bbdd-dev",
                 "contabilidad.mayor", "contabilidad.saldos_cuenta_mes", "`tesoreria`",
                 "`personal`", "permission denied", "PERFIL_NO_DISPONIBLE", "estado_servidor",
                 "perfil=restringido", "SET ROLE"):
        assert cosa in contrato, f"datamart_seg_anual.md no cita {cosa}"
    for clausula in ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"):
        assert f"**{clausula}." in contrato, clausula
    assert _hallazgos(contrato) == [], "ni oid, ni UPN, ni contraseña"


def test_f141_r30_mcp_bbdd_solo_enlaza_al_contrato() -> None:
    texto = _azure_apps("mcp_bbdd.md")
    lineas = [linea for linea in texto.splitlines() if LOGIN in linea or "F-141" in linea]
    assert lineas and all("datamart_seg_anual.md" in linea for linea in lineas), lineas
    # `PERFIL_NO_DISPONIBLE` ya es un código suyo (perfil total): lo que no se copia
    # son las cláusulas del contrato.
    assert not [c for c in ("**E1.", "**E3.", "**E4.") if c in texto], (
        "enlaza al contrato, no lo copia"
    )
