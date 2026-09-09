<!-- progress/review_F-066.md -->
# F-066 · Revisión

## PASADA 4 · Revisión incremental desde `f94fae6` (cierre)

HEAD `984358c`. De los 7 commits del delta, `ddcf8b2` y `084f75a` **ya se
aprobaron en la pasada 3**; los cinco de cierre (`77500d6`, `ad2ca8c`,
`d13810e`, `75c153b`, `984358c`) **no tocan ni una línea de Python**
(`git diff --name-only 77500d6..HEAD -- '*.py'` sale vacío; el único `.py` de
todo el delta es `tests/test_f066_tolerancia_recuentos.py`, ya revisado). Nada
invalida lo aprobado: el alcance medido por las campañas no se mueve, así que
RM1 sigue en pie. Pasadas 1-3 resumidas abajo; íntegras en
`git show 084f75a:progress/review_F-066.md`.

### Veredicto: APPROVED

**Rigor `critico`** declarado: fase RED, cobertura, mutación con 0
supervivientes o firma, y «Evidencias». Todo eso estaba aprobado en la pasada
3. Faltaba **la prueba en el repositorio** de que T13 y T14 ocurrieron. Ahora
está, y no me la he creído: la he contrastado contra `_meta.etl_runs` y
`_meta.diccionario_publicacion`, que era mi objeción de fondo. **Los seis
cambios requeridos están cerrados.**

### Las evidencias constan, y las he verificado en la fuente

Consultas de solo lectura, agregadas, hechas por mí. **Cada cifra de
`mediciones.md` §3 coincide exactamente:**

| Tramo de `20260908T111652Z-570bb9` | `_meta.etl_runs` | §3 |
|---|---|---|
| `ingest_raw` | 25.491.959 filas / 2.454,1 s / SUCCESS | igual |
| `apu` · `dcopro` · `asi` | 2.155.571/166,3 · 788.415/141,3 · 783.765/24,4 | igual |
| `apa` · `hmores` · `dncpro` | 709.701/38,2 · 329.086/34,3 · 286.652/43,6 | igual |
| `dco` · `confir` · `dcf` | 72.241/19,8 · 70.057/6,7 · 165.503/54,6 | igual |
| `obrparpre` · `firma_origen` | 1.098,4 s · 57,8 s (921 filas) | igual |

Y lo que no estaba escrito y confirma el resto: **57 tramos, 0 no-SUCCESS** en
esa ejecución; **32 tramos, 20.147.626 filas, 1.832,4 s** en la línea base
`20260905T173031Z-d06188` —luego el +26,5 % / +33,9 % es correcto, y la
explicación de las 920 filas de `firma_origen` también—; y **57 tramos,
25.497.946 filas / 2.921,1 s, 0 no-SUCCESS** en la nocturna automática
`20260909T000017Z-868dc5`: las 56 tablas corren cada noche en producción.
`_meta.diccionario_publicacion` tiene **una fila**: versión **16**, hash
`9140b14dc991…`, 2026-09-09 **07:31:21 UTC**, 130 objetos, 822 columnas, 16
reglas, cobertura 100,0 %. Exactamente lo que pega §6.

### El episodio de `check-diccionario`: bien resuelto, y el cabo suelto es otro

**Publicar a mano no puede diferir de lo que publicará la nocturna, y es
demostrable sin ejecutar nada.** El comando manual y el paso
`publicar_diccionario` de `run-all` leen la misma entrada
(`config/diccionario/**`) y publican su hash. El último commit que toca ese
directorio es **`38e170c`** (F-068 T3): `git log b3abcf4..HEAD --
config/diccionario/` devuelve solo ése, y ninguno de los seis posteriores lo
roza. La imagen `r20260909-0520` se construyó a las 05:20 UTC con la rama en
`75c153b` (02:30 UTC), **posterior a `38e170c`**; luego su
`config/diccionario/` es idéntico al del árbol y el hash de esta noche será el
mismo. Y el batch del publicado a mano —`20260909T073120Z-254365`— duró **1
segundo sin un solo tramo de ingesta**: la escritura contra producción fue
**una acción concreta y acotada**, que es lo que `CLAUDE.md` exige, documentada
con su autorización.

