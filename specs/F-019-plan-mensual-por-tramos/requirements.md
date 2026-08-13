<!-- specs/F-019-plan-mensual-por-tramos/requirements.md -->
# F-019 · Build de stg.plan_mensual por tramos — Requisitos (EARS)

**Rigor: `critico`.** El sub-paso reescrito ejecuta SQL contra
`psql-albaranes-rs9k2`, servidor compartido que sirve a `albaranes` y
`partes` EN PRODUCCIÓN. El incidente del 2026-08-09 (disco al 93,4 %,
servidor en solo-lectura 10 minutos) es exactamente lo que esta feature
tiene que hacer imposible. Aplica CHECKPOINTS.md nivel `critico`: cero
mutantes supervivientes sin justificación aceptada y toda verificación
`MANUAL (humano)` con su comando exacto y su resultado real.

Convenciones de este documento:

- **[AUTO]** — verificable con pytest, sin red ni BBDD (fixtures/dobles).
  Nombre trazable `test_f019_rN_*`.
- **[MANUAL-local]** — la ejecuta el humano contra su PostgreSQL **local**
  (credenciales en `.env.local.bak`). Preferida sobre Azure siempre que el
  dato exista en local: cero riesgo para producción.
- **[MANUAL-Azure]** — la ejecuta el humano contra Azure. Solo las
  imprescindibles, y siempre vigilando `storage_percent`.
- `PSQL` = `& "C:\Program Files\PostgreSQL\16\bin\psql.exe"`. Recordatorio:
  **las opciones van ANTES de la cadena/parámetros de conexión**.

---

## Bloque 1 · Medir antes de tocar

### R1 · Mediciones previas en local [MANUAL-local]

El equipo debe disponer, ANTES de fijar las constantes del troceo (T2), de
estas mediciones tomadas sobre el PostgreSQL local (que ya tiene la carga
completa y el build actual funciona):

1. **Tamaño y cardinalidad del resultado final**: filas totales de
   `stg.plan_mensual`, filas por rama (master amb 8/11 vs reales amb 3/7) y
   tamaño físico de la tabla.
2. **Explosión de la rama master**: nº de filas explosionadas (suma de
   posiciones no vacías de `planif` de los presupuestos amb 8/11).
3. **Distribución por obra**: top 15 obras por peso (filas de
   `raw.obrparpre` que les tocan, distinguiendo master/reales) y el peso de
   la obra más pesada. Decide si el corte por obra puede equilibrarse.
4. **Derrame real del build actual**: delta de `temp_files`/`temp_bytes` de
   `pg_stat_database` antes y después de un `python main.py stage` local.
   Da el coeficiente KB-derramados/fila real, no estimado.

Verificación: MANUAL (humano). Comandos (usuario/BBDD de `.env.local.bak`):

```powershell
# 1 · resultado final
PSQL -h localhost -U <usuario> -d sigrid_dm -X -c "SELECT count(*) AS filas, count(*) FILTER (WHERE ambito_id IN (8,11)) AS filas_master, count(*) FILTER (WHERE ambito_id IN (3,7)) AS filas_reales, pg_size_pretty(pg_total_relation_size('stg.plan_mensual')) AS tamano FROM stg.plan_mensual;"

# 2 · explosión master
PSQL -h localhost -U <usuario> -d sigrid_dm -X -c "SELECT count(*) AS presupuestos_master, SUM(cardinality(string_to_array(op.planif,'|'))) AS posiciones_totales FROM stg.presupuesto pp JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id WHERE pp.ambito_id IN (8,11) AND op.planif IS NOT NULL AND length(trim(op.planif)) >= 1;"

# 3 · distribución por obra
PSQL -h localhost -U <usuario> -d sigrid_dm -X -c "SELECT pp.obra_id, count(*) AS filas, count(*) FILTER (WHERE pp.ambito_id IN (8,11)) AS filas_master, count(*) FILTER (WHERE pp.ambito_id IN (3,7)) AS filas_reales FROM stg.presupuesto pp JOIN raw.obrparpre op ON op.ide = pp.presupuesto_id WHERE pp.ambito_id IN (3,7,8,11) GROUP BY 1 ORDER BY 2 DESC LIMIT 15;"

# 4 · derrame del build actual (ANTES y DESPUÉS de `python main.py stage`)
PSQL -h localhost -U <usuario> -d sigrid_dm -X -c "SELECT temp_files, pg_size_pretty(temp_bytes) AS temp, temp_bytes FROM pg_stat_database WHERE datname = current_database();"
```

