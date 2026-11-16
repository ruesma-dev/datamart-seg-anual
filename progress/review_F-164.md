# progress/review_F-164.md
Revisión completa (pasada 1, principal) · `git diff 95a7c022f3..8aa0e6a` · azure-apps `f61570b`

## Veredicto: CHANGES_REQUESTED (RECHAZADO)

La regla es correcta. La he medido en Azure sobre los 16.088 enlaces reales, con el motor de
producción, y no hay ningún camino por el que un parte firmado quede abierto. Las tres desviaciones
están bien y no hace falta volver al humano. Rechazo porque la puerta no protege el `CASE` del SQL,
que es lo que decide en producción: cuatro mutaciones graves de ese `CASE` la dejan en verde (H1).
El arreglo es un test de unas 15 líneas, ya probado. Además, hay papeleo desfasado (H2).

**Nivel de rigor:** `critico` (declarado; disparadores 3 y 4). Exige fase RED, cobertura ≥ 90 %,
mutación con cero supervivientes sin justificar y las MANUAL con su comando.

## Puerta (C1) y lo que he ejecutado yo

- **Puerta completa:** no la repito, por orden del líder (dura 2 h 12 min). Doy por buena la suya
  sobre `4e5ef33` (13.525 passed, `PUERTA COBERTURA` 24/24, `ENTORNO LISTO`). Comprobado: el delta
  hasta HEAD solo toca `BACKLOG.md`, `features.json` e `impl_F-164.md`.
- **Mis tests:** F-164 + F-156 + `test_f006_fichas`, 1.629 passed; los 17 ficheros que leen
  `documento_adjuntos`, 738 passed; sandbox R10 con un PostgreSQL 16 local desechable (ICU),
  **6 passed** (ya parado). Árbol limpio después (solo `?? progress/mutacion_F-163.json`, de F-163).
- **Azure, solo lectura (`filas_solo_lectura`):** el `CASE` literal del SQL de HEAD, aplicado a la
  tabla publicada hoy (última alta 2026-11-15).

## Verificación independiente en Azure

| Comprobación | Resultado |
|---|---|
| Previsión | **Idéntica**: 708 INC→REP **3.341**, 707 UNI→REP **8**, INC 6.729, REP 4.489, TAREA 699, UNIDAD 822. **3.349** de 16.088. Ninguna sale de REPARACION |
| Dominio `familia_publicada` contra el `CASE`, ejecutado por el ARE de Azure, fila a fila | **0 distintas de 16.088** (R10 con datos y motor reales). `familia_adjunto` contra la `familia` de hoy: 0 |
| Abiertas (8.250) con «FIRM» como subcadena (cubre «PARTEFIRMADO»), «FDO», «DNI», «CONFORME», espacios no ASCII o «RS»+cifra en el nombre | **0** |
| Abiertas con «PARTE» o «RECIB»; comprimidos | 20 de PV001: descripciones de fotos del alta («PARTE BAJA»…). 50 de TAREA (`…_PARTE_DE_TRABAJOS`, aceptados en D1). 11 «RECIBIDOR». Los 3 zip y 1 rar de PV001, subidos el día del alta |

Lo abierto es lo que dice la spec en §7. Ningún nulo, cero, acento ni mayúscula abre nada: en el
SQL, `NULLIF(gratipide, 0)` + `IS TRUE` cierran la clase nula y las señales nunca son `NULL`
(`COALESCE`); el `upper()` de Azure sube los acentos (lo confirma la equivalencia fila a fila).

## Las tres desviaciones (ninguna exige volver al humano)

1. **Tipo nulo → REPARACION. Correcta.** La piden R4 y el design §5; solo chocaba con el docstring
   del §3, y en la dirección segura. En el SQL no hay tipo nulo (`JOIN … c.tip IN`).
2. **`CASE` en el `SELECT` final. Equivalente, y mejor.** `b.*` ya trae `NULLIF(BTRIM(…), '')` y
   `NULLIF(gratipide, 0)`, y no duplica la expresión de F-156. Probado sobre los 16.088 enlaces.
