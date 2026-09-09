<!-- specs/F-066-ingesta-raw-pendientes/tasks.md -->
# F-066 · Tareas

Rigor crítico: T1-T3 son la fase RED (los tests se escriben y fallan antes de tocar YAML o código). Un commit por tarea: `F-066 Tn: ...`.

- [x] T1: Escribir `tests/test_f066_ingesta_raw.py` con los tests de R1-R9, R11, R13 y R14 (leen `config/tables_sigrid.yaml` y `config/diccionario/raw.yaml`; constante `VACIAS_EN_SIGRID` con las 19 de R3; `emp` con exactamente las 11 exclusiones técnicas y ninguna columna personal excluida, `res` sin exclusiones; fichas de `emp`/`res` que declaran sus datos personales) y comprobar que fallan  |  Verificación: `pytest tests/test_f066_ingesta_raw.py` en rojo, traza en `progress/impl_F-066.md`
- [x] T2: Escribir `tests/test_f066_recuentos.py` (R15-R18: dominio con los cuatro casos, CLI con dobles de `SigridApiClient` y `PostgresClient`, `sys.exit(1)` en `distintas`/`ausentes`/`sin_medir`, ninguna llamada a `record_run_start`) y comprobar que fallan  |  Verificación: `pytest tests/test_f066_recuentos.py` en rojo
- [x] T3: Crear `etl_sigrid/domain/recuentos.py` (`InformeRecuentos`, `comparar_recuentos`) y el comando `check-raw-recuentos` en `main.py` (§4 de design)  |  Verificación: `pytest tests/test_f066_recuentos.py` en verde
- [x] T4: Dar de alta en `config/tables_sigrid.yaml` el bloque PERSONAL (`res`, `emp`, `hmo`, `hmores`) con las exclusiones técnicas de §3 (11 en `emp`, 0 en `res`, `tex` en `hmores`; nada por dato personal)  |  Verificación: `pytest tests/test_f066_ingesta_raw.py -k "personal or emp or res"`
- [x] T5: Dar de alta el bloque CONTABILIDAD (`cua`, `asi`, `apu`, `apa`; `tex` excluida en `apu` y `apa`; sin `where`, sin `page_size`)  |  Verificación: `pytest tests/test_f066_ingesta_raw.py -k contabilidad`
- [x] T6: Dar de alta el bloque COMPRAS/PROVEEDOR (`conact`, `auxpronat`, `prvcer`, `prvobrpag`, `confir`, `deffir`, `dco`, `dcopro`, `dcorec`, `dnc`, `dncpro`, `ctrrec`, `dcfrec`, `dcarec`, `auxpag`, `auxefp`, `conest`) con la lista estándar de exclusiones, `page_size: 5000` en `dcopro` y `dncpro`, `incremental_column: tiemod` solo en `auxpronat`, `auxpag`, `auxefp`, y el comentario con las 19 descartadas por vacías  |  Verificación: `pytest tests/test_f066_ingesta_raw.py -k "compras or vacias"`
- [x] T7: Quitar `pagtex` y `pagfor` de `exclude_columns` de `dcf` (R8) y corregir su ficha a «No se traen 21»  |  Verificación: `pytest tests/test_f066_ingesta_raw.py tests/test_f006_raw_ingesta.py -k dcf`
- [x] T8: Escribir las 25 fichas en `config/diccionario/raw.yaml` con el patrón de `rec` (R10, R11, R14; las de `emp` y `res` dicen qué datos personales contienen; la de `conest` que traduce `con.est` por `tip`), subir `version` en `00_global.yaml` y pasar «31 tablas» a 56 en `raw.yaml`, `00_global.yaml` y `objetos_pendientes.yaml`  |  Verificación: `pytest tests/test_f006_raw_ingesta.py tests/test_f006_fuente_que_gobierna.py tests/test_f006_copias.py tests/test_f066_ingesta_raw.py`
- [x] T9: Ingestar en local, tabla a tabla, las 25 nuevas y `dcf` con `python main.py ingest --table <t> --full` y comprobar que `raw.<t>` se crea con PK `ide` y el recuento de Sigrid  |  Verificación: MANUAL (humano): `python main.py check-raw-recuentos` termina con código 0
- [x] T10: Párrafo en `docs/ARCHITECTURE.md` («Acceso a datos»): grupos nuevos, mapa de `con.tip`, `apu` sin `tiemod`, `hmores`, datos personales en `raw`, lo que Sigrid no guarda (DA-6, DA-7)  |  Verificación: `pytest tests/test_f006_docs.py tests/test_documentos_del_arnes.py`
- [x] T11: Actualizar `azure-apps/datamart_seg_anual.md` (R21: 56 tablas, las 25 nuevas, las descartadas, `dcf` con `pagtex`/`pagfor`, datos personales enteros en `raw.emp`/`raw.res`) y hacer commit en ese repositorio  |  Verificación: MANUAL (humano): `git -C ../azure-apps log -1 --stat`
- [x] T12: Cobertura de las líneas cambiadas ≥ 80 % y campaña de mutación completa sobre `etl_sigrid/domain/recuentos.py` y el comando (`python -m harness.mutacion`), 0 supervivientes o justificación aceptada; informe en `progress/`  |  Verificación: `bash harness/init.sh` secciones 7b y mutación en verde
- [x] T13: Desplegar la imagen (`infra/`, tag fechado) y esperar la primera nocturna con las 25 tablas; anotar en `mediciones.md` filas y segundos por tabla, total frente a 1.832 s, créditos antes/después y SKU (R19), y la fila de F-065 (R20)  |  Verificación: MANUAL (humano): `python main.py timings` y `az monitor metrics list ... cpu_credits_remaining`
- [x] T14: Contra Azure, tras esa nocturna: `python main.py check-raw-recuentos` con código 0 y `python main.py check-diccionario` sin objetos sin ficha  |  Verificación: MANUAL (humano) — **HECHA el 2026-09-09 por el líder**, tras la nocturna automática `29815200` (00:00→03:18 UTC). Recuentos: **código 0, VEREDICTO CONFORME**, 51 iguales y 5 con deriva tolerada, **0 con filas que faltan en raw**, peor desviación 0,0080 % frente a un umbral de 0,05 %. Diccionario: **código 0**, biyección exacta 130/130 y lo publicado ES lo del árbol (versión 16). Las dos salidas, con su contexto, en `mediciones.md` §6.
- [x] T15: Pasar al líder los hallazgos de R22 para que actualice las fichas de F-055, F-056, F-057 y F-067 en `harness/features.json`  |  Verificación: MANUAL (humano): `bash harness/init.sh` regenera `BACKLOG.md` con las fichas cambiadas
- [x] T16: Ejecutar `bash harness/init.sh` en verde  |  Verificación: exit 0

