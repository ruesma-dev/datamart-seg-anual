<!-- progress/review_F-072.md -->
Revisión completa (pasada 1) · HEAD `b2d10d30581dcb068df2b04f47cab92b44ba3c37`

# Review F-072 · el censo semántico de las 31 tablas sin consumidor

**VEREDICTO: CAMBIOS REQUERIDOS.** Un solo criterio de `acceptance` sin cumplir
—el 7—, y su hueco cambia el alcance de F-073. Lo demás está bien: **contrasté ~40
cifras contra la base y no falló ninguna de las cinco que cambian decisiones.**

**Nivel de rigor**: `estandar`, declarado. Exige fase RED, cobertura y mutación.
El diff real (`76efa0f..HEAD`, 11 ficheros) es **0 `.py` y 0 `.sql`**: las tres
puertas quedan N/A por ausencia de código, justificado en C4 bis.

## Lo que verifiqué yo, con su resultado real

Consultas de SOLO LECTURA (`PostgresClient.filas_solo_lectura`, `READ ONLY`); ni
una escritura. Las cinco pedidas salieron **exactas**:

| qué | informe | medido por mí |
|---|---|---|
| Puente `cen`→`obr` por (`emp`,`cod`); `cen.obride` | 683 pares 1:1, 0 ambigüedades; `obride` 0 en 804 | **683 pares / 683 centros / 683 obras**, y `cen` 804 filas con **0 `obride` informados** ✓ |
| `retenciones.movimientos.obra_id`; aritmética `+1` | 261 de 261; `+1` solo 64 % | **261 distintos, 261 resueltos, 0 casan hoy con `maestro.obras`**; `+1` **436/683 = 63,8 %** (4 con −1) ✓ |
| `res` por `cla` | 1.353 / 1.157 / 106 | **1.353 personas, 1.157 consumos, 106 medios** sobre 2.616 ✓ |
| `comprv.prvide` vs `dco.entide` | 18,11 % vs 99,86 % | **12.799 de 70.677** y **70.579 de 70.677** ✓ |
| `auxobrtca` / `obrparpar.tcaide` | 3 filas / 0 en 392.207 | **3** y **392.207 filas, 0 informadas** ✓ |
| `tiemod` en `com`/`comlin`/`comprv` | no existe; degrada en silencio | **la columna NO está en `raw`; `_source_tiemod` NULL en las 287.673**; `auxpag` sí la tiene (69/69) ✓ |

`ingest_raw_step.py:279` es literalmente
`tiemod_col = spec.incremental_column if spec.incremental_column in col_names else None`;
las tres declaran `tiemod` en el yaml y 20.185+196.811+70.677 = **287.673** ✓.

**Volúmenes**: recontadas las 28 tablas del censo en `raw`; **coinciden todas** con
las fichas, de `dcopro` 788.644 y `hmores` 329.170 a `deffir` 17, `auxefp` 10,
`prvobrpag` 6 y **`obrprv` 0**. **Económicas y de enganche**: `comlin` **1.160,1
M€** adjudicados con 14.513 `pre`=0, **4.100 negativas** y la línea máxima de
**363,2 M€**; ofertado **3.467 M€** en 67.959 ofertas; `ctrrec` `reccla`=5 →
**6.257 contratos, base 460,3 M€, cuota 22,8 M€**; `hmores` **98,0 M€** con **535
de 535** obras en `maestro.obras` y **5.773 de 5.773** partidas en `stg.partidas`;
`apa.obride` **a cero en las 709.759**. **§2 y §4**: el yaml declara **56** tablas,
las **31** del censo están todas y **ninguna de las nueve** del §2 aparece;
`prvcer` excluye `tex` ✓. **Coherencia catálogo ↔ bloques**: sin contradicciones;
las 31 tienen veredicto en §1 (19 de dato + 5 catálogo + `prvcer` + 6 descartes).

**Tres desviaciones menores, ninguna cambia una decisión**: (a) `prvcer`, los
«2.708 caducados antes de 2020» son 2.705 más 3 sin fecha (`feccad`=0); (b) `apa`
por el puente, el 93,2 % del debe medido sobre muestra del 10 % es **96,3 %** sobre
la tabla entera (va a favor, y el muestreo estaba declarado); (c) `dco.entide`
distintos, 8.741 y no 8.742.

## Los siete criterios de `acceptance`

1. Ficha de las 31 (qué es, grano, volumen, unión) — **[x]**. 2. % informado
   columna a columna, medido — **[x]**, muestreo declarado en `apu` y `dcopro`.
3. Significado desde sigrid-api y `sigrid_tablas.md` — **[x]**, cada afirmación
   etiquetada [DOC]/[SIG]/[RAW], con seis contradicciones doc↔dato cazadas. 4.
   Preguntas de negocio — **[x]**. 5. Enrutado — **[x]**. 6. Solo lectura — **[x]**.
7. **Hallazgos heredados de F-071 recogidos y medidos — [ ] NO CUMPLIDO.**

## Cambios requeridos

**1. El criterio 7 no está en el entregable.** «F-071» no aparece ni una vez en
los cinco ficheros; `auxmun`/`auxpro` solo salen como dirección **del empleado**
en la ficha de `emp`, y los tres campos de `raw.obr` que F-071 marcó como *no* la
dirección de la obra (`diride` director, `perdir` contacto, `entdiride` dirección
del cliente) no se mencionan. Viven en `progress/current.md` líneas 175-181,
**heredados de la spec de F-071 y sin una sola medición**; el criterio pide
«recogidos **y medidos**». Lo medí en una consulta, y el número cambia el alcance
de F-073:

> `raw.obr`, 921 obras: `dir1` informado en **305 (33,1 %)**, `dir2` en 47,
> `dircpo` en 303, **`munide` en 294 (31,9 %, 194 municipios)**, `proide` en 306;
> resueltos contra catálogo, **294 con municipio y 306 con provincia**. Los tres
> campos que F-071 dijo que no son la dirección lo confirman por vacíos: `diride`
> 8, **`perdir` 0**, `entdiride` 2. Catálogos: `auxmun` 56.053, `auxpro` 95.

**F-073 promete en su `acceptance` que «dónde está la obra X» se responde sin
explicar nada en el prompt. Con este dato, para dos de cada tres obras la respuesta
correcta es "no consta".** Hay que escribirlo en el catálogo antes de especificar
F-073, que es justo para lo que existe F-072. *Arreglo*: una sección corta en
`explore_F-072_catalogo.md` con esos porcentajes y la advertencia.

**2. Menor, pero es C2.** `progress/current.md` línea 19 sigue listando **F-071 en
prioridad 4 como «spec en curso»** cuando su línea 126 dice «F-071 ESTÁ RETIRADA»:
un resto de la sesión anterior que manda a la próxima a una feature muerta.

## CHECKPOINTS

- **C1 [x]** — `bash harness/init.sh` exit 0: **3.970 passed, 159 skipped** en
  404 s; COBERTURA [OK]; TAMAÑO [OK]. Los siete ficheros del arnés existen.
- **C2 [ ]** — Una sola `in_progress` ✓, rama correcta ✓, `history.md` al día ✓.
  Falla por el cambio requerido 2: `current.md` arrastra la tabla anterior.
- **C3 N/A justificado** — 0 `.py` y 0 `.sql`: no hay arquitectura ni
  convenciones de código que juzgar. **Barrido de datos sensibles hecho por mí
  sobre los cinco entregables: limpios.** `emp` y `res` describen DNI, NSS,
  cuenta bancaria y domicilio **por lo que son, con su porcentaje y sin un solo
  valor**, y dejan escrita la restricción de publicación. **C3 bis N/A**: no se
  toca `docs/referencia/`.
- **C4 [x] con matiz** — no hay requisitos EARS ni tests posibles: el entregable
  es conocimiento. La trazabilidad se cumple contra los siete `acceptance`,
  **verificados contra la base por el reviewer**, la única forma de test que
  admite esta feature.
- **C4 bis** · `rigor` declarado ✓. **Fase RED N/A justificado**: cero líneas de
  producción y cero tests nuevos; nada que romper para enseñar el fallo previo.
  - **Cobertura N/A justificado**, y hay que decir por qué: la puerta salió
    `[OK] 93,6 % de 842 líneas`, pero **esas 842 líneas no son de F-072**.
    `harness.alcance` resuelve el diff contra `cd18e09` (F-052), muy por detrás,
    así que mide el acumulado de F-025, F-066 y F-068, ya cerradas. El alcance
    propio de F-072 es **cero líneas de Python**.
  - **Mutación N/A justificado**: no hay un solo `.py` que mutar (control:
    `git diff 76efa0f..HEAD --name-only` → 11 ficheros, 0 `.py`, 0 `.sql`), y
    lanzarla sobre el alcance contaminado de arriba mutaría código de otras
    features. **RM1-RM6 N/A por ausencia de campaña**, no por omisión.
    **Evidencias N/A justificado**: no hubo implementer; la evidencia son los
    cuatro informes de bloque y el catálogo, recontrastados arriba.
- **C4 ter N/A** — no hay `harness/rutas_sensibles.json`. **C5 [x] con nota**:
  `tasks.md` N/A (`sdd=false`); commits bien rotulados (`9746c7a` informes,
  `b2d10d3` fichas); `features.json` refleja el estado real. Único sin trackear:
  `progress/explore_F-074_las_nueve.md`, trabajo de **F-074**.

## Las seis correcciones de ficha de `b2d10d3` — **las seis están y se sostienen**

Apendadas como bloque marcado sin borrar el texto viejo, y **las seis las sostiene
lo que medí**: F-036 (el punto 3 no es implementable: 3 filas y 0 de 392.207),
F-038 (proveedor por `dco.entide` 99,86 % y no `comprv.prvide` 18,11 %, más el
saneado de `comlin`), F-045 (nudo resuelto y 1:1: 683 pares, 261/261, `+1` solo
64 %), F-055 (`prvcer` muerto, recuperar `tex`, publicar solo comparativos),
F-057 (`res` no es el maestro de personal: 1.353/1.157/106) y F-061 (desbloqueada
por F-045).

## Automejora (propuesta, no aplicada)

1. **`rigor` mal elegido.** F-072 no escribe una línea de código y
   `CHECKPOINTS.md` define `documental` como «solo documentación, specs o notas de
   sesión: ni código ni SQL». Declararla `estandar` obliga a justificar tres N/A
   que el nivel correcto no habría pedido.
2. **`harness.alcance` mide contra una base obsoleta.** Con `dev` varias features
   por detrás, el alcance de la feature en curso arrastra el código de las ya
   cerradas y **las dos puertas automáticas miden lo que no es**: aquí la cobertura
   salió verde por herencia. Misma familia que RM1; merece ficha propia (anclar el
   alcance al primer commit de la rama, no a `dev`).
