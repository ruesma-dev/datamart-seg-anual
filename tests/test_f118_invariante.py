# tests/test_f118_invariante.py
"""
F-118 · El invariante de la serie densa con casos generados (R21, R26).

Semilla fija y sin `hypothesis` (no está en el proyecto): cientos de (obra,
ámbito) inventadas, con fases de un mes y de rango solapadas, partidas que
entran, salen, vuelven y valen 0, y para cada partida se comprueba:

- R21: la suma de `importe_mes` publicado es el acumulado de la partida en el
  último cierre del ámbito (0 si ya no está);
- más fuerte: en cada fila publicada, la suma acumulada de los movimientos
  publicados hasta ella es su acumulado (la serie telescopea fila a fila);
- ningún (partida, mes) repetido;
- el relleno siempre mueve 0 y el deshacer siempre mueve algo y deja 0;
- toda fila de Sigrid se publica con su acumulado.
"""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal

from etl_sigrid.domain.mes_fase import FaseReal, meses_relleno
from etl_sigrid.domain.serie_real import relleno_por_mes, serie_densa

SEMILLA = 118
CASOS = 400


def _mas_meses(mes: date, n: int) -> date:
    total = mes.year * 12 + mes.month - 1 + n
    return date(total // 12, total % 12 + 1, 1)


def _fases(rng: random.Random) -> list[FaseReal]:
    """Fases vigentes de una (obra, ámbito): de un mes, de rango, solapadas."""
    mes = date(2015 + rng.randint(0, 8), rng.randint(1, 12), 1)
    fases: list[FaseReal] = []
    for numero in range(1, rng.randint(2, 12) + 1):
        mes = _mas_meses(mes, rng.choice((1, 1, 1, 2, 3, 4)))
        atras = rng.choice((0, 0, 0, 1, 2, 3, 5))
        adelante = rng.choice((0, 0, 1))
        inicio = _mas_meses(mes, -atras)
        fin = _mas_meses(mes, adelante)
        fases.append(FaseReal(numero, mes, inicio, fin))
    return fases


def _partida(rng: random.Random, cierres: list[date]) -> dict[date, Decimal]:
    filas: dict[date, Decimal] = {}
    presente = rng.random() < 0.5
    for mes in cierres:
        if rng.random() < 0.25:
            presente = not presente
        if presente:
            valor = Decimal(0) if rng.random() < 0.15 else Decimal(
                rng.randint(-5000, 20000)
            ) / 100
            filas[mes] = valor
    return filas


def _casos() -> list[tuple[list[date], dict[date, date], dict[date, Decimal]]]:
    rng = random.Random(SEMILLA)
    casos = []
    for _ in range(CASOS):
        fases = _fases(rng)
        cierres = [f.anio_mes for f in fases]
        relleno = relleno_por_mes(
            meses_relleno(fases), {f.numero_fase: f.anio_mes for f in fases}
        )
        for _partida_n in range(rng.randint(1, 6)):
            casos.append((cierres, relleno, _partida(rng, cierres)))
    return casos


CASOS_GENERADOS = _casos()


def test_f118_r26_los_casos_generados_ejercitan_todos_los_tipos_de_fila() -> None:
    """Un generador que nunca produjera un deshacer o un relleno no probaría nada."""
    tipos = {"relleno": 0, "deshacer": 0, "sigrid": 0}
    for cierres, relleno, filas in CASOS_GENERADOS:
        for fila in serie_densa(filas, cierres, relleno):
            if fila.es_deshacer:
                tipos["deshacer"] += 1
            elif fila.es_relleno:
                tipos["relleno"] += 1
            else:
                tipos["sigrid"] += 1
    assert min(tipos.values()) >= 100, tipos


def test_f118_r21_la_suma_telescopea_al_ultimo_cierre_del_ambito() -> None:
    for indice, caso in enumerate(CASOS_GENERADOS):
        _comprobar(indice, *caso)


def _comprobar(
    indice: int, cierres: list[date], relleno: dict[date, date], filas: dict[date, Decimal]
) -> None:
    publicadas = serie_densa(filas, cierres, relleno)

    ultimo = max(cierres)
    assert sum((f.movimiento for f in publicadas), Decimal(0)) == filas.get(
        ultimo, Decimal(0)
    ), f"caso {indice}: la suma no es el acumulado del ultimo cierre"

    meses = [f.mes for f in publicadas]
    assert meses == sorted(set(meses)), f"caso {indice}: mes repetido o desordenado"

    corriente = Decimal(0)
    for fila in publicadas:
        corriente += fila.movimiento
        assert corriente == fila.acumulado, (indice, fila)
        if fila.es_relleno:
            assert fila.movimiento == 0 and not fila.es_deshacer
        if fila.es_deshacer:
            assert fila.acumulado == 0 and fila.movimiento != 0

    sigrid = {f.mes: f.acumulado for f in publicadas if not (f.es_relleno or f.es_deshacer)}
    assert sigrid == dict(filas)
