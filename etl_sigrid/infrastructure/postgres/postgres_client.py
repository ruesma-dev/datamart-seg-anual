# etl_sigrid/infrastructure/postgres/postgres_client.py
"""
Cliente Postgres del ETL. Responsabilidades:

  1. Auto-bootstrap perezoso: la primera vez que cualquier método toca Postgres,
     se asegura de que la BBDD existe (la crea si no), los schemas están creados,
     y la tabla _meta.etl_runs existe. El usuario no tiene que ejecutar nada
     manualmente.
  2. Conectarse con psycopg 3.
  3. Crear dinámicamente tablas raw.* a partir de la metadata de Sigrid
     (CREATE TABLE IF NOT EXISTS con tipos derivados de INFORMATION_SCHEMA).
  4. Cargar masivamente con COPY FROM STDIN (10-100x más rápido que INSERT).
  5. Soportar carga incremental (cursor sobre MAX(ide) ya cargado).

Toda la mecánica está encapsulada aquí. Los Steps de la capa application no
saben de psycopg, solo invocan métodos limpios.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from etl_sigrid.domain.entities import ColumnSpec
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.conninfo import safe_dsn
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements

logger = get_logger(__name__)


# Schemas del data mart
SCHEMAS = ("raw", "aux", "stg", "mart", "_meta")

# Una cadena de conexión, o algo que la produzca. Es callable porque con
# autenticación Entra la "contraseña" es un token que caduca y hay que
# resolverlo en cada conexión, no una vez al arrancar.
ConnInfo = str | Callable[[], str]


class PostgresClient:
    """
    Cliente Postgres con auto-bootstrap perezoso.

    Constructor:
        conninfo       : conexión a la BBDD del data mart (ej. sigrid_dm)
        admin_conninfo : conexión a una BBDD admin existente (ej. postgres) para
                         poder hacer CREATE DATABASE si la nuestra no existe
        target_db      : nombre de la BBDD a crear si no existe
        auto_create_db : si es False, NUNCA se ejecuta CREATE DATABASE ni se
                         abre conexión contra la BBDD admin; la base tiene que
                         existir ya. Es lo obligatorio contra el servidor
                         compartido de Azure, donde viven albaranes y partes.
        set_role       : rol de grupo al que hacer SET ROLE al abrir cada
                         sesión, para que todos los objetos tengan el mismo
                         propietario conecte quien conecte.
    """

    def __init__(
        self,
        conninfo: ConnInfo,
        admin_conninfo: ConnInfo,
        target_db: str,
        *,
        auto_create_db: bool = True,
        set_role: str | None = None,
    ) -> None:
        self._conninfo = conninfo
        self._admin_conninfo = admin_conninfo
        self._target_db = target_db
        self._auto_create_db = auto_create_db
        self._set_role = (set_role or "").strip()
        self._bootstrap_done = False

    # ---------------------------------------------------------------------
    # Conexión (con auto-bootstrap)
    # ---------------------------------------------------------------------

    @staticmethod
    def _resolve(conninfo: ConnInfo) -> str:
        """Resuelve la cadena de conexión (puede venir de un proveedor callable)."""
        return conninfo() if callable(conninfo) else conninfo

    def _connect(self, conninfo: ConnInfo, *, autocommit: bool = False) -> psycopg.Connection:
        """
        Abre una conexión y le aplica `SET ROLE` como PRIMERA sentencia de la
        sesión (R7). Todo el cliente pasa por aquí: si alguna ruta se saltara
        el SET ROLE, crearía objetos con otro propietario y el siguiente
        proceso no podría recrearlos.
        """
        conn = psycopg.connect(self._resolve(conninfo), autocommit=autocommit)
        if self._set_role:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("SET ROLE {}").format(sql.Identifier(self._set_role))
                    )
            except Exception:
                conn.close()
                raise
        return conn

    @contextmanager
    def connection(self) -> psycopg.Connection:
        """
        Context manager que abre y cierra una conexión psycopg.
        En la primera llamada de la vida del cliente, ejecuta auto-bootstrap
        (crea BBDD si no existe, crea schemas, crea _meta.etl_runs).
        """
        if not self._bootstrap_done:
            self._auto_bootstrap()
            self._bootstrap_done = True

        conn = self._connect(self._conninfo)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def check_connectivity(self) -> str:
        """
        Smoke test: garantiza que la BBDD existe y devuelve la versión de Postgres.
        Si la BBDD no existe, la crea automáticamente (con sus schemas).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            return row[0] if row else "unknown"

    # ---------------------------------------------------------------------
    # Bootstrap automático
    # ---------------------------------------------------------------------

    def _auto_bootstrap(self) -> None:
        """
        Idempotente. Asegura:
          1. La BBDD `target_db` existe (la crea si no, y solo si
             `auto_create_db`; contra Azure la crea el humano una vez).
          2. Los schemas (raw, aux, stg, mart, _meta) existen.
          3. La tabla _meta.etl_runs existe.
        """
        if self._auto_create_db:
            created = self._ensure_database()
            if created:
                logger.info("postgres_db_created", db=self._target_db)
            else:
                logger.debug("postgres_db_already_exists", db=self._target_db)
        else:
            self._assert_database_reachable()

        self._bootstrap_schemas_and_meta()
        logger.debug("postgres_bootstrap_done", schemas=list(SCHEMAS))

    def _assert_database_reachable(self) -> None:
        """
        Con `auto_create_db=False` no se toca la BBDD admin ni se crea nada
        (R9): lo único que se hace es comprobar que la base ya existe abriendo
        una conexión contra ella. Si no responde, el mensaje remite al script de
        provisión y al runbook en vez de intentar crearla (R10).
        """
        try:
            conn = self._connect(self._conninfo)
        except psycopg.OperationalError as e:
            raise RuntimeError(
                f"No puedo conectar a la BBDD '{self._target_db}' y "
                f"PG_AUTO_CREATE_DB=false, así que NO se intenta crearla: este "
                f"servidor puede estar compartido con otras bases en producción. "
                f"Créala con infra/sql/01_create_database.sql y sus roles con "
                f"infra/sql/02_roles.sql, siguiendo docs/runbook_postgres_azure.md. "
                f"Conexión usada: {safe_dsn(self._resolve(self._conninfo))}. "
                f"Detalle: {e}"
            ) from e
        conn.close()

    def _ensure_database(self) -> bool:
        """
        Comprueba si la BBDD existe consultando pg_database via la BBDD admin.
        Si no existe, la crea. Devuelve True si fue creada, False si ya existía.

        CREATE DATABASE no puede ejecutarse dentro de una transacción, por eso
        usamos autocommit=True para esta conexión administrativa.
        """
        try:
            admin_conn = self._connect(self._admin_conninfo, autocommit=True)
        except psycopg.OperationalError as e:
            raise RuntimeError(
                f"No puedo conectar a la BBDD admin para verificar/crear "
                f"'{self._target_db}'. Comprueba que el servidor Postgres está "
                f"accesible y que la BBDD admin existe (variable PG_ADMIN_DB, "
                f"por defecto 'postgres'). Detalle: {e}"
            ) from e

        try:
            with admin_conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (self._target_db,),
                )
                if cur.fetchone() is not None:
                    return False

                # No existe: la creamos
                cur.execute(
                    sql.SQL("CREATE DATABASE {} WITH ENCODING 'UTF8'").format(
                        sql.Identifier(self._target_db)
                    )
                )
                return True
        finally:
            admin_conn.close()

    def _bootstrap_schemas_and_meta(self) -> None:
        """Crea los schemas y la tabla _meta.etl_runs si no existen. Idempotente."""
        ddl_path = Path(__file__).parent / "sql" / "ddl" / "00_meta.sql"
        with ddl_path.open(encoding="utf-8") as f:
            ddl_meta = f.read()

        conn = self._connect(self._conninfo)
        try:
            with conn.cursor() as cur:
                for schema in SCHEMAS:
                    cur.execute(
                        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                            sql.Identifier(schema)
                        )
                    )
                cur.execute(ddl_meta)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def force_bootstrap(self) -> None:
        """
        Fuerza el bootstrap aunque ya se haya hecho (idempotente igualmente).
        Útil para el comando CLI 'bootstrap' si el usuario quiere reejecutarlo.
        """
        self._auto_bootstrap()
        self._bootstrap_done = True

    # ---------------------------------------------------------------------
    # DDL dinámico de tablas raw
    # ---------------------------------------------------------------------

    def ensure_raw_table(
        self,
        target_table: str,
        columns: list[ColumnSpec],
        *,
        primary_key: str = "ide",
    ) -> None:
        """
        Crea la tabla raw.<target_table> si no existe, con los tipos derivados
        de la metadata de Sigrid. Añade dos columnas técnicas:
            _ingested_at   TIMESTAMP   cuándo se cargó la fila en Postgres
            _source_tiemod DOUBLE PRECISION  valor de tiemod de Sigrid (NULL si no existe)
        Si la tabla ya existe, no la toca.
        """
        if not columns:
            raise ValueError(f"Sin columnas para crear raw.{target_table}")

        col_definitions = []
        for c in columns:
            null_clause = "NULL" if c.is_nullable else "NOT NULL"
            col_definitions.append(
                sql.SQL("{} {} {}").format(
                    sql.Identifier(c.name),
                    sql.SQL(c.postgres_type),
                    sql.SQL(null_clause),
                )
            )

        # Columnas técnicas
        col_definitions.append(sql.SQL("_ingested_at TIMESTAMP NOT NULL DEFAULT NOW()"))
        col_definitions.append(sql.SQL("_source_tiemod DOUBLE PRECISION NULL"))

        # PK si la columna existe en la lista
        pk_clause = sql.SQL("")
        if any(c.name == primary_key for c in columns):
            pk_clause = sql.SQL(", PRIMARY KEY ({})").format(sql.Identifier(primary_key))

        ddl = sql.SQL("CREATE TABLE IF NOT EXISTS raw.{} ({}{})").format(
            sql.Identifier(target_table),
            sql.SQL(", ").join(col_definitions),
            pk_clause,
        )

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(ddl)

        logger.info(
            "raw_table_ready",
            table=f"raw.{target_table}",
            columns=len(columns),
            pk=primary_key,
        )

    def table_exists(self, schema: str, table: str) -> bool:
        """Devuelve True si la tabla existe en el schema dado."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s",
                (schema, table),
            )
            return cur.fetchone() is not None

    def get_table_columns(self, schema: str, table: str) -> list[str]:
        """
        Devuelve la lista ordenada de nombres de columnas de una tabla.

        Útil para validación previa antes de ejecutar SQL que asume ciertas
        columnas. Si la tabla no existe, devuelve [].
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            )
            return [row[0] for row in cur.fetchall()]

    def assert_columns_exist(
        self,
        schema: str,
        table: str,
        required_columns: list[str],
    ) -> None:
        """
        Verifica que `required_columns` están todas presentes en `schema.table`.
        Si falta alguna, lanza ValueError con un mensaje claro que indica:
          - qué columnas faltan
          - qué columnas SÍ tiene la tabla (para facilitar el diagnóstico)

        Llamar al inicio de un Step evita fallos a mitad de transformación con
        mensajes crípticos. Es el patrón "fail fast".
        """
        if not self.table_exists(schema, table):
            raise ValueError(
                f"La tabla {schema}.{table} no existe. "
                f"¿Has ejecutado el step de ingesta previo?"
            )

        actual = set(self.get_table_columns(schema, table))
        required = set(required_columns)
        missing = required - actual
        if missing:
            raise ValueError(
                f"Columnas faltantes en {schema}.{table}: "
                f"{sorted(missing)}. "
                f"Columnas presentes: {sorted(actual)}. "
                f"Posibles causas: (1) la columna se llama distinto en tu Sigrid; "
                f"(2) está en exclude_columns del YAML; (3) Sigrid ha cambiado el esquema."
            )

    def get_max_id(self, schema: str, table: str, id_column: str = "ide") -> int:
        """Devuelve el MAX(id_column) de la tabla. 0 si está vacía o no existe."""
        if not self.table_exists(schema, table):
            return 0
        query = sql.SQL("SELECT COALESCE(MAX({}), 0) FROM {}.{}").format(
            sql.Identifier(id_column),
            sql.Identifier(schema),
            sql.Identifier(table),
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def truncate_table(self, schema: str, table: str) -> None:
        """TRUNCATE de la tabla. Útil para full-refresh."""
        query = sql.SQL("TRUNCATE TABLE {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
        logger.info("table_truncated", table=f"{schema}.{table}")

    def count_rows(self, schema: str, table: str) -> int:
        """COUNT(*) de la tabla."""
        if not self.table_exists(schema, table):
            return 0
        query = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0]) if row else 0

    # ---------------------------------------------------------------------
    # Permisos del rol de solo lectura
    # ---------------------------------------------------------------------

    def role_exists(self, role: str) -> bool:
        """True si el rol existe en el servidor."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            return cur.fetchone() is not None

    def list_schemas(self) -> list[str]:
        """Esquemas que existen realmente en la BBDD."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            return [row[0] for row in cur.fetchall()]

    def apply_readonly_grants(
        self,
        readonly_role: str,
        owner_role: str,
        schemas: Iterable[str],
    ) -> list[str]:
        """
        Reaplica los permisos de lectura y devuelve las sentencias ejecutadas.

        Solo se conceden permisos sobre los esquemas que existen: `run-all` no
        construye `cierre`, `compras`, `maestro` ni `retenciones` (van en
        comandos aparte), así que en una base recién creada esos esquemas
        pueden no estar todavía. Intentarlo daría error y tumbaría el paso por
        algo que no es un problema.
        """
        existentes = set(self.list_schemas())
        pedidos = list(schemas)
        aplicables = [s for s in pedidos if s in existentes]
        ausentes = [s for s in pedidos if s not in existentes]
        if ausentes:
            logger.warning("grants_esquemas_inexistentes", schemas=ausentes)

        sentencias = build_readonly_grant_statements(
            readonly_role, owner_role, aplicables, database=self._target_db
        )
        if not sentencias:
            return []

        with self.connection() as conn, conn.cursor() as cur:
            for stmt in sentencias:
                cur.execute(stmt)

        logger.info(
            "grants_aplicados",
            role=readonly_role,
            schemas=aplicables,
            statements=len(sentencias),
        )
        return sentencias

    # ---------------------------------------------------------------------
    # Ejecución de archivos SQL (DDL, transformaciones stg/mart)
    # ---------------------------------------------------------------------

    def execute_sql_file(
        self,
        path: Path,
        *,
        params: dict | tuple | None = None,
    ) -> None:
        """
        Ejecuta el contenido de un archivo .sql contra Postgres.

        Comportamiento:
          - Sin parámetros: ejecuta todo el texto en una sola llamada
            (psycopg permite múltiples statements separados por ';').
          - Con parámetros: divide el texto en statements individuales
            (split por ';' respetando comentarios y strings) y los ejecuta
            uno a uno. Solo aplica los parámetros al/los statement(s) que
            realmente los contienen como placeholders. Esto es necesario
            porque Postgres no permite "multiple commands" en una prepared
            statement.

        Si el SQL falla, lanza la excepción de psycopg con el mensaje original
        (incluye nombre del error y posición).
        """
        if not path.exists():
            raise FileNotFoundError(f"SQL no encontrado: {path}")

        sql_text = path.read_text(encoding="utf-8")

        with self.connection() as conn, conn.cursor() as cur:
            if params is None:
                cur.execute(sql_text)
            else:
                statements = _split_sql_statements(sql_text)
                for stmt in statements:
                    if _statement_has_placeholders(stmt, params):
                        cur.execute(stmt, params)
                    else:
                        cur.execute(stmt)

        logger.info(
            "sql_file_executed",
            file=str(path.name),
            has_params=params is not None,
            param_style="dict" if isinstance(params, dict) else ("tuple" if params else "none"),
        )

    # ---------------------------------------------------------------------
    # Carga masiva con COPY
    # ---------------------------------------------------------------------

    def copy_rows(
        self,
        schema: str,
        table: str,
        columns: list[str],
        rows: Iterable[dict[str, Any]],
        *,
        tiemod_column: str | None = None,
    ) -> int:
        """
        Inserta filas en `schema.table` usando COPY FROM STDIN en formato texto.

        `rows` es un iterable de dicts (no se materializa entero en memoria).
        `columns` define el orden y selección de columnas a insertar.
        Añade automáticamente `_source_tiemod` si `tiemod_column` se proporciona
        y existe en cada fila.

        Devuelve el número de filas insertadas.
        """
        if not columns:
            raise ValueError("Lista de columnas vacía")

        # Cláusula de columnas para COPY. Incluye _source_tiemod si procede.
        copy_columns = list(columns)
        if tiemod_column:
            copy_columns.append("_source_tiemod")

        copy_sql = sql.SQL(
            "COPY {}.{} ({}) FROM STDIN WITH (FORMAT text, NULL '\\N')"
        ).format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in copy_columns),
        )

        rows_written = 0

        with self.connection() as conn, conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for row in rows:
                fields: list[str] = []
                for c in columns:
                    fields.append(_pg_text_format(row.get(c)))
                if tiemod_column:
                    fields.append(_pg_text_format(row.get(tiemod_column)))
                copy.write("\t".join(fields) + "\n")
                rows_written += 1

        return rows_written

    # ---------------------------------------------------------------------
    # Tracking de runs (_meta.etl_runs)
    # ---------------------------------------------------------------------

    def record_run_start(self, stage: str, step: str) -> int:
        """Inserta una fila en _meta.etl_runs con status=RUNNING. Devuelve el run_id."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO _meta.etl_runs (stage, step, started_at, status)
                VALUES (%s, %s, %s, 'RUNNING')
                RETURNING id
                """,
                (stage, step, datetime.utcnow()),
            )
            row = cur.fetchone()
            return int(row[0])

    def record_run_end(
        self,
        run_id: int,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Cierra la fila de _meta.etl_runs con status final."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE _meta.etl_runs
                SET finished_at    = %s,
                    status         = %s,
                    rows_processed = %s,
                    error_message  = %s
                WHERE id = %s
                """,
                (datetime.utcnow(), status, rows_processed, error_message, run_id),
            )


# -------------------------------------------------------------------------
# Helpers de formato para COPY (formato texto de Postgres)
# -------------------------------------------------------------------------

def _pg_text_format(value: Any) -> str:
    """
    Codifica un valor Python al formato texto de COPY de Postgres.

    Reglas:
      - None        → \\N (NULL)
      - bool        → 't' / 'f'
      - bytes       → \\\\x<hex>   (formato hex de bytea)
      - resto       → str(value) con escapado de \\, tab, newline, CR
    """
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, bytes):
        return "\\\\x" + value.hex()
    s = str(value)
    # Escapado para formato texto de COPY
    return (
        s.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


# -------------------------------------------------------------------------
# Helpers para ejecutar SQL con múltiples statements + parámetros
# -------------------------------------------------------------------------

def _split_sql_statements(sql_text: str) -> list[str]:
    """
    Divide un texto SQL en statements individuales por ';'.

    Maneja:
      - Comentarios de línea (-- ...): se ignoran al detectar separadores.
      - Strings literales con comilla simple: no divide por ';' dentro de ellas.

    Suficiente para los SQL controlados de este proyecto. NO maneja:
      - Bloques delimitados con $$ ... $$ (CREATE FUNCTION con plpgsql).
        Por eso 00_functions.sql se ejecuta sin parámetros (caso simple).
      - Comentarios de bloque /* ... */.
    """
    statements: list[str] = []
    current: list[str] = []
    in_string = False
    in_line_comment = False

    i = 0
    while i < len(sql_text):
        ch = sql_text[i]

        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_string:
            current.append(ch)
            if ch == "'":
                # Comilla doble '' dentro de string = escape, no fin
                if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                    current.append("'")
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        # Detectar inicio de comentario de línea
        if ch == "-" and i + 1 < len(sql_text) and sql_text[i + 1] == "-":
            in_line_comment = True
            current.append(ch)
            i += 1
            continue

        if ch == "'":
            in_string = True
            current.append(ch)
            i += 1
            continue

        if ch == ";":
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    # Último statement sin ; final
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def _statement_has_placeholders(stmt: str, params: dict | tuple) -> bool:
    """
    Devuelve True si el statement contiene placeholders compatibles con `params`.

    Reglas:
      - dict params + %(nombre)s en el SQL → True si alguna clave del dict aparece
      - tuple params + %s en el SQL → True si %s está presente

    Sirve para no pasar parámetros a statements que no los necesitan (TRUNCATE, etc.),
    lo cual evita errores 'argument formats can't be mixed' en psycopg.
    """
    # Eliminar comentarios de línea antes de buscar
    cleaned_lines = []
    for line in stmt.splitlines():
        idx = line.find("--")
        if idx >= 0:
            line = line[:idx]
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    if isinstance(params, dict):
        return any(f"%({k})s" in cleaned for k in params)
    return "%s" in cleaned
