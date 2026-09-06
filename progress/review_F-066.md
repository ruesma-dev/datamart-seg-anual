<!-- progress/review_F-066.md -->
# F-066 · Revisión

## PASADA 2 · Revisión incremental desde `26ce092`

HEAD `6f3db18`, árbol limpio. Delta: `26ce092..HEAD`, 6 commits (los cuatro del
implementer más `5564975`, la firma, y `b964c6e`, que **no estaba en la lista** y
reviso abajo). Lo aprobado en la pasada 1 sigue aprobado: el delta **no toca
`etl_sigrid/` ni `main.py`**, solo tests, papeleo y `infra/env/dev.json`.
**La pasada 1 va abajo resumida** porque la puerta de tamaño da 140 líneas y ella
sola las ocupaba (`review 140/140`): se conservan su veredicto, sus 10 hallazgos
y sus checkpoints, y el texto íntegro está en
`git show 6f3db18:progress/review_F-066.md`.

### Veredicto: APROBADO lo entregable · C4/C5 abiertos hasta T13-T14 · 1 hallazgo nuevo, no bloqueante

Los 7 cambios requeridos están cerrados y lo he verificado uno a uno, **no leído
del informe**. Lo que NO se aprueba es el cierre: R19, R20 y R24 siguen
PENDIENTES porque T13 y T14 esperan al humano, y el informe lo dice con todas las
letras en vez de disimularlo. **Rigor `critico`**, declarado.

### Hallazgo por hallazgo

1. **CERRADO, y es el bueno.** El test de F-024 está **reescrito, no excluido**,
   y comprueba lo que R1 sí promete: la forma de los 500 y que el espacio de
   sufijos es real (≤ 3 colisiones toleradas y los 16 hexadecimales presentes).
   **`etl_sigrid/domain/` no se tocó** (verificado en el diff). **Remedí yo la
   estabilidad**, 3.000 pasadas del cuerpo del test: **0 fallos, máximo 1
   colisión** — clavado con lo declarado; con tolerancia 3 el fallo por azar cae
   a ~1,3e-10. Y la campaña repetida **NO lleva la cabecera «⚠ CAMPAÑA NO
   VÁLIDA»**; «Sin veredicto (base rota)» = 0.
2. **CERRADO.** `tasks.md`: T15 `[x]`, y sección nueva con **por qué** T13 y T14
   siguen `[ ]` (autorización del humano + no contaminar la nocturna de F-025).
3. **CERRADO.** `current.md` §«LAS VERIFICACIONES MANUAL … CON SU COMANDO EXACTO
   (C4)»: las cinco con su comando literal y su estado, el `--interval PT1M` y su
   porqué dentro. Igual que la de F-025.
4. **CERRADO.** `current.md` de 1.263 a **512 líneas**, **un solo** encabezado de
   F-066 y conservados los tres recuentos del diccionario (130/822/47) que exige
   `test_f006_los_recuentos_de_current_son_los_de_hoy`.
5. **CERRADO.** El informe de mutación abre con el comando entero
   (`--base d1f56aa --workers 1`) y explica que con `--base dev` salen 247
   mutantes en 11 ficheros porque la rama nace de la de F-025 sin fusionar.
6. **CERRADO.** Tres tests de R12 con **fase RED real** (traza del rojo
   inyectando `raw.conest` en `objetos_pendientes.yaml`). El par «no se aplaza» +
   «todas tienen ficha» es el correcto: uno solo pasaría también en el mundo sin
   fichas y sin declararlas.
7. **CERRADO, medido contra Sigrid.** `dncpro` = **286.432** en los cinco sitios
   (`design.md`, R9, `mediciones.md`, `tables_sigrid.yaml`, `raw.yaml`); no queda
   ni un 286.428. **8 y 10 · FICHADOS** en **F-069** (`6f3db18`) junto con mi
   automejora: verificado que la ficha recoge las tres y qué va a `arnes-base`.
9. **FIRMADO Y VERIFICADO.** La firma del humano (2026-09-06, 20:45 UTC,
   «firmo») consta en los **tres** sitios: ficha de F-066 en `features.json`
   (`5564975`), nota de T12 en `tasks.md` y `progress/mutacion_F-066.md`.

### Lo que he medido yo, no leído

* **`bash harness/init.sh` · exit 0**, «ENTORNO LISTO», ejecutado tal cual:
  **3.871 passed, 159 skipped, 317,57 s**; `PUERTA COBERTURA` **[OK] 92,5 %**
  (662/716, nivel critico); `PUERTA TAMAÑO` **[OK]**. Los avisos, los de siempre
  (212 de `ruff`, deuda previa; features `blocked`).
* **Recálculo puro** con `harness.alcance` y `generar_mutantes`: **218 líneas**
  (`recuentos.py` 134 + `main.py` 84) y **23 mutantes** (16 + 7), **idénticos**
  al informe. El superviviente existe como mutante real: mismo operador
  (`booleano`), misma línea (`main.py:1995`), mismo `bold=True` → `bold=False`.
* **Campaña NO reejecutada**: declara **2.072,2 s** (34,5 min), muy por encima
  del umbral de 60 s; me quedo en el recálculo puro más RM1–RM6, y lo digo para
  que se vea qué nivel de verificación se aplicó. Y **388 tests** recolectados en
  los tres ficheros (345 de F-066 + 43 de F-024): los de «Evidencias».
