<!-- progress/review_F-023_F-003_cierre.md -->
# Review de cierre · F-023 y F-003

Fecha: 2026-08-19. Rama revisada: `feature/F-024-coherencia-cargas-truncadas`
(HEAD `aa2f39d`). Sin tocar Azure: ninguna lectura, ninguna escritura.
Sin lanzar campañas de mutación (sí recálculos puros, que no ejecutan la suite).

## Veredicto

| Feature | Veredicto | Puede pasar a `done` |
|---|---|---|
| **F-023** | **APPROVED** | Sí, **después** de F-003 (su acceptance nº 6 lo exige) |
| **F-003** | **CHANGES_REQUESTED** | No: cinco cambios, todos concretos y baratos |

Ninguno de los cambios que pido a F-003 es trabajo de ingeniería nueva: son
cuatro apuntes de evidencia que ya existe y **un defecto real en un comando
copiable** que el propio repositorio dejó anotado «para la vuelta de F-003».
Esta es esa vuelta.

## Entorno

`bash harness/init.sh` ejecutado tal cual: **exit 0**. 617 passed en 7,14 s.
`PUERTA COBERTURA [OK] 100.0% de 372 líneas cambiadas (372/372, umbral 80%,
nivel critico)`. Dos `[AVISO]` preexistentes y declarados: `ruff` 152 (deuda) y
«hay features en estado blocked» (F-003, a propósito).

---

# Nivel de rigor con el que juzgo cada una

## F-023: la juzgo como `critico`, no como el `estandar` que declara

Tres motivos, en orden de peso:

1. **El humano lo decidió y el fichero no lo recogió.** Un nivel declarado que
   contradice la decisión del humano es **peor que no declarar nivel**: la regla
   de omisión aplica `critico` por defecto, mientras que un `estandar` escrito
   baja la vara en silencio para quien reabra la feature dentro de tres meses y
   lea el JSON en vez de esta conversación.
2. **Por contenido, es `critico` por definición.** La tabla de `CHECKPOINTS.md`
   reserva ese nivel para «infraestructura compartida, producción, seguridad o
   dinero». F-023 verifica identidad gestionada y RBAC sobre una cuenta de
   almacenamiento, y su prueba negativa toca —en lectura— un recurso de otro
   proyecto. Es exactamente el supuesto.
3. Mi protocolo manda aplicar el más exigente ante la duda.

Qué cambia en la práctica juzgarla en `critico` y no en `estandar`: **solo dos
cosas**, y las dos se cumplen. Cero supervivientes sin justificación aceptada
(los dos de la campaña vigente están aceptados por el humano por escrito) y
verificaciones `MANUAL (humano)` con su comando exacto y su resultado real
(`progress/manual_F-023.md` las trae las tres, con salida pegada). Es decir: el
nivel equivocado en el fichero **no le ha ahorrado ninguna puerta** a esta
feature. Pero hay que corregirlo (apunte de cierre 1).

## F-003: `critico`, como declara

Exige todo lo de `estandar` + cero supervivientes + verificaciones MANUAL con
comando exacto y resultado real. **Es precisamente ahí donde falla**: el comando
exacto de T22 no funciona como está escrito (cambio requerido 2).

---

# Los tres puntos donde pediste criterio

## 1 · La «desviación» de la verificación 3 no es una desviación

**Fui a leer el requisito original en vez de la paráfrasis, y ahí está la
respuesta.** `specs/F-004-etl-sin-dependencias-locales/requirements.md`,
sección «Verificaciones que NO puede cubrir un test automático», punto 3, dice
literalmente:

> «Comprobación de que el mensaje de error de permisos es útil de verdad:
> **ejecutar sin el rol asignado** y leer el log.»

**El requisito nunca pidió quitar el rol y reasignarlo.** Pidió ejecutar *sin el
rol asignado*, que es exactamente lo que se hizo: apuntar a una cuenta sobre la
que el rol no está asignado. El «quitar y devolver» aparece en la paráfrasis de
la ficha de F-023, no en el requisito de F-004. Así que lo ejecutado **cumple el
acceptance en su literalidad**, y la desviación lo es respecto de una redacción
posterior más estricta que la original, no respecto del requisito.

Tu valoración es correcta, y añado la verificación técnica que la sostiene —hecha
contra el código, no leída del informe:

- `etl_sigrid/infrastructure/excel/blob_aux_file_source.py`, `_traducir()`:
  **una sola rama** para los fallos de acceso, disparada por
  `CODIGOS_DE_ACCESO = frozenset({401, 403})` o por nombre de clase. El mensaje
  se construye con `ref.account`, `ref.display` y `ref.env_var`, **los tres
  derivados de la URI**. No existe ninguna bifurcación que dependa de *qué*
  cuenta es, ni de si la asignación existió antes y se retiró.
