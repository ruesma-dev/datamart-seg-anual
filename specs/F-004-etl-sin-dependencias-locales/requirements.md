<!-- specs/F-004-etl-sin-dependencias-locales/requirements.md -->
# F-004 · Ejecutar el ETL en Azure sin dependencias locales — Requisitos

Notación EARS. Cada requisito se traduce a >= 1 test trazable
(`test_f004_rN_*`). Ningún test toca red ni BBDD: la lectura de blob se
verifica con un doble inyectado en el límite del adaptador.

---

## Contexto y alcance

**F-004 es SOLO CÓDIGO.** No aprovisiona nada en Azure: la storage account y
el contenedor `aux` los crea **F-003**. Aquí solo se consigue que el ETL sepa
leer sus tres Excels auxiliares esté donde esté el fichero.

### Corrección de la premisa de `harness/features.json`

La entrada F-004 dice que «hoy `run-all` incluye `LoadExcelAuxStep`, que lee
los Excels auxiliares desde rutas locales». **Eso no es cierto a día de hoy.**
`etl_sigrid/application/steps/load_excel_aux_step.py` es un *stub*: devuelve
`SKIPPED` con el mensaje «No implementado todavía» y no abre ningún fichero.
Las variables `AUX_EXCEL_*` existen en `config/settings.py` y en
`.env.example`, pero **nadie las lee**.

Consecuencia práctica: el pipeline **no falla hoy** en un contenedor por culpa
de este step. La feature sigue siendo un prerrequisito real del despliegue,
pero su valor es *construir* la capacidad de lectura, no *arreglar* una rotura.

### Frontera explícita: F-004 lee, no carga

F-004 deja los tres Excels **leídos y validados**, no volcados a `aux.*`.
Motivo, no pereza:

- Las tablas destino **no existen**. `README.md` §5.2 lista `aux.tipo_partida`
  y compañía bajo «En el futuro puede contener»; el único objeto real del
  schema `aux` es `aux.periodificacion_partida`, hoy vacía.
- **El esquema de los tres Excel no está en el repositorio** (columnas, hojas,
  claves) ni las reglas de negocio que los mapean a `mart`. Inventarlos sería
  exactamente el «workaround ante spec ambigua» que prohíbe `CLAUDE.md`.

Por tanto, tras F-004 el step `load_excel_aux`:

1. resuelve las tres ubicaciones (local o blob),
2. descarga/lee el contenido **a memoria**,
3. abre cada libro con `openpyxl` y comprueba que es legible,
4. reporta origen, tamaño y hojas de cada uno,
5. **no escribe una sola fila en Postgres.**

La carga a `aux.*` necesita decisión del humano y feature propia. Anotado en
`progress/current.md` como decisión abierta **DA-1**.

---

## Requisitos

### Resolución del origen

> **R1.** El sistema debe resolver cada uno de los tres Excels auxiliares
> (`tipo_partida`, `tipo_coste`, `mapeo_proporcionales`) a partir del valor de
> su variable `AUX_EXCEL_*`, de forma que el resto del código obtenga el
> contenido del fichero **sin saber** si está en disco o en un blob.

- `test_f004_r1_settings_declara_las_tres_variables_con_su_nombre_de_entorno`
- `test_f004_r1_la_misma_llamada_sirve_para_ruta_local_y_para_uri_de_blob`

> **R2.** CUANDO el valor de una variable `AUX_EXCEL_*` es una URI
> `https://<cuenta>.blob.core.windows.net/<contenedor>/<ruta-del-blob>`, el
> sistema debe leer el fichero desde Azure Blob Storage, extrayendo cuenta,
> contenedor y nombre de blob de la propia URI.

- `test_f004_r2_uri_de_blob_se_clasifica_como_blob_y_se_descompone`
- `test_f004_r2_nombre_de_blob_con_subcarpetas_se_conserva_entero`

> **R3.** CUANDO el valor **no** es una URI de Azure Blob Storage —ruta
> Windows (`C:/...`), ruta POSIX (`/datos/...`) o ruta de red UNC
> (`\\servidor\recurso\...`)—, el sistema debe leerlo del sistema de ficheros
> local. Que el ETL siga funcionando en local es requisito, no cortesía.

- `test_f004_r3_ruta_windows_posix_y_unc_se_clasifican_como_local`
- `test_f004_r3_lee_un_xlsx_real_del_sistema_de_ficheros`

### Autenticación

> **R4.** MIENTRAS lee desde Azure Blob Storage, el sistema debe autenticarse
> con `DefaultAzureCredential`, sin cadena de conexión, sin clave de cuenta y
> sin SAS. La misma credencial resuelve por identidad gestionada en el
> contenedor y por la sesión de `az` en el puesto local.

- `test_f004_r4_el_cliente_de_blob_se_construye_con_default_azure_credential`
- `test_f004_r4_no_hay_cadenas_de_conexion_ni_claves_en_el_codigo`

### Configuración inválida (comportamiento no deseado)

> **R5.** SI el valor es una URI `https://` cuyo host **no** termina en
> `.blob.core.windows.net`, ENTONCES el sistema debe fallar con un error de
> configuración que nombre la variable y el host recibido, **sin** tratar el
> valor como ruta local.

