# F-038 · Exploración medida del comparativo de ofertas

Medido el **2026-09-17** contra Sigrid vivo por `sigrid-api` (`leer_sql`, SOLO
LECTURA) y contra el datamart por el MCP. Cero escrituras. Cada afirmación lleva
su cifra; lo que no se puede saber está dicho con todas las letras.

Da por buenos los volúmenes del censo de F-072
(`progress/explore_F-072_compras.md`): aquí solo se miden las preguntas nuevas.
Las cifras bailan unas decenas respecto a aquel censo porque el origen es vivo:
hoy `com` tiene **20.261** filas (no 20.260) y `comlin` **197.645**.

---

## 1 · Estados y fechas: qué fecha es la de creación

**El estado** sale de `con.est` con `con.tip = 46`, traducido por la pareja
(46, est) contra `conest`. **De los 32 estados publicados del catálogo, en uso
solo 18**, y el reparto está muy concentrado:

| est | estado | comparativos |
|---|---|---|
| 5 | APROBADO | **18.709 (92,3 %)** |
| 1 | EN ELABORACIÓN | 604 |
| 51 | APROBADO UTE | 256 |
| 114 | Aprobado Dirección Compras | 171 |
| 6 | RECHAZADO JEFE GRUPO | 141 |
| 7 | RECHAZADO DIRECCION COMPRAS | 130 |
| 2 | PROPUESTO POR JEFE DE OBRA | 95 |
| 11 | ELABORACION UTE | 78 |
| 21 | APROBADO JEFE OBRA UTE | 26 |
| resto (9 estados) | — | 51 |

`SELECT c.est, e.res, COUNT(*) FROM com m JOIN con c ON c.ide=m.ide LEFT JOIN
conest e ON e.tip=46 AND e.est=c.est GROUP BY c.est, e.res`

**Las fechas, contadas con `>0` porque 0 = NULL** (`com` más `con.fec`):

| campo | informados | % | lectura |
|---|---|---|---|
| **`con.fec`** | **20.261** | **100 %** | **fecha de ALTA del documento = la CREACIÓN que pide Aguado.** Rango 2009-02-06 a 2026-09-17 |
| `con.tiemod` | 20.261 | 100 % | última modificación del documento (float Delphi). **NO es el cambio de estado**: cualquier edición la mueve |
| `com.fecent` | 44 | 0,22 % | papel mojado |
| `com.feclim` | 34 | 0,17 % | papel mojado |
| `com.fecsum` | 32 | 0,16 % | papel mojado |
| `com.feccon` | 26 | 0,13 % | papel mojado |
| `com.fecdiv` / `fecinirec` / `fecfinrec` | **0** | 0 % | **vacías en las 20.261** |

**RESPUESTA A AGUADO, medida: la fecha de creación del documento es `con.fec`,
100 % informada.** Las siete fechas propias de `com` no sirven: entre las cuatro
que tienen algo suman 136 valores sobre 20.261 documentos. No se puede deducir su
semántica de una distribución de 26-44 casos; solo se puede decir que **nadie las
rellena** y que publicarlas sería publicar vacío.

También a 0 en las 20.261, **verificado en ORIGEN y no solo en `raw`**:
`ppoide`, `prmide`, `pexide`, `tipsub`, `horlim`. Y `com.tex` informado en
**60 de 20.261**.

---

## 2 · Los importes: existen CUATRO magnitudes y NO cuadran entre sí

Este es el hallazgo central. Hay cuatro cifras calculables y las cuatro dan
números distintos para lo mismo. Publicar una sola sin decir cuál es, o publicar
varias sin declarar que no cuadran, produce el error que F-083 vino a evitar.

| # | categoría | cómo se calcula | cobertura | total |
|---|---|---|---|---|
| A | **Ofertado por proveedor** (total del documento) | `dco.totdoc` de los `comprv.docide` | 68.194 de 70.919 ofertas (96,2 %) | **3.474,8 M€** |
| B | **Ofertado línea a línea** | `dcopro.can × dcopro.pre` con `comlinide>0` | 782.780 de 791.011 líneas (99,0 %); **196.675 de 197.645 `comlin` cubiertas (99,5 %)** | **2.989,1 M€** |
| C | **Adjudicado** (la línea del concurso) | `comlin.can × comlin.pre` | `pre<>0` en 183.100 (92,6 %), `can<>0` en 191.496 (96,9 %) | **1.229,1 M€** |
| D | **Contratado** | `ctr.totdoc` de los contratos con `comide>0` | 11.447 de 11.515 (99,4 %) | **623,8 M€** (CON IVA) |

**La oferta GANADORA se identifica sin ambigüedad**: el `dco` con `con.est = 6`
«Aceptada definitivamente» (`tip=12`). **17.783 comparativos tienen exactamente
una ganadora, 1 tiene dos y 2.162 no tienen ninguna.** Suma de ganadoras:
**707,7 M€**.

