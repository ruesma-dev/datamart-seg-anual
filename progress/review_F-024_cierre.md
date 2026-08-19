<!-- progress/review_F-024_cierre.md -->
# F-024 · Review de CIERRE — la Fase C contra R23–R26

**Fecha:** 2026-08-19 · **Rama:** `feature/F-024-coherencia-cargas-truncadas`
**Alcance de esta pasada:** SOLO la Fase C (T17–T20, requisitos `[MANUAL]`
R23, R24, R25 y R26) y los checkpoints de cierre.
**Fuera de alcance, por indicación expresa y porque ya están aprobados:** el
código de la Fase B (`progress/review_F-024.md`, APPROVED en segunda pasada) y
el arreglo de la ventana de la alerta (`progress/review_F-024_T19_ventana.md`,
APPROVED en segunda pasada). No los he vuelto a revisar.

## Veredicto

> ## APPROVED

Aprobado **en sustancia**: las cuatro verificaciones manuales están ejecutadas
y su resultado real está escrito. Queda un punto abierto —el `Deactivated` de
R23— que argumento abajo en detalle, y una lista de **apuntes de cierre
obligatorios antes de marcar `done`** (§7). El `done` sin esos apuntes deja
C2 y C5 incumplidos: la aprobación es del trabajo, no un permiso para saltarse
el cierre.

**Nivel de rigor:** `critico`, declarado en `harness/features.json`. Exige
C1–C5 + C3 bis, fase RED, cobertura ≥ 80 % de las líneas cambiadas, campaña de
mutación con **cero supervivientes salvo justificación aceptada por el humano**,
y **verificaciones `MANUAL (humano)` listadas con su comando exacto y su
resultado real**. Es esta última la que decide esta pasada.

---

## 1 · Lo que he verificado por mi cuenta (no me he fiado del informe)

| Comprobación | Resultado |
|---|---|
| `bash harness/init.sh` | **verde**. 617 tests, `ENTORNO LISTO` |
| `PUERTA COBERTURA` | **[OK] 100.0 % de 372 líneas cambiadas (372/372, umbral 80 %, nivel critico)** |
| Alcance de mutación recalculado (`harness.alcance`) | 12 ficheros, mismo `merge-base` `1f3d5df` que declara el informe |
| Nº de mutantes recalculado (`harness.mutacion.generar_mutantes`, cálculo puro) | **108**, idéntico al informe. Reparto por fichero: coherencia 30, postgres_client 26, main 20, frescura 14, timings 7, build_mart 4, build_stg 4, ejecucion 3 |
| Muestreo de supervivientes | los dos (`main.py:564` y `main.py:567`, operador `booleano`, `bold=True → bold=False`) **existen como mutantes reales**, con el mismo operador y el mismo texto original→mutado que declara `progress/mutacion_F-024.md` |
| Código tocado desde el último APPROVED (`9701a7c..HEAD`) | **ninguno**: solo `BACKLOG.md`, `harness/features.json`, `progress/decisiones_abiertas.md` y `progress/manual_F-024_fase_c.md`. No hay código nuevo sin revisar |
| Barrido de datos sensibles sobre los ficheros de `docs/referencia/` que aparecen en el diff | **limpio** (patrones: IPv4, GUID, correos, `password/secret/token/api-key/subscription-id/tenant-id`, `Bearer`). Además esos dos ficheros no los escribe F-024: entran por el merge de `dev` (commit `7d00640`) |
| Originales PDF/ofimática añadidos en la rama | **ninguno** |
| Secretos en las líneas añadidas de `infra/`, `etl_sigrid/`, `main.py`, `config/`, `specs/` | **ninguno** |

No he tocado Azure: ni una lectura ni una escritura. No he lanzado ninguna
campaña de mutación (el número lo he verificado con el cálculo puro, que no
ejecuta la suite ni escribe en disco; y la campaña completa ya la corrí yo en
la pasada anterior: 108/106/2).

---

## 2 · R25 — despliegue y huérfanas cerradas · **CUMPLIDO**

Evidencia: `progress/manual_F-024_fase_c.md`, secciones de T17.

