<!-- progress/explore_F-042.md -->
# F-042 · La evidencia: qué obras, qué problema y cuánto dinero

> **Medido el 2026-08-28 contra la base real** (`sigrid_dm` en
> `psql-albaranes-rs9k2`), **en solo lectura**: todas las consultas se
> ejecutaron con `default_transaction_read_only = on` y terminaron en
> `ROLLBACK`. No se escribió ni una fila.
>
> El dato que se mide es el de la **nocturna del 2026-08-28**: `build_mart`
> terminó en `SUCCESS` a las 04:56 UTC con 5.330.792 filas
> (`_meta.v_frescura`, consulta **Q14**). No hay ningún build a medias por medio.
>
> Este documento **no es la spec**. Es lo que el humano pidió ver antes de que
> se escriba: las obras con nombre, el problema exacto y el dinero, para
> contrastarlo con lo que él sabe de cada obra.

---

## 1. Lo primero: los conjuntos NO son el mismo, y están encajados

La ficha maneja tres números —22 obras, 9 obras, 8 obras— que miden cosas
distintas. Medidos hoy:

| Conjunto | Obras | Qué significa | Consulta |
|---|---|---|---|
| **A · Fases que chocan** | **22** | Tienen dos fases que Sigrid guarda con el mismo `ano` y el mismo `mes`. Es la CAUSA. | Q2 |
| **B · Filas duplicadas en el fact** | **9** | De esas 22, las que además tienen presupuesto en las dos fases. Son las que producen las 8.778 claves duplicadas. | Q3 |
| **C · Con dinero mal publicado** | **7** | De esas 9, las que además tienen importe distinto de cero en las dos fases. | Q9 |

**Están estrictamente encajados: C ⊂ B ⊂ A.** Ninguna obra está en un conjunto
sin estar en los anteriores.

Las **13 obras** que están en A pero no en B no producen ningún duplicado
porque una de las dos fases **no tiene ni una línea de presupuesto** (Q4): son
fases creadas en Sigrid que nunca se valoraron.

Las **2 obras** que están en B pero no en C —**0433** y **0606**— sí duplican
filas, pero la fila gemela lleva **importe cero**, así que la suma no se
inmuta. Sobre **0606 hay que insistir porque es la obra más grande de todo el
lío por número de filas (3.336 claves duplicadas, el 38 % del total) y su
error en euros es CERO.** Cualquier medida que la cuente como obra afectada
está inflada.

### La comprobación de unicidad, hoy

`8.778` claves duplicadas, `17.556` filas, **exactamente el mismo número que el
2026-08-21** (Q1). El defecto es **estable**, no ha crecido ni se ha movido con
las nocturnas de estos siete días.

---

## 2. Las 22 obras, con nombre y código

Ordenadas por año. La columna **conjunto** dice hasta dónde llega cada una.

