<!-- progress/review_F-024.md -->
# F-024 · Coherencia del datamart ante cargas truncadas — Review de la Fase B (T5–T16)

**Fecha**: 2026-08-18. **Rama**: `feature/F-024-coherencia-cargas-truncadas`.
**Alcance revisado**: Fase B (T5–T16). T1–T4 ya cerradas; T17–T20 son Fase C
(humano) y **no se han ejecutado ni se debían ejecutar**.

## Veredicto

> ## CAMBIOS_REQUERIDOS

Cuatro bloqueantes, todos concretos y baratos. **Ninguno es un fallo de
comportamiento del código**: el código hace lo que la spec pide y lo he
verificado ejecutando mutantes contra él. Lo que falla es la **red de
seguridad**: la garantía más importante de la feature —que el pipeline
nocturno no tiene vía de escape— no está amarrada por ningún test, un
requisito AUTO se quedó sin test trazable, y el traspaso a la Fase C manda al
humano a un comando que no funciona.

Dicho lo que falta, conviene decir también lo que hay: es de las
implementaciones más sólidas que ha pasado por aquí. La puerta va de verdad
antes de escribir (lo he comprobado moviéndola), el dominio es puro y muerde
en mutación, la fase RED trae trazas reales y hasta cazó un error del propio
implementer, y la campaña de mutación es exacta hasta el último mutante.

**Nivel de rigor**: `critico` (declarado en `harness/features.json`). Exige
C1–C5, fase RED con traza, cobertura de las líneas cambiadas ≥ 80 %, campaña
de mutación con **cero supervivientes** salvo justificación escrita aceptada
por el humano, y las verificaciones `MANUAL (humano)` listadas con su comando
exacto.

---

## 1 · Bloqueantes

### B1 · La garantía central de R11/DA-2 no la comprueba ningún test

R11 y DA-2 dicen lo mismo con todas las letras: **`run-all` no tiene vía de
escape**. Es la razón de ser de la política estricta. Pues bien: apliqué a
mano dos mutantes sobre `main.py`, en `build_pipeline_steps`:

```python
BuildStgStep(settings, batch_id=batch_id, omitir_puerta=True),   # M13a
BuildMartStep(settings, batch_id=batch_id, omitir_puerta=True),  # M13b
```

Resultado de la suite **completa** con cada uno aplicado:

```
[*** SUPERVIVIENTE ***] M13a run-all construye BuildStgStep con omitir_puerta=True
     -> 587 passed, 871 warnings in 4.46s
[*** SUPERVIVIENTE ***] M13b run-all construye BuildMartStep con omitir_puerta=True
     -> 587 passed, 871 warnings in 4.62s
```

Es decir: si alguien desactiva **las dos puertas** en el pipeline que corre
todas las noches a las 02:00, los 587 tests siguen en verde y nadie se entera.
La feature entera existe para impedir eso.

El único test de R11 sobre `run-all` —`tests/test_f024_cli.py:502`,
`test_f024_r11_run_all_no_admite_sin_puerta`— comprueba que **click rechaza la
opción**:

```python
resultado = cli(pg).invoke(main.cli, ["run-all", "--sin-puerta"])
assert resultado.exit_code != 0
```

Eso protege la superficie de la CLI, no la composición del pipeline. La opción
no es el peligro; el peligro es el argumento que se le pasa al step.

**Qué hace falta**: un test que afirme sobre los objetos que devuelve
`build_pipeline_steps(...)` que el `BuildStgStep` y el `BuildMartStep`
construidos llevan la puerta activa (p. ej. `_omitir_puerta is False`), y que
falle si alguien la desactiva. `tests/test_f024_cli.py:695-710` ya instrumenta
`build_pipeline_steps` para `full_refresh`: el patrón está a mano.

Nota para el informe de mutación: estos dos mutantes **no son un fallo de la
campaña**. `harness.mutacion` no añade argumentos con nombre, así que no los
genera. Aparecen justamente porque el protocolo del reviewer manda aplicar a
mano los vecinos más peligrosos, y este era el más peligroso de todos.

### B2 · R17 se quedó sin ningún test trazable

R17 es `[AUTO]` y nombra sus dos tests:
`test_f024_r17_meta_en_esquemas_de_consumo` y
`test_f024_r17_grants_cubren_vistas_de_meta`. **No existe ningún
`test_f024_r17_*` en el repositorio** (comprobado sobre los 176 tests de
F-024 y sobre todo `tests/`). El docstring de
`tests/test_f024_meta_y_formato.py:3` anuncia «(R2, R13, R16, R17)» y no
cumple la última.

La conducta subyacente sí está cubierta por F-005
(`tests/test_f005_grants.py:70` y `:81`, que comprueban que `_meta` entra en
los esquemas de consumo por defecto y que se emite
`GRANT SELECT ON ALL TABLES IN SCHEMA "_meta"`), así que **no hay riesgo
inmediato**. Pero:

- C4 exige un test trazable por requisito EARS, y no lo hay.
- La omisión **no está declarada** en §5 «Desviaciones» del informe, donde sí
  se declararon las otras cuatro. Aquí es donde duele: una desviación
  declarada es una decisión; una sin declarar es un descuido, y no hay forma
  de distinguirla de un requisito olvidado.
