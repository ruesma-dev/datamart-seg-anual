<!-- progress/impl_F-158.md -->
# F-158 · Informe del implementer · Hotfix del céntimo negativo en el coste por contrato

Implementer, 2026-11-05 (15:35-17:10 UTC). Worktree `agent-a14bcd52abad383f8`, rama
`feature/F-158-hotfix-devengo-negativo`; rigor `estandar`. Spec aprobada en la PARADA 1 con
D1 = A, D2 = fuera, D3 = v72 y D4 = sin sandbox. Sin lecturas a Azure (el worktree no tiene
`.env`; el diagnóstico de `progress/spec_F-158.md` ya estaba medido). Nada escrito fuera del
worktree. Sin push.

## Commits (uno por tarea)

| Tarea | Commit | Qué |
|---|---|---|
| T1 | `4e46f0f` | `tests/test_f158_reparto_personal.py` (nuevo) y `test_f150_r46_el_reparto_lleva_la_parte_de_personal` actualizado; RED |
| T2 | `2850a2d` | `repartir_personal` en `etl_sigrid/domain/proyeccion_caja.py` |
| T3 | `eb74891` | `07_devengo_pendiente.sql`, paso 5: `repartido_personal` por acumulado; cabecera, COMMENT y una línea de comentario de `00_setup.sql` |
| T4 | `456019d` | fichas de `tesoreria.yaml`, `00_global.yaml` v72 con su nota, errata de `postventa.yaml`, `test_f156_r34` a `>=` |
| T5 | `b7c091d` | dos tests que matan los dos supervivientes de la mutación |

T6 (despliegue) es MANUAL del humano; T7 (`init.sh`), abajo.

## Ficheros tocados

- `etl_sigrid/domain/proyeccion_caja.py`: `repartir_personal(reparto, pendiente,
  pendiente_personal)`, pura. Por mes, `_redondear(pp x A(m) / p) - _redondear(pp x A(m-1) /
  p)`; `pendiente == 0` → `[]`. Docstring con el caso 392521 y la garantía de R2-R3.
- `etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql`, paso 5:
  - `partes` ya no calcula `parte_personal`; `repartido` ya no reparte el personal (fuera
    `suma_partes_personal`) y lleva `r.pendiente AS pendiente_partida` y `r.pendiente_personal`;
  - CTE nueva `repartido_personal` con la fórmula de design §3 y la ventana
    `SUM(x.importe) OVER (PARTITION BY obra, concepto, partida ORDER BY x.anio_mes)`;
  - la rama del `UNION ALL` lee `repartido_personal r`. `perfil`, `sin_perfil`, las guardas, 5
    bis y todo lo demás, intactos.
  - Comentarios: cabecera F-150 N16 punto 5 y el de la CTE. El `COMMENT ON TABLE` de
    `devengo_pendiente_obra_mes` cambia «(mismo reparto)» por «repartido por acumulado sobre
    importe_pendiente (F-158): nunca lo supera en un mes» (es metadato, no DDL de columnas).
- `etl_sigrid/infrastructure/postgres/sql/tesoreria/00_setup.sql`: SOLO el texto de un
  comentario SQL de la línea 561 (`-- ...`), sin cambio de DDL.
- `config/diccionario/tesoreria.yaml`: `importe_pendiente_personal` de
  `devengo_pendiente_obra_mes` («repartido por acumulado sobre `importe_pendiente` (F-158): nunca
  lo supera en un mes…») y la descripción de `devengo_pendiente_contrato_mes` («ninguna fila con
  contrato es negativa, y la fila sin contrato solo es negativa por un mes negativo del plan de la
  version (F-158…)»).
- `config/diccionario/00_global.yaml`: `version: 72` con su nota `# version 72 (F-158, 2026-11-05)`.
- `config/diccionario/postventa.yaml`: «lA MASCARA ES HEURISTICA» → «la mascara es heuristica».
- `tests/test_f158_reparto_personal.py` (nuevo, 19 tests), `tests/test_f150_personal.py` (R46),
  `tests/test_f156_diccionario.py` (R34).
- `azure-apps/datamart_seg_anual.md`: NO cambia (mismo contrato publicado: ni objetos, ni
  columnas, ni tipos; cambian céntimos de una columna que ya se publica).

## Decisiones y desviaciones (justificadas)

