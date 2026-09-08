# tests/test_f068_exclusion_lectura_mcp.py
"""
F-068 · Tablas de `raw` que el rol de lectura del MCP NO puede leer.

Contexto: por decisión del humano del 2026-08-08 el rol `mcp_sigrid_dm_ro`
recibe `SELECT` sobre TODOS los esquemas, `raw` incluido, y `apply_grants` se
lo renueva cada noche. Desde que F-066 trajo `raw.emp` y `raw.res` enteras, eso
son datos personales de 1.352 empleados legibles por cualquier cuenta del
tenant. El humano decidió el 2026-09-07 la salida (b): revocar.

Lo que fijan estos tests es que la revocación **sobreviva a la nocturna**, que
es donde una revocación suelta se pierde:

  R1  Cada tabla declarada en la lista de exclusión recibe un REVOKE, y ese
      REVOKE va DESPUÉS del `GRANT SELECT ON ALL TABLES` de su esquema.
  R2  El esquema que tiene exclusiones NO deja `ALTER DEFAULT PRIVILEGES ...
      GRANT`, sino su REVOKE: si no, una tabla recreada nace legible otra vez.
  R3  Los esquemas sin exclusiones conservan su GRANT por defecto intacto.
  R4  Una exclusión sobre un esquema que no se concede no emite nada.
  R5  Una entrada malformada revienta en vez de dejar la tabla legible.
  R6  El defecto de configuración excluye `raw.emp` y `raw.res`, y es
      parametrizable por entorno (PG_EXCLUDED_TABLES).
  R7  El paso del pipeline le pasa la lista al cliente, y el cliente solo
      revoca sobre las tablas que existen.
  R8  `infra/sql/02_roles.sql` excluye exactamente las mismas tablas que el
      código, y ambos sitios dicen que esto es TEMPORAL.

Sin red ni BBDD: `build_readonly_grant_statements` es una función pura y el
paso se prueba con un cliente Postgres de mentira.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from etl_sigrid.application.steps.apply_grants_step import ApplyGrantsStep
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements

REPO_ROOT = Path(__file__).resolve().parents[1]

ROL = "mcp_sigrid_dm_ro"
DUENO = "sigrid_dm_etl"
TODOS_LOS_ESQUEMAS = (
    "mart", "cierre", "compras", "maestro", "retenciones", "raw", "stg", "aux", "_meta",
)


def _indice(sentencias: list[str], fragmento: str) -> int:
    """Posición de la primera sentencia que contiene `fragmento`."""
    for i, s in enumerate(sentencias):
        if fragmento in s:
            return i
    raise AssertionError(f"ninguna sentencia contiene {fragmento!r}:\n" + "\n".join(sentencias))


# ---------------------------------------------------------------------------
# R1 · la tabla excluida se revoca, y se revoca DESPUÉS de concederla
# ---------------------------------------------------------------------------

def test_f068_r1_la_tabla_excluida_recibe_su_revoke() -> None:
    """
    `GRANT SELECT ON ALL TABLES IN SCHEMA raw` alcanza a `raw.emp`: no hay
    forma de conceder el esquema saltándose una tabla. Lo único que funciona
    es conceder y quitar después, en la misma tanda.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp", "raw.res"]
    )

    for tabla in ("emp", "res"):
        esperada = f'REVOKE ALL PRIVILEGES ON TABLE "raw"."{tabla}" FROM "{ROL}"'
        assert esperada in sentencias, f"falta el REVOKE de raw.{tabla}"