**El cabo suelto real es el mismo de la avería**: del despliegue de
`r20260909-0520` no queda más que una frase —ni digest, ni commit del que se
construyó—. Lo de arriba es **inferencia mía a partir de horas de commit**, no
un rastro documental: si el tag se hubiera construido de otra rama, §6 seguiría
pareciendo cierta. **No bloquea**, y la comprobación barata está a mano: mirar
mañana que `_meta.diccionario_publicacion` traiga `9140b14dc991…` con un batch
nocturno.

### Checkpoints

* **C1 [x]** medido abajo. **C2 [x]** `current.md` está fechado hoy y purgado
  (638 → 271 → 122 líneas), describe solo la sesión activa y las MANUAL con su
  comando exacto; las tres features cerradas tienen su resumen en
  `history.md`. Ver la observación 3 sobre **cuándo** se escribió eso.
  **C3 [x]** trivial: el delta de cierre no toca código. **C3 bis** y
  **C4 ter N/A**: no entra ningún documento de fuera y no hay
  `rutas_sensibles.json`.
* **C4 [x]**, y era el que bloqueaba. **R19** cumplido en §3 (filas y segundos
  por tabla, total contra la línea base, créditos y SKU, verificado arriba);
  **R20**, la fila de F-065 en §4 con sus siete celdas; **R24**, las dos
  verificaciones MANUAL ejecutadas por el líder con la nocturna ya terminada y
  pegadas en §6 con hora, autor y código de salida: `check-raw-recuentos`
  **código 0, CONFORME** —51 iguales, 5 con deriva tolerada, **0 con filas que
  faltan en `raw`**, que es el criterio grave, y peor desviación 0,0080 %
  contra 0,05 %— y `check-diccionario` **código 0**, biyección 130/130.
  `config/objetos_pendientes.yaml` sigue en **`pendientes: []`**. Los unit
  tests no tocan red ni BBDD.
* **C4 bis [x]** sin cambio: no hay código nuevo, luego no hay campaña nueva
  que deber. Las tres siguen válidas (sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto
  (base rota)» = 0), supervivientes analizados —dos equivalentes con argumento
  y el `bold=True` firmado por el humano el 06-sep—, fase RED con traza real en
  los tres informes, y «Evidencias» completa también en `impl_F-066_cierre.md`,
  que declara N/A cobertura y mutación **con el motivo** (cero líneas de
  Python). RM1-RM6 revisitados: el delta no altera el alcance medido.
* **C5 [x]** `tasks.md` con las **27 tareas en `[x]`**; T19-T24 declaradas con
  su tabla `commit → tarea` diciendo en la primera frase que los seis commits
  se rotularon mal, que es lo honesto; T25-T27 con un commit cada una. Árbol
  **limpio**. `features.json` dice `in_progress`, el estado real hasta cerrar.

| Requisito | Test / evidencia que lo cubre |
|---|---|
| R15-R17 | `test_f066_tolerancia_recuentos.py` (40) + `test_f066_recuentos.py` (30) |
| R25-R28 | `test_f066_reconciliar_columnas.py` |
| R19, R20 | MANUAL: §3 y §4, contrastados contra `_meta.etl_runs` |
| R24 | MANUAL: §6, código 0 en los dos comandos |

### Lo que he medido yo

