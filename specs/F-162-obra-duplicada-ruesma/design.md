<!-- specs/F-162-obra-duplicada-ruesma/design.md -->
# F-162 · Diseño · Todas las fichas de obra en el seguimiento, con su empresa y su ficha por defecto

Cifras: spec-author, 2026-11-11, solo lectura en Azure (`raw` de `20261111T000022Z-b97406`); el
detalle por ficha se regenera con los pasos 0 y 4 de §7.

## 1. Encaje y límite

Capa `stg` (lee `raw`) y, por arrastre, vistas de `mart`, `cierre`, `maestro` y el diccionario. Fuera
del repo solo cambia `azure-apps/datamart_seg_anual.md`; `mcp-bbdd` no (la IA aprende del diccionario).
`03`/`01` no están en `FICHEROS_DEL_SELLO` (`build_stg_step.py:113`) y `stg.plan_mensual`, `partidas`,
`presupuesto`, `fases` y `_fase0` ya se construyen para `raw.obr JOIN raw.con`
(`postgres_client.py:313`), no para `stg.obras`: no cambian.

## 2. Ficheros

**A crear**: `etl_sigrid/domain/ficha_obra.py` (§3.2); `tests/test_f162_fichas_por_empresa.py`;
`tests/test_f162_sandbox.py` (§6).

**A modificar**
- `sql/stg/01_ddl.sql` — `empresa_id INTEGER NULL`, `clave_obra VARCHAR(40) NULL`, `es_por_defecto
  BOOLEAN NOT NULL DEFAULT FALSE` DETRÁS de `_built_at` en el `CREATE TABLE IF NOT EXISTS
  stg.obras`, y la migración en el bloque `DO` (patrón de `version_fec_efectiva`, líneas 270-278),
  para que la posición sea la misma en Azure y en una base nueva. Índice `(empresa_id, codigo_obra)`.
- `sql/stg/03_obras.sql` — sin `WHERE rn = 1`; cabecera nueva (§3.1).
- `sql/maestro/01_obras.sql` — `es_por_defecto` al final (§3.3); su `COMMENT ON` y la cabecera.
- `sql/mart/05_views_powerbi.sql` — `v_pbi_dim_obra`: `empresa_id`, `clave_obra`, `es_por_defecto`
  al final y `obra_label` con la clave (D3). Ya hace `DROP ... CASCADE` + `CREATE`.
- `sql/cierre/05_views_cabecera.sql` — las tres columnas al final de `v_pbi_cierre_cabecera`, de
  `stg.obras o` (ya hace `DROP ... CASCADE`).
- `main.py` — ayudante `_obra_de_stg(cur, codigo_o_clave)` (código → ficha por defecto; `28-0721`
  → `clave_obra`) en los seis comandos de R12; `find-obra` muestra `empresa_id`/`clave_obra`.
- Diccionario: `stg.yaml` (ficha `obras`: grano «una fila por ficha», 634; `claves_alternativas:
  [[clave_obra], [empresa_id, codigo_obra]]`; columnas nuevas), `maestro.yaml` (`es_por_defecto`; la
  lista vieja de las líneas ~358, ~383, ~429), `mart.yaml` (`v_pbi_dim_obra`, `codigo_obra` del
  fact), `cierre.yaml` (cabecera, `codigo_obra` del fact), `personal.yaml` (`en_seguimiento`, su
  «Medido»), `00_global.yaml` (§4.2, preguntas de R16, `version` siguiente con su nota).
- `config/cobertura_excepciones.yaml` (fuera la sección 3 entera: 0517, 0252, 0720, 0606) y
  `tests/test_f052_cobertura.py` (`EXCEPCIONES_MAX = 19`).
- Tests que caen (R18): `tests/test_f102_obra_principal.py` (`HASH_STG_OBRAS_MAIN`, `r7_es_identico`,
  `r7_el_guarda_de_f073`, los dos `r18_*`) y `tests/test_f073_sql.py` (`r26`), cada uno sustituido
  por un comentario que remite a F-162. Se queda `test_f102_r7_stg_no_lee_la_vista_de_fichas`.
- Comentarios de `sql/maestro/00_setup.sql:62-64`, `docs/ARCHITECTURE.md:421-424` y
  `azure-apps/datamart_seg_anual.md:338-340` (commit local en `azure-apps`; el push, del humano).

