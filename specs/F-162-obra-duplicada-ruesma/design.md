<!-- specs/F-162-obra-duplicada-ruesma/design.md -->
# F-162 · Diseño · Desempate de fichas en `stg.obras`, con Ruesma delante si los datos no deciden

Requisitos: `requirements.md`. Diagnóstico: `progress/explore_0721_obra_duplicada.md`. Las cifras
de este documento las midió el spec-author el 2026-11-11 (10:40-12:30 UTC) en solo lectura contra
Azure, sobre el `raw` de la nocturna `20261111T000022Z-b97406`.

## 1. Encaje y límite

Capa `stg`, lee solo `raw`; no cruza la frontera del servicio (fuera del repo solo cambia nuestro
`azure-apps/datamart_seg_anual.md`). Hotfix acotado: «cada obra desde su empresa» sigue en F-106.

`03_obras.sql` y `01_ddl.sql` NO están en `FICHEROS_DEL_SELLO` (`build_stg_step.py:113`): cambiarlos
no fuerza la reconstrucción completa de `stg.plan_mensual`. Y `stg.plan_mensual`, `stg.partidas`,
`stg.presupuesto` y `stg.fases` se construyen para el universo `raw.obr JOIN raw.con`
(`postgres_client.py:313`), no para `stg.obras`: **no cambian ni una fila** (§5.2).

## 2. Ficheros

**A crear**
- `etl_sigrid/domain/ficha_obra.py` — oráculo puro del orden (§3).
- `tests/test_f162_desempate_obras.py` — oráculo, texto del SQL, DDL, fichas, cobertura (§4).
- `tests/test_f162_sandbox.py` — el `03_obras.sql` real contra un Postgres desechable (§4).

**A modificar**
- `etl_sigrid/infrastructure/postgres/sql/stg/03_obras.sql` — cabecera (R11), CTE del recuento,
  `EXISTS` de la marca, `ORDER BY` de cinco criterios, `empresa_id` en `INSERT`/`SELECT` (§3).
- `etl_sigrid/infrastructure/postgres/sql/stg/01_ddl.sql` — `empresa_id INTEGER NULL` detrás de
  `_built_at` en el `CREATE TABLE IF NOT EXISTS stg.obras` y migración en el bloque `DO` (patrón
  de `version_fec_efectiva`, líneas 270-278): `IF NOT EXISTS (information_schema.columns ...)
  THEN ALTER TABLE stg.obras ADD COLUMN empresa_id INTEGER NULL`.
- `config/diccionario/stg.yaml` — ficha `obras` (descripción «UNA FICHA POR CODIGO», columna
  `empresa_id`, relación a `maestro.obras`) (R12).
- `config/diccionario/maestro.yaml` (líneas ~358, ~383, ~429), `sql/maestro/00_setup.sql:62-64` y
  `sql/maestro/01_obras.sql:19-20` (solo comentarios), `docs/ARCHITECTURE.md:421-424`: la lista de
  códigos en que difieren pasa a la de §5.4 (R13). No se toca el `COMMENT ON` de la línea 127
  («stg.obras NO la usa»): sigue siendo cierto.
- `config/diccionario/00_global.yaml` — `version` a la siguiente libre (hoy 75 → 76) con su nota.
  La nota de la v29 (línea 174) es historia y no se reescribe.
- `config/cobertura_excepciones.yaml` — fuera las entradas `0517` y `0252` (sección 3, F-053) y
  el párrafo de la sección se ajusta («las que dependen de F-053» quedan 0720 y 0606).
- `tests/test_f052_cobertura.py` — `EXCEPCIONES_MAX = 21` (R16).
- `tests/test_f102_obra_principal.py` — se retira `test_f102_r7_stg_obras_es_identico_al_de_main`
  y `HASH_STG_OBRAS_MAIN`, con un comentario que remite a F-162 (R15). Se quedan
  `test_f102_r7_el_guarda_de_f073_sigue_en_pie` y `test_f102_r7_stg_no_lee_la_vista_de_fichas`.
- `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md:338-340` — «`stg.obras` no
  cambia» pasa a la regla nueva y la columna `empresa_id` (commit local en `azure-apps`; el push
  es del humano).

