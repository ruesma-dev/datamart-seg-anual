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

import argparse
import ast
import random
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from harness.alcance import Alcance, alcance_de_feature

Posicion = tuple[int, int]

#: Veredictos posibles de la suite frente a un mutante.
MUERTO = "muerto"
SUPERVIVIENTE = "superviviente"
TIMEOUT = "timeout"

#: Segundos máximos por mutante si nadie configura otra cosa.
TIMEOUT_POR_DEFECTO = 120

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


# --- Ejecución de la suite --------------------------------------------------


def _leer(ruta: Path) -> str:
    """Lee preservando los saltos de línea tal cual están en disco."""
    with open(ruta, encoding="utf-8", newline="") as fichero:
        return fichero.read()


def _escribir(ruta: Path, texto: str) -> None:
    """Escribe sin traducir saltos de línea: restaurar debe ser idéntico."""
    with open(ruta, "w", encoding="utf-8", newline="") as fichero:
        fichero.write(texto)


class EjecutorPytest:
    """Lanza la suite en un proceso aparte y traduce el resultado.

    Que la suite falle significa que los tests CAZAN el mutante (muerto). Que
    pase significa que el mutante sobrevive: nadie comprobaba esa línea.
    """

    def __init__(self, raiz: str = ".", argumentos: list[str] | None = None) -> None:
        self.raiz = raiz
        self.argumentos = argumentos or ["-x", "-q", "--tb=no", "-p", "no:cacheprovider"]

    def ejecutar(self, timeout_s: int) -> str:
        try:
            proceso = subprocess.run(
                [sys.executable, "-m", "pytest", *self.argumentos],
                cwd=self.raiz,
                capture_output=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return TIMEOUT
        return SUPERVIVIENTE if proceso.returncode == 0 else MUERTO


# --- Campaña ----------------------------------------------------------------


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

    @property
    def evaluados(self) -> int:
        return len(self.mutantes_evaluados)


def ejecutar_campania(
    alcance: Alcance,
    ejecutor: object,
    timeout_s: int = TIMEOUT_POR_DEFECTO,
    raiz: str = ".",
    max_mutantes: int | None = None,
    semilla: int | None = None,
    mutantes: list[Mutante] | None = None,
    eco: Callable[[str], None] | None = None,
) -> InformeMutacion:
    """Muta el alcance, mutante a mutante, y cuenta cuántos sobreviven.

    Garantía dura: pase lo que pase (excepción, timeout, Ctrl-C), ningún
    fichero queda mutado en el árbol de trabajo al salir de esta función.
    """
    inicio = time.monotonic()
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
    )

    if max_mutantes is not None and len(mutantes) > max_mutantes:
        sorteo = random.Random(semilla)
        mutantes = sorted(
            sorteo.sample(mutantes, max_mutantes),
            key=lambda m: (m.fichero, m.linea, m.col, m.operador),
        )
        informe.muestreado = True

    try:
        for indice, mutante in enumerate(mutantes, start=1):
            fuente = fuentes.get(mutante.fichero)
            if fuente is None:
                continue
            informe.mutantes_evaluados.append(mutante)
            mutada = aplicar_mutante(fuente, mutante)

            try:
                compile(mutada, mutante.fichero, "exec")
            except (SyntaxError, ValueError):
                informe.muertos += 1  # no compila: los tests lo cazarían siempre
                continue

            ruta = base / mutante.fichero
            try:
                _escribir(ruta, mutada)
                veredicto = ejecutor.ejecutar(timeout_s)
            finally:
                _escribir(ruta, fuente)

            if veredicto == SUPERVIVIENTE:
                informe.supervivientes.append(mutante)
            elif veredicto == TIMEOUT:
                informe.timeouts.append(mutante)
            else:
                informe.muertos += 1

            if eco is not None:
                eco(
                    f"[{indice}/{len(mutantes)}] {veredicto:13} "
                    f"{mutante.descripcion()}"
                )
    finally:
        # Red de seguridad: si algo se torció entre medias, el árbol vuelve a
        # su estado original igualmente.
        for fichero, fuente in fuentes.items():
            ruta = base / fichero
            if ruta.is_file() and _leer(ruta) != fuente:
                _escribir(ruta, fuente)
        informe.segundos = time.monotonic() - inicio

    return informe


# --- Informe ----------------------------------------------------------------


