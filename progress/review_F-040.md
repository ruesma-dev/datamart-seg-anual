<!-- progress/review_F-040.md -->
Revisión incremental desde fbb5063 (pasada 3): `git diff fbb5063..fcfd86f` (fbb5063 = mi informe de la pasada 2)

# F-040 · Review · Fase 1: ventas, certificaciones, clientes y cobro

**Veredicto: APPROVED (APROBADO), condicionado a dos cosas que corre el líder sobre `fcfd86f`:**
la puerta completa con `.env`, incluida la sandbox SQL de F-040 con DSN, y la campaña de mutación
(cifras en § Condición). Si alguna de las dos no sale como se exige, este veredicto no vale.

**Nivel de rigor:** `critico` (declarado en `features.json`). Exige RED con traza, cobertura ≥ 80 %
de lo cambiado, mutación con cero supervivientes salvo justificación aceptada por escrito por el
humano, y RM5 (demostración de UN equivalente, elegido por mí).

Reviewer, 2026-11-10. No he tocado Azure ni Sigrid. No he copiado `.env` ni ejecutado `init.sh` ni la
suite entera, porque así lo pidió el líder: el worktree no tiene `.env` y esa puerta la pasa él.
Árbol limpio al terminar.

## Pasadas anteriores (detalle en `git show fbb5063:progress/review_F-040.md`)

Pasada 1 (`6392b0d`): CHANGES_REQUESTED por H1, H2 y H3. Pasada 2 (`39c21d4`): APPROVED
condicionado a la mutación, con H1-H3 resueltos, B1-B9 sin tests relajados y RM5 hecho (L51
`frozen`). Lo aprobado se da por bueno: el delta no toca firmas ni mueve ficheros, pero amplía
el alcance de mutación (58 → 61), así que la campaña se repite.

## Pasada 3 · qué verifiqué (diff `fbb5063..fcfd86f`, 13 ficheros)

| Comprobación | Resultado real |
|---|---|
| Tests propios de F-040, sin sandbox (no hay DSN) | **280 passed, 2072 skipped**, 19,9 s. Los skipped son la sandbox |
| `test_f006_fichas`/`_reglas`/`_formato` (fichas cambiadas) | 1378 passed, 1 failed de entorno (`r9_frescura`, sin `SIGRID_API_*`); con valores ficticios, **passed** |
| **RED reproducido por mí**: código de `fbb5063` (`git archive` en mi scratchpad) + tests nuevos de `dominio`, `sql` y `diccionario` | **14 failed, 210 passed**. Fallan `'ES12345678Z' == '12345678Z'`, `'ESX1234567L' == 'X1234567L'`, `'PTK1234567A' == 'K1234567A'`, la falta de `PATRON_NIF_CON_PREFIJO_PAIS` y de `persona_fisica_de_factura`, los tres eslabones frente a cuatro, `'ES12345678Z' == None` en `codigo_cliente_publicado`, `COALESCE(vc.es_persona_fisica, TRUE)` y `'FACTURA_CLIENTE'` ausentes en el SQL. Coincide con el § 8 del informe, que además trae el RED de la sandbox (`{1005: (None, False)}`) |
| Alcance recalculado (`harness.alcance` + `generar_mutantes`, cálculo puro, `--base main`) | 5 ficheros, **484 líneas**, **61 mutantes**: **49** en `ventas.py` y **12** en `build_ventas_step.py`; 0 en `settings.py`, `diccionario.py` y `main.py`. Coincide con el informe |
| `azure-apps` `0f5ae73` | La fila de `cobertura_enlace` de `datamart_seg_anual.md` cuenta el eslabón nuevo. R2-a no cambia columnas ni objetos expuestos, así que no hay más que documentar |

### R2-a · SQL = dominio, caso por caso

- **Dominio**: limpia y pasa a mayúsculas; si casa `PATRON_NIF_CON_PREFIJO_PAIS`, `limpio[2:]`, si
  no `limpio or None`. **SQL**: `n = NULLIF(upper(regexp_replace(...)), '')` y
  `CASE WHEN n ~ <mismo patrón> THEN substr(n, 3) ELSE n END`; con `n` NULL, `~` da NULL y sale
  NULL por el `ELSE`, como el dominio. Dos tests atan los literales (SQL = dominio; patrón con
  prefijo = `"^[A-Z]{2}" + PATRON_NIF_PERSONA[1:]`).
