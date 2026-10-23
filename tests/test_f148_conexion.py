# tests/test_f148_conexion.py
"""
F-148 · La apertura de conexión (R1-R7, R15-R16).

La noche del 23-10 una apertura NUEVA se quedó colgada 130 s —el
`connect_timeout` por defecto de psycopg 3, que no configurábamos— y, sin
reintento, mató `ingest_raw`. Aquí se fija: la cadena lleva `connect_timeout`,
keepalives y `tcp_user_timeout`; un error transitorio se reintenta con espera
creciente y uno de autenticación NO; y la apertura deja rastro si tarda.

Ningún test abre red ni BBDD: psycopg se dobla, la espera se inyecta y el reloj
se sustituye.
"""

from __future__ import annotations

import psycopg
import pytest

from config.settings import PostgresSettings
from etl_sigrid.infrastructure.postgres import conninfo


def _pg(**kwargs: object) -> PostgresSettings:
    """`PostgresSettings` hermético: sin el `.env` del puesto."""
    base: dict[str, object] = {
        "host": "localhost",
        "db": "sigrid_dm",
        "user": "postgres",
        "password": "",
        "sslmode": "",
        "auth_mode": "password",
        "set_role": "",
    }
    base.update(kwargs)
    return PostgresSettings(_env_file=None, **base)  # type: ignore[arg-type]


class LoggerFalso:
    """Registra los eventos en vez de imprimirlos."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict]] = []

    def _anotar(self, nivel: str, evento: str, **campos: object) -> None:
        self.eventos.append((nivel, evento, campos))

    def info(self, evento: str, **campos: object) -> None:
        self._anotar("info", evento, **campos)

    def warning(self, evento: str, **campos: object) -> None:
        self._anotar("warning", evento, **campos)

    def de(self, evento: str) -> list[dict]:
        return [c for _n, e, c in self.eventos if e == evento]


class Reloj:
    """Reloj de mentira: devuelve los instantes que se le dan, en orden."""

    def __init__(self, *instantes: float) -> None:
        self._instantes = list(instantes)

    def __call__(self) -> float:
        return self._instantes.pop(0)


# ---------------------------------------------------------------------------
# R1-R2 · la cadena lleva connect_timeout, keepalives y tcp_user_timeout
# ---------------------------------------------------------------------------


def _parametros(dsn: str) -> dict[str, str]:
    return psycopg.conninfo.conninfo_to_dict(dsn)  # type: ignore[return-value]


def test_f148_r1_r2_la_cadena_lleva_los_valores_por_defecto() -> None:
    """Los valores decididos por el humano (D1, D2), sin variables en el job."""
    dsn = conninfo.build_conninfo(_pg(), "secreto")
    p = _parametros(dsn)

    assert p["connect_timeout"] == "15"
    assert p["keepalives"] == "1"
    assert p["keepalives_idle"] == "30"
    assert p["keepalives_interval"] == "10"
    assert p["keepalives_count"] == "3"
    assert p["tcp_user_timeout"] == "60000"


def test_f148_r1_tambien_la_cadena_admin() -> None:
    """La base admin abre conexión NUEVA igual: también le toca el timeout."""
    dsn = conninfo.make_admin_conninfo_provider(_pg(admin_db="postgres"))()
    p = _parametros(dsn)

    assert p["dbname"] == "postgres"
    assert p["connect_timeout"] == "15"
    assert p["tcp_user_timeout"] == "60000"


def test_f148_r1_r2_los_valores_vienen_de_la_configuracion() -> None:
    pg = _pg(
        connect_timeout_s=7,
        keepalives_idle_s=31,
        keepalives_interval_s=11,
        keepalives_count=4,
        tcp_user_timeout_ms=45000,
    )
    p = _parametros(conninfo.build_conninfo(pg, "x"))

    assert (p["connect_timeout"], p["keepalives_idle"], p["keepalives_interval"]) == (
        "7", "31", "11",
    )
    assert (p["keepalives_count"], p["tcp_user_timeout"]) == ("4", "45000")


def test_f148_r1_r2_r3_las_variables_de_entorno_se_leen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los nombres de las variables son contrato: `PG_` + campo en mayúsculas."""
    for variable, valor in (
        ("PG_CONNECT_TIMEOUT_S", "9"),
        ("PG_KEEPALIVES_IDLE_S", "40"),
        ("PG_KEEPALIVES_INTERVAL_S", "12"),
        ("PG_KEEPALIVES_COUNT", "5"),
        ("PG_TCP_USER_TIMEOUT_MS", "30000"),
        ("PG_CONNECT_INTENTOS", "6"),
    ):
        monkeypatch.setenv(variable, valor)
    pg = PostgresSettings(_env_file=None)  # type: ignore[call-arg]

    assert (pg.connect_timeout_s, pg.keepalives_idle_s, pg.keepalives_interval_s) == (9, 40, 12)
    assert (pg.keepalives_count, pg.tcp_user_timeout_ms, pg.connect_intentos) == (5, 30000, 6)


def test_f148_r3_intentos_por_defecto_cuatro() -> None:
    assert _pg().connect_intentos == 4


@pytest.mark.parametrize("valor", [2, 120])
def test_f148_r1_connect_timeout_admite_los_extremos(valor: int) -> None:
    assert _pg(connect_timeout_s=valor).connect_timeout_s == valor


@pytest.mark.parametrize("valor", [1, 121])
def test_f148_r1_connect_timeout_fuera_de_rango_aborta(valor: int) -> None:
    with pytest.raises(ValueError):
        _pg(connect_timeout_s=valor)


@pytest.mark.parametrize("valor", [1, 10])
def test_f148_r3_intentos_admite_los_extremos(valor: int) -> None:
    assert _pg(connect_intentos=valor).connect_intentos == valor


@pytest.mark.parametrize("valor", [0, 11])
def test_f148_r3_intentos_fuera_de_rango_aborta(valor: int) -> None:
    with pytest.raises(ValueError):
        _pg(connect_intentos=valor)
