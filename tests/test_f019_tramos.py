# tests/test_f019_tramos.py
"""
F-019 · Tests del planificador de tramos (dominio puro).

Cubren R3 (partición completa por obra), R4 (tramos acotados por peso
configurable + obra sobredimensionada) y R5 (plan determinista).

NINGÚN test de este fichero abre red ni BBDD: `planificar_tramos` es una
función pura del dominio y solo recibe un diccionario de pesos.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from config.settings import PostgresSettings
from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    MARCADOR_FILTRO_OBRAS,
    RAMAS_CON_FILTRO,
    BuildStgStep,
    PlanMensualAbortado,
    componer_sql_tramo,
)
from etl_sigrid.domain.entities import StepStatus
from etl_sigrid.domain.tramos import (
    Tramo,
    planificar_tramos,
    tramos_sobredimensionados,
)
from etl_sigrid.infrastructure.postgres.postgres_client import (
    BYTES_POR_GB,
    PostgresClient,
    porcentaje_ocupacion,
)

# Variables de entorno de la feature. Se limpian en los tests de settings para
# que el .env del puesto (que apunta a Azure) no decida el resultado.
VARIABLES_F019 = ("PG_TRAMO_MAX_FILAS", "PG_DISCO_TOTAL_GB", "PG_DISCO_LIMITE_PCT")

# El mismo fichero que ejecuta el step, resuelto por la misma constante: si el
# step cambiara de sitio el SQL, estos tests no seguirían mirando a otro lado.
RUTA_PLAN_MENSUAL = DIRECTORIO_SQL_STG / "08_plan_mensual.sql"

# Pesos de ejemplo: 10 obras con la asimetría típica (unas pocas pesan mucho).
PESOS: dict[int, int] = {
    101: 900_000,
    102: 420_000,
    103: 380_000,
    104: 250_000,
    105: 250_000,
    106: 120_000,
    107: 90_000,
    108: 40_000,
    109: 10_000,
    110: 0,
}

MAXIMO = 1_000_000


# --- R3 · Partición completa por obra ---------------------------------------


def test_f019_r3_plan_de_tramos_particiona_las_obras() -> None:
    """Cada obra en exactamente un tramo, ningún tramo vacío, unión = total."""
    tramos = planificar_tramos(PESOS, MAXIMO)

    todas: list[int] = []
    for tramo in tramos:
        assert tramo.obras, f"Tramo {tramo.indice} vacío"
        todas.extend(tramo.obras)

    assert sorted(todas) == sorted(PESOS)          # cobertura total
    assert len(todas) == len(set(todas))           # disjuntos
    assert [t.indice for t in tramos] == list(range(1, len(tramos) + 1))


def test_f019_r3_el_peso_de_cada_tramo_es_la_suma_de_sus_obras() -> None:
    for tramo in planificar_tramos(PESOS, MAXIMO):
        assert tramo.peso == sum(PESOS[obra] for obra in tramo.obras)


def test_f019_r3_sin_obras_no_hay_tramos() -> None:
    assert planificar_tramos({}, MAXIMO) == []


# --- R4 · Tramos acotados por peso configurable ------------------------------


def test_f019_r4_ningun_tramo_supera_el_maximo() -> None:
    for tramo in planificar_tramos(PESOS, MAXIMO):
        assert tramo.peso <= MAXIMO, f"Tramo {tramo.indice} pesa {tramo.peso}"


def test_f019_r4_un_maximo_pequeno_produce_mas_tramos_igual_de_acotados() -> None:
    """Bajar el máximo trocea más fino; lo único que puede pasarse es una obra
    que ya no cabe ni sola, y entonces va sola."""
    tramos = planificar_tramos(PESOS, 500_000)
    assert len(tramos) > len(planificar_tramos(PESOS, MAXIMO))

    sobredimensionados = tramos_sobredimensionados(tramos, 500_000)
    for tramo in tramos:
        if tramo in sobredimensionados:
            assert tramo.obras == (101,)  # la única obra que pesa más de 500 000
        else:
            assert tramo.peso <= 500_000


def test_f019_r4_un_tramo_que_da_justo_el_maximo_no_se_parte() -> None:
    """El límite es 'superar', no 'alcanzar': 60+40 con máximo 100 es UN tramo."""
    tramos = planificar_tramos({1: 60, 2: 40}, 100)
    assert tramos == [Tramo(indice=1, obras=(1, 2), peso=100)]
    assert tramos_sobredimensionados(tramos, 100) == []


def test_f019_r4_obra_gigante_va_en_tramo_unitario_con_warning() -> None:
    """Una obra sola por encima del máximo: tramo unitario, y se puede avisar."""
    pesos = {7: 2_500_000, 8: 100, 9: 200}
    tramos = planificar_tramos(pesos, MAXIMO)

    gigante = [t for t in tramos if 7 in t.obras]
    assert len(gigante) == 1
    assert gigante[0].obras == (7,), "la obra gigante arrastra compañía"
    assert gigante[0].peso == 2_500_000

    sobredimensionados = tramos_sobredimensionados(tramos, MAXIMO)
    assert sobredimensionados == gigante
    assert sobredimensionados[0].peso == 2_500_000  # el WARNING lo emite el step


def test_f019_r4_un_maximo_no_positivo_es_un_error_de_configuracion() -> None:
    with pytest.raises(ValueError, match="PG_TRAMO_MAX_FILAS"):
        planificar_tramos(PESOS, 0)


def test_f019_r4_un_maximo_de_una_sola_fila_sigue_siendo_valido() -> None:
    """Un máximo absurdamente pequeño es legítimo (trocea al extremo).

    Lo prohibido es el cero o el negativo, que dejarían el build sin tope.
    """
    assert planificar_tramos({4: 5, 5: 3}, 1) == [
        Tramo(indice=1, obras=(4,), peso=5),
        Tramo(indice=2, obras=(5,), peso=3),
    ]


def test_f019_r4_maximo_configurable_desde_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los tres parámetros de la feature son settings con default, no constantes.

    Importa porque las mediciones de T1 (que ejecuta el humano contra su
    PostgreSQL local) pueden obligar a mover los valores: deben moverse por
    variable de entorno, sin tocar código ni tests.
    """
    for variable in VARIABLES_F019:
        monkeypatch.delenv(variable, raising=False)

    por_defecto = PostgresSettings(_env_file=None)
    assert por_defecto.tramo_max_filas == 1_000_000
    assert por_defecto.disco_total_gb == 32
    assert por_defecto.disco_limite_pct == 80.0

    monkeypatch.setenv("PG_TRAMO_MAX_FILAS", "250000")
    monkeypatch.setenv("PG_DISCO_TOTAL_GB", "64")
    monkeypatch.setenv("PG_DISCO_LIMITE_PCT", "65.5")
    configurado = PostgresSettings(_env_file=None)
    assert configurado.tramo_max_filas == 250_000
    assert configurado.disco_total_gb == 64
    assert configurado.disco_limite_pct == 65.5


