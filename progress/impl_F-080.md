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