**NO se tocan**: `maestro.v_obra_fichas` y su orden (es otra pregunta: «cuál es la ficha de
Ruesma», F-102); `stg/04`-`09` (sello y universo, §1); `mart/*.sql` y `cierre/*.sql` (leen
`stg.obras` por `obra_id` y columnas con nombre: la columna nueva no les afecta); el filtro de
códigos (R6); `personal/02_partes_lineas.sql` (su `EXISTS` contra `stg.obras` recoge el cambio
solo); la excepción `0720` (ver D3) y la `0606`.

## 3. El SQL y el oráculo

`03_obras.sql`, esqueleto (el implementer conserva el `TRUNCATE` y el filtro tal cual):

```sql
INSERT INTO stg.obras (obra_id, codigo_obra, nombre_obra, activa, empresa_id)
WITH lineas_presupuesto AS (          -- R5: se agrega ANTES de unir; sin fan-out
    SELECT obride, count(*) AS num_lineas FROM raw.obrparpre GROUP BY obride
), ranked AS (
    SELECT obr.ide AS obra_id, con.cod AS codigo_obra, con.res AS nombre_obra,
           con.emp AS empresa_id,
           ROW_NUMBER() OVER (PARTITION BY con.cod ORDER BY
               CASE WHEN EXISTS (SELECT 1 FROM raw.conext x
                                 WHERE x.conide = obr.ide AND x.cod = '15') THEN 0 ELSE 1 END,
               COALESCE(lp.num_lineas, 0) DESC,
               CASE WHEN con.emp = 1 THEN 0 ELSE 1 END,
               con.tiemod DESC NULLS LAST,
               obr.ide DESC) AS rn
    FROM raw.obr obr
    JOIN raw.con con ON con.ide = obr.ide
    LEFT JOIN lineas_presupuesto lp ON lp.obride = obr.ide
    WHERE <filtro de hoy, sin cambios>
)
SELECT obra_id, codigo_obra, nombre_obra, TRUE AS activa, empresa_id FROM ranked WHERE rn = 1;
```

- `raw.con.emp` es `integer` en Azure y hoy no hay ningún nulo (0 de 925 fichas); la columna se
  declara `NULL` igualmente, y `CASE WHEN con.emp = 1` trata un nulo como «no Ruesma».
- La marca pasa de `LEFT JOIN` a `EXISTS`, como en `maestro.v_obra_fichas`. Hoy no hay ninguna
  ficha con dos filas cod 15 (medido), así que el resultado no cambia por esto.
- `rn = 1` se queda literal: lo exige `test_f073_r26_no_toca_el_desempate_de_stg_obras`.

`etl_sigrid/domain/ficha_obra.py` (domain, sin dependencias): `FichaObra` (dataclass congelada:
`obra_id`, `codigo_obra`, `empresa_id: int | None`, `marcada_vigente`, `num_lineas`, `tiemod: int
| None`), `EMPRESA_RUESMA = 1`, `clave_desempate(f) -> tuple` (menor = mejor, los cinco criterios
de R1; `tiemod` NULL al final, como el SQL) y `elegir_ficha(fichas) -> FichaObra` (`ValueError`
si viene vacía). El test de texto (R7) extrae el `ORDER BY` del `ROW_NUMBER` y comprueba las
cinco expresiones en orden; oráculo y SQL se cruzan en el sandbox con los mismos casos.

## 4. Tests (sin red ni BBDD salvo el sandbox)

`tests/test_f162_desempate_obras.py`:
- `test_f162_r2_la_0721_elige_la_ficha_de_ruesma_con_lineas` — oráculo con las dos fichas reales
  (2759553: emp 1, sin marca, 9.165 líneas; 2855829: emp 28, sin marca, 0, `tiemod` mayor).
- `test_f162_r2_el_sql_de_main_no_cuenta_lineas` — RED documentado: el `ORDER BY` de hoy no tiene
  el criterio (2); se ejecuta contra el fichero del árbol, así que en `main` falla y después pasa.
- `test_f162_r3_empate_en_datos_gana_ruesma` — misma marca y mismas líneas; la de otra empresa es
  más reciente y de `ide` mayor; gana la de emp 1. Variante con las dos a 0 líneas.
- `test_f162_r4_cada_criterio_manda_sobre_los_siguientes` — parametrizado, una frontera por
  línea: marca vacía > sin marca con líneas; más líneas UTE > menos líneas Ruesma (0252, 0517);
  Ruesma > `tiemod` mayor; `tiemod` mayor > `ide` mayor; `tiemod` NULL pierde; `ide` mayor.