3. **ICU `und` en la sandbox. Correcta y necesaria:** Windows no tiene `en_US.utf8` libc, y en `C`
   solo se restringe de más. El cruce con el motor de Azure cierra la diferencia.

## Hallazgos

- **H1 · [Media; bloquea en `critico`] La puerta no protege la ESTRUCTURA del `CASE`.**
  - **Qué pasa:** `test_f164_sql.py:83-109` comprueba los literales (parejas, patrones y columnas
    leídas), no la forma de la expresión. La sandbox sí la ve, pero hace `skip` en la puerta (sin
    DSN), y `harness.mutacion` no muta SQL: T7 tampoco lo verá.
  - **Cómo lo he medido:** mutación a mano sobre una copia (`git archive` de HEAD) en el
    scratchpad, contra los 738 tests y contra la sandbox.

  | Mutante en `06_adjuntos.sql:103-111` | Puerta (sin DSN) | Sandbox |
  |---|---|---|
  | M1 `…clase_grafico_id = 37) OR TRUE) IS TRUE` (abre los sin clase que no dan señal) | **VIVO** | muerto |
  | M2 `…= 37) OR b.clase_grafico_id IS NULL) IS TRUE` | **VIVO** | muerto |
  | M3 `…[0-9]{3,5}' AND FALSE) IS FALSE` (S3 apagada) | **VIVO** | muerto |
  | M4 el `OR` entre S2 y S3 → `AND` | **VIVO** | muerto |
  | M5 `IS FALSE` → `IS NOT TRUE` (equivalente) / M6 quitar `COALESCE(b.descripcion, '')` | muertos | vivo / muerto |

  En `critico`, un mutante a mano que sobrevive pide un test o una justificación aceptada por el
  humano (C4 bis). Aquí toca un test.
- **H2 · [Baja] Papeleo desfasado.**
  - La sección F-164 de `current.md` sigue diciendo «BLOQUEO (T12)… La puerta NO ha terminado en
    verde».
  - Las MANUAL (T8-T11) no están en `current.md` con su comando, y C4 lo exige.
  - T12 sigue en `[ ]`, y la fila «Tiempo de la suite» de `impl_F-164.md` dice «no terminó».
- **H3 · [Info, líder] `f61570b` YA ESTÁ EN `origin/main` de `azure-apps`** (push del 2026-11-16
  17:48:31 de `69fef27`, de proformas, que desciende de él). Es veraz («SIN DESPLEGAR»), pero el
  «sin push» de `impl_F-164.md` ya no vale. Nada apunta a nuestros agentes.
- **H4 · [Info, antes de T7] El `.strip(" ")` de `_texto_senal` no cambia el resultado.** Para S2 el
  espacio ya es no letra, y S3 no está anclado. Su mutante saldrá superviviente equivalente, lo que
  en `critico` pide la aceptación escrita del humano, o quitar el `strip`. Mejor decidirlo ya.

## Cambios requeridos

1. **(H1)** Añadir a `tests/test_f164_sql.py` un test que exija el `CASE` ENTERO, construido con las
   constantes del dominio:
   - un orden fijo de las parejas, `ORDEN_SQL`, porque `LISTA_ABIERTA` es un `frozenset`;
   - `assert set(ORDEN_SQL) == set(pv.LISTA_ABIERTA)`;
   - `esperado = f"CASE WHEN ({' OR '.join(f'(b.tipo_documento_codigo = {t} AND b.clase_grafico_id = {c})' for t, c in ORDEN_SQL)}) IS TRUE AND (upper(COALESCE(b.nombre_fichero, '') || ' ' || COALESCE(b.descripcion, '')) ~ '{pv.PATRON_SENAL_FIRMA}' OR upper(COALESCE(b.nombre_fichero, '')) ~ '{pv.PATRON_SENAL_CODIGO}') IS FALSE THEN b.familia_documento ELSE 'REPARACION' END::TEXT AS familia,"`;
   - `assert esperado in _select_final()`.

   **Probado en la copia:** pasa sobre HEAD y mata M1-M6. Anotar su RED (con M1, por ejemplo).
