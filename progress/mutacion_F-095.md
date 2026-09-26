<!-- progress/mutacion_F-095.md -->
# F-095 · Campana de mutacion (review pasada 1, cambios 2-5)

**Campana MANUAL y SISTEMATICA**: la herramienta genera 0 mutantes para F-095
(ver «Control del cero»), y el cambio real es SQL, que no muta. Los mutantes NO
los elige quien escribio los tests: los genera un script
(`campana.py` + `sqlmap.py`, scratchpad de la sesion) recorriendo los seis
`CREATE` de `sql/retenciones/03`-`06`:

- **una por expresion proyectada** de cada SELECT (CTE incluidos): la expresion
  se sustituye por `NULL` conservando el alias;
- **DISTINCT** quitado; cada **FILTER** quitado;
- **cada condicion** de nivel superior de cada `WHERE` y `HAVING` (a `TRUE` si
  van con AND, a `FALSE` si van con OR);
- **cada JOIN**: su tipo cambiado (LEFT <-> INNER, FULL -> LEFT) y cada
  condicion de su `ON` a `TRUE`;
- los **11 del reviewer** (S1-S11) tal cual;
- en `build_retenciones_step.py`: cada campo de los cuatro `_SubStep` nuevos, su
  `target_schema`, y cada `_SubStep` quitado ENTERO (lineas completas: compila;
  sustituye al #6 mortinato de la pasada anterior). Cada mutante de Python se
  compila antes de juzgarlo.

Juez: `tests/test_f095_retenciones_contables.py` + `tests/test_f047_steps.py`,
en una COPIA por worker (`git archive HEAD`), restaurando tras cada mutante. El
arbol del repositorio no se toca.

| Dato | Valor |
|---|---|
| SHA de HEAD medido | `528c2eb39af762e086d7130b3ca41870e3015795` |
| Workers | 3 (una copia por worker, en paralelo) |
| Linea base (por copia, antes de mutar) | 17.2 s (94 passed, 1 skipped in 14.13s), 15.4 s (94 passed, 1 skipped in 12.68s), 10.5 s (94 passed, 1 skipped in 8.18s) |
| Timeout por mutante | 120 s |
| Tiempo total | 1212.3 s (20.2 min) |
| Mutantes generados | **264** |
| Muertos | **264** |
| Supervivientes | **0** |
| Timeouts | 0 |
| Mortinatos (no compilan) | 0 |

Por tipo: DISTINCT 1, FILTER 8, condicion del HAVING 1, condicion del ON 22, condicion del WHERE 19, expresion 164, review 11, step: campo 11, step: esquema 3, step: sub-paso quitado 4, tipo de JOIN 20.

## Control del cero automatico (RM)

`python -m harness.mutacion --feature F-095 --base main` -> «CERO MUTANTES»: el
alcance son 38 lineas de `build_retenciones_step.py` (docstring, comentarios y
la declaracion de `SUB_PASOS`). **Prueba de control**, calculo puro con
`harness.mutacion.generar_mutantes` sobre el fichero ENTERO: **12 mutantes**, en
las lineas 46, 130, 134, 137, 149, 152, 159, 160, 162 y 166 (el `run()` y el
`_SubStep`, que F-095 no toca). El generador funciona: el 0 es legitimo.

## Lo que mato a S1-S11

`test_f095_contrato_expresion_a_expresion` (commit 528c2eb): para cada SELECT de
los seis `CREATE` fija el DISTINCT, cada expresion proyectada y cada clausula
del FROM (JOIN con su ON, WHERE, GROUP BY, HAVING), mas un control de que el
parser ve lo que debe. Los tests anteriores fijaban el alias; este, la formula.

## Equivalentes y notas (RM3, RM5)

- **Ningun superviviente**: nada que declarar equivalente en esta campana.
- El #13 de la pasada anterior (quitar `NULLS NOT DISTINCT` del indice unico de
  `saldo_contable`) **es un equivalente semantico**: el `GROUP BY` ya da una
  sola fila por (proveedor, obra), NULL incluido; el indice es una guarda
  redundante que hace fallar el build si alguien rompe el grano. Lo mata un
  test de texto (`test_f095_r11_clave_con_la_fila_sin_obra`), y se declara aqui
  como pide el review. No entra en la campana sistematica (no es SELECT,
  WHERE, FILTER, HAVING ni JOIN).
- Los mutantes a `NULL` los mata el contrato expresion a expresion; los que
  dan 2 o mas fallos los mata ademas un test semantico (p. ej. S1 y S2,
  `test_f095_r14_*`/`r15_*`).
- Los 4 `_SubStep` quitados enteros compilan y mueren con 3-4 fallos
  (`test_f095_r27_*` y `test_f047_r4_*`): sustituyen al #6 mortinato.

## Tabla completa

