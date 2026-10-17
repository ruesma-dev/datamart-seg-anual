# F-128 · Diseño: la cabecera entera de factura y albarán, sus recargos y el cuadre de retenciones

Requisitos: `requirements.md` (R1-R31, D1-D5 con la opción A). Mediciones: `progress/spec_F-128.md`.

## 1. Encaje y límite del servicio

Todo es ETL de este datamart sobre tablas que YA se ingieren (`dcf`, `dca`, `dcfrec`, `dcarec`,
`con`, `auxpag`, `auxefp`): ni ingesta nueva, ni `sigrid-api`, ni otro proyecto. Dos esquemas:
- **`compras`**: la cabecera (columnas AL FINAL de `facturas` y `albaranes`) y los recargos de
  cada documento (dos tablas nuevas). Es donde viven el documento y sus líneas.
- **`retenciones`**: el cuadre factura ↔ mayor ↔ efectos. Vive junto al de F-095
  (`v_cuadre_proveedor`) y, como todo `retenciones`, lee SOLO `raw`, `maestro` y sus propias
  tablas (`main.py`: «`compras` y `retenciones` solo leen de `raw`»). Leer `compras.facturas`
  lo ataría a `build_compras` y un `DROP … CASCADE` de `compras` se llevaría la vista.

Permisos: los dos esquemas los leen el estándar, el total y (tras F-141) el restringido, que «ve
retenciones» y `compras` entera. `apply_grants` concede por esquema (`grants.py`, `ON ALL TABLES
IN SCHEMA`): los objetos nuevos quedan cubiertos sin tocar grants ni `02_roles.sql`. Nada de lo
publicado es personal ni bancario (D4-A deja fuera las cuentas del proveedor).
Consumidores: Power BI, el MCP y el portal `retenciones` (lee vistas de `retenciones` y `compras`
por nombre de columna, ninguna con `SELECT *`): añadir columnas AL FINAL no rompe a nadie.

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/cabecera_compra.py` | Oráculo puro: `CLASES_RECARGO`, `clase_recargo`, `es_retencion_garantia`, `es_retencion_fiscal`, `MOTIVOS`, `INVENTARIO_DCF`, `INVENTARIO_DCA`, `publicadas(inventario, objeto)` |
| `etl_sigrid/infrastructure/postgres/sql/retenciones/07_cuadre_factura.sql` | `retenciones.retencion_factura` (tabla) y `retenciones.v_cuadre_factura_obra` (vista) |
| `tests/test_f128_dominio.py` | R1-R4 |
| `tests/test_f128_sql.py` | R5-R20, R27-R28 sobre el TEXTO del SQL (no se ejecuta: Postgres compartido) |
| `tests/test_f128_diccionario.py` | R21-R26, R29 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `sql/compras/00_setup.sql` | + `compras.fn_clase_recargo(reccla INT)` y `compras.fn_es_retencion_garantia(reccla INT, codigo TEXT)` |
| `sql/compras/01_documentos.sql` | Cabecera del fichero (bloque F-128); sección RECARGOS (dos tablas) ANTES de ALBARANES; columnas nuevas AL FINAL de `albaranes` y `facturas` |
| `sql/retenciones/00_setup.sql` | + `retenciones.fn_es_retencion_garantia`, copia deliberada (R19) |
| `etl_sigrid/application/steps/build_retenciones_step.py` | + `_SubStep("cuadre_factura", "07_cuadre_factura.sql", "retenciones", "retencion_factura")` el último; docstring |
| `main.py` | Docstring de `build-retenciones`: + `07_cuadre_factura.sql` (solo texto) |
| `tests/test_f095_retenciones_contables.py` | `FICHEROS_RETENCIONES` + `07_cuadre_factura.sql` (solo esa lista) |
| `config/diccionario/compras.yaml` | Columnas nuevas de `facturas` y `albaranes`, lo no publicado, fichas de `factura_recargos`, `albaran_recargos`, las dos funciones; relaciones |
| `config/diccionario/retenciones.yaml` | Fichas de `retencion_factura`, `v_cuadre_factura_obra`, `fn_es_retencion_garantia`; `v_cuadre_proveedor` gana relación y aviso AGR |
| `config/diccionario/00_global.yaml` | `version` = la de `main` + 1 al merge, entrada «(F-128» en la historia |
| `docs/ARCHITECTURE.md` | «Semántica Sigrid»: `totdoc`/`tot`/`totpag`, `reccla` y `RETESP` (≤ 15 líneas) |
| `azure-apps/datamart_seg_anual.md` | Lo expuesto: columnas, 2 tablas de `compras`, 2 objetos de `retenciones` (otro repo: commit local) |

## 4. Ficheros que NO se tocan

`config/tables_sigrid.yaml` (D3-A: sin ingesta), `02_fact_linea.sql` y `03_views.sql` (la
atribución de coste por línea no cambia), `06_pago_factura.sql` (`v_facturas_pago` ya publica
`pagide`, `efeide`, `cueide`, `banide`, `banban`, `bansuc`, `pagfor`, `pagtex` de la factura: no
se duplican en `facturas`), `15_alarmas_liquidatoria.sql` (F-138), los ficheros 01-06 de
`retenciones` (F-095: se leen, no se cambian), `grants.py`, `infra/sql/02_roles.sql`,
`harness/features.json` y `progress/current.md` (los actualiza el líder tras D1-D5).

## 5. Dominio · `etl_sigrid/domain/cabecera_compra.py`

```python
CLASES_RECARGO: Final[dict[int, str]] = {0: "RECARGO", 1: "DESCUENTO", 3: "RETENCION_FISCAL",
    4: "RETENCION_GARANTIA_TOTAL", 5: "RETENCION_GARANTIA_BASE"}
