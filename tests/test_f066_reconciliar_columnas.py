# tests/test_f066_reconciliar_columnas.py
"""
F-066 · Reconciliación de columnas de una tabla `raw` que YA existe (R25-R28).

El defecto que estos tests fijan tumbó la nocturna dos veces seguidas
—`k251zrq` (2026-09-07 16:02 UTC) y `29813760` (2026-09-08 00:00 UTC)— con

    psycopg.errors.UndefinedColumn:
        column "pagtex" of relation "dcf" does not exist

F-066 dejó de excluir `pagfor` y `pagtex` de `dcf`, pero `raw.dcf` ya existía
en Azure sin esas dos columnas. `ensure_raw_table` emitía `CREATE TABLE IF NOT
EXISTS` y **nada más**: con la tabla ya creada no reconciliaba nada, y el
`COPY` posterior nombraba columnas que no estaban. Las 25 tablas nuevas de
F-066 no dieron problema porque nacen de cero; el fallo solo aparece cuando
cambian las columnas de una tabla **preexistente**, que es justo lo que no se
ve en local contra una base vacía.

Sin red y sin BBDD: el cliente Postgres nunca llega a `psycopg` (se sustituye
`_connect`, su única puerta de conexión) y el step se ejecuta contra dobles.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from etl_sigrid.domain.entities import ColumnSpec, TableSpec
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class _CursorFalso:
    """Cursor que apunta el SQL que se le ejecuta y contesta el catálogo dado."""

    def __init__(self, catalogo: list[tuple[str, str]]) -> None:
        self._catalogo = catalogo
        self.ejecutadas: list[str] = []
        self.parametros: list[Any] = []

    def __enter__(self) -> _CursorFalso:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, consulta: Any, parametros: Any = None) -> None:
        texto = consulta if isinstance(consulta, str) else consulta.as_string(None)
        self.ejecutadas.append(texto)
        self.parametros.append(parametros)

    def fetchall(self) -> list[tuple[str, str]]:
        return list(self._catalogo)

    def fetchone(self) -> tuple | None:
        return None


class _ConexionFalsa:
    """Conexión que no abre nada. Solo sirve un cursor y se deja cerrar."""

    def __init__(self, catalogo: list[tuple[str, str]]) -> None:
        self.cursor_falso = _CursorFalso(catalogo)
        self.commits = 0

    def cursor(self) -> _CursorFalso:
        return self.cursor_falso

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:  # pragma: no cover - solo si algo revienta
        pass

    def close(self) -> None:
        pass


def _cliente(
    monkeypatch: pytest.MonkeyPatch, catalogo: list[tuple[str, str]]
) -> tuple[PostgresClient, _CursorFalso]:
    """Cliente Postgres con cadenas de mentira y una conexión de juguete."""
    cliente = PostgresClient(
        conninfo="dbname=de_mentira",
        admin_conninfo="dbname=admin_de_mentira",
        target_db="sigrid_dm",
    )
    cliente._bootstrap_done = True  # nadie va a crear ninguna base aquí
    conexion = _ConexionFalsa(catalogo)
    monkeypatch.setattr(cliente, "_connect", lambda *a, **k: conexion)
    return cliente, conexion.cursor_falso


def _col(nombre: str, tipo: str = "varchar", *, largo: int | None = 30,
         nullable: bool = True) -> ColumnSpec:
    return ColumnSpec(
        name=nombre,
        sql_server_type=tipo,
        char_max_length=largo,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=nullable,
    )


#: Las tres columnas con las que `raw.dcf` vivía en Azure antes de F-066, tal
#: y como las devuelve el catálogo de Postgres (`format_type`).
_DCF_EN_AZURE: list[tuple[str, str]] = [
    ("ide", "integer"),
    ("cod", "character varying(30)"),
    ("_ingested_at", "timestamp without time zone"),
    ("_source_tiemod", "double precision"),
]

#: Y las que F-066 espera desde que dejó de excluir `pagfor` y `pagtex`.
_DCF_ESPERADA: list[ColumnSpec] = [
    _col("ide", "int", largo=None, nullable=False),
    _col("cod", "varchar", largo=30),
    _col("pagfor", "int", largo=None),
    _col("pagtex", "varchar", largo=50),
]


# ---------------------------------------------------------------------------
# R25 · A una tabla que ya existe se le AÑADEN las columnas que le faltan
# ---------------------------------------------------------------------------


def test_f066_r25_una_tabla_preexistente_recibe_las_columnas_que_le_faltan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El caso exacto de la nocturna caída: `raw.dcf` sin `pagfor` ni `pagtex`.

    Sin esto, `ensure_raw_table` se queda en el `CREATE TABLE IF NOT EXISTS`,
    que con la tabla ya creada no hace nada, y el `COPY` siguiente revienta.
    """
    cliente, cursor = _cliente(monkeypatch, _DCF_EN_AZURE)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    alters = [s for s in cursor.ejecutadas if "ALTER TABLE" in s]
    assert len(alters) == 1, (
        f"se esperaba UNA sola sentencia ALTER TABLE; se emitieron {len(alters)}: "
        f"{cursor.ejecutadas}"
    )
    assert '"pagfor"' in alters[0] and '"pagtex"' in alters[0], (
        f"faltan columnas en el ALTER: {alters[0]}"
    )
    assert alters[0].count("ADD COLUMN") == 2, (
        f"las dos columnas que faltan van en el mismo ALTER: {alters[0]}"
    )


