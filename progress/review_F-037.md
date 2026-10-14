<!-- progress/review_F-037.md -->
Revisión incremental desde `19e020d` (pasada 2) · delta `19e020d..1d1b9f6` · 2026-10-14

# F-037 · Review · pasada 2 · APPROVED

**Veredicto: APPROVED (APROBADO).** Los dos cambios de la pasada 1 están resueltos y no queda ningún
cambio requerido. Lo aprobado hasta `19e020d` (código, SQL, permisos, diccionario, las 12
desviaciones y «lo que no puede fallar») queda dado por bueno. El detalle de la pasada 1 vive en el
historial de este fichero, en el commit `b5a08e2`. Se resume abajo para que el informe quepa en el
tope de 140 líneas.

**Nivel de rigor: `critico`** (declarado en `features.json`). Exige fase RED, cobertura ≥ 80 % de lo
cambiado, una campaña completa con cero supervivientes y las MANUAL con su comando exacto.

## Delta revisado (verificado, no supuesto)

- Tres commits, y los tres **solo tocan `progress/`**: `b475edb` (`current.md`), `2abde26`
  (`impl_F-037.md` y `mutacion_F-037.md`) y `1d1b9f6` (`impl_F-037.md`).
  `git diff 19e020d..HEAD -- . ':!progress'` está **vacío**, así que no cambia código, SQL, tests,
  `harness/` ni la spec. El conjunto de ficheros de la feature frente a `main` (sin `progress/`) es
  idéntico al de `19e020d`: comparé el hash de las dos listas.
