<!-- progress/impl_F-008.md -->
# F-008 · Documentación de referencia: tablas de Sigrid y landing zone de acens

Fecha: 2026-08-08 · Rama: `feature/F-008-docs-referencia-sigrid-acens`
Ejecutado por el líder **sin delegar** en el `implementer` (ver «Notas» abajo).

## Qué se ha hecho

Dos documentos que solo existían en PDF fuera del repositorio entran ahora
como Markdown en `docs/referencia/`. Ambos convertidos con la herramienta MCP
`markitdown`, conforme a la regla de `CLAUDE.md`. Los PDF originales **no**
se han copiado al árbol de trabajo ni versionado.

### `01_sigrid_tablas.md` — commit `e8cd88e`

Origen: `tablas_sigrid.pdf`, «AUTODOCUMENTADOR ESTRUCTURA BASE DE DATOS
SIGRID v.20240618», 380 páginas, fechado el 2024-11-06.

Diccionario completo del sistema origen: entidades, campos, tipos, índices y
referencias entre tablas. 21.977 líneas, ~2,1 MB.

Se guarda la **salida literal** de `markitdown`, sin retoques, para que la
conversión sea reproducible por quien la repita. Eso conserva dos defectos,
documentados en la cabecera del propio fichero:

- la cabecera «AUTODOCUMENTADOR…» se repite en cada una de las 380 páginas;
- unas pocas filas traen columnas del PDF pegadas entre sí (efecto de la
  extracción, no del original).

Verificado por búsqueda que no contiene correos, IPs ni valores de
credenciales: es un diccionario de esquema, no datos.

### `02_azure_landing_zone_acens.md` — commit `c8e90ea`

Origen: `CO388632 Construcciones Ruesma - Documento Entregable.pdf`, acens,
fechado el 2026-03-25.

Diseño de la Landing Zone Fundacional de Azure. **Versión redactada**, por
decisión expresa del humano tomada en sesión tras señalarle los tres riesgos:

1. el original lleva declaración de confidencialidad de acens que prohíbe la
   reproducción total o parcial → queda citada en la cabecera y el documento
   se marca como referencia interna;
2. rangos de red reales (cuenta, management, HUB, PRO, DEV/POC, subredes del
   HUB y red de la sede) → sustituidos por marcadores `<RANGO-*>`,
   `<SUBRED-*>`, `<RED-SEDE-CLIENTE>`;
3. dos correos personales destinatarios de alertas → sustituidos por
   `<correo-alertas-1>` y `<correo-alertas-2>`.

Verificado por búsqueda que el Markdown resultante no contiene **ninguna** IP
ni correo. No había credenciales, IDs de suscripción ni tenant en el original.

El resto del contenido es fiel al documento. El detalle redactado sigue
disponible en el PDF original, fuera del repositorio.

También se añade un índice a `docs/referencia/README.md`.

## Estado de los criterios de aceptación

| Criterio | Estado |
|---|---|
| Conversión con la herramienta MCP `markitdown` | Cumplido en ambos |
| `01_sigrid_tablas.md` con cabecera de origen y fecha | Cumplido |
| `02_azure_landing_zone_acens.md` con cabecera | Cumplido |
| Nombres conformes a `NN_tema.md` | Cumplido |
| Originales fuera del repositorio | Cumplido |
| Sin secretos ni datos sensibles; redacción anotada | Cumplido y verificado por búsqueda |
| `README.md` menciona los documentos nuevos | Cumplido (índice) |
| `bash harness/init.sh` en verde | Cumplido (22 tests, rama de feature) |

## Lo que aporta al bloque Azure

El documento de acens es material directo para dos decisiones abiertas:

- **D1 (acceso de red al Postgres).** Ya existe hub&spoke en *Spain Central*
  con Azure Firewall en modalidad Basic, VPN Site-to-Site permanente contra
  la red de la sede y VPN SSL para puestos. La opción B (private endpoint +
  VPN) deja de implicar montar la VPN desde cero. Nota: no se provisionan
  NSGs, el filtrado es del firewall central.
- **D3 (¿solo dev o también producción?).** El diseño ya contempla división
  por entorno DEV/STA/PRO y rangos de red reservados para PRO y DEV/POC, y
  todo se despliega con Terraform vía pipelines de Azure DevOps. Apunta a
  parametrizar `infra/` por entorno desde el principio.

Ninguna de las dos decisiones se cierra aquí: son del humano.

## Notas

- Trabajo hecho por el líder sin lanzar el subagente `implementer`: la
  sesión trae la instrucción de no invocar la herramienta Agent salvo
  petición explícita del humano, que prevalece sobre la autorización
  permanente de `CLAUDE.md`. El rastro documental se mantiene igualmente.
- **Falta el veredicto del `reviewer`** contra `CHECKPOINTS.md` para poder
  marcar F-008 como `done`. La feature queda en `in_progress`.
