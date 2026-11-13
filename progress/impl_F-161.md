# F-161 · Informe del implementer (`estandar`)

Rama `feature/F-161-versiones-sin-reparto`, worktree `agent-a6aed2aa041e4084f`, base `64b7c92`
(mismo código de `etl_sigrid/` que `491fbf1`: `git diff --stat 491fbf1 HEAD -- etl_sigrid` vacío).

## Fase RED (T1)

Tests escritos ANTES del código. Comandos y salida real (2026-11-13):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f161_dominio.py -q
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.master_versiones'
ERROR tests/test_f161_dominio.py
1 error in 0.43s

$ .venv/Scripts/python.exe -m pytest tests/test_f161_sql.py tests/test_f161_diccionario.py -q
83 failed, 3 passed in 6.31s
```

Las 3 que pasan en RED son guardas de «no cambia» (D4), verdes por construcción:
`test_f161_r6_fuera_del_sello_y_de_la_ventana`, `test_f161_r10_el_resto_de_02_no_cambia` y
`test_f161_r20_ningun_objeto_nuevo_queda_pendiente`.

Trazas de los requisitos centrales:

```
$ pytest "tests/test_f161_sql.py::test_f161_r10_02_filtra_reparto_y_las_dos_fechas" --tb=short
E   AssertionError: assert 'SELECT obra_...siones_master' == 'SELECT obra_...a IS NOT NULL'
E     - sion_tex, tipo_master FROM mart.master_versiones_tipadas WHERE tiene_reparto AND version_fec_creacion IS NOT NULL AND version_fec_efectiva IS NOT NULL
E     + sion_tex, CASE WHEN version_tex IS NULL OR length(trim(version_tex)) = 0 THEN 'Sin clasificar' WHEN UPPER(version_tex) LIKE '%ABC%' ...

$ pytest "...::test_f161_r9_06_ya_no_construye_el_catalogo" "...::test_f161_r10_la_cuatrimestral_de_fin_obra_filtra_reparto" --tb=line
test_f161_sql.py:412: assert 'CREATE TABL...ones_tipadas' not in "DROP VIEW I... consulta.';"
E   assert "WHERE v.tipo_master = 'Cuatrimestral' AND v.tiene_reparto" in "SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral FROM mart.master_versiones_tipadas v WHERE v.tipo_master = 'Cuatrimestral' GROUP BY v.obra_id"

Errores agregados (83 fallos):
     23 AssertionError: no existe etl_sigrid\infrastructure\postgres\sql\mart\01b_master_versiones.sql
     19 AssertionError: 01_ddl.sql no crea stg.master_versiones
     12 AssertionError: no existe etl_sigrid\infrastructure\postgres\sql\stg\10_master_versiones.sql
      2 ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.postgres.master_versiones_sql'
      2 AssertionError: assert 'todas las versiones con lineas' in 'Una fila por (`obra_id`, ... y solo versiones con fecha efectiva resuelta.'
