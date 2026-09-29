<!-- specs/F-056-mayor-plan-contable/design.md -->
# F-056 · Diseño

Esquema nuevo **`contabilidad`**, construido por un paso propio
`build_contabilidad` que lee `raw` y el puente `maestro.centros_coste`. Tres
tablas: el plan de cuentas como árbol, el mayor (una fila por apunte) y los
saldos por cuenta y mes. Sin ingesta nueva: todo está en `raw` desde F-066.
Medidas y consultas: `progress/spec_F-056.md`.

## Lo que el dato es (medido el 2026-09-26, y corrige a la ficha)

- **El árbol no es el que decía F-066.** `con.tip = 16` son los **grupos** del
  plan (44.778, idénticos a la tabla `cug` de Sigrid, que no se ingiere) con
  códigos de 1 a 4 dígitos; `cua` son las **cuentas auxiliares** (`con.tip = 17`,
  34.196, todas de 10 dígitos) y las únicas con apuntes. Cinco niveles:
  grupo (1), subgrupo (2), cuenta (3), subcuenta (4), auxiliar (10).
- **El árbol es de prefijos, dentro de la empresa.** El 100 % de los grupos de
  2-4 dígitos tiene su prefijo como grupo en la misma empresa; ningún código se
  repite dentro de una empresa. El padre DECLARADO (`cug.padide`, leído en
  Sigrid por `sigrid-api`) coincide con el prefijo en el 100 % de los 34.369
  casos en que existe, pero falta en 10.088 grupos. En `cua.padide`: 33.838
  coinciden, **6 difieren** (empresas 12, 17, 18) y 352 están a 0 (335 tienen
  prefijo). Por eso el árbol va por prefijo y el declarado se publica aparte [D7].
- **La fecha**: `apu.fec` está en el 100 % y coincide con la del asiento
  (`con.fec`) en 2.166.404 de 2.166.701; las **297** que no (2017) llevan el
  último día del mes y el asiento el primero. Sigrid indexa el mayor por
  `cuefec` = (cuenta, `apu.fec`), así que la fecha del mayor es `apu.fec` [D6].
- **La empresa**: la de la cuenta y la del asiento coinciden en el 100 %. 38
  empresas con apuntes; la 1 tiene 1.948.503 (89,9 %). Las 15 sin apuntes en
  2025-2026 suman 79.792 (3,7 %) [D1].
- **La clase del apunte existe en origen** (`apu.cla`: 3 cierre, -1 apertura,
  1 regularización) **pero no siempre**: los cierres de 2020 y aperturas de 2021
  (8.960 filas) y 290 regularizaciones vienen con `cla = 0`, y 124 aperturas en
  mayúsculas escapan a un `LIKE`. De ahí la regla combinada de R18. Apertura =
  cierre previo en 52.409 pares cuenta-ejercicio; 2 no casan; **1.433 apuntes
  son saldo inicial** (1.315 de 2008 y los arranques de empresas nuevas).
- **Asientos descuadrados**: 3 de 788.047 (224,52 €). No es de esta feature
  medirlos: F-064.
- **Obra por `cenide`**: 54 % del total, pero por grupo del PGC: 6 → 90,3 %
  (425.520 de 471.188), 7 → 61,4 %, 4 → 46,8 %, 1-3 → casi nada. `apu.obr` en
  142 filas: vetado.
- **Tercero**: `apu.empide` en 1.030.078 apuntes (47,5 %), 998.686 de ellos a un
  proveedor (`con.tip = 5`). En los grupos 40 y 41, un 45-59 %.
- **`apa` es el mayor ANALÍTICO**: su cuenta es de `caa` (99,98 %), no de `cua`,
  y 83.587 filas cuelgan de un asiento analítico sin apunte financiero. [D4]
- **Caso testigo**: `1-4308000197` = AHORRAMAS, S.A., Retenciones (id 573009,
  padre 4308 «Clientes, retenciones»): 641 apuntes 2009-2026, saldo 1.189.275,13.
  Sumar sin excluir CIERRE da 7.742.538,38: la trampa, con cifra.
- **Contraste con Sigrid**: la subcuenta 434 de la empresa 1 en 2026 da un saldo
  de **5.345.557,80, idéntico** al de la captura de Juan Romero del 03-09.

