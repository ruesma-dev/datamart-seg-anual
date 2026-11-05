<!-- progress/impl_F-156.md -->
# F-156 · Postventa (unidades, incidencias, tareas, histórico, adjuntos y coste por obra)

Implementer, 2026-11-04. Rama `feature/F-156-postventa`, rigor `estandar`. Spec aprobada por el
humano el 2026-11-04 («si lanza»): D1=A con perfil nuevo postventa, D2 pliego aparte, D3, D4 coste
SOLO facturas, D5-D8 y D10 recomendadas, D9 `REPARACION` solo postventa y total.
Commits `4fc6da8` (T1) a `7354ea2` (T14) y `206fd57` (puerta completa). `azure-apps` `8dc4b04`,
local, sin push. **T16 (despliegue) NO ejecutada**: es del humano (§5).

## 1. Qué cambió

| Fichero | Cambio |
|---|---|
| `config/tables_sigrid.yaml`, `config/diccionario/raw.yaml` | 13 tablas nuevas (`upv`, `rcp`, `rcpint`, `tar`/`tarres` filtradas a tareas con reclamación, `obrofc`, `auxrcp`, `auxtrcp`, `auxofc`, `prmtpl`, `auxgra`, `log` recortada a los cierres de la aplicación, `per` con 5 columnas) y `rcg`/`gra` ampliadas a 707/708/47: **censo 93** |
| `etl_sigrid/domain/postventa.py` (nuevo), `domain/documento_adjuntos.py` | Constantes y oráculos (estados, garantías por clase, máscara, `familia_adjunto`, `obra_de_partida`, `liga_coste`, columnas de `per` permitidas) |
| `sql/postventa/00..08` (nuevos) | Setup y funciones, unidades y oficios, incidencias e intervinientes (guarda R12), tareas, histórico (`rac` + cierres de `raw.log`), `v_estado_incidencias`, adjuntos (guarda R21), `postventa_restringida` (3 tablas), `partida_obra_origen` + `v_coste_obra` |
| `application/steps/build_postventa_step.py` (nuevo), `main.py` | `BuildPostventaStep` (9 sub-pasos), en `run-all` tras `build_contabilidad` (16 pasos), en `PASOS_CON_PERMISOS`, comando `build-postventa` |
| `config/settings.py`, `.env.example` | `postventa` en consumo y restringido; `postventa_restringida` vetada y restringida; `PG_PERFIL_POSTVENTA_{GROUP,LOGIN,SCHEMAS}` con valores por defecto (el job no lleva variables nuevas) |
| `infrastructure/postgres/grants.py`, `apply_grants_step.py` | `perfil_postventa_en_conflicto`; `_PerfilRestringido` parametrizada por `_Rotulos` y reutilizada para el perfil postventa (guardas, veto, filtraciones, verificaciones con claves `*_postventa`), bloque tras el restringido |
| `infra/sql/02_roles.sql`, `docs/runbook_postgres_azure.md` | Grupo y login postventa, `\getenv POSTVENTA_PWD`, 18 esquemas, vetos, punto 5 sexies; runbook §14 |
| `config/diccionario/postventa.yaml`, `postventa_restringida.yaml` (nuevos), `00_global.yaml` | 18 fichas; **v71** (287 objetos, 2459 columnas, 137 de consumo); `R-POSTVENTA-RESTRINGIDA`; `R-FRESCURA` y `R-PERFILES` (cuarto perfil); `R-SIGRID-CON` con los campos nuevos |
| `etl_sigrid/domain/diccionario.py` | `ESQUEMAS_DEL_DATAMART` +2 (18) |
| `docs/ARCHITECTURE.md`, `CLAUDE.md`, `specs/F-006-mcp-azure/design_detalle.md`, `azure-apps/datamart_seg_anual.md` | Esquemas, perfil postventa, 16 pasos, 93 tablas, enlace al pliego; inventario 287 |
| `tests/` | `test_f156_{dominio,ingesta_sql,grants,pipeline,diccionario}.py` (196 tests); al día los que fijaban listas, roles, censo y pasos (f006, f024, f037, f047, f057, f066, f074, f079, f085, f090, f097, f107, f135-f141, f146-f148, f150) |