- **RM1**: `git diff --name-only b475edb..HEAD` = `progress/impl_F-037.md` y
  `progress/mutacion_F-037.md`. **Nada del alcance mutado cambia** después del SHA medido.

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` tal cual sobre `1d1b9f6`: **EXIT 0, ENTORNO LISTO**.
  - **7.826 passed, 242 skipped, 0 failed**, en 1.008,9 s.
  - `PUERTA COBERTURA` [OK]: 100,0 % (136/136, umbral 80 %, crítico).
  - `PUERTA TAMAÑO` [OK]: review 139/140 antes de esta pasada.
  - ruff: 271 avisos de deuda previa.
  - Rama `feature/F-037-tesoreria`.
- **Recálculo puro** con `alcance_de_ficheros` + `generar_mutantes`:
  - `build_tesoreria_step.py`: 157 líneas, 12 mutantes.
  - `domain/tesoreria.py`: 194 líneas, 33 mutantes.
  - Total **45**: coincide con el informe en las líneas de alcance y en el número de mutantes.
  - El árbol queda limpio (`git status`).
- **Campaña no reejecutada: 2 h 04 min según el informe** (7.428,3 s, muy por encima de 60 s). Para
  los veredictos vale mi **RM4 de la pasada 1**: reevalué los 45 sobre una copia y los 45 murieron.
  El código no ha cambiado desde entonces, así que sigue vigente.

## Cambio 1 · Campaña de mutación VÁLIDA: RESUELTO

`progress/mutacion_F-037.md`, generado por la herramienta el 14-10 a las 04:50:
- **No lleva la cabecera «⚠ CAMPAÑA NO VÁLIDA».** En `harness/mutacion.py:1610`, esa cabecera sale
  siempre que `fiable` sea falso, es decir, con `aviso_base`, que incluye la expiración de la base de
  cierre, o con `base_rota`. Que no salga implica que la base de cierre también pasó.
- **Totales:** 45 generados, 45 evaluados, 45 muertos, 0 supervivientes, 0 timeouts y **0 sin
  veredicto (base rota)**. Es una campaña completa, sin muestreo.
- **SHA de HEAD medido:** `b475edbefd5899c43ff79fd21292e4ffd894ed6e`, que coincide con el SHA real
  del commit. Ver RM1 arriba.
- **Línea base:** se corrió en los dos workers (490,6 s y 491,3 s). No es un cero sin base.
- **RM2:** con media = total / evaluados (`mutacion.py:1206`), 165,1 × 45 = 7.429 ≈ 7.428,3 s, y
  cuadra. Por worker salen 330 s frente a una base de 491 s, unas 2/3 partes. Eso no es un salto de
  orden de magnitud, y es lo esperable con `-x` y 45 de 45 muertos (el caso F-038).
- **Ventana temporal:** `b475edb` se commiteó a las 02:39 (+02:00). El implementer declara que la
  campaña corrió de 00:46 a 02:50 UTC, es decir, de 02:46 a 04:50 locales. El informe sale a las
  04:50 y `2abde26` se commitea a las 05:04. La secuencia es coherente.
- **Los dos `timeout` de la primera campaña** (`tesoreria.py:192` y `:193`) salen ahora muertos, como
  dio mi RM4 (3 y 5 fallos). Se confirma que eran efecto de la suspensión.

## Cambio 2 · MANUAL con su comando exacto en `current.md`: RESUELTO

`progress/current.md` tiene una sección propia, «F-037 · Verificaciones MANUAL, con su comando exacto».
- **T13:** los cuatro pasos de design §7 en orden.
  - `az containerapp job show` con los nombres de las variables.
  - `70_build_image.ps1` y `85_update_job.ps1 -Tag`.
  - `psql -f infra/sql/02_roles.sql`.
  - `build-tesoreria` → `build-compras` → `apply-grants`.
- **T14:** las cuatro consultas con su resultado esperado: la negativa con `mcp_sigrid_dm_ro`, la
  positiva con `mcp_sigrid_dm_total` frente a `raw.pag + raw.cob`, R16 y el contraste R30.
- **T15:** `publicar-diccionario` y los tres `check-*`.
- **T16:** la consulta a `_meta.etl_runs` y la negativa repetida.

Comprobé que existen los scripts (`infra/70_build_image.ps1`, `infra/85_update_job.ps1` con
`-Tag`), los siete comandos CLI en `main.py`, los dos logins en `02_roles.sql` y la clave
`verificacion` en `apply_grants_step.py:242`. La sección no trae secretos: la contraseña la pide
`psql`, y el host y el administrador van como `<host>` y `<admin>`.

## Checkpoints (pasada 2)

**C1** [x] init.sh exit 0 sobre `1d1b9f6` · [x] ficheros del arnés presentes.
**C2** [x] una sola `in_progress` (F-037) · [x] rama `feature/F-037-tesoreria` · [x] `current.md`
al día (pasada 1 y ciclo de corrección) · [x] las `done`, en `history.md` (sin cambios).
**C3** [x] Sin cambios de código en el delta. Sigue valiendo la pasada 1: hexagonal, primera línea
con ruta, sin `print`, sin secretos, semántica Sigrid.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] Trazabilidad requisito → test (tabla abajo) · [x] sin red ni BBDD en los unit tests ·
[x] **las MANUAL listadas en `current.md` con su comando exacto** (cambio 2) · [x] dobles: la puerta
de `init.sh` en verde.
**C4 bis** [x] `rigor: critico` declarado · [x] fase RED con trazas reales de T1-T9 (pasada 1) ·
[x] cobertura [OK] 100 % de 136 · [x] **informe de mutación sin «⚠ CAMPAÑA NO VÁLIDA» y con 0 sin
veredicto** (cambio 1) · [x] recálculo puro = 45 · [x] tiempo total > 60 s: campaña no reejecutada,
dicho arriba, y con RM4 vigente · [x] RM1: SHA `b475edb`, delta posterior fuera del alcance · [x] RM2
coherente · [x] RM3: ningún equivalente sale muerto (los 45 cambian el comportamiento) · N/A RM5: no
hay equivalentes declarados · N/A RM6: no se quitó ninguna guarda · [x] la línea base consta en el
informe · [x] sin supervivientes PENDIENTE · [x] «Evidencias» con los cuatro números (7.826 tests,
100 %, 45/0, 1.014 s) y los workers (2). La tabla de campaña MANUAL ya no aplica, porque la campaña
es automática y válida.
**C4 ter** N/A: no hay `harness/rutas_sensibles.json` declarado.
**C5** [x] T1-T12 y T17 en `[x]`, con su commit · N/A T13-T16, justificado: son MANUAL de despliegue
y van después del APROBADO y del merge (design §7) · [x] sin temporales · [x] `features.json` real
(`in_progress`, `critico`).

## Cobertura requisito → test (sin cambios desde la pasada 1)

| Req. | Test |
|---|---|
| R1, R3, R4, R25 bis | `test_f037_dominio` (r1_*, r3_*, r4_*, r25bis_*) |
| R2 | `test_f037_dominio::r2_la_regex_es_la_de_f135`, `test_f037_sql::r2_*`, `r12_la_guarda_recalcula` |
| R5-R9 | `test_f037_sql::r5_*`, `r6_*`, `r7_*`, `r8_la_obra_sale_solo_del_centro`, `r9_*` |
| R10-R14 | `test_f037_sql::r10_*`, `r11_*`, `r12_*` (3), `r13_*`, `r14_*` |
| R15, R16 | `test_f037_sql::r15_*`, `r16_*`, `test_f080_sql::r7_..._vista`, `r8_...`; recuento MANUAL (T14.3) |
| R17, R18 | `test_f037_paso::r17_*`, `r18_*` |
| R19 | `test_f037_diccionario::r19_check_declarados_*`, `r19_check_unicidad_*` |
| R20-R22 | `test_f037_grants::r20_*`, `r21_*`, `r22_*` |
| R23, R29 | MANUAL (T13, T14 y T16), con su comando en `current.md` |
| R24-R27, R30 | `test_f037_diccionario::r24_*`..`r27_*`, `r30_*`; contraste MANUAL (T14.4) |
| R28 | `test_f037_diccionario::docs_*` y `azure-apps` `a781704` (local, sin push) |
| R31 | `bash harness/init.sh` |

## Pasada 1 (resumen; completa en `b5a08e2`)

Revisión completa de `main...19e020d`, CHANGES_REQUESTED solo por evidencia.
- **Verificado entonces:**
  - init.sh en verde.
  - RM4 sobre una copia, con 45 de 45 muertos.
  - El SQL ejecutado en un PostgreSQL 16 desechable: motivos, precedencia y la guarda R12. La vista
    de F-080 sobrevive a una segunda noche.
  - Ningún pago de personal sale en la general.
  - El estándar no tiene acceso a `tesoreria_restringida`.
  - Sin `DROP`.
  - `previsto_antiguo`.
  - La obra sale solo por el centro.
  - El diccionario en v51.
  - Las 12 desviaciones del implementer, aceptadas.
- **Cambios pedidos:**
  1. Repetir la campaña hasta tener un informe VÁLIDO.
  2. Las MANUAL con su comando exacto en `current.md`.

  Los dos quedan resueltos en esta pasada.

## Cambios requeridos

Ninguno.

**Observación para el cierre, sin cambio exigido.** El `INSERT` de 01 y 02 no se ha ejecutado nunca
contra datos reales. Lo probará el primer build de T13, y si falla, la transacción lo deja todo como
estaba. La feature pasa a `done` solo cuando T13-T16 se ejecuten y sus resultados queden en
`impl_F-037.md`. Además, recordad que la imagen del job tiene que llevar este código (memoria «el
repositorio en verde no es producción»).

**Automejora (propuesta, no aplicada).** C4 bis podría admitir, en `critico`, que una campaña «NO
VÁLIDA» **solo por expiración** (base rota = 0) se cierre con una reverificación en serie, a
condición de que traiga una fila por mutante y el reviewer la reproduzca entera sobre una copia. En
F-037 habría ahorrado la campaña repetida: 2 h de CPU para confirmar los 45/45 de mi RM4.
