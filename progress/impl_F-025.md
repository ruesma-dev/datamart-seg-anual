<!-- progress/impl_F-025.md -->
# F-025 · Implementación · Las obras cerradas no se reconstruyen cada noche

Rama `feature/F-025-ventana-negocio-build`. **Fases 0 a 6 hechas; la fase 7
entera (T27-T35) es MANUAL y queda para el humano**: escribe contra producción.

## Qué cambió, en una frase

El datamart deja de reconstruir las 920 obras cada noche —se rehacen 40 y 880
conservan su última versión buena— **y las dos tablas acotadas dejan de
truncarse**: cada tramo borra exactamente las obras que va a reinsertar, en su
misma transacción. Lo segundo repara por sí solo la avería del 02-sep, aunque
el acotado no ahorrase nada.

**La ventana nace APAGADA** (`PG_VENTANA_ACTIVA=false`, R5). Mientras no se
encienda, el contenido publicado es exactamente el de hoy.

## El corazón: el borrado derivado (R10, R13)

El `TRUNCATE` de `plan_mensual` **no estaba dentro del SQL troceado**: lo
lanzaba el step una vez, antes de los 60 tramos. Pasarle solo las obras vivas al
troceado de F-019 tal cual **habría vaciado la tabla y dejado 40 obras de 920**,
que es lo que el humano prohibió. Ahora las dos listas —lo que se borra y lo que
se escribe— **se componen del mismo dato**, así que no pueden desincronizarse.

**Eso invierte una invariante de F-019 y se hizo a propósito.** Sus tests
exigían que abortar dejase la tabla VACÍA, porque una tabla a medias era
indistinguible de una completa. Ya no: lo que queda son obras enteras con su
última versión buena, y vaciarlas destruiría lo congelado. **Los tests de F-019
se reescribieron a la invariante nueva, con su porqué en cada docstring, no se
relajaron.** Quien impide que `build_mart` construya sobre un stage a medias
sigue siendo la puerta de F-024, intacta.

## Ficheros tocados

**Creados:** `domain/ventana.py` (criterio, firma, sello, veredicto),
`infrastructure/postgres/ventana_sql.py` (las cuatro consultas del guardián,
solo texto), `infra/97_create_alert_ventana.ps1` y once `tests/test_f025_*.py`.

**Modificados:** `build_stg_step.py` (plan, borrado derivado, registro, aborto,
VACUUM), `ingest_raw_step.py` (sub-paso de la firma), `postgres_client.py` (seis
consultas, ocho métodos), `sql/ddl/00_meta.sql`, `sql/stg/06_presupuesto.sql`,
`huella_ampliada.py`, `main.py` (`ventana-plan`, `check-ventana`,
`--reconstruir-todo`, `--desde plan_obra`), `config/settings.py`,
`config/business_rules.yaml`, cuatro fichas del diccionario,
`docs/ARCHITECTURE.md`, `infra/env/dev.json` e `infra/README.md`. Fuera del
repositorio, `azure-apps/datamart_seg_anual.md`, en su propio commit.

**Intactos, comprobado con el diff y no de memoria** (§10): `08_plan_mensual.sql`
—su marcador ya estaba—, `sql/mart/**`, `sql/cierre/**` y `domain/tramos.py`. En
`06_presupuesto.sql` el diff son **dos líneas**: se va el `TRUNCATE`, entra el
filtro; **ni una línea de su lógica**.

## Decisiones de diseño que no estaban en la spec

1. **La firma se parte en dos columnas** (`firma_origen` = la del origen cuando
   se construyó; `firma_actual` = la de esta noche). Con una sola, la ingesta
   pisaría la referencia cada noche y la comparación no diría nada.
2. **El censo sale de `raw.obr JOIN raw.con`, no de `maestro.obras`**: esa vista
   la construye `build_maestros`, que va DESPUÉS de este build y en una base
   nueva no existe. Leyendo `raw` no hay dependencia de orden.
3. **Las obras sobrantes se NOMBRAN, no se borran.** La primera versión las
   borraba en la completa; se cambió al ver de dónde sale el universo con el que
   se decide —ese mismo `JOIN`—: borrar por lo que no vea sería destruir datos
   buenos en silencio, y R10 dice que **lo que se borra se deriva de lo que se
   va a escribir**. Así la invariante no tiene ni una excepción. Precio
   declarado: una obra retirada de Sigrid conserva sus filas hasta que alguien
   las borre a mano.
4. **El registro va en llamada aparte, no dentro del SQL del tramo**, porque
   `execute_sql_text` devuelve el `rowcount` de la última sentencia. Si el
   proceso muere entre el tramo y su registro, la obra entra mañana por R18: se
   reconstruye de más, que es el lado correcto en el que fallar.
5. **El sello es función de módulo, no método**: lo necesitan el step, el
   comando y el guardián, y los dos últimos no tienen por qué instanciar un
   step para leer dos ficheros y hacer un hash.

## El arreglo de F-052 que pidió el humano

