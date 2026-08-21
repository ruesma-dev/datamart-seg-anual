<!-- progress/review_F-006.md -->
# F-006 · Review — el diccionario semántico

> **F-006, bloques A–D, E y F parcial: APROBADO** en la sexta pasada. La septima
> pasada revisa el diccionario completo (los 53 objetos restantes) y lo RECHAZA.
>
> Este fichero tiene **diez pasadas**, de la más reciente a la más antigua. Se
> conservan íntegras: son lo que se pidió corregir cada vez y el patrón contra el
> que se contrasta la siguiente. Leídas al revés cuentan cómo un diccionario que
> parecía correcto resultó tener un defecto sistemático en dos tercios de sus
> fichas, y cómo se cerró: derivando la comprobación en vez de revisando a ojo.

---

# DÉCIMA PASADA · 2026-08-21 — el vicio de fondo, cerrado

> Commits revisados: `ad88f9b`..`5bb6963`.

## Veredicto de la décima pasada

**RECHAZADO**, y **rectifico el APROBADO que ya había emitido**. Es la cuarta vez
en esta feature que me pasa lo mismo, y el patrón de mi error es siempre el
mismo, así que lo dejo escrito: **verifico el estado y doy por buena la defensa**.
Comprobé que hoy no queda ninguna copia —con mi propio barrido normalizado, y es
cierto— y de ahí di por bueno que el barrido *cubre* la superficie publicable. No
la cubre, y basta un experimento adverso para verlo.

Lo cerrado sigue cerrado y es mucho: los dos graves, el vicio de fondo de los
derivadores, `es_hoja`. Pero quedan **dos defectos en la superficie de consumo**,
uno en `stg`, un mecanismo que promete lo que no hace, dos recuentos declarados
que no cuadran y un ejemplo publicado que el SQL no soporta.

---

## Bloquean · están en la superficie de consumo

### 1 · `retenciones.entidad_cif`: el mecanismo publicado es falso, y va por cuadruplicado

La corrección acertó en la conclusión y falló en el porqué, que es lo que un
agente copia para escribir SQL. El texto nuevo dice:

> «La entidad **no tiene ficha de proveedor**: el `LEFT JOIN` con `raw.prv` no
> casa.»

Vale para la rama PROVEEDOR. **No vale para la mitad CLIENTE de la tabla**: en
`retenciones/01_movimientos.sql:107`, `entidad_cif` es el literal
`NULL::VARCHAR(24)`. Ahí no hay ningún `LEFT JOIN raw.prv` que pueda casar o no:
el NULL es una constante. Quien lea la ficha buscará una ficha de proveedor
ausente donde lo que hay es una columna que no existe para ese sentido.

Y el bloque de siete líneas está **duplicado literalmente en cuatro fichas**
—`movimientos`, `v_pbi_retencion_entidad`, `v_pbi_retenciones_vivas`,
`v_pbi_retenciones_vencidas`—: el arreglo de esta tanda ha creado, de un golpe,
cuatro copias que la próxima corrección tendrá que acertar a la vez.

### 2 · `maestro.proveedores_obra.razon_social`: el arreglo no llegó a la ficha hermana

En la misma tanda se corrigió `maestro.proveedores.razon_social` para decir que
una razón social sin informar llega como **cadena vacía** y nunca como NULL. Su
hermana, en el mismo fichero (`maestro.yaml:229-231`), sigue diciendo
`nulo_significa: La entidad no tiene ficha de proveedor, **o no tiene razon
social**`. El SQL es el mismo patrón —`maestro/03_proveedores_obra.sql:45`,
`pv.raz` en crudo con `LEFT JOIN raw.prv`—, así que la segunda mitad es falsa por
el mismo motivo que se acaba de corregir arriba.

---

## No bloquea la batería, pero hay que corregirlo · `stg`

### 3 · `pct_acumulado`, la cuarta hermana

Ya lo tenía localizado por mi cuenta y la auditoría llega a la misma columna:
`stg.plan_mensual.pct_acumulado` sigue en `suma_solo_dentro_del_mes` siendo un
porcentaje **acumulado** —lo dice su propio `significado`—, con `pct_mes` al lado
como la desacumulada y con `R-IMPORTE-MES` (bloqueante) incluyéndola en su
ámbito. Las otras cuatro columnas del mismo grupo sí pasaron a `ultimo_valor`.

Lo que lo explica está en el test: `tests/test_f006_stg_trampas.py:292` enumera
**a mano** `["can_origen", "importe_origen", "importe_origen_raw",
"total_incurrido"]`. El guardián se escribió a la medida del arreglo, así que no
podía ver la quinta. Es la octava instancia del patrón, y esta vez vive en el
test, no en la ficha.

---

## El mecanismo · el barrido de copias no cubre lo que dice cubrir

Se declaró que el barrido pasa a cubrir «toda la superficie publicable, no solo
las fichas». **No la cubre, y lo comprobé yo**: en un worktree aislado planté en
`stg.obras.motivo_no_consumo` —campo publicable— dos afirmaciones que las pasadas
séptima y octava rechazaron, plegadas como las pliega el propio YAML:

```yaml
      Se rehace cada noche con una ingesta incremental por
      `tiemod`, asi que no se refresca
      nunca.
```

Resultado: **`14 passed`**. Y lo que `yaml.safe_load` publica de ahí es
exactamente «ingesta incremental por `tiemod`, asi que no se refresca nunca»: las
dos frases rechazadas, servidas al MCP, con la batería en verde.

La causa está a la vista en el fichero: el barrido parametrizado sobre los diez
YAML mira **texto crudo**, y una frase partida por el salto de línea que `>-`
introduce es invisible para él; el que sí normaliza el plegado **solo lee
`00_global.yaml`**. La protección que funciona es justo la que no se extendió a
los otros nueve ficheros. Y `BLOQUES_PUBLICABLES` es una **constante muerta**: no
la usa ninguna función.

El arreglo es de una línea: que el barrido normalizado recorra
`str(yaml.safe_load(...))` de los **diez** ficheros. Y conviene, porque los
defectos 1 y 2 de arriba son justamente lo que ese barrido debería haber cazado.

---

---

## Dos recuentos declarados que no cuadran

No cambian el veredicto, pero sí lo que uno cree que está protegido.

**Las correcciones del guardián son nueve, no diez.** El desglose real es **4 + 5**:
las cuatro que ningún sufijo cazaba (`maestro.proveedores.razon_social`,
`stg.ambitos.codigo`, `.descripcion`, `.clase_sigrid`) y **cinco** del punto ciego
del `INSERT … SELECT` (`stg.obras.codigo_obra`, `.nombre_obra`,
`stg.partidas.descripcion_corta`, `stg.fases.anio`, `.mes`). El propio mensaje de
commit que anuncia «seis» **enumera cinco**. `entidad_cif` no cuenta como décima:
el guardián **no la marca** —llega por `LEFT JOIN`, donde el NULL sí es posible— y
su arreglo fue de significado, no de posibilidad.

**Y las tablas que dejaron de saltarse son cinco, no tres.** Lo medí: el guardián
evalúa ahora **seis** objetos de `stg` —`ambitos`, `fases`, `obras`, `partidas`,
`plan_mensual` y `presupuesto`—, y el docstring que documenta el arreglo
(`tests/test_f006_fichas.py:571`) nombra solo `partidas`, `fases` y
`plan_mensual`. Quedan sin mencionar **`stg.obras`** —que aportó **dos** de los
cinco hallazgos— y **`stg.presupuesto`**. El control se escribió sobre la lista
corta, así que fija menos de lo que el arreglo consiguió.

## Por qué `pct_acumulado` era invisible: la derivación tiene un punto ciego estructural

La comprobación nueva de coherencia dentro del ámbito de cada regla
(`tests/test_f006_stg_trampas.py:266`) **funciona y no es un falso control**: su
control comparte el accesor del ámbito, pero fija literales, así que al encoger
el ámbito la comprobación pasa en vacío y **el control falla**. Correcto.

Lo que no puede ver es otra cosa: compara **la misma columna declarada en varios
objetos** del ámbito. Una columna que existe en **uno solo** —y `pct_acumulado`
existe solo en `stg.plan_mensual`— no tiene con qué compararse y es invisible por
construcción. Comprobado: marcarla `clave_sustituta` deja la batería entera en
verde. Por eso el defecto no se detectó ni por la lista escrita a mano ni por la
derivación: hacían falta las dos y ninguna la alcanza.

## Un ejemplo publicado que el SQL no soporta

`stg.yaml:594-598` explica —con razón— que el filtro `f.anio IS NOT NULL` de
`08_plan_mensual.sql:328` no descarta nada, y lo ilustra diciendo que «una fase
con `anio = 0` **entra igual**». No entra: dos líneas antes, la misma `SELECT`
hace `make_date(f.anio, f.mes, 1)` (`:319`), y `make_date` **rechaza el año 0**
—«year 0 is out of range»—. Una fase así no entraría: **abortaría el build**. El
punto de fondo se sostiene; el ejemplo concreto, no.

## Rectificación de un test mío

La tarea C del encargo era juzgar si el implementer tenía razón al corregir un
test que escribí yo en la séptima pasada. **La tiene, y yo estaba al revés.**
Aquel test afirmaba que `stg.fases.anio`/`.mes` podían ser NULL y que
`stg.plan_mensual` descartaba esas fases. Es falso: `stg/05_fases.sql:26-27`
proyecta `f.ano` y `f.mes` **en crudo** desde `raw.obrfas`, sin `NULLIF` —y en la
línea de al lado sí lo ponen donde lo querían: `NULLIF(TRIM(f.res), '')`—, así
que con la convención de Sigrid el «sin informar» llega como 0 y el filtro es
inerte. La premisa nueva es la correcta.

## `es_hoja`: cerrado, con dos matices menores

La corrección es cierta y está en las dos vistas, y el fenómeno que denuncia es
estructural: `capitulo_padre_id` existe en `stg.partidas` y el árbol llega a seis
niveles. Dos imprecisiones que no bloquean: la receta que propone —«bajar al
último nivel de la jerarquía»— sugiere un `MAX(nivel)` cuando la profundidad es
variable y el criterio exacto es «ninguna fila la apunta con `capitulo_padre_id`»,
columna que **ninguna de las dos vistas proyecta**; y el ejemplo llama «nivel 2» a
`CI.2`, que con `CI` como raíz es nivel 1.

---

## GRAVE 2 · el derivador, verificado con uno que no comparte linaje

Es lo que se me pidió atacar, porque en la novena pasada mi verificación y la
suya coincidieron **en el mismo error**. Así que esta vez escribí un derivador
**desde cero**, con otro diseño: trocea cada fichero en **sentencias**
—respetando los bloques `$$` de las funciones—, resuelve el mapa alias→tabla
**dentro de cada sentencia** y solo entonces busca `alias.campo`. No reutiliza
ni una línea del repositorio ni de mi script anterior.

Resultado: **13 tablas**, y contrastado contra lo que la regla publica hoy,
**coincidencia exacta, campo a campo**:

`auxmun`(res) · `auxobramb`(cod,res) · `auxobrcla`(res) · `auxobrtip`(res) ·
`auxpro`(res) · `conext`(cod) · **`ctrpro`(res)** · **`dcapro`(res)** ·
`dcfpro`(res) · `obrfas`(res) · `obrfasamb`(fec,res) · `obrparpar`(cod,res) ·
`prv`(cif,raz)

Las dos que faltaban están dentro. El diagnóstico era el correcto: el alias es
local a la sentencia, y `l` era `ctrpro`, `dcapro` y `dcfpro` en el mismo fichero.

**Y el vicio de fondo está cerrado, que es lo que importaba más.** Los controles
nuevos no comparten linaje con lo que controlan:

| Control | Qué hace |
|---|---|
| `..._el_derivador_no_pierde_un_alias_repetido` | SQL **fabricado** con el caso exacto del bug y **la respuesta escrita a mano**: `{"ctrpro": {"res"}, "dcapro": {"res"}}`. Un derivador por fichero lo suspende |
| `..._el_troceo_en_sentencias_separa_los_ambitos` | Fija que `SELECT … raw.a x; SELECT … raw.b x;` da `{x: a}` y `{x: b}`, no uno solo |
| `..._las_tres_lineas_de_compras_existen_de_verdad` | Contraste del **fichero real por otra vía**: lee líneas con su propia regex y **no usa `alias_de_raw` ni `sentencias`**. Si el derivador vuelve a perder una tabla, este no se entera de la misma manera |

Eso es exactamente lo que hacía falta: el control ya no puede confirmar el error
del derivador con el mismo error. Se acaba una clase entera de falsos verdes.

## GRAVE 1 · la copia borrada, y ninguna más en lo publicable

`convenciones.identidad_sigrid` ya no repite la regla: **remite** a ella y dice
por qué, dejando la lección escrita para el siguiente que pase:

> «**Lo que hay que saber antes de consultar `raw` esta en la regla
> `R-SIGRID-CON`, que es la unica version** […]. Esta entrada no lo repite a
> proposito. Cuando lo repetia, se quedo atras […]. Eran dos versiones publicadas
> que se contradecian.»

Barrí **toda la superficie publicable** de los diez YAML —lo que sobrevive a
`yaml.safe_load`, con el texto normalizado sin tildes y sin plegado de línea—
buscando las ocho afirmaciones que revisiones anteriores rechazaron: «viven en
`con`», «no en la extension», «no en la tabla especifica», `cen.res`, «Reparto
nombre», `--full-refresh`, «incremental por `tiemod`» y «no se refresca nunca».
**Cero coincidencias: el estado de hoy es limpio.**

Lo que **no** puedo dar por bueno es la defensa: el barrido del repositorio no
cubre esa superficie, y lo demuestro en §«El mecanismo». Estado limpio y defensa
incompleta son dos cosas distintas, y confundirlas es lo que me llevó a aprobar
antes de tiempo.

## El guardián sin sufijos, medido

Dejó de perseguir nombres y comprueba la afirmación real —«columna proyectada en
crudo desde `raw` que declara `nulo_significa`»—. Lo medí antes y después:

| | Novena pasada | Ahora |
|---|---|---|
| Fichas evaluadas | 15 | **20** |
| Fichas de `stg` dentro | 1 (`ambitos`) | **6** (`ambitos`, `fases`, `obras`, `partidas`, `plan_mensual`, `presupuesto`) |
| Columnas recorridas | 30 | **95** |
| Saltos «no lee de `raw`» | 45 | **40** |

El punto ciego está cerrado: las tablas de `stg` se pueblan con `INSERT … SELECT`
en un fichero distinto del que las declara, y el guardián las saltaba con un
motivo que era **falso** —decía que no leen de `raw` cuando sí lo hacen—. Ahora
concatena los ficheros que **declaran o pueblan** el objeto.

Cero columnas llegan hoy al `assert`, pero esta vez eso significa lo correcto:
las que llegaban se corrigieron, y el detector tiene desde la octava pasada un
control que distingue «cero por sano» de «cero por roto».

## Rigor e higiene

- **1828 tests**, 122 saltados, cobertura **99,0 %**, ejecutado por mí.
- **Mutación recalculada con el `__pycache__` borrado**: 2358 líneas, **166
  mutantes**, 0 supervivientes, 0 timeouts.
