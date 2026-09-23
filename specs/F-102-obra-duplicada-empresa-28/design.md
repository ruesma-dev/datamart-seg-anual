<!-- specs/F-102-obra-duplicada-empresa-28/design.md -->
# F-102 · Diseno tecnico

Hotfix de `maestro` con una pieza en `stg`: la definicion de "ficha principal"
se escribe **una vez**, en una vista de `stg` que construye `stg.obras` y que
lee `maestro.obras`. Asi "la marca casa con la deduplicacion de `stg.obras`" es
cierto por construccion, no por dos copias que hoy coinciden.

## 1 · Lo medido (2026-09-23, solo lectura)

Origen: `raw` de la ingesta 2026-09-23 00:48 UTC, sesion `read_only`
(`sigrid_dm`), salvo donde dice Sigrid (`sigrid-api`) o MCP. Consultas en
`progress/spec_F-102.md`.

### 1.1 Las fichas duplicadas

- **922 fichas, 846 codigos, 58 repetidos, 76 fichas de mas** (Sigrid: 922/846).
  Dentro de una empresa el codigo es unico (empresa 1: 782/782; 28: 103/103):
  **la identidad es (`con.emp`, `con.cod`)**, el par de `04_centros_coste.sql`.
- `con.emp` = `auxemp.numemp` (Sigrid, 38 filas): **28 = PORSAN E HIJOS
  CONSTRUCCIONES SL**; 12, 14, 15, 25, 26, 27, 31 y 34 son UTE.
- Los 58: **42 empresa 1 + 28** (40 en el universo; POSTV2 y VAR fuera); 8
  empresa 1 + UTE; y 8 mas fuera del universo (0001-0005, CM, CP, GG). En esos
  10 de fuera cada empresa usa el codigo para **obras distintas** (0001: «CALLE
  CONCORDIA Nº 4 (VALENCIA)» en la 11, «HOTEL BAHAMAS (IBIZA)» en la 18).
- Las 103 fichas de la 28: **0 con direccion, cliente, `conext` 15, presupuesto
  o cierres**. 57 son unica ficha (obras propias de Porsan 0006-0060 y 0676B).

### 1.2 Que elige hoy `stg.obras`, y donde se equivoca

`stg/03_obras.sql` ordena `conext 15 -> tiemod DESC -> ide DESC`. Sin marca
decide `tiemod`, y en tres codigos elige **la ficha sin cierres**: `mart` y
`cierre` pierden la obra entera, porque su `JOIN stg.obras` descarta la buena:

| codigo | elige hoy | ficha con los datos | filas de `stg.plan_mensual` que no llegan a `mart` |
|---|---|---|---|
| 0720 | 2824201 (empresa 28) | 2759241 (empresa 1) | 142 |
| 0252 | 587639 (empresa 1) | 650280 (UTE, 12) | 7.564 |
| 0517 | 1060846 (empresa 1) | 1088657 (UTE, 25) | 72.737 |

MCP: las buenas, 0 filas hoy en `mart.v_pbi_dim_obra` y `cierre.v_pbi_cierre_cabecera`.

### 1.3 El ranking propuesto (R2) y que campo decide cada codigo

`conext 15 -> num_cierres DESC -> empresa 1 -> tiemod DESC -> ide DESC`. Sobre
los 58 repetidos decide: **conext 39**, **cierres 10** (0252, 0272, 0455, 0517,
0581, 0606, 0671, 0720, POSTV2, VAR), **empresa 1 en 4** (0309, CM, CP, GG) y
**tiemod solo en 0001-0005**, que estan fuera del universo. Ninguno del universo
llega a `tiemod` ni a `ide`. Resultado: `stg.obras` cambia en 0252, 0517 y 0720
y en nada mas (581 de 584 iguales).

Sin «cierres», «empresa 1» voltearia la 0606 (las dos marcadas; la UTE 31 con
24 cierres y 279.817 filas de plan, la 1 con 15 y 1.097) y dejaria mal 0252 y
0517. Sin «empresa 1», CM, CP y GG irian a otra empresa por `tiemod`.

### 1.4 Donde aparece el `obra_id` de una ficha NO principal

**(a)** copia de la 28 en el universo (40 fichas); **(b)** otra empresa en el
universo (8: pares con UTE); **(c)** fuera del universo (28, no son copias).

