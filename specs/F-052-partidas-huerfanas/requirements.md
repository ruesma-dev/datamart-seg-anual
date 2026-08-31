<!-- specs/F-052-partidas-huerfanas/requirements.md -->
# F-052 · Requisitos · El árbol de partidas no puede amputar un subárbol

**Línea base: `progress/explore_F-052.md`** (medido contra la base el
2026-08-31, solo lectura). Sus cifras son las de esta spec y no se repiten aquí
más de lo imprescindible.

**La causa, ya identificada y medida.** El filtro `AND h.cod <> ''` de
`sql/stg/04_partidas.sql:78` no solo decide qué se publica: decide **por dónde
se desciende**. Tres capítulos intermedios con código vacío que cuelgan de la
raíz `CD` de la 0599 —«FASE 1 - MOVIMIENTO TIERRAS Y CIMENTACIÓN», «FASE 2 -
OBRA CIVIL», «FASE 2 - INSTALACIONES»— cortan el recorrido y **amputan 1.323
partidas**. Las otras 12 perdidas son **ciclos** de `padide`. La hipótesis
anterior («la cadena no llega a una raíz») quedó **DESMENTIDA**: la cadena sí
llega.

**El daño.** El datamart oculta **2.624.793,46 €** de coste directo de la 0599
(65,7 % de su coste) y **el 100 % de su venta real, 4.066.989,23 €**: publica un
margen del **66,3 %** cuando el real es **1,8 %**, y `cierre.fact_cierre_mensual`
saca esa obra con **DIRECTOS = 0,00 €** junto a 4 M€ de venta sin que chirríe.

**Rigor `critico`**: fase RED obligatoria, cobertura de las líneas cambiadas y
campaña de mutación completa con **cero supervivientes** (`harness/rigor.json`).
Si el humano la exime, debe quedar por escrito como en F-042.

---

## 1 · El recorrido del árbol

**R1.** CUANDO el ETL reconstruye `stg.partidas`, el sistema debe **descender a
través de** un capítulo cuyo código sea la cadena vacía, en vez de amputar su
subárbol.

**R2.** El filtro de código vacío debe decidir **qué se publica, no por dónde se
desciende**: un capítulo con `cod = ''` sigue **sin publicarse** como fila de
`stg.partidas`, exactamente como hoy.

**R3.** CUANDO un capítulo no publicado queda entre una partida y su ancestro,
`capitulo_padre_id` de esa partida debe apuntar al **ancestro publicado más
cercano**, y `nivel` debe contar **solo ancestros publicados**.

**R4.** `ruta_capitulos` no debe contener nunca un segmento vacío. Invariante
comprobable: `cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1`
para toda fila de `stg.partidas`.

**R5.** SI la cadena de `padide` de una partida forma un ciclo, ENTONCES el
recorrido debe cortarlo **sin colgarse**, esa partida debe quedar fuera de
`stg.partidas` y el hecho debe poder denunciarse (R14).

**R6.** El recorrido no debe alterar **ninguna** fila cuya cadena de ancestros no
contenga ni códigos vacíos ni ciclos: mismos `partida_id`, `codigo_partida`,
`capitulo_padre_id`, `capitulo_raiz_*`, `categoria`, `ruta_capitulos` y `nivel`.

## 2 · El resultado, con las cifras de la línea base

**R7.** Tras la reconstrucción, `stg.partidas` debe pasar de **389.178** a
**390.501** filas, y las **19** filas de `raw.obrparpar` (390.520) que sigan sin
llegar deben ser **exactamente** los 7 nodos con `cod = ''` y las 12 en ciclo,
enumeradas por `ide`.

**R8.** La obra **0599 TANATORIO MAJADAHONDA** debe pasar de **117** a **1.440**
partidas publicadas (las 1.443 de `raw` menos sus 3 capítulos sin código).

**R9.** `mart.fact_seguimiento_mensual` debe ganar hasta **~183.756** filas
(**183.530** de la 0599, +3,5 % sobre 5.297.341) y deben aparecer las
combinaciones **0599 × ámbito 7** y **0599 × ámbito 11**, hoy inexistentes.

**R10.** En la capa `cierre`, los **DIRECTOS** de la 0599 deben pasar de
**0,00 €** a **~2,62 M€** repartidos en sus 28 meses, y el margen publicado de
**66,3 %** a **~1,8 %**.