- **Nada prohibido**: el diff toca cinco YAML, cuatro ficheros de tests y
  `progress/`. Ni un `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base.
  **`harness/` intacto** y **sin `push`**.
- Mi novena pasada quedó preservada en un commit propio, sin alterar su contenido.

## La superficie de consumo: uno cerrado, dos abiertos

**`es_hoja` sí está cerrado**, y bien, en **las dos** vistas
(`mart.v_pbi_dim_partida` y `v_pbi_dim_partida_niveles`): retirada la promesa y
sustituida por la verdad, con el ejemplo concreto —«un **capitulo** intermedio de
nivel 2 con descendientes —`CI.2`, con `CI.2.1` debajo— sale marcado como hoja
igual que ellas. Por eso **no evita el doble conteo**»—.

**`entidad_cif` no**: la conclusión es correcta y el mecanismo publicado es falso
para la mitad CLIENTE de la tabla (defecto 1). Y aparece un tercero que esta
tanda dejó atrás, `maestro.proveedores_obra.razon_social` (defecto 2).

Corrijo aquí lo que escribí antes de tener la auditoría: **la superficie de
consumo no está limpia**. Lo que sí sigue siendo cierto es que sus 47 fichas y
644 columnas no tienen ningún defecto de los grandes —columnas inventadas,
granos falsos, claves que no identifican, acumulados marcados sumables—: los dos
que quedan son afirmaciones sobre *por qué* una columna es nula.

## Alcance y qué falta para la batería

El diccionario está **estructuralmente completo**: bloques A a G, **102 fichas
para 102 objetos publicados, 793 columnas, 13 reglas duras y `pendientes` en 0**,
más el contrato de `_meta` con `mcp-bbdd` y el paso que lo publica. Lo que falta
para aprobarlo son los cuatro puntos de arriba, ninguno estructural.

Para poder pasar la batería de aceptación hace falta, por este orden:

1. **Los cuatro defectos de esta pasada**, empezando por los dos de consumo.
2. **T19**: `python main.py publicar-diccionario` contra la base real y las tres
   consultas de comprobación del contrato. Es la primera vez que algo de esto se
   ejecutará contra un PostgreSQL: la adaptación de tipos de psycopg, el `JSONB`,
   los `TEXT[]` y el `CHECK (id = 1)` están sin probar, y está declarado.
3. **T26/T27**: `check-diccionario` contra el catálogo real, **con la consulta de
   unicidad de clave**. Es lo único que convierte «102 objetos» en una verdad
   comprobada y no en lo que ve una expresión regular, y lo único que puede
   cerrar las claves compuestas que el análisis estático no decide.
4. **T39**: las 18 preguntas contra el diccionario publicado —13 respondibles, 3
   parciales y 2 que deben contestarse con un «no puedo, y este es el motivo»—.
   Ese es el criterio de éxito de F-006.
5. Los bloques 🔏 de permisos y firewall, que necesitan firma del humano y no
   condicionan la batería.

**Deuda declarada que viaja** y que conviene no perder: el falso positivo del
detector de multifuente (`COALESCE` de dos ramas del mismo objeto); los menores 5
a 7 de la sexta pasada; **F-041**, para que «cero supervivientes» signifique lo
que dice; los comentarios del SQL que mienten —ya mordieron una vez con
`dec_cantidades`—; y la lista del punto 4 de `R-SIGRID-CON`, que es conservadora
y cuyo enunciado se lee cerrado.

---

# NOVENA PASADA · 2026-08-21 — el criterio, y la copia que sobrevivió

> Commits revisados: `0f9bb54`..`7ffd1e0`.

## Veredicto de la novena pasada

**RECHAZADO.** Y **rectifico un APROBADO que ya había emitido**: lo di apoyándome
en mis propias comprobaciones, con una auditoría de barrido todavía corriendo.
Al llegar encontró dos cosas que yo no vi, y una de ellas **demuestra que mi
verificación estaba mal hecha**. Las he confirmado las dos contra el código.

El criterio —lo que no se pueda derivar de la fuente que gobierna el hecho, no se
afirma— **sí está aplicado en el texto de la regla**, y eso es real y valioso.
Lo que falla es que **el derivador tiene un bug** y que **la afirmación
rechazada sigue publicada doce líneas más abajo, en el mismo fichero**.

### Lo que me corrige a mí

Escribí que había reproducido la lista del punto 3 «con mi propio derivador» y
que daba «exactamente las mismas once tablas». Es cierto que coincidía, pero
**coincidía porque mi script tenía el mismo bug que el suyo**: los dos
construimos el mapa alias→tabla **por fichero**, con un `dict` que machaca la
clave. En `compras/01_documentos.sql` las tres tablas de línea comparten el alias
`l` —`FROM raw.ctrpro l` (:61), `FROM raw.dcapro l` (:126), `FROM raw.dcfpro l`
(:179)— y las tres proyectan `l.res AS descripcion` (:52, :103, :167). El `dict`
se queda con la última, así que el `res` de las tres se atribuye solo a
`dcfpro`. Dos derivaciones con el mismo error no son una verificación
independiente: son el mismo error dos veces. Lo doy por lección propia.

---

## Los defectos

### 1 · El sexto superviviente, y esta vez publicado (GRAVE)

`config/diccionario/00_global.yaml:399-403`, en `convenciones.identidad_sigrid`:

> «En Sigrid `ide` es la clave universal y muchas tablas son "propiedades de
> `con` 1:1" […]. El codigo (`cod`), el nombre (`res`) y la fecha (`fec`) viven
> en `con`, **no en la extension**. `con.nom` NO existe.»

Es **la afirmación que la séptima pasada rechazó**, viva y en contenido
**publicable** —no en un comentario, como el quinto caso—, y **contradice al
punto 3 de `R-SIGRID-CON` doce líneas más abajo en el mismo fichero**, que
enumera once tablas cuyos `cod`/`res`/`fec`/`cif`/`raz` propios lee el ETL sin
pasar por `con`. El MCP publica las dos. Y las dos listas de «propiedades de
`con`» divergen: **ocho** tablas aquí, **diez** en el punto 2.

**Por qué no lo cazó el detector nuevo**: `tests/test_f006_copias.py` es una
lista negra de **subcadenas literales**. Busca `"no en la tabla especifica"`; aquí
pone `"no en la extension"`. Es además sensible a tildes y mayúsculas y —lo
decisivo— **ciega al plegado de línea**: en un bloque `>-` cualquier frase de la
lista partida por un salto es invisible. Lo que sí compara afirmaciones es
`test_f006_fuente_que_gobierna.py`, pero su alcance son las 31 fichas de `raw`, y
`00_global.yaml` queda fuera.

### 2 · La lista «derivada» está incompleta por un bug del generador (GRAVE)

Por la colisión de alias descrita arriba, el punto 3 publica `dcfpro` (`.res`) y
**omite `ctrpro` y `dcapro`**, que cumplen el mismo criterio en el mismo fichero.

Lo agravante no es la omisión, son tres líneas: es que
`test_f006_r9_la_regla_declara_exactamente_los_campos_derivados` compara la regla
**contra la misma derivación defectuosa**. Está verde por construcción y no puede
detectar el fallo. Y el `motivo` de la regla vende esa lista como garantía: «la
genera un test […] y la regla queda en rojo si dejan de coincidir». Mis pruebas
P1 y P2 de esta misma pasada —quitar `obrparpar`, añadir una tabla inventada— sí
saltaron, y por eso di el mecanismo por bueno: fijan la **coherencia** entre
regla y derivador, no la **corrección** del derivador.

Arreglo: resolver el alias por ámbito de consulta y no por fichero, y añadir al
control un caso con alias repetido, que es justo lo que el repositorio ya tiene.

### 3 · `stg.plan_mensual` contradice a una regla bloqueante que la incluye (MEDIA)

Cuatro columnas acumuladas pasaron a `suma_solo_dentro_del_mes`:
`importe_origen`, `importe_origen_raw`, `can_origen` y `pct_acumulado`
(`stg.yaml:126,149,159,168`). Pero `R-IMPORTE-MES` es **bloqueante**, su `ambito`
**incluye `stg.plan_mensual`** (`00_global.yaml`) y dice que el acumulado ya
lleva dentro los meses anteriores. Las **doce** columnas equivalentes de `mart`
—`fact_seguimiento_mensual`, `fact_seguimiento_categoria`, `v_pbi_fact`,
`v_pbi_fact_categoria`, `v_fact_periodificado`— siguen todas en `ultimo_valor`,
que es lo correcto. La misma magnitud, en el linaje directo, con dos etiquetas
opuestas, y la de aguas arriba contradiciendo la regla que se le adjunta.

`pct_acumulado` es peor: es un **porcentaje** (`unidad: "%"`), y sumar
porcentajes de avance de partidas distintas no significa nada.

*(Aviso: aquí yo mismo leí mal primero con `sed` y creí que `mart` había
cambiado. No: `mart` está intacto, lo verifiqué parseando los diez YAML.)*

### 4 · La receta de `sigrid_tablas.md` es falsa en 25 de 31 fichas (MEDIA)

La coletilla nueva dice que `grep -n "^| <tabla> "` devuelve «tambien las filas
de otras tablas con un campo llamado así». Ejecutado contra el documento: **25 de
31 devuelven exactamente una línea**, así que describe filas que no existen. En
las seis restantes la regla de desambiguación —«la de entidad es la que lleva la
descripcion en la segunda columna»— **no desambigua** (las filas de campo también
la llevan) y **en `con` está invertida**: su fila de entidad es
`| con Conceptos | | ETC | |`, con la segunda columna **vacía**. Seguir la receta
en la ficha de `con` lleva al sitio equivocado.

### 5 · El `motivo` promete una procedencia que el punto 2 incumple (MEDIA)

«Todo lo que afirma esta regla se **deriva de este repositorio**». El punto 2
—«**Diez** tablas son "Propiedades de `con`" en 1:1»— no es derivable: ningún SQL
une `prv`, `cen`, `com`, `dca`, `dcf`, `cob`, `pag` ni `rec` a `con` por `ide`
(solo `obr`, en `maestro/01_obras.sql:30`). Su única fuente es el PDF que el
mismo `motivo` declara no apto. El número es correcto —diez de las 31—, pero el
cambio de «Muchas» a «**Diez**» endurece a exhaustiva una afirmación no
verificable, justo cuando el `motivo` presume de lo contrario.

### Menores

6. El desglose de exclusiones de `dca` y `dcf` **no suma**: «6 de direcciones, 2
   de descripciones largas, 2 de observaciones, 11 sueltas» = 21, y son 23
   (`raw.yaml:1054-1056`, `:1140-1142`). El test comprueba el total y los nombres
   citados, no que el desglose cuadre.
7. `stg.yaml:443`: `capitulo_raiz_cod` quedó con `nulo_significa: null` en vez de
   documentar que nunca es NULL, como sus tres hermanas. Y la razón que da
   `codigo_partida` (`:414-417`) es inventada: lo que protege a las descendientes
   es su propio filtro (`04_partidas.sql:77-78`), no el del padre.

---

## Lo que sí está bien, y es mucho

- **El criterio está aplicado en el texto**: el mapa fuente→hecho de la cabecera
  de `raw.yaml`, el recorte de lo insostenible (`cen.res`, `obr.res`, las cuatro
  excepciones falsas) y el hueco declarado con su fuente son exactamente lo
  pedido. **Al rechazar los `entcif` que yo sugería tiene razón y me corrige**:
  los propuse desde el mismo PDF que ya había producido dos afirmaciones falsas.
- **El ancla de la carga es correcta y completa**: cita el `CMD ["run-all",
  "--full"]` real y cubre los dos caminos sin negar ninguno. Las 31 citas de
  `--full-refresh` fuera, contrastadas contra los `click.option`.
- **La reversión del retoque de `06_presupuesto.sql` está limpia**: en toda la
  feature el único SQL tocado es el DDL nuevo del contrato. Revertir en vez de
  debilitar el guardián de F-011 es la decisión correcta, y `dec_cantidades`
  quedó cerrado por otra vía y mejor: dice que no interviene y **avisa de que los
  comentarios del SQL repiten una fórmula que el código no ejecuta**.
- **`_source_tiemod`** cerrado y bien anclado; **`stg.presupuesto`** corregido con
  la prosa exacta («sumable dentro de UNA fase, nunca a través de `fase_num`») y
  el reconocimiento de que se pasó con `ultimo_valor`; el «cinco cosas» ya dice
  seis; y el **control que le faltaba al guardián de nulos** existe, mide el
  detector sobre un caso fabricado y admite que está en cero.
- **El punto 4 de la regla es cierto**, verificado tabla a tabla: `auxobramb`,
  `obrfas`, `obrfasamb` y `obrparpre` no se unen a `raw.con` en ningún SQL.
- **Mutación** recalculada con el bytecode borrado: 2358 líneas, 166 mutantes, 0
  supervivientes, 0 timeouts. `pendientes` en 0, 102 fichas ↔ 102 objetos. Nada
  prohibido, sin `push`, `harness/` intacto.

---

---

## Y SÍ hay defectos en la superficie de consumo

Esto responde directamente a la pregunta de alcance, y la respuesta cambia la
decisión: **recortar `raw` no basta**. Una revisión fresca de los seis esquemas
recomendados —60 fichas, 707 columnas, 50 claves (25 compuestas), 84 relaciones y
214 `nulo_significa`, contrastadas una a una— los encuentra **sustancialmente
sanos** pero con **dos defectos de gravedad media**, los dos verificados por mí:

### C1 · `mart.v_pbi_dim_partida.es_hoja` promete lo que no cumple (MEDIA)

La ficha (`mart.yaml:567-569`) dice: «Marca las partidas de detalle frente a los
capitulos, **para no sumar dos veces al agregar por la jerarquia**». El SQL
(`mart/05_views_powerbi.sql:58-60`) es una heurística:

```sql
CASE WHEN nivel >= 2 OR codigo_partida LIKE '%.%' THEN TRUE ELSE FALSE END AS es_hoja
```

Un **capítulo intermedio** de nivel ≥ 2 sale `es_hoja = TRUE`. Que los árboles
llegan más hondo lo prueba la vista hermana, que tiene `nivel_1..nivel_6`. Filtrar
`es_hoja = TRUE` y sumar puede contar el capítulo **y** sus hijos: doble conteo de
importes, en `mart`, que es la superficie principal. El comentario del propio SQL
es más prudente que la ficha («útil para filtrar si se quiere solo partidas
hoja»), y existe `stg.partidas.capitulo_padre_id`, con el que la prueba de hoja
sí sería exacta. Arreglo: declararlo heurística y retirar la promesa.

### C2 · `entidad_cif` sin sanear, y cuatro fichas documentan un NULL que no llega (MEDIA)

`retenciones/01_movimientos.sql:59` proyecta `prv.cif AS entidad_cif` **en crudo**.
El mismo origen, en los dos maestros, sí se sanea: `maestro/02_proveedores.sql:28`
hace `NULLIF(TRIM(p.cif), '') AS cif`. Que el propio repositorio lo envuelva ahí
es la prueba de que los blancos ocurren.

Cuatro fichas declaran `nulo_significa: La entidad no tiene CIF en el maestro`
—`movimientos`, `v_pbi_retencion_entidad`, `v_pbi_retenciones_vivas` y
`v_pbi_retenciones_vencidas`—, así que `WHERE entidad_cif IS NULL` pierde en
silencio a los proveedores con CIF en blanco. Y `maestro.proveedores.cif` sí lo
dice bien («no tiene CIF, **o esta en blanco**»), lo que deja la incoherencia a la
vista dentro del mismo diccionario.

**Lo importante es por qué se escapó**: es el tercer caso de la misma familia que
ya corregimos dos veces —`cierre.v_pbi_cierre_cabecera.cliente_ide` en la tercera
pasada, `maestro.obras.cliente_id` en la séptima—. El guardián se amplió entonces
de `_ide` a `_id`; ahora se escapa por `_cif`. **Persigue sufijos en vez de
derivar**: lo derivable es «columna proyectada en crudo desde una tabla de `raw`
que declara `nulo_significa`», sin mirar cómo se llama.

### Menores en consumo (omisión, no falsedad)

`nulo_significa` más estrechos que la realidad en `cierre` (`fase_numero`,
`fase_nombre_mes`, `fase_fecha_inicio` y las derivadas de periodificación, que
también son NULL cuando la venta final es 0 o falta el importe de fase 0); nueve
columnas de fecha en `compras` sin `nulo_significa` pese a que
`compras.fn_sigrid_date(0)` devuelve NULL —un `WHERE anio = 2025` descarta en
silencio los documentos sin fecha—; `nivel_1`/`nivel_2` sin el `nulo_significa`
que sí llevan `nivel_3..6`; y el grano de `v_master_vigente_anual`, que dice «31
de diciembre si el año ya pasó, hoy si es el año en curso» cuando el `CASE` usa
`hoy` también para años futuros.

Queda además un **riesgo no verificable sin base**: la clave de
`v_master_versiones_tipadas` es una terna sobre un `SELECT DISTINCT` de ocho
columnas; se sostiene solo si las otras cinco dependen de ella. Es material para
la consulta de unicidad de T26.

### Lo que en consumo está limpio, y conviene decirlo

Las 707 columnas existen y pertenecen **a su** objeto —comprobado también en los
ficheros que crean varios—; ni un grano falso; las 25 claves compuestas
identifican una fila, incluidas las tres históricamente frágiles
(`v_pbi_proveedor_obra` con sus seis columnas, `v_pbi_partida_coste` con cinco,
`v_pbi_retencion_obra` con tres); ni un `COUNT(DISTINCT)` marcado `suma`; todos
los acumulados en `ultimo_valor`; y **las seis trampas de negocio están en campos
publicables y son ciertas**. Los dos casos peligrosos de `*_ide` sin `NULLIF`
—`maestro.obras.cliente_id` y `cierre.v_pbi_cierre_cabecera.cliente_ide`— están
correctamente documentados como no nulables, que era justo lo que se corrigió.

### Dos incoherencias más en el bloque global

`esquemas.compras.pasos_etl: []` y `esquemas.retenciones.pasos_etl: []`
contradicen el `paso_etl: build_compras` / `build_retenciones` que llevan todas
sus fichas; y `esquemas._meta.pasos_etl` omite `publicar_diccionario`, que es
precisamente el paso que escribe las tablas del diccionario y el que declaran sus
cuatro fichas.

---

## Dónde caen los defectos, para la decisión de alcance

Se pidió separar lo que está en `raw` de lo que toca a los esquemas de consumo:

- **Ninguno de los siete está en `mart`, `cierre`, `compras`, `retenciones`,
  `maestro` ni `_meta`**. Esta tanda no toca esos seis ficheros, y las doce
  columnas de `mart` que podían haberse contagiado siguen correctas.
- **Pero dos no son «solo `raw`»**: el defecto 1 y el 5 están en
  `00_global.yaml`, que el MCP publica **entero** y sirve a cualquier consulta,
  sea del esquema que sea; y el 3 pone a una ficha a contradecir una regla
  `bloqueante` cuyo ámbito abarca cinco objetos de `mart` y cuatro de `cierre`.
  El bloque global no es zona acotable.

Así que la respuesta a la pregunta de fondo es: **recortar `raw` no cierra esto**.
Los defectos 1, 2 y 5 viven en la regla y en las convenciones globales, y el 3 en
`stg`. Lo que sí sigue siendo cierto es que **el contenido de las 47 fichas de
consumo, con sus 644 columnas, no está en cuestión**: si se quiere avanzar hacia
la batería, el camino es cerrar estos siete —los dos graves son un borrado y un
`dict` mal construido— y no seguir puliendo fichas de `raw`.

---

---

## El criterio: aplicado de verdad, no de nombre

La instrucción era: **lo que no se pueda derivar de la fuente que gobierna el
hecho, no se afirma; se omite, y si el hueco importa se declara como hueco.**
Lo ha aplicado, y se puede comprobar sin creerle:

1. **Hay un mapa explícito fuente→hecho** en la cabecera de `raw.yaml`: qué corre
   de noche → el `Dockerfile`; cómo carga según la bandera →
   `ingest_raw_step.py`; cómo se llama la bandera → los `click.option` de
   `main.py`; qué campos propios existen → nuestro SQL. Cada afirmación tiene
   una fuente asignada, y son las que gobiernan cada hecho.
2. **La lista del punto 3 la reproduje por mi cuenta.** Escribí mi propio
   derivador —para cada alias de una tabla de `raw`, usos de `.cod`, `.res`,
   `.fec`, `.raz`, `.cif`— y da **exactamente las mismas once tablas con los
   mismos campos**: `auxmun`(res), `auxobramb`(cod,res), `auxobrcla`(res),
   `auxobrtip`(res), `auxpro`(res), `conext`(cod), `dcfpro`(res), `obrfas`(res),
   `obrfasamb`(fec,res), `obrparpar`(cod,res) y `prv`(cif,raz). Incluye
   `obrparpar.cod`/`.res`, que era el hueco que más pesaba.
   De paso me corrijo: en la octava pasada di `dcfpro.res` por dudoso; **existe
   y se lee** (`compras/01_documentos.sql:167`, `l.res AS descripcion` sobre
   `FROM raw.dcfpro l`).
3. **El mecanismo cierra los dos sentidos**, que es lo que faltaba en las pasadas
   7 y 8. Lo probé en un worktree:

   | Prueba | Resultado |
   |---|---|
   | Quitar `obrparpar` de la lista de la regla | **detectado** — la regla no puede quedarse corta |
   | Añadir una tabla inventada (`comlin`) | **detectado** — la regla no puede inventar |

   El test compara lo declarado con lo derivado exigiendo **igualdad**, y muestra
   la diferencia en los dos sentidos. Con esto, el defecto que causó los dos
   rechazos anteriores no puede repetirse en silencio.
4. **Recortó lo que no podía sostener y declaró el hueco.** Fuera `cen.res`
   (inventado), `obr.res` (solo lo respaldaba el PDF) y las cuatro excepciones
   falsas. Y el `motivo` dice qué deja de decir y a dónde ir:

   > «**Lo que esta regla NO dice, y es deliberado**: que campos existen en
   > Sigrid y el datamart no lee. Esa pregunta solo la responde
   > `azure-apps/sigrid_tablas.md` […]. Para preguntar por una columna concreta,
   > ese documento; para fiarse de una afirmacion, este repositorio.»

   Eso es exactamente lo pedido: omitir y declarar el hueco con su fuente.
5. **Al rechazar los `entcif` que yo sugería, tiene razón y me corrige.** Los
   propuse desde el mismo PDF cuyo segmentador ya había producido dos
   afirmaciones falsas; son misma fuente y mismo riesgo. Rechazarlos es aplicar
   el criterio también contra la sugerencia del reviewer, que es la parte difícil
   de aplicarlo.

## Lo demás que declaraba, verificado

| Punto | Veredicto |
|---|---|
| **El ancla de la carga** | **Correcta y completa.** La cabecera cita el `CMD ["run-all","--full"]` real, y las fichas cubren **los dos caminos** sin negar ninguno: de noche recarga entera, sin `--full` append por `MAX(ide)`. Es la corrección del defecto 6 de la octava pasada, hecha contra la fuente que gobierna qué se ejecuta |
| **Las 31 citas de `--full-refresh`** | Fuera; ahora se contrasta contra los `click.option` reales, y hay test que reconoce una bandera inventada |
| **La reversión del retoque de `06_presupuesto.sql`** | **Limpia**: `git diff a7cccdd..HEAD -- etl_sigrid/` está vacío. Y en **toda la feature** el único SQL tocado es `sql/ddl/01_diccionario.sql`, el DDL nuevo del contrato: **ni un SQL de negocio modificado**, que es la regla de hierro 3 de esta feature. Revertir en vez de debilitar el guardián de F-011 es la decisión correcta |
| **`dec_cantidades`** | **Cerrado por otra vía y mejor**: la ficha dice ahora que **no interviene**, da la fórmula real y **avisa de que los comentarios del SQL repiten una fórmula que no es**. Convierte la deuda en aviso en vez de tocar el SQL |
| **`stg.presupuesto`** | Corregido: `cantidad` e `importe` quedan en `suma_solo_dentro_del_mes`, que es lo exacto —sumar entre partidas de la misma fase es correcto; entre fases, no—. Reconocer que se pasó con `ultimo_valor` es la lectura buena: lo no sumable era la dimensión |
| **Mutación** | Recalculada con el `__pycache__` borrado: **2358 líneas, 166 mutantes**, idéntico a lo declarado, 0 supervivientes y 0 timeouts. `harness/mutacion.py` intacto |
| **Higiene** | Nada prohibido: ni `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**. Árbol limpio y sin worktrees huérfanos |

---

# OCTAVA PASADA · 2026-08-21 — la regla de oro y la carga de `raw`

> Commits revisados: `f1d449f`..`a7cccdd`.

## Veredicto de la octava pasada

**RECHAZADO.** Las dos correcciones centrales de la tanda —la regla de oro y la
carga de `raw`— **sustituyeron una afirmación falsa por otra**, y en los dos
casos la nueva es falsa en dirección contraria. No es un matiz: la regla es
`bloqueante` y se adjunta a las 31 fichas del origen, y la carga es lo que le
dice al agente cuán viejo es el dato que está leyendo.

Lo demás de la tanda está bien, y una parte muy bien: el fallo de
`_proyeccion_de` **no tuvo efecto retroactivo** —medido por dos vías
independientes—, las seis fichas de `compras` revalidadas no tienen ni una
columna ajena, la biyección 102↔102 es exacta y la mutación cuadra con el
bytecode limpio.

**Rectifico además una frase de mi propio borrador**: escribí que el guardián de
nulos «pasa de cubrir 1 ficha a 15». Eso describe el bucle, no la comprobación:
lo medí y **cero columnas llegan hoy al `assert`** (defecto 12).

---

## Los defectos

### A · La regla de oro: 1 de 7 excepciones es correcta

1. **`cen.res` no existe: la regla vuelve a inventar un campo (GRAVE).** Es el
   defecto por el que se rechazó la séptima pasada, movido de tabla. La regla
   dice que `cen.res` es «Reparto nombre» y la ficha lo repite
   (`raw.yaml:354-356`). Conté las coincidencias en el bloque de `cen` de
   `azure-apps/sigrid_tablas.md` (L4651-4715): **cero**. El `res | Reparto
   nombre` está en **`cenrep`** (L4723), tabla distinta que **ni se ingiere**.
   Lo corrobora nuestro SQL: `cierre/05_views_cabecera.sql:175` toma el nombre
   del centro de `cenc.res`, donde `cenc` es **`raw.con`**, y el `LEFT JOIN
   raw.cen` de la línea anterior no aporta ninguna columna.
2. **Cuatro falsos positivos más (MEDIA-GRAVE).** La regla exige «campos propios
   **con el mismo nombre**». `ctr`, `dca` y `dcf` llevan `entcod`, `entres`,
   `entcif` y `fecdoc` —nombres distintos—; `com` no tiene ninguno de los tres.
   Y `prv` no tiene `cod`/`res`/`fec`: tiene `cif` y `raz`, que es lo que dice
   bien el punto 4, así que el punto 3 la contradice y contradice a su propia
   ficha, que acierta.
3. **Y dieciséis falsos negativos (GRAVE).** «Las que los tienen son …» se lee
   como enumeración cerrada sobre las 31 tablas. Faltan `conext`, `obrparpar`,
   `obrfas`, `obrfasamb`, `obrctr`, `condir`, `obrprv`, los cinco catálogos
   `aux*`, `ctrpro`, `dcapro` y `dcfpro`. Mi barrido derivable sobre nuestro SQL
   —para cada alias de `raw`, usos de `.cod`/`.res`/`.fec`/`.raz`/`.cif`—
   confirma que **ocho de ellas se leen a diario sin unir a `con`**: entre otras
   **`obrparpar`** (`stg/04_partidas.sql:46-47`: `p.cod AS codigo_partida`,
   `p.res AS descripcion_corta` — el código y la descripción de la partida),
   `obrfas.res` (el nombre del mes) y los catálogos `auxobramb`, `auxobrtip`,
   `auxobrcla`, `auxpro`, `auxmun`, que **no tienen ninguna relación con `con`**:
   el JOIN que la regla sugiere no existe.
4. **La copia divergente sigue publicada (MEDIA).** La cabecera de `raw.yaml`,
   que encabeza las 31 fichas, conserva intacta la frase rechazada —«`cod`,
   `res` y `fec` viven en `con`, **no en la tabla especifica**»— y ocho líneas
   después declara: «Esta regla se publica ademas como `R-SIGRID-CON` en el
   bloque global», presentando como la misma dos versiones que divergen. Es el
   **quinto caso** del patrón: la corrección se aplica donde se señaló y la copia
   sobrevive.
5. **El mecanismo no podía cazarlo (MEDIA).** `CON_CAMPOS_PROPIOS`
   (`tests/test_f006_regla_de_oro.py:48`) es una lista escrita a mano, y el test
   que exige que las fichas repitan la excepción (`:143`) se parametriza solo con
   `["obr", "prv"]`: **con `cen` dentro habría fallado**. El comentario que
   justifica no derivarla del PDF es honesto —el segmentador daba resultados
   inestables, y de ahí salió justamente el error de `cen`/`cenrep`—, pero la
   conclusión es la equivocada: **había una fuente derivable sin usar, nuestro
   propio SQL**.

**Cómo cerrarlo**: que la regla enuncie el patrón sin lista cerrada, nombre las
excepciones verificadas una a una —`obr.res` es la única confirmada entre las
diez extensiones 1:1, y `prv` aporta `cif`/`raz` con otro nombre— y que un test
derive del SQL las tablas cuyos campos propios usa el ETL y exija que la regla no
las contradiga.

### B · La carga de `raw`: la nueva redacción es falsa contra la ejecución real

6. **La imagen desplegada hace recarga completa (GRAVE).** Las 31 fichas dicen
   ahora que la carga es append por `MAX(ide)` y que **«lo modificado en Sigrid
   no se refresca nunca»**. El `Dockerfile:26-27` dice lo contrario, y es lo que
   se despliega:

   ```dockerfile
   # El job nocturno SIEMPRE full (el incremental pierde UPDATEs).
   ENTRYPOINT ["python", "main.py"]
   CMD ["run-all", "--full"]
   ```

   Y lo corroboran `docs/ARCHITECTURE.md` («la ingesta nocturna SIEMPRE
   `--full`»), `infra/80_create_job.ps1` («el alcance de la carga nocturna está
   escrito en el Dockerfile y en ningún sitio más»), el runbook y
   `azure-apps/datamart_seg_anual.md`. La corrección se derivó de
   `ingest_raw_step.py` —la fuente correcta para *cómo* carga el comando— y no de
   la que gobierna *qué se ejecuta de noche*. Es el error que el docstring de ese
   mismo fichero de tests denuncia: «derivar de la fuente equivocada es tan malo
   como no derivar».
7. **La bandera citada 31 veces no existe (GRAVE).** Las fichas dicen «la recarga
   completa existe —`--full-refresh`, que hace `TRUNCATE`—». La opción real es
   **`--full`** (`python main.py ingest --help`); `--full-refresh` falla con «no
   such option». Un comando inejecutable, publicado 31 veces.
8. **«`run-all` no la pasa» es falso (MEDIA).** `run-all` tiene `--full`
   (`main.py:457`) y lo propaga hasta `IngestRawStep`. Lo cierto es que el
   *valor por defecto* es incremental; combinado con el defecto 6, la frase manda
   al lector justo al revés de lo que ocurre en producción.

### C · Copias supervivientes del mismo defecto

9. **`stg.yaml:323-326`** conserva la frase que esta misma tanda erradicó de las
   31 fichas de `raw`: `_source_tiemod` «Marca de modificacion de la fila en
   Sigrid, **que usa la ingesta incremental**». El barrido de frases prohibidas
   del test nuevo solo mira `raw.yaml`. Y falta la consecuencia que sí importa y
   nadie dice: bajo append, `_source_tiemod` guarda el `tiemod` que la fila tenía
   **al entrar**, así que es una marca de inserción, no de modificación.
