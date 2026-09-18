# Búsqueda exhaustiva · ¿está el «% de coste objetivo» en Sigrid?

Medido el **2026-09-17 22:25 UTC** contra Sigrid vivo por `sigrid-api` (`leer_sql`, **SOLO
LECTURA**, cero escrituras). Encargo: «el porcentaje de coste objetivo revisa a ver si está en
Sigrid», con **coste objetivo = ABC con un % de bajada**. Seis vías nuevas, ninguna repetida de
`progress/explore_planificado_fase0_abc_objetivo.md`.

**VEREDICTO: NO ESTÁ EN SIGRID. Ni el porcentaje, ni el importe, ni un ámbito, ni una versión,
ni un campo extendido.** La vía 6 lo demuestra sola: **ningún importe de la base es un múltiplo
constante del ABC**. El % lo aplica alguien fuera. **Hay que preguntarlo; no se puede deducir.**

## 1 · El catálogo de ámbitos entero: 14, y ninguno es un objetivo

`auxobramb` es el catálogo: **14 filas, todas vivas** (`fecbaj = 0`), con recuento de
`obrparpre` / `obrfasamb` (todas las fases, no solo la 0):

| ide·cod·nombre | `obrparpre` | obras | `obrfasamb` | | ide·cod·nombre | `obrparpre` | obras | `obrfasamb` |
|---|---|---|---|---|---|---|---|---|
| 1 PRO PROYECTO | 40.278 | 29 | 288 | | 9 MASV MASTER CERTIF. | 2.155.996 | 201 | 3.080 |
| 2 EST ESTUDIO | 140.162 | 669 | 564 | | 10 COP COSTE PENDIENTE | 522.703 | 134 | 1.689 |
| **3 COS COSTE** | 2.068.367 | 688 | 5.100 | | 11 MASP MASTER VENTA | 2.506.026 | 226 | 3.168 |
| 4 OFE OFERTA | 75.675 | 136 | 516 | | 12 EST_JO ESTUDIO J.OBRA | 102.405 | 27 | 377 |
| 5 VEN CERTIFICACION | 1.423.033 | 336 | 4.798 | | 13 CER_PEC CERTIF. PEC | 231.724 | 44 | 779 |
| 7 PROD VENTA | 1.813.059 | 369 | 4.899 | | 14 POR_REF PPTO REFEREN. | 87.652 | 2 | 47 |
| **8 MAS MASTER COSTE** | 2.761.109 | 241 | 3.176 | | 15 PRO_JO PRODUCC. REAL | 14.631 | 4 | 61 |

**Ninguno se llama OBJETIVO, META, BAJA ni equivalente.** Los dos no mirados antes —12 `ESTUDIO
JEFE OBRA` (27 obras) y 15 `PRODUCCIÓN REAL` (4)— no lo son ni por nombre ni por cobertura. El
catálogo no tiene huecos (`ide` 1-15 sin el 6) y `obramb` confirma que las obras solo usan esos 14.
**La hipótesis «el objetivo es un ámbito» queda cerrada.**

## 2 · Los textos de las versiones master, de forma sistemática

Patrones en `obrfasamb.res` + `.tex`, con fechas (`fec`), todos los ámbitos:

| patrón | ámbito 8 | otros ámbitos | rango de fechas en el 8 |
|---|---|---|---|
| `OBJETIV` | **8 filas / 8 obras** | 0 | 2009-08-31 → 2018-10-15 |
| `COEFICIENT` | 3 / 3 | 1 (amb 2) | 2009-08-31 (las tres) |
| `K=` | 3 / 2 | 0 | 2016-05 → 2016-12 |
| `AJUST` | **1 / 1** | 3 (amb 2 y 4) | 2025-09-18 |
| `BAJA` | **0** | 5 (amb 2 y 4) | — |
| `META` / `REDUC` | **0** | 0 | — |
| contiene `%` | 28 / 28 | 7 (amb 2 y 4) | 2009-08-31 → 2025-03-13 |

Leídas las 28 con `%` una a una: **todas son de gastos generales o coeficiente de paso** —`GG=9%`,
`9%GG`, `Coef. Paso=1,23`, `(3%)`, `Control de Calidad(0,5%)`— **salvo las 3 de 2009** (`res` =
`OBJETIVO COSTE`, `tex` = `Estudio con coeficiente 80%`; obras 584748, 585622, 585626). Las otras 5
con `OBJETIV` son `CIERRE OBJETIVO` / `OBJETIVO FIN OBRA` de 2018, sin porcentaje. En `obrfas`:
`OBJETIV` 1 fila, `BAJA` 0, `COEFICIENT` 0.