- Azure evalúa RBAC **por petición**: «rol nunca asignado» y «rol retirado hace
  un minuto» devuelven el mismo `AuthorizationPermissionMismatch` 403. No hay
  un código distinto para una asignación revocada. Los dos escenarios son
  indistinguibles para el ETL por construcción, no por suerte.
- `tests/test_f004_r10_error_de_permisos_menciona_el_rol_y_las_dos_salidas`
  parametriza 403, 401 y `ClientAuthenticationError` contra ese mismo mensaje —
  **y lo hace nombrando la cuenta propia** (`assert "stdatamartsegdev" in
  mensaje`).

**Respuesta a tu duda concreta**: la laguna que señalas —que no se demuestra
que la pérdida del rol *sobre la cuenta propia* produzca ese mensaje— **no hay
que cerrarla**, y no porque sea poca cosa, sino porque está cubierta por las dos
mitades juntas. La diferencia entre los dos escenarios se reduce al valor de
`ref.account`; la prueba manual aporta el 403 real de Azure sobre otra cuenta, y
el test automático aporta el mismo camino de código con el nombre de la cuenta
propia. Lo único que ninguna de las dos demuestra es que Azure devuelva 403 tras
una retirada de rol, y eso es comportamiento de Azure, no de este repositorio:
no es nuestro sistema bajo prueba.

**Añado una cuarta ventaja a las tres tuyas**, porque refuerza el argumento: el
procedimiento original tiene un **modo de falso negativo** que el sustituto no
tiene. F-026 documenta que RBAC no propaga de inmediato en esta suscripción
(`60_create_identity.ps1` lanza un `throw` falso por consultar demasiado
pronto). En el guion original, la reasignación podría *parecer* fallida estando
bien, o el 403 podría seguir apareciendo un rato después de devolver el rol. Se
habría depurado propagación en vez de verificar un mensaje.

**Un matiz, sin consecuencias**: la prueba negativa se ejecutó contra
`stalbaranesrs9k2`, un recurso de *albaranes*. Fue **solo lectura** —un `list`
que dio 403 y tres descargas que dieron 403—, encaja en «contra sistemas
ajenos, solo lecturas» y no dejó estado. La decisión del implementer de **no
nombrar esa cuenta en `infra/README.md`** (sí en la evidencia) es correcta: en
documentación de infraestructura habría parecido una dependencia que no existe.
Valía cualquier cuenta sin el rol, y así está escrito.

## 2 · Las tareas de F-003: el implementer tenía razón. **No hay nada que desmarcar**

Verifiqué las cuatro contra `progress/current.md` §«Tanda 2 EJECUTADA el
2026-08-17», una por una:

| Tarea | Evidencia que le corresponde | ¿Coincide? |
|---|---|---|
| T23 crear el job | job `caj-datamart-seg-dev` creado y programado `0 2 * * *` UTC; cuatro intentos y el bug de `$TAG` en `00_vars.ps1` corregido en `19f51a3` | Sí |
| T24 ejecución + build | ejecución `Succeeded` (`...-41p0exu`); `version` coincide con el tag desplegado; hallazgo de los `--args` pegados | Sí |
| T25 logs | KQL en verde; columna real `ContainerJobName_s`, no `ContainerAppName_s` | Sí |
| T26 alerta + correo | fallo 20:46:24 → correo 20:51:58 = **5 min 34 s**, dentro de los 15 min de R25; DA-3 resuelta | Sí |

**Confirmo tu instinto invertido: el problema es el contrario del que temías.**
Ninguna tarea marcada está marcada por inercia. Lo que hay son **seis tareas sin
marcar cuya evidencia ya existe**: T18, T19, T20, T21, T22 y T22 bis, todas
documentadas con resultado verificado en `progress/current.md` §«Tanda 1 del
bloque 5 · EJECUTADA por el humano el 2026-08-10» (resource group con sus 7
tags, Log Analytics, entorno sin VNet con su `staticIp`, regla de firewall,
storage con los tres flags de R17, vault con los tres secretos incluido el paso
8 bis, identidad con exactamente 3 roles de ámbito recurso, imagen con tag único
sin `latest`).

Para T22 bis lo comprobé contra la letra de **R27**, que exige solo que
`az keyvault secret list` liste los dos nombres: la tanda 1 lo registra. Y hay
una **segunda prueba independiente** de que T22 y T22 bis funcionaron:
`80_create_job.ps1` aborta si el secreto no está en el vault del proyecto, y el
job se creó y ha ejecutado correctamente contra Postgres. Ninguna de las dos
cosas es posible si alguna de esas dos tareas hubiera fallado.

Dos detalles menores, ambos bien resueltos y sin defecto:

- El bloque V1–V3 añadido aparte, en vez de renumerar tareas de la spec, es la
  decisión correcta: esas verificaciones se ejecutaron en F-023, no en F-003.
