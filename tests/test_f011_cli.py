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

#: Los comandos que esta feature añade, todos de solo lectura (R25). La lista
#: ES el requisito: añadir aquí el comando nuevo es lo que impide que se le
#: cuele un `_arrancar_ejecucion()` dentro de seis meses.
COMANDOS_NUEVOS_DE_LECTURA = (
    ("perfil-carga", []),
    ("bench-sigrid", ["--tabla", "con", "--paginas", "1000"]),
)


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
        tables_sigrid={
            "tables": [
                {
                    "source_table": "con",
                    "target_table": "con",
                    "exclude_columns": ["ima", "tex"],
                }
            ]
        },
        sigrid_api=SimpleNamespace(
            base_url="https://sigrid-api.example",
            # Nunca una credencial de verdad en un test, ni de desarrollo.
            function_key=SimpleNamespace(get_secret_value=lambda: "clave-de-mentira"),
            database="sigrid",
            page_size=10_000,
            timeout_s=230.0,
            max_retries=3,
        ),
    )


class ApiFalsaCli:
    """Doble de `SigridApiClient` para los tests del comando `bench-sigrid`."""

    #: Lo que la CLI le pidió, para poder afirmar sobre ello desde fuera.
    ultima: ApiFalsaCli | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.columnas_pedidas: list[str] = []
        self.sql_enviado: list[str] = []
        self.max_rows: list[int | None] = []
        ApiFalsaCli.ultima = self

    def __enter__(self) -> ApiFalsaCli:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def fetch_table_schema(self, source_table: str) -> list[SimpleNamespace]:
        self.columnas_pedidas.append(source_table)
        return [
            SimpleNamespace(name="ide"),
            SimpleNamespace(name="res"),
            SimpleNamespace(name="ima"),  # excluida en tables_sigrid.yaml
        ]

    def leer_sql(
        self,
        sql: str,
        parameters: list | None = None,
        max_rows: int | None = None,
    ) -> dict:
        self.sql_enviado.append(sql)
        self.max_rows.append(max_rows)
        filas = [[i + 1, "x"] for i in range(min(max_rows or 0, 10))]
        return {"columns": ["ide", "res"], "rows": filas, "row_count": len(filas)}


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):
    """Deja la CLI lista para invocarse sin red, sin BBDD y sin `.env`."""

    def _preparar(pg: object) -> CliRunner:
        monkeypatch.setattr(main, "get_settings", settings_falsos)
        monkeypatch.setattr(main, "configure_logging", lambda **kwargs: None)
        monkeypatch.setattr(main, "_get_pg", lambda: pg)
        monkeypatch.setattr(main, "SigridApiClient", ApiFalsaCli)
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


@pytest.mark.parametrize("comando,argumentos", COMANDOS_NUEVOS_DE_LECTURA)
def test_f011_r25_comandos_de_lectura_no_escriben_en_meta(
    cli, comando: str, argumentos: list[str]
) -> None:
    """El doble revienta ante cualquier escritura; basta con que el comando pase."""
    pg = PgQueNoEscribe(perfil=(BATCH, CARGA))
    resultado = cli(pg).invoke(main.cli, [comando, *argumentos])

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


def test_f011_r1_fetch_perfil_carga_traduce_las_filas_a_mediciones() -> None:
    """El mapeo fila→`FilaPerfil`, con la duración calculada aquí y no en SQL.

    Se sustituye `PostgresClient.connection`, que es el único punto por el que
    el cliente llega a la BBDD: el test no abre ninguna conexión. Lo que se
    comprueba es lo que rompería en silencio —el orden de las columnas y la
    resta de instantes— y que una fila sin cerrar cuenta 0 s en vez de reventar.
    """
    from datetime import datetime

    from tests.test_f019_tramos import CursorFalso, cliente_con

    cursor = CursorFalso(
        filas=[
            (
                "ingest",
                "ingest_raw",
                datetime(2026, 8, 19, 2, 0, 22),
                datetime(2026, 8, 19, 2, 35, 54),
                "SUCCESS",
                20_048_847,
                BATCH,
            ),
            (
                "ingest",
                "ingest_raw.obrparpre",
                datetime(2026, 8, 19, 2, 0, 30),
                None,  # sin cerrar: 0 s, no una excepción
                "RUNNING",
                None,
                BATCH,
            ),
        ]
    )
    cliente, _ = cliente_con(cursor)

    medido, filas = cliente.fetch_perfil_carga()

    assert medido == BATCH
    assert len(filas) == 2
    assert filas[0].segundos == pytest.approx(2_132.0)
    assert filas[0].filas == 20_048_847
    assert filas[0].status == "SUCCESS"
    assert filas[1].segundos == 0.0
    assert filas[1].filas == 0
    assert filas[1].tabla == "obrparpre"


