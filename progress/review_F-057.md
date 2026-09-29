<!-- progress/review_F-057.md -->
Revision incremental desde `c9124f8` (pasada 4), sobre HEAD `2d6fc80`; delta = `c9124f8..HEAD`.

# F-057 · Review del esquema `personal`

> Pasadas anteriores, intactas: [pasada 1](review_F-057_pasada1.md),
> [pasada 2](review_F-057_pasada2.md) y [pasada 3](review_F-057_pasada3.md)
> (esta ultima comprobada con `diff` contra `git show HEAD:progress/review_F-057.md`:
> identica). Se movio por el tope de 140 lineas.

## Pasada 4

**Veredicto: APPROVED**, con lo MANUAL del humano pendiente (abajo). Los dos
«nueve» de la pasada 3 estan corregidos sin numero y el barrido por el numero
solo, repetido por mi, sale limpio.

**Rigor:** `estandar` (declarado): fase RED, cobertura >= 80 %, mutacion. El
delta no toca SQL, tests ni Python: siguen valiendo las guardas, la
propagacion y la mutacion dadas por buenas en las pasadas 1 a 3.

### Lo pedido en la pasada 3

- [x] **1.** `config/diccionario/00_global.yaml:881`: «Son los de
  `ESQUEMAS_DEL_DATAMART` (eran nueve hasta F-057). Los informes de
  exploracion decian ocho y se equivocaban.» Sin numero en presente; el
  «nueve» que queda es historico explicito.
- [x] **2.** `docs/ARCHITECTURE.md:510`: «uno por esquema —los de
  `ESQUEMAS_DEL_DATAMART`— mas `00_global.yaml`». Sin numero.
- [x] **3.** `impl_F-057.md` (seccion «Pasada 4») trae los dos comandos y la
  lista de aciertos con su juicio.

### Delta

`git diff --stat c9124f8..HEAD`: **3 ficheros**, `00_global.yaml` (+2 -1),
`docs/ARCHITECTURE.md` (+1 -1), `progress/impl_F-057.md`. Ni SQL, ni tests,
ni Python. Comentario YAML y doc no publicados: no hace falta subir `version`.

### Barrido, ejecutado por mi

1. `git grep -n -i -E "\bnueve\b" -- . ':!specs/F-005*' ':!specs/F-006*' ':!progress/*'`
   → **53 aciertos**, los mismos que lista el implementer. Leidos en contexto
   los dudosos. Ninguno afirma en presente que haya nueve esquemas:
   - historicos explicitos: `00_global.yaml:881`, `diccionario.py:38` («Los
     DIEZ... Eran nueve hasta F-057»), `test_f006_formato.py:272`;
   - guarda R25: `test_f057_personal.py:999/1023`;
   - `BACKLOG.md:592` / `features.json:517`: descripcion de F-034
     (terminada), «verificado... que config/settings.py sigue con los NUEVE
     esquemas» con fecha 2026-08-27. Historico, ya juzgado en la pasada 3;
   - el resto, «nueve» de otra cosa: tablas de F-074, «multiplicaba por
     nueve», simbolos de regex, supervivientes de F-073, preguntas de F-085,
     bases del servidor, obras, columnas, minutos/SQL/descartes de specs
     F-025, F-052 y F-066. Todos coinciden con el juicio del implementer.
2. `git grep -n -i -E "\b9\b" -- config/diccionario docs etl_sigrid tests infra`
   → **257 aciertos en 82 ficheros** (el implementer dice 258; diferencia de
   uno sin importancia: el filtro de esquemas da cero en ambos). Filtrado por
   `esquema|schema|len(|== 9`: solo 4 lineas, todas de fechas o planes
   (`test_f025_firma.py:129`, `test_f025_ventana.py:184`,
   `test_f042_regla.py:319/414`). **Cero sobre esquemas.**
3. Comprobacion cruzada mia, todo el repo salvo `progress/`:
   `git grep -n -i -E "(\b9\b|nueve).{0,40}(esquema|schema)|(esquema|schema).{0,40}(\b9\b|nueve)"`.
   Aparte de lo ya citado, solo salen `README_COMPRAS_SETUP.md:5` («las 9
   tablas de compras», no esquemas) y las specs cerradas de F-005/F-006,
   excluidas a proposito por ser el registro de lo que se especifico entonces.

**Sale limpio.**

## Checkpoints (delta)

- **C1** [x] `bash harness/init.sh` tal cual: exit 0, **ENTORNO LISTO**; 5027 passed, 189 skipped (455,38 s), igual recuento que la pasada 3.
- **C2** [x] una `in_progress` (F-057), rama `feature/F-057-recursos-empleados-partes`.
- **C3** [x] primera linea con ruta intacta en lo tocado; sin prints ni
  secretos; hexagonal sin cambios (no hay codigo en el delta).
- **C3 bis** N/A: el delta no toca `docs/referencia/`.
- **C4** [x] guardas R8/R16/R17/R21/R25 sin cambios (SQL y tests intactos).
  [x] offline. [x] **propagacion del cambio de cardinalidad completa**: el
  barrido por el numero solo no deja ningun «nueve esquemas» en presente.
- **C4 bis** [x] rigor `estandar`. [x] cobertura `[OK]` 94,7 % (968/1022). [x] mutacion:
  rige la de la pasada 1 (campaña no reejecutada: 4.084,7 s y 2.906,6 s segun
  el informe; el delta no toca codigo mutable). [x] RM1: el delta no toca el
  alcance mutado. [x] RM6: no se quito defensa. N/A RM5: nivel `estandar`.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] commit `F-057 review 9: ...`. T1-T22 y T25 `[x]`; T23-T24 son
  MANUAL del humano (abajo).
- **TAMAÑO** [x] este informe queda por debajo de 140 lineas.

## Cobertura requisito -> test

Sin cambios respecto a la pasada 2 (tabla en
[`review_F-057_pasada2.md`](review_F-057_pasada2.md)) y la pasada 1.

## Cambios requeridos

Ninguno.

## Pendiente MANUAL del humano (no bloquea este veredicto; si el cierre)

F-057 **no pasa a `done`** hasta que el humano ejecute, en este orden:
`python main.py build-personal` en Azure, **T23** (cifras contra la base viva)
y **T24** (`python main.py publicar-diccionario`, que publica la `version` 25
con `_meta.yaml` y `00_global.yaml` corregidos). Confirmar que el `.env`
local, si fija `PG_CONSUMPTION_SCHEMAS`, incluye `personal`.

## Automejora (propuesta, no aplicada)

Se mantiene la de la pasada 3 para `CHECKPOINTS.md` C4 (vale para
`arnes-base`): al cambiar la cardinalidad de un conjunto citado en prosa, el
barrido busca **el numero viejo solo** (`\bnueve\b`, `\b9\b`), no la frase
con el sustantivo; y conviene remitir a la constante en vez de escribir el
numero, como se ha hecho aqui.

## Evidencias

- `bash harness/init.sh` tal cual: exit 0, **ENTORNO LISTO**; 5027 passed, 189 skipped (455,38 s), igual recuento que la pasada 3.
- Solo escribi este informe y `review_F-057_pasada3.md`; no toque codigo ni
  rama. Los `progress/explore_*` son de otros agentes.