- **Los que no cambian** (el patrón pide 11 caracteres: 2 letras, `[0-9KLMXYZ]`, 7 cifras y letra):
  `ESB12345678` (la B no está en la clase), `FR12345678901` (13) y `ES1234567Z` (10, y la E inicial
  tampoco es NIF: no es persona). Un NIF de 9 nunca casa, así que no hay doble recorte (`ESES…`).
  Todos están en el dominio y en la sandbox (CIF fijos y 2.000 aleatorios con prefijos).
- **Alcance**: todo pasa por `fn_cif_normalizado`: `es_persona_fisica`, `cif`, `cif_normalizado` y
  `codigo_cliente` en `01_clientes`; `cif_cliente` es `vc.cif`, ya anulado; la guarda R24
  normaliza en sus tres consultas (+3 casos que la tumban en la sandbox).

### R2-b · ¿algún camino deja pasar texto de una persona física a `ventas`?

Recorrí todo `sql/ventas/`. **No encontré ninguno.**
- `02_facturas`: `COALESCE(vc.es_persona_fisica, TRUE)`. Con un cliente ausente o con `entide` 0,
  `nombre_cliente` y `cif_cliente` salen NULL por el `LEFT JOIN`.
- `factura_lineas`: `COALESCE(f.es_persona_fisica, TRUE)`. Se anula si la factura es de persona o
  si no existe.
- `factura_lineas_persona` usa el mismo predicado, así que las dos tablas reparten las mismas líneas
  (la sandbox lo comprueba con 2006 y 2007).
- La cabecera (`entres`, `entcif`, direcciones) sigue solo en `ventas_restringida`.
- La guarda R24 de líneas usa `f.es_persona_fisica`, ahora TRUE para el cliente ausente, así que
  también cubre el caso nuevo.
- `FACTURA_CLIENTE` (`04_enlace`): `count(*)` frente a `count(c.cliente_id)` con
  `LEFT JOIN ventas.clientes`. La sandbox comprueba `(6, 5, 150.43, 130.43)`: 120,43 + 10 + 20, de
  las que 20 no tienen cliente. Solo cuenta, no lanza: no tumba el paso.

Lo que no bloquea va en § Observaciones.

## Checkpoints (pasada 3: delta + lo que el delta reabre)

| Punto | Estado | Motivo |
|---|---|---|
| C1 `init.sh` exit 0 | [x] condición | Lo ejecuta el líder sobre `fcfd86f` con `.env`; aquí no hay `.env` y está prohibido copiarlo |
| C2 una `in_progress`, rama, `current.md` | [x] | `current.md` al día con el ciclo 2 |
| C2 `history.md` | N/A | F-040 aún no está `done` |
| C3 hexagonal | [x] | El delta del dominio solo usa `re`. `persona_fisica_de_factura` es el oráculo puro, como `codigo_cliente_publicado` |
| C3 primera línea, comentarios en español, sin prints ni secretos | [x] | En los 13 ficheros |
| C3 semántica Sigrid | [x] | `raw.cli` por `entide`, `NULLIF(…, 0)` |
| C3 bis | N/A | No entran documentos de fuera |
| C4 cada requisito con test | [x] | Tabla siguiente |
| C4 unit tests sin red ni BBDD | [x] | La sandbox se salta sin DSN |
| C4 dobles = original | [x] | Las filas nuevas de la sandbox usan las columnas reales de `raw.cli`/`con`/`dvf`/`dvfpro` |
| C4 bis RED | [x] | Reproducido por mí (14 failed) |
| C4 bis cobertura | [x] condición | El 100 % que da el informe es del ciclo 1. La `PUERTA COBERTURA` de la puerta del líder sobre `fcfd86f`, ≥ 80 % |
| C4 bis mutación, RM1, RM2, sin «NO VÁLIDA» | [ ] **condición** | La campaña sobre `fcfd86f` aún no existe (`progress/mutacion_F-040.md` no está) |
| C4 bis supervivientes, RM5 | [x] / condición | RM5 ya hecho en la pasada 2 (L51 `frozen`). Los supervivientes, cuando llegue el informe |
| C4 bis RM6 | N/A | No se quita ninguna guarda: R2-a y R2-b solo endurecen |
| C4 bis campaña manual por cero mutantes | N/A | Hay 61 |
| C4 bis «Evidencias» | [x] | Los cuatro números. La mutación, delegada al líder (lo dice) |
| C4 ter | N/A | F-040 no declara `informe` |
| C5 `tasks.md` | [x] | Sin cambios desde la pasada 2. El ciclo 2 son enmiendas, no tareas nuevas |
| C5 diccionario y `azure-apps` | [x] | Fichas de `clientes`, `facturas`, `factura_lineas`, `cobertura_enlace`, las dos `fn_*` y las dos de la restringida. `azure-apps` en `0f5ae73` |