**`bash harness/init.sh` · exit 0**, «ENTORNO LISTO»: **3.970 passed, 159
skipped, 352,58 s**; `PUERTA COBERTURA` **[OK] 93,6 %** (788/842, `critico`);
`PUERTA TAMAÑO` [OK]; `BACKLOG.md al día`; avisos de siempre (216 de `ruff`,
`blocked` por F-052). Cuatro consultas agregadas a `_meta`. **No** he
reejecutado `check-raw-recuentos` ni `check-diccionario`. **Campañas no
reejecutadas** (4.264, 3.871 y 2.091 s, muy por encima del umbral de 60 s):
vale el recálculo puro de la pasada 3, que no cambia porque el alcance tampoco.

### Observaciones no bloqueantes y acciones de cierre

1. **§6 dice «pegar la salida entera, tal cual» y pega la última línea
   (`conest`) más el resumen.** Los cuatro criterios están en el resumen, así
   que no bloquea; pero **las 5 tablas con deriva tolerada quedan sin
   identificar** (solo se nombra `dcopro`, la peor), y si mañana una empieza a
   separarse no hay contra qué compararla.
2. **R19 pide «créditos al empezar y al terminar» y lo escrito es una cota**
   (mínimo 552 de 576, ≤ 24 gastados), declarada como tal sin disimulo.
   `cpu_credits_remaining` retiene 93 días: la serie es recuperable.
3. **El cierre se escribió antes que el veredicto, y hay que decirlo.** Durante
   esta pasada, `current.md`, `history.md` y `features.json` cambiaron en
   disco: la feature quedó en **`done`** y `history.md` ya afirma «Veredicto
   **APPROVED** en la cuarta pasada». `CLAUDE.md` prohíbe marcar `done` **sin**
   veredicto aprobado del reviewer, y aquí el orden se invirtió. **No cambia mi
   veredicto** —lo alcancé sobre las evidencias que verifiqué yo, y el estado
   final coincide—, pero dar por hecho lo que aún no se ha emitido vacía la
   puerta. La parte buena: eso cerró de paso lo que iba a pedir aquí, porque
   `current.md` ya no dice que falte T14 y trae la versión **16** publicada.
4. **Dejar rastro del despliegue**: tag, digest y **commit del que se
   construyó** cada imagen, en una línea de `mediciones.md` o de `infra/`. Es
   la diferencia entre demostrar y suponer, y ya costó una avería.
5. Siguen pendientes de la pasada 3, ambas declaradas por el implementer:
   cabecera en `mutacion_F-066_verificacion.md` diciendo que es salida cruda, y
   la grieta del umbral —0,05 % de `obrparpre` son ~6.940 filas—: **revisarla
   si baja `page_size` o aparece una tabla mayor**. Menor, medido por mí: §6
   data el fin de la nocturna `29815200` a las 03:18 UTC y su último tramo
   termina a las **03:13:10**; inmaterial.

**Automejora propuesta (no aplicada).** C4 de `CHECKPOINTS.md` podría exigir
que una verificación `MANUAL` contra un entorno desplegado deje escrito **con
qué imagen** —tag y commit— se ejecutó. Este review ha tenido que reconstruirlo
por horas de commit: es la misma clase de agujero que la avería de agosto.

## PASADAS 1-3 · resumen (verbatim en `git show 084f75a:progress/review_F-066.md`)

**1** (`26ce092`, completa): **RECHAZADO**, 10 hallazgos, 4 bloqueantes; el
fondo, aprobado. **2**: los 7 cambios cerrados uno a uno, **C4 y C5 abiertos
hasta T13-T14**, más el hallazgo no bloqueante `b964c6e`. **3** (desde
`6f3db18`): **CHANGES_REQUESTED con el código APROBADO**, los seis puntos de
papeleo que cierra esta pasada. Allí quedó verificado, y no se repite aquí: la
tolerancia con dirección es honesta y está atada por tests (`0,05 %` encajado
entre 0,0286 % real y 0,072 % de página perdida); **RM3** en verde (los
equivalentes salen VIVOS); el mutador es ciego a las constantes `float` y a la
división, y esos dos sitios los muté a mano y **mueren** (**RM4**); **RM5**
reproducido; **RM6** sin ninguna guarda borrada.