## Estado de las tres MANUAL (actualizado el 2026-09-09)

* **T13 · HECHA el 2026-09-08.** El humano construyó y desplegó la imagen
  `r20260908-1248` —con F-066 y F-068 dentro, que era la condición del bloqueo—
  y la nocturna `caj-datamart-seg-dev-p1gq8ks` corrió de 11:16 a 14:19 UTC en
  `Succeeded`, con los diez pasos en verde y `check-declarados` 130/130.
  **R19 y R20 quedan cumplidos**: `mediciones.md` §3 trae filas y segundos por
  tabla de las 8 grandes y de `dcf` sacados de `_meta.etl_runs`, el total
  (25.491.959 filas / 2.454,1 s) frente a la línea base (20.147.626 / 1.832,4 s,
  +26,5 % y +33,9 %), los créditos (mínimo 552 de 576) y el SKU
  (`Standard_B2s`); §4 trae la fila de F-065 con sus siete celdas. La nocturna
  `29815200` del 09-sep lo repite en producción (25.497.946 filas / 2.921,1 s).
* **T14 · HECHA** por el líder el **2026-09-09**, tras la nocturna automática
  `29815200` (00:00→03:18 UTC, `Succeeded`, los diez pasos y 130/130 declarados).
  Los dos comandos en verde y sus salidas pegadas en `mediciones.md` §6:
  **`check-raw-recuentos` código 0 · CONFORME** —51 iguales, 5 con deriva
  tolerada, **0 con filas que faltan en `raw`**, peor desviación 0,0080 % contra
  un umbral de 0,05 %, seis veces de margen— y **`check-diccionario` código 0**,
  biyección exacta 130/130 y lo publicado igual al árbol.

  **La comparación con el 08-sep es la que justifica T19-T24**: el mismo estado
  de la base daba entonces «31 iguales · 25 distintas» y **código 1** con el
  criterio viejo. No se ha tapado nada —una tabla con filas de menos sigue
  tumbando el comando sea cual sea su tamaño—; lo que ha desaparecido son 25
  falsas alarmas que ahogaban la señal.

  **`check-diccionario` costó dos pasadas, y el motivo importa**: la primera
  (05:52 UTC) salió en **código 1** porque la imagen en producción era del
  mediodía anterior y dos fichas se corrigieron después. El código estaba bien;
  lo que la IA leía, no. Se resolvió desplegando `r20260909-0520` y publicando a
  mano, las dos cosas con autorización expresa del humano. **C4 queda cerrado.**
