<!-- specs/F-025-ventana-negocio-build/tasks.md -->
# F-025 · Acotar el build por ventana de negocio — Tareas

Una tarea = un commit (`F-025 Tn: descripción`). Orden por dependencia; los
tests van antes o junto a la implementación (fase RED, exigida por el rigor
`critico`).

> **T6 es una PARADA.** Las tareas T7 en adelante **no se empiezan** sin que
> **Negocio firme DA-1** sobre `progress/ventana_F-025.md`. Es la razón por la
> que esta feature existe separada de F-011: sin esa firma no hay ventana que
> aplicar, y el spec-author **no** cierra DA-1.

> **T13 es la segunda PARADA**: la prueba de equivalencia. Cualquier
> diferencia en los bloques `estructura` o `cerrado` de la huella es FALLO, la
> feature se marca `blocked` y **no se racionaliza** (precedente de F-019 T11).

---

## Bloque A · Medir el peso de la ventana (se hace siempre)

- [ ] **T1**: Añadir el bloque `ventana:` a `config/business_rules.yaml` con
      `candidatos:` (los cuatro de DA-1: `sin_fecha_fin_real`,
      `con_movimiento_12m`, `situacion_contrato`, `sin_fecha_cierre`, cada uno
      con su SQL `SELECT obra_id ...` y su comentario) y `vigente: null` con el
      comentario que apunta a **DA-1, decisión de Negocio pendiente**.
      **Verificación**: `pytest tests/test_f025_config.py -q` (R6) — el YAML
      carga, los candidatos tienen nombre y SQL, `vigente` es `null` y ningún
      SQL contiene `;` ni empieza por algo distinto de `SELECT`.

- [ ] **T2**: Crear `etl_sigrid/domain/ventana.py` con `Candidato`,
      `PesoVentana`, `peso_de_la_ventana(...)` y `format_perfil_ventana(...)`
      (funciones puras, sin imports de infraestructura). Tests primero.
      **Verificación**: `pytest tests/test_f025_ventana.py -k "peso or format" -q`
      (R1).

- [ ] **T3**: Añadir a `etl_sigrid/domain/ventana.py` la función
      `ahorro_estimado(duraciones_por_tramo, pesos_por_obra, obras_dentro)`,
      que prorratea los minutos de `build_plan_mensual` (filas
      `build_stg.build_plan_mensual.tramo_NN` de `_meta.etl_runs`) y de
      `build_mart.build_fact` entre las obras dentro y fuera.
      **Verificación**: `pytest tests/test_f025_ventana.py -k ahorro -q` (R2),
      con fixture de tramos reales y los bordes (ninguna obra fuera, todas
      fuera, tramo sin duración registrada).

- [ ] **T4**: Añadir `fetch_peso_ventana(predicado_sql)` y
      `fetch_obras_de_la_ventana(predicado_sql)` a `postgres_client.py` (solo
      lectura, con validación de que el predicado empieza por `SELECT` y no
      trae `;`), y el comando `perfil-ventana [--detalle] [--out]` a `main.py`
      **sin** `_arrancar_ejecucion()`.
      **Verificación**: `pytest tests/test_f025_ventana.py -q` (R1, R3, R4,
      R19) con `PostgresClient` mockeado; incluye el test de que **cero**
      escrituras llegan a `_meta` y el de que sin candidatos declarados el
      comando falla nombrando DA-1.

- [ ] **T5 · MANUAL (humano)**: ejecutar la medición real. Con `.env`
      apuntando a Azure:

      ```bash
      python main.py perfil-ventana
      python main.py perfil-ventana --detalle --out ventana_candidatos.csv
      python main.py timings                 # desglose por tramo, para contrastar
      ```

      **Verificación**: `MANUAL (humano)`. El CSV **no se versiona** (va al
      puesto, como las huellas de F-019).

- [ ] **T6 · PARADA · Negocio**: escribir `progress/ventana_F-025.md` con los
      números de T5 por candidato (obras dentro/fuera, % de filas, ahorro
      estimado en minutos) y la recomendación; **y que Negocio firme DA-1**
      eligiendo el predicado vigente.
      **Verificación**: `MANUAL (humano)`. El reviewer comprueba que el informe
      existe, que cada número cita su origen (`_meta.etl_runs` / consulta al
      datamart) y que la firma de DA-1 está en `progress/current.md`. Si el
      ahorro no justifica el riesgo, la feature se **cierra aquí** entregando
      solo el bloque A, y se dice así en `progress/current.md`.

---

## Bloque B · Acotar el refresco (solo si T6 dice que sí)

- [ ] **T7**: Fijar el predicado elegido en `ventana.vigente` de
      `config/business_rules.yaml` y añadir `VentanaSettings` (prefijo
      `VENTANA_`: `activa=False`, `max_pct_fuera=95.0`) a `config/settings.py`.
      **Verificación**: `pytest tests/test_f025_apagado.py -q` (R7) — sin
      variables de entorno, la composición del pipeline y el SQL que se
      ejecutaría son **idénticos** a los de hoy.

