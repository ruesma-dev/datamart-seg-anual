# tests/test_f148_sesion_carga.py
"""
F-148 · Una conexión por tabla en la ingesta (R8-R14, R17).

Hasta F-148 `copy_rows` abría una conexión NUEVA por página: ~2.800 solo en
`obrparpre`, y bastaba con que una se colgara para matar la noche. Ahora la
tabla entera viaja por UNA sesión de carga, con COPY y COMMIT por página (el
contrato DA-8 no cambia: una página confirmada no se pierde), y si la conexión
se rompe a mitad se reconecta y se repite ESA página tras comprobar si llegó.

Sin red ni BBDD: la conexión es un doble que registra lo que se le pide y se
rompe cuando el test se lo manda.
"""

from __future__ import annotations

from types import SimpleNamespace

import psycopg
import pytest
from psycopg import errors as pg_errors

from etl_sigrid.application.steps import ingest_raw_step
from etl_sigrid.application.steps.ingest_raw_step import IngestRawStep
from etl_sigrid.domain.entities import ColumnSpec, StepStatus, TableSpec
from etl_sigrid.infrastructure.postgres import postgres_client, sesion_carga
from etl_sigrid.infrastructure.postgres.postgres_client import (
    SQL_FILAS_EN_RANGO,
    PostgresClient,
    linea_copy,
)
from etl_sigrid.infrastructure.postgres.sesion_carga import (
    REINTENTOS_PAGINA,
    MedidaPagina,
    PaginaAmbiguaError,
    SesionDeCarga,
)

# ---------------------------------------------------------------------------
# Dobles
# ---------------------------------------------------------------------------


def _roto(mensaje: str = "server closed the connection unexpectedly") -> psycopg.OperationalError:
    return psycopg.OperationalError(mensaje)


class Conexion:
    """Doble de `psycopg.Connection` para la sesión de carga.

    `romper_en` es una lista de momentos («copy» o «commit») en los que esta
    conexión se rompe; `error` sustituye al error de conexión por otro.
    """

    def __init__(
        self,
        registro: list,
        *,
        romper_en: tuple[str, ...] = (),
        recuento: int = 0,
        error: BaseException | None = None,
        cerrada_sin_rota: bool = False,
        tras_commits: int = 0,
    ) -> None:
        self.registro = registro
        self._romper_en = list(romper_en)
        self._recuento = recuento
        self._error = error
        self._cerrada_sin_rota = cerrada_sin_rota
        self._tras_commits = tras_commits
        self.commits = 0
        self.broken = False
        self.closed = False
        self.lineas: list[str] = []

    def _quizas_romper(self, momento: str) -> None:
        if self._error is not None and momento == "copy":
            raise self._error
        if self.commits < self._tras_commits:
            return
        if self._romper_en and self._romper_en[0] == momento:
            self._romper_en.pop(0)
            if self._cerrada_sin_rota:
                self.closed = True
            else:
                self.broken = True
            raise _roto()

    # --- cursor ---
    def cursor(self) -> Conexion:
        return self

    def __enter__(self) -> Conexion:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def copy(self, sentencia: object) -> Conexion:
        self.registro.append(("copy_sql", sentencia.as_string(None)))  # type: ignore[attr-defined]
        return self

    def write(self, linea: str) -> None:
        self._quizas_romper("copy")
        self.lineas.append(linea)
        self.registro.append(("linea", linea))

    def execute(self, sentencia: object, parametros: object = None) -> None:
        self.registro.append(("recuento", sentencia.as_string(None), parametros))  # type: ignore[attr-defined]

    def fetchone(self) -> tuple[int]:
        return (self._recuento,)

    # --- transacción ---
    def commit(self) -> None:
        self._quizas_romper("commit")
        self.commits += 1
        self.registro.append(("commit",))

    def rollback(self) -> None:
        self.registro.append(("rollback",))

    def close(self) -> None:
        self.closed = True
        self.registro.append(("close",))


class Abridor:
    """`abrir` de mentira: entrega las conexiones preparadas, en orden."""

    def __init__(self, *conexiones: Conexion) -> None:
        self._conexiones = list(conexiones)
        self.aperturas = 0

    def __call__(self) -> Conexion:
        self.aperturas += 1
        conexion = self._conexiones.pop(0)
        conexion.registro.append(("abrir", self.aperturas))
        return conexion


