# F-157 · Diseño

Requisitos: `requirements.md`. Mediciones: `progress/spec_F-157.md`. Rigor `estandar`.

## 1. Encaje y límite del servicio

Es explotar en `stg` un dato que ya está en `raw` (`obrparpre.planif` de la fase 0 y
`obrfasamb.plafec`), igual que la rama master de `stg/08_plan_mensual.sql`. No hay ingesta
nueva, ni llamada nueva a `sigrid-api`, ni permisos nuevos: `stg` lo leen ya todos los perfiles
y `apply-grants` da `SELECT` por esquema (`azure-apps/datamart_seg_anual.md`). Cabe en el
límite de este ETL. Lo que NO es de aquí: convertir esa planificación en caja (F-140/F-150) o
en escenarios de Power BI (D8).

## 2. Ficheros a crear

- `etl_sigrid/infrastructure/postgres/sql/stg/09_plan_mensual_fase0.sql` — § 5.2.
- `etl_sigrid/domain/planif.py` — oráculo puro, § 4.
- `tests/test_f157_dominio.py`, `tests/test_f157_sql.py`, `tests/test_f157_step.py`,
  `tests/test_f157_diccionario.py` y `tests/test_f157_sandbox.py` (§ 10).

## 3. Ficheros a modificar

- `sql/stg/00_functions.sql`: `stg.fn_explotar_planif` (§ 5.1), al final del fichero.
- `sql/stg/01_ddl.sql`: la tabla y su vista de cobertura (§ 5.3), detrás de `plan_mensual`.
- `etl_sigrid/application/steps/build_stg_step.py`: `MARCADOR_FILTRO_FASE0 =
  "/*F157_FILTRO_OBRAS*/"`, `componer_sql_fase0(sql, obras)` (gemela de
  `componer_sql_presupuesto`: cuenta el marcador, sustituye y antepone
  `componer_borrado_derivado("plan_mensual_fase0", obras)`), `FICHEROS_DEL_SELLO` += `"09_…"`
  al final, el `_SubStep` nuevo tras `build_plan_mensual` y `_build_plan_mensual_fase0` (§ 6).
  Docstring de cabecera: añadir el 09 a la lista.
- `etl_sigrid/infrastructure/postgres/postgres_client.py`: `TABLAS_ACOTADAS` +=
  `"plan_mensual_fase0"` (entra así en el `VACUUM (ANALYZE)` de higiene y en
  `_exigir_tabla_acotada`).
- `config/diccionario/stg.yaml` (dos fichas nuevas, la de `plan_mensual` corregida) y
  `config/diccionario/00_global.yaml` (`R-IMPORTE-MES.ambito`, `version` 71 → 72 o la que
  toque, con su comentario de versión) — § 8.
- Tests que fijen `FICHEROS_DEL_SELLO`, `TABLAS_ACOTADAS` o la lista de sub-pasos de
  `build_stg` (buscar con `grep -rn "FICHEROS_DEL_SELLO\|TABLAS_ACOTADAS\|build_plan_mensual" tests`)
  y, si el presupuesto lo pide, `PRESUPUESTO_MAX` de `tests/test_f147_presupuesto_contexto.py`
  con su motivo.
- `docs/ARCHITECTURE.md` (semántica Sigrid: «fas=0 = Previsto … planif NO explosionada» pasa
  a decir que su `planif` va a `stg.plan_mensual_fase0`), `CLAUDE.md` (mapa, una línea) y
  `../azure-apps/datamart_seg_anual.md` (objeto, ~0,45 GB, minutos; commit local allí, sin push).

## 4. Ficheros que NO se tocan

- `sql/stg/08_plan_mensual.sql` (ni comentarios: está en el sello y en el contrato de
  `huella_obras.py`, marcadores `F042_*`), `06_presupuesto.sql`, `07_version_master_vigente.sql`.
- `sql/mart/`, `sql/cierre/` (sus seis `JOIN` de `pm.version` con `stg.fases.numero_fase` no
  ven la tabla nueva), `sql/tesoreria/07_devengo_pendiente.sql`, `sql/retenciones/`,
  `sql/maestro/`, `cp_tipologia_sql.py`, `huella_obras.py`, `mes_fase_sql.py`,
  `domain/tramos.py`, `domain/ventana.py`.
