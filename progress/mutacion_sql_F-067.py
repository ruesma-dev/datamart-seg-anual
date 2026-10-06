# progress/mutacion_sql_F-067.py
"""
F-067 · Campaña de mutación MANUAL sobre el SQL de la feature.

`harness.mutacion` solo muta Python, y la lógica de F-067 vive sobre todo en
SQL: la foto diaria (`compras/11_historial_estados.sql`), la fecha de Delphi
(`compras.fn_sigrid_tiempo` en `00_setup.sql`), las columnas nuevas de
`compras/01_documentos.sql`, `compras/10_necesidades.sql` y las dos vistas de
`descompuestos/06_views.sql`. Mismo método que `progress/mutacion_sql_F-038_fase2.py`:
cada mutante es una sustitución de texto EXACTA que cambia el comportamiento
del SQL; se aplica en un worktree desechable, se ejecuta el subconjunto de tests
sin `-x` y se cuentan los FAILED.

FUERA DEL SUBCONJUNTO A PROPÓSITO: `tests/test_f073_sql.py`, cuyo hash de
`01_documentos.sql` mataría cualquier mutante de ese fichero sin decir nada de
si los tests de F-067 lo ven. Se mide lo que cazan los tests de la feature.

Uso (desde la raíz del repositorio):
    python progress/mutacion_sql_F-067.py <ruta_worktree_desechable>

El worktree se crea con `git worktree add --detach <ruta> HEAD` y se borra
después con `git worktree remove --force <ruta>`. Un solo worker, en serie.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SQL = "etl_sigrid/infrastructure/postgres/sql/"
TESTS = [
    "tests/test_f067_sql.py",
    "tests/test_f067_dominio.py",
    "tests/test_f067_diccionario.py",
    "tests/test_f084_sql.py",
    "tests/test_f083_sql.py",
    "tests/test_f047_steps.py",
    "tests/test_f097_descompuestos.py",
    "tests/test_f120_factor.py",
    "tests/test_f123_origenes.py",
    "tests/test_f006_fichas.py",
]

SETUP = "compras/00_setup.sql"
DOCS = "compras/01_documentos.sql"
NEC = "compras/10_necesidades.sql"
HIST = "compras/11_historial_estados.sql"
VIS = "descompuestos/06_views.sql"

#: (id, fichero, texto ORIGINAL, texto MUTADO, qué rompe).
MUTANTES = [
    # --- la fecha de Delphi ---------------------------------------------------
    ("M01", SETUP, "TIMESTAMP '1899-12-30' + v", "TIMESTAMP '1900-01-01' + v",
     "la época de SQL Server: dos días de más"),
    ("M02", SETUP, "CASE WHEN v > 0 THEN TIMESTAMP", "CASE WHEN v >= 0 THEN TIMESTAMP",
     "el 0 de Sigrid sale como 1899-12-30"),
    ("M03", SETUP, "+ v * INTERVAL '1 day' END", "+ floor(v) * INTERVAL '1 day' END",
     "se pierde la hora"),
    # --- la foto: guardas -----------------------------------------------------
    ("M04", HIST, "IF v_obs IS NULL OR v_obs <= v_ult THEN",
     "IF v_obs IS NULL OR v_obs < v_ult THEN", "relanzar sin ingesta nueva escribe"),
    ("M05", HIST, "v_actual < 0.98 * v_abiertos", "v_actual < 0.9 * v_abiertos",
     "el umbral de presencia baja al 90 %"),
    ("M06", HIST, "RAISE EXCEPTION 'F-067: raw.con trae", "RAISE NOTICE 'F-067: raw.con trae",
     "la ingesta a medias ya no para el build"),
    ("M07", HIST, "SELECT count(*) INTO v_actual FROM raw.con c WHERE c.tip IN (44, 15);",
     "SELECT count(*) INTO v_actual FROM raw.con c;", "la guarda cuenta todos los tipos"),
    # --- la foto: cerrar y abrir ----------------------------------------------
    ("M08", HIST, "AND  c.est IS DISTINCT FROM h.estado_id;", "AND  c.est <> h.estado_id;",
     "un estado que sale de NULL no es cambio"),
    ("M09", HIST, "AND  c.tip = h.tipo_documento_codigo\n      AND  c.est",
     "AND  c.est", "el cambio no mira el tipo"),
    ("M10", HIST, "WHERE  c.ide = h.documento_id AND c.tip = h.tipo_documento_codigo\n",
     "WHERE  c.ide = h.documento_id\n", "el desaparecido no mira el tipo"),
    ("M11", HIST, "SET    hasta = v_obs, motivo_cierre = 'DESAPARECIDO'",
     "SET    hasta = v_obs, motivo_cierre = 'CAMBIO'", "el desaparecido se cierra como cambio"),
    ("M12", HIST, "v_obs, NULL, v_ult, (v_ult IS NULL), NULL",
     "v_obs, NULL, v_ult, TRUE, NULL", "todo tramo nuevo es de línea base"),
    ("M13", HIST, "v_obs, NULL, v_ult, (v_ult IS NULL), NULL",
     "v_obs, NULL, NULL, (v_ult IS NULL), NULL", "se pierde la ventana del cambio"),
    ("M14", HIST, "WHERE  c.tip IN (44, 15)\n      AND  NOT EXISTS",
     "WHERE  c.tip IN (44, 15, 46)\n      AND  NOT EXISTS", "entran los comparativos"),
    ("M15", HIST, "WHERE  h.documento_id = c.ide AND h.hasta IS NULL\n",
     "WHERE  h.documento_id = c.ide\n", "quien tuvo un tramo nunca reabre"),
    ("M16", HIST, "v_insertados - v_cambios, v_desaparecid", "v_insertados, v_desaparecid",
     "los cambios cuentan como altas"),
    # --- la foto: que no se borre ---------------------------------------------
    ("M17", HIST, "CREATE TABLE IF NOT EXISTS compras.historial_estados (",
     "DROP TABLE IF EXISTS compras.historial_estados;\n"
     "CREATE TABLE compras.historial_estados (", "la historia se reconstruye cada noche"),
    ("M18", HIST, "CREATE UNIQUE INDEX IF NOT EXISTS ux_hist_est_abierto",
     "CREATE INDEX IF NOT EXISTS ux_hist_est_abierto", "dos tramos abiertos posibles"),
    # --- la vista -------------------------------------------------------------
    ("M19", HIST, "est ON TRUE\nWHERE h.hasta IS NULL;", "est ON TRUE;",
     "la vista enseña tramos cerrados"),
    ("M20", HIST, "((now() AT TIME ZONE 'Europe/Madrid')::date", "((now())::date",
     "los días con la fecha UTC"),
    ("M21", HIST, "h.es_linea_base                                    AS antiguedad_es_minima",
     "NOT h.es_linea_base                                AS antiguedad_es_minima",
     "el mínimo al revés"),
    ("M22", HIST, "WHEN 44 THEN 'CONTRATO' WHEN 15 THEN 'FACTURA'",
     "WHEN 15 THEN 'CONTRATO' WHEN 44 THEN 'FACTURA'", "tipos cruzados"),
    ("M23", HIST, "compras.fn_estado_documento(h.tipo_documento_codigo, h.estado_id)",
     "compras.fn_estado_documento(44, h.estado_id)", "la factura se traduce como contrato"),
    # --- el contrato ----------------------------------------------------------
    ("M24", DOCS, "AND x.cod LIKE 'RET%'", "AND x.cod LIKE 'RE%'", "entran otros conceptos"),
    ("M25", DOCS, "ORDER  BY r.pos, r.ide", "ORDER  BY r.ide", "con dos, gana la de menor ide"),
    ("M26", DOCS, "    LIMIT  1\n) ret ON TRUE;", ") ret ON TRUE;", "un contrato con dos se duplica"),
    ("M27", DOCS, "ROUND((r.valpor * 100)::NUMERIC, 4)", "ROUND((r.valpor)::NUMERIC, 4)",
     "porcentaje en tanto por uno"),
    ("M28", DOCS, "LEFT JOIN raw.auxpag pag  ON", "JOIN raw.auxpag pag  ON",
     "se pierden los contratos sin forma de pago"),
    ("M29", DOCS, "compras.fn_sigrid_tiempo(con.tiemod)", "compras.fn_sigrid_date(con.fec)",
     "la última modificación es la fecha de alta"),
    ("M30", DOCS, "NULLIF(c.pagide, 0)                     AS forma_pago_id",
     "c.pagide                                AS forma_pago_id", "el 0 de Sigrid no es NULL"),
    # --- las líneas (cada bloque, por su línea anterior única) ----------------
    ("M31", DOCS, "AS importe_pendiente_facturar,\n    -- F-067 (D3): el CÓDIGO 2 y la "
     "NECESIDAD de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de "
     "Sigrid son NULL.\n    NULLIF(btrim(l.cod2), '')",
     "AS importe_pendiente_facturar,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de "
     "compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son "
     "NULL.\n    l.cod2                   ", "el código 2 vacío no es NULL (albarán)"),
    ("M32", DOCS, "AS contrato_id_directo,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD "
     "de compra, AL FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son "
     "NULL.\n    NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código "
     "2»\n    NULLIF(l.dncide, 0)",
     "AS contrato_id_directo,\n    -- F-067 (D3): el CÓDIGO 2 y la NECESIDAD de compra, AL "
     "FINAL. Ver la\n    -- cabecera del fichero. Vacío y 0 de Sigrid son NULL.\n    "
     "NULLIF(btrim(l.cod2), '')               AS codigo_alternativo,  -- «código 2»\n    "
     "NULLIF(l.dncproide, 0)", "la necesidad de la factura es su línea"),
    ("M33", DOCS, "AS necesidad_id,        -- dnc: el DPC\n    NULLIF(l.dncproide, 0)"
     "                  AS necesidad_linea_id   -- dncpro\nFROM raw.ctrpro l",
     "AS necesidad_id,        -- dnc: el DPC\n    NULLIF(l.dncide, 0)"
     "                     AS necesidad_linea_id   -- dncpro\nFROM raw.ctrpro l",
     "la línea de necesidad del contrato es el documento"),
    ("M34", DOCS, "compras.albaran_lineas (necesidad_linea_id);",
     "compras.albaran_lineas (necesidad_id);", "el índice por la columna equivocada"),
    # --- las necesidades ------------------------------------------------------
    ("M35", NEC, "COALESCE(o.dncide = d.ide, FALSE)", "COALESCE(o.dncide = d.obride, FALSE)",
     "la de la obra comparada con la obra"),
    ("M36", NEC, ") nl ON nl.dncide = d.ide;", ") nl ON nl.dncide = d.obride;",
     "las líneas de otro documento"),
    ("M37", NEC, "JOIN raw.con c            ON c.ide = d.ide",
     "JOIN raw.con c            ON c.ide = d.obride", "el nombre de la obra y no del documento"),
    ("M38", NEC, "COALESCE(nl.n, 0)", "nl.n", "sin líneas sale NULL y no 0"),
    # --- descompuestos --------------------------------------------------------
    ("M39", VIS, "n.ide = lineas.dncpro_id) AS necesidad_id\n"
     "FROM descompuestos.lineas WHERE origen = 'PLANIF_JO';",
     "n.ide = lineas.producto_id) AS necesidad_id\n"
     "FROM descompuestos.lineas WHERE origen = 'PLANIF_JO';", "la necesidad por otra llave"),
    ("M40", VIS, "(SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = "
     "lineas.dncpro_id) AS necesidad_id\nFROM descompuestos.lineas WHERE origen = "
     "'MASTER_PLANIF_JO';",
     "(SELECT NULLIF(n.ide, 0) FROM raw.dncpro n WHERE n.ide = lineas.dncpro_id) AS "
     "necesidad_id\nFROM descompuestos.lineas WHERE origen = 'MASTER_PLANIF_JO';",
     "el documento es la propia línea (master)"),
]


def _pytest(raiz: Path) -> tuple[int, str]:
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=no", "-p", "no:cacheprovider"],
        cwd=raiz, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    fallos = len(re.findall(r"^FAILED ", salida, re.MULTILINE))
    errores = len(re.findall(r"^ERROR ", salida, re.MULTILINE))
    resumen = salida.strip().splitlines()[-1] if salida.strip() else ""
    return fallos + errores, resumen


def main() -> int:
    raiz = Path(sys.argv[1]).resolve()
    base, resumen = _pytest(raiz)
    print(f"LINEA BASE: {base} fallos · {resumen}", flush=True)
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
    print(f"LINEA BASE FINAL: {final} fallos · {resumen}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
