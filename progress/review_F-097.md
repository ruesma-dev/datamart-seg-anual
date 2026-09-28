<!-- progress/review_F-097.md -->
Revisión completa (pasada 1) · `main...7d7dc0b` (rama `feature/F-097-descompuestos-partidas`)

# F-097 · Review del reviewer

**Veredicto: CHANGES_REQUESTED.** Dos cambios pequeños y localizados en el troceado
(hallazgos 1 y 2) y uno de papel. El resto —incremental, orígenes, cuadre, pipeline,
diccionario, R29, mutación— está bien hecho y verificado; no hay que tocarlo.

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de lo
cambiado y campaña de mutación con supervivientes analizados. RM5 no aplica (solo `critico`).

## Hallazgos, por gravedad

1. **MEDIA (bloquea) · `fn_trocear` revienta con un número válido pero grande.**
   `01_troceado.sql:81-82` castea `ROUND(precio*rendimiento,2)` y `ROUND(cantidad*precio,2)`
   a `NUMERIC(18,2)`: un producto >= 1e16 da `numeric field overflow` y tumba el sub-paso
   (`lineas_coste` o el lote de `lineas_master`). `PATRON_NUMERO` admite hasta `e999`, así
   que la protección de la desviación 9 del informe («`1e9999` reventaría el build; R14 pide
   NULL») no protege. **Evidencia** (PostgreSQL 16 local desechable con `00`+`01`): precio
   `12345678901234567` × 1 → SQL `NumericValueOutOfRange`, Python devuelve fila (espejo
   divergente); `1e300` → SQL `NumericValueOutOfRange`, Python `decimal.InvalidOperation`.
   Hoy el dato no lo trae (muestra mía de Sigrid, solo lectura: 29.383 registros del master,
   máximo |número| 1,2 M, |producto| 2,4 M), pero el diseño promete que un `|` en el texto
   largo «desplaza campos y queda a la vista», no que pare el build, y con el master
   incremental un registro así en una versión cerrada deja `build_descompuestos` `FAILED`
   **todas las noches** hasta cambiar código. Arreglarlo cuesta dos líneas.
2. **BAJA (bloquea: el espejo es el oráculo) · Python acepta un `\n` final que el SQL no.**
   `domain/descompuestos.py:99-100`: `re.match` con `$` casa antes de un `\n` final; en
   PostgreSQL `$` es fin de cadena. `...|12\n|3|...` da precio 12 (y un enlace `55\n` da
   `dncpro_id` 55) en Python y NULL en SQL. **Evidencia** (misma base): esos dos casos
   `iguales=False`; 38/37/35/29/19 campos, CRLF, texto largo con saltos y `~` dentro,
   cabecera basura y `~d|` → `iguales=True`.
3. **BAJA (no bloquea) · un error de Postgres al escribir UNA versión aborta la ingesta**
   (`_fase("versiones", ...)` dentro del bucle), mientras que un error de Sigrid o un
   recuento distinto se registran y se sigue (R9). Hipotético (un `ide` que cambie de
   versión chocaría con la PK de `_des_texto`). Para una ficha menor, no para esta.
4. **INFO · las PK de `lineas` y `cuadre_partida` suponen `(obra, partida, amb, fas)` único**
   (`stg/06` deduplica por ahí). Sigrid, solo lectura: 0 repetidos con `des` (ámbito 3 fase
   0 y 8), 0 con `pre <> 0` y `obride <> 0`; 0 `dncide` compartidos entre obras y 0 partidas
   de `dncpro` de otra obra. Si aparece, falla en voz alta. Aceptado.
5. **INFO** · SQL probado por texto (convención, F-056); lo compensa el espejo (88 tests).
6. **INFO** · `current.md`: la sección F-097 aún se titula «PARADA 1 pendiente».

## Cambios requeridos

