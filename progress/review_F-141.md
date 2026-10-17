<!-- progress/review_F-141.md -->
Revisión completa (pasada 1), `git diff main...HEAD` sobre `9757337` (merge-base `1672383`)

# F-141 · Review del perfil RESTRINGIDO del MCP

**Veredicto: CHANGES_REQUESTED** — solo por evidencia de cierre: ni una línea de código. El
código, el SQL, el diccionario y los tests están bien; faltan la ACEPTACIÓN del humano de los
tres equivalentes (rigor `critico`) y la lista de MANUAL con su comando en `current.md` (C4).

**Nivel de rigor: `critico`** (declarado en `harness/features.json`). Exige fase RED, cobertura
de lo cambiado ≥ 80 %, campaña COMPLETA con cero supervivientes salvo justificación escrita
ACEPTADA POR EL HUMANO, RM1-RM6 y las MANUAL listadas con su comando exacto.

## Verificación propia (no del informe)
- **`bash harness/init.sh`** (tal cual), 3.ª pasada: **exit 0, `8225 passed, 249 skipped`** (16 min 48 s). Las dos primeras
  cayeron por ESTE informe (borrador de 146 líneas; luego un patrón citado en el barrido).
- **Fase RED reproducida**: `tests/test_f141_perfil_restringido.py` de HEAD sobre una copia de
  `386da30` (la spec, sin código) → `116 failed, 20 passed, 3 skipped`. Los que pasan son hechos
  del árbol previos (las tres excepciones ya leían la cartera), como dice el informe §3.
- **Mutación, recálculo puro** (`harness.alcance` + `generar_mutantes`): 6 ficheros, **752
  líneas, 56 mutantes**, igual que el informe. Los 4 supervivientes existen tal cual (operador
  `entero`, mismo texto original → mutado). Campaña NO reejecutada: 14.715,6 s según el informe.
- **RM4 sobre una copia** (scratchpad): el superviviente 4 (`postgres_client.py:1633`,
  `split(".", 1)[0]` → `[1]`) aplicado a mano → `test_f141_cliente_apply_perfil_restringido_
  anota_lo_revocado` FALLA (1 failed, 10 passed): cerrado de verdad.
- **RM5, muestra de UNO** (el 2, `grants.py:426`): `s.split(".", 1)[0] == s.split(".", 2)[0]`
  para las 1.093 cadenas de longitud ≤ 6 sobre `{a, ., b}` y 100.000 aleatorias: equivalente.
- **Barrido de secretos** sobre las líneas añadidas del diff y el commit `a520a62` de
  `azure-apps` (GUID, `@dominio`, IPv4, asignaciones de contraseña, `AccountKey`, `sv=20`, `Bearer`):
  **cero**. Solo aparece `C:/Users/<usuario-windows>/...` en las líneas base de
  `mutacion_F-141.md` (lo escribe la herramienta; 27 informes de `main` igual): observación 4.
- **R24** con `git grep` fuera de `progress/`, `specs/`, `features.json`, `BACKLOG.md`: solo
  `settings.py:155` (la constante de la guarda R3), el renombre de `02_roles.sql` (122-131) y
  el test. Conforme.
- **Lo que pidió el líder**: el restringido NO ve `contabilidad.mayor` ni `saldos_cuenta_mes`
  (excluidos, `REVOKE ALL` en la misma transacción que el `GRANT ... ALL TABLES`: sin ventana),
  ni `personal` ni `tesoreria` (fuera de `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS` y vetados desde el
  CATÁLOGO); SÍ `compras` entero, con `vencimientos`, `v_facturas_pago` y `v_control_forma_pago`
  como excepción NOMINAL por esquema (`tesoreria`): si una alcanza otra cosa, es filtración (test
  r13). Ninguna vista ni tabla visible lee `contabilidad.mayor`, `saldos_cuenta_mes` ni
  `personal` en `sql/` (las de `contabilidad` y `tesoreria` son TABLAS; `apuntes_contables`
  sale de `raw.apu`). Renombre a `sigrid_dm_autorizado_ro` en código, SQL, tests, diccionario y
  `azure-apps`.

