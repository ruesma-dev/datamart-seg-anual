<!-- progress/explore_F-006_contexto.md -->
# F-006 · Exploración del contexto de decisión (2026-08-20)

> Informe del subagente explorador (solo lectura). Lo guarda el líder porque el
> subagente no tenía herramientas de escritura.

## 1. Fichas relacionadas

- **F-006** · `pending`, prioridad **1**, `sdd=true`, rama `feature/F-006-mcp-azure`.
  **No existe `specs/F-006-mcp-azure/`.** Alcance en ESTE repo: rol de solo
  lectura, regla de firewall y **el diccionario semántico del datamart**.
- **F-030** · Reglas de negocio compartidas. `pending`, prioridad 12, rigor
  `documental`, `sdd=false`. Reglas como **guía en lenguaje natural**, en **su
  propio repositorio con dueño en Negocio**, publicadas por el MCP como
  **prompt**. Cinco AC: repo propio sin copias; procedimiento de planificación
  temporal escrito; publicación como prompt; **circuito de vuelta** de las
  correcciones con aprobación del dueño; separar regla-guía de regla codificada.
- **F-034** · Power BI deja de leer de local. **Dato clave: hoy
  `mcp_sigrid_dm_ro` es el ÚNICO rol de lectura y ve TODOS los esquemas,
  incluidos `raw` y `stg`.** Propone `pbi_sigrid_dm_ro` acotado.
- **F-032** · Limpieza: retirar copias viejas de secretos (incluye
  `pg-mcp-sigrid-dm-ro`) y las reglas de firewall del puesto, al final.
- **F-025** (ventana de negocio, spec existe) y **F-035** (medir las cuatro
  palancas) quedan por detrás de F-006 desde el 2026-08-20.
- **F-024** (done) dejó `_meta.v_frescura` y `_meta.v_raw_state` legibles por el
  rol del MCP: el consumidor puede saber si lo que ve es de esta noche.

## 2. Decisiones abiertas (`progress/decisiones_abiertas.md`)

- **D1** · Acceso de red al Postgres (público+firewall vs private endpoint+VPN).
  Abierta. Cero private endpoints en la suscripción; P2S sin configurar.
- **D4** · Dónde vive el MCP: **cerrada** → `PycharmProjects/mcp-bbdd`.
- **D8** · Dónde se persiste una planificación hecha por la IA. **Abierta.**
  El MCP es solo lectura por diseño; persistir es escritura. Tres salidas sin
  recomendar: no persistir / tabla propia en el datamart / otro servicio con su
  permiso. **Lo que no se hará: relajar el MCP para que escriba.**
- **D10** · Por dónde entra Power BI (Desktop vs Service). Abierta.
- **D11** · El acceso por regla de IP ya no funciona: la IP del puesto rota por
  CGNAT. **Resuelta en parte** con una regla única sin fecha reescrita antes de
  cada tanda. Tumba la opción A de D10. Fondo sin decidir.

## 3. Rastro operativo del MCP en `progress/`

- `current.md:90-104` — F-006 es lo primero; leer ficha → F-030 → D8.
- `current.md:940-956` — frontera de seguridad medida: `mcp_sigrid_dm_ro` no
  puede escribir; **sí puede conectarse a `albaranes`** (riesgo aceptado) pero
  no leer sus datos; por `pg_catalog` ve 14 nombres de tabla y 450 de columna.
- `current.md:226,442` — vistas de `_meta` legibles por el rol del MCP,
  verificado con `has_table_privilege`. **Lo único no probado: la conectividad
  de punta a punta del MCP.**
- `current.md:587`, `:1616`, `history.md:152-157` — hay que ejecutar
  `apply-grants` tras cada despliegue: el `DROP VIEW ... CASCADE` se lleva los
  GRANT. Sin eso el MCP perdería el acceso cada noche.
- `current.md:680` — **IP de salida del entorno Container Apps: `68.221.221.85`**,
  autorizada como regla `caj-datamart-seg-dev`. Es el patrón que seguiría el MCP.

## 4. Ecosistema (`azure-apps/`)

- `datamart_seg_anual.md` describe el MCP aún como «cliente de escritorio».
  Expone `mart.v_pbi_*` a Power BI y `_meta.v_*` a ambos. No expone API HTTP.
- **No hay documento propio de `mcp-bbdd` en `azure-apps/`**: hueco a cubrir.
  `sigrid_api.md:847` ya lo lista como consumidor indirecto vía datamart.
- **`albaranes`** (misma instancia `psql-albaranes-rs9k2`, base `albaranes`,
  schema `public`): albaranes de proveedor con `obra_codigo`/`obra_nombre`
  (`albaran_documents_merge`), líneas con `codigo_imputacion`, **contratos
  Sigrid del proveedor+obra** (`albaran_contratos_merge`,
  `albaran_contrato_lines_merge` con `codigo_partida`) y valoración IA
  (`albaran_valuations`, `albaran_line_valuations`). Es la fuente natural del
  «coste real de proveedor por obra y partida». Multi-base sería barato: mismo
  servidor, un rol de lectura más.
- **`partes`**: partes diarios por obra (mano de obra). Mismo servidor.
- **«Comparativos»: no existe proyecto ni tabla aquí.** Vive en Sigrid
  (`sigrid_api.md` §9.6, vía `ctr.comide → com.ide`) y este datamart **no lo
  ingiere**. En el portal es solo un informe Power BI.

## 5. Patrón de despliegue heredable (`docs/ARCHITECTURE.md`)

Container Apps Job en `rg-datamart-seg-dev`, entorno `cae-datamart-seg-dev`
**sin VNet a propósito, para tener IP de salida estática**; ACR compartido
`acralbaranesdev` con tags fechados; Key Vault propio `kv-datamart-seg-dev` con
RBAC y secretos por referencia; identidad gestionada `id-datamart-seg-dev` con
tres permisos exactos; Log Analytics con alerta de frescura.

## Los tres cabos que hereda un MCP en cloud

1. `mcp_sigrid_dm_ro` es **demasiado amplio** (ve `raw` y `stg`) y hoy es el
   único rol de lectura. F-034 quiere separarlo.
2. El firewall es de un **servidor compartido**: la vía limpia es autorizar la
   **IP de salida estática** del entorno del MCP, no perseguir IPs de puesto.
3. **D8 sin decidir** condiciona si el MCP sigue siendo solo lectura, y
   **F-030 + el diccionario semántico** son prerrequisitos funcionales.
