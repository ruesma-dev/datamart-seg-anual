<!-- progress/impl_F-079.md -->
# F-079 · Todo lo publicado es consultable — informe de implementación

Rama `feature/F-079-todo-lo-publicado-es-consultable`. Rigor `estandar`,
`sdd=false`: se trabaja contra los seis `acceptance` de `harness/features.json`.

**Lo que cambió, en una frase:** los siete objetos de `stg` que no son funciones
—y la entrada del propio esquema `stg` en `00_global.yaml`— dejan de estar
desaconsejados para consulta; las advertencias de **corrección** que viajaban
dentro de su `motivo_no_consumo` se mudan a la `descripcion`, que es texto
publicado; los grupos B y C no se tocan; el diccionario sube a **versión 18** y
queda **pendiente de publicar** (escritura contra Azure: la autoriza el humano).

## Ficheros tocados

| Fichero | Qué |
|---|---|
| `config/diccionario/stg.yaml` | 7 fichas a `consumo_recomendado: true`, sin `motivo_no_consumo`; 4 advertencias reubicadas en `descripcion`; cabecera del fichero reescrita |
| `config/diccionario/00_global.yaml` | esquema `stg` a `true` con `para_que_sirve` nuevo; `version: 17 → 18` + entrada de changelog |
| `tests/test_f079_stg_consultable.py` | **nuevo**, 53 tests: los seis criterios y, sobre todo, el barrido de que ninguna advertencia se pierde |
| `tests/test_f006_formato.py` | el test que afirmaba lo contrario, corregido (ver §5) |
| `progress/current.md` | recuentos (47 → 54 de consumo, versión 18) + sección de F-079 con sus MANUAL |

Ni una línea de Python de producción ni de SQL: es contenido del diccionario.

## 1 · Tres correcciones al inventario del encargo (medidas, no estimadas)

El encargo daba 27 objetos fuera de `raw` con `consumo_recomendado: false`
repartidos en 7 + 10 funciones + 10 rotos. **El 27 es exacto; el reparto, no.**
Medido sobre el diccionario cargado (no sobre el YAML crudo):

* **Grupo B: son 11 funciones, no 10** (3 en `cierre`, 3 en `compras`, 3 en
  `stg`, 1 en `maestro`, 1 en `retenciones`). La lista literal está en la
  constante `GRUPO_B_FUNCIONES` de `tests/test_f079_stg_consultable.py`.
* **Grupo C: son 9 objetos, no 10** (la lista del encargo ya enumeraba nueve).
  Literal y motivo, en la constante `GRUPO_C` del mismo fichero.
* **Los códigos de regla del encargo estaban cruzados** (`domain/diccionario.py`):
  la que exige `ejemplos_preguntas` a todo recomendado es **R40** (l. 602), no
  R11 —R11 vigila que el `ambito` de las reglas duras sea resoluble—; y **R3** no
  compara `descripcion` con `motivo_no_consumo`, sino que exige que el motivo
  exista y llegue a 30 caracteres cuando el booleano es `false` (l. 573). Subir
  el booleano activa además **R6** (`columnas`) y **R2** (`clave_negocio`). **Los
  siete ya cumplían las tres**: verificado antes de tocar nada, y atado en test.

7 + 11 + 9 = 27. ✔

## 2 · La clasificación frase a frase de los siete motivos (el trabajo de verdad)