10. **Cuatro `nulo_significa` imposibles en `stg.partidas`**, uno de ellos el que
    se acaba de «corregir»: `capitulo_raiz_cod` dice ahora «El capitulo raiz no
    tiene codigo en Sigrid», imposible porque la rama raíz filtra `p.cod IS NOT
    NULL AND p.cod <> ''` (`04_partidas.sql:57-58`). Igual en `codigo_partida`,
    `ruta_capitulos` y `nivel`, que se construyen sin poder ser nulos.

### D · Otras fichas

11. **`dec_cantidades` afirma gobernar una fórmula en la que no aparece
    (GRAVE).** La ficha (`stg.yaml:307-314`) dice que gobierna el redondeo
    `ROUND(ROUND(can, decc) * ROUND(pre, decp), deci)`. El SQL real es
    `ROUND(pp.can::NUMERIC * ROUND(pp.pre::NUMERIC, decp), deci)`
    (`06_presupuesto.sql:73-76`): **`decc` no interviene**, y la NOTA de cuatro
    líneas antes lo dice expresamente —«la cantidad NO se redondea… Sigrid solo
    redondea el PRECIO»—. El origen del error es reconocible: los comentarios de
    `08_plan_mensual.sql:309,401-402` sí repiten la fórmula con `decc`, y la
    ficha copió el comentario en vez del código. Es la deuda «comentarios del SQL
    que mienten» mordiendo por primera vez.
12. **El guardián de nulos no comprueba nada hoy (MEDIA, mecanismo).** Lo medí:
    15 fichas evaluadas, **30 columnas candidatas y cero llegan al `assert`** —se
    filtran todas en la guarda de proyección desnuda—. No es inútil: queda como
    alarma para el futuro. Pero, a diferencia de los otros seis detectores del
    fichero, **no tiene un `test_..._control_...`** que fije que sigue detectando
    algo, que es justo lo que impide que un detector se degrade a cero en
    silencio. Y ya está en cero.
13. **La plantilla de exclusiones es falsa en 19 fichas (MEDIA).** «No se traen N
    columnas: textos largos, observaciones e imagenes» se aplicó igual a todas:
    en `pag` la única excluida es `blores`; en `dca`/`dcf` seis de las 23 son
    direcciones; en `cen` y `obrprv` solo hay `tex`. En `dca`/`dcf` el texto
    anterior —«una lista larga de textos y campos de direccion»— era **exacto**,
    así que el diff cambió una frase cierta por una falsa. El test comprueba el
    número y las columnas citadas, no la caracterización.

### Menores

- «Antes de escribir cualquier consulta contra `raw`, **cinco cosas**» y numera
  **seis**; el `motivo` repite el error. El punto 6 —polimorfismo `docoritip`,
  nuevo, correcto y con cita literal verificada— queda anunciado como si no
  existiera.
- El punto 4 acierta con `prv.cif` pero omite que `ctr.entcif`, `dca.entcif` y
  `dcf.entcif` traen el CIF desnormalizado en la cabecera del documento.
- `stg.presupuesto` baja sus tres medidas a `ultimo_valor`, lo que contradice su
  propio `ejemplos_preguntas` («cuánto suma el presupuesto de venta…») y el uso
  real de `cierre/02_build_fact.sql:259-286`, que hace `SUM(importe_oficial)`
  sobre una fase fija. Lo no sumable es la dimensión `fase_num`, no la columna.
- `fase_num = 0` en los ámbitos reales es el «Previsto» vivo, no un mes, y el
  `grano` reescrito no lo recoge pese a que `cierre/02_build_fact.sql:252-286`
  depende de ello.
- La receta `grep -n "^| <tabla> "` que las 31 fichas dan para localizar la tabla
  en `sigrid_tablas.md` no aísla el bloque de `con`.
- `config/tables_sigrid.yaml` sigue diciendo «catálogo estable, refresco
  completo» en 13 tablas, y poner `incremental_column: null` no provoca ninguna
  recarga. Las fichas aciertan y el fichero de configuración miente.

---

## Lo que sí está verificado y correcto

### El fallo de `_proyeccion_de` no tuvo efecto retroactivo

Era lo que más preocupaba y se midió por dos vías independientes que coinciden:

- **Un solo llamante en toda su vida**: el guardián de nulos. `git log -S` da
  tres commits —nacimiento, corrección, informe— y ninguna otra llamada. Los
  demás contrastes van por `columnas_del_create_table`, `cuerpo_de_vista`,
  `cuerpo_del_insert`, `pk_declarada` y `proyeccion_por_alias`, todos
  cualificados por `esquema.objeto`.
- **Alcanzaba a una sola ficha**: `cierre.v_pbi_cierre_cabecera`, cuyo fichero
  crea **un solo objeto**. No había vecino del que heredar proyección.
- **Revalidación a mano de las seis fichas de `compras/01_documentos.sql`**: 78
  columnas documentadas contra 78 proyectadas, **ninguna ajena y ninguna
  omitida**, y los **30 `nulo_significa` respaldados por el `NULLIF`/`CASE` de su
  propio bloque**. Los dos casos donde el vecino sí habría mentido
  —`albaranes.contrato_id` y `factura_lineas.albaran_id`— son correctos.
- Mismo contraste sobre los otros once ficheros multiobjeto: **0 problemas**.

El acotado fue en la práctica un anti-falsos-positivos: eliminó tres acusaciones
falsas contra `compras` que aparecieron al ampliar el guardián. Correcto y
necesario, pero no reparó nada retroactivo.

### Lo demás

- **`pendientes` en 0 significa lo que dice**: biyección exacta, 102 fichas ↔ 102
  objetos, sin huérfanas ni fantasmas, con los recuentos por esquema cuadrando
  uno a uno. Salvedad ya conocida: «los que el repositorio publica» son los que
  ve la heurística; la verdad es R28, que sigue sin existir.
- **El punto 2 de la regla es exacto**: las diez «Propiedades de `con`» son
  exactamente esas diez. El punto 6 (polimorfismo) es correcto con cita literal.
  `con.nom` no existe, `obr.res` sí, y `prv.cif`/`prv.raz` tienen la doble
  verificación que declaran.
- **Mutación**: recalculada con el `__pycache__` borrado —2358 líneas, 166
  mutantes—, idéntica a lo declarado, 0 supervivientes y 0 timeouts.
  `harness/mutacion.py` **intacto**, como debe ser: su arreglo es F-041.
- **Nada prohibido**: el diff toca YAML, dominio, tests y `progress/`. Ni un
  `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**.
- El resto de correcciones de la tanda que verifiqué y son ciertas:
  `R-FRESCURA-MANUAL` con los seis pasos reales, `stg.fases.anio`/`.mes`,
  `maestro.obras.cliente_id`, `capitulo_raiz_id`, `version_master_vigente` a
  `1:N`, `total_incurrido` en los dos ámbitos reales y la guarda del mes oficial.

---

## Qué falta para poder pasar la batería de aceptación

Cuando se cierren estos trece, lo que queda ya no es contenido:

1. **T19**: publicar contra la base real y comprobar el contrato de `_meta`.
2. **T26/T27**: `check-diccionario` contra el catálogo real, con la consulta de
   unicidad de clave. Es además lo único que convierte «102 objetos» en una
   verdad y no en lo que ve una expresión regular.
3. **T39**: las 18 preguntas contra el diccionario publicado —13 respondibles, 3
   parciales y 2 que deben contestarse con un «no puedo, y este es el motivo»—.
4. Los bloques 🔏 de permisos y firewall, que necesitan firma del humano.

Y la deuda declarada que viaja: el falso positivo del detector de multifuente,
los menores 5-7 de la sexta pasada, F-041 para que «cero supervivientes»
signifique lo que dice, y ahora los comentarios del SQL que mienten —que con el
defecto 11 han dejado de ser deuda teórica—.

---

# SÉPTIMA PASADA · 2026-08-20 — el diccionario completo

> Commits revisados: `c5c0bd6`..`df4b199`. Alcance nuevo: los **53 objetos** que
> faltaban —`maestro` (4), `stg` (10), `aux` (1), `_meta` (7) y `raw` (31)—.
> Total del diccionario: **102 objetos, 793 columnas, 13 reglas, `pendientes` en 0**.

## Veredicto de la séptima pasada

**RECHAZADO.** El andamiaje de esta tanda es excelente —los recuentos cuadran, el
trinquete llega a 0 de verdad, la mutación se recalcula sola, el barrido de
comentarios está automatizado y los tres hallazgos de «derivar antes de
corregir» son ciertos— pero **el contenido de los dos esquemas más grandes tiene
defectos graves**, y son de la clase que esta feature existe para impedir: fichas
que producen números falsos y una regla **bloqueante** que le dice al agente que
un campo cargado en la base no existe.

Los diez que bloquean están abajo. Ninguno es de forma: los verifiqué uno a uno
contra el SQL y contra `azure-apps/sigrid_tablas.md`.

---

## Lo que hay que corregir

### En `raw` y en la regla de oro

1. **`R-SIGRID-CON` está sobregeneralizada, y es `bloqueante` sobre las 31
   fichas.** Dice que `cod`, `res` y `fec` viven en `con` «**no en la tabla
   específica**». Falso para la tabla más consultada del datamart:
   `sigrid_tablas.md:16542` da `obr.res = "Nombre completo", Texto ilimitado`, y
   `raw.obr` se ingiere con `exclude_columns: []`, así que **la columna está
   cargada en Postgres**. El `motivo` repite el error —«consultar `obr` sin unir
   a `con` devuelve una obra sin nombre y sin código»: sin código sí, sin nombre
   no— y la ficha `raw.obr` (`raw.yaml:115-118`) lo dice otra vez. Una regla
   bloqueante que niega un campo real es peor que no tenerla.
2. **La ficha `raw.prv` ubica el CIF donde no está** (`raw.yaml:373-374`: «el
   CIF, el nombre y el código del proveedor están en `con`»). El CIF es
   `prv.cif`, y lo confirma el propio repositorio:
   `maestro/02_proveedores.sql:28-29` toma `p.cif` y `p.raz` **de `raw.prv`**, y
   solo `cod`/`res` de `raw.con`. El agente que siga la ficha buscará `con.cif` y
   se estrellará: exactamente el fallo que la regla de oro existe para evitar.
3. **Las 31 fichas describen mal cómo se carga la tabla.** 18 dicen «carga
   incremental por `tiemod`» y 13 «se recarga entera cada noche», y **ninguna de
   las dos cosas ocurre**: `ingest_raw_step.py:205-211` toma
   `last_id_already = pg.get_max_id("raw", tabla, "ide")` —append de los `ide`
   por encima del máximo ya guardado— y usa `incremental_column` **solo** para
   volcar `_source_tiemod`. Una fila modificada en Sigrid no se refresca nunca, y
   el `TRUNCATE` solo ocurre con `full_refresh=True`, que `run-all` no pasa. Es
   información operativa falsa sobre la frescura del origen.
4. **`tiemod` no existe en 15 de las 18 tablas** a las que `tables_sigrid.yaml`
   —y por herencia la ficha— le asigna esa columna de corte. Solo `con` y
   `comprv` la tienen.
5. **Trece punteros a objetos que no existen**: `compras.documentos` (×7) y
   `compras.fact_linea` (×6), en las fichas de `con`, `ctr`, `ctrpro`, `dca`,
   `dcapro`, `dcf` y `dcfpro`. Lo verifiqué: 13 menciones en `raw.yaml` y **cero
   apariciones en todo el SQL**; los reales son `compras.contratos`,
   `compras.albaranes`, `compras.facturas` y `compras.fact_compras_linea`. Como
   todo el argumento de DA-2 es «no consultes `raw`, ve aguas abajo y la ficha te
   dice dónde», el puntero roto vacía el `motivo_no_consumo` de siete tablas.
6. **Ninguna de las 31 fichas remite a `azure-apps/sigrid_tablas.md`**, que es la
   contrapartida que DA-2 prometía a cambio de no documentar columnas. Las dos
   menciones viven en el comentario de cabecera, que `yaml.safe_load` descarta.
   **Rectifico aquí mi propio barrido**: lo hice contra el publicable *global*, y
   ahí el puntero aparece —en la entrada `esquemas.raw` de `00_global.yaml`—, así
   que lo di por bueno. El matiz que se me escapó es que un agente que pida
   `describir_tabla('raw.dcapro')` recibe la ficha, no el bloque de esquema: el
   puntero tiene que estar **en la ficha**.

### En `stg`

7. **`stg.presupuesto` no dice que en los ámbitos reales es ACUMULADO A ORIGEN, y
   encima marca `agregacion: suma`.** Las tres medidas —`cantidad`, `importe`,
   `importe_oficial`— llevan `suma`, y el desacumulado se hace aguas abajo por
   diferencia con la fase anterior (`08_plan_mensual.sql:346-352`:
   `cantidad - LAG(cantidad)`). Sumar a través de `fase_num` multiplica. Es la
   trampa de `R-IMPORTE-MES` otra vez, en la ficha que se autoproclama «la fuente
   buena para cuál es el presupuesto de la obra» y que propone como ejemplo
   «Cuál es el presupuesto de la obra X».
8. **La trampa de las versiones master no está escrita en `stg.presupuesto`**,
   donde aplica igual que en `plan_mensual`: en los ámbitos 8 y 11 hay una fila
   por versión. La ficha invita a la pregunta y solo dice «filtrar la fase
   correcta», sin advertir de qué pasa si no se filtra.
9. **`stg.fases.anio` y `.mes` declaran un origen falso**: «derivado de su fecha
   de inicio», con `nulo_significa: La fase no tiene fecha de inicio`.
   `05_fases.sql:26-27` los copia de `f.ano` y `f.mes` de `raw.obrfas`, que son
   independientes de `fecini`. No es cosmético: `08_plan_mensual.sql:328-329`
   exige `anio`/`mes` no nulos para construir los ámbitos reales.
10. **Cuatro `nulo_significa` imposibles en `stg.partidas`, uno de ellos
    invertido**: `capitulo_raiz_id.nulo_significa: «La propia fila es el capítulo
    raíz»` cuando `04_partidas.sql:51` hace exactamente lo contrario —«En la
    raíz, ella misma es el raíz», `p.ide AS capitulo_raiz_id`—. Buscar las raíces
    con `WHERE capitulo_raiz_id IS NULL` devuelve cero filas.

### En `maestro`, y en el mecanismo que debía impedirlo

11. **`maestro.obras.cliente_id` declara un nulo que nunca ocurre**, y es la
    **reincidencia exacta** del defecto que ya corregimos en la tercera pasada.
    `maestro/01_obras.sql:26` proyecta `o.entide AS cliente_id` **sin
    `NULLIF(…, 0)`** —el propio fichero avisa en su cabecera de que en Sigrid
    esas referencias «vienen a 0»— y la ficha (`maestro.yaml:75`) dice
    `nulo_significa: La obra no tiene cliente asignado`. Un `WHERE cliente_id IS
    NULL` devuelve cero filas siempre.
    Lo importante es **por qué se coló**: el guardián que se escribió para esto,
    `test_f006_r2_un_nulo_declarado_en_un_ide_tiene_que_ser_posible`, filtra por
    `columna.nombre.endswith("_ide")` (`tests/test_f006_fichas.py:514`), y
    `maestro` nombra sus columnas `_id`. El mecanismo estaba y no cubrió el caso
    por un sufijo. Arreglo doble: la ficha, y ampliar el guardián a `_id`.
12. **El `motivo` de `R-FRESCURA-MANUAL` cita una composición del pipeline que ya
    no es la real** (`00_global.yaml:49-51`): «IngestRaw, LoadExcelAux, BuildStg,
    BuildMart y ApplyGrants». Falta **`PublicarDiccionarioStep`**, que el bloque E
    insertó entre `BuildMart` y `ApplyGrants`. La conclusión de la regla no
    cambia, pero es una regla `bloqueante` cuya evidencia citada está desfasada
    desde hace dos tandas.
13. **`tests/test_f006_raw_ingesta.py:78-97` pasa en vacío en 11 de las 31
    fichas.** La aserción es `citadas <= excluidas`, que se cumple trivialmente
    cuando `citadas` está vacío, y las columnas citadas se extraen con una regex
    que exige un formato de prosa concreto (`**No se traen** …`). Hoy solo 7
    fichas citan alguna, mientras 11 tienen exclusiones y no citan ninguna
    —`dca` y `dcf` con 23 columnas excluidas cada una—. Sin un control de
    no-vacuidad, el día que alguien escriba el aviso con otro formato el test
    seguirá verde mientras la ficha calla.

### Deuda de la misma tanda, que puede viajar

`stg.fn_master_fecha_efectiva` omite la guarda `IF v_mes_creac IN (2,6,10)`, que
es media regla; `stg.version_master_vigente` declara `N:N` una relación que es
`1:N`; `stg.plan_mensual.total_incurrido` dice «no es de coste real» cuando
también llega en el ámbito 7; `presupuesto.dec_cantidades` dice gobernar un
redondeo que el SQL declara explícitamente que no aplica; `R-SIGRID-CON` no
advierte de las referencias polimórficas (`linoriide` + `docoritip`); y
`domain/diccionario.py:99` sigue diciendo «las DOCE reglas duras» cuando la tupla
tiene trece.

---

## Los números, recontados

No me fío de los recuentos y esta vez hay una discrepancia con lo que llegó por
el chat, sin consecuencias pero conviene fijarla:

| | Declarado | Medido por mí |
|---|---|---|
| Tests | 1496 | **1557** |
| Saltados | 40 | **82** |
| Cobertura | 99,0 % de 722 | 99,0 % de 722 ✔ |
| Objetos / columnas / pendientes | 102 / 793 / 0 | **102 / 793 / 0** ✔ |

La diferencia de tests es de medición: el líder contó antes de los cuatro
últimos commits. El **inventario cuadra exactamente**: 102 fichas para 102
objetos publicados, `pendientes` vacía y `PENDIENTES_MAX = 0`. El trinquete en 0
significa lo que dice.

Reparto verificado: `_meta` 7 objetos (los tres de instrumentación más las tres
tablas del diccionario y su vista), `aux` 1, `cierre` 12, `compras` 14,
`maestro` 4, `mart` 13, `raw` 31 **con 0 columnas** —como manda DA-2—,
`retenciones` 10 y `stg` 10.

## Los 82 saltados, explicados

Subieron de 40 a 82 y el informe no lo menciona, así que lo desgloso:

| Nº | Motivo | Veredicto |
|---|---|---|
| 31 | «las tablas de `raw` no tienen DDL en el repositorio (DA-2)» | **legítimo y esperado**: son las 31 fichas nuevas de `raw` |
| 35 | «el `GROUP BY` de este objeto no es derivable» | legítimo (eran 28; suben porque hay más objetos) |
| 6 | «la PK es una clave sustituta; la de negocio es otra cosa» | **legítimo, y es la prueba de que la corrección de la PK inline funciona** |
| 3+3 | «la proyección no se deja leer» | legítimo: los catálogos `VALUES` |
| 2 | «el DDL no declara clave primaria, ni aparte ni inline» | legítimo: las CTAS sin PK |
| 2 | «se crea con SQL dinámico; tiene su propio test» | legítimo, ya validado |

**Ninguno esquiva una comprobación que antes se ejecutara.** Y el mensaje falso
que denuncié en la cuarta pasada está corregido: ahora dice «ni aparte ni
inline» y solo aplica a las dos tablas que de verdad no tienen PK; las tres
tablas de hecho caen en la rama correcta —clave sustituta—, que antes no se
alcanzaba.

## La mutación, mirada con lupa

- **Recalculada de forma independiente**: alcance **2358 líneas**, **166
  mutantes**. Coincide con `progress/mutacion_F-006.md`, que declara 166
  evaluados, 166 muertos, **0 supervivientes y 0 timeouts**.
- **Los cuatro «timeouts» eran cuatro supervivientes**, y está contado sin
  adornos en `tests/test_f006_supervivientes.py`, que además explica por qué
  sobrevivían: dos `frozen=True → False` en `Columna` y `Relacion` —que nadie
  cazaba, mientras la hermana `Ficha` sí tenía quien la cazara— y dos mínimos de
  longitud subidos en uno, que sobrevivían porque **ningún caso ejercitaba el
  borde**. La lección que deja escrita es la correcta: **un timeout no es un
  mutante muerto, es un mutante sin evaluar.**
- **El mutante vivo en el bytecode: confirmado, y lo reproduje.** Monté un
  módulo de laboratorio fuera del repositorio, generé su `__pycache__`, apliqué
  una mutación **del mismo tamaño** conservando el `mtime`, y después restauré el
  fuente original conservándolo otra vez. Python siguió ejecutando el bytecode
  **mutado**:

  ```
  resultado: True      <- fuente original
  resultado: False     <- fuente mutado
  resultado: False     <- fuente RESTAURADO, pero corre el .pyc mutado
  ```

  Es real y es serio: con el fuente restaurado la suite corre contra código
  mutado. En este caso dio un falso rojo; **en el caso simétrico daría un falso
  verde**, es decir, un mutante contado como muerto sin estarlo.

  **Salvedad que el líder debe conocer**: `harness/mutacion.py` **no se ha
  tocado** —lo comprobé: el diff de `harness/` en esta tanda es solo
  `features.json`—, así que el defecto sigue vivo en la herramienta y la campaña
  de 166/166 se midió con él presente. Está dado de alta como **F-041**, junto
  con el recuento de timeouts y los worktrees huérfanos, y es del arnés genérico,
  así que viaja a `arnes-base` por la regla de propagación. No bloquea F-006: la
  evidencia disponible es la que la herramienta puede dar hoy, y los cuatro
  supervivientes reales se reevaluaron uno a uno.

## La regla de oro, verificada en la fuente

`R-SIGRID-CON` es la decimotercera regla y gobierna cómo un agente entiende todo
`raw`. **Fui a la fuente** (`azure-apps/sigrid_tablas.md`, entidad `con`) y sus
puntos centrales se confirman al pie de la letra:

| Afirmación | Verificación |
|---|---|
| «`ide` es la clave … y es el índice primario» | `ide Identificador \| Entero \| INDICE PRIMARIO \| Unico` |
| «`cod`, `res` y `fec` viven en `con`» | los tres están en la entidad: `cod Código`, `res Resumen`, `fec Fecha alta` |
| «`con.nom` NO EXISTE; el nombre legible es `con.res`» | **no hay ningún campo `nom`** en la entidad |
| El `motivo` cita `ide`, `cod`, `res`, `fec`, `est` y `fecbaj` | los seis están, con esos nombres |
| «un campo que acaba en `ide` es una referencia» | la lista de referencias de `con` es exactamente eso: `pag.conide`, `ctr.entide`, `obrfasamb.ofeentide`… |

Y el hallazgo que la motiva es cierto y no menor: **la regla estaba solo en un
comentario del YAML**, y los comentarios no se publican. El MCP no la habría
visto nunca.

## El parser que no veía las columnas migradas

Verificado por mí, y es un hallazgo genuino de «derivar antes de corregir»:
`_meta.etl_runs.batch_id` **no está en el `CREATE TABLE`**, se añade después con
`ALTER TABLE _meta.etl_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL`
(`sql/ddl/00_meta.sql:34`). El contraste exacto de columnas no leía los `ALTER`,
así que acusaba a la ficha de documentar una columna inexistente **cuando la
columna existe**, solo que migrada. Ejecuté el parser corregido sobre el fichero
y devuelve las diez columnas, `batch_id` incluida. Si se hubiera «corregido» la
ficha en vez del parser, se habría borrado de la ficha una columna real.

## El barrido de comentarios, hecho a máquina

Es la segunda vez que aparece el mismo fallo —ya pasó con el aviso de frescura en
la cabecera—, así que no me fié del barrido manual: parseé los diez YAML con
`safe_load` —que descarta los comentarios— y comparé el conjunto de
identificadores citados en comentarios contra **todo** el texto publicable del
diccionario.

**No queda ninguna afirmación importante fuera de lo publicable.** Los únicos
identificadores que viven solo en comentarios son `describir_tabla` —el nombre
de una herramienta del MCP— y `exclude_columns` / `incremental_column`, que son
claves de `config/tables_sigrid.yaml` citadas al explicar **cómo se verificó** la
ficha; lo que esas claves significan está contado en prosa publicable en 19
sitios de `raw.yaml`. Ninguno de los tres es semántica de negocio.

## El nombre de fichero que git no podía indexar

`aux.yaml` pasaba los tests y `git add` lo rechazaba: `AUX` es nombre de
dispositivo reservado en Windows. La solución —`aux_.yaml`, con el sufijo de la
convención de Python— es correcta y está bien acotada:

- **el contenido sigue declarando `esquema: aux`**, que es lo que consultará el
  MCP: el nombre del fichero no se publica;
- el cargador resuelve **la familia entera** de reservados —`con`, `prn`, `aux`,
  `nul`, `com1`–`com9`, `lpt1`–`lpt9`— en una sola función usada por el cargador
  y por quien cree un esquema nuevo;
- y el comentario señala el caso que habría dolido de verdad: **`con` es el
  nombre de la tabla central de Sigrid**.

## Rigor y comprobaciones de siempre

- **1557 tests + 82 saltados**, ejecutados por mí; cobertura **99,0 % de 722
  líneas**.
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` ni ningún SQL de negocio; ni un `GRANT`,
  `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**: no hay rama
  remota. **Sin worktrees huérfanos.**
- El dominio sigue puro: `diccionario.py` importa solo `re`, `collections.abc` y
  `dataclasses`; el manejo de nombres de fichero vive en el cargador, que es
  infraestructura.
- Deuda menor nueva: un aviso `I001` de `ruff` en
  `tests/test_f006_supervivientes.py` (orden de imports). Es la segunda vez que
  un test nuevo entra con ese aviso.
- **Matiz de proceso**: el commit `df4b199` es de **F-041** y va en la rama de
  F-006. Es solo el alta en `features.json` y `BACKLOG.md` de una feature nacida
  de este trabajo, no una implementación, así que es defendible; conviene que el
  líder lo sepa porque la regla es una rama por feature.

---

## Lo que esta bien y no hay que rehacer

El rechazo es de contenido y el andamiaje es solido; conviene decirlo para que la
correccion no se lleve por delante lo que funciona:

- **Ni una columna inventada ni omitida** en las 75 de `stg`, contrastadas una a
  una; ni una ficha de `raw` de mas o de menos: las 31 `target_table` de
  `config/tables_sigrid.yaml` casan con las 31 del YAML, en el mismo orden.
- Los **31 titulos de `raw`** coinciden literalmente con la fila de entidad del
  autodocumentador de Sigrid, y las 31 tablas tienen `ide` como indice primario
  unico, como afirma la regla.
- **Nueve de las doce afirmaciones de `R-SIGRID-CON` son ciertas**, incluidas las
  dos que mas pesan: `con.nom` no existe y el `0` es el NULL de las fechas.
- Las **seis trampas de `stg`** que se pidio comprobar estan escritas en campos
  **publicables** y son ciertas: ninguna vive solo en un comentario.
- **`_meta` y `aux_` estan limpios**: los siete objetos de `_meta` casan columna a
  columna con su DDL —y `v_diccionario` conserva el orden del contrato, con
  `motivo_no_consumo` la ultima—, y las dos afirmaciones de `aux_` (se crea vacia
  por diseno, la vista no periodifica nada) se verificaron contra el SQL.
- Las tres trampas de `maestro` estan escritas y son ciertas.
- Las seis tablas de `raw` que las fichas declaran sin consumidor son exactamente
  las seis que ningun SQL lee.

Con esas bases, lo que falta es corregir trece afirmaciones y dos mecanismos, no
rehacer el trabajo.

## Checkpoints (septima pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —trece
afirmaciones publicadas que el SQL o el origen desmienten, una de ellas en una
regla bloqueante— · **C4 bis** `[x]`, con la salvedad del bytecode · **C4 ter**
N/A · **C5** N/A parcial (los bloques A a G del alcance encargado).

---

# SEXTA PASADA · 2026-08-20 — cierre

> Commits revisados: `6fb7f13`..`c81457f`.

## Veredicto de la sexta pasada

**APROBADO, sin matices.**

Los tres defectos de la quinta pasada están cerrados y verificados contra el SQL,
y el trabajo entregado queda aprobado con este alcance:

| Bloque | Estado |
|---|---|
| **A · Formato** (T3–T8) | aprobado |
| **B · Reglas duras** (T9–T11) | aprobado |
| **C · Fichas de `mart`** (T12, T13) | aprobado |
| **D · Fichas de `cierre`** (T14) | aprobado |
| **E · Publicación en `_meta`** (T15–T18) | aprobado — T19 queda como verificación MANUAL (humano), con sus comandos escritos |
| **F · parcial** (T20 `compras`, T21 `retenciones`) | aprobado |

**49 fichas, 593 columnas, 12 reglas duras y el contrato con `mcp-bbdd`**, con las
claves, los granos, las cardinalidades, las nulidades y las agregaciones
contrastadas contra el SQL que crea cada objeto. Quedan 53 objetos por documentar
—`stg`, `maestro`, `aux`, `_meta`, `raw`— y su trinquete en 53.

## Los tres defectos

1. **`v_pbi_retencion_obra`** declara ahora la clave de tres columnas y su grano
   explica por qué: «en `retenciones.movimientos` las tres se resuelven con
   cascadas DISTINTAS […] un `obra_id` cuyo centro de coste no exista en el
   maestro puede aparecer con dos códigos y dar DOS filas». Cerrado.
2. **`v_pbi_cierre_indirectos_detalle`**: «traen valor tanto si el grupo se
   periodifica como si no, **pero pueden ser nulas por su propia causa**: no
   haber presupuesto vivo o no haber plazo calculable». Cerrado, y con el SQL por
   delante.
3. **La premisa falsa del comentario del test**, cerrada y con el porqué escrito.
   **Y corregida también en este informe**, que era donde nació: ver la nota de
   enmienda en la cuarta pasada, §«La acotación de lo no derivable».

## El barrido, y los dos «legítimos»

El barrido automatizado —hecho **antes** de tocar nada, que era la lección
pendiente— dio tres candidatos. Los reproduje ejecutando el detector sobre los 49
objetos y **salen exactamente los mismos tres**. De los dos declarados legítimos,
verifiqué la dependencia contra el SQL:

- **`mart.fact_seguimiento_categoria`** omite `anio`, `mes`, `tipo_dato`,
  `concepto` y `ambito_id`. Las dos primeras se derivan de `anio_mes` y las tres
  siguientes de `escenario`, cuya correspondencia es 1:1 y está fijada en
  `mart.v_pbi_dim_escenario`. **Legítimo.**
- **`retenciones.v_pbi_retencion_entidad`** omite `entidad_nombre` y
  `entidad_cif`. Aguas arriba, en `movimientos`, las dos ramas resuelven
  `entidad_nombre` con `ent.res` —una sola fuente, lookup por `entidad_id`— y
  `entidad_cif` con `prv.cif` en la rama PROVEEDOR y `NULL` constante en la de
  CLIENTE (`01_movimientos.sql:57-59, 105-107`). **Legítimo.**

Ninguno de los dos miente.

## El ataque a la comprobación nueva

Es la que va a gobernar los 53 objetos que faltan, así que fui a romperla.

**Lo que hace bien**: ejecutada sobre el diccionario entero **no marca ni una
sola columna**, y las siete omisiones legítimas de arriba pasan limpias. Su test
de control separa los dos casos (`COALESCE(cen_con.cod, obr_con.cod)` sí,
`ent.res` no, `COALESCE(od.num_obras, 0)` no). Cero falsos positivos hoy.

**Dónde se rompe** (encontrado, reproducido, y **no bloquea**): la regla mira si
dentro del `COALESCE` hay dos alias distintos, no si esos alias resuelven al
**mismo objeto**. Construí una vista con dos ramas de la misma tabla unidas por
la propia clave:

```sql
SELECT COALESCE(a.obra_id, b.obra_id)         AS obra_id,
       COALESCE(a.nombre_obra, b.nombre_obra) AS nombre_obra,
       SUM(a.importe_mes)                     AS total