def test_f011_r1_fetch_perfil_carga_respeta_el_batch_pedido() -> None:
    """Con `--batch`, el batch devuelto es el pedido aunque no haya filas."""
    from tests.test_f019_tramos import CursorFalso, cliente_con

    cliente, _ = cliente_con(CursorFalso(filas=[]))

    medido, filas = cliente.fetch_perfil_carga("20260818T102311Z-aaaaaa")

    assert medido == "20260818T102311Z-aaaaaa"
    assert filas == []


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


# ---------------------------------------------------------------------------
# R4, R5, R5-bis · `bench-sigrid` mide contra Sigrid sin tocar el datamart
# ---------------------------------------------------------------------------


def test_f011_r4_bench_sigrid_barre_los_tamanos_pedidos(cli) -> None:
    """Un `SELECT TOP n` por tamaño, con las columnas que usa la ingesta."""
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", "1000,5000"]
    )

    assert resultado.exit_code == 0, resultado.output
    api = ApiFalsaCli.ultima
    assert api is not None
    assert api.columnas_pedidas == ["con"]
    assert api.max_rows == [1_000, 5_000]
    # `ima` está en exclude_columns del YAML: la ingesta no la pide y el banco
    # tampoco, o estaría midiendo un blob que nunca viaja.
    assert all("[ima]" not in sql for sql in api.sql_enviado)
    assert all(sql.startswith("SELECT TOP ") for sql in api.sql_enviado)
    # R5-bis: el veredicto compara con el timeout configurado.
    assert "230" in resultado.output


def test_f011_r4_bench_sigrid_escribe_el_csv_pedido(cli, tmp_path) -> None:
    """`--out` deja las mediciones en disco; el CSV no se versiona (T7)."""
    salida = tmp_path / "bench.csv"
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli,
        ["bench-sigrid", "--tabla", "con", "--paginas", "1000", "--out", str(salida)],
    )

    assert resultado.exit_code == 0, resultado.output
    assert salida.exists()
    assert salida.read_text(encoding="utf-8-sig").splitlines()[0].startswith("page_size;")


def test_f011_r4_bench_sigrid_sin_tamanos_es_un_error_de_uso(cli) -> None:
    """`--paginas ,,` no mide nada: sale 2 en vez de fingir un barrido vacío."""
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", " , "]
    )

    assert resultado.exit_code == 2


def test_f011_r4_bench_sigrid_no_abre_conexion_con_postgres(cli, monkeypatch) -> None:
    """No es que no escriba: es que ni siquiera pide el cliente del datamart."""
    def _no(_pg=None):
        raise AssertionError("bench-sigrid no puede pedir el cliente de Postgres")

    monkeypatch.setattr(main, "_get_pg", _no)

    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", "1000"]
    )

    assert resultado.exit_code == 0, resultado.output


def test_f011_r5_bench_sigrid_avisa_de_la_divergencia_del_cap(cli, monkeypatch) -> None:
    """Si la API acredita un cap distinto del documentado, se dice (DA-6).

    Y se dice nombrando al dueño del documento: `azure-apps/sigrid_api.md` es
    de `sigrid-api` y este proyecto no lo edita (T8-bis).
    """
    from etl_sigrid.infrastructure.sigrid.sigrid_api_client import (
        SigridApiPageSizeTooLargeError,
    )

    class ApiQueRechaza(ApiFalsaCli):
        def leer_sql(self, sql, parameters=None, max_rows=None):  # type: ignore[override]
            raise SigridApiPageSizeTooLargeError(requested=max_rows or 0, cap=20_000)

    # El orden importa: la fixture `cli` también sustituye `SigridApiClient`,
    # así que este doble tiene que ponerse DESPUÉS de prepararla.
    runner = cli(PgQueNoEscribe())
    monkeypatch.setattr(main, "SigridApiClient", ApiQueRechaza)

    resultado = runner.invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", "50000"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "RECHAZADA" in resultado.output
    assert "20,000" in resultado.output
    assert "sigrid-api" in resultado.output


def test_f011_r24_ni_un_secreto_en_la_salida_del_bench(cli) -> None:
    """La clave de función no puede acabar impresa por consola (R24)."""
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", "1000"]
    )

    assert "clave-de-mentira" not in resultado.output
