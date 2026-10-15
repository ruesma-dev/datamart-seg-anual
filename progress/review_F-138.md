<!-- progress/review_F-138.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` sobre `c7afce1` · 2026-10-15

# F-138 · Review · pasada 1 · APPROVED

**Veredicto: APPROVED (APROBADO).** Sin cambios requeridos. Quedan las MANUAL de despliegue
(T14-T16), bien listadas, y cuatro observaciones no bloqueantes al final.

**Nivel de rigor: `estandar`** (declarado en `features.json`): fase RED en lo central, cobertura
≥ 80 % de lo cambiado y campaña de mutación muestreada con supervivientes analizados. RM5 no aplica.

## Verificado por cuenta propia (no leído del informe)

- **`bash harness/init.sh` sobre `c7afce1`**: **ENTORNO LISTO, exit 0** (segunda ejecución). pytest **8.065 passed,
  249 skipped** (19 min); **PUERTA COBERTURA 100 % de 66 líneas**. La primera dio un único KO, el de
  TAMAÑO de este mismo informe (borrador escrito a mitad de la ejecución), con todo lo demás en verde.
- **SQL contra el oráculo en un PostgreSQL 16 DESECHABLE** (`initdb` propio en el scratchpad,
  puerto 54411; ninguna base real): `00_setup.sql` + `15_` **dos veces** (idempotente) en **tres
  bases con `LC_CTYPE` distinto** (`C`, `en-US`, `es-ES`). `fn_texto_normalizado` y
  `fn_clase_liquidacion` = `normalizar`/`clasificar` en **4.003 textos** aleatorios (trozos de los
  patrones con acentos, `ß`, `ǅ`, `ı`, `İ`, `ſ`, `K`, `ﬁ`, `Ｌ`, `²`, combinantes, NBSP, tabuladores,
  saltos): **0 divergencias en las tres**. La regla del SQL y la del Python son la misma.
- Fixture de 19 documentos y 14 alarmas: completa 13 (la 43 fuera), general 11 (sin 33/35); la
  marca (NEGADA gana, CARTA, DUDOSA, REMITE, memo aparte con los booleanos FALSE, ABONO); 5
  contratos (cierre LIQUIDATORIA y CARTA, NEGADA sin cierre, sin facturas → `ultima_factura_cierra`
  NULL, albarán liquidatorio por la línea) y 2 facturas posteriores con sus días: lo que dice la
  spec. **Las dos guardas saltan** y deshacen la transacción: la de ingesta (sin alarmas de factura;
  la general sigue con 11) y la de la restricción (con el `CASE` alterado a `c.tip IN (33)`).
- **Sigrid, solo lectura**: `crefec`/`crehor` son `int` → `INTEGER` en `raw` (lo que exige
  `make_interval`; con `BIGINT` no compilaría). Las familias de la general que podrían rozar
  personal: la **17** son auxiliares 400/407/410/414 y los **6** asientos de la **20** tocan
  400x-477x, 600x, 606x y 621x: **ninguna cuenta de `PREFIJOS_CUENTA_RESTRINGIDA`**. Azure: nada.

## Restricción de datos personales (pedido del líder)

- `settings.py` y `.env.example`: `compras_restringida` en VETADOS y RESTRINGIDOS; no en consumo ni
  en `DEFAULT_TOTAL_VETOED_SCHEMAS`. `ESQUEMAS_DEL_DATAMART` = 16.
- `02_roles.sql`: la crea con `SET ROLE sigrid_dm_etl`; la veta al estándar en los **dos** `DO` del
  5 ter (administrador y dueño: tablas, USAGE y privilegio por defecto), **no** al total; la concede
  al autorizado (USAGE, SELECT, `ALTER DEFAULT PRIVILEGES`), dentro del `BEGIN…COMMIT`, y la nombra
  en las comprobaciones finales. Línea a línea el patrón de `tesoreria_restringida`. `apply_grants`
  no cambia (de listas desde F-135/F-136); lo prueban los tests simulados, incluido «si el estándar
  la lee, el paso falla».
- SQL: la completa filtra la lista explícita (falla cerrada), la general es `WHERE NOT restringido`
  y la guarda recalcula desde `raw.con`. La 43 no entra ni en `raw` (`filtro_conala()`, test R3).

## Las 10 desviaciones del implementer

1 (0 en cualquier campo → `None`: es R10), 2 (la completa filtra las 17: refuerza R3, mismo
conjunto), 3 (`liquidacion_creada_el` NULL si no cierra, declarado), 4 (`ultima_factura_cierra`
NULL sin facturas: R18 solo exige no-NULL a `facturas_terminadas` y `num_*`; declarado), 5
(`num_albaranes_liquidatorios` = `es_liquidatoria`: las 99 cartas son de facturas), 6 (`NULLIF` en
`texto` y `tipo_alarma`), 8 (la entrada histórica v48 sigue en 74), 9 (`test_f066`/`test_f074`
también fijaban 74) y 10 (orden de listas): **aceptadas**. 7 («veintidos» para esquivar la
heurística de `test_f006_stg_trampas`): **aceptada**, pero es un rodeo del test (observación 3).

## Mutación (C4 bis, verificada de forma independiente)

- **Recálculo puro**: `alcance_de_ficheros` = 196 líneas de `liquidatoria.py`, `generar_mutantes`
  = **37**, como el informe. El resto de ficheros de F-138 (`settings.py`, `diccionario.py`,
  `build_compras_step.py`) da **0** mutantes: no queda nada fuera (los 10 de `harness/backlog.py`
  que añade `alcance_de_feature` vienen de `31e537d`, de `main`). El sorteo con semilla `20260820`
  reproduce los 20 evaluados y los **3 supervivientes** (l. 187, mismo operador y texto).
- **Campaña no reejecutada**: 5.597,7 s (93 min) según el informe, por encima de 60 s.
- **RM1**: medido sobre `cb2431a`; `cb2431a..HEAD` solo toca `progress/` y `tasks.md`.
- **RM2**: base 585-588 s; media 279,9 s × 2 workers ≈ 560 s por mutante, coherente con 17 de 20
  muertos con `-x`. Sin «⚠ CAMPAÑA NO VÁLIDA»; 0 sin veredicto.
- **RM3**: ningún muerto es equivalente (familias, 42→43, `(15, 15)`, restringidas, `is not None`,
  la mención, la guarda con `and` —que sí cambia `(20260929, 0)`— y los `divmod`).
- **RM4** (copia en el scratchpad, `test_f138_dominio.py`): los 3 supervivientes → **102 passed**
  (equivalentes: `< 1`/`<= 0` solo difieren en 0, ya excluido por `not`; con `and`, un negativo da
  año u hora negativos y `datetime()` lanza `ValueError` → `None`). Muerto de control
  `divmod(resto, 101)` → **5 failed**. Los tres análisis completos, ninguno `PENDIENTE`.

## Checkpoints

**C1** [x] init.sh exit 0 (arriba) · [x] ficheros del arnés presentes.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-138-facturas-liquidatorias` · [x]
`current.md`: la sección de F-138 está arriba y al día (arrastra historia anterior, 4.184 líneas:
estado heredado, aceptado en F-037 y F-136, no introducido aquí) · [x] `history.md` sin cambios.
**C3** [x] hexagonal: `domain/liquidatoria.py` solo importa `re`, `datetime`, `typing`; el SQL en
`sql/compras/15_…` · [x] primera línea con ruta en los 7 ficheros de código nuevos · [x] sin
`print`, TODO, secretos ni dependencias nuevas · [x] semántica Sigrid: `con` como cabecera,
`fn_sigrid_date`, la cadena factura→contrato idéntica a `fact_por_ctr` de `v_pbi_contrato_consumo`
(comparada); no toca ámbitos, fases ni importes.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] trazabilidad (tabla abajo), todo en verde · [x] unit tests sin red ni BBDD · [x] MANUAL
en `current.md` con su comando exacto y en el orden del design: job e imagen; `psql -X -v
ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn` ANTES del build; `ingest --table conala --full` y
`auxala`; `build-compras`; `apply-grants`; `check-raw-recuentos` y R28-R29;
`publicar-diccionario` y los tres `check-*`; **aviso a `mcp-bbdd`** (lista blanca y reinicio);
`timings`. Los comandos existen en `main.py`; la nocturna es `run-all --full`, así que `conala` sin
`tiemod` se relee entera cada noche · [x] dobles: puerta de `init.sh` en verde.
**C4 bis** [x] `rigor` declarado · [x] fase RED con trazas reales de T1, T2, T4-T8 (T9-T11 son
documentación) · [x] cobertura 100 % de 66 líneas · [x] mutación verificada · [x] campaña > 60 s,
dicho · [x] coste ≈ 560 s/mutante · [x] informe válido · [x] RM1 · [x] RM2 · RM5 N/A (`estandar`)
· RM6 N/A (no se quitó ninguna guarda) · campaña manual N/A (la automática dio 37) · [x]
supervivientes analizados · [x] «Evidencias» con los cuatro números y 2 workers · [x] sin N/A mudo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T13 y T17 `[x]` con su commit `F-138 Tn:`; T14-T16 son MANUAL de despliegue,
pendientes por diseño hasta después del APROBADO · [x] árbol limpio · [x] `features.json`
`in_progress`.

