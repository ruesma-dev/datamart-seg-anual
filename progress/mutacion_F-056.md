<!-- progress/mutacion_F-056.md -->
# F-056 · Campanas de mutacion (rigor critico: 0 supervivientes)

Dos campanas, porque el cambio es sobre todo SQL, que la herramienta no muta:

1. **La herramienta** (`python -m harness.mutacion --feature F-056 --base main
   --workers 2`) sobre el Python del alcance (215 lineas: el step nuevo,
   `main.py`, `settings.py`, `diccionario.py`). Genera **12 mutantes**, todos en
   `build_contabilidad_step.py` (las lineas de `main.py`, `settings.py` y
   `diccionario.py` son docstrings, llamadas y literales sin operador mutable).
2. **La SISTEMATICA de SQL y propagacion** que pidio el reviewer en F-095: los
   mutantes los genera un script (`campana.py`, scratchpad de la sesion, con el
   parser de F-095/F-110 ampliado a `UNION ALL`), no quien escribio los tests.

## 1 · Herramienta (Python)

| Métrica | Valor |
|---|---|
| Mutantes generados | 12 |
| Mutantes evaluados | 12 |
| Muertos | 12 |
| Supervivientes | 0 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 1961.6 s |
| SHA de HEAD medido | `7f71b1ea8999678b8f056df3112afb58e2e52a41` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-056_fab4ntf_/wk_0` | 395.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-056_fab4ntf_/wk_1` | 399.1 |
| Media por mutante evaluado (s) | 163.5 |
| Timeout efectivo por mutante (s) | 799 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | no: campaña completa |

Los 12, **muertos**. Cuatro de ellos (`exc_info=True`, `rows = 0`, `and`->`or`,
`round(.., 2)`) sobrevivieron en F-057 sobre el step gemelo (tres quedaron
declarados equivalentes y uno se mato alli con un test nuevo); aqui los matan los
tests de T21 (`test_f056_r3_el_log_de_cada_sub_paso`,
`..._el_log_del_fallo_lleva_la_traza`, `..._a_medio_configurar_no_cuenta_filas`)
y `slots`/`frozen` los mata `..._los_sub_pasos_son_dato_inmutable`. Una primera
pasada con 3 workers, en paralelo con la campana de SQL, dio tambien 12/12 pero
la herramienta la declaro NO VALIDA (la linea base de cierre agoto sus 600 s por
la contencion); esta es la repeticion sin nada mas corriendo.

## 2 · Campana sistematica (SQL y propagacion)

Recorre los tres `CREATE TABLE` de `sql/contabilidad/01`-`03` (todos sus
SELECT, CTE incluidos; cada rama del `UNION ALL` es su propio SELECT):

- **una por expresion proyectada** (-> `NULL`, conservando el alias; las `x.*`
  de los CTE intermedios no se mutan: no proyectan nada propio);
- **DISTINCT** quitado; cada **FILTER** quitado;
- **cada condicion** de nivel superior de cada `WHERE`;
- **cada JOIN**: su tipo cambiado (LEFT <-> INNER) y cada condicion de su `ON` a `TRUE`;
- **cada sentencia de DDL** de detras del CREATE (PK, unico, indices) quitada;
- la **guarda `DO $$`** del mayor: condicion a FALSE, IF quitado, prefijo
  `mayor: ` quitado y guarda delante del DROP;
- **32 semanticos de las reglas** (S1-S32: ILIKE->LIKE, orden de la clase,
  ejercicio anterior, signo del importe, particion y orden de las ventanas,
  prefijo del padre, UNION->UNION ALL, fn_fecha...) y **27 de propagacion**
  (P1-P27: step, `main.py`, esquemas de consumo, `ESQUEMAS_DEL_DATAMART`,
  fichero de provision, version, `R-FRESCURA`, `R-SALDO-CONTABLE`, claves y
  relaciones de las fichas, fichas de `raw`, ARCHITECTURE, CLAUDE.md).

Juez: `tests/test_f056_contabilidad.py` entero (sin `-x`, para contar fallos)
para lo de SQL; para la propagacion, ademas `test_f024_cli`, `test_f047_nocturna`,
`test_f047_steps`, `test_f057_personal`, `test_f079_stg_consultable`,
`test_f108_claves_alternativas`, `test_f006_formato`, `test_f006_frescura` y
`test_f006_publicacion`. Una COPIA por worker (`git archive HEAD`, con el
`.env` volcado al entorno del proceso y sin copiarlo), restaurando tras cada
mutante. El arbol del repositorio no se toca.

| Dato | Valor |
|---|---|
| SHA de HEAD medido | `3c67936dcfe5606749c483ef639126f7e85d4e07` |
| Workers | 4 |
| Linea base (bateria ampliada, por copia) | 188.4 s, 192.4 s, 248.8 s, 178.2 s (527 passed cada una) |
| Tiempo total | 2724.6 s (45.4 min) |
| Mutantes generados | **233** |
| Muertos en la primera pasada | **229** |
| Supervivientes en la primera pasada | **4** -> **0** tras la pasada 2 (abajo) |
| Timeouts / mortinatos | 0 / 0 |

Por tipo: DDL quitado 11, DISTINCT 1, FILTER 4, condicion del ON 21, condicion del WHERE 3, expresion 118, guarda: IF quitado 1, guarda: condicion 1, guarda: delante del DROP 1, guarda: sin nombre del sub-paso 1, semantico 59, tipo de JOIN 12.

### Los cuatro supervivientes de la primera pasada, y como se mataron

Todos de **propagacion documental** (ningun superviviente en el SQL, la guarda
ni el step). Rejuzgados con la bateria ampliada sobre `5150061` (base:
527 passed in 83.83s (0:01:23)):

