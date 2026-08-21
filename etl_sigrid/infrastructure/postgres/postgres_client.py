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

from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Json

from etl_sigrid.domain.coherencia import EstadoPaso, EstadoTablaRaw
from etl_sigrid.domain.ejecucion import MOTIVO_HUERFANA
from etl_sigrid.domain.entities import ColumnSpec
from etl_sigrid.domain.perfil_carga import FilaPerfil
from etl_sigrid.domain.tiemod import COLUMNA_TIEMOD, EstadoTiemod
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.conninfo import safe_dsn
from etl_sigrid.infrastructure.postgres.fingerprint import build_estructura_query
from etl_sigrid.infrastructure.postgres.frescura import FilaFrescura
from etl_sigrid.infrastructure.postgres.grants import build_readonly_grant_statements
from etl_sigrid.infrastructure.postgres.timings import Timing

logger = get_logger(__name__)


# Schemas del data mart
SCHEMAS = ("raw", "aux", "stg", "mart", "_meta")

# Cuántas mediciones devolver cuando no hay un arranque de `ingest_raw` al que
# anclarse. Evita volcar el histórico entero de _meta.etl_runs.
TIMINGS_SIN_ANCLA = 100

# Una cadena de conexión, o algo que la produzca. Es callable porque con
# autenticación Entra la "contraseña" es un token que caduca y hay que
# resolverlo en cada conexión, no una vez al arrancar.
ConnInfo = str | Callable[[], str]


# --- Troceo y puerta de disco del build de plan_mensual (F-019) -------------

# Gigabyte binario: es la unidad en la que Azure declara el disco del Flexible
# Server (32 GB) y en la que se compara `PG_DISCO_TOTAL_GB`.
BYTES_POR_GB = 1024 * 1024 * 1024

# Ocupación del disco del SERVIDOR, no de nuestra base: el disco es compartido
# con `albaranes` y `partes`, y lo que hay que vigilar es el total.
# `pg_database_size` sobre otra base exige privilegio CONNECT; el rol del ETL
# lo tiene (frontera medida en F-005). No cuenta WAL ni logs del servidor: ese
# hueco lo absorbe el margen entre el límite (80 %) y la protección de Azure
# (~95 %).
SQL_OCUPACION_DISCO = "SELECT SUM(pg_database_size(datname)) FROM pg_database"

# Peso de cada obra = filas de raw.obrparpre que le tocan, ponderando la rama
# master por el número de posiciones de su `planif`, que es lo que de verdad
# explota el CROSS JOIN LATERAL. Las filas de reales (amb 3/7) no se explotan:
# pesan una. Es una agregación sin ventanas, así que no derrama como el build.
SQL_PESOS_PLAN_MENSUAL = """
SELECT
    pp.obra_id,
    SUM(
        CASE
            WHEN pp.ambito_id IN (8, 11)
                THEN COALESCE(
                    cardinality(
                        string_to_array(NULLIF(TRIM(op.planif), ''), '|')
                    ),
                    0
                )
            ELSE 1
        END
    )::BIGINT AS peso
FROM stg.presupuesto pp
JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
WHERE pp.ambito_id IN (3, 7, 8, 11)
GROUP BY pp.obra_id
"""


# --- Coherencia ante cargas truncadas (F-024) -------------------------------
#
# Las consultas van como constantes de módulo, igual que `SQL_OCUPACION_DISCO`,
# para que los tests estáticos lean EXACTAMENTE el SQL que se envía. Ninguna se
# ejecuta con parámetros salvo la primera: `LIKE 'build_stg%'` lleva un `%` que
# psycopg tomaría por marcador si hubiera parámetros que sustituir.

