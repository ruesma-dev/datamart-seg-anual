Revisión incremental desde 99119e6 (pasada 2) · principal · delta `99119e6..9a8b655`

# F-161 · Review principal

- **Veredicto: APPROVED** (pasada 2). La condición es que el `init.sh` con `.env` del líder salga en exit 0 y con
  `PUERTA COBERTURA` en `[OK]` sobre este HEAD.
- **Pasada 1** (`fbac82e`, revisión completa): CHANGES_REQUESTED por un único hallazgo. La sandbox no ejercitaba D4:
  quitar `tiene_reparto` de 02, 06 o `01b` la dejaba en verde. El código de producción ya se dio por bueno entonces.
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json` (no hay `rigor.local.json`). Exige fase RED,
  cobertura de las líneas cambiadas y C1-C5. La mutación y la capa e2e son informativas. El carril `estandar`
  no lleva RM1-RM7.

## Pasada 2: qué miré y qué ejecuté (2026-11-13)

- **El delta no toca producción.** `git diff --name-only 99119e6..HEAD -- etl_sigrid config main.py infra` sale
  vacío. Solo cambian `tests/test_f161_sandbox.py` y papeleo: `impl_F-161.md`, `current.md`, `tasks.md` (T10 y T11
  marcadas), `features.json` y `BACKLOG.md`. Ninguna firma ni alcance de lo aprobado se mueve.
- **La sandbox nueva** (`8d02b31`):
  - v6 «PLANIFICACION CUATRIMESTRAL MAR-26»: ámbito 8, `plafec` 0, `fec` 2026-03-15, una línea de 150 € sin `planif`.
  - Una partida CP en la v2, para que `fact_cp_tipologia` tenga planificado.
  - Ahora la sandbox ejecuta también los ficheros reales `06_cp_tipologia.sql` y `retenciones/05_fin_obra.sql`, con
    un `raw` y un `cierre` mínimos. La función `fn_sigrid_date` se extrae de `00_setup.sql`, no se reescribe.
  - Asertos concretos: el mensual planificado en v1, v1, v2, v2, v2 (nunca v6); vigencia anual 2026 en v2; CP
    planificado 80,00 €; `fin_obra` = (2, 2026-04-01, …); en marzo, importe en v6 y temporal en v2.
  - El cambio de octubre a marzo es correcto: el mensual del fixture acaba en abril de 2026, así que con octubre
    la mutación de 02 no habría tenido ningún mes en el que ganar.
- **Lo reproduje yo**, en un PostgreSQL 16 desechable (`initdb` en el scratchpad, puerto 55171, parado y borrado al
  terminar). Cada mutación se hizo en una copia `git archive HEAD`; el árbol de trabajo no se tocó.
  - HEAD: **20 passed**.
  - Quitar `tiene_reparto` en las cuatro mutaciones da exactamente la tabla del implementer:

| Mutación (quitar `tiene_reparto`) | Resultado | Tests que caen |
|---|---|---|
| `mart/02_build_fact.sql:70` | 2 failed | r16, r10_d4_el_mensual… |
| `mart/06_cp_tipologia.sql:150` | 2 failed | r10_master_vigente_anual…, r10_d4_la_vigencia_anual_y_cp… |
| `mart/01b_master_versiones.sql:207` | 4 failed | r14 oráculo, r14 hoy, r16, r14_d4_en_marzo… |
| `retenciones/05_fin_obra.sql:162` | 1 failed | r10_d4_el_fin_de_obra… |

- `ARNES_SIN_CACHE=1 bash harness/init.sh` NO lo ejecuté. El líder lo pasa con `.env` y pidió no duplicarlo; el
  worktree no tiene `.env` y daría los rojos de entorno conocidos.
- Tests sin `.env`, con `SIGRID_API_*` ficticios:
  - F-161 (dominio, sql, diccionario, sandbox sin DSN), más f110, f040_frontera y f006_contexto: **176 passed,
    21 skipped**. Los 21 skipped son sandboxes que se quedan sin DSN.
  - Regresión dirigida de la pasada 1: 6036 passed y 0 failed. Desde entonces no ha cambiado código de producción.

## Checkpoints (estado tras la pasada 2)

- **C1** `[x]` condicionado: el exit 0 de `init.sh` con `.env` es del líder.
- **C2** `[x]`. Hay una sola feature activa, y la sección F-161 de `current.md` ya está al día. Las secciones de
  otras features que siguen en `current.md` vienen de `main`.
- **C3** `[x]`.
  - Hexagonal: el dominio es puro y `master_versiones_sql.py` solo construye texto.
  - Convenciones: ruta en la primera línea; sin `print`, TODO ni secretos.
  - Semántica Sigrid: `fas` es la versión, `importe` va sin coeficientes y la v0 sigue D6.
- **C3 bis** `N/A`: no entra ningún documento de fuera.
- **C3 ter** `N/A`: no se registra ninguna conversación nueva. D1-D14 llevan fecha y origen.
- **C3 quater** `[x]`: commit aparte `d6bb377` en `azure-apps`, solo en el documento propio y sin push.
- **C4** `[x]`. Cada requisito tiene un test trazable en verde (tabla abajo), y la capa sandbox de R10 y R16 ahora
  sí muerde. Los unit tests no tocan red ni BBDD. Las tareas MANUAL constan en `current.md` y `impl_F-161.md`, con
  los comandos de design §8. No hay dobles de test nuevos.
- **C4 bis**:
  - Rigor declarado `[x]`.
  - Fase RED `[x]`: trae la salida real (`ModuleNotFoundError`, 83 failed y las trazas de R9 y R10).
  - Cobertura: pendiente de la `PUERTA COBERTURA` del líder.
  - Mutación `N/A por nivel`: es informativa y la campaña corre después de esta pasada.
  - RM1-RM7 `N/A` por carril.
  - Sección «Evidencias» `[x]`.
  - Capa e2e `N/A`: ETL sin interfaz y ningún requisito `(capa: e2e)`.
- **C4 ter** `N/A`: no existe `harness/rutas_sensibles.json`.
- **C5** `[x]`:
  - T1, T2 y T4-T11 están `[x]` con su commit.
  - T3, T7, T12 y T13 son MANUAL en Azure, para después del merge. T14 es la puerta del líder.
  - El árbol queda limpio (salvo este informe).

## Cobertura requisito → test

| R | Tests (todos en verde) |
|---|---|
| R1-R5 | `test_f161_sql` r1-r5 + sandbox r1-r5 contra el oráculo (9 versiones con la v6) |
| R6 | sql r6 ×5 + `test_f157_step` |
| R7-R9 | sql r7 ×9, r8, r9 ×4; dominio r7 |
| R10 | sql r10 ×9; dominio r10; sandbox r10 + **r10_d4 ×4** (02, 06 + CP, `fin_obra`, catálogo); muerden, ver tabla |
| R11 | sql r11 ×2 + sandbox r11; MANUAL paso 4 |
| R12 | sql r12 ×2 + sandbox r12 |
| R13 | MANUAL (paso 4: 776 filas / 2.107.662,97 €) |
| R14-R15, R17 | sql r14 ×7, r15, r17; dominio r14; sandbox r14 (oráculo), **r14_d4_en_marzo**, r15 |
| R16 | sql r14_r16 + sandbox r16 (cae con las mutaciones de 02 y `01b`); MANUAL paso 4 |
| R18-R19 | MANUAL (huellas, `check-cp-tipologia`, T3) |
| R20-R21 | `test_f161_diccionario` r20 ×10, r21 ×3, más f006, f079 y f147 |

## Cambios requeridos

Ninguno. El cambio requerido 1 de la pasada 1 está atendido y comprobado (tabla de arriba).

## Observaciones (siguen abiertas, no bloquean)

- **O1 · Para el humano. `retenciones/05_fin_obra.sql:162` y `:119`.**
  - El catálogo trae ahora versiones con `tiene_reparto` y `version_fec_efectiva` NULL, que antes no estaban.
  - La CTE elige por `MAX(version)` sin mirar fecha: es F-110 D1, y `test_f110…:97` veta las columnas de fecha ahí.
  - Hoy hay 0 casos, y el código es literal a R10.
  - El humano decide: aceptarlo, o añadir `AND v.version_fec_efectiva IS NOT NULL` y aflojar ese veto.
- **O2 · Coste de `stg/10_master_versiones.sql:76-91`.**
  - El `EXISTS` correlado dentro de un `OR` no se convierte en semi-join.
  - Hay además una sonda de índice por línea.
  - Ya está anotado en T3. Si duele, la alternativa es un `IN (SELECT … FROM plan)` con hash o un `UNION ALL`.
- **O3 · R16 solo llega hasta el mes del build.** Es coherente con D9; anotarlo en la spec al cerrar.
- **O4 · `mart/01b_master_versiones.sql:170`.** El `JOIN stg.partidas` es interno: una partida ausente se perdería.
  El paso MANUAL 4 (R13) lo detecta; valorar un `LEFT JOIN`.
- **O6 · `config/diccionario/stg.yaml` (`master_versiones`).** `n_lineas` lleva `agregacion: suma`, y sumarlo entre
  versiones multiplica. Es menor.
- **O5 (papeleo) está resuelta** en `dff7418`.

## Juicio de lo que pidió el líder (de la pasada 1, sigue vigente)

- **Desviaciones 1-9 del implementer: legítimas.**
  - La 1 (`CASE` en vez de `COALESCE`) mejora el design: protege R4 y R11.
  - La 3 queda en O3 y la 4 en O1. La 8 la resolvió el líder con `d6bb377`.
- **Tests de otras features adaptados: ninguno relaja una guarda.**
  - `f097_r17` comprueba los mismos literales en `01b`, que es donde vive ahora la cascada.
  - `f040_r30` exime un solo fichero, con su motivo.
  - `f095` y `f110` alargan la cadena esperada y mantienen el resto, incluido el veto de fechas.
  - `f157_step` sigue exigiendo que `fase0` vaya justo detrás de `plan_mensual`.
  - `f147` sube el tope con su entrada de historia.
  - El de f006 es solo la línea de recuentos de `current.md`.
- **MANUAL (T3, T7, T12/T13): suficientes.**
  - Llevan criterio de parada explícito: cualquier diferencia de huella o de `check-cp-tipologia`, PARAR y volver a
    la imagen anterior; si T3 crece más de 5 min, PARAR.
  - T3 ya incluye O2, y T7 ya incluye contar las versiones de tipo temporal.

## Automejora (propuesta, no aplicada)

- Para `reviewer.md`, punto 2: «si un requisito con capa sandbox protege un filtro, el reviewer comprueba que la
  sandbox se pone en rojo al quitarlo». Es el RM7 llevado a SQL y vale también en `estandar`: en la pasada 1 la
  sandbox estaba en verde y no veía la decisión central de la feature (D4).
