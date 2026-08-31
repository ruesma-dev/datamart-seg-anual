# etl_sigrid/domain/huella.py
"""
F-042 · La huella antes/después: comparación y veredicto (R22 a R25).

**La prueba que decide.** Lo fijó el humano el 2026-08-29 y manda sobre
cualquier otra forma de verificar: «hay que probar que el mensual y el acumulado
de las obras no afectadas no cambie», «con el mismo raw», «en los 4 ámbitos para
estar seguro».

Para un cambio que reescribe datos, la garantía pertinente no es «mis tests
detectan cambios en el código» sino **«no cambian datos que no deberían
cambiar»**. Por eso esta comparación sustituye a la campaña de mutación, que el
humano retiró en la misma petición.

## Qué se compara

Una celda es (obra, ámbito, mes) y lleva cuatro cosas: cuántas filas la
componen, **qué fases** (`versiones`) la componen, el **movimiento del mes** y el
**acumulado a origen**. Las dos últimas son dos historias distintas: el acumulado
es lo que está doblado y el mensual es lo que un desplazamiento mal hecho
rompería. Confundirlas en un solo número escondería justo el defecto que la
renumeración evita.

`versiones` es lo que hace observable la parte (a) de R23 —«las obras cuya
numeración de fase cambia»—: como `version` publica el número original de Sigrid
(R7), un cierre descartado desaparece de esa lista y se ve. El orden interno
renumerado no se publica en ninguna columna y, por definición, no se puede mirar
desde fuera: lo que sí se ve es su efecto en `importe_mes`.

Capa **domain**: funciones puras, sin BBDD ni ficheros. Leer la base y escribir
el CSV es `infrastructure/postgres/huella_obras.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

#: Los cuatro ámbitos: 3 Coste Real, 7 Venta Real, 8 Master Coste, 11 Master
#: Venta. El humano los pidió los cuatro **para estar seguro**, y los dos master
#: son la mejor prueba de que el arreglo no se desborda: hoy no tienen ni una
#: clave duplicada, así que su resultado esperado es cero cambios.
AMBITOS_DE_LA_HUELLA = (3, 7, 8, 11)

#: Los campos de importe que se comparan, en el orden en que se informan.
CAMPOS_DE_IMPORTE = ("importe_mes", "importe_origen")


@dataclass(frozen=True, slots=True)
class FilaHuella:
    """Una celda de la huella: (obra, ámbito, mes) con lo que hay dentro."""

    obra_id: int
    codigo_obra: str
    ambito_id: int
    periodo: date
    filas: int
    #: Las fases presentes en esa celda, separadas por `|` y ordenadas. Vacío
    #: cuando la huella viene de `mart`, que no publica el número de fase.
    versiones: str
    importe_mes: Decimal
    importe_origen: Decimal
    #: La categoría de coste (CD, CI, CP, OTRO) en la huella de `mart`, y cadena
    #: **vacía** en la de `stg`, que no baja a ese grano (F-052, T27). Entra en
    #: la clave: sin ella una partida **recategorizada** —una CI que pasa a CD—
    #: es invisible, porque el total de la obra no se mueve y sólo cambia el
    #: desglose, que es justo lo que rompe un informe de Power BI.
    categoria: str = ""

    @property
    def clave(self) -> tuple[int, int, date, str]:
        return (self.obra_id, self.ambito_id, self.periodo, self.categoria)


@dataclass(frozen=True, slots=True)
class CambioDeNumeracion:
    obra_id: int
    codigo_obra: str
    ambito_id: int
    periodo: date
    antes: str
    despues: str
    categoria: str = ""


@dataclass(frozen=True, slots=True)
class CambioDeImporte:
    obra_id: int
    codigo_obra: str
    ambito_id: int
    periodo: date
    campo: str
    antes: Decimal
    despues: Decimal
    categoria: str = ""

    @property
    def diferencia(self) -> Decimal:
        return self.despues - self.antes


@dataclass(frozen=True, slots=True)
class Comparacion:
    """Las dos listas COMPLETAS de R23, más lo que hace falta para leerlas.

    `celdas_antes` y `celdas_despues` van aquí porque un «0 diferencias» sobre
    dos huellas vacías es indistinguible de un «0 diferencias» sobre 11.883
    celdas, y solo uno de los dos prueba algo.
    """

    numeracion: tuple[CambioDeNumeracion, ...]
    importes: tuple[CambioDeImporte, ...]
    celdas_antes: int
    celdas_despues: int
    #: Los ámbitos presentes en alguna de las dos huellas, ordenados.
    ambitos: tuple[int, ...]


#: El valor de una celda que no existe en uno de los dos lados. Cero, y no
#: «se salta»: una celda que aparece o desaparece ES un cambio, y de los gordos
#: —el patrón 2 de estas obras hace desaparecer meses enteros—.
_VACIA = Decimal(0)


def comparar_huellas(
    antes: Iterable[FilaHuella], despues: Iterable[FilaHuella]
) -> Comparacion:
    """Las dos listas completas de cambios entre dos huellas.

    Se recorre la **unión** de las claves, no la intersección: si solo se miraran
    las celdas que están en los dos lados, un mes que desaparece pasaría por
    «sin diferencias», que es exactamente el fallo que hay que cazar.
    """
    por_clave_antes = {f.clave: f for f in antes}
    por_clave_despues = {f.clave: f for f in despues}

    numeracion: list[CambioDeNumeracion] = []
    importes: list[CambioDeImporte] = []

    for clave in sorted(set(por_clave_antes) | set(por_clave_despues)):
        a = por_clave_antes.get(clave)
        d = por_clave_despues.get(clave)
        obra_id, ambito_id, periodo, categoria = clave
        codigo = (a or d).codigo_obra  # type: ignore[union-attr]

        versiones_antes = a.versiones if a else ""
        versiones_despues = d.versiones if d else ""
        if versiones_antes != versiones_despues:
            numeracion.append(
                CambioDeNumeracion(
                    obra_id=obra_id,
                    codigo_obra=codigo,
                    ambito_id=ambito_id,
                    periodo=periodo,
                    antes=versiones_antes,
                    despues=versiones_despues,
                    categoria=categoria,
                )
            )

        for campo in CAMPOS_DE_IMPORTE:
            valor_antes = getattr(a, campo) if a else _VACIA
            valor_despues = getattr(d, campo) if d else _VACIA
            if valor_antes != valor_despues:
                importes.append(
                    CambioDeImporte(
                        obra_id=obra_id,
                        codigo_obra=codigo,
                        ambito_id=ambito_id,
                        periodo=periodo,
                        campo=campo,
                        antes=valor_antes,
                        despues=valor_despues,
                        categoria=categoria,
                    )
                )

    ambitos = sorted(
        {f.ambito_id for f in por_clave_antes.values()}
        | {f.ambito_id for f in por_clave_despues.values()}
    )

    return Comparacion(
        numeracion=tuple(numeracion),
        importes=tuple(importes),
        celdas_antes=len(por_clave_antes),
        celdas_despues=len(por_clave_despues),
        ambitos=tuple(ambitos),
    )


def veredicto(
    comparacion: Comparacion, obras_esperadas: Sequence[str]
) -> tuple[int, str]:
    """`(codigo, informe)`. Código distinto de 0 = **la feature no se cierra**.

    **QUÉ DEMUESTRA Y QUÉ NO, porque no es lo mismo.** Demuestra el «**y solo**»:
    que ninguna obra fuera de la lista se mueve y que los master no se mueven.
    **No** demuestra que las obras esperadas **sí** se hayan movido ni que se
    hayan movido **en lo previsto por R14**: eso es un contraste contra cifras
    externas y se hace a mano (T17). Un verde aquí con las 9 obras quietas sería
    un verde: correcto y vacío.

    Tres motivos de fallo, y son tres cosas distintas:

    1. **Se mueve una obra que no está en `obras_esperadas`** (R25). Es el
       corazón de la prueba: el arreglo tiene que tocar a las nueve obras y a
       ninguna más.
    2. **Se mueve algo en los ámbitos 8 u 11** (R24). Un cambio ahí es un
       desbordamiento. **Ojo con cuánto vale este cero cuando la huella del
       «después» viene de `--propuesta`:** ahí esas filas se **copian** de la
       actual, así que el cero es cierto por construcción y no es una medición.
       La garantía real de que los master no se mueven es que **su rama del SQL
       es byte a byte la misma**, fijada por hash en `tests/test_f042_sql.py`.
       Cuando el «después» sale de una reconstrucción de verdad, entonces sí
       mide.
    3. **La huella no trae los cuatro ámbitos.** Entonces no prueba lo que dice
       probar, y un verde sería una mentira cómoda.

    El informe lleva **la lista entera**, no una muestra: el humano pidió «la
    lista completa», y un `LIMIT` en un informe de no-regresión es una forma
    elegante de no mirar.
    """
    esperadas = {str(c).strip() for c in obras_esperadas if str(c).strip()}
    faltan = [a for a in AMBITOS_DE_LA_HUELLA if a not in comparacion.ambitos]

    fuera_de_lista = sorted(
        {
            c.codigo_obra
            for c in (*comparacion.numeracion, *comparacion.importes)
            if c.codigo_obra not in esperadas
        }
    )
    desbordes = [
        c
        for c in (*comparacion.numeracion, *comparacion.importes)
        if c.ambito_id in (8, 11)
    ]

    lineas = [
        f"Huella ANTES: {comparacion.celdas_antes} celda(s). "
        f"DESPUES: {comparacion.celdas_despues}. "
        f"Ambitos presentes: {', '.join(map(str, comparacion.ambitos)) or 'ninguno'}.",
        "",
        _bloque_numeracion(comparacion),
        "",
        _bloque_importes(comparacion),
        "",
        _bloque_master(desbordes),
        "",
    ]

    codigo = 0
    if faltan:
        codigo = 1
        lineas.append(
            f"KO   la huella NO trae los ambitos {', '.join(map(str, faltan))}: "
            f"la prueba tenia que cubrir los cuatro (3, 7, 8 y 11) y cubre "
            f"{len(comparacion.ambitos)}. Sin ellos no se puede afirmar que el "
            f"arreglo no se desborda"
        )
    if desbordes:
        codigo = 1
        lineas.append(
            f"KO   {len(desbordes)} cambio(s) en los ambitos MASTER (8, 11), que "
            f"no se tocan: la rama que los produce esta fijada por hash y hoy no "
            f"tienen ni una clave duplicada. El arreglo se ha salido de su sitio"
        )
    if fuera_de_lista:
        codigo = 1
        lineas.append(
            f"KO   se mueven {len(fuera_de_lista)} obra(s) FUERA de la lista "
            f"esperada: {', '.join(fuera_de_lista)}. La feature no se cierra"
        )
    if codigo == 0:
        lineas.append(
            "OK   cambian exactamente las obras previstas y solo en lo previsto; "
            "el resto, ni un centimo. Los ambitos 8 y 11, con cero cambios"
        )

    return codigo, "\n".join(lineas)


def _categoria(cambio) -> str:
    """` · categoria CD` cuando la huella baja a ese grano, y nada cuando no.

    La huella de `stg` no trae categoría, y escribir un ` · categoria ` vacío en
    todas sus líneas sería ruido en el informe que más se lee de esta feature.
    """
    return f" · categoria {cambio.categoria}" if cambio.categoria else ""


def _bloque_numeracion(comparacion: Comparacion) -> str:
    if not comparacion.numeracion:
        return "Numeracion de fase: 0 cambios."
    lineas = [f"Numeracion de fase: {len(comparacion.numeracion)} cambio(s)."]
    lineas += [
        f"  {c.codigo_obra} (obra {c.obra_id}) · ambito {c.ambito_id}"
        f"{_categoria(c)} · "
        f"{c.periodo:%Y-%m}: [{c.antes or 'ninguna'}] -> [{c.despues or 'ninguna'}]"
        for c in comparacion.numeracion
    ]
    return "\n".join(lineas)


def _bloque_importes(comparacion: Comparacion) -> str:
    if not comparacion.importes:
        return "Importes: 0 cambios."
    total = sum(c.diferencia for c in comparacion.importes if c.campo == "importe_origen")
    lineas = [
        f"Importes: {len(comparacion.importes)} cambio(s). "
        f"Variacion neta del acumulado a origen: {total}."
    ]
    lineas += [
        f"  {c.codigo_obra} (obra {c.obra_id}) · ambito {c.ambito_id}"
        f"{_categoria(c)} · "
        f"{c.periodo:%Y-%m} · {c.campo}: {c.antes} -> {c.despues} "
        f"({c.diferencia:+})"
        for c in comparacion.importes
    ]
    return "\n".join(lineas)


def _bloque_master(desbordes: Sequence[object]) -> str:
    """Se imprime SIEMPRE, también en verde: es la frase que el humano pidió
    poder leer sin interpretarla."""
    if not desbordes:
        return "Ambitos master 8 y 11: 0 cambios, que es el resultado esperado."
    return f"Ambitos master 8 y 11: {len(desbordes)} cambio(s). NO deberia haber ninguno."
