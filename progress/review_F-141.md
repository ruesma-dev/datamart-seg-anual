<!-- progress/review_F-141.md -->
Revisión incremental desde 9757337 (pasada 2): `git diff 9757337..3e177f3` (7766ea1 solo añade este informe)

# F-141 · Review del perfil RESTRINGIDO del MCP

**Veredicto (pasada 2): APPROVED.** Los dos cambios de la pasada 1 están resueltos y la
ampliación del 2026-10-17 (la ficha de `compras.documento_adjuntos` nombra `abrir_adjunto`)
es correcta, coincide con el contrato de `mcp-bbdd` y su test se refuerza, no se debilita.
Pasada 1 (CHANGES_REQUESTED, solo evidencia): `git show 7766ea1:progress/review_F-141.md`;
lo aprobado allí queda dado por bueno y aquí se resume.

**Nivel de rigor: `critico`** (declarado en `harness/features.json`). Exige fase RED, cobertura
de lo cambiado ≥ 80 %, campaña COMPLETA con cero supervivientes salvo justificación escrita
ACEPTADA POR EL HUMANO, RM1-RM6 y las MANUAL listadas con su comando exacto.

## Pasada 2 · qué cambió y qué verifiqué

Delta: `config/diccionario/compras.yaml` y `00_global.yaml` (texto de ficha, sin subir
versión), `tests/test_f139_limite.py` (R2), `harness/features.json` + `BACKLOG.md` (F-141 a
`in_progress`), `progress/` (current, impl, mutación). **Cero líneas de código de producción**:
el alcance medido por la campaña (`grants.py`, `postgres_client.py`, etc.) no cambia, así que
la mutación NO se repite (RM1: ningún fichero del alcance tocado desde `557295c`).

- **Cambio 1 resuelto**: «ACEPTADO por el humano el 2026-10-17 (…) «acepto»» bajo la
  «Decisión» de los supervivientes 1, 2 y 3 de `progress/mutacion_F-141.md`, en el §6 del
  informe y en `current.md`. El superviviente 4 sigue cerrado por su test (pasada 1, RM4).
- **Cambio 2 resuelto**: `progress/current.md`, «F-141 · Verificaciones MANUAL, con su
  comando exacto»: T14 (`70_build_image.ps1` → `85_update_job.ps1 -Tag` → `job show`), T15
  (P0-P7: vault, `02_roles.sql` con `ON_ERROR_STOP`, R31 con sus nueve negativas, R32 con sus
  positivas y el recuento de adjuntos, R33 con `Compare-Object` de la huella, `apply-grants`,
  `publicar-diccionario` y reinicio del MCP), T16 (la consulta R34 a `_meta.etl_runs` literal),
  T17 (E1-E8 con `git log -1 --stat a520a62`) y la vuelta atrás. Sin valores de secretos: la
  contraseña llega por el vault a una variable de entorno y se retira.
- **Ampliación, contenido**: el párrafo «EL LIMITE (F-139)» dice que la IA localiza el
  `adjunto_id` en el índice y abre el ORIGINAL con `abrir_adjunto(adjunto_id)` (F-023 de
  `mcp-bbdd`, 2026-10-17), SIN CONVERTIR, imágenes visibles y PDF/ofimática como binario
  (conversión = F-142), y que el permiso lo comprueba la herramienta con el login de quien
  pregunta según la regla «QUIEN PUEDE ABRIR EL FICHERO» (que existe, unas líneas abajo).
  Cotejado con `azure-apps/mcp_bbdd.md` (§2 líneas 196-207 y la verificación de 638-643): la
  firma, la fecha, el `LEFT JOIN` con el login del perfil antes de llamar a `sigrid-api` y
  «las imágenes las ve directamente, los PDF y la ofimática le llegan como binario». Conforme.
  Nada más del repositorio (config, docs, código) decía que la herramienta no existe.
- **Ampliación, test**: el viejo `..._no_afirma_que_la_herramienta_exista` prohibía el nombre;
  el nuevo `..._nombra_la_herramienta_desplegada` exige siete literales (firma, F-023, fecha,
  `adjunto_id` en el índice, imágenes, binario, la regla D1) y PROHÍBE «NO ESTA DESPLEGADA» y
  «ni el datamart ni el MCP abren» sobre la ficha entera. `..._declara_el_limite` solo pierde
  «NO ESTA DESPLEGADA», que ahora es lo prohibido. No es un debilitamiento: la aserción se
  invierte por un hecho nuevo aprobado y gana cobertura.
- **RED reproducida** (copia en el scratchpad, `git archive HEAD` con la ficha de `84830ee`):
  `test_f139_r2_la_ficha_nombra_la_herramienta_desplegada` FALLA (`1 failed, 14 passed`); con
  la ficha de HEAD, `15 passed`. Y reintroduciendo «NO ESTA DESPLEGADA» en la ficha de HEAD,
  vuelve a fallar: la prohibición muerde.
- **`bash harness/init.sh`** (tal cual) sobre `3e177f3`: **exit 0, `8225 passed, 249
  skipped`** en 2.629 s (máquina cargada), `PUERTA COBERTURA [OK] 100.0% de 227 líneas`,
  `PUERTA TAMAÑO [OK]`, `ENTORNO LISTO`. Con este informe ya escrito repetí lo que lo lee:
  `python -m harness.tamano --feature F-141` y los diez ficheros de tests que leen `progress/`: tamaño `review 134/140`, `409 passed`.
- **Barrido de secretos** del delta: sin GUID, IP, dominio, contraseña ni clave. La orden de
  T17 lleva la ruta local de `azure-apps` con el usuario del puesto, como otras cinco de
  `current.md` (observación 4 de la pasada 1: no es secreto).