1. Que un número fuera de rango no tumbe el build (`01_troceado.sql`, `00_setup.sql` y
   `domain/descompuestos.py`): acotar `PATRON_NUMERO`/`fn_num` a una magnitud que no
   desborde (p. ej. |x| < 1e15, exponente acotado en consecuencia), o proteger los dos
   `ROUND(...)::NUMERIC(18,2)` con `CASE WHEN abs(...) < 1e16` (NULL si no cabe). Mismo
   comportamiento en el espejo, sin `InvalidOperation`. Tests: espejo con `1e300` y 17
   cifras → NULL sin excepción, y la aserción textual en `test_f097_descompuestos.py`.
   Corregir la frase de la desviación 9 en `progress/impl_F-097.md`.
2. `domain/descompuestos.py:99-100`: `_NUMERO` y `_ENLACE` con `fullmatch` (o `\Z`), y un
   test con un numérico y un enlace seguidos de `\n` dentro del registro.
3. `progress/current.md`: título de la sección F-097.

## Lo verificado por mí

- `bash harness/init.sh` entero (pasada 1): **5922 passed, 219 skipped** en 14 min 9 s;
  `PUERTA COBERTURA [OK] 99,6 %` (512/514); la única `[KO]` fue `PUERTA TAMAÑO` por el
  borrador de ESTE informe (168 > 140), recortado y relanzado: ver la línea final.
- **Incremental.** Ningún `DROP`/`TRUNCATE` de las tablas de estado en ningún sitio (barrido
  de `main.py`, steps y SQL: solo `raw` del YAML y esquemas ajenos). `reemplazar_filas`:
  `DELETE`+`COPY`+control en una conexión y un `commit`, `rollback` si algo falla. Recuento
  distinto → no se escribe nada (copia y control viejos): la noche siguiente la huella
  vuelve a diferir y se relee. Tope: vigente > cambiada > nueva, por `(obra, fas)`, corte en
  seco, ámbito 3 primero, siempre entra una; `--sin-tope` lo ignora; el build, igual.
- **Orígenes (R17, D1, D13).** v0 `MASTER_INICIAL`; >= primera ABC `MASTER_PLANIF_JO`; resto
  `MASTER_PRE_ABC`; `obrfasamb` sin duplicar; vigente `MAX(conext.valn)` cod `'15'`;
  `tipo_version` literal de `mart`. `SUSTITUIDO_POR_PLANIFICACION` solo en ESTUDIO, por
  partida con algún registro enlazado, que ESTUDIO excluye entera. Vistas con origen fijo.
- **Cuadre.** Hoja (`obrparpar.padide`), `pre <> 0`, `obride <> 0`, precio a 2 decimales
  frente a Σ `importe_unitario`, tolerancia 0,01; sin líneas de ese origen →
  `SIN_DESCOMPUESTO`. Ámbito 3 en `05`; master del lote en `03`, en su transacción.
- **R29.** Solo `obrparpre` cambia en el YAML; las otras 13, F-115 (fichada).
- **Pipeline (D3).** Nadie depende de los dos pasos; una ingesta `FAILED` salta solo
  `build_descompuestos` (la noche sale 1, como con cualquier build). `check-declarados` ve 11
  objetos; tras la primera noche con la ingesta en verde existen todos aunque no haya
  primera carga, así que no añade rojo propio.
- **Diccionario.** Avisa del master INCOMPLETO hasta la primera carga y de los tipos 3 y 11
  PROVISIONALES; `R-DESCOMPUESTO-ORIGEN`, `R-FRESCURA` a siete, `version: 37`.
- **Reglas duras.** Barrido del diff (claves, GUID, IPs, correos, cadenas de conexión): nada.
  Mis lecturas de Sigrid, solo `SELECT` por `leer_sql`; nada escrito en Azure. `azure-apps`
  85356e6 sin push. Árbol limpio tras mis pruebas.

## Mutación (C4 bis)

Recálculo puro: **1.321 líneas, 175 mutantes** = informe; muestreo reproducido (semilla
20260820): los 4 supervivientes en la muestra, mismo operador y texto. RM1: SHA `c1bf0bf`;
lo posterior no toca producción. RM2: 209,3 s × 2 workers = 418,6 s frente a base 439 s;
20 × 209,3 = total. Coste por mutante 418,7 s. Sin cabecera de no válida, 0 sin veredicto.
**Campaña no reejecutada: 69,8 min según el informe.** RM3: el muerto `slots=False` no es
equivalente (lo mata el barrido conductual de `test_f006_dataclasses_inmutables.py`). RM4:
los cuatro supervivientes reproducidos sobre una copia (`git archive`): 2, 1, 1 y 1 fallos;
sin mutar 88 passed. RM6: no se quitó código defensivo.

