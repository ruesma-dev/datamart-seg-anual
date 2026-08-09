<!-- progress/impl_F-004.md -->
# F-004 · Ejecutar el ETL en Azure sin dependencias locales — Informe de implementación

Rama `feature/F-004-etl-sin-dependencias-locales`. Nivel de rigor **estandar**
(`harness/features.json`). Spec aprobada por el humano el 2026-08-09.
Las 11 tareas de `tasks.md` están hechas y marcadas, una por commit.

---

## 1. Qué cambió, en una frase

El step `load_excel_aux` deja de ser un *stub* que devolvía `SKIPPED` y pasa a
**resolver, obtener y validar** los tres Excels auxiliares indistintamente
desde una ruta del sistema de ficheros o desde Azure Blob Storage, decidiendo
por la **forma del valor** de `AUX_EXCEL_*`, autenticando con
`DefaultAzureCredential` y trabajando **siempre en memoria**. No carga nada a
`aux.*` y no aprovisiona nada en Azure: F-004 es solo código.

## 2. Ficheros tocados

### Creados

| Ruta | Qué es |
|---|---|
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | Puerto `AuxFileSource`, `AuxFileRef`, jerarquía de errores, `parse_aux_file_ref()`, adaptador local y fábrica |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | Adaptador de Blob Storage: descarga a memoria y traducción de errores del SDK |
| `tests/test_f004_aux_file_source.py` | 40 tests, R1–R11 |
| `tests/test_f004_load_excel_aux_step.py` | 11 tests, R11–R14 |
| `tests/test_f004_sin_dependencias_locales.py` | 6 tests de auditoría, R15–R16 |
| `progress/mutacion_F-004.md` | Campaña de mutación, con los 2 supervivientes analizados |

### Modificados

| Ruta | Qué cambia |
|---|---|
| `etl_sigrid/application/steps/load_excel_aux_step.py` | Reescrito por completo (era un stub de 37 líneas) |
| `config/settings.py` | Docstring de `AuxExcelSettings` (ruta **o** URI) y método `entries()` |
| `requirements.txt` | `azure-storage-blob>=12.20.0` (ver desviación D1) |
| `.env.example` | Las dos formas admitidas, sin la ruta personal de OneDrive, con el aviso de que el SAS se rechaza |
| `docs/ARCHITECTURE.md` | Entrada en «Acceso a datos» |
| `specs/F-004-.../tasks.md` | Las 11 tareas marcadas |

**No se ha tocado** nada de lo que `design.md` §4 declara fuera: ni el
orquestador, ni `steps/base.py`, ni los otros cinco steps, ni un solo fichero
SQL, ni `postgres_client.py`, ni el `Dockerfile` (R16 lo **verifica**, no lo
cambia), ni `infra/`, ni `main.py` — el parámetro nuevo del constructor es
*keyword-only* y opcional, así que `LoadExcelAuxStep(settings)` sigue valiendo.

## 3. Decisiones de diseño (y por qué)

1. **Discriminar por la forma del valor**, no por una variable `AUX_SOURCE`.
   Una variable de modo permite el estado absurdo «modo blob con ruta de
   Windows»; la URI ya lleva toda la información.
2. **Inyección en el límite, nunca parcheo del SDK.** El step recibe una
   `source_factory` y el adaptador de blob una `blob_client_factory`. Los
   tests doblan ahí y por eso **ningún test necesita `azure-storage-blob`
   instalado** (en este puesto no lo está: `import azure` falla).
3. **Traducción de errores del SDK por NOMBRE de clase**, no por su jerarquía.
   Sobrevive a una reorganización de `azure-core` y permite doblar sin el SDK.
   Precio reconocido: un renombrado de clase en el SDK degradaría el mensaje a
   genérico — nunca a silencio.
4. **Import perezoso del SDK, en una sola función** (`_importar_sdk`). Quien
   solo usa el camino local no paga arranque, y la suite corre entera sin el
   paquete. Que ese import sea el oficial se comprueba **por la fuente de la
   función** (`inspect.getsource`), que es lo único que ningún doble puede
   fingir.
5. **Una credencial por instancia**, reutilizada para los tres ficheros:
   `DefaultAzureCredential` recorre varias fuentes y no es barata.
6. **Los mensajes de error son producto, no adorno.** Este step va a fallar de
   noche en un contenedor y alguien lo va a diagnosticar por el log: por eso
   R8–R10 se prueban sobre el TEXTO (variable responsable, ubicación, rol
   `Storage Blob Data Reader`, `az login` en local / identidad gestionada en
   Azure), y por eso `display` nunca devuelve la URI cruda.
