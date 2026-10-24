# F-148 · Requisitos

> Robustez de la nocturna. Diagnóstico (solo lectura, 2026-10-23):
> [`progress/explore_F-148_corte.md`](../../progress/explore_F-148_corte.md).
> En una línea: `copy_rows` abre una conexión NUEVA por página (~2.800 en
> `obrparpre`); una de ellas se cuelga 130 s (el `connect_timeout` por defecto
> de psycopg 3, que no configuramos), sin reintento, y mata `ingest_raw`. El
> servidor estaba sano. Las paradas de ~135 s existen desde el 24-09; desde el
> 17-10 caen en el connect. El reintento del job repite desde cero.

## Decisión del humano (2026-10-23): enfoque 1 + 2 + 3 + 4

1. Una conexión por tabla en la ingesta (COPY y commit por página sobre ella).
2. `connect_timeout` corto y reintento de conexión con espera creciente, nunca
   ante errores de autenticación (+ keepalives y `tcp_user_timeout`, decidido
   en `design.md` §4).
3. Reanudar en vez de repetir, y permisos que no dependan del final.
4. Instrumentar por página `http_s`, `pg_connect_s`, `copy_s` (+ psycopg en
   DEBUG solo en el connect).

**Fuera**: mover la hora del job, VNet/NAT Gateway, activar logs del servidor
compartido (escrituras en Azure: quedan como recomendación, `design.md` §9).

## A · La apertura de conexión (parte 2)

- **R1.** El sistema debe incluir `connect_timeout` en TODA cadena de conexión
  (base del datamart y base admin), con el valor de `PG_CONNECT_TIMEOUT_S`
  (por defecto **15**; válido de 2 a 120).
- **R2.** El sistema debe incluir en toda cadena `keepalives=1`,
  `keepalives_idle`, `keepalives_interval`, `keepalives_count` y
  `tcp_user_timeout`, con los valores de `PG_KEEPALIVES_IDLE_S` (30),
  `PG_KEEPALIVES_INTERVAL_S` (10), `PG_KEEPALIVES_COUNT` (3) y
  `PG_TCP_USER_TIMEOUT_MS` (60000). El job no necesita variables nuevas.
- **R3.** SI abrir la conexión falla con un error TRANSITORIO
  (`psycopg.errors.ConnectionTimeout`; `OperationalError` con `sqlstate` de
  clase `08`, `53300` o `57P03`; u `OperationalError` sin `sqlstate` y sin
  marca de autenticación), ENTONCES el sistema debe reintentar hasta
  `PG_CONNECT_INTENTOS` intentos en total (por defecto **4**) con espera
  exponencial (2, 4, 8 s; tope 30 s) y registrar `pg_conexion_reintento` con
  intento, segundos y el error redactado.
- **R4.** SI el error es de AUTENTICACIÓN, PERMISO o destino inexistente
  (mensaje con «password authentication failed», «pg_hba.conf» —«no … entry» y
  «rejects connection»—, «permission denied for database», «role/database …
  does not exist»; o `sqlstate` fuera de los de R3), ENTONCES NO debe
  reintentar. psycopg 3.3 abre SIN `sqlstate`: el texto es la defensa.
- **R5.** SI se agotan los intentos, ENTONCES el sistema debe propagar la última
  excepción, igual que hoy.
- **R6.** Ningún log del reintento ni de la instrumentación debe contener la
  contraseña ni el token (`safe_dsn` o solo el texto del error redactado).
- **R7.** SI falla el `SET ROLE` tras conectar, ENTONCES el sistema debe cerrar
  la conexión y propagar sin reintentar (es un permiso, no la red).

## B · Una conexión por tabla en la ingesta (parte 1)

- **R8.** CUANDO `ingest_raw` carga una tabla, el sistema debe copiar TODAS sus
  páginas sobre UNA sesión de carga (una conexión), con un COPY y un COMMIT por
  página: una página confirmada no se pierde si cae la siguiente (el contrato
  DA-8 de `docs/ARCHITECTURE.md` se mantiene).
- **R9.** MIENTRAS la conexión de la sesión no se rompa, el sistema debe abrir
  exactamente UNA conexión para las N páginas de la tabla.
- **R10.** SI la conexión se rompe durante el COPY o el COMMIT de una página,
  ENTONCES el sistema debe reconectar (con R3) y reintentar ESA página, hasta
  `REINTENTOS_PAGINA` = 3 veces, sin repetir las páginas ya confirmadas.
- **R11.** Antes de reintentar una página, el sistema debe contar las filas de
  la tabla con `id_column` entre el mínimo y el máximo de la página: **0** →
  repite el COPY; **igual al número de filas de la página** → la da por
  confirmada sin copiar (el COMMIT llegó y se perdió el acuse); **otro valor** →
  falla la tabla con un error que diga «página ambigua» y el rango.
- **R12.** SI el error de la página NO es de conexión (datos, clave duplicada,
  permisos), ENTONCES el sistema no debe reintentar: la tabla falla como hoy.
- **R13.** El sistema debe cerrar la conexión de la sesión al terminar la tabla,
  haya ido bien o mal.

## C · Instrumentación (parte 4)