| # | fichero:linea | tipo | original -> mutado | fallos | resultado |
|---|---|---|---|---|---|
| 1 | `03_apuntes_contables.sql:23` | expresion | `prv.ide` -> `NULL` | 2 | MUERTO |
| 2 | `03_apuntes_contables.sql:24` | expresion | `ent.res` -> `NULL` | 2 | MUERTO |
| 3 | `03_apuntes_contables.sql:25` | expresion | `prv.cueretide` -> `NULL` | 2 | MUERTO |
| 4 | `03_apuntes_contables.sql:26` | expresion | `cue.cod` -> `NULL` | 2 | MUERTO |
| 5 | `03_apuntes_contables.sql:27` | expresion | `cue.res` -> `NULL` | 2 | MUERTO |
| 6 | `03_apuntes_contables.sql:28` | expresion | `LEFT(cue.cod, 4)` -> `NULL` | 2 | MUERTO |
| 7 | `03_apuntes_contables.sql:30` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 8 | `03_apuntes_contables.sql:30` | condicion del ON | `ent.ide = prv.ide` -> `TRUE` | 2 | MUERTO |
| 9 | `03_apuntes_contables.sql:31` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 10 | `03_apuntes_contables.sql:31` | condicion del ON | `cue.ide = prv.cueretide` -> `TRUE` | 2 | MUERTO |
| 11 | `03_apuntes_contables.sql:32` | condicion del WHERE | `COALESCE(prv.cueretide, 0) <> 0` -> `TRUE` | 2 | MUERTO |
| 12 | `03_apuntes_contables.sql:102` | expresion | `a.ide` -> `NULL` | 2 | MUERTO |
| 13 | `03_apuntes_contables.sql:103` | expresion | `NULLIF(a.asiide, 0)` -> `NULL` | 2 | MUERTO |
| 14 | `03_apuntes_contables.sql:104` | expresion | `retenciones.fn_sigrid_date(a.fec)` -> `NULL` | 2 | MUERTO |
| 15 | `03_apuntes_contables.sql:105` | expresion | `EXTRACT(YEAR FROM retenciones.fn_sigrid_date(a.fec))::INT` -> `NULL` | 2 | MUERTO |
| 16 | `03_apuntes_contables.sql:106` | expresion | `a.cueide` -> `NULL` | 2 | MUERTO |
| 17 | `03_apuntes_contables.sql:107` | expresion | `cp.codigo_cuenta` -> `NULL` | 1 | MUERTO |
| 18 | `03_apuntes_contables.sql:108` | expresion | `cp.proveedor_id` -> `NULL` | 2 | MUERTO |
| 19 | `03_apuntes_contables.sql:109` | expresion | `a.res` -> `NULL` | 2 | MUERTO |
| 20 | `03_apuntes_contables.sql:110` | expresion | `COALESCE(a.hab, 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 21 | `03_apuntes_contables.sql:111` | expresion | `COALESCE(a.deb, 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 22 | `03_apuntes_contables.sql:112` | expresion | `(COALESCE(a.hab, 0) - COALESCE(a.deb, 0))::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 23 | `03_apuntes_contables.sql:113` | expresion | `NULLIF(a.cenide, 0)` -> `NULL` | 2 | MUERTO |
| 24 | `03_apuntes_contables.sql:115` | tipo de JOIN | `JOIN` -> `LEFT JOIN` | 2 | MUERTO |
| 25 | `03_apuntes_contables.sql:115` | condicion del ON | `cp.cuenta_id = a.cueide` -> `TRUE` | 2 | MUERTO |
| 26 | `03_apuntes_contables.sql:120` | DISTINCT | `DISTINCT` -> (nada) | 2 | MUERTO |
| 27 | `03_apuntes_contables.sql:120` | expresion | `ap.cuenta_id` -> `NULL AS cuenta_id` | 2 | MUERTO |
| 28 | `03_apuntes_contables.sql:120` | expresion | `ap.ejercicio` -> `NULL AS ejercicio` | 2 | MUERTO |
| 29 | `03_apuntes_contables.sql:122` | condicion del WHERE | `ap.concepto LIKE 'Asiento de cierre%'` -> `TRUE` | 2 | MUERTO |
| 30 | `03_apuntes_contables.sql:126` | expresion | `r.asiide` -> `NULL` | 2 | MUERTO |
| 31 | `03_apuntes_contables.sql:126` | expresion | `MIN(r.conide)` -> `NULL` | 2 | MUERTO |
| 32 | `03_apuntes_contables.sql:128` | condicion del WHERE | `r.asiide <> 0` -> `TRUE` | 1 | MUERTO |
| 33 | `03_apuntes_contables.sql:128` | condicion del WHERE | `r.conide <> 0` -> `TRUE` | 1 | MUERTO |
| 34 | `03_apuntes_contables.sql:134` | expresion | `p.conide` -> `NULL` | 1 | MUERTO |
| 35 | `03_apuntes_contables.sql:135` | expresion | `COUNT(DISTINCT COALESCE(p.cenide, 0))` -> `NULL` | 2 | MUERTO |
| 36 | `03_apuntes_contables.sql:136` | expresion | `MIN(COALESCE(p.cenide, 0))` -> `NULL` | 2 | MUERTO |
| 37 | `03_apuntes_contables.sql:138` | condicion del WHERE | `COALESCE(p.retide, 0) <> 0` -> `TRUE` | 2 | MUERTO |
| 38 | `03_apuntes_contables.sql:138` | condicion del WHERE | `COALESCE(p.conide, 0) <> 0` -> `TRUE` | 1 | MUERTO |
| 39 | `03_apuntes_contables.sql:143` | expresion | `p.entide` -> `NULL` | 1 | MUERTO |
| 40 | `03_apuntes_contables.sql:143` | expresion | `MIN(p.cenide)` -> `NULL` | 1 | MUERTO |
| 41 | `03_apuntes_contables.sql:145` | condicion del WHERE | `COALESCE(p.retide, 0) <> 0` -> `TRUE` | 2 | MUERTO |
| 42 | `03_apuntes_contables.sql:145` | condicion del WHERE | `COALESCE(p.cenide, 0) <> 0` -> `TRUE` | 2 | MUERTO |
| 43 | `03_apuntes_contables.sql:147` | condicion del HAVING | `COUNT(DISTINCT p.cenide) = 1` -> `TRUE` | 2 | MUERTO |
| 44 | `03_apuntes_contables.sql:151` | expresion | `ap.apunte_id` -> `NULL AS apunte_id` | 1 | MUERTO |
| 45 | `03_apuntes_contables.sql:152` | expresion | `ap.asiento_id` -> `NULL AS asiento_id` | 1 | MUERTO |
| 46 | `03_apuntes_contables.sql:153` | expresion | `ap.fecha` -> `NULL AS fecha` | 1 | MUERTO |
| 47 | `03_apuntes_contables.sql:154` | expresion | `ap.ejercicio` -> `NULL AS ejercicio` | 1 | MUERTO |
| 48 | `03_apuntes_contables.sql:155` | expresion | `ap.cuenta_id` -> `NULL AS cuenta_id` | 1 | MUERTO |
| 49 | `03_apuntes_contables.sql:156` | expresion | `ap.codigo_cuenta` -> `NULL AS codigo_cuenta` | 1 | MUERTO |
| 50 | `03_apuntes_contables.sql:157` | expresion | `ap.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 51 | `03_apuntes_contables.sql:158` | expresion | `ap.concepto` -> `NULL AS concepto` | 1 | MUERTO |
| 52 | `03_apuntes_contables.sql:159` | expresion | `ap.importe_alta` -> `NULL AS importe_alta` | 1 | MUERTO |
| 53 | `03_apuntes_contables.sql:160` | expresion | `ap.importe_baja` -> `NULL AS importe_baja` | 1 | MUERTO |
| 54 | `03_apuntes_contables.sql:161` | expresion | `ap.importe` -> `NULL AS importe` | 1 | MUERTO |
| 55 | `03_apuntes_contables.sql:162` | expresion | `CASE WHEN ap.concepto LIKE 'Asiento de cierre%' THEN 'CIERRE' -- «no existe cierre de la c...` -> `NULL` | 2 | MUERTO |
| 56 | `03_apuntes_contables.sql:170` | expresion | `UPPER(COALESCE(ap.concepto, '')) LIKE '%PRESCRI%'` -> `NULL` | 2 | MUERTO |
| 57 | `03_apuntes_contables.sql:171` | expresion | `ap.centro_coste_id` -> `NULL AS centro_coste_id` | 1 | MUERTO |
| 58 | `03_apuntes_contables.sql:172` | expresion | `COALESCE(cc_apu.obra_id, cc_fac.obra_id, cc_efe.obra_id, cc_prv.obra_id)` -> `NULL` | 2 | MUERTO |
| 59 | `03_apuntes_contables.sql:173` | expresion | `CASE WHEN cc_apu.obra_id IS NOT NULL THEN 'APUNTE' WHEN cc_fac.obra_id IS NOT NULL THEN 'F...` -> `NULL` | 2 | MUERTO |
| 60 | `03_apuntes_contables.sql:178` | expresion | `ra.documento_id` -> `NULL` | 2 | MUERTO |
| 61 | `03_apuntes_contables.sql:180` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 62 | `03_apuntes_contables.sql:180` | condicion del ON | `cc.cuenta_id = ap.cuenta_id` -> `TRUE` | 2 | MUERTO |
| 63 | `03_apuntes_contables.sql:180` | condicion del ON | `cc.ejercicio = ap.ejercicio - 1` -> `TRUE` | 2 | MUERTO |
| 64 | `03_apuntes_contables.sql:181` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 65 | `03_apuntes_contables.sql:181` | condicion del ON | `cc_apu.centro_coste_id = ap.centro_coste_id` -> `TRUE` | 2 | MUERTO |
| 66 | `03_apuntes_contables.sql:182` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 67 | `03_apuntes_contables.sql:182` | condicion del ON | `ra.asiento_id = ap.asiento_id` -> `TRUE` | 2 | MUERTO |
| 68 | `03_apuntes_contables.sql:183` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 69 | `03_apuntes_contables.sql:183` | condicion del ON | `ef.documento_id = ra.documento_id` -> `TRUE` | 2 | MUERTO |
| 70 | `03_apuntes_contables.sql:183` | condicion del ON | `ef.num_centros = 1` -> `TRUE` | 2 | MUERTO |
| 71 | `03_apuntes_contables.sql:184` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 72 | `03_apuntes_contables.sql:184` | condicion del ON | `cc_fac.centro_coste_id = NULLIF(ef.centro_coste_id, 0)` -> `TRUE` | 2 | MUERTO |
| 73 | `03_apuntes_contables.sql:185` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 74 | `03_apuntes_contables.sql:185` | condicion del ON | `efe.ide = ra.documento_id` -> `TRUE` | 3 | MUERTO |
| 75 | `03_apuntes_contables.sql:186` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 76 | `03_apuntes_contables.sql:186` | condicion del ON | `cc_efe.centro_coste_id = NULLIF(efe.cenide, 0)` -> `TRUE` | 2 | MUERTO |
| 77 | `03_apuntes_contables.sql:187` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 78 | `03_apuntes_contables.sql:187` | condicion del ON | `pu.proveedor_id = ap.proveedor_id` -> `TRUE` | 2 | MUERTO |
| 79 | `03_apuntes_contables.sql:188` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 80 | `03_apuntes_contables.sql:188` | condicion del ON | `cc_prv.centro_coste_id = pu.centro_coste_id` -> `TRUE` | 2 | MUERTO |
| 81 | `03_apuntes_contables.sql:191` | expresion | `r.apunte_id` -> `NULL AS apunte_id` | 1 | MUERTO |
| 82 | `03_apuntes_contables.sql:192` | expresion | `r.asiento_id` -> `NULL AS asiento_id` | 1 | MUERTO |
| 83 | `03_apuntes_contables.sql:193` | expresion | `r.fecha` -> `NULL AS fecha` | 1 | MUERTO |
| 84 | `03_apuntes_contables.sql:194` | expresion | `r.ejercicio` -> `NULL AS ejercicio` | 1 | MUERTO |
| 85 | `03_apuntes_contables.sql:195` | expresion | `r.cuenta_id` -> `NULL AS cuenta_id` | 1 | MUERTO |
| 86 | `03_apuntes_contables.sql:196` | expresion | `r.codigo_cuenta` -> `NULL AS codigo_cuenta` | 1 | MUERTO |
| 87 | `03_apuntes_contables.sql:197` | expresion | `r.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 88 | `03_apuntes_contables.sql:198` | expresion | `r.concepto` -> `NULL AS concepto` | 1 | MUERTO |
| 89 | `03_apuntes_contables.sql:199` | expresion | `r.importe_alta` -> `NULL AS importe_alta` | 1 | MUERTO |
| 90 | `03_apuntes_contables.sql:200` | expresion | `r.importe_baja` -> `NULL AS importe_baja` | 1 | MUERTO |
| 91 | `03_apuntes_contables.sql:201` | expresion | `r.importe` -> `NULL AS importe` | 1 | MUERTO |
| 92 | `03_apuntes_contables.sql:202` | expresion | `r.clase` -> `NULL AS clase` | 1 | MUERTO |
| 93 | `03_apuntes_contables.sql:203` | expresion | `r.es_prescripcion` -> `NULL AS es_prescripcion` | 1 | MUERTO |
| 94 | `03_apuntes_contables.sql:204` | expresion | `r.centro_coste_id` -> `NULL AS centro_coste_id` | 1 | MUERTO |
| 95 | `03_apuntes_contables.sql:205` | expresion | `r.obra_id` -> `NULL AS obra_id` | 1 | MUERTO |
| 96 | `03_apuntes_contables.sql:206` | expresion | `ob.emp` -> `NULL` | 1 | MUERTO |
| 97 | `03_apuntes_contables.sql:207` | expresion | `ob.cod` -> `NULL` | 1 | MUERTO |
| 98 | `03_apuntes_contables.sql:208` | expresion | `ob.emp::text \|\| '-' \|\| ob.cod` -> `NULL` | 1 | MUERTO |
| 99 | `03_apuntes_contables.sql:209` | expresion | `ob.res` -> `NULL` | 1 | MUERTO |
| 100 | `03_apuntes_contables.sql:210` | expresion | `r.via_obra` -> `NULL AS via_obra` | 1 | MUERTO |
| 101 | `03_apuntes_contables.sql:211` | expresion | `r.documento_id` -> `NULL AS documento_id` | 1 | MUERTO |
| 102 | `03_apuntes_contables.sql:213` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 103 | `03_apuntes_contables.sql:213` | condicion del ON | `ob.ide = r.obra_id` -> `TRUE` | 1 | MUERTO |
| 104 | `04_saldo_contable.sql:36` | expresion | `a.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 105 | `04_saldo_contable.sql:37` | expresion | `cp.proveedor_nombre` -> `NULL AS proveedor_nombre` | 1 | MUERTO |
| 106 | `04_saldo_contable.sql:38` | expresion | `a.obra_id` -> `NULL AS obra_id` | 1 | MUERTO |
| 107 | `04_saldo_contable.sql:39` | expresion | `a.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO |
| 108 | `04_saldo_contable.sql:40` | expresion | `a.codigo_obra` -> `NULL AS codigo_obra` | 1 | MUERTO |
| 109 | `04_saldo_contable.sql:41` | expresion | `a.clave_obra` -> `NULL AS clave_obra` | 1 | MUERTO |
| 110 | `04_saldo_contable.sql:42` | expresion | `a.nombre_obra` -> `NULL AS nombre_obra` | 1 | MUERTO |
| 111 | `04_saldo_contable.sql:43` | expresion | `COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'ALTA'), 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 112 | `04_saldo_contable.sql:44` | expresion | `COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'BAJA'), 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 113 | `04_saldo_contable.sql:45` | expresion | `COALESCE(SUM(a.importe) FILTER (WHERE a.clase = 'SALDO_INICIAL'), 0)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 114 | `04_saldo_contable.sql:46` | expresion | `COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')), 0)::N...` -> `NULL` | 2 | MUERTO |
| 115 | `04_saldo_contable.sql:47` | expresion | `COALESCE(SUM(a.importe) FILTER (WHERE a.clase IN ('APERTURA', 'SALDO_INICIAL') AND a.ejerc...` -> `NULL` | 2 | MUERTO |
| 116 | `04_saldo_contable.sql:48` | expresion | `COUNT(*) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> `NULL` | 1 | MUERTO |
| 117 | `04_saldo_contable.sql:49` | expresion | `MIN(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> `NULL` | 2 | MUERTO |
| 118 | `04_saldo_contable.sql:50` | expresion | `MAX(a.fecha) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> `NULL` | 2 | MUERTO |
| 119 | `04_saldo_contable.sql:52` | tipo de JOIN | `JOIN` -> `LEFT JOIN` | 1 | MUERTO |
| 120 | `04_saldo_contable.sql:52` | condicion del ON | `cp.proveedor_id = a.proveedor_id` -> `TRUE` | 1 | MUERTO |
| 121 | `04_saldo_contable.sql:55` | condicion del WHERE | `a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')` -> `FALSE` | 2 | MUERTO |
| 122 | `04_saldo_contable.sql:55` | condicion del WHERE | `(a.clase = 'APERTURA' AND a.ejercicio = 2016)` -> `FALSE` | 2 | MUERTO |
| 123 | `04_saldo_contable.sql:43` | FILTER | `FILTER (WHERE a.clase = 'ALTA')` -> (nada) | 2 | MUERTO |
| 124 | `04_saldo_contable.sql:44` | FILTER | `FILTER (WHERE a.clase = 'BAJA')` -> (nada) | 2 | MUERTO |
| 125 | `04_saldo_contable.sql:45` | FILTER | `FILTER (WHERE a.clase = 'SALDO_INICIAL')` -> (nada) | 2 | MUERTO |
| 126 | `04_saldo_contable.sql:46` | FILTER | `FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> (nada) | 2 | MUERTO |
| 127 | `04_saldo_contable.sql:47` | FILTER | `FILTER (WHERE a.clase IN ('APERTURA', 'SALDO_INICIAL') AND a.ejercicio = 2016)` -> (nada) | 2 | MUERTO |
| 128 | `04_saldo_contable.sql:48` | FILTER | `FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> (nada) | 1 | MUERTO |
| 129 | `04_saldo_contable.sql:49` | FILTER | `FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> (nada) | 2 | MUERTO |
| 130 | `04_saldo_contable.sql:50` | FILTER | `FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL'))` -> (nada) | 2 | MUERTO |
| 131 | `05_fin_obra.sql:92` | expresion | `12` -> `NULL` | 2 | MUERTO |
| 132 | `05_fin_obra.sql:97` | expresion | `c.obride` -> `NULL` | 1 | MUERTO |
| 133 | `05_fin_obra.sql:98` | expresion | `MAX(NULLIF(c.fecinigar, 0))` -> `NULL` | 2 | MUERTO |
| 134 | `05_fin_obra.sql:99` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecreafin, 0)))` -> `NULL` | 2 | MUERTO |
| 135 | `05_fin_obra.sql:100` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprorec, 0)))` -> `NULL` | 2 | MUERTO |
| 136 | `05_fin_obra.sql:101` | expresion | `retenciones.fn_sigrid_date(MAX(NULLIF(c.fecprefin, 0)))` -> `NULL` | 2 | MUERTO |
| 137 | `05_fin_obra.sql:102` | expresion | `NULLIF(MAX(c.plaret), 0)` -> `NULL` | 2 | MUERTO |
| 138 | `05_fin_obra.sql:103` | expresion | `NULLIF(MAX(c.plagar), 0)` -> `NULL` | 2 | MUERTO |
| 139 | `05_fin_obra.sql:104` | expresion | `COUNT(*)` -> `NULL` | 1 | MUERTO |
| 140 | `05_fin_obra.sql:109` | expresion | `f.obra_id` -> `NULL AS obra_id` | 2 | MUERTO |
| 141 | `05_fin_obra.sql:109` | expresion | `MAX(f.anio_mes)` -> `NULL` | 2 | MUERTO |
| 142 | `05_fin_obra.sql:111` | condicion del WHERE | `f.ejecutado_mes <> 0` -> `TRUE` | 2 | MUERTO |
| 143 | `05_fin_obra.sql:116` | expresion | `obr.ide` -> `NULL` | 1 | MUERTO |
| 144 | `05_fin_obra.sql:117` | expresion | `con.emp` -> `NULL` | 2 | MUERTO |
| 145 | `05_fin_obra.sql:118` | expresion | `con.cod` -> `NULL` | 1 | MUERTO |
| 146 | `05_fin_obra.sql:119` | expresion | `con.emp::text \|\| '-' \|\| con.cod` -> `NULL` | 2 | MUERTO |
| 147 | `05_fin_obra.sql:120` | expresion | `con.res` -> `NULL` | 1 | MUERTO |
| 148 | `05_fin_obra.sql:121` | expresion | `con.est` -> `NULL` | 2 | MUERTO |
| 149 | `05_fin_obra.sql:122` | expresion | `COALESCE(retenciones.fn_sigrid_date(oc.fec_inicio_garantia), retenciones.fn_sigrid_date(ob...` -> `NULL` | 2 | MUERTO |
| 150 | `05_fin_obra.sql:124` | expresion | `ci.ultimo_cierre` -> `NULL` | 1 | MUERTO |
| 151 | `05_fin_obra.sql:126` | expresion | `COALESCE( oc.fec_real_fin, retenciones.fn_sigrid_date(obr.fecfinrea) )` -> `NULL` | 2 | MUERTO |
| 152 | `05_fin_obra.sql:130` | expresion | `oc.fec_recepcion_provisional` -> `NULL` | 2 | MUERTO |
| 153 | `05_fin_obra.sql:131` | expresion | `COALESCE( oc.fec_prev_fin, retenciones.fn_sigrid_date(obr.fecfinpre) )` -> `NULL` | 2 | MUERTO |
| 154 | `05_fin_obra.sql:135` | expresion | `COALESCE(oc.plazo_retencion, oc.plazo_garantia, k.plazo_fijo_meses)::INT` -> `NULL` | 2 | MUERTO |
| 155 | `05_fin_obra.sql:136` | expresion | `CASE WHEN oc.plazo_retencion IS NOT NULL THEN 'PLAZO_RETENCION_CLIENTE' WHEN oc.plazo_gara...` -> `NULL` | 3 | MUERTO |
| 156 | `05_fin_obra.sql:139` | expresion | `COALESCE(oc.num_contratos_obra, 0)` -> `NULL` | 1 | MUERTO |
| 157 | `05_fin_obra.sql:141` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 158 | `05_fin_obra.sql:141` | condicion del ON | `con.ide = obr.ide` -> `TRUE` | 2 | MUERTO |
| 159 | `05_fin_obra.sql:142` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 160 | `05_fin_obra.sql:142` | condicion del ON | `oc.obra_id = obr.ide` -> `TRUE` | 1 | MUERTO |
| 161 | `05_fin_obra.sql:143` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 162 | `05_fin_obra.sql:143` | condicion del ON | `ci.obra_id = obr.ide` -> `TRUE` | 1 | MUERTO |
| 163 | `05_fin_obra.sql:149` | expresion | `CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia WHEN b.ultimo_c...` -> `NULL` | 3 | MUERTO |
| 164 | `05_fin_obra.sql:153` | expresion | `CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' WHEN b.ultimo_cierre ...` -> `NULL` | 2 | MUERTO |
| 165 | `05_fin_obra.sql:159` | expresion | `f.obra_id` -> `NULL AS obra_id` | 1 | MUERTO |
| 166 | `05_fin_obra.sql:160` | expresion | `f.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO |
| 167 | `05_fin_obra.sql:161` | expresion | `f.codigo_obra` -> `NULL AS codigo_obra` | 1 | MUERTO |
| 168 | `05_fin_obra.sql:162` | expresion | `f.clave_obra` -> `NULL AS clave_obra` | 1 | MUERTO |
| 169 | `05_fin_obra.sql:163` | expresion | `f.nombre_obra` -> `NULL AS nombre_obra` | 1 | MUERTO |
| 170 | `05_fin_obra.sql:164` | expresion | `f.estado_obra` -> `NULL AS estado_obra` | 1 | MUERTO |
| 171 | `05_fin_obra.sql:165` | expresion | `f.fecha_inicio_garantia` -> `NULL AS fecha_inicio_garantia` | 1 | MUERTO |
| 172 | `05_fin_obra.sql:166` | expresion | `f.ultimo_cierre` -> `NULL AS ultimo_cierre` | 1 | MUERTO |
| 173 | `05_fin_obra.sql:167` | expresion | `f.fecha_fin_real` -> `NULL AS fecha_fin_real` | 1 | MUERTO |
| 174 | `05_fin_obra.sql:168` | expresion | `f.fecha_recepcion_provisional` -> `NULL AS fecha_recepcion_provisional` | 1 | MUERTO |
| 175 | `05_fin_obra.sql:169` | expresion | `f.fecha_fin_prevista` -> `NULL AS fecha_fin_prevista` | 1 | MUERTO |
| 176 | `05_fin_obra.sql:170` | expresion | `f.fecha_fin_obra` -> `NULL AS fecha_fin_obra` | 1 | MUERTO |
| 177 | `05_fin_obra.sql:171` | expresion | `f.fuente_fin_obra` -> `NULL AS fuente_fin_obra` | 1 | MUERTO |
| 178 | `05_fin_obra.sql:172` | expresion | `(f.fecha_fin_obra IS NULL AND COALESCE(f.estado_obra, 0) IN (19, 21, 23, 25))` -> `NULL` | 2 | MUERTO |
| 179 | `05_fin_obra.sql:173` | expresion | `f.plazo_meses` -> `NULL AS plazo_meses` | 1 | MUERTO |
| 180 | `05_fin_obra.sql:174` | expresion | `f.fuente_plazo` -> `NULL AS fuente_plazo` | 2 | MUERTO |
| 181 | `05_fin_obra.sql:175` | expresion | `(f.fecha_fin_obra + make_interval(months => f.plazo_meses))::DATE` -> `NULL` | 3 | MUERTO |
| 182 | `05_fin_obra.sql:176` | expresion | `f.num_contratos_obra` -> `NULL AS num_contratos_obra` | 1 | MUERTO |
| 183 | `06_views_contables.sql:44` | expresion | `s.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 184 | `06_views_contables.sql:45` | expresion | `MAX(s.proveedor_nombre)` -> `NULL` | 1 | MUERTO |
| 185 | `06_views_contables.sql:46` | expresion | `SUM(s.saldo)` -> `NULL` | 2 | MUERTO |
| 186 | `06_views_contables.sql:47` | expresion | `SUM(s.saldo_anterior_2016)` -> `NULL` | 1 | MUERTO |
| 187 | `06_views_contables.sql:53` | expresion | `a.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 188 | `06_views_contables.sql:53` | expresion | `-SUM(a.importe)` -> `NULL` | 1 | MUERTO |
| 189 | `06_views_contables.sql:55` | condicion del WHERE | `a.es_prescripcion` -> `TRUE` | 1 | MUERTO |
| 190 | `06_views_contables.sql:55` | condicion del WHERE | `a.clase IN ('ALTA', 'BAJA')` -> `TRUE` | 1 | MUERTO |
| 191 | `06_views_contables.sql:60` | expresion | `entidad_id` -> `NULL` | 1 | MUERTO |
| 192 | `06_views_contables.sql:61` | expresion | `MAX(entidad_nombre)` -> `NULL` | 1 | MUERTO |
| 193 | `06_views_contables.sql:62` | expresion | `SUM(importe)` -> `NULL` | 1 | MUERTO |
| 194 | `06_views_contables.sql:63` | condicion del WHERE | `sentido = 'PROVEEDOR'` -> `TRUE` | 2 | MUERTO |
| 195 | `06_views_contables.sql:63` | condicion del WHERE | `estado = 'VIVA'` -> `TRUE` | 2 | MUERTO |
| 196 | `06_views_contables.sql:64` | condicion del WHERE | `entidad_id IS NOT NULL` -> `TRUE` | 1 | MUERTO |
| 197 | `06_views_contables.sql:69` | expresion | `COALESCE(c.proveedor_id, e.proveedor_id)` -> `NULL` | 1 | MUERTO |
| 198 | `06_views_contables.sql:70` | expresion | `COALESCE(c.proveedor_nombre, e.proveedor_nombre)` -> `NULL` | 1 | MUERTO |
| 199 | `06_views_contables.sql:71` | expresion | `COALESCE(c.saldo_contable, 0)::NUMERIC(18, 2)` -> `NULL` | 1 | MUERTO |
| 200 | `06_views_contables.sql:72` | expresion | `COALESCE(e.viva_efectos, 0)::NUMERIC(18, 2)` -> `NULL` | 1 | MUERTO |
| 201 | `06_views_contables.sql:73` | expresion | `COALESCE(c.saldo_anterior_2016, 0)::NUMERIC(18, 2)` -> `NULL` | 1 | MUERTO |
| 202 | `06_views_contables.sql:75` | tipo de JOIN | `FULL JOIN` -> `LEFT JOIN` | 2 | MUERTO |
| 203 | `06_views_contables.sql:75` | condicion del ON | `e.proveedor_id = c.proveedor_id` -> `TRUE` | 2 | MUERTO |
| 204 | `06_views_contables.sql:78` | expresion | `x.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 205 | `06_views_contables.sql:79` | expresion | `x.proveedor_nombre` -> `NULL AS proveedor_nombre` | 1 | MUERTO |
| 206 | `06_views_contables.sql:80` | expresion | `x.saldo_contable` -> `NULL AS saldo_contable` | 1 | MUERTO |
| 207 | `06_views_contables.sql:81` | expresion | `x.viva_efectos` -> `NULL AS viva_efectos` | 1 | MUERTO |
| 208 | `06_views_contables.sql:82` | expresion | `(x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2)` -> `NULL` | 2 | MUERTO |
| 209 | `06_views_contables.sql:83` | expresion | `CASE WHEN ABS(x.saldo_contable - x.viva_efectos) < 1 THEN 'CUADRA' WHEN ABS(x.viva_efectos...` -> `NULL` | 2 | MUERTO |
| 210 | `06_views_contables.sql:88` | expresion | `x.saldo_anterior_2016` -> `NULL AS saldo_anterior_2016` | 1 | MUERTO |
| 211 | `06_views_contables.sql:89` | expresion | `COALESCE(p.prescrito, 0)::NUMERIC(18, 2)` -> `NULL` | 1 | MUERTO |
| 212 | `06_views_contables.sql:91` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 1 | MUERTO |
| 213 | `06_views_contables.sql:91` | condicion del ON | `p.proveedor_id = x.proveedor_id` -> `TRUE` | 1 | MUERTO |
| 214 | `06_views_contables.sql:92` | condicion del WHERE | `ABS(x.saldo_contable) >= 1` -> `FALSE` | 2 | MUERTO |
| 215 | `06_views_contables.sql:92` | condicion del WHERE | `ABS(x.viva_efectos) >= 1` -> `FALSE` | 2 | MUERTO |
| 216 | `06_views_contables.sql:106` | expresion | `s.proveedor_id` -> `NULL AS proveedor_id` | 1 | MUERTO |
| 217 | `06_views_contables.sql:107` | expresion | `s.proveedor_nombre` -> `NULL AS proveedor_nombre` | 1 | MUERTO |
| 218 | `06_views_contables.sql:108` | expresion | `s.obra_id` -> `NULL AS obra_id` | 1 | MUERTO |
| 219 | `06_views_contables.sql:109` | expresion | `s.empresa_id` -> `NULL AS empresa_id` | 1 | MUERTO |
| 220 | `06_views_contables.sql:110` | expresion | `s.codigo_obra` -> `NULL AS codigo_obra` | 1 | MUERTO |
| 221 | `06_views_contables.sql:111` | expresion | `s.clave_obra` -> `NULL AS clave_obra` | 1 | MUERTO |
| 222 | `06_views_contables.sql:112` | expresion | `s.nombre_obra` -> `NULL AS nombre_obra` | 1 | MUERTO |
| 223 | `06_views_contables.sql:113` | expresion | `s.saldo` -> `NULL AS saldo` | 1 | MUERTO |
| 224 | `06_views_contables.sql:114` | expresion | `s.ultimo_movimiento` -> `NULL AS ultimo_movimiento` | 1 | MUERTO |
| 225 | `06_views_contables.sql:115` | expresion | `f.fecha_fin_obra` -> `NULL AS fecha_fin_obra` | 1 | MUERTO |
| 226 | `06_views_contables.sql:116` | expresion | `f.fuente_fin_obra` -> `NULL AS fuente_fin_obra` | 1 | MUERTO |
| 227 | `06_views_contables.sql:117` | expresion | `f.plazo_meses` -> `NULL AS plazo_meses` | 1 | MUERTO |
| 228 | `06_views_contables.sql:118` | expresion | `f.fuente_plazo` -> `NULL AS fuente_plazo` | 1 | MUERTO |
| 229 | `06_views_contables.sql:119` | expresion | `f.fecha_vencimiento` -> `NULL AS fecha_vencimiento` | 1 | MUERTO |
| 230 | `06_views_contables.sql:120` | expresion | `CASE WHEN s.obra_id IS NULL THEN 'SIN_OBRA' WHEN f.fecha_vencimiento IS NULL THEN 'SIN_FIN...` -> `NULL` | 2 | MUERTO |
| 231 | `06_views_contables.sql:124` | expresion | `(f.fecha_vencimiento - CURRENT_DATE)` -> `NULL` | 1 | MUERTO |
| 232 | `06_views_contables.sql:125` | expresion | `f.terminada_sin_fin_obra` -> `NULL AS terminada_sin_fin_obra` | 1 | MUERTO |
| 233 | `06_views_contables.sql:127` | tipo de JOIN | `LEFT JOIN` -> `JOIN` | 2 | MUERTO |
| 234 | `06_views_contables.sql:127` | condicion del ON | `f.obra_id = s.obra_id` -> `TRUE` | 2 | MUERTO |
| 235 | `06_views_contables.sql:128` | condicion del WHERE | `s.saldo <> 0` -> `TRUE` | 2 | MUERTO |
| 236 | `06_views_contables.sql:46` | review S1 | `SUM(s.saldo) AS saldo_contable` -> `SUM(s.altas) AS saldo_contable` | 2 | MUERTO |
| 237 | `06_views_contables.sql:82` | review S2 | `(x.saldo_contable - x.viva_efectos)::NUMERIC(18, 2) AS diferencia` -> `(x.viva_efectos - x.saldo_contable)::NUMERIC(18, 2) AS diferencia` | 2 | MUERTO |
| 238 | `06_views_contables.sql:53` | review S3 | `-SUM(a.importe) AS prescrito` -> `SUM(a.importe) AS prescrito` | 1 | MUERTO |
| 239 | `06_views_contables.sql:62` | review S4 | `SUM(importe) AS viva_efectos` -> `COUNT(*) AS viva_efectos` | 1 | MUERTO |
| 240 | `06_views_contables.sql:124` | review S5 | `(f.fecha_vencimiento - CURRENT_DATE)` -> `(CURRENT_DATE - f.fecha_vencimiento)` | 1 | MUERTO |
| 241 | `06_views_contables.sql:113` | review S6 | `s.saldo,` -> `s.altas AS saldo,` | 1 | MUERTO |
| 242 | `06_views_contables.sql:47` | review S7 | `SUM(s.saldo_anterior_2016) AS` -> `SUM(s.saldo_inicial) AS` | 1 | MUERTO |
| 243 | `03_apuntes_contables.sql:128` | review S8 | `WHERE r.asiide <> 0 AND r.conide <> 0` -> `WHERE r.asiide <> 0` | 1 | MUERTO |
| 244 | `03_apuntes_contables.sql:213` | review S9 | `LEFT JOIN raw.con ob ON ob.ide = r.obra_id` -> `LEFT JOIN raw.con ob ON ob.ide = r.centro_coste_id` | 1 | MUERTO |
| 245 | `03_apuntes_contables.sql:208` | review S10 | `ob.emp::text \|\| '-' \|\| ob.cod` -> `ob.cod \|\| '-' \|\| ob.emp::text` | 1 | MUERTO |
| 246 | `04_saldo_contable.sql:48` | review S11 | `COUNT(*) FILTER (WHERE a.clase IN ('ALTA', 'BAJA', 'SALDO_INICIAL')) AS num_apuntes` -> `COUNT(*) AS num_apuntes` | 1 | MUERTO |
| 247 | `build_retenciones_step.py:75` | step: campo | `name="apuntes"` -> `name="apunte"` | 1 | MUERTO |
| 248 | `build_retenciones_step.py:76` | step: campo | `sql_file="03_apuntes_contables.sql"` -> `sql_file="03_apuntes.sql"` | 5 | MUERTO |
| 249 | `build_retenciones_step.py:78` | step: campo | `target_table="apuntes_contables"` -> `target_table="apuntes"` | 2 | MUERTO |
| 250 | `build_retenciones_step.py:81` | step: campo | `name="saldo"` -> `name="saldos"` | 1 | MUERTO |
| 251 | `build_retenciones_step.py:82` | step: campo | `sql_file="04_saldo_contable.sql"` -> `sql_file="04_saldo.sql"` | 5 | MUERTO |
| 252 | `build_retenciones_step.py:84` | step: campo | `target_table="saldo_contable"` -> `target_table="saldo"` | 2 | MUERTO |
| 253 | `build_retenciones_step.py:87` | step: campo | `name="fin_obra"` -> `name="fin"` | 2 | MUERTO |
| 254 | `build_retenciones_step.py:88` | step: campo | `sql_file="05_fin_obra.sql"` -> `sql_file="05_fin.sql"` | 5 | MUERTO |
| 255 | `build_retenciones_step.py:90` | step: campo | `target_table="fin_obra"` -> `target_table="fin"` | 2 | MUERTO |
| 256 | `build_retenciones_step.py:92` | step: campo | `name="views_contables"` -> `name="vistas"` | 1 | MUERTO |
| 257 | `build_retenciones_step.py:92` | step: campo | `sql_file="06_views_contables.sql"` -> `sql_file="06_views.sql"` | 4 | MUERTO |
| 258 | `build_retenciones_step.py:77` | step: esquema | `target_schema="retenciones"` -> `target_schema="cierre"` | 3 | MUERTO |
| 259 | `build_retenciones_step.py:83` | step: esquema | `target_schema="retenciones"` -> `target_schema="cierre"` | 3 | MUERTO |
| 260 | `build_retenciones_step.py:89` | step: esquema | `target_schema="retenciones"` -> `target_schema="cierre"` | 3 | MUERTO |
| 261 | `build_retenciones_step.py:74` | step: sub-paso quitado | `_SubStep( name="apuntes", sql_file="03_apuntes_contables.sql", target_schema="retenciones"...` -> (nada) | 3 | MUERTO |
| 262 | `build_retenciones_step.py:80` | step: sub-paso quitado | `_SubStep( name="saldo", sql_file="04_saldo_contable.sql", target_schema="retenciones", tar...` -> (nada) | 3 | MUERTO |
| 263 | `build_retenciones_step.py:86` | step: sub-paso quitado | `_SubStep( name="fin_obra", sql_file="05_fin_obra.sql", target_schema="retenciones", target...` -> (nada) | 4 | MUERTO |
| 264 | `build_retenciones_step.py:92` | step: sub-paso quitado | `_SubStep(name="views_contables", sql_file="06_views_contables.sql"),` -> (nada) | 3 | MUERTO |