# --- R6 · El SQL filtra por obra en las DOS ramas ----------------------------
#
# Tests estáticos: leen el fichero .sql y no ejecutan SQL contra nada. No
# validan sintaxis (eso solo lo hace la BBDD, en R13/R14), pero convierten la
# regresión más probable —alguien edita el fichero y se lleva por delante un
# filtro— en rojo inmediato de la suite. Un tramo que filtrara solo una rama
# duplicaría las filas de la otra en CADA tramo.


def _sql_plan_mensual() -> str:
    return RUTA_PLAN_MENSUAL.read_text(encoding="utf-8")


def test_f019_r6_marcador_presente_en_ambas_ramas() -> None:
    sql = _sql_plan_mensual()
    inicio_master = sql.index("master_planif AS (")
    inicio_reales = sql.index("reales_base AS (")
    assert inicio_master < inicio_reales, "el fichero ya no tiene las dos ramas"

    rama_master = sql[inicio_master:inicio_reales]
    rama_reales = sql[inicio_reales:]
    assert MARCADOR_FILTRO_OBRAS in rama_master, "rama master sin filtro de tramo"
    assert MARCADOR_FILTRO_OBRAS in rama_reales, "rama reales sin filtro de tramo"
    assert sql.count(MARCADOR_FILTRO_OBRAS) == RAMAS_CON_FILTRO


