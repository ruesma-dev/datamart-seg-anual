<!-- progress/impl_F-080.md -->
# F-080 · Informe de implementación

Vencimientos, forma de pago y texto de la factura de compra. Rigor `estandar`.
Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`.

## T0 · Precondición dura de F-073 (R20): CUMPLIDA

`etl_sigrid/infrastructure/postgres/sql/compras/04_formas_pago.sql` existe en el
árbol (2.400 bytes) y `build_compras_step.py:71-75` lo declara como sub-paso
`formas_pago` con `target_schema=compras` / `target_table=formas_pago`. No se
duplica la dimensión desde `raw.auxpag`. **T0 bis** (que la vista esté construida
en la base) es MANUAL del humano y NO bloquea: queda en `progress/current.md`.

### El portero estaba en rojo ANTES de empezar, y no por el código

`bash harness/init.sh` sobre HEAD `b6cfd6e` daba `[KO] PUERTA TAMAÑO`:
`requirements.md` 152 líneas (tope 150) y `design.md` 252 (tope 250). Con eso ni
se podía arrancar en verde ni cerrar T29. Se han **recompuesto líneas** (ancho de
dos párrafos y del blockquote de cabecera), y se ha comprobado palabra a palabra
contra HEAD~1 que el multiset de palabras de los dos ficheros es **idéntico**: no
se ha tocado ni un requisito, ni una decisión, ni una cifra. Commit `d0129a7`.

## T1 · Los nombres medidos, antes de una línea de SQL (solo lectura)

Medido el 2026-09-11 contra Sigrid con el **cliente del ETL**
(`SigridApiClient.leer_sql`, que rechaza cualquier sentencia que no sea de
lectura), no con el MCP —que no ve `raw` ni Sigrid—.

| tabla | lo que hacía falta saber | medido |
|---|---|---|
| `pag` (46 col.) | las columnas del efecto | `ide, conide, tot, fecven, fecrea, fecreaemi, efeide, natide, cueide, banide, banban, bansuc, bancue, ban, bantipide, retide, cenide, remide, padide, cla, pun` |
| `con` (19 col.) | identidad del efecto | `cod` varchar(24), `res` varchar(128), `est` int, **`fecbaj` int**, `tip` int, `serie` int, `tex` text |
| `conest` (17 col.) | la clave de unión | se une por **`tip` + `est`**; el nombre es `res` y **`cod` es el rótulo de 3 letras** de la pantalla (PDT, APR, EMI, CAR, REM, PAG, DEV, AGR, DIV, ANT) |
| `rpa` (30 col.) | la remesa | `fecrem` int, `imptot` float, `banide`, `banban`, `bansuc`, `ban`, `efeide`, `cla`, `tex`. **NO tiene `cod`** |
| `auxnap` (6 col.) | naturaleza | `ide, cod, res, pos, fecbaj, tiemod`. 3 filas: NOM/EMB/CUO |
| `auxban` (12 col.) | banco y sucursal | `ide, cod, res, pos, tipsuc, paiide, tiemod`. 1.690 filas |
| `cua` (16 col.) | cuenta contable | `ide, padide, niv, cla…`; **no tiene `cod` ni `res`** |
| `dcf` (145 col.) | los campos de pago | `pagide, pagfor, pagtex, efeide, cypnatide, cueide, banide, banban, bansuc, bandig, bancue, ban, bantipide, fecdoc, entref` |

**Dos hallazgos de T1 que cambian de dónde se lee el dato** (y que son la misma
trampa de DA-9 dos veces más):

1. **`rpa` ES un documento**: `tip = 27`, y las 3.919 remesas tienen fila en
   `raw.con`. El código `RP26/0254` y la descripción («REMESA CONFIRMING
   SABADELL») están en `con.cod` / `con.res`, no en `rpa`. `codigo_remesa` se
   lee del `raw.con` de la remesa.
2. **`cua` también**: las 34.158 cuentas tienen fila en `raw.con` con `tip = 17`,
   y el número de cuenta contable (`4100006400`) y su nombre están ahí. La
   cuenta y el banco del efecto se resuelven contra `raw.con`, no contra `cua`.

**Cómo se une el bloque bancario (lo que «no constaba»)**: `pag.banban` y
`pag.bansuc` apuntan los dos a **`auxban.ide`**, en dos joins distintos —no al
código—. Medido: 110.460 de 110.477 `banban` casan (99,98 %) y 93.273 de 93.273
`bansuc` (100 %). `auxban.tipsuc` separa las 442 entidades (0) de las 1.248
sucursales (1).

## T2 · Las cifras (2026-09-11, solo lectura)

| medida | valor |
|---|---|
| efectos cuyo `conide` es factura de compra (grano de `compras.vencimientos`) | **195.510** |
| facturas distintas con efectos | 165.737 |
| reparto de `con.est` contra `raw.conest` `tip = 25` | 10 Pagado 106.262 · 14 Agrupados 55.476 · 2 Aprobado 20.848 · 1 Pendiente 10.436 · 5 En cartera 2.319 · 3 Emitido 169 |
| efectos de factura en remesa (`remide <> 0`) | 40.090 |
| efectos de factura con retención (`retide <> 0`) | 23.180 |
| efectos de factura con `fecrea = 0` | 120.843 (61,8 %) |
| documentos `tip = 15` con `con.tex` | 108.527 de 165.759 (65,5 %), máx. 11.580 bytes, 30,3 MB |
| documentos `tip = 44` con `con.tex` | 1.614 de 18.965 (8,5 %), máx. 1.731 bytes, 0,35 MB |
| facturas que NO cuelgan de ningún contrato (R30) | **85.324 de 165.759 (51,5 %)** |
| series del código del efecto | `FR` 192.444 · `DI` 3.016 · `AG` 25 · `AB` 13 · `VA` 10 · `FC` 2 |

**`incremental_column` MEDIDO en `INFORMATION_SCHEMA`** (R3), no por analogía:
`auxnap.tiemod` float **sí**, `auxban.tiemod` float **sí**, y **`rpa` no tiene
`tiemod` ni ninguna columna de tipo fecha** (sus 30 columnas son numéricas o
texto; `fecrem` es un entero AAAAMMDD), así que va con `incremental_column: null`.
Es exactamente el error que F-074 cometió declarando tres `tiemod` inexistentes.

Recuentos de las tres altas: `auxnap` **3**, `auxban` **1.690**, `rpa` **3.919**.

## T3 · Medición A del coste de ventana (R4a), solo lectura

Tres ventanas de `con` repartidas por la tabla (`ide > 0`, `ide > 1.417.302`,
`ide > 2.434.604`), las mismas para las cuatro combinaciones. `con` tiene
**2.186.880 filas** y 19 columnas; «sin tex» son 18 (se excluye `ima`).

| variante | `page_size` | filas | segundos | MB de respuesta |
|---|---|---|---|---|
| sin `tex` | 10.000 | 30.000 | **1,78** | 3,98 |
| sin `tex` | 5.000 | 15.000 | 1,02 | 1,99 |
| con `tex` | 10.000 | 30.000 | **2,24** | 4,57 |
| con `tex` | 5.000 | 15.000 | 1,04 | 2,25 |

Página más pesada medida con `tex` a 10.000 filas: **1,71 MB**. Extrapolado a la
tabla entera: **2,2 → 2,7 min** de lectura HTTP y **290 → 333 MB**.

**Traer `tex` cuesta +26 % de tiempo de lectura y +15 % de bytes: medio minuto
sobre el total de `con`.** Y el temor de DA-4 —«una página de 10.000 documentos
habladores puede pesar cientos de MB»— **no se cumple**: la peor pesa 1,71 MB.
Por eso `page_size` de `con` se queda en el default global, sin bajarlo (R5 deja
esa decisión al humano con el dato delante, y aquí el dato dice que no hace falta).

## T4 · La anulación, VERIFICADA (no investigada) · R39, R40

**(a) `FR25/04222`, la factura de los ocho efectos del correo.** Los tres con
`con.fecbaj <> 0` son exactamente los tres que la captura pinta en rojo con aspa:

| `con.cod` | est | estado | `fecbaj` | importe |
|---|---|---|---|---|
| `FR25/04222_01` | 2 | Aprobado | **20250908** | 87.854,56 |
| `DIV25/0156` | 2 | Aprobado | **20251010** | 57.435,88 |
| `DIV25/0169` | 2 | Aprobado | **20251108** | 50.354,99 |
| `FR25/04222_02` | 1 | Pendiente | 0 | 4.623,93 |
| `DIV25/0155` · `DIV25/0168` · `DIV25/0184` · `DIV25/0185` | 10 | Pagado | 0 | 30.418,68 · 7.080,89 · 25.925,15 · 24.429,84 |

Suma de los **cinco vivos = 92.478,49**, y quitando la retención viva
(4.623,93) quedan **87.854,56**: los **dos números de la cabecera** de la
captura. Los anulados suman 195.645,43, que es el fantasma que aparecería sin
filtrar. El estado NO distingue: los tres anulados están «Aprobado».

**(b)** Efectos de baja: **89.228 de 255.148 (34,97 %)**; ciñéndose a los de
factura de compra, **76.215 de 195.510 (39,0 %)**. Coherente con los 89.095 /
255.074 del 2026-09-10 (el sistema sigue vivo).

**(c)** `pag.padide` informado en **0 de 255.148** → `efecto_origen_id` NO se
publica. `con.serie` informado en **0 de 255.148** → la serie sale de
`compras.fn_serie`. Y `con.tip <> 25` en **0 de 255.148**: todo efecto es un
documento de tipo 25, sin excepción.

Las tres comprobaciones salen. No hay nada que parar antes de T10.

## T7 y T8 · Medición B y el presupuesto de ventana · MANUAL (humano)

**T7 es una ESCRITURA y ningún agente la ejecuta.** Comando exacto, también en
`progress/current.md`:

```
python main.py ingest --table con --full
```

y después, la duración de la fila `ingest_raw.con` de `_meta.etl_runs` frente a
las noches anteriores (`python main.py timings --last 10`).

**T8, el contraste con las 4 h de referencia (R5, DA-5).** Con la medición B
pendiente, lo único que se puede contrastar hoy es lo que sale de la medición A:
traer `con.tex` añade **~0,5 min de lectura** (2,2 → 2,7 min) y 43 MB a una
ventana que hoy tarda **3 h 25 min**, o sea **~3 h 26 min frente a un
presupuesto de 4 h: unos 34 min de margen**. **No hay aviso que dar**, y por lo
tanto nada que bloquear. Si la medición B lo desmintiera, el aviso va por
escrito y **la feature sigue**: no es una puerta, no se marca `blocked` y el
`page_size` lo decide el humano con el dato delante.
