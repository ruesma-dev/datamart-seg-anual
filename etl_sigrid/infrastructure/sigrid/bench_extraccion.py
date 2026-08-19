# etl_sigrid/infrastructure/sigrid/bench_extraccion.py
"""
Banco de pruebas de la extracción: qué rinde cada tamaño de página contra
sigrid-api (F-011, R4, R5, R5-bis).

Este módulo **no conoce el datamart**. No importa `PostgresClient` ni psycopg,
y hay un test que lo comprueba leyendo el fuente. No es cosmética: `bench-sigrid`
se lanza contra el SQL Server de producción de Sigrid para medir, y un comando
de diagnóstico que además pudiera escribir en el destino dejaría de serlo.

La consulta que se mide es **la misma que usa la ingesta**: keyset por `ide`,
`SELECT TOP n`, columnas explícitas. Medir con otra forma mediría otra cosa.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter

from etl_sigrid.domain.extraccion import MedicionPagina, es_sentencia_de_lectura
from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
    SigridApiPageSizeTooLargeError,
)

logger = get_logger(__name__)

CABECERA_CSV = (
    "page_size",
    "peticiones",
    "filas",
    "segundos",
    "filas_por_segundo",
    "latencia_media_s",
    "latencia_max_s",
    "rechazada",
    "cap_devuelto",
)


def construir_sql_de_pagina(
    source_table: str,
    columnas: Sequence[str],
    page_size: int,
    *,
    id_column: str = "ide",
    schema: str = "dbo",
    where: str | None = None,
) -> str:
    """
    La consulta de una página, idéntica en forma a la de `stream_table`.

    Se valida aquí mismo (R23): si el nombre de la tabla o el `where` traen
    algo que convierta la sentencia en otra cosa, esto se niega a devolver el
    SQL en vez de dejar que salga hacia `/api/sql/read`.
    """
    if not columnas:
        raise ValueError("La lista de columnas no puede estar vacía")

    col_list = ", ".join(f"[{c}]" for c in columnas)
    where_clause = f"AND ({where}) " if where else ""
    sql = (
        f"SELECT TOP {int(page_size)} {col_list} "
        f"FROM [{schema}].[{source_table}] "
        f"WHERE [{id_column}] > ? {where_clause}"
        f"ORDER BY [{id_column}] ASC"
    )

    if not es_sentencia_de_lectura(sql):
        raise ValueError(
            f"La consulta construida no es una sentencia de lectura y NO se "
            f"enviará a Sigrid (R23). Revisa el nombre de tabla o el filtro: {sql!r}"
        )
    return sql


def medir_pagina(
    api,
    source_table: str,
    *,
    columnas: Sequence[str],
    page_size: int,
    id_column: str = "ide",
    where: str | None = None,
    repeticiones: int = 1,
    desde_id: int = 0,
    reloj: Callable[[], float] = perf_counter,
) -> MedicionPagina:
    """
    Mide UN tamaño de página: tiempo, filas y latencia máxima por petición.

    Las repeticiones **avanzan el cursor** por keyset, igual que la ingesta. Si
    repitieran la misma página, la segunda mediría la caché del SQL Server y el
    número saldría bonito y falso.

    Un rechazo de la API (`SigridApiPageSizeTooLargeError`) no interrumpe nada:
    se devuelve la medición marcada como rechazada, con el cap que la propia
    API acredita en el cuerpo del 400 (R5).
    """
    sql = construir_sql_de_pagina(
        source_table, columnas, page_size, id_column=id_column, where=where
    )

    ultimo_id = desde_id
    peticiones = 0
    filas = 0
    total_s = 0.0
    latencia_max = 0.0

    for _ in range(max(1, repeticiones)):
        t0 = reloj()
        try:
            respuesta = api.leer_sql(sql, parameters=[ultimo_id], max_rows=page_size)
        except SigridApiPageSizeTooLargeError as e:
            logger.warning(
                "bench_page_size_rechazado", page_size=page_size, cap=e.cap
            )
            return MedicionPagina(
                page_size=page_size,
                peticiones=peticiones,
                filas=filas,
                segundos=total_s,
                latencia_max_s=latencia_max,
                rechazada=True,
                cap_devuelto=e.cap,
            )

        latencia = reloj() - t0
        total_s += latencia
        latencia_max = max(latencia_max, latencia)
        peticiones += 1

        recibidas = int(respuesta["row_count"])
        filas += recibidas
        logger.info(
            "bench_pagina",
            tabla=source_table,
            page_size=page_size,
            filas=recibidas,
            segundos=round(latencia, 3),
        )

        if recibidas < page_size:
            break  # la tabla se acabó: seguir pidiendo mediría el vacío

        idx = respuesta["columns"].index(id_column)
        ultimo_id = respuesta["rows"][-1][idx]

    return MedicionPagina(
        page_size=page_size,
        peticiones=peticiones,
        filas=filas,
        segundos=total_s,
        latencia_max_s=latencia_max,
    )


def barrer_paginas(
    api,
    source_table: str,
    *,
    columnas: Sequence[str],
    tamanos: Sequence[int],
    id_column: str = "ide",
    where: str | None = None,
    repeticiones: int = 1,
    reloj: Callable[[], float] = perf_counter,
) -> list[MedicionPagina]:
    """Recorre los tamaños pedidos, en orden, y devuelve una medición por cada uno."""
    return [
        medir_pagina(
            api,
            source_table,
            columnas=columnas,
            page_size=t,
            id_column=id_column,
            where=where,
            repeticiones=repeticiones,
            reloj=reloj,
        )
        for t in tamanos
    ]


def escribir_csv_bench(mediciones: Sequence[MedicionPagina], path: Path) -> None:
    """UTF-8 con BOM y separador `;`, según `docs/CONVENTIONS.md`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(CABECERA_CSV)
        for m in mediciones:
            escritor.writerow(
                [
                    m.page_size,
                    m.peticiones,
                    m.filas,
                    f"{m.segundos:.3f}",
                    f"{m.filas_por_segundo:.1f}",
                    f"{m.latencia_media_s:.3f}",
                    f"{m.latencia_max_s:.3f}",
                    "si" if m.rechazada else "no",
                    "" if m.cap_devuelto is None else m.cap_devuelto,
                ]
            )