def test_f068_r1_el_revoke_va_despues_del_grant_del_esquema() -> None:
    """
    El orden es lo único que hace que esto funcione. Al revés —revocar y luego
    conceder el esquema entero— la tabla se quedaría legible, y el conjunto
    seguiría pareciendo correcto leyendo las sentencias por separado.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp", "raw.res"]
    )

    grant_raw = _indice(sentencias, 'GRANT SELECT ON ALL TABLES IN SCHEMA "raw"')
    for tabla in ("emp", "res"):
        revoke = _indice(sentencias, f'ON TABLE "raw"."{tabla}"')
        assert revoke > grant_raw, (
            f"el REVOKE de raw.{tabla} se emite ANTES del GRANT del esquema: "
            "el GRANT lo pisaría y la tabla quedaría legible"
        )


def test_f068_r1_solo_se_revoca_lo_declarado() -> None:
    """Ninguna otra tabla de `raw` pierde el permiso por el camino."""
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp"]
    )

    revokes_de_tabla = [
        s for s in sentencias if s.startswith("REVOKE ALL PRIVILEGES ON TABLE")
    ]
    assert revokes_de_tabla == [
        f'REVOKE ALL PRIVILEGES ON TABLE "raw"."emp" FROM "{ROL}"'
    ]


def test_f068_r1_sin_exclusiones_el_sql_es_el_de_siempre() -> None:
    """
    Sin lista de exclusión no se emite ni un REVOKE: quien no tenga la
    parametrización puesta (desarrollo local) sigue con el comportamiento
    anterior, letra por letra.
    """
    con_defecto = build_readonly_grant_statements(ROL, DUENO, TODOS_LOS_ESQUEMAS)
    explicito = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=[]
    )

    assert con_defecto == explicito
    assert not any("REVOKE" in s for s in con_defecto)


# ---------------------------------------------------------------------------
# R2, R3 · los privilegios por defecto, que es por donde vuelve el permiso
# ---------------------------------------------------------------------------

def test_f068_r2_el_esquema_con_exclusiones_revoca_los_privilegios_por_defecto() -> None:
    """
    `ALTER DEFAULT PRIVILEGES ... GRANT SELECT ON TABLES` es una regla que vive
    en el catálogo: mientras esté puesta, CUALQUIER tabla que nazca en `raw`
    —una `raw.emp` recreada, una tabla nueva de personal— nace ya legible por
    el MCP, sin que nadie ejecute un GRANT. Dejar de emitirla no la borra: hay
    que emitir su REVOKE, que es lo que la quita del catálogo.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp", "raw.res"]
    )

    esperada = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'REVOKE SELECT ON TABLES FROM "{ROL}"'
    )
    assert esperada in sentencias

    prohibida = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'GRANT SELECT ON TABLES TO "{ROL}"'
    )
    assert prohibida not in sentencias, (
        "se sigue concediendo el privilegio por defecto sobre raw: una tabla "
        "recreada volvería a ser legible hasta el siguiente apply_grants"
    )


def test_f068_r3_los_demas_esquemas_conservan_su_grant_por_defecto() -> None:
    """
    Las vistas de `mart`, `cierre`, `compras` y `retenciones` se recrean con
    DROP + CREATE en cada build: sin el privilegio por defecto nacerían
    ilegibles. La exclusión de `raw` no puede llevárselo por delante.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp"]
    )

    for esquema in ("mart", "cierre", "compras", "maestro", "retenciones", "stg", "aux", "_meta"):
        esperada = (
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "{esquema}" '
            f'GRANT SELECT ON TABLES TO "{ROL}"'
        )
        assert esperada in sentencias, f"{esquema} ha perdido su privilegio por defecto"


def test_f068_r2_sin_propietario_configurado_tambien_se_revoca() -> None:
    """En local no hay rol de grupo: la regla aplica al rol de la sesión."""
    sentencias = build_readonly_grant_statements(
        ROL, "", ["raw"], excluded_tables=["raw.emp"]
    )

    assert (
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA "raw" REVOKE SELECT ON TABLES FROM "{ROL}"'
        in sentencias
    )
    assert not any("FOR ROLE" in s for s in sentencias)


# ---------------------------------------------------------------------------
# R4, R5 · los bordes de la lista
# ---------------------------------------------------------------------------

def test_f068_r4_exclusion_de_un_esquema_no_concedido_no_emite_nada() -> None:
    """
    Si mañana se saca `raw` de PG_CONSUMPTION_SCHEMAS (la salida (a) de la
    ficha), no hay nada que revocar: revocar sobre un esquema que no se toca
    solo serviría para reventar el paso si la tabla no existiera.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, ["mart", "cierre"], excluded_tables=["raw.emp"]
    )

    assert not any("REVOKE" in s for s in sentencias)
    assert not any('"raw"' in s for s in sentencias)