def _sesion(abrir: Abridor, *, tiemod: str | None = None) -> SesionDeCarga:
    return SesionDeCarga(
        abrir, "raw", "obrparpre", ["ide", "cod"], id_column="ide", tiemod_column=tiemod
    )


PAGINA_1 = [{"ide": 1, "cod": "a"}, {"ide": 2, "cod": "b"}]
PAGINA_2 = [{"ide": 7, "cod": "x"}, {"ide": 3, "cod": None}, {"ide": 5, "cod": "z"}]


class Reloj:
    def __init__(self, *instantes: float) -> None:
        self._instantes = list(instantes)

    def __call__(self) -> float:
        return self._instantes.pop(0)


class LoggerFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def info(self, evento: str, **campos: object) -> None:
        self.eventos.append((evento, campos))

    warning = info
    error = info

    def de(self, evento: str) -> list[dict]:
        return [c for e, c in self.eventos if e == evento]


# ---------------------------------------------------------------------------
# R8-R9 · una conexión para N páginas, COPY + COMMIT por página
# ---------------------------------------------------------------------------


def test_f148_r8_r9_una_conexion_para_todas_las_paginas() -> None:
    registro: list = []
    abrir = Abridor(Conexion(registro))
    sesion = _sesion(abrir)

    sesion.copiar_pagina(PAGINA_1)
    sesion.copiar_pagina(PAGINA_2)
    sesion.copiar_pagina(PAGINA_1[:1])

    assert abrir.aperturas == 1
    assert [r[0] for r in registro].count("commit") == 3
    assert [r[0] for r in registro].count("copy_sql") == 3


def test_f148_r8_cada_pagina_se_confirma_antes_de_la_siguiente() -> None:
    """El contrato DA-8: lo confirmado no se pierde si cae la página siguiente."""
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro)))

    sesion.copiar_pagina(PAGINA_1)
    sesion.copiar_pagina(PAGINA_2)

    tipos = [r[0] for r in registro if r[0] in ("linea", "commit")]
    assert tipos == ["linea", "linea", "commit", "linea", "linea", "linea", "commit"]


def test_f148_r8_el_copy_lleva_tabla_columnas_y_formato() -> None:
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro)))

    sesion.copiar_pagina(PAGINA_2)

    (copy_sql,) = [r[1] for r in registro if r[0] == "copy_sql"]
    assert copy_sql == (
        'COPY "raw"."obrparpre" ("ide", "cod") FROM STDIN WITH (FORMAT text, NULL \'\\N\')'
    )
    assert [r[1] for r in registro if r[0] == "linea"] == ["7\tx\n", "3\t\\N\n", "5\tz\n"]


def test_f148_r8_con_tiemod_anade_source_tiemod() -> None:
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro)), tiemod="tiemod")

    sesion.copiar_pagina([{"ide": 1, "cod": "a", "tiemod": 20261023}])

    (copy_sql,) = [r[1] for r in registro if r[0] == "copy_sql"]
    assert '("ide", "cod", "_source_tiemod")' in copy_sql
    assert [r[1] for r in registro if r[0] == "linea"] == ["1\ta\t20261023\n"]


def test_f148_r8_la_columna_id_es_obligatoria_entre_las_columnas() -> None:
    with pytest.raises(ValueError, match="ide"):
        SesionDeCarga(Abridor(), "raw", "t", ["cod"], id_column="ide")


def test_f148_r9_sin_paginas_no_se_abre_ninguna_conexion() -> None:
    abrir = Abridor()
    sesion = _sesion(abrir)

    sesion.cerrar()

    assert abrir.aperturas == 0


def test_f148_linea_copy_formatea_cada_tipo() -> None:
    """El formateo es compartido con `reemplazar_filas`: se fija aquí."""
    fila = {"n": None, "v": True, "f": False, "b": b"\x01\xff", "t": "a\\b\tc\nd\re", "i": 7}

    assert linea_copy(fila, ["n", "v", "f", "b", "t", "i", "falta"]) == (
        "\\N\tt\tf\t\\\\x01ff\ta\\\\b\\tc\\nd\\re\t7\t\\N\n"
    )


# ---------------------------------------------------------------------------
# R10-R11 · la conexión se rompe: reconectar, comprobar y repetir ESA página
# ---------------------------------------------------------------------------


