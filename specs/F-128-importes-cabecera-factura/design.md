# F-128 · Diseño: la cabecera entera de factura y albarán, sus recargos y el cuadre de retenciones

Requisitos: `requirements.md` (R1-R36; D1-A, D2-B, D3-A, D4-B, D5-A cerradas por el humano el
2026-10-17). Mediciones: `progress/spec_F-128.md`.

## 1. Encaje y límite del servicio

Todo es ETL de este datamart sobre tablas que YA se ingieren (`dcf`, `dca`, `dcfrec`, `dcarec`,
`con`, `auxpag`, `auxefp`, `auxban`): ni ingesta nueva, ni `sigrid-api`, ni otro proyecto. Tres
esquemas:
- **`compras`**: la cabecera (columnas AL FINAL de `facturas` y `albaranes`) y los recargos de
  cada documento (dos tablas nuevas). Es donde viven el documento y sus líneas.
- **`compras_restringida`** (D4-B): la cuenta bancaria del proveedor que lleva cada documento.
  Ya existe (F-138) y es del perfil total; nadie del estándar ni del restringido (F-141) la lee.
- **`retenciones`**: el cuadre factura ↔ mayor ↔ efectos. Vive junto al de F-095
  (`v_cuadre_proveedor`) y, como todo `retenciones`, lee SOLO `raw`, `maestro` y sus propias
  tablas (`main.py`: «`compras` y `retenciones` solo leen de `raw`»). Leer `compras.facturas`
  lo ataría a `build_compras` y un `DROP … CASCADE` de `compras` se llevaría la vista.

