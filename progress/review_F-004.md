<!-- progress/review_F-004.md -->
# F-004 · Ejecutar el ETL en Azure sin dependencias locales — Informe de review

Rama revisada: `feature/F-004-etl-sin-dependencias-locales` (verificada con
`git branch --show-current`). Base de integración: `dev`
(merge-base `4741db1`). HEAD revisado: `0321057`.

Fecha: 2026-08-09.

---

## Veredicto

## **APPROVED**

Los 16 requisitos EARS tienen test trazable y pasan, el arnés termina en verde
con la puerta de cobertura ejecutada, y las tres puertas del nivel `estandar`
—fase RED, cobertura y mutación— están cumplidas con evidencia. Los totales de
la campaña de mutación se han **recalculado de forma independiente** y
coinciden exactamente con el informe del implementer.

No hay cambios requeridos. Las observaciones del final son para el humano y
para features futuras, no condiciones de cierre.

---

## Nivel de rigor y puertas exigidas

`harness/features.json` declara para F-004 `"rigor": "estandar"` (valor válido
según `harness/rigor.json`, que expone los niveles `critico`, `documental` y
`estandar`, por defecto `critico` y umbral de cobertura 80 %). No se aplica el
nivel por omisión: está declarado.

`estandar` exige, según la tabla de `CHECKPOINTS.md`:

| Puerta | Exigida | Estado |
|---|---|---|
| C1–C3, C3 bis, C5 | Sí | Cumplidas |
| Tests trazables (C4) | Sí | 16/16 requisitos con >= 1 test |
| **Fase RED** en los requisitos centrales | Sí | Trazas literales en `impl_F-004.md` §4 |
| **Cobertura** de las líneas cambiadas >= 80 % | Sí | `[OK] 98.2 %` (164/167) |
| **Campaña de mutación** con supervivientes documentados y analizados | Sí | 27/25/2 = 92,6 %; los 2 analizados |
| Cero supervivientes | **No** (eso es `critico`) | 2 supervivientes, justificados como equivalentes |

---

## Verificaciones ejecutadas por el reviewer

Todas sin red y sin BBDD. **No se ha ejecutado `python main.py` en ninguna
forma**, ni se ha abierto conexión a Postgres o a `sigrid-api`: `.env` apunta
al servidor compartido de producción y hay una carga en curso desde otro
worktree. Tampoco se ha relanzado la campaña de mutación: la verificación de
sus totales es **cálculo puro**.

### 1. `bash harness/init.sh`

```
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 98.2% de 167 líneas cambiadas cubiertas
     (164/167, umbral 80%, nivel estandar)
[OK] Rama actual: feature/F-004-etl-sin-dependencias-locales
ENTORNO LISTO. Puedes trabajar.
EXIT=0
```

Ejecutado dos veces con resultado idéntico. La puerta de cobertura sale en
`[OK]` **con porcentaje**, no en `N/A`: es lo que exige C4 bis en rama de
feature.

Único aviso: `ruff: 127 avisos (deuda previa, no bloquea)`. Es el mismo número
que declara el implementer como línea base anterior a la feature, así que
F-004 no añade deuda de estilo.

### 2. `python -m pytest -q`

```
221 passed, 24 warnings in 1.77s
```

Cero fallos. Los 24 warnings son `DeprecationWarning` de
`datetime.utcnow()`, deuda previa compartida con `steps/base.py` y
`apply_grants_step.py` (F-005); no son de F-004 en exclusiva y no bloquean.

### 3. Tests trazables por requisito (recuento propio, `--collect-only`)

| Req | Tests | Req | Tests |
|---|---|---|---|
| R1 | 3 | R9 | 1 |
| R2 | 4 | R10 | 6 |
| R3 | 8 | R11 | 3 |
| R4 | 4 | R12 | 2 |
| R5 | 2 | R13 | 2 |
| R6 | 3 | R14 | 4 |
| R7 | 5 | R15 | 2 |
| R8 | 2 | R16 | 4 |

**16/16 requisitos cubiertos**, ninguno con cero tests. Total 55 tests
`test_f004_rN_*`, coherente con el `+55` que declara el implementer
(166 → 221).

### 4. Ningún test toca red ni BBDD

