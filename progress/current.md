<!-- progress/current.md -->
# Trabajo en curso

**F-014 · in_progress** — rama `feature/F-014-arnes-generico`. `sdd=false`:
la especificación son sus criterios `acceptance` en `harness/features.json`.

Extraer de este proyecto un arnés genérico, versionado e instalable en
cualquier repositorio. Ya existe `C:\Users\pgris\PycharmProjects\arnes-base`
con un snapshot del 2026-08-08 a las 13:01 y un `instalar_arnes.ps1`, pero
**no es un repositorio git** y **nació obsoleto**: le faltan las cinco
mejoras de esa misma tarde.

La regla de propagación ya está escrita en el `CLAUDE.md` de este proyecto y
en el del directorio padre, deliberadamente **antes** de implementar la
feature: si no, la próxima mejora se vuelve a perder.

## Estado: implementación terminada, pendiente de review

Informe completo en **`progress/impl_F-014.md`**. Los **13** criterios
`acceptance` quedan cubiertos —el nº 13 lo añadió el humano el 2026-08-09,
ya iniciada la feature—. Resumen: `arnes-base` es ya un repositorio git con
el arnés genérico **v1.1.0**, guía de instalación de tres caminos e
instalador con modo actualizar que enseña el diff. Documento actualizado en
`azure-apps`. `bash harness/init.sh` de este repositorio en verde, 65 tests.

Commits de esta rama: `53d1127`, `be54b6c`, `e33d929`, `824e23f` (el añadido
de que Windows no suspenda el equipo) y el de corrección de la review.

**Ojo, reviewer**: la feature toca **tres repositorios** con commits
independientes. Los de `arnes-base` y `azure-apps` no salen en el diff de
esta rama; están listados en el §1 del informe.

### Verificaciones MANUAL pendientes (humano)

1. **Modo interactivo del instalador en consola real** (se probó con
   respuestas por stdin, no tecleando):
   ```powershell
   cd C:\Users\pgris\PycharmProjects\arnes-base
   .\instalar_arnes.ps1 -Destino "C:\ruta\copia-de-pruebas" -Modo actualizar
   ```
2. **Decidir el remoto de `arnes-base`.** Hoy no tiene. Antes de publicarlo,
   decidir si las rutas locales `C:\Users\pgris\...` deben salir: el
   historial de git no suelta lo que entra, y ahora es el momento barato.

### Decisiones que quedan para el humano (no bloquean el cierre)

- **Portar hacia este proyecto** las cuatro mejoras que el arnés genérico
  tiene y este repositorio no (LÍMITE DE MICROSERVICIO, `init.sh` con
  `LINT_BLOQUEA`/`REQUIERE_ENV`/aviso de `[ADAPTAR]`). Merece feature propia.
- **Convertir la regla de propagación en mecanismo**: hoy es una norma
  escrita y nada impide incumplirla. Candidato: un punto en `CHECKPOINTS.md`
  que el reviewer recorra cuando la feature haya tocado ficheros del arnés.

F-005 cerrada el 2026-08-08, resumen en `progress/history.md`.

## Pendiente del humano: runbook de F-005 (Fase 2)

Nada se ha ejecutado contra Azure. El procedimiento está en
`docs/runbook_postgres_azure.md`. Orden y puertas:

1. **Fotografía previa** de las reglas de firewall (solo lectura).
2. **PUERTA BLOQUEANTE**: menos de **14 GB libres** de los 32 → parar.
   Ampliar almacenamiento es **irreversible**: el disco solo crece.
3. Generar las dos contraseñas y guardarlas en **Key Vault**, nunca en el
   repositorio.
4. `01_create_database.sql` y `02_roles.sql` (idempotentes). Después,
   comprobar que **`albaranes` y `partes` siguen conectando**.
5. Firewall, solo si la IP no está cubierta.
6. Huella local con el mes cerrado que fije el humano.
7. **Carga inicial**. El `apply-grants` final **no es opcional**.
8. **Medición** → `progress/medicion_carga_inicial.md` con veredicto sobre si
   `Standard_B1ms` aguanta. Es la entrada de F-011.
9. Verificación: comparar huellas, comprobar que el rol de lectura no
   escribe, y refrescar el informe de Power BI.

## Siguiente por prioridad tras F-014

F-003 (infra del Container Apps Job), con spec escrita y aprobada.