| objeto | (a) copia 28 | (b) otra empresa | (c) fuera |
|---|---|---|---|
| `personal.partes_lineas` | **14.079 lineas, 39 fichas, 1.677.332,46 €** | 2.475 / 6 / 1.899.575,80 € | 1.624 / 5 / 183.954,55 € |
| `compras.fact_compras_linea` (FACTURA+ABONO) | 3 lineas, 484,00 € | 1.572 / 8 / 8.686.666,99 € | 3.468 / 21 / 11.371.568,46 € |
| `compras.contratos` | 0 | 18 | 21 |
| `retenciones.movimientos` | 0 | 67 (27 cliente, 40 proveedor) | 21 |
| `maestro.proveedores_obra` | 0 | 13 | 17 |
| `maestro.centros_coste` | 40 | 8 | 28 |
| `stg.presupuesto` / `stg.plan_mensual` | 0 / 0 | 1.707 / 1.097 (0606 de la 1) | 1 / 0 |
| `mart.*`, `cierre.fact_cierre_mensual` | 0 | 0 | 0 |

La **0704 Siroco** que cita Juan: ficha 2652878 (28), 531 lineas, 519 de HORA
(2.563 h, 57.667,50 €) y 12 de DIA, 2 recursos, 2025-12-03 a 2026-09-18.
**Lo que no cambia**: en `compras` y `retenciones`, filtrar por `codigo_obra`
ya suma las dos fichas; por el `obra_id` de la principal se pierden las de la
copia. Ningun SQL del repositorio une por codigo sin empresa (el unico cruce por
codigo, `04_centros_coste.sql`, va por `emp` + `cod`).

### 1.5 Direccion sobre las fichas principales (ranking R2)

`dir1` en 312 de 846 principales (36,9 %). Por tramo de codigo: < 0400, 78 de
252; 0400-0599, 93 de 200; 0600-0671, 62 de 74; **0672+, 49 de 59**; cinco o mas
digitos, 29 de 240; otros, 1 de 21. Cifras de Juan reproducidas: cuatro digitos
`>= '0672'` en la empresa 1, **57 con 48 con `dir1`** (sin ella: 0673, 0684,
0689, 0701, 0703, 0714, 0716, 0717, 0725); en curso de la 1 con cuatro digitos,
**40 con 34** (faltan 0664, 0701, 0714, 0716, 0717, 0725) y a la 0715 le faltan
codigo postal y municipio. La direccion es escasa en las obras **antiguas**, no
en las recientes: el «un tercio» de la ficha mezclaba las dos cosas.

### 1.6 `condir` no aporta nada

Ya se ingiere (`tables_sigrid.yaml`, 803 filas, 740 entidades: 722 de `con.tip`
5, proveedores). **0 de las 922 fichas de obra** tienen fila; en Sigrid, `condir
JOIN obr` da 0. El unico puntero de obra a `condir` es `obr.entdiride`, la
direccion del **cliente** (2 fichas), vetada por F-073.

## 2 · Ficheros a crear

`tests/test_f102_obra_principal.py`: los `test_f102_rN_*`, offline (§6).

## 3 · Ficheros a modificar

- `etl_sigrid/infrastructure/postgres/sql/stg/03_obras.sql` — antes del
  `TRUNCATE`, `CREATE OR REPLACE VIEW stg.v_obra_fichas` (§5); el `INSERT` lee de
  ella. Cabecera: el ranking nuevo, las cifras de §1.2 y «58 codigos» (hoy dice 53).
- `etl_sigrid/infrastructure/postgres/sql/maestro/01_obras.sql` — cinco
  columnas al final, `LEFT JOIN stg.v_obra_fichas`, `LEFT JOIN LATERAL` a
  `raw.auxemp`; cabecera, ejemplos de consumo y `COMMENT ON VIEW` sin «un tercio»
  y **sin las frases que veta `test_f073_r11`** (ojo al redactar lo de la 28).
- `config/tables_sigrid.yaml` — `auxemp` (`incremental_column: null`, sin
  filtro ni exclusiones, comentario con §1.1). `raw.yaml`: ficha y 68 -> 69.
- `config/diccionario/maestro.yaml` — ficha `obras` (cinco columnas, §1.5,
  §1.6) y punto 1 del comentario de cabecera.
- `config/diccionario/stg.yaml` — ficha `v_obra_fichas` (vista, `preparacion`,
  no recomendada, `clave_negocio: [obra_id]`, `build_stg`); en `obras`, el desempate.