* **T15 · HECHA** por el líder el 2026-09-06 a las 19:40 UTC (commit
  `26ce092`): los hallazgos de R22 están en las fichas de F-055, F-056, F-057 y
  F-067 de `harness/features.json`, y nace **F-068** con lo del permiso del MCP
  sobre `raw.emp`.

## Nota de T12 · la campaña de mutación (2026-09-07)

Campaña completa **en serie**, con el comando y la base escritos enteros —el
informe no imprime `--base` y con el defecto (`dev`) salen 247 mutantes en 11
ficheros, porque esta rama nace de la de F-025 sin fusionar—:

```bash
python -m harness.mutacion --feature F-066 --base d1f56aa --workers 1
```

Tres pasadas, y **solo la tercera es válida**:

| # | HEAD | Mutantes | Muertos | Supervivientes | Tiempo | Veredicto del arnés |
|---|---|---|---|---|---|---|
| 1.ª | — | 23 | 20 | 3 | 3.621,8 s | válida |
| 2.ª | `ca31adb` | 23 | 22 | 1 | 3.311,2 s | **CAMPAÑA NO VÁLIDA** |
| **3.ª** | `d8c73b8` | **23** | **22** | **1** | **2.072,2 s** | **válida** · 0 timeouts · 0 sin veredicto |

**Por qué la 2.ª salió no válida, y qué se hizo.** No fue el código de esta
feature: la línea base terminó roja en un test aleatorio **de F-024**
(`test_f024_r1_batch_id_tiene_forma_y_es_unico`), que generaba 500 `batch_id`
en el mismo segundo y exigía los 500 distintos. El sufijo son 6 hexadecimales
—16.777.216 valores—, así que por el problema del cumpleaños la probabilidad de
colisión es 1 - exp(-500²/(2·16.777.216)) ≈ **0,74 %**, que casa con el 0,833 %
medido sobre 3.000 repeticiones. Con la suite corriendo 23 veces seguidas, ese
test invalidaba campañas ajenas cada dos por tres. **El líder decidió arreglarlo
y no excluirlo**: el defecto estaba en el test, no en el `batch_id`. Reescrito
el 2026-09-06 para comprobar lo que R1 sí garantiza (la forma de los 500 y que
el espacio de sufijos es grande de verdad); remedido, **0 fallos en 3.000
pasadas**. La 3.ª campaña es la que se corrió con él ya arreglado.

