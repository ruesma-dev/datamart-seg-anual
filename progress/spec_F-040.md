<!-- progress/spec_F-040.md -->
# F-040 · Mediciones del spec-author (solo lectura)

Spec-author, 2026-11-06, 08:52-10:40 UTC (fuera de la ventana 00:00-05:00). Todo en SOLO
LECTURA: Sigrid por `sigrid-api` (`SigridApiClient.leer_sql`), el datamart de Azure por
`PostgresClient.filas_solo_lectura` con `_bootstrap_done = True`. Los scripts viven fuera del
repositorio (scratchpad de la sesión) y se ejecutaron con el `.env` del checkout principal sin
tocar ningún fichero suyo. Ninguna lectura de `stg.plan_mensual`. Ninguna escritura.

## 1. Volumen (Sigrid, 2026-11-06)

| Tabla | Filas | Columnas | MB en Sigrid | `tiemod` | Lectura medida |
|---|---:|---:|---:|---|---|
| `dvf` (ya en `raw`, 9 columnas) | 15.732 | 151 | 40,8 | no | — |
| `dvfpro` | 29.273 | 90 | 27,6 | no | 10.000 filas / 17 col. en 0,8 s |
| `dvfrec` | 6.145 | 21 | 2,7 | no | — |
| `cer` | 6.308 | 135 | 16,1 | no | entera / 33 col. en 1,3 s |
| `cerpro` | 6.362 | 86 | 6,2 | no | entera / 22 col. en 0,8 s |
| `cerrec` | 7.396 | 21 | 2,0 | no | — |
| `cerprodes` | 4.349 | — | — | no | — |
| `cli` | 1.209 | 173 | 2,3 | no | — |
| `obrcer` | **0** | 32 | 0 | no | VACÍA |
| `cerpropar`, `dvfpropar` | **0** | — | 0 | — | VACÍAS |
| `cob` (ya en `raw`) | 22.025 | — | — | sí | — |

`con.tip`: `cer` = **54**, `dvf` = 11, `cli` = 4. Catálogo de estados ya en `raw.conest`:
54 → 1 Pendiente de emisión, 2 Aprobada por gerencia, 3 Emitida, 4 Aprobada por propiedad;
11 → 1 Pendiente de emisión, 2 Emitida, 4 Comprobada, 10 Contabilizada.

**Ventana nocturna.** Las 8 nocturnas del 30-10 al 06-11: `ingest_raw` 38-48 min, noche entera
282-296 min (00:00 → 04:56; la del 01-11, 365 min). Base de datos: 37 GB. Lo nuevo son
~60.000 filas y ~60 MB en origen con todas las columnas (bastante menos con listas blancas):
**+10 a 20 s de lectura** a la velocidad medida (6.000-10.000 filas/s por la pasarela) y un build
de tablas de miles de filas (< 30 s estimados, como `build_postventa`, 92 s de media con más
SQL). **Impacto < 1 % de la ventana.** El margen sobre las 05:00 sigue siendo el de siempre
(4 min); F-040 no lo empeora de forma apreciable, pero no lo crea.

## 2. Certificación: qué hay y qué NO hay

- **`obrcer` está VACÍA** (0 filas): `prorea`, `cerobr`, `cerrev` y `ceraac` no existen en la
  práctica. La certificación vive en **`cer`** (documento) + **`cerpro`** (sus líneas).
- `cer`: obra (`obride`) y centro (`cenide`) en el 100 %; contrato de venta (`ctride`) en
  6.277 (99,5 %), y su cliente coincide con el del contrato en 6.134; número (`fas`) en
  6.304; fechas de 2009 a 2026-10-31 (fin de mes). 310 centros, 732 contratos.
- Código: `<obra>.<contrato>.<nn>` (`0696.CONT_PPAL P 04.25`, `0707.ORD_CAMB.15`).
- **`cer.idefac` y `cer.feccob` están a 0 en las 6.308**: el campo «fecha de cobro» que el
  backlog proponía como enlace NO sirve. `cer.estfac` = 1 en 4.065.
