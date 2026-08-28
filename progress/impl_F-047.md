<!-- progress/impl_F-047.md -->
# F-047 · Implementación (absorbe F-044)

**Rama** `feature/F-047-nocturna-desfasada` · 5 commits · rigor `critico`
**`bash harness/init.sh` en VERDE**: 2.569 tests, 128 saltados, 375 s;
cobertura **100 % de 259 líneas cambiadas**; puerta de tamaño cumplida.

## Qué cambió, en una frase

La nocturna construía `raw → stg → mart` y **destruía** cada noche
`cierre.v_pbi_planif_vs_real` sin recrearla. Ahora construye el datamart entero
en diez pasos, `build_cierre` va después de `build_mart` **por `depends_on`**, y
al terminar contrasta lo que el repositorio declara contra la base.

## Ficheros tocados

| Fichero | Qué |
|---|---|
| `main.py` | los cuatro build en `build_pipeline_steps`; `build-compras` y `build-retenciones` pasan a ser wrappers de step; comando `check-declarados`; el guardián al final de `run-all` |
| `steps/build_compras_step.py`, `steps/build_retenciones_step.py` | **nuevos**: su SQL se ejecutaba en línea, sin step |
| `steps/build_cierre_step.py` | `depends_on = [build_stg, build_mart]` |
| `steps/publicar_diccionario_step.py` | usa el inventario compartido |
| `infrastructure/inventario_repositorio.py` | **nuevo**: la lectura de `sql/**` estaba copiada 2 veces y hacía falta una 3ª |
| `infrastructure/postgres/catalogo.py` | `evaluar_construccion` + `formatear_construccion`; corregida una causa falsa del docstring |
| `config/objetos_pendientes.yaml` | **nuevo**: el trinquete del guardián, hoy vacío |
| `config/diccionario/*.yaml` | 40 fichas a `refresco: nocturno`; los 4 esquemas del global; `R-FRESCURA-MANUAL` → `R-FRESCURA`; versión 9 → 10 |
| `domain/diccionario.py` | el código de la regla en `CODIGOS_REGLAS_OBLIGATORIAS` |
| `docs/ARCHITECTURE.md`, `CLAUDE.md`, `azure-apps/datamart_seg_anual.md` | la nocturna de hoy, el coste medido y el guardián |
| tests | 4 ficheros nuevos (`test_f047_*`, 69 tests) y 7 actualizados |

## Decisiones de diseño, y por qué

1. **`BuildCierreStep.depends_on = ["build_stg", "build_mart"]`.** La segunda no
   es dependencia de datos, es **dependencia de destrucción**: `mart` dropea con
   `CASCADE` la tabla de la que cuelga la vista de `cierre`. Declararlo en el
   DAG y no en el orden de la lista es lo que hace que el orden lo garantice el
   orden topológico. Un comentario se borra sin que nadie se entere; hay un test
   que compone el pipeline **al revés** y comprueba que el orden aguanta.
2. **`apply_grants` NO depende de los cuatro build, a propósito.** Sería lo
   «ordenado» —los cuatro recrean vistas con `DROP` + `CREATE` y un `DROP` se
   lleva los `GRANT`—, pero convertiría un fallo de `build_cierre` en
   `apply_grants` SKIPPED, y eso deja al MCP y a Power BI sin permisos sobre las
   vistas de `mart` que sí se recrearon. Se resuelve con la posición en la lista
   más un test sobre el orden topológico real. **El precio, declarado**: un
   esquema puede quedarse atrás sin tumbar la noche, y de ahí la regla nueva.
3. **Los tres que solo leen de `raw` van después de `build_mart`, no antes.**
   Da igual para el reloj (el pipeline es secuencial) y deja intacto el prefijo
   probado de la nocturna. *Alternativa considerada*: tras `ingest_raw`
   salvaría sus 9,7 min si `build_stg` (110 min) muere; cambia más de lo que
   arregla y esa decisión es del humano.
4. **El guardián NO es un step.** Es una lectura, no una construcción; meterlo
   en el DAG lo haría dependencia de `apply_grants` o al revés. Corre después
   de todo, en `run-all`, y un fallo **leyendo** el catálogo cuenta como
   veredicto negativo: tragárselo dejaría exactamente el agujero que cierra.
5. **El trinquete es el patrón que ya usa el diccionario**, no uno nuevo:
   objeto construido **o** pendiente declarado, lista versionada, y sólo baja
   (un pendiente ya construido, o uno que el repositorio no declara, rompen la
   puerta). Hoy la lista está **vacía** y eso es un dato: los diez pasos
   construyen los 103 objetos declarados.
