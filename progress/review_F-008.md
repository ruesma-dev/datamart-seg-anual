<!-- progress/review_F-008.md -->
# Review F-008 · Documentación de referencia: tablas de Sigrid, landing zone de acens y sigrid-api

Fecha: 2026-08-08 · Rama revisada: `feature/F-008-docs-referencia-sigrid-acens`
Base de comparación: `dev` · Commits revisados: `e8cd88e`, `c8e90ea`,
`f8864a7`, `f61512c`
Feature `sdd=false`: se valida contra los `acceptance` de `harness/features.json`
y contra `CHECKPOINTS.md`.

## Veredicto

**CHANGES_REQUESTED**

El trabajo sustantivo está bien y verificado de forma independiente: los tres
documentos existen con su cabecera, los nombres siguen la convención, **no hay
ni un secreto ni un dato sensible** en ninguno de los tres, los PDF originales
no han entrado al repositorio ni al árbol de trabajo, y `bash harness/init.sh`
termina en verde. Los nueve criterios `acceptance` se cumplen.

Lo que bloquea el cierre es una sola cosa, barata de arreglar: **C2 —
`progress/current.md` contiene información obsoleta y contradictoria sobre la
propia F-008**, además de un resto de la sesión de F-001. Es exactamente el
fallo que el fichero de memoria existe para evitar. Son cuatro líneas en un
único fichero; corregidas, esta feature es APROBADA sin más cambios.