Permisos: `apply_grants` concede y veta POR ESQUEMA (`ON ALL TABLES IN SCHEMA`). Lo nuevo de
`compras` y `retenciones` lo leen estándar, total y (F-141) restringido sin tocar nada; la tabla de
`compras_restringida` queda vetada al estándar (`PG_VETOED_SCHEMAS`), fuera del restringido (F-141
R5/R12) y concedida al autorizado, del que es miembro el total; `lecturas_indebidas` ya vigila todo
el esquema cada noche. No cambian `grants.py`, `settings.py` ni `02_roles.sql` (R22), ni `mcp-bbdd`
(ya tiene `compras_restringida` en `esquemas_permitidos`). Consumidores (Power BI, MCP, portal
`retenciones`) leen por nombre de columna, sin `SELECT *`: añadir AL FINAL no rompe a nadie.

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/cabecera_compra.py` | Oráculo puro: `CLASES_RECARGO`, `clase_recargo`, `es_retencion_garantia`, `es_retencion_fiscal`, `MOTIVOS`, `INVENTARIO_DCF`, `INVENTARIO_DCA`, `publicadas(inventario, objeto)` |
| `etl_sigrid/infrastructure/postgres/sql/retenciones/07_cuadre_factura.sql` | `retenciones.retencion_factura` (tabla) y `retenciones.v_cuadre_factura_obra` (vista) |
| `tests/test_f128_dominio.py` | R1-R4 |
| `tests/test_f128_sql.py` | R5-R19, R24, R32-R33 sobre el TEXTO del SQL (no se ejecuta: Postgres compartido) |
| `tests/test_f128_restringida.py` | R20-R23 (texto del SQL, defectos de `settings`, barrido de cuentas) |
| `tests/test_f128_diccionario.py` | R25-R31, R34 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `sql/compras/00_setup.sql` | + `compras.fn_clase_recargo(reccla INT)` y `compras.fn_es_retencion_garantia(reccla INT)` |
| `sql/compras/01_documentos.sql` | Cabecera del fichero (bloque F-128); sección RECARGOS (dos tablas) ANTES de ALBARANES; columnas nuevas AL FINAL de `albaranes` y `facturas`; sección CUENTA BANCARIA (`compras_restringida`) la ÚLTIMA |
| `sql/retenciones/00_setup.sql` | + `retenciones.fn_es_retencion_garantia`, copia deliberada (R19) |
| `etl_sigrid/application/steps/build_retenciones_step.py` | + `_SubStep("cuadre_factura", "07_cuadre_factura.sql", "retenciones", "retencion_factura")` el último; docstring |
| `etl_sigrid/application/steps/build_compras_step.py` | Solo el comentario del sub-paso `documentos` (ahora deja también la tabla de R20) |
| `main.py` | Docstring de `build-retenciones`: + `07_cuadre_factura.sql` (solo texto) |
| `tests/test_f095_retenciones_contables.py` | `FICHEROS_RETENCIONES` + `07_cuadre_factura.sql` (solo esa lista) |
| `config/diccionario/compras.yaml` | Columnas nuevas de `facturas` y `albaranes`, lo no publicado, fichas de `factura_recargos`, `albaran_recargos`, las dos funciones; relaciones |
| `config/diccionario/compras_restringida.yaml` | Ficha de `documento_cuenta_bancaria` (R30); comentario de cabecera: el esquema guarda ya dos cosas |
| `config/diccionario/retenciones.yaml` | Fichas de `retencion_factura`, `v_cuadre_factura_obra`, `fn_es_retencion_garantia`; `v_cuadre_proveedor` gana relación y aviso AGR |
| `config/diccionario/00_global.yaml` | `version` = la de `main` + 1 al merge, entrada «(F-128» en la historia; `R-COMPRAS-RESTRINGIDA.regla` + un párrafo (R30), `ambito` igual (lo fija `test_f138_r26_la_regla_dura`) |
| `docs/ARCHITECTURE.md` | «Semántica Sigrid»: `totdoc`/`tot`/`totpag`, `reccla` y `RETESP` (≤ 15 líneas); `compras_restringida` guarda también la cuenta del proveedor |
| `CLAUDE.md` | Mapa: una frase en la entrada de `compras/` (la cuenta del proveedor va a `compras_restringida`) |
| `azure-apps/datamart_seg_anual.md` | Lo expuesto: columnas, 2 tablas de `compras`, 1 de `compras_restringida` (solo total), 2 objetos de `retenciones` (otro repo: commit local) |

## 4. Ficheros que NO se tocan

`tables_sigrid.yaml` (sin ingesta), `settings.py`, `grants.py`, `02_roles.sql` (§1),
`02_fact_linea.sql` y `03_views.sql` (la atribución por línea no cambia), `06_pago_factura.sql`
(`v_facturas_pago` ya publica de la factura `pagide`, `efeide`, `cueide`, `banide`, banco y
sucursal, `pagfor`, `pagtex` desde F-080: ni se duplican ni se mueven; §12),
`15_alarmas_liquidatoria.sql`, los 01-06 de `retenciones` (F-095), `progress/current.md`.

## 5. Dominio · `etl_sigrid/domain/cabecera_compra.py`

```python
CLASES_RECARGO: Final[dict[int, str]] = {0: "RECARGO", 1: "DESCUENTO", 3: "RETENCION_FISCAL",
    4: "RETENCION_GARANTIA_TOTAL", 5: "RETENCION_GARANTIA_BASE"}
def clase_recargo(reccla: int | None) -> str: ...            # "OTRA" fuera del mapa
def es_retencion_garantia(reccla: int | None) -> bool: ...   # reccla in (4, 5); D2-B
def es_retencion_fiscal(reccla: int | None) -> bool: ...
MOTIVOS: Final[frozenset[str]]                              # los siete de R3
INVENTARIO_DCF / INVENTARIO_DCA: Final[dict[str, tuple[str, str]]]
def publicadas(inventario, objeto: str) -> list[str]: ...   # columnas PUBLICADO en ese objeto
```
`INVENTARIO_*` es DATO medido el 2026-10-17 (informe §5 y §7): el contrato que los tests
contrastan con el SQL; una columna nueva de `raw.dcf` se detecta con la consulta MANUAL de §11.
Si está publicada en dos objetos, las dos rutas con ` + ` (`dcf.banban` →
`compras.v_facturas_pago.banco + compras_restringida.documento_cuenta_bancaria.banco_id`).
Bancarias: `ban`, `bancue`, `bandig` (las dos) y `dca.banban`/`bansuc` → `compras_restringida`;
`bantipide` → CATALOGO_NO_INGERIDO (`auxcueban`); `dca.banide` → INTERNO (cuenta propia, 0,9 %).

## 6. SQL · `compras`

**`00_setup.sql`** (funciones `IMMUTABLE`, `LANGUAGE sql`, con `COMMENT`):
```sql
compras.fn_clase_recargo(reccla INT) RETURNS TEXT
  -- CASE reccla WHEN 0 THEN 'RECARGO' WHEN 1 THEN 'DESCUENTO' WHEN 3 THEN 'RETENCION_FISCAL'
  --   WHEN 4 THEN 'RETENCION_GARANTIA_TOTAL' WHEN 5 THEN 'RETENCION_GARANTIA_BASE' ELSE 'OTRA' END
