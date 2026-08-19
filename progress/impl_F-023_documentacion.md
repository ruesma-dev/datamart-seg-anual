<!-- progress/impl_F-023_documentacion.md -->
# F-023 · Documentación de cierre (solo documentación)

Fecha: 2026-08-19. Rama: `feature/F-024-coherencia-cargas-truncadas`.
Encargo: reflejar en la documentación que los Excels auxiliares se leen del
blob, actualizar el documento del proyecto en `azure-apps/` y marcar en
`specs/F-003-infra-caj/tasks.md` lo que corresponda. **Sin tocar código, sin
tocar Azure, sin ejecutar nada contra la base.**

Fuente de las evidencias: `progress/manual_F-023.md` (las tres verificaciones
de F-004) y `progress/current.md` §«Tanda 2 EJECUTADA el 2026-08-17» (el
despliegue del job). Ninguno de los dos se ha modificado.

## Ficheros tocados

| Fichero | Qué cambia |
|---|---|
| `infra/README.md` | Sección nueva «Los Excels auxiliares se leen del blob, no del disco» (sustituye a «Verificaciones heredadas de F-004»); §4 de los pasos con autorización distingue los dos roles de datos |
| `specs/F-003-infra-caj/tasks.md` | T23–T26 marcadas `[x]` con fecha, resultado y puntero a la evidencia; bloque nuevo con las tres verificaciones de F-004 (V1–V3) |
| `azure-apps/datamart_seg_anual.md` (otro repositorio) | Fila nueva en «Qué consume» + subsección de los Excels en blob; nota fechada en la cabecera de estado |
| `progress/impl_F-023_documentacion.md` | Este informe |

## 1 · `infra/README.md`

La sección que había («Verificaciones heredadas de F-004») describía tres
comprobaciones **pendientes** y no decía en ningún sitio de dónde salen los
Excels en Azure. Ahora dice las dos cosas:

- **Dónde viven**: contenedor `aux` de la cuenta del entorno (`storageAccount`
  en `infra/env/<entorno>.json`; en `dev`, `stdatamartsegdev`), creada por el
  paso 5.
- **Qué los apunta**: las tres `AUX_EXCEL_*`, con la URI del blob.
- **Qué rol hace falta**: `Storage Blob Data Reader` para leer;
  `Storage Blob Data Contributor` **solo** para subir o reemplazar. Son dos
  roles distintos y antes el README los mezclaba en uno.
- **Por dónde se autentica cada entorno**: identidad gestionada en el job,
  `az login` de la persona en el puesto. Ni SAS ni clave de cuenta.
- **La advertencia que hoy costó un intento fallido**: el `.env` del puesto
  puede seguir apuntando a rutas locales, así que un `load-aux` en `SUCCESS`
  con `origen=local` **no prueba nada del blob**. Lo que hay que mirar es el
  campo `origen` del evento `aux_file_read`; y como segunda pista, que leer del
  blob tarda segundos mientras que leer de disco es instantáneo. Incluye la
  invocación con las tres variables pasadas por entorno, que es la forma de
  comprobarlo **sin tocar `.env`**.
- **Las tres verificaciones, ya cumplidas**, en una tabla con la hora de cada
  una y la desviación de la tercera explicada, apuntando a
  `progress/manual_F-023.md` para el detalle.

Se conservan a propósito el aviso de `pip install -r requirements.txt` (la
lectura de blob falla con `ModuleNotFoundError` si faltan las librerías) y las
menciones a `F-019` que exige `test_f003_la_puerta_nombra_la_feature_bloqueante`.

## 2 · `azure-apps/datamart_seg_anual.md`

**No lo reflejaba**: la única fila sobre los Excels decía «Hoy sin implementar:
el step es un *stub*. Irán a Blob Storage». Cambios, siguiendo el estilo del
documento (tabla de «Qué consume» + subsección fechada debajo, como la de
F-024):

1. Fila de «Qué consume» reescrita: Blob Storage propio, cuenta y contenedor,
   lectura por identidad con `Storage Blob Data Reader`, sin claves ni SAS.
