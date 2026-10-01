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