**Review pasada 1 (CHANGES_REQUESTED, 2026-11-05), corregida:** (1) vuelta atrás con el SHA de
`main` (`9dcd0aa`) y `git rev-parse main` en el paso 0; (2) `DROP OWNED BY` con el `GRANT ... TO
CURRENT_USER WITH INHERIT TRUE` delante, probado en PG16 (traza en §5) en design §12 y runbook §14;
(3) fichas de `postventa`, esquema y `R-POSTVENTA-RESTRINGIDA`: la máscara es heurística, los
nombres propios del texto libre no se quitan y seis columnas van sin máscara; fuera «sin
personas»; (4) `R-FRESCURA` «los nueve»; (5) `current.md` con la cifra real del presupuesto.
Tras ello, `bash harness/init.sh` en verde sobre `a21c786`: 10509 passed, 312 skipped (43 min 34 s),
PUERTA COBERTURA 100 % de 239 líneas.

## 2. Decisiones y desviaciones (justificadas)

- **Máscara también en `motivo` y `oficios_obra.comentario`** (la spec la pedía en descripción y
  texto): son texto libre del mismo origen; sin máscara, R11 tenía un agujero.
- **«Hoy» de `v_estado_incidencias` en hora de Madrid** (`now() AT TIME ZONE 'Europe/Madrid'`):
  el servidor está en UTC y de 00:00 a 01:00/02:00 los días saldrían con uno de menos.
- **El oficio de la tarea, del primer recurso CON oficio** (`c514fa6`): el PostgreSQL desechable
  enseñó tareas sin oficio cuando el primer `tarres` traía `obrofcide` 0.
- **CONNECT solo al grupo postventa**, no al login, como F-141 (el login no lleva permisos propios).
- **`_PerfilRestringido` parametrizada** en vez de copiada: una sola implementación de las guardas
  para los dos perfiles; los mensajes y claves del restringido no cambian (sus tests, intactos).
- **`ESQUEMAS_DEL_DATAMART` pasó de T9 a T13**: exige entrada en `esquemas` de `00_global.yaml`.
- **R34 leído como `ejemplos_preguntas` de las fichas**, no como preguntas de aceptación nuevas:
  `test_f006_reglas` fija la batería P1-P26; añadirlas era tocar otra feature.
- **`PRESUPUESTO_MAX` de F-147 subido con motivo a 34.006**, y a 34.056 en la review (pasada 1, la máscara heurística) (+2.719: regla nueva, 13 fichas de
  consumo y 2 esquemas). `R-PERFILES` recortada para seguir ≤ 1.000 caracteres (test F-147 B).
- **`R-FRESCURA` se titula «Nueve esquemas…»**; su resumen, ≤ 250.
- **Tests de otras features actualizados** (solo cifras y listas, con comentario F-156): el censo
  80→93 (f085 además admite `log` porque entra RECORTADA, D8 de F-156), 16→18 esquemas, 9 roles,
  5 contraseñas, el paso en run-all; f090/f150 por el `where` de `rcg`/`gra` con 707/708/47; el
  alcance de R24 en `test_f156_ingesta_sql` limitado a los alias de `per`.
- **`nulo_significa` movido a `significado`** en `incidencia_procesos.estado_origen_id` y
  `v_coste_obra.obra_origen_id`: son NULL por UNION/LEFT JOIN y la heurística de `test_f006_fichas`
  no lo ve; el texto lo dice igual.
- **Runbook §14** añadido (la spec solo pedía `02_roles.sql`): el alta del perfil necesita su
  procedimiento como §13 para el restringido.

## 3. Verificación real

- `bash harness/init.sh` (2026-11-04/05): **verde**. `10509 passed, 312 skipped in 15175.92s
  (4:12:55)` con medición de cobertura; `PUERTA COBERTURA: 100.0% de 239 líneas cambiadas
  cubiertas (239/239)`; `PUERTA TAMAÑO` OK. Corrido sobre `206fd57`; después solo cambian
  `progress/` y `tasks.md` (informe, mutación y marcas), sin código ni tests.
- Los 9 SQL de postventa ejecutados contra un **PostgreSQL 16 desechable local** (puerto 55432,
  datos sintéticos de `raw` con los tipos reales): todos corren; paridad SQL ↔ dominio de
  `fn_enmascarar` y `fn_obra_de_partida` en 33 casos, 0 fallos. `02_roles.sql` corrido allí con
  las 5 contraseñas por entorno: el login postventa con UNA pertenencia (`hereda t`, `set f`),
  `t` en `postventa`/`postventa_restringida`/`_meta`, `f` en `contabilidad`, `tesoreria`,
  `personal`, `raw` y las otras `*_restringida`, sin privilegios propios. Servidor parado al final.
