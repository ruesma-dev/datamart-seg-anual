-- etl_sigrid/infrastructure/postgres/sql/stg/10_master_versiones.sql
--
-- Materializa stg.master_versiones (F-161): una fila por versión master de los
-- ámbitos 8 (coste) y 11 (venta) con el resumen de su reparto en el tiempo.
-- Lee de stg.presupuesto, stg.plan_mensual (los dos de esta noche) y
-- raw.obrfasamb. La lee mart/01b_master_versiones.sql, que publica el catálogo.
--
-- POR QUÉ EXISTE. Hasta F-161 el catálogo de versiones se deducía de
-- `stg.plan_mensual`, que solo tiene las líneas CON reparto (`planif`). Una
-- versión entera sin `planif` —la v24 de coste de la 0698, «CIERRE
-- SEPTIEMBRE-26», 776 líneas y 2.107.662,97 €— no aparecía en ningún sitio.
-- Ahora el universo es (D5):
--
--   claves de las líneas de stg.presupuesto  ∪  claves de stg.plan_mensual
--
-- con la cabecera de raw.obrfasamb OPCIONAL (hay versiones con líneas y sin
-- cabecera). La versión 0 solo entra si tiene reparto (D6): hoy son 8 filas en
-- 4 obras que ya estaban en el catálogo; las demás v0 son el vivo de F-157.
--
-- LA PARTE TEMPORAL NO CAMBIA (D4). `tiene_reparto` = la versión tiene filas en
-- stg.plan_mensual. Solo esas rigen el mensual (02_build_fact.sql), la vigencia
-- anual (06_cp_tipologia.sql) y la Cuatrimestral de retenciones/05_fin_obra.sql.
-- Las demás solo informan.
--
-- LOS ATRIBUTOS (R4, R5). Con reparto, fechas, descripción y texto son los de
-- stg.plan_mensual, como hasta hoy (por eso el catálogo de hoy queda dentro,
-- idéntico: R11). Sin reparto, salen de la cabecera con las MISMAS expresiones
-- que la rama master de 08_plan_mensual.sql (alias `fa` y `fa_coste` incluidos,
-- para que el test las compare literalmente). Sin cabecera, NULL.
--
-- LA CABECERA DUPLICADA (D13). Si raw.obrfasamb trae dos filas de la misma
-- (obra, ámbito, versión), manda la de `ide` mayor, como en
-- descompuestos/03_lineas_master.sql. Hoy hay 0 casos (ver
-- docs/referencia/05_caso_obrfasamb_version_duplicada.md).
--
-- LA LÍNEA CON REPARTO (D7) es la que deja al menos una fila en
-- stg.plan_mensual (por `presupuesto_id`), no la que tiene `planif` escrito:
-- en la v23 de coste de la 0698 hay 751 con `planif` y solo 690 dejan meses.
-- La misma marca la publica, línea a línea, la vista stg.v_master_lineas.
--
-- reparto: NINGUNO si la versión no tiene reparto; COMPLETO si lo tiene y
-- ninguna línea con importe <> 0 se queda sin él; PARCIAL en el resto.
--
-- SE EJECUTA ENTERO (R6): ni tramos ni ventana de F-025, y fuera del sello.
-- TRUNCATE + INSERT en la misma llamada (`execute_sql_file`): o se rehace o no
-- se toca.

TRUNCATE TABLE stg.master_versiones;

