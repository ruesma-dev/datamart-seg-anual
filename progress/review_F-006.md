<!-- progress/review_F-006.md -->
# F-006 · Review de los bloques A, B, C y D

> Rama `feature/F-006-mcp-azure`, commits `ba8ff93`..`5e901f8`.
> Alcance revisado: **solo T3–T14** (bloques A a D). Los bloques E a K no
> entran en el veredicto; sí se dice al final cómo quedan preparados.

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
