<!-- specs/F-038-comparativos/tasks.md -->
# F-038 · Tareas

Rama `feature/F-038-comparativos`. Un commit por tarea (`F-038 Tn: ...`), `git add`
de ficheros concretos. Rigor `estandar`: fase RED con traza en
`progress/impl_F-038.md` para los requisitos que lista `design.md` §7. Ningún
agente ejecuta SQL contra la base: los tests leen el TEXTO del SQL; lo que exige
la base es MANUAL del humano. **D1 aprobado (2026-10-04): dos fases.** Fase 2
(T11-T19) cuando el humano la abra y con D4 decidida; D3 aprobado (T15 entra).

## Fase 1 · comparativo, ofertas, importes, ahorro, contrato, aprobación

- [x] T1: `etl_sigrid/domain/comparativos.py` (Fase 1: `CIF_FALSOS`, `PATRONES_FAMILIA`, `EXCLUSIONES`, umbrales, `normalizar_nombre`, `familia_ficticia`, `es_adjudicado_atipico`) con `tests/test_f038_dominio.py` y las fixtures medidas de design §3 (R8-R11, R16)  |  Verificación: `python -m pytest tests/test_f038_dominio.py -q` (RED antes, traza en el informe)
- [x] T2: `compras.fn_normalizar_nombre` y `compras.fn_familia_ficticia` al final de `sql/compras/00_setup.sql`; test de que sus literales son los del dominio (R11)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k "setup or literales"`
- [x] T3: `sql/compras/08_comparativos.sql`, parte 1: cabecera, guarda `RAISE EXCEPTION` de dos contratos (R21) y `compras.comparativo_ofertas` con las columnas de design §4 (R2-R4, R8, R12, R15)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k "ofertas or guarda or prvide or totdoc"`
- [x] T4: `08_comparativos.sql`, parte 2: `compras.comparativos` con sus cuatro agregados y columnas de design §4 (R1, R4-R7, R13-R20, R23)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q`
- [x] T5: `SUB_PASOS` de `build_compras_step.py` + `08` (cuenta `comparativos`) y docstring; lista de `tests/test_f047_steps.py`  |  Verificación: `python -m pytest tests/test_f047_steps.py -q`
- [x] T6: Fichas de `comparativos` y `comparativo_ofertas` en `config/diccionario/compras.yaml` con lo que exige design §6; ficha de `contratos.comparativo_id` (R22) y relaciones de `contratos`/`albaranes`; en `00_global.yaml` `version` +1, P5 respondible y las cuatro preguntas del acceptance 13 (R24); `tests/test_f038_diccionario.py`  |  Verificación: `python -m pytest tests/test_f038_diccionario.py tests/test_f006_fichas.py tests/test_f006_formato.py tests/test_f006_cobertura.py -q`
- [x] T7: Párrafo de `docs/ARCHITECTURE.md` («Semántica Sigrid»): ficticias por CIF y nombre, importes sin IVA (`dco.totbas`), atípico 10×/100.000 €, enlace por `comlin.ctride`  |  Verificación: el reviewer lo lee contra design §2
- [x] T8: `azure-apps/datamart_seg_anual.md`: los dos objetos nuevos de `compras` y la nota de `compras.contratos.comparativo_id`; commit en ESE repositorio (sin push)  |  Verificación: `git -C C:/Users/pgris/PycharmProjects/azure-apps log -1 --stat`
- [x] T9: Campaña de mutación del arnés sobre `domain/comparativos.py` y análisis de supervivientes en el informe  |  Verificación: `python -m harness.mutacion --feature F-038`
- [x] T10: Ejecutar `bash harness/init.sh` en verde (pytest, cobertura de líneas cambiadas, tamaño de spec e informes)  |  Verificación: `bash harness/init.sh`

## Fase 2 · objetivo, líneas de los dos lados, firmas

- [x] T11: Dominio Fase 2: `PATRON_DTO`, `parse_porcentaje_dto`, `TOLERANCIA_*`, `casa_con_base` y `base_regla` (ABC si la obra tiene primera ABC, si no ESTUDIOS), con tests de los `dto` medidos y de las tres líneas de la 0696 (R27, R29)  |  Verificación: `python -m pytest tests/test_f038_dominio.py -q`
- [x] T12: `compras.fn_porcentaje_dto` en `00_setup.sql` con el patrón del dominio, sin `EXCEPTION` (R27)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k dto`
- [x] T13: `sql/compras/09_comparativos_detalle.sql`: `comparativo_lineas` y `comparativo_oferta_lineas` con la base del descompuesto según D4 (R25, R26, R29, R30, R32)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k "lineas or base"`
- [x] T14: `09`: `compras.comparativo_objetivo` (R31)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k objetivo`
- [ ] T15: `09`: `compras.comparativo_firmas` (R33)  |  Verificación: `python -m pytest tests/test_f038_sql.py -q -k firmas`
- [ ] T16: `SUB_PASOS` + `09` (cuenta `comparativo_oferta_lineas`) y `tests/test_f047_steps.py`  |  Verificación: `python -m pytest tests/test_f047_steps.py -q`
- [ ] T17: Fichas de Fase 2 (R28, R34, R35) y `version` +1  |  Verificación: `python -m pytest tests/test_f038_diccionario.py tests/test_f006_fichas.py -q`
- [ ] T18: `azure-apps/datamart_seg_anual.md` con los objetos de Fase 2; commit en ese repositorio  |  Verificación: `git -C C:/Users/pgris/PycharmProjects/azure-apps log -1 --stat`
- [ ] T19: Mutación del dominio de Fase 2 y `bash harness/init.sh` en verde  |  Verificación: `python -m harness.mutacion --feature F-038` y `bash harness/init.sh`