## Checkpoints

**C1** [x] `init.sh` exit 0 (arriba) · [x] los siete ficheros base existen.

**C2** [x] ninguna feature `in_progress` (ver observación 1) · [x] rama
`feature/F-141-perfil-restringido` · [x] `current.md` con la sesión de F-141 arriba; los
bloques de F-139 son de su cierre bloqueado aún vivo · [x] las `done` tienen resumen.

**C3** [x] hexagonal: guardas y orquestación en `application/`, SQL de catálogo y sentencias en
`infrastructure/postgres/`, constantes puras en `grants.py`; sin dominio nuevo · [x] primera
línea con ruta en los ficheros tocados · [x] sin `print`, `TODO` ni secretos; sin dependencias
nuevas · [x] semántica Sigrid: no toca SQL de capas (solo permisos).

**C3 bis** N/A: no añade ni cambia nada en `docs/referencia/`.

**C4** [x] los 30 requisitos automatizables (R1-R30) con test `test_f141_rN_*` en verde; R12
dentro de `r11_r12_camino_normal` y `r13_..._sale_del_catalogo`; R31-R34 son MANUAL (T15-T16)
· [x] sin red ni BBDD (cliente falso y conexión simulada; el PG16 real de T11 fue aparte) ·
**[ ] MANUAL en `current.md` con su comando exacto**: solo dice «T14-T17 son MANUALES: runbook
§13», sin comandos (cambio 2; mismo motivo que la pasada 1 de F-037) · [x] dobles: los métodos
de `_ClienteFalso` existen todos en `PostgresClient` con la misma aridad, y la puerta de dobles
de `init.sh` sale en verde.

**C4 bis** [x] `rigor: critico` declarado · [x] **fase RED** con traza real por tarea (informe
§3) y reproducida por mí · [x] **cobertura** `[OK] 100.0% de 227 líneas (227/227)` · [x] **mutación**: informe de la
herramienta, totales recalculados (752/56) · [x] muertos: campaña de más de 60 s, no
reejecutada; recálculo puro + RM4 del superviviente 4 · [x] coste por mutante 14.715,6 × 3 ÷
56 = 788 s, frente a una base de ~1.150 s: plausible con `-x` y 52/56 muertos · [x] sin
«⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto (base rota)» = 0, base medida en los tres workers ·
[x] **RM1**: medido sobre `557295c` (SHA completo); de ahí a HEAD solo cambian `tests/`,
`progress/` y `tasks.md`, y el recálculo sobre HEAD da el mismo alcance · [x] **RM2**: media
262,8 s × 3 workers = 788 s ≈ 0,7 × base; 56 × 262,8 = 14.717 ≈ 14.715,6 · [x] **RM3**:
revisé los 52 muertos y ninguno es equivalente (`frozen`/`slots` los mata el barrido de F-006;
`-=` sobre listas da `TypeError`; los `[1]` cambian el índice; los `or`/`and` cambian la
condición) · [x] **RM5**: los tres declarados equivalentes lo son (muestra de UNO reproducida)
· **[ ] cero supervivientes sin justificación ACEPTADA POR EL HUMANO**: los supervivientes 1-3
dicen «pendientes de aceptación del humano» en `mutacion_F-141.md` y en `current.md:16`
(cambio 1). Mi verificación sustenta la justificación; aceptarla no me toca · [x] **RM6**: no
se quitó ninguna guarda para matar un mutante · [x] análisis completos, ninguno en
`PENDIENTE` · [x] «Evidencias» con los cuatro números y los workers (informe §6) · [x] ningún
N/A sin motivo.

**C5** [x] T1-T13 `[x]` con un commit `F-141 Tn:` cada una (T14-T17 son MANUAL tras el merge,
no exigibles ahora) · [x] árbol limpio tras mi revisión (copias en el scratchpad).

## Cobertura requisito → test