def clase_recargo(reccla: int | None) -> str: ...            # "OTRA" fuera del mapa
def es_retencion_garantia(reccla: int | None, codigo: str | None) -> bool: ...
def es_retencion_fiscal(reccla: int | None) -> bool: ...
MOTIVOS: Final[frozenset[str]]                              # los ocho de R3
INVENTARIO_DCF / INVENTARIO_DCA: Final[dict[str, tuple[str, str]]]
def publicadas(inventario, objeto: str) -> list[str]: ...   # columnas PUBLICADO de ese objeto
```
`INVENTARIO_*` es DATO medido el 2026-10-17 (§5 del informe), no se descubre en ejecución: es el
contrato que los tests contrastan con el SQL. Una columna de `raw.dcf` que el inventario no
conozca se detecta en Azure con la consulta MANUAL de §10 (paso 3). Ya publicadas en otro objeto
llevan `("PUBLICADO", "compras.v_facturas_pago.<col>")`.

## 6. SQL · `compras`

**`00_setup.sql`** (funciones `IMMUTABLE`, `LANGUAGE sql`, con `COMMENT`):
```sql
compras.fn_clase_recargo(reccla INT) RETURNS TEXT
  -- CASE reccla WHEN 0 THEN 'RECARGO' WHEN 1 THEN 'DESCUENTO' WHEN 3 THEN 'RETENCION_FISCAL'
  --   WHEN 4 THEN 'RETENCION_GARANTIA_TOTAL' WHEN 5 THEN 'RETENCION_GARANTIA_BASE' ELSE 'OTRA' END
compras.fn_es_retencion_garantia(reccla INT, codigo TEXT) RETURNS BOOLEAN
  -- COALESCE(reccla IN (4, 5) OR (reccla = 1 AND upper(btrim(codigo)) LIKE 'RET%'), FALSE)
```

**`01_documentos.sql` · sección RECARGOS Y RETENCIONES (nueva, antes de ALBARANES)**:
`DROP TABLE IF EXISTS compras.factura_recargos CASCADE; CREATE TABLE … AS SELECT` desde
`raw.dcfrec r JOIN raw.con x ON x.ide = r.recide` (`LEFT`: 3 filas sin concepto) y `LEFT JOIN
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
`NULLIF(btrim(a.entres), '')`; ídem `entcod`, `entciftip`, `entcifpai`.

**Bloque FACTURAS**: lo mismo con R5; los joins nuevos van DETRÁS de `LEFT JOIN LATERAL
compras.fn_estado_documento(15, con.est) est ON TRUE` (lo exige `test_f083_sql`: ningún `WHERE`
entre `FROM raw.dcf f` y el primer lateral) y la agregación sale de `compras.factura_recargos`.
`contrato_id = NULLIF(f.ctride, 0)`. Sin `WHERE` externo: `count(facturas) = count(raw.dcf)`.
La cabecera del fichero gana un bloque «F-128» con el porqué (cifras de §2 del informe), en la
misma disciplina que F-083/F-084/F-067: las columnas de siempre no se tocan.