- Barrido de imports en `tests/test_f004_*.py` con el patrón
  `^\s*(import|from)\s+(azure|psycopg|httpx|socket|requests|urllib\.request)`:
  **ninguna coincidencia**.
- Las únicas menciones a `azure` en los tests son (a) docstrings de dobles
  homónimos de las excepciones del SDK y (b) aserciones de texto sobre el
  código fuente del import perezoso (`inspect.getsource`). Ninguna importa
  nada del SDK.
- Prueba definitiva: **el SDK de Azure ni siquiera está instalado en este
  entorno**. Comprobado por el reviewer:
  `azure.identity NO instalado -> ModuleNotFoundError`,
  `azure.storage.blob NO instalado -> ModuleNotFoundError`. Con 221 tests en
  verde, es imposible que alguno haya hablado con Azure.
- Los dobles se inyectan en el límite (`source_factory` en el step,
  `blob_client_factory` e `importar_sdk` en el adaptador). **No se parchea
  `sys.modules`** ni ningún módulo de terceros, que es lo que prohibía
  `tasks.md`.

### 5. R6 verificado a mano por el reviewer

No me he fiado del test: he llamado yo a `parse_aux_file_ref` con una URI que
lleva un SAS completo (`sv=...&sig=SUPERSECRETO%2Fabc%3D&se=...`). El mensaje
producido es:

```
La variable AUX_EXCEL_TIPO_PARTIDA (Excel auxiliar 'tipo_partida') lleva
parámetros tras la URI
'https://stcuenta.blob.core.windows.net/aux/TipoPartida.xlsx'. No se admiten
tokens SAS ni claves: el ETL lee los blobs con identidad gestionada, ...
```

Comprobaciones sobre ese texto: contiene `?` → **False**; contiene `sig=` →
**False**; contiene `sv=` → **False**; contiene `SUPERSECRETO` → **False**;
contiene el token entero → **False**.

Probados además los dos caminos vecinos, porque un corte que solo funciona en
un sitio no es un corte:

- URI con **fragmento** (`#sig=OTROSECRETO`): rechazada, y el mensaje no
  filtra el secreto.
- URI con host **ajeno** a Blob Storage y query (`https://evil.example.com/...?sig=FUGA`):
  R5 la rechaza como error de configuración, y tampoco filtra.

La razón estructural: `_sin_secretos()` corta antes de `?` y de `#`, y
`AuxFileRef.display` nunca devuelve la URI cruda —solo
`blob: <cuenta>/<contenedor>/<blob>`—, así que el token no puede llegar al log
por la vía del step tampoco.

### 6. Arquitectura hexagonal

- `etl_sigrid/domain/` **no se toca** en toda la rama (confirmado en el
  `--stat`): el dominio sigue sin imports de infraestructura.
- La lectura de blob es **un adaptador de infraestructura**:
  `etl_sigrid/infrastructure/excel/blob_aux_file_source.py`, con el puerto
  (`AuxFileSource`, `Protocol`) y el adaptador local en `aux_file_source.py`,
  en el paquete `infrastructure/excel/` que ya existía.
- **El step NO importa el SDK de Azure.** Sus imports son `openpyxl`,
  `config.settings`, `steps.base`, `domain.entities`, el puerto
  `aux_file_source` y `logging_config`. Ni `azure.identity` ni
  `azure.storage.blob` aparecen en la capa de aplicación.
- El import del adaptador de blob es **perezoso y localizado**: dentro de
  `get_aux_file_source()` (línea 212) y dentro de `_importar_sdk()`
  (`blob_aux_file_source.py:48-49`), única función que toca el SDK real.
- Contrastado con `docs/ARCHITECTURE.md`, que la rama actualiza en su sección
  «Acceso a datos» describiendo exactamente esto («el step `load_excel_aux` no
  sabe de Azure»). Documento y código coinciden.
- SQL: **F-004 no crea ni modifica un solo fichero** bajo
  `infrastructure/postgres/sql/**`. El checkpoint de numeración `NN_nombre.sql`
  no tiene nada que evaluar aquí.

### 7. Verificación INDEPENDIENTE de la campaña de mutación

