<!-- progress/impl_F-085.md -->
# F-085 · Informe del implementer · quién aprobó qué y cuándo

Rama `feature/F-085-quien-aprobo-que-y-cuando`, 2026-10-07. Rigor **estándar**.
Spec aprobada con D1-D8 (D4 enmendada). T1-T11 hechas, un commit por tarea
(`git log 08f14cb..HEAD`); T12-T14 son MANUAL del humano (§6). **Nada se
escribió en Sigrid ni en el Postgres de Azure**: los tests leen el TEXTO del SQL
y del YAML; las únicas lecturas externas fueron metadatos de columnas de `usu` y
`rac` por `sigrid-api` (INFORMATION_SCHEMA, solo lectura).

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `etl_sigrid/domain/documento_procesos.py` (nuevo) | Oráculo puro: `FAMILIAS` {15,44,46,42}, `COLUMNAS_CREDENCIALES_USU` (6), `EMPRESA_PREFERENTE` 1, `Paso`, `PasoEncadenado`, `hora_sigrid`, `normalizar_login`, `encadenar`, `empleado_de_usuario` |
| `config/tables_sigrid.yaml` | `rac`: `where: null` + comentario con cifras y coste (R1); `usu` nueva con las 10 exclusiones, cada una con su motivo (R2); bloque «LO QUE SIGRID NO GUARDA» corregido (R28) |
| `sql/compras/12_documento_procesos.sql` (nuevo) | `compras.documento_procesos` (DROP + CREATE, PK `paso_id`, 3 índices) (R6-R16) |
| `sql/personal/00_setup.sql` | `CREATE TABLE IF NOT EXISTS personal.usuarios_sigrid`, índice único `UPPER(login)` e índice por `empleado_id` |
| `sql/personal/06_usuarios_sigrid.sql` (nuevo) | `TRUNCATE` + `INSERT` desde `raw.usu`, empleado por código (R17-R21) |
| `application/steps/build_compras_step.py` | Sub-paso `12` DETRÁS de `11` (cuenta `documento_procesos`), docstring |
| `application/steps/build_personal_step.py` | Sub-paso `06` al final (cuenta `usuarios_sigrid`), docstring |
| `config/diccionario/compras.yaml` | Ficha `documento_procesos` (R22-R23); `comparativos.fecha_alta`/`fecha_aprobacion` y `comparativo_firmas` (R26) |
| `config/diccionario/personal.yaml` | Ficha `usuarios_sigrid` (R24) |
| `config/diccionario/raw.yaml` | Fichas `usu` (nueva) y `rac` (ya no filtrada); `confir` corregida; «Son 72 tablas» (R25) |
| `config/diccionario/00_global.yaml` | `version` 45 + comentario; «las 72 tablas»; `R-SIGRID-CON` declara `rac.fec`, `rac.res`, `usu.cod`, `usu.res` (R27) |
| `docs/ARCHITECTURE.md` | «Qué se copia de Sigrid: 72 tablas», «Lo que Sigrid NO guarda» corregido, punto nuevo de F-085, nota en el titular de F-067 (R28) |
| `specs/F-006-mcp-azure/design_detalle.md` | Enmienda de inventario: 205 → 206 → **207 objetos** |
| `../azure-apps/datamart_seg_anual.md` | 72 tablas, `rac` entera, `usu`, sección F-085. Commit local **`e08a3bb`** en `azure-apps` (solo ese fichero), sin push |
| Tests nuevos | `test_f085_dominio.py` (38), `test_f085_sql.py` (34), `test_f085_diccionario.py` (48): **120** |
| Tests ajustados | censo 71→72 (`f066`, `f074`, `f097`, `f095` r31, comentarios de `f107`); `f095_r9` → `..._sin_filtro_desde_f085`; listas de sub-pasos (`f047`, `f073`, `f080`, `f057`, `f101`); `f057_r27` (4→5 tablas); `f067_r27` versión `== 44` → `>= 44`; `f108` `DECLARADAS` + `personal.usuarios_sigrid` `[[login]]` (design §7) |

## 2 · Decisiones y desviaciones (justificadas; también en `progress/current.md`)

- **Fichas en el commit que crea el objeto**: `raw.usu` en T4 (con la entrada
  de la ingesta: si no, se rompen las biyecciones ficha↔tabla), la de
  `documento_procesos` en T5 y la de `usuarios_sigrid` en T7. La puerta de
  cobertura exige ficha o pendiente y la lista de pendientes no puede crecer.
