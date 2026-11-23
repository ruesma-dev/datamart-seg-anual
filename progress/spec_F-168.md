<!-- progress/spec_F-168.md -->
# F-168 · Mediciones del spec-author (2026-11-23, solo lectura)

Todo leído por `sigrid-api` (`POST /api/sql/read`, `WITH (NOLOCK)`, agregados en SQL, ninguna
respuesta `truncated`) y por Azure con `_bootstrap_done = True` y `filas_solo_lectura`. Scripts en el
scratchpad del spec-author, no versionados. **No se copia aquí ningún texto de documento**: el único
ejemplo es de una partida técnica (material).

## M1 · Columnas reales (INFORMATION_SCHEMA.COLUMNS de Sigrid)

La lista de `exclude_columns` es genérica y nombra columnas que no existen. Lo que SÍ hay:

| Tabla | Texto largo real (tipo `text`) | Lo que excluye el YAML y NO existe |
|---|---|---|
| `obrparpar` | `tex` (sin `des` ni `med`) | `des`, `med` |
| `obrparpre` | `tex`, `des`, `planif` (+ `med` image) | — |
| `dnc` / `dncpro` | `dnc.tex`; `dncpro.tex`, `com`, `medfijdis` | — |
| `com` / `comlin` / `comprv` | solo `com.tex`; **`comlin` y `comprv` no tienen ninguna** | casi toda la lista |
| `dco` / `dcopro` | cabecera `tex` + 12 de direcciones; línea `tex`, `desesp`, `texcom` | — |
| `ctr` / `ctrpro` | cabecera `tex`, `cntnot` y direcciones; línea `tex`, `desesp`, `texcom` | — |
| `dcp` / `dcppro` (pedidos, NO ingeridas) | cabecera `tex`; línea `tex`, `desesp`, `texcom` | — |
| `dca`/`dcapro`, `dcf`/`dcfpro` | cabecera `tex` y direcciones; línea `tex`, `desesp`, `texcom` (+`serdesdat` en `dcfpro`) | — |
| `obrctr` | `tex`, `texobs`, `texfinpro`, `texgarpro`, `texgaremp`, `texseg`, `coestr` | — |
| `cer`/`cerpro`, `dvf`/`dvfpro` | cabecera `tex`; línea `tex`, `desesp`, `texcom` | — |
| `dcfprodes`, `dcaprodes`, `ctrprodes` | ninguna | toda la lista |

Enlace a la partida: `paride` en `dncpro`, `dcopro`, `ctrpro`, `dcapro`, `dcfpro`, `dcppro`,
`cerpro` y `dvfpro`; `dncproide` (la línea de la planificación) en las cinco de compras; `comlin`
enlaza `dncproide` (necesidad) y `dcoproide` (oferta ganadora), y `dcopro.comlinide` la oferta.

## M2 · Cobertura, tamaño y formato (todas: **0 RTF**, texto plano)

| Columna | Filas | Con texto | % | MB | Máx. bytes | > 4 KB | > 32 KB | Lectura del agregado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `obrparpar.tex` (partida) | 401.017 | 242.438 | 60,5 | 165,6 | 24.804.068 | 966 | 7 | 2,9 s |
| `obrparpre.tex` | 14.287.657 | 0 | 0 | 0 | 0 | — | — | 6,5 s |
| `dncpro.tex` (planificación de compras) | 296.438 | 164.012 | 55,3 | 97,6 | 14.731 | 1.472 | 0 | 3,2 s |
| `dcopro.tex` (líneas de oferta) | 809.719 | 487.834 | 60,2 | 303,3 | 14.731 | 5.716 | 0 | 13,4 s |
| `ctrpro.tex` (líneas de contrato) | 249.860 | 132.927 | 53,2 | 67,5 | 14.827 | 787 | 0 | 3,8 s |
| `dcapro.tex` (líneas de albarán) | 1.185.832 | 305.869 | 25,8 | 158,5 | 14.827 | 1.863 | 0 | 10,5 s |
| `dcfpro.tex` (líneas de factura) | 1.117.044 | 229.090 | 20,5 | 108,7 | 14.827 | 1.156 | 0 | 9,1 s |
| `dcppro.tex` (líneas de pedido) | 656 | 605 | 92,2 | 0,16 | 2.813 | 0 | 0 | 0,1 s |
| **Suma de las seis del flujo** | | **1.562.170** | | **901,2** | | | | |

