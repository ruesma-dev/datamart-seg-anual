Revisión completa (pasada 1) · principal · `main` (d450937)...`fbac82e`

# F-161 · Review principal

- **Veredicto: CHANGES_REQUESTED** (un cambio requerido, en tests; el código de producción se da por bueno).
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json` (sin `rigor.local.json`). Exige fase RED,
  cobertura de lo cambiado y C1-C5; mutación y e2e informativas. Carril `estandar`: sin RM1-RM7.
- **Puerta:** `init.sh` NO ejecutado aquí por orden del líder (worktree sin `.env`; lo pasa él con `.env` sobre
  `fbac82e`). C1 y la línea `PUERTA COBERTURA` quedan a su resultado.

## Lo que ejecuté (2026-11-13, worktree, `SIGRID_API_*` ficticios)

- `tests/test_f161_{dominio,sql,diccionario}.py`: **119 passed** (r21 de azure-apps ya en verde por `d6bb377`).
- **Sandbox SIN skip** en un PostgreSQL 16 local desechable (`initdb` en mi scratchpad, puerto 55161, borrado
  al terminar): `test_f161_sandbox.py` **15 passed**; `test_f157_sandbox.py` + `test_f162_sandbox.py` (cargan el
  `stg/01_ddl.sql` cambiado) **33 passed**. T11 queda así verificado por el reviewer.
- Regresión dirigida (f006, f019, f024, f025, f040, f047, f078, f079, f095, f097, f110, f118, f140, f147, f148,
  f149, f157, f162, f161): **6036 passed, 2477 skipped, 0 failed** en 1006 s (los skip, sandboxes sin DSN).
- Mutaciones a mano en una COPIA (`git archive HEAD` en el scratchpad; el árbol no se tocó), ver hallazgo 1.

## Checkpoints

- C1 `[x]` condicionado: `init.sh` con `.env` es del líder (instrucción expresa). Sin su exit 0, no vale este informe.
- C2 `[x]` una activa (F-161 `in_review`), rama `feature/F-161-versiones-sin-reparto`. `current.md` arrastra secciones
  de otras features: preexistente en `main`, no de esta rama (observación O5).
- C3 `[x]` hexagonal: `domain/master_versiones.py` puro (solo stdlib); `master_versiones_sql.py` solo construye texto;
  SQL por capa (`stg/10`, `mart/01b`). Primera línea con ruta en los 8 ficheros nuevos; sin `print`, TODO ni secretos.
  Semántica Sigrid: `fas` = versión en 8/11, `importe` sin coeficientes, v0 según D6.
- C3 bis `N/A`: no entra ningún documento de fuera. C3 ter `N/A`: no registra conversación nueva; D1-D14 citadas
  con fecha y origen en `features.json` y design §10.
- C3 quater `[x]`: `azure-apps` `d6bb377`, commit aparte, solo `datamart_seg_anual.md` (+19), sin push, contenido
  igual a la frontera de design §1 (cuatro objetos, sin permisos nuevos, reiniciar `mcp-bbdd`).
- C4 `[ ]` **por el hallazgo 1**: cada requisito tiene test trazable y pasa (tabla abajo), pero la capa sandbox de
  R10/R16 —la que demuestra D4 con SQL ejecutado— no puede fallar. Unit tests sin red ni BBDD `[x]`. MANUAL listadas
  `[x]` por referencia (`current.md` → `impl_F-161.md` y design §8, como en F-040). Dobles: no hay dobles nuevos.
- C4 bis: rigor declarado `[x]`; **fase RED `[x]`** (salida real: `ModuleNotFoundError` y 83 failed, con las trazas de
  R10 y R9; las 3 verdes en RED son guardas de «no cambia», legítimas); **cobertura**: pendiente de `PUERTA COBERTURA`
  del líder; **mutación** `N/A por nivel` (informativa, la campaña corre tras esta pasada); RM1-RM7 `N/A` por carril;
  Evidencias `[x]` (los cuatro números y la fila e2e); capa e2e `N/A`: ETL sin interfaz y ningún requisito `(capa: e2e)`.
- C4 ter `N/A`: no existe `harness/rutas_sensibles.json`.
- C5 `[x]` con pendientes del líder: T1-T2, T4-T6, T8-T9 `[x]` con commit `F-161 Tn`; T3, T7, T12, T13 MANUAL tras
  merge; T10 hecho (`3e17f08` + `d6bb377`) y T11 hecho (arriba) pero sin marcar; T14 es la puerta del líder.
  Árbol limpio.

## Cobertura requisito → test

| R | Tests (todos en verde) |
|---|---|
| R1-R5 | `test_f161_sql` r1-r5 (DDL, PK, universo, D6, D13, expresiones de 08) + sandbox r1-r5 con oráculo |
| R6 | sql r6 ×5 (detrás de fase0, último, entero, fuera de sello y ventana) + `test_f157_step` |
| R7-R9 | sql r7 ×9, r8, r9 ×4; dominio r7 (cascada) |
| R10 | sql r10 ×9 (02, 06, 05 y su `DO`); dominio r10; sandbox r10 (**vacía para D4**, hallazgo 1) |
| R11 | sql r11 ×2 (`CATALOGO_ANTERIOR` = 06 en `491fbf1`; `EXCEPT` doble) + sandbox r11; MANUAL paso 4 |
| R12 | sql r12 ×2 + sandbox r12 (versión sin reparto por partida) |
| R13 | MANUAL (paso 4: 776 filas / 2.107.662,97 €) |
| R14-R15, R17 | sql r14 ×7, r15, r17; dominio r14; sandbox r14 (oráculo mes a mes), r15 (la 0721) |
| R16 | sql r14_r16 (predicado de 02 copiado) + sandbox r16 (**vacía para D4**, hallazgo 1); MANUAL paso 4 |
| R18-R19 | MANUAL (huellas, `check-cp-tipologia`, T3) |
| R20-R21 | `test_f161_diccionario` r20 ×10, r21 ×3 + f006, f079, f147 |

## Cambios requeridos

1. **La sandbox no ejercita D4: R10 y R16 pasan aunque se quite el filtro.** `tests/test_f161_sandbox.py:69-79`
   (`CABECERAS`): todas las versiones sin reparto son «CIERRE…» (o sin texto), así que caen por `tipo_master`
   antes de llegar a `tiene_reparto`. Lo comprobé en una copia: quitando `tiene_reparto` de
   `mart/02_build_fact.sql:70`, de `mart/06_cp_tipologia.sql:150` y de `mart/01b_master_versiones.sql:207` (la CTE
   `temporales`), la sandbox sigue **15/15 en verde**; solo lo cazan los tests de texto (`test_f161_r10_02_filtra…`,
   `…_master_vigente_anual_filtra_reparto`, `…_r14_r16_la_temporal_con_el_predicado_de_02`). Es el caso real que el
   filtro protege: las 927 versiones «sin `plafec`» del diagnóstico (§5.2) entran ahora al catálogo y pueden ser de
   tipo temporal. **Pido:** una versión de tipo temporal SIN reparto y posterior a la temporal vigente (p. ej.
   OBRA_A, ámbito 8, v6 «PLANIFICACION CUATRIMESTRAL OCT-26», `plafec` 0, `fec` octubre 2026, una línea con importe y
   sin `planif`) y que la sandbox afirme: `fact_seguimiento_mensual.version_master` nunca es 6;
   `master_vigente_anual` no la elige; en `master_importe_mensual` del mes del build, `version_temporal` = 2 y
   `version_importe` = 6, con `tipo_master_importe` = 'Cuatrimestral'. Ajustar las expectativas que cambien (r1, r3,
   r14 «hoy»). Criterio de hecho: repetir mi mutación de 02, 06 o `01b` debe poner la sandbox en rojo.

## Observaciones (no bloquean)

- **O1 · D4 en `retenciones/05_fin_obra.sql:162` y `:119`** (desviación 4 del implementer): el catálogo trae ahora
  versiones con `tiene_reparto` y `version_fec_efectiva` NULL, que el de antes excluía (06 filtraba la fecha). La CTE
  `cuatrimestral` elige por `MAX(version)` sin mirar fecha (F-110 D1 lo exige y `test_f110…:97` lo veta), así que una
  Cuatrimestral con reparto y sin fecha cambiaría el fin de obra. Hoy 0 casos y es literal a R10; que el líder lo
  enseñe al humano en el resumen: aceptarlo o añadir `AND v.version_fec_efectiva IS NOT NULL` (y aflojar ese veto).
- **O2 · Coste de `stg/10_master_versiones.sql:76-91`**: el `EXISTS` correlado sobre la CTE `plan` dentro de un `OR`
  no se convierte en semi-join (recorre la CTE por cada línea v0), y el de `con_reparto` es una sonda de índice por
  línea (~1 M). T3 debe medir esa CTE en concreto; si duele, `(obra_id, ambito_id, fase_num) IN (SELECT … FROM plan)`
  (subplan con hash) o un `UNION ALL` de las dos ramas.
- **O3 · R16 solo hasta el mes del build** (desviación 3): el mensual proyecta meses futuros y `master_importe_mensual`
  no los tiene (D9). Coherente con D9, pero R16 dice «todo mes»: anotarlo en la spec al cerrar.
- **O4 · `mart/01b_master_versiones.sql:170`** `JOIN stg.partidas` interno: una línea con partida ausente desaparece
  de la vista por partida. El paso MANUAL 4 (776 filas de R13) lo detectaría; valorar `LEFT JOIN`.
- **O5 · Papeleo del líder**: la sección F-161 de `current.md` dice `in_progress` y T10 MANUAL (ya hecho en
  `d6bb377`); marcar T10 y T11 en `tasks.md`.
- **O6 · `config/diccionario/stg.yaml`** (`master_versiones`): `n_lineas` lleva `agregacion: suma` y los importes
  `no_sumable`; sumar `n_lineas` entre versiones también multiplica. Menor.

## Juicio de lo que pidió el líder

- **Desviaciones 1-9**: legítimas. La 1 (`CASE` y no `COALESCE`) es mejor que el design: con `COALESCE` un NULL de
  `plan_mensual` se rellenaría con la cabecera y rompería R4/R11. La 4 y la 3, en O1 y O3. La 8 la resolvió el líder.
- **Tests de otras features adaptados, ninguno relaja una guarda**: `f097_r17` mira los mismos nueve literales donde
  vive ahora la cascada (`01b`); `f040_r30` exime solo `retenciones/05_fin_obra.sql`, con motivo, y sigue vetando
  `tesoreria/` y el resto de `retenciones/`; `f095` y `f110` alargan la cadena con `AND tiene_reparto` y mantienen
  todo lo demás (incluido el veto de fechas); `f157_step` sigue exigiendo fase0 justo detrás de `plan_mensual`;
  `f147` sube el tope con su entrada de historia; el de f006 es solo la línea de recuentos de `current.md`.
- **MANUAL (T3, T7, T12/T13)**: suficientes. Comandos de design §8 con criterio de parada explícito (cualquier
  diferencia de huella o de `check-cp-tipologia` → PARAR y volver a la imagen anterior; T3 > 5 min → PARAR). Añadir a
  T3 lo de O2 y a T7 cuántas de las versiones que entran son de tipo temporal (la población que protege D4).
- **Código de producción**: correcto contra design §3. Orden de `build_mart` (`01b` antes de `02`); `01b` deja la
  vista de 8 columnas + 9 detrás (R8); `02` cambia solo la CTE; `tesoreria/07` sigue bien (busca por clave, una fila);
  ningún objeto fuera de `mart` depende del catálogo, así que el `DROP … CASCADE` de `01b` no arrastra nada nuevo;
  `stg/01_ddl.sql` no está en `FICHEROS_DEL_SELLO`.

## Automejora (propuesta, no aplicada)

- `reviewer.md`, punto 2 del protocolo: «si un requisito declara capa sandbox y protege un filtro, el reviewer
  comprueba que la sandbox se pone en rojo al quitarlo». Es el RM7 aplicado a SQL y sirve también en `estandar`:
  aquí la sandbox estaba en verde y era vacía para la decisión más importante de la feature.
