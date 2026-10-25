# etl_sigrid/infrastructure/config/hipotesis_caja_yaml.py
"""
Lee `config/hipotesis_caja.yaml` (F-140, D13-A y D14-A) y lo entrega al
dominio para validarlo.

Solo adapta: abre el fichero, comprueba su forma (un mapa con `hipotesis` y,
si está, `obras`, las dos listas) y pasa las filas a
`etl_sigrid.domain.proyeccion_caja`, que es quien sabe qué es una hipótesis
válida. Devuelve los errores en vez de lanzarlos para que el paso
`build_tesoreria` falle con la lista ENTERA y sin escribir nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from etl_sigrid.domain.proyeccion_caja import (
    Hipotesis,
    construir_catalogo,
    validar_catalogo,
    validar_valores_obra,
)

#: El catálogo del repositorio: `config/hipotesis_caja.yaml`.
RUTA_POR_DEFECTO = Path(__file__).resolve().parents[3] / "config" / "hipotesis_caja.yaml"


@dataclass(frozen=True, slots=True)
class HipotesisLeidas:
    """Lo leído del YAML. `errores` vacío = se puede publicar.

    Con errores en el catálogo, `catalogo` va vacío: sin catálogo válido las
    obras no se pueden validar, y no se publica nada.
    """

    catalogo: tuple[Hipotesis, ...]
    obras: list[dict[str, Any]] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def cargar_hipotesis_caja(ruta: Path | None = None) -> HipotesisLeidas:
    """Lee y valida el YAML de hipótesis. `FileNotFoundError` si no existe."""
    ruta = RUTA_POR_DEFECTO if ruta is None else ruta
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        return HipotesisLeidas((), [], [f"{ruta.name}: no es un mapa con la seccion hipotesis"])
    filas = datos.get("hipotesis")
    obras = datos.get("obras")
    obras = [] if obras is None else obras
    errores: list[str] = []
    if not isinstance(filas, list):
        errores.append(f"{ruta.name}: la seccion hipotesis tiene que ser una lista")
    if not isinstance(obras, list):
        errores.append(f"{ruta.name}: la seccion obras tiene que ser una lista")
    if errores:
        return HipotesisLeidas((), [], errores)
    errores = validar_catalogo(filas)
    if errores:
        return HipotesisLeidas((), obras, errores)
    catalogo = construir_catalogo(filas)
    errores = validar_valores_obra(obras, {h.codigo: h for h in catalogo})
    return HipotesisLeidas(catalogo, obras, errores)