compras.fn_es_retencion_garantia(reccla INT) RETURNS BOOLEAN
  -- COALESCE(reccla IN (4, 5), FALSE)   -- D2-B: el RETESP (clase 1) NO; el COMMENT lo dice
```

**`01_documentos.sql` · sección RECARGOS Y RETENCIONES (nueva, antes de ALBARANES)**:
`DROP TABLE IF EXISTS compras.factura_recargos CASCADE; CREATE TABLE … AS SELECT` desde
`raw.dcfrec r LEFT JOIN raw.con x ON x.ide = r.recide` (3 filas sin concepto) y `LEFT JOIN
raw.con cue ON cue.ide = NULLIF(r.cueide, 0)`, `WHERE EXISTS (SELECT 1 FROM raw.dcf f WHERE f.ide
= r.docide)` (mismo patrón que las líneas). Columnas de R12; `porcentaje = ROUND((valpor *
100)::NUMERIC, 4)` como `ctrrec` en F-067. PK `recargo_id`; índices en `factura_id` y
`es_retencion_garantia`. `compras.albaran_recargos` igual sobre `raw.dcarec` y `raw.dca`.
Van ANTES porque `facturas` y `albaranes` los agregan; ninguno depende de ellos con `CASCADE`.

**Bloque ALBARANES**: la proyección de 12 columnas intacta; detrás, en el orden de R10:
```sql
COALESCE(a.impbru, 0)::NUMERIC(18,2) AS importe_bruto, … COALESCE(a.totdoc, 0) AS total_documento,
(COALESCE(a.totdoc, 0) - COALESCE(a.totpag, 0))::NUMERIC(18,2) AS importe_retenciones,
COALESCE(rec.garantia, 0)::NUMERIC(18,2) AS importe_retencion_garantia, …
compras.fn_sigrid_date(a.fecdoc) AS fecha_documento, NULLIF(a.pagide, 0) AS forma_pago_id,
pag.res AS forma_pago, NULLIF(a.efeide, 0) AS medio_pago_id, efp.res AS medio_pago,
cue.cod AS cuenta_contable, NULLIF(a.obride, 0) AS obra_cabecera_id, obr.cod AS
codigo_obra_cabecera, … (a.estfac = 1) AS facturado_sigrid (COALESCE a FALSE), …
```
Joins nuevos, todos `LEFT`: `raw.auxpag`, `raw.auxefp`, `raw.con` (cuenta, obra, centro) y
`(SELECT albaran_id, SUM(cuota) FILTER (WHERE es_retencion_garantia) AS garantia, SUM(cuota)
FILTER (WHERE clase_recargo = 'RETENCION_FISCAL') AS fiscal FROM compras.albaran_recargos GROUP BY
albaran_id) rec ON rec.albaran_id = a.ide`. Agregar antes de unir es la guarda de grano (R7).
`ivadif`/`tipisp`: `COALESCE(x <> 0, FALSE)`. «Nombre del proveedor en el documento» =
`NULLIF(btrim(a.entres), '')`; ídem `entcod`, `entciftip`, `entcifpai`. Ni un `ban*`.

**Bloque FACTURAS**: lo mismo con R5; los joins nuevos van DETRÁS de `LEFT JOIN LATERAL
compras.fn_estado_documento(15, con.est) est ON TRUE` (lo exige `test_f083_sql`: ningún `WHERE`
entre `FROM raw.dcf f` y el primer lateral) y la agregación sale de `compras.factura_recargos`.
`contrato_id = NULLIF(f.ctride, 0)`. Sin `WHERE` externo: `count(facturas) = count(raw.dcf)`.
La cabecera del fichero gana un bloque «F-128» con el porqué (cifras de §2 del informe), en la
misma disciplina que F-083/F-084/F-067: las columnas de siempre no se tocan.

## 7. SQL · `compras_restringida.documento_cuenta_bancaria` (D4-B, final de `01_documentos.sql`)

```sql
CREATE TABLE compras_restringida.documento_cuenta_bancaria AS   -- tras DROP TABLE IF EXISTS … CASCADE
WITH doc AS (SELECT f.ide, 'FACTURA'::TEXT AS tipo, f.fecdoc, f.entide, f.banban, f.bansuc,
                    f.bandig, f.bancue, f.ban FROM raw.dcf f WHERE NULLIF(btrim(f.ban), '') IS NOT NULL
             UNION ALL SELECT a.ide, 'ALBARAN', … FROM raw.dca a WHERE NULLIF(btrim(a.ban), '') IS NOT NULL)
