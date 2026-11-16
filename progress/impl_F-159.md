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

Verde (tras T2-T5), mismo comando: `19 passed`. Caso real: `[(2026-11, 0.00), (2026-12, 1080.00)]`.

## Commits

| Tarea | Commit | Qué |
|---|---|---|
| — | `b8c3515` | merge de `main` `70d4df7` (conflicto en `progress/current.md` resuelto) y F-159 `in_progress` |
| T1 | `f664d39` | tests nuevos (RED) y los de F-140/F-150/F-157/F-158 a la fórmula nueva |
| T2 | `4966c73` | `repartir_pendiente` por acumulado sobre la envolvente |
| T3 | `9d416ee` | paso 5 del SQL: `envolvente`, `partes`, `repartido`, cabecera y comentario de 5 bis |
| T4 | `314c204` | guarda nueva tras `_dev_reparto` y R50 con su primera fila negativa |
| T5 | `5166c0b` | fichas de `tesoreria.yaml` y diccionario v74 |
| T6/T8 | (el de este informe) | mutación manual, cobertura, `init.sh` |

## Ficheros tocados

- `etl_sigrid/domain/proyeccion_caja.py`: `repartir_pendiente` reescrita (misma firma) y el
  párrafo del docstring del módulo. `repartir_personal`, sin cambios.
- `etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql`: paso 5
  (`envolvente` nueva; `partes` y `repartido` reescritos; `perfil`, `repartido_personal`,
  `sin_perfil` y el `UNION ALL`, iguales), guarda nueva (R9) entre `ANALYZE _dev_reparto` y
  `TRUNCATE tesoreria.devengo_pendiente_obra_mes`, mensaje de R50 (R10), cabecera (punto 5) y
  comentario de 5 bis paso 3.
- `config/diccionario/tesoreria.yaml`: `importe_pendiente` de `devengo_pendiente_obra_mes`, el
  párrafo «EL DEVENGO PENDIENTE, MES A MES» de su descripción y el párrafo «No es caja» de
  `devengo_pendiente_contrato_mes`. `config/diccionario/00_global.yaml`: `version: 74` y su nota.
- Tests: nuevo `tests/test_f159_reparto_envolvente.py` (19 tests). Actualizados sin perder lo
  que defienden: `test_f140_dominio.py` (100/3 → 33,33 / 33,34 / 33,33; un test renombrado a
  `..._el_redondeo_va_por_acumulado`), `test_f140_sql.py` (renombrado a
  `..._por_acumulado_y_el_ultimo_mes_entero`), `test_f150_sql.py`, `test_f150_personal.py`,
  `test_f150_coeficiente.py` (743,48 / 122,68 → 743,49 / 122,67), `test_f158_reparto_personal.py`
  (RED de F-158 con copia privada del algoritmo de `fbf43dd`; el último mes de 392521 pasa de
  8.249,97 a 8.249,99; la frase de la ficha del contrato, ahora ausente) y
  `test_f157_diccionario.py` (`== 73` → `>=`).
- `harness/features.json` (F-159 `in_progress`), `specs/.../tasks.md` (T1-T6 `[x]`),
  `progress/current.md`.
- `azure-apps/datamart_seg_anual.md` NO cambia: mismo contrato publicado (columnas, clave y
  objetos iguales; design §1).

## Decisiones y desviaciones

1. **Alias `r` en `repartido`** (design §3.1 usa `p`): así siguen intactas las aserciones de
   F-158 sobre `r.pendiente AS pendiente_partida` y `FROM repartido_personal r`. Mismo SQL.
2. **R50 con variables escalares `TEXT`** en vez de un `RECORD`: un `SELECT ... INTO` sin filas
   deja NULL en escalares de forma garantizada (con `n_obras > 0` y sin negativos la «primera»
   sale NULL, como pide design §3.3). La consulta va DENTRO del `IF`: no cuesta nada en verde.
3. **La guarda nueva solo mira `pendiente` y el personal** (lo de R9), no `importe_con_coef`:
   la spec no lo pide. Con `pendiente_con_coeficientes` ≥ 0 el reparto con coeficientes tiene
   la misma garantía por construcción (misma envolvente, mismo acumulado).
4. **Dos `in_progress` en `features.json`** (F-157 y F-159), por orden expresa del líder: F-157
   la cierra él aparte. `init.sh` lo marca en su sección 3 (ver «Evidencias»).
5. **Mutación manual con la suite acotada**, como F-158 (su desviación 5): la línea base de
   `python -m harness.mutacion` corre la suite entera (~1 h) y aquí sale ROJA sin `.env`
   (`test_f006_t26`), así que la campaña del arnés no puede arrancar. Sus números no son
   comparables con los de una campaña del arnés.