FROM mart.fact_seguimiento_mensual a
FULL JOIN mart.fact_seguimiento_mensual b ON a.obra_id = b.obra_id
GROUP BY obra_id, nombre_obra;
```

Aquí `nombre_obra` **sí** depende de `obra_id` —las dos ramas son la misma
tabla—, y el test la marca:

```
['mart.v_prueba_fulljoin.nombre_obra'] se agrupan y salen de un COALESCE de
varias fuentes, asi que no se pueden dar por dependientes de la clave: o entran
en ella, o la ficha promete una unicidad que no existe
```

Es decir: obligaría a meter `nombre_obra` en la clave, **a mentir en la ficha
para pasar la puerta**, que es justo lo que había que evitar. Dos matices que lo
dejan en deuda y no en defecto: hoy **ningún objeto del repositorio** tiene ese
patrón en un `GROUP BY` analizable, y la variante con `GROUP BY` por expresiones
—`GROUP BY COALESCE(...), COALESCE(...)`— ni siquiera se analiza, así que tampoco
salta. El patrón existe ya en el repositorio dentro de una CTE
(`06_views_cp_tipologia.sql`, `detalle_partida`: `COALESCE(r.codigo_partida,
p.codigo_partida)` sobre las dos ramas de un `FULL JOIN`), así que aparecerá.

**Arreglo cuando muerda**: comparar si los dos alias del `COALESCE` resuelven al
mismo objeto en el `FROM`/`JOIN`; si lo hacen y el join es por la clave, la
dependencia se mantiene. Alternativa barata: permitir declarar la omisión
justificada en la ficha, como ya se hace con `motivo_no_consumo`.

## Deuda declarada que viaja con los bloques que faltan

Por decisión del líder, y con mi acuerdo: los menores 5 (la analogía suavizada de
`compras.yaml`), 6 (`MIN`/`MAX` sobre todos los efectos en una vista de saldo
vivo, preexistente) y 7 (la justificación del SQL de T26 que dice que agrupar los
NULOS es «como se comportan en un JOIN», cuando es al revés: es **más** estricto
que un JOIN). A esos tres se suma el falso positivo de arriba. Ninguno bloquea, y
los cuatro están escritos con su caso reproducible.

## Rigor

- **1361 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 %**.
- **Mutación verificada de forma independiente**: 2324 líneas, **161 mutantes**,
  cero supervivientes; coincide con `progress/mutacion_F-006.md`.
- **Nada prohibido**: el diff toca dos YAML, un fichero de tests y `progress/`.
  Ni un `GRANT`, `REVOKE`, firewall, Azure ni conexión a la base. **Sin `push`**.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos.

### Checkpoints

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[x]` ·
**C4 bis** `[x]` · **C4 ter** N/A · **C5** N/A parcial (20 de 42 tareas: el
alcance encargado; C5 se exigirá entero cuando F-006 pase a `done`).

---

# QUINTA PASADA · 2026-08-20 — el grano, derivado

> Commits revisados: `d07a67a`..`bbf9045` (cuatro). Alcance: T15–T18, T20 y T21.

## Veredicto de la quinta pasada

**RECHAZADO**, por dos defectos de gravedad media que aparecieron al terminar el
contraste de los 28 granos.

**Rectifico un veredicto que ya había emitido.** Di APROBADO apoyándome en mis
propias comprobaciones —el recuento, los mecanismos, cinco granos muestreados— y
dejando dicho que dos auditorías paralelas seguían corriendo. Al llegar,
confirmaron los 28 granos uno a uno y **encontraron dos cosas que yo no había
mirado**. Las he verificado contra el SQL y son ciertas, así que el veredicto
cambia. Es la segunda vez en esta feature que me pasa lo mismo, y la lección es
la de siempre: el contraste caso a caso encuentra lo que el muestreo no.

Lo que se pidió está hecho y bien hecho —los cuatro defectos de campo vecino, los
tres menores, la vía (a) implementada y la (b) diferida con criterio—, y los 28
granos reescritos son ciertos: **ninguno se escribió para el test**. Lo que falla
es otra cosa: **el barrido de copias no fue exhaustivo**, y quedan dos fichas que
siguen diciendo algo que el SQL desmiente. El commit se titula «los cuatro
defectos de campo vecino»; este es el quinto y el sexto.

Lo importante de esta tanda no es que se hayan corregido cuatro fichas: es que
**el defecto que llevábamos tres pasadas persiguiendo caso a caso era
sistemático**, y solo se vio al derivarlo. Eso confirma lo que veníamos diciendo
desde la segunda pasada, y esta vez el número lo dice sin ambigüedad.

---

## Lo que hay que corregir

### 1 · `retenciones.v_pbi_retencion_obra`: la clave no cubre su `GROUP BY` (MEDIA)

Es **el mismo defecto que motivó el rechazo de la tercera pasada**, en la ficha
hermana de la que sí se corrigió.

- Ficha (`retenciones.yaml:363`): `grano` «Una fila por `obra_id`» y
  `clave_negocio: [obra_id]`.
- SQL (`retenciones/02_views.sql:89`): `GROUP BY obra_id, codigo_obra, nombre_obra`.
- Y las tres columnas **no se derivan unas de otras**: en `movimientos`,
  `obra_id = COALESCE(NULLIF(p.cenide,0), CASE WHEN od.num_obras = 1 THEN
  od.obra_unica END)` mientras `codigo_obra = COALESCE(cen_con.cod, obr_con.cod)`
  y `nombre_obra = COALESCE(cen_con.res, obr_con.res)`
  (`01_movimientos.sql:61-64`): son cascadas distintas, resueltas por joins
  distintos. Con `cenide <> 0` sin fila en `raw.con` y `num_obras = 1`, la misma
  `obra_id` puede salir con dos `codigo_obra` → **dos filas para la clave
  declarada**, y quien una por `obra_id` duplica.

En `compras.v_pbi_partida_coste` este mismo caso se corrigió bien, y su ficha lo
explica con esas palabras: «`codigo_obra` se resuelve con una cascada distinta de
la de `obra_id`» (`compras.yaml:919-920`). Faltó cruzarlo con `retenciones`.

**Por qué no lo cazó el test nuevo**: el contraste es `clave ⊆ GROUP BY`, de
subconjunto y no de igualdad. Es la limitación que ya señalé en la cuarta pasada,
y este es el caso donde muerde. La comprobación de unicidad de T26 lo resolvería,
pero hasta entonces la ficha miente.

### 2 · `cierre.v_pbi_cierre_indirectos_detalle`: «traen valor siempre» es falso (MEDIA)

El `grano` (`cierre.yaml:499-500`) afirma: «Sus dos entradas, `importe_fase0` y
`plazo_total_meses`, **traen valor siempre**». No es cierto, y **la propia ficha
se contradice cincuenta líneas más abajo**: `importe_fase0.nulo_significa: La
subcategoria no tiene presupuesto vivo` (`:550`) y
`plazo_total_meses.nulo_significa: La obra no tiene plazo calculable` (`:559`).
El SQL confirma que ambas pueden ser NULL —`04_views_detalle.sql:340-341` guarda
explícitamente `WHEN po.plazo_total_meses IS NULL THEN NULL` y `WHEN
f0s.importe_fase0_subcat IS NULL THEN NULL`, y las dos llegan por `LEFT JOIN`—.

La intención se adivina —«traen valor **sea el grupo INFRA o no**», que es lo que
dicen bien los `significado` de las dos columnas— pero, tal y como está escrito,
quien lea el grano concluye que nunca son nulas y no comprobará el NULL. Es de
una línea: «traen valor tanto si el grupo se periodifica como si no; pueden ser
nulas por su propia causa (ver `nulo_significa`)».

### 3 · Una premisa falsa sostiene el límite del test — y la escribí yo (MEDIA-BAJA)

`tests/test_f006_fichas.py:1156` justifica por qué «la clave es demasiado corta»
no es derivable diciendo: «`codigo_obra` **sí** depende de `obra_id` y
`proveedor_cif` NO depende de `proveedor_id`». La segunda mitad es cierta; **la
primera es falsa**, y lo desmiente el propio commit en `compras.yaml:919-920`
—con el SQL a favor de la ficha—.

El origen de la frase es mi informe de la cuarta pasada: la escribí yo, el
implementer la tomó como fundamento y su propia corrección la contradice. Hay que
arreglarla en los dos sitios, porque el límite del test sigue siendo real —lo es
por `proveedor_cif`— pero el ejemplo que lo ilustra es justamente un caso en el
que la dependencia **no** existe.

### Menores

4. `retenciones.yaml:428-431` etiqueta `N:1` la relación `obra_id →
   maestro.obras.obra_id` mientras el grano de esa misma ficha dice una fila por
   `obra_id`; los dos casos análogos de `compras` usan `1:1` (`:694`, `:887`).
   Una de las dos afirmaciones sobra. (Se resuelve sola al corregir el defecto 1.)
5. `compras.yaml:667-669`: la analogía nueva («`importe_facturado` tampoco
   filtra») compara cosas distintas —ahí no filtrar da el neto correcto, sobre
   `factura_lineas`; en el pendiente arrastra NOTA y OTRO, sobre
   `albaran_lineas`—. La corrección era necesaria, pero suaviza un aviso que no
   conviene suavizar.
6. `v_pbi_retencion_entidad.primera_devolucion_prevista` y
   `ultima_devolucion_prevista` son `MIN`/`MAX` sobre **todos** los efectos,
   liquidados incluidos (`02_views.sql:45-46`), y la ficha no lo dice en una
   vista cuyo titular es `saldo_vivo`. Preexistente, no de esta tanda.
7. La justificación del SQL de unicidad de T26 dice que agrupar los NULOS es
   «como se comportan en un JOIN»: **falso**, en un `JOIN … ON a.x = b.x` los
   NULL no casan. Agruparlos juntos es **más estricto** que un JOIN, que es lo
   que conviene para comprobar una clave, pero el motivo escrito no es el
   verdadero. El SQL en sí es correcto.

## El 28 de 41, verificado

No me fié del recuento. Lo reproduje: en un worktree aislado dejé los tests de
HEAD y **revertí los cinco YAML al commit anterior** (`c20c933`), que es
exactamente «activar la comprobación sobre el diccionario de ayer». Resultado:

```
28 failed, 14 passed, 268 deselected
```

**28 de 42 fichas con clave declarada**, ni una más ni una menos. Es decir: dos
tercios del diccionario tenían un `grano` que no nombraba todas las columnas de
su propia clave, incluidas fichas de `mart` y `cierre` que tres revisiones
—las mías entre ellas— habían dado por veraces. Lo eran en columnas, en claves y
en cardinalidades; en granos, no.

Vale la pena decirlo claro porque es la lección de las cinco pasadas: **la
revisión humana caso a caso encontró dos; la comprobación derivada encontró 28**.

## Las 28 correcciones — la parte que había que mirar de verdad

El riesgo de reescribir 28 granos de golpe contra un criterio automático es que
alguno se escriba para el test y no para el lector. Lo verifiqué por dos vías: un
barrido propio en busca de coletillas —del tipo «… la clave incluye X, Y, Z»
pegado al final, que satisface el `\b` del test sin explicar nada— y el contraste
uno a uno contra el SQL.

Contrasté contra el SQL, uno a uno, **cinco de los 28** —los dos que motivaron
el rechazo (`v_pbi_proveedor_obra`, `v_pbi_albaranes_sin_facturar`) y otros tres
elegidos por ser los más fáciles de estropear: `fact_seguimiento_categoria`,
`v_pbi_cierre_resumen` y `retenciones.movimientos`—. Los cinco son ciertos, y uno
trae una corrección no trivial que nadie había pedido: `movimientos` pasa a
declarar la clave `(sentido, movimiento_id)` porque el identificador sale de
`p.ide` y de `c.ide` —dos secuencias distintas, `pag` y `cob`
(`retenciones/01_movimientos.sql:47-48, 97-98`)—, así que **solo es único dentro
de su sentido**. El barrido no encuentra coletillas, y el caso que motivó el
rechazo quedó así:

> «Una fila por (`obra_id`, `codigo_obra`, `proveedor_id`, `proveedor_nombre`,
> `proveedor_cif`, `anio`), que es su clave de negocio y son SEIS columnas, no
> tres. No basta con (obra, proveedor, ano): `proveedor_cif` sale del CIF que
> traía cada documento y NO depende de `proveedor_id`, así que dos facturas del
> mismo proveedor con CIF distinto dan DOS filas. Unir por tres columnas
> duplica.»

Eso no es satisfacer un test: es explicar la trampa que la review tardó tres
pasadas en aislar, y dejarla escrita donde el agente la va a leer.

**Los 28 se verificaron enteros**, uno a uno contra el SQL —19 de `mart` y
`cierre`, 9 de `compras` y `retenciones`— y **los 28 son ciertos**. El patrón de
la reescritura es homogéneo y honesto: traducir la palabra de negocio al nombre
de columna (`obra` → `obra_id`, `mes` → `anio_mes`, «renglón del cuadro» →
`concepto_cuadro`), sin inventar dimensiones, sin meter columnas redundantes para
pasar el test y sin prometer unicidad que el SQL no dé. Se comprobó además, con
las dos versiones del YAML parseadas y comparadas objeto a objeto, que **el único
campo que cambió es `grano`**: `columnas`, `clave_negocio`, `relaciones`,
`cardinalidad`, `descripcion`, `paso_etl` y `refresco` están intactos en los
cuatro ficheros. **Cero regresiones.**

Los dos defectos de arriba no son granos reescritos mal: son fichas que el
barrido de copias no visitó.

## El detector elegido — es el correcto, no el cómodo

Descartó dos variantes y las razones son buenas:

- **Casar la enumeración del grano con la clave** exige emparejar conceptos de
  negocio («obra», «mes») con nombres de columna (`obra_id`, `anio_mes`): un
  emparejamiento difuso que **marcaría de más**.
- **Contar dimensiones** no delata nada: las seis columnas de
  `v_pbi_proveedor_obra` son tres conceptos.
- **Exigir que los nombres aparezcan** es exacto, no admite interpretación y
  tiene un efecto colateral bueno: el grano pasa a decir por qué columnas hay que
  unir.

Su límite, dicho para que conste: es una comprobación **textual**, así que se
puede satisfacer mencionando la columna sin arreglar la contradicción. Por eso
las 28 correcciones necesitaban revisión humana, y por eso la hice.

## La derivación del congelado — correcta, y con control en los dos sentidos

Es la afirmación más fuerte de la tanda y es cierta en semántica PostgreSQL:
`CURRENT_DATE` dentro de un `CREATE TABLE … AS SELECT` se evalúa **una vez**, al
construir, y el valor queda materializado; dentro de una vista se reevalúa en
cada consulta. El detector solo marca columnas de **tablas**
(`test_f006_fichas.py:1843-1868`) y su control lo ancla en los dos sentidos:
exige que `retenciones` dé exactamente `{vencida_sin_liquidar,
dias_desde_vencimiento}` y que `compras.dias_desde_albaran` —que es de una
vista— **no** aparezca.

La herencia también es correcta: `v_pbi_retenciones_vencidas.antiguedad` se
calcula con un `CASE` sobre `dias_desde_vencimiento`
(`retenciones/02_views.sql:139-145`), que viene congelada de la tabla; y un
`SUM(importe) FILTER (WHERE vencida_sin_liquidar)` es tan de la fecha del build
como la marca, porque el conjunto de filas se decidió entonces.

Lo probé: quité la palabra «build» del significado de `antiguedad` y
`test_f006_r2_toda_columna_congelada_lo_advierte` se puso en rojo.

