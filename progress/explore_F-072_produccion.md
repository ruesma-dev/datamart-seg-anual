# F-072 · Censo semántico de `raw` — bloque PRODUCCIÓN, PARTIDAS Y MAQUINARIA

Explorador, 2026-09-09. `apu`, `apa`, `asi`, `cua`, `hmo`, `hmores`, `auxefp`, `auxobrtca`. **Todo solo lectura.**

**Procedencia.** `[DOC]` = `azure-apps/sigrid_tablas.md` · `[API]` = medido contra el Sigrid vivo por `sigrid-api` · `[RAW]` =
medido sobre `raw` en el Postgres.

**Método.** Barrido completo `[RAW]` en `hmores`, `asi`, `cua`, `hmo`, `auxefp`, `auxobrtca`. Muestreo en las dos grandes:
`apu` (2,15 M / 497 MB) con `TABLESAMPLE SYSTEM (2)` y `(1)` — 44.473 y 21.700 filas; `apa` (710 k / 128 MB) con `SYSTEM (10)` —
70.225 filas. Recuentos totales, rangos de fecha y **todas** las comprobaciones de relación van `[API]`, sobre la tabla entera.

## 1. Corrección de partida: `apu` y `apa` NO son análisis de precios unitarios

El encargo lo daba por hecho. `[DOC]` es tajante: **`apu` = «Apuntes Contables»**, **`apa` = «Desglose analítico»** del apunte.
Son el mayor contable.

**Busqué el análisis de precios de verdad. Está en el esquema y está vacío:**

| pieza | qué es `[DOC]` | dato real `[API]` |
|---|---|---|
| `catest` | `padide`→`proide` con `canren` **Rendimiento** y `canfac` Factor: el APU relacional de libro | **0 filas** |
| `catpro` | banco de precios, con `natide`→`auxpronat` = **naturaleza** (mano de obra / material / maquinaria) | **0 filas** |
| `obrparres` | `paride`×`reside`: qué recursos usa cada partida | **0 filas** |
| `obrparpar.proide`→`pro` | ata la partida a un precio del banco | **106 de 392.209** (0,03 %) |
| `obrparpre.des` + `haydes` | «Descomposición desglose», **Texto ilimitado** | `haydes=1` en **1.731.245 de 13.885.098** |

**Hallazgo de primera: Ruesma no usa el módulo de banco de precios de Sigrid.** La descomposición que sí existe vive dentro de
`obrparpre.des`, **un blob de texto por fila de presupuesto**, no una tabla relacional. Responder «de qué está hecho el precio
de esta partida» exige parsear ese blob: es un proyecto, no una tabla procesada más.

**Lo que sí distingue mano de obra de maquinaria y material no está en el presupuesto, está en el coste real: `hmores` ×
`auxhor`.** Es la vía practicable y está casi entera en `raw` (falta el catálogo). **Jerarquía de partidas** `[API]`:
`obrparpar` son 392.209 filas, 389.698 con `padide` (99,4 %), 45.157 padres; `tip`=0 capítulos (≈45,5 k), `tip`=1 partidas. Es
un árbol de capítulos, **no** una descomposición de precio, y `stg.partidas` ya lo modela.

## 2. Fichas

### `raw.hmores` — la línea del parte: quién, qué obra, qué partida, cuántas horas, cuánto cuesta

- **Grano**: una imputación al parte. Recurso × obra × partida × fecha × tipo de hora.
- **Volumen**: 329.170 `[RAW]` / **329.265 `[API]`** (`raw` va 95 filas por detrás: son los partes de hoy). 111 MB, 56 columnas.
  `fec` 2002-2026 `[API]`, grueso desde 2017; 40.062 líneas en 2025.
- **Se une por** (declarado `[DOC]`, comprobado con `LEFT JOIN` `[API]`): `obride`→`obr` **0 huérfanos**, 536 obras, y **las 535
  con dato están las 535 en `maestro.obras`** `[RAW]` · `paride`→`obrparpar` **0 huérfanos sobre 301.498**, y **las 5.773
  partidas están las 5.773 en `stg.partidas`** `[RAW]` · `hmoide`→`hmo` 0 huérfanos · `reside`→`res` 0 huérfanos ·
  `horide`→**`auxhor`, que NO está ingerida**: el único destino que falta.
