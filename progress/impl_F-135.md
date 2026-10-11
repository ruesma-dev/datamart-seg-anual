<!-- progress/impl_F-135.md -->
# F-135 · Informe del implementer · rigor CRÍTICO

Spec aprobada el 2026-10-11 (D1-D12 recomendadas + precisión del humano: «el rol admin
debe leer como hasta hoy, el rol general, con esta restricción»). Rama
`feature/F-135-restringir-personal-contabilidad`, un commit por tarea (T1-T12, sin push);
`azure-apps` con commit propio `3110470` (sin push). **Ni una escritura, GRANT ni REVOKE
contra Azure**: lo único contra Azure fue T14, un `SELECT` en transacción `READ ONLY`.
Aquí solo hay recuentos y agregados: ni nombres, ni NIF, ni importes de personas.

## 1. Qué cambió

| Tarea | Ficheros | Qué |
|---|---|---|
| T1 | `etl_sigrid/domain/restriccion_personal.py` | Oráculo puro: 14 prefijos CR, `REGEX_CUENTA_RESTRINGIDA` (construida desde la tupla), `PATRON_CONCEPTO_NOMINA`, `es_cuenta_restringida`, `es_asiento_de_personal` (todos NORMAL + CR o nómina), `motivo_restriccion` (CUENTA gana) |
| T2 | `sql/contabilidad/00-03` | `00` crea también `contabilidad_restringida`. `01-03` escriben ahí, **mismas columnas y cálculo que hoy**; `02` gana los CTE `asientos_personal` (GROUP BY asiento sobre `fechados`, ya materializado) y `marcados`, y al final `restringido`, `motivo_restriccion`, `saldo_acumulado_visible` + índice parcial. Guarda R6 sobre el completo |
| T3 | `sql/contabilidad/04-07` (nuevos) | Plan general (521 CR enmascaradas, `restringida`), mayor general (columnas de hoy en su orden, `WHERE NOT restringido`, acumulado visible, guarda R10 en `DO`), saldos generales (`FILTER (WHERE NOT restringido)`, `HAVING`, `num_apuntes_restringidos`, `incompleto`), `apuntes_restringidos_mes` (solo recuentos) |
| T4 | `build_contabilidad_step.py` | `SUB_PASOS` con los 8 ficheros y su esquema destino; docstring |
| T5 | `config/settings.py`, `.env.example` | `raw` fuera de `DEFAULT_CONSUMPTION_SCHEMAS`; `PG_VETOED_SCHEMAS` (`contabilidad_restringida,raw`), `PG_RESTRICTED_ROLE`, `PG_RESTRICTED_SCHEMAS` y sus `*_list`; aviso F-135 en el comentario de F-068 |
| T6 | `postgres/grants.py` | `esquemas_en_conflicto`, `build_veto_statements` (tablas, USAGE y privilegio por defecto), `build_restricted_grant_statements`. `build_readonly_grant_statements` intacto |
| T7 | `postgres_client.py` | `apply_readonly_grants(vetoed_schemas=)` (veto DETRÁS, solo esquemas que existen), `apply_restricted_grants`, `lecturas_indebidas` (`has_schema/table_privilege`, solo catálogo) |
| T8 | `apply_grants_step.py` | Orden de design §5: conflicto → FAILED sin conexión; general + vetos; autorizado (ausente → aviso y sigue); postcondición en catálogo → FAILED con la lista; `metadata` `vetados`, `rol_autorizado`, `verificacion` |
| T9 | `infra/sql/02_roles.sql` | Rol `NOLOGIN` + `CONNECT`, esquema como `sigrid_dm_etl`, `raw` fuera del bucle del punto 5, punto 5 ter (dos concedentes, dentro del `BEGIN…COMMIT`), concesiones del autorizado, comprobación final |
| T10 | `config/diccionario/*`, `domain/diccionario.py` | `contabilidad_restringida.yaml` (3 fichas), `contabilidad.yaml` (general + `apuntes_restringidos_mes`), excepción R21 en `retenciones.yaml`, `R-CONTABILIDAD-RESTRINGIDA`, `R-SALDO-CONTABLE` y `R-FRESCURA` alcanzan el esquema nuevo, **version 49**; esquema 13 en `ESQUEMAS_DEL_DATAMART`; enmienda en `specs/F-006-mcp-azure/design_detalle.md` (212 objetos) |
| T11 | `docs/ARCHITECTURE.md`; `azure-apps/datamart_seg_anual.md`, `mcp_bbdd.md` §2 | Qué lee cada rol, el veto de `raw`, lo pendiente en `mcp-bbdd` F-008 y F-087 |
| T12 | `harness/features.json` (+ `BACKLOG.md`) | Ficha de F-127: el criterio de `apa` (100.502 de 716.007), sin tocar su `status` |

