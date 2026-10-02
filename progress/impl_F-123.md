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
  F-123 con lo que rompe a los consumidores y el orden del despliegue. **Aviso
  para el líder**: ese documento dice aún «sin desplegar» de F-097 y F-120, que
  según `current.md` están en producción desde la imagen `r20261002-0835`; no lo
  he tocado porque no es de esta feature y no lo he verificado.

## T12 · Mutación

`python -m harness.mutacion --feature F-123` genera **CERO mutantes** y no
escribe informe: las 16 líneas Python del alcance son cadenas y docstrings; la
lógica de F-123 es SQL, que el arnés no muta. Evidencia aportada de otra forma
y dicha por escrito: **campaña manual de 21 mutantes sobre cada línea de SQL
cambiada y la tupla del dominio: 21 muertos, 0 supervivientes, 241 s**. Detalle,
tabla y límites en `progress/mutacion_F-123.md`.

<!-- T19 en adelante -->
