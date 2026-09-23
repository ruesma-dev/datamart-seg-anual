<!-- specs/F-102-obra-duplicada-empresa-28/design.md -->
# F-102 · Diseno tecnico

La definicion de "ficha principal" se escribe **una vez**, en una vista de `stg`
de la que salen `stg.obras`, las columnas nuevas de `maestro.obras` y la
traduccion que necesitan las vistas de consumo de `compras`. Asi la marca casa
con la deduplicacion de `stg.obras` por construccion.

## 1 · Lo medido (2026-09-23, solo lectura)

`raw` de la ingesta 2026-09-23 00:48 UTC en sesion `read_only`, salvo donde dice
Sigrid (`sigrid-api`) o MCP. Consultas en `progress/spec_F-102.md`.

### 1.1 Las fichas duplicadas

- **922 fichas, 846 codigos, 58 repetidos, 76 de mas** (Sigrid: 922/846). En una
  empresa el codigo es unico (empresa 1: 782/782; 28: 103/103): **la identidad
  es (`con.emp`, `con.cod`)**, el par de `04_centros_coste.sql`.
- `con.emp` = `auxemp.numemp` (Sigrid, 38 filas): **28 = PORSAN E HIJOS
  CONSTRUCCIONES SL**; 12, 14, 15, 25, 26, 27, 31 y 34 son UTE.
- Los 58: **42 empresa 1 + 28** (40 en el universo; POSTV2 y VAR fuera); 8
  empresa 1 + UTE; 8 mas fuera del universo (0001-0005, CM, CP, GG). En esos 10
  de fuera cada empresa usa el codigo para **obras distintas** (0001: «CALLE
  CONCORDIA Nº 4 (VALENCIA)» en la 11, «HOTEL BAHAMAS (IBIZA)» en la 18).
- Las 103 fichas de la 28: **0 con direccion, cliente, `conext` 15, presupuesto
  o cierres**. 57 son unica ficha (obras propias de Porsan 0006-0060 y 0676B).

### 1.2 La regla del humano (D1) y su impacto

Regla: **«la ficha principal es la de Construcciones Ruesma»**. Orden: empresa 1
-> `conext 15` -> `num_cierres` DESC -> `tiemod` DESC -> `ide` DESC. Hoy la
empresa 1 decide en 53 de los 58; los 5 sin ficha de la 1 (0001-0005, fuera del
universo) los decide el resto; ningun codigo tiene dos fichas de la 1.

`stg.obras` cambia en **4 codigos** respecto a hoy (580 de 584 iguales) y en 5
respecto a la opcion B que se descarto (0252, 0517, 0581, 0606, 0671):

| codigo | hoy en `stg.obras` | con la regla (empresa 1) | efecto en `mart` / `cierre` |
|---|---|---|---|
| 0720 | 2824201 (28): 0 cierres, 0 plan | 2759241: 2 cierres, 142 plan | **entra** (hoy falta) |
| 0581 | 1312365 (UTE 27): 20 cierres, 85.524 plan | 1287408: 0 cierres, 0 plan | **sale**: pierde 85.524 filas de `mart`, 76 de `cierre` |
| 0606 | 1581378 (UTE 31): 24 cierres, 279.817 plan | 1562946: 15 cierres, 1.097 plan | **se reduce**: hoy 71.249 filas de `mart` y 92 de `cierre`; queda lo que den 1.097 filas de plan |
| 0671 | 2163834 (UTE 34): 1 cierre, 0 plan | 2154295: 0 cierres, 0 plan | ninguno (hoy 0 en `mart` y `cierre`) |

**0252 y 0517 (empresa 1 + UTE) quedan como hoy**: principal la ficha de la 1,
sin cierres ni plan, y sus 7.564 y 72.737 filas de plan (fichas UTE 650280 y
1088657) siguen sin llegar a `mart`. **Riesgo que el humano debe aceptar
expresamente (T0)**: con la regla, 0581 y 0606 pasan a una ficha de la
empresa 1 con **menos datos** que la que se elige hoy.

### 1.3 Donde aparece el `obra_id` de una ficha NO principal (regla del humano)

(a) copia de la 28 en el universo, 40 fichas; (b) otra empresa en el universo, 8
fichas (las UTE); (c) fuera del universo, 28 fichas (no son copias). Filas:

| objeto | (a) | (b) | (c) |
|---|---|---|---|
| `compras.contratos` / `v_pbi_contrato_consumo` | 0 | 469 | 21 |
| `compras.albaran_lineas` | 0 | 37.646 | 958 |
| `compras.factura_lineas` | **3** | 39.223 | 3.468 |
| `compras.fact_compras_linea` | **3** (484,00 €) | 83.375 | 4.520 |
| `compras.v_pbi_proveedor_obra` | 3 | 936 | 545 |
| `compras.v_pbi_albaranes_sin_facturar` | 0 | 2.730 | 112 |
| `compras.v_pbi_partida_coste` | 0 | 3.535 | 0 |
| `compras.v_control_forma_pago` | 0 | 1.672 | 101 |
| `retenciones.movimientos` / `v_pbi_retencion_obra` | 0 / 0 | 516 / 5 | 21 / 3 |
| `maestro.proveedores_obra` / `centros_coste` | 0 / 40 | 331 / 8 | 17 / 28 |
| `personal.partes_lineas` | **14.079** (1.677.332,46 €) | 6.316 | 1.624 |

En euros, (b) de `fact_compras_linea` FACTURA+ABONO: **31.171.472,60 €** en 8
fichas UTE. Sin ficha de obra que pueda ser copia (no publican obra, medido en
`information_schema`): `compras.facturas`, `albaranes`, `contrato_lineas`,
`vencimientos`, `v_facturas_pago`, `formas_pago`, `documento_texto`,
`documento_comentarios`. `mart` y `cierre` leen `stg.obras`: tras el cambio solo
tienen principales **por construccion**. La 0704 Siroco: ficha 2652878 (28), 531
lineas de parte (2.563 h, 57.667,50 €). **Filtrar por `codigo_obra`** en
`compras`/`retenciones` ya suma todas las fichas (el codigo de la copia es el
mismo); ningun SQL une por codigo sin empresa.

### 1.4 Direccion sobre las principales, y `condir`

`dir1` en **310 de 846** (36,6 %): < 0400, 77/252; 0400-0599, 93/200;
0600-0671, 61/74; **0672+, 49/59**; cinco o mas digitos, 29/240; otros, 1/21.
Juan reproducido: cuatro digitos `>= '0672'`, **57 principales, todas de la 1, 48
con `dir1`** (sin ella 0673, 0684, 0689, 0701, 0703, 0714, 0716, 0717, 0725); en
curso, 40 / 34; a la 0715 le faltan CP y municipio. La direccion escasea en las
obras **antiguas**. `condir` ya se ingiere (803 filas, 722 de proveedores) y **0
de 922 fichas de obra** tienen fila (en Sigrid tambien 0).

## 2 · Ficheros a crear

`tests/test_f102_obra_principal.py`: los `test_f102_rN_*`, offline (§6).

## 3 · Ficheros a modificar

- `sql/stg/03_obras.sql` — antes del `TRUNCATE`, `CREATE OR REPLACE VIEW
  stg.v_obra_fichas` (§5); el `INSERT` lee de ella. Cabecera: la regla del
  humano con fecha, §1.2 y «58 codigos» (hoy dice 53).
- `sql/maestro/01_obras.sql` — cinco columnas al final, `LEFT JOIN
  stg.v_obra_fichas`, lateral a `raw.auxemp`; cabecera, ejemplos y `COMMENT ON
  VIEW` sin «un tercio» y **sin las frases que veta `test_f073_r11`**.
- `sql/compras/03_views.sql` — `obra_principal_id` al final de
  `v_pbi_contrato_consumo`, `v_pbi_proveedor_obra`, `v_pbi_albaranes_sin_facturar`
  y `v_pbi_partida_coste` (§5).
- `sql/compras/06_pago_factura.sql` — lo mismo en `v_control_forma_pago` (ahi ya
  hay `DROP VIEW ... CASCADE`; la columna va al final igualmente).
- `config/diccionario/compras.yaml` — en las cinco vistas: columna
  `obra_principal_id` y relacion `obra_principal_id -> maestro.obras.obra_id`
  (N:1). En `contratos`, `albaran_lineas`, `factura_lineas` y
  `fact_compras_linea`: la ficha de `obra_id` y el `porque` de su relacion dicen
  que puede ser una ficha no principal (cifras de §1.3) y como traducir:
  `JOIN maestro.obras mo USING (obra_id)` -> `mo.obra_principal_id`.
- `config/diccionario/retenciones.yaml` (`movimientos`, `v_pbi_retencion_obra`) y
  `maestro.yaml` (`proveedores_obra`, `centros_coste`) — mismo texto de
  traduccion en `obra_id` y en el `porque`, con sus cifras. Sin SQL.
- `config/diccionario/maestro.yaml` — ficha `obras` (cinco columnas, §1.4,
  `condir`) y punto 1 del comentario de cabecera.
- `config/diccionario/stg.yaml` — ficha `v_obra_fichas` (vista, `preparacion`,
  no recomendada, `clave_negocio: [obra_id]`, `build_stg`); en `obras`, la regla.