**NO se tocan**: `maestro.v_obra_fichas`/`es_ficha_principal` (solo `raw`; `compras` depende); `stg/04-09`;
`mart/01-04,06`, `cierre/01-04,06`, `personal`, `tesoreria`, `retenciones` (van por `obra_id`); `mcp-bbdd`.

## 3. El SQL y el criterio

### 3.1 `stg/03_obras.sql`

```sql
INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa, empresa_id, clave_obra, es_por_defecto)
WITH fichas AS (
    SELECT obr.ide AS obra_id, con.cod AS codigo_obra, con.res AS nombre_obra,
           con.emp AS empresa_id, con.emp::text || '-' || con.cod AS clave_obra, con.tiemod
    FROM raw.obr obr JOIN raw.con con ON con.ide = obr.ide
    WHERE <filtro de códigos de hoy, sin cambios>
), dudosas AS (            -- solo los códigos con varias fichas y ninguna de la empresa 1
    SELECT obra_id FROM fichas f
    WHERE codigo_obra IN (SELECT codigo_obra FROM fichas GROUP BY codigo_obra
                          HAVING count(*) > 1 AND NOT bool_or(empresa_id = 1))
), lineas AS (             -- R5: se agrega ANTES de unir
    SELECT p.obride, count(*) AS num_lineas
    FROM raw.obrparpre p WHERE p.obride IN (SELECT obra_id FROM dudosas) GROUP BY p.obride
)
SELECT f.obra_id, f.codigo_obra, f.nombre_obra, TRUE, f.empresa_id, f.clave_obra,
       ROW_NUMBER() OVER (PARTITION BY f.codigo_obra ORDER BY
           CASE WHEN f.empresa_id = 1 THEN 0 ELSE 1 END,
           COALESCE(l.num_lineas, 0) DESC,
           f.tiemod DESC NULLS LAST,
           f.obra_id DESC) = 1
FROM fichas f LEFT JOIN lineas l ON l.obride = f.obra_id;
```

- (2) «si solo hay una ficha, esa» sale sola (partición de una fila). **Coste**: `raw.obrparpre` (13,7 M filas) no tiene índice por `obride`; un `GROUP BY` completo
  tarda **48 s** (medido 12:06:21-12:07:09 UTC). Hoy `dudosas` está **vacía** (§5.1), así que el
  implementer mide con `EXPLAIN (ANALYZE)` en solo lectura que el plan no barre la tabla con el
  conjunto vacío; si la barre, se acepta el coste (≤ 48 s) y se anota. Lo que no vale es una
  subconsulta correlacionada por ficha: tardó > 300 s.
- `raw.con.emp` es `integer` y no tiene nulos (0 de 925); `empresa_id = 1` trata un nulo como «no
  Ruesma». Dentro de una empresa el código es único (F-102), así que la empresa 1 aporta como
  mucho una ficha por código; si un día no fuera así, deciden las líneas y después `tiemod`.

### 3.2 El criterio y la marca `conext` 15 (R5-R7)

`etl_sigrid/domain/ficha_obra.py`: `FichaObra` (dataclass congelada: `obra_id`, `codigo_obra`,
`empresa_id`, `num_lineas`, `tiemod`), `EMPRESA_RUESMA = 1`, `clave_por_defecto(f) -> tuple` (menor
= mejor) y `ficha_por_defecto(fichas) -> FichaObra` (`ValueError` si vacía, o si mezcla códigos).

**`conext` 15 no entra**, por tres razones: (a) el humano da el orden completo y no la nombra; (b)
la marca dice cuál de las fichas duplicadas es «la vigente», que es justo la elección que el modelo
nuevo abandona: cada ficha es vigente en su empresa; (c) medido, no decide nada: en los 49 códigos
con varias fichas, todos con ficha de la empresa 1, la marca nunca está en otra empresa sin estar
también en la de Ruesma (solo en la 0606 la tienen las dos). Si el humano la quiere, es una línea
entre (1) y (3) y su test (D2).

### 3.3 `maestro.obras.es_por_defecto` (R8)

`LEFT JOIN stg.obras so ON so.obra_id = c.ide` y `COALESCE(so.es_por_defecto, vf.es_ficha_principal)`
como última columna (el `CREATE OR REPLACE VIEW` solo admite columnas nuevas al final, línea 82).
`maestro` ya lee `stg` (`tiene_presupuesto`) y `build_maestros` depende de `build_stg`. No se pone en
`v_obra_fichas`: lee solo `raw`, la leen las vistas de `compras` en cada consulta y contar líneas
ahí costaría los 48 s en cada una. Hoy `es_por_defecto` = `es_ficha_principal` en las 925 fichas
(§5.1): solo difieren si un código con varias fichas no tiene la de Ruesma.

