<!-- progress/impl_F-120.md -->
# F-120 · Informe del implementer · el factor del descompuesto

Rama `feature/F-120-factor-descompuesto`. Rigor `estandar`. Alcance de esta
sesión: T1-T13 y T19. T14-T18 son MANUAL del humano (Azure), con su comando en
`progress/current.md`.

Precondición: `bash harness/init.sh` en verde al empezar (6.149 passed, 219
skipped, 23 min 40 s; cobertura N/A, la rama aún no cambiaba Python).

## T1 · Decisiones D1-D10 y lo que cambió respecto a la recomendación

Fuente: `progress/spec_F-120.md`, sección «APROBADA POR EL HUMANO (2026-10-01)»,
que manda sobre la spec donde difieren.

- **D1-D6 y D8: según la recomendación.** Sin cambios.
- **D7 REESCRITA** (líder, aprobada por el humano). La spec (R25, design §7 y el
  `acceptance` 5) dice «la foto fija de Estudios es MASTER_INICIAL»: es FALSO en
  general (en la 0713 la versión 0 no tiene descompuesto). Las fichas de
  `lineas`, `v_pbi_estudio` y `cuadre_partida` dicen lo aprobado: ESTUDIO tiene
  rendimientos y precios de Estudios pero su `cantidad_total` e `importe_total`
  siguen la medición ACTUAL; el importe de Estudios es medición × precio de la
  versión 0 (`stg.presupuesto`, ámbito 8, fase 0); lo que vale de ESTUDIO es el
  descompuesto por unidad; MASTER_INICIAL solo existe donde la versión 0 guarda
  descompuesto. Ejemplos: 0713 HORMIGÓN EN ESCALERAS (4.979,02 frente a
  5.376,84) y 0726 FORJ. RETICULAR 35+10 (527.564,24 frente a 527.584,96). El
  test de R25 exige el texto nuevo y PROHÍBE el viejo.
- **Añadido 1 (humano)**: el FACTOR explicado en las fichas (qué es, cómo viene,
  la fórmula, 1 sin factor, PLANIF_JO con `faccan`, las ~95.000 de campo vacío
  en F-122 y el ejemplo 1,22 × 0,003 × 339,39 = 1,24).
- **Añadido 2 (líder, aprobado)**: fuera el aviso caducado «EL MASTER ESTÁ
  INCOMPLETO HASTA LA PRIMERA CARGA» (la primera carga fue el 2026-09-29).
- **D9**: 9 líneas con factor en la 400854 v6 (el `acceptance` decía 7).
- **D10**: fuera de alcance, fichada como F-122.

Pendiente para el líder (no lo toca el implementer): el `acceptance` 5 de F-120
en `harness/features.json` aún dice «la foto fija de Estudios es MASTER_INICIAL».

## T2 · Fase RED (`tests/test_f120_factor.py`, antes de tocar código)

`python -m pytest tests/test_f120_factor.py -q -p no:cacheprovider` sobre `e65fe5a`:
**100 failed, 3 passed** (los 3 son guardas que ya se cumplían: R22, R23 y el
contador de requisitos). Los requisitos centrales, con `--tb=line`:

```
$ python -m pytest tests/test_f120_factor.py -q -p no:cacheprovider --tb=line -k "r13_la_400854 or r6_importe_unitario_lleva or r11_ or r1_r5_forma_del_campo_14 and (1.22x0.003 or 0.41) or r14_r16 or r12_troceado or r21_el_sello or r25_estudio_sigue and lineas"
tests/test_f120_factor.py:100: KeyError: 'factor_rendimiento'      (R6, R11, R13: el dominio no conoce el campo)
E   AttributeError: module 'etl_sigrid.domain.descompuestos' has no attribute 'PATRON_FACTOR_RENDIMIENTO'
E   AssertionError: assert 'CROSS JOIN LATERAL (SELECT CASE p.factip WHEN 1 THEN p.faccan::NUMERIC WHEN 0 THEN 1::NUMERIC END AS factor) f' in ', o.ide, p.paride, ... WHERE COALESCE(o.dncide, 0) <> 0 AND COALESCE(p.paride, 0) <> 0'
E   AssertionError: assert ('01_troceado...s_master.sql') == ('00_setup.sq...s_master.sql')
E   AssertionError: lineas: falta «medicion ACTUAL»
FAILED ...test_f120_r1_r5_forma_del_campo_14[0.41-factor0-rendimiento0]
FAILED ...test_f120_r1_r5_forma_del_campo_14[1.22x0.003-factor5-rendimiento5]
FAILED ...test_f120_r6_importe_unitario_lleva_el_factor
FAILED ...test_f120_r11_multiplica_sin_perder_precision
FAILED ...test_f120_r13_la_400854_v6_cuadra_al_centimo
FAILED ...test_f120_r12_troceado_usa_el_patron_literal_y_fn_num
FAILED ...test_f120_r14_r16_planif_jo_con_factip_y_faccan
FAILED ...test_f120_r21_el_sello_incluye_00_setup
FAILED ...test_f120_r25_estudio_sigue_la_medicion_actual[lineas]
9 failed, 94 deselected in 4.86s
```