- `config/diccionario/00_global.yaml` — `R-OBRA-FICHA-PRINCIPAL`, `R-UNIVERSO-OBRA`,
  68 -> 69 en `R-SIGRID-CON`, `version` +1 con su parrafo en la cabecera.
- `config/tables_sigrid.yaml` — `auxemp` (`incremental_column: null`, sin
  filtro ni exclusiones). `raw.yaml`: su ficha y 68 -> 69.
- `tests/test_f066_ingesta_raw.py`, `test_f074_*`, `test_f080_*`: `TOTAL_TABLAS` +1.
- `tests/test_f073_sql.py` — `test_f073_r26` («`rn = 1`») pasa a exigir el
  desempate en `stg.v_obra_fichas` (lo cambia F-102 por D1).
- `docs/ARCHITECTURE.md` — bullet en «Semantica Sigrid» (obra en varias
  empresas, identidad (`emp`, `cod`), principal = empresa 1) y 68 -> 69 tablas.
- `azure-apps/datamart_seg_anual.md` — columnas nuevas de `maestro.obras` y de
  las vistas de `compras`, la regla, y 0720/0581/0606/0671 en `mart`/`cierre`.
  Commit propio en `azure-apps`.

## 4 · Ficheros que NO se tocan

- **`sql/personal/`, `personal.yaml`, `build_personal_step.py`** (F-101 en curso):
  su repaso (14.079 lineas de copias de la 28) se hace **despues de F-101**.
- Tablas de `compras` (`01_documentos.sql`, `02_fact_linea.sql`, `05_*`, `07_*`)
  y SQL de `retenciones` y `maestro/03_*`, `04_*`: el `obra_id` es el de Sigrid y
  no se reescribe (D2 A). Tampoco ganan columna: se consultan por SQL y el
  diccionario da la traduccion.
- `build_compras_step.py`: **no** gana `depends_on build_stg` (ver §7).
- `stg/06_*`, `08_*` (sello de F-025), `stg/01_ddl.sql`, `sql/mart/*`,
  `sql/cierre/*`: leen `stg.obras` y recogen el cambio solos.
- El proyecto `facturas` (esquema `fase1`, repositorio aparte e independiente:
  D4), `azure-apps/facturas.md` y `mcp-bbdd`.

## 5 · SQL

```
CREATE OR REPLACE VIEW stg.v_obra_fichas AS            -- stg/03_obras.sql
WITH base AS (
  SELECT o.ide AS obra_id, c.cod AS codigo_obra, c.emp AS empresa_id, c.tiemod,
         EXISTS (SELECT 1 FROM raw.conext x
                 WHERE x.conide = o.ide AND x.cod = '15')          AS marcada_vigente,
         (SELECT count(*) FROM raw.obrfas f WHERE f.obride = o.ide) AS num_cierres,
         (c.cod NOT IN (<lista de hoy, sin cambios>) AND c.cod !~ '[0-9]{5,}'
          AND c.cod IS NOT NULL AND length(trim(c.cod)) > 0)     AS en_universo_seguimiento
  FROM raw.obr o JOIN raw.con c ON c.ide = o.ide),
r AS (
  SELECT b.*, count(*) OVER (PARTITION BY codigo_obra) AS num_fichas_codigo,
         ROW_NUMBER() OVER w AS rango_ficha, first_value(obra_id) OVER w AS principal
  FROM base b
  WINDOW w AS (PARTITION BY codigo_obra ORDER BY
     CASE WHEN empresa_id = 1 THEN 0 ELSE 1 END,          -- regla del humano
     CASE WHEN marcada_vigente THEN 0 ELSE 1 END, num_cierres DESC,
     tiemod DESC NULLS LAST, obra_id DESC
     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING))
SELECT obra_id, codigo_obra, empresa_id, marcada_vigente, num_cierres::int,
       en_universo_seguimiento, num_fichas_codigo::int, rango_ficha::int,
       (rango_ficha = 1) AS es_ficha_principal,
       CASE WHEN en_universo_seguimiento THEN principal ELSE obra_id END
                                                         AS obra_principal_id
FROM r;

INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa)
SELECT vf.obra_id, vf.codigo_obra, c.res, TRUE
FROM stg.v_obra_fichas vf JOIN raw.con c ON c.ide = vf.obra_id
WHERE vf.en_universo_seguimiento AND vf.es_ficha_principal;
```

Los filtros dependen **solo del codigo**: todas las fichas de un codigo estan
dentro o fuera a la vez, y particionar todas da la misma particion que
particionar las filtradas.

