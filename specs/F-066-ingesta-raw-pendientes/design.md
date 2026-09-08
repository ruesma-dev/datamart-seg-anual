<!-- specs/F-066-ingesta-raw-pendientes/design.md -->
# F-066 · Ingerir de Sigrid los raw que faltan — Diseño

## 1 · Lo medido el 2026-09-06 (solo lectura: `leer_sql`, `INFORMATION_SCHEMA`, `COUNT(*)`)

Mapa de `con.tip` verificado por recuento: 5 proveedor (`prv`), 12 oferta de
compra (`dco`), 14 albarán (`dca`), 15 factura (`dcf`), 16 cuenta del plan,
20 asiento (`asi`), 33 recurso (`res`), 42 obra, 43 empleado (`emp`), 44
contrato (`ctr`), 46 comparativo (`com`).

**Las 25 tablas que entran** (filas · columnas · notas). La cifra de
`dncpro` decía **286.428** por un error de transcripción y estaba en
contradicción con `mediciones.md` §1; **remedida contra Sigrid el 2026-09-06**
(`SELECT COUNT(*) FROM [dbo].[dncpro]` por `sigrid-api`, solo lectura): son
**286.432**, que es lo que ya decían `mediciones.md`, `tables_sigrid.yaml` y
la ficha de `raw.dncpro`. Corregida aquí y en R9:

| Grupo | Tabla | Filas | Cols | Nota |
|---|---|---|---|---|
| A personal | `res` | 2.610 | 55 | `tip = 33`; 1.723 de baja; `cif` informado en 626 |
| A | `emp` | 1.352 | 161 | `tip = 43`; DNI en 1.341, SS en 1.171, CCC en 985 |
| A | `hmo` | 6.850 | 16 | cabecera del parte; `reside` solo en 6 |
| A | **`hmores`** | 328.760 | 56 | **las horas**: `reside` 99,9 %, `obride` 99,6 % (536 obras), `fec`, `can`, `tot` |
| B contabilidad | `cua` | 34.139 | 16 | propiedades de `con` |
| B | `asi` | 783.386 | 7 | `tip = 20`, 0 huérfanos |
| B | `apu` | 2.154.543 | 36 | **sin `tiemod`**; `fec` informada al 100 %; `cenide` 54 %; `obr` 142 |
| B | `apa` | 709.403 | 20 | desglose analítico: `cenide` 99,98 %, `apuide` 88 %, `obride` 0 |
| C proveedor | `conact` | 7.090 | 11 | **actividades del proveedor**: 4.773 proveedores × 409 naturalezas; `homolo` = 0 en todas |
| C | `auxpronat` | 514 | 23 | catálogo al que apunta `conact.actide` (409 de 409 casan); tiene `tiemod` |
| C | `prvcer` | 2.741 | 8 | certificados del proveedor: `fec`, `feccad`, `cadval`, `cod` |
| C | `prvobrpag` | 6 | — | formas de pago del proveedor por obra |
| C firmas | `confir` | 69.993 | 28 | circuito real de firma: 65.761 de comparativos (`COMVAL`/`COAVAL`, roles `DCOM`/`JG`/`JEFO`…, `fec` informada en el 90 %), 3.436 de facturas **sin fecha**, 796 de obras |
| C | `deffir` | 17 | 19 | definición de los procesos de firma (`cod`, `roles`, `contip`, `estini`, `estfin`) |
| C ofertas | `dco` | 72.151 | 145 | ofertas de proveedor: `comide` en 70.583, `obride` 72.123, `fecdoc`, totales, `pagide` |
| C | `dcopro` | 787.641 | 71 | líneas de oferta (`comlin.dcoproide` apunta aquí) |
| C | `dcorec` | 748 | 21 | recargos de la oferta |
| C | `dnc` | 275 | 15 | necesidades de compra (`com.dncide`) |
| C | `dncpro` | 286.432 | 73 | líneas de necesidad (`comlin.dncproide`) |
| C condiciones | `ctrrec` | 6.342 | 21 | **retención del contrato**: `recide` 558368 en 6.125, `valpor`, `bas`, `cuo` |
| C | `dcfrec` | 32.650 | 21 | recargos/retención en factura |
| C | `dcarec` | 40.930 | 21 | recargos en albarán |
| C | `auxpag` | 69 | 13 | formas de pago (`ctr.pagide`, `dcf.pagide`, `dco.pagide`) |
| C | `auxefp` | 10 | 13 | medios de pago (`auxpag.efeide`) |
| C estados | `conest` | 193 | 17 | catálogo de estados **por `tip`** (29 tipos; 69 filas de compras): `tip`, `est`, `cod`, `res`, `pos`. Para `tip = 44`: 1 PFP, 3 EPF enviado, 5 RFP recibido, 6 COMD, 7 FIR firmado, 8 TER, 9 RES |