## 4. Quién cruza por código, y la IA

### 4.1 Barrido (R10)

Barridos los `GROUP BY`/`PARTITION BY`/`JOIN` de `sql/` sin comentarios: **ninguno agrupa ni cruza
por `codigo_obra` sin `obra_id`** salvo el ranking de `maestro/00_setup.sql` (intencionado); `mart`,
`cierre`, `retenciones`, `compras` y `tesoreria` llevan `obra_id` o `partida_id` en la clave. En
Python, huellas, cobertura, mes-fase y ventana usan `obra_id` de clave y el código de etiqueta.
**Solo saldrían duplicados** en los seis `fetchone` de `main.py` (R12) y en Power BI y la IA, que
filtran por código (R11, R13). Cobertura y `--obras-esperadas` van por código: abarcan las dos.

### 4.2 Las reglas (R13-R17)

- `R-EMPRESA-POR-DEFECTO` · `resumen` propuesto (≤ 250, conserva «`empresa_id = 1`», F-147 R7):
  «Sin empresa en la pregunta: para una obra, su ficha `es_por_defecto` (la de Ruesma si existe);
  en lo demás, `empresa_id = 1`. Dilo. El mismo código puede ser la obra en varias empresas: nunca
  sumes sus fichas sin decirlo.» La `regla` (≤ 1.200) cambia «`stg`, `mart`, `cierre` y
  `descompuestos` no tienen empresa» por «`stg`, `mart` y `cierre` tienen una fila por ficha: se
  llega a la empresa y a `es_por_defecto` por `obra_id` → `stg.obras`», y añade el aviso cuando la
  ficha por defecto no tiene datos y otra del código sí (hoy 0581 y 0671: los datos están en la UTE).
  Conserva los términos que fija `tests/test_f144_empresa_por_defecto.py`.
- `R-UNIVERSO-OBRA`: una fila por ficha (634 fichas, 585 códigos); conserva «lo dice su ficha».
- Presupuesto: el implementer mide con `test_f147_presupuesto_contexto.py` y, si sube, acorta.

## 5. Medido el 2026-11-11

### 5.1 El universo

| | Hoy | Con F-162 |
|---|---|---|
| Fichas en `stg.obras` | 585 (523 de la empresa 1, 57 de la 28, 5 de UTE) | **634** (527 de la 1, 97 de la 28, 10 de otras) |
| Códigos | 585 | 585 (49 con varias fichas, **todos** con ficha de la empresa 1) |
| Con presupuesto / con plan | — | 509 / 355 (de las 49 nuevas: 9 / 4) |

Entran 49 fichas: 40 de PORSAN (vacías), 4 de Ruesma (1-0581, 1-0606, 1-0671, 1-0721) y 5 de UTE
o de otra empresa (12-0252, 14-0272, 15-0309, 25-0517, 26-0455). Los 58 códigos sin ficha de Ruesma
tienen UNA sola ficha: la regla (3) de R5 hoy no se aplica a nadie. `es_por_defecto` cambia
respecto a la ficha de hoy en 0581, 0606, 0671 y 0721 (pasa a la de Ruesma); en 0252 y 0517 la de
hoy ya era la de Ruesma.

### 5.2 Lo que gana datos (las 4 fichas nuevas con plan; ninguna de hoy pierde ni una fila)

| Ficha | Presupuesto | Plan (ámbitos: filas) | Coste 3 / venta 7 (suma `importe_mes`) |
|---|---|---|---|
| 12-0252 (650280) | 28.511 | 3: 4.809 · 7: 4.213 | 4.547.711 / 4.129.990 |
| 25-0517 (1088657) | 158.737 | 3: 68.706 · 7: 65.739 · 8: 3.324 · 11: 3.288 | 6.092.837 / 6.814.253 |
| 1-0606 (1562946) | 1.017 | 3: 921 · 7: 926 · 8: 231 · 11: 216 | 1.811.435 / 1.890.561 |
| 1-0721 (2759553) | 9.165 | 3: 283 · 7: 129 | 499.364 / 479.758 |

Con presupuesto y sin plan (entran en `stg.obras` y en la cabecera de `cierre`, no en el fact):
14-0272 (119), 15-0309 (2), 26-0455 (103), 1-0581 (125) y 1-0671 (112). `_fase0`: 0517 y 0606.

