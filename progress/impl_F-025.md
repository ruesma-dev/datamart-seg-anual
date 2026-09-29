<!-- progress/impl_F-025.md -->
# F-025 · Implementación · Las obras cerradas no se reconstruyen cada noche

Rama `feature/F-025-ventana-negocio-build`. **Fases 0 a 6 hechas; la fase 7 entera (T27-T35)
es MANUAL y queda para el humano**: escribe contra producción.

## Qué cambió, en una frase

El datamart deja de reconstruir las 920 obras cada noche —se rehacen 40 y 880 conservan su
última versión buena— **y las dos tablas acotadas dejan de truncarse**: cada tramo borra
exactamente las obras que va a reinsertar, en su misma transacción. Lo segundo repara por sí
solo la avería del 02-sep, aunque el acotado no ahorrase nada. **La ventana nace APAGADA**
(`PG_VENTANA_ACTIVA=false`, R5): mientras no se encienda, lo publicado es lo de hoy.

## El corazón: el borrado derivado (R10, R13)

El `TRUNCATE` de `plan_mensual` **no estaba dentro del SQL troceado**: lo lanzaba el step
una vez, antes de los 60 tramos. Pasarle solo las obras vivas al troceado de F-019 tal cual
**habría vaciado la tabla y dejado 40 obras de 920**, que es lo que el humano prohibió.
Ahora las dos listas —lo que se borra y lo que se escribe— **se componen del mismo dato**,
así que no pueden desincronizarse.

**Eso invierte una invariante de F-019 y se hizo a propósito.** Sus tests exigían que
abortar dejase la tabla VACÍA, porque una tabla a medias era indistinguible de una completa.
Ya no: lo que queda son obras enteras con su última versión buena, y vaciarlas destruiría lo
congelado. **Los tests de F-019 se reescribieron a la invariante nueva, con su porqué en
cada docstring, no se relajaron.** Quien impide que `build_mart` construya sobre un stage a
medias sigue siendo F-024, intacta.

## Ficheros tocados

**Creados:** `domain/ventana.py` (criterio, firma, sello, veredicto),
`infrastructure/postgres/ventana_sql.py` (las cuatro consultas del guardián, solo texto),
`infra/97_create_alert_ventana.ps1` y once `tests/test_f025_*.py`.

**Modificados:** `build_stg_step.py` (plan, borrado derivado, registro, aborto, VACUUM),
`ingest_raw_step.py` (sub-paso de la firma), `postgres_client.py` (seis consultas, ocho
métodos), `sql/ddl/00_meta.sql`, `sql/stg/06_presupuesto.sql`, `huella_ampliada.py`,
`main.py` (`ventana-plan`, `check-ventana`, `--reconstruir-todo`, `--desde plan_obra`),
`config/settings.py`, `config/business_rules.yaml`, cuatro fichas del diccionario,
`docs/ARCHITECTURE.md`, `infra/env/dev.json` e `infra/README.md`. Fuera del repositorio,
`azure-apps/datamart_seg_anual.md`, en su propio commit.

**Intactos, comprobado con el diff y no de memoria** (§10): `08_plan_mensual.sql`,
`sql/mart/**`, `sql/cierre/**` y `domain/tramos.py`. En `06_presupuesto.sql` el diff son
**dos líneas** —se va el `TRUNCATE`, entra el filtro—, ni una de lógica.

## Decisiones de diseño que no estaban en la spec

1. **La firma se parte en dos columnas** (`firma_origen` = la del origen cuando se
   construyó; `firma_actual` = la de esta noche). Con una sola, la ingesta pisaría la
   referencia cada noche y la comparación no diría nada.
2. **El censo sale de `raw.obr JOIN raw.con`, no de `maestro.obras`**: esa vista la
   construye `build_maestros`, que va DESPUÉS de este build y en una base nueva no existe.
   Leyendo `raw` no hay dependencia de orden.
3. **Las obras sobrantes se NOMBRAN, no se borran.** Borrar por lo que el `JOIN` no vea
   sería destruir datos buenos en silencio, y R10 dice que **lo que se borra se deriva de lo
   que se va a escribir**: así la invariante no tiene ni una excepción. Precio declarado:
   una obra retirada de Sigrid conserva sus filas hasta que alguien las borre a mano.
