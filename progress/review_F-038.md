<!-- progress/review_F-038.md -->
Revisión incremental desde ada7bec (Fase 2 · pasada 2): delta `ada7bec..c80181f` (`c96dfa9`, `1023052`, `c80181f`; `dcd7f3d` es F-125, del líder); la pasada 1 revisó entera `e9c5507..ada7bec`

# F-038 · Review · Fase 2 · líneas, objetivo y firmas

**Veredicto: APPROVED** (Fase 2, pasada 2). Los tres cambios de la pasada 1
están hechos, y las cifras que el implementer declara las he reproducido en
Azure, una a una.

**Fase 1**: APPROVED (pasadas 1 y 2), mergeada (`dda0dc5`) y desplegada. Su
review, íntegra, en `progress/review_F-038_fase1.md`. La pasada 1 de la Fase 2,
íntegra, en el commit `4ff5229` (`git show 4ff5229:progress/review_F-038.md`);
aquí va resumida para caber en el tope de 140 líneas.

**Rigor:** `estandar`, declarado: fase RED, cobertura ≥ 80 % y mutación.

## Pasada 2 · delta `ada7bec..c80181f`

- **Ficheros**: `09_comparativos_detalle.sql`, `compras.yaml`, dos tests de
  F-038, el script y el informe de la campaña SQL, `impl`, `current.md`. Ni el
  dominio ni el step cambian desde `d2d1d34` (`git diff --stat` vacío): la
  campaña del arnés (13/13) sigue valiendo (RM1). `features.json` y
  `BACKLOG.md` solo ganan F-125 (`dcd7f3d`, el líder a petición del humano):
  la entrada de F-038 no cambia.
- **Cambio 1, hecho.** `con_descompuesto` es ahora un `EXISTS` sobre
  `descompuestos.lineas` de su obra y partida **sin** filtro de versión
  (`09:181-190`): NULL solo sin descompuesto en ninguna; el resto que no casa,
  falso. Ficha de `casa_base` y su test nuevo
  (`test_f038_r30_casa_base_nulo_solo_sin_descompuesto_en_ninguna_version`).
- **Cambio 2, hecho según la decisión del humano** («primero a y si no b»,
  2026-10-05): `elemento` ordena `c.casa DESC, c.por_dncpro DESC, c.orden`
  (`09:161`). Dentro de la versión: el de igual `dncpro_id` si casa; si no, el
  que case por precio; si ninguno, el de igual `dncpro_id` sin casar. El orden
  entre versiones (`elegida`) no cambia: nunca una posterior. Citada en `impl`
  §2.3, en `current.md` y en la cabecera de la CTE.
- **Cambio 3, hecho.** Las fichas de `comparativo_oferta_lineas` y
  `comparativo_objetivo` dan la cifra medida con la regla publicada y separan
  la previsión de la spec; la MANUAL 4 separa cierto / falso / NULL y la T25
  espera la 962172 falso, sin base.
- **Reproducido en Azure, SOLO LECTURA** (`psycopg` directo,
  `transaction_read_only = on`, sin el cliente del ETL; el SQL de `c80181f` con
  la temporal como CTE y `fn_porcentaje_dto` en línea; 89 s):

| `base_regla` · `casa_base` | líneas | informe |
|---|---|---|
| ABC · cierto con la ABC | 11.409 | 11.409 |
| ABC · cierto con anterior | 5.468 (4.982 PRE_ABC + 473 MASTER_ESTUDIO + 13 ESTUDIO) | 5.468 |
| ESTUDIOS · cierto | 7.548 (7.463 + 85) | 7.548 |
| **Total cierto** | **24.425 de 84.084 (29,0 %)** | 24.425 |
| falso | 59.570 (ABC 24.752, de ellas 4.382 con base ABC; ESTUDIOS 34.818) | 59.570 |
| NULL | 89 (83 + 6) | 89 |

  Coincide todo. «Con la ABC» y «anterior» dan exactamente la previsión de la
  spec: la regla decidida es la que midió el spec-author.
- **Ejemplos**: A1 `ABC v3` 3.482, A2 `ABC v4` 131.926,58, B1 y B2
  `MASTER_PRE_ABC v2` (10,80 y 98): cierto. C1 (las seis líneas del
  comparativo) y C2 `ABC v3` 4,20: falso; nunca la posterior. 0696: 939265 y
  952250 `ABC v3` 69,70 cierto; **962172 falso**, sin base: lo que espera la T25.
- **Tests**: los dos de SQL cambiados siguen la decisión y son igual de
  estrictos (texto exacto del `ORDER BY` y del `EXISTS`, más «`candidatas`
  no aparece en `con_descompuesto`»); los de ficha solo añaden frases. Fase
  RED de los nuevos con su traza en `impl` §7. Nada se rebaja.