| Objeto | Frase | Veredicto | Dónde queda |
|---|---|---|---|
| `plan_mensual` | «conviven TODAS las versiones master… multiplica los importes» | **corrección** | `descripcion` + regla `R-VERSION-MASTER` |
| `plan_mensual` | «para planificación hay que ir a `mart.fact_seguimiento_mensual`» | mixta: dice **dónde está resuelta** la versión | `descripcion`, como parte del aviso |
| `presupuesto` | «elegir la columna de importe según el ámbito y filtrar la fase correcta» | **corrección** | `descripcion` (era lo único que solo vivía aquí) |
| `presupuesto` | «la fuente buena para cuál es el presupuesto de la obra» | enrutado **positivo** | `descripcion` (se gana, no se pierde) |
| `obras` | «su columna `activa` no significa nada» | **corrección** | `descripcion` + `significado` de la columna + `R-OBRA-ACTIVA` |
| `version_master_vigente` | «resuelve la versión de forma GLOBAL… no coincide con `mart` en los meses anteriores» | **corrección** | `descripcion` |
| `ambitos` | «`uso_seguimiento` está desfasada: da una respuesta incompleta» | **corrección** | `descripcion` + `significado` de la columna |
| `presupuesto`, `ambitos` | «es capa intermedia», «es un catálogo de apoyo del build» | preferencia | **se van** |
| `partidas`, `obras`, `fases` | «para consultar X está `mart.v_pbi_dim_partida` / `maestro.obras` / `cierre.v_pbi_cierre_cabecera`» | preferencia | el puntero se conserva como **navegación**, sin el «no mires aquí» |

**Hallazgo: las advertencias de corrección son CUATRO, no dos.** El encargo
nombraba las de `plan_mensual` y `obras.activa`; repasando frase a frase salen
dos más de la misma clase —dan respuestas falsas, no incómodas—:
`version_master_vigente` y `ambitos.uso_seguimiento`. Las cuatro, reubicadas y
con su test.

### Verificación pedida: la de `plan_mensual` ya existía como regla dura

**Confirmado.** `00_global.yaml` declara **`R-VERSION-MASTER`**, título «En
stg.plan_mensual conviven TODAS las versiones master», severidad **bloqueante**,
con `stg.plan_mensual` en su `ambito`. Y como el validador **deriva `avisos`
desde el `ambito`** (R12), el aviso baja solo a la ficha aunque nadie lo escriba:
el agente no se quedaba sin ella en ningún caso. Igual la de `obras.activa`, que
tiene **`R-OBRA-ACTIVA`** y además vive en el `significado` de su columna. **Las
otras dos advertencias solo estaban en el motivo: esas sí se habrían perdido.**

## 3 · Fase RED (obligatoria en `estandar`)

Test escrito **antes** del cambio y commiteado solo, en rojo, en `ee2e9bf`.

Comando exacto:

```
python -m pytest tests/test_f079_stg_consultable.py -p no:cacheprovider -q --no-header --tb=line
```

Salida real (extractos; 19 fallos de 54):

```
E   AssertionError: stg.plan_mensual sigue desaconsejado para consulta: `stg` está entre los
    esquemas que el MCP puede leer, y desaconsejarlo solo consigue que el agente no mire donde sí hay dato
E   assert False is True
 +  where False = Ficha(esquema='stg', objeto='plan_mensual', ..., consumo_recomendado=False, ...)

E   AssertionError: sin inventariar: ['stg.ambitos', 'stg.fases', 'stg.obras', 'stg.partidas',
    'stg.plan_mensual', 'stg.presupuesto', 'stg.version_master_vigente']; inventariado y ya no está: []

E   AssertionError: la versión del diccionario no ha subido: lo que el MCP lea seguirá pareciendo lo de antes
    assert 17 >= 18

E   AssertionError: la cabecera de `00_global.yaml` no explica qué cambió en esta versión
    assert 'version 17' in '# config/diccionario/00_global.yaml # # El bloque global ...'

FAILED ...::test_f079_r1_los_siete_de_stg_son_consumo_recomendado[los 7 objetos]
FAILED ...::test_f079_r1_{no_queda_ningun_objeto_de_stg_desaconsejado_salvo_funciones,
                          el_esquema_stg_del_global_ya_no_dice_que_no_se_consulta}
FAILED ...::test_f079_r2_{la_trampa_de_las_versiones_master_sigue_en_la_ficha,
   la_columna_activa_de_stg_obras_sigue_avisando, version_master_vigente_avisa_de_que_es_global,
   ambitos_avisa_de_que_uso_seguimiento_esta_desfasado,
   el_presupuesto_conserva_sus_dos_trampas_sin_motivo,
   ninguna_ficha_de_stg_se_queda_sin_decir_a_donde_ir[stg.version_master_vigente]}
FAILED ...::test_f079_r3_el_inventario_de_lo_que_no_se_toca_esta_completo
FAILED ...::test_f079_r5_{la_version_del_diccionario_sube, el_changelog_del_global_explica_la_version_nueva}
19 failed, 35 passed in 54.54s
```