**R11.** *(La prueba que decide.)* Ninguna obra distinta de las **seis** del
informe (0599, 0613, 0618, 0630, 0565, 0686) puede cambiar **ni una celda** en
los cuatro ámbitos (3, 7, 8, 11), ni en número de filas ni en importe. Se
demuestra con `huella-obras` / `comparar-huellas` antes y después sobre el
**mismo `raw`**, como en F-042.

**R12.** `python main.py check-unicidad` debe seguir dando **0 claves
duplicadas** en `mart.fact_seguimiento_mensual` después del cambio.

## 3 · El guardián: que no vuelva a caerse una obra en silencio

**R13.** El sistema debe ofrecer una comprobación de **solo lectura** que
contraste lo que entra en `stg` con lo que sale en `mart` por
(`obra_id`, `ambito_id`).

**R14.** CUANDO una obra tenga filas en `stg.plan_mensual` para un ámbito y
**cero** filas en `mart.fact_seguimiento_mensual` para ese mismo ámbito, la
comprobación debe **fallar nombrando obra y ámbito**.

**R15.** La comprobación debe contar además las filas de `stg.plan_mensual` cuyo
`partida_id` no tiene ficha en `stg.partidas` o cuyo `obra_id` no la tiene en
`stg.obras`, **agrupadas por obra**, que es lo que los `INNER JOIN` de
`mart/02_build_fact.sql` borran hoy sin decir nada.

**R16.** Las excepciones conocidas y aceptadas (las 12 partidas en ciclo, las
obras `OBRA PRUEBA`/`POSTVENTA`/`VAR`, y las tres obras que dependen de F-053)
deben declararse en un fichero de configuración con **trinquete: la lista solo
puede bajar**, como `config/objetos_pendientes.yaml`.

**R17.** La comprobación debe ejecutarse al final de `run-all` y hacer **salir
con código distinto de 0** cuando encuentre algo fuera de lo declarado.

**R18.** El módulo que construye la consulta **no debe abrir ninguna conexión**:
solo produce texto, al estilo de `unicidad_sql.py` y `cierres_sql.py`.

**R19.** Cada consulta debe llevar su `SET LOCAL statement_timeout`: corre contra
`psql-albaranes-rs9k2`, **compartido con `albaranes` y `partes` en producción**.

## 4 · Documentación de lo publicado

**R20.** La ficha de `stg.partidas` en `config/diccionario/stg.yaml` debe
corregir lo que deja de ser cierto: hoy afirma que una partida sin código «no
llega a esta tabla», y a partir de ahora sus **descendientes sí llegan**. Debe
describir el nuevo significado de `capitulo_padre_id` (ancestro publicado, no
necesariamente el padre de Sigrid), `nivel` y `ruta_capitulos`.

**R21.** Las fichas de `mart` y `cierre` deben avisar de que las cifras
publicadas de la **0599** cambian a partir de esta reconstrucción, con la fecha,
para que quien lea un informe antiguo sepa por qué no cuadra.

**R22.** `config/diccionario/00_global.yaml` debe subir `version`, y la lista de
`pendientes` no puede crecer.

**R23.** `docs/ARCHITECTURE.md` debe recoger, en «Semántica Sigrid
imprescindible», que en Sigrid un capítulo **puede no tener código** y que eso no
puede cortar el árbol.

## 5 · Lo que NO entra en esta feature

**R24.** El desempate `WHERE rn = 1` de `sql/stg/03_obras.sql:125` **no se
toca**. Deja tres obras más invisibles (0517, 0252 y 0720; ~10,65 M€ de coste y
10,94 M€ de venta) por **otra causa**, y se ficha como feature aparte (F-053).
Esta spec solo la nombra como dependencia conocida y la declara en R16.

**R25.** Los nueve puntos de descarte silencioso de la sección 4 del informe
**no se instrumentan uno a uno**. Dos de ellos (las 399.519 filas de fase 0 y los
6,7 M de ámbitos que el fact no mira) son descartes **por diseño**. Se instrumenta
el que causó esto: el `JOIN stg.partidas` / `JOIN stg.obras` del build (R15).

**R26.** No se escribe nada contra Sigrid. Los 3 capítulos sin código y los 2
auto-bucles son dato mal metido en el origen: se avisa a quien lo administra,
como en F-050, pero el ETL se protege igual y **no espera** al saneamiento.

## 6 · Antes de publicar

**R27.** MIENTRAS no se haya avisado a Negocio del cambio de cifras de la 0599,
el sistema no debe publicar la reconstrucción: no es un arreglo silencioso, es un
número que alguien pudo usar. El aviso lo da el humano con la tabla de la sección
3 del informe.
