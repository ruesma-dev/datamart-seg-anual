<!-- progress/impl_F-066_cierre.md -->
# F-066 · Pasada de cierre: los cinco puntos de papeleo del review

Cambios requeridos de la **pasada 3** de `progress/review_F-066.md`
(`CHANGES_REQUESTED` con el **código APROBADO**). Los seis puntos son de
documentación y trazabilidad; **este trabajo no toca ni una línea de Python**.
Me tocan el **1, 2, 4, 5 y 6**; el **3** es del líder (las dos verificaciones
`MANUAL` contra Azure) y lo que hago con él es **dejarle el hueco preparado**.

Tareas nuevas declaradas en `tasks.md`: **T25, T26 y T27**.

## Punto 1 · R19 · las cifras de la nocturna, sacadas de la base

`mediciones.md` §3 decía «PENDIENTE hasta la primera nocturna». Ahora está
medido, y **medido por mí contra `_meta.etl_runs`**, no copiado del chat: la
queja del reviewer era exactamente esa (regla ANTI TELÉFONO-DESCOMPUESTO).

Nocturna **`caj-datamart-seg-dev-p1gq8ks`**, 2026-09-08, **11:16 → 14:19 UTC**,
`Succeeded`, imagen `r20260908-1248`, SKU **`Standard_B2s`**, `batch_id`
`20260908T111652Z-570bb9`. `ingest_raw`: **25.491.959 filas en 2.454,1 s**.

**Filas y segundos por tabla** (lo que el reviewer decía que no estaba en ningún
sitio), de los tramos `ingest_raw.<tabla>` de ese `batch_id`:

| `apu` | `dcopro` | `asi` | `apa` | `hmores` | `dncpro` | `dco` | `confir` | `dcf` |
|---|---|---|---|---|---|---|---|---|
| 2.155.571 | 788.415 | 783.765 | 709.701 | 329.086 | 286.652 | 72.241 | 70.057 | 165.503 |
| 166,3 s | 141,3 s | 24,4 s | 38,2 s | 34,3 s | 43,6 s | 19,8 s | 6,7 s | 54,6 s |

Subtotal de las 8 grandes: **5.195.488 filas / 474,6 s**. Con `dcf`,
**5.360.991 / 529,2 s**. La tabla completa, en `mediciones.md` §3.

### Lo que aparece al medir y no estaba escrito

**La línea base de R19 está mal por 920 filas, y ahora se sabe por qué.** R19
declara «20.148.546 filas, 1.832 s». El `rows_processed` de esa ejecución
(`20260905T173031Z-d06188`) es **20.147.626**. La diferencia es el tramo
`ingest_raw.firma_origen`, que el paso padre **no** suma y el sumatorio de
tramos sí. Las dos lecturas son válidas; mezclarlas da un delta falso. Comparado
`rows_processed` contra `rows_processed`:

| | Base (05-sep) | `p1gq8ks` (08-sep) | Δ |
|---|---|---|---|
| Filas | 20.147.626 | 25.491.959 | **+5.344.333 (+26,5 %)** |
| Segundos | 1.832,4 | 2.454,1 | **+621,7 s (+33,9 %)** |
| Filas/s | 10.995 | 10.387 | −5,5 % |

**Dónde se van los 2.454 s: no en lo nuevo.** `obrparpre` sola se lleva
**1.098,4 s** (44,8 % del paso) y las nueve tablas de arriba **529,2 s**
(21,6 %). `firma_origen` cuesta 57,8 s y se paga **una vez** para las 56 tablas,
como predijo §2 desde el puesto.

**Créditos**: mínimo **552 de 576** durante toda la ejecución, lo que acota el
gasto en **≤ 24**. No se guardó la serie punto a punto; digo lo que hay medido y
lo llamo cota, no medición. Frente a los 21 de la primera acotada y los ~40 de
la completa del 04-sep.

**Y ya no es un caso aislado**: la nocturna `29815200` (09-sep, 00:00:17 UTC,
corriendo mientras escribo) hizo `ingest_raw` con **25.497.946 filas en
2.921,1 s**. Las 56 tablas entran cada noche en producción.

## Punto 2 · R20 · la fila de F-065

