<!-- progress/review_F-159.md -->
Revisión completa (pasada 1): `git diff 8b2bf08..a7362ed` (punta `a7362ed`, `main` `8b2bf08` dentro)

# F-159 · Review · Hotfix 2: reparto por acumulado sobre la envolvente del plan neto

**Veredicto: APPROVED (APROBADO)**, condicionado a que la puerta completa que pasa el líder sobre
`a7362ed` en la copia con `.env` salga en verde. Si sale roja, este veredicto no vale.

**Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura de las
líneas cambiadas ≥ 80 % y campaña de mutación con los supervivientes analizados. RM5 no aplica.

Reviewer, 2026-11-08. Nada contra Azure ni Sigrid; mutación y RED en copias del scratchpad; árbol limpio.

## Lo que verifiqué yo (no del informe)

| Comprobación | Resultado real |
|---|---|
| `init.sh` | No lo ejecuté, por orden del líder: en el worktree sale rojo solo por el `.env`, y la puerta completa la pasa él |
| F-159 + F-158 + F-140 (dominio y SQL) | **275 passed** en 2,3 s |
| F-150 (todos) + F-147 + F-149 + F-157 | **839 passed, 24 skipped** en 42 s |
| F-006 del diccionario (fichas, formato, catálogo, unicidad, relaciones, nombres, punteros, regla de oro, cobertura) | **1621 passed, 303 skipped** en 150 s. No lancé `comandos` ni `reglas`: dependen del `.env` y del CLI, no de F-159 |
| RED reproducido | Los tests nuevos sobre una copia de `8b2bf08`: **13 failed, 6 passed**, los mismos que pega el informe |
| Caso 404326 con el algoritmo viejo (`proyeccion_caja.py` de `8b2bf08`) | `[(2026-11, -19438920.00), (2026-12, 19440000.00)]`. Con el nuevo: `0.00` / `1080.00` |
| SQL = dominio | Simulé el paso 5 a mano en Python: envolvente con `MIN` hacia delante y `GREATEST(0,…)`, `ROUND` a la mitad lejos del cero, `LAG` y el último mes entero. Lo comparé con `repartir_pendiente` en **18.849 perfiles con signo**, en COSTE y en VENTA (coeficiente de 0 a 3): **idénticos al céntimo**, cada mes en [0, p], ninguno por encima de p y la suma exacta en los dos conceptos |
| Cobertura (`coverage` + `harness.cobertura --base main`) | **`PUERTA COBERTURA: 100.0% de 16 líneas cambiadas cubiertas (16/16)`**, diff desde `8b2bf081b9` |
| Alcance recalculado (`harness.alcance`) | 1 fichero, 49 líneas: `proyeccion_caja.py`. El SQL queda fuera del alcance automático |
| Mutantes de la herramienta (`generar_mutantes`) | **12**, ejecutados uno a uno (RM4) con los tests de F-159, F-140 (dominio), F-150 (coeficiente y personal) y F-158. Resultado: **10 muertos y 2 supervivientes, los dos equivalentes** (tabla abajo) |
| Filas manuales reproducidas al pie de la letra | **D6**: `minimo = min(minimo, acumulados[i])` → `max(...)` muere en `r6_el_caso_1_0710` y en 7 tests más. **M1**: `MIN(a.plan_acumulado)` → `MAX(...)` muere en `r8_el_sql_sigue_al_dominio`. **M5**: quitar el bloque de la guarda R9 muere en `r9_la_guarda_nueva…` |
| Ruff en los ficheros tocados | 1 aviso, de antes: `RUF002` en la línea 331, que ya estaba en `93fc38c`. Ninguno nuevo |

| Línea | Original → mutado (`proyeccion_caja.py`) | Fallos /167 |
|---|---|---|
| 177 | `suma += plan` → `suma -= plan` | 16 |
| 179 | `[_CERO] * len(meses)` → `[_CERO] // len(meses)` | 27 |
| 181 | `range(len(meses) - 1, -1, -1)` → `range(len(meses) + 1, -1, -1)` | 27 |
| 181 | `… - 1, -1, -1)` → `… - 2, -1, -1)` | **0: equivalente** |
| 181 | `… - 1, -1, -1)` → `… - 1, -2, -1)` | **0: equivalente** |
| 181 | `… - 1, -1, -1)` → `… - 1, -1, -2)` | 17 |
| 186 | `ultimo = len(meses) - 1` → `+ 1` | 2 |
| 186 | `ultimo = len(meses) - 1` → `- 2` | 17 |
| 188 | `if i == ultimo` → `if i != ultimo` | 18 |
| 188 | `pendiente * envolvente[i]` → `pendiente // envolvente[i]` | 16 |
| 189 | `hasta - anterior` → `hasta + anterior` | 22 |
| 189 | `(mes, hasta - anterior, False)` → `True` | 10 |