| Código | Obra | Mes en conflicto | Las dos fases, como se llaman en Sigrid | Conjunto |
|---|---|---|---|---|
| **0246** | C.R.A. EL ENCINAR, OTERO DE HERREROS | jun-2010 | 12 «Junio 2010» + 13 «**AGOSTO 2010**» | **C** |
| **0310** | O.C. CASETA BOMBAS, DEPÓSITO PCI - J.DEERE | may-2011 | 3 «Mayo 2011» + 4 «Mayo 2011» | **C** |
| 0422 | DOMINO'S PIZZA CL SALVADOR MADARIAGA, A CORUÑA | sep-2014 | 1 «Septiembre 2014» + 2 «Septiembre 2014» | A |
| 0425 | DOMINO'S PIZZA AVDA. FINISTERRE (A CORUÑA) | oct-2014 | 1 «Octubre 2014» + 2 «Octubre 2014-2» | A |
| **0433** | DOMINO'S PIZZA EN PALMA DE MALLORCA | nov-2014 | 1 «Noviembre 2014» + 2 «Noviembre 2014 - 2» | **B** (0 €) |
| 0435 | DOMINO'S PIZZA EN AVDA VALLADOLID, PALENCIA | nov-2014 | 1 «Noviembre 2014» + 2 «Noviembre 2014 - 2» | A |
| **0462** | REFUERZO E IMPERM. TERRAZAS COLEGIO RETAMAR | dic-2015 | 6 «Diciembre 2015» + 7 «**Diciembre 2015-Enero-16**» | **C** |
| 0464 | DOMINO'S PIZZA CASTELLÓ | sep-2015 | 2 «Septiembre 2015» + 3 «Septiembre 2015-2» | A |
| **0471** | AHORRAMAS C/ QUINTANAPALLA, LAS TABLAS | mar-2016 **y** abr-2016 | 5+6 «Marzo 2016-1/-2» y 7+8 «Abril 2016-1/-2» | **C** |
| 0472 | DOMINO'S PIZZA EN AVILÉS | nov-2015 | 1 «Noviembre 2015» + 2 «Noviembre 2015(2)» | A |
| 0473 | DOMINO'S PIZZA C/ MIRACRUZ, SAN SEBASTIÁN | nov-2015 | 1 «Noviembre 2015» + 2 «Noviembre 2015» | A |
| **0499** | NUEVO EDIFICIO CENTRO UNIVERSITARIO VILLANUEVA | ene-2018 **y** feb-2018 | 18+19 «Enero 2018-1/-2» y 20+21 «Febrero 2018-1/-2» | **C** |
| 0505 | DOMINOS PIZZA EN BENIDORM | ago-2016 | 2 «Agosto 2016 (1)» + 3 «Agosto 2016 (2)» | A |
| 0509 | DOMINOS PIZZA EN ALFAFAR (VALENCIA) | oct-2016 | 2 «Octubre 2016» + 3 «Octubre 2016» | A |
| 0514 | DOMINOS PIZZA EN EL EJIDO (ALMERÍA) | nov-2016 | 2 «Noviembre 2016 (1)» + 3 «**Diciembre 2016**» | A |
| 0515 | DOMINOS PIZZA EN PRETER (ALICANTE) | dic-2016 | 3 «Diciembre 2016 (2)» + 4 «**Marzo 2017**» | A |
| 0516 | DOMINOS PIZZA EN HUESCA | nov-2016 | 2 «Noviembre 2016 (1)» + 3 «**Noviembre-Diciembre 2016**» | A |
| 0521 | DOMINOS PIZZA EN AVDA. LA PESETA - CARABANCHEL | dic-2016 | 1 «Diciembre 2016-1» + 2 «Diciembre 2016-2» | A |
| **0545** | ADECUACIÓN ZONA ADMINISTRATIVA NAVE 01-J. DEERE | dic-2017 | 5 «Diciembre 2017» + 6 «DICIEMBRE-17(2)» | **C** |
| 0559 | DOMINO'S PIZZA EN VALLADOLID (ABR) | dic-2017 | 1 «Diciembre» + 2 «Diciembre 2017» | A |
| **0571** | 28 VIVIENDAS PLAZA DEL CAMPILLO MUNDO NUEVO, 2 | may-2020 | 21 «**Enero 2020-Abril 2020**» + 22 «**Agosto 2020**» | **C** |
| **0606** | PARQUE TEMÁTICO PUY DU FOU - LOTE 7 (TOLEDO) | feb-2021 | 14 «Febrero 2021» + 16 «**Mayo 2021**» | **B** (0 €) |

*(Q2 para la lista y las fases; Q3 para el conjunto B; Q9 para el C.)*

**Doce de las veintidós son Domino's Pizza.** Obras pequeñas, de un mes o dos,
en las que el jefe de obra cerró dos veces dentro del mismo mes. Ninguna llega
al conjunto C: son cortas y una de las dos fases suele estar vacía.

---

## 3. El problema exacto: **hay DOS patrones, no uno**

La ficha pone como ejemplo la obra 584748 (**0246**), fase 13 «AGOSTO 2010» con
`mes = 6`. **Ese patrón NO se repite en todas.** Contra la base salen dos, y se
distinguen con una pregunta sencilla: **¿la fase TERMINA dentro del mes que
declara?** (Q2, columna `fin_cuadra_con_mes`).

### Patrón 1 · «Dos cierres dentro del mismo mes» — 14 obras, 16 colisiones

Las dos fases **empiezan y acaban dentro del mes declarado**. Es el corte por
quincenas: del 1 al 15 y del 16 a fin de mes.

