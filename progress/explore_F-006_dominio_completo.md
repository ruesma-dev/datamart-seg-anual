<!-- progress/explore_F-006_dominio_completo.md -->
# F-006 · El datamart como conocimiento de negocio de obra: inventario y cobertura

> Ampliación del encargo del 2026-08-20, tras reformular el humano el objetivo:
> el datamart debe ser **el repositorio único del conocimiento de negocio de
> obra**, y el MCP debe publicar su estructura y significado para que un agente
> construya sus propios casos de uso. Informe del subagente explorador (solo
> lectura), guardado por el líder. Complementa
> `explore_F-006_datamart_casos_uso.md`.

## PARTE 0 · Siete advertencias que el diccionario DEBE llevar

Sin ellas, un agente generará SQL que devuelve números plausibles y falsos.

**A0.1 · Cuatro de los ocho esquemas no se refrescan de noche.** `run-all`
(`main.py:405-430`) es `IngestRaw -> LoadExcelAux -> BuildStg -> BuildMart ->
ApplyGrants`. `cierre`, `compras`, `maestro` y `retenciones` se construyen a mano
y pueden estar arbitrariamente desfasados. Toda respuesta que salga de esos
cuatro debería citar su fecha de build (`_meta.v_frescura`).

**A0.2 · `importe_mes` no se suma entre meses; `importe_origen` ya es
acumulado.** Sumar `importe_origen` en el tiempo multiplica (~9x): fue el bug de
la Tanda 1.4 del cierre (`cierre/02_build_fact.sql:7-15`).

**A0.3 · Dos universos de obra distintos.** `stg.obras` excluye códigos
administrativos (`0001-0005`, `CM`, `CP`, `GG`, `VAR`, `POSTV`, `BD*`, `GGD`,
`GINT`, `OT`), excluye códigos de 5+ dígitos y **deduplica por `conext.cod='15'`**.
`maestro.obras` no filtra nada. Por tanto `maestro.obras` es superconjunto de
`stg.obras` y contar obras en una u otra da resultados distintos a propósito.

**A0.4 · `stg.obras.activa` está cableado a `TRUE`** (`stg/03_obras.sql:120`).
La columna no significa nada. Para saber si una obra vive: `maestro.obras.es_activa`
(de `con.fecbaj`) o las fechas de `cierre.v_pbi_cierre_cabecera`.

**A0.5 · En `stg.plan_mensual` conviven TODAS las versiones master.** Filtrar
solo por obra y ámbito **multiplica los importes por el número de versiones**. La
versión vigente solo está resuelta aguas abajo, en `mart` y en `cierre`. Un
agente debe ir a `mart`, no a `stg`.

**A0.6 · `fas` significa dos cosas.** En ámbitos reales (3, 7) `fas` = **mes**
(`fas=0` es el «Previsto» vivo). En ámbitos master (8, 11) `fas` = **número de
versión**. En `stg.presupuesto` se llama `fase_num`; en `stg.plan_mensual`,
`version`; en `raw.obrfas`, `fasnum`.

**A0.7 · Claves sustitutas no deterministas.** `plan_id`, `fact_id`,
`fact_cat_id` y `cierre_id` son `BIGSERIAL`: cambian en cada build. Nunca como
identificador estable ni expuestas al usuario.

## PARTE 1 · Notas de inventario que no estaban en el primer informe

### `_meta`
- `etl_runs`: grano (ejecución de paso o sub-paso). `batch_id`
  `YYYYMMDDTHHMMSSZ-xxxxxx`, **ordenable como texto**. Timestamps **UTC sin zona**.
- `v_raw_state`: `DISTINCT ON (step)` sobre `ingest_raw.%`. Es lo que lee la
  puerta de `build_stg` para exigir las 31 tablas del mismo batch SUCCESS.
- `v_frescura`: solo pasos (filtra los ~60 tramos). `LEFT JOIN` deliberado.

### Regla de oro de Sigrid
`ide` es la clave universal. Muchas tablas son «Propiedades de `con` 1:1»:
`obr.ide = con.ide`, y lo mismo `prv`, `dca`, `dcf`, `ctr`, `rec`, `pag`, `cob`.
**El código (`cod`), el nombre (`res`) y la fecha (`fec`) viven en `con`, no en
la extensión. `con.nom` no existe.** Fechas: enteros `YYYYMMDD`, `0` = NULL,
con cuatro funciones de conversión (una por esquema, deliberadamente).