7. **Acumular todos los errores** antes de fallar (mismo criterio que
   `_preflight_check` de `build_stg_step`): con dos ficheros rotos, el mensaje
   los nombra los dos.
8. **`SKIPPED` sin configuración, `FAILED` con configuración rota.** «No me han
   dicho dónde está» y «me han dicho dónde está y no está» son problemas
   distintos y merecen desenlaces distintos.

---

## 4. Fase RED — salida real de cada fallo

Nivel `estandar`: para los requisitos centrales, el test se escribió ANTES que
el código. Estas son las trazas literales, con el comando que las produjo.

### T1 · R1 — `entries()` no existía

```
$ python -m pytest tests/test_f004_aux_file_source.py -q --tb=short
F                                                                        [100%]
================================== FAILURES ===================================
__ test_f004_r1_settings_declara_las_tres_variables_con_su_nombre_de_entorno __
tests\test_f004_aux_file_source.py:41: in test_...
    assert ajustes.entries() == (
           ^^^^^^^^^^^^^^^
.venv\Lib\site-packages\pydantic\main.py:1042: in __getattr__
    raise AttributeError(f'{type(self).__name__!r} object has no attribute {item!r}')
E   AttributeError: 'AuxExcelSettings' object has no attribute 'entries'
1 failed in 0.63s
```

### T2 · R2, R3, R5–R7 — el módulo del puerto no existía

```
$ python -m pytest tests/test_f004_aux_file_source.py -q --tb=short
tests\test_f004_aux_file_source.py:15: in <module>
    from etl_sigrid.infrastructure.excel.aux_file_source import (
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.excel.aux_file_source'
1 error in 0.62s
```

Tras implementarlo: `21 passed in 0.53s`.

### T3 · R3, R8 — el adaptador local no existía

```
$ python -m pytest tests/test_f004_aux_file_source.py -q --tb=short
tests\test_f004_aux_file_source.py:15: in <module>
    from etl_sigrid.infrastructure.excel.aux_file_source import (
E   ImportError: cannot import name 'LocalAuxFileSource' from
    'etl_sigrid.infrastructure.excel.aux_file_source'
1 error in 0.79s
```

Tras implementarlo: `25 passed in 0.64s`.

### T4 · R4, R9, R10 — el adaptador de blob no existía

```
$ python -m pytest tests/test_f004_aux_file_source.py -q --tb=short
tests\test_f004_aux_file_source.py:29: in <module>
    from etl_sigrid.infrastructure.excel.blob_aux_file_source import (
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.excel.blob_aux_file_source'
1 error in 0.67s
```

**Segundo rojo, y este enseñó algo.** Con el adaptador ya escrito, tres tests
seguían en rojo porque mis dobles se llamaban `_ResourceNotFoundError`,
`_ClientAuthenticationError`… y la traducción es **por nombre de clase**:

```
E   AuxFileError: Fallo al leer el Excel auxiliar 'tipo_coste'
    (blob: stdatamartsegdev/aux/tipo_coste.xlsx, variable AUX_EXCEL_TIPO_COSTE):
    _ClientAuthenticationError: no autorizado
3 failed, 34 passed in 1.14s
```

El fallo era del test, no del código: un doble con otro nombre no dobla nada.
Renombrados a los nombres exactos del SDK → `37 passed in 0.97s`.

### T6 · R11–R14 — el step no aceptaba fuente inyectada

```
$ python -m pytest tests/test_f004_load_excel_aux_step.py -q --tb=short
E   TypeError: LoadExcelAuxStep.__init__() got an unexpected keyword argument 'source_factory'
7 failed, 1 passed in 0.77s
```

**Y un rojo más, que corrigió el código.** Ya implementado el step, R14 seguía
fallando porque el mensaje del libro ilegible no decía de dónde salía el
fichero:

```
E   assert 'blob: stdatamartsegdev/aux/TipoPartida.xlsx' in
    "1 Excel(s) auxiliar(es) no se pudieron leer:\n\n  · El Excel auxiliar
     'tipo_partida' (variable AUX_EXCEL_TIPO_PARTIDA...ZipFile: File is not a
     zip file. ..."
1 failed, 7 passed in 0.84s
```

Tenía razón el test: un `BadZipFile` sin la ubicación no es diagnosticable. Se
añadió `ref.display` y el tamaño en bytes al mensaje.