Los resultados se anotan en `design.md` §Mediciones (columna «medido») y en
el informe del implementer. Si contradicen las estimaciones (p. ej. una
obra sola pesa más que el tramo máximo propuesto), se recalculan las
constantes y se anota la corrección **antes** de seguir.

### R2 · Línea base de equivalencia [MANUAL-local]

ANTES de cambiar ningún fichero que afecte al build, el humano debe capturar
la huella del resultado del build **actual** en local:

```powershell
# checksum del contenido (excluye plan_id y _built_at, que cambian por diseño)
#
# CORREGIDO en T1 (2026-08-11): la formulación original agregaba las 29,09 M
# de filas en UNA cadena y Postgres la rechaza («memoria agotada»: una cadena
# no puede superar 1 GB). Se hashea por cubos: cada fila va a uno de 4.096
# cubos según su md5, se hashea cada cubo y se hashea la lista ordenada de
# hashes. Misma semántica (mismo conjunto de filas ⇔ mismo checksum) y es la
# fórmula que DEBE repetirse tal cual en R13.
PSQL -h localhost -U <usuario> -d sigrid_dm -X -A -t -c "SELECT sum(n) || '|' || md5(string_agg(h, '|' ORDER BY b)) FROM (SELECT substr(md5(fila), 1, 3) AS b, count(*) AS n, md5(string_agg(fila, '|' ORDER BY fila)) AS h FROM (SELECT concat_ws('~', presupuesto_id, obra_id, partida_id, ambito_id, version, version_descripcion, version_tex, version_fec_creacion, version_fec_efectiva, anio_mes, posicion_mes, pct_acumulado, pct_mes, precio_unitario, can_mes, can_origen, importe_mes, importe_origen, importe_mes_raw, importe_origen_raw, total_incurrido, total_incurrido_mes) AS fila FROM stg.plan_mensual) t GROUP BY 1) buckets;"

# huella de las vistas de consumo (herramienta de F-005)
python main.py fingerprint-views --out huella_local_antes_f019.csv
```

Verificación: MANUAL (humano). Ambos resultados guardados (el checksum,
anotado en el informe; el CSV, en el puesto — **no** se versiona).

---

## Bloque 2 · El troceo

### R3 · Partición completa por obra [AUTO]

CUANDO `build_stg` ejecuta el sub-paso `build_plan_mensual`, el sistema debe
calcular un **plan de tramos** que particione el conjunto de obras con
presupuesto en ámbitos 3/7/8/11: cada obra en exactamente un tramo, ningún
tramo vacío y la unión de tramos igual al conjunto total. El corte es por
`obra_id` porque **ninguna ventana del SQL cruza obras** (todas particionan
por `presupuesto_id` o por `(obra_id, partida_id, ambito_id)`), lo que hace
la equivalencia estructural, no casual.

Test: `test_f019_r3_plan_de_tramos_particiona_las_obras` (fixture de pesos
por obra; propiedad: disjuntos + cobertura total).

### R4 · Tramos acotados por peso configurable [AUTO]

El planificador de tramos debe empaquetar obras por su peso (filas
estimadas, ver design DA-1) sin que ningún tramo supere el máximo
configurado (`PG_TRAMO_MAX_FILAS`, default justificado con los números de
R1). SI una obra por sí sola supera el máximo, ENTONCES debe ir en un tramo
unitario y el sistema debe emitir un WARNING con su peso (no abortar: es el
mínimo físico posible).

