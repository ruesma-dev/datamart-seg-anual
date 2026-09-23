<!-- progress/impl_F-101.md -->
# F-101 · Informe del implementer (2026-09-23)

HOTFIX de F-057. Rama `hotfix/F-101-cabecera-del-parte`, rigor `estandar`. Spec
aprobada con D-3 (SI a `hmores.tex`), D-8 opcion A, D-9 (se publica
`precio_venta`) y D-1 (`obra_cabecera_id` / `centro_coste_cabecera_id`).
T1-T13 hechas, un commit por tarea (`F-101 T1` ... `F-101 T12`). Ficha en
`in_progress`; **no** se marca `done` (eso va tras el APROBADO del reviewer).

## Que cambio

| Fichero | Cambio |
|---|---|
| `sql/personal/00_setup.sql` | `personal.fn_fecha_serie(DOUBLE PRECISION)` (epoca 1899-12-30); DDL de `personal.partes` (16 col., indices `(obra_cabecera_id, anio, mes)`, `(codigo_parte)` NO unico, `(estado_id)`) y `personal.recursos_tipos_hora` (14 col., `(recurso_id)`, `(tipo_hora_id)`); `codigo_parte` y `texto_linea` en `partes_lineas`, en el CREATE y con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` |
| `sql/personal/02_partes_lineas.sql` | `codigo_parte` por `LEFT JOIN raw.con c ON c.ide = l.hmoide`; `texto_linea = NULLIF(l.tex, '')`. **Sigue sin nombrar `raw.hmo`** |
| `sql/personal/03_partes.sql` (nuevo) | La cabecera: `raw.hmo JOIN raw.con`, estado por el LATERAL de `conest` `tip = 35`, `activo`/`fecha_baja` con el vocabulario de `recursos`, `fecha_modificacion` por fecha serie, `num_lineas` y `lineas_en_otra_obra` |
| `sql/personal/04_recursos_tipos_hora.sql` (nuevo) | Una fila por `raw.reshor`; `LEFT JOIN raw.auxhor` y `raw.res`; `CASE medide` identico al de las lineas; sin `prenom`, `cuaide` ni `proide` |
| `sql/personal/03_views.sql` -> `05_views.sql` | `git mv`; solo cambia la cabecera con la ruta |
| `application/steps/build_personal_step.py` | `SUB_PASOS` de 4 a 6: `setup, recursos, partes_lineas, partes, recursos_tipos_hora, views`; las dos nuevas cuentan filas |
| `main.py` | Solo el docstring de `build-personal` (listaba `03_views.sql`) |
| `config/tables_sigrid.yaml` | `hmores.exclude_columns: []` con las cifras de D-3 en el comentario |
| `config/diccionario/personal.yaml` | Fichas `partes`, `recursos_tipos_hora`, `fn_fecha_serie`; columnas `codigo_parte` y `texto_linea` y relacion `parte_id -> personal.partes` en `partes_lineas`; relacion `recursos -> recursos_tipos_hora`; `version 1 -> 2` |
| `config/diccionario/00_global.yaml` | `version 27 -> 28` con su bloque; `para_que_sirve` de `personal` menciona los dos objetos |
| `config/diccionario/raw.yaml` | Ficha `raw.hmores`: 57 columnas y ya no dice «No se traen 1» (lo vigila `test_f006_r26_*`) |
| `tests/test_f101_cabecera_parte.py` (nuevo) | 51 tests `test_f101_rN_*`, R1-R30 |
| `tests/test_f057_personal.py` | Rutas `05_views.sql`, seis ficheros, cuatro recuentos (28 filas), `CREATE TABLE` x4 |
| `tests/test_f066_ingesta_raw.py` | `NUEVAS["hmores"] = (personal, ())`, como hizo F-074 con `prvcer` |
| Arreglos que cazo `init.sh` (T13) | `03_partes.sql`: `NULLIF(c.res, '')` (`test_f006_r2`); R-SIGRID-CON en `00_global.yaml`: `auxhor.cod` en el punto 3 y `reshor` en el punto 4 (solo 1 de 8.968 `ide` coincide con `con`, medido); ficha `partes.anio` sin erratas sueltas (`test_f006_r10`); `personal.fn_fecha_serie` en `GRUPO_B_FUNCIONES` de `test_f079`; enmienda de inventario a 161 en `specs/F-006-mcp-azure/design.md` y `design_detalle.md` |
| `azure-apps/datamart_seg_anual.md` | Commit **87dc629** en ese repo (sin push): 3 -> 5 objetos de `personal`, cuatro trampas nuevas, `hmores.tex` en «Que consume» |

## Decisiones y desviaciones (justificadas tambien en `progress/current.md`)

1. **`lineas_en_otra_obra` NO usa el LATERAL de design §4.1.** El diseno daba
   `raw.hmores` por «indexada por `hmoide`» y no lo esta: `pg_indexes` (solo
   lectura) solo tiene `hmores_pkey (ide)`. `EXPLAIN` sin ANALYZE del LATERAL:
   `Nested Loop` con `Seq Scan on hmores` por cada parte, **coste 119.752.314**.
   Se agrega una vez: subconsulta `GROUP BY l.hmoide` (con `raw.hmo hc` para la
   obra de cabecera) unida por hash, **coste 19.681**. Misma fuente
   (`raw.hmores`, no `personal.partes_lineas`), mismo resultado, sin crear un
   indice en `raw`. El test R10 se ajusto antes de escribir el SQL y veta el
   LATERAL.
2. **`00_global.yaml` ya estaba en 27** (merge de main): T11 fue 27 -> 28.
3. **`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`** para las dos columnas nuevas
   de `partes_lineas`: la nocturna del 23 ya creo la tabla y `CREATE TABLE IF
   NOT EXISTS` no la toca; sin el ALTER, el INSERT de la primera noche revienta.
4. **D-3 arrastra `raw.yaml` y `test_f066`**, que la spec no listaba: la ficha
   de `raw.hmores` decia que `tex` no se trae.
5. **El texto de la linea no cita el nombre medido** («un nombre y dos
   apellidos» en su lugar) en SQL ni en la ficha publicada: no se propaga un
   dato personal de origen a un fichero versionado ni al diccionario del MCP.
6. **Precios y conteos de `reshor` al dia de hoy**: 8.968 filas y 2.064
   recursos (la spec midio 8.959/2.063 el 22-23; son altas del dia). Las fichas
   citan la cifra de hoy con fecha.
7. `recursos_tipos_hora.recurso_id -> personal.partes_lineas.recurso_id` se
   declara `N:N` con el `porque` que explica la union por
   `(recurso_id, tipo_hora_id)` y los 17 pares repetidos (camino de M6).

## Lo medido (solo lectura)

Sigrid por `sigrid-api` (`leer_sql`), 2026-09-23. **T1: todas las cifras de
gobierno se reproducen**:

| Cifra | Spec | Hoy |
|---|---|---|
| `con.tip = 35` / codigos distintos | 6.886 / 6.258 | 6.886 / 6.258 |
| Codigos repetidos / partes afectados | 569 / 1.197 | 569 / 1.197 |
| `conest` tip 35 | 1 REG 647, 3 CER 541, 10 IMP 5.698 | identico |
| `hmo.feccie`/`cla`/`caaide` != 0; `reside` | 0/0/0; 6 | 0/0/0; 6 |
| `reshor` pares repetidos / con dos precios | 17 / 1 | 17 / 1 |
| `reshor.cuaide`/`proide` != 0; `pre`; `preven` | 0/0; 2.037; 3 | 0/0; 2.037; 3 |
| Lineas en otra obra / partes | 615 / 14 | 615 / 14 |
| `hmores.tex`: filas / bytes / max | 13.390 / 284.080 / 318 | identico |
| `reshor` sin `auxhor`; recursos con defecto sin fila | 3; 4 | 3; 4 |

Extra: `es_por_defecto` cierto en **2.032** filas; `hmo.cenide` casa en `cen`
537/537 y `hmo.obride` en `obr` 537/539 (la relacion a `maestro.obras` avisara
por cobertura parcial, no KO); 0 `hmo` sin `con` y 0 `con tip 35` sin `hmo`;
13 partes sin lineas; `con.fec = 0` en 1 parte (ninguna otra fuera de rango);
`hmo.obride = 0` en 41, `cenide = 0` en 47. Postgres (dev del `.env`):
`pg_indexes` y dos `EXPLAIN` sin ANALYZE en `READ ONLY` por
`filas_solo_lectura`; al construir el cliente corre su bootstrap idempotente
(`CREATE SCHEMA IF NOT EXISTS` sobre esquemas que ya existen), como en todo
comando del ETL. Tipos leidos de `INFORMATION_SCHEMA`: `con.tiemod float`,
`reshor.pre/preven/candef float`, `hmores.tex text`, `auxhor.fecbaj int`.
Scripts en el scratchpad de la sesion (`t1_*.py`, `pg_*.py`, `f101_fec.py`).

## Fuera del alcance

- **Usuario que crea el parte**: `dbo.log`, F-105 (declarado en la ficha).
- **D-8 opcion B** (`tipo_hora_defecto_id` en `personal.recursos`): no; la ficha
  declara los 4 recursos sin marca.
- **`prenom`**: no se publica (vetado por test sobre el texto ejecutable).
- `01_recursos.sql`, `objetos_pendientes.yaml` (sigue `[]`), grants, `mcp-bbdd`.

## Verificaciones MANUAL pendientes (humano; no ejecutadas aqui)

M1-M10 de `specs/F-101-cabecera-del-parte/tasks.md`, sin cambios. Dos matices:
- **M9 va ANTES que M1**: sin `ingest --table hmores --full` con la
  configuracion nueva, `raw.hmores` no tiene `tex` y `02_partes_lineas.sql`
  falla en `l.tex` (la ingesta anade la columna con `ADD COLUMN`, F-066). La
  nocturna lo hace sola en el orden correcto (`ingest` antes que
  `build_personal`); un `build-personal` a mano, no.
- **M5**: `es_por_defecto` cierto en 2.032 filas (no ~2.031), y 8.968 filas.
- M10 (`publicar-diccionario`, version 28) es escritura contra Azure: humano.

## Fase RED (trazas reales, commit 4233c72, antes de escribir SQL ni fichas)

Comando exacto:
`python -m pytest tests/test_f101_cabecera_parte.py -q -p no:cacheprovider --tb=line -W ignore`
Resultado: **`46 failed, 5 passed in 3.27s`**. Los 5 que ya pasaban son guardas
de lo que NO debe cambiar (veto de `raw.hmo` en las lineas R14, `personal` sin
dependientes R26, pendientes vacios R27, trazabilidad R29 y el `_ficha_de` de
`partes_lineas` que ya existia). Extracto de la salida (ruta recortada):

```
E   AssertionError: falta el CREATE TABLE de personal.partes
tests\test_f101_cabecera_parte.py:99: AssertionError: falta el CREATE TABLE de personal.partes
E   AssertionError: falta el indice \(obra_cabecera_id, anio, mes\) de personal.partes (R1)
etl_sigrid\infrastructure\postgres\sql\personal\03_partes.sql        [x14: AssertionError: SQL no encontrado]
E   AssertionError: `hmores.tex` entra desde F-101 (D-3) (R15)
tests\test_f101_cabecera_parte.py:322: AssertionError: `hmores.tex` entra desde F-101 (D-3) (R15)
E   AssertionError: la ficha de personal.partes_lineas no documenta texto_linea
E   AssertionError: falta el CREATE TABLE de personal.recursos_tipos_hora
etl_sigrid\infrastructure\postgres\sql\personal\04_recursos_tipos_hora.sql [x12: SQL no encontrado]
E   AssertionError: falta la ficha de personal.recursos_tipos_hora (R28)
E   AssertionError: assert ['00_setup.sq...03_views.sql'] == ['00_setup.sq...05_views.sql']
tests\test_f101_cabecera_parte.py:486: AssertionError: assert ['00_setup.sq...03_views.sql'] == ['00_setup.sq...05_views.sql']
E   AssertionError: assert None == 'tabla'                     (R27: inventario sin personal.partes)
E   AssertionError: falta la ficha de personal.partes (R28)
E   AssertionError: falta la ficha de personal.fn_fecha_serie (R28)
E   AssertionError: ['codigo_parte', 'texto_linea']            (R28: columnas sin ficha)
E   assert 1 == 2                                              (R28: version de personal.yaml)
E   AssertionError: `personal.partes` no esta en azure-apps (R30)
46 failed, 5 passed in 3.27s
```

Cada tarea se cerro con su subconjunto en verde (T3 `-k "ddl or r9 or r27"`
10/12 con las 2 de ficha aun rojas; T4 12/12; T5 5/7 con 2 de ficha; T6 61/61
con F-057; T7 F-057 58/58; T8 62/62; T9 722/722 con f006/f066/f074/f080; T10
27/28 con la de version; T11 108/109 con la de azure-apps; T12 51/51).
El test R10 se reescribio **antes** de cambiar el SQL (forma agregada, veta el
LATERAL) y el R4 al corregir `descripcion` (`NULLIF(c.res, '')`, exigido por
`test_f006_r2_un_nulo_declarado_tiene_que_ser_posible[personal.partes]`, que
cazo el primer `init.sh`: la ficha declaraba `nulo_significa` sobre un valor
que en crudo nunca es NULL).

## Evidencias

- **`bash harness/init.sh`** tal cual, 4.a pasada, en el arbol principal:
  **ENTORNO LISTO**. `[OK] pytest en verde`, `[OK] PUERTA COBERTURA: 94.7% de
  1022 lineas cambiadas cubiertas (968/1022, umbral 80%, nivel estandar)`,
  `[OK] PUERTA TAMANO` (requirements 137/150, design 236/250, impl 144/220 en
  esa pasada), `[OK] Rama actual`. Unico aviso: ruff, 232 (deuda previa).
  Las tres pasadas anteriores cayeron en rojo, una por fallo, y cada arreglo
  esta en su commit (tabla de arriba).
- **Tests**: **5.112 passed, 189 skipped, 0 failed**; de ellos, 51 son
  `test_f101_*` nuevos (R1-R30 cubiertos; lo comprueba el propio `test_f101_r29`).
- **Tiempo de la suite**: **1.204,06 s (20 min 04 s)**, el que imprime pytest
  dentro de `init.sh`.
- **Cobertura de lineas cambiadas**: 94,7 %. OJO: `init.sh` la mide contra
  `dev`, que va muy por detras de `main`; las 1.022 lineas incluyen cambios
  de otras features ya en `main` (misma cifra que midio F-094).
- **Mutacion**: `python -m harness.mutacion --feature F-101 --base main` ->
  **CERO MUTANTES** (exit 3): «el alcance tiene 38 linea(s) de produccion pero
  no se ha generado ni un mutante». Las 38 lineas son la tabla de datos
  `SUB_PASOS` (llamadas `_SubStep` con literales) y docstrings de
  `build_personal_step.py` y `main.py`: nada mutable. No hay
  `progress/mutacion_F-101.md` porque la herramienta no lo escribe con 0
  generados. El cambio real es SQL y YAML, que la campana no cubre; la
  evidencia sustitutiva es (a) los 51 tests sobre el texto del SQL y las
  fichas, con fase RED demostrada arriba; (b) los tests del step ejecutado
  contra un doble (`test_f101_r26_*`, `test_f057_r24_*`), que matan cualquier
  cambio de orden, nombre o destino de un sub-paso; y (c) las mediciones en
  solo lectura contra Sigrid y el `EXPLAIN` contra Postgres.
- **Lo que no se ha verificado aqui**: que los dos SQL nuevos corran contra una
  base (M1-M8). Construir `personal` escribe en el Postgres compartido: es del
  humano. El riesgo concreto es M9 antes que M1 (ver arriba).