## Checkpoints (C1–C5)

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0. Ejecutado por mí:
      22 tests pasan, `features.json` válido, rama correcta, un único
      `in_progress` (F-008). Único aviso: `ruff` con 122 avisos, deuda previa
      declarada como no bloqueante por el propio `init.sh`.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress` (F-008).
- [x] Rama actual `feature/F-008-docs-referencia-sigrid-acens`, nunca `main`.
- [ ] **`progress/current.md` describe SOLO la sesión activa.** NO se cumple.
      Ver «Cambios requeridos» 1, 2 y 3.
- [x] F-001, única feature `done`, tiene su resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones

- [x] Dominio sin imports de infraestructura, SQL en su capa: **N/A**. La rama
      no toca ni una línea de Python ni de SQL. Diff completo: 3 documentos de
      referencia, `docs/referencia/README.md`, `CLAUDE.md`, dos ficheros de
      `.claude/agents/`, `harness/features.json` y dos ficheros de `progress/`.
      Ningún fichero fuera de lo previsto por los `acceptance`, salvo los
      cambios de reglas del arnés, que el humano pidió en la misma sesión y
      quedan justificados en `progress/impl_F-008.md` §«Regla nueva del humano».
- [x] Primera línea con la ruta relativa: verificada en los cinco Markdown
      nuevos o modificados (`docs/referencia/01_sigrid_tablas.md:1`,
      `02_azure_landing_zone_acens.md:1`, `03_sigrid_api.md:1`,
      `README.md:1`, `progress/impl_F-008.md:1`).
- [x] Sin `print()` de debug, sin TODOs sin contexto, **sin secretos
      hardcodeados**, sin dependencias nuevas. Detalle del barrido de secretos
      en la sección siguiente.
- [x] Semántica Sigrid (amb/fas, `importe_origen`/`importe_mes`, `fasnum`):
      **N/A**, no hay lógica de negocio en la rama.

### C4 — La verificación es real

- [x] Requisitos EARS con test trazable: **N/A**. `sdd=false` y feature
      exclusivamente documental; ninguno de los nueve `acceptance` es
      verificable con pytest. La verificación real de esta feature es la
      inspección del contenido, que consta en la tabla de cobertura de abajo.
- [x] Los unit tests no tocan red ni BBDD. La suite (22 tests) no se ha
      modificado y sigue en verde.
- [x] Verificaciones `MANUAL (humano)` listadas en `current.md`: no se declaró
      ninguna. Ver «Observación sobre el criterio de `markitdown`» abajo: es el
      único punto que no he podido comprobar mecánicamente, y considero la
      evidencia circunstancial suficiente.

### C5 — La sesión se cerró bien

- [x] `tasks.md` con tareas `[x]` y un commit por tarea: **N/A** en su primera
      mitad, porque `sdd=false` y no hay `specs/F-008-*/tasks.md`. Sobre la
      convención de mensajes de commit, ver «Observaciones» punto O1: hay
      desviación respecto a `.claude/agents/implementer.md`, pero no la trato
      como bloqueante y explico por qué.
- [x] Sin ficheros temporales ni artefactos sin trackear.
      `git status --porcelain --untracked-files=all` devuelve vacío.
- [x] `features.json` refleja el estado real: F-008 en `in_progress`, a la
      espera de este veredicto. Las prioridades de F-002 y F-007 se
      reajustaron a 7 y 8 al insertar F-008 en 6, sin dejar huecos ni empates.

## Barrido de datos sensibles (hecho por mí, no leído del informe)

Búsquedas ejecutadas sobre `docs/referencia/` completo, no sobre el informe:

| Qué busqué | Patrón | Resultado |
|---|---|---|
| Direcciones IP | `\b(\d{1,3}\.){3}\d{1,3}\b` | 1 coincidencia: `docs/referencia/03_sigrid_api.md:134`, `127.0.0.1:11433`. Es loopback de un túnel de desarrollo local: **no es una IP interna ni revela topología**. Aceptable. |
| Correos electrónicos | `[\w.%+-]+@[\w.-]+\.\w{2,}` | **Cero coincidencias** en los tres documentos. Los dos destinatarios de alertas de acens están sustituidos por `<correo-alertas-1>` / `<correo-alertas-2>`. |
| GUID (suscripción, tenant, client id) | `[0-9a-f]{8}-[0-9a-f]{4}-...` | **Cero coincidencias** en los tres documentos. |
| Credenciales y tokens | `password\|secret\|api.key\|token\|subscription\|tenant\|connection string\|AccountKey\|Bearer` | En `02`: cero. En `03`: solo **nombres** de variables y de secretos (`SQL_SERVER_PASSWORD`, `sigrid-password`, `@Microsoft.KeyVault(VaultName=...;SecretName=...)`), nunca un valor. La function key se obtiene con `az functionapp keys list` (`03_sigrid_api.md:206`), no está escrita. |
| Cadenas largas tipo clave/base64 | `[A-Za-z0-9+/=]{32,}` | Solo nombres de fichero del árbol de directorios del repo `sigrid-api` (`03_sigrid_api.md:70-73`). Ningún material criptográfico. |
| URLs, rutas UNC, rutas Windows, dominios de la empresa en el diccionario de Sigrid | `https?://`, `\\\\host\\`, `C:\\`, `ruesma\.`, `\.es\b` | **Cero coincidencias** en `01_sigrid_tablas.md`. Es esquema puro: códigos de tabla, descripciones y tipos. |

Marcadores de redacción presentes y coherentes con lo declarado en cabecera:
15 ocurrencias de `<RANGO-*>` / `<SUBRED-*>` / `<RED-SEDE-CLIENTE>` /
`<correo-alertas-*>` en `02`, y 5 de `<ID-SUSCRIPCION>` / `<HOST-SQL-ONPREM>` /
`<PUERTO>` en `03` (líneas 128, 133 y 261, además de las dos de cabecera).

Sobre los nombres de recursos que `03` **sí** conserva
(`func-sigridapi-dev-huyke`, `kv-sigridapi-dev-huyke`, `rg-sigrid-dev-data-api`):
he comprobado que **ya estaban en el repositorio antes de esta rama**, en
`infra/30_create_job.ps1:19` y en `README.md:714`. El documento no introduce
ningún identificador operativo nuevo, así que la decisión de mantenerlos ni
empeora la exposición actual ni contradice ninguna regla dura.

Un apunte que no es un hallazgo pero conviene no confundir: en
`docs/referencia/01_sigrid_tablas.md:36` aparece una fila `cla | Password |
Texto de 255 caracteres`. Es la **definición de columna** de la tabla `ABcue`
del sistema origen, no una credencial.

### Originales fuera del repositorio

