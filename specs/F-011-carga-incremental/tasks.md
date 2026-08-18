<!-- specs/F-011-carga-incremental/tasks.md -->
# F-011 · Carga incremental del datamart — Tareas

Una tarea = un commit (`F-011 Tn: descripción`). Orden por dependencia; los
tests van antes o junto a la implementación (fase RED, exigida por el rigor
`critico` que hereda esta feature al no declarar `rigor`).

> **T9 es una PARADA.** Las tareas T10 en adelante **no se empiezan** sin la
> firma del humano sobre `progress/medicion_F-011.md`. Es el «medir antes de
> optimizar» de la feature, convertido en puerta ejecutable.

---

## Bloque A · Medición (se hace siempre)

- [ ] **T1**: Crear `etl_sigrid/domain/perfil_carga.py` con `FilaPerfil`,
      `PerfilCarga`, `perfil_de_carga`, `techo_de_mejora`,
      `tablas_que_acumulan` y `format_perfil` (funciones puras, sin imports de
      infraestructura). Tests primero.
      **Verificación**: `pytest tests/test_f011_perfil.py -q` en verde (R1, R2,
      R3), incluida la fase RED documentada.

- [ ] **T2**: Añadir `fetch_perfil_carga(batch_id=None)` a
      `postgres_client.py` (solo `SELECT` sobre `_meta.etl_runs`) y el comando
      `perfil-carga` a `main.py`, sin `_arrancar_ejecucion()`.
      **Verificación**: `pytest tests/test_f011_cli.py -k perfil_carga -q`
      (cliente Postgres mockeado; comprueba también R25: cero escrituras en
      `_meta`).

- [ ] **T3**: Crear `etl_sigrid/domain/extraccion.py` (`MedicionPagina`,
      `resumen_bench`, `es_sentencia_de_lectura`, `comparar_cap`).
      **Verificación**: `pytest tests/test_f011_bench.py -k "resumen or lectura
      or cap" -q` (R5, R23).

- [ ] **T4**: Crear `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` y
      el comando `bench-sigrid --tabla --paginas [--out]`. El adaptador **no
      importa `PostgresClient`**; captura `SigridApiPageSizeTooLargeError` y
      sigue con los tamaños admitidos.
      **Verificación**: `pytest tests/test_f011_bench.py -q` (R4, R5) — el
      cliente HTTP va mockeado; un test comprueba por barrido de imports que
      el módulo no toca Postgres.

- [ ] **T5**: Crear `etl_sigrid/domain/tiemod.py` (`EstadoTiemod`,
      `veredicto_tiemod` con `SIRVE` / `NO SIRVE` / `SIN EVIDENCIA`,
      `format_diagnostico`).
      **Verificación**: `pytest tests/test_f011_tiemod.py -q` (R6, R7), con un
      caso por veredicto y los bordes (columna toda nula, tabla vacía, dos
      fotografías idénticas).

- [ ] **T6**: Añadir `fetch_diagnostico_tiemod()` a `postgres_client.py` y el
      comando `diagnostico-tiemod [--out] [--comparar-con]` a `main.py`.
      **Verificación**: `pytest tests/test_f011_cli.py -k tiemod -q`.

- [ ] **T7 · MANUAL (humano)**: ejecutar las mediciones reales. Con `.env`
      apuntando a Azure (ver el aviso de `progress/current.md`):

      ```bash
      python main.py perfil-carga                     # desglose de la carga del 18-ago
      python main.py diagnostico-tiemod --out huella_tiemod_1.csv
      python main.py bench-sigrid --tabla obrparpre --paginas 200,1000,5000,10000 --out bench_sigrid.csv
      ```

      Y, tras la siguiente carga nocturna completa:

      ```bash
      python main.py diagnostico-tiemod --out huella_tiemod_2.csv
      python main.py diagnostico-tiemod --comparar-con huella_tiemod_1.csv
      ```

      **Verificación**: `MANUAL (humano)`. Los CSV **no se versionan** (van al
      puesto, como las huellas de F-019). El `bench-sigrid` va contra el SQL
      Server de producción: lo lanza el humano en el momento que elija.

- [ ] **T8**: Escribir `progress/medicion_F-011.md` con los números reales de
      T7, el `batch_id` de cada carga medida, el cap real de `max_rows`
      medido frente al documentado (DA-6) y una **recomendación firmada de SÍ
      o NO** implementar el bloque B, contrastada contra el umbral de DA-7.
      **Verificación**: el fichero existe y cada número tiene su origen
      citado (`_meta.etl_runs` / salida del bench). Inspección del reviewer.

- [ ] **T9 · PARADA · MANUAL (humano)**: el humano lee T8 y decide. Cierra
      además DA-1, DA-2, DA-3, DA-4, DA-6 y DA-7 en
      `progress/current.md`.
      **Verificación**: `MANUAL (humano)`. Si la decisión es NO, la feature
      salta a T22 y se cierra con el bloque A entregado y el bloque C
      convertido en feature nueva (DA-5).

---

## Bloque B · Ingesta incremental (solo si T9 dice que sí)

- [ ] **T10**: Crear `etl_sigrid/domain/carga_incremental.py` con
      `ModoCarga`, `decidir_modo_de_carga` y `decidir_modo_de_tabla`. Tests
      exhaustivos primero (es la pieza que la campaña de mutación va a morder).
      **Verificación**: `pytest tests/test_f011_watermark.py -q` (R12, R15,
      R17) + `python -m harness.mutacion --feature F-011` sin supervivientes
      en este módulo.

