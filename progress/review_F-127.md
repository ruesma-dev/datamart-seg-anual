# F-127 · Revisión (reviewer, pasada principal)

Revisión completa (pasada 1): `git diff 90d1bfd...876edbe` (rama `feature/F-127-mayor-analitico`) y `azure-apps` 70a039a.

**Veredicto: CHANGES_REQUESTED.** El implementer cumple la spec aprobada, pero la spec tiene un hueco de
datos personales que la medición no vio: **60 filas de 3 cuentas CP de hecho llegan a
`contabilidad.mayor_analitico`** (cambio 1). Hace falta una decisión del humano antes de tocar código.

**Nivel de rigor:** `critico` (declarado): fase RED, cobertura 90 %, mutación con 0 supervivientes (60 %, [100, 300]), RM1-RM7; e2e informativa.

## Cambios requeridos

1. **[Decisión del humano, luego implementer] Tres cuentas de contrapartida se escapan de C3.**
   Medido en Azure (solo lectura, el SELECT de 08 como subconsulta): las filas visibles cuyas cuentas
   están en los centros de las CP son 49.845 de 197 cuentas. Casi todas son cuentas de gastos de `GG`,
   `0003` y `CM`, sin nombres. Pero **en el centro `CP` quedan visibles 3 cuentas y 60 filas**:
   `CP.MAD060001` (51 filas, la última del 2026-11-01), `CP.MAD030033` (7) y `CP.BAL150002` (2). Las tres
   tienen código `CP.*`, están en el centro de las contrapartidas, todas sus filas van a la `628` y sus
   descripciones (2 de 3) son palabras de nombres de recurso. Los conceptos son «NÓMINA», «PAGA EXTRA»,
   «NOMINA DICIEMBRE» y «FACT TELEFONICA MOVILES» más una palabra de nombre. **El mismo código
   `CP.MAD060001` es la CP actual de un recurso en otra empresa.** No son `caaconide` de nadie y no tienen
   abono `ANA`, así que ni C3 ni D7-b las cogen. La ficha general afirma «Las cuentas de contrapartida de
   los trabajadores no tienen fila», y es falso para ellas.
   Opciones con su tamaño hoy (para el líder → humano):
   - (c1) C3 incluye además **toda cuenta cuyo centro es el centro `CP`** (20 filas `raw.con` con
     `cod = 'CP'`, una por empresa): +60 filas, cierra las tres. De las 827 cuentas del centro, 802 ya
     son CP actuales.
   - (c2) Las cuentas con el **mismo código** que una CP actual en otra empresa: +51 filas. Solo cierra
     `CP.MAD060001`.
   - (c3) Aceptarlo y corregir las fichas (general y saldos), ARCHITECTURE y `azure-apps` para que digan
     que hay CP sin recurso visibles.
   Lo recomendado es (c1): falla cerrado, como D7-b, y cuesta 60 filas. El implementer, tras la decisión,
   toca el oráculo (`restriccion_personal.py`), el CTE `cp` de `08_mayor_analitico.sql:66-85` y su copia
   en la guarda de `10_mayor_analitico_general.sql:96-115`, los tests de R7/R10/R15 y las cifras de las
   fichas, de `current.md` (T13) y de `azure-apps`.
2. **[Implementer, según 1] Corregir las cifras y las frases que dependan de la decisión**:
   `contabilidad.yaml` (`saldos_cuenta_analitica_mes`: «Las cuentas de contrapartida ... no tienen
   fila»), los recuentos 181.712 / 540.919 / 998 cuentas de las fichas, de `current.md` y de
   `azure-apps/datamart_seg_anual.md`, y el «7 cuentas, 5.857 filas» de la ficha completa si cambia.
3. **[Recomendado, no bloqueante por sí solo] La guarda de R15 no vigila C2.** En
   `10_mayor_analitico_general.sql` vigila CP, el apunte restringido o sin resolver y el cuadre, pero
   no los asientos de personal. Hoy C2 coincide con C1 fila a fila (0 filas solo C2), así que no se
   escapa nada; una cuarta comprobación «0 filas cuyo `asiento_id` es AP del mayor completo» cierra la
   red sin coste. R15 no la pide: la decide el líder.

## La desviación 1 (D7-b: 5.857 filas, no 324): lo decide el humano

