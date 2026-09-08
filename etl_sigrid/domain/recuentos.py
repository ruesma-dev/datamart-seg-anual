# etl_sigrid/domain/recuentos.py
"""
F-066 · El veredicto de `check-raw-recuentos`: ¿está en `raw` lo mismo que hay
en Sigrid? **Dominio puro** (R15, R16, R17).

Una ingesta puede terminar «en verde» y dejar media tabla: un `COPY` cortado,
un timeout del balanceador a los 230 s, una página que no volvió.
`check-coherencia` mira de qué carga viene cada tabla y `check-frescura` cuánto
hace que no hay build; ninguno compara el **número de filas** con el origen.

## Igualdad exacta era un criterio inalcanzable (corregido el 2026-09-08)

La primera versión exigía que las 56 cifras coincidieran al alma. Eso no puede
pasar nunca: Sigrid es un ERP que se sigue usando mientras el datamart es una
foto de un instante. La primera medición real lo dejó claro —ingesta de las
11:16-11:57 UTC, verificación unas cinco horas después—:

    31 iguales · 25 distintas · 0 ausentes · 0 sin medir      -> código 1

y las 25 eran trabajo en el origen, no un fallo. Se sabe por la **firma**: 25
de 25 con Sigrid POR ENCIMA de `raw` y **ninguna** al revés, 4.883 filas sobre
25.287.500 (0,0193 %) y la peor tabla, `obrparpre`, en +3.969 sobre 13.884.933
(0,0286 %). Un guardián que se pone rojo todas las noches se deja de mirar, y
entonces ya no guarda nada.

## La dirección importa más que la magnitud

* **Sigrid con más filas que `raw`** es la deriva normal. Se acepta mientras
  quede por debajo de la tolerancia, y entonces la tabla está `DERIVA`.
* **Sigrid con menos filas que `raw`** es alarma inmediata, **sea de una
  fila**. Eso no lo produce el paso del tiempo: o se borró algo en origen, o
  la ingesta duplicó, o cargó lo que no era. Hasta hoy se confundía con lo
  anterior y se perdía dentro del mismo montón.
* `AUSENTE EN RAW` y `SIN MEDIR` siguen siendo fallo, con tolerancia o sin
  ella: son la lección de `check-cobertura` del 2026-09-02, **«no he podido
  mirar» no es «está bien»**.

## Por qué la tolerancia es relativa y por tabla

50 filas no significan lo mismo en `obrparpre` (13,9 M) que en un catálogo de
200: en la primera son ruido y en el segundo son un cuarto de la tabla. Un
umbral **absoluto** trataría igual las dos, y uno **global** —sobre la suma de
las 56— quedaría dominado por `obrparpre`, que ella sola es el 55 % de las
filas: perder un catálogo entero no movería la cifra global ni un 0,001 %. La
consecuencia buscada es que en una tabla pequeña la tolerancia relativa no
llega ni a una fila, es decir, se le sigue exigiendo exactitud.

Capa **domain**: funciones puras, sin BBDD, sin red y sin ficheros. Contar en
Sigrid y en Postgres es cosa del CLI, que es quien tiene los dos clientes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

#: Cuánta deriva se acepta en una tabla, en **porcentaje** de las filas que
#: tiene Sigrid, y solo en la dirección «Sigrid tiene más».
#:
#: No es un número redondo elegido a ojo: es lo único que cabe entre las dos
#: cotas que lo aprietan.
#:
#: * Por abajo, el peor día medido (2026-09-08, `obrparpre` con 3.969 filas
#:   sobre 13.884.933 tras cinco horas de uso) da 0,0286 %. Por debajo de eso
#:   el comando se pondría rojo una mañana normal.
#: * Por arriba, una **página perdida** de la ingesta son 10.000 filas
#:   (`page_size` de sigrid-api), que en la tabla más grande del YAML son
#:   0,072 %. Por encima de eso el comando dejaría de ver justo aquello para
#:   lo que se escribió.
#:
#: 0,05 % está casi en el centro geométrico de esa ventana: 1,7 veces el peor
#: día medido y por debajo de una página perdida en **todas** las tablas
#: declaradas. Se cambia con `--tolerancia-pct`; con `0` se recupera la
#: igualdad exacta de la primera versión.
TOLERANCIA_DERIVA_PCT = 0.05

#: Los seis veredictos, tal y como se imprimen. Son constantes porque los busca
#: el test del comando y los lee un humano con prisa a las tres de la mañana.
ESTADO_OK = "OK"
ESTADO_DERIVA = "DERIVA"
ESTADO_FALTAN = "FALTAN EN RAW"
ESTADO_SOBRAN = "SOBRAN EN RAW"
ESTADO_AUSENTE = "AUSENTE EN RAW"
ESTADO_SIN_MEDIR = "SIN MEDIR"

_SIN_CIFRA = "—"


@dataclass(frozen=True, slots=True)
class Recuento:
    """Lo medido para una tabla. `None` significa «no hay cifra», no «cero»."""

    tabla: str
    sigrid: int | None
    raw: int | None
    tolerancia_pct: float = TOLERANCIA_DERIVA_PCT

    @property
    def diferencia(self) -> int | None:
        """Filas que Sigrid tiene **de más** (positivo) o de menos (negativo)."""
        if self.sigrid is None or self.raw is None:
            return None
        return self.sigrid - self.raw

    @property
    def desviacion_pct(self) -> float | None:
        """La diferencia, en porcentaje de lo que hay en Sigrid.

        Se divide por la cifra de Sigrid porque es la de referencia: `raw`
        aspira a ser una copia suya. Si Sigrid dice cero y `raw` trae filas, la
        desviación es del 100 %, que es exactamente lo que significa.
        """
        diferencia = self.diferencia
        if diferencia is None:
            return None
        if not self.sigrid:
            return 0.0 if diferencia == 0 else 100.0
        return abs(diferencia) * 100.0 / self.sigrid

    @property
    def estado(self) -> str:
        diferencia = self.diferencia
        if self.sigrid is None:
            return ESTADO_SIN_MEDIR
        if self.raw is None:
            return ESTADO_AUSENTE
        if diferencia == 0:
            return ESTADO_OK
        if diferencia < 0:  # type: ignore[operator]
            return ESTADO_SOBRAN
        return (
            ESTADO_DERIVA
            if self.desviacion_pct <= self.tolerancia_pct  # type: ignore[operator]
            else ESTADO_FALTAN
        )


@dataclass(frozen=True, slots=True)
class InformeRecuentos:
    """El barrido entero, en el orden del YAML."""

    #: Una entrada por tabla declarada, para poder sacar una línea por tabla.
    recuentos: tuple[Recuento, ...]
    #: El umbral que se aplicó, para que el verde se pueda interpretar.
    tolerancia_pct: float
    iguales: tuple[str, ...]
    #: `(tabla, filas en Sigrid, filas en raw)`: las dos cifras, siempre.
    toleradas: tuple[tuple[str, int, int], ...]
    faltantes: tuple[tuple[str, int, int], ...]
    sobrantes: tuple[tuple[str, int, int], ...]
    ausentes: tuple[str, ...]
    sin_medir: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Conforme si todo se pudo medir y lo que no cuadra es deriva normal."""
        return not (
            self.faltantes or self.sobrantes or self.ausentes or self.sin_medir
        )

    @property
    def peor(self) -> Recuento | None:
        """La tabla con más desviación relativa, que es la que hay que mirar."""
        medidas = [r for r in self.recuentos if r.desviacion_pct]
        return max(medidas, key=lambda r: r.desviacion_pct or 0.0) if medidas else None


