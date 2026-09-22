<!-- progress/impl_F-057.md -->
# F-057 · El esquema `personal` · informe de implementacion

Rama `feature/F-057-recursos-empleados-partes`, rigor `estandar`, `sdd=true`.
Se implemento la spec tal cual: **T1-T21 en 15 commits**, uno por tarea o por
hallazgo del portero; T22 (mutacion) mas abajo. **T23 y T24 son MANUAL del
humano** y no se han hecho: contra Sigrid y produccion, solo lecturas. **Nada
se ha construido en la base.** Sin `git push`.

**Ficheros tocados (28).** Nuevos: los cuatro `sql/personal/*.sql`,
`steps/build_personal_step.py`, `config/diccionario/personal.yaml` y
`tests/test_f057_personal.py`. Modificados: `main.py`, `config/settings.py`,
`.env.example`, `etl_sigrid/domain/diccionario.py`,
`config/diccionario/00_global.yaml`, `docs/ARCHITECTURE.md`, `CLAUDE.md`,
`progress/current.md`, `specs/F-006-mcp-azure/design{,_detalle}.md`, siete
suites de F-006/F-024/F-047/F-079, y `azure-apps/datamart_seg_anual.md` (commit
propio en ese repositorio).

## T1 · Fase RED (obligatoria en nivel `estandar`)

La suite se escribio ENTERA antes que el SQL, el step y el YAML. Comando exacto
y salida real con el arbol aun sin implementacion (commit `a233ff0`):

```
$ python -m pytest tests/test_f057_personal.py -q --tb=line
...
65 failed, 3 passed in 1.70s
```

Tres trazas, una por familia de test (`--tb=short`):

```
tests\test_f057_personal.py:59: in _sql
    assert ruta.exists(), f"SQL no encontrado: {ruta}"
E   AssertionError: SQL no encontrado: ...\sql\personal\01_recursos.sql

tests\test_f057_personal.py:541: in test_f057_r24_step_nombre_stage_y_dependencias
    from etl_sigrid.application.steps.build_personal_step import BuildPersonalStep
E   ModuleNotFoundError: No module named
    'etl_sigrid.application.steps.build_personal_step'

tests\test_f057_personal.py:800: in _ficha_de
    assert objeto in fichas, f"falta la ficha de personal.{objeto} (R23)"
E   AssertionError: falta la ficha de personal.partes_lineas (R23)
E   assert 'partes_lineas' in {}
```

Los 3 que ya pasaban son tareas de «verificar, no tocar» (T11, T15b, T17b): el
test ES la prueba de que no hacia falta codigo. `r3`, `r4` y `r10`
sobre-especificaban la forma y se relajaron en T3 sin debilitar el guarda.

## Lo construido, y lo que no es evidente

- `00_setup.sql` no dropea tablas (un `DROP` se llevaria los `GRANT`).
  `01_recursos.sql` no tiene `WHERE`: `activo` es BANDERA. El empleado entra
  por `LEFT JOIN LATERAL (... LIMIT 1)` con cinco columnas de `raw.emp`,
  vigiladas por **lista blanca** desde la pasada 2. `03_views.sql` toma codigo
  y nombre de obra de `raw.con`, para no depender de `maestro`.
- **Desviacion unica del diseno**: `02_partes_lineas.sql` **no lee `raw.hmo`**
  (R12/D2: la obra sale de la LINEA, `parte_id` ya esta en `hmores.hmoide`), y
  un test lo veta.

## Los doce puntos de propagacion, uno a uno — y dos mas