- `publicar_diccionario` con el doble de F-024: SUCCESS, v71, 287 objetos, 2459 columnas,
  cobertura 100 %. `contexto_bbdd` medido: 34.006 (reglas 7.788, enrutado 16.982, bloques 9.236); tras la review (pasada 1), 34.056 (reglas 7.804, bloques 9.270).
- **Nada contra Azure ni Sigrid** salvo lecturas de la fase de spec. Sin push.

## 4. Fase RED (comandos y salida real)

Todas con `.venv/Scripts/python.exe -m pytest <fichero> -q -p no:cacheprovider --tb=line`,
ANTES del código de cada tarea. Trazas completas en el scratchpad de la sesión (`red_t*.txt`).

**T1 · dominio** (`tests/test_f156_dominio.py`):
```
E   ImportError: cannot import name 'postventa' from 'etl_sigrid.domain' (...\etl_sigrid\domain\__init__.py)
ERROR tests/test_f156_dominio.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
```
**T1/T2 · ingesta y SQL** (`tests/test_f156_ingesta_sql.py`):
```
E        +  where False = exists()
E        +    where exists = WindowsPath('.../sql/postventa/00_setup.sql').exists
39 failed, 2 passed in 2.08s
```
**T9 · permisos** (`tests/test_f156_grants.py`):
```
>       assert "postventa" in pg.consumption_schema_list
E       AssertionError: assert 'postventa' in ['mart', 'cierre', 'compras', 'maestro', 'retenciones', 'personal', ...]
>       assert "postventa_restringida" in pg.vetoed_schema_list
E       AssertionError: assert 'postventa_restringida' in ['contabilidad_restringida', 'tesoreria_restringida', 'compras_restringida', 'raw']
37 failed, 2 passed, 42 warnings in 2.73s
```
**T12 · pipeline** (`tests/test_f156_pipeline.py`):
```
E   AssertionError: assert 0 == 1
     +  where 0 = <built-in method count of list object ...>('build_postventa')
E   AssertionError: assert 'build_postventa' in ('build_stg', 'build_mart', 'build_maestros', ...)
5 failed, 8 passed, 52 warnings in 1.52s
```
**T13 · diccionario** (`tests/test_f156_diccionario.py`):
```
E   FileNotFoundError: [Errno 2] No such file or directory: '...\config\diccionario\postventa.yaml'
E   assert 70 == (70 + 1)
E   AssertionError: assert 'postventa_restringida' in ['contabilidad', 'contabilidad_restringida', ...]
30 failed in 0.48s
```
Después, en verde: 196 tests de F-156 `passed in 8.25s`.

## 5. Verificaciones MANUAL pendientes (T16, design §12; tras APROBADO y merge a `main`)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = consulta
de solo lectura con `pg._bootstrap_done = True` (design §12); `$dsn` del administrador.

0. Anotar el tag del job (`az containerapp job show -n caj-datamart-seg-dev -g rg-datamart-seg-dev
   --query "properties.template.containers[0].image" -o tsv`), `git rev-parse main` (el
   2026-11-05 era **`9dcd0aa`**; si `main` se mueve antes del merge, vale el nuevo) y el recuento
   de `rcg` de compras.
1. `infra/70_build_image.ps1` y `infra/85_update_job.ps1 -Tag <nuevo>`.
2. Contraseña en `kv-mcp-bbdd-dev/pg-password-postventa` → `POSTVENTA_PWD`; `psql -X -v
   ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn` (runbook §14) → «mcp_sigrid_dm_postventa:
   contraseña fijada».
3. `<PY> main.py ingest --table <t> --full` de las 13 tablas y luego `rcg` y `gra`;
   `check-raw-recuentos` sin filas de menos; recuento de compras igual al del paso 0.
4. `<PY> main.py build-postventa` → SUCCESS; `apply-grants` → las cuatro verificaciones ok.
5. Cifras: incidencias ~22.180, unidades 1.328, tareas ~13.770; adjuntos por familia
   INCIDENCIA ~10.030, REPARACION ~4.430, UNIDAD ~830, TAREA ~700.
