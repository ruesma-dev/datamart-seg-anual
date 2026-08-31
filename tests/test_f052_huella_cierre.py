# tests/test_f052_huella_cierre.py
"""
F-052 · La huella de CIERRE (huella 4, T29, R11).

`cierre` es **la capa que Negocio ve** en Power BI, y la que esta feature mueve
entera en la 0599: DIRECTOS pasa de 0,00 € a ~2,62 M € en sus 28 meses, y el
margen del 66,3 % al 1,8 %. Las huellas 1 y 2 miran `stg.plan_mensual` y
`mart.fact_seguimiento_categoria`, que están **aguas arriba**: entre ellas y
`cierre` hay una capa entera de reglas —`fn_mes_de_version_master`, el
telescopado, los filtros por `p.categoria` de `cierre/02_build_fact.sql`— que
ninguna de las dos ejerce. Un cambio que se colara ahí no lo vería ninguna.

Sin red ni BBDD: el cliente es un doble que sirve filas enlatadas.

**Nota de honestidad sobre la fase RED (rigor `critico`).** El mecanismo que
prueba este fichero —`FormatoHuella`, `comparar_ampliada`, `veredicto_ampliado`,
`construir_huella_ampliada` y los CSV— es el **mismo** que el de la huella 3, y
entró con ella tras su propia fase RED
(`tests/test_f052_huella_dimension.py`). Lo específico de aquí es el formato
`cierre` y su consulta, que viajaron en el mismo módulo compartido. Queda dicho
en `progress/impl_F-052.md`.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.huella_ampliada import (
    FORMATO_CIERRE,
    FilaAmpliada,
    comparar_ampliada,
    formato_de,
    veredicto_ampliado,
)
from etl_sigrid.infrastructure.postgres.cierres_sql import PALABRAS_DE_ESCRITURA
from etl_sigrid.infrastructure.postgres.huella_ampliada import (
    construir_huella_ampliada,
    escribir_csv_ampliada,
    leer_csv_ampliada,
    sql_huella_cierre,
)

#: Los cuatro conceptos base de `cierre.fact_cierre_mensual`. GASTOS y
#: BENEFICIO se derivan en la vista de resumen y no están en la tabla.
CONCEPTOS = ("VENTA", "DIRECTOS", "INDIRECTOS", "GENERALES")

#: Una fila tal y como la devuelve la consulta: la 0599 en diciembre de 2022,
#: con los DIRECTOS a cero que esta feature convierte en ~2,62 M EUR.
#: Los tipos son los que devuelve psycopg de verdad: `date` para `anio_mes` y
#: `Decimal` para las metricas. Con cadenas, el test no ejercitaria la
#: conversion a coma decimal ni la de fechas, que es donde puede perderse algo.
FILA_DIRECTOS = (
    1442383, "0599", date(2022, 12, 1), "DIRECTOS", 1,
    Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"),
)
FILA_VENTA = (
    1442383, "0599", date(2022, 12, 1), "VENTA", 1,
    Decimal("4066989.23"), Decimal("0.00"), Decimal("4066989.23"), Decimal("0.00"),
)


class PgFalso:
    def __init__(self, filas):
        self._filas = list(filas)
        self.consultas: list[str] = []
        self.timeouts: list[int] = []

    def filas_solo_lectura(self, sql_text: str, timeout_s: int) -> list[tuple]:
        self.consultas.append(sql_text)
        self.timeouts.append(timeout_s)
        return self._filas

    def __getattr__(self, nombre: str):
        raise AssertionError(f"la huella es de solo lectura y ha llamado a pg.{nombre}")


# ---------------------------------------------------------------------------
# La consulta
# ---------------------------------------------------------------------------


def test_f052_t29_el_grano_es_obra_mes_concepto():
    """El mismo grano que la clave de negocio de `cierre.fact_cierre_mensual`:
    agrupar por encima escondería justo el movimiento de esta feature, que es un
    concepto (DIRECTOS) que aparece donde no había nada."""
    sql = sql_huella_cierre()

    assert "FROM cierre.fact_cierre_mensual" in sql
    assert re.search(
        r"GROUP\s+BY\s+f\.obra_id,\s*f\.anio_mes,\s*f\.concepto", sql, re.I
    )


@pytest.mark.parametrize(
    "metrica",
    ("ejecutado_origen", "ejecutado_mes", "final_importe", "pendiente_importe"),
)
def test_f052_t29_la_huella_trae_las_cuatro_metricas_que_negocio_mira(metrica: str):
    assert metrica in sql_huella_cierre()
    assert metrica in FORMATO_CIERRE.cabecera


def test_f052_t29_un_nulo_no_puede_leerse_como_un_cero_silencioso():
    """`final_anterior` y `variacion_importe` admiten NULL en el DDL. Las cuatro
    métricas que sí se agregan van con `COALESCE` para que la huella no dependa
    de si una obra tiene el mes vacío."""
    assert sql_huella_cierre().upper().count("COALESCE") >= 5


def test_f052_t29_la_huella_de_cierre_no_escribe():
    texto = sql_huella_cierre().upper()

    for palabra in PALABRAS_DE_ESCRITURA:
        assert not re.search(rf"\b{palabra}\b", texto), f"la huella contiene {palabra}"
    assert "TEMP" not in texto


def test_f052_t29_la_huella_de_cierre_no_filtra_por_obra():
    """Se compara `cierre` ENTERO. Acotarla a las seis obras afectadas
    convertiría la prueba en una tautología."""
    assert "WHERE" not in sql_huella_cierre().upper()


# ---------------------------------------------------------------------------
# La lectura y el CSV
# ---------------------------------------------------------------------------


def test_f052_t29_se_lee_de_una_pasada_y_solo_lee():
    pg = PgFalso([FILA_VENTA, FILA_DIRECTOS])

    filas = construir_huella_ampliada(pg, FORMATO_CIERRE, timeout_s=200)

    assert len(pg.consultas) == 1
    assert pg.timeouts == [200]
    assert [f.clave for f in filas] == [
        ("1442383", "2022-12-01", "VENTA"),
        ("1442383", "2022-12-01", "DIRECTOS"),
    ]


def test_f052_t29_el_csv_va_y_vuelve_sin_perder_un_centimo(tmp_path):
    destino = tmp_path / "huella_cierre.csv"
    filas = construir_huella_ampliada(PgFalso([FILA_VENTA, FILA_DIRECTOS]), FORMATO_CIERRE)

    escribir_csv_ampliada(FORMATO_CIERRE, filas, destino)
    formato, leidas = leer_csv_ampliada(destino)

    assert formato is FORMATO_CIERRE
    assert leidas == filas
    assert "4066989,23" in destino.read_text(encoding="utf-8-sig"), (
        "coma decimal, convención de Ruesma para un CSV que se abre en Excel ES"
    )


def test_f052_t29_las_dos_huellas_ampliadas_no_se_confunden(tmp_path):
    """Comparar una huella de `cierre` contra una de dimensión daría un montón
    de diferencias falsas. Se reconocen por su cabecera y no por el nombre del
    fichero, que cualquiera puede teclear mal."""
    destino = tmp_path / "huella_cierre.csv"
    escribir_csv_ampliada(
        FORMATO_CIERRE,
        construir_huella_ampliada(PgFalso([FILA_VENTA]), FORMATO_CIERRE),
        destino,
    )

    assert formato_de(FORMATO_CIERRE.cabecera) is FORMATO_CIERRE
    assert leer_csv_ampliada(destino)[0] is FORMATO_CIERRE


# ---------------------------------------------------------------------------
# R11 · lo que esta huella caza y las otras no
# ---------------------------------------------------------------------------


def _fila(codigo_obra: str, concepto: str, importe: str) -> FilaAmpliada:
    return FilaAmpliada(
        codigo_obra=codigo_obra,
        clave=(codigo_obra, "2022-12-01", concepto),
        valores=(
            ("codigo_obra", codigo_obra),
            ("filas", "1"),
            ("ejecutado_origen", importe),
            ("ejecutado_mes", "0,00"),
            ("final_importe", importe),
            ("pendiente_importe", "0,00"),
        ),
    )


def test_f052_r11_los_directos_de_la_0599_apareciendo_se_ven():
    """El cambio previsto de esta feature, visto desde la capa que Negocio lee."""
    antes = (_fila("0599", "VENTA", "4066989,23"), _fila("0599", "DIRECTOS", "0,00"))
    despues = (
        _fila("0599", "VENTA", "4066989,23"),
        _fila("0599", "DIRECTOS", "2624793,46"),
    )

    comparacion = comparar_ampliada(FORMATO_CIERRE, antes, despues)
    codigo, informe = veredicto_ampliado(comparacion, ["0599"])

    assert codigo == 0, "la 0599 SÍ puede moverse: es una de las seis"
    assert "DIRECTOS" in informe
    assert "2624793,46" in informe


def test_f052_r11_una_obra_ajena_que_se_mueve_en_cierre_detiene_la_feature():
    """Es lo que el humano puso por delante de todo: que no se rompa lo que hoy
    funciona bien."""
    antes = (_fila("0599", "DIRECTOS", "0,00"), _fila("0664", "DIRECTOS", "100,00"))
    despues = (
        _fila("0599", "DIRECTOS", "2624793,46"),
        _fila("0664", "DIRECTOS", "100,01"),
    )

    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_CIERRE, antes, despues), ["0599"]
    )

    assert codigo != 0
    assert "0664" in informe
    assert "100,01" in informe, "un céntimo basta: no hay umbral"


def test_f052_r11_un_concepto_que_desaparece_de_un_mes_es_un_cambio():
    antes = (_fila("0664", "VENTA", "100,00"), _fila("0664", "DIRECTOS", "50,00"))
    despues = (_fila("0664", "VENTA", "100,00"),)

    codigo, informe = veredicto_ampliado(
        comparar_ampliada(FORMATO_CIERRE, antes, despues), ["0599"]
    )

    assert codigo != 0
    assert "DIRECTOS" in informe
    assert "sin fila" in informe
