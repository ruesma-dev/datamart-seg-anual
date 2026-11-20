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
* **Falla cerrado** (review de F-135, pasada 1): un apunte que trae cuenta
  (`cuenta_id`) pero cuyo código no resuelve en el plan no se sabe si es de
  personal, así que se trata como CR: se restringe con motivo
  `CUENTA_SIN_RESOLVER` (para contarlo aparte) y hace AP a su asiento. Sin eso,
  una auxiliar sin su fila en `raw.cua` dejaría pasar una 465 y su banco al
  general. Hoy son 0 en Azure: no cambia ninguna cifra.

F-127 (2026-11-20) extiende el criterio al MAYOR ANALÍTICO (`raw.apa`), con el
criterio V2 que R23 de F-135 dejó escrito para él. Una fila analítica es
restringida si cualquiera de:

* **C1, apunte restringido**: su apunte financiero (`apuide`) es un apunte
  restringido del mayor completo.
* **C2, asiento de personal**: su asiento (`conide`) es un AP del mayor
  completo (todos sus apuntes `NORMAL` y alguno restringido).
* **C3, cuenta de contrapartida (CP)**: su cuenta analítica es la CP de algún
  recurso (`raw.res.caaconide`) o, por D7-b, una cuenta de un centro de CP con
  abono en un asiento `ANALITICO` (`con.tip = 32`): una CP de antes que el
  recurso ya no declara. Falla cerrado: restringe DE MÁS.
* **Falla cerrado**: una fila con `apuide` que no está en el mayor completo se
  restringe con motivo `APUNTE_SIN_RESOLVER`.

Este módulo es el ORÁCULO: el SQL de `contabilidad_restringida.mayor` y el de
`contabilidad_restringida.mayor_analitico` no lo llaman, pero llevan los mismos
literales (`REGEX_CUENTA_RESTRINGIDA`, `PATRON_CONCEPTO_NOMINA`, los motivos y
los tipos de `con.tip`, escritos tal cual), y un test los compara (R4 de F-135,
R10 de F-127). Dominio puro: sin dependencias de infraestructura.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence, Set
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
MOTIVO_CUENTA_SIN_RESOLVER = "CUENTA_SIN_RESOLVER"
MOTIVO_ASIENTO_PERSONAL = "ASIENTO_PERSONAL"

#: Lo que publica `contabilidad.plan_cuentas.nombre_cuenta` en las cuentas
#: auxiliares CR (D6): que exista una cuenta de préstamo o de embargo a nombre
#: de alguien ya es el dato que se protege.
TEXTO_CUENTA_ENMASCARADA = "(cuenta restringida)"


@dataclass(frozen=True, slots=True)
class ApunteContable:
    """Lo que el criterio mira de un apunte del mayor.

    `cuenta_id` es la cuenta que trae el apunte (`None` si no trae ninguna,
    `cueide = 0`); `codigo_cuenta`, su código en el plan (`None` si no resuelve).
    """

    codigo_cuenta: str | None
    clase_asiento: str
    concepto: str | None
    cuenta_id: int | None = None


def es_cuenta_restringida(codigo: str | None) -> bool:
    """True si el código de cuenta empieza por un prefijo CR (R1).

    Anclado al principio, como el `^` del SQL. Un apunte sin cuenta
    (`cueide = 0`, `None`) no es CR.
    """
    return codigo is not None and codigo.startswith(PREFIJOS_CUENTA_RESTRINGIDA)


def cuenta_sin_resolver(apunte: ApunteContable) -> bool:
    """True si el apunte trae cuenta pero su código no resuelve en el plan."""
    return apunte.cuenta_id is not None and apunte.codigo_cuenta is None


def _cuenta_cerrada(apunte: ApunteContable) -> bool:
    """CR, o cuenta que no resuelve: lo que se restringe por la cuenta."""
    return es_cuenta_restringida(apunte.codigo_cuenta) or cuenta_sin_resolver(apunte)


def concepto_es_de_nomina(concepto: str | None) -> bool:
    """True si el concepto contiene la palabra nómina, en cualquier forma (R3)."""
    return concepto is not None and _PATRON_CONCEPTO_PY.search(concepto) is not None


def es_asiento_de_personal(apuntes: Sequence[ApunteContable]) -> bool:
    """True si el asiento es AP (R2).

    Todos sus apuntes de clase `NORMAL` y alguno en una CR (o en una cuenta que
    no resuelve: falla cerrado) o con concepto de nómina. Un asiento sin
    apuntes no es AP.
    """
    if not apuntes:
        return False
    if any(a.clase_asiento != CLASE_NORMAL for a in apuntes):
        return False
    return any(
        _cuenta_cerrada(a) or concepto_es_de_nomina(a.concepto)
        for a in apuntes
    )


def motivo_restriccion(apunte: ApunteContable, asiento_es_personal: bool) -> str | None:
    """`CUENTA_SIN_RESOLVER`, `CUENTA`, `ASIENTO_PERSONAL` o `None` (visible) (R7).

    La cuenta gana: un apunte de una CR dentro de un AP es `CUENTA`. Una cuenta
    que no resuelve no tiene código, así que nunca es a la vez CR.
    """
    if cuenta_sin_resolver(apunte):
        return MOTIVO_CUENTA_SIN_RESOLVER
    if es_cuenta_restringida(apunte.codigo_cuenta):
        return MOTIVO_CUENTA
    if asiento_es_personal:
        return MOTIVO_ASIENTO_PERSONAL
    return None