def test_f066_r25_la_columna_que_ya_esta_no_se_vuelve_a_anadir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solo se añade lo que falta: `ide` y `cod` ya están y no se tocan."""
    cliente, cursor = _cliente(monkeypatch, _DCF_EN_AZURE)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    alter = next(s for s in cursor.ejecutadas if "ALTER TABLE" in s)
    assert '"ide"' not in alter and '"cod"' not in alter, (
        f"se está añadiendo una columna que ya existe: {alter}"
    )


def test_f066_r25_una_tabla_al_dia_no_emite_ningun_alter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La noche normal —esquema sin cambios— no toca el DDL de nada."""
    catalogo = _DCF_EN_AZURE + [
        ("pagfor", "integer"),
        ("pagtex", "character varying(50)"),
    ]
    cliente, cursor = _cliente(monkeypatch, catalogo)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    assert not [s for s in cursor.ejecutadas if "ALTER TABLE" in s], (
        f"esquema al día y aun así se emite DDL: {cursor.ejecutadas}"
    )


def test_f066_r25_las_columnas_tecnicas_no_entran_en_la_comparacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_ingested_at` y `_source_tiemod` las pone el ETL, no Sigrid.

    Si entraran en la comparación se leerían como columnas «sobrantes» del
    destino y ensuciarían el log con un aviso falso cada noche y cada tabla.
    """
    catalogo = _DCF_EN_AZURE + [
        ("pagfor", "integer"),
        ("pagtex", "character varying(50)"),
    ]
    cliente, _ = _cliente(monkeypatch, catalogo)
    avisos: list[tuple[str, dict[str, Any]]] = []
    _capturar_avisos(monkeypatch, avisos)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    assert avisos == [], f"las columnas técnicas han provocado avisos: {avisos}"


# ---------------------------------------------------------------------------
# R26 · La columna añadida nace NULL, porque la tabla ya tiene filas
# ---------------------------------------------------------------------------


def test_f066_r26_la_columna_anadida_nace_null_aunque_el_origen_la_declare_not_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ADD COLUMN ... NOT NULL` sobre una tabla con filas falla en Postgres.

    `dcf` tiene 165.391 facturas cargadas: la columna nueva nace vacía por
    definición, así que se declara NULL pase lo que pase en el origen.
    """
    esperadas = [
        _col("ide", "int", largo=None, nullable=False),
        _col("cod", "varchar", largo=30),
        _col("pagfor", "int", largo=None, nullable=False),  # NOT NULL en Sigrid
    ]
    cliente, cursor = _cliente(monkeypatch, _DCF_EN_AZURE)

    cliente.ensure_raw_table("dcf", esperadas, primary_key="ide")

    alter = next(s for s in cursor.ejecutadas if "ALTER TABLE" in s)
    assert "NOT NULL" not in alter, (
        f"la columna añadida no puede nacer NOT NULL sobre una tabla con filas: {alter}"
    )
    assert "NULL" in alter, f"la columna añadida debe declararse NULL: {alter}"


def test_f066_r26_la_columna_anadida_lleva_su_tipo_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El tipo sale del mapeo de `ColumnSpec`, no de un TEXT de conveniencia."""
    cliente, cursor = _cliente(monkeypatch, _DCF_EN_AZURE)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    alter = next(s for s in cursor.ejecutadas if "ALTER TABLE" in s)
    assert "VARCHAR(50)" in alter, f"`pagtex` debe nacer VARCHAR(50): {alter}"
    assert "INTEGER" in alter, f"`pagfor` debe nacer INTEGER: {alter}"