- Si mañana alguien saca `_meta` de `PG_CONSUMPTION_SCHEMAS`, F-024 no se
  entera: las dos vistas que esta feature expone a MCP y a Power BI se quedan
  sin permisos y la suite sigue verde.

**Qué hace falta**: los dos tests con su nombre trazable (pueden ser dos
líneas cada uno reutilizando `build_readonly_grant_statements`), o —si se
decide que F-005 ya lo cubre— la desviación escrita en el informe y un
puntero desde R17 a los tests de F-005. Lo primero es más barato que discutir
lo segundo.

### B3 · Las verificaciones MANUAL no están en `progress/current.md`

C4, tercer checkbox: «Las verificaciones `MANUAL (humano)` están listadas en
`progress/current.md` con su comando exacto, pendientes de que el humano las
ejecute».

El informe del implementer **sí** cumple su parte y bien: §7 trae la tabla
T17–T20, dice explícitamente «Ninguna se ha ejecutado: todas exigen BBDD o
Azure reales», apunta a dónde vive el comando exacto de cada una y añade
cuatro avisos útiles para quien las ejecute (la extensión `scheduled-query`
es del puesto, el script 95 no se ha ejecutado nunca contra Azure, conviene
capturar `timings --last 3` antes, hace falta `apply-grants` después).

Pero `progress/current.md` sigue describiendo F-024 como «**SPEC ESCRITA el
2026-08-18 — pendiente de aprobación del humano**», con las DA-1..8 listadas
como decisiones abiertas y sus recomendaciones. Eso era verdad hace dos días;
hoy es información falsa: las ocho están cerradas, la Fase B está hecha y lo
que queda pendiente son T17–T20, que no aparecen por ninguna parte del
fichero.

`current.md` es del líder, no del implementer —el propio informe lo dice en
§7 y explica por qué no lo tocó—, así que esto se arregla en el cierre, no
reabriendo la implementación. Pero hay que arreglarlo antes de dar la feature
por revisada: es la memoria externa del arnés, y ahora mismo miente.

### B4 · El comando exacto de R23 manda al humano a una consulta que no funciona

`specs/F-024-coherencia-cargas-truncadas/requirements.md:560`, dentro del
bloque de comandos de R23 (`[MANUAL-Azure]`):

```powershell
az monitor log-analytics query -w $ws --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s == '<job>' | ...
```

`ContainerAppName_s` es exactamente la columna que **T3 demostró que no
existe** para un job, verificada con `| getschema`, y que la enmienda del
2026-08-18 corrige en la cabecera del propio documento (líneas 97-99).
Filtrar por ella devuelve siempre cero filas, que es indistinguible de «el job
no dejó logs»: el humano ejecutaría el paso 1 de R23, vería un 0 y concluiría
que la alerta está rota cuando lo roto es la consulta.

En el mismo bloque, líneas 566-568, las ventanas van en ISO 8601
(`--window-size PT1H --evaluation-frequency PT5M`, y `P1DT6H` al restaurar),
cuando T3 confirmó que `az monitor scheduled-query` exige `##h##m##s` y
rechaza el ISO. Los tres comandos fallarían.

Justo es decir que **`infra/README.md` está bien** —líneas 287 y 303-306
traen la consulta con `ContainerJobName_s` y las ventanas como `1h`, `5m`,
`30h`, con su nota fechada explicando el porqué—, y que el informe apunta a
esa sección la primera para T19. La corrección de esa columna en el README,
de hecho, es un hallazgo del implementer que no le pedía nadie y que estaba
mal desde F-003. Pero la spec es donde el checkpoint manda mirar y donde
mirará quien ejecute la Fase C dentro de tres semanas, y ahí sigue el comando
viejo. Son cuatro sustituciones en `requirements.md`.

---

## 2 · Pendiente de la firma del humano (no lo puedo cerrar yo)

**Los 2 supervivientes de la campaña de mutación.** Los he verificado como
reales (ver §4) y la justificación de equivalencia me parece **correcta en el
fondo**: `bold=True → bold=False` en dos `click.secho` de cabeceras
decorativas de `check-coherencia` no cambia dato, veredicto ni código de
salida, y bajo `CliRunner` —con color desactivado— la salida es idéntica byte
a byte, así que ningún test razonable podría distinguirlos sin convertirse en
un test de `click`. Como reviewer la acepto.

Pero `CHECKPOINTS.md` y `harness/rigor.json` piden, en nivel `critico`, «cero
supervivientes salvo **justificación escrita aceptada por el humano**», y el
análisis de `progress/mutacion_F-024.md` lo firma el líder («completado por el
líder, 2026-08-18»). El líder no es el humano. Es un trámite, no una
objeción técnica: basta con que el humano lo dé por bueno al cerrar.

---

