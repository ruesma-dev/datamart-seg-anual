# etl_sigrid/infrastructure/postgres/sesion_carga.py
"""
Sesión de carga de una tabla de `raw`: UNA conexión, COPY + COMMIT por página
(F-148, R8-R13).

Hasta F-148 `copy_rows` abría una conexión NUEVA por página de `sigrid-api`:
~2.800 solo en `obrparpre`, ~3 por segundo contra el Postgres compartido, y la
noche que una se colgaba 130 s moría la ingesta entera
(`progress/explore_F-148_corte.md`). Aquí la tabla entera viaja por una sola
conexión, abierta en la primera página.

**El contrato DA-8 no cambia**: cada página se confirma con su propio COMMIT,
así que lo cargado no se pierde si cae la página siguiente.

**Si la conexión se rompe** durante el COPY o el COMMIT de una página, se cierra,
se abre otra (con el reintento de `reintento_conexion`) y se repite ESA página,
hasta `REINTENTOS_PAGINA` veces. Antes de repetirla se cuenta lo que hay en la
tabla dentro del rango de ids de la página —las tablas de `raw` tienen PK en
`id_column`—: cero, se copia; tantas como la página, el COMMIT llegó y solo se
perdió el acuse, así que no se copia otra vez; cualquier otra cifra no tiene
explicación inocente y la tabla falla («página ambigua»). Un error que no es de
conexión —datos, clave duplicada, permisos— no se reintenta (R12).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import psycopg
from psycopg import sql

from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.conninfo import safe_dsn
from etl_sigrid.infrastructure.postgres.postgres_client import SQL_FILAS_EN_RANGO, linea_copy

logger = get_logger(__name__)

#: Cuántas veces se repite una página tras romperse la conexión (R10).
REINTENTOS_PAGINA = 3


class PaginaAmbiguaError(RuntimeError):
    """Tras una rotura, la tabla tiene parte de la página: ni repetir ni seguir."""


@dataclass(frozen=True, slots=True)
class MedidaPagina:
    """Lo que costó una página (R14), en segundos con 3 decimales.

    `pg_connect_s` es el tiempo de (re)conexión dentro de la página (0 si se
    reutilizó la conexión); `copy_s`, todo lo demás: COPY, COMMIT y, si hubo
    rotura, el recuento.
    """

    filas: int
    copy_s: float
    pg_connect_s: float
    reintentos: int


class SesionDeCarga:
    """Carga las páginas de UNA tabla por una sola conexión."""

    def __init__(
        self,
        abrir: Callable[[], Any],
        schema: str,
        table: str,
        columns: Sequence[str],
        *,
        id_column: str,
        tiemod_column: str | None = None,
    ) -> None:
        if id_column not in columns:
            raise ValueError(
                f"la columna id '{id_column}' no está entre las columnas de {schema}.{table}: "
                f"sin ella no se puede comprobar una página tras una rotura"
            )
        self._abrir = abrir
        self._tabla = f"{schema}.{table}"
        self._id_column = id_column
        self._campos = [*columns, tiemod_column] if tiemod_column else list(columns)
        destino = [*columns, "_source_tiemod"] if tiemod_column else list(columns)
        self._copia = sql.SQL("COPY {}.{} ({}) FROM STDIN WITH (FORMAT text, NULL '\\N')").format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in destino),
        )
        self._recuento = sql.SQL(SQL_FILAS_EN_RANGO).format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            id=sql.Identifier(id_column),
        )
        self._conn: Any = None

    def copiar_pagina(self, filas: Sequence[dict[str, Any]]) -> MedidaPagina:
        """COPY + COMMIT de una página; ante una rotura, reconecta y la repite."""
        inicio = perf_counter()
        conexion_s = 0.0
        reintentos = 0
        comprobar = False
        while True:
            if self._conn is None:
                antes = perf_counter()
                self._conn = self._abrir()
                conexion_s += perf_counter() - antes
            try:
                if not (comprobar and self._ya_confirmada(filas)):
                    self._copiar(filas)
                break
            except Exception as error:
                rota = isinstance(error, psycopg.OperationalError) and self._rota()
                if not rota or reintentos == REINTENTOS_PAGINA:
                    self._descartar()
                    raise
                self.cerrar()
                reintentos += 1
                comprobar = True
                logger.warning(
                    "ingest_pagina_reintento",
                    table=self._tabla,
                    reintento=reintentos,
                    error=safe_dsn(str(error)),
                )
        return MedidaPagina(
            filas=len(filas),
            copy_s=round(perf_counter() - inicio - conexion_s, 3),
            pg_connect_s=round(conexion_s, 3),
            reintentos=reintentos,
        )

    def cerrar(self) -> None:
        """Cierra la conexión, si hay. Se puede llamar más de una vez (R13)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------

    def _copiar(self, filas: Sequence[dict[str, Any]]) -> None:
        with self._conn.cursor() as cur, cur.copy(self._copia) as copia:
            for fila in filas:
                copia.write(linea_copy(fila, self._campos))
        self._conn.commit()

    def _ya_confirmada(self, filas: Sequence[dict[str, Any]]) -> bool:
        """R11: ¿llegó la página antes de la rotura? Sí, no o «ambigua»."""
        ids = [fila[self._id_column] for fila in filas]
        rango = {"lo": min(ids), "hi": max(ids)}
        with self._conn.cursor() as cur:
            cur.execute(self._recuento, rango)
            (presentes,) = cur.fetchone()
        # Que el recuento no deje una transacción abierta mientras se espera a
        # la siguiente página de `sigrid-api`.
        self._conn.commit()
        if presentes == 0:
            return False
        if presentes == len(filas):
            return True
        raise PaginaAmbiguaError(
            f"página ambigua en {self._tabla}: {presentes} filas con {self._id_column} "
            f"entre {rango['lo']} y {rango['hi']} y la página trae {len(filas)}"
        )

    def _rota(self) -> bool:
        return bool(self._conn.broken or self._conn.closed)

    def _descartar(self) -> None:
        """Tras un error que no se reintenta: cerrar si está rota, deshacer si no."""
        if self._rota():
            self.cerrar()
        else:
            self._conn.rollback()
