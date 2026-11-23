Revisión completa (pasada 1, principal) · `git diff 5566284..bb1b130` · rama `feature/F-168-texto-largo-flujo-obra`

# F-168 · Review · El texto largo de la partida y del flujo de obra

**Veredicto: CHANGES_REQUESTED.** Tres cambios pequeños y concretos; el código y el SQL están bien
y los he visto ejecutarse.

**Nivel de rigor:** `estandar` (declarado en `features.json`): C1-C5, fase RED, cobertura de lo
cambiado y mutación **informativa** (sin RM1-RM7). Capa e2e N/A: no habrá pasada de evidencias.

## Lo que verifiqué ejecutándolo

1. **La sandbox, que el implementer no corrió.** El puesto SÍ tiene PostgreSQL 16
   (`C:\Program Files\PostgreSQL\16\bin`, con `initdb`). Levanté un clúster DESECHABLE en mi
   scratchpad (`initdb -A trust` + `pg_ctl`, puerto 54399; sin tocar el servicio instalado ni nada
   compartido) y lo borré al acabar: `tests/test_f168_sandbox.py` → **13 passed en 5,36 s**.
2. **`03_lineas_master.sql` real**, que la sandbox no ejecuta (script en el scratchpad con
   `componer_sql_lote` y el sello real): versiones master 0 y 1 → 6 líneas con el `texto_id` del
   dominio, `NULL` sin texto, 0 huérfanas, `textos` 3 → 4 (no repite el de ESTUDIO), sello escrito;
   repetir el lote no duplica; lote vacío y `05_cuadre.sql` con la columna nueva de `fn_trocear`, OK.
3. **Migración** desde `00/01/02` de `5566284`: `texto_id` entra AL FINAL por `ALTER`, `textos` se crea.
4. Los 6 `test_f168_*` y los 15 ficheros adaptados, con la sandbox: **1.301 passed, 4 skipped (ajenos
   a F-168), 0 failed en 431,82 s**. Suite entera no relanzada (instrucción del líder).

## Los puntos que pidió el líder

- **`descompuestos` sigue incremental**: ningún `DROP`/`TRUNCATE` de `lineas`, `textos`, `_des_texto`
  ni `_versiones_cargadas` (grep en `sql/descompuestos/`, los dos steps y `main.py`). `textos` es
  `CREATE IF NOT EXISTS` + `ON CONFLICT DO NOTHING`. El sello suma `../stg/11_texto_largo.sql` (bien
  resuelto desde `DIRECTORIO_SQL`; el Dockerfile copia `etl_sigrid/` entero): cambia una vez y retrocea
  por lotes con el mecanismo de F-120, probado en el punto 2.
- **Recorte en origen real**: `stream_table` cambia `[tex]` por `expresion_recorte('tex', 16000)`
  (`SUBSTRING(...,1,16000)` + `REPLACE` de `CHAR(0)` con colación binaria); es la única vía de ingesta
  de `raw`. Lo fijan `r3_stream_table_pide_la_columna_recortada` (SQL enviado) y
  `r4_la_ingesta_pasa_los_recortes_a_sigrid` (cableado). Contra Sigrid real: T13 (MANUAL, líder).
- **D6**: ni `GRANT`/`REVOKE`/`_restringida` en el diff; `apply_grants` es por esquema
  (`ALL TABLES IN SCHEMA`), los objetos nuevos heredan los permisos sin código. Lo vigilan `r24_*`.
- **Diccionario v82**: fichas de `stg.partida_texto`, las 3 funciones de `stg/11`, `compras.linea_texto`,
  `compras.textos`, `compras.v_linea_texto`, `descompuestos.textos` y `lineas.texto_id` con relación;
  tocadas `stg.partidas.descripcion_corta`, las líneas de compras y `documento_texto` (12, 15, 44, 46).
  Las trampas de design §7 están todas.