**`azure-apps`**: `0f45bbb` en `master`, local, sin push, árbol limpio: «76 tablas», los cuatro
objetos y el esquema restringido como «SIN DESPLEGAR» y el contrato con `mcp-bbdd`. Cumple R27.

## Cobertura: requisito → test (`tests/test_f138_*.py`)

| Req. | Test |
|---|---|
| R1, R3 | `ingesta_sql::r1_*`, `r3_*`; `dominio::r1_*`, `r3_la_43_no_entra_nunca` |
| R2 | `ingesta_sql::r2_el_censo_pasa_a_76` + censos de F-066/074/085/090/095/097 |
| R4, R32 | `dominio::r4_*`, `r32_el_resto_no_es_restringida_ni_la_25` |
| R5-R9 | `dominio::r5_*`, `r6_*`, `r7_*`, `r8_casos_de_la_spec`, `r9_*` |
| R10 | `dominio::r10_fecha_hora_creacion`; `ingesta_sql::r10_creada_el_en_sql_es_el_oraculo` |
| R11-R14 | `ingesta_sql::r11_*`, `r12_*`, `r13_*` (con `el_sql_clasifica_como_el_oraculo`), `r14_*` |
| R15-R21 | `ingesta_sql::r15_*` … `r21_*` |
| R22-R23 | `grants::r22_*`, `r23_*` + listas de F-006/037/057/135 |
| R24-R27 | `diccionario::r24_*` … `r27_*` |
| R28-R31 | MANUAL (T14-T15); las cifras de R29 vigiladas en la ficha (`diccionario::r29_*`) |

## Observaciones (no bloqueantes)

1. `creada_el` diverge del oráculo con un `crefec` de 7 dígitos (2026093 → `to_date` da
   2026-09-03, Python `None`). Sigrid no trae ninguno (mínimo 20081204).
2. La guarda de la restricción solo mira 33 y 35: una alarma futura de 17, 20 o 25 sobre una
   cuenta o un asiento de personal iría a la general sin aviso. Hoy medido que no. Candidata a F.
3. «veintidos» rodea una heurística de `test_f006_stg_trampas`; el arreglo es afinarla.
4. `ruff`: tres `SIM300` nuevos en `test_f138_dominio.py` (l. 55, 56, 212). Estilo; no bloquea.

## Automejora (propuesta, no aplicada)

En `reviewer.md`, al recalcular el alcance: avisar de que `alcance_de_feature` puede meter ficheros
traídos de `main` (aquí `harness/backlog.py`) si su base no es el `merge-base`; contrastar con
`git diff --stat main...HEAD`.
