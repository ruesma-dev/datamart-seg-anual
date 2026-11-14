# etl_sigrid/infrastructure/postgres/master_versiones_sql.py
"""
F-161 · La comprobación de que el catálogo completo CONTIENE, idéntico, el de
antes (R11). **Solo construye texto**: este módulo no abre ninguna conexión.

Hasta F-161 el catálogo de versiones master se deducía de `stg.plan_mensual`
con un `SELECT DISTINCT` (sección 1 de `mart/06_cp_tipologia.sql`, commit
`491fbf1`). F-161 lo construye en `mart/01b_master_versiones.sql` desde
`stg.master_versiones`, con TODAS las versiones con líneas. Las que rigen el
mensual son las que tienen reparto, y esas tienen que ser exactamente las de
antes, columna a columna, o la parte temporal cambiaría (D4).

`CATALOGO_ANTERIOR` es esa sección 1 **congelada**: recalcula desde
`stg.plan_mensual` sin tocar ningún objeto de F-161. `sql_comparacion_catalogo()`
hace el `EXCEPT` en los dos sentidos contra las filas del catálogo nuevo con
`tiene_reparto` y fecha efectiva. Cero filas = idénticos.

Lo usan `tests/test_f161_sandbox.py` y el paso MANUAL 4 de `design.md` §8, que
lo lanza en solo lectura (`filas_solo_lectura` con `_bootstrap_done = True`).
**Es caro**: barre los ámbitos master de `stg.plan_mensual` (8,6 GB de heap en
Azure); se lanza fuera de la nocturna y una sola vez.
"""

from __future__ import annotations

#: Las ocho columnas del catálogo de antes, en su orden.
COLUMNAS_CATALOGO = (
    "obra_id",
    "ambito_id",
    "version",
    "version_fec_creacion",
    "version_fec_efectiva",
    "version_descripcion",
    "version_tex",
    "tipo_master",
)

#: La sección 1 de `mart/06_cp_tipologia.sql` en `491fbf1`, copiada literal.
#: Congelada: si mañana cambia la cascada del tipo, esta copia NO cambia.
CATALOGO_ANTERIOR = """
SELECT DISTINCT
    obra_id,
    ambito_id,
    version,
    version_fec_creacion,
    version_fec_efectiva,
    version_descripcion,
    version_tex,
    CASE
        WHEN version_tex IS NULL OR length(trim(version_tex)) = 0
            THEN 'Sin clasificar'
        WHEN UPPER(version_tex) LIKE '%ABC%'
            THEN 'ABC'
        WHEN UPPER(version_tex) LIKE '%INICIAL%'
         AND UPPER(version_tex) LIKE '%VALORADA%'
            THEN 'Planif Inicial'
        WHEN UPPER(version_tex) LIKE '%CUATRIM%'
          OR UPPER(version_tex) LIKE '%VALORADA%'
            THEN 'Cuatrimestral'
        WHEN UPPER(version_tex) LIKE '%CIERRE%'
            THEN 'Cierre mensual'
        ELSE 'Sin clasificar'
    END AS tipo_master
FROM stg.plan_mensual
WHERE ambito_id IN (8, 11)
  AND version_fec_efectiva IS NOT NULL
"""


def sql_comparacion_catalogo() -> str:
    """Las filas que están en un catálogo y no en el otro, con su lado.

    Cero filas es el resultado esperado (R11). Las dos mitades llevan las
    mismas ocho columnas en el mismo orden, así que el `EXCEPT` compara fila a
    fila, también los NULL.
    """
    columnas = ", ".join(COLUMNAS_CATALOGO)
    return f"""
WITH anterior AS ({CATALOGO_ANTERIOR}),
nuevo AS (
    SELECT {columnas}
    FROM mart.master_versiones_tipadas
    WHERE tiene_reparto AND version_fec_efectiva IS NOT NULL
)
SELECT 'solo_anterior' AS lado, x.*
FROM (SELECT * FROM anterior EXCEPT SELECT * FROM nuevo) x
UNION ALL
SELECT 'solo_nuevo' AS lado, y.*
FROM (SELECT * FROM nuevo EXCEPT SELECT * FROM anterior) y
ORDER BY 2, 3, 4, 1
"""