| Lo que pide R25 | Resultado real |
|---|---|
| Imagen con F-024 desplegada en el job | `r20260818-2146`, digest `sha256:f0b3270…0391b7`; job actualizado desde `r20260818-1003` con disparo `Schedule` intacto |
| Las filas `RUNNING` del 18-ago quedan `ABORTED` **con motivo** | **Sí**, y con el antes/después de la misma tabla: la foto previa las retrata `RUNNING` con el aviso «2 fila(s) RUNNING desde hace más de 6 h»; tras `apply-grants` salen `ABORTED` y **el aviso desaparece del pie** |
| El motivo dice qué pasó, causa probable, quién y cuándo | **Sí**, texto pegado entero: «huérfana: el proceso que la abrió no la cerró —muerte externa: deadline, OOM o reinicio—; marcada por la ejecución `20260818T194921Z-09f6b1` el 2026-08-18 19:49:21» |
| `mcp_sigrid_dm_ro` puede leer `_meta.v_frescura` y `_meta.v_raw_state` | **Sí**, verificado por catálogo (§7 del cuaderno) |

Dos desviaciones respecto a la letra de R25, las dos **aceptadas y anotadas**:

1. **R25 nombra `build_stg.build_plan_mensual.tramo_39`; la huérfana real era
   `tramo_40`.** Es una errata de la spec, no de la ejecución: la evidencia
   demuestra lo que R25 quería demostrar (las dos filas `RUNNING` del 18-ago
   cerradas con motivo) y encima cerró **cinco más** del pasivo de los días 9 y
   14, que nadie sabía que estaban abiertas. Recomiendo corregir el número en
   `requirements.md` para que el registro no se contradiga con la evidencia.
2. **La sesión `psql` real como `mcp_sigrid_dm_ro` no se hizo**; el permiso se
   verificó con `has_schema_privilege` / `has_table_privilege` e
   `information_schema` desde la conexión de la aplicación. **Lo acepto como
   equivalente**: esas funciones responden *por el rol indicado*, que es la
   misma fuente que consulta el motor al autorizar; si faltara el `GRANT`
   saldría `False`. Lo único que no cubre es la conectividad del MCP
   (contraseña vigente, firewall, `sslmode`), que no es de F-024. Y el motivo
   por el que no se hizo es el correcto: leer el secreto del Key Vault quedó
   denegado y **no se buscó una vía alternativa**, que es exactamente la
   conducta debida ante una denegación de seguridad.

---

## 3 · R24 — muerte externa controlada · **CUMPLIDO, y es la mejor evidencia de la feature**

Los cinco pasos de R24 tienen su comando y su salida real. Lo verifico punto
por punto contra el enunciado:

| Paso de R24 | Exigido | Resultado real |
|---|---|---|
| 1–2 | lanzar como el cron y matar a los ~10 min con la ingesta en `raw` | job `caj-datamart-seg-dev-cay0s53` arrancado 10:10:19 UTC, matado 10:20:32 UTC con los logs enseñando `obrparpre` página 842. Estado `Stopped` |
| 3 | `timings` enseña `RUNNING`; `check-coherencia` KO y sale 1 | `ingest_raw.obrparpre … RUNNING`, sin aviso de 6 h (llevaba 6 min: correcto). `check-coherencia` KO con **las dos causas separadas y nombradas** (último intento no `SUCCESS` + batches distintos), salida 1 |
| 4 | `stage` sale 1, `FAILED` en `build_stg.puerta_raw`, **ningún `TRUNCATE` en `stg`**; las `RUNNING` pasan a `ABORTED`; `check-frescura` sigue FRESCO | las tres garantías en una sola ejecución: huérfana cerrada con el `batch_id` de quien la cerró, `puerta_raw_ko` con `no_exitosas=['obrparpre']`, **`rows=0` en 5,2 s** (no hubo build ni truncado) y `check-frescura` FRESCO con salida 0 |
| 5 | recarga completa → `check-coherencia` OK, frescura con hora nueva, buzón sin `Activated` | `caj-datamart-seg-dev-lf64bpa` `Succeeded` a las 13:10:49 UTC (2 h 45). `check-coherencia` OK **con una sola identidad de ejecución** (`20260819T102544Z-5c4257`), `check-frescura` FRESCO 0,5 h, salida 0 |

