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
    ("diagnostico-tiemod", []),
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

    def fetch_diagnostico_tiemod(self) -> list:
        if self._error_al_leer is not None:
            raise self._error_al_leer
        return []

    def fetch_filas_desde_tiemod(self, tabla: str, umbral: float) -> int:
        return 0

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
        # Páginas COMPLETAS: si devolviera menos filas que el tamaño pedido,
        # `medir_pagina` cortaría a la primera y las repeticiones no se
        # ejercitarían nunca.
        desde = int(parameters[0]) if parameters else 0
        filas = [[desde + i + 1, "x"] for i in range(max_rows or 0)]
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


# ---------------------------------------------------------------------------
# R6, R7 · `diagnostico-tiemod` fotografía y compara, sin escribir en _meta
# ---------------------------------------------------------------------------


def estado_tiemod(tabla: str, filas: int, maximo: float | None, nulos: int = 0):
    from etl_sigrid.domain.tiemod import EstadoTiemod

    return EstadoTiemod(
        tabla=tabla,
        filas=filas,
        nulos=nulos,
        minimo=None if maximo is None else 40_000.0,
        maximo=maximo,
        distintos=0 if maximo is None else 10,
    )


class PgConTiemod(PgQueNoEscribe):
    """Doble que además responde al diagnóstico de `tiemod`."""

    def __init__(self, estados: list, avanzadas: dict[str, int] | None = None) -> None:
        super().__init__()
        self._estados = estados
        self._avanzadas = avanzadas or {}
        self.umbrales_pedidos: list[tuple[str, float]] = []

    def fetch_diagnostico_tiemod(self) -> list:
        return list(self._estados)

    def fetch_filas_desde_tiemod(self, tabla: str, umbral: float) -> int:
        self.umbrales_pedidos.append((tabla, umbral))
        return self._avanzadas.get(tabla, 0)


def test_f011_r6_diagnostico_tiemod_fotografia_las_tablas(cli) -> None:
    """Sin `--comparar-con` imprime el estado por tabla y nada más."""
    pg = PgConTiemod([estado_tiemod("con", 2_172_969, 46_263.5)])
    resultado = cli(pg).invoke(main.cli, ["diagnostico-tiemod"])

    assert resultado.exit_code == 0, resultado.output
    assert "con" in resultado.output
    assert "2,172,969" in resultado.output
    # Sin fotografía anterior no se lanza ni una consulta de recuento.
    assert pg.umbrales_pedidos == []


def test_f011_r6_diagnostico_tiemod_escribe_la_huella(cli, tmp_path) -> None:
    """`--out` deja el CSV que después alimenta la comparación de R7."""
    salida = tmp_path / "huella_tiemod_1.csv"
    pg = PgConTiemod([estado_tiemod("con", 100, 46_263.5)])

    resultado = cli(pg).invoke(main.cli, ["diagnostico-tiemod", "--out", str(salida)])

    assert resultado.exit_code == 0, resultado.output
    assert salida.exists()
    assert salida.read_text(encoding="utf-8-sig").splitlines()[0].startswith("tabla;")


def test_f011_r7_diagnostico_tiemod_compara_dos_cargas(cli, tmp_path) -> None:
    """Con dos fotografías sale el veredicto por tabla, y el recuento real.

    El umbral de la consulta de recuento es el máximo de la foto ANTERIOR: es
    lo que convierte «cuántas filas cambiaron» en un número medible.
    """
    from etl_sigrid.domain.tiemod import escribir_csv_tiemod

    huella = tmp_path / "huella_tiemod_1.csv"
    escribir_csv_tiemod([estado_tiemod("con", 100, 46_263.5)], huella)

    pg = PgConTiemod([estado_tiemod("con", 118, 46_264.75)], avanzadas={"con": 18})
    resultado = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(huella)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "SIRVE" in resultado.output
    assert pg.umbrales_pedidos == [("con", 46_263.5)]


def test_f011_r7_diagnostico_tiemod_sin_evidencia_si_nada_cambio(cli, tmp_path) -> None:
    """Dos fotos iguales: `SIN EVIDENCIA`, que no es lo mismo que `NO SIRVE`."""
    from etl_sigrid.domain.tiemod import escribir_csv_tiemod

    huella = tmp_path / "huella.csv"
    escribir_csv_tiemod([estado_tiemod("con", 100, 46_263.5)], huella)

    pg = PgConTiemod([estado_tiemod("con", 100, 46_263.5)])
    resultado = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(huella)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "SIN EVIDENCIA" in resultado.output


