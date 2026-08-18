<!-- specs/F-023-cierre-operativo-f003/tasks.md -->
# F-023 · Cierre operativo de F-003 — Tareas

Rama: `feature/F-023-cierre-operativo-f003`. Un commit por tarea
(`F-023 Tn: ...`) en las tareas que tocan ficheros; las MANUAL no generan
commit propio salvo el del acta en `progress/impl_F-023.md`.

**Regla de hierro**: ningún agente abre conexión a Azure, a Postgres ni a
`sigrid-api`, ni edita `.env`. Todo lo marcado `MANUAL (humano)` lo ejecuta
el humano con el comando exacto de `requirements.md`, y el implementer solo
**transcribe** el resultado real (comando, salida relevante, hora).

## Fase 0 · Decidir antes de tocar nada

- [ ] **T1**: Cerrar las siete decisiones abiertas de `design.md` §9
      (DA-1 rigor, DA-2 acceso del puesto, DA-3 reglas ajenas, DA-4
      `SIGRID_API_PAGE_SIZE`, DA-5 defecto de `60_create_identity.ps1`,
      DA-6 plan B de las variables del job, DA-7 orden respecto a F-024) y
      anotar cada una con fecha en este `design.md`.
      | **Verificación**: MANUAL (humano) — las siete DA tienen escrito
      «CERRADA <fecha>: opción X».

## Fase A · Invariantes (implementer, sin red ni BBDD)

- [ ] **T2**: Escribir `tests/test_f023_cierre_operativo.py` con los cuatro
      tests de R1–R4, reutilizando los ayudantes de
      `tests/test_f003_infra.py` (`_script`, `_config`, `_env_vars_del_job`)
      en vez de duplicarlos. Antes de darlos por buenos, **fase RED**:
      provocar el fallo de cada uno con una entrada de prueba (un
      `auxBlobs` con ruta, un texto de script con `AUX_EXCEL_*=D:\...`, una
      lista de variables que incluya `SIGRID_API_PAGE_SIZE`) y pegar la
      salida real del fallo en el informe.
      | **Verificación**: `python -m pytest tests/test_f023_cierre_operativo.py -v`
      en verde, y las cuatro trazas RED en `progress/impl_F-023.md`.

- [ ] **T3**: Fotografía del estado inicial, **solo lectura**, para que las
      tareas siguientes sean idempotentes y para poder restaurar: blobs del
      contenedor, roles de plano de datos sobre la cuenta, variables
      `AUX_EXCEL_*` del job desplegado, secretos por **nombre** de los dos
      vaults, reglas de firewall del servidor y línea de `hosts`.
      | **Verificación**: MANUAL (humano) — los comandos de lectura de R5,
      R6, R12 y R18 más:
      `az containerapp job show -g <resourceGroup> -n <job> --query "properties.template.containers[0].env" -o json`
      (sin filtros JMESPath con `?`: rompen contra `az.cmd` en PowerShell
      5.1). Salidas pegadas en el informe. **Si las tres `AUX_EXCEL_*` del
      job NO son URIs de blob → aplicar DA-6 y avisar antes de seguir.**

## Fase B · Bloque 1 · Los Excels en el blob y las verificaciones de F-004

- [ ] **T4**: Subir los tres Excels al contenedor `aux` con los nombres
      exactos de `auxBlobs` (`--auth-mode login`; la cuenta no admite clave
      compartida).
      | **Verificación**: MANUAL (humano) — **R5**: el listado devuelve los
      tres nombres con tamaño > 0.

- [ ] **T5**: Comprobar (y si falta, asignar) el rol de lectura de blobs
      del humano sobre la cuenta, dejando anotada la **lista literal** de
      roles: es la que hay que restaurar en T8.
      | **Verificación**: MANUAL (humano) — **R6**: `az role assignment list`
      sobre el ámbito de la cuenta.

- [ ] **T6**: Verificación 1 de F-004 — `python main.py load-aux` desde el
      puesto con las tres `AUX_EXCEL_*` del `.env` apuntando a las URIs de
      blob. Antes: `pip install -r requirements.txt` y la comprobación de
      que no hay ninguna ejecución del job en `Running`.
      | **Verificación**: MANUAL (humano) — **R7** y **R8**: `SUCCESS` con
      `origen=blob` en los tres ficheros. Un `origen=local` es FALLO, no un
      matiz.

- [ ] **T7**: Verificación 2 de F-004 — ejecución del job con
      `--command python --args "main.py" "load-aux"` y consulta KQL de los
      eventos `aux_file_read`.
      | **Verificación**: MANUAL (humano) — **R9**: tres eventos con
      `"origen": "blob"` y ninguna ruta local. Si la KQL devuelve cero
      filas, `| getschema` antes de concluir nada.

- [ ] **T8**: Verificación 3 de F-004 — prueba negativa: retirar **todos**
      los roles de datos de blob del humano sobre la cuenta (no solo
      `Reader`: `Contributor` incluye lectura), ejecutar `load-aux`, leer el
      mensaje y **restaurar exactamente** los roles de T5.
      | **Verificación**: MANUAL (humano) — **R10** y **R11**: el error
      nombra `Storage Blob Data Reader`, `az login` y la identidad
      gestionada; y después la lista de roles coincide con la de T5 y
      `load-aux` vuelve a dar `SUCCESS`. **La tarea no está hecha sin la
      restauración comprobada.**

## Fase C · Bloque 2 · Retirar las copias viejas de los secretos