- `config/tables_sigrid.yaml` (las columnas ya se ingieren), `infra/`, `main.py` (el sub-paso
  vive dentro de `build_stg`: `run-all` y `stage` lo ejecutan sin cambios).

## 4 bis. Oráculo `etl_sigrid/domain/planif.py` (dominio, sin dependencias)

`explotar_planif(texto: str | None) -> list[PosicionPlanif]`, con `PosicionPlanif` dataclass
congelada `(posicion_mes: int, pct_acumulado: Decimal, pct_mes: Decimal)`. Pasos: partir por
`|` numerando desde 1; quitar las posiciones vacías (conservan su número: el «hueco» no
renumera, como `WITH ORDINALITY` + `WHERE length(trim(v)) > 0`); valor = `Decimal` si casa
`^-?\d+([.,]\d+)?$` (coma → punto) y si no `None`; aplicar la regla de R5 tratando `None` como
no positivo; `pct_mes` = acumulado − el de la posición conservada anterior (0 la primera).
`conservar(p) -> bool` = `not (acum == 0 and mes == 0) and acum <= Decimal("2.5")`.
Sin redondeos: `NUMERIC(18,6)` lo hace el SQL y los casos de prueba tienen ≤ 6 decimales.

## 5. SQL (capa `stg`)

### 5.1 `stg.fn_explotar_planif(p_planif TEXT)` en `00_functions.sql`

`RETURNS TABLE (posicion_mes INTEGER, pct_acumulado NUMERIC(18,6), pct_mes NUMERIC(18,6))
LANGUAGE sql IMMUTABLE PARALLEL SAFE`, `CREATE OR REPLACE`. Cuerpo = las CTE
`master_explosion` → `master_con_pct_mes` del 08 copiadas con las ventanas SIN `PARTITION BY`
(la función recibe un único `planif`), los mismos `CASE` en el mismo orden y el mismo regex.
Comentario de cabecera: «Esta es la regla del master de `08_plan_mensual.sql`; si cambia allí,
cambia aquí: lo vigilan `test_f157_sql.py` (mismos literales) y `test_f157_sandbox.py`
(mismo resultado)». No filtra (R6 lo aplica el 09) para que el sandbox compare todo.

### 5.2 `09_plan_mensual_fase0.sql`

Cabecera: qué construye, de qué lee (`stg.presupuesto`, `raw.obrparpre`, `raw.obrfasamb`), que
va acotado y de una pasada, y que no tiene ventanas (la equivalencia por tramos de F-019 vale
por construcción). Sin `TRUNCATE` ni `DROP`. Esqueleto:

```sql
WITH fa0 AS (                      -- R3: una fila por (obra, ámbito) fase 0, la de ide mayor
    SELECT DISTINCT ON (obride, amb) obride, amb, plafec
    FROM raw.obrfasamb
    WHERE fas = 0 AND amb IN (3, 7) AND plafec > 0
      AND obride = ANY (/*F157_FILTRO_OBRAS*/)
    ORDER BY obride, amb, ide DESC
), base AS (
    SELECT pp.*, op.planif,
           date_trunc('month', stg.fn_sigrid_date_to_date(fa0.plafec))::DATE AS mes_inicio
    FROM stg.presupuesto pp
    JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id
    JOIN fa0 ON fa0.obride = pp.obra_id AND fa0.amb = pp.ambito_id
    WHERE pp.ambito_id IN (3, 7) AND pp.fase_num = 0
      AND op.planif IS NOT NULL AND length(trim(op.planif)) >= 1
)
INSERT INTO stg.plan_mensual_fase0 (...)
SELECT ..., (b.mes_inicio + (e.posicion_mes - 1) * INTERVAL '1 month')::DATE, ...
FROM base b CROSS JOIN LATERAL stg.fn_explotar_planif(b.planif) e
WHERE NOT (e.pct_acumulado = 0 AND e.pct_mes = 0) AND e.pct_acumulado <= 2.5;
```

