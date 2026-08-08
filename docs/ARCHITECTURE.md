<!-- docs/ARCHITECTURE.md -->
# Arquitectura · datamart-seg-anual

ETL Sigrid → PostgreSQL → Power BI para el seguimiento económico mensual de
obras. Microservicio único; se despliega como job programado en Azure.

## Hexagonal + pipeline

- `etl_sigrid/domain/` — entidades puras (TableSpec, ColumnSpec, StepResult,
  StepStatus). CERO imports de infraestructura.
- `etl_sigrid/application/` — `Orchestrator` ejecuta una lista de steps.
  Cada step hereda de `steps/base.py::PipelineStep` y recibe/enriquece un
  contexto. Steps actuales: ingest_raw, load_excel_aux, build_stg, build_mart,
  build_maestros, build_cierre.
- `etl_sigrid/infrastructure/` — adaptadores: `sigrid/sigrid_api_client.py`
  (HTTP a sigrid-api), `postgres/postgres_client.py`, SQL por capas en
  `postgres/sql/`, logging estructurado.
- Punto de entrada: `main.py` (click). El pipeline se compone en main, no
  dentro de los steps.

## Capas PostgreSQL (¡no existe capa en `public`!)

`raw` → `stg` → `mart` (+ `cierre` para cierres mensuales y planif vs real).
Módulos adicionales: `compras`, `maestro`, `retenciones`, `auxiliar`.
SQL numerado `NN_nombre.sql` y ejecutado en orden dentro de cada capa.

## Semántica Sigrid imprescindible (fuente de bugs si se ignora)

- Ámbitos: amb=3 Coste Real, amb=7 Venta Real, amb=8 Master Coste,
  amb=11 Master Venta.
- Master (amb 8/11): `fas` = número de VERSIÓN; planif explosionada.
- Reales (amb 3/7): `fas` = MES; fas=0 = Previsto (foto viva),
  fas=1..N cierres mensuales; planif NO explosionada;
  importe del mes = diferencia con la fase anterior.
- `obr.ide = con.ide` (obra hereda de concepto). El nombre legible está en
  `con.res`. `con.nom` NO existe.
- En `raw.obrfas` el campo de fase se llama `fasnum`; en `raw.obrparpre` se
  llama `fas`. No confundirlos.
- Versión de master vigente por obra: campo extendido `cod='15'` en `conext`.
- `importe_origen = round(can * round(precio, decp), deci)`;
  `importe_mes` = diferencia entre orígenes consecutivos.
  REGLA: `importe_mes` jamás se suma entre meses distintos en vistas para
  Power BI; `importe_origen` es acumulado.
- Fechas Sigrid: enteros YYYYMMDD; 0 = NULL.
- La ingesta nocturna SIEMPRE `--full` (el cursor incremental por `ide`
  pierde los UPDATE).
- Palabra reservada `real` en vistas de `cierre` → siempre entre comillas.

## Acceso a datos

- Sigrid solo vía sigrid-api (`POST /api/sql/read`), nunca conexión directa.
  Tope duro 10.000 filas/petición; timeout de red efectivo 230 s.
- Solo LECTURA de Sigrid desde este proyecto. Las escrituras del datamart van
  al PostgreSQL propio (local en dev, Flexible Server en Azure).

## Infra

- `Dockerfile` en raíz. `infra/` con scripts PowerShell 5.1 (UTF-8 BOM, CRLF)
  siguiendo el patrón `00_vars.ps1` como única fuente de verdad de nombres.
- Destino: Azure Container Apps Job programado en `rg-seguimiento-dev`,
  región `spaincentral`. Tags de imagen fechados (`rYYYYMMDD-HHmm`), nunca
  reescribir tags.