- [ ] **T9**: Comprobar las cuatro precondiciones del borrado: secretos
      presentes **por nombre** en el vault del proyecto, ejecución
      `Succeeded` del job posterior a la migración, **soft-delete** activo
      en `kv-albaranes-rs9k2`, y respuesta del humano a «¿lee alguien más
      esos dos secretos de ese vault?».
      | **Verificación**: MANUAL (humano) — **R12** y **R13**. Si el
      soft-delete estuviera desactivado: la feature queda `blocked` y no se
      borra nada.

- [ ] **T10**: Recoger el **OK explícito** del humano para ese borrado
      concreto y citarlo literalmente, con fecha y hora, en
      `progress/impl_F-023.md`.
      | **Verificación**: revisión del reviewer — el acta existe y es
      inequívoca (nombra los dos secretos y el vault).

- [ ] **T11**: Borrar las dos copias en `kv-albaranes-rs9k2`, sin leer
      ningún valor y sin `purge`.
      | **Verificación**: MANUAL (humano) — **R14**: los dos nombres
      desaparecen de `secret list` y aparecen en `secret list-deleted`.
      Prohibidos `secret show` y `secret purge`.

- [ ] **T12**: Comprobar que el job sigue ejecutando después del borrado:
      prueba corta inmediata (`--command python --args "main.py" "check-pg"`)
      y confirmación de la siguiente ejecución nocturna.
      | **Verificación**: MANUAL (humano) — **R15**: las dos `Succeeded`, y
      sin correo de alerta de la nocturna.

## Fase D · Bloque 3 · Limpieza del puesto

- [ ] **T13**: Retirar la línea del fichero `hosts` que fija a mano la
      dirección del servidor de Postgres (consola de administrador) y
      comprobar que el nombre resuelve por DNS y el puesto sigue
      conectando.
      | **Verificación**: MANUAL (humano) — **R16**: `Select-String` sin
      resultados, `Resolve-DnsName` responde y `check-pg` devuelve la
      versión del servidor.

- [ ] **T14**: **Puerta**: confirmar que la Fase C de F-024 (T17–T20) está
      completa —o que el humano acepta recrear la regla cuando la
      necesite—, antes de tocar el firewall.
      | **Verificación**: MANUAL (humano) — **R17**: estado de F-024
      anotado en el informe, con la decisión DA-7 aplicada.

- [ ] **T15**: Retirar las reglas `datamart-puesto-*` de
      `psql-albaranes-rs9k2`, dejando intactas la regla del entorno del job
      y la de servicios de Azure. Antes, confirmar con `--help` el flag del
      servidor que admite la versión de `az` instalada.
      | **Verificación**: MANUAL (humano) — **R18**: el listado final no
      contiene ninguna `datamart-puesto-*` y sí la del job. ⚠ Escritura en
      un recurso de `albaranes`: autorización expresa, la ejecuta el humano.

- [ ] **T16**: Decidir sobre las dos reglas antiguas ajenas (`ClientPgris`,
      `FirewallIPAddress_2026-6-16`): borrarlas **solo** con confirmación
      escrita de que nadie más las usa; si no, dejarlas y anotar por qué.
      | **Verificación**: MANUAL (humano) — **R19**: respuesta literal del
      humano y listado posterior.

- [ ] **T17**: Anotar la decisión sobre `SIGRID_API_PAGE_SIZE` (qué valor
      se queda en el `.env` del puesto y por qué), dejando constancia de
      que el job no depende de esa variable.
      | **Verificación**: **R20** — la mitad automática la fija el test de
      R4 (T2); la otra mitad, MANUAL (humano): decisión escrita en el
      informe y en `progress/current.md`. Ningún agente edita `.env` ni los
      `.bak`.

## Fase E · Documentación y cierre

- [ ] **T18**: Actualizar `infra/README.md`: comandos y resultados de las
      tres verificaciones de F-004, el paso 8 bis corregido (las copias
      viejas ya no son la vuelta atrás; lo es el soft-delete del vault de
      origen), el flag correcto del comando de firewall y la subsección
      nueva «Volver a autorizar el puesto cuando haga falta».
      | **Verificación**: revisión del reviewer (C3) — **R21**: cada
      afirmación contrastable contra lo anotado en el informe.

- [ ] **T19**: Actualizar `azure-apps/datamart_seg_anual.md` **en el mismo
      trabajo**: origen real de los Excels (contenedor `aux`, identidad
      gestionada, rol de lectura), sección «Dónde viven los secretos» (por
      **nombre**, nunca valores) y corrección del encabezado y de las dos
      frases que siguen diciendo que el proyecto no está desplegado.
      Commit propio en el repositorio `azure-apps`, no en esta rama.
      | **Verificación**: revisión del reviewer (C3) — **R21**: el
      documento no contiene ningún secreto, IP, ID de suscripción ni
      tenant, y no contradice la realidad verificada.

- [ ] **T20**: Cerrar la trazabilidad de F-003: en
      `specs/F-003-infra-caj/tasks.md`, marcar T23–T26 con su fecha y
      añadir marcadas las tres verificaciones heredadas de F-004 con su
      resultado real.
      | **Verificación**: revisión del reviewer (C4) — **R22**.

- [ ] **T21**: Escribir `progress/impl_F-023.md` completo (evidencias,
      trazas RED, actas de las trece verificaciones MANUAL, alcance de
      cobertura y salida real de la campaña de mutación aunque sea de cero
      mutantes) y actualizar `progress/current.md` con el estado de F-023 y
      de F-003 y las decisiones que queden abiertas.
      | **Verificación**: revisión del reviewer contra `CHECKPOINTS.md`.

- [ ] **T22**: Ejecutar `bash harness/init.sh` en verde.
      | **Verificación**: **R23** — código de salida 0.