def test_f019_r6_el_sql_ya_no_contiene_truncate() -> None:
    """El TRUNCATE lo ejecuta el step UNA vez, antes del primer tramo.

    Si volviera al fichero, cada tramo borraría lo que insertó el anterior y
    `stg.plan_mensual` acabaría con las obras del último tramo y nada más.
    """
    assert "TRUNCATE" not in _sql_plan_mensual().upper()


def test_f019_r6_la_logica_de_negocio_del_planif_sigue_intacta() -> None:
    """La interpretación del planif está validada al céntimo contra Sigrid.

    F-019 solo añade un filtro y quita un TRUNCATE; estas marcas de la lógica
    de negocio tienen que seguir ahí.
    """
    sql = _sql_plan_mensual()
    for marca in (
        "max_posterior",
        "ultimo_positivo",
        "grupo_positivo",
        "stg.fn_master_fecha_efectiva",
        "WHERE NOT (pct_acumulado = 0 AND pct_mes = 0)",
    ):
        assert marca in sql, f"desapareció del SQL: {marca}"


# --- R7 · Composición segura del filtro --------------------------------------


def test_f019_r7_solo_enteros_en_el_filtro() -> None:
    """El filtro se compone con enteros validados; nada más entra en el SQL."""
    plantilla = f"A {MARCADOR_FILTRO_OBRAS} B {MARCADOR_FILTRO_OBRAS} C"
    compuesto = componer_sql_tramo(plantilla, (10, 20, 30))

    assert compuesto == "A ARRAY[10, 20, 30]::BIGINT[] B ARRAY[10, 20, 30]::BIGINT[] C"
    assert MARCADOR_FILTRO_OBRAS not in compuesto

    for obras_invalidas in (
        ("101",),                    # un identificador que llega como texto
        (10, "20; DROP TABLE stg.plan_mensual"),
        (10, 20.0),                  # un float no es un obra_id
        (True,),                     # bool ES subclase de int: no cuela
        (10, None),
    ):
        with pytest.raises(TypeError, match="obra"):
            componer_sql_tramo(plantilla, obras_invalidas)


def test_f019_r7_sin_marcador_falla_antes_de_ejecutar() -> None:
    """Sin marcador NO se ejecuta el fichero: se ejecutaría sin filtro."""
    with pytest.raises(ValueError, match="F019_FILTRO_OBRAS"):
        componer_sql_tramo("SELECT 1", (10,))

    # Y con el marcador en una sola rama tampoco: sería duplicar la otra.
    with pytest.raises(ValueError, match="F019_FILTRO_OBRAS"):
        componer_sql_tramo(f"A {MARCADOR_FILTRO_OBRAS} B", (10,))


def test_f019_r7_un_tramo_sin_obras_no_compone_nada() -> None:
    plantilla = f"{MARCADOR_FILTRO_OBRAS} {MARCADOR_FILTRO_OBRAS}"
    with pytest.raises(ValueError, match="sin obras"):
        componer_sql_tramo(plantilla, ())


def test_f019_r7_el_sql_real_compuesto_queda_sin_marcadores() -> None:
    compuesto = componer_sql_tramo(_sql_plan_mensual(), (1234, 5678))
    assert MARCADOR_FILTRO_OBRAS not in compuesto
    assert compuesto.count("= ANY (ARRAY[1234, 5678]::BIGINT[])") == RAMAS_CON_FILTRO


# --- Dobles del cliente Postgres ---------------------------------------------
#
# Ningún test abre una conexión: se sustituye `PostgresClient.connection`, que
# es el único punto por el que el cliente llega a la BBDD.


