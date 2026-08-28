<!-- progress/impl_F-047.md -->
# F-047 · Implementación (absorbe F-044)

**Rama** `feature/F-047-nocturna-desfasada` · 5 commits · rigor `critico`
**`bash harness/init.sh` en VERDE**: 2.581 tests, 128 saltados, 387 s;
cobertura **100 % de 259 líneas cambiadas**; puerta de tamaño cumplida.

## Qué cambió, en una frase

La nocturna construía `raw → stg → mart` y **destruía** cada noche
`cierre.v_pbi_planif_vs_real` sin recrearla. Ahora construye el datamart entero
en diez pasos, `build_cierre` va después de `build_mart` **por `depends_on`**, y
al terminar contrasta lo que el repositorio declara contra la base.

## Ficheros tocados (33 en total, `git diff --stat aea1307..HEAD`)

- **Nuevos**: `steps/build_compras_step.py` y `steps/build_retenciones_step.py`
  (su SQL se ejecutaba en línea, sin step); `infrastructure/inventario_repositorio.py`
  (la lectura de `sql/**` estaba copiada 2 veces y hacía falta una 3ª);
  `config/objetos_pendientes.yaml` (el trinquete del guardián, hoy vacío);
  4 ficheros de test `test_f047_*`.
- **`main.py`**: los cuatro build en `build_pipeline_steps`; `build-compras` y
  `build-retenciones` pasan a wrappers de step; `check-declarados`; el guardián
  al final de `run-all`.
- **`steps/build_cierre_step.py`**: `depends_on = [build_stg, build_mart]`.
  **`catalogo.py`**: `evaluar_construccion` + `formatear_construccion`, y una
  causa falsa que su docstring daba por buena, corregida.
- **`config/diccionario/*.yaml`**: 40 fichas a `refresco: nocturno`, los cuatro
  esquemas del global, `R-FRESCURA-MANUAL` → `R-FRESCURA`, versión 9 → 10.
- **Docs**: `ARCHITECTURE.md`, `CLAUDE.md` y `azure-apps/datamart_seg_anual.md`
  (commit propio allí). **Tests**: 9 ficheros actualizados, 2 de ellos del arnés.

## Decisiones de diseño, y por qué

1. **`BuildCierreStep.depends_on = ["build_stg", "build_mart"]`.** La segunda no
   es dependencia de datos, es **dependencia de destrucción**: `mart` dropea con
   `CASCADE` la tabla de la que cuelga la vista de `cierre`. Declararlo en el DAG
   y no en el orden de la lista hace que lo garantice el orden topológico —un
   comentario se borra sin que nadie se entere—; hay un test que compone el
   pipeline **al revés** y comprueba que el orden aguanta.
2. **`apply_grants` NO depende de los cuatro build, a propósito.** Sería lo
   «ordenado» —los cuatro recrean vistas con `DROP` + `CREATE` y un `DROP` se
   lleva los `GRANT`—, pero convertiría un fallo de `build_cierre` en
   `apply_grants` SKIPPED, y eso deja al MCP y a Power BI sin permisos sobre las
   vistas de `mart` que sí se recrearon. Se resuelve con la posición en la lista
   más un test sobre el orden topológico real. **El precio, declarado**: un
   esquema puede quedarse atrás sin tumbar la noche, y de ahí la regla nueva.
3. **Los tres que solo leen de `raw` van después de `build_mart`, no antes.**
   Da igual para el reloj (el pipeline es secuencial) y deja intacto el prefijo
   probado. *Alternativa*: tras `ingest_raw` salvaría sus 9,7 min si `build_stg`
   muere; cambia más de lo que arregla y esa decisión es del humano.
4. **El guardián NO es un step.** Es una lectura, no una construcción; en el
   DAG sería dependencia de `apply_grants` o al revés. Corre después de todo, y
   un fallo **leyendo** el catálogo cuenta como veredicto negativo: tragárselo
   dejaría el agujero que viene a cerrar.
5. **El trinquete es el patrón que ya usa el diccionario**, no uno nuevo: objeto
   construido **o** pendiente declarado, lista versionada, y sólo baja (un
   pendiente ya construido, o uno que el repositorio no declara, rompen la
   puerta). Hoy está **vacía**, y es un dato: los diez pasos construyen los 103.
6. **`R-FRESCURA-MANUAL` se renombra a `R-FRESCURA`.** Es una regla
   **bloqueante** que el MCP sirve a los agentes y decía «el pipeline nocturno
   construye SOLO raw, stg y mart». Dejarla era crear una mentira nueva del tipo
   que F-047 vino a matar. Ahora fija el peligro que SÍ queda (decisión 2): hay
   que citar la frescura **del paso**, no la del pipeline.
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

- `test_f006_frescura.py` (5) — la composición esperada pasa de 6 pasos a 10 y
  la mentira que vigila cambia de sentido. La dirección «me declaro nocturno sin
  serlo» **sigue vigilada**, con un paso inventado (`build_cierre_a_mano`),
  porque ya no hay esquema real desfasado con el que ilustrarla: borrarla dejaba
  el fichero sin guardián.
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
- `test_f006_publicacion.py` (2) — la lista de pasos, y `"build_cierre" in
  pasos_nocturnos` en vez de `not in`.
