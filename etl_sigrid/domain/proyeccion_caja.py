# etl_sigrid/domain/proyeccion_caja.py
"""
Los ingredientes para pasar el devengo de una obra a caja (F-140, fase 2 de la
cartera de F-037). Dominio puro: sin dependencias de infraestructura.

**EL DATAMART NO CONVIERTE DEVENGO EN CAJA** (regla del humano). Este módulo
lee la fórmula de plazo de Sigrid, calcula el pendiente de una partida y lo
reparte en el tiempo, y valida y resuelve las HIPÓTESIS de conversión; nunca
aplica un plazo, una retención o un IVA a un importe ni a una fecha. La
conversión la hace la IA en vivo, declarando cada hipótesis con su valor y su
nivel (`R-CAJA-HIPOTESIS`).

Es el ORÁCULO del SQL de `sql/tesoreria/` (patrón de F-135): el SQL no lo
llama, pero lleva los mismos literales (`REGEX_TOKEN_DIAS`,
`REGEX_TOKEN_RETENCION`, `SEPARADOR_TOKENS`, el orden de `resolver_hipotesis`)
y `tests/test_f140_sql.py` los compara.

**La fórmula de plazo** (`auxpag.formul`, `auxcob.formul`, medida en las 70 +
52 formas el 2026-10-24): tokens separados por blancos; `N` son los días de un
vencimiento y `NR` los del efecto de RETENCIÓN. `30 60 90` son tres
vencimientos; `120 450R`, uno a 120 días y la retención a 450. Lo que no casa
con esa gramática NO se interpreta: falla cerrado (R8).

**El pendiente de una partida** (R12, D3-A): máx(0, plan de la versión V desde
su mes − ejecutado real en el intervalo [mes de V, último cierre]). Lo
ejecutado de más es `sobre_ejecutado` y no resta a otras partidas.

**El reparto en el tiempo** (R14, D19-A): el pendiente de la partida, en
proporción al plan de V de cada mes posterior al cierre; el último mes del
perfil absorbe el redondeo. Sin perfil, todo al primer mes pendiente, marcado
como retraso.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

# ---------------------------------------------------------------------------
# La fórmula de plazo (R7, R8)
# ---------------------------------------------------------------------------

#: Un token de días de vencimiento: solo dígitos.
REGEX_TOKEN_DIAS = r"^[0-9]+$"
#: El token de la retención: dígitos y una `R` mayúscula final.
REGEX_TOKEN_RETENCION = r"^[0-9]+R$"
#: El separador de tokens, el de `regexp_split_to_array(btrim(f), '\s+')`.
SEPARADOR_TOKENS = r"\s+"
#: Lo que quita `btrim(f)` sin segundo argumento: solo espacios.
_BLANCO_DE_BTRIM = " "


class PlazoFormula(NamedTuple):
    """Lo que dice una fórmula: días de cada vencimiento, de la retención y si se reconoció.

    Una fórmula no reconocida da `((), None, False)`: no se adivina nada.
    """

    dias_vencimientos: tuple[int, ...]
    dias_retencion: int | None
    reconocida: bool


_NO_RECONOCIDA = PlazoFormula((), None, False)


def leer_formula_plazo(formula: str | None) -> PlazoFormula:
    """Lee una fórmula de plazo de Sigrid (R7) o falla cerrado (R8).

    Vacía, `None`, un token que no es `N` ni `NR` o dos `NR`: no reconocida.
    Los días van en el orden escrito. Blancos repetidos separan como uno.
    """
    if formula is None:
        return _NO_RECONOCIDA
    recortada = formula.strip(_BLANCO_DE_BTRIM)
    if not recortada:
        return _NO_RECONOCIDA
    dias: list[int] = []
    retenciones: list[int] = []
    for token in re.split(SEPARADOR_TOKENS, recortada):
        if re.search(REGEX_TOKEN_DIAS, token):
            dias.append(int(token))
        elif re.search(REGEX_TOKEN_RETENCION, token):
            retenciones.append(int(token[:-1]))
        else:
            return _NO_RECONOCIDA
    if len(retenciones) > 1:
        return _NO_RECONOCIDA
    return PlazoFormula(tuple(dias), retenciones[0] if retenciones else None, True)


# ---------------------------------------------------------------------------
# El pendiente de una partida y su reparto (R12, R14)
# ---------------------------------------------------------------------------

_CENTIMO = Decimal("0.01")
_CERO = Decimal(0)


def pendiente_partida(
    plan_desde_version: Decimal, ejecutado_intervalo: Decimal
) -> tuple[Decimal, Decimal]:
    """`(pendiente, sobre_ejecutado)` de una partida (R12).

    `pendiente = máx(0, plan − ejecutado)` y `sobre_ejecutado = máx(0,
    ejecutado − plan)`: nunca los dos a la vez, y su diferencia es la del plan
    y lo ejecutado.
    """
    diferencia = plan_desde_version - ejecutado_intervalo
    return max(_CERO, diferencia), max(_CERO, -diferencia)


def _redondear(valor: Decimal) -> Decimal:
    """`ROUND(numeric, 2)` de PostgreSQL: la mitad, lejos del cero."""
    return valor.quantize(_CENTIMO, rounding=ROUND_HALF_UP)


def repartir_pendiente(
    pendiente: Decimal,
    perfil: Sequence[tuple[date, Decimal]],
    primer_mes: date,
) -> list[tuple[date, Decimal, bool]]:
    """Reparte el pendiente de una partida en sus meses (R14, D19-A).

    `perfil` es el plan de V en cada mes posterior al último cierre. Los meses
    a cero no son perfil (la cola a cero no es plan, criterio de F-110). Si el
    perfil queda vacío o su suma no es positiva, todo va a `primer_mes` con
    `es_retraso` cierto: es lo planificado y no ejecutado que la versión ya no
    sitúa en ningún mes futuro. Si no, cada mes recibe `pendiente × plan_mes /
    plan_total` redondeado al céntimo y el ÚLTIMO mes, el resto: la suma
    iguala el pendiente exactamente. Sin pendiente, no hay reparto.

    Devuelve `[(mes, importe, es_retraso)]` en orden de mes.
    """
    if pendiente == 0:
        return []
    meses = sorted((mes, plan) for mes, plan in perfil if plan != 0)
    total = sum((plan for _mes, plan in meses), _CERO)
    if not meses or total <= 0:
        return [(primer_mes, pendiente, True)]
    reparto: list[tuple[date, Decimal, bool]] = []
    acumulado = _CERO
    for mes, plan in meses[:-1]:
        importe = _redondear(pendiente * plan / total)
        acumulado += importe
        reparto.append((mes, importe, False))
    reparto.append((meses[-1][0], pendiente - acumulado, False))
    return reparto


# ---------------------------------------------------------------------------
# Lo que no se publica (R16)
# ---------------------------------------------------------------------------

#: El nombre de una columna de CAJA: una fecha, un mes o un importe que saldría
#: de APLICAR un plazo, una retención o un IVA a un devengo. Ninguna tabla de
#: F-140 la tiene (`tests/test_f140_sql.py`).
PATRON_COLUMNA_DE_CAJA = r"caja|flujo|previst|fecha_pago|fecha_cobro|con_iva"


def es_columna_de_caja(nombre: str) -> bool:
    """True si el nombre casa con `PATRON_COLUMNA_DE_CAJA`, sin distinguir mayúsculas."""
    return re.search(PATRON_COLUMNA_DE_CAJA, nombre, flags=re.IGNORECASE) is not None