**La única huella reciente, y no es lo que parece.** La fila de 2025-09-18 es la obra **2537303,
versión 3, `AJUSTES SOBRE ABC 18/09/2025`**. De sus 20 versiones del ámbito 8, la v3 vale
**10.055.683 €** y la v4 (`Versión 4 (22/09/2025)_ABC`, `tex` = `ABC DEF`) **10.013.935 €**: **la
versión de «ajustes» es ANTERIOR al ABC y un 0,4 % MÁS ALTA** (ratio 1,004). Es el borrador con
el que se llega al ABC, no una bajada aplicada sobre él.

**Inventario completo del convenio de tipificación** (lo que sigue al paréntesis de `res` en los
3.176 registros del ámbito 8): **3.151 sin sufijo**, `_ABC` 3, `OBJETIVO COSTE` 3 (las de 2009),
`_CUAT OCT-25` / `_CUAT FEB-26` / `CUATR FEB-25` / `CUATR JUN-25` 1 cada uno y 12 literales sueltos
más (`OT`, `NO VALE`…). **No existe ningún `_OBJ` ni equivalente**; el ABC se tipifica por `tex`.
**El «objetivo coste con coeficiente» existió en 3 obras de agosto de 2009 y no ha vuelto en
diecisiete años: práctica abandonada.**

## 3 · Barrido de nombres de columna en toda la base

`INFORMATION_SCHEMA.COLUMNS` con `obj`/`baj`/`coef`/`meta`/`redu`: **140 columnas**, 104 en
tablas `tmp*` de 2017-2026 (`ssreduccion`/`svreduccion`). Las reales, medidas una a una:

| candidato | medición | veredicto |
|---|---|---|
| `obrctr.coebaj` («coef. de baja» del contrato de obra) | **0 informadas de 966 filas / 448 obras** (min y max = 0) | NO |
| `obrfasamb.coeficval` (valor del coeficiente, varchar) | **0 informadas en los 14 ámbitos** | NO |
| `obrfasamb.coepas` / `plaest` | 0 salvo **218** y 40 en el ámbito 2; `tipofi`, `impsie` y `beopor2`, **0 en los 14** | NO |
| `obrcal.coef`, `obrape.bajtem` | **tablas vacías** (0 filas) | NO |

Con `por`/`pct`/`dto`/`desc`: **206 columnas**. Las únicas de obra: `obrpar.porpar` (**tabla
vacía**), `obrparpar.porcen` (**0 de 393.954**), `obrtecext.porcen` (0 de 6.730),
`obrtecint.porcen` (0 de 20), `obrtecres.porcen` (0 de 526), `obrctr.cobporret` (retención de
cobro) y las ya descartadas. La familia `roe` / `roecos` / `roeseg`: **entera vacía, 0 filas**.

## 4 · Barrido de nombres de tabla

- `obj`/`coef`/`baj`/`meta`/`redu`: solo `auxentobj`, `auxmotbaj`, `ect` y `empent` (**0 filas** las cuatro).
- `pre` (23 tablas): **vacías todas** menos `cuepre` (13), `condoppre` (60.679, precios de
  documento de contrato) y `obrparpre`. A cero: `obrrevpre`, `obrprediv`, `ppooripre`, `propre`,
  `ctrrevpre`, `prmpre`, `puepre`, `ppoamb`, `ppoambfas`, `auxppoamb`.
- **Mapa completo de las 56 tablas `obr*`** (`sys.partitions`): solo 11 tienen filas —`obr` 922,
  `obramb` 8.811, `obrctr` 966, `obrfas` 4.568, `obrfasamb` 28.542, `obrofc` 1.081, `obrparmre`
  198.397, `obrparpar` 393.954, `obrparpre` 13.942.821, `obrusu` 9.160, `obrx` 922—. **No hay
  ninguna tabla de objetivos colgada de la obra.**
- **El mecanismo de campos extendidos, cerrado del todo.** `defext` define **26 campos en todo
  el sistema** y **ninguno es un porcentaje ni un objetivo**: los 5 de obra (`tip = 42`) son
  Delegado, Jefe de grupo, Jefe Administración, Administrativo de obra y «Número Versión
  Planificación»; los de `tip = 43` son de personal y los de `tip = 44` de contrato. Si alguien
  hubiera querido añadir «% objetivo» sin tocar el modelo, este era el sitio: **no lo hizo**.

## 5 · La obra como portadora: las 28 columnas `float` de `obr`, medidas