- La verificación de T24 pide que `version` coincida «con el tag de T21», y lo
  que coincidió fue el tag de la imagen **reconstruida en la tanda 2**
  (`r20260817-2025`), porque la de T21 (`r20260810-1024`) quedó obsoleta.
  `tasks.md` dice «el tag desplegado», que es la redacción honesta. Correcto.

## 3 · Sí, F-003 puede cerrarse habiéndole quitado trabajo a F-023 (con un aviso)

Lo verifiqué **requisito a requisito**, no leyendo la ficha: barrí
`specs/F-003-infra-caj/requirements.md` buscando `hosts`, `firewall`, `puesto`,
`kv-albaranes`, «copias viejas» y «borra». Resultado:

- **Ninguno de los dos bloques de F-032 es requisito de F-003.** La única
  mención a las copias viejas está dentro de **R27**, y es una cláusula de
  **orden** («las copias viejas no se borran hasta que el job funcione»), no una
  obligación de borrarlas. La verificación que R27 declara es solo que el vault
  del proyecto liste los dos nombres — cumplida.
- La línea de `hosts`, las reglas de firewall **del puesto**
  (`datamart-puesto-pgris-*`) y `SIGRID_API_PAGE_SIZE` **no aparecen en ningún
  requisito de F-003**. El requisito de firewall de F-003 es **otra regla**: la
  de la IP estática de salida del entorno (R23, T22), y su verificación es
  «correcto si tras ello R22 pasa» — R22 pasó.

**Conclusión: mover limpieza operativa a F-032 para desbloquear es legítimo aquí,
porque no retira ninguna condición de F-003.** No es un cheque en blanco para
futuras extracciones: lo es porque se comprobó que esos bloques no estaban
requeridos.

**El aviso.** La cláusula de R27 hacía el borrado *condicional* a que el job
funcionara, y el job ya funciona: el bloque 1 de F-032 pasa de «todavía no toca»
a «toca y se debe». Con prioridad 20 puede quedarse meses ahí, y lo que queda
mientras tanto son **dos copias vivas de contraseñas de Postgres en el vault de
otro proyecto**. No es motivo para no cerrar F-003, pero sí para no dejar que
F-032 se enfríe: o subes la prioridad del bloque 1 por separado, o aceptas por
escrito que las copias se quedan. Decisión tuya; solo que sea decisión y no
olvido.

---

# Checkpoints

Leyenda: `[x]` cumplido · `[ ]` vacío (bloquea) · `N/A` no aplica, con motivo.

## F-023

- **C1** `[x]` — `init.sh` exit 0; los siete ficheros del arnés existen.
- **C2** `[x]` con **una desviación justificada** — Una sola feature
  `in_progress` (F-023). `history.md` sin resumen de F-023 todavía: es apunte de
  cierre, no defecto. **Desviación**: la rama actual es la de F-024, no
  `feature/F-023-cierre-operativo-f003` (que existe, `a9fd908`, pero quedó
  atrás). Está declarado por escrito en la cabecera de `manual_F-023.md` y fue
  deliberado. **Tiene un coste que conviene saber** (ver «Hallazgos», nº 3): con
  el trabajo en la rama ajena, `harness.alcance` mide **cero líneas** para
  F-023, así que las puertas de cobertura y mutación, invocadas
  `--feature F-023`, no medirían nada y saldrían verdes por vacío.
- **C3** `[x]` — Los cuatro commits de F-023 de hoy (`859e3ed`, `b88b8a6`,
  `aa2f39d`, `bddc8c2`) **no tocan una línea de Python**: solo `BACKLOG.md`,
  `harness/features.json`, `progress/*`, `infra/README.md` y
  `specs/F-003-infra-caj/tasks.md`. Nada de arquitectura que romper. Barrido de
  datos sensibles ejecutado **por mí** sobre los cuatro ficheros de contenido
  (`infra/README.md`, `specs/F-003-infra-caj/tasks.md`,
  `progress/manual_F-023.md`, `progress/impl_F-023_documentacion.md`) con
  patrones de IPv4, GUID, correo y `password|pwd|secret|key=`: **cero
  coincidencias**. La afirmación del implementer se sostiene.
- **C3 bis** `N/A` — **motivo**: no se añade ni modifica ningún fichero de
  `docs/referencia/`.
- **C4** `[x]` con N/A justificado — Los criterios `acceptance` de F-023 son
  verificaciones **MANUAL contra Azure**: no admiten test automático (es
  literalmente por eso que F-004 las dejó pendientes en su sección
  «Verificaciones que NO puede cubrir un test automático»). `N/A` justificado
  por naturaleza del criterio, no por omisión. Las tres están listadas con
  comando exacto y salida real en `progress/manual_F-023.md`, que es lo que
  `critico` exige. Los unit tests no tocan red ni BBDD (los de blob usan doble
  inyectado; el SDK no se parchea nunca).
