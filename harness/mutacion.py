# harness/mutacion.py
"""Mutador mínimo del arnés: comprueba que los tests son de verdad.

Muta ÚNICAMENTE las líneas de producción que toca una feature (el alcance lo
calcula `harness.alcance` desde el diff de git), ejecuta la suite por cada
mutante y cuenta cuántos sobreviven. Un mutante superviviente es una línea que
ningún test comprueba de verdad.

Todo con biblioteca estándar (`ast` + `subprocess`): la herramienta tiene que
poder instalarse tal cual en cualquier repositorio, incluido Windows.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass

Posicion = tuple[int, int]

#: (símbolo original, símbolo mutado) por tipo de nodo del árbol sintáctico.
COMPARACIONES: dict[type, tuple[str, str]] = {
    ast.Eq: ("==", "!="),
    ast.NotEq: ("!=", "=="),
    ast.Lt: ("<", "<="),
    ast.LtE: ("<=", "<"),
    ast.Gt: (">", ">="),
    ast.GtE: (">=", ">"),
}
ARITMETICOS: dict[type, tuple[str, str]] = {
    ast.Add: ("+", "-"),
    ast.Sub: ("-", "+"),
    ast.Mult: ("*", "//"),
    ast.FloorDiv: ("//", "*"),
}
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
        # Se elimina el `not` y el hueco hasta su operando, para no dejar
        # espacios de más en la línea mutada.
        yield _Candidato(
            _inicio(nodo),
            _inicio(nodo.operand),
            "not",
            "",
            "not",
            hasta=_inicio(nodo.operand),
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


def _localizar(brutas: list[str], candidato: _Candidato) -> Posicion | None:
    """Encuentra el token a mutar dentro del hueco entre dos operandos.

    Devuelve `(línea, columna en bytes)`. Se busca línea a línea porque un
    token de operador nunca está partido entre dos líneas.
    """
    objetivo = candidato.buscar.encode("utf-8")
    if not objetivo:
        return None
    (linea_ini, col_ini), (linea_fin, col_fin) = candidato.ini, candidato.fin
    for numero in range(linea_ini, linea_fin + 1):
        if numero > len(brutas):
            break
        bruta = brutas[numero - 1].encode("utf-8")
        desde = col_ini if numero == linea_ini else 0
        hasta = col_fin if numero == linea_fin else len(bruta)
        posicion = bruta.find(objetivo, desde, hasta)
        if posicion != -1:
            return (numero, posicion)
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