- **Columnas que importan** (% sobre 329.170 `[RAW]`): `reside` 99,997 % (1.983) · `horide` 99,997 % (55 valores) · `fec` 99,999
  % · `cenide` 99,62 % (536) · `obride` 99,58 % (536) · `caaide` 93,93 % (3.766) · `paride` **91,58 %** (5.774) · `can`≠0 97,3 %
  · `pre`≠0 96,8 % · `tot`≠0 96,7 %, **suma 98,0 M€** · `empdpreide` 30,5 %.
- **Columnas vacías o inútiles** `[RAW]`: a cero total `cuaide`, **`maqide`**, `maqopeide`, `taride`, `tarreside`, `ortide`,
  `dvaproide`, `dvfproide`, `dvpide`, `resconide`, `resrspide`, `hdereside`, `fabproide`, `verirec1/2`, `prenomcon`, `canven`,
  `haycanven`, `canres`, `vehhor`, `cenmul`. Residuales: `prenom` 27, `preven` 103, `vehkil` 2, `proide` 1, `prvide` 72,
  `emprccide` 16, `empabside` 16, **`fac`=1 en 7 filas** `[API]`. **La mitad de las 56 columnas no lleva dato.**
- **TRAMPA MEDIDA: `can` no tiene unidad homogénea.** La fija `horide`: `H*` horas, `M*` **meses**, `KM` kilómetros,
  `CD/CG/CA/CO` euros de caja. Precio medio 488,40 €/unidad `[RAW]`: la media de un mes de jefe de obra con una hora de peón.
  Sumar `can` en bruto da un número sin significado.
- **Cómo funciona** (`[DOC]` + ejemplo real `[API]`): el jefe de obra abre un parte (`hmo`) por obra y centro; imputa líneas con
  recurso, día, tipo y cantidad; Sigrid las valora con `pre` y calcula `tot`. El parte con más líneas de 2026: **480 líneas, 23
  partidas, 10 recursos, del 30-ene al 31-dic** — **el parte no es mensual** pese a tener `ano` y `mes`. Su reparto: MJG jefe de
  grupo 104 líneas / 14 **meses** / 126.000 €; CO caja-otros 89 / 10.130 €; OGAS gasoil 104 / 4.690 €; MESVE vehículo 71 / 4.200
  €; KM 665 €; OTEL móvil 560 €; y dos líneas de absentismo a importe
  0. En una sola tabla: personal, maquinaria, consumos, caja y absentismo, cada uno con su unidad.
- **Qué permitiría responder que hoy no se puede**: cuántas horas y cuánto de mano de obra propia lleva **esta partida**; qué
  parte del indirecto de una obra es jefe de obra, encargado, maquinaria, dietas, gasoil o EPIs; cuánto absentismo soporta una
  obra.
- **Enrutado**: **F-057** y **F-061**, es *la* tabla de las dos. Y da a **F-036** la categoría oficial del trabajador, la mitad
  de lo que pide.

**`auxhor`, el catálogo que falta** (60 filas `[API]`, 55 en uso, no ingerido). Sin él `horide` son 55 enteros mudos. Reparto
por importe de toda la serie `[RAW]` etiquetado `[API]`: jefatura (MJEFO, MENC, MAJO, MJG) **54,1 M€** · oficial (HLOF, HEOF)
15,2 M€ · capataz (MCAP, HCAP, HECAP) 8,3 M€ · técnicos (MADM, MPRL, MING) 7,9 M€ · gruista (HLGR, HEGR) 7,4 M€ · **maquinaria
(MESGR grúa torre, MESMQ, MESVE vehículo, MESCA caseta) 1,5 M€** · peón (HLPE, HEPE) 1,2 M€ · consumos (OGAS gasoil, OTEL móvil,
OTRO) 2,0 M€ · caja de obra (CD dietas, CG combustible, CA alojamiento, CO otros) 0,5 M€ · EPIs `SS-*` y absentismo `CI*`
residual. **Ingerirlo es la acción más barata y rentable del bloque.** Y ahí está la maquinaria del título: no en
`hmores.maqide` (vacío), sino en MESGR/MESMQ/MESVE.

### `raw.hmo` — la cabecera del parte: obra, centro y poco más

- **Grano**: un parte de trabajo. **Volumen**: 6.859 `[RAW]` / 6.862 `[API]`, 936 kB.
- **Se une por**: `obride`→`obr` (540 valores) · `cenide`→`cen` · `ide`→`con` («propiedades de `con`» `[DOC]`). Recibe
  `hmores.hmoide`, 0 huérfanos `[API]`.