## 3 · Checkpoints

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0. **Ejecutado por mí**:
      `587 passed`, `[OK] PUERTA COBERTURA: 100.0% de 372 líneas cambiadas
      cubiertas (372/372, umbral 80%, nivel critico)`, `ENTORNO LISTO`.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress`: F-024 (11 `pending`, 10 `done`,
      1 `blocked`, 1 `in_progress`).
- [x] Rama actual `feature/F-024-coherencia-cargas-truncadas`, la declarada.
- [ ] **`progress/current.md` describe SOLO la sesión activa.** No: 1.046
      líneas, mayoría de F-003, y su sección de F-024 está congelada en «spec
      escrita, pendiente de aprobación». Ver **B3**. Deuda arrastrada de
      sesiones anteriores, pero hoy además contiene información falsa sobre
      la feature en curso.
- [x] Toda feature `done` tiene resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones

- [x] Dominio sin infraestructura. `domain/ejecucion.py` importa solo
      `datetime` y `secrets`; `domain/coherencia.py` solo `dataclasses`,
      `datetime` y `collections.abc`. La dependencia va en el sentido bueno:
      `postgres_client.py` (infra) importa `EstadoPaso`/`EstadoTablaRaw` del
      dominio, nunca al revés. `FilaFrescura` y `format_frescura` viven en
      infraestructura, que es donde `design.md` §3 los puso a propósito
      (mismo patrón que `timings.py`).
- [x] SQL en su capa: todo lo nuevo es DDL de bootstrap añadido al final de
      `sql/ddl/00_meta.sql`, sin numeración nueva (correcto: no es una capa
      del datamart). Ni una línea de SQL de negocio tocada.
- [x] Primera línea con la ruta relativa en los 11 ficheros nuevos y
      modificados que he comprobado, incluidos los cinco de tests y el `.ps1`.
- [x] Sin `print()` de debug, sin TODOs, sin secretos. Barrido sobre el
      script 95 con `caj-|ruesma|psql-|acr|@|GUID`: cero coincidencias; todo
      sale de `$CFG`.
- [x] Semántica Sigrid intacta: la feature no toca `amb/fas`, `fasnum`,
      `importe_origen` ni ningún SQL de negocio.
- [x] Sin dependencias nuevas.

### C3 bis — Documentos que entran de fuera

**N/A justificado**: F-024 no añade ni modifica ningún fichero de
`docs/referencia/`. Comprobado sobre el diff de la feature
(`b86c5fb..HEAD`): los únicos documentos tocados son `docs/ARCHITECTURE.md`,
`infra/README.md` y la spec, todos escritos aquí, ninguno importado.

### C4 — La verificación es real

- [ ] **Cada requisito EARS con ≥ 1 test trazable.** R1–R16 y R18–R22 sí
      (176 tests `test_f024_*`, todos en verde). **R17 no tiene ninguno**:
      ver **B2**. R23–R26 son `[MANUAL]` y R27 se verifica con `init.sh`, que
      es lo que su propio enunciado dice.
- [x] Los tests no tocan red ni BBDD. Comprobado: cero referencias a
      `psycopg`, `connect(`, `requests`, `httpx`, `socket` en los cinco
      ficheros `test_f024_*`; todo va por `PgFalso`, `CursorFalso`,
      `CliRunner` y `monkeypatch` de `main._get_pg`. El helper `cliente_con`
      (`tests/test_f019_tramos.py:326`) construye el `PostgresClient` contra
      `host=servidor-inexistente` y le sustituye `connection`. La suite entera
      corre en 6 s con `.env` apuntando a Azure. **R27 verificado.**
- [ ] **Las verificaciones MANUAL en `progress/current.md` con su comando
      exacto.** No están (B3), y el comando de R23 en la spec está mal (B4).
      El informe del implementer sí las lista y sí deja claro que quedan para
      el humano.

### C4 bis — El rigor declarado se cumple

- [x] La feature declara `rigor: "critico"` en `harness/features.json`.
- [x] **Fase RED con salida real.** El informe trae la traza pegada de T5 a
      T13, con el comando exacto y el fallo textual: `ModuleNotFoundError`
      para los módulos nuevos, `AttributeError: type object 'StepStatus' has
      no attribute 'ABORTED'`, `TypeError: BuildStgStep.__init__() got an
      unexpected keyword argument 'batch_id'`, los 11/8/37/11 fallos por
      fichero. No es «se siguió TDD»: es la traza. Y la segunda RED de T5
      —hecha a propósito después de crear el módulo, para no quedarse en el
      fallo de importación— es la que cazó un literal equivocado **en el
      test** (la `Z` que faltaba en `YYYYMMDDTHHMMSSZ`). Eso es la fase RED
      haciendo exactamente su trabajo, y está bien contado.
- [x] **Cobertura.** `[OK] PUERTA COBERTURA: 100.0% de 372 líneas cambiadas
      cubiertas (372/372, umbral 80%, nivel critico)`, ejecutada por mí. La
      diferencia con las 1.268 líneas del informe de mutación no es una
      discrepancia: `harness/cobertura.py` cruza el mismo alcance con
      `lineas_ejecutables()`, y 372 de las 1.268 lo son.
- [x] **Mutación verificada de forma independiente.** Ver §4: alcance y
      totales recalculados por mí coinciden **exactamente**.
- [ ] **Cero supervivientes en `critico`.** Los 2 de la campaña están
      analizados y su justificación la acepto, pero le falta la aceptación
      del humano que exige el nivel (§2). Y aparte, he encontrado **2
      supervivientes nuevos** aplicando mutantes vecinos a mano (**B1**), que
      sí exigen un test.
- [x] **Sección «Evidencias» con los cuatro números.** `progress/impl_F-024.md`
      §6: tests (587 passed / 0 failed), cobertura (100 %, 372/372), mutantes
      (108 generados, 106 muertos, 2 supervivientes), tiempo de la suite
      (7,54 s; yo he medido 6,0-6,1 s en dos pasadas, misma magnitud).
- [x] Ningún punto de este bloque marcado N/A sin justificación.

### C5 — La sesión se cerró bien

- [x] `tasks.md` con T5–T16 en `[x]` y **un commit por tarea**, verificado
      uno a uno: `F-024 T5:` … `F-024 T16:`, doce commits consecutivos con el
      formato de `docs/CONVENTIONS.md`. T17–T20 en `[ ]`, que es lo correcto:
      son Fase C.
- [x] Sin artefactos nuevos sin trackear. Los seis `huella_*.csv` de la raíz
      son previos a F-024 (F-019 y T13 de F-003) y ya estaban al abrir la
      sesión. Menor: no tienen entrada en `.gitignore`.
- [x] `features.json` refleja el estado real (`in_progress`, no `done`).

---

## 4 · Verificación independiente de la campaña de mutación

No me he creído el informe: he recalculado el alcance con `harness.alcance` y
los mutantes con `harness.mutacion.generar_mutantes` (cálculo puro, sin
ejecutar la suite ni escribir en disco).

| Métrica | Informe | Recalculado por mí | |
|---|---|---|---|
| Ficheros en alcance | 12 | 12 | coincide |
| Líneas en alcance | 1.268 | 1.268 | coincide |
| Mutantes generados | 108 | 108 | coincide |

Y fichero a fichero también: `coherencia.py` 270 líneas → 30 mutantes,
`postgres_client.py` 176 → 26, `main.py` 274 → 20, `frescura.py` 212 → 14,
`build_stg_step.py` 104 → 4, `build_mart_step.py` 75 → 4, `timings.py` 53 → 7,
`ejecucion.py` 74 → 3, y los cuatro restantes a 0. Suma exacta.

**Los dos supervivientes existen como mutantes reales**, con el mismo operador
y el mismo texto original→mutado que declara el informe:

```
564 booleano | click.secho("=== Estado de raw por tabla ===", fg="cyan", bold=True) -> ... bold=False)
567 booleano | click.secho("=== Estado de stg ===", fg="cyan", bold=True)          -> ... bold=False)
```

No es un informe escrito a mano.

### Mutantes vecinos aplicados a mano

Doce mutantes que la herramienta **no** genera —cadenas SQL, orden de
sentencias, argumentos con nombre—, sobre la puerta de coherencia y el marcado
de huérfanas. Cada uno aplicado, suite ejecutada, fichero restaurado:

| # | Mutante | Resultado |
|---|---|---|
| M1 | La marca de huérfanas pierde el `WHERE status = 'RUNNING'` (reescribiría el histórico entero) | **muere** |
| M2 | La marca escribe `FAILED` en vez de `ABORTED` | **muere** |
| M3 | `fetch_ultimo_intento_stg` ordena por `started_at DESC` en vez de `id DESC` | **muere** |
| M4 | La puerta de `stg` acepta cualquier sub-paso (`startswith` en vez de `==`) | **muere** |
| M5 | `sin_batch` deja de contar para el veredicto | **muere** |
| M6 | Se ignora que falten tablas requeridas | **muere** |
| M7 | La puerta de `raw` pasa a ir **después** del pre-flight | **muere** |
| M9 | La puerta de `stg` se evalúa **después** de todo el SQL de `mart` | **muere** |
| M10 | La puerta de `raw` se evalúa **después** de construir `stg` entero | **muere** |
| M11 | Con `--sin-puerta`, la fila de `stg` se registra `SUCCESS` en vez de `SKIPPED` | **muere** |
| M12 | Ídem en `mart` | **muere** |
| M14 | `check-coherencia` (solo lectura) pasa a marcar huérfanas | **muere** |
| **M13a/b** | **`run-all` construye los steps con `omitir_puerta=True`** | **SOBREVIVE** (B1) |

M3 merece un comentario: el informe explica en §4.3 por qué se ordena por `id`
y no por fecha, y el razonamiento es correcto —la fila de paso se inserta al
terminar, así que su `started_at` es anterior al de sus propios tramos, y por
fecha la puerta de `mart` fallaría **justo las noches buenas**—. Es un detalle
sutil, fácil de «arreglar» mal en un refactor futuro, y hay un test que lo
mata. Bien visto y bien amarrado.

M7, M9 y M10 son la prueba de que R10 y R15 se cumplen de verdad: los tests no
afirman «falló», afirman «falló **antes**». Mover la puerta detrás del primer
SQL pone la suite en rojo en los tres casos.

---

## 5 · Trazabilidad requisito → test

| Req | Cubierto por | |
|---|---|---|
| R1 | `test_f024_r1_*` (dominio: forma, unicidad, orden cronológico, instante inyectado) | ok |
| R2 | `test_f024_r2_ddl_meta_migra_sin_destruir`, `_batch_id_admite_nulos`, `_todas_las_sentencias_del_ddl_son_idempotentes`, `_record_run_escribe_batch_id_si_lo_recibe`, `_llamantes_sin_batch_siguen_funcionando`, `_el_grabador_de_pasos_propaga_su_batch` | ok |
| R3 | `test_f024_r3_run_all_un_solo_batch_para_todas_las_filas`, `_dos_ejecuciones_no_comparten_batch`, `_los_subpasos_y_tramos_llevan_el_batch`, `_sin_batch_el_step_sigue_funcionando` | ok |
| R4 | `test_f024_r4_cada_comando_que_escribe_marca_huerfanas...` (parametrizado), `_la_marca_actualiza_solo_filas_running`, `_warning_por_fila_marcada`, `_aborted_es_parte_del_vocabulario_de_estados` | ok |
| R5 | `test_f024_r5_los_comandos_de_lectura_no_marcan_huerfanas` (doble que revienta si le piden abortar) | ok |
| R6 | `test_f024_r6_timings_muestra_aborted`, `_avisa_de_running_antiguas`, `_no_avisa_de_running_recientes`, `_el_umbral_de_la_huerfana_son_seis_horas_exactas`, `_sin_ahora_se_usa_el_reloj` | ok |
| R7 | `test_f024_r7_fallo_al_marcar_huerfanas_no_impide_el_comando` | ok |
| R8 | `test_f024_r8_*` (OK, falta tabla, no SUCCESS parametrizado, batch nulo, batches distintos, ignora no declaradas) | ok |
| R9 | `test_f024_r9_mensaje_lista_tablas_y_batches`, `_mensaje_termina_con_las_dos_acciones` | ok |
| R10 | `test_f024_r10_puerta_ko_no_toca_stg_y_falla`, `_ningun_raw_incoherente_llega_a_construir` (×4), `_puerta_ok_registra_y_continua`, `_la_puerta_precede_al_preflight` | ok |
| R11 | `test_f024_r11_stage_sin_puerta_registra_skipped_y_continua`, `_sin_puerta_no_es_una_excusa_para_no_mirar`, `_los_comandos_sueltos_admiten_sin_puerta`, `_run_all_no_admite_sin_puerta` | **parcial — B1** |
| R12 | `test_f024_r12_las_requeridas_salen_del_yaml` | ok |
| R13 | `test_f024_r13_vista_raw_state_definida_en_el_ddl`, `_fetch_estado_raw_mapea_filas`, `_fetch_ultimo_intento_stg_coge_la_fila_de_mayor_id`, `_sin_filas_de_stg_no_hay_ultimo_intento` | ok |
| R14 | `test_f024_r14_check_coherencia_codigos_de_salida` (0/1/1), `_explica_por_que`, `_no_escribe` | ok |
| R15 | `test_f024_r15_build_mart_ko_si_ultimo_stage_no_termino` (×5), `_ok_si_stage_success`, `_la_puerta_precede_al_primer_sql_de_mart`, `_sin_puerta_registra_y_continua`, `_sin_batch_sigue_funcionando` | ok |
| R16 | `test_f024_r16_vista_frescura_columnas_y_or_replace`, `_separa_ultimo_ok_de_ultimo_intento`, `_solo_mira_pasos_de_pipeline`, `_las_horas_se_calculan_en_utc`, `_ninguna_vista_de_meta_lee_de_otra_capa`, `_fetch_frescura_mapea_las_ocho_columnas` | ok |
| **R17** | **ninguno** (`test_f005_grants.py:70,81` lo cubre de hecho, pero no de forma trazable) | **B2** |
| R18 | `test_f024_r18_comandos_sueltos_registran_el_paso` (parametrizado), `_un_paso_fallido_registra_y_sale_uno` | ok |
| R19 | `test_f024_r19_format_frescura_veredictos`, `_check_frescura_codigos_de_salida` (×4), `_umbral_por_defecto_coincide_con_dev_json`, `_admite_umbral_y_paso`, +4 más | ok |
| R20 | `test_f024_r20_format_estado_raw_marca_las_incoherentes`, `_la_marca_discrimina_cuando_hay_una_sola_culpable`, `_con_todo_coherente_no_marca_nada`, `_sin_estados_lo_dice` | ok |
| R21 | `test_f024_r21_orquestador_emite_step_finished_con_step_y_status`, `_la_alerta_filtra_por_los_tres_terminos`, `_la_alerta_mira_el_job_por_la_columna_real` | ok |
| R22 | `test_f024_r22_*` (lee de `$CFG` y sin nombres, BOM/CRLF/cabecera, idempotente, ventana derivada y no ISO, dispara por ausencia y se desactiva sola, README en orden, `dev.json`) | ok |
| R23–R26 | `[MANUAL]` — Fase C, T17–T20. No ejecutados (correcto). | **B3/B4** |
| R27 | `bash harness/init.sh` en verde, ejecutado por mí. Sin red ni BBDD, verificado. | ok |

---

## 6 · Verificaciones puntuales que pedía el encargo

- **Dominio puro sin infraestructura**: confirmado (C3).
- **Migración de `_meta` idempotente y compatible con el histórico**:
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS batch_id TEXT NULL` y
  `CREATE INDEX IF NOT EXISTS`, añadidos al final del fichero sin tocar el
  `CREATE TABLE` ni un solo `DROP`. El histórico queda con `batch_id` NULL y
  `format_timings` no cambió de columnas —el aviso de R6 va al pie— así que
  los tests de formato de F-005 siguen verdes. Un test comprueba además que
  ninguna sentencia del fichero rompe el troceador de `postgres_client.py`,
  que es la trampa real: ese fichero se ejecuta en **la primera conexión de
  cada proceso**, o sea cada noche.
