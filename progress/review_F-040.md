<!-- progress/review_F-040.md -->
Revisión incremental desde 6392b0d (pasada 2): `git diff 2dba699..39c21d4` (2dba699 = mi informe de la pasada 1)

# F-040 · Review · Fase 1: ventas, certificaciones, clientes y cobro

**Veredicto: APPROVED (APROBADO), condicionado SOLO a la campaña de mutación** que corre el líder
sobre `39c21d4` (cifras exigidas en § Condición). Si la campaña no las cumple, este veredicto no vale.

**Nivel de rigor:** `critico` (declarado en `features.json`). Exige RED con traza, cobertura ≥ 80 %
de lo cambiado, mutación con cero supervivientes salvo justificación aceptada por el humano, y RM5
(demostración de UN equivalente, elegido por mí).

Reviewer, 2026-11-09. Nada contra Azure ni Sigrid. Sandbox y mutación en copias de mi scratchpad
(`revisor/copia`, `revisor/copia2`), con un PG16 propio en el puerto 55441, ya parado. Árbol limpio.

## Pasada 1 (6392b0d), en resumen

CHANGES_REQUESTED por H1 (`ventas.clientes.codigo_cliente` = `con.cod` sin anular ni guarda), H2 (el
§ 2.7 del informe prometía un «fail-closed» que el código no hace) y H3 (superviviente real
`cobrado <= 0` → `<= 1` en `estado_seguimiento`). También una nota para el humano (O1) y varios
menores (O2). Lo que entonces quedó comprobado sigue valiendo: R30 sin diff, permisos R27-R29
coherentes, D4 con un único punto de decisión, casts a `NUMERIC` y RED real.

## Pasada 2 · qué verifiqué

| Comprobación | Resultado real |
|---|---|
| Puerta completa (líder, copia con `.env`, `39c21d4` exacto) | exit 0, **11056 passed, 2461 skipped**, 4733,98 s, «ENTORNO LISTO»; TAMAÑO OK. Los skipped de más son la sandbox de F-040 sin DSN |
| `PUERTA COBERTURA` (líder, datos de esa ejecución, `--base main`) | **100,0 % (155/155)**, umbral 80 %, nivel `critico` |
| Tests F-040 con mi sandbox | **2319 passed** en 22,3 s (eran 2300: +19 de H1 y H3) |
| H1 (`3ca7aea`) | `01_clientes.sql`: `codigo_cliente` NULL si `es_persona_fisica` o si el código normalizado casa con `PATRON_NIF_PERSONA`; íntegro en `ventas_restringida.clientes_contacto` (`LEFT JOIN raw.con` tipo 4, 1:1 por `ide`); guarda R24 ampliada a `codigo_cliente`. Hay oráculo en el dominio (`codigo_cliente_publicado`), con los literales del SQL atados a él por test. La sandbox cubre la persona física con código propio, el código con forma de NIF en una sociedad (`87654321-x`) y dos casos que tumban la guarda. Fichas y `design_detalle` (enmienda), al día |
| H2 (`445608c`) | § 2.7 reescrito: dice qué NO es persona física. Las propuestas (a) y (b), sin aplicar y pendientes del humano |
| H3 (`96b3630`) | Fronteras 0,01 / 0,50 / 1 y «emitido 0» en el dominio, y la vista = el dominio en la sandbox. **Lo reproduje** en `copia2`: `cobrado <= 1` → 1 failed, y `cobrado < 0` → 1 failed |
| O2 (`d7f4fb1`) | Fichas de `facturado_origen` y `cobertura_enlace` al día; `02_roles.sql`: «seis filas». Sin cambio de comportamiento |
| Base roja B1-B9 | Línea por línea, más abajo: **ningún test relajado** |
| Alcance (`harness.alcance`, `39c21d4`) | 5 ficheros, **465 líneas** (eran 450). **58 mutantes**: 12 en `build_ventas_step.py` y **46** en `ventas.py` (+1: L141, `and` → `or` en `codigo_cliente_publicado`) |
| Mutante nuevo L141 (RM4, `copia2`) | **Muerto**: 1 failed en `test_f040_dominio`/`_sandbox` |
| RM5 (equivalente elegido: L51 `frozen=True → False`) | Sobrevive a 2419 tests en mi RM4 de la pasada 1, y `grep` confirma que nadie asigna atributos a un `_SubStep` de ventas (los tests solo parchean `SUB_PASOS` con `monkeypatch`). Equivalente demostrado |

