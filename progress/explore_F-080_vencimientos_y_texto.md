<!-- progress/explore_F-080_vencimientos_y_texto.md -->
# Exploración F-080 · Vencimientos y texto de la factura de compra (Sigrid)

> Origen: petición de Juan Romero por correo el 2026-09-10
> («PETICIONES (TEXTO Y VENCIMIENTOS/FORMAS PAGO)»). Exploración de SOLO
> LECTURA sobre documentación (`azure-apps/sigrid_tablas.md`,
> `config/tables_sigrid.yaml`, informes del censo F-072 y de F-074).
> **No se ha consultado la base en vivo**: donde no hay cifra medida se
> escribe «no consta en las fuentes».

## Tabla resumen de candidatas

| Tabla | Qué es | Grano | ¿En `raw` hoy? | Volumen |
|---|---|---|---|---|
| `dcf` | **Factura de compra** (cabecera) | 1 fila por factura | Sí, **con `tex` excluido** | ~163.000 |
| `dca` | Albarán de compra (NO es la factura) | 1 fila por albarán | Sí, excluye `tex`, `pagfor`, `pagtex` | ~305.000 |
| `pag` | **Pagos**: efectos/vencimientos de compra | 1 fila por vencimiento | Sí (excluye solo `blores`) | 254.856 (2026-09-09) |
| `cob` | **Cobros**: efectos/vencimientos de venta | 1 fila por vencimiento | Sí | 21.802 (2026-09-09) |
| `con` | Documento genérico (superclase) | 1 fila por documento | Sí, **con `tex` excluido** | no consta |
| `auxpag` | Catálogo Formas de Pago | 1 fila | Sí | 69 |
| `auxefp` | Catálogo Tipos de Medios de Pago | 1 fila | Sí | 10 |
| `auxnap` | Catálogo Naturalezas de Pagos | 1 fila | **No** | no consta |
| `auxban` | Catálogo Bancos y Sucursales | 1 fila | **No** | no consta |
| `cua` | Cuentas auxiliares (incl. bancarias) | 1 fila por cuenta | Sí | 34.139 |
| `dvf` y familia | Documentos de VENTA | — | **No** (F-040) | no consta |
| `cvecyp` | «Efectos de un contrato» de venta a promotoras | 1 fila | No | no consta |

## 1 · La cabecera de la factura de compra

**No es `dca`** (eso es el albarán de compra, `sigrid_tablas.md:7579`). Es
**`dcf`, «Factura de compra»** (`sigrid_tablas.md:7892`), `tip = 15`.
Series FR/FRGG (factura) y AB/ABGG (abono, importes negativos).

Campos relevantes de `dcf`:

* **Forma de pago**: `pagide` → `auxpag`; además `pagtex` (Con. Pago) y
  `pagfor` (Fórmula Pago), las dos recuperadas por F-066.
* **Medio de pago**: `efeide` → `auxefp`.
* **Naturaleza**: `cypnatide` → `auxnap` (**catálogo no ingerido**).
* **Cuentas**: `cueide` → `cua` (cuenta del tercero); bloque bancario propio
  `banide` → `cua`, `banban`/`bansuc` → `auxban`, `bandig`, `bancue`, `ban`
  (CCC completo), `bantipide` → `auxcueban`.
* **Estado**: hereda `con.est`, cuyo catálogo por tipo es `conest`; para
  `tip = 15` hay **26 estados** (Recibida, Comprobada, Contabilizada,
  Aprobada por jefe de obra/grupo/administración, Aprobado pago, Retenida,
  Rechazada…). Hay además `estped`/`estser`/`estfac` y sus `antest*`.
* **Texto**: campo propio `tex` («Observaciones», texto ilimitado).

## 2 · Los vencimientos: `pag`

Es **`pag`, «Pagos»**, propiedades de `con`, tipo `11`. Grano: **una fila por
vencimiento/efecto**, varias por factura si hay varios plazos.

* Unión con la cabecera: **`pag.conide → dcf.ide`** (mismo `ide` porque `dcf`
  extiende `con`). Confirmado además en la ficha de F-067.
* `tot` (importe), `fecven` (vencimiento previsto), `fecrea` (fecha real de
  pago, **0 = pendiente**), `fecreaemi` (emisión real).
* `efeide` → `auxefp`; `natide` → `auxnap`; `cueide` → `cua`;
  `banide` → `cua`; `banban`/`bansuc` → `auxban`; `bancue`, `ban`.
* `retide` (retención asociada), `cenide` (centro de coste), `entide`, `pun`.

**Dos cosas que la captura enseña y el diccionario NO confirma:**

