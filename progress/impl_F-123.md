<!-- progress/impl_F-123.md -->
# F-123 · Informe del implementer · la regla de orígenes del descompuesto

Rama `feature/F-123-descompuestos-regla-origenes`. Spec v2 aprobada por el humano
el 2026-10-02 (D1 y D2 según la recomendación). Rigor `estandar`. Alcance: T1-T12
y T19; T13-T18 son MANUAL del humano (al final, con su comando exacto).

## Precondición

`bash harness/init.sh` en verde ANTES de tocar nada: **6.252 passed, 219
skipped en 1.295 s**, `ENTORNO LISTO`.

## Qué cambió (T1-T7)

| Tarea | Commit | Fichero(s) | Cambio |
|---|---|---|---|
| T1 | `ee8fa3b` | `tests/test_f123_origenes.py` (nuevo) | 27 tests de R1-R21 (fase RED, abajo) |
| T2 | `9a4d390` | `domain/descompuestos.py`, `test_f097_planificador.py` | `ORIGENES` con `MASTER_ESTUDIO` en el sitio de `MASTER_INICIAL` |
| T3 | `020788b` | `sql/descompuestos/02_lineas_coste.sql` | `CHECK` nuevos en el DDL; bloque `DO` de migración (una guarda por tabla) tras los dos `CREATE` y antes del primer `DELETE`/`INSERT`; `NOT EXISTS` de versión 0 en `_versiones_cargadas` en el `INSERT` de `ESTUDIO`; cabecera (fase viva) |
| T4 | `4a0c779` | `03_lineas_master.sql` | `'MASTER_ESTUDIO'` en el `CASE` de `_atributos` y en el `IN` del `DELETE`; cabecera. **Sello nuevo `5c3fb64e292fa14d`** (antes `7cad480aee614b2a`) |
| T5 | `ed51bc7` | `04_elementos.sql`, `05_cuadre.sql` | `lineas_master_estudio` en el mismo sitio; en 05, `WHERE o.origen = 'PLANIF_JO' OR NOT EXISTS (versión 0)` tras los `LEFT JOIN` (DELETE, CTE y CASE intactos) |
| T6 | `db1539d` | `06_views.sql`, `build_descompuestos_step.py` | `v_pbi_master_estudio` al final, con las 21 columnas de `v_pbi_estudio` en su orden y `WHERE origen = 'MASTER_ESTUDIO'`; cabecera «las cuatro vistas»; docstring del paso |
| T7 | `e138fcb` | `test_f097_descompuestos.py`, `test_f120_factor.py` | `COLUMNAS_ELEMENTOS`, `VISTAS_POR_ORIGEN` (+`v_pbi_master_estudio`), el `CASE` y el `IN` de 03, el `WHERE` de 05, `r24` renombrado a `cada_vista_con_su_origen` (4 vistas); en F-120, la nota D7 (`r25`: «sin master 0», `MASTER_ESTUDIO`, sin el nombre viejo) y la versión (`r26`: `>= 39`). Ninguno se borra |

`MASTER_INICIAL` solo queda escrito en el SQL dentro del bloque `DO` de 02 (lo
fija `test_f123_r5`). `SUB_PASOS`, `FICHEROS_DEL_SELLO`, la ingesta, `00`/`01`,
el bloque `PLANIF_JO` y las otras tres vistas no se tocan (huellas del texto en
`test_f123_r3`/`r8`/`r10`).

## Fase RED (T1)

Comando: `python -m pytest tests/test_f123_origenes.py -q --tb=line -p no:cacheprovider`
con solo el test escrito (commit `ee8fa3b`, nada más cambiado). Traza real,
recortada a las líneas de error (la completa, en el scratchpad de la sesión):