`check-cobertura` **salía OK habiendo mirado CERO combinaciones**. No era
teórico: pasó contra producción el 02-sep, con `stg.plan_mensual` truncada al
21,6 % —las dos consultas devolvieron cero filas y dijo OK—, y por eso F-052
está `blocked`. Ahora sale KO, con marcador y con un informe que lo explica.

Lo más incómodo: **el propio módulo ya lo declaraba** en el docstring de
`Veredicto` y guardaba `filas_miradas` para eso; faltaba la línea que lo
aplicase. Y un test de F-052 pasaba en falso —comprobaba el «todo declarado» con
un doble **sin ninguna fila**, o sea verificaba justo el defecto—: ahora recibe
una combinación sana y el caso de cero tiene su test aparte. `check-ventana`
nació con la regla puesta.

## Fase RED · las trazas

**T3 — el criterio de obra congelada.** Tests escritos antes del módulo:

```
$ python -m pytest tests/test_f025_ventana.py -q
tests\test_f025_ventana.py:31: in <module>
    from etl_sigrid.domain.ventana import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.ventana'
=========================== short test summary info ===========================
ERROR tests/test_f025_ventana.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.28s
```

**T10 — el build que no borra lo que no reconstruye.** Igual, antes del código:

```
$ python -m pytest tests/test_f025_build.py -q
tests\test_f025_build.py:45: in <module>
    from etl_sigrid.application.steps.build_stg_step import (
E   ImportError: cannot import name 'componer_borrado_derivado' from
    'etl_sigrid.application.steps.build_stg_step'
=========================== short test summary info ===========================
ERROR tests/test_f025_build.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 1.59s
```

**T5** falló en rojo por `FICHEROS_DEL_SELLO` inexistente (23 de 24 en verde) y
**T9** por las fichas del diccionario. Los dos, en sus commits.

## Verificaciones MANUAL pendientes (fase 7 entera, y T1/T2b)

Ninguna se ha ejecutado: **todas escriben contra producción o barren tablas de
millones de filas**, y el servidor sigue recuperando créditos de CPU tras la
avería.

| | Qué falta |
|---|---|
| **T1** | Peso real por obra (`SQL_PESOS_PLAN_MENSUAL`). **Decide si la feature merece la pena**: si el ahorro es menor del 40 %, la spec manda PARAR |
| **T2b** | Coste del scan de la firma sobre `raw.obrparpre`, con y sin `planif`. Decide la forma final de la firma. La consulta cara está escrita en `SQL_FIRMA_ORIGEN_CON_PLANIF`, lista para medir |
| **T27-T31b** | Las cinco huellas del antes, la reconstrucción acotada, las cinco del después con **tolerancia CERO**, la 0599 y `_meta.v_frescura_obra` |
| **T32-T34** | Los cinco `check-*`, el bloat contra la línea base de T2 y los créditos de CPU |
| **T35** | Desplegar `infra/97_create_alert_ventana.ps1`. **Sin esto el guardián es mudo** |

**LAS ONCE, CON SU COMANDO LITERAL Y EN ORDEN, EN `progress/current.md`**
(sección «LAS MANUAL DE LA FASE 7»): el humano puede ejecutarlas sin releer la
spec. Es el tercer punto de C4, el que el reviewer marcó en rojo.

**Y una que no está en `tasks.md`:** encender `PG_VENTANA_ACTIVA` es una
decisión del humano. Hasta entonces esto solo repara el `TRUNCATE`. **Con un
hueco recién encontrado:** `infra/80_create_job.ps1` enumera las `--env-vars`
del job una a una y **ninguna `PG_VENTANA_*` está en la lista**;
`85_update_job.ps1` solo cambia la imagen. Encenderla en producción exige tocar
infra o fijarla sobre el job (`az containerapp job update --set-env-vars`). **No
se ha tocado `infra/`**: cómo se despliega el job lo decide el humano.

## Evidencias
| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **3.305 en verde**, 134 saltados. De ellos **290 son de F-025** |
| **Suite completa** | **163 s** (`python -m pytest tests/`) |
| **Cobertura de las líneas cambiadas** | **91,7 %** (578/630, umbral 80 %, nivel `critico`) |
| **Mutantes generados / evaluados** | **83 / 83**, 0 timeouts, 0 sin veredicto |
| **Supervivientes** | **5 en la campaña**, los cinco analizados y **cerrados con test**; detalle en `progress/mutacion_F-025.md` |
| **Coste de la campaña** | **59,3 min** con 4 workers (línea base 210-214 s) |
| **`bash harness/init.sh`** | **EN VERDE**, 3.305 pasados y 134 saltados en 385 s |

### La campaña de mutación (T26, DA-6)

**83 mutantes sobre `domain/ventana.py`, 78 muertos, 5 supervivientes, 0
timeouts.** Informe completo en `progress/mutacion_F-025.md`. Los cinco están
analizados y **ninguno era equivalente**: los cinco eran huecos de test reales,
y los cinco están cerrados con un test que los mata.