class CursorFalso:
    """Cursor de mentira: guarda lo ejecutado y devuelve filas preparadas."""

    def __init__(self, filas: list[tuple] | None = None, rowcount: int | None = 0):
        self.filas = filas if filas is not None else []
        self.rowcount = rowcount
        self.ejecutado: list[str] = []

    def __enter__(self) -> CursorFalso:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> None:
        self.ejecutado.append(sql)

    def fetchone(self) -> tuple | None:
        return self.filas[0] if self.filas else None

    def fetchall(self) -> list[tuple]:
        return list(self.filas)


class ConexionFalsa:
    def __init__(self, cursor: CursorFalso) -> None:
        self._cursor = cursor

    def cursor(self) -> CursorFalso:
        return self._cursor


class ConexionesFalsas:
    """Reemplazo de `PostgresClient.connection` que cuenta aperturas."""

    def __init__(self, cursor: CursorFalso) -> None:
        self.cursor = cursor
        self.aperturas = 0

    @contextmanager
    def __call__(self) -> Iterator[ConexionFalsa]:
        self.aperturas += 1
        yield ConexionFalsa(self.cursor)


def cliente_con(cursor: CursorFalso) -> tuple[PostgresClient, ConexionesFalsas]:
    """Un PostgresClient cuyo `connection()` no toca ningún servidor."""
    cliente = PostgresClient(
        "host=servidor-inexistente dbname=ninguna",
        "host=servidor-inexistente dbname=ninguna",
        "sigrid_dm",
    )
    conexiones = ConexionesFalsas(cursor)
    cliente.connection = conexiones  # type: ignore[method-assign]
    return cliente, conexiones


# --- R8 · Medición de ocupación de disco -------------------------------------


def test_f019_r8_el_porcentaje_de_ocupacion_va_en_gigabytes_binarios() -> None:
    assert BYTES_POR_GB == 1_073_741_824
    assert porcentaje_ocupacion(17_179_869_184, 32) == 50.0   # 16 GiB de 32
    assert porcentaje_ocupacion(0, 32) == 0.0
    assert porcentaje_ocupacion(27_487_790_694, 32) == pytest.approx(80.0, abs=0.01)
    assert porcentaje_ocupacion(536_870_912, 1) == 50.0       # un disco de 1 GB


def test_f019_r8_un_disco_total_no_positivo_es_un_error_de_configuracion() -> None:
    with pytest.raises(ValueError, match="PG_DISCO_TOTAL_GB"):
        porcentaje_ocupacion(1, 0)


def test_f019_r8_medir_ocupacion_suma_todas_las_bases_del_servidor() -> None:
    """Todas las bases: el disco es compartido con albaranes y partes."""
    cursor = CursorFalso(filas=[(17_179_869_184,)])
    cliente, conexiones = cliente_con(cursor)

    assert cliente.medir_ocupacion_disco_pct(32) == 50.0
    assert conexiones.aperturas == 1
    assert "pg_database_size" in cursor.ejecutado[0]
    assert "FROM pg_database" in cursor.ejecutado[0]


def test_f019_r10_una_medicion_vacia_o_nula_no_se_toma_por_cero() -> None:
    """Sin dato NO se sigue: se propaga el fallo y la puerta aborta (R10)."""
    for filas in ([], [(None,)]):
        cliente, _ = cliente_con(CursorFalso(filas=filas))
        with pytest.raises(RuntimeError, match="ocupación"):
            cliente.medir_ocupacion_disco_pct(32)


# --- R4/R3 · Pesos por obra que alimentan al planificador --------------------


def test_f019_r3_los_pesos_por_obra_llegan_como_diccionario() -> None:
    cursor = CursorFalso(filas=[(101, 900_000), (102, 420_000)])
    cliente, conexiones = cliente_con(cursor)

    assert cliente.fetch_pesos_plan_mensual() == {101: 900_000, 102: 420_000}
    assert conexiones.aperturas == 1
    consulta = cursor.ejecutado[0]
    assert "raw.obrparpre" in consulta
    assert "stg.presupuesto" in consulta
    assert "GROUP BY" in consulta


# --- R11 · Una conexión (una transacción) por ejecución de tramo -------------


