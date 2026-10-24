# etl_sigrid/infrastructure/postgres/reintento_conexion.py
"""
Apertura de conexión con reintento (F-148, R3-R6 y R15).

La noche del 2026-10-23 una conexión NUEVA contra el Postgres compartido se
quedó colgada 130 s —el `connect_timeout` por defecto de psycopg 3, que no
configurábamos— y, sin reintento, la excepción mató `ingest_raw` entero. El
servidor estaba sano: los demás inquilinos conectaban con normalidad
(`progress/explore_F-148_corte.md`).

Tres piezas, las tres sin estado:

  - `es_error_transitorio` decide si un error de apertura merece otro intento.
    La autenticación y el destino inexistente NUNCA: esperar no los arregla y
    reintentarlos solo retrasa el aviso (y, con contraseña, acerca el bloqueo).
  - `abrir_con_reintento` reintenta con espera exponencial (2, 4, 8 s; tope
    30), con tenacity como el cliente de `sigrid-api`. Peor caso con los
    valores por defecto: 4 x 15 s + 2 + 4 + 8 = 74 s, menos que el cuelgue que
    sustituye.
  - `psycopg_en_debug` pone el logger de psycopg en DEBUG SOLO mientras se
    abre la conexión: psycopg 3.3 registra ahí cada intento («connection
    attempt», «connection failed», «connection succeeded»), que es lo que
    faltaba para saber en qué fase se cuelga.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import perf_counter, sleep

import psycopg
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from etl_sigrid.infrastructure.logging_config import get_logger
from etl_sigrid.infrastructure.postgres.conninfo import safe_dsn

logger = get_logger(__name__)


#: Espera exponencial entre intentos: base x 2^(n-1), entre el mínimo y el tope.
ESPERA_BASE_S = 2
ESPERA_MIN_S = 2
ESPERA_MAX_S = 30

#: SQLSTATE que sí son de la red o del servidor de paso: la clase 08 (conexión),
#: demasiadas conexiones y el servidor arrancando. Solo estos —o ninguno— se
#: reintentan, así que la clase 28 (autorización) y `3D000` (base inexistente)
#: quedan fuera sin nombrarlas (R4).
CLASE_CONEXION = "08"
SQLSTATES_TRANSITORIOS = frozenset({"53300", "57P03"})

#: psycopg 3.3 NO trae SQLSTATE al fallar la apertura: `generators.py` lanza
#: `OperationalError("connection failed: …")` con el texto de libpq y
#: `sqlstate` None, así que el 28P01 o el 42501 del servidor nunca llegan. El
#: texto es lo único que distingue un rechazo de una red caída. `pg_hba.conf`
#: cubre las dos formas del rechazo de la puerta («no pg_hba.conf entry» y
#: «pg_hba.conf rejects connection»); «permission denied for database» es la
#: falta de CONNECT (revisión de F-148, pasada 1).
MARCAS_DEFINITIVAS = (
    "password authentication failed",
    "pg_hba.conf",
    "permission denied for database",
)
_DESTINO_INEXISTENTE = re.compile(r"(role|database) .* does not exist")


def es_error_transitorio(exc: BaseException) -> bool:
    """True si abrir otra vez puede salir bien (R3); False si no (R4).

    Orden: lo definitivo primero —un 08 con la marca de contraseña sigue siendo
    una contraseña mala—; después, solo `OperationalError` (`ConnectionTimeout`
    lo es) sin SQLSTATE o con uno de red. Cualquier otro error no se reintenta.
    """
    texto = str(exc).lower()
    if any(marca in texto for marca in MARCAS_DEFINITIVAS) or _DESTINO_INEXISTENTE.search(texto):
        return False
    if not isinstance(exc, psycopg.OperationalError):
        return False
    sqlstate = exc.sqlstate or ""
    return not sqlstate or sqlstate.startswith(CLASE_CONEXION) or sqlstate in SQLSTATES_TRANSITORIOS


def _avisar_reintento(estado: RetryCallState) -> None:
    """`pg_conexion_reintento`, con el error redactado (R6)."""
    logger.warning(
        "pg_conexion_reintento",
        intento=estado.attempt_number,
        espera_s=estado.next_action.sleep,  # type: ignore[union-attr]
        error=safe_dsn(str(estado.outcome.exception())),  # type: ignore[union-attr]
    )


def abrir_con_reintento[T](
    abrir: Callable[[], T],
    *,
    intentos: int,
    dormir: Callable[[float], None] = sleep,
) -> tuple[T, float, int]:
    """Llama a `abrir` hasta `intentos` veces si el error es transitorio.

    Devuelve la conexión, los segundos que costó en total y cuántos intentos
    hicieron falta. Agotados los intentos, o ante un error que no es
    transitorio, propaga la ÚLTIMA excepción tal cual (R5). `dormir` se inyecta
    para que los tests no esperen.
    """
    inicio = perf_counter()
    reintentador = Retrying(
        stop=stop_after_attempt(intentos),
        wait=wait_exponential(multiplier=ESPERA_BASE_S, min=ESPERA_MIN_S, max=ESPERA_MAX_S),
        retry=retry_if_exception(es_error_transitorio),
        sleep=dormir,
        before_sleep=_avisar_reintento,
        reraise=True,
    )
    conexion = reintentador(abrir)
    return conexion, perf_counter() - inicio, reintentador.statistics["attempt_number"]


@contextmanager
def psycopg_en_debug() -> Iterator[None]:
    """El logger `psycopg` en DEBUG mientras dura el bloque, y luego como estaba (R15)."""
    registrador = logging.getLogger("psycopg")
    previo = registrador.level
    registrador.setLevel(logging.DEBUG)
    try:
        yield
    finally:
        registrador.setLevel(previo)