**Y aquí está el aviso que vale la feature.** Comparando, comparativo a
comparativo, la ganadora (A) contra el adjudicado (C), excluido el comparativo
1610000 de los 363 M€:

- **697 de 17.783 cuadran al euro (3,9 %)**
- **16.474 (92,6 %) tienen el adjudicado POR DEBAJO de la oferta ganadora**
- 554 (3,1 %) por encima en más del 5 %
- totales: ganadora 707,7 M€ frente a adjudicado 814,9 M€

Es decir: **`dco.totdoc` y `comlin.can×pre` NO son la misma magnitud.** `totdoc`
es el total del documento de oferta (el mismo campo que `R-COMPRAS-SIN-IVA` marca
como CON IVA para `ctr.totdoc`); `comlin` es la línea del concurso. Y las líneas
del ganador (`dcopro` con su `dco` en est=6) suman **585,6 M€ en 179.080 líneas**,
una tercera cifra. **No se puede decidir aquí cuál es «el importe del
comparativo»: es una decisión de negocio y hay que preguntarla.**

**El ahorro del concurso SÍ se puede calcular.** En los **15.597 comparativos con
más de un ofertante con importe**, la diferencia entre la oferta más cara y la
más barata suma **186,5 M€** (mínimas 659,7 M€, máximas 846,1 M€). Hoy nadie ve
esa cifra.

**Saneado obligatorio antes de publicar** (medido hoy sobre `comlin`): **14.545
líneas con `pre`=0** en 2.921 comparativos, **4.203 líneas con importe negativo**
(−22,2 M€) y el comparativo **1610000 con una sola línea de 363,2 M€**. Le sigue
el **2834916 con 66,9 M€**, que es nuevo respecto al censo de F-072.

---

## 3 · El «planificado» de Aguado: NO se resuelve. Tres hipótesis medidas

**Descartadas con cifra**: `com.ppoide`, `com.prmide` y `com.pexide` están a
**0 en las 20.261 filas**. No hay presupuesto colgado del comparativo.

**HIPÓTESIS 1 · `dncpro.preref`/`canref` («precio y medición de referencia»).
DESCARTADA, y esto CORRIGE la ficha de F-038.** La ficha afirma que ahí vive «el
de referencia». Medido: `preref` informado en 178.818 líneas (90,5 %), pero
**coincide con `comlin.pre` en 177.275 de ellas (99,1 %)**. Y no es efecto de la
adjudicación: en los comparativos **EN ELABORACIÓN** coincide en 2.294 de 2.411
(95,1 %) y en los **RECHAZADOS por Dirección de Compras** en 277 de 312 (88,8 %).
**`preref` es el mismo precio de la línea, no una referencia independiente.**
Publicarlo como «precio previsto» daría desviación ≈ 0: exactamente el error que
la ficha advierte para `dncpro.pre`, pero el error está **también en `preref`**.
Lo único que sí difiere es `canref` (la MEDICIÓN): coincide con `comlin.can` en
128.882 de 165.002 (78,1 %), y por eso `Σ canref×preref` = 643,0 M€ frente a
`Σ can×pre` = 1.080,2 M€ sobre esas mismas líneas.

**HIPÓTESIS 2 · el presupuesto de la obra vía `dncpro.paride`. Es la única con
contenido, y no es directamente sumable.** `dncpro.paride` está informado en
**197.642 de 197.642 líneas (100 %)** y **197.633 (99,995 %)** tienen esa partida
en `obrparpre`. Restringido al ámbito **3 = COSTE**, **196.916 líneas (99,6 %)**
tienen presupuesto de coste para su partida en su obra. **PERO**: `obrparpre` es
único por `(obride, paride, amb, fas)` y hay del orden de **4,1 fases por
partida** (10.833 filas para 2.623 partidas en la obra con más comparativos), así
que el join a pelo explota: probado, da **137.000 M€**, tres órdenes de magnitud
fuera. Agregado bien por `(obride, paride)`, los 122.541 pares
comparativo×partida con coste presupuestado suman **30.770 M€** frente a 1.229 M€
adjudicados, **25 veces más**, porque el presupuesto de una partida de obra
entera se compra en muchos comparativos y se cuenta repetido. **Es un enlace
real, no una comparación.**

**HIPÓTESIS 3 · el ámbito 14 `POR_REF` «PRESUPUESTO REFERENCIA».** Existe, con
**87.652 filas de 13.941.970** (0,63 %) en `obrparpre`, y solo alcanza **61.177**
de las líneas de comparativo en el join sin desduplicar. Con esa cobertura no es
una fuente general.

