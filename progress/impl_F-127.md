<!-- progress/impl_F-127.md -->
# F-127 · Informe del implementer (rigor `critico`, pasada principal)

Worktree `.claude/worktrees/f127`, rama `feature/F-127-mayor-analitico` (base 177ef2d = `dev` 90d1bfd).
Spec aprobada el 2026-11-20: D1-D8 con lo recomendado (D7 = b). Sin `.env` en el worktree: la puerta
completa la pasa el líder (ver «Salida de init.sh»).

## Qué cambió (commits T1-T9 en la rama; T10 en `azure-apps`)

| Tarea | Commit | Qué |
|---|---|---|
| T1 | eb9047b | `domain/restriccion_personal.py`: `tipo_asiento`, `centros_de_contrapartida`, `es_cuenta_contrapartida` (D7-b), `FilaAnalitica`, `motivo_apunte_analitico` (CONTRAPARTIDA > APUNTE_SIN_RESOLVER > APUNTE_RESTRINGIDO > ASIENTO_PERSONAL), `es_apunte_analitico_restringido`, `obra_imputada` (D4) |
| T2 | 4c2d6f9 | `sql/contabilidad/08_mayor_analitico.sql`: `contabilidad_restringida.mayor_analitico`, 33 columnas, C1-C3 con D7-b, falla cerrado, obra por centro, obra imputada, acumulado completo y visible, PK, índices y guarda `v_mayor = v_apa` |
| T3 | b0ff2dc | `09_saldos_analitica.sql`: cuenta × centro × empresa × mes (`COALESCE` a 0), acumulado a fin de mes, PK |
| T4 | 9fc33bd | `10_mayor_analitico_general.sql`: solo `NOT restringido`, 29 columnas, guarda (0 CP, 0 apuntes restringidos, general + restringidas = completo) |
| T5 | db7ba83 | `11_saldos_analitica_general.sql` (`num_apuntes_restringidos`, `incompleto`) y `12_apuntes_analiticos_restringidos_mes.sql` (solo recuentos por motivo) |
| T6 | 883b276 | `build_contabilidad_step.py`: cinco `_SubStep` al final, docstring; cabecera de `00_setup.sql` |
| T7 | 8ae75df | `config/settings.py`: solo el comentario de D3 (ningún valor cambia); tests R19 |
| T8 | 67b58e5, 7e4597f | Diccionario v81: 2 fichas en `contabilidad_restringida.yaml`, 3 en `contabilidad.yaml`, `R-PERFILES` y `R-SALDO-CONTABLE` (solo `regla`), `raw.apa`, `apa` en el punto 3 de la regla de campos derivados; F-006 `design_detalle.md` (331 objetos); `current.md` con los recuentos |
| T9 | 0d4e70a | `docs/ARCHITECTURE.md` (párrafo «Desde F-127» y el punto «El mayor analítico y F-127» reescrito), `config/tables_sigrid.yaml` (comentario de `apa`) |
| T10 | `azure-apps` 70a039a | `datamart_seg_anual.md`: sección F-127 (SIN DESPLEGAR) y la fila de `contabilidad`. `git pull --rebase` antes: «Current branch main is up to date». Sin push |

### Decisiones y desviaciones (justificadas)

1. **D7-b al pie de la letra restringe 5.857 filas, no 324.** Las 7 cuentas antiguas de los centros de CP
   con abono `ANALITICO` se marcan ENTERAS (5.526 filas contables + 331 ANA, la última del 2026-11-02);
   frente a solo `caaconide` ocultan 3.087 filas más. Es lo que dice D7-b («también cuentan como CP»);
   las 324 de la spec eran solo los abonos. **Lo tiene que ver el humano** en la PARADA 2. Cambia las
   cifras esperadas de T13: 181.712 restringidas y 540.919 generales (no ~178.301 / ~544.330).
2. **Tests de F-056 y F-135 fijaban SUB_PASOS con exactamente ocho ficheros**: pasan a «los ocho de antes y
   detrás los cinco de F-127». Igual con las listas fijadas de F-141 (`NO_DISPONIBLES`) y F-146
   (tupla aparte `TABLAS_CONTABILIDAD_F127` solo para el test del diccionario: la comprobación final de
   `infra/sql/02_roles.sql` no cambia, el veto es del esquema entero). Ningún fichero ni
   columna de F-056/F-135 cambia.
3. **`R-PERFILES` tiene tope de 1.000 caracteres (regla + motivo, F-147)**: «el mayor analitico» va en
   el paréntesis de lo que el restringido no lee, y «CP: `contabilidad_restringida.mayor_analitico`.» detrás
   de la definición de «restringida» (F-146 prohíbe nombrar contabilidad entre «SI lee» y «restringida»).
   Para caber, el `motivo` gana «F-127» y pierde «Lo que falta, en cada ficha.» (ningún test lo pedía; lo
   dicen las fichas). Total 996. El `resumen` no cambia.