- `git ls-tree -r HEAD` no contiene ningún `.pdf`, `.doc(x)`, `.xls(x)` ni
  `.ppt(x)`.
- `git log dev..HEAD --diff-filter=A` tampoco: ningún original entró y salió.
- `find` sobre el árbol de trabajo (excluyendo `.git`): cero ficheros de esos
  tipos.
- `git status --porcelain -uall`: vacío, o sea que tampoco hay un original sin
  trackear esperando a colarse en el próximo `git add .`.

## Cobertura: criterio `acceptance` → evidencia

| # | Criterio | Evidencia | Estado |
|---|---|---|---|
| 1 | PDF convertidos con la herramienta MCP `markitdown`, no transcritos a mano | Cabeceras de `01:6` y `02:6`. Evidencia circunstancial fuerte: 21.977 líneas, la cabecera de página del PDF repetida 382 veces y columnas pegadas — artefactos propios de una extracción automática, imposibles en una transcripción manual. Ver observación abajo | Cumplido |
| 2 | `01_sigrid_tablas.md` con cabecera de origen y fecha | Líneas 1-7: ruta, origen `tablas_sigrid.pdf` con versión y nº de páginas, fecha del documento 2024-11-06, fecha de conversión 2026-08-08, mención a que el original queda fuera | Cumplido |
| 3 | `02_azure_landing_zone_acens.md` con la misma cabecera | Líneas 1-17: origen, fecha 2026-03-25, conversión 2026-08-08, más dos bloques añadidos (confidencialidad de acens y detalle de lo redactado) | Cumplido |
| 4 | `03_sigrid_api.md` con la misma cabecera | Líneas 1-15: origen, fecha 2026-06-07, fecha de incorporación, y por qué no pasó por `markitdown` (llegó ya en Markdown). Desviación explícita y justificada respecto a la plantilla de `README.md:44-50`, que solo prevé el caso «convertido» | Cumplido |
| 5 | Nombres conformes a `NN_tema.md` | `01_sigrid_tablas.md`, `02_azure_landing_zone_acens.md`, `03_sigrid_api.md`: numeración correlativa sin huecos y tema en `snake_case`, como exige `docs/referencia/README.md:36-37` | Cumplido |
| 6 | Los PDF originales no entran en el repositorio | Cuatro comprobaciones independientes, detalladas arriba | Cumplido |
| 7 | Sin secretos ni datos sensibles; lo redactado, anotado | Barrido completo arriba: cero correos, cero GUID, cero IP internas, cero valores de credencial. Lo redactado está anotado en la cabecera de `02` (líneas 14-17) y de `03` (líneas 9-15), y resumido en `README.md:25-26` | Cumplido |
| 8 | `README.md` menciona los documentos nuevos | `docs/referencia/README.md:20-26`: índice con los tres, incluida la marca **Versión redactada** en los dos que lo son | Cumplido |
| 9 | `bash harness/init.sh` en verde | Ejecutado por mí: exit 0 | Cumplido |

## Coherencia de las reglas nuevas (`CLAUDE.md`, `leader.md`, `implementer.md`)

Revisadas las tres piezas juntas. **No contradicen ninguna regla dura
existente** y encajan entre sí:

- Las dos paradas de `CLAUDE.md` §«Ritmo de trabajo con el humano» tienen su
  contrapartida exacta en `leader.md`: PARADA 1 en las filas `pending`
  (`sdd=false`) e `in_progress`, PARADA 2 en la fila «revisión OK». No queda
  ningún camino del flujo por el que se implemente sin PARADA 1 ni se cierre
  sin PARADA 2.
- La fila `spec_ready` no necesitaba tocarse: ya paraba para aprobación humana,
  y PARADA 1 dispara al pasar a `in_progress`. Coherente.
- La fila «revisión KO» relanza al implementer sin parada, y al tercer ciclo
  marca `blocked`. Coherente con `CLAUDE.md`, que solo obliga a volver a la
  PARADA 1 cuando la propuesta *confirmada* se revela incorrecta, no cuando
  falla la ejecución de un plan válido.
