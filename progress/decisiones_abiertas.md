<!-- progress/decisiones_abiertas.md -->
# Decisiones abiertas · bloque Azure

Registro de las decisiones que el humano tiene que cerrar **antes** de que el
`spec-author` escriba las specs de F-004, F-005, F-003 y F-006. Ninguna
bloquea el trabajo ya terminado; todas bloquean el diseño del despliegue.

Estado: **pendientes de revisión por el humano** (aplazadas el 2026-08-08 a
petición suya, tras cerrar la integración de F-001 y el mantenimiento).

Cuando se cierre una decisión, anótala aquí con su fecha y bórrala de la
lista de pendientes de la feature en `harness/features.json`.

---

## D1 · Acceso de red al Postgres de Azure — afecta a F-005, F-006

La más cara de cambiar a posteriori. El MCP corre en el puesto del usuario,
fuera de Azure, así que el Flexible Server tiene que ser alcanzable desde
fuera.

- **Opción A — acceso público con reglas de firewall por IP.** Rápido de
  montar. Expone el endpoint a Internet y exige que las IPs de salida de la
  oficina sean fijas.
- **Opción B — private endpoint + VPN.** Sin exposición pública. Más trabajo
  de red y el MCP solo funciona con la VPN levantada.

Sin cerrar esto no se puede diseñar F-005 ni verificar F-006.

> **Material nuevo (2026-08-08, F-008).** El diseño de acens en
> `docs/referencia/02_azure_landing_zone_acens.md` describe un hub&spoke en
> Spain Central con Azure Firewall (Basic), **VPN Site-to-Site permanente
> contra la red de la sede** y VPN SSL para puestos. La opción B ya no
> implica montar la VPN desde cero. Ojo: no se provisionan NSGs, el filtrado
> es del firewall central.

## D2 · Qué Azure Container Registry usar — afecta a F-003

`infra/00_vars.ps1` tiene `$ACR = "TODO_acr_existente"` con el comentario
«p.ej. el ACR compartido de albaranes», pero sin nombre real. Hace falta el
nombre del registro y confirmar que el Container Apps Job puede tirar de él.

## D3 · ¿Solo `dev`, o también producción? — afecta a F-003, F-005

Todo apunta hoy a `rg-seguimiento-dev`. Si va a haber un entorno productivo,
los scripts de `infra/` deben parametrizar el entorno desde el principio en
vez de duplicarse después.

> **Material nuevo (2026-08-08, F-008).** El diseño de acens ya contempla
> división por entorno **DEV/STA/PRO**, con rangos de red reservados para PRO
> y para DEV/POC, y despliegue por Terraform vía pipelines de Azure DevOps.
> Apunta a parametrizar `infra/` por entorno desde el principio.

## D4 · Dónde vive el MCP — afecta a F-006

El MCP que hoy consulta el Postgres local **no está en este repositorio**
(verificado por búsqueda en el árbol). Hay que localizar su repositorio o su
configuración para poder repuntarlo y verificar que sus consultas siguen
funcionando contra Azure.

## D5 · Destino de los Excels auxiliares — afecta a F-004

`LoadExcelAuxStep` lee `TipoPartida.xlsx`, `TipoCoste.xlsx` y
`mapeo_proporcionales.xlsx` de rutas locales o de red vía `AUX_EXCEL_*`. En
un contenedor esas rutas no existen y `run-all` falla en el segundo paso.

Recomendación: llevarlos a Azure Blob Storage y que el step lea
indistintamente de ruta local o de blob. Falta confirmar la cuenta de
almacenamiento y quién mantiene esos ficheros.

> **Parcialmente cerrada el 2026-08-08.** El humano confirma que **los Excels
> auxiliares se suben a Azure**. El mecanismo de subida para gente de negocio
> (app web o sistema equivalente) se saca a feature propia, **F-010**, que
> depende de F-007; F-004 no la necesita, le basta con leer del blob aunque
> el fichero se suba a mano.
>
> Sigue pendiente: **qué storage account** concreta —debería salir del
> inventario de F-009— y **quién mantiene** los ficheros.

## D6 · Horario del job nocturno y avisos de fallo — afecta a F-003

`infra/00_vars.ps1` propone `0 3 * * *` (03:00 UTC, que en horario de verano
español son las 05:00). Falta confirmar la hora y decidir si se quiere aviso
—correo u otro canal— cuando el job falle. Sin aviso, un fallo nocturno pasa
inadvertido hasta que alguien mire Power BI.

---

## Decisiones ya cerradas

- **2026-08-08 · Backlog priorizado.** Aprobado el orden F-001, F-004, F-005,
  F-003, F-006, F-002, F-007. El bloque Azure pasa por delante de
  PLAN_VIGENTE.
- **2026-08-08 · Subagentes.** El humano confirma la autorización permanente
  de subagentes recogida en `CLAUDE.md`.
