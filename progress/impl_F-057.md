<!-- progress/impl_F-057.md -->
# F-057 · El esquema `personal` · informe de implementacion

Rama `feature/F-057-recursos-empleados-partes`, rigor `estandar`, `sdd=true`.
Se implemento la spec tal cual: **T1-T21 en 15 commits**, uno por tarea o por
hallazgo del portero; T22 (mutacion) mas abajo. **T23 y T24 son MANUAL del
humano** y no se han hecho: contra Sigrid y produccion, solo lecturas. **Nada
se ha construido en la base.** Sin `git push`.

**Ficheros tocados (28).** Nuevos: cuatro `sql/personal/*.sql`,
`build_personal_step.py`, `personal.yaml`, `test_f057_personal.py`. Tocados:
`main.py`, `settings.py`, `.env.example`, `diccionario.py`, `00_global.yaml`,
`ARCHITECTURE.md`, `CLAUDE.md`, `current.md`, `specs/F-006-mcp-azure/design
{,_detalle}.md`, siete suites de F-006/F-024/F-047/F-079 y `azure-apps/
datamart_seg_anual.md` (commit propio en ese repositorio).

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

Los 3 que ya pasaban son de «verificar, no tocar» (T11, T15b, T17b). `r3`, `r4`
y `r10` sobre-especificaban la forma y se relajaron en T3 sin debilitar el guarda.

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

Hechos: **1** `build_personal_step.py`; **3** `build-personal` en `main.py`;
**4** el step en `build_pipeline_steps`, entre retenciones y cierre; **5**
`run-all` de cuatro build a cinco; **6** `DEFAULT_CONSUMPTION_SCHEMAS` +
`.env.example`; **7** `ESQUEMAS_DEL_DATAMART` 9 → 10 y los tres mensajes del
validador; **9-10** `clave_negocio` y `relaciones` en el YAML; **11**
`personal.yaml` + `version` 24 → 25; **12** `ARCHITECTURE.md`, `CLAUDE.md`,
`azure-apps`. **Verificados sin tocar** (lo prueba un test): **2**
`orchestrator.py`, `apply_grants` (lee `consumption_schema_list`) y **8**
`check-declarados` (`rglob`). **Fuera de los doce**: **13** `STEPS_POR_COMANDO`
de `test_f024_cli.py` y **14** `GRUPO_B_FUNCIONES` de `test_f079`.

**13 y 14 los destapo `init.sh`**: el 13 tumbo la suite con `AttributeError:
'SimpleNamespace' object has no attribute 'postgres'` (`build-personal` abria
conexion offline). **Se quito `reset-personal`**: la spec no lo pide y un test
veta que exista. **Arrastre en siete suites** (ninguna cedio): esquemas 9 → 10
(`test_f006_formato`; `len(ESQUEMAS_DEL_DATAMART)` en `test_f006_comandos` y
`test_f047_guardian_puerta`), nocturna de once pasos (`test_f006_frescura`,
`test_f047_nocturna`), `test_f006_publicacion` y 13-14. Inventario: **158
objetos / 1015 columnas / 69 fichas de consumo**; `R-FRESCURA` a cinco esquemas
y `R-SIGRID-CON` gana `auxhor`, `auxrestip`, `hmores` y `res`.

**Un fichero ajeno se colo en tres commits — error mio.**
`progress/explore_peticiones_juan_2026-09-18.md` es de otro agente; lo metieron
`84e0ada`, `234b986` y `8a45f06` con `git add -A`, prohibido. Desde `4d24f5c` se
anade fichero a fichero. No se reescribe el historial; lo saca el lider al
mergear.

## Pasada 2 · correcciones del review (CHANGES_REQUESTED de `review_F-057.md`)

El SQL no cambia: guardas, propagacion y comentarios (`43cb68d` 1-3,
`43138f2` 6, `0e9b9ab` 4, `2306301` 5). **1 · R8 lista negra → LISTA BLANCA**
(14 de sus 19 nombres no existian en `emp`): `raw.emp` se lee una vez, en el
lateral, que selecciona exactamente `{ide, dni, nomnom, nomape1, nomape2}` como
`alias.col` desnudos, y el `SELECT` exterior no usa otra `e.<col>`. **2 · R16**
igualdad exacta del `CASE` con `{1 HORA, 2 DIA, 3 MES, 19 UD}`; **R17** `ELSE
'DESCONOCIDA'` unico. **3 · R21** `fullmatch` de `pl.unidad = 'HORA'` y un solo
`WHERE`. **4 · `infra/sql/02_roles.sql`** con `personal` en los puntos 4-6 y
test `r25` **visto en rojo** con el cambio retirado: `AssertionError: punto 4:
crea ['_meta', 'aux', ..., 'stg'] (R25)`. **5** «diez» en el runbook y
`00_global.yaml`. **6** comentario del lateral (`raw` si tiene PK; `LIMIT 1` es
defensa en profundidad). **7** workers, en «Evidencias».