- PARADA 2 dice explícitamente «lo construyes leyendo los informes, **no
  reenviándolos**». Eso **refuerza** la regla dura ANTI TELÉFONO-DESCOMPUESTO
  en vez de erosionarla, que era el riesgo evidente de pedir resúmenes por
  chat. Bien resuelto.
- El añadido a `implementer.md` (líneas 34-39) solo cambia *cómo se escribe* el
  informe, no *qué* se responde por chat: la respuesta de una línea sigue
  intacta más abajo. Sin conflicto.
- La excepción de solo lectura (`CLAUDE.md`: ejecutar `init.sh`, leer, buscar)
  es necesaria y no choca con el protocolo obligatorio, que empieza justamente
  por ejecutar `init.sh` antes de cualquier trabajo.

Única fricción de redacción, **no bloqueante**, apuntada como propuesta P3
abajo: `CLAUDE.md` §«Autorización permanente de subagentes» dice «No hace
falta pedir permiso feature a feature» y la sección nueva dice «espera
confirmación del humano antes de escribir nada». Hablan de cosas distintas
—permiso para usar la herramienta Agent frente a aprobación del plan— pero
están a diez líneas una de otra y un lector apresurado puede leerlas como
contradictorias.

## Cambios requeridos

Todos en `progress/current.md`. Ninguno afecta al contenido de la feature.

1. **`progress/current.md:16-18`** — «F-008 no puede arrancar hasta que el
   humano entregue las rutas locales de los dos PDF; la conversión se hará con
   la herramienta MCP `markitdown`». Es **falso a día de hoy** y contradice
   directamente a las líneas 4-8 del mismo fichero, que dicen que los
   documentos ya están convertidos y commiteados. Una sesión que retomara el
   trabajo leyendo este fichero recibiría dos estados incompatibles de la misma
   feature. Reescribir el párrafo en pasado o eliminarlo.

2. **`progress/current.md:5`** — «Los **dos** documentos ya están convertidos y
   commiteados (`e8cd88e`, `c8e90ea`)» y, en el mismo sentido,
   **`progress/current.md:14-16`**, que titula F-008 como «tablas de Sigrid y
   landing zone de acens». Los documentos son **tres**: falta
   `03_sigrid_api.md`, añadido en `f61512c`, que además es el que cambia el
   título y la descripción de la feature en `features.json`. El fichero de
   memoria se quedó en la foto anterior al tercer commit. Actualizar el
   recuento, el commit `f61512c` y el título.

3. **`progress/current.md:10-12`** — «F-001 cerrada el 2026-08-08… Siguiente
   por prioridad: F-004…» es un resto de la sesión de F-001, que C2 prohíbe
   expresamente («sin restos de sesiones anteriores»). El cierre de F-001 ya
   está donde corresponde, en `progress/history.md`. Eliminar o reducirlo a la
   línea de «siguiente por prioridad», que sí describe el estado activo.

Hecho esto, no hace falta volver a ejecutar nada más que `bash harness/init.sh`
y este servidor puede reemitir veredicto sin repetir el barrido de secretos.

## Observaciones (no bloquean)

**O1 · Convención de mensajes de commit.** Los cuatro commits de la rama usan
`docs(F-008): …`, mientras que `.claude/agents/implementer.md` §Protocolo punto
2 exige `F-XXX Tn: <descripción corta>`, y F-001 —la otra feature `sdd=false`,
ya aprobada— sí lo siguió (`F-001 T1:`, `F-001 T2:`, `F-001 T3:`). No lo trato
como bloqueante por tres razones: C5 condiciona ese requisito a las tareas de
un `tasks.md` que aquí no existe; la trazabilidad al identificador de la
feature se conserva en los cuatro mensajes; y arreglarlo exigiría reescribir
historia por un asunto de forma. Queda anotado para que el humano decida y para
que no siente precedente por descuido. Ver propuesta P2.

