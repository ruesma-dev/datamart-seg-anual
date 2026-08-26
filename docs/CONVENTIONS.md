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

## El diccionario semántico

`config/diccionario/` es la capa semántica del datamart: un YAML por esquema
—más `00_global.yaml` con las reglas duras— que explica qué significa cada
objeto publicado y qué trampas tiene al leerlo. De ahí lo publica en `_meta` el
paso `publicar_diccionario`, y de `_meta` lo lee por SQL el servidor MCP. Cómo
encaja: `docs/ARCHITECTURE.md`.

- **Quien añade o cambia un objeto publicado actualiza su ficha en el mismo
  trabajo**, no después. Vale para una tabla o una vista nuevas, una columna
  añadida o renombrada, y cualquier cambio de grano o de significado. Una ficha
  que describe el objeto de antes no es documentación incompleta: es una
  afirmación falsa, y quien la lee es un agente que no puede preguntar.
- **Si la ficha no se puede escribir ahora, se declara como pendiente** en
  `config/diccionario/00_global.yaml`. Aplazarla es legítimo; ignorarla no.
  `bash harness/init.sh` exige ficha **o** pendiente declarado, y la lista de
  pendientes solo puede bajar: el trinquete no admite añadidos silenciosos.
- **La ficha se contrasta contra la base, no contra la memoria**:
  `python main.py check-diccionario` compara el diccionario del árbol con el
  catálogo real —objeto publicado sin ficha, ficha sin objeto, tipo que no
  casa— y avisa si lo publicado va por detrás del repositorio. Necesita
  conexión, así que la puerta offline de `init.sh` no puede hacer ese trabajo.
- **Sube `version` en `00_global.yaml`** cuando el contenido cambie. La
  identidad de lo publicado es el `hash_fuente`, calculado sobre los ficheros;
  la versión es lo que lee una persona. Publicar es
  `python main.py publicar-diccionario`, y contra Azure eso es una escritura:
  la autoriza el humano, no un agente.
- El diccionario describe **lo que el dato ES**, nunca cómo se decide con él.
  Un procedimiento de negocio no entra en un YAML de `config/diccionario/`.

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