1. **El plan de 392521 es una reconstrucción.** spec_F-158 §2 da los cinco importes del plan
   (3.264 / 4.896 / 8.976 / 8.160 / 4.080), no los doce meses. Sin `.env` no se puede releer
   Azure. Busqué por fuerza bruta todas las combinaciones de 12 meses con esos importes y el último
   en 8.160: la única que da los céntimos medidos (8.249,97 / 8.250,02 en 2027-10, y 3.300,00
   frente a 3.299,99 en los meses de 3.264) es **3.264 x 7, 4.896, 8.976, 8.160, 4.080, 8.160**,
   que es además el orden en que la spec los cita. Fixture con esos números; el comentario del
   test lo dice.
2. **`test_f156_r34_la_version_sube_en_uno` (de F-156)** fijaba `version == 71`, así que
   cualquier subida lo rompía. Pasa a `>= 71` más la nota `# version 71 (F-156, 2026-11-`: es el
   patrón de F-153 (`>= 70` + nota) y de F-155. Lo que defiende F-156 sigue fijado. Es un test de
   otra feature: lo anoto para el reviewer.
3. **La errata se escribe sin tildes**, «la mascara es heuristica», y no «la máscara»:
   `postventa.yaml` no tiene ni una tilde y sigue la convención ASCII de los YAML del
   diccionario. El test acepta las dos formas.
4. **`features.json` no se toca.** F-156 sigue `in_progress` en el árbol (ya fusionada), e
   `init.sh` admite como máximo una `in_progress`. El estado de F-158 lo lleva el líder.
5. **La mutación es manual y con la suite acotada**, no `python -m harness.mutacion`: su línea
   base corre la suite entera (~1 h 07 min, F-156), y aquí sale ROJA por el `.env`, así que la
   campaña no puede ni arrancar. Detalle en «Evidencias».
6. Lo que la spec dejaba abierto en R10, la frase de la ficha del contrato, se redacta de forma
   que diga también que ninguna fila CON contrato es negativa: es lo que garantiza R50.

## Fase RED (contra `fbf43dd`)

Comando: copia de `etl_sigrid/`, `config/` y `tests/` de `fbf43dd` (`git archive fbf43dd`) en el
scratchpad, más los tests NUEVOS de T1, y desde ahí:
`.venv/Scripts/python.exe -m pytest tests/test_f158_reparto_personal.py tests/test_f150_personal.py -q -p no:cacheprovider --tb=line`

```
E   AttributeError: module 'etl_sigrid.domain.proyeccion_caja' has no attribute 'repartir_personal'. Did you mean: 'partir_personal'?
...test_f158_reparto_personal.py:84: AttributeError:     (r6 caso 1-0707; y r1, r2_r3, r4, r5)
E   AssertionError: assert 'ROUND(q.pendiente_personal * q.acumulado / q.pendiente_partida, 2) - ROUND(q.pendiente_personal * (q.acumulado - q.importe) / q.pendiente_partida, 2) AS importe_personal' i
...test_f158_reparto_personal.py:193: AssertionError:    (r7 el SQL sigue al dominio)
E   AssertionError: assert 'por acumulado sobre el pendiente del mes (F-158)' in '-- etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql ====...
E   AssertionError: assert 'repartido por acumulado sobre `importe_pendiente`' in 'la parte de personal propio de `importe_pendiente` en el mes (el mismo reparto). se paga en dos tramos, sin plazo, re
E   AssertionError: assert 71 >= 72
E   AssertionError: assert 'lA MASCARA' not in '# config/di...guntas: []\n'
E   assert 'ROUND(q.pendiente_personal * q.acumulado / ...' in " DO $$ BEGIN ...     (test_f150_r46, actualizado)
FAILED tests/test_f158_reparto_personal.py::test_f158_r6_el_caso_1_0707_no_da_personal_mayor_que_pendiente
FAILED tests/test_f158_reparto_personal.py::test_f158_r1_la_formula_por_acumulado
FAILED tests/test_f158_reparto_personal.py::test_f158_r1_sin_pendiente_no_hay_reparto
FAILED tests/test_f158_reparto_personal.py::test_f158_r2_r3_invariantes - Att...
FAILED tests/test_f158_reparto_personal.py::test_f158_r4_cuota_uno_y_cero - A...
FAILED tests/test_f158_reparto_personal.py::test_f158_r5_sin_perfil_una_fila
FAILED tests/test_f158_reparto_personal.py::test_f158_r7_el_sql_sigue_al_dominio
FAILED tests/test_f158_reparto_personal.py::test_f158_r7_la_cabecera_lo_dice
FAILED tests/test_f158_reparto_personal.py::test_f158_r10_fichas - AssertionE...
FAILED tests/test_f158_reparto_personal.py::test_f158_r10_version_72_con_su_nota
FAILED tests/test_f158_reparto_personal.py::test_f158_la_errata_de_postventa
FAILED tests/test_f150_personal.py::test_f150_r46_el_reparto_lleva_la_parte_de_personal
12 failed, 41 passed in 1.20s
```