### `stg.presupuesto` — la regla de importes
- `importe` = `ROUND(can × ROUND(pre, decp), deci)`. **La cantidad no se
  redondea**: redondearla infla los CP tipo porcentaje.
- `importe_oficial` = `COALESCE(NULLIF(impcoe,0), importe)`; `impcoe` lleva los
  coeficientes que Sigrid aplica **solo en venta**.
- **Para coste (amb 3, 8) usar `importe`; para venta (amb 7, 11)
  `importe_oficial`.**
- Es el importe **total sin distribución mensual**: es lo que hay que usar para
  «el presupuesto de la obra», no la suma de `plan_mensual`.

### `stg.plan_mensual` — semántica del `planif` (validada al céntimo)
La cadena `v1|v2|...|vN` es **pct acumulado literal**. Un `0` intermedio es
estorno literal; un `0` final hace *forward fill del último positivo*, no del
máximo; un `0` de pre-arranque es 0. `pct_mes = pct_efectivo - LAG(pct_efectivo)`.
Ancla del mes 1: `raw.obrfasamb.plafec`.
`version_fec_efectiva` = fecha de creación salvo cuatrimestral entregada tarde
(caso real: obra 0704 V11).

### `mart.fact_seguimiento_mensual` — reglas de versión
- `tipo_master` se deriva de `version_tex` con prioridad estricta: `ABC` ->
  'ABC'; `INICIAL` **y** `VALORADA` -> 'Planif Inicial'; `CUATRIM` **o**
  `VALORADA` -> 'Cuatrimestral'; `CIERRE` -> 'Cierre mensual'; resto -> 'Sin
  clasificar'.
- **Solo son «master vigente»** Planif Inicial, ABC y Cuatrimestral. Las de
  Cierre mensual **no reemplazan al plan**: si una obra solo tiene cierres en un
  mes, ese mes queda sin planificado (síntoma de obra mal configurada).
- Si la versión vigente no tiene fila ese mes, importes = **0**, pero la versión
  sigue siendo la vigente.

### `cierre.fact_cierre_mensual` — cómo se construye
- EJECUTADO de `stg.plan_mensual` amb 7 (VENTA) y amb 3 por categoría
  (CI/CD/CP), unido a `stg.fases` por `numero_fase = version`. Mes canónico por
  `fn_mes_de_fase`: **manda el TEXTO si discrepa de la fecha**.
- FINAL master de **`stg.presupuesto`, no de `plan_mensual`** (fix de la Tanda 1.5).
- **Fallback fase 0** = presupuesto vivo, aplicado **también a meses cerrados**
  por diseño: dos capturas en momentos distintos pueden diferir legítimamente.
- Los % de `v_pbi_cierre_resumen` se dividen por la **VENTA de esa misma columna
  y ese mismo mes**; excepción, `VENTA final_pct` va contra
  `presupuesto_aprobado_venta`.

### `compras.fact_compras_linea` — trampa de clave
**No tiene PK declarada y `linea_id` NO es único**: viene de tres tablas Sigrid
distintas (`ctrpro`, `dcapro`, `dcfpro`) que pueden colisionar. La clave real es
`(tipo_doc, linea_id)`. Un agente no debe tratar `linea_id` como único.
Resolución de obra en cascada: contrato -> cabecera; albarán -> línea, fallback
al contrato; factura -> línea, fallback a la línea de albarán origen y luego al
contrato. **Los abonos entran con signo natural negativo.**

### `maestro.proveedores_obra` — trampa de importe
`importe_contratado` = `SUM(ctr.totdoc)`, es decir **total del documento con
IVA**: distinto de la suma de líneas sin IVA de `compras`. `raw.obrprv`, la
tabla «Obras: Proveedores» de Sigrid, **está vacía en Ruesma**.

### `retenciones.movimientos` — atribución a obra
Orden: (1) `efecto.cenide` (en Ruesma cada obra es su centro, ~98 %); (2) las
líneas del documento origen **solo si todas apuntan a la misma obra**. Si la
factura reparte, `obra_id` queda NULL y `num_obras_documento > 1`.
**Nunca hacer join directo a las líneas: multiplica el importe por el número de
líneas.** `padide` es siempre 0 en Ruesma.

