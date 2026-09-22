<!-- progress/review_F-057_pasada2.md -->
> Pasada 2 de la review de F-057, **intacta** (identica a `review_F-057.md` en `17588d6`). Movida aqui en la pasada 3 por el tope de 140 lineas.

Revision incremental desde `fe5fb9c` (pasada 2), sobre HEAD `5588845`; delta = `fe5fb9c..HEAD`.

# F-057 · Review del esquema `personal`

> **La pasada 1 esta intacta en [`review_F-057_pasada1.md`](review_F-057_pasada1.md)**
> (identica a la commiteada en `5588845`, comprobado con `diff`). Se movio ahi
> solo porque ocupaba 139 de las 140 lineas del tope y la pasada 2 no cabia.

## Pasada 2

**Veredicto: CHANGES_REQUESTED.** Los siete cambios estan bien: las guardas
caen con TODAS mis mutaciones de la pasada 1 y el arbol tal cual sigue en verde.
**Queda un olvido de propagacion igual al del cambio 5**, en otro fichero que se
publica al MCP, y dos textos de codigo. Ediciones de una linea; nada de SQL.

**Rigor:** `estandar` (declarado): fase RED, cobertura >= 80 %, mutacion. El
delta no toca Python de produccion: rige la verificacion de mutacion de la 1.

### Rompiendolo a mano, otra vez (copia `git archive HEAD` en el scratchpad)

Las de la pasada 1 mas cuatro nuevas por la puerta de atras; `romper.py` aplica,
ejecuta `pytest tests/test_f057_personal.py` y restaura. Salida real:

| Mutacion | Pasada 1 | Pasada 2 (salida real) | Test que cae |
|---|---|---|---|
| Lateral + `emp.tarseg`, `ban`, `bancue`, `sexo`, `telmov`, `ele`, `dir1`, `dircpo`, `esigpas`, `g3wpas`, `clamai` | pasa 11/11 | **CAE 11/11** (1 failed, 57 passed c/u) | `r8_el_lateral_lee_exactamente_la_lista_blanca` |
| Lateral `SELECT emp.*` | pasa | **CAE** (1 failed, 57 passed) | idem |
| Fuga completa: `seg_social`/`cuenta_banco` en DDL + INSERT desde `e.tarseg`/`e.ban` + lateral | pasa | **CAE** (2 failed, 56 passed) | lista blanca + `r8_el_select_exterior_...` |
| NUEVA: `emp.tarseg AS dni` (renombrar para colarse) | — | **CAE** (1 failed) | lista blanca |
| NUEVA: subconsulta escalar `(SELECT x.tarseg FROM raw.emp x ...)` en el SELECT | — | **CAE** (2 failed) | `r8_raw_emp_solo_se_lee_en_el_lateral` (+ `r4`) |
| `WHEN 4 THEN 'HORA'` añadido | pasa | **CAE** (1 failed) | `r16_unidad_desde_medide` |
| `WHEN 5 THEN 'KM'` añadido | pasa | **CAE** (1 failed) | idem |
| `WHEN 3 THEN 'HORA'` antepuesto | pasa | **CAE** (1 failed) | idem |
| `ELSE 'HORA'` | cae | **CAE** (1 failed) | `r17_medide_desconocido_no_se_traduce` |
| `WHERE pl.unidad = 'HORA' OR pl.unidad = 'MES'` | pasa | **CAE** (1 failed) | `r21_vista_solo_horas` |
| NUEVA: `IN ('HORA','MES')` / sin `WHERE` / `(... OR TRUE)` | — | **CAE 3/3** | idem |
| **Reverso**: arbol restaurado | 58 passed | **58 passed** | — |

Es **lista blanca de verdad**: igualdad exacta con `{ide, dni, nomnom, nomape1,
nomape2}`, cada elemento `alias.col` desnudo (sin `*`, expresion ni alias);
`raw.emp` UNA sola vez en el SQL ejecutable; fuera del lateral, `e.<col>` solo
una de las cinco. Los comentarios no disparan las guardas (reverso en verde).

### Cambios 4 a 7

- [x] **4.** `infra/sql/02_roles.sql`: `personal` en los puntos 4, 5 y 6, sin
  «nueve»; y un test nuevo (R25) compara las tres listas con
  `ESQUEMAS_DEL_DATAMART`. Bien: el defecto pasa a guarda.
- [x] **5.** `docs/runbook_postgres_azure.md:149` y `00_global.yaml:6` y `:1082`
  dicen «diez»; el runbook ademas añade `personal` a la lista.
- [x] **6.** Comentario del lateral: verificado en el codigo que `emp` se ingiere
  con `id_column: ide` (`config/tables_sigrid.yaml:576-578`) via
  `ensure_raw_table(..., primary_key=spec.id_column)`
  (`ingest_raw_step.py:268`), y `ESQUEMAS_CON_CLAVE_GARANTIZADA = ("raw",)`
  (`unicidad_sql.py:53`). El comentario dice la verdad.
- [x] **7.** «Evidencias»: **4 workers** en las dos campañas (`impl_F-057.md:174-182`);
  `tasks.md` T5 anota la sustitucion por la lista blanca.

### Barrido de «nueve esquemas» en el resto del repositorio

`specs/F-005`, `specs/F-006`, `progress/*_F-005/F-006*` son registro historico
de features cerradas: se quedan como estan. Vivos y falsos desde F-057:

- **`config/diccionario/_meta.yaml:512-513`** — **SE PUBLICA AL MCP** (ficha de
  `_meta.diccionario_contexto.bloque`): «Hoy son **29** filas (5 convenciones,
  9 ordenes de magnitud, 3 ejes, **9 esquemas** y 3 de `ocultar`)». Medido en
  `00_global.yaml`: 5/9/3/**10**/3 = **30**. Es exactamente el olvido del
  cambio 5, en otro fichero; la pasada 1 no lo vio.
- `etl_sigrid/domain/diccionario.py:401`, docstring de `_validar_esquemas`:
  «los NUEVE esquemas». El implementer lo señalo (`impl_F-057.md:150`) y lo
  dejo fuera por no pedirlo el review: ahora se pide.
- `tests/test_f006_formato.py:267` (comentario) y `:981` (docstring): «nueve».

## Checkpoints (delta)

- **C1** [x] `bash harness/init.sh` exit 0, **ENTORNO LISTO**: 5027 passed,
  189 skipped (423 s). Baja de 5042 por reemplazar 19 parametrizados de la lista
  negra por 3 de la blanca y sumar 1 de R25: cuadra (-19 +3 +1 = -15).
- **C2** [x] una `in_progress`, rama correcta. `current.md`: cambio 8, del lider.
- **C3** [x] hexagonal; primera linea con ruta en lo tocado; sin prints ni secretos.
- **C3 bis** N/A: el delta no toca `docs/referencia/`.
- **C4** [x] R8, R16/R17 y R21 vigilados de verdad (tabla). [x] offline.
  [ ] **propagacion al diccionario publicado incompleta** (`_meta.yaml:512-513`).
- **C4 bis** [x] rigor `estandar`. [x] cobertura `[OK]` 94,7 % (968/1022).
  [x] mutacion: el delta no toca Python de produccion, rige la verificacion de
  la pasada 1 (campaña no reejecutada: 4.084,7 s y 2.906,6 s segun el informe).
  [x] RM1: el delta no toca ficheros del alcance mutado. [x] RM6: no se quito
  defensa. [x] workers declarados. N/A RM5: nivel `estandar`.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] commits `F-057 review N: ...` por cambio. [ ] T25 sigue `[ ]` con
  `init.sh` en verde: marcarla al cerrar. T23-T24 MANUAL, bien abiertas.

## Cobertura requisito -> test (delta)

| Requisito | Test |
|---|---|
| R8 | `test_f057_r8_raw_emp_solo_se_lee_en_el_lateral`, `..._el_lateral_lee_exactamente_la_lista_blanca`, `..._el_select_exterior_no_usa_otra_columna_del_empleado` |
| R16 | `test_f057_r16_unidad_desde_medide` (igualdad exacta, sin `medide` repetido) |
| R17 | `test_f057_r17_medide_desconocido_no_se_traduce` (un solo `ELSE`, `'DESCONOCIDA'`) |
| R21 | `test_f057_r21_vista_solo_horas` (filtro exacto, un unico `WHERE`) |
| R25 | `test_f057_r25_el_fichero_de_provision_trae_los_diez_esquemas` |

El resto de R1-R28, como en la pasada 1.

## Cambios requeridos (pasada 2)

1. **`config/diccionario/_meta.yaml:512-513`**: «29 filas ... 9 esquemas» ->
   «30 filas ... 10 esquemas». Mejor aun, quitar el desglose numerico: la
   propia ficha dice que «el recuento caduca» y remite a la consulta. Si el
   cambio exige subir la version del diccionario, subirla; publicarlo entra
   en T24 (MANUAL).
2. **`etl_sigrid/domain/diccionario.py:401`**: «los NUEVE esquemas» -> «los
   esquemas de `ESQUEMAS_DEL_DATAMART`» (sin numero, para no repetir esto).
3. **`tests/test_f006_formato.py:267` y `:981`**: mismo cambio en el
   comentario y el docstring.
4. **`tasks.md` T25**: marcar `[x]` con el `init.sh` en verde de esta pasada.

Si la pasada 3 toca SQL o `test_f057_personal.py`, se repite la tabla.

## Pendiente MANUAL del humano (no bloquea)

T23 (cifras contra la base viva) y T24 (`python main.py publicar-diccionario`,
que tras el cambio 1 publica tambien `_meta.yaml` corregido). `build-personal`
en Azure. Confirmar que el `.env` local, si fija `PG_CONSUMPTION_SCHEMAS`,
incluye `personal`.

## Automejora (propuesta, no aplicada)

`CHECKPOINTS.md` C4 (vale para `arnes-base`): si una feature cambia la
**cardinalidad** de un conjunto citado en prosa (esquemas, pasos, reglas), el
reviewer hace `grep` del numero viejo en letra y en cifra sobre lo no
historico, sobre todo lo publicado. Aqui el olvido salio en dos pasadas.

## Evidencias

- `bash harness/init.sh` tal cual: **exit 0, ENTORNO LISTO**; 5027 passed,
  189 skipped (423,42 s); cobertura 94,7 %; TAMAÑO en topes.
- Mutaciones sobre copia en el scratchpad. Solo escribi este informe y
  `review_F-057_pasada1.md`; lo demas no rastreado es de otros agentes.
