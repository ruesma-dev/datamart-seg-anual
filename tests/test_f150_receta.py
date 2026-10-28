# tests/test_f150_receta.py
"""
F-150 · La receta de la caja en el dominio (R1, D7): cada hipótesis dice en
qué PASO de la receta se aplica, uno de siete y en este orden.

El orden es la receta: la IA pasa el devengo a caja SIEMPRE así, y la ficha de
`tesoreria.hipotesis_caja` lo cuenta con los mismos siete pasos (R2, T12).
Dominio puro: sin BBDD.
"""

from __future__ import annotations

import dataclasses

import pytest

from etl_sigrid.domain import proyeccion_caja as dom
from etl_sigrid.domain.proyeccion_caja import (
    PASOS_RECETA,
    Hipotesis,
    construir_catalogo,
    validar_catalogo,
)


def _fila(**cambios) -> dict:
    base = {
        "codigo": "H01",
        "sentido": "PAGO",
        "descripcion": "Plazo de pago con contrato",
        "unidad": "DIAS",
        "valor_defecto": 60,
        "fuente_defecto": "forma de pago mas frecuente",
        "ingrediente": "tesoreria.plazos_forma_pago",
        "validado": False,
        "admite_obra": True,
        "paso_receta": "PLAZO",
    }
    base.update(cambios)
    return base


# ---------------------------------------------------------------------------
# R1 · los siete pasos, en su orden
# ---------------------------------------------------------------------------


def test_f150_r1_los_siete_pasos_en_el_orden_de_la_receta() -> None:
    assert PASOS_RECETA == (
        "DEVENGO", "DOCUMENTO", "COEFICIENTES", "PLAZO", "RETENCION", "IVA", "CARTERA",
    )


def test_f150_r1_una_fila_con_su_paso_es_valida() -> None:
    assert validar_catalogo([_fila()]) == []


@pytest.mark.parametrize("paso", PASOS_RECETA)
def test_f150_r1_cada_paso_de_la_lista_vale(paso: str) -> None:
    assert validar_catalogo([_fila(paso_receta=paso)]) == []


def test_f150_r1_sin_paso_receta_es_un_error() -> None:
    fila = _fila()
    del fila["paso_receta"]
    errores = validar_catalogo([fila])
    assert errores == ["H01: falta el campo paso_receta"], errores


@pytest.mark.parametrize("paso", ["plazo", "PAGO", "", None, 4, "COEFICIENTE", " PLAZO"])
def test_f150_r1_un_paso_fuera_de_la_lista_es_un_error(paso) -> None:
    errores = validar_catalogo([_fila(paso_receta=paso)])
    assert len(errores) == 1, errores
    assert errores[0].startswith("H01: paso_receta ")
    assert "fuera de" in errores[0] and "DEVENGO" in errores[0]


def test_f150_r1_construir_catalogo_falla_sin_paso() -> None:
    fila = _fila()
    del fila["paso_receta"]
    with pytest.raises(ValueError, match="falta el campo paso_receta"):
        construir_catalogo([fila])


def test_f150_r1_la_hipotesis_lleva_su_paso() -> None:
    (hipotesis,) = construir_catalogo([_fila(paso_receta="RETENCION")])
    assert hipotesis.paso_receta == "RETENCION"


def test_f150_r1_paso_receta_es_el_ultimo_campo_de_hipotesis() -> None:
    """Al final y con defecto: quien construye una `Hipotesis` sin él no se rompe."""
    campos = [c.name for c in dataclasses.fields(Hipotesis)]
    assert campos[-1] == "paso_receta"
    assert dataclasses.fields(Hipotesis)[-1].default == ""


def test_f150_r1_paso_receta_es_obligatorio_y_no_opcional() -> None:
    assert "paso_receta" in dom._CAMPOS_OBLIGATORIOS
    assert "paso_receta" not in dom._CAMPOS_OPCIONALES