- `test_f024_cli.py` (3) — `build-compras` y `build-retenciones` entran en
  `STEPS_POR_COMANDO` y con ellos en la parametrización de R18 («cada comando
  suelto registra su paso»), criterio de aceptación de F-044. Y el `== 6`
  cableado del recuento de filas de `run-all` se ancla a
  `len(build_pipeline_steps(...))`.
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
por diseño (`orchestrator.py`): el total es la suma pase lo que pase, y el orden
solo decide *cuándo* termina cada uno y qué se salta si algo falla. Dos matices
que sí cambian, y ninguno afecta al reloj: si `build_mart` falla,
`build_cierre` queda **SKIPPED** (antes ni se lanzaba) y esos 27,8 min no se
gastan; y el guardián añade **una consulta a `information_schema`** al final,
despreciable frente a 3 h 24 y sin tocar `raw`, `stg` ni `mart`.

**El disco no se mueve**: 57,92 % → 57,93 % sobre un límite del 80 % en la
medición del 21. Estos cuatro reconstruyen desde `raw`/`stg` y no acumulan como
`plan_mensual`, que es lo que llenó el disco en F-019.

## Verificaciones MANUAL pendientes (ninguna se pudo hacer aquí)

El puesto **no tiene conexión** a `psql-albaranes-rs9k2` (puerto 5432 cerrado
desde esta IP). Queda, todo **lectura** salvo el punto 4:

1. `check-declarados` contra Azure: cuántos de los 103 declarados faltan hoy.
2. `check-diccionario`: que la huérfana siga siendo esa y solo esa.
3. `pg_depend`: que no haya otros dependientes de
   `mart.fact_seguimiento_categoria` creados fuera del repositorio.
4. **ESCRITURA, la autoriza el humano**: `publicar-diccionario` para servir la
   versión 10. Hasta entonces `_meta` sigue diciendo que esos cuatro esquemas son
   de refresco manual, y ya no lo son.
5. **Decisión del humano**: si 3 h 24 acabando a las ~05:24 UTC vale o conviene
   adelantar el arranque. Enlaza con F-035 y F-025.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados | **2.581 pasados**, 128 saltados, 0 fallos (`bash harness/init.sh`) |
| Suite, tiempo | **387 s** con medición de cobertura; **~160 s** sin ella |
| Cobertura de líneas cambiadas | **100 % (259/259)**, umbral 80 %, nivel `critico` |
| Tests nuevos | **84**: 77 en los 4 ficheros `test_f047_*` y 7 en tests del arnés |
| `ruff` | 238 avisos frente a 237 de la línea base: **+1**, un `noqa: E402` inerte igual que los 27 que main.py ya tenía. Deuda previa, no bloquea |
| Mutación (serie, sin tope) | **70 mutantes, 63 muertos, 7 supervivientes, 0 timeouts**, 2 h 32 min. **1 era falso**; los **6 reales tienen test** y mueren. **Supervivientes finales: 0** |

**Cómo se midió.** Campaña **EN SERIE** (`--workers 1`, `--max-mutantes 0`),
no en paralelo: con 70 mutantes salía a cuenta y así **no aplica** la regla de
reverificación de F-041 —la paralela produce falsos muertos, y un falso muerto
esconde un superviviente real—. Costó **2 h 32 min** (130 s de media por
mutante), algo más de las ~2 h que el encargo ponía como aviso; se supo al
terminar, no antes. Análisis completo en `progress/mutacion_F-047.md`.

**15 supervivientes en total, 15 con test, 0 justificados como equivalentes.**
Ocho salieron de una primera pasada interrumpida en el 29/70, todos en los dos
steps nuevos y del mismo tipo —**nadie comprobaba lo que el paso DEJA DICHO**:
`exc_info`, `rows`, el guardián `target_schema AND target_table`, el redondeo de
`duration_s`—; uno obligó a sacar la lista de sub-pasos a `SUB_PASOS`, porque
cableada dentro de `run()` **la condición no era comprobable**.

**Hallazgo que NO está en F-041**: de los siete de la campaña completa, uno era
**FALSO SUPERVIVIENTE** (muere a mano, dos tests caídos) **y la campaña era EN
SERIE**. F-041 documenta falsos MUERTOS del modo paralelo; esto es un falso
superviviente con un solo worker, y el sospechoso es el `__pycache__`. Dirección
inofensiva —cuesta un test de más—, pero **hay que anotarlo en F-041**.

**Controles a mano y con el bytecode limpio**: los 15 mutantes aplicados uno a
uno, suite entera; los 15 mueren. Tres de los reales eran del arnés genérico
—en el alcance solo por la topología de la rama—: sus tests se **portaron a
`arnes-base`** en el mismo trabajo (commit `f097e62`), regla de propagación.

**F-044 queda absorbida**: sus cinco criterios están cubiertos salvo los dos que
exigen medir contra la base (tiempo real de la nocturna y pico de disco), que
son las verificaciones MANUAL 1 y 5. Cerrarla es del líder, no mío.