Tests: `test_f019_r4_ningun_tramo_supera_el_maximo`,
`test_f019_r4_obra_gigante_va_en_tramo_unitario_con_warning`,
`test_f019_r4_maximo_configurable_desde_settings`.

### R5 · Plan determinista [AUTO]

CUANDO el planificador recibe los mismos pesos por obra y el mismo máximo,
el sistema debe producir exactamente el mismo plan de tramos (orden estable,
sin depender del orden de iteración de dicts ni de aleatoriedad).

Test: `test_f019_r5_plan_determinista`.

### R6 · El SQL filtra por obra en las DOS ramas [AUTO]

El fichero `08_plan_mensual.sql` debe contener el marcador de filtro de
tramo aplicado a la rama master (CTE `master_planif`) **y** a la rama reales
(CTE `reales_base`), y NO debe contener el `TRUNCATE` (que pasa a ejecutarlo
el step, una sola vez, antes del primer tramo). Un tramo que filtrara solo
una rama duplicaría o perdería filas: este requisito lo hace imposible de
regresar en silencio.

Tests (estáticos, leen el fichero sin BBDD):
`test_f019_r6_marcador_presente_en_ambas_ramas`,
`test_f019_r6_el_sql_ya_no_contiene_truncate`.

### R7 · Composición segura del filtro [AUTO]

CUANDO el sistema sustituye el marcador por la lista de obras del tramo,
debe componer el filtro exclusivamente con enteros validados. SI algún
identificador de obra no es un entero, ENTONCES debe fallar antes de enviar
nada a la BBDD. SI el marcador no está en el SQL (p. ej. alguien lo borra),
ENTONCES debe fallar con un mensaje explícito, nunca ejecutar el fichero sin
filtro.

Tests: `test_f019_r7_solo_enteros_en_el_filtro`,
`test_f019_r7_sin_marcador_falla_antes_de_ejecutar`.

---

## Bloque 3 · La puerta de disco

### R8 · Medición de ocupación antes de cada tramo [AUTO]

ANTES de ejecutar cada tramo (incluido el primero), el sistema debe medir la
ocupación del disco del servidor (suma de `pg_database_size` de todas las
bases frente a `PG_DISCO_TOTAL_GB`, ver design DA-2) y registrarla en el log
estructurado del tramo.

Test: `test_f019_r8_mide_ocupacion_antes_de_cada_tramo` (doble de
`PostgresClient` que cuenta las llamadas).

### R9 · Límite de seguridad: aborto limpio [AUTO]

SI la ocupación medida supera `PG_DISCO_LIMITE_PCT` (default 80 %,
configurable), ENTONCES el sistema debe: (1) NO ejecutar ese tramo ni los
siguientes, (2) dejar `stg.plan_mensual` **vacía** (TRUNCATE de limpieza:
nada de tabla a medias que un consumidor pueda tomar por completa),
(3) marcar el sub-paso FAILED en `_meta.etl_runs` con un mensaje que diga
ocupación medida, límite y tramo en el que paró, y (4) devolver
`StepStatus.FAILED` para que el pipeline no continúe a `build_mart`.

Tests: `test_f019_r9_supera_limite_aborta_sin_ejecutar_el_tramo`,
`test_f019_r9_aborto_deja_la_tabla_vacia_y_failed_en_meta`.

### R10 · Fail-safe de la medición [AUTO]

SI la medición de ocupación falla (error de permisos, excepción, valor no
disponible), ENTONCES el sistema debe abortar exactamente igual que en R9.
Continuar a ciegas —que es lo que hace el build actual— queda prohibido.

Test: `test_f019_r10_medicion_fallida_aborta_no_continua`.

### R11 · Transacción por tramo y fallo limpio [AUTO]