def test_f019_r11_execute_sql_text_abre_una_conexion_por_llamada() -> None:
    cursor = CursorFalso(rowcount=4321)
    cliente, conexiones = cliente_con(cursor)

    assert cliente.execute_sql_text("INSERT INTO stg.plan_mensual ...") == 4321
    assert cliente.execute_sql_text("INSERT INTO stg.plan_mensual ...") == 4321
    assert conexiones.aperturas == 2, "los tramos comparten transacción"


def test_f019_r11_un_recuento_no_disponible_cuenta_como_cero_filas() -> None:
    for rowcount in (None, -1, 0):
        cliente, _ = cliente_con(CursorFalso(rowcount=rowcount))
        assert cliente.execute_sql_text("INSERT ...") == 0


# --- Dobles para la orquestación del step -------------------------------------

# Tres obras y un máximo de 1 000: el plan sale en DOS tramos —(1,) de peso 600
# y (2, 3) de peso 900—, que es lo mínimo para poder observar «antes de cada
# tramo», «se para en el segundo» y «no se ejecutan los siguientes».
PESOS_CORTOS: dict[int, int] = {1: 600, 2: 500, 3: 400}
MAXIMO_CORTO = 1_000

# Tablas que declara el YAML falso de estos tests. Las usan a la vez
# `settings_falsos` (lo que la puerta de F-024 exige) y
# `PgFalso.fetch_estado_raw` (lo que dice haber): si dejaran de coincidir, la
# puerta de coherencia pararía el step antes de llegar a la de disco, que es lo
# que estos tests miden.
TABLAS_DEL_YAML_FALSO = ("con", "obr", "obrparpre")


