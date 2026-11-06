Revisión completa (pasada 1), diff da6c36f..06a92f0 (`main` = da6c36f, merge en 7569cb9)

<!-- progress/review_F-157.md -->
# F-157 · Review · la fase 0 repartida en el tiempo

**Veredicto: APPROVED**, con una condición: la puerta completa de `bash harness/init.sh` que
pasa el líder sobre 06a92f0 en la copia con `.env` tiene que salir en verde, y la línea
`PUERTA COBERTURA` en `[OK]`. En el worktree `init.sh` sale rojo solo por el `.env` (está
prohibido crearlo). Ese rojo es del entorno, no de la feature.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura ≥ 80 % de lo
cambiado y mutación muestreada (20 mutantes, semilla 20260820). RM5 no aplica.

## Lo que ejecuté yo (worktree y una copia en el scratchpad)

| Qué | Resultado |
|---|---|
| F-157 (dominio, SQL, step, diccionario) + F-019, F-025, F-042, F-052, F-073, F-118, F-006, F-079, F-147, F-149 | ver «Suite acotada», abajo |
| Sandbox de F-157 con DSN (Postgres local desechable `f155pg`) en la copia | `108 passed` (dominio+SQL+step+sandbox) |
| `git diff --stat main -- stg/08 mart cierre tesoreria retenciones maestro` | vacío (y también contra da6c36f) |
| `plan_mensual_fase0` fuera de `sql/stg/`: grep en `.sql` y `.py` | solo el step, el cliente y `stg/{00,01,09}` |
| `/*F157_FILTRO_OBRAS*/` en el 09 | 1 aparición (otra mención en la cabecera, sin `/* */`, no cuenta) |
| `harness.tamano --feature F-157` | dentro de topes (impl 199/220) |
| `git status` al terminar | limpio |

**Suite acotada.** Son 4.439 tests y tardaron 22 min.

- **En el worktree:** `81 failed, 4028 passed, 330 skipped`. Ninguno de los 81 rojos es de
  F-157. Todos son tests que arrancan el CLI de `main.py`, y fallan con
  `validation errors for SigridApiSettings` o con un `exit_code 1` de `CliRunner`, que es la
  falta del `.env`. Están en `f006_comandos`, `f006_reglas`, `f025_cli`, `f025_huella`,
  `f042_check_cierres`, `f042_huella`, `f052_cobertura`, `f052_comparar_huellas` y `f118_check`.
- **La prueba de que no es la feature.** Corrí el mismo conjunto sobre dos copias limpias
  (`git archive`): una de `main` (da6c36f) y otra de HEAD. Las dos dan la **misma** lista de
  rojos, 82 cada una; `diff` sale IGUALES.
- **El rojo número 82** es `test_f147_r8` y solo aparece en las copias, no en el worktree: es
  un artefacto de la copia, no de la feature.
- **Los tests de F-157** (121), sello, `TABLAS_ACOTADAS`, F-019, F-073, F-079, F-147 (salvo
  ese caso de las copias) y F-149: todos en verde.

## Mutación (C4 bis)

`harness.mutacion` no arranca aquí: su línea base corre la suite entera, que sale roja por el
`.env`. Hice lo mismo que en F-158:

- **Recálculo puro.** `alcance_de_feature` da 3 ficheros y 199 líneas (da6c36f..rama).
  `generar_mutantes` da 35 mutantes. La muestra de la herramienta (20, semilla 20260820) cae en
  `build_stg_step.py` (2) y `domain/planif.py` (18).
- **Los 20 ejecutados por mí**, con `aplicar_mutante`, sobre una COPIA (`git archive`) en el
  scratchpad (RM4), contra `test_f157_{dominio,sql,step,sandbox}` con sandbox: **20 muertos,
  0 supervivientes**, 351 s. Ejemplos: `:312 + "\n" → - "\n"` mata 7; `:814 if not obras → if
  obras` mata 5; `planif.py:39 frozen=True → False` mata 1 (`r8_posicion_es_inmutable`);
  `:86 not sin_nada and → or` mata 5.