> **0499 · VILLANUEVA**, enero 2018:
> fase 18 «Enero 2018-1» → 01-ene a 15-ene, `ano=2018 mes=1`
> fase 19 «Enero 2018-2» → 16-ene a 31-ene, `ano=2018 mes=1`
> Las dos caen en `anio_mes = 2018-01-01`.

Aquí **el `mes` de Sigrid es correcto en las dos**. Lo que pasa es que el mes
tiene dos cierres y el datamart solo tiene sitio para uno.

Un caso dentro de este patrón merece mirarse aparte: **0545 (J. DEERE)**, cuyas
fases 5 «Diciembre 2017» y 6 «DICIEMBRE-17(2)» tienen **exactamente las mismas
fechas** (01-dic-2017 a 31-dic-2017). No son dos quincenas: son dos cierres del
mismo periodo. Es el mejor candidato de todos a «error de configuración».

### Patrón 2 · «La fase abarca varios meses y el `mes` se quedó en el de arranque» — 8 obras, 8 colisiones

La segunda fase **termina en un mes posterior** al que declara, y su nombre lo
dice. `ano`/`mes` se quedaron en el mes en que la fase empezó, que es el mismo
mes que ya ocupaba la fase anterior.

> **0246 · EL ENCINAR** (el ejemplo de la ficha):
> fase 12 «Junio 2010» → 01-jun a 15-jun, `mes = 6` ✔ cuadra
> fase 13 «AGOSTO 2010» → 16-jun a **31-ago**, `mes = 6` ✘ **no cuadra**

Obras del patrón 2: **0246, 0462, 0464, 0514, 0515, 0516, 0571, 0606.**

**El patrón 2 tiene una consecuencia que no está en la ficha: faltan meses.**
Si la fase que cubre junio–agosto se archiva como «junio», julio y agosto
**no existen en el datamart**. Comprobado (Q10):

| Obra | Meses que hay en el fact | Meses que faltan |
|---|---|---|
| **0246** | abr-2010, may-2010, **jun-2010**, sep-2010 | jul y ago 2010 |
| **0571** | …, **may-2020**, sep-2020 | jun, jul y ago 2020 |

Y **0571 es el caso extremo del patrón 2: NINGUNA de sus dos fases cuadra.** La
21 se llama «Enero 2020-Abril 2020» y acaba el 30-abr; la 22 se llama «Agosto
2020» y acaba el 31-ago. Ninguna de las dos es de mayo, y sin embargo las dos
están archivadas como mayo de 2020.

---

## 4. El dinero, medido hoy

### 4.1 Aviso importante sobre la cifra de la ficha