Fuera por medición (casi vacías o cabecera):

| Columna | Con texto / filas | MB |
|---|---|---:|
| `dnc.tex` | 3 / 280 | 0 |
| `dncpro.com` · `dncpro.medfijdis` | 463 / 296.438 · 0 | 0,04 · 0 |
| `com.tex` (comparativo) | 60 / 20.802 | 0 |
| `dco.tex` · `ctr.tex` · `dca.tex` · `dcf.tex` · `dcp.tex` | 580 · 738 · 607 · 479 · 0 | < 0,4 cada una |
| `desesp` y `texcom` de las líneas | 0 a 73 por tabla | ~0 |
| `obrctr.tex` (contrato de venta, cabecera) | 277 / 975 (máx. 682 B) | 0,04 |
| `obrctr.texobs/texfinpro/texgarpro/texgaremp/texseg` | 0 | 0 |
| `cer.tex` · `dvf.tex` (cabeceras de venta) | 4.446 / 6.326 · 8.135 / 15.752 | 0,5 · 0,85 |
| `cerpro.tex` · `dvfpro.tex` (líneas de venta) | 0 / 6.380 · 27 / 29.368 | 0 · 0,006 |
| `obrfas.tex` · `pro.tex` | 15 / 4.634 · 4 / 55.179 | 0 |

**El memo del documento vive en `con.tex`** (ya en `raw` desde F-080), no en la cabecera de su tabla:

| `con.tip` | Documentos | Con memo | MB | Máx. B | ¿Publicado hoy? |
|---|---:|---:|---:|---:|---|
| 46 comparativo | 20.802 | **5.902 (28 %)** | 2,56 | 28.154 | **No** (`documento_texto` es solo 15 y 44) |
| 12 oferta | 74.431 | 832 | 0,09 | 5.045 | No |
| 14 albarán | 318.237 | 656 | 0,08 | 966 | No |
| 15 factura · 44 contrato | 169.316 · 19.322 | 111.516 · 1.669 | 31,2 · 0,36 | 11.580 · 1.731 | Sí |

## M3 · ¿Copia o edición? (igualdad exacta del texto, ambos no vacíos)

| Línea ~ origen (enlace) | Iguales | Distintos | Solo la línea | Solo el origen | Lectura |
|---|---:|---:|---:|---:|---|
| planificación ~ partida (`paride`) | 90.073 | 58.645 | 15.292 | 84.768 | 61 % copia, 39 % editado |
| oferta ~ planificación (`dncproide`) | 460.824 | 15.410 | 11.200 | 4.202 | **97 % copia** |
| oferta ~ partida (`paride`) | 239.703 | 207.765 | 40.327 | 218.136 | 54 % |
| contrato ~ planificación (`dncproide`) | 80.611 | 27.577 | 9.632 | 3.878 | 75 % copia, 25 % editado |
| contrato ~ oferta (`linoriide`) | 20.856 | 5.763 | 202 | 1.737 | 78 % |
| albarán ~ contrato (`linoriide`) | 245.587 | 305 | 294 | 192 | **99,9 % copia** |
| factura ~ albarán (`linoriide`) | 215.333 | 896 | 7.776 | 1.794 | **99,6 % copia** |
| pedido ~ planificación (`dncproide`) | 598 | 5 | 0 | 0 | 99 % |

