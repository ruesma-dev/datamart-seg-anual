<!-- progress/impl_F-159.md -->
# F-159 · Informe del implementer · Hotfix 2: reparto por acumulado sobre la envolvente

Implementer, 2026-11-07, en el worktree del agente (rama `feature/F-159-hotfix-devengo-negativo-2`,
`main` `70d4df7` mergeada). Rigor `estandar`. Spec aprobada por el humano: D1 = A (envolvente
neta), D2 = acumulado, D3 = guarda nueva + R50 con su primera fila, D4 = R50 no se relaja, D5 =
v74, D6 = sin sandbox. Nada escrito contra Azure ni Sigrid; no hizo falta leer Azure (la
reproducción en solo lectura es el paso 0 bis MANUAL de `design.md` §6).

## Fase RED (T1)

Tests escritos ANTES que el código, sobre el árbol en `b8c3515` (= `93fc38c` + el merge de
`main`, sin código de F-159). Comando exacto:

```
python -m pytest tests/test_f159_reparto_envolvente.py -q -p no:cacheprovider
```

Salida (recortada a las líneas del fallo; `python` = el `.venv` del checkout principal):

```
>       assert reparto == [(NOV, D("0.00"), False), (DIC, D("1080.00"), False)]
E         At index 0 diff: (datetime.date(2026, 11, 1), Decimal('-19438920.00'), False) != (datetime.date(2026, 11, 1), Decimal('0.00'), False)
tests\test_f159_reparto_envolvente.py:80: AssertionError                       <- R6, el caso 404326
E         At index 0 diff: Decimal('60.00') != Decimal('0.00')                  <- R1, 100/-100/100
E         At index 0 diff: (datetime.date(2026, 11, 1), Decimal('-20.00'), False) != (... Decimal('0.00'), False)  <- R1, suelo 0
>               assert D(0) <= importe <= pendiente, caso
E               assert Decimal('533801.47') <= Decimal('348332.75')            <- R3, invariantes con signo
E       AssertionError: assert 'SUM(pr.importe_mes) OVER (PARTITION BY pr.obra_id, pr.concepto, pr.partida_id ORDER BY pr.anio_mes) AS plan_acumulado' in 'CREATE TEMP TABLE _dev_reparto ...'   <- R8
E       AssertionError: assert 'por ACUMULADO sobre el plan NETO acumulado de V' in '-- etl_sigrid/...'  <- R8 cabecera
E       AssertionError: assert 'WHERE pendiente < 0 OR importe_personal < 0 OR importe_personal > pendiente' in 'ANALYZE _dev_reparto; '  <- R9
E       assert 'SELECT obra_id, anio_mes, categoria, contrato_id, importe_pendiente INTO neg_obra, ...' in "TRUNCATE tesoreria.devengo_pendiente_contrato_mes; ... importes negativos', n_obras, n_negativos; END IF; "  <- R10
E       AssertionError: assert 'plan neto acumulado de v' in 'pendiente repartido en ese mes: lo que se proyecta devengar. sin iva.'  <- R12
E       AssertionError: assert 73 >= 74                                          <- R12 versión
13 failed, 6 passed in 0.79s
```

El caso real da **-19.438.920,00** en 2026-11 con el algoritmo de `93fc38c`, exactamente el del
diagnóstico. `test_f159_r6_el_algoritmo_de_ayer_amplificaba` lo deja escrito (copia privada del
algoritmo: -19.438.920,00 / +19.440.000,00, suma 1.080,00: por eso R14 pasaba y cayó R50). Los
6 que pasan en RED son los que el algoritmo viejo ya cumplía (R4, R5, R11, multiplicar antes de
dividir, el último mes sin redondear y la copia privada).

Con los tests de F-140/F-150/F-158 actualizados a la fórmula nueva (design §2), la batería
afectada en RED: `22 failed, 420 passed` (los 13 de arriba + 9 de los ficheros viejos).