Y lo que hace HOY el espejo con los 19 registros de la 400854 v6 (mismo `KeyError`
aparte: se troceó con el código de F-097 tal cual):

```
linea 13: None None
con factor sin importe: 9
suma importe_unitario: 190.69 (precio de la partida 249.41)
```

## T3-T7 · Código (un commit por tarea)

- **T3** `domain/descompuestos.py`: `_CUERPO_NUMERO` (`PATRON_NUMERO` conserva
  su texto exacto), `PATRON_FACTOR_RENDIMIENTO`, `factor_rendimiento()`,
  `POSICIONES["factor_rendimiento"]` (la 14), `RegistroDes.factor` y
  `_producto(*valores)` a 60 cifras (`PRECISION_PRODUCTO`, R11).
- **T4** `01_troceado.sql`: `DROP FUNCTION IF EXISTS` + `CREATE`, `factor` al
  final del `RETURNS TABLE`, una capa `f` que lee el campo 14 como texto y la
  `c` que lo parte con `fn_num` y el patrón literal; `importe_unitario` con
  `c.factor`. Cabecera: formato, el `DROP` y el orden de despliegue.
- **T5** `02_lineas_coste.sql`: `factor NUMERIC` al final del DDL + `ALTER TABLE
  ... ADD COLUMN IF NOT EXISTS factor NUMERIC` (sin `DEFAULT`); ESTUDIO con
  `t.factor`; PLANIF_JO con `CROSS JOIN LATERAL (SELECT CASE p.factip WHEN 1
  THEN p.faccan::NUMERIC WHEN 0 THEN 1::NUMERIC END AS factor) f` (sin `ELSE`:
  el 646 da NULL). Medido en `raw.dncpro` (solo lectura): `factip` 0 en
  246.673 líneas, 1 en 42.096, 646 en 1, ningún NULL.
- **T6** `03` inserta `t.factor`; `06` lo pone el último en las tres vistas.
- **T7** `FICHEROS_DEL_SELLO = ("00_setup.sql", "01_troceado.sql",
  "03_lineas_master.sql")`. Sello tras T7: `7cad480aee614b2a` (el de
  producción era `99f827a11969d59f`; cambiará con cualquier edición posterior
  de esos tres ficheros: el que vale es el que imprime el paso en T16).

Tests de F-097 que cambian con la spec (no son regresiones): `COLUMNAS_LINEAS`
+ `factor`; las dos aserciones de `importe_unitario` (01 y PLANIF_JO); el sello
con `00`; `POSICIONES` con `factor_rendimiento`; y (T10) el aviso de
«INCOMPLETO», que el añadido 2 retira. **Desviación menor**: la verificación de
T3 pide `test_f097_*.py` en verde, pero `test_f097_r13_las_posiciones_son_las_del_dominio`
compara `POSICIONES` con el SQL y no podía pasar hasta T4 (el diseño renombra
la clave en el dominio y el alias en el SQL). Quedó verde en T4. Un test mío
corregido tras la RED: en `r19` la cadena esperada del `SELECT` estaba mal
escrita (`c.base_porcentaje` en vez de `END AS base_porcentaje`).

## T8 · Contraste SQL frente a espejo (PostgreSQL 16 local y desechable)