- `r5_*`: CTE con `GROUP BY obride`, ningún `JOIN raw.obrparpre` en `ranked`, `COALESCE(..., 0)`,
  marca por `EXISTS`. `r6_*`: filtros y `TRUE AS activa` idénticos. `r7_el_order_by_sigue_al_oraculo`.
- `r8_*` / `r9_*`: `empresa_id INTEGER NULL` tras `_built_at`, migración en el `DO`, `INSERT` de cinco.
- `test_f162_r11_*`, `r12_*`, `r13_*` — cabecera, ficha (columna `empresa_id`, la regla, la lista
  nueva de §5.4) y que ningún fichero de R13 conserve «0581, 0606, 0671 y 0720».
- `test_f162_r16_*` — ni `0252` ni `0517` en las excepciones; `EXCEPCIONES_MAX == 21`.

`tests/test_f162_sandbox.py` (`F162_SANDBOX_DSN`, base nueva por test y borrada al final, patrón de
`tests/test_f157_sandbox.py`; tipos de la ingesta: ids `integer`, `tiemod` `integer`): crea
`raw.obr`, `raw.con`, `raw.conext`, `raw.obrparpre` mínimas, ejecuta `01_ddl.sql` y `03_obras.sql`
reales y comprueba R2-R5, R10 (`empresa_id` 1, 12 y 25), un código administrativo excluido y que
`elegir_ficha` da lo mismo que el SQL en todos los casos. Ejecutarla con DSN es parte de la puerta
del líder (memoria «la puerta completa, fuera del worktree»).

## 5. Qué arrastra el cambio (medido el 2026-11-11)

### 5.1 Las tres fichas nuevas y las tres que salen

| `obra_id` | código | emp | `stg.presupuesto` | `stg.partidas` | `stg.plan_mensual` (ámbitos) | `stg.fases` |
|---|---|---|---|---|---|---|
| 650280 entra | 0252 | 12 | 28.511 | 506 | 9.022 (3, 7) | 34 |
| 1088657 entra | 0517 | 25 | 158.737 | 2.692 | 141.057 (3, 7, 8, 11) | 34 |
| 2759553 entra | 0721 | 1 | 9.165 | 1.256 | 412 (3, 7) | 5 |
| 587639 sale | 0252 | 1 | 22 | 107 | 0 | 0 |
| 1060846 sale | 0517 | 1 | 207 | 211 | 0 | 0 |
| 2855829 sale | 0721 | 28 | 0 | 0 | 0 | 0 |

Las tres que salen tienen **0 filas** de `stg.plan_mensual` y hoy **0** en
`mart.fact_seguimiento_mensual` y `cierre.fact_cierre_mensual`: **ninguna cifra publicada
desaparece**; el cambio solo AÑADE obras al seguimiento. `stg.obras` sigue con 585 filas.

### 5.2 Por capa (quién lee `stg.obras` y por qué clave; todos por `obra_id`)

- **`stg.partidas`, `stg.presupuesto`, `stg.plan_mensual`, `_fase0`, `stg.fases`**: no lo leen;
  **no cambian** (huella `plan_obra` idéntica). La 0252 y la 0517 están congeladas por la ventana
  (`_meta.obra_build`: sin actividad desde 2014 y 2022) y conservan sus filas del 08-11.
- **`mart`** (`02_build_fact.sql:239-332`, `INNER JOIN stg.obras`; se rehace entero cada noche):
  entran la 0252 (ámbitos 3 y 7: 4.547.710,53 € de coste y 4.129.990,44 € de venta, 2010-07 a
  2014-01), la 0517 (3 y 7: 6.092.837,38 € y 6.814.253,09 €, 2017-02 a 2022-04; y master 8 y 11
  de 2018) y la 0721 (3 y 7: 499.363,68 € y 479.758,35 €, 2026-06 a 2026-10). Sumas de
  `importe_mes` de `stg.plan_mensual` sobre todas sus versiones: la cifra del fact la da la huella.
  `mart.v_pbi_dim_obra` (`05_views_powerbi.sql:26`) cambia el `obra_id` de esos tres códigos.
  `mart.master_versiones_tipadas` lee `stg.plan_mensual` sin `stg.obras`: no cambia (hoy solo
  tiene la 1088657, 4 filas).
- **`cierre`** (`02_build_fact.sql:314`, `04_views_detalle.sql:476,574`,
  `05_views_cabecera.sql:183`): las tres obras entran en el fact y en la cabecera.
