Revisión completa (pasada 1), diff da6c36f..06a92f0 (`main` = da6c36f, merge en 7569cb9)

<!-- progress/review_F-157.md -->
# F-157 · Review · la fase 0 repartida en el tiempo

**Veredicto: APPROVED.** La puerta completa del líder sobre 06a92f0, en la copia con `.env`,
salió VERDE: 10.610 passed, 0 failed y tamaño en verde. Ahí la cobertura sale N/A (HEAD
detached), así que la medí yo sobre la rama: **100 % de 71 líneas cambiadas** (umbral 80 %).
**Rigor:** `estandar`, declarado en `features.json`. Exige RED, cobertura ≥ 80 % de lo
cambiado y mutación muestreada (20 mutantes, semilla 20260820). RM5 no aplica.

## Lo que verifiqué yo

| Qué | Resultado |
|---|---|
| Sandbox F-157 con DSN (Postgres local `f155pg`), sobre la copia | dominio, SQL, step y sandbox: `108 passed` |
| `git diff --stat main --` 08, `mart/`, `cierre/`, `tesoreria/`, `retenciones/`, `maestro/` | vacío (también contra da6c36f) |
| Quién lee `plan_mensual_fase0` (grep en `.sql` y `.py`) | solo el step, el cliente y `stg/{00,01,09}` |
| `/*F157_FILTRO_OBRAS*/` en el 09 | 1 vez; la mención de la cabecera no lleva `/* */` |
| Borrado e insert | en un solo texto y en un `execute_sql_text`: una conexión, una transacción |
| `git status` al terminar | limpio |

**Suite acotada.** Corrí F-157, F-019, F-025, F-042, F-052, F-073, F-118, F-006, F-079, F-147
y F-149: 4.439 tests en 22 min.

- **Worktree:** `81 failed, 4028 passed, 330 skipped`.
- **Los 81 rojos son de tests que arrancan el CLI de `main.py`.** Fallan por
  `SigridApiSettings` o por el `exit 1` de `CliRunner`, que es el `.env` que falta.
- **Comparación con `main`.** Corrí el mismo conjunto sobre copias limpias (`git archive`) de
  `main` (da6c36f) y de HEAD: la **misma** lista de rojos (82 cada una), y `diff` sale IGUALES.
  El rojo de más, `test_f147_r8`, es un artefacto de la copia.
- **Los 121 de F-157:** en verde, igual que sello, `TABLAS_ACOTADAS`, F-073, F-079 y F-149.

## Mutación (C4 bis)

`harness.mutacion` no arranca aquí: su línea base corre la suite entera, que sale roja por el
`.env`. Seguí el mismo criterio que en F-158.

- **Recálculo:** `alcance_de_feature` da 3 ficheros y 199 líneas. `generar_mutantes` da 35
  mutantes; la muestra de la herramienta (20, semilla 20260820) cae 2 en
  `build_stg_step.py` y 18 en `domain/planif.py`.
- **Ejecuté yo los 20**, con `aplicar_mutante` sobre una COPIA en el scratchpad (RM4) y con
  `test_f157_{dominio,sql,step,sandbox}`: **20 muertos, 0 supervivientes**, en 351 s. Dos
  ejemplos: `:312 + "\n"` → `- "\n"` lo matan 7 tests; `planif.py:39 frozen=True` → `False`
  lo mata `r8_posicion_es_inmutable`.
- **La campaña manual del implementer** (21 mutantes, SQL incluido). El texto exacto está en
  su script `scratchpad/f157_impl/mutar.py`. Reproduje tres filas:
  - D3 `[indice + 1 :]` → `[indice:]`: SOBREVIVE.
  - Q3 `(posicion_mes - 1) *` → `(posicion_mes) *`: MUERE, con 3 fallos (`r4` y `r22`).
  - V1, la vista sin `FILTER`: MUERE (`r11_cobertura`).
