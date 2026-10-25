-- etl_sigrid/infrastructure/postgres/sql/tesoreria/08_hipotesis_caja_obra.sql
-- ============================================================================
-- F-140 · SCHEMA tesoreria (9/9): tesoreria.hipotesis_caja_obra, EL VALOR DE
-- CADA HIPOTESIS EN CADA OBRA (R3, R5, D14-A, D18-A)
--
-- GRANO: una fila por (obra, codigo) para las obras con devengo pendiente
-- (`tesoreria.devengo_corte_obra`) y las que tienen algun valor MANUAL, y los
-- codigos del catalogo que admiten valor por obra (`admite_obra`).
--
-- EL VALOR, en el orden de `resolver_hipotesis` (`domain/proyeccion_caja.py`):
--   1. MANUAL: el de la seccion `obras` de `config/hipotesis_caja.yaml`, que
--      el paso ya cargo en `tesoreria.hipotesis_caja_manual` (nivel OBRA).
--   2. SIGRID (D18-A), solo H09, H10 y H11: el de los contratos con el cliente
--      de la obra (`tesoreria.condiciones_contrato_cliente`) cuando TODOS dan
--      valor y es el MISMO (nivel OBRA). H09, el plazo de una formula de UN
--      solo vencimiento reconocida (varios vencimientos no son un plazo); H10,
--      la retencion; H11, el plazo de retencion o, si no, el de garantia.
--   3. DEFECTO: el del catalogo (nivel DEFECTO).
--
-- NO SE APLICA: este fichero no multiplica ni suma nada (R6, test). Que hacer
-- con el valor es cosa de quien consulta, y `R-CAJA-HIPOTESIS` le obliga a
-- declararlo.
--
-- Guarda (R3): una `clave_obra` del YAML que no es una obra tumba el paso con
-- la lista, antes de vaciar nada.
--
-- Lee de: tesoreria.hipotesis_caja, tesoreria.hipotesis_caja_manual,
--         tesoreria.condiciones_contrato_cliente, tesoreria.devengo_corte_obra,
--         maestro.v_obra_fichas.
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
LEFT JOIN tesoreria.hipotesis_caja_manual m ON m.clave_obra = o.clave_obra AND m.codigo = h.codigo
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
        SELECT k.obra_id, COALESCE(k.plazo_retencion_meses, k.plazo_garantia_meses) AS valor
        FROM tesoreria.condiciones_contrato_cliente k
        WHERE k.obra_id IS NOT NULL
    ) c
    GROUP BY c.obra_id
) s ON s.obra_id = o.obra_id AND s.codigo = h.codigo
WHERE h.admite_obra;

COMMENT ON TABLE tesoreria.hipotesis_caja_obra IS
'F-140. El valor de cada hipotesis de caja (catalogo tesoreria.hipotesis_caja) en cada obra con devengo pendiente o con valor manual: MANUAL (seccion obras del YAML), si no SIGRID (H09-H11, solo si todos los contratos con el cliente de la obra dan el mismo valor), si no DEFECTO. nivel OBRA o DEFECTO. Nada se aplica: es el valor que quien consulta debe declarar (R-CAJA-HIPOTESIS). Clave: obra_id, codigo.';