# ---------------------------------------------------------------------------
# R27 · Solo se añade: nunca se borra una columna ni se cambia un tipo
# ---------------------------------------------------------------------------


def _capturar_avisos(
    monkeypatch: pytest.MonkeyPatch, destino: list[tuple[str, dict[str, Any]]]
) -> None:
    """Sustituye `logger.warning` del cliente por un testigo."""
    from etl_sigrid.infrastructure.postgres import postgres_client as pc

    def _warning(evento: str, **kwargs: Any) -> None:
        destino.append((evento, kwargs))

    monkeypatch.setattr(pc.logger, "warning", _warning)


def test_f066_r27_una_columna_que_el_origen_ya_no_trae_se_avisa_y_no_se_borra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borrar sincronizando destruiría datos: el ETL avisa y sigue.

    Regla aprobada por el humano el 2026-09-08 y no negociable.
    """
    catalogo = _DCF_EN_AZURE + [("bor", "character varying(10)")]
    esperadas = [
        _col("ide", "int", largo=None, nullable=False),
        _col("cod", "varchar", largo=30),
    ]
    cliente, cursor = _cliente(monkeypatch, catalogo)
    avisos: list[tuple[str, dict[str, Any]]] = []
    _capturar_avisos(monkeypatch, avisos)

    cliente.ensure_raw_table("dcf", esperadas, primary_key="ide")

    assert not any("DROP COLUMN" in s for s in cursor.ejecutadas), (
        f"el ETL NUNCA borra una columna de raw: {cursor.ejecutadas}"
    )
    assert any("bor" in str(kwargs.values()) for _, kwargs in avisos), (
        f"la columna sobrante `bor` tiene que salir en el log: {avisos}"
    )


def test_f066_r27_un_tipo_que_cambia_se_avisa_y_no_se_altera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cambiar un tipo en caliente puede truncar dato: se avisa y se sigue."""
    catalogo = [
        ("ide", "integer"),
        ("cod", "character varying(10)"),  # en Sigrid ya es varchar(30)
        ("_ingested_at", "timestamp without time zone"),
    ]
    esperadas = [
        _col("ide", "int", largo=None, nullable=False),
        _col("cod", "varchar", largo=30),
    ]
    cliente, cursor = _cliente(monkeypatch, catalogo)
    avisos: list[tuple[str, dict[str, Any]]] = []
    _capturar_avisos(monkeypatch, avisos)

    cliente.ensure_raw_table("dcf", esperadas, primary_key="ide")

    assert not any("ALTER COLUMN" in s for s in cursor.ejecutadas), (
        f"el ETL NUNCA cambia el tipo de una columna: {cursor.ejecutadas}"
    )
    assert avisos, "un tipo que ya no casa tiene que salir en el log"
    evento, kwargs = avisos[0]
    assert "cod" in str(kwargs.values()), f"el aviso debe nombrar la columna: {kwargs}"
    assert "dcf" in str(kwargs.values()), f"el aviso debe nombrar la tabla: {kwargs}"