- **D3 es equivalente.** A `elif any(...)` solo se llega cuando la posición actual no es
  positiva, así que incluirla en el `any` no cambia nada. Ningún equivalente salió muerto
  (RM3) y no se quitó ninguna guarda (RM6).

## Las 11 desviaciones: todas aceptadas

1. **Redacción.** La ficha abre con «El presupuesto vivo de hoy (fase 0), repartido en el
   tiempo». Dice que no se suma con los cierres ni con el master, sino que se compara con
   ellos. Busqué «no es real», «ficticio» e «hipot…» en `stg.yaml`, ARCHITECTURE, CLAUDE.md y
   `azure-apps` (2ba73e3): cero apariciones. Lo vigila `test_f157_r23_no_dice_que_no_sea_real`.
2. **R18 sin test de diff.** Un test contra un SHA fijo prohibiría para siempre cambiar
   `mart/` o `cierre/`. El 08 ya queda fijado por el sha256 de F-073; el diff lo hice yo y
   sale vacío.
3. **Puerta de disco propia, sin helper.** Va antes de escribir. Si no puede medir, o si la
   ocupación está alta, lanza `PlanMensualAbortado` sin ejecutar nada (`r15` ×2; S3 muere).
4. **El oráculo redondea a 6 decimales.** Es más fiel que el design: el SQL convierte a
   `NUMERIC(18,6)` antes del `> 0`. Lo prueban los 500 `planif` aleatorios de la sandbox.
5. **Filtro de `plafec` inválido.** Es el del master (`plafec_date IS NOT NULL`). Sin él, un
   `anio_mes` NULL rompería el NOT NULL de la columna.
6. **La vista con `LATERAL ... LIMIT 1`.** Equivale al diseño. El 06 hace `DISTINCT ON
   (obride, paride, amb, fas)` y el índice `opaf` de `obrparpre` es único en Sigrid
   (`azure-apps/sigrid_tablas.md`), así que la PK de la tabla nueva no puede chocar.
7. **Tres ficheros fuera del § 3.** Los exigen las puertas del diccionario: F-006, F-079 y la
   ficha de la función.
8. **`PRESUPUESTO_MAX` 34.253.** Son +197 de enrutado, con su motivo escrito: la convención
   de F-147.
9. **Nulos en `NOT NULL`.** Es un riesgo declarado, con el mismo contrato que la rama master;
   `dec_*` ya llega con `COALESCE` desde el 06. Queda abierto `can`/`pre` NULL: ver la
   observación 1.
10. **El log de `init.sh`:** comando sin cambios. 11. **`N:N`, `promedio` y el recuento:** bien.

## Checkpoints

- C1: [x] `init.sh` verde en la puerta del líder (en el worktree solo falla
  el entorno). [x] Están los ficheros del arnés.
- C2: [x] Una sola feature `in_progress`. [x] La rama es la de la feature. [x] `current.md`
  está al día. N/A `history.md`: la feature aún no está en `done`.
- C3: [x] Hexagonal: `domain/planif.py` es puro (`re`, `decimal`, `dataclasses`); el SQL va en
  `infrastructure/.../stg/` y el step en `application/`. [x] La primera línea lleva la ruta en
  `planif.py`, el 09 y los 5 tests. [x] Sin `print`, sin TODO y sin secretos (el DSN del
  informe va con `***`). [x] La semántica de Sigrid se respeta y ARCHITECTURE está al día.
- C3 bis: N/A, no entra ningún documento de fuera.
- C4: [x] Requisitos con test (tabla abajo); R20-R22, R25 y R26 son MANUAL. [x] Sin red ni
  BBDD: la sandbox se salta sin DSN. [x] MANUAL listado: `current.md` remite a T12 y a design
  § 12, con sus comandos. [x] Dobles: `PgFase0` solo añade `medir_ocupacion_disco_pct` y
  `count_rows`, con la firma real, y los vigila `test_f025_contrato_cliente.py`.
