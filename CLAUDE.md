<!-- CLAUDE.md -->
# Arnés · datamart-seg-anual

Eres parte de un sistema de agentes (arnés) de este repositorio. Tu punto de
entrada es el rol **líder**: lee `.claude/agents/leader.md` y actúa según su
protocolo. Todo en español.

## Autorización permanente de subagentes

El humano **autoriza y espera** que lances los subagentes de
`.claude/agents/` (`spec-author`, `implementer`, `reviewer`) mediante la
herramienta Agent. No hace falta pedir permiso feature a feature: esta línea
es esa petición explícita, dada de antemano y para todas las sesiones.

Si el entorno te impide lanzarlos (por ejemplo, una sesión hija de Claude
Code, detectable con `CLAUDE_CODE_CHILD_SESSION=1`, arranca restringida),
**dilo en el primer mensaje** en vez de asumir el trabajo en silencio: el
humano decidirá si relanza la sesión desde una terminal limpia o si acepta
que trabajes sin delegar. Si trabajas sin delegar, mantén igualmente el
rastro documental en `progress/`.

## Protocolo obligatorio (antes de cualquier trabajo)

1. Ejecuta `bash harness/init.sh`. Si falla, **PARA** y reporta el motivo.
   No trabajes nunca sobre un entorno en rojo.
2. Lee `progress/current.md`. Si hay trabajo a medias o una feature
   `blocked` de una sesión anterior, retómala antes de empezar nada nuevo.
3. Lee `harness/features.json` y localiza la primera tarea no terminada
   (por orden de prioridad: `blocked` > `in_progress` > `spec_ready` >
   `pending`). Máximo UNA feature `in_progress` a la vez (init.sh lo valida).
4. Sigue el flujo SDD descrito en `.claude/agents/leader.md`.

## Mapa del repositorio (no leas todo el proyecto, ve a lo que necesites)

- `main.py` — CLI (click). Comandos: check-api, check-pg, bootstrap, ingest,
  stage, build-mart, run-all, status.
- `config/` — `settings.py` (pydantic-settings sobre `.env`),
  `tables_sigrid.yaml` (tablas a ingerir), `business_rules.yaml`.
- `etl_sigrid/domain/` — entidades puras (sin dependencias externas).
- `etl_sigrid/application/` — `orchestrator.py` + `steps/` (patrón pipeline;
  cada step hereda de `steps/base.py`).
- `etl_sigrid/infrastructure/postgres/` — cliente + `sql/` por capa:
  `raw` (implícito en ingesta), `stg/`, `mart/`, `cierre/`, `compras/`,
  `maestro/`, `retenciones/`, `auxiliar/`.
- `etl_sigrid/infrastructure/sigrid/` — cliente HTTP de sigrid-api.
- `tests/` — pytest. Los de humo NO tocan red ni BBDD.
- `specs/` — especificaciones SDD (una carpeta por feature).
- `progress/` — memoria externa del arnés (`current.md`, `history.md`,
  informes `impl_*.md` / `review_*.md` / `explore_*.md` por subagente).
- `docs/` — `ARCHITECTURE.md`, `CONVENTIONS.md`.
- `docs/referencia/` — información adicional de negocio y del sistema origen
  (manuales de Sigrid, criterios de cierre, documentación que llega de
  fuera), toda en Markdown. Consúltala cuando la pregunta sea «por qué el
  ETL hace esto» y la respuesta no esté en el código. Ver su `README.md`.
- `CHECKPOINTS.md` — criterios objetivos de estado final; el reviewer los
  recorre antes de cerrar cualquier feature.
- `infra/` — scripts PowerShell de despliegue a Azure + `Dockerfile` en raíz.

## Documentos que llegan de fuera (PDF y ofimática)

Cuando el humano pase un PDF —o un `.docx`, `.xlsx`, `.pptx`— conviértelo a
Markdown y guárdalo en `docs/referencia/` antes de trabajar con él. El
original NO se versiona: al repositorio entra solo el Markdown.

- Usa la herramienta MCP `markitdown` si está conectada. Si no lo está,
  conviértelo leyendo el documento directamente; no es motivo para parar.
- Nombra el fichero según la convención de `docs/referencia/README.md` y
  ponle la cabecera con origen y fecha del documento.
- Si el documento trae datos sensibles (precios de proveedor, datos
  personales, credenciales), **no lo conviertas sin preguntar**: acabaría
  versionado en git.

## Reglas duras (no negociables)

- PROHIBIDO marcar una feature como `done` sin que `bash harness/init.sh`
  termine en verde (incluye pytest) y sin veredicto APROBADO del reviewer
  contra `CHECKPOINTS.md`.
- PROHIBIDO tocar `.env` o subirlo a git. Los secretos no se escriben en
  ningún fichero del repo ni en specs ni en progress.
- PROHIBIDO ejecutar comandos que escriban contra Sigrid o contra el Postgres
  de producción. En local solo lecturas de Sigrid (`ingest`) y escrituras al
  Postgres local/dev definido en `.env`.
- Cada feature se desarrolla en su rama `feature/F-XXX-slug`. Nunca commits
  directos a `dev` ni a `main`.
- ANTI TELÉFONO-DESCOMPUESTO: por el chat no circula código ni informes
  largos. Cada subagente escribe su resultado en `progress/` y responde con
  UNA línea de referencia (`done -> progress/impl_F-XXX.md`). Si un
  subagente devuelve contenido largo por chat sin fichero, se rechaza.
- Si una herramienta falla de forma inesperada o la spec resulta ambigua:
  NO improvisar workarounds. Marcar la feature `blocked`, anotar el motivo
  en `progress/current.md` y parar.
- Convenciones de código: `docs/CONVENTIONS.md`. Arquitectura:
  `docs/ARCHITECTURE.md`. Léelos antes de diseñar o implementar.
- Los agentes NO hacen `git push` ni crean PRs salvo petición explícita del
  humano. Commits locales sí, según protocolo del implementer.