| Id | Mutante | Por que vivia | Arreglo | Pasada 2 |
|---|---|---|---|---|
| P20 | `7.742.538,38` -> `7,74 M` en `contabilidad.yaml` | la PRIMERA aparicion estaba en el comentario de cabecera del YAML, que no se publica: mutante mal apuntado, equivalente | reapuntado a la ficha del mayor (`quitando solo los CIERRE da **7.742.538,38**`) | MUERTO (test_f056_r28_las_advertencias_con_cifra) |
| P24 | `raw.apa`: se quita «es F-061» | la ficha seguia diciendo F-061 en `motivo_no_consumo` | `test_f056_r30_*` exige F-061 y `contabilidad.mayor.apunte_id` en la DESCRIPCION | MUERTO |
| P25 | ARCHITECTURE: «son prefijos» -> «es un arbol» | el test buscaba la palabra `prefijo`, que seguia en el parrafo | el test busca la frase «El plan de cuentas son prefijos» | MUERTO |
| P26 | CLAUDE.md: `contabilidad/` fuera de la lista de capas | la frase nueva sobre `contabilidad/` lo seguia nombrando | el test busca `` `personal/`, `contabilidad/`, `auxiliar/` `` | MUERTO |

Tests reforzados en el commit `5150061`. **Saldo: 233 mutantes, 233 muertos, 0
supervivientes.**

### Equivalentes y notas

- **Ningun superviviente queda**: nada que declarar equivalente salvo el P20
  original (un comentario YAML no publicado), que se reapunto.
- **43 mutantes los mata SOLO el contrato expresion a expresion**
  (`test_f056_contrato_expresion_a_expresion`): son columnas que el SELECT
  final o un CTE pasan TAL CUAL (`s.apunte_id`, `n.nivel`, `m.ejercicio`...).
  Cambiarlas a `NULL AS <alias>` conserva el nombre; lo que no conserva es la
  formula, y eso es lo que fija el contrato (el mismo mecanismo que acepto el
  reviewer en F-095). Los valores que esas columnas transportan si tienen su
  test semantico aguas arriba (R15-R23, R25). Ids: 15, 16, 17, 18, 24, 25, 27, 29, 30, 98, 99, 100, 101, 102, 103, 105, 106, 107, 108, 112, 113, 114, 115, 116, 117, 118, 119, 120, 126, 141, 142, 143, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162.
- Los mutantes que dan 2 o mas fallos los mata ademas un test semantico.

## Tabla completa de la campana sistematica