- **Campaña SQL 27/27**, reproducida en un worktree desechable de HEAD
  (borrado; `git status` limpio), base 68 passed: **M36** (la regla de antes)
  **→ 1 fallo, M50 → 1, M51** (el NULL de antes) **→ 1**, como la tabla.
- **`bash harness/init.sh`** relanzado entero sobre HEAD: ver C1.

## Pasada 1 · resumen (íntegra en `4ff5229`)

- Lo que sigue valiendo, verificado entonces y no tocado por el delta:
  `EXPLAIN` de los SELECT de `09` en Azure OK (columnas y tipos); paridad del
  `dto` SQL ↔ `parse_porcentaje_dto` sobre 453 textos y 786.864 líneas, **0
  discrepancias**; D4 en el SQL (nunca posterior, sin ABC solo Estudios,
  desempate `casa DESC, fase_num DESC`); desviaciones 1, 2 y 5-9 aceptadas (la
  5, temporal y transacción única, comprobada en `postgres_client.py:666-684` y
  `1454-1456`); lector cruzado de `descompuestos` declarado en cuatro sitios;
  `comparativo_firmas` con los reenvíos como filas y F-085 fuera; los tests de
  F-047, F-073, F-079, F-080, F-123 y `R-SIGRID-CON` no rebajan nada.
- Mutación del arnés recalculada (3.665 s, > 60 s, no reejecutada): 84 líneas y
  13 mutantes, como el informe; RM1, RM2, RM3 y RM6 OK. M47 de la SQL es
  equivalente en ejecución y muere porque el test fija el texto: límite
  declarado por el propio informe, no bloquea.
- Los tres cambios que pidió: los de arriba.

## Checkpoints

**C1** [x] `bash harness/init.sh` sobre `c80181f`: **ENTORNO LISTO, exit 0**,
6.795 passed, 227 skipped (2.001 s), cobertura `[OK]` 14/14, tamaño review
129/140 · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` (F-125 entra `pending`) · [x] rama
`feature/F-038-comparativos` · [x] `current.md` es el estado real · [x]
`history.md`: no aplica aún.
**C3** [x] hexagonal (dominio solo `re`/`Decimal`; SQL en `sql/compras/09_…`)
· [x] primera línea con la ruta · [x] sin `print` de depuración, secretos ni
dependencias · [x] semántica: `casa_base` NULL es «sin descompuesto» y
«no casa» es falso, como decide la spec.
**C3 bis** N/A: no toca `docs/referencia/`. **C4 ter** N/A: sin `rutas_sensibles.json`.
**C4** [x] R25-R35 con `test_f038_rN_*` en verde; R36 MANUAL por naturaleza
(T22) · [x] sin red ni BBDD · [x] MANUAL en orden, con comando y con las cifras
que el SQL da · [x] ningún doble nuevo.
**C4 bis** [x] rigor declarado · [x] RED con traza real (T11-T17 y los tests
nuevos de la review) · [x] cobertura `[OK]` 14/14 · [x] alcance y mutantes
recalculados · [x] > 60 s: recálculo y filas SQL reproducidas (M33, M36, M47
en la pasada 1; M36, M50, M51 ahora) · [x] coste por mutante coherente · [x]
sin «CAMPAÑA NO VÁLIDA», «Sin veredicto» 0 · [x] RM1 · [x] RM2 · N/A RM5:
`estandar`, sin supervivientes · [x] RM6 · [x] SQL manual con línea, texto y nº
de fallos · N/A análisis de supervivientes: no hay · [x] «Evidencias» con
workers · [x] ningún N/A sin motivo.
**C5** [x] T11-T19 `[x]`, commits `F-038 T11`…`T19` y los de la review · [x]
árbol limpio · [x] `features.json` refleja el estado real.

## Cobertura requisito → test (`tests/test_f038_*.py`)

R25 `r25_lineas_*` (3) · R26 `r26_*` (4, + F-047) · R27 `r27_*` (7) + mi
paridad real · R28 `r28_*` (2) · R29 `r29_*` (9) · R30 `r30_*` (6) · R31
`r31_*` (7) · R32 `r32_lineas_*` · R33 `r33_*` (5) · R34 `r34_*` · R35
`r35_*` (3) · R36 MANUAL T22.

## Cambios requeridos

Ninguno. Faltan las MANUAL del humano (T20-T25 en `current.md`).

## Para el líder y el humano (no bloquea)

- La regla deja **59.570 líneas «no casa»**; las fichas dicen que no es error
  del dato y que Negocio puede ampliarla (versión vigente al hacer el
  comparativo).
- **Automejora (propuesta, no aplicada)** de RM3 en `reviewer.md`: «en una
  campaña MANUAL cuyos tests fijan el TEXTO del SQL, un equivalente muerto no
  invalida la campaña: se anota como límite». M47 lo enseña.