Verificado en Azure: el conjunto CP pasa de 853 a 860 cuentas (+7). Esas 7 cuentas tienen 5.857 filas,
de las que **324 son los abonos `ANA`** que citaba la spec. **La lectura del implementer es la que dice
el texto aprobado**: R7 define C3 por la cuenta («su cuenta analítica es una CP ... o una cuenta de un
centro de CP con abono en un asiento ANALITICO»), y D7-b dice «restringe DE MÁS». Las 324 eran las
filas que hacían CP a la cuenta, no las filas que se restringen. Restringir solo los abonos dejaría a la
vista los cargos de nómina y de móvil de una CP con nombre. El dato que cambia es el de T13: 181.712
restringidas y 540.919 generales, en lugar de ~178.301 y ~544.330. **Lo tiene que confirmar el humano**
junto con el cambio 1, que es de la misma familia.

## Puntos que pidió el líder

- **Fuga de lo personal.** `restringido` nunca es NULL: las cuatro marcas son booleanos no nulos
  (medido: 0 NULL de 722.631). El general es `WHERE NOT restringido`. 12 solo cuenta (`COUNT`) y 11 solo
  publica recuentos de lo restringido. Las tres guardas `DO $$` lanzan `RAISE` dentro de la transacción
  del fichero y fallan cerrado: si falta el mayor completo, la consulta casca. Hay dos excepciones: el
  cambio 1 y la guarda sin C2 (cambio 3). Las líneas visibles de los asientos `ANA`, los cargos a obra,
  no son una fuga nueva: el rol estándar ya lee `personal`, y el perfil restringido no lee `contabilidad`.
- **Tests de otras features.** F-056: `.get(table, 0)` afloja el doble, pero la lista exacta de
  `contados` lo compensa. F-135: `[:8]`, y los cinco nuevos los fijan `test_f056_r1` (la lista entera) y
  `test_f127_r18`. F-141: `NO_DISPONIBLES` crece, así que el test es más estricto. F-146: la tupla aparte
  solo entra en el test del diccionario, y la comprobación de `02_roles.sql` no cambia (el veto es de
  esquema). Ninguno pierde lo que protegía.
- **F-147.** Medido con `_medir` sobre los dos árboles: la base da 37.914 (8.376 + 19.439 + 10.099) y HEAD
  38.519 (8.394 + 20.026 + 10.099). +605 exactos, con el motivo en el historial del test.
- **`R-PERFILES`.** 996 caracteres (antes 978), regla y motivo. Sigue diciendo los cuatro perfiles y que
  el restringido no lee `contabilidad` (incluido el mayor analítico). Pierde «Lo que falta, en cada
  ficha», que ya dicen las fichas. Observación: «CP:» va sin expandir en la regla, aunque la ficha sí lo
  explica.
- **D3.** `DEFAULT_PERFIL_RESTRINGIDO_EXCLUDED_TABLES = ""` y las listas del restringido y del postventa
  sin `contabilidad` ni `contabilidad_restringida`. En `settings.py` solo cambian comentarios (diff
  revisado).
- **Diccionario v81.** Las cinco fichas, con clave, relaciones y aviso de acceso, y la v81. He barrido el
  diff entero de F-127 (fichas, tests, `progress/`) y el commit de `azure-apps` contra los nombres de
  `raw.res`: **0 nombres completos y 0 NIF**. Las 8 parejas que coinciden son falsos positivos («obra
  del», «centro de»). El test `test_f127_r22_ningun_nombre_de_persona` solo busca «Juan»/«Romero»: es
  débil, pero el barrido lo cubre.

## Checkpoints

- **C1** `[ ]` pendiente: la puerta completa la pasa el líder fuera del worktree, que no tiene `.env`, y
  aún no la he recibido. En su lugar he ejecutado la batería del líder: **3.994 passed, 22 failed, 387
  skipped (679 s)**. Los 22 son los mismos que caen en la base 90d1bfd, en un árbol extraído con `git
  archive`: 21 de `test_f006_comandos.py` y la frescura de `test_f006_reglas.py`, todos por
  `SigridApiSettings ... Field required`. Ajenos a F-127. `test_f127`: 181 passed, 1 skipped (el de
  `azure-apps`, por la ruta del worktree).
- **C2** `[x]` F-127 está `in_review`, es la única activa y va en su rama. **C3 bis** N/A: no entra
  ningún documento de fuera.
- **C3** `[x]` El dominio es puro y los cinco SQL están en `infrastructure/`. Primera línea con la ruta en
  todos los ficheros nuevos. Sin `print`, sin secretos y sin GRANT/REVOKE en el SQL. `ruff`: 2 avisos,
  los dos anteriores a F-127 (RUF100 en `test_f056:372`, que es la 356 de la base, e I001 en
  `test_f146:16`). Los campos vetados de `apa` (R4) no se leen.
