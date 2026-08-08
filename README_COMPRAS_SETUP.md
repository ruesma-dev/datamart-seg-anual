# Compras — puesta en marcha SIN tocar main.py ni el YAML

Al no tener yo tus versiones reales de `main.py` y `tables_sigrid.yaml`, este
ZIP resuelve el problema por otra vía: un **script autónomo** que hace la
ingesta de las 9 tablas de compras y construye el schema, sin depender de
ningún archivo del pipeline.

## Contenido

```
scripts/compras_setup.py                          ← NUEVO, autónomo
etl_sigrid/infrastructure/postgres/sql/compras/    ← los 4 SQL (por si no los copiaste)
    00_setup.sql  01_documentos.sql  02_fact_linea.sql  03_views.sql
```

## Uso

```powershell
# 1. Copia la carpeta scripts/ y sql/compras/ al proyecto
# 2. Comprueba conexiones (5 segundos)
python scripts\compras_setup.py --check

# 3. Ingesta + construcción (10-15 min la primera vez, 2,9M filas)
python scripts\compras_setup.py --all
```

Otras opciones:

```powershell
python scripts\compras_setup.py --ingest              # solo ingesta a raw
python scripts\compras_setup.py --build               # solo los 4 SQL
python scripts\compras_setup.py --all --tabla dcapro  # una tabla concreta
```

Es **idempotente**: cada tabla se recrea (DROP + CREATE + COPY), así que se
puede relanzar sin miedo. No toca ninguna tabla del pipeline existente
(solo crea `raw.com`, `raw.comlin`, `raw.comprv`, `raw.ctrpro`, `raw.dca`,
`raw.dcapro`, `raw.dcf`, `raw.dcfpro`, `raw.dcfprodes` y el schema `compras`).

## Cómo funciona

1. Lee las columnas reales de cada tabla en Sigrid vía
   `INFORMATION_SCHEMA.COLUMNS` (así no hay que adivinar nada) y descarta
   texto largo y binarios (`text`, `image`, `xml`, `varbinary`…).
2. Mapea tipos: enteros → `BIGINT`, reales → `DOUBLE PRECISION`, resto → `TEXT`.
3. Crea `raw.<tabla>` y la puebla paginando por `ide` con `COPY` (rápido).
4. Ejecuta los 4 SQL del schema `compras`.
5. Imprime conteos y el desglose por tipo de documento.

Credenciales: lee el `.env` del proyecto y acepta varios nombres habituales
(`SIGRID_API_BASE_URL` / `SIGRID_API__BASE_URL`, `PG_HOST` / `POSTGRES_HOST`,
etc.). Si falta alguna, te dice cuál y lista las variables que sí encuentra.

## Consultas para verificar

```sql
-- Contratos agotándose
SELECT codigo_contrato, codigo_obra, proveedor_nombre,
       importe_contratado, importe_albaranado, importe_certificado_proforma,
       importe_facturado, importe_albaranado_sin_facturar,
       importe_consumido, importe_disponible, pct_consumido
FROM compras.v_pbi_contrato_consumo
WHERE pct_consumido >= 90
ORDER BY pct_consumido DESC;

-- Proveedores de una obra por facturación
SELECT proveedor_nombre, facturado, albaranado, certificado_proforma
FROM compras.v_pbi_proveedor_obra
WHERE codigo_obra = '0707' AND anio = 2026
ORDER BY facturado DESC NULLS LAST LIMIT 10;

-- Albaranado sin facturar
SELECT codigo_albaran, tipo_documento, fecha, proveedor_nombre,
       importe, importe_pendiente_facturar, dias_desde_albaran
FROM compras.v_pbi_albaranes_sin_facturar
ORDER BY importe_pendiente_facturar DESC LIMIT 30;

-- Coste de compras por partida
SELECT codigo_partida, descripcion_partida,
       albaranado, certificado_proforma, facturado, contratado
FROM compras.v_pbi_partida_coste
WHERE codigo_obra = '0707'
ORDER BY COALESCE(facturado,0) + COALESCE(albaranado,0) DESC;
```

## Validación realizada

Ejecutado de punta a punta contra PostgreSQL real con API simulada:
descubrimiento de columnas, creación de las 9 tablas raw, COPY, los 4 SQL y
verificación de importes. Escenario contrato 1.000 € → albarán 500 € +
proforma 100 € → facturas 320 € + abono −20 € + factura directa 50 €:
contratado 1.000 / albaranado 500 / proforma 100 / facturado 350 /
pendiente facturar 280 / consumido 650 / **65,00 %** — todo al céntimo.

## Para la integración definitiva

Este script es la vía rápida. Para dejarlo en el pipeline oficial
(`ingest` + `build-compras`) necesito tus dos archivos actuales:

```
config/tables_sigrid.yaml
main.py
```

Con ellos te devuelvo ambos completos y modificados, sin riesgo de perder
`build-cierre`, `build-maestros`, `inspect-todo` ni el resto de comandos que
tienes. Mientras, el script hace exactamente el mismo trabajo.