- **`06_usuarios_sigrid.sql` resuelve el empleado con un CTE AGRUPADO por
  código** (`COUNT(*) = 1` → ése; si no, la ÚNICA de `emp = 1`; si no, NULL) y
  `LEFT JOIN`, no con el `LEFT JOIN LATERAL` del design §6: misma regla, mismo
  «nunca multiplica» (una fila por código), pero lee `raw.con` una vez y no 233.
- **`12`: `encaja_con_anterior` con `IS NOT DISTINCT FROM`** (no `=`): falso y no
  nulo si un estado viniera nulo, igual que el `==` del oráculo; `dias` con
  `EXTRACT(EPOCH ...)::NUMERIC / 86400` (aritmética exacta, como el `Decimal`
  del dominio); `make_time` con casts a `INT` explícitos. Con los datos medidos
  (`est1`/`est2` enteros nunca nulos) el resultado es el del design §5.
- **Columnas de `usu` y `rac` verificadas contra Sigrid** (INFORMATION_SCHEMA
  por `sigrid-api`): los diez nombres excluidos existen tal cual, en minúsculas
  (la exclusión de la ingesta distingue mayúsculas). `usu` tiene 24 columnas,
  una de ellas `delO` con mayúscula, que SÍ entra (ver riesgos §7).
- **Índice ÚNICO sobre `UPPER(login)`** en `personal.usuarios_sigrid` (R20): si
  Sigrid diera de alta dos logins iguales así, el build de `personal` falla
  (esquema módulo: la noche sigue) en vez de publicar un casado ambiguo.
- **Claves alternativas**: solo `[[login]]` en `personal.usuarios_sigrid`, como
  pide el design §7 (añadida a la lista aprobada de `test_f108`; `check-unicidad`
  la comprobará contra la base). En `documento_procesos` NO se declara
  `(documento_id, orden)`: no lo pide la spec y la lista es de claves aprobadas.
- **Ficha de `raw.confir`** corregida además de las de R26: afirmaba que
  «ninguna tabla de Sigrid» guarda el cambio de estado.
- **NO se tocan (D7, van con F-132)**: el SQL y el dominio de F-067, las fichas
  de `compras.contratos` (l. ~220 «Sigrid no guarda cuando cambio el estado»),
  `historial_estados*`, `v_estado_documentos`, y la fila de F-067 en azure-apps
  («Sigrid no la guarda»). En ARCHITECTURE solo una nota en el titular de F-067.
- **Entorno**: el primer `init.sh` de arranque dio rojo por mi culpa (creé el
  módulo de dominio mientras corría y el barrido de dataclasses lo vio a medias;
  aislado pasa). El segundo, sobre el árbol limpio, **verde** (6.984 passed,
  226 skipped, 1 h 12 min con la máquina saturada por campañas de otros
  proyectos). Para no ensuciarlo trabajé T1-T11 en un worktree temporal (rama
  `trabajo/F-085`, ya borrada) y llevé los commits a la rama de la feature por
  fast-forward.

## 3 · Fase RED (trazas reales)

**T1 · dominio.** Primero sin módulo:

```
$ .venv/Scripts/python.exe -m pytest tests/test_f085_dominio.py -q
    from etl_sigrid.domain.documento_procesos import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.documento_procesos'
ERROR tests/test_f085_dominio.py
1 error in 1.91s
```

Después con un esqueleto (constantes y dataclasses; las cuatro funciones
`raise NotImplementedError`), para ver caer cada caso por comportamiento:

```
$ .venv/Scripts/python.exe -m pytest tests/test_f085_dominio.py -q -p no:cacheprovider
FAILED tests/test_f085_dominio.py::test_f085_r10_hora_sigrid[165211-esperada2]
FAILED tests/test_f085_dominio.py::test_f085_r14_normalizar_login[ Magomez -MAGOMEZ]
FAILED tests/test_f085_dominio.py::test_f085_r11_la_fr26_10025_sale_en_su_orden
FAILED tests/test_f085_dominio.py::test_f085_r12_la_fr26_10025_encaja_paso_a_paso
FAILED tests/test_f085_dominio.py::test_f085_r13_dias_entre_pasos_de_la_fr26_10025
FAILED tests/test_f085_dominio.py::test_f085_r18_varias_fichas_se_queda_la_de_la_empresa_1
  (... 34 en total; los 4 que pasan son las constantes: familias, credenciales,
  empresa preferente y el `momento` de la dataclass)
E       NotImplementedError
34 failed, 4 passed in 2.99s
```

