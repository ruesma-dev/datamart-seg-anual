# etl_sigrid/domain/tiemod.py
"""
¿Sirve `tiemod` como watermark? El diagnóstico, respondido con lo que el
datamart ya tiene guardado (F-011, R6 y R7).

La descripción de la feature daba por hecho que «Sigrid NO tiene una marca de
última modificación fiable». Verificado contra `azure-apps/sigrid_tablas.md` el
2026-08-18, esa premisa hay que reformularla: **`tiemod` («Tiempo
modificación») está en 232 filas del diccionario, ~190 tablas**, y la ingesta
**ya la copia** a la columna `_source_tiemod` de cada tabla de `raw` en cada
carga. O sea que la pregunta no es «¿existe una marca?» sino «¿la mantiene
Sigrid?», y esa se responde con SQL local, sin volver a leer Sigrid.

Lo que NO se puede saber con una sola carga es si `tiemod` avanza en toda fila
modificada. Por eso R7 compara **dos fotografías** y emite un veredicto por
tabla; y por eso R19 impedirá activar el modo incremental sin ese veredicto
registrado. Las tres respuestas posibles son distintas y ninguna es un matiz:

  * `SIRVE`         — el máximo global creció y hubo filas que avanzaron.
  * `NO SIRVE`      — la tabla cambió y `tiemod` no, o la columna es toda nula.
  * `SIN EVIDENCIA` — no hay dos cargas comparables, o entre ellas no cambió nada.

Confundir `NO SIRVE` con `SIN EVIDENCIA` mandaría a la basura una columna buena
solo porque esa noche nadie tocó la tabla.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Columna técnica donde `copy_rows` deja el `tiemod` de Sigrid, tabla a tabla.
COLUMNA_TIEMOD = "_source_tiemod"

CABECERA_CSV = ("tabla", "filas", "nulos", "minimo", "maximo", "distintos")


class Veredicto(StrEnum):
    """Las tres respuestas de R7. El valor es el que se imprime."""

    SIRVE = "SIRVE"
    NO_SIRVE = "NO SIRVE"
    SIN_EVIDENCIA = "SIN EVIDENCIA"


@dataclass(frozen=True, slots=True)
class EstadoTiemod:
    """Fotografía de `_source_tiemod` en una tabla de `raw` (R6)."""

    tabla: str
    filas: int
    nulos: int
    minimo: float | None
    maximo: float | None
    distintos: int

    @property
    def pct_nulos(self) -> float:
        """Porcentaje de filas sin marca. 0 si la tabla está vacía."""
        if self.filas <= 0:
            return 0.0
        return self.nulos / self.filas * 100.0

    @property
    def esta_vacia(self) -> bool:
        return self.filas <= 0

    @property
    def toda_nula(self) -> bool:
        """Tabla con filas y **ninguna** con marca. Descalifica la columna.

        Una tabla vacía NO cuenta: no hay nada que juzgar en ella.
        """
        return self.filas > 0 and self.nulos >= self.filas


@dataclass(frozen=True, slots=True)
class ComparacionTiemod:
    """El veredicto de una tabla entre dos cargas (R7)."""

    tabla: str
    antes: EstadoTiemod | None
    ahora: EstadoTiemod
    filas_avanzadas: int | None
    veredicto: Veredicto
    motivo: str

    @property
    def delta_filas(self) -> int:
        """Cuántas filas ha ganado (o perdido) la tabla entre las dos cargas."""
        if self.antes is None:
            return 0
        return self.ahora.filas - self.antes.filas


def veredicto_tiemod(
    antes: EstadoTiemod | None,
    ahora: EstadoTiemod,
    filas_avanzadas: int | None = None,
) -> Veredicto:
    """
    ¿Sirve `tiemod` en esta tabla? (R7)

    `filas_avanzadas` es el `COUNT(*)` de filas cuyo `_source_tiemod` supera el
    máximo de la fotografía anterior, medido con una consulta aparte. Es
    opcional porque comparar dos CSV a secas ya da una respuesta útil; cuando
    está, se exige que las dos señales **coincidan**: un máximo que crece con
    cero filas por encima de él es una contradicción, y ante una contradicción
    lo honrado es no dar la columna por buena.
    """
    return _veredicto_y_motivo(antes, ahora, filas_avanzadas)[0]


def _veredicto_y_motivo(
    antes: EstadoTiemod | None,
    ahora: EstadoTiemod,
    filas_avanzadas: int | None,
) -> tuple[Veredicto, str]:
    """El veredicto y la frase que lo explica, que se imprime al lado."""
    if ahora.toda_nula:
        return (
            Veredicto.NO_SIRVE,
            f"{COLUMNA_TIEMOD} es nula en las {ahora.filas:,} filas de la tabla",
        )
    if ahora.esta_vacia:
        return Veredicto.SIN_EVIDENCIA, "la tabla está vacía"
    if antes is None:
        return Veredicto.SIN_EVIDENCIA, "no hay fotografía anterior de esta tabla"
    if antes.maximo is None or ahora.maximo is None:
        return (
            Veredicto.SIN_EVIDENCIA,
            "alguna de las dos fotografías no tiene ningún valor con el que comparar",
        )

    avanzo_el_maximo = ahora.maximo > antes.maximo
    cambio_el_contenido = ahora.filas != antes.filas

    if avanzo_el_maximo and (filas_avanzadas is None or filas_avanzadas > 0):
        cuantas = (
            "sin recuento de filas"
            if filas_avanzadas is None
            else f"{filas_avanzadas:,} filas por encima del máximo anterior"
        )
        return (
            Veredicto.SIRVE,
            f"el máximo pasó de {antes.maximo:,.5f} a {ahora.maximo:,.5f} ({cuantas})",
        )

    if avanzo_el_maximo:
        return (
            Veredicto.SIN_EVIDENCIA,
            "el máximo creció pero el recuento de filas por encima del anterior "
            "es 0: las dos señales se contradicen",
        )

    if cambio_el_contenido:
        return (
            Veredicto.NO_SIRVE,
            f"la tabla cambió de contenido ({ahora.filas - antes.filas:+,} filas) "
            f"y el máximo de {COLUMNA_TIEMOD} no se movió",
        )

    return Veredicto.SIN_EVIDENCIA, "entre las dos cargas no cambió nada en la tabla"


def comparar_tiemod(
    antes: Iterable[EstadoTiemod],
    ahora: Iterable[EstadoTiemod],
    filas_avanzadas: Mapping[str, int] | None = None,
) -> tuple[ComparacionTiemod, ...]:
    """
    Empareja las dos fotografías **por nombre de tabla** y emite un veredicto.

    Por nombre y no por posición: las dos cargas pueden traer tablas distintas
    (una tabla nueva en el YAML) o en distinto orden, y emparejar por posición
    daría veredictos cruzados sin avisar.
    """
    previos = {e.tabla: e for e in antes}
    avanzadas = dict(filas_avanzadas or {})

    comparaciones = []
    for estado in sorted(ahora, key=lambda e: e.tabla):
        avance = avanzadas.get(estado.tabla)
        veredicto, motivo = _veredicto_y_motivo(
            previos.get(estado.tabla), estado, avance
        )
        comparaciones.append(
            ComparacionTiemod(
                tabla=estado.tabla,
                antes=previos.get(estado.tabla),
                ahora=estado,
                filas_avanzadas=avance,
                veredicto=veredicto,
                motivo=motivo,
            )
        )
    return tuple(comparaciones)


# ---------------------------------------------------------------------------
# Formato para la consola
# ---------------------------------------------------------------------------

_CAB_DIAG = (
    f"{'tabla':<16} {'filas':>14} {'nulos':>12} {'%_nulos':>8} "
    f"{'minimo':>16} {'maximo':>16} {'distintos':>12}"
)
_CAB_COMP = f"{'tabla':<16} {'veredicto':<14} {'Δ filas':>10} {'avanzadas':>10}  motivo"


def format_diagnostico(estados: Sequence[EstadoTiemod]) -> str:
    """Una línea por tabla con las seis cifras de R6, y el total al pie."""
    if not estados:
        return (
            f"Ninguna tabla de `raw` tiene columna {COLUMNA_TIEMOD}. ¿Se ha "
            f"ejecutado alguna ingesta contra esta base?"
        )

    lineas = [_CAB_DIAG, "-" * len(_CAB_DIAG)]
    for e in sorted(estados, key=lambda x: x.tabla):
        lineas.append(
            f"{e.tabla:<16} {e.filas:>14,} {e.nulos:>12,} {e.pct_nulos:>8.1f} "
            f"{_num(e.minimo):>16} {_num(e.maximo):>16} {e.distintos:>12,}"
        )

    filas = sum(e.filas for e in estados)
    nulos = sum(e.nulos for e in estados)
    lineas.append("-" * len(_CAB_DIAG))
    lineas.append(
        f"{'TOTAL':<16} {filas:>14,} {nulos:>12,} "
        f"{(0.0 if filas <= 0 else nulos / filas * 100.0):>8.1f}"
    )
    return "\n".join(lineas)


def format_comparacion(comparaciones: Sequence[ComparacionTiemod]) -> str:
    """Veredicto por tabla y recuento global, que es lo que lee la puerta de R19."""
    if not comparaciones:
        return "Nada que comparar: no hay tablas en común entre las dos cargas."

    lineas = [_CAB_COMP, "-" * len(_CAB_COMP)]
    for c in comparaciones:
        avanzadas = "-" if c.filas_avanzadas is None else f"{c.filas_avanzadas:,}"
        lineas.append(
            f"{c.tabla:<16} {c.veredicto.value:<14} {c.delta_filas:>+10,} "
            f"{avanzadas:>10}  {c.motivo}"
        )

    lineas.append("-" * len(_CAB_COMP))
    lineas.append(
        "RESUMEN: "
        + ", ".join(
            f"{sum(1 for c in comparaciones if c.veredicto is v)} {v.value}"
            for v in Veredicto
        )
    )
    return "\n".join(lineas)


def _num(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:,.5f}"


# ---------------------------------------------------------------------------
# La fotografía en CSV: es lo que se compara entre dos cargas (R7)
#
# Va junto a la clase que serializa, como `Metrica` y `escribir_csv` en
# `fingerprint.py`: el formato de la huella es parte del requisito —`R7` habla
# de «la salida de una ejecución anterior»—, no un detalle del adaptador.
# ---------------------------------------------------------------------------


def escribir_csv_tiemod(estados: Sequence[EstadoTiemod], path: Path) -> None:
    """UTF-8 con BOM y separador `;`, según `docs/CONVENTIONS.md`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(CABECERA_CSV)
        for e in sorted(estados, key=lambda x: x.tabla):
            escritor.writerow(
                [
                    e.tabla,
                    e.filas,
                    e.nulos,
                    "" if e.minimo is None else repr(e.minimo),
                    "" if e.maximo is None else repr(e.maximo),
                    e.distintos,
                ]
            )


def leer_csv_tiemod(path: Path) -> list[EstadoTiemod]:
    """Simétrico de `escribir_csv_tiemod`.

    Rechaza un fichero que no sea una huella en vez de interpretarlo como
    pueda: comparar contra un CSV cualquiera daría un veredicto inventado, que
    es peor que no dar ninguno.
    """
    with path.open(encoding="utf-8-sig", newline="") as f:
        filas = list(csv.reader(f, delimiter=";"))

    if not filas:
        return []
    if tuple(filas[0]) != CABECERA_CSV:
        raise ValueError(
            f"{path} no parece una huella de tiemod: se esperaba la cabecera "
            f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[0])}"
        )

    return [
        EstadoTiemod(
            tabla=fila[0],
            filas=int(fila[1]),
            nulos=int(fila[2]),
            minimo=None if fila[3] == "" else float(fila[3]),
            maximo=None if fila[4] == "" else float(fila[4]),
            distintos=int(fila[5]),
        )
        for fila in filas[1:]
        if fila
    ]