WITH
-- 1) Las versiones con reparto, con los atributos que ya publica plan_mensual.
plan AS (
    SELECT DISTINCT ON (obra_id, ambito_id, version)
        obra_id,
        ambito_id,
        version,
        version_fec_creacion,
        version_fec_efectiva,
        version_descripcion,
        version_tex
    FROM stg.plan_mensual
    WHERE ambito_id IN (8, 11)
    ORDER BY obra_id, ambito_id, version,
             version_fec_efectiva DESC NULLS LAST,
             version_fec_creacion DESC NULLS LAST,
             version_descripcion, version_tex
),
-- 2) Las líneas master: versión >= 1, y la 0 solo si tiene reparto (D6). La
--    marca es la de stg.v_master_lineas (D7).
lineas AS (
    SELECT
        pp.obra_id,
        pp.ambito_id,
        pp.fase_num AS version,
        pp.importe,
        EXISTS (
            SELECT 1
            FROM stg.plan_mensual pm
            WHERE pm.presupuesto_id = pp.presupuesto_id
        ) AS con_reparto
    FROM stg.presupuesto pp
    WHERE pp.ambito_id IN (8, 11)
      AND (
            pp.fase_num >= 1 OR EXISTS (
                SELECT 1
                FROM plan p
                WHERE p.obra_id = pp.obra_id
                  AND p.ambito_id = pp.ambito_id
                  AND p.version = pp.fase_num
            )
      )
),
agregado AS (
    SELECT
        obra_id,
        ambito_id,
        version,
        COUNT(*) AS n_lineas,
        COUNT(*) FILTER (WHERE con_reparto) AS n_lineas_con_reparto,
        SUM(importe) AS importe_total,
        SUM(importe) FILTER (WHERE con_reparto) AS importe_con_reparto,
        BOOL_OR(NOT con_reparto AND importe <> 0) AS hay_sin_reparto_con_importe
    FROM lineas
    GROUP BY obra_id, ambito_id, version
),
-- 3) La cabecera, sin duplicar (D13), y el texto de coste para la venta.
fa_dedup AS (
    SELECT DISTINCT ON (obride, amb, fas)
        ide, obride, amb, fas, plafec, fec, res, tex
    FROM raw.obrfasamb
    WHERE amb IN (8, 11)
    ORDER BY obride, amb, fas, ide DESC
),
cabecera AS (
    SELECT
        fa.obride                            AS obra_id,
        fa.amb                               AS ambito_id,
        fa.fas                               AS version,
        stg.fn_sigrid_date_to_date(fa.fec)   AS fec_creacion,
        -- Las cuatro expresiones de 08_plan_mensual.sql, copiadas literal.
        stg.fn_master_fecha_efectiva(
            COALESCE(NULLIF(TRIM(fa.tex), ''), NULLIF(TRIM(fa_coste.tex), '')),
            fa.res,
            stg.fn_sigrid_date_to_date(fa.fec)
        )                                    AS fec_efectiva,
        COALESCE(
            NULLIF(TRIM(fa.res), ''),
            CASE fa.amb
                WHEN 8  THEN 'Master coste sin descripción'
                WHEN 11 THEN 'Master venta sin descripción'
                ELSE NULL
            END
        )                                    AS res_descripcion,
        COALESCE(
            NULLIF(TRIM(fa.tex), ''),
            NULLIF(TRIM(fa_coste.tex), '')
        )                                    AS tex_descripcion,
        (fa.plafec IS NOT NULL AND fa.plafec > 0) AS tiene_ancla
    FROM fa_dedup fa
    LEFT JOIN fa_dedup fa_coste
        ON fa_coste.obride = fa.obride
       AND fa_coste.fas    = fa.fas
       AND fa_coste.amb    = 8
       AND fa.amb          = 11
),
-- 4) El universo (D5): líneas ∪ reparto. La cabecera es opcional.
universo AS (
    SELECT obra_id, ambito_id, version FROM agregado
    UNION
    SELECT obra_id, ambito_id, version FROM plan
)
INSERT INTO stg.master_versiones (
    obra_id, ambito_id, version,
    version_fec_creacion, version_fec_efectiva, version_descripcion, version_tex,
    tiene_reparto, reparto,
    n_lineas, n_lineas_con_reparto,
    importe_total, importe_con_reparto, importe_sin_reparto,
    tiene_cabecera, tiene_ancla
)
SELECT
    u.obra_id,
    u.ambito_id,
    u.version,
    -- Con reparto, los de plan_mensual (R4); sin él, los de la cabecera (R5:
    -- NULL si no la hay).
    CASE WHEN p.obra_id IS NOT NULL THEN p.version_fec_creacion ELSE c.fec_creacion END AS version_fec_creacion,
    CASE WHEN p.obra_id IS NOT NULL THEN p.version_fec_efectiva ELSE c.fec_efectiva END AS version_fec_efectiva,
    CASE WHEN p.obra_id IS NOT NULL THEN p.version_descripcion ELSE c.res_descripcion END AS version_descripcion,
    CASE WHEN p.obra_id IS NOT NULL THEN p.version_tex ELSE c.tex_descripcion END AS version_tex,
    (p.obra_id IS NOT NULL) AS tiene_reparto,
    CASE
        WHEN p.obra_id IS NULL THEN 'NINGUNO'
        WHEN COALESCE(a.hay_sin_reparto_con_importe, FALSE) THEN 'PARCIAL'
        ELSE 'COMPLETO'
    END AS reparto,
    COALESCE(a.n_lineas, 0) AS n_lineas,
    COALESCE(a.n_lineas_con_reparto, 0) AS n_lineas_con_reparto,
    COALESCE(a.importe_total, 0)::NUMERIC(18,2) AS importe_total,
    COALESCE(a.importe_con_reparto, 0)::NUMERIC(18,2) AS importe_con_reparto,
    (COALESCE(a.importe_total, 0) - COALESCE(a.importe_con_reparto, 0))::NUMERIC(18,2) AS importe_sin_reparto,
    (c.obra_id IS NOT NULL) AS tiene_cabecera,
    COALESCE(c.tiene_ancla, FALSE) AS tiene_ancla
FROM universo u
LEFT JOIN agregado a
    ON a.obra_id = u.obra_id AND a.ambito_id = u.ambito_id AND a.version = u.version
LEFT JOIN plan p
    ON p.obra_id = u.obra_id AND p.ambito_id = u.ambito_id AND p.version = u.version
LEFT JOIN cabecera c
    ON c.obra_id = u.obra_id AND c.ambito_id = u.ambito_id AND c.version = u.version;