### T7 · R15 — la auditoría encontró dos falsos positivos reales

El primer barrido de rutas absolutas salió en rojo, y bien:

```
E   AssertionError: Rutas absolutas en el código que viaja en la imagen:
E     etl_sigrid/infrastructure/postgres/postgres_client.py:763 [recurso de red UNC] return "\\\\x" + value.hex()
E     etl_sigrid/infrastructure/postgres/postgres_client.py:767 [recurso de red UNC] s.replace("\\", "\\\\")
1 failed, 5 passed in 0.14s
```

No son rutas: es el escapado de `bytea` de PostgreSQL. El patrón UNC ingenuo
(`"` seguido de dos barras) caza cualquier barra escapada. Afinado a
`['"]\\{2,4}[A-Za-z0-9_.$-]+\\{1,2}` —dos barras, **nombre de servidor** y otra
barra— y fijado con `test_f004_r15_el_barrido_caza_de_verdad_una_ruta_absoluta`,
que comprueba que cada patrón caza su forma **y** que esas dos líneas inocentes
no vuelven a saltar. Un test de auditoría que no sabe fallar no vigila nada.

---

## 5. T8 · Auditoría del pipeline: los 9 puntos de `design.md` §8, uno a uno

Recorridos a mano sobre el código de hoy.

| # | Punto | Verificado | Veredicto |
|---|---|---|---|
| 1 | Los cuatro `build_*` resuelven su `sql_dir` con `Path(__file__)...parents[2]` | Sí: `build_stg:85`, `build_mart:73`, `build_cierre:66`, `build_maestros:65` | **Correcto**, y ahora blindado por `test_f004_r16_los_steps_resuelven_sus_sql_relativos_al_paquete`, que reproduce la expresión y comprueba que cae dentro del paquete |
| 2 | `Settings._load_yaml` lee los dos YAML vía `Path(__file__).resolve().parent` | Sí, `config/settings.py:242-244` | **Correcto**. Blindado por `test_f004_r16_los_yaml_de_configuracion_viven_bajo_config` |
| 3 | `main.py` añade la raíz al `sys.path` relativo al fichero | Sí, `main.py:38` | **Correcto** |
| 4 | `SettingsConfigDict(env_file=".env")` en las cuatro clases | Sí, 4 ocurrencias | **Aceptable**. En el contenedor no hay `.env` y pydantic-settings lo ignora; la config llega por variables de entorno. Riesgo residual solo en local (se resuelve contra el *cwd*). Sin acción, como fijaba la spec |
| 5 | `build_stg_step` es el único sin `sql_path.exists()` | **Confirmado**: `cierre:91`, `maestros:93`, `mart:114` lo comprueban; `stg` no | **Menor**, documentado y **no corregido** (fuera de alcance). Candidato a backlog |
| 6 | Ningún step escribe ficheros temporales; los logs van a `stdout` | `logging_config.py:23` usa `stream=sys.stdout` | **Correcto**. La lectura de blob mantiene la propiedad (R11) |
| 7 | `scripts/` y `patches/` traen rutas locales pero no viajan en la imagen | Confirmado: el `Dockerfile` copia 4 rutas explícitas | **Irrelevante**. Excluidos del barrido de R15 a propósito |
| 8 | No existe `.dockerignore` | Confirmado | **Sin riesgo hoy**: no hay `COPY . .`, y el test de R16 lo fija (`assert "." not in origenes`) |
| 9 | `LoadExcelAuxStep` es un stub | Confirmado (era `SKIPPED` + «No implementado todavía») | **Es el objeto de la feature**: reescrito |

### Hallazgos NUEVOS, no listados en la tabla de la spec

- **N1 · `main.py` resuelve por su cuenta dos capas SQL.** Las líneas 2713 y
  3012 construyen `Path(__file__).resolve().parent / "etl_sigrid" / ... /
  "compras"` y `.../"retenciones"`. Es correcto —relativo al fichero, dentro
  del árbol que copia la imagen— **pero depende de que `main.py` esté junto a
  `etl_sigrid/`**, que es exactamente lo que hace el `Dockerfile`
  (`WORKDIR /app`, `COPY etl_sigrid/ etl_sigrid/`, `COPY main.py .`).
  Verificado. Sin acción; las dos capas están cubiertas por el test de
  directorios SQL de R16.