- **R14.** Por cada página, el sistema debe registrar `ingest_pagina` con
  `table`, `page`, `filas`, `http_s` (espera del iterador de `sigrid-api`),
  `pg_connect_s` (tiempo de (re)conexión dentro de esa página; 0 si no hubo),
  `copy_s` (COPY + COMMIT) y `reintentos`, en segundos con 3 decimales.
- **R15.** MIENTRAS `psycopg.connect` está en curso, el logger `psycopg` debe
  estar en DEBUG; al terminar, bien o mal, debe volver a su nivel anterior.
- **R16.** CUANDO una apertura tarda más de 2 s o necesita reintento, el sistema
  debe registrar `pg_conexion_lenta` con `connect_s` e `intentos`.
- **R17.** El paso `ingest_raw` debe dejar en su `metadata` cuántas conexiones
  abrió el cliente (`conexiones_abiertas`), para medir el antes y el después.

## D · Reanudar en vez de repetir (parte 3)

- **R18.** CUANDO `run-all` arranca con `CONTAINER_APP_JOB_EXECUTION_NAME`
  definida, el `batch_id` debe llevar como sufijo los 6 primeros hex del
  SHA-256 de ese nombre; y SI en `_meta.etl_runs` hay un lote con ese sufijo
  iniciado en las últimas `VENTANA_REANUDACION` (8 h), ENTONCES la ejecución
  debe ADOPTAR ese `batch_id` y registrar `ejecucion_reanudada`.
- **R19.** SI la variable no está (puesto, comandos sueltos) o no hay lote que
  adoptar, ENTONCES el sistema debe comportarse como hoy: lote nuevo y nada
  omitido. Los comandos distintos de `run-all` nunca reanudan.
- **R20.** SI la búsqueda del lote falla, ENTONCES el sistema debe avisar
  (`reanudacion_no_disponible`) y arrancar un lote nuevo: no tumba la noche.
- **R21.** Al reanudar, el orquestador debe omitir un paso SOLO si tiene fila de
  paso (sin punto) en `SUCCESS` en el lote y TODAS sus dependencias
  (`depends_on`) también se omiten. `apply_grants` no se omite nunca.
- **R22.** Un paso omitido no se ejecuta ni graba fila en `_meta.etl_runs`
  (`v_frescura` sigue diciendo cuándo se construyó de verdad), cuenta como
  `SUCCESS` para sus dependientes y deja `paso_reanudado` en el log.
- **R23.** Al reanudar, `ingest_raw` debe omitir (sin truncar ni escribir fila)
  las tablas declaradas con fila `ingest_raw.<tabla>` en `SUCCESS` en el lote,
  cargar el resto y anotar `tablas_reanudadas` en su `metadata`.
- **R24.** Tras una ingesta reanudada, la puerta de `build_stg`
  (`evaluar_coherencia_raw`) debe dar OK: todas las tablas vienen del mismo lote.

## E · Permisos que no dependen del final (parte 3)

- **R25.** CUANDO termina —en `SUCCESS` o `FAILED`— un paso EJECUTADO de
  `PASOS_CON_PERMISOS` (`build_stg`, `build_mart`, `build_maestros`,
  `build_tesoreria`, `build_compras`, `build_retenciones`, `build_personal`,
  `build_contabilidad`, `build_descompuestos`, `build_cierre`), `run-all` debe
  aplicar los permisos completos (la lógica íntegra de `ApplyGrantsStep`, con
  sus vetos y verificaciones) y grabar la fila `apply_grants.tras_<paso>`.
- **R26.** SI esa aplicación devuelve `FAILED` o lanza, ENTONCES el sistema debe
  avisar (`permisos_tras_paso_fallidos`) sin cambiar el resultado del paso ni
  detener la noche. `apply_grants` sigue siendo el último paso y el que decide.
- **R27.** SI la noche muere después de un paso de `PASOS_CON_PERMISOS`,
  ENTONCES los permisos aplicados tras ese paso deben quedar ya aplicados (test
  con un paso posterior que lanza).
- **R28.** Un paso omitido al reanudar no dispara la aplicación de permisos.

## F · Documentación y diccionario

- **R29.** La ficha de `_meta.etl_runs` debe decir que un `batch_id` abarca la
  ejecución del job **con su reintento** (pueden convivir dos filas del mismo
  paso en un lote) y que existen las filas `apply_grants.tras_<paso>`;
  `version` de `00_global.yaml` sube a 60.
- **R30.** `docs/ARCHITECTURE.md` (párrafo DA-8 y F-047) y
  `azure-apps/datamart_seg_anual.md` deben describir la conexión por tabla, el
  `connect_timeout` y su reintento, la reanudación y los permisos por paso.

## G · Aceptación en producción (MANUAL, humano)

- **R31.** Tras el despliegue, **N = 7 noches SEGUIDAS** deben cumplir a la vez:
  (a) ejecución del job `Succeeded` SIN reintento de réplica; (b) ninguna fila
  `FAILED`/`ABORTED` en `ingest_raw%`; (c) en la consulta KQL de huecos entre
  páginas (> 100 s, `design.md` §8) ningún hueco atribuido por `ingest_pagina`
  a `pg_connect_s` ni a `copy_s`. Un hueco de `http_s` no rompe la racha pero se
  anota y se remite a `sigrid-api` (D6). Una noche que falle reinicia la cuenta.
- **R32.** El despliegue sigue la secuencia MANUAL de `design.md` §7 y queda
  anotado en `progress/current.md`.