4. **Presupuesto de contexto de F-147** subido de 37.914 a 38.519 (+605, el medido), con su motivo en el
   historial del test: +18 en reglas, +587 de enrutado por cinco fichas recomendadas (preguntas acortadas).
   Lo tiene que ver el humano: es una subida de tope.
5. **Alias `caa` (no `ca`) para `raw.caa`** en las CTE de CP: con `ca` también para `raw.con` por LEFT
   JOIN, el test de nulos de F-006 creía que `codigo_cuenta_analitica` no podía ser NULL.
6. **T14 de `tasks.md` no corre en PostgreSQL** (FULL JOIN con `IS NOT DISTINCT FROM`): la versión buena,
   en `progress/current.md` «F-127 · pasos MANUAL».
7. **Documento del ecosistema**: la spec dice «sí» a la frontera y `CLAUDE.md` declara `azure-apps`:
   hecho (T10), solo `datamart_seg_anual.md`, commit aparte 70a039a, sin push.

## Validación en solo lectura contra Azure (2026-11-20, `filas_solo_lectura`, nada escrito)

El SELECT de cada fichero, como CTE, sobre el `raw` de la nocturna:

| Medida | Resultado |
|---|---|
| Mayor completo (08) | 722.631 filas = `raw.apa`; `apunte_analitico_id` único |
| Restringidas | 181.712 (CONTRAPARTIDA 173.978, APUNTE_RESTRINGIDO 7.734, ASIENTO_PERSONAL 0, SIN_RESOLVER 0; 998 cuentas) |
| General (10) | 540.919; guarda: `v_cp = 0`, `v_apunte = 0`, 540.919 + 181.712 = 722.631 |
| Saldos completos (09) | 182.449 filas, PK única; R13 (suma por cuenta mayor vs saldos): 0 discrepancias |
| Saldos generales (11) | 154.951 filas, 682 `incompleto`; `num_apuntes` suma 540.919 |
| Recuentos (12) | 701 filas, suman 181.712 |
| Obra imputada | 83.370 filas con obra imputada de 83.597 ANALITICO; sin fecha ni empresa nulas |
| Tiempos | SELECT de 08 ~28 s; los cinco encadenados ~65 s (estimación del coste nocturno: +1-3 min) |

## Fase RED (trazas reales, `python -m pytest -q tests/test_f127_mayor_analitico.py -k <tarea>`)

- **T1** (dominio, antes de las funciones): `ImportError: cannot import name 'MOTIVO_APUNTE_RESTRINGIDO'
  from 'etl_sigrid.domain.restriccion_personal'` — la colección entera cae.
- **T2** (antes de 08): `E AssertionError: SQL no encontrado: ...\sql\contabilidad\08_mayor_analitico.sql`
  → `54 failed`.
- **T3** (antes de 09):
  ```
  E       AssertionError: SQL no encontrado: ...\sql\contabilidad\09_saldos_analitica.sql
  4 failed, 66 passed, 44 deselected in 1.67s
  ```
- **T4** (antes de 10): `SQL no encontrado: ...10_mayor_analitico_general.sql` → `6 failed`.
- **T5** (antes de 11 y 12):
  ```
  E       AssertionError: SQL no encontrado: ...\contabilidad\11_saldos_analitica_general.sql
  E       AssertionError: SQL no encontrado: ...\contabilidad\12_apuntes_analiticos_restringidos_mes.sql
  6 failed, 140 deselected in 0.98s
  ```
- **T6** (antes de los sub-pasos):
  ```
  E       AssertionError: assert [] == [('mayor_anal...ingidos_mes')]
  E         Right contains 5 more items, first extra item: ('mayor_analitico', '08_mayor_analitico.sql', 'contabilidad_restringida', 'mayor_analitico')
  ```
  → `3 failed`.
- **T7** (antes del comentario de D3):
  ```
  E       AssertionError: D3: el comentario dice dónde nació
  E       assert 'F-127 nació en `contabilidad`' in ' (F-141), para administrativos: el TERCER perfil, ...'
  2 failed, 3 passed, 151 deselected in 2.43s
  ```
- **T8** (antes de las fichas): `23 failed, 156 deselected in 8.00s` (KeyError de las fichas, `version`
  80 ≠ 81, `R-PERFILES` sin `contabilidad_restringida.mayor_analitico`).