`initdb` en el scratchpad, puerto 55433; nunca Azure. Muestra copiada de
`descompuestos._des_texto` de Azure en **solo lectura** (`BEGIN READ ONLY` +
`statement_timeout` 150 s, 8 consultas, la más lenta 27,9 s): el ámbito 3 entero,
la 0713 entera (10 versiones del master) y, del master de otras obras, los dos
raros, 150 filas con factor negativo, 100 con factor 0 y los tres extremos de §2.

```
filas de _des_texto: 62614 (43389 del ambito 3, 19624 de la 0713)
registros troceados: 171869 (Python) / 171869 (SQL); SQL en 16.3 s
formas del campo 14 en la muestra: {'numero': 132466, 'vacio': 33080, 'a x b': 5206,
  'a x -b': 254, 'factor 0': 330, 'a x (rend. vacio)': 106, 'raro': 7, 'factor negativo': 420}
filas con alguna diferencia: 0 | diferencias por columna: {}
```

**0 diferencias**, las 19 columnas de `RegistroDes` (con `factor`). Los raros
de la muestra: `0678.CDMA15` (2) y `1963589xF321886` (5). La 400854 v6 en el SQL
local: 19 líneas, **suma 249,41 = precio**, línea 13 = 1,24, y las 9 de forma
factor con factor y rendimiento (8 con factor distinto de 1).

## T9 · El build de la rama sobre un estado de F-097 (mismo PostgreSQL local)

Base nueva `prueba_f120b`: `raw` de juguete (`obrparpre` = las 62.614 filas de la
muestra, `obrparpar` vacío, `obrfasamb`/`conext` sintéticos para las 93
versiones, y 6 líneas de `dncpro` en la 400854 con `factip` 1, 0, 646, factor 0
y factor -1). Primero **el estado de F-097 con los SQL de `main`** (`git show
main:...`): `lineas` SIN `factor`, `fn_trocear` viejo, sello `99f827a11969d59f`.
Después `BuildDescompuestosStep` de la rama (`--sin-tope`), dos veces:

```
ESTADO F-097 (main): 400854 v6 [('NO_CUADRA', 249.41, 190.69)] | columna factor en lineas: 0 | versiones: 93
BUILD 1: SUCCESS 285704 27.1 s {"sello_troceado": "7cad480aee614b2a", "versiones_troceadas": 93, "lotes": 1}
  400854_v6: CUADRA 249.41 249.41 19 lineas | 9 con factor, rendimiento e importe
  ultima columna: lineas, v_pbi_estudio, v_pbi_planif_jo, v_pbi_master_planif_jo -> factor
  _des_texto igual: true | filas/bytes/huella/batch_id/cargada_at de _versiones_cargadas iguales: true
  PLANIF_JO (factor, rend., precio, imp. unit.): 1.00021 1 34.2 34.21 | 1 0.44 119 52.36 | NULL 1 2 NULL (646)
                                                0 1 5 0.00 | -1 1 10 -10.00 | 1.22 0.003 339.39 1.24
BUILD 2: SUCCESS 285704 20.4 s {"versiones_troceadas": 0, "lotes": 0}
  md5 de lineas y de cuadre_partida IDENTICOS a los del build 1
```

El `ALTER TABLE` funciona sobre la `lineas` de F-097, el `DROP FUNCTION` sobre
el `fn_trocear` viejo y `CREATE OR REPLACE VIEW` añade `factor` al final de las
vistas de F-097. Cuadre del master en la muestra: MASTER_PLANIF_JO NO_CUADRA
525 -> 3, MASTER_PRE_ABC 81 -> 0. (ESTUDIO no es comparable en esa foto: el
script cargó `_des_texto` después del `02` de `main`, así que el «antes» de
ESTUDIO salió vacío; tras el build, 20.682 NO_CUADRA, en línea con los 20.687
de producción: su causa es otra, §4 de la spec.)

## T10-T12 · Diccionario, documentación y `azure-apps`

