<!-- progress/review_F-067.md -->
Revisión completa (pasada 1): `git diff main...HEAD` sobre `b393c8b`; fuera, por ser del líder, `10021ba`, `1bfa8a8`, `b5b6ac3`, `d4bf384` y `7a5a8d9`

# F-067 · Review · foto diaria de estados, condiciones del contrato y código 2

**Veredicto: CHANGES_REQUESTED.** Solo hay que arreglar papeleo y un
comentario. El código, el SQL, los tests y las dos campañas los he verificado y
están bien, y las cifras de la spec las he reproducido en Azure.

**Rigor:** `critico`, declarado: RED, cobertura, mutación sin supervivientes, RM5, MANUAL.

## Lo que se ha verificado

- **La foto (`11`)**: lo ejecutable no tiene ni `DROP`, ni `TRUNCATE`, ni
  `DELETE` (test con `\b`, y M17 → 4 fallos). Las tablas se crean con `IF NOT
  EXISTS`, sin FK, así que ningún `DROP ... CASCADE` de `compras` se las lleva;
  `--full` solo trunca `raw` (`ingest_raw_step.py:272`). Los pasos 1-6 van en el
  orden del design §3. **Relanzar la misma noche no escribe nada**: `v_obs <=
  v_ult → RETURN` antes de cualquier `UPDATE` (test; M04 lo mata). El tramo se
  cierra por `ide`+`tip` con `IS DISTINCT FROM` y el desaparecido no se reabre.
  El índice único parcial impide dos tramos abiertos. El `INSERT` lleva
  `observado_antes = v_ult` y `es_linea_base = (v_ult IS NULL)`. Lo he comparado
  paso a paso con `aplicar_foto`, cambio de tipo incluido, y es igual.
- **La guarda del 98 % NO se ha debilitado.** `d698881` solo toca el DOMINIO, y
  lo que quita (`n_abiertos > 0 and`) es redundante: con 0 abiertos queda
  `len < 0`. Lo he comprobado por fuerza bruta (n 0-299, v 0-399): 0
  discrepancias entre el original, el mutante `>= 0` y la versión nueva. El SQL
  no cambia desde T4 (`de51611`, `e032831`), y un test fija su texto exacto,
  `IF v_abiertos > 0 AND v_actual < 0.98 * v_abiertos THEN RAISE EXCEPTION`,
  antes del primer `UPDATE`. M05, M06 y M07 mueren.
- **Delphi**: época `1899-12-30` y `v > 0`, la misma que `EPOCA_DELPHI` (test);
  M01, con la de SQL Server, muere. En Azure, `max(tiemod)` = 2026-10-05 15:44.
- **D2**: la vista saca la antigüedad de `h.desde` (Madrid), sin `tiemod` (test
  de veto). Las fichas dicen que `tiemod` NO es el cambio de estado.
- **Columnas al final** en `contratos` (5) y en las tres tablas de líneas (3).
  Ninguna existente se mueve (`test_f084_sql`, R12, R17). `necesidad_id` va
  detrás de `factor`. **Sello intacto**: `git diff main...HEAD --stat --
  sql/descompuestos/` solo devuelve `06_views.sql`.
- **En Azure, SOLO LECTURA** (psycopg directo, `transaction_read_only = on`,
  sesión en UTC). `raw.con._ingested_at` es `timestamp DEFAULT now()` y se carga
  entera cada noche (min y max a 2 min). 44/15: 185.754, con `ide` único. El
  SELECT de `contratos` con su lateral da 19.081 filas: 19.072 con forma de pago
  y 6.333 con retención (5 % en 6.277). `dcapro`: 1.162.871 / 357.349 /
  378.010, y todas casan con `dncpro`. `dnc`: 277, 271 de ellas las de su obra.
  `necesidad_id` va por `dncpro_pkey` (Index Scan). Coincide con la previsión de
  T19.
- Los tests ajustados de F-006/038/073/079/120 no pierden exigencia; ningún
  commit del implementer toca `features.json` (los cambios son del líder).

## Checkpoints