4. **El registro va en llamada aparte, no dentro del SQL del tramo**: `execute_sql_text`
   devuelve el `rowcount` de la última sentencia. Si el proceso muere entre el tramo y su
   registro, la obra entra mañana por R18 —se reconstruye de más, el lado correcto en el que
   fallar—.
5. **El sello es función de módulo, no método**: lo necesitan el step, el comando y el
   guardián, y los dos últimos no tienen por qué instanciar un step para hacer un hash.

## El arreglo de F-052 que pidió el humano

`check-cobertura` **salía OK habiendo mirado CERO combinaciones**. No era teórico: pasó
contra producción el 02-sep, con `stg.plan_mensual` truncada al 21,6 % —las dos consultas
devolvieron cero filas y dijo OK—, y por eso F-052 está `blocked`. Ahora sale KO, con
marcador y con un informe que lo explica.

Lo más incómodo: **el propio módulo ya lo declaraba** en el docstring de `Veredicto` y
guardaba `filas_miradas`; faltaba la línea que lo aplicase. Y un test de F-052 pasaba en
falso —comprobaba el «todo declarado» con un doble **sin ninguna fila**—: ahora recibe una
combinación sana. `check-ventana` nació con la regla puesta.

## Fase RED · las trazas

**T3 — el criterio de obra congelada.** Tests escritos antes del módulo:

```
$ python -m pytest tests/test_f025_ventana.py -q
tests\test_f025_ventana.py:31: in <module>
    from etl_sigrid.domain.ventana import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.ventana'
ERROR tests/test_f025_ventana.py — Interrupted: 1 error in 0.28s
```

**T10 — el build que no borra lo que no reconstruye.** Igual, antes del código:

```
$ python -m pytest tests/test_f025_build.py -q
tests\test_f025_build.py:45: in <module>
    from etl_sigrid.application.steps.build_stg_step import (
E   ImportError: cannot import name 'componer_borrado_derivado' from
    'etl_sigrid.application.steps.build_stg_step'
ERROR tests/test_f025_build.py — Interrupted: 1 error in 1.59s
```

**T5** falló por `FICHEROS_DEL_SELLO` inexistente y **T9** por las fichas del diccionario.
Los dos, en sus commits.

## Verificaciones MANUAL pendientes (fase 7 entera, y T1/T2b)

Ninguna se ha ejecutado: **todas escriben contra producción o barren tablas de millones de
filas**, y el servidor sigue recuperando créditos de CPU tras la avería.

| | Qué falta |
|---|---|
| **T1 / T2b** | Peso real por obra (`SQL_PESOS_PLAN_MENSUAL`): **decide si la feature merece la pena** —si el ahorro baja del 40 %, la spec manda PARAR—. Y el coste del scan de la firma sobre `raw.obrparpre` con y sin `planif`, que fija su forma final (`SQL_FIRMA_ORIGEN_CON_PLANIF`, lista para medir) |
| **T27-T31b** | Las cinco huellas del antes, la reconstrucción acotada, las cinco del después con **tolerancia CERO**, la 0599 y `_meta.v_frescura_obra` |
| **T32-T35** | Los cinco `check-*`, el bloat contra la línea base de T2, los créditos de CPU y **desplegar `infra/97_create_alert_ventana.ps1`: sin eso el guardián es mudo** |

**LAS ONCE, CON SU COMANDO LITERAL Y EN ORDEN, EN `progress/current.md`** (sección «LAS
MANUAL DE LA FASE 7»): el humano puede ejecutarlas sin releer la spec. Es el tercer punto de
C4, el que el reviewer marcó en rojo.

**Y una que no está en `tasks.md`:** encender `PG_VENTANA_ACTIVA` es una decisión del humano
—hasta entonces esto solo repara el `TRUNCATE`— y desde la pasada 3 se hace **cambiando
`"ventanaActiva": "true"` en `infra/env/dev.json`** y relanzando `80_create_job.ps1`
(§Pasada 3). **`85_update_job.ps1` NO vale**: solo cambia la imagen y no toca el entorno,
así que el despliegue habitual no llevaría el valor nuevo.