2. Subsección «Los Excels auxiliares se leen del blob (verificado el
   2026-08-19)»: los tres ficheros, las tres variables, los dos roles y qué
   pasa si falta el rol.
3. Cabecera: nota fechada que corrige el «EN LOCAL, sin desplegar en Azure».

Sobre el punto 3, y para que lo revise el humano: **el documento está más
desactualizado de lo que abarca este encargo**. Decía literalmente «Hoy no
existe ningún Container Apps Job en la suscripción», «Dónde vive el dato ·
Hoy: PostgreSQL local del puesto» y marcaba F-003/F-005 como «Diseñado». Nada
de eso es cierto desde el 2026-08-17. No lo he reescrito —se sale del encargo y
exige contrastar F-005 y F-003 recurso a recurso—, pero **no podía dejar la
cabecera diciendo que lo que describo como Azure «no es realidad»** mientras
añadía una sección de realidad verificada: la contradicción quedaba dentro del
mismo documento. La nota nueva delimita las dos cosas y **avisa de que el resto
está pendiente de una pasada**. Si el humano prefiere otra redacción, es una
línea.

Commit local en `azure-apps` (rama `master`), sin push, como se pidió.

## 3 · `specs/F-003-infra-caj/tasks.md` — lo que se ha marcado y lo que NO

Aquí hay un desajuste que conviene leer antes de dar el visto bueno.

**T23–T26 de F-003 no son las tres verificaciones de F-004.** Son: crear el job
(T23), ejecución de prueba y verificación de la build (T24), consultar los logs
en Log Analytics (T25) y crear la alerta y probar que el correo llega (T26). El
encargo pedía marcarlas «con su fecha y un puntero a
`progress/manual_F-023.md`», y **ese puntero no les corresponde**: lo que
acredita las cuatro es la tanda 2 del despliegue, ejecutada el **2026-08-17**
y anotada en `progress/current.md`. Las he marcado con esa evidencia, no con la
de hoy:

| Tarea | Marcada | Con qué evidencia |
|---|---|---|
| T23 crear el job | `[x]` | 2026-08-17: `caj-datamart-seg-dev` creado y programado `0 2 * * *` UTC; cuatro intentos y un bug real de `00_vars.ps1` corregido |
| T24 ejecución de prueba + build | `[x]` | 2026-08-17: ejecución `Succeeded`, `version` coincide con el tag; hallazgo de los `--args` pegados |
| T25 logs en Log Analytics | `[x]` | 2026-08-17 **y reconfirmada hoy**: la consulta del README devuelve líneas reales. Aquí sí hay puntero a `progress/manual_F-023.md` §«Verificación 2», que la ejerció otra vez. La columna del README estaba mal (`ContainerAppName_s`) y la corrigió F-024 (T3) |
| T26 alerta + correo | `[x]` | 2026-08-17: fallo a las 20:46:24 local, correo a las 20:51:58 (5 min 34 s, dentro de los 15 min de R25); DA-3 resuelta |

**Lo que NO he marcado, y por qué:**

- **T27** (anotar en `progress/current.md` el resultado de cada verificación
  MANUAL y las decisiones abiertas) y **T28** (`init.sh` en verde). Quedan
  fuera del encargo, `progress/current.md` es intocable en esta sesión y T27
  cierra contra el reviewer, no contra mí. **Son las dos que faltan para cerrar
  F-003.**
- **T18–T22 y T22 bis** siguen en `[ ]` aunque `progress/current.md` las da por
  ejecutadas el 2026-08-10 (tanda 1). No estaban en el encargo y no las he
  tocado; **lo aviso porque `tasks.md` está dando por pendiente medio bloque 5
  que ya está hecho**, y eso confunde a quien llegue nuevo tanto como el
  README viejo.

**Las tres verificaciones de F-004 no tenían ninguna tarea en esta spec**: no
aparecen en `tasks.md` de F-003 (solo en `infra/README.md` y en la cola de
`specs/F-004-.../tasks.md`, cuyas T1–T11 están cerradas). Como el acceptance de
F-023 pide «tasks.md con T23–T26 **y las verificaciones marcadas**», he añadido
un bloque propio antes de «Cierre» con V1, V2 y V3, cada una con su hora, la
desviación de V3 explicada y el puntero a `progress/manual_F-023.md`. No las he
numerado como tareas nuevas de la spec porque no lo son: se ejecutaron en F-023.