**CONCLUSIÓN: el «planificado» que pide Aguado NO existe como campo del
comparativo en Sigrid.** Lo más cercano es el presupuesto de COSTE de la partida
de la obra, que es otra cosa, y hay que preguntarle si es eso lo que quiere.

---

## 4 · Aprobaciones: quién y cuándo. Las dos fuentes coinciden

Frontera con F-085: **aquí solo se mide**; el modelo del circuito es de allí.

| vía | firmas | comparativos distintos | usuarios | con fecha |
|---|---|---|---|---|
| `confir` (tip 46) | **66.123** | **19.670** | 120 | **59.664 (90,2 %)** |
| `dbo.log` (`tab='con'`, `tip=46`, `ope=24`) | **61.664** | **19.657** | 120 | 100 % (`fec`+`hor`) |

**Coinciden**: 19.670 frente a 19.657 comparativos, y 120 usuarios por las dos
vías. Los que más firman: `ipallares` 10.971, `jmaguado` 8.379, `mvicente` 4.683.

**TRAMPA MEDIDA EN `dbo.log`, y es gorda: `log.ide` NO es el `ide` del
documento.** Es la PK del propio log: 183.684 valores distintos para 183.684
filas. **El enlace correcto es `(log.cod, log.emp, log.tip) → (con.cod, con.emp,
con.tip)`**, y así casan **61.381 de 61.664 firmas (99,5 %)**. Unir por `ide` da
118 coincidencias sobre 19.670: **basura que parece un join**.

**Segunda corrección: `dbo.log.res` NO trae la actividad.** Para `ope=5` es
**`con.res`, el NOMBRE del comparativo**, en 65.616 de 66.550 (98,6 %). Que se
lean «MOVIMIENTO DE TIERRAS» o «PINTURA» es porque así se titula el comparativo.
La actividad de verdad está en `com.natide` (punto 6).

**El desempate que F-085 pide sobre `fir`/`firok`/`est`, medido aquí:**
`fir=1, firok=0, est=2` → 40.545 · `fir=1, firok=1, est=2` → 19.113 ·
`fir=0, firok=0, est=0` → **6.459** · `fir=0, firok=0, est=2` → 6.
Los **6.459 con `fir=0` son exactamente los 6.459 sin fecha** (66.123 − 59.664).
**`fir=0` ⇔ sin fecha ⇔ firma PENDIENTE, no firma sin sellar.** Afecta a
**4.120 comparativos**. `firok` distingue la firma con validación digital OK.

**Circuito**: `cod` vale `COMVAL` (comparativo) o `COAVAL` (ampliación); `rol`
da los escalones: **JEFO (jefe de obra), JG (jefe de grupo) y DCOM (dirección de
compras)** con 17.927 / 17.925 / 17.927 firmas en COMVAL → **tres escalones
fijos**, más las variantes UTE (JEFOUTE, JGUTE, JGALD, JGINE) y JEFINST.
**`ord` = 0 en TODAS**: el orden de los pasos NO está en `confir`; lo único que
ordena es `deffir.pos` (17 filas) y la fecha de cada firma. **`estfin` SÍ es el
estado final del circuito** y casa con `con.est`: 5 APROBADO, 51 APROBADO UTE,
114 Aprobado Dir. Compras.

**«Fecha del último cambio de estado» (Aguado): SE PUEDE, para el estado que
importa.** Los **18.709 comparativos APROBADOS tienen los 18.709 firma con fecha
en `confir`**, y `MAX(confir.fec)` es la fecha en que se completó el circuito, o
sea la del paso a APROBADO. **Tiempo medio de aprobación medido: 19,8 días** desde
`con.fec` (19.649 comparativos). Para los estados que NO son de firma (EN
ELABORACIÓN, PROPUESTO) la fecha del cambio **no existe**, y `dbo.log` da la
fecha de la ACCIÓN, no el estado al que se pasó: `log.est` vale 1 (182.615) y
2 (1.069), es el resultado de la operación y no el estado del documento.

---

## 5 · Comparativo → contrato: la vía publicada pierde el 38 %

| vía | comparativos enlazados | contratos |
|---|---|---|
| **`comlin.ctride`** | **18.537 (91,5 %)** | **11.695** |
| `ctr.comide` | 11.421 (56,4 %) | 11.515 |
| intersección | 11.395 | 11.452 |

**`comlin.ctride` cubre 7.116 comparativos más que `ctr.comide`.** Y lo publicado
hoy sale de la vía pobre: `compras.contratos` tiene **11.503 filas con
`comparativo_id` y 11.409 comparativos distintos** (MCP, build 2026-09-16 02:39
UTC). Un usuario que pregunte «¿este comparativo tiene contrato?» contra el
datamart de hoy recibe **NO** en unos 7.100 casos en que la respuesta es SÍ.

