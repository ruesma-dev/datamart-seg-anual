<!-- specs/F-066-ingesta-raw-pendientes/mediciones.md -->
# F-066 · Mediciones

Todo lo de aquí está **medido**, no estimado. Lo que todavía no se ha podido
medir dice **PENDIENTE** y quién lo mide.

## 1 · Sigrid, el 2026-09-06 (solo lectura)

Vía `sigrid-api`, con `INFORMATION_SCHEMA.COLUMNS` y `COUNT(*)`. Es la fuente de
las cifras del `design.md` y de las constantes de `tests/test_f066_ingesta_raw.py`.

**Las 25 tablas nuevas: 5.328.841 filas.**

| Grupo | Tablas | Filas |
|---|---|---|
| Personal | `res` 2.610 · `emp` 1.352 · `hmo` 6.850 · `hmores` 328.760 | 339.572 |
| Contabilidad | `cua` 34.139 · `asi` 783.386 · `apu` 2.154.543 · `apa` 709.403 | 3.681.471 |
| Compras/proveedor | `dcopro` 787.641 · `dncpro` 286.432 · `dco` 72.151 · `confir` 69.993 · `dcarec` 40.930 · `dcfrec` 32.650 · `conact` 7.090 · `ctrrec` 6.342 · `prvcer` 2.741 · `dcorec` 748 · `auxpronat` 514 · `dnc` 275 · `conest` 193 · `auxpag` 69 · `deffir` 17 · `auxefp` 10 · `prvobrpag` 6 | 1.307.798 |

**Las 19 descartadas tienen 0 filas**, contadas una a una: `PFfir`,
`logfirdoc`, `auxfam`, `act`, `auxacttip`, `actent`, `actseg`, `comlinpar`,
`ctrrevpre`, `ctrproact`, `dcfproimp`, `verhis`, `auxtarprv`, `auxsec`,
`confam`, `entfam`, `prvres`, `prvcalsel`, `rqs`.

**Columnas de binario o texto ilimitado, tabla a tabla.** Es lo que decide
`exclude_columns`, y **corrige tres suposiciones de la spec**: `hmo`, `cua` y
`asi` no tienen ninguna, así que no excluyen nada. `emp` tiene exactamente las
11 de §3. Y hay cinco columnas ilimitadas **fuera** de la lista estándar que por
eso entran: `dncpro.com` (informada en 1.039 filas de 286.432, media 38 bytes),
`dncpro.medfijdis` (3.185 filas), `auxpag.formul` (69 filas), `auxefp.est` (10)
y `prvobrpag.texF` (6). Ninguna pesa.

**`dcf.pagtex`**, la columna que R8 recupera: informada en **165.390 de 165.391**
facturas, con **15,6 bytes de media**. Estaba excluida por tamaño.

## 2 · La ingesta desde el puesto (T9, 2026-09-06 12:02–12:21 UTC)

**Solo las tablas de menos de 100.000 filas**, por instrucción del humano: desde
el puesto las grandes tardan horas, la conexión se cae y gastan créditos del
servidor compartido. **17 tablas, 136.536 filas.**

| Tabla | Filas | Segundos del sub-paso |
|---|---|---|
| `auxefp` | 10 | 5,5 |
| `prvobrpag` | 6 | 1,1 |
| `deffir` | 17 | 1,2 |
| `auxpag` | 69 | 1,4 |
| `conest` | 193 | 1,3 |
| `dnc` | 275 | 1,2 |
| `auxpronat` | 514 | 1,3 |
| `dcorec` | 748 | 1,5 |
| `emp` | 1.352 | 2,1 |
| `res` | 2.610 | 2,0 |
| `prvcer` | 2.741 | 1,4 |
| `ctrrec` | 6.342 | 1,7 |
| `hmo` | 6.850 | 2,0 |
| `conact` | 7.090 | 1,9 |
| `dcfrec` | 32.650 | 3,8 |
| `cua` | 34.139 | 2,8 |
| `dcarec` | 40.930 | 4,9 |
| **Total** | **136.536** | **≈ 37 s de datos** |

**El dato que cambia la estimación de la nocturna.** Cada invocación duró
~70 s de reloj, pero **el paso de tabla no es quien los gasta**: entre 60 y 67 s
se los lleva `ingest_raw.firma_origen`, la firma de origen de F-025, que corre
**una vez por invocación**. En la nocturna eso se paga **una sola vez para las
56 tablas**, no 56 veces. Copiar 136.536 filas costó unos **37 segundos**.

