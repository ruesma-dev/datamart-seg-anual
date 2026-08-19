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

---

# Segunda pasada · 2026-08-19, tras el review de cierre

`progress/review_F-023_F-003_cierre.md`: **F-023 APPROVED**, **F-003
CHANGES_REQUESTED** con cinco cambios. Tres eran míos (1, 2 y 5); los otros dos
—la ficha de F-026 y `progress/current.md`— los hace el líder, y no he tocado
`harness/features.json`, `BACKLOG.md` ni `progress/current.md`.

El reviewer confirma además el punto que dejé abierto en la primera pasada:
**ninguna de T23–T26 estaba marcada por inercia y no hay nada que desmarcar**.
El problema era el inverso, y es el cambio 1.

## Cambio 1 · Seis tareas con evidencia y sin marcar, más T28

Marcadas en `specs/F-003-infra-caj/tasks.md`, cada una con **qué se verificó**,
no solo un `[x]`. La evidencia es la tanda 1 del bloque 5
(`progress/current.md`, 2026-08-10). **No se ha ejecutado nada contra Azure**
para marcarlas: son apuntes de lo ya verificado.

| Tarea | Qué acredita la evidencia |
|---|---|
| T18 | `rg-datamart-seg-dev` con los 7 tags `acens-*` (`costcenter=pendiente`), Log Analytics PerGB2018 a 30 días, entorno **sin VNet** con logs a Log Analytics, `staticIp` anotada |
| T19 | Storage con los **tres** flags de R17 y contenedor `aux`; vault con RBAC y vacío; identidad con **exactamente 3 roles** de ámbito recurso |
| T20 | `SIGRID-API-FUNCTION-KEY` en el vault, comprobado **por nombre** (nunca `secret show`) |
| T21 | Imagen con **tag único y sin `latest`**, publicada sin credenciales de registro |
| T22 | Regla de firewall creada por el humano con autorización expresa; R23 pide «correcto si tras ello R22 pasa», y R22 pasó en T24 |
| T22 bis | Los dos secretos `pg-*` listados en el vault del proyecto, migrados sin exponer valores (lo único que R27 exige) |
| T28 | `bash harness/init.sh` hoy: **exit 0**, 617 passed, cobertura 100,0 % de 372 líneas |

Tres cosas que he dejado escritas en las tareas, porque marcarlas a secas habría
tapado información que ya costó dinero una vez:

- **T18 no lleva la `staticIp` escrita en la spec**, aunque la tarea pide
  «anotar la `staticIp`»: el repositorio no versiona direcciones IP. La tarea
  remite a `progress/current.md`, donde está, y dice por qué no está aquí.
- **T21 quedó obsoleta sola.** Su imagen (`r20260810-1024`) no es la que
  verificó T24: la tanda 2 reconstruyó (`r20260817-2025`) para incluir los fixes
  de T13. Está dicho en la tarea, en vez de dejar dos tags que no cuadran.
- **T22 bis anota que las copias viejas siguen vivas** en el vault de otro
  proyecto y que la condición de R27 —«que el job funcione»— ya se cumple, así
  que su borrado (bloque 1 de F-032) **toca decidirlo**. Es el aviso del
  reviewer, puesto donde se leerá al reabrir la tarea.

**Ninguna tarea se ha quedado abierta por falta de evidencia.** Las que siguen
en `[ ]` son T27 (exige contenido nuevo en `progress/current.md`, que es del
líder) y nada más.

## Cambio 2 · El comando de firewall que no ejecutaba

Corregido en los dos sitios copiables que pedía el reviewer:

- `infra/README.md`, paso 2 de «Pasos que exigen autorización expresa»
- `specs/F-003-infra-caj/requirements.md`, bloque de **R23**

De `create -g <grupo> -n <servidor> --rule-name <regla>` a
`create --resource-group <grupo> --server-name <servidor> --name <regla>`.
Fuente: `progress/manual_F-024_fase_c.md` (commit `7cc4fa1`), donde está
verificado que el servidor va en `--server-name`/`-s`, la regla en `--name`/`-n`
y que **`--rule-name` no existe** en la CLI del puesto.

Además de corregirlo, en los dos ficheros queda escrito **por qué**, porque un
comando arreglado sin explicación se vuelve a romper:

1. Los dos mensajes de error reales y lo que confunden: pasar el servidor en
   `--name` responde «the following arguments are required: --server-name/-s», y
   `--rule-name` responde «unrecognized arguments».
2. **La asimetría entre subcomandos, que es la trampa de verdad**: la línea del
   `firewall-rule list`, dos más abajo en el README, **está bien con
   `-n <servidor>`** porque `list` no recibe nombre de regla, así que ahí `-n`
   *sí* es el servidor. **No la he tocado**, y las dos correcciones dicen
   explícitamente que no se generalice el arreglo a `list`: quien «arregle» esa
   línea a `-s` la romperá. Es comportamiento de la CLI, no un descuido.
3. El `create` va **en una sola línea a propósito**: un backtick de continuación
   con un espacio detrás rompe el comando en PowerShell sin decir por qué.

### Dos sitios más con el mismo defecto, que NO he tocado

El barrido de `--rule-name` en el repositorio devuelve **dos apariciones más**,
las dos copiables, y ninguna estaba en el encargo:

- `docs/runbook_postgres_azure.md`, línea **181** (el `create` del runbook, con
  el mismo `-n <servidor> --rule-name`) y línea **201** (un
  `firewall-rule delete --rule-name <nombre>`, roto por el mismo motivo).
- `specs/F-005-postgres-azure/tasks.md`, **T16**, mismo `create`.

**Por qué no las he corregido, aunque el arreglo sea idéntico**: el reviewer
cierra diciendo que revisará «solo el diff de `tasks.md`, los dos ficheros del
comando y `current.md`». Un tercer y cuarto fichero entrarían sin que nadie los
mire, y uno de ellos es la spec de una feature ya cerrada. **Lo dejo señalado
con línea exacta**: el runbook es documento operativo vivo y su `create` y su
`delete` fallan igual que fallaba este; el de F-005 es histórico y molesta
menos. Decisión del líder, no mía.

## Verificación de esta pasada

`bash harness/init.sh` tal cual, **antes** de commitear: **exit 0**, **617
passed** en 5,95 s, `PUERTA COBERTURA [OK] 100.0% de 372 líneas cambiadas
(372/372, umbral 80%, nivel critico)`. Los dos `[AVISO]` siguen siendo los
preexistentes (`ruff` 152, deuda; y F-003 `blocked` a propósito). Ni una línea
de Python tocada en esta pasada tampoco: mutación no procede, cobertura sin
diferencias propias que medir.

Barrido propio antes de commitear: **ni una IP, ni un GUID, ni un correo, ni un
ID de suscripción o tenant** en los tres ficheros tocados. La `staticIp` del
entorno se menciona por su nombre de propiedad, nunca por su valor —ver T18—, y
la puerta `test_f003_r4_...` pasa en verde.