`mediciones.md` §4 tenía cuatro celdas vacías. Rellenada con la nocturna del
08-sep: fecha, alcance (56 tablas, `build_stg` acotado por F-025), créditos
—declarados como lo que son: mínimo medido 552/576 y cota de gasto ≤ 24, no una
lectura antes/después—, duración 3 h 03, `Succeeded` y `Standard_B2s`.

## Punto 3 · el hueco de T14, preparado para el líder (no ejecutado)

**No he ejecutado `check-raw-recuentos` ni `check-diccionario`**, y es
deliberado: R24 los declara `MANUAL (humano)`, la nocturna `29815200` está
corriendo y cada uno hace 56 `COUNT(*)` contra Sigrid y contra el Postgres
compartido con `albaranes` y `partes` en producción.

Lo que sí he hecho es **`mediciones.md` §6**: los dos comandos literales, el
criterio de cierre de cada uno, y dos bloques de código con el formato listo
para pegar la salida más la línea de código de salida, fecha UTC y quién lo
ejecutó. Con los dos huecos rellenos, T14 pasa a `[x]` y R24 queda cumplido.

Queda escrito allí que lo único medido contra Azure —08-sep, 16:30 UTC, 31
iguales · 25 distintas, código 1— es con el criterio **viejo**, anterior a
T19-T24.

## Punto 4 · C5 · `tasks.md` decía lo que ya no era verdad

* **T13 → `[x]`.** La imagen `r20260908-1248` se desplegó y la nocturna corrió.
* **T14 → sigue `[ ]`**, ahora rotulada «PENDIENTE, del líder», con la
  dependencia dicha y el puntero a §6.
* La sección «Estado de las tres MANUAL» estaba fechada el 2026-09-06 y
  afirmaba que R19, R20 y R24 seguían pendientes. Reescrita al 2026-09-09: R19
  y R20 **cumplidos**, con las cifras y dónde están; R24 abierto, del líder, y
  **mientras T14 siga en `[ ]`, C4 sigue abierto y la feature no pasa a `done`**.

## Punto 5 · C5 · seis commits sin tarea que los respaldara

`da965c8`, `29f7c62`, `4a3cd2c`, `e2e2ad8`, `ddcf8b2` y `084f75a` van rotulados
`F-066 T1`…`T6`, pero T1-T6 son las tareas de la **ingesta**, hechas el 06-sep y
cerradas. El trabajo real —la tolerancia con dirección— no estaba declarado.

Añadidas **T19-T24** en `tasks.md`, una por commit, con su verificación, y una
tabla explícita `commit → tarea` para que se lea eso y no la etiqueta del
mensaje. La sección dice en su primera frase que **se declaran a posteriori y
que los commits se rotularon mal**: esconderlo sería el mismo defecto que el
reviewer señaló.

**No se reescribe el historial.** Un `rebase` corregiría los mensajes y a cambio
invalidaría los SHA que ya citan `mediciones.md`, `progress/review_F-066.md`,
los dos informes de mutación y la ficha de `harness/features.json`, sobre una
rama que ya está revisada. El coste supera con mucho al de una tabla.

## Punto 6 · C2 · `progress/current.md`

Estaba fechado el 2026-09-07 y decía «C4 y C5 quedan ABIERTOS hasta T13-T14»,
que ya era falso en dos de las tres cosas. Actualizado al 2026-09-09:

* **El punto de retomada es uno solo y está el primero**: T14, con sus dos
  comandos, cuándo lanzarlos (nocturna terminada), qué se espera ver y por qué
  el resultado del 08-sep con el criterio viejo no sirve.
* **F-025 CERRADA** (`96bb7b9`) y **F-068 CERRADA** (`f94fae6`), cada una con lo
  que dejó abierto: T33 pasa a F-065, F-071 nace del censo de obras, y la
  verificación de `02_roles.sql` contra una base de prueba sigue pendiente.
* **Backlog reordenado**: F-071 en 4, F-070 en 5 acotada a los ocho esquemas que
  el MCP lee, F-034 en 6; detrás F-057 y F-056, ya sin ingesta dentro.
* **Purga de 253 líneas**: la fase 7 de F-025, entera, con puntero a dónde vive
  cada cosa; y el estado de F-066 anterior a T13. C2 pide que este fichero
  describa **solo la sesión activa**. De 638 a 271 líneas.
