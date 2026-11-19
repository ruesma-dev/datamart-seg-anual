Revisión completa (pasada 1) · base `main` (d8566ac) · HEAD `9879f3f`

# F-104 · Review principal (reviewer, 2026-11-19)

- **Veredicto: APPROVED** (con cuatro observaciones que no bloquean, abajo).
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED, cobertura
  (o su N/A impreso) y la sección «Evidencias»; la mutación es INFORMATIVA (T10, campaña tras este
  APPROVED) y la capa e2e, N/A (sin `harness/servicios.json`). Sin RM1-RM7 ni supervivientes.
- **Alcance revisado:** los commits de F-104 de `6912ae7` a `4fd894b` más `7ae1e00` (T1) y el de
  estado `9879f3f`; fuera de revisión `41b8841`/`a1a34c2`/`bca5c22` (salvo la línea del test de R4
  que entró en `bca5c22`, declarada en el informe). En `azure-apps`, `4621627`.

## Puerta y tests (qué ejecuté)

- **`init.sh` completo: NO repetido**, por instrucción del líder (2 h 42 min). Me apoyo en la puerta
  del implementer sobre `7e7376f` (EXIT 0, 13.620 passed) y en que el delta `7e7376f..9879f3f` es solo
  papeleo: `BACKLOG.md`, `features.json` (`in_progress` -> `in_review`), `tasks.md` (T12 `[x]`) y el
  informe. Sin `servicios.json`, `ARNES_SIN_CACHE=1` no cambia nada. No veo motivo para pedir la
  puerta completa: lo que cambia después de ella no es código.
- **Tests de F-104, ejecutados por mí:** `test_f104_retenciones_cliente.py` +
  `test_f104_ventas_retencion.py` **46 passed**; `test_f104_sandbox.py` contra un PostgreSQL 16
  desechable propio (initdb en mi scratchpad, puerto local) **12 passed**.
- **Batería de lo afectado** (F-104, F-040 con su sandbox, F-047, F-094, F-095, F-110, F-128, F-006,
  F-079, F-147, F-003, F-141, F-144, F-102, backlog, estados, documentos del arnés y base de la
  puerta), con la F-040 sandbox también contra mi PostgreSQL desechable: **6.669 passed, 357
  skipped, 0 failed, EXIT 0 (23 min 11 s)**.
- Árbol limpio tras mis pruebas: solo `?? progress/mutacion_F-164.json` (ajeno, sin tocar).

## Checkpoints

- **C1** [x] puerta del implementer en verde sobre `7e7376f` + delta de papeleo (ver arriba); ficheros
  base presentes.
- **C2** [x] una sola activa (F-104 `in_review`); prioridad 2, la primera abierta; rama
  `feature/F-104-retenciones-cliente`. `current.md`: F-104 solo añade sus secciones arriba; las 6.113
  líneas acumuladas son deuda previa, no de esta feature. [x] `history.md`: F-104 no está `done`.
- **C3** [x] SQL en su capa (`retenciones/08_`, `ventas/06b_`), steps en `application`, sin dominio
  nuevo. [x] Ruta en la primera línea de los 2 SQL y los 3 tests nuevos. [x] Sin `print`, sin TODO,
  sin dependencias nuevas; barrido del diff sin secretos, oids, GUID ni rutas de scratchpad (solo el
  marcador `<scratchpad del implementer>` y un DSN local sin contraseña en el informe). [x] Semántica
  Sigrid: estado con la precedencia de F-094 y la ficha `raw.con` del efecto; saldo `deb - hab` con la
  clase de `03_apuntes_contables.sql` replicada línea a línea (lo comparé); `categoria` idéntica a
  `v_cuadre_proveedor`. Ámbito/fase/`importe_mes`/`obrfasamb`: N/A, no se tocan.
- **C3 bis** N/A: no entra ningún documento de fuera.
- **C3 ter** [x] las decisiones del humano (D1-D12) constan con fecha y cita en `design.md` §9 y en
  `features.json`; lo no verificable (R20-R22, R37) queda MANUAL.