**El único superviviente** es `bold=True -> bold=False` en el título del
comando `check-raw-recuentos` (`main.py:1995`): **mutante equivalente**, no
cambia ni una letra del texto ni el código de salida y `CliRunner` invoca sin
color, así que cazarlo exigiría afirmar sobre secuencias ANSI y no sobre
comportamiento. **Lo FIRMÓ el humano el 2026-09-06 a las 20:45 UTC** —palabra
literal, «firmo»—, que es lo que el rigor `critico` exige para levantar
`supervivientes_maximos: 0`; consta en la ficha de F-066 de
`harness/features.json` (commit `5564975`) y en `progress/mutacion_F-066.md`.
El reviewer lo reprodujo por su cuenta y da la exención por buena. **No se
reabre.**

Los otros dos supervivientes de la 1.ª pasada **sí eran huecos reales** y están
muertos desde `ca31adb`: `max_rows=1` y `err=True`.

## Un commit de esta rama que NO es de F-066 (hallazgo 11 del review, pasada 2)

`b964c6e` **cambia produccion y no pertenece a esta feature**: mueve la nocturna
de `0 2 * * *` a **`0 0 * * *`** y sube `replicaTimeoutSeconds` de 18000 a
**25200** en `infra/env/dev.json`, con su reflejo en `docs/ARCHITECTURE.md` y en
`test_f003_r9_cron_del_entorno_dev_es_medianoche`. Lo pidio el humano el
2026-09-06 a las 20:20 UTC -una carga completa dura ~4 h 50 y arrancando a las
02:00 el dato no estaba listo hasta media manana- y el lider lo ejecuto en el
job de Azure y en los cuatro sitios donde el valor esta versionado, mas
`azure-apps/datamart_seg_anual.md` (commit `3916ca6` alli). El cambio del
timeout no es una decision nueva: **corrige una divergencia** que existia desde
el 05-sep, cuando se subio a 7 h en Azure tras morir la reconstruccion
`kcb9n2r` por ese techo, y el repositorio se quedo diciendo 5 h.

Queda escrito aqui, y no solo en el cuerpo del commit, porque un cambio de
produccion que viaja de polizon en la rama de otra feature es invisible para
quien lea la spec. **No altera el alcance medido de F-066**: son JSON, Markdown
y un test.
- [x] T17: Arreglar el defecto de R25-R28: `tests/test_f066_reconciliar_columnas.py` en rojo primero, después `_reconciliar_columnas_raw` en `postgres_client.py`  |  Verificación: `pytest tests/test_f066_reconciliar_columnas.py` en verde y traza RED en `progress/impl_F-066_reconciliar_columnas.md`
- [x] T18: Cobertura y campaña de mutación del arreglo, e informe  |  Verificación: `bash harness/init.sh` en verde

## Fase de tolerancia con dirección (2026-09-08) · T19-T24

Estas seis tareas **se declaran a posteriori**, el 2026-09-09, y hay que decirlo:
los seis commits que las implementan **se rotularon mal**. Van etiquetados
`F-066 T1` … `F-066 T6`, pero T1-T6 son las tareas de la ingesta, hechas el
06-sep y ya cerradas. El trabajo es real y está revisado —el reviewer aprobó el
código en la pasada 3—, lo que faltaba era la tarea que lo respaldara, igual que
sí se hizo con T17/T18 para la reconciliación de columnas. La correspondencia
commit → tarea es esta, y es lo que hay que leer en vez de la etiqueta del
commit:

| Commit | Rótulo que lleva | Tarea que es en realidad |
|---|---|---|
| `da965c8` | `F-066 T1` | **T19** |
| `29f7c62` | `F-066 T2` | **T20** |
| `4a3cd2c` | `F-066 T3` | **T21** |
| `e2e2ad8` | `F-066 T4` | **T22** |
| `ddcf8b2` | `F-066 T5` | **T23** |
| `084f75a` | `F-066 T6` | **T24** |

