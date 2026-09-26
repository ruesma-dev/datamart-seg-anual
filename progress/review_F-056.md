<!-- progress/review_F-056.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` (merge-base `fe061b0`) hasta HEAD `a0c6919`

# F-056 · Review del reviewer

**Veredicto: CHANGES_REQUESTED.** El fondo está bien y verificado contra la base; fallan
dos cosas de papel, baratas (abajo). Ningún cambio toca código, SQL ni el alcance de la
mutación: la pasada 2 será incremental y sin campañas.

**Nivel de rigor:** `critico` (declarado). Exige fase RED, cobertura >= 80 %, mutación con
0 supervivientes y las verificaciones `MANUAL (humano)` con su comando exacto.

## Lo verificado por mí

- `bash harness/init.sh`: exit 0, **5659 passed, 207 skipped**, `PUERTA COBERTURA [OK]
  100.0 % de 67 líneas`, `PUERTA TAMAÑO [OK]`, `ENTORNO LISTO`.
- **Base, SOLO LECTURA** (`SET TRANSACTION READ ONLY`, script en mi scratchpad):
  - **(2) Clases = F-095**: R18 recalculada sobre `retenciones.apuntes_contables` (hoy
    **49.528**; eran 49.505): **0 diferencias**. ALTA 26.858 y BAJA 4.858 → NORMAL;
    APERTURA 8.870, CIERRE 8.870 y SALDO_INICIAL 72 idénticos; ningún REGULARIZACION.
  - **(3) C1** `1-4308000197` desde `raw`: **641** apuntes, 2009-01-31 a 2026-09-21, saldo
    **1.189.275,13**, apertura 2026 **727.529,01** (= saldo a fin de 2025), sin quitar
    aperturas **7.742.538,38**. **C2** `1-434` 2026 sin CIERRE: **5.345.557,80**.
  - Supuestos del SQL: `tip=16` solo de 1-4 dígitos y `tip=17` solo de 10; 0 `cua` sin
    `con`; 0 apuntes con cuenta fuera de `cua` o sin fecha; 0 `(emp, cod)` repetidos en
    `tip=16`; `maestro.centros_coste` 804/804 ids únicos; existen todas las columnas que
    lee el SQL; `EXPLAIN` del SELECT real de `plan_cuentas` y `mayor` planifica sin error.
- **(4) Árbol**: padre y ancestros unen siempre por empresa + prefijo; únicos
  `(empresa_id, codigo_cuenta)` y `clave_cuenta`; `R-CODIGO-POR-EMPRESA` los alcanza.
- **(1) Propagación**: step (`depends_on=["ingest_raw"]`, nadie depende de él), orden
  personal → contabilidad → cierre, comando suelto (huérfanas sí, publicar no),
  `ESQUEMAS_DEL_DATAMART`, consumo por defecto, `.env.example`, `02_roles.sql` (tres
  listas), runbook, `R-FRESCURA`, `check-unicidad` (dos alternativas; `test_f108` cuenta
  por clave, no se debilita), `check-relaciones` (muestreo: el `cuenta_id = 0` de saldos
  no lo tumba). Barrido fuera de `tests/`: ninguna lista a mano de esquemas o `build_*`
  sin `contabilidad`. La ingesta hace `TRUNCATE` (la vista puente no cae); la guarda R14
  va en la transacción del `CREATE`; el Job no fija `PG_CONSUMPTION_SCHEMAS`. **Tiempo
  del build NO medido** (R35 es MANUAL, del líder): estimado 4-6 min y ~1,2 GB en B2s.
- **(5)** Fichas `raw.cua/asi/apu/apa` corregidas; no queda «dos saltos» ni «nivel 0».
- **(7)** `version: 36`; `main` y el MCP publicado están en 35.
- **(8)** Aviso de `mcp-bbdd` en `impl_F-056.md` §7 y `azure-apps`; contrastado con
  `mcp-bbdd/config/config.yaml`: `seguridad.esquemas_permitidos`, `personal` tras
  `retenciones`. **(10)** `azure-apps` `2748264` + `90d84af`, limpio, sin push.
- **(9) Nombres de persona: FALLA** → cambio 2.

**Desviaciones, aceptadas las tres**: PK de saldos con `empresa_id` (el design era
contradictorio y su PK tumbaba el build, medido); asiento por `LEFT JOIN` (R13); guarda
en la misma transacción (mejor que el design).

## Mutación (C4 bis)

- **Herramienta**: `harness.alcance` (base `main`) + `generar_mutantes`: **4 ficheros,
  215 líneas, 12 mutantes**, coincide. Tiempo total 1961,6 s > 60 s → **campaña no
  reejecutada (≈33 min según el informe)**: recálculo puro + RM. Reproduje en una copia
  3 de 12 (`exc_info=False`, `total_rows -= rows`, `and`→`or`): MUERTOS por el test citado.
- **RM1**: SHA `7f71b1e` / `3c67936`+`5150061`; después solo `progress/`, `tasks.md` y
  tests más estrictos. **RM2**: base ~397 s, media 163,5 × 2 workers = 327 s por
  mutante, coherente; sin «NO VÁLIDA» ni base rota. **RM3**: ningún equivalente MUERTO
  (P20 se reapuntó). **RM5**: sin equivalentes vivos. **RM6**: N/A, no se quitó defensa.
- **Sistemática (233 filas)** con fichero:línea, original→mutado y nº de fallos: es
  sistemática de verdad (expresión, JOIN, ON, WHERE, FILTER, DISTINCT, DDL, guarda y 59
  semánticos). **Reproducidas al pie de la letra** #47 (`pad.emp = n.empresa_id`→`TRUE`,
  2 fallos) y #178 S4 (`- 1` fuera, 3 fallos): idénticas. **Muestra propia de 10 mutantes
  que NO están en su tabla** (sin `cla=-1`, sin `cla=3`, regularización sin `cla`, sin
  `posicion` en la ventana, movimiento + REGULARIZACION, `fecha_asiento` del apunte,
  asiento por `JOIN`, `g1` sin empresa, anti-join invertido, `importe_saldo` sin
  SALDO_INICIAL): **10/10 MUERTOS**, cada uno por su test semántico además del contrato.

## Checkpoints

- C1: [x] init.sh exit 0 · [x] ficheros del arnés.
- C2: [x] una `in_progress` · [x] rama correcta · [x] `current.md`: F-056 solo añade su
  sección (criterio de F-112) · [x] `history.md` N/A: F-056 aún no está `done`.
- C3: [x] hexagonal (`sql/contabilidad/NN_*.sql`, step en application) · [x] ruta en
  primera línea · [x] sin prints, secretos ni dependencias · [x] semántica Sigrid:
  `amb/fas`, `importe_origen` y `obrfasamb` N/A (no se leen); CIERRE/APERTURA resuelto
  como regla dura.
- C3 bis: N/A — no toca `docs/referencia/`. C4 ter: N/A — sin `rutas_sensibles.json`.
- C4: [x] R1-R36 trazables y en verde (tabla) · [x] offline · **[ ] MANUAL en
  `current.md` con su comando exacto** (cambio 1) · [x] dobles con la firma real de
  `PostgresClient` (`execute_sql_file(path)`, `count_rows(schema, table)`).
- C4 bis: [x] rigor · [x] RED con salida real (`60 failed, 2 passed` + trazas) · [x]
  cobertura 100 % · [x] totales verificados · [x] muertos comprobados · [x] coste por
  mutante 327 s · [x] válida · [x] RM1 · [x] RM2 · [x] RM5 · [x] RM6 N/A · [x] tabla
  manual reproducible · [x] 0 supervivientes · [x] «Evidencias» con workers · [x] N/A
  todos justificados.
- C5: [x] T0-T21 y T25 `[x]`, T22-T24 MANUAL tras el APROBADO; T3-T5 y T6-T8 en un
  commit declarado, T18 en `azure-apps`, T19-T20 son informe y puerta: aceptado · [x]
  árbol limpio · [x] `features.json` coherente.

## Cobertura requisito → test (`tests/test_f056_contabilidad.py`, 66 en verde)

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1-R2 | r1_* (3), r2_* (2) | R17-R20 | r17_*, r18_* (2), r19_*, r20_* |
| R3-R5 | r3_* (8), r4_* (2), r5_* (2) | R21-R24 | r21_*, r22_*, r23_*, r24_* |
| R6-R10 | r6_*, r7_*, r8_*, r9_*, r10_* | R25-R26 | r25_*, r26_* |
| R11-R14 | r11_*, r12_*, r13_* (2), r14_* | R27-R32 | r27_* (4), r28_*, r29_*, r30_*, r31_* (3), r32_* |
| R15-R16 | r15_*, r16_* | R33-R36 | R33-R35 MANUAL (C1/C2 remedidos por mí); r36_* |

## Cambios requeridos

1. **`progress/current.md`, sección F-056, línea «T22-T24 · MANUAL»**: poner ahí cada
   verificación MANUAL con su **comando exacto y resultado esperado** (los siete puntos
   de `progress/impl_F-056.md` líneas 117-139: build + `timings` + tamaños, C1, C2, C3,
   C4 con `COALESCE`, `check-*`/`apply-grants`/`publicar-diccionario`, y `mcp-bbdd`). Un
   puntero al informe no cumple C4.
2. **Nombre de persona** (criterio 9 del líder; precedente F-101: commit nuevo, sin
   reescribir historia). Cambiar «Juan Romero»/«Juan» por una referencia sin nombre
   («la captura de Sigrid del 03-09») en `specs/F-056-mayor-plan-contable/requirements.md:135`,
   `specs/F-056-mayor-plan-contable/design.md:50` y `:155`, y `progress/spec_F-056.md:59`.
   Vienen de la spec (ya en `main`); el diff del implementer no añade ninguno.

**No bloqueante:** `docs/ARCHITECTURE.md` (coste de `run-all`) dice «~2,5 min» y «~1 GB»
frente a 126 s y ~1,2 GB del informe; `test_f057_r25_..._trae_los_diez_esquemas`
conserva «diez» en el nombre.

## Automejora (propuesta, no aplicada)

Añadir a C3 un punto «sin nombres de persona del personal en specs ni `progress/`»: hoy
solo lo sostienen el precedente F-101 y la petición del líder, y el nombre entró en
`main` con la spec aprobada sin que ninguna puerta lo viera.