No he tocado la cola de `specs/F-004-.../tasks.md`, que sigue listando esas tres
verificaciones como pendientes. F-004 está `done` y modificar la spec de una
feature cerrada no estaba en el encargo; si se quiere cerrar también ahí, es un
cambio de tres líneas y lo señalo para que lo decida el humano.

## Decisiones de diseño (de documentación, que aquí es lo que hay)

1. **Nombres de recurso en el README, sí; en los scripts, no.** El README ya
   nombra `acralbaranesdev`, `psql-albaranes-rs9k2` y `kv-albaranes-rs9k2`, y la
   puerta que prohíbe nombres de recurso solo mira los `.ps1`
   (`test_f003_r5...` y el barrido de `Invoke-Az`). Aun así, en los ejemplos
   copiables he usado `<cuenta>` en vez del nombre literal, para que el mismo
   bloque valga en cualquier entorno; el nombre real aparece una vez, señalando
   que sale de `infra/env/<entorno>.json`.
2. **La segunda cuenta de almacenamiento de la prueba negativa no se nombra en
   el README.** En `progress/manual_F-023.md` sí está (es evidencia), pero en la
   documentación de infraestructura habría parecido una dependencia de este
   proyecto sobre un recurso de otro, que es justo lo que no es: valía cualquier
   cuenta sin el rol.
3. **Ningún dato prohibido.** No se ha escrito ninguna IP, GUID, dirección de
   correo, ID de suscripción ni de tenant en ninguno de los ficheros tocados,
   ni en este informe. A la persona que confirmó la recepción del correo se la
   nombra por su papel.

## Fase RED

**No aplica**: no hay una línea de código nueva ni un test nuevo. El encargo es
documentación y las tres verificaciones que documenta son MANUAL contra Azure,
ejecutadas y registradas en `progress/manual_F-023.md`. Lo que sí hay son
**puertas automáticas que ya existían** y que este cambio tenía que seguir
pasando (barrido de secretos, orden de los scripts en el README, la mención de
`F-019`, las ventanas de `--window-size` en los bloques de código): se ejecutó
la suite completa después de editar, y en verde.

## Verificaciones MANUAL pendientes

Ninguna nueva. De F-003 quedan T27 y T28 (arriba). De F-023, el veredicto del
reviewer.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados y resultado | **617 passed**, 0 fallos (871 warnings, todos `DeprecationWarning` de `datetime.utcnow()`, deuda previa) |
| Tiempo de ejecución de la suite | **6,61 s** |
| Cobertura de las líneas cambiadas | **100,0 % de 372 líneas** (372/372, umbral 80 %, nivel `critico`) según la línea `PUERTA COBERTURA`. Las 372 líneas **no son de este cambio**: son las que el arnés mide contra la base de la rama (trabajo de F-024); este cambio no toca ni una línea de Python |
| Mutantes generados y supervivientes | **no se ha lanzado campaña**, y no procede: no hay código nuevo que mutar y el encargo la excluía explícitamente |

Salida resumida de `bash harness/init.sh`, ejecutado **antes** de commitear (sin
pipes, tal cual):

```
[OK] Arnés v1.5.0 (2026-08-18)
    28 features, 17 abiertas, en curso: ['F-023'], bloqueadas: ['F-003']
[OK] features.json válido
[OK] BACKLOG.md al día
[AVISO] Hay features en estado blocked: revisa progress/current.md
[AVISO] ruff: 152 avisos (deuda previa, no bloquea)
617 passed, 871 warnings in 6.61s
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 100.0% de 372 líneas cambiadas cubiertas (372/372, umbral 80%, nivel critico)
[OK] Rama actual: feature/F-024-coherencia-cargas-truncadas
ENTORNO LISTO. Puedes trabajar.
```

Los dos `[AVISO]` son previos a este trabajo: `F-003` está `blocked` a propósito
hasta cerrar F-023, y los avisos de `ruff` son deuda declarada que no bloquea.