6. Tests añadidos a los de design §5: de R1, negativo al final, el mínimo mira hacia delante
   (50/-10/30/-60/100) y suelo 0 con perfil desordenado; de R2, multiplicar antes de dividir y
   el último mes sin redondear (matan D11 y D10).

## Mutación (T6)

Alcance: `repartir_pendiente` (D1-D17) y el SQL de F-159 (M1-M10: los cinco de design §5 y
cinco más). Un cambio textual por mutante; suite acotada con `-x` a `test_f159_reparto_envolvente`,
`test_f140_dominio`, `test_f140_sql`, `test_f150_coeficiente`, `test_f150_sql`,
`test_f150_personal`, `test_f150_contrato_compra` y `test_f158_reparto_personal`; el fichero se
restaura tras cada mutante y `git status` sale limpio al final. Script: `mutar.py` del
scratchpad de la sesión. **27 generados, 26 muertos, 1 superviviente (equivalente)**, 46,1 s.

| Mutante | Lo caza |
|---|---|
| D1 `pendiente == 0` → `!= 0` | `r6_el_caso_1_0710` |
| D2 `total <= 0` → `< 0` (neto 0 se reparte) | `r5_neto_no_positivo` |
| D3 perfil `plan != 0` → `> 0` (la alternativa P) | `r6_el_caso_1_0710` |
| D4 `suma += plan` → `=` (sin acumulado) | `r1_la_envolvente_absorbe` |
| D5 el mínimo arranca en el primer acumulado | `r1_un_negativo_al_final` |
| D6 `min` → `max` | `r6_el_caso_1_0710` |
| D7 sin suelo 0 | `r6_el_caso_1_0710` |
| D8 barrido hacia delante en vez de inverso | `r1_la_envolvente_absorbe` |
| D9 sin envolvente (solo suelo 0 al acumulado) | `r1_la_envolvente_absorbe` |
| D10 el último mes también redondeado | `r2_el_ultimo_mes_es_el_pendiente_sin_redondear` |
| D11 dividir antes de multiplicar | `r2_multiplica_antes_de_dividir_como_el_sql` |
| D12 sin `_redondear` | `r2_la_formula_por_acumulado` |
| D13 sin restar lo de hasta el mes anterior | `r1_la_envolvente_absorbe` |
| D14 `anterior` no avanza | `r1_la_envolvente_absorbe` |
| D15 `ultimo` fuera de rango | `r2_el_ultimo_mes_es_el_pendiente_sin_redondear` |
| D16 sin perfil, `es_retraso` falso | `r5_neto_no_positivo` |
| **D17 `not meses or total <= 0` → `total <= 0`** | **superviviente** |
| M1 `MIN` → `MAX` en la envolvente | `r8_el_sql_sigue_al_dominio` |
| M2 sin `GREATEST(0,` | `r8` |
| M3 `DESC` → `ASC` en la envolvente | `r8` |
| M4 el último mes con `ROUND` en vez de `d.pendiente` | `r8` |
| M5 sin la guarda nueva | `r9_la_guarda_nueva` |
| M6 `importe` = `hasta` (sin `LAG`) | `r8` |
| M7 la guarda sin `importe_personal > pendiente` | `r9` |
| M8 R50 ordena `DESC` (la menos negativa) | `r10_r50_nombra_su_primera_fila_negativa` |
| M9 el plan acumulado en orden `DESC` | `r8` |
| M10 `importe_con_coef` sin `LAG` | `r8` |

**D17, equivalente.** Sin meses, `total` es la suma vacía, 0, y `total <= 0` ya es cierto: la
rama sin perfil se toma igual. `not meses` solo deja escrita la intención; ningún test puede
distinguirlo. No es un hueco.

M1-M10 los caza la lectura del texto del SQL, no una ejecución (sin sandbox, D6). La garantía
de que el SQL hace lo que el dominio es la letra (R8) más la reproducción en solo lectura del
paso 0 bis MANUAL.

## Verificaciones MANUAL pendientes (T7, el humano)