6. `SELECT liga, round(sum(importe)) FROM postventa.v_coste_obra GROUP BY 1` (R27: ligado
   ~2,58 M€, SIN_OBRA ~0,54 M€).
7. `v_estado_incidencias` por `origen_fecha` (R17) y su tiempo (≤ ~1 s).
8. `publicar-diccionario` (v71), `check-diccionario`, `check-declarados`, `check-unicidad --timeout 300`.
9. Enviar `specs/F-156-postventa/pliego_mcp_bbdd.md` a `mcp-bbdd`; tras su despliegue, reinicio
   del MCP y pruebas por perfil.
10. Primera nocturna: `<PY> main.py timings`.

**Vuelta atrás** (design §12): job al tag del paso 0; `git switch --detach 9dcd0aa` (el SHA del
paso 0); `DROP SCHEMA postventa_restringida, postventa CASCADE` y `DROP TABLE` de las 13 de `raw`
como `sigrid_dm_etl`; como administrador `DROP ROLE IF EXISTS mcp_sigrid_dm_postventa; GRANT
sigrid_dm_perfil_postventa_ro TO CURRENT_USER WITH INHERIT TRUE; DROP OWNED BY
sigrid_dm_perfil_postventa_ro; DROP ROLE IF EXISTS sigrid_dm_perfil_postventa_ro;`; reingesta de
`rcg` y `gra`; `publicar-diccionario` y `apply-grants`.

**El `GRANT` del administrador, probado** (review pasada 1, punto 2; PostgreSQL 16 desechable,
2026-11-05, `adm_azure` = `LOGIN NOSUPERUSER CREATEROLE`, roles de prueba `pv_grupo_prueba` y
`pv_login_prueba` creados por él como `02_roles.sql`). Tras el alta, su pertenencia al grupo:
```
       rol       |     miembro     | admin_option | inherit_option | set_option
 pv_grupo_prueba | adm_azure       | t            | f              | f
```
Vuelta atrás SIN el `GRANT` (`psql -X -v ON_ERROR_STOP=1 -c "DROP ROLE IF EXISTS pv_login_prueba;
DROP OWNED BY pv_grupo_prueba; DROP ROLE IF EXISTS pv_grupo_prueba;"`):
```
ERROR:  permission denied to drop objects
DETALLE:  Only roles with privileges of role "pv_grupo_prueba" may drop objects owned by it.
exit=1      (y los dos roles siguen: el -c es una transacción)
```
CON `GRANT pv_grupo_prueba TO CURRENT_USER WITH INHERIT TRUE;` delante del `DROP OWNED BY`:
`DROP ROLE` / `GRANT ROLE` / `DROP OWNED` / `DROP ROLE`, `exit=0`, roles restantes: ninguno,
`pg_default_acl`: 0.

## 6. Fuera de alcance y lo que falta

- **`mcp-bbdd`**: lista blanca, `abrir_adjunto` con las cuatro familias y el perfil postventa
  (pliego). Hasta entonces el MCP no ve `postventa`.
- Coste de personal en `v_coste_obra` (D4: fuera; la ficha dice cómo cruzarlo con `personal`).
- Las obras `0004` de otras empresas no tienen partidas: su coste no sale.
- Para cerrar: review contra `CHECKPOINTS.md` y los pasos MANUAL de §5.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados | `bash harness/init.sh`: **10509 passed, 312 skipped**, 0 failed (F-156: 196 tests propios) |
| Cobertura de líneas cambiadas | **100.0 %** (239/239), `PUERTA COBERTURA`, umbral 80 % |
| Mutantes | `python -m harness.mutacion --feature F-156 --workers 2 --timeout 3000`: 762 líneas de producción en 8 ficheros, 20 evaluados (muestreo `estandar`, semilla 20260820): **19 muertos, 1 superviviente, 0 timeouts** (19.878 s; base 2.193-2.204 s por worker). El superviviente (`build_postventa_step.py:137`, redondeo de `duration_s` de 2 a 3 decimales) solo va al log: equivalente, analizado en `progress/mutacion_F-156.md`. El SQL no se muta: lo cubren los tests de literales contra el dominio y el PostgreSQL desechable |
| Tiempo de la suite | **15175,92 s (4 h 12 min 55 s)** con cobertura, según la propia suite |