GREEN: `38 passed in 0.90s`.

**T2-T11 · SQL, YAML y diccionario**, antes de tocar nada (tras T1):

```
$ .venv/Scripts/python.exe -m pytest tests/test_f085_sql.py tests/test_f085_diccionario.py -q --tb=no -rfs
FAILED tests/test_f085_sql.py::test_f085_r1_rac_se_ingiere_sin_filtro_y_sin_tex
FAILED tests/test_f085_sql.py::test_f085_r2_usu_excluye_exactamente_las_diez
FAILED tests/test_f085_sql.py::test_f085_r3_ninguna_credencial_de_usu_se_ingiere
FAILED tests/test_f085_sql.py::test_f085_r4_el_censo_pasa_a_72_sin_conpro_rol_ni_log
FAILED tests/test_f085_sql.py::test_f085_r6_las_familias_del_in_son_las_del_dominio
FAILED tests/test_f085_sql.py::test_f085_r11_el_orden_de_la_cadena_es_el_del_dominio
FAILED tests/test_f085_sql.py::test_f085_r18_el_empleado_es_la_regla_del_dominio
FAILED tests/test_f085_sql.py::test_f085_r20_ninguna_credencial_ni_contacto_en_personal
FAILED tests/test_f085_diccionario.py::test_f085_r22_ficha_de_documento_procesos_con_todas_sus_columnas
FAILED tests/test_f085_diccionario.py::test_f085_r26_comparativos_ya_no_dice_que_sigrid_no_guarda_el_cambio
  (... extracto: 79 en total)
SKIPPED [1] tests\test_f085_diccionario.py:229: azure-apps no esta junto a este repositorio
79 failed, 2 passed, 1 skipped in 9.45s
```

Los 2 que pasan desde el principio son guardas de NO cambio, verdes por
diseño: `test_f085_r5_retenciones_sigue_filtrando_el_asiento_en_su_sql` (el
SQL de retenciones ya filtraba) y `test_f085_r21_no_toca_la_configuracion_de_permisos`.
El skip es del worktree temporal (sin `azure-apps` al lado); en el árbol real
corre y pasa (§4).

## 4 · Verificación automática (resultado real)

- Por tarea, la verificación de `tasks.md` (con `-k` cuando el fichero de tests
  cubre tareas posteriores). Tras T11, en el árbol real con `.env` y `azure-apps`:
  `test_f085_*`, `f095`, `f107`, `f006_reglas`, `f067_reset` → **309 passed**.
- `bash harness/init.sh` final: ver «Evidencias».

## 5 · Coste en la ventana nocturna (estimado; el real es R32, MANUAL)

| Pieza | Estimación | De dónde sale |
|---|---|---|
| Ingesta `rac` sin filtro | 3-4 min (+2-3 min sobre los 75 s de anoche), ~375 MB (+260 MB) | banco de lectura de la spec, 14.154 filas/s |
| Ingesta `usu` | < 1 s, 233 filas | 24 columnas, una página |
| Sub-paso `12` (compras) | 1-3 min, ~200-250 MB con índices | ~1,01 M filas, una ordenación por documento, 2 traducciones de estado por fila (patrón de `11`) |
| Sub-paso `06` (personal) | < 2 s | 233 filas, un barrido agrupado de `con` tipo 43 |

**Total: +4 a +7 min** sobre la nocturna del 2026-10-07 (4 h 37 min 44 s), que
ya está 38 min por encima de las 4 h de referencia. No lo causa F-085, pero lo
agrava: **enseñárselo al humano antes de desplegar**.

## 6 · MANUAL pendiente (humano). Postgres LOCAL/dev del `.env`, nunca Azure