- **C3 quater** [x] `4621627` toca solo `datamart_seg_anual.md` (31+/2-), commit aparte, SHA en el
  informe; sin push (`git status` limpio, no hice pull ni push). Coincide con la «Frontera» (§8):
  seis objetos nuevos, dos columnas, la cifra de CLIENTE que baja y la frontera de F-040 cumplida.
  Sin datos personales (solo nombres de empresa).
- **C4** [x] cada R tiene test (tabla abajo) y pasan. [x] Los estáticos no tocan red ni base; el
  sandbox solo con `F104_SANDBOX_DSN` y en una base nueva que borra. [x] MANUAL (T11) con comandos
  exactos en `current.md`. [x] Dobles: F-104 no añade ninguno.
- **C4 bis** [x] `rigor` declarado. [x] Fase RED con salida real (43 failed, 3 passed, 12 errors, y
  los mensajes). [x] `PUERTA COBERTURA: N/A` con su motivo impreso (lo Python cambiado son docstrings
  y la tupla `SUB_PASOS`). Mutación: N/A por nivel (informativa; la campaña de T10 va después).
  [x] «Evidencias» con los cuatro números y la fila «Capa e2e». Capa e2e: N/A, sin `servicios.json`.
  [x] `rigor.local.json` no se toca.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1-T9 y T12 `[x]` con su commit (T2-T3 juntos, mismo fichero, justificado); T10 queda
  para la campaña y T11 es MANUAL, como prevé la spec. [x] Sin temporales. [x] `features.json` al día.

## Comprobaciones de fondo que pidió el líder

- **Perfiles:** ningún CIF en las seis tablas nuevas; `entidad_cif` de CLIENTE sigue `NULL::VARCHAR(24)`
  (D9). Solo `nombre_cliente` (público por `R-VENTAS-RESTRINGIDA`) y `nombre_cuenta` del plan. La
  guarda `07_guardas.sql` mira prefijos de columna de todo `ventas`: las columnas nuevas no casan con
  ninguno. `infra/sql/02_roles.sql` sin tocar. El diccionario y `azure-apps` no traen nada personal.
- **R-VENTAS-TRES-CIFRAS:** no se suman certificado, facturado y cobrado. `diferencia` (retención
  menos efectos emitidos) es una resta declarada, con su nombre y su ficha.
- **Frontera F-094/F-040:** en `retenciones/` solo cambian `01` y `08`, nada en `tesoreria/`; en
  `ventas/`, solo `06b` es nuevo (`ventas/00`-`07` iguales). `TOCADOS_DESPUES` admite exactamente los
  dos de F-104. La rama PROVEEDOR solo gana las dos columnas finales (sandbox R9). Las `v_pbi_*` no
  cambian y siguen filtrando `estado = 'VIVA'`.
- **Diccionario v80** (= `main` 79 + 1): ficha para los seis objetos nuevos y para `origen_retencion`
  y `cuenta_id`; `test_f040_r31` (22 objetos de `ventas` = 22 fichas) y R16/R36 lo comprueban.
  El tope de contexto de F-147 sube de 37.356 a 37.914 con su motivo escrito, como F-161.

## Cobertura requisito -> test

