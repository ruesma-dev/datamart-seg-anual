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