- **Puerta antes de cualquier escritura en `build_stg` y `build_mart`**:
  confirmado por lectura (es la primera sentencia de ambos `run()`, antes del
  pre-flight en `stg` y antes de `sql_dir` en `mart`) y por mutación (M7, M9,
  M10 mueren).
- **`--sin-puerta` solo en comandos sueltos y registrado SKIPPED**: la opción
  está en `stage` y `build-mart` y no en `run-all`; la fila queda `SKIPPED`
  **aunque el veredicto sea OK**, que es la lectura literal de R11 y la
  correcta: lo que esa fila cuenta es que el build se hizo sin puerta, no lo
  que la puerta habría dictaminado. M11 y M12 lo amarran.
- **`run-all` sin `--sin-puerta`**: la opción, sí; la composición del
  pipeline, **no** → B1.
- **Marcar huérfanas nunca tumba la carga (R7)**: `_arrancar_ejecucion`
  envuelve `abortar_runs_huerfanos` en `try/except`, loguea
  `huerfanas_no_marcadas` y devuelve la ejecución igualmente. El cliente
  propaga la excepción a propósito y quien decide es la CLI. Correcto y bien
  documentado.
- **`timings` no escribe (R5, DA-7)**: no llama a `_arrancar_ejecucion`;
  avisa al pie por encima de 6 h. M14 confirma que un `check-coherencia` que
  se pusiera a marcar pondría la suite en rojo.
