<!-- specs/F-023-cierre-operativo-f003/tasks.md -->
# F-023 · Cierre operativo de F-003 — Tareas

Rama: `feature/F-023-cierre-operativo-f003`. Rigor **`critico`** (DA-1,
cerrada el 2026-08-18). Un commit por tarea (`F-023 Tn: ...`) en las tareas
que tocan ficheros; las MANUAL no generan commit propio salvo el del acta en
`progress/impl_F-023.md`.

**Regla de hierro**: ningún agente abre conexión a Azure, a Postgres ni a
`sigrid-api`, ni edita `.env`. Todo lo marcado `MANUAL (humano)` lo ejecuta
el humano con el comando exacto de `requirements.md`, y el implementer solo
**transcribe** el resultado real (comando, salida relevante, hora).

**Regla del acta (rigor `critico`)**: las dos tareas que borran algo —T11
(secretos) y T15 (reglas de firewall)— no están hechas sin el **OK del
humano citado literalmente**, con fecha y hora, **antes** de la evidencia
del borrado.

**Orden cerrado (DA-7)**: la Fase D no empieza hasta que la Fase C de F-024
(T17–T20 de aquella feature) esté completa. T14 es la puerta y no se salta.

## Fase 0 · Decidir antes de tocar nada

- [x] **T1** (2026-08-18): Cerradas las siete decisiones abiertas de
      `design.md` §9 — el humano respondió «acepto la recomendación» en las
      siete: **DA-1** rigor `critico`; **DA-2** opción A (se retiran todas
      las `datamart-puesto-*` y se recrea bajo demanda con el comando del
      README); **DA-3** no se borran `ClientPgris` ni
      `FirewallIPAddress_2026-6-16`; **DA-4** `SIGRID_API_PAGE_SIZE` solo
      afecta al `.env` del puesto y `.env.example` no se toca; **DA-5** el
      defecto de `60_create_identity.ps1` va al backlog, con mitigación de
      esperar y repetir; **DA-6** opción A (`az containerapp job update
      --set-env-vars` a mano, documentado, y la carencia del guion al
      backlog); **DA-7** se acepta el orden respecto a F-024.
      | **Verificación**: `design.md` §9 se titula «Decisiones cerradas
      (2026-08-18, por el humano)» y las siete llevan escrito
      «CERRADA 2026-08-18» con su efecto. Hecho por el spec-author; el
      líder aplica `rigor: critico` en `harness/features.json`.

## Fase A · Invariantes (implementer, sin red ni BBDD)

- [ ] **T2**: Escribir `tests/test_f023_cierre_operativo.py` con los
      **cinco** tests de R1–R4, reutilizando los ayudantes de
      `tests/test_f003_infra.py` (`_script`, `_config`, `_env_vars_del_job`)
      en vez de duplicarlos. Antes de darlos por buenos, **fase RED**
      (obligatoria en rigor `critico`): provocar el fallo de **cada uno** de
      los cinco con la entrada de prueba que indica `design.md` §11 —en una
      copia aislada, **nunca sobre el árbol real**— y pegar la salida real
      del fallo en el informe.
      | **Verificación**: `python -m pytest tests/test_f023_cierre_operativo.py -v`
      en verde, y las **cinco** trazas RED en `progress/impl_F-023.md`.

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
      job NO fueran URIs de blob** → avisar y aplicar el plan cerrado de
      **DA-6**: corregirlas con
      `az containerapp job update --set-env-vars ...` (comando completo en
      `design.md` §9), comprobar después con `job show` que siguen ahí las
      demás variables y la referencia a secreto de `PG_PASSWORD`,
      documentarlo en el README (T18) y dejar la ficha de la carencia para
      el backlog (T22). **Ni se recrea el job ni se toca
      `infra/env/dev.json`.**

## Fase B · Bloque 1 · Los Excels en el blob y las verificaciones de F-004

- [ ] **T4**: Subir los tres Excels al contenedor `aux` con los nombres
      exactos de `auxBlobs` (`--auth-mode login`; la cuenta no admite clave
      compartida).
      | **Verificación**: MANUAL (humano) — **R5**: el listado devuelve los
      tres nombres con tamaño > 0.

- [ ] **T5**: Comprobar (y si falta, asignar) el rol de lectura de blobs
      del humano sobre la cuenta, dejando anotada la **lista literal** de
      roles: es la que hay que restaurar en T8. Si la lectura no refleja
      todavía un rol recién creado, **esperar y repetir** (DA-5): es
      propagación de RBAC, no un fallo.
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
      mensaje y **restaurar exactamente** los roles de T5. Entre retirar y
      probar, y entre restaurar y comprobar, **esperar a la propagación de
      RBAC** (DA-5).
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
      | **Verificación**: revisión del reviewer — **acta** exigida por el
      rigor `critico`: existe, es inequívoca (nombra los dos secretos y el
      vault) y es **anterior** al borrado de T11.

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

> **Esta fase entera va después de la Fase C de F-024** (DA-7). T13 (el
> `hosts`) puede hacerse antes porque no quita acceso; **el firewall, no**.

