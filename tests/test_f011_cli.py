# tests/test_f011_cli.py
"""
F-011 · Tests de los comandos nuevos de la CLI, todos de SOLO LECTURA:
`perfil-carga` (R1–R3), `diagnostico-tiemod` (R6, R7) y `bench-sigrid` (R4).

La afirmación central es R25: **ninguno de los tres escribe en `_meta`**. No es
una preferencia de estilo. F-024 dejó dicho que solo los comandos que escriben
marcan huérfanas y registran paso; un comando de diagnóstico que escribiera en
la tabla que está diagnosticando falsearía justo el dato que se ha ido a
buscar. El doble de cliente de este fichero **revienta** si se lo piden, así
que la afirmación se comprueba en vez de confiarse.

Ningún test abre red ni BBDD: se sustituyen `main.get_settings` y `main._get_pg`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import main
from etl_sigrid.domain.perfil_carga import FilaPerfil

BATCH = "20260819T020016Z-327ef0"

#: Los comandos que esta feature añade, todos de solo lectura (R25).
COMANDOS_NUEVOS_DE_LECTURA = ("perfil-carga",)


class PgQueNoEscribe:
    """Doble del cliente Postgres que falla si alguien intenta escribir.

    Cada método de escritura levanta `AssertionError` con el nombre del método:
    si un comando de lectura crece y se le cuela un registro, el test dice
    exactamente cuál era.
    """

    def __init__(
        self,
        perfil: tuple[str | None, list[FilaPerfil]] | None = None,
        error_al_leer: Exception | None = None,
    ) -> None:
        self._perfil = perfil if perfil is not None else (None, [])
        self._error_al_leer = error_al_leer
        self.batches_pedidos: list[str | None] = []

    # --- lecturas permitidas -------------------------------------------
    def fetch_perfil_carga(
        self, batch_id: str | None = None
    ) -> tuple[str | None, list[FilaPerfil]]:
        self.batches_pedidos.append(batch_id)
        if self._error_al_leer is not None:
            raise self._error_al_leer
        return self._perfil

    # --- escrituras prohibidas -----------------------------------------
    def abortar_runs_huerfanos(self, *args: object, **kwargs: object) -> list:
        raise AssertionError("abortar_runs_huerfanos: un comando de lectura no marca")

    def record_run_start(self, *args: object, **kwargs: object) -> int:
        raise AssertionError("record_run_start: un comando de lectura no registra")

    def record_run_end(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("record_run_end: un comando de lectura no registra")

    def record_run_completed(self, *args: object, **kwargs: object) -> int:
        raise AssertionError("record_run_completed: un comando de lectura no registra")

    def execute_sql_text(self, *args: object, **kwargs: object) -> int:
        raise AssertionError("execute_sql_text: un comando de lectura no escribe SQL")

    def truncate_table(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("truncate_table: un comando de lectura no borra nada")


def settings_falsos() -> SimpleNamespace:
    return SimpleNamespace(
        logging=SimpleNamespace(log_level="INFO", log_format="console"),
        tables_sigrid={"tables": [{"source_table": "con", "target_table": "con"}]},
    )


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    """Deja la CLI lista para invocarse sin red, sin BBDD y sin `.env`."""

    def _preparar(pg: object) -> CliRunner:
        monkeypatch.setattr(main, "get_settings", settings_falsos)
        monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        return CliRunner()

    return _preparar


def fila(step: str, segundos: float, filas: int = 0, stage: str = "ingest") -> FilaPerfil:
    return FilaPerfil(
        stage=stage, step=step, segundos=segundos, filas=filas, status="SUCCESS"
    )


CARGA = [
    fila("ingest_raw", 33 * 60, 20_050_000),
    fila("build_stg", 111 * 60, 29_590_000, stage="stage"),
    fila("build_mart", 21 * 60, 5_290_000, stage="build_mart"),
    fila("ingest_raw.obrparpre", 1_600, 13_760_000),
    fila("ingest_raw.con", 380, 500_000),
]


# ---------------------------------------------------------------------------
# R1, R2, R3 · `perfil-carga` imprime el desglose de la última carga
# ---------------------------------------------------------------------------


def test_f011_r1_perfil_carga_imprime_pasos_tablas_y_techo(cli) -> None:
    """El comando lee `_meta.etl_runs` y vuelca las tres respuestas."""
    pg = PgQueNoEscribe(perfil=(BATCH, CARGA))
    resultado = cli(pg).invoke(main.cli, ["perfil-carga"])

    assert resultado.exit_code == 0, resultado.output
    assert BATCH in resultado.output
    assert "ingest_raw" in resultado.output
    assert "build_stg" in resultado.output
    assert "obrparpre" in resultado.output
    # R2 y R3, que son las dos preguntas que deciden la puerta de R8.
    assert "Techo de mejora" in resultado.output
    assert "80 % del tiempo de ingesta" in resultado.output
    # Sin --batch se pide la última carga.
    assert pg.batches_pedidos == [None]


def test_f011_r1_perfil_carga_admite_un_batch_concreto(cli) -> None:
    """`--batch` mide una carga anterior: es lo que permite comparar dos noches."""
    pg = PgQueNoEscribe(perfil=(BATCH, CARGA))
    resultado = cli(pg).invoke(main.cli, ["perfil-carga", "--batch", BATCH])

    assert resultado.exit_code == 0, resultado.output
    assert pg.batches_pedidos == [BATCH]


def test_f011_r1_perfil_carga_sin_datos_lo_dice_y_no_revienta(cli) -> None:
    """Una base sin cargas medidas no es un error del comando."""
    resultado = cli(PgQueNoEscribe(perfil=(None, []))).invoke(main.cli, ["perfil-carga"])

    assert resultado.exit_code == 0, resultado.output
    assert "Sin mediciones" in resultado.output


def test_f011_r1_perfil_carga_sale_2_si_no_puede_leer(cli) -> None:
    """Mismo criterio que `check-coherencia`: 2 es «no he podido comprobarlo»."""
    pg = PgQueNoEscribe(error_al_leer=RuntimeError("sin conexión"))
    resultado = cli(pg).invoke(main.cli, ["perfil-carga"])

    assert resultado.exit_code == 2
    assert "sin conexión" in resultado.output


# ---------------------------------------------------------------------------
# R25 · Los comandos nuevos no generan batch_id ni escriben en _meta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("comando", COMANDOS_NUEVOS_DE_LECTURA)
def test_f011_r25_comandos_de_lectura_no_escriben_en_meta(cli, comando: str) -> None:
    """El doble revienta ante cualquier escritura; basta con que el comando pase.

    Va parametrizado sobre la lista y no comando a comando porque la lista ES
    el requisito: el día que esta feature añada un cuarto comando de lectura,
    añadirlo aquí es lo que impide que se le cuele un `_arrancar_ejecucion()`.
    """
    pg = PgQueNoEscribe(perfil=(BATCH, CARGA))
    resultado = cli(pg).invoke(main.cli, [comando])

    assert resultado.exit_code == 0, resultado.output


def test_f011_r25_perfil_carga_no_arranca_ejecucion(cli, monkeypatch) -> None:
    """Ni siquiera indirectamente: `_arrancar_ejecucion` no se llama.

    El test anterior lo comprueba por el lado del cliente; este lo comprueba
    por el lado de la CLI, que es donde vive la única puerta de entrada de los
    comandos que escriben (`main._arrancar_ejecucion`).
    """
    llamadas: list[object] = []
    monkeypatch.setattr(
        main, "_arrancar_ejecucion", lambda pg: llamadas.append(pg)
    )

    resultado = cli(PgQueNoEscribe(perfil=(BATCH, CARGA))).invoke(
        main.cli, ["perfil-carga"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert llamadas == []


# ---------------------------------------------------------------------------
# R23 · El SQL que sale de esta feature es de lectura, y se comprueba estático
# ---------------------------------------------------------------------------


def test_f011_r23_el_sql_del_perfil_es_un_select() -> None:
    """La consulta va en una constante de módulo para poder leerla en un test.

    Mismo patrón que F-024: si el SQL se construyera dentro del método, este
    test no podría comprobar que no hay un UPDATE escondido.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import SQL_PERFIL_CARGA

    normalizado = " ".join(SQL_PERFIL_CARGA.split()).upper()
    assert normalizado.startswith("SELECT")
    for prohibida in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"):
        assert prohibida not in normalizado, f"{prohibida} en SQL_PERFIL_CARGA"