T12 (R29, R32):
```
python main.py ingest --table rac --full      # anotar duración: ~3-4 min
python main.py ingest --table usu --full      # 233 filas
python main.py build-compras                  # anotar duración del sub-paso documento_procesos (log compras_substep_done)
SELECT orden, proceso, estado_origen_codigo, estado_destino_codigo, usuario, nombre_usuario, momento, asiento_id, es_ultimo
FROM compras.documento_procesos WHERE familia = 'FACTURA' AND codigo_documento = 'FR26/10025' ORDER BY orden;
```
Debe salir: 1 Comprobar factura REC→COM jmvargas 2026-09-28 16:52:11 (sin
asiento) · 2 Contabilizar COM→CON jmvargas 16:52:50 asiento 2843515 · 3 Aprobar
CON→APJO ialvarez 2026-10-05 16:23:32 · 4 Aprobar APJO→APRJG jmsanchez 16:58:15,
`es_ultimo` solo en el 4.º y `nombre_usuario` en los cuatro.

T13 (R30, ±0,5 puntos de la spec):
```
SELECT familia, COUNT(DISTINCT documento_id), AVG((encaja_con_anterior)::int), AVG((nombre_usuario IS NOT NULL)::int)
FROM compras.documento_procesos GROUP BY familia;      -- 166.840 / 18.539 / 19.822 / 666 docs; nombre ~93,0 % global
SELECT p.familia, AVG((p.estado_destino_id = c.est)::int) FROM compras.documento_procesos p
JOIN raw.con c ON c.ide = p.documento_id WHERE p.es_ultimo GROUP BY p.familia;   -- >= 99,9 %
python main.py build-personal
SELECT COUNT(*), COUNT(empleado_id), COUNT(dni) FROM personal.usuarios_sigrid;   -- 233 / 210 / ~204
```

T14 (R31): antes y después de `python main.py build-retenciones`,
`SELECT COUNT(*), COUNT(obra_id), SUM(importe) FROM retenciones.apuntes_contables;`
→ idénticos. Y `python main.py check-raw-recuentos` en verde para `rac` y `usu`.

**Despliegue (Azure, lo autoriza el humano)**: imagen nueva y job;
`publicar-diccionario` (versión 45); reiniciar `mcp-bbdd`. La primera nocturna
crea `raw.usu` y recarga `raw.rac` entera; comprobar con `check-raw-recuentos`.

## 7 · Riesgos y lo que queda fuera

- **`usu.delO`** (mayúscula en el nombre, `varchar(8)`, «Delegación origen»)
  entra en `raw.usu` con su nombre entre comillas. La ingesta cita los
  identificadores (`sql.Identifier`), así que no debería fallar; si T12 diera
  error en esa columna, se añade a `exclude_columns` (no se usa).
- Fuera, por decisión: `dbo.log` (F-105), `conpro`, `rol` (D8), `rac.tex` (D3),
  la antigüedad del estado de F-067 desde `rac` (F-132, D7), el enlace
  factura→asiento con importes (F-091), `nodesa` (significado sin confirmar).

## Evidencias

| Evidencia | Valor real (medido) |
|---|---|
| Tests ejecutados | **7.132 passed, 228 skipped, 0 failed** (`bash harness/init.sh`, 2026-10-07, HEAD `aa5b10f`); 120 nuevos de F-085 |
| Cobertura de líneas cambiadas | **100,0 %** (74/74, umbral 80 %): `PUERTA COBERTURA` de `init.sh` |
| Mutación (muestreo del nivel estándar: 20 de 49, semilla 20260820) | **20 evaluados, 20 muertos, 0 supervivientes, 0 timeouts**: `progress/mutacion_F-085.md` |
| Tiempo de la suite | 3.127,7 s (52 min) con cobertura y la campaña de mutación compitiendo; sin cobertura y sin campaña, 1.136,9 s (18 min 57 s) |
| `init.sh` final | **VERDE** sobre HEAD `1ced67b` (2026-10-08): 7.132 passed, 228 skipped en 1.630,6 s (27 min), cobertura 100 % (74/74), tamaño impl 207/220, sin ningún KO |

Notas: la campaña corrió en paralelo (2 workers, `--timeout 3600` fijado a
mano porque con la máquina saturada la línea base no cabía en los 600 s por
defecto: midió 1.549,6 y 1.571,8 s). Los 20 mutantes muestreados cayeron en
`documento_procesos.py`; las líneas de `SUB_PASOS` de los dos steps (datos)
estaban en el alcance (30 de 221) y no salieron en la muestra. El modo
paralelo puede dar falsos muertos (memoria del proyecto); la reverificación
en serie solo se exige en rigor crítico.