El marcador va en `fa0` y solo ahí: filtra por obra antes del `JOIN`, que va a `stg.presupuesto`
por `idx_pres_obra_amb`. Las fórmulas de importe y cantidad, literalmente las del `INSERT`
master del 08 (`ROUND((cantidad * pct_mes) * ROUND(precio::NUMERIC, dec_precios),
dec_importes)` y compañía), cambiando el origen del %.

### 5.3 DDL en `01_ddl.sql`

`CREATE TABLE IF NOT EXISTS stg.plan_mensual_fase0` con las columnas de R1 (tipos de
`plan_mensual`: `NUMERIC(18,6)` para %, `NUMERIC(20,6)` para precio y cantidades,
`NUMERIC(18,2)` para importes, `importe_partida NUMERIC(18,2)`), `PRIMARY KEY (obra_id,
ambito_id, partida_id, anio_mes)` —empieza por `obra_id`: sirve al borrado derivado— y
`CHECK (ambito_id IN (3, 7))`. Sin `BIGSERIAL`: la clave es la de negocio. Índice extra
`(anio_mes)` como `plan_mensual`. La vista `CREATE OR REPLACE VIEW
stg.v_plan_mensual_fase0_cobertura`: `stg.presupuesto` (fase 0, 3 y 7) `LEFT JOIN` el
agregado de la tabla por `presupuesto_id`, agrupado por `(obra_id, ambito_id)`; solo obras
con fase 0 en ese ámbito; `mes_inicio` = `MIN` de la tabla (NULL si no hay reparto).

## 6. El sub-paso en `build_stg_step.py`

`_SubStep("build_plan_mensual_fase0", "09_plan_mensual_fase0.sql", "stg",
"plan_mensual_fase0", acotado_fase0=True)` (campo nuevo, o un `tipo` si el implementer
prefiere no añadir booleanos; el despacho del bucle de `run` gana una rama).
`_build_plan_mensual_fase0(pg, sql_path)`: (1) obras = `self._obras_a_reconstruir()`; vacío →
log y `return 0` (R14); (2) puerta de disco: `pg.medir_ocupacion_disco_pct(total_gb)` contra
`disco_limite_pct`, mismo mensaje y misma excepción `PlanMensualAbortado` que la de los tramos
—extraer un `_puerta_de_disco(pg, contexto)` común si sale limpio, sin cambiar la conducta de
los tramos—; (3) `pg.execute_sql_text(componer_sql_fase0(...))`, una transacción; (4) log
`plan_mensual_fase0_acotado` con obras y filas; en la completa, `_denunciar_obras_sobrantes`
con la tabla nueva. NO escribe en `_meta.obra_build` (su frescura es la de la obra en esa
noche, § 11).

## 7. Por qué el `JOIN` de `cierre/` no corre riesgo

La tabla no tiene `version`: no hay nada que cruzar con `stg.fases.numero_fase`, y
`stg.plan_mensual` no gana ni pierde una fila. `test_f157_sql.py` busca `plan_mensual_fase0`
en todo `sql/` fuera de `stg/` y en los `.py` de `infrastructure/` (salvo el cliente y el step)
y exige cero apariciones (R19).

## 8. Diccionario

- `stg.plan_mensual_fase0`: `consumo_recomendado: true`, `clave_negocio` = la PK, `paso_etl:
  build_stg`, `refresco: nocturno`. Descripción en este orden: qué es (la pantalla
  «Planificación en el tiempo (por partidas)», fase 0 viva del jefe de obra, hoy y sin
  historia, no master ni cierre); solo partidas planificadas (coste ~86,5 % del importe,
  venta ~93,8 % del importe en las obras con reparto, con su fecha, y el resto en la vista);
  no se suma ni se une con `stg.plan_mensual`; el total de la partida es `importe_origen` de
  su último mes; frescura por `_meta.v_frescura_obra`. `ejemplos_preguntas`, primero las dos
  que enrutan: «¿cómo reparte por meses la venta prevista de la obra 0726?» y «compara mes a
  mes la planificación viva de venta con la del master vigente» (contra
  `mart.fact_seguimiento_mensual`, escenario `Venta Planificada`). Columnas: todas con
  `significado` y `agregacion` (`importe_mes` sumable entre meses; `importe_origen`,
  `importe_partida` y los % no).