- [ ] **T8**: Añadir a `etl_sigrid/domain/ventana.py` `filtrar_obras(...)` y
      `validar_ventana(...)` (R13). Tests exhaustivos primero: es la pieza que
      la campaña de mutación va a morder.
      **Verificación**: `pytest tests/test_f025_guardias.py -q` (R13) con los
      bordes (cero obras dentro, todas dentro, justo en el umbral, justo por
      encima).

- [ ] **T9**: Añadir el índice `idx_plan_mensual_obra` a
      `sql/stg/01_ddl.sql` (`CREATE INDEX IF NOT EXISTS`, aditivo).
      **Verificación**: `pytest tests/test_f025_build.py -k ddl -q` — el test
      lee el `.sql`, comprueba `IF NOT EXISTS` y que no hay bloques `$$`.

- [ ] **T10**: Modificar `build_stg_step.py`: filtrar obras antes de
      `planificar_tramos`, sustituir el `TRUNCATE` global por `DELETE ... WHERE
      obra_id = ANY(...)` **dentro de la transacción del tramo**, aplicar
      `validar_ventana` y escribir el `metadata` de R14. **`componer_sql_tramo`,
      el marcador `/*F019_FILTRO_OBRAS*/` y `tramos.py` no se tocan.**
      **Verificación**: `pytest tests/test_f025_build.py -q` (R8, R10, R14,
      R17) + `pytest tests/test_f019_*.py -q` **sin modificar ni un test de
      F-019**; si alguno hay que tocarlo, el diseño se torció y hay que parar.

- [ ] **T11**: Sustituir el `TRUNCATE` de `sql/mart/02_build_fact.sql` por el
      marcador `/*F025_BORRADO*/` y hacer que `build_mart_step.py` inyecte el
      `TRUNCATE` de siempre (sin ventana) o el `DELETE` por obra (con ventana),
      dejando `agg_categoria` coherente.
      **Verificación**: `pytest tests/test_f025_build.py -k mart -q` (R9) —
      incluye el test de que, con la ventana apagada, el SQL compuesto es
      **carácter por carácter** el fichero de hoy.

- [ ] **T12**: Guardias de proceso: `run-all --full` y `stage --full`
      reconstruyen todo aunque la ventana esté activa (R15); la puerta de
      coherencia de `raw` de F-024 sigue intacta (R16); la puerta de disco de
      F-019 sigue armada (R11); `stg.obras.activa` sigue cableada a `TRUE`
      (R18).
      **Verificación**: `pytest tests/test_f025_guardias.py tests/test_f025_alcance.py -q`
      (R11, R15, R16, R18, R20, R21) + los tests de F-024 pasan sin
      modificarse.

- [ ] **T13 · PARADA · MANUAL (humano)**: prueba de equivalencia contra Azure.
      Build completo y build acotado sobre **el mismo `raw`**:

      ```bash
      python main.py check-coherencia                  # raw coherente (F-024)
      # 1) build completo, la referencia
      python main.py stage --full
      python main.py build-mart
      python main.py fingerprint-views --out huella_completo_f025.csv --periodo-hasta 2026-07
      # 2) build acotado, sin volver a ingerir
      VENTANA_ACTIVA=1 python main.py stage
      VENTANA_ACTIVA=1 python main.py build-mart
      python main.py fingerprint-views --out huella_ventana_f025.csv --periodo-hasta 2026-07
      python main.py compare-fingerprints huella_completo_f025.csv huella_ventana_f025.csv
      ```

      Esperado: **cero diferencias** en los bloques `estructura` y `cerrado`
      (el bloque `vivo` puede avisar por `mart.v_pbi_dim_fecha`, que usa
      `CURRENT_DATE`). Cualquier FALLO se marca `blocked` y **no se
      racionaliza**.
      **Verificación**: `MANUAL (humano)`. Anotar también el tiempo real de
      cada build y el pico de ocupación de disco, para contrastarlos con la
      estimación de T3.

- [ ] **T14**: Actualizar `docs/ARCHITECTURE.md` (qué es la ventana, que acota
      el refresco y no el contenido, cómo se declara, la reconstrucción
      completa semanal) y `azure-apps/datamart_seg_anual.md` (perfil de carga y
      variables de entorno nuevas; y las tablas nuevas de `sigrid-api` si DA-1
      eligió la opción (c)). No se toca `azure-apps/sigrid_api.md`, que es de
      otro proyecto.
      **Verificación**: inspección del reviewer + `pytest tests/test_f025_alcance.py -q`
      (R21: barrido de secretos sobre lo nuevo).

---

## Cierre

- [ ] **T15**: Campaña de mutación del rigor `critico` y análisis de
      supervivientes, con foco en `etl_sigrid/domain/ventana.py`.
      **Verificación**: `python -m harness.mutacion --feature F-025` con cero
      supervivientes, o cada superviviente justificado por escrito en
      `progress/mutacion_F-025.md` y **aceptado por el humano**.

- [ ] **T16**: Ejecutar `bash harness/init.sh` en verde (incluye pytest y la
      puerta de cobertura de las líneas cambiadas).
      **Verificación**: `bash harness/init.sh` termina con exit code 0.
