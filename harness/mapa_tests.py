# harness/mapa_tests.py
"""Mapa línea -> tests de la campaña de mutación (F-019).

Hasta la 1.9.0 cada mutante pagaba la suite ENTERA, también el que muere al
primer test que toca su línea y el que vive en una línea que ningún proceso
ejecuta. Aquí se mide UNA vez, con coverage y un plugin propio de pytest, qué
test ejecuta cada línea de los ficheros del alcance, y con eso la campaña:

- **poda** el mutante cuya sentencia no ejecuta NINGÚN proceso medido: es
  superviviente sin correr nada (no puede cambiar ninguna ejecución);
- juzga con el **subconjunto** de tests que ejecutan su sentencia, validado
  antes sin mutar; solo su código 1 (muerto) es definitivo, cualquier otro
  resultado se revalida con la suite entera;
- y juzga con la **suite entera** lo que solo se ejecuta sin test atribuible
  (subprocesos, importación, copias del árbol).

Dos capas, en los términos de `docs/ARCHITECTURE.md`: el DOMINIO (clasificar,
leer el volcado) son funciones puras sin E/S; el ADAPTADOR (`medir`) lanza
coverage y pytest en subproceso con el intérprete del ejecutor. El intérprete
de la campaña no necesita coverage: lee el volcado con `json`.

Riesgo residual, escrito para que nadie lo olvide: un subproceso que NO hereda
el entorno, o que corre con otro intérprete sin coverage, no se mide, y sus
líneas parecerían no ejecutadas. Por eso el PODADO sale aparte en el informe y
es superviviente: en `critico` exige su justificación escrita (decisión D1).
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

#: Clases de un mutante frente al mapa.
PODAR = "podar"
SUBCONJUNTO = "subconjunto"
SUITE = "suite"
Clase = Literal["podar", "subconjunto", "suite"]

#: Caracteres que puede ocupar la lista de nodeids en la orden de pytest. Por
#: debajo del límite de 32 767 de la línea de órdenes de Windows, con margen
#: para el intérprete, los argumentos del ejecutor y la ruta. Constante de
#: código y no de configuración, con el mismo criterio que `MARGEN_TIMEOUT`:
#: es un parámetro del mecanismo, no de la máquina.
TOPE_CARACTERES_ORDEN = 24_000

#: Versión mínima de coverage: `[run] patch = subprocess` llega en la 7.10.
VERSION_MINIMA_COVERAGE = (7, 10)

#: Variable con la que el plugin sabe dónde escribir el orden de recolección.
VARIABLE_ORDEN = "ARNES_CONTEXTOS_ORDEN"

#: Directorio del plugin de pytest y del volcado. Sin `__init__.py` a propósito:
#: se antepone a `PYTHONPATH` y se carga con `-p arnes_contextos`, así que lo
#: importa también el venv de un servicio, que no ve el paquete `harness`.
DIRECTORIO_PLUGIN = Path(__file__).resolve().parent / "pytest_arnes"


@dataclass(frozen=True)
class MapaTests:
    """Qué tests ejecutan cada línea de los ficheros del alcance.

    `contextos` va por ruta RELATIVA al directorio del ejecutor, y por línea;
    el contexto `""` es una ejecución sin test atribuible (importación,
    subproceso, copia del fichero fuera del árbol). Inmutable: el mismo mapa
    vale para todos los mutantes y todos los workers (R5).
    """

    sha: str
    orden: tuple[str, ...]
    contextos: dict[str, dict[int, frozenset[str]]]
    segundos: float


@dataclass(frozen=True)
class Degradado:
    """Por qué un ejecutor NO tiene mapa: juzga todo con la suite entera (R18)."""

    motivo: str


# --- Dominio -----------------------------------------------------------------


def _inicio(nodo: ast.AST) -> int:
    """Primera línea del nodo, decoradores incluidos."""
    if isinstance(nodo, ast.match_case):
        return nodo.pattern.lineno
    lineas = [nodo.lineno]  # type: ignore[attr-defined]
    lineas += [d.lineno for d in getattr(nodo, "decorator_list", [])]
    return min(lineas)


def _fin(nodo: ast.AST) -> int:
    if isinstance(nodo, ast.match_case):
        return nodo.body[-1].end_lineno or nodo.pattern.lineno
    return nodo.end_lineno or nodo.lineno  # type: ignore[attr-defined]


def _hijos(nodo: ast.AST) -> list[ast.AST]:
    """Sentencias anidadas: cuerpos, `else`, `finally`, `except` y `case`."""
    hijos: list[ast.AST] = []
    for campo in ("body", "orelse", "finalbody", "handlers", "cases"):
        for hijo in getattr(nodo, campo, None) or []:
            if isinstance(hijo, (ast.stmt, ast.excepthandler, ast.match_case)):
                hijos.append(hijo)
    return hijos


def _mas_interna(nodos: list[ast.AST], linea: int) -> ast.AST | None:
    for nodo in nodos:
        if _inicio(nodo) <= linea <= _fin(nodo):
            return _mas_interna(_hijos(nodo), linea) or nodo
    return None


def lineas_de_sentencia(fuente: str, linea: int) -> set[int]:
    """Líneas cuya ejecución dice si la sentencia de `linea` se ejecutó (R7).

    Sentencia SIMPLE más interna que contiene la línea: de `lineno` a
    `end_lineno`, porque las constantes plegadas de una sentencia multilínea
    no tienen evento de línea propio (hallazgo b). COMPUESTA: su cabecera
    —de `lineno` a la línea anterior a su primer hijo— y sus decoradores, sin
    el cuerpo. La línea pedida entra siempre: un `else:` no es sentencia y cae
    en la cabecera de su `if`. Fuera de toda sentencia, o con un fuente que no
    compila, solo la propia línea.
    """
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError):
        return {linea}
    nodo = _mas_interna(list(arbol.body), linea)
    if nodo is None:
        return {linea}
    hijos = _hijos(nodo)
    if not hijos:
        return set(range(_inicio(nodo), _fin(nodo) + 1)) | {linea}
    cabecera = nodo.pattern.lineno if isinstance(nodo, ast.match_case) else nodo.lineno  # type: ignore[attr-defined]
    primero = min(_inicio(hijo) for hijo in hijos)
    lineas = set(range(cabecera, max(cabecera + 1, primero)))
    for decorador in getattr(nodo, "decorator_list", []):
        lineas |= set(range(decorador.lineno, (decorador.end_lineno or decorador.lineno) + 1))
    return lineas | {linea}


def contextos_de(mapa: MapaTests, fichero: str, lineas: set[int]) -> frozenset[str]:
    """Unión de los contextos de esas líneas; vacía si ningún proceso las ejecutó."""
    por_linea = mapa.contextos.get(fichero, {})
    return frozenset().union(*(por_linea.get(linea, frozenset()) for linea in lineas))


def cabe_en_orden(ids: tuple[str, ...] | list[str], tope: int = TOPE_CARACTERES_ORDEN) -> bool:
    """¿Los nodeids, separados por un espacio, no pasan de `tope` caracteres?"""
    return sum(len(nodeid) + 1 for nodeid in ids) <= tope


def clasificar(contextos: frozenset[str], orden: tuple[str, ...]) -> tuple[Clase, tuple[str, ...]]:
    """Cómo se juzga un mutante, según los contextos de su sentencia.

    - Ninguno: `podar` (R8). Es el ÚNICO caso que poda (R12).
    - Solo el vacío: `suite` (R10).
    - Con nodeids: `subconjunto`, en el orden de recolección (R9); el `""` se
      ignora, porque si hay que revalidar la suite entera ya lo cubre.
    - El subconjunto es la suite entera o no cabe en la orden: `suite` (R11).
    - Un nodeid que no está en `orden` no se inventa: `suite`.
    """
    if not contextos:
        return (PODAR, ())
    ids = [contexto for contexto in contextos if contexto]
    if not ids:
        return (SUITE, ())
    posicion = {nodeid: indice for indice, nodeid in enumerate(orden)}
    if any(nodeid not in posicion for nodeid in ids):
        return (SUITE, ())
    elegidos = tuple(sorted(ids, key=posicion.__getitem__))
    if len(elegidos) >= len(orden) or not cabe_en_orden(elegidos):
        return (SUITE, ())
    return (SUBCONJUNTO, elegidos)


def _normalizar(ruta: str, sin_mayusculas: bool) -> str:
    texto = ruta.replace("\\", "/").rstrip("/")
    return texto.casefold() if sin_mayusculas else texto


def leer_volcado(
    datos: dict,
    raiz_ejecutor: str,
    rutas: list[str],
    sin_mayusculas: bool | None = None,
) -> dict[str, dict[int, frozenset[str]]]:
    """Contextos por línea de cada ruta del alcance, desde el volcado compacto.

    Una ruta medida igual a `<raíz del ejecutor>/<ruta>` aporta sus contextos
    tal cual. Una que solo TERMINA en `/<ruta>` es una copia del fichero que un
    test hizo en otro sitio (hallazgo c): sus líneas cuentan como ejecución SIN
    test atribuible, `""` (R4). Así, un mutante que una copia ejecuta no se
    poda nunca, y tampoco se le atribuye un test que no lo ejecutó en el árbol.

    Separadores normalizados a `/`; sin distinguir mayúsculas en Windows.
    """
    if sin_mayusculas is None:
        sin_mayusculas = os.name == "nt"
    nombres: list[str] = list(datos.get("contextos", []))
    raiz = _normalizar(str(Path(raiz_ejecutor).resolve()), sin_mayusculas)
    objetivos = {ruta: _normalizar(ruta, sin_mayusculas) for ruta in rutas}
    acumulado: dict[str, dict[int, set[str]]] = {ruta: {} for ruta in rutas}
    for medido, por_linea in (datos.get("ficheros") or {}).items():
        normal = _normalizar(medido, sin_mayusculas)
        for ruta, relativa in objetivos.items():
            destino = acumulado[ruta]
            if normal == f"{raiz}/{relativa}":
                for linea, indices in por_linea.items():
                    # Una línea medida sin contexto alguno sigue siendo una
                    # línea EJECUTADA: nunca puede quedar como «no ejecutada».
                    destino.setdefault(int(linea), set()).update(
                        [nombres[i] for i in indices] or [""]
                    )
            elif normal.endswith(f"/{relativa}"):
                for linea in por_linea:
                    destino.setdefault(int(linea), set()).add("")
    return {
        ruta: {linea: frozenset(contextos) for linea, contextos in por_linea.items()}
        for ruta, por_linea in acumulado.items()
    }


def version_de_coverage_suficiente(texto: str) -> bool:
    """¿La salida de `coverage --version` es de una 7.10 o posterior?"""
    encontrada = re.search(r"version\s+(\d+)\.(\d+)", texto)
    if encontrada is None:
        return False
    return (int(encontrada.group(1)), int(encontrada.group(2))) >= VERSION_MINIMA_COVERAGE


def construir_mapa(
    datos: dict,
    orden: list[str],
    raiz_ejecutor: str,
    rutas: list[str],
    sha: str,
    segundos: float,
) -> MapaTests | Degradado:
    """El mapa a partir del volcado y del orden de recolección, o por qué no.

    Sin tests recogidos o sin un solo contexto de test en el volcado no hay
    mapa (R18): podar con él sería podarlo todo por un plugin que no se cargó.
    """
    if not orden:
        return Degradado("la medición del mapa no recogió ningún test")
    if not any(nombre for nombre in datos.get("contextos", [])):
        return Degradado(
            "el mapa no trae ningún contexto de test (¿se cargó el plugin "
            "arnes_contextos?)"
        )
    return MapaTests(
        sha=sha,
        orden=tuple(orden),
        contextos=leer_volcado(datos, raiz_ejecutor, rutas),
        segundos=segundos,
    )


# --- Adaptador: coverage y pytest en subproceso ------------------------------

#: Segundos para preguntar la versión de coverage o el SHA: no miden nada.
TIMEOUT_VERSION_S = 120

#: Variables de un coverage EXTERIOR que no deben colarse en la medición del
#: mapa: si la propia campaña corre dentro de otra medición, el `.pth` del
#: intérprete arrancaría la exterior en cada proceso de la suite.
_VARIABLES_DE_OTRO_COVERAGE = (
    "COVERAGE_PROCESS_CONFIG",
    "COVERAGE_PROCESS_START",
    "COVERAGE_RCFILE",
)


def _version_de_coverage(ejecutable: str, entorno: dict[str, str]) -> tuple[int, str]:
    """`(código, salida)` de `<ejecutable> -m coverage --version`."""
    proceso = subprocess.run(
        [ejecutable, "-m", "coverage", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_VERSION_S,
        env=entorno,
        check=False,
    )
    return proceso.returncode, (proceso.stdout or "") + (proceso.stderr or "")


def _sha(raiz: str) -> str:
    """SHA de HEAD del árbol donde se mide; cadena vacía fuera de git."""
    try:
        proceso = subprocess.run(
            ["git", "-C", raiz, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_VERSION_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proceso.stdout.strip() if proceso.returncode == 0 else ""


def _rcfile(datos: Path, rutas: list[str]) -> str:
    """`.coveragerc` de la medición: subprocesos, datos absolutos y solo el alcance.

    `include` lleva `*/<ruta>` por fichero: limita lo medido al alcance y casa
    también con las copias que un test haga del fichero en otro sitio (R4).
    `data_file` absoluto, para que un subproceso con otro `cwd` escriba donde
    toca; `parallel`, para que cada proceso escriba el suyo.
    """
    patrones = "\n".join(f"    */{ruta}" for ruta in rutas)
    return (
        "[run]\n"
        "patch = subprocess\n"
        "parallel = true\n"
        f"data_file = {datos.as_posix()}\n"
        f"include =\n{patrones}\n"
    )


def medir(ejecutor: object, rutas: list[str], timeout_s: int) -> MapaTests | Degradado:
    """Mide el mapa de `rutas` (relativas a la raíz del ejecutor) con su suite.

    La suite ENTERA del ejecutor, con los argumentos de su línea base y su ruta,
    bajo `coverage run` y el plugin `arnes_contextos`, en su raíz y con su
    intérprete (R1). Todo lo que escribe va a un temporal FUERA del árbol, que
    se borra al terminar. Cualquier cosa rara —sin coverage, coverage anterior
    a 7.10, suite roja o expirada, volcado ilegible— es un `Degradado` con su
    motivo: sin mapa nunca se poda (R18).
    """
    arranque = time.monotonic()
    ejecutable = str(ejecutor.ejecutable)  # type: ignore[attr-defined]
    raiz = str(ejecutor.raiz)  # type: ignore[attr-defined]
    entorno = dict(ejecutor.entorno())  # type: ignore[attr-defined]
    for variable in _VARIABLES_DE_OTRO_COVERAGE:
        entorno.pop(variable, None)
    try:
        codigo, version = _version_de_coverage(ejecutable, entorno)
    except (OSError, subprocess.TimeoutExpired) as error:
        return Degradado(f"no se pudo preguntar la versión de coverage a {ejecutable}: {error}")
    if codigo != 0:
        return Degradado(f"el intérprete {ejecutable} no tiene coverage")
    if not version_de_coverage_suficiente(version):
        return Degradado(
            f"coverage de {ejecutable} es anterior a 7.10 ({version.strip()}): sin "
            "`patch = subprocess` no se distingue «solo en subproceso» de «nunca»"
        )

    temporal = Path(tempfile.mkdtemp(prefix="arnes-mapa-"))
    try:
        datos = temporal / "datos" / ".coverage"
        datos.parent.mkdir()
        rc = temporal / "coveragerc"
        rc.write_text(_rcfile(datos, rutas), encoding="utf-8")
        orden_json = temporal / "orden.json"
        volcado_json = temporal / "volcado.json"
        previo = entorno.get("PYTHONPATH")
        entorno["PYTHONPATH"] = os.pathsep.join(
            [str(DIRECTORIO_PLUGIN), *([previo] if previo else [])]
        )
        entorno[VARIABLE_ORDEN] = str(orden_json)
        ruta = getattr(ejecutor, "ruta", None)
        orden = [
            ejecutable, "-m", "coverage", "run", f"--rcfile={rc}", "-m", "pytest",
            *ejecutor.argumentos_linea_base(),  # type: ignore[attr-defined]
            "-p", "arnes_contextos",
            *([ruta] if ruta else []),
        ]
        try:
            proceso = subprocess.run(
                orden, cwd=raiz, capture_output=True, timeout=timeout_s, env=entorno,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Degradado(f"la medición del mapa expiró a los {timeout_s} s")
        if proceso.returncode != 0:
            return Degradado(
                f"la suite bajo coverage no salió verde (código {proceso.returncode})"
            )
        restante = max(1, int(timeout_s - (time.monotonic() - arranque)))
        try:
            combinado = subprocess.run(
                [ejecutable, "-m", "coverage", "combine", f"--rcfile={rc}", "-q"],
                cwd=temporal, capture_output=True, timeout=restante, env=entorno,
                check=False,
            )
            volcado = subprocess.run(
                [ejecutable, str(DIRECTORIO_PLUGIN / "arnes_volcar_mapa.py"), str(datos),
                 str(volcado_json)],
                cwd=temporal, capture_output=True, timeout=restante, env=entorno,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return Degradado(f"el volcado del mapa expiró a los {timeout_s} s")
        if combinado.returncode != 0 or volcado.returncode != 0:
            return Degradado(
                f"no se pudo combinar o volcar el mapa (códigos {combinado.returncode} "
                f"y {volcado.returncode})"
            )
        try:
            leidos = json.loads(volcado_json.read_text(encoding="utf-8"))
            recogidos = json.loads(orden_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            return Degradado(f"el volcado o el orden del mapa no se pueden leer: {error}")
        if not isinstance(leidos, dict) or not isinstance(recogidos, list):
            return Degradado("el volcado o el orden del mapa no tienen el formato esperado")
        return construir_mapa(
            leidos, [str(nodeid) for nodeid in recogidos], raiz, rutas, _sha(raiz),
            time.monotonic() - arranque,
        )
    finally:
        shutil.rmtree(temporal, ignore_errors=True)