## Evidencias
| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **3.308 en verde**, 134 saltados. De ellos **293 son de F-025** |
| **Suite completa** | **163 s** suelta; **245 s** dentro de `init.sh`, con cobertura |
| **Cobertura de las líneas cambiadas** | **91,7 %** (578/630, umbral 80 %, nivel `critico`) |
| **Mutantes generados / evaluados** | **83 / 83** sobre `domain/ventana.py` = el **38 % del alcance real** (219 en 10 ficheros). El resto, **EXENTO por el humano** (DA-6) |
| **Supervivientes** | **0**, ninguno equivalente y ningún `PENDIENTE` |
| **Timeouts** | **4** — ni muertos ni supervivientes: **sin veredicto por reloj**. Cerrados por el reviewer (RM4), que los reprodujo sobre HEAD: **los cuatro MUEREN** en 5-9 s. **83 de 83 con veredicto** |
| **Coste de la campaña** | **7.720 s** (2 h 09) con **4 workers**; línea base **467-473 s** por worker, media 93,0 s por mutante |
| **`bash harness/init.sh`** | **EN VERDE** el 2026-09-04 tras la pasada 3: 3.308 pasados, 134 saltados, 245 s |

### La campaña (T26, DA-6): qué midió y qué NO

**Dos pasadas, y vale la segunda:** sobre `073af30` —el HEAD real de `ventana.py`, sin
cambios desde entonces— y con **CERO supervivientes**. El review invalidó la primera
(`8e9b1f2`), y **sus números —5 supervivientes, 59,3 min, base 210-214 s— estuvieron
publicados en esta tabla por error hasta el 2026-09-04**. Las dos, en
`progress/mutacion_F-025.md`.

**Lo que NO midió.** El alcance se declaró a mano («Origen del diff: **ficheros**») y cubrió
**un fichero de diez**: recalculado con `harness.alcance`, la feature son **10 ficheros,
2.610 líneas, 219 mutantes**. Fuera quedaron **`build_stg_step.py` (34), donde vive
`componer_borrado_derivado`, o sea LO QUE SE BORRA**, `main.py` (37), `postgres_client.py`
(31, con `SQL_ESTADO_OBRAS`), `ventana_sql.py` (15) y `cobertura.py` (6).

**El humano lo eximió por escrito el 2026-09-04**, como en F-042 y F-052: DA-6 de
`decisiones.md`, la ficha de `features.json` y T26. Lo cubren en su lugar
`test_f025_build.py`, el 91,7 % de cobertura y **las cinco huellas con tolerancia CERO de
T27/T30** —que **siguen sin ejecutar**: hoy ese hueco lo cubren solo los tests.

**Qué encontró** (detalle en `mutacion_F-025.md` y en `223cd1d`): un defecto real que borró
en vez de tapar —`_meses_antes`, helper **cuya rama no se ejecutaba nunca**— y diez
**defaults de dataclass** sin test, cada uno una decisión de seguridad sin protección
(`Plan.completa` en `True` habría hecho que **las 880 obras no se rehicieran nunca**). Los
cinco supervivientes de la primera pasada estaban todos en la capa que REDACTA la denuncia
—el peor dejaba el **marcador vacío en KO y emitido en verde**— y no los cazaba nadie porque
los tests miraban `MARCADOR_KO in output`, **literal que sale también en la línea de log**.

## El censo, remedido: la contrapartida que se le enseñó al humano estaba inflada

Circulaban tres cifras para «congeladas pese a tener actividad» (7, 39, 8) y dos para la
regla 2 (222, 226). **Remedido el 2026-09-03 en solo lectura con la definición QUE
IMPLEMENTA EL CÓDIGO** —`postgres_client.SQL_ESTADO_OBRAS`: universo `raw.obr ⨝ raw.con` y
actividad `MAX(make_date(...))` de `stg.fases`—, con la consulta entera en `mediciones.md`
§5:

| universo | congeladas | diarias | al fact | regla 1 | regla 2 | regla 3 | con actividad | **congeladas con actividad** |
|---|---|---|---|---|---|---|---|---|
| 920 | 880 | 40 | 38 | 693 | **226** | 872 | 48 | **8** |

Las 8 son **7 CERRADAS (estado 25)** y **1 de seis dígitos**, la `180501`; y **0 de las
226** están en `stg.obras`, el `INNER JOIN` por el que pasa el fact (recomprobado sobre 226,
no sobre 222). **Al humano se le presentó un 40 donde son 8**, con un desglose —39 CERRADAS,
36 cerrando en 2025-12— que **no reproduce**: se midió sobre `maestro.obras` con
`coalesce(fecha_fin, fecha_inicio)`, que atribuye a 36 obras una actividad que `stg.fases`
desmiente. **El error fue de quien midió, no del código.** Su decisión NO cambia —880/40
cuadra y la contrapartida real es MENOR que la aceptada—, pero el registro tenía que decir
la verdad: corregido en `decisiones.md` §DA-1, R2/R3, `mediciones.md` §2 y §5, `design.md`,
`ARCHITECTURE.md`, `business_rules.yaml`, la ficha `estado_id` del diccionario **y, desde la
pasada 3, también en el código**.

## Pasada 3 del review · los tres cambios requeridos

**Registro y despliegue, ni una línea de lógica**: campaña, cobertura y huellas siguen
valiendo tal cual. **1 · El censo corregido llega al código**, donde se había parado en
`.md` y `.yaml`. Barrido sobre **el árbol entero** de lo que §DA-1 declara muerto —el 40
congeladas-con-actividad (**8 de 48**), el 80 con actividad (**48**), el 222 de seis dígitos
(**226**) y el «39 CERRADAS, 36 por el cierre de 2025-12», que **no reproduce**—: los ocho
del review, con `main.py:1333` —**el `--help` del paso 5 de las MANUAL**— a la cabeza, **y
tres que su tabla no listaba**: `config/diccionario/stg.yaml:73` (**ficha PUBLICADA en
`_meta`, la que lee el MCP**), `test_f025_settings.py:213` y `current.md:319`. **Once
sitios**, todos comentario o docstring; donde la cifra vieja se cita es para enterrarla y
decir que manda `SQL_ESTADO_OBRAS`.

**2 · Las `PG_VENTANA_*`, declaradas en `infra/`.** Cuatro claves en `infra/env/dev.json`
(`ventanaActiva`, `ventanaMeses`, `ventanaDiaCompleta`, `ventanaRescate`) con su
`$aviso_ventanaEnv`, y su bloque en `80_create_job.ps1`. **`ventanaActiva` nace en
`"false"`** (R5): no enciende nada; hace que encenderla sea cambiar un valor **versionado**
en vez de un `az ... --set-env-vars` suelto que desaparece sin ruido al recrear el job.
Booleanos como cadena, igual que `pgAutoCreateDb`, o PowerShell interpolaría `False`. **Tres
tests nuevos** cierran el circuito nombre→valor→inyección: el job los inyecta desde `$CFG`,
**todo** entorno los declara con ventana y rescate apagados, y
`ventanaMeses`/`ventanaDiaCompleta` no divergen del código —el contenedor no lleva
`dev.json`—; los dos interruptores quedan fuera de esa red **a propósito**, tienen que poder
divergir. **`85_update_job.ps1` no se ha tocado y conviene saberlo:** solo cambia la imagen,
así que el valor nuevo **solo llega recreando el job**. Dicho en `current.md`, paso 6.
**Menor:** `features.json` decía 91,5 % donde el portero mide **91,7 %**.

## Desviaciones respecto a la spec

Ninguna en el alcance. Dos matices para el reviewer: **los doce meses se cuentan en meses,
no en días** —cambia una obra cuya última fase sea de hace justo doce meses; va del lado
seguro y es más fiel al dato—; y **la spec pedía `filas` sin decir de qué**: son las de
`stg.plan_mensual` de esa obra, agregadas por tramo con índice, no el total repartido.