- `config/diccionario/00_global.yaml` — `R-OBRA-FICHA-PRINCIPAL`, `R-UNIVERSO-OBRA`,
  68 -> 69 en `R-SIGRID-CON`, `version` +1 con su parrafo en la cabecera.
- `tests/test_f066_ingesta_raw.py`, `test_f074_*`, `test_f080_*`: `TOTAL_TABLAS` +1.
- `tests/test_f073_sql.py` — `test_f073_r26` («`rn = 1`» en `03_obras.sql`) se
  reescribe: el desempate vive ahora en `stg.v_obra_fichas` y lo cambia F-102
  por decision del humano (D1). Se conserva la intencion: que exista y sea uno.
- `docs/ARCHITECTURE.md` — bullet en «Semantica Sigrid»: la obra puede estar en
  varias empresas, la identidad es (`emp`, `cod`) y la principal sale de
  `stg.v_obra_fichas`; «68 tablas» -> 69 en §«Que se copia de Sigrid».
- `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` — §«Que
  expone»: columnas nuevas de `maestro.obras`, la regla y el cambio de 0252, 0517
  y 0720 en `mart`/`cierre`. Commit propio en `azure-apps`.

## 4 · Ficheros que NO se tocan

- **`sql/personal/`, `personal.yaml`, `build_personal_step.py`**: F-101 esta en
  curso sobre ellos; la regla nueva cubre `personal.partes_lineas` desde
  `00_global.yaml`.
- `sql/compras/*`, `sql/retenciones/*`, `maestro/03_*` y `04_*`: su `obra_id` es
  el de Sigrid (D2). `stg/01_ddl.sql`: `stg.obras` no cambia de columnas.
- `stg/06_presupuesto.sql` y `08_plan_mensual.sql` (**sello** de F-025): ya
  construyen todas las fichas de `raw` (§1.2). `sql/mart/*`, `sql/cierre/*`:
  leen `stg.obras` y recogen el cambio solos.
- El repositorio `facturas`, `azure-apps/facturas.md` y
  `mcp-bbdd/config/diccionario_datos.yaml`: son de otros proyectos.

## 5 · SQL (capa `stg`, fichero `03_obras.sql`; capa `maestro`, `01_obras.sql`)

```
CREATE OR REPLACE VIEW stg.v_obra_fichas AS
WITH base AS (
  SELECT o.ide AS obra_id, c.cod AS codigo_obra, c.emp AS empresa_id, c.tiemod,
         EXISTS (SELECT 1 FROM raw.conext x
                 WHERE x.conide = o.ide AND x.cod = '15')        AS marcada_vigente,
         (SELECT count(*) FROM raw.obrfas f WHERE f.obride = o.ide) AS num_cierres,
         (c.cod NOT IN (<lista de hoy, sin cambios>) AND c.cod !~ '[0-9]{5,}'
          AND c.cod IS NOT NULL AND length(trim(c.cod)) > 0)   AS en_universo_seguimiento
  FROM raw.obr o JOIN raw.con c ON c.ide = o.ide),
r AS (
  SELECT b.*, count(*) OVER (PARTITION BY codigo_obra) AS num_fichas_codigo,
         ROW_NUMBER() OVER w AS rango_ficha, first_value(obra_id) OVER w AS principal
  FROM base b
  WINDOW w AS (PARTITION BY codigo_obra ORDER BY
     CASE WHEN marcada_vigente THEN 0 ELSE 1 END, num_cierres DESC,
     CASE WHEN empresa_id = 1 THEN 0 ELSE 1 END,
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

Equivalencia con lo de hoy: los filtros dependen **solo del codigo**, asi que
todas las fichas de un codigo estan dentro o fuera a la vez y particionar todas
las fichas da la misma particion que particionar las filtradas. `tiemod` del
`base` es `con.tiemod` (el de hoy). El recuento de `obrfas` es subconsulta
escalar sobre 922 filas: coste despreciable.

En `maestro/01_obras.sql`, detras de `tiene_seguimiento`:

```
    vf.empresa_id, em.nombre_empresa, vf.es_ficha_principal,
    vf.num_fichas_codigo, vf.obra_principal_id
...
LEFT JOIN stg.v_obra_fichas vf ON vf.obra_id = c.ide
LEFT JOIN LATERAL (SELECT ae.res AS nombre_empresa FROM raw.auxemp ae
                   WHERE ae.numemp = c.emp ORDER BY ae.ide LIMIT 1) em ON TRUE