def test_f066_r27_un_tipo_equivalente_escrito_distinto_no_dispara_aviso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`character varying(30)` y `VARCHAR(30)` son el mismo tipo.

    Sin normalización, cada noche saldría un aviso por columna de cada tabla y
    el log dejaría de servir para ver los cambios de verdad.
    """
    catalogo = [
        ("ide", "integer"),
        ("cod", "character varying(30)"),
        ("fec", "timestamp without time zone"),
        ("imp", "numeric(18, 4)"),
        ("baj", "boolean"),
    ]
    esperadas = [
        _col("ide", "int", largo=None, nullable=False),
        _col("cod", "varchar", largo=30),
        _col("fec", "datetime", largo=None),
        ColumnSpec(
            name="imp",
            sql_server_type="decimal",
            char_max_length=None,
            numeric_precision=18,
            numeric_scale=4,
            is_nullable=True,
        ),
        _col("baj", "bit", largo=None),
    ]
    cliente, cursor = _cliente(monkeypatch, catalogo)
    avisos: list[tuple[str, dict[str, Any]]] = []
    _capturar_avisos(monkeypatch, avisos)

    cliente.ensure_raw_table("dcf", esperadas, primary_key="ide")

    assert avisos == [], f"tipos equivalentes y aun así avisa: {avisos}"
    assert not [s for s in cursor.ejecutadas if "ALTER TABLE" in s]


def test_f066_r27_la_reconciliacion_solo_emite_add_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Barrido: en el peor caso —falta una, sobra otra y una tercera cambia de
    tipo— el único DDL que sale es `ADD COLUMN`."""
    catalogo = [
        ("ide", "integer"),
        ("cod", "character varying(10)"),  # tipo cambiado
        ("bor", "text"),  # sobrante
        ("_ingested_at", "timestamp without time zone"),
    ]
    esperadas = [
        _col("ide", "int", largo=None, nullable=False),
        _col("cod", "varchar", largo=30),
        _col("pagtex", "varchar", largo=50),  # faltante
    ]
    cliente, cursor = _cliente(monkeypatch, catalogo)
    _capturar_avisos(monkeypatch, [])

    cliente.ensure_raw_table("dcf", esperadas, primary_key="ide")

    ddl = " ".join(cursor.ejecutadas)
    assert "DROP" not in ddl, f"nunca se borra nada: {ddl}"
    assert "ALTER COLUMN" not in ddl, f"nunca se cambia un tipo: {ddl}"
    assert "ADD COLUMN" in ddl, f"lo que falta sí se añade: {ddl}"


# ---------------------------------------------------------------------------
# R28 · El orden: reconciliar ANTES del TRUNCATE, y dejar traza de cada ADD
# ---------------------------------------------------------------------------


def test_f066_r28_la_reconciliacion_va_antes_del_truncate() -> None:
    """Si el DDL fallase después del TRUNCATE, la tabla quedaría vacía Y sin la
    columna: se habría destruido la carga de ayer sin poder cargar la de hoy.

    Reconciliar primero deja el dato viejo intacto cuando el esquema no se
    puede arreglar. Además `ADD COLUMN` sin `DEFAULT` es metadato puro: no
    reescribe la tabla, así que hacerlo antes del TRUNCATE no cuesta nada.
    """
    from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep

    class _ApiFalsa:
        def fetch_table_schema(self, tabla: str) -> list[ColumnSpec]:
            return [_col("ide", "int", largo=None, nullable=False)]

        def stream_table(self, *args: object, **kwargs: object):
            yield [{"ide": 1}]

    class _PgFalso:
        def __init__(self) -> None:
            self.traza: list[str] = []

        def record_run_start(self, *args: object, **kwargs: object) -> int:
            return 1

        def record_run_end(self, *args: object, **kwargs: object) -> None:
            pass

        def ensure_raw_table(self, *args: object, **kwargs: object) -> None:
            self.traza.append("ensure")

        def truncate_table(self, schema: str, table: str) -> None:
            self.traza.append("truncate")

        def get_max_id(self, *args: object, **kwargs: object) -> int:
            return 0

        def copy_rows(self, **kwargs: object) -> int:
            self.traza.append("copy")
            return 1

    ajustes = SimpleNamespace(sigrid_api=SimpleNamespace(page_size=10_000))
    pg = _PgFalso()
    paso = IngestRawStep(ajustes, full_refresh=True, batch_id="b")  # type: ignore[arg-type]

    paso._ingest_one_table(TableSpec(source_table="dcf", target_table="dcf"), _ApiFalsa(), pg)

    assert pg.traza.index("ensure") < pg.traza.index("truncate"), (
        f"el esquema se arregla ANTES de vaciar la tabla: {pg.traza}"
    )
    assert pg.traza.index("truncate") < pg.traza.index("copy")