Tests nuevos: `tests/test_f135_dominio.py` (85), `test_f135_sql.py` (61), `test_f135_grants.py`
(40). Adaptados sin cambiar lo que comprueban: `test_f056` (01-03 en el esquema nuevo; además
se arregla su parser, que cortaba la consulta en un `)` dentro de un literal), `test_f005`,
`test_f068` (fakes con la interfaz nueva; `raw` ya no está en el consumo), `test_f095`
(`raw.rac` ya no la lee el MCP), `test_f057` y `test_f006_formato` (13 esquemas).

## 2. Decisiones y desviaciones (justificadas también en `progress/current.md`)

- **Interpretación, no desviación**: «las mismas columnas que hoy» se cumple conservando
  TODAS las de hoy (nombre, orden, cálculo) y añadiendo AL FINAL las tres de R5 en el mayor
  completo; plan y saldos completos, idénticos. Comprobado en local (§4).
- **Desviación**: `version: 49` del diccionario, no 48: F-090 publicó la 48 el 2026-10-10.
- **Veto con `REVOKE ALL`** (no solo `SELECT`) en tablas, esquema y privilegio por defecto.
- **Hallazgo que corrige una premisa (sin efecto en el código)**: en la prueba local con
  un administrador NO superusuario miembro de `sigrid_dm_etl` (como en Azure), una
  concesión que hace el administrador al rol general queda registrada como del DUEÑO, y la
  nocturna SÍ la revoca. Lo que la nocturna no alcanza es una concesión a `PUBLIC` (u otro
  concedente real): ese es el caso que caza la postcondición R18, y el mensaje lo dice.
- `contabilidad_restringida` lleva `consumo_recomendado: true` (es la contabilidad de verdad
  para quien puede leerla); la regla dura explica que el rol general recibe «permission denied».

## 3. Fase RED (comando exacto y salida real, antes del código)

```
$ python -m pytest tests/test_f135_dominio.py -q                                   # T1
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.restriccion_personal'
1 error in 0.32s
$ python -m pytest tests/test_f135_sql.py -q -k "r4 or r5 or r6 or r7"               # T2
FAILED ...test_f135_r4_la_regex_de_cuentas_es_la_del_dominio
FAILED ...test_f135_r7_la_cuenta_gana_al_asiento
18 failed, 28 deselected in 0.64s
$ python -m pytest tests/test_f135_sql.py -q -k "r8 or r9 or r10 or r11 or r12 or r13 or r14"   # T3
FAILED ...test_f135_r8_el_mayor_general_son_los_no_restringidos_con_las_columnas_de_hoy
FAILED ...test_f135_r13_recuentos_sin_importes - Asserti...
14 failed, 32 deselected in 0.64s
$ python -m pytest tests/test_f135_sql.py -k sub_pasos tests/test_f056_contabilidad.py -q        # T4
E  At index 1 diff: ('plan_cuentas', '01_plan_cuentas.sql', 'contabilidad', 'plan_cuentas') != (..., 'contabilidad_restringida', 'plan_cuentas')
3 failed, 1 passed, 108 deselected
$ python -m pytest tests/test_f135_grants.py -q -k "r19 or settings"                  # T5
FAILED ...test_f135_r19_raw_fuera_de_los_esquemas_de_consumo
7 failed, 1 passed, 32 deselected
$ python -m pytest tests/test_f135_grants.py -q -k "r15 or r16 or r17"               # T6
E  AttributeError: module 'etl_sigrid.infrastructure.postgres.grants' has no attribute 'esquemas_en_conflicto'
$ python -m pytest tests/test_f135_grants.py -q -k cliente                          # T7
E  TypeError: PostgresClient.apply_readonly_grants() got an unexpected keyword argument 'vetoed_schemas'
6 failed, 2 passed, 32 deselected
$ python -m pytest tests/test_f135_grants.py -q -k "r15 or r17 or r18 or paso"       # T8
FAILED ...test_f135_r17_un_env_viejo_para_en_seco[consumo0-raw]
8 failed, 6 passed, 26 deselected
$ python -m pytest tests/test_f135_grants.py -q -k r20                               # T9
FAILED ...test_f135_r20_crea_el_rol_autorizado_nologin_con_connect
7 failed
$ python -m pytest tests/test_f135_sql.py -q -k "diccionario or r21 or r22"         # T10
FAILED ...test_f135_r22_regla_dura_contabilidad_restringida
10 failed, 1 passed, 46 deselected
$ python -m pytest tests/test_f135_sql.py -q -k docs                                # T11
FAILED ...test_f135_docs_dicen_que_lee_cada_rol[azure-apps/datamart]
3 failed, 2 passed, 56 deselected
```
Todas en verde tras su código: `pytest tests/test_f135_*.py` → 186 passed.