Es la exigencia nueva del paso 4 del protocolo, y es donde un informe escrito
a mano se caería. Recalculado por el reviewer con cálculo puro
(`harness.alcance.alcance_de_feature` + `harness.mutacion.generar_mutantes`),
sin ejecutar la suite y sin escribir en disco:

**Alcance** — recalculado vs. declarado en `progress/mutacion_F-004.md`:

| Fichero | Informe | Recalculado | ¿Coincide? |
|---|---|---|---|
| `config/settings.py` | 34 | 34 | Sí |
| `etl_sigrid/application/steps/load_excel_aux_step.py` | 133 | 133 | Sí |
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | 215 | 215 | Sí |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | 145 | 145 | Sí |
| **Total** | **527** | **527** | **Sí** |

**Número de mutantes**: informe 27, recalculado **27**. Desglose por fichero
(`settings` 1, `load_excel_aux_step` 5, `aux_file_source` 17,
`blob_aux_file_source` 4), suma 27.

**Muestreo de supervivientes** (los 2 declarados, en
`aux_file_source.py:81`). Ambos existen como mutantes reales, con el **mismo
operador** (`entero`) y el **mismo texto original→mutado** que dice el
informe:

| # | Informe | Generador (col) | ¿Coincide? |
|---|---|---|---|
| 1 | `split("?", 1)` → `split("?", 2)` | col 28, op `entero` | Sí |
| 2 | `split("#", 1)` → `split("#", 2)` | col 45, op `entero` | Sí |

Y la afirmación de que las mutaciones **peligrosas** de esa misma línea sí
murieron es comprobable: el generador produce también `[0]` → `[1]` en los dos
troceos (cols 31 y 48), y **no** figuran entre los supervivientes. Son
precisamente las que filtrarían el token SAS al mensaje de error (R6), y están
muertas.

**Análisis de la equivalencia, hecho por mí y no aceptado por confianza**: la
función devuelve `valor.split(sep, n)[0]`. El primer elemento de un `split` es
idéntico para cualquier `maxsplit >= 1`, porque el separador que delimita ese
primer trozo es siempre el primero. Los dos mutantes son **equivalentes por
construcción**: ningún test puede matarlos sin congelar un detalle interno que
nadie observa. La justificación del informe es correcta.

Ninguna sección de superviviente queda en `PENDIENTE`.

### 8. Convenciones (`docs/CONVENTIONS.md`)

- **Primera línea con la ruta relativa**: verificada en los 7 ficheros Python
  nuevos o modificados. Los 7 la tienen y es correcta.
- **Type hints**: presentes en todas las firmas nuevas
  (`parse_aux_file_ref(...) -> AuxFileRef`, `read_bytes(...) -> bytes`,
  `entries() -> tuple[tuple[str, str, str], ...]`, `run() -> StepResult`,
  `_traducir(...) -> AuxFileError`), con `from __future__ import annotations`
  en los tres módulos.
- **Sin `print()` de debug**: barrido `^\s*print\(` sobre el código nuevo →
  ninguna coincidencia. El log va por `structlog` (`get_logger`), con eventos
  estructurados `aux_file_read` / `aux_files_done` / `aux_files_failed` /
  `aux_files_skipped`.
- **Sin TODOs sin contexto**: la única coincidencia del barrido
  `TODO|FIXME|XXX` es la palabra española «TODOS» dentro de un docstring
  (`load_excel_aux_step.py:18`). Falso positivo.
- **Sin secretos hardcodeados**: no hay cadenas de conexión, claves de cuenta
  ni SAS en el código —es justo lo que el diseño rechaza por construcción—.
  `.env.example` **mejora** en esto: la rama sustituye la ruta personal de
  OneDrive del humano por `D:/datos/aux/...` y añade el perfil de blob con
  marcadores `<cuenta>`, sin valores reales. `stdatamartsegdev` aparece solo
  en tests y documentos como nombre de cuenta de ejemplo; no es un secreto.
- **Dependencias nuevas previstas en la spec**: sí. `azure-storage-blob>=12.20.0`
  está justificada en `design.md` §7. `azure-identity` no se duplica porque ya
  estaba desde F-005 (desviación D1, correcta: el diff solo amplía su
  comentario para documentar los dos usos). No entra ninguna dependencia que
  la spec no previera.