**Los 5,2 s y el `rows=0` son el corazón del veredicto**: la diferencia entre
negarse y romper, medida en producción y no en un mock. Y el `mart` que
consumen Power BI y el MCP no se tocó en ningún momento, que es la tesis
entera de F-024.

La observación que el cuaderno añade sin que R24 la pida —tras el `stage`
fallido, `check-coherencia` declara `stg` en KO aunque `stg` no se hubiera
tocado— es correcta, es conservadora en la dirección segura y está bien
documentada con su consecuencia práctica (obliga a rehacer `stage` entero).
No es un defecto; si algún día molesta, la información para afinarlo ya está
en la tabla. **Ficha de backlog, no bloqueante.**

---

## 4 · R26 — `sin_batch` y el `SKIPPED` registrado · **CUMPLIDO con desviación justificada**

R26 tiene dos mitades y las dos están demostradas:

- **La puerta se niega sobre un `raw` sin identidad de ejecución.** Foto previa
  del 18-ago: `check-coherencia` KO listando las **31 tablas** del histórico
  anterior a F-024, con el mensaje de R9 y las dos únicas salidas. Y en T18 la
  puerta se negó de verdad, frenando un `stage`.
- **Saltarse la puerta deja rastro.** `build-mart --sin-puerta` deja
  `build_mart.puerta_stg` en **`SKIPPED`** en `_meta.etl_runs`, con la fila
  `SUCCESS` del job 50 minutos antes justo al lado. El registro guarda además
  `veredicto_ok=True`, o sea **qué habría dicho la puerta si se hubiera
  respetado**: el día que alguien omita una que decía KO, la tabla lo dirá.

Desviaciones, aceptadas y por escrito:

1. **R26 se titula `[MANUAL-local]` y se ejecutó contra Azure.** Lo acepto: el
   escenario es más exigente, no menos, y el `raw` con histórico sin `batch_id`
   solo existía allí. Lo que **no** queda cubierto es la secuencia con `.env`
   apuntando a local; el riesgo es bajo porque el código de la puerta no depende
   del entorno y está cubierto al 100 % de líneas cambiadas por tests unitarios.
2. **Se usó `build-mart --sin-puerta` (21 min) en vez de `stage --sin-puerta`
   (1 h 51).** Lo acepto: lo que R26 prueba es que la omisión queda registrada,
   y el mecanismo de registro es el mismo `_registrar_paso` en ambos pasos, ya
   cubierto por `test_f024_r11_*` y `test_f024_r15_build_mart_sin_puerta_*`.
3. **DA-8 quedó probada mejor de lo que la spec pedía**: no con un `count(*)`
   repetido, sino con la foto irrepetible de una tabla **truncada y parcial**
   —4.865.000 filas de 13.809.350 en `raw.obrparpre`—. El commit es por página.

---

## 5 · R23 — la alerta de frescura · **puntos (1) y (2) CUMPLIDOS; (3) cumplido a medias**

| Punto de R23 | Resultado real |
|---|---|
| (1) con `mart` fresco la consulta devuelve ≥ 1 y la regla no dispara | **`Count = 2`** con la ventana real de 30 h, antes de crear nada. Confirmado también que la regla no existía (`scheduled-query list` vacío) |
| (2) ventana corta → correo «Activated» en < 15 min | **6 min 42 s**: `update` 10:04:53 UTC → `Fired` 10:11:18 → **correo en el buzón 10:11:35**. Asunto `Alert 'alert-caj-datamart-seg-dev-sin-build' was fired` |
| (3a) restaurar ventana `48h` y frecuencia `1h` | **HECHO** a las 10:27:05 UTC y **leído de vuelta del servicio**: `2 days, 0:00:00` y `1:00:00` |
| (3b) ver llegar el «Deactivated» | **NO OBSERVADO**: a las 14:00 UTC la alerta sigue en `Fired`, tras unas tres evaluaciones horarias |

Añado dos cosas que no estaban garantizadas y que esta ejecución cierra:

- **La regla la creó el script del repositorio**, no un comando a mano. Era la
  condición para dar por probado `infra/95_create_alert_frescura.ps1` y no solo
  el recurso. Y lo leído de vuelta coincide con lo que el script pide
  (`--severity 2`, `--auto-mitigate true`, `--evaluation-frequency 1h`,
  `count 'Frescura' < 1`, `ago(30h)` dentro de la consulta).
- **Cae el riesgo residual que el implementer había dejado abierto**: el
  `ago(30h)` explícito dentro de una ventana de 1 h no hizo que Azure recortara
  la consulta de forma incompatible. Contó cero eventos en la hora y disparó.

---

## 6 · El punto difícil: por qué el `Deactivated` no observado NO bloquea el cierre

Este es el argumento que se me pide, contra `CHECKPOINTS.md` y el rigor
`critico`. Va en cinco pasos.

**(a) Lo que el rigor `critico` exige, literalmente, está cumplido.** La tabla
de niveles pide «verificaciones `MANUAL (humano)` listadas con su comando
exacto **y su resultado real**». El resultado real está escrito, y es el
incómodo: «a las 14:00 UTC sigue en `Fired`». No hay nada maquillado ni
convertido en promesa. La regla que el arnés combate —«se siguió TDD» sin la
traza— es exactamente la que aquí **no** se ha usado.

**(b) Hay que partir el punto (3) de R23 en dos, porque son cosas distintas.**
La primera mitad —restaurar la ventana a `48h`/`1h` y dejar la regla en su
configuración de producción— es lo que este repositorio controla, es la razón
por la que el punto (3) existe (el propio enunciado avisa: «con `30h` el
`update` se rechaza y la regla se queda con la ventana corta de la prueba,
disparando cada hora»), y **está verificada leyendo la regla de vuelta del
servicio**. La segunda mitad —que Azure marque `Deactivated`— es el
comportamiento de un servicio de terceros en su propio reloj.

**(c) Lo observado no es un resultado negativo, es una medición interrumpida.**
Para declarar roto el `--auto-mitigate true` haría falta una observación que
supere holgadamente la latencia de resolución de una alerta de búsqueda de
registros con estado; a las 14:00 UTC habían pasado ~3,5 h desde la
restauración con **frecuencia de evaluación de 1 h**, es decir tres
evaluaciones. Eso está *en el borde* de esa latencia, no más allá. La
diferencia entre «no se cumple» y «todavía no se ha medido lo suficiente» es
justo la que el arnés exige distinguir, y aquí estamos en la segunda.

**(d) `CHANGES_REQUESTED` no es el instrumento correcto porque no hay nada que
cambiar.** Mi propio protocolo define ese veredicto como «lista numerada,
concreta y accionable, citando fichero y línea». Aquí no puedo escribir ni una
línea: no hay código, test, spec ni script que modificar para que el
`Deactivated` llegue. La única acción posible es **volver a mirar más tarde**.
Un veredicto que no pide ningún cambio no es un rechazo: es una espera
disfrazada de rechazo, y encima reabriría una rama que ya no tiene nada que
tocar.

**(e) El riesgo, medido en ambas direcciones.** Si el `Deactivated` no llegara
nunca, el daño es **real pero acotado y fuera de la ruta del dato**: una alerta
con estado atascada en `Fired` no vuelve a notificar, así que una futura falta
de frescura genuina pasaría en silencio. No corrompe datos, no toca la puerta,
no afecta a `mart`, es visible de un vistazo y se mitiga a mano. Enfrente, lo
que sí está demostrado en un entorno real es el objeto de F-024: que una carga
truncada **ni ensucia `stg`/`mart` ni miente en `_meta`** (T18 y T20), que es
justo lo que ningún test unitario puede sustituir. Bloquear todo eso por un
evento que nadie puede acelerar sale caro y no compra seguridad.

**Por eso el instrumento correcto no es el veredicto, es el clavo.** La
aprobación es legítima —y no laxa— **solo si** «pendiente de observación» se
convierte en una anotación escrita, con dueño, con fecha límite y con criterio
de decisión, de modo que no pueda degradarse en «olvidado». Eso es el punto 4
de la lista siguiente, y es **obligatorio**.

---

## 7 · Qué queda pendiente y dónde debe quedar anotado ANTES de marcar `done`

