<!-- specs/F-052-partidas-huerfanas/requirements.md -->
# F-052 · Requisitos · El árbol de partidas no puede amputar un subárbol

**Línea base: `progress/explore_F-052.md`** (medido contra la base el 2026-08-31,
solo lectura); sus cifras son las de esta spec y no se repiten aquí. **Las siete
decisiones están CERRADAS** por el humano el 2026-08-31 → **`decisiones.md`**; de
ese cierre salen los cambios en R11, R17 y R27 y los nuevos R28-R30.

**La causa.** El filtro `AND h.cod <> ''` de `sql/stg/04_partidas.sql:78` no solo
decide qué se publica: decide **por dónde se desciende**. Tres capítulos
intermedios con código vacío bajo la raíz `CD` de la 0599 cortan el recorrido y
**amputan 1.323 partidas**; las otras 12 perdidas son **ciclos** de `padide`. La
hipótesis anterior («la cadena no llega a una raíz») quedó **DESMENTIDA**.

**El daño.** El datamart oculta **2.624.793,46 €** de coste directo de la 0599 y
**el 100 % de su venta, 4.066.989,23 €**: publica margen del **66,3 %** cuando el
real es **1,8 %**. **Rigor `critico`**: fase RED, cobertura de las líneas
cambiadas y campaña de mutación con **cero supervivientes**; si el humano la
exime, por escrito como en F-042.

---

## 1 · El recorrido del árbol

**R1.** CUANDO el ETL reconstruye `stg.partidas`, debe **descender a través de**
un capítulo cuyo código sea la cadena vacía en vez de amputar su subárbol. Solo
se relaja la **rama de descenso** (línea 78); la raíz (línea 58) **no se toca**
(DA-1).

**R2.** El filtro de código vacío debe decidir **qué se publica, no por dónde se
desciende**: un capítulo con `cod = ''` sigue **sin publicarse** como fila de
`stg.partidas`, exactamente como hoy.

**R3.** CUANDO un capítulo no publicado queda entre una partida y su ancestro,
`capitulo_padre_id` debe apuntar al **ancestro publicado más cercano** y `nivel`
debe contar **solo ancestros publicados**.

**R4.** `ruta_capitulos` no debe contener nunca un segmento vacío. Invariante
comprobable: `cardinality(string_to_array(ruta_capitulos, ' > ')) = nivel + 1`
en toda fila de `stg.partidas`.

**R5.** SI la cadena de `padide` forma un ciclo, ENTONCES el recorrido debe
cortarlo **sin colgarse**, con array de visitados **y** tope de profundidad como
respaldo (DA-3); esa partida queda fuera de `stg.partidas` y el hecho debe poder
denunciarse (R14).

**R6.** El recorrido no debe alterar **ninguna** fila cuya cadena de ancestros no
contenga ni códigos vacíos ni ciclos: mismos `partida_id`, `codigo_partida`,
`capitulo_padre_id`, `capitulo_raiz_*`, `categoria`, `ruta_capitulos` y `nivel`.

## 2 · El resultado, con las cifras de la línea base

| | Lo que debe cumplirse tras la reconstrucción |
|---|---|
| **R7** | `stg.partidas` de **389.178** a **390.501** filas; las **19** de `raw.obrparpar` (390.520) que no lleguen deben ser **exactamente** los 7 nodos con `cod = ''` y las 12 en ciclo, enumeradas por `ide` |
| **R8** | La **0599 TANATORIO MAJADAHONDA** de **117** a **1.440** partidas (sus 1.443 de `raw` menos los 3 capítulos sin código) |
| **R9** | `mart.fact_seguimiento_mensual` gana hasta **~183.756** filas (183.530 de la 0599, +3,5 % sobre 5.297.341) y aparecen **0599 × ámbito 7** y **0599 × ámbito 11**, hoy inexistentes |
| **R10** | En `cierre`, **DIRECTOS** de la 0599 de **0,00 €** a **~2,62 M€** en sus 28 meses, y el margen de **66,3 %** a **~1,8 %** |

**R11.** *(BLOQUEANTE, DA-2.)* Ninguna obra distinta de las **seis** del informe
(0599, 0613, 0618, 0630, 0565, 0686) puede cambiar **ni una celda** en los cuatro
ámbitos (3, 7, 8, 11), ni en filas, ni en importe, **ni en su sitio dentro del
árbol**; se demuestra con las **cuatro huellas** de `design.md` §7 antes y después
sobre el **mismo `raw`**. SI se mueve una sola cifra fuera de esas seis, la feature
**se detiene y se consulta al humano**: «prefiero perder la 0599 porque no sigue el
patrón correcto» (2026-08-31).

**R12.** `check-unicidad` debe seguir dando **0 claves duplicadas** en
`mart.fact_seguimiento_mensual` después del cambio.

## 3 · El guardián: que no vuelva a caerse una obra en silencio