Cada tramo debe ejecutarse en su propia conexión/transacción (el patrón que
ya impone `PostgresClient.connection()`): el pico de temporales de un tramo
no se apila con el del siguiente. SI el INSERT de un tramo falla, ENTONCES
el sistema debe aplicar la misma limpieza de R9 (tabla vacía, FAILED en
`_meta`, sin tramos posteriores).

Tests: `test_f019_r11_cada_tramo_en_su_transaccion` (doble: una conexión
por tramo), `test_f019_r11_fallo_de_tramo_limpia_y_para`.

### R12 · Observabilidad por tramo [AUTO]

Por cada tramo ejecutado, el sistema debe emitir un log estructurado con:
índice del tramo y total (`3/14`), nº de obras, peso estimado, filas
insertadas reales (rowcount del INSERT, no COUNT de la tabla), duración y
ocupación medida antes del tramo. Además debe registrar cada tramo en
`_meta.etl_runs` (`build_stg.build_plan_mensual.tramo_NN`) para que
`python main.py timings` muestre el coste real por tramo — la medición del
paso 9 de F-005 sale de ahí.

Tests: `test_f019_r12_log_por_tramo_con_campos_obligatorios`,
`test_f019_r12_registro_en_meta_por_tramo`.

---

## Bloque 4 · Equivalencia funcional

### R13 · Resultado idéntico al build actual, en local [MANUAL-local]

CUANDO el build por tramos termina en local, `stg.plan_mensual` debe
contener exactamente las mismas filas que producía el build actual (mismo
checksum que R2, misma cardinalidad; `plan_id` y `_built_at` excluidos por
diseño). Y las vistas de consumo deben dar huella idéntica.

Verificación: MANUAL (humano):

```powershell
python main.py stage           # con .env apuntando a LOCAL
# repetir el checksum de R2: debe coincidir carácter a carácter
python main.py fingerprint-views --out huella_local_despues_f019.csv
python main.py compare-fingerprints huella_local_antes_f019.csv huella_local_despues_f019.csv
```

Resultado esperado: checksum idéntico y `compare-fingerprints` sin
diferencias. **Cualquier diferencia es FALLO**, no se racionaliza: se
investiga o se marca la feature `blocked`.

> **ENMENDADO en T11 (2026-08-13), opción C autorizada por el humano.** El
> checksum byte a byte resultó **insatisfacible por diseño** ante «filas
> gemelas»: `raw.obrfasamb` contiene versiones master duplicadas (mismo
> `(obride, amb, fas)`, ver
> `docs/referencia/05_caso_obrfasamb_version_duplicada.md`), cada posición
> de esas versiones sale dos veces, y las ventanas de `08_plan_mensual.sql`
> (`ROWS UNBOUNDED PRECEDING`, `LAG ... ORDER BY posicion_mes`) quedan
> subespecificadas en el empate: cada plan de ejecución reparte los pct
> entre las gemelas de forma estable pero distinta. El checksum medía ese
> orden, no el contenido. **Criterio enmendado**, verificado el 2026-08-13
> contra el build viejo reconstruido en un worktree (`2cb6de7`) sobre el
> MISMO `raw` congelado:
>
> 1. Misma cardinalidad (29.403.619 en ambos).
> 2. Ambos builds reproducibles consigo mismos (checksum estable ×2 cada
>    uno: viejo `ec74147e...`, nuevo `c58b928d...`).
> 3. `EXCEPT ALL` numérico de las 22 columnas en ambas direcciones: las
>    únicas filas discrepantes (10.259, un 0,035 %) son gemelas de las 2
>    obras del caso, y **por clave los multiconjuntos de valores son
>    idénticos** en todas las columnas de negocio: solo cambia el reparto
>    entre gemelas.
> 4. `compare-fingerprints` equivalente sin avisos.
>
> Con ese criterio, **R13 queda SUPERADO**: el troceo no cambia ningún
> valor. El desempate determinista de las gemelas es la feature F-022.

---

## Bloque 5 · Verificación en Azure (cierra el paso 8 de F-005)