### 9. Diff contra `design.md`: ¿solo los ficheros previstos?

`git diff dev...HEAD --stat` → 15 ficheros. Contrastados uno a uno con
`design.md` §2 y §3:

| Fichero | Previsto en | Veredicto |
|---|---|---|
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | §2 crear | Correcto |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | §2 crear | Correcto |
| `tests/test_f004_aux_file_source.py` | §2 crear | Correcto |
| `tests/test_f004_load_excel_aux_step.py` | §2 crear | Correcto |
| `tests/test_f004_sin_dependencias_locales.py` | §2 crear | Correcto |
| `etl_sigrid/application/steps/load_excel_aux_step.py` | §3 modificar | Correcto |
| `config/settings.py` | §3 modificar | Correcto |
| `requirements.txt` | §3 modificar | Correcto (ver D1) |
| `.env.example` | §3 modificar | Correcto |
| `docs/ARCHITECTURE.md` | §3 modificar | Correcto |
| `specs/.../tasks.md` | tareas marcadas | Correcto |
| `harness/features.json` | estado de la feature | Correcto (lo mueve el líder) |
| `progress/current.md`, `impl_F-004.md`, `mutacion_F-004.md` | memoria del arnés | Correcto |

**Nada de lo que `design.md` §4 declara fuera de alcance ha sido tocado**:
verificado en el `--stat` que no aparecen `orchestrator.py`, `steps/base.py`,
los otros cinco steps, ningún `.sql`, `postgres_client.py`, `Dockerfile`,
`infra/**` ni `main.py`. La compatibilidad de `main.py` se sostiene porque el
parámetro nuevo del constructor es *keyword-only* con valor por defecto.

Las cuatro desviaciones declaradas (D1 `azure-identity` no duplicada, D2
parámetro `importar_sdk` inyectable, D3 sin rutas absolutas de ejemplo en los
mensajes, D4 cuatro tests añadidos tras la primera vuelta de mutación) están
documentadas, son razonables y **ninguna afecta a un requisito EARS**. D2 en
particular es lo que permite verificar R4 sin parchear `sys.modules`, que era
una prohibición explícita de `tasks.md`: es una desviación que mejora el
cumplimiento, no que lo relaja.

---

## Checkpoints (`CHECKPOINTS.md`)

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0. Verificado: `EXIT=0`.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`. Los comprueba el propio `init.sh`, todos `[OK]`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress`: `init.sh` imprime
      `16 features, 10 abiertas, en curso: ['F-004'], bloqueadas: ninguna`.
- [x] La rama actual es `feature/F-004-etl-sin-dependencias-locales`, la de la
      feature en curso y la declarada en su entrada de `features.json`. No es
      `main` ni `dev`.
- [x] `progress/current.md` describe la sesión activa: F-004 implementada y
      pendiente de revisión, F-005 fase 2 con la carga **en ejecución ahora**,
      F-015 cerrada el mismo día y el rumbo confirmado por el humano. No son
      restos de sesiones anteriores: es el estado vivo del 2026-08-09.
- [x] Toda feature `done` tiene su resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones

- [x] Dominio sin imports de infraestructura (`etl_sigrid/domain/` intacto).
      SQL en su capa: **N/A por ausencia**, F-004 no añade ni modifica un solo
      `.sql`, como fija `design.md` §6. Justificado: no hay artefacto SQL que
      colocar en una capa equivocada.
- [x] Primera línea de cada fichero Python con su ruta relativa: 7/7.
- [x] Sin `print()` de debug, sin TODOs sin contexto, sin secretos
      hardcodeados, sin dependencias nuevas no previstas en la spec.
- [x] Semántica Sigrid (amb/fas, `importe_origen` vs `importe_mes`, `fasnum`
      vs `fas`): **N/A justificado**. F-004 no toca modelo de datos, ni SQL,
      ni ninguna entidad de negocio de Sigrid: lee tres ficheros y comprueba
      que abren. No hay semántica que respetar o violar.

### C3 bis — Los documentos que entran de fuera son seguros