def escribir_informe(informe: InformeMutacion, ruta: Path) -> None:
    """Escribe el informe de la campaña en Markdown."""
    alcance = informe.alcance
    lineas: list[str] = [
        f"<!-- {ruta.as_posix()} -->",
        f"# {informe.feature} · Campaña de mutación",
        "",
        f"Generado por `python -m harness.mutacion --feature {informe.feature}` "
        f"el {datetime.now().strftime('%Y-%m-%d %H:%M')}.",
        "",
        "## Alcance",
        "",
        f"Origen del diff: **{alcance.origen}** "
        f"(`{alcance.ref_diff[0]}` .. `{alcance.ref_diff[1]}`).",
        "",
        "| Fichero | Líneas en alcance |",
        "|---|---|",
    ]
    for fichero in alcance.ficheros():
        lineas.append(f"| `{fichero}` | {len(alcance.lineas[fichero])} |")
    lineas += [
        f"| **Total** | **{alcance.total_lineas()}** |",
        "",
        "## Totales",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Mutantes generados | {informe.generados} |",
        f"| Mutantes evaluados | {informe.evaluados} |",
        f"| Muertos | {informe.muertos} |",
        f"| Supervivientes | {len(informe.supervivientes)} |",
        f"| Timeouts | {len(informe.timeouts)} |",
        f"| Tiempo total | {informe.segundos:.1f} s |",
    ]
    if informe.muestreado:
        lineas.append(
            f"| Muestreo | sí — {informe.evaluados} de {informe.generados} "
            f"mutantes, semilla `{informe.semilla}` |"
        )
    else:
        lineas.append("| Muestreo | no: campaña completa |")

    lineas += ["", "## Supervivientes", ""]
    if not informe.supervivientes:
        lineas += ["Ninguno: cada mutación aplicada la cazó al menos un test.", ""]
    else:
        lineas += [
            "Cada superviviente es una línea que ningún test comprueba de verdad, "
            "o una mutación equivalente. Distinguirlo es trabajo del implementer: "
            "el análisis no puede quedarse en PENDIENTE al cerrar la feature.",
            "",
        ]
        for numero, mutante in enumerate(informe.supervivientes, start=1):
            lineas += [
                f"### {numero}. `{mutante.fichero}:{mutante.linea}` "
                f"[{mutante.operador}]",
                "",
                f"- Original: `{mutante.original}`",
                f"- Mutado:   `{mutante.mutado}`",
                "",
                "#### Análisis (PENDIENTE del implementer)",
                "",
                "> Por qué ningún test lo caza: PENDIENTE.",
                "> Decisión: ¿test nuevo o mutante equivalente justificado?",
                "",
            ]

    if informe.timeouts:
        lineas += ["## Timeouts", ""]
        for mutante in informe.timeouts:
            lineas.append(f"- `{mutante.fichero}:{mutante.linea}` {mutante.descripcion()}")
        lineas.append("")

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# --- CLI --------------------------------------------------------------------


def _analizar_argumentos(argv: list[str] | None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m harness.mutacion",
        description=(
            "Muta las líneas de producción que toca una feature y comprueba "
            "cuántas mutaciones sobreviven a la suite de tests."
        ),
    )
    analizador.add_argument("--feature", required=True, help="Identificador, p. ej. F-001")
    analizador.add_argument("--base", default="dev", help="Rama de integración")
    analizador.add_argument("--rama", default=None, help="Rama de la feature")
    analizador.add_argument("--raiz", default=".", help="Raíz del repositorio a mutar")
    analizador.add_argument("--timeout", type=int, default=None, help="Segundos por mutante")
    analizador.add_argument("--max-mutantes", type=int, default=None)
    analizador.add_argument("--semilla", type=int, default=None)
    analizador.add_argument("--salida", default=None, help="Ruta del informe")
    return analizador.parse_args(argv)


def main(argv: list[str] | None = None, ejecutor: object | None = None) -> int:
    """Punto de entrada: 0 sin supervivientes, 1 con ellos, 2 error de uso."""
    opciones = _analizar_argumentos(argv)
    timeout_s = opciones.timeout or TIMEOUT_POR_DEFECTO

    try:
        alcance = alcance_de_feature(
            opciones.feature, base=opciones.base, rama=opciones.rama, raiz=opciones.raiz
        )
    except SystemExit as parada:
        print(str(parada), file=sys.stderr)
        return 2

    print(alcance.descripcion())
    if not alcance.lineas:
        print("Sin líneas de producción en el alcance: nada que mutar.")

    informe = ejecutar_campania(
        alcance,
        ejecutor or EjecutorPytest(raiz=opciones.raiz),
        timeout_s=timeout_s,
        raiz=opciones.raiz,
        max_mutantes=opciones.max_mutantes,
        semilla=opciones.semilla,
        eco=lambda linea: print(linea, flush=True),
    )

    destino = Path(opciones.salida or f"progress/mutacion_{opciones.feature}.md")
    escribir_informe(informe, destino)
    print(
        f"{informe.evaluados} mutantes evaluados, {informe.muertos} muertos, "
        f"{len(informe.supervivientes)} supervivientes, "
        f"{len(informe.timeouts)} timeouts en {informe.segundos:.1f} s"
    )
    print(f"Informe: {destino.as_posix()}")
    return 1 if informe.supervivientes else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