def test_f066_r28_cada_add_column_deja_su_linea_en_el_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Es un cambio de esquema en producción: tiene que verse en la traza.

    Sin esta línea, la noche que el ETL añada una columna a una tabla de 2,1 M
    filas no quedaría constancia de quién la creó ni cuándo.
    """
    from etl_sigrid.infrastructure.postgres import postgres_client as pc

    cliente, _ = _cliente(monkeypatch, _DCF_EN_AZURE)
    eventos: list[tuple[str, dict[str, Any]]] = []

    def _info(evento: str, **kwargs: Any) -> None:
        eventos.append((evento, kwargs))

    monkeypatch.setattr(pc.logger, "info", _info)

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    nombradas = {
        kwargs.get("column")
        for _, kwargs in eventos
        if kwargs.get("column") is not None
    }
    assert {"pagfor", "pagtex"} <= nombradas, (
        f"cada columna añadida deja su propia línea de log: {eventos}"
    )
    assert any("dcf" in str(kwargs.get("table", "")) for _, kwargs in eventos), (
        f"el log tiene que nombrar la tabla: {eventos}"
    )


def test_f066_r28_un_catalogo_vacio_no_intenta_reconciliar_nada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Si el catálogo no devuelve la tabla, no se inventa un ALTER a ciegas."""
    cliente, cursor = _cliente(monkeypatch, [])

    cliente.ensure_raw_table("dcf", _DCF_ESPERADA, primary_key="ide")

    assert not [s for s in cursor.ejecutadas if "ALTER TABLE" in s], (
        f"sin catálogo no hay nada que reconciliar: {cursor.ejecutadas}"
    )


# ---------------------------------------------------------------------------
# R27 · `_tipo_normalizado` a solas: es quien decide si un tipo «ya no casa»
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("escrito_por_el_etl", "devuelto_por_el_catalogo"),
    [
        ("VARCHAR(30)", "character varying(30)"),
        ("NUMERIC(18,4)", "numeric(18, 4)"),
        ("TIMESTAMP", "timestamp without time zone"),
        ("TIME", "time without time zone"),
        ("DOUBLE PRECISION", "double precision"),
        ("BOOLEAN", "boolean"),
        ("TEXT", "text"),
        ("INTEGER", "integer"),
        ("BYTEA", "bytea"),
    ],
)
def test_f066_r27_los_dos_nombres_del_mismo_tipo_se_normalizan_igual(
    escrito_por_el_etl: str, devuelto_por_el_catalogo: str
) -> None:
    """Las dos caras de cada tipo: la que escribe el DDL y la que lee el
    catálogo. Si alguna pareja dejara de casar, el ETL avisaría cada noche de
    un cambio de tipo que no ha ocurrido."""
    from etl_sigrid.infrastructure.postgres.postgres_client import _tipo_normalizado

    assert _tipo_normalizado(escrito_por_el_etl) == _tipo_normalizado(
        devuelto_por_el_catalogo
    )


@pytest.mark.parametrize(
    ("uno", "otro"),
    [
        ("VARCHAR(30)", "character varying(10)"),  # cambia el largo
        ("TIMESTAMP", "timestamp with time zone"),  # cambia la zona
        ("NUMERIC(18,4)", "numeric(18,2)"),  # cambia la escala
        ("INTEGER", "bigint"),  # cambia el ancho
        ("TEXT", "bytea"),  # cambia todo
    ],
)
def test_f066_r27_dos_tipos_distintos_no_se_normalizan_al_mismo(
    uno: str, otro: str
) -> None:
    """La otra mitad: normalizar no puede llegar a igualar lo que sí difiere,
    o el aviso no saltaría nunca y el arreglo seria ciego a un cambio real."""
    from etl_sigrid.infrastructure.postgres.postgres_client import _tipo_normalizado

    assert _tipo_normalizado(uno) != _tipo_normalizado(otro)


def test_f066_r27_un_tipo_con_parentesis_sin_cerrar_no_revienta() -> None:
    """Nada garantiza que `format_type` devuelva siempre algo bien formado, y
    esta función corre en la ingesta de las 56 tablas: si tropieza, tumba la
    noche entera por un aviso que ni siquiera era un error."""
    from etl_sigrid.infrastructure.postgres.postgres_client import _tipo_normalizado

    assert _tipo_normalizado("varchar(30") == "varchar(30"
    assert _tipo_normalizado("") == ""