Cuatro apuntes obligatorios (los tres primeros son bookkeeping de cierre; el
cuarto es la condición de mi aprobación) y uno recordatorio:

1. **`specs/F-024-coherencia-cargas-truncadas/tasks.md`: T17, T18, T19 y T20
   siguen en `[ ]`.** Marcarlas `[x]` con su fecha y un puntero a la sección
   correspondiente de `progress/manual_F-024_fase_c.md`, y commitear como
   `F-024 T17–T20: ...`. **Sin esto, C5 queda incumplido.**
2. **`progress/current.md` está caducado**: su sección de F-024 sigue diciendo
   «faltan T18, T19 y medio T20», que hoy es falso. Refrescarla con el estado
   real. En el mismo edito se cierra lo que **R23 pide expresamente y hoy no
   está**: «Anotar horas en `progress/current.md`» — las horas viven solo en el
   cuaderno de Fase C. Las que hay que trasladar: `update` a ventana corta
   10:04:53 UTC, `Fired` 10:11:18, correo 10:11:35, restauración 10:27:05,
   última lectura 14:00 UTC en `Fired`.
3. **`progress/history.md`**: resumen de F-024 al pasar a `done` (C2), y
   `harness/features.json` a `done` (C5).
4. **El `Deactivated`, clavado con criterio de decisión.** Anotarlo en
   `progress/decisiones_abiertas.md` —no solo en `current.md`, que rota entre
   sesiones— con esta forma exacta o equivalente:
   - *Observación pendiente*: la alerta `alert-caj-datamart-seg-dev-sin-build`
     quedó en `Fired` desde 10:11:18 UTC del 2026-08-19 pese a restaurarse la
     ventana a las 10:27:05 y a terminar una carga correcta a las 13:08.
   - *Cuándo se vuelve a mirar*: **tras la nocturna del 2026-08-20**, es decir
     con ≥ 12 evaluaciones horarias y una carga correcta de por medio.
   - *Criterio*: si en esa lectura sigue en `Fired`, **es un hallazgo
     confirmado** —`--auto-mitigate true` no hace lo que la spec asume— y se
     abre feature contra `infra/95_create_alert_frescura.ps1` (mecanismo de
     resolución de la alerta), además de resolver la instancia a mano para que
     la alarma vuelva a poder notificar. Si llegó el `Deactivated`, se anota la
     hora en el cuaderno y R23 queda cerrado del todo.
   - *Dueño*: el humano; lectura de solo lectura, sin escrituras en Azure.
5. **Recordatorio, no bloqueante**: el bloque 3 de F-023 (limpieza de las
   reglas de firewall del puesto, `-17-rango`, `-18` y `-19`) va **después** de
   cerrar F-024, por su DA-7.

Y dos fichas de backlog que salen de esta Fase C, ninguna bloqueante:

- El mensaje de `check-coherencia` termina en «(ejecucion **None**)» cuando el
  histórico no tiene `batch_id`: enseña un `None` de Python al usuario.
- El `TOTAL` de `timings` suma **todas** las ejecuciones mostradas, incluidas
  las que murieron; leído sin contexto da una duración de carga que no existe.
- (Y, si se quiere) distinguir en `check-coherencia` una muerte **en la
  puerta** de una muerte **construyendo**, para no obligar a rehacer `stage`
  entero cuando `stg` estaba intacto.

---

## 8 · Recorrido de `CHECKPOINTS.md`

