<!-- progress/review_F-090.md -->
Revisión completa (pasada 1), diff `75389c5..335d671` (merge-base con `main`, la `RAMA_BASE`)

# F-090 · Review · el índice de documentos adjuntos de compras

**Veredicto: CHANGES_REQUESTED** (código y SQL bien; falla documentación que se consume
o que hace de evidencia: cinco cambios pequeños, abajo).

**Nivel de rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED,
cobertura de lo cambiado ≥ umbral y campaña de mutación con supervivientes analizados.

## Verificación ejecutada por el reviewer

- `bash harness/init.sh` sobre `335d671`: **7.268 passed, 231 skipped** (16 min 33 s),
  COBERTURA 100 % (28/28). Su único KO fue el tope de ESTE informe a medio escribir; ya
  recortado, `init.sh` se relanzó tras el commit (resultado en la línea de respuesta).
- Alcance y mutantes **recalculados** (`harness.alcance.alcance_de_feature` +
  `harness.mutacion.generar_mutantes`, cálculo puro): 132 líneas (20 en
  `build_compras_step.py`, 112 en `domain/documento_adjuntos.py`) y **8 mutantes**, todos
  en el dominio: las 5 claves de `FAMILIAS_ADJUNTOS` (15→16, 44→45, 46→47, 12→13, 14→15),
  `is None`→`is not None` en l. 80 y l. 89 y `group(1)`→`group(2)` en l. 83. Coincide con
  `progress/mutacion_F-090.md`. Control del cero en `build_compras_step.py`: el fichero
  entero sí genera 12 mutantes; en las 20 líneas del diff, 0 (solo añade un `_SubStep`
  de datos y docstring). Cero legítimo.
- **Campaña no reejecutada: 2.427 s según el informe** (> 60 s): recálculo puro + RM1-RM6.
- `ruff` sobre los ficheros nuevos: 1 aviso nuevo (cambio 5). `documents/read` leído en
  `azure-apps/sigrid_api.md` §8.3 y en el código de `sigrid-api` (cambio 1).

## Checkpoints

