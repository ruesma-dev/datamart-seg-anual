-- etl_sigrid/infrastructure/postgres/sql/compras/04_formas_pago.sql
--
-- DIMENSIÓN de formas de pago (F-073), desde `raw.auxpag` + `raw.auxefp`.
--
-- La forma de pago no existía en ninguna capa procesada: vivía solo en `raw`,
-- que el MCP no lee, así que para Negocio no existía. La necesitan F-067 (el
-- contrato) y F-037 (la cartera) por separado, y por eso se publica una vez
-- aquí como catálogo en lugar de dos veces cableada.
--
-- GRANO: una fila por fila de `raw.auxpag`. 69 el 2026-09-10, resueltas contra
-- los 10 medios de `raw.auxefp` por `auxpag.efeide`. El `LEFT JOIN` conserva
-- las 69 aunque alguna se quede sin medio; aquí no se filtra nada, ni las
-- formas dadas de baja.
--
-- EL NOMBRE DEL MEDIO ES `auxefp.res`, MEDIDO (T1 de F-073, vuelto a medir el
-- 2026-09-11 en F-081): `est` viene vacío en 5 de las 10 filas y a NULL en las
-- otras 5, mientras que `res` trae CHEQUE, EFECTIVO, PAGARÉ, TRANSFERENCIA,
-- LETRA, CONFIRMING / PAGARÉ… Publicar `est` habría dado una columna vacía con
-- un nombre convincente.
-- `config/tables_sigrid.yaml` lo declaraba en `est` y era falso; **F-081 lo
-- corrigió**, y `tests/test_f081_yaml_ingesta.py` impide que vuelva.
--
-- `plazo_formula` VA TAL CUAL Y NO ES UN NÚMERO DE DIAS. `auxpag.formul` es una
-- fórmula de Sigrid: `30 450R` es un valor real del catálogo. Interpretarlo
-- aquí sería inventar precisión; quien necesite un plazo numérico lo decide en
-- su feature, con el criterio escrito (DA-5).
--
-- Consumo típico:
--   SELECT codigo, nombre, medio_pago, plazo_formula FROM compras.formas_pago;

CREATE OR REPLACE VIEW compras.formas_pago AS
SELECT
    ap.ide                   AS forma_pago_id,
    ap.cod                   AS codigo,
    ap.res                   AS nombre,
    ap.formul                AS plazo_formula,
    NULLIF(ap.efeide, 0)     AS medio_pago_id,
    ef.res                   AS medio_pago,
    ef.cla                   AS clase_medio
FROM      raw.auxpag ap
LEFT JOIN raw.auxefp ef ON ef.ide = NULLIF(ap.efeide, 0);

COMMENT ON VIEW compras.formas_pago IS
'Catalogo de formas de pago (69 filas) con su medio resuelto desde auxefp (10 medios: CHEQUE, EFECTIVO, PAGARE, TRANSFERENCIA...). TRAMPA: plazo_formula es la formula de Sigrid tal cual y NO es un numero de dias -"30 450R" es un valor real del catalogo-, asi que no se puede sumar ni comparar como cantidad.';
