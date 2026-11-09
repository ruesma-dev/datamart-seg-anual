<!-- progress/review_F-040.md -->
Revisión completa (pasada 1): `git diff main...6392b0d` (merge-base `66b4eb0`, punta `6392b0d`)

# F-040 · Review · Fase 1: ventas, certificaciones, clientes y cobro

**Veredicto: CHANGES_REQUESTED.** Tres cambios concretos (§ Cambios requeridos) y, además, el
veredicto final queda condicionado a la puerta completa y a la campaña de mutación que pasa el
líder sobre `6392b0d` en la copia con `.env` (cifras exigidas en § Condiciones).

**Nivel de rigor:** `critico`, declarado en `features.json`. Exige fase RED con traza, cobertura
de lo cambiado ≥ 80 %, campaña de mutación con cero supervivientes salvo justificación aceptada
por el humano, y RM5 (demostración ejecutable de UN equivalente, elegido por mí).

Reviewer, 2026-11-09. Nada contra Azure ni Sigrid (el MCP no conectó: no medí `con.cod`). Sandbox y
mutación en mi scratchpad (`revisor/`), PG16 propio en el puerto 55441; árbol de trabajo limpio.

## Lo que verifiqué yo (no del informe)

| Comprobación | Resultado real |
|---|---|
| `init.sh` | No en el worktree (sin `.env`, rojo por entorno); la puerta completa es del líder |
| Tests F-040 con sandbox (`F040_SANDBOX_DSN` a mi PG16) | **2300 passed** en 12,9 s, igual que el informe |
| F-040 + `f024_cli` + `f047_nocturna` + `f148` | 2419 passed, 1 skipped, 1 failed: `test_f024_r19` (pide `.env`, entorno) |
| RED | Las cuatro trazas (`red_t1/t10/t11/t14.txt`) existen y dicen lo que pega el informe |
| R30 | `git diff --stat main...6392b0d -- sql/retenciones sql/tesoreria sql/compras sql/postventa grants.py apply_grants_step.py`: **vacío** |
| Tests de otras features | Revisado el diff línea a línea: **solo listas, recuentos (93→100, 18→20) y el tope de F-147** (37.042, con desglose y motivo, precedente F-156). Ninguna aserción debilitada |
| Permisos (R27-R29) | `settings`, `.env.example` y `02_roles.sql` coherentes: `ventas` en consumo (punto 5); `ventas_restringida` en los DOS `ARRAY` del 5 ter, no en el `ARRAY['raw']` del total; USAGE + SELECT + default privileges al autorizado; comprobaciones finales del estándar, total, restringido y postventa al día |
| D4 / R12 | `CLASES_GARANTIA` solo en el dominio y el `IN (4, 5)` de `fn_clase_recargo`; el test exige que coincidan y que ningún otro SQL filtre por `reccla`. Las cuatro columnas son `FILTER` sobre un `CASE` total: no se solapan ni pierden nada |
| `double precision` | Todo `SUM` de `raw` castea por fila a `NUMERIC(18,2)`; ningún `ROUND` en `sql/ventas/`. La guarda R25 usa el mismo cast en los dos lados |
| Alcance (`harness.alcance`, base `main`) | 5 ficheros, 450 líneas: `settings.py`, `build_ventas_step.py`, `diccionario.py`, `ventas.py`, `main.py` (= el informe) |
| Mutantes (`generar_mutantes`) | **57**: 12 en `build_ventas_step.py`, 45 en `ventas.py`, 0 en los otros tres |
| Mutación RM4 (subconjunto, copia en scratchpad) | **57 evaluados, 51 muertos, 6 vivos** en 915 s con los 8 `test_f040_*` + `f024_cli`, `f047_nocturna`, `f148` (sandbox activa). Vivos: L51 `slots=True→False` y `frozen=True→False` (equivalentes), L119 `exc_info=True→False`, L126 `rows = 0→1` y L133 `round(…, 2→3)` (solo cambian el log: `rows_processed` no se mueve) de `build_ventas_step.py`; y **`ventas.py` L228 `cobrado <= 0` → `cobrado <= 1`: superviviente REAL** (H3) |
| Ruff en lo nuevo | 5 avisos menores en tests (`SIM300`×3, `E741`, `SIM117`); `main.py` y `settings.py` sin avisos nuevos (71 = los de `main`) |

## Hallazgos

**H1 · `ventas.clientes.codigo_cliente` puede publicar un NIF (bloqueante).** Sale de `con.cod`
sin filtro (`01_clientes.sql`, `c.cod AS codigo_cliente`) y la guarda R24 (`07_guardas.sql`) solo
mira `cif` y `cif_cliente`. El propio implementer lo señala (§ 2.11) y lo aplaza a una medición
MANUAL **después** del merge y del despliegue: es decir, el dato llegaría primero al perfil
estándar y se miraría después. D2 y R24 («un CIF con forma de NIF de persona en `clientes`») piden
lo contrario, y en rigor `critico` con datos personales el orden no es negociable.