## Ficheros a crear

- `etl_sigrid/infrastructure/postgres/sql/contabilidad/00_setup.sql` —
  `CREATE SCHEMA IF NOT EXISTS contabilidad` y `contabilidad.fn_fecha(BIGINT)`
  (misma forma que `retenciones.fn_sigrid_date`: 0/NULL/inválida → NULL).
- `.../contabilidad/01_plan_cuentas.sql` — `DROP TABLE IF EXISTS ... CASCADE` +
  `CREATE TABLE contabilidad.plan_cuentas AS` (R6-R12). Dos ramas en
  `UNION ALL`: grupos (`raw.con` tip 16) y auxiliares (`raw.cua` JOIN `raw.con`
  por `ide`). El padre por prefijo es un `LEFT JOIN raw.con` por
  `(emp, cod = left(...))` restringido a `tip = 16`; los ancestros, cuatro
  `LEFT JOIN` más por `left(cod, 1..4)`. Sin `WITH RECURSIVE`: la profundidad
  la fija la longitud del código, y no hay ciclo posible. PK `cuenta_id`, índice
  único `(empresa_id, codigo_cuenta)`, índice `(cuenta_padre_id)`.
- `.../contabilidad/02_mayor.sql` — `contabilidad.mayor` (R13-R24):
  - CTE `cierres` = `SELECT DISTINCT cueide, ejercicio` de los apuntes CIERRE
    (anti-join para SALDO_INICIAL, como F-095: un `NOT EXISTS` correlacionado
    no se hashea).
  - `raw.apu` JOIN `raw.con` asiento por `asiide` (PK), `LEFT JOIN
    contabilidad.plan_cuentas` por `cueide` (PK), `LEFT JOIN raw.con` tercero
    por `NULLIF(empide,0)` (PK), `LEFT JOIN maestro.centros_coste` por
    `NULLIF(cenide,0)` (única por construcción, F-073).
  - `saldo_acumulado` con `SUM(importe_saldo) OVER (PARTITION BY cuenta_id
    ORDER BY fecha, codigo_asiento, posicion, apunte_id)`.
  - PK `apunte_id`; índices `(empresa_id, codigo_cuenta, fecha)`,
    `(cuenta_id, fecha)`, `(asiento_id)`, `(obra_id)`, `(tercero_id)`.
  - Guarda final `DO $$` (R14): compara `count(*)` con `raw.apu` y hace
    `RAISE EXCEPTION` con las dos cifras (el troceador de `postgres_client`
    respeta `$$`: ya lo usa la guarda de `retenciones/05_fin_obra.sql`). Es una
    postcondición: si salta, la tabla queda escrita pero el paso sale `FAILED` y
    `R-FRESCURA` lo denuncia; no se construye en tabla auxiliar y se renombra.
- `.../contabilidad/03_saldos_cuenta_mes.sql` — `contabilidad.saldos_cuenta_mes`
  (R25-R26) por `GROUP BY cuenta_id, empresa_id, ejercicio, mes` sobre
  `contabilidad.mayor`, con `FILTER (WHERE clase_asiento = ...)` por columna y
  `saldo_acumulado` por ventana sobre las filas ya agregadas. PK
  `(cuenta_id, ejercicio, mes)` (la cuenta NULL del R16 se agrupa aparte con
  `COALESCE(cuenta_id, 0)`: una sola fila por empresa y mes, importe cero).
- `etl_sigrid/application/steps/build_contabilidad_step.py` — copia de la forma
  de `build_personal_step.py`: `SUB_PASOS` como dato a nivel de módulo
  (`setup`, `plan_cuentas`, `mayor`, `saldos_cuenta_mes`), `name =
  "build_contabilidad"`, `stage = "build_aux"`, `depends_on = ["ingest_raw"]`
  (no `build_maestros`, por el mismo motivo escrito en
  `build_retenciones_step.py`: la vista es SQL puro sobre `raw`).
- `config/diccionario/contabilidad.yaml` — tres fichas (R27-R28).
- `tests/test_f056_contabilidad.py` — la suite offline (R36), al estilo de
  `tests/test_f095_retenciones_contables.py`.