## MANUAL del humano, en orden (tras el APROBADO del reviewer)

- [ ] T20: MANUAL (humano) · Merge a `main`; imagen con tag fechado desde `main` y job a ella  |  Verificación: MANUAL (humano): `powershell -NoProfile -File infra/70_build_image.ps1`, `powershell -NoProfile -File infra/85_update_job.ps1 -Tag rYYYYMMDD-HHmm` y `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv` con el tag nuevo
- [ ] T21: MANUAL (humano) · Dejar correr la nocturna (00:00 UTC); publica el diccionario ella sola  |  Verificación: MANUAL (humano): `python main.py status` con `run-all` SUCCESS y `python main.py timings --last 1` con `build_compras` dentro de la previsión (+1 min en Fase 1, +2 en Fase 2)
- [ ] T22: MANUAL (humano, solo lectura) · Puertas contra la base  |  Verificación: MANUAL (humano): `python main.py check-declarados`, `python main.py check-unicidad`, `python main.py check-relaciones` y `python main.py check-diccionario`, los cuatro con código 0
- [ ] T23: MANUAL (humano, solo lectura) · Cifras contra la previsión de `progress/spec_F-038.md`: `SELECT count(*), count(contrato_id), sum(ahorro_concurso), count(ahorro_concurso), count(*) FILTER (WHERE adjudicado_atipico) FROM compras.comparativos;` (≈ recuento de `raw.com`, ≈ 18.600, ≈ 72,7 M€, ≈ 6.900, ≈ 52) y `SELECT familia_ficticia, count(*) FROM compras.comparativo_ofertas GROUP BY 1;` (≈ 32.900 ficticias)  |  Verificación: MANUAL (humano): resultado en `progress/current.md`; una desviación > 5 % se para y se avisa
- [ ] T24: MANUAL (humano) · Reiniciar el MCP y hacerle, sin explicarle nada, las cuatro preguntas del acceptance 13 (comparativos por actividad; ahorro del concurso; quién aprobó el comparativo X y cuándo; ¿acabó en contrato el comparativo X?)  |  Verificación: MANUAL (humano): las cuatro respuestas usan `compras.comparativos` y citan la frescura de `build_compras`
- [ ] T25: SOLO Fase 2 · MANUAL (humano, solo lectura) · El caso de la captura de Elena Díaz (obra 0696): `compras.comparativo_objetivo` da 94.853,91 €, 5 % y `base_regla` = ABC; sus líneas 939265 y 952250 casan con la ABC v3 (69,70 × 0,95 = 66,215) y la 962172 (26,60, base 28,00) no tiene base ni en la ABC ni en Estudios  |  Verificación: MANUAL (humano): `SELECT o.* FROM compras.comparativo_objetivo o JOIN compras.comparativos c USING (comparativo_id) WHERE c.comparativo_id = 2754136;` y `SELECT linea_oferta_id, precio, porcentaje_descuento, precio_base, origen_base, casa_base FROM compras.comparativo_oferta_lineas WHERE oferta_id = 2754139;`