- [ ] **T13**: Retirar la línea del fichero `hosts` que fija a mano la
      dirección del servidor de Postgres (consola de administrador) y
      comprobar que el nombre resuelve por DNS y el puesto sigue
      conectando.
      | **Verificación**: MANUAL (humano) — **R16**: `Select-String` sin
      resultados, `Resolve-DnsName` responde y `check-pg` devuelve la
      versión del servidor.

- [ ] **T14**: **Puerta (DA-7)**: confirmar que la Fase C de F-024
      (T17–T20) está **completa** antes de tocar el firewall. No hay
      alternativa: si no lo está, la Fase D se detiene aquí y se retoma
      cuando lo esté.
      | **Verificación**: MANUAL (humano) — **R17**: estado de F-024
      anotado en el informe (`harness/features.json` y `progress/current.md`
      como fuente).

- [ ] **T15**: Retirar **todas** las reglas `datamart-puesto-*` de
      `psql-albaranes-rs9k2` —el puesto no conserva ninguna vigente
      (DA-2, opción A)—, dejando intactas la regla del entorno del job y la
      de servicios de Azure. Antes, confirmar con `--help` el flag del
      servidor que admite la versión de `az` instalada, y recoger el **OK
      explícito** del humano para este borrado concreto.
      | **Verificación**: MANUAL (humano) — **R18**: el listado final no
      contiene **ninguna** `datamart-puesto-*` y sí la del job. ⚠ Escritura
      destructiva en un recurso de `albaranes`: **acta** con el OK citado
      (rigor `critico`), autorización expresa y la ejecuta el humano.

- [ ] **T16**: Dejar **sin tocar** las dos reglas antiguas ajenas
      (`ClientPgris`, `FirewallIPAddress_2026-6-16`) y anotar en el informe
      que se conservan **a propósito** (DA-3): son de `albaranes` y
      anteriores a este proyecto. No se pregunta, no se borra.
      | **Verificación**: MANUAL (humano) — **R19**: las dos aparecen
      intactas en el listado final de T15, y el informe dice por qué.

- [ ] **T17**: Anotar la decisión sobre `SIGRID_API_PAGE_SIZE` (qué valor
      se queda en el `.env` del puesto y por qué), dejando constancia de
      que el job no depende de esa variable y de que el asunto **queda
      cerrado** (DA-4).
      | **Verificación**: **R20** — la mitad automática la fija el test de
      R4 (T2); la otra mitad, MANUAL (humano): decisión escrita en el
      informe. **`.env.example` no se toca**; ningún agente edita `.env` ni
      los `.bak`.

## Fase E · Documentación y cierre

- [ ] **T18**: Actualizar `infra/README.md`: comandos y resultados de las
      tres verificaciones de F-004, el paso 8 bis corregido (las copias
      viejas ya no son la vuelta atrás; lo es el soft-delete del vault de
      origen), el flag correcto del comando de firewall, la subsección
      nueva **«Volver a autorizar el puesto cuando haga falta»** (comando
      completo de R18, nombre datado, borrado al terminar, variante de
      rango) y la subsección nueva **«Cambiar una variable de entorno de un
      job vivo»** (comando de DA-6 y comprobación posterior de que las
      referencias a secretos siguen en su sitio).
      | **Verificación**: revisión del reviewer (C3) — **R21**: cada
      afirmación contrastable contra lo anotado en el informe, y los dos
      comandos nuevos completos y ejecutables.

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

- [ ] **T21**: Escribir `progress/impl_F-023.md` completo: evidencias con
      los cuatro números, las **cinco** trazas RED, las **actas de las
      dieciséis verificaciones MANUAL** (comando, salida real y hora), las
      dos actas de borrado con el OK citado (T10 y T15), el alcance de
      cobertura con su número real y la salida real de la campaña de
      mutación. La campaña se ejecuta con `python -m harness.mutacion` y
      genera `progress/mutacion_F-023.md`: dará **cero mutantes** porque el
      diff no lleva código de producción, y **cero es un dato que se pega,
      no un «no aplica»**. Actualizar `progress/current.md` con el estado de
      F-023 y de F-003.
      | **Verificación**: revisión del reviewer contra `CHECKPOINTS.md`
      (C4 bis, nivel `critico`): fase RED, cobertura, mutación con totales
      recalculados por el reviewer, cero supervivientes y las MANUAL con
      resultado real.

- [ ] **T22**: Dejar en el informe la **ficha de los dos defectos que van
      al backlog**, copiada o referenciada sin ambigüedad desde
      `design.md` §9: (1) `60_create_identity.ps1` verifica los roles antes
      de que RBAC propague y lanza un `throw` falso (DA-5); (2) los guiones
      de despliegue no saben cambiar una variable de entorno de un job vivo
      —`80_create_job.ps1` se niega si el job existe y `85_update_job.ps1`
      solo cambia la imagen— (DA-6). **Ningún agente edita
      `harness/features.json`**: el alta la hace el líder.
      | **Verificación**: revisión del reviewer — **R23**: las dos fichas
      existen y son accionables sin volver a investigar el código.

- [ ] **T23**: Ejecutar `bash harness/init.sh` en verde.
      | **Verificación**: **R24** — código de salida 0.