- **C4 bis** `[x]`, con la fase RED **producida por mí** (detalle abajo).
  - Nivel declarado: `estandar`; nivel aplicado: `critico`, por escrito arriba.
  - **Fase RED** `[x]` — Ver «La fase RED que faltaba».
  - **Cobertura** `[x]` — `[OK] 100.0% de 372 líneas (372/372)`. Las 372 son de
    F-024, como el implementer dijo honestamente; el cambio de hoy no toca
    Python.
  - **Mutación** `[x]` con verificación independiente — Recalculé el alcance con
    `harness.alcance` y los mutantes con `harness.mutacion.generar_mutantes`
    (cálculo puro, sin ejecutar la suite): **108 mutantes**, exactamente el
    total de `progress/mutacion_F-024.md`, con el desglose por fichero
    consistente. Los dos supervivientes son de `main.py` (`bold=True→False` en
    cabeceras decorativas), con análisis completado y **aceptado por el humano**
    el 2026-08-18: ninguno en `PENDIENTE`, cero supervivientes sin justificar
    como exige `critico`.
  - **Evidencias** `[x]` — La sección existe en
    `progress/impl_F-023_documentacion.md` con los cuatro números, y el cuarto
    («no se lanzó campaña, y no procede») está declarado, no omitido.
- **C4 ter** `N/A` — **motivo**: no existe `harness/rutas_sensibles.json` en
  este repositorio, que es el caso mayoritario y explícitamente no exige
  justificación.
- **C5** `[x]` con N/A justificado — `tasks.md`: `N/A`, **motivo**: F-023 es
  `sdd=false` y no tiene `specs/F-023-*/`. Commits con formato
  `F-023: <descripción>`, el mínimo que la nota de cabecera de `CHECKPOINTS.md`
  pide para `sdd=false`. Árbol de trabajo **limpio**: `git status --porcelain`
  sin salida (los `huella_*.csv` que veías están cubiertos por `.gitignore:27`).
  `features.json` refleja el estado real salvo el campo `rigor`, que es el
  apunte de cierre 1.

**F-023 no tiene ningún checkbox vacío.** Su único impedimento para `done` es
externo: el criterio nº 6 de su propio `acceptance` exige que F-003 esté `done`,
y F-003 todavía no puede.

## F-003

- **C1** `[x]` — exit 0.
- **C2** `[x]` con dos notas — `history.md` sin resumen de F-003 (apunte de
  cierre). `progress/current.md` tiene una contradicción interna: la línea 613
  dice «**DA-3**, sigue abierta» mientras la tanda 2, más abajo, la da por
  resuelta. Va en el cambio requerido 4.
- **C3** `[x]` — F-003 no aporta código nuevo en esta pasada; su re-review
  APPROVED del 2026-08-10 cubre T1–T17 (`progress/review_F-003.md`).
- **C3 bis** `N/A` — **motivo**: no toca `docs/referencia/`.
- **C4** **`[ ]` VACÍO** — Es el que bloquea. Tercer punto: «las verificaciones
  `MANUAL (humano)` están listadas con su **comando exacto**». El comando de T22
  —en `infra/README.md:149-150` y en R23 de `requirements.md`— **no ejecuta**:
  pasa el servidor en `-n` y nombra la regla con `--rule-name`, y en esta CLI el
  servidor va en `--server-name`/`-s` y la regla en `--name`/`-n`, mientras
  `--rule-name` **no existe**. No es una sospecha mía: está verificado y escrito
  en `progress/manual_F-024_fase_c.md` (commit `7cc4fa1`), y `current.md` ya lo
  listaba entre los defectos «anotados sin corregir aún (**para la vuelta de
  F-003**)». Además, T27 pide el resultado de cada verificación MANUAL **en
  `current.md`**, y las tres de F-004 viven solo en `manual_F-023.md`.
- **C4 bis** `[x]` — Nivel `critico` declarado y correcto. Puertas heredadas de
  la pasada de código (T1–T17) con su review APPROVED; el alcance vivo de
  `config/settings.py` está dentro de la campaña que verifiqué (108/106/2, cero
  supervivientes en ese fichero).
- **C4 ter** `N/A` — **motivo**: sin `harness/rutas_sensibles.json`. Lo anoto
  como propuesta de mejora abajo, porque F-003 es justo la feature que lo
  querría.
- **C5** **`[ ]` VACÍO** — `tasks.md` con **ocho** tareas sin marcar: T18, T19,
  T20, T21, T22, T22 bis, T27 y T28. Las seis primeras tienen evidencia real y
  solo les falta el apunte; T27 exige contenido nuevo en `current.md`; T28 está
  en verde hoy y solo falta marcarla.

---

# La fase RED que faltaba (la produje yo, en copia aislada)

F-023 tiene **un commit de código de producción** que no aparece en ningún
informe: `193fc3c` (2026-08-18), `config/settings.py` +13/−1 más
`tests/test_f023_timeout_sigrid_api.py`, el techo de 230 s de `sigrid-api` que
tumbó las 31 tablas la primera noche del job. No existe `progress/impl_F-023.md`
y por tanto **no había traza RED**, que `critico` exige. Con `estandar` o con
`critico`, ese checkbox estaba vacío.