| # | Punto | Estado |
|---:|---|---|
| 1 | `build_personal_step.py` (`_SubStep`, `SUB_PASOS`, `build_aux`, `depends_on`) | **hecho** |
| 2 | `orchestrator.py` | **verificado, sin tocar**: generico; el test prueba el orden y que nadie lo declara en su `depends_on` |
| 3 | comando suelto `build-personal` en `main.py` | **hecho** |
| 4 | `BuildPersonalStep` en `build_pipeline_steps`, entre retenciones y cierre | **hecho** |
| 5 | docstring y recuento de `run-all`: de «cuatro build» a cinco | **hecho** |
| 6 | `DEFAULT_CONSUMPTION_SCHEMAS` + `.env.example`; `apply_grants` | **hecho** / **verificado, sin tocar** (lee `consumption_schema_list`) |
| 7 | `ESQUEMAS_DEL_DATAMART` (9 → 10) y los tres mensajes del validador | **hecho** |
| 8 | `check-declarados` sobre `sql/personal/**` | **verificado, sin tocar**: `rglob("*.sql")` ya lo recorre; `objetos_pendientes.yaml` sigue vacio |
| 9 y 10 | `clave_negocio` (`recurso_id`, `linea_id`) → `check-unicidad`, y `relaciones` (obra → `maestro.obras`, partida → `stg.partidas`, recurso → `personal.recursos`) → `check-relaciones` | **hecho** en el YAML, sin tocar el codigo de los dos comandos |
| 11 | `config/diccionario/personal.yaml` + entrada de esquema y `version` 24 → **25** | **hecho** |
| 12 | `docs/ARCHITECTURE.md`, `CLAUDE.md`, `azure-apps/datamart_seg_anual.md` | **hecho** |
| **13** | **`STEPS_POR_COMANDO` de `tests/test_f024_cli.py`** | **hecho** — no estaba en los doce |
| **14** | **`GRUPO_B_FUNCIONES` de `tests/test_f079_stg_consultable.py`** | **hecho** — tampoco estaba |

**Los puntos 13 y 14 los destapo `init.sh`, no una revision.** El 13
(`STEPS_POR_COMANDO`, que es R4 de F-024) tumbo la suite con `AttributeError:
'SimpleNamespace' object has no attribute 'postgres'`: sin el, `build-personal`
abria conexion en un test offline. El 14 inventaria lo publicado y no
recomendado. **Se quito `reset-personal`**, anadido por simetria: la spec no lo
pide, y un test exige que no exista.

**Arrastre en siete suites que enumeraban a mano** (ninguna cedio): esquemas 9
→ 10 (`test_f006_formato`; en `test_f006_comandos` y `test_f047_guardian_puerta`
el `9` literal pasa a `len(ESQUEMAS_DEL_DATAMART)`), nocturna de once pasos
(`test_f006_frescura`, `test_f047_nocturna`), `test_f006_publicacion` y los
puntos 13-14. Inventario: **158 objetos / 1015 columnas / 69 fichas de
consumo**. `R-FRESCURA` pasa a **cinco** esquemas y `R-SIGRID-CON` gana
`auxhor`, `auxrestip`, `hmores` y `res` (derivado por tests).

**Un fichero ajeno se colo en tres commits — error mio.**
`progress/explore_peticiones_juan_2026-09-18.md` es de otro agente; lo metieron
`84e0ada`, `234b986` y `8a45f06` con `git add -A`, prohibido. Desde `4d24f5c` se
anade fichero a fichero. No se reescribe el historial; lo saca el lider al
mergear.

## Pasada 2 · correcciones del review (CHANGES_REQUESTED de `review_F-057.md`)

El SQL no cambia: solo guardas, propagacion y comentarios. Commits `43cb68d`
(1-3), `43138f2` (6), `0e9b9ab` (4) y `2306301` (5).

1. **R8, lista negra → LISTA BLANCA.** De los 19 nombres «reales», 14 no
   existian en `emp`. Tres tests nuevos: `raw.emp` se lee **una vez**, en el
   lateral; el lateral selecciona **exactamente** `{ide, dni, nomnom, nomape1,
   nomape2}` como `alias.col` desnudos (sin `*`, sin expresiones, sin `AS`); y
   el `SELECT` exterior no usa otra `e.<col>`. Sustituye a los 19 parametrizados.
2. **R16:** igualdad exacta del `CASE` con `{1 HORA, 2 DIA, 3 MES, 19 UD}`, sin
   `medide` repetidos y todo `WHEN` literal. **R17:** `ELSE 'DESCONOCIDA'` unico.
3. **R21:** entre `WHERE` y `GROUP BY`, `fullmatch` de `pl.unidad = 'HORA'`, y un
   solo `WHERE` en la vista.
