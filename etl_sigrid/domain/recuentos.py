# etl_sigrid/domain/recuentos.py
"""
F-066 · El veredicto de `check-raw-recuentos`: ¿está en `raw` lo mismo que hay
en Sigrid? **Dominio puro** (R16, R17).

Una ingesta puede terminar «en verde» y dejar media tabla: un `COPY` cortado,
un timeout del balanceador a los 230 s, una página que no volvió.
`check-coherencia` mira de qué carga viene cada tabla y `check-frescura` cuánto
hace que no hay build; ninguno compara el **número de filas** con el origen.

## Cuatro veredictos, y son cosas distintas

* **igual** — las dos cifras coinciden. Es el único que no exige nada.
* **distinta** — hay dos cifras y no coinciden. El informe se queda con las
  dos: «faltan filas» sin decir cuántas no se puede accionar.
* **ausente** — la tabla no existe en `raw`. No es lo mismo que tener cero
  filas: cero es una cifra y se compara como tal.
* **sin medir** — Sigrid no contestó (rechazó la consulta, cortó, no llegó).

## Por qué `sin_medir` NO está conforme

Es la lección de `check-cobertura` del 2026-09-02: **«no he podido mirar» no es
«está bien»**. Un guardián que las confunde es peor que no tenerlo, porque se le
cree. Por eso `ok` exige que las cuatro listas menos `iguales` estén vacías, y
por eso una tabla que no aparece en los mapas cae en `sin_medir` en vez de
desaparecer del informe.

El orden de las cuatro listas es el del YAML de ingesta, que es el orden en que
las tablas se leen y se cargan; no el alfabético.

Capa **domain**: funciones puras, sin BBDD, sin red y sin ficheros. Contar en
Sigrid y en Postgres es cosa del CLI, que es quien tiene los dos clientes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

#: Los cuatro veredictos, tal y como se imprimen. Son constantes porque los
#: busca el test del comando y los lee un humano con prisa.
ESTADO_OK = "OK"
ESTADO_DISTINTA = "DISTINTA"
ESTADO_AUSENTE = "AUSENTE EN RAW"
ESTADO_SIN_MEDIR = "SIN MEDIR"


@dataclass(frozen=True, slots=True)
class Recuento:
    """Lo medido para una tabla. `None` significa «no hay cifra», no «cero»."""

    tabla: str
    sigrid: int | None
    raw: int | None

    @property
    def estado(self) -> str:
        if self.sigrid is None:
            return ESTADO_SIN_MEDIR
        if self.raw is None:
            return ESTADO_AUSENTE
        return ESTADO_OK if self.sigrid == self.raw else ESTADO_DISTINTA


@dataclass(frozen=True, slots=True)
class InformeRecuentos:
    """El barrido entero, en el orden del YAML."""

    #: Una entrada por tabla declarada, para poder sacar una línea por tabla.
    recuentos: tuple[Recuento, ...]
    iguales: tuple[str, ...]
    #: `(tabla, filas en Sigrid, filas en raw)`: las dos cifras, siempre.
    distintas: tuple[tuple[str, int, int], ...]
    ausentes: tuple[str, ...]
    sin_medir: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Conforme solo si todo lo declarado se pudo medir y cuadró."""
        return not (self.distintas or self.ausentes or self.sin_medir)


def comparar_recuentos(
    declaradas: Sequence[str],
    sigrid: Mapping[str, int | None],
    raw: Mapping[str, int | None],
) -> InformeRecuentos:
    """Compara dos mapas `tabla → filas | None` y emite el veredicto.

    `declaradas` manda: una tabla que no esté en alguno de los dos mapas no
    desaparece del informe, cae en `sin_medir`. Un mapa incompleto no puede
    pasar por «todo cuadra».
    """
    recuentos = tuple(
        Recuento(tabla=t, sigrid=sigrid.get(t), raw=raw.get(t)) for t in declaradas
    )

    iguales = tuple(r.tabla for r in recuentos if r.estado == ESTADO_OK)
    ausentes = tuple(r.tabla for r in recuentos if r.estado == ESTADO_AUSENTE)
    sin_medir = tuple(r.tabla for r in recuentos if r.estado == ESTADO_SIN_MEDIR)
    distintas = tuple(
        (r.tabla, int(r.sigrid), int(r.raw))  # type: ignore[arg-type]
        for r in recuentos
        if r.estado == ESTADO_DISTINTA
    )

    return InformeRecuentos(
        recuentos=recuentos,
        iguales=iguales,
        distintas=distintas,
        ausentes=ausentes,
        sin_medir=sin_medir,
    )


def _cifra(valor: int | None) -> str:
    return "—" if valor is None else f"{valor:,}".replace(",", ".")


def formatear(informe: InformeRecuentos) -> str:
    """Una línea por tabla y un resumen con las cuatro cuentas."""
    # La cabecera NO lleva la sangría de dos espacios de las filas: es lo que
    # deja separar el cuerpo del encabezado sin adivinar por el contenido.
    lineas = [f"{'tabla':<16}{'sigrid':>14}{'raw':>14}   veredicto"]
    lineas += [
        f"  {r.tabla:<14}{_cifra(r.sigrid):>14}{_cifra(r.raw):>14}   {r.estado}"
        for r in informe.recuentos
    ]
    lineas.append("")
    lineas.append(
        f"{len(informe.iguales)} iguales · {len(informe.distintas)} distintas · "
        f"{len(informe.ausentes)} ausentes · {len(informe.sin_medir)} sin medir"
    )
    return "\n".join(lineas)
