<!-- GUIA_USO_HARNESS.md -->
# Guía de uso · Arnés SDD con Claude Code (prototipo datamart)

## 0. Instalación de los ficheros (una vez)

1. Copia el contenido de este ZIP a la raíz de
   `C:\Users\pgris\PycharmProjects\datamart-seg-anual\` respetando carpetas.
   Ficheros nuevos: `CLAUDE.md`, `.claude/`, `harness/`, `specs/`,
   `progress/`, `docs/`, `infra/`, `Dockerfile`, esta guía.
   No se modifica ningún fichero existente.
2. Añade al `.gitignore` (opcional): nada. `progress/` SÍ se versiona —
   es la memoria compartida entre sesiones y máquinas.
3. Commit inicial del arnés en `dev`:
   ```
   git checkout dev
   git add CLAUDE.md .claude harness specs progress docs infra Dockerfile GUIA_USO_HARNESS.md
   git commit -m "Arnes SDD: agentes, init.sh, features, specs, infra"
   ```

## 1. Claude Code en PyCharm (verificación)

Con el plugin ya instalado: abre el proyecto en PyCharm y pulsa el icono de
Claude en la barra lateral (o abre el terminal integrado y ejecuta `claude`).
Claude Code en Windows ejecuta los comandos bash vía Git Bash, así que
`bash harness/init.sh` funciona tal cual. Prueba manual previa recomendable
desde Git Bash o desde el propio Claude:

```
bash harness/init.sh
```

Debe terminar en "ENTORNO LISTO". Si falla pytest, arregla eso ANTES de usar
el arnés: el portero existe justo para no trabajar sobre un proyecto roto.

## 2. Primera sesión: feature de calentamiento (F-001, sin SDD)

F-001 es trivial a propósito (comando `version` en el CLI) para validar el
circuito completo sin ruido.

1. En el chat de Claude Code:
   > Lee CLAUDE.md y actúa como líder. Ejecuta el protocolo y trabaja en F-001.
2. Qué debe pasar (vigílalo la primera vez):
   - Ejecuta `init.sh` y muestra el verde.
   - Crea la rama `feature/F-001-cli-version` desde `dev`.
   - Como `sdd: false`, lanza el implementer directamente.
   - Implementa, escribe un test, commit `F-001 T1: ...`, `init.sh` en verde,
     lanza el reviewer, y marca `done` moviendo el resumen a
     `progress/history.md`.
3. Tú: revisa el diff (`git diff dev...HEAD`), y si está bien:
   ```
   git checkout dev
   git merge --no-ff feature/F-001-cli-version
   git push
   ```

## 3. Ciclo SDD completo (F-002 PLAN_VIGENTE — el caso real)

### Fase A — Especificación
> Actúa como líder y trabaja en F-002.

El líder lanza el spec-author, que crea `specs/F-002-plan-vigente/` con
`requirements.md` (EARS), `design.md` y `tasks.md`, deja la feature en
`spec_ready` y PARA.

### Fase B — Aprobación humana (tu momento clave)
Lee los tres ficheros con calma. Aquí es donde inviertes tu criterio:
- ¿Los requisitos EARS cubren los casos borde (mes de corte, obra sin master
  vigente, versión master cambiada a mitad de año)?
- ¿El design respeta importe_origen/importe_mes y la capa `cierre`?
- Pide cambios en el mismo chat: "En design.md cambia X, añade requisito
  para Y". El spec-author reescribe.

Cuando estés conforme, edita `harness/features.json` (o díselo a Claude):
`"status": "in_progress"`. Y dile:
> F-002 aprobada, continúa.

### Fase C — Implementación y revisión
El implementer ejecuta `tasks.md` en orden, un commit por tarea, y al acabar
el líder lanza el reviewer, que valida trazabilidad requisito→test y deja su
veredicto en `progress/current.md`.

### Fase D — Pruebas locales que la IA no puede hacer sola
Las tareas marcadas `MANUAL (humano)` en tasks.md: normalmente ejecutar
contra tu Postgres local/dev, p. ej.:
```
python main.py run-all --full
```
y validar cifras en Power BI / consultas de contraste. Si algo falla, pega el
log en el chat y el líder relanza al implementer con ese feedback (tu flujo
habitual de tandas, pero dentro del arnés).

### Fase E — Integración
```
git checkout dev
git merge --no-ff feature/F-002-plan-vigente
git push
```
El humano hace merge y push, nunca el agente.

## 4. Despliegue a Azure (F-003 o cuando toque)

1. Rellenar los `TODO_` de `infra/00_vars.ps1` (ACR y host de Postgres).
2. Una sola vez: `.\infra\10_create_rg.ps1`.
3. Por despliegue:
   ```
   .\infra\20_build_image.ps1     # build en ACR con tag fechado rYYYYMMDD-HHmm
   .\infra\30_create_job.ps1      # primera vez (crea el job con secretos)
   .\infra\40_update_job.ps1      # despliegues siguientes
   az containerapp job start -g rg-seguimiento-dev -n caj-datamart-seg   # prueba manual
   ```
4. Recuerda: el `.env` NO viaja a Azure; los secretos van como secrets del
   job. Tags fechados siempre (los Container Apps fijan el digest).

## 5. Mantenimiento del arnés

- **Nuevas features**: añade una entrada a `harness/features.json`
  (id correlativo, `sdd: true` salvo trivialidades) o pídeselo a Claude.
- **Contexto degradado**: si la sesión se alarga (a partir de ~40% de ventana)
  usa `/clear` o abre sesión nueva. El arnés está diseñado para eso: la nueva
  sesión lee `progress/current.md` y retoma sin releer el proyecto.
- **Automejora**: si el reviewer o tú detectáis que un protocolo falla,
  cambiad el `.md` del agente (los agentes proponen, tú apruebas).
- **Azurite**: no aplica a este proyecto (no hay colas). Cuando repliquemos el
  arnés en albaranes/partes, añadiremos a su `init.sh` la comprobación de que
  Azurite está levantado y las colas creadas antes de trabajar.

## 6. Chuleta de prompts

| Quiero...                          | Prompt |
|------------------------------------|--------|
| Empezar sesión                     | "Lee CLAUDE.md, actúa como líder y sigue el protocolo." |
| Trabajar una feature concreta      | "Actúa como líder y trabaja en F-00X." |
| Aprobar una spec                   | "F-00X aprobada, pásala a in_progress y continúa." |
| Rechazar parte de una spec         | "En specs/F-00X/design.md, <cambio>. Regenera y espera mi aprobación." |
| Retomar tras cerrar PyCharm        | "Lee CLAUDE.md y progress/current.md y retoma el trabajo pendiente." |
| Añadir feature                     | "Añade a features.json: <descripción>. sdd=true. No empieces a trabajarla." |