- `stg.v_plan_mensual_fase0_cobertura`: grano `(obra_id, ambito_id)`, para «¿cuánto de la
  fase 0 está planificado?».
- `stg.plan_mensual`: en `version`, quitar «con `fas = 0` como el "Previsto" vivo» (aquí no
  hay filas de fase 0) y apuntar a la tabla nueva; una línea en la descripción.
- `R-IMPORTE-MES.ambito` += `stg.plan_mensual_fase0`. Sin regla nueva (D7 = A): el `resumen`
  no cambia. Ningún texto publicado cita una regla `fuera_mcp` (F-149).

## 9. Decisiones descartadas

- **D1 = B (versión 0 en `plan_mensual`)**: `mart/02_build_fact.sql` toma TODO el ámbito 3 como
  «Coste Real» y el 7 como «Venta Real» sin mirar `version`; `06_cp_tipologia.sql` calcula el
  último mes real con `MAX(anio_mes)` de ámbito 3 (saltaría a 2028); `check-cierres` exige que
  Σ `importe_mes` de una partida real sea su último cierre; `huella_obras` y `mes_fase_sql`
  leen 3 y 7. Hacerlo bien era tocar seis consumidores y el 08, que está en el sello y en la
  huella de F-042.
- **D2 = B (copiar las CTE en el 09)**: dos copias de la regla validada al céntimo. **D2 = C**:
  cambia la rama master; exige una huella de los 131 master y no lo pide nadie. Queda para otra
  feature, con la función ya probada.
- **D4 = B**: cuadra al céntimo pero rompe la comparación con el master, que es para lo que lo
  pide Juan. Los ≤ 0,03 € por partida son los mismos que el master tiene con Sigrid.
- **D5 = B o C**: B cuesta ~100 min de una noche; C (carga MANUAL de día) gasta créditos de CPU
  del servidor compartido con `albaranes` y `partes`.
- **D6 = B**: nadie lo ha pedido y la certificación no tiene master con el que compararla aquí.
- **D7 = B**: el aviso llega por la ficha del único objeto que lo necesita.

## 10. Tests de humo (sin red ni BBDD, salvo el sandbox opcional)

- `test_f157_dominio.py` (R5, R6, R8-R10): casos de R9, vacíos al final, no numéricos, negativos,
  `None`/cadena vacía → lista vacía, todo a cero → nada que conservar, > 2,5 descartado.
- `test_f157_sql.py` (R1-R4, R6-R8, R11, R13, R16, R18, R19): DDL con columnas, PK y `CHECK`;
  el 09 sin `TRUNCATE`/`DROP`/`PARTITION BY`, con `fas = 0`, `amb IN (3, 7)`, `ide DESC`, el
  marcador una vez y `fn_explotar_planif`; la función con los mismos `CASE`, regex y descarte que
  el 08 (comparando el texto normalizado de las expresiones); el 08 sin la cadena
  `plan_mensual_fase0`; el sello con el 09 al final; R19.
- `test_f157_step.py` (R12-R17): con `PostgresClient` simulado: orden de sub-pasos, borrado y
  `INSERT` en el mismo texto, plan vacío no ejecuta, marcador ausente o doble → `ValueError`,
  disco alto o sin medir → FAILED sin `execute_sql_text`, `record_run_end` con filas.
- `test_f157_diccionario.py` (R23, R24): fichas con las frases clave, `R-IMPORTE-MES`, versión.
- `test_f157_sandbox.py` (R5-R8, R22 sintético): con `F157_SANDBOX_DSN` (si no, `skip`), crea
  una base desechable como `test_f155_ofertas_compartidas.py`, carga `00_functions.sql`,
  compara la función con el oráculo en todos los casos y en 500 `planif` aleatorios con semilla,
  y ejecuta el 08 (rama master, ámbito 8) y el 09 (ámbito 7) sobre el MISMO `planif`: mismos %.
  El implementer lo corre en un PostgreSQL local desechable y deja la traza en su informe.

## 11. Riesgos