**La ficha dice 37 celdas, 8 obras, 39,07 M€ (medido el 2026-08-22). No
reproduce.** Y no reproduce porque **la consulta que produjo esa cifra nunca se
publicó** —lo reconoce la propia ficha del diccionario: *«su consulta NO está
publicada todavía»`—, así que no hay forma de repetirla.

Lo que sí reproduce **exactamente** es la causa: 8.778 claves duplicadas,
17.556 filas, 9 obras, 22 obras con fases que chocan. Ahí no se mueve un dígito.

Medido hoy, la cifra depende de **qué fase se dé por buena**, y hay dos reglas
razonables:

| Regla aplicada | Celdas | Obras | Exceso |
|---|---|---|---|
| **«Manda la fase que TERMINA dentro del mes»** (la que se sostiene) | **35** | **7** | **30.425.881,56 €** |
| «Manda siempre la fase de número mayor» (la ingenua) | 39 | 8 | 48.666.904,52 € |

*(Q11 da las dos columnas en la misma pasada.)*

La regla ingenua es la que mete a **0606 · PUY DU FOU** en la lista con
**18,24 M€ de error que no existen**: su fase 16 está vacía, así que quedarse
con ella daría cero euros en febrero de 2021, cuando el valor bueno son los
6,51 M€ de la fase 14. La cifra honesta y reproducible de hoy es
**30,43 M€ en 35 celdas de 7 obras**.

### 4.2 Obra a obra, para contrastar

Acumulado a origen (`importe_origen`) en el mes en conflicto: lo que se publica
hoy y lo que debería publicarse. **CD + CI + CP juntos.**

| Código | Obra | Mes | Escenario | Publicado hoy | Correcto | De más | Inflado |
|---|---|---|---|---:|---:|---:|---:|
| **0499** | VILLANUEVA | feb-2018 | Coste Real | 10.753.384,34 | 5.688.073,92 | **5.065.310,42** | **+89 %** |
| **0499** | VILLANUEVA | feb-2018 | Venta Real | 9.188.195,38 | 4.840.043,66 | **4.348.151,72** | **+90 %** |
| **0499** | VILLANUEVA | ene-2018 | Venta Real | 7.759.798,61 | 3.881.439,76 | **3.878.358,85** | **+100 %** |
| **0499** | VILLANUEVA | ene-2018 | Coste Real | 8.321.104,83 | 4.712.823,94 | **3.608.280,89** | **+77 %** |
| **0571** | PZA. DEL CAMPILLO | may-2020 | Coste Real | 9.182.732,45 | 4.591.393,06 | **4.591.339,39** | **+100 %** |
| **0571** | PZA. DEL CAMPILLO | may-2020 | Venta Real | 8.353.619,24 | 4.176.809,62 | **4.176.809,62** | **+100 %** |
| **0471** | AHORRAMAS LAS TABLAS | abr-2016 | Coste Real | 1.973.599,08 | 1.070.081,64 | 903.517,44 | +84 % |
| **0471** | AHORRAMAS LAS TABLAS | abr-2016 | Venta Real | 1.917.453,12 | 1.049.832,59 | 867.620,53 | +83 % |
| **0471** | AHORRAMAS LAS TABLAS | mar-2016 | Coste Real | 1.304.675,56 | 903.517,44 | 401.158,12 | +44 % |
| **0471** | AHORRAMAS LAS TABLAS | mar-2016 | Venta Real | 1.245.100,05 | 867.620,53 | 377.479,52 | +44 % |
| **0246** | EL ENCINAR | jun-2010 | Coste Real | 1.508.064,09 | 753.433,05 | 754.631,04 | +100 % |
| **0246** | EL ENCINAR | jun-2010 | Venta Real | 1.226.105,88 | 613.052,94 | 613.052,94 | +100 % |
| **0462** | RETAMAR | dic-2015 | Venta Real | 429.336,39 | 214.657,72 | 214.678,67 | +100 % |
| **0462** | RETAMAR | dic-2015 | Coste Real | 395.309,32 | 197.654,52 | 197.654,80 | +100 % |
| **0545** | J. DEERE NAVE 01 | dic-2017 | Venta Real | 317.482,23 | 157.760,75 | 159.721,48 | +101 % |
| **0545** | J. DEERE NAVE 01 | dic-2017 | Coste Real | 308.951,40 | 156.704,75 | 152.246,65 | +97 % |
| **0310** | CASETA BOMBAS J.DEERE | may-2011 | Venta Real | 116.072,72 | 58.036,36 | 58.036,36 | +100 % |
| **0310** | CASETA BOMBAS J.DEERE | may-2011 | Coste Real | 117.053,57 | 59.220,45 | 57.833,12 | +98 % |
| | | | **TOTAL** | | | **30.425.881,56** | |

*(Q12. Los importes salen de `mart.fact_seguimiento_categoria`, que es lo que
Power BI y el MCP leen hoy.)*

**Lo que ve el usuario, dicho en una línea:** en esos meses la tarjeta de KPI
enseña **el doble** —o casi el doble— de lo que la obra llevaba de verdad.

Los tres casos que no llegan al 100 % (**0471** en marzo, **0499** en enero y
febrero) son de patrón 1 y la razón es aritmética: la primera quincena tenía
menos acumulado que la segunda, así que sumar las dos infla menos del doble.

---

## 5. Cuánto pesa el error en cada obra

Un millón de más en una obra de cien millones y en una de dos no son el mismo
problema. La referencia es el **coste real a origen de la obra en su último mes
con dato**, es decir, lo que costó la obra entera (Q13).

| Código | Obra | Coste total real de la obra | De más publicado (coste) | Peso |
|---|---|---:|---:|---:|
| **0462** | RETAMAR | **197.654,52** | 197.654,80 | **100 % · el error es la obra entera** |
| **0571** | PZA. DEL CAMPILLO | 4.591.393,06 | 4.591.339,39 | **100 %** |
| **0246** | EL ENCINAR | 754.877,36 | 754.631,04 | **100 %** |
| **0499** | VILLANUEVA | 8.805.209,88 | 8.673.591,31 | **99 %** |
| **0545** | J. DEERE NAVE 01 | 157.141,23 | 152.246,65 | **97 %** |
| **0310** | CASETA BOMBAS | 65.102,93 | 57.833,12 | **89 %** |
| **0471** | AHORRAMAS LAS TABLAS | 2.001.576,48 | 1.304.675,56 | **65 %** |

**Ninguna obra sale barata.** El error a origen no es una desviación pequeña:
en cinco de las siete, lo que sobra en ese mes vale casi tanto como la obra
completa. Es lógico —se está sumando dos veces un acumulado que ya casi era el
total— pero conviene decirlo con el número delante.

### Un caso que hay que separar de los demás: **0462 · RETAMAR**

En las otras seis obras el mes en conflicto está **en medio** de la serie: la
curva sube al doble y vuelve a bajar en el mes siguiente. En **0462, el mes en
conflicto (dic-2015) es el ÚLTIMO mes de la obra**. No hay mes siguiente que la
corrija. **El total definitivo de esa obra está publicado al doble de forma
permanente:** 395.309,32 € de coste cuando costó 197.654,52 €. Cualquiera que
hoy pregunte «¿cuánto costó Retamar?» recibe el doble, sin ningún mes posterior
que le haga sospechar.

En las otras seis, la firma visible es una **joroba** en el gráfico. Ejemplo de
la 0246 (Q10, coste real CD):

```
abr-2010    498.650 €
may-2010    498.650 €
jun-2010    998.236 €   <-- el doble
(jul, ago    no existen)
sep-2010    499.832 €   <-- vuelve al sitio
```

---

## 6. Quién está consumiendo hoy estos números

Comprobado contra el catálogo de la base, no contra el repositorio (Q6 para las
dependencias, Q7 para los permisos, Q8 para el diccionario publicado).

| Objeto publicado | Lee de | ¿Le afecta? | ¿Lo sirve el MCP? |
|---|---|---|---|
| `mart.v_pbi_fact_categoria` | `fact_seguimiento_categoria` | **SÍ, el doblado íntegro** | **Sí** (`SELECT` a `mcp_sigrid_dm_ro`) |
| `mart.fact_seguimiento_categoria` | — | **SÍ** | **Sí** |
| `mart.v_pbi_fact` | `fact_seguimiento_mensual` | **SÍ**: le llegan las 17.556 filas duplicadas tal cual | **Sí** |
| `mart.fact_seguimiento_mensual` | — | **SÍ** | **Sí** |
| `cierre.v_pbi_planif_vs_real` | `fact_seguimiento_categoria` | **No por el doblado** (usa `importe_mes`), **sí por el patrón 2** (mete tres meses de real en uno) | **Sí** |
| `mart.v_fact_periodificado` | `fact_seguimiento_mensual` | No: solo hace `SUM(importe_mes)`, que telescopea bien | **Sí** |
| `mart.v_pbi_dim_fecha` | `fact_seguimiento_mensual` | No: solo toma el `MIN`/`MAX` del rango | Sí |

**Los seis objetos con `SELECT` concedido a `mcp_sigrid_dm_ro`**, y ese rol —según
lo dejado por F-006— **lo comparten hoy el MCP y Power BI**. Así que la respuesta
a «quién consume esto» es: **los dos, por el mismo sitio.**

### Dos cosas que la ficha no decía y conviene saber

1. **`cierre.v_pbi_planif_vs_real` también cuelga de la tabla afectada.** La
   ficha solo nombraba `mart.v_pbi_fact_categoria`. Es la misma vista que F-047
   acaba de rescatar. Se salva del doblado porque usa `importe_mes`, pero en las
   ocho obras de patrón 2 sigue comparando planificado contra un real que lleva
   tres meses metidos en uno.

2. **El aviso NO llega hasta el consumidor.** La ficha de
   `mart.fact_seguimiento_categoria` sí trae el aviso en mayúsculas. La de
   **`mart.v_pbi_fact_categoria`, que es la vista que Power BI abre de verdad,
   no lo trae**: su grano publicado es una línea sin ningún aviso. Un agente que
   consulte la vista por el MCP —lo natural, porque es la superficie de
   consumo— **no se entera de nada**. Es exactamente la lección de F-006 («el
   aviso baja al significado de cada columna») repetida un nivel más abajo.

### Un detalle sobre «ninguna columna identifica la fase»

Es casi cierto, y conviene precisarlo. `mart.v_pbi_fact` sí publica
`version_descripcion`, que para los reales trae el nombre de la fase. Pero es
**texto libre del jefe de obra, no el número de fase**, y en varias obras las
dos fases se llaman igual. En la **0310**, las dos filas gemelas son
**literalmente indistinguibles** (Q5):

| obra | partida | anio_mes | escenario | version_descripcion | version_master | importe_origen |
|---|---|---|---|---|---|---:|
| 702871 | 63061 | 2011-05-01 | Coste Real | Mayo 2011 | *(nulo)* | 5.936,04 |
| 702871 | 63061 | 2011-05-01 | Coste Real | Mayo 2011 | *(nulo)* | 6.993,25 |

Dos importes distintos, cero forma de saber cuál es el bueno desde lo publicado.
Pasa lo mismo en **0422, 0473 y 0509**. Así que la conclusión de la ficha se
sostiene: **la clave no se puede alargar con lo que hoy hay publicado.**

---

## 7. ¿Está creciendo o es un residuo histórico?

**Es residuo histórico, y con margen amplio.** Colisiones por año de fase,
contra el volumen total de fases (Q15):

| Año | Fases | Obras | Colisiones |
|---|---:|---:|---:|
| 2009 | 79 | 31 | 0 |
| 2010 | 144 | 33 | 1 |
| 2011 | 131 | 37 | 1 |
| 2012–2013 | 275 | — | 0 |
| **2014** | 176 | 44 | **4** |
| **2015** | 196 | 57 | **4** |
| **2016** | 197 | 53 | **8** |
| 2017 | 269 | 62 | 2 |
| 2018 | 360 | 62 | 2 |
| 2019 | 328 | 51 | 0 |
| 2020 | 302 | 49 | 1 |
| 2021 | 305 | 50 | 1 |
| **2022** | 297 | 55 | **0** |
| **2023** | 400 | 60 | **0** |
| **2024** | 462 | 69 | **0** |
| **2025** | 400 | 70 | **0** |
| **2026** | 230 | 43 | **0** |

**Cinco años consecutivos sin una sola colisión** (2022 a 2026), y en ese tramo
el volumen de fases ha crecido de 297 a 462 al año. La última colisión es de
**febrero de 2021** y es justo la que no cuesta dinero (0606). El foco está en
**2014–2018**, la época de las obras Domino's, y se apagó solo.

**Consecuencia para la urgencia:** esto **no es una hemorragia abierta**. Es
dinero mal publicado en obras **todas terminadas** (la más reciente cerró en
sep-2020) que sigue saliendo en cualquier informe histórico. No hay prisa por
una nocturna, pero tampoco desaparece solo: cada `build-mart` lo vuelve a
escribir igual.

---

## 8. Las dos hipótesis, con su consecuencia numérica

La decisión es de Negocio y **no la toma ningún agente**. Lo que aporta la
evidencia es que **no hay una hipótesis, hay dos, y cada una gobierna un patrón
distinto**. Elegir una sola para las 22 obras es lo único que la evidencia sí
descarta.

### Hipótesis 1 · «Las dos fases son información legítima»

Encaja con el **patrón 1: 14 obras, 16 colisiones**. El jefe de obra cerró dos
veces dentro del mes, a propósito, y las dos medidas son buenas.

- **Qué haría falta:** una columna más en la clave —el número de fase— y
  **publicada**, porque hoy no se puede reconstruir desde el fact.
- **Qué pasaría con los totales:** el acumulado del mes pasa a ser el de la
  **última quincena**. Se retiran **19.877.715,10 €** de exceso en las cinco
  obras de patrón 1 con dinero (0310, 0471, 0499, 0545). Ningún mes aparece ni
  desaparece: el eje temporal queda igual.
- **Qué NO arregla:** las ocho obras del patrón 2 siguen mal, porque ahí el
  problema no es que falte una columna, es que **el mes está equivocado**.

### Hipótesis 2 · «Una de las dos es error de configuración en Sigrid»

Encaja con el **patrón 2: 8 obras, 8 colisiones**, donde el `mes` de la fase
contradice a su fecha de fin y a su propio nombre.

- **Qué haría falta:** no un filtro, sino un **remapeo**. Filtrar la fase
  descolocada tira medidas reales —la fase 13 de la 0246 es el trabajo de
  jun-16 a ago-31—; lo que corresponde es llevarla al mes que le toca.
- **Qué pasaría con los totales:** se retiran **10.548.166,46 €** de exceso
  (0246, 0462, 0571; la 0606 aporta 0 €) **y además aparecen meses que hoy no
  existen**: jul y ago 2010 en la 0246, y jun, jul y ago 2020 en la 0571. El eje
  temporal **cambia**, y con él cualquier informe de evolución mensual de esas
  obras.
- **Un aviso:** en la **0571 ninguna de las dos fases cuadra con mayo**. Aquí
  «cuál de las dos está mal configurada» no tiene respuesta obvia; probablemente
  lo estén las dos.

### Lo que la evidencia sí zanja, y con qué números

1. **Una sola hipótesis para las 22 obras no se sostiene.** La prueba es
   objetiva y no opinable: en 16 colisiones las dos fases terminan dentro del
   mes que declaran, y en 8 la segunda termina fuera. Son hechos distintos.
2. **«Quedarse siempre con la fase de número mayor» está descartado.** Da cero
   euros en feb-2021 para PUY DU FOU, donde hay 6,51 M€ de coste real
   perfectamente válidos en la fase 14. Ese atajo no solo no arregla: rompe una
   obra que hoy está bien.
3. **`importe_mes` no hay que tocarlo.** Ya está bien: las filas telescopean y
   su suma es el movimiento del mes (200 de 200 series, medido en F-006 y
   coherente con lo visto hoy). El defecto está acotado a las columnas
   acumuladas a origen.
4. **0433 y 0606 no son obras afectadas en dinero.** Duplican filas, sí, y eso
   rompe cualquier `JOIN` por la clave; pero su euro de más es cero. Contarlas
   como afectadas es lo que produce la diferencia entre 48,67 M€ y 30,43 M€.

**Lo que sigue siendo suyo, y este documento no responde:** en las 14 obras de
patrón 1, ¿los dos cierres del mes son dos medidas que Negocio quiere conservar
por separado, o son un apaño de obra que a efectos de seguimiento anual sobra?
De esa respuesta depende si la clave del datamart crece con una columna nueva
—y aparece en Power BI— o si el datamart se queda con un cierre por mes.

---

## Apéndice · Las consultas

Todas se ejecutaron en solo lectura contra `sigrid_dm`. Las abreviadas indican
el criterio; el texto íntegro es reconstruible desde estas líneas.

- **Q1 · Unicidad (T26).** `SELECT count(*), COALESCE(sum(filas),0) FROM (SELECT
  obra_id, partida_id, anio_mes, escenario, count(*) AS filas FROM
  mart.fact_seguimiento_mensual GROUP BY 1,2,3,4 HAVING count(*)>1) d;`
  → **8.778 / 17.556**.
- **Q2 · Las 22 obras y sus fases.** Colisiones en `stg.fases` (`GROUP BY
  obra_id, anio, mes HAVING count(*)>1`, con `numero_fase >= 1`), unidas a
  `stg.fases` y `stg.obras` para traer `numero_fase`, `nombre_mes`,
  `fecha_inicio`, `fecha_fin` y el predicado
  `EXTRACT(YEAR FROM fecha_fin)=anio AND EXTRACT(MONTH FROM fecha_fin)=mes`
  que separa el patrón 1 del 2. → **24 colisiones en 22 obras**.
- **Q3 · Las 9 obras con filas duplicadas.** La subconsulta de Q1 agrupada por
  `obra_id`, unida a `stg.obras`. → **9 obras**, escenarios `Coste Real` y
  `Venta Real` únicamente.
- **Q4 · Por qué 13 obras no duplican.** Fases en colisión contra
  `stg.presupuesto` (`LEFT JOIN` por `obra_id` + `fase_num`, `ambito_id IN
  (3,7)`), contando filas por fase. → 13 obras tienen una de las dos fases con
  **0 filas**.
- **Q5 · Las filas gemelas indistinguibles.** `SELECT obra_id, partida_id,
  anio_mes, escenario, version_descripcion, version_master, importe_origen,
  importe_mes FROM mart.fact_seguimiento_mensual WHERE obra_id = 702871 AND
  anio_mes = '2011-05-01' AND escenario = 'Coste Real' ORDER BY partida_id,
  fact_id;`
- **Q6 · Quién lee las tablas afectadas.** `pg_depend` + `pg_rewrite` +
  `pg_class` filtrando `relname IN ('fact_seguimiento_categoria',
  'fact_seguimiento_mensual')` en el esquema `mart`. → 5 vistas.
- **Q7 · Permisos del MCP.** `SELECT table_schema, table_name, privilege_type
  FROM information_schema.role_table_grants WHERE grantee =
  'mcp_sigrid_dm_ro' AND table_name IN (…);` → `SELECT` en los 6 objetos.
- **Q8 · Lo que el diccionario publica.** `SELECT esquema, objeto,
  consumo_recomendado, grano, clave_negocio, avisos FROM _meta.diccionario
  WHERE objeto IN (…);` → el aviso está en la tabla, **no** en
  `v_pbi_fact_categoria`.
- **Q9 a Q13 · La medición del dinero.** Comparten el mismo armazón:
  1. colisiones de `stg.fases` (como Q2) → **fase dueña del mes**: la que
     termina dentro del mes; si terminan las dos, la de número mayor;
  2. `stg.plan_mensual` filtrado a esas `(obra_id, anio_mes)` y `ambito_id IN
     (3,7)`, donde `version` es el número de fase de los reales;
  3. `count(*) OVER (PARTITION BY obra_id, partida_id, ambito_id, anio_mes)`
     para marcar las parejas;
  4. correcto = `sum(importe_origen) FILTER (WHERE n = 1 OR version =
     fase_dueña)`, agregado por `(obra_id, anio_mes, categoria, ambito_id)`
     con la `categoria` de `stg.partidas`;
  5. `JOIN` contra `mart.fact_seguimiento_categoria` por esa misma cuaterna.

  La reconstrucción se validó celda a celda contra lo publicado: **desvío
  0,00 € en las 43 celdas** tocadas por una colisión. Variantes:
  **Q9** = celdas con diferencia (35, 7 obras); **Q11** = la misma consulta con
  la regla alternativa `version = max(version)` en paralelo (39 celdas, 8
  obras, 48.666.904,52 €) y `ROLLUP` para el total; **Q12** = agregado por
  `(obra, mes, escenario)`; **Q13** = exceso contra el acumulado de la obra en
  su último mes con dato.
- **Q10 · Meses presentes y huecos.** `SELECT anio_mes, sum(importe_origen) FROM
  mart.fact_seguimiento_categoria WHERE escenario='Coste Real' AND
  categoria='CD' AND obra_id = … GROUP BY 1 ORDER BY 1;` para 584748, 950302 y
  1251489.
- **Q14 · Frescura del dato.** `SELECT * FROM _meta.v_frescura ORDER BY 1;`
  → `build_mart` OK el 2026-08-28 a las 04:56 UTC.
- **Q15 · Evolución por año.** Fases por año de `stg.fases` con un `LEFT JOIN`
  al recuento de colisiones del mismo año.

**Reproducibilidad.** El ejecutor usado abre la conexión con
`SET default_transaction_read_only = on` y `SET statement_timeout = '120s'`,
rechaza cualquier texto con palabra de escritura y cierra con `ROLLBACK`.
Vivió en el scratchpad de la sesión; no se ha versionado nada ni se ha tocado
`.env`.
