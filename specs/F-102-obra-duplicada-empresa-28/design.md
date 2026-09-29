<!-- specs/F-102-obra-duplicada-empresa-28/design.md -->
# F-102 · Diseno tecnico

**Modelo del humano (2026-09-23)**: «las obras son por empresa. La UTE es una
cosa y Ruesma otra [...] no estamos consolidando. El codigo igual representa que
es la misma obra, pero desde la perspectiva de diferentes empresas. Lo mismo con
Porsan». Por eso este hotfix solo publica **identificadores** para que nada
salga duplicado por codigo: `obra_id` sigue siendo la clave tecnica, y se anade
la clave legible (empresa + codigo), y en `maestro` la marca de la ficha de
Ruesma como referencia.
**`stg.obras` no cambia**: pasar el seguimiento a «solo Ruesma» y traer las
demas empresas es F-106.

## 1 · Lo medido (2026-09-23, solo lectura)

`raw` de las 00:48 UTC en sesion `read_only`, salvo Sigrid o MCP (`progress/spec_F-102.md`).

### 1.1 Las fichas duplicadas

- **922 fichas, 846 codigos, 58 repetidos, 76 de mas** (Sigrid: 922/846). En una
  empresa el codigo es unico (empresa 1: 782/782; 28: 103/103).
- `con.emp` = `auxemp.numemp` (Sigrid, 38 filas): **28 = PORSAN E HIJOS
  CONSTRUCCIONES SL**; 12, 14, 15, 25, 26, 27, 31 y 34 son UTE.
- Los 58: **42 empresa 1 + 28**; 8 empresa 1 + UTE; 8 sin la 1 o administrativos
  (0001-0005, CM, CP, GG), donde las fichas de distintas empresas son cosas
  distintas (0001: CALLE CONCORDIA en la 11, HOTEL BAHAMAS en la 18).
- Las 103 fichas de la 28: **0 con direccion, cliente, `conext` 15, presupuesto
  o cierres**. 57 son unica ficha (obras propias de Porsan 0006-0060 y 0676B).

### 1.2 Las claves legibles son unicas

`clave_obra` = `empresa_id || '-' || codigo_obra`: **922 claves para 922
fichas**, 0 codigos vacios, 0 empresas a 0. `clave_recurso`: **2.618 para
2.618**, idem. El formato no puede colisionar: `empresa_id` es entero, asi que
todo lo anterior al primer `-` es la empresa y la clave se descompone sin
ambiguedad; es unica si y solo si lo es el par (empresa, codigo).

### 1.3 La ficha de Ruesma (`es_ficha_principal`, `obra_principal_id`)

Orden: **empresa 1** -> `conext 15` -> `num_cierres` DESC -> `tiemod` DESC ->
`ide` DESC. 846 principales para 846 codigos; 64 son de otra empresa (codigos que
solo existen fuera de la 1, entre ellos las 57 de Porsan y 0001-0005, decididos
por el resto del ranking). `obra_principal_id` = la ficha de la 1 del codigo, o
la propia: **59 fichas** apuntan a otra. De ellas, 11 son de codigos
administrativos (CM 1, CP 4, GG 4, POSTV2 1, VAR 1) cuya ficha en otra empresa
es su propio centro de gastos: la ficha del diccionario lo advierte.

### 1.4 Donde la marca difiere de `stg.obras`, y por que `stg.obras` no cambia

| codigo | `stg.obras` (hoy, se queda) | ficha de Ruesma (`es_ficha_principal`) |
|---|---|---|
| 0720 | 2824201 (28): 0 cierres, 0 plan | 2759241: 2 cierres, 142 filas de plan |
| 0581 | 1312365 (UTE 27): 20 cierres, 85.524 plan y `mart`, 76 `cierre` | 1287408: 0 cierres, 0 plan |
| 0606 | 1581378 (UTE 31): 24 cierres, 279.817 plan, 71.249 `mart`, 92 `cierre` | 1562946: 15 cierres, 1.097 plan |
| 0671 | 2163834 (UTE 34): 1 cierre | 2154295: 0 cierres |

Aplicar la marca a `stg.obras` sacaria 0581 de `mart`/`cierre` y reduciria 0606;
por decision del humano no se toca y **F-106** lo resuelve. 0252 y 0517 coinciden
(`stg.obras` ya elige la ficha de la 1, sin cierres; sus datos estan en la UTE).

