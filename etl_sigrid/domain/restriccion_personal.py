# etl_sigrid/domain/restriccion_personal.py
"""
Qué apuntes de la contabilidad son información de PERSONAL (F-135).

Origen: correo de Juan Romero (Dir. Administración y Control de Costes) del
2026-10-09: «hay que limitarla a todos los usuarios salvo a los que tenemos ese
rol», con su criterio «si se cuela algo, restringe DE MÁS y lo afinamos».
Criterio aprobado por el humano el 2026-10-11 (V2 de la spec, D1-b):

* **CR, cuenta restringida entera**: la cuenta empieza por uno de los catorce
  prefijos de `PREFIJOS_CUENTA_RESTRINGIDA`. Sus apuntes se restringen TODOS, en
  cualquier clase de asiento (también cierres y aperturas).
* **AP, asiento de personal**: un asiento cuyos apuntes son TODOS de clase
  `NORMAL` y que tiene algún apunte en una CR o algún concepto de nómina. Se
  restringe ENTERO: la caja (570), el banco y el IVA que van dentro también.
  Exigir `NORMAL` no es un detalle: 243 asientos de regularización, cierre o
  apertura llevan cuentas 640-476 y, sin esa condición, arrastrarían todo el
  grupo 6 y 7 de su empresa y año (medido el 2026-10-09).
* **Apunte restringido**: el de una CR o el de un AP. Su motivo es `CUENTA` si
  la cuenta es CR (aunque el asiento también sea AP) y `ASIENTO_PERSONAL` si
  solo lo es el asiento.

Este módulo es el ORÁCULO: el SQL de `contabilidad_restringida.mayor` no lo
llama, pero lleva los mismos literales (`REGEX_CUENTA_RESTRINGIDA` y
`PATRON_CONCEPTO_NOMINA`, escritos tal cual), y un test los compara (R4).
Dominio puro: sin dependencias de infraestructura.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

#: Los catorce prefijos de cuenta restringida entera (D1-b y D11): los de Juan
#: (640, 642, 649, 465, 466, 476; 460, 461, 544 y 4753) más 641, 643, 644 y 645
#: (indemnizaciones y otras retribuciones). `4753` es de cuatro dígitos: 4750,
#: 4751 y 4752 son impuestos y retenciones de profesionales y quedan visibles
#: fuera de un AP (D12).
PREFIJOS_CUENTA_RESTRINGIDA: tuple[str, ...] = (
    "640", "641", "642", "643", "644", "645", "649",
    "465", "466", "476", "460", "461", "544", "4753",
)

#: La expresión regular que lleva el SQL, construida desde la tupla: es el
#: literal que `02_mayor.sql`, `04_plan_cuentas_general.sql` y
#: `05_mayor_general.sql` deben llevar tal cual (R4).
REGEX_CUENTA_RESTRINGIDA: str = "^(" + "|".join(PREFIJOS_CUENTA_RESTRINGIDA) + ")"

#: El concepto de nómina, en sintaxis de PostgreSQL (`\m` y `\M` son el
#: principio y el fin de palabra) y para `~*` (sin distinguir mayúsculas). La
#: `Ó` va explícita por si el plegado de mayúsculas del servidor no la alcanza.
#: Casa «nómina», «nomina», «NÓMINAS»; no casa «denominación».
PATRON_CONCEPTO_NOMINA: str = r"\mn[oóÓ]minas?\M"

#: El mismo patrón para el `re` de Python, que escribe la frontera como `\b`.
_PATRON_CONCEPTO_PY = re.compile(
    PATRON_CONCEPTO_NOMINA.replace(r"\m", r"\b").replace(r"\M", r"\b"),
    re.IGNORECASE,
)

#: La única clase de asiento que puede ser AP (`contabilidad.mayor.clase_asiento`).
CLASE_NORMAL = "NORMAL"

#: Valores de `motivo_restriccion` (R7).
MOTIVO_CUENTA = "CUENTA"
MOTIVO_ASIENTO_PERSONAL = "ASIENTO_PERSONAL"

#: Lo que publica `contabilidad.plan_cuentas.nombre_cuenta` en las cuentas
#: auxiliares CR (D6): que exista una cuenta de préstamo o de embargo a nombre
#: de alguien ya es el dato que se protege.
TEXTO_CUENTA_ENMASCARADA = "(cuenta restringida)"


@dataclass(frozen=True, slots=True)
class ApunteContable:
    """Lo que el criterio mira de un apunte del mayor."""

    codigo_cuenta: str | None
    clase_asiento: str
    concepto: str | None


def es_cuenta_restringida(codigo: str | None) -> bool:
    """True si el código de cuenta empieza por un prefijo CR (R1).

    Anclado al principio, como el `^` del SQL. Un apunte sin cuenta
    (`cueide = 0`, `None`) no es CR.
    """
    return codigo is not None and codigo.startswith(PREFIJOS_CUENTA_RESTRINGIDA)


def concepto_es_de_nomina(concepto: str | None) -> bool:
    """True si el concepto contiene la palabra nómina, en cualquier forma (R3)."""
    return concepto is not None and _PATRON_CONCEPTO_PY.search(concepto) is not None


def es_asiento_de_personal(apuntes: Sequence[ApunteContable]) -> bool:
    """True si el asiento es AP (R2).

    Todos sus apuntes de clase `NORMAL` y alguno en una CR o con concepto de
    nómina. Un asiento sin apuntes no es AP.
    """
    if not apuntes:
        return False
    if any(a.clase_asiento != CLASE_NORMAL for a in apuntes):
        return False
    return any(
        es_cuenta_restringida(a.codigo_cuenta) or concepto_es_de_nomina(a.concepto)
        for a in apuntes
    )


def motivo_restriccion(apunte: ApunteContable, asiento_es_personal: bool) -> str | None:
    """`CUENTA`, `ASIENTO_PERSONAL` o `None` (visible) (R7).

    La cuenta gana: un apunte de una CR dentro de un AP es `CUENTA`.
    """
    if es_cuenta_restringida(apunte.codigo_cuenta):
        return MOTIVO_CUENTA
    if asiento_es_personal:
        return MOTIVO_ASIENTO_PERSONAL
    return None


def es_apunte_restringido(apunte: ApunteContable, asiento_es_personal: bool) -> bool:
    """True si el apunte no es legible por el rol general."""
    return motivo_restriccion(apunte, asiento_es_personal) is not None
