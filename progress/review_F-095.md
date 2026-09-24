<!-- progress/review_F-095.md -->
Revisión completa (pasada 1) · `main`(249b683)..`215addc` · 2026-09-25

# F-095 · Review · CHANGES_REQUESTED (RECHAZADO)

**Veredicto: RECHAZADO.** El SQL cumple la spec y H1-H7, `init.sh` está en
verde y las nueve desviaciones están justificadas. **Lo que falla es la campaña
de mutación de rigor `critico`.** El implementer eligió a mano 22 mutantes, y
los 22 caen sobre fragmentos que los tests ya fijan literalmente. Yo lancé una
muestra independiente de 16 mutantes sobre el mismo SQL y **sobreviven 11**,
entre ellos el núcleo del cuadre (R14): `saldo_contable`, `viva_efectos` y
`diferencia` pueden calcular otra cosa con la suite en verde.

**Rigor:** `critico`, declarado. Exige fase RED, cobertura ≥ 80 %, campaña
entera con 0 supervivientes y verificaciones MANUAL con su comando.

## Qué se ejecutó (resultados reales)

- `bash harness/init.sh`: **exit 0**. `5417 passed, 203 skipped` en 2.269 s.
  Cobertura `[OK] 94.7% (968/1022)`. Tamaño `[OK]`.
- `harness.alcance` (`--base main`): 38 líneas de Python, 0 mutantes. La
  **prueba de control** (el fichero entero, sin la exclusión de alcance) da 12:
  el 0 es legítimo. La herramienta no muta SQL.
- **Campaña manual del implementer, reproducida entera** sobre una copia
  (`git archive HEAD`) en el scratchpad, con `test_f095` y `test_f047_steps`,
  en serie. Base: 87 passed. Tiempo: 440 s para 38 mutantes. **Mueren los 22**,
  con los mismos fallos salvo el #6: sale 1 error de colección, no 3. Además el
  #6 es mortinato: deja un `)` suelto y lo mata un `SyntaxError`, no un test.
- Árbol limpio (`git status`). Nada escrito en Sigrid ni en Postgres.

## Supervivientes del reviewer (RM4: copia en el scratchpad; script `mut_review.py`)

| # | fichero:línea | original → mutado |
|---|---|---|
| S1 | `06_views_contables.sql:46` | `SUM(s.saldo)              AS saldo_contable` → `SUM(s.altas) ...` |
| S2 | `06:82` | `(x.saldo_contable - x.viva_efectos)` → `(x.viva_efectos - x.saldo_contable)` |
| S3 | `06:53` | `-SUM(a.importe) AS prescrito` → `SUM(a.importe) AS prescrito` |
| S4 | `06:62` | `SUM(importe)         AS viva_efectos` → `COUNT(*)             AS viva_efectos` |
| S5 | `06:124` | `(f.fecha_vencimiento - CURRENT_DATE)` → `(CURRENT_DATE - f.fecha_vencimiento)` |
| S6 | `06:113` | `    s.saldo,` → `    s.altas AS saldo,` |
| S7 | `06:47` | `SUM(s.saldo_anterior_2016) AS ...` → `SUM(s.saldo_inicial) AS ...` |
| S8 | `03_apuntes_contables.sql:128` | `WHERE r.asiide <> 0 AND r.conide <> 0` → `WHERE r.asiide <> 0` |
| S9 | `03:213` | `LEFT JOIN raw.con ob ON ob.ide = r.obra_id` → `... = r.centro_coste_id` |
| S10 | `03:208` | `ob.emp::text \|\| '-' \|\| ob.cod` → `ob.cod \|\| '-' \|\| ob.emp::text` |
| S11 | `04_saldo_contable.sql:48` | `COUNT(*) FILTER (WHERE a.clase IN (...)) AS num_apuntes` → `COUNT(*) AS num_apuntes` |

Los 11 dan 0 fallos. Murieron 5: el año 2016→2015, MAX→MIN de `fecinigar` y
de `plaret`, la `clave_obra` invertida en `05` y `ejercicio - 1` → `+ 1`.
**Ninguno de los 11 es equivalente**: todos cambian una cifra o una clave que
se publica. S9 y S10 rompen `R-CODIGO-POR-EMPRESA` en `apuntes_contables`:
hoy la clave solo la fija un test en `05`.

## Checkpoints

- **C1** [x] · **C2** [x] (observación para el líder: `current.md` arrastra
  2.064 líneas de sesiones anteriores, deuda previa) · **C3** [x] hexagonal,
  rutas en la primera línea, sin prints ni secretos, semántica Sigrid.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x] R1-R31 trazables y en verde · [x] offline · [x] MANUAL M1-M6 con
  comando y resultado esperado · [x] `_PgFalso` casa con `postgres_client.py:1061,1426`.