## Ficheros a modificar (la propagación, que es donde se olvidan cosas)

Lista de F-057 (`specs/F-057-recursos-empleados-partes/design.md` §propagación)
más lo que su T21 destapó:
- `main.py` — (a) comando `build-contabilidad`; (b) `BuildContabilidadStep` en
  `build_pipeline_steps` detrás de `BuildPersonalStep`; (c) docstrings de
  `run-all` y de `build_pipeline_steps` («cinco build» pasa a «seis»).
- `etl_sigrid/domain/diccionario.py` — `contabilidad` en `ESQUEMAS_DEL_DATAMART`.
- `config/settings.py` y `.env.example` — `contabilidad` en
  `DEFAULT_CONSUMPTION_SCHEMAS` / `PG_CONSUMPTION_SCHEMAS`.
- `config/diccionario/00_global.yaml` — entrada `esquemas.contabilidad`
  (`pasos_etl: [build_contabilidad]`), regla `R-SALDO-CONTABLE` (ámbito: los
  tres objetos; el saldo es `importe_saldo`/`saldo_acumulado`; CIERRE y APERTURA
  no se suman; en los grupos 6 y 7 la REGULARIZACION deja el ejercicio a cero),
  `version` 34 → 35 (o la siguiente libre al implementar).
- `config/diccionario/raw.yaml` — fichas `cua`, `asi`, `apu`, `apa` (R30).
- Tests con listas cerradas: `tests/test_f024_cli.py` (`STEPS_POR_COMANDO`,
  stage real `build_aux`), `tests/test_f047_nocturna.py` (composición exacta),
  `tests/test_f006_publicacion.py` (comandos que NO publican),
  `tests/test_f079_stg_consultable.py` (`GRUPO_B_FUNCIONES`:
  `contabilidad.fn_fecha`). Se comprueba con `pytest` completo, no se supone.
- `docs/ARCHITECTURE.md` — `contabilidad` en capas y en el diagrama de
  `run-all`; párrafo «el plan de cuentas son prefijos» y «clase de apunte».
- `CLAUDE.md` — la línea de `sql/` del mapa gana `contabilidad/`.
- `azure-apps/datamart_seg_anual.md` — el esquema expuesto (commit en ese repo).
- `harness/features.json` — nada más que el estado, por el flujo.

## Ficheros que NO se tocan

- `config/tables_sigrid.yaml` — no se ingiere nada (ni `cug`, D7; ni índices
  en `raw`: `raw.apu` solo tiene su PK y cada noche se recrea).
- `sql/retenciones/*` — F-095 clasifica sus 49.505 apuntes con una regla que,
  medida sobre ellos, da **0 diferencias** con la de R18. No se reescribe para
  leer de `contabilidad.mayor`: añadiría a `build_retenciones` una dependencia
  que hoy no tiene. Duplicación DECLARADA, propuesta aparte [D8].
- `sql/maestro/04_centros_coste.sql` y `06_cuentas_analiticas.sql`.
- `sql/stg/*`, `sql/mart/*`: el título dice «stg y mart» como CAPAS; aquí son
  un esquema módulo (el precedente es F-057: dentro de `build_stg` un fallo
  dejaría sin `mart` la noche, y los permisos se dan por esquema).
- `raw.apa` — no entra [D4].

## Riesgos y decisiones

**Decisiones abiertas para el humano** (recomendación en negrita):

- **D1 · Alcance por empresa.** (A) **las 38, con historia desde 2008**; (B) solo
  las 23 con apuntes en 2025-2026. B ahorra el 3,7 % y pierde la historia de
  UTEs y sociedades cerradas que F-058 necesita para estados por empresa y año.
- **D2 · Mayor materializado o vista.** (A) **tabla**: ~19 s de lectura medida
  (EXPLAIN ANALYZE del SELECT completo) más escritura e índices, estimado 2-5
  min por noche sobre las 4 h 07 de hoy y ~0,9 GB (base 27 GB de 64). (B) vista
  sobre `raw`: sin coste nocturno, pero `raw.apu` no tiene índice por cuenta:
  una cuenta ~1-2 s en caliente, cualquier agregado de empresa o año 8-20 s y
  en frío o con el B1ms sin créditos más que la ventana de 30 s del MCP
  (`R-COSTE-CONSULTA`), y el `saldo_acumulado` se calcula en cada consulta.
