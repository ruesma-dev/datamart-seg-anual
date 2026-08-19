# tests/test_f016_huecos_alto_f005.py
"""
F-016 · Los seis huecos de riesgo ALTO de F-005.

Cada test de este fichero existe para **matar un mutante concreto** de la
línea base `progress/mutacion_F-005.md` (§ «Los seis de riesgo ALTO»). No son
tests de cortesía: si se invierte la línea que fijan, el test se pone rojo.

| Hueco | Línea en la base (árbol `c7500d4`) | Test |
|---|---|---|
| 1 | `config/settings.py:103` | `..._h1_...` |
| 2 | `postgres_client.py:78` | `..._h2_...` |
| 3 | `postgres_client.py:201` | `..._h3_...` |
| 4 | `fingerprint.py:334` | `..._h4_...` |
| 5 | `fingerprint.py:405` | `..._h5_...` |
| 6 | `main.py:388` | `..._h6_...` |

Sin red y sin BBDD: la configuración se lee sin `.env`, el cliente Postgres
nunca llega a `psycopg` (se sustituye su única puerta de conexión) y el CLI se
invoca con `CliRunner` sobre dobles.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from click.testing import CliRunner

import main
from config.settings import PostgresSettings
from etl_sigrid.domain.entities import StepResult, StepStatus
from etl_sigrid.infrastructure.postgres import fingerprint as fp
from etl_sigrid.infrastructure.postgres.postgres_client import PostgresClient

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


class _CursorFalso:
    """Cursor que apunta lo que se le ejecuta y contesta lo que se le diga."""

    def __init__(self, respuesta: tuple | None) -> None:
        self.respuesta = respuesta
        self.ejecutadas: list[Any] = []

    def __enter__(self) -> _CursorFalso:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, consulta: Any, *_: Any) -> None:
        self.ejecutadas.append(consulta)

    def fetchone(self) -> tuple | None:
        return self.respuesta


class _ConexionFalsa:
    """Conexión que no abre nada. Solo sirve cursores y se deja cerrar."""

    def __init__(self, respuesta: tuple | None = (1,)) -> None:
        self.cursor_falso = _CursorFalso(respuesta)
        self.cerrada = False

    def cursor(self) -> _CursorFalso:
        return self.cursor_falso

    def close(self) -> None:
        self.cerrada = True


def _cliente_sin_red(**kwargs: Any) -> PostgresClient:
    """Cliente Postgres con cadenas de mentira: nadie va a conectarse con ellas."""
    return PostgresClient(
        conninfo="dbname=de_mentira",
        admin_conninfo="dbname=admin_de_mentira",
        target_db="sigrid_dm",
        **kwargs,
    )


def _rastrear_bootstrap(
    monkeypatch: pytest.MonkeyPatch, cliente: PostgresClient
) -> list[str]:
    """Sustituye las tres ramas de `_auto_bootstrap` por testigos."""
    llamadas: list[str] = []

    def _crear() -> bool:
        llamadas.append("crear")
        return False

    def _comprobar() -> None:
        llamadas.append("comprobar")

    def _schemas() -> None:
        llamadas.append("schemas")

    monkeypatch.setattr(cliente, "_ensure_database", _crear)
    monkeypatch.setattr(cliente, "_assert_database_reachable", _comprobar)
    monkeypatch.setattr(cliente, "_bootstrap_schemas_and_meta", _schemas)
    return llamadas


def _metricas(bloque: str, metrica: str, valor: str) -> list[fp.Metrica]:
    """Huella de una sola vista con una sola métrica."""
    return [fp.Metrica("mart", "v_fact", bloque, metrica, valor)]


def _settings_minimo() -> SimpleNamespace:
    """Lo justo para que el grupo de comandos arranque sin leer `.env`."""
    return SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console")
    )


# ---------------------------------------------------------------------------
# Hueco 1 · el defecto de auto_create_db en la CONFIGURACIÓN
# (línea base: `config/settings.py:103`, `True,` -> `False,`)
# ---------------------------------------------------------------------------


def test_f016_h1_el_defecto_de_auto_create_db_en_la_configuracion_es_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    `PG_AUTO_CREATE_DB` es la puerta bloqueante de F-005 contra el servidor
    compartido de producción, y su defecto es deliberado: **True** en
    desarrollo (una base local que no existe se crea sola) y **False** en
    Azure, puesto a mano en el entorno. Cambiar el defecto a False dejaría
    verde la suite y rompería en silencio el arranque en local; cambiarlo a
    True cuando alguien lo hubiera bajado devolvería el auto-bootstrap al
    servidor compartido. Por eso el valor se fija aquí, no se supone.
    """
    campo = PostgresSettings.model_fields["auto_create_db"]
    assert campo.default is True, (
        "el defecto declarado de auto_create_db ha cambiado; si es a propósito, "
        "hay que revisar el runbook de Azure y este test"
    )

    # Y el mismo valor, ya construido el objeto, sin `.env` ni variables de
    # entorno de por medio: el defecto es del código, no del fichero de turno.
    monkeypatch.delenv("PG_AUTO_CREATE_DB", raising=False)
    assert PostgresSettings(_env_file=None).auto_create_db is True