### El eje que nadie explota
`partida_id` une los dos mundos: `stg.partidas` / `stg.plan_mensual` /
`mart.fact_seguimiento_mensual` por un lado, y `compras.contrato_lineas` /
`albaran_lineas` / `factura_lineas` / `fact_compras_linea` /
`v_pbi_partida_coste` por otro. **Permite comparar coste planificado de la
partida con coste incurrido documental de la partida, y hoy no lo hace ninguna
vista.** Es la relación más valiosa del datamart.

⚠ `compras` y `retenciones` **no** filtran por `stg.obras`: pueden traer obras
administrativas que el seguimiento excluye.

## PARTE 2 · Mapa de cobertura del dominio

Leyenda: ✅ en el datamart · 🟡 en `raw` sin modelar · 🔴 en Sigrid sin ingerir ·
⬛ otro proyecto / no existe

| Área | Estado |
|---|---|
| Presupuesto y partidas | ✅ alta |
| Producción (venta real/planificada) | ✅ alta |
| **Certificaciones a cliente** | 🔴 ausente (`cer`, `cerpro`, `obrcer`) |
| Contratación de proveedores | ✅ buena |
| Compras: ofertas y pedidos | 🔴 ausente (`dco`, `dcp`) |
| **Comparativos de ofertas** | 🟡 en `raw`, cero modelado |
| Albaranes de compra | ✅ muy buena |
| Facturas recibidas | ✅ muy buena |
| Retenciones (proveedor) | ✅ buena |
| Retenciones (cliente) | 🟡 sin respaldo ni CIF |
| Avales y fianzas | 🔴 ausente (`ava`, `avr`) |
| **Cobros / pagos / tesorería** | 🟡 el 100 % del dato en `raw.pag`/`cob`, filtrado y descartado |
| Previsiones de pago, remesas, bancos | 🔴 ausente (`prp`, `mte`, `rpa`) |
| Mano de obra | 🔴 ausente · ⬛ proyecto `partes` |
| Maquinaria y alquileres | 🔴 ausente |
| Cierre mensual | ✅ alta (F-017/F-018 abiertas) |
| Cierre anual | 🟡 solo CP |
| Planificación mensual de importes | ✅ alta (F-002/F-022 abiertas) |
| Planificación por tareas / Gantt | 🔴 ausente (`tar`, `obrlba`) |
| Maestro de obras | ✅ buena |
| Maestro de proveedores | 🟡 sin oficio ni naturaleza |
| **Maestro de clientes** | 🔴 **ausente: `cli` no se ingiere** |
| Maestro de productos | 🔴 ausente (`pro`, `auxfam`, `auxpronat`) |
| **Clasificación por oficio** | 🔴 **ausente aquí; existe en Sigrid** |
| Contabilidad y analítica | 🔴 ausente (`asi`, `cua`, `caa`) |

### El hallazgo principal: el oficio SÍ existe en Sigrid

| Clasificador | Dónde vive | Estado |
|---|---|---|
| **`auxofc` — Oficios** (`ide`, `cod`, `res`) | catálogo | 🔴 sin ingerir |
| **`obrofc` — «Obras: Oficios»** (`obride`, `pos`, **`ofcide`**, **`prvide`**, `coment`) | tabla 1:N | 🔴 sin ingerir |
| `prv.ofcide` — oficio del proveedor | 🟡 **ya en `raw.prv`** | sin catálogo ni exposición |
| `prv.natide` -> `auxpronat` | 🟡 **ya en `raw.prv`** | ídem |
| `obrparpar.tcaide` -> `auxobrtca` | 🟡 **ambos ya en `raw`** | **`auxobrtca` se ingiere y ningún SQL lo usa** |
| `obrparpar.prvide` — proveedor de la partida | 🟡 ya en `raw` | sin exponer |
| `obrparpar.nati` — naturaleza del trabajo | 🟡 ya en `raw` | sin exponer |
| `obrparpar.cosindide` -> `auxobrcin` | 🟡/🔴 | sin exponer |
| `pro.natide`/`famide`/`linide` | 🔴 `pro` sin ingerir | naturaleza/familia del producto |

**`obrofc` es literalmente la tabla «qué proveedor hace qué oficio en qué obra».**
Ingerir `obrofc` + `auxofc` (dos tablas pequeñas) convierte la pregunta del
fontanero en un SELECT de tres líneas. Es la mejor relación coste/valor del
informe.