Lectura: el texto nace en la partida, se **edita** al planificar las compras (el 39 % de las líneas
de planificación con texto lo cambia: describe el elemento comprado, no la unidad de obra), se
**copia** a la oferta, se **retoca** en el contrato (25 %) y desde ahí se copia tal cual a albarán y
factura. Ojo: `linoriide` no dice a qué tabla apunta (lo dice `docoritip`); en «factura ~ contrato»
salen 204.962 cruces con solo 9.421 iguales, señal de que muchos `linoriide` de factura apuntan a un
albarán y casan por casualidad con un `ctrpro.ide`. Por eso el diseño compara solo por `paride` y
`dncproide`, que no son ambiguos.

## M4 · Deduplicación

| Tabla | Textos | Distintos (`CHECKSUM` + longitud) |
|---|---:|---:|
| `obrparpar` | 242.438 | 143.053 |
| `dncpro` | 164.012 | 74.111 |
| `dcopro` | 487.840 | 67.508 |
| `ctrpro` | 132.927 | 83.823 |
| `dcapro` | 305.869 | 57.854 |
| `dcfpro` | 229.090 | 59.263 |
| `dcppro` | 605 | 567 |
| **Las siete juntas** | **1.562.781** | **206.948 distintos, 152,5 MB** (de ellos 45,3 MB son los 7 de > 32 KB) |

Los 901 MB por línea son **~107 MB de texto distinto** sin la basura: un catálogo deduplicado
publica una octava parte.

## M5 · Coste de lectura por la pasarela

- 20.000 líneas de `dcopro` con `tex`: **1,6 s y 8,4 MB**; las mismas sin `tex`: 0,1 s.
  La página más pesada a 5.000 filas de línea es de ~74 MB en el peor caso teórico (5.000 × 14.827 B);
  la típica, ~3 MB. Nada se acerca a los 230 s.
- `obrparpar` tiene una fila de **24,8 MB** y siete de > 32 KB (45 MB): sin tope en origen viajan
  enteras cada noche. Detalle del tramo en M7.

## M6 · Azure hoy (lote `20261123T000043Z-3db566`)

- Base: **38 GB** (40.692.022.295 B) de 64. `descompuestos`: `lineas` 2.686 MB, `_des_texto` 1.970 MB.
- Nocturna: 00:00 → **05:06 UTC** (5 h 05 min); el 21 acabó a las 06:54. `ingest_raw` entero, 36,5 min.
- Ingesta de las seis tablas sin `tex`: `obrparpar` 34 s, `dncpro` 37 s, `dcopro` 110 s, `ctrpro` 51 s,
  `dcapro` 162 s, `dcfpro` 164 s: **558 s**. Ocupan en `raw` 114 + 131 + 385 + 119 + 558 + 538 MB = 1,85 GB.
- Estimación con `tex`: +901 MB por la pasarela. A ritmo de lectura (5,3 MB/s, M5) son +3 min; con el
  ratio medido en F-080 para `con.tex` (+15 % de bytes, +26 % de tiempo) son **+6 a 8 min**. En disco,
  `raw` +~1 GB (los textos de ~600 B no se comprimen: TOAST solo actúa a partir de ~2 KB por fila).
- `descompuestos.lineas`: 4.827.550 filas (ESTUDIO 11.783, MASTER_ESTUDIO 110.735, MASTER_PRE_ABC
  1.802.062, MASTER_PLANIF_JO 2.607.631, PLANIF_JO 295.339); 2.990.183 de 4.520.428 del master llevan
  `dncpro_id`. `stg.partidas`: 400.992 filas, 99 MB.

## M7 · Partidas por ámbito, tope y datos personales

**La partida tiene UN texto para todos sus ámbitos.** `obrparpre.tex` está vacío (M2) y
`obrparpar.parvenide` y `parideori` valen 0 en las 401.017 filas: coste, venta, fase 0 y master
comparten la misma partida (`obrparpre.paride`), así que su texto largo es `obrparpar.tex`, uno por
`partida_id`. Partidas con presupuesto en cada ámbito y cuántas tienen texto:

| Ámbito | Partidas | Con texto | % | Obras |
|---|---:|---:|---:|---:|
| 3 coste | 225.317 | 154.298 | 68 | 690 |
| 7 venta | 194.178 | 152.229 | 78 | 373 |
| 8 master coste | 168.926 | 129.443 | 77 | 245 |
| 11 master venta | 150.425 | 126.521 | 84 | 231 |
| resto (1, 2, 4, 5, 9, 10, 12-15) | 589.590 | 469.338 | 80 | — |

Por tipo: `tip` 1 (partida) 241.022 de 354.321 con texto; `tip` 0 (capítulo) 1.411 de 46.691; `tip`
99, 5 de 5. **525 de las 739 obras** tienen al menos una partida con texto. Ejemplo citado por el líder:
partida 419079 (04.02 «FORJ. RETICULAR 35+10» de la 0726), con la descripción técnica completa.

**Tope.** De `obrparpar.tex`: 69 textos > 8 KB y **solo 8 > 16 KB, de 4 obras, que suman 45,4 MB**
(recortarlos a 16.000 quita 45,2 MB, el 27 % del volumen de la tabla). El mayor texto de cualquier
línea del flujo es de 14.827 B: un tope de 16.000 caracteres no recorta ni una línea de documento.
Un vistazo a los grandes: binario pegado (`Äk¶8686868…` con bytes de control), no texto.

**Caracteres que rompen.** Ningún texto lleva NUL (`CHAR(0)`), que haría fallar el `COPY` de la tabla
entera; llevan caracteres de control 31 (`obrparpar`), 25 (`dncpro`), 58 (`dcopro`), 49 (`ctrpro`),
111 (`dcapro`) y 58 (`dcfpro`).

**Datos personales.** Dos pasadas. La laxa (cualquier `@`, cualquier secuencia que parezca teléfono,
«DNI»/«NIF», «contacto», «IBAN») da miles de coincidencias por tabla (p. ej. `dcopro`: 351, 11.997,
9.331, 13.726 y 611) y es ruido: casa con «en contacto con el terreno» o con medidas. La estricta:

| Tabla | Correo | Nueve cifras 6-9 aisladas o 3-2-2-2 | Ocho cifras + letra | IBAN |
|---|---:|---:|---:|---:|
| `obrparpar` | 14 | 203 | 2 | 0 |
| `dncpro` | 9 | 193 | 2 | 0 |
| `ctrpro` | 9 | 174 | 2 | 0 |

Clasificado a mano un vistazo de cada señal (sin copiar nada a este fichero): los correos son de
**empresa** (departamento de compras o de soporte de un fabricante; uno es `Mbps@720p`, ruido); de 12
«teléfonos» de partida, **10 son referencias de producto** (`Ref. 801390004`, `K929482507 de
Philips`, `SYSTIMAX / 760038240`) y 2 son el **contacto comercial de un proveedor** (nombre y
teléfono) escrito por quien hizo el presupuesto; los «DNI» son referencias de modelo. No hay IBAN.
Conclusión: lo personal que hay es **contacto profesional de proveedores en unas decenas de textos**;
la máscara de postventa (`[6-9][0-9]{8}` sin fronteras) destrozaría sobre todo referencias de
producto, que es justo lo que sirve para comparar precios. `obs`, direcciones y textos de cabecera
NO entran (siguen excluidos).

## M8 · El campo 9 del descompuesto (Azure, `TABLESAMPLE SYSTEM (3)` de `_des_texto`)

| Ámbito | Registros en la muestra | Con campo 9 | Bytes del campo 9 | Máx. B | Con enlace a `dncpro` | RTF |
|---|---:|---:|---:|---:|---:|---:|
| 3 (Estudios) | 3.437 | 660 (19 %) | 241.539 | 2.273 | 740 | 0 |
| 8 (master) | 134.969 | 71.666 (53 %) | 26.335.182 | 6.706 | 65.085 | 0 |