- **La campaña manual del implementer** (21 mutantes, también del SQL). Su tabla del informe no
  trae el texto exacto, pero el script `scratchpad/f157_impl/mutar.py` sí lo trae, y con él
  reproduje tres filas al pie de la letra. D3 `posiciones[indice + 1 :]` → `posiciones[indice:]`
  SOBREVIVE (108 passed). Q3 `(posicion_mes - 1) *` → `(posicion_mes) *` MUERE (3 fallos:
  `r4_mes_de_inicio_y_anio_mes` y `r22_master_y_fase0`). V1, la vista sin `FILTER`, MUERE
  (`r11_cobertura`).
- **D3 es equivalente: lo acepto.** Se llega a la rama `elif any(...)` solo con la posición
  actual NO positiva, así que meterla en la búsqueda no cambia el `any`. Muerto no ha salido
  ninguno equivalente (RM3). Tampoco se quitó ninguna guarda (RM6).
- No hay `progress/mutacion_F-157.md`: es el N/A justificado de abajo.

## Las 11 desviaciones

1. **Redacción.** La acepto. La tabla abre con «El presupuesto vivo de hoy (fase 0), repartido
   en el tiempo» y dice que no se suma con los cierres ni con el master, y que se compara con
   ellos. Busqué «no es real», «ficticio» y «hipot…» en `stg.yaml`, ARCHITECTURE, CLAUDE.md y
   `azure-apps/datamart_seg_anual.md` (2ba73e3): ninguna aparición. Lo vigila
   `test_f157_r23_no_dice_que_no_sea_real`.
2. **R18 sin test de diff.** La acepto. Un test contra un SHA fijo prohibiría para siempre
   tocar `mart/` y `cierre/`. El 08 ya lo fija el sha256 de `test_f073_sql.py` (y
   `test_f157_r18_el_08_sigue_fijado_por_su_huella`). El diff lo medí yo: vacío.
3. **Puerta de disco sin un helper común.** La acepto: el design lo dejaba a criterio y así
   F-019 no se toca. Va antes de escribir y después del corte sin obras. Si la ocupación está
   alta o no se puede medir, lanza `PlanMensualAbortado` sin llamar a `execute_sql_text`
   (`r15` ×2, y el mutante S3 muere).
4. **El oráculo redondea a 6 decimales.** La acepto: es más fiel que el design. El regex hace
   un cast a `NUMERIC(18,6)` antes de comparar con > 0, así que sin redondear un `0.0000001`
   saldría positivo en Python y 0 en SQL. Lo cubren el test `r5_seis_decimales` y los 500
   aleatorios de la sandbox.
5. **Filtro de `plafec` inválido.** Lo acepto. El master hace lo mismo
   (`fa.plafec_date IS NOT NULL`), y sin el filtro un `anio_mes` NULL rompería el NOT NULL.
6. **La vista con `LATERAL ... LIMIT 1`.** La acepto. Equivale a unir por `presupuesto_id`
   porque `06_presupuesto.sql` hace `DISTINCT ON (obride, paride, amb, fas)`, y en Sigrid el
   índice `opaf` de `obrparpre` es único (`azure-apps/sigrid_tablas.md`). Por la misma razón
   la PK `(obra, ámbito, partida, anio_mes)` no puede chocar.
7. **Tres ficheros fuera de la lista del § 3.** Los acepto: los piden las puertas del
   diccionario (la ficha de la función, F-079 y el recuento de F-006).
8. **`PRESUPUESTO_MAX` sube a 34.253.** La acepto. Son +197 de enrutado de dos fichas de
   consumo, con su motivo en la historia del test, que es la convención de F-147.
9. **Nulos en las columnas `NOT NULL`.** Lo acepto como riesgo declarado, no como defecto. Es
   el mismo contrato que la rama master, y `dec_*` ya llega con `COALESCE` desde el 06. Lo que
   queda abierto es un `can` o un `pre` NULL de una partida de fase 0 con `planif`: tumbaría
   `build_stg`, y con él `mart` esa noche. Ver la observación 1.