@pytest.mark.parametrize(
    "entrada",
    ["emp", "raw.", ".emp", "raw.emp.col", "raw..emp", "."],
)
def test_f068_r5_una_entrada_malformada_revienta(entrada: str) -> None:
    """
    Falla ruidosamente, y no en silencio. Una exclusión mal escrita que se
    ignorase dejaría los datos personales legibles con la configuración puesta
    y con toda la pinta de estar protegidos: es el peor de los desenlaces.
    """
    with pytest.raises(ValueError, match=re.escape("'esquema.tabla'")):
        build_readonly_grant_statements(
            ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=[entrada]
        )


def test_f068_r5_identificadores_citados_y_a_prueba_de_inyeccion() -> None:
    """El nombre de la tabla se cita, como el resto de identificadores."""
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, ["raw"], excluded_tables=['raw.tabla"rara']
    )

    revoke = next(
        s for s in sentencias if s.startswith("REVOKE ALL PRIVILEGES ON TABLE")
    )
    assert '"raw"."tabla""rara"' in revoke


def test_f068_r5_el_revoke_es_lo_unico_que_lleva_all_privileges() -> None:
    """
    Barrido de seguridad de F-005 conservado: sigue sin haber ni una sentencia
    que CONCEDA escritura. `ALL PRIVILEGES` solo puede aparecer quitando.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp", "raw.res"]
    )

    concesiones = "\n".join(s for s in sentencias if not s.startswith("REVOKE"))
    for prohibido in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALL PRIVILEGES"):
        assert prohibido not in concesiones

    for s in sentencias:
        if "ALL PRIVILEGES" in s:
            assert s.startswith("REVOKE"), s


# ---------------------------------------------------------------------------
# R6 · el defecto de configuración
# ---------------------------------------------------------------------------

def test_f068_r6_el_defecto_excluye_emp_y_res() -> None:
    """
    `raw.emp` trae DNI, número de la Seguridad Social y cuenta bancaria.
    `raw.res` trae el NIF de la persona en `cif` (626 filas informadas) y las
    credenciales de acceso a Sigrid: la ficha de F-068 la daba por limpia, y no
    lo está. Las dos van excluidas por defecto.
    """
    from config.settings import DEFAULT_EXCLUDED_TABLES

    declaradas = [t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()]
    assert declaradas == ["raw.emp", "raw.res"]


def test_f068_r6_la_lista_es_parametrizable_por_entorno() -> None:
    """
    Es una lista declarada, no un apaño: mañana entra otra tabla con datos
    personales y se añade aquí. Y el día que el MCP tenga control por usuario,
    el humano la vacía con PG_EXCLUDED_TABLES sin tocar código.
    """
    from config.settings import PostgresSettings

    por_defecto = PostgresSettings(_env_file=None)
    assert por_defecto.excluded_table_list == ["raw.emp", "raw.res"]

    ampliada = PostgresSettings(_env_file=None, excluded_tables=" raw.emp , raw.res ,raw.per ")
    assert ampliada.excluded_table_list == ["raw.emp", "raw.res", "raw.per"]

    vacia = PostgresSettings(_env_file=None, excluded_tables="")
    assert vacia.excluded_table_list == []


def test_f068_r6_env_example_documenta_la_variable() -> None:
    """Quien monte el entorno tiene que ver la variable y su motivo."""
    texto = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PG_EXCLUDED_TABLES" in texto


# ---------------------------------------------------------------------------
# R7 · el paso del pipeline y el cliente
# ---------------------------------------------------------------------------

class _ClienteFalso:
    """Cliente Postgres de mentira: apunta qué se le pide y no abre nada."""

    def __init__(self) -> None:
        self.recibido: dict[str, object] = {}

    def role_exists(self, role: str) -> bool:
        return True

    def apply_readonly_grants(
        self,
        readonly_role: str,
        owner_role: str,
        schemas: object,
        excluded_tables: object = (),
    ) -> list[str]:
        self.recibido = {
            "readonly_role": readonly_role,
            "owner_role": owner_role,
            "schemas": list(schemas),  # type: ignore[call-overload]
            "excluded_tables": list(excluded_tables),  # type: ignore[call-overload]
        }
        return ["GRANT ..."]


def test_f068_r7_el_paso_pasa_la_lista_de_exclusion_al_cliente() -> None:
    """
    Aquí es donde se cierra el agujero: `apply_grants` corre como último paso
    de CADA noche, así que si el paso no lleva la lista, la nocturna devuelve
    el permiso al día siguiente y la revocación manual dura 24 horas.
    """
    cliente = _ClienteFalso()
    settings = SimpleNamespace(
        postgres=SimpleNamespace(
            readonly_role=ROL,
            set_role=DUENO,
            consumption_schema_list=["mart", "raw"],
            excluded_table_list=["raw.emp", "raw.res"],
        )
    )

    resultado = ApplyGrantsStep(settings, client=cliente).run()

    assert resultado.status == StepStatus.SUCCESS
    assert cliente.recibido["excluded_tables"] == ["raw.emp", "raw.res"]
    assert resultado.metadata["tablas_excluidas"] == ["raw.emp", "raw.res"]


def test_f068_r7_el_cliente_solo_revoca_sobre_las_tablas_que_existen() -> None:
    """
    Un REVOKE sobre una tabla inexistente da error y tumbaría el paso. Es el
    mismo criterio con el que `apply_readonly_grants` ya filtra los esquemas.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    ejecutadas: list[str] = []

    class _Cursor:
        def execute(self, stmt: str) -> None:
            ejecutadas.append(stmt)

        def __enter__(self) -> _Cursor:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    class _Conn:
        def cursor(self) -> _Cursor:
            return _Cursor()

        def __enter__(self) -> _Conn:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    cliente = PostgresClient.__new__(PostgresClient)
    cliente._target_db = "sigrid_dm"  # type: ignore[attr-defined]
    cliente.list_schemas = lambda: ["raw", "mart"]  # type: ignore[method-assign]
    cliente.table_exists = lambda esquema, tabla: tabla == "emp"  # type: ignore[method-assign]
    cliente.connection = lambda: _Conn()  # type: ignore[method-assign]

    cliente.apply_readonly_grants(
        readonly_role=ROL,
        owner_role=DUENO,
        schemas=["raw", "mart"],
        excluded_tables=["raw.emp", "raw.fantasma"],
    )

    revokes = [
        s for s in ejecutadas if s.startswith("REVOKE ALL PRIVILEGES ON TABLE")
    ]
    assert revokes == [f'REVOKE ALL PRIVILEGES ON TABLE "raw"."emp" FROM "{ROL}"']


