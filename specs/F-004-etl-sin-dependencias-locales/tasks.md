<!-- specs/F-004-etl-sin-dependencias-locales/tasks.md -->
# F-004 · Ejecutar el ETL en Azure sin dependencias locales — Tareas

Rama: `feature/F-004-etl-sin-dependencias-locales`. Un commit por tarea,
formato `F-004 Tn: descripción`. Orden por dependencia: el puerto antes que
los adaptadores, los adaptadores antes que el step.

Recordatorios que aplican a **todas** las tareas:

- Primera línea de cada fichero Python: comentario con su ruta relativa.
- Ningún test toca red ni BBDD. Los dobles se inyectan; no se parchean
  módulos del SDK de Azure.
- Nada de rutas absolutas en el código: los ejemplos de ruta viven en
  `.env.example` y en las specs, no en `etl_sigrid/` ni en `config/`
  (el test de R15 los cazaría).

---

- [x] **T1**: En `config/settings.py`, actualizar el docstring de
      `AuxExcelSettings` (el valor puede ser ruta local/de red **o** URI de
      blob) y añadir `entries() -> tuple[tuple[str, str, str], ...]` que
      devuelva `(nombre_lógico, variable_de_entorno, valor)` de los tres
      ficheros. Sin cambiar tipos ni nombres de campo.
      **Verificación**: `test_f004_r1_settings_declara_las_tres_variables_con_su_nombre_de_entorno`

- [x] **T2**: Crear `etl_sigrid/infrastructure/excel/aux_file_source.py` con
      `AuxFileRef`, la jerarquía de errores (`AuxFileError`,
      `AuxFileConfigError`, `AuxFileNotFoundError`, `AuxFileAccessError`) y
      `parse_aux_file_ref()`, aplicando las reglas de clasificación y
      descomposición de URI del diseño §5.1.
      **Verificación**: `test_f004_r2_uri_de_blob_se_clasifica_como_blob_y_se_descompone`,
      `test_f004_r2_nombre_de_blob_con_subcarpetas_se_conserva_entero`,
      `test_f004_r3_ruta_windows_posix_y_unc_se_clasifican_como_local`,
      `test_f004_r5_uri_https_ajena_a_blob_storage_es_error_de_configuracion`,
      `test_f004_r6_uri_con_sas_se_rechaza`,
      `test_f004_r6_el_mensaje_de_rechazo_no_filtra_el_token`,
      `test_f004_r7_uri_sin_contenedor_o_sin_blob_es_error_de_configuracion`

- [x] **T3**: En el mismo módulo, `AuxFileSource` (Protocol),
      `LocalAuxFileSource.read_bytes()` con traducción de errores y el mensaje
      accionable de R8, y la fábrica `get_aux_file_source()` con import
      perezoso del adaptador de blob.
      **Verificación**: `test_f004_r3_lee_un_xlsx_real_del_sistema_de_ficheros`
      (fixture que genera el `.xlsx` en `tmp_path` con `openpyxl`),
      `test_f004_r8_ruta_local_inexistente_produce_mensaje_accionable`

- [x] **T4**: Crear `etl_sigrid/infrastructure/excel/blob_aux_file_source.py`
      con `BlobAuxFileSource`, la fábrica de cliente por defecto
      (`DefaultAzureCredential` + `BlobClient`, import perezoso) y la
      traducción de errores del SDK por nombre de clase.
      **Verificación**: `test_f004_r2_...` con fábrica doble,
      `test_f004_r4_el_cliente_de_blob_se_construye_con_default_azure_credential`,
      `test_f004_r9_blob_inexistente_produce_mensaje_con_cuenta_contenedor_y_blob`,
      `test_f004_r10_error_de_permisos_menciona_el_rol_y_las_dos_salidas`,
      `test_f004_r10_falta_de_credencial_menciona_az_login_e_identidad_gestionada`

- [x] **T5**: Añadir `azure-identity>=1.17.0` y `azure-storage-blob>=12.20.0`
      a `requirements.txt` (justificación en diseño §7). No tocar
      `requirements-dev.txt`.
      **Verificación**: `pip install -r requirements.txt` sin errores y
      `python -c "import azure.identity, azure.storage.blob"` sin excepción.
      Además `test_f004_r4_no_hay_cadenas_de_conexion_ni_claves_en_el_codigo`

