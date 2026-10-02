<!-- progress/review_F-120.md -->
Revisión incremental desde f6d5eae (pasada 2) · la pasada 1 fue completa sobre `main...f6d5eae`

# F-120 · Review · el factor del descompuesto

**Veredicto (pasada 2): APPROVED.** Los dos cambios requeridos están hechos, el
test ampliado estuvo en rojo antes del arreglo y no hay regresiones.

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de lo
cambiado y una campaña de mutación con los supervivientes analizados. RM5 es N/A
por nivel.

## Pasada 2 (delta `f6d5eae..6f33cb8`)

Commits: `10150b1` (líder), `4d935a7` (R1-1), `8b87306` (R1-2) y `6f33cb8` (R1-3).
El delta toca YAML, docs, tests y papeleo. **No toca Python de producción ni SQL**:
el alcance de mutación y la cobertura no cambian, y el sello sigue en
`7cad480aee614b2a` (recalculado con `sello_de_troceado()`). Nada de lo aprobado
en la pasada 1 queda invalidado.

- **Cambio 1, hecho.** En `00_global.yaml:1389`, `esquemas.descompuestos.para_que_sirve`
  dice ahora «La primera carga del master se hizo el 2026-09-29, con las 3.025
  versiones; que version esta cargada lo dice `_versiones_cargadas`». Barrí el
  contenido PUBLICADO (sin comentarios) de todos los `config/diccionario/*.yaml`
  buscando `INCOMPLET|primera carga`: **ningún aviso caducado**. Solo quedan
  usos ajenos (`compras`, `contabilidad`, `raw`, `stg`: «sello incompleto», «clase
  incompleta», «respuesta INCOMPLETA») y las frases nuevas con la fecha.
- **El test ampliado recorre todos los YAML**: `test_f120_r25_sin_el_aviso_caducado_*`
  aplica `glob("*.yaml")` sobre el contenido cargado y además exige la fecha y
  `_versiones_cargadas` en `esquemas.descompuestos`. **RED reproducida**: en un
  worktree temporal de `4d935a7`, con el `00_global.yaml` de `f6d5eae`, sale
  `1 failed`; con el de la rama, `1 passed`. Worktree borrado; árbol limpio.
- **Cambio 2, hecho (líder).** El `acceptance` 5 y R25 siguen la D7 aprobada:
  importe de Estudios = medición × precio de la v0, lo que vale es el
  descompuesto por unidad, MASTER_INICIAL solo donde la v0 guarda descompuesto.
  Ya no dice «foto fija».
- **Hallazgo 5, hecho.** `ARCHITECTURE.md:809` dice ahora «Sin la primera carga,
  la nocturna completaría… estaría INCOMPLETO; en producción la primera carga
  se hizo el 2026-09-29»: el referente queda claro y el tiempo verbal es correcto.
- **Hallazgo 6, hecho.** La cabecera de F-118 en `current.md` dice ya DESPLEGADA
  (`r20260930-1715`) y VERIFICADA el 01-10.
- **`bash harness/init.sh`**: ENTORNO LISTO, exit 0. **6.252 passed, 219
  skipped** (11 min 38 s). `PUERTA COBERTURA [OK] 100,0 %` (29/29). Tamaño [OK]
  (impl 219/220).
- **Siguen abiertos, no bloquean**: el hallazgo 3 (el cerrojo nocturno del
  `ALTER`, un patrón que ya existía) y el 4 (el equivalente 60 -> 61, aceptado).

## Pasada 1, resumen (detalle en `git show 10150b1:progress/review_F-120.md`)

Veredicto CHANGES_REQUESTED por: (1) el aviso caducado en `esquemas.descompuestos`
y (2) el `acceptance` 5 con la D7 vieja. Los dos están resueltos arriba.
Observaciones: (3) el `ADD COLUMN IF NOT EXISTS` toma `AccessExclusiveLock` sobre
`lineas` cada noche, incluso con la columna presente (medido en un PG16 local);
(4) `PRECISION_PRODUCTO` 60 -> 61 es equivalente en la práctica, no en sentido
estricto; (5) ARCHITECTURE; (6) la cabecera de F-118; (7) la nocturna publica
v39 sola, quizá antes de T16, y la ficha lo cubre.

Verificación propia de la pasada 1, sin escrituras en Azure:
- **RED reproducida**: worktree en `9769269` -> 99 failed, 3 passed, 1 skipped.
- **Azure en SOLO LECTURA**: `dncpro.factip` es `integer` y `faccan` `double
  precision`; `fn_trocear` no tiene dependientes y su ACL es la de por defecto;
  las 3.025 versiones llevan el sello `99f827a11969d59f`.
