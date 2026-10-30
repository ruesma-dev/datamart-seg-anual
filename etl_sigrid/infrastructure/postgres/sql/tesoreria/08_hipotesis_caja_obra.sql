-- etl_sigrid/infrastructure/postgres/sql/tesoreria/08_hipotesis_caja_obra.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (9/9): tesoreria.hipotesis_caja_obra, EL VALOR DE
-- CADA HIPOTESIS EN CADA OBRA (R3, R5, D14-A, D18-A)
--
-- GRANO: una fila por (obra, codigo) para las obras con devengo pendiente
-- (`tesoreria.devengo_corte_obra`) y las que tienen algun valor MANUAL, y TODOS
-- los codigos del catalogo (las 29 desde F-150): `R-CAJA-HIPOTESIS` manda declararlas todas
-- desde esta tabla (P1-a del review de F-140). La que no admite valor por obra
-- (`admite_obra` falso, hoy H17) sale siempre con su valor por DEFECTO: ni el
-- YAML ni Sigrid le dan valor de obra (los dos LEFT JOIN lo exigen).
--
-- EL VALOR, en el orden de `resolver_hipotesis` (`domain/proyeccion_caja.py`):
--   1. MANUAL: el de la seccion `obras` de `config/hipotesis_caja.yaml`, que
--      el paso ya cargo en `tesoreria.hipotesis_caja_manual` (nivel OBRA).
--   2. SIGRID (D18-A), solo H09, H10 y H11: el de los contratos con el cliente
--      de la obra (`tesoreria.condiciones_contrato_cliente`) cuando TODOS dan
--      valor y es el MISMO (nivel OBRA). H09, el plazo de una formula de UN
--      solo vencimiento reconocida (varios vencimientos no son un plazo); H10,
--      la retencion; H11, el plazo de retencion o, si no, el de garantia.
--      F-150 (N2): H12, el tipo de IVA de la FICHA de la obra (`raw.obr.ivaide`
--      -> `raw.iva`, x 100), una fila por obra (no hay contratos que casar).
--      Ese IVA solo cubre las bases `sin_iva_contrato` del devengo: el del
--      contrato ya va en `devengo_pendiente_obra_mes.importe_iva_contrato`.
--      F-150 (N15): H13, el IVA efectivo de las compras de la obra: 100 x
--      cuota entre base de sus lineas de factura de compra (`raw.dcfpro`, con la
--      fecha de la factura en `raw.con`) de los 12 meses hasta el build, si la
--      base llega a `UMBRAL_BASE_H13` (0,5 M EUR); si no, DEFECTO. Es la medida
--      de un porcentaje, como el x 100 de H12, no aplicar una hipotesis. La
--      marca ISP de Sigrid es falsa: se mide la cuota.
--   3. DEFECTO: el del catalogo (nivel DEFECTO).
--
-- NO SE APLICA: este fichero no multiplica ni suma nada (R6, test), salvo
-- pasar el IVA de la ficha de fraccion (0.21) a porcentaje (21), que es la
-- unidad del catalogo y no aplica ninguna hipotesis. Que hacer
-- con el valor es cosa de quien consulta, y `R-CAJA-HIPOTESIS` le obliga a
-- declararlo.
--
-- Guarda (R3): una `clave_obra` del YAML que no es una obra tumba el paso con
-- la lista, antes de vaciar nada.
--
-- Lee de: tesoreria.hipotesis_caja, tesoreria.hipotesis_caja_manual,
--         tesoreria.condiciones_contrato_cliente, tesoreria.devengo_corte_obra,
--         maestro.v_obra_fichas, raw.obr y raw.iva (H12, F-150),
--         raw.dcfpro y raw.con (H13, F-150 N15).
-- Escribe en: tesoreria.hipotesis_caja_obra.
-- ============================================================================

DO $$
DECLARE
    desconocidas TEXT;
BEGIN
    SELECT string_agg(DISTINCT m.clave_obra, ', ' ORDER BY m.clave_obra)
      INTO desconocidas
      FROM tesoreria.hipotesis_caja_manual m
     WHERE NOT EXISTS (SELECT 1 FROM maestro.v_obra_fichas fo WHERE fo.clave_obra = m.clave_obra);
    IF desconocidas IS NOT NULL THEN
        RAISE EXCEPTION 'hipotesis_caja_obra: clave_obra del YAML que no es ninguna obra: %', desconocidas;
    END IF;
END $$;

TRUNCATE tesoreria.hipotesis_caja_obra;

INSERT INTO tesoreria.hipotesis_caja_obra (
    obra_id, empresa_id, clave_obra, codigo, valor, nivel, fuente, motivo
)
SELECT
    o.obra_id                                                AS obra_id,
    o.empresa_id                                             AS empresa_id,
    o.clave_obra                                             AS clave_obra,
    h.codigo                                                 AS codigo,
    CASE WHEN m.valor IS NOT NULL THEN m.valor WHEN s.valor IS NOT NULL THEN s.valor ELSE h.valor_defecto END AS valor,
    CASE WHEN m.valor IS NOT NULL THEN 'OBRA' WHEN s.valor IS NOT NULL THEN 'OBRA' ELSE 'DEFECTO' END AS nivel,
    CASE WHEN m.valor IS NOT NULL THEN 'MANUAL' WHEN s.valor IS NOT NULL THEN 'SIGRID' ELSE 'DEFECTO' END AS fuente,
    CASE WHEN m.valor IS NOT NULL THEN m.motivo WHEN s.valor IS NOT NULL THEN s.motivo END AS motivo