| R | Test (`tests/`) |
|---|---|
| R1, R2 | `test_f104_r1_*`, `test_f104_r2_*`; sandbox `r1_r6_r7_estado_origen_y_cuenta` |
| R3 | `test_f104_r3_la_cabecera_explica_el_agr_con_el_caso_medido` |
| R4, R5 | `test_f104_r4_*` (x2), `test_f104_r5_*`; sandbox `r4_*`, `r5_*` (x2) |
| R6-R8, R10 | `test_f104_r6_*`, `test_f104_r7_r8_*`, `test_f104_r10_*`; sandbox `r1_r6_r7_*` |
| R9 | sandbox `r9_proveedor_intacto` + MANUAL (T11) |
| R11-R13 | `test_f104_r11_*` (x2), `r12_*`, `r13_*`; sandbox `r11_*`, `r12_*` |
| R14, R15, R24 | `test_f104_r14_*` (x2), `r15_*`, `r24_*`, `test_f040_frontera.py`; sandbox `r15_*` |
| R16-R18 | `test_f104_r16_*` (x3), `r17_*`, `r18_*` |
| R19 | revisión del reviewer (C3 quater) |
| R23 | `test_f104_r23_entidad_cif_de_cliente_sigue_null` |
| R25, R26, R36 | `test_f104_r25_*`, `test_f104_r26_*`, `test_f104_r36_*`, `test_f040_diccionario.py` |
| R27-R30 | `test_f104_r27_*` (x2), `r28_*`, `r29_*` (x2), `r30_*` (x2); sandbox `r27_r28_r29_*` |
| R31, R32 | `test_f104_r31_*` (x2), `r32_*`; sandbox `r31_*`, `r32_*` |
| R33, R34 | `test_f104_r33_*`, `r34_*` (x3), `test_f040_pipeline.py`; sandbox `r33_*` |
| R35 | `test_f104_r35_ninguna_columna_personal` + MANUAL (permisos, T11) |
| R20-R22, R37 | MANUAL (humano), comandos en `current.md` (T11) |

## Observaciones (no bloquean; para el líder y el humano)

1. **Una palabra perdida en el diccionario** (`config/diccionario/retenciones.yaml:2149`, relación
   `cuentas_cliente.cliente_id`): «agregar por  antes de unir» (falta, casi seguro, `` `cliente_id` ``:
   huele a un acento grave comido por el shell). Va publicado al MCP: conviene arreglarlo antes del
   merge; con los tests del diccionario basta, no pide la puerta entera.
2. **`build-ventas` en `main.py:5538-5551`** no nombra `06b_retencion_cliente.sql` ni que ahora
   necesita `build-retenciones` de F-104 antes (la guarda R33 lo tumba si no). Solo el `--help`; el
   orden de T11 en `current.md` es correcto.
3. **La guarda de `ventas` puede no correr una noche.** Cada SQL es su transacción: si
   `build_retenciones` falla DESPUÉS de `01` (que tira `v_cuadre_cliente` en cascada), `06b` cae por
   R33 y `07_guardas.sql` (la de nada personal) no se ejecuta esa noche. El paso queda FAILED igual y
   `R-FRESCURA` avisa, y es el orden que pide la spec (R33/R34), así que no es un defecto de la
   implementación. Pero si el humano lo quiere evitar, alternativa: que `06b` no tumbe el paso y deje
   las tablas de la noche anterior, o adelantar la guarda. Para decidir, no para este ciclo.
4. **Facturas anuladas:** `retencion_factura` toma todo `ventas.facturas`, incluidas las `anulada`
   (como dice R27). En T11 merece mirar `SELECT f.anulada, r.motivo, COUNT(*), SUM(r.retencion) FROM
   ventas.retencion_factura r JOIN ventas.facturas f USING (factura_id) GROUP BY 1, 2`: si las
   anuladas pesan en SIN_EFECTO sin su rectificativa, `diferencia_sin_explicar` las arrastra.
   Además, `design.md` §8 dice que `ventas` no está en la lista blanca del MCP; desde el 2026-11-18 sí
   lo está (`current.md`): texto de spec envejecido, sin efecto en el código.

## Automejora (propuesta, no aplicada)

- `reviewer.md`, protocolo punto 1: cuando la suite pasa de ~2 h, dejar escrito que el reviewer puede
  apoyarse en la puerta del implementer si el delta posterior es solo papeleo (lista cerrada:
  `BACKLOG.md`, `features.json`, `tasks.md`, `progress/`), ejecutando él los tests de la feature y los
  afectados. Hoy lo decide el líder caso a caso.