### R14 · Relanzar el build completo contra Azure [MANUAL-Azure]

Con R13 en verde y la rama mergeada al árbol desde el que carga el humano,
el humano debe relanzar contra Azure (`.env` de Azure): `stage`,
`build-mart` y `apply-grants`, vigilando `storage_percent` durante la
ejecución. La ejecución debe terminar SUCCESS sin que la ocupación supere
`PG_DISCO_LIMITE_PCT`. Esto levanta la prohibición vigente («PROHIBIDO
relanzar stage contra Azure») **porque ya no es el mismo build**: ahora hay
tramos acotados y puerta de disco; aún así se lanza en horario acordado con
el humano (fuera de la ventana de uso de albaranes/partes).

Verificación: MANUAL (humano):

```powershell
# 0 · pre-check: la medición de ocupación funciona con el rol del ETL
#     (si fallara, la puerta R10 abortaría el build nada más empezar)
PSQL -h psql-albaranes-rs9k2.postgres.database.azure.com -p 5432 -U sigrid_dm_app -d sigrid_dm -X -c "SELECT pg_size_pretty(SUM(pg_database_size(datname))) FROM pg_database;"

# 1 · build por fases, anotando tiempos
python main.py stage
python main.py build-mart
python main.py apply-grants

# 2 · vigilancia de disco durante stage (repetir; o Portal → métrica storage_percent)
az monitor metrics list --resource psql-albaranes-rs9k2 --resource-group rg-albaranes-dev --resource-type Microsoft.DBforPostgreSQL/flexibleServers --metric storage_percent --interval PT1M --query "value[0].timeseries[0].data[-5:]"
```

Resultado esperado: los tres comandos SUCCESS, pico de `storage_percent`
anotado en el informe y por debajo del límite, y `python main.py timings`
con el desglose por tramo. Con esto queda completado el **paso 8 de F-005**
y medido el **paso 9** (veredicto sobre el B1ms con el build troceado).

### R15 · Huella local vs Azure [MANUAL-Azure]

CUANDO R14 termina, el humano debe comparar la huella de las vistas de
consumo de local contra Azure (paso 10 de F-005):

```powershell
python main.py fingerprint-views --out huella_azure_f019.csv   # .env Azure
python main.py compare-fingerprints huella_local_despues_f019.csv huella_azure_f019.csv
```

Resultado esperado: sin diferencias (misma semántica que R13: una
diferencia es FALLO).

### R16 · Desbloqueo de F-003 [MANUAL]

CUANDO R14 y R15 estén en verde y F-019 esté marcada `done`, el humano puede
poner `jobProgramable: true` en `infra/env/dev.json` (el test
`tests/test_f003_infra.py` solo lo permite con F-019 cerrada) y ejecutar la
tanda 2 de F-003 (T23–T26). Esta feature no toca ese fichero: solo deja las
condiciones cumplidas y constancia escrita.

Verificación: MANUAL (humano); pertenece operativamente a F-003.

---

## Bloque 6 · Salud del repositorio

### R17 · Suite sin red ni BBDD, init.sh en verde [AUTO]

Todos los tests `test_f019_*` deben ejecutarse sin abrir conexión a red ni a
BBDD (dobles de `PostgresClient`, fixtures de pesos, lectura estática del
SQL) y `bash harness/init.sh` debe terminar en verde con la cobertura y la
mutación que exige el rigor `critico`.

Verificación: `bash harness/init.sh`.

---

## Fuera de alcance

- Crecer el disco (opción A) o subir el SKU (opción C): descartadas por el
  humano el 2026-08-09.
- Optimizar el SQL de la explosión (reescritura algorítmica del planif):
  solo se añade el filtro de tramo; la lógica de negocio validada al céntimo
  NO se toca.
- La carga incremental (F-011) y la creación del job (T23 de F-003).
- Tocar `infra/env/dev.json` o cualquier fichero de F-003.