- **N2 · `fingerprint.escribir_csv` SÍ escribe en disco** (`path.parent.mkdir`
  + `path.open("w")`, líneas 302-303), lo que matiza el punto 6 de la tabla.
  **No es un step**: es el comando manual `fingerprint-views`, con la ruta que
  el humano pasa en `--salida`, y no participa en `run-all --full`. No es una
  dependencia del sistema de ficheros *local* del pipeline. Sin acción.
- **N3 · El barrido de secretos de F-005 tiene un falso positivo con las rutas
  largas.** `test_f005_r21_barrido_de_secretos_en_el_arbol` puso `init.sh` en
  rojo al añadir yo una línea a `docs/ARCHITECTURE.md`: su patrón de base64
  (`[A-Za-z0-9+/]{24,}`) casó con `sigrid/infrastructure/excel/`. **No he
  tocado el test de otra feature**: he reformulado mi frase. Queda anotado como
  candidato para **F-016** (refuerzo de los tests de F-005): el patrón debería
  excluir cadenas con `/` repetidos o exigir contexto de asignación.

**Conclusión, sin cambios respecto a la spec**: la única dependencia real del
sistema de ficheros local del pipeline eran los tres `AUX_EXCEL_*`, y es justo
lo que esta feature elimina.

---

## 6. Desviaciones respecto al diseño

- **D1 · `azure-identity` NO se ha vuelto a añadir a `requirements.txt`.**
  `design.md` §7 pedía añadir los dos paquetes, pero `azure-identity>=1.17` ya
  estaba desde F-005 (autenticación Entra contra Postgres). Duplicar la línea
  habría sido ruido. Se ha añadido solo `azure-storage-blob>=12.20.0` y se ha
  actualizado el comentario de `azure-identity` para que diga sus **dos** usos.
- **D2 · `BlobAuxFileSource` tiene un parámetro más de lo diseñado**
  (`importar_sdk`, *keyword-only*, con valor por defecto). Sin él, comprobar
  R4 —«el cliente se construye con `DefaultAzureCredential`»— exigía parchear
  `sys.modules` con módulos falsos de Azure, y `tasks.md` lo prohíbe
  explícitamente. Con él, la verificación es inyección limpia en el límite. La
  firma pública (`blob_client_factory`) es la del diseño.
- **D3 · Ninguna plantilla de mensaje incluye una ruta absoluta de ejemplo.**
  El diseño ilustraba R8 con `'D:/datos/TipoPartida.xlsx'`; ponerlo en el
  código lo habría cazado el test de R15. Los ejemplos viven en `.env.example`
  y en la spec; el mensaje interpola la ruta **recibida** y enseña la forma de
  la URI con marcadores `<cuenta>`/`<contenedor>`.
- **D4 · Se añadieron 4 tests después de la primera campaña de mutación** (los
  dos flags de `load_workbook` y las dos garantías de `AuxFileRef`). No es una
  desviación del alcance: es el ciclo que exige el nivel `estandar`. Detalle en
  `progress/mutacion_F-004.md`.

Ninguna desviación afecta a un requisito EARS: los 16 están implementados y
trazados.

---

## 7. Lo que NO se ha hecho, a propósito

- **No se carga nada a `aux.*`.** Frontera explícita de la spec: las tablas
  destino no existen y el esquema de los tres libros no está en el
  repositorio. Queda como **decisión abierta DA-1** en `progress/current.md`.
- **No se ha aprovisionado nada en Azure.** La cuenta de almacenamiento y el
  contenedor `aux` los crea **F-003**.
- **No se ha ejecutado `python main.py` en ninguna forma.** Hay una carga
  `run-all --full` corriendo contra el servidor compartido de producción desde
  este mismo repositorio (worktree `datamart-carga`) y `.env` apunta ahí.
- **No se ha instalado `azure-storage-blob` en el entorno del proyecto**, por
  la misma razón: `pip install` puede mover paquetes compartidos bajo los pies
  de un proceso de horas. Se verificó en un **venv aislado** (ver Evidencias).
- **No se ha corregido el hueco N3** (barrido de secretos de F-005) ni el
  punto 5 (falta de `exists()` en `build_stg`): son de otras features.

---

## 8. Verificaciones MANUAL pendientes (humano) — dependen de F-003

Las tres exigen la storage account y el contenedor `aux`, que **todavía no
existen**. Anotadas también en `progress/current.md` con su comando exacto.