Todas las de `design.md` §6, tras APROBADO y merge a `main`: tag actual del job, **reproducción
en solo lectura** del paso 5 nuevo con los datos del día (0 meses y 0 agregados negativos),
imagen, job, `build-tesoreria` suelto, `apply-grants`, las consultas de §6 paso 4 (0 negativos
en `devengo_pendiente_contrato_mes` y en `devengo_pendiente_obra_mes`; 1-0710 COSTE con todos
los meses ≥ 0 y ≤ su pendiente; `build_tesoreria` SUCCESS hoy), `publicar-diccionario` → v74,
`check-diccionario`, `check-declarados`, reinicio del MCP y la nocturna siguiente. **La sintaxis
del SQL nuevo** (`WINDOW w`, `LAG ... OVER w`, `MIN ... OVER (... ROWS ...)` dentro de
`GREATEST`, el `SELECT ... INTO` de escalares de R50) **no se ha ejecutado contra un
PostgreSQL**: lo hará la primera ejecución del paso 0 bis, antes de construir la imagen.

Fuera del alcance (design §7): `stg`, `perfil`, `_dev_partida`, `repartir_personal`, 5 bis, las
condiciones de R14/R50/R58, `importe_plan_restante`, `10_saldo_partida.sql`, `mart`, `cierre`.

## `bash harness/init.sh` (T8: ROJO en el worktree, por el entorno)

Ejecutado tal cual el 2026-11-07 sobre `5166c0b` (código completo; el informe, aún sin commit): **4 comprobaciones
fallidas**, ninguna del código de F-159:

- `Hay 2 features in_progress (F-157, F-159). Máximo 1.`: la orden del líder (desviación 4).
- `Falta .env`: prohibido crearlo en el worktree.
- `pytest`: `1 failed, 256 passed in 307.37s`, se para (`-x`) en
  `test_f006_comandos.py::test_f006_t26_cli_dry_run_no_toca_la_base` (el `.env`).
- `PUERTA COBERTURA: 0.0% de 16 líneas` porque ese pytest `-x` se para antes de llegar a los
  tests de F-159; medida aparte, 100 % (abajo).
- En verde: `PUERTA TAMAÑO: F-159 dentro de los topes (requirements 72/150, design 208/250,
  impl 166/220)` y la rama.

T8 queda sin marcar: la puerta completa la pasa el líder en una copia con `.env`.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de los ficheros afectados (F-159, F-158, F-150, F-140, F-147, F-149) | `python -m pytest tests/test_f159*.py tests/test_f158*.py tests/test_f150*.py tests/test_f140*.py tests/test_f147*.py tests/test_f149*.py -q`: **1215 passed, 1 skipped in 37.30s** |
| Tests de F-006 (diccionario) | `python -m pytest tests/test_f006*.py -q --deselect ...::test_f006_t26_cli_dry_run_no_toca_la_base`: **2725 passed, 306 skipped, 21 failed in 8137.69s (2:15:37)**. Los 21 son `test_f006_comandos.py` (t26, t40, r28: el CLI) y `test_f006_reglas.py::test_f006_r9_la_regla_de_frescura_cita_el_pipeline_real`, TODOS con `ValidationError: 2 validation errors for SigridApiSettings (base_url, function_key: Field required)`: el `.env` que falta. Ninguno toca F-159 |
| F-157 (versión del diccionario) | `test_f157_diccionario.py`: verde con la v74 (`>=`), dentro de los 90 de T5 |
| Fichero nuevo | `tests/test_f159_reparto_envolvente.py`: **19 passed in 0.8 s** (RED: 13 failed, 6 passed) |
| Cobertura de las líneas cambiadas | `coverage run -m pytest tests/test_f159_reparto_envolvente.py tests/test_f140_dominio.py tests/test_f150_coeficiente.py tests/test_f158_reparto_personal.py` + `coverage json` + `python -m harness.cobertura --base main --config harness/rigor.json`: **`PUERTA COBERTURA: 100.0% de 16 líneas cambiadas cubiertas (16/16, umbral 80%, nivel estandar; diff desde 70d4df75a1, merge-base con main)`** |
| Mutantes | **27 generados, 26 muertos, 1 superviviente equivalente (D17)**; manual, suite acotada, 46,1 s (desviación 5) |
| Tiempo de la suite | ficheros afectados 37,3 s; F-006 2 h 15 min (sin `.env`, con la máquina compartida por `init.sh` y la cobertura parte del tiempo); `init.sh` hasta su `-x`, 307 s |

`ruff check` sobre `proyeccion_caja.py`: 1 aviso PREEXISTENTE (`RUF002`, el `×` de
`iva_efectivo_compra`, línea 331, también en `93fc38c`); nada nuevo.

Falta para cerrar: la puerta completa del líder con `.env`, el review contra `CHECKPOINTS.md`,
el merge y el despliegue MANUAL (T7). Aviso para el reviewer: F-006 tarda más de 2 h en esta
máquina.