def test_f011_r6_diagnostico_tiemod_sale_2_si_no_puede_leer(cli) -> None:
    class PgRoto(PgConTiemod):
        def fetch_diagnostico_tiemod(self):  # type: ignore[override]
            raise RuntimeError("sin conexión")

    resultado = cli(PgRoto([])).invoke(main.cli, ["diagnostico-tiemod"])

    assert resultado.exit_code == 2
    assert "sin conexión" in resultado.output


def test_f011_r25_diagnostico_tiemod_no_escribe_en_meta(cli) -> None:
    """Mismo doble que revienta ante cualquier escritura (R25)."""
    pg = PgConTiemod([estado_tiemod("con", 100, 46_263.5)])
    resultado = cli(pg).invoke(main.cli, ["diagnostico-tiemod"])

    assert resultado.exit_code == 0, resultado.output


def test_f011_r23_el_sql_del_diagnostico_es_de_lectura() -> None:
    """Las tres consultas de tiemod, leídas como texto: ni una escritura."""
    from etl_sigrid.infrastructure.postgres.postgres_client import (
        SQL_DIAGNOSTICO_TIEMOD,
        SQL_FILAS_DESDE_TIEMOD,
        SQL_TABLAS_CON_TIEMOD,
    )

    for consulta in (
        SQL_TABLAS_CON_TIEMOD,
        SQL_DIAGNOSTICO_TIEMOD,
        SQL_FILAS_DESDE_TIEMOD,
    ):
        normalizada = " ".join(consulta.split()).upper()
        assert normalizada.startswith("SELECT")
        for prohibida in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER"):
            assert prohibida not in normalizada


def test_f011_r6_el_diagnostico_interpola_la_tabla_como_identificador() -> None:
    """La tabla viaja por `sql.Identifier`, nunca concatenada.

    Los nombres vienen del catálogo de la propia base, así que el riesgo real
    es bajo; pero una plantilla con `%s` para un nombre de tabla es el error
    que después nadie revisa.
    """
    from etl_sigrid.infrastructure.postgres.postgres_client import (
        SQL_DIAGNOSTICO_TIEMOD,
        SQL_FILAS_DESDE_TIEMOD,
    )

    assert "{tabla}" in SQL_DIAGNOSTICO_TIEMOD and "{col}" in SQL_DIAGNOSTICO_TIEMOD
    assert "{tabla}" in SQL_FILAS_DESDE_TIEMOD
    assert "%(umbral)s" in SQL_FILAS_DESDE_TIEMOD


def test_f011_r6_fetch_diagnostico_tiemod_traduce_las_filas() -> None:
    """El mapeo desde el cursor, sin BBDD: catálogo y luego una agregación."""
    from etl_sigrid.domain.tiemod import EstadoTiemod
    from tests.test_f019_tramos import CursorFalso, cliente_con

    class CursorPorConsulta(CursorFalso):
        """Devuelve el catálogo la primera vez y la agregación después."""

        def __init__(self) -> None:
            super().__init__(filas=[])
            self.respuestas = [
                [("con",)],
                [(100, 4, 1.5, 46_264.0, 37)],
            ]

        def execute(self, sql: str, params: object = None) -> None:
            super().execute(str(sql), params)
            self.filas = self.respuestas.pop(0) if self.respuestas else []

    cliente, _ = cliente_con(CursorPorConsulta())

    assert cliente.fetch_diagnostico_tiemod() == [
        EstadoTiemod(
            tabla="con", filas=100, nulos=4, minimo=1.5, maximo=46_264.0, distintos=37
        )
    ]


def test_f011_r7_fetch_filas_desde_tiemod_devuelve_el_recuento() -> None:
    from tests.test_f019_tramos import CursorFalso, cliente_con

    cliente, _ = cliente_con(CursorFalso(filas=[(18,)]))

    assert cliente.fetch_filas_desde_tiemod("con", 46_263.5) == 18


