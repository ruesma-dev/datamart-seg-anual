<!-- specs/F-011-carga-incremental/tasks.md -->
# F-011 · Carga incremental del datamart — Tareas

Una tarea = un commit (`F-011 Tn: descripción`). Orden por dependencia; los
tests van antes o junto a la implementación (fase RED, exigida por el rigor
`critico` que hereda esta feature al no declarar `rigor`).

> **T9 es una PARADA.** Las tareas T10 en adelante **no se empiezan** sin la
> firma del humano sobre `progress/medicion_F-011.md`. Es el «medir antes de
> optimizar» de la feature, convertido en puerta ejecutable.

> **Cambio del 2026-08-18.** El humano cerró seis decisiones y dejó DA-1 sin
> decidir; con ella salió de F-011 el bloque C entero, que ahora es
> `specs/F-025-ventana-negocio-build/`. Efecto sobre esta lista:
> **T20 desaparece** (hueco deliberado: no se renumera nada, para que los
> mensajes de commit `F-011 Tn` sigan apuntando a lo mismo), **T21 se queda**
> reducida a su test de alcance, y **entra T8-bis** (avisar al dueño de
> `sigrid-api` del dato de DA-6). Ver `requirements.md` § «Decisiones
> cerradas».

---

## Bloque A · Medición (se hace siempre)

- [x] **T1**: Crear `etl_sigrid/domain/perfil_carga.py` con `FilaPerfil`,
      `PerfilCarga`, `perfil_de_carga`, `techo_de_mejora`,
      `tablas_que_acumulan` y `format_perfil` (funciones puras, sin imports de
      infraestructura). Tests primero.
      **Verificación**: `pytest tests/test_f011_perfil.py -q` en verde (R1, R2,
      R3), incluida la fase RED documentada.

- [x] **T2**: Añadir `fetch_perfil_carga(batch_id=None)` a
      `postgres_client.py` (solo `SELECT` sobre `_meta.etl_runs`) y el comando
      `perfil-carga` a `main.py`, sin `_arrancar_ejecucion()`.
      **Verificación**: `pytest tests/test_f011_cli.py -k perfil_carga -q`
      (cliente Postgres mockeado; comprueba también R25: cero escrituras en
      `_meta`).

- [x] **T3**: Crear `etl_sigrid/domain/extraccion.py` (`MedicionPagina`,
      `resumen_bench`, `es_sentencia_de_lectura`, `comparar_cap`).
      **Verificación**: `pytest tests/test_f011_bench.py -k "resumen or lectura
      or cap" -q` (R5, R23).

- [x] **T4**: Crear `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` y
      el comando `bench-sigrid --tabla --paginas [--out]`. El adaptador **no
      importa `PostgresClient`**; captura `SigridApiPageSizeTooLargeError` y
      sigue con los tamaños admitidos.
      **Verificación**: `pytest tests/test_f011_bench.py -q` (R4, R5) — el
      cliente HTTP va mockeado; un test comprueba por barrido de imports que
      el módulo no toca Postgres.

- [x] **T5**: Crear `etl_sigrid/domain/tiemod.py` (`EstadoTiemod`,
      `veredicto_tiemod` con `SIRVE` / `NO SIRVE` / `SIN EVIDENCIA`,
      `format_diagnostico`).
      **Verificación**: `pytest tests/test_f011_tiemod.py -q` (R6, R7), con un
      caso por veredicto y los bordes (columna toda nula, tabla vacía, dos
      fotografías idénticas).

- [x] **T6**: Añadir `fetch_diagnostico_tiemod()` a `postgres_client.py` y el
      comando `diagnostico-tiemod [--out] [--comparar-con]` a `main.py`.
      **Verificación**: `pytest tests/test_f011_cli.py -k tiemod -q`.