**Los dos supervivientes son equivalentes**: solo cambian `envolvente[ultimo]`, que no se lee (el
último mes toma `hasta = pendiente`). El primero arranca en `n-2`, pero `minimo` ya empieza en
`total` = `acumulados[n-1]`; el segundo añade `i = -1`, que solo reescribe `envolvente[n-1]`. Ningún
equivalente sale muerto (RM3). El D17 del implementer también lo es: sin meses, `total` vale 0.

## Puntos que pidió el líder

- [x] **SQL y dominio dicen lo mismo.** Lo fijan la letra (`r8`) y mi simulación de 18.849 casos.
  `total_perfil` (línea 449) lleva el mismo filtro que `perfil` (línea 589), así que es `W(último)`.
- [x] **Con p ≥ 0, cada mes ≥ 0, suma p exacta y ningún mes por encima de p, en COSTE y en
  VENTA.** `W'` no decrece y acaba en `total`, así que `W'/total` está en [0, 1]. `ROUND` es
  monótono y `p` es `NUMERIC(18,2)`, porque lo son `stg.plan_mensual.importe_mes` y
  `mart…importe_mes` (`01_ddl.sql` 219 y 65). `pendiente_con_coeficientes` va redondeado al
  céntimo (línea 421). Lo comprueban `r3_r7_invariantes` (2.000 casos) y mi simulación.
- [x] **La ventana no tiene empates.** `_dev_plan` agrupa por (obra, concepto, partida, anio_mes)
  (línea 239): hay un mes por partición. `SUM … ORDER BY`, `MIN … DESC ROWS` y `LAG` son
  deterministas.
- [x] **La guarda no se puede saltar.** Es un `DO` con `RAISE EXCEPTION` entre `ANALYZE
  _dev_reparto` y `TRUNCATE …obra_mes`, y `r9` fija esa posición. Tampoco da falsos positivos:
  las filas del perfil traen pendiente 0 y personal NULL, y la VENTA trae el personal NULL.
- [x] **La traza RED existe.** Está en `impl_F-159.md` con la salida real, y la reproduje (arriba).
- [x] **Los céntimos que cambian están justificados** (recalculados a mano). F-140, 100/3:
  acumulados 33,33 / 66,67 / 100 → 33,33 / 33,34 / 33,33. F-150, 1.237,90 sobre 100/200/33:
  acumulados 371,74 / 1.115,23 → 371,74 / 743,49 / 122,67. F-158, 392521: último mes 8.249,99, lo
  que da el dominio ya validado contra el SQL; su RED se conserva con una copia privada de
  `fbf43dd`. Ningún test pierde lo que defendía (suma exacta, retraso sin perfil, mes más tardío
  al final, personal ≤ mes).

## Desviaciones del implementer

1. **Alias `r` en `repartido`.** Acepto: mismo SQL, conserva las aserciones de F-158.
2. **R50 con escalares `TEXT`.** Acepto. `SELECT … INTO` sin filas deja NULL, y la consulta va
   dentro del `IF`. Es asignación por E/S, válida en PL/pgSQL. Nunca se ha ejecutado contra un
   PostgreSQL (D6): ver la observación 2.
3. **La guarda no mira `importe_con_coef`.** Acepto: R9 no lo pide; con `pendiente_con_coeficientes` ≥ 0 la garantía es la misma (obs. 3).
4. **Dos `in_progress`.** Resuelto tras el merge de `8b2bf08`: solo queda F-159.
5. **Mutación manual.** Acepto con justificación (C4 bis), como en F-158: la línea base necesita
   el `.env`. A su tabla le faltan el texto exacto y los fallos por fila; la sustituyen los 12
   mutantes de la herramienta, ejecutados por mí, y las 3 filas que reproduje.
6. **Tests añadidos.** Acepto: matan D10 y D11.

## Checkpoints