* El **estado CAR/PDT** de la rejilla no existe como campo en `pag`. Lo
  medido es que `fecrea = 0` significa pendiente. Que la interfaz derive el
  rótulo de ahí es una interpretación razonable, **no un hecho verificado**.
* El **código `FR26/06051_01`**: `pag` no tiene `cod` ni secuencial propio en
  el diccionario. El prefijo es `con.cod` de la cabecera; el sufijo `_01`
  parece un orden que pinta la aplicación. **No consta** que se almacene.

## 3 · Equivalentes en venta y en contratos

* **Venta**: `cob`, «Cobros», misma estructura, con catálogos propios
  `auxefc` (medio) y `auxnac` (naturaleza). Pero `cob.conide` apunta a `dvf`,
  **que no se ingiere** (F-040): el cobro existe como efecto y no como
  documento.
* **Contratos**: no hay tabla de vencimientos de `ctr`. Los efectos llegan a
  `pag` a través de la factura. Existe `cvecyp`, «Efectos de un contrato»,
  pero es del módulo de **venta a promotoras** (`cve`), no de compras, y no
  consta que Ruesma lo use.

## 4 · Dónde vive el bloque de texto

**No hay evidencia de una tabla de comentarios con una fila por comentario.**

* `dcf.tex` («Observaciones», texto ilimitado) y `con.tex` («Texto /
  Observaciones») son campos memo únicos por documento.
* **Los dos están EXCLUIDOS de la ingesta hoy** en `config/tables_sigrid.yaml`.
  La entrada de `con` dice literalmente «texto libre largo, no lo usamos en
  seguimiento»; `dcf` lo repite en `exclude_columns`.
* Precedente: `prvcer.tex` estaba excluido **por el automatismo de la lista
  estándar del módulo COMPRAS, no por una decisión sobre esa tabla**, y F-074
  lo recuperó porque era el único campo que decía de qué trata cada
  certificado.

**Conclusión con la cautela debida.** La estructura (memo único, no tabla de
filas) es segura. El **formato del contenido** —comentarios concatenados con
sello `[dd/mm/aaaa hh:mm:ss Usuario: xxx]` y separadores de guiones— se
deduce de la captura de Juan Romero, **no del diccionario**. Antes de
escribir spec hay que **leer `dcf.tex` en vivo** sobre una factura con varios
comentarios.

## 5 · Los catálogos

* **`auxpag`** (69 filas): `cod`, `res`, `formul` (Fórmula, texto ilimitado),
  `efeide` → `auxefp`, `reccod`, `can`/`cat`, `ser`, `tex`.
* **`auxefp`** (10 filas): `cod`, `res`, `est`, `pagdia`/`pagdiad`/`pagmes`
  (días y meses de pago y diferimiento), `cla` (Clase), `codface`, `codsunat`.
* **`auxnap`**: catálogo mínimo (`ide`, `cod`, `res`, `pos`, `fecbaj`,
  `tiemod`). **No se ingiere.**
* Lado venta: `auxefc` y `auxnac`, tampoco ingeridos.

## 6 · Qué falta por ingerir

1. **`auxnap`** — naturalezas de pago, para dar nombre a `pag.natide` y
   `dcf.cypnatide`.
2. **`auxban`** — bancos y sucursales, para dar nombre a `banban`/`bansuc`.
3. **Recuperar la columna `dcf.tex`** (y decidir sobre `con.tex`). **No es
   una tabla nueva: es dejar de excluir una columna de una tabla ya
   ingerida**, el mismo patrón que `pagfor`/`pagtex` en F-066 y `prvcer.tex`
   en F-074.
4. `dvf` y familia solo si se quisiera el lado de venta (F-040).

Ya están y no hay que tocarlos: `dcf`, `dca`, `pag`, `cob`, `cua`, `prv`,
`auxpag`, `auxefp`, `conest`, `prvcer`.

## 7 · Volúmenes, y lo que hay que medir antes de comprometer nada

* `auxnap`: **no consta**. Por analogía con `auxefp` (10) sería pequeño, pero
  no está medido.
* `auxban`: **no consta**, y es de tipo `TC` (jerarquía banco↔sucursal), así
  que puede ser bastante mayor que los catálogos planos. Hay que medirlo.
* **`dcf.tex`: no consta su tamaño.** La medida más cercana es la de F-066
  sobre otras dos columnas (`pagtex`/`pagfor`: 165.390 de 165.391 facturas
  informadas, 15,6 bytes de media), y **no sirve de referencia**: `tex` es un
  memo de observaciones y puede ser órdenes de magnitud mayor. Medir
  `AVG(LEN(tex))` y `MAX(LEN(tex))` contra Sigrid antes de decidir.
