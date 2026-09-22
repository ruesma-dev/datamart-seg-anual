<!-- progress/review_F-057.md -->
Revision incremental desde `17588d6` (pasada 3), sobre HEAD `d9e9cb2`; delta = `17588d6..HEAD`.

# F-057 · Review del esquema `personal`

> Pasadas anteriores, intactas: [pasada 1](review_F-057_pasada1.md) y
> [pasada 2](review_F-057_pasada2.md) (esta ultima comprobada con `diff` contra
> `git show 17588d6:progress/review_F-057.md`: identica). Se movio por el tope.

## Pasada 3

**Veredicto: CHANGES_REQUESTED.** Los cuatro cambios de la pasada 2, y el
cuarto «nueve» que encontro el implementer, estan bien. **Pero mi barrido,
repetido con un patron mas ancho, saca dos «nueve» vivos y falsos que ni mi
pasada 2 ni el barrido del implementer vieron.** Dos ediciones de una linea,
en ningun caso SQL ni tests. Mea culpa: en la pasada 2 busque «nueve
esquemas» y estas dos frases no llevan la palabra «esquemas» pegada.

**Rigor:** `estandar` (declarado): fase RED, cobertura >= 80 %, mutacion. El
delta no toca Python ejecutable (solo un docstring): rige la verificacion de
mutacion de la pasada 1.

### Lo pedido en la pasada 2

- [x] **1.** `config/diccionario/_meta.yaml:512-513`: **quito el desglose**, no
  corrigio el numero. Ahora dice que el recuento por bloque no se escribe
  porque caduca «en cuanto una feature anade un esquema o una convencion» y
  remite a `SELECT bloque, count(*) FROM _meta.diccionario_contexto GROUP BY 1`.
  La ficha sigue siendo correcta (los cinco `valores` no cambian) y util: dice
  que bloques hay y como contarlos. Es lo mejor de las dos opciones.
- [x] **2.** `etl_sigrid/domain/diccionario.py:401`: «los esquemas de
  `ESQUEMAS_DEL_DATAMART`», sin numero.
- [x] **3.** `tests/test_f006_formato.py:267` y `:981`: idem.
- [x] **3 bis.** `tests/test_f006_punteros.py:34` (el que hallo el implementer,
  mi pasada 2 no lo listaba): «entre los de `ESQUEMAS_DEL_DATAMART`». Bien.
- [x] **4.** `tasks.md` T25 `[x]`; T23-T24 siguen `[ ]` (MANUAL), correcto.

Confirmado: `git diff --stat 17588d6..HEAD -- '*.sql' tests/test_f057_personal.py`
sale **vacio**; la tabla de romper guardas de la pasada 2 sigue valiendo.

### Las dos decisiones del implementer

- **No subir la `version` del diccionario: CORRECTA.** `00_global.yaml:272`
  dice `version: 25`; en `main` es 24, y el MCP anuncia **Version 24 · publicado
  2026-09-18 03:43 UTC**. La 25 entra en `84e0ada` (F-057 T18-T19) y solo la
  contiene esta rama (`git branch --contains`). Sin publicar: `_meta.yaml`
  corregido viaja en esa misma 25 con T24.
- **«los NUEVE esquemas» en `BACKLOG.md:592` / `features.json:517`:
  CORRECTA.** Es la descripcion de **F-034** (terminada), que cuenta lo que se
  encontro entonces en `config/settings.py`: es registro historico de otra
  feature, y ademas `BACKLOG.md` es generado. Reescribirla falsearia la historia.

### Barrido (repetido, patron ancho)

Comando: `git grep -n -i -E "\bnueve\b" -- . ':!specs/F-005*' ':!specs/F-006*'
':!progress/*'` mas `git grep -n -i -E "(nueve|9) esquemas"` sobre todo salvo
lo de F-005/F-006; cada acierto leido en contexto. Casi todos son «nueve» de
otra cosa (tablas de F-074, «multiplicaba por nueve», mutantes, bases del
servidor). Los que hablan de esquemas:

| Sitio | Texto | Juicio |
|---|---|---|
| `diccionario.py:38` | «Los DIEZ ... Eran nueve hasta F-057» | historico explicito, bien |
| `test_f006_formato.py:272` | «Eran NUEVE ... y son DIEZ desde F-057» | idem, bien |
| `test_f057_personal.py:1023` | `assert "nueve" not in crudo` | es la guarda R25, bien |
| BACKLOG / features.json | F-034 | historico (arriba) |
| **`config/diccionario/00_global.yaml:881`** | «# ESQUEMAS (R4) ... **Son NUEVE.**» | **FALSO, presente** |
| **`docs/ARCHITECTURE.md:510`** | «uno por esquema —los **nueve** del datamart—» | **FALSO, presente** |