### 1.5 Donde aparece el `obra_id` de una ficha que no es la de Ruesma

Filas por objeto: (a) copia de la 28 dentro del universo del seguimiento (40
fichas); (b) otra empresa dentro del universo (8, las UTE); (c) fuera (28).

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

Lineas de fichas **no Ruesma** en `fact_compras_linea`: 91.431 (54.198.506,59 €
de FACTURA+ABONO); de ellas, **84.233 (31.770.036,29 €)** con un codigo que
tambien tiene ficha de Ruesma, que son las que se mezclarian agregando por
`codigo_obra`. En `v_pbi_proveedor_obra`: 1.880 filas no Ruesma, 1.066 con
codigo compartido. 9.363 lineas sin obra. Sin columna de obra, luego sin el problema
(`information_schema`): `compras.facturas`, `albaranes`, `contrato_lineas`,
`vencimientos`, `v_facturas_pago`, `formas_pago`, `documento_texto`,
`documento_comentarios`. `mart` y `cierre` heredan la eleccion de `stg.obras`.
0704 Siroco: ficha 2652878 (28), 531 lineas de parte (2.563 h, 57.667,50 €).

### 1.6 Direccion sobre las principales, y `condir`

`dir1` en **310 de 846** (36,6 %): < 0400, 77/252; 0400-0599, 93/200;
0600-0671, 61/74; **0672+, 49/59**; cinco o mas digitos, 29/240; otros, 1/21.
Juan reproducido: cuatro digitos `>= '0672'`, **57 principales, todas de la 1, 48
con `dir1`** (faltan 0673, 0684, 0689, 0701, 0703, 0714, 0716, 0717, 0725); en
curso, 40 / 34; la 0715 sin CP ni municipio. La direccion escasea en las obras
**antiguas**. `condir` ya se ingiere y **0 de 922 fichas de obra** tienen fila
(Sigrid: 0).

### 1.7 `personal.recursos` (correo de Juan, 23-09)

2.618 recursos, 2.504 codigos, **61 repetidos, 0 dentro de una empresa**. Por
empresa: 1 -> 2.499; 12 -> 9; 14 -> 3; 18 -> 35; 25 -> 4; 27 -> 20; 28 -> 41;
31 -> 7. `MO/0009`: 537315 (1), 1404513 (27), 1991024 (18), 2146405 (28). De 91
personas fuera de la 1, 13 comparten NIF con una de la 1 (D5: sin marca). Partes
de recursos de fuera de la 1: 26.426 lineas, 3.226.523,83 €.

## 2 · Ficheros a crear

`tests/test_f102_obra_principal.py`: los `test_f102_rN_*`, offline (§6).

## 3 · Ficheros a modificar

- `sql/maestro/01_obras.sql` — antes de `maestro.obras`, `CREATE OR REPLACE VIEW
  maestro.v_obra_fichas` (§5); `maestro.obras` gana al final las seis columnas
  (`LEFT JOIN` a la vista, lateral a `raw.auxemp`). Cabecera, ejemplos y
  `COMMENT ON VIEW`: el modelo, sin «un tercio» y **sin las frases que veta
  `test_f073_r11`**.
- `sql/compras/03_views.sql` (cuatro vistas) y `06_pago_factura.sql`
  (`v_control_forma_pago`) — `empresa_id` y `clave_obra` al final (§5).
- `config/tables_sigrid.yaml` — `auxemp` (`incremental_column: null`, sin filtro
  ni exclusiones). `raw.yaml`: su ficha y 68 -> 69.
- `tests/test_f066_ingesta_raw.py`, `test_f074_*`, `test_f080_*`: `TOTAL_TABLAS` +1.
- `config/diccionario/maestro.yaml` — fichas `obras` (seis columnas, §1.3,
  §1.6, modelo) y `v_obra_fichas` (vista, `consumo`, no recomendada,
  `clave_negocio: [obra_id]`, `build_maestros`); en `proveedores_obra` y
  `centros_coste`, el texto de R23. Punto 1 del comentario de cabecera.
- `config/diccionario/compras.yaml` — cinco vistas: las dos columnas, relacion
  `clave_obra -> maestro.obras.clave_obra` (N:1) y el aviso de R22; cuatro
  tablas: texto de R23 con §1.5.