# Cierra de una vez todas las filas que dejó abiertas un proceso muerto. NO
# filtra por antigüedad (toda `RUNNING` que exista al arrancar es de otro
# proceso, por definición) ni por batch (las nuestras aún no existen). El
# `WHERE status = 'RUNNING'` es lo único que separa esto de reescribir el
# histórico entero, incluidos los SUCCESS de las cargas buenas.
SQL_ABORTAR_HUERFANOS = """
UPDATE _meta.etl_runs
SET status        = 'ABORTED',
    finished_at   = %(ahora)s,
    error_message = %(motivo)s
WHERE status = 'RUNNING'
RETURNING id, step, started_at
"""

# De qué carga viene cada tabla de raw. Se lee de la VISTA y no de `etl_runs`
# para que la puerta, `check-coherencia`, el MCP y Power BI vean exactamente lo
# mismo: una sola definición de «última ingesta», en el DDL.
SQL_ESTADO_RAW = """
SELECT tabla, status, batch_id, started_at, finished_at, filas
FROM _meta.v_raw_state
ORDER BY tabla
"""

# El último intento de construir stg. Por `id` DESC y no por fecha: la fila de
# PASO se inserta al TERMINAR el step, y su `started_at` es el del arranque,
# anterior al de todos sus sub-pasos. Ordenando por fecha, un stage terminado
# devolvería su último tramo y la puerta de mart lo tomaría por incompleto.
SQL_ULTIMO_INTENTO_STG = """
SELECT id, step, status, batch_id, started_at, finished_at
FROM _meta.etl_runs
WHERE step LIKE 'build_stg%'
ORDER BY id DESC
LIMIT 1
"""

SQL_FRESCURA = """
SELECT paso,
       ultimo_ok_finished_at,
       ultimo_ok_batch_id,
       ultimo_ok_filas,
       horas_desde_ultimo_ok,
       ultimo_intento_started_at,
       ultimo_intento_status,
       ultimo_intento_error
FROM _meta.v_frescura
ORDER BY paso
"""

# --- Perfil de carga (F-011, R1-R3) -----------------------------------------
#
# SOLO LECTURA y sobre `_meta.etl_runs` y nada más: es el «medir antes de
# optimizar» de F-011, y no hace falta ejecutar ninguna carga nueva para
# responderlo, porque cada tabla ya deja su fila `ingest_raw.<tabla>` desde
# F-024.
#
# El ancla es la ÚLTIMA carga con `batch_id`, elegida por `ORDER BY batch_id
# DESC`: el identificador de F-024 es UTC compacto, así que ordena
# cronológicamente sin parsear nada (fue una decisión explícita de esa
# feature). Y se ancla a `step = 'ingest_raw'` porque es el primer paso de
# `run-all`: así el perfil sale de una carga de verdad y no de un
# `apply-grants` suelto que se ejecutó después.
SQL_PERFIL_CARGA = """
SELECT stage, step, started_at, finished_at, status, rows_processed, batch_id
FROM _meta.etl_runs
WHERE batch_id = COALESCE(
        %(batch)s,
        (SELECT batch_id
         FROM _meta.etl_runs
         WHERE step = 'ingest_raw' AND batch_id IS NOT NULL
         ORDER BY batch_id DESC
         LIMIT 1)
      )
ORDER BY started_at, id
"""

# --- Diagnóstico de `tiemod` (F-011, R6-R7) ---------------------------------
#
# SOLO LECTURA sobre `raw`. Responde si la marca de modificación de Sigrid
# sirve como watermark **sin volver a leer Sigrid**: sus valores ya están
# guardados en `_source_tiemod`, carga tras carga, desde que existe
# `copy_rows(tiemod_column=...)`.
#
# El COUNT(DISTINCT) no es gratis —obliga a recorrer la tabla entera— y por eso
# esto es un comando que se lanza a mano, no un paso del pipeline.
SQL_TABLAS_CON_TIEMOD = """
SELECT table_name
FROM information_schema.columns
WHERE table_schema = 'raw' AND column_name = %(columna)s
ORDER BY table_name
"""

