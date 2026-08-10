# tests/test_f019_tramos.py
"""
F-019 · Tests del planificador de tramos (dominio puro).

Cubren R3 (partición completa por obra), R4 (tramos acotados por peso
configurable + obra sobredimensionada) y R5 (plan determinista).

NINGÚN test de este fichero abre red ni BBDD: `planificar_tramos` es una
función pura del dominio y solo recibe un diccionario de pesos.
"""

from __future__ import annotations

import pytest

from collections.abc import Iterator
from contextlib import contextmanager

from config.settings import PostgresSettings
from etl_sigrid.application.steps.build_stg_step import (
    DIRECTORIO_SQL_STG,
    MARCADOR_FILTRO_OBRAS,
    RAMAS_CON_FILTRO,
    componer_sql_tramo,
)
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


# --- R5 · Plan determinista --------------------------------------------------


def test_f019_r5_plan_determinista() -> None:
    """Mismos pesos y mismo máximo => mismo plan, sea cual sea el orden del dict."""
    al_reves = dict(reversed(list(PESOS.items())))
    assert al_reves != PESOS or list(al_reves) != list(PESOS)  # orden distinto

    esperado = planificar_tramos(PESOS, MAXIMO)
    assert planificar_tramos(al_reves, MAXIMO) == esperado
    assert planificar_tramos(dict(sorted(PESOS.items())), MAXIMO) == esperado


def test_f019_r5_las_obras_se_empaquetan_de_mayor_a_menor_peso() -> None:
    """Orden estable declarado: peso descendente y, a igual peso, obra_id."""
    tramos = planificar_tramos({1: 100, 2: 300, 3: 300, 4: 200}, 10_000)
    assert tramos == [Tramo(indice=1, obras=(2, 3, 4, 1), peso=900)]
