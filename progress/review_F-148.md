Revisión completa (pasada 1) · diff `main...HEAD` = `9ff322f..4e34599`

# F-148 · Robustez de la nocturna · informe del reviewer

- **Veredicto: CHANGES_REQUESTED.** Hay cuatro cambios pequeños y ninguno es de arquitectura (la lista está al final).
- **Rigor:** `critico`, declarado en `features.json` (D5). Exige fase RED, cobertura ≥ 80 %,
  la campaña de mutación ENTERA con cero supervivientes y las verificaciones MANUAL con su comando.
- **`bash harness/init.sh`** (lo ejecuté yo sobre `4e34599`): exit 0, **8.783 passed, 254 skipped** en 35 min 49 s, `PUERTA COBERTURA` 100 % (281/281), `PUERTA TAMAÑO` OK y `ENTORNO LISTO`.

## Los cinco puntos del líder

1. **Reintento y autenticación: está a medias (cambio 1).** La contraseña no se registra:
   `pg_conexion_reintento` pasa el error por `safe_dsn`, y el DEBUG de psycopg 3.3.4
   (`connection.py:105-116`, `generators.py:76`) solo trae host, puerto, hostaddr y el resumen de
   `PGconn`. El problema es otro: **psycopg 3.3 no pone SQLSTATE a un error de apertura**.
   `generators.py:99` lanza `OperationalError("connection failed: …")` con `sqlstate=None`, así que
   la rama SQLSTATE de `es_error_transitorio` no se ejecuta nunca al conectar. Los casos
   `28P01`/`28000`/`3D000` de `DEFINITIVOS` (`test_f148_conexion.py:186-188`) imitan excepciones que
   `psycopg.connect` no lanza: son verde falso. Lo único que protege son las marcas de texto. Por
   eso hoy se reintentan 4 veces (~14 s de espera) dos errores definitivos que no traen ninguna
   marca: `FATAL: pg_hba.conf rejects connection …` y `FATAL: permission denied for database …`.
   No bloquea la cuenta, pero incumple el «nunca» de R4 y la suite no lo ve.
2. **Reintento de página (R11): correcto por construcción.** Las 76 tablas usan `id_column: ide`,
   y `stream_table` pagina con `WHERE [ide] > ? ORDER BY [ide] ASC` (`sigrid_api_client.py:222`).
   Cada página es un tramo contiguo, posterior a todo lo ya cargado (`--full` trunca y la carga
   incremental arranca en `MAX(ide)`). La PK está en `id_column`, así que un duplicado da
   `UniqueViolation`, que no se reintenta (R12). Como el COPY es atómico, el recuento da 0 o todas, y
   «ambigua» queda como red de seguridad. El recuento hace `commit`: la sesión no se queda en
   `idle in transaction` mientras espera a `sigrid-api`. Un `id_column` que no esté entre las
   columnas ya no carga (`ValueError`), y hoy no le pasa a ninguna tabla.
3. **Reanudación: no adopta lotes ajenos.** Sin la variable, el lote es siempre nuevo (R19, con un
   test por comando). Con ella, solo se adopta un lote con sufijo `-sha256(nombre)[:6]` iniciado en
   las últimas 8 h. Un lote nuevo no lee lo terminado (`Ejecucion.reanudada`).
   `abortar_runs_huerfanos` cierra las `RUNNING` de la réplica muerta. Barrí todas las vistas que
   leen de OTRO esquema construido: `cierre/06`→`mart` (declarada), `compras/05`→`tesoreria.efectos`
   (no se dropea), `compras/03,06` y `retenciones/02`→`maestro` (`CREATE OR REPLACE`),
   `maestro/06`→`personal.*` (no se dropea), `retenciones/00`→`compras.fn_*`. No hay ninguna
   dependencia de DESTRUCCIÓN sin declarar. Queda un efecto sobre los datos (R-a).
4. **Permisos por paso: no abren nada que el final vaya a cerrar.** `ApplyGrantsStep` va entero y
   sin estado sobre el catálogo VIVO: tras cada build deja lo mismo que el final dejaría sobre ese
   catálogo. Los GRANT y los vetos del general van en UNA transacción (`postgres_client.py:1500`). La
   ventana entre el general y el veto del total ya existía; ahora se repite, igual de corta. La puerta
   de mart (`LIKE 'build_stg%'`) no confunde las filas `apply_grants.tras_*`. Coste: sin medir (D4).
5. **`azure-apps` y despliegue: incompletos (cambios 3 y 4).**