- C4 bis: [x] Rigor declarado. [x] RED con la salida real; el commit 21672ad solo trae tests.
  [x] Cobertura: 100 % de 71 líneas, medida por mí sobre la rama.
  - N/A justificado: no hay `mutacion_F-157.md`, porque la línea base exige el `.env`. Lo
    sustituyen el recálculo y los 20 mutantes de la herramienta, ejecutados por mí (20/20).
  - [x] Muertos comprobados, ejecutados por mí. N/A justificado: sin informe de la
    herramienta no hay tiempo por mutante, ni cabecera «⚠ CAMPAÑA NO VÁLIDA», ni RM1 ni RM2
    que juzgar. El SHA que verifiqué es 06a92f0, el HEAD.
  - N/A RM5, por el nivel `estandar`. [x] RM6. [x] Campaña manual reproducible: 3 filas
    reproducidas. [x] Superviviente D3 analizado. [x] «Evidencias» con los cuatro números.
- C4 ter: N/A, no hay `harness/rutas_sensibles.json`.
- C5: [x] T1-T11 en `[x]`, cada una con su commit `F-157 Tn:`. T12 (MANUAL, el sábado) y T13
  (puerta del líder) quedan pendientes, justificado. [x] Árbol limpio. [x] `features.json`
  en `in_progress`.

## Cobertura de requisitos

| Req. | Test (`tests/test_f157_*`) |
|---|---|
| R1 | `r1_columna_con_su_tipo`, `_sin_columnas_de_mas_ni_version`, `_clave_primaria_...`, `_va_detras_...` |
| R2-R4, R10 | `r2_r3_solo_fase_0_..._ide_mayor`, `r2_inserta_...`, `r4_mes_de_inicio_y_anio_mes`, `r10_*`; sandbox `r2_r10`, `r3_r4` |
| R5, R9 | `r5_*` (hueco, no numérico, coma, negativo, 6 decimales, espacios; SQL igual que el master), `r9_*` (0726, 0696, 0677, P4.03.06) |
| R6-R8 | `r6_*`, `r7_formula_literal_del_master`, `r7_importe_partida_...`, `r8_*`; sandbox `r6_r8`, `r8` ×2, `r22` |
| R11 | `r11_vista_de_cobertura`; sandbox `r11_cobertura` |
| R12-R17 | `r12_*` (orden, pasada única, domingo), `r13_*` (+ sandbox), `r14_*`, `r15_*` ×2, `r16_*` ×3, `r17_*` |
| R18, R19 | `r18_el_08_no_la_menciona`, `_sigue_fijado_por_su_huella` (y mi diff vacío); `r19_nadie_fuera_de_stg_...` |
| R20-R22, R25, R26 | MANUAL (T12, design § 12); R22 en sintético con sandbox `r22` |
| R23, R24, R27 | `test_f157_diccionario.py` (13), más F-006, F-079, F-147 y F-149 |

## Cambios requeridos

Ninguno bloqueante. Observaciones para el líder:

1. **Una sonda de nulos en T12, paso 0** (añadirla a design § 12; solo lectura, fuera de 00-05
   UTC): `SELECT count(*) FROM stg.presupuesto pp JOIN raw.obrparpre op ON op.ide =
   pp.presupuesto_id WHERE pp.fase_num = 0 AND pp.ambito_id IN (3,7) AND
   length(trim(op.planif)) >= 1 AND (pp.cantidad IS NULL OR pp.precio IS NULL)`. Si sale
   > 0, la primera noche tumba `build_stg`. No la lancé: el worktree no tiene `.env`.
2. **Un borde sin impacto.** `str.strip()` quita `\t` y `\n`, pero `trim()` de PostgreSQL
   solo quita espacios. Una posición que sea solo `\t` desaparece en el oráculo y en el SQL
   cuenta como 0. El SQL sigue igual que el master. No pido cambio.
3. **Campañas manuales:** el texto exacto y los fallos van en la tabla (el scratchpad no dura).

**Automejora (propuesta, no aplicada):** segunda feature, tras F-158, con la línea base de
mutación roja por el entorno. Propongo un `--tests` en `harness.mutacion` que acote la suite.
