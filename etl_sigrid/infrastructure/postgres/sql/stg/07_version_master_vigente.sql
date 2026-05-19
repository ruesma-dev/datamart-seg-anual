-- etl_sigrid/infrastructure/postgres/sql/stg/07_version_master_vigente.sql
--
-- Materializa stg.version_master_vigente leyendo raw.conext.
--
-- En Sigrid, los campos extendidos (conext) son metadatos clave-valor por concepto.
-- El cod (placeholder Python en este archivo) corresponde a "Versión Master Vigente",
-- y su valor numérico (valn) indica la versión del master que cada obra tiene activa hoy.
--
-- Esto reemplaza la lógica DAX SELECTEDVALUE(DimCamposExtValores[valn]) que hoy
-- vive en 5 medidas distintas del BI. Aquí se resuelve UNA VEZ por ejecución.
--
-- El placeholder %(cod)s se sustituye desde Python con el valor de
-- business_rules.yaml -> sigrid.campos_extendidos.cod_version_master_vigente
-- (por defecto '15'). Si Sigrid cambia el cod del campo extendido, se cambia el
-- YAML y nada más.
--
-- Si una obra tiene varias filas en conext con el mismo cod (no debería, pero por
-- seguridad), tomamos MAX(valn). Las filas sin valn se ignoran.

TRUNCATE TABLE stg.version_master_vigente;

INSERT INTO stg.version_master_vigente (obra_id, version_vigente)
SELECT
    conide                                  AS obra_id,
    MAX(valn::INTEGER)                      AS version_vigente
FROM raw.conext
WHERE cod = %(cod)s
  AND valn IS NOT NULL
  AND conide IS NOT NULL
GROUP BY conide;
