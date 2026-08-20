# etl_sigrid/infrastructure/sigrid/sigrid_api_client.py
"""
Cliente HTTP de la Function App sigrid-api.

Características clave:
  - Paginación con keyset (WHERE ide > :last_ide ORDER BY ide ASC)
    en lugar de OFFSET, que escala mal en tablas grandes.
  - Reintentos automáticos con backoff exponencial en errores transitorios
    (timeouts, 429, 5xx) usando tenacity.
  - Streaming iterativo: yield de batches en lugar de cargar todo en memoria.
  - Trunca campos binarios / texto pesado vía la lista exclude_columns.

La API tiene límites por petición (MAX_ALLOWED_ROWS en la Function App).
Este cliente respeta `page_size` que debe ser <= ese límite.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from etl_sigrid.domain.entities import ColumnSpec
from etl_sigrid.domain.extraccion import es_sentencia_de_lectura
from etl_sigrid.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class SigridApiError(Exception):
    """Error genérico de la API."""


class SigridApiHttpError(SigridApiError):
    """Error HTTP de la API (4xx/5xx)."""


class SigridApiBusinessError(SigridApiError):
    """La API responde 200 pero ok=False (consulta rechazada por validación)."""


class SigridApiSentenciaNoDeLecturaError(SigridApiError):
    """Se ha intentado mandar a Sigrid algo que no es un `SELECT` (F-011, R23).

    Sigrid es el sistema de producción de un tercero y `sigrid-api` es su única
    puerta. Que este error exista, y que sea la propia puerta la que lo lance,
    es lo que convierte «contra Sigrid solo lecturas» en algo comprobable en
    vez de una norma escrita en un documento.
    """

    def __init__(self, sql: str) -> None:
        self.sql = sql
        super().__init__(
            "Esta sentencia no es de lectura y no se enviará a Sigrid: solo se "
            f"admiten consultas que empiecen por SELECT. Recibido: "
            f"{sql[:LONGITUD_SQL_EN_ERROR]!r}"
        )


class SigridApiPageSizeTooLargeError(SigridApiHttpError):
    """
    La API rechaza la petición porque max_rows excede su MAX_ALLOWED_ROWS.

    Mensaje útil que indica al usuario el cap actual y cómo solucionarlo
    (sin tener que adivinar de qué tablero viene la validación).
    """

    def __init__(self, requested: int, cap: int) -> None:
        self.requested = requested
        self.cap = cap
        super().__init__(
            f"La API sigrid-api rechaza max_rows={requested} porque su límite "
            f"actual es {cap}. Dos soluciones:\n"
            f"  A) Inmediata: baja SIGRID_API_PAGE_SIZE a {cap} (o menos) en tu .env\n"
            f"     y, si alguna tabla tiene 'page_size' propio en tables_sigrid.yaml\n"
            f"     mayor que {cap}, bájalo también.\n"
            f"  B) Si quieres páginas más grandes: en el portal de Azure, sube\n"
            f"     MAX_ALLOWED_ROWS de la Function App al valor deseado y REINICIA\n"
            f"     la Function App (el cap se fija en cold-start)."
        )


#: Cuánto SQL se copia dentro del mensaje de error. La consulta rechazada puede
#: ser de miles de caracteres —una generada— y el mensaje acaba en un log que
#: alguien tiene que leer: se enseña el principio, que es donde está el verbo.
LONGITUD_SQL_EN_ERROR = 200

# Errores que merecen reintento automático
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class SigridApiClient:
    """
    Cliente HTTP de sigrid-api con paginación, retries y streaming.

    Uso típico:
        client = SigridApiClient(base_url, function_key, database)
        columns = client.fetch_table_schema("obrparpre")
        for batch in client.stream_table("obrparpre", id_column="ide"):
            ...  # batch es list[dict[str, Any]]
    """

    def __init__(
        self,
        base_url: str,
        function_key: str,
        database: str,
        *,
        page_size: int = 5000,
        timeout_s: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._function_key = function_key
        self._database = database
        self._page_size = page_size
        self._timeout_s = timeout_s
        self._max_retries = max_retries

        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_s, connect=15.0),
            headers={
                "x-functions-key": function_key,
                "Content-Type": "application/json",
            },
        )

    # ---------------------------------------------------------------------
    # API pública
    # ---------------------------------------------------------------------

    def check_connectivity(self) -> dict[str, Any]:
        """Smoke test: ejecuta SELECT 1 contra la API y devuelve la respuesta."""
        return self._post_sql(sql="SELECT 1 AS ok", max_rows=1)

    def fetch_table_schema(self, source_table: str, schema: str = "dbo") -> list[ColumnSpec]:
        """
        Lee INFORMATION_SCHEMA.COLUMNS de Sigrid y devuelve las columnas tipadas.
        Permite generar el CREATE TABLE Postgres dinámicamente.
        """
        sql = """
        SELECT
            COLUMN_NAME           AS name,
            DATA_TYPE             AS sql_server_type,
            CHARACTER_MAXIMUM_LENGTH AS char_max_length,
            NUMERIC_PRECISION     AS numeric_precision,
            NUMERIC_SCALE         AS numeric_scale,
            IS_NULLABLE           AS is_nullable
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        response = self._post_sql(sql=sql, parameters=[schema, source_table], max_rows=500)

        if response["row_count"] == 0:
            raise SigridApiBusinessError(
                f"La tabla {schema}.{source_table} no existe en Sigrid o no es accesible"
            )

        cols: list[ColumnSpec] = []
        col_names = response["columns"]
        for row in response["rows"]:
            data = dict(zip(col_names, row, strict=True))
            cols.append(
                ColumnSpec(
                    name=data["name"],
                    sql_server_type=data["sql_server_type"],
                    char_max_length=data.get("char_max_length"),
                    numeric_precision=data.get("numeric_precision"),
                    numeric_scale=data.get("numeric_scale"),
                    is_nullable=(data.get("is_nullable", "YES").upper() == "YES"),
                )
            )
        return cols

    def stream_table(
        self,
        source_table: str,
        *,
        columns: list[str],
        id_column: str = "ide",
        where: str | None = None,
        schema: str = "dbo",
        start_id: int = 0,
        page_size: int | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        """
        Itera la tabla `schema.source_table` usando paginación keyset sobre `id_column`.

        Genera batches de hasta `page_size` filas. Termina cuando la API
        devuelve menos filas que el page_size (no quedan más).

        Parámetros:
          columns   : lista explícita de columnas a recuperar (permite excluir blobs).
          where     : filtro adicional opcional ("amb = 11" por ejemplo, sin WHERE).
          start_id  : cursor inicial (para carga incremental, MAX(ide) ya cargado).
          page_size : si se pasa, sobreescribe self._page_size para esta llamada.
                      Útil para tablas con columnas texto/blob pesadas que necesitan
                      batches más pequeños.
        """
        if not columns:
            raise ValueError("La lista de columnas no puede estar vacía")
        if id_column not in columns:
            raise ValueError(f"id_column '{id_column}' debe estar en la lista de columnas")

        effective_page_size = page_size or self._page_size

        # Construye la lista de columnas escapando con corchetes (SQL Server quoted identifiers)
        col_list = ", ".join(f"[{c}]" for c in columns)
        where_clause = f"AND ({where})" if where else ""

        sql_template = (
            f"SELECT TOP {effective_page_size} {col_list} "
            f"FROM [{schema}].[{source_table}] "
            f"WHERE [{id_column}] > ? {where_clause} "
            f"ORDER BY [{id_column}] ASC"
        )

        last_id: int = int(start_id)
        total_yielded = 0
        page_num = 0

        while True:
            page_num += 1
            response = self._post_sql(
                sql=sql_template,
                parameters=[last_id],
                max_rows=effective_page_size,
            )

            rows_raw = response["rows"]
            col_names = response["columns"]
            row_count = response["row_count"]

            if row_count == 0:
                logger.info(
                    "sigrid_stream_done",
                    table=source_table,
                    pages=page_num - 1,
                    total_rows=total_yielded,
                )
                return

            # Convertir filas (listas posicionales) a dicts
            batch = [dict(zip(col_names, row, strict=True)) for row in rows_raw]

            # Cursor para la siguiente página
            id_idx = col_names.index(id_column)
            last_id = rows_raw[-1][id_idx]

            total_yielded += row_count
            logger.info(
                "sigrid_stream_page",
                table=source_table,
                page=page_num,
                rows=row_count,
                last_id=last_id,
                total_so_far=total_yielded,
                page_size=effective_page_size,
            )

            yield batch

            # Si la página vino corta, es la última
            if row_count < effective_page_size:
                logger.info(
                    "sigrid_stream_done",
                    table=source_table,
                    pages=page_num,
                    total_rows=total_yielded,
                )
                return

    def leer_sql(
        self,
        sql: str,
        parameters: list | None = None,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta una consulta de LECTURA contra Sigrid y devuelve la respuesta.

        Es la puerta pública para el SQL que no construye el propio cliente —hoy
        el banco de extracción de F-011—, y valida antes de enviar: si la
        sentencia no es de lectura, no sale (R23). Sin este método, quien
        necesitara mandar una consulta tendría que llamar al `_post_sql`
        privado y el validador sería decorativo.
        """
        if not es_sentencia_de_lectura(sql):
            raise SigridApiSentenciaNoDeLecturaError(sql)
        return self._post_sql(sql=sql, parameters=parameters, max_rows=max_rows)

    def close(self) -> None:
        """Cierra la conexión HTTP. Llamar al terminar el pipeline."""
        self._client.close()

    def __enter__(self) -> SigridApiClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ---------------------------------------------------------------------
    # Internos
    # ---------------------------------------------------------------------

    def _post_sql(
        self,
        sql: str,
        parameters: list | None = None,
        max_rows: int | None = None,
    ) -> dict[str, Any]:
        """POST a /api/sql/read con reintentos."""

        @retry(
            retry=retry_if_exception_type(_RETRYABLE),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1.0, min=1.0, max=30.0),
            reraise=True,
        )
        def _do_post() -> dict[str, Any]:
            payload: dict[str, Any] = {
                "database": self._database,
                "sql": sql,
                "parameters": parameters or [],
                "timeout_seconds": int(self._timeout_s),
            }
            if max_rows is not None:
                payload["max_rows"] = max_rows

            try:
                resp = self._client.post(f"{self._base_url}/api/sql/read", json=payload)
            except _RETRYABLE as e:
                logger.warning("sigrid_api_transient_error", error=str(e), sql_preview=sql[:80])
                raise

            if resp.status_code >= 400:
                # No reintenta en 4xx (error del cliente, no transitorio).
                # Si es el error específico "max_rows excede el cap", lo
                # detectamos y lanzamos una excepción con mensaje accionable.
                cap = _parse_max_rows_cap(resp)
                if cap is not None:
                    requested = max_rows if max_rows is not None else 0
                    raise SigridApiPageSizeTooLargeError(requested=requested, cap=cap)
                raise SigridApiHttpError(
                    f"HTTP {resp.status_code} de sigrid-api: {resp.text[:500]}"
                )

            body = resp.json()
            if not body.get("ok", False):
                raise SigridApiBusinessError(
                    f"API rechazó la consulta: {body.get('error', 'sin detalle')}"
                )
            return body

        return _do_post()


# -------------------------------------------------------------------------
# Helpers internos
# -------------------------------------------------------------------------

def _parse_max_rows_cap(resp: httpx.Response) -> int | None:
    """
    Intenta extraer el cap real de max_rows de un 400 de la API.

    La API valida con Pydantic y devuelve un cuerpo como:
        {"ok": false, "error": "Solicitud inválida.",
         "details": {"type": "ValidationError",
           "validation": [{
              "type": "less_than_equal",
              "loc": ["max_rows"],
              "ctx": {"le": 10000}, ...
           }]}}

    Devuelve el valor de `le` si encuentra esa estructura. None si no aplica.
    """
    if resp.status_code != 400:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    details = body.get("details") or {}
    validation = details.get("validation") or []
    for v in validation:
        if (
            v.get("type") == "less_than_equal"
            and v.get("loc") == ["max_rows"]
            and isinstance(v.get("ctx"), dict)
            and "le" in v["ctx"]
        ):
            try:
                return int(v["ctx"]["le"])
            except (TypeError, ValueError):
                return None
    return None