- **T10** `descompuestos.yaml`: `factor` (último) en `lineas` y en las tres
  vistas; `rendimiento` «sin el factor», `importe_unitario` = factor x
  rendimiento x precio, `cantidad_total` «ya lleva el factor»; el FACTOR
  explicado con su ejemplo (añadido 1); la nota de ESTUDIO de D7 REESCRITA en
  `lineas`, `v_pbi_estudio` y `cuadre_partida` (texto aprobado, con la 0713 y la
  0726); fuera todo «INCOMPLETO» (añadido 2: `lineas`, `cuadre_partida`,
  `_versiones_cargadas`, `v_pbi_master_planif_jo` y la cabecera), con la fecha de
  la primera carga y cómo saber qué versión está. `fn_trocear` describe el factor
  y el sello. `00_global.yaml`: versión **39** con su entrada de historia.
  Árbol: 189 objetos, 1.416 columnas, 85 de consumo (anotado en `current.md`,
  lo exige `test_f006_los_recuentos_de_current_son_los_de_hoy`). F-006: 2.090
  passed, 216 skipped.
- **T11** `ARCHITECTURE.md`: campo 14 «factor x rendimiento», `00_setup.sql` en el
  sello, la duración medida de la primera carga y el orden de despliegue.
  `main.py`: ayuda de `--sin-tope` con 916,9 s medidos (fuera «sin medir») y la
  docstring de `build-descompuestos` con el factor.
- **T12** `azure-apps/datamart_seg_anual.md`: un párrafo con la columna `factor`,
  commit `20be0ce` en `azure-apps` (rama `master`, sin push).

## T13 · Campaña de mutación (`progress/mutacion_F-120.md`)

`python -m harness.mutacion --feature F-120 --base main --workers 2` sobre
`68e1223`: alcance 83 líneas (3 ficheros), **9 mutantes generados y evaluados**
(menos que el tope de 20: no hubo muestreo), **8 muertos, 1 superviviente**, 0
timeouts, 0 sin veredicto, 2.180,6 s; línea base 370,5 / 373,1 s, media 242,3 s
x 2 workers = 484,6 s por mutante. El superviviente (`PRECISION_PRODUCTO` 60 ->
61) es **equivalente justificado**: análisis en el informe de mutación. Un primer
intento con 4 workers salió «CAMPAÑA NO VÁLIDA» (la línea base de cierre agotó
sus 600 s con cuatro suites compitiendo; mismos 8/1): se descartó y no se usa.

## Qué queda fuera y qué falta para cerrar

- **MANUAL (humano), T14-T18**, con su comando exacto en `progress/current.md`
  y en su ORDEN: imagen (T14) -> foto del cuadre (T15) -> `build-descompuestos
  --sin-tope` + `apply-grants` (T16) -> la 400854 v6 y la foto de después (T17,
  R28-R29) -> `publicar-diccionario` v39 (T18). Sin push en ningún repositorio.
- Fuera de alcance: F-122 (campo 14 vacío con precio, ~95.000 líneas, y las
  ~310 partidas que dejan de cuadrar). Para el líder: el `acceptance` 5 de
  `features.json` aún dice lo de MASTER_INICIAL (ver T1).
- Nota de entorno: el scratchpad tenía un PostgreSQL de otra sesión en
  `pgdata`, levantado; lo paré para usar el puerto 55433 con uno nuevo
  (`pg120`), que también quedó parado al terminar.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests de la feature | **292 passed** (`test_f120_factor.py`, 103, y los cuatro `test_f097_*.py`), 2,3 s |
| Tests ejecutados (T19, `bash harness/init.sh`) | **6.252 passed, 219 skipped, 0 failed** |
| Cobertura de las líneas cambiadas | **100,0 %** (29 de 29; `PUERTA COBERTURA`, umbral 80 %) |
| Mutantes | **9 generados, 9 evaluados, 8 muertos, 1 superviviente** (equivalente justificado); SHA `68e1223` |
| Workers de la campaña | **2** (2.180,6 s; media 242,3 s x 2 = 484,6 s por mutante; línea base 370,5-373,1 s) |
| Tiempo de la suite | 11 min 22 s con cobertura (682,4 s, `init.sh`) |
| `bash harness/init.sh` final (T19) | **ENTORNO LISTO, exit 0**; tamaño impl 210/220 (medido sobre `5487cc2` + este informe) |