- [x] **T6**: Reescribir
      `etl_sigrid/application/steps/load_excel_aux_step.py` según el diseño
      §5.4: fábrica inyectable, lectura en memoria, `openpyxl` sobre
      `BytesIO`, acumulación de todos los errores, `SKIPPED` sin configuración,
      `SUCCESS` con metadata por fichero. `main.py` no se toca.
      **Verificación**: `test_f004_r11_el_step_abre_el_libro_desde_memoria_sin_ruta_existente`,
      `test_f004_r12_los_tres_ficheros_legibles_dan_success_con_metadata`,
      `test_f004_r13_sin_variables_configuradas_el_step_queda_skipped`,
      `test_f004_r13_configuracion_parcial_lee_lo_configurado_y_lista_lo_omitido`,
      `test_f004_r14_fichero_ilegible_da_failed_nombrando_el_fichero`,
      `test_f004_r14_dos_fallos_se_reportan_los_dos_en_el_mismo_mensaje`

- [x] **T7**: Crear `tests/test_f004_sin_dependencias_locales.py` con la
      auditoría automatizada: barrido de rutas absolutas sobre
      `etl_sigrid/**/*.py`, `config/**/*.py` y `main.py` (patrones:
      `["']<letra>:[\\/]`, UNC `\\\\`, `/home/`, `/Users/`, `/mnt/`;
      `scripts/` y `patches/` excluidos por no viajar en la imagen), y
      comprobación de que existen los directorios SQL de cada capa y de que el
      `Dockerfile` copia `config/`, `etl_sigrid/` y `main.py` sin copiar
      `.env`.
      **Verificación**: `test_f004_r15_el_codigo_de_la_imagen_no_contiene_rutas_absolutas`,
      `test_f004_r16_los_directorios_sql_de_cada_capa_existen_en_el_paquete`,
      `test_f004_r16_el_dockerfile_copia_config_y_el_paquete_y_no_copia_env`

- [x] **T8**: Recorrer a mano la tabla de auditoría del diseño §8 sobre el
      código actual y anotar en `progress/impl_F-004.md` la confirmación de
      cada punto y **cualquier hallazgo nuevo** que no esté en la tabla. Si
      aparece uno que sea dependencia real del sistema de ficheros local, NO
      improvisar: anotarlo y consultarlo.
      **Verificación**: `progress/impl_F-004.md` contiene los 9 puntos
      revisados uno a uno, con veredicto.

- [x] **T9**: Actualizar `.env.example`: documentar las dos formas admitidas,
      sustituir la ruta personal de OneDrive por un ejemplo neutro y añadir el
      ejemplo de URI de blob comentado, advirtiendo de que no se admite SAS.
      **Verificación**: revisión del reviewer; `bash harness/init.sh` sigue
      encontrando `.env` y en verde.

- [x] **T10**: Añadir a `docs/ARCHITECTURE.md`, sección «Acceso a datos», la
      línea sobre los Excels auxiliares: ruta local o Azure Blob Storage, con
      identidad gestionada y sin claves.
      **Verificación**: revisión del reviewer contra `CHECKPOINTS.md` C3.

- [x] **T11**: Ejecutar `bash harness/init.sh` en verde (incluye `pytest`) y
      dejar `progress/current.md` con las verificaciones **MANUAL (humano)**
      pendientes y su comando exacto.
      **Verificación**: `bash harness/init.sh` termina con exit code 0.

---

## Verificaciones MANUAL (humano)

No se pueden automatizar: exigen Azure y **dependen de F-003**, que crea la
storage account y el contenedor `aux`. Se listan en `progress/current.md` al
cerrar la feature; no bloquean el cierre de F-004.

1. Con `az login` activo y el rol `Storage Blob Data Reader` sobre la cuenta,
   apuntar `AUX_EXCEL_TIPO_PARTIDA` al blob real y ejecutar:
   `python main.py load-aux`
   Esperado: `SUCCESS`, y en el detalle `origen=blob` con las hojas del libro.
2. Desde el Container Apps Job, con identidad gestionada:
   `az containerapp job start -n <job> -g <rg>` y luego leer los logs
   buscando el evento `aux_file_read`.
   Esperado: los tres ficheros leídos, ninguna ruta local en el log.
3. Prueba negativa del mensaje de permisos: retirar temporalmente el rol
   `Storage Blob Data Reader`, ejecutar `python main.py load-aux` y comprobar
   que el error dice qué rol falta y qué hacer. Volver a asignarlo después.
