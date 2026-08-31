# etl_sigrid/domain/huella_ampliada.py
"""
F-052 · La revisión de datos ampliada: huellas 3 y 4 (T28-T30, R11).
**Dominio puro.**

## Por qué existe

El humano **eximió la campaña de mutación** el 2026-08-31 y pidió a cambio más
revisión de datos: *«con respecto a la B es crucial que no cambie o rompa lo que
se está construyendo ahora que está bien; prefiero que se haga una revisión de
datos antes y después que tantos mutation test»*. La comparación antes/después
pasó de dos huellas a **cuatro**, y estas son las dos nuevas:

* **Huella 3 · dimensión** — `stg.partidas` resumida por obra. Caza una partida
  que **cambie de sitio en el árbol sin cambiar de importe**: otro padre, otro
  nivel, otra ruta. Para las huellas de dinero eso es invisible, y sin embargo
  sale distinto en Power BI, porque el «Árbol Presupuesto» se dibuja con
  `ruta_capitulos` y `nivel`.
* **Huella 4 · cierre** — `cierre.fact_cierre_mensual` por obra × mes ×
  concepto. Es la capa que **Negocio ve**, y la que esta feature mueve entera en
  la 0599: DIRECTOS pasa de 0,00 € a ~2,62 M €.

## Por qué son genéricas y no dos módulos calcados

Las dos hacen lo mismo: leer un CSV, cruzar por una clave y listar **todas** las
diferencias. Lo único que cambia es qué columnas forman la clave. Un `FormatoHuella`
lo declara y el resto es común, así que añadir una quinta huella el día que haga
falta es declarar seis nombres de columna y no copiar doscientas líneas.

Se comparan **como texto**, a propósito. Las dos huellas se escriben con el mismo
código y se leen con el mismo código, así que la igualdad de cadenas es exacta y
no introduce redondeos que el build no tiene. Un `Decimal` reconvertido dos veces
sí podría introducirlos.

## El criterio: CERO

`veredicto_ampliado` sale distinto de 0 ante **cualquier** diferencia en una obra
que no esté en la lista esperada. No hay umbral, ni porcentaje, ni tolerancia:
lo fijó el humano y es lo que sustituye a la campaña de mutación.

Capa **domain**: sin BBDD ni ficheros. Leer la base y escribir el CSV es
`infrastructure/postgres/huella_ampliada.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: Lo que se escribe en el lado que no tiene fila. **No se salta**: una obra que
#: aparece o desaparece ES un cambio, y de los gordos.
SIN_FILA = "(sin fila)"


@dataclass(frozen=True, slots=True)
class FormatoHuella:
    """Qué columnas trae una huella y cuáles de ellas forman su clave."""

    nombre: str
    cabecera: tuple[str, ...]
    columnas_clave: tuple[str, ...]
    #: Para qué sirve, en una línea, para que el informe la explique solo.
    proposito: str

    def __post_init__(self) -> None:
        faltan = [c for c in self.columnas_clave if c not in self.cabecera]
        if faltan:
            raise ValueError(
                f"el formato {self.nombre} declara columnas de clave que no "
                f"estan en su cabecera: {', '.join(faltan)}"
            )
        if "codigo_obra" not in self.cabecera:
            raise ValueError(
                f"el formato {self.nombre} no trae `codigo_obra`, y sin el no se "
                f"puede decidir si la obra que se mueve estaba en la lista"
            )

    @property
    def columnas_valor(self) -> tuple[str, ...]:
        return tuple(c for c in self.cabecera if c not in self.columnas_clave)


#: **Huella 3.** Una fila por obra. `resumen` es un `md5` sobre las seis
#: columnas que definen dónde está cada partida dentro del árbol, ordenadas por
#: `partida_id`: si una sola se mueve, cambia el resumen de su obra.
FORMATO_DIMENSION = FormatoHuella(
    nombre="dimension",
    cabecera=("obra_id", "codigo_obra", "partidas", "raices", "nivel_max", "resumen"),
    columnas_clave=("obra_id",),
    proposito=(
        "el ARBOL de stg.partidas por obra: caza una partida que cambie de sitio "
        "sin cambiar de importe"
    ),
)

#: **Huella 4.** La capa que Negocio ve en Power BI, y la que esta feature mueve
#: entera en la 0599.
FORMATO_CIERRE = FormatoHuella(
    nombre="cierre",
    cabecera=(
        "obra_id",
        "codigo_obra",
        "periodo",
        "concepto",
        "filas",
        "ejecutado_origen",
        "ejecutado_mes",
        "final_importe",
        "pendiente_importe",
    ),
    columnas_clave=("obra_id", "periodo", "concepto"),
    proposito="el CIERRE por obra x mes x concepto, que es lo que Negocio lee",
)

FORMATOS = (FORMATO_DIMENSION, FORMATO_CIERRE)


def formato_de(cabecera: Sequence[str]) -> FormatoHuella | None:
    """El formato cuya cabecera coincide **exactamente**, o `None`.

    Exactamente y en orden: un CSV con las mismas columnas en otro orden se
    rechaza en vez de leerse mal en silencio.
    """
    columnas = tuple(cabecera)
    return next((f for f in FORMATOS if f.cabecera == columnas), None)


@dataclass(frozen=True, slots=True)
class FilaAmpliada:
    """Una fila de huella: su clave, su obra y sus valores, todo como texto."""

    codigo_obra: str
    clave: tuple[str, ...]
    valores: tuple[tuple[str, str], ...]

    @property
    def como_dict(self) -> dict[str, str]:
        return dict(self.valores)


@dataclass(frozen=True, slots=True)
class DiferenciaAmpliada:
    codigo_obra: str
    clave: tuple[str, ...]
    campo: str
    antes: str
    despues: str


@dataclass(frozen=True, slots=True)
class ComparacionAmpliada:
    """Las diferencias, **todas**, más lo que hace falta para leerlas.

    `filas_antes` y `filas_despues` van aquí porque un «0 diferencias» sobre dos
    huellas vacías es indistinguible de un «0 diferencias» sobre 390.501
    partidas, y sólo uno de los dos prueba algo.
    """

    formato: FormatoHuella
    diferencias: tuple[DiferenciaAmpliada, ...]
    filas_antes: int
    filas_despues: int


def comparar_ampliada(
    formato: FormatoHuella,
    antes: Iterable[FilaAmpliada],
    despues: Iterable[FilaAmpliada],
) -> ComparacionAmpliada:
    """Todas las diferencias entre dos huellas del mismo formato.

    Se recorre la **unión** de las claves, no la intersección: si sólo se miraran
    las filas presentes en los dos lados, una obra que se cae entera pasaría por
    «sin diferencias», que es justo el fallo que hay que cazar.
    """
    por_antes = {f.clave: f for f in antes}
    por_despues = {f.clave: f for f in despues}

    diferencias: list[DiferenciaAmpliada] = []
    for clave in sorted(set(por_antes) | set(por_despues)):
        a = por_antes.get(clave)
        d = por_despues.get(clave)
        codigo = (a or d).codigo_obra  # type: ignore[union-attr]
        valores_a = a.como_dict if a else {}
        valores_d = d.como_dict if d else {}

        for campo in formato.columnas_valor:
            valor_a = valores_a.get(campo, SIN_FILA)
            valor_d = valores_d.get(campo, SIN_FILA)
            if valor_a != valor_d:
                diferencias.append(
                    DiferenciaAmpliada(
                        codigo_obra=codigo,
                        clave=clave,
                        campo=campo,
                        antes=valor_a,
                        despues=valor_d,
                    )
                )

    return ComparacionAmpliada(
        formato=formato,
        diferencias=tuple(diferencias),
        filas_antes=len(por_antes),
        filas_despues=len(por_despues),
    )


def veredicto_ampliado(
    comparacion: ComparacionAmpliada, obras_esperadas: Sequence[str]
) -> tuple[int, str]:
    """`(codigo, informe)`. Código distinto de 0 = **la feature no se cierra**.

    **Tolerancia cero, y es literal.** Cualquier diferencia en una obra que no
    esté en `obras_esperadas` detiene la feature: no hay umbral, ni porcentaje,
    ni redondeo. Es lo que el humano puso a cambio de eximir la mutación.

    Dos motivos de fallo:

    1. **Se mueve una obra fuera de la lista.** El corazón de la prueba.
    2. **Las dos huellas están vacías.** Entonces el cero no mide nada, y un
       verde sería una mentira cómoda.

    Lo que un verde **no** demuestra: que las obras esperadas se hayan movido, ni
    que se hayan movido en lo previsto. Eso es un contraste contra cifras
    externas y se hace a mano (R7 a R10).
    """
    esperadas = {str(c).strip() for c in obras_esperadas if str(c).strip()}
    fuera = sorted(
        {d.codigo_obra for d in comparacion.diferencias if d.codigo_obra not in esperadas}
    )
    dentro = sorted(
        {d.codigo_obra for d in comparacion.diferencias if d.codigo_obra in esperadas}
    )

    lineas = [
        f"Huella `{comparacion.formato.nombre}` — "
        f"{comparacion.formato.proposito}.",
        f"ANTES: {comparacion.filas_antes} fila(s). "
        f"DESPUES: {comparacion.filas_despues}. "
        f"Diferencias: {len(comparacion.diferencias)}.",
        "",
        _bloque_diferencias(comparacion),
        "",
    ]

    codigo = 0
    if comparacion.filas_antes == 0 and comparacion.filas_despues == 0:
        codigo = 1
        lineas.append(
            "KO   las dos huellas estan vacias: esto no compara nada. Un cero "
            "aqui es indistinguible de un cero sobre el datamart entero, y solo "
            "uno de los dos prueba algo"
        )
    if fuera:
        codigo = 1
        lineas.append(
            f"KO   se mueven {len(fuera)} obra(s) FUERA de la lista esperada: "
            f"{', '.join(fuera)}. Tolerancia CERO: la feature se detiene y se "
            f"consulta al humano"
        )
    if codigo == 0:
        movidas = ", ".join(dentro) or "ninguna"
        lineas.append(
            f"OK   solo se mueven las obras previstas ({movidas}); el resto, ni "
            f"una celda. No prueba que las previstas se hayan movido BIEN: eso "
            f"se contrasta contra las cifras de R7 a R10"
        )

    return codigo, "\n".join(lineas)


def _bloque_diferencias(comparacion: ComparacionAmpliada) -> str:
    """La lista ENTERA: un `LIMIT` en un informe de no-regresión es una forma
    elegante de no mirar."""
    if not comparacion.diferencias:
        return "Diferencias: ninguna."
    lineas = [f"Diferencias: {len(comparacion.diferencias)}."]
    lineas += [
        f"  {d.codigo_obra} · {' / '.join(d.clave)} · {d.campo}: "
        f"{d.antes} -> {d.despues}"
        for d in comparacion.diferencias
    ]
    return "\n".join(lineas)