6. **`R-FRESCURA-MANUAL` se renombra a `R-FRESCURA`.** Es una regla
   **bloqueante** que el MCP sirve a los agentes y decía «el pipeline nocturno
   construye SOLO raw, stg y mart». Dejarla habría sido crear una mentira nueva
   del mismo tipo que F-047 vino a matar. Lo que la regla dice ahora es el
   peligro que SÍ queda (decisión 2): el paso de esos cuatro no es dependencia
   de nadie, puede fallar sin tumbar la noche, y hay que citar la frescura **del
   paso**, no la del pipeline.
7. **Los dos steps nuevos copian el patrón de `BuildCierreStep`/
   `BuildMaestrosStep`** en vez de factorizar el bucle común: es lo que pedía el
   encargo («sigue ese patrón, sin inventar uno nuevo»). Coste: ~40 líneas
   duplicadas ×2; unificarlas son los cuatro a la vez y es otra tarea.

## Los tests que cambiaron de veredicto, uno a uno

Ninguno se tocó para que pasara. En todos, **el veredicto lo dicta la
composición real**: `_validar_frescura` compara contra
`main.build_pipeline_steps`, así que meter los cuatro build invierte R14 solo.
Eso era el diseño de F-006 —«el día que `build-cierre` entre, el veredicto
cambia solo»— funcionando.

- `test_f006_frescura.py` (5 tests) — la composición esperada pasa de 6 pasos a
  10, y la mentira que vigila cambia de sentido. La dirección «me declaro
  nocturno sin serlo» **sigue vigilada**, ahora con un paso inventado
  (`build_cierre_a_mano`), porque ya no hay ningún esquema real desfasado con el
  que ilustrarla. Si se hubiera borrado, el fichero se quedaba sin guardián.
- `test_f006_fichas.py::..._cierre_entero_se_declara_de_refresco_manual` — decía
  literalmente «`cierre` no está en `build_pipeline_steps`». Dejarlo en `manual`
  pondría en rojo la validación del diccionario entero.
- `test_f006_fichas.py::..._una_ficha_cuyo_paso_no_deja_rastro_lo_advierte` —
  **el que más merece mirarse.** Exigía que las 24 fichas de `compras` y
  `retenciones` ADVIRTIERAN de que su fecha de build no era consultable. El
  agujero ya no existe: se invierte a exigir que **ningún `paso_etl` declarado
  quede fuera de los pasos registrables**. Es un contrato más fuerte, y si
  alguien vuelve a meter SQL en línea sin step, se pone rojo.
- `test_f006_formato.py::..._los_cuatro_esquemas_manuales_lo_declaran_en_el_global`
  — pasa a comprobar el régimen de los ocho nocturnos **y** que `aux` sigue
  siendo el único `estatico`; sin eso el test degeneraría en «todo es nocturno».
- `test_f006_publicacion.py` (2) — la lista de pasos y `"build_cierre" in
  pasos_nocturnos` en vez de `not in`.
- `test_f024_cli.py` (3) — `build-compras` y `build-retenciones` entran en
  `STEPS_POR_COMANDO`, y con ellos en la parametrización de R18 («cada comando
  suelto registra su paso»), que es el criterio de aceptación de F-044. Y el
  `== 6` cableado del recuento de filas de `run-all` se ancla a
  `len(build_pipeline_steps(...))`: era exactamente el número escrito a mano que
  este repositorio persigue.
- `test_f006_unicidad.py` — el barrido de código muerto dio por muertas
  `objetos_de_sql`/`objetos_de_raw` en cuanto su lectura se movió al módulo
  nuevo. Se añade el nuevo consumidor a la lista. **El barrido hizo su trabajo.**
- **`test_f005_grants.py:256` NO se tocó**: fija que `apply_grants` va tras
  `build_mart`, que `depends_on == ["build_mart"]` y que es el último del orden.
  Los tres siguen siendo ciertos y son la decisión 2. Ese contrato se arregló
  no cambiándolo.

## Fase RED

**Alcance A** — `tests/test_f047_nocturna.py` escrito antes que el código,
13 fallos. La traza del test que reproduce la causa raíz:

```
$ python -m pytest tests/test_f047_nocturna.py::test_f047_r2_build_cierre_corre_despues_de_build_mart -p no:cacheprovider --no-header -q
        orden = _orden()

>       assert orden.index("build_cierre") > orden.index("build_mart")
E       ValueError: 'build_cierre' is not in list

tests\test_f047_nocturna.py:102: ValueError
1 failed in 1.35s
```

**Alcance B** — `tests/test_f047_guardian.py` escrito antes que
`evaluar_construccion`:

```
$ python -m pytest tests/test_f047_guardian.py -p no:cacheprovider --no-header -q
tests\test_f047_guardian.py:31: in <module>
    from etl_sigrid.infrastructure.postgres.catalogo import (
E   ImportError: cannot import name 'EvaluacionConstruccion' from
    'etl_sigrid.infrastructure.postgres.catalogo'
1 error in 0.28s
```

**El guardián dentro de `run-all`**, con los dobles de F-024 que aún no sabían
responder al catálogo — muestra además que un fallo leyendo NO se traga:

```
E         [SUCCESS] apply_grants              rows=        7 duration=1800.0s
E         KO   no se pudo comprobar lo declarado contra la base:
E              'PgFalso' object has no attribute 'list_objetos_catalogo'
E       assert 1 == 0
```

## Lo que los cuatro build añaden a la nocturna

Medición del humano del **2026-08-21** (a mano, con el disco vigilado):
maestros **0,2** min, compras **8,9**, retenciones **0,6**, cierre **27,8**.
**Total +37,5 min**, de 2 h 46 a unas **3 h 24**; arrancando a las 02:00 UTC, el
final se mueve de 04:46 a ~**05:24 UTC**.

**El orden que he elegido NO cambia esa cuenta.** El orquestador es secuencial
por diseño (`orchestrator.py`), así que el total es la suma pase lo que pase; el
orden solo decide *cuándo* termina cada uno y qué se salta si algo falla. Dos
matices que sí cambian, y ninguno afecta al reloj:

- si `build_mart` falla, `build_cierre` queda **SKIPPED** (antes ni se lanzaba),
  así que esos 27,8 min no se gastan;
- el guardián añade **una consulta a `information_schema`** al final: coste
  despreciable frente a 3 h 24, y no toca `raw`, `stg` ni `mart`.

**El disco no se mueve**: 57,92 % → 57,93 % sobre un límite del 80 % en la
medición del 21. Estos cuatro reconstruyen desde `raw`/`stg` y no acumulan como
`plan_mensual`, que es lo que llenó el disco en F-019.

## Verificaciones MANUAL pendientes (ninguna se pudo hacer aquí)

El puesto **no tiene conexión** a `psql-albaranes-rs9k2` (puerto 5432 cerrado
desde esta IP) y las escrituras contra producción las autoriza el humano una a
una. Queda, todo **lectura** salvo el punto 4:

1. `python main.py check-declarados` contra Azure: cuántos de los 103 declarados
   faltan de verdad hoy.
2. `python main.py check-diccionario`: que la huérfana siga siendo esa y solo esa.
3. `pg_depend`: que no haya otros dependientes de
   `mart.fact_seguimiento_categoria` creados fuera del repositorio.
4. **ESCRITURA, la autoriza el humano**: `publicar-diccionario` para servir la
   versión 10. Hasta entonces `_meta` sigue diciendo que esos cuatro esquemas
   son de refresco manual, y ya no lo son.
5. **Decisión del humano, no del agente**: si 3 h 24 acabando a las ~05:24 UTC
   es aceptable o conviene adelantar el arranque. Enlaza con F-035 y F-025.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados | **2.569 pasados**, 128 saltados, 0 fallos (`bash harness/init.sh`) |
| Suite, tiempo | **375 s** con medición de cobertura; **153 s** sin ella |
| Cobertura de líneas cambiadas | **100 % (259/259)**, umbral 80 %, nivel `critico` |
| Tests nuevos | 69 en 4 ficheros `test_f047_*` |
| `ruff` | 238 avisos frente a 237 de la línea base: **+1**, un `noqa: E402` inerte igual que los 27 que main.py ya tenía. Deuda previa, no bloquea |
| Mutación | PENDIENTE |

**Cómo se midió.** Campaña **EN SERIE** (`--workers 1`, `--max-mutantes 0`),
no en paralelo: con 70 mutantes salía a cuenta y así **no aplica** la regla de
reverificación de F-041 —la campaña paralela produce falsos muertos, y un falso
muerto esconde un superviviente real—. Detalle en `progress/mutacion_F-047.md`.

**Aviso sobre el alcance**: el diff se calcula contra `dev` y la rama nace de
`feature/F-006-mcp-azure`, así que arrastra **16 mutantes de
`harness/mutacion_paralela.py`**, trabajo de F-006 que ya tuvo su campaña. Se
analizan igual, pero conviene saberlo al leer los números.

**F-044 queda absorbida**: sus cinco criterios de aceptación están cubiertos
salvo los dos que exigen medir contra la base (tiempo real de la nocturna
completa y pico de disco), que son las verificaciones MANUAL 1 y 5. Cerrarla es
del líder, no mío.