## 7. SQL · `retenciones/07_cuadre_factura.sql`

Cabecera: qué construye, qué lee (`raw.dcf`, `raw.dcfrec`, `raw.con`, `retenciones.apuntes_contables`,
`retenciones.movimientos`, `retenciones.saldo_contable`) y las cifras de §4 del informe.
```sql
DROP TABLE IF EXISTS retenciones.retencion_factura CASCADE;
CREATE TABLE retenciones.retencion_factura AS
WITH garantia AS (            -- por factura, ANTES de unir
    SELECT r.docide AS factura_id, SUM(r.cuo) AS retencion
    FROM raw.dcfrec r LEFT JOIN raw.con x ON x.ide = r.recide
    WHERE retenciones.fn_es_retencion_garantia(r.reccla, x.cod) GROUP BY r.docide),
contable AS (SELECT documento_id, SUM(importe) AS importe FROM retenciones.apuntes_contables
    WHERE clase IN ('ALTA', 'BAJA') AND documento_id IS NOT NULL GROUP BY documento_id),
efectos AS (SELECT documento_id,
    SUM(importe) FILTER (WHERE estado <> 'BAJA' OR estado_sigrid = 14) AS generados,
    SUM(importe) FILTER (WHERE estado = 'VIVA') AS vivos
    FROM retenciones.movimientos WHERE sentido = 'PROVEEDOR' AND documento_id IS NOT NULL
    GROUP BY documento_id),
universo AS (SELECT factura_id FROM garantia WHERE ABS(retencion) >= 0.01
    UNION SELECT documento_id FROM contable)
SELECT … FROM universo u JOIN raw.dcf f ON f.ide = u.factura_id JOIN raw.con c ON c.ide = f.ide
LEFT JOIN garantia g … LEFT JOIN contable ct … LEFT JOIN efectos e … LEFT JOIN raw.con prv …
LEFT JOIN raw.con ob ON ob.ide = NULLIF(f.obride, 0);
```
El `JOIN raw.dcf` deja fuera los `documento_id` contables que no son factura (efectos, AGR).
`empresa_id`/`clave_obra` como `03_apuntes_contables.sql` (`ob.emp`, `ob.emp || '-' || ob.cod`).
`retencion_factura` = `COALESCE(g.retencion, 0)`. Categorías con `CASE` en el orden de R17.
PK `factura_id`; índices en `proveedor_id` y `obra_id`; `COMMENT ON TABLE`.

`retenciones.v_cuadre_factura_obra` (`DROP VIEW IF EXISTS … CASCADE; CREATE VIEW`): `facturas` =
agregado de `retencion_factura` por (`proveedor_id`, `obra_id`); `contable` =
`saldo_contable` (ya es una fila por par, `NULLS NOT DISTINCT`); `FULL JOIN … ON
c.proveedor_id = f.proveedor_id AND c.obra_id IS NOT DISTINCT FROM f.obra_id`; nombre de
proveedor y obra del lado que exista; `WHERE ABS(retencion_facturas) >= 1 OR
ABS(altas_contables) >= 1`. Mismo estilo y tolerancia (1 €) que `v_cuadre_proveedor`.

`retenciones/00_setup.sql`: `retenciones.fn_es_retencion_garantia` con el MISMO cuerpo que la de
`compras` (patrón `tesoreria` F-037, `test_f037_funciones_copiadas_de_compras`).

## 8. Diccionario semántico

- `compras.facturas` y `compras.albaranes`: una ficha por columna nueva (significado, cobertura
  del §5, `agregacion`: importes `sumable` con el aviso de `R-ABONO-NEGATIVO`, ids
  `no_sumable`). Descripción: + párrafo «LA CABECERA ENTERA (F-128)» con la identidad
  `total_factura = base_imponible + cuota_iva`, `importe_retenciones = total_factura −
  total_a_pagar = garantía + fiscal` y lo NO publicado por motivo (R22). Obra de cabecera: «para
  AUDITAR; para imputar coste, la de la línea» (lo que F-093 pidió nombrar).