**H2 · El informe afirma un «fail-closed» que el código no hace.** § 2.7: «un CIF ilegible o un
`perfis` desconocido se tratan como persona física». Falso: `perfis` NULL cuenta como 0, un CIF
como `ES12345678Z` no casa con el patrón y se publica, y una factura de un `entide` ausente de
`raw.cli` sale `es_persona_fisica = FALSE` (`02_facturas.sql`) y publica sus descripciones. El
código cumple R6 tal como está escrito; lo falso es la garantía que el humano leerá.

**H3 · Superviviente real en `estado_seguimiento` (bloqueante en `critico`).** Con `cobrado <= 1`
ningún test falla: falta el caso frontera de lo cobrado entre 0 y 1 € (p. ej. `cobrado =
Decimal("0.50")`, `emitido = 100` → `COBRADA_PARCIAL`). El `CASE` de `05_vistas.sql` replica la
frontera, así que el test debe ir al dominio y a la sandbox (`r18_seguimiento_igual_al_dominio`).

**O1 · La guarda R24 avisa, pero no retira (no bloqueante; para el humano).** `execute_sql_file`
hace `COMMIT` por fichero: si `07_guardas.sql` revienta, lo filtrado ya está en `ventas` y legible
por el estándar hasta que alguien actúe. Opción: vaciar o revocar `ventas` si falla `guardas`, o
llevar R24 dentro de la transacción de `01`/`02`. Cambia el diseño: PARADA 1.

**O2 · Menores.** `v_contraste_certificado_obra` y `facturado` suman también las facturas anuladas
(`anulada`) y las rectificativas: es la base de Sigrid, pero la ficha no lo dice. `02_roles.sql`
mantiene «`lee = f` en las cuatro filas» junto a «seis filas» (texto viejo). `cobertura_enlace`
cuenta efectos BAJA de `raw.cob` en `FACTURA_EFECTO`/`EFECTO_FACTURA`.

## Checkpoints

| Punto | Estado | Motivo |
|---|---|---|
| C1 `init.sh` exit 0 | [ ] | Pendiente del líder. Su primera pasada con `.env` salió ROJA en `test_f006_los_recuentos_de_current_son_los_de_hoy` (`current.md` sin los recuentos de v75); lo ha corregido en el worktree (sin commitear) y relanzado |
| C2 una sola `in_progress`, rama, `current.md` | [x] | F-040 la única; rama `feature/F-040-ingresos` |
| C2 `history.md` de las `done` | N/A | F-040 no está `done` |
| C3 hexagonal | [x] | `domain/ventas.py` solo `re`, `decimal`, `typing`; el paso en `application`, el SQL en `infrastructure` |
| C3 primera línea, sin prints, sin secretos | [x] | Comprobado en los 24 ficheros nuevos; `02_roles.sql` y runbook § 15 sin `*_PWD` |
| C3 semántica Sigrid | [ ] | H1 (`codigo_cliente`) |
| C3 bis documentos de fuera | N/A | La feature no trae documentos externos |
| C4 cada requisito con test | [x] | Tabla siguiente; R34 es MANUAL (T18) |
| C4 unit tests sin red ni BBDD | [x] | La sandbox salta sin `F040_SANDBOX_DSN` y crea/borra su propia base |
| C4 MANUAL listadas | [x] | design § 9, impl § 5, `current.md` |
| C4 dobles comparados con el original | [x] | La sandbox usa los tipos reales de la ingesta (`double precision`, `smallint`) |
| C4 bis rigor declarado | [x] | `critico` |
| C4 bis fase RED con salida real | [x] | Cuatro trazas reales, verificadas en disco |
| C4 bis cobertura | [ ] | 148/148 medido aparte por el implementer; falta la `PUERTA COBERTURA` de la puerta completa |
| C4 bis mutación, RM1, RM2, sin «NO VÁLIDA» | [ ] | No existe aún `progress/mutacion_F-040.md` (la campaña del implementer abortó, exit 3) |
| C4 bis supervivientes analizados, RM5 | [ ] | H3 + los cinco de log/equivalentes por justificar |
| C4 bis RM6 | N/A | No se quitó código defensivo |
| C4 bis campaña manual por cero mutantes | N/A | La automática genera 57 |
| C4 bis «Evidencias» con los cuatro números | [x] | Con la mutación sin veredicto, dicho así |
| C4 ter rutas sensibles | N/A | F-040 no declara `informe` extra en `features.json` |
| C5 `tasks.md` | [ ] | T17-T18 MANUAL tras merge (aceptable); T19 (puerta) pendiente |
| C5 sin temporales | [x] | Árbol limpio salvo la edición del líder en `current.md` |
| C5 `features.json` real | [x] | `in_progress` |