- **T9** (R24, con ARCHITECTURE y tables_sigrid de la base):
  ```
  E           AssertionError: ARCHITECTURE.md no dice «Desde F-127»
  E       AssertionError: assert ('F-127' in '\n    target_table: apa\n ...
  2 failed, 1 skipped, 179 deselected in 1.12s
  ```
  y, con los cambios, `2 passed, 1 skipped` (el tercero salta en el worktree porque `azure-apps` no está
  junto a él; en el checkout principal sí corre).

## Salida de `init.sh` (T17)

**No se ejecuta la puerta completa en el worktree**: no tiene `.env`, y 22 tests de
`test_f006_comandos.py` (CLI) más `test_f006_reglas.py::...frescura_cita_el_pipeline_real` caen por
`SigridApiSettings: base_url / function_key Field required`. Comprobado que es ajeno a F-127: los mismos
22 fallan en un worktree limpio de la base 177ef2d. **La puerta completa (`bash harness/init.sh`) la pasa
el líder** en el checkout con `.env`, con las líneas `PUERTA CARRIL` y `PUERTA COBERTURA`.

**Batería de lo afectado** (worktree, 2026-11-20, tras el último commit 7e4597f):
`python -m pytest -q tests/test_f127_mayor_analitico.py tests/test_f006*.py tests/test_f147*.py
tests/test_f149*.py tests/test_f135*.py tests/test_f056_contabilidad.py tests/test_f107*.py tests/test_f141*.py
tests/test_f146*.py tests/test_f040_diccionario.py tests/test_f037_diccionario.py tests/test_f128_diccionario.py
tests/test_f138_diccionario.py tests/test_f136_login_total.py tests/test_backlog_md.py tests/test_estados.py
tests/test_documentos_del_arnes.py tests/test_init_sh_estados.py`

- Pasada completa (antes de los dos últimos arreglos): `24 failed, 4210 passed, 392 skipped in 858.95s`;
  22 eran los de `.env` de arriba y 2 (F-141 r26 y F-146 r4) se arreglaron en 7e4597f.
- Repasada de lo tocado por 7e4597f (F-141, F-146, F-147, F-127, F-135, F-136, F-040, F-037, F-128,
  F-138, F-006 reglas/fuente/contexto): `1 failed, 1146 passed, 13 skipped in 338.99s`; el único fallo es
  el de frescura por `.env`. F-147 de nuevo tras fijar el tope: `106 passed`.
- `tests/test_f127_mayor_analitico.py`: `181 passed, 1 skipped in 8.27s` (el skip es R24 de `azure-apps`).
- `ruff` limpio en lo tocado (salvo el `I001` previo de F-146, ver «Qué quedó fuera»).

## Verificaciones MANUAL pendientes (humano)

T12-T16, con sus comandos exactos y las cifras esperadas corregidas, en `progress/current.md`, sección
«F-127 · pasos MANUAL». Push del humano: la rama y el commit 70a039a de `azure-apps` (`pull` y `push`).

## Qué quedó fuera

- Sin esquemas, roles, grants, variables ni endpoints nuevos; `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`
  sigue vacía (D3).
- La caja ni el cruce CP ↔ partes como objeto: la receta R23 está en la ficha, no en una vista.
- Lint: `tests/test_f146_restringido_sin_contabilidad.py` arrastra un `I001` de antes (verificado sobre
  8ae75df); no se toca.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-127 | 181 passed, 1 skipped, 8,27 s |
| Batería de lo afectado | 4.210 passed / 24 failed (22 `.env`, 2 arreglados) en 858,95 s; repasada 1.146 passed, 1 failed (`.env`) en 338,99 s |
| Cobertura (coverage.py sobre los tests de F-127 y F-135) | `restriccion_personal.py` 100 % (89/89); `build_contabilidad_step.py` 82 % (líneas 204-225 sin cubrir: el `execute` contra la base, que no toca F-127). La línea `PUERTA COBERTURA` la da el portero completo del líder |
| Mutación del SQL (a mano, scratchpad `mutar_sql.py`) | 34 mutantes en 08-12 (tipos de asiento, C1-C3, D7-b, precedencia de motivos, falla cerrado, guardas, filtros, acumulados, recuentos): **34 muertos, 0 supervivientes** con `pytest -x tests/test_f127_mayor_analitico.py` |
| Campaña `python -m harness.mutacion --feature F-127` | **PENDIENTE de la pasada de campaña**: según `implementer.md`, el líder me relanza tras el APPROVED del reviewer (2 h+ con `--timeout 2400`). Entonces se analiza cada superviviente aquí |
| Capa e2e | N/A: ETL sin interfaz (no hay requisitos `(capa: e2e)` en la spec) |
| Validación en Azure (solo lectura) | Tabla de arriba: 722.631 / 540.919 / 181.712, guardas a 0, R13 0 discrepancias |