- C1: [ ] → pendiente de la puerta del líder (rojo en el worktree solo por el `.env`). [x] Ficheros del arnés.
- C2: [x] Una sola feature `in_progress` (F-159). [x] Rama `feature/F-159-…`.
  [x] `current.md` lleva la sesión de F-159 arriba; las entradas de antes siguen la práctica del
  repositorio. [x] Las features `done` tienen su resumen (F-157 la cerró el líder en `main`).
- C3: [x] Arquitectura hexagonal: el dominio es puro y el SQL está en `tesoreria/07`. [x] La
  primera línea con la ruta está en los tres ficheros. [x] Sin `print`, sin TODO, sin secretos y
  sin dependencias nuevas. [x] Semántica Sigrid: no toca ámbito ni fase; `importe_mes` solo se
  acumula dentro de la partida y tras el cierre.
- C3 bis: N/A, porque no toca `docs/referencia/`.
- C4: [x] Cada requisito tiene su test (tabla abajo). [x] Sin red ni BBDD. [x] MANUAL listado
  (T7, `design.md` §6, con su comando). [x] No hay dobles nuevos.
- C4 bis: [x] Rigor declarado (`estandar`). [x] RED con la traza real. [x] Cobertura 100 %
  (16/16), medida por mí.
  N/A justificado para `mutacion_F-159.md`, coste por mutante, «⚠ CAMPAÑA NO VÁLIDA», RM1 y RM2:
  la línea base de la herramienta necesita el `.env` y no hay informe; lo sustituyen el alcance y
  los 12 mutantes recalculados y ejecutados por mí (la manual dice 46 s < 60: no me fié de ella).
  N/A RM5 (`estandar`). [x] RM6: no se quitó ninguna guarda; se añadió una.
- C5: [x] T1-T6 `[x]`, cada una con su commit `F-159 Tn:`. T7 (MANUAL) y T8 (la puerta del
  líder) quedan para después, como en F-158.

## Cobertura: requisito → test

| Req | Test |
|---|---|
| R1 | `r1_la_envolvente_absorbe…`, `r1_un_negativo_al_final…`, `r1_el_minimo_mira…`, `r1_suelo_cero…` |
| R2 | `r2_la_formula_por_acumulado`, `r2_multiplica_antes…`, `r2_el_ultimo_mes…`; F-140 `r14_el_redondeo_va_por_acumulado`; F-150 `r14_…con_coeficientes…` |
| R3, R7 | `r3_r7_invariantes` (2.000 casos con signo, con el personal encima) |
| R4 | `r4_sin_negativos_solo_cambia_el_redondeo` |
| R5 | `r5_neto_no_positivo_al_primer_mes`; F-150 `r14_…sin_perfil…` |
| R6 | `r6_el_caso_1_0710`, `r6_el_algoritmo_de_ayer_amplificaba` |
| R8 | `r8_el_sql_sigue_al_dominio`, `r8_la_cabecera_lo_dice` |
| R9 | `r9_la_guarda_nueva_antes_de_vaciar_la_obra_mes` |
| R10 | `r10_r50_nombra_su_primera_fila_negativa` |
| R11 | `r11_lo_que_no_cambia`; F-158 `r7_…` |
| R12 | `r12_fichas`, `r12_version_74_con_su_nota`; F-157 `r24_…` (`>=`) |
| R13 | MANUAL (T7, `design.md` §6) |

## Cambios requeridos

Ninguno bloqueante. Observaciones para el líder:

1. **La nota de F-159 en `features.json` está vieja** («pendiente de la PARADA 1»): actualízala al cerrar.
2. **El SQL nuevo no se ha ejecutado nunca contra un PostgreSQL.** Lo nuevo es `WINDOW w`, `MIN …
   OVER (… ROWS …)` dentro de `GREATEST` y el `INTO` de escalares `TEXT` de R50. Con D6 no hay
   sandbox, así que la primera ejecución será el paso 0 bis de `design.md` §6, en solo lectura.
   Ese paso es **obligatorio antes de construir la imagen**.
3. **Fuera de alcance, ya existía antes.** Si un día `coeficiente_venta` < 0 (el master se calcula
   como un cociente de oficial entre importe), `pendiente_con_coeficientes` saldría negativo y su
   reparto también. Ninguna guarda lo diría. Si se quiere, va como feature aparte.
4. **Automejora (propuesta, no aplicada; ya se pidió en F-158).** Añadir a `harness.mutacion` un
   `--tests` que acote la línea base a los ficheros afectados. Así, una feature sin `.env` puede
   sacar su `mutacion_F-XXX.md` formal en vez de una tabla manual sin texto exacto.