- `factura_recargos` / `albaran_recargos`: grano, clave `recargo_id`, cobertura (19,7 % / 13,2 %
  de los documentos), `clase_recargo` con `valores`, `RETESP`, «no sumar albarán + factura».
- `retencion_factura`: universo, de dónde sale cada lado, categorías con sus cifras, ejemplo de
  Juan (R24). `v_cuadre_factura_obra`: 5.302 de 6.108 pares; diferencia con `v_cuadre_proveedor`.
- `00_global.yaml`: versión e historia. No hay regla dura nueva: las trampas van en sus fichas.
  Sin pendientes nuevos.

## 9. Tests (sin red ni BBDD)

- `test_f128_dominio.py`: tabla de casos de `clase_recargo` y `es_retencion_garantia` (0-5,
  `None`, 2, `RETESP`, `ret5` en minúscula, `des02`, `RET5` con clase 3 = falso); R4 con
  inventarios fabricados; los inventarios reales sin motivos fuera de `MOTIVOS`.
- `test_f128_sql.py`: prefijo de columnas de siempre y orden exacto de las nuevas (R5, R10) leyendo
  la proyección entre `SELECT` y `FROM raw.dc? ?`; expresión de cada importe (R6); agregación
  previa con `GROUP BY` (R7); `NULLIF`/`COALESCE` (R8); sin `WHERE` externo y joins tras el
  lateral (R9); `CASE` de las funciones = `CLASES_RECARGO` (R14); cuerpos iguales (R19); lista y
  orden de `SUB_PASOS` (R20); `publicadas(INVENTARIO_*, …)` = columnas del SQL que leen `dcf`/`dca`
  (R3); ni `empide` ni `hor` (R27); `dca` sigue excluyendo `pagfor`/`pagtex` (R28).
- `test_f128_diccionario.py`: fichas = columnas del SQL; frases obligatorias de R21-R25;
  relaciones; versión ≥ `git show main:config/diccionario/00_global.yaml` + 1 (si no hay `git` o
  `main`, `skip` con motivo); textos de `ARCHITECTURE.md` y `azure-apps` (R29).

## 10. Despliegue y verificación (MANUAL, humano, tras el review)

1. Imagen nueva del job (la nocturna lo construye todo; `run-all` ya incluye los dos pasos).
2. O a mano en Azure: `python main.py build-compras` y `python main.py build-retenciones`.
3. Comprobación del inventario: `SELECT column_name FROM information_schema.columns WHERE
   table_schema = 'raw' AND table_name IN ('dcf','dca')` contra las claves de `INVENTARIO_*`.
4. Las cifras de R30 con las consultas del informe; `python main.py check-diccionario`.
5. `python main.py publicar-diccionario` (escritura: la autoriza el humano) y reiniciar el MCP
   (cachea el diccionario); las dos preguntas de R31.

## 11. Riesgos y decisiones

- **Tabla ancha.** `facturas` pasa de 15 a 42 columnas y `albaranes` de 12 a 46. Alternativa
  descartada: una tabla aparte `factura_cabecera` (1:1): obliga a un `JOIN` para lo que Juan pide
  ver en la factura, y F-083/F-084/F-067 ya fijaron el patrón «al final».
- **`tot` frente a `totpag`.** Sigrid los documenta distintos; medido iguales en el 100 %. Se
  publica `totpag`; si un día difieren, R30 lo detecta (la identidad deja de cumplirse).
- **El cuadre por factura y no por efecto.** Por efecto no se puede: los AGR pierden la factura.
  Por factura el lado contable cuadra al 99,3 % y el de efectos al 84,2 % (sin el estado 14,
  al 33 %: incluirlo es lo que hace útil la columna, y la ficha explica por qué).
- **Obra del cuadre = obra de cabecera** (`dcf.obride`), no la cascada de F-095: coincide en el
  99,8 % de las facturas enlazadas y es la que Administración ve en la factura.
- **Orden en `run-all`**: `retenciones` va después de `compras` pero no lo necesita (§1).
- **Rendimiento**: dos agregados sobre ≤ 41.466 filas y joins por PK de `raw.con`; el lateral
  del estado no cambia. `retencion_factura` ≈ 27.000 filas.
- **Pendiente para F-130**: reutiliza `compras.factura_recargos`; F-091 (13,2 % entre debe y
  `totdoc`) no se toca, pero desde aquí `total_factura` es consultable.