**Lo que NO está en Sigrid, medido** (esto es lo que la ficha de F-067 tiene
que saber): `ctr` no tiene fecha de envío, recepción ni firma —solo `fecdoc`,
`fecvig1/2` (5 informadas), `fecent`, `feclim`, `fecfac`, `tipgar`, `impavr`—
y su estado es **`con.est`, valor actual** (1/3/5/6/7/8/9; 13.418 en 7).
`concam` (1.539.071 cambios) audita **solo facturas y efectos** desde 2017 y
**nunca el campo `est`** (audita `efeide`, `pagfor`, `pagtex`, `pagide`,
`fecdoc`, `cenide`, `obride`…). `PFID` vacío en `ctr`, `dcf` y `dco`; `PFfir`
y `logfirdoc` a cero. **Penalización** no existe como campo de `ctr` (146
columnas); solo podría vivir en `ctr.tex` (738 informados, media 13 bytes).
`dcf.fecrec` y `dcf.fecpag` valen 0 siempre; la fecha de la factura es
`dcf.fecdoc` (165.311 de 165.391), ya en `raw`. Factura↔pago:
`pag.conide → dcf.ide` con `fecven`, `fecrea`, `retide`, ya en `raw`.

**Base y estimación.** `ingest_raw` el 2026-09-05 en B2s: 20.148.546 filas,
1.832 s (`con` 2,18 M/118 s; `dcapro` 1,15 M/209 s). Nuevo: **+5.328.841
filas (+26 %)**, ~+8 a +13 min, ~+0,9 GB en `raw`. `raw.con` ya tiene el
plan: 44.778 filas `tip = 16`, 38 empresas. En `raw.con`, 388 recursos llevan
un `cod` con forma de DNI: ya está en la base, esta feature no lo toca.

## 2 · Ficheros

**Crear**: `etl_sigrid/domain/recuentos.py`; `tests/test_f066_ingesta_raw.py`
(R1-R9, R11, R13, R14: leen YAML, sin red); `tests/test_f066_recuentos.py`
(R15-R18, dobles de los dos clientes);
`specs/F-066-ingesta-raw-pendientes/mediciones.md`.

**Modificar**: `config/tables_sigrid.yaml` (tres bloques nuevos al final —
PERSONAL, CONTABILIDAD, COMPRAS/PROVEEDOR— y en `dcf` quitar `pagtex`,
`pagfor` de `exclude_columns`; comentario con las 19 descartadas por vacías);
`config/diccionario/raw.yaml` (25 fichas + `dcf`; cabecera «Son 56 tablas»);
`config/diccionario/00_global.yaml` (`version` +1; «las 31 tablas» → 56);
`config/objetos_pendientes.yaml` (comentario); `main.py`
(`check-raw-recuentos`); `docs/ARCHITECTURE.md` (párrafo en «Acceso a
datos»: grupos nuevos, `apu` sin `tiemod`, `hmores`, mapa de `tip`, política
de datos personales, qué no guarda Sigrid); `azure-apps/datamart_seg_anual.md`
(repositorio aparte, commit propio); `harness/features.json` (solo el líder).

**No se tocan**: `ingest_raw_step.py`, `sigrid_api_client.py`,
`postgres_client.py` (`count_rows` y `table_exists` ya existen), ningún SQL de
`stg/`, `mart/`, `ddl/` (las tablas de `raw` las crea `ensure_raw_table`),
`infra/sql/02_roles.sql` y `apply_grants_step.py` (DA-5),
`business_rules.yaml` y `domain/ventana.py` (la firma de origen solo agrega
tablas de obra).

## 3 · `emp` y `res`: solo exclusiones técnicas (R5, R6, R7)

Decisión del humano (2026-09-06, 12:05 UTC): **no se excluye ninguna columna
por ser dato personal**. La regla es la misma que en el resto del YAML:
fuera lo binario y el texto ilimitado, dentro todo lo demás.

- `emp` (161 columnas) excluye **11**: `ima` (Binario ilimitado, la foto) y
  las diez de Texto ilimitado `dir`, `dirtex`, `web`, `tex`, `eleloc`,
  `disobs`, `podtex`, `traele`, `tracta`, `obsnom`. Entran `dni`, `dnipai`,
  `tarseg`, `fecnac`, `banban`..`ban`, `dir1`, `dir2`, `tel*`, `ele`,
  `clamai`, `esigpas`, `g3wpas`, etc.
- `res` (55 columnas) excluye **0**: no tiene binarios ni texto ilimitado;
  `cif`, `logacc`, `ideacc`, `ipacc`, `recema` entran.

La ficha de cada una **declara** qué datos personales contiene (R11); el
test de R5 comprueba que ninguna columna personal está excluida.

## 4 · Clases y funciones

Dominio, `etl_sigrid/domain/recuentos.py` (sin imports de infraestructura):