* **RM1** · HEAD medido `d8c73b8`; los cuatro commits posteriores tocan **solo**
  `BACKLOG.md`, `features.json`, `progress/` y `tasks.md`: nada del alcance.
  **RM2** · 23 × 90,1 s = 2.072,3 ≈ los 2.072,2 declarados, base 132,7 s (la
  media bajo la base es lo normal con `-x` y 22 de 23 muertos). **RM3** · el
  equivalente sale **VIVO**. **RM5** · reproducido en la pasada 1, y `main.py`
  no ha cambiado desde entonces. **RM6** · ninguna guarda borrada: el delta no
  toca código de producción Python.

### Hallazgo NUEVO · 11 · [no bloqueante]

**`b964c6e` viaja en esta rama y no es de F-066.** Cambia producción: `cron`
`0 2 * * *` → **`0 0 * * *`** y `replicaTimeoutSeconds` 18000 → **25200** en
`infra/env/dev.json`, más `docs/ARCHITECTURE.md` y `test_f003_r9`. No aparece en
`design.md`, en `tasks.md` ni en el informe de correcciones, cuyo «Sin cambios en
… `infra/`» solo es cierto de los commits del implementer.
**No bloquea, y por eso:** lo pidió el humano por escrito, está documentado en
`current.md`, propagado a `azure-apps` (`3916ca6`), cubierto por un test
actualizado y **corrige una divergencia real** (el job llevaba 25200 desde el
05-sep y el repositorio decía 18000). Verifiqué que no queda ningún `0 2 * * *`
ni ningún `18000` vivos fuera de specs históricas, y que no altera el alcance
medido: JSON, Markdown y tests, nada mutable.
**Lo que pido:** que el líder lo deje escrito donde toque —ficha propia o nota en
`tasks.md`— para que un cambio de producción no viva solo en el cuerpo de un
commit; y que tenga presente que la nocturna de la que dependen T13 y T14 corre
ahora **a las 00:00 UTC**, dentro de ~1 h desde que firmo esto (22:47 UTC).

### Checkpoints (pasada 2)

* **C1 [x]** `init.sh` exit 0 entero, medido arriba. **C2 [x]** una sola
  `in_progress`; rama correcta; `current.md` describe ya solo lo vivo, y la deuda
  de `history.md` está fichada en F-069.
* **C3 [x]** hexagonal intacta: el delta no toca `etl_sigrid/`; ruta en la 1.ª
  línea, sin `print()` ni secretos. **C3 bis N/A**: no toca `docs/referencia/`.
  **C4 ter N/A**: no hay `harness/rutas_sensibles.json`.
* **C4 [x] salvo R19, R20 y R24**, que dependen de T13/T14 y siguen PENDIENTES
  por decisión del líder. R12 ya tiene test trazable; R23 cumplido.
* **C4 bis [x]** los dos vacíos de la pasada 1, cerrados: campaña **válida** y
  superviviente **aceptado por escrito por el humano**, que es lo que `critico`
  exige para levantar `supervivientes_maximos: 0`. Fase RED y «Evidencias», ahí.
* **C5 [x] salvo T13 y T14**, legítimamente `[ ]` y justificadas por escrito.
  **Queda abierto para cerrar F-066:** T13, T14 y con ellas R19, R20 y R24.
  Ninguna es de código.

## PASADA 1 · resumen (verbatim en `git show 6f3db18:progress/review_F-066.md`)

**Revisión completa**, HEAD `26ce092`, diff `d1f56aa..HEAD`.
**Veredicto: RECHAZADO · 10 hallazgos, 4 bloqueantes.** El fondo quedó aprobado:
56 tablas sin duplicados, 56 fichas, dominio puro, dobles cruzados a mano contra
`SigridApiClient` y `PostgresClient`, `init.sh` exit 0 (3.868 passed, cobertura
92,5 %) y —reejecutando yo los 23 mutantes en un worktree aislado— **los mismos
22 muertos y 1 superviviente** del informe. Bloqueaba que la herramienta
declarase inválida su propia campaña, más tres desajustes de papeleo.

Los cuatro **bloqueantes**: (1) campaña con cabecera «⚠ CAMPAÑA NO VÁLIDA», con
la causa medida en el test aleatorio de F-024 (0,833 % de fallo en 3.000
pasadas); (2) `tasks.md` con T15 `[ ]` estando hecha; (3) las `MANUAL (humano)`
sin su comando exacto en `current.md`; (4) `current.md` con 1.249 líneas de
sesiones cerradas y el encabezado de F-066 duplicado. Los tres **menores**:
(5) el informe de mutación declaraba un comando que no reproduce sus números,
por no escribir `--base`; (6) R12 sin test trazable; (7) `dncpro` con 286.428 en
la spec y 286.432 en `mediciones.md`. Las tres **observaciones**: (8) la puerta
de dobles solo cubre `PostgresClient`; (9) el superviviente `bold` necesitaba la
firma del humano; (10) F-044 y F-047 `done` sin resumen en `history.md`. Más la
**automejora**: que el informe de mutación imprima su `--base`, y que
`reviewer.md` avise de que un worktree nuevo no hereda `.env`.

**Trazabilidad requisito → test** (sin cambios salvo R12, ya cerrado): R1–R9 en
`test_f066_r1..r9_*`; R10–R14 en los 14 tests sobre `raw.yaml`, `00_global.yaml`
y `objetos_pendientes.yaml`, **más los tres de R12 nuevos**; R15–R18 en
`test_f066_recuentos.py`; R21 y R22 en `azure-apps` (`a900682`) y `features.json`;
**R23 ahora cumplido**; R19, R20 y R24 PENDIENTES de T13/T14.