# ---------------------------------------------------------------------------
# Hueco 2 · el defecto de auto_create_db en el CLIENTE
# (línea base: `postgres_client.py:78`, `auto_create_db: bool = True,`)
# ---------------------------------------------------------------------------


def test_f016_h2_el_defecto_de_auto_create_db_en_el_cliente_crea_la_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Sin pasar el parámetro, el cliente toma el camino de creación. Es la otra
    punta del mismo interruptor: `main._get_pg()` lo pasa explícitamente, pero
    cualquier otro constructor del cliente hereda este defecto.
    """
    cliente = _cliente_sin_red()
    llamadas = _rastrear_bootstrap(monkeypatch, cliente)

    cliente._auto_bootstrap()

    assert llamadas == ["crear", "schemas"], (
        "por defecto el cliente asegura la base creándola; no se limita a "
        "comprobar que existe"
    )


def test_f016_h2_con_auto_create_db_false_no_se_toca_la_bbdd_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    El otro lado de la puerta: con el interruptor bajado NUNCA se ejecuta
    `CREATE DATABASE` ni se abre la conexión administrativa. Es lo obligatorio
    contra `psql-albaranes-rs9k2`, donde viven albaranes y partes.
    """
    cliente = _cliente_sin_red(auto_create_db=False)
    llamadas = _rastrear_bootstrap(monkeypatch, cliente)

    cliente._auto_bootstrap()

    assert llamadas == ["comprobar", "schemas"]
    assert "crear" not in llamadas


# ---------------------------------------------------------------------------
# Hueco 3 · la conexión administrativa se abre en autocommit
# (línea base: `postgres_client.py:201`, `autocommit=True` -> `False`)
# ---------------------------------------------------------------------------