Extrapolando por filas —y es una extrapolación, no una medición—, los
5,19 M de filas que faltan estarían en el orden de **10-15 minutos**, coherente
con el «+8 a +13 min» del diseño. La cifra buena es la de T13.

## 3 · La primera nocturna con las 56 tablas (T13, R19) — MEDIDA

`caj-datamart-seg-dev-p1gq8ks`, **2026-09-08, 11:16 → 14:19 UTC** (3 h 03),
`Succeeded`. Primera ejecución con la imagen **`r20260908-1248`**, que ya lleva
F-066 y F-068. SKU **`Standard_B2s`**, temporal desde el 2026-09-05. Los diez
pasos en verde y `check-declarados` **130/130**. `batch_id`
**`20260908T111652Z-570bb9`**.

`ingest_raw`: **11:16:52 → 11:57:47**, `SUCCESS`, **25.491.959 filas en
2.454,1 s**. Las 56 tablas contestaron: `_meta.etl_runs` guarda **57 tramos**
(las 56 más `ingest_raw.firma_origen`), ninguno `FAILED`.

### Filas y segundos por tabla: las 8 grandes y `dcf`

De `_meta.etl_runs`, tramos `ingest_raw.<tabla>` de ese `batch_id`:

| Tabla | Filas | Segundos |
|---|---|---|
| `apu` | 2.155.571 | 166,3 |
| `dcopro` | 788.415 | 141,3 |
| `asi` | 783.765 | 24,4 |
| `apa` | 709.701 | 38,2 |
| `hmores` | 329.086 | 34,3 |
| `dncpro` | 286.652 | 43,6 |
| `dco` | 72.241 | 19,8 |
| `confir` | 70.057 | 6,7 |
| **Subtotal, las 8 grandes** | **5.195.488** | **474,6** |
| `dcf` (recarga `--full` que crea `pagtex`/`pagfor`) | 165.503 | 54,6 |
| **Total de las 9** | **5.360.991** | **529,2** |

Las 8 grandes traen **3.183 filas más** que las 5.192.305 contadas en Sigrid el
06-sep (+0,061 % en dos días) y `dcf` **112 más** que las 165.391: es la deriva
del ERP vivo, la misma que motiva la tolerancia con dirección que se verifica en §6.

**Dónde se van los 2.454 s.** No en lo nuevo: `obrparpre` sola se lleva
**1.098,4 s** (44,8 % del paso) y las nueve de arriba **529,2 s** (21,6 %).
`firma_origen` cuesta **57,8 s** y se paga **una sola vez** para las 56 tablas,
como predijo §2.

### Total frente a la línea base

| | Base `20260905T173031Z-d06188` (05-sep) | Ésta (08-sep) | Δ |
|---|---|---|---|
| Filas de `ingest_raw` | 20.147.626 | 25.491.959 | **+5.344.333 (+26,5 %)** |
| Segundos | 1.832,4 | 2.454,1 | **+621,7 s (+33,9 %)** |
| Filas/s | 10.995 | 10.387 | −5,5 % |
| SKU | `Standard_B2s` | `Standard_B2s` | = |

**Corrección a la línea base que declara R19.** R19 escribe «20.148.546 filas,
1.832 s». Medido en `_meta.etl_runs`, esa ejecución tiene **20.147.626** en el
`rows_processed` del paso: las **920** de diferencia son el tramo
`ingest_raw.firma_origen`, que el paso padre **no** suma. Las dos lecturas son
válidas mientras no se mezclen; contando la firma en los dos lados, 20.148.546 →
**25.492.880**, y el salto es el mismo (+5.344.334). La tabla de arriba compara
`rows_processed` con `rows_processed`.

### Créditos de CPU

**Mínimo 552 de 576** (tope del `Standard_B2s`) durante toda la ejecución, que
acota el gasto en **≤ 24 créditos**. Frente a los 21 de la primera nocturna
acotada y los ~40 de la completa del 04-sep en B1ms. No se guardó la serie punto
a punto de esta ejecución: lo medido es el mínimo, y como cota basta —el 26 % de
filas de más no acerca la hucha al suelo ni de lejos—. Detalle de la comparación
entre nocturnas, en `specs/F-025-ventana-negocio-build/mediciones.md`
§«SEGUNDA NOCTURNA ACOTADA».

### Ya no es un caso aislado: la nocturna del 09-sep lo repite

`29815200`, del **2026-09-09 a las 00:00:17 UTC** (el cron nuevo), `ingest_raw`
`SUCCESS` con **25.497.946 filas en 2.921,1 s**. Las 56 tablas entran cada noche
en producción, no solo en la ejecución manual que las estrenó.

