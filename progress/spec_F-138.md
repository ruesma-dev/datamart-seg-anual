# F-138 · Informe del spec-author: mediciones de las alarmas y la marca «liquidatoria»

Spec: `specs/F-138-facturas-liquidatorias/`. Todo medido el **2026-10-14** en SOLO LECTURA,
contra Sigrid por `sigrid-api` (`leer_sql`). Sin escrituras en Sigrid ni en
Postgres. Ni logins ni nombres en este informe: solo agregados. Los volcados
intermedios vivieron en el scratchpad de la sesión y no se versionan.

## 1. Las dos tablas de origen

- **`conala`** («Alarmas en conceptos»): **46.242 filas** (`ide` de 1 a 47.300),
  1,80 MB de texto en total (`tex` máx. 2.987 bytes, media 38). **No tiene
  `tiemod`**. Columnas: `ide`, `conide` (-> `con`), `alaide` (-> `auxala`),
  `alatip`, `alatab`, `pos`, `fec1`, `fec2`, `tex`, `rol`, `usu`, `tipabr`
  («ver al abrir»), `creusu`, `crefec`, `crehor`, `tiptex` («abrir ventana
  texto»). **0 huérfanas** contra `con` y contra `auxala`; 643 con `alaide = 0`
  (sin tipo).
- **`auxala`** («Alarmas (Clasificaciones)»): **4 filas** — 01 ALARMA FACT. POR
  INCIDENCIAS, 02 AVISO ABONOS, 03 INFORMATIVA, 04 (sin nombre). Tiene `tiemod`.

## 2. «Creada por: <login> -> 29/09/2026 7:38:06» está en `conala`, no en `dbo.log`

La alarma de la factura del correo (FR26/10035) es `alaide = 3` (03 INFORMATIVA),
texto «FACTURA LIQUIDATORIA», **`crefec = 20260929`, `crehor = 73806`** y
`creusu` = el login que enseña la captura. `crefec`/`crehor`/`creusu` están
informados en el **100 %** (desde 2008-12-04; `crehor` HHMMSS, 0 valores
imposibles). **`fec1` y `fec2` NO son fechas fiables**: a 0 en 45.741 de 46.242
filas, y en facturas y albaranes informadas en **1 de 23.833**. `usu` y `rol`,
vacías en el 100 %. `tipabr = 1` en 23.309 de 23.833; `tiptex = 1` en 137.

## 3. De qué documentos cuelgan (por `con.tip`)

| tip | documento | alarmas | con «LIQUIDA» |
|---|---|---|---|
| 15 | factura de compra (FR 18.584, FRGG 9; abonos 0) | 18.593 | 8.813 |
| 44 | contrato de compra | 15.562 | 32 |
| 14 | albarán AC 5.178 · proforma PROF 60 · nota NTC 2 | 5.240 | 4.667 (AC 4.612, PROF 55) |
| 11 | factura de VENTA (códigos `26/10/0016`, nombre de cliente) | 4.259 | 510 |
| 46 | comparativo | 725 | 23 |
| 43 | empleado (personal) | 497 | 8 |
| 54 | contrato de VENTA (`0704.CONT_PPAL.16`) | 388 | 190 |
| resto | 12, 5, 17, 25, 35, 42, 20, 4, 33, 40, 1 | ~1.000 | 8 |

De las ~14.250 alarmas «LIQUIDA», **13.480 son de facturas, albaranes y
proformas**; las ~770 restantes, de ventas (700), contratos (32), comparativos
(23) y otras. Las de contrato son sobre todo «CONTRATO INTERNO» y la forma de
pago escrita a mano.

**Coste de ingesta**: `conala` filtrada a `tip IN (14, 15)` son **23.833 filas,
643 KB**, leídas en **1,1 s** en una petición; `auxala`, 4 filas.

## 4. El texto: 697 variantes y una regla

Normalizado (mayúsculas, sin acentos, todo lo que no es letra o cifra a un
espacio), los tokens que empiezan por `LIQ`: LIQUIDATORIA 12.549, LIQUIDACION
926, LIQ 11, LIQUIDADA 8, LIQUIDATORIAS 5 y ~30 erratas (LIQUDATORIA,
LIQUIATORIA, LIQIDACION…). Cabeza: «LIQUIDATORIA» 4.947, «FACTURA
LIQUIDATORIA» 2.576, «UNICA Y LIQUIDATORIA» 1.519, «FACTURA UNICA Y
LIQUIDATORIA» 583, «ULTIMA Y LIQUIDATORIA» 556, «FRA LIQUIDATORIA» 296,
«LIQUIDACION» 226, «PROFORMA LIQUIDATORIA» 114, «ES LIQUIDACION» 89…

Casos que NO son una liquidatoria afirmada (medidos a mano sobre el volcado):

