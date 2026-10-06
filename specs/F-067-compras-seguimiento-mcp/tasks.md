<!-- specs/F-067-compras-seguimiento-mcp/tasks.md -->
# F-067 · Tareas

Rama `feature/F-067-compras-seguimiento-mcp`. Un commit por tarea (`F-067 Tn: ...`),
`git add` de ficheros concretos. Rigor **crítico**: fase RED de cada requisito
con test, traza en `progress/impl_F-067.md`, mutación completa del dominio con 0
supervivientes o justificación aceptada por el humano. Ningún agente ejecuta SQL
contra la base: los tests leen el TEXTO del SQL. Con D1 en dos fases: Fase 1 =
T1-T6 y T11-T15 (en T11-T13, solo lo de la foto y contratos); Fase 2 = T7-T10
más lo que quede de T11-T15.

## La foto y el contrato

- [x] T1: `etl_sigrid/domain/historial_estados.py` (`TIPOS_HISTORIAL`, `UMBRAL_PRESENCIA`, `MOTIVOS_CIERRE`, `EPOCA_DELPHI`, `Tramo`, `FotoIncompletaError`, `aplicar_foto`, `dias_en_estado`, `fecha_delphi`) con `tests/test_f067_dominio.py` y los casos de design §8 (R1-R7, R10, R14)  |  Verificación: `python -m pytest tests/test_f067_dominio.py -q` (RED antes, traza en el informe)
- [ ] T2: `compras.fn_sigrid_tiempo` al final de `sql/compras/00_setup.sql` con la época del dominio (R14)  |  Verificación: `python -m pytest tests/test_f067_sql.py -q -k tiempo`
- [ ] T3: `sql/compras/11_historial_estados.sql`: cabecera, las dos tablas persistentes, el bloque `DO` de la foto (design §3, pasos 1-6) sin `DROP`/`TRUNCATE`/`DELETE` (R1-R8)  |  Verificación: `python -m pytest tests/test_f067_sql.py -q -k "historial or foto or veto"`
- [ ] T4: `11`: `compras.v_estado_documentos` (R9-R11)  |  Verificación: `python -m pytest tests/test_f067_sql.py -q -k estado_documentos`
- [ ] T5: `01_documentos.sql`, CONTRATOS: `forma_pago_id`, `forma_pago`, `retencion_garantia_porcentaje`, `retencion_garantia_concepto`, `fecha_ultima_modificacion` al final (R12-R14)  |  Verificación: `python -m pytest tests/test_f067_sql.py tests/test_f084_sql.py -q`
- [ ] T6: `SUB_PASOS` + `11` (cuenta `historial_estados`), docstring, y `tests/test_f047_steps.py`  |  Verificación: `python -m pytest tests/test_f047_steps.py -q`

## El código 2 y las necesidades

- [ ] T7: `01_documentos.sql`: `codigo_alternativo`, `necesidad_id`, `necesidad_linea_id` al final de `albaran_lineas` (y, con D3, de `contrato_lineas` y `factura_lineas`), índice (R17, R18)  |  Verificación: `python -m pytest tests/test_f067_sql.py -q -k lineas`
- [ ] T8: `sql/compras/10_necesidades.sql`: `compras.necesidades` (R19) y `SUB_PASOS` + `10` (cuenta `necesidades`) antes de `11`  |  Verificación: `python -m pytest tests/test_f067_sql.py tests/test_f047_steps.py -q -k "necesidades or steps"`
- [ ] T9: `sql/descompuestos/06_views.sql`: `necesidad_id` al final de `v_pbi_planif_jo` y `v_pbi_master_planif_jo` por subconsulta escalar (R20, R21)  |  Verificación: `python -m pytest tests/test_f067_sql.py tests/test_f097_descompuestos.py -q` y `git diff main --stat -- etl_sigrid/infrastructure/postgres/sql/descompuestos/` (solo `06_views.sql`)
- [ ] T10: Fichas de `albaran_lineas` (y D3), `necesidades` y `descompuestos.yaml` (R22-R25)  |  Verificación: `python -m pytest tests/test_f067_diccionario.py tests/test_f006_fichas.py tests/test_f006_formato.py tests/test_f006_cobertura.py -q`

## Fichas, documentos y cierre

