# harness/cobertura.py
"""Puerta de cobertura de las LÍNEAS CAMBIADAS por la feature en curso.

No mide la cobertura global del repositorio —esa es deuda histórica, se ve
pero no bloquea—, sino la de lo que esta feature acaba de escribir. Cruza el
JSON de `coverage` con el mismo alcance de diff que usa la mutación: una sola
fuente de verdad para el «qué cambió».

La puerta decide ella misma si aplica. No aplica en la rama de integración, ni
cuando no hay líneas Python de producción cambiadas, ni cuando el nivel de
rigor de la feature no exige cobertura: en esos casos se declara N/A **con el
motivo escrito**, que es distinto de aprobar en silencio.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

from harness.alcance import alcance_de_feature, ejecutar_git
from harness.rigor import (
    RUTA_FEATURES,
    RUTA_RIGOR,
    cargar_features,
    cargar_rigor,
    exige,
    feature_de_rama,
    nivel_de_feature,
    umbral_cobertura,
)

ETIQUETA = "PUERTA COBERTURA"
MENSAJE_INSTALACION = (
    "falta la medición de cobertura y la puerta aplica: "
    "pip install -r requirements-dev.txt"
)


def hay_coverage() -> bool:
    """¿Está instalada la herramienta de medición?"""
    return importlib.util.find_spec("coverage") is not None


def rama_actual(raiz: str = ".") -> str:
    return ejecutar_git(["branch", "--show-current"], raiz=raiz).strip()


def lineas_ejecutables(fuente: str) -> set[int]:
    """Líneas con sentencia de un fuente Python.

    Sirve para los ficheros que NO aparecen en el informe de coverage: un
    módulo nuevo que ningún test importa no puede salir gratis por no haberse
    medido.
    """
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return set()
    return {
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.stmt) and nodo.lineno
    }


def _indexar(cov: dict) -> dict[str, dict]:
    """Normaliza las rutas del JSON de coverage (separadores del sistema)."""
    return {
        ruta.replace("\\", "/"): datos for ruta, datos in cov.get("files", {}).items()
    }


def cobertura_lineas_cambiadas(
    cov: dict, lineas: dict[str, set[int]], raiz: str = "."
) -> tuple[int, int]:
    """Devuelve (líneas cubiertas, líneas ejecutables) dentro del alcance."""
    medidos = _indexar(cov)
    cubiertas = 0
    totales = 0

    for fichero, numeros in lineas.items():
        clave = fichero.replace("\\", "/")
        datos = medidos.get(clave)
        if datos is None:
            ruta = Path(raiz) / clave
            if not ruta.is_file():
                continue
            ejecutables = lineas_ejecutables(ruta.read_text(encoding="utf-8"))
            totales += len(numeros & ejecutables)
            continue
        ejecutadas = set(datos.get("executed_lines", []))
        ausentes = set(datos.get("missing_lines", []))
        relevantes = numeros & (ejecutadas | ausentes)
        totales += len(relevantes)
        cubiertas += len(relevantes & ejecutadas)

    return cubiertas, totales


def _na(motivo: str) -> int:
    print(f"{ETIQUETA}: N/A ({motivo})")
    return 0


def _ko(motivo: str) -> int:
    print(f"{ETIQUETA}: {motivo}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    """Puerta de cobertura: 0 si pasa o no aplica, 1 si falla."""
    analizador = argparse.ArgumentParser(
        prog="python -m harness.cobertura",
        description="Comprueba la cobertura de las líneas cambiadas por la feature.",
    )
    analizador.add_argument("--base", default="dev", help="Rama de integración")
    analizador.add_argument("--config", default=str(RUTA_RIGOR))
    analizador.add_argument("--features", default=str(RUTA_FEATURES))
    analizador.add_argument("--cov", default="coverage.json")
    analizador.add_argument("--raiz", default=".")
    opciones = analizador.parse_args(argv)

    try:
        rigor = cargar_rigor(opciones.config)
    except ValueError as error:
        return _ko(str(error))

    rama = rama_actual(opciones.raiz)
    if not rama or rama in (opciones.base, "main", "master"):
        return _na(f"rama {rama or '(detached)'}: solo aplica en ramas de feature")

    feature = feature_de_rama(rama, cargar_features(opciones.features))
    if feature is None:
        return _na(f"la rama {rama} no corresponde a ninguna feature declarada")

    nivel = nivel_de_feature(feature, rigor)
    if not exige(nivel, "cobertura", rigor):
        return _na(f"{feature.get('id')} es de nivel {nivel}: no exige cobertura")

    try:
        alcance = alcance_de_feature(
            feature.get("id", ""),
            base=opciones.base,
            rama=rama,
            raiz=opciones.raiz,
        )
    except SystemExit as parada:
        return _na(f"no se pudo calcular el alcance: {parada}")

    if not alcance.lineas:
        return _na(
            f"{feature.get('id')} no cambia líneas Python de producción frente a "
            f"{opciones.base}"
        )

    ruta_cov = Path(opciones.cov)
    if not hay_coverage() or not ruta_cov.is_file():
        return _ko(MENSAJE_INSTALACION)

    try:
        datos = json.loads(ruta_cov.read_text(encoding="utf-8"))
    except ValueError as error:
        return _ko(f"{ruta_cov.as_posix()} no es JSON válido: {error}")

    cubiertas, totales = cobertura_lineas_cambiadas(datos, alcance.lineas, opciones.raiz)
    if totales == 0:
        return _na(
            f"{feature.get('id')}: las líneas cambiadas no contienen sentencias "
            "ejecutables"
        )

    umbral = umbral_cobertura(rigor)
    porcentaje = 100.0 * cubiertas / totales
    resumen = (
        f"{porcentaje:.1f}% de {totales} líneas cambiadas cubiertas "
        f"({cubiertas}/{totales}, umbral {umbral}%, nivel {nivel})"
    )
    if porcentaje + 1e-9 < umbral:
        return _ko(resumen)
    print(f"{ETIQUETA}: {resumen}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