**Rompiendolo a mano** (script en el scratchpad: muta el SQL, lanza
`pytest tests/test_f057_personal.py`, restaura). Tests viejos (`fe5fb9c`) →
nuevos:

| Mutacion | Viejos | Nuevos (caen) |
|---|---|---|
| `WHERE ... OR pl.unidad = 'MES'` | pasa 73/73 | `r21_vista_solo_horas` |
| quitar WHERE / `IN ('HORA','MES')` | cae | `r21_vista_solo_horas` |
| `WHEN 4 THEN 'HORA'`, `WHEN 5 THEN 'KM'`, anteponer `WHEN 3 THEN 'HORA'` | pasa 73/73 | `r16_unidad_desde_medide` |
| quitar ELSE / `ELSE 'HORA'` · `CASE h.ext` | cae | r17 · r16, r16b y r17 |
| lateral + 14 columnas de `emp` (`tarseg`, `ban`, `bancue`, `sexo`, `telmov`, `ele`, `dir1`, `dircpo`, `esigpas`, `g3wpas`, `clamai`, `fecnac`, `estciv`, `tel`) | tarseg/ban: pasa | **14 de 14** caen `r8_el_lateral_lee_exactamente_la_lista_blanca` |
| `SELECT emp.*` / `emp.tarseg AS dni` · subconsulta escalar sobre `raw.emp` | pasa 73/73 · — | `r8_el_lateral_...` · `r8_raw_emp_solo_se_lee_en_el_lateral` (y `r4`) |
| fuga completa: DDL + INSERT + lateral con `tarseg`/`ban` | pasa 73/73 | `r8_el_lateral_...` y `r8_el_select_exterior_...` |

Salida real (extracto): `BASE: 57 passed` · `R21 OR ... 'MES' | CAE | 1 failed,
56 passed` · `R8 fuga completa | CAE | 2 failed, 55 passed` · `REVERTIDO: 57
passed`; tests viejos: `PASA | 73 passed`.

**Pasada 3:** sin numero en prosa en `_meta.yaml` (quita «29 filas... 9
esquemas»), `diccionario.py:401`, `test_f006_formato.py:267/981` y
`test_f006_punteros.py:34`: remiten a `ESQUEMAS_DEL_DATAMART`. T25 `[x]`.

## Pasada 4 · los dos «nueve» sin «esquemas» pegado (2026-09-22)

`00_global.yaml:881` → «Son los de `ESQUEMAS_DEL_DATAMART` (eran nueve hasta
F-057)...»; `ARCHITECTURE.md:510` → «—los de `ESQUEMAS_DEL_DATAMART`—». No se
publican: `version` no sube. **Barrido por el numero solo**, despues del cambio:

```
git grep -n -i -E "\bnueve\b" -- . ':!specs/F-005*' ':!specs/F-006*' ':!progress/*'
git grep -n -i -E "\b9\b" -- config/diccionario docs etl_sigrid tests infra
```

**«nueve», 53 aciertos, ninguno afirma hoy nueve esquemas.** *Historicos
explicitos:* `00_global.yaml:881` (el nuevo), `diccionario.py:38`,
`test_f006_formato.py:272` («Eran NUEVE... DIEZ desde F-057»),
`test_f057_personal.py:999/1023` (guarda que veta «nueve» en `02_roles.sql`),
`features.json:517`/`BACKLOG.md:592` (lo verificado en F-006 el 2026-08-27).
*Otra cosa:* tablas de F-074 (`tables_sigrid.yaml:1146/1148/1152`,
`ARCHITECTURE.md:130/151`, `test_f074_*`, `test_f066:41`, `features.json`
1167/1169/1177, `BACKLOG.md:526`); «multiplicaba por nueve» (`00_global.yaml`
346/1172, `mart.yaml:176`, `test_f006_reglas.py:8/817`, `test_f006_formato:627`);
supervivientes (`test_f006_constantes:5`, `BACKLOG.md:544`, `features.json:1300`);
bases del servidor (`postgres_client.py:156`); obras (`huella.py:209`,
`arbol_partidas.py:163`); columnas (`test_f042_huella:298`, `test_f006_fichas`
1642/2421); simbolos de regex (`test_f003_infra` 320/381/416, `BACKLOG.md:244`,
`features.json:740`); F-085 (`BACKLOG.md:160`, `features.json:1379/1381`); `lpt`
(`test_f006_constantes:266`); objetos de F-079 (`test_f079:85`); minutos, SQL,
descartes y tablas en `specs/F-025`, `F-052`, `F-066`.