# ---------------------------------------------------------------------------
# Bordes que la campaña de mutación dejó al descubierto
# ---------------------------------------------------------------------------


def test_f011_r6_fetch_diagnostico_tiemod_no_inventa_filas_en_una_tabla_vacia() -> None:
    """Una tabla vacía trae ceros y nulos, y así tienen que llegar.

    Es el caso que descalifica una columna (`toda_nula`) y el que peor sienta
    que llegue redondeado: un 1 donde hay un 0 convierte «no hay nada» en «hay
    algo».
    """
    from etl_sigrid.domain.tiemod import EstadoTiemod
    from tests.test_f019_tramos import CursorFalso, cliente_con

    class CursorPorConsulta(CursorFalso):
        def __init__(self) -> None:
            super().__init__(filas=[])
            self.respuestas = [[("vacia",)], [(0, 0, None, None, 0)]]

        def execute(self, sql: str, params: object = None) -> None:
            super().execute(str(sql), params)
            self.filas = self.respuestas.pop(0) if self.respuestas else []

    cliente, _ = cliente_con(CursorPorConsulta())

    assert cliente.fetch_diagnostico_tiemod() == [
        EstadoTiemod(
            tabla="vacia", filas=0, nulos=0, minimo=None, maximo=None, distintos=0
        )
    ]


def test_f011_r7_fetch_filas_desde_tiemod_sin_respuesta_es_cero() -> None:
    """Si el cursor no devuelve fila, el recuento es 0, no 1.

    Un 1 inventado aquí convertiría un `NO SIRVE` en un `SIRVE`: el veredicto
    de R7 se apoya justo en este número.
    """
    from tests.test_f019_tramos import CursorFalso, cliente_con

    cliente, _ = cliente_con(CursorFalso(filas=[]))

    assert cliente.fetch_filas_desde_tiemod("con", 46_263.5) == 0


def test_f011_r25_el_cap_documentado_es_el_del_documento_del_ecosistema() -> None:
    """1.000 es lo que dice `azure-apps/sigrid_api.md`, y por eso diverge (DA-6)."""
    assert main.CAP_DOCUMENTADO_SIGRID_API == 1_000


@pytest.mark.parametrize(
    "argumentos",
    [
        ["perfil-carga"],
        ["diagnostico-tiemod"],
        ["bench-sigrid", "--tabla", "con", "--paginas", " , "],
    ],
)
def test_f011_los_errores_van_a_stderr(cli, argumentos: list[str]) -> None:
    """Los mensajes de error salen por stderr, no mezclados con el informe.

    Importa de verdad: estos comandos se redirigen a un fichero para adjuntar
    la medición, y un error escrito en stdout acabaría dentro del informe como
    si fuera un resultado.
    """
    pg = PgQueNoEscribe(error_al_leer=RuntimeError("sin conexión"))
    resultado = cli(pg).invoke(main.cli, argumentos)

    assert resultado.exit_code == 2
    assert "✗" in resultado.stderr
    assert "✗" not in resultado.stdout


def test_f011_r6_diagnostico_tiemod_rechaza_un_directorio_como_salida(cli, tmp_path) -> None:
    """`--out` es un fichero. Un directorio es un error de uso, no un aviso."""
    pg = PgConTiemod([estado_tiemod("con", 100, 46_263.5)])

    resultado = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--out", str(tmp_path)]
    )

    assert resultado.exit_code == 2


def test_f011_r4_bench_sigrid_rechaza_un_directorio_como_salida(cli, tmp_path) -> None:
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli,
        ["bench-sigrid", "--tabla", "con", "--paginas", "1000", "--out", str(tmp_path)],
    )

    assert resultado.exit_code == 2


def test_f011_r7_comparar_con_exige_un_fichero_que_exista(cli, tmp_path) -> None:
    """La huella anterior tiene que existir: si no, no hay nada que comparar.

    Sin esta guardia, un nombre mal escrito daría una comparación vacía con
    aspecto de resultado.
    """
    pg = PgConTiemod([estado_tiemod("con", 100, 46_263.5)])

    inexistente = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(tmp_path / "no_existe.csv")]
    )
    directorio = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(tmp_path)]
    )

    # Los dos salen 2, pero tiene que rechazarlos CLICK al validar la opción,
    # no el `open` de más adelante: el mensaje de uso dice qué opción está mal
    # y el del `open` solo dice que un fichero no se pudo abrir.
    assert inexistente.exit_code == 2
    assert "Invalid value for '--comparar-con'" in inexistente.stderr
    assert directorio.exit_code == 2
    assert "Invalid value for '--comparar-con'" in directorio.stderr