En vez de pedirla —una traza RED no se puede reconstruir a posteriori sin
inventarla—, la produje con el mecanismo que `CHECKPOINTS.md` prevé: **copia
aislada, nunca el árbol real**. Un `git worktree` desechable en el commit
anterior al fix (`193fc3c^` = `963331c`), con solo el fichero de test copiado
encima, y la suite de esos cuatro tests contra el código de *antes*:

```
FAILED test_f023_el_techo_de_sigrid_api_es_230
    AttributeError: module 'config.settings' has no attribute 'SIGRID_API_TIMEOUT_MAX_S'
FAILED test_f023_el_default_del_timeout_no_supera_el_techo
    AttributeError: module 'config.settings' has no attribute 'SIGRID_API_TIMEOUT_MAX_S'
FAILED test_f023_un_timeout_por_encima_del_techo_se_rechaza_al_arrancar
    Failed: DID NOT RAISE ValidationError
3 failed, 1 passed in 0.93s
```

Worktree eliminado después; `git worktree list` con una sola entrada, la real.

Lo que esto demuestra, y por qué importa más que cumplir un trámite: el tercer
fallo —`DID NOT RAISE ValidationError`— prueba que **el test discrimina de
verdad** la restricción `le=SIGRID_API_TIMEOUT_MAX_S`. Sin ella el test cae. Eso
es exactamente lo que la campaña de mutación **no** puede decirme aquí (ver
hallazgo 1), así que esta traza no es burocracia: es la única evidencia
independiente de que ese cambio está vigilado. El cuarto test («un timeout igual
o menor se acepta») pasa antes y después, como debe: es el lado de no
regresión.

Con esto el checkbox de fase RED de F-023 queda `[x]`, con la traza en este
informe en vez de en el del implementer.

---

# Cambios requeridos · F-003

1. **Marcar T18, T19, T20, T21, T22 y T22 bis** en
   `specs/F-003-infra-caj/tasks.md`, cada una con la evidencia que ya existe:
   `progress/current.md` §«Tanda 1 del bloque 5 · EJECUTADA por el humano el
   2026-08-10». **No hay que reejecutar nada contra Azure**; es apuntar lo
   verificado. Si alguna te consta como no ejecutada, déjala abierta y escribe
   el motivo: prefiero eso a marcarla.
2. **Corregir el comando de firewall**, que hoy no ejecuta, en los **dos**
   sitios:
   - `infra/README.md:149-150` — dice
     `firewall-rule create -g <pgResourceGroup> -n <servidor> --rule-name <job>`;
     debe decir `--server-name <servidor>` (o `-s`) y `--name <job>` (o `-n`).
   - `specs/F-003-infra-caj/requirements.md`, bloque de R23 — mismo error:
     `-n psql-albaranes-rs9k2 --rule-name caj-datamart-seg-<entorno>`.
   Fuente de la corrección, ya verificada en este repositorio:
   `progress/manual_F-024_fase_c.md` (commit `7cc4fa1`) — «el servidor va en
   `--server-name`/`-s`, **no** en `--name`; la regla se nombra con `--name`/`-n`;
   **`--rule-name` no existe** en la CLI».
   **Cuidado al editar**: la línea del `firewall-rule list`, dos más abajo en el
   README, **está bien** con `-n <servidor>` — en `list`, `-n` *sí* es el
   servidor. Esa asimetría entre subcomandos es justo lo que hay que dejar
   escrito para que nadie la "arregle" al revés. Vale la pena hacerlo bien:
   `current.md` registra que el 2026-08-19 se perdió media hora y se creó una
   regla de más por tropezar con esto.
3. **F-026 no existe.** `harness/features.json` tiene 29 features y F-026 no está
   entre ellas (faltan también F-021, F-025 y F-027). Sin embargo la ficha de
   F-023 y `progress/manual_F-023.md` apuntan a F-026 el defecto «RBAC sin
   propagar en `60_create_identity.ps1`, `throw` falso, necesita reintento con
   espera», y `current.md` lo lista como el segundo defecto de F-003 «anotado
   sin corregir». **Ese defecto no está registrado en ningún sitio ejecutable.**
   O se crea la feature, o se añade como tarea de F-003, o se anota como deuda
   aceptada; lo que no puede quedar es un puntero a una ficha inexistente en la
   evidencia de cierre de una feature `critico`.
4. **T27**: anotar en `progress/current.md` el resultado de **cada** verificación
   MANUAL. Las tres de F-004 viven solo en `manual_F-023.md`; basta un puntero
   con el resultado de cada una. Lo demás que T27 pide ya está: la deuda del
   **ID de suscripción en el historial de git** está en §«Deuda que dejas
   decidir a ti» (línea 617) y DA-1/DA-2/DA-4 están resueltas y fechadas.
   Aprovecha para arreglar la contradicción de **DA-3**: la línea 613 la da por
   abierta y la tanda 2 por resuelta.
