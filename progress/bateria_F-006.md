# Batería de aceptación de F-006 — 18 preguntas contra el diccionario publicado

**Fecha de ejecución:** 2026-08-22
**Ejecutor:** agente actuando como *usuario de negocio con MCP*, sin acceso al
repositorio `datamart-seg-anual` (única lectura permitida: §9 de
`specs/F-006-mcp-azure/requirements.md`, el fichero de preguntas).
**Prototipo:** `C:\Users\pgris\PycharmProjects\mcp-bbdd`, invocado desde Python
con su propia fábrica (`interface_adapters/mcp/fabrica.py`), sin cliente MCP
interactivo. Todas las llamadas pasaron por los mismos servicios que usan las
herramientas del servidor.
**Base:** `sigrid_dm` en `psql-albaranes-rs9k2`, rol `mcp_sigrid_dm_ro`
(solo lectura). Diccionario leído de `_meta` (`origen: bbdd`): **versión 6,
publicada 2026-08-22 00:02 UTC, 103 objetos, 798 columnas, 13 reglas,
cobertura 100,00 %**, hash `52f10723…`.

---

## 0 · Arranque (camino de un agente real)

| # | Herramienta | Resultado |
|---|---|---|
| 1 | `estado_servidor()` | Conexión OK. PostgreSQL 16.14. Esquemas autorizados: `mart, cierre, stg, compras, maestro, retenciones, aux, _meta`. **`raw` NO es consultable** aunque esté documentado (31 objetos). |
| 2 | `contexto_bbdd()` | Fecha del servidor 2026-08-22. Sirvió las **13 reglas duras enteras** más el resumen por esquema con la fecha del último build. |
| 3 | `listar_tablas()` | 61 objetos consultables de 103 documentados, con el motivo explícito de cada `[NO RECOMENDADO PARA CONSULTA]`. |

**Lo bueno, dicho de entrada.** El arranque es excelente. Las 13 reglas llegan
*antes* de escribir una sola consulta y están redactadas como orden más motivo,
no como advertencia genérica. Las fichas de `describir_tabla` son, con
diferencia, lo mejor de este diccionario: declaran el grano real (no el
teórico), el significado del NULL columna a columna, la agregación permitida
(`suma` / `ultimo_valor` / `no_sumable` / `suma_solo_dentro_del_mes`), y —esto
es raro y muy valioso— **declaran los defectos abiertos del propio build con la
cifra medida**.

**Lo primero que falla, y falla en el arranque.** `contexto_bbdd()` **no sirve
tres de los cinco bloques que `_meta.diccionario_contexto` publica**. Detalle
en el hallazgo H-1.

---

## P1 · ¿Qué proveedores nos han facturado más?

**Herramientas:** `contexto_bbdd` → `listar_tablas` → `describir_tabla('compras.v_pbi_proveedor_obra')` → `describir_tabla('compras.fact_compras_linea')` → `consultar` ×4.

**SQL final (ranking):**
```sql
SELECT proveedor_id, max(proveedor_nombre) AS proveedor,
       sum(facturado) AS facturado_neto_sin_iva,
       sum(facturado) FILTER (WHERE obra_id IS NULL) AS de_ello_sin_obra
FROM compras.v_pbi_proveedor_obra
GROUP BY proveedor_id ORDER BY 3 DESC NULLS LAST LIMIT 10;
```

**Resultado (histórico completo, neto sin IVA):**

| # | Proveedor | Facturado neto |
|---|---|---|
| 1 | CONSTRUCCIONES RUESMA, S.A. | 15.781.090,03 € *(todo sin obra)* |
| 2 | UTE VALDEBEBAS VI | 9.662.092,82 € |
| 3 | ZANELA FERREIRA, S.L. | 9.064.666,01 € |
| 4 | UTE JARAS BOADILLA | 8.095.771,41 € |
| 5 | ARMADURAS DE ACERO FERRALIA, S.L. | 7.868.804,68 € |

**Contraste hecho:** total de la vista 828.903.506,41 € frente a
`SUM(importe)` sobre `fact_compras_linea` con `tipo_doc IN ('FACTURA','ABONO')`
= 828.903.912,97 €. La diferencia son **406,56 €**, que es exactamente el
importe de las líneas sin proveedor. **La ficha lo había predicho literalmente**
(«la vista filtra `proveedor_id IS NOT NULL`… para no perderlas hay que ir a
`compras.fact_compras_linea`»). Las filas con `obra_id IS NULL` no se perdieron:
27.553.336,83 € de estructura/generales.

**Avisos que el diccionario dio y usé:** sin IVA, abonos con signo natural
(no restar dos veces), no perder `obra_id IS NULL`, clave real
`(tipo_doc, linea_id)`, y que `compras` es de **refresco manual**.

**Veredicto: RESPONDIDA.**

**Pero:** el proveedor nº 1 de la empresa es **la propia empresa**
(CONSTRUCCIONES RUESMA, S.A., 15,78 M€, el 100 % sin obra). El diccionario **no
dice una palabra** sobre autofacturación, UTEs ni intercompañía, y sin embargo
tres de los cinco primeros puestos del ranking son entidades del propio grupo
(«CONSTRUCCIONES RUESMA», «UTE VALDEBEBAS VI», «UTE JARAS BOADILLA»). Un usuario
de negocio recibiría «nuestro mayor proveedor somos nosotros» sin ninguna
señal de que eso es una convención contable y no un dato de compras. **Falta una
regla o una nota de campo sobre qué es un proveedor intragrupo y si debe
excluirse del ranking.**

---

## P2 · ¿Qué retenciones tengo de los proveedores de la obra X?

Obra X = **0655 · HOTEL FLORIDA NORTE - PROYECTO PRÍNCIPE (MADRID)**.

**Herramientas:** `describir_tabla('maestro.obras')` → `describir_tabla('retenciones.movimientos')` → `buscar_valor('maestro.obras','nombre_obra','VALDEBEBAS')` → `consultar` ×4 → `describir_tabla('retenciones.v_pbi_retencion_obra')`.

**SQL final:**
```sql
SELECT entidad_id, max(entidad_nombre) AS proveedor,
       sum(importe) FILTER (WHERE estado='VIVA') AS saldo_vivo,
       sum(importe)                              AS neto_practicado,
       count(*) AS efectos
FROM retenciones.movimientos
WHERE sentido='PROVEEDOR' AND obra_id = 1990274
GROUP BY 1 ORDER BY saldo_vivo DESC NULLS LAST;
```

**Resultado:** 453 efectos. **Saldo vivo de la obra: 1.667.521,24 €**; neto
practicado 1.764.948,03 €. Los cinco mayores: INSELEC GLOBAL 280.971,72 €;
MADERSENIA 266.380,00 €; VITALPLAC 163.660,13 €; TALLERES PROEJE 142.008,93 €;
SISTEMAS VALCOM 105.012,06 €.

**Contraste de orden de magnitud:** total empresa `PROVEEDOR` = 25.392 efectos,
neto 39.513.230,84 €, saldo vivo 35.279.498,06 €. Coincide con el orden de
magnitud publicado (34,7 M€ / 25.124 efectos) y **con el famoso 38,9 M€ que en
su día se atribuyó por error a una sola obra**: la cifra de la empresa entera.
No uní a `compras.factura_lineas` (regla `R-RETENCION-NO-JOIN-LINEAS`).