- **C3 ter** `[x]`: los avisos de Juan llevan fecha y las preguntas de D8 constan como pendientes.
- **C3 quater** `[x]` 70a039a toca solo `datamart_seg_anual.md`, va en un commit aparte con su SHA en
  `impl_F-127.md`, sin push (`main` va 4 por delante: los otros 3 son de `facturas`), y coincide
  con la §7 de design. Si se aplica el cambio 1, hay que actualizarlo.
- **C4** `[x]` Cada requisito unit tiene su test (tabla abajo). R13, R20, R25 y R26 son MANUAL, con su
  comando en `current.md` (T12-T16). Los tests no tocan red ni BBDD.
- **C4 bis**: fase RED `[x]` (trazas reales de T1-T9 en el informe). Cobertura: pendiente de la línea
  `PUERTA COBERTURA` del líder; el dominio está al 100 % (89/89) según el informe. Mutación:
  **pendiente, pasada de evidencias** (la campaña va tras el APPROVED). RM1-RM6: pendientes de esa
  pasada. RM4 hecha ya (abajo). **RM7** `[x]`. «Evidencias» `[x]`. Capa e2e: N/A, es un ETL sin
  interfaz y ningún requisito es `(capa: e2e)`.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** `[x]` a esta altura: T1-T10 `[x]` con un commit por tarea. T11 es la campaña, T12-T16 son MANUAL
  y T17 la puerta del líder. El árbol está limpio.

## Verificación independiente (RM4 y RM7)
En una copia de HEAD (`git archive` al scratchpad, nunca en el worktree), con `pytest -x
tests/test_f127_mayor_analitico.py`, he probado 9 mutantes y los 9 mueren. En 08: sin C2, sin la unión
de D7-b, sin «apunte sin resolver». En 10: filtro `r.restringido IS NOT NULL`, sin la guarda de CP, con
el acumulado completo. En 11: el importe sin `FILTER`. En 12: con importe y sin `WHERE`.
**RM7 (el orden 08 → 10):** si muevo `mayor_analitico_general` delante de `mayor_analitico` en
`SUB_PASOS`, la suite de F-127 se pone en rojo por sí sola (2 failed), y también la de F-056 (4 failed).

## Cobertura requisito → test
| Req | Test(s) `tests/test_f127_mayor_analitico.py` |
|---|---|
| R1-R2 | `r1_el_completo_es_una_tabla…`, `r1_sin_filtrar…`, `r1_nada_multiplica`, `r1_indices…`, `r2_la_guarda_de_recuento` |
| R3 | `r3_columnas_en_orden`, `r3_la_base_sale_de_apa…`, `r3_tipo_de_asiento…`, `r3_centro_obra…` |
| R4-R6 | `r4_no_lee_los_campos_vetados_de_apa`, `r4_la_obra_solo…`, `r5_saldo_acumulado…`, `r6_la_unica_obra_de_cargo`, `r6_la_obra_imputada…` |
| R7-R9 | `r7_*` (dominio y SQL, C1-C3, D7-b), `r8_precedencia`, `r8_motivo_en_su_precedencia`, `r9_*` |
| R10-R12 | `r10_los_literales_del_sql_son_los_del_dominio`, `r11_el_acumulado_visible`, `r11_indice_parcial…`, `r12_*` · R13: MANUAL (T14) |
| R14-R15 | `r14_*`, `r15_guarda_sin_cp`, `r15_guarda_sin_apunte…`, `r15_guarda_general_mas…` |
| R16-R17 | `r16_*`, `r17_recuentos_por_motivo_sin_importes`, `r17_ni_debe_ni_haber_ni_importe` |
| R18-R19 | `r18_*` (los ocho de antes, los cinco al final, `depends_on`, cuenta los trece), `r19_*` · R20: MANUAL (T15) |
| R21-R23 | `r21_*`, `r22_*`, `r23_la_receta_de_la_cp_del_trabajador` |
| R24 | `r24_*` (el de `azure-apps` se salta en el worktree) · R25, R26: MANUAL (T13, T16) |

## Automejora (propuesta, no aplicada)
`spec-author.md` / `CHECKPOINTS.md` C4 bis: si una restricción se define por un CONJUNTO (las CP), medir
el **residuo visible de su familia** (mismo centro, prefijo o código en otra empresa), no solo lo que el
conjunto atrapa. D7 midió las cuentas con abono `ANA` y no vio las 3 del centro `CP` sin abono.
Azure: solo lecturas (`filas_solo_lectura`, READ ONLY) desde el checkout principal, que sigue sin cambios.