## Pasada 1 · verificación propia (resumen; detalle en `7766ea1`)

- Fase RED de los 30 requisitos automatizables reproducida sobre `386da30`: 116 failed.
- Mutación: recálculo puro 6 ficheros / 752 líneas / 56 mutantes = el informe; campaña NO
  reejecutada (14.715,6 s según el informe); RM2 coherente (788 s por mutante frente a una
  base de ~1.150 s con `-x` y 52/56 muertos); RM3: ningún muerto equivalente; RM4 del
  superviviente 4 sobre una copia (falla su test); RM5 con muestra de UNO (el 2,
  `split(".", 1)[0] ≡ split(".", 2)[0]`, 101.093 cadenas); RM6: ninguna guarda quitada.
- Lo pedido por el líder: el restringido no ve `contabilidad.mayor`, `saldos_cuenta_mes`,
  `personal` ni `tesoreria` (salvo las tres vistas nominales de `compras`); sí `compras`
  entero. Renombre a `sigrid_dm_autorizado_ro` en código, SQL, tests, diccionario y `azure-apps`.

## Checkpoints (estado a la pasada 2)

**C1** [x] `init.sh` exit 0 (arriba) · [x] los siete ficheros base existen.

**C2** [x] una sola `in_progress`: F-141 (observación 1 de la pasada 1, resuelta) · [x] rama
`feature/F-141-perfil-restringido` · [x] `current.md` con F-141 arriba · [x] las `done`
tienen resumen.

**C3** [x] hexagonal (pasada 1; el delta no toca código) · [x] primera línea con ruta · [x]
sin `print`, `TODO` ni secretos; sin dependencias nuevas · [x] semántica Sigrid: solo
permisos y texto de ficha.

**C3 bis** N/A: no añade ni cambia nada en `docs/referencia/`.

**C4** [x] R1-R30 con test `test_f141_rN_*` en verde, y R2 de F-139 ajustado a la ampliación
· [x] sin red ni BBDD · [x] **MANUAL en `current.md` con su comando exacto** (T14-T17,
resuelto) · [x] dobles: puerta de `init.sh` en verde.

**C4 bis** [x] `rigor: critico` · [x] fase RED (informe §3 y §5 bis, reproducidas) · [x]
cobertura `[OK] 100.0% de 227 líneas` · [x] mutación de la herramienta, totales recalculados
(752/56) · [x] muertos: campaña > 60 s, no reejecutada; recálculo puro + RM4 · [x] sin
«⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto (base rota)» = 0 · [x] RM1 (el delta no toca el
alcance) · [x] RM2 · [x] RM3 · [x] RM5 · [x] **cero supervivientes sin justificación
ACEPTADA POR EL HUMANO** (1-3 aceptados el 2026-10-17; 4 cerrado con test) · [x] RM6 · [x]
ningún análisis en `PENDIENTE` · [x] «Evidencias» con los cuatro números · [x] ningún N/A
sin motivo.

**C5** [x] T1-T13 `[x]` con commit `F-141 Tn:` cada una; T14-T17 son MANUAL tras el merge ·
[x] árbol limpio tras mi revisión (copias en el scratchpad).

## Cobertura requisito → test

| Req. | Test (en `tests/test_f141_perfil_restringido.py` salvo indicación) |
|---|---|
| R1-R10 | `r1_*` (7), `r2_*`, `r3_*`-`r8_*` (13 + 2 cruzados), `r9_*` (2), `r10_*` (2) |
| R11-R18 | `r11_build_*` (4), `r11_r12_camino_normal_…`, `r13_*` (3), `r14_*`-`r18_*` (8) |
| R19-R23 | `r19_*` (3) y F-135/F-136/F-037/F-138, `r20_*`-`r22_*` (11), `r23_comprobacion_final` |
| R24-R30 | `r24_*`, `r20_r24_*`, `r25_*` (4), `r26_*` (4), `r27_*` (3), `r28_*` (3), `r29_*` (2), `r30_*` (9) |
| Ampliación (ficha) | `tests/test_f139_limite.py::test_f139_r2_la_ficha_nombra_la_herramienta_desplegada` y `..._declara_el_limite` |
| R31-R34 | MANUAL (T15-T16, `current.md` y runbook §13 P6-P8) |

## Cambios requeridos

Ninguno.

## Observaciones (no bloquean)

1. `azure-apps/datamart_seg_anual.md:1303` («Qué rompe este proyecto a otros») aún dice «la
   futura `abrir_adjunto`». El documento es de este proyecto: quitar «futura» en el próximo
   trabajo que lo toque (o en el cierre de F-141, junto con su push).
2. `main` avanzó a `98ad9b7` (`BACKLOG.md`, `features.json`, `current.md`, `history.md`): el
   merge chocará en esos ficheros, no en el diccionario. v54 = v53 de `main` + 1 (R29).
3. Siguen las 3-5 de la pasada 1 (vistas materializadas en `table_exists`, ruta local en
   `mutacion_F-141.md`, la clausura sobre `pg_class`): hoy sin casos.

## Automejora (propuesta al humano, no aplicada)

- `CHECKPOINTS.md` C4 bis (`critico`): el líder recoge la aceptación de los equivalentes ANTES
  de lanzar la review; aquí costó una pasada. `harness/mutacion.py`: ruta del worktree
  relativa (`wk_0`), sin el usuario del puesto.
- `reviewer.md`, revisión incremental: aclarar que tras un CHANGES_REQUESTED el SHA de
  partida es el último commit REVISADO (no hay «último aprobado»).
