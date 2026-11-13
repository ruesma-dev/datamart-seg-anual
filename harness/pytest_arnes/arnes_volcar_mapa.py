# harness/pytest_arnes/arnes_volcar_mapa.py
"""Vuelca los datos de coverage a un JSON compacto de contextos por línea (F-019).

Uso: `<intérprete del ejecutor> arnes_volcar_mapa.py <datos de coverage> <salida>`.

Lo corre el MISMO intérprete que midió (el que tiene coverage), con la API
pública `CoverageData.contexts_by_lineno`. Escribe

    {"contextos": [nombre, ...], "ficheros": {ruta: {línea: [índice, ...]}}}

y la campaña lo lee con `json`, sin necesitar coverage. No `coverage json
--show-contexts`: sobre la suite del payload dio 776 MB frente a 388 KB de
este volcado (§1.4 de `progress/spec_F-019.md`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def volcar(datos: str, salida: str) -> None:
    from coverage import CoverageData

    medidos = CoverageData(basename=datos)
    medidos.read()
    nombres = sorted(medidos.measured_contexts())
    indice = {nombre: posicion for posicion, nombre in enumerate(nombres)}
    ficheros: dict[str, dict[str, list[int]]] = {}
    for fichero in sorted(medidos.measured_files()):
        ficheros[fichero] = {
            str(linea): sorted(indice[contexto] for contexto in contextos)
            for linea, contextos in sorted(medidos.contexts_by_lineno(fichero).items())
        }
    Path(salida).write_text(
        json.dumps({"contextos": nombres, "ficheros": ficheros}, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    volcar(sys.argv[1], sys.argv[2])