- **D3 · Objetos de consumo.** (A) **`plan_cuentas`, `mayor` y
  `saldos_cuenta_mes`**; (B) A + `v_saldos_arbol` (debe, haber y saldo por nodo
  del árbol y ejercicio: la vista de la captura de Juan). La recomendación deja
  B a F-058, porque el saldo de un nodo de los grupos 6-7 depende de si se
  quita la regularización, y eso es semántica de estado financiero.
- **D4 · `apa`.** (A) **fuera: va a F-061**, que pide los movimientos de las
  cuentas analíticas de contrapartida (167.135 filas de `apa`, 826 cuentas) y
  lo que los partes imputan; `apa` es analítica (`caa`), no el mayor financiero.
  (B) publicarla aquí como `contabilidad.mayor_analitico`. Con A, F-056 deja el
  enlace listo: `apa.apuide` → `mayor.apunte_id` (629.982 filas, 88 %).
- **D5 · Esquema nuevo.** (A) **`contabilidad`**, que exige añadirlo a la lista
  blanca de `mcp-bbdd` (`config/config.yaml`, otro repositorio, con despliegue
  de su imagen) o el MCP lo rechaza «fuera del ámbito»; (B) meterlo en un
  esquema ya visible, que mezcla dominios. Con A, este repositorio no toca
  `mcp-bbdd`: el informe deja escrito el cambio y lo lanza el líder allí.
- **D6 · Fecha.** **`fecha` = `apu.fec` y `fecha_asiento` por los dos saltos,
  las dos publicadas**. Cumple el criterio 2 de la ficha tal cual (la fecha del
  asiento por los dos saltos, como fecha real) sin publicar la del apunte como
  si fuera la misma; se propone reformular ese criterio con la cifra 297.
- **D7 · Árbol por prefijo, sin ingerir `cug`.** El declarado falta en el 22,5 %
  de los grupos y coincide con el prefijo donde existe; ingerir `cug` (44.778
  filas) solo serviría para publicar un padre incompleto. Revocable.
- **D8 · Convergencia con F-095.** Proponer una ficha para que
  `retenciones.apuntes_contables` lea la clase de `contabilidad.mayor`. No aquí.

**Alternativas descartadas**: `WITH RECURSIVE` para el árbol (no hace falta y es
el camino de los ciclos de F-052); índices en `raw.apu` (la ingesta la recrea y
es capa de origen); publicar `apu.obr` (142 filas); atribuir obra por la
cascada de F-095 (es de las cuentas de retención; generalizarla es F-058).

**Riesgos**: (1) coste real del paso sobre el B1ms — se mide (R35) y si pasa de
10 min se vuelve con cifra; (2) `saldo_acumulado` en tabla se reescribe entero
cada noche, que es lo esperado con `run-all --full`; (3) 294 apuntes sin cuenta
e importe cero se publican con la cuenta a NULL: `check-unicidad` no cuenta
claves NULL (F-108).

## Qué deja listo para las que dependen

- **F-058**: el grano cuenta × mes × empresa (`saldos_cuenta_mes`), la clase del
  asiento para quitar la regularización y el árbol con los ancestros por nivel
  para agregar balance (1-5) y resultados (6-7); obra por centro en el 90 % del
  grupo 6.
- **F-060**: `tercero_id` y la subcuenta del grupo 4 por empresa, con
  `saldo_acumulado` a cualquier fecha para el aging.
- **F-061**: `mayor.apunte_id` como destino de `apa.apuide` [D4] y el grupo 64
  por centro.
- **F-062**: 472/477/4751/476 por empresa y mes en `saldos_cuenta_mes`.
- **F-063**: grupos 62 y 64 por empresa y mes; la distinción analítica ≠
  contabilidad ya escrita en las fichas.
- **F-064**: `centro_coste_id` NULL, `clase_origen` y el asiento para medir
  descuadres (hoy 3).
- **F-091**: `asiento_id` en cada apunte; el puente `rac` es de F-091 y el mayor
  lo consume, no lo reconstruye.