Mientras tanto lo único disponible es texto libre (`contratos.descripcion`, que
en Ruesma suele nombrar el oficio: «FONTANERÍA Y SANEAMIENTO»). Y la única
taxonomía que llega al datamart —CD/CI/CP/OTRO— es una **heurística sobre el
código del capítulo raíz**, pese a que `auxobrtca`, el catálogo oficial, se
ingiere desde el principio y el propio `tables_sigrid.yaml` lo justifica
diciendo que sirve «para clasificar sin depender de heurísticas».

## PARTE 3 · Escalones de ampliación recomendados

**Escalón 1 — coste casi nulo (solo tocan `raw` ya cargado o una vista):**
1. Ingerir `obrofc` + `auxofc` -> clasificación por oficio.
2. Exponer `prv.ofcide` y `prv.natide` en `maestro.proveedores` (+ `auxpronat`).
3. Usar `obrparpar.tcaide` -> `auxobrtca` en `stg.partidas` en vez de la heurística.
4. Vista `retenciones.v_pbi_retencion_obra_entidad` (obra × proveedor).
5. Vista `compras.v_pbi_proveedor_periodo` (proveedor × mes, sin obra).

**Escalón 2 — módulo nuevo, SQL casi calcado del existente:**
6. Esquema `tesoreria` sobre `raw.pag`/`raw.cob` **sin** el filtro `retide<>0`,
   con `sentido` COBRO/PAGO y `estado` PREVISTO/REALIZADO. Mismo patrón que
   `retenciones/01_movimientos.sql`. Campos ya disponibles: `tot`, `fecven`,
   `fecrea`, `conide`, `entide`, `cenide`, `efeide`, `natide`, `remide`,
   `banide`, `prpide`.
7. Modelar comparativos en `compras` (`com`/`comlin`/`comprv` ya en `raw`).
8. Vista puente partida × (plan vs incurrido documental) por `partida_id`.

**Escalón 3 — ingesta nueva, estructural:**
9. Ventas: `dvf`/`dvfpro` (snippet ya preparado en
   `config/tables_sigrid_venta_snippet.yaml`).
10. Certificaciones: `cer`/`cerpro`/`obrcer` — el eslabón entre producción y cobro.
11. Clientes: `cli` — hoy solo tenemos el nombre.
12. Pedidos de compra: `dcp`/`dcppro` — «qué está pedido y no ha llegado».

**Escalón 4 — decisiones de alcance, no de implementación:**
13. Mano de obra (`hmo`, `emp`) y maquinaria (`maq`): solapan con el proyecto
    `partes`. Decidir si el datamart es fuente única o se federa.
14. Planificación por tareas / Gantt (`tar`, `obrlba`).

## PARTE 4 · Las 31 tablas ingeridas

**Núcleo del seguimiento (13):** `con` (entidad universal; aporta `cod`/`res`/`fec`
a todo), `conext` (campos extendidos; `cod='15'` = versión master vigente),
`obr`, `obrparpar` (partidas y capítulos, con `tcaide`/`prvide`/`nati` sin
explotar), `obrparpre` (presupuestos y la cadena `planif`), `obrfas` (fases;
campo `fasnum`), `obrfasamb` (`plafec` = ancla del mes 1; `tex` clasifica la
versión), `obrctr` (contratos de obra lado cliente, con `coegar`), `cen`,
`auxobrtip`, `auxobrcla`, `auxobramb`, `auxobrtca` (**se ingiere y nadie lo usa**).

**Maestros (6):** `condir` (direcciones; las obras no tienen), `obrprv`
(**vacía en Ruesma**), `prv` (con `ofcide` y `natide` sin explotar), `auxpro`,
`auxmun`, `ctr`.

**Compras, tandas C1-C2 (9):** `com`, `comlin`, `comprv` (**ingeridos, nunca
modelados**), `ctrpro` (~241 k), `dca` (~305 k), `dcapro` (~1,13 M, con
`canfac`), `dcf` (~163 k), `dcfpro` (~1,08 M), `dcfprodes` (~267 filas).

**Retenciones, tanda R1 (3):** `cob` (21.643), `pag` (252.189) — **con
`retide<>0` son retenciones; el resto es el flujo de caja y se descarta** — y
`rec` (2.177; tipo dominante `ide=558368`, 97 %).

Columnas excluidas a propósito en `dca`/`dcf` que harían falta para tesorería:
`pagfor` (fórmula de pago), `pagtex` (condiciones), `texent`.