SELECT d.ide AS documento_id, d.tipo AS tipo_documento, c.cod AS codigo_documento,
       compras.fn_sigrid_date(d.fecdoc) AS fecha_documento, …, bb.res AS banco, …,
       NULLIF(btrim(d.bancue), '') AS numero_cuenta, btrim(d.ban) AS cuenta_bancaria
FROM doc d LEFT JOIN raw.con c … LEFT JOIN raw.con prv … LEFT JOIN raw.auxban bb … LEFT JOIN raw.auxban bs …;
```
PK `documento_id` (0 `ide` comunes entre `dcf` y `dca`); índice en `proveedor_id`; `COMMENT`
que EMPIEZA por «ACCESO RESTRINGIDO». Universo = `ban` informado, el superconjunto medido (nadie
tiene `bancue`, `bandig` o `banban` sin `ban`): ~17.706 facturas y ~17.756 albaranes. Al final del
fichero: nadie la lee. Elecciones del spec-author dentro de D4-B (informe §7): `bantipide` fuera
(catálogo `auxcueban` no ingerido, no predice el formato; como D5-A), `cuenta_bancaria` tal cual
(sin normalizar ni convertir CCC ↔ IBAN) y `dca.banide` fuera.

## 8. SQL · `retenciones/07_cuadre_factura.sql`

Cabecera: qué construye, qué lee (`raw.dcf`, `raw.dcfrec`, `raw.con`, `retenciones.apuntes_contables`,
`retenciones.movimientos`, `retenciones.saldo_contable`) y las cifras de §4 del informe.
```sql
CREATE TABLE retenciones.retencion_factura AS        -- tras DROP TABLE IF EXISTS … CASCADE
WITH garantia AS (SELECT r.docide AS factura_id, SUM(r.cuo) AS retencion FROM raw.dcfrec r  -- ANTES de unir
    WHERE retenciones.fn_es_retencion_garantia(r.reccla) GROUP BY r.docide),               -- D2-B: 4 y 5
contable AS (SELECT documento_id, SUM(importe) AS importe FROM retenciones.apuntes_contables
    WHERE clase IN ('ALTA', 'BAJA') AND documento_id IS NOT NULL GROUP BY documento_id),
efectos AS (SELECT documento_id, SUM(importe) FILTER (WHERE estado <> 'BAJA' OR estado_sigrid = 14)
    AS generados, SUM(importe) FILTER (WHERE estado = 'VIVA') AS vivos FROM retenciones.movimientos
    WHERE sentido = 'PROVEEDOR' AND documento_id IS NOT NULL GROUP BY documento_id),