## La base roja (B1-B9): ¿se relajó algún test?

- **B1, `R-SIGRID-CON`** (`055033f`). Cambia la regla, no el test (R9 de F-006, que barre el SQL).
  Punto 3: `cli.cif`, `cli.raz` y `dvfpro.res` se leen de su tabla, cierto en `01`, `06` y
  `02_facturas`. Punto 4: entra `cerprodes`, que no se une a `con` (`04_enlace`), y sale `dvf`, que
  ahora sí se une (`02_facturas`, `LEFT JOIN raw.con c ON c.ide = f.ide`). Es correcto: la regla
  dice lo que hace el SQL.
- **B6 y B8, `R-PERFILES`** (`a404042`, `9d148c8`). El tope de 1.000 caracteres no cambia. Del texto
  sale el paréntesis «`postventa_restringida`, también del POSTVENTA». Comprobado contra `main`: la
  primera frase de la `regla` («POSTVENTA = RESTRINGIDO + `postventa_restringida`») y el `resumen`
  lo siguen diciendo, así que la semántica para el MCP no se pierde. El `motivo` conserva la fecha
  de F-146 que exige su test y quita solo la de F-040, que estaba repetida. `ventas` y
  `ventas_restringida` siguen en el `ambito`.
- **B2**: fichas de `cerrec` y `dvfrec` con «No se traen 1 columna». **B3**: grupo H del
  inventario de F-079 (las cinco `ventas.fn_*`, como las de postventa en F-156). **B4/B5**: censos
  93 → 100. **B7**: las dos reglas nuevas en `REGLAS_TRAS_F147`, como F-140 y F-156. Todo son
  altas en listas o recuentos; ninguna aserción se debilita.
- Por qué no salieron antes: el `-x` de `init.sh` cortaba en el fallo de entorno, y así las
  tapaba. La lección va a Automejora.

## Checkpoints

| Punto | Estado | Motivo |
|---|---|---|
| C1 `init.sh` exit 0 | [x] | Líder, `39c21d4`, con `.env` |
| C2 una `in_progress`, rama, `current.md` | [x] | |
| C2 `history.md` | N/A | F-040 aún no está `done` |
| C3 hexagonal | [x] | El dominio solo usa `re`, `decimal` y `typing` |
| C3 primera línea, sin prints ni secretos | [x] | También en el delta |
| C3 semántica Sigrid | [x] | H1 resuelto |
| C3 bis | N/A | No entran documentos de fuera |
| C4 cada requisito con test | [x] | Tabla siguiente. R34 es MANUAL (T18) |
| C4 unit tests sin red ni BBDD | [x] | La sandbox salta sin DSN y crea y borra su propia base |
| C4 MANUAL listadas | [x] | design § 9, impl § 5 |
| C4 dobles = original | [x] | Tipos reales de la ingesta |
| C4 bis rigor | [x] | `critico` |
| C4 bis RED | [x] | Pasada 1: cuatro trazas. Ciclo 1: RED de H1 (15 failed) y de H3, que mata el mutante a mano |
| C4 bis cobertura | [x] | 100 % (155/155) |
| C4 bis mutación, RM1, RM2, sin «NO VÁLIDA» | [ ] | **Condición**: campaña en marcha |
| C4 bis supervivientes, RM5 | [x] / condición | RM5 hecho (L51 `frozen`); el resto, al llegar el informe |
| C4 bis RM6 | N/A | No se quitó código defensivo: H1 añade defensa |
| C4 bis campaña manual por cero mutantes | N/A | Hay 58 |
| C4 bis «Evidencias» | [x] | Al día con el ciclo 1 |
| C4 ter | N/A | F-040 no declara `informe` |
| C5 `tasks.md` | [x] | T1-T16 `[x]`. T17-T18 son MANUALES tras el merge, por diseño. T19 cumplido por la puerta del líder: marcarla al cerrar |
| C5 sin temporales / `features.json` | [x] | |