def es_apunte_restringido(apunte: ApunteContable, asiento_es_personal: bool) -> bool:
    """True si el apunte no es legible por el rol general."""
    return motivo_restriccion(apunte, asiento_es_personal) is not None


# ===========================================================================
# F-127 · el mayor analítico (`raw.apa`)
# ===========================================================================

#: `con.tip` del asiento de una fila analítica: 20 es el asiento contable (el
#: de los apuntes de `raw.apu`) y 32 el asiento ANALÍTICO puro (código `ANA…`,
#: sin apunte financiero: el que imputa los partes a las obras y abona la CP).
TIPO_CON_ASIENTO = 20
TIPO_CON_ASIENTO_ANALITICO = 32

#: Valores de `tipo_asiento` en el mayor analítico (R3).
TIPO_ASIENTO_CONTABLE = "CONTABLE"
TIPO_ASIENTO_ANALITICO = "ANALITICO"
TIPO_ASIENTO_OTRO = "OTRO"

#: Valores de `motivo_restriccion` del mayor analítico (R8), además de
#: `MOTIVO_ASIENTO_PERSONAL`, que se reutiliza.
MOTIVO_CONTRAPARTIDA = "CONTRAPARTIDA"
MOTIVO_APUNTE_SIN_RESOLVER = "APUNTE_SIN_RESOLVER"
MOTIVO_APUNTE_RESTRINGIDO = "APUNTE_RESTRINGIDO"


def tipo_asiento(tip: int | None) -> str:
    """`CONTABLE` (`con.tip = 20`), `ANALITICO` (32) u `OTRO` (R3)."""
    if tip == TIPO_CON_ASIENTO:
        return TIPO_ASIENTO_CONTABLE
    if tip == TIPO_CON_ASIENTO_ANALITICO:
        return TIPO_ASIENTO_ANALITICO
    return TIPO_ASIENTO_OTRO


@dataclass(frozen=True, slots=True)
class FilaAnalitica:
    """Lo que el criterio mira de una fila de `raw.apa`.

    `apunte_id` es `NULLIF(apa.apuide, 0)`; `apunte_resuelto`, que ese apunte
    está en el mayor completo; `apunte_restringido`, su `restringido` allí;
    `asiento_personal`, que el asiento es AP (C2); `cuenta_es_contrapartida`,
    que la cuenta analítica es CP (C3, con D7-b).
    """

    apunte_id: int | None
    apunte_resuelto: bool
    apunte_restringido: bool
    asiento_personal: bool
    cuenta_es_contrapartida: bool


def centros_de_contrapartida(
    contrapartidas: Set[int], centro_de_cuenta: Mapping[int, int | None]
) -> frozenset[int]:
    """Los centros de coste de las CP actuales (D7-b). Sin centro no cuenta."""
    return frozenset(
        centro
        for cuenta in contrapartidas
        if (centro := centro_de_cuenta.get(cuenta)) is not None
    )


def es_cuenta_contrapartida(
    cuenta_id: int | None,
    *,
    centro_coste_id: int | None,
    abonada_en_analitico: bool,
    contrapartidas: Set[int],
    centros_contrapartida: Set[int],
) -> bool:
    """C3 (R7, D7-b): la CP de un recurso, o una cuenta de un centro de CP con
    abono (`hab <> 0`) en un asiento `ANALITICO`."""
    if cuenta_id is None:
        return False
    if cuenta_id in contrapartidas:
        return True
    return abonada_en_analitico and centro_coste_id in centros_contrapartida


def motivo_apunte_analitico(fila: FilaAnalitica) -> str | None:
    """El motivo de R8, en su precedencia; `None` si la fila es visible.

    `CONTRAPARTIDA` > `APUNTE_SIN_RESOLVER` > `APUNTE_RESTRINGIDO` >
    `ASIENTO_PERSONAL`. Sin apunte financiero (`apuide = 0`) no hay nada que
    resolver.
    """
    if fila.cuenta_es_contrapartida:
        return MOTIVO_CONTRAPARTIDA
    if fila.apunte_id is not None and not fila.apunte_resuelto:
        return MOTIVO_APUNTE_SIN_RESOLVER
    if fila.apunte_restringido:
        return MOTIVO_APUNTE_RESTRINGIDO
    if fila.asiento_personal:
        return MOTIVO_ASIENTO_PERSONAL
    return None


def es_apunte_analitico_restringido(fila: FilaAnalitica) -> bool:
    """True si la fila analítica no es legible por el rol general (R7, R9)."""
    return motivo_apunte_analitico(fila) is not None


def obra_imputada(obras_de_cargo: Iterable[int | None]) -> int | None:
    """La obra de un asiento `ANALITICO` (R6, D4): la de sus filas que no son
    de CP si es UNA sola; con ninguna o con varias, `None`. Las filas sin obra
    no cuentan, como `count(DISTINCT ...)` en SQL."""
    distintas = {obra for obra in obras_de_cargo if obra is not None}
    if len(distintas) == 1:
        return next(iter(distintas))
    return None