2. **(H2)** Dejar al día el papeleo:
   - En `current.md`: quitar el BLOQUEO, poner el resultado de la puerta y listar T8-T11 con su
     comando exacto (de `tasks.md` y del design §7: la huella, `70_build_image.ps1`,
     `85_update_job.ps1 -Tag <nuevo>`, `az containerapp job show`, la ejecución puntual, la vuelta
     atrás `-Tag r20261116-1018` y `mcp-bbdd` con los 4 perfiles).
   - Marcar T12 `[x]`.
   - En `impl_F-164.md`, corregir la fila del tiempo y la línea del push (H3).

Recomendado, no exigido: resolver H4 en el mismo ciclo.

## Checkpoints

- **C1** [x] Puerta del líder en verde sobre `4e5ef33` (delta hasta HEAD: papeleo); arnés completo.
- **C2** [x] Una sola feature activa (F-164, `in_review`), en su rama. [!] `current.md` (H2).
- **C3** [x] Hexagonal: el dominio solo importa `re`, `collections`, `datetime` y `typing`, y el SQL
  está en su capa. Cabeceras con ruta; sin `print`, TODO, secretos ni dependencias nuevas. ruff: un
  SIM300 cosmético en `test_f164_dominio.py:62`.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C3 ter** [x] Las decisiones atribuidas llevan fecha y origen (design §9).
- **C3 quater** [x] Solo nuestro documento, en un commit aparte que consta en el informe, y fiel a
  la «Frontera». Push: H3.
- **C4** [x] Cada requisito tiene su test, y pasan. Los unit tests no tocan red ni BBDD; no hay
  dobles nuevos. **[ ]** Las MANUAL no están en `current.md` (H2).
- **C4 bis**
  - [x] Nivel declarado. [x] Cobertura 24/24 (umbral 90 %). [x] «Evidencias» presente (H2).
  - [x] RED con salida real: 266 failed sobre `60ebf8d`, la ruptura del dominio (7 failed) y la
    sandbox contra el SQL viejo y contra el `CASE` roto.
  - **Mutación, RM1–RM6 y supervivientes:** pendiente, pasada de evidencias. RM7: anticipo N/A
    (no se protege un orden). Capa e2e: N/A, sin `servicios.json` ni requisitos `(capa: e2e)`.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1-T6 `[x]`, cada una con su commit `F-164 Tn:`. T7 va tras el APPROVED; T8-T11 son
  MANUAL del despliegue. **[ ]** T12 (H2).

## Cobertura: requisito → test (`tests/test_f164_*.py`)

| Req. | Tests |
|---|---|
| R1, R5, R6 | `dominio::r1_*` (23 parejas × 6 textos), `r5_una_clase_nueva…` (0-199 × 3), `r6_la_extension…` |
| R2, R3, R4, R7 | `dominio::r2_*` (5), `r3_*` (7), `r4_*` (4) + `sql::r4_*`, `r7_*` (2) |
| R8 | `dominio::r8_los_siete…` (7, con su RED) y `r8_la_regla_de_hoy…` |
| R9, R11 | `dominio::r9_*`, `sql::r9_*` (3; falta la estructura, H1), `sql::r11_*` (5) |
| R10 | `sandbox::r10_*` (6), en verde con DSN, y equivalencia sobre los 16.088 de Azure |
| R12, R13 | `diccionario::r12_*` (9), `r13_*` (2) |
| R14-R16 | MANUAL (T10, T11). La previsión de R14, reproducida: 3.349 |

## Observaciones y automejora (no bloquean)

- **O1 · Espacios Unicode.** El `\s` de `re` casa U+00A0 y el del ARE con libc no: un `RS…` con
  espacios duros quedaría cerrado en el oráculo y abierto en el SQL. Hoy, 0 casos.
- **O2 ·** `postventa.yaml:797` «Cuantos partes firmados…» contará los falsos positivos aceptados.
- **Automejora (RM8):** si en `critico` la lógica decisiva vive en SQL y su sandbox hace `skip` en
  la puerta, mutarla a mano sobre una copia (como RM7) y exigir un test de la expresión entera.