- **Vistas legibles por el rol de solo lectura (R17)**: la conducta está
  bien —`_meta` sigue en los esquemas de consumo y `GRANT SELECT ON ALL
  TABLES` cubre vistas en PostgreSQL— pero sin test trazable → B2.
- **Evento de log estable (R21)**: `orchestrator.py:89` emite `step_finished`
  y no se ha tocado el fichero (diff vacío); el script filtra
  `has_all ('step_finished','build_mart','SUCCESS')`. Los dos extremos
  amarrados, que es justo el punto de R21.
- **Script 95 (R22)**: BOM UTF-8 ✓, CRLF en todas las líneas ✓, cabecera
  `# infra/95_create_alert_frescura.ps1` ✓, idempotente por `show` previo ✓,
  ventana derivada de `$CFG.frescuraUmbralHoras` como `"{0}h" -f $horas` ✓,
  `count 'Frescura' < 1`, severidad 2, `--auto-mitigate true`,
  `ContainerJobName_s` ✓, cero nombres de recurso y cero secretos ✓, aborta
  con mensaje explícito si falta la extensión `scheduled-query` ✓.
- **Suite sin red ni BBDD (R27)**: verificado.
- **DA-8 en `docs/ARCHITECTURE.md`**: corregido y bien contado
  (líneas 185-194): «La ingesta hace commit por PÁGINA, no por tabla», con la
  consecuencia para futuros post mortem —una muerte a mitad de tabla la deja
  truncada y parcial, no intacta— y la nota de que la puerta no depende de
  ello. Corrige explícitamente la afirmación anterior.