10. **`init.sh` redirigido a un log.** La acepto: el comando sigue siendo el mismo.
11. **Tres fallos del diccionario que destapó la suite completa, ya corregidos.** Los acepto:
    `N:N`, la agregación `promedio` y el recuento de `current.md`.

## Checkpoints

- C1: [x] `init.sh` en verde, CONDICIONADO a la puerta del líder (el worktree solo falla por
  el entorno). [x] Están los ficheros del arnés.
- C2: [x] Una sola `in_progress` (F-157). [x] Rama `feature/F-157-planificacion-fase0`.
  [x] `current.md` describe la sesión. N/A `history.md`: F-157 aún no está en `done`.
- C3: [x] Hexagonal: `domain/planif.py` es puro (`re`, `decimal`, `dataclasses`), el SQL va en
  `infrastructure/.../stg/` y el sub-paso en `application/steps/`. [x] La primera línea lleva
  la ruta en `planif.py`, el 09 y los 5 tests. [x] Sin `print`, sin TODO y sin secretos (en el
  informe el DSN va con `***`). [x] Semántica Sigrid: los ámbitos 3 y 7 de `plan_mensual`
  intactos; la fase 0, aparte; ARCHITECTURE al día.
- C3 bis: N/A, no entra ningún documento de fuera.
- C4: [x] Cada requisito con su test (tabla abajo); R20-R22 y R25-R26 son MANUAL. [x] Sin red
  ni BBDD: la sandbox se salta si no hay DSN. [x] MANUAL listado: `current.md` remite a T12 y a
  design § 12, que trae los comandos exactos. [x] Los dobles: `PgFase0` solo añade
  `medir_ocupacion_disco_pct` y `count_rows`, los dos con la firma del cliente real, y los
  vigila `test_f025_contrato_cliente.py` (incluido en mi suite acotada).
- C4 bis: [x] Rigor declarado. [x] RED con salida real (T1, T3-T5, T6 y T9), y el commit
  21672ad solo trae tests. [x] Cobertura: el implementer declara 100 % de 71 líneas; la
  confirma la puerta del líder (en el worktree, `-x` para antes por el `.env`).
  - N/A justificado: no hay `mutacion_F-157.md`, porque la línea base exige el `.env`. Lo
    sustituyen el recálculo y los 20 mutantes de la herramienta ejecutados por mí (20/20).
  - [x] Muertos comprobados: los ejecuté yo, no me fié del recuento.
  - N/A justificado: no hay informe de la herramienta que juzgar, así que tampoco hay coste por
    mutante, cabecera «⚠ CAMPAÑA NO VÁLIDA», RM1 ni RM2. Lo que verifiqué es 06a92f0, el HEAD.
  - N/A RM5, por el nivel `estandar`. [x] RM6: no se quitó ninguna guarda.
  - [x] Campaña manual: el texto exacto está en el script y reproduje 3 filas.
    [x] El superviviente D3 está analizado (equivalente). [x] La sección «Evidencias» trae los
    cuatro números.
- C4 ter: N/A, no hay `harness/rutas_sensibles.json`.
- C5: [x] T1-T11 en `[x]`, cada una con su commit `F-157 Tn:`. T12 (MANUAL, en sábado) y T13
  (la puerta del líder) quedan para después, justificado. [x] Árbol limpio.
  [x] `features.json` en `in_progress`.

## Cobertura de requisitos