- Estados: Emitida 2.841 (516,3 M€ base), Aprobada por propiedad 1.324 (249,3 M€), Pendiente
  de emisión 2.139 (3,6 M€: borradores), Aprobada por gerencia 4. Ninguna con `fecbaj`.
- `cer.docoriide` → la certificación ANTERIOR del mismo contrato (4.205 de 4.222).
- **A cuenta / a origen.** `cerpro.tot` es lo certificado en el periodo SIN recargos;
  `cerpro.imporiori`, el **a origen** (informado en 5.993 líneas); `imporiant`, el anterior (660).
  Ejemplo 0486 CONT_PPAL: a cuenta 39.426,40 → 47.924,21 → …; a origen 39.426,40 → 87.350,61 →
  199.733,00. La cabecera `cer.totbas` = líneas + recargos de clase 0 en 5.375 de 6.308 (85 %).
  `cer.totproori`/`totprcori` solo en 138: no sirven.
- 6.265 certificaciones tienen UNA línea; 43 tienen 2-10 (ajustes de decimales, liquidaciones).
- **`cerpro.paride` está en 5 de 6.362 líneas** y `proide` en 0: la certificación NO baja a
  partida ni a producto. El contraste con la producción solo puede ser por OBRA (o contrato).

## 3. Enlace certificación → factura → cobro

- **Certificación → factura: por `cerprodes`** (destinos de las líneas, `docdestip` = 11 =
  factura de venta), 4.349 filas, el 100 % con destino en `dvf` y línea en `dvfpro`. Cubre
  **4.106 certificaciones** y **3.753 facturas** (758,3 M€ de base, 307 centros).
  En sentido inverso, `dvfpro.linoriide` → `cerpro` en 4.452 líneas.
  - Por estado: Emitida 2.792 de 2.841 (98,3 %); Aprobada por propiedad 1.305 de 1.324
    (98,6 %); Pendiente 8 de 2.139. De las 68 emitidas/aprobadas sin factura, 26 tienen base 0.
  - Cardinalidad: 3.407 facturas de UNA certificación, 268 de dos, 79 de 3 a 27; 3.984
    certificaciones con UNA factura, 71 con dos, 51 con 3 a 5. Es N:M: no se reparte importe.
  - En 2.685 de las 3.407 facturas 1:1 la base de la factura iguala la de la certificación.
  - `dvf.ceride` (→ `obrcer`) a 0 en todas; `dvf.docoriide` solo en 27.
- **Factura → cobro: `cob.conide`**. 20.528 de 22.025 efectos (93,2 %, 1.200,3 M€) apuntan a
  una `dvf`; 15.709 de 15.732 facturas tienen efecto (12.254 uno, 3.455 varios, hasta 77).
  Los 1.496 sin documento son agrupados `AGR` (1.186, 162,9 M€), divisiones `DIV` (236) y
  sueltos. **En `cob` no hay estado 14 (Agrupado)**: el original de un agrupado sigue en est 1
  con `fecbaj` (es el problema que estudia F-104). Consecuencia: lo cobrado vía `AGR` no se
  atribuye a la factura; se declara.
- **Contraste producido / certificado / facturado** (22 obras de `tesoreria.devengo_corte_obra`,
  VENTA): venta real a origen con coeficientes 121,75 M€; certificado emitido o aprobado
  109,54 M€; facturado 109,54 M€. En 19 de 22 obras certificado = facturado al céntimo; la
  0678, 0686 y 0713 difieren por certificaciones pendientes o sin factura. El hueco
  producido − certificado va de −0,46 M€ (0720, certificado por delante) a +3,13 M€ (0696).
- **Conceptos fuera de coeficiente: NO hay campo estructural.** `obrcer.cerrev` vacío; los
  recargos `COEF_RECGG`/`COEF_RECBI`/`COEF_DESADJ` (clase 0) solo están en 1.286 de 6.308
  certificaciones (la mayoría de los CONTRATO PRINCIPAL los llevan dentro del precio); solo 36
  líneas dicen «revisión»/«contradictorio» (1,88 M€). Los contratos sí lo insinúan por nombre:
  «ORDENES DE CAMBIO» (12+7), «PARTIDAS SIN COEFICIENTES» (3), «MEDICIONES NO ACREDITADAS» (2),
  «CONTRATO SIN PEM». Hace falta el criterio de Control de Costes (D1).