- `config/diccionario/retenciones.yaml` — texto de R23 en sus dos fichas.
- `config/diccionario/stg.yaml` — ficha `obras`: sigue como hoy, §1.4, F-106.
- `config/diccionario/00_global.yaml` — `R-CODIGO-POR-EMPRESA`, `R-UNIVERSO-OBRA`
  (§1.4), 68 -> 69 en `R-SIGRID-CON`, `version` +1 con su parrafo de cabecera.
- `docs/ARCHITECTURE.md` — bullet en «Semantica Sigrid»: obras y recursos por
  empresa, claves legibles, ficha de Ruesma, F-106; 68 -> 69 tablas.
- `azure-apps/datamart_seg_anual.md` — columnas nuevas y la regla; commit propio.
- **Tras fusionar F-101 en `main`** (toca los mismos ficheros):
  `personal/00_setup.sql` (`ALTER TABLE personal.recursos ADD COLUMN IF NOT
  EXISTS` x3; nunca `DROP`), `01_recursos.sql` (`c.emp`, la clave y el lateral a
  `raw.auxemp`; lista blanca de `raw.emp` intacta) y `personal.yaml` (§1.7).

## 4 · Ficheros que NO se tocan

- **`sql/stg/03_obras.sql`** y todo `stg`: la eleccion de `stg.obras` se queda
  (§1.4); `test_f073_r26` intacto. Tampoco `mart`, `cierre` ni el sello de F-025.
- Tablas de `compras` (`01_*`, `02_*`, `05_*`, `07_*`), SQL de `retenciones`,
  `maestro/03_*`, `04_*` y ningun `depends_on` de los steps (§7).
- `personal` antes de F-101; `02_partes_lineas.sql` ni despues (se traduce al leer).
- El proyecto `facturas` (independiente, D4), `azure-apps/facturas.md`, `mcp-bbdd`.

## 5 · SQL (`maestro/01_obras.sql`)

```
CREATE OR REPLACE VIEW maestro.v_obra_fichas AS
WITH base AS (
  SELECT o.ide AS obra_id, c.cod AS codigo_obra, c.emp AS empresa_id, c.tiemod,
         c.emp::text || '-' || c.cod                                 AS clave_obra,
         EXISTS (SELECT 1 FROM raw.conext x
                 WHERE x.conide = o.ide AND x.cod = '15')          AS marcada_vigente,
         (SELECT count(*) FROM raw.obrfas f WHERE f.obride = o.ide) AS num_cierres
  FROM raw.obr o JOIN raw.con c ON c.ide = o.ide),
r AS (
  SELECT b.*, count(*) OVER (PARTITION BY codigo_obra) AS num_fichas_codigo,
         bool_or(empresa_id = 1) OVER (PARTITION BY codigo_obra) AS hay_ruesma,
         ROW_NUMBER() OVER w AS rango_ficha, first_value(obra_id) OVER w AS primera
  FROM base b
  WINDOW w AS (PARTITION BY codigo_obra ORDER BY
     CASE WHEN empresa_id = 1 THEN 0 ELSE 1 END,          -- Ruesma primero
     CASE WHEN marcada_vigente THEN 0 ELSE 1 END, num_cierres DESC,
     tiemod DESC NULLS LAST, obra_id DESC
     ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING))
SELECT obra_id, codigo_obra, empresa_id, clave_obra, marcada_vigente,
       num_cierres::int, num_fichas_codigo::int, rango_ficha::int,
       (rango_ficha = 1)                                  AS es_ficha_principal,
       CASE WHEN hay_ruesma THEN primera ELSE obra_id END AS obra_principal_id
FROM r;
```

`obra_principal_id` sale de la MISMA ventana que `es_ficha_principal`: con ficha
de la 1 en el codigo, es la principal (la de Ruesma); sin ella, la propia. Asi
las dos no pueden divergir aunque un dia haya dos fichas de la 1.