```
...FFFFF.FFF.FFFFFFFFFFFFF.                                              [100%]
tests/test_f123_origenes.py:183: assert "CASE WHEN v.fase_num = 0 THEN 'MASTER_ESTUDIO' WHEN abc.fase_abc IS NOT NULL AND ... END AS origen" in " ON COMMIT DROP AS WITH fasamb AS ( ..."
tests/test_f123_origenes.py:197: ValueError: substring not found          (r5: no hay bloque DO)
tests/test_f123_origenes.py:205: AssertionError: assert ('ESTUDIO', '...ER_PLANIF_JO') == ('ESTUDIO', '...ER_PLANIF_JO')
tests/test_f123_origenes.py:212: assert "CONSTRAINT ck_lineas_origen CHECK (origen IN ('ESTUDIO', 'PLANIF_JO', 'MASTER_ESTUDIO', ..." in " origen TEXT NOT NULL, ..."
tests/test_f123_origenes.py:220: assert "COUNT(*) FILTER (WHERE origen = 'MASTER_ESTUDIO') AS lineas_master_estudio" in "DROP TABLE IF EXISTS descompuestos.elementos; ..."
tests/test_f123_origenes.py:247: AssertionError: assert ('WHERE NOT EXISTS (SELECT 1 FROM enlazadas e ...) AND ' + 'NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v WHERE v.obra_id = t.obra_id AND v.fase_num = 0)') in ', t.obra_id, ... FROM troceado t WHERE NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id)'
tests/test_f123_origenes.py:256: assert False                             (r10: 05 sin el filtro)
tests/test_f123_origenes.py:268: AssertionError: assert {'_des_texto'...'fn_num', ...} == {'_des_texto'...'fn_num', ...}
tests/test_f123_origenes.py:104: AssertionError: no encuentro «CREATE OR REPLACE VIEW descompuestos.v_pbi_master_estudio AS SELECT » en 06_views.sql
tests/test_f123_origenes.py:104: AssertionError: no encuentro «DO $$» en 02_lineas_coste.sql   (x3: r15 x2, r16)
tests/test_f123_origenes.py:321: ValueError: substring not found          (r15: DO antes del INSERT)
tests/test_f123_origenes.py:345: AssertionError: el literal vive en 03: el sello tiene que cambiar   ('7cad480aee614b2a' != '7cad480aee614b2a')
tests/test_f123_origenes.py:357: assert 39 == 40
tests/test_f123_origenes.py:367: AssertionError: R-DESCOMPUESTO-ORIGEN no dice «FASE VIVA»
tests/test_f123_origenes.py:376: AssertionError: MASTER_ESTUDIO           (esquemas.descompuestos)
tests/test_f123_origenes.py:137: KeyError: 'v_pbi_master_estudio'         (ficha nueva)
tests/test_f123_origenes.py:410: AssertionError: ARCHITECTURE.md no dice «`MASTER_ESTUDIO`»
tests/test_f123_origenes.py:420: AssertionError: la ayuda de build-descompuestos no dice «MASTER_ESTUDIO»
tests/test_f123_origenes.py:429: AssertionError: azure-apps no dice «F-123»
21 failed, 6 passed in 1.94s
```

Los 6 que pasaban en RED son los que fijan lo que NO cambia (R1, R2, R3, R8 por
huella del texto, R13) y el «un test por requisito». Verde, tarea a tarea:
T2 `-k dominio` 1 passed (+95 de `test_f097_planificador.py`); T3 `-k "migracion
or estudio or check"` 7 passed; T4 `-k "master or sello"` 3 passed; T5 `-k
"elementos or cuadre"` 3 passed; T6 `-k vistas` 2 passed; T7
`test_f097_*.py test_f120_factor.py`: 288 passed y 4 failed, los de diccionario
(`r27_fichas` y `r25` x3), que cierran en T9.

## T8 · Contraste en un PostgreSQL 16 desechable (nunca Azure)

PostgreSQL 16.4 local, `initdb` en el scratchpad, puerto 55434. **Contra Azure,
solo lecturas** (`BEGIN READ ONLY` + `statement_timeout`, 10 consultas, la más
lenta 47,5 s) para copiar la muestra: `_des_texto` del ámbito 3 entero y del
master de la 0713 y la 0726 (64.936 filas), `_versiones_cargadas` ENTERA (3.025,
170 versiones 0 en 197 obras: así el filtro «obra con master 0» es el real),
`raw.obrparpre` del ámbito 3 fase 0 y del master de las dos obras (247.989), los
45.442 `padide` de `obrparpar`, y `obrfasamb`/`conext`/`obr`/`dncpro`/`con`/
`auxpronat` de las dos obras. Primero el **estado de `main`** (los siete SQL de
F-120 por `git show main:`, sello `7cad480aee614b2a`); después
`BuildDescompuestosStep` de la rama DOS veces con `--sin-tope`:

```
ANTES (main):  ESTUDIO 99.049 lineas / 174 obras / 35.523 partidas   (= produccion, spec §2)
               MASTER_INICIAL 3.350 / 1 / 1.305 (la 0726: solo su master esta en la muestra)
               cuadre ESTUDIO 9.433 CUADRA / 20.786 NO_CUADRA / 113.428 SIN_DESC. / 5.923 SUSTITUIDO (= §2)
               ck_lineas_origen y ck_cuadre_origen con MASTER_INICIAL (oid 18456 / 18466)
               ESTUDIO en obras con version 0: 87.266 lineas
BUILD 1: SUCCESS 298141 64,8 s {"sello_troceado": "5c3fb64e292fa14d", "versiones_troceadas": 3025, "lotes": 7}
               ESTUDIO 11.783 / 44 / 6.544          MASTER_ESTUDIO 3.350 / 1 / 1.305
               cuadre ESTUDIO 2.710 / 2.654 / 45.739 / 103 (= 51.206)   MASTER_ESTUDIO 1.249 CUADRA / 202 SIN_DESC.
               CHECK sin MASTER_INICIAL (oid 18557 / 18558)   ESTUDIO en obras con version 0: 0
               parejas (obra, partida) con MASTER_ESTUDIO y ESTUDIO: 0        v_pbi_master_estudio: 3.350 filas
               0726 / 419079: MASTER_ESTUDIO v0 10 lineas 134,35 | MASTER_PRE_ABC v1 10 lineas 134,35 | ESTUDIO: ninguna
               0713: ESTUDIO 1.774 lineas / 687 partidas, MASTER_ESTUDIO: ninguna
               md5 iguales a ANTES: PLANIF_JO (lineas y cuadre), MASTER_PRE_ABC+MASTER_PLANIF_JO,
                 master 0 sin el origen, ESTUDIO de las obras sin version 0, _des_texto, huella de _versiones_cargadas
BUILD 2: SUCCESS 298141 8,9 s {"versiones_troceadas": 0, "lotes": 0}
               todo identico al BUILD 1; CHECK con el MISMO oid 18557 / 18558 (la migracion no vuelve a actuar)
IMAGEN VIEJA tras el codigo nuevo (03 de main, 0726 v0): CheckViolation ... "ck_lineas_origen"
```

- **La previsión de la spec (§3) sale EXACTA**: `ESTUDIO` 11.783 líneas, 44
  obras, 6.544 partidas; dejan de publicarse 87.266 (99.049 − 11.783); cuadre
  `ESTUDIO` 51.206 filas con el reparto previsto (2.710 / 2.654 / 45.739 / 103).
- **Migración una sola vez** (R15, R16): el oid de los dos `CHECK` cambia en el
  build 1 y no en el 2; cero filas `MASTER_INICIAL` tras el build 1.
- **Con tope** (segunda base, `presupuesto_mb` 1: 1 versión troceada y 3.024
  aplazadas en el build 1, 3.018 en el 2): la 0726 v0 sale ya como
  `MASTER_ESTUDIO` con su cuadre (1.249 / 202) aunque su versión siga con el
  sello viejo. Lo que se ve no depende del retroceo (design §5).
- **El riesgo del orden del despliegue es real**: el 03 de `main` contra el
  `CHECK` nuevo falla con `CheckViolation`. Imagen PRIMERO (T15).
- Límite de la muestra: el master solo está cargado para la 0713 (sin versión
  0) y la 0726, así que las cifras del master no son las de producción; las de
  `ESTUDIO` y su cuadre sí, porque el ámbito 3, `obrparpre` del ámbito 3 y
  `_versiones_cargadas` están enteros. Scripts y logs: `t8/` del scratchpad.

## T9-T11 · Diccionario, documentación y `azure-apps`