* **Los tres recuentos del diccionario (130 / 822 / 47) se conservan
  literalmente**: los vigila `test_f006_los_recuentos_de_current_son_los_de_hoy`
  y ya tumbaron `init.sh` una vez al reescribir la cabecera.

## Un commit que no es mío, y por qué está aquí

`77500d6` mete `progress/review_F-066.md`, `harness/features.json` y
`BACKLOG.md`, que el reviewer y el líder dejaron **sin commitear** al emitir el
veredicto. Va en un commit propio, separado de las correcciones, para que se vea
quién escribió cada cosa; sin él el árbol no queda limpio.

## Fase RED · no aplica en esta pasada, y hay que decirlo

El rigor `critico` exige fase RED **para los requisitos centrales**, y la fase
RED de esta feature está donde le toca: `progress/impl_F-066.md` (la ingesta),
`impl_F-066_reconciliar_columnas.md` (R25-R28) e
`impl_F-066_tolerancia_recuentos.md` (T19-T24), las tres con la traza real del
fallo pegada.

**Esta pasada no escribe código**: `git diff --stat` sobre mis tres commits no
toca ni un `.py`. Un test que fallara antes no tendría nada que probar. Los
requisitos que cierro —R19, R20— son de **medición y rastro**, y su verificación
es que las cifras estén en el fichero y salgan de `_meta.etl_runs`; R24 es
`MANUAL` por definición de la propia spec.

## Evidencias

| Evidencia | Valor |
|---|---|
| Ficheros tocados | 3 de papeleo (`mediciones.md`, `tasks.md`, `current.md`) + 3 ajenos en `77500d6`. **Cero ficheros de código.** |
| Tests ejecutados y resultado | **3.970 passed, 159 skipped, 0 failed** (`bash harness/init.sh`, exit 0, «ENTORNO LISTO») |
| Cobertura de las líneas cambiadas | **N/A**: cero líneas de Python cambiadas, así que `PUERTA COBERTURA` no tiene alcance que medir. La de la feature está en 93,6 % (788/842) desde `084f75a`. |
| Mutantes generados y supervivientes | **N/A por el mismo motivo**: no hay código nuevo que mutar. Las campañas de la feature están cerradas y analizadas en `progress/mutacion_F-066.md` y `progress/mutacion_F-066_tolerancia_recuentos.md` (35 mutantes, 33 muertos, 2 supervivientes equivalentes con su argumento escrito, más el `bold=True` firmado por el humano el 06-sep). |
| Tiempo de ejecución de la suite | **348,71 s** (0:05:48) |
| Puertas de `init.sh` | `PUERTA COBERTURA` **[OK] 93,6 %** (788/842, umbral 80 %, nivel `critico`) · `PUERTA TAMAÑO` **[OK]** (requirements 150/150, design 250/250, impl 219/220, review 140/140) · `BACKLOG.md al día` · avisos de siempre: 216 de `ruff` y `blocked` |
| Comprobación rápida durante el trabajo | `pytest tests/test_f006_contexto.py tests/test_documentos_del_arnes.py tests/test_f015_alcance.py tests/test_f006_docs.py` → **62 passed en 0,78 s** |

## Lo que queda fuera y lo que falta para cerrar

* **Falta T14**, y es del líder: los dos comandos `MANUAL` contra Azure con la
  nocturna terminada. Hueco en `mediciones.md` §6. **Hasta entonces C4 sigue
  abierto y F-066 no puede pasar a `done`.**
* **Fuera de alcance, por instrucción**: `az`, `infra/`, `git push` y `.env`.
* **Observación no bloqueante del reviewer que NO he atendido** (no está entre
  los cinco puntos que me tocan): `progress/mutacion_F-066_verificacion.md` es
  salida cruda con dos `PENDIENTE` y convendría una cabecera que lo diga. Queda
  fichada aquí para que no se pierda.
* **La grieta del umbral, que sigue viva y conviene no olvidar**: 0,05 % de
  `obrparpre` son ~6.940 filas y una pérdida menor pasaría en verde. **Revisar
  el umbral si baja `page_size` o aparece una tabla mayor.** Está escrito en
  `current.md` y en el review.
