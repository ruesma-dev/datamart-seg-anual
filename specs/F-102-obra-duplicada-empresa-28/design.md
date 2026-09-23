<!-- specs/F-102-obra-duplicada-empresa-28/design.md -->
# F-102 · Diseno tecnico

La definicion de "ficha principal" se escribe **una vez**, en una vista de `stg`
de la que salen `stg.obras`, las columnas nuevas de `maestro.obras` y la
traduccion que necesitan las vistas de consumo de `compras`. Asi la marca casa
con la deduplicacion de `stg.obras` por construccion.

## 1 · Lo medido (2026-09-23, solo lectura)

`raw` de las 00:48 UTC en sesion `read_only`, salvo Sigrid o MCP (`progress/spec_F-102.md`).

### 1.1 Las fichas duplicadas

- **922 fichas, 846 codigos, 58 repetidos, 76 de mas** (Sigrid: 922/846). En una
  empresa el codigo es unico (empresa 1: 782/782; 28: 103/103): **la identidad
  es (`con.emp`, `con.cod`)**, el par de `04_centros_coste.sql`.
- `con.emp` = `auxemp.numemp` (Sigrid, 38 filas): **28 = PORSAN E HIJOS
  CONSTRUCCIONES SL**; 12, 14, 15, 25, 26, 27, 31 y 34 son UTE.
- Los 58: **42 empresa 1 + 28** (40 en el universo; POSTV2, VAR fuera); 8
  empresa 1 + UTE; 8 fuera (0001-0005, CM, CP, GG). En los 10 de fuera son
  **obras distintas** (0001: CALLE CONCORDIA en la 11, HOTEL BAHAMAS en la 18).
- Las 103 fichas de la 28: **0 con direccion, cliente, `conext` 15, presupuesto
  o cierres**. 57 son unica ficha (obras propias de Porsan 0006-0060 y 0676B).

### 1.2 La regla del humano (D1) y su impacto

**«La ficha principal es la de Construcciones Ruesma»**: empresa 1 -> `conext
15` -> `num_cierres` DESC -> `tiemod` DESC -> `ide` DESC. La 1 decide 53 de los
58; los 5 sin ficha de la 1 (0001-0005, fuera) los decide el resto; ninguno
tiene dos de la 1. `stg.obras` cambia en **4 codigos** frente a hoy (580 de 584
iguales) y en 5 frente a la opcion B descartada (0252, 0517, 0581, 0606, 0671):

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

(b) en FACTURA+ABONO: **31.171.472,60 €**. Sin columna de obra, luego sin copias
posibles (`information_schema`): `compras.facturas`, `albaranes`,
`contrato_lineas`, `vencimientos`, `v_facturas_pago`, `formas_pago`,
`documento_texto`, `documento_comentarios`. `mart`/`cierre`: principales **por
construccion**. 0704 Siroco: ficha 2652878, 531 lineas (2.563 h, 57.667,50 €).

### 1.4 Direccion sobre las principales, y `condir`

`dir1` en **310 de 846** (36,6 %): < 0400, 77/252; 0400-0599, 93/200;
0600-0671, 61/74; **0672+, 49/59**; cinco o mas digitos, 29/240; otros, 1/21.
Juan reproducido: cuatro digitos `>= '0672'`, **57 principales, todas de la 1, 48
con `dir1`** (sin ella 0673, 0684, 0689, 0701, 0703, 0714, 0716, 0717, 0725); en
curso, 40 / 34; a la 0715 le faltan CP y municipio. La direccion escasea en las
obras **antiguas**. `condir` ya se ingiere (803 filas, 722 de proveedores) y **0
de 922 fichas de obra** tienen fila (en Sigrid tambien 0).

### 1.5 `personal.recursos`: mismo problema (correo de Juan, 23-09)

`codigo_recurso` es `con.cod` del recurso: 2.618 recursos, 2.504 codigos, **61
repetidos globalmente, 0 dentro de una empresa** (2.618 pares (`emp`, `cod`)).
Por empresa: 1 -> 2.499; 12 -> 9; 14 -> 3; 18 -> 35; 25 -> 4; 27 -> 20; 28 -> 41;
31 -> 7. `MO/0009`: 537315 (1, NIETO ROMERO), 1404513 (27), 1991024 (18, que en
la 1 es otra ficha y otro codigo) y 2146405 (28). Personas (`cla = 1`) fuera de
la 1: 91; 60 con NIF; **13 comparten NIF** con una de la 1 (12 con una sola, 1
ambigua) y ninguna con el mismo codigo; 20 por nombre normalizado; 22 por
cualquiera; 0 por empleado (`conide`). Lineas de parte de recursos de fuera de
la 1: **26.426 y 3.226.523,83 €** (28: 17.652 y 2.082.681,46 €).

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
- `config/diccionario/compras.yaml` — cinco vistas: columna y relacion
  `obra_principal_id -> maestro.obras.obra_id` (N:1). `contratos`,
  `albaran_lineas`, `factura_lineas`, `fact_compras_linea`: `obra_id` y el
  `porque` dicen que puede ser no principal (§1.3) y como traducir
  (`JOIN maestro.obras USING (obra_id)` -> `obra_principal_id`).
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
- **Tras fusionar F-101 en `main`** (toca los mismos ficheros):
  `personal/00_setup.sql` (`ALTER TABLE personal.recursos ADD COLUMN IF NOT
  EXISTS empresa_id, nombre_empresa`; nunca `DROP`), `01_recursos.sql` (`c.emp`
  y lateral a `raw.auxemp`; lista blanca de `raw.emp` intacta) y `personal.yaml`
  (clave legible (`empresa_id`, `codigo_recurso`), §1.5, `MO/0009`).
