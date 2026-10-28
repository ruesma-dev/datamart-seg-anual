# tests/test_f150_perfil.py
"""
F-150 · La unidad `PERFIL_MESES` de las hipótesis de caja (R25, D5).

Un perfil reparte un importe ENTERO en varios meses: pares `[meses,
porcentaje]`, `meses` de 0 a 120 y estrictamente creciente, `porcentaje` > 0 y
<= 100 con dos decimales como mucho, y la suma, exactamente 100. Lo que no
cumple eso es un error por cada fallo, igual en `valor_defecto` (el catálogo)
que en la sección `obras` (el valor de una obra). Dominio puro: sin BBDD.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from etl_sigrid.domain.proyeccion_caja import (
    MAX_MESES_PERFIL,
    UNIDADES,
    construir_catalogo,
    validar_catalogo,
    validar_valores_obra,
)

#: Una hipótesis de perfil válida, la forma de H03 tras F-150 (`design.md` §6).
_BASE = {
    "codigo": "H03",
    "sentido": "PAGO",
    "descripcion": "Desfase entre el coste y el documento del proveedor.",
    "unidad": "PERFIL_MESES",
    "valor_defecto": [[0, 100]],
    "fuente_defecto": "Propuesta F-150",
    "ingrediente": None,
    "validado": False,
    "admite_obra": True,
    "paso_receta": "DOCUMENTO",
}


def _fila(**cambios) -> dict:
    fila = dict(_BASE)
    fila.update(cambios)
    return fila


def _errores_defecto(valor) -> list[str]:
    return validar_catalogo([_fila(valor_defecto=valor)])


def _errores_obra(valor) -> list[str]:
    catalogo = {h.codigo: h for h in construir_catalogo([_fila()])}
    fila = {"clave_obra": "1-0704", "codigo": "H03", "valor": valor,
            "motivo": "Pacto con el proveedor", "fecha": date(2026, 10, 28)}
    return validar_valores_obra([fila], catalogo)


# ---------------------------------------------------------------------------
# R25 · lo que vale
# ---------------------------------------------------------------------------


def test_f150_r25_perfil_meses_es_una_unidad() -> None:
    assert "PERFIL_MESES" in UNIDADES
    assert MAX_MESES_PERFIL == 120


@pytest.mark.parametrize("valor", [
    [[0, 100]],
    [[1, 100]],
    [[0, 33.33], [1, 33.33], [2, 33.34]],
    [[0, 50], [3, 25.5], [120, 24.5]],
    [(0, 40), (2, 60)],
    [[0, Decimal("99.99")], [1, Decimal("0.01")]],
    [[0, 100.0]],
])
def test_f150_r25_un_perfil_valido_no_da_errores(valor) -> None:
    assert _errores_defecto(valor) == []
    assert _errores_obra(valor) == []


def test_f150_r25_el_catalogo_conserva_el_perfil_tal_cual() -> None:
    perfil = [[0, 33.33], [1, 33.33], [2, 33.34]]
    (hipotesis,) = construir_catalogo([_fila(valor_defecto=perfil)])
    assert hipotesis.unidad == "PERFIL_MESES"
    assert hipotesis.valor_defecto == perfil


# ---------------------------------------------------------------------------
# R25 · lo que no vale: un error por cada fallo, en el catálogo y en `obras`
# ---------------------------------------------------------------------------

#: (valor, trozos que tiene que decir el error)
_INVALIDOS = [
    ([], ["no es un PERFIL_MESES"]),
    (None, ["no es un PERFIL_MESES"]),
    ({"0": 100}, ["no es un PERFIL_MESES"]),
    ("[[0, 100]]", ["no es un PERFIL_MESES"]),
    (100, ["no es un PERFIL_MESES"]),
    ([[0, 100, 1]], ["par 1", "no es un par"]),
    ([[0]], ["par 1", "no es un par"]),
    ([100], ["par 1", "no es un par"]),
    (["0-100"], ["par 1", "no es un par"]),
    ([[True, 100]], ["par 1", "meses True"]),
    ([[-1, 100]], ["par 1", "meses -1"]),
    ([[121, 100]], ["par 1", "meses 121"]),
    ([[1.5, 100]], ["par 1", "meses 1.5"]),
    ([["0", 100]], ["par 1", "meses '0'"]),
    ([[0, 50], [0, 50]], ["par 2", "creciente"]),
    ([[2, 50], [1, 50]], ["par 2", "creciente"]),
    ([[0, 0], [1, 100]], ["par 1", "porcentaje 0"]),
    ([[0, -10], [1, 110]], ["par 1", "porcentaje -10", "par 2", "porcentaje 110"]),
    ([[0, 100.001]], ["par 1", "porcentaje 100.001"]),
    ([[0, 33.333], [1, 66.667]], ["par 1", "decimales", "par 2"]),
    ([[0, True]], ["par 1", "porcentaje True"]),
    ([[0, "100"]], ["par 1", "porcentaje '100'"]),
    ([[0, float("nan")]], ["par 1", "porcentaje nan"]),
    ([[0, 33.33], [1, 33.33], [2, 33.33]], ["suman 99.99"]),
    ([[0, 50], [1, 50.01]], ["suman 100.01"]),
]


@pytest.mark.parametrize(("valor", "trozos"), _INVALIDOS)
def test_f150_r25_el_valor_defecto_invalido_da_su_error(valor, trozos) -> None:
    errores = _errores_defecto(valor)
    assert errores, f"{valor!r} pasa como PERFIL_MESES"
    texto = " | ".join(errores)
    assert all(e.startswith("H03: ") for e in errores)
    for trozo in trozos:
        assert trozo in texto, (trozo, texto)


@pytest.mark.parametrize(("valor", "trozos"), _INVALIDOS)
def test_f150_r25_el_valor_de_obra_invalido_da_el_mismo_error(valor, trozos) -> None:
    errores = _errores_obra(valor)
    assert errores, f"{valor!r} pasa como PERFIL_MESES en obras"
    texto = " | ".join(errores)
    assert all(e.startswith("obras, fila 1 ('1-0704', 'H03'): ") for e in errores)
    for trozo in trozos:
        assert trozo in texto, (trozo, texto)


def test_f150_r25_un_error_por_cada_fallo() -> None:
    """Tres fallos, tres errores: quien corrige el YAML ve la lista entera."""
    errores = _errores_defecto([[5, 30], [3, 0], [200, 30]])
    assert len(errores) == 4, errores
    texto = " | ".join(errores)
    assert "par 2: meses 3 no es mayor" in texto
    assert "par 2: porcentaje 0" in texto
    assert "par 3: meses 200" in texto
    assert "suman 60" in texto


def test_f150_r25_con_un_par_mal_formado_no_se_suma() -> None:
    """La suma solo se juzga si todos los pares son pares: un error, no dos."""
    errores = _errores_defecto([[0, 50], [1]])
    assert len(errores) == 1, errores
    assert "par 2" in errores[0]


def test_f150_r25_el_porcentaje_fuera_de_rango_no_se_mira_por_decimales() -> None:
    errores = _errores_defecto([[0, 150.555]])
    assert len([e for e in errores if "par 1" in e]) == 1, errores


def test_f150_r25_la_suma_es_exacta_en_decimal_no_en_float() -> None:
    """0.1 + 0.2 en float no es 0.3: la suma va con `Decimal(str(p))`."""
    assert _errores_defecto([[0, 0.1], [1, 0.2], [2, 99.7]]) == []
