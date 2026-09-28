<!-- progress/impl_F-097.md -->
# F-097 · Informe del implementer

Rama `feature/F-097-descompuestos-partidas`. Rigor `estandar`. Spec
`specs/F-097-descompuestos-partidas/`, aprobada por el humano el 2026-09-27;
PARADA 1 confirmada el 2026-09-28 con el cambio de orden (T0 bloquea la puesta
en producción, no el código). Alcance de esta sesión: T1-T16 y T20.

## T1 · Decisiones D12-D15

Comprobado en `progress/current.md` (sección de F-097) y en
`progress/spec_F-097.md` («APROBADA POR EL HUMANO (2026-09-27)»): D12, D13, D14
y D15 aprobadas **según la recomendación** («ok» del humano); D14 fichada como
F-115. Ninguna se aparta de la recomendación: no hay nada que devolver a la
spec. Siguen abiertas con Negocio, sin bloquear: D8 (tipos 3 y 11, se publican
con la traducción del diseño y la ficha lo dice provisional) y D11 (D05DF210).

## T2 · Fase RED (trazas reales, 2026-09-28)

Cuatro ficheros de test escritos ANTES que el código: `test_f097_planificador.py`
(dominio: plan de relectura, plan de troceado y el espejo en Python del
troceado), `test_f097_ingesta_descompuestos.py` (paso de ingesta con dobles de
Sigrid y Postgres, y `reemplazar_filas` contra un doble de la conexión),
`test_f097_descompuestos.py` (SQL, paso de build, cableado, diccionario,
documentación) y `test_f097_tiemod_obrparpre.py` (R29).

Comando: `python -m pytest tests/test_f097_planificador.py tests/test_f097_ingesta_descompuestos.py tests/test_f097_descompuestos.py tests/test_f097_tiemod_obrparpre.py -q -p no:cacheprovider`

```
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.descompuestos'
ERROR tests/test_f097_planificador.py
ERROR tests/test_f097_descompuestos.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
```

Los otros dos ficheros, sueltos (`... test_f097_ingesta_descompuestos.py test_f097_tiemod_obrparpre.py -q`):
`34 failed, 2 passed in 2.49s` (los 2 que pasan fijan lo que NO debe cambiar:
la ingesta sigue en 71 tablas y la entrada `obrparpre` conserva sus demás campos).
Tres requisitos centrales, con `--tb=short`:

```
test_f097_r9_recuento_distinto_se_revierte_y_sigue
E   ImportError: cannot import name 'ingest_descompuestos_step' from 'etl_sigrid.application.steps'
test_f097_r8_reemplazar_filas_borra_copia_y_controla_en_una_transaccion
E   ImportError: cannot import name 'FilaControl' from 'etl_sigrid.infrastructure.postgres.postgres_client'
test_f097_r29_obrparpre_no_declara_tiemod
E   AssertionError: obrparpre no tiene tiemod en Sigrid (22 columnas, medido el 2026-09-27)
    assert 'tiemod' is None
```