No se reescribe el historial para corregir los mensajes: la rama ya está
revisada y un `rebase` invalidaría los SHA que citan `mediciones.md`,
`progress/review_F-066.md` y los informes de mutación.

- [x] T19: Tolerancia CON DIRECCIÓN en `check-raw-recuentos` (`domain/recuentos.py` y `main.py`): filas de más en Sigrid son deriva y se toleran hasta `--tolerancia-pct` (0,05 % por tabla, relativo); filas de menos son alarma sea de una fila; `ausentes` y `sin_medir` siguen siendo fallo. La salida separa los cuatro casos, dice el umbral aplicado, la peor desviación y cuánto hace de la última ingesta correcta  |  Verificación: `pytest tests/test_f066_tolerancia_recuentos.py` en verde tras la fase RED (traza en `progress/impl_F-066_tolerancia_recuentos.md`) · commit `da965c8`
- [x] T20: Escribir el criterio nuevo donde manda: R15-R17 reformulados en `requirements.md`, el contrato de `InformeRecuentos` y el porqué del 0,05 % en `design.md`, y el criterio de aceptación en `harness/features.json`  |  Verificación: `pytest tests/test_documentos_del_arnes.py` y `bash harness/init.sh` regenera `BACKLOG.md` · commit `29f7c62`
- [x] T21: Cerrar la rama de Sigrid a cero (el 100 % de desviación cuando Sigrid dice 0 y `raw` trae filas, la única división que no se puede hacer) con dos tests, y quitar de las cabeceras la hora exacta que no se había verificado  |  Verificación: cobertura de líneas cambiadas 100 % · commit `4a3cd2c`
- [x] T22: Dejar `ruff check` sin avisos nuevos sobre `recuentos.py`, el test nuevo y `main.py`, y escribir `progress/impl_F-066_tolerancia_recuentos.md`  |  Verificación: `ruff check etl_sigrid/domain/recuentos.py tests/test_f066_tolerancia_recuentos.py` limpio · commit `e2e2ad8`
- [x] T23: Campaña de mutación en serie sobre el diff de la tolerancia (`b3abcf4..e2e2ad8`, `--workers 1`) y matar con test los supervivientes que son huecos reales  |  Verificación: `python -m harness.mutacion --feature F-066 --base b3abcf4 --workers 1`; 35 mutantes, 6 supervivientes → 4 muertos con test · commit `ddcf8b2`
- [x] T24: Segunda pasada de la campaña y análisis escrito de los dos supervivientes que quedan (equivalentes de `recuentos.py:129`), más las tres celdas que faltaban en «Evidencias»  |  Verificación: 35 mutantes, 33 muertos, 2 supervivientes equivalentes, 0 timeouts; `bash harness/init.sh` en verde · commit `084f75a`

## Pasada de cierre del review (2026-09-09) · T25-T27

Los seis cambios requeridos de la pasada 3 de `progress/review_F-066.md`. El
punto 3 (las dos verificaciones MANUAL de T14) **no está aquí**: es del líder.

- [x] T25: Rellenar `mediciones.md` §3 y §4 con la nocturna `p1gq8ks` (R19 y R20): filas y segundos por tabla de las 8 grandes y de `dcf` desde `_meta.etl_runs`, total frente a la línea base, créditos y SKU, y la fila de F-065 con sus siete celdas  |  Verificación: ni «PENDIENTE» ni celda vacía en §3 y §4 de `mediciones.md`
- [x] T26: Dejar preparado en `mediciones.md` §6 el hueco de T14 (los dos comandos, el criterio de cierre y el bloque donde se pega la salida), actualizar `tasks.md` (T13, T14, la sección de las MANUAL y estas tareas nuevas) y `progress/current.md` al estado real de la sesión  |  Verificación: `pytest tests/test_documentos_del_arnes.py`
- [x] T27: `bash harness/init.sh` en verde y árbol limpio, con el informe en `progress/impl_F-066_cierre.md`  |  Verificación: exit 0