- **T9** (`41170ec`). `00_global.yaml`: `version` 40 con su entrada en la
  cabecera; `R-DESCOMPUESTO-ORIGEN` (D1, sin regla nueva) explica la FASE VIVA
  (coste fase 0, el presupuesto que el jefe de obra evoluciona día a día; su
  descompuesto es PLANIF_JO) y la regla de Estudios (MASTER_ESTUDIO en las obras
  con master 0, ESTUDIO solo en las que no; juntas, las dos vistas; «no existe»
  = SIN_DESCOMPUESTO), con la medición del 2026-10-02 en `motivo` y
  `v_pbi_master_estudio` en `ambito`; `esquemas.descompuestos` reescrito.
  `descompuestos.yaml`: cabecera (puntos 1, 3 y 7), fichas `lineas`,
  `cuadre_partida`, `elementos` (`lineas_master_estudio`), `v_pbi_estudio` y la
  nueva `v_pbi_master_estudio` (21 columnas, clave `obra_id, partida_id, orden`).
  El aviso de F-120 («precios de Estudios, medición ACTUAL») queda solo para
  las obras sin master 0; el ejemplo 0726 pasa a MASTER_ESTUDIO y el 0713 sigue
  en ESTUDIO. Sale el ejemplo 377070 «ESTUDIO SUSTITUIDO» y el 36,3 % de
  ESTUDIO que cuadraba: medían la regla vieja. `MASTER_INICIAL` solo queda en la
  historia de la cabecera de `00_global.yaml` (versión 37), que no se publica.
  Recuento del árbol: **190 objetos, 1437 columnas, 86 de consumo** (anotado en
  `current.md`, lo exige `test_f006_los_recuentos_de_current_son_los_de_hoy`).
- **T10** (`d158fc0`). `docs/ARCHITECTURE.md`: tabla de pestañas con
  `MASTER_ESTUDIO` y párrafo «La regla de Estudios (F-123)» (fase viva, por obra
  contra `_versiones_cargadas`, las dos vistas, la migración y el sello).
  `main.py`: ayuda de `build-descompuestos` («cuatro vistas», la regla, y que la
  imagen vieja falla contra el `CHECK` nuevo).
- **T11** (`8d49a5f` aquí; **`2288386` en `azure-apps`**, rama `master`, sin
  push). `datamart_seg_anual.md`: orígenes, `v_pbi_master_estudio` y un párrafo
  F-123 con lo que rompe y el orden del despliegue. Para el líder: dice aún
  «sin desplegar» de F-097 y F-120 (no es de esta feature; no lo toqué).

## T12 · Mutación

`python -m harness.mutacion --feature F-123` genera **CERO mutantes** (las 16
líneas Python son cadenas y docstrings; la lógica es SQL, que no muta). Campaña
MANUAL de 21 mutantes sobre cada línea de SQL cambiada y la tupla del dominio:
**21 muertos, 0 supervivientes**; sin `-x`, 1 worker, 96 s (base 5,7 s), HEAD
`8d49a5f93edde44217bdbaa162c8cf4c0a7927d3`. Pares exactos original -> mutado,
`fichero:línea` y nº de fallos de cada uno en `progress/mutacion_F-123.md`.

## T19 · `bash harness/init.sh` (HEAD `e293c34`)

`6285 passed, 221 skipped, 1682 warnings in 2378.23s (0:39:38)` · `PUERTA
COBERTURA: 100.0% de 1 líneas cambiadas (1/1)` · **`ENTORNO LISTO`**, exit 0.

## Desviaciones y decisiones

Ninguna desviación de la spec. Menores: una guarda `IF` por tabla en el `DO`;
los nombres de los tests esquivan los `-k` de las otras tareas; T12 manual.
Fuera de alcance (spec): medición de Estudios en `ESTUDIO`, «fase viva» en
`stg`/`mart`/`cierre`, fase 0 de venta y F-122.

## MANUAL del humano (T13-T18), EN ESTE ORDEN

- **T13** · Aviso a Juan Romero y Elena Díaz ANTES de desplegar, con el texto de
  `progress/spec_F-123.md` §5. Anotarlo en `current.md`.
- **T14** · Solo lectura, antes: `SELECT origen, count(*), count(DISTINCT
  obra_id), count(DISTINCT (obra_id, partida_id)) FROM descompuestos.lineas GROUP
  BY 1` y `SELECT origen, estado, count(*) FROM descompuestos.cuadre_partida
  GROUP BY 1, 2`. (Leído el 02-10 para T8: igual que spec §2.)
