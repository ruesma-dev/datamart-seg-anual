# harness/tiempos.py
"""Relojes de los tests bajo carga (F-019).

Una campaña de mutación con W workers corre W suites a la vez, y cada una
avanza como mucho W veces más despacio. Los tests que lanzan un subproceso con
un timeout fijo, medido en reposo, caían entonces por reloj y no por defecto:
la línea base salía roja y la campaña abortaba sin culpa de nadie.

`escalar_timeout` multiplica esos timeouts por `ARNES_FACTOR_TIMEOUT_TESTS`,
que la campaña pone al número de workers (salvo que el entorno ya lo traiga).
Fuera de una campaña la variable no existe y el factor es 1: el test se
comporta exactamente como antes.

Módulo propio y sin dependencias porque lo importan los tests del proyecto y
la campaña, y ninguno de los dos debe arrastrar al otro.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping

#: Variable de entorno con el factor por el que se multiplican los timeouts.
VARIABLE_FACTOR = "ARNES_FACTOR_TIMEOUT_TESTS"


def factor_timeout_tests(entorno: Mapping[str, str] | None = None) -> float:
    """El factor de `ARNES_FACTOR_TIMEOUT_TESTS`: un número finito ≥ 1, o 1.

    Ausente, vacío, no numérico, infinito, NaN o menor que 1 cuentan como 1:
    un factor que ACORTA un reloj no es lo que nadie pide al exportarlo, y un
    valor ilegible no debe tumbar la suite.
    """
    valor = (os.environ if entorno is None else entorno).get(VARIABLE_FACTOR)
    try:
        factor = float(valor) if valor is not None else 1.0
    except ValueError:
        return 1.0
    if not math.isfinite(factor) or factor < 1:
        return 1.0
    return factor


def escalar_timeout(segundos: float) -> int:
    """`segundos × factor`, redondeado hacia arriba a segundos enteros."""
    return math.ceil(segundos * factor_timeout_tests())