def comparar_recuentos(
    declaradas: Sequence[str],
    sigrid: Mapping[str, int | None],
    raw: Mapping[str, int | None],
    tolerancia_pct: float = TOLERANCIA_DERIVA_PCT,
) -> InformeRecuentos:
    """Compara dos mapas `tabla → filas | None` y emite el veredicto.

    `declaradas` manda: una tabla que no esté en alguno de los dos mapas no
    desaparece del informe, cae en `sin_medir`. Un mapa incompleto no puede
    pasar por «todo cuadra».
    """
    recuentos = tuple(
        Recuento(
            tabla=t,
            sigrid=sigrid.get(t),
            raw=raw.get(t),
            tolerancia_pct=tolerancia_pct,
        )
        for t in declaradas
    )

    def _cifras(estado: str) -> tuple[tuple[str, int, int], ...]:
        return tuple(
            (r.tabla, int(r.sigrid), int(r.raw))  # type: ignore[arg-type]
            for r in recuentos
            if r.estado == estado
        )

    def _nombres(estado: str) -> tuple[str, ...]:
        return tuple(r.tabla for r in recuentos if r.estado == estado)

    return InformeRecuentos(
        recuentos=recuentos,
        tolerancia_pct=tolerancia_pct,
        iguales=_nombres(ESTADO_OK),
        toleradas=_cifras(ESTADO_DERIVA),
        faltantes=_cifras(ESTADO_FALTAN),
        sobrantes=_cifras(ESTADO_SOBRAN),
        ausentes=_nombres(ESTADO_AUSENTE),
        sin_medir=_nombres(ESTADO_SIN_MEDIR),
    )