## Checkpoints

- **C1** [x] `init.sh` termina con exit 0 (ver arriba). [x] Están todos los ficheros del arnés.
- **C2** [x] Una sola feature en `in_progress`. [x] Rama de la feature. [x] `current.md` al día. [x] Las `done`, en `history`.
- **C3** [x] Hexagonal: `reanudacion.py` es puro, el orquestador va en aplicación, la sesión, el
  reintento y el SQL en infraestructura, y la composición en `main.py`. [x] Primera línea con la ruta
  (los 3 módulos y los 5 tests). [x] Sin `print`, TODOs ni secretos (el barrido solo da `1.2.3.4`,
  de ejemplo), y sin dependencias nuevas. [x] No toca SQL de negocio. Inocuo, aunque fuera del
  diseño: un reordenado de imports en `postgres_client.py:1736`.
- **C3 bis** N/A: no toca `docs/referencia/`. **C4 ter** N/A: no hay `rutas_sensibles.json`.
- **C4** [x] Cada requisito tiene su test (tabla). [x] Ningún test toca red ni BBDD. [x] Las MANUAL
  están en `current.md`. [ ] **Dobles fieles al original**: la puerta automática pasa, pero los
  casos SQLSTATE de R4 imitan algo que `psycopg.connect` no produce (cambio 1).
- **C4 bis** [x] Rigor declarado. [x] Fase RED con trazas reales de T1 a T11. [x] Cobertura 100 %
  (281/281). [x] Mutación recalculada por mí: `alcance_de_feature("F-148", base="main")` da 12
  ficheros y **805 líneas**, y `generar_mutantes` da **92**; coincide con el informe. [x] El «Tiempo
  total» (31.149 s) pasa de 60 s: **campaña no reejecutada (8 h 39 min según el informe)**; queda
  el recálculo puro más las RM. [x] Coste por mutante: 31.149 × 3 / 92 = 1.016 s, de acuerdo con la
  línea base (1.003-1.014 s). [x] Sin cabecera de no válida y con «Sin veredicto» a 0.
  [x] **RM1**: se midió sobre `c2e226d`, y de ahí a HEAD solo cambian `progress/` y `tasks.md`.
  [x] **RM2**: media 338,6 × 3 ≈ línea base, y 92 × 338,6 = total. [x] **RM3**: repasé los 25
  mutantes de `reintento_conexion`, `reanudacion` y `main`, y ninguno es equivalente. [x] **RM5** N/A:
  no hay supervivientes. [x] **RM6**: no se quitó ninguna guarda (la rama «28/3D000» es redundante).
  [x] «Evidencias» trae los cuatro números y los workers. [x] Ningún N/A va sin motivo.
  **RM4** (sobre una copia `git archive HEAD` en el scratchpad): el mutante `not` de
  `sesion_carga.py:111` es **código inválido** (`if comprobar and self._ya_confirmada(filas)):`,
  «unmatched ')'»; compilé los 92 y es el único). «Murió» por un error de importación, y es el que el
  log no imprimió. Su versión válida (`if (comprobar and …):`) la caza la suite: **19 failed** en
  `test_f148_sesion_carga.py`. El cero se sostiene; el defecto es del arnés (ver «Automejora»).
- **C5** [x] Las tareas T1-T15 están en `[x]`, con un commit por tarea. [x] Árbol limpio. [x] `features.json` al día.

## Cobertura requisito → test (`tests/test_f148_*`)

| Req. | Tests |
|---|---|
| R1-R2 | `conexion::r1_r2_*`, `r1_tambien_la_cadena_admin`, `r1_connect_timeout_*` |
| R3, R5 | `conexion::r3_errores_transitorios`, `r3_reintenta_con_espera_2_4_8`, `r3_la_espera_tiene_tope_de_30`, `r5_*`, `r3_la_factoria_*` |
| R4 | `conexion::r4_*` (los casos SQLSTATE son inalcanzables: cambio 1) |
| R6-R7 | `conexion::r3_r6_*`, `sesion_carga::r10_el_reintento_deja_aviso`, `conexion::r7_*` |
| R8-R14, R17 | `sesion_carga::r8_*` … `r14_*`, `r17_*`; `conexion::r17_*` |
| R15-R16 | `conexion::r15_*`, `r16_*` |
| R18-R24 | `reanudacion::r18_*` … `r24_*` (R24 con control negativo), `dominio_*`, `sql_*` |
| R25-R28 | `permisos_por_paso::r25_*` … `r28_*` |
| R29-R30 | `documentacion::r29_*`, `r30_*` |
| R31-R32 | MANUAL (humano), en `current.md` |