- **Columnas que importan** `[RAW]`: `cenide` 100 % (538) · `obride` 99,4 % · `ano` 99,7 % · `mes` 99,97 %. Nada más.
- **Columnas vacías o inútiles**: **`caaide` está informada en las 6.859 filas pero tiene UN solo valor distinto** — el caso de
  libro de «100 % informado y a cero»; igual `synckey`, y **`cla`=0 en las 6.862 filas `[API]`**. A cero: `feccie`, `hpcide`,
  `ppoide`, `resequide`, `pexide`, `fabproide`, `cenmul`. `reside` tiene 6 valores: el recurso va en la línea. **Suciedad**: 21
  filas con `ano`=0 y 5 con años imposibles (22, 211, 11226, 201311, 201831); el año fiable es `hmores.fec`.
- **Cómo funciona / Enrutado**: contenedor administrativo. Se abre por obra y no se cierra —el ejemplo de arriba abarca once
  meses—, y todo lo que cambia después pasa en `hmores`; `feccie` («fecha cierre diario») está vacía, **nadie cierra los
  partes**. Va a **F-057** como dimensión menor: no construyas sobre `hmo` lo que puedas construir sobre `hmores`.

### `raw.apa` — el desglose analítico del apunte: coste contable por obra y concepto

- **Grano**: una línea analítica de un asiento; cada apunte financiero se reparte en una o varias con centro de coste y cuenta
  analítica `[DOC]`.
- **Volumen**: 709.759 `[RAW]` / **709.850 `[API]`**, 128 MB, 20 columnas, 2008-2026.
- **Se une por**: `cenide`→`cen` **99,98 %** (603 centros) `[RAW]`, **y de ahí a la obra** por el puente de §3: **98,8 % de las
  filas y 93,2 % del debe** de la muestra · `cueide`→**`caa`, cuenta ANALÍTICA, no `cua`** `[DOC]`, comprobado `[API]`: contra
  `caa` **0 huérfanos**, contra `cua` **709.723 huérfanos, o sea todos** — el nombre `cueide` habría llevado a cualquiera a la
  tabla equivocada; los literales salen de `con` (`0517.C — OBRA COMPLETA (constructoras)`, `GG.GES — Salarios y Seguridad
  Social`) · `apuide`→`apu` 88,4 % · `conide`→`con` **100 %** `[API]`, así que las 82.305 filas sin apunte (83,3 M€ de debe, 8,0
  %) cuelgan igualmente del asiento · **`obride` está a CERO en el 100 % de las filas** `[RAW]`: inservible pese al nombre.
- **Columnas que importan** (muestra 10 %): `conide` 100 % (43.826 asientos) · `fec`, `cod`, `res` 100 % · `cenide` 99,98 % ·
  `cueide` 99,98 % (10.716) · `deb`≠0 90,5 % · `hab`≠0 8,0 %.
- **Columnas vacías o inútiles**: `obride` 0, `del`, `delo`, `doc` 0, **`ori` y `canal` a 0 en las 709.850 filas `[API]`**,
  `pun` 17, `obr` 32 (0,05 %).
- **Cómo funciona**: se contabiliza un asiento (`con`+`asi`), sus líneas financieras van a `apu` y, **al imputar a centro de
  coste**, Sigrid deriva el desglose analítico a `apa` con la cuenta del concepto. Encadena con compras: la factura de proveedor
  genera el asiento y el asiento genera el analítico de la obra. La analítica puede ser más fina que el apunte (varias `apa` por
  `apu`) o existir sin él (12 %).
- **¿Llega a la partida? NO, y conviene decirlo.** `obrparpar.caaide` está informado en 201.914 de 392.209 partidas (51,5 %,
  40.775 cuentas) `[API]`, así que tienta unir por cuenta analítica. **No vale**: solo el 14,9 % de las filas de `apa` tienen
  una cuenta que sea de partida, y cada cuenta cuelga de 5 partidas de media y hasta **3.659**. Es un concepto de coste de obra,
  no una clave de partida.
- **Qué permitiría responder**: la **cuenta de resultados contable de una obra**, contra lo que dice el cierre del jefe de obra
  —dos versiones de la verdad, y la diferencia es información de negocio—; cuánto de salarios absorbe cada obra; qué obras
  tienen coste contable sin cierre.
- **Enrutado**: **F-058** y **F-061**. No F-036 ni F-002.

### `raw.apu` — el apunte contable: el mayor, línea a línea

- **Grano**: una línea de asiento sobre una cuenta financiera.
- **Volumen**: **2.156.121 `[API]`**, 497 MB, 36 columnas. **La tabla más grande de `raw`.** `fec` **20080101 – 20260909**
  `[API]`.