- [ ] T11: Fichas de `historial_estados`, `historial_estados_fotos`, `v_estado_documentos`, `contratos` (R10, R11, R14-R16) y `comparativos` (R26); `00_global.yaml` `version` +1, comentario de versión y P23-P26 (R27)  |  Verificación: `python -m pytest tests/test_f067_diccionario.py tests/test_f006_fichas.py tests/test_f006_formato.py tests/test_f006_cobertura.py -q`
- [ ] T12: `docs/ARCHITECTURE.md`: tablas persistentes de `compras` (no se reconstruyen, `--full` no las toca, qué pasa si se borran), foto por tramos, fecha de Delphi de `tiemod` (R29)  |  Verificación: el reviewer lo lee contra design §2 y §9
- [ ] T13: `azure-apps/datamart_seg_anual.md`: objetos y columnas nuevos de `compras` y `descompuestos`; commit en ESE repositorio, sin push (R29)  |  Verificación: `git -C C:/Users/pgris/PycharmProjects/azure-apps log -1 --stat`
- [ ] T14: Campaña de mutación COMPLETA sobre `domain/historial_estados.py` y análisis de supervivientes en el informe  |  Verificación: `python -m harness.mutacion --feature F-067`
- [ ] T15: Ejecutar `bash harness/init.sh` en verde (pytest, cobertura de líneas cambiadas, tamaño de spec e informes)  |  Verificación: `bash harness/init.sh`

## MANUAL del humano, en orden (tras el APROBADO del reviewer)

- [ ] T16: MANUAL (humano) · Merge a `main`; imagen con tag fechado desde `main` y job a ella  |  Verificación: MANUAL (humano): `powershell -NoProfile -File infra/70_build_image.ps1`, `powershell -NoProfile -File infra/85_update_job.ps1 -Tag rYYYYMMDD-HHmm` y `az containerapp job show -g rg-datamart-seg-dev -n caj-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv` con el tag nuevo
- [ ] T17: MANUAL (humano) · Dejar correr la nocturna (00:00 UTC): toma la LÍNEA BASE de la foto y publica el diccionario  |  Verificación: MANUAL (humano): `python main.py status` con `run-all` SUCCESS y `python main.py timings --last 1` con `build_compras` < +1 min sobre la noche anterior
- [ ] T18: MANUAL (humano, solo lectura) · Puertas contra la base  |  Verificación: MANUAL (humano): `python main.py check-declarados`, `python main.py check-unicidad`, `python main.py check-relaciones` y `python main.py check-diccionario`, los cuatro con código 0
- [ ] T19: MANUAL (humano, solo lectura) · Cifras contra la previsión: `SELECT * FROM compras.historial_estados_fotos;` (una fila, `es_linea_base`, ≈ 185.800 documentos) ; `SELECT count(*), count(codigo_alternativo), count(necesidad_linea_id) FROM compras.albaran_lineas;` (≈ 1.163.000, ≈ 357.000, ≈ 378.000) ; `SELECT count(*) FROM compras.necesidades;` (≈ 277) ; `SELECT count(retencion_garantia_porcentaje), count(forma_pago_id) FROM compras.contratos;` (≈ 6.330, ≈ 19.070)  |  Verificación: MANUAL (humano): resultado en `progress/current.md`; una desviación > 5 % se para y se avisa
- [ ] T20: MANUAL (humano, solo lectura) · Segunda noche: la foto avanza  |  Verificación: MANUAL (humano): `SELECT observado_en, n_cambios, n_altas, n_desaparecidos FROM compras.historial_estados_fotos ORDER BY 1;` con dos filas y cambios del orden de decenas a cientos (no miles)
- [ ] T21: MANUAL (humano) · Reiniciar el MCP (cachea el diccionario) y hacerle, sin explicarle nada, P23-P26 y el caso de Juan: `AC26/28510` de MOMOSA muestra `codigo_alternativo = 'MOMOSA'` en líneas sin contrato  |  Verificación: MANUAL (humano): las respuestas usan `compras.v_estado_documentos`, `compras.comparativos` y `compras.albaran_lineas`, y P23 dice que la antigüedad es un mínimo que empieza el día del despliegue
- [ ] T22: MANUAL (humano) · Escribir a Compras (y a Juan Romero): qué se responde ya, que «más de tres semanas» es cierto desde el día 21 tras el despliegue, que la penalización no es un campo (¿dónde la escriben?) y que «actividad validada» no existe en Sigrid (D4, F-055)  |  Verificación: MANUAL (humano): correo enviado, anotado en `progress/current.md`
- [ ] T23: MANUAL (humano, solo lectura, a los 21 días del despliegue) · Probar con Compras las cuatro preguntas por el MCP y medir si `tiemod` se mueve con el cambio de estado del contrato: `SELECT count(*), count(*) FILTER (WHERE c.fecha_ultima_modificacion >= h.desde - interval '1 day') FROM compras.historial_estados h JOIN compras.contratos c ON c.contrato_id = h.documento_id WHERE NOT h.es_linea_base;`  |  Verificación: MANUAL (humano): resultado en `progress/current.md`; P23 pasa a `respondible` en el `00_global.yaml` siguiente
