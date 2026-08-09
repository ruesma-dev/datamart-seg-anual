<!-- progress/current.md -->
# Trabajo en curso

(vacío — ninguna feature en ejecución)

F-014 cerrada el 2026-08-09, resumen en `progress/history.md`.

## Pendiente del humano

1. **Runbook de F-005 (Fase 2)** — nada se ha ejecutado todavía contra Azure.
   Procedimiento completo en `docs/runbook_postgres_azure.md`. Empieza por la
   **puerta bloqueante de los 14 GB libres**: por debajo, la carga inicial no
   arranca, porque ampliar el almacenamiento de un Flexible Server es
   irreversible.
2. **El hook de energía no está activo en la sesión en curso**: Claude Code
   lee la configuración al arrancar. Se activará en la siguiente sesión.
   Mientras tanto, `scripts/mantener_despierto.ps1` se lanza a mano.
3. **La regla de firewall `dev-puesto-pgris-2026-08-08`** sigue puesta en
   `sql-sigridetl-dev-8yv7pj`. El servidor ya no tiene bases de usuario, así
   que es inocua; se retira con el resource group en F-012.

## Siguiente por prioridad

**F-003 · Infra: despliegue como Container Apps Job diario**, prioridad 5,
`spec_ready` y ya aprobada por el humano. Necesita de F-005 el host, el
nombre de la base y el del rol: si no están, la implementación debe marcar
`blocked` en vez de inventar valores. Ver `specs/F-003-infra-caj/`.

Detrás, **F-015 · Verificar que los tests son de verdad** (mutación acotada
al diff, evidencia de fase RED, cobertura con umbral y niveles de rigor),
dada de alta el 2026-08-09 tras revisar el arnés de Uncle Bob
(`betta-tech/harness-sdd`) y la skill `AmazingAng/old-coder`.

## Decisiones abiertas

**Ninguna.** Las siete decisiones del bloque Azure (D1 a D7) están cerradas;
el detalle y su justificación, en `progress/decisiones_abiertas.md`. Lo que
queda pendiente no son decisiones sino ejecución: el runbook de arriba.