### 5.3 Arrastre por capa

- **`mart`** (`INNER JOIN stg.obras`): +152.785 filas de plan de entrada (0,47 % de 32,85 M) →
  cuatro fichas más en el fact (351 → 355 obras). `v_pbi_dim_obra`: 585 → 634 filas.
- **`cierre`**: el fact gana esas cuatro; la cabecera (`FROM stg.obras`) pasa a 634 filas.
- **`personal.partes_lineas.en_seguimiento`**: 18.521 líneas (3.429.850,04 €) de las 49 fichas
  nuevas pasan a TRUE (hoy FALSE): los partes de PORSAN a su propia copia (la 0704 de F-102).
- **`tesoreria`** (devengo pendiente desde `mart`): lo planificado después del último real. 0252
  sin master; 0517 con master de 2018 y real hasta 2022-04; 0721 sin master (F-161); 0606 a
  comprobar. Esperado: sin devengo nuevo (§7, paso 6).
- **`retenciones`**: `fin_obra` ya trae todas las fichas; lo de `cierre` llega una noche después.
- **Power BI**: `obra_id` estable para las 585 de hoy; aparecen 49 filas más en la dimensión y 6
  códigos con dos filas con datos o presupuesto (0252, 0517, 0581, 0606, 0671, 0721). D3.

### 5.4 Coste de la nocturna

`build_mart` 4.968 s y `build_cierre` 2.845 s de media (8 días): +0,47 % de entrada son unos +25 s
y +15 s. `03_obras.sql`: +0 s si el plan no barre `obrparpre` con `dudosas` vacía, +48 s si la barre.

## 6. Tests (sin red ni BBDD salvo el sandbox)

`tests/test_f162_fichas_por_empresa.py` (nombres `test_f162_rN_*`):
- r1/r2: sin `WHERE rn = 1` ni filtro nuevo (RED en `17b41ec`); r3: DDL, migración, `INSERT` de 7;
  r4: `claves_alternativas`; r6: el SQL no nombra `conext`; r7: `ORDER BY` = `clave_por_defecto`.
- r5: oráculo parametrizado: Ruesma gana aunque la otra tenga más líneas, `tiemod` e `ide` mayores;
  ficha única; varias sin Ruesma: líneas > `tiemod` > `ide`; `tiemod` NULL pierde.
- r8: `maestro/01_obras.sql`: `es_por_defecto` última columna con el `COALESCE`.
- r11/r12: columnas de las dos vistas; el ayudante de `main.py` (con un cursor falso: código →
  `es_por_defecto`, `28-0721` → `clave_obra`, código inexistente → mensaje).
- r13-r17: términos de las reglas, ámbitos, fichas, preguntas, versión; r19: `EXCEPCIONES_MAX == 19`.

`tests/test_f162_sandbox.py` (`F162_SANDBOX_DSN`, base nueva y borrada al final como
`tests/test_f157_sandbox.py`; tipos de la ingesta): `raw.obr`, `raw.con`, `raw.obrparpre` mínimas;
ejecuta `01_ddl.sql` y `03_obras.sql` reales: 0721 con dos filas y `es_por_defecto` en la de la 1;
código sin Ruesma con dos fichas (gana la de más líneas; con empate, `tiemod`); un código
administrativo fuera; oráculo = SQL en todos. Lo ejecuta el líder con DSN.

## 7. Pasos MANUAL (tras APROBADO y merge; los lanza el humano, fuera de 00:00-05:00 UTC)

`<PY>` = `.venv/Scripts/python.exe` desde la raíz; `<Q>` = `filas_solo_lectura` con
`_bootstrap_done = True`. Vuelta atrás de código: `17b41ec` (o la punta previa al merge).

0. **ANTES, mismo `raw`**: tag del job (`az containerapp job show -n caj-datamart-seg-dev -g
   rg-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`); `huella-obras
   --desde mart|cierre|dimension|plan_obra --out antes_<x>.csv`; con `<Q>`, filas por ficha de
   §5.2-5.3 (a `progress/impl_F-162.md`).
1. `infra/70_build_image.ps1` → tag nuevo. 2. `infra/85_update_job.ps1 -Tag <tag nuevo>`.
3. Job puntual SIN ingesta (`--yaml`, memoria «job puntual sin ingesta»): `stage && build-mart &&
   build-maestros && build-cierre && build-tesoreria && build-retenciones && build-personal &&
   apply-grants`. Sin `--reconstruir-todo`.