def test_f148_r10_se_rompe_en_el_commit_reconecta_y_repite_la_pagina() -> None:
    registro: list = []
    primera = Conexion(registro, romper_en=("commit",))
    segunda = Conexion(registro, recuento=0)
    abrir = Abridor(primera, segunda)
    sesion = _sesion(abrir)

    medida = sesion.copiar_pagina(PAGINA_1)

    assert abrir.aperturas == 2
    assert primera.closed is True
    assert segunda.lineas == ["1\ta\n", "2\tb\n"]
    assert medida.reintentos == 1
    assert medida.filas == 2


def test_f148_r10_las_paginas_confirmadas_no_se_repiten() -> None:
    registro: list = []
    primera = Conexion(registro, romper_en=("copy",), tras_commits=1)
    segunda = Conexion(registro, recuento=0)
    abrir = Abridor(primera, segunda)
    sesion = _sesion(abrir)

    sesion.copiar_pagina(PAGINA_1)
    medida = sesion.copiar_pagina(PAGINA_2)

    assert abrir.aperturas == 2
    assert primera.lineas == ["1\ta\n", "2\tb\n"]
    assert segunda.lineas == ["7\tx\n", "3\t\\N\n", "5\tz\n"]
    assert medida.reintentos == 1


def test_f148_r10_tambien_si_la_conexion_queda_cerrada() -> None:
    registro: list = []
    primera = Conexion(registro, romper_en=("copy",), cerrada_sin_rota=True)
    segunda = Conexion(registro, recuento=0)
    sesion = _sesion(Abridor(primera, segunda))

    medida = sesion.copiar_pagina(PAGINA_1)

    assert medida.reintentos == 1
    assert segunda.lineas == ["1\ta\n", "2\tb\n"]


def test_f148_r10_hasta_tres_reintentos_y_la_cuarta_rotura_propaga() -> None:
    assert REINTENTOS_PAGINA == 3
    registro: list = []
    rotas = [Conexion(registro, romper_en=("copy",)) for _ in range(4)]
    abrir = Abridor(*rotas)

    with pytest.raises(psycopg.OperationalError):
        _sesion(abrir).copiar_pagina(PAGINA_1)

    assert abrir.aperturas == 4
    assert rotas[-1].closed is True


def test_f148_r10_tres_roturas_y_a_la_cuarta_va() -> None:
    registro: list = []
    conexiones = [Conexion(registro, romper_en=("copy",)) for _ in range(3)]
    sana = Conexion(registro, recuento=0)
    abrir = Abridor(*conexiones, sana)

    medida = _sesion(abrir).copiar_pagina(PAGINA_1)

    assert medida.reintentos == 3
    assert sana.lineas == ["1\ta\n", "2\tb\n"]


def test_f148_r11_cuenta_las_filas_del_rango_de_ids_de_la_pagina() -> None:
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro, romper_en=("copy",)), Conexion(registro)))

    sesion.copiar_pagina(PAGINA_2)

    (recuento,) = [r for r in registro if r[0] == "recuento"]
    assert recuento[1] == SQL_FILAS_EN_RANGO.format(schema='"raw"', table='"obrparpre"', id='"ide"')
    assert "count(*)" in recuento[1]
    assert recuento[2] == {"lo": 3, "hi": 7}


def test_f148_r11_la_pagina_ya_llego_no_se_copia_otra_vez() -> None:
    """El COMMIT llegó y se perdió el acuse: copiar otra vez duplicaría."""
    registro: list = []
    segunda = Conexion(registro, recuento=2)
    sesion = _sesion(Abridor(Conexion(registro, romper_en=("commit",)), segunda))

    medida = sesion.copiar_pagina(PAGINA_1)

    assert segunda.lineas == []
    assert medida == MedidaPagina(
        filas=2, copy_s=medida.copy_s, pg_connect_s=medida.pg_connect_s, reintentos=1
    )
    # Y no deja la transacción del recuento abierta mientras espera a sigrid-api.
    assert registro[-1] == ("commit",)


def test_f148_r11_un_recuento_que_no_cuadra_es_pagina_ambigua() -> None:
    registro: list = []
    segunda = Conexion(registro, recuento=1)
    sesion = _sesion(Abridor(Conexion(registro, romper_en=("commit",)), segunda))

    with pytest.raises(PaginaAmbiguaError, match="página ambigua") as exc:
        sesion.copiar_pagina(PAGINA_2)

    assert "3" in str(exc.value) and "7" in str(exc.value)
    assert "raw.obrparpre" in str(exc.value)
    assert segunda.lineas == []
    assert ("rollback",) in registro


