<!-- progress/impl_F-038_fase1.md -->
# F-038 · Informe del implementer · Fase 1 (T1-T10)

> Copia íntegra del informe de la Fase 1 (aprobado y desplegado el 2026-10-05),
> sacada de `progress/impl_F-038.md` al abrir la Fase 2 para que el informe
> vigente quepa en su tope de 220 líneas. Nada se ha cambiado debajo de esta nota;
> donde dice `progress/mutacion_F-038.md`, hoy es `progress/mutacion_F-038_fase1.md`.

Implementer, 2026-10-04. Rama `feature/F-038-comparativos`. Spec aprobada por el
humano el 2026-10-04 (D1 dos fases, Fase 1 tal cual). **Fase 2 (T11-T19, T25)
FUERA**. T20-T24 son MANUAL del humano (§5). Ni un SQL contra ninguna base: los
tests leen el texto del SQL.

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/comparativos.py` (nuevo) | Oráculo: `CIF_FALSOS`, `PATRONES_FAMILIA` (6, en orden), `EXCLUSIONES`, literales de normalización, `FACTOR_ATIPICO`/`MINIMO_ATIPICO`; `normalizar_nombre`, `familia_ficticia`, `es_adjudicado_atipico` |
| `sql/compras/00_setup.sql` | + `compras.fn_normalizar_nombre` y `compras.fn_familia_ficticia` al final (nada existente cambia) |
| `sql/compras/08_comparativos.sql` (nuevo) | Guarda R21 (`DO $$ ... RAISE EXCEPTION`, lo primero), `compras.comparativo_ofertas` (19 col.) y `compras.comparativos` (36 col.), columnas e índices de design §4 |
| `application/steps/build_compras_step.py` | `SUB_PASOS` + `comparativos` (`08`, cuenta `compras.comparativos`); docstring |
| `config/diccionario/compras.yaml` | Fichas de las dos tablas y las dos funciones; `contratos.comparativo_id` reescrita (R22) y `albaranes.comparativo_id`; relaciones `contratos`/`albaranes` → `comparativos` |
| `config/diccionario/00_global.yaml` | `version` 42; `esquemas.compras`; P5 → respondible; P19-P22; `confir.fec` en el punto 3 de `R-SIGRID-CON` |
| `docs/ARCHITECTURE.md` | Párrafo «Semántica Sigrid»: ficticias, sin IVA, atípico, contrato por `comlin.ctride` |
| `azure-apps/datamart_seg_anual.md` | Sección F-038 (commit `6a2bbde` en ESE repositorio, sin push) |
| Tests nuevos | `test_f038_dominio.py` (69), `test_f038_sql.py` (36), `test_f038_diccionario.py` (65) |
| Tests de otras features (ver §2.3) | `test_f047_steps.py`, `test_f073_pipeline.py`, `test_f080_pipeline.py`, `test_f006_reglas.py`, `test_f079_stg_consultable.py` |
| Otros | `specs/F-006-mcp-azure/design_detalle.md` (enmienda: 194 objetos); `progress/current.md`; `progress/mutacion_F-038.md`; `progress/mutacion_sql_F-038.py` |

## 2 · Decisiones y desviaciones

1. **`aprobado_por` con la misma condición que `fecha_aprobacion`** (circuito
   cerrado: `con.est` es un `estfin` de sus firmas). R23 solo condiciona la
   fecha; literal, `aprobado_por` publicaría como «aprobó» a quien firmó el
   último paso de un comparativo RECHAZADO: cifra plausible y falsa. Es la
   lectura de acceptance 5 («para los aprobados»). Si el reviewer o el humano
   lo quieren literal, es quitar un `CASE` y su test.
2. **Patrón FASE_0 afinado**: `FASE ?0( |$)|PLANIFICACION 0$` en vez de
   `FASE ?0|...` (design §3 lo permite «solo con los nombres medidos»): «FASE 05»
   no es la fase 0; los tres nombres medidos casan igual.
3. **Tests de otras features tocados, todos por consecuencia directa de la spec**:
   las listas completas de ficheros de `build_compras` (`test_f073_pipeline`,
   `test_f080_pipeline`, como hizo F-080 con F-073); la batería de F-006
   (`test_f006_reglas`: P1-P22, P5 respondible → 18/2/2, que pide R24); el
   inventario de funciones fuera de consumo (`test_f079`); y el recuento de
   objetos en el design de F-006 (194), como hizo F-118.
4. **`R-SIGRID-CON` gana `confir.fec`**: `08` lee `f.fec` de `raw.confir` sin
   pasar por `con`, y el test de F-006 deriva esa lista del SQL.
5. Detalles de SQL: `ORDER BY f.fec DESC NULLS LAST, f.hor DESC NULLS LAST,
   f.ide DESC` (en `DESC`, Postgres pone los NULL primero); alias `oft` y no
   `of` (palabra clave); `importe_adjudicado_lineas` NULL si no hay líneas.
6. Proceso: la primera línea base de mutación salió en ROJO (4 tests de otras
   features rotos por mis cambios, invisibles en mis subconjuntos); arreglados
   en `9a73809` antes de la campaña. Lección: correr la suite entera antes de mutar.

## 3 · Fase RED (rigor `estandar`)

Requisitos centrales de design §7 de la Fase 1: R3, R8-R11, R12, R14, R15, R16,
R19, R20, R21. Trazas reales, recortadas a sus líneas de resultado.

**T1 · R8-R11, R16** — `python -m pytest tests/test_f038_dominio.py -q --tb=line`
contra un esqueleto con las constantes vacías y las funciones en
`raise NotImplementedError` (antes, sin módulo: `ModuleNotFoundError: No module
named 'etl_sigrid.domain.comparativos'`):
```
E   NotImplementedError
FAILED tests/test_f038_dominio.py::test_f038_r8_r9_familia_de_los_nombres_medidos[None-OBJETIVO-RUESMA-OBJETIVO]
FAILED tests/test_f038_dominio.py::test_f038_r8_r10_ofertas_reales[None-MAT PLANIFICACION DE ESPACIOS, S.L.]
FAILED tests/test_f038_dominio.py::test_f038_r16_umbrales - assert 0 == 10
FAILED tests/test_f038_dominio.py::test_f038_r16_es_adjudicado_atipico[adjudicado0-mayor0-True]
66 failed, 1 passed in 0.24s
```
Verde con el módulo: `67 passed in 0.20s` (69 tras el test del superviviente).

**T2 · R11 (literales SQL = dominio)** —
`python -m pytest tests/test_f038_sql.py -q --tb=line -k "setup or literales"`:
```
AssertionError: `compras.fn_familia_ficticia` tiene que estar definida exactamente UNA vez en `compras/00_setup.sql`
FAILED tests/test_f038_sql.py::test_f038_r11_literales_patrones_de_familia_en_su_orden
FAILED tests/test_f038_sql.py::test_f038_r11_literales_cif_falsos - Assertion...
FAILED tests/test_f038_sql.py::test_f038_r11_literales_exclusiones - Assertio...
6 failed, 1 passed in 0.08s
```

**T3 · R3, R12, R21** —
`python -m pytest tests/test_f038_sql.py -q --tb=line -k "ofertas or guarda or prvide or totdoc"`:
```
AssertionError: SQL no encontrado: ...\sql\compras\08_comparativos.sql
FAILED tests/test_f038_sql.py::test_f038_ofertas_r3_proveedor_de_dco_entide
FAILED tests/test_f038_sql.py::test_f038_prvide_r3_el_sql_no_lee_comprv_prvide
FAILED tests/test_f038_sql.py::test_f038_totdoc_r12_el_sql_no_lee_dco_totdoc
FAILED tests/test_f038_sql.py::test_f038_ofertas_r12_importes_documento_sin_iva_y_lineas
FAILED tests/test_f038_sql.py::test_f038_guarda_r21_dos_contratos_rompen_el_build
12 failed, 7 deselected in 0.15s
```
Que los vetos (R3 `prvide`, R12 `totdoc`) muerden de verdad con el fichero
presente lo prueba la campaña SQL: M09 (`totbas` → `totdoc`) muere con 2 fallos.

**T4 · R14, R15, R16, R19, R20** — `python -m pytest tests/test_f038_sql.py -q --tb=line`
(con la parte 1 ya escrita, sin el bloque de `compras.comparativos`):
```
ValueError: substring not found
FAILED tests/test_f038_sql.py::test_f038_r14_ninguna_columna_se_llama_importe_a_secas
FAILED tests/test_f038_sql.py::test_f038_r15_ganadora_solo_si_es_unica - Valu...
FAILED tests/test_f038_sql.py::test_f038_r16_atipico_con_los_umbrales_del_dominio
FAILED tests/test_f038_sql.py::test_f038_r19_ahorro_solo_con_ofertas_reales_con_importe
FAILED tests/test_f038_sql.py::test_f038_r20_contrato_por_comlin_ctride - Val...
15 failed, 19 passed in 0.15s
```
Verde: `34 passed` (36 tras los tests de alias y de los JOIN, añadidos al
descubrir un `oftt.` que ningún test de texto veía).

**T5** — `python -m pytest tests/test_f047_steps.py -q --tb=line`:
`FAILED ...test_f047_r4_encadena_sus_sql_en_orden[build_compras]`,
`FAILED ...test_f038_r1_build_compras_cuenta_los_comparativos`, `2 failed, 21 passed`.

**T6 · R22, R24** — `python -m pytest tests/test_f038_diccionario.py -q --tb=line`:
`FAILED ...test_f038_r22_contratos_comparativo_id_remite_al_objeto_nuevo`,
`FAILED ...test_f038_r24_la_version_sube`, `FAILED ...test_f038_r24_p5_pasa_a_respondible`,
`65 failed in 0.90s`.

## 4 · Verificaciones

- Subconjuntos por tarea, todos verdes tras cada commit (ver §3).
- Suite entera sin cobertura, antes de mutar (`python -m pytest tests -q -x`):
  `6612 passed, 223 skipped in 286.21s`.
- `bash harness/init.sh`: ver «Evidencias».
- NO verificado (no se puede sin base): que el SQL corra en Postgres y sus
  cifras. Riesgos a mirar en T21: tipos de `raw` (`confir.hor`, `dco.totbas`),
  `translate` con tildes (fichero UTF-8, lo lee `execute_sql_file` en UTF-8) y
  la guarda R21 (hoy 0 casos medidos).

## 5 · MANUAL del humano, en orden, tras el APROBADO del reviewer

Copiadas con su comando exacto en `progress/current.md` (sección F-038):
1. **T20** · merge a `main`; `powershell -NoProfile -File infra/70_build_image.ps1`;
   `powershell -NoProfile -File infra/85_update_job.ps1 -Tag rYYYYMMDD-HHmm`;
   `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv` → el tag nuevo.
2. **T21** · nocturna (00:00 UTC, publica la v42). `python main.py status` →
   `run-all` SUCCESS; `python main.py timings --last 1` → `build_compras` ≲ +1 min.
   Fallo en el sub-paso `comparativos` con «F-038 R21» = comparativo con dos
   contratos: parar y avisar.
3. **T22** · `python main.py check-declarados`, `check-unicidad`,
   `check-relaciones`, `check-diccionario` → código 0 los cuatro.
4. **T23** · `SELECT count(*), count(contrato_id), sum(ahorro_concurso), count(ahorro_concurso), count(*) FILTER (WHERE adjudicado_atipico) FROM compras.comparativos;`
   → ≈ 20.378, ≈ 18.600, ≈ 72,7 M€, ≈ 6.900, ≈ 52;
   `SELECT familia_ficticia, count(*) FROM compras.comparativo_ofertas GROUP BY 1;`
   → ≈ 32.900 no NULL. Desviación > 5 %: parar y avisar.
5. **T24** · reiniciar el MCP; cuatro preguntas (actividad, ahorro, quién aprobó
   y cuándo, ¿acabó en contrato?) → `compras.comparativos` y frescura de `build_compras`.

## 6 · Fuera de alcance / lo que falta

- Fase 2 entera (objetivo, líneas de los dos lados, firmas por escalón): D4
  decidida el 2026-10-04; espera a que el humano la abra.
- `ingest` nueva, `compras.contratos` sin cambios de columnas (R22 es solo ficha).
- Para cerrar: review, y después T20-T24 del humano.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (`init.sh`) | **6614 passed, 223 skipped**, 0 failed (de ellos 170 de F-038: 69 + 36 + 65) |
| Cobertura de líneas cambiadas | `PUERTA COBERTURA: 100.0% de 32 líneas cambiadas cubiertas (32/32, umbral 80%, nivel estandar; diff desde 4dfe8c70b5, merge-base con main)` |
| Mutación (`harness.mutacion`, 2 workers, HEAD `9a738095ec3f2a6a091627b9afc2b6f79f0a7cff`) | 14 generados (campaña completa: < 20), **13 muertos, 1 superviviente** (`<= 0` → `<= 1`, hueco real: test nuevo, reverificado en serie: 2 fallos), 0 timeouts, 3011,4 s. Detalle: `progress/mutacion_F-038.md` |
| Mutación SQL manual (1 worker, `47cc859a654fd7a5066231af861d8e3c7e4ff559`) | **24 mutantes, 24 muertos**; tabla en el anexo de `progress/mutacion_F-038.md`, script `progress/mutacion_sql_F-038.py` |
| Tiempo de la suite | 905,70 s con cobertura dentro de `init.sh` (0:15:05); 286,21 s sin cobertura |
| `bash harness/init.sh` | **ENTORNO LISTO**, exit 0, sobre HEAD `496f56d` (todas las comprobaciones OK; `PUERTA TAMAÑO`: requirements 144/150, design 249/250, impl 163/220). El commit posterior solo rellena esta tabla y marca T10 |
