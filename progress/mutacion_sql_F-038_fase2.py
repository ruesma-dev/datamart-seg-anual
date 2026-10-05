# progress/mutacion_sql_F-038_fase2.py
"""
F-038 · Campaña de mutación MANUAL sobre el SQL de la Fase 2.

Igual que `progress/mutacion_sql_F-038.py` (Fase 1): `harness.mutacion` solo
muta Python, y la lógica de la Fase 2 vive sobre todo en SQL
(`compras.fn_porcentaje_dto` en `00_setup.sql` y
`compras/09_comparativos_detalle.sql`). Cada mutante es una sustitución de
texto EXACTA que cambia el comportamiento del SQL; se aplica en un worktree
desechable, se ejecuta el subconjunto de tests sin `-x` y se cuentan los
FAILED.

Uso (desde la raíz del repositorio):
    python progress/mutacion_sql_F-038_fase2.py <ruta_worktree_desechable>

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
    "tests/test_f006_fichas.py",
]

#: (id, fichero, texto ORIGINAL, texto MUTADO, qué rompe).
MUTANTES = [
    ("M25", "00_setup.sql", "WHEN t ~ '^-?[0-9]+(,[0-9]+)?%$' THEN",
     "WHEN t ~ '^-?[0-9]+(,[0-9]+)?%' THEN", "el patrón del dto pierde el ancla final"),
    ("M26", "00_setup.sql", "replace(replace(t, '%', ''), ',', '.')::NUMERIC",
     "replace(t, '%', '')::NUMERIC", "la coma decimal llega al cast"),
    ("M27", "09_comparativos_detalle.sql", "FROM raw.comlin l\nLEFT JOIN raw.dncpro n",
     "FROM raw.comlin l\nJOIN raw.dncpro n", "se pierden las líneas sin necesidad"),
    ("M28", "09_comparativos_detalle.sql", "NULLIF(n.paride, 0)", "NULLIF(n.ide, 0)",
     "la partida es la propia necesidad"),
    ("M29", "09_comparativos_detalle.sql", "WHERE lp.comlinide > 0",
     "WHERE lp.comlinide >= 0", "líneas de oferta sin línea de comparativo"),
    ("M30", "09_comparativos_detalle.sql", "WHERE d.es_primera_abc\nGROUP BY d.obra_id",
     "WHERE d.es_vigente\nGROUP BY d.obra_id", "la ABC de la obra es la vigente"),
    ("M31", "09_comparativos_detalle.sql",
     "WHERE lo.familia_ficticia = 'OBJETIVO' AND lo.porcentaje_descuento IS NOT NULL",
     "WHERE lo.es_ficticia AND lo.porcentaje_descuento IS NOT NULL",
     "cualquier ficticia busca base"),
    ("M32", "09_comparativos_detalle.sql", "<= 0.011 + 0.002 * abs(ob.precio)",
     "<= 0.011 + 0.02 * abs(ob.precio)", "tolerancia relativa diez veces mayor"),
    ("M33", "09_comparativos_detalle.sql", "AND d.fase_num <= ob.fase_abc)",
     "AND d.fase_num >= 0)", "entran las versiones posteriores a la ABC"),
    ("M34", "09_comparativos_detalle.sql", "'MASTER_ESTUDIO', 'ESTUDIO', 'MASTER_PRE_ABC')",
     "'MASTER_ESTUDIO', 'ESTUDIO', 'MASTER_PRE_ABC', 'MASTER_PLANIF_JO')",
     "la planificación posterior entra como anterior"),
    ("M35", "09_comparativos_detalle.sql",
     "OR (ob.fase_abc IS NULL AND d.origen IN ('MASTER_ESTUDIO', 'ESTUDIO'))",
     "OR (ob.fase_abc IS NULL)", "sin ABC entra cualquier versión"),
    ("M36", "09_comparativos_detalle.sql", "c.por_dncpro DESC, c.casa DESC, c.orden",
     "c.casa DESC, c.por_dncpro DESC, c.orden", "el precio manda sobre el dncpro_id"),
    ("M37", "09_comparativos_detalle.sql", "e.casa DESC, e.fase_num DESC, e.origen",
     "e.casa DESC, e.fase_num ASC, e.origen", "la anterior MÁS ANTIGUA antes que la ABC"),
    ("M38", "09_comparativos_detalle.sql",
     "WHERE e.casa OR e.es_primera_abc OR ob.fase_abc IS NULL", "WHERE TRUE",
     "sin casa, cualquier anterior en vez de la de la regla"),
    ("M39", "09_comparativos_detalle.sql",
     "WHEN cd.linea_oferta_id IS NOT NULL THEN FALSE END AS casa_base",
     "ELSE FALSE END AS casa_base", "sin descompuesto sale falso y no NULL"),
    ("M40", "09_comparativos_detalle.sql", "COALESCE(d.dncpro_id = ob.dncpro_id, FALSE)",
     "COALESCE(d.producto_id = ob.dncpro_id, FALSE)", "el elemento por otra llave"),
    ("M41", "09_comparativos_detalle.sql",
     "ORDER BY o.fecha_oferta DESC NULLS LAST, o.oferta_id DESC",
     "ORDER BY o.fecha_oferta ASC NULLS LAST, o.oferta_id DESC",
     "la OBJETIVO más antigua"),
    ("M42", "09_comparativos_detalle.sql", "CASE WHEN cp.n_porcentajes = 1 THEN",
     "CASE WHEN cp.n_porcentajes >= 1 THEN", "con varios % se elige uno"),
    ("M43", "09_comparativos_detalle.sql", "FILTER (WHERE l.casa_base)",
     "FILTER (WHERE l.casa_base IS NOT NULL)", "lo que no casa cuenta como casado"),
    ("M44", "09_comparativos_detalle.sql", "WHERE ob.orden = 1;", "WHERE ob.orden >= 1;",
     "varias filas por comparativo"),
    ("M45", "09_comparativos_detalle.sql", "COALESCE(f.fir = 0, FALSE)",
     "COALESCE(f.fir = 1, FALSE)", "pendiente = firmada"),
    ("M46", "09_comparativos_detalle.sql", "JOIN raw.com m ON m.ide = f.conide;",
     "LEFT JOIN raw.com m ON m.ide = f.conide;", "entran firmas de facturas y obras"),
    ("M47", "09_comparativos_detalle.sql", "CREATE TEMP TABLE _f038_obra_abc ON COMMIT DROP AS",
     "CREATE TEMP TABLE _f038_obra_abc AS", "la temporal sobrevive a la transacción"),
    ("M48", "09_comparativos_detalle.sql",
     "CASE WHEN el.es_primera_abc THEN 'ABC' ELSE el.origen END || ' v' || el.fase_num",
     "el.origen || ' v' || el.fase_num", "la ABC sale como MASTER_PLANIF_JO"),
    ("M49", "09_comparativos_detalle.sql",
     "FROM compras.comparativo_ofertas o\n    WHERE o.familia_ficticia = 'OBJETIVO'",
     "FROM compras.comparativo_ofertas o\n    WHERE o.es_ficticia",
     "el objetivo puede ser cualquier ficticia"),
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
        ruta.write_text(texto.replace(original, mutado), encoding="utf-8", newline="\n")
        try:
            fallos, resumen = _pytest(raiz)
        finally:
            ruta.write_text(texto, encoding="utf-8", newline="\n")
        veredicto = "MUERTO" if fallos else "SUPERVIVIENTE"
        print(f"{ident} | {fichero}:{linea} | {original!r} -> {mutado!r} | "
              f"{fallos} | {veredicto} | {rompe}", flush=True)
    final, resumen = _pytest(raiz)
    print(f"LINEA BASE FINAL: {final} fallos · {resumen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