- [ ] **T7 · MANUAL (humano) · SIGUE PENDIENTE** · PARCIAL: ejecutar las mediciones reales.
      **Hecho lo que se podía sin escribir en Azure** (2026-08-20): el
      desglose por paso y por tabla de TRES cargas completas, leído de los
      logs del job, y el veredicto de `tiemod` contra el catálogo de
      Sigrid. **Sin hacer**: `perfil-carga`/`diagnostico-tiemod` contra el
      datamart —la IP del puesto ha rotado y abrir el firewall es una
      escritura sobre un recurso compartido— y `bench-sigrid`, que va
      contra producción de Sigrid y lo lanza el humano. Números en
      `progress/medicion_F-011.md`. Con `.env`
      apuntando a Azure (ver el aviso de `progress/current.md`):

      ```bash
      python main.py perfil-carga                     # desglose de la carga del 18-ago
      python main.py diagnostico-tiemod --out huella_tiemod_1.csv
      python main.py bench-sigrid --tabla obrparpre --paginas 1000,5000,10000,20000 --out bench_sigrid.csv
      ```

      Y, tras la siguiente carga nocturna completa:

      ```bash
      python main.py diagnostico-tiemod --out huella_tiemod_2.csv
      python main.py diagnostico-tiemod --comparar-con huella_tiemod_1.csv
      ```

      El barrido llega a **20.000**, que es el cap real de `sigrid-api`
      (DA-6); hoy el ETL trabaja a 10.000, por debajo del límite. Lo que aquí
      se busca ya no es descubrir el cap —lo dio el humano— sino si subir el
      `page_size` compra tiempo y **cuál es el corte real del balanceador**
      (R5-bis: documentado 120 s, en uso 230 s, sin acreditar).

      **Verificación**: `MANUAL (humano)`. Los CSV **no se versionan** (van al
      puesto, como las huellas de F-019). El `bench-sigrid` va contra el SQL
      Server de producción: lo lanza el humano en el momento que elija.

- [x] **T8**: Escribir `progress/medicion_F-011.md` con los números reales de
      T7, el `batch_id` de cada carga medida, el cap y el timeout reales
      medidos frente a los documentados (DA-6, R5-bis) y una **recomendación
      firmada de SÍ o NO** implementar el bloque B.
      **Verificación**: el fichero existe, cada número tiene su origen citado
      (`_meta.etl_runs` / salida del bench) y **los dos números del umbral de
      DA-7 están escritos al lado de sus dos límites**: ahorro estimado frente
      a 20 min, y peso de la ingesta frente al 40 % del total. Inspección del
      reviewer.

- [ ] **T8-bis · MANUAL (humano) · SIGUE PENDIENTE**: avisar al **dueño de `sigrid-api`** de que
      `azure-apps/sigrid_api.md` documenta `MAX_ALLOWED_ROWS = 1000` cuando el
      cap real son **20.000** (dato del humano, 2026-08-18), y pasarle de paso
      lo que mida R5-bis sobre el timeout (documentado 120 s, en uso 230 s).
      **Este proyecto NO edita ese documento**: su dueño es `sigrid-api`
      (`CLAUDE.md` § ecosistema; ya pasó con las dos copias divergentes de
      `sigrid_api.md`).
      **Verificación**: `MANUAL (humano)`. Queda anotado en
      `progress/medicion_F-011.md` a quién se avisó y cuándo; el reviewer
      comprueba que **no hay ningún cambio en `azure-apps/`** en la rama
      (`git -C ../azure-apps status --porcelain` limpio).

- [x] **T9 (2026-08-20, FIRMADA: NO al bloque B) · PARADA · MANUAL (humano)**: el humano lee T8 y decide SÍ o NO
      sobre el bloque B, contra el umbral de DA-7.
      Las decisiones DA-2 a DA-7 **ya están cerradas** (2026-08-18,
      `requirements.md` § «Decisiones cerradas»), y DA-1 salió a F-025: en esta
      parada no queda nada más que decidir que el SÍ o el NO.
      **Verificación**: `MANUAL (humano)`. Si la decisión es NO, la feature
      salta a T21 y se cierra entregando solo el bloque A; el trabajo de
      rendimiento continúa en **F-025**, que ataca el 67 % del tiempo.

---

## Bloque B · Ingesta incremental (solo si T9 dice que sí)