**O2 · El criterio de `markitdown` no es verificable a posteriori.** Sin el PDF
original —que, correctamente, no está en el repositorio— ningún reviewer puede
demostrar que la conversión se hizo con la herramienta y no a mano. Lo doy por
cumplido porque la forma de la salida solo se explica por una extracción
automática (382 cabeceras de página repetidas, columnas pegadas, 21.977 líneas)
y porque la herramienta MCP `markitdown` está efectivamente conectada en este
entorno. Es una comprobación basada en indicios, y quiero que conste como tal.

**O3 · La feature la ejecutó el líder sin delegar en el `implementer`.**
Documentado en `progress/impl_F-008.md:126-129`. `CLAUDE.md` §«Autorización
permanente de subagentes» prevé este caso y exige dos cosas: decirlo en el
primer mensaje al humano y mantener el rastro documental en `progress/`. Lo
segundo se cumple de sobra. Lo primero no me consta verificable desde aquí.
Sin efecto sobre el resultado de F-008, pero el desajuste entre lo que dice
`CLAUDE.md` y lo que hace la sesión conviene resolverlo con el humano en vez de
dejarlo escrito en cada informe.

**O4 · Cabecera de `03` frente a la plantilla del README.** `README.md:44-50`
solo contempla la línea «Convertido a Markdown el AAAA-MM-DD». `03` la sustituye
por «Incorporado a `docs/referencia/` el …» porque no hubo conversión. Es la
decisión correcta —mentiría al escribir «convertido»—, pero la plantilla del
README debería recoger el caso de los documentos que ya llegan en Markdown.
Ver propuesta P4.

## Automejora (propuestas, no aplicadas)

**P1 · `.gitignore` no protege contra los originales.** El acceptance 6 se
cumple hoy por disciplina, no por mecanismo: nada impide que un `git add .`
con un PDF suelto en el árbol lo versione, y una vez dentro sale caro. Propongo
añadir a `.gitignore` un bloque `*.pdf`, `*.docx`, `*.xlsx`, `*.pptx` con el
comentario «originales de `docs/referencia/`: al repo entra solo el Markdown».
Convierte una regla dura de `CLAUDE.md` en algo que la herramienta hace cumplir
sola.

**P2 · `CHECKPOINTS.md` no dice qué hacer con `sdd=false`.** C4 (requisitos
EARS) y C5 (`tasks.md` y commits `F-XXX Tn:`) están escritos suponiendo que hay
spec. Con `sdd=false` el reviewer tiene que interpretar qué es N/A y qué sigue
aplicando, y esa interpretación no debería quedar a criterio de cada revisión.
Propongo una línea en la cabecera de C4 y C5: «Si `sdd=false`, léase
`acceptance` donde dice requisito EARS, y `F-XXX: <descripción>` como formato
mínimo de commit; el resto del checkpoint es N/A». Esto habría cerrado la
duda O1 sin necesidad de opinión.

**P3 · Fricción aparente en `CLAUDE.md`.** Añadir al final de §«Autorización
permanente de subagentes» una frase del tipo «Esta autorización cubre el uso de
la herramienta Agent, no la aprobación del plan: la PARADA 1 de la sección
siguiente sigue siendo obligatoria». Dos líneas que evitan que un agente futuro
resuelva la ambigüedad en la dirección cómoda.

**P4 · Plantilla de cabecera en `docs/referencia/README.md`.** Añadir una
segunda variante para los documentos que ya llegan en Markdown («Incorporado a
`docs/referencia/` el AAAA-MM-DD. Llegó ya en Markdown: no requirió
`markitdown`»), y una tercera línea opcional «**Redactado.** …» para los que
llevan material sustituido. Las tres ya existen de hecho en los ficheros de
esta feature; solo falta elevarlas a convención.

**P5 · Un checkpoint para features documentales.** `CHECKPOINTS.md` no tiene
ningún criterio sobre documentos que entran de fuera, aunque `CLAUDE.md` ya
regula su conversión. Propongo un C3 bis: «Todo documento nuevo en
`docs/referencia/` lleva cabecera con origen y fecha, y ha pasado un barrido de
secretos (correos, IP, GUID, credenciales) cuyo resultado consta en el informe
de review». En esta revisión he tenido que inventarme el barrido; la próxima no
debería depender de que al reviewer se le ocurra.