`comlin.ctride` está informado en **185.911 de 197.645 líneas (94,1 %)**. El
contrato trae **código (`con.cod`, 100 %) y fecha (`con.fec`, 11.506 de 11.515 =
99,9 %)**: **las dos cosas que pide Aguado se pueden dar.**

---

## 6 · Ofertas y actividad

**`comprv` es el ofertante invitado**: una fila por proveedor invitado a un
comparativo, **70.919 filas**, cada una con su documento de oferta
(`docide` → `dco`, **70.919 de 70.919, 100 %**). Se invita a **1 proveedor en
4.033 comparativos, 2 en 3.136, 3 en 3.440, 4 en 4.361** y cola hasta 27.
`pos` informado al 100 %, `refide` al 30,7 %.

**Confirmada la trampa de F-072 en origen**: `comprv.prvide` informado en
**12.906 de 70.919 (18,2 %)**; **`dco.entide` en 70.822 (99,86 %)**. El proveedor
sale de `dco.entide`, con **8.759 proveedores distintos**.

**Ofertar frente a ser invitado**: de las 70.919 invitaciones, por `con.est` del
`dco` (tip 12) → **Rechazada 45.800 · Aceptada definitivamente 17.785 ·
Pendiente 3.707 · Recibida 3.400 · Precios solicitados 227**. Y por línea:
`dcopro` cubre **196.675 de 197.645 líneas**, con **1 oferta en 24.144 líneas,
2 en 27.898, 3 en 41.468, 4 en 45.889**, cola hasta 27.

**LA ACTIVIDAD ES `com.natide` → `auxpronat`**, informada en **20.108 de 20.261
(99,25 %)** y **casan las 20.108 (100 %)**, con **254 actividades**: DRENAJE,
SANEAMIENTO Y VARIOS DE URBANIZACIÓN 3.176 · SUBCONTRATA CON APORTE DE MATERIALES
2.691 · SUMINISTRO DE MATERIALES 2.191 · SUBCONTRATA SOLO MANO DE OBRA 1.160 ·
OBRA COMPLETA 848 + 626 · ALQUILER DE MAQUINARIA 662. **Es lo que pide F-067 y
está listo.** `com.cocide` → `auxobrcoc` (tipo de contrato) solo al **16,9 %**
(3.430). Los comparativos cubren **192 obras**.

---

## Decisiones que quedan para el humano

1. **¿QUÉ ES «el importe del comparativo»?** Hay cuatro cifras medidas (A 3.474,8
   M€ ofertado, B 2.989,1 M€ ofertado por línea, C 1.229,1 M€ adjudicado, D 623,8
   M€ contratado) y la ganadora (707,7 M€) **no cuadra con el adjudicado en el
   96,1 % de los comparativos**. Hay que elegir cuál se publica como «el»
   importe, o publicar varias con el nombre exacto de cada una. **No lo puede
   decidir la spec sola.**
2. **PREGUNTAR A AGUADO QUÉ ES «EL PLANIFICADO».** No existe en el comparativo.
   Si es el presupuesto de coste de la partida (hipótesis 2, 99,6 % de cobertura)
   se puede enlazar, pero **no es comparable como suma** y hay que decidir el
   criterio. Es una pregunta legítima para devolverle.
3. **Corregir la ficha de F-038**: `dncpro.preref` NO es el precio de referencia
   (coincide con el adjudicado en el 99,1 %, y en el 95,1 % de los comparativos
   aún en elaboración). El aviso de la ficha vale para `pre` **y también para
   `preref`**.
4. **El enlace comparativo → contrato**: ¿se corrige `compras.contratos` para que
   use `comlin.ctride` (+7.100 comparativos) o se publica el enlace en el objeto
   nuevo de comparativos? Afecta a un objeto ya publicado.
5. **Frontera con F-085**: la fecha de aprobación del comparativo sale de
   `MAX(confir.fec)` y está medida aquí. ¿La publica F-038 en su objeto de
   comparativo, porque es la fecha que Aguado pide, o espera al modelo de firmas
   de F-085? Recomendación: **F-038 publica la fecha de aprobación y el número de
   firmas pendientes; F-085 publica el circuito paso a paso.**
6. **Ingesta**: para el modelo completo hacen falta `dco`, `dcopro` y `dncpro`
   (ya en `raw` por F-066) y, si se quiere el enlace al presupuesto, `obrparpre`
   (ya en `raw`). **`dbo.log` no hace falta para el comparativo**: `confir` lo
   cubre mejor y con fecha.
7. **Las siete fechas de `com` y los cinco campos a 0** (`ppoide`, `prmide`,
   `pexide`, `tipsub`, `horlim`): declararlos en `config/objetos_pendientes.yaml`
   o dejar constancia en la ficha del diccionario de que están vacíos en origen,
   para que nadie los vuelva a mirar.