#: Plantilla: la tabla y la columna se interpolan con `psycopg.sql.Identifier`,
#: nunca por concatenación. Va como constante para que un test pueda leer
#: exactamente el SQL que se envía, igual que hace F-024.
SQL_DIAGNOSTICO_TIEMOD = """
SELECT COUNT(*)                                  AS filas,
       COUNT(*) FILTER (WHERE {col} IS NULL)     AS nulos,
       MIN({col})                                AS minimo,
       MAX({col})                                AS maximo,
       COUNT(DISTINCT {col})                     AS distintos
FROM raw.{tabla}
"""

#: Filas cuya marca supera la de la fotografía anterior. Es la traducción
#: operativa de «cuántas filas cambiaron» de R7: si `tiemod` es una marca de
#: modificación, toda fila tocada desde la foto anterior está por encima de su
#: máximo. Si no lo es, este recuento sale 0, que es justo la señal de NO SIRVE.
SQL_FILAS_DESDE_TIEMOD = "SELECT COUNT(*) FROM raw.{tabla} WHERE {col} > %(umbral)s"

SQL_RUN_START = """
INSERT INTO _meta.etl_runs (stage, step, started_at, status, batch_id)
VALUES (%s, %s, %s, 'RUNNING', %s)
RETURNING id
"""