Mismo comando tras T2 y T3: **`53 passed in 24.34s`** (54 → 53: se retiró un test
propio que llamaba mal al validador, §5).

## 4 · Trazabilidad de los seis `acceptance`

| # | Criterio | Test / evidencia |
|---|---|---|
| 1 | los siete quedan recomendados sin motivo | `test_f079_r1_los_siete_de_stg_son_consumo_recomendado[7]`, `..._no_queda_ningun_objeto_de_stg_desaconsejado_salvo_funciones`, `..._el_esquema_stg_del_global_ya_no_dice_que_no_se_consulta`, `..._cumplen_lo_que_el_validador_exige_al_recomendado[7]` |
| 2 | ninguna advertencia se pierde, y se dice desde dónde | los seis `test_f079_r2_*` (§2 dice el «desde dónde») |
| 3 | grupos B y C inventariados y justificados | `test_f079_r3_*` (11 + 9 parametrizados) + `..._el_inventario_de_lo_que_no_se_toca_esta_completo` + `..._dicen_el_hecho_no_la_preferencia` |
| 4 | `check-diccionario` en 0 y biyección exacta | **MANUAL (humano)**: necesita conexión. Offline queda cubierto por `test_f006_r2_el_diccionario_global_real_valida_entero` y la puerta de `init.sh` |
| 5 | la versión sube y se publica | `test_f079_r5_la_version_del_diccionario_sube` (18) y `..._el_changelog_...`. **Publicar es MANUAL** |
| 6 | el MCP enruta a `stg` sin ayuda en el prompt | **MANUAL (humano)**: no se puede comprobar antes de publicar |

## 5 · Decisiones de diseño, y lo que se rompió al cambiar

1. **La entrada del esquema `stg` en `00_global.yaml` entra en el alcance
   aunque el encargo listara solo los siete objetos.** Decía literalmente «NO es
   superficie de consulta» y es **lo primero que el agente lee** para decidir
   dónde buscar: arreglar las siete fichas y dejarla habría dejado la feature sin
   efecto. Es exactamente la frase que el humano señaló.
2. **`raw` y `aux` se quedan fuera**, y no por descuido: `raw` es copia literal
   de Sigrid sin semántica (y el encargo lo excluye), y la tabla de `aux` se
   crea **vacía por diseño**. Ahí el aviso es un hecho.
3. **`capa: preparacion` no se toca** (dice dónde está el objeto en el pipeline,
   no si se consulta; el validador no acopla los dos campos), y **los punteros
   aguas abajo se conservan como navegación**: quitar la preferencia no es dejar
   al agente sin saber que `mart.v_pbi_dim_partida` existe. Un test exige que
   cada una de las siete fichas siga citando un objeto de otro esquema.
4. **Test roto por el cambio, arreglado:**
   `test_f006_formato.py::test_f006_r4_raw_y_stg_quedan_fuera_de_la_superficie_de_consumo`
   afirmaba `dicc.esquemas["stg"]["consumo_recomendado"] is False`. Pasa a
   llamarse `..._raw_y_aux_...`, **deriva** el conjunto de esquemas fuera de la
   superficie en vez de escribirlo a mano —así `aux`, que nadie comprobaba,
   queda cubierto— y su docstring deja escrito por qué `stg` entró y que la
   trampa de las versiones master no se fue con la marca. Es el único test de la
   suite que asumía lo contrario: se buscó `consumo_recomendado` en todo
   `tests/` antes de tocar nada.
5. **Test propio retirado en T2.** El de F-079 que validaba el diccionario
   entero llamaba a `validar(dicc, pasos)` pasándole el `hash_fuente` —el
   segundo valor que devuelve `cargar_diccionario` **no** son los pasos
   nocturnos—, y daba 136 errores falsos. Ya la hace bien
   `test_f006_formato.py::test_f006_r2_el_diccionario_global_real_valida_entero`.