universo AS (SELECT factura_id FROM garantia WHERE ABS(retencion) >= 0.01 UNION SELECT documento_id FROM contable)
SELECT … FROM universo u JOIN raw.dcf f ON f.ide = u.factura_id JOIN raw.con c ON c.ide = f.ide
LEFT JOIN garantia g … LEFT JOIN contable ct … LEFT JOIN efectos e … LEFT JOIN raw.con prv …
LEFT JOIN raw.con ob ON ob.ide = NULLIF(f.obride, 0);
```
El `JOIN raw.dcf` deja fuera los `documento_id` contables que no son factura (efectos, AGR).
`empresa_id`/`clave_obra` como `03_apuntes_contables.sql` (`ob.emp`, `ob.emp || '-' || ob.cod`).
`retencion_factura` = `COALESCE(g.retencion, 0)`; categorías con `CASE` en el orden de R17; PK
`factura_id`, índices en `proveedor_id` y `obra_id`, `COMMENT`. Con D2-B las 42 facturas `RETESP`
con asiento salen SOLO_CONTABLE (de 175): correcto, lo explica la ficha, sin caso especial en SQL.

`retenciones.v_cuadre_factura_obra` (`DROP VIEW IF EXISTS … CASCADE; CREATE VIEW`): agregado de
`retencion_factura` por (`proveedor_id`, `obra_id`) `FULL JOIN` `saldo_contable` (una fila por par)
`ON c.proveedor_id = f.proveedor_id AND c.obra_id IS NOT DISTINCT FROM f.obra_id`; nombres del lado
que exista; `WHERE ABS(retencion_facturas) >= 1 OR ABS(altas_contables) >= 1`, como `v_cuadre_proveedor`.

`retenciones/00_setup.sql`: `retenciones.fn_es_retencion_garantia` con el MISMO cuerpo que la de
`compras` (patrón `tesoreria` F-037, `test_f037_funciones_copiadas_de_compras`).

## 9. Diccionario semántico

- `compras.facturas` y `compras.albaranes`: una ficha por columna nueva (significado, cobertura
  del §5, `agregacion`: importes `sumable` con el aviso de `R-ABONO-NEGATIVO`, ids
  `no_sumable`). Descripción: + párrafo «LA CABECERA ENTERA (F-128)» con la identidad
  `total_factura = base_imponible + cuota_iva`, `importe_retenciones = total_factura −
  total_a_pagar = garantía + fiscal` y lo NO publicado por motivo (R26), con la cuenta del
  proveedor «solo en `compras_restringida` (perfil total)». Obra de cabecera: «para AUDITAR; para
  imputar coste, la de la línea» (lo que F-093 pidió nombrar).
- `factura_recargos` / `albaran_recargos`: grano, clave `recargo_id`, cobertura (19,7 % / 13,2 %
  de los documentos), `clase_recargo` con `valores`, `RETESP`, «no sumar albarán + factura».
- `RETESP` (R29): «clase DESCUENTO que Sigrid usa como retención del 5 % sin IVA; aquí NO es
  garantía (decisión del 2026-10-17); está en `importe_descuentos`, no en `importe_retenciones`;
  su asiento va a la cuenta de retención en 42 de las 44 facturas; búscalo por `codigo_concepto`».
- `documento_cuenta_bancaria` (R30): aviso de acceso primero, grano, cobertura (10,6 % / 5,7 %),
  IBAN 44 % / 68 % y CCC el resto, «la cuenta del documento: = ficha actual del proveedor en el
  31 % / 72 %». `R-COMPRAS-RESTRINGIDA`: + «las cuentas de proveedor no tienen versión general:
  sin el perfil total, dilo y no las busques por otro camino».
- `retencion_factura`: universo, de dónde sale cada lado, categorías con sus cifras, ejemplo de
  Juan (R28). `v_cuadre_factura_obra`: 5.304 de 6.109 pares; diferencia con `v_cuadre_proveedor`.
- `00_global.yaml`: versión e historia. No hay regla dura nueva. Sin pendientes nuevos.

## 10. Tests (sin red ni BBDD)

- `test_f128_dominio.py`: tabla de casos de `clase_recargo` y `es_retencion_garantia` (0-5,
  `None`, 2, 1 = falso aunque sea `RETESP`); R4 con inventarios fabricados; los inventarios
  reales sin motivos fuera de `MOTIVOS` y con las bancarias de §5.
- `test_f128_sql.py`: prefijo de columnas de siempre y orden exacto de las nuevas (R5, R10) leyendo
  la proyección entre `SELECT` y `FROM raw.dc? ?`; expresión de cada importe (R6); agregación
  previa con `GROUP BY` (R7); `NULLIF`/`COALESCE` (R8); sin `WHERE` externo y joins tras el
  lateral (R9); `CASE` de las funciones = `CLASES_RECARGO` y R2 (R14); cuerpos iguales (R19);
  `SUB_PASOS` (R24); `publicadas(INVENTARIO_*, …)` = columnas del SQL de cada objeto (R3); ni
  `empide` ni `hor` (R32); `tables_sigrid.yaml` sin los catálogos ni `pagfor`/`pagtex` (R33).
- `test_f128_restringida.py`: columnas y orden de R20, `WHERE` de `ban` en las dos ramas, solo
  `raw`; barrido de `sql/**/*.sql` sin el bloque de R20 (R21, con un positivo fabricado); R22
  (`skip` del restringido si F-141 aún no está); R23 sobre `git diff --name-only main...HEAD` (sin
  `git`, `skip` con motivo) y sobre un positivo fabricado.
- `test_f128_diccionario.py`: fichas = columnas del SQL; frases obligatorias de R25-R30;
  relaciones; versión ≥ `git show main:config/diccionario/00_global.yaml` + 1 (si no hay `git` o
  `main`, `skip` con motivo); textos de `ARCHITECTURE.md`, `CLAUDE.md` y `azure-apps` (R34).

## 11. Despliegue y verificación (MANUAL, humano, tras el review)

1. Imagen nueva del job (la nocturna termina en `apply_grants`), o a mano `python main.py
   build-compras`, `build-retenciones` y `apply-grants` en Azure.
2. Comprobación del inventario: `SELECT column_name FROM information_schema.columns WHERE
   table_schema = 'raw' AND table_name IN ('dcf','dca')` contra las claves de `INVENTARIO_*`.
3. Las cifras de R35 con las consultas del informe; con el login estándar, `SELECT 1 FROM
   compras_restringida.documento_cuenta_bancaria LIMIT 1` → «permission denied»;
   `python main.py check-diccionario`.
4. `python main.py publicar-diccionario` (escritura: la autoriza el humano) y reiniciar el MCP
   (cachea el diccionario); las dos preguntas de R36.

## 12. Riesgos y decisiones

- **Tabla ancha.** `facturas` pasa de 15 a 42 columnas y `albaranes` de 12 a 46. Alternativa
  descartada: una tabla aparte `factura_cabecera` (1:1): obliga a un `JOIN` para lo que Juan pide
  ver en la factura, y F-083/F-084/F-067 ya fijaron el patrón «al final».
- **`tot` frente a `totpag`.** Sigrid los documenta distintos; medido iguales en el 100 %. Se
  publica `totpag`; si un día difieren, R35 lo detecta (la identidad deja de cumplirse).
- **El cuadre por factura y no por efecto.** Por efecto no se puede: los AGR pierden la factura.
  Con D2-B, contabilidad cuadra al 99,1 % y efectos al 84,2 % (sin el estado 14, al 33 %).
- **Obra del cuadre = obra de cabecera** (`dcf.obride`), no la cascada de F-095: coincide en el
  99,8 % de las facturas enlazadas y es la que Administración ve en la factura.
- **Merge con F-141** (en curso): las dos tocan `R-COMPRAS-RESTRINGIDA`, `ARCHITECTURE.md`,
  `CLAUDE.md` y la versión del diccionario; la segunda en llegar a `main` rebasa y conserva los dos.
- **Banco y sucursal ya en el estándar**: `v_facturas_pago` (F-080) da sus NOMBRES; no son la
  cuenta y F-128 no lo cambia (informe §7). **Autónomos**: su cuenta es dato personal; solo al
  total por D4-B y ningún valor en el repositorio (R23).
- **Rendimiento**: agregados sobre ≤ 41.466 filas, ~35.500 cuentas, joins por PK. **F-130**
  reutiliza `factura_recargos`; F-091 no se toca, pero `total_factura` ya es consultable.