De las 922 obras, informadas: `plaadj` 168 (plazo, 0,7-25), `coegar` 167 (garantía, 2,5-10),
`impadj` 158, `impadjtot` 157, `implic`/`implictot` 18, `plalic` 16, `impofe`/`impofetot` 14,
`fiaimp` 7, `supurb` 4, `coeind` **2**, `impurb` 2. **A cero en las 922**: `apebajmed`,
`apebajref`, `apebajtem`, `imppregas`, `adjimp`, `inccom`, `utepar1/1r/1a`, `impada`, `impadatot`,
`divcam`; y los campos libres `cam1`…`cam6`. `obrx` (1 fila por obra) no tiene ninguna columna
porcentual. **Ninguna columna de `obr` es un porcentaje 0-100 ni 0-1**: el único deducible es la
baja de licitación `impadj / implic`, que solo tienen **18 obras**, y es del lado de la **venta**.

## 6 · La comprobación empírica: ningún importe es múltiplo constante del ABC

Para las **57 obras con versión ABC** (`amb = 8` y `ABC` en `tex` o `res`), `SUM(can*pre)` de su
última versión ABC como denominador y las demás combinaciones `(obra, ámbito, versión)` como
numerador, agregado por ratio a dos decimales (obras distintas que lo repiten):

| ratio | amb 8 | amb 11 | amb 9 | amb 3 | | ratio | amb 8 | amb 11 | amb 9 | amb 3 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1,00 | **57** | 15 | 12 | 6 | | 0,96 | 18 | 16 | 11 | 10 |
| 0,99 | 33 | 15 | 8 | 4 | | 0,95 | 17 | 13 | 7 | 9 |
| 0,98 | 27 | 19 | 12 | 9 | | 0,94 | 16 | 12 | 14 | 7 |
| 0,97 | 22 | 18 | 7 | 4 | | **0,80** | **0** | — | 4 | — |