4. Huellas otra vez y `comparar-huellas antes despues --obras-esperadas
   0252,0517,0606,0721,0272,0309,0455,0581,0671`. `cierre`: solo esas. `dimension` y `plan_obra`:
   solo cambia la etiqueta `codigo_obra` de fichas nuevas (filas e importes idénticos). `mart`: sale
   ≠ 0 por el motivo 2 (ámbitos 8/11) SOLO en 0517 y 0606; se acepta leyendo la lista. Otra = PARAR.
5. `<Q>`: `count(*)` de `stg.obras` = 634; un `es_por_defecto` por código (`count(*) FILTER (WHERE
   es_por_defecto)` = 585); `empresa_id IS NULL` = 0; dos filas para 0721 (1 y 28).
6. `<Q>`: `tesoreria.devengo_pendiente_obra_mes` de 650280, 1088657, 1562946 y 2759553 → 0 filas;
   si no, PARAR.
7. `check-cobertura` sin KO de 0252, 0517, 0606, 0720 ni 0721; `check-unicidad` OK (claves nuevas).
8. `publicar-diccionario` (con la imagen del paso 1 en el job), `check-diccionario`, reinicio MCP.
9. La nocturna siguiente: `build_stg`, `build_mart`, `build_maestros`, `build_cierre` SUCCESS.
10. Power BI (humano): filtro por defecto según D3.

**Vuelta atrás**: (1) `85_update_job.ps1 -Tag <tag del paso 0>`; (2) `DROP VIEW maestro.obras
CASCADE` (el `CREATE OR REPLACE` viejo no puede quitar `es_por_defecto`; arrastra las vistas que la
leen en `compras/01_documentos.sql`, `personal/05_views.sql` y `retenciones/01-02`); (3) relanzar el
job puntual del paso 3 añadiendo `build-compras` antes de `apply-grants`: `stg.obras` vuelve a 585 y
`mart`/`cierre`/vistas se rehacen como hoy; (4) `publicar-diccionario` desde `17b41ec`. Las tres
columnas de `stg.obras` quedan a NULL/FALSE, inofensivas (el `03` viejo nombra sus columnas).

## 8. Decisiones abiertas y features vecinas

- **D1** · fuera del seguimiento, `maestro.obras.es_por_defecto` = `es_ficha_principal` (o NULL).
- **D2** · `conext` 15 fuera del criterio (§3.2). Si se quiere, va entre (1) y (3).
- **D3** · Power BI: (a) sin filtro, con `obra_label` = `clave_obra · nombre` (recomendada: hoy
  0581, 0606 y 0671 se ven por la ficha de la UTE y un filtro `es_por_defecto` las dejaría sin datos
  en Power BI); (b) filtro de informe `es_por_defecto = TRUE`; (c) filtro `empresa_id = 1`. Cambiar
  `obra_label` cambia el texto de las 585 de hoy (`1-0581 · …`).
- **D4** · Agregados sin empresa en `mart`/`cierre` (p. ej. «coste del año»): `empresa_id = 1`
  (propuesta de §4.2, coherente con la regla de 2026-10-18) o una ficha por código
  (`es_por_defecto`, que mete los 58 códigos sin Ruesma, como hoy).
- **D5** · ¿`empresa_id`/`clave_obra` también en los hechos de `mart`/`cierre`? Propuesta: no (por `obra_id`).
- **F-053** · propuesta: cerrarla como **absorbida por F-162** (sus 0517, 0252, 0720 y 0606
  publican cada ficha con lo suyo; la elección de negocio de la 0606 deja de hacer falta).
- **F-106** · enmienda propuesta, en lugar de su punto (1): «El seguimiento (`stg`, `mart`, `cierre`)
  lleva desde F-162 todas las fichas de todas las empresas, cada una por su `obra_id`, con
  `empresa_id`, `clave_obra` y `es_por_defecto`. F-106 queda para RECURSOS, PARTES y COMPRAS de
  otras empresas: atribuirlos a la obra de SU empresa sin consolidar, y decidir con el humano cómo
  los ve Power BI.» El RIESGO de su descripción («cambia el `obra_id` de 0581, 0606, 0671, 0720»)
  ya no aplica: ningún `obra_id` publicado cambia.
- **D6 (aviso)** · 1-0721 entra con reales (3 y 7) y sin master: sin `planif` (F-161).