5. **T28**: marcarla. `bash harness/init.sh` en verde hoy, exit 0, verificado en
   la cabecera de este informe.

Con esos cinco puntos F-003 queda cerrable sin volver a Azure. Cuando estén,
reviso solo el diff de `tasks.md`, los dos ficheros del comando y `current.md`;
no hace falta otra pasada completa.

---

# Apuntes de cierre · F-023 (para cuando F-003 esté cerrada)

De esto te encargas tú, como con F-024:

1. **`harness/features.json`, ficha de F-023**: `"rigor": "estandar"` →
   `"critico"`. Es el hallazgo que pediste que te dijera: el nivel declarado
   está equivocado y llevaba así desde el principio.
2. **`harness/features.json`**: F-023 `in_progress` → `done`, y F-003 `blocked`
   → `done`, **en ese orden y solo después de los cinco cambios de arriba**.
3. **`progress/history.md`**: resumen de F-023 y de F-003. Hoy no hay ninguno de
   los dos, y C2 lo exige para toda feature `done`.
4. **Opcional, tú decides**: cerrar las tres verificaciones en la cola de
   `specs/F-004-.../tasks.md`, que las sigue listando pendientes. F-004 está
   `done`; el implementer hizo bien en no tocar la spec de una feature cerrada y
   en señalarlo. Son tres líneas.
5. **Decisión pendiente, no apunte**: qué haces con el bloque 1 de F-032 (las
   dos copias de contraseñas en el vault de *albaranes*), ahora que la condición
   de R27 —«que el job funcione»— ya se cumplió. Subir su prioridad o aceptar
   por escrito que se quedan.

---

# Hallazgos y propuestas de automejora (no aplicadas)

## 1 · La campaña de mutación es ciega a un techo numérico en un `Field(...)`

Encontrado haciendo la prueba de control que mi protocolo exige cuando aparece
un cero. `config/settings.py` está en el alcance de la campaña vigente con 12
líneas —justo las del cambio de F-023 (50-53, 62-69)— y aporta **0 mutantes**.
Control: `generar_mutantes` sobre **todo** `config/settings.py` ignorando el
alcance da **15 mutantes**, ninguno en las líneas 50-69.

Conclusión: **el cero es legítimo** (el juego de operadores no sabe mutar una
constante de módulo ni un literal numérico dentro de los argumentos de
`Field(...)`), no es un generador roto ni un informe escrito a mano. Pero el
diagnóstico incómodo es este: un cambio cuyo contenido entero es **un número y
una cota** es el caso de libro para el que existe el mutation testing —mutar
`230.0` a `231.0` y ver si alguien se queja— y la herramienta pasó de largo sin
decir nada. Verde por silencio.

**Propuesta** (a `arnes-base` si se acepta, por la regla de propagación): que la
campaña imprima una línea **«líneas en alcance sin ningún mutante generado»**,
por fichero. No cuesta nada y convierte un silencio en un dato: el reviewer
sabría que la puerta no dijo «sí», dijo «nada». Y, si se quiere ir más lejos, un
operador para literales numéricos en argumentos con nombre y en constantes de
módulo.

## 2 · `CHECKPOINTS.md` C5 solo mira en una dirección

C5 pide «`tasks.md` con todas las tareas `[x]`». Nada obliga a comprobar lo
contrario: **tareas sin marcar cuya evidencia ya existe en `progress/`**. Hoy
eso es literalmente lo único que separa a F-003 de `done`, y llevaba nueve días
así sin que ninguna puerta lo señalara.

**Propuesta**: añadir a C5 la comprobación en los dos sentidos — «ninguna tarea
marcada sin evidencia, y ninguna tarea con evidencia sin marcar». El reviewer ya
tiene que leer `progress/`; es coste cero y cierra un hueco real.

## 3 · Una feature que trabaja en la rama de otra es invisible a las puertas

`harness.alcance` para F-023 devuelve **cero líneas**, porque diffea contra
`feature/F-023-cierre-operativo-f003`, que existe pero se quedó atrás: el
trabajo se hizo en la rama de F-024. Si alguien hubiera lanzado la cobertura o
la mutación con `--feature F-023`, habrían salido **verdes por vacío**, y ese
cero es indistinguible de «no había nada que medir». Hoy no ha causado daño
—verifiqué que el único commit de código de F-023 vive en la rama de F-024 y
**sí** entró en la campaña que recalculé—, pero es una vía silenciosa para
saltarse las tres puertas sin proponérselo.

**Propuesta**: que `init.sh` avise cuando la rama actual **no** sea la declarada
por la feature `in_progress` en `features.json`. Existe información para
detectarlo y hoy solo se valida que la rama sea `feature/*`.