## Cobertura requisito enmendado → test

| Requisito | Tests |
|---|---|
| R6 (R2-a) | `dominio` `r6_prefijo_de_pais` (12 casos), `r6_el_patron_con_prefijo_es_el_del_nif`; `sql` `r6_la_normalizacion_es_la_del_dominio`; `sandbox` CIF fijos y aleatorios con prefijo, `r2b_…_y_cif_con_prefijo` (clientes 6 y 7) |
| R7 (R2-b) | `dominio` `r7_factura_sin_cliente_es_persona`; `sql` `r7_factura_de_cliente_ausente_es_persona`; `sandbox` `r2b_…` (factura 1006) |
| R20 | `dominio` `r20_cuatro_eslabones`; `sql` `r20_factura_cliente_…`, `r20_cobertura_…`; `sandbox` `r20_cobertura`, `r2b_…` |
| R23 | `sandbox` `r2b_…` (`factura_lineas_persona` 2006 y 2007) |
| R24 | `dominio` `r24_codigo_cliente_publicado` (+2 casos); `sandbox` `r24_r25_*` (+3 casos que tumban la guarda) |

## Condición (lo único pendiente)

1. **La puerta del líder sobre `fcfd86f`**, en una copia con `.env` y con `F040_SANDBOX_DSN`:
   `init.sh` en exit 0, la sandbox de F-040 en verde (incluido `test_f040_sandbox_r2b_…`) y la
   `PUERTA COBERTURA` ≥ 80 %. La sandbox es la única prueba ejecutada de que la SQL y el dominio
   coinciden y de R2-b. Si no corre, no hay aprobación.
2. **`progress/mutacion_F-040.md` sobre `fcfd86f`**:
   - la fila «SHA de HEAD medido» con el SHA completo de `fcfd86f…` (RM1);
   - la línea base terminada y verde, sin «⚠ CAMPAÑA NO VÁLIDA» y con «Sin veredicto (base rota)» = 0;
   - **61 mutantes**, con un tiempo coherente (RM2);
   - como mucho, los **cinco supervivientes de `build_ventas_step.py`** que el humano aceptó por
     escrito el 2026-11-10: L51 `slots`, L51 `frozen`, L119 `exc_info`, L126 `rows = 0 → 1` y
     L133 `round 2 → 3`.

   Cualquier superviviente de `ventas.py`, y en particular de las líneas nuevas 118, 129-130 y 145,
   reabre la review. Si la campaña tarda menos de 60 s, la reejecuto entera.

## Observaciones (no bloquean; para el humano o para F-104)

- **O3 · `contrato_nombre`** (`02_facturas`, `03_certificaciones`) es `raw.con.res` del contrato de
  venta, publicado en `ventas`. En el arrendamiento a una persona puede llevar su nombre. No lo
  bloqueo: es anterior a este delta y el nombre del cliente ya es público por decisión del humano
  (D2). Aun así, es texto libre como `dvfpro.res`. Si el humano quiere el mismo trato que las
  líneas, sería una enmienda más.
- **O4 · prefijos no cubiertos**: el humano fijó «dos letras». Un `ESP12345678Z` o un NIF de 7
  cifras con prefijo no se reconocen como persona y su CIF quedaría público. Hoy los recuentos no
  cambian, así que el riesgo es teórico; la guarda R24 tampoco los ve.
- **O5 · menores**: `factura_cabecera` (`06_restringida`) mantiene `COALESCE(…, FALSE)`, código
  muerto (`ventas.facturas` = `raw.dvf`, guarda R25) pero incoherente con el `TRUE` de R2-b; la
  ficha de `enlazados` no dice qué es en `FACTURA_CLIENTE`; el `COMMENT` trae un « , » suelto.
- **O1** (pasada 2) sigue en pie: si la guarda R24 salta, lo filtrado ya está en `ventas`.

## Automejora (propuesta, no aplicada)

- Que el reviewer pueda correr la sandbox sin `.env` (un DSN de PG local desechable en el entorno
  de la sesión): hoy la prueba SQL = dominio depende entera de la puerta del líder. Siguen las dos
  de la pasada 2 (suite sin `-x` en `critico`; política de lo ya publicado si salta una guarda).
