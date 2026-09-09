<!-- progress/review_F-066.md -->
# F-066 · Revisión

## PASADA 3 · Revisión incremental desde `6f3db18` (cierre)

HEAD `084f75a`. Delta `6f3db18..HEAD`: 10 commits de F-066 —T17/T18 (reconciliar
columnas) y los seis rotulados «T1…T6» de la tolerancia—, más los de F-025 y
F-068, que tienen review propio. Lo aprobado en la pasada 2 sigue aprobado y el
delta **no lo invalida**: lo que cambia después en `postgres_client.py` cae en
las líneas 1276-1325, de F-068, fuera del alcance de F-066. **Las pasadas 1 y 2
van abajo resumidas** por la puerta de tamaño; el texto íntegro, en
`git show 6f3db18:progress/review_F-066.md`.

### Veredicto: CHANGES_REQUESTED · el código está APROBADO, el cierre NO

**Rigor `critico`**, declarado: exige fase RED, cobertura, mutación con 0
supervivientes o firma, y «Evidencias». Todo eso está. Lo que **no** está es la
prueba, en el repositorio, de que T13 y T14 ocurrieron: R19, R20 y R24 siguen
literalmente sin cumplir en los ficheros que ellos mismos nombran. La nocturna
corrió de verdad, pero **una cifra que solo viaja por el chat no es evidencia**:
es la regla ANTI TELÉFONO-DESCOMPUESTO de `CLAUDE.md`. Seis arreglos de papeleo,
ninguno de código.

### Cambios requeridos

1. **R19 · `specs/F-066-ingesta-raw-pendientes/mediciones.md` §3 sigue diciendo
   «PENDIENTE hasta la primera nocturna (T13, lo hace el humano)».** Las cifras
   de `p1gq8ks` existen, pero en `specs/F-025-ventana-negocio-build/`
   `mediciones.md` §«SEGUNDA NOCTURNA ACOTADA», y son las de F-025 (`ingest_raw`
   2.454 s, 25.491.959 filas, créditos mín. 552/576). Falta, y no está en ningún
   sitio: **filas y segundos POR TABLA** de `_meta.etl_runs` (las 8 grandes y
   `dcf`), el total frente a la base (20.148.546 filas / 1.832 s), créditos
   antes y después, y el **SKU** (B2s).
2. **R20 · §4 de ese mismo fichero**, la fila de F-065, sigue siendo
   `| PENDIENTE (T13) | completa, 56 tablas | | | | | B2s |`: cuatro celdas
   vacías. Rellenarla con la nocturna del 08-sep.
3. **R24 y T14 · no hay rastro de la verificación que cierra la feature.** Lo
   único medido contra Azure (31 iguales · 25 distintas, 16:30 UTC del 08-sep)
   es con el criterio **viejo** y salió con código 1. Nadie ha ejecutado
   `check-raw-recuentos` **con la tolerancia nueva**, ni `check-diccionario`,
   tras la nocturna: lo dice el implementer en el §6 de
   `progress/impl_F-066_tolerancia_recuentos.md`. Ejecutarlos y pegar la salida.
   **Yo tampoco lo he ejecutado**: la nocturna `29815200` está corriendo y el
   comando hace 56 `COUNT(*)` contra Sigrid y contra un Postgres bajo carga; y
   R24 lo define como MANUAL (humano).
4. **C5 · `tasks.md` tiene T13 y T14 en `[ ]`**, y su sección «Estado de las tres
   MANUAL (2026-09-06)» sigue afirmando que R19, R20 y R24 están pendientes.
5. **C5 · seis commits sin tarea que los respalde.** `da965c8`, `29f7c62`,
   `4a3cd2c`, `e2e2ad8`, `ddcf8b2` y `084f75a` se rotulan `F-066 T1…T6`, pero
   T1-T6 de `tasks.md` son las de la **ingesta**: la tolerancia no está
   declarada como tarea (el de columnas sí lo hizo bien, T17/T18). Añadir T19…
6. **C2 · `progress/current.md`** sigue fechado el 2026-09-07 y diciendo «C4 y C5
   quedan ABIERTOS hasta T13-T14». Actualizarlo al cerrar.

### El criterio nuevo: es honesto, no es bajar el listón

* **La dirección no es una excusa, es la señal.** Una fila de menos en Sigrid
  tumba el comando sea cual sea la magnitud. Antes eso existía, pero **ahogado**
  entre 25 falsas alarmas que nadie iba a leer; ahora sale en bloque propio.
* **El 0,05 % no es un número puesto para que salga verde.** Encajado entre dos
  cotas medidas —peor día real 0,0286 %, página perdida 0,072 % sobre
  `obrparpre`— y **las dos fijadas por un test** que lee la constante
  (`..._cae_en_la_unica_ventana_util`). Y relativo **por tabla** conserva la
  exactitud donde importa: 0,05 % de `conest` (193) no llega a una fila.
* **La grieta, dicha en voz alta** (observación, no bloqueo): 0,05 % de
  `obrparpre` son ~6.940 filas, y una pérdida menor pasa en verde. Es el suelo
  de cualquier tolerancia, y el fallo para el que se escribió el comando —`COPY`
  cortado, timeout a los 230 s— pierde páginas de 10.000, que sí caza. Revisar
  el umbral si baja `page_size` o aparece una tabla mayor.

### La campaña: los equivalentes son ciertos y el hueco `float` no bloquea