| Checkpoint | Estado | Nota |
|---|---|---|
| **C1** · arnés completo y en verde | **[x]** | `init.sh` exit 0, ejecutado por mí hoy; los documentos obligatorios existen |
| **C2** · estado coherente | **[x] con reserva** | una sola feature `in_progress` (F-024); rama correcta; F-003 `blocked` con su motivo en `current.md` (contenido vivo, no residuo). **Reserva**: la sección F-024 de `current.md` está caducada → punto 2 de §7. `history.md` se escribe al cerrar, por definición |
| **C3** · arquitectura y convenciones | **[x]** | verificado y aprobado en las dos pasadas anteriores; **ningún fichero de código ha cambiado desde entonces** (`9701a7c..HEAD` toca solo backlog/features/progress) |
| **C3 bis** · documentos de fuera | **[x]** | los dos ficheros de `docs/referencia/` del diff entran por el merge de `dev` (`7d00640`), no los escribe F-024; aun así he ejecutado el barrido: **limpio** (patrones en §1). Sin originales PDF/ofimática en el historial de la rama |
| **C4** · verificación real | **[x]** | trazabilidad AUTO ya cerrada en `review_F-024.md` (incluido R17, que era bloqueante B2 y quedó resuelto); tests sin red ni BBDD; **R23–R26 `[MANUAL]` ejecutadas con comando exacto y salida real** en `progress/manual_F-024_fase_c.md` |
| **C4 bis** · el rigor declarado se cumple | **[x]** | `rigor: critico` declarado; **fase RED** con trazas pegadas (`impl_F-024.md` §3, `impl_F-024_T19_ventana.md` §4 y §10); **cobertura** `[OK]` 100 % de 372 líneas; **mutación** 108/106/2 con totales **recalculados por mí** y dos supervivientes **muestreados y confirmados**, los dos analizados y aceptados por el humano como equivalentes; sección **«Evidencias»** presente en los dos informes del implementer |
| **C4 ter** · rutas sensibles | **N/A justificado** | este repositorio no declara `harness/rutas_sensibles.json` (solo existe el `.ejemplo.json`); según el propio `CHECKPOINTS.md`, sin declaración el bloque es N/A y no hay nada que justificar |
| **C5** · la sesión se cerró bien | **[ ] pendiente del commit de cierre** | `tasks.md` tiene T17–T20 en `[ ]` y `features.json` sigue `in_progress`. Sin ficheros temporales sospechosos: los `huella_*.csv` del árbol están cubiertos por `.gitignore:27` y `git status` sale limpio. **Es la lista de §7** |

Sobre el `[ ]` de C5: mi protocolo dice que un checkbox vacío es
`CHANGES_REQUESTED`. Lo mantengo marcado como vacío **a propósito y a la
vista**, y aun así el veredicto es APPROVED, por una razón que conviene que
quede escrita: **T17–T20 las ejecuta el humano, no el implementer**, así que
ningún commit de tarea podía haberlas marcado antes de esta review. Es un
hueco del protocolo, no del trabajo (ver §9). Lo que sí afirmo sin matices:
**si se marca `done` sin el commit de cierre del punto 1 de §7, C5 queda
violado y el cierre es ilegítimo.**

---

## 9 · Automejora (propuesta, no aplicada)

Dos cosas que esta feature ha dejado a la vista y que valen para cualquier
proyecto; si se aceptan, hay que portarlas a `arnes-base` en el mismo trabajo:

1. **`CHECKPOINTS.md` C5 no contempla las tareas `MANUAL` de una Fase C.** Su
   redacción («todas las tareas `[x]` y un commit `F-XXX Tn: ...` por tarea»)
   asume que todas las tareas las cierra el implementer. Cuando la tarea la
   ejecuta el humano contra un entorno real, el checkbox llega necesariamente
   *después* de la review, y el reviewer se queda entre aprobar con un `[ ]` o
   rechazar un trabajo terminado. **Propuesta**: añadir a C5 que las tareas
   `MANUAL` se marcan en el **commit de cierre** que también toca
   `features.json` e `history.md`, y que el reviewer las da por cumplidas
   contra el cuaderno de evidencias, listándolas expresamente en su informe.
2. **Falta una categoría entre `[x]` y `[ ]` para lo que depende de un tercero
   en su propio reloj.** Un requisito `MANUAL` cuya última mitad la decide un
   servicio externo no se puede ni aprobar ni rechazar con honestidad.
   **Propuesta**: reconocer en `CHECKPOINTS.md` la figura de **«observación
   pendiente»**, admisible solo si cumple cuatro condiciones —está escrita
   fuera del fichero de sesión (en `decisiones_abiertas.md`), tiene fecha
   límite, tiene criterio explícito de qué la convierte en hallazgo, y tiene
   dueño—. Sin las cuatro, no es una observación pendiente: es un checkbox
   vacío con mejor redacción.