# ---------------------------------------------------------------------------
# R8 · el SQL de provisión dice lo mismo que el código
# ---------------------------------------------------------------------------

def test_f068_r8_02_roles_excluye_las_mismas_tablas_que_el_codigo() -> None:
    """
    `02_roles.sql` es lo que se aplica al crear el rol DESDE CERO. Si dijera
    otra cosa que el código, un rol recién provisionado nacería con los datos
    personales legibles hasta la primera nocturna.
    """
    from config.settings import DEFAULT_EXCLUDED_TABLES

    sql = (REPO_ROOT / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")

    declaradas = {t.strip() for t in DEFAULT_EXCLUDED_TABLES.split(",") if t.strip()}
    en_sql = set(re.findall(r"'(raw\.[a-z_]+)'", sql))

    assert en_sql == declaradas, (
        f"02_roles.sql excluye {sorted(en_sql)} y el código {sorted(declaradas)}"
    )

    # Y lo hace con las dos mitades: quitar el permiso y quitar la regla que
    # lo devolvería sola.
    assert "REVOKE ALL PRIVILEGES ON TABLE" in sql
    assert "ALTER DEFAULT PRIVILEGES" in sql and "REVOKE SELECT ON TABLES" in sql


def test_f068_r8_esta_escrito_que_es_temporal() -> None:
    """
    Requisito explícito del humano: la reversión ya está decidida, condicionada
    a que el MCP tenga control por usuario. Que nadie lo lea dentro de seis
    meses como una prohibición permanente.
    """
    settings_py = (REPO_ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    roles_sql = (REPO_ROOT / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")
    ficha = (REPO_ROOT / "config" / "diccionario" / "raw.yaml").read_text(encoding="utf-8")

    for nombre, texto in (
        ("config/settings.py", settings_py),
        ("infra/sql/02_roles.sql", roles_sql),
        ("config/diccionario/raw.yaml", ficha),
    ):
        assert "TEMPORAL" in texto, f"{nombre} no dice que la exclusión es temporal"
        assert "F-068" in texto, f"{nombre} no cita la feature que lo decidió"


# ---------------------------------------------------------------------------
# R9 · la regla del catálogo no depende de que la tabla exista HOY
# ---------------------------------------------------------------------------
#
# El agujero que cerró la revisión de F-068: el cliente filtraba de la lista de
# exclusión las tablas que no existen —necesario para el `REVOKE ... ON TABLE`,
# que fallaría sobre una tabla ausente— y la función pura derivaba de ESA lista
# ya filtrada qué esquemas cambian su `ALTER DEFAULT PRIVILEGES`. Resultado: un
# `DROP` de `raw.emp` desactivaba solo la mitad que protege el futuro, la
# nocturna reponía la regla del catálogo y la siguiente `raw.emp` nacía
# legible. Es justo el escenario para el que se diseñó la segunda mitad.


def test_f068_r9_el_catalogo_se_revoca_aunque_la_tabla_no_exista() -> None:
    """
    La regla de `ALTER DEFAULT PRIVILEGES` se declara sobre el ESQUEMA, no
    sobre la tabla: no necesita que la tabla exista y es precisamente lo que
    protege a la tabla que aún no ha nacido.
    """
    sentencias = build_readonly_grant_statements(
        ROL,
        DUENO,
        TODOS_LOS_ESQUEMAS,
        excluded_tables=["raw.emp", "raw.res"],
        missing_tables=["raw.emp", "raw.res"],
    )

    esperada = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'REVOKE SELECT ON TABLES FROM "{ROL}"'
    )
    assert esperada in sentencias, (
        "sin ninguna de las tablas excluidas presente se deja de revocar el "
        "privilegio por defecto de raw: la siguiente tabla nacería legible"
    )

    prohibida = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'GRANT SELECT ON TABLES TO "{ROL}"'
    )
    assert prohibida not in sentencias


def test_f068_r9_la_tabla_ausente_no_recibe_revoke_de_tabla() -> None:
    """
    La otra mitad sigue filtrándose: un `REVOKE ... ON TABLE` sobre una tabla
    que no existe da error y tumbaría el paso. Las dos listas son distintas y
    cada una manda sobre lo suyo.
    """
    sentencias = build_readonly_grant_statements(
        ROL,
        DUENO,
        TODOS_LOS_ESQUEMAS,
        excluded_tables=["raw.emp", "raw.res"],
        missing_tables=["raw.res"],
    )

    revokes_de_tabla = [
        s for s in sentencias if s.startswith("REVOKE ALL PRIVILEGES ON TABLE")
    ]
    assert revokes_de_tabla == [
        f'REVOKE ALL PRIVILEGES ON TABLE "raw"."emp" FROM "{ROL}"'
    ]


def test_f068_r9_sin_lista_de_ausentes_se_revoca_todo_lo_declarado() -> None:
    """
    El defecto es el seguro: quien no diga qué falta, revoca lo declarado. Un
    llamante que se olvide del parámetro falla ruidosamente contra la BBDD, no
    en silencio dejando la tabla legible.
    """
    sentencias = build_readonly_grant_statements(
        ROL, DUENO, TODOS_LOS_ESQUEMAS, excluded_tables=["raw.emp", "raw.res"]
    )

    revokes_de_tabla = [
        s for s in sentencias if s.startswith("REVOKE ALL PRIVILEGES ON TABLE")
    ]
    assert len(revokes_de_tabla) == 2


def test_f068_r9_el_cliente_mantiene_el_catalogo_tras_un_drop() -> None:
    """
    El test de extremo a extremo del agujero, con el cliente real: `raw.emp`
    no existe (un DROP manual, o una tabla de personal que aún no se ha
    ingerido) y la nocturna NO puede reponer el privilegio por defecto de
    `raw`, porque entonces la siguiente `raw.emp` nacería legible.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

    ejecutadas: list[str] = []

    class _Cursor:
        def execute(self, stmt: str) -> None:
            ejecutadas.append(stmt)

        def __enter__(self) -> _Cursor:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    class _Conn:
        def cursor(self) -> _Cursor:
            return _Cursor()

        def __enter__(self) -> _Conn:
            return self

        def __exit__(self, *a: object) -> None:
            return None

    cliente = PostgresClient.__new__(PostgresClient)
    cliente._target_db = "sigrid_dm"  # type: ignore[attr-defined]
    cliente.list_schemas = lambda: ["raw", "mart"]  # type: ignore[method-assign]
    cliente.table_exists = lambda esquema, tabla: False  # type: ignore[method-assign]
    cliente.connection = lambda: _Conn()  # type: ignore[method-assign]

    cliente.apply_readonly_grants(
        readonly_role=ROL,
        owner_role=DUENO,
        schemas=["raw", "mart"],
        excluded_tables=["raw.emp", "raw.res"],
    )

    revoke_catalogo = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'REVOKE SELECT ON TABLES FROM "{ROL}"'
    )
    grant_catalogo = (
        f'ALTER DEFAULT PRIVILEGES FOR ROLE "{DUENO}" IN SCHEMA "raw" '
        f'GRANT SELECT ON TABLES TO "{ROL}"'
    )
    assert revoke_catalogo in ejecutadas
    assert grant_catalogo not in ejecutadas, (
        "con las tablas excluidas ausentes la nocturna repone la regla del "
        "catálogo sobre raw: la siguiente raw.emp nace legible"
    )

    # Y no intenta revocar sobre tablas que no existen, que era el motivo del
    # filtro.
    assert not any(s.startswith("REVOKE ALL PRIVILEGES ON TABLE") for s in ejecutadas)


# ---------------------------------------------------------------------------
# R10 · el fichero de provisión, sin ventana y sin esquemas a mano
# ---------------------------------------------------------------------------


def test_f068_r10_el_grant_y_su_revoke_van_en_una_transaccion() -> None:
    """
    `psql` sin `BEGIN` explícito confirma cada sentencia por separado: entre el
    GRANT del punto 5 y el primer REVOKE del 5 bis las tablas quedan legibles,
    y si el script muere ahí con ON_ERROR_STOP quedan legibles Y confirmadas.
    Las dos mitades tienen que ser atómicas.
    """
    sql = (REPO_ROOT / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")

    apertura = sql.index("\nBEGIN;")
    cierre = sql.index("\nCOMMIT;")
    grant_esquemas = sql.index("GRANT SELECT ON ALL TABLES IN SCHEMA")
    ultimo_revoke = sql.rindex("REVOKE SELECT ON TABLES FROM")

    assert apertura < grant_esquemas, "el GRANT del punto 5 queda fuera de la transacción"
    assert ultimo_revoke < cierre, "el REVOKE del punto 5 bis queda fuera de la transacción"


def test_f068_r10_el_esquema_del_catalogo_no_esta_escrito_a_mano() -> None:
    """
    `grants.py` deriva de la lista qué esquemas cambian su privilegio por
    defecto; este fichero escribía `raw` a mano. Con una exclusión en otro
    esquema (PG_EXCLUDED_TABLES) la nocturna lo resolvería y el fichero de
    provisión no, y el rol nacería con la regla puesta sobre ese esquema.
    """
    sql = (REPO_ROOT / "infra" / "sql" / "02_roles.sql").read_text(encoding="utf-8")

    assert "ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA raw " not in sql, (
        "el esquema del ALTER DEFAULT PRIVILEGES del punto 5 bis sigue escrito "
        "a mano; hay que derivarlo de la lista de tablas excluidas"
    )
    assert "split_part(objeto, '.', 1)" in sql