`maestro/01_obras.sql`, detras de `tiene_seguimiento`: `vf.empresa_id,
em.nombre_empresa, vf.es_ficha_principal, vf.num_fichas_codigo,
vf.obra_principal_id`, con `LEFT JOIN stg.v_obra_fichas vf ON vf.obra_id = c.ide`
y `LEFT JOIN LATERAL (SELECT ae.res AS nombre_empresa FROM raw.auxemp ae WHERE
ae.numemp = c.emp ORDER BY ae.ide LIMIT 1) em ON TRUE`.

Vistas de `compras`: `COALESCE(vf.obra_principal_id, x.obra_id) AS
obra_principal_id` al final, con `LEFT JOIN stg.v_obra_fichas vf ON vf.obra_id =
x.obra_id`. En `v_pbi_proveedor_obra` el join va **fuera** del `GROUP BY`
(subconsulta agregada y despues el join a 922 filas) para no tocar su coste. Si
el `obra_id` es NULL, la columna tambien.

## 6 · Tests (offline, `tests/test_f102_obra_principal.py`)

Patron de `test_f073_sql.py` (SQL sin comentarios `--`, YAML con el dominio del
diccionario). Un test por R salvo los MANUAL (R8, R13, R14, R31). No obvios: la
lista de administrativos aparece **una sola vez** en `sql/`; la ventana empieza
por `empresa_id = 1` y no contiene `MIN(`, `ide ASC` ni `obra_id ASC`; las tablas
de `compras` y los SQL de `retenciones`/`personal` no nombran `v_obra_fichas`;
`version` > 27 (la de `main` al escribir la spec).

## 7 · Riesgos y decisiones de diseno

- **Cambia lo publicado en `mart` y `cierre`** (§1.2): entra 0720, **sale 0581,
  se reduce 0606**. La 0720 cambia de `obra_id` en `mart.v_pbi_dim_obra`
  (2824201 -> 2759241): Power BI relaciona por `obra_id`.
- **Power BI y `compras`**: con la regla, los hechos de las 8 fichas UTE (31,2 M€
  facturados) dejan de casar con `mart.v_pbi_dim_obra` por `obra_id`. Por eso
  las cinco vistas de consumo ganan `obra_principal_id` (la relacion que Power
  BI debe usar): es el caso «cuando sea necesario». Las tablas se consultan por
  SQL y el diccionario basta.
- **`compras` lee una vista de `stg` sin declarar la dependencia**: mismo patron
  que `retenciones` -> `maestro.centros_coste` (F-094). `build_stg` va antes en
  la lista y la vista nunca se dropea; declararlo haria que un fallo de `stg`
  dejara sin `compras` esa noche.
- **Dependencias de vistas**: `maestro.obras` y cinco vistas de `compras` cuelgan
  de `stg.v_obra_fichas`; sus columnas nuevas, solo al final.
- **Fusion**: F-101 toca `version` de `00_global.yaml` y otra seccion del
  documento de `azure-apps`; F-095 sube `TOTAL_TABLAS`. Se suman, no se pisan.
- **Descartado**: «`obra_id` menor» (**falla en la 0680**: la copia de la 28,
  2278106, tiene el `ide` menor que la buena, 2278832); un ranking propio en
  `maestro`; filtrar `maestro.obras` a principales (pierde el grupo b); reescribir
  el `obra_id` de los hechos (D2).

## 8 · Decisiones del humano (2026-09-23)

- **D1**: la principal es la de la empresa 1, delante de `conext` y cierres; el
  resto del ranking desempata. **Pendiente**: que acepte el riesgo de §1.2 (0581
  sale de `mart`/`cierre`, 0606 se reduce) o que pida separar la eleccion de
  `stg.obras` de la marca de `maestro` (romperia «la marca casa con `stg.obras`»).
- **D2 (A)**: no se reescribe ningun `obra_id`; se traduce con `obra_principal_id`.
- **D3**: se ingiere `auxemp`.
- **D4**: `facturas` es independiente; no hay aviso. Entra en su lugar el
  repaso de `compras` y de toda ficha con relacion a `maestro.obras.obra_id`
  (§1.3, §3). Fichas con esa relacion: `compras` (6), `retenciones` (2),
  `maestro` (2), `cierre` (2), `mart` (3), `personal` (2, tras F-101) y
  `stg.obras`; `mart`, `cierre` y `stg.obras` no pueden tener copias tras el
  cambio y no se tocan.

## 9 · Limite del microservicio

Todo vive en el ETL; una tabla mas por `sigrid-api` y nada a nivel de servidor.
**Fuera de alcance**: las 55 obras propias de Porsan (0006-0060) entran en
`stg.obras` sin presupuesto ni seguimiento (MCP, 2026-09-23).