## Riesgos que no bloquean

- **R-a · Datos de ayer al reanudar.** `build_retenciones` lee `mart` y `stg` sin declararlos (F-110
  D4). Si en la réplica 1 cae `build_stg`, las retenciones salen con el `mart` de ayer, y la
  réplica 2 ya no las rehace, porque están en SUCCESS (antes de F-148 sí las rehacía). Conviene
  dejarlo escrito en `design.md` §10.
- **R-b · `tcp_user_timeout`** también corta si el servidor deja la ventana TCP a cero más de 60 s
  (un COPY contra un servidor sin créditos de CPU). En la ingesta lo cubre R10; en el COPY de
  `reemplazar_filas` (`ingest_descompuestos`) no hay reintento. Hay que vigilarlo en las 7 noches.
- **R-c · `conexiones_abiertas`** solo cuenta el cliente de la ingesta, y el «~550» no incluye los diez `apply_grants.tras_*`.

## Cambios requeridos

1. **Hacer real R4.** En `etl_sigrid/infrastructure/postgres/reintento_conexion.py:63`, añadir a
   `MARCAS_DEFINITIVAS` `"pg_hba.conf rejects connection"` (o generalizar a `"pg_hba.conf"`) y
   `"permission denied for database"`. Decir en el docstring que psycopg 3.3 no da SQLSTATE al
   abrir (`generators.py:99`), así que las marcas son la única defensa. En `test_f148_conexion.py`,
   añadir a `DEFINITIVOS` casos con la forma REAL
   (`psycopg.OperationalError('connection failed: connection to server at "h" (…), port 5432
   failed: FATAL:  …')`, sin SQLSTATE), uno por marca, y un test que fije que el error de apertura
   llega con `sqlstate is None`. Esto amplía la lista de R4: que el líder lo confirme con el humano.
2. **Mutación del delta.** Si el cambio 1 solo añade literales y tests, el generador no produce
   mutantes nuevos (no muta cadenas). En ese caso basta con dejarlo en `impl_F-148.md`, con el
   recálculo de `generar_mutantes` sobre las líneas nuevas. Si toca lógica: `python -m
   harness.mutacion --feature F-148 --ficheros etl_sigrid/infrastructure/postgres/reintento_conexion.py`.
3. **`azure-apps/datamart_seg_anual.md`** (un commit local nuevo sobre `40b0da9`): (a) «la nocturna
   las mide (`conexiones_abiertas`)» solo vale para la ingesta, y el «~550» no cuenta los permisos
   por paso (R-c); (b) cambiar «la nocturna del 2026-10-22 se quedó colgada» por «las nocturnas del
   17 al 23 de octubre» (H2-H3 analizan el 23). Mismo ajuste en `docs/ARCHITECTURE.md:1018`.
4. **Completar el despliegue MANUAL de `progress/current.md`**: (a) antes del paso 2, anotar el tag
   que corre hoy el job y la vuelta atrás (`infra/85_update_job.ps1 -Tag <anterior>`); (b) tras el
   paso 2, comprobar que el job ya apunta a la imagen nueva (memoria «repositorio verde no es
   producción»); (c) tras la primera nocturna con la v60, **reiniciar el MCP**, que cachea el
   diccionario (como en F-147), y comprobar «Versión 60» en `contexto_bbdd()`; (d) hacer el `git
   push` de `azure-apps` cuando el humano lo autorice y quitar «PENDIENTE de desplegar», con el tag;
   (e) para R31(a): `az containerapp job execution list` no enseña los reintentos de réplica. Usar
   `SELECT step, count(*) FROM _meta.etl_runs WHERE batch_id = '<lote>' AND position('.' IN step) = 0
   GROUP BY step HAVING count(*) > 1` (debe dar cero filas) o comprobar que no aparece
   `ejecucion_reanudada` en Log Analytics.

## Automejora (propuesta, no aplicada)

- **`harness/mutacion.py`, operador `not`** (portarlo a `arnes-base`): ante `not (…)` se come el
  paréntesis y genera código inválido que cuenta como MUERTO. Propuesta: compilar cada mutante en
  `generar_mutantes`, descartar o informar aparte los que no compilan, y sacarlos también en el log.
- **`reviewer.md` / C4:** «una excepción fabricada en un test tiene la forma que da la librería real
  en ESE camino» (aquí, el SQLSTATE en los errores de apertura).