```python
@dataclass(frozen=True, slots=True)
class InformeRecuentos:
    iguales: tuple[str, ...]
    distintas: tuple[tuple[str, int, int], ...]   # (tabla, sigrid, raw)
    ausentes: tuple[str, ...]                     # sin tabla en raw
    sin_medir: tuple[str, ...]                    # Sigrid no respondió
    @property
    def ok(self) -> bool: ...                     # todo en `iguales`

def comparar_recuentos(declaradas: Sequence[str],
                       sigrid: Mapping[str, int | None],
                       raw: Mapping[str, int | None]) -> InformeRecuentos: ...
```

CLI, `main.py` → `check-raw-recuentos`, junto a `check-coherencia`: lee
`settings.tables_sigrid`; por tabla manda por `leer_sql`
`SELECT COUNT(*) AS n FROM [dbo].[<source_table>]` (+ `WHERE <where>`),
`SigridApiError` → `None`; en Postgres `count_rows("raw", target)` si
`table_exists`, si no `None`; imprime una línea por tabla y `sys.exit(1)` si
`not informe.ok`. Sin `record_run_start` (R18). Fichas de `raw`: patrón `rec`
con `motivo_no_consumo` que remita a la feature de mart que lo publicará.

## 5 · SQL

Ninguno. `ensure_raw_table` crea cada tabla en la primera ingesta
(`CREATE TABLE IF NOT EXISTS`, PK `ide`, `_ingested_at`, `_source_tiemod`).
El `SELECT` del MCP lo cubre `ALTER DEFAULT PRIVILEGES ... IN SCHEMA raw`
(`infra/sql/02_roles.sql`) más `apply_grants` cada noche.

## 6 · Riesgos y decisiones

- **DA-1 · `apu` entera y `--full`.** Incremental por `_source_tiemod` es
  imposible: `apu`, `asi`, `cua`, `apa` no tienen la columna (las
  «propiedades de `con`» la tienen en `con`, y F-011 no está activa). Por
  empresa: emp=1 es el 89,9 %, ahorra ≤ 10 % y exige subconsulta a `con` vía
  `asi`. Por ejercicio: 2017+ es el 85 %. Coste estimado ≤ 5 min y ~350 MB.
  Si R19 mide > 15 min, se reabre con cifra.
- **DA-2 · `apa` entra** (~1-2 min): desglose analítico por centro de coste
  con cuenta analítica (`caa`); candidata a fuente de la cuenta de resultados
  por obra de F-058. `obride` a 0: no es el puente obra↔centro de F-045.
- **DA-3 · Las 19 tablas vacías no se ingieren** (R3). En particular `act`,
  `auxacttip`, `actent`, `actseg` (CRM) y `auxfam`: **la actividad del
  proveedor en Ruesma es `conact` → `auxpronat`**, naturalezas de producto,
  y ahí sí hay dato. `homolo` = 0 en las 7.090 filas: «validada» no se
  informa en Sigrid; `prvcer` (certificados con caducidad) es lo más cercano.
  F-055 se replantea sobre estas dos.
- **DA-4 · `hmores` entra aunque la ficha no la nombraba**: las horas están
  ahí, no en `hmo`. Sin ella F-057 no responde «horas por obra».
- **DA-5 · Datos personales: se trae todo y se declara.** Decidido por el
  humano el 2026-09-06 frente a la propuesta inicial de excluir 72 columnas:
  `emp` y `res` entran enteras salvo las exclusiones técnicas de §3, y la
  ficha de cada una dice qué contiene (DNI, Seguridad Social, cuenta
  bancaria, domicilio, contacto, fecha de nacimiento, credenciales de
  acceso). Lo que se publique de eso lo decide F-057, no `raw`. **Aviso, y
  ahora con más motivo**: por decisión del 2026-08-08, `mcp_sigrid_dm_ro`
  lee **todos** los esquemas, `raw` incluido, así que `raw.emp` y `raw.res`
  serán legibles enteras por cualquier agente conectado al MCP. Opción fuera
  de esta spec: sacar `raw` de `PG_CONSUMPTION_SCHEMAS` o revocar `SELECT`
  sobre esas dos tablas (`infra/sql/` + humano).
- **DA-6 · Firmas = `confir` + `deffir`, no `PFfir`.** Responde «quién
  aprobó el comparativo, con qué rol y cuándo» (65.761 firmas). **No**
  responde la carencia (1) de Compras: los contratos (`tip = 44`) no pasan
  por `confir`, y para facturas (`tip = 15`) las 3.436 firmas vienen sin
  fecha. Es un hecho del origen, no un hueco de la ingesta.
