<!-- docs/CONVENTIONS.md -->
# Convenciones · datamart-seg-anual

## Python

- Python 3.12, PEP8, type hints en firmas públicas.
- Primera línea de CADA fichero: comentario con su ruta relativa.
  Ej.: `# etl_sigrid/application/steps/build_stg_step.py`
- Pydantic v2. `default=` solo en la firma, nunca duplicado dentro de
  `Field()`.
- Configuración: `config/settings.py` (pydantic-settings) leyendo `.env`.
  Parametrizaciones en YAML dentro de `config/`. Ningún secreto en código.
- Logging con structlog vía `infrastructure/logging_config.py`. Prohibido
  `print()` en código de producción (permitido en `scripts/` puntuales).
- Errores transitorios de red: tenacity con reintentos, ya modelado en los
  clientes existentes; reutilizar ese patrón.

## SQL

- Un fichero por unidad lógica, numerado `NN_nombre.sql` dentro de su capa.
- Idempotente: `CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE VIEW`.
- Comentario de cabecera explicando qué construye y de qué capa lee.

## Tests

- pytest en `tests/`. Los tests de humo no tocan red ni BBDD.
- Un requisito EARS => al menos un test con nombre trazable
  (`test_f002_r1_...`).
- Mock de clientes (Sigrid/Postgres) en unit tests; nada de credenciales.

## Git

- Ramas: `main` (estable) ← `dev` (integración) ← `feature/F-XXX-slug`.
- Commits: `F-XXX Tn: descripción` (tareas) o `F-XXX: descripción` (ajustes).
- Los agentes solo hacen commit local en ramas feature. Push, merge a dev y
  PRs: siempre el humano.

## Entregas y ficheros

- CSV de salida: UTF-8 BOM, `;` como separador, coma decimal.
- PowerShell: UTF-8 con BOM y CRLF.
- Medidas DAX sin tildes.