- [ ] **T11**: Crear `etl_sigrid/infrastructure/postgres/sql/ddl/01_watermark.sql`
      (tabla `_meta.ingesta_watermark` idempotente + ampliación **aditiva** de
      `_meta.v_raw_state`) y hacer que `_bootstrap_schemas_and_meta` ejecute
      todos los `sql/ddl/*.sql` en orden en lugar del `00_meta.sql` fijo.
      **Verificación**: `pytest tests/test_f011_watermark.py -k ddl -q` (R11):
      el test lee el `.sql`, comprueba `IF NOT EXISTS`, que la vista conserva
      sus columnas actuales en el mismo orden y que no hay bloques `$$`.

- [ ] **T12**: Añadir a `postgres_client.py` `leer_watermark()`,
      `actualizar_watermark(...)` y el parámetro opcional `metadata` de
      `record_run_end(...)`.
      **Verificación**: `pytest tests/test_f011_ingesta.py -k metadata -q`
      (R10), con conexión mockeada.

- [ ] **T13**: Añadir `IngestaSettings` (prefijo `INGESTA_`) a
      `config/settings.py` con los tres valores por defecto que reproducen el
      comportamiento actual.
      **Verificación**: `pytest tests/test_f011_cli.py -k apagado -q` (R18):
      sin variables de entorno, la composición del pipeline y el modo de
      ingesta son idénticos a los de hoy.

- [ ] **T14**: Añadir `desde_tiemod` a `SigridApiClient.stream_table` y el
      método `count_rows(source_table, where=None)`. La paginación keyset por
      `ide` **no cambia**: `tiemod` solo entra en el `WHERE`.
      **Verificación**: `pytest tests/test_f011_bench.py -k sql_generado -q` —
      comprueba el SQL emitido carácter a carácter y que sigue siendo un
      `SELECT` (R23).

- [ ] **T15**: Reescribir el bucle de `ingest_raw_step.py`: modo global desde
      el watermark, fila en `_meta.etl_runs` para **todas** las tablas
      declaradas (R9), modo por tabla desde el dominio, `metadata` de R10,
      actualización del watermark.
      **Verificación**: `pytest tests/test_f011_ingesta.py -q` (R9, R10, R15,
      R17) con `SigridApiClient` y `PostgresClient` mockeados.

- [ ] **T16**: Añadir `--solo-altas` a `ingest` y la negativa de R16 y R19 en
      `main.py`. `run-all` **no** recibe vía de escape nueva.
      **Verificación**: `pytest tests/test_f011_cli.py -q` (R16, R19) —
      incluye un test de que `run-all` no expone ninguna opción para saltarse
      el modo, en la línea del test equivalente de F-024.

- [ ] **T17**: Tests de no regresión de la puerta de F-024 con escenarios de
      carga incremental.
      **Verificación**: `pytest tests/test_f011_coherencia.py tests/test_f024_dominio.py -q`
      (R13, R14) — los de F-024 pasan **sin modificarse**; si alguno hay que
      tocarlo, el diseño se torció y hay que parar.

- [ ] **T18 · MANUAL (humano)**: primera carga incremental real contra Azure,
      contrastada con una completa inmediatamente posterior:

      ```bash
      python main.py timings                       # estado previo
      # 1) noche/ejecución incremental
      python main.py check-coherencia              # debe decir OK (R9/R13)
      python main.py check-frescura
      python main.py fingerprint-views --out huella_incremental.csv
      # 2) recarga completa a continuación
      python main.py run-all --full
      python main.py fingerprint-views --out huella_full.csv
      python main.py compare-fingerprints huella_incremental.csv huella_full.csv
      ```

      Esperado: `check-coherencia` OK tras la incremental y **cero
      diferencias** entre las dos huellas. Cualquier diferencia es FALLO: se
      marca la feature `blocked` y no se racionaliza (precedente de F-019 T11).
      **Verificación**: `MANUAL (humano)`.

- [ ] **T19**: Actualizar `docs/ARCHITECTURE.md` (modelo de carga resultante y
      corrección de la frase «la ingesta nocturna SIEMPRE `--full`») y
      `azure-apps/datamart_seg_anual.md` (lo que este servicio consume de
      `sigrid-api` y sus variables de entorno nuevas).
      **Verificación**: inspección del reviewer + `pytest tests/test_f011_alcance.py -q`
      (R24: barrido de secretos sobre lo nuevo).

---

## Bloque C · Ventana de negocio (solo se mide)

- [ ] **T20**: Añadir el bloque `ventana:` a `config/business_rules.yaml` con
      el predicado a `null` y el comentario que apunta a DA-1, y el comando
      `perfil-ventana` (+ `fetch_peso_ventana` en `postgres_client.py`).
      **Verificación**: `pytest tests/test_f011_ventana.py -q` (R20, R21).

- [ ] **T21**: Test de alcance que fija que el SQL de `stg` y `mart` no ha
      cambiado en esta rama (R22), y anotar en `progress/current.md` la
      propuesta de feature nueva para acotar el build (DA-5) con los números
      de T8 como justificación.
      **Verificación**: `pytest tests/test_f011_alcance.py -q`.

---

## Cierre

- [ ] **T22**: Campaña de mutación del rigor `critico` y análisis de
      supervivientes.
      **Verificación**: `python -m harness.mutacion --feature F-011` con cero
      supervivientes, o cada superviviente justificado por escrito en
      `progress/mutacion_F-011.md` y **aceptado por el humano**.

- [ ] **T23**: Ejecutar `bash harness/init.sh` en verde (incluye pytest y la
      puerta de cobertura de las líneas cambiadas).
      **Verificación**: `bash harness/init.sh` termina con exit code 0.
