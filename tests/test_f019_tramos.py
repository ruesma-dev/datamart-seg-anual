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

from etl_sigrid.domain.tramos import (
    Tramo,
    planificar_tramos,
    tramos_sobredimensionados,
)

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