- [~] **T10 · DESCARTADA (puerta de R8, 2026-08-20)**: Crear `etl_sigrid/domain/carga_incremental.py` con
      `ModoCarga`, `decidir_modo_de_carga` y `decidir_modo_de_tabla`. Tests
      exhaustivos primero (es la pieza que la campaña de mutación va a morder).
      `decidir_modo_de_carga` recibe **`dia_semana_full`** además de
      `cada_dias`: la regla exacta —el domingo manda, los días son la red— está
      en R12-bis y se implementa literalmente, sin variantes.
      **Verificación**: `pytest tests/test_f011_watermark.py -q` (R12, R12-bis,
      R15, R17), con los cinco casos de R12-bis (domingo con full de ayer,
      domingo con full de hoy, martes a los 6 días, martes a los 7, sin full
      previa) + `python -m harness.mutacion --feature F-011` sin
      supervivientes en este módulo.

- [~] **T11 · DESCARTADA (puerta de R8, 2026-08-20)**: Crear `etl_sigrid/infrastructure/postgres/sql/ddl/01_watermark.sql`
      (tabla `_meta.ingesta_watermark` idempotente + ampliación **aditiva** de
      `_meta.v_raw_state`) y hacer que `_bootstrap_schemas_and_meta` ejecute
      todos los `sql/ddl/*.sql` en orden en lugar del `00_meta.sql` fijo.
      **Verificación**: `pytest tests/test_f011_watermark.py -k ddl -q` (R11):
      el test lee el `.sql`, comprueba `IF NOT EXISTS`, que la vista conserva
      sus columnas actuales en el mismo orden y que no hay bloques `$$`.

- [~] **T12 · DESCARTADA (puerta de R8, 2026-08-20)**: Añadir a `postgres_client.py` `leer_watermark()`,
      `actualizar_watermark(...)` y el parámetro opcional `metadata` de
      `record_run_end(...)`.
      **Verificación**: `pytest tests/test_f011_ingesta.py -k metadata -q`
      (R10), con conexión mockeada.

- [~] **T13 · DESCARTADA (puerta de R8, 2026-08-20)**: Añadir `IngestaSettings` (prefijo `INGESTA_`) a
      `config/settings.py` con los **cuatro** valores por defecto que
      reproducen el comportamiento actual: `modo="full"`, `full_cada_dias=7`,
      **`full_dia_semana=6` (domingo, DA-2)** y `deriva_max_filas=0`. El día de
      la semana se valida en el rango 0–6.
      **Verificación**: `pytest tests/test_f011_cli.py -k apagado -q` (R18):
      sin variables de entorno, la composición del pipeline y el modo de
      ingesta son idénticos a los de hoy.

- [~] **T14 · DESCARTADA (puerta de R8, 2026-08-20)**: Añadir `desde_tiemod` a `SigridApiClient.stream_table` y el
      método `count_rows(source_table, where=None)`. La paginación keyset por
      `ide` **no cambia**: `tiemod` solo entra en el `WHERE`.
      **Verificación**: `pytest tests/test_f011_bench.py -k sql_generado -q` —
      comprueba el SQL emitido carácter a carácter y que sigue siendo un
      `SELECT` (R23).

- [~] **T15 · DESCARTADA (puerta de R8, 2026-08-20)**: Reescribir el bucle de `ingest_raw_step.py`: modo global desde
      el watermark, fila en `_meta.etl_runs` para **todas** las tablas
      declaradas (R9), modo por tabla desde el dominio, `metadata` de R10,
      actualización del watermark.
      **Verificación**: `pytest tests/test_f011_ingesta.py -q` (R9, R10, R15,
      R17) con `SigridApiClient` y `PostgresClient` mockeados.

- [~] **T16 · DESCARTADA (puerta de R8, 2026-08-20)**: Añadir `--solo-altas` a `ingest` y la negativa de R16 y R19 en
      `main.py`. `run-all` **no** recibe vía de escape nueva.
      **Verificación**: `pytest tests/test_f011_cli.py -q` (R16, R19) —
      incluye un test de que `run-all` no expone ninguna opción para saltarse
      el modo, en la línea del test equivalente de F-024.

- [~] **T17 · DESCARTADA (puerta de R8, 2026-08-20)**: Tests de no regresión de la puerta de F-024 con escenarios de
      carga incremental.
      **Verificación**: `pytest tests/test_f011_coherencia.py tests/test_f024_dominio.py -q`
      (R13, R14) — los de F-024 pasan **sin modificarse**; si alguno hay que
      tocarlo, el diseño se torció y hay que parar.

