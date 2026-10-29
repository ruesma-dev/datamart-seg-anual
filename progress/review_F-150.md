<!-- progress/review_F-150.md -->
Revisión incremental desde b08f0b6 (pasada 3) · `git diff b08f0b6..289fedb` · HEAD `289fedb`

# F-150 · Review · la receta de la caja (fase 1)

**Veredicto: APROBADO** (pasada 3, el arreglo del despliegue). Pasada 1 (`6efddfe`): rechazo solo
por C4. Pasada 2 (`7eed62e`): APROBADO. Las tres siguen debajo, resumidas.

**Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED en los requisitos
centrales, cobertura de lo cambiado ≥ 80 % y mutación con los supervivientes analizados.

## Pasada 3 (arreglo del despliegue, 29-10)

- **Alcance:** `07` (1 línea), `test_f150_sql.py`, `impl_F-150.md`, `current.md`. Sin firmas ni otro SQL.
- **Cambio mínimo y en estilo:** `SUM(fv.totbas)` → `SUM(fv.totbas::NUMERIC(18, 2))` en el CTE
  `facturado`, el mismo cast que `c.totbas::NUMERIC(18, 2)` de `05:57` (F-140). Lo de aguas abajo
  (`ROUND(COALESCE(fa.facturado_origen, 0), 2)`, `GREATEST`) queda en `numeric`.
- **RED reproducido por mí** (worktree desechable en el scratchpad, ya borrado): con el `07` de
  `b08f0b6` y el test de `289fedb`, `-k "dvf or facturado"` → `AssertionError: importes de raw.dvf
  sin ::NUMERIC(18, 2): ['totbas']` · **2 failed, 2 passed**; con el `07` de `289fedb`, 4 passed.
  Coincide con la salida que cita `impl_F-150.md`.
- **Ninguna otra columna `raw` `double precision` en una función solo `numeric`** en lo que F-150
  añade a `00`, `06`, `07` y `08` (diff contra `a80bb1b`): `raw.iva.iva` va como
  `ROUND((i.iva * 100)::NUMERIC, 4)` en `06` y `08`; `coestr` es texto que `fn_coeficientes` pasa a
  `NUMERIC[]`; `op.ctride`, `ob.ivaide`, `ob.cenide`, `o.ivaide` solo se usan en `JOIN`/`NULLIF`
  (igualdad, válida con `double`); `stg.presupuesto.importe/importe_oficial` son `NUMERIC(18,2)`
  (`stg/01_ddl.sql:91-92`) y el resto viene de `mart`/`stg`/`tesoreria`. La prueba definitiva es
  la del líder: `build-tesoreria` con `d1c2ee1` acabó SUCCESS en Azure (229,3 s) y R30 cuadra.
- **`init.sh`:** acreditado en `impl_F-150.md` («Evidencias»): verde sobre `2d30248`, 9.646 passed
  / 266 skipped (5.902 s). `289fedb` solo toca `impl_F-150.md`, así que vale para HEAD. No lo
  reejecuto (instrucción del líder). Cobertura N/A justificada: sin Python de producción frente a
  `main`. Mutación N/A: el SQL no se muta; lo cubren el test de texto y la sandbox.
- **Progress:** `impl_F-150.md` trae causa, cambio, test con su RED, sandbox con `raw` en `double
  precision` (antes: el error de Azure; ahora: 66 OK) y la lección; `current.md`, la línea del
  29-10. Tamaño de `impl` 220/220. **Sin secretos** (barrido del diff vacío). Commits `F-150 ...`.
- **Aviso, no bloqueante:** `main` (`8b08d59`) lleva F-150 SIN el arreglo. Hasta integrar la rama
  y reconstruir la imagen del job, la nocturna volverá a caer en `build-tesoreria`.
- **Checkpoints del delta:** C1 `[x]` (acreditado) · C3 `[x]` capa y estilo · C4 `[x]` test que
  falla sin el arreglo · C4 bis `[x]` RED con salida real · C5 `[x]` árbol limpio, commits.

## Pasada 2 (`6efddfe..7eed62e`) · resumen

- C4 MANUAL corregido: la subsección «F-150 · Despliegue MANUAL, T15» de `current.md` trae los
  diez pasos con su comando; todo lo que nombran existe y sin secretos (`<host>`, `<usuario>`).