Extrapolado al 100 %: ~8 MB en el ámbito 3 y **~0,9 GB en el master**, porque cada versión copia el
texto entero; deduplicado será una fracción (las versiones repiten los mismos elementos). Ejemplo de
material: «HORM. HA-30/P/40/ IIa CENTRAL» → «M3. Hormigón para armar de resistencia HA-30/P/40/ IIa
Nmm2, con cemento CEM II/A-P 32,5 R arena de río y árido rodado tamaño máximo 40 mm., de central…».
Hoy `fn_trocear` NO lo extrae (posiciones 1-5, 7, 11, 14, 16, 17 y 36).

## M9 · ¿En los comparativos está? (la pregunta del humano)

**Sí, pero no en la tabla del comparativo.** `comlin` (sus líneas) y `comprv` (sus invitaciones) **no
tienen ninguna columna de texto**, y `com.tex` está en 60 de 20.802. El texto de cada línea del
comparativo vive en dos sitios a los que la línea apunta:

- su **línea de planificación** (`comlin.dncproide` → `dncpro.tex`): lo que se pide;
- cada **línea de oferta** (`dcopro.comlinide` → `dcopro.tex`): lo que oferta cada proveedor, copia
  de la planificación en el 97 % (M3) y retocada en el resto.

Y el comentario del comparativo entero (el memo de su pestaña «Texto») está en `con.tex`: 5.902 de
20.802 comparativos (28 %), ya en `raw` desde F-080 pero **sin publicar** (M2). Las tres cosas las
publica el diseño: `compras.linea_texto` (tipos NECESIDAD y OFERTA) y `compras.documento_texto`
ampliado a comparativos y ofertas (D7).

## M10 · Cuentas del diseño (estimadas; se miden en los pasos MANUAL)

| Concepto | Estimado |
|---|---|
| Bytes nuevos por la pasarela cada noche | 901 MB − 45 MB recortados ≈ **856 MB** |
| Tiempo de ingesta | **+6 a 8 min** sobre 558 s de las seis tablas (M6) |
| `raw` | +~0,9 GB |
| `stg.partida_texto` | ~242.000 filas, ~120 MB |
| `compras.textos` + `compras.linea_texto` | ≤ 207.000 textos (~80 MB) + ~1,32 M filas (~150 MB con su clave) |
| `descompuestos.textos` + `lineas.texto_id` (UUID) | ~50-150 MB + ~80 MB (4,83 M filas × 16 B) |
| Base | 38 GB → **~39,5 GB** de 64 |
| Construcción | +2 a 5 min cada noche; retroceso único de `descompuestos` ~15-20 min (MANUAL) |
| Nocturna | 5 h 05 → **~5 h 15-20** |

## Preguntas a Juan Romero (BORRADOR, no enviado)

1. Para comparar precios entre obras, ¿le basta el texto de la PARTIDA (el de la unidad de obra), o
   necesita también el de cada línea de oferta y de contrato (lo que de verdad se compró, que en un
   25 % de los contratos ya no es el texto planificado)?
2. Ocho partidas de cuatro obras tienen textos de más de 16.000 caracteres que son binario pegado.
   ¿Le vale que se publiquen cortados a 16.000 y marcados como recortados?
3. En unas decenas de textos hay el nombre y el teléfono del comercial de un proveedor. ¿Hay algún
   motivo de su lado para no verlos en el datamart?

## M11 · La expresión de recorte funciona en Sigrid

`CAST(REPLACE(SUBSTRING(CAST([tex] AS VARCHAR(MAX)), 1, 16000) COLLATE Latin1_General_BIN, CHAR(0),
'') AS VARCHAR(MAX)) AS [tex]` sobre las cinco primeras partidas de > 16 KB (223 KB a 3,5 MB): las
cinco salen a 16.000 caracteres (una a 15.998 por `LEN`, que no cuenta los espacios finales), en
0,6 s. Una página de 5.000 partidas con esa expresión, con el `WHERE [ide] > ?` del ingestor: 0,3 s.