```

`tests/test_f161_sandbox.py` no tiene fase RED propia: sin `F161_SANDBOX_DSN` hace `skip`.

## Hecho

El catálogo de versiones master pasa a ser **completo**: toda versión de ámbito 8/11 con líneas
(fase >= 1) o con reparto temporal, con su grano verdadero y su marca `tiene_reparto`. Lo temporal
no cambia (D4): los tres consumidores (02, 06 y `retenciones/05`) filtran `tiene_reparto`. Se añade
el coste por partida y versión y la tabla mensual «último cierre frente a temporal» (D9, D10 a y b).

## Ficheros (commits `F-161 Tn`, base `64b7c92`, 28 ficheros, +2943/-192)

- `etl_sigrid/domain/master_versiones.py` (T2): `VersionMaster`, `tipo_master`, `clasificar_reparto`,
  `version_vigente(..., temporal=)`. Puro, sin dependencias.
- `sql/stg/01_ddl.sql` + `sql/stg/10_master_versiones.sql` (T4): `stg.master_versiones` (PK obra,
  ámbito, versión) y la vista `stg.v_master_lineas`.
- `steps/build_stg_step.py` (T5): sub-paso `build_master_versiones`, último y fuera del sello.
- `sql/mart/01b_master_versiones.sql` + `steps/build_mart_step.py` (T6): `mart.master_versiones_tipadas`
  (8 columnas de siempre + 9 nuevas), su vista, `mart.v_master_version_partida` y
  `mart.master_importe_mensual`. Nuevo sub-paso `master_versiones` entre ddl y build_fact.
- `postgres/master_versiones_sql.py` (T6): `CATALOGO_ANTERIOR` (sección 1 de 06 congelada en
  `491fbf1`) y `sql_comparacion_catalogo()` para la verificación de T13.
- `sql/mart/06_cp_tipologia.sql`, `sql/mart/02_build_fact.sql`, `sql/retenciones/05_fin_obra.sql` (T8):
  leen el catálogo único y filtran `tiene_reparto`; 06 ya no construye el catálogo.
- `config/diccionario/{00_global,stg,mart}.yaml` (T9): v77, fichas nuevas, R-VERSION-MASTER, P18.
- `docs/ARCHITECTURE.md`, `CLAUDE.md` (T10).
- Tests nuevos: `test_f161_dominio.py`, `test_f161_sql.py`, `test_f161_diccionario.py`,
  `test_f161_sandbox.py`. Adaptados (con su motivo en el propio test): `test_f078_sql.py`,
  `test_f157_step.py`, `test_f095_retenciones_contables.py`, `test_f110_fin_obra_cuatrimestral.py`,
  `test_f147_presupuesto_contexto.py`, y el inventario de `specs/F-006-mcp-azure/design_detalle.md`.

## Decisiones y desviaciones respecto a la spec

1. **`CASE WHEN p.obra_id IS NOT NULL THEN p.x ELSE c.y END` en lugar de `COALESCE`** (design §3) en
   los atributos de 10: con `COALESCE`, un NULL legítimo del plan se rellenaría con la cabecera y
   rompería R4 (las versiones con reparto conservan EXACTAMENTE los atributos de hoy). La sandbox lo
   cubre.
2. **`VersionMaster.fec_creacion`**: campo no listado en el design; hace falta para el filtro
   temporal de `version_vigente` (02 exige las dos fechas).
3. **R16 sobre meses <= mes del build**: D9 no genera meses futuros, así que la comprobación
   cruzada se hace en ese rango.
4. **`retenciones/05`**: divergencia teórica si una versión con reparto tuviera `fec_efectiva`
   NULL (hoy 0 casos; el test de F-110 veta las columnas de fecha en esa CTE). Se deja anotado.
5. **Sandbox**: se corrigió la expectativa de la v4 sin cabecera (commit `7c421a9`) y se añadió el
   caso de 06; ejecutada en un Postgres local desechable: 15 passed.
6. **Presupuesto de `contexto_bbdd`** subido 37.042 -> 37.356 caracteres (fichas nuevas), con su
   entrada de historia en `test_f147_presupuesto_contexto.py`.
7. **`consumo_recomendado: true`** en las fichas de `stg` nuevas, como exige F-079 para `stg`.
8. **azure-apps**: la edición de `azure-apps/datamart_seg_anual.md` la denegó el clasificador de
   permisos de la sesión; `git pull --rebase` allí dio «Already up to date» (402b082) y el repositorio
   quedó intacto. Queda MANUAL (abajo). Por eso falla `test_f161_r21_azure_apps_nombra_los_objetos`.
9. `FICHEROS_DEL_SELLO` y `TABLAS_ACOTADAS` sin tocar (R6).

## Tests (resultado real, 2026-11-13, sin `.env`)

- `test_f161_dominio.py` 33 passed; `test_f161_sql.py` 72 passed; `test_f161_diccionario.py`
  13 passed, 1 failed (r21 azure-apps, ver 8); `test_f161_sandbox.py` 15 passed con DSN local, skip sin él.
- Regresión dirigida: f110+f095 104 passed; f078 116 passed (+11 fallos de entorno, sin `.env`,
  preexistentes); f157_step 13; f019/f024/f025/f081 113; f157_diccionario 13; f147 contenido 61 y
  presupuesto 14; f149 14.
- Suite completa (2026-11-13, worktree sin `.env`): **116 failed, 13073 passed, 2552 skipped en
  1389,61 s**. Clasificación de los 116:
  - **3 causados por F-161, corregidos después** (tests adaptados con su motivo, autorizados por
    design «tests que fijan el texto movido»): `test_f097_r17_tipo_version_es_la_regla_de_mart` (la
    cascada vive ahora en `01b`), `test_f040_r30_sin_diff_en_retenciones_ni_tesoreria` (lista
    `TOCADOS_DESPUES` con `retenciones/05_fin_obra.sql` por R10; `tesoreria/` y el resto de
    `retenciones/` siguen intocables) y `test_f006_los_recuentos_de_current_son_los_de_hoy` (línea
    del diccionario v77 en `current.md`). Tras el cambio: f006_contexto+f040+f097 **82 passed, 1 skipped**.
  - **1 MANUAL**: `test_f161_r21_azure_apps_nombra_los_objetos` (ver decisión 8).
  - **112 de entorno** (sin `.env`: `SigridApiSettings` sin `base_url`/`function_key`, CLI con
    exit 1). Los 20 ficheros que los contienen, relanzados con `SIGRID_API_BASE_URL` y
    `SIGRID_API_FUNCTION_KEY` ficticios: **761 passed, 2 skipped en 107,44 s**.

## Pendiente MANUAL (líder o humano)

- **T3** (incluye O2 del review: medir la CTE `lineas`/`EXISTS` de `stg/10`): `EXPLAIN (ANALYZE)` en Azure, solo lectura, fuera de 00-05 UTC, de `CATALOGO_ANTERIOR` y del
  `SELECT` de `stg/10_master_versiones.sql` (sin el INSERT). PARAR si el nuevo supera en > 5 min (R19).
- **T7**: remedir en Azure (solo lectura) motivos y tabla §5.3, y cuántas versiones que entran son de tipo temporal (lo pide el review); `SELECT count(*)` del borrador de
  `master_importe_mensual`.
- **T10 (azure-apps)**: HECHO por el líder (`d6bb377` en azure-apps, sin push); r21 en verde.
- **T11**: HECHO (reviewer 15 passed; tras la pasada 1, 20 passed; ver abajo).
- **T12/T13**: design §8 pasos 0-5 (huellas antes, imagen, job puntual `--yaml`, comparar,
  `check-cp-tipologia` 0 diferencias, `sql_comparacion_catalogo()` 0 filas, v24 de la 0698 = 776
  filas / 2.107.662,97 €, R16, tiempos R19, publicar diccionario v77 con su imagen y reiniciar MCP).
- **T14**: `bash harness/init.sh` en la copia con `.env` (en el worktree da rojo por falta de `.env`).

## Review pasada 1: cambio requerido atendido (2026-11-13)

**Hallazgo**: ninguna versión sin reparto de la sandbox era de tipo temporal, así que R10/R16 no
podían fallar. **Cambio** (`8d02b31`, solo `tests/test_f161_sandbox.py`): v6 «PLANIFICACION
CUATRIMESTRAL MAR-26» (ámbito 8, `plafec` 0, `fec` 2026-03-15, una línea de 150 € sin `planif`),
posterior a la v2 (2026-02-10) y dentro de los meses del mensual; partida 4 de categoría CP en la v2
para que `fact_cp_tipologia` tenga planificado; y la sandbox ejecuta además `retenciones/05_fin_obra.sql`
(con `raw.obr`/`raw.con`/`raw.obrctr`/`cierre.fact_cierre_mensual` mínimos y `fn_sigrid_date` copiada
de `00_setup.sql`). Asertos nuevos: v6 Cuatrimestral/NINGUNO; el PLANIFICADO de la obra A es v1, v1,
v2, v2, v2 (nunca 6); `master_vigente_anual` 2026 = v2 y `fact_cp_tipologia` 2026 = 80,00 €; `fin_obra` =
(2, 2026-04-01, ULTIMO_CUATRIMESTRAL_MAS_1_MES); en 2026-03 `master_importe_mensual` da importe v6
Cuatrimestral y temporal v2. Ajustadas r1 (9 versiones) y r2 (línea con reparto de la partida 4).
Elegí marzo y no octubre (la propuesta del review) porque el mensual solo tiene meses hasta abril de
2026: con octubre, la mutación de `02` no habría tenido mes en el que ganar.

```
$ F161_SANDBOX_DSN=postgresql://postgres@127.0.0.1:55161/postgres pytest tests/test_f161_sandbox.py -q
20 passed in 2.47s
```

**Muerde** (cada mutación en una copia `git archive HEAD` del scratchpad, el árbol sin tocar; script
`muta_f161.sh`, Postgres 16 local desechable con `initdb` en el scratchpad, puerto 55161):

| Mutación (quitar `tiene_reparto`) | Resultado | Tests que caen |
|---|---|---|
| `mart/02_build_fact.sql:70` | 2 failed, 18 passed | r16, r10_d4_el_mensual… |
| `mart/06_cp_tipologia.sql:150` | 2 failed, 18 passed | r10_master_vigente_anual…, r10_d4_la_vigencia_anual_y_cp… |
| `mart/01b_master_versiones.sql:207` | 4 failed, 16 passed | r14 oráculo, r14 hoy, r16, r14_d4_en_marzo… |
| `retenciones/05_fin_obra.sql` (CTE `cuatrimestral`) | 1 failed, 19 passed | r10_d4_el_fin_de_obra… |

**Observaciones no bloqueantes**: no implementadas (ninguna es trivial sin tocar producción o el
diccionario publicado). O1 la decide el humano; O2 y la cuenta de temporales, añadidas a T3 y T7;
O3 (R16 hasta el mes del build) y O4 (`JOIN stg.partidas` interno), para el cierre; O6 (`n_lineas`
con `agregacion: suma`), menor, cambia el diccionario publicado.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados | suite completa 13073 passed / 116 failed (3 corregidos, 1 MANUAL, 112 de entorno que pasan con `SIGRID_API_*` ficticios) / 2552 skipped |
| Tests de F-161 | dominio 33, sql 72, diccionario 14 (r21 verde tras `d6bb377`), sandbox 20 con DSN local |
| Cobertura de líneas cambiadas | NO MEDIDA aquí: `init.sh` da rojo en el worktree sin `.env`; la línea `PUERTA COBERTURA` la toma el líder en T14 |
| Mutación | pendiente de la pasada de campaña (tras el APPROVED), como manda el protocolo |
| Tiempo de la suite | 1389,61 s (con otras dos tandas de pytest compitiendo en la máquina) |
| Capa e2e | N/A: ETL sin interfaz de navegador; la spec no marca requisitos `(capa: e2e)` |
| `bash harness/init.sh` | no ejecutado en verde aquí (sin `.env`, rojo esperado): T14 del líder |

Contenedor desechable `f161pg` (sandbox local): al terminar, Docker ya no estaba en marcha (`docker stop` sin daemon), así que no queda nada corriendo; si reaparece, `docker rm -f f161pg`.
