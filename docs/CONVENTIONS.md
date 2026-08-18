<!-- docs/CONVENTIONS.md -->
# Convenciones · datamart-seg-anual

> Documento normativo: el reviewer valida contra él.

## Estructura y estilo

- Primera línea de CADA fichero de código: comentario con su ruta relativa.
  Ej.: `# etl_sigrid/application/steps/build_stg_step.py`
- Arquitectura hexagonal (Ports & Adapters): `domain` sin dependencias,
  `application` orquesta, `infrastructure` adapta. Patrón pipeline + steps
  con objeto contexto; la composición del pipeline se hace en el punto de
  entrada (`orchestrator.py`), no dentro de los steps.
- Configuración leída del entorno (`.env` en local), parametrizaciones en
  YAML dentro de `config/`. **Ningún secreto en código.**
- Logging estructurado. Prohibido `print()` en código de producción
  (permitido en `scripts/` puntuales).
- Errores transitorios de red: reintentos con backoff, nunca bucle desnudo.

### Python

- Python 3.12, PEP8, type hints en firmas públicas.
- Pydantic v2. `default=` solo en la firma, nunca duplicado dentro de
  `Field()`.
- Configuración: `config/settings.py` (pydantic-settings) leyendo `.env`.
- Logging con structlog vía `infrastructure/logging_config.py`. Reintentos
  con tenacity, ya modelado en los clientes existentes; reutilizar ese
  patrón.

## SQL

- Un fichero por unidad lógica, numerado `NN_nombre.sql` dentro de su capa.
- Idempotente: `CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE VIEW`.
- Comentario de cabecera explicando qué construye y de qué capa lee.
- Palabras reservadas siempre entre comillas si se usan como identificador.

## Tests

- pytest en `tests/`. Los unit tests no tocan red ni BBDD: mocks y fixtures.
- Un requisito EARS (o criterio `acceptance`) => al menos un test con nombre
  trazable (`test_fXXX_rN_...`).
- Mock de clientes (Sigrid/Postgres) en unit tests. Nada de credenciales en
  los tests, ni siquiera de entornos de desarrollo.

## Git

- Ramas: `main` (estable) ← `dev` (integración) ← `feature/F-XXX-slug`.
- Commits: `F-XXX Tn: descripción` (tareas) o `F-XXX: descripción` (ajustes).
- Los agentes solo hacen commit local en ramas feature. Push, merge a dev y
  PRs: siempre el humano.
- Los originales en PDF u ofimática no se versionan (ver `.gitignore`).

<!-- ==================== INICIO · ENTORNO DE RUESMA ==================== -->
<!-- Convenios de la organización, no del arnés. Fuera de ese entorno,     -->
<!-- borra el bloque entero hasta el comentario de cierre.                 -->

## Convenios del entorno de Ruesma

- **Todo en español**, incluidos comentarios de código y mensajes de commit.
- CSV de salida: UTF-8 BOM, `;` como separador, coma decimal (Excel ES).
- PowerShell: UTF-8 con BOM y CRLF (salvo excepciones documentadas).
- Medidas DAX sin tildes.
- Azure: imágenes con tags fechados (`rYYYYMMDD-HHmm`), nunca reescribir
  tags; secretos como secrets del recurso, jamás desplegar `.env`.

<!-- ===================== FIN · ENTORNO DE RUESMA ====================== -->