def test_f148_r11_tras_comprobar_la_rotura_se_vuelve_a_comprobar() -> None:
    """Si se rompe también el COPY repetido, la siguiente vuelta cuenta otra vez."""
    registro: list = []
    abrir = Abridor(
        Conexion(registro, romper_en=("commit",)),
        Conexion(registro, recuento=0, romper_en=("commit",)),
        Conexion(registro, recuento=2),
    )

    medida = _sesion(abrir).copiar_pagina(PAGINA_1)

    assert medida.reintentos == 2
    assert len([r for r in registro if r[0] == "recuento"]) == 2


# ---------------------------------------------------------------------------
# R12 · un error que no es de conexión no se reintenta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(pg_errors.UniqueViolation("duplicate key"), id="clave-duplicada"),
        pytest.param(pg_errors.InsufficientPrivilege("permission denied"), id="permisos"),
        pytest.param(pg_errors.QueryCanceled("canceling statement"), id="operational-sana"),
        pytest.param(ValueError("dato raro"), id="datos"),
    ],
)
def test_f148_r12_error_que_no_es_de_conexion_no_se_reintenta(error: BaseException) -> None:
    registro: list = []
    conexion = Conexion(registro, error=error)
    abrir = Abridor(conexion)

    with pytest.raises(type(error)):
        _sesion(abrir).copiar_pagina(PAGINA_1)

    assert abrir.aperturas == 1
    assert ("rollback",) in registro
    assert conexion.closed is False


# ---------------------------------------------------------------------------
# R13 · la sesión se cierra al terminar la tabla, bien o mal
# ---------------------------------------------------------------------------


def _cliente_con(conexiones: list[Conexion]) -> PostgresClient:
    cliente = PostgresClient("dbname=x", "dbname=admin", "sigrid_dm")
    cola = list(conexiones)
    cliente._connect = lambda _c, autocommit=False: cola.pop(0)  # type: ignore[method-assign]
    return cliente


def test_f148_r13_la_sesion_se_cierra_al_terminar() -> None:
    registro: list = []
    conexion = Conexion(registro)

    with _cliente_con([conexion]).sesion_de_carga("raw", "t", ["ide"], id_column="ide") as sesion:
        sesion.copiar_pagina([{"ide": 1}])
        assert conexion.closed is False

    assert conexion.closed is True


def test_f148_r13_la_sesion_se_cierra_aunque_falle() -> None:
    registro: list = []
    conexion = Conexion(registro)
    gestor = _cliente_con([conexion]).sesion_de_carga(
        "raw", "t", ["ide", "tiemod"], id_column="ide", tiemod_column="tiemod"
    )

    with pytest.raises(RuntimeError, match="sigrid-api"), gestor as sesion:
        sesion.copiar_pagina([{"ide": 1, "tiemod": 5}])
        raise RuntimeError("sigrid-api se cae a mitad")

    assert conexion.closed is True
    assert conexion.lineas == ["1\t5\t5\n"]


def test_f148_r13_cerrar_dos_veces_no_falla() -> None:
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro)))
    sesion.copiar_pagina(PAGINA_1)

    sesion.cerrar()
    sesion.cerrar()

    assert registro.count(("close",)) == 1


# ---------------------------------------------------------------------------
# R14 · lo que mide cada página
# ---------------------------------------------------------------------------


def test_f148_r14_la_medida_separa_conexion_y_copia(monkeypatch: pytest.MonkeyPatch) -> None:
    # inicio, abrir (antes, después), fin
    monkeypatch.setattr(sesion_carga, "perf_counter", Reloj(10.0, 10.0, 11.23456, 13.0))
    sesion = _sesion(Abridor(Conexion([])))

    medida = sesion.copiar_pagina(PAGINA_1)

    assert medida == MedidaPagina(filas=2, copy_s=1.765, pg_connect_s=1.235, reintentos=0)


def test_f148_r14_sin_reconexion_pg_connect_es_cero(monkeypatch: pytest.MonkeyPatch) -> None:
    sesion = _sesion(Abridor(Conexion([])))
    sesion.copiar_pagina(PAGINA_1)
    monkeypatch.setattr(sesion_carga, "perf_counter", Reloj(20.0, 20.4567))

    medida = sesion.copiar_pagina(PAGINA_2)

    assert medida == MedidaPagina(filas=3, copy_s=0.457, pg_connect_s=0.0, reintentos=0)