## Cobertura requisito → test (`tests/test_f040_*`)

| Requisitos | Tests |
|---|---|
| R1-R4 | `ingesta` `r1_*`-`r4_*`; censos en f066, f074, f085, f090, f138, f150 y f156 |
| R5-R8 | `dominio` `r6_*`, `r8_*`, `r24_codigo_cliente_publicado`; `sql` `r5_*`-`r8_*`; `sandbox_r5_r8_*`, `r6_r8_*` |
| R9-R13 | `sql` `r9_*`-`r13_*`; `dominio` `r11_*`, `r12_*`; `sandbox_r9_r11`, `r11_*`, `r13_*` |
| R14-R20 | `sql` `r14_*`-`r20_*`; `dominio` `r18_*` (con las fronteras de H3); `sandbox_r14`-`r20`, `r18_frontera_de_lo_cobrado` |
| R21-R25 | `sql` `r21_*`-`r25_*`, `r24_codigo_de_persona_o_con_forma_de_nif_a_null`; `sandbox_r21_r23`, `r24_r25_*` (8 casos que tumban la guarda) |
| R26-R30 | `pipeline` `r26_*`; `grants` `r27_*`-`r29_*`; `frontera` `r30_*` |
| R31-R33 | `diccionario` `r31_*`-`r33_*` |
| R34 | MANUAL (T18) |

## Condición (lo único pendiente)

`progress/mutacion_F-040.md` del líder sobre `39c21d4`, con:
- la fila «SHA de HEAD medido» = `39c21d4…` completo (RM1);
- línea base terminada y verde, sin «⚠ CAMPAÑA NO VÁLIDA» y con «Sin veredicto (base rota)» = 0;
- **58 mutantes**;
- un tiempo coherente (RM2);
- como mucho **los cinco supervivientes de `build_ventas_step.py`**: L51 `slots`, L51 `frozen`,
  L119 `exc_info`, L126 `rows = 0 → 1` y L133 `round 2 → 3`, cada uno con su justificación (están
  en impl § 7). Doy por buenos los equivalentes y los que solo tocan el log. En `critico` hace
  falta además que **el humano acepte esa justificación por escrito**.

Cualquier otro superviviente, o uno de `ventas.py`, reabre la review. Si la campaña tarda menos de
60 s, la reejecuto entera.

## Opinión sobre las propuestas H2, pendientes del humano (no condicionan el veredicto)

- **(a) Quitar el prefijo de país** antes del patrón de NIF: **a favor**, pero solo si lo que queda
  casa con el patrón (`ES12345678Z` → `12345678Z`). Así, un CIF de sociedad que empiece por `ES`
  seguido de otra cosa no se toca. Va en dominio y SQL a la vez, con el test de literales.
- **(b) Tratar como persona física la factura cuyo cliente falta en `raw.cli`**: **a favor**. Es
  coherente con la línea huérfana, que ya se trata así, y el coste es esconder alguna descripción
  de más. Mejor aún si una guarda cuenta cuántas facturas tienen `entide` fuera de `raw.cli`.
- **(c) `perfis` NULL sin cambio**: de acuerdo.
- **O1** sigue en pie para el humano. Hoy, si la guarda R24 salta, el paso queda FAILED, pero lo
  filtrado ya está commiteado en `ventas`.

## Automejora (propuesta, no aplicada)

- En rigor `critico`, que el implementer pase la suite entera **sin `-x`** antes de pedir review:
  B1-B9 eran fallos reales que el `-x` de `init.sh` tapaba detrás de los de entorno.
- Que el diseño de toda guarda de datos personales que vaya en un SQL aparte diga qué pasa con lo
  ya publicado si salta (O1). Ambas valen para `arnes-base`.
