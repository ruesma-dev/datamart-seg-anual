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

    assert grants.EXCEPCIONES_FILTRACION_RESTRINGIDO == {v: "tesoreria" for v in EXCEPCIONES}
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

    assert grants.TABLAS_ORIGEN_ADJUNTOS == tuple(
        f"compras.{tabla}" for tabla, _ in ORIGEN_POR_FAMILIA.values()
    )
    assert grants.OBJETO_ADJUNTOS == "compras.documento_adjuntos"


# --- R5 · perfil_restringido_en_conflicto -----------------------------------

_VETADOS = ["contabilidad_restringida", "tesoreria_restringida", "compras_restringida", "raw"]
_RESTRINGIDOS = ["contabilidad_restringida", "tesoreria_restringida", "compras_restringida"]


def _conflicto(esquemas: list[str], **cambios: list[str]) -> list[str]:
    from etl_sigrid.infrastructure.postgres.grants import perfil_restringido_en_conflicto

    listas = {
        "consumo": ESQUEMAS_R + ["tesoreria", "personal"],
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
        ("raw", {"consumo": ESQUEMAS_R + ["raw"]}),  # vetado al estándar
        ("compras_restringida", {"consumo": ESQUEMAS_R + ["compras_restringida"],
                                 "vetados": ["raw"]}),  # de lo restringido
        ("stg2", {"consumo": ESQUEMAS_R + ["stg2"], "total_vetados": ["raw", "stg2"]}),
    ],
    ids=["fuera-del-consumo", "vetado", "restringido", "vetado-al-total"],
)
def test_f141_grants_r5_cada_lista_que_choca(extra: str, cambios: dict) -> None:
    assert _conflicto(ESQUEMAS_R + [extra, extra], **cambios) == [extra], (
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
    assert origenes_de_adjuntos_sin_leer(ESQUEMAS_R, EXCLUIDAS_R + ["compras.facturas"]) == [
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

    catalogo = ESQUEMAS_R + [
        "tesoreria", "personal", "raw", "contabilidad_restringida", "pg_catalog",
        "information_schema", "pg_toast", "pg_temp_3", "pg_toast_temp_3", "public",
        "nuevo", "tesoreria",
    ]
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
CATALOGO = ESQUEMAS_R + ["tesoreria", "personal", "raw", RESTR_C, "tesoreria_restringida",
                         "compras_restringida", "public", "pg_catalog", "information_schema",
                         "pg_toast"]
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

    def role_exists(self, role):  # noqa: ANN001, ANN201
        self.llamadas.append(("role_exists", role))
        return role in self.existen

    def list_schemas(self):  # noqa: ANN201
        self.llamadas.append(("catalogo",))
        return list(CATALOGO)

    def apply_readonly_grants(self, readonly_role, owner_role, schemas, excluded_tables=(),
                              vetoed_schemas=()):  # noqa: ANN001, ANN201
        self.llamadas.append(("general", readonly_role))
        return ["G1", "G2"]

    def apply_restricted_grants(self, role, owner_role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("autorizado", role))
        return ["A1"]

    def apply_veto(self, role, owner_role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("veto", role, owner_role, list(schemas)))
        return ["V"] * len(list(schemas))

    def lecturas_indebidas(self, role, schemas, tables):  # noqa: ANN001, ANN201
        self.llamadas.append(("verifica", role, list(schemas), list(tables)))
        return list(self.indebidas.get(role, []))

    def esquemas_sin_usage(self, role, schemas):  # noqa: ANN001, ANN201
        self.llamadas.append(("usage", role, list(schemas)))
        return list(self.sin_usage.get(role, []))

    def vistas_que_filtran(self, schemas, foreign_schemas, tables):  # noqa: ANN001, ANN201
        self.llamadas.append(("filtran", list(schemas), list(foreign_schemas), list(tables)))
        self._quizas_falla("filtran")
        return list(self.filas)

    def objetos_vigilados(self, schemas, pattern):  # noqa: ANN001, ANN201
        self.llamadas.append(("vigilados", list(schemas), pattern))
        return list(self.vigilados)

    def pertenencias(self, role):  # noqa: ANN001, ANN201
        self.llamadas.append(("pertenencias", role))
        return list(self.pert.get(role, []))

    def apply_perfil_restringido(self, role, owner_role, schemas, revoked):  # noqa: ANN001, ANN201
        self.llamadas.append(("perfil", role, owner_role, list(schemas), list(revoked)))
        return ["R1", "R2", "R3"]


def _settings(**pg: object):  # noqa: ANN202
    from types import SimpleNamespace

    base: dict[str, object] = {
        "readonly_role": ESTANDAR,
        "set_role": DUENO,
        "consumption_schema_list": ESQUEMAS_R + ["tesoreria", "personal"],
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
        cliente, perfil_restringido_schema_list=ESQUEMAS_R + ["raw", "nuevo"],
    ))
    assert "PG_PERFIL_RESTRINGIDO_SCHEMAS" in mensaje and "(raw, nuevo)" in mensaje


def test_f141_r5_tesoreria_entera_tambien() -> None:
    """Dársela es configuración válida del consumo, pero sigue en el consumo: no choca."""
    cliente = _ClienteFalso(filas=[])
    resultado = _paso(cliente, perfil_restringido_schema_list=ESQUEMAS_R + ["tesoreria"])
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
        cliente, perfil_restringido_excluded_table_list=EXCLUIDAS_R + [mala],
    ))
    assert "PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES" in mensaje and f"({mala})" in mensaje


def test_f141_r8_un_origen_de_adjuntos_excluido_para_en_seco() -> None:
    cliente = _ClienteFalso()
    mensaje = _para_en_seco(cliente, _paso(
        cliente, perfil_restringido_excluded_table_list=EXCLUIDAS_R + ["compras.contratos"],
    ))
    assert "compras.documento_adjuntos" in mensaje and "(compras.contratos)" in mensaje
    assert "F-139" in mensaje


def test_f141_r8_excluyendo_tambien_los_adjuntos_pasa() -> None:
    cliente = _ClienteFalso()
    resultado = _paso(cliente, perfil_restringido_excluded_table_list=EXCLUIDAS_R + [
        "compras.contratos", "compras.documento_adjuntos",
    ])
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