## Cobertura requisito → test

| Requisitos | Tests (`tests/test_f040_*`) |
|---|---|
| R1-R4 | `ingesta`: `r1_*` (20 columnas exactas, lista negra, prohibida → falla), `r2_*`, `r3_*` (35 y prohibida → falla), `r4_*`; censos en f066/f074/f090/f150/f156 |
| R5-R8 | `dominio` `r6_*`, `r8_*`; `sql` `r5_*`, `r6_*`, `r7_*`, `r8_*`; `sandbox_r5_r8_clientes`, `sandbox_r6_r8_funciones_iguales_al_oraculo` (2.000 CIF) |
| R9-R13 | `sql` `r9_*`, `r10_*`, `r11_*`, `r12_*`, `r13_*`; `dominio` `r11_*`, `r12_*`; `sandbox_r9_r11`, `r11_*`, `r13_*` |
| R14-R15 | `sql` `r14_*`, `r15_*`; `sandbox_r14_r15_certificaciones` |
| R16-R20 | `sql` `r16_*`-`r20_*`; `dominio` `r18_*`; `sandbox_r16`-`r20` |
| R21-R23 | `sql` `r21_*`-`r23_*`, `restringida_solo_en_su_esquema`; `sandbox_r21_r23` |
| R24-R25 | `sql` `r24_*`, `r25_*`; `sandbox_r24_r25_*` (pasa y revienta con la cifra en 6 casos); `pipeline` `r25_*` |
| R26 | `pipeline` `r26_*` (16 tests); f024/f047/f148 |
| R27-R29 | `grants` `r27_*`-`r29_*` (21 tests); f037/f135/f138/f156 |
| R30 | `frontera` `r30_*` (diff vacío, verificado también a mano) |
| R31-R33 | `diccionario` `r31_*`-`r33_*` |
| R34 | MANUAL (T18, design § 9 paso 6) |

## Cambios requeridos

1. **H1.** En `etl_sigrid/infrastructure/postgres/sql/ventas/01_clientes.sql`, publicar
   `codigo_cliente` a NULL si `es_persona_fisica` **o** si el código normalizado casa con
   `PATRON_NIF_PERSONA` (el íntegro, si hace falta, a `ventas_restringida.clientes_contacto`);
   añadir a `07_guardas.sql` la comprobación de `codigo_cliente` con el mismo patrón; un caso en
   `tests/test_f040_sandbox.py` (persona con `con.cod` = su NIF) que haga saltar la guarda, y la
   ficha de `config/diccionario/ventas.yaml` (línea 50) al día. Alternativa aceptable: medir antes
   del merge, en solo lectura, cuántos `con.cod` de tipo 4 casan con el patrón, y dejar la cifra
   en el informe; si es 0, basta la guarda.
2. **H2.** Corregir `progress/impl_F-040.md` § 2.7: o se borra la frase, o se hace verdad (y
   entonces con test). Mínimo: decir que `perfis` NULL, un CIF con prefijo de país y una factura de
   un cliente ausente de `raw.cli` se tratan como persona JURÍDICA.

3. **H3.** Test frontera de `estado_seguimiento` con `0 < cobrado < 1` en
   `tests/test_f040_dominio.py` y el mismo caso en la sandbox (vista = dominio). Los cinco vivos
   de `build_ventas_step.py`, justificados en `progress/mutacion_F-040.md` (o matados con test).

## Condiciones (lo que necesito del líder para cerrar)

- **Puerta:** `bash harness/init.sh` sobre `6392b0d` (o el commit con los cambios) con exit 0, nº
  de passed, y la línea `PUERTA COBERTURA` en `[OK]` con su porcentaje.
- **Mutación:** `progress/mutacion_F-040.md` con SHA completo de HEAD, línea base terminada (sin
  «⚠ CAMPAÑA NO VÁLIDA» ni «Sin veredicto (base rota)»), **57 mutantes**, y cada superviviente con
  su análisis. Por mi pasada RM4 espero como mínimo el de `ventas.py` L228 (real, H3) y los cinco de `build_ventas_step.py` (equivalentes o de log, a justificar uno a uno); si salen más, cada uno trae
  test o justificación. RM5: reproduciré la demostración del equivalente que elija.

## Automejora (propuesta, no aplicada)

Que el diseño de toda guarda de datos personales en un SQL aparte diga qué pasa con lo ya publicado
si salta (O1); candidato a C4 ter de `CHECKPOINTS.md` y a `arnes-base`.