- [~] **T18 · DESCARTADA (puerta de R8, 2026-08-20)** · MANUAL (humano)**: primera carga incremental real contra Azure,
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

- [~] **T19 · DESCARTADA (puerta de R8, 2026-08-20)**: Actualizar `docs/ARCHITECTURE.md` (modelo de carga resultante,
      **la recarga completa de los domingos** y corrección de la frase «la
      ingesta nocturna SIEMPRE `--full`») y `azure-apps/datamart_seg_anual.md`
      (lo que este servicio consume de `sigrid-api` —frecuencia y volumen de
      peticiones— y sus variables de entorno nuevas, `INGESTA_MODO`,
      `INGESTA_FULL_CADA_DIAS`, `INGESTA_FULL_DIA_SEMANA`,
      `INGESTA_DERIVA_MAX_FILAS`). Sigue sin tocarse `azure-apps/sigrid_api.md`
      (T8-bis).
      **Verificación**: inspección del reviewer + `pytest tests/test_f011_alcance.py -q`
      (R24: barrido de secretos sobre lo nuevo).

---

## ~~Bloque C · Ventana de negocio~~ — EXTRAÍDO A F-025 (2026-08-18)

- ~~**T20**~~: **HUECO DELIBERADO.** La tarea que añadía el bloque `ventana:` a
  `config/business_rules.yaml`, el comando `perfil-ventana` y
  `fetch_peso_ventana` **ya no pertenece a F-011**: es
  `specs/F-025-ventana-negocio-build/`, porque depende de DA-1 y DA-1 sigue sin
  decidir. No se renumera: T21, T22 y T23 conservan su número.

- [x] **T21**: Test de alcance que fija que esta rama **no** ha tocado el SQL de
      `stg` ni de `mart` y que **no** existen ni el bloque `ventana:` de
      `config/business_rules.yaml`, ni el comando `perfil-ventana`, ni
      `fetch_peso_ventana` (R22). Y enlazar F-011 con F-025 en la cabecera de
      la spec, ya escrita.
      **Verificación**: `pytest tests/test_f011_alcance.py -q` (R22, R24).
      El reviewer comprueba además que `specs/F-025-ventana-negocio-build/`
      existe con sus tres ficheros y que su DA-1 sigue **abierta**.

---

## Cierre

- [x] **T22**: Campaña de mutación del rigor `critico` y análisis de
      supervivientes.
      **Verificación**: `python -m harness.mutacion --feature F-011` con cero
      supervivientes, o cada superviviente justificado por escrito en
      `progress/mutacion_F-011.md` y **aceptado por el humano**.

- [x] **T23**: Ejecutar `bash harness/init.sh` en verde (incluye pytest y la
      puerta de cobertura de las líneas cambiadas).
      **Verificación**: `bash harness/init.sh` termina con exit code 0.

## Cierre de F-011 (2026-08-20)

**T1-T8 y T21-T23 hechas**: el bloque A -medir- se entrego entero, y es el
resultado de la feature. **T9 es la puerta y esta FIRMADA con un NO** por el
humano (`progress/medicion_F-011.md` §6.2, commit `6125be3`).

**T10-T19 quedan DESCARTADAS**, no pendientes: la puerta de **R8** las
condicionaba a que el ahorro fuera >= 20 min o la ingesta >= 40 % del total, y
lo medido fue **2,25 min** y **19,9 %**. Ninguna de las dos, y van en O. **DA-4**
ya habia escrito que hacer si el watermark no servia -llevar el esfuerzo al
build- y **DA-7** fijo los umbrales antes de medir. La feature ha ejecutado su
propia spec: la rama del NO estaba escrita de antemano.

**Siguen pendientes del humano** T7 (mediciones manuales complementarias) y
T8-bis (avisar al dueño de `sigrid-api`), las dos MANUAL y ninguna bloqueante.

El tiempo esta en `build_stg`: **110,7 min, el 67,0 %** de la carga. Eso es
**F-025**.