Y el aviso **llega completo y no se sobrepropaga**: se recorrieron las columnas
que dependen de `vencida_sin_liquidar` o `dias_desde_vencimiento` en el SQL
—`movimientos`, las dos de `vivas`, las cuatro de `vencidas` incluida
`antiguedad`, `entidad.importe_vencido`/`num_vencidas`,
`obra.vencido_proveedores`/`vencido_cliente` y
`resumen.importe_vencido`/`num_vencidas`— y **todas lo declaran**; mientras que
`compras.dias_desde_albaran`, que vive en un `CREATE VIEW` y por tanto se
recalcula, **no** lo dice, que es lo correcto.

**Dónde puede quedarse corto** (deuda, no defecto): el conjunto de columnas
congeladas se agrupa **por esquema**, no por objeto, y la herencia es de
profundidad uno —una vista que referenciara una columna heredada de otra vista no
se marcaría—. Hoy no existe ninguna cadena así, y agrupar por esquema peca de
conservador, que es el lado bueno del error.

## Lo demás que declaraba

| Punto | Verificado |
|---|---|
| **P12 de la batería** | Corregido, y bien: «no generaliza la regla: en `compras.v_pbi_contrato_consumo` el pendiente se suma sin filtrar, así que allí las NOTA también cuentan» |
| **Vía (a), tablas agregadas** | **Probado por mí**: puse `num_partidas` en `suma` y falla `test_f006_r7_la_agregacion_de_las_tablas_agregadas_casa_con_el_sql`. Antes no lo cubría nada |
| **PK inline** | Corregido: `pk_declarada` devuelve ahora `['fact_id']` y `['cierre_id']` donde antes daba `None`, y sigue dando `None` para el CTAS sin PK. Los tres motivos de skip falsos, resueltos |
| **El aserto que impedía crecer** | Sustituido por el invariante de prefijo (`proyectadas[:18] == COLUMNAS_V_DICCIONARIO[:18]`), que es el correcto: permite añadir al final, que es lo único que el contrato declara compatible |
| **Los dos docstrings** | Corregidos. El del `rollback` distingue ahora que el `commit` sí se ejecutaba y solo el `rollback` no |
| **Vía (b), diferida a T26** | El SQL hace lo que dice (ver abajo) y el reparto es sensato: T26 construye el comando, T27 lo ejecuta contra la base como verificación MANUAL (humano), coherente con la regla de que ningún agente abre conexión |

---

## Rigor y comprobaciones de siempre

- **1359 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 % de 718
  líneas**. Los 40 saltados siguen siendo los mismos cinco grupos ya auditados en
  la cuarta pasada, ahora con los tres motivos falsos de PK corregidos.
