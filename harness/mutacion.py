# harness/mutacion.py
"""Mutador mínimo del arnés: comprueba que los tests son de verdad.

Muta ÚNICAMENTE las líneas de producción que toca una feature (el alcance lo
calcula `harness.alcance` desde el diff de git), ejecuta la suite por cada
mutante y cuenta cuántos sobreviven. Un mutante superviviente es una línea que
ningún test comprueba de verdad.

Tres garantías que sostienen los números que imprime (1.5.3):

1. **Línea base.** Antes de juzgar a nadie, la suite corre SIN mutar nada, en
   el mismo sitio y con el mismo intérprete con que se va a juzgar. Si no está
   verde, la campaña se aborta: sobre una base roja todo mutante sale «muerto»
   y el cero de supervivientes es mentira. Pasó de verdad el 2026-08-19.
2. **El veredicto no es binario.** Una suite que se rompe por su cuenta —error
   de recolección, error interno, mal uso— no dice nada del mutante. Se
   comprueba la base ahí mismo y, si está rota, el mutante NO cuenta como
   muerto.
3. **Restauración a prueba de muerte.** `try/finally`, manejador de SIGINT y
   SIGTERM, y un centinela en disco que deja escrito qué mutante está aplicado
   ahora mismo, para que un `kill` a machetazos deje rastro en vez de un
   mutante disfrazado de código.

Todo con biblioteca estándar (`ast` + `subprocess`): la herramienta tiene que
poder instalarse tal cual en cualquier repositorio, incluido Windows.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from pathlib import Path

from harness.alcance import (
    ORIGEN_FICHEROS,
    RAMA_BASE_POR_DEFECTO,
    Alcance,
    alcance_de_feature,
    alcance_de_ficheros,
    rama_base_configurada,
)
from harness.mapa_tests import (
    PODAR,
    SUBCONJUNTO,
    SUITE,
    Degradado,
    MapaTests,
    clasificar,
    contextos_de,
    lineas_de_sentencia,
)
from harness.mapa_tests import medir as medir_mapa_de_tests
from harness.rigor import (
    CONTROL_FRACCION,
    CONTROL_MINIMO,
    ORIGEN_ORDEN,
    RUTA_RIGOR,
    CapaLocalInvalida,
    ReglaMuestreo,
    cargar_features,
    cargar_rigor,
    control_incremental,
    ficheros_no_versionados,
    max_mutantes_nivel,
    nivel_de_feature,
    regla_nivel,
    semilla_nivel,
    timeout_mutacion,
    seleccion_de_tests,
    workers_mutacion,
)
from harness.servicios import Servicio, cargar_servicios, interprete, servicio_de_ruta
from harness.tiempos import VARIABLE_FACTOR

Posicion = tuple[int, int]

#: Veredictos posibles de la suite frente a un mutante.
MUERTO = "muerto"
SUPERVIVIENTE = "superviviente"
TIMEOUT = "timeout"

#: La suite no llegó a juzgar: no compila, se rompió la recolección, error
#: interno, mal uso o ningún test recogido (código 5). `ejecutar_campania`
#: comprueba la línea base ahí mismo: rota, sale `BASE_ROTA`; utilizable, se
#: queda `INDETERMINADO` (F-023: antes salía `MUERTO`). Ni muerto ni
#: superviviente: no invalida la campaña y consta con su código en el informe.
INDETERMINADO = "indeterminado"

#: Códigos de salida simbólicos de un mutante no muerto (F-023). Texto y no
#: entero porque «no compila» y «timeout» no son códigos de pytest; `n/d` es el
#: de un ejecutor que solo sabe `ejecutar` (dobles, subclases de proyecto).
NO_COMPILA = "no compila"
CODIGO_TIMEOUT = "timeout"
CODIGO_ND = "n/d"

#: Código del superviviente PODADO (F-019, R8): ningún proceso medido ejecuta
#: su sentencia, así que ni se escribió ni se corrió ninguna suite.
SIN_EJECUTAR = "sin ejecutar"

#: Modos de la selección de tests en el informe (F-019, R25). `None` en el
#: campo es una campaña que no la conoce (dobles e informes de antes).
SELECCION_ACTIVA = "activa"
SELECCION_DEGRADADA = "degradada"
SELECCION_DESACTIVADA = "desactivada"

#: Mutante juzgado sobre una base que ya estaba rota. No cuenta como muerto ni
#: como superviviente: no se sabe nada de él, y decir «muerto» era el defecto
#: que la 1.5.3 arregla.
BASE_ROTA = "base_rota"

#: SUELO de segundos por mutante si nadie configura otra cosa. Suelo y no
#: techo: el timeout efectivo se deriva de la línea base medida (R1/R7).
TIMEOUT_POR_DEFECTO = 120

#: Rama de integración de ÚLTIMO RECURSO: la de verdad es `RAMA_BASE` de
#: `harness/init.sh`, que `main` lee cuando no se pasa `--base` (1.7.14).
#: `comando_de` omite `--base` solo cuando coincide con esta: si el proyecto
#: integra en otra rama, el comando la escribe y se puede reproducir en
#: cualquier sitio sin depender de su `init.sh`.
BASE_POR_DEFECTO = RAMA_BASE_POR_DEFECTO

#: Cuánto se multiplica el peor tiempo de línea base MEDIDO para obtener el
#: timeout de un mutante. Va en el código y no en `rigor.json` a propósito
#: (decisión del humano del 2026-08-21): es un parámetro del mecanismo, no de la
#: máquina, y meterlo en configuración reabre la puerta a cablear valores
#: locales en un arnés que viaja a cinco proyectos.
#:
#: Dos, no diez: el margen tiene que absorber el ruido de una suite que ya se
#: midió con los W workers compitiendo, no tapar un mutante que cuelga.
MARGEN_TIMEOUT = 2.0

#: Por cuánto se multiplica el suelo para darle su timeout a la LÍNEA BASE.
#: Huevo y gallina: la base necesita un reloj para poder medirse, y no puede
#: usar uno derivado de sí misma. Se le da uno holgado y aparte, y es defendible
#: porque se paga **una vez por worker**, no una por mutante. Si ni con 10
#: minutos cabe la suite limpia, el problema ya no es el reloj.
FACTOR_HOLGURA_BASE = 5

#: Tope del número de workers CALCULADO por defecto. No limita lo que se pida a
#: mano con `--workers` ni lo declarado en `rigor.json` (R10).
#:
#: Fue 16 hasta que alguien lo midió, y ese 16 hacía la campaña paralela
#: inutilizable por defecto: el 2026-08-21, en una máquina de 22 núcleos, la
#: suite limpia tardó 51 s en reposo, 97,5 s con UN worker y 119-122 s con
#: TRES, contra un timeout configurado de 120 s. Con 16 no habría cabido ni
#: una línea base.
#:
#: El único punto medido y verde son 3 workers, y ya ahí la suite sube un 25 %.
#: 4 es un paso sobre lo medido, no un salto; subirlo es una decisión CON
#: DATOS, y `--workers N` sigue sin límite para quien quiera producirlos.
TOPE_WORKERS = 4

#: Códigos de salida de pytest que este módulo distingue. Solo el 1 —«han
#: fallado tests»— significa que el mutante pudo ser cazado; el 2 (recolección
#: interrumpida), el 3 (error interno) y el 4 (mal uso) significan que la suite
#: ni siquiera llegó a juzgar, y contarlos como muerte era parte del defecto.
PYTEST_OK = 0
PYTEST_FALLOS = 1

#: Código con el que pytest avisa de que no ha recogido NINGÚN test. No es un
#: fallo de la suite: es que no hay suite. Contarlo como mutante muerto daría
#: por cazado lo que nadie comprueba, justo lo que esta herramienta destapa.
PYTEST_SIN_TESTS = 5

#: Argumentos con los que se corre la LÍNEA BASE (la suite sin mutar nada).
#: Sin `-x` a propósito: el mensaje de aborto tiene que nombrar TODOS los tests
#: que fallan, no solo el primero, o arreglar la base es un juego de adivinar.
#: `-rfE` fuerza el resumen «FAILED ...» y «ERROR ...» aunque `--tb=no` calle
#: las trazas. La `E` no sobra: una suite que muere en la RECOLECCIÓN no tiene
#: ni un FAILED que enseñar, y ése es justo el caso más frecuente en modo serie
#: —pytest invocado sin ruta sobre una raíz sin configuración—. Sin ella el
#: aborto decía «código 2» a secas y mandaba a adivinar.
ARGUMENTOS_LINEA_BASE: tuple[str, ...] = (
    "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider",
)

#: Fichero donde una campaña en curso deja escrito qué mutante tiene aplicado.
#: Vive bajo `.arnes_cache/`, que el bloque gestionado del `.gitignore` ya
#: ignora: es estado de una ejecución, no algo que se versione.
RUTA_CENTINELA = Path(".arnes_cache/mutacion_en_curso.json")

#: Líneas del resumen de pytest que nombran un test caído.
_LINEA_FALLIDA = re.compile(r"^(?:FAILED|ERROR)\s+(\S+)", re.MULTILINE)

#: Con qué empiezan las líneas de eco de la línea base. La campaña paralela las
#: reconoce por aquí para NO contarlas en su `[i/n]` de progreso.
MARCA_LINEA_BASE = "[base] "

#: (símbolo original, símbolo mutado) por tipo de nodo del árbol sintáctico.
#:
#: `is` / `is not` entran aquí porque en Python son LA guarda de ausencia
#: (`x is None`), y sin ellas la campaña quedaba ciega justo en el patrón que
#: ha provocado los defectos más caros. Límite conocido y aceptado: la
#: sustitución busca la cadena literal, así que un `is  not` con espaciado no
#: canónico —o partido entre dos líneas— NO genera mutante (no falla:
#: simplemente no hay candidato). En un repositorio formateado con ruff/black
#: ese espaciado no existe, y sostener una expresión regular por él obligaría a
#: cambiar el contrato de `_Candidato` a cambio de nada.
COMPARACIONES: dict[type, tuple[str, str]] = {
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
    ast.Is: ("is", "is not"),
    ast.IsNot: ("is not", "is"),
    ast.In: ("in", "not in"),
    ast.NotIn: ("not in", "in"),
}
ARITMETICOS: dict[type, tuple[str, str]] = {
    ast.Add: ("+", "-"),
    ast.Sub: ("-", "+"),
    ast.Mult: ("*", "//"),
    ast.FloorDiv: ("//", "*"),
    ast.Div: ("/", "*"),
}
#: Nombres de función que el operador `minmax` intercambia.
MINMAX: dict[str, str] = {"min": "max", "max": "min"}

#: Operadores de F-026, y su límite. Todos usan el mismo molde que los de
#: arriba: un tramo de UNA línea, buscado por texto. Lo que ocupa más de una
#: línea no da mutante (no falla), como el `is  not` partido de `COMPARACIONES`.
#:
#: - `comparacion`: además `in` ↔ `not in`. Delimitado como palabra: el `in` de
#:   `inicio` no casa, y el de un `for x in xs` no es una comparación.
#: - `aritmetico`: además `/` → `*` (y `/=` → `*=`). Solo en ese sentido.
#: - `minmax`: `min` ↔ `max`, solo con el nombre desnudo; `np.min` no se toca.
#: - `negacion`: la condición de un `if`/`elif`/`while` → `not (…)`.
#: - `ternario`: la condición de `a if c else b` → `not (…)`.
#:   Ninguno de los dos niega lo que ya invierte otro operador (`_condicion_negable`).
#: - `veracidad`: `x is not None` → `x` y `x is None` → `not x`, con `x` nombre o
#:   atributo; además del de `comparacion`, no en su lugar.
#: - `formato`: el ancho + 1 de la especificación literal de un campo de
#:   f-string (`{n:03d}` → `{n:04d}`). Sin ancho, o anidada (`{n:{w}}`), nada.
#:   Se localiza por TEXTO: las posiciones de los nodos internos de una
#:   f-string solo son fiables desde Python 3.12. Dos campos con la misma
#:   especificación en la misma f-string dan un solo mutante (el primero).

#: Comparaciones de un solo operador que `comparacion` ya invierte: negar la
#: condición entera sería el mismo cambio dos veces (R6).
_YA_INVERTIDAS = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn)

#: Nodos que se niegan sin paréntesis: `not x`, `not x.y`, `not f()`, `not x[0]`.
_SIN_PARENTESIS = (ast.Name, ast.Attribute, ast.Call, ast.Subscript)

#: Especificación de formato con ancho: `[[relleno]alineación][signo][z][#][0]`
#: y el ANCHO, que es lo que se muta. Lo demás (agrupación, precisión, tipo)
#: va en `resto` y no se toca.
_ANCHO = re.compile(r"^(?P<pre>(?:.?[<>=^])?[+\- ]?z?#?0?)(?P<ancho>\d+)(?P<resto>.*)$")
LOGICOS: dict[type, tuple[str, str]] = {
    ast.And: ("and", "or"),
    ast.Or: ("or", "and"),
}


@dataclass(frozen=True)
class Mutante:
    """Un solo cambio en una sola línea de un solo fichero."""

    fichero: str
    linea: int
    col: int
    original: str
    mutado: str
    operador: str
    longitud: int = 0
    sustituto: str = ""

    def descripcion(self) -> str:
        return f"{self.fichero}:{self.linea} [{self.operador}] {self.original} -> {self.mutado}"


@dataclass(frozen=True)
class _Candidato:
    """Sitio del código donde se puede aplicar una mutación."""

    ini: Posicion
    fin: Posicion
    buscar: str
    nuevo: str
    operador: str
    hasta: Posicion | None = None


def _inicio(nodo: ast.AST) -> Posicion:
    return (nodo.lineno, nodo.col_offset)  # type: ignore[attr-defined]


def _final(nodo: ast.AST) -> Posicion:
    return (nodo.end_lineno, nodo.end_col_offset)  # type: ignore[attr-defined]


def _texto_del_span(brutas: list[str], ini: Posicion, fin: Posicion) -> str:
    """Devuelve el texto exacto entre dos posiciones de una misma línea."""
    if ini[0] != fin[0]:
        return ""
    return brutas[ini[0] - 1].encode("utf-8")[ini[1] : fin[1]].decode("utf-8", "replace")


def _tras_la_palabra(brutas: list[str], ini: Posicion, largo: int) -> Posicion:
    """Columna (en bytes) tras una palabra de `largo` bytes y sus blancos.

    Solo cuenta el espacio y el tabulador de la MISMA línea: si el operando
    arranca en la siguiente, lo que queda tras la palabra es el fin de línea.
    """
    bruta = brutas[ini[0] - 1].encode("utf-8")
    col = ini[1] + largo
    while col < len(bruta) and bruta[col : col + 1] in (b" ", b"\t"):
        col += 1
    return (ini[0], col)


def _condicion_negable(test: ast.expr) -> bool:
    """¿Negar esta condición es un cambio que ningún otro operador hace ya? (R6)"""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return False  # lo quita el operador `not`
    if isinstance(test, ast.Constant):
        return False  # `booleano` o `entero`, y `while True` negado es un cuelgue
    return not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], _YA_INVERTIDAS)
    )


def _negar(texto: str, test: ast.expr) -> str:
    """`not <texto>`, con paréntesis salvo que no hagan falta (R7)."""
    if isinstance(test, _SIN_PARENTESIS):
        return f"not {texto}"
    return f"not ({texto})"


def _negacion(test: ast.expr, brutas: list[str], operador: str) -> Iterator[_Candidato]:
    """El candidato que niega `test` entero, si es negable y cabe en una línea."""
    if not _condicion_negable(test):
        return
    texto = _texto_del_span(brutas, _inicio(test), _final(test))
    if texto:
        yield _Candidato(_inicio(test), _final(test), texto, _negar(texto, test), operador)


def _veracidad(nodo: ast.Compare, brutas: list[str]) -> Iterator[_Candidato]:
    """`x is not None` → `x` y `x is None` → `not x`, con `x` nombre o atributo (R9)."""
    if not (
        len(nodo.ops) == 1
        and isinstance(nodo.ops[0], (ast.Is, ast.IsNot))
        and isinstance(nodo.left, (ast.Name, ast.Attribute))
        and isinstance(nodo.comparators[0], ast.Constant)
        and nodo.comparators[0].value is None
    ):
        return
    texto = _texto_del_span(brutas, _inicio(nodo), _final(nodo))
    izquierda = _texto_del_span(brutas, _inicio(nodo.left), _final(nodo.left))
    if texto and izquierda:
        nuevo = izquierda if isinstance(nodo.ops[0], ast.IsNot) else f"not {izquierda}"
        yield _Candidato(_inicio(nodo), _final(nodo), texto, nuevo, "veracidad")


def _formato(nodo: ast.JoinedStr) -> Iterator[_Candidato]:
    """Ancho + 1 de cada especificación literal con ancho de una f-string (R8)."""
    if nodo.lineno != nodo.end_lineno:
        return
    for valor in nodo.values:
        if not isinstance(valor, ast.FormattedValue):
            continue
        especificacion = valor.format_spec
        if not (
            isinstance(especificacion, ast.JoinedStr)
            and len(especificacion.values) == 1
            and isinstance(especificacion.values[0], ast.Constant)
            and isinstance(especificacion.values[0].value, str)
        ):
            continue
        texto = especificacion.values[0].value
        casa = _ANCHO.match(texto)
        if casa is None:
            continue
        mutado = f"{casa['pre']}{int(casa['ancho']) + 1}{casa['resto']}"
        yield _Candidato(
            _inicio(nodo), _final(nodo), f":{texto}}}", f":{mutado}}}", "formato"
        )


def _candidatos(nodo: ast.AST, brutas: list[str]) -> Iterator[_Candidato]:
    """Enumera las mutaciones aplicables a un nodo del árbol sintáctico."""
    if isinstance(nodo, ast.Compare):
        izquierdas = [nodo.left, *nodo.comparators[:-1]]
        for operador, izquierda, derecha in zip(
            nodo.ops, izquierdas, nodo.comparators, strict=True
        ):
            simbolos = COMPARACIONES.get(type(operador))
            if simbolos:
                yield _Candidato(
                    _final(izquierda), _inicio(derecha), *simbolos, "comparacion"
                )
        yield from _veracidad(nodo, brutas)

    elif isinstance(nodo, (ast.If, ast.While)):
        yield from _negacion(nodo.test, brutas, "negacion")

    elif isinstance(nodo, ast.IfExp):
        yield from _negacion(nodo.test, brutas, "ternario")

    elif isinstance(nodo, ast.JoinedStr):
        yield from _formato(nodo)

    elif isinstance(nodo, ast.BinOp):
        simbolos = ARITMETICOS.get(type(nodo.op))
        if simbolos:
            yield _Candidato(
                _final(nodo.left), _inicio(nodo.right), *simbolos, "aritmetico"
            )

    elif isinstance(nodo, ast.AugAssign):
        simbolos = ARITMETICOS.get(type(nodo.op))
        if simbolos:
            yield _Candidato(
                _final(nodo.target), _inicio(nodo.value), *simbolos, "aritmetico"
            )

    elif isinstance(nodo, ast.BoolOp):
        simbolos = LOGICOS.get(type(nodo.op))
        if simbolos:
            for izquierda, derecha in zip(nodo.values, nodo.values[1:], strict=False):
                yield _Candidato(_final(izquierda), _inicio(derecha), *simbolos, "logico")

    elif isinstance(nodo, ast.UnaryOp) and isinstance(nodo.op, ast.Not):
        # Se elimina la palabra `not` y los blancos que la siguen, y NADA más.
        # Hasta F-026 se borraba hasta el inicio del operando, y el nodo de un
        # operando entre paréntesis empieza DENTRO del paréntesis: `if not (a
        # and b):` daba `if a and b):`, un mutante que no compila.
        yield _Candidato(
            _inicio(nodo),
            _inicio(nodo.operand),
            "not",
            "",
            "not",
            hasta=_tras_la_palabra(brutas, _inicio(nodo), len("not")),
        )

    elif isinstance(nodo, ast.Call):
        if isinstance(nodo.func, ast.Name) and nodo.func.id in MINMAX:
            yield _Candidato(
                _inicio(nodo.func),
                _final(nodo.func),
                nodo.func.id,
                MINMAX[nodo.func.id],
                "minmax",
            )

    elif isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, bool):  # `bool` es subclase de `int`: va primero
            texto = _texto_del_span(brutas, _inicio(nodo), _final(nodo))
            if texto in ("True", "False"):
                yield _Candidato(
                    _inicio(nodo),
                    _final(nodo),
                    texto,
                    "False" if texto == "True" else "True",
                    "booleano",
                )
        elif isinstance(nodo.value, int):
            texto = _texto_del_span(brutas, _inicio(nodo), _final(nodo))
            if texto:
                yield _Candidato(
                    _inicio(nodo), _final(nodo), texto, str(nodo.value + 1), "entero"
                )


#: Bytes que cuentan como «parte de una palabra» al delimitar un token
#: alfabético. Los >= 0x80 entran porque una letra acentuada de un comentario
#: ocupa dos bytes en UTF-8 y sigue siendo parte de la palabra.
_PARTE_DE_PALABRA = re.compile(rb"[A-Za-z0-9_\x80-\xff]")


def _es_palabra(objetivo: bytes) -> bool:
    """¿El token a buscar se escribe con letras (`is`, `is not`, `and`, `not`)?

    Solo estos se delimitan. Los símbolos (`==`, `+`, `<=`) NO: `x==y` es
    legal, el carácter anterior a `==` es una letra y exigirle delimitación
    dejaría de mutarlo.
    """
    return bool(
        objetivo
        and _PARTE_DE_PALABRA.match(objetivo[:1])
        and _PARTE_DE_PALABRA.match(objetivo[-1:])
    )


def _delimitado(bruta: bytes, ini: int, fin: int) -> bool:
    """¿La coincidencia `[ini, fin)` es un token entero y no parte de una palabra?

    `is` cabe dentro de «análisis», y el hueco entre los dos operandos de una
    comparación puede contener un comentario cuando la condición va entre
    paréntesis. Sin esta comprobación el mutante caía dentro del comentario:
    equivalente por construcción, superviviente eterno y ruido en el informe.
    """
    anterior = bruta[ini - 1 : ini] if ini > 0 else b""
    siguiente = bruta[fin : fin + 1]
    return not (_PARTE_DE_PALABRA.match(anterior) or _PARTE_DE_PALABRA.match(siguiente))


def _localizar(brutas: list[str], candidato: _Candidato) -> Posicion | None:
    """Encuentra el token a mutar dentro del hueco entre dos operandos.

    Devuelve `(línea, columna en bytes)` de la primera coincidencia **válida**:
    para un token alfabético, la primera que sea una palabra entera. Se busca
    línea a línea porque un token de operador nunca está partido entre dos
    líneas —y por eso un `is not` con salto de línea en medio no da mutante,
    límite declarado junto a `COMPARACIONES`—.
    """
    objetivo = candidato.buscar.encode("utf-8")
    if not objetivo:
        return None
    exigir_palabra = _es_palabra(objetivo)
    (linea_ini, col_ini), (linea_fin, col_fin) = candidato.ini, candidato.fin
    for numero in range(linea_ini, linea_fin + 1):
        if numero > len(brutas):
            break
        bruta = brutas[numero - 1].encode("utf-8")
        desde = col_ini if numero == linea_ini else 0
        hasta = col_fin if numero == linea_fin else len(bruta)
        posicion = bruta.find(objetivo, desde, hasta)
        while posicion != -1:
            if not exigir_palabra or _delimitado(
                bruta, posicion, posicion + len(objetivo)
            ):
                return (numero, posicion)
            posicion = bruta.find(objetivo, posicion + 1, hasta)
    return None


def generar_mutantes(fuente: str, lineas: set[int], fichero: str) -> list[Mutante]:
    """Genera un mutante por cada mutación posible en las líneas del alcance.

    Cada mutante es UN SOLO cambio. Las líneas fuera del alcance no se tocan:
    la herramienta nunca muta el repositorio entero.
    """
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return []

    brutas = fuente.split("\n")
    mutantes: list[Mutante] = []
    vistos: set[tuple[int, int, str]] = set()

    for nodo in ast.walk(arbol):
        for candidato in _candidatos(nodo, brutas):
            localizado = _localizar(brutas, candidato)
            if localizado is None:
                continue
            numero, col = localizado
            if numero not in lineas:
                continue
            if (numero, col, candidato.operador) in vistos:
                continue
            vistos.add((numero, col, candidato.operador))

            longitud = len(candidato.buscar.encode("utf-8"))
            if candidato.hasta is not None and candidato.hasta[0] == numero:
                longitud = max(longitud, candidato.hasta[1] - col)

            bruta = brutas[numero - 1].encode("utf-8")
            nueva = (
                bruta[:col] + candidato.nuevo.encode("utf-8") + bruta[col + longitud :]
            ).decode("utf-8", "replace")
            mutantes.append(
                Mutante(
                    fichero=fichero,
                    linea=numero,
                    col=col,
                    original=brutas[numero - 1].strip(),
                    mutado=nueva.strip(),
                    operador=candidato.operador,
                    longitud=longitud,
                    sustituto=candidato.nuevo,
                )
            )

    return sorted(mutantes, key=lambda m: (m.fichero, m.linea, m.col, m.operador))


def aplicar_mutante(fuente: str, mutante: Mutante) -> str:
    """Devuelve el fuente con el mutante aplicado (sin tocar el disco)."""
    brutas = fuente.split("\n")
    bruta = brutas[mutante.linea - 1].encode("utf-8")
    brutas[mutante.linea - 1] = (
        bruta[: mutante.col]
        + mutante.sustituto.encode("utf-8")
        + bruta[mutante.col + mutante.longitud :]
    ).decode("utf-8", "replace")
    return "\n".join(brutas)


# --- Selección de mutantes (F-058) ------------------------------------------


def clave_de_orden(mutante: Mutante) -> tuple[str, int, int, str]:
    """Orden con el que se entregan los mutantes sorteados: el de siempre."""
    return (mutante.fichero, mutante.linea, mutante.col, mutante.operador)


def reducir_por_linea(mutantes: list[Mutante], rng: random.Random) -> list[Mutante]:
    """Deja UN mutante por (fichero, línea), elegido con `rng` (R1).

    Si un mutante de una línea muere, los demás de esa línea suelen morir con
    él: evaluarlos todos cuesta suites enteras y casi no añade señal. Los grupos
    salen en el orden de la lista recibida, así que con una lista ordenada el
    resultado también lo está.
    """
    grupos: dict[tuple[str, int], list[Mutante]] = {}
    for mutante in mutantes:
        grupos.setdefault((mutante.fichero, mutante.linea), []).append(mutante)
    return [rng.choice(grupo) for grupo in grupos.values()]


def seleccionar(
    mutantes: list[Mutante], regla: ReglaMuestreo, semilla: int | None
) -> tuple[list[Mutante], int, int | None]:
    """Sede ÚNICA del sorteo, en serie y en paralelo: `(elegidos, C, tope)` (R8).

    Un solo `random.Random(semilla)`: primero reduce por línea si la regla lo
    pide y después, si los candidatos pasan del tope, sortea. Sin reducción la
    secuencia es idéntica a la de antes de F-058 (R26).
    """
    rng = random.Random(semilla)
    candidatos = reducir_por_linea(mutantes, rng) if regla.por_linea else list(mutantes)
    limite = regla.tope(len(candidatos))
    if limite is None or len(candidatos) <= limite:
        return (candidatos, len(candidatos), limite)
    return (
        sorted(rng.sample(candidatos, limite), key=clave_de_orden),
        len(candidatos),
        limite,
    )


# --- Ejecución de la suite --------------------------------------------------


def _leer(ruta: Path) -> str:
    """Lee preservando los saltos de línea tal cual están en disco."""
    with open(ruta, encoding="utf-8", newline="") as fichero:
        return fichero.read()


def _purgar_bytecode(ruta: Path) -> list[str]:
    """Borra el `.pyc` de `ruta`, si lo hay; devuelve lo que no pudo borrar.

    CPython da por válido un bytecode cuando el fuente conserva el mismo tamaño
    y el mismo mtime **truncado a segundos enteros**. Dos mutantes consecutivos
    del mismo fichero cumplen las dos cosas más veces de las que parece: se
    escriben en el mismo segundo y muchas mutaciones cambian el mismo número de
    bytes (`*`->`//` y `>`->`>=` añaden uno cada una). Cuando coinciden, la
    suite del segundo mutante ejecuta el bytecode del PRIMERO y su veredicto no
    dice nada del código que hay en disco.

    Medido aquí el 2026-08-19: la misma campaña sobre el mismo repositorio de
    juguete daba 3 supervivientes o 2 según el segundo en que cayera, y el que
    desaparecía salía contado como MUERTO. Es el mismo pecado que arregla esta
    versión —un muerto que nadie mató—, por otra puerta.

    Desde F-023 `EjecutorPytest` ya no depende de esta purga (corre con
    `PYTHONPYCACHEPREFIX` vacío), pero los ejecutores que no pasan por su
    `correr` sí. Por eso lo que no se pudo borrar ya no se traga: se devuelve
    como `"<ruta>: <error>"` y quien llama lo avisa (R14).
    """
    cache = ruta.parent / "__pycache__"
    if not cache.is_dir():
        return []
    restos: list[str] = []
    for compilado in cache.glob(f"{ruta.stem}.*.pyc"):
        try:
            compilado.unlink()
        except OSError as error:
            # Windows: otro proceso puede tenerlo abierto. No es fatal —perder
            # la campaña por una caché sería peor—, pero tampoco es silencio.
            restos.append(f"{compilado.as_posix()}: {error}")
    return restos


def _escribir(ruta: Path, texto: str) -> list[str]:
    """Escribe un fuente sin traducir saltos de línea, y tira su bytecode.

    Sin traducir, porque restaurar debe dejar el fichero idéntico. Y tirando el
    `.pyc`, porque lo que se escribe aquí se va a ejecutar acto seguido: ver
    `_purgar_bytecode`.
    """
    with open(ruta, "w", encoding="utf-8", newline="") as fichero:
        fichero.write(texto)
    return _purgar_bytecode(ruta)


@dataclass(frozen=True)
class ResultadoSuite:
    """Lo que devolvió una ejecución de la suite, sin interpretar todavía.

    Separar el HECHO (código de salida y salida de texto) de su INTERPRETACIÓN
    (¿mutante muerto?, ¿base rota?) es lo que permite que la misma ejecución
    sirva para juzgar un mutante y para juzgar la línea base.
    """

    codigo: int
    salida: str = ""
    expirado: bool = False

    @property
    def verde(self) -> bool:
        """¿La suite terminó con código 0? Sin tests que recoger NO es verde.

        Hasta F-023 el 5 contaba como verde y su mutante salía superviviente:
        «nadie recogió ningún test» no dice que nadie compruebe la línea, dice
        que la suite no juzgó. Para un mutante eso es `indeterminado`.
        """
        return not self.expirado and self.codigo == PYTEST_OK

    @property
    def base_utilizable(self) -> bool:
        """¿Vale como LÍNEA BASE? Verde o sin tests que recoger (R6 de F-023).

        Es la pregunta de quien juzga la base, no la de quien juzga un
        mutante: una base sin tests no está rota y la campaña no aborta.
        """
        return self.verde or self.sin_tests

    @property
    def sin_tests(self) -> bool:
        return not self.expirado and self.codigo == PYTEST_SIN_TESTS

    def fallidos(self) -> list[str]:
        """Tests que la suite nombra como caídos, en orden y sin repetir."""
        vistos: list[str] = []
        for nombre in _LINEA_FALLIDA.findall(self.salida):
            if nombre not in vistos:
                vistos.append(nombre)
        return vistos


class CampaniaAbortada(RuntimeError):
    """La campaña no puede dar un número honesto y para sin escribir informe.

    Abortar es la única salida decente: escribir un informe con un cero de
    supervivientes que nadie ha medido es peor que no medir, porque el reviewer
    lo da por bueno.
    """


class BaseRota(CampaniaAbortada):
    """La suite falla SIN mutar nada: ningún veredicto de esta campaña valdría."""


class ArbolSucio(CampaniaAbortada):
    """Hay trabajo sin commitear en ficheros que la campaña va a mutar."""


class FaltanFicheros(CampaniaAbortada):
    """Falta en el árbol principal un fichero no versionado que se declaró."""


def comprobar_ficheros_no_versionados(raiz: str, rutas: list[str]) -> None:
    """Aborta con `FaltanFicheros` nombrando CADA ruta declarada que no existe.

    R19 de F-023: se llama antes de elegir serie o paralelo y de tocar nada.
    Una ruta declarada es obligatoria, también el `.env` (que luego se vuelca
    como variables y no se copia): si el proyecto dice que la suite la
    necesita, medir sin ella daría una base roja o, peor, una verde por azar.
    """
    faltan = [ruta for ruta in rutas if not (Path(raiz) / ruta).exists()]
    if faltan:
        detalle = "\n".join(f"    - {ruta}" for ruta in faltan)
        raise FaltanFicheros(
            "FALTAN FICHEROS NO VERSIONADOS: 'mutacion.ficheros_no_versionados' "
            "declara rutas que no existen en el árbol principal. Campaña abortada "
            f"sin tocar nada:\n{detalle}\n"
            "  Créalas (son locales: git no las trae) o quítalas de la "
            "declaración en harness/rigor.local.json."
        )


#: Directorio de bytecode de cada raíz durante la campaña (R23 de F-023):
#: `{raíz resuelta: directorio vacío}`. Por raíz y no por ejecutor: hay un
#: ejecutor por fichero, y la base y los mutantes de una raíz comparten suite.
_PREFIJOS: dict[str, str] = {}
_CERROJO_PREFIJOS = threading.Lock()


def prefijo_pycache(raiz: str) -> str:
    """El `PYTHONPYCACHEPREFIX` de `raiz`: un directorio vacío, uno por raíz.

    Con él, CPython no lee NINGÚN `__pycache__` del árbol: ni el que dejó una
    campaña anterior ni el que una purga no pudo borrar. Y como la suite sigue
    corriendo con `PYTHONDONTWRITEBYTECODE=1`, el prefijo sigue vacío toda la
    campaña: no hay `.pyc` mutado que pueda darse por válido dentro de él.
    Cada worktree de la paralela es una raíz distinta y tiene el suyo.
    """
    clave = str(Path(raiz).resolve())
    with _CERROJO_PREFIJOS:
        if clave not in _PREFIJOS:
            _PREFIJOS[clave] = tempfile.mkdtemp(prefix="arnes-pycache-")
        return _PREFIJOS[clave]


#: Factor de timeout de los tests que la campaña en curso exporta a cada suite
#: que lanza (R23 de F-019): el número de workers. `None` fuera de una campaña.
#: Lo fija `_main` y lo retira `main` al salir; vive en el módulo y no en cada
#: ejecutor porque los ejecutores se fabrican fichero a fichero y en cada
#: worker, y todos tienen que exportar el mismo.
_FACTOR_TESTS: int | None = None


def fijar_factor_tests(workers: int | None) -> None:
    """Fija (o retira, con `None`) el factor que `EjecutorPytest.entorno` exporta."""
    global _FACTOR_TESTS
    _FACTOR_TESTS = None if workers is None else max(1, workers)


def retirar_prefijos() -> None:
    """Borra los directorios de `prefijo_pycache`; lo llama `main` al salir."""
    with _CERROJO_PREFIJOS:
        directorios = list(_PREFIJOS.values())
        _PREFIJOS.clear()
    for directorio in directorios:
        shutil.rmtree(directorio, ignore_errors=True)


class EjecutorPytest:
    """Lanza la suite en un proceso aparte y traduce el resultado.

    Que la suite falle CON tests caídos (código 1) significa que los tests cazan
    el mutante (muerto). Que pase (código 0) significa que el mutante sobrevive:
    nadie comprobaba esa línea. Y que pytest ni llegue a juzgar (recolección
    interrumpida, error interno, mal uso, ningún test recogido) no significa
    nada del mutante: eso sale como `INDETERMINADO` y quien llama comprueba la
    línea base para separarlo de `BASE_ROTA` (F-023: un solo criterio).

    `raiz` es el directorio desde el que se lanza la suite y `ejecutable`, el
    intérprete con el que se lanza. En un monorepo, los de cada servicio.

    `ruta` acota la RECOLECCIÓN dentro de esa raíz. Sin ella, `python -m pytest`
    a secas recoge todo lo que cuelgue del directorio: en un monorepo eso
    arrastra `services/**/tests` y muere en la recolección con el intérprete
    equivocado, así que ningún mutante llega a juzgarse (R1–R3). Es la
    misma ruta explícita que `harness/init.sh` usa para la suite de la raíz.
    """

    def __init__(
        self,
        raiz: str = ".",
        argumentos: list[str] | None = None,
        ejecutable: str | None = None,
        ruta: str | None = None,
    ) -> None:
        self.raiz = raiz
        self.argumentos = argumentos or ["-x", "-q", "--tb=no", "-p", "no:cacheprovider"]
        self.ejecutable = ejecutable or sys.executable
        self.ruta = ruta

    def identidad(self) -> tuple[str, str, str]:
        """Con qué intérprete, desde dónde y sobre qué ruta juzga. Dos
        ejecutores con la misma identidad ejecutan exactamente la misma suite:
        la línea base de uno vale por la del otro y no se corre dos veces.

        La ruta entra en la identidad porque dos ejecutores que comparten raíz e
        intérprete pero acotan distinto NO corren la misma suite: darles la
        misma línea base sería medir una y dar por buena la otra."""
        return (str(Path(self.raiz).resolve()), self.ejecutable, self.ruta or "")

    def correr(
        self,
        timeout_s: int,
        argumentos: tuple[str, ...] | None = None,
        ids: tuple[str, ...] | None = None,
    ) -> ResultadoSuite:
        """Ejecuta la suite y devuelve el hecho crudo, sin interpretarlo.

        La ruta acotada va SIEMPRE al final, tanto aquí como en la línea base:
        una base que recoge más tests que los mutantes no protege nada.

        Con `ids` (F-019, R9) corre SOLO esos nodeids, relativos a `raiz`, con
        los mismos argumentos y SIN la ruta acotada: los nodeids ya acotan, y
        añadir la ruta volvería a recoger la suite entera.
        """
        pedidos = list(argumentos or self.argumentos)
        if ids:
            pedidos.extend(ids)
        elif self.ruta is not None:
            pedidos.append(self.ruta)
        try:
            proceso = subprocess.run(
                [self.ejecutable, "-m", "pytest", *pedidos],
                cwd=self.raiz,
                capture_output=True,
                timeout=timeout_s,
                check=False,
                env=self.entorno(),
            )
        except subprocess.TimeoutExpired:
            return ResultadoSuite(codigo=-1, salida="", expirado=True)
        salida = (proceso.stdout or b"").decode("utf-8", "replace") + (
            proceso.stderr or b""
        ).decode("utf-8", "replace")
        return ResultadoSuite(codigo=proceso.returncode, salida=salida)

    def entorno(self) -> dict[str, str]:
        """Entorno de TODA suite que lanza este ejecutor: mapa, base, subconjunto
        y mutante (F-019). Un solo sitio, para que no diverjan.

        Con el factor de la campaña (R23 de F-019): `ARNES_FACTOR_TIMEOUT_TESTS`
        al número de workers, con `setdefault` —si el entorno ya lo trae, manda
        el del entorno—, para que los tests que lanzan subprocesos escalen su
        reloj con `harness.tiempos.escalar_timeout`. Fuera de una campaña no se
        inventa nada.
        """
        entorno = {
            **os.environ,
            # SIN BYTECODE, y no es un detalle de rendimiento. La suite se
            # lanza contra un fichero MUTADO: si el subproceso escribe
            # `__pycache__`, en el disco queda un `.pyc` compilado desde el
            # código mutado. Al restaurar el `.py` original, CPython valida
            # la caché por (tamaño, mtime) del fuente, y la restauración
            # deja los dos iguales —mismo texto, mismo segundo—, así que el
            # `.pyc` mutado se sigue dando por bueno. El árbol queda
            # envenenado: la campaña mide contra un código que ya no está y
            # la suite del proyecto puede pasar o fallar sin que nadie haya
            # tocado nada. El síntoma que lo delata es una campaña
            # absurdamente rápida. Pasó de verdad el 2026-08-19, y costó
            # una review entera averiguar de dónde salía.
            #
            # Y CON PREFIJO (F-023): `PYTHONPYCACHEPREFIX` a un directorio
            # vacío de esta raíz, que pisa el del entorno. Sin él, un
            # `__pycache__` previo del árbol (otra campaña, una purga que
            # falló) podía darse por válido para el fuente mutado.
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": prefijo_pycache(self.raiz),
        }
        if _FACTOR_TESTS is not None:
            entorno.setdefault(VARIABLE_FACTOR, str(_FACTOR_TESTS))
        return entorno

    def argumentos_linea_base(self) -> tuple[str, ...]:
        """Los `argumentos` del ejecutor, sin cortar al primer fallo y con resumen.

        R21 de F-023 (petición de datamart F-128): una base que recoge más o
        menos tests que los mutantes no protege nada, así que hereda rutas,
        `-k` y `-m`. Solo se quitan `-x`, `--exitfirst` y `--maxfail` —el
        aborto tiene que nombrar TODOS los tests que caen— y se añade `-rfE`.
        Con los argumentos por defecto, exactamente `ARGUMENTOS_LINEA_BASE`.
        """
        pedidos: list[str] = []
        saltar = False
        for argumento in self.argumentos:
            if saltar:
                saltar = False
                continue
            if argumento in ("-x", "--exitfirst") or argumento.startswith("--maxfail="):
                continue
            if argumento == "--maxfail":
                saltar = True
                continue
            pedidos.append(argumento)
        if pedidos == [a for a in ARGUMENTOS_LINEA_BASE if a != "-rfE"]:
            return ARGUMENTOS_LINEA_BASE
        if "-rfE" not in pedidos:
            pedidos.append("-rfE")
        return tuple(pedidos)

    def linea_base(self, timeout_s: int) -> ResultadoSuite:
        """Corre la suite SIN mutar nada, nombrando todos los tests que caen."""
        return self.correr(timeout_s, self.argumentos_linea_base())

    def medir_mapa(self, rutas: list[str], timeout_s: int) -> MapaTests | Degradado:
        """Mapa línea -> tests de `rutas` (relativas a `raiz`) con ESTA suite (F-019).

        La suite entera, con los argumentos de la línea base, bajo coverage y
        el plugin del arnés, en esta raíz y con este intérprete (R1, R18).
        """
        return medir_mapa_de_tests(self, rutas, timeout_s)

    def juzgar(self, timeout_s: int) -> tuple[str, str]:
        """`(veredicto, código de salida)` del mutante aplicado (F-023).

        Un solo criterio: MUERTO es el código 1 y nada más. El 0 es
        superviviente; el reloj agotado, timeout; y todo lo demás —2, 3, 4 y
        también el 5, «ningún test recogido»— es `INDETERMINADO`, que resuelve
        quien llama mirando la línea base. El código viaja con el veredicto
        para que el informe diga el hecho y no solo su lectura.
        """
        return _leer_veredicto(self.correr(timeout_s))

    def juzgar_subconjunto(self, ids: tuple[str, ...], timeout_s: int) -> tuple[str, str]:
        """`(veredicto, código)` del mutante aplicado con SOLO esos tests (R9).

        Mismo criterio que `juzgar`; quien llama decide qué hacer con él: solo
        el MUERTO es definitivo, el resto se revalida con la suite entera (R15).
        """
        return _leer_veredicto(self.correr(timeout_s, ids=ids))

    def subconjunto_verde(self, ids: tuple[str, ...], timeout_s: int) -> bool:
        """¿Esos tests salen con código 0 SIN mutar nada? (R13)

        Un test que depende de otro, o del orden, sale rojo en el subconjunto
        sin culpa del mutante; sin esta comprobación su rojo contaría como un
        muerto que nadie mató.
        """
        return self.correr(timeout_s, ids=ids).verde

    def ejecutar(self, timeout_s: int) -> str:
        return self.juzgar(timeout_s)[0]


def _leer_veredicto(resultado: ResultadoSuite) -> tuple[str, str]:
    """El criterio único de F-023: MUERTO es el código 1 y nada más."""
    if resultado.expirado:
        return (TIMEOUT, CODIGO_TIMEOUT)
    codigo = str(resultado.codigo)
    if resultado.codigo == PYTEST_OK:
        return (SUPERVIVIENTE, codigo)
    if resultado.codigo == PYTEST_FALLOS:
        return (MUERTO, codigo)
    return (INDETERMINADO, codigo)


# --- Línea base: nunca contar muertos sobre una suite que ya fallaba ---------


#: Causas conocidas de una línea base roja que SOLO se rompe en modo paralelo.
#: Se enumeran en el mensaje de aborto porque el arreglo es distinto en cada
#: caso y adivinarlo desde «3 tests fallan» cuesta una tarde.
CAUSAS_CONOCIDAS = (
    (
        "ficheros NO versionados que la suite necesita (.env, datos locales, "
        "fixtures generadas): no existen dentro de un git worktree; decláralos "
        "en 'mutacion.ficheros_no_versionados' y se copian"
    ),
    (
        "detached HEAD: el worktree no está en ninguna rama, así que un test "
        "que lea `git branch --show-current` recibe cadena vacía"
    ),
    (
        "instalación editable apuntando al árbol principal: la suite del worker "
        "importaría el código de fuera del worktree, sin mutar"
    ),
)

#: Causas que NO tienen nada que ver con el paralelismo y muerden igual con
#: `--workers 1`. La primera se descubrió el 2026-08-19: un fichero de
#: `harness/` no pertenece a ningún servicio, así que `ejecutor_para` lo juzga
#: con `python -m pytest` SIN ruta desde la raíz; sin configuración de pytest
#: ahí, esa invocación recoge las suites de todos los servicios y muere en la
#: recolección en menos de un segundo, haga lo que haga el mutante. Dos
#: campañas enteras, de 19 y de 61 mutantes sobre ficheros de `harness/`,
#: salieron «muertas» sin que un solo test las juzgara.
CAUSAS_EN_CUALQUIER_MODO = (
    (
        "la suite se invoca SIN ruta —`python -m pytest` desde la raíz— porque "
        "el fichero mutado no cae en ningún servicio de harness/servicios.json: "
        "si la raíz no tiene configuración de pytest (testpaths, rootdir), esa "
        "invocación recoge lo que no debe y muere en la recolección"
    ),
    (
        "la suite necesita un servicio externo (base de datos, cola, API) que "
        "en esta máquina no está levantado"
    ),
)


def timeout_derivado(
    suelo: int, tiempos_base: dict[str, float], margen: float = MARGEN_TIMEOUT
) -> int:
    """Segundos por mutante derivados de la línea base ya medida (R1).

    `max(suelo, ceil(peor_tiempo × margen))`. Sede ÚNICA de la fórmula.

    Se deriva de la línea base y no de una medición aparte porque
    `comprobar_linea_base` ya corre la suite limpia **dentro de cada worktree y
    con los W workers compitiendo**, que es justo la contención que hay que
    medir, y ya devuelve los segundos: la medición correcta estaba hecha y se
    tiraba. Usarla no cuesta ni un segundo extra y absorbe máquina, workers y
    tamaño de suite sin ninguna fórmula que adivine.

    Manda el PEOR de los tiempos: un timeout que solo le vale al worker más
    rápido no le vale a nadie. Se redondea hacia arriba porque regalar el
    segundo que faltaba justo en el peor caso convierte una campaña válida en
    una tanda de «timeout». Sin ninguna medición —ejecutores dobles, campaña sin
    línea base— no hay nada de lo que derivar y se devuelve el suelo tal cual.
    """
    if not tiempos_base:
        return suelo
    return max(suelo, math.ceil(max(tiempos_base.values()) * margen))


def timeout_de_base_de_cierre(
    timeout_base_s: int, tiempos_apertura: dict[str, float], margen: float = MARGEN_TIMEOUT
) -> int:
    """Segundos para la línea base de CIERRE (R20 de F-019, §8 de su spec).

    `max(timeout_base_s, ceil(peor base de apertura × margen))`. La de apertura
    ya se midió con la misma carga que tendrá la de cierre; anclar el cierre
    solo al suelo (`suelo × 5 × W`) dejó sin validez las dos campañas de T15
    de F-019, con aperturas de 806–858 s y un reloj de 1200 s. Sin apertura
    medida, el reloj de la base tal cual.
    """
    if not tiempos_apertura:
        return timeout_base_s
    return max(timeout_base_s, math.ceil(max(tiempos_apertura.values()) * margen))


def timeout_de_linea_base(suelo: int, workers: int = 1) -> int:
    """Segundos que se le conceden a la suite SIN mutar nada (R2), y al mapa.

    `suelo × FACTOR_HOLGURA_BASE × max(1, workers)` (R20 de F-019). Ver
    `FACTOR_HOLGURA_BASE`: es holgado a propósito y su coste está acotado
    porque se paga una vez por worker. Lineal en W y sin techo (decisión D3 del
    humano): con W suites compitiendo, cada una avanza como mucho W veces más
    despacio, y la de F-026 con 2 workers ya rozaba los 875 s de 600.
    """
    return suelo * FACTOR_HOLGURA_BASE * max(1, workers)


def mensaje_base_rota(etiqueta: str, resultado: ResultadoSuite) -> str:
    """Mensaje accionable: qué falla, dónde, por qué suele fallar y qué hacer."""
    fallidos = resultado.fallidos()
    detalle = (
        "\n".join(f"    - {nombre}" for nombre in fallidos)
        if fallidos
        else f"    (pytest salió con código {resultado.codigo} sin nombrar tests)"
    )
    causas = "\n".join(f"    - {causa}" for causa in CAUSAS_CONOCIDAS)
    siempre = "\n".join(f"    - {causa}" for causa in CAUSAS_EN_CUALQUIER_MODO)
    return (
        f"LÍNEA BASE EN ROJO en {etiqueta}: la suite falla SIN mutar nada.\n"
        "Campaña abortada sin escribir informe: sobre una base roja TODO "
        "mutante saldría «muerto» y el cero de supervivientes sería falso.\n"
        "\n"
        "  Tests que fallan sin mutar:\n"
        f"{detalle}\n"
        "\n"
        "  Causas conocidas SOLO del modo paralelo (cada worker corre en un\n"
        "  `git worktree` desechable creado desde HEAD):\n"
        f"{causas}\n"
        "\n"
        "  Causas que muerden en CUALQUIER modo, también con --workers 1:\n"
        f"{siempre}\n"
        "\n"
        "  Arregla la base. Si la tuya es de las primeras, --workers 1 la "
        "esquiva: en\n"
        "  serie la suite corre sobre el propio árbol y no hay worktree que "
        "valga."
    )


def mensaje_base_expirada_al_arrancar(
    etiqueta: str, timeout_s: int, workers: int | None
) -> str:
    """Aviso de una línea base de ARRANQUE que se quedó sin tiempo (R5).

    «Sube el timeout» no es una acción: con W workers compitiendo, la respuesta
    casi siempre es bajar W, y el valor que se sube tiene nombre y fichero. Sin
    esos dos datos el mensaje manda a adivinar, y adivinar en esta maquinaria ha
    costado ya varias tardes.
    """
    cuantos = f"{workers} worker(s)" if workers is not None else "los workers en juego"
    return (
        f"LÍNEA BASE SIN TERMINAR en {etiqueta}: la suite SIN MUTAR agotó los "
        f"{timeout_s} s que se le concedieron (el suelo "
        f"'mutacion.timeout_por_mutante_s' multiplicado por la holgura de "
        f"{FACTOR_HOLGURA_BASE} y por los workers), con {cuantos} compitiendo "
        "por la máquina.\n"
        "  Ningún veredicto de esta campaña valdría: si la suite LIMPIA ya no "
        "cabe en el reloj, todo mutante saldría «timeout».\n"
        "  Qué hacer: baja los workers (--workers N; cada worker arranca una "
        "suite entera, no un hilo) o sube el suelo "
        "'mutacion.timeout_por_mutante_s' de harness/rigor.json. Si ni con esa "
        "holgura cabe la suite limpia, entonces sí: acótala."
    )


def comprobar_linea_base(
    implicados: list[tuple[str, object]],
    timeout_s: int,
    eco: Callable[[str], None] | None = None,
    workers: int | None = None,
) -> dict[str, float]:
    """Corre la suite sin mutar en cada sitio donde se va a juzgar.

    `implicados` son los pares `(etiqueta, ejecutor)` que van a dictar los
    veredictos. Un ejecutor sin `linea_base` —un doble de test— se salta con
    aviso: no se puede comprobar lo que no sabe correr una suite.

    Lanza `BaseRota` en cuanto uno falla, sin haber tocado un solo fichero.

    Devuelve los SEGUNDOS que tardó la suite limpia en cada sitio (R11). Ese
    número es el patrón con el que se lee todo lo demás: una campaña que declara
    veinte mutantes en menos de lo que tarda UNA suite limpia no ha juzgado a
    nadie, y eso se ve leyendo el informe en vez de reejecutándolo. Un ejecutor
    que no sabe correr la suite no aporta entrada: mejor `n/d` que un cero, que
    se lee como medición.
    """
    tiempos: dict[str, float] = {}
    for etiqueta, ejecutor in implicados:
        correr_base = getattr(ejecutor, "linea_base", None)
        if correr_base is None:
            if eco is not None:
                eco(f"{MARCA_LINEA_BASE}{etiqueta}: ejecutor sin línea base, no se comprueba")
            continue
        arranque = time.monotonic()
        resultado = correr_base(timeout_s)
        tiempos[etiqueta] = time.monotonic() - arranque
        if resultado.expirado:
            raise BaseRota(
                mensaje_base_expirada_al_arrancar(etiqueta, timeout_s, workers)
            )
        if not resultado.base_utilizable:
            raise BaseRota(mensaje_base_rota(etiqueta, resultado))
        if eco is not None:
            estado = "sin tests que recoger" if resultado.sin_tests else "en verde"
            eco(
                f"{MARCA_LINEA_BASE}{etiqueta}: {estado} "
                f"({tiempos[etiqueta]:.1f} s)"
            )
    return tiempos


def ejecutores_implicados(
    mutantes: list[Mutante],
    ejecutor: object,
    ejecutor_de: Callable[[str], object] | None,
) -> list[tuple[str, object]]:
    """Ejecutores distintos que van a juzgar esta tanda de mutantes.

    Se deduplica por identidad —(directorio, intérprete)— para no correr N
    veces la misma suite en un monorepo donde varios ficheros del alcance caen
    en el mismo servicio.
    """
    if ejecutor_de is None:
        return [(_etiqueta_de(ejecutor), ejecutor)]
    elegidos: dict[object, tuple[str, object]] = {}
    for mutante in mutantes:
        candidato = ejecutor_de(mutante.fichero)
        identidad = getattr(candidato, "identidad", None)
        clave = identidad() if identidad is not None else id(candidato)
        elegidos.setdefault(clave, (_etiqueta_de(candidato), candidato))
    return list(elegidos.values())


def _etiqueta_de(ejecutor: object) -> str:
    """Cómo se nombra un ejecutor en los mensajes: por el directorio que corre."""
    raiz = getattr(ejecutor, "raiz", None)
    return Path(str(raiz)).as_posix() if raiz is not None else repr(ejecutor)


def _ruta_raiz(raiz: str) -> str | None:
    """Ruta con la que se acota la suite de la RAÍZ, o `None` si no la hay.

    `tests` es la convención del arnés —`harness/init.sh` ya invoca así la
    suite de la raíz— y acotarla es lo que permite juzgar un fichero que no
    pertenece a ningún servicio. Un repositorio que ponga su suite en otro sitio
    no mejora (R2): se invoca sin ruta, exactamente como hasta hoy.
    """
    return "tests" if (Path(raiz) / "tests").is_dir() else None


def ejecutor_para(
    fichero: str,
    servicios: list[Servicio],
    raiz: str = ".",
    raiz_venvs: str | None = None,
) -> EjecutorPytest:
    """Ejecutor con el que se juzga un mutante, según a qué servicio pertenece.

    Un fichero de un servicio Python se juzga con la suite de ESE servicio, en
    su directorio y con su intérprete. Todo lo demás —código de la raíz, o un
    `.py` suelto dentro de un servicio de otro lenguaje— con la suite de la
    raíz, como en un repositorio de un solo proyecto.

    `raiz_venvs` separa DÓNDE se ejecuta la suite de DÓNDE vive el entorno
    virtual: la campaña paralela lanza los tests dentro de un `git worktree`
    —que no trae venvs, porque no están versionados— con el intérprete del
    árbol principal. Sin él, ambas cosas son `raiz` y el comportamiento es
    exactamente el de siempre.
    """
    servicio = servicio_de_ruta(fichero, servicios)
    if servicio is None or servicio.lenguaje != "python":
        return EjecutorPytest(raiz=raiz, ruta=_ruta_raiz(raiz))
    return EjecutorPytest(
        raiz=str(Path(raiz) / servicio.ruta),
        ejecutable=interprete(servicio, raiz_venvs or raiz),
    )


# --- Centinela: qué mutante está aplicado AHORA MISMO ------------------------


@dataclass(frozen=True)
class Aplicado:
    """Un mutante escrito en disco en este instante."""

    fichero: str
    ruta: str
    linea: int
    descripcion: str
    linea_original: str
    en_arbol_principal: bool


class Centinela:
    """Deja escrito en disco qué mutante está aplicado, y en qué fichero.

    El `try/finally` de la campaña restaura el árbol en todo lo que se puede
    prever: excepción, timeout, Ctrl-C. Lo que NO cubre es un `kill` que mata el
    proceso sin desenrollar la pila —pasó el 2026-08-19 y dejaron el árbol con
    un `==` convertido en `!=` dentro de la puerta que protege `build_mart`—. El
    riesgo real de eso no es perder la campaña: es **commitear un mutante
    creyendo que es código**.

    Este centinela es la red de la red: un JSON pequeño que se reescribe al
    aplicar y al soltar cada mutante, y que se borra al terminar bien. Si queda
    ahí, algo murió a medias y lo dice con nombre y línea. Lo leen dos: la
    siguiente campaña (que se ofrece a restaurar) y `harness/init.sh`, para no
    dar por válido un veredicto medido sobre un mutante.

    Es seguro entre hilos: los workers de la campaña paralela comparten uno.
    """

    def __init__(
        self, raiz: str = ".", feature: str = "", modo: str = "serie", pid: int | None = None
    ) -> None:
        self.raiz = Path(raiz).resolve()
        self.ruta = self.raiz / RUTA_CENTINELA
        self.feature = feature
        self.modo = modo
        self.pid = os.getpid() if pid is None else pid
        self.inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._aplicados: dict[str, Aplicado] = {}
        self._cerrojo = threading.Lock()

    # -- escritura ----------------------------------------------------------

    def _volcar(self) -> None:
        """Reescribe el fichero entero: es pequeño y así nunca queda a medias."""
        aplicados = list(self._aplicados.values())
        datos = {
            "feature": self.feature,
            "modo": self.modo,
            "pid": self.pid,
            "inicio": self.inicio,
            "raiz": self.raiz.as_posix(),
            "muta_arbol_principal": any(a.en_arbol_principal for a in aplicados),
            "aplicados": [vars(a) for a in aplicados],
        }
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def abrir(self) -> None:
        with self._cerrojo:
            self._volcar()

    def aplicar(self, ruta: Path, mutante: Mutante, fuente_original: str) -> None:
        """Anota que `ruta` acaba de quedar mutada, con cómo era su línea."""
        brutas = fuente_original.split("\n")
        original = brutas[mutante.linea - 1] if mutante.linea <= len(brutas) else ""
        absoluta = Path(ruta).resolve()
        with self._cerrojo:
            self._aplicados[absoluta.as_posix()] = Aplicado(
                fichero=mutante.fichero,
                ruta=absoluta.as_posix(),
                linea=mutante.linea,
                descripcion=mutante.descripcion(),
                linea_original=original,
                en_arbol_principal=_dentro_de(absoluta, self.raiz),
            )
            self._volcar()

    def soltar(self, ruta: Path) -> None:
        """Anota que `ruta` ya está restaurada."""
        with self._cerrojo:
            self._aplicados.pop(Path(ruta).resolve().as_posix(), None)
            self._volcar()

    def cerrar(self) -> None:
        """Retira el centinela: la campaña terminó y el árbol está limpio."""
        with self._cerrojo:
            self._aplicados.clear()
            self.ruta.unlink(missing_ok=True)

    # -- lectura y recuperación ---------------------------------------------

    @staticmethod
    def leer(raiz: str = ".") -> dict | None:
        """Contenido del centinela de `raiz`, o `None` si no hay campaña anotada."""
        ruta = Path(raiz).resolve() / RUTA_CENTINELA
        if not ruta.is_file():
            return None
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Un centinela ilegible es igual de sospechoso que uno legible: hubo
            # una campaña y nadie la cerró. Se devuelve lo mínimo para avisar.
            return {"feature": "", "aplicados": [], "muta_arbol_principal": True,
                    "ilegible": True}


def _dentro_de(ruta: Path, directorio: Path) -> bool:
    """¿`ruta` cuelga de `directorio`? (sin `is_relative_to`, que exige 3.9+)."""
    try:
        Path(ruta).resolve().relative_to(Path(directorio).resolve())
    except ValueError:
        return False
    return True


def restaurar_desde_centinela(raiz: str = ".") -> tuple[list[str], list[str]]:
    """Deshace los mutantes que dejó aplicados una campaña muerta a medias.

    Devuelve `(restaurados, irrecuperables)`. Se reescribe LA LÍNEA mutada con
    el texto original que el propio centinela guardó, que es lo único que la
    campaña llegó a cambiar; solo si esos datos no sirven se recurre a `git
    checkout`, que reescribe el fichero entero y, con `core.autocrlf` de por
    medio, puede cambiarle los finales de línea por el camino. Lo que no se pueda
    arreglar se devuelve para que lo vea un humano: dejarlo en silencio sería lo
    peor.
    """
    datos = Centinela.leer(raiz)
    if datos is None:
        return ([], [])
    restaurados: list[str] = []
    irrecuperables: list[str] = []
    for aplicado in datos.get("aplicados", []):
        ruta = Path(str(aplicado.get("ruta", "")))
        if not ruta.is_file():
            continue  # el worktree ya no está: no hay nada que restaurar
        original = aplicado.get("linea_original")
        numero = int(aplicado.get("linea", 0) or 0)
        brutas = _leer(ruta).split("\n") if original is not None else []
        if original is not None and 0 < numero <= len(brutas):
            brutas[numero - 1] = original
            _escribir(ruta, "\n".join(brutas))
            restaurados.append(ruta.as_posix())
            continue
        codigo, _ = _git_en(str(ruta.parent), "checkout", "--", str(ruta))
        if codigo == 0:
            restaurados.append(ruta.as_posix())
        else:
            irrecuperables.append(ruta.as_posix())
    Path(raiz).resolve().joinpath(RUTA_CENTINELA).unlink(missing_ok=True)
    return (restaurados, irrecuperables)


# --- Restauración a prueba de señales ----------------------------------------


@contextmanager
def restauracion_ante_senales(restaurar: Callable[[], None]) -> Iterator[None]:
    """Ejecuta `restaurar` también cuando llegan SIGINT o SIGTERM.

    `try/finally` no cubre una señal que termina el proceso: SIGTERM lo mata sin
    desenrollar la pila y el árbol se queda mutado. Aquí se atiende la señal, se
    restaura y se convierte en la excepción que el `finally` de siempre sabe
    tratar (`KeyboardInterrupt` para SIGINT, `SystemExit` para SIGTERM).

    Solo el hilo principal puede registrar manejadores: llamado desde un worker
    esto no hace nada, a propósito y sin ruido. En la campaña paralela el
    manejador lo pone el coordinador, que sí es el hilo principal, y restaura
    los worktrees de todos leyendo el centinela compartido.
    """
    anteriores: dict[int, object] = {}

    def manejador(numero: int, _marco: object) -> None:
        restaurar()
        if numero == getattr(signal, "SIGINT", None):
            raise KeyboardInterrupt
        raise SystemExit(128 + numero)

    for nombre in ("SIGINT", "SIGTERM"):
        numero = getattr(signal, nombre, None)
        if numero is None:
            continue
        try:
            anteriores[int(numero)] = signal.signal(numero, manejador)
        except (ValueError, OSError):
            pass  # hilo secundario, o plataforma que no permite ese manejador
    try:
        yield
    finally:
        for numero, anterior in anteriores.items():
            try:
                signal.signal(numero, anterior)  # type: ignore[arg-type]
            except (ValueError, OSError, TypeError):
                pass


# --- Guardia del árbol de trabajo --------------------------------------------


def _git_en(raiz: str, *args: str) -> tuple[int, str]:
    """git en `raiz`, devolviendo `(código, salida)`.

    No se reutiliza `harness.alcance.ejecutar_git`: aquel devuelve cadena vacía
    cuando git falla, y aquí distinguir «no hay cambios» de «git ha fallado»
    decide si la campaña arranca o no.
    """
    proceso = subprocess.run(
        ["git", "-C", str(raiz), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return proceso.returncode, (proceso.stdout or "") + (proceso.stderr or "")


def sha_de_head(raiz: str = ".") -> str | None:
    """SHA COMPLETO de `HEAD` en `raiz`, o `None` si git no puede responder.

    Completo y no abreviado a propósito: es lo que permite comprobar sin
    ambigüedad que el alcance medido y el alcance revisado son el mismo commit.
    Fuera de un repositorio devuelve `None`, y el informe imprime `n/d`: nunca
    un SHA inventado.
    """
    codigo, salida = _git_en(raiz, "rev-parse", "HEAD")
    if codigo != 0:
        return None
    sha = salida.strip()
    return sha or None


def ficheros_con_cambios(raiz: str, ficheros: list[str]) -> list[str]:
    """De los ficheros dados, cuáles tienen cambios sin commitear.

    Lanza `ArbolSucio` si git no puede responder: no saber si un fichero que
    vamos a sobrescribir tiene trabajo dentro es exactamente el caso en que no
    hay que tocarlo.
    """
    if not ficheros:
        return []
    codigo, salida = _git_en(raiz, "status", "--porcelain", "--", *ficheros)
    if codigo != 0:
        raise ArbolSucio(
            f"No se pudo comprobar el estado del árbol en {raiz} (git salió con "
            f"{codigo}). La campaña sobrescribe ficheros de producción para "
            "mutarlos y no arranca sin saber si tienen trabajo sin commitear.\n"
            f"    {salida.strip()}"
        )
    sucios: list[str] = []
    for linea in salida.splitlines():
        if len(linea) < 4:
            continue
        ruta = linea[3:].strip().strip('"')
        if " -> " in ruta:  # renombrado: interesa el destino
            ruta = ruta.split(" -> ", 1)[1].strip().strip('"')
        if ruta not in sucios:
            sucios.append(ruta)
    return sucios


def guardia_arbol_limpio(raiz: str, ficheros: list[str]) -> None:
    """Se niega a arrancar si algún fichero a mutar tiene cambios sin commitear.

    Dos motivos, los dos vividos: (1) al restaurar, la campaña reescribe el
    fichero con lo que leyó al empezar, así que un cambio a medias que llegue
    después se pierde; (2) si la campaña muere a machetazos, el mutante que deje
    escrito es indistinguible de trabajo real y acaba commiteado.
    """
    sucios = ficheros_con_cambios(raiz, ficheros)
    if not sucios:
        return
    listado = "\n".join(f"    - {ruta}" for ruta in sucios)
    raise ArbolSucio(
        "Hay cambios sin commitear en ficheros que esta campaña va a MUTAR:\n"
        f"{listado}\n"
        "\n"
        "  La campaña los sobrescribe y los restaura a como estaban al empezar, "
        "así que\n"
        "  cualquier edición posterior se perdería; y si la campaña muere a "
        "medias, el\n"
        "  mutante que quede en disco es indistinguible de tu trabajo. "
        "Commitea (o guarda\n"
        "  en un stash) y vuelve a lanzarla."
    )


# --- Campaña ----------------------------------------------------------------


def mutantes_por_fichero(alcance: Alcance, mutantes: list[Mutante]) -> dict[str, int]:
    """Cuántos de `mutantes` caen en cada fichero del alcance, 0 incluido (R15).

    El 0 es el dato: un fichero con líneas en alcance y ningún mutante es lo
    que la suma de la campaña escondía (F-026).
    """
    cuenta = dict.fromkeys(alcance.ficheros(), 0)
    for mutante in mutantes:
        if mutante.fichero in cuenta:
            cuenta[mutante.fichero] += 1
    return cuenta


# --- Mapa línea -> tests (F-019) --------------------------------------------

#: Identidad de un mapa: (directorio del ejecutor RELATIVO al árbol, intérprete,
#: ruta acotada). Relativa para que el mapa medido en `wk_0` valga en los demás
#: worktrees y en el repaso (R5, R29).
ClaveMapa = tuple[str, str, str]


def clave_de_mapa(ejecutor: object, raiz: str) -> ClaveMapa:
    """Con qué clave se guarda (y se busca) el mapa de `ejecutor` en el árbol `raiz`."""
    propia = getattr(ejecutor, "raiz", None)
    if propia is None:
        relativa = "."
    else:
        try:
            relativa = Path(
                os.path.relpath(Path(str(propia)).resolve(), Path(raiz).resolve())
            ).as_posix()
        except ValueError:  # Windows: otra unidad
            relativa = Path(str(propia)).resolve().as_posix()
    ruta = getattr(ejecutor, "ruta", None)
    return (relativa, str(getattr(ejecutor, "ejecutable", "")), str(ruta or ""))


def etiqueta_de_clave(clave: ClaveMapa) -> str:
    """Cómo se nombra un mapa en el informe: su directorio relativo."""
    return clave[0]


def ruta_para_ejecutor(fichero: str, ejecutor: object, raiz: str) -> str:
    """`fichero` (relativo al árbol) relativo al directorio del ejecutor."""
    propia = getattr(ejecutor, "raiz", None)
    if propia is None:
        return fichero
    try:
        return Path(
            os.path.relpath((Path(raiz) / fichero).resolve(), Path(str(propia)).resolve())
        ).as_posix()
    except ValueError:
        return fichero


def _avisar(eco: Callable[[str], None] | None, texto: str) -> None:
    if eco is not None:
        eco(texto)
    else:
        print(texto, file=sys.stderr)


def medir_mapas(
    ficheros: list[str],
    ejecutor: object,
    ejecutor_de: Callable[[str], object] | None,
    raiz: str,
    timeout_s: int,
    eco: Callable[[str], None] | None = None,
) -> dict[ClaveMapa, MapaTests | Degradado]:
    """Un mapa por ejecutor implicado, medido en el árbol `raiz` (R1, R18).

    Cada ejecutor mide con su suite entera los ficheros de `ficheros` que
    juzga él. Un ejecutor que no sabe medir (un doble, una subclase de
    proyecto) queda `Degradado`. El motivo de cada degradación se imprime.
    """
    grupos: dict[ClaveMapa, tuple[object, list[str]]] = {}
    for fichero in ficheros:
        elegido = ejecutor if ejecutor_de is None else ejecutor_de(fichero)
        clave = clave_de_mapa(elegido, raiz)
        rutas = grupos.setdefault(clave, (elegido, []))[1]
        relativa = ruta_para_ejecutor(fichero, elegido, raiz)
        if relativa not in rutas:
            rutas.append(relativa)
    mapas: dict[ClaveMapa, MapaTests | Degradado] = {}
    for clave, (elegido, rutas) in grupos.items():
        etiqueta = etiqueta_de_clave(clave)
        medir = getattr(elegido, "medir_mapa", None)
        if medir is None:
            mapas[clave] = Degradado("el ejecutor no sabe medir el mapa")
        else:
            if eco is not None:
                eco(
                    f"{MARCA_LINEA_BASE}mapa de `{etiqueta}`: midiendo qué test "
                    f"ejecuta cada línea ({len(rutas)} fichero(s), suite entera bajo "
                    "coverage)"
                )
            mapas[clave] = medir(rutas, timeout_s)
        resultado = mapas[clave]
        if isinstance(resultado, Degradado):
            _avisar(
                eco,
                f"{MARCA_LINEA_BASE}mapa de `{etiqueta}`: SIN selección de tests, se "
                f"juzga todo con la suite entera — {resultado.motivo}",
            )
        elif eco is not None:
            eco(
                f"{MARCA_LINEA_BASE}mapa de `{etiqueta}`: {len(resultado.orden)} tests, "
                f"{resultado.segundos:.1f} s"
            )
    return mapas


def _mapas_vigentes(
    mapas: dict[ClaveMapa, MapaTests | Degradado],
    sha_head: str | None,
    raiz: str,
    eco: Callable[[str], None] | None,
) -> dict[ClaveMapa, MapaTests | Degradado]:
    """Los mapas con los que juzga ESTE árbol: el de otro HEAD no vale (R6)."""
    vigentes: dict[ClaveMapa, MapaTests | Degradado] = {}
    for clave, mapa in mapas.items():
        if isinstance(mapa, MapaTests) and mapa.sha != (sha_head or ""):
            mapa = Degradado(
                f"el HEAD de {Path(raiz).as_posix()} ({sha_head or 'n/d'}) no es el del "
                f"mapa ({mapa.sha or 'n/d'}): sus mutantes se juzgan con la suite entera"
            )
            _avisar(eco, f"{MARCA_LINEA_BASE}AVISO: {mapa.motivo}")
        vigentes[clave] = mapa
    return vigentes


def _anotar_mapas(informe: InformeMutacion, mapas: dict[ClaveMapa, MapaTests | Degradado]) -> None:
    """Lo que el informe declara de los mapas: modo, motivos, SHA, tiempos (R25)."""
    informe.seleccion = SELECCION_ACTIVA
    for clave, mapa in mapas.items():
        etiqueta = etiqueta_de_clave(clave)
        if isinstance(mapa, Degradado):
            informe.seleccion = SELECCION_DEGRADADA
            informe.motivos_degradado[etiqueta] = mapa.motivo
            continue
        informe.sha_mapa = informe.sha_mapa or mapa.sha
        informe.segundos_mapa[etiqueta] = mapa.segundos
        informe.tests_en_suite[etiqueta] = len(mapa.orden)


@dataclass
class InformeMutacion:
    """Resultado de una campaña de mutación."""

    feature: str
    alcance: Alcance
    generados: int = 0
    muertos: int = 0
    supervivientes: list[Mutante] = field(default_factory=list)
    timeouts: list[Mutante] = field(default_factory=list)
    mutantes_evaluados: list[Mutante] = field(default_factory=list)
    segundos: float = 0.0
    muestreado: bool = False
    max_mutantes: int | None = None
    semilla: int | None = None
    #: Mutantes juzgados sobre una base que ya estaba rota. Ni muertos ni
    #: supervivientes: de ellos no se sabe nada.
    base_rota: list[Mutante] = field(default_factory=list)
    #: Motivo por el que los números de este informe NO son de fiar, si lo hay.
    aviso_base: str | None = None
    #: SHA completo de HEAD contra el que se midió. Sin él, un informe sigue
    #: pareciendo válido después de que la rama crezca mil líneas (RM1/R10).
    sha_head: str | None = None
    #: Segundos que tardó la suite LIMPIA en cada ejecutor implicado (R11). Es
    #: el patrón contra el que se lee la media por mutante.
    segundos_linea_base: dict[str, float] = field(default_factory=dict)
    #: Nivel de rigor que fijó el muestreo, para que el informe diga quién lo
    #: decidió (R9). Lo rellena el CLI, que es quien lo resuelve.
    nivel: str | None = None
    #: Segundos concedidos a CADA mutante en esta campaña (R4). Ya no es el
    #: valor de `rigor.json` sino uno derivado de la línea base medida, y sin
    #: declararlo los tiempos de dos campañas dejan de ser comparables sin que
    #: nadie se entere.
    timeout_efectivo: int | None = None
    #: El SUELO del que se partió (`mutacion.timeout_por_mutante_s`), o el valor
    #: de `--timeout` si se fijó a mano.
    timeout_suelo: int | None = None
    #: ¿El timeout vino de `--timeout` en vez de derivarse? (R6)
    timeout_fijado: bool = False
    #: Workers con los que se midió. Con W workers el «Tiempo total» es
    #: aproximadamente `mutantes × media / W`, y sin este número la regla de
    #: coherencia de RM2 marcaría como sospechosa una campaña legítima (R27).
    workers: int | None = None
    #: Rama de integración contra la que se calculó el alcance. Sin ella, el
    #: comando de la cabecera mide OTRO alcance cuando la rama nace de otra
    #: feature: el diff contra `dev` arrastra las líneas de la feature madre.
    base: str | None = None
    #: Cuántos mutantes que quedaron en `timeout` se repasaron después EN SERIE.
    #: Cero significa «no hizo falta» o «esta campaña no repasa», nunca «no se
    #: hace»: el informe distingue los tres casos por escrito.
    timeouts_repasados: int = 0
    #: Regla con que se eligieron los mutantes (F-058); `None` = el camino de
    #: antes, con `max_mutantes` a secas, y el informe sale como entonces.
    regla: ReglaMuestreo | None = None
    #: Mutantes que quedaron tras la reducción a uno por línea, antes de sortear.
    candidatos: int | None = None
    #: Muertos de la campaña anterior que se dan por buenos sin reevaluarlos
    #: (`--incremental`). Cuentan como muertos en el informe y en el estado.
    reutilizados: list[Mutante] = field(default_factory=list)
    #: SHA del estado del que se reutiliza, y cuántos muertos de la muestra de
    #: control se volvieron a juzgar. Solo en una campaña incremental (R19).
    incremental_desde: str | None = None
    control: int = 0
    #: Mutantes sin veredicto por causa del propio mutante (F-023): no compila,
    #: o su suite salió con 2, 3, 4 o 5 con la base utilizable. Ni muertos ni
    #: supervivientes, y no invalidan la campaña (R7).
    indeterminados: list[Mutante] = field(default_factory=list)
    #: Código de salida de cada mutante NO muerto, por `clave_de_orden` (la
    #: misma tupla que `clave_estable` de la paralela): `"0"`…`"5"`,
    #: `"timeout"`, `"no compila"` o `"n/d"` (R8).
    codigos: dict[tuple, str] = field(default_factory=dict)
    #: `"<ruta>: <error>"` de cada `.pyc` que la purga no pudo borrar (R14).
    pyc_no_borrados: list[str] = field(default_factory=list)
    #: Mutantes GENERADOS por fichero del alcance, 0 incluido (F-026, R15):
    #: antes de muestrear, así que su suma es `generados`. `None` = no se sabe
    #: (informes construidos a mano, dobles de antes), y el informe dice `n/d`.
    por_fichero: dict[str, int] | None = None
    #: F-019. Supervivientes PODADOS: subconjunto de `supervivientes` cuya
    #: sentencia no ejecuta ningún proceso medido (R8, R24).
    podados: list[Mutante] = field(default_factory=list)
    #: `activa`, `degradada` o `desactivada`; `None` = campaña sin selección
    #: que no la declara (dobles, informes de antes), y el informe sale como
    #: en la 1.9.0.
    seleccion: str | None = None
    #: Motivo de cada ejecutor sin mapa, por su etiqueta (R18, R6).
    motivos_degradado: dict[str, str] = field(default_factory=dict)
    sha_mapa: str | None = None
    #: Segundos de la medición del mapa y tests de su suite, por etiqueta.
    segundos_mapa: dict[str, float] = field(default_factory=dict)
    tests_en_suite: dict[str, int] = field(default_factory=dict)
    #: Tamaño del subconjunto de cada mutante juzgado con uno (R25).
    tamanos_subconjunto: list[int] = field(default_factory=list)
    #: Mutantes que el subconjunto no mató y se revalidaron con la suite
    #: entera, y cuántos de ellos murieron al revalidar (R15, R25).
    revalidados: int = 0
    muertos_al_revalidar: int = 0
    #: Subconjuntos distintos que no salieron verdes SIN mutar (R13).
    subconjuntos_descartados: int = 0
    #: Segundos y mutantes juzgados con la SUITE ENTERA: la media que RM2
    #: mira cuando la selección está activa (R26).
    segundos_suite_entera: float = 0.0
    juzgados_suite_entera: int = 0
    #: ¿`mutacion.seleccion_de_tests` la encendía? Lo sabe el CLI, no la campaña:
    #: el comando de la cabecera tiene que reproducir el modo (F-019, R19).
    seleccion_por_rigor: bool = False

    @property
    def segundos_por_mutante(self) -> float | None:
        """Media de segundos por mutante evaluado; `None` si no se evaluó ninguno."""
        if not self.mutantes_evaluados:
            return None
        return self.segundos / len(self.mutantes_evaluados)

    @property
    def evaluados(self) -> int:
        return len(self.mutantes_evaluados)

    @property
    def juzgados(self) -> int:
        """Evaluados en esta campaña más los veredictos reutilizados (F-058)."""
        return self.evaluados + len(self.reutilizados)

    @property
    def timeouts_resueltos(self) -> int:
        """Repasados a los que el repaso SÍ les sacó un veredicto de verdad.

        Lo que sigue en `timeouts` tras el repaso ya no tiene la contención como
        excusa: se midió a solas y aun así agotó el reloj.
        """
        return max(0, self.timeouts_repasados - len(self.timeouts))

    @property
    def fiable(self) -> bool:
        """¿Se puede cerrar una feature con estos números?"""
        return self.aviso_base is None and not self.base_rota


def ejecutar_campania(
    alcance: Alcance,
    ejecutor: object,
    timeout_s: int = TIMEOUT_POR_DEFECTO,
    raiz: str = ".",
    max_mutantes: int | None = None,
    semilla: int | None = None,
    mutantes: list[Mutante] | None = None,
    eco: Callable[[str], None] | None = None,
    ejecutor_de: Callable[[str], object] | None = None,
    centinela: Centinela | None = None,
    comprobar_arbol: bool = True,
    comprobar_base: bool = True,
    timeout_base_s: int | None = None,
    timeout_fijado: bool = False,
    workers: int = 1,
    regla: ReglaMuestreo | None = None,
    seleccion: bool | None = None,
    mapas: dict[ClaveMapa, MapaTests | Degradado] | None = None,
) -> InformeMutacion:
    """Muta el alcance, mutante a mutante, y cuenta cuántos sobreviven.

    Selección de tests (F-019). Con `seleccion=True` y sin `mapas`, mide un
    mapa por ejecutor implicado ANTES de la línea base (R1); con `mapas` (la
    campaña paralela los mide en `wk_0`) usa esos, si su SHA es el de este
    árbol (R6). Con mapa, cada mutante se clasifica por su sentencia: podado,
    subconjunto validado o suite entera (R7–R15). `seleccion=False` es la 1.9.0
    declarando `desactivada` (R19); `None` sin `mapas`, la 1.9.0 tal cual.

    Con `regla` (F-058) los mutantes se eligen con `seleccionar` —uno por línea
    y tope del nivel— y `max_mutantes` no pinta nada; sin ella, el camino de
    siempre con `max_mutantes` y la misma semilla.

    Con `ejecutor_de` se elige el ejecutor fichero a fichero (un monorepo juzga
    cada mutante con la suite de su servicio); sin ella se usa `ejecutor` para
    todo, que es el caso de un repositorio de un solo proyecto.

    Antes de juzgar a nadie corre la LÍNEA BASE —la suite sin mutar nada, en el
    mismo sitio y con el mismo intérprete— y aborta con `BaseRota` si no está
    verde. Y antes de eso se niega a arrancar, con `ArbolSucio`, si algún
    fichero a mutar tiene cambios sin commitear. Las dos comprobaciones se
    pueden desactivar (`comprobar_base`, `comprobar_arbol`) para el único caso
    en que sobran: la campaña paralela, cuyo coordinador ya comprobó el árbol
    principal entero y cuyos worktrees se comprueban uno a uno igualmente.

    `timeout_s` es el SUELO por mutante, no el techo: tras medir la línea base
    se deriva de ella el timeout efectivo (`timeout_derivado`), que nunca baja
    del suelo. Con `timeout_fijado=True` —`--timeout N` en la orden— no se
    deriva nada y `timeout_s` se usa tal cual (R6). La propia línea base corre
    con su reloj aparte y más holgado, `timeout_base_s` (R2).

    Garantía dura: pase lo que pase (excepción, timeout, Ctrl-C, SIGTERM),
    ningún fichero queda mutado en el árbol de trabajo al salir de esta función.
    """
    inicio = time.monotonic()
    suelo = timeout_s
    if timeout_base_s is None:
        timeout_base_s = timeout_de_linea_base(suelo, workers)
    base = Path(raiz)
    fuentes: dict[str, str] = {}

    for fichero in alcance.ficheros():
        ruta = base / fichero
        if ruta.is_file():
            fuentes[fichero] = _leer(ruta)

    if mutantes is None:
        mutantes = []
        for fichero, fuente in fuentes.items():
            mutantes.extend(generar_mutantes(fuente, alcance.lineas[fichero], fichero))

    informe = InformeMutacion(
        feature=alcance.feature,
        alcance=alcance,
        generados=len(mutantes),
        max_mutantes=max_mutantes,
        semilla=semilla,
        sha_head=sha_de_head(raiz),
        timeout_suelo=suelo,
        timeout_efectivo=suelo,
        timeout_fijado=timeout_fijado,
        workers=workers,
        por_fichero=mutantes_por_fichero(alcance, mutantes),
    )

    if regla is not None:
        mutantes, informe.candidatos, informe.max_mutantes = seleccionar(
            list(mutantes), regla, semilla
        )
        informe.regla = regla
        informe.muestreado = len(mutantes) < informe.candidatos
    elif max_mutantes is not None and len(mutantes) > max_mutantes:
        sorteo = random.Random(semilla)
        mutantes = sorted(
            sorteo.sample(mutantes, max_mutantes),
            key=lambda m: (m.fichero, m.linea, m.col, m.operador),
        )
        informe.muestreado = True

    # Nada de esto toca un solo fichero: si algo falla, falla ANTES de mutar.
    if comprobar_arbol:
        guardia_arbol_limpio(raiz, list(fuentes))
    implicados = ejecutores_implicados(list(mutantes), ejecutor, ejecutor_de)
    # F-019: el mapa, antes de la línea base y de juzgar a nadie (R1). La línea
    # base sigue siendo la de siempre: entera y sin instrumentar (R16).
    if seleccion is False:
        mapas = None
        informe.seleccion = SELECCION_DESACTIVADA
    elif seleccion and mapas is None and mutantes:
        ficheros_juzgados = sorted({m.fichero for m in mutantes if m.fichero in fuentes})
        mapas = medir_mapas(ficheros_juzgados, ejecutor, ejecutor_de, raiz, timeout_base_s, eco)
    if mapas is not None:
        mapas = _mapas_vigentes(mapas, informe.sha_head, raiz, eco)
        _anotar_mapas(informe, mapas)
    elif seleccion:
        informe.seleccion = SELECCION_ACTIVA
    if comprobar_base and mutantes:
        informe.segundos_linea_base = comprobar_linea_base(
            implicados, timeout_base_s, eco, workers=workers
        )
        # Aquí es donde la campaña deja de adivinar: la suite limpia ya se ha
        # corrido en el sitio donde se va a juzgar y con los W workers
        # compitiendo, así que lo que tardó ES la medida buena. Antes ese
        # número se tiraba y el timeout salía de un fijo de `rigor.json`.
        if not timeout_fijado:
            timeout_s = timeout_derivado(suelo, informe.segundos_linea_base)
            informe.timeout_efectivo = timeout_s
            if eco is not None and informe.segundos_linea_base:
                peor = max(informe.segundos_linea_base.values())
                eco(
                    f"{MARCA_LINEA_BASE}timeout por mutante: {timeout_s} s "
                    f"= max(suelo {suelo} s, peor línea base {peor:.1f} s "
                    f"× margen {MARGEN_TIMEOUT})"
                )

    def anotar_restos(restos: list[str]) -> None:
        """R14 de F-023: cada `.pyc` que no se pudo borrar, avisado una vez."""
        for resto in restos:
            if resto in informe.pyc_no_borrados:
                continue
            informe.pyc_no_borrados.append(resto)
            ruta_pyc, _, error = resto.partition(": ")
            aviso = (
                f"AVISO: no se pudo borrar {ruta_pyc} ({error}): si el ejecutor no "
                "aísla el bytecode, el mutante pudo juzgarse con uno viejo"
            )
            if eco is not None:
                eco(aviso)
            else:
                print(aviso, file=sys.stderr)

    def restaurar_todo() -> None:
        """Devuelve al disco los fuentes tal y como se leyeron al empezar."""
        for fichero, fuente in fuentes.items():
            ruta = base / fichero
            if ruta.is_file() and _leer(ruta) != fuente:
                anotar_restos(_escribir(ruta, fuente))
            if centinela is not None:
                centinela.soltar(ruta)

    #: R13: veredicto de cada subconjunto distinto corrido SIN mutar.
    subconjuntos_validados: dict[tuple[str, ...], bool] = {}

    try:
        with restauracion_ante_senales(restaurar_todo):
            for indice, mutante in enumerate(mutantes, start=1):
                fuente = fuentes.get(mutante.fichero)
                if fuente is None:
                    continue
                informe.mutantes_evaluados.append(mutante)
                mutada = aplicar_mutante(fuente, mutante)

                if not compila(mutada, mutante.fichero):
                    # R5 de F-023: no compila es defecto del generador, no un
                    # test que caza. Hasta aquí contaba como MUERTO sin que
                    # ningún test lo juzgara. Ni se escribe ni se corre.
                    informe.indeterminados.append(mutante)
                    informe.codigos[clave_de_orden(mutante)] = NO_COMPILA
                    if eco is not None:
                        eco(
                            f"[{indice}/{len(mutantes)}] {INDETERMINADO:13} "
                            f"{mutante.descripcion()} ({NO_COMPILA})"
                        )
                    continue

                elegido = (
                    ejecutor if ejecutor_de is None else ejecutor_de(mutante.fichero)
                )

                # F-019: cómo se juzga, según el mapa de su ejecutor (R7–R13).
                clase, ids = _clase_del_mutante(mapas, elegido, raiz, mutante, fuente)
                if clase == PODAR:
                    # R8: ningún proceso medido ejecuta su sentencia. Ni se
                    # escribe ni se corre: es superviviente, aparte (R24).
                    informe.supervivientes.append(mutante)
                    informe.podados.append(mutante)
                    informe.codigos[clave_de_orden(mutante)] = SIN_EJECUTAR
                    if eco is not None:
                        eco(
                            f"[{indice}/{len(mutantes)}] {SUPERVIVIENTE:13} "
                            f"{mutante.descripcion()} (podado: {SIN_EJECUTAR})"
                        )
                    continue
                usar_subconjunto = False
                if clase == SUBCONJUNTO:
                    # R13: SIN mutar y antes de aplicar nada, una vez por
                    # subconjunto distinto en esta campaña.
                    if ids not in subconjuntos_validados:
                        subconjuntos_validados[ids] = bool(
                            elegido.subconjunto_verde(ids, timeout_s)  # type: ignore[attr-defined]
                        )
                        if not subconjuntos_validados[ids]:
                            informe.subconjuntos_descartados += 1
                    usar_subconjunto = subconjuntos_validados[ids]

                ruta = base / mutante.fichero
                revalidado = False
                try:
                    anotar_restos(_escribir(ruta, mutada))
                    if centinela is not None:
                        centinela.aplicar(ruta, mutante, fuente)
                    veredicto = codigo = None
                    if usar_subconjunto:
                        informe.tamanos_subconjunto.append(len(ids))
                        del_subconjunto, codigo = elegido.juzgar_subconjunto(  # type: ignore[attr-defined]
                            ids, timeout_s
                        )
                        if del_subconjunto == MUERTO:
                            # R14: un test que pasa sin el mutante (R13) cae
                            # con él, y ese test también está en la suite.
                            veredicto = MUERTO
                        else:
                            # R15: cualquier otra cosa se revalida, con el
                            # mutante AÚN aplicado, con la suite entera.
                            revalidado = True
                    if veredicto is None:
                        arranque_suite = time.monotonic()
                        veredicto, codigo = _juzgar(elegido, timeout_s)
                        informe.segundos_suite_entera += time.monotonic() - arranque_suite
                        informe.juzgados_suite_entera += 1
                finally:
                    anotar_restos(_escribir(ruta, fuente))
                    if centinela is not None:
                        centinela.soltar(ruta)

                if veredicto == INDETERMINADO:
                    # La suite ni llegó a juzgar. Puede ser el mutante (rompió
                    # la recolección, dejó la suite sin tests) o puede ser la
                    # base. Cuesta una ejecución más averiguarlo, y es la
                    # diferencia entre un número y una invención.
                    veredicto = _resolver_indeterminado(elegido, timeout_s)

                if revalidado:
                    informe.revalidados += 1
                    if veredicto == MUERTO:
                        informe.muertos_al_revalidar += 1

                if veredicto == SUPERVIVIENTE:
                    informe.supervivientes.append(mutante)
                elif veredicto == TIMEOUT:
                    informe.timeouts.append(mutante)
                elif veredicto == BASE_ROTA:
                    informe.base_rota.append(mutante)
                elif veredicto == INDETERMINADO:
                    informe.indeterminados.append(mutante)
                else:
                    informe.muertos += 1
                if veredicto != MUERTO:
                    # R8: el hecho viaja con el veredicto. De BASE_ROTA se
                    # guarda el código del mutante; el de la base, en el aviso.
                    informe.codigos[clave_de_orden(mutante)] = codigo

                if eco is not None:
                    sufijo = f" (código {codigo})" if veredicto != MUERTO else ""
                    eco(
                        f"[{indice}/{len(mutantes)}] {veredicto:13} "
                        f"{mutante.descripcion()}{sufijo}"
                    )
    finally:
        # Red de seguridad: si algo se torció entre medias, el árbol vuelve a
        # su estado original igualmente.
        restaurar_todo()
        informe.segundos = time.monotonic() - inicio

    # La línea base del arranque protege el arranque. Ésta protege el resto: si
    # la base se rompió a mitad —alguien borró un fichero, el entorno cambió—,
    # cada «muerto» contado desde entonces es un mutante que nadie cazó.
    if comprobar_base and informe.mutantes_evaluados:
        # Con el timeout de la BASE, no con el del mutante: ésta también es una
        # suite limpia y también se corre una vez por worker (R2). Dársela con
        # el reloj corto convertiría en «base expirada» lo que solo es una
        # máquina ocupada, y eso ya es la mentira que arregla R11.
        # F-019 (R20, §8): anclada además a la apertura medida, que ya vio la
        # carga real de los W workers.
        informe.aviso_base = _base_rota_al_final(
            implicados, timeout_de_base_de_cierre(timeout_base_s, informe.segundos_linea_base)
        )
    if informe.base_rota and informe.aviso_base is None:
        informe.aviso_base = (
            f"{len(informe.base_rota)} mutante(s) se juzgaron con la suite rota "
            "por causas ajenas a la mutación: no cuentan ni como muertos ni como "
            "supervivientes, y la campaña no cubre esas líneas."
        )

    return informe


def _clase_del_mutante(
    mapas: dict[ClaveMapa, MapaTests | Degradado] | None,
    ejecutor: object,
    raiz: str,
    mutante: Mutante,
    fuente: str,
) -> tuple[str, tuple[str, ...]]:
    """`(clase, ids)` con que se juzga `mutante` (R7–R12).

    Sin mapa de su ejecutor —sin selección, degradado, otro HEAD— o con un
    ejecutor que no sabe correr subconjuntos, la suite entera de siempre. Con
    un ejecutor sin subconjuntos SÍ se poda: podar no corre nada.
    """
    mapa = mapas.get(clave_de_mapa(ejecutor, raiz)) if mapas else None
    if not isinstance(mapa, MapaTests):
        return (SUITE, ())
    lineas = lineas_de_sentencia(fuente, mutante.linea)
    relativa = ruta_para_ejecutor(mutante.fichero, ejecutor, raiz)
    clase, ids = clasificar(contextos_de(mapa, relativa, lineas), mapa.orden)
    sabe = hasattr(ejecutor, "juzgar_subconjunto") and hasattr(ejecutor, "subconjunto_verde")
    if clase == SUBCONJUNTO and not sabe:
        return (SUITE, ())
    return (clase, ids)


def _resolver_indeterminado(ejecutor: object, timeout_s: int) -> str:
    """¿La suite se rompió por el mutante o ya estaba rota?

    Se corre la línea base ahí mismo. Utilizable (verde o sin tests): la base
    está bien y el mutante sigue `INDETERMINADO`; hasta F-023 eso era una
    muerte, y un mutante que rompe la importación no lo caza ningún test.
    Rota: no se sabe nada de este mutante, `BASE_ROTA`, como siempre.
    """
    correr_base = getattr(ejecutor, "linea_base", None)
    if correr_base is None:
        return BASE_ROTA
    return INDETERMINADO if correr_base(timeout_s).base_utilizable else BASE_ROTA


def _juzgar(ejecutor: object, timeout_s: int) -> tuple[str, str]:
    """`(veredicto, código)` de cualquier ejecutor (R10 de F-023).

    `juzgar` es opcional: los dobles de test y las subclases de proyecto que
    solo saben `ejecutar` siguen valiendo, con el código `n/d`.
    """
    juzgar = getattr(ejecutor, "juzgar", None)
    if juzgar is not None:
        return juzgar(timeout_s)
    return (ejecutor.ejecutar(timeout_s), CODIGO_ND)  # type: ignore[attr-defined]


def compila(fuente: str, fichero: str) -> bool:
    """¿El fuente compila? Lo usan la campaña y la migración del estado (R5, R12)."""
    try:
        compile(fuente, fichero, "exec")
    except (SyntaxError, ValueError):
        return False
    return True


def mensaje_base_expirada_al_final(etiqueta: str, timeout_s: int) -> str:
    """Aviso de una línea base de cierre que se quedó SIN TIEMPO (R11).

    Expirar no es fallar. La suite no dijo que nada esté mal: no llegó a
    terminar. Confundir las dos cosas no es un matiz de redacción: el
    2026-08-21, en la primera ejecución real de la campaña paralela, el arnés
    dijo «Arregla la suite y repite la campaña» sobre una suite impecable y
    mandó al humano a buscar un fallo que no existía. Lo que hay que tocar aquí
    es el reloj —menos workers compitiendo, o más suelo—, no los tests.
    """
    return (
        f"La línea base de cierre EXPIRÓ en {etiqueta}: se agotaron los "
        f"{timeout_s} s concedidos. Ojo, la suite NO falló y NO hay ningún test "
        "roto que buscar: se quedó sin tiempo, que es otra cosa. Aun así los "
        "números de esta campaña no valen, porque no se ha podido comprobar que "
        "la base siguiera verde al terminar.\n"
        "  Qué hacer: baja los workers (--workers N: cada worker corre una suite "
        "entera y todas compiten por la misma máquina) o sube el SUELO "
        "'mutacion.timeout_por_mutante_s' de harness/rigor.json. No toques la "
        "suite."
    )


def _base_rota_al_final(implicados: list[tuple[str, object]], timeout_s: int) -> str | None:
    """Reejecuta la línea base al cerrar. Devuelve el motivo si dejó de estar verde.

    Distingue las dos formas de no estar verde, porque tienen arreglos opuestos:
    EXPIRAR es un problema de reloj (R11) y FALLAR es un problema de suite
    (R12). La consecuencia sí es la misma en los dos casos: el informe queda
    marcado como no fiable y la ejecución sale con 3 (R13).
    """
    for etiqueta, ejecutor in implicados:
        correr_base = getattr(ejecutor, "linea_base", None)
        if correr_base is None:
            continue
        resultado = correr_base(timeout_s)
        if resultado.expirado:
            return mensaje_base_expirada_al_final(etiqueta, timeout_s)
        if not resultado.base_utilizable:
            fallidos = ", ".join(resultado.fallidos()) or f"código {resultado.codigo}"
            return (
                f"La línea base estaba VERDE al empezar y ROJA al terminar en "
                f"{etiqueta} ({fallidos}). La base se rompió durante la campaña, "
                "así que los mutantes contados como «muertos» pueden no estarlo: "
                "estos números NO valen para cerrar una feature. Arregla la suite "
                "y repite la campaña."
            )
    return None


# --- Informe ----------------------------------------------------------------


#: Cabecera con la que se escribe un análisis que todavía nadie ha hecho.
CABECERA_PENDIENTE = "#### Análisis (PENDIENTE del implementer)"

#: Encabezado de la sección de un superviviente en el informe.
PATRON_SUPERVIVIENTE = re.compile(
    r"^### \d+\. `(?P<fichero>.+):(?P<linea>\d+)` \[(?P<operador>[^\]]+)\]$"
)

#: Cabecera de la declaración de un fichero sin mutantes que nadie ha escrito.
CABECERA_DECLARACION_PENDIENTE = "#### Declaración (PENDIENTE del implementer)"

#: Encabezado de la ficha de un fichero sin mutantes (F-026, R17). No casa
#: `PATRON_SUPERVIVIENTE` (`### N. …`), así que `analisis_escritos` no la lee.
PATRON_SIN_MUTANTES = re.compile(r"^### `(?P<fichero>.+)` — \d+ líneas en alcance, 0 mutantes$")

#: Aviso que acompaña a un análisis traído de la campaña anterior.
AVISO_REPUESTO = (
    "> _Análisis traído de la campaña anterior de esta feature: el mutante "
    "volvió a sobrevivir con el mismo operador y el mismo texto. Reléelo si el "
    "código de alrededor ha cambiado._"
)


def clave_de_mutante(fichero: str, operador: str, original: str, mutado: str) -> tuple:
    """Identidad de un superviviente entre dos campañas, SIN el número de línea.

    La línea se mueve en cuanto alguien añade un import más arriba, y aun así
    sigue siendo el mismo mutante: mismo fichero, mismo operador y mismo cambio
    de texto. Incluirla haría que el análisis se perdiera en cuanto el fichero
    respirase, que es justo lo que este mecanismo evita.
    """
    return (fichero, operador, original, mutado)


def analisis_escritos(texto: str) -> dict[tuple, str]:
    """Análisis ya redactados en un informe anterior, indexados por mutante.

    Devuelve solo los que alguien ha escrito de verdad: la plantilla vacía no
    cuenta. Si dos supervivientes comparten clave con análisis distintos, la
    clave se descarta entera —reponer el análisis equivocado sería peor que no
    reponer ninguno—.
    """
    encontrados: dict[tuple, list[str]] = {}
    lineas = texto.splitlines()
    indice = 0
    while indice < len(lineas):
        cabecera = PATRON_SUPERVIVIENTE.match(lineas[indice].strip())
        if cabecera is None:
            indice += 1
            continue
        fichero = cabecera.group("fichero")
        operador = cabecera.group("operador")
        original = mutado = None
        analisis: list[str] = []
        indice += 1
        while indice < len(lineas) and not lineas[indice].startswith("### "):
            linea = lineas[indice]
            if linea.startswith("- Original: `") and original is None:
                original = linea[len("- Original: `") : -1]
            elif linea.startswith("- Mutado:") and mutado is None:
                mutado = linea.split("`", 1)[1][:-1] if "`" in linea else None
            elif linea.startswith("#### Análisis"):
                if linea.strip() != CABECERA_PENDIENTE:
                    analisis = [linea]
                    indice += 1
                    while indice < len(lineas) and not lineas[indice].startswith(
                        ("### ", "## ")
                    ):
                        analisis.append(lineas[indice])
                        indice += 1
                    break
            indice += 1
        if analisis and original is not None and mutado is not None:
            clave = clave_de_mutante(fichero, operador, original, mutado)
            texto_analisis = "\n".join(analisis).rstrip()
            encontrados.setdefault(clave, []).append(texto_analisis)
    return {
        clave: textos[0]
        for clave, textos in encontrados.items()
        if len(set(textos)) == 1
    }


def declaraciones_escritas(texto: str) -> dict[str, str]:
    """Declaraciones de ficheros sin mutantes ya redactadas, por fichero (R19).

    Como `analisis_escritos`: la plantilla pendiente no cuenta, y lo redactado
    va desde su cabecera `#### Declaración` hasta el siguiente `### ` o `## `.
    """
    escritas: dict[str, str] = {}
    lineas = texto.splitlines()
    indice = 0
    while indice < len(lineas):
        ficha = PATRON_SIN_MUTANTES.match(lineas[indice].strip())
        indice += 1
        if ficha is None:
            continue
        while indice < len(lineas) and not lineas[indice].startswith(("### ", "## ")):
            linea = lineas[indice]
            if linea.startswith("#### Declaración") and linea.strip() != (
                CABECERA_DECLARACION_PENDIENTE
            ):
                bloque = []
                while indice < len(lineas) and not lineas[indice].startswith(
                    ("### ", "## ")
                ):
                    bloque.append(lineas[indice])
                    indice += 1
                escritas[ficha.group("fichero")] = "\n".join(bloque).rstrip()
                break
            indice += 1
    return escritas


def celda_de_mutantes(informe: InformeMutacion, fichero: str) -> str:
    """La celda «Mutantes generados» de un fichero en la tabla «Alcance»."""
    if informe.por_fichero is None:
        return "n/d"
    generados = informe.por_fichero.get(fichero, 0)
    if generados == 0 and informe.alcance.lineas.get(fichero):
        return "0 — sin mutantes"
    return str(generados)


def ficheros_sin_mutantes(informe: InformeMutacion) -> list[str]:
    """Ficheros con líneas en alcance y 0 mutantes generados (R17)."""
    if informe.por_fichero is None:
        return []
    return [
        fichero
        for fichero in informe.alcance.ficheros()
        if informe.alcance.lineas[fichero] and informe.por_fichero.get(fichero, 0) == 0
    ]


def seccion_sin_mutantes(informe: InformeMutacion, previas: dict[str, str]) -> list[str]:
    """La sección «Ficheros sin mutantes»; vacía si no hay ninguno (R17, R18)."""
    ficheros = ficheros_sin_mutantes(informe)
    if not ficheros:
        return []
    lineas = [
        "## Ficheros sin mutantes",
        "",
        (
            "Cada uno tiene líneas en alcance y el generador no ha sacado de ellas "
            "ni un mutante: la campaña no las ha juzgado. Declara por qué no hay "
            "nada que mutar (solo declaraciones, cadenas, imports) o qué test de la "
            "fase RED cubre el cambio. El reviewer hace la prueba de control "
            "(`generar_mutantes` sin exclusión de alcance) y ninguna declaración "
            "puede quedarse en `PENDIENTE` al cerrar la feature."
        ),
        "",
    ]
    for fichero in ficheros:
        lineas += [
            (
                f"### `{fichero}` — {len(informe.alcance.lineas[fichero])} líneas "
                "en alcance, 0 mutantes"
            ),
            "",
        ]
        previa = previas.get(fichero)
        if previa is None:
            lineas += [
                CABECERA_DECLARACION_PENDIENTE,
                "",
                "> Por qué no hay nada que mutar, o qué test lo cubre: PENDIENTE.",
                "",
            ]
        else:
            lineas += [previa, ""]
    return lineas


#: Prefijos de las filas del informe cuyo valor depende de CÓMO se corrió la
#: campaña —el reloj y las condiciones— y no de lo que midió. Vive aquí, al lado
#: de quien las escribe, para que quien añada una fila así la vea y la declare:
#: cuando esta lista se mantenía a mano dentro de un test de paridad
#: serie/paralelo, la fila que añadió una versión posterior se quedó fuera y
#: dejó el test flaky durante semanas. Se compara por PREFIJO a propósito:
#: `| Línea base (s) — \`etiqueta\`` lleva pegada la etiqueta del ejecutor.
#:
#: `Workers` y `Timeout efectivo` entraron después: una campaña en serie y una
#: paralela sobre el mismo commit tienen que dar informes comparables, y esas
#: dos filas no coinciden nunca. El `Suelo configurado` NO entra: sale de
#: `rigor.json`, es el mismo en las dos, y que deje de coincidir es una
#: diferencia real que hay que ver.
FILAS_DE_RELOJ: tuple[str, ...] = (
    "Generado por",
    "| Tiempo total",
    "| Línea base (s)",
    "| Media por mutante evaluado (s)",
    "| Timeout efectivo por mutante (s)",
    "| Workers",
    "| Timeouts repasados en serie",
    # F-019: tiempos del mapa y de la suite entera, y los subconjuntos
    # descartados, que cada worker valida por su cuenta (en paralelo, el mismo
    # subconjunto rojo cuenta una vez por worker que lo prueba).
    "| Medición del mapa (s)",
    "| Tiempo ahorrado por la poda",
    "| Media por mutante juzgado con la suite entera (s)",
    "| Subconjuntos descartados",
)

#: Comentario de ruta con el que arranca todo informe. Cambia con el nombre del
#: fichero, no con lo medido, así que tampoco entra en la comparación.
_COMENTARIO_DE_RUTA = "<!-- "


def lineas_comparables(texto: str) -> list[str]:
    """Las líneas de un informe que dos campañas equivalentes deben compartir.

    Descarta las de `FILAS_DE_RELOJ` y el comentario de ruta de la cabecera. Lo
    que queda es el resultado de la medición —alcance, totales, SHA, muestreo y
    fichas de supervivientes—, que sí tiene que coincidir entre la campaña en
    serie y la paralela.
    """
    return [
        linea
        for linea in texto.splitlines()
        if not linea.startswith(FILAS_DE_RELOJ)
        and not linea.startswith(_COMENTARIO_DE_RUTA)
    ]


def comando_de(informe: InformeMutacion) -> str:
    """El comando que reproduce esta campaña: base y workers incluidos.

    Sin `--workers` el comando de la cabecera no reproduce nada: la misma
    feature medida con 1 worker y con 16 da tiempos que se diferencian en un
    factor 4 y, hasta que la campaña repasa sus timeouts, veredictos distintos.

    Y sin `--base` reproduce **otro alcance**, que es peor: cuando la rama de la
    feature nace de otra rama de feature en vez de `dev`, el diff contra `dev`
    arrastra las líneas de la feature madre, así que ni el número de mutantes ni
    la lista de supervivientes son comparables. Pasó de verdad el 2026-09-06.

    Solo se escribe lo que no es el valor de siempre: repetir `--base dev` en
    todos los informes es ruido que acaba haciendo que nadie lea la línea.
    """
    comando = f"python -m harness.mutacion --feature {informe.feature}"
    if informe.base is not None and informe.base != BASE_POR_DEFECTO:
        comando += f" --base {informe.base}"
    if informe.workers is not None:
        comando += f" --workers {informe.workers}"
    # F-019 (R19): la cabecera reproduce el modo. Apagada es el defecto y no se
    # escribe, salvo que la clave de rigor la encendiera: entonces la apagó la orden.
    if informe.seleccion in (SELECCION_ACTIVA, SELECCION_DEGRADADA):
        comando += " --con-seleccion"
    elif informe.seleccion == SELECCION_DESACTIVADA and informe.seleccion_por_rigor:
        comando += " --sin-seleccion"
    return comando


def fila_del_repaso(informe: InformeMutacion) -> str:
    """Fila de totales que cuenta qué pasó con los mutantes en `timeout`.

    Se imprime SIEMPRE, también cuando no hubo ninguno: una fila ausente se lee
    como descuido, y un `0` a secas no distingue «no hizo falta repasar» de «este
    arnés no repasa». Las tres redacciones son los tres casos reales.
    """
    if informe.timeouts_repasados:
        return (
            f"| Timeouts repasados en serie | {informe.timeouts_repasados} — "
            f"{informe.timeouts_resueltos} con veredicto tras el repaso, "
            f"{len(informe.timeouts)} en timeout todavía |"
        )
    if informe.timeouts:
        return (
            "| Timeouts repasados en serie | 0: campaña en serie, el reloj ya "
            "midió a cada mutante a solas |"
        )
    return "| Timeouts repasados en serie | 0: ningún mutante agotó el reloj |"


def filas_de_muestreo(informe: InformeMutacion) -> list[str]:
    """Filas «Un mutante por línea» y «Muestreo» del informe (R9–R11).

    Sin regla (F-058) salen las de siempre, byte a byte: un informe de antes y
    uno de ahora sobre la misma campaña tienen que poder compararse.
    """
    regla = informe.regla
    if regla is None:
        if informe.muestreado:
            return [
                (
                    f"| Muestreo | sí — {informe.evaluados} de {informe.generados} "
                    f"mutantes, semilla `{informe.semilla}`, nivel "
                    f"`{informe.nivel or 'n/d'}` |"
                )
            ]
        return ["| Muestreo | no: campaña completa |"]

    candidatos = informe.candidatos if informe.candidatos is not None else informe.generados
    filas = [
        f"| Un mutante por línea | sí — {informe.generados} generados → {candidatos} "
        "candidatos, uno por línea |"
        if regla.por_linea
        else "| Un mutante por línea | no |"
    ]
    if informe.muestreado:
        filas.append(
            f"| Muestreo | sí — {informe.juzgados} de {candidatos} candidatos, "
            f"semilla `{informe.semilla}`, nivel `{informe.nivel or 'n/d'}`; tope: "
            f"{regla.motivo(candidatos, informe.nivel)} |"
        )
    elif informe.max_mutantes is not None:
        filas.append(
            f"| Muestreo | no: campaña completa ({candidatos} candidatos ≤ tope "
            f"{informe.max_mutantes} del nivel `{informe.nivel or 'n/d'}`) |"
        )
    else:
        filas.append("| Muestreo | no: campaña completa |")
    return filas


def cota_regla_del_tres(evaluados: int) -> str:
    """Cota superior al 95 % de la tasa real de supervivientes con 0 en k (R12).

    Informativa: no la consulta ninguna puerta. Dice cuánto puede esconder una
    muestra limpia, que es lo que hay que saber para decidir si pedir la entera.
    """
    return (
        f"{CERO_EN_LA_MUESTRA} {evaluados} → tasa real < 3/{evaluados} "
        f"({300 / evaluados:.1f} %) al 95 % (regla del tres)."
    )


#: Arranque de la frase de la cota: el reviewer la busca por aquí.
CERO_EN_LA_MUESTRA = "0 supervivientes en"


def filas_de_codigos(informe: InformeMutacion) -> list[str]:
    """Tabla «No muertos: código de salida» (R9 de F-023); vacía sin no muertos.

    Una fila por mutante no muerto, ordenada por `clave_de_orden`: el hecho
    (código) junto a su lectura (veredicto), para que un indeterminado o un
    superviviente se pueda revisar sin reejecutar la campaña.
    """
    grupos = (
        (SUPERVIVIENTE, informe.supervivientes),
        (TIMEOUT, informe.timeouts),
        (INDETERMINADO, informe.indeterminados),
        (BASE_ROTA, informe.base_rota),
    )
    no_muertos = sorted(
        ((m, veredicto) for veredicto, lista in grupos for m in lista),
        key=lambda par: clave_de_orden(par[0]),
    )
    if not no_muertos:
        return []
    filas = [
        "## No muertos: código de salida",
        "",
        "| Fichero:línea | Operador | Veredicto | Código |",
        "|---|---|---|---|",
    ]
    for mutante, veredicto in no_muertos:
        codigo = informe.codigos.get(clave_de_orden(mutante), CODIGO_ND)
        filas.append(
            f"| `{mutante.fichero}:{mutante.linea}` | {mutante.operador} | "
            f"{veredicto} | {codigo} |"
        )
    return [*filas, ""]


def fila_de_supervivientes(informe: InformeMutacion) -> str:
    """`| Supervivientes | N |`, desglosada en podados y medidos con selección (R24)."""
    total = len(informe.supervivientes)
    if informe.seleccion is None:
        return f"| Supervivientes | {total} |"
    if not informe.tests_en_suite:
        return f"| Supervivientes | {total} (todos medidos: sin mapa no se poda) |"
    podados = len(informe.podados)
    return (
        f"| Supervivientes | {total} ({podados} podados sin ejecutar, "
        f"{total - podados} medidos) |"
    )


def _por_etiqueta(valores: dict, formato: str) -> str:
    return "; ".join(
        f"`{etiqueta}`: {format(valor, formato)}" for etiqueta, valor in sorted(valores.items())
    )


def filas_de_seleccion(informe: InformeMutacion) -> list[str]:
    """Filas de la selección de tests en «Totales» (R25, R26); vacías sin declararla.

    Lo que no se midió dice `n/d`, nunca un cero que parezca medido: sin un
    solo mapa (desactivada, o degradada en todos los ejecutores) no hay
    podados ni subconjuntos que contar.
    """
    if informe.seleccion is None:
        return []
    if informe.seleccion == SELECCION_DESACTIVADA:
        modo = (
            "desactivada (`--sin-seleccion`, la clave la encendía): todo con la "
            "suite entera, como la 1.9.0"
            if informe.seleccion_por_rigor
            else "desactivada (por defecto): todo con la suite entera, como la 1.9.0"
        )
    elif informe.seleccion == SELECCION_DEGRADADA:
        motivos = "; ".join(
            f"`{etiqueta}`: {motivo}"
            for etiqueta, motivo in sorted(informe.motivos_degradado.items())
        )
        modo = f"degradada — {motivos}"
    else:
        modo = "activa — mapa línea -> tests, poda y subconjuntos validados"
    hay_mapa = bool(informe.tests_en_suite)
    nd = "n/d"
    if hay_mapa and informe.tamanos_subconjunto:
        media_sub = sum(informe.tamanos_subconjunto) / len(informe.tamanos_subconjunto)
        tamano = f"{media_sub:.1f} tests ({len(informe.tamanos_subconjunto)} mutantes)"
    elif hay_mapa:
        tamano = "n/d (ningún mutante se juzgó con subconjunto)"
    else:
        tamano = nd
    peor_base = max(informe.segundos_linea_base.values(), default=None)
    ahorro = (
        f"{len(informe.podados) * peor_base:.1f}"
        if hay_mapa and peor_base is not None
        else nd
    )
    media_suite = (
        f"{informe.segundos_suite_entera / informe.juzgados_suite_entera:.1f} "
        f"({informe.juzgados_suite_entera} mutantes)"
        if informe.juzgados_suite_entera
        else nd
    )
    return [
        f"| Selección de tests | {modo} |",
        f"| SHA del mapa | `{informe.sha_mapa}` |" if informe.sha_mapa else "| SHA del mapa | n/d |",
        f"| Medición del mapa (s) | {_por_etiqueta(informe.segundos_mapa, '.1f') or nd} |",
        f"| Tests en la suite | {_por_etiqueta(informe.tests_en_suite, 'd') or nd} |",
        f"| Tamaño medio del subconjunto | {tamano} |",
        (
            f"| Revalidados con la suite entera | {informe.revalidados} "
            f"({informe.muertos_al_revalidar} murieron al revalidar) |"
            if hay_mapa
            else "| Revalidados con la suite entera | n/d |"
        ),
        f"| Subconjuntos descartados | {informe.subconjuntos_descartados if hay_mapa else nd} |",
        f"| Podados (sin ejecutar) | {len(informe.podados) if hay_mapa else nd} |",
        f"| Tiempo ahorrado por la poda (s) — derivado: podados × línea base | {ahorro} |",
        f"| Media por mutante juzgado con la suite entera (s) | {media_suite} |",
    ]


#: Sección «Cómo se juzgó» con la selección apagada (R19, opción «b»).
COMO_SE_JUZGO_SIN_SELECCION = (
    "## Cómo se juzgó",
    "",
    (
        "- Cada mutante con la **suite entera**, como en la 1.9.0: la selección de "
        "tests está apagada por defecto (en la suite del propio arnés costó más de "
        "lo que ahorró). Se enciende con `--con-seleccion` en la orden o con "
        "`mutacion.seleccion_de_tests: true` en `harness/rigor.local.json`; la "
        "orden manda sobre la clave."
    ),
    "",
)

#: Sección «Cómo se juzgó» (R27): el porqué de la asimetría y del timeout.
COMO_SE_JUZGO = (
    "## Cómo se juzgó",
    "",
    (
        "- **PODADO**: ningún proceso medido ejecuta la sentencia del mutante, así "
        "que no puede cambiar ninguna ejecución; es superviviente sin escribirlo ni "
        "correr nada. Un PODADO necesita la misma justificación escrita que uno "
        "medido. Riesgo residual: un subproceso que no hereda el entorno o usa otro "
        "intérprete no se mide, y sus líneas parecerían no ejecutadas; "
        "`--sin-seleccion` lo descarta."
    ),
    (
        "- El **muerto** del subconjunto **no se revalida**: ese subconjunto se "
        "corrió antes SIN mutar y salió verde, así que el test que cae lo hace por "
        "el mutante, y ese test también está en la suite entera."
    ),
    (
        "- Lo que el subconjunto no mata (superviviente, timeout, indeterminado) "
        "**sí se revalida** con la suite entera y el mutante aún aplicado: que no "
        "caiga ninguno de sus tests no prueba que no caiga ninguno de la suite, y "
        "el veredicto que cuenta es el de la suite entera."
    ),
    (
        "- El **timeout** por mutante sigue saliendo de la **línea base** de la "
        "suite entera: es la única medida tomada con la contención de los W "
        "workers; un subconjunto no tiene base propia, medirla costaría más de lo "
        "que ahorra, y un mutante que cuelga cuelga igual con dos tests que con "
        "doscientos."
    ),
    "",
)


def escribir_informe(informe: InformeMutacion, ruta: Path) -> None:
    """Escribe el informe de la campaña en Markdown.

    Si ya había un informe de esta feature, los análisis de supervivientes que
    alguien hubiera escrito se conservan. Una campaña se repite muchas veces
    —tras un merge, tras cambiar el arnés, tras tocar un test— y sobrescribir
    ese trabajo con la plantilla vacía borra evidencia que el reviewer exige y
    que a veces el humano ya ha dado por buena.
    """
    alcance = informe.alcance
    anterior = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    previos = analisis_escritos(anterior)
    declaraciones = declaraciones_escritas(anterior)
    lineas: list[str] = [
        f"<!-- {ruta.as_posix()} -->",
        f"# {informe.feature} · Campaña de mutación",
        "",
        f"Generado por `{comando_de(informe)}` "
        f"el {datetime.now().strftime('%Y-%m-%d %H:%M')}.",
        "",
    ]
    if not informe.fiable:
        # Lo primero que se lee, y en negrita: un informe cuyos números no valen
        # tiene que decirlo antes que nada, o el reviewer suma la tabla y cierra.
        lineas += [
            "> ## ⚠ CAMPAÑA NO VÁLIDA",
            ">",
            f"> {informe.aviso_base}",
            ">",
            "> **No cierres la feature con estos números.** Arregla la línea base "
            "y repite la campaña.",
            "",
        ]
    # Un alcance declarado a mano (`--ficheros`) no tiene diff detrás: enseñar
    # dos refs entre backticks haría creer que se comparó algo con algo.
    if alcance.origen == ORIGEN_FICHEROS:
        origen_del_alcance = (
            f"Origen del diff: **{ORIGEN_FICHEROS}** (alcance declarado en la orden)."
        )
    else:
        origen_del_alcance = (
            f"Origen del diff: **{alcance.origen}** "
            f"(`{alcance.ref_diff[0]}` .. `{alcance.ref_diff[1]}`)."
        )
    lineas += [
        "## Alcance",
        "",
        origen_del_alcance,
        "",
        "| Fichero | Líneas en alcance | Mutantes generados |",
        "|---|---|---|",
    ]
    for fichero in alcance.ficheros():
        lineas.append(
            f"| `{fichero}` | {len(alcance.lineas[fichero])} | "
            f"{celda_de_mutantes(informe, fichero)} |"
        )
    lineas += [
        f"| **Total** | **{alcance.total_lineas()}** | **{informe.generados}** |",
        "",
        "## Totales",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Mutantes generados | {informe.generados} |",
        (
            f"| Mutantes evaluados | {informe.evaluados} (+ "
            f"{len(informe.reutilizados)} veredictos reutilizados) |"
            if informe.reutilizados
            else f"| Mutantes evaluados | {informe.evaluados} |"
        ),
        f"| Muertos | {informe.muertos + len(informe.reutilizados)} |",
        fila_de_supervivientes(informe),
        f"| Timeouts | {len(informe.timeouts)} |",
        f"| Indeterminados | {len(informe.indeterminados)} |",
        fila_del_repaso(informe),
        f"| Sin veredicto (base rota) | {len(informe.base_rota)} |",
        f"| Tiempo total | {informe.segundos:.1f} s |",
    ]
    # RM1: sin el commit medido, un informe sigue pareciendo válido después de
    # que la rama crezca mil líneas. RM2: con la línea base y la media por
    # mutante juntas, una campaña imposiblemente rápida se ve leyendo. Las tres
    # filas se imprimen SIEMPRE; lo que no se sabe se dice `n/d`, porque un cero
    # se lee como medición y una fila ausente, como descuido.
    lineas.append(
        f"| SHA de HEAD medido | `{informe.sha_head}` |"
        if informe.sha_head
        else "| SHA de HEAD medido | n/d |"
    )
    if informe.segundos_linea_base:
        for etiqueta, segundos in sorted(informe.segundos_linea_base.items()):
            lineas.append(f"| Línea base (s) — `{etiqueta}` | {segundos:.1f} |")
    else:
        lineas.append("| Línea base (s) | n/d |")
    media = informe.segundos_por_mutante
    lineas.append(
        f"| Media por mutante evaluado (s) | {media:.1f} |"
        if media is not None
        else "| Media por mutante evaluado (s) | n/d |"
    )
    # R4. El timeout por mutante ya no es el fijo de `rigor.json`: se deriva
    # de la línea base medida. Sin declararlo, los tiempos de dos
    # campañas dejan de ser comparables sin que nadie se entere, y el reviewer
    # compara peras con manzanas creyendo que compara lo mismo.
    if informe.timeout_efectivo is None:
        lineas.append("| Timeout efectivo por mutante (s) | n/d |")
    elif informe.timeout_fijado:
        lineas.append(
            f"| Timeout efectivo por mutante (s) | {informe.timeout_efectivo} "
            "— fijado a mano con `--timeout`, sin derivar |"
        )
    else:
        lineas.append(
            f"| Timeout efectivo por mutante (s) | {informe.timeout_efectivo} "
            f"— derivado de la línea base × {MARGEN_TIMEOUT} |"
        )
    lineas.append(
        f"| Suelo configurado (s) | {informe.timeout_suelo} |"
        if informe.timeout_suelo is not None
        else "| Suelo configurado (s) | n/d |"
    )
    lineas.append(
        f"| Workers | {informe.workers} |"
        if informe.workers is not None
        else "| Workers | n/d |"
    )
    lineas += filas_de_muestreo(informe)
    if informe.incremental_desde is not None:
        lineas.append(
            f"| Modo | incremental desde `{informe.incremental_desde}` — "
            f"{len(informe.reutilizados)} reutilizados, "
            f"{informe.evaluados - informe.control} reevaluados, "
            f"{informe.control} de control |"
        )
    lineas += filas_de_seleccion(informe)
    if informe.seleccion is not None:
        apagada = informe.seleccion == SELECCION_DESACTIVADA
        lineas += ["", *(COMO_SE_JUZGO_SIN_SELECCION if apagada else COMO_SE_JUZGO)]

    lineas += ["", "## Supervivientes", ""]
    if not informe.supervivientes:
        lineas += ["Ninguno: cada mutación aplicada la cazó al menos un test.", ""]
        if informe.muestreado and informe.juzgados:
            lineas += [cota_regla_del_tres(informe.juzgados), ""]
    else:
        lineas += [
            "Cada superviviente es una línea que ningún test comprueba de verdad, "
            "o una mutación equivalente. Distinguirlo es trabajo del implementer: "
            "ningún análisis puede quedarse sin completar al cerrar la feature.",
            "",
        ]
        for numero, mutante in enumerate(informe.supervivientes, start=1):
            lineas += [
                f"### {numero}. `{mutante.fichero}:{mutante.linea}` "
                f"[{mutante.operador}]",
                "",
                f"- Original: `{mutante.original}`",
                f"- Mutado:   `{mutante.mutado}`",
            ]
            if informe.seleccion is not None:
                # R24: el PODADO no se corrió; el MEDIDO, sí.
                lineas.append(
                    "- Juicio: PODADO (sin ejecutar: ningún proceso medido ejecuta "
                    "su sentencia)"
                    if mutante in informe.podados
                    else "- Juicio: MEDIDO"
                )
            lineas.append("")
            previo = previos.get(
                clave_de_mutante(
                    mutante.fichero, mutante.operador, mutante.original, mutante.mutado
                )
            )
            if previo is None:
                lineas += [
                    CABECERA_PENDIENTE,
                    "",
                    "> Por qué ningún test lo caza: PENDIENTE.",
                    "> Decisión: ¿test nuevo o mutante equivalente justificado?",
                    "",
                ]
            else:
                lineas += [previo, "", AVISO_REPUESTO, ""]

    lineas += filas_de_codigos(informe)

    if informe.timeouts:
        lineas += ["## Timeouts", ""]
        if informe.timeouts_repasados:
            lineas += [
                (
                    "Estos agotaron el reloj **también al repasarlos en serie**, "
                    "uno a uno y sin nadie compitiendo por la máquina: la "
                    "contención ya no los explica. Míralos como un cuelgue de "
                    "verdad, no como ruido."
                ),
                "",
            ]
        else:
            lineas += [
                (
                    "Campaña sin repaso en serie: con un solo evaluador el reloj "
                    "ya midió a cada mutante a solas, así que estos timeouts son "
                    "suyos."
                ),
                "",
            ]
        for mutante in informe.timeouts:
            # `descripcion()` ya empieza por `fichero:linea`: anteponerlo daba
            # `- \`a.py:3\` a.py:3 [op] x -> y`. Nadie lo había leído nunca
            # porque la sección entera estaba sin test (R20).
            lineas.append(
                f"- `{mutante.fichero}:{mutante.linea}` [{mutante.operador}] "
                f"{mutante.original} -> {mutante.mutado}"
            )
        lineas.append("")

    if informe.base_rota:
        lineas += [
            "## Sin veredicto: la suite estaba rota por su cuenta",
            "",
            "De estos mutantes no se sabe nada. La suite falló sin que la "
            "mutación tuviera que ver, así que **no** cuentan como muertos: esas "
            "líneas se quedan sin comprobar hasta que la base vuelva a estar "
            "verde y la campaña se repita.",
            "",
        ]
        for mutante in informe.base_rota:
            lineas.append(f"- `{mutante.fichero}:{mutante.linea}` {mutante.descripcion()}")
        lineas.append("")

    if informe.pyc_no_borrados:
        lineas += ["## Bytecode que no se pudo borrar", ""]
        lineas += [f"- `{resto}`" for resto in informe.pyc_no_borrados]
        lineas.append("")

    # F-026: al final, tras todo lo que dice cómo se juzgó lo que SÍ se mutó.
    lineas += seccion_sin_mutantes(informe, declaraciones)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# --- Repetición incremental (F-058) -----------------------------------------
#
# Reutilizar el veredicto de un muerto es seguro solo si la producción no ha
# cambiado (la lista de mutantes y la muestra con semilla son idénticas, y se
# comprueba recalculándolas) y los tests solo han crecido. Ese es el caso de la
# repetición más común: cerrar supervivientes con tests nuevos y volver a medir.
# Una línea añadida que neutralice un test la vigila la muestra de control.

#: Versión del formato del estado: otra versión es un estado que no se entiende.
VERSION_ESTADO = 1

#: Marca del criterio de muerte con que se juzgó el estado (F-023, decisión
#: B+): muerto = código 1. Un estado sin ella es heredado y `--incremental` lo
#: migra en memoria (`migrar_estado`). No sube `VERSION_ESTADO`: un arnés
#: anterior ignora la clave y, si ve un `indeterminado`, rechaza el estado y
#: mide entero, que es degradar a seguro.
CRITERIO_ESTADO = "codigo_1"

#: Qué ha cambiado desde el SHA del estado (`clasificar_delta`).
DELTA_VIGENTE = "vigente"
DELTA_SOLO_TESTS = "solo_tests"
DELTA_CODIGO = "codigo"

#: Ficheros de papeleo exactos que no cambian el veredicto de ningún mutante.
_PAPELEO_EXACTO = ("BACKLOG.md", "harness/features.json")


def ruta_de_estado(informe_md: Path) -> Path:
    """El estado vive junto al informe: `mutacion_F-XXX.md` → `.json`."""
    return informe_md.with_suffix(".json")


def _clave_de_estado(mutante: Mutante) -> tuple:
    return (mutante.fichero, mutante.linea, mutante.col, mutante.operador,
            mutante.original, mutante.mutado)


def _veredictos(informe: InformeMutacion) -> list[tuple[Mutante, str]]:
    """Cada mutante juzgado con su veredicto, en el orden estable del informe.

    Los muertos no se guardan uno a uno en el informe: son los evaluados que no
    salieron ni supervivientes, ni en timeout, ni sin veredicto.
    """
    otros = {_clave_de_estado(m): SUPERVIVIENTE for m in informe.supervivientes}
    otros.update({_clave_de_estado(m): TIMEOUT for m in informe.timeouts})
    otros.update({_clave_de_estado(m): BASE_ROTA for m in informe.base_rota})
    otros.update({_clave_de_estado(m): INDETERMINADO for m in informe.indeterminados})
    juzgados = [*informe.mutantes_evaluados, *informe.reutilizados]
    return [
        (m, otros.get(_clave_de_estado(m), MUERTO))
        for m in sorted(juzgados, key=clave_de_orden)
    ]


def escribir_estado(informe: InformeMutacion, ruta: Path) -> bool:
    """Escribe el estado de la campaña (R14) si es fiable; dice si lo escribió.

    Una campaña NO VÁLIDA no deja estado: sus veredictos no valen para nada, y
    reutilizarlos sería justo lo que esa cabecera prohíbe.
    """
    if not informe.fiable:
        return False
    datos = {
        "version": VERSION_ESTADO,
        "criterio": CRITERIO_ESTADO,
        "fiable": True,
        "feature": informe.feature,
        "sha": informe.sha_head,
        "nivel": informe.nivel,
        "regla": informe.regla.como_dict() if informe.regla is not None else None,
        "semilla": informe.semilla,
        "generados": informe.generados,
        "candidatos": informe.candidatos,
        "evaluados": [
            {"fichero": m.fichero, "linea": m.linea, "col": m.col,
             "operador": m.operador, "original": m.original, "mutado": m.mutado,
             "veredicto": veredicto}
            for m, veredicto in _veredictos(informe)
        ],
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return True


def leer_estado(ruta: Path) -> dict | None:
    """El estado de la campaña anterior, o `None` si no hay o no se entiende."""
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return datos if isinstance(datos, dict) else None


def _es_papeleo(ruta: str) -> bool:
    return (
        ruta.startswith(("progress/", "specs/"))
        or ruta.endswith(".md")
        or ruta in _PAPELEO_EXACTO
    )


def _es_test(ruta: str) -> bool:
    nombre = ruta.rsplit("/", 1)[-1]
    return (
        ruta.startswith("tests/")
        or "/tests/" in ruta
        or (nombre.startswith("test_") and nombre.endswith(".py"))
        or nombre == "conftest.py"
    )


def clasificar_delta(raiz: str, sha: str) -> str:
    """¿Qué ha cambiado entre `sha` y HEAD? `vigente`, `solo_tests` o `codigo`.

    `vigente`: solo papeleo, ningún veredicto puede haber cambiado. `solo_tests`:
    papeleo y tests que solo crecen (cero líneas borradas). Cualquier otra cosa
    —producción, configuración, un binario, un test con líneas borradas, o un
    `sha` que no es antepasado de HEAD— es `codigo`, y obliga a medir entero.
    """
    codigo, _ = _git_en(raiz, "merge-base", "--is-ancestor", sha, "HEAD")
    if codigo != 0:
        return DELTA_CODIGO
    codigo, salida = _git_en(
        raiz, "-c", "core.quotepath=off", "diff", "--numstat", "--no-renames", sha, "HEAD"
    )
    if codigo != 0:
        return DELTA_CODIGO
    resultado = DELTA_VIGENTE
    for linea in salida.splitlines():
        partes = linea.split("\t", 2)
        if len(partes) != 3:
            continue
        anadidas, borradas, ruta = partes
        if anadidas == "-" or borradas == "-":
            return DELTA_CODIGO  # binario: no se sabe qué cambió
        if _es_papeleo(ruta):
            continue
        if _es_test(ruta) and borradas == "0":
            resultado = DELTA_SOLO_TESTS
            continue
        return DELTA_CODIGO
    return resultado


@dataclass
class PlanIncremental:
    """Qué se reevalúa y qué se reutiliza en una repetición incremental."""

    desde: str
    reevaluar: list[Mutante]
    control: list[Mutante]
    reutilizados: list[Mutante]
    generados: int
    candidatos: int
    limite: int | None
    #: Mutantes de HEAD por fichero (F-026, R16), solo de los ficheros que dan
    #: alguno: `componer_incremental` pone los ceros con el alcance del informe.
    #: `None` en un plan construido sin él.
    por_fichero: dict[str, int] | None = None


def plan_incremental(
    estado: dict,
    regla: ReglaMuestreo | None,
    semilla: int | None,
    nivel: str | None,
    mutantes_en_head: list[Mutante],
    control: tuple[float, int] = (CONTROL_FRACCION, CONTROL_MINIMO),
) -> PlanIncremental | str:
    """El plan de la repetición, o el MOTIVO por el que hay que medir entero.

    Exige que nivel, regla y semilla sean los del estado, y que `seleccionar`
    sobre los mutantes de HEAD dé exactamente los evaluados del estado: si la
    muestra no es la misma, sus veredictos hablan de otros mutantes.
    """
    if estado.get("version") != VERSION_ESTADO:
        return f"el estado es de otra versión ({estado.get('version')!r})"
    if estado.get("fiable") is not True:
        return "el estado no es de una campaña fiable"
    if estado.get("nivel") != nivel:
        return f"el nivel cambió ({estado.get('nivel')!r} → {nivel!r})"
    if estado.get("regla") != (regla.como_dict() if regla is not None else None):
        return "la regla de muestreo cambió"
    if estado.get("semilla") != semilla:
        return f"la semilla cambió ({estado.get('semilla')!r} → {semilla!r})"
    if regla is not None and semilla is None:
        return "sin semilla fija la muestra no es reproducible"

    if regla is not None:
        elegidos, candidatos, limite = seleccionar(mutantes_en_head, regla, semilla)
    else:
        elegidos, candidatos, limite = list(mutantes_en_head), len(mutantes_en_head), None
    por_clave = {_clave_de_estado(m): m for m in elegidos}
    veredictos = {
        (e.get("fichero"), e.get("linea"), e.get("col"), e.get("operador"),
         e.get("original"), e.get("mutado")): e.get("veredicto")
        for e in estado.get("evaluados", [])
        if isinstance(e, dict)
    }
    if set(por_clave) != set(veredictos) or len(elegidos) != len(veredictos):
        return "la muestra que sale en HEAD no es la del estado"
    if any(
        v not in (MUERTO, SUPERVIVIENTE, TIMEOUT, INDETERMINADO) for v in veredictos.values()
    ):
        return "el estado trae mutantes sin veredicto"

    # Supervivientes, timeouts e indeterminados (F-023) se reevalúan: de
    # ninguno de ellos hay una muerte que reutilizar.
    reevaluar = [m for m in elegidos if veredictos[_clave_de_estado(m)] != MUERTO]
    muertos = [m for m in elegidos if veredictos[_clave_de_estado(m)] == MUERTO]
    fraccion, minimo = control
    cuantos = min(
        len(muertos), max(minimo, math.ceil(Fraction(str(fraccion)) * len(muertos)))
    )
    sorteados = set(random.Random(semilla).sample(muertos, cuantos))
    return PlanIncremental(
        desde=str(estado.get("sha")),
        reevaluar=reevaluar,
        control=[m for m in muertos if m in sorteados],
        reutilizados=[m for m in muertos if m not in sorteados],
        generados=len(mutantes_en_head),
        candidatos=candidatos,
        limite=limite,
        por_fichero=dict(Counter(m.fichero for m in mutantes_en_head)),
    )


def migrar_estado(
    estado: dict, mutantes_en_head: list[Mutante], raiz: str = "."
) -> tuple[dict, int]:
    """Estado anterior a F-023 juzgado con el criterio nuevo, y cuántos cambian.

    Pura e idempotente: con `criterio` devuelve el MISMO estado y 0. Sin él,
    una COPIA en la que cada `muerto` cuyo mutante de HEAD (misma
    `_clave_de_estado`) no compila sobre el fuente de `raiz` pasa a
    `indeterminado` —el arnés de antes lo daba por muerto sin juzgarlo—. Sin
    correr ninguna suite y sin escribir nada. Una entrada sin mutante en HEAD
    se deja tal cual: ya la rechaza `plan_incremental`.

    Límite aceptado (decisión B+): un muerto heredado por código 2, 3 o 4 no
    se distingue aquí de uno legítimo; lo vigila la muestra de control.
    """
    if "criterio" in estado:
        return (estado, 0)
    por_clave = {_clave_de_estado(m): m for m in mutantes_en_head}
    fuentes: dict[str, str | None] = {}
    copia = json.loads(json.dumps(estado))
    cambiados = 0
    for entrada in copia.get("evaluados", []):
        if not isinstance(entrada, dict) or entrada.get("veredicto") != MUERTO:
            continue
        mutante = por_clave.get(
            (entrada.get("fichero"), entrada.get("linea"), entrada.get("col"),
             entrada.get("operador"), entrada.get("original"), entrada.get("mutado"))
        )
        if mutante is None:
            continue
        if mutante.fichero not in fuentes:
            ruta = Path(raiz) / mutante.fichero
            fuentes[mutante.fichero] = _leer(ruta) if ruta.is_file() else None
        fuente = fuentes[mutante.fichero]
        if fuente is None or compila(aplicar_mutante(fuente, mutante), mutante.fichero):
            continue
        entrada["veredicto"] = INDETERMINADO
        cambiados += 1
    return (copia, cambiados)


def componer_incremental(
    informe: InformeMutacion, plan: PlanIncremental
) -> InformeMutacion:
    """Funde la campaña corta con lo reutilizado: el informe de la regla entera."""
    informe.generados = plan.generados
    informe.por_fichero = (
        None
        if plan.por_fichero is None
        else {
            fichero: plan.por_fichero.get(fichero, 0)
            for fichero in informe.alcance.ficheros()
        }
    )
    informe.candidatos = plan.candidatos
    informe.max_mutantes = plan.limite
    informe.reutilizados = list(plan.reutilizados)
    informe.incremental_desde = plan.desde
    informe.control = len(plan.control)
    informe.muestreado = informe.juzgados < plan.candidatos
    return informe


def mutantes_del_alcance(alcance: Alcance, raiz: str = ".") -> list[Mutante]:
    """Todos los mutantes del alcance, leídos y ordenados como en la campaña."""
    base = Path(raiz)
    mutantes: list[Mutante] = []
    for fichero in alcance.ficheros():
        ruta = base / fichero
        if ruta.is_file():
            mutantes.extend(
                generar_mutantes(_leer(ruta), alcance.lineas[fichero], fichero)
            )
    return mutantes


# --- CLI --------------------------------------------------------------------


def _analizar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m harness.mutacion",
        description=(
            "Muta las líneas de producción que toca una feature y comprueba "
            "cuántas mutaciones sobreviven a la suite de tests."
        ),
    )
    analizador.add_argument(
        "--feature", default=None, help="Identificador de la feature, p. ej. F-XXX"
    )
    analizador.add_argument(
        "--base",
        default=None,
        help="Rama de integración (por defecto, RAMA_BASE de harness/init.sh)",
    )
    analizador.add_argument("--rama", default=None, help="Rama de la feature")
    analizador.add_argument("--raiz", default=".", help="Raíz del repositorio a mutar")
    analizador.add_argument(
        "--ficheros",
        default=None,
        help=(
            "Rutas separadas por coma que se mutan ENTERAS, en vez de calcular "
            "el alcance desde el diff de la feature. Para campañas cuyo sujeto "
            "es un módulo, no un cambio. --feature sigue haciendo falta: es "
            "quien resuelve el nivel de rigor y, con él, el muestreo."
        ),
    )
    analizador.add_argument(
        "--timeout",
        type=int,
        default=None,
        help=(
            "Segundos por mutante, ANULANDO el cálculo automático. Sin este "
            "flag el timeout se deriva de la línea base medida y "
            "'mutacion.timeout_por_mutante_s' actúa solo como suelo."
        ),
    )
    analizador.add_argument(
        "--max-mutantes",
        type=int,
        default=None,
        help=(
            "Mutantes que se evalúan como mucho. 0 = SIN TOPE (la campaña "
            "entera), que es como se anula el tope que impone un nivel de "
            "rigor. Sin este flag, el 'max_mutantes' del nivel de la feature "
            "en harness/rigor.json; si el nivel no declara ninguno, sin tope."
        ),
    )
    analizador.add_argument(
        "--semilla",
        type=int,
        default=None,
        help=(
            "Semilla del muestreo. Sin ella, la 'semilla' del nivel de rigor "
            "de la feature: dos campañas del mismo nivel eligen los mismos "
            "mutantes y son comparables."
        ),
    )
    analizador.add_argument("--salida", default=None, help="Ruta del informe")
    analizador.add_argument(
        "--incremental",
        action="store_true",
        help=(
            "Repite la campaña reutilizando el estado de la anterior "
            "(mutacion_F-XXX.json junto al informe): si desde su SHA solo han "
            "cambiado papeleo y tests que crecen, reevalúa supervivientes, "
            "timeouts y una muestra de control de los muertos. En cualquier otro "
            "caso hace la campaña completa y dice por qué."
        ),
    )
    analizador.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Evaluadores concurrentes, cada uno en su git worktree. 1 = campaña "
            "en serie sobre el propio árbol (lo de siempre). Sin este flag, "
            "'mutacion.workers' de harness/rigor.json o los núcleos menos dos."
        ),
    )
    modo_seleccion = analizador.add_mutually_exclusive_group()
    modo_seleccion.add_argument(
        "--con-seleccion",
        action="store_true",
        help=(
            "Enciende la selección de tests (F-019): mide una vez el mapa línea "
            "-> tests con coverage, poda los mutantes cuya sentencia no ejecuta "
            "ningún proceso y juzga el resto con los tests que la tocan, "
            "revalidando con la suite entera lo que no matan. Por defecto está "
            "APAGADA, salvo 'mutacion.seleccion_de_tests: true' en rigor."
        ),
    )
    modo_seleccion.add_argument(
        "--sin-seleccion",
        action="store_true",
        help=(
            "Juzga cada mutante con la suite ENTERA, como la 1.9.0, aunque "
            "'mutacion.seleccion_de_tests' la encienda (F-019)."
        ),
    )
    analizador.add_argument(
        "--estado",
        action="store_true",
        help=(
            "No lanza nada: dice si hay una campaña en curso según el centinela "
            "de .arnes_cache/. Códigos: 0 no hay, 3 la hay sin tocar el árbol "
            "principal, 4 la hay CON un mutante aplicado en el árbol principal. "
            "Lo usa harness/init.sh."
        ),
    )
    analizador.add_argument(
        "--restaurar",
        action="store_true",
        help=(
            "No lanza nada: deshace los mutantes que dejó aplicados una campaña "
            "muerta a medias, según el centinela, y lo retira."
        ),
    )
    opciones = analizador.parse_args(argv)
    opciones.base = opciones.base or rama_base_configurada(opciones.raiz)
    # R23. Hasta hoy `--timeout 0` era falsy y caía EN SILENCIO al valor
    # configurado: quien lo escribía creía haber pedido algo y recibía otra
    # cosa. Un timeout de cero no es una opción legítima, así que se rechaza con
    # el código 2 de error de uso en vez de esconderse.
    if opciones.timeout is not None and opciones.timeout <= 0:
        analizador.error(
            f"--timeout tiene que ser un entero de segundos mayor que cero, y "
            f"es {opciones.timeout}."
        )
    if opciones.workers is not None and opciones.workers < 1:
        analizador.error(
            f"--workers tiene que ser 1 o más (1 = campaña en serie), y es "
            f"{opciones.workers}."
        )
    return opciones


#: Códigos de salida de `--estado`, para que init.sh no tenga que leer el JSON.
SIN_CAMPANIA = 0
CAMPANIA_AJENA = 3
CAMPANIA_MUTANDO = 4


def _modo_estado(raiz: str) -> int:
    """Informa de si hay una campaña en curso. Ver `--estado`."""
    datos = Centinela.leer(raiz)
    if datos is None:
        print("Sin campaña de mutación en curso.")
        return SIN_CAMPANIA
    aplicados = datos.get("aplicados", [])
    detalle = "; ".join(str(a.get("descripcion", "")) for a in aplicados) or "ninguno"
    cabecera = (
        f"Campaña de mutación EN CURSO: feature {datos.get('feature') or '(?)'}, "
        f"modo {datos.get('modo') or '(?)'}, pid {datos.get('pid') or '(?)'}, "
        f"desde {datos.get('inicio') or '(?)'}. Mutante aplicado: {detalle}."
    )
    if datos.get("muta_arbol_principal"):
        print(
            f"{cabecera}\n"
            "    El ÁRBOL PRINCIPAL tiene un mutante escrito ahora mismo: lo que "
            "midas aquí\n"
            "    (compilación, tests, cobertura) mide el mutante, no tu código. "
            "Si no hay\n"
            "    ninguna campaña viva, el centinela es basura de una que murió: "
            "recupérate\n"
            "    con `python -m harness.mutacion --restaurar`."
        )
        return CAMPANIA_MUTANDO
    print(
        f"{cabecera}\n"
        "    Muta en worktrees aparte, no en este árbol. Aun así compite por CPU "
        "y se\n"
        "    romperá si commiteas mientras corre."
    )
    return CAMPANIA_AJENA


def _modo_restaurar(raiz: str) -> int:
    """Deshace lo que dejó una campaña muerta a medias. Ver `--restaurar`."""
    datos = Centinela.leer(raiz)
    if datos is None:
        print("No hay centinela: no quedó ningún mutante aplicado.")
        return 0
    restaurados, irrecuperables = restaurar_desde_centinela(raiz)
    for ruta in restaurados:
        print(f"Restaurado: {ruta}")
    for ruta in irrecuperables:
        print(f"NO SE PUDO RESTAURAR: {ruta}", file=sys.stderr)
    if not restaurados and not irrecuperables:
        print("El centinela no apuntaba a ningún fichero vivo; retirado.")
    return 2 if irrecuperables else 0


def workers_por_defecto() -> int:
    """Workers cuando nadie dice nada: `min(max(1, (núcleos - 2) // 2), tope)`.

    Los dos primeros núcleos son los de siempre: la máquina y el coordinador. El
    `// 2` es lo que cambió sobre la fórmula vieja, y cambió porque aquélla suponía
    que el cuello de botella es la CPU. No lo es: cada worker arranca un proceso
    **pytest completo** —intérprete, importaciones, recolección, E/S de disco y,
    en un monorepo, un venv por servicio—, así que el recurso escaso es la
    máquina entera y no el núcleo. Se reserva del orden de dos núcleos por
    suite.

    En 4 núcleos da 1; en 8, 3; en 22, 4 (antes daba 16, y con 16 no cabía ni
    una línea base dentro de su timeout).
    """
    return min(max(1, ((os.cpu_count() or 1) - 2) // 2), TOPE_WORKERS)


def resolver_workers(pedidos: int | None, configurados: int | None) -> int:
    """Número de workers, por precedencia: `--workers` > `rigor.json` > default."""
    if pedidos is not None:
        return pedidos
    if configurados is not None:
        return configurados
    return workers_por_defecto()


def _timeout_configurado() -> int:
    """Timeout por mutante de `harness/rigor.json`, con red de seguridad.

    Se lee la configuración del arnés que ejecuta la campaña (el directorio
    actual), no la del repositorio mutado, que puede ser un árbol antiguo sin
    arnés. Un proyecto sin configuración de rigor cae en el valor por defecto;
    lo que nunca se cablea en el código es el umbral de cobertura.
    """
    try:
        return timeout_mutacion(cargar_rigor(RUTA_RIGOR))
    except CapaLocalInvalida:
        raise  # R19 de F-063: una capa local rota no se degrada en silencio
    except ValueError:
        return TIMEOUT_POR_DEFECTO


def _no_versionados_configurados() -> list[str]:
    """`mutacion.ficheros_no_versionados` de la configuración, o `[]` (F-023)."""
    try:
        return ficheros_no_versionados(cargar_rigor(RUTA_RIGOR))
    except CapaLocalInvalida:
        raise
    except ValueError:
        return []


def _seleccion_configurada() -> bool:
    """`mutacion.seleccion_de_tests` de la configuración; `False` si no está (F-019)."""
    try:
        return seleccion_de_tests(cargar_rigor(RUTA_RIGOR))
    except CapaLocalInvalida:
        raise
    except ValueError:
        return False


def resolver_seleccion(con: bool, sin: bool, configurada: bool) -> bool:
    """¿Selección de tests? La orden manda sobre la clave; sin ninguna, la clave (R19)."""
    if con:
        return True
    if sin:
        return False
    return configurada


def _workers_configurados() -> int | None:
    """Workers declarados en `harness/rigor.json`, o `None` si no hay clave."""
    try:
        return workers_mutacion(cargar_rigor(RUTA_RIGOR))
    except CapaLocalInvalida:
        raise
    except ValueError:
        return None


def resolver_muestreo(
    pedido_max: int | None,
    pedido_semilla: int | None,
    nivel_max: int | None,
    nivel_semilla: int | None,
) -> tuple[int | None, int | None]:
    """Tope y semilla del muestreo: `--max-mutantes` > nivel de rigor > sin tope.

    Función pura, y sede ÚNICA de la precedencia: la campaña en serie y la
    paralela reciben ya resuelto lo mismo. `pedido_max == 0` significa **sin
    tope**, que es la única forma de anular desde la orden el tope que impone un
    nivel; un negativo se trata igual, porque «menos de un mutante» no es un
    tope que nadie quiera.

    El tope y la semilla se resuelven por separado a propósito: pedir una
    semilla distinta para reproducir algo no debe deshacer el tope del nivel.
    """
    if pedido_max is not None:
        maximo = pedido_max if pedido_max > 0 else None
    else:
        maximo = nivel_max
    semilla = pedido_semilla if pedido_semilla is not None else nivel_semilla
    return (maximo, semilla)


def resolver_regla(
    pedido_max: int | None, regla_del_nivel: ReglaMuestreo | None
) -> ReglaMuestreo | None:
    """La regla con que se elige, por precedencia: `--max-mutantes` > nivel (R7).

    Lo pedido a mano es siempre un tope FIJO —la fracción del nivel se ignora—,
    pero la reducción a uno por línea sigue siendo la del nivel: es parte de qué
    se mide, no de cuánto. `0` (o negativo) es «sin tope»; sin reducción que
    conservar, eso es la campaña entera de siempre y no hay regla.
    """
    if pedido_max is None:
        return regla_del_nivel
    por_linea = regla_del_nivel is not None and regla_del_nivel.por_linea
    techo = pedido_max if pedido_max > 0 else None
    if techo is None and not por_linea:
        return None
    return ReglaMuestreo(
        por_linea=por_linea, fraccion=None, suelo=None, techo=techo, origen=ORIGEN_ORDEN
    )


def _regla_configurada(feature: str) -> tuple[ReglaMuestreo | None, int | None, str | None]:
    """Regla, semilla y nivel de una feature según `harness/rigor.json`.

    Mismo degradado que `_muestreo_configurado`, que se conserva tal cual: sin
    configuración legible, `(None, None, None)` y campaña completa.
    """
    try:
        rigor = cargar_rigor(RUTA_RIGOR)
        ficha = next((f for f in cargar_features() if f.get("id") == feature), {})
        nivel = nivel_de_feature(ficha, rigor)
        return (regla_nivel(nivel, rigor), semilla_nivel(nivel, rigor), nivel)
    except CapaLocalInvalida:
        raise
    except ValueError:
        return (None, None, None)


def _muestreo_configurado(feature: str) -> tuple[int | None, int | None, str | None]:
    """Tope, semilla y NIVEL de rigor de una feature, según `harness/rigor.json`.

    Devuelve también el nivel porque el informe tiene que declarar quién fijó la
    semilla (R9), y resolverlo aparte obligaría a releer los mismos dos ficheros.

    Ante cualquier configuración ausente o ilegible devuelve `(None, None,
    None)` —campaña completa, como hasta hoy—, igual que hacen
    `_timeout_configurado` y `_workers_configurados`: el arnés se degrada, no se
    cae, en un repositorio con configuración anterior.
    """
    try:
        rigor = cargar_rigor(RUTA_RIGOR)
        ficha = next(
            (f for f in cargar_features() if f.get("id") == feature), {}
        )
        nivel = nivel_de_feature(ficha, rigor)
        return (max_mutantes_nivel(nivel, rigor), semilla_nivel(nivel, rigor), nivel)
    except CapaLocalInvalida:
        raise
    except ValueError:
        return (None, None, None)


def anuncio_de_regla(regla: ReglaMuestreo, semilla: int | None, nivel: str | None) -> str:
    """La línea con que el CLI anuncia la regla antes de generar (R13)."""
    if regla.fraccion is not None:
        porcentaje = format(regla.fraccion * 100, "g")
        tope = (
            f"{porcentaje} % de los candidatos, suelo {regla.suelo or 0}, techo "
            f"{'sin techo' if regla.techo is None else regla.techo}"
        )
    elif regla.techo is None:
        tope = "sin tope"
    elif regla.origen == ORIGEN_ORDEN:
        tope = f"tope fijado a mano {regla.techo}"
    else:
        tope = f"tope fijo {regla.techo}"
    return (
        f"Regla de muestreo (nivel {nivel or 'no resuelto'}): uno por línea "
        f"{'sí' if regla.por_linea else 'no'}; {tope}; semilla {semilla}."
    )


def decidir_incremental(
    estado: dict | None,
    raiz: str,
    alcance: Alcance,
    regla: ReglaMuestreo | None,
    semilla: int | None,
    nivel: str | None,
) -> tuple[str, PlanIncremental | None, str]:
    """`(decisión, plan, motivo)` de una repetición con `--incremental`.

    La decisión es `vigente` (no hay nada que medir), `solo_tests` con su plan,
    o `codigo` sin plan: campaña completa, y el motivo dice por qué (R17).
    """
    if estado is None:
        return (DELTA_CODIGO, None, "no hay estado de una campaña anterior legible")
    sha = estado.get("sha")
    if not isinstance(sha, str) or not sha:
        return (DELTA_CODIGO, None, "el estado no declara el SHA medido")
    delta = clasificar_delta(raiz, sha)
    if delta == DELTA_CODIGO:
        return (
            DELTA_CODIGO,
            None,
            (
                f"el delta desde {sha} toca producción, borra líneas de tests o "
                "no parte de HEAD"
            ),
        )
    try:
        control = control_incremental(cargar_rigor(RUTA_RIGOR))
    except CapaLocalInvalida:
        raise
    except ValueError:
        control = (CONTROL_FRACCION, CONTROL_MINIMO)
    mutantes = mutantes_del_alcance(alcance, raiz)
    # F-023 (R12, R32): un estado sin `criterio` se juzgó con el criterio de
    # antes. Se migra en memoria —el fichero solo lo reescribe una campaña
    # fiable— y, aunque el delta sea `vigente`, se corre el plan corto para que
    # informe y estado queden con el criterio nuevo.
    heredado = "criterio" not in estado
    estado, migrados = migrar_estado(estado, mutantes, raiz)
    plan = plan_incremental(estado, regla, semilla, nivel, mutantes, control)
    if isinstance(plan, str):
        return (DELTA_CODIGO, None, plan)
    if heredado:
        return (
            DELTA_SOLO_TESTS,
            plan,
            (
                f"estado anterior a F-023: {migrados} muerto(s) no compilan y se "
                "reevalúan; informe y estado se reescriben con el criterio nuevo"
            ),
        )
    if delta == DELTA_VIGENTE:
        return (DELTA_VIGENTE, None, f"desde {sha} solo ha cambiado papeleo")
    return (DELTA_SOLO_TESTS, plan, "")


#: Código con el que sale una campaña que NO ha juzgado nada. Distinto del 1
#: de «hay supervivientes» a propósito: aquello es un resultado, esto no.
NADA_JUZGADO = 3


def mensaje_alcance_vacio(alcance: Alcance) -> str:
    """Por qué se aborta cuando el alcance no tiene ni una línea (R16)."""
    return (
        f"ALCANCE VACÍO en {alcance.feature}: ni una línea de producción que "
        f"mutar (origen {alcance.origen}, {alcance.ref_diff[0]}.."
        f"{alcance.ref_diff[1]}). No se ha juzgado NADA.\n"
        "  No se escribe informe: un fichero en progress/ con un cero que nadie "
        "ha medido es peor que no tener fichero, porque se lee como «nada que "
        "arreglar» y el reviewer lo da por bueno.\n"
        "  Causas habituales: la rama ya está mergeada y el diff contra la base "
        "sale vacío (declara el alcance a mano con --ficheros), o todo lo que "
        "cambió es documentación, tests o especificaciones."
    )


def mensaje_sin_mutantes(alcance: Alcance) -> str:
    """Por qué se aborta cuando hay líneas pero no sale ni un mutante (R14)."""
    return (
        f"CERO MUTANTES en {alcance.feature}: el alcance tiene "
        f"{alcance.total_lineas()} línea(s) de producción pero no se ha generado "
        "ni un mutante, así que no se ha juzgado NADA.\n"
        "  No se escribe informe: «0 generados, 0 supervivientes» se lee como "
        "una campaña impecable.\n"
        "  Motivo: esas líneas no llevan código mutable —imports, docstrings, "
        "declaraciones, cadenas— o el fichero no se pudo leer. Amplía el "
        "alcance o aporta la evidencia de otra forma, y dilo por escrito."
    )


def main(argv: list[str] | None = None, ejecutor: object | None = None) -> int:
    """Punto de entrada: `_main`, con la capa local de rigor rota como error de uso.

    R19 de F-063: los lectores de `harness/rigor.json` degradan a sus valores
    por defecto ante una configuración ilegible, pero NO ante una
    `harness/rigor.local.json` inválida: medir con un rigor distinto del que el
    proyecto declaró sería peor que no medir. Aquí se traduce en mensaje y 2.
    """
    try:
        return _main(argv, ejecutor)
    except CapaLocalInvalida as error:
        print(
            f"ABORTADA: la capa local de rigor no vale y la campaña no se degrada "
            f"a los valores por defecto.\n  {error}",
            file=sys.stderr,
        )
        return 2
    finally:
        # R23 de F-023: los prefijos de bytecode de la campaña, fuera del temp
        # por cualquier salida de `_main`, incluida una excepción.
        retirar_prefijos()
        # R23 de F-019: el factor de los tests es de ESTA campaña.
        fijar_factor_tests(None)


def _main(argv: list[str] | None = None, ejecutor: object | None = None) -> int:
    """Cuerpo de `main`.

    Códigos: 0 sin supervivientes, 1 con ellos, 2 error de uso, 3 campaña
    abortada (línea base roja, árbol sucio o nada que juzgar). El 3 es distinto
    del 1 a propósito: «hay supervivientes» es un resultado; «no se ha medido
    nada» no.

    Las dos guardas de D4 viven AQUÍ y no en `harness.alcance` a sabiendas. El
    mismo modo de fallo —una campaña de cero que sale en verde— ha entrado ya
    por tres puertas distintas: la invocación de pytest sin ruta, `--ficheros
    ","` y `--feature` sobre una rama ya mergeada. Poner una cuarta guarda en
    el cuarto constructor de alcance es esperar a la quinta; `main` es el
    único punto por el que pasan todas las vías, incluidas
    las que todavía no existen, y además es quien escribe el informe y elige el
    código de salida. La guarda de entrada de `alcance_de_ficheros` NO se
    retira (R17): ésa sabe QUÉ ruta sobra, y ésta solo sabe que no quedó nada.
    """
    opciones = _analizar_argumentos(argv)
    # `is not None` y no `or`: aquí el 0 ya no puede llegar (R23 lo rechaza),
    # pero era justo el `or` lo que hacía que `--timeout 0` cayera en silencio
    # al valor configurado.
    timeout_fijado = opciones.timeout is not None
    timeout_s = opciones.timeout if timeout_fijado else _timeout_configurado()

    if opciones.estado:
        return _modo_estado(opciones.raiz)
    if opciones.restaurar:
        return _modo_restaurar(opciones.raiz)
    if not opciones.feature:
        print("Falta --feature (o usa --estado / --restaurar).", file=sys.stderr)
        return 2

    # Una campaña anterior que murió a machetazos pudo dejar un mutante escrito.
    # Empezar encima de él mediría el mutante viejo, no el código.
    if Centinela.leer(opciones.raiz) is not None:
        print(
            "Hay un centinela de una campaña anterior sin cerrar. Se restaura "
            "antes de empezar:",
            file=sys.stderr,
        )
        # R18: hasta hoy este código de salida se TIRABA. Si la restauración no
        # podía deshacer algo, la campaña arrancaba igual sobre un árbol que ya
        # estaba mutado y todos sus veredictos hablaban de un código que nadie
        # había escrito.
        if _modo_restaurar(opciones.raiz) != 0:
            print(
                "ABORTADA sin empezar: queda al menos un fichero con un MUTANTE "
                "de la campaña anterior escrito en disco (los nombra la línea "
                "«NO SE PUDO RESTAURAR» de aquí arriba).\n"
                "  Medir encima de un mutante viejo es medir el mutante: cada "
                "veredicto de esta campaña hablaría de un código que nadie ha "
                "escrito, y el informe no lo diría.\n"
                "  Deshazlo a mano —`git checkout -- <fichero>`— y vuelve a "
                "lanzarla.",
                file=sys.stderr,
            )
            return NADA_JUZGADO

    try:
        servicios = cargar_servicios(raiz=opciones.raiz)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    try:
        if opciones.ficheros:
            alcance = alcance_de_ficheros(
                opciones.ficheros.split(","), opciones.feature, raiz=opciones.raiz
            )
        else:
            alcance = alcance_de_feature(
                opciones.feature,
                base=opciones.base,
                rama=opciones.rama,
                raiz=opciones.raiz,
                servicios=servicios,
            )
    except SystemExit as parada:
        print(str(parada), file=sys.stderr)
        return 2

    print(alcance.descripcion())
    # R16: aquí, ANTES de crear worktrees o correr ninguna línea base. Hasta hoy
    # esto solo imprimía «Sin líneas de producción» y SEGUÍA, y seguir es lo que
    # producía el informe de cero mutantes que se lee como «todo bien».
    if not alcance.total_lineas():
        print(mensaje_alcance_vacio(alcance), file=sys.stderr)
        return NADA_JUZGADO

    def factoria(fichero: str) -> object:
        return ejecutor_para(fichero, servicios, opciones.raiz)

    nivel_max, nivel_semilla, nivel = _muestreo_configurado(opciones.feature)
    max_mutantes, semilla = resolver_muestreo(
        opciones.max_mutantes, opciones.semilla, nivel_max, nivel_semilla
    )
    regla_del_nivel, _, _ = _regla_configurada(opciones.feature)
    regla = resolver_regla(opciones.max_mutantes, regla_del_nivel)
    if regla is not None:
        # R13: antes de generar nada, quien lanza la campaña ve con qué regla
        # se va a elegir; si no le cuadra, la corta sin haber gastado una suite.
        print(anuncio_de_regla(regla, semilla, nivel))
    # La línea de antes solo cuando el tope ES fijo: con una fracción, «hasta
    # 300» anunciaría el techo como si fuera lo que se va a evaluar.
    if max_mutantes is not None and (regla is None or regla.fraccion is None):
        print(
            f"Muestreo: hasta {max_mutantes} mutantes, semilla {semilla} "
            f"(nivel {nivel or 'no resuelto'})."
        )

    destino = Path(opciones.salida or f"progress/mutacion_{opciones.feature}.md")
    plan: PlanIncremental | None = None
    if opciones.incremental:
        decision, plan, motivo = decidir_incremental(
            leer_estado(ruta_de_estado(destino)), opciones.raiz, alcance, regla,
            semilla, nivel,
        )
        if decision == DELTA_VIGENTE:
            print(f"Campaña vigente: {motivo}. No se ejecuta nada.")
            return 0
        if plan is None:
            print(f"Campaña completa: {motivo}.")
        else:
            if motivo:
                print(f"Migración del estado: {motivo}.")
            print(
                f"Campaña incremental desde {plan.desde}: {len(plan.reevaluar)} "
                f"supervivientes, timeouts e indeterminados que reevaluar, "
                f"{len(plan.control)} muertos de control y "
                f"{len(plan.reutilizados)} veredictos reutilizados."
            )

    workers = resolver_workers(opciones.workers, _workers_configurados())
    # R23 de F-019: cada suite que lance la campaña lleva el factor de W.
    fijar_factor_tests(workers)
    timeout_base_s = timeout_de_linea_base(timeout_s, workers)
    if timeout_fijado:
        # R6: quien fija el timeout a mano tiene que saber que ha desactivado la
        # derivación, o leerá el informe creyendo que el número está medido.
        print(
            f"Timeout FIJADO a mano: {timeout_s} s por mutante. El cálculo "
            "automático a partir de la línea base queda ANULADO."
        )
    else:
        print(
            f"Timeout por mutante: se derivará de la línea base medida, con "
            f"suelo {timeout_s} s y margen {MARGEN_TIMEOUT}. La propia línea "
            f"base dispone de {timeout_base_s} s."
        )
    seleccion_configurada = _seleccion_configurada()
    con_seleccion = resolver_seleccion(
        opciones.con_seleccion, opciones.sin_seleccion, seleccion_configurada
    )
    print(
        "Selección de tests: activa. Se mide una vez el mapa línea -> tests; "
        "se podan los mutantes cuya sentencia no ejecuta ningún proceso y el resto "
        "se juzga con los tests que la tocan (--sin-seleccion la apaga)."
        if con_seleccion
        else "Selección de tests: DESACTIVADA: cada mutante con la suite entera, "
        "como la 1.9.0 (--con-seleccion o mutacion.seleccion_de_tests la encienden)."
    )
    paralela = workers >= 2 and ejecutor is None
    # R19 de F-023: lo no versionado que se declaró tiene que existir ANTES de
    # abrir el centinela, crear worktrees o escribir un solo mutante, y en los
    # dos modos: en serie la suite corre sobre este árbol y también lo necesita.
    no_versionados = _no_versionados_configurados()
    try:
        comprobar_ficheros_no_versionados(opciones.raiz, no_versionados)
    except FaltanFicheros as error:
        print(str(error), file=sys.stderr)
        return NADA_JUZGADO
    centinela = Centinela(
        raiz=opciones.raiz,
        feature=opciones.feature,
        modo="paralelo" if paralela else "serie",
    )
    centinela.abrir()

    def campania(dados: list[Mutante] | None) -> InformeMutacion:
        """Una campaña con la regla de siempre o, con `dados`, solo esos."""
        eleccion = (
            {"max_mutantes": max_mutantes, "regla": regla}
            if dados is None
            else {"max_mutantes": None, "regla": None, "mutantes": dados}
        )
        if paralela:
            # Import perezoso: `harness.mutacion_paralela` se apoya en este
            # módulo, y al revés solo aquí. Sin ciclo que gestionar.
            from harness.mutacion_paralela import ejecutar_campania_paralela

            print(f"Campaña paralela: hasta {workers} workers, uno por worktree.")
            return ejecutar_campania_paralela(
                alcance,
                servicios,
                timeout_s=timeout_s,
                raiz=opciones.raiz,
                workers=workers,
                semilla=semilla,
                eco=lambda linea: print(linea, flush=True),
                centinela=centinela,
                timeout_base_s=timeout_base_s,
                timeout_fijado=timeout_fijado,
                ficheros=no_versionados,
                seleccion=con_seleccion,
                **eleccion,
            )
        return ejecutar_campania(
            alcance,
            ejecutor or EjecutorPytest(raiz=opciones.raiz),
            timeout_s=timeout_s,
            raiz=opciones.raiz,
            semilla=semilla,
            eco=lambda linea: print(linea, flush=True),
            ejecutor_de=factoria if servicios and ejecutor is None else None,
            centinela=centinela,
            timeout_base_s=timeout_base_s,
            timeout_fijado=timeout_fijado,
            workers=workers,
            # F-019 (R19): apagada por defecto; la orden o la clave la encienden.
            seleccion=con_seleccion,
            **eleccion,
        )

    try:
        if plan is None:
            informe = campania(None)
        else:
            informe = campania(plan.reevaluar + plan.control)
            # R18 de F-058 y R31 de F-023: un muerto del control que ya no lo
            # está —sobrevive o vuelve indeterminado— desmiente TODO lo
            # reutilizado, sea el estado nativo o migrado.
            no_muertos = [*informe.supervivientes, *informe.indeterminados]
            revividos = [m for m in plan.control if m in no_muertos]
            if revividos:
                print(
                    f"AVISO: {len(revividos)} muerto(s) de la muestra de control "
                    f"sobrevive(n) ahora ({revividos[0].descripcion()}) o "
                    "vuelve(n) indeterminado(s): los "
                    "veredictos reutilizados ya no valen. Se descartan y se hace "
                    "la campaña completa."
                )
                plan = None
                informe = campania(None)
            else:
                informe.regla = regla
                informe = componer_incremental(informe, plan)
    except CampaniaAbortada as error:
        # Sin informe a propósito: un fichero en `progress/` con un cero que
        # nadie ha medido es peor que no tener fichero.
        print(str(error), file=sys.stderr)
        return 3
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    finally:
        centinela.cerrar()

    # R14: red final. Puede haber líneas en el alcance y aun así ni un mutante
    # (imports, docstrings, declaraciones). Ese informe no dice nada de nada.
    if informe.generados == 0:
        print(mensaje_sin_mutantes(alcance), file=sys.stderr)
        return NADA_JUZGADO

    # Quién fijó el muestreo lo sabe el CLI, no la campaña: el informe tiene que
    # decirlo para que se pueda repetir con los mismos mutantes (R9).
    informe.nivel = nivel
    # Contra qué base se midió también lo sabe el CLI: con `--ficheros` no hay
    # base que valga, y sin ella el comando de la cabecera mide otro alcance.
    informe.base = None if opciones.ficheros else opciones.base
    informe.seleccion_por_rigor = seleccion_configurada
    escribir_informe(informe, destino)
    # R14: el estado que permite repetir con `--incremental`. Solo si es fiable.
    if escribir_estado(informe, ruta_de_estado(destino)):
        print(f"Estado: {ruta_de_estado(destino).as_posix()}")
    print(
        f"{informe.evaluados} mutantes evaluados, {informe.muertos} muertos, "
        f"{len(informe.supervivientes)} supervivientes, "
        f"{len(informe.timeouts)} timeouts, {len(informe.base_rota)} sin "
        f"veredicto en {informe.segundos:.1f} s"
    )
    print(f"Informe: {destino.as_posix()}")
    if not informe.fiable:
        print(f"CAMPAÑA NO VÁLIDA: {informe.aviso_base}", file=sys.stderr)
        return 3
    return 1 if informe.supervivientes else 0


if __name__ == "__main__":  # pragma: no cover
    # Se llama al `main` del módulo IMPORTADO, no al de esta copia. Con
    # `python -m harness.mutacion` este fichero se ejecuta como `__main__`, y
    # `harness.mutacion_paralela` lo vuelve a importar como `harness.mutacion`:
    # dos copias del módulo y, por tanto, dos clases `BaseRota` distintas. Un
    # `except CampaniaAbortada` escrito aquí NO cazaría la que lanza la campaña
    # paralela, y el aborto saldría por pantalla como un traceback pelado.
    # Delegando en el módulo importado, todo el mundo usa las mismas clases.
    from harness.mutacion import main as _main

    raise SystemExit(_main())
