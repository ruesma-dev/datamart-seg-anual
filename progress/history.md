<!-- progress/history.md -->
# Histórico del arnés

Registro append-only. El líder mueve aquí el resumen de cada feature terminada.

---

## F-001 — Comando 'version' en el CLI · 2026-08-08

Rama `feature/F-001-cli-version` (desde `dev` en b979b82). `sdd=false`.
Veredicto APROBADO, detalle en `progress/review_F-001.md`.

`python main.py version` imprime versión, tag de imagen, fecha de build y
versión de Python, y sale con 0. `ETL_VERSION` y `get_build_info()` viven en
`config/settings.py`; el tag y la fecha llegan por `IMAGE_TAG`/`BUILD_DATE`
y valen `local` fuera de un contenedor. El `Dockerfile` los recibe como
`ARG` al final del fichero e `infra/20_build_image.ps1` los inyecta en el
build, de modo que la imagen desplegada dice qué build es.

Decisión: `version` se salta `get_settings()` mediante
`ctx.invoked_subcommand`, porque la configuración aborta sin `SIGRID_API_*`
y este es justo el comando que hace falta cuando el contenedor arranca mal
configurado. Verificado que el resto de comandos siguen configurándose.

Commits: e617309 (T0 backlog + arranque), 83730e3 (T1 comando),
cfbdd1b (T2 tests), e37a6b7 (T3 sellado de imagen).
Tests: 15 → 22.

Pendientes anotados, fuera de alcance: `.ps1` en LF frente a la convención
CRLF (llevar a F-003), `ruff` configurado pero no instalado ni ejecutado por
`init.sh`.

---

## F-008 · Documentación de referencia: tablas de Sigrid, landing zone de acens y sigrid-api

Cerrada el 2026-08-08. `sdd=false`. Rama
`feature/F-008-docs-referencia-sigrid-acens`. APROBADA en segunda revisión
(`progress/review_F-008.md`).

Tres documentos que vivían fuera del repositorio entran como Markdown en
`docs/referencia/`:

- `01_sigrid_tablas.md` — Autodocumentador de la BBDD de Sigrid v.20240618,
  380 páginas, ~22.000 líneas. Diccionario de tablas, campos, tipos e
  índices del sistema origen. Salida literal de `markitdown`, sin retoques,
  para que la conversión sea reproducible; los artefactos de extracción
  (cabecera de página repetida, columnas pegadas) quedan advertidos en su
  cabecera.
- `02_azure_landing_zone_acens.md` — diseño de la Landing Zone. Redactado:
  fuera rangos de red y correos personales; la confidencialidad de acens,
  citada en cabecera.
- `03_sigrid_api.md` — microservicio `sigrid-api`, único punto de acceso a la
  BBDD de Sigrid y a quien llama `etl_sigrid/infrastructure/sigrid/`. Llegó
  ya en Markdown, sin conversión. Redactado: fuera el ID de suscripción y el
  host del SQL on-prem; los nombres de recursos se mantienen porque ya
  estaban en `infra/` y en el `README.md`.

Decisión de método: el reviewer ejecuta su propio barrido de datos sensibles
en vez de fiarse del informe del implementer. Salió limpio (cero correos,
cero GUID, cero IPs internas, cero valores de credencial) y esa práctica se
eleva a checkpoint en C3 bis.

Cambios de arnés incluidos en la feature:

- Regla de las **dos paradas con el humano** (proponer y esperar confirmación
  antes de implementar; resumir después), en `CLAUDE.md`, enganchada al flujo
  de `.claude/agents/leader.md` como PARADA 1 y PARADA 2, y reflejada en
  `.claude/agents/implementer.md`.
- Las cinco propuestas de automejora del review, aplicadas: `.gitignore`
  blinda los originales en PDF y ofimática (P1); `CHECKPOINTS.md` explica
  cómo revisar features `sdd=false` (P2) y añade **C3 bis** para documentos
  que entran de fuera (P5); `CLAUDE.md` aclara que la autorización de
  subagentes no exime de la PARADA 1 (P3); `docs/referencia/README.md`
  recoge las variantes de cabecera y el bloque de redacción (P4).

Backlog: alta de **F-009** (inventario del entorno Azure, prioridad 2, solo
lectura) y **F-010** (carga de los Excels auxiliares, prioridad 9). **D5**
parcialmente cerrada: los Excels van a Azure; falta la storage account y
quién los mantiene.

Commits: e8cd88e, c8e90ea, f8864a7, f61512c, 38cde59 y el de cierre.

---
