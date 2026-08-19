# etl_sigrid/domain/extraccion.py
"""
Dominio del banco de extracción: qué rinde cada tamaño de página y qué SQL
tiene permiso de salir hacia Sigrid.

La feature nace de dos premisas sobre `sigrid-api`, y las dos hay que tratarlas
con cuidado:

  * «limita a 1.000 filas por petición» — **refutada** (DA-6): el cap real son
    20.000 y este ETL trabaja a 10.000, por debajo del límite. Lo que queda por
    saber no es cuál es el cap, sino si subir el tamaño de página compra tiempo
    o si el coste está en el SQL Server y no en el transporte (R4).
  * «el balanceador corta a los 230 s» — **sin acreditar**: el documento dice
    120 s y en uso van 230. Eso es lo que mide `latencia_max_s` (R5-bis).

Y una regla que no es de rendimiento sino de seguridad: contra Sigrid, que es
producción de un tercero y a la que se llega por una única puerta, **solo
lecturas** (R23). `es_sentencia_de_lectura` es esa puerta, y vive en el dominio
para que se pueda probar exhaustivamente sin abrir un socket.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: Palabras que convierten una consulta en escritura. `INTO` está en la lista
#: por SQL Server: `SELECT * INTO otra_tabla FROM t` CREA una tabla, así que
#: empezar por SELECT no basta para que algo sea de lectura.
PALABRAS_DE_ESCRITURA = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "MERGE",
    "DROP",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "REVOKE",
    "INTO",
)

#: Fracción del timeout a partir de la cual la latencia observada deja de ser
#: holgura y pasa a ser un aviso. El 80 % no es magia: es el margen que faltó
#: la noche del 2026-08-18, cuando un `timeout_seconds` de 300 contra un corte
#: real de 230 s tumbó la carga.
UMBRAL_AVISO_TIMEOUT = 0.8

_COMENTARIO_LINEA = re.compile(r"--[^\n]*")
_COMENTARIO_BLOQUE = re.compile(r"/\*.*?\*/", re.DOTALL)
_ARRANCA_CON_SELECT = re.compile(r"^SELECT\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class MedicionPagina:
    """Lo medido para UN tamaño de página del barrido."""

    page_size: int
    peticiones: int
    filas: int
    segundos: float
    latencia_max_s: float
    rechazada: bool = False
    cap_devuelto: int | None = None

    @property
    def filas_por_segundo(self) -> float:
        """Ritmo de extracción. 0 si no se llegó a medir tiempo.

        La guardia mira solo el tiempo: con `filas = 0` la división ya da 0,0
        por sí sola. Comprobarlo además sería una condición que ningún test
        puede distinguir —lo dijo la campaña de mutación— y una condición que
        no se puede distinguir es una condición que sobra.
        """
        if self.segundos <= 0:
            return 0.0
        return self.filas / self.segundos

    @property
    def latencia_media_s(self) -> float:
        """Tiempo medio por petición. 0 si la API no aceptó ninguna."""
        if self.peticiones <= 0:
            return 0.0
        return self.segundos / self.peticiones


@dataclass(frozen=True, slots=True)
class ResumenBench:
    """El barrido entero, ya interpretado."""

    mediciones: tuple[MedicionPagina, ...]
    mejor_page_size: int | None
    mejor_filas_por_segundo: float
    latencia_max_s: float
    caps_rechazados: tuple[int, ...]

    @property
    def cap_medido(self) -> int | None:
        """El cap real que ha acreditado la API, o `None` si no rechazó nada.

        Manda el más restrictivo de los rechazos: si dos tamaños distintos
        devuelven caps distintos, el que gobierna lo que se puede pedir es el
        menor.
        """
        return min(self.caps_rechazados) if self.caps_rechazados else None


@dataclass(frozen=True, slots=True)
class Divergencia:
    """El cap documentado y el medido no coinciden (R5, DA-6)."""

    medido: int
    documentado: int
    mensaje: str


def resumen_bench(mediciones: Iterable[MedicionPagina]) -> ResumenBench:
    """
    Interpreta el barrido: mejor tamaño, latencia máxima y caps rechazados.

    Los tamaños rechazados **no compiten** por ser el mejor: un rechazo no es
    un resultado malo, es la ausencia de resultado. Contarlo como 0 filas/s
    sería confundir «la API no me deja» con «va lento».
    """
    lista = tuple(mediciones)
    admitidas = [m for m in lista if not m.rechazada]

    mejor = max(admitidas, key=lambda m: m.filas_por_segundo, default=None)
    caps = tuple(
        m.cap_devuelto for m in lista if m.rechazada and m.cap_devuelto is not None
    )

    return ResumenBench(
        mediciones=lista,
        mejor_page_size=None if mejor is None else mejor.page_size,
        mejor_filas_por_segundo=0.0 if mejor is None else mejor.filas_por_segundo,
        latencia_max_s=max((m.latencia_max_s for m in lista), default=0.0),
        caps_rechazados=caps,
    )


def es_sentencia_de_lectura(sql: str) -> bool:
    """
    ¿Puede esta sentencia salir hacia `/api/sql/read`? (R23)

    Criterio, deliberadamente estrecho:

      1. Quitados comentarios y espacios, tiene que **empezar** por `SELECT`.
      2. No puede contener ninguna palabra de escritura (`PALABRAS_DE_ESCRITURA`),
         comparada como palabra completa: `updated_at` no es un `UPDATE`.
      3. No puede llevar una segunda sentencia detrás de un `;`.

    Un `WITH ... SELECT` es una lectura perfectamente legítima y aquí se
    rechaza igual: el requisito dice «que no empiece por SELECT» y esta feature
    no necesita CTEs contra Sigrid. Es mejor un validador estrecho que haya que
    ampliar a propósito que uno ancho por si acaso.
    """
    limpio = _COMENTARIO_BLOQUE.sub(" ", sql)
    limpio = _COMENTARIO_LINEA.sub(" ", limpio).strip()
    if not limpio:
        return False

    # Un `;` final es aceptable; lo que no lo es es otra sentencia detrás.
    cuerpo, _, resto = limpio.partition(";")
    if resto.strip():
        return False

    if not _ARRANCA_CON_SELECT.match(cuerpo.strip()):
        return False

    mayusculas = cuerpo.upper()
    return not any(
        re.search(rf"\b{palabra}\b", mayusculas) for palabra in PALABRAS_DE_ESCRITURA
    )


def comparar_cap(medido: int | None, documentado: int) -> Divergencia | None:
    """
    Compara el cap que la API acredita con el que dice su documentación.

    Devuelve `None` cuando no hay nada que avisar, incluido el caso de no haber
    medido: no medir no es lo mismo que coincidir.

    El mensaje nombra al dueño del documento a propósito. `azure-apps/sigrid_api.md`
    es de `sigrid-api`, no de este proyecto: aquí se registra el dato y se avisa
    (T8-bis), no se corrige el documento ajeno.
    """
    if medido is None or medido == documentado:
        return None

    return Divergencia(
        medido=medido,
        documentado=documentado,
        mensaje=(
            f"El cap real de sigrid-api es {medido:,} filas por petición, no "
            f"{documentado:,} como documenta azure-apps/sigrid_api.md. Este "
            f"proyecto NO edita ese documento: avisar a su dueño, el proyecto "
            f"sigrid-api."
        ),
    )


# ---------------------------------------------------------------------------
# Formato para la consola
# ---------------------------------------------------------------------------

_CAB_BENCH = (
    f"{'page_size':>10} {'peticiones':>11} {'filas':>12} {'segundos':>10} "
    f"{'filas/s':>12} {'lat_media_s':>12} {'lat_max_s':>11}  observación"
)


def format_bench(resumen: ResumenBench, timeout_s: float) -> str:
    """
    Tabla del barrido con el veredicto de R4 y el aviso de R5-bis.

    `timeout_s` se recibe en vez de leerse de la configuración porque este
    módulo es dominio puro: quien sabe qué timeout está en uso es el comando.
    """
    if not resumen.mediciones:
        return (
            "Sin mediciones: ningún tamaño de página llegó a probarse. "
            "¿Tabla mal escrita, o la API rechazó todos los tamaños?"
        )

    lineas = [_CAB_BENCH, "-" * len(_CAB_BENCH)]
    for m in resumen.mediciones:
        observacion = ""
        if m.rechazada:
            cap = "cap desconocido" if m.cap_devuelto is None else f"cap {m.cap_devuelto:,}"
            observacion = f"RECHAZADA por la API ({cap})"
        lineas.append(
            f"{m.page_size:>10,} {m.peticiones:>11,} {m.filas:>12,} "
            f"{m.segundos:>10.2f} {m.filas_por_segundo:>12,.0f} "
            f"{m.latencia_media_s:>12.2f} {m.latencia_max_s:>11.2f}  {observacion}"
        )

    lineas.append("-" * len(_CAB_BENCH))
    lineas.extend(_veredicto_bench(resumen, timeout_s))
    return "\n".join(lineas)


def _veredicto_bench(resumen: ResumenBench, timeout_s: float) -> Sequence[str]:
    """Las tres conclusiones: mejor tamaño, cap real y margen de timeout."""
    lineas: list[str] = []

    if resumen.mejor_page_size is not None:
        lineas.append(
            f"R4: mejor rendimiento con page_size={resumen.mejor_page_size:,} "
            f"({resumen.mejor_filas_por_segundo:,.0f} filas/s)."
        )

    if resumen.cap_medido is not None:
        lineas.append(
            f"R5: la API acredita un cap de {resumen.cap_medido:,} filas por petición."
        )

    lineas.append(
        f"R5-bis: latencia máxima observada {resumen.latencia_max_s:.2f} s "
        f"frente a un timeout configurado de {timeout_s:.0f} s."
    )
    if resumen.latencia_max_s >= timeout_s * UMBRAL_AVISO_TIMEOUT:
        lineas.append(
            f"AVISO: la petición más lenta consumió el "
            f"{resumen.latencia_max_s / timeout_s * 100:.0f} % del timeout de "
            f"{timeout_s:.0f} s. Con una tabla mayor, o el SQL Server más "
            f"cargado, esto es un corte."
        )
    return lineas