* Referencia de la pasarela (`azure-apps/sigrid_api.md`): `dev` admite
  `max_rows` hasta 500.000 y 230 s de timeout; el patrón medido en F-074 es
  ~10.000 filas por página en ~0,7 s.

---

# MEDIDO CONTRA SIGRID EL 2026-09-10 (solo lectura, `leer_sql`)

Lo que sigue **corrige** por medición lo que arriba era inferencia.

## El texto NO está en `dcf.tex`. Está en `con.tex`

| campo | documentos | con texto | % | bytes máx |
|---|---|---|---|---|
| `dcf.tex` | 165.658 | **474** | 0,3 % | 2.301 |
| `ctr.tex` | 18.936 | 738 | 3,9 % | 6.673 |
| **`con.tex`, facturas (`tip = 15`)** | 165.658 | **108.445** | **65,5 %** | 11.580 |
| `con.tex`, comparativos (`tip = 46`) | 20.190 | 5.707 | 28,3 % | 28.154 |
| `con.tex`, contratos (`tip = 44`) | 18.936 | 1.614 | 8,5 % | 1.731 |

La pestaña «Texto» se pinta desde el memo de la **superclase `con`**, no desde
el campo homónimo de la tabla del documento. La factura del correo de Juan
Romero (`con.cod = 'FR26/06051'`, `ide` 2776822, `tip` 15) tiene **797 bytes**
en `con.tex` y **NULL** en `dcf.tex`.

**Y `con.tex` está excluido hoy de la ingesta** con este comentario en
`config/tables_sigrid.yaml`: «texto libre largo, no lo usamos en seguimiento».
Esa frase es exactamente lo que la petición de Administración desmiente.

### El formato del contenido, verificado sobre la factura del correo

Comentarios concatenados en **orden descendente** (el más reciente primero),
separados por `\n --------------------------------- \n`, y cada uno cerrado
con `[dd/mm/aaaa hh:mm:ss Usuario: <login>]`. El cuerpo lleva saltos `\r\n`.
El último bloque puede traer una línea automática de la aplicación con
formato distinto (`fecha hora<TAB>Línea no procedente de Albarán: N`).

El formato es **regular y parseable**, pero es texto libre acumulado: nada
garantiza que un comentario respete la plantilla.

### Lo que cuesta traerlo

| alcance | bytes |
|---|---|
| `con.tex` entero (2.185.737 documentos, 120.649 con texto) | **33,7 MB** |
| solo facturas y contratos (`tip IN (15, 44)`, 184.594 docs) | **30,6 MB** |

Sobre 25 GB ocupados de un disco de 64 GB, es ruido. El coste real a vigilar
es el de la **ventana nocturna**, no el disco.

## `contex` es OTRA cosa, y conviene no confundirla

Existe `contex`: 15 columnas (`ide`, `conide`, `contexide`, `res`, `tex`, y
usuario/fecha/hora de alta, edición y borrado, más `leido`) y **2.855 filas**.
Es una tabla de notas estructuradas con autoría real por fila. **No es la
pestaña «Texto»**: si lo fuera, tendría cientos de miles de filas. Merece
mirarse aparte.

## Los vencimientos, medidos

| medida | valor |
|---|---|
| filas de `raw.pag` | **255.001** |
| documentos distintos con efectos (`conide`) | 197.477 |
| efectos con `fecrea = 0` | 158.503 |
| efectos con retención (`retide <> 0`) | 25.605 |
| facturas de compra | 165.658 |
| **facturas con al menos un efecto** | **165.636 (99,99 %)** |
| máximo de efectos en una factura | **16** |

**Trampa que hay que declarar**: `fecrea = 0` NO significa «vivo». Son 158.503
efectos, el 62 %, e incluyen vencimientos pasados sin puntear. La cartera viva
que midió F-037 son 10.607 pagos. Confundirlos da una cifra plausible y falsa.

**`pag` ya se ingiere entero**, así que los vencimientos **no cuestan ingesta
nueva**: solo build.

## Los catálogos que faltan, medidos

| catálogo | filas | para qué |
|---|---|---|
| `auxnap` (naturalezas de pago) | **3** | `pag.natide`, `dcf.cypnatide` |
| `auxban` (bancos y sucursales) | **1.666** | `pag.banban`/`bansuc` |
| `auxpag` (formas de pago) | 69 | ya ingerido, es la dimensión de F-073 |
| `auxefp` (medios de pago) | 10 | ya ingerido |

Las dos que faltan suman 1.669 filas: coste de ventana despreciable.
