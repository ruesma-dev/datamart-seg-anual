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

**Creados:** `etl_sigrid/domain/ventana.py` (el criterio, la firma, el sello, el
veredicto), `etl_sigrid/infrastructure/postgres/ventana_sql.py` (las cuatro
consultas del guardián, solo texto), `infra/97_create_alert_ventana.ps1`, y once
`tests/test_f025_*.py`.

**Modificados:** `build_stg_step.py` (plan, borrado derivado, registro, aborto,
VACUUM), `ingest_raw_step.py` (sub-paso de la firma), `postgres_client.py` (seis
consultas y ocho métodos), `sql/ddl/00_meta.sql` (`_meta.obra_build` y
`_meta.v_frescura_obra`), `sql/stg/06_presupuesto.sql` (marcador y `TRUNCATE`
fuera; **ni una línea de su lógica**), `huella_ampliada.py` (quinta huella),
`main.py` (`ventana-plan`, `check-ventana`, `--reconstruir-todo`, `--desde
plan_obra`), `config/settings.py`, `config/business_rules.yaml`,
`config/diccionario/{00_global,_meta,stg,maestro}.yaml`, `docs/ARCHITECTURE.md`,
`infra/env/dev.json`, `infra/README.md`.

**Fuera de este repositorio:** `azure-apps/datamart_seg_anual.md`, en su propio
commit y en su repositorio, como manda la regla de propiedad.

**Intactos, y comprobado con el diff, no de memoria** (§10 de la spec):
`08_plan_mensual.sql` —su marcador ya estaba—, `sql/mart/**`, `sql/cierre/**` y
`domain/tramos.py`. Y en `06_presupuesto.sql` el diff son **dos líneas**: se va
el `TRUNCATE`, entra el filtro. Ni una de su lógica.

## Decisiones de diseño que no estaban en la spec

1. **La firma se parte en dos columnas** (`firma_origen` = la del origen cuando
   se construyó; `firma_actual` = la de esta noche). El diseño hablaba de una.
   Con una sola, la ingesta pisaría la referencia cada noche y la comparación no
   diría nada.
2. **El censo sale de `raw.obr JOIN raw.con`, no de `maestro.obras`.** Esa vista
   la construye `build_maestros`, que en `run-all` va DESPUÉS de este build, y
   en una base nueva no existe. Leyendo `raw` no hay dependencia de orden.
3. **Las obras sobrantes se NOMBRAN, no se borran.** El borrado derivado no
   alcanza a una obra que desapareciera del origen, y sin esto nadie lo sabría.
   La primera versión las borraba en la completa; se cambió al ver de dónde sale
   el universo con el que se decide: del censo, que es `raw.obr JOIN raw.con`.
   Borrar por lo que ese `JOIN` no vea sería destruir datos buenos en silencio,
   y R10 dice que **lo que se borra se deriva de lo que se va a escribir**. Con
   el cambio, la invariante de la feature no tiene ni una excepción. El precio,
   declarado: una obra retirada de Sigrid conserva sus filas hasta que alguien
   las borre a mano.
4. **El registro va en llamada aparte, no dentro del SQL del tramo**, porque
   `execute_sql_text` devuelve el `rowcount` de la última sentencia. Si el
   proceso muere entre el tramo y su registro, la obra entra mañana por R18: se
   reconstruye de más, que es el lado correcto en el que fallar.
5. **El sello es función de módulo, no método**: lo necesitan el step, el
   comando y el guardián, y los dos últimos no tienen por qué instanciar un step
   para leer dos ficheros y hacer un hash.

## El arreglo de F-052 que pidió el humano

`check-cobertura` **salía OK habiendo mirado CERO combinaciones**. No era
teórico: pasó contra producción el 02-sep, con `stg.plan_mensual` truncada al
21,6 % —las dos consultas devolvieron cero filas y dijo OK—, y por eso F-052
está `blocked`. Ahora sale KO, con marcador y con un informe que lo explica.

Lo más incómodo del hallazgo: **el propio módulo ya lo declaraba** en el
docstring de `Veredicto` —«un veredicto verde sobre cero filas no es un verde»—
y guardaba `filas_miradas` para eso. Faltaba la línea que lo aplicase.

Y un test de F-052 que pasaba en falso: comprobaba que el comando sale con 0
«cuando todo está declarado» usando un doble **sin ninguna fila**, así que
verificaba justo el defecto. Ahora se le da una combinación sana, y el caso de
cero tiene su test aparte. `check-ventana` nació con la regla puesta.

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

**T5 — el sello sobre el SQL real** falló en rojo por `FICHEROS_DEL_SELLO`
inexistente (23 de 24 en verde), y **T9** por las fichas del diccionario que
todavía no existían. Los dos, en sus commits.

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

**Y una que no está en `tasks.md`:** encender `PG_VENTANA_ACTIVA` es una
decisión del humano. Hasta entonces esto solo repara el `TRUNCATE`.

## Evidencias

| Evidencia | Valor |
|---|---|
| **Tests ejecutados** | **3.294 en verde**, 134 saltados. De ellos **278 son de F-025** |
| **Suite completa** | **164 s** (`python -m pytest tests/`) |
| **Cobertura de las líneas cambiadas** | PENDIENTE-COBERTURA |
| **Mutantes / supervivientes** | PENDIENTE-MUTACION |
| **`bash harness/init.sh`** | PENDIENTE-INIT |

### La campaña de mutación (T26, DA-6)

PENDIENTE-ANALISIS

### Lo que la primera pasada ya cambió

La campaña **encontró un defecto real antes de terminar**: diez de sus veinte
supervivientes estaban en cuatro líneas de `_meses_antes`, el helper que restaba
doce meses a una fecha y recortaba el día al último del mes destino. **Esa rama
nunca se ejecutaba** con el criterio real —restar 12 meses cae en el mismo mes,
que tiene los mismos días— y ningún test podía alcanzarla.

La respuesta no fue escribir tests que la taparan, sino **borrarla**: se
sustituyó por `meses_transcurridos`, que cuenta meses enteros. Y no es una
simplificación perezosa, es lo que dice el dato: la actividad sale de
`MAX(make_date(anio, mes, 1))`, siempre día 1, así que comparar días era
inventarse una precisión que el origen no tiene. Cambia un borde —una obra cuya
última fase es de hace exactamente doce meses ya no depende del día— y hay un
test que lo dice.

Los otros diez eran **defaults de dataclass** que ningún test alcanzaba porque
todos construían las obras con todos los campos informados. Cada uno era una
decisión de seguridad sin protección: `tiene_filas` y `registrada` en `False`
—ante la duda no se congela—, `firma_divergente` en `False` —«no se sabe» no es
«cambió»— y `Plan.completa` en `False` —si naciera en `True`, el hito se
registraría cada noche y **las 880 obras no se reharían nunca**—. Todos tienen
ahora su test con su porqué.

## Desviaciones respecto a la spec

Ninguna en el alcance. Dos matices que conviene que el reviewer mire:

- **El borde de los doce meses se cuenta en meses, no en días** (ver arriba). Es
  un cambio de comportamiento en un caso: una obra cuya última fase es de hace
  exactamente doce meses. Va del lado seguro —no congela— y es más fiel al dato.
- **La spec pedía `filas` en el registro** y no decía de qué. Se guarda las
  filas de `stg.plan_mensual` de esa obra, medidas con una agregación por tramo
  acotada por el índice, no el total del tramo repartido.