- **`plamed = 2`** (23 obras de coste, 18 de venta): la regla se validó en obras con `plamed = 0`.
  Si en esas el texto fuese medición y no %, el % final no sería 1: § 4 de las mediciones da
  1 en el 97 %, pero Juan lo contrasta en Sigrid en una obra con `plamed = 2` (§ 12, paso 5).
- **La pantalla de Sigrid no está documentada** (§ 8 de las mediciones): el cuadre lo hace
  Control de Costes en la 0726 (paso 5).
- Un fallo del sub-paso pone `build_stg` en FAILED, como cualquier otro: la puerta de F-024
  para `mart` esa noche. Es el último sub-paso y no lee nada nuevo de `raw`.
- Frescura: es la de `stg.presupuesto` de la obra; si el 09 fallase con el 08 bien, la fase 0
  quedaría un día atrás sin que `_meta.v_frescura_obra` lo diga (lo dice `timings`).
- Primera noche: completa por el sello (D5). Desplegar en sábado; si no, +~100 min.

## 12. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = `<PY> -c
"import main, sys; pg = main._get_pg(); pg._bootstrap_done = True;
print(pg.filas_solo_lectura(sys.argv[1], 300))" "<consulta>"`. La 0726 = `obra_id` 2817778;
los `obra_id` de 0696, 0677 y 0705 se sacan de `stg.obras` con `empresa_id = 1`.

0. Anotar el tag del job (`az containerapp job show -n caj-datamart-seg-dev -g
   rg-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`) y `git
   rev-parse main` (el 2026-11-05, antes del merge, `fbf43dd`). `<PY> main.py huella-obras
   --desde plan_obra --out antes_F157.csv`.
1. Sábado: `powershell -NoProfile -File infra/70_build_image.ps1` y `powershell -NoProfile
   -File infra/85_update_job.ps1 -Tag <tag nuevo>`; el `az` del paso 0 lo confirma.
2. Tras la nocturna del domingo: `<PY> main.py timings` (`build_plan_mensual_fase0` y la
   completa), `huella-obras --desde plan_obra --out despues_F157.csv` y comparar con el del
   paso 0 (R20); `check-cierres`, `check-unicidad --timeout 300`, `check-declarados` (R21).
   R22: `<Q>` con un `SELECT` que aplique `stg.fn_explotar_planif` (IMMUTABLE, solo lectura) a
   los `planif` master de 0696, 0677 y 0705 (`stg.presupuesto` ámbitos 8/11 + `raw.obrparpre`)
   y lo compare con sus filas de `stg.plan_mensual` por `(presupuesto_id, posicion_mes)` → 0.
3. Cifras: `<Q> "SELECT ambito_id, count(*), count(DISTINCT obra_id) FROM
   stg.plan_mensual_fase0 GROUP BY 1"` (R26) y, para la 0726, filas, meses, % final y Σ
   `importe_mes` por partida frente a `importe_partida`, y su fila de la vista (R25).
4. `<PY> main.py publicar-diccionario`, `check-diccionario` (0 avisos) y reinicio del MCP para
   vaciar su caché del diccionario (memoria «servidor MCP»).
5. Control de Costes: la 0726 (venta) y una obra con `plamed = 2` frente a la pantalla de
   Sigrid, tres partidas y dos meses cada una. Si no casa: vuelta atrás y `blocked`.
6. La nocturna del lunes: `timings` → `build_plan_mensual_fase0` ≤ ~5 min (R26).

**Vuelta atrás** (en este orden): (1) `infra/85_update_job.ps1 -Tag <tag del paso 0>`,
comprobado con el `az` del paso 0; (2) `git switch --detach fbf43dd` (o el SHA del paso 0); (3)
como `sigrid_dm_etl`: `DROP VIEW IF EXISTS stg.v_plan_mensual_fase0_cobertura; DROP TABLE IF
EXISTS stg.plan_mensual_fase0; DROP FUNCTION IF EXISTS stg.fn_explotar_planif(text);` —nada
más depende de ellas—; (4) `<PY> main.py publicar-diccionario` desde ese árbol y
`check-declarados` → OK. Con el sello de vuelta al de `fbf43dd`, la noche siguiente vuelve a ser
completa (~+100 min): avisar. `stg.plan_mensual` no se toca en ningún paso.