El fallo del ALGORITMO de ayer, y no solo la ausencia de la función, queda escrito de dos formas:

- `test_f158_r6_el_algoritmo_de_ayer_daba_el_negativo`, en verde a propósito: dos
  `repartir_pendiente` independientes dan `8249.97` y `8250.02` en 2027-10, es decir -0,05.
- El generador de `test_f158_r2_r3_invariantes` (semilla 20261105, 2.000 casos) con el
  algoritmo de `fbf43dd`, script del scratchpad: `casos 2000 con personal > pendiente en algun
  mes: 18`; ejemplo `(209653.78, 0.999999, [(7179.38, 7179.39)])`.

Verde, tras T2-T3: el caso 392521 mes a mes, pendiente / personal nuevo / personal de ayer:
3.300,00 / 3.300,00 o 3.299,99 / 3.299,99 en los siete de 3.264; ...; **2027-10: 8.249,97 /
8.249,96 / 8.250,02**. `pendiente - personal` va de 0,00 a 0,01 en cada mes y suma 0,06, la
diferencia a nivel de partida. Antes era 0,01 en once meses y -0,05 en el último.

## Tests (resultado real)

- `pytest tests/test_f158_reparto_personal.py tests/test_f147_*.py tests/test_f149_*.py
  tests/test_f150_*.py tests/test_f140_*.py tests/test_f153_*.py tests/test_f155_*.py
  tests/test_f156_*.py` (antes de T5): **1459 passed, 7 skipped en 70,9 s**. Tras T5,
  `test_f158_reparto_personal.py`: **19 passed**; con `test_f150_personal.py`, **56 passed**.
- `pytest` de 11 ficheros de F-006 (fichas, formato, catálogo, cobertura, reglas, unicidad,
  publicación, contexto, punteros, relaciones, docs): **1749 passed, 301 skipped, 1 failed en
  412,96 s**. El rojo es `test_f006_reglas.py::test_f006_r9_la_regla_de_frescura_cita_el_pipeline_real`,
  con `ValidationError: 2 validation errors for SigridApiSettings (base_url, function_key: Field
  required)`. Es el `.env`: **falla igual sobre `fbf43dd`** (lo comprobé en la copia del
  scratchpad: `1 failed`).
- `bash harness/init.sh`: ver la sección siguiente.

## `bash harness/init.sh`

Ejecutado tal cual en el worktree (17:52-18:06 UTC): **3 comprobaciones fallidas, las tres por el
`.env`** que el worktree no tiene (y no se puede crear):

```
[KO] Falta .env — copiar de .env.example
FAILED tests/test_f006_comandos.py::test_f006_t26_cli_dry_run_no_toca_la_base
1 failed, 256 passed, 27 warnings in 832.94s (0:13:52)
[KO] pytest en rojo (¿pytest instalado en el venv?)
[KO] PUERTA COBERTURA: 8.3% de 12 líneas cambiadas cubiertas (1/12, ...)
[OK] PUERTA TAMAÑO: F-158 dentro de los topes (requirements 58/150, design 145/250, impl 201/220)
```

El único test rojo es el del `.env` (`SigridApiSettings`). La cobertura de 1/12 sale de ahí:
pytest corre con `-x`, se para en `test_f006_t26` y nunca llega a los tests de F-158. Medida
aparte (ver «Evidencias»), da 12/12. Compilación, `features.json`, `BACKLOG.md`, `rigor.json` y
la rama, en verde. Ruff: 286 avisos de deuda previa; los ficheros que toca F-158 no añaden
ninguno. **La puerta completa la tiene que pasar el líder en un checkout con `.env`.**

## Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados | 1459 passed / 7 skipped (F-140, F-147, F-149, F-150, F-153, F-155, F-156, F-158) + 1749 passed / 301 skipped / 1 failed por `.env` (F-006); `test_f158_*` 19/19 |
| Cobertura de las líneas cambiadas | `PUERTA COBERTURA: 100.0% de 12 líneas cambiadas cubiertas (12/12, umbral 80%, nivel estandar; diff desde fbf43ddacc, merge-base con main)`: `coverage run -m pytest tests/test_f158_reparto_personal.py tests/test_f150_personal.py tests/test_f156_diccionario.py` + `coverage json` + `python -m harness.cobertura --base main` |
| Mutantes | **16 generados, 16 muertos, 0 supervivientes** (manual; la primera pasada dejó 2, ver abajo) |
| Tiempo de la suite | campaña de 16 mutantes: 35,6 s; suite de los ficheros afectados: 70,9 s; F-006: 412,96 s |