```

Las marcas salen de `vf` (una sola definicion). `build_maestros` ya depende de
`build_stg` desde F-073, asi que la vista existe cuando se recrea `maestro`.

## 6 · Tests (offline, `tests/test_f102_obra_principal.py`)

Patron de `test_f073_sql.py` (texto del SQL sin comentarios `--`, YAML cargado
con el dominio del diccionario). Un test por R salvo R8, R13, R14 y R28, que son
MANUAL con el SQL de `tasks.md`. Los dos que no son obvios: R5/R7 exigen que la
lista de administrativos aparezca **una sola vez** en `sql/`, y R2 veta `MIN(`,
`ide ASC` y `obra_id ASC` dentro de la ventana. R22 compara contra la constante
27 (la `version` de `main` al escribir la spec).

## 7 · Riesgos y decisiones de diseno

- **Cambia lo publicado en `mart` y `cierre`** (D1): entran 0252, 0517 y 0720 con
  sus datos (7.564 + 72.737 + 142 filas de plan) y la 0720 cambia de `obra_id` en
  `mart.v_pbi_dim_obra` (2824201 -> 2759241). Power BI relaciona por `obra_id`:
  una relacion guardada con el id viejo deja de ver la 0720 (hoy ya no ve nada).
- **Dependencia de vistas**: `maestro.obras` cuelga de `stg.v_obra_fichas`;
  columnas nuevas de la vista, solo al final (regla de F-073 R18).
- **Fusion**: F-101 toca `version` de `00_global.yaml` y otra seccion de
  `azure-apps/datamart_seg_anual.md`; F-095 sube `TOTAL_TABLAS` por `rac`.
  Quien fusione segundo suma, no pisa.
- **Fuera del universo** la marca solo elige un representante (no son copias):
  por eso alli `obra_principal_id` es la propia ficha (R6).
- **Descartado**: «`obra_id` menor» (acierta en 0692, 0696, 0704 y 0710 pero
  **falla en la 0680**: la copia de la 28, 2278106, tiene el `ide` menor que la
  buena, 2278832); un ranking propio en `maestro` (dos definiciones que
  divergen); filtrar `maestro.obras` a principales (pierde el grupo b de §1.4).

## 8 · Decisiones abiertas para el humano

- **D1 · Ranking.** (A) el de hoy, extendido: cero cambio en `stg`, pero la 0720
  queda con la copia vacia de la 28 como principal (Juan no se reproduce: 56 de
  la 1, 47 con direccion) y 0252/0517 siguen fuera de `mart`. (B, **recomendada**)
  el de R2: arregla los tres. (C) `conext -> empresa <> 28 -> tiemod -> ide`:
  arregla solo la 0720.
- **D2 · Traducir el `obra_id` de las copias.** (A, **recomendada**) no
  reescribir nada; `maestro.obras.obra_principal_id` permite traducir al leer y
  la regla lo explica. (B) ademas, columna traducida en `personal.partes_lineas`
  cuando F-101 este fusionada (feature aparte). (C) reescribir el `obra_id` de los
  hechos: descartada, borra de quien es el coste (Porsan imputa a su ficha) y en
  el grupo b mezclaria el coste propio de Ruesma con el de la UTE (8,7 M€).
- **D3 · Nombre de la empresa.** (A, **recomendada**) ingerir `auxemp` (38
  filas, sin datos personales: nombre y CIF de sociedades). (B) publicar solo
  `empresa_id`: quita R11, R15, R16 y los `TOTAL_TABLAS`.
- **D4 · Aviso a `facturas`.** (A, **recomendada**) texto listo en
  `progress/impl_F-102.md` que el humano lleva a esa sesion; el proyecto
  `facturas` decide como usa `es_ficha_principal`. (B) el implementer escribe en
  el backlog de `facturas`: descartada, no es su repositorio.

## 9 · Limite del microservicio

Todo vive en el ETL: lee `raw`, publica `stg` y `maestro`, documenta en el
diccionario. No hay llamada nueva a `sigrid-api` salvo ingerir una tabla mas; no
se toca `psql-albaranes-rs9k2` a nivel de servidor. **Fuera de alcance, para el
backlog**: las 55 obras propias de Porsan (0006-0060, empresa 28) entran en
`stg.obras` sin presupuesto ni seguimiento (MCP, 2026-09-23).