**N/A, justificado por escrito**: F-004 **no añade ni modifica ningún fichero
en `docs/referencia/`**. Verificado sobre el diff completo de la rama
(`git diff dev...HEAD --name-only | grep docs/referencia` → sin
coincidencias), y sobre los ficheros añadidos
(`git diff dev...HEAD --diff-filter=A`): los 7 son dos módulos Python, tres
ficheros de test y dos informes de `progress/`. **Ningún PDF ni documento
ofimático entra en la rama**, ni ahora ni en ningún commit intermedio. El
checkpoint no tiene objeto que evaluar.

Aun así, y como el barrido de datos sensibles lo ejecuta el reviewer, he
mirado el único documento modificado (`docs/ARCHITECTURE.md`, +14 líneas) y
los dos ficheros de configuración de ejemplo. Resultado: sin correos, sin IP,
sin GUID de suscripción o tenant, sin credenciales ni tokens. `.env.example`
**pierde** un dato personal que antes tenía (la ruta de OneDrive del humano) y
usa marcadores `<cuenta>`.

### C4 — La verificación es real

- [x] Cada requisito EARS tiene >= 1 test trazable `test_f004_rN_*` y todos
      pasan: 16/16 requisitos, 55 tests, 221 en la suite completa, 0 fallos.
- [x] Los unit tests no tocan red ni BBDD: barrido de imports sin
      coincidencias, dobles inyectados en el límite, y el SDK de Azure ni
      siquiera está instalado en el entorno donde pasan los 221.
- [x] Las verificaciones `MANUAL (humano)` están listadas en
      `progress/current.md` con su comando exacto, pendientes del humano. Son
      las tres de `requirements.md`, anotadas bajo el epígrafe
      «**BLOQUEADAS hasta F-003**» con `python main.py load-aux`,
      `az containerapp job start -n <job> -g <rg>` y la prueba negativa de
      retirada del rol. **No se han ejecutado en esta review**, como ordenaba
      el encargo: dependen de la storage account que crea F-003.

### C4 bis — El rigor declarado se cumple

- [x] La feature declara `rigor: "estandar"` en `harness/features.json`, valor
      válido para `harness/rigor.json`. No se aplica el nivel por omisión.
- [x] **Fase RED**: `progress/impl_F-004.md` §4 trae la **salida real** del
      fallo previo al código para T1 (`AttributeError: 'AuxExcelSettings'
      object has no attribute 'entries'`), T2 y T4 (`ModuleNotFoundError`), T3
      (`ImportError: cannot import name 'LocalAuxFileSource'`), T6
      (`TypeError: ... unexpected keyword argument 'source_factory'`) y T7
      (la `AssertionError` del barrido de rutas). No es «se siguió TDD»: son
      trazas pegadas, con el comando que las produjo y el conteo de tests. Dos
      de esos rojos además **corrigieron cosas** (el mensaje de R14 sin
      ubicación, y el patrón UNC que cazaba el escapado de `bytea`), que es la
      señal de que la fase RED fue real y no reconstruida.
- [x] **Cobertura**: `bash harness/init.sh` sale en
      `[OK] PUERTA COBERTURA: 98.2% de 167 líneas cambiadas cubiertas
      (164/167, umbral 80%, nivel estandar)`. Con porcentaje, no en `N/A`.
      Las 3 líneas sin cubrir son el cuerpo de `_importar_sdk` (el `from
      azure...` real), imposible de cubrir sin instalar el SDK, y están
      verificadas por otra vía documentada (venv aislado).
- [x] **Mutación**: existe `progress/mutacion_F-004.md`, generado por
      `python -m harness.mutacion --feature F-004`, con totales reales
      **verificados de forma independiente por el reviewer**: alcance 527
      líneas y 27 mutantes recalculados con `harness.alcance` y
      `harness.mutacion.generar_mutantes` (cálculo puro, sin ejecutar la suite
      ni escribir en disco), coincidencia exacta fichero a fichero. Detalle en
      la sección 7.
- [x] Cada superviviente tiene su análisis **completado**, ninguno en
      `PENDIENTE`: los 2 son `split(sep, 1)` → `split(sep, 2)` sobre un
      resultado del que solo se toma `[0]`, equivalentes por construcción, y
      he verificado yo la equivalencia además de muestrear que existen como
      mutantes reales con el mismo operador y texto. El nivel `estandar` **no**
      exige cero supervivientes (eso es `critico`), así que dos equivalentes
      justificados no bloquean.