1. Con `az login` y el rol `Storage Blob Data Reader`, apuntar
   `AUX_EXCEL_TIPO_PARTIDA` al blob real y ejecutar `python main.py load-aux`.
   Esperado: `SUCCESS`, `origen=blob`, hojas del libro en el detalle.
2. Desde el Container Apps Job con identidad gestionada: `az containerapp job
   start` y buscar el evento `aux_file_read` en los logs. Esperado: los tres
   ficheros leídos y **ninguna ruta local** en el log.
3. Prueba negativa: retirar el rol, ejecutar y comprobar que el error dice qué
   rol falta y qué hacer. Volver a asignarlo después.

---

## 9. Evidencias

Números medidos, no estimados.

| Evidencia | Valor | Cómo se obtuvo |
|---|---|---|
| **Tests ejecutados** | **221 pasan, 0 fallan** (166 antes de la feature: **+55**) | `python -m coverage run -m pytest -q` dentro de `bash harness/init.sh` |
| **Tiempo de la suite** | **2,85 s** | el que imprime pytest en esa misma ejecución |
| **Cobertura de líneas cambiadas** | **98,2 % (164/167)**, umbral 80 % | línea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados / muertos / supervivientes** | **27 / 25 / 2 → 92,6 %** | `python -m harness.mutacion --feature F-004` → `progress/mutacion_F-004.md` |
| **Veredicto del arnés** | `ENTORNO LISTO`, **exit code 0** | `bash harness/init.sh; echo $?` |
| **Avisos de ruff** | 127, **los mismos que antes de la feature** | `python -m ruff check . --output-format=concise` |

**Las 3 líneas sin cubrir** son el cuerpo de `_importar_sdk` (el `from
azure.identity import ...` real): el SDK no está instalado en este puesto y no
se ha instalado a propósito (§7). Se han verificado por otra vía, en un venv
aislado del proyecto:

```
$ <venv-aislado>/python -m pip install "azure-identity>=1.17" "azure-storage-blob>=12.20.0"
azure-identity 1.25.3 | azure-storage-blob 12.30.0 | azure-core 1.41.0
import OK: DefaultAzureCredential BlobClient

$ PYTHONPATH=<repo> <venv-aislado>/python -c "... BlobAuxFileSource()._cliente_por_defecto(ref) ..."
SDK real: azure.storage.blob._blob_client.BlobClient | azure.identity._credentials.default.DefaultAzureCredential
url  : https://stdatamartsegdev.blob.core.windows.net/aux/TipoPartida.xlsx
cuenta/contenedor/blob: stdatamartsegdev aux TipoPartida.xlsx
credencial: DefaultAzureCredential
```

Es decir: **el SDK real acepta los argumentos que construye el adaptador y
reconstruye exactamente la URI de partida**, con `DefaultAzureCredential` como
credencial. Es lo más cerca del extremo a extremo que se puede llegar sin la
cuenta de F-003 y sin abrir una conexión.

**Mutación · dos vueltas**: 27/21/6 (77,8 %) con los tests escritos tarea a
tarea, y 27/25/2 (92,6 %) tras cazar cuatro huecos que ni la fase RED ni el
98 % de cobertura habían detectado. Los 2 supervivientes finales son
`split(sep, 1)` → `split(sep, 2)` sobre un resultado del que solo se toma
`[0]`: **equivalentes por construcción**, ningún test puede cazarlos, y así
está razonado en `progress/mutacion_F-004.md`. La campaña se ejecutó en un
`git worktree` aparte —el árbol vivo tiene la carga corriendo— y se repitió
sobre el commit final con resultado idéntico.

## 10. Trazabilidad EARS → tests

