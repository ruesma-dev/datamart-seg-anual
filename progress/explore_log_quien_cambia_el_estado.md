<!-- progress/explore_log_quien_cambia_el_estado.md -->
# Las doce tablas de log, una por una: donde queda registrado quien aprueba una factura

Encargo del humano el 2026-09-16: «mira las tablas de log una por una». Venia de
una afirmacion suya que yo no habia sabido verificar: «con respecto a las
facturas, no tienen firmas pero si se cambia el estado y este estado debe saber
quien lo hizo, **eso es lo que usamos como "firma" en facturas**».

Yo habia mirado `confir` (3.454 filas de factura, **todas sin fecha**) y `concam`
(1,5 M de cambios auditados, **ni uno del campo `est`**) y me habia quedado sin
respuesta. **Tenia razon el humano y estaba en otro sitio.** Todo lo de abajo
esta medido contra Sigrid por `sigrid-api`, en **solo lectura**, el 2026-09-16.

## Las doce, una por una: once estan vacias

| tabla | filas |
|---|---|
| **`log`** | **8.472.098** |
| `logfav` | 0 |
| `logfirdoc` | 0 |
| `logmnt` | 0 |
| `logtmp` | 0 |
| `verifactulog` | 0 |
| `yetlog` | 0 |
| `atptfewslog` | 0 |
| `faceb2bwslog` | 0 |
| `facewslog` | 0 |
| `faeptwslog` | 0 |
| `geacamwslog` | 0 |

Y barri ademas **todo lo que suena a auditoria** por `INFORMATION_SCHEMA`
(`%log%`, `%aud%`, `%cam%`, `%hist%`, `%trace%`): 25 tablas. De las trece que no
estaban en la lista original, **once tambien estan vacias** (`enalog`, `goalog`,
`logtar`, `auxhcamco`, `auxtracam`, `congeacam`, `dCam`, `divcam`, `tracam`,
`tracampes`), `logweb` tiene **1 fila** y `e_histip` **900**. `concam` ya se
habia medido. **No hay ninguna otra candidata.**

## `dbo.log` es el libro de actas de Sigrid

Catorce columnas: `ide`, `emp`, `ori`, **`ope`** (que se hizo), **`fec`** y
**`hor`** (cuando), **`usu`** (quien), **`tab`** (sobre que tabla), **`tip`**
(tipo de documento), **`cod`** (codigo del documento), **`res`** (el literal de
la accion), `tex`, `est`, `err`.

Cubre **de 2008-11-22 a hoy**. De sus 8,47 M de filas, **5.175.371 son de `con`**
—la superclase de documentos, otra vez ella— y dentro de esas:

| tipo | que es | filas |
|---|---|---|
| **15** | **factura recibida** | **1.618.199** |
| 14 | | 1.051.076 |
| **25** | **efecto de pago** | 803.173 |
| **46** | **comparativo** | 183.621 |
| **42** | **obra** | 171.465 |
| **44** | **contrato** | 149.010 |

## La respuesta: la operacion 24 es la firma de la factura

De las 1,62 M de filas de factura, **300.438 son de `ope = 24`**, y su `res` dice
literalmente quien firma y en que rol:

| `res` | filas |
|---|---|
| ` : Aprobar factura : FIRMA DIGITAL` | 291.126 |
| ` : Aprobar factura : **ERROR al validar FIRMA DIGITAL**` | 4.493 |
| ` : Aprobar factura Gerencia Mascaró : FIRMA DIGITAL` | 1.353 |
| ` : Aprobar Factura Administración : FIRMA DIGITAL` | 1.039 |
| ` : Aprobar factura Jefe Grupo Aldara : FIRMA DIGITAL` | 896 |
| ` : Aprobar factura Jefe Grupo Inesco : FIRMA DIGITAL` | 873 |
| ` : Aprobar factura Jefe Grupo Ruesma : FIRMA DIGITAL` | 274 |
| ` : Aprobar factura maquinaria : FIRMA DIGITAL` | 194 |
| ` : Aprobar Factura Jefe Fabrica : FIRMA DIGITAL` | 40 |
| ` : Pasar directamente a DG : FIRMA DIGITAL` | 3 |

Mas sus variantes de error, 4.630 en total. **Los roles del circuito de
aprobacion de F-083 estan aqui con nombre y apellidos**, y encajan uno a uno con
los estados del tipo 15 (`APJO`, `APRJG`, `APRADM`, `APR`).

**Cobertura**: **152.627 facturas distintas** dejan rastro, sobre las 165.866 que
publica `compras.facturas` — el **92,0 %** — y las firman **183 usuarios
distintos**. Los diez primeros van de 31.348 a 5.331 aprobaciones.

Una muestra real, tal cual sale:

```
[8472075, 24, 20260916, 183434, 'mccalle', 'con', 15, 'FR26/07780',
 ' : Aprobar factura : FIRMA DIGITAL', 1]
```

Quien: `mccalle`. Cuando: 2026-09-16 18:34:34. Que: la factura `FR26/07780`.
Accion: aprobada con firma digital. **Eso es exactamente lo que el humano
llamaba «la firma» de las facturas**, y no estaba en `confir` ni en `concam`.

## Lo que queda por averiguar antes de modelar

1. **No hay catalogo de `ope`.** Busque tablas `%ope%` y `%acc%` y ninguna lo
   traduce. Las nueve operaciones que aparecen en facturas —5 (892.152), 24
   (300.438), 3 (238.695), 1 (160.152), 30 (25.011), 2, 8, 9, 6— hay que
   **inferirlas por su `res`**: la 1 parece el alta (su `res` trae proveedor y
   referencia), la 5 y la 3 llegan con `res` vacio.
2. **`log.est` NO es el estado del documento**: vale 1 (casi siempre), 2 y 0, y
   se comporta como el resultado de la propia operacion. **El estado de la
   factura sigue siendo `con.est`, el que publico F-083.**
3. **El rastro no dice a que estado se paso**, dice que accion se hizo. Para
   responder «quien la dejo en APRADM» hay que **casar la accion con el estado**,
   y eso es lo que hay que disenar.
4. **`dbo.log` NO se ingiere**: no esta entre las 68 tablas de
   `config/tables_sigrid.yaml`. Con 8,47 M de filas, **cargarla entera seria la
   tabla mas grande del `raw`**; el filtro natural es `tab = 'con'`, y aun mejor
   `tab = 'con' AND tip IN (15, 44, 46)`.
5. **Sirve para mas que las facturas**: con 149.010 filas de contrato y 183.621
   de comparativo, esta misma tabla alimenta lo que **F-084** y el circuito de
   firma no pueden responder por otra via.

## Donde vive esto ahora

Se ficho primero como **F-086**, y el 2026-09-16 el humano ordeno **fusionarla
con F-085**: «fusiona f85 y f86 en una sola». El motivo es bueno y esta escrito
en la ficha resultante: **`confir` y `dbo.log` son dos fuentes de la MISMA
pregunta**, y cada una cubre lo que la otra no —el comparativo lo responde
`confir` (66.096 firmas, 90,2 % fechadas), la factura solo `dbo.log` (300.438
aprobaciones frente a 3.454 firmas sin una sola fecha) y el contrato tambien
solo `dbo.log`, porque en `confir` no hay ninguna—. Separarlas obligaria a
saber a cual preguntar segun el tipo de documento.

**Todo lo medido aqui sigue vigente**; solo cambia el numero de la ficha que lo
recoge: **F-085**.