## Checkpoints

- C1: [x] `init.sh` exit 0 (relanzado, línea final) · [x] ficheros del arnés.
- C2: [x] una `in_progress` · [x] rama correcta · [x] `current.md`: F-097 solo añade su
  sección (criterio de F-056) · [x] `done` con resumen en `history.md` (sin cambios).
- C3: [x] hexagonal y SQL en `sql/descompuestos/NN_*.sql` · [x] ruta en primera línea ·
  [x] sin prints de debug (los de `F-097_comparar_huellas.py` son su salida), secretos ni
  dependencias nuevas · [ ] **troceado robusto como promete el diseño** (hallazgos 1-2);
  ámbito/fase y versiones duplicadas de `obrfasamb`, bien.
- C3 bis: N/A — no toca `docs/referencia/`. C4 ter: N/A — sin `rutas_sensibles.json`.
- C4: [x] R2-R29 con test (`test_f097_un_test_por_requisito` lo exige); R1, R30, R31 MANUAL ·
  [x] sin red ni BBDD · [x] MANUAL en `current.md` con comando y resultado esperado (T0 con
  PARAR, T17, T18 C1-C4, T19) · [x] dobles contra el original (barrido de la suite, verde).
- C4 bis: [x] `rigor` · [x] RED con trazas (R8, R9, R29) · [x] cobertura 99,6 % · [x]
  mutación verificada · [x] muertos: > 60 s, recálculo + RM1-RM4 · [x] coste por mutante ·
  [x] sin cabecera no válida · [x] RM1 · [x] RM2 · N/A RM5 (`estandar`) · [x] RM6 · N/A
  campaña manual (automática, 175) · [x] supervivientes analizados · [x] «Evidencias»
  completas con 2 workers.
- C5: [x] tareas `[x]` con commit `F-097 Tn:`; T0, T17, T18, T19 MANUAL `[ ]` a propósito
  (bloquean la puesta en producción, decisión del humano del 2026-09-28) · [x] sin
  temporales · [x] `features.json` en `in_progress`.

## Cobertura requisito → test (prefijo `test_f097_`)

| Req. | Test | Req. | Test | Req. | Test |
|---|---|---|---|---|---|
| R1 | MANUAL T0 | R11 | `r11_*` (2) | R21 | `r21_*` (dominio y SQL) |
| R2 | `r2_*` (7) | R12 | `r12_*` (2) | R22 | `r22_catalogo_de_elementos` |
| R3 | `r3_*` (3) | R13 | `r13_*` (14) | R23 | `r23_*` (2) |
| R4 | `r4_*` (5) | R14 | `r14_*` (5) | R24 | `r24_tres_vistas_*` |
| R5 | `r5_*` (11) | R15 | `r15_estudio_sin_*` | R25 | `r25_*` (8) |
| R6 | `r6_*` (10) | R16 | `r16_planif_jo_*` | R26 | `r26_*` (2) |
| R7 | `r7_*` (3) | R17 | `r17_*` (3) | R27 | `r27_*` (6) |
| R8 | `r8_*` (8) | R18 | `r18_identificacion_*` | R28 | `r28_documentacion` |
| R9 | `r9_*` (3) | R19 | `r19_*` (7) | R29 | `r29_*` (4) |
| R10 | `r10_*` (3) | R20 | `r20_clave_*` | R30-31 | MANUAL T17-T18 |

## Automejora (propuesta, no aplicada)

- `reviewer.md`: si hay **espejo** Python de un SQL, contrastar ambos en casos límite en un
  PostgreSQL local desechable (números enormes, saltos en campos). Cazó 1 y 2.

`init.sh` relanzado: exit 0, 5922 passed, cobertura 99,6 %, tamaño 140/140, ENTORNO LISTO.