## 4 · La paráfrasis que costó un análisis (y casi una operación de RBAC)

Todo el episodio de la «desviación» de la verificación 3 existió porque la ficha
de F-023 **parafraseó** el requisito de F-004 más estricto de lo que estaba
escrito: donde F-004 pedía «ejecutar sin el rol asignado», la ficha exigía
«quitar el rol y reasignarlo». Eso generó un riesgo inventado (una asignación que
devolver sobre un recurso compartido), un permiso que el puesto no tiene, y una
discusión de desviación sobre un requisito que en realidad se cumplía tal cual.

**Propuesta**: cuando una ficha o una spec reformule un requisito de otra
feature, que **cite el original o lo enlace**. Una línea de coste; aquí habría
ahorrado el análisis entero.

---

# Segunda pasada · 2026-08-19 (tarde)

Revisados los commits `09c2a44`, `5bee7e4` y `1883289` sobre el HEAD `4a10bfa`.
Alcance de esta pasada, el que anuncié: el diff de `tasks.md`, los dos ficheros
del comando y `current.md`, más los dos ficheros del trabajo extra.

**`bash harness/init.sh` tal cual: exit 0, 617 passed, `PUERTA COBERTURA [OK]
100,0 % de 372 líneas cambiadas (372/372, umbral 80 %, nivel critico)`.** Los
dos `[AVISO]` son los de siempre. Árbol limpio y un solo worktree, comprobados
al retomar tras la caída.

## Veredicto

| Feature | Veredicto | Puede pasar a `done` |
|---|---|---|
| **F-003** | **APPROVED** | Sí, tras los dos apuntes de cierre de abajo |
| **F-023** | **APPROVED** (sin cambios respecto a la primera pasada) | Sí, después de F-003 |

Los cinco cambios están hechos, y tres de ellos mejor de lo que pedí.

## Los cinco cambios, uno a uno

1. **T18–T22 y T22 bis marcadas** `[x]` — Verificado contra
   `progress/current.md` §«Tanda 1». No es un marcado a ciegas: la nota de
   cabecera dice que se marcan apuntando esa evidencia y que **no se ha vuelto a
   ejecutar nada contra Azure**, que es exactamente la distinción que importa.
   Y cada tarea anota lo que marcarla a secas habría tapado: que la `staticIp`
   de T18 no se versiona y por eso no está ahí, que la imagen de T21
   (`r20260810-1024`) quedó obsoleta antes de T24, y que las copias viejas de
   T22 bis **siguen vivas** con la condición de R27 ya cumplida. La prueba
   independiente que apunté para T22 bis —`80_create_job.ps1` aborta sin el
   secreto en el vault propio, luego T22 y T22 bis funcionaron— quedó recogida.
   El aviso de T22 sobre que la regla existe «porque quien la creó usó los
   parámetros correctos, no los que decía la spec» es la frase honesta.
2. **Comando de firewall corregido** en `infra/README.md` y en R23 — Correcto en
   los dos sitios: `--resource-group` / `--server-name` / `--name`. La línea del
   `firewall-rule list` **intacta** con su `-n`, y la asimetría explicada con el
   aviso de no generalizar el arreglo, que era el riesgo real de esta
   corrección. Añadido además el detalle del backtick de continuación, que no
   pedí y evita el siguiente tropiezo.
3. **F-026 registrada** — Ficha con el defecto descrito y cinco criterios
   `acceptance` accionables (reintento con espera, mensaje que distingue «aún no
   propagó» de «no tienes permiso», documentación de quién tiene los permisos,
   verificación real y arnés en verde), `estandar`, prioridad 14. `init.sh`
   valida el JSON y `BACKLOG.md` la recoge en la línea 28. Ya no hay punteros a
   una ficha inexistente.
4. **T27** — Las tres verificaciones están en `current.md` con hora y resultado,
   y con las dos cosas que pedían no perderse: que el primer intento de V1 dio
   `SUCCESS` con `origen=local` y **no valía**, y que V3 se hizo sin tocar RBAC.
   DA-3 ya no se contradice: la línea que la daba por abierta remite a la tanda 2
   y explica por qué se corrigió. La deuda del ID de suscripción seguía en su
   sitio.
5. **T28 marcada** con el `init.sh` de hoy.

## Las dos cosas de más: la primera, bien; la segunda, bien pensada y mal puesta

**El runbook: acertaste, y era más grave de lo que parecía.**
`docs/runbook_postgres_azure.md` es documento operativo vivo y sus dos comandos
no ejecutaban; al `delete` le faltaban además grupo y servidor, así que estaba
roto por partida doble. Dejarlo «para no ensuciar el diff» habría sido cumplir
la letra de mi encargo a costa de su motivo: el cambio 2 existía justamente
porque un comando copiable que falla cuesta media hora. La nota que explica la
asimetría entre subcomandos —y que en `list` el `-n` **sí** es el servidor y no
hay que tocarlo— es lo que impide que el próximo «arregle» lo que funciona.
Barrido el repositorio entero: **no queda ningún comando de firewall ejecutable
roto**; lo que menciona `--rule-name` es prosa que explica el error.