- **`personal.partes_lineas.en_seguimiento`** (`EXISTS` contra `stg.obras`): pasan a TRUE las
  líneas de 650280 (1.992) y 2759553 (224); a FALSE las de 587639 (109), 1060846 (1.136) y
  2855829 (2). Hoy: 1.247 TRUE / 2.216 FALSE entre las seis fichas.
- **`tesoreria`** (`07_devengo_pendiente.sql` lee `mart.fact_seguimiento_mensual`): el devengo
  pendiente es lo PLANIFICADO posterior al último mes REAL. 0252 no tiene master; los master de la
  0517 (2018-05 a 2018-11) son anteriores a su último real (2022-04); la 0721 no tiene master en
  `stg.plan_mensual` (sus 9.165 líneas no traen `planif`, F-161). **Esperado: sin devengo nuevo**;
  se comprueba (§6, paso 6).
- **`retenciones`** (lee `cierre.fact_cierre_mensual`, `cierre.v_pbi_cierre_cabecera` y
  `mart.master_versiones_tipadas`): `fin_obra` ya tiene las seis fichas (sale de `maestro`), pero
  `ultimo_cierre` y lo que viene de `cierre` se rellenará para las tres nuevas. En la nocturna
  `retenciones` corre ANTES que `cierre`: lo verá una noche después salvo el job puntual (§6).
- **Python**: `cobertura_sql.py`, `huella_obras.py`, `huella_ampliada.py`, `mes_fase_sql.py` unen
  por `obra_id` con columnas nombradas. `check-unicidad` sigue (un `codigo_obra` por fila).
- **Fuera del ETL**: Power BI y el MCP ven otro `obra_id` para 0252, 0517 y 0721 (el anterior no
  tenía ni una fila en el fact); `SELECT *` sobre `stg.obras` ve una columna más al final. La skill
  del ABC y las consultas ganan `empresa_id`.

### 5.3 El riesgo de las cifras históricas (cambio deseado)

La 0252 y la 0517 son obras cerradas (2009 y 2016) que hoy NO publican nada en `mart` ni `cierre`
(F-052 las declaró invisibles: ~10,6 M€ de coste y ~10,9 M€ de venta). Con F-162 aparecen con la
ficha de su UTE, que es la que tiene los datos. Mueve totales históricos de Power BI (años
2010-2014 y 2017-2022) **hacia arriba**, y es lo deseado; quien compare un informe anterior verá
la diferencia. No dobla nada: la ficha de Ruesma de esas obras no publicaba ninguna fila.

### 5.4 `stg.obras` frente a `maestro.obras.es_ficha_principal` después de F-162

Eligen distinto en **cinco** códigos, todos con la ficha de la UTE en `stg.obras`: **0252** (12),
**0517** (25), **0581** (27), **0606** (31) y **0671** (34). La 0720 y la 0721 coinciden (la 0720 ya
elige hoy la 2759241, emp 1, con el orden actual; la 0721 pasa a la 2759553).

### 5.5 Coste nocturno

El recuento de `raw.obrparpre` (13,7 M filas, sin índice por `obride`) es un barrido completo:
**48 s** medidos (12:06:21-12:07:09 UTC) en el B2s. Se acepta (D2); una consulta correlacionada por
ficha, sin índice, tardó más de 300 s y se descartó.

## 6. Pasos MANUAL (tras APROBADO y merge; los lanza el humano, fuera de 00:00-05:00 UTC)

`<PY>` = `.venv/Scripts/python.exe` desde la raíz del checkout principal; `<Q>` = lectura con
`filas_solo_lectura` y `_bootstrap_done = True`. Vuelta atrás de código: **`17b41ec`** (o la punta
de `main` previa al merge).

0. **ANTES, mismo `raw`**: tag actual del job (`az containerapp job show -n caj-datamart-seg-dev -g
   rg-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`); huellas
   `<PY> main.py huella-obras --desde mart|cierre|dimension|plan_obra --out antes_<x>.csv`; y con
   `<Q>` la ficha por código y el recuento por objeto de §5.1-5.2 para los seis `obra_id`
   (la salida se guarda en `progress/impl_F-162.md`).
