# tests/test_f161_dominio.py
"""
F-161 · El oráculo del catálogo de versiones master (R3, R7, R10, R14).

`etl_sigrid/domain/master_versiones.py` repite en Python puro tres reglas que
el SQL aplica en `stg/10_master_versiones.sql` y `mart/01b_master_versiones.sql`:

- `tipo_master`: la cascada del tipo por el texto del jefe de obra (la de
  `mart/02_build_fact.sql` hasta F-161, copiada literal).
- `clasificar_reparto`: NINGUNO, COMPLETO o PARCIAL (R3, D7).
- `version_vigente`: la del ÚLTIMO CIERRE (D8, `temporal=False`) y la TEMPORAL
  que elige `02_build_fact.sql` (R10, `temporal=True`).

Los casos de la 0698 son los medidos por el spec-author (design §5.4), en
pequeño. Sin red ni BBDD: la sandbox compara este oráculo con el SQL.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.master_versiones import (
    TIPOS_TEMPORALES,
    VersionMaster,
    clasificar_reparto,
    tipo_master,
    version_vigente,
)

D = Decimal

# --- tipo_master: la cascada (R7) -------------------------------------------

#: Los textos que documenta la cabecera de `02_build_fact.sql`, con su tipo.
TEXTOS_DE_LA_CABECERA = [
    ("CIERRE INICIAL_ESTUDIO", "Cierre mensual"),
    ("CIERRE INICIAL_OBRA", "Cierre mensual"),
    ("PLANIFICACION VALORADA INICIAL", "Planif Inicial"),
    ("PLANIFICACION VALORADA OCT-25", "Cuatrimestral"),
    ("CIERRE DICIEMBRE-25/ ABC", "ABC"),
    ("CIERRE ENERO-26", "Cierre mensual"),
    ("PLANIFICACION CUATRIMESTRAL FEB-26", "Cuatrimestral"),
    ("CIERRE SEPTIEMBRE-26", "Cierre mensual"),
]


@pytest.mark.parametrize(("texto", "tipo"), TEXTOS_DE_LA_CABECERA)
def test_f161_r7_la_cascada_con_los_textos_de_la_cabecera(texto: str, tipo: str) -> None:
    assert tipo_master(texto) == tipo


@pytest.mark.parametrize("texto", [None, "", "   "])
def test_f161_r7_sin_texto_es_sin_clasificar(texto: str | None) -> None:
    assert tipo_master(texto) == "Sin clasificar"


def test_f161_r7_la_prioridad_es_estricta() -> None:
    """ABC gana a todo; INICIAL+VALORADA gana a VALORADA a secas."""
    assert tipo_master("abc valorada inicial cuatrim cierre") == "ABC"
    assert tipo_master("valorada inicial cierre") == "Planif Inicial"
    assert tipo_master("cuatrim cierre") == "Cuatrimestral"
    assert tipo_master("OTRA COSA") == "Sin clasificar"


def test_f161_r10_los_tres_tipos_que_rigen_el_mensual() -> None:
    assert TIPOS_TEMPORALES == ("Planif Inicial", "ABC", "Cuatrimestral")


# --- clasificar_reparto (R3, D7) --------------------------------------------


def test_f161_r3_v24_de_la_0698_sin_reparto_es_ninguno() -> None:
    """La v24 de coste: 776 líneas, ninguna deja filas en `plan_mensual`."""
    lineas = [(D("2107662.97"), False)]
    assert clasificar_reparto(lineas, tiene_reparto=False) == "NINGUNO"


def test_f161_r3_v20_de_la_0698_lineas_sin_reparto_a_cero_es_completo() -> None:
    """La v20: sus 95 líneas sin reparto están a 0 €, así que es COMPLETO."""
    lineas = [(D("2165726.69"), True), (D("0"), False), (D("0.00"), False)]
    assert clasificar_reparto(lineas, tiene_reparto=True) == "COMPLETO"


def test_f161_r3_v23_de_la_0698_lineas_sin_reparto_con_importe_es_parcial() -> None:
    """La v23: 61 líneas con `planif` que no dejan ningún mes (56.059,64 €)."""
    lineas = [(D("2055968.14"), True), (D("56059.64"), False)]
    assert clasificar_reparto(lineas, tiene_reparto=True) == "PARCIAL"


def test_f161_r3_una_linea_negativa_sin_reparto_tambien_es_parcial() -> None:
    assert clasificar_reparto([(D("10"), True), (D("-1"), False)], tiene_reparto=True) == "PARCIAL"


def test_f161_r3_con_reparto_y_sin_lineas_es_completo() -> None:
    assert clasificar_reparto([], tiene_reparto=True) == "COMPLETO"


def test_f161_r3_sin_reparto_y_sin_lineas_es_ninguno() -> None:
    assert clasificar_reparto([], tiene_reparto=False) == "NINGUNO"


def test_f161_r3_importe_nulo_no_cuenta_como_importe() -> None:
    """En SQL `NULL <> 0` es NULL y `BOOL_OR` lo ignora."""
    assert clasificar_reparto([(D("5"), True), (None, False)], tiene_reparto=True) == "COMPLETO"


# --- version_vigente (D8 y R10) ---------------------------------------------


def _v(
    version: int,
    efectiva: date | None,
    tipo: str = "Cuatrimestral",
    *,
    n_lineas: int = 10,
    reparto: bool = True,
    importe: str = "100",
    creacion: date | None = date(2020, 1, 1),
) -> VersionMaster:
    return VersionMaster(
        version=version,
        fec_efectiva=efectiva,
        tipo=tipo,
        n_lineas=n_lineas,
        tiene_reparto=reparto,
        importe_total=D(importe),
        fec_creacion=creacion,
    )


def _numero(v: VersionMaster | None) -> int | None:
    return v.version if v else None


#: La 0698 de coste en pequeño: v20 Cuatrimestral con reparto, v23 cierre con
#: reparto, v24 cierre SIN reparto (design §5.3).
V0698 = [
    _v(20, date(2026, 6, 10), "Cuatrimestral"),
    _v(23, date(2026, 9, 5), "Cierre mensual"),
    _v(24, date(2026, 10, 3), "Cierre mensual", reparto=False),
]


def test_f161_r14_el_ultimo_cierre_es_la_ultima_de_cualquier_tipo() -> None:
    assert _numero(version_vigente(V0698, date(2026, 11, 1), temporal=False)) == 24
    assert _numero(version_vigente(V0698, date(2026, 9, 1), temporal=False)) == 23


def test_f161_r10_la_temporal_es_la_de_hoy() -> None:
    """Sin reparto o 'Cierre mensual': no rige el mensual (D4)."""
    assert _numero(version_vigente(V0698, date(2026, 11, 1), temporal=True)) == 20


def test_f161_r10_sin_reparto_no_rige_aunque_sea_cuatrimestral() -> None:
    versiones = [_v(1, date(2026, 2, 1)), _v(2, date(2026, 3, 1), reparto=False)]
    assert _numero(version_vigente(versiones, date(2026, 4, 1), temporal=True)) == 1
    assert _numero(version_vigente(versiones, date(2026, 4, 1), temporal=False)) == 2


def test_f161_r10_sin_fecha_de_creacion_no_rige() -> None:
    """El filtro de `02`: `version_fec_creacion IS NOT NULL`."""
    versiones = [_v(1, date(2026, 2, 1)), _v(2, date(2026, 3, 1), creacion=None)]
    assert _numero(version_vigente(versiones, date(2026, 4, 1), temporal=True)) == 1


def test_f161_r14_el_mes_incluye_la_fecha_efectiva_de_ese_mes() -> None:
    """`version_fec_efectiva < anio_mes + 1 mes`: rige desde su propio mes."""
    versiones = [_v(1, date(2026, 2, 1)), _v(2, date(2026, 3, 31))]
    assert _numero(version_vigente(versiones, date(2026, 3, 1), temporal=False)) == 2
    assert _numero(version_vigente(versiones, date(2026, 2, 1), temporal=False)) == 1
    assert version_vigente(versiones, date(2026, 1, 1), temporal=False) is None


def test_f161_r14_el_mes_de_diciembre_pasa_de_ano() -> None:
    versiones = [_v(1, date(2026, 12, 31))]
    assert _numero(version_vigente(versiones, date(2026, 12, 1), temporal=False)) == 1


def test_f161_r14_empate_de_fecha_gana_la_mayor_version() -> None:
    versiones = [_v(3, date(2026, 2, 1)), _v(5, date(2026, 2, 1)), _v(4, date(2026, 2, 1))]
    assert _numero(version_vigente(versiones, date(2026, 2, 1), temporal=False)) == 5
    assert _numero(version_vigente(versiones, date(2026, 2, 1), temporal=True)) == 5


def test_f161_r14_fecha_nula_fuera_en_los_dos_modos() -> None:
    versiones = [_v(1, date(2026, 2, 1)), _v(9, None)]
    assert _numero(version_vigente(versiones, date(2026, 5, 1), temporal=False)) == 1
    assert _numero(version_vigente(versiones, date(2026, 5, 1), temporal=True)) == 1


def test_f161_r14_la_version_0_fuera_del_ultimo_cierre() -> None:
    """D8: versiones >= 1. La v0 con reparto sí puede regir el temporal (D6)."""
    versiones = [_v(0, date(2026, 2, 1))]
    assert version_vigente(versiones, date(2026, 5, 1), temporal=False) is None
    assert _numero(version_vigente(versiones, date(2026, 5, 1), temporal=True)) == 0


def test_f161_r14_sin_lineas_fuera_del_ultimo_cierre() -> None:
    versiones = [_v(1, date(2026, 2, 1)), _v(2, date(2026, 3, 1), n_lineas=0)]
    assert _numero(version_vigente(versiones, date(2026, 5, 1), temporal=False)) == 1


def test_f161_r15_la_0721_tiene_importe_y_no_tiene_temporal() -> None:
    """Su única versión, v1 «CIERRE INICIAL_OBRA», sin reparto (F-162 D6)."""
    versiones = [
        _v(1, date(2025, 3, 1), tipo_master("CIERRE INICIAL_OBRA"), reparto=False,
           importe="13523755.74"),
    ]
    importe = version_vigente(versiones, date(2026, 11, 1), temporal=False)
    assert importe is not None and importe.importe_total == D("13523755.74")
    assert version_vigente(versiones, date(2026, 11, 1), temporal=True) is None


def test_f161_r14_acepta_un_dia_cualquiera_del_mes() -> None:
    versiones = [_v(1, date(2026, 3, 20))]
    assert _numero(version_vigente(versiones, date(2026, 3, 15), temporal=False)) == 1


def test_f161_versionmaster_es_inmutable() -> None:
    v = _v(1, date(2026, 1, 1))
    with pytest.raises(AttributeError):
        v.version = 2  # type: ignore[misc]