- **`azure-apps/datamart_seg_anual.md`**: **sí he podido verificarlo**. Repo
  presente en el puesto, commit `aba68fa` «datamart-seg-anual: expone
  `_meta.v_frescura` y `_meta.v_raw_state` (F-024)», con las columnas de
  ambas vistas, la alerta de frescura y el aviso a los consumidores. Hecho en
  el mismo trabajo, como manda `CLAUDE.md`.

---

## 7 · Observaciones menores (no bloquean)

1. **Los comandos `reset-*` escriben y no marcan huérfanas.** `reset-mart`,
   `reset-cierre`, `reset-compras`, `reset-retenciones`, `reset-fases` y
   `reset-plan-mensual` truncan tablas y no pasan por `_arrancar_ejecucion`.
   Es **coherente con la spec**: la lista de «comando que escribe» de las
   convenciones de `requirements.md` los deja fuera y el test parametrizado de
   R4/R5 la recorre entera. Lo anoto para que sea una decisión y no un olvido
   heredado: si mañana alguien resetea `mart` a mano tras una muerte externa,
   las huérfanas siguen ahí.
2. **`build_mart_step.py` sigue sin salto de línea final.** Deuda previa; el
   diff lo arrastra (`\ No newline at end of file` a los dos lados).
3. **`ruff`**: 3 avisos en los ficheros tocados, los 3 idénticos en la rama
   base (`RUF002` ×2 y `RUF100` en `build_mart_step.py`). Deuda previa, no
   introducida aquí. Los ficheros nuevos pasan limpios, como dice el informe.
4. **Seis `huella_*.csv` sin trackear en la raíz**, de F-019 y de T13 de
   F-003. Previos a esta sesión. Convendría una línea en `.gitignore`.