- [x] El informe del implementer trae la sección **«Evidencias»** (§9) con los
      cuatro números: tests ejecutados y resultado (221 pasan, 0 fallan, +55),
      cobertura de las líneas cambiadas (98,2 %, 164/167), mutantes y
      supervivientes (27 / 25 muertos / 2 supervivientes, 92,6 %) y tiempo de
      la suite (2,85 s; en mi ejecución, 1,77 s).
- [x] Ningún punto de este bloque marcado N/A. Los dos N/A del informe (C3 bis
      y dos viñetas de C3) están justificados por escrito arriba, y ninguno es
      una puerta de verificación.

### C5 — La sesión se cerró bien

- [x] `tasks.md` con las **11 tareas marcadas `[x]`** y un commit por tarea con
      el formato `F-004 Tn: ...`. Verificado en `git log dev..HEAD`: T1 a T7,
      T9, T10 (dos commits), T11 (dos commits) y T8 en el commit final
      `F-004 T8+T11: ...`. Todas las tareas tienen commit; T8 y T11 son
      documentales y su producto vive en `progress/`, como declaraba la spec.
- [x] Sin ficheros temporales ni artefactos sin trackear:
      `git status --porcelain` **vacío**. El worktree de la campaña de
      mutación se creó y se eliminó, y no ha dejado rastro en el árbol.
- [x] `features.json` refleja el estado real: F-004 sigue `in_progress`.
      Moverla a `done` es del líder, tras este APROBADO.

**Ningún checkbox vacío en C1–C5.**

---

## Cobertura: requisito → test que lo cubre