- **T15** · Merge a `main`, imagen con tag fechado y job apuntando a ella;
  comprobar ANTES de seguir: `az containerapp job show -g rg-datamart-seg-dev -n
  caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`.
  La imagen vieja contra el `CHECK` nuevo FALLA (visto en T8). **Sin vuelta
  atrás**: tras la migración, volver a la imagen anterior exige revertir antes
  los dos `CHECK` (y las filas `MASTER_ESTUDIO`); si no, `CheckViolation`.
- **T16** · Fuera de la nocturna, mirando los créditos de CPU, desde el MISMO
  commit: `python main.py build-descompuestos --sin-tope` y `python main.py
  apply-grants`. Debe salir SUCCESS, `versiones_troceadas` = las cargadas (3.025
  el 02-10) y `sello_troceado` **`5c3fb64e292fa14d`** si `00`/`01`/`03` llegan a
  `main` sin cambios (F-120 tardó 1.619 s). La primera vez la migración de `02`
  toma `AccessExclusiveLock` sobre `lineas` (~4,7 M filas, que el `ADD
  CONSTRAINT` valida) y `cuadre_partida` hasta el commit de `02`: el MCP y Power
  BI esperan; por eso va fuera de la nocturna (después, solo un `SELECT`).
- **T17** · Solo lectura, después: repetir T14. Debe dar (spec §3, confirmado
  en T8 para el ámbito 3): `ESTUDIO` 11.783 / 44 / 6.544; `MASTER_ESTUDIO`
  107.061 / 170 / 36.355; 0 filas `MASTER_INICIAL`; cuadre `ESTUDIO` 2.710 /
  2.654 / 45.739 / 103; cuadre `MASTER_ESTUDIO` = el de `MASTER_INICIAL` de antes
  (34.174 / 675 / 54.299); `PLANIF_JO` y el resto del master iguales. Testigos:
  `SELECT origen, fase_num, count(*), sum(importe_unitario) FROM
  descompuestos.lineas WHERE obra_id = 2817778 AND partida_id = 419079 GROUP BY
  1, 2` -> `MASTER_ESTUDIO` 0 10 134,35 y `MASTER_PRE_ABC` 1 10 134,35, sin
  `ESTUDIO`; `SELECT origen, count(*), count(DISTINCT partida_id) FROM
  descompuestos.lineas WHERE obra_id = 2645007 AND origen IN ('ESTUDIO',
  'MASTER_ESTUDIO') GROUP BY 1` -> solo `ESTUDIO` 1.774 687; R11: `SELECT
  count(*) FROM (SELECT obra_id, partida_id FROM descompuestos.lineas WHERE
  origen IN ('MASTER_ESTUDIO', 'ESTUDIO') GROUP BY 1, 2 HAVING count(DISTINCT
  origen) = 2) x` -> 0. Y la consulta de R24 por `psql` (spec §4).
- **T18** · `python main.py publicar-diccionario` contra Azure (versión 40) y
  reiniciar el MCP; comprobar `_meta.diccionario_publicacion` con la versión 40.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (`init.sh`, T19) | **6.285 passed, 221 skipped, 0 failed** (precondición: 6.252) |
| Tests nuevos de F-123 | 27 (`tests/test_f123_origenes.py`), 21 en rojo en la fase RED |
| Cobertura de líneas cambiadas | **100,0 % (1/1)**, `PUERTA COBERTURA` |
| Mutación del arnés | **0 mutantes generados** (solo cadenas y docstrings; sin informe del arnés) |
| Mutación manual sobre el SQL | **21 generados, 21 muertos, 0 supervivientes**; 96 s, **1 worker** (`progress/mutacion_F-123.md`) |
| Tiempo de la suite | **2.378,23 s** (39 min 38 s) |
| Contraste T8 (PG 16 local) | build 1 SUCCESS 64,8 s, build 2 SUCCESS 8,9 s; previsión §3 exacta; R11 = 0 |

Review 1 (CHANGES_REQUESTED, solo papeleo): atendidos en `mutacion_F-123.md`,
`current.md`, T15 y T16. Falta: review 2 y las MANUAL T13-T18.
