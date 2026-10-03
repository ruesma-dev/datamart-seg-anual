# progress/mediciones/F-113_mutacion_sql.py
"""
F-113 · T7: campaña de mutación MANUAL sobre el SQL de la categoría.

`python -m harness.mutacion` solo muta Python (el dominio); la lógica de F-113
vive también en `sql/stg/04_partidas.sql`, así que sus mutantes se escriben a
mano aquí (lo pidió el reviewer de F-123: el script, versionado en `progress/`).

Método, por cada mutante y EN SERIE (1 worker):

1. Worktree desechable (`git worktree add --detach`) del HEAD actual.
2. Se exige que el texto ORIGINAL aparezca UNA sola vez en el fichero, se
   sustituye por el MUTADO y se ejecutan los tests que leen ese SQL **sin `-x`**
   (`-q --tb=no`), contando los `FAILED`.
3. Se restaura el fichero y se comprueba que vuelve a ser idéntico al original.

Línea base antes y después (tiene que estar verde). Imprime la tabla en
Markdown para `progress/mutacion_F-113.md`.

Uso, desde la raíz del repositorio:

    python progress/mediciones/F-113_mutacion_sql.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SQL = "etl_sigrid/infrastructure/postgres/sql/stg/04_partidas.sql"
TESTS = (
    "tests/test_f113_sql.py",
    "tests/test_f052_sql.py",
    "tests/test_f006_stg_trampas.py",
)

R1 = "WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CD'"
R2 = "WHEN UPPER(p.cod) LIKE 'CI%' THEN 'CI'"
R3 = "WHEN UPPER(p.cod) LIKE 'CP%' THEN 'CP'"
NUM = "WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'CD'"
FIN = "ELSE 'OTRO' END)::TEXT     AS categoria"
LIMPIO = "UPPER(REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))"
IN_EXACTO = "IN ('CD', 'CI', 'CP')"
SANGRIA = "\n              "

#: (id, original, mutado, qué simula). Textos EXACTOS, sin la sangría inicial.
MUTANTES: list[tuple[str, str, str, str]] = [
    ("M01", R1, "WHEN UPPER(p.cod) LIKE '%CD%' THEN 'CD'", "vuelve el comodín delante (CD)"),
    ("M02", R2, "WHEN UPPER(p.cod) LIKE '%CI%' THEN 'CI'", "vuelve el comodín delante (CI): el defecto"),
    ("M03", R3, "WHEN UPPER(p.cod) LIKE '%CP%' THEN 'CP'", "vuelve el comodín delante (CP)"),
    ("M04", R1, "WHEN UPPER(p.cod) LIKE 'CD%' THEN 'CI'", "prefijo CD clasifica como CI"),
    ("M05", R2, "WHEN UPPER(p.cod) LIKE 'C%' THEN 'CI'", "prefijo recortado a C"),
    ("M06", R3, "WHEN UPPER(p.cod) LIKE 'CP%' THEN 'OTRO'", "prefijo CP clasifica como OTRO"),
    ("M07", R1, "WHEN p.cod LIKE 'CD%' THEN 'CD'", "sin UPPER en la raíz (cd minúsculas)"),
    ("M08", R1 + SANGRIA + R2, R2 + SANGRIA + R1, "orden de los WHEN CD/CI (equivalente)"),
    ("M09", "(CASE " + R1, "(CASE " + NUM + SANGRIA + R1, "la numérica antes que los prefijos (equivalente)"),
    ("M10", NUM, "WHEN p.cod ~ '[0-9]+' AND p.cod NOT IN ('34', '99') THEN 'CD'", "numérica sin anclas"),
    ("M11", NUM, "WHEN p.cod ~ '^[0-9]+$' AND p.cod IN ('34', '99') THEN 'CD'", "NOT IN -> IN"),
    ("M12", NUM, "WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34') THEN 'CD'", "fuera el '99'"),
    ("M13", NUM, "WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('33', '99') THEN 'CD'", "'34' -> '33'"),
    ("M14", NUM, "WHEN p.cod ~ '^[0-9]+$' AND p.cod NOT IN ('34', '99') THEN 'OTRO'", "numérica -> OTRO"),
    ("M15", FIN, "ELSE 'CD' END)::TEXT     AS categoria", "ELSE 'OTRO' -> ELSE 'CD'"),
    ("M16", FIN, "ELSE 'OTRO' END)     AS categoria", "sin ::TEXT en la raíz"),
    ("M17", FIN, "ELSE 'OTRO' END)::TEXT     AS categoria_raiz", "la raíz proyecta otro nombre"),
    ("M18", IN_EXACTO, "IN ('CD', 'CI')", "fuera CP de la lista exacta"),
    ("M19", "ELSE a.categoria END)::TEXT AS categoria", "ELSE 'OTRO' END)::TEXT AS categoria", "el intermedio no hereda: ELSE 'OTRO'"),
    ("M20", "ELSE a.categoria END)::TEXT AS categoria", "ELSE a.capitulo_raiz_cod END)::TEXT AS categoria", "hereda el código de la raíz, no su categoría"),
    ("M21", "(CASE WHEN " + LIMPIO, "(CASE WHEN UPPER(REPLACE(h.cod, ' ', ''))", "WHEN sin quitar puntos (C.I. deja de contar)"),
    ("M22", "THEN " + LIMPIO, "THEN UPPER(REPLACE(h.cod, '.', ''))", "THEN sin quitar espacios"),
    ("M23", "THEN " + LIMPIO, "THEN a.categoria", "el intermedio exacto no manda nunca"),
    ("M24", "(CASE WHEN " + LIMPIO, "(CASE WHEN (REPLACE(REPLACE(h.cod, '.', ''), ' ', ''))", "sin UPPER en el intermedio"),
    ("M25", IN_EXACTO, "LIKE ANY (ARRAY['CD%', 'CI%', 'CP%'])", "prefijo en los intermedios (CI10 pasaría a CI)"),
    ("M26", "ELSE a.categoria END)::TEXT AS categoria", "ELSE a.categoria END) AS categoria", "sin ::TEXT en la recursiva"),
    ("M27", "    categoria,\n    ruta_capitulos,\n    nivel,", "    'OTRO' AS categoria,\n    ruta_capitulos,\n    nivel,", "el INSERT no copia la categoría del recursivo"),
]


def _git(*args: str, cwd: Path = RAIZ) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _pytest(arbol: Path) -> tuple[int, list[str], float, str]:
    """Fallos, nombres de los tests caídos, segundos y la línea de resumen."""
    t0 = time.monotonic()
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=arbol,
        capture_output=True,
        text=True,
    ).stdout
    caidos = re.findall(r"^FAILED (\S+)", salida, re.M)
    errores = re.findall(r"^ERROR (\S+)", salida, re.M)
    resumen = salida.strip().splitlines()[-1] if salida.strip() else "(sin salida)"
    return len(caidos) + len(errores), caidos + errores, time.monotonic() - t0, resumen


def main() -> None:
    sha = _git("rev-parse", "HEAD")
    temporal = Path(tempfile.mkdtemp(prefix="f113_mut_sql_"))
    arbol = temporal / "wt"
    _git("worktree", "add", "--detach", str(arbol), sha)
    try:
        ruta = arbol / SQL
        original = ruta.read_bytes()
        texto = original.decode("utf-8")

        n, _, s, resumen = _pytest(arbol)
        print(f"SHA {sha} · worktree {arbol} · 1 worker")
        print(f"Línea base ANTES: {resumen} ({s:.1f} s)")
        assert n == 0, "la línea base no está verde: la campaña no juzga nada"

        filas = []
        t_total = time.monotonic()
        for ident, orig, mut, que in MUTANTES:
            assert texto.count(orig) == 1, f"{ident}: el original aparece {texto.count(orig)} veces"
            linea = texto[: texto.index(orig)].count("\n") + 1
            ruta.write_bytes(texto.replace(orig, mut).encode("utf-8"))
            try:
                n, caidos, s, _ = _pytest(arbol)
            finally:
                ruta.write_bytes(original)
            assert ruta.read_bytes() == original
            nombres = sorted({c.split("::")[-1] for c in caidos})
            filas.append((ident, linea, orig, mut, n, nombres, que, s))
            estado = "MUERTO" if n else "SUPERVIVIENTE"
            print(f"{ident} {estado} fallos={n} ({s:.1f} s) {que}", flush=True)
        total = time.monotonic() - t_total

        n, _, s, resumen = _pytest(arbol)
        print(f"Línea base DESPUÉS: {resumen} ({s:.1f} s)")
        print(f"Tiempo total de los mutantes: {total:.0f} s")

        def celda(t: str) -> str:
            return "`" + t.replace("\n", " ⏎ ").replace("|", "\\|").strip() + "`"

        print()
        print("| Mutante | Fichero:línea | Original | Mutado | Fallos | Qué simula | Tests que caen |")
        print("|---|---|---|---|---|---|---|")
        for ident, linea, orig, mut, n, nombres, que, _ in filas:
            print(
                f"| {ident} | `04_partidas.sql:{linea}` | {celda(orig)} | {celda(mut)} | {n} "
                f"| {que} | {', '.join(nombres)} |"
            )
        vivos = [f[0] for f in filas if f[4] == 0]
        print()
        print(f"{len(filas)} generados, {len(filas) - len(vivos)} muertos, {len(vivos)} supervivientes {vivos}")
    finally:
        _git("worktree", "remove", "--force", str(arbol))


if __name__ == "__main__":
    main()