class PgFalso:
    """Doble de `PostgresClient` que deja traza de TODO lo que le piden.

    No hereda de `PostgresClient` a propósito: si el step llamara a un método
    que este doble no implementa, el test debe fallar, no acabar en una
    conexión real.
    """

    def __init__(
        self,
        pesos: dict[int, int] | None = None,
        ocupaciones: list[float] | None = None,
        filas: list[int] | None = None,
        error_medicion: Exception | None = None,
        tramo_que_falla: int | None = None,
    ) -> None:
        self.pesos = dict(PESOS_CORTOS if pesos is None else pesos)
        self._ocupaciones = list([10.0, 10.0] if ocupaciones is None else ocupaciones)
        self._filas = list([700, 900] if filas is None else filas)
        self._error_medicion = error_medicion
        self._tramo_que_falla = tramo_que_falla

        self.traza: list[str] = []
        self.truncados: list[tuple[str, str]] = []
        self.sql_ejecutado: list[str] = []
        self.ficheros_ejecutados: list[str] = []
        self.pasos_registrados: list[str] = []
        self.cierres: list[tuple[int, str, int, str | None]] = []
        self.total_gb_medidos: list[int] = []
        self._ultimo_run = 0

    # --- lo que usa el build por tramos ---
    def fetch_pesos_plan_mensual(self) -> dict[int, int]:
        self.traza.append("pesos")
        return dict(self.pesos)

    def truncate_table(self, schema: str, table: str) -> None:
        self.traza.append("truncate")
        self.truncados.append((schema, table))

    def medir_ocupacion_disco_pct(self, total_gb: int) -> float:
        self.traza.append("medicion")
        self.total_gb_medidos.append(total_gb)
        if self._error_medicion is not None:
            raise self._error_medicion
        return self._ocupaciones.pop(0)

    def execute_sql_text(self, sql_text: str) -> int:
        self.traza.append("sql")
        self.sql_ejecutado.append(sql_text)
        if len(self.sql_ejecutado) == self._tramo_que_falla:
            raise RuntimeError("could not extend file: No space left on device")
        return self._filas.pop(0)

    # --- lo que usa el resto del step ---
    def record_run_start(
        self, stage: str, step: str, batch_id: str | None = None
    ) -> int:
        # `batch_id` llegó con F-024: el doble sigue la firma real del cliente.
        # Aquí no se comprueba (eso es de F-024), pero tiene que ADMITIRLO o el
        # doble dejaría de parecerse a lo que sustituye.
        self.pasos_registrados.append(step)
        self._ultimo_run += 1
        return self._ultimo_run

    def fetch_estado_raw(self) -> list:
        """Un `raw` coherente: F-024 puso una puerta al principio de `run()`.

        Estos tests son sobre la puerta de DISCO, así que la de coherencia
        tiene que dejarlos pasar. Se declaran las mismas tablas que
        `settings_falsos`, todas del mismo batch y en SUCCESS.
        """
        from etl_sigrid.domain.coherencia import EstadoTablaRaw

        return [
            EstadoTablaRaw(
                tabla=tabla,
                status="SUCCESS",
                batch_id="20260819T020000Z-f019f0",
                started_at=datetime(2026, 8, 19, 2, 0, 0),
                finished_at=datetime(2026, 8, 19, 2, 30, 0),
                filas=10,
            )
            for tabla in TABLAS_DEL_YAML_FALSO
        ]

    def record_run_end(
        self,
        run_id: int,
        status: str,
        rows_processed: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.cierres.append((run_id, status, rows_processed, error_message))

    def execute_sql_file(self, path: object, params: object = None) -> None:
        self.traza.append("fichero")
        self.ficheros_ejecutados.append(getattr(path, "name", str(path)))

    def count_rows(self, schema: str, table: str) -> int:
        return 0

    def assert_columns_exist(self, schema: str, table: str, columnas: list[str]) -> None:
        return None


class LoggerFalso:
    """Recoge los eventos estructurados sin escribir nada por consola."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict]] = []

    def _anotar(self, nivel: str, evento: str, **kwargs: object) -> None:
        self.eventos.append((nivel, evento, kwargs))

    def debug(self, evento: str, **kwargs: object) -> None:
        self._anotar("debug", evento, **kwargs)

    def info(self, evento: str, **kwargs: object) -> None:
        self._anotar("info", evento, **kwargs)

    def warning(self, evento: str, **kwargs: object) -> None:
        self._anotar("warning", evento, **kwargs)

    def error(self, evento: str, **kwargs: object) -> None:
        self._anotar("error", evento, **kwargs)

    def exception(self, evento: str, **kwargs: object) -> None:
        self._anotar("exception", evento, **kwargs)

    def de(self, evento: str) -> list[dict]:
        return [kwargs for _, nombre, kwargs in self.eventos if nombre == evento]


def settings_falsos(
    max_filas: int = MAXIMO_CORTO,
    total_gb: int = 32,
    limite_pct: float = 80.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        postgres=SimpleNamespace(
            tramo_max_filas=max_filas,
            disco_total_gb=total_gb,
            disco_limite_pct=limite_pct,
        ),
        business_rules={
            "sigrid": {"campos_extendidos": {"cod_version_master_vigente": "15"}}
        },
        # F-024: de aquí saca la puerta de coherencia qué tablas exigir. Las
        # mismas que devuelve `PgFalso.fetch_estado_raw`, para que la puerta
        # pase y estos tests sigan midiendo lo suyo: la puerta de disco.
        tables_sigrid={
            "tables": [{"source_table": t} for t in TABLAS_DEL_YAML_FALSO]
        },
    )


def construir_por_tramos(pg: PgFalso, **kwargs: object) -> int:
    paso = BuildStgStep(settings_falsos(**kwargs))  # type: ignore[arg-type]
    return paso._build_plan_mensual_por_tramos(pg, RUTA_PLAN_MENSUAL)


# --- R8 · Medición antes de CADA tramo ---------------------------------------


def test_f019_r8_mide_ocupacion_antes_de_cada_tramo() -> None:
    """Incluido el primero, y siempre ANTES de ejecutar el tramo."""
    pg = PgFalso()
    construir_por_tramos(pg)

    assert pg.traza == [
        "pesos",
        "truncate",      # una sola vez, antes del primer tramo
        "medicion", "sql",
        "medicion", "sql",
    ]
    assert pg.total_gb_medidos == [32, 32]
    assert pg.truncados == [("stg", "plan_mensual")]


# --- R9 · Límite de seguridad: aborto limpio ---------------------------------


def test_f019_r9_supera_limite_aborta_sin_ejecutar_el_tramo() -> None:
    pg = PgFalso(ocupaciones=[10.0, 92.5])

    with pytest.raises(PlanMensualAbortado) as fallo:
        construir_por_tramos(pg)

    mensaje = str(fallo.value)
    assert "92.5" in mensaje          # ocupación medida
    assert "80.0" in mensaje          # límite configurado
    assert "2/2" in mensaje           # tramo en el que paró

    # El segundo tramo NO se ejecutó y la tabla quedó vacía.
    assert pg.traza == [
        "pesos", "truncate", "medicion", "sql", "medicion", "truncate",
    ]
    assert len(pg.sql_ejecutado) == 1


def test_f019_r9_una_ocupacion_justo_en_el_limite_no_aborta() -> None:
    """El límite es superarlo, no alcanzarlo: 80,0 con límite 80 sigue."""
    pg = PgFalso(ocupaciones=[80.0, 80.0])
    construir_por_tramos(pg)
    assert len(pg.sql_ejecutado) == 2


def test_f019_r9_aborto_deja_la_tabla_vacia_y_failed_en_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El step entero: FAILED, tabla vacía y rastro en _meta.etl_runs."""
    import etl_sigrid.application.steps.build_stg_step as modulo

    pg = PgFalso(ocupaciones=[95.0])
    monkeypatch.setattr(modulo, "build_postgres_client", lambda _s: pg)

    resultado = BuildStgStep(settings_falsos()).run()  # type: ignore[arg-type]

    assert resultado.status is StepStatus.FAILED
    assert "build_plan_mensual" in (resultado.error_message or "")
    assert pg.sql_ejecutado == []                       # ni un tramo
    assert pg.truncados == [("stg", "plan_mensual")] * 2  # inicial + limpieza

    fallidos = [c for c in pg.cierres if c[1] == "FAILED"]
    assert [c[0] for c in fallidos]                     # hay FAILED en _meta
    assert any("95.0" in (c[3] or "") for c in fallidos)
    assert "build_stg.build_plan_mensual" in pg.pasos_registrados


# --- R10 · Fail-safe de la medición ------------------------------------------


def test_f019_r10_medicion_fallida_aborta_no_continua() -> None:
    """Si no se puede medir, no se sigue a ciegas: se aborta como en R9."""
    pg = PgFalso(error_medicion=RuntimeError("permission denied for pg_database"))

    with pytest.raises(PlanMensualAbortado, match="permission denied"):
        construir_por_tramos(pg)

    assert pg.sql_ejecutado == []
    assert pg.traza == ["pesos", "truncate", "medicion", "truncate"]


# --- R11 · Transacción por tramo y fallo limpio ------------------------------


def test_f019_r11_cada_tramo_en_su_transaccion() -> None:
    """Una ejecución por tramo, cada una con SUS obras y solo con las suyas."""
    pg = PgFalso()
    construir_por_tramos(pg)

    assert len(pg.sql_ejecutado) == 2
    assert pg.sql_ejecutado[0].count("= ANY (ARRAY[1]::BIGINT[])") == RAMAS_CON_FILTRO
    assert pg.sql_ejecutado[1].count("= ANY (ARRAY[2, 3]::BIGINT[])") == RAMAS_CON_FILTRO
    for sql in pg.sql_ejecutado:
        assert MARCADOR_FILTRO_OBRAS not in sql
        assert "TRUNCATE" not in sql.upper()


def test_f019_r11_fallo_de_tramo_limpia_y_para() -> None:
    pg = PgFalso(tramo_que_falla=1)

    with pytest.raises(PlanMensualAbortado, match="No space left on device"):
        construir_por_tramos(pg)

    assert len(pg.sql_ejecutado) == 1               # no hay tramos posteriores
    assert pg.traza[-1] == "truncate"               # tabla vacía
    assert ("stg", "plan_mensual") in pg.truncados
    assert any(estado == "FAILED" for _, estado, _, _ in pg.cierres)


# --- R12 · Observabilidad por tramo ------------------------------------------


def test_f019_r12_log_por_tramo_con_campos_obligatorios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import etl_sigrid.application.steps.build_stg_step as modulo

    registro = LoggerFalso()
    monkeypatch.setattr(modulo, "logger", registro)

    pg = PgFalso(filas=[700, 900])
    assert construir_por_tramos(pg) == 1_600        # suma de rowcounts reales

    tramos = registro.de("plan_mensual_tramo")
    assert len(tramos) == 2
    assert set(tramos[0]) == {
        "tramo", "obras", "peso", "filas", "duracion_s", "ocupacion_pct",
    }
    assert tramos[0]["tramo"] == "1/2"
    assert tramos[0]["obras"] == 1
    assert tramos[0]["peso"] == 600
    assert tramos[0]["filas"] == 700
    assert tramos[0]["ocupacion_pct"] == 10.0
    assert tramos[0]["duracion_s"] >= 0.0
    assert tramos[1]["tramo"] == "2/2"
    assert tramos[1]["obras"] == 2
    assert tramos[1]["peso"] == 900
    assert tramos[1]["filas"] == 900

    plan = registro.de("plan_mensual_plan_de_tramos")
    assert plan == [{"tramos": 2, "obras": 3, "peso_total": 1_500, "max_filas": 1_000}]


def test_f019_r12_registro_en_meta_por_tramo() -> None:
    """`python main.py timings` tiene que poder desglosar el coste por tramo."""
    pg = PgFalso()
    construir_por_tramos(pg)

    assert pg.pasos_registrados == [
        "build_stg.build_plan_mensual.tramo_01",
        "build_stg.build_plan_mensual.tramo_02",
    ]
    assert pg.cierres == [
        (1, "SUCCESS", 700, None),
        (2, "SUCCESS", 900, None),
    ]


def test_f019_r4_el_step_avisa_de_la_obra_sobredimensionada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La obra que no cabe ni sola no aborta el build: se avisa con su peso."""
    import etl_sigrid.application.steps.build_stg_step as modulo

    registro = LoggerFalso()
    monkeypatch.setattr(modulo, "logger", registro)

    pg = PgFalso(pesos={7: 5_000}, ocupaciones=[10.0], filas=[42])
    construir_por_tramos(pg)

    avisos = registro.de("plan_mensual_tramo_sobredimensionado")
    assert avisos == [
        {"tramo": 1, "obras": [7], "peso": 5_000, "max_filas": MAXIMO_CORTO}
    ]
    assert len(pg.sql_ejecutado) == 1     # avisa, pero construye


# --- R5 · Plan determinista --------------------------------------------------


def test_f019_r5_plan_determinista() -> None:
    """Mismos pesos y mismo máximo => mismo plan, sea cual sea el orden del dict."""
    al_reves = dict(reversed(list(PESOS.items())))
    assert al_reves != PESOS or list(al_reves) != list(PESOS)  # orden distinto

    esperado = planificar_tramos(PESOS, MAXIMO)
    assert planificar_tramos(al_reves, MAXIMO) == esperado
    assert planificar_tramos(dict(sorted(PESOS.items())), MAXIMO) == esperado


def test_f019_r5_un_tramo_es_un_valor_inmutable_y_cerrado() -> None:
    """El plan se calcula una vez y no se retoca: nadie puede reescribir un
    tramo a mitad del bucle ni colarle campos que el step no espera."""
    tramo = planificar_tramos({1: 10}, 100)[0]

    with pytest.raises(AttributeError):
        tramo.peso = 999          # type: ignore[misc]
    assert not hasattr(tramo, "__dict__")   # sin campos fuera de los declarados


def test_f019_r5_las_obras_se_empaquetan_de_mayor_a_menor_peso() -> None:
    """Orden estable declarado: peso descendente y, a igual peso, obra_id."""
    tramos = planificar_tramos({1: 100, 2: 300, 3: 300, 4: 200}, 10_000)
    assert tramos == [Tramo(indice=1, obras=(2, 3, 4, 1), peso=900)]