def test_f016_h3_la_conexion_administrativa_se_abre_en_autocommit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    `CREATE DATABASE` no puede ejecutarse dentro de una transacción: sin
    autocommit, Postgres rechaza la sentencia. No es un detalle de estilo, es
    una condición de corrección, y hasta hoy no la comprobaba nadie.
    """
    cliente = _cliente_sin_red()
    conexion = _ConexionFalsa(respuesta=(1,))  # la base ya existe
    aperturas: list[tuple[Any, bool]] = []

    def _abrir(conninfo: Any, *, autocommit: bool = False) -> _ConexionFalsa:
        aperturas.append((conninfo, autocommit))
        return conexion

    monkeypatch.setattr(cliente, "_connect", _abrir)

    assert cliente._ensure_database() is False, "la base ya existía: no se crea"

    assert aperturas == [("dbname=admin_de_mentira", True)], (
        "la conexión administrativa se abre contra la BBDD admin y en "
        "autocommit; sin autocommit CREATE DATABASE falla"
    )
    assert conexion.cerrada, "la conexión administrativa se cierra siempre"


# ---------------------------------------------------------------------------
# Hueco 4 · igualdad de valores de TEXTO al comparar dos huellas
# (línea base: `fingerprint.py:334`, `==` -> `!=`)
# ---------------------------------------------------------------------------


def test_f016_h4_la_comparacion_de_textos_distingue_iguales_de_distintos() -> None:
    """
    El núcleo de la verificación de que las vistas responden igual en Azure que
    en local. Los tests de F-005 solo pisaban la rama numérica y la de igualdad
    exacta; la rama de texto —la que se usa cuando un agregado no es un
    número— no la comprobaba nadie. Invertida, dos huellas idénticas se
    declararían distintas y dos distintas, iguales.
    """
    iguales = fp.comparar(
        _metricas(fp.BLOQUE_CERRADO, "sum_importe", "n/d"),
        _metricas(fp.BLOQUE_CERRADO, "sum_importe", "n/d"),
    )
    assert iguales == [], "dos valores de texto idénticos no son una diferencia"

    distintos = fp.comparar(
        _metricas(fp.BLOQUE_CERRADO, "sum_importe", "n/d"),
        _metricas(fp.BLOQUE_CERRADO, "sum_importe", "s/d"),
    )
    assert [d.gravedad for d in distintos] == [fp.FALLO]
    assert distintos[0].detalle == "texto", "se comparó como texto, no como número"
    assert (distintos[0].valor_a, distintos[0].valor_b) == ("n/d", "s/d")


# ---------------------------------------------------------------------------
# Hueco 5 · la clasificación de una diferencia como FALLO
# (línea base: `fingerprint.py:405`, `gravedad == FALLO` -> `!=`)
# ---------------------------------------------------------------------------


def test_f016_h5_el_detalle_de_la_diferencia_corresponde_a_su_gravedad() -> None:
    """
    De esta decisión depende que la verificación de la carga en Azure dé por
    buena una carga mala. F-005 ya comprobaba la **gravedad**; lo que nadie
    comprobaba es que el motivo escrito al lado sea el suyo: invertida, un
    FALLO se explicaría como «diferencia en el periodo vivo, esperable», que es
    exactamente la frase con la que un humano archiva un problema real.
    """
    fallo = fp.comparar(
        _metricas(fp.BLOQUE_CERRADO, fp.METRICA_COUNT, "1000"),
        _metricas(fp.BLOQUE_CERRADO, fp.METRICA_COUNT, "1001"),
    )
    assert [d.gravedad for d in fallo] == [fp.FALLO]
    assert "igualdad exacta" in fallo[0].detalle
    assert "esperable" not in fallo[0].detalle

    aviso = fp.comparar(
        _metricas(fp.BLOQUE_VIVO, fp.METRICA_COUNT, "1000"),
        _metricas(fp.BLOQUE_VIVO, fp.METRICA_COUNT, "1200"),
    )
    assert [d.gravedad for d in aviso] == [fp.AVISO]
    assert "periodo vivo" in aviso[0].detalle
    assert "igualdad exacta" not in aviso[0].detalle


# ---------------------------------------------------------------------------
# Hueco 6 · la detección de un paso fallido del pipeline
# (línea base: `main.py:388`, `status == FAILED` -> `!=`)
# ---------------------------------------------------------------------------


def _invocar_apply_grants(
    monkeypatch: pytest.MonkeyPatch, estado: StepStatus
) -> Any:
    """Invoca `apply-grants` con un paso de mentira que termina en `estado`."""
    monkeypatch.setattr(main, "get_settings", lambda: _settings_minimo())
    monkeypatch.setattr(main, "configure_logging", lambda **_: None)

    class _PasoFalso:
        def __init__(self, _settings: Any) -> None:
            pass

        @property
        def stage(self) -> str:
            # F-024: `_ejecutar_paso` lo necesita para registrar la fila.
            return "apply_grants"

        def run(self) -> StepResult:
            inicio = datetime(2026, 8, 10, 3, 0, 0)
            return StepResult(
                step_name="apply_grants",
                status=estado,
                started_at=inicio,
                finished_at=inicio,
            )

    class _PgFalso:
        """F-024: `apply-grants` pasa por el cliente para marcar y registrar.

        Este test mide el CÓDIGO DE SALIDA del comando, no el registro, así que
        el doble se limita a no estorbar.
        """

        def abortar_runs_huerfanos(self, batch_id: str, ahora: Any = None) -> list:
            return []

        def record_run_completed(self, **_kwargs: Any) -> int:
            return 1

    monkeypatch.setattr(main, "_get_pg", _PgFalso)
    monkeypatch.setattr(main, "ApplyGrantsStep", _PasoFalso)
    return CliRunner().invoke(main.cli, ["apply-grants"])


def test_f016_h6_un_paso_fallido_hace_salir_al_cli_con_codigo_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Invertida la comparación, el CLI daría por buena una ejecución fallida: el
    job nocturno terminaría en verde con los permisos sin aplicar y nadie se
    enteraría hasta que el MCP dejara de leer.
    """
    resultado = _invocar_apply_grants(monkeypatch, StepStatus.FAILED)

    assert resultado.exit_code == 1, resultado.output
    assert "FAILED" in resultado.output


def test_f016_h6_un_paso_correcto_hace_salir_al_cli_con_codigo_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El otro lado de la misma comparación: lo que va bien sale con 0."""
    resultado = _invocar_apply_grants(monkeypatch, StepStatus.SUCCESS)

    assert resultado.exit_code == 0, resultado.output
    assert "SUCCESS" in resultado.output