def test_f148_r10_el_reintento_deja_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    registro_log = LoggerFalso()
    monkeypatch.setattr(sesion_carga, "logger", registro_log)
    registro: list = []
    sesion = _sesion(Abridor(Conexion(registro, romper_en=("copy",)), Conexion(registro)))

    sesion.copiar_pagina(PAGINA_1)

    (aviso,) = registro_log.de("ingest_pagina_reintento")
    assert aviso["table"] == "raw.obrparpre"
    assert aviso["reintento"] == 1
    assert "server closed" in aviso["error"]


# ---------------------------------------------------------------------------
# T5 · el paso de ingesta sobre la sesión (R8, R14, R17)
# ---------------------------------------------------------------------------


class SesionFalsa:
    def __init__(self, registro: list, medidas: list[MedidaPagina] | None = None) -> None:
        self.registro = registro
        self._medidas = list(medidas or [])
        self.paginas: list[list[dict]] = []

    def copiar_pagina(self, filas: list[dict]) -> MedidaPagina:
        self.paginas.append(list(filas))
        self.registro.append(("pagina", len(filas)))
        if self._medidas:
            return self._medidas.pop(0)
        return MedidaPagina(filas=len(filas), copy_s=0.0, pg_connect_s=0.0, reintentos=0)


class PgIngesta:
    """Doble del cliente para `_ingest_one_table` y `run`."""

    def __init__(self, medidas: list[MedidaPagina] | None = None) -> None:
        self.registro: list = []
        self.sesiones: list[dict] = []
        self.sesion = SesionFalsa(self.registro, medidas)
        self.cierres: list[tuple] = []
        self.conexiones_abiertas = 0

    def record_run_start(self, stage: str, step: str, batch_id: str | None = None) -> int:
        return 1

    def record_run_end(
        self, run_id: int, status: str, rows_processed: int = 0, error_message: str | None = None
    ) -> None:
        self.cierres.append((status, rows_processed, error_message))

    def ensure_raw_table(self, *a: object, **k: object) -> None:
        return None

    def truncate_table(self, *a: object) -> None:
        return None

    def get_max_id(self, *a: object) -> int:
        return 0

    def fetch_firma_origen(self) -> dict:
        return {}

    def registrar_firmas_actuales(self, firmas: dict) -> int:
        return 0

    def sesion_de_carga(
        self,
        schema: str,
        table: str,
        columns: list[str],
        *,
        id_column: str,
        tiemod_column: str | None = None,
    ):
        from contextlib import contextmanager

        @contextmanager
        def _gestor():
            self.sesiones.append(
                {
                    "schema": schema,
                    "table": table,
                    "columns": list(columns),
                    "id_column": id_column,
                    "tiemod_column": tiemod_column,
                }
            )
            self.registro.append(("abre",))
            try:
                yield self.sesion
            finally:
                self.registro.append(("cierra",))

        return _gestor()


def _columna(nombre: str) -> ColumnSpec:
    return ColumnSpec(
        name=nombre,
        sql_server_type="int",
        char_max_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )


class ApiPaginas:
    def __init__(
        self, paginas: list[list[dict]], columnas: tuple[str, ...] = ("ide", "cod")
    ) -> None:
        self._paginas = paginas
        self._columnas = columnas
        self.pedidas: list[dict] = []

    def fetch_table_schema(self, tabla: str) -> list[ColumnSpec]:
        return [_columna(c) for c in self._columnas]

    def stream_table(self, tabla: str, **kwargs: object):
        self.pedidas.append(kwargs)
        yield from self._paginas


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        sigrid_api=SimpleNamespace(
            page_size=10_000,
            base_url="http://x",
            database="ruesma",
            timeout_s=1.0,
            max_retries=1,
            function_key=SimpleNamespace(get_secret_value=lambda: "k"),
        ),
        tables_sigrid={"tables": [{"source_table": "con", "target_table": "con"}]},
    )


def test_f148_r8_el_paso_carga_la_tabla_por_una_sesion() -> None:
    pg = PgIngesta()
    api = ApiPaginas([PAGINA_1, PAGINA_2])
    paso = IngestRawStep(_settings(), batch_id="b")  # type: ignore[arg-type]

    filas = paso._ingest_one_table(
        TableSpec(source_table="con", target_table="con_raw", incremental_column="cod"), api, pg
    )

    assert filas == 5
    assert pg.sesiones == [
        {
            "schema": "raw",
            "table": "con_raw",
            "columns": ["ide", "cod"],
            "id_column": "ide",
            "tiemod_column": "cod",
        }
    ]
    assert pg.registro == [("abre",), ("pagina", 2), ("pagina", 3), ("cierra",)]
    assert pg.cierres == [("SUCCESS", 5, None)]