| Req | Tests |
|---|---|
| R1 | `..._settings_declara_las_tres_variables...`, `..._la_misma_llamada_sirve_para_ruta_local_y_para_uri_de_blob`, `..._valor_vacio_es_error_de_configuracion` |
| R2 | `..._uri_de_blob_se_clasifica_como_blob_y_se_descompone`, `..._nombre_de_blob_con_subcarpetas_se_conserva_entero`, `..._el_esquema_https_no_distingue_mayusculas`, `..._la_referencia_es_inmutable_y_sin_diccionario` |
| R3 | `..._ruta_windows_posix_y_unc_se_clasifican_como_local` (5 casos), `..._lee_un_xlsx_real_del_sistema_de_ficheros`, `..._la_fabrica_devuelve_el_adaptador_local...`, `..._los_espacios_del_borde_no_cuentan` |
| R4 | `..._el_cliente_de_blob_se_construye_con_default_azure_credential`, `..._el_sdk_se_importa_de_forma_perezosa_y_es_el_oficial`, `..._sin_el_sdk_instalado_el_error_dice_como_arreglarlo`, `..._no_hay_cadenas_de_conexion_ni_claves_en_el_codigo` |
| R5 | `..._uri_https_ajena_a_blob_storage_es_error_de_configuracion`, `..._uri_http_sin_tls_es_error_de_configuracion` |
| R6 | `..._uri_con_sas_se_rechaza`, `..._el_mensaje_de_rechazo_no_filtra_el_token`, `..._el_fragmento_tambien_se_rechaza` |
| R7 | `..._uri_sin_contenedor_o_sin_blob_es_error_de_configuracion` (4 casos), `..._una_cuenta_vacia_tambien_se_rechaza` |
| R8 | `..._ruta_local_inexistente_produce_mensaje_accionable`, `..._un_directorio_en_vez_de_un_fichero_tambien_falla...` |
| R9 | `..._blob_inexistente_produce_mensaje_con_cuenta_contenedor_y_blob` |
| R10 | `..._error_de_permisos_menciona_el_rol_y_las_dos_salidas` (3 casos), `..._falta_de_credencial_menciona_az_login_e_identidad_gestionada`, `..._un_error_http_que_no_es_de_permisos_no_se_disfraza`, `..._un_error_nuestro_no_se_vuelve_a_envolver` |
| R11 | `..._el_step_abre_el_libro_desde_memoria_sin_ruta_existente`, `..._el_adaptador_de_blob_devuelve_bytes_sin_tocar_el_disco`, `..._el_libro_se_abre_en_solo_lectura_y_con_valores` |
| R12 | `..._los_tres_ficheros_legibles_dan_success_con_metadata`, `..._el_step_no_escribe_una_sola_fila_en_postgres` |
| R13 | `..._sin_variables_configuradas_el_step_queda_skipped`, `..._configuracion_parcial_lee_lo_configurado_y_lista_lo_omitido` |
| R14 | `..._fichero_ilegible_da_failed_nombrando_el_fichero`, `..._dos_fallos_se_reportan_los_dos_en_el_mismo_mensaje`, `..._una_variable_mal_configurada_tambien_es_failed`, `..._un_fallo_inesperado_de_la_fuente_se_atribuye_a_su_fichero` |
| R15 | `..._el_codigo_de_la_imagen_no_contiene_rutas_absolutas`, `..._el_barrido_caza_de_verdad_una_ruta_absoluta` |
| R16 | `..._los_directorios_sql_de_cada_capa_existen_en_el_paquete`, `..._los_steps_resuelven_sus_sql_relativos_al_paquete`, `..._los_yaml_de_configuracion_viven_bajo_config`, `..._el_dockerfile_copia_config_y_el_paquete_y_no_copia_env` |

## 11. Commits (uno por tarea)

```
49f0b79 F-004 T1: AuxExcelSettings admite ruta local o URI de blob y expone entries()
210fa9f F-004 T2: AuxFileRef, jerarquia de errores y parse_aux_file_ref (local vs blob)
a0708bc F-004 T3: puerto AuxFileSource, adaptador local con mensaje accionable y fabrica
5220489 F-004 T4: BlobAuxFileSource lee a memoria con DefaultAzureCredential ...
9f06cec F-004 T5: azure-storage-blob en requirements.txt (azure-identity ya estaba...)
e56c14c F-004 T6: el step load_excel_aux resuelve, lee en memoria y valida los tres Excels
0824b57 F-004 T7: auditoria automatizada de rutas absolutas y de lo que copia la imagen
af6478b F-004 T9: .env.example documenta ruta local y URI de blob, sin ruta personal ni SAS
4474c8d F-004 T10: ARCHITECTURE.md documenta la lectura de los Excels auxiliares
dad3d28 F-004 T10: ... sin falso positivo del barrido de secretos y test de no re-envolver
5052fed F-004 T11: tests contra los supervivientes de la campana de mutacion
635db3a F-004 T11: informe de mutacion analizado y avisos de ruff propios a cero
```

T8 (auditoría manual) y T11 (cierre) son documentales: viven en este informe y
en `progress/`. No se ha hecho `git push` ni se ha tocado `dev`. `features.json`
sigue con F-004 `in_progress`: moverlo a `done` es del líder, tras el APROBADO
del reviewer.