## 4 · La fila de F-065 (R20)

F-065 todavía no tiene carpeta en `specs/`, así que su fila vive aquí hasta que
la tenga.

| Fecha | Alcance | Créditos al empezar | Gastados | Duración | Estado | SKU |
|---|---|---|---|---|---|---|
| 2026-09-08 | completa, 56 tablas (`build_stg` acotado por F-025) | no medido punto a punto; **mínimo 552 de 576** en toda la ejecución | **≤ 24** (cota del mínimo) | **3 h 03** (11:16 → 14:19 UTC) | `Succeeded` | `Standard_B2s` |

## 5 · Lo que cazó el comando nuevo el mismo día que nació

`python main.py check-raw-recuentos`, contra Azure y con las 17 tablas ya
ingeridas, **imprimió 73 líneas para 56 tablas**: el generador del bloque de
compras se había ejecutado dos veces y el YAML tenía 17 entradas repetidas. La
nocturna las habría cargado dos veces cada noche, en silencio.

Ninguno de los 310 tests del fichero lo veía, y no por casualidad: todos leen la
ingesta a través de un `dict` indexado por `source_table`, que **colapsa los
duplicados**. Se corrigió el YAML y se añadieron dos comprobaciones que leen la
**lista** en vez del diccionario.

**Estado tras corregirlo** (`check-raw-recuentos`, 2026-09-06, código 1):

```
44 iguales · 4 distintas · 8 ausentes · 0 sin medir
```

- **8 ausentes**: las 8 grandes que esperan a la nocturna. Correcto.
- **4 distintas**: `con` (2.183.292 en Sigrid frente a 2.183.289 en `raw`), `com`
  (+1), `comlin` (+29) y `comprv` (+2). **No es un fallo de esta feature**: son
  tablas que ya se ingerían y Sigrid ha seguido creciendo desde la última
  nocturna. Es exactamente el desfase que el comando existe para hacer visible,
  y en T14 —tras una nocturna— tiene que salir 0.
- **0 sin medir**: las 56 consultas a Sigrid contestaron.

## 6 · T14 y R24 · las dos verificaciones MANUAL contra Azure — PENDIENTE (líder)

**Las mide el humano/líder**, no el implementer: R24 las declara `MANUAL` y los
dos comandos hacen 56 `COUNT(*)` contra Sigrid y contra el Postgres compartido,
así que no se lanzan con una nocturna corriendo. **La ventana buena es con la
nocturna `29815200` (00:00 UTC del 09-sep) ya terminada.**

Lo único medido hasta hoy contra Azure es del **08-sep a las 16:30 UTC** y con el
criterio **viejo** (igualdad exacta): **31 iguales · 25 distintas**, las 25 con
Sigrid por encima —4.883 filas sobre 25.287.500, 0,0193 %; peor tabla
`obrparpre` +3.969 (0,0286 %)— y salida con **código 1**. Ese es justo el
resultado que la tolerancia con dirección de T19-T24 convierte en verde sin
tapar nada. **Nadie lo ha reejecutado con el criterio nuevo**: eso es lo que
falta aquí.

### Hueco 1 · `check-raw-recuentos` con la tolerancia nueva

```bash
python main.py check-raw-recuentos
```

Criterio de cierre: **código de salida 0**, `ausentes` = 0 y `sin_medir` = 0, y
ninguna tabla con Sigrid **por debajo** de `raw` (esas son alarma sea cual sea la
magnitud). Pegar la salida entera aquí, tal cual, incluidos el umbral aplicado y
la peor desviación:

```
(pegar aquí la salida de check-raw-recuentos — fecha y hora UTC de la ejecución)
```

Código de salida: `(pegar)` · Ejecutado el `(fecha, hora UTC)` por `(quién)`.

### Hueco 2 · `check-diccionario`

```bash
python main.py check-diccionario
```

Criterio de cierre: **ningún objeto sin ficha** —las 56 tablas de `raw` con la
suya— y `objetos_pendientes.yaml` sin entradas nuevas. Pegar la salida:

```
(pegar aquí la salida de check-diccionario — fecha y hora UTC de la ejecución)
```

Código de salida: `(pegar)` · Ejecutado el `(fecha, hora UTC)` por `(quién)`.

**Cuando los dos huecos estén rellenos**, T14 pasa a `[x]` en `tasks.md` y R24
queda cumplido; hasta entonces C4 sigue abierto y la feature no puede pasar a
`done`.
