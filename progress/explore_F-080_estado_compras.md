<!-- progress/explore_F-080_estado_compras.md -->
# Exploración F-080 · Qué publica hoy `compras`, y quién reclama la petición de Juan Romero

> Solo lectura sobre el repositorio, 2026-09-10. Complementa a
> `progress/explore_F-080_vencimientos_y_texto.md`, que mira el lado Sigrid.

## 1 · Lo que `compras` publica hoy

`etl_sigrid/infrastructure/postgres/sql/compras/` son cuatro ficheros.

* `00_setup.sql`: solo funciones (`fn_sigrid_date`, `fn_serie`,
  `fn_tipo_documento`).
* `01_documentos.sql`:
  * `compras.contratos` (22-44), 1 fila por contrato, desde `raw.ctr` +
    `raw.con`. Columnas: `contrato_id, codigo_contrato, serie, descripcion,
    fecha, obra_id, codigo_obra, proveedor_id, proveedor_nombre,
    proveedor_cif, comparativo_id`. **Ni forma de pago, ni estado, ni
    vencimiento, ni texto.**
  * `compras.facturas` (138-157), 1 fila por factura o abono, desde `raw.dcf`
    + `raw.con`. Columnas: `factura_id, codigo_factura, serie,
    tipo_documento, descripcion, fecha, proveedor_id, proveedor_nombre,
    proveedor_cif, referencia_proveedor`. **Nada de lo pedido.** Y `fecha`
    (146) es `con.fec`, el **alta** del documento, no `dcf.fecdoc`.
  * `contrato_lineas`, `albaranes`, `albaran_lineas`, `factura_lineas`:
    tampoco.
* `02_fact_linea.sql` y `03_views.sql`: agregados de importe; heredan las
  mismas carencias.

## 2 · Sus fichas del diccionario

`config/diccionario/compras.yaml`. La cabecera avisa de importes sin IVA,
abonos en negativo, que no filtra por `stg.obras` y de que **«NO SE REFRESCA
DE NOCHE»** (17-21), lo cual **contradice** el `refresco: nocturno` que
declaran las fichas de objeto del mismo fichero (50, 199, 266, 347, 410, 505,
551, 645, 759, 860, 961). Es una inconsistencia real del diccionario, no una
lectura.

Las fichas de `contratos` (185-256) y `facturas` (496-539) describen lo que
hay y **no mencionan** forma de pago, estado, vencimiento, banco ni texto.

## 3 · F-067: lo que promete de verdad

Los siete criterios de `acceptance` están en `harness/features.json`. Los dos
que importan aquí:

1. «`compras.contratos` publica el estado actual con su nombre (`conest`),
   forma de pago y retención; la penalización queda como pregunta a Compras».
5. «`compras.facturas` publica estado, fecha de cambio de estado y fecha de la
   propia factura, y se cruza con `raw.pag` para decir si está pagada y
   cuándo».

**CORRECCIÓN A LA SPEC DE F-073.** `design.md:23,25`, `requirements.md:93-95`
(R23) y `progress/current.md:26-28` afirman que el cableado de forma de pago y
estado **a `compras.contratos` y `compras.facturas`** es el criterio 1 de
F-067. Es impreciso: **el criterio 1 nombra solo `compras.contratos`**. El
estado de las facturas vive en el criterio 5, que **no menciona la forma de
pago**. Resultado: **ningún criterio de F-067 promete hoy la forma de pago de
la factura**, que es justo lo que pide Juan Romero. La narrativa de F-067 sí
dice que `dcf` recuperó `pagtex` y `pagfor` en F-066, pero eso es el dato
crudo, no el compromiso de publicarlo.

## 4 · Quién reclama la petición

| Feature | Estado | Prioridad | Solape |
|---|---|---|---|
| **F-037** tesorería | pending | 21 | Los vencimientos/efectos: publica `raw.pag` y `raw.cob` sin el filtro de retenciones, con `fecven`, `fecrea`, medio y estado. Alcance tesorería general, no compras |
| **F-067** compras por el MCP | pending | 16 | Estado y forma de pago de contratos, estado y fecha de facturas, cruce factura→pago. Con el hueco del §3 |
| **F-073** | spec_ready | 6 | **No es la feature**: `requirements.md:13-15` excluye explícitamente `compras.contratos` y `compras.facturas` |

**Ninguna feature fichada cubre la petición completa**, y **ninguna menciona
el texto libre de la pestaña «Texto»** para documentos de compra.

## 5 · Cómo se excluye hoy el texto largo

`config/tables_sigrid.yaml`, campo `exclude_columns` por tabla. El módulo
compras aplica **a bulto** la misma lista (223-239): `tex, med, des, obs, ima,
emptex, dirtex, eiotex, desesp, texcom, serdesdat, texobs, coestr`.

* `ctr`: excluye `tex` y `obs` (217-219). **La pestaña «Texto» del contrato no
  se ingiere en absoluto.**
* `dcf`: excluye `tex` y `obs` (411-424). Nota (435-439): `pagfor` y `pagtex`
  **dejaron de excluirse** el 2026-09-06 con F-066, y `pagtex` viene informado
  en 165.390 de 165.391 facturas. O sea: la factura ya trae condiciones de
  pago en `raw`, pero **sigue sin el texto libre**.
* `dca`: igual, y no cambió.

**El precedente de cómo se revierte ya existe y está hecho una vez**:
`prvcer.tex` estaba fuera solo porque la lista del módulo se aplica a bulto, y
F-074 lo sacó de la exclusión (`impl_F-074.md:78-80`,
`config/tables_sigrid.yaml:755-775`).

Mecanismo: `ingest_raw_step.py:230-256` pide el esquema real a Sigrid y filtra
por **nombre** de columna. **No hay límite de tamaño de texto** en la ingesta
ni en el cliente; el único límite del cliente es de **filas por petición**
(`sigrid_api_client.py:67-87`). El control de tamaño es manual: la lista de
exclusión más el `page_size` por tabla (ejemplo `obrparpre.planif`, línea 66,
con `page_size: 5000`).

## 6 · La ventana nocturna

Última medida: `caj-datamart-seg-dev-29816640`, 00:00 → 03:24 UTC del
2026-09-10, `Succeeded`, **3 h 25 min**, frente a las 4 h 52 de antes de
F-025. No hay presupuesto máximo declarado en ningún sitio.

`raw.pag` ya se ingiere entero hoy (254.856 filas), así que **los vencimientos
no cuestan ingesta nueva**, solo build.

## 7 · Hallazgo: el banco no está identificado con certeza

Ninguna ficha de `retenciones.movimientos` ni de F-037 tiene columna de banco.
El único rastro es `explore_F-006_dominio_completo.md:155` («Previsiones de
pago, remesas, bancos | ausente (`prp`, `mte`, `rpa`)»), del 2026-08-20 y **no
revalidado**. De esos tres, `prp` sí se revalidó en F-037 y tiene **0 filas**.
Hay que decírselo a Administración: el banco de la rejilla no tiene todavía
una tabla identificada y comprobada.