- **C4 bis**
  - [x] `rigor` declarado · [x] RED con traza real (64 failed) · [x] cobertura OK.
  - [ ] **Mutación**: no hay `progress/mutacion_F-095.md`, y la campaña manual
    no es la entera: es una selección sobre texto ya fijado, y quedan 11
    supervivientes (S1-S11).
  - [x] Reejecuté los 22 · [x] 8-17 s por mutante con base de 12 s · [x] base verde.
  - [ ] **RM1**: no declara el SHA. El alcance no cambió después de `83ada78`
    (lo comprobé): es un defecto de papeleo.
  - [ ] **RM2**: sin tiempo total ni línea base.
  - N/A RM5: nadie declara ningún mutante equivalente.
  - [x] RM6: el #11 se mató endureciendo el test, sin quitar código.
  - [ ] **Tabla manual**: le falta la línea en todas las filas, y el #6 es
    mortinato con fallos que no reproduzco.
  - [ ] **Cero supervivientes en `critico`**: S1-S11 no tienen ni test ni justificación.
  - [x] «Evidencias» completa, con «1 worker, en serie».
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] T0-T22 y T26 `[x]`, con commit `F-095 Tn:`. T23-T25 son MANUAL
  del humano, y así debe ser · [x] sin temporales · [x] `in_progress` coherente.

## Los ocho puntos del líder

1. Desviaciones correctas. El anti-join equivale al `NOT EXISTS` porque
   `cierres_cuenta` lleva DISTINCT; R5 medido: 0 violaciones, 72 apuntes y
   642.775,50 €, todos de 2008. FACTURA estricta es más conservadora (su cifra,
   en M4). El cuadre usa `ABS(...) >= 1` e incluye los saldos negativos: es lo
   seguro. Censo 71: los pines de F-107 pasan a `>=` con su motivo.
2. `01` y `02` fuera del diff (R25). El cuadre lee `estado = 'VIVA'`, sin
   `fecrea`, `fecbaj` ni `est`.
3. H1 y H2 cumplidos: `MAX(obrctr.fecinigar)` → `obr.garfecini` → último día
   del mes siguiente al último `anio_mes` con movimiento (DATE); plazo
   `plaret` → `plagar` → 12 en una constante; 46 / 116 / 17 obras
   (24,3 % + 72,7 %), 132.544,84 € sin fecha.
4. `R-CODIGO-POR-EMPRESA`: fórmula de `maestro/00_setup.sql:84` y ámbito
   ampliado. Hueco de test en `03` (S9, S10).
5. Campaña: ver C4 bis.
6. Nombres de persona: barrido de las líneas añadidas (mayúsculas y «Nombre
   Apellido»); solo sale FERMALUX, que es una empresa.
7. `azure-apps` `a698815`, en `master`: recoge `rac`, los seis objetos, la
   nueva fuente del saldo y la dependencia del cierre.
8. `rac` con `where: "asiide <> 0"` (la única filtrada; `check-raw-recuentos`
   aplica el filtro) y el orden M1-M6, escritos.

## Cobertura requisito → test (`tests/test_f095_retenciones_contables.py`)

| Requisitos | Tests |
|---|---|
| R1-R6 | `r1_*`, `r2_*`, `r3_*`, `r4_*`, `r5_*`, `r6_*` |
| R7-R10 | `r7_*` (3), `r8_*` (2), `r9_*` (2), `r10_*` |
| R11-R16 | `r11_*` (2), `r12_*`, `r13_*`, `r14_*`, `r15_*`, `r15_y_r16_*` (las cifras de FERMALUX son MANUAL) |
| R17-R26 | `r17_*` (4), `r18_*`, `r19_*` (2), `r20_*`, `r21_*` (2), `r22_*` (2), `r23_*` (2), `r24_*`, `r25_*` (2), `r26_*` |
| R27-R31 | `r27_*` (6), `r28_*` (4), `r29_*`, R30 (toda la suite es offline), `r31_*` |

Todos tienen test, pero **en R11, R14 y R24 el test comprueba el alias y no la
fórmula** (S1-S7, S11).

## Cambios requeridos

1. **Matar S1-S11** con tests que fijen la expresión, no solo el alias:
   - `06`: líneas 46-47, 53-55 (con su `WHERE`), 62, 82, 113 y 124;
   - `03`: línea 128, y de la 206 a la 213 (`empresa_id`, `codigo_obra`,
     `clave_obra` y el `JOIN` por `r.obra_id`);
   - `04`: línea 48.
2. **Repetir la campaña manual de forma sistemática.** Al menos un mutante por
   cada expresión del SELECT, cada `WHERE`/`FILTER`/`HAVING` y cada `JOIN` de
   los seis `CREATE` de `03`-`06`, más S1-S11. Va en `progress/mutacion_F-095.md`,
   que es lo que pide la verificación de T22, junto con la prueba de control del
   0 automático.
3. **Completar la tabla**: `fichero:línea` en cada fila, «SHA de HEAD medido»
   completo, tiempo total, línea base y workers (RM1 y RM2).
4. **Sustituir el #6** por un mutante que compile (quitar la línea entera
   `_SubStep(name="views_contables", ...),`) y anotar su número real de fallos.
5. **Cero supervivientes**, o la justificación de cada uno para que la acepte el humano.

## Automejora (propuesta, no aplicada)

- C4 bis: una campaña MANUAL sobre SQL con tests de texto genera sus mutantes
  de forma **sistemática** (uno por expresión, filtro o join de cada `CREATE`),
  no elegidos por quien escribió los tests; el reviewer añade su muestra.
- RM3: con tests de texto un equivalente sí puede morir (el #13, `NULLS NOT
  DISTINCT`, redundante con el `GROUP BY`). No invalida la campaña: se declara.
