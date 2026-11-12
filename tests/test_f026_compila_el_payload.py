# tests/test_f026_compila_el_payload.py
"""R14 de F-026: ningún mutante del propio payload deja de compilar.

`test_f026_operadores.py` lo comprueba sobre un fuente de patrones escrito a
propósito; aquí, sobre el código real del arnés, que es donde aparecen las
formas que nadie pensó al escribir los patrones (`not (...)` en `carril.py` y
en el propio `mutacion.py` era justo una de ellas). Todas las líneas de
`harness/*.py` entran en el alcance.

Coste (decisión 5 de la spec: si pasa de 10 s, muestra fija con semilla).
Medido el 2026-11-07: compilar el FICHERO entero por cada mutante costaba 54 s
solo para `mutacion.py` (~80 ms por compilación × ~700 mutantes). Por eso:

1. **Todos** los mutantes se compilan, pero solo la sentencia de primer nivel
   que los contiene (con sus decoradores). Un mutante cambia UNA línea, y una
   sentencia de primer nivel es una unidad sintáctica completa: si el cambio
   desparejara un paréntesis o rompiera la sentencia, la sentencia sola deja
   de compilar igual que el fichero. ~5 s para todo el payload.
2. Una **muestra fija** (`SEMILLA`, `MUESTRA` por fichero) se compila además
   sobre el fichero entero, para que la equivalencia del punto 1 no sea una
   fe: si una sentencia suelta compilara y el fichero no, se vería aquí.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from harness.mutacion import Mutante, aplicar_mutante, generar_mutantes

HARNESS = Path(__file__).resolve().parent.parent / "harness"
FICHEROS = sorted(HARNESS.glob("*.py"))
SEMILLA = 0
MUESTRA = 5


def _mutantes(ruta: Path) -> tuple[str, list[Mutante]]:
    fuente = ruta.read_text(encoding="utf-8")
    nombre = f"harness/{ruta.name}"
    return fuente, generar_mutantes(fuente, set(range(1, fuente.count("\n") + 2)), nombre)


def _tramos(fuente: str) -> list[tuple[int, int]]:
    """`(primera, última)` línea de cada sentencia de primer nivel."""
    tramos = []
    for nodo in ast.parse(fuente).body:
        decoradores = [d.lineno for d in getattr(nodo, "decorator_list", [])]
        tramos.append((min([nodo.lineno, *decoradores]), nodo.end_lineno or nodo.lineno))
    return tramos


def _error(texto: str, nombre: str) -> str | None:
    try:
        compile(texto, nombre, "exec")
    except SyntaxError as error:
        return error.msg
    return None


def test_f026_r14_hay_ficheros_del_payload_que_medir() -> None:
    assert len(FICHEROS) >= 10


@pytest.mark.parametrize("ruta", FICHEROS, ids=lambda ruta: ruta.name)
def test_f026_r14_cada_mutante_del_payload_compila(ruta: Path) -> None:
    fuente, mutantes = _mutantes(ruta)
    tramos = _tramos(fuente)

    rotos = []
    for mutante in mutantes:
        ini, fin = next(t for t in tramos if t[0] <= mutante.linea <= t[1])
        sentencia = "\n".join(aplicar_mutante(fuente, mutante).split("\n")[ini - 1 : fin])
        error = _error(sentencia, mutante.fichero)
        if error is not None:
            rotos.append(f"{mutante.descripcion()} ({error})")

    assert rotos == []


@pytest.mark.parametrize("ruta", FICHEROS, ids=lambda ruta: ruta.name)
def test_f026_r14_muestra_fija_compila_el_fichero_entero(ruta: Path) -> None:
    fuente, mutantes = _mutantes(ruta)
    muestra = random.Random(SEMILLA).sample(mutantes, min(MUESTRA, len(mutantes)))

    rotos = [
        f"{m.descripcion()} ({error})"
        for m in muestra
        if (error := _error(aplicar_mutante(fuente, m), m.fichero)) is not None
    ]

    assert rotos == []


def test_f026_r14_la_sentencia_suelta_delata_lo_que_delata_el_fichero() -> None:
    """Control del punto 1: el `not (` de antes de F-026, cazado por la sentencia."""
    fuente = "import os\n\n\ndef f(a, b):\n    if not (a and b):\n        return 1\n"
    roto = Mutante("m.py", 5, 7, "if not (a and b):", "if a and b):", "not", 5, "")
    ini, fin = next(t for t in _tramos(fuente) if t[0] <= roto.linea <= t[1])
    mutada = aplicar_mutante(fuente, roto)

    assert _error(mutada, "m.py") is not None
    assert _error("\n".join(mutada.split("\n")[ini - 1 : fin]), "m.py") is not None