def test_f011_r7_una_tabla_nueva_no_rompe_la_comparacion(cli, tmp_path) -> None:
    """La foto anterior no tiene `dca` y la de ahora sí: no se consulta su umbral.

    Es el caso de una tabla añadida al YAML entre dos cargas. Preguntar por su
    máximo anterior reventaría con un KeyError.
    """
    from etl_sigrid.domain.tiemod import escribir_csv_tiemod

    huella = tmp_path / "huella.csv"
    escribir_csv_tiemod([estado_tiemod("con", 100, 46_263.5)], huella)

    pg = PgConTiemod(
        [estado_tiemod("con", 100, 46_263.5), estado_tiemod("dca", 7, 46_264.75)],
        avanzadas={"con": 0},
    )
    resultado = cli(pg).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(huella)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert [t for t, _ in pg.umbrales_pedidos] == ["con"]
    assert "dca" in resultado.output


def test_f011_r4_bench_sigrid_exige_tabla(cli) -> None:
    """Sin `--tabla` no hay nada que medir: error de uso, no un barrido vacío."""
    resultado = cli(PgQueNoEscribe()).invoke(main.cli, ["bench-sigrid"])

    assert resultado.exit_code == 2


def test_f011_r4_bench_sigrid_ensena_sus_valores_por_defecto(cli) -> None:
    """`--help` tiene que decir qué barre si no le dices nada.

    El 20.000 del barrido por defecto es el cap real de DA-6: si no sale en la
    ayuda, nadie sabe que se está midiendo justo en el límite de la API.
    """
    resultado = cli(PgQueNoEscribe()).invoke(main.cli, ["bench-sigrid", "--help"])

    assert resultado.exit_code == 0
    ayuda = " ".join(resultado.output.split())
    assert "1000,5000,10000,20000" in ayuda
    # Cada opción con valor por defecto tiene que enseñarlo, `--repeticiones`
    # incluida: es la que multiplica el número de peticiones contra producción.
    assert "[default: 1000,5000,10000,20000]" in ayuda
    assert "[default: 1]" in ayuda


def test_f011_r4_bench_sigrid_mide_una_pagina_por_tamano_si_no_se_pide_mas(cli) -> None:
    """El `--repeticiones` por defecto es 1: medir no puede costar el doble."""
    resultado = cli(PgQueNoEscribe()).invoke(
        main.cli, ["bench-sigrid", "--tabla", "con", "--paginas", "1000,5000"]
    )

    assert resultado.exit_code == 0, resultado.output
    api = ApiFalsaCli.ultima
    assert api is not None
    assert len(api.sql_enviado) == 2, "una petición por tamaño, ni una más"


def test_f011_r7_un_csv_que_no_es_una_huella_se_distingue_de_un_fallo_de_bbdd(
    cli, tmp_path
) -> None:
    """Pasar el CSV del bench a `--comparar-con` tiene su propio mensaje.

    Los dos salen 2, pero «este fichero no es una huella» y «no pude leer el
    datamart» mandan a mirar sitios distintos. Y la fotografía anterior se lee
    ANTES de tocar la BBDD: no tiene sentido recorrer 20 M de filas para
    después descubrir que el fichero de comparación no valía.
    """
    otro = tmp_path / "bench.csv"
    otro.write_text("page_size;peticiones;filas\n1000;1;1000\n", encoding="utf-8-sig")

    class PgQueNoDeberiaLeer(PgConTiemod):
        def fetch_diagnostico_tiemod(self):  # type: ignore[override]
            raise AssertionError("no se puede leer raw antes de validar la huella")

    resultado = cli(PgQueNoDeberiaLeer([])).invoke(
        main.cli, ["diagnostico-tiemod", "--comparar-con", str(otro)]
    )

    assert resultado.exit_code == 2
    assert "no parece una huella" in resultado.stderr