- **Mutación verificada de forma independiente**: alcance **2324 líneas** y
  **161 mutantes** recalculados; coinciden con `progress/mutacion_F-006.md`; cero
  supervivientes. (No varía respecto a la tanda anterior porque estos cuatro
  commits tocan YAML, tests y specs, no código de producción.)
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` ni ningún SQL de negocio; ni un `GRANT`,
  `REVOKE`, firewall o Azure; ninguna conexión a la base. **Sin `push`**: no
  existe rama remota de la feature.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos, `PENDIENTES_MAX`
  = 53.
- Árbol limpio; mis experimentos se hicieron en worktrees aislados ya eliminados.

### Checkpoints (quinta pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —dos
fichas siguen declarando algo que el SQL desmiente (defectos 1 y 2): una clave
que no identifica una fila y una nulidad imposible. Todo lo demás de C4 está
cumplido, y el resto del diccionario —49 fichas, 593 columnas— sí cuadra— ·
**C4 bis** `[x]` · **C4 ter** N/A · **C5** N/A parcial (20 de 42 tareas, el
alcance encargado).

---

# CUARTA PASADA · 2026-08-20 — cierre de los defectos del bloque E y F

> Commits revisados: `efbef48`..`c20c933` (cinco). Mismo alcance: T15–T18,
> T20 y T21.

## Veredicto de la cuarta pasada

**RECHAZADO**, por poco y por una sola razón: **tres de los defectos dados por
cerrados lo están en el campo que la review señaló y siguen abiertos en el campo
vecino de la misma ficha**, y dos de ellos son afirmaciones falsas en el `grano`,
que es lo primero que un agente lee.

Todo lo demás está bien, y es mucho: el contrato con `mcp-bbdd` quedó resuelto
como debía, el mecanismo derivable funciona y no marca de más, y los 40 tests
saltados —el punto por el que había que empezar— tienen explicación buena.

**Rectifico además mi propia verificación**: di por cerrados los defectos (a),
(e) y el del congelado tras comprobar `clave_negocio` y la ficha de la columna.
No miré el `grano` ni las dos vistas derivadas, y ahí seguían. La lección es del
proceso, no de una persona: **cuando se corrige una afirmación hay que buscar sus
copias en el mismo fichero**, porque esta es la tercera vez que el defecto
sobrevive en el campo de al lado —pasó con el ejemplo de `design.md`, con los
residuos de «mes anterior» y ahora con los granos—.

---

## Lo que hay que corregir

1. **El `grano` contradice a su propia `clave_negocio`, y el grano es el que
   induce el fan-out.** En `v_pbi_proveedor_obra` la clave pasó a las seis
   columnas del `GROUP BY` (`compras.yaml:710`) pero el `grano` sigue diciendo
   «Una fila por (obra, proveedor, ano)» (`:707-709`). Son incompatibles: si
   `proveedor_cif` no depende funcionalmente de `proveedor_id` —y no depende,
   sale de `entcif` del documento— entonces hay más de una fila por (obra,
   proveedor, año), que es justo el motivo por el que se amplió la clave. Quien
   lea el grano unirá por tres columnas y duplicará. Idéntico en
   `v_pbi_partida_coste`: clave de cinco (`:904`), grano «Una fila por (obra,
   partida)» (`:900-901`).
2. **La regla falsa de la NOTA sobrevive en el `grano` de la vista vecina.** La
   corrección quedó bien en la ficha de `tipo_documento` (`:329-333`) y en la de
   `importe_albaranado_sin_facturar` (`:659-666`), pero el `grano` de
   `v_pbi_albaranes_sin_facturar` (`:803-806`) mantiene la formulación general:
   «las notas de cargo suman en el consumido del contrato pero no cuentan como
   pendiente de facturar». La segunda mitad es **exactamente lo que es falso** en
   `v_pbi_contrato_consumo`, cuyo `SUM(pendiente_facturar)` no filtra por tipo
   (`compras/03_views.sql:42`). El test que fija la corrección no mira ese campo.
3. **El aviso de congelado no llega a las dos vistas donde aterriza la
   pregunta.** En la tabla base quedó muy bien explicado, pero
   `v_pbi_retenciones_vivas` (`retenciones.yaml:477-482`) sigue diciendo «Si la
   fecha prevista ya paso» y «Dias desde el vencimiento», y
   `v_pbi_retenciones_vencidas` (`:541-543`) «Cuantos dias lleva vencido», las
   dos sin advertir de que ambas columnas se calcularon con `CURRENT_DATE` **en
   el build** (`retenciones/01_movimientos.sql:21, 77-79, 120-122`) y llevan
   parados los días que lleve sin reconstruirse el esquema. Son las vistas que
   responden P13 de la batería, y mi informe anterior las citó por número de
   línea.

### Menores (arreglar al pasar)

4. **El detector de PK tiene un punto ciego y su mensaje de skip miente.**
   `pk_declarada` reconoce `ALTER TABLE … ADD PRIMARY KEY (col)` —por eso cubre
   de verdad 8 de las 12 tablas— pero **no la forma inline** `col TIPO PRIMARY
   KEY`. Llamé a la función: devuelve `None` para `mart.fact_seguimiento_mensual`,
   `mart.fact_seguimiento_categoria` y `cierre.fact_cierre_mensual`, cuyos DDL la
   declaran en la propia columna. El test las salta diciendo «el DDL no declara
   clave primaria para este objeto», **que es falso**. Hoy no cuesta nada —esas
   tres habrían saltado igual por la rama «la PK es una clave sustituta»—, pero
   el día que alguien declare una PK de negocio inline, el test la saltará en
   silencio. Su control prueba positivo y negativo, pero solo de la forma `ALTER
   TABLE`, así que no ve el hueco.
5. **Un aserto rompe el crecimiento que el propio contrato declara compatible.**
   `test_f006_publicacion.py:989` fija `proyectadas[-1] == "motivo_no_consumo"`.
   Añadir una columna **al final** —lo único que la cabecera del DDL permite sin
   romper a nadie— pone ese aserto en rojo aunque se actualicen SQL, `design.md`
   y la lista. El invariante correcto es el prefijo de 18, que ya está en la
   línea siguiente.
6. **Dos docstrings afirman de más.** El del `rollback` dice que «el `commit` y
   el `rollback` reales no se ejecutaban en ningún test»: lo del `rollback` es
   cierto y está demostrado, pero el `commit` **sí** se ejecutaba
   (`test_f005_conexion.py` usa el `connection()` real). Y el de `apply_grants`
   es un test **estructural** —comprueba `depends_on`—, no conductual: protege
   del escenario que nombra, no de un cambio en la lógica de salto del
   orquestador. Es la misma clase de sobreventa que ya se corrigió dos veces.
7. Tres medidas más de la clase «`SUM(…) FILTER` sin `COALESCE`, NULL no
   declarado» quedan sin `nulo_significa` —`v_pbi_retencion_resumen.saldo_vivo`,
   `.importe_liquidado`, `.importe_vencido`— mientras sus hermanas del mismo
   fichero sí lo declaran; `compras.yaml:662-664` dice «es el único agregado de
   la vista que se suma SIN filtrar por tipo», y no lo es (`importe_facturado`
   tampoco filtra, y la propia ficha lo admite en `:646-652`); y
   `fact_compras_linea.proveedor_id` (`:91-93`) no declara `nulo_significa`
   pese a salir de un `NULLIF(entide, 0)`, siendo la tabla a la que la ficha
   vecina te manda «para no perder las líneas sin proveedor».

### El mecanismo: dos puntos ciegos que explican por qué pasan estos tres

- **El contraste `clave_negocio` ⊆ `GROUP BY` es de subconjunto, no de
  igualdad** (`test_f006_fichas.py:1399`). Por eso una clave corta lo pasaba
  antes y por eso hoy nada impide que el `grano` diga menos que la clave.
- **Nada contrasta el `grano` con la `clave_negocio`**, y buena parte de eso
  **sí es derivable**: cuando el `grano` enumera columnas entre paréntesis
  —«Una fila por (obra, proveedor, ano)»—, esa enumeración debería casar con la
  clave declarada, o declararse explícitamente como resumen. Es un test corto y
  habría cazado los defectos 1 y 2 de esta lista.
- Además, el contraste de agregación excluye `TABLAS_CON_DDL_EXPLICITO`
  (`:1263`), así que `mart.fact_seguimiento_categoria.num_partidas` —un
  `COUNT(DISTINCT)`— hoy está bien pero nada lo fija.

---

## Lo que sí está cerrado, verificado

### Los 40 saltados — explicados, y ninguno esquiva nada que antes corriera

| Nº | Motivo impreso | Veredicto |
|---|---|---|
| 2 | «se crea con SQL dinámico; tiene su propio test» | **legítimo**, ya validado |
| 3 | «la proyección no se deja leer» (agregación) | **legítimo** |
| 3 | ídem (`GROUP BY`) | **legítimo** |
| 28 | «el `GROUP BY` no es derivable» | **legítimo** |
| 4 | «el DDL no declara clave primaria» | **motivo falso en 3 de los 4** (defecto 4) |

Los tres tests son **nuevos de esta tanda**, parametrizados sobre las 49 fichas,
y saltan donde no aplican; lo que ya existía sigue ejecutándose entero. Los 3+3
de «proyección ilegible» son los tres catálogos `SELECT * FROM (VALUES …)`, y
**comprobé que los tres siguen cubiertos** por el test de proyección exacta, que
pasa para los tres. Los 28 del `GROUP BY` son legítimos: el test corre sobre las
**seis** vistas con `GROUP BY` directo y salta donde la agregación vive en CTEs
bajo un `UNION`; su test de control ancla el alcance en los dos sentidos —exige
que tres objetos SÍ se lean y que uno con `UNION` NO—, que es lo que impide que
se degrade en silencio.

### El contrato (defecto 6) — cerrado y bien resuelto

`motivo_no_consumo` se queda —el MCP necesita el porqué— pero **al final**: las
18 columnas del contrato conservan su posición. Extraje el orden de las dos
fuentes y **coinciden posición por posición**. `design.md` §4.2 se enmendó con
nota fechada, y también su bloque SQL, no solo la nota.

Y los tests **fijan posiciones, no presencia**, probado en worktree aislado:

| Experimento | Resultado |
|---|---|
| Intercambiar `d.tipo` y `d.capa` | **detectado**: `At index 2 diff` |
| Mover `motivo_no_consumo` al medio | **detectado**: `At index 5 diff` |

Los cuatro menores del contrato también: los denominadores de `cobertura_cols` y
`n_columnas` quedan explicados en dos `COMMENT ON COLUMN` —en la base, que es
donde el MCP los lee—; el DDL dice ahora que la identidad es `hash_fuente` y no
`version`; y las cifras viejas de T19 están corregidas a 49 y 12.

### El mecanismo — funciona y no marca de más

- **`agregacion` contra la función del SQL**: corre en **34 de 37** casos, y su
  criterio es más fino que el que yo habría escrito: distingue
  `COUNT(DISTINCT …)` de `COUNT(*)` sobre particiones disjuntas, que sí es
  aditivo. Lo comprobé por la vía contraria: un detector tosco («todo COUNT es
  no sumable») **habría marcado nueve columnas de más**; el suyo no marca
  ninguna.
- **Los cinco `COUNT(DISTINCT)` son ciertos**: los tres que encontré a mano más
  `num_entidades` y `num_obras` de `v_pbi_retencion_resumen`
  (`retenciones/02_views.sql:161-162`), que **no vi**. Es el argumento a favor de
  derivar en vez de revisar a ojo.

### Las fichas — cinco de los seis graves, cerrados

Cerrados y verificados contra el SQL: los tres contadores a `no_sumable`; los
negativos imposibles de `v_pbi_albaranes_sin_facturar` («la vista filtra `> 0`,
así que las líneas sobrefacturadas **no aparecen**»); las claves de las dos
vistas fuente de `retenciones`, resueltas **mejor de lo pedido** —`clave_negocio:
[]` con el `grano` advirtiendo que el par es «exactamente el que produce el
fan-out de `R-RETENCION-NO-JOIN-LINEAS`, y por eso esta vista se agrega SIEMPRE
por documento antes de usarse»—; los cuatro medios; y los once menores 12-20.

**Sobre la clave vacía declarada**: es mejor que una clave inventada y **no abre
puerta trasera**. El validador la admite **solo fuera de la superficie de
consumo** (`domain/diccionario.py:499-505`), y salir de ella cuesta escribir un
`motivo_no_consumo` con mínimo de longitud, visible en el diff. Una clave
inventada manda al agente a un JOIN que multiplica; un hueco declarado le dice
que esa vista no deduplica.

**Sin regresión en `mart` ni `cierre`**: el diff de esta tanda toca solo
`compras.yaml` y `retenciones.yaml`; los otros tres YAML son idénticos byte a
byte, y sus granos, claves y cardinalidades se revalidaron igualmente.

### Los dos tests sin fase RED — justificados, y el hueco existía

El del `rollback` cubre una ruta que **ningún test del repositorio ejecutaba**:
confirmado empíricamente instrumentando `connection()` en una copia del commit
anterior y corriendo su suite entera —la marca de `commit` se crea, la de
`rollback` no—. El test nuevo pisa la ruta real: solo sustituye la apertura del
socket. Y `apply_grants` sigue corriendo con la publicación fallida, verificado
montando el pipeline (`build_mart SUCCESS / publicar_diccionario FAILED /
apply_grants SUCCESS`).

### `CLAUDE.md` — corregido con precisión

Pasa de «hay una puerta que lo exige» a «la puerta exige **ficha o pendiente
declarado**: se puede aplazar la ficha, pero no ignorarla, y la lista de
pendientes solo baja». Es exactamente lo que la puerta hace.

### La acotación de lo no derivable — honesta, y dos vías que aporto

Que la clave sea *demasiado corta* exige dependencias funcionales que no siempre
están en el texto: `proveedor_cif` no depende de `proveedor_id` —sale del CIF que
traía cada documento— y aun así se escribe igual que una columna que sí
dependiera. Forzar la igualdad con el `GROUP BY` marcaría fichas correctas
—`mart.fact_seguimiento_categoria` agrupa por nueve columnas de las que cinco se
derivan de otras dos—: **la acotación es honesta**. Dos vías que no aparecen en
su informe:

> **Corrección del 2026-08-20 (sexta pasada).** Este párrafo decía «`codigo_obra`
> depende de `obra_id` y omitirla es correcto». **Era falso**, y el error es mío:
> en `retenciones.movimientos` las dos salen de cascadas distintas
> (`01_movimientos.sql:61-64`) y en `compras.v_pbi_partida_coste` la ficha lo
> dice con esas palabras. El implementer tomó la frase de aquí como fundamento
> del límite del test y su propia corrección la desmintió. El límite sigue siendo
> real —lo es por `proveedor_cif`—, pero el ejemplo que lo ilustraba era
> justamente un caso en el que la dependencia **no** existe. Queda corregido
> arriba y en `tests/test_f006_fichas.py`.

- **Derivable hoy y gratis**: las tablas agregadas que se llenan con
  `INSERT … SELECT … GROUP BY` —`mart.fact_seguimiento_categoria`,
  `sql/mart/03_agg_categoria.sql`— tienen su `GROUP BY` en el repositorio, y
  ningún mecanismo comprueba su clave: el de `GROUP BY` solo mira vistas y el de
  PK las salta por clave sustituta. Es el mismo parser sobre otra sentencia.
- **La definitiva**: que `check-diccionario` (R28, T27) incluya una consulta de
  unicidad por objeto —`SELECT count(*) - count(DISTINCT (clave)) FROM …`—.
  Liquida el problema entero, dependencias funcionales incluidas, con una
  consulta barata por objeto. Conviene declararlo como parte de T27 antes de que
  se escriba.

---

## Rigor y comprobaciones de siempre

- **1310 tests + 40 saltados**, ejecutados por mí; cobertura **98,9 %**.
- **Mutación verificada de forma independiente**: recalculé alcance (**2324
  líneas**) y mutantes (**161**); coinciden con `progress/mutacion_F-006.md`;
  cero supervivientes.
- **Nada prohibido**: el diff no toca `main.py`, `settings.py`, `grants.py`,
  `infra/**` ni ningún SQL de negocio; ni un `GRANT`, `REVOKE`, firewall o Azure;
  ninguna conexión a la base. **Sin `push`**: no existe rama remota de la feature.
- `ruff` se queda en 161 avisos, los mismos que antes: no añade deuda.
- Trinquete coherente: 49 fichas + 53 pendientes = 102 objetos, y
  `PENDIENTES_MAX` vale 53.

### Checkpoints (cuarta pasada)

**C1** `[x]` · **C2** `[x]` · **C3** `[x]` · **C3 bis** N/A · **C4** `[ ]` —tres
fichas siguen declarando en su `grano` algo que el SQL desmiente (defectos 1-3);
todo lo demás de C4 está cumplido— · **C4 bis** `[x]` · **C4 ter** N/A · **C5**
N/A parcial (20 de 42 tareas, el alcance encargado).

---

# TERCERA PASADA · 2026-08-20 — bloque E y bloque F parcial

> Commits revisados: `5b5e8ff`..`206eae3` (doce: cinco de arrastres de la
> segunda pasada y siete del trabajo nuevo). Alcance: **T15–T18** (publicación
> en `_meta`) y **T20, T21** (fichas de `compras` y `retenciones`).

## Veredicto de la tercera pasada

**RECHAZADO.**

El **bloque E está casi bien hecho** —el contrato cumple sus tres invariantes y
sus tres tablas son idénticas a `design.md` §4.1, aunque **la vista se desvía**
(defecto 6)—, el trinquete
reformulado **aguanta las cinco vías de burla** que le probé, y los cinco
arrastres de la segunda pasada están cerrados. Nada de eso salva la entrega:
**las fichas nuevas de `compras` y `retenciones` mienten en cinco puntos que
producen números falsos**, y el criterio de esta feature es explícito —una ficha
que miente es motivo de rechazo aunque todo lo demás esté bien—.

Lo que más pesa: la ficha de `compras.albaranes` enuncia como regla general una
de las trampas que esta feature existe para contar bien —«la NOTA suma en el
consumido pero no en el pendiente»— y **es falsa en una de las dos vistas donde
se aplica**. Tres contadores `COUNT(DISTINCT …)` van marcados `agregacion:
suma`, que es justo el campo que el MCP traduce a «esta columna se suma». Y dos
fichas de `retenciones` declaran una clave de negocio que **contradice su propio
grano** y que es exactamente el par que produce el fan-out que el fichero
declara como la regla que más dinero ha costado.

No es un problema de volumen ni de descuido puntual: **la puerta no contrasta
con el SQL ni las claves de negocio ni el campo `agregacion`**, y son los dos
huecos que ya señalé en la segunda pasada (experimentos E6 y E11). Entonces no
habían hecho daño porque `mart` y `cierre` tienen claves simples; `compras` y
`retenciones` las tienen compuestas, y ahí es donde se ha caído.

---

## Lo que hay que corregir

### Graves · afirmaciones que producen números falsos

1. **`compras.yaml:326-328` — la regla de la NOTA es falsa en `v_pbi_contrato_consumo`.**
   La ficha de `albaranes.tipo_documento` dice, sin acotar: «Solo ALBARAN y
   PROFORMA cuentan como pendiente de facturar; la NOTA suma en el consumido
   pero no en el pendiente». Es cierto en `v_pbi_albaranes_sin_facturar`
   (`03_views.sql:172`) y **falso** en `v_pbi_contrato_consumo`: en la CTE
   `alb_pivot`, las tres primeras medidas llevan `FILTER` por tipo y
   `SUM(pendiente_facturar)` **no lo lleva** (`03_views.sql:39-42`), así que
   `importe_albaranado_sin_facturar` incluye NOTA y OTRO. Ni esa ficha ni la de
   la columna (`compras.yaml:652-657`) lo dicen.
2. **`compras.yaml:741,744,747` — tres `COUNT(DISTINCT …)` declarados sumables.**
   `num_facturas`, `num_albaranes` y `num_contratos` llevan `agregacion: suma` y
   son `COUNT(DISTINCT documento_id)` / `COUNT(DISTINCT contrato_id)`
   (`03_views.sql:126-130`). Una factura repartida entre tres obras aparece en
   tres filas con valor 1: sumarlas da tres facturas donde hay una. El
   vocabulario cerrado ya tiene `no_sumable` para esto.
3. **`retenciones.yaml:639` y `:667` — clave de negocio que contradice su propio
   grano.** `v_src_lineas_compra` es `SELECT docide, obride FROM raw.dcfpro`
   (`retenciones/00_setup.sql:101-103`): **una fila por línea**, como dice su
   propio `grano`. La `clave_negocio: [docide, obride]` declarada se repite
   tantas veces como líneas tenga la factura contra esa obra. Es el par que
   produce el fan-out de `R-RETENCION-NO-JOIN-LINEAS`, ofrecido como clave. Lo
   mismo en `v_src_lineas_venta`, hoy inocuo porque la vista está vacía, pero la
   ficha describe la forma que tendrá cuando se ingiera `dvfpro`.
4. **`compras.yaml:827-831` — anuncia negativos que la vista no puede devolver.**
   `v_pbi_albaranes_sin_facturar.importe_pendiente_facturar` dice que «NEGATIVO
   significa que se facturó de más, y el signo se conserva a propósito». La
   vista filtra `WHERE l.importe_pendiente_facturar > 0` (`03_views.sql:171`):
   ahí no hay negativos. El texto es correcto en `albaran_lineas`
   (`compras.yaml:436-441`), de donde parece copiado. Quien pregunte por
   sobrefacturación mirará aquí y concluirá que no existe.
5. **`compras.yaml:699` — clave de negocio reducida en `v_pbi_proveedor_obra`.**
   Declara `[obra_id, proveedor_id, anio]`; el `GROUP BY` real tiene seis
   columnas (`03_views.sql:133-134`), y `proveedor_cif` **no** depende de
   `proveedor_id`: sale del CIF del documento, como la propia ficha admite en
   `:716`. Dos facturas del mismo proveedor con `entcif` distinto dan dos filas
   para la clave declarada.

6. **`sql/ddl/01_diccionario.sql:118` — la vista del contrato se desvía de la
   spec, y de la forma que el propio fichero prohíbe.** `_meta.v_diccionario`
   proyecta **19 columnas**; `design.md` §4.2 especifica **18**. La añadida es
   `motivo_no_consumo`, y no está al final: va **en posición 6**, entre
   `consumo_recomendado` y `descripcion`. La cabecera del mismo fichero, cuatro
   líneas más arriba (`:10-16`), dice: «QUE SE PUEDE CAMBIAR SIN ROMPER A NADIE:
   añadir columnas **AL FINAL**… QUE NO: quitar o **reordenar** columnas de la
   vista». La columna es una buena idea —el MCP necesita el porqué de un objeto
   no recomendado—, pero esta es **la mitad del contrato que `mcp-bbdd` va a
   consultar de verdad**, y quien implemente contra la spec y desempaquete por
   posición se encontrará los campos corridos a partir del sexto. `design.md`
   §4.2 **no se enmendó**, y en esta misma tanda sí se enmendaron sus recuentos,
   así que la ocasión estaba. **Decidir ahora**: mover la columna al final o
   enmendar §4.2. Dejarlo como está, no.
7. **La vista es la única de las cuatro estructuras sin test que fije sus
   columnas.** Las tres tablas tienen contraste exacto y parametrizado
   (`tests/test_f006_publicacion.py:157`); la vista solo tiene una comprobación
   de presencia por subcadena de 15 de sus 19 nombres (`:190`), que además omite
   justo `tipo`, `capa`, `consumo_recomendado` y `motivo_no_consumo`. Rigor
   asimétrico en la pieza más expuesta: falta el test con la lista completa **y
   ordenada**.

### Medias

8. **`compras.yaml:712` — `nulo_significa` imposible y, peor, un filtro no
   documentado.** La vista lleva `WHERE proveedor_id IS NOT NULL`
   (`03_views.sql:132`): la fila que la ficha describe no existe, y **las líneas
   sin proveedor desaparecen de la vista** sin que ninguna ficha lo advierta. La
   pérdida silenciosa de `obra_id IS NULL` sí está protegida (`:705-708`); esta
   es la misma familia, contada a medias.
9. **`retenciones.yaml:72` — `tipo_id.nulo_significa` imposible.** Las dos ramas
   filtran `WHERE COALESCE(retide, 0) <> 0` (`01_movimientos.sql:89,131`): un
   efecto sin tipo no entra en la tabla. Quien busque `WHERE tipo_id IS NULL`
   obtendrá cero filas y concluirá que no hay efectos sin tipo.
10. **Ocho medidas que devuelven NULL y no lo declaran.** Los cuatro importes de
   `v_pbi_proveedor_obra` (`compras.yaml:721-738`) y los cuatro de
   `v_pbi_partida_coste` (`:885-901`) son `SUM(…) FILTER (…)` **sin
   `COALESCE`** (`03_views.sql:118-125`, `:188-195`). El contraste lo delata:
   `v_pbi_contrato_consumo` sí envuelve en `COALESCE(...,0)` (`:77-82`) y por eso
   allí no hace falta declararlo. `WHERE facturado > 0` pierde filas en silencio.
11. **`retenciones.yaml:145-154` (y sus copias en `:466-471`, `:530-532`) —
   `vencida_sin_liquidar` y `dias_desde_vencimiento` están congelados.**
   `movimientos` es un `CREATE TABLE AS` (`01_movimientos.sql:21`) y ambas se
   calculan con `CURRENT_DATE` **en el build** (`:77-79`, `:120-122`). El texto
   («días transcurridos desde la fecha prevista», «la fecha prevista ya pasó»)
   se lee como *hoy*. En un esquema de refresco manual **cuya frescura ni
   siquiera es consultable por SQL**, la lista de vencidas puede llevar semanas
   parada y nadie puede saber cuánto. Hay que decir que para vencimiento a fecha
   de hoy se recalcula sobre `fecha_prevista_devolucion`.

### Menores (arreglar al pasar, no bloquean por sí solos)

12. `compras.yaml:45` — `(tipo_doc, linea_id)` es correcta para los seis tipos
    nombrados, pero `OTRO` es alcanzable desde dos ramas del UNION
    (`00_setup.sql:40` y `:43`, `tip=14` y `tip=15` con serie desconocida), así
    que ahí vuelve a colisionar. Basta con decirlo en la ficha.
13. `compras.yaml:863` — `v_pbi_partida_coste` declara `[obra_id, partida_id]` y
    el `GROUP BY` incluye `codigo_obra`, que se resuelve con una cadena
    `COALESCE` distinta de `obra_id` (`02_fact_linea.sql:52-53` y `:83-84`).
14. `compras.yaml:77-81` — la cascada de `obra_id` omite el respaldo por
    contrato: el SQL es `COALESCE(l.obra_id, ctr.obra_id)` (`02_fact_linea.sql:52`).
15. `compras.yaml:799-803` — `contrato_id` sale solo de la cabecera y
    `codigo_contrato` de `COALESCE(a.contrato_id, l.contrato_id_linea)`
    (`03_views.sql:169-170`): pueden salir juntos nulo e informado.
16. `retenciones.yaml:344-347` — invita a cuadrar euros contra
    `sin_obra_asignada`, que es un `COUNT`, no un importe (`02_views.sql:170`).
17. `retenciones.yaml:117-122` — `num_obras_documento` es **siempre 0** en
    sentido CLIENTE, porque se alimenta de la vista vacía; se describe como «lo
    que explica que la obra esté vacía», y para CLIENTE nunca explica nada.
18. `retenciones.yaml:168-175` — la relación a `compras.facturas` solo casa en
    sentido PROVEEDOR; la ficha gemela de `v_pbi_retencion_entidad` (`:326-331`)
    sí lo acota, esta no.
19. `retenciones.yaml:607-610` dice que las dos lecturas del saldo «no hay que
    compararlas entre sí» cuando el SQL dice lo contrario (`02_views.sql:19-20`):
    la divergencia **es** el diagnóstico.
20. `compras.yaml:640-644` y `:951-954`, `:971-975`: `importe_facturado` suma sin
    filtrar tipo; `fn_serie` devuelve cadena vacía, no NULL, y su ejemplo no es
    el formato real de Sigrid (`00_setup.sql:24-25`).
21. `diccionario_sql.py:38-40` justifica `DELETE` frente a `TRUNCATE` diciendo
    que «`TRUNCATE` no es transaccional de la misma forma en todos los
    escenarios». En PostgreSQL `TRUNCATE` **sí** es transaccional; la razón
    buena es que toma un `ACCESS EXCLUSIVE` que bloquea a los lectores, que es
    justo lo que aquí se quiere evitar. La decisión es correcta; el motivo
    escrito, no.
22. **`CLAUDE.md` promete más de lo que la puerta hace.** Dice que «quien añade o
    cambia un objeto publicado actualiza su ficha en el mismo trabajo: hay una
    puerta en `init.sh` que lo exige». Lo comprobé (**experimento E14**): publicar
    una vista nueva sin ficha, declararla en `pendientes` y subir el tope **pasa
    la puerta de cobertura**; lo único que salta es, de rebote, el test que
    cuenta objetos contra `design.md`. Lo que la puerta exige es «ficha **o**
    pendiente declarado». Rebajar la frase o cerrar el hueco.

23. **Falta el test de que `apply_grants` siga corriendo cuando
    `publicar_diccionario` falla.** Hoy es cierto porque
    `ApplyGrantsStep.depends_on == ["build_mart"]` y el orquestador solo salta
    un paso si falló una dependencia **declarada**. Pero nada lo fija: el día
    que alguien añada `"publicar_diccionario"` a esas dependencias «para que
    quede ordenado», una noche con el diccionario inválido dejaría al MCP sin
    `GRANT` — que es exactamente el fallo que R20 existe para evitar. Es un test
    de una línea.
24. **`cobertura_cols` y `n_columnas` no comparten denominador.** `n_columnas`
    publica **593** (todas las fichas) y `cobertura_columnas` se mide solo sobre
    `consumo_recomendado: true` (**554**). Hoy ambos dan 100 % y no se nota,
    pero `n_columnas * cobertura_cols / 100` no es el número de columnas
    documentadas. Sin `COMMENT ON COLUMN` que lo aclare ni mención en la spec, un
    consumidor razonable los combinará.
25. **La atomicidad está probada estructuralmente, no conductualmente.** El
    doble sustituye `connection()` entera, así que el `commit`/`rollback` real
    de `postgres_client.py:332-334` no se ejecuta en ningún test del
    repositorio. Falta uno que compruebe que una excepción a mitad del `with`
    provoca `rollback()`.
26. **`version` es un `1` estático que nadie incrementa** (`00_global.yaml`). Si
    `mcp-bbdd` lo usa para invalidar caché, no invalidará nunca: la identidad
    real es `hash_fuente`, y eso solo está dicho en un comentario del SQL. DA-5
    decidió «número manual **más** hash»; el número está, pero conviene
    documentar en el DDL cuál de los dos manda.
27. **`progress/impl_F-006.md` da por buena una comprobación con cifras
    viejas**: la verificación manual de T19 habla de «37 filas en
    `_meta.diccionario` (25 fichas hoy)» cuando ya son **49** y **62**. Quien
    ejecute T19 verá un desajuste que no es un fallo.

### Y el mecanismo, que es lo que evita la próxima vez

Los cinco defectos graves los habría cazado la puerta si comprobara dos cosas
que hoy no comprueba, y que ya salieron en la segunda pasada (E6, E11):

- **Contrastar `clave_negocio` contra el SQL**: para las vistas, comparar con
  las columnas del `GROUP BY`; para las tablas, con la PK del DDL. Ambas son
  derivables con el parser que ya existe. Habría cazado los defectos 3, 5 y 11.
- **Contrastar `agregacion` con la función del alias**: `COUNT(DISTINCT …)` no
  puede ser `suma`. Habría cazado el defecto 2.

Mientras eso no exista, cada esquema con claves compuestas exige revisión
humana columna a columna, y eso no escala a los 45 objetos que quedan.

---

## Lo que sí está bien, verificado

### El contrato con `mcp-bbdd` (bloque E)

- **Las tres tablas, columna por columna iguales a `design.md` §4.1.** Extraje
  los nombres del DDL real y del diseño: **coinciden exactamente**, en el mismo
  orden, incluido el `CHECK (id = 1)` del singleton. Tienen además test de
  contraste exacto y parametrizado. **La vista es la excepción, y es el defecto
  6**: rectifico aquí mi propia comprobación inicial, que se quedó en §4.1.
- **Invariante del orden**: `build_pipeline_steps` compone `IngestRaw →
  LoadExcelAux → BuildStg → BuildMart → **PublicarDiccionario** → ApplyGrants`
  (`main.py`), con el motivo escrito en el propio código: `apply_grants` es una
  foto del instante, y publicar después dejaría las tres tablas nuevas sin
  `GRANT` para el rol del MCP.
- **Invariante del reemplazo**: `DELETE` + `INSERT`
  (`diccionario_sql.py:41-43`), y **ni un `DROP` ni un `TRUNCATE` ejecutable** en
  el DDL, en los constructores ni en el paso: las únicas apariciones de esas
  palabras son comentarios que explican por qué no se usan.
- **Reusa la conexión abierta** en vez de abrir una segunda contra el servidor
  compartido, y el comando suelto valida con los pasos nocturnos de la
  composición real, no con una lista escrita a mano.
- **R19 y R21 se cumplen y están bien probados**: si el diccionario no valida,
  el cliente ni siquiera se instancia, y los tests lo demuestran con un espía
  cuyo `connection()` **lanza excepción si alguien lo llama**, comprobando
  después que la lista de llamadas está vacía. El fallo termina en `FAILED` y
  `run-all` sale con código 1 sin tocar el build de datos.
- **El `hash_fuente` es reproducible de verdad**: ordena los ficheros, incluye
  el nombre de cada uno y **normaliza `\r\n` a `\n`** —el detalle que casi
  siempre se olvida y que haría que el mismo diccionario diera dos hashes según
  el puesto—, con tests para las cuatro propiedades.
- **El test de las 49 fichas prueba lo que dice**: carga el diccionario real de
  `config/diccionario/`, no una maqueta; el cliente es el de producción con solo
  `connection` sustituida; y las 62 filas están **derivadas** (49 objetos + 12
  reglas + 1 publicación), no cableadas. El doble registra el orden real de las
  sentencias, y con él se comprueba que los `DELETE` preceden a los `INSERT` y
  que todo cae dentro de una única transacción.

### El trinquete reformulado

Cambió de «cada revisión cabe en la anterior» a «ningún objeto que tuvo ficha
vuelve a `pendientes`», y el motivo es legítimo: el DDL del contrato añadió
cuatro objetos nuevos a `_meta` y la comparación cruda los daba por regresión.
**Le probé cinco vías y ninguna pasa**: desdocumentar una ficha vieja y subir el
tope (**E1**); hacerlo con una ficha estrenada en este mismo commit (**E12**,
nuevo); **commitear** el retroceso para que el árbol coincida con HEAD (**E9**);
renombrar el fichero de esquema y borrar la ficha en el mismo commit (**E13**,
nuevo); y la ficha esquelética de `x` (**E2**). Además siguen cazados el resto de
experimentos de las pasadas anteriores (**E3**, columna de otra vista del mismo
fichero SQL). El falso positivo se arregló **sin** abrir un falso negativo en lo
que importa. El único hueco que queda es el consciente y acotado del defecto 20.

### Los arrastres de la segunda pasada

Los cinco, cerrados y verificados: el `porque` de `v_pbi_planif_vs_real` ahora
explica que la vista colapsó `categoria` dentro de `concepto_cuadro` y que no
hay clave directa; el de `v_pbi_cp_tipologia` pasa a `(obra_id, anio)` diciendo
que el ámbito lo fija el SQL; `final_pct` da el mapa real de divisores; queda
**un** «mes anterior» en todo `cierre.yaml`, y es el legítimo; y el informe
rebajó su afirmación sobre granos y claves. Hay además un test que exige que las
columnas citadas en un `porque` existan.

### Los tres hallazgos que el implementer se apunta

- **Las tablas `CREATE TABLE AS SELECT` no las comprobaba nadie**: cierto, y
  ahora el test de proyección exacta las cubre explícitamente
  (`test_f006_fichas.py:544`). Es lo que hace que las 162 columnas de `compras` y
  las 99 de `retenciones` estén verificadas nombre a nombre — y, en efecto,
  **no hay ni una inventada ni una omitida** en los 24 objetos nuevos.
- **El aviso de frescura estaba en la cabecera del YAML, que no se publica**:
  cierto y bien resuelto. `R-FRESCURA-MANUAL` lleva ahora dentro que
  `build-compras` y `build-retenciones` no registran paso y que de esos dos
  esquemas hay que **advertir que la antigüedad se desconoce, en vez de
  callarlo**.
- **Los dos `1:1` de retenciones que eran `N:N`**: corregidos; repasadas las
  nueve relaciones del fichero, todos los lados `1` prometen unicidad real.

### Rigor

- **1242 tests + 2 skipped**, ejecutados por mí. Los 2 skips son legítimos y
  están cubiertos: las dos vistas de `retenciones` creadas con SQL dinámico
  dentro de un `DO $$` tienen su propio test a mano
  (`test_f006_r26_las_vistas_dinamicas_de_retenciones`).
- **Cobertura 98,9 % de 718 líneas cambiadas.**
- **Mutación verificada de forma independiente**: recalculé alcance (**2313
  líneas**, ocho ficheros) y mutantes (**160**), y coinciden con
  `progress/mutacion_F-006.md`; cero supervivientes.
- **T19 bien diferida**: `MANUAL (humano)` con los comandos exactos y las tres
  consultas de comprobación, listada en `current.md`. Esto cierra la reserva que
  dejé en la primera pasada sobre C4.
- **Nada prohibido**: ni un `GRANT`, `REVOKE`, firewall ni Azure en el diff; las
  únicas apariciones de esas palabras son comentarios que explican el orden del
  pipeline. `grants.py` y `apply_grants_step.py`, intactos. Y la ausencia de
  conexiones no se dio por buena leyendo: se comprobó **relanzando la suite
  entera con los sockets parcheados para lanzar excepción** — 1242 passed, ni un
  socket abierto.
- **Riesgo residual honesto**: nada del bloque E se ha ejecutado nunca contra un
  PostgreSQL. La adaptación de tipos de psycopg (el `JSONB` como texto, los
  `list[str]` a `TEXT[]`), el `CHECK (id = 1)` y la propia sintaxis del DDL están
  sin probar. Está declarado y planificado como T19, no oculto.
- **`azure-apps/datamart_seg_anual.md` no menciona todavía las tres tablas ni la
  vista.** Está planificado como T37 (bloque J), así que es un aplazamiento
  deliberado; pero la regla de `CLAUDE.md` dice «en el mismo trabajo, no
  después», y el contrato con otro equipo es justo el caso que esa regla cubre.
  Conviene decidirlo explícitamente en vez de que se arrastre.
- Deuda menor nueva: **+2 avisos de `ruff`** (un `I001` en
  `tests/test_f006_publicacion.py` y el bloque de imports de `main.py`), cuando
  las tandas anteriores dejaban `ruff` limpio en lo propio.

### Checkpoints (tercera pasada)

- **C1** `[x]` — `init.sh` exit 0, 1242 tests + 2 skipped, ejecutado por mí.
- **C2** `[x]` — una `in_progress`, rama correcta, `current.md` al día.
- **C3** `[x]` — dominio sin infraestructura; el paso nuevo en `application/steps/`,
  los constructores SQL en `infrastructure/postgres/`, el DDL en `sql/ddl/` con
  su numeración. Cabeceras de ruta presentes. Deuda menor: +2 avisos de `ruff`.
- **C3 bis** — **N/A**: no se toca `docs/referencia/`.
- **C4** `[ ]` — **el checkbox que falta**: R2 exige que la ficha diga qué es una
  fila y qué la identifica, y cinco fichas nuevas declaran claves o reglas que el
  SQL desmiente (defectos 1-5). Los tests pasan; lo que no se cumple es el
  requisito. Las verificaciones `MANUAL (humano)` sí están listadas con su
  comando exacto.
- **C4 bis** `[x]` — fase RED por tarea; cobertura 98,9 % de 718 líneas;
  mutación **verificada de forma independiente** (2313 líneas, 160 mutantes,
  coinciden), cero supervivientes; sección «Evidencias» presente.
- **C4 ter** — **N/A**: no existe `harness/rutas_sensibles.json`.
- **C5** — **N/A parcial**: 20 de 42 tareas, que son el alcance encargado.

### Observación de coherencia

Las cuatro tablas y vistas nuevas de `_meta` entran en `pendientes` sin ficha:
es decir, **el diccionario se publica a sí mismo sin describirse**. Es coherente
con el trinquete y T24 lo recoge, pero conviene que no se cierre el bloque F sin
ello, porque el MCP verá esos cuatro objetos en el catálogo antes que su ficha.

---
---

# SEGUNDA PASADA · 2026-08-20

> Commits revisados: `5783cbc`..`7d9845b` (trece). Mismo alcance: **T3–T14**,
> bloques A a D.

## Veredicto de la segunda pasada

**APROBADO**, con cuatro correcciones de arrastre que deben entrar **antes de
que el bloque E publique el diccionario en `_meta`** (§«Lo que arrastra»).

Los **diez defectos están corregidos**, verificados uno a uno y no de palabra:
cada arreglo lo comprobé contra el SQL o reproduciendo el experimento que antes
pasaba en verde. En cinco casos se arregló **el mecanismo y no el caso**, y las
ampliaciones que eso destapó son **ciertas, no ruido**: las 4 relaciones de
fan-out nuevas y los 2 objetos extra de `R-IMPORTE-MES` los verifiqué contra el
SQL uno a uno. Las fichas **siguen siendo veraces tras 277 líneas de edición**:
332 columnas, 22 granos y 22 claves de negocio revalidados, sin una sola
regresión.

Apruebo aun quedando cuatro imprecisiones (una de ellas introducida al
corregir) porque son de **otra categoría** que las que motivaron el rechazo.
Aquellas publicaban un valor sin sentido (`cardinalidad: 61`), inducían un
fan-out silencioso que multiplica importes y etiquetaban mal las cifras de
control: producían números falsos sin avisar. Las que quedan son prosa del
campo `porque` que, si un agente la sigue, produce **un error de SQL ruidoso**
(une por una columna que no existe) o una matización imperfecta. Bloquear otra
ronda completa por eso no protegería nada que no proteja ya el hecho de que el
diccionario **todavía no se publica**: hasta el bloque E no llega a ningún
agente, y ahí es donde deben entrar.

---

## Los diez defectos, uno a uno

Estado verificado por mí. «Experimento» significa que reproduje en un worktree
aislado la mutación que antes pasaba en verde.

| # | Defecto | Estado | Cómo lo comprobé |
|---|---|---|---|
| 1 | `cardinalidad: 1:1` publicada como `61` | **corregido, con mecanismo** | Vocabulario cerrado `CARDINALIDADES` (`domain/diccionario.py:83`) aplicado en `:625`. **Experimento E7**: quitar las comillas a un `1:1` → falla `test_f006_r5_ninguna_relacion_real_publica_una_cardinalidad...` con un mensaje que dice «escríbelo ENTRE COMILLAS». Las 8 relaciones afectadas, entrecomilladas; `yaml.safe_load` confirma que **las 42 cardinalidades son ahora `str`** |
| 2 | Seis cardinalidades `N:1` que eran `N:N` | **corregido, con mecanismo; 10 instancias** | La unicidad se **deriva** de la clave de negocio (`_es_unica_por`, `diccionario.py:675`; `_validar_cardinalidad`, `:699`). Las 4 nuevas salen de `mart.yaml`, que la primera pasada no auditó, y **las cuatro son ciertas** contra el SQL. Ninguna relación legítima quedó degradada: las `N:1` hacia dimensiones de clave simple siguen intactas. **Experimento E8**: degradar un `N:N` a `N:1` → detectado |
| 3 | `orden_concepto` «1 a 6» falso | **corregido, ampliado a 3 fichas + 1 relación** | Contrastado: `02_build_fact.sql:299-304` da 1/2/3/4 y `03_views.sql:56,87` añaden GASTOS=2 y BENEFICIO=6. La ficha declara ahora los valores reales `{1,2,2,3,4,6}`, dice que el 2 está duplicado y que no hay 5, y **manda ordenar por `v_pbi_dim_concepto`**, que sí va 1→6 |
| 4 | Órdenes de magnitud: «total» siendo saldo vivo | **corregido** | Las cifras cuadran **al dígito** con `LEEME_RETENCIONES_R1.md:21-22` («34,7 M€ vivos», «21,9 M€ vivos»), ahora con `criterio: saldo_vivo`/`total`, fuente comprobable y sentido (quién retiene a quién, contra `sql/retenciones/01_movimientos.sql:6-8`). La cifra de «~27.300 efectos», que **no estaba en ninguna fuente**, se sustituyó por los dos recuentos reales desglosados |
| 5 | `cliente_ide.nulo_significa` falso | **corregido, con mecanismo** | La ficha dice ahora que llega **0** y cómo filtrarlo. La afirmación fuerte («es el único `*_ide` sin `NULLIF`») es cierta: los otros seis lo llevan. **Experimento E10**: reintroducir el nulo imposible → detectado por dos tests |
| 6 | `R-FRESCURA-MANUAL` citaba `_meta.v_diccionario`, inexistente | **corregido, con mecanismo** | Ahora cita solo `_meta.v_frescura`, que sí existe (`sql/ddl/00_meta.sql:70`), y añade que la antigüedad de `compras`/`retenciones` **se desconoce**. Hay barrido con regex de los nueve esquemas sobre `regla`, `motivo` y `respuesta_correcta`, contrastado contra el inventario derivado del SQL. Queda una cita en `nota` de P15, en condicional y correcta |
| 7 | `R-CLAVE-SUSTITUTA` marcaba estable→inestable | **corregido; mecanismo a medias** | `aux.periodificacion_partida` fuera del ámbito, y las cuatro claves que sí son inestables (`fact_id`, `fact_cat_id`, `plan_id`, `cierre_id`) siguen dentro. El matiz: el test nuevo cubre los falsos positivos y no los falsos negativos, y por eso `mart.v_fact_periodificado.fact_id` —marcada `clave_sustituta`— no la alcanza la regla. Hueco preexistente, no regresión |
| 8 | `R-IMPORTE-MES` no cubría `cierre` | **corregido, ampliado a 4; cero ruido** | Los dos extra (`v_pbi_cierre_indirectos_detalle`, `v_pbi_cierre_generales_detalle`) **tienen la trampa de verdad**: CTE `agregado` con `SUM(importe_origen)` + `LAG` + `ejecutado_mes`. El detector es **simétrico** (busca todo objeto que documente a la vez una columna EUR `suma_solo_dentro_del_mes` y otra `ultimo_valor`) y lleva test de control anti-detector-vacío: devuelve 9 objetos y los 9 están en el ámbito |
| 9 | `design.md` señalado y no corregido | **corregido** | Nota de enmienda fechada (`design.md:40-48`), ejemplo §3.3 con los nombres reales, relación a `maestro.obras.obra_id`, §5.1 a 13 y 12 objetos, y «más de 80» → 98. **Experimentos D1 y D2**: reintroducir el literal `COSTE_REAL` o la columna `obra_codigo` en el ejemplo → detectado. (D3, falsear el recuento de la tabla §5.1, no está vigilado: menor) |
| 10 | Las defensas de la puerta | **corregido: 3 de mis 4 experimentos ahora se cazan; el 4º, declarado** | Ver el apartado siguiente |

## Los experimentos, reejecutados por mí

Worktree aislado (`git worktree --detach`), árbol real intacto. Línea base: 327
tests de F-006 en verde.

| Experimento | Antes | Ahora |
|---|---|---|
| **E1** · desdocumentar `v_pbi_dim_escenario`, devolverla a `pendientes` y **subir** el tope a 74 | pasaba (252 passed) | **detectado**: `test_f006_r27_el_trinquete_solo_baja_a_lo_largo_del_historial` |
| **E2** · ficha esquelética (`descripcion: x`, `grano: x`, `motivo_no_consumo: x`) que saca un objeto de `pendientes` | pasaba | **detectado**: 3 fallos (mínimos de contenido + proyección exacta + validación) |
| **E3** · colar `obra_label`, columna de otra vista del **mismo fichero SQL**, en `v_pbi_fact` | pasaba (254 passed) | **detectado**: `..._las_vistas_documentan_exactamente_su_proyeccion[mart.v_pbi_fact]` |
| **E4** · invertir el `significado` de `importe_mes` a «Importe ACUMULADO» | pasaba | **sigue pasando** — y está **declarado sin adornos** en el informe: «que el TEXTO de una ficha sea cierto […] lo garantiza la revisión humana y la batería T39» |
| **E9** (nuevo) · el mismo retroceso de E1 pero **commiteado**, para que el árbol coincida con HEAD | — | **detectado**: el anclaje recorre el historial del fichero por pares, no solo el árbol |
| **E5** (nuevo) · grano falso en `fact_seguimiento_mensual` («una fila por obra y mes») | — | **pasa en verde** |
| **E6** (nuevo) · `clave_negocio: [obra_id]` en esa misma tabla | — | **pasa en verde** |
| **E11** (nuevo) · clave de negocio falsa **y** degradar a `N:1` el fan-out que esa clave sostiene | — | **pasa en verde** |

Sobre E4: no es un incumplimiento. Ninguna de las cuatro defensas que pedí
podía cazar un texto invertido, y el implementer lo dice en vez de taparlo,
que es exactamente la conducta que la primera pasada echó en falta.

Sobre E5, E6 y E11 sí hay algo que corregir, aunque no en el código: el informe
afirma que ahora están cubiertos «nombres de columna, **granos declarados**,
**claves de negocio**, cardinalidades…». Lo que de verdad está cubierto es que
las columnas de la clave **existan** y que la cardinalidad no prometa una
unicidad que la clave declarada no sostiene. Que el grano o la clave sean
**ciertos** no lo comprueba nada, y E11 enseña la consecuencia: como la
detección de fan-out se **deriva** de la clave de negocio, quien declare una
clave falsa desactiva de paso la defensa que esa clave sostiene. Es la misma
clase de sobreventa —una línea que promete más de lo que el test hace— que
motivó parte del rechazo anterior, y por eso conviene arreglar la frase.

## Lo que arrastra (obligatorio antes de que el bloque E publique)

1. **`cierre.yaml:933` manda un JOIN por una columna que no existe.** El
   `porque` de la relación `v_pbi_planif_vs_real → mart.fact_seguimiento_categoria`
   dice «El JOIN va por `(obra_id, anio_mes, categoria)`», pero la vista **no
   proyecta `categoria`**: sus 13 columnas llevan `concepto_cuadro`
   (`sql/cierre/06_views_planif_vs_real.sql:113-123`). Y no es solo el nombre:
   `PRODUCCIÓN`, `TOTAL COSTES` y `BENEFICIO` son agregados que no corresponden
   a ninguna categoría (`06:52-62`, `:84-106`). **Lo introdujo la corrección del
   defecto 2**, y la corrección hermana de `cierre.yaml:339-341` sí eligió una
   columna que existe en los dos lados (`concepto`), lo que confirma que es un
   despiste.
2. **`mart.yaml:881`**: la relación `v_pbi_cp_tipologia → v_master_vigente_anual`
   manda unir por `(obra_id, anio, ambito_id)`, y `ambito_id` no es columna de
   la vista origen (sus 7 columnas están verificadas); en el SQL es un filtro
   constante `va.ambito_id = 8` (`06_views_cp_tipologia.sql:216`).
3. **`cierre.yaml:298-302`**: al explicar la excepción, `final_pct` se
   autoincluye en ella. En la fila VENTA usa `aprobado_venta`
   (`03_views.sql:190-196`), no `venta_final` como los otros cuatro. Aun así es
   mejor que el texto anterior.
4. **Seis residuos de «mes anterior»** (`cierre.yaml:122,126,269,272,282,307`)
   en columnas vecinas de las siete que sí se corrigieron a «FILA anterior». Es
   la misma trampa —el `LAG` salta los meses sin cierre— en la misma ficha.
5. **La frase del informe** sobre granos y claves de negocio: rebajarla a lo que
   los tests hacen de verdad (ver arriba). Y, si se quiere cerrar E6/E11 de
   verdad, contrastar la clave de negocio contra la PK o el índice único del
   DDL en las tablas, que es donde sí es derivable.

## Rigor y checkpoints (segunda pasada)

- **C1** `[x]` — `bash harness/init.sh` exit 0, **1125 tests**, ejecutado por mí.
- **C2** `[x]` — una sola feature `in_progress`, rama correcta, `current.md` al día.
- **C3** `[x]` — dominio sin infraestructura, cabeceras de ruta, `ruff` limpio.
- **C3 bis** — **N/A**: el diff no toca `docs/referencia/`.
- **C4** `[x]` — la reserva de la primera pasada (R27 se cumplía «al pie de la
  letra» pero no conseguía lo que prometía) **queda resuelta**: el anclaje al
  historial de git es la comprobación que faltaba, y E9 confirma que ni
  commiteando se esquiva.
- **C4 bis** `[x]` — fase RED con trazas por defecto corregido; cobertura
  **98,7 % de 544 líneas**; **mutación verificada de forma independiente**:
  recalculé alcance (**1693 líneas**) y mutantes (**128** = 81 + 24 + 0 + 23),
  y coinciden con `progress/mutacion_F-006.md`; cero supervivientes; sección
  «Evidencias» presente.
- **C4 ter** — **N/A**: no existe `harness/rutas_sensibles.json`.
- **C5** — **N/A parcial**, como en la primera pasada: 14 de 42 tareas, que son
  el alcance encargado. Se exigirá entero al pasar F-006 a `done`.

## Nada prohibido, otra vez

`git diff 5e901f8..HEAD --name-status`: solo los tres YAML del diccionario, el
dominio, los tests, `design.md` y ficheros de `progress/`. **Cero cambios** en
`main.py`, `config/settings.py`, `grants.py`, `postgres_client.py`, `infra/**` y
cualquier `.sql`. Ningún GRANT, REVOKE, firewall ni Azure; ninguna conexión a la
base. Árbol limpio; mis experimentos se hicieron en worktrees aislados que ya
he eliminado.

---
---

# PRIMERA PASADA · 2026-08-20 (RECHAZADO)

> Commits revisados: `ba8ff93`..`5e901f8`. Se conserva íntegra: es lo que se
> pidió corregir y el patrón de contraste de la segunda pasada.

## Veredicto

**RECHAZADO (CHANGES_REQUESTED).**

No por el código —que es sólido— sino por **el contenido publicado**, que es
lo que esta feature entrega. En 25 fichas y 332 columnas no hay **ninguna
columna inventada, ninguna columna omitida, ningún grano falso y ninguna clave
de negocio falsa**: eso está verificado una a una contra el SQL y es la parte
difícil, que está bien hecha. Pero quedan **diez defectos** que sí hay que
corregir, y **cinco de ellos son afirmaciones falsas o engañosas en el texto
que un agente leerá para decidir qué SQL escribe**: una publica un valor sin
sentido (`cardinalidad: 61`) en ocho relaciones de los dos ficheros, otra
invita a un JOIN con fan-out en seis, y otra convierte en «total de la empresa»
unas cifras que son de saldo vivo. Con rigor `critico` y siendo la mentira con aplomo el riesgo
que esta feature existe para eliminar, no se aprueba: son correcciones baratas
y localizadas, y consagrarlas ahora las propaga a las 73 fichas que faltan.

Y hay un segundo motivo, de fondo: **la puerta que debería impedir que esto se
repita en las 73 fichas restantes no lo impide**. Demostrado con experimentos
(ver §«La puerta de cobertura»): el trinquete **puede subir**, una ficha
esquelética de `x` saca objetos de `pendientes`, y el grano, la clave de
negocio y el significado de una columna se pueden invertir sin que ningún test
se entere. El trabajo entregado **no** explota ninguno de esos huecos —lo
comprobé ficha a ficha—, pero el bloque A se entregó como «el andamiaje que
garantiza que el diccionario no se quede atrás» y hoy garantiza bastante menos
de lo que dice. Corregirlo ahora es barato; después de escribir 73 fichas, no.

## Nivel de rigor

`"rigor": "critico"`, declarado explícitamente en `harness/features.json`
(commit `cab50ab`; antes funcionaba por omisión). Exige, según
`CHECKPOINTS.md`: fase RED con traza, cobertura de las líneas cambiadas,
campaña de mutación con **cero supervivientes** sin justificación aceptada por
el humano, y verificaciones `MANUAL (humano)` con su comando y su resultado
real. **Las cuatro puertas se cumplen** (ver C4 bis).

---

## Lo que hay que corregir

Numerado y ordenado por gravedad. Todo con fichero y línea de los dos lados.

### 1. `cardinalidad: 1:1` se publica como el entero `61` (8 relaciones)

YAML interpreta `1:1` sin comillas como **sexagesimal**: 1×60+1 = 61.
`cargador_yaml.py:431` lo pasa por `_texto()` (`:106-108`, que es `str(valor)`),
así que la ficha que consumirá el MCP dirá literalmente `cardinalidad: "61"`.

Verificado ejecutando el propio parser sobre los dos ficheros:

- `mart.yaml`: `v_pbi_fact:408`, `v_pbi_fact_categoria:474`,
  `v_pbi_dim_obra:508`, `v_pbi_dim_partida:565`,
  `v_pbi_dim_partida_niveles:622`, `v_fact_periodificado:1008`.
- `cierre.yaml`: `v_pbi_cierre_cabecera:776` y `:782`.

`1:N` y `N:1` se salvan solo porque llevan letra.

**Corregir**: entrecomillar (`cardinalidad: "1:1"`) **y** cerrar el hueco que
lo permitió: `Relacion.cardinalidad` (`domain/diccionario.py:142`) se declara
`str` pero **no se valida contra ningún vocabulario**. Añadir vocabulario
cerrado `1:1 | 1:N | N:1 | N:N` con su test, como ya se hizo con `agregacion`
(R7). Sin eso el mismo fallo entra otra vez en las 73 fichas que faltan.

### 2. Seis cardinalidades declaradas `N:1` / `1:N` que en realidad son `N:N`

El `de` es `obra_id` a secas y el destino tiene muchas filas por obra:

| Ficha | Relación | Dice | Es |
|---|---|---|---|
| `cierre.yaml:154-156` | `fact_cierre_mensual.obra_id → mart.fact_seguimiento_mensual.obra_id` | 1:N | N:N |
| `cierre.yaml:302-304` | `v_pbi_cierre_resumen.obra_id → cierre.fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:556-558` | `indirectos_detalle.obra_id → v_pbi_dim_subcategoria_ci.obra_id` | N:1 | N:N |
| `cierre.yaml:560-562` | `indirectos_detalle.obra_id → fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:630-632` | `generales_detalle.obra_id → fact_cierre_mensual.obra_id` | N:1 | N:N |
| `cierre.yaml:855-857` | `planif_vs_real.obra_id → mart.fact_seguimiento_categoria.obra_id` | N:1 | N:N |

Un agente que se fíe del `N:1` escribe un JOIN con **fan-out silencioso y
duplica importes**. Es exactamente el error que `R-RETENCION-NO-JOIN-LINEAS`
existe para castigar, cometido dentro del propio diccionario.

**Corregir**: poner `N:N` donde lo sea, o —mejor— declarar la relación por su
clave real (`(obra_id, anio_mes)`, `(obra_id, grupo_cod, subcategoria_cod)`),
que es la información que evita el fan-out.

### 3. `v_pbi_cierre_resumen.orden_concepto`: el rango declarado es falso

- Ficha (`cierre.yaml:211-213`): «Orden de presentacion del concepto **(1 a 6)**».
- Real: los cuatro conceptos base heredan `1,2,3,4` de
  `sql/cierre/02_build_fact.sql:291-297`; `GASTOS` recibe **2**
  (`03_views.sql:56`) y `BENEFICIO` **6** (`03_views.sql:85`). Los valores son
  `{1, 2, 2, 3, 4, 6}`: **el 2 está duplicado y el 5 no existe**.
- Además **no coincide** con `v_pbi_dim_concepto.orden` (`03_views.sql:25-32`),
  pese a que la relación de `cierre.yaml:312-315` dice que el dim aporta «el
  orden de presentacion».

Un `ORDER BY orden_concepto` deja GASTOS e INDIRECTOS empatados y en orden
indefinido. La ficha debe decir qué valores toma de verdad y mandar ordenar
por el dim.

### 4. Los órdenes de magnitud (R10) mezclan dos criterios y llaman «total» a lo vivo

`00_global.yaml:260-276` publica «Retenido a proveedores, **total de la
empresa**: 34.700.000» y «Retenido de clientes, **total de la empresa**:
21.900.000». La fuente primaria del repositorio, `LEEME_RETENCIONES_R1.md:19-22`,
dice **«34,7 M€ vivos»** y **«21,9 M€ vivos»** (saldo vivo, `fecrea = 0`).
La tercera cifra, ~27.300 efectos, sí es el total (25.124 + 2.219 = 27.343).

Es decir: el bloque cuya única función es **detectar una cifra absurda antes de
darla por buena** mezcla saldo vivo con totales sin avisar. Un agente que
compare un `SUM(importe)` de todos los movimientos contra 34,7 M€ concluirá que
su número está mal cuando está bien, o al revés.

**Corregir**: añadir «vivos» a las dos primeras y citar como `fuente` el
documento del repositorio que trae la medición (`LEEME_RETENCIONES_R1.md:19-22`),
no la nota de segunda mano del prototipo.

### 5. `v_pbi_cierre_cabecera.cliente_ide`: el `nulo_significa` es falso

Ficha (`cierre.yaml:662-665`): «La obra no tiene cliente asignado».
`sql/cierre/05_views_cabecera.sql:71` proyecta `obr.entide AS cliente_ide`
**sin `NULLIF(..., 0)`** — es el único `*_ide` de la vista que no lo lleva
(compárese con `tecnico_ide:73`, `centro_coste_ide:75`, `tipo_obra_ide:77`,
`clase_obra_ide:79`, `director_obra_ide:162`). Las obras sin cliente traen
**0**, y `WHERE cliente_ide IS NULL` no devuelve nada.

### 6. `R-FRESCURA-MANUAL` manda consultar una vista que todavía no existe

`00_global.yaml:43-44`: «se obtiene con `SELECT * FROM _meta.v_frescura` (o de
una sola vez, junto con la semantica, en `_meta.v_diccionario`)».
`_meta.v_diccionario` **no existe en el repositorio** (cero apariciones fuera
de `specs/`); la crea T15, en el bloque E. El propio fichero se contradice en
`00_global.yaml:655`: «Cuando exista `_meta.v_diccionario` (bloque E)».

No es catastrófico porque el diccionario aún no se publica —la publicación es
también bloque E—, pero deja una dependencia dura que hay que fijar: **o se
condiciona la frase, o el bloque E no puede publicar sin haber creado antes la
vista**. Publicar en ese orden sería servir una instrucción que revienta.

### 7. `R-CLAVE-SUSTITUTA` marca como inestable una clave que sí es estable

La regla (`00_global.yaml:156-165`) mete `aux.periodificacion_partida` en el
ámbito y declara `regla_id` entre las claves que «se reasignan enteras en cada
build», con el motivo «las tablas se recrean con DROP + CREATE».
`sql/mart/04_view_periodificado.sql:14` crea esa tabla con **`CREATE TABLE IF
NOT EXISTS`** y ningún build la reconstruye: `regla_id` es estable. El error es
conservador (no produce números falsos), pero es un dato falso dentro de una
regla dura, y las reglas duras se respetan por ser exactas.

### 8. `R-IMPORTE-MES` no cubre `cierre`, que es donde ocurrió el bug que la motiva

El ámbito (`00_global.yaml:55-61`) lista objetos de `mart` y `stg`, pero el
`motivo` cita el bug de la Tanda 1.4 **del cierre**
(`sql/cierre/02_build_fact.sql:7-10`, el ≈9x). `cierre.fact_cierre_mensual`
tiene la misma trampa con otros nombres: `ejecutado_origen` es acumulado y
`ejecutado_mes` el parcial (`sql/cierre/01_ddl_fact.sql:23-26`). Está mitigado
en las fichas (`agregacion: ultimo_valor`), pero un agente que lea la regla y
no la ficha repite el error original.

**Corregir**: añadir `cierre.fact_cierre_mensual` y `cierre.v_pbi_cierre_resumen`
al ámbito, nombrando esas dos columnas.

### 9. `design.md` quedó señalado y no corregido

El informe del implementer dice, con razón, que el ejemplo de `design.md` §3.3
usa columnas y literales que no existen, y que el recuento de §5.1 está mal.
Pero **no lo arregló**, y el documento sigue como estaba:

- `design.md:186,192,208,219-220`: `obra_codigo`, `partida_codigo`, `mes`,
  `valores: [COSTE_REAL, COSTE_PLAN, VENTA_REAL, VENTA_PLAN]` y la relación
  `a: maestro.obras.obra_codigo`. **Ninguno existe**: el SQL dice `codigo_obra`,
  `codigo_partida`, `anio_mes` y `Coste Real / Coste Planificado / Venta Real /
  Venta Planificada` (`sql/mart/01_ddl.sql:47-72`,
  `sql/mart/05_views_powerbi.sql:73-79`), y `maestro.obras` expone `obra_id`
  (`sql/maestro/01_obras.sql:19`).
- `design.md:393-394`: «`mart.yaml` ~11 objetos: 2 tablas + **9 vistas**» y
  «`cierre.yaml` ~10 objetos: 1 tabla, **6 vistas**, 3 funciones».
  El inventario real es **13 objetos en `mart` (2 + 11 vistas)** y **12 en
  `cierre` (1 + 8 vistas + 3 funciones)**, verificado por mí objeto a objeto.
  `design.md:823` sigue diciendo «más de 80 objetos» cuando son 98.

`design.md` §3 es **el contrato del YAML** y su ejemplo es lo que copiará quien
escriba `compras.yaml`, `retenciones.yaml` y las 73 fichas restantes. Que las
fichas de este bloque estén bien no evita que el error se propague desde el
documento. Si el arnés exige que la enmienda la firme el spec-author, que la
firme; pero no puede quedarse sin hacer.

### 10. Las defensas de la puerta, antes de escribir 73 fichas más

Detalle y evidencia en §«La puerta de cobertura». Lo mínimo:

- **Mínimos de contenido** en `descripcion`, `grano`, `significado` y
  `motivo_no_consumo`, como ya se exige en el bloque global
  (`test_f006_formato.py:964`, `test_f006_reglas.py:301-302,450-451`). Cierra
  la ficha esquelética y la puerta trasera de R3 de un golpe.
- **Acotar la búsqueda de columnas al `SELECT` de la vista** y quitar los
  comentarios antes de buscar.
- **Anclar `PENDIENTES_MAX`** a algo que no sea la misma línea que se edita, o
  añadir un test que prohíba que un objeto vuelva de documentado a `pendientes`.
- **Retirar de los docstrings** la afirmación de que `check-diccionario` cubre
  hoy lo que la puerta offline no ve, o implementarlo. Hoy es una promesa.

Esto es prevención, no reparación: **ninguna de las 25 fichas entregadas
explota estos huecos**. Si el líder prefiere tratarlo como tarea aparte del
bloque A en vez de como condición de esta entrega, es defendible; lo que no lo
es es dejarlo sin decidir.

---

## Correcciones del implementer que SÍ he verificado y son correctas

Conviene decirlo porque son enmiendas a la spec y, si estuvieran mal, el error
quedaría consagrado en el contrato:

| Corrección | Veredicto | Evidencia |
|---|---|---|
| El inventario real son **98 objetos**, no «más de 80» | **correcta** | reproducido por mí con `objetos_de_sql` + `objetos_de_raw`: **98** = raw 31, compras 14, mart 13, cierre 12, retenciones 10, stg 10, maestro 4, `_meta` 3, aux 1. Coincide con el reparto declarado |
| `mart` tiene **11 vistas**, no 9 | **correcta** | las 11 en `sql/mart/04`, `05`, `05b`, `06` |
| `cierre` tiene **8 vistas**, no 6 | **correcta** | `03_views.sql:24,37`, `04_views_detalle.sql:50,101,117,503`, `05_views_cabecera.sql:21`, `06_views_planif_vs_real.sql:31` |
| Los cuatro literales de escenario son `Coste Real / Coste Planificado / Venta Real / Venta Planificada` | **correcta** | `sql/mart/05_views_powerbi.sql:73-79` |
| `clave_negocio` con `obra_id`/`partida_id` en vez de los códigos | **correcta** | `codigo_partida` es anulable y `obra_id` = `con.ide`, estable |
| `presupuesto_aprobado_venta` es copia literal del inicial | **correcta** | `sql/cierre/05_views_cabecera.sql:167` |
| `final_pct` de VENTA va contra el aprobado | **correcta** | `sql/cierre/03_views.sql:193-202` |
| `ejecutado_mes_periodif` resta el INCURRIDO del mes anterior | **correcta** | `sql/cierre/04_views_detalle.sql:388-396,449-452` |
| `ratio_lineal` no tiene tope en el 100 % | **correcta** | `04_views_detalle.sql:307-320`, solo `GREATEST`, ningún `LEAST` (el comentario del SQL en `:295` es el que miente) |
| `v_pbi_dim_subcategoria_ci` resuelve por obra | **correcta** | `04_views_detalle.sql:52-61,87-90` |
| `build-compras` y `build-retenciones` no registran paso en `_meta.etl_runs` | **correcta** | `main.py:3189-3191` y `:3491-3493` ejecutan SQL en línea sin step; `build_cierre` y `build_maestros` sí (`main.py:2246,2261`) |
| `mart.v_fact_periodificado` no periodifica nada hoy | **correcta** | `aux.periodificacion_partida` se crea vacía; `consumo_recomendado: false` con motivo escrito |

---

## Veracidad de las fichas: lo que se comprobó y cómo

No es un muestreo simbólico: se contrastaron **las 25 fichas y las 332 columnas
una a una** contra el SQL que crea cada objeto.

- **`mart.yaml`** (13 objetos, 185 columnas), contra `sql/mart/01_ddl.sql`,
  `02_build_fact.sql`, `03_agg_categoria.sql`, `04_view_periodificado.sql`,
  `05_views_powerbi.sql`, `05b_view_dim_partida_niveles.sql` y
  `06_views_cp_tipologia.sql`. Las 34 columnas de `fact_seguimiento_mensual`,
  las 19 de `fact_seguimiento_categoria`, las 17 de `v_pbi_fact`, las 35 de
  `v_fact_periodificado` y las 18 de `v_pbi_dim_partida_niveles` coinciden
  **exactamente**, ni una de más ni una de menos. Los granos son ciertos,
  incluida la parte delicada: la elección de versión vigente **por mes**
  (`02_build_fact.sql:152-170`) y la ventana común plan/real de
  `v_pbi_cp_tipologia` (`06_views_cp_tipologia.sql`, CTE `corte`), que la
  ficha describe con exactitud, mes de corte incluido.
- **`cierre.yaml`** (12 objetos, 147 columnas), contra los siete ficheros de
  `sql/cierre/`. Mismo resultado: 147/147 columnas existen con el nombre exacto
  y no sobra ninguna; los 9 granos y las 9 claves de negocio son ciertos.
- **Relaciones**: los destinos que hoy el validador **no puede** comprobar
  (porque están en `pendientes`) los comprobé a mano: `stg.obras.obra_id`
  (`sql/stg/03_obras.sql:83`), `stg.partidas.partida_id`, `maestro.obras.obra_id`
  (`sql/maestro/01_obras.sql:19`), `compras.v_pbi_partida_coste.partida_id`
  (`sql/compras/03_views.sql:181+`), `cierre.fact_cierre_mensual.obra_id`,
  `stg.plan_mensual.obra_id` y `aux.periodificacion_partida.regla_id`. **Todos
  existen.** El defecto de las relaciones es la cardinalidad (punto 2), no el
  destino.

### Las doce reglas duras

Las doce están, con los seis campos, todas `bloqueante`, y **ninguna es falsa**.
Verificadas contra el SQL las siete que pedía el encargo:

| Regla | Veredicto | Evidencia |
|---|---|---|
| `R-IMPORTE-MES` | verdadera (ámbito corto, punto 8) | `stg/08_plan_mensual.sql:352-355`: `importe_mes = importe_origen - LAG(importe_origen)`. El ≈9x está literal en `cierre/02_build_fact.sql:7-10` |
| `R-VERSION-MASTER` | verdadera y accionable | `stg/01_ddl.sql:202-224` (conviven todas las versiones); la vigente se resuelve solo aguas abajo, `mart/02_build_fact.sql:152-170`, con el filtro `tipo_master IN ('Planif Inicial','ABC','Cuatrimestral')` palabra por palabra |
| `R-ABONO-NEGATIVO` | verdadera | `compras/03_views.sql:10` y las vistas agregan FACTURA y ABONO juntos (`:118`, `:192`) |
| `R-RETENCION-NO-JOIN-LINEAS` | verdadera | `retenciones/01_movimientos.sql:3,48,68`: un registro por efecto. El incidente de 38,9 M€ está declarado en `progress/explore_F-006_mcp_bbdd.md:80-83` |
| `R-LINEA-ID-NO-UNICA` | verdadera | `compras/02_fact_linea.sql:12-13`: `CREATE TABLE ... AS` de tres orígenes (`ctrpro`, `dcapro`, `dcfpro`), sin PK; `tipo_doc` y `linea_id` existen |
| `R-UNIVERSO-OBRA` | verdadera | `stg/03_obras.sql:105-118` (lista de administrativas, `cod !~ '[0-9]{5,}'`, dedup por `conext.cod='15'`) vs `maestro/01_obras.sql:17-30`, vista **sin un solo WHERE** |
| `R-CLAVE-SUSTITUTA` | verdadera salvo `aux` (punto 7) | `fact_id`, `fact_cat_id`, `cierre_id`, `plan_id` son BIGSERIAL y sus tablas se recrean o truncan en cada build |

Las otras cinco (`R-FRESCURA-MANUAL`, `R-OBRA-ACTIVA`, `R-FAS-AMBIGUO`,
`R-COMPRAS-SIN-IVA`, `R-COMPRAS-TIPO-DOC`) también son verdaderas. Dos matices
menores: el `motivo` de `R-COMPRAS-TIPO-DOC` describe mal el mecanismo (la
función se llama con literales `14`/`15` y `compras.fn_serie(con.cod)`, no con
`con.tip`, y `'CONTRATO'` es un literal de `02_fact_linea.sql:17`), y
`R-COMPRAS-SIN-IVA` puede afinar que `totdoc` es «total sin retención», o sea
que la diferencia no es solo el impuesto.

**Observación de cobertura**: `derivar_avisos` solo adjunta códigos a fichas que
existen. Hoy **siete de las doce reglas apuntan únicamente a objetos que siguen
en `pendientes`**, así que no se adjuntan a ninguna ficha. Es coherente con el
trinquete, pero hasta que `pendientes` esté vacía esas reglas solo llegan al
agente si se le sirve el bloque global entero. Conviene que el bloque E lo
tenga en cuenta al diseñar qué devuelve `contexto_bbdd`.

---

## La puerta de cobertura: qué garantiza y qué no

Se pidió expresamente comprobar tres cosas. Las respondo con experimentos
reales, hechos en un **worktree aislado** (el árbol de trabajo nunca se tocó y
`git status` sigue limpio).

**1. ¿El trinquete solo puede bajar?** **No. El trinquete no es un trinquete.**
`PENDIENTES_MAX` (`tests/test_f006_cobertura.py:417`) es una constante escrita
en el propio fichero de test, y nada la ancla a su valor anterior. Los dos
tests que la vigilan comparan la constante **con la lista del YAML**, no con el
pasado: `..._solo_baja` (`:468`) exige `len(pendientes) <= PENDIENTES_MAX` y
`..._no_esta_holgado` (`:483`) exige la igualdad. Subir las dos cosas a la vez
pasa en verde.

Demostrado: borré la ficha de `mart.v_pbi_dim_escenario`, la devolví a
`pendientes` y subí el tope a 74 → **252 passed, todo verde**. Es decir,
**desdocumentar un objeto ya documentado y retroceder el contador es legal**,
que es exactamente lo que la regla de hierro 4 de `tasks.md` dice que no puede
pasar. Lo único realmente protegido es la holgura (que la constante no quede
por encima de la lista) y la coherencia de `pendientes` (ni fantasmas ni
objetos ya documentados), más
`test_f006_r24_puerta_el_inventario_no_esta_vacio` (`:432`), que sí cubre bien
el fallo silencioso clásico —si cambia la ruta del SQL y el `rglob` no
encuentra nada, la puerta pasaría sin comprobar nada—. La frase del docstring
«**Solo baja.** […] ninguna tarea lo sube» es hoy un comentario, no un test.

**2. ¿Se puede pasar declarando un objeto como documentado sin estarlo?**
**Sí, y por varias vías. Esto hay que cerrarlo antes de los bloques F y G.**
Los experimentos:

- **Omitir columnas de una vista pasa desapercibido.** Borré `can_mes` de la
  ficha de `mart.v_pbi_fact` —una columna que la vista sí tiene
  (`sql/mart/05_views_powerbi.sql:157`)— y la suite entera quedó **en verde:
  `98 passed`**. Para las **tablas** la comprobación de
  `test_f006_fichas.py:153` sí es exacta en los dos sentidos; para las
  **vistas** solo se exige que cada columna documentada *aparezca* en el
  fichero SQL, así que una ficha con la mitad de sus columnas pasa.
- **Una ficha esquelética baja el trinquete.** Escribí un `maestro.yaml` con
  `descripcion: x`, `grano: x`, `motivo_no_consumo: x`,
  `consumo_recomendado: false` y una sola columna `obra_id: x`, saqué
  `maestro.obras` de `pendientes` y bajé `PENDIENTES_MAX` a 72: **todos los
  tests de F-006 en verde**. El validador exige que los campos *existan*, no
  que digan algo. Escalado en la auditoría paralela: generando las **31 fichas
  de `raw` rellenas con `x`** el trinquete cae de 73 a 42 en verde. Por ese
  camino F-006 «cierra» con `pendientes` a 0 sin una línea de conocimiento.
- **El contraste de vistas admite cualquier palabra del fichero.** El test
  genérico (`test_f006_fichas.py:254-270`) busca `\b<nombre>\b` en el **texto
  crudo del fichero entero, comentarios incluidos**. Documenté `obra_label`
  —columna de `mart.v_pbi_dim_obra`— dentro de la ficha de `mart.v_pbi_fact`,
  ambas en `05_views_powerbi.sql` → **254 passed**. La auditoría paralela
  confirma que también pasan palabras que solo aparecen en un comentario
  (`segmentadores`, `estrella`) y hasta el nombre de la tabla origen como si
  fuera una columna. Sí funciona el corte **entre** ficheros distintos.
- **El texto no se contrasta con nada, tampoco en las tablas.** Grano, clave de
  negocio, descripción, `tipo`, `capa` y el `significado` de cada columna no
  los cruza ningún test con el SQL. Comprobado en la auditoría paralela con
  nueve mutaciones, todas en verde; las tres que más importan: grano falso en
  `fact_seguimiento_mensual` («una fila por obra y mes», borrando partida y
  escenario), `clave_negocio: [obra_id]` en esa misma tabla, y el
  `significado` de `importe_mes` **invertido** a «Importe ACUMULADO desde el
  inicio de la obra». Esa última es literalmente la trampa nº 1 del datamart
  (`R-IMPORTE-MES`) escrita al revés, y la suite no se entera:
  `test_f006_r7_mart_importe_origen_no_se_declara_sumable` (`:180`) solo mira
  el campo `agregacion`, no el texto.

Es un hueco de la puerta, no del trabajo entregado: **verifiqué que ninguna de
las 25 fichas de este bloque lo explota** —las 332 columnas están completas, los
granos y las claves son ciertos y los significados también—. Pero quedan 73
fichas por escribir y el mecanismo que debería impedirlo no lo impide. Cuatro
defensas baratas, por orden de rentabilidad: **(a)** exigir mínimos de
contenido como ya se hace en el bloque global (`descripcion >= 40`,
`grano >= 20`, `significado >= 15`, `motivo_no_consumo >= 30`), que mata de una
vez la ficha esquelética y el `motivo_no_consumo: x`; **(b)** recortar el texto
de la vista concreta —entre su `CREATE VIEW` y el siguiente— y quitar
comentarios antes de buscar, que cierra lo de `obra_label`; **(c)** para las
vistas de `consumo_recomendado: true`, comparar el número de columnas
documentadas con el de alias del `SELECT` final; **(d)** anclar
`PENDIENTES_MAX` a algo que no se pueda subir editando la misma línea.

**3. ¿El umbral acordado es el que se aplicará en el bloque H?** El umbral
implementado en `evaluar_cobertura` (`domain/inventario.py:171-219`) es el de
R25/R26: **100 % de objetos con ficha** (bloqueante) y **100 % de columnas con
`significado` dentro de `consumo_recomendado: true`** (bloqueante), con aviso
no bloqueante fuera. Además bloquea dos cosas que la spec no pedía y que están
bien traídas: fichas huérfanas (describen humo) y pendientes fantasma (inflan
el trinquete). La salvedad es la del punto 2: ese 100 % se mide **sobre las
columnas declaradas**, no sobre las que el objeto tiene de verdad. La
comprobación contra el catálogo real es `check-diccionario` (R28), que llega en
el bloque E y sigue siendo imprescindible: el propio docstring de la puerta
declara que es heurística (R29), como pedía la spec.

Con un matiz que conviene fijar: **`check-diccionario` se cita tres veces como
la defensa que cubre lo que la puerta offline no ve** (`test_f006_fichas.py:23`,
`test_f006_cobertura.py:17`, `domain/inventario.py:13,94`) **y todavía no
existe** —no hay tal comando en `main.py`; es T27, bloque E—. Está bien que no
exista, es alcance futuro; lo que no está bien es citarlo en presente como si
protegiera algo hoy. Y hay un test que roza la circularidad:
`test_f006_r29_dominio_el_docstring_declara_la_heuristica`
(`test_f006_cobertura.py:163-169`) comprueba que la cadena `"check-diccionario"`
**esté escrita en el docstring**, es decir, verifica la promesa, no el comando.

## Checkpoints

| | Estado | Nota |
|---|---|---|
| **C1** · arnés en verde | `[x]` | `bash harness/init.sh` exit 0, 1052 tests, ejecutado por mí |
| **C1** · ficheros del arnés | `[x]` | los siete presentes |
| **C2** · una sola `in_progress` | `[x]` | solo F-006 |
| **C2** · rama correcta | `[x]` | `feature/F-006-mcp-azure` |
| **C2** · `current.md` solo la sesión activa | `[x]` | 46 líneas, sin restos |
| **C2** · `history.md` de las `done` | `[x]` | F-006 no es `done` |
| **C3** · arquitectura hexagonal | `[x]` | `domain/diccionario.py` y `domain/inventario.py` importan solo stdlib y dominio; el cargador YAML vive en `infrastructure/` |
| **C3** · primera línea con ruta | `[x]` | los 9 ficheros nuevos |
| **C3** · sin prints, TODOs ni secretos | `[x]` | `ruff check` limpio en todo lo nuevo |
| **C3** · semántica Sigrid | `[x]` | `amb`/`fas`, `importe_origen` vs `importe_mes` y las versiones master duplicadas están tratadas y son el núcleo de las reglas |
| **C3 bis** · documentos de fuera | **N/A** | no se añade ni se modifica nada en `docs/referencia/`. Justificado: el diff no toca esa carpeta |
| **C4** · requisito → test | `[x]` con reserva | R1–R14, R16, R22, R24–R27, R29, R39, R41 con tests `test_f006_rN_*`; R40 lo exige el validador (`diccionario.py:455-461`) aunque su test no lleve el número; el resto son de bloques E–K. **La reserva**: R27 se cumple *al pie de la letra* —la puerta falla si `pendientes` crece por encima del valor declarado— pero ese valor se declara en la línea de al lado y se puede subir, así que el requisito, tal y como está redactado, **no consigue lo que la regla de hierro 4 de `tasks.md` promete**. El hueco es del requisito tanto como del test |
| **C4** · tests sin red ni BBDD | `[x]` | ni un import de `psycopg`/`requests`; hay un test que **prohíbe** al dominio importar `yaml`, `psycopg` o `pathlib` |
| **C4** · verificaciones MANUAL listadas | `[~]` | están en `progress/impl_F-006.md` (T19, T27, T32–34, T37–T39), **no en `current.md`** como pide el checkpoint. Ninguna correspondía a los bloques A–D. Defecto menor, no bloqueante |
| **C4 bis** · rigor declarado | `[x]` | `"rigor": "critico"` explícito |
| **C4 bis** · fase RED | `[x]` | trazas reales pegadas para T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13 y T14. Además el implementer declara y explica un test RED que **reescribió** al implementar, en vez de esconderlo |
| **C4 bis** · cobertura | `[x]` | `PUERTA COBERTURA: 98.8% de 499 líneas cambiadas (493/499, umbral 80%)`, reproducido por mí |
| **C4 bis** · mutación verificada de forma independiente | `[x]` | ver abajo |
| **C4 bis** · supervivientes analizados | `[x]` | cero supervivientes; nada que analizar |
| **C4 bis** · sección «Evidencias» con los cuatro números | `[x]` | `impl_F-006.md:501-525` |
| **C4 ter** · rutas sensibles | **N/A** | no existe `harness/rutas_sensibles.json` (solo el `.ejemplo.json`): el bloque es N/A por configuración |
| **C5** · `tasks.md` todo `[x]` | **N/A parcial** | 14 de 42 tareas marcadas, que son **exactamente** T1–T14, el alcance encargado. Justificado: esto es una revisión de entrega intermedia, no el cierre de la feature; C5 se exigirá entero cuando F-006 pase a `done` |
| **C5** · sin artefactos sueltos | `[x]` | `git status` limpio |
| **C5** · `features.json` refleja el estado | `[x]` | `in_progress` |

### Verificación independiente de la mutación (C4 bis)

No me fié del informe. Recalculado con cálculo puro, sin ejecutar la suite:

- **Alcance**: `harness.alcance.alcance_de_feature('F-006')` da 808 + 278 + 2 +
  435 = **1523 líneas**, idéntico a `progress/mutacion_F-006.md`.
- **Mutantes**: `harness.mutacion.generar_mutantes` sobre esas líneas devuelve
  **112** (65 + 24 + 0 + 23), idéntico al informe.
- **Muestreo de mortalidad**: como la campaña declara 0 supervivientes no hay
  supervivientes que muestrear, así que hice la comprobación inversa en un
  **worktree aislado** (nunca en el árbol real): apliqué tres mutantes elegidos
  al azar —`diccionario.py:501`, `inventario.py:127`,
  `cargador_yaml.py:239`— y la suite de F-006 los mató a los tres
  (exit 1 en los tres casos). El «112 de 112 muertos» es creíble.
- La campaña no declara cero mutantes, así que la prueba de control por
  exclusión de alcance no aplica.

---

## Que no se haya tocado nada prohibido

Comprobado con `git diff dev...HEAD --name-status`. El diff **añade** nueve
ficheros de código y contenido y modifica solo `BACKLOG.md`,
`harness/features.json` y `progress/current.md`.

- **Cero cambios** en `main.py`, `config/settings.py`, `grants.py`,
  `postgres_client.py`, `infra/**` y en cualquier `.sql`. Ningún `GRANT`,
  ningún `REVOKE`, ninguna regla de firewall, nada de Azure.
- Ninguna conexión a la base: los tests nuevos no importan `psycopg` y hay un
  test que lo prohíbe explícitamente en el dominio.
- El cambio de `harness/features.json` es el `status`/`rigor` de F-006 y el
  alta de F-036 a F-040, que venía de la sesión de spec.

---

## Cómo quedan preparados los bloques E a K

Se pidió opinión expresa sobre el contrato de `_meta` que consumirá `mcp-bbdd`.
**Queda bien preparado**, con una salvedad y una dependencia:

- Las entidades del dominio cubren **campo por campo** el DDL de `design.md`
  §4.1: `tipo`, `capa`, `consumo_recomendado`, `motivo_no_consumo`,
  `descripcion`, `grano`, `clave_negocio`, `paso_etl`, `refresco`, `avisos`
  (derivados, no escritos a mano) y el resto de la ficha para el `JSONB`.
  Publicar no exige tocar el formato: es serializar lo que ya hay.
- `derivar_avisos` (R12) ya funciona y es dominio puro, así que la columna
  `avisos` del contrato se llena sola.
- **Salvedad**: el defecto 1 (`cardinalidad: 61`) llegaría tal cual al `JSONB`
  publicado. Corregirlo antes del bloque E cuesta ocho comillas; después
  cuesta una republicación.
- **Dependencia dura**: el bloque E debe crear `_meta.v_diccionario` (T15)
  **antes o a la vez** que la primera publicación, porque el texto de
  `R-FRESCURA-MANUAL` ya la cita como consultable (defecto 6).

---

## Hallazgos menores (anotar, no bloquean)

No entran en la lista de correcciones exigidas, pero conviene que el
implementer los recoja al pasar por ahí:

1. `cierre.yaml:433-436` y `:472-475` dicen que fuera de INFRA «todas las
   columnas de periodificacion son nulas»; `importe_fase0` y
   `plazo_total_meses` traen valor siempre (`04_views_detalle.sql:438-439`).
   Curiosamente las fichas de esas dos columnas sí lo dicen bien.
2. `final_anterior` (`cierre.yaml:100`): un mes anterior sin previsión da **0**,
   no NULL (`02_build_fact.sql:331`); es NULL solo en la primera fila de la
   partición.
3. «al cierre del mes anterior» (cuatro fichas) significa **fila anterior
   presente**, no mes de calendario anterior: el `LAG` salta los meses sin
   fase (`02_build_fact.sql:353-359`).
4. `v_pbi_cierre_cabecera.plazo_meses` y
   `v_pbi_cierre_indirectos_detalle.plazo_total_meses` se calculan distinto y
   dan números distintos para la misma obra; ninguna ficha lo advierte.
5. `final_pct` como «única excepción del cuadro» (`cierre.yaml:267-274`) exagera:
   en la fila VENTA los cinco porcentajes son excepción; lo único propio del
   `final_pct` es el divisor.
6. `v_pbi_dim_concepto` y `v_pbi_dim_tipologia_cp` se describen como «catálogo
   ESTATICO» pero declaran `refresco: manual`, existiendo `estatico` en el
   vocabulario.
7. Tres comentarios del SQL mienten y el YAML acierta —`04_views_detalle.sql:295`
   (cap del `ratio_lineal`), `03_views.sql:129` (fallback inexistente),
   `05_views_cabecera.sql:174` (JOIN muerto con `raw.cen`)—. No es deuda de
   esta feature, pero engañarán a quien lea el SQL: candidatos a una feature de
   limpieza.

---

## Propuesta de mejora del protocolo (no aplicada)

Para `CHECKPOINTS.md`, a decisión del humano: **cuando una feature entrega
contenido declarativo que otro sistema consumirá (YAML, prompts, fichas), C4
debería exigir explícitamente que los valores del contrato pasen por un
vocabulario cerrado validado**, no solo que el campo exista. El defecto 1 de
esta review —un `1:1` que YAML convierte en `61` y que ningún test vio— es
justo lo que ese punto habría cazado, y no lo cazan ni la cobertura (la línea
se ejecuta) ni la mutación (el valor viene del dato, no del código).