## 4. Verificación del SQL y de los permisos en un PostgreSQL 16.15 REAL (local)

Contenedor desechable `postgres:16` (16.15, la versión de Azure, `en_US.utf8`), nada de Azure.
Scripts y logs en el scratchpad de la sesión (`prueba_local_sql.py`, `prueba_local_grants.sh`,
`prueba_local_apply_grants.py`).
- **SQL (51 comprobaciones, VERDE)**: raw sintético de 21 apuntes y 10 asientos (nómina,
  pago, anticipo solo por concepto, «Denominación», regularización, cierre de 4753, embargo,
  apunte sin cuenta, retención de profesional, «NÓMINAS» en mayúsculas). Se ejecuta el SQL de
  HEAD (la contabilidad de hoy) y luego los 8 nuevos: **`contabilidad_restringida` = la
  `contabilidad` de hoy** (EXCEPT ALL en los dos sentidos = 0, mismos tipos; el mayor con las 3
  columnas al final); el motivo de cada apunte = el del oráculo Python; general = no
  restringidos, columnas de hoy, acumulado = acumulado de lo visible (banco mixto −500 y no el
  completo); plan con 3 CR enmascaradas y el grupo 640 sin enmascarar; saldos sin filas CR,
  `incompleto` correcto y cuadre con el mayor general; recuentos por mes. **Guarda R10**:
  colando un CR salta («tiene 1 apuntes de cuentas restringidas») y queda la tabla anterior; con
  un `restringido` NULL salta la del recuento («6 visibles + 14 restringidos no suman los 21»).
- **`02_roles.sql`** como administrador NO superusuario (CREATEROLE, como Azure), sobre una base
  provisionada con el `02` de HEAD y con `raw` concedido: corre entero y es reejecutable; tras él,
  el general recibe `permission denied for schema raw` / `... contabilidad_restringida` y sigue
  leyendo `contabilidad.mayor`; el autorizado lee el completo (2 filas, 1 restringida); las dos
  consultas finales: 0 filas y `lee = f` en los dos esquemas.
- **`apply_grants` con el cliente REAL** (16 comprobaciones, VERDE): noche normal SUCCESS y
  `verificacion = ok`; una concesión a PUBLIC sobre `raw.apu` → FAILED nombrando
  `raw (USAGE), raw.apu (SELECT)`; un `.env` viejo con `raw` → FAILED sin ejecutar nada; una
  tabla nueva en `raw` o en la restringida nace sin lectura para el general y con ella para el
  autorizado (privilegio por defecto).

## 5. T14 · contraste de SOLO LECTURA contra Azure (2026-10-11, 02:07 UTC)

`filas_solo_lectura` (READ ONLY, sin bootstrap) con el criterio del SQL de `02` sobre el
`contabilidad.mayor` de hoy (aún sin filtrar). 206,6 s. **Ojo**: se lanzó a las 02:07 UTC, en
plena ventana nocturna; fue lectura pura, pero compitió con la nocturna por la CPU del servidor.

| Medida | 2026-10-11 | Spec (2026-10-09) |
|---|---:|---:|
| Apuntes del mayor | 2.176.231 | 2.175.286 |
| Restringidos (V2) | **55.519** | 55.504 |
| · por cuenta CR / solo por asiento | 33.439 / 22.080 | |
| Asientos / empresas | 8.796 / 25 | 8.791 / 25 |
| **Apuntes CR que quedarían visibles** | **0** | 0 |
| Saldos: parciales (`incompleto`) / enteros fuera | 6.065 / 11.810 | 6.063 / 11.809 |
| Filas de saldos general / completo | 389.862 / 401.672 | |
| Cuentas CR de nivel 5 (enmascaradas) | 521 | 521 |

