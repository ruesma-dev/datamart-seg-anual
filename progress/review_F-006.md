<!-- progress/review_F-006.md -->
# F-006 · Review — bloques A a F

> Este fichero tiene **tres pasadas**, de la más reciente a la más antigua.
> Se conservan íntegras: son lo que se pidió corregir cada vez y el patrón
> contra el que se contrasta la siguiente.

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
