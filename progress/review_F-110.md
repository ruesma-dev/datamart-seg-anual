Revisión completa (pasada 1) · `79a4505..5c4befb` (F-110 entera, desde el merge de F-108)
# F-110 · Review del reviewer (2026-09-26)

**Veredicto: APROBADO (APPROVED).**

**Rigor `critico`** (declarado): fase RED, cobertura >= 80 %, mutación con **0
supervivientes** y MANUAL listadas. Contra la spec, la sección «APROBADA» de
`progress/spec_F-110.md`, `docs/CONVENTIONS.md` y `CHECKPOINTS.md`.

## Lo que pidió el líder, punto por punto

1. **Orden garantía → último cuatrimestral + 1 → NULL** [x]. CTE `fin` de
   `05_fin_obra.sql:210-222`: dos `CASE` sin `ELSE`, `ultimo_cierre` ausente de
   `fin`, de `terminada_sin_fin_obra` y de `fecha_vencimiento`. El CTE
   `cierres` y la columna `ultimo_cierre` siguen (D5) y la ficha la rotula
   «INFORMATIVA desde F-110» (`retenciones.yaml:1382`).
2. **D2 con el ejemplo literal** [x]. CTE `plan`: `MAX(pm.anio_mes) FILTER
   (WHERE pm.importe_mes <> 0)` sobre la versión de `cuatrimestral`
   (`MAX(v.version)` con `tipo_master = 'Cuatrimestral'`), ámbitos 8 y 11.
   `test_f110_r5_ejemplo_del_humano` ejecuta los dos `INTERVAL` del SQL:
   2028-03-01 → 2028-04-30. Contraste mío por el MCP (solo lectura): `1-0686`
   v28, último mes con importe **2026-11-01**, última fila 2027-02-01 (cola a
   cero fuera); `1-0692` v4, 2025-02-01. Coincide con `impl_F-110.md`.
3. **D4 y la nocturna** [x]. `depends_on == ["ingest_raw"]` intacto. Orden real
   de `main.build_pipeline_steps` (l. 508-523): ingest, excel, **stg, mart**,
   maestros, compras, **retenciones**; el DFS de `_topological_sort` conserva
   ese orden y `test_f110_r16_orden_topologico` lo fija. Si `stg` o `mart`
   fallan, `run_all` solo salta los dependientes: `retenciones` corre con las
   tablas de la noche anterior (el `DROP` de `mart.master_versiones_tipadas`
   va en la transacción de `06_cp_tipologia.sql`; `stg.plan_mensual` es
   incremental, sin `TRUNCATE`). **La primera noche** las dos tablas ya existen
   en producción (build del 25). Si faltaran, la guarda falla antes del `DROP`.
4. **Guardas** [x]. Cuatro `RAISE 'fin_obra: ...'` antes del `DROP`; la de
   `cierre` vacía, retirada; la de existencia, conservada (l. 114-129).
5. **Diccionario versión 34** [x], con su línea de historia.
6. **Tests de F-095 reescritos sin aflojar** [x]. Los seis de T3 citan F-110 y
   se **endurecen**: `r21` pasa de «contiene `fin_obra`» a 4 × `'fin_obra: '`;
   `d7` pasa de `<= {raw, cierre}` a `== {raw, cierre, mart, stg}` y fija la
   única tabla de `mart` y de `stg`; `r19` añade `ULTIMO_CIERRE_MAS_1_MES` vetado;
   el contrato `CONTRATO_SQL` gana los CTE `cuatrimestral` y `plan` literales.
   `r18` intacto salvo el docstring. Ningún test borrado.
7. **Campaña de mutación** [x]: ver C4 bis. Muestra propia de 16, todos muertos.
8. **Sin nombres de persona** [x]: barrido del diff y de `azure-apps`, cero.
9. **`azure-apps`** [x]. Commit local `f087516` en `master`: fila de
   `retenciones.fin_obra`, lecturas nuevas, `cierre` solo informativa y sin
   fallo por tabla vacía, efecto para quien consume, versión 34. Sin push.

## Checkpoints

- **C1** [x]: `bash harness/init.sh` tal cual en `5c4befb`: **5.519 passed, 203
  skipped en 725 s**, COBERTURA **95,1 %** (1052/1106), TAMAÑO dentro de topes
  (req. 142/150, design 237/250, impl 194/220), **ENTORNO LISTO, exit 0**. Arnés
  completo.
- **C2** [x]: una sola `in_progress` (F-110), rama `feature/F-110-...`.
  `current.md` tiene la sección de F-110, pero sigue arrastrando ~2.150 líneas
  de sesiones cerradas: deuda previa del líder, ya anotada en el review de F-108.
- **C3** [x]: SQL en su capa (`retenciones/05`), mismo número; el step solo cambia
  docstring y comentario; primera línea con ruta en los ficheros nuevos; sin
  `print`, TODO, secretos ni dependencias nuevas; `ruff` limpio en lo tocado.
  Trampas Sigrid: ámbitos 8/11 (master) sin mezclar con 3/7; `version` es `fas`
  master (R-FAS-AMBIGUO) y se une por `obra_id` + `version`, sin sumar importes
  (R-VERSION-MASTER no aplica: solo se toma un `MAX` de mes).
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x]: R1-R23 trazables (tabla abajo), todo offline (`test_f110_r22`).
  Verificaciones MANUAL (T16-T18) en `current.md` §F-110, con los comandos
  exactos en `impl_F-110.md` §«Lo que falta» (enlazado desde `current.md`).
  Dobles: el único es el cliente falso de `test_f095_r21_un_fallo...`, que ya
  existía; F-110 solo cambia el texto del error.
