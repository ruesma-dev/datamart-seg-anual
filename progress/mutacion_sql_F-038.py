# progress/mutacion_sql_F-038.py
"""
F-038 · Campaña de mutación MANUAL sobre el SQL de la Fase 1.

`harness.mutacion` solo muta Python, y la lógica de F-038 vive sobre todo en
SQL (`compras/00_setup.sql` y `compras/08_comparativos.sql`). Este script
aporta la evidencia que falta: cada mutante es una sustitución de texto EXACTA
que cambia el comportamiento del SQL; se aplica en un worktree desechable, se
ejecuta el subconjunto de tests sin `-x` y se cuentan los FAILED.

Uso (desde la raíz del repositorio):
    python progress/mutacion_sql_F-038.py <ruta_worktree_desechable>

El worktree se crea con `git worktree add --detach <ruta> HEAD` y se borra
después con `git worktree remove --force <ruta>`. Un solo worker, en serie.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SQL = "etl_sigrid/infrastructure/postgres/sql/compras/"
TESTS = [
    "tests/test_f038_sql.py",
    "tests/test_f038_dominio.py",
    "tests/test_f038_diccionario.py",
    "tests/test_f084_sql.py",
    "tests/test_f006_fichas.py",
]

#: (id, fichero, texto ORIGINAL, texto MUTADO, qué rompe).
MUTANTES = [
    ("M01", "00_setup.sql", "x.c NOT IN ('A99999999', 'A00000000')",
     "x.c NOT IN ('A99999999')", "A00000000 pasa a CIF real"),
    ("M02", "00_setup.sql", "WHEN x.n ~ 'CUATRIM' THEN", "WHEN x.n ~ 'CUATRI' THEN",
     "patrón de familia distinto del dominio"),
    ("M03", "00_setup.sql", "'[^A-Z0-9]+', ' ', 'g'", "'[^A-Z]+', ' ', 'g'",
     "la normalización se come las cifras (FASE 0)"),
    ("M04", "00_setup.sql", "'PLANIFICACION DE ESPACIOS') > 0 THEN NULL",
     "'PLANIFICACION DE ESPACIOS') >= 0 THEN NULL", "toda oferta excluida"),
    ("M05", "00_setup.sql", "WHEN x.c = 'A00000000' THEN 'OFICINA_TECNICA'",
     "WHEN x.c = 'A00000000' THEN 'OBJETIVO'", "familia de respaldo cambiada"),
    ("M06", "08_comparativos.sql", "WHERE l.ctride > 0\n        GROUP BY l.comide",
     "WHERE l.ctride >= 0\n        GROUP BY l.comide", "la guarda cuenta el 0 como contrato"),
    ("M07", "08_comparativos.sql", "HAVING count(DISTINCT l.ctride) > 1",
     "HAVING count(DISTINCT l.ctride) > 2", "la guarda deja pasar dos contratos"),
    ("M08", "08_comparativos.sql", "COALESCE(c.est = 6, FALSE)",
     "COALESCE(c.est = 5, FALSE)", "ganadora con otro estado"),
    ("M09", "08_comparativos.sql", "d.totbas::NUMERIC(18, 2)",
     "d.totdoc::NUMERIC(18, 2)", "importe con IVA"),
    ("M10", "08_comparativos.sql", "WHERE lp.comlinide > 0",
     "WHERE lp.comlinide >= 0", "líneas de oferta sin línea de comparativo"),
    ("M11", "08_comparativos.sql", "compras.fn_estado_documento(12, c.est)",
     "compras.fn_estado_documento(46, c.est)", "estado de la oferta con el tipo del comparativo"),
    ("M12", "08_comparativos.sql", "count(*) FILTER (WHERE NOT o.es_ficticia) AS n_ofertas_reales",
     "count(*) FILTER (WHERE o.es_ficticia) AS n_ofertas_reales", "reales = ficticias"),
    ("M13", "08_comparativos.sql",
     "MIN(o.importe_ofertado_documento) FILTER (WHERE NOT o.es_ficticia AND ",
     "MIN(o.importe_ofertado_documento) FILTER (WHERE ", "la mínima admite ficticias"),
    ("M14", "08_comparativos.sql", "a.n_ofertas_ganadoras = 1",
     "a.n_ofertas_ganadoras >= 1", "con dos ganadoras se duplica el comparativo"),
    ("M15", "08_comparativos.sql", "> 10 * oft.mayor_oferta",
     "> 3 * oft.mayor_oferta", "umbral del atípico distinto del dominio"),
    ("M16", "08_comparativos.sql", ">= 2 THEN oft.maxima_real - oft.minima_real",
     ">= 1 THEN oft.maxima_real - oft.minima_real", "ahorro con una sola oferta"),
    ("M17", "08_comparativos.sql", "WHERE f.fir <> 0", "WHERE f.fir = 0",
     "la última firma es una pendiente"),
    ("M18", "08_comparativos.sql", "f.fec DESC NULLS LAST", "f.fec ASC NULLS LAST",
     "la PRIMERA firma en vez de la última"),
    ("M19", "08_comparativos.sql", "CASE WHEN fi.estado_es_final THEN uf.fecha END",
     "CASE WHEN TRUE THEN uf.fecha END", "fecha de aprobación en cualquier estado"),
    ("M20", "08_comparativos.sql", "LEFT JOIN raw.auxpronat a ON",
     "JOIN raw.auxpronat a ON", "se pierden los comparativos sin actividad"),
    ("M21", "08_comparativos.sql", "bool_or(f.estfin = fc.est)",
     "bool_and(f.estfin = fc.est)", "otra definición de circuito cerrado"),
    ("M22", "08_comparativos.sql", "JOIN raw.con c ON c.ide = d.ide",
     "JOIN raw.con c ON c.ide = p.ide", "estado de la invitación, no de la oferta"),
    ("M23", "08_comparativos.sql", "count(*) FILTER (WHERE f.fir = 0) AS n_firmas_pendientes",
     "count(*) FILTER (WHERE f.fir = 1) AS n_firmas_pendientes", "pendientes = firmadas"),
    ("M24", "08_comparativos.sql", "LEFT JOIN contratado ct ON ct.contrato_id = li.contrato_id",
     "LEFT JOIN contratado ct ON ct.contrato_id = m.ide", "contratado de otro documento"),
]


def _pytest(raiz: Path) -> tuple[int, str]:
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    fallos = len(re.findall(r"^FAILED ", salida, re.MULTILINE))
    resumen = salida.strip().splitlines()[-1] if salida.strip() else ""
    return fallos, resumen


def main() -> int:
    raiz = Path(sys.argv[1]).resolve()
    base, resumen = _pytest(raiz)
    print(f"LINEA BASE: {base} fallos · {resumen}")
    if base:
        return 1
    for ident, fichero, original, mutado, rompe in MUTANTES:
        ruta = raiz / SQL / fichero
        texto = ruta.read_text(encoding="utf-8")
        assert texto.count(original) == 1, f"{ident}: el original no es único"
        linea = texto[: texto.index(original)].count("\n") + 1
        ruta.write_text(texto.replace(original, mutado), encoding="utf-8")
        try:
            fallos, resumen = _pytest(raiz)
        finally:
            ruta.write_text(texto, encoding="utf-8")
        veredicto = "MUERTO" if fallos else "SUPERVIVIENTE"
        print(f"{ident} | {fichero}:{linea} | {original!r} -> {mutado!r} | "
              f"{fallos} | {veredicto} | {rompe}")
    final, resumen = _pytest(raiz)
    print(f"LINEA BASE FINAL: {final} fallos · {resumen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