- Los tres no bloqueantes, resueltos; el delta no cambió firmas, SQL ni datos (330 passed).
- `init.sh` sobre `7eed62e`: verde, 9.645 passed / 266 skipped (6.024 s); cobertura 100 %.

## Pasada 1 (sobre `6efddfe`) · lo que se verificó

- **`bash harness/init.sh` en esta pasada:** **verde**, exit 0, «ENTORNO LISTO»: 9.645 passed, 266 skipped (5.817 s); cobertura `[OK]` 100 % (143/143); tamaño OK.
- **SQL ejecutado de verdad:** el `sandbox_f150.py` del implementer, vuelto a correr sobre un
  `postgres:16` desechable lanzado por mí con el SQL de HEAD: **66 OK, 0 fallos**. El oráculo es el
  dominio. Cubre `00` aplicado dos veces, `06`, `07` (con la guarda D6) y `08`. Contenedor borrado.
- **Azure, solo lectura** (`filas_solo_lectura`):
  - las 21 obras de VENTA tienen un `cenide` propio, ni 0 ni compartido, así que el hueco no
    cuenta dos veces una factura;
  - las 19.005 partidas VENTA casan con `raw.obrparpar.ide`, y 0 son de otra obra;
  - existen las columnas fuente (`obr.ivaide`, `obrctr.coestr`/`ivaide`, `obrparpar.ctride`,
    `stg.presupuesto`);
  - `raw.iva` y `raw.dvf` aún no existen en Azure. Es lo esperado: llegan en T15.
- **Sigrid** (`sigrid_tablas.md`): `dvf` con las 9 columnas de la lista blanca; ni `dvf` ni `iva` con `tiemod`.
- **El código frente a la spec**, leído línea a línea:
  - `coestr` se lee por líneas `\r?\n` y por CÓDIGO; `RET*` va aparte y no suma; `COEF_DESADJ` va
    en cascada; un código desconocido o un valor no numérico fallan cerrado. Python y SQL son
    gemelos, incluido un `\r` suelto;
  - fuente del coeficiente: CONTRATO > 9 > 11 > SIN; la guarda D6 salta antes del `TRUNCATE`;
  - el hueco es neto por obra, con `GREATEST(0, …)`, `MEDIA_OBRA` (1 si la obra no tiene ningún
    coeficiente) y el IVA y la retención por el peso de cada contrato;
  - H12 SIGRID sale de la ficha de la obra; un MANUAL lo pisa.
- **Catálogo:** `cargar_hipotesis_caja()` da **27 hipótesis y 0 errores**, con los pasos de §6,
  los perfiles H03/H08/H24/H25, H14 `MENSUAL`, H20 `FIN_MES_ALBARAN` y H26/H27 como R24; ninguna
  validada. Los textos de H10, H12, H13, H15 y H20 son los de §6.
- **Reglas de producción:**
  - sin secretos: el barrido del diff solo encuentra el `127.0.0.1` local;
  - ni `DROP` ni `GRANT` (solo `ON COMMIT DROP` de tablas temporales);
  - ni `_des_texto` ni `_versiones_cargadas` aparecen en el diff;
  - `objetos_pendientes.yaml` sigue vacío y es coherente: lo nuevo son dos tablas `raw` de la
    ingesta y dos funciones de `00`.
- **Diccionario:** v63; fichas de `raw.iva` y `raw.dvf`; columnas nuevas con `significado` y
  `nulo_significa`; `R-CAJA-HIPOTESIS` remite a la receta y `R-VENTA-COEFICIENTES` cubre las tres
  `devengo_*`.
- **`azure-apps` `044beef`:** `iva`, cabecera de `dvf`, 80 tablas, columnas, guarda D6, despliegue.
- **Tests de F-140:** solo recuentos (23→27, 78→80, `>= 2`/`>= 62`); los de F-150 fijan los exactos.

## Mutación (C4 bis)

- **Recálculo puro:** **329 líneas en 4 ficheros y 95 mutantes**, igual que el informe. La muestra
  (semilla `20260820`) contiene el superviviente (`:227`) y los dos timeouts (`:485`, `:498`), con
  el mismo texto original → mutado.