| Req | Qué exige | Test(s) que lo cubren | Estado |
|---|---|---|---|
| R1 | Resolver los tres Excels sin que el llamante sepa el origen | `test_f004_r1_settings_declara_las_tres_variables_con_su_nombre_de_entorno`, `test_f004_r1_la_misma_llamada_sirve_para_ruta_local_y_para_uri_de_blob`, `test_f004_r1_valor_vacio_es_error_de_configuracion` | Pasa |
| R2 | URI de blob → se lee de Blob Storage, descompuesta | `test_f004_r2_uri_de_blob_se_clasifica_como_blob_y_se_descompone`, `test_f004_r2_nombre_de_blob_con_subcarpetas_se_conserva_entero`, `test_f004_r2_el_esquema_https_no_distingue_mayusculas`, `test_f004_r2_la_referencia_es_inmutable_y_sin_diccionario` | Pasa |
| R3 | Windows / POSIX / UNC → sistema de ficheros local | `test_f004_r3_ruta_windows_posix_y_unc_se_clasifican_como_local` (5 casos), `test_f004_r3_lee_un_xlsx_real_del_sistema_de_ficheros`, `test_f004_r3_la_fabrica_devuelve_el_adaptador_local...`, `test_f004_r3_los_espacios_del_borde_no_cuentan` | Pasa |
| R4 | `DefaultAzureCredential`, sin cadena, clave ni SAS | `test_f004_r4_el_cliente_de_blob_se_construye_con_default_azure_credential`, `test_f004_r4_el_sdk_se_importa_de_forma_perezosa_y_es_el_oficial`, `test_f004_r4_sin_el_sdk_instalado_el_error_dice_como_arreglarlo`, `test_f004_r4_no_hay_cadenas_de_conexion_ni_claves_en_el_codigo` | Pasa |
| R5 | Host `https` ajeno a Blob Storage → error de config | `test_f004_r5_uri_https_ajena_a_blob_storage_es_error_de_configuracion`, `test_f004_r5_uri_http_sin_tls_es_error_de_configuracion` | Pasa |
| R6 | SAS rechazado y **sin filtrar el token** | `test_f004_r6_uri_con_sas_se_rechaza`, `test_f004_r6_el_mensaje_de_rechazo_no_filtra_el_token`, `test_f004_r6_el_fragmento_tambien_se_rechaza` — **más la comprobación propia del reviewer** (sección 5) | Pasa |
| R7 | URI sin contenedor y blob → error con la forma esperada | `test_f004_r7_uri_sin_contenedor_o_sin_blob_es_error_de_configuracion` (4 casos), `test_f004_r7_una_cuenta_vacia_tambien_se_rechaza` | Pasa |
| R8 | Fichero local ausente → mensaje accionable | `test_f004_r8_ruta_local_inexistente_produce_mensaje_accionable`, `test_f004_r8_un_directorio_en_vez_de_un_fichero_tambien_falla...` | Pasa |
| R9 | Blob ausente → cuenta, contenedor y blob en el mensaje | `test_f004_r9_blob_inexistente_produce_mensaje_con_cuenta_contenedor_y_blob` | Pasa |
| R10 | Permisos → rol `Storage Blob Data Reader` y las dos salidas | `test_f004_r10_error_de_permisos_menciona_el_rol_y_las_dos_salidas` (3 casos), `test_f004_r10_falta_de_credencial_menciona_az_login_e_identidad_gestionada`, `test_f004_r10_un_error_http_que_no_es_de_permisos_no_se_disfraza`, `test_f004_r10_un_error_nuestro_no_se_vuelve_a_envolver` | Pasa |
| R11 | Todo en memoria, sin temporales | `test_f004_r11_el_step_abre_el_libro_desde_memoria_sin_ruta_existente`, `test_f004_r11_el_adaptador_de_blob_devuelve_bytes_sin_tocar_el_disco`, `test_f004_r11_el_libro_se_abre_en_solo_lectura_y_con_valores` | Pasa |
| R12 | Tres legibles → `SUCCESS` con metadata por fichero | `test_f004_r12_los_tres_ficheros_legibles_dan_success_con_metadata`, `test_f004_r12_el_step_no_escribe_una_sola_fila_en_postgres` | Pasa |
| R13 | Ninguna configurada → `SKIPPED`; parcial → lee y lista | `test_f004_r13_sin_variables_configuradas_el_step_queda_skipped`, `test_f004_r13_configuracion_parcial_lee_lo_configurado_y_lista_lo_omitido` | Pasa |
| R14 | Fallo → `FAILED` listando **todos** los problemáticos | `test_f004_r14_fichero_ilegible_da_failed_nombrando_el_fichero`, `test_f004_r14_dos_fallos_se_reportan_los_dos_en_el_mismo_mensaje`, `test_f004_r14_una_variable_mal_configurada_tambien_es_failed`, `test_f004_r14_un_fallo_inesperado_de_la_fuente_se_atribuye_a_su_fichero` | Pasa |
| R15 | Sin rutas absolutas en el código que viaja en la imagen | `test_f004_r15_el_codigo_de_la_imagen_no_contiene_rutas_absolutas`, `test_f004_r15_el_barrido_caza_de_verdad_una_ruta_absoluta` | Pasa |
| R16 | Todo lo que se resuelve en ejecución vive en la imagen | `test_f004_r16_los_directorios_sql_de_cada_capa_existen_en_el_paquete`, `test_f004_r16_los_steps_resuelven_sus_sql_relativos_al_paquete`, `test_f004_r16_los_yaml_de_configuracion_viven_bajo_config`, `test_f004_r16_el_dockerfile_copia_config_y_el_paquete_y_no_copia_env` | Pasa |

Mención aparte para dos tests que elevan la calidad por encima del mínimo:
`test_f004_r15_el_barrido_caza_de_verdad_una_ruta_absoluta` —un test de
auditoría que comprueba que **sabe fallar**, sin lo cual no vigila nada— y
`test_f004_r4_el_sdk_se_importa_de_forma_perezosa_y_es_el_oficial`, que
verifica por `inspect.getsource` que el import perezoso es el del SDK real,
que es lo único que un doble no puede fingir.

---

## Cambios requeridos

**Ninguno.** El veredicto es APPROVED sin condiciones.

---

## Observaciones para el humano (no bloquean el cierre)