5. **`config/settings.py` aparece en el alcance de mutación** (12 líneas) sin
   ser de F-024: el alcance se calcula contra `merge-base` con `dev`
   (`8de4d9e`), que arrastra F-003 y F-023. Es conservador —mide de más, no
   de menos— y no invalida nada. Solo conviene saberlo al leer el informe.

---

## 8 · Qué hay que hacer para el APROBADO

1. **B1** — Test que amarre que `build_pipeline_steps` construye
   `BuildStgStep` y `BuildMartStep` **con la puerta activa**. Debe morir con
   `omitir_puerta=True`.
2. **B2** — Los dos tests `test_f024_r17_*` de R17 (o la desviación escrita y
   el puntero a los de F-005).
3. **B3** — `progress/current.md` al día: F-024 en Fase B cerrada, DA-1..8
   cerradas, y T17–T20 listadas con su comando exacto como pendientes del
   humano.
4. **B4** — Corregir en `requirements.md` R23: `ContainerAppName_s` →
   `ContainerJobName_s` (línea 560) y las ventanas ISO 8601 → `##h##m##s`
   (líneas 566-568). El texto correcto ya está en `infra/README.md`.
5. **Firma del humano** sobre los 2 supervivientes equivalentes (§2).

Nada de esto toca la lógica de la feature. Con B1 y B2 hechos vuelvo a pasar
la campaña de mutación sobre lo nuevo y los mutantes M13a/M13b a mano.

---

## 9 · Automejora del protocolo (propuesta, no aplicada)

Los dos supervivientes de B1 no los habría encontrado la campaña automática:
`harness/mutacion.py` no genera mutantes que **añadan un argumento con
nombre** a una llamada, y ahí es donde vivía el agujero más grave de una
feature de rigor `critico`. Propongo, para que lo valore el humano:

- **En `CHECKPOINTS.md`, C4 bis**: dejar escrito que en nivel `critico` el
  reviewer debe aplicar a mano, además de los vecinos del código, los
  mutantes sobre la **composición** (argumentos por defecto de los objetos
  que se construyen en el punto de entrada). Es un patrón repetible: la
  puerta puede estar perfectamente implementada y perfectamente probada, y
  desactivarse en la línea que la instancia.
- **En `harness/mutacion.py`**: un operador nuevo que, para cada parámetro
  booleano con default en una firma, genere el mutante que lo pasa invertido
  en cada sitio donde se construye el objeto. Cubriría este caso de forma
  automática y es genérico, así que iría también a `arnes-base`.

Ambas valen para cualquier proyecto: si el humano las aprueba, se portan a
`arnes-base` en el mismo trabajo, según la regla de propagación de
`CLAUDE.md`.

---

# Re-review · 2026-08-18 (2ª pasada, sobre el commit `89a8707`)

> ## APROBADO

Los cuatro bloqueantes están resueltos. No me he creído el mensaje del líder:
he vuelto a aplicar a mano los mutantes que encontré en la primera pasada y he
comprobado que ahora mueren.

## Verificación de cada bloqueante

### B1 · `run-all` no tiene vía de escape — RESUELTO

Los dos mutantes que sobrevivían a los 587 tests ahora matan la suite:

| Mutante sobre `main.py: build_pipeline_steps` | 1ª pasada | 2ª pasada |
|---|---|---|
| `BuildStgStep(..., omitir_puerta=True)` | 587 passed (**sobrevivía**) | **2 failed**, 589 passed |
| `BuildMartStep(..., omitir_puerta=True)` | 587 passed (**sobrevivía**) | **2 failed**, 589 passed |

Los amarran `test_f024_r11_el_pipeline_nocturno_lleva_las_dos_puertas_activas`
y `test_f024_r11_las_puertas_del_pipeline_no_se_desactivan_ni_con_full_refresh`
(`tests/test_f024_cli.py`), que inspeccionan los objetos que devuelve
`build_pipeline_steps` en vez de la superficie de la CLI. El primero afirma
además que hay exactamente un `BuildStgStep` y un `BuildMartStep`, así que el
segundo —que recorre la lista— no puede quedarse en verde por vacío. Es la
comprobación correcta: la opción no era el peligro, lo era el argumento.

El comentario que precede a los dos tests deja escrito **por qué** existen y
qué agujero tapan. Dentro de seis meses, quien los toque sabrá lo que se juega.

### B2 · R17 con test trazable — RESUELTO

`test_f024_r17_meta_en_esquemas_de_consumo` y
`test_f024_r17_grants_cubren_vistas_de_meta` en
`tests/test_f024_meta_y_formato.py`. No me he limitado a ver que existen y
pasan: he comprobado que **muerden**.

| Mutante | Resultado |
|---|---|
| `_meta` sale de `DEFAULT_CONSUMPTION_SCHEMAS` (`config/settings.py:82`) | **muere** — cae `test_f024_r17_meta_en_esquemas_de_consumo` (y, de paso, `test_f005_r14`) |
| El GRANT deja de cubrir `ALL TABLES IN SCHEMA` (`grants.py`) | **muere** — 3 tests en rojo |

El segundo test cubre además el `ALTER DEFAULT PRIVILEGES`, que es lo que hace
que una vista creada **después** del `apply-grants` siga siendo legible. Va
más allá de lo que pedía R17 y viene bien.