- **Campaña no reejecutada:** 15.325,8 s según el informe, por encima del umbral de 60 s.
- **RM4, sobre una copia (`git archive`, ya borrada):**
  - con `> 3` en `:227` falla `test_f150_r7_una_linea_de_solo_tres_campos_se_lee_como_el_sql`
    (1 failed / 40 passed), y sin el mutante pasan 41;
  - `:485` (`or valor`) y `:498` (`par[2]`) también mueren.
- **RM1:** medido en `e85a3d8`. Hasta HEAD no cambia nada de `etl_sigrid/`, así que el alcance es
  el mismo.
- **RM2:** base de 1.265 / 1.281 s y media de 766,3 s con 2 workers, es decir, 1.532 s reales por
  mutante, del orden de la base. `20 × 766,3` = 15.326, el tiempo total. Es coherente.
- **RM3:** ningún equivalente sale muerto. Lo comprobé en `:247` (`otros`) y `:468` (`1 <`): los
  matan casos que existen en los tests (`COEF_RECCC`, porcentajes 0,01 y 0,1).
- **RM5:** N/A, porque el rigor es `estandar`.
- **RM6:** no se quitó ninguna guarda.
- **Validez del informe:** sin la cabecera «CAMPAÑA NO VÁLIDA» y con 0 «Sin veredicto».

## Checkpoints

- **C1:** `[x]` `init.sh` con código 0 · `[x]` existen los ficheros base.
- **C2:** `[x]` una sola `in_progress` · `[x]` rama `feature/F-150-receta-caja` · `[x]`
  `current.md` con F-150 como sección activa (lo demás, como en F-140) · `history.md`: N/A, no es
  `done`.
- **C3:**
  - `[x]` hexagonal: dominio puro (`re`, `decimal`, `typing`), el SQL en `sql/tesoreria/NN_` y la
    ingesta en `application`;
  - `[x]` la primera línea es la ruta;
  - `[x]` sin `print`, TODO, secretos ni dependencias nuevas;
  - `[x]` semántica de Sigrid: `stg.presupuesto` con obra, ámbito 9/11 y `fase_num` = V (R10); lo
    real con `importe_mes` y tope en el cierre (la misma fuente que `real_origen_corte` de F-140).
- **C3 bis:** N/A, porque no toca `docs/referencia/`.
- **C4:** `[x]` trazabilidad (tabla de abajo) · `[x]` sin red ni BBDD · **`[ ]` MANUAL con su
  comando exacto en `current.md`** (pasada 1); `[x]` en la pasada 2 · `[x]` dobles: comprobación automática en `init.sh`.
- **C4 bis:** `[x]` rigor declarado · `[x]` fase RED con salida real (`impl_F-150.md` §5: R1-R5,
  R7, R9, R12, R14, R15, R17, R20-R23, R25, R32) · `[x]` cobertura `[OK]` 100 % (143/143) · `[x]` mutación
  verificada · `[x]` «Evidencias» con los cuatro números y los 2 workers.
- **C4 ter:** N/A, porque no existe `harness/rutas_sensibles.json` (solo el `.ejemplo`).
- **C5:** `[x]` T1-T14 y T16 `[x]` con su commit; T15 es el despliegue MANUAL tras la review,
  como en F-140 · `[x]` `git status` limpio · `[x]` `features.json` al día.

## Cobertura · requisito → test (`tests/test_f150_*.py`)

| Requisitos | Tests |
|---|---|
| R1, R24-R28 | `receta`/`perfil` r1 (12), r24 (3), r25 (9), r26 (3), r27 (3), r28 (4) |
| R2-R6, R15, R32 | `diccionario` r2, r3 (2), r4, r5, r6 (2), r15, r32 (2) |
| R7, R9, R18, R22 | `contrato` r7 (17), r18; `coeficiente` r9 (10); `hueco` r22 (11) |
| R8, R10-R14, R19-R21, R23 | `sql` r8 (9), r10-r13 (2-3 cada uno), r14 (7), r19, r20 (2), r21 (4), r23 (7) |
| R16, R17 · R29 · R30-R31 | `ingesta` r16 (5), r17 (6) · MANUAL hecho (§4, 15,60 en 15,50-15,75) · MANUAL T15, con comandos en `current.md` |

## Automejora (propuesta, no aplicada)

En `implementer.md` (y `arnes-base`): «MANUAL a `current.md` CON su comando exacto». Es el segundo rechazo por esto (F-140 y F-150).