`00_global.yaml:881` es un comentario YAML (no se publica), pero encabeza
justo el bloque `esquemas:` donde F-057 añadio `personal`: quien lo lea ve
«nueve» sobre diez fichas. Y es el mismo fichero que la pasada 2 dio por
corregido (`:6` y `:1082`). `ARCHITECTURE.md` es documentacion viva que el
`CLAUDE.md` manda leer antes de diseñar.

## Checkpoints (delta)

- **C1** [x] `bash harness/init.sh` tal cual: exit 0, **ENTORNO LISTO**;
  5027 passed, 189 skipped (435,94 s). Mismo recuento que la pasada 2: el
  delta no añade ni quita tests, cuadra.
- **C2** [x] una `in_progress` (F-057), rama correcta.
- **C3** [x] primera linea con ruta intacta en lo tocado; sin prints ni
  secretos; hexagonal sin cambios.
- **C3 bis** N/A: el delta no toca `docs/referencia/`.
- **C4** [x] guardas R8/R16/R17/R21/R25 sin cambios desde la pasada 2 (SQL y
  `test_f057_personal.py` intactos). [x] offline.
  [ ] **propagacion del cambio de cardinalidad incompleta**: dos «nueve» vivos
  (tabla de arriba).
- **C4 bis** [x] rigor `estandar`. [x] cobertura `[OK]` 94,7 % (968/1022).
  [x] mutacion: rige la de la pasada 1 (campaña no reejecutada: 4.084,7 s y
  2.906,6 s segun el informe; el delta no toca codigo mutable). [x] RM1: el
  delta no toca el alcance mutado. [x] RM6: no se quito defensa. N/A RM5:
  nivel `estandar`.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] commit `F-057 review 8: ...`; T25 `[x]`. T23-T24 MANUAL abiertas.
- **TAMAÑO** [x] review 140/140 en el `init.sh` de esta pasada, antes de
  reescribir; este fichero queda por debajo.

## Cobertura requisito -> test

Sin cambios respecto a la pasada 2 (tabla en
[`review_F-057_pasada2.md`](review_F-057_pasada2.md)) y la pasada 1.

## Cambios requeridos (pasada 3)

1. **`config/diccionario/00_global.yaml:881`**: «Son NUEVE. Los informes de
   exploracion dicen ocho y se equivocan.» -> sin numero, p. ej. «Son los de
   `ESQUEMAS_DEL_DATAMART` (eran nueve hasta F-057). Los informes de
   exploracion decian ocho y se equivocaban.»
2. **`docs/ARCHITECTURE.md:510`**: «—los nueve del datamart—» -> «—los de
   `ESQUEMAS_DEL_DATAMART`—» (o «los diez»; mejor sin numero).
3. Antes de entregar, **el implementer repite el barrido ancho** de arriba
   (`\bnueve\b`, no solo «nueve esquemas») y pega en `impl_F-057.md` el
   comando y cada acierto con su juicio.

Ni SQL ni `test_f057_personal.py`: la pasada 4 no repetira la tabla de romper
guardas. No requiere subir la `version` (comentario y doc no publicados).

## Pendiente MANUAL del humano (no bloquea)

`build-personal` en Azure, T23 (cifras contra la base viva) y T24
(`python main.py publicar-diccionario`, que publica la 25 con `_meta.yaml` ya
corregido). Confirmar que el `.env` local, si fija `PG_CONSUMPTION_SCHEMAS`,
incluye `personal`.

## Automejora (propuesta, no aplicada)

Refina la de la pasada 2 para `CHECKPOINTS.md` C4 (vale para `arnes-base`):
al cambiar la cardinalidad de un conjunto citado en prosa, el `grep` busca
**el numero viejo solo** (`\bnueve\b` y `\b9\b` junto al sustantivo), no la
frase «nueve esquemas»: el sustantivo puede ir en otra linea o sobreentenderse.
Asi se escaparon `00_global.yaml:881` y `ARCHITECTURE.md:510` en dos pasadas.

## Evidencias

- `bash harness/init.sh` tal cual: exit 0, ENTORNO LISTO, 5027 passed,
  189 skipped, cobertura 94,7 %.
- Solo escribi este informe y `review_F-057_pasada2.md`; no toque codigo ni
  rama. Los `progress/explore_*` no rastreados o modificados son de otros agentes.