- `azure-apps/datamart_seg_anual.md` — columnas nuevas de `maestro.obras`, de
  las vistas de `compras` y de `personal.recursos`, la regla, y 0720/0581/0606/0671
  en `mart`/`cierre`. Commit propio en `azure-apps`.

## 4 · Ficheros que NO se tocan

- **Nada de `personal` antes de que F-101 este en `main`**; despues, solo lo de
  `recursos` (§3). `02_partes_lineas.sql` no se toca: sus 14.079 lineas de
  copias de la 28 se traducen al leer (regla y D2).
- Tablas de `compras` (`01_*`, `02_*`, `05_*`, `07_*`), SQL de `retenciones`,
  `maestro/03_*`, `04_*` y `build_compras_step.py` (sin `depends_on build_stg`,
  §7): el `obra_id` es el de Sigrid y no se reescribe ni se duplica (D2 A).
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

Los filtros dependen **solo del codigo**: particionar todas las fichas da la
misma particion que particionar las filtradas.

`maestro/01_obras.sql`, tras `tiene_seguimiento`: las cinco de `vf` (`LEFT JOIN
stg.v_obra_fichas vf ON vf.obra_id = c.ide`) y `em.nombre_empresa` de `LEFT JOIN
LATERAL (SELECT ae.res ... FROM raw.auxemp ae WHERE ae.numemp = c.emp ORDER BY
ae.ide LIMIT 1) em ON TRUE`. El mismo lateral en `personal/01_recursos.sql`.

Vistas de `compras`: `COALESCE(vf.obra_principal_id, x.obra_id) AS
obra_principal_id` al final (`LEFT JOIN stg.v_obra_fichas vf ON vf.obra_id =
x.obra_id`; NULL si `obra_id` es NULL). En `v_pbi_proveedor_obra`, sobre el agregado.

## 6 · Tests (offline, `tests/test_f102_obra_principal.py`)

Patron de `test_f073_sql.py` (SQL sin comentarios `--`, YAML con el dominio del
diccionario). Un test por R salvo los MANUAL (R8, R13, R14, R33). No obvios: la
lista de administrativos aparece **una sola vez** en `sql/`; la ventana empieza
por `empresa_id = 1` y no contiene `MIN(`, `ide ASC` ni `obra_id ASC`; las tablas
de `compras` y los SQL de `retenciones`/`personal` no nombran `v_obra_fichas`;
`version` > 27 (la de `main` al escribir la spec).

## 7 · Riesgos y decisiones de diseno

- **Cambia lo publicado en `mart` y `cierre`** (§1.2): entra 0720, **sale 0581,
  se reduce 0606**. La 0720 cambia de `obra_id` en `mart.v_pbi_dim_obra`
  (2824201 -> 2759241): Power BI relaciona por `obra_id`.
- **Power BI y `compras`**: los hechos de las 8 fichas UTE (31,2 M€) dejan de
  casar con `mart.v_pbi_dim_obra` por `obra_id`; por eso las cinco vistas de
  consumo ganan `obra_principal_id` («cuando sea necesario»). Las tablas se
  consultan por SQL y les basta el diccionario.
- **`compras` lee `stg.v_obra_fichas` sin declarar la dependencia**, como
  `retenciones` -> `maestro.centros_coste` (F-094): `build_stg` va antes y la
  vista no se dropea; declararla dejaria sin `compras` la noche que falle `stg`.
  Columnas nuevas de la vista, solo al final (cuelgan de ella 6 vistas).
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
- **D3**: se ingiere `auxemp` (sirve tambien a `personal.recursos`).
- **D5 (abierta) · marca de «misma persona en otra empresa»** en
  `personal.recursos`. (A, **recomendada**) no publicarla: solo 13 de 91 se
  unen por un campo exacto (NIF), 31 no tienen NIF y el nombre es heuristica.
  (B) `recurso_empresa1_id` por NIF exacto cuando casa con una sola ficha de la
  1 (12 hoy). (C) NIF o nombre (22): descartada, adivina.
- **D4**: `facturas` es independiente, sin aviso. En su lugar, repaso de toda
  ficha con relacion a `maestro.obras.obra_id`: `compras` (6), `retenciones` (2),
  `maestro` (2), `personal` (2, tras F-101); `mart` (3), `cierre` (2) y
  `stg.obras` no pueden tener copias tras el cambio y no se tocan.

## 9 · Limite del microservicio

Todo en el ETL; una tabla mas por `sigrid-api`. **Fuera de alcance**: las 55
obras propias de Porsan (0006-0060) estan en `stg.obras` sin presupuesto (MCP).