**Todos estaban en la capa que REDACTA la denuncia**, no en la que decide. Es
la parte que uno prueba de oído —«sale la obra en el informe, pues ya está»— y
no es cosmética: con el guardián avisando sin bloquear (DA-5), esa capa es la
única vía por la que el hallazgo llega a una persona.

| Superviviente | Qué habría pasado |
|---|---|
| `if not self.codigo` invertido en `marcador` | **Marcador vacío en KO y emitido en verde**: la alerta no dispararía nunca, y dispararía todas las noches. Las dos mitades de la avería que la alerta existe para no tener |
| `de_tipo` con `!=` | Cada obra **bajo el epígrafe equivocado**: la 0599 saldría como «congelada sin filas» cuando lo que le pasa es que su origen cambió |
| `obras_miradas: int = 0 → 1` | Un veredicto sin censo daría **verde**. Es el defecto de `check-cobertura` otra vez, en el default |
| `_corto`: `[:8] → [:9]` y `or → and` | El `detalle` publicado en `_meta.obra_build` dejaría de traer los prefijos comparables de los dos sellos |

**Y por qué no los cazaba nadie, que es el hallazgo útil:** mis tests del
guardián comprobaban `MARCADOR_KO in output`, **y ese literal aparece también en
la línea de log**, que lo escribe desde la constante: pasaban aunque el marcador
compuesto viniera vacío. Los nuevos miran **la propiedad**, no la salida. El de
`de_tipo` es igual: con un solo hallazgo el texto sale idéntico, solo que bajo
el epígrafe que no toca.

### Lo que la primera pasada ya cambió (resumen; detalle en `223cd1d`)

La campaña **encontró un defecto real antes de terminar**: diez de sus veinte
supervivientes vivían en `_meses_antes`, un helper que recortaba el día al
último del mes destino y **cuya rama no se ejecutaba nunca** con el criterio
real. No se taparon con tests: **se borró** y se sustituyó por
`meses_transcurridos`, que cuenta meses enteros, que es lo que dice el dato
(la actividad es `MAX(make_date(anio, mes, 1))`, siempre día 1). Los otros diez
eran **defaults de dataclass** que ningún test alcanzaba, y cada uno era una
decisión de seguridad sin protección —`Plan.completa` en `True` habría hecho
que **las 880 obras no se rehicieran nunca**—. Todos tienen ya su test.

## El censo, remedido: la contrapartida que se le enseñó al humano estaba inflada

Circulaban tres cifras para «congeladas pese a tener actividad» (7, 39, 8) y dos
para la regla 2 (222, 226). **Remedido el 2026-09-03 en solo lectura con la
definición QUE IMPLEMENTA EL CÓDIGO** —universo `raw.obr ⨝ raw.con` y actividad
`MAX(make_date(f.anio, GREATEST(f.mes,1), 1))` de `stg.fases`, o sea
`postgres_client.SQL_ESTADO_OBRAS`—, con la consulta entera guardada en
`mediciones.md` §5:

| universo | congeladas | diarias | al fact | regla 1 | regla 2 | regla 3 | con actividad | **congeladas con actividad** |
|---|---|---|---|---|---|---|---|---|
| 920 | 880 | 40 | 38 | 693 | **226** | 872 | 48 | **8** |

Las 8 son **7 CERRADAS (estado 25)** y **1 de seis dígitos**, la `180501`. Y
**0 de las 226** de seis dígitos están en `stg.obras`, que es el `INNER JOIN`
por el que pasa el fact: se recomprobó sobre 226, no sobre 222.

**Al humano se le presentó un 40 donde son 8**, con un desglose —39 CERRADAS,
36 de ellas cerrando en 2025-12— que **no reproduce**: aquello se midió sobre
`maestro.obras` con `coalesce(fecha_fin, fecha_inicio)` y salía de
`obras_congeladas_F025.csv`, que da a 36 obras una actividad de 2025-12 que
`stg.fases` desmiente. **El error fue de quien midió, no del código.** Su
decisión NO cambia —880/40 cuadra al dedillo y la contrapartida real es MENOR
que la aceptada—, pero el registro tenía que decir la verdad: queda escrito así
en `decisiones.md` §DA-1, R2/R3, `mediciones.md` §2 y §5, `design.md`,
`ARCHITECTURE.md`, `business_rules.yaml` y la ficha `estado_id` del diccionario.

## Desviaciones respecto a la spec

Ninguna en el alcance. Dos matices que conviene que el reviewer mire:

- **El borde de los doce meses se cuenta en meses, no en días** (ver arriba):
  cambia una obra cuya última fase sea de hace exactamente doce meses. Va del
  lado seguro —no congela— y es más fiel al dato, que es mensual.
- **La spec pedía `filas` en el registro** y no decía de qué. Se guardan las de
  `stg.plan_mensual` de esa obra, medidas con una agregación por tramo acotada
  por el índice, no el total del tramo repartido.