- **DA-7 · Sigrid no guarda el histórico de estados de contratos ni
  facturas.** Confirmado dos veces con `leer_sql` (spec-author y líder):
  `concam` no tiene ninguna fila con `cam = 'est'` ni parecido, `confir` no
  tiene conceptos `tip = 44`, `ctr` no tiene fechas de circuito. Lo que sí
  hay: el estado actual (`con.est`), su nombre por tipo en **`conest`** (que
  por eso entra: 193 filas, sin ella `7` no significa «Firmado»), la alta
  (`con.fec`) y la última modificación (`con.tiemod`, ya en
  `raw.con._source_tiemod`), que sirve de **proxy de la antigüedad del
  estado actual** mientras la foto diaria no acumule historia. Decidido:
  el histórico se construye en **F-067** como foto diaria `(documento, est,
  fecha)` sobre `raw`, y empieza a contar el día que se despliegue. `concam`
  **no** se ingiere (1,5 M filas de cambios de forma de pago y fecha de
  factura); si F-067 lo pide, entra con `where: tip = 15`.
- **DA-8 · Condiciones del contrato: lo que hay.** Forma de pago
  (`ctr.pagide` → `auxpag`, `pagtex`, `pagfor`, ya en `raw`), retención
  (`ctrrec` + `rec`), garantía (`ctr.tipgar`: −1 en 7.408, 0 en 11.425, 1 en
  79, 2 en 7; `impavr`, `avride`). Penalización: sin campo; `ctr.tex` sigue
  excluida (738 informados, media 13 bytes) salvo que Compras confirme que la
  escriben ahí.
- **DA-9 · `dcf` recupera `pagtex` y `pagfor`** (R8): las condiciones de pago
  de la factura estaban excluidas por tamaño, no por decisión de negocio, y
  son la carencia (4). `dca` no cambia.
- **DA-10 · Ofertas y necesidades entran enteras** (`dco`, `dcopro`,
  `dcorec`, `dnc`, `dncpro`): son la cadena necesidad → comparativo →
  oferta → contrato que Compras pide ver, y `comlin` ya apunta a `dcopro` y
  `dncpro`. Coste ~+4 min y ~1,1 M filas; el mayor sumando tras `apu`.
- **DA-11 · El recuento se compara con un comando**, no a mano: 56 `COUNT(*)`
  en Sigrid cuestan segundos (`apu`: 0,3 s). Fuera de `run-all`.
- **Riesgo · la nocturna crece un 26 % en filas.** Con B2s sobra; R19/R20
  lo miden antes de bajar a B1ms. Si allí `ingest_raw` supera 45 min, F-065
  lo verá.
- **Riesgo · `apu.fec` contradice la ficha de F-056** («la fecha no está en
  `apu`»): está al 100 %. F-056 la contrasta contra `con.fec` vía `asi`.
- **Riesgo · `emp` cambia de esquema**: una columna de texto ilimitado nueva
  haría fallar el `COPY` (el YAML lo documenta). Mitigación: la ficha cuenta
  las 11 excluidas y anota revisar la lista si `emp` pasa de 161 columnas.

## 7 · Límite del microservicio

Copiar tablas de Sigrid a `raw` es la responsabilidad de este ETL. Fuera:
revocar permisos del MCP sobre `raw` (plataforma, `infra/sql/` + humano), el
histórico de estados por foto diaria (F-067, `stg`) y cualquier dato de
nómina o RRHH que no esté en Sigrid.

## 8 · Reconciliar columnas de un `raw` preexistente (R25-R28)

`ensure_raw_table` gana `_reconciliar_columnas_raw(cur, tabla, columnas)`, que
corre en la MISMA transacción que el `CREATE TABLE IF NOT EXISTS`.

- **De dónde salen las columnas reales**: `pg_attribute` + `format_type`, no
  `information_schema.columns`, porque hace falta el tipo CON su precisión
  (`character varying(30)`, `numeric(18,4)`) para poder compararlo.
- **DA-8 · antes del TRUNCATE, no después.** Si el DDL fallara después de
  vaciar, la tabla quedaría sin dato Y sin la columna: se habría destruido la
  carga de ayer sin poder cargar la de hoy. `ADD COLUMN` sin `DEFAULT` es
  metadato puro en Postgres —no reescribe la tabla—, así que adelantarlo no
  cuesta nada ni en `apu` (2,1 M filas). El orden ya era ése en el step
  (`ensure` en el punto 2, `truncate` en el 3); un test lo fija.
- **DA-9 · varias columnas, un solo `ALTER TABLE`.** Un bloqueo y un cambio
  atómico: `dcf` necesita `pagfor` y `pagtex` a la vez.
- **DA-10 · comparar tipos exige normalizar.** El ETL escribe `VARCHAR(30)` y
  el catálogo devuelve `character varying(30)`. Sin `_tipo_normalizado` el
  aviso saltaría en cada columna de cada tabla, todas las noches, y el log
  dejaría de servir para ver los cambios de verdad.