- **PG16 local desechable**: los 11 textos reales de la 400854 de la 0713 y 304
  registros sintéticos de casos límite -> `fn_trocear` frente a `trocear_des`,
  **506 registros, 0 diferencias** en las 19 columnas. **La v6 real tiene 9
  líneas con forma factor y suma 249,41**; la línea 13 da 1,22 × 0,003 × 339,39 =
  1,24. Sobre el estado de F-097, `DROP`+`CREATE` funciona y es repetible, y el
  `ALTER` deja `factor` la última en la tabla y en las tres vistas.
- **Mutación, recálculo puro**: 83 líneas y 9 mutantes, como el informe; el
  superviviente existe tal cual. Campaña no reejecutada: 2.180,6 s según el
  informe (> 60 s).

## Checkpoints (estado tras la pasada 2)

**C1** [x] init.sh exit 0 · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama de la feature · [x] la sección de
F-120 en `current.md` al día, y la cabecera de F-118 corregida (las secciones
antiguas son deuda previa que F-120 no amplía) · [x] `history.md` sin cambios
necesarios.
**C3** [x] hexagonal: el dominio solo usa stdlib y el SQL va en
`sql/descompuestos/NN_*` · [x] primera línea con ruta · [x] sin `print`, TODOs,
secretos ni dependencias nuevas. Barrido de IPs, GUID, `@`, `pwd=` y
`AccountKey`: solo falsos positivos · [x] semántica: no mezcla orígenes ni
versiones, `importe_total` no cambia, el factor del master sale del texto de cada
versión.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R27 con test `test_f120_rN_*` en verde (R28-R29 son MANUAL) · [x]
sin red ni BBDD · [x] T14-T18 en `current.md` con su comando, lo que debe salir y
el ORDEN OBLIGATORIO (imagen T14 antes que retroceo T16, con el porqué) · [x]
F-120 no añade dobles; la comprobación del árbol corre en la suite verde.
**C4 bis** [x] rigor declarado · [x] RED con traza real, reproducida en las dos
pasadas · [x] cobertura 100 % · [x] alcance y mutantes recalculados · [x] > 60 s:
recálculo puro, dicho arriba · [x] coste por mutante 2.180,6 × 2 / 9 = 484,6 s ·
[x] sin «CAMPAÑA NO VÁLIDA» y 0 sin veredicto · [x] RM1: SHA `68e1223`, y lo que
vino después no toca Python de producción · [x] RM2: 9 × 242,3 = 2.180,7, y
media × 2 = 484,6 s frente a una base de 370-373 s · N/A RM5: nivel `estandar` ·
[x] RM6: ninguna guarda quitada · N/A campaña manual: la automática dio 9 · [x]
el superviviente está analizado · [x] «Evidencias» con los workers (2) · [x]
ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T13 y T19 `[x]`, cada una con su commit `F-120 Tn:`, y las
correcciones en `F-120 R1-n` (T14-T18 son MANUAL) · [x] árbol limpio · [x]
`features.json`: el `acceptance` 5 ya sigue la D7 aprobada.

## Cobertura requisito -> test (`tests/test_f120_factor.py`)

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1-R5, R9 | `r1_r5_forma_del_campo_14`, `r2_*`…`r5_*`, `r9_*` | R14-R16 | `r14_r16_planif_jo_*`, `r15_factip_raro_*` |
| R6 | `r6_*` (5) | R17 | `r17_ddl_y_alter_*`, `r17_estudio_*`, `r17_master_*` |
| R7, R8 | `r7_importe_total_*`, `r8_porcentaje_*` | R18, R19 | `r18_*` (3 vistas), `r19_troceado_drop_*` |
| R10, R11 | `r10_*` (2), `r11_multiplica_*` | R20-R23 | `r20_*`, `r21_*`, `r22_*`, `r23_*` |
| R12, R13 | `r12_*` (2), `r13_la_400854_v6_*` | R24-R27 | `r24_*` (2), `r25_*` (2, uno sobre todos los YAML), `r26_*`, `r27_*` (2) |

## Cambios requeridos

Ninguno. Para cerrar faltan las MANUAL del humano, T14-T18, en su orden: primero
la imagen y comprobar el tag del job, luego la foto del cuadre, el retroceo con
`--sin-tope` + `apply-grants`, la 400854 v6 y la foto de después, y el diccionario
v39.

**Automejora (propuesta para `CHECKPOINTS.md` C3, no aplicada):** «un texto
retirado del diccionario se busca en todos los YAML, `esquemas` incluido». La
pasada 2 lo aplica ya en el test de F-120.