- **Se une por**: `asiide`→`asi` **0 huérfanos sobre 2.156.121** `[API]` · `cueide`→`cua` (cuenta financiera) **0 huérfanos
  sobre 2.155.827** `[API]` · `cenide`→`cen` 54,5 % · `empide`→`con` (tercero) 48,4 %. **A la obra llega solo por `cenide`**:
  54,5 % de las filas pero **26,8 % del debe** (26,9 M€ de 100,4 M€ en muestra) — el resto es tesorería y balance, que no tienen
  obra. `obr` (texto) informado en **1 fila de 44.473**: inservible, como ya avisaba el yaml.
- **Columnas que importan** (muestra 2 %): `asiide`, `fec`, `cod`, `res` 100 % · `cueide` 99,98 % (7.404 cuentas) · `deb`≠0 54,3
  % / `hab`≠0 45,1 % · `cenide` 54,5 % (514) · `empide` 48,4 % (1.590) · `info` 37,5 % (`A0`, `I0`, `A2`, `R0`…) · `pun` 19,3 %.
  Debe por grupo PGC en muestra: grupo 4 (13.240 líneas, 53,6 M€), grupo 5 (2.035, 24,8 M€), **grupo 6 gastos** (4.579, 21,7
  M€), grupo 1 (134, 5,8 M€). `cla` `[API]`: 0 en 2.054.817, −1 en 49.332, 3 en 47.968, 1 en 4.004.
- **Columnas vacías o inútiles** (0 en toda la muestra `[RAW]`): `concil`, `cptide`, `pexide`, `pcaide`, `pcatip`, `pdpide`,
  `cuectride`, `anacueide`, `fecven`, `fec1`, `num1`, `tex1`, `docnum`, `jus`, `del`, `delo`. `doc` 0,25 %; `doctip` solo `''` o
  `'0'` `[API]`; **`canal`≠0 en 8 filas de 2.156.121 `[API]`**. **Diecisiete de 36 columnas no llevan dato.**
- **Cómo funciona**: el asiento nace del ciclo de compra o venta (factura → asiento) o a mano; sus líneas son `apu`, cuadradas
  contra `asi`; **la fecha y la empresa no viven aquí ni en `asi`, viven en `con`**; y si la línea lleva centro de coste, Sigrid
  deriva el analítico a `apa`. Un asiento real `[API]`: 140 apuntes y **0 líneas `apa`** — no todo asiento genera analítica.
- **Qué permitiría responder**: balance y cuenta de resultados por empresa y ejercicio; qué tercero concentra el gasto; qué
  asientos manuales tocan una obra. Para *coste por obra*, `apa` es mejor fuente.
- **Enrutado**: **F-056** y **F-058**. A **F-061** le aporta el grupo 64 —cuánto costó el personal—, que `hmores` no sabe.

### `raw.asi` — la cabecera del asiento, y está casi vacía

- **Grano**: un asiento. **Volumen**: 783.847 `[RAW]` / 783.968 `[API]`, 80 MB.
- **Se une por**: `ide`→`con` **0 huérfanos** `[RAW]`; ahí viven **fecha** (`con.fec`), **empresa** (`con.emp`), código y
  resumen. Recibe `apu.asiide`, 0 huérfanos `[API]`.
- **Columnas que importan**: `deb` y `hab` ≠ 0 en 99,77 %, con **11.646 M€ a cada lado** y cuadre al euro sobre toda la serie
  (…201 vs …211) `[RAW]`.
- **Columnas vacías o inútiles**: **`ori` tiene un solo valor (0) en las 783.968 filas** `[API]` — otro «100 % informado y a
  cero»; `canal`≠0 en **2 filas** `[API]`; `cptide` y `pexide` a cero en todas. Fuera de `deb`/`hab` no dice nada.
- **Cómo funciona**: es la mitad contable de un registro que empieza en `con`. `[DOC]` lo anuncia («Propiedades de `con` 11») y
  el dato lo confirma: sin `con` no se sabe ni de qué día ni de qué empresa es el asiento.
- **Enrutado**: **F-056**, pieza de paso. No merece objeto propio: se resuelve dentro del SQL que construya el mayor.

### `raw.cua` — la extensión de las cuentas financieras imputables