- **`azure-apps` `2f4d08c`**: solo `datamart_seg_anual.md` (+27/−1), commit aparte, sin push
  (`ahead 2`; el otro, `c36a412`, es ajeno). Coincide con la «Frontera» de la spec.

## Desviaciones declaradas

- `stg.fn_texto_recortado`: **justificada** (el 16000 en un solo sitio de SQL; cubierta por R7).
- Temporal `_f168_fuentes ON COMMIT DROP`: **justificada** (limpia una vez; probada en la transacción).
- `CASE` local 12/46 en `compras/07`: **justificada** (`fn_tipo_documento` es compartida; sandbox R18 OK).
- Textos de descompuestos en CTE + `ON CONFLICT`, sin vaciar: **justificada** (design §4.4). Coste:
  observación 2.
- `PRESUPUESTO_MAX` +220: **aceptable con aviso**. R25 dice «sin pasarse»; la práctica del repositorio
  (F-127, F-150) es subir con motivo escrito, y lo trae. El humano debe verlo en el resumen final.
- 15 tests adaptados: **justificados**, cada uno comentado; ninguno afloja una guarda (F-097 R26 admite
  solo las dos funciones de `stg`; F-123 guarda las huellas viejas al lado de las nuevas).

## Checkpoints

**C1** — [ ] `init.sh` verde: **pendiente de la puerta del líder** (`puerta/F-168`). Con los KO ya
conocidos (`PUERTA COBERTURA` y `test_en_este_repositorio_la_base_no_esta_rezagada`, `main` 37 commits
detrás de `dev`) no se podría aprobar igual: es de base, no de F-168, pero no se aprueba en rojo.
[x] Ficheros del arnés presentes.

**C2** — [x] una activa. [x] orden de prioridad. [x] rama `feature/F-168-...`. [x] `current.md` abre
con la sesión activa (observación 4). [x] `history.md`.

**C3** — [x] hexagonal (`domain/texto_largo.py` puro). [x] ruta en la primera línea de los 10 ficheros
nuevos. [x] sin `print`, TODO, secretos ni dependencias nuevas. [x] Sigrid: R10 no filtra ámbito a
propósito (un texto por partida) y no toca importes.

**C3 bis** — N/A: no toca `docs/referencia/`. **C3 ter** — N/A: el diff no atribuye afirmaciones
nuevas a personas (las decisiones citadas están en la spec ya aprobada, con fecha).
**C3 quater** — [x] los cuatro puntos (arriba).

**C4** — [ ] **R17 sin test trazable** (cambio 1). [x] unit sin red ni BBDD (la sandbox se salta sin
DSN). [ ] **MANUAL sin comando en `current.md`, y T14 incompleta** (cambio 2). [x] dobles: el falso de
`test_f150` acepta `recortes=` como el original; la comprobación automática va en la puerta del líder.

**C4 bis** — [x] `estandar` declarado. [x] fase RED con trazas reales por tarea (T1-T8, T10).
[ ] cobertura: pendiente de la puerta del líder. N/A por nivel: mutación, RM1-RM7 y supervivientes
(informativa en `estandar`; sin informe aún → observación 5). [x] «Evidencias» completas (cobertura no
medible en el worktree, con motivo). Capa e2e N/A (`CAPA E2E: N/A`). C4 ter N/A (sin
`harness/rutas_sensibles.json`).

**C5** — [ ] T9 sigue `[ ]` aunque ya corrió verde (cambio 3); T13-T16 son MANUAL tras desplegar y T17
es la puerta del líder. [x] un commit `F-168 Tn:` por tarea. [x] árbol limpio (`mutacion_F-164.json` es
del checkout principal). [x] `features.json` en `in_progress`.

## Cobertura requisito → test (`test_f168_` + …)