- **C4 bis** — todos [x]:
  - [x] Rigor declarado: `critico`.
  - [x] **Fase RED**: traza real en `impl_F-110.md` (11 failed de los centrales,
    27/33 de la suite, 5 de F-095 en T3; T2 verde antes del SQL).
  - [x] **Cobertura**: `[OK]` 95,1 %.
  - [x] **Mutación, control del cero, recalculado por mí**:
    `alcance_de_feature('F-110')` → 1 fichero, 27 líneas (docstring y
    comentario del step), `generar_mutantes` → **0**; sobre el fichero entero →
    **12**, en las líneas 57, 149, 153, 156, 168, 171, 178, 179, 181, 185: idéntico
    a lo declarado. El cero es legítimo y la campaña manual lo sustituye.
  - [x] **Campaña manual reproducible**: una fila por mutante con fichero:línea,
    texto exacto original → mutado y nº de fallos (114 filas). **Reproduje
    cuatro al pie de la letra** sobre una copia (`git archive HEAD` +
    `azure-apps/datamart_seg_anual.md` al lado, mismo juez de 4 ficheros):
    #21 → 2 fallos, #69 → 3, #86 (S4) → 3, #97 (S15) → 2. **Los cuatro
    coinciden** con la tabla, y mi línea base da los mismos 146 tests.
  - [x] **Muestra independiente** (12 mutantes míos, fuera de la tabla): fuente
    por `version_cuatrimestral` en vez del mes (R6); `MIN` del mes; `GROUP BY`
    con `ambito_id` en `plan` y en `cuatrimestral`; literal `'cuatrimestral'`
    en la guarda; ámbitos 3/7 añadidos al plan; `FILTER` `IS NOT NULL`; guarda
    contra la vista `v_master_...`; `depends_on` con `build_stg`; «misma
    noche» → «noche anterior» en ARCHITECTURE; plan unido por `oc.obra_id`;
    `CASE` del fin con las ramas invertidas. **12/12 muertos** (1 a 4 fallos).
    97 s en total; árbol del repositorio intacto (`git status` limpio).
  - [x] **> 60 s**: la campaña declara 516,7 s, así que no se reejecutó
    entera; se aplicó recálculo puro + reproducción + muestra propia (arriba).
  - [x] **Coste por mutante**: 516,7 × 3 / 114 = **13,6 s**, dentro de la línea
    base declarada (11,1-18,0 s por copia). Coherente (RM2).
  - [x] **RM1**: SHA medido `5d06b28…`; desde ahí solo cambian `progress/` y
    `tasks.md`, nada del alcance. **RM2** coherente. **RM3**: ningún
    equivalente declarado. **RM5** N/A justificado: cero supervivientes, no hay
    equivalente que muestrear. **RM6** N/A justificado: se retira la guarda de
    `cierre` vacía por decisión escrita de spec (D5/R14), no para matar un
    mutante, y la de existencia se conserva.
  - [x] Sin «CAMPAÑA NO VÁLIDA», base en verde; 0 supervivientes, nada en
    `PENDIENTE`; «Evidencias» con los cuatro números y 3 workers.
- **C4 ter** N/A: el repositorio no declara `harness/rutas_sensibles.json` con
  rutas tocadas por esta feature (la puerta de `init.sh` no señaló ninguna).
- **C5** [x]: T0-T15 y T19 `[x]` con commits `F-110 Tn:`; T16-T18 abiertas por
  ser MANUAL (humano), como marca la spec. Sin temporales; `features.json` en
  `in_progress` hasta este veredicto.

## Cobertura requisito → test

| R | Test(s) |
|---|---|
| R1-R4 | `test_f110_r1_*`, `r2_*`, `r3_*`, `r4_*`; contrato `CONTRATO_SQL` de F-095 |
| R5-R7 | `test_f110_r5_*` (2, uno ejecuta el ejemplo), `r6_*`, `r7_*` |
| R8-R13 | `test_f110_r8_*`..`r13_*`, `r10_*` (2); `test_f095_r18/r19/r20_*` |
| R14-R17 | `test_f110_r14_*` (3), `r15_*`, `r16_orden_topologico`, `r17_*`; `test_f095_r21_*` (2) |
| R18-R20 | `test_f110_r18_*`, `r19_*`, `r20_*`; `test_f095_r28_*` |
| R21-R23 | `test_f110_r21_*` (6), `r22_*`, `r23_*` (2) |

## Observaciones (no bloquean)

1. **Riesgo latente de D1, medido hoy a cero.** `cuatrimestral` toma el
   `MAX(version)` entre los dos ámbitos y `plan` une ESE número en 8 y en 11. Si
   algún día un número fuera Cuatrimestral en un ámbito y otra cosa en el otro,
   el plan del otro ámbito entraría en el último mes. Medido por el MCP el
   2026-09-25: en las 117 obras la versión elegida existe en **los dos**
   ámbitos y es Cuatrimestral en ambos (234 filas, 0 discrepancias). Es la
   regla aprobada (D1); blindarlo sería una feature propia.
2. T16-T18 y el despliegue siguen MANUAL: sin imagen nueva, la nocturna aplica
   la regla vieja.

## Automejora (propuesta, no aplicada)

En campañas MANUALES (F-095, F-110), reproducir dos filas solo prueba las que
el implementer eligió generar. Propongo añadir a C4 bis, en rigor `critico`:
«el reviewer juzga además, sobre una copia, al menos cinco mutantes semánticos
propios que NO estén en la tabla, y anota el resultado».
