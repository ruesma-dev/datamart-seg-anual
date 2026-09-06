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

## 3 · PENDIENTE hasta la primera nocturna (T13, lo hace el humano)

Se dejan para la nocturna, con la imagen nueva, **8 tablas y 5.192.305 filas**:
`apu` (2.154.543), `dcopro` (787.641), `asi` (783.386), `apa` (709.403),
`hmores` (328.760), `dncpro` (286.432), `dco` (72.151) y `confir` (69.993).
También **`dcf`**: sus 165.391 filas ya están en `raw`, pero **sin `pagtex` ni
`pagfor`**, y solo una recarga con `--full` crea esas dos columnas.

Lo que hay que anotar aquí después de esa nocturna (R19):

| Qué | De dónde sale |
|---|---|
| Filas y segundos por tabla | `python main.py timings` |
| Total de `ingest_raw` frente a la línea base | línea base: **20.148.546 filas, 1.832 s en B2s el 2026-09-05** |
| Créditos antes y después | `cpu_credits_remaining` (`infra/README.md`) |
| SKU en el que se midió | hoy `Standard_B2s`, temporal desde el 2026-09-05 |

## 4 · La fila de F-065 (R20) — PENDIENTE

F-065 todavía no tiene carpeta en `specs/`, así que su fila vive aquí hasta que
la tenga. Se rellena tras la nocturna de T13.

| Fecha | Alcance | Créditos al empezar | Gastados | Duración | Estado | SKU |
|---|---|---|---|---|---|---|
| PENDIENTE (T13) | completa, 56 tablas | | | | | B2s |

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