Con esto, los **22 requisitos AUTO (R1–R22) tienen test trazable**; R27 se
verifica con `init.sh` y R23–R26 son MANUAL de Fase C. La tabla de
trazabilidad de la §5 de la primera pasada queda sin ninguna casilla vacía.

### B3 · `progress/current.md` al día — RESUELTO

La sección de F-024 ya no dice «spec escrita, pendiente de aprobación»: dice
**«IMPLEMENTADA (Fase B) — en review; Fase C (Azure) pendiente del humano»**,
con las ocho decisiones cerradas, DA-8 corregida (commit por página) y una
advertencia útil de que donde el fichero diga «transaccional por tabla», en
las secciones históricas de F-003/F-005, hay que leerlo con esa corrección.
Las cuatro tareas de Fase C están listadas con sus comandos y con el puntero a
`requirements.md` R23–R26 y a `infra/README.md`. Y anota explícitamente que la
justificación de los 2 mutantes equivalentes queda pendiente del visto bueno
del humano.

### B4 · Comandos de R23 — RESUELTO

`requirements.md:560` ya usa `ContainerJobName_s`, y las ventanas de las líneas
566-568 pasan a `1h` / `5m` y `30h` / `1h`. Comprobado que **no queda ningún
`ContainerAppName_s` en la spec de F-024** (el único superviviente en el
repositorio está en `specs/F-003-infra-caj/requirements.md:391`, que es
historia de otra feature y ya está corregido donde se opera, en
`infra/README.md`).

En `design.md` §8 la nota «Sintaxis a confirmar en Fase A» pasa a
«**CONFIRMADA** en Fase A (T3, 2026-08-18)» con la sintaxis final, y conserva
el texto original de la duda. Conservarlo es lo correcto: la duda explica por
qué el script no se ejecutó contra Azure sin confirmar.

## Entorno

`bash harness/init.sh` ejecutado por mí sobre `89a8707`:

```
591 passed, 871 warnings in 6.85s
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 372 líneas cambiadas cubiertas (372/372, umbral 80%, nivel critico)
[OK] Rama actual: feature/F-024-coherencia-cargas-truncadas
ENTORNO LISTO. Puedes trabajar.
```

180 tests `test_f024_*` (eran 176). Árbol de trabajo limpio salvo los seis
`huella_*.csv` previos a la feature. El commit `89a8707` sigue el formato
`F-XXX: descripción` que `docs/CONVENTIONS.md` reserva para los ajustes, que
es lo que es.

## Checkpoints que cambian respecto a la 1ª pasada

- **C2**, `current.md` describe la sesión activa: `[ ]` → **`[x]`**.
- **C4**, cada requisito EARS con test trazable: `[ ]` → **`[x]`**.
- **C4**, verificaciones MANUAL en `current.md` con su comando: `[ ]` →
  **`[x]`** (con la corrección de §«Antes de ejecutar T17», abajo).
- **C4 bis**, cero supervivientes: los 2 nuevos que encontré están muertos.
  Queda **solo** la firma del humano sobre los 2 equivalentes de la campaña,
  que no es cosa del implementer ni mía (ver abajo).

El resto de checkpoints se mantiene como en la primera pasada.

## Lo único que queda, y no lo puede cerrar un agente

**La aceptación del humano sobre los 2 supervivientes equivalentes**
(`main.py:564` y `:567`, `bold=True → bold=False` en dos cabeceras
decorativas de `check-coherencia`). Los verifiqué como mutantes reales, la
justificación de equivalencia la considero correcta —bajo `CliRunner`, con el
color desactivado, la salida es idéntica byte a byte— y como reviewer la
acepto. Pero `CHECKPOINTS.md` y `harness/rigor.json` exigen en nivel `critico`
una «justificación escrita **aceptada por el humano**», y esa firma no la
puede dar el líder ni yo. Está anotada como pendiente en `current.md` y el
líder se la pide al humano.

**Este APROBADO cubre la Fase B.** El cierre de F-024 a `done` sigue
exigiendo, según `tasks.md` §Notas de orden, que T17–T20 se ejecuten con
resultado real anotado: en nivel `critico` las verificaciones MANUAL no pueden
quedar en «pendiente» al cerrar.

## Antes de ejecutar T17: una errata que corregir

`progress/current.md:60` escribe el primer comando de T17 como
`infra8_build_image.ps1`. El script se llama **`infra\70_build_image.ps1`**,
que es como lo escribe correctamente el propio fichero en la línea 284. No lo
convierto en bloqueante —la fuente autorizada del comando es `requirements.md`
R25 y `infra/README.md`, y las dos están bien— pero hay que arreglarlo antes
de que nadie intente ejecutar la Fase C leyendo esa línea.

## Nota sobre las dos propuestas de automejora

Siguen sobre la mesa, sin aplicar, para que las valore el humano: la de
`CHECKPOINTS.md` (que en `critico` el reviewer aplique a mano mutantes sobre
la **composición**, no solo sobre el código) y la de `harness/mutacion.py`
(operador que invierta los parámetros booleanos con default en los puntos
donde se construye el objeto). B1 es la prueba de que hacían falta: la puerta
estaba perfectamente implementada y perfectamente probada, y se desactivaba
en la línea que la instancia. Si se aprueban, van a `arnes-base` en el mismo
trabajo.