## 4. Recargos (retenciones y coeficientes)

| Clase | Venta (`dvfrec`) | Certificación (`cerrec`) |
|---|---|---|
| 0 coeficientes | `COEF_RECGG` 880, `COEF_RECBI` 898, `COEF_DESADJ` 78 | 1.220 / 1.278 / 125 |
| 1 `RETESP` «Retención 5% garantía (sin iva)» | 1.030 · 16,78 M€ | 1.249 · 13,34 M€ |
| 3 retenciones de alquiler (`180A`, `ret02`) | 225 · 0,05 M€ | — |
| 4 `RET5T` | 68 · 1,29 M€ | 101 · 1,31 M€ |
| 5 `RET5`, `RET10` | 2.801 · 24,36 M€ | 3.336 · 21,93 M€ |

Ojo: en compras el `RETESP` NO es garantía (D2-B de F-128); en venta Sigrid lo llama
«garantía». Lo decide D4 (y, para la cifra de retención de cliente, F-104).

## 5. Clientes (`cli`) y calidad del CIF

- 1.209 clientes; 1.065 se usan en facturas u obras. `dvf.entide`, `obr.entide` y `cob.entide`
  apuntan SIEMPRE a un `cli` (0 huérfanos). 1.060 clientes en facturas, 194 en obras, 179 en
  contratos, 164 en certificaciones. El CIF de cabecera de la factura (`dvf.entcif`) coincide con
  el del cliente en 15.701 de 15.730.
- CIF: 31 vacíos (ninguno en un cliente con uso); 533 con forma de CIF de sociedad; **547 con
  forma de DNI (letra de control correcta en los 547) y 23-24 de NIE**: 571 con NIF de persona,
  de los que solo **26 tienen `perfis` = 1**. 3 con separadores; 10 de país extranjero; **50
  CIF repetidos en 111 fichas**.
- Las personas: 537 clientes con 3.631 facturas (16,5 M€, 49 centros): arrendamientos de plazas
  de garaje, compraventa de viviendas, rentas. Solo 3 tienen obra o certificación. **Son datos
  personales**: D2.
- Columnas sensibles en `cli`: dirección (1.161), correo (96), teléfono (73), cuenta bancaria
  (33). `taride` (clasificación) solo en 2 («Promotor»), `secide` (sector) en 0: **no hay
  clasificación de cliente en Sigrid**; la pregunta «diez mayores clientes» se responde por
  importe facturado, no por tipo.

## 6. Lo que publica hoy el datamart (Azure)

- `raw.dvf`: 15.732 filas, 11 columnas (9 + 2 de control). `raw` tiene 93 tablas.
- `tesoreria.efectos` COBRO: 22.025 efectos, 1.385,87 M€; 20.529 con documento; estados
  Cobrado 12.394, Pendiente 9.505, Cartera 120, Descontado 6. `tercero_cif` NULL.
- `retenciones.movimientos` CLIENTE: 2.212 VIVA (22,41 M€) + 42 LIQUIDADA; `entidad_cif` NULL en
  todas; `retenciones.v_src_lineas_venta` = 0 filas.
- **Efecto de traer `dvfpro` sobre las retenciones**: los efectos de retención de cliente SIN
  centro de coste son **0**, así que activar el respaldo por líneas NO cambia ninguna cifra de
  `retenciones.movimientos`. La vista deja de estar vacía (29.273 filas).

## 7. Conclusión para la spec

Fase 1 (esta spec) es barata en ventana y con dato limpio: ingesta de 7 tablas + `dvf` ampliada,
esquema `ventas` con clientes, facturas, certificaciones, enlace y seguimiento hasta el cobro, y
un contraste por obra limitado a las obras de la receta. El contraste completo y los conceptos
fuera de coeficiente necesitan un criterio que hoy no está en Sigrid: fase 2 (D1).
