# progress/mutacion_dominio_F-067.py
"""
F-067 · Re-verificación del dominio tras cerrar los supervivientes de la campaña.

La campaña de `harness.mutacion` (`progress/mutacion_F-067.md`, sobre
`d088327`) dejó 5 supervivientes y 1 timeout en `domain/historial_estados.py`.
Se cerraron con tests nuevos y con una simplificación de la guarda del 98 %
(ver `progress/impl_F-067.md` §7). Repetir la campaña entera cuesta ~4 h (cada
mutante corre la suite COMPLETA: 1.090 s de línea base con 4 workers), así que
este script genera **los mismos mutantes con el mismo generador**
(`harness.mutacion.generar_mutantes`, sobre TODAS las líneas del fichero) y
los evalúa contra los tests de la feature, que son un SUBCONJUNTO de la suite:
un mutante que muere aquí muere también con la suite entera.

Uso (desde la raíz, con el árbol limpio; restaura el fichero al terminar):
    python progress/mutacion_dominio_F-067.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from harness.mutacion import aplicar_mutante, generar_mutantes

FICHERO = "etl_sigrid/domain/historial_estados.py"
TESTS = ["tests/test_f067_dominio.py", "tests/test_f067_sql.py",
         "tests/test_f006_dataclasses_inmutables.py"]


def _pytest() -> tuple[int, str]:
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    fallos = len(re.findall(r"^(FAILED|ERROR) ", salida, re.MULTILINE))
    return fallos, (salida.strip().splitlines() or [""])[-1]


def main() -> int:
    ruta = Path(FICHERO)
    fuente = ruta.read_text(encoding="utf-8")
    base, resumen = _pytest()
    print(f"LINEA BASE: {base} fallos · {resumen}", flush=True)
    if base:
        return 1
    lineas = set(range(1, fuente.count("\n") + 2))
    mutantes = generar_mutantes(fuente, lineas, FICHERO)
    supervivientes = 0
    try:
        for i, mutante in enumerate(mutantes, 1):
            ruta.write_text(aplicar_mutante(fuente, mutante), encoding="utf-8", newline="\n")
            fallos, _ = _pytest()
            veredicto = "muerto" if fallos else "SUPERVIVIENTE"
            supervivientes += not fallos
            print(f"[{i}/{len(mutantes)}] {veredicto} ({fallos}) {mutante.descripcion()}",
                  flush=True)
    finally:
        ruta.write_text(fuente, encoding="utf-8", newline="\n")
    final, resumen = _pytest()
    print(f"{len(mutantes)} mutantes, {supervivientes} supervivientes. "
          f"LINEA BASE FINAL: {final} fallos · {resumen}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