4. **`infra/sql/02_roles.sql`**: `personal` en los puntos 4, 5 y 6; «diez».
   Test nuevo `test_f057_r25_el_fichero_de_provision_trae_los_diez_esquemas`
   (las tres listas = `ESQUEMAS_DEL_DATAMART`), **visto en rojo** con el cambio
   retirado: `AssertionError: punto 4: crea ['_meta', 'aux', ..., 'stg'] (R25)`.
5. «diez» en `docs/runbook_postgres_azure.md` y `00_global.yaml` (cabecera y P4,
   que se publica al MCP; la version 25 aun no esta publicada, no sube).
6. Comentario del lateral: `raw` **si** tiene `PRIMARY KEY (ide)`; el
   `LIMIT 1` es defensa en profundidad. Tambien las cabeceras de `00_setup.sql`
   y `01_recursos.sql` citaban el test de la lista negra.
7. Workers de las campañas, en «Evidencias».

**Rompiendolo a mano**, mismas mutaciones que el reviewer, script en el
scratchpad que muta el SQL, lanza `pytest tests/test_f057_personal.py`, y
restaura el original. **Antes** (tests de `fe5fb9c`) y **despues**:

| Mutacion | Tests viejos | Tests nuevos (caen) |
|---|---|---|
| `WHERE ... OR pl.unidad = 'MES'` | pasa 73/73 | cae `r21_vista_solo_horas` |
| quitar WHERE / `IN ('HORA','MES')` | cae | cae `r21_vista_solo_horas` |
| anadir `WHEN 4 THEN 'HORA'` / `WHEN 5 THEN 'KM'` | pasa 73/73 | cae `r16_unidad_desde_medide` |
| anteponer `WHEN 3 THEN 'HORA'` | pasa 73/73 | cae `r16_unidad_desde_medide` |
| quitar ELSE / `ELSE 'HORA'` | cae | cae `r17_medide_desconocido_no_se_traduce` |
| `CASE h.ext` | cae | cae r16, r16b y r17 |
| lateral + `emp.tarseg`, `ban`, `bancue`, `sexo`, `telmov`, `ele`, `dir1`, `dircpo`, `esigpas`, `g3wpas`, `clamai`, `fecnac`, `estciv`, `tel` (14) | tarseg/ban: pasa 73/73 | **14 de 14** caen `r8_el_lateral_lee_exactamente_la_lista_blanca` |
| lateral `SELECT emp.*` / `emp.tarseg AS dni` | pasa 73/73 | cae `r8_el_lateral_lee_...` |
| subconsulta escalar `(SELECT x.tarseg FROM raw.emp x ...)` | — | cae `r8_raw_emp_solo_se_lee_en_el_lateral` (y `r4`) |
| fuga completa: DDL + INSERT + lateral con `tarseg`/`ban` | pasa 73/73 | caen `r8_el_lateral_...` y `r8_el_select_exterior_...` |

Salida real (extracto): `BASE: 57 passed` · `R21 OR pl.unidad = 'MES' | CAE |
1 failed, 56 passed` · `R16 anteponer WHEN 3 THEN 'HORA' | CAE | 1 failed, 56
passed` · `R8 fuga completa (DDL + INSERT + lateral) | CAE | 2 failed, 55
passed` · `REVERTIDO: 57 passed`; tests viejos: `PASA | 73 passed`.

**Pasada 3 (2026-09-22):** sin numero en prosa: `_meta.yaml` (se publica al
MCP) quita el desglose «29 filas... 9 esquemas»; `diccionario.py:401`,
`test_f006_formato.py:267/981` y, del barrido, `test_f006_punteros.py:34`
remiten a `ESQUEMAS_DEL_DATAMART`. T25 `[x]`. Sin cambio de `version` (ya 25).

## Evidencias

`bash harness/init.sh`, cierre de la pasada 3 (2026-09-22), ejecutado tal cual.
Salida real:

```
5027 passed, 189 skipped, 1402 warnings in 428.58s (0:07:08)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 94.7% de 1022 líneas cambiadas cubiertas
     (968/1022, umbral 80%, nivel estandar)
[OK] PUERTA TAMAÑO: F-057 dentro de los topes (impl 219/220, review 140/140)
[OK] Rama actual: feature/F-057-recursos-empleados-partes
ENTORNO LISTO. Puedes trabajar.        (codigo de salida 0)
```

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados | **5.027 pasan**, 189 skipped, 0 fallos (5.042 en la pasada 1: los 19 parametrizados de la lista negra pasan a 3 de lista blanca, +1 de `02_roles.sql`) |
| De ellos, de F-057 | **58** en `tests/test_f057_personal.py` (73 en la pasada 1) |
| Cobertura de lineas cambiadas | **94,7 %** (968 de 1.022), umbral 80 % |
| Tiempo de la suite | **428,58 s** (7 min 8 s) bajo medicion de cobertura (28 min el 2026-09-18; la diferencia no se ha medido) |
| Mutacion, campaña de rama (muestreo 20/349, **4 workers**) | 13 muertos, **7 supervivientes, todos de F-024/F-025**: ninguno cae en codigo de F-057 |
| Mutacion, campaña dirigida a `build_personal_step.py` (**4 workers**) | **12 generados / 12 evaluados**, 8 muertos, 4 supervivientes → **3 tras T22, los tres equivalentes** (argumentos de log) |

**T22** (`and` → `or` en el guardian de `target_schema`/`target_table`) lo mata
`test_f057_r24_un_sub_paso_a_medio_configurar_no_cuenta_filas` (`f4674f9`):
mutante → `1 failed`, original → `1 passed`. Los 11 restantes, analizados en
**`progress/mutacion_F-057.md`**.

Las dos campañas, con **4 workers**, en un `git worktree` limpio desde
`f6547dd` con el `.env` principal exportado. **Para el lider**: el suelo
`timeout_por_mutante_s` ya no cabe en la suite; se uso `--timeout 2400` sin
tocar configuracion (decision del arnes, propagable a `arnes-base`).

## Verificaciones MANUAL pendientes (no las hace un agente)

**F-057 no pasa a `done` con esto.** Todo lo de arriba es texto y tests
offline: **nadie ha construido nada en la base**, y construir es la unica forma
de comprobar que este SQL se ejecuta. Lo lanza el humano, en este orden:

```
python main.py build-personal        # T23 - construye el esquema y su vista
python main.py check-declarados      # los 4 objetos declarados, construidos
python main.py check-unicidad        # recurso_id y linea_id, sin duplicados
python main.py check-relaciones      # obra, partida y recurso enganchan
python main.py publicar-diccionario  # T24 - sube la version 25 a _meta
python main.py apply-grants          # el esquema nuevo, al rol del MCP
```

**Las cifras que tienen que salir** (medidas contra Sigrid el 2026-09-18, y que
esta implementacion NO ha comprobado contra el Postgres construido):

- `personal.recursos`: **2.618** filas, **1.354** con `clase = 'PERSONA'`, de
  ellas **1.034** con `activo = false`; **824** con `empleado_id` informado.
- `personal.partes_lineas`: **330.638** filas; `SUM(importe)` =
  **98.275.191,12** EUR; **318.892** con `en_seguimiento = true` sobre **523**
  obras; **302.575** con `partida_id`.
- `SUM(cantidad) WHERE unidad = 'HORA'` = **1.249.038,44**, y `SUM(cantidad)`
  sin filtrar = **1.837.201,23**. Si las dos coinciden, el `CASE` de la unidad
  no esta funcionando.
- `unidad = 'DESCONOCIDA'` tiene que salir en **10** lineas exactas. Mas de 10
  significa que Sigrid ha estrenado una unidad de medida y que hay que ampliar
  el `CASE` antes de fiarse de ninguna suma.

**Prueba de verdad por el MCP**: «horas de la obra 0695 en 2026 por oficio»;
oficial 1a albanil = **7.366,00 h** y **170.470,10 EUR**. Un `SUM(cantidad)`
sin filtrar unidad significa que la ficha ha fallado.