- **Grano**: una cuenta del plan financiero, «propiedades de `con`» 1:1 `[DOC]`.
- **Volumen**: 34.148 `[RAW]` / 34.153 `[API]`, 4,4 MB, 16 columnas.
- **Se une por**: `ide`→`con` **0 huérfanos** `[RAW]` (de ahí código y nombre) · `padide`→`cug` **0 huérfanos sobre 33.801**
  `[API]`. Recibe `apu.cueide`.
- **Columnas que importan**: dos. `padide` 98,97 % (3.022 padres) y `niv`, con **dos valores**: 254 cuentas de nivel 0 y 33.899
  de nivel 5 `[API]`.
- **Jerarquía: sí, pero incompleta aquí.** Solo guarda los escalones 0 y 5; los niveles intermedios viven en `cug`/`con` y
  **`cug` no está ingerida**. El árbol de cuentas se monta sobre `con`, no sobre `cua`.
- **Columnas vacías o inútiles** (0 en las 34.148 `[RAW]`; `cla`=0 en todas `[API]`): `prpide`, `prbide`, `divcod`, `divregexc`,
  `divregmod`, `pcacod`, `pcatip`, `cla`, `codagr`, `difposide`, `difnegide`, `mesalta`, `ejealta`. **Trece de dieciséis.**
- **Cómo funciona**: la cuenta nace en `con` (tip=16) con código y nombre; `cua` solo marca **cuál es imputable** (nivel 5) y
  cuál de agrupación (nivel 0). Ese es el filtro que evita sumar dos veces al agregar el mayor.
- **Enrutado**: **F-056**, como dimensión. Poco más.

### `raw.auxefp` — el catálogo de formas de pago

- **Grano**: un medio de pago. **Volumen**: **10 filas**, 32 kB, **las 10 activas**: `fecbaj`=0 en todas `[API]` (en `[RAW]`,
  los 64/128/192 que parecen fechas son `pos`).
- **Se une por** `[DOC]`: `ctr`, `dcf`, `dco`, `dca`, `pag`, `cob`, `prv`, `prvobrpag`, `auxpag`. **Uso real `[RAW]`**: 165.535
  de 165.539 facturas (99,998 %), 309.906 de 309.937 albaranes, 72.231 de 72.260 ofertas, 18.921 de 18.929 contratos. **Todos
  esos destinos ya están en `compras.*` y ninguna columna de ninguna capa procesada expone hoy la forma de pago** `[RAW]`.
- **Columnas que importan**: `cod`, `res`, `pos` y `cla`, que agrupa `[API]`: 1 transferencia, 2 recibo y tarjeta, 3 efecto
  (pagaré, letra), 4 cheque, 5 confirming, 0 efectivo y compensación.
- **Reparto real** (contratos / facturas) `[RAW]`: PAGARÉ 12.674 / 83.104 · CONFIRMING-PAGARÉ 3.576 / 19.024 · SÓLO CONFIRMING
  1.528 / 9.267 · TRANSFERENCIA 871 / 18.792 · RECIBO 204 / 30.427 · CHEQUE 39 / 773 · **COMPENSACIÓN SALDOS: 0 usos**.
- **Cómo funciona**: se pacta en el contrato (`ctr.efeide`), viaja a la oferta y al albarán y llega a la factura, que dispara el
  vencimiento. Es el mismo dato recorriendo el ciclo de compra entero; por eso está informado en el 99,99 % de todo.
- **Qué permitiría responder**: cuánto de la compra de una obra se paga por confirming y cuánto por pagaré; qué proveedores
  concentran el confirming.
- **Enrutado**: **no encaja en F-036, F-057, F-061 ni F-002.** Es una dimensión de dos columnas para `compras.*`; que entre de
  acompañante en la próxima feature de compras.

### `raw.auxobrtca` — el catálogo de tipos de capítulo: está muerto

- **Grano**: un tipo de capítulo. **Volumen**: **3 filas** — `0001 INSTALACIONES`, `0002 DEMOLICIONES`, `0003 CARPINTERIA DE
  MADERA`—, con `codpre`, `codpri`, `codfis` y `tex` vacíos en las tres.
- **Se une por** `[DOC]`: `obrparpar.tcaide`, `pro.tcaide`, `catpro.tcaide`, `contca.tcaide`. **Uso real `[API]`: obrparpar 0,
  pro 0, catpro 0, contca 12.** En `[RAW]`, `obrparpar.tcaide` está a cero en las 392.207 partidas.