**C1** [x] `init.sh` en verde salvo el tope de este informe, ya corregido (arriba) · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` (F-090) · [x] rama `feature/F-090-documento-adjunto` ·
[ ] `current.md` describe SOLO la sesión activa: la sección de F-090 dice «Mutación NO
VÁLIDA … repetirla» (ya no es cierto) y sigue la sección «F-132 · FASE B … en curso»
junto a la de «F-132 · CERRADA» (cambio 3) · [x] F-132 `done` tiene su entrada en `history.md`.
**C3** [x] hexagonal: el dominio solo importa `re` y `typing`; el SQL en `sql/compras/` con
`14_`; el step solo añade datos · [x] primera línea con ruta en los 5 ficheros nuevos ·
[x] sin `print`, sin TODO, sin secretos (barrido de IPs, GUID y `password` en el diff:
solo `127.0.0.1` ficticio en el informe), sin dependencias nuevas (`pglast` quedó en el
scratchpad del implementer) · [x] semántica Sigrid: no toca `amb`/`fas` ni importes; el
grano lo defiende la PK `adjunto_id` = `rcg.ide`, y el `LEFT JOIN raw.comprv` no
multiplica porque `compras.comparativo_ofertas` ya declara PK `oferta_id` = `comprv.docide`.
**C3 bis** N/A: la feature no añade ni cambia nada en `docs/referencia/`.
**C4** [x] R1-R25 y R27 con test `test_f090_rN_*` (tabla abajo), 101 tests, pasan; R26,
R28, R29 son MANUAL · [x] sin red ni BBDD: YAML y SQL se leen como texto · [x] MANUAL con
comando exacto en `impl_F-090.md` §5 y `current.md` apunta ahí (criterio aceptado en F-085
y F-132) · [x] dobles: F-090 no crea ninguno; los dos tests ajustados de F-047 y F-132
usan los mismos dobles de antes, y la puerta de dobles de `init.sh` sale en verde.
**C4 bis** [x] `rigor` declarado · [x] **fase RED** con salida real de T1, T2, T4, T5 y
T6-T7 (`impl` §3) · [x] cobertura de lo cambiado 100 % (28/28), en la puerta de `init.sh` ·
[x] mutación: informe generado por la herramienta, totales verificados (arriba) ·
[x] muertos: campaña > 60 s, no reejecutada, dicho arriba · [x] coste por mutante =
2.427 × 4 / 8 = 1.213 s ≫ 1 s · [x] sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0 ·
[x] **RM1**: medida sobre `b88fdbb`; de ahí a HEAD solo cambia `progress/mutacion_F-090.md`
· [x] **RM2**: línea base ~710 s, media 303,4 s con 4 workers → 1.213 s reales por
mutante (más que la base por la contienda de 4 suites a la vez, mismo orden de magnitud)
y 8 × 303,4 = 2.427 cuadra · [x] **RM3**: ninguno de los 8 es equivalente (cambiar una
familia o el grupo de la regex cambia el resultado; `15: ALBARAN` pisa la clave de
FACTURA) · N/A **RM5**: rigor `estandar`, sin equivalentes · [x] **RM6**: no se quitó
ninguna guarda · N/A campaña manual: la automática dio 8 · [x] sin supervivientes que
analizar · [ ] **«Evidencias»**: la fila de mutación de `impl` §6 describe la campaña
**anterior** (2 workers, «NO VÁLIDA … hay que repetirla») y no la válida que está en
`progress/mutacion_F-090.md` (4 workers, `--timeout 1800`, 2.427 s, SHA `b88fdbb`); la fila
de `init.sh` dice KO de entorno y no recoge el verde del árbol principal (cambio 2) ·
[x] ningún N/A sin motivo.
**C4 ter** N/A: no hay `harness/rutas_sensibles.json` en este repositorio.
**C5** [ ] `tasks.md`: T1-T8 `[x]` con commit `F-090 Tn:`; T9-T11 MANUAL en `[ ]`, como
debe ser; pero **T12 (`init.sh` en verde) sigue `[ ]`** y ya está en verde (cambio 4) ·
[x] `git status` limpio · [x] `features.json` en `in_progress`, correcto.

## Lo que pidió mirar el líder

- **Filtro en origen (D2)**: `rcg` solo enlaces con `con.tip IN (12, 14, 15, 44, 46)`, `gra`
  solo los gráficos que esos enlaces nombran; 43, 306 y 708 no entran ni en `raw` (R3, R5).
  Un gráfico con varios documentos entra solo si uno es de compras, sin su enlace de
  personal. `run-all --full` (`Dockerfile`) las recarga enteras cada noche con el filtro, y
  `check-raw-recuentos` cuenta con el mismo `where`.
- **Sin binario**: `gra` tiene dos binarios (`ima`, `pul`) y dos textos ilimitados (`tex`,
  `cam`) según `azure-apps/sigrid_tablas.md`: los cuatro fuera, R4 nombra la que falte.
- **`cod` + `emp` bastan**: sí. `ruesma_rep.gra.cod` es único y la spec probó una lectura
  con 200. Pero la receta publicada **no funciona tal cual**: falta `blob_column` (cambio 1).
  Los avisos del 11 % sin nombre y del 0,23 % sin binario están en la ficha y en `azure-apps`.
- **Objetos intactos**: ningún SQL de `compras` cambia salvo el nuevo `14_` (R17 vigila `01_`);
  `documento_procesos` y `v_estado_documentos` no dependen del `14` ni él de ellos.
- **MANUAL de `impl` §5**: en orden (imagen y job → ingesta `rcg` antes que `gra` →
  `build-compras` → `check-raw-recuentos` → diccionario v48 y MCP → timings), con cifras
  esperadas y qué hacer si salta la guarda. Ninguna escritura contra Azure ni Sigrid en la rama.
- **El SQL no ha corrido nunca contra Postgres.** Lo que lo respalda: 29 tests de texto,
  el parser real de Postgres (`pglast`, informe §4), el `DO $$ … RAISE EXCEPTION` ya probado
  en `08_comparativos.sql`, `fn_sigrid_date(BIGINT)` usado igual sobre `con.fec` (el mismo
  «Entero tipo fecha»), la regex `\.([^.\s]+)$` válida en ARE (`\s` dentro de corchetes está
  permitido) y la PK garantizada por `rcg.ide`. **Riesgos del primer `build-compras`**, no
  bloqueantes: (a) si la ingesta de `gra` falla la primera noche (`stop_on_error` falso por
  defecto), `raw.gra` no existe y `build_compras` cae en su último sub-paso, con el resto
  de `compras` ya hecho pero el paso en FAILURE; (b) con `raw.rcg` VACÍA la guarda pasa
  (`v_total > 0`) y publica una tabla vacía: lo caza `check-raw-recuentos`, no la guarda;
  (c) los tipos de `raw.rcg`/`raw.gra` los decide la ingesta: lo comprueba el `SELECT` de
  T9. Recomiendo T9 a mano antes de dejarlo a la nocturna.

## Cobertura (requisito → test)

| Req. | Test(s) |
|---|---|
| R1-R6 | `test_f090_ingesta_sql.py::test_f090_r1_*` … `r6_el_censo_pasa_a_74` (12) |
| R7-R10 | `test_f090_dominio.py::test_f090_r7_*` … `r10_*` (50, parametrizados) |
| R11-R18 | `test_f090_ingesta_sql.py::test_f090_r11_*` … `r18_*` (17) |
| R19-R25, R27 | `test_f090_diccionario.py::test_f090_r19_*` … `r25_*`, `r27_*` (22) |
| R26, R28, R29 | MANUAL: T9, T11 y T10 (`impl_F-090.md` §5, pasos 3-5) |

## Cambios requeridos

1. **La receta de `documents/read` está incompleta, y el MCP la va a leer.**
   `config/diccionario/compras.yaml`, ficha `documento_adjuntos`, párrafo «EL FICHERO NO
   ESTA EN EL DATAMART» (`database: ruesma_rep`, `table: gra`, `id_column: cod`,
   `id_value` = `cod_repositorio`), y la misma lista en `azure-apps/datamart_seg_anual.md`
   (sección F-090): falta **`blob_column: ima`**, que `sigrid-api` exige
   (`Field(...)`, `sigrid-api/domain/models/sql_models.py:182`; es lo que usó la prueba de
   `progress/spec_F-090.md` l. 74-75). Añadirlo en los dos sitios, y en
   `tests/test_f090_diccionario.py::test_f090_r21_*` añadir `"blob_column"` a los datos
   buscados para que no se vuelva a caer. Aclarar de paso que ese `ima` es la columna de
   `ruesma_rep.gra`, no la de `raw.gra` (que se excluye), para que nadie lea contradicción.
2. **`progress/impl_F-090.md` §6 «Evidencias»**: sustituir la fila de mutación por la
   campaña válida (8/8 muertos, 0 supervivientes, **4 workers**, `--timeout 1800`, 2.427 s,
   línea base ~710 s, SHA `b88fdbb`, `progress/mutacion_F-090.md`) y la fila de `init.sh` por
   el verde del árbol principal (passed, skipped, cobertura 100 % 28/28). La nota «hay que
   repetirla» de §5 paso 1 pasa a «hecho».
3. **`progress/current.md`**: en la sección de F-090, quitar «Mutación NO VÁLIDA … repetirla»
   y poner el estado real (mutación válida, `init.sh` verde, en review). Retirar la sección
   «F-132 · FASE B, rama BORRAR, en curso», que contradice la de «CERRADA» (F-132 ya está en
   `history.md`).
4. **`specs/F-090-documento-adjunto/tasks.md`**: marcar T12 `[x]` (init.sh verde en el árbol
   principal, con la cifra). T9-T11 se quedan `[ ]`: son MANUAL.
5. **`tests/test_f090_dominio.py:184`**: ruff SIM300 («yoda»), aviso nuevo: `ruff check --fix`.

Ninguno toca producción ni SQL: pasada 2 incremental desde `335d671`, sin repetir campaña.

**Automejora (propuesta, no aplicada)**: en `CHECKPOINTS.md` C4 bis, «Evidencias», añadir
«y coinciden con el `progress/mutacion_F-XXX.md` vigente (workers, tiempo, SHA)»: aquí la
campaña se repitió después del informe y nadie actualizó las evidencias.