def _cifra(valor: int | None) -> str:
    return _SIN_CIFRA if valor is None else f"{valor:,}".replace(",", ".")


def _pct(valor: float | None) -> str:
    return _SIN_CIFRA if valor is None else f"{valor:.4f} %".replace(".", ",")


def _diferencia(valor: int | None) -> str:
    return _SIN_CIFRA if valor is None else f"{valor:+,}".replace(",", ".")


def _bloque(titulo: str, filas: tuple[tuple[str, int, int], ...]) -> list[str]:
    if not filas:
        return []
    return [""] + [titulo] + [
        f"  {tabla}: Sigrid {_cifra(s)}, raw {_cifra(r)} ({_diferencia(s - r)})"
        for tabla, s, r in filas
    ]


def formatear(informe: InformeRecuentos, horas_desde_ingesta: float | None = None) -> str:
    """Una línea por tabla, los hallazgos aparte y el veredicto al final.

    `horas_desde_ingesta` es **contexto, no criterio**: la deriva esperable es
    proporcional al tiempo transcurrido desde la última ingesta correcta, así
    que un 0,03 % cinco horas después es normal y cinco minutos después no lo
    es. No entra en el veredicto —una vista que no se puede leer no puede
    volver rojo un día bueno ni verde uno malo—, solo se enseña.
    """
    # La cabecera NO lleva la sangría de dos espacios de las filas: es lo que
    # deja separar el cuerpo del encabezado sin adivinar por el contenido.
    lineas = [f"{'tabla':<16}{'sigrid':>14}{'raw':>14}{'desv.':>11}   veredicto"]
    lineas += [
        f"  {r.tabla:<14}{_cifra(r.sigrid):>14}{_cifra(r.raw):>14}"
        f"{_pct(r.desviacion_pct):>11}   {r.estado}"
        for r in informe.recuentos
    ]

    lineas += _bloque(
        "SIGRID TIENE MENOS FILAS QUE raw. Eso no es deriva: mira si se ha "
        "borrado algo en origen o si la ingesta duplicó.",
        informe.sobrantes,
    )
    lineas += _bloque(
        "Faltan filas en raw por encima de la tolerancia. Mira si la ingesta "
        "se cortó a media tabla.",
        informe.faltantes,
    )

    peor = informe.peor
    lineas.append("")
    lineas.append(
        f"{len(informe.iguales)} iguales · "
        f"{len(informe.toleradas)} con deriva tolerada · "
        f"{len(informe.faltantes)} con filas que faltan en raw · "
        f"{len(informe.sobrantes)} con filas que sobran en raw · "
        f"{len(informe.ausentes)} ausentes · "
        f"{len(informe.sin_medir)} sin medir"
    )
    lineas.append(
        f"tolerancia {_pct(informe.tolerancia_pct)} por tabla, y solo hacia "
        f"arriba · desviación máxima "
        + (f"{_pct(peor.desviacion_pct)} ({peor.tabla})" if peor else "ninguna")
    )
    lineas.append(
        "última ingesta correcta: "
        + (
            "hace un tiempo desconocido (no se pudo leer _meta.v_frescura)"
            if horas_desde_ingesta is None
            else f"hace {horas_desde_ingesta:.1f} h".replace(".", ",")
        )
    )
    lineas.append(f"VEREDICTO: {'CONFORME' if informe.ok else 'NO CONFORME'}")
    return "\n".join(lineas)