## 6. Ventana nocturna (medido o estimado)

No medible sin escribir en Azure. Estimado: la copia general del mayor es un CTAS de
~2,12 M filas desde una tabla (sin uniones ni ventana nueva) + 5 índices, y el `02` añade
una agregación por asiento con regex (el `SELECT` equivalente de T14, más pesado, tardó
206 s en lectura y con la nocturna en marcha). **+4-7 min sobre los 590 s de hoy y ~+0,75 GB**.
Con la nocturna en ~4 h 40 min, el margen al `replicaTimeout` de 5 h baja a unos 13-16 min:
**riesgo a vigilar** (T15 mide la duración real).

## 7. Evidencias (números medidos)

| Evidencia | Resultado |
|---|---|
| Suite completa (`bash harness/init.sh`, final sobre `ba557e1`) | **7.486 passed, 238 skipped**, 0 failed; ENTORNO LISTO (exit 0) |
| Tiempo de la suite | **1.462,6 s (24 min 22 s)** el final; 1.896,6 s el de `bbb1c01` |
| `PUERTA COBERTURA` | **100,0 % de 135 líneas cambiadas** (135/135, umbral 80 %, nivel crítico) |
| `PUERTA TAMAÑO` | requirements 149/150, design 238/250, impl 217/220 |
| Mutación (`--feature F-135 --workers 4 --timeout 1800`) | **25 mutantes, 25 muertos, 0 supervivientes, 0 timeouts**, 6.047 s → `progress/mutacion_F-135.md` |
| Tests de F-135 | 186 (85 dominio, 61 SQL/diccionario/docs, 40 permisos) |
| SQL y permisos en PostgreSQL 16.15 real (local) | 51 + 16 comprobaciones en verde (§4) |

Sobre la mutación: el generador del arnés solo produce mutantes de operadores (25 en 530
líneas); el texto de las sentencias SQL que arman `grants.py` y el paso no se muta, y por eso
lo fijan los tests de igualdad exacta (`test_f135_grants.py`) y la ejecución real en local
(§4). El SQL de `sql/contabilidad/` tampoco es Python: lo cubren los contratos expresión a
expresión (`test_f056`, `test_f135_sql`) y la prueba local. Primer intento de la campaña
abortado por **línea base roja** (4 tests): destapó dos fallos míos de T10 (`current.md` sin
el recuento de 1.698 columnas; las fichas del completo declaraban claves alternativas que
F-108 no aprobó). Corregidos en `bbb1c01`; segunda campaña, sobre ese HEAD, la de la tabla.

## 8. MANUAL pendiente (humano), EN ESTE ORDEN y el MISMO DÍA (pasos 3-6 antes de la nocturna)

1. **D3/D9, antes de nada**: abrir cada `.pbix` en uso → «Transformar datos» → origen de
   cada consulta. Esperado: ninguna lee `raw.*`. **Si alguna lo lee, PARAR**: variante B
   (`raw` sigue concedido y van a `PG_EXCLUDED_TABLES` `raw.apu, apa, asi, pag, rac, hmores`).
2. **Espacio**: portal → `psql-albaranes-rs9k2` → almacenamiento usado. Esperado: margen para
   +0,75 GB por debajo del 80 % de 64 GB (la puerta de disco del ETL).
3. **Línea base «antes»** (solo lectura, con el login del ETL o el administrador):
   `SELECT count(*), sum(debe), sum(haber), sum(importe_saldo) FROM contabilidad.mayor;`
   `SELECT count(*), sum(debe), sum(haber), sum(importe_saldo) FROM contabilidad.saldos_cuenta_mes;`
   `SELECT count(*) FROM contabilidad.plan_cuentas;` `SELECT count(*) FROM raw.apu;` — anotar.