`maestro.obras`, tras `tiene_seguimiento`: `vf.empresa_id, em.nombre_empresa,
vf.clave_obra, vf.num_fichas_codigo, vf.es_ficha_principal,
vf.obra_principal_id`, con `LEFT JOIN maestro.v_obra_fichas vf ON vf.obra_id =
c.ide` y `LEFT JOIN LATERAL (SELECT ae.res AS nombre_empresa FROM raw.auxemp ae
WHERE ae.numemp = c.emp ORDER BY ae.ide LIMIT 1) em ON TRUE`. El mismo lateral y
`c.emp::text || '-' || c.cod AS clave_recurso` en `personal/01_recursos.sql`.

Vistas de `compras`: `vf.empresa_id, vf.clave_obra` al final (`LEFT JOIN
maestro.v_obra_fichas vf ON vf.obra_id = x.obra_id`); en `v_pbi_proveedor_obra`,
sobre el agregado. **Sin `obra_principal_id`**: cada factura queda con SU empresa.

## 6 · Tests (offline, `tests/test_f102_obra_principal.py`)

Patron de `test_f073_sql.py`. Un test por R salvo los MANUAL (R11, R12, R30).
No obvios: `stg/03_obras.sql` identico al de `main` por hash (R7); la ventana
empieza por `empresa_id = 1` y no ordena por `ide ASC`/`obra_id ASC` (R2); la
clave se construye con `'-'` y `empresa_id` delante (R6, R26); los SQL de R24 no
nombran `v_obra_fichas`; `version` > 27. La unicidad de las claves se prueba
ademas en la base: `clave_negocio` de las fichas y `check-unicidad` (R30).

## 7 · Riesgos y decisiones de diseno

- **La vista va en `maestro`, no en `stg`**: `stg.obras` no la usa (R7), y
  ponerla en `stg` sugeriria que el seguimiento la sigue. Lee solo `raw`, asi que
  `compras` no gana dependencia de `stg`; `build_maestros` corre antes que
  `build_compras` y la vista no se dropea (patron de `retenciones` ->
  `maestro.centros_coste`, F-094). Sus columnas nuevas, solo al final.
- **Lo que no casa hasta F-106**: en 0581, 0606, 0671 y 0720 la ficha de Ruesma
  no es la de `stg.obras` ni la de `mart.v_pbi_dim_obra`. `compras` no se ve
  afectado: publica la empresa y la clave de su propia ficha, no la de Ruesma.
- **`obra_principal_id` solo en `maestro.obras`**, como referencia: usarlo para
  agregar hechos sumaria facturas de la UTE en la obra de Ruesma, que el humano
  no consolida. La ficha del diccionario lo prohibe expresamente.
- **Codigos administrativos** (§1.3): 11 fichas apuntan a la de Ruesma sin ser la
  misma cosa; declarado en la ficha, no se corrige (son de gestion).
- **Fusion**: F-101 toca `version` de `00_global.yaml` y el documento de
  `azure-apps`; F-095 sube `TOTAL_TABLAS`. Se suman, no se pisan.
- **Descartado**: «`obra_id` menor» (falla en la 0680: la copia de la 28,
  2278106, tiene el `ide` menor que la buena, 2278832); filtrar `maestro.obras` a
  principales; reescribir el `obra_id` de los hechos (D2); cambiar `stg.obras`.

## 8 · Decisiones finales del humano (2026-09-23) · SPEC APROBADA

- **D1**: principal = ficha de la empresa 1; sin ella, el resto del ranking.
  Solo identificadores; `stg.obras` no cambia; el seguimiento «solo Ruesma» y
  las demas empresas son **F-106** (prioridad 3, la ficha el lider).
- **D2 (A)**: no se reescribe ningun `obra_id`. En `compras`, `empresa_id` y
  `clave_obra`, no `obra_principal_id` (decision final del humano).
- **D3**: se ingiere `auxemp` (obras y recursos).
- **D4**: `facturas` es independiente, sin aviso; en su lugar, repaso de toda
  ficha con relacion a `maestro.obras.obra_id`: `compras` (6), `retenciones` (2),
  `maestro` (2), `personal` (2, tras F-101); `mart` (3), `cierre` (2) y
  `stg.obras` heredan `stg.obras` y no se tocan.
- **D5 (A)**: sin marca de «misma persona en otra empresa».

## 9 · Limite del microservicio

Todo en el ETL; una tabla mas por `sigrid-api`. Fuera de alcance, en F-106:
seguimiento por empresa y las 55 obras de Porsan en `stg.obras` sin presupuesto.
