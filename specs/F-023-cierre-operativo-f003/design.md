<!-- specs/F-023-cierre-operativo-f003/design.md -->
# F-023 · Cierre operativo de F-003 — Diseño técnico

## 1. Naturaleza de la feature: casi nada es código

F-023 no añade capacidad al ETL. Todo lo que hace falta ya existe y está
probado: F-004 construyó la lectura de blobs con `DefaultAzureCredential`,
F-003 creó la cuenta, el contenedor, el vault, la identidad y el job. Lo
que falta es **ejecutar**: poner los ficheros donde el job los espera,
comprobar que se leen de verdad, retirar los duplicados de seguridad que ya
sobran y recoger el andamiaje del puesto.

Por eso el reparto es deliberadamente asimétrico:

| Bloque | Naturaleza | Quién lo ejecuta |
|---|---|---|
| 0 · invariantes (R1–R4) | Tests nuevos, sin red ni BBDD | El implementer |
| 1 · Excels y verificaciones de F-004 (R5–R11) | Operación Azure | **MANUAL (humano)** |
| 2 · secretos duplicados (R12–R15) | Operación Azure destructiva | **MANUAL (humano)**, con OK explícito |
| 3 · limpieza del puesto (R16–R20) | Operación puesto + Azure | **MANUAL (humano)** |
| 4 · documentación y cierre (R21–R23) | Markdown y `init.sh` | El implementer |

El implementer **no abre ninguna conexión a Azure, a Postgres ni a
`sigrid-api`**. Escribe tests y documentación, y transcribe a
`progress/impl_F-023.md` los resultados reales que el humano le pase de
cada verificación MANUAL: comando, salida relevante y hora.

## 2. Hallazgo que corrige la premisa de la feature

La `description` de F-023 en `harness/features.json` dice que hay que
«cambiar las `AUX_EXCEL_*` de `infra/env/dev.json` a URIs de blob (hoy
apuntan a rutas locales de OneDrive)». **Leído el árbol, eso no es cierto**:

- `infra/env/dev.json` **no tiene** claves `AUX_EXCEL_*`. Tiene
  `storageAccount`, `auxContainer` y `auxBlobs` (tres nombres de fichero).
- `infra/80_create_job.ps1` §4 compone
  `$baseAux = "https://{0}.blob.core.windows.net/{1}"` y de ahí las tres
  variables del contenedor. El job desplegado el 2026-08-17 se creó con ese
  script.
- Las rutas de OneDrive viven en el **`.env` del puesto** (no versionado),
  corregidas a mano el 2026-08-16 (`progress/current.md`).

**Consecuencia de diseño**: no hay cambio de configuración que hacer en el
repositorio. Lo que sí falta es (a) **verificar** contra Azure que el job
desplegado tiene realmente esas tres variables como URIs de blob, y (b)
**fijar el invariante con tests** para que la premisa no pueda volverse
verdadera por descuido. Si (a) revelara que el job desplegado no las tiene,
se aplica **DA-6**.

## 3. Ficheros a crear

| Ruta | Qué contiene |
|---|---|
| `tests/test_f023_cierre_operativo.py` | Los cuatro tests de R1–R4. Sin red, sin BBDD, sin Azure: leen `infra/env/dev.json`, `infra/*.ps1` y el árbol del paquete, igual que hace `tests/test_f003_infra.py`. |
| `progress/impl_F-023.md` | Informe del implementer: evidencias, y el **acta de cada verificación MANUAL** con comando, salida real y hora. Es la única evidencia que verá el reviewer de los bloques 1–3. |

### Tests, uno por uno

- `test_f023_r1_las_aux_excel_del_job_son_uris_de_blob` — parsea
  `80_create_job.ps1`, localiza las tres asignaciones `AUX_EXCEL_*=` y
  comprueba que cada valor se compone de `$baseAux` y de
  `$CFG.auxBlobs.<clave>`, y que `$baseAux` se construye con
  `$CFG.storageAccount`, `$CFG.auxContainer` y el sufijo
  `blob.core.windows.net`. Reutiliza los ayudantes `_script()` / `_config()`
  de `tests/test_f003_infra.py` (importados, no copiados).