4. **`02_roles.sql` como administrador** (pide las contraseñas ACTUALES de Key Vault, porque
   el fichero las fija): `psql "host=<servidor> dbname=sigrid_dm user=<admin> sslmode=require"
   -v ON_ERROR_STOP=1 -v app_pwd="$APP_PWD" -v mcp_pwd="$MCP_PWD" -f infra/sql/02_roles.sql`.
   Esperado: `COMMIT`; 4 roles (`sigrid_dm_restringido_ro` con `rolcanlogin = f`); 13
   esquemas; las dos consultas de privilegios con 0 filas y `lee = f` en `contabilidad_restringida`
   y `raw`. Desde aquí el MCP ya no lee `raw` (su lista blanca ya lo excluía).
5. **Imagen y job**: `infra/70_build_image.ps1` (tag `rYYYYMMDD-HHmm` desde `main` con F-135)
   y `infra/85_update_job.ps1 -Tag <tag>`; **comprobar** con `az containerapp job show` que el
   job lleva ese tag. Si la nocturna corriera con la imagen vieja, su `apply_grants` volvería a
   conceder `raw` (y el general seguiría leyendo el mayor completo).
6. **Desde el puesto**: `python main.py build-contabilidad` y después `python main.py apply-grants`.
   Anotar la duración de `build_contabilidad` frente a los 590 s de hoy (`python main.py timings`).
   Esperado: SUCCESS en los dos; `apply_grants` con `verificacion = ok` en `_meta.etl_runs`.
7. **La copia completa = la `contabilidad` de antes** (administrador): las cuatro consultas del
   paso 3 cambiando `contabilidad.` por `contabilidad_restringida.` en `mayor` y
   `saldos_cuenta_mes` → mismas cifras que el paso 3; `contabilidad_restringida.plan_cuentas`,
   mismo recuento. Y `SELECT count(*) FROM contabilidad.mayor` + `SELECT count(*) FROM
   contabilidad_restringida.mayor WHERE restringido` = recuento del completo (~55.519 restringidos).
8. **Prueba NEGATIVA (R25-R26)** con el login REAL `mcp_sigrid_dm_ro` (contraseña de Key Vault en
   una variable de la sesión): `SELECT 1 FROM contabilidad_restringida.mayor LIMIT 1;` y lo mismo
   con `raw.apu`, `raw.apa`, `raw.pag`, `raw.con`, `raw.hmores` → cada una `ERROR: permission
   denied for schema …` (anotar el mensaje). `SELECT count(*) FROM contabilidad.mayor WHERE
   codigo_cuenta ~ '^(640|641|642|643|644|645|649|465|466|476|460|461|544|4753)';` → 0;
   `SELECT count(*) FROM contabilidad.saldos_cuenta_mes s JOIN contabilidad.plan_cuentas p USING
   (cuenta_id) WHERE p.restringida;` → 0.
9. **Prueba POSITIVA (R27)**, administrador: `GRANT sigrid_dm_restringido_ro TO CURRENT_USER;`
   (si luego `SET ROLE` falla por permisos: `... WITH SET TRUE`), `SET ROLE
   sigrid_dm_restringido_ro; SELECT count(*), count(*) FILTER (WHERE restringido) FROM
   contabilidad_restringida.mayor; RESET ROLE; REVOKE sigrid_dm_restringido_ro FROM
   CURRENT_USER;` → primer recuento = `SELECT count(*) FROM raw.apu`; segundo ≈ 55.519.
10. **Diccionario (T17, líder)**: `python main.py publicar-diccionario` (v49) y
    `python main.py check-diccionario`; reiniciar el MCP; `contabilidad.mayor` responde por el
    MCP en menos de 30 s.
11. **Al día siguiente (R28, T18)**, sin ejecutar nada a mano: repetir el paso 8 y comprobar en
    `_meta.etl_runs` que `apply_grants` terminó SUCCESS con `verificacion = ok`, y la duración
    total de la nocturna frente a las ~4 h 40 min (margen al `replicaTimeout` de 5 h).

## 9. Fuera de alcance (anotado, no implementado)

- `mcp-bbdd` (su F-008): conectar con un login miembro de `sigrid_dm_restringido_ro` según
  quién pregunte, y admitir `contabilidad_restringida` en `seguridad.esquemas_permitidos`.
- F-087 (este repositorio): rol propio de Power BI. Hasta ambas, el rol autorizado no lo usa
  ningún cliente. D8 (quién es «ese rol»), D10 (coste por persona en `personal`) y el ajuste
  del criterio (D9, D12): con Juan Romero.