**Filas sin obra señaladas:** 533 efectos, 3.257.556,49 €, que quedan fuera de
cualquier suma por obra.

**Veredicto: RESPONDIDA.**

**Dos cosas que el diccionario dice y la base contradice:**

1. La ficha de `num_obras_documento` explica que `obra_id IS NULL` **junto con
   `num_obras_documento > 1`** es la marca de «factura que reparte entre varias
   obras». **En sentido PROVEEDOR eso no ocurre nunca**: los 533 efectos sin obra
   tienen `num_obras_documento = 0`, los 533. El marcador que la ficha enseña a
   buscar no se dispara jamás, y la ficha solo advierte de ese cero para el
   sentido CLIENTE.
2. Ver **H-2**: el `obra_id` de este esquema no es el de `maestro.obras`.

---

## P3 · ¿Quién fue el proveedor de fontanería de la obra X?

**Herramientas:** `describir_tabla('compras.contratos')` → `consultar` ×5.

**Objeto que el diccionario manda usar:** `compras.contratos.descripcion`, cuya
ficha dice literalmente: *«En Ruesma **suele nombrar el oficio** ("FONTANERIA Y
SANEAMIENTO"), y es la única vía —heurística— de responder quién hizo qué en una
obra»*.

**Lo medido:**
```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE descripcion ILIKE '%fontan%')                      AS con_oficio,
       count(*) FILTER (WHERE descripcion ILIKE '%'||proveedor_nombre||'%')      AS es_el_proveedor
FROM compras.contratos;
-- total 18.879 · con_oficio 5 · es_el_proveedor 16.513
```

**`descripcion` contiene un oficio en 5 de 18.879 contratos (0,03 %), y en
16.513 (87,5 %) es literalmente el nombre del proveedor** seguido de una
referencia documental: `"AIRMAX RENTAL GROUP, S.A.U.. (02/11/2023)"`. En la
obra 0655, con 152 contratos, **cero** menciones de oficio.

**Vía alternativa que sí funciona** (texto libre de línea, no de cabecera):
```sql
SELECT proveedor_nombre, sum(importe) AS facturado
FROM compras.fact_compras_linea
WHERE codigo_obra='0655' AND tipo_doc IN ('FACTURA','ABONO')
  AND descripcion ILIKE '%fontan%'
GROUP BY 1 ORDER BY 2 DESC;
```
→ SISTEMAS VALCOM, S.L. 26.544,30 €; VITALPLAC 16.669,32 €; RAUL MERINO RAMOS
6.068,45 €; FEYMACO 13,59 €. Candidato razonable: **SISTEMAS VALCOM, S.L.**,
declarándolo como **heurística sobre texto libre**.

**Veredicto: RESPONDIDA CON DUDA.** La parte que el criterio de §9 exige —«la
respuesta correcta declara que es una heurística y que el datamart no tiene
taxonomía de oficio»— sí la da el diccionario, y de forma ejemplar: la ficha de
`maestro.proveedores` dice que el oficio está en `raw.prv` y ninguna vista lo
saca (F-036).

**Pero el diccionario me mandó al objeto equivocado y con una afirmación falsa.**
De haberme fiado, habría contestado «no hay contratos de fontanería en esa obra»,
que es una respuesta errónea con aire de respuesta correcta. La frase «suele
nombrar el oficio» **hay que corregirla**: lo que suele nombrar es el proveedor.

---

## P4 · ¿Cuál es el flujo de caja de la obra X?

**Herramientas:** `listar_tablas` (61 objetos revisados) → `consultar` ×2 sobre `_meta.v_diccionario`.

```sql
SELECT count(*) FROM _meta.v_diccionario
WHERE objeto ILIKE '%cobro%' OR objeto ILIKE '%pago%' OR objeto ILIKE '%tesor%'
   OR objeto ILIKE '%caja%'  OR objeto ILIKE '%banco%' OR objeto ILIKE '%efecto%';
-- 0
```
Cero objetos de tesorería en los 103 documentados, repartidos en
`aux 1 · cierre 12 · compras 14 · maestro 4 · mart 13 · _meta 8 · raw 31 ·
retenciones 10 · stg 10`.

**Respuesta al usuario:** *el datamart no tiene tesorería*. Lo que hay es el
mundo **documental** de la compra (contratos, albaranes, facturas) y las
retenciones de garantía; cuándo se paga o se cobra, no. En `raw` existen las
tablas `cob` y `pag` de Sigrid, pero `raw` no es consultable y no está modelado.

**Veredicto: RECHAZADA CORRECTAMENTE.** El diccionario permitió llegar al «no
puedo, y este es el motivo» sin dar ningún número inventado.

---

## P5 · De la obra X: facturado por contrato, albarán sin facturar y comparativos

**Herramientas:** `describir_tabla('compras.v_pbi_contrato_consumo')` → `describir_tabla('compras.v_pbi_albaranes_sin_facturar')` → `consultar` ×2.

**Contratos (obra 0655, 152 contratos):**
contratado **17.396.669,21 €** · facturado **16.917.008,65 €** · consumido
17.008.419,84 € · disponible 388.249,37 € · pendiente según esta vista
**91.410,95 €**.

**Albaranes sin facturar (obra 0655):** 2.910 líneas, todas `ALBARAN`,
**14.580.976,11 €** pendientes. Ninguna PROFORMA.

**Comparativos: NO EXISTEN como objeto.** `compras.contratos.comparativo_id`
guarda solo el identificador; la ficha lo dice: *«el comparativo NO está
modelado en el datamart, aunque sus tablas de origen sí están ingeridas. Es
F-038»*. Correctamente declarado.

**Sobrefacturación:** la vista `v_pbi_albaranes_sin_facturar` filtra `> 0`; el
signo negativo se conserva en `compras.albaran_lineas`, tal y como avisa la
ficha. Comprobado: 89.865 líneas con pendiente negativo.

**Veredicto: RESPONDIDA CON DUDA.**

**La duda es de tamaño 160×.** Las dos cifras de «entregado y no facturado» de
la misma obra difieren en tres órdenes de magnitud: **91.410,95 €** en
`v_pbi_contrato_consumo` frente a **14.580.976,11 €** en
`v_pbi_albaranes_sin_facturar`. La ficha avisa de que «las dos cifras pueden no
coincidir» porque una filtra tipo de documento y la otra no —pero eso explica una
diferencia por NOTA y OTRO, **no un factor de 160**. La causa real es que la
primera solo cuenta lo que cuelga de un contrato y la segunda todo, y **eso no
está escrito en ninguna de las dos fichas**. Un usuario que pregunte «¿cuánto
tengo sin facturar en la 0655?» recibe 91 mil o 14,5 millones según a qué objeto
vaya, sin nada que le diga cuál es el suyo.

---

## P6 · ¿Cuál es la planificación mensual de la obra X?

Obra X = **0696 · 88+88 VIVIENDAS KODAK - EL QUINTANAR (LAS ROZAS)**
(`obra_id` 2419057), la más activa de 2026.

**Herramientas:** `describir_tabla('mart.fact_seguimiento_mensual')` → `describir_tabla('mart.v_master_versiones_tipadas')` → `consultar` ×2.

**SQL final:**
```sql
SELECT anio_mes,
       sum(importe_mes) FILTER (WHERE escenario='Coste Planificado')  AS coste_plan,
       sum(importe_mes) FILTER (WHERE escenario='Venta Planificada')  AS venta_plan,
       max(version_master) FILTER (WHERE escenario='Coste Planificado') AS version
FROM mart.fact_seguimiento_mensual
WHERE obra_id=2419057 AND anio=2026
  AND escenario IN ('Coste Planificado','Venta Planificada')
GROUP BY 1 ORDER BY 1;
```

**Resultado (2026, `importe_mes`, EUR):**

| Mes | Coste plan. | Venta plan. | Versión |
|---|---|---|---|
| Ene | 1.226.358,98 | 1.091.422,38 | 17 |
| Feb | 1.104.154,66 | 900.393,05 | 22 |
| Mar | 1.384.370,08 | 1.192.408,39 | 22 |
| Abr | 1.960.589,45 | 1.829.117,27 | 22 |
| May | 2.863.733,99 | 2.751.564,30 | 22 |
| Jun | 2.710.402,85 | 2.469.747,61 | 27 |
| Jul | 2.526.568,03 | 2.294.519,13 | 27 |
| Ago | 2.145.394,88 | 2.013.992,19 | 27 |
| Sep | 3.496.700,03 | 3.455.240,41 | 27 |
| Oct | 4.131.714,29 | 4.130.340,78 | 27 |
| Nov | 4.033.447,77 | 3.989.252,61 | 27 |
| Dic | 3.149.179,27 | 3.083.187,54 | 27 |

**Todo lo que §9 exige, cumplido:** fui a `mart` y **no** a `stg.plan_mensual`
(`R-VERSION-MASTER`), usé `importe_mes` y no `importe_origen` (`R-IMPORTE-MES`),
y la versión vigente cambia **mes a mes** (17 → 22 → 27), que es exactamente lo
que `mart` resuelve y `stg.version_master_vigente` no.

**Sobre las versiones de «Cierre mensual»:** la obra 0696 tiene, en ámbito 8,
**20 versiones de tipo `Cierre mensual`**, 5 `Cuatrimestral`, 2 `ABC` y 1
`Planif Inicial`. Las 20 de cierre **no reemplazan al plan**; la vigente sale de
las otras ocho. El diccionario lo dice en tres sitios distintos y coherentes.

**Veredicto: RESPONDIDA.**

---

## P7 · ¿Cuánto llevamos ejecutado en la obra X a cierre del mes M?

**Herramientas:** `describir_tabla('cierre.v_pbi_cierre_resumen')` → `consultar` (`_meta.v_frescura`) → `consultar`.

**Último cierre disponible de la obra 0696: julio de 2026.**

| Concepto | Ejecutado a origen | Del mes | Previsión final | % s/venta |
|---|---|---|---|---|
| VENTA | 22.360.883,44 | 2.425.044,91 | 51.000.201,59 | 43,84 |
| GASTOS | 25.422.423,11 | 2.555.235,07 | 46.262.791,48 | 113,69 |
| DIRECTOS | 19.457.525,86 | 2.084.091,32 | 36.619.515,12 | 87,02 |
| INDIRECTOS | 3.528.517,86 | 203.297,54 | 4.936.233,09 | 15,78 |
| GENERALES | 2.436.379,39 | 267.846,21 | 4.707.043,27 | 10,90 |
| BENEFICIO | −3.061.539,67 | −130.190,16 | 4.737.410,11 | −13,69 |

**Frescura citada (obligatoria por `R-FRESCURA-MANUAL`):** `build_cierre`
terminó bien el **2026-08-21 23:30:04 UTC**, hace 1,5 h, lote
`20260821T230219Z-0f9fa3`, 16.888 filas, último intento `SUCCESS`. El dato es de
anoche.

Usé `ejecutado_origen` como último valor y **no** lo sumé entre meses
(`R-IMPORTE-MES`, que en `cierre` se llama `ejecutado_mes`/`ejecutado_origen`).
Los porcentajes van contra la VENTA de esa misma columna y ese mismo mes, tal y
como manda la ficha.

**Veredicto: RESPONDIDA.** Es la pregunta mejor servida de las dieciocho: la
ficha explica incluso que `orden_concepto` tiene el valor 2 repetido y no sirve
para ordenar, y que hay que usar `cierre.v_pbi_dim_concepto.orden`.

---

## P8 · ¿Qué obras se desvían más de su master vigente en coste directo?

**Herramientas:** `describir_tabla('mart.fact_seguimiento_categoria')` → `describir_tabla('mart.v_master_vigente_anual')` → `consultar` ×3.

**SQL final** (CD, enero–julio 2026, `importe_mes`, escenarios separados):
```sql
SELECT obra_id, max(codigo_obra), max(nombre_obra),
       sum(importe_mes) FILTER (WHERE escenario='Coste Real')        AS cd_real,
       sum(importe_mes) FILTER (WHERE escenario='Coste Planificado') AS cd_plan,
       sum(importe_mes) FILTER (WHERE escenario='Coste Real')
     - sum(importe_mes) FILTER (WHERE escenario='Coste Planificado') AS desviacion
FROM mart.fact_seguimiento_categoria
WHERE categoria='CD' AND anio=2026 AND anio_mes <= DATE '2026-07-01'
GROUP BY obra_id
HAVING sum(importe_mes) FILTER (WHERE escenario='Coste Planificado') > 0
ORDER BY 6 DESC LIMIT 8;
```

| Obra | CD real | CD planificado | Desviación |
|---|---|---|---|
| 0696 KODAK EL QUINTANAR | 11.373.136,20 | 10.950.884,12 | **+422.252,08** |
| 0678 CAÑOS CARMONA | 3.505.855,60 | 3.179.689,58 | +326.166,02 |
| 0704 SIROCO TOMARES | 2.317.519,25 | 2.108.633,92 | +208.885,33 |
| 0681 CULMIA VILLAVERDE | 555.172,23 | 447.631,16 | +107.541,07 |
| 0705 CEU SAN PABLO TUTOR | 957.936,80 | 853.224,14 | +104.712,66 |

Escenarios separados, ámbitos no mezclados, `importe_mes` y no `importe_origen`
—que en esta tabla está además **doblado en 37 celdas de 8 obras (39,07 M€ de
más)**, defecto que la propia ficha declara con la cifra medida—.

**Veredicto: RESPONDIDA CON DUDA.**

**La duda:** no pude citar **qué versión master rige** cada obra, porque
`mart.v_master_vigente_anual` —uno de los dos objetos esperados por §9— **no se
puede consultar**: ver **H-3**.

---

## P9 · ¿Cuántas obras activas tenemos? *(pregunta trampa)*

**Herramientas:** `describir_tabla('maestro.obras')` → `consultar` ×4.

El diccionario avisa de la trampa que anuncia §9 y la avisa bien
(`R-OBRA-ACTIVA`): *«no uses `stg.obras.activa`… la construye un literal
`TRUE AS activa`. Para el estado real usa `maestro.obras.es_activa`, que se
deriva de `con.fecbaj`»*. Y `R-UNIVERSO-OBRA` obliga a declarar el universo.

Hice las dos cosas. Y entonces:

```sql
SELECT count(*) AS total, count(*) FILTER (WHERE es_activa) AS activas,
       count(fecha_baja) AS con_fecha_baja
FROM maestro.obras;
-- total 918 · activas 918 · con_fecha_baja 0
```

**`maestro.obras.es_activa` vale TRUE en las 918 filas, porque `fecha_baja` está
informada en CERO.** La columna que el diccionario presenta como «la buena» está
tan vacía de significado como la que marca de trampa. Y en el universo del
seguimiento pasa lo mismo: `mart.v_pbi_dim_obra` tiene 582 obras y las 582 dan
«activa».

**Respuesta que puedo dar:** «tenemos **918** obras en el maestro y **582** en el
universo del seguimiento; **de cuántas siguen vivas, el datamart no lo sabe**,
porque el campo del que se deriva está vacío en el 100 % de las filas».

**Veredicto: NO RESPONDIDA.**

**Es el peor hallazgo de la batería y es de manual: el diccionario avisa de una
trampa y a continuación empuja a otra idéntica sin avisar.** La pregunta era
trampa a propósito y el diccionario esquivó la trampa conocida para caer en la
gemela. Ver **H-4**.

---

## P10 · ¿Cuál es el presupuesto de la obra X? *(pregunta trampa)*

**Herramientas:** `describir_tabla('stg.presupuesto')` → `describir_tabla('stg.version_master_vigente')` → `consultar` ×4.

La ficha de `stg.presupuesto` es magistral: marcada NO RECOMENDADA pero
documentada porque *«es la fuente buena para "cuál es el presupuesto de la obra",
que no se responde sumando `stg.plan_mensual`»*, con las dos trampas escritas
antes de la tabla de columnas.

**Master vigente de la obra 0696 (versión 27):**
```sql
SELECT ambito_id, sum(importe) AS coste, sum(importe_oficial) AS venta
FROM stg.presupuesto
WHERE obra_id=2419057 AND ambito_id IN (8,11) AND fase_num=27
GROUP BY 1;
```

| Ámbito | Columna correcta | Importe |
|---|---|---|
| 8 (coste master) | `importe` | **46.280.386,06 €** |
| 11 (venta master) | `importe_oficial` | **51.000.201,59 €** |

**Contraste independiente que cuadra:** la venta master (51.000.201,59 €)
coincide **al céntimo** con `final_importe` del concepto VENTA del cierre de
julio (P7). Dos objetos de dos esquemas distintos, mismo número.

**Las dos trampas, demostradas:**
1. **Sumar sin filtrar versión:** `SUM(importe)` sobre el ámbito 8 sin fijar
   `fase_num` da **1.300.310.803,88 €** contra 46.280.386,06 € reales. **28,1×.**
   Hay 30 versiones conviviendo.
2. **Columna equivocada:** en el ámbito 11, `importe` vale 42.919.180,30 € y
   `importe_oficial` 51.000.201,59 €. Usar la de coste para la venta la
   subestima en **8.081.021,29 € (−15,8 %)**. Y en el ámbito 8 las dos columnas
   valen lo mismo, así que el error **es invisible en coste y solo falsea la
   venta**, que es exactamente lo que la ficha advierte.

También comprobé el «Previsto vivo» (`fase_num = 0`, ámbitos reales): coste
46.281.409,06 € y venta 42.919.180,30 €.

**Veredicto: RESPONDIDA.** Trampa esquivada gracias al diccionario, y no habría
podido esquivarla sin él.

**Fricción menor:** `stg.version_master_vigente` **no tiene `ambito_id`** (una
fila por obra), así que el JOIN natural por `(obra_id, ambito_id, version)` falla
con `column v.ambito_id does not exist`. La ficha lo dice —«resuelve la versión
vigente de forma GLOBAL, una por obra»— pero no dice que por eso no se puede
unir por ámbito. Tuve que sacar la versión del propio hecho.

---

## P11 · Evolución mensual del coste directo de la obra X en el año A *(trampa)*

**Herramientas:** `describir_tabla('mart.fact_seguimiento_mensual')` (ya hecha en P6) → `consultar` ×2.

**Obra 0696, coste directo real, 2026, `importe_mes`:**

| Mes | CD real |
|---|---|
| Ene | 1.054.930,36 |
| Feb | 1.064.463,70 |
| Mar | 1.182.069,31 |
| Abr | 1.564.502,22 |
| May | 2.191.930,45 |
| Jun | 2.231.148,84 |
| Jul | 2.084.091,32 |
| **Total** | **11.373.136,20** |

**La trampa, medida:** `SUM(importe_origen)` sobre el mismo filtro devuelve
**95.652.558,12 €**, es decir **8,4×** el valor correcto. Y en una obra ya
terminada (0655, CD real 2025) el factor llega a **12.993×** (3.829,30 € reales
frente a 49.754.403,02 €), porque hay muchos meses de acumulado y muy poco
movimiento. **La regla `R-IMPORTE-MES` no exagera: es exactamente eso.**

**Veredicto: RESPONDIDA.** Trampa esquivada, y el aviso llegó en el arranque,
antes de escribir nada.

---

## P12 · ¿Qué tenemos en albaranes sin facturar?

**Herramientas:** `describir_tabla('compras.v_pbi_albaranes_sin_facturar')` → `consultar` ×5.

```sql
SELECT tipo_documento, count(*) AS lineas, sum(importe_pendiente_facturar) AS pendiente
FROM compras.v_pbi_albaranes_sin_facturar GROUP BY 1;
```

| Tipo | Líneas | Pendiente |
|---|---|---|
| ALBARAN | 116.485 | **68.724.258.730.537,81 €** |
| PROFORMA | 685 | 1.844.621,12 € |

**Sesenta y ocho billones de euros.** Solo ALBARAN y PROFORMA, como manda la
ficha (las NOTA suman en consumido pero no en pendiente), pero la cifra es
absurda por seis órdenes de magnitud.

**Causa localizada:** **dos líneas** del albarán `AC21/03345` (28-02-2021, obra
0609, AZULEJOS Y PAVIMENTOS ANTERO AYBAR) con `cantidad = 184.493.959.731` e
`importe = 34.361.999.999.898,80 €` cada una. Suman 68.723.999.999.797,60 €, el
99,99999 % del total. Y su espejo: 89.865 líneas con pendiente negativo por
−68.724.246.572.287,35 € en `compras.albaran_lineas`.

**Cifra útil, saneada a mano** (excluyendo las 2 líneas > 10 M€):
**260.575.361,33 €** en 117.168 líneas. **Esa es la respuesta que daría**,
diciendo que he tenido que sanear.

**Veredicto: RESPONDIDA CON DUDA.**

**Lo que falló:** ningún mecanismo del diccionario detuvo esta cifra. Los
**órdenes de magnitud existen** —el propio `_meta.diccionario_contexto` dice que
«existen para que una respuesta absurda se note»— pero (a) **no se sirven en
`contexto_bbdd()`** (H-1) y (b) **solo cubren retenciones**: cuatro entradas, las
cuatro de `retenciones`. No hay ningún orden de magnitud para `compras`, para
`mart` ni para `cierre`. La única razón por la que no di 68 billones por buenos
es que 68 billones es evidentemente absurdo; con un factor de 3 no me habría
enterado.

*Nota: `linea_id` **sí** es único en la vista (117.170 filas / 117.170 valores
distintos), tal y como declara la ficha. Las dos filas gemelas son dos líneas
distintas del mismo albarán, no un fallo de grano.*

---

## P13 · ¿Qué retenciones vencen este trimestre y siguen vivas?

**Herramientas:** `describir_tabla('retenciones.v_pbi_retenciones_vencidas')` → `consultar` ×2.

**Interpretación literal («vencen en Q3-2026 y siguen vivas»), recalculada
sobre `fecha_prevista_devolucion` como manda la ficha:**

| Sentido | Efectos | Importe |
|---|---|---|
| PROVEEDOR | 756 | 1.376.119,92 € |
| CLIENTE | 14 | 83.926,78 € |

**Stock vencido acumulado** (`v_pbi_retenciones_vencidas`, tramos congelados al
build): PROVEEDOR 20.738 efectos / 29.648.796,80 €, de los que **14.234 efectos
y 19.370.872,01 € llevan más de 2 años**; CLIENTE 2.087 efectos /
21.032.031,07 €, con 1.695 efectos y 17.268.601,01 € por encima de dos años.

**Frescura citada:** `retenciones` es de **refresco manual** y —esto lo dice la
propia regla `R-FRESCURA-MANUAL`— **`build-retenciones` no registra paso propio,
así que no aparece en `_meta.v_frescura` y su fecha de build no es consultable
por SQL**. Comprobado: los 8 pasos de `v_frescura` son `apply_grants`,
`build_cierre`, `build_maestros`, `build_mart`, `build_stg`, `ingest_raw`,
`load_excel_aux` y `publicar_diccionario`. Ni `build_compras` ni
`build_retenciones`. **Hay que advertir de que la antigüedad se desconoce**, y
el diccionario me lo dijo antes de que lo descubriera.

Usé `fecha_prevista_devolucion` recalculada y **no** `vencida_sin_liquidar` ni
`dias_desde_vencimiento`, congeladas al día del build.

**Veredicto: RESPONDIDA.** Ejemplo de manual de un diccionario que documenta
su propio punto ciego en lugar de callarlo.

---

## P14 · Las diez partidas con más coste incurrido de la obra X

**Herramientas:** `describir_tabla('compras.v_pbi_partida_coste')` → `consultar`.

**Obra 0696, por `facturado` (neto sin IVA):**

| Partida | Descripción | Facturado |
|---|---|---|
| P4.04.01.03 | FORJ.RET. 25+5 BLOQ. PERDIDOS | 790.462,99 |
| P5.04.01.03 | FORJ.RET. 25+5 BLOQ. PERDIDOS | 757.119,66 |
| P4.04.01.01 | FORJ.RET. 30+5 CASET. RECUP. | 469.267,00 |
| P5.04.01.02 | FORJ.RET. 30+5 BLOQ. PERDIDOS | 461.542,84 |
| P5.04.01.01 | FORJ.RET. 30+5 CASET. RECUP. | 426.352,72 |
| P4.08.01 | FACHADA VENTILADA PIEDRA CALIZA | 405.615,93 |
| P4.04.01.04 | H.ARM. HA-25/F/20/XC1 LOSAS PLANAS | 385.982,98 |
| CI.03A.3 | ANDAMIOS-PLATAFORMAS | 352.476,19 |
| P4.04.01.02 | FORJ.RET. 30+5 BLOQ. PERDIDOS | 351.143,56 |
| P5.04.01.04 | H.ARM. HA-25/F/20/XC1 LOSAS PLANAS | 338.776,88 |

**Advertencias que el diccionario obliga a dar y di:** `compras` **no filtra por
`stg.obras`** y puede traer obras administrativas; solo entran líneas con partida
informada, así que el total es menor que el de `fact_compras_linea`; los NULL de
`facturado` son «no hubo facturas», no cero, y un `WHERE facturado > 0` los
descarta en silencio; y **el puente plan-vs-incurrido por `partida_id` no existe
todavía** (F-039), declarado en la relación N:N de la ficha.

**Veredicto: RESPONDIDA.**

---

## P15 · ¿De cuándo es el dato que me estás dando?

**Herramientas:** `describir_tabla('_meta.v_frescura')` → `describir_tabla('_meta.diccionario_publicacion')` → `consultar` ×2.

**Último OK y último intento, por separado** (`SELECT * FROM _meta.v_frescura`):

| Paso | Último OK (UTC) | Horas | Último intento | Estado |
|---|---|---|---|---|
| publicar_diccionario | 2026-08-22 00:02:21 | 0,96 | 00:02:20 | SUCCESS |
| build_cierre | 2026-08-21 23:30:04 | 1,49 | 23:02:19 | SUCCESS |
| build_maestros | 2026-08-21 22:49:28 | 2,17 | 22:49:17 | SUCCESS |
| apply_grants | 2026-08-21 04:40:50 | 20,31 | 04:40:50 | SUCCESS |
| build_mart | 2026-08-21 04:40:50 | 20,31 | 04:18:55 | SUCCESS |
| build_stg | 2026-08-21 04:18:54 | 20,68 | 02:28:24 | SUCCESS |
| load_excel_aux | 2026-08-21 02:28:24 | 22,52 | 02:28:21 | SUCCESS |
| ingest_raw | 2026-08-21 02:28:21 | 22,52 | 02:00:22 | SUCCESS |

**Versión del diccionario publicado** (`_meta.diccionario_publicacion`, fila
única con `CHECK (id = 1)`): versión **6**, hash `52f107235bc623df…`, publicada
2026-08-22 00:02:20 UTC, lote `20260822T000220Z-94762c`, **103 objetos, 13
reglas, 798 columnas, cobertura 100,00 %**.

**Y lo que hay que decir además:** `compras` y `retenciones` **no tienen paso en
`v_frescura`**, así que de esos dos esquemas la antigüedad se desconoce.

**Veredicto: RESPONDIDA.** R15 y R16 pasan: último OK y último intento llegan
separados y la versión publicada se responde sin salir de SQL.

---

## P16 · ¿Cuánto le hemos comprado al proveedor P en toda la empresa este año? *(trampa)*

Proveedor P = **ARMADURAS DE ACERO FERRALIA, S.L.** (`proveedor_id` 686288).

**Herramientas:** `buscar_valor` (falló, ver abajo) → `describir_tabla('maestro.proveedores')` → `consultar` ×3.

**Desglose por tipo de documento, 2026:**

| tipo_doc | Líneas | Importe |
|---|---|---|
| FACTURA | 378 | **1.435.614,40 €** |
| CONTRATO | 153 | 1.321.682,95 € |
| ALBARAN | 436 | 905.888,52 € |
| PROFORMA | 251 | 583.973,50 € |

**Respuesta: 1.435.614,40 € facturado neto sin IVA en 2026** (a fecha del último
documento cargado, 2026-08-20).

**Las tres trampas, esquivadas y medidas:**
1. **No filtrar `tipo_doc`** daría 4.247.159,37 €, es decir **2,96×** la cifra
   real. Contratado, albaranado y facturado son tres momentos del mismo coste
   (`R-COMPRAS-TIPO-DOC`).
2. **`linea_id` no es único** (`R-LINEA-ID-NO-UNICA`): conté con la clave real
   `(tipo_doc, linea_id)`. En este caso concreto ambos recuentos dan 1.218, pero
   la clave correcta es la del par.
3. **No comparar con `maestro.proveedores_obra.importe_contratado`**
   (`R-COMPRAS-SIN-IVA`): ese proveedor tiene ahí 8.925.184,68 €, **con IVA y
   del histórico completo**. Compararlo con el facturado del año daría una
   «desviación» inventada.

**Veredicto: RESPONDIDA.**

**Fricción:** `buscar_valor('maestro.proveedores','nombre_proveedor', …)` falló
con `La columna 'nombre_proveedor' no existe`. La columna se llama `nombre` a
secas. Es culpa mía por no describir la tabla antes —el propio pie de página de
cada ficha lo recuerda—, pero merece nota: **casi todas las tablas usan
`proveedor_nombre` / `nombre_obra` y `maestro.proveedores` usa `nombre` y
`codigo`**, sin el prefijo. La incoherencia de nomenclatura entre el maestro y
el resto invita a ese error, y el mensaje de error del servidor fue claro y
recuperable en un intento.

---

## P17 · ¿Quiénes son nuestros diez mayores clientes?

**Herramientas:** `describir_tabla('maestro.obras')` → `consultar` ×2.

**Respuesta correcta: no se puede.** La ficha de `maestro.obras` lo dice sin
rodeos en `nombre_cliente`: *«Es lo ÚNICO que el datamart sabe del cliente: la
tabla de clientes de Sigrid no se ingiere, así que no hay CIF, ni dirección, ni
facturación de cliente. Es F-040»*. Y el nombre viene de `con.res`, exactamente
como anticipa §9.

**Además no hay venta a cliente en ningún sitio**: `compras` es solo compra a
proveedor, y `retenciones.v_src_lineas_venta` está **siempre vacía en Ruesma**
(la ficha lo declara y por eso la marca NO RECOMENDADA). Sin facturación de
venta no hay ranking de clientes posible.

**Lo único que sí puedo dar, y lo daría diciendo qué es:** número de obras por
cliente — AHORRAMAS 64, DIA 62, GRUPO ZENA PIZZA 43, JOHN DEERE IBÉRICA 14,
F.E.I.S.A. 14, COMUNIDAD AUTÓNOMA DE MADRID 13. **Y con una advertencia gorda:
432 de las 918 obras (47 %) no tienen cliente resuelto** (`cliente_id = 0`), así
que hasta ese recuento es parcial. Ese 47 % **no lo dice el diccionario**; lo
tuve que medir yo.

**Veredicto: RECHAZADA CORRECTAMENTE.**

---

## P18 · ¿Qué obras están mal configuradas, sin planificado en algún mes?

**Herramientas:** `describir_tabla('mart.v_master_versiones_tipadas')` → `consultar` ×3.

**SQL final** (obras con coste real en 2026 y meses sin ninguna fila de
planificado):

| Obra | Meses con real | **Meses sin plan** | Coste real 2026 |
|---|---|---|---|
| 0677 MIRASIERRA | 7 | **4** | 3.241.732,17 |
| 0713 DAVID LLOYD TOMARES | 7 | 2 | 2.735.951,84 |
| 0710 RES. SAN VICENTE DEL RASPEIG | 7 | 1 | 2.077.174,76 |
| 0712 AHORRAMAS TALAVERA | 7 | 2 | 1.419.681,37 |
| 0705 CEU SAN PABLO TUTOR | 7 | 1 | 1.282.009,78 |
| 0718 IFEMA H07 | 3 | **3** | 912.318,90 |
| 0681 CULMIA VILLAVERDE | 7 | **5** | 799.029,30 |
| 0672 CULMIA CARABANCHEL | 7 | **5** (+1 mes con plan a cero) | 572.307,47 |

**El síntoma reconocido, tal y como pide §9:** el diccionario explica por qué
pasa —una obra cuyas únicas versiones de un tramo son de tipo `Cierre mensual`
se queda **sin plan vigente** en esos meses, porque los cierres no reemplazan al
plan— y también que **un mes sin fila de la versión vigente da importes 0 sin
dejar de ser la vigente**. Las dos lecturas están separadas en el resultado:
`meses_sin_fila_plan` frente a `meses_con_plan_a_cero` (0672 tiene de las dos).

**Veredicto: RESPONDIDA.**

**Limitación:** quería dar además el recuento de obras cuyas únicas versiones
master son de cierre. `mart.v_master_versiones_tipadas` **agotó el tiempo
(30 s)** al agregarla sobre todas las obras; filtrada a una sola obra tarda
**24 s**. Es usable para una obra, no para un barrido (ver H-3).

---

## Hallazgos: qué falla y por qué

Ordenados por gravedad. Los cinco primeros son los que un usuario de negocio
sufriría.

### H-1 · `contexto_bbdd()` no sirve tres de los cinco bloques que `_meta` publica — **BLOQUEANTE**

`_meta.diccionario_contexto` contiene **24 filas** en cinco bloques:
`convenciones` (5), `ejes` (3), `esquemas` (9), `ordenes_de_magnitud` (4) y
`ocultar` (3). La llamada obligatoria de arranque, `contexto_bbdd()`, sirve las
**13 reglas** y el **resumen por esquema**, y **nada más**. No llegan:

- **`ordenes_de_magnitud`** — la defensa contra cifras absurdas. Su propia ficha
  dice que existen «para que una respuesta absurda se note» y que son «los que
  evitan que se repita el 38,9 M€ en una sola obra». **No se sirven.** En P12
  di con una cifra de 68,7 billones de euros y ninguna barrera saltó.
- **`ejes`** — los literales exactos de `escenario` (`Coste Real`,
  `Coste Planificado`, `Venta Real`, `Venta Planificada`) y los ámbitos de
  Sigrid de los que sale cada uno. Los necesité en P6, P8 y P11. Los conseguí
  porque `describir_tabla` los repite en `valores posibles`, pero un agente que
  escriba SQL después del contexto y sin describir la tabla los inventaría.
- **`convenciones`** — moneda, IVA, formato de fechas de Sigrid, y que los
  timestamps de `_meta` son UTC sin zona.

La ficha de la tabla dice, con su propia fecha: *«Nació el 2026-08-22 como
enmienda del contrato. Hasta entonces `_meta` publicaba los objetos y las reglas
pero no el resto del bloque global, así que un MCP que leyera de la base habría
respondido PEOR que el prototipo local»*. **La enmienda está publicada en la base
pero el servidor no la consume**: el diccionario cumplió y el consumidor no se
enteró. Desde la silla del usuario el efecto es idéntico al de no haberla
escrito.

*Dos detalles menores en la misma tabla:* declara «~21 filas» y tiene 24; y el
valor `ocultar` del `bloque` no está en la lista de `valores posibles` de su
propia columna.

### H-2 · `retenciones.movimientos.obra_id` NO une con `maestro.obras.obra_id`, y el diccionario declara esa relación — **BLOQUEANTE**

La ficha declara la relación `obra_id -> maestro.obras.obra_id (N:1)` *«Para el
nombre y el cliente de la obra»*. Medido:

```sql
SELECT count(DISTINCT m.obra_id) AS ret_obras,
       count(DISTINCT o.obra_id) AS casan_en_maestro
FROM retenciones.movimientos m
LEFT JOIN maestro.obras o ON o.obra_id = m.obra_id
WHERE m.sentido='PROVEEDOR' AND m.obra_id IS NOT NULL;
-- ret_obras 256 · casan_en_maestro 0
```

**Cero de 256.** El caso concreto: la obra 0655 «HOTEL FLORIDA NORTE» es
`obra_id = 1990274` en `retenciones` y `obra_id = 1990273` en `maestro.obras`,
en `compras.contratos` y en `mart`. La 0696 es 2419059 en retenciones y 2419057
en el resto.

**La causa está insinuada pero mal contada.** La ficha dice que `obra_id` se
resuelve «por el CENTRO DE COSTE del efecto, **que en Ruesma coincide con la
obra** en torno al 98 % de los casos». Lo que ocurre es que el centro de coste
es una **entidad distinta con su propio `ide`**, contigua a la de la obra. No
«coincide con la obra»: **apunta a la obra pero no es su identificador**. La
frase induce exactamente el error de unir por `obra_id`.

**Consecuencia práctica:** un `INNER JOIN` devuelve **cero filas** y un `LEFT
JOIN` devuelve **todo a NULL**, en silencio, sin error. Cualquier pregunta que
cruce retenciones con obras —«retenciones de las obras del cliente X», «obras
activas con retención viva»— sale mal. Lo que hay que usar es `codigo_obra`, que
sí es común, y **eso no está escrito en ninguna parte**.

### H-3 · `mart.v_master_vigente_anual` no se puede consultar: agota el tiempo con `LIMIT 5` — **BLOQUEANTE**

```sql
SELECT * FROM mart.v_master_vigente_anual LIMIT 5;
-- ERROR [CONEXION]: canceling statement due to statement timeout (30 s)
```

Ni siquiera filtrada a una obra y un año responde. Es **objeto esperado de P8**
en §9, está en la superficie recomendada (**no** lleva
`[NO RECOMENDADO PARA CONSULTA]`), y su ficha la anuncia como la que responde
«qué versión de plan rige en la obra X para 2025». **No responde nada.**
Su hermana `mart.v_master_versiones_tipadas` tarda **24 s** para una sola obra y
agota el tiempo si se agrega sobre todas.

Esto abre un agujero de categoría en el diccionario: **no hay ningún campo de
coste**. Ni un `[LENTO]`, ni un «filtra siempre por obra», ni una nota de que
`v_pbi_partida_coste` tarda 13 s o que `fact_compras_linea` con
`count(DISTINCT documento_id)` no cabe en la ventana. En una base compartida con
dos aplicaciones en producción, un agente que no sabe qué es caro lanza consultas
que se cortan a los 30 s —me pasó **cinco veces** en esta batería— o, peor,
consultas que sí terminan pero molestan.

### H-4 · La columna que el diccionario recomienda para «obra activa» está tan vacía como la que marca de trampa — **BLOQUEANTE**

`R-OBRA-ACTIVA` es una regla dura, bloqueante y bien escrita: no uses
`stg.obras.activa`, que es un literal `TRUE`. Y a continuación manda a
`maestro.obras.es_activa`, «que se deriva de `con.fecbaj`».

**Las 918 filas de `maestro.obras` tienen `fecha_baja` a NULL, luego `es_activa`
es TRUE en las 918.** El resultado es indistinguible de la trampa que la regla
denuncia.

Lo grave no es que el dato de origen esté vacío —eso es de Sigrid—, es que **el
diccionario afirma que esa columna sirve, y no sirve**. Una regla que desvía de
una trampa hacia otra idéntica es peor que no tener regla: da confianza
injustificada. La regla debería decir «hoy `fecha_baja` está informada en 0 de
918 obras, así que el estado de la obra **no se puede responder** con el
datamart; para el estado real, `cierre.v_pbi_cierre_cabecera`». La regla ya
menciona esa vista como tercera opción, pero de pasada y sin decir que las dos
primeras están rotas.

### H-5 · «`compras.contratos.descripcion` suele nombrar el oficio»: falso, y es el objeto que §9 espera para P3 — **GRAVE**

5 de 18.879 contratos (**0,03 %**) contienen «fontan»; 16.513 (**87,5 %**)
tienen como descripción el nombre del proveedor. La ficha afirma lo contrario y
pone como ejemplo un literal («FONTANERIA Y SANEAMIENTO») que casi no existe en
la base. Seguirla lleva a responder «no hay contratos de fontanería en esa obra»,
que es una respuesta **incorrecta con aspecto de correcta**.

La heurística que sí funciona es `compras.fact_compras_linea.descripcion`, cuya
ficha, por cierto, lo dice bien: *«Es lo único que hoy permite adivinar el oficio
… y es una heurística, no una clasificación»*. **Las dos fichas se contradicen y
la equivocada es la que §9 designa como objeto esperado.**

### H-6 · Anomalía de datos de 68,7 billones de euros que ningún control detiene — **GRAVE**

Dos líneas del albarán `AC21/03345` (2021, obra 0609) con
`cantidad = 184.493.959.731` e `importe = 34.361.999.999.898,80 €` cada una
inflan `compras.v_pbi_albaranes_sin_facturar` de **260,6 M€** (cifra plausible) a
**68,7 billones**. Con su espejo negativo en `compras.albaran_lineas`.

Es un problema de calidad del dato de origen, no del diccionario. Pero el
diccionario **se atribuye explícitamente la misión de que eso se note** y no la
cumple: los órdenes de magnitud no se sirven (H-1) y, aunque se sirvieran, **solo
cubren `retenciones`**. Cuatro entradas, las cuatro del mismo esquema. Faltan
para compras, mart y cierre, que es donde están los importes grandes.

### H-7 · Dos cifras del mismo concepto que difieren 160× sin explicación suficiente — **MEDIO**

Obra 0655, «entregado y no facturado»: **91.410,95 €** según
`compras.v_pbi_contrato_consumo.importe_albaranado_sin_facturar` y
**14.580.976,11 €** según `compras.v_pbi_albaranes_sin_facturar` (2.910 líneas,
ninguna anómala). La ficha avisa de que «pueden no coincidir» y da como motivo el
filtro de tipo de documento —lo que explicaría un margen por NOTA y OTRO, no un
factor 160—. La causa real (una cuenta lo que cuelga de contrato y la otra todo)
no está escrita. El aviso existe pero **minimiza** la diferencia, que es una
forma sutil de inducir error.

### H-8 · La marca de «factura repartida entre varias obras» nunca se dispara — **MENOR**

`retenciones.movimientos.num_obras_documento > 1` junto a `obra_id IS NULL` es,
según la ficha, la señal de una factura que toca varias obras. En sentido
PROVEEDOR los 533 efectos sin obra tienen ese campo a **0**, los 533. La ficha
advierte del cero solo para el sentido CLIENTE.

### H-9 · `compras.contratos` promete un importe que no tiene — **MENOR**

La descripción del objeto dice «a quién, para qué obra, **por cuánto** y de qué
comparativo salió». No hay ninguna columna de importe en la tabla. Escribí
`importe_contrato` y el servidor lo rechazó limpiamente
(`column "importe_contrato" does not exist`, con sugerencia de usar
`describir_tabla`). Recuperable en un intento, pero la descripción invita al
error. El importe está en `compras.v_pbi_contrato_consumo.importe_contratado`.

### H-10 · `stg.version_master_vigente` no tiene `ambito_id` — **MENOR**

Grano de una fila por obra, así que el JOIN natural
`(obra_id, ambito_id, version)` falla. La ficha dice que la resolución es
«global» pero no advierte de que por eso no se puede unir por ámbito.

### H-11 · Nomenclatura incoherente en `maestro.proveedores` — **MENOR**

Todo el datamart usa `proveedor_nombre`, `nombre_obra`, `codigo_obra`.
`maestro.proveedores` usa `nombre` y `codigo` a secas. `buscar_valor` con el
nombre esperado falla.

### H-12 · Vacíos de negocio que ningún objeto declara — **MENOR pero acumulativo**

Cosas que un usuario de negocio necesita y tuve que medir yo porque el
diccionario no las dice:

- **Proveedores intragrupo**: el nº 1 del ranking de compras es la propia
  empresa (P1). Nada explica qué es ni si debe excluirse.
- **432 de 918 obras (47 %) sin cliente resuelto** (`cliente_id = 0`). La ficha
  explica el mecanismo (`cliente_id` sin `NULLIF`, hay que escribir `= 0`, no
  `IS NULL`) —muy bien— pero **no dice el volumen**, que es lo que decide si un
  recuento por cliente es publicable.
- **Dos obras distintas con el mismo `codigo_obra` `0696`** (`obra_id` 2419057 y
  2515321) en `maestro.obras`. Filtrar por código —que es lo que hace un usuario,
  porque el `ide` no lo conoce nadie— puede mezclarlas. Ninguna ficha lo advierte,
  y varias animan a usar `codigo_obra` como si fuera identificador.

---

## Lo que el diccionario hizo bien, y conviene no perderlo

Para que el balance sea justo, porque los aciertos son muchos y varios son
excepcionales:

1. **Las 13 reglas duras llegan antes de la primera consulta**, con orden y
   motivo. `R-IMPORTE-MES` me ahorró un error de **8,4×** en P11 y de
   **12.993×** en la obra 0655. `R-COMPRAS-TIPO-DOC`, uno de **2,96×** en P16.
   `R-VERSION-MASTER`, uno de **28,1×** en P10.
2. **El grano declarado es el real, no el teórico.** `v_pbi_proveedor_obra` dice
   que su clave son **seis** columnas y no tres, y por qué. `v_pbi_partida_coste`
   dice cinco y no dos. Eso evita fan-outs que nadie ve venir.
3. **Los defectos abiertos del propio build están escritos con la cifra
   medida**: 8.778 combinaciones duplicadas en 9 obras del fact mensual; 37
   celdas de 8 obras con `importe_origen` doblado por **39,07 M€** en el
   preagregado por categoría; y, crucial, **medida a medida** cuál está bien y
   cuál mal («`importe_mes` está bien, 200 de 200 series; `importe_origen` está
   doblado»). Un diccionario que denuncia a su propio ETL es exactamente lo que
   hace falta.
4. **El significado del NULL, columna a columna**, y distinguiendo NULL real de
   cadena vacía y de cero. `razon_social` nunca es NULL sino cadena vacía;
   `cliente_id` sin cliente vale 0 y no NULL; `facturado` NULL es «no hubo
   facturas» y un `WHERE facturado > 0` lo descarta en silencio. Esto es lo que
   separa un diccionario de un `\d+`.
5. **Los objetos NO RECOMENDADOS traen el motivo y la alternativa**, no solo la
   prohibición. `stg.presupuesto` está marcada NO RECOMENDADA **y** documentada
   entera porque es la única fuente buena para el presupuesto: esa tensión
   resuelta con criterio es lo que permitió responder P10 bien.
6. **El punto ciego de frescura está declarado en vez de disimulado**:
   `build_compras` y `build_retenciones` no registran paso, no salen en
   `v_frescura`, y hay que advertir de que la antigüedad se desconoce. Lo dice la
   regla, antes de que yo lo descubriera.
7. **Los mensajes de error del servidor son accionables**: los cuatro errores de
   columna inexistente me dijeron qué hacer y se recuperaron en un intento.
8. **Cuadres cruzados que salen al céntimo**: la venta master de P10
   (51.000.201,59 €) contra la previsión de venta del cierre de P7; el total de
   `v_pbi_proveedor_obra` contra el de `fact_compras_linea` con la diferencia
   explicada de 406,56 €. Los órdenes de magnitud de retenciones (34,7 M€ /
   25.124 efectos) contra lo medido (35,28 M€ / 25.392). Coherencia real.

---

## Recuento por veredicto

| Veredicto | Nº | Preguntas |
|---|---|---|
| **RESPONDIDA** | **11** | P1, P2, P6, P7, P10, P11, P13, P14, P15, P16, P18 |
| **RESPONDIDA CON DUDA** | **4** | P3, P5, P8, P12 |
| **NO RESPONDIDA** | **1** | P9 |
| **RECHAZADA CORRECTAMENTE** | **2** | P4, P17 |
| **Total** | **18** | |

### Contra el criterio de éxito que §9 declara

> *«el diccionario está completo cuando las 13 se responden bien y las 5
> restantes se contestan con un "no puedo, y este es el motivo" correcto»*

**Las 13 respondibles** (P1, P2, P6, P7, P8, P9, P10, P11, P12, P13, P15, P16,
P18): **10 bien**, 2 con duda (P8, P12) y **1 fallada (P9)**.

**Las 3 parciales**: P14 bien y con las advertencias exigidas; P5 con la duda de
H-7; **P3 mal**, porque el objeto que §9 designa contiene una afirmación falsa.

**Las 2 imposibles** (P4, P17): **las dos rechazadas correctamente y con el
motivo exacto**, incluida la feature que lo desbloquearía. Esta mitad del
criterio se cumple sin reservas.

### Veredicto global

**El diccionario no está completo, pero le falta poco y lo que le falta es
identificable.** De los 12 hallazgos, **cuatro son bloqueantes** y **ninguno
requiere reescribir el diccionario**: dos son afirmaciones falsas que hay que
corregir (H-2 la relación de retenciones, H-4 la columna de obra activa, H-5 el
oficio en la descripción del contrato), uno es una enmienda publicada que el
consumidor no lee (H-1) y otro es una categoría entera que falta —el coste de
consulta— más un objeto roto (H-3).

Dicho de otro modo: **el diccionario acierta en todo lo que se propuso
documentar y falla en tres sitios donde afirma algo que la base contradice.** Y
un diccionario que se equivoca afirmando es más peligroso que uno que calla,
porque su valor entero descansa en que uno pueda fiarse sin comprobar. En P9 me
fié y respondí mal; en P3 me fié y habría respondido mal si no hubiera
comprobado.

Las tres afirmaciones falsas se arreglan con tres ediciones de texto. La
enmienda no consumida se arregla en el prototipo MCP. El coste de consulta es la
única categoría nueva, y bastaría con una marca `[LENTO]` y una nota de
«filtra siempre por obra» en los cinco objetos que la necesitan.

---

## Anexo · Sobre la ejecución

- **Solo lectura**, siempre. Rol `mcp_sigrid_dm_ro`, sin escrituras, sin
  `build-*`, sin tocar permisos ni firewall. No hizo falta ninguna regla nueva:
  la conexión funcionó a la primera.
- **Cinco consultas se cortaron por el `statement_timeout` de 30 s** y se
  anotaron como tales: el ranking de proveedores con `count(DISTINCT
  documento_id)`, dos sobre `mart.v_master_vigente_anual` (incluso con
  `LIMIT 5`), una sobre `mart.v_master_versiones_tipadas` agregada, y una que
  unía el hecho por categoría con la vista de master vigente. Se reescribieron
  más baratas o se declararon no respondibles. Ninguna se reintentó en bucle.
- **Camino seguido en todas las preguntas:** `contexto_bbdd()` una vez al
  principio → `listar_tablas` → `describir_tabla` **antes** de escribir SQL
  sobre cualquier objeto → `consultar`. `buscar_valor` se usó para resolver
  nombres propios (obras y proveedores).
- **No se leyó nada del repositorio `datamart-seg-anual`** salvo la sección §9
  del fichero de preguntas. Todo el conocimiento del modelo salió del MCP.