- **Cómo funciona**: no funciona. Alguien creó tres etiquetas y nadie las asignó nunca.
- **Enrutado — DESMIENTE A F-036.** El punto (3) de su ficha dice: «sustituir la heurística CD/CI/CP/OTRO por el catálogo
  oficial `obrparpar.tcaide` → `auxobrtca`, AMBOS YA INGERIDOS». **Ese camino no existe**, verificado contra el Sigrid vivo; hay
  que corregir la ficha antes de que alguien lo implemente. El sustituto razonable, con lo medido: `auxhor` para el oficio de la
  mano de obra propia y `prv.ofcide`/`auxofc` para el del proveedor — los otros dos puntos de esa misma ficha, que sí se
  sostienen.

## 3. Hallazgo transversal: el puente centro de coste → obra existe y es 1:1

`[DOC]` declara `cen.obride` → `obr`. **El dato lo desmiente: está a 0 en las 804 filas, tanto en `[RAW]` como en `[API]`.** Es
la contradicción documento/realidad más cara del bloque, porque ha bloqueado dos features. La relación real es que el centro de
coste y su obra **son dos filas de `con` con la misma empresa y el mismo código**:

```sql
raw.cen n JOIN raw.con cc ON cc.ide = n.ide
          JOIN raw.con co ON co.emp = cc.emp AND co.cod = cc.cod
          JOIN raw.obr o  ON o.ide = co.ide
```

Medido `[RAW]`: **683 pares, 683 centros distintos, 683 obras distintas, 0 ambigüedades.** Estrictamente 1:1. **No** es la
aritmética que sugería F-045: solo 436 de 683 cumplen `cenide = obride + 1` (64 %) y 4 cumplen `−1`; hay que construirlo por
código. Coherente con `[API]`: 648 de los 804 centros tienen `cla`=42, la clase «obra».

**Resuelve `retenciones.movimientos.obra_id` en 261 de 261 valores** `[RAW]`, que es exactamente el agujero de F-045 (hoy casan
0 de 261 contra `maestro.obras`). Es también el bloqueo declarado de F-061 y lo que hace utilizable `apa`. Los 121 centros que
no resuelven son estructura, delegación y servicios generales: no todo centro es una obra.

## 4. Lo que yo construiría, y en qué orden

1. **Ingerir `auxhor` (60 filas) y publicar `stg` + `mart` sobre `hmores`.** Lo mejor del bloque y no depende de nada: 329 k
  líneas que llegan al 100 % a `maestro.obras` y al 100 % a `stg.partidas`, con recurso, fecha, cantidad, precio e importe. Sin
  `auxhor` la tabla es ilegible; con él separa mano de obra por categoría, maquinaria, consumos, dietas, EPIs y absentismo.
  Alimenta **F-057** y **F-061** y da a **F-036** la mitad de lo que pide. El único diseño delicado es la unidad de `can`, que
  cambia con `horide`: hay que modelarla explícitamente, nunca sumarla en bruto.
2. **El puente centro → obra, como objeto propio en `maestro`.** Cuarenta líneas de SQL, 1:1 verificado; desbloquea **F-045**
  (261/261), habilita **F-061** y hace utilizable `apa`. El mejor ratio esfuerzo/valor de todo lo medido, y no lo pedía nadie.
3. **`apa` como coste contable por obra y concepto analítico.** Con el puente hecho, el 98,8 % de las filas y el 93,2 % del debe
  caen en una obra concreta, con el concepto nombrado desde `con`. Es la segunda versión de la verdad frente al cierre:
  **F-058**, y el contraste que **F-061** necesita. Que la spec deje escrito que **no baja a partida**.
4. **`apu` + `asi` + `cua`, juntos y solo dentro de F-056.** No merecen tres objetos: `asi` no aporta más que `deb`/`hab`, `cua`
  aporta dos columnas y la fecha y la empresa están en `con`. Son el mayor contable: se construyen de una vez o no se
  construyen. Ojo al coste: 497 MB y 17 de 36 columnas vacías en `apu`.
5. **`auxefp` como dimensión de dos columnas en `compras`.** Diez filas, 99,99 % de uso en facturas y albaranes, y hoy la forma
  de pago no existe en ninguna capa procesada. Media hora. No merece feature propia.
6. **`hmo`: no construir nada encima** (cuatro columnas útiles, siete vacías, nadie cierra los partes) y **`auxobrtca`:
  descartar y corregir la ficha de F-036** antes de que alguien implemente un camino que no existe.
7. **No prometer «de qué está hecho el precio de una partida»** (§1): el banco de precios está vacío y la descomposición vive en
  un blob. Es un proyecto de parseo, no una tabla procesada, y conviene que el humano lo sepa antes de comprometerlo.
