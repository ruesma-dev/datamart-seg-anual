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

import logging

import psycopg
import pytest
from psycopg import errors as pg_errors

from config.settings import PostgresSettings
from etl_sigrid.infrastructure.postgres import conninfo, reintento_conexion
from etl_sigrid.infrastructure.postgres.reintento_conexion import (
    abrir_con_reintento,
    es_error_transitorio,
    psycopg_en_debug,
)


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


# ---------------------------------------------------------------------------
# R3-R4 · qué error se reintenta y cuál no
# ---------------------------------------------------------------------------

TRANSITORIOS = [
    pytest.param(pg_errors.ConnectionTimeout("connection timeout expired"), id="timeout"),
    pytest.param(psycopg.OperationalError("connection failed: server closed"), id="sin-sqlstate"),
    pytest.param(pg_errors.lookup("08006")("se cayó"), id="08006"),
    pytest.param(pg_errors.lookup("08001")("no conecta"), id="08001"),
    pytest.param(pg_errors.lookup("53300")("too many connections"), id="53300"),
    pytest.param(pg_errors.lookup("57P03")("the database system is starting up"), id="57P03"),
]

DEFINITIVOS = [
    pytest.param(pg_errors.lookup("28P01")("rechazado"), id="28P01"),
    pytest.param(pg_errors.lookup("28000")("rechazado"), id="28000"),
    pytest.param(pg_errors.lookup("3D000")("no existe"), id="3D000"),
    pytest.param(
        psycopg.OperationalError('FATAL:  password authentication failed for user "etl"'),
        id="password",
    ),
    pytest.param(
        psycopg.OperationalError('FATAL:  no pg_hba.conf entry for host "1.2.3.4"'),
        id="pg_hba",
    ),
    pytest.param(psycopg.OperationalError('FATAL:  role "etl" does not exist'), id="rol"),
    pytest.param(
        psycopg.OperationalError('FATAL:  database "sigrid_dm" does not exist'), id="base",
    ),
    pytest.param(pg_errors.lookup("57014")("canceling statement"), id="57014-otro-operational"),
    pytest.param(pg_errors.lookup("42501")("permission denied"), id="permiso"),
    pytest.param(ValueError("no es de psycopg"), id="ajeno"),
]


@pytest.mark.parametrize("error", TRANSITORIOS)
def test_f148_r3_errores_transitorios(error: BaseException) -> None:
    assert es_error_transitorio(error) is True


@pytest.mark.parametrize("error", DEFINITIVOS)
def test_f148_r4_errores_que_no_se_reintentan(error: BaseException) -> None:
    assert es_error_transitorio(error) is False


def test_f148_r4_la_autenticacion_manda_sobre_la_clase_de_conexion() -> None:
    """Un 08 que trae la marca de autenticación no se reintenta: la contraseña
    mala no se arregla esperando, y reintentar bloquearía la cuenta antes."""
    error = pg_errors.lookup("08006")("password authentication failed for user x")
    assert es_error_transitorio(error) is False


# ---------------------------------------------------------------------------
# R3, R5, R6 · el reintento con espera creciente
# ---------------------------------------------------------------------------


class Apertura:
    """`abrir` de mentira: falla con los errores dados y luego conecta."""

    def __init__(self, *errores: BaseException) -> None:
        self._errores = list(errores)
        self.llamadas = 0

    def __call__(self) -> str:
        self.llamadas += 1
        if self._errores:
            raise self._errores.pop(0)
        return "conexion"


def _timeout() -> BaseException:
    return pg_errors.ConnectionTimeout("connection timeout expired")


def test_f148_r3_reintenta_con_espera_2_4_8() -> None:
    esperas: list[float] = []
    abrir = Apertura(_timeout(), _timeout(), _timeout())

    conexion, _segundos, intentos = abrir_con_reintento(abrir, intentos=4, dormir=esperas.append)

    assert conexion == "conexion"
    assert intentos == 4
    assert abrir.llamadas == 4
    assert esperas == [2, 4, 8]


def test_f148_r3_la_espera_tiene_tope_de_30() -> None:
    esperas: list[float] = []
    abrir = Apertura(*[_timeout() for _ in range(5)])

    abrir_con_reintento(abrir, intentos=6, dormir=esperas.append)

    assert esperas == [2, 4, 8, 16, 30]


def test_f148_r3_sin_fallo_un_solo_intento_y_sin_espera() -> None:
    esperas: list[float] = []

    conexion, _s, intentos = abrir_con_reintento(Apertura(), intentos=4, dormir=esperas.append)

    assert (conexion, intentos, esperas) == ("conexion", 1, [])


def test_f148_r3_mide_los_segundos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reintento_conexion, "perf_counter", Reloj(10.0, 12.5))

    _c, segundos, _i = abrir_con_reintento(Apertura(), intentos=4, dormir=lambda _s: None)

    assert segundos == pytest.approx(2.5)


def test_f148_r5_agotados_los_intentos_propaga_el_ultimo_error() -> None:
    ultimo = pg_errors.ConnectionTimeout("el cuarto")
    abrir = Apertura(_timeout(), _timeout(), _timeout(), ultimo)

    with pytest.raises(pg_errors.ConnectionTimeout) as exc:
        abrir_con_reintento(abrir, intentos=4, dormir=lambda _s: None)

    assert exc.value is ultimo
    assert abrir.llamadas == 4


def test_f148_r4_la_autenticacion_falla_al_primer_intento() -> None:
    esperas: list[float] = []
    abrir = Apertura(psycopg.OperationalError("password authentication failed for user x"))

    with pytest.raises(psycopg.OperationalError):
        abrir_con_reintento(abrir, intentos=4, dormir=esperas.append)

    assert abrir.llamadas == 1
    assert esperas == []


def test_f148_r3_r6_el_reintento_se_registra_sin_secretos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registro = LoggerFalso()
    monkeypatch.setattr(reintento_conexion, "logger", registro)
    error = psycopg.OperationalError("fallo con password=SUPERSECRETO host=x")

    abrir_con_reintento(Apertura(error), intentos=4, dormir=lambda _s: None)

    (aviso,) = registro.de("pg_conexion_reintento")
    assert aviso["intento"] == 1
    assert aviso["espera_s"] == 2
    assert "SUPERSECRETO" not in str(aviso)
    assert "password=***" in aviso["error"]


# ---------------------------------------------------------------------------
# R15 · psycopg en DEBUG solo mientras se conecta
# ---------------------------------------------------------------------------


def test_f148_r15_psycopg_en_debug_y_vuelve_a_su_nivel() -> None:
    registrador = logging.getLogger("psycopg")
    previo = registrador.level
    registrador.setLevel(logging.WARNING)
    try:
        with psycopg_en_debug():
            assert registrador.level == logging.DEBUG
        assert registrador.level == logging.WARNING
    finally:
        registrador.setLevel(previo)


def test_f148_r15_vuelve_a_su_nivel_aunque_falle() -> None:
    registrador = logging.getLogger("psycopg")
    previo = registrador.level
    registrador.setLevel(logging.ERROR)
    try:
        with pytest.raises(RuntimeError), psycopg_en_debug():
            raise RuntimeError("la conexión cae")
        assert registrador.level == logging.ERROR
    finally:
        registrador.setLevel(previo)