**Mutación.** Alcance: `repartir_personal` (11 mutantes, D1-D11) y el paso 5 del SQL (M1-M5,
los tres de design §5 y dos más). Cada mutante es un solo cambio textual, con la suite acotada
a `test_f158_reparto_personal.py`, `test_f150_personal.py`, `test_f150_contrato_compra.py`,
`test_f140_sql.py` y `test_f140_dominio.py` (`-x`). El fichero se restaura tras cada mutante y
`git status` sale limpio al terminar. El script está en el scratchpad de la sesión (`mutar.py`).
No es `python -m harness.mutacion` (desviación 5): sus números no son comparables con los de una
campaña del arnés.

| Mutante | Resultado | Lo caza |
|---|---|---|
| D1 sin la guarda `pendiente == 0` | muerto (2.ª pasada) | `r1_sin_pendiente` (un mes a 0 con p = 0 dividía por 0) |
| D2 `== 0` → `!= 0` | muerto | `r6_el_caso_1_0707` |
| D3 `acumulado +=` → `=` | muerto | `r6` |
| D4 `+=` → `-=` | muerto | `r6` |
| D5 sin restar el anterior | muerto | `r6` |
| D6 `anterior` no avanza | muerto | `r6` |
| D7 sin redondear | muerto | `r1_la_formula_por_acumulado` |
| D8 dividir antes de multiplicar | muerto (2.ª pasada) | `r1_multiplica_antes_de_dividir_como_el_sql` |
| D9 `pp` → `pendiente` | muerto | `r6` |
| D10 pierde el último mes | muerto | `r6` |
| D11 `anterior` arranca en `pp` | muerto | `r6` |
| M1 el personal con su propio resto (la fórmula de `fbf43dd`) | muerto | `r7_el_sql_sigue_al_dominio` |
| M2 sin `ORDER BY` en la ventana | muerto | `r7` |
| M3 `acumulado - importe` → `acumulado` | muerto | `r7` |
| M4 la rama del `UNION ALL` lee `repartido` | muerto | `r7` |
| M5 `/ pendiente_partida` → `/ importe` | muerto | `r7` |

**Análisis de los dos supervivientes de la primera pasada; los dos eran huecos reales:**

- **D1.** El único test de la guarda pasaba un reparto vacío, y con él el bucle no corre: la
  guarda no se notaba. Sin ella, `repartir_personal([(mes, 0, False)], 0, 0)` divide 0 entre 0
  (`InvalidOperation`). Test añadido.
- **D8.** Multiplicar antes de dividir parecía equivalente, pero no lo es en la frontera del
  redondeo. Con `0,17 x 0,13 / 0,26` = 0,085 exacto, el `ROUND` da 0,09, como PostgreSQL. Con
  `0,17 / 0,26 x 0,13` = 0,08499… da 0,08, y el céntimo cambia de mes. Lo encontré por búsqueda
  exhaustiva sobre importes de 0,03 a 3,99. Test añadido: es la garantía de que el dominio y el
  SQL dan el mismo céntimo.

M1-M5 los caza la lectura del texto del SQL, no una ejecución: sin sandbox, por D4. La garantía
de que la fórmula del SQL CALCULA bien la dan el dominio, que es letra a letra la misma fórmula,
y sus invariantes.

## Verificaciones MANUAL pendientes (humano, tras APROBADO y merge a `main`)

T6, según design §6: imagen, job, `build-tesoreria` suelto, `apply-grants` y las cuatro
comprobaciones (0 negativos en `devengo_pendiente_contrato_mes`; 0 meses con personal >
pendiente; la fila de 2563363 / 2027-10 / CI sin contrato ≥ 0; `build_tesoreria` SUCCESS hoy).
Después, `publicar-diccionario` → v72 (solo tras la v71 de F-156), `check-diccionario`,
`check-declarados`, el reinicio del MCP y la nocturna siguiente. Vuelta atrás: a `fbf43dd`.

## Fuera del alcance y lo que falta

- Fuera, por D2: el mes negativo del plan de 1-0702, que sigue entero sin contrato (R8, fijado
  en `test_f158_r8`). Fuera, por D4: el sandbox SQL.
- Falta: la puerta completa de `init.sh` en un checkout CON `.env` (la pasa el líder), la review
  y T6.