1. `powershell -NoProfile -File infra/70_build_image.ps1` → tag nuevo.
2. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag nuevo>`; el `az` del paso 0 debe
   acabar en ese tag.
3. **Job puntual SIN ingesta** con `--yaml` (memoria «job puntual sin ingesta»), comando
   `python main.py stage && python main.py build-mart && python main.py build-cierre && python
   main.py build-tesoreria && python main.py build-retenciones && python main.py build-personal &&
   python main.py apply-grants`. Sin `--reconstruir-todo`: el sello no cambia. Lejos de la nocturna.
4. **DESPUÉS**: las cuatro huellas otra vez y `<PY> main.py comparar-huellas antes_<x>.csv
   despues_<x>.csv --obras-esperadas 0252,0517,0721`. Esperado: `dimension`, `cierre` y `plan_obra`
   en verde; `mart` sale con código ≠ 0 SOLO por el motivo 2 (ámbitos 8/11) y SOLO en la 0517, cuyos
   master entran por primera vez: se acepta leyendo la lista entera; cualquier otra obra = PARAR.
5. Con `<Q>`: `SELECT codigo_obra, obra_id, empresa_id FROM stg.obras WHERE codigo_obra IN
   ('0252','0517','0721')` → 650280/12, 1088657/25, 2759553/1; `count(*)` = 585; `count(*) WHERE
   empresa_id IS NULL` = 0; filas del fact y del cierre por esas tres > 0.
6. Con `<Q>`: `tesoreria.devengo_pendiente_obra_mes` para los tres `obra_id` → 0 filas (§5.2);
   si no, PARAR y reportar.
7. `<PY> main.py check-cobertura` → sin KO de 0252, 0517 ni 0721; `check-unicidad` OK.
8. `<PY> main.py publicar-diccionario` → la versión de T7, solo con la imagen del paso 1 en el job
   (memoria «publicar el diccionario solo con su imagen»); `check-diccionario`; reinicio del MCP.
9. La nocturna siguiente: `build_stg` y `build_mart` SUCCESS en `_meta.etl_runs` y el paso 5 igual.

**Vuelta atrás**: (1) `infra/85_update_job.ps1 -Tag <tag del paso 0>`; (2) relanzar el job puntual
del paso 3 (o esperar a la nocturna): `stg.obras` vuelve a la elección de hoy y `mart`/`cierre`
pierden las tres obras; (3) `publicar-diccionario` desde `17b41ec` → v75. La columna `empresa_id`
queda en Azure a NULL, inofensiva: el `03` viejo nombra sus columnas. Quitarla (`ALTER TABLE
stg.obras DROP COLUMN empresa_id`) es opcional y es una escritura del humano.

## 7. Decisiones

- **D1 (tomada)**: la columna al FINAL, también en el `CREATE`, para que la posición sea la misma
  en Azure y en una base nueva (el patrón de `plan_mensual` la pone antes de `_built_at` y las
  bases divergen). Nadie hace `INSERT`/`SELECT` posicional sobre `stg.obras` (buscado: el único
  `INSERT` es el del `03`, con lista de columnas; las vistas nombran columnas).
- **D2 (tomada)**: contar líneas en `raw.obrparpre` (criterio del humano) aunque cueste 48 s. La
  alternativa «tiene cabecera en `obrfasamb`» (la de la ampliación del diagnóstico) solo cambiaba la
  0721 y no recupera 0252 ni 0517.
- **D3 (abierta)** · la excepción `0720` de cobertura: la 0720 ya elige su ficha de Ruesma con
  datos (§5.4), así que probablemente sobra. Propuesta: comprobarlo en el paso 7 y, si no salta,
  quitarla aquí (`EXCEPCIONES_MAX` 20). Si el humano prefiere no mezclar, se queda para F-053.
- **D4 (abierta)** · F-053 (`pending`): F-162 resuelve sus 0252 y 0517, y la 0720 ya está. Queda
  la 0606. Propuesta: al cerrar F-162, reescribir F-053 para que sea solo la 0606.
- **D5 (abierta)** · tensión con F-106, que dice «el seguimiento de Ruesma lee solo fichas de la
  empresa 1»: F-162 lleva la 0252 y la 0517 a la ficha de su UTE, como ya están 0581, 0606 y 0671.
  Propuesta: F-162 manda hasta F-106, y F-106 lo apunta en su descripción.
- **D6 (aviso, no decisión)** · la 0721 entra en `mart` con sus reales (ámbitos 3 y 7), pero SIN
  versiones master: ninguna de sus líneas trae `planif`, y eso es F-161. Su presupuesto se ve en
  `stg.presupuesto` por el `obra_id` correcto. Conviene decírselo a Control de Costes.