SQL_RUN_COMPLETED = """
INSERT INTO _meta.etl_runs
    (stage, step, started_at, finished_at, status,
     rows_processed, error_message, metadata, batch_id)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""


def _float_o_none(valor: Any) -> float | None:
    """Convierte a `float` respetando el nulo de SQL.

    Existe para que cada columna se lea con su propio valor y no con el índice
    de la de al lado: `MIN` y `MAX` de la misma columna son nulos a la vez, así
    que confundirlos no lo detecta ningún dato posible. Con el helper, la
    confusión ni se puede escribir.
    """
    return None if valor is None else float(valor)


def porcentaje_ocupacion(bytes_usados: int, total_gb: int) -> float:
    """Ocupación del disco en tanto por ciento, con el total en GB binarios.

    La validación mira `total_gb` y no los bytes ya calculados: es el valor que
    de verdad configura el humano (`PG_DISCO_TOTAL_GB`), y así el mensaje habla
    de lo que hay que corregir.
    """
    if total_gb <= 0:
        raise ValueError(
            f"PG_DISCO_TOTAL_GB debe ser un entero positivo, y vale {total_gb}. "
            f"Sin tamaño de disco no hay puerta de seguridad que valga."
        )
    return bytes_usados * 100.0 / (total_gb * BYTES_POR_GB)


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
    # Huella de las vistas de consumo
    # ---------------------------------------------------------------------

    def list_view_columns(self, schemas: Iterable[str]) -> list[tuple]:
        """
        Columnas de todas las VISTAS de los esquemas dados:
        (esquema, vista, posición, columna, tipo), en orden estable.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(build_estructura_query(list(schemas)))
            return list(cur.fetchall())

    def fetch_aggregates(self, query: str) -> tuple:
        """
        Ejecuta una consulta de agregados de una sola fila y devuelve sus
        valores. La consulta la construye `fingerprint.build_agregado_query`,
        que cita los identificadores; aquí no se concatena nada.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(query)
            fila = cur.fetchone()
            return tuple(fila) if fila else ()

    def comprobar_unicidad(self, consulta, timeout_s: int) -> tuple[int, int] | None:
        """Ejecuta UNA comprobación de unicidad (F-006, T26).

        Devuelve `(claves_duplicadas, filas_implicadas)`, o **`None` si la
        consulta agotó el `statement_timeout`**. Ese `None` no es un cero: es
        «no lo sabemos», y quien lo reciba tiene que reportarlo como NO
        COMPROBADO. Contarlo como correcto convertiría el límite de tiempo
        —que está para no ahogar un servidor compartido con `albaranes` y
        `partes`— en una forma de aprobar sin mirar.

        La transacción va `READ ONLY` y el `statement_timeout` es `SET LOCAL`,
        así que ni escribe ni cambia la configuración del servidor.
        """
        import psycopg

        with self.connection() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute(f"SET LOCAL statement_timeout = '{int(timeout_s)}s'")
                    cur.execute(consulta.sql)
                    fila = cur.fetchone()
                conn.commit()
            except psycopg.errors.QueryCanceled:
                conn.rollback()
                return None
            except Exception:
                conn.rollback()
                raise
        if fila is None:
            return (0, 0)
        return (int(fila[0]), int(fila[1]))

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
    # Diccionario semántico (F-006)
    # ---------------------------------------------------------------------

    def publicar_diccionario(
        self,
        dicc,
        *,
        hash_fuente: str,
        informe,
        batch_id: str | None = None,
        ahora: datetime | None = None,
    ) -> int:
        """Reemplaza el diccionario publicado y devuelve las filas escritas.

        TODO ocurre dentro de UNA transacción, y esa es la garantía que el
        contrato con `mcp-bbdd` le debe a quien consulte mientras se publica:
        verá el diccionario anterior completo o el nuevo completo, nunca uno a
        medias y nunca vacío. Una tabla vacía dejaría al MCP inventándose los
        significados, que es justo lo que esta feature existe para impedir.

        El vaciado es `DELETE` y jamás `DROP`: un `DROP` se lleva por delante
        los `GRANT` del rol de lectura y dejaría al MCP ciego hasta el
        `apply-grants` siguiente.
        """
        from etl_sigrid.infrastructure.postgres.diccionario_sql import (
            SQL_BORRAR_DICCIONARIO,
            SQL_BORRAR_PUBLICACION,
            SQL_BORRAR_REGLAS,
            SQL_INSERT_DICCIONARIO,
            SQL_INSERT_PUBLICACION,
            SQL_INSERT_REGLA,
            fila_publicacion,
            filas_diccionario,
            filas_reglas,
        )

        instante = ahora if ahora is not None else datetime.utcnow()
        fichas = filas_diccionario(dicc)
        reglas = filas_reglas(dicc)
        publicacion = fila_publicacion(dicc, hash_fuente, instante, batch_id, informe)

        with self.connection() as conn, conn.cursor() as cur:
            # Borrar antes de insertar: al revés chocaría con la clave primaria.
            cur.execute(SQL_BORRAR_DICCIONARIO)
            cur.execute(SQL_BORRAR_REGLAS)
            cur.execute(SQL_BORRAR_PUBLICACION)
            if fichas:
                cur.executemany(SQL_INSERT_DICCIONARIO, fichas)
            if reglas:
                cur.executemany(SQL_INSERT_REGLA, reglas)
            cur.execute(SQL_INSERT_PUBLICACION, publicacion)

        escritas = len(fichas) + len(reglas) + 1
        logger.info(
            "diccionario_publicado",
            version=publicacion[1],
            hash_fuente=hash_fuente[:12],
            objetos=len(fichas),
            reglas=len(reglas),
            filas=escritas,
        )
        return escritas

    def list_objetos_catalogo(self, schemas: Sequence[str]) -> list[tuple]:
        """Los objetos que la base tiene DE VERDAD, para `check-diccionario`.

        Es la única fuente no heurística: la puerta offline lee el SQL del
        repositorio con expresiones regulares y no puede ver un objeto creado
        por otra vía. Incluye funciones además de tablas y vistas, porque el
        diccionario también las documenta.
        """
        from etl_sigrid.infrastructure.postgres.diccionario_sql import (
            SQL_OBJETOS_CATALOGO,
        )

        pedidos = list(schemas)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_OBJETOS_CATALOGO, (pedidos, pedidos))
            return list(cur.fetchall())

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
    # Build por tramos de stg.plan_mensual (F-019)
    # ---------------------------------------------------------------------

    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        """Peso estimado de cada obra para planificar los tramos.

        Devuelve {obra_id: filas estimadas}. Es la entrada de
        `domain.tramos.planificar_tramos`, que no sabe de BBDD.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_PESOS_PLAN_MENSUAL)
            return {int(fila[0]): int(fila[1]) for fila in cur.fetchall()}

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        """Ocupación del disco del servidor, en tanto por ciento.

        **Propaga las excepciones a propósito**: quien llama tiene que abortar
        si esto falla (R10). Devolver un 0 «por si acaso» sería seguir a
        ciegas, que es exactamente lo que hacía el build que llenó el disco.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_OCUPACION_DISCO)
            fila = cur.fetchone()

        if not fila or fila[0] is None:
            raise RuntimeError(
                "No se pudo medir la ocupación del disco del servidor: la "
                "consulta sobre pg_database no devolvió ningún valor. Sin esa "
                "medición no se ejecuta ningún tramo."
            )
        return porcentaje_ocupacion(int(fila[0]), total_gb)

    def execute_sql_text(self, sql_text: str) -> int:
        """Ejecuta un SQL ya compuesto y devuelve las filas afectadas.

        Una llamada = una conexión = **una transacción** (lo garantiza
        `connection()`). Es lo que impide que el pico de temporales de un
        tramo se apile con el del siguiente.

        El recuento sale del `rowcount` del cursor, no de un `COUNT(*)` sobre
        la tabla: un seq-scan por tramo sobre millones de filas en 1 vCPU
        sería castigo gratuito.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql_text)
            filas = cur.rowcount

        # psycopg deja rowcount en -1 cuando la sentencia no trae recuento.
        return max(int(filas), 0) if filas is not None else 0

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

    def record_run_start(
        self, stage: str, step: str, batch_id: str | None = None
    ) -> int:
        """Inserta una fila en _meta.etl_runs con status=RUNNING. Devuelve el run_id.

        `batch_id` es opcional a propósito (F-024): este método lo llaman los
        sub-pasos de `build_stg` y sus ~60 tramos, y hacerlo obligatorio
        rompería todos los llamantes a la vez. Sin él se escribe NULL, que es
        exactamente lo que tiene el histórico anterior a la feature.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_RUN_START, (stage, step, datetime.utcnow(), batch_id))
            row = cur.fetchone()
            return int(row[0])

    # ---------------------------------------------------------------------
    # Coherencia ante cargas truncadas (F-024)
    # ---------------------------------------------------------------------

    def abortar_runs_huerfanos(
        self, batch_id: str, ahora: datetime | None = None
    ) -> list[tuple[int, str, datetime]]:
        """Cierra como ABORTED las filas que dejó abiertas un proceso muerto.

        Devuelve `(id, step, started_at)` de cada fila marcada, para que quien
        llama emita un WARNING por fila: enterarse de que anoche murió algo es
        justo lo que no pasaba antes de F-024.

        **Propaga las excepciones**: quien llama decide. Y decide continuar
        (R7), porque esto es contabilidad y el paso que venga detrás fallará
        por sí mismo si la BBDD no está.
        """
        instante = datetime.utcnow() if ahora is None else ahora
        motivo = MOTIVO_HUERFANA.format(
            batch_id=batch_id,
            ahora=instante.isoformat(sep=" ", timespec="seconds"),
        )
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ABORTAR_HUERFANOS, {"ahora": instante, "motivo": motivo})
            return [
                (int(fila[0]), str(fila[1]), fila[2]) for fila in cur.fetchall()
            ]

    def fetch_estado_raw(self) -> list[EstadoTablaRaw]:
        """Última ingesta conocida de cada tabla de `raw`, desde la vista."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ESTADO_RAW)
            return [
                EstadoTablaRaw(
                    tabla=fila[0],
                    status=fila[1],
                    batch_id=fila[2],
                    started_at=fila[3],
                    finished_at=fila[4],
                    filas=int(fila[5] or 0),
                )
                for fila in cur.fetchall()
            ]

    def fetch_ultimo_intento_stg(self) -> EstadoPaso | None:
        """La fila más reciente de `build_stg%`, o `None` si no hay ninguna."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_ULTIMO_INTENTO_STG)
            fila = cur.fetchone()

        if fila is None:
            return None
        return EstadoPaso(
            id=int(fila[0]),
            step=fila[1],
            status=fila[2],
            batch_id=fila[3],
            started_at=fila[4],
            finished_at=fila[5],
        )

    def fetch_frescura(self) -> list[FilaFrescura]:
        """`_meta.v_frescura` tal cual, con las horas ya en `float`.

        La vista las devuelve como `numeric` (psycopg las trae en `Decimal`) y
        `format_frescura` las compara con un umbral entero: la conversión se
        hace aquí, una vez, y no en cada llamante.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_FRESCURA)
            return [
                FilaFrescura(
                    paso=fila[0],
                    ultimo_ok_finished_at=fila[1],
                    ultimo_ok_batch_id=fila[2],
                    ultimo_ok_filas=fila[3],
                    horas_desde_ultimo_ok=(
                        None if fila[4] is None else float(fila[4])
                    ),
                    ultimo_intento_started_at=fila[5],
                    ultimo_intento_status=fila[6],
                    ultimo_intento_error=fila[7],
                )
                for fila in cur.fetchall()
            ]

    def fetch_timings(self, last: int = 1) -> list[Timing]:
        """
        Mediciones de las `last` ejecuciones más recientes del pipeline.

        Una "ejecución" se ancla al arranque de `ingest_raw`, que es el primer
        paso de `run-all`: se devuelven todas las filas desde el arranque
        número `last` hacia atrás. Así entran también los pasos que se lanzan
        después con comandos sueltos (build-cierre, apply-grants), que es
        justo lo que interesa medir en la carga inicial.

        Si todavía no hay ningún `ingest_raw` registrado —caso de una base
        cargada antes de que el orquestador instrumentara los pasos— se
        devuelven las últimas `TIMINGS_SIN_ANCLA` filas en vez del histórico
        entero, que puede ser de años.
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT MIN(started_at) FROM (
                    SELECT started_at
                    FROM _meta.etl_runs
                    WHERE step = 'ingest_raw'
                    ORDER BY started_at DESC
                    LIMIT %s
                ) AS arranques
                """,
                (last,),
            )
            row = cur.fetchone()
            desde = row[0] if row else None

            if desde is not None:
                cur.execute(
                    """
                    SELECT stage, step, started_at, finished_at, status, rows_processed
                    FROM _meta.etl_runs
                    WHERE started_at >= %s
                    ORDER BY started_at, id
                    """,
                    (desde,),
                )
                filas = cur.fetchall()
            else:
                cur.execute(
                    """
                    SELECT stage, step, started_at, finished_at, status, rows_processed
                    FROM _meta.etl_runs
                    ORDER BY started_at DESC, id DESC
                    LIMIT %s
                    """,
                    (TIMINGS_SIN_ANCLA,),
                )
                filas = list(reversed(cur.fetchall()))

            return [
                Timing(
                    stage=fila[0],
                    step=fila[1],
                    started_at=fila[2],
                    finished_at=fila[3],
                    status=fila[4],
                    rows_processed=int(fila[5] or 0),
                )
                for fila in filas
            ]

    def fetch_perfil_carga(
        self, batch_id: str | None = None
    ) -> tuple[str | None, list[FilaPerfil]]:
        """
        Desglose de una carga: una fila por paso y una por tabla de la ingesta.

        Devuelve el par `(batch medido, filas)`. El `batch_id` viaja de vuelta
        —y no solo las filas, como apuntaba el diseño— porque R8 exige que el
        informe de medición diga de QUÉ carga salen los números: sin él, quien
        lee el perfil no puede saber si midió la nocturna buena o la noche que
        murió a los diez minutos.

        Sin argumento mide la última carga registrada. Solo `SELECT`: no marca
        huérfanas ni registra paso (R25).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_PERFIL_CARGA, {"batch": batch_id})
            filas = cur.fetchall()

        medido = batch_id
        perfil: list[FilaPerfil] = []
        for stage, step, started_at, finished_at, status, rows, batch in filas:
            if medido is None:
                medido = batch
            perfil.append(
                FilaPerfil(
                    stage=stage,
                    step=step,
                    segundos=(
                        0.0
                        if started_at is None or finished_at is None
                        else (finished_at - started_at).total_seconds()
                    ),
                    filas=int(rows or 0),
                    status=status,
                )
            )
        return medido, perfil

    def fetch_diagnostico_tiemod(self) -> list[EstadoTiemod]:
        """
        Estado de `_source_tiemod` en cada tabla de `raw` que la tenga (R6).

        Una consulta de agregación por tabla, en una sola conexión. Es cara
        —recorre cada tabla entera— y por eso solo la lanza el comando
        `diagnostico-tiemod`, nunca el pipeline.
        """
        columna = sql.Identifier(COLUMNA_TIEMOD)
        estados: list[EstadoTiemod] = []

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_TABLAS_CON_TIEMOD, {"columna": COLUMNA_TIEMOD})
            tablas = [fila[0] for fila in cur.fetchall()]

            for tabla in tablas:
                cur.execute(
                    sql.SQL(SQL_DIAGNOSTICO_TIEMOD).format(
                        col=columna, tabla=sql.Identifier(tabla)
                    )
                )
                # Una agregación sin GROUP BY siempre devuelve exactamente una
                # fila: no hay rama defensiva que probar aquí, y añadirla solo
                # dejaría código muerto que ningún test puede recorrer.
                fila = cur.fetchone()
                estados.append(
                    EstadoTiemod(
                        tabla=tabla,
                        filas=int(fila[0] or 0),
                        nulos=int(fila[1] or 0),
                        minimo=_float_o_none(fila[2]),
                        maximo=_float_o_none(fila[3]),
                        distintos=int(fila[4] or 0),
                    )
                )
        return estados

    def fetch_filas_desde_tiemod(self, tabla: str, umbral: float) -> int:
        """Cuántas filas de `raw.<tabla>` tienen la marca por encima de `umbral` (R7)."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                sql.SQL(SQL_FILAS_DESDE_TIEMOD).format(
                    tabla=sql.Identifier(tabla),
                    col=sql.Identifier(COLUMNA_TIEMOD),
                ),
                {"umbral": umbral},
            )
            fila = cur.fetchone()
            return int(fila[0]) if fila else 0

    def record_run_completed(
        self,
        stage: str,
        step: str,
        started_at: datetime | None,
        finished_at: datetime | None,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        batch_id: str | None = None,
    ) -> int:
        """
        Inserta de una vez la fila de un paso YA terminado, y devuelve su id.

        Es distinto de `record_run_start` + `record_run_end`: ese par lo usan
        los steps que se instrumentan a sí mismos. Este lo usa el orquestador
        para dejar rastro de TODOS los pasos, incluidos los que no se
        instrumentan por dentro (build_mart, build_cierre), que son los pesados.

        Estas son las filas de PASO que después lee `_meta.v_frescura`, y por
        eso son las que más importa que lleven `batch_id` (F-024).
        """
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                SQL_RUN_COMPLETED,
                (
                    stage,
                    step,
                    started_at or datetime.utcnow(),
                    finished_at,
                    status,
                    rows_processed,
                    error_message,
                    Json(metadata) if metadata else None,
                    batch_id,
                ),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

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