FROM (
    SELECT fo.obra_id, fo.empresa_id, fo.clave_obra
    FROM maestro.v_obra_fichas fo
    WHERE fo.obra_id IN (SELECT c.obra_id FROM tesoreria.devengo_corte_obra c)
       OR fo.clave_obra IN (SELECT x.clave_obra FROM tesoreria.hipotesis_caja_manual x)
) o
CROSS JOIN tesoreria.hipotesis_caja h
LEFT JOIN tesoreria.hipotesis_caja_manual m
       ON m.clave_obra = o.clave_obra AND m.codigo = h.codigo AND h.admite_obra
LEFT JOIN (
    -- D18-A: un valor por obra solo si todos sus contratos dan el mismo.
    SELECT c.obra_id, 'H09'::VARCHAR(3) AS codigo,
           CASE WHEN count(*) = count(c.valor) AND count(DISTINCT c.valor) = 1 THEN to_jsonb(min(c.valor)) END AS valor,
           'Unico en los contratos con el cliente (plazo de la forma de cobro)' AS motivo
    FROM (
        SELECT k.obra_id,
               CASE WHEN k.formula_reconocida AND k.num_vencimientos = 1 THEN k.dias_vencimientos[1] END AS valor
        FROM tesoreria.condiciones_contrato_cliente k
        WHERE k.obra_id IS NOT NULL
    ) c
    GROUP BY c.obra_id
    UNION ALL
    SELECT c.obra_id, 'H10'::VARCHAR(3) AS codigo,
           CASE WHEN count(*) = count(c.valor) AND count(DISTINCT c.valor) = 1 THEN to_jsonb(min(c.valor)) END AS valor,
           'Unico en los contratos con el cliente (retencion)' AS motivo
    FROM (
        SELECT k.obra_id, k.retencion_porcentaje AS valor
        FROM tesoreria.condiciones_contrato_cliente k
        WHERE k.obra_id IS NOT NULL
    ) c
    GROUP BY c.obra_id
    UNION ALL
    SELECT c.obra_id, 'H11'::VARCHAR(3) AS codigo,
           CASE WHEN count(*) = count(c.valor) AND count(DISTINCT c.valor) = 1 THEN to_jsonb(min(c.valor)) END AS valor,
           'Unico en los contratos con el cliente (plazo de retencion o de garantia)' AS motivo
    FROM (
        -- La unidad de H11 es MESES ENTEROS: el plazo sale como entero, y uno
        -- con decimales no es un valor (cuenta como contrato sin valor).
        SELECT x.obra_id,
               CASE WHEN x.meses = trunc(x.meses) THEN x.meses::INTEGER END AS valor
        FROM (
            SELECT k.obra_id, COALESCE(k.plazo_retencion_meses, k.plazo_garantia_meses) AS meses
            FROM tesoreria.condiciones_contrato_cliente k
            WHERE k.obra_id IS NOT NULL
        ) x
    ) c
    GROUP BY c.obra_id
    UNION ALL
    -- F-150 (N2): H12 desde la ficha de la obra; una obra, un tipo de IVA.
    SELECT ob.ide AS obra_id, 'H12'::VARCHAR(3) AS codigo,
           to_jsonb(ROUND((i.iva * 100)::NUMERIC, 4)) AS valor,
           'Ficha de la obra (tipo de IVA)' AS motivo
    FROM raw.obr ob JOIN raw.iva i ON i.ide = NULLIF(ob.ivaide, 0)
    UNION ALL
    -- F-150 (N15): H13, cuota entre base de las compras de la obra en 12 meses.
    SELECT x.obra_id, 'H13'::VARCHAR(3) AS codigo,
           CASE WHEN x.base >= 500000 THEN to_jsonb(ROUND(100 * x.cuota / x.base, 2)) END AS valor,
           'Compras de la obra en 12 meses (cuota de IVA entre base)' AS motivo
    FROM (
        SELECT NULLIF(l.obride, 0) AS obra_id,
               SUM(COALESCE(l.tot, 0)::NUMERIC(18, 2)) AS base,
               SUM(COALESCE(l.ivacuo, 0)::NUMERIC(18, 2)) AS cuota
        FROM raw.dcfpro l JOIN raw.con c ON c.ide = l.docide
        WHERE abs(l.tot) < 1e8
          AND tesoreria.fn_fecha(c.fec) <= CURRENT_DATE
          AND date_part('year', age(CURRENT_DATE, tesoreria.fn_fecha(c.fec))) = 0
        GROUP BY NULLIF(l.obride, 0)
    ) x
    WHERE x.obra_id IS NOT NULL
) s ON s.obra_id = o.obra_id AND s.codigo = h.codigo AND h.admite_obra;

COMMENT ON TABLE tesoreria.hipotesis_caja_obra IS
'F-140, F-150. El valor de las 29 hipotesis de caja (catalogo tesoreria.hipotesis_caja; la que no admite valor por obra, siempre DEFECTO) en cada obra con devengo pendiente o con valor manual: MANUAL (seccion obras del YAML), si no SIGRID (H09-H11, solo si todos los contratos con el cliente de la obra dan el mismo valor; H12, el tipo de IVA de la ficha de la obra, que solo cubre las bases sin IVA del contrato; H13, cuota / base de las compras de la obra en 12 meses si la base llega a 0,5 M EUR), si no DEFECTO. nivel OBRA o DEFECTO. Nada se aplica: es el valor que quien consulta debe declarar (R-CAJA-HIPOTESIS). Clave: obra_id, codigo.';