* **`recuentos.py:129` es equivalente de verdad.** Solo se alcanza con
  `sigrid`/`raw` no nulos —luego `diferencia` es `int`— y con `diferencia != 0`,
  porque el cero salió por el `return ESTADO_OK` de la 127. Sobre enteros no
  nulos, `d < 0`, `d <= 0` y `d < 1` son la misma función. El argumento depende
  **solo** de la guarda de la 127, y está probada: sus dos mutantes murieron.
  **RM3 en verde**: los equivalentes salen VIVOS.
* **El hueco del mutador es real, bien declarado, y NO bloquea.** Confirmé que
  `TOLERANCIA_DERIVA_PCT = 0.05` (L75) está en el alcance y **no genera ni un
  mutante**, y que en la L118 se muta el `*` pero no el `/`. Pero «ciego para la
  campaña» no es «sin probar»: **muté los dos sitios a mano y mueren** (abajo).

### Lo que he medido yo, no leído del informe

* **`bash harness/init.sh` · exit 0**, «ENTORNO LISTO», tal cual: **3.970
  passed, 159 skipped, 305,27 s**; `PUERTA COBERTURA` **[OK] 93,6 %** (788/842,
  critico); `PUERTA TAMAÑO` [OK]. Avisos de siempre: 216 de `ruff` y `blocked`.
* **Recálculo puro** con `harness.alcance` y `generar_mutantes`: tolerancia
  `b3abcf4..e2e2ad8` → **241 líneas (195+46) y 35 mutantes**; reconciliación
  `79059f8..ca1d6b9` → **180 líneas y 6 mutantes**. **Idénticos** a los informes,
  y los seis supervivientes de la 1.ª pasada existen como mutantes reales con el
  mismo operador y el mismo texto original→mutado.
* **RM5** (obligatorio en `critico`): reproduje un equivalente, `< 0` → `<= 0`:
  **70 passed**, sobrevive, como debe. **RM4 · los dos sitios ciegos, mutados a
  mano**: `0.05` → `0.1` mata 2 tests; `/ self.sigrid` → `* self.sigrid` mata
  **15**. Árbol devuelto a su estado exacto de partida.
* **RM1** · SHA medidos `ddcf8b2` y `ca1d6b9`; lo posterior no toca su alcance
  (`084f75a` solo `progress/`; F-068 solo las líneas 1276-1325). **RM2** ·
  35×121,8≈4.264,1; 35×110,6≈3.871,5; 6×348,6≈2.091,5: ningún salto de orden de
  magnitud. **Campañas NO reejecutadas** (4.264, 3.871 y 2.091 s, muy por encima
  del umbral de 60 s): recálculo puro más RM1-RM6, y lo digo para que se vea qué
  nivel se aplicó. **RM6** · ninguna guarda borrada; se **añade** una (`if not
  catalogo: return`), y `str.find` → `str.partition` quita el centinela `-1`, no
  defensa (equivalencia comprobada sobre 24 tipos).

### Checkpoints

* **C1 [x]** medido arriba. **C2 [ ]** `current.md` no describe el estado de hoy
  (punto 6). **C3 [x]** hexagonal intacta: `recuentos.py` sigue siendo dominio
  puro —sin BBDD, red ni ficheros—, el cliente en infraestructura y el CLI como
  único sitio con los dos; ruta en la 1.ª línea, sin `print()` ni secretos.
  **C3 bis** y **C4 ter N/A**: ni `docs/referencia/` ni `rutas_sensibles.json`.
* **C4 [ ]** R19, R20 y R24 sin cumplir (puntos 1-3). R15-R18 reformulados y
  trazados; R25-R28 con test propio; R21 verificado en `azure-apps` («56
  tablas», `pagtex`/`pagfor`, datos personales); `objetos_pendientes.yaml` con
  **cero** pendientes: nada aplazado en el diccionario.
* **C4 bis [x]** campañas válidas —sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto
  (base rota)» = 0—, análisis sin `PENDIENTE` en el informe que manda, fase RED
  con traza real y «Evidencias» completa. *Observación:*
  `mutacion_F-066_verificacion.md` es salida cruda y lleva dos `PENDIENTE`; no
  bloquea —el análisis está en `mutacion_F-066_tolerancia_recuentos.md`—, pero
  conviene una cabecera en el crudo que lo diga.
* **C5 [ ]** T13 y T14 en `[ ]`, y seis commits sin tarea (puntos 4 y 5).

| Requisito | Test que lo cubre |
|---|---|
| R15, R16, R17 | `test_f066_tolerancia_recuentos.py` (40) + `test_f066_recuentos.py` (30) |
| R25, R26, R27, R28 | `test_f066_reconciliar_columnas.py` |
| R19, R20, R24 | **sin cubrir**: son MANUAL (humano) y no están escritos |

## PASADAS 1 y 2 · resumen (verbatim en `git show 6f3db18:progress/review_F-066.md`)

**Pasada 1** (HEAD `26ce092`, completa): **RECHAZADO**, 10 hallazgos, 4
bloqueantes —una campaña que se declaraba a sí misma inválida por un test
aleatorio de F-024, y tres desajustes de papeleo—; el fondo quedó aprobado.
**Pasada 2** (desde `26ce092`): **APROBADO lo entregable**, los 7 cambios
cerrados y verificados uno a uno, con **C4 y C5 abiertos hasta T13-T14** y un
hallazgo no bloqueante (`b964c6e`, el cron de las 00:00 UTC de polizón). El
superviviente `bold=True` lo firmó el humano el 2026-09-06 a las 20:45 UTC.