| Req. | Test |
|---|---|
| R1 | `test_f157_r1_columna_con_su_tipo`, `_sin_columnas_de_mas_ni_version`, `_clave_primaria_...`, `_va_detras_de_plan_mensual` |
| R2, R3 | `test_f157_r2_r3_solo_fase_0_...ide_mayor`, `r2_inserta_en_la_tabla_nueva`; sandbox `r2_r10`, `r3_r4` |
| R4 | `test_f157_r4_mes_de_inicio_y_anio_mes`; sandbox `r3_r4_ide_mayor_y_meses_desde_plafec` |
| R5 | `test_f157_r5_*` (dominio: hueco, no numérico, coma, negativo, 6 decimales, espacios; SQL: mismo CASE, regex y ventanas que el master) |
| R6 | `test_f157_r6_conservar`, `r6_mas_de_250...`, `r6_mismo_descarte_que_el_master`; sandbox `r6_r8` |
| R7 | `test_f157_r7_formula_literal_del_master`, `r7_importe_partida_es_el_de_presupuesto`; sandbox `r22` (importes) |
| R8 | `test_f157_r8_funcion_firma`, `_no_filtra`, `_usa_la_funcion`, `_posicion_es_inmutable`; sandbox `r8` ×2 (17 casos + 500 aleatorios) |
| R9 | `test_f157_r9_*` (0726 ×2, 0696, 0677, P4.03.06, vacíos al final) |
| R10 | `test_f157_r10_*`; sandbox `r2_r10` |
| R11 | `test_f157_r11_vista_de_cobertura`; sandbox `r11_cobertura` |
| R12 | `test_f157_r12_*` (orden, una pasada, domingo), `r12_cabecera_con_su_ruta` |
| R13 | `test_f157_r13_*` (marcador ×1 y en `fa0`, compone borrado+filtro, sin marcador o doble → `ValueError`, solo enteros); sandbox `r13` |
| R14 | `test_f157_r14_plan_sin_obras_no_toca_la_tabla` |
| R15 | `test_f157_r15_disco_por_encima_...`, `_disco_sin_medir_...` |
| R16 | `test_f157_r16_el_09_entra_en_el_sello_tras_el_08`, `_tabla_acotada`, `_entra_en_la_higiene` |
| R17 | `test_f157_r17_registra_las_filas_de_la_tabla` |
| R18 | `test_f157_r18_el_08_no_la_menciona`, `_sigue_fijado_por_su_huella`; mi diff, vacío |
| R19 | `test_f157_r19_nadie_fuera_de_stg_lee_la_tabla` |
| R20-R22, R25, R26 | MANUAL (T12, design § 12); R22 en sintético en la sandbox `r22` |
| R23, R24, R27 | `test_f157_diccionario.py` (13), más F-006, F-079, F-147 y F-149 |

## Cambios requeridos

Ninguno bloqueante. Observaciones para el líder:

1. **Antes del despliegue (T12, paso 0), una sonda de nulos.** Hay que añadirla a design § 12,
   con `filas_solo_lectura` y fuera de 00-05 UTC: `SELECT count(*) FROM stg.presupuesto pp
   JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id WHERE pp.fase_num = 0 AND pp.ambito_id
   IN (3,7) AND length(trim(op.planif)) >= 1 AND (pp.cantidad IS NULL OR pp.precio IS NULL)`.
   Si da más de 0, la primera noche tumba `build_stg` (desviación 9). Yo no la lancé: el
   worktree no tiene `.env`.
2. **Un borde del oráculo, sin impacto real.** `str.strip()` quita tabuladores y saltos de
   línea; el `trim()` de PostgreSQL quita solo espacios. Una posición que sea solo `\t`
   desaparece en Python y en SQL cuenta como 0. El master tiene el mismo `trim`, así que el
   SQL sigue siendo fiel a él. Solo divergiría la comparación con el oráculo, y la sandbox no
   lo genera. No pido cambio.
3. **Para próximas campañas manuales:** la tabla del informe debería traer el texto exacto
   original → mutado y el número de fallos, o versionar el script. El scratchpad no dura.

## Automejora (propuesta, no aplicada)

Es la misma que en F-158, y con esta ya van dos features. Propongo un `--tests` en
`harness.mutacion` que acote la suite de la línea base, o bien un modo «ejecutar la muestra
sobre una copia». Así un worktree sin `.env` podría producir `mutacion_F-XXX.md` válido, sin
que el reviewer tenga que reconstruir la muestra a mano.
