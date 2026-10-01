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