1. **Las tres verificaciones MANUAL siguen pendientes y son reales.** Están
   correctamente anotadas en `progress/current.md` como bloqueadas hasta
   F-003, que es lo que exige C4, y no se han ejecutado. Pero conviene no
   perderlas de vista: hasta que alguien lea un blob de verdad, R4, R9 y R10
   están verificados **contra dobles**, no contra Azure. El implementer llegó
   todo lo lejos que se podía sin la cuenta —comprobó en un venv aislado que
   el SDK real acepta los argumentos que construye el adaptador y reconstruye
   la URI de partida—, y eso es lo correcto, pero no sustituye a la prueba.
   **Recomendación: engancharlas como criterio de aceptación de F-003**, que
   es quien crea la cuenta, en vez de dejarlas en una lista aparte.
2. **Dependencia hacia F-003 que puede morderse en silencio**: si el job no
   usa identidad *system-assigned*, F-003 debe inyectar `AZURE_CLIENT_ID` en
   el entorno del contenedor. `DefaultAzureCredential` lo lee solo, pero
   alguien tiene que ponerlo, y su ausencia no se manifiesta hasta la primera
   lectura de blob. Ya está anotado en `current.md`; lo repito aquí porque es
   el fallo más probable del primer arranque en Azure.
3. **Falso positivo del barrido de secretos de F-005** (hallazgo N3 del
   implementer): `test_f005_r21_barrido_de_secretos_en_el_arbol` puso `init.sh`
   en rojo porque su patrón de base64 (`[A-Za-z0-9+/]{24,}`) casó con la ruta
   `sigrid/infrastructure/excel/` en un texto en prosa. El implementer hizo lo
   correcto —**no tocó el test de otra feature**, reformuló su propia frase— y
   lo anotó para **F-016**. Confirmo el diagnóstico: un barrido que obliga a
   reescribir prosa inocente acabará desactivado por alguien con prisa. En
   F-016, exigir contexto de asignación o excluir cadenas con varias barras.
4. **Deuda previa que F-004 no aumenta pero tampoco resuelve**: los 127 avisos
   de `ruff` y los 24 `DeprecationWarning` de `datetime.utcnow()`. El segundo
   tiene fecha de caducidad real (`utcnow` está marcado para retirada) y afecta
   a `steps/base.py`, que es común a todos los steps. Candidato a una feature
   de mantenimiento propia; fuera del alcance de F-004.
5. **Punto 5 de la auditoría, consciente y sin corregir**: `build_stg_step` es
   el único de los cuatro `build_*` que no comprueba `sql_path.exists()` antes
   de ejecutar. La spec lo declaró fuera de alcance y el implementer lo
   respetó, que es lo correcto. Queda como candidato a backlog.

---

## Automejora del protocolo (propuesta, NO aplicada)

La exigencia nueva del paso 4 —verificar los totales de mutación de forma
independiente— **ha funcionado y merece quedarse**: recalcular alcance y
mutantes cuesta un comando, es cálculo puro y compatible con un entorno donde
está prohibido ejecutar nada pesado, y convierte «el informe dice 27» en «he
contado 27». En esta review el resultado fue coincidencia exacta, pero el
valor está en que la comprobación existe, no en que saliera bien.

Dos afinados que propongo al humano, para `.claude/agents/reviewer.md` y/o
`CHECKPOINTS.md`, sin aplicarlos yo:

1. **Pedir explícitamente el contraste de las mutaciones MUERTAS de la misma
   línea que un superviviente.** El muestreo actual verifica que los
   supervivientes existen; lo que de verdad cierra el hueco es comprobar que
   las mutaciones *peligrosas* vecinas —aquí, `[0]` → `[1]`, la que filtraría
   el token SAS— **no** están entre ellos. Un informe amañado listaría como
   «equivalente» justo la mutación que sí cambia el comportamiento, y el
   muestreo tal como está redactado no obliga a mirarlo. Es una línea más de
   protocolo y sube bastante el listón.
2. **Añadir a C4 una comprobación de que la suite no puede tocar red aunque
   quisiera.** En esta feature la prueba más contundente no fue el barrido de
   imports, sino constatar que **el SDK de Azure no está instalado** y aun así
   pasan los 221 tests. Sugerencia: donde el checkpoint dice «los unit tests
   no tocan red ni BBDD (mocks/fixtures)», añadir «y el reviewer deja
   constancia de *cómo* lo comprobó: barrido de imports, ausencia del SDK, o
   ambos». Evita que ese checkbox se marque por lectura del informe ajeno.
