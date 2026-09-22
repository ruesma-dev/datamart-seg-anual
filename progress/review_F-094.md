<!-- progress/review_F-094.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` hasta `a7e647c`

# F-094 · Review (2026-09-22)

**Veredicto: CHANGES_REQUESTED** (un solo `[ ]`, documental y barato: ver «Cambios requeridos»).
Contrato: los 4 `acceptance` (sdd=false), el plan aprobado el 2026-09-22 y la ampliación H6 (resto de F-045).

**Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura ≥ 80 % de lo cambiado y
campaña de mutación con los supervivientes analizados; no exige cero supervivientes ni RM5.

## Lo verificado por mí (no copiado del informe)

- **`bash harness/init.sh`** en el árbol principal, con su `.env`: **exit 0, «ENTORNO LISTO»**. 5.043 passed, 189 skipped, 0 failed (30 min 45 s); `[OK] PUERTA COBERTURA: 94.7% de 1022 líneas cambiadas (968/1022, umbral 80%)`; `[OK] PUERTA TAMAÑO`; rama correcta. Únicos avisos, previos: F-052 blocked y 232 de ruff.
- **Cifras, releídas en SOLO LECTURA contra Azure** (`psycopg` con `default_transaction_read_only=on`, sin
  `build_postgres_client`; he ejecutado el SELECT NUEVO de `01_movimientos.sql` como subconsulta, sin builds).
  Coinciden todas al céntimo con el informe:
  PROVEEDOR VIVA **7.752 / 8.345.506,03** (vencidas 3.857 / 3.163.487,46) · LIQUIDADA 2.368 / 12.754.011,79 ·
  BAJA 15.511 / 18.691.779,56 · CLIENTE VIVA 2.196 / 22.157.642,75 · LIQUIDADA 42 / 322.851,50.
  **FERMALUX** (1958815): VIVA 51 / **64.201,96**, BAJA 23 / 17.246,76, LIQUIDADA 3 / 17.246,76.
  **27.869 filas y 27.869 claves `(sentido, movimiento_id)` distintas**: el JOIN a `raw.con efe` y a
  `maestro.centros_coste` no multiplica (la PK del build no reventará).
  **Obra: 262 `obra_id` distintos, 262 en `maestro.obras`**; 27.336 filas con obra; 0 filas con centro y sin
  obra; `v_pbi_retencion_obra` agrupada da 262 filas para 262 `obra_id`.
- **`est 15`**: `maestro.estados_documento` tipo 25 → 15 = `DIV` «Divididos» (catálogo: 1 PDT, 2 APR, 3 EMI,
  5 CAR, 7 REM, 10 PAG, 12 DEV, 14 AGR, 15 DIV, 20 ANT, idéntico al del informe). **0 efectos** de retención en
  `est 15`: hoy no mueve un euro; incluirlo es coherente con 14 (padre sustituido por sus hijos).
- **Precedencia BAJA > LIQUIDADA**: los efectos con `fecbaj` y `fecrea` a la vez son **2 / 1.000,84 €**
  (reproducido). BAJA primero es lo que evita el doble conteo: el original agrupado y su AGR pagado no pueden
  sumar los dos en `importe_liquidado`. FERMALUX lo enseña: BAJA 17.246,76 = LIQUIDADA 17.246,76, contado una vez.
- **Lado cliente**: reproducido que los 1.957 efectos de `cob` con `fecbaj <> 0` (19,94 M€) están **todos en
  `est 1`**, y que el criterio de `pag` dejaría 229 / **2.122.847,33 €**. Queda sin cambios y explicado en la
  cabecera del SQL, la ficha `estado`, el orden de magnitud (SIN VERIFICAR) y el test
  `test_f094_cliente_conserva_el_estado_por_fecrea`. Acceptance 3 cumplido por su segunda rama.
- **Fase RED reproducida**: he copiado los dos tests nuevos a mi scratchpad junto al SQL y los YAML de `main`:
  **14 failed, 1 passed** (el de `VARCHAR`, que ya se cumplía), coherente con las trazas del informe.

## Vistas (`02_views.sql`) · BAJA no suma donde no debe

| vista | lectura de dinero | BAJA |
|---|---|---|
| `v_pbi_retencion_entidad` | `saldo_vivo`/`importe_liquidado` por estado; `neto_practicado`, `total_cargos`, `total_abonos` con `estado <> 'BAJA'`; vencidas por `vencida_sin_liquidar` | aparte, `num_bajas`/`importe_baja` al final |
| `v_pbi_retencion_resumen` | ídem; `neto_practicado` sin BAJA | aparte, al final |
| `v_pbi_retencion_obra` | solo `estado = 'VIVA'`/`'LIQUIDADA'` y `vencida_sin_liquidar` | nunca entra |
| `v_pbi_retenciones_vivas` | `WHERE estado = 'VIVA'` | nunca entra |
| `v_pbi_retenciones_vencidas` | `WHERE vencida_sin_liquidar` (que en PROVEEDOR exige lo mismo que VIVA, con `COALESCE(efe.est,0)`) | nunca entra |

`estado` es un CASE sin NULL con tres valores, así que `num_movimientos = num_vivas + num_liquidadas +
num_bajas` cuadra por construcción en entidad y resumen. Columnas nuevas al final: no se mueve ninguna posición.

## Obra (H6) y orden de pasos

- Cascada limpia: con centro manda `maestro.centros_coste` (único por construcción: `raw.cen` + `LATERAL … LIMIT 1`);
  sin centro, la obra única de las líneas. `codigo_obra`/`nombre_obra` salen del `con` de la MISMA obra por las
  dos ramas: la clave de tres columnas de la vista por obra ya no puede partir un `obra_id` (medido: 262 = 262).
- **Rotura para consumidores declarada**: en el informe («rompe a quien una `obra_id` … Power BI incluido»), en la
  propuesta de párrafo para `azure-apps/datamart_seg_anual.md` (tras la línea 447) y en el diccionario
  (`obra_id`, `centro_coste_id`, relación nueva y `cierre.yaml::centro_coste_ide`, que ya no se vende como pasarela).
- **Ningún otro SQL del repo** une `retenciones.*.obra_id` con un centro de coste: barrido de
  `retenciones\.(movimientos|v_pbi)` en todo el árbol; solo lo consumen `main.py inspect-retenciones*`, que filtran
  por `codigo_obra`, y el docstring histórico de `check-relaciones` (describe el defecto de F-006, sigue siendo cierto
  como historia).
- **Orden garantizado sin `depends_on`**: `test_f094_obra_maestros_corre_antes_que_retenciones` fija el orden
  topológico real de `build_pipeline_steps` y que NO se declare la dependencia. Razonamiento correcto: `maestro`
  depende de `build_stg`, y la vista es SQL sobre `raw` que ningún SQL dropea (lo he comprobado: no hay `DROP` en
  `sql/maestro/` ni `DROP SCHEMA maestro` en código). Queda escrito en el step y en `00_setup.sql`.

## Diccionario

`version` 25 → **26** con su changelog. Fichas nuevas: `estado` (tres valores y reglas por sentido),
`estado_sigrid`, `fecha_baja`, `centro_coste_id`, `num_bajas`, `importe_baja`; reescritas `obra_id`, `importe`
(«un SUM de toda la tabla NO es el neto»), `neto_practicado`, `total_*`. Relaciones: `obra_id → maestro.obras`
(N:1) y `centro_coste_id → maestro.centros_coste` (N:1) sustituyen a la N:N por `cierre…centro_coste_ide`. Orden de
magnitud 34.700.000 → **8.350.000** con fuente medida; cliente marcado SIN VERIFICAR. Puertas F-006 de `init.sh`:
ver C1. Los dos tests de F-006 ajustados **no aflojan**: el de fichas sigue exigiendo los tres hechos («NO es la
obra», «0 de 261», por dónde se traduce) en la columna donde hoy son ciertos, más «262 de 262» y el veto del «98»;
el de reglas sigue exigiendo dos órdenes de saldo vivo con su criterio.

**Observación (no bloquea):** la cadena «34,7 M€» sigue en el `fuente` publicado de `00_global.yaml:746`, pero
como el error que fue («Hasta F-094 aquí ponía 34,7 M€ … una cifra del orden de 35 M€ es ese error»), no como
orden de magnitud. Leo el acceptance 4 como «deja de servirse como cifra válida», y eso se cumple (el valor ya no
está y lo vigila `test_f094_la_cifra_inflada_sale_del_diccionario`). Si el humano lo quiere literal, basta con
quitar el número de esa frase y dejar la advertencia del «orden de 35 M€».

## Checkpoints

**C1** — [x] init.sh exit 0 · [x] ficheros base.
**C2** — [x] una sola `in_progress` (F-094) · [x] rama `feature/F-094-retenciones-estado-vivo` · [x] `current.md`:
es un registro rodante del proyecto con secciones de sesiones previas desde mucho antes de F-094; F-094 añade la
suya arriba y no introduce restos · [x] features `done` con su resumen (F-094 no se cierra aquí).
**C3** — [x] hexagonal: SQL en `sql/retenciones/` con `NN_nombre.sql`, el step solo cambia un comentario ·
[x] primera línea con ruta en todo lo nuevo · [x] sin prints, TODOs, secretos ni dependencias nuevas (las
mediciones leen el `.env` en tiempo de ejecución y viven en el scratchpad) · [x] semántica Sigrid: no toca
ámbito/fase ni importes origen/mes; la trampa propia (ficha del EFECTO `p.ide` frente a la del documento
`p.conide`, y centro ≠ obra) está resuelta y documentada.
**C3 bis** — N/A: no toca `docs/referencia/`.
**C4** — [x] cada acceptance con test (tabla abajo) y en verde · [x] los tests no tocan red ni BBDD (texto SQL, YAML
y `build_pipeline_steps` con `SimpleNamespace`) · **[ ] las verificaciones MANUAL (humano) NO están en
`progress/current.md`**: solo en `impl_F-094.md`. Ver cambio 1 · [x] dobles contra el original: puerta automática de
`init.sh`; F-094 no añade dobles.
**C4 bis** — [x] rigor `estandar` declarado · [x] fase RED con trazas reales, y reproducida por mí · [x] cobertura:
PUERTA COBERTURA en init.sh (ver C1) · [x] mutación, **N/A justificado**: la campaña genera **0 mutantes** y es un cero
legítimo. Recalculado: `harness.alcance.alcance_de_feature('F-094')` da como único Python de producción
`build_retenciones_step.py` líneas 81–87 (comentario), y `generar_mutantes` sobre ellas da **0**; **prueba de
control** sobre el fichero entero ignorando el alcance: **12** mutantes, así que el generador funciona. El cambio real
es SQL/YAML, fuera del alcance de la herramienta; la evidencia sustitutiva es la medición del SELECT nuevo (que he
reproducido) y 16 tests que fijan el texto EXACTO de cada CASE, así que cualquier cambio de operador o de literal en
ellos cae · N/A (sin informe de mutación): la regla de 60 s, el coste por mutante, la cabecera de campaña no válida,
RM1 y RM2 no tienen campaña sobre la que aplicarse · N/A RM5, por nivel `estandar` · N/A RM6: no se quitó código
defensivo (se añadió `COALESCE(efe.est, 0)`) · N/A campaña MANUAL: no se sustituyó por una · N/A supervivientes: no
hay · [x] sección «Evidencias» con tests, cobertura, mutantes y tiempo de suite · [x] ningún N/A sin motivo.
**C4 ter** — N/A: el repositorio no declara `harness/rutas_sensibles.json` (solo existe el `.ejemplo.json`).
**C5** — N/A `tasks.md` (sdd=false); commits `F-094 Tn: …` T0–T4 · [x] árbol limpio, sin temporales (mis scripts
están en el scratchpad) · [x] `features.json` en `in_progress`, que es el estado real.

## Trazabilidad acceptance → test

| acceptance | tests |
|---|---|
| 1 · no VIVA con `fecbaj`/`est` pagado-agrupado; criterio en SQL y ficha | `test_f094_proveedor_une_la_ficha_con_del_propio_efecto`, `…_el_estado_mira_fecbaj_y_est`, `…_tres_estados_y_baja_manda`, `…_vencida_solo_si_viva`, `…_la_ficha_declara_baja_y_las_columnas_nuevas`, `…_el_neto_y_los_cargos_excluyen_baja` |
| 2 · FERMALUX 64.201,96 y ~8,35 M€ | medición reproducida por mí (arriba); `test_f006_r10_las_cifras_de_retencion_son_de_saldo_vivo_y_lo_dicen` fija el 8.350.000. Las cifras sobre la tabla construida son MANUAL |
| 3 · lado cliente medido | `test_f094_cliente_conserva_el_estado_por_fecrea` + medición reproducida |
| 4 · 34,7 M€ fuera; unicidad y relaciones | `test_f094_la_cifra_inflada_sale_del_diccionario`, `test_f094_obra_la_ficha_declara_el_cruce_real_con_obras`, `test_f006_r2_retenciones_avisa_de_que_su_obra_id_no_es_la_obra`; unicidad medida (27.869 = 27.869) y relación medida (262/262); `check-unicidad`/`check-relaciones` sobre la tabla construida son MANUAL |
| H6 · obra real | `test_f094_obra_*` (6) |

## Cambios requeridos

1. **`progress/current.md`, sección «F-094 · IMPLEMENTADA, PENDIENTE DE REVIEW»**: añadir las verificaciones
   `MANUAL (humano)` con su comando exacto y **en su orden** (C4), copiadas de `progress/impl_F-094.md` §«Verificaciones
   MANUAL pendientes»: `python main.py build-retenciones` → `check-unicidad` → `check-relaciones` →
   `publicar-diccionario`, las cuatro consultas de contraste con su resultado esperado, la comprobación por MCP de
   que la versión 26 ya no sirve 34,7 M€ (reinicio del MCP por su caché) y la aplicación del párrafo propuesto a
   `azure-apps/datamart_seg_anual.md`. Es donde las lee el líder y el humano, y dos de ellas son las que cierran el
   acceptance 4: sin ellas en `current.md`, el orden build → checks → publicar (con la relación nueva, un
   `check-relaciones` antes del build sale KO) se pierde.

Nada más. El SQL, las vistas, el diccionario y los tests quedan aprobados tal cual; la pasada 2 puede ser
incremental desde `a7e647c`.