def test_f148_r8_sin_columna_tiemod_no_pide_source_tiemod() -> None:
    pg = PgIngesta()
    paso = IngestRawStep(_settings(), batch_id="b")  # type: ignore[arg-type]

    paso._ingest_one_table(
        TableSpec(source_table="con", target_table="con", incremental_column="tiemod"),
        ApiPaginas([PAGINA_1]),
        pg,
    )

    assert pg.sesiones[0]["tiemod_column"] is None


def test_f148_r8_una_pagina_vacia_se_salta_y_sigue() -> None:
    pg = PgIngesta()
    paso = IngestRawStep(_settings(), batch_id="b")  # type: ignore[arg-type]

    filas = paso._ingest_one_table(
        TableSpec(source_table="con", target_table="con"), ApiPaginas([[], PAGINA_1]), pg
    )

    assert filas == 2
    assert pg.sesion.paginas == [PAGINA_1]


def test_f148_r14_ingest_pagina_por_cada_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    registro_log = LoggerFalso()
    monkeypatch.setattr(ingest_raw_step, "logger", registro_log)
    # Por página: antes y después de pedir a sigrid-api. La tercera vuelta es el
    # final del iterador.
    monkeypatch.setattr(ingest_raw_step, "perf_counter", Reloj(0.0, 1.23456, 5.0, 5.5, 9.0, 9.0001))
    medidas = [
        MedidaPagina(filas=2, copy_s=0.25, pg_connect_s=0.75, reintentos=0),
        MedidaPagina(filas=3, copy_s=0.5, pg_connect_s=0.0, reintentos=2),
    ]
    pg = PgIngesta(medidas)
    paso = IngestRawStep(_settings(), batch_id="b")  # type: ignore[arg-type]

    paso._ingest_one_table(
        TableSpec(source_table="con", target_table="con"), ApiPaginas([PAGINA_1, PAGINA_2]), pg
    )

    assert registro_log.de("ingest_pagina") == [
        {
            "table": "con",
            "page": 1,
            "filas": 2,
            "http_s": 1.235,
            "pg_connect_s": 0.75,
            "copy_s": 0.25,
            "reintentos": 0,
        },
        {
            "table": "con",
            "page": 2,
            "filas": 3,
            "http_s": 0.5,
            "pg_connect_s": 0.0,
            "copy_s": 0.5,
            "reintentos": 2,
        },
    ]


def test_f148_r13_el_paso_cierra_la_sesion_aunque_falle_la_pagina() -> None:
    pg = PgIngesta()

    class SesionQueFalla(SesionFalsa):
        def copiar_pagina(self, filas: list[dict]) -> MedidaPagina:
            raise pg_errors.ConnectionTimeout("connection timeout expired")

    pg.sesion = SesionQueFalla(pg.registro)
    paso = IngestRawStep(_settings(), batch_id="b")  # type: ignore[arg-type]

    with pytest.raises(pg_errors.ConnectionTimeout):
        paso._ingest_one_table(
            TableSpec(source_table="con", target_table="con"), ApiPaginas([PAGINA_1]), pg
        )

    assert pg.registro[-1] == ("cierra",)
    assert pg.cierres[0][0] == "FAILED"


class ApiContexto(ApiPaginas):
    def __init__(self, *_a: object, **_k: object) -> None:
        super().__init__([PAGINA_1])

    def __enter__(self) -> ApiContexto:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def test_f148_r17_el_paso_anota_las_conexiones_abiertas(monkeypatch: pytest.MonkeyPatch) -> None:
    pg = PgIngesta()
    pg.conexiones_abiertas = 7
    monkeypatch.setattr(ingest_raw_step, "build_postgres_client", lambda _s: pg)
    monkeypatch.setattr(ingest_raw_step, "SigridApiClient", ApiContexto)

    resultado = IngestRawStep(_settings(), batch_id="b").run()  # type: ignore[arg-type]

    assert resultado.status is StepStatus.SUCCESS
    assert resultado.metadata["conexiones_abiertas"] == 7


def test_f148_r17_copy_rows_ya_no_existe() -> None:
    """Su único llamante pasó a la sesión: un `copy_rows` vivo volvería a abrir
    una conexión por página en cuanto alguien lo llamara."""
    assert not hasattr(postgres_client.PostgresClient, "copy_rows")