**R13.** Debe existir una comprobación de **solo lectura** que contraste lo que
entra en `stg` con lo que sale en `mart` por (`obra_id`, `ambito_id`).

**R14.** CUANDO una obra tenga filas en `stg.plan_mensual` para un ámbito y
**cero** en `mart.fact_seguimiento_mensual` para ese mismo ámbito, debe
**denunciarlo nombrando obra y ámbito**.

**R15.** Debe contar además las filas de `stg.plan_mensual` sin ficha de partida
o de obra, **agrupadas por obra**: es lo que los `INNER JOIN` de
`mart/02_build_fact.sql` borran hoy sin decir nada.

**R16.** Las excepciones aceptadas (12 partidas en ciclo, obras `OBRA
PRUEBA`/`POSTVENTA`/`VAR` y las tres de F-053) se declaran en configuración con
**trinquete: la lista solo puede bajar**, como `config/objetos_pendientes.yaml`.

**R17.** *(DA-4: avisa, no bloquea.)* Se ejecuta al final de `run-all` y **NO
debe hacer salir el job con código distinto de 0**: registra, y la nocturna
termina en verde. Lanzada a mano sí devuelve código distinto de 0, para servir de
puerta en una verificación manual.

**R18.** El módulo que construye la consulta **no debe abrir ninguna conexión**:
solo produce texto, al estilo de `unicidad_sql.py` y `cierres_sql.py`.

**R19.** Cada consulta debe llevar su `SET LOCAL statement_timeout`: corre contra
`psql-albaranes-rs9k2`, **compartido con `albaranes` y `partes` en producción**.

**R28.** SI encuentra algo fuera de lo declarado, ENTONCES debe escribir una línea
con un **marcador estable y buscable** (literal fijado en el diseño) más el
recuento de obras invisibles y filas huérfanas. Un test debe cruzar los dos
extremos —el código que lo emite y el `.ps1` que lo busca—, al estilo de
`test_f024_r19_umbral_por_defecto_coincide_con_dev_json`.

**R29.** Debe traer un script de infraestructura que cree la regla de consulta
programada sobre `log-datamart-seg-dev` que busque ese marcador y notifique al
grupo de acción **`ag-datamart-seg-dev`**, hermano de
`infra/95_create_alert_frescura.ps1`. Despliegue **manual**, como el resto.

**R30.** **Ninguna dirección de correo entra en el repositorio.** Los
destinatarios viven en el grupo de acción y se pasan con `-AlertEmail` al
desplegar `infra/90_create_alert.ps1`; nunca en una spec, un `.ps1` ni un `.json`.

## 4 · Documentación de lo publicado

**R20.** La ficha de `stg.partidas` en `config/diccionario/stg.yaml` debe corregir
lo que deja de ser cierto —hoy afirma que una partida sin código «no llega a esta
tabla», y ahora sus **descendientes sí llegan**— y describir el nuevo significado
de `capitulo_padre_id` (ancestro publicado, no el padre de Sigrid), `nivel` y
`ruta_capitulos`.

**R21.** Las fichas de `mart` y `cierre` deben avisar, con la fecha, de que las
cifras publicadas de la **0599** cambian a partir de esta reconstrucción, para
que quien lea un informe antiguo sepa por qué no cuadra (DA-6).

**R22.** `00_global.yaml` sube `version` y la lista de `pendientes` no crece.

**R23.** `docs/ARCHITECTURE.md`, en «Semántica Sigrid imprescindible»: un capítulo
**puede no tener código** y eso no puede cortar el árbol.

## 5 · Lo que NO entra, y lo que hay que hacer antes de publicar

**R24.** El desempate `WHERE rn = 1` de `sql/stg/03_obras.sql:125` **no se toca**.
Deja tres obras más invisibles (0517, 0252, 0720; ~10,65 M€ de coste y 10,94 M€ de
venta) por **otra causa**: es **F-053**, ya fichada con prioridad 2 (DA-7). Aquí
solo se nombra y se declara como excepción aceptada hasta que se cierre (R16).

**R25.** Los nueve puntos de descarte silencioso del informe **no se instrumentan
uno a uno**: dos de ellos (399.519 filas de fase 0 y 6,7 M de ámbitos que el fact
no mira) son descartes **por diseño**. Se instrumenta el que causó esto: el `JOIN
stg.partidas` / `JOIN stg.obras` del build (R15).

**R26.** No se escribe nada contra Sigrid. Los 3 capítulos sin código y los 2
auto-bucles son dato mal metido en el origen: se avisa a quien lo administra,
como en F-050, con **prioridad únicamente para la 0686 VALDEBEBAS** por ser obra
viva, y el ETL **no espera** al saneamiento (DA-5).

**R27.** MIENTRAS no se haya dado a Negocio el aviso de `aviso_negocio.md`, el
sistema **no debe publicar** la reconstrucción: no es un arreglo silencioso, es un
número que alguien pudo usar. **Paso manual bloqueante** del humano (DA-6).