- `test_f023_r1_ninguna_aux_excel_del_job_lleva_ruta_local_ni_sas` — control
  negativo del anterior: ninguna de las tres líneas contiene `:\`, `\\`,
  `~`, `OneDrive` ni `?`.
- `test_f023_r2_los_tres_auxblobs_son_nombres_de_fichero_xlsx` — sobre
  **todos** los ficheros de `infra/env/*.json` (no solo `dev`), los tres
  valores de `auxBlobs` terminan en `.xlsx`, no contienen `/`, `\`, `:`,
  `?` ni `~`, y coinciden con su forma recortada (`strip()`): el espacio
  colado ya rompió las rutas del `.env` el 2026-08-16.
- `test_f023_r3_ni_el_codigo_ni_infra_mencionan_rutas_de_onedrive` — barrido
  de `etl_sigrid/`, `config/`, `main.py` e `infra/` (`*.ps1` y `env/*.json`)
  buscando `OneDrive`, `tablas_auxiliares` y `Documentos`. **Alcance
  acotado a propósito**: `progress/`, `specs/`, `BACKLOG.md` y `docs/`
  quedan fuera porque ahí esas palabras son historia legítima y el test
  sería un falso positivo permanente (la lección de
  `test_f005_r21_barrido_de_secretos`, que se puso rojo por una ruta larga
  en un documento).
- `test_f023_r4_el_job_no_fija_el_tamano_de_pagina_de_la_api` — la lista de
  variables que `80_create_job.ps1` inyecta **no** contiene
  `SIGRID_API_PAGE_SIZE`; reutiliza `_env_vars_del_job()` de
  `test_f003_infra.py`.

## 4. Ficheros a modificar

| Ruta | Qué cambia |
|---|---|
| `infra/README.md` | §«Verificaciones heredadas de F-004»: los comandos exactos de R5–R10 y el resultado (fecha) de cada una. §3 «Paso 8 bis»: el párrafo «las copias viejas no se borran todavía» pasa a decir que **se retiraron** (fecha) y que la vuelta atrás es el soft-delete del vault de origen. §2 «Autorizar la IP del job»: el flag del servidor confirmado con `--help` (defecto anotado en `progress/current.md`) y una subsección nueva **«Volver a autorizar el puesto cuando haga falta»** con el comando de creación y el criterio de borrarla al terminar. |
| `azure-apps/datamart_seg_anual.md` | Fila de «Qué consume» de los Excels: dejan de ser un *stub*; se leen del contenedor `aux` de la cuenta del proyecto por identidad gestionada con `Storage Blob Data Reader`, y sus URIs se componen en `infra/env/dev.json`. Sección nueva **«Dónde viven los secretos»**: solo el Key Vault del proyecto, por **nombre** (jamás un valor), y constancia de que ya no hay copia en el vault de `albaranes`. Corrección del encabezado «Estado: EN LOCAL, sin desplegar» y de las dos frases «hoy no existe ningún Container Apps Job» / «hoy: PostgreSQL local del puesto», que llevan desde el 2026-08-08 contradiciendo la realidad. |
| `specs/F-003-infra-caj/tasks.md` | T23–T26 marcadas `[x]` con su fecha, y las tres verificaciones de F-004 añadidas como tareas marcadas con su resultado (R22). |
| `progress/current.md` | Estado de F-023 y de F-003 al cerrar, decisiones abiertas que queden y el puntero al informe. |

**`azure-apps/` es otro repositorio**: se edita en su ruta
(`C:\Users\pgris\PycharmProjects\azure-apps`) y lleva **su propio commit**,
no entra en la rama de esta feature. El humano tiene el remoto de
`azure-apps` en baja prioridad, así que basta con el commit local.

## 5. Ficheros y recursos que NO se tocan

- **La carga de los Excels a `aux.*`: es F-013.** Aquí no se crea ninguna
  tabla `aux.*`, no se escribe ni una fila y no se decide ningún modelo
  destino. `load-aux` **lee y valida**; que su docstring diga «(pendiente)»
  es correcto y se queda como está.
- **`infra/env/dev.json`**: no cambia. Ya declara lo correcto (§2). Solo se
  tocaría bajo DA-6, y entonces la spec se reabre.
- **`etl_sigrid/`, `config/`, `main.py`**: ni una línea de producción. Si
  una verificación MANUAL destapa un defecto de código (caso típico: el
  mensaje de permisos de R11), **no se parchea aquí**: se anota y se abre
  feature.
- **`.env`, `.env.azure.bak`, `.env.local.bak`**: son del humano y están
  prohibidos para los agentes. Las URIs de blob de R7 las escribe él.
- **`harness/features.json`**: el cambio de `sdd` y de `status` (y el de
  `rigor`, si acepta DA-1) lo hace el líder tras la aprobación.
- **`80_create_job.ps1` y el resto de `infra/*.ps1`**: no se modifican. El
  job desplegado no se recrea ni se reprograma; su `cron`, su
  `replicaTimeoutSeconds` y sus secretos se quedan como están.
- **En `kv-albaranes-rs9k2`, todo lo que no sean los dos secretos del
  datamart.** Ni se listan con detalle ni se leen.
- **En `psql-albaranes-rs9k2`**: nada a nivel de servidor (parámetros,
  autenticación, almacenamiento), y de las reglas de firewall solo las
  `datamart-puesto-*`; la del entorno del job y la de servicios de Azure se
  quedan (R18), y las dos ajenas solo si el humano lo confirma (R19).
- **F-024 Fase C**: no se ejecuta desde aquí. F-023 depende de ella (§7),
  no la sustituye.

## 6. Capa hexagonal y SQL

**Ninguna.** No hay clases ni funciones nuevas, no hay SQL nuevo, no se
crea ni se altera ningún esquema. Lo único que se añade al paquete Python
es un fichero de tests, que no pertenece a `domain`, `application` ni
`infrastructure`: vive en `tests/` y verifica artefactos de despliegue,
igual que `tests/test_f003_infra.py`.

## 7. Orden de ejecución (no es estético: es funcional)

```
   [tests R1–R4]                     (implementer, sin red)
        │
        ▼
   Bloque 1  ── subir Excels → roles → verificación 1 → verificación 2 → verificación 3 (+restaurar rol)
        │        exige: firewall del puesto VIVO (load-aux abre Postgres)
        ▼
   Bloque 2  ── precondiciones → OK del humano → borrado → job sigue OK
        │        exige: ejecución correcta del job (ya la hay, 18-ago)
        ▼
   [F-024 Fase C, T17–T20]           ← se ejecuta desde el puesto
        │
        ▼
   Bloque 3  ── hosts → (esperar) → firewall del puesto → decisión page_size
        │        el firewall va AL FINAL: retirarlo antes deja al humano sin acceso
        ▼
   Bloque 4  ── README + azure-apps + tasks.md de F-003 + init.sh verde
```

Tres dependencias duras que conviene tener escritas porque son fáciles de
romper por prisa:

1. **`load-aux` necesita Postgres**, no solo el blob (abre ejecución en
   `_meta` antes de leer). Sin regla de firewall del puesto, R7 y R10
   fallan por una razón que no tiene nada que ver con lo que se está
   probando.
2. **`load-aux` marca `ABORTED` las filas `RUNNING`** (F-024). Ejecutarlo
   con el job en marcha corrompe la contabilidad de esa ejecución y puede
   cerrar su puerta de coherencia. De ahí la comprobación obligatoria de
   R8.
3. **La verificación 3 retira permisos y hay que devolverlos.** Es el único
   paso de la feature que deja el entorno peor si se interrumpe a la mitad.
   Va emparejado con su restauración en la misma tarea, y la tarea no está
   hecha hasta que `load-aux` vuelve a dar `SUCCESS`.

## 8. Límite de microservicio

Se ha evaluado, porque dos de los tres bloques tocan recursos que **no son
de este proyecto**:

- `kv-albaranes-rs9k2` y `psql-albaranes-rs9k2` son de `albaranes`. Lo que
  F-023 hace ahí es **retirar la huella que este proyecto dejó** (dos
  secretos que nacieron ahí por falta de vault propio, y unas reglas de
  firewall para el puesto). No se añade responsabilidad nueva: se devuelve
  el recurso a su estado. **No procede extraer nada a otro microservicio**;
  procede el protocolo que ya rige el repositorio: autorización expresa del
  humano, recurso a recurso, y él ejecuta.
- El único candidato real a servicio propio que aparece de refilón es
  **subir y mantener los Excels sin pasar por un técnico**, y ya está
  reconocido como **F-010**. F-023 sube los ficheros **a mano y una vez**,
  que es exactamente lo que F-004 declaró suficiente («F-004 no depende de
  F-010: basta con que el ETL lea del blob, aunque el fichero se suba a
  mano»). Nada de lo que se hace aquí prejuzga el diseño de F-010.
- Se comprobó que **ningún documento de `azure-apps/` menciona
  `kv-albaranes-rs9k2`** y que `albaranes.md` no habla de los secretos del
  datamart: por tanto el borrado del bloque 2 **no obliga a actualizar el
  documento de otro proyecto**, solo el propio (R21).

## 9. Decisiones abiertas (las cierra el humano antes de implementar)

- **DA-1 · ¿`estandar` o `critico`?** `CHECKPOINTS.md` define `critico`
  como «infraestructura compartida, producción, seguridad o dinero»; los
  bloques 2 y 3 borran cosas en producción de otro proyecto.
  **Recomendación: `critico`.** El coste es bajo —la campaña de mutación
  no tendrá material (§10) y las verificaciones MANUAL con comando exacto y
  resultado real ya están escritas— y el beneficio es que el reviewer exija
  el acta de cada borrado.
- **DA-2 · ¿qué acceso conserva el puesto al Postgres tras la limpieza?**
  (A) Retirar todas las `datamart-puesto-*` y recrear una regla bajo demanda
  con el comando documentado en el README. (B) Dejar una regla vigente.
  **Recomendación: A** — las direcciones que traen esas reglas están
  caducadas desde hace días (la IP del humano rota), así que dejarlas es
  una puerta abierta que además no sirve.
- **DA-3 · `ClientPgris` y `FirewallIPAddress_2026-6-16`.** Son de
  `albaranes` y anteriores a este proyecto (R19). Solo el humano sabe si
  alguien las usa. **Recomendación: no borrarlas** salvo confirmación
  explícita; el coste de dejarlas es cero.
- **DA-4 · `SIGRID_API_PAGE_SIZE`.** El job no la usa (R4), así que solo
  afecta al `.env` del puesto. **Recomendación: dejar el valor que le
  funcione en su red y no tocar `.env.example`** (que refleja el defecto
  del código). Anotar la decisión y cerrar el asunto.
- **DA-5 · defecto anotado de `60_create_identity.ps1`** (verifica los
  roles antes de que RBAC propague y lanza un `throw` falso). Se va a rozar
  en R6/R10, donde la propagación importa. **Recomendación: BACKLOG**, no
  arreglarlo aquí: no es de ninguno de los tres bloques y ampliaría el
  alcance de una feature que es de operación. Mitigación durante F-023:
  esperar y repetir el comando antes de concluir nada.
- **DA-6 · si el job desplegado NO tuviera las `AUX_EXCEL_*` como URIs de
  blob.** `80_create_job.ps1` se **niega** a correr si el job existe, y
  `85_update_job.ps1` solo cambia la imagen: hoy no hay camino soportado
  para cambiar una variable de entorno de un job vivo. Opciones: (A)
  `az containerapp job update --set-env-vars ...` a mano, documentado en el
  README; (B) borrar y recrear el job (pierde el historial de ejecuciones y
  hay que reprogramar). **Recomendación: A**, y anotar la carencia del
  guion de despliegue como backlog. Se espera **no** tener que usarlo: R9
  debería confirmar que ya son URIs de blob.
- **DA-7 · orden respecto a F-024.** El bloque 3 (firewall) exige que la
  Fase C de F-024 esté completa (§7). ¿Se acepta ese orden, o el humano
  prefiere ejecutar F-023 entera antes y recrear la regla cuando le haga
  falta para F-024? **Recomendación: aceptar el orden**; es gratis y evita
  un ida y vuelta.

## 10. Riesgos, y qué los contiene

| Riesgo | Contención |
|---|---|
| Borrar un secreto de producción y no poder volver atrás | R12 (c) exige soft-delete comprobado **antes**; R13 para la feature si no lo hay; R14 prohíbe `purge` y deja la recuperación documentada |
| El valor de un secreto acaba en pantalla, en el historial o en un fichero | `az keyvault secret show` está **prohibido** sobre esos nombres en toda la feature; toda comprobación es `secret list` (nombres) |
| La verificación 3 se interrumpe y el humano queda sin permisos sobre la cuenta | La restauración es parte de la **misma** tarea; R10 exige contrastar la lista de roles contra la fotografía de R6 y volver a ejecutar `load-aux` |
| Retirar la regla del firewall equivocada y apagar la carga nocturna | R18 nombra explícitamente qué debe **permanecer**; el listado posterior es la evidencia |
| Retirar el firewall del puesto antes de tiempo y bloquear F-024 | R17 y el orden de §7 |
| `load-aux` desde el puesto pisa una ejecución del job | R8: comprobación obligatoria de ejecuciones en `Running` y prohibición de la ventana nocturna |
| Subir un Excel con el nombre mal escrito: el job falla de madrugada | R5 compara el listado del contenedor contra `auxBlobs`; R2 impide que el nombre declarado deje de ser un nombre de fichero |
| Que la feature «se dé por hecha» sin evidencia real | Todo MANUAL lleva comando exacto y su salida real va a `progress/impl_F-023.md`; el reviewer valida contra eso |

## 11. Cómo se satisfacen las puertas de `CHECKPOINTS.md`

- **Fase RED**: aplica a los cuatro tests nuevos. Se demuestra con la
  salida real del fallo, provocado sin tocar producción: por ejemplo,
  copiando `infra/env/dev.json` a un fichero temporal con un `auxBlobs` que
  lleve una ruta, o pasando al ayudante del test un texto de script con una
  ruta local. Los tests son de artefactos, así que la fase RED se hace
  sobre **entradas de prueba**, no rompiendo el repositorio.
- **Cobertura de las líneas cambiadas**: el diff no contiene ninguna línea
  de producción (solo tests y Markdown). El alcance saldrá **vacío**, y eso
  es el resultado correcto, no una omisión. Se declara con el número real
  que dé la herramienta.
- **Campaña de mutación**: por el mismo motivo, **cero mutantes** —no hay
  código de producción que mutar—. Se ejecuta igualmente y se pega la
  salida: cero mutantes es un dato, «no aplica» sin ejecutar no lo es.
- **Verificaciones MANUAL**: son el cuerpo de la feature. Trece, cada una
  con su comando exacto en `requirements.md` y su resultado real en el
  informe.
- Si el humano acepta DA-1 (`critico`), lo anterior no cambia: lo que se
  añade es la exigencia de que **cada borrado tenga su acta** con el OK
  citado, que R14 ya impone.