| # | fichero:linea | tipo | original -> mutado | fallos | resultado |
|---|---|---|---|---|---|
| 1 | `01_plan_cuentas.sql:53` | expresion | `g.ide` -> `NULL AS ide` | 2 | MUERTO |
| 2 | `01_plan_cuentas.sql:53` | expresion | `g.emp` -> `NULL AS emp` | 2 | MUERTO |
| 3 | `01_plan_cuentas.sql:53` | expresion | `g.cod` -> `NULL AS cod` | 2 | MUERTO |
| 4 | `01_plan_cuentas.sql:55` | condicion del WHERE | `g.tip = 16` -> `TRUE` | 2 | MUERTO |
| 5 | `01_plan_cuentas.sql:58` | expresion | `e.numemp` -> `NULL` | 2 | MUERTO |
| 6 | `01_plan_cuentas.sql:58` | expresion | `MIN(e.res)` -> `NULL` | 2 | MUERTO |
| 7 | `01_plan_cuentas.sql:65` | expresion | `c.ide` -> `NULL` | 2 | MUERTO |
| 8 | `01_plan_cuentas.sql:66` | expresion | `c.emp` -> `NULL` | 2 | MUERTO |
| 9 | `01_plan_cuentas.sql:67` | expresion | `c.cod` -> `NULL` | 2 | MUERTO |
| 10 | `01_plan_cuentas.sql:68` | expresion | `c.res` -> `NULL` | 2 | MUERTO |
| 11 | `01_plan_cuentas.sql:69` | expresion | `c.fecbaj` -> `NULL` | 2 | MUERTO |
| 12 | `01_plan_cuentas.sql:70` | expresion | `LENGTH(c.cod)` -> `NULL` | 2 | MUERTO |
| 13 | `01_plan_cuentas.sql:71` | expresion | `NULL::INT` -> `NULL` | 2 | MUERTO |
| 14 | `01_plan_cuentas.sql:73` | condicion del WHERE | `c.tip = 16` -> `TRUE` | 2 | MUERTO |
| 15 | `01_plan_cuentas.sql:77` | expresion | `c.ide` -> `NULL AS ide` | 1 | MUERTO (solo contrato) |
| 16 | `01_plan_cuentas.sql:78` | expresion | `c.emp` -> `NULL AS emp` | 1 | MUERTO (solo contrato) |
| 17 | `01_plan_cuentas.sql:79` | expresion | `c.cod` -> `NULL AS cod` | 1 | MUERTO (solo contrato) |
| 18 | `01_plan_cuentas.sql:80` | expresion | `c.res` -> `NULL AS res` | 1 | MUERTO (solo contrato) |
| 19 | `01_plan_cuentas.sql:81` | expresion | `c.fecbaj` -> `NULL AS fecbaj` | 2 | MUERTO |
| 20 | `01_plan_cuentas.sql:82` | expresion | `5` -> `NULL` | 2 | MUERTO |
| 21 | `01_plan_cuentas.sql:83` | expresion | `NULLIF(cu.padide, 0)` -> `NULL` | 3 | MUERTO |
| 22 | `01_plan_cuentas.sql:85` | tipo de JOIN | `JOIN` -> `LEFT JOIN` | 3 | MUERTO |
| 23 | `01_plan_cuentas.sql:85` | condicion del ON | `c.ide = cu.ide` -> `TRUE` | 3 | MUERTO |
| 24 | `01_plan_cuentas.sql:88` | expresion | `n.cuenta_id` -> `NULL AS cuenta_id` | 1 | MUERTO (solo contrato) |
| 25 | `01_plan_cuentas.sql:89` | expresion | `n.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO (solo contrato) |
| 26 | `01_plan_cuentas.sql:90` | expresion | `em.empresa_nombre` -> `NULL AS empresa_nombre` | 2 | MUERTO |
| 27 | `01_plan_cuentas.sql:91` | expresion | `n.codigo_cuenta` -> `NULL AS codigo_cuenta` | 1 | MUERTO (solo contrato) |
| 28 | `01_plan_cuentas.sql:92` | expresion | `n.empresa_id::TEXT \|\| '-' \|\| n.codigo_cuenta` -> `NULL` | 2 | MUERTO |
| 29 | `01_plan_cuentas.sql:93` | expresion | `n.nombre_cuenta` -> `NULL AS nombre_cuenta` | 1 | MUERTO (solo contrato) |
| 30 | `01_plan_cuentas.sql:94` | expresion | `n.nivel` -> `NULL AS nivel` | 1 | MUERTO (solo contrato) |
| 31 | `01_plan_cuentas.sql:95` | expresion | `CASE n.nivel WHEN 1 THEN 'GRUPO' WHEN 2 THEN 'SUBGRUPO' WHEN 3 THEN 'CUENTA' WHE...` -> `NULL` | 2 | MUERTO |
| 32 | `01_plan_cuentas.sql:97` | expresion | `n.nivel = 5` -> `NULL` | 2 | MUERTO |
| 33 | `01_plan_cuentas.sql:98` | expresion | `LEFT(n.codigo_cuenta, 1)` -> `NULL` | 2 | MUERTO |
| 34 | `01_plan_cuentas.sql:99` | expresion | `pad.ide` -> `NULL` | 2 | MUERTO |
| 35 | `01_plan_cuentas.sql:100` | expresion | `n.cuenta_padre_declarada_id` -> `NULL AS cuenta_padre_declarada_id` | 2 | MUERTO |
| 36 | `01_plan_cuentas.sql:101` | expresion | `(n.cuenta_padre_declarada_id IS NOT NULL AND n.cuenta_padre_declarada_id IS DIST...` -> `NULL` | 2 | MUERTO |
| 37 | `01_plan_cuentas.sql:103` | expresion | `g1.ide` -> `NULL` | 2 | MUERTO |
| 38 | `01_plan_cuentas.sql:104` | expresion | `g2.ide` -> `NULL` | 2 | MUERTO |
| 39 | `01_plan_cuentas.sql:105` | expresion | `g3.ide` -> `NULL` | 2 | MUERTO |
| 40 | `01_plan_cuentas.sql:106` | expresion | `g4.ide` -> `NULL` | 2 | MUERTO |
| 41 | `01_plan_cuentas.sql:107` | expresion | `CONCAT_WS(' > ', g1.cod, g2.cod, g3.cod, g4.cod, CASE WHEN n.nivel = 5 THEN n.co...` -> `NULL` | 2 | MUERTO |
| 42 | `01_plan_cuentas.sql:109` | expresion | `contabilidad.fn_fecha(n.fecbaj)` -> `NULL` | 2 | MUERTO |
| 43 | `01_plan_cuentas.sql:110` | expresion | `COALESCE(n.fecbaj, 0) = 0` -> `NULL` | 2 | MUERTO |
| 44 | `01_plan_cuentas.sql:112` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 45 | `01_plan_cuentas.sql:112` | condicion del ON | `em.empresa_id = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 46 | `01_plan_cuentas.sql:113` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 47 | `01_plan_cuentas.sql:113` | condicion del ON | `pad.emp = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 48 | `01_plan_cuentas.sql:114` | condicion del ON | `pad.cod = CASE WHEN n.nivel = 5 THEN LEFT(n.codigo_cuenta, 4) WHEN n.nivel > 1 T...` -> `TRUE` | 2 | MUERTO |
| 49 | `01_plan_cuentas.sql:116` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 50 | `01_plan_cuentas.sql:116` | condicion del ON | `g1.emp = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 51 | `01_plan_cuentas.sql:116` | condicion del ON | `g1.cod = LEFT(n.codigo_cuenta, 1)` -> `TRUE` | 2 | MUERTO |
| 52 | `01_plan_cuentas.sql:117` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 53 | `01_plan_cuentas.sql:117` | condicion del ON | `g2.emp = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 54 | `01_plan_cuentas.sql:117` | condicion del ON | `n.nivel >= 2` -> `TRUE` | 2 | MUERTO |
| 55 | `01_plan_cuentas.sql:117` | condicion del ON | `g2.cod = LEFT(n.codigo_cuenta, 2)` -> `TRUE` | 2 | MUERTO |
| 56 | `01_plan_cuentas.sql:118` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 57 | `01_plan_cuentas.sql:118` | condicion del ON | `g3.emp = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 58 | `01_plan_cuentas.sql:118` | condicion del ON | `n.nivel >= 3` -> `TRUE` | 2 | MUERTO |
| 59 | `01_plan_cuentas.sql:118` | condicion del ON | `g3.cod = LEFT(n.codigo_cuenta, 3)` -> `TRUE` | 2 | MUERTO |
| 60 | `01_plan_cuentas.sql:119` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 61 | `01_plan_cuentas.sql:119` | condicion del ON | `g4.emp = n.empresa_id` -> `TRUE` | 2 | MUERTO |
| 62 | `01_plan_cuentas.sql:119` | condicion del ON | `n.nivel >= 4` -> `TRUE` | 2 | MUERTO |
| 63 | `01_plan_cuentas.sql:119` | condicion del ON | `g4.cod = LEFT(n.codigo_cuenta, 4)` -> `TRUE` | 2 | MUERTO |
| 64 | `01_plan_cuentas.sql:121` | DDL quitado | `ALTER TABLE contabilidad.plan_cuentas ADD PRIMARY KEY (cuenta_id);` -> (nada) | 1 | MUERTO |
| 65 | `01_plan_cuentas.sql:123` | DDL quitado | `CREATE UNIQUE INDEX uq_con_plan_empresa_codigo ON contabilidad.plan_cuentas (emp...` -> (nada) | 1 | MUERTO |
| 66 | `01_plan_cuentas.sql:124` | DDL quitado | `CREATE INDEX idx_con_plan_padre ON contabilidad.plan_cuentas (cuenta_padre_id);` -> (nada) | 1 | MUERTO |
| 67 | `02_mayor.sql:69` | expresion | `a.ide` -> `NULL` | 2 | MUERTO |
| 68 | `02_mayor.sql:70` | expresion | `a.asiide` -> `NULL` | 2 | MUERTO |
| 69 | `02_mayor.sql:71` | expresion | `asi.cod` -> `NULL` | 2 | MUERTO |
| 70 | `02_mayor.sql:72` | expresion | `a.pos` -> `NULL` | 2 | MUERTO |
| 71 | `02_mayor.sql:73` | expresion | `contabilidad.fn_fecha(a.fec)` -> `NULL` | 2 | MUERTO |
| 72 | `02_mayor.sql:74` | expresion | `contabilidad.fn_fecha(asi.fec)` -> `NULL` | 2 | MUERTO |
| 73 | `02_mayor.sql:75` | expresion | `asi.emp` -> `NULL` | 2 | MUERTO |
| 74 | `02_mayor.sql:76` | expresion | `NULLIF(a.cueide, 0)` -> `NULL` | 2 | MUERTO |
| 75 | `02_mayor.sql:77` | expresion | `a.res` -> `NULL` | 2 | MUERTO |
| 76 | `02_mayor.sql:78` | expresion | `a.doc` -> `NULL` | 2 | MUERTO |
| 77 | `02_mayor.sql:79` | expresion | `a.pun` -> `NULL` | 2 | MUERTO |
| 78 | `02_mayor.sql:80` | expresion | `a.cla` -> `NULL` | 2 | MUERTO |
| 79 | `02_mayor.sql:81` | expresion | `COALESCE(a.deb, 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 80 | `02_mayor.sql:82` | expresion | `COALESCE(a.hab, 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 81 | `02_mayor.sql:83` | expresion | `(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 82 | `02_mayor.sql:84` | expresion | `CASE WHEN a.cla = 3 OR a.res ILIKE 'asiento de cierre%' THEN 'CIERRE' WHEN a.cla...` -> `NULL` | 2 | MUERTO |
| 83 | `02_mayor.sql:88` | expresion | `NULLIF(a.cenide, 0)` -> `NULL` | 2 | MUERTO |
| 84 | `02_mayor.sql:89` | expresion | `NULLIF(a.empide, 0)` -> `NULL` | 2 | MUERTO |
| 85 | `02_mayor.sql:91` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 86 | `02_mayor.sql:91` | condicion del ON | `asi.ide = a.asiide` -> `TRUE` | 3 | MUERTO |
| 87 | `02_mayor.sql:96` | expresion | `EXTRACT(YEAR FROM ap.fecha)::INT` -> `NULL` | 2 | MUERTO |
| 88 | `02_mayor.sql:97` | expresion | `EXTRACT(MONTH FROM ap.fecha)::INT` -> `NULL` | 2 | MUERTO |
| 89 | `02_mayor.sql:103` | DISTINCT | `DISTINCT` -> (nada) | 3 | MUERTO |
| 90 | `02_mayor.sql:103` | expresion | `f.cuenta_id` -> `NULL AS cuenta_id` | 2 | MUERTO |
| 91 | `02_mayor.sql:103` | expresion | `f.ejercicio` -> `NULL AS ejercicio` | 2 | MUERTO |
| 92 | `02_mayor.sql:105` | condicion del WHERE | `f.clase_bruta = 'CIERRE'` -> `TRUE` | 2 | MUERTO |
| 93 | `02_mayor.sql:110` | expresion | `CASE WHEN f.clase_bruta = 'APERTURA' AND ci.cuenta_id IS NULL THEN 'SALDO_INICIA...` -> `NULL` | 2 | MUERTO |
| 94 | `02_mayor.sql:113` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 95 | `02_mayor.sql:113` | condicion del ON | `ci.cuenta_id = f.cuenta_id` -> `TRUE` | 3 | MUERTO |
| 96 | `02_mayor.sql:113` | condicion del ON | `ci.ejercicio = f.ejercicio - 1` -> `TRUE` | 3 | MUERTO |
| 97 | `02_mayor.sql:118` | expresion | `CASE WHEN c.clase_asiento IN ('CIERRE', 'APERTURA') THEN 0::NUMERIC(18, 2) ELSE ...` -> `NULL` | 2 | MUERTO |
| 98 | `02_mayor.sql:123` | expresion | `s.apunte_id` -> `NULL AS apunte_id` | 1 | MUERTO (solo contrato) |
| 99 | `02_mayor.sql:124` | expresion | `s.asiento_id` -> `NULL AS asiento_id` | 1 | MUERTO (solo contrato) |
| 100 | `02_mayor.sql:125` | expresion | `s.codigo_asiento` -> `NULL AS codigo_asiento` | 1 | MUERTO (solo contrato) |
| 101 | `02_mayor.sql:126` | expresion | `s.posicion` -> `NULL AS posicion` | 1 | MUERTO (solo contrato) |
| 102 | `02_mayor.sql:127` | expresion | `s.fecha` -> `NULL AS fecha` | 1 | MUERTO (solo contrato) |
| 103 | `02_mayor.sql:128` | expresion | `s.fecha_asiento` -> `NULL AS fecha_asiento` | 1 | MUERTO (solo contrato) |
| 104 | `02_mayor.sql:129` | expresion | `(s.fecha IS DISTINCT FROM s.fecha_asiento)` -> `NULL` | 2 | MUERTO |
| 105 | `02_mayor.sql:130` | expresion | `s.ejercicio` -> `NULL AS ejercicio` | 1 | MUERTO (solo contrato) |
| 106 | `02_mayor.sql:131` | expresion | `s.mes` -> `NULL AS mes` | 1 | MUERTO (solo contrato) |
| 107 | `02_mayor.sql:132` | expresion | `s.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO (solo contrato) |
| 108 | `02_mayor.sql:133` | expresion | `s.cuenta_id` -> `NULL AS cuenta_id` | 1 | MUERTO (solo contrato) |
| 109 | `02_mayor.sql:134` | expresion | `pc.codigo_cuenta` -> `NULL AS codigo_cuenta` | 2 | MUERTO |
| 110 | `02_mayor.sql:135` | expresion | `pc.nombre_cuenta` -> `NULL AS nombre_cuenta` | 2 | MUERTO |
| 111 | `02_mayor.sql:136` | expresion | `pc.clave_cuenta` -> `NULL AS clave_cuenta` | 2 | MUERTO |
| 112 | `02_mayor.sql:137` | expresion | `s.concepto` -> `NULL AS concepto` | 1 | MUERTO (solo contrato) |
| 113 | `02_mayor.sql:138` | expresion | `s.documento` -> `NULL AS documento` | 1 | MUERTO (solo contrato) |
| 114 | `02_mayor.sql:139` | expresion | `s.punteo` -> `NULL AS punteo` | 1 | MUERTO (solo contrato) |
| 115 | `02_mayor.sql:140` | expresion | `s.clase_origen` -> `NULL AS clase_origen` | 1 | MUERTO (solo contrato) |
| 116 | `02_mayor.sql:141` | expresion | `s.clase_asiento` -> `NULL AS clase_asiento` | 1 | MUERTO (solo contrato) |
| 117 | `02_mayor.sql:142` | expresion | `s.debe` -> `NULL AS debe` | 1 | MUERTO (solo contrato) |
| 118 | `02_mayor.sql:143` | expresion | `s.haber` -> `NULL AS haber` | 1 | MUERTO (solo contrato) |
| 119 | `02_mayor.sql:144` | expresion | `s.importe` -> `NULL AS importe` | 1 | MUERTO (solo contrato) |
| 120 | `02_mayor.sql:145` | expresion | `s.importe_saldo` -> `NULL AS importe_saldo` | 1 | MUERTO (solo contrato) |
| 121 | `02_mayor.sql:146` | expresion | `SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id ORDER BY s.fecha, s.codigo_...` -> `NULL` | 2 | MUERTO |
| 122 | `02_mayor.sql:150` | expresion | `s.centro_coste_id` -> `NULL AS centro_coste_id` | 2 | MUERTO |
| 123 | `02_mayor.sql:151` | expresion | `cc.obra_id` -> `NULL AS obra_id` | 2 | MUERTO |
| 124 | `02_mayor.sql:152` | expresion | `cc.codigo_obra` -> `NULL AS codigo_obra` | 2 | MUERTO |
| 125 | `02_mayor.sql:153` | expresion | `cc.empresa::TEXT \|\| '-' \|\| cc.codigo_obra` -> `NULL` | 2 | MUERTO |
| 126 | `02_mayor.sql:154` | expresion | `s.tercero_id` -> `NULL AS tercero_id` | 1 | MUERTO (solo contrato) |
| 127 | `02_mayor.sql:155` | expresion | `ter.res` -> `NULL` | 2 | MUERTO |
| 128 | `02_mayor.sql:157` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 129 | `02_mayor.sql:157` | condicion del ON | `pc.cuenta_id = s.cuenta_id` -> `TRUE` | 3 | MUERTO |
| 130 | `02_mayor.sql:158` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 131 | `02_mayor.sql:158` | condicion del ON | `cc.centro_coste_id = s.centro_coste_id` -> `TRUE` | 3 | MUERTO |
| 132 | `02_mayor.sql:159` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 3 | MUERTO |
| 133 | `02_mayor.sql:159` | condicion del ON | `ter.ide = s.tercero_id` -> `TRUE` | 3 | MUERTO |
| 134 | `02_mayor.sql:161` | DDL quitado | `ALTER TABLE contabilidad.mayor ADD PRIMARY KEY (apunte_id);` -> (nada) | 1 | MUERTO |
| 135 | `02_mayor.sql:162` | DDL quitado | `CREATE INDEX idx_con_mayor_empresa_cuenta_fecha ON contabilidad.mayor (empresa_i...` -> (nada) | 1 | MUERTO |
| 136 | `02_mayor.sql:163` | DDL quitado | `CREATE INDEX idx_con_mayor_cuenta_fecha ON contabilidad.mayor (cuenta_id, fecha)...` -> (nada) | 1 | MUERTO |
| 137 | `02_mayor.sql:164` | DDL quitado | `CREATE INDEX idx_con_mayor_asiento ON contabilidad.mayor (asiento_id);` -> (nada) | 1 | MUERTO |
| 138 | `02_mayor.sql:165` | DDL quitado | `CREATE INDEX idx_con_mayor_obra ON contabilidad.mayor (obra_id);` -> (nada) | 1 | MUERTO |
| 139 | `02_mayor.sql:166` | DDL quitado | `CREATE INDEX idx_con_mayor_tercero ON contabilidad.mayor (tercero_id);` -> (nada) | 1 | MUERTO |
| 140 | `03_saldos_cuenta_mes.sql:35` | expresion | `COALESCE(m.cuenta_id, 0)` -> `NULL` | 2 | MUERTO |
| 141 | `03_saldos_cuenta_mes.sql:36` | expresion | `m.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO (solo contrato) |
| 142 | `03_saldos_cuenta_mes.sql:37` | expresion | `m.ejercicio` -> `NULL AS ejercicio` | 1 | MUERTO (solo contrato) |
| 143 | `03_saldos_cuenta_mes.sql:38` | expresion | `m.mes` -> `NULL AS mes` | 1 | MUERTO (solo contrato) |
| 144 | `03_saldos_cuenta_mes.sql:39` | expresion | `COUNT(*)` -> `NULL` | 2 | MUERTO |
| 145 | `03_saldos_cuenta_mes.sql:40` | expresion | `SUM(m.debe)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 146 | `03_saldos_cuenta_mes.sql:41` | expresion | `SUM(m.haber)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 147 | `03_saldos_cuenta_mes.sql:42` | expresion | `COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento IN ('APERTURA', 'SALDO_INI...` -> `NULL` | 2 | MUERTO |
| 148 | `03_saldos_cuenta_mes.sql:43` | expresion | `COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'NORMAL'), 0)::NUMERIC(1...` -> `NULL` | 2 | MUERTO |
| 149 | `03_saldos_cuenta_mes.sql:44` | expresion | `COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'REGULARIZACION'), 0)::N...` -> `NULL` | 2 | MUERTO |
| 150 | `03_saldos_cuenta_mes.sql:45` | expresion | `COALESCE(SUM(m.importe) FILTER (WHERE m.clase_asiento = 'CIERRE'), 0)::NUMERIC(1...` -> `NULL` | 2 | MUERTO |
| 151 | `03_saldos_cuenta_mes.sql:46` | expresion | `SUM(m.importe_saldo)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 152 | `03_saldos_cuenta_mes.sql:51` | expresion | `s.cuenta_id` -> `NULL AS cuenta_id` | 1 | MUERTO (solo contrato) |
| 153 | `03_saldos_cuenta_mes.sql:52` | expresion | `s.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO (solo contrato) |
| 154 | `03_saldos_cuenta_mes.sql:53` | expresion | `s.ejercicio` -> `NULL AS ejercicio` | 1 | MUERTO (solo contrato) |
| 155 | `03_saldos_cuenta_mes.sql:54` | expresion | `s.mes` -> `NULL AS mes` | 1 | MUERTO (solo contrato) |
| 156 | `03_saldos_cuenta_mes.sql:55` | expresion | `s.num_apuntes` -> `NULL AS num_apuntes` | 1 | MUERTO (solo contrato) |
| 157 | `03_saldos_cuenta_mes.sql:56` | expresion | `s.debe` -> `NULL AS debe` | 1 | MUERTO (solo contrato) |
| 158 | `03_saldos_cuenta_mes.sql:57` | expresion | `s.haber` -> `NULL AS haber` | 1 | MUERTO (solo contrato) |
| 159 | `03_saldos_cuenta_mes.sql:58` | expresion | `s.importe_apertura` -> `NULL AS importe_apertura` | 1 | MUERTO (solo contrato) |
| 160 | `03_saldos_cuenta_mes.sql:59` | expresion | `s.importe_movimiento` -> `NULL AS importe_movimiento` | 1 | MUERTO (solo contrato) |
| 161 | `03_saldos_cuenta_mes.sql:60` | expresion | `s.importe_regularizacion` -> `NULL AS importe_regularizacion` | 1 | MUERTO (solo contrato) |
| 162 | `03_saldos_cuenta_mes.sql:61` | expresion | `s.importe_cierre` -> `NULL AS importe_cierre` | 1 | MUERTO (solo contrato) |
| 163 | `03_saldos_cuenta_mes.sql:62` | expresion | `s.importe_saldo` -> `NULL AS importe_saldo` | 2 | MUERTO |
| 164 | `03_saldos_cuenta_mes.sql:63` | expresion | `SUM(s.importe_saldo) OVER ( PARTITION BY s.cuenta_id, s.empresa_id ORDER BY s.ej...` -> `NULL` | 2 | MUERTO |
| 165 | `03_saldos_cuenta_mes.sql:42` | FILTER | `FILTER (WHERE m.clase_asiento IN ('APERTURA', 'SALDO_INICIAL'))` -> (nada) | 2 | MUERTO |
| 166 | `03_saldos_cuenta_mes.sql:43` | FILTER | `FILTER (WHERE m.clase_asiento = 'NORMAL')` -> (nada) | 2 | MUERTO |
| 167 | `03_saldos_cuenta_mes.sql:44` | FILTER | `FILTER (WHERE m.clase_asiento = 'REGULARIZACION')` -> (nada) | 2 | MUERTO |
| 168 | `03_saldos_cuenta_mes.sql:45` | FILTER | `FILTER (WHERE m.clase_asiento = 'CIERRE')` -> (nada) | 2 | MUERTO |
| 169 | `03_saldos_cuenta_mes.sql:69` | DDL quitado | `ALTER TABLE contabilidad.saldos_cuenta_mes ADD PRIMARY KEY (cuenta_id, empresa_i...` -> (nada) | 1 | MUERTO |
| 170 | `03_saldos_cuenta_mes.sql:70` | DDL quitado | `CREATE INDEX idx_con_saldos_empresa_ejercicio ON contabilidad.saldos_cuenta_mes ...` -> (nada) | 1 | MUERTO |
| 171 | `02_mayor.sql:179` | guarda: condicion | `v_mayor <> v_apu` -> `FALSE` | 1 | MUERTO |
| 172 | `02_mayor.sql:179` | guarda: IF quitado | `IF v_mayor <> v_apu THEN RAISE EXCEPTION 'mayor: contabilidad.mayor tiene % fila...` -> (nada) | 1 | MUERTO |
| 173 | `02_mayor.sql:180` | guarda: sin nombre del sub-paso | `mayor:` -> (nada) | 1 | MUERTO |
| 174 | `02_mayor.sql:171` | guarda: delante del DROP | `DROP TABLE IF EXISTS contabilidad.mayor CASCADE; CREATE TABLE contabilidad.mayor...` -> `-- R14: el mayor tiene EXACTAMENTE las filas de raw.apu, o el build falla DO $$ ...` | 1 | MUERTO |
| 175 | `02_mayor.sql:84` | semantico S1 | `a.res ILIKE 'asiento de cierre%'` -> `a.res LIKE 'Asiento de cierre%'` | 2 | MUERTO |
| 176 | `02_mayor.sql:85` | semantico S2 | `a.res ILIKE 'asiento de apertura%'` -> `a.res LIKE 'Asiento de apertura%'` | 2 | MUERTO |
| 177 | `02_mayor.sql:84` | semantico S3 | `WHEN a.cla = 3 OR a.res ILIKE 'asiento de cierre%' THEN 'CIERRE' WHEN a.cla = -1...` -> `WHEN a.cla = -1 OR a.res ILIKE 'asiento de apertura%' THEN 'APERTURA' WHEN a.cla...` | 2 | MUERTO |
| 178 | `02_mayor.sql:113` | semantico S4 | `ci.ejercicio = f.ejercicio - 1` -> `ci.ejercicio = f.ejercicio` | 3 | MUERTO |
| 179 | `02_mayor.sql:118` | semantico S5 | `IN ('CIERRE', 'APERTURA') THEN 0` -> `IN ('CIERRE') THEN 0` | 2 | MUERTO |
| 180 | `02_mayor.sql:83` | semantico S6 | `(COALESCE(a.deb, 0) - COALESCE(a.hab, 0))` -> `(COALESCE(a.hab, 0) - COALESCE(a.deb, 0))` | 2 | MUERTO |
| 181 | `02_mayor.sql:148` | semantico S7 | `ORDER BY s.fecha, s.codigo_asiento, s.posicion, s.apunte_id` -> `ORDER BY s.fecha, s.apunte_id` | 2 | MUERTO |
| 182 | `02_mayor.sql:147` | semantico S8 | `PARTITION BY s.cuenta_id` -> `PARTITION BY s.empresa_id` | 2 | MUERTO |
| 183 | `02_mayor.sql:73` | semantico S9 | `contabilidad.fn_fecha(a.fec) AS fecha,` -> `contabilidad.fn_fecha(asi.fec) AS fecha,` | 2 | MUERTO |
| 184 | `02_mayor.sql:76` | semantico S10 | `NULLIF(a.cueide, 0)` -> `a.cueide` | 2 | MUERTO |
| 185 | `02_mayor.sql:86` | semantico S11 | `a.cla = 1 OR a.res ILIKE 'asiento de regulariz%'` -> `a.cla = 1` | 2 | MUERTO |
| 186 | `02_mayor.sql:179` | semantico S12 | `IF v_mayor <> v_apu THEN` -> `IF v_mayor > v_apu THEN` | 1 | MUERTO |
| 187 | `02_mayor.sql:105` | semantico S13 | `WHERE f.clase_bruta = 'CIERRE'` -> `WHERE f.clase_bruta IN ('CIERRE', 'APERTURA')` | 2 | MUERTO |
| 188 | `02_mayor.sql:153` | semantico S14 | `cc.empresa::TEXT \|\| '-' \|\| cc.codigo_obra` -> `cc.codigo_obra` | 2 | MUERTO |
| 189 | `01_plan_cuentas.sql:74` | semantico S15 | `UNION ALL` -> `UNION` | 4 | MUERTO |
| 190 | `01_plan_cuentas.sql:114` | semantico S16 | `THEN LEFT(n.codigo_cuenta, 4)` -> `THEN LEFT(n.codigo_cuenta, 3)` | 2 | MUERTO |
| 191 | `01_plan_cuentas.sql:115` | semantico S17 | `WHEN n.nivel > 1 THEN LEFT(n.codigo_cuenta, n.nivel - 1)` -> `WHEN n.nivel > 1 THEN LEFT(n.codigo_cuenta, n.nivel)` | 2 | MUERTO |
| 192 | `01_plan_cuentas.sql:97` | semantico S18 | `n.nivel = 5 AS es_imputable` -> `n.nivel >= 4 AS es_imputable` | 2 | MUERTO |
| 193 | `01_plan_cuentas.sql:108` | semantico S19 | `CASE WHEN n.nivel = 5 THEN n.codigo_cuenta END) AS ruta_codigos` -> `n.codigo_cuenta) AS ruta_codigos` | 2 | MUERTO |
| 194 | `01_plan_cuentas.sql:118` | semantico S20 | `AND n.nivel >= 3 AND g3.cod` -> `AND g3.cod` | 2 | MUERTO |
| 195 | `01_plan_cuentas.sql:101` | semantico S21 | `(n.cuenta_padre_declarada_id IS NOT NULL AND n.cuenta_padre_declarada_id IS DIST...` -> `(n.cuenta_padre_declarada_id IS DISTINCT FROM pad.ide)` | 2 | MUERTO |
| 196 | `01_plan_cuentas.sql:58` | semantico S22 | `MIN(e.res) AS empresa_nombre` -> `MAX(e.res) AS empresa_nombre` | 2 | MUERTO |
| 197 | `01_plan_cuentas.sql:110` | semantico S23 | `COALESCE(n.fecbaj, 0) = 0 AS es_activa` -> `n.fecbaj = 0 AS es_activa` | 2 | MUERTO |
| 198 | `03_saldos_cuenta_mes.sql:42` | semantico S24 | `IN ('APERTURA', 'SALDO_INICIAL')` -> `IN ('APERTURA')` | 2 | MUERTO |
| 199 | `03_saldos_cuenta_mes.sql:64` | semantico S25 | `PARTITION BY s.cuenta_id, s.empresa_id` -> `PARTITION BY s.cuenta_id` | 2 | MUERTO |
| 200 | `03_saldos_cuenta_mes.sql:65` | semantico S26 | `ORDER BY s.ejercicio, s.mes` -> `ORDER BY s.mes, s.ejercicio` | 2 | MUERTO |
| 201 | `03_saldos_cuenta_mes.sql:46` | semantico S27 | `SUM(m.importe_saldo)::NUMERIC(18, 2)` -> `SUM(m.importe)::NUMERIC(18, 2)` | 2 | MUERTO |
| 202 | `03_saldos_cuenta_mes.sql:69` | semantico S28 | `ADD PRIMARY KEY (cuenta_id, empresa_id, ejercicio, mes);` -> `ADD PRIMARY KEY (cuenta_id, ejercicio, mes);` | 1 | MUERTO |
| 203 | `00_setup.sql:30` | semantico S29 | `IF d IS NULL OR d = 0 THEN` -> `IF d IS NULL THEN` | 1 | MUERTO |
| 204 | `00_setup.sql:34` | semantico S30 | `EXCEPTION WHEN OTHERS THEN RETURN NULL;` -> (nada) | 1 | MUERTO |
| 205 | `00_setup.sql:20` | semantico S31 | `CREATE SCHEMA IF NOT EXISTS contabilidad;` -> (nada) | 1 | MUERTO |
| 206 | `00_setup.sql:39` | semantico S32 | `'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE.` -> `'Convierte una fecha entera de Sigrid (AAAAMMDD) a DATE, como personal.fn_fecha.` | 1 | MUERTO |
| 207 | `build_contabilidad_step.py:96` | semantico P1 | `return ["ingest_raw"]` -> `return ["ingest_raw", "build_maestros"]` | 1 | MUERTO |
| 208 | `build_contabilidad_step.py:89` | semantico P2 | `return "build_aux"` -> `return "build_contabilidad"` | 1 | MUERTO |
| 209 | `build_contabilidad_step.py:114` | semantico P3 | `f"Fallo en {sub.name}: SQL file no encontrado: {sql_path}"` -> `f"SQL file no encontrado: {sql_path}"` | 1 | MUERTO |
| 210 | `build_contabilidad_step.py:138` | semantico P4 | `total_rows += rows` -> (nada) | 1 | MUERTO |
| 211 | `build_contabilidad_step.py:66` | semantico P5 | `target_table="mayor",` -> `target_table="apu",` | 2 | MUERTO |
| 212 | `main.py:536` | semantico P6 | `BuildContabilidadStep(settings), BuildCierreStep(settings),` -> `BuildCierreStep(settings), BuildContabilidadStep(settings),` | 4 | MUERTO |
| 213 | `main.py:536` | semantico P7 | `BuildContabilidadStep(settings), BuildCierreStep(settings),` -> `BuildCierreStep(settings),` | 15 | MUERTO |
| 214 | `main.py:5112` | semantico P8 | `ejecucion = _arrancar_ejecucion(pg) _ejecutar_paso(BuildContabilidadStep(setting...` -> `_ejecutar_paso(BuildContabilidadStep(settings), pg, None)` | 3 | MUERTO |
| 215 | `main.py:575` | semantico P9 | `los seis build (maestros, compras, retenciones, personal, contabilidad, cierre)` -> `los cinco build (maestros, compras, retenciones, personal, cierre)` | 2 | MUERTO |
| 216 | `settings.py:94` | semantico P10 | `personal,contabilidad,raw` -> `personal,raw` | 1 | MUERTO |
| 217 | `.env.example:49` | semantico P11 | `personal,contabilidad,raw` -> `personal,raw` | 1 | MUERTO |
| 218 | `diccionario.py:56` | semantico P12 | `"contabilidad",` -> (nada) | 14 | MUERTO |
| 219 | `02_roles.sql:90` | semantico P13 | `CREATE SCHEMA IF NOT EXISTS contabilidad;` -> (nada) | 1 | MUERTO |
| 220 | `00_global.yaml:396` | semantico P14 | `version: 36` -> `version: 35` | 1 | MUERTO |
| 221 | `00_global.yaml:419` | semantico P15 | `ambito: [cierre, compras, maestro, retenciones, personal, contabilidad]` -> `ambito: [cierre, compras, maestro, retenciones, personal]` | 1 | MUERTO |
| 222 | `00_global.yaml:571` | semantico P16 | `- contabilidad.saldos_cuenta_mes regla: >-` -> `regla: >-` | 1 | MUERTO |
| 223 | `00_global.yaml:1270` | semantico P17 | `pasos_etl: [build_contabilidad]` -> `pasos_etl: [build_personal]` | 1 | MUERTO |
| 224 | `contabilidad.yaml:73` | semantico P18 | `claves_alternativas: [[empresa_id, codigo_cuenta], [clave_cuenta]]` -> `claves_alternativas: [[empresa_id, codigo_cuenta]]` | 4 | MUERTO |
| 225 | `contabilidad.yaml:377` | semantico P19 | `- de: centro_coste_id a: maestro.centros_coste.centro_coste_id` -> `- de: centro_coste_id a: maestro.obras.obra_id` | 1 | MUERTO |
| 226 | `contabilidad.yaml:20` | semantico P20 | `7.742.538,38` -> `7,74 M` | 0 | SUPERVIVIENTE -> MUERTO (ver abajo) |
| 227 | `contabilidad.yaml:407` | semantico P21 | `clave_negocio: [cuenta_id, empresa_id, ejercicio, mes]` -> `clave_negocio: [cuenta_id, ejercicio, mes]` | 1 | MUERTO |
| 228 | `raw.yaml:1538` | semantico P22 | `NO hacen falta los dos saltos` -> `hacen falta dos saltos` | 1 | MUERTO |
| 229 | `raw.yaml:1498` | semantico P23 | `extienden a su fila de 'con', que es de 'con.tip = 17'` -> `extienden a su fila de 'con'` | 1 | MUERTO |
| 230 | `raw.yaml:1560` | semantico P24 | `No entra en 'contabilidad': es F-061.` -> `No entra en 'contabilidad'.` | 0 | SUPERVIVIENTE -> MUERTO (ver abajo) |
| 231 | `ARCHITECTURE.md:202` | semantico P25 | `- **El plan de cuentas son prefijos, dentro de la empresa (F-056).**` -> `- **El plan de cuentas es un arbol, dentro de la empresa (F-056).**` | 0 | SUPERVIVIENTE -> MUERTO (ver abajo) |
| 232 | `CLAUDE.md:98` | semantico P26 | `'personal/', 'contabilidad/', 'auxiliar/'` -> `'personal/', 'auxiliar/'` | 0 | SUPERVIVIENTE -> MUERTO (ver abajo) |
| 233 | `main.py:505` | semantico P27 | `y F-056 el sexto ('build_contabilidad'): seis build de negocio.` -> `.` | 1 | MUERTO |