R1 `r1_*` · R2 `r2_*` (3) · R3 `r3_*` (6) · R4 `r4_*` (5) · R5 `r5_*` (10) + sandbox · R6 `r6_*` (5) ·
R7 `r7_*` (3) · R8 `r8_*` + sandbox · R9 `r9_*` · R10 `r10_*` + sandbox · **R11 MANUAL (T14)** ·
R12 `r12_*` (2) · R13 `r13_*` (5) + sandbox · R14 `r14_*` + sandbox · R15 `r15_*` + sandbox ·
R16 `r16_*` + sandbox · **R17 ninguno (cambio 1)** · R18 `r18_*` + sandbox · R19 `r19_*` (4) ·
R20 `r20_*` (7) + sandbox (+ master en mi script) · R21 `r21_*` (5) + sandbox · R22 `r22_*` ·
R23 `r23_*` + sandbox · R24 `r24_*` (2) · R25 `r25_*` (7) · R26 reviewer (`2f4d08c`) ·
**R27 MANUAL (T15)**.

## Cambios requeridos

1. **Test trazable de R17** (`tests/test_f168_sql.py` y `tests/test_f168_sandbox.py`). No hay ningún
   `test_f168_r17_*`. Estático: la rama OFERTA de `16_textos_linea.sql` toma `o.ide` de `raw.dcopro` y
   la NECESIDAD `n.ide` de `raw.dncpro`, las mismas claves que publica `09_comparativos_detalle.sql`
   (`lp.ide AS linea_oferta_id`, `NULLIF(l.dncproide, 0) AS linea_necesidad_id`). Sandbox: una línea de
   comparativo y una de oferta que casan con `compras.v_linea_texto` por (`tipo_linea`, `linea_id`) sin
   tabla intermedia.
2. **`progress/current.md` con las verificaciones MANUAL y su comando exacto** (C4), no «descritas en el
   informe». Y **corregir T14** en `tasks.md`, `impl_F-168.md` y `current.md`: la ingesta suelta es
   `python main.py ingest --full --table <t>` para cada una de las seis. Sin `--full` es incremental
   desde `max(ide)` (`ingest_raw_step.py:357`): `ensure_raw_table` añade `tex` vacía, las filas que ya
   estaban se quedan con `tex` NULL y `stg.partida_texto`/`linea_texto` salen casi vacías hasta la
   nocturna (que sí va con `run-all --full`, Dockerfile).
3. **T9 en `tasks.md`**: la sandbox ya corrió verde (13/13, punto 1): márcala `[x]` citando esta review y
   corrige en `impl_F-168.md` «el puesto no tiene Postgres local» (tiene PostgreSQL 16 con `initdb`).

## Observaciones (no bloquean)

1. **Primera noche**: `stg/11` va el ÚLTIMO de `build_stg`; si esa noche falla un sub-paso anterior,
   caen también `compras/16` y todo `build_descompuestos` (sin las funciones). Moverlo al principio
   (son funciones puras) lo evitaría.
2. **CTE de `03`**: `troceado` se lee dos veces y Postgres lo MATERIALIZA (antes iba en flujo). Con
   `--sin-tope` es el master entero a disco temporal: en T14, mirar `temp_bytes` y los créditos de CPU.
3. `PRESUPUESTO_MAX` +220 contra la letra de R25: que el líder lo diga al humano.
4. `progress/current.md` arrastra 6.161 líneas (417 KB) de sesiones anteriores; C2 pide solo la activa.
   Previo a F-168: purgarlo al cerrar.
5. Sin `progress/mutacion_F-168.md` aún (informativa): sus totales, al resumen final.

## Automejora (propuesta, no aplicada)

- `implementer.md`/`reviewer.md`: antes de declarar «sin Postgres local», buscar
  `C:\Program Files\PostgreSQL\*\bin\initdb.exe` y levantar un clúster desechable en el scratchpad
  (`initdb -A trust` + `pg_ctl -o "-p <puerto>"`): convierte las sandbox en `skip` en evidencia sin
  tocar nada compartido.
- Ninguna sandbox ejecuta `descompuestos/03_lineas_master.sql`: añadir un caso de master la próxima
  vez que se toque `03`.