- `test_f004_r5_uri_https_ajena_a_blob_storage_es_error_de_configuracion`

> **R6.** SI la URI de blob incluye query string (típicamente un token SAS),
> ENTONCES el sistema debe rechazarla remitiendo a la identidad gestionada, y
> el mensaje de error **no debe contener la query string**.

- `test_f004_r6_uri_con_sas_se_rechaza`
- `test_f004_r6_el_mensaje_de_rechazo_no_filtra_el_token`

> **R7.** SI la URI de blob no identifica contenedor **y** blob (por ejemplo
> `https://cuenta.blob.core.windows.net/aux`), ENTONCES el sistema debe fallar
> con un error de configuración que muestre la forma esperada.

- `test_f004_r7_uri_sin_contenedor_o_sin_blob_es_error_de_configuracion`

### Errores en tiempo de ejecución: mensajes accionables

Este step va a fallar de noche en un contenedor y alguien lo diagnosticará por
los logs. Los tres requisitos siguientes son sobre **el texto del error**.

> **R8.** SI el fichero local configurado no existe o no se puede leer,
> ENTONCES el sistema debe fallar con un mensaje que incluya el nombre lógico
> del fichero, la variable de entorno responsable, la ruta recibida y la pista
> de que en un contenedor de Azure se espera una URI de blob.

- `test_f004_r8_ruta_local_inexistente_produce_mensaje_accionable`

> **R9.** SI el blob no existe, ENTONCES el sistema debe fallar con un mensaje
> que incluya cuenta, contenedor y nombre de blob, y que indique que el
> fichero debe subirse al contenedor.

- `test_f004_r9_blob_inexistente_produce_mensaje_con_cuenta_contenedor_y_blob`

> **R10.** SI la lectura del blob falla por permisos o por ausencia de
> credencial, ENTONCES el mensaje debe nombrar el rol
> **`Storage Blob Data Reader`** sobre la cuenta y las dos salidas según el
> entorno: `az login` en local, identidad gestionada asignada al job en Azure.

- `test_f004_r10_error_de_permisos_menciona_el_rol_y_las_dos_salidas`
- `test_f004_r10_falta_de_credencial_menciona_az_login_e_identidad_gestionada`

### Sin sistema de ficheros

> **R11.** El sistema debe obtener el contenido de los Excels **en memoria**,
> sin escribir ficheros temporales en disco, ni al leer de blob ni al abrir el
> libro con `openpyxl`.

- `test_f004_r11_el_step_abre_el_libro_desde_memoria_sin_ruta_existente`

### Comportamiento del step

> **R12.** CUANDO las tres variables `AUX_EXCEL_*` están configuradas y los
> tres ficheros son accesibles y legibles, el step `load_excel_aux` debe
> terminar en `SUCCESS` y registrar en su metadata, por fichero: origen
> (`local` / `blob`), ubicación segura para log, tamaño en bytes y hojas del
> libro.

- `test_f004_r12_los_tres_ficheros_legibles_dan_success_con_metadata`

> **R13.** MIENTRAS las tres variables `AUX_EXCEL_*` estén vacías, el step
> debe terminar en `SKIPPED` explicando que no hay ninguna configurada, sin
> hacer fallar `run-all`. Si solo alguna está vacía, las vacías se omiten y se
> listan en el resultado; las configuradas se leen.

- `test_f004_r13_sin_variables_configuradas_el_step_queda_skipped`
- `test_f004_r13_configuracion_parcial_lee_lo_configurado_y_lista_lo_omitido`

> **R14.** SI alguno de los ficheros configurados no se puede obtener o no es
> un `.xlsx` legible, ENTONCES el step debe terminar en `FAILED` **listando
> todos** los ficheros problemáticos en un único mensaje, no solo el primero.

- `test_f004_r14_fichero_ilegible_da_failed_nombrando_el_fichero`
- `test_f004_r14_dos_fallos_se_reportan_los_dos_en_el_mismo_mensaje`

### Auditoría del resto del pipeline

> **R15.** El sistema debe estar libre de rutas absolutas del sistema de
> ficheros local en el código que viaja en la imagen (`etl_sigrid/`,
> `config/`, `main.py`).

- `test_f004_r15_el_codigo_de_la_imagen_no_contiene_rutas_absolutas`

> **R16.** El sistema debe resolver todos los ficheros que necesita en
> ejecución (SQL por capas y YAML de configuración) **dentro del árbol que la
> imagen copia**, de modo que existan en el contenedor.

- `test_f004_r16_los_directorios_sql_de_cada_capa_existen_en_el_paquete`
- `test_f004_r16_el_dockerfile_copia_config_y_el_paquete_y_no_copia_env`

---

## Verificaciones que NO puede cubrir un test automático

Van a `progress/current.md` como **MANUAL (humano)**; requieren Azure y por
tanto **dependen de F-003**, que crea la cuenta y el contenedor `aux`:

1. Lectura real de un blob desde el puesto local con `az login` activo.
2. Lectura real del mismo blob desde el Container Apps Job con identidad
   gestionada y rol `Storage Blob Data Reader`.
3. Comprobación de que el mensaje de error de permisos es útil de verdad:
   ejecutar sin el rol asignado y leer el log.