**«9», 258 aciertos en 82 ficheros, ninguno cuenta esquemas** (filtrados ademas
por `esquema|schema|len(|== 9`: cero sobre esquemas). Son: decimales y miles
(`38,9 M€`, `31,9 %`, `9.723`, `1e-9`), «9 obras» con huecos o duplicados
(`mart.yaml`, `stg.yaml`, `cierres*.py`, `huella.py`, `test_f006_stg_trampas`),
codigos (`CP.9`, estado 9 de `con`, clase 9, `medide`, `DA-9`, `ELSE 9`),
regex `[0-9]`, indices `fila[9]`/`f[9]`, anchos de formato `:<9`, pasos 9 de
`infra/README.md` y del runbook, septiembre en fechas y `mes_int := 9`, «9
objetos rotos» de F-079, «9 meses» de F-025 e ids de fixtures.

## Evidencias

`bash harness/init.sh`, cierre de la pasada 4 (2026-09-22), ejecutado tal cual.
Salida real:

```
5027 passed, 189 skipped, 1402 warnings in 429.98s (0:07:09)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 94.7% de 1022 líneas cambiadas cubiertas
     (968/1022, umbral 80%, nivel estandar)
[OK] PUERTA TAMAÑO: F-057 dentro de los topes (impl 219/220, review 139/140)
[OK] Rama actual: feature/F-057-recursos-empleados-partes
ENTORNO LISTO. Puedes trabajar.        (codigo de salida 0)
```

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados | **5.027 pasan**, 189 skipped, 0 fallos (5.042 en la pasada 1: los 19 parametrizados de la lista negra pasan a 3 de lista blanca, +1 de `02_roles.sql`) |
| De ellos, de F-057 | **58** en `tests/test_f057_personal.py` (73 en la pasada 1) |
| Cobertura de lineas cambiadas | **94,7 %** (968 de 1.022), umbral 80 % |
| Tiempo de la suite | **429,98 s** (7 min 9 s) bajo medicion de cobertura (28 min el 2026-09-18; la diferencia no se ha medido) |
| Mutacion, campaña de rama (muestreo 20/349, **4 workers**) | 13 muertos, **7 supervivientes, todos de F-024/F-025**: ninguno cae en codigo de F-057 |
| Mutacion, campaña dirigida a `build_personal_step.py` (**4 workers**) | **12 generados / 12 evaluados**, 8 muertos, 4 supervivientes → **3 tras T22, los tres equivalentes** (argumentos de log) |

**T22** (`and` → `or` en el guardian de `target_schema`/`target_table`) lo mata
`test_f057_r24_un_sub_paso_a_medio_configurar_no_cuenta_filas` (`f4674f9`):
mutante `1 failed`, original `1 passed`; los 11 restantes, en
**`progress/mutacion_F-057.md`**. Campañas en un `git worktree` limpio desde
`f6547dd`. **Para el lider**: el suelo `timeout_por_mutante_s` ya no cabe en la
suite; se uso `--timeout 2400` sin tocar configuracion (propagable a `arnes-base`).

## Verificaciones MANUAL pendientes (no las hace un agente)

**F-057 no pasa a `done` con esto**: nadie ha construido nada en la base. Lo
lanza el humano, en este orden:

```
python main.py build-personal        # T23 - construye el esquema y su vista
python main.py check-declarados      # los 4 objetos declarados, construidos
python main.py check-unicidad        # recurso_id y linea_id, sin duplicados
python main.py check-relaciones      # obra, partida y recurso enganchan
python main.py publicar-diccionario  # T24 - sube la version 25 a _meta
python main.py apply-grants          # el esquema nuevo, al rol del MCP
```

**Las cifras que tienen que salir** (medidas contra Sigrid el 2026-09-18, NO
comprobadas contra el Postgres construido): `personal.recursos` **2.618** filas,
**1.354** `PERSONA`, de ellas **1.034** `activo = false`, **824** con
`empleado_id`. `personal.partes_lineas` **330.638** filas, `SUM(importe)`
**98.275.191,12** EUR, **318.892** en seguimiento sobre **523** obras,
**302.575** con `partida_id`. `SUM(cantidad)` con `unidad = 'HORA'`
**1.249.038,44** y sin filtrar **1.837.201,23** (si coinciden, el `CASE` falla).
`DESCONOCIDA` en **10** lineas exactas: mas, y Sigrid estreno unidad.

**Prueba de verdad por el MCP**: «horas de la obra 0695 en 2026 por oficio»;
oficial 1a albanil = **7.366,00 h** y **170.470,10 EUR**. Un `SUM(cantidad)`
sin filtrar unidad significa que la ficha ha fallado.
