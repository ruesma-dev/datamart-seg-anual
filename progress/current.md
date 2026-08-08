<!-- progress/current.md -->
# Trabajo en curso

**F-008 · in_progress** — rama `feature/F-008-docs-referencia-sigrid-acens`.

Los **tres** documentos de referencia están incorporados y commiteados:

- `01_sigrid_tablas.md` (`e8cd88e`) — diccionario de la BBDD de Sigrid.
- `02_azure_landing_zone_acens.md` (`c8e90ea`) — landing zone, redactado.
- `03_sigrid_api.md` (`f61512c`) — microservicio `sigrid-api`, redactado.

El commit `f61512c` añade además la regla de las dos paradas con el humano
(`CLAUDE.md`, `leader.md`, `implementer.md`) y actualiza el título y la
descripción de F-008 para incluir el tercer documento. Informe completo en
`progress/impl_F-008.md` (commit `f8864a7`).

`bash harness/init.sh` en verde.

**Revisión:** el reviewer devolvió `CHANGES_REQUESTED` el 2026-08-08
(`progress/review_F-008.md`). Los nueve criterios `acceptance` se cumplen y el
barrido de secretos salió limpio; el único bloqueo era la incoherencia de este
mismo fichero, ya corregida. Pendiente: **reemitir veredicto** y, con el
APROBADO, merge a `dev`.

El review deja cinco propuestas de automejora (P1–P5) que **no** se han
aplicado: pendientes de decisión del humano. La más relevante es P1, blindar
`.gitignore` contra los originales en PDF y ofimática.

## Backlog: altas y decisiones de esta sesión (2026-08-08)

- **F-008** dada de alta a petición del humano, por delante de F-002.
- **F-009 · Inventario del entorno Azure existente**, prioridad 2, por delante
  de todo el bloque Azure. Solo lectura. Debería cerrar D2 y aportar a D1, D3
  y D5.
- **F-010 · Carga y mantenimiento de los Excels auxiliares en Azure**,
  prioridad 9, junto a F-007: depende de que exista la app web.
- **D5 parcialmente cerrada**: los Excels auxiliares se suben a Azure. Falta
  la storage account concreta (debería salir de F-009) y quién los mantiene.

Prioridades tras la renumeración: F-009=2, F-004=3, F-005=4, F-003=5,
F-006=6, F-008=7, F-002=8, F-010=9, F-007=10.