| Req. | Test (todos en `tests/test_f141_perfil_restringido.py`) |
|---|---|
| R1-R2 | `test_f141_r1_*` (7), `test_f141_r2_*` |
| R3-R8 | `r3_*` (3), `r4_*` (3), `r5_*` (2), `r6_*`, `r7_*`, `r8_*` (2), `r3_r8_sin_rol_estandar…`, `r4_r8_sin_grupo…` |
| R9-R10 | `r9_*` (2), `r10_*` (2) |
| R11-R12 | `r11_build_*` (4), `r11_r12_camino_normal_en_orden_y_el_ultimo`, `r13_raw_no_es_filtracion_y_lo_no_suyo_sale_del_catalogo` |
| R13-R18 | `r13_*` (2), `r14_*` (2), `r15_*`, `r16_*`, `r17_*`, `r18_*` (3) |
| R19 | `r19_*` (3) y los tests de F-135/F-136/F-037/F-138 con solo el literal cambiado |
| R20-R23 | `r20_*` (3), `r21_*` (4), `r22_*` (4), `r23_comprobacion_final` |
| R24-R30 | `r24_*`, `r20_r24_*`, `r25_*` (4, con control sintético), `r26_*` (4), `r27_*` (3), `r28_*` (3), `r29_*` (2), `r30_*` (9) |
| R31-R34 | MANUAL (T15-T16, runbook §13 P6-P8) |

## Cambios requeridos

1. **La aceptación del humano de los supervivientes 1-3** (`grants.py:393`, `grants.py:426`,
   `postgres_client.py:1633`, `split(".", 1)[0]` → `split(".", 2)[0]`). El líder se la pide
   y se escribe, con fecha y sus palabras, en `progress/mutacion_F-141.md` (bajo cada
   «Decisión») y en `progress/current.md:16`, en lugar de «pendientes de aceptación». Sin
   tocar código ni repetir la campaña. Si el humano NO la acepta: `s.partition(".")[0]` en las
   tres líneas, y entonces sí campaña nueva (RM1: cambian ficheros del alcance).
2. **`progress/current.md`, sección de F-141: las MANUAL T14-T17 con su comando exacto**, como
   la de F-037: por tarea, el paso del runbook (§13 P0-P9) y la orden literal de lo que verifica
   cada requisito MANUAL: `infra/70_build_image.ps1` / `85_update_job.ps1 -Tag <tag>` / `az
   containerapp job show` (T14); `psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn`, la
   negativa R31, la positiva R32 y la huella R33 (T15); la consulta a `_meta.etl_runs` de R34
   (T16); la entrega del contrato E1-E8 (T17). Sin valores de secretos.

## Observaciones (no bloquean)

1. `harness/features.json` tiene F-141 en `spec_ready` aunque T1-T13 están hechas (`init.sh`:
   «en curso: ninguna»). Es del líder: pásala a `in_progress` o al estado que toque.
2. `main` ha avanzado (`b75a012`: `features.json`, `current.md`, `BACKLOG.md`): el merge
   chocará en esos tres. El diccionario sigue siendo v54 = v53 de `main` + 1 (R29 lo vigila).
3. `table_exists` (previo) no ve vistas MATERIALIZADAS: una excluida o que filtre lo sería
   «ausente» y no recibiría `REVOKE`; la postcondición la caza y el paso FALLA (con un mensaje
   que diría «ya revocada»). Hoy no hay ninguna en `sql/`.
4. `mutacion_F-141.md` lleva la ruta local con el usuario de Windows (la escribe la herramienta).
5. La clausura solo sigue dependencias sobre `pg_class` (una función `SECURITY DEFINER` no se
   vería) y `list_schemas` solo ve esquemas accesibles al ETL. Hoy sin casos; para §11.

## Automejora (propuesta al humano, no aplicada)

- `CHECKPOINTS.md` C4 bis (`critico`): el líder recoge la aceptación de los equivalentes ANTES
  de lanzar la review; aquí cuesta una pasada. `harness/mutacion.py`: ruta del worktree
  relativa (`wk_0`), sin el usuario del puesto.