**Es una campana continua centrada en 1,00 que decae sin un solo escalón.** Ratios redondos
exactos del ámbito 8: **0,75 → 0 obras · 0,80 → 0 obras · 0,85 → 2 · 0,90 → 3 · 0,95 → 17 obras
en 32 versiones** (ese 0,95 es la banda de ruido 0,945-0,955, no un salto: sus vecinos 0,94 y
0,96 tienen 16 y 18. **Si existiera un «coste objetivo = ABC × k» con k fijo, el 0,80 o el 0,90
tendría decenas de obras y sus vecinos ninguna. Pasa lo contrario.**

**Por obra**, el ratio **mínimo** entre sus versiones del ámbito 8: **20 obras no bajan de 1,00 ·
31 se quedan en 0,90-0,99 · 2 en 0,80-0,89 · 2 en 0,70-0,79 · 2 por debajo** (versiones
incompletas, una a 0,00). **51 de las 57 no tienen NINGUNA versión un 20 % por debajo de su ABC.**
En los ámbitos 3, 5, 7 y 9, en cambio, el ratio recorre **toda** la escala sin huecos (0,50 0,51
0,52 … 1,02, con 4 a 12 obras en cada peldaño) porque ahí `fas` es el **mes** y se mide una curva
de acumulación. **Ese contraste es la prueba negativa más limpia**: donde hay serie temporal salen
todos los ratios; donde hay versiones solo los cercanos a 1. Nunca un múltiplo fijo.

## Subproducto: Sigrid guarda «cuál es la versión del planificado», pero caducada

El campo extendido de obra `cod = '15'` («Número Versión Planificación Informe Planificación»,
`defext.ide = 31`) está informado en **123 obras** con un número de versión de 0 a 43, y **56 de
las 57 con ABC lo tienen**. Pero **no apunta al ABC**: de esas 56 solo **2** coinciden con la
última versión ABC y **54 apuntan a una posterior**; contra la última versión del ámbito 8 solo
**23 de 123** están al día. **Indicio de que Negocio quiere fijar «la versión buena», inservible como dato.**

## Lo que hay que preguntarle al humano

1. **¿Quién fija el porcentaje y con qué granularidad?** ¿Por empresa, por obra, por capítulo? En Sigrid no hay sitio para ninguno de los tres.
2. **¿Sobre qué ABC se aplica?** Sobre el último, sobre el del año, sobre la obra completa.
3. **¿Dónde vive hoy?** Hoja de cálculo, criterio de dirección, correo. Si Negocio lo mantiene
   fuera, la vía honesta es **parametrizarlo** (`config/business_rules.yaml`) y decir en la ficha
   del diccionario que **no viene de Sigrid**, con su fecha y su dueño.
4. **Aviso**: implementarlo sin respuesta publicaría una cifra plausible y falsa, justo el fallo que la regla `R-FRESCURA` del diccionario existe para evitar.

---

# CORRECCIÓN DEL 2026-09-18: EL % SÍ ESTÁ EN SIGRID, Y ESTABA DONDE NADIE MIRÓ

**El veredicto de arriba —«NO ESTÁ EN SIGRID»— es FALSO, y conviene entender por
qué se falló, porque el error es instructivo.** Lo resolvió **Elena Díaz
(Control de Costes)** con un correo de las **10:00 del 2026-09-18**: una captura
de la ficha de Sigrid **con la casilla rodeada a mano en rojo**.

## El hallazgo: las magnitudes de planificación son OFERTAS DE PROVEEDORES FICTICIOS

**El coste objetivo no es una versión del presupuesto de la obra: es UNA OFERTA
MÁS dentro del comparativo**, presentada por un proveedor que no existe. En la
captura, el comparativo de la obra 0696 tiene **seis ofertas** y tres de ellas
son de proveedores inventados:

| # | proveedor | importe | estado |
|---|---|---|---|
| 1 | **00021 OFICINA TÉCNICA** | 100.262,40 | REJ |
| 2 | **04440 PLANIFICACIÓN CUATRIMESTRAL** | 99.846,23 | REJ |
| 3 | **00010 OBJETIVO-RUESMA** (NIF `A99999999`) | **94.853,91** | REJ |
| 4 | 5948 RIVISA INDUSTRIAL | 94.212,24 | **ADEF** |
| 5 | 41000347 VALLADOS SIETE PICOS | 99.955,50 | REJ |
| 6 | 4681 CESAR MOLPECERES | 135.053,17 | REJ |

**La cuenta cuadra al céntimo**: 99.846,23 (cuatrimestral) × 0,95 = **94.853,92**
frente a los 94.853,91 del objetivo. **El objetivo es el cuatrimestral con el 5 %
de descuento**, y ese 5 % es lo que Elena rodeó: la columna **`Dto`** de las
líneas de detalle.

## Dónde vive, medido

**`dcopro.dto`**, el descuento de la línea de la oferta. **Y es TEXTO, no un
número**: trae `'15%'`, `'10,08%'`, `'5%'`, `'13,79%'` —con el símbolo y con
coma decimal española—. Una consulta que lo trate como número **revienta**: el
motor devuelve `22018 Error de conversión`. Quien lo modele tiene que parsearlo.

**Cobertura sobre los 20.261 comparativos**, por el nombre de la entidad de la
oferta (`dco.entres`):

| familia | comparativos |
|---|---|
| ofertas REALES | 19.909 |
| **OBJETIVO** | **11.088 (54,7 %)** |
| **OFICINA TÉCNICA** | **7.061** |
| PLANIFICACIÓN | 4.769 |
| **FASE 0** | 819 |
| CUATRIMESTRAL | 679 |

Y las entidades ficticias con más ofertas: `00645 PLANIFICACION` 2.567, **`00010
OBJETIVO RUESMA` 2.303** (CIF `A99999999`), **`00021 OFICINA TECNICA` 2.003**
(CIF `A00000000`), `00010 OBJETIVO-RUESMA` 1.947, `00021 OFICINA TÉCNICA` 1.183,
`04440 PLANIFICACION CUATRIMESTRAL` 411, `02700 PLANIFICACION " FASE 0 "` 459.

**LOS NOMBRES NO ESTÁN NORMALIZADOS** —con tilde y sin tilde, con guion y sin
guion, con asteriscos `*OBJETIVO*`— y **el mismo código de entidad se repite con
razones sociales distintas**. Identificarlos por `entres` con un `LIKE` es lo
que funciona hoy, pero es frágil: los CIF falsos (`A99999999`, `A00000000`) son
una señal mejor y hay que medir su cobertura antes de elegir.

## Por qué la búsqueda anterior falló, que es la lección

Las seis vías de arriba buscaban **un porcentaje fijo aplicado al ABC del
presupuesto de la obra**. La vía 6 concluyó que no existía porque **ningún
importe es múltiplo constante del ABC**. Esa medición era CORRECTA y la
conclusión que se sacó de ella, equivocada:

**el porcentaje no es fijo — cada comparativo tiene el suyo**. Medidos: 15 %,
12 %, 10,08 %, 3,5 %, 8,25 %, 20,09 %, 14,33 %, 23,13 %… Buscar un escalón en
la distribución de ratios **no podía encontrar nada**, porque no hay un ratio,
hay miles.

Y el segundo error, más de fondo: **se buscó en el presupuesto de la obra porque
ahí viven el ABC y la fase 0**, sin caer en que el objetivo del COMPARATIVO se
fija **en el comparativo**. El dato estaba a un `JOIN` de lo que ya se había
medido.

**Moraleja para la siguiente vez que una búsqueda salga vacía**: un negativo bien
demostrado sigue siendo un negativo **sobre la hipótesis que se probó**, no sobre
la pregunta. Y cuando alguien de Negocio dice «esto existe», existe: lo que falla
es dónde lo buscamos.