**F-005: el criterio es correcto, la colocación no.** Anotar en vez de
reescribir es lo que corresponde en una feature `done` —la spec de una feature
cerrada es el registro de lo que se hizo, y reescribir sus comandos haría que
ese registro dejara de coincidir con lo que realmente se ejecutó—. Es el mismo
criterio que apliqué a la cola de F-004, así que **no lo reviertas: la nota se
queda**.

Pero está **dentro del bloque de código**, entre el `create` y el `list`
(`specs/F-005-postgres-azure/tasks.md:166-170`), y ahí hace daño en vez de
avisar:

- No se renderiza como cita: los `>` salen como texto literal dentro del
  bloque, así que no parece un aviso sino parte del script.
- Quien copie el bloque —que es la forma normal de usar una tarea MANUAL— se
  lleva cinco líneas de prosa en medio de dos comandos. Pegadas en una consola,
  el `>` inicial es un operador de redirección: en bash el paréntesis de
  «(al cerrar F-003)» hace saltar un error de sintaxis, y en PowerShell falla
  igual. Ruido, no aviso.
- Y el `create` roto que la nota denuncia **sigue siendo la primera línea del
  bloque**, con el aviso debajo: quien copie solo el primer comando se lleva los
  flags malos sin haber visto nada.

Se arregla moviendo las cinco líneas **fuera del cierre del bloque**, detrás de
los ``` de la línea 172. La nota, idéntica; solo cambia de sitio. Va como
apunte de cierre y no como cambio requerido porque es un movimiento de cinco
líneas, está en la spec de una feature cerrada y el documento operativo vivo
—el runbook— ya está correcto.

## Los checkpoints que estaban vacíos en la primera pasada

- **C4 de F-003** `[x]` — El comando exacto de la verificación MANUAL de T22 ya
  ejecuta, en los dos sitios. El resultado de cada verificación MANUAL está en
  `current.md`.
- **C5 de F-003** `[x]` con una salvedad mecánica — De las ocho tareas abiertas
  quedan **cero por trabajo** y **una por marcar**: T27 sigue en `[ ]`, y no
  podía ser de otra manera, porque su verificación declarada es «revisión del
  reviewer contra `CHECKPOINTS.md` C4» y esa revisión es este documento. Doy su
  contenido por verificado; marcarla es la consecuencia de este veredicto, no
  trabajo pendiente. Va como apunte de cierre 1.

## Apuntes de cierre

### F-003 (antes de marcarla `done`)

1. **Marcar T27** `[x]` en `specs/F-003-infra-caj/tasks.md`, con este informe
   como evidencia (segunda pasada, 2026-08-19: contenido en `current.md`
   verificado, DA-1/DA-2/DA-3 resueltas y fechadas, deuda del ID de suscripción
   anotada para tu decisión).
2. **Mover la nota de `specs/F-005-postgres-azure/tasks.md` T16 fuera del
   bloque de código**, detrás del cierre del bloque. Sin cambiar su texto.
3. `harness/features.json`: F-003 `blocked` → `done`.
4. `progress/history.md`: resumen de F-003.

### F-023 · **mantengo los cinco apuntes tal como los escribí**

Nada de lo hecho hoy los altera. Los repito para no obligar a subir:

1. `harness/features.json`, ficha de F-023: `"rigor": "estandar"` →
   `"critico"`.
2. F-023 `in_progress` → `done`, **después** de F-003.
3. `progress/history.md`: resumen de F-023.
4. Opcional: cerrar las tres verificaciones en la cola de
   `specs/F-004-.../tasks.md`. Si lo haces, **mismo criterio que acaba de
   aplicarse a F-005**: nota fechada al lado, no reescritura. Y fuera del
   bloque de código.
5. Decisión pendiente, no apunte: qué haces con el bloque 1 de F-032 (las dos
   copias de contraseñas en el vault de *albaranes*), ahora que la condición de
   R27 ya se cumple. Hoy ha ganado un recordatorio más en T22 bis.

## Las cuatro propuestas de automejora siguen vivas

Ninguna se ha aplicado, que es lo correcto: son para que decidas tú. Recuerdo la
que más caro sale si se olvida: **la campaña de mutación es ciega a un techo
numérico en un `Field(...)`** —cero mutantes en las 12 líneas del cambio de
F-023, verde por silencio—, y la propuesta es que la campaña imprima «líneas en
alcance sin ningún mutante generado». El episodio de hoy le da una segunda
razón: el defecto del RBAC llevaba **nueve días** apuntando a una ficha que no
existía, y ninguna puerta lo dijo.