6. **`azure-apps/datamart_seg_anual.md` NO hay que tocarlo**, comprobado: describe
   la **forma** del contrato con `mcp-bbdd` (qué tablas de `_meta` se publican,
   qué columnas tiene `_meta.v_diccionario`). Aquí no cambia ninguna columna ni
   ningún objeto publicado: cambia el **valor** de un campo. Nada que tocar en
   `docs/` tampoco.
7. **`progress/current.md`.** `test_f006_los_recuentos_de_current_son_los_de_hoy`
   obliga a decir los números de hoy: de consumo pasa de 47 a 54. La edición es
   quirúrgica —hay otra sesión trabajando en este repositorio— y todos los
   `git add` fueron de ficheros concretos.

## 6 · Fuera del alcance, y verificaciones MANUAL (humano) pendientes

Fuera: `mart.v_pbi_cp_tipologia` (la arregla F-078, en otra sesión); publicar (es
escritura contra Azure); la calidad de las fichas ahora que son superficie de
consulta (es F-070). No se ejecutó `ingest`, `stage`, `build-mart`, `run-all`,
`bootstrap` ni `publicar-diccionario`: contra Azure, solo lecturas.

Las tres MANUAL, también en `progress/current.md`. **Ningún agente puede
ejecutarlas**, y sin la 1 la feature no surte efecto:

1. `python main.py publicar-diccionario` — sin esto el MCP sigue leyendo la
   **versión 16** y `stg` le seguirá pareciendo desaconsejado.
2. `python main.py check-diccionario` — se espera **exit 0**, biyección exacta y
   versión publicada **18**.
3. Preguntar al MCP, **sin explicarle nada en el prompt**, algo que solo `stg`
   puede responder (el ámbito de certificación de una obra, que está en
   `stg.presupuesto` —no filtra por ámbito, verificado en
   `sql/stg/06_presupuesto.sql`— y en ningún sitio aguas abajo) y comprobar que
   **enruta a `stg`**.

## Evidencias

| Evidencia | Número real |
|---|---|
| Suite completa · `init.sh` de precondición | **4162 passed, 168 skipped** en **846,37 s** |
| Suite completa · `init.sh` de cierre | INIT-CIERRE |
| Tests propios de F-079 | **53 passed** en 24,34 s (19 en rojo en fase RED) |
| Cobertura de las líneas cambiadas | COBERTURA-CIERRE |
| Mutantes generados / evaluados | **288 / 20** (muestreo `estandar`, semilla `20260820`) |
| Muertos / supervivientes / timeouts / sin veredicto | **12 / 8 / 0 / 0** |
| **Workers** / tiempo total de la campaña | **4** / **2239,0 s** |
| Línea base (peor worktree) / media por mutante | **354,6 s** / **111,9 s** |

**Coherencia del tiempo (RM2 y coste por mutante):** `111,9 s × 4 workers =
447,6 s` de coste real por mutante frente a una línea base de **354,6 s** — por
**encima** de la base, coherente y muy lejos del segundo por mutante que delata
una campaña falsa. 0 sin veredicto, sin cabecera «CAMPAÑA NO VÁLIDA».

**Los ocho supervivientes están analizados uno a uno en
`progress/mutacion_F-079.md`, ninguno en `PENDIENTE`**, y se leen con un dato
delante: **el alcance medido no es el de F-079**. `harness.alcance` diffea la
RAMA contra `cd18e096` y arrastra 3.527 líneas de F-025, F-066, F-072 y F-074 —
**es el defecto que ya tiene ficha, F-075**—, y F-079 no toca una línea de Python
de producción. Los ocho son huecos preexistentes: siete, traducciones fila →
entidad en `postgres_client.py` y `ventana_sql.py` que ningún test ejecuta; el
octavo, `main.py:543`, ya con ficha **F-077**. **No se tapan aquí**: es código de
otra feature. El informe de mutación cierra proponiendo ficha para los siete.

**SHA medido (RM1): `bc1ce726cd9f050554efd64c209d8e25dbc4c140`.** Después llegan
`e17220e` —solo reordena dos párrafos de `stg.yaml`— y el commit de este informe:
ninguno toca Python, así que el alcance medido sigue siendo el de HEAD.