**C1** [x] `bash harness/init.sh` sobre `b393c8b`: **6.976 passed, 226
skipped** (56 min), `COBERTURA [OK] 100 %` (66/66). Su único `[KO]` fue el
TAMAÑO de ESTE informe, que escribía mientras corría (174 > 140); ya está
recortado, y `python -m harness.tamano --feature F-067`: dentro (review 140/140) · [x] los
ficheros del arnés existen.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-067-…` · [x]
`current.md` refleja el estado real · [x] `history.md`: no aplica todavía.
**C3** [x] hexagonal: el dominio solo usa la librería estándar y el SQL está en
`sql/compras/10_`/`11_` · [x] primera línea con la ruta · [x] sin `print`, sin
secretos y sin dependencias nuevas · [x] Sigrid: `tip` 44/15 y la pareja (tipo,
estado) de F-084. Ámbito, fase e importes: N/A, porque no toca `stg`, `mart` ni
importes.
**C3 bis** N/A: no toca `docs/referencia/`. **C4 ter** N/A: no hay
`rutas_sensibles.json`.
**C4** [x] R1-R29 con `test_f067_rN_*` en verde; R28 (puertas en la base) y R30
son MANUAL · [x] sin red ni BBDD · **[ ] las MANUAL no están en `current.md`
con su comando** (cambio 1) · [x] no hay dobles nuevos.
**C4 bis** [x] rigor declarado · [x] RED con traza real, y la T4 reproducida en
un worktree de `de51611` con el test de `e032831`: «7 failed, 1 passed», como el
informe · [x] cobertura `[OK]` · [x] alcance y mutantes recalculados · [x]
> 60 s: **la campaña del arnés NO se ha reejecutado** (15.340 s según el
informe); a cambio, recálculo más RM4 · [x] coste por mutante 306,8 × 4 =
1.227 s, coherente con la base de ~1.090 s · [x] sin «NO VÁLIDA» y «Sin
veredicto» 0 · [x] RM1 · [x] RM2 · [x] RM5 · [x] RM6 · [x] tabla SQL con línea,
texto exacto y fallos, reproducida · [x] los supervivientes y el timeout tienen
su análisis · [x] «Evidencias» con los workers · [x] ningún N/A sin motivo.
**C5** [x] T1-T15 `[x]`, con un commit `F-067 Tn` cada una (T16-T23 son MANUAL)
· [x] árbol limpio (worktrees borrados) · [x] `features.json` real.

## Mutación (verificación independiente)

- **Recálculo** (`harness.alcance` + `generar_mutantes`): sobre `d088327`, 235
  líneas (33 + 202) y 50 mutantes, como el informe. Los 4 supervivientes y el
  timeout existen con el mismo operador y el mismo texto (l. 121, 125, 173 y
  176). Sobre HEAD: 239 líneas y 45 mutantes.
- **RM1**: lo medido (`d088327`) no es HEAD; después cambió el dominio
  (`d698881`). **RM4**: he reejecutado `progress/mutacion_dominio_F-067.py` en
  una copia de HEAD: **45/45 muertos, base 276 passed**, como declara el informe.
  El step da 0 mutantes en las dos versiones.
- **RM3**: ningún equivalente sale muerto. **RM5**: el equivalente `>= 0` lo he
  demostrado arriba por fuerza bruta, y además ya no existe. **RM6**: lo que se
  quitó es una condición redundante, no una guarda contra `None`. `n_abiertos`
  es una suma de unos (l. 120), así que nunca es negativo, y el SQL mantiene
  `v_abiertos > 0` sobre un `count(*)`.
- **Campaña SQL**: `mutacion_sql_F-067.py` reejecutado entero en un worktree de
  HEAD: **40/40 muertos, con el nº de fallos idéntico fila a fila** (M05 → 1,
  M17 → 4, M21 → 1…). Base 1.199 passed: las 1.197 del informe más los 2 tests
  de `d698881`.

## Cobertura requisito → test (`tests/test_f067_*.py`)

R1 `r1_*` (5) · R2 (8) · R3 · R4 (4) · R5 (7) · R6 (7) · R7 (4) · R8 (9) · R9
(5) · R10 (4) · R11 (2) · R12 (3) · R13 (3) · R14 (9) · R15-R16 · R17-R18 (5) ·
R19 (5) · R20-R21 (3) · R22-R25 (7) · R26-R27 (4) · R28 (2) más T18 · R29 por
lectura (ARCHITECTURE y `azure-apps` en `5a66c79`) · R30 MANUAL T21.

## Cambios requeridos

1. **`progress/current.md` l. 103-106**: copiar las MANUAL de `impl_F-067.md`
   §6 **en orden, con su comando exacto y lo que debe salir**, como F-113 y
   F-038. Ahora solo hay un resumen y un puntero (C4; mismo motivo de rechazo
   que F-123 en su pasada 1). El primer punto, la **decisión sobre
   `reset-compras`**, que `impl` §6 pone como precondición de T16.
2. **`sql/compras/11_historial_estados.sql:86-88`**: «La excepción revierte el
   build entero de la noche» es **falso**. Cada sub-paso es su propia
   transacción (`postgres_client.py:1454` y el bucle de
   `build_compras_step.py`), así que `00`-`10` ya están confirmados y solo se
   revierte la foto. Hay que corregirlo: «revierte este fichero: no se toma la
   foto; el resto de `compras` ya se ha reconstruido». Es lo que leerá quien
   opere esa noche. Ningún test fija ese comentario.

## Para el líder y el humano (no bloquea)

- **`reset-compras` borra la historia** (`DROP SCHEMA compras CASCADE`,
  `main.py:4933`), y lo **recomiendan** `README_COMPRAS_C1_C2.md:53` y
  `LEEME_INTEGRACION.md:21`. El implementer hizo bien en no tocarlo (fuera del
  design). Hay que decidirlo ANTES de desplegar: que el comando excluya las dos
  tablas o se niegue, y corregir esos dos documentos.
- **Riesgo de la spec (R5)**: un documento que falta una noche, por una ingesta
  a medias que pasa la guarda (≤ 2 %, unos 3.700), se cierra como DESAPARECIDO y
  al reaparecer pierde `antiguedad_es_minima`: su antigüedad vuelve a contar
  desde cero. Con `--full` es improbable, pero no tiene vuelta atrás.
- T23 (`NOT h.es_linea_base`) cuenta también las altas, no solo los cambios.

## Automejora (propuesta, no aplicada)

En `reviewer.md` o C3: «tabla PERSISTENTE en un esquema que se reconstruye →
buscar en todo el repo (CLI, scripts, `infra/`, README) `DROP SCHEMA <esquema>`
o un reset». El veto de R8 solo mira quién NOMBRA las tablas.