- **Negada**: «NO ES LIQUIDATORIA», «AUNQUE NO ES LIQUIDACION NO DIFIERO EL IVA,
  OBRA RECEPCIONADA…» (2011-2014), «FINALMENTE NO ES LIQUIDACION».
- **Dudosa**: «CARTA LIQUIDACION» 99, «TRABAJOS POSTERIORES A (LA) LIQUIDACION»
  ~20, «PREVISION (DE) LIQUIDACION» ~15, «TIENE QUE VENIR COMO LIQUIDACION» 4,
  «NO SE SI ES LIQUIDACION», «QUEDA PENDIENTE LIQUIDATORIA».
- **Remite a otro sitio**: «VER TEXTO» 1.836, «VER NOTA» 964, «MIRAR TEXTO» 210
  (y variantes con la forma de pago delante).

Regla candidata (la de la spec, R8-R12), aplicada a las 23.833 alarmas:

| | LIQUIDATORIA | DUDOSA | NEGADA | REMITE | sin mención |
|---|---|---|---|---|---|
| alarmas de factura | 8.663 | 122 | 45 | 3.185 | 6.578 |
| alarmas de albarán AC | 4.589 | 25 | 13 | 9 | 542 |
| alarmas de proforma | 55 | 0 | 0 | 0 | 5 |
| alarmas de nota | 0 | 0 | 0 | 0 | 2 |

Por DOCUMENTO (precedencia NEGADA > LIQUIDATORIA > DUDOSA > REMITE; 453
documentos tienen 2 alarmas y 8 tienen 3): **facturas 8.653 liquidatorias**,
122 dudosas, 45 negadas, 3.004 que solo remiten; **albaranes 4.586**, 25, 13,
9; **proformas 55**; notas 0.

## 5. El memo del documento (`con.tex`, ya en `raw` desde F-080)

2.051 documentos 14/15 mencionan «LIQUIDA» en el memo. Con la misma regla:
facturas con memo LIQUIDATORIA y **sin** alarma que lo diga: **458** (+46 que
solo tienen «VER TEXTO»); albaranes, **46**. De los 3.013 documentos que solo
remiten («VER TEXTO/NOTA»), **50** tienen la liquidación en el memo (47
afirmada). Ojo: `compras.documento_texto` solo publica facturas y contratos
(15, 44); el memo de los albaranes está en `raw.con.tex` pero no en `compras`.

## 6. Cobertura por año (documentos LIQUIDATORIA / documentos del año, por `con.fec`)

- Facturas: 2008 0/845 · 2009 44/4.164 · 2010-2017 entre 201 y 536 al año
  (4-9 %) · 2018 622/12.072 · 2019 610/13.787 · 2020 523/12.327 · 2021
  760/11.932 · 2022 490/10.698 · 2023 702/13.780 · 2024 774/15.599 · 2025
  756/15.317 · 2026 677/13.847 (≈ 5 % desde 2018).
- Albaranes: 2009 8 · 2010-2017 58-199 al año · 2018-2026 267-455 al año
  (≈ 1,5 %). Proformas: 2024 6/387 · 2025 16/1.256 · 2026 33/1.211.
- No hay alarmas creadas antes del 2008-12-04: un documento anterior sin marca
  no dice nada.

## 7. La cadena contrato -> albarán -> factura (la del `v_pbi_contrato_consumo`)

Factura -> contrato por `COALESCE(línea directa a contrato, albarán.ctride,
línea del albarán a contrato)`; albarán -> contrato por `ctride` o por su línea.

- Facturas liquidatorias con contrato: **6.052 de 8.653** (70 %); 59 cuelgan de
  más de un contrato. Albaranes y proformas liquidatorios con contrato: 3.485
  de 4.641 (PROF 47 de 55).
- **5.530 contratos** tienen al menos una factura liquidatoria (478 tienen más
  de una); 3.061 un albarán o proforma liquidatorio, 2.732 de ellos también la
  factura. En total **5.859 de los 19.127 contratos**.
- **En 5.200 de esos 5.530 la ÚLTIMA factura del contrato es la liquidatoria.**
  **719 contratos tienen 1.160 facturas con fecha de alta POSTERIOR a su primera
  factura liquidatoria**: es el control más claro que sale de aquí.
- Estado (`con.est`, tipo 44) de los 5.859: Firmado 3.940, Terminado 1.435,
  Recibido 175, Enviado 140, Comprobada 91, Pdt. envío 72, Rescindido 6. De los
  3.185 contratos Terminados, 1.435 (45 %) tienen liquidatoria.

## 8. Decisiones que necesita el humano

Ver `specs/F-138-facturas-liquidatorias/requirements.md`, D1-D8. La que bloquea el
cierre de la feature es **D1 (para qué)**: es el criterio 1 del `acceptance` y
solo lo puede contestar Elena Díaz. Pregunta propuesta para reenviarle (texto
completo en D1). Las demás tienen recomendación y no bloquean empezar.
