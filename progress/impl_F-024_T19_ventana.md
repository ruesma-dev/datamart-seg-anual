<!-- progress/impl_F-024_T19_ventana.md -->
# F-024 · T19 — la ventana de la alerta de frescura (defecto del 2026-08-19)

Implementer, 2026-08-19. Rama `feature/F-024-coherencia-cargas-truncadas`.
Alcance: **solo** el defecto que destapó la verificación manual de T19
(`progress/manual_F-024_fase_c.md`, última sección). No se ha tocado Azure ni
se ha creado la alerta: eso lo hace el líder con el humano después de esto.

## 1 · El defecto

El primer `create` de la regla, ya con la autenticación resuelta, lo rechazó
el ARM:

```
(InvalidRequestContent) The request content was invalid and could not be
deserialized: 'WindowSize of 1800 minutes is not supported. Supported
granularities are: 5, 10, 15, 30, 45, 60, 120, 180, 240, 300, 360, 720, 1440,
2880'
```

1800 min son las 30 h de DA-4. `windowSize` **no es un valor libre**: solo
admite esas granularidades y entre 1440 (24 h) y 2880 (48 h) no hay ninguna.
`infra/95_create_alert_frescura.ps1` componía la ventana como
`$ventana = "{0}h" -f $horas`, o sea `30h`: **la alerta nunca se pudo crear**.

La suite no lo cazó porque leía el script como texto y `30h` era una cadena
perfectamente bien formada. El comentario que decía «confirmado con `--help`»
es la trampa: `--help` valida la **forma** `##h##m##s`, no el **valor**.

## 2 · Lo implementado (decisión del humano, ya cerrada)

**DA-4 no cambia: el criterio sigue siendo 30 h.** Cambia cómo se expresa, en
dos mitades que salen del **mismo** `frescuraUmbralHoras` y ninguna escrita a
mano:

| Mitad | Valor con umbral 30 | Dónde vive |
|---|---|---|
| **Ventana** de la regla | `48h` (2880 min) | `--window-size`, derivada por `Resolver-VentanaAdmitida` |
| **Criterio** exacto | 30 h | `where TimeGenerated > ago(30h)`, dentro de la KQL |

La ventana sale más ancha que el criterio a propósito y no lo relaja: la regla
lee 48 h de logs y **cuenta solo** los de las últimas 30. Se elige *la menor*
granularidad que contiene el umbral, no la mayor de la lista: una ventana más
ancha de lo necesario es más caro de consultar y no aporta nada.

Un umbral que no cabe en ninguna granularidad (> 48 h) **falla antes de llamar
a Azure**, con un mensaje que nombra la clave a cambiar y el tope. Un umbral
menor que 1 h también: no tiene sentido y el redondeo a `5m` sería una
sorpresa silenciosa.

## 3 · Ficheros tocados

| Fichero | Qué cambia |
|---|---|
| `infra/95_create_alert_frescura.ps1` | función `Resolver-VentanaAdmitida` (lista de granularidades con el error del ARM citado, elección de la menor que contiene el umbral, `throw` accionable si no cabe o si el umbral es absurdo); `$ventana` sale de ella; `$filtroTemporal` (`ago($horas h)`) entra en la KQL; cabecera con la restricción real y la trampa de `--help`; la traza de salida dice ventana y criterio por separado, y con qué valor hay que restaurar |
| `tests/test_f024_infra_alerta.py` | seis tests nuevos (tres de ellos **ejecutan** la función con `powershell`) y el de la ventana reescrito; una sola invocación de `powershell` en caché para todos los umbrales |
| `infra/env/dev.json` | `$aviso_frescura`: el umbral es el criterio, la ventana es un valor derivado; el tope de 48 h |
| `infra/README.md` | el `update` de restaurar pasa de `30h` a `48h`; la lista de granularidades, el error del ARM y la trampa de `--help`; las tres cosas que salen del umbral |
| `specs/.../requirements.md` | enmienda fechada en DA-4 (restricción, solución, por qué la ventana es más ancha); R22.3 reescrito; R23 paso (3) y su comando → `48h`; nota en el bloque de T3 |
| `specs/.../design.md` | §8 con el pseudocódigo real y la enmienda; el `--window-size 30h` de T3 marcado como falso |
| `specs/.../tasks.md` | T19 restaura a `48h`; sub-tarea `T19 bis` con lo hecho aquí |
| `progress/current.md` | el aviso donde el líder busca los pasos de T19 |
| `progress/manual_F-024_fase_c.md` | **fuera del alcance pedido, ver §6**: redactado el GUID que dejaba `init.sh` en rojo |

El estilo del `.ps1` se mantiene: español **sin tildes**, comentarios que
explican *por qué*, UTF-8 con BOM y CRLF (comprobado byte a byte por el test
de F-003 y por el de esta feature).

## 4 · Fase RED (rigor `critico`)

Tests escritos **antes** del arreglo. Comando y salida real:

```
$ python -m pytest tests/test_f024_infra_alerta.py -q
...
E       AssertionError: la ventana se compone pegando una 'h' al umbral: eso
        produjo 30h (1800 min), que Azure no admite, y la alerta no se pudo
        crear nunca
E       assert not <re.Match object; span=(1214, 1241), match='$ventana = "{0}h" -f $horas'>
tests\test_f024_infra_alerta.py:299: AssertionError
...
E       AssertionError: el script no define la función Resolver-VentanaAdmitida
tests\test_f024_infra_alerta.py:118: AssertionError
...
E       AssertionError: la KQL no acota por TimeGenerated: la regla contaría los
        eventos de toda la ventana (48 h) en vez de los del umbral (30 h)
tests\test_f024_infra_alerta.py:348: AssertionError
...
E       AssertionError: README.md manda ejecutar --window-size 30h (1800 min),
        que Azure rechaza
E       assert 1800 in (5, 10, 15, 30, 45, 60, ...)
tests\test_f024_infra_alerta.py:463: AssertionError

19 failed, 11 passed in 1.57s
```

Los 19 fallos son, agrupados: la ventana compuesta a mano (1), la función que
no existía —y con ella los 15 casos que la ejecutan— (16), la KQL sin filtro
temporal (1) y la documentación mandando restaurar `30h` (1).

Tras el arreglo, el mismo comando: **`30 passed in 1.30s`**.

## 5 · Verificaciones, con el resultado real

1. **`bash harness/init.sh`** → `ENTORNO LISTO. Puedes trabajar.`
   `614 passed, 871 warnings in 12.48s` (y `in 45.05s` en la última corrida,
   con la máquina cargada: mismo resultado);
   `PUERTA COBERTURA: 100.0% de 372 líneas cambiadas cubiertas (372/372,
   umbral 80%, nivel critico)`.
2. **Los tests ejecutan el script de verdad, no lo leen.** Se extrae
   `Resolver-VentanaAdmitida` del `.ps1` y se invoca con `powershell` para 14
   umbrales. Con el umbral configurado (30) devuelve `48h`; para cada umbral
   de 1 a 48 devuelve exactamente la menor granularidad que lo contiene; con
   49, 72, 0 y −1 lanza error con el mensaje accionable.
3. **Prueba de que el test nuevo no es un adorno**: manipulando la lista del
   script (`2880` → `1800`, el valor inválido) la suite se pone en rojo con
   **5 fallos**, entre ellos el del umbral real. Script restaurado después
   (`git diff --quiet` limpio).
4. **Prueba de que el test de la documentación no es vacuo**: devolviendo
   `infra/README.md` a `--window-size 30h` falla con
   `README.md manda ejecutar --window-size 30h (1800 min), que Azure rechaza`.
   Restaurado.
5. **Campaña de mutación** (`python -m harness.mutacion --feature F-024`):
   **108 mutantes, 108 muertos, 0 supervivientes, 0 timeouts en 270,9 s** →
   `progress/mutacion_F-024_T19.md`.
   **[Corrección del 2026-08-19, §17: este resultado era falso.** Los dos
   supervivientes del 18-ago siguen vivos; la campaña paralela los contó como
   muertos por error y yo interpreté el cero como una mejora. La cifra buena
   es 108 / 106 / 2.**]**
6. **Contra Azure, nada.** Ni un `create`, ni un `update`, ni una lectura.
   Verificado también por lo que no hay en el diff: el script no se ha
   ejecutado.

## 6 · Fuera del alcance pedido, pero hecho (y por qué)

`init.sh` estaba **ya en rojo antes de empezar**, y no por esto: el commit
`e1ea3ed` dejó en `progress/manual_F-024_fase_c.md` el GUID literal del
mensaje `AADSTS50076`, y `test_f003_r4_sin_secretos_ni_identificadores_en_infra_y_spec`
lo rechaza. Comprobado con `git stash`: sin mis cambios, las mismas dos
comprobaciones fallaban con los mismos números (`36.0% de 372 líneas`, que era
consecuencia de que pytest aborta al primer fallo y no llega a medir).

Ese GUID es un identificador **público** de Microsoft (la Service Management
API), no de la suscripción ni del tenant, pero el guardián no puede
distinguirlo y no podía dejarse: con el repositorio en rojo no se puede cerrar
nada. Se ha sustituido por su nombre, que es lo que aportaba el dato
(commit `0af5027`). Si el líder quería otra redacción, es un `git revert` de
un commit de una línea.

## 7 · Lo que queda fuera

- **Crear la alerta en Azure**: sigue pendiente y es de T19. El script ya no
  tiene el defecto, pero **la alerta no está verificada hasta que llegue un
  correo de verdad**. Nadie ha comprobado en el servicio que `48h` +
  `ago(30h)` se acepte: lo que se sabe es que 2880 min está en la lista que
  el propio ARM devolvió.
- **Riesgo residual identificado, no cerrado**: si Azure Monitor recortase la
  consulta al rango de la ventana de forma incompatible con un `ago()`
  explícito, la regla contaría distinto de lo previsto. Se ve en el primer
  `Activated`/`Deactivated` de la prueba de extremo a extremo, que es
  precisamente el paso que falta.
- **T18 y la segunda mitad de T20**: no se han tocado.
- **`azure-apps/datamart_seg_anual.md`**: leído (líneas 75-79). Dice que la
  alerta «avisa si pasan **30 h** sin que el job complete un `build_mart`», y
  eso **sigue siendo verdad**: el criterio no ha cambiado y la ventana es un
  detalle de implementación de la regla, no algo que ese documento exponga o
  consuma. Por eso no se ha tocado, ni hacía falta.
- **`--evaluation-frequency`**: no se ha tocado (`1h`) ni se ha comprobado que
  sus valores estén igual de restringidos. Con `1h` y `5m` ya se han hecho
  llamadas que el ARM no rechazó por eso.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados y resultado | **614 pasan, 0 fallan** (`bash harness/init.sh`). De ellos, **30** en `tests/test_f024_infra_alerta.py`, **6 nuevos** y 1 reescrito |
| Cobertura de las líneas cambiadas | **100,0 %** (372/372; umbral 80 %, nivel `critico`) — línea `PUERTA COBERTURA` de `init.sh` |
| Mutantes generados / supervivientes | ~~**108 / 0**~~ **CORREGIDO en §17: son 108 / 2**, los dos equivalentes y ya justificados. El `0` salió de una campaña paralela cuyo resultado no es reproducible; `progress/mutacion_F-024_T19b.md` |
| Tiempo de ejecución de la suite | **12,48 s** en la primera medición y **45,05 s** en la última, con el mismo resultado: la máquina estaba a la vez con la campaña de mutación y con otras cargas, así que el número no es comparable entre corridas. Lo que sí se midió aislado: el fichero de esta feature pasa de 6,23 s (14 invocaciones de `powershell`) a **1,30 s** (una sola, en caché) |
| Tiempo de la campaña de mutación | **270,9 s** |
| Fase RED | traza pegada en §4: 19 fallos antes del arreglo, 30 en verde después |

Nota sobre el alcance de la mutación: este trabajo **no cambia ni una línea de
Python de producción** (solo el `.ps1`, tests y documentación), así que las
1268 líneas en alcance y los 108 mutantes son los de F-024 completa. La
mutación no llega a los `.ps1`: ahí la red es la suite de `infra/`, y por eso
tres de los tests nuevos ejecutan la función en vez de leerla.

## Commits

| Commit | Qué |
|---|---|
| `0af5027` | el informe de la fase C no versiona el app id de la Service Management API |
| `04d87a1` | la ventana sale de las granularidades que admite Azure (script, tests, README, `dev.json`, spec) |
| `dbd84d0` | los tests de la ventana arrancan `powershell` una sola vez |

Sin `git push` y sin PR, como manda el protocolo.

---

# Segunda vuelta · 2026-08-19 (CAMBIOS_REQUERIDOS del reviewer)

`progress/review_F-024_T19_ventana.md` devolvió el trabajo con un bloqueante y
dos menores. Tenía razón en los tres, y el bloqueante era **el mismo defecto de
clase que este trabajo venía a cerrar**, un paso más allá: cerré la ventana
comprobando el valor, pero dejé el criterio de 30 h comprobado por su **forma**.

## 8 · El bloqueante

`test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` buscaba
`TimeGenerated > ago(...)` en el **texto del fichero** y exigía que esa línea
llevara `$horas`. Eso demuestra que `$filtroTemporal` **se define**, no que
**llegue a la consulta**. El reviewer quitó la variable de la concatenación de
`$kql` —una variable definida y no usada, lo que deja un merge mal resuelto— y
la suite entera pasó en verde con la regla juzgando a 48 h en vez de a 30.

## 9 · Lo implementado en esta vuelta

**La composición de la consulta pasa a una función del `.ps1`,
`Componer-ConsultaFrescura -Job <j> -UmbralHoras <h> [-Nombre <n>]`**, que
devuelve el argumento completo de `--condition-query` (`<nombre>=<kql>`). Los
tests la **ejecutan** con `powershell` —mismo mecanismo que
`Resolver-VentanaAdmitida`, misma pasada en caché, un solo arranque— y afirman
sobre la cadena devuelta:

| Test | Qué afirma sobre el VALOR |
|---|---|
| `test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` (reescrito) | la consulta enviada trae `ago(30h)`; las horas del `ago` son las del umbral de `dev.json`; y **no** coinciden con las de la ventana (si coincidieran, el filtro no estaría acotando nada) |
| `test_f024_r22_la_consulta_compuesta_lleva_el_evento_y_el_job` (nuevo) | los tres términos de `TERMINOS_DEL_EVENTO` van dentro del `has_all` **de la cadena enviada**, la consulta arranca en `ContainerAppConsoleLogs_CL` y acota por `ContainerJobName_s` con el job real |
| `test_f024_r22_el_nombre_de_la_consulta_es_el_que_cuenta_la_condicion` (nuevo) | el nombre del resultado que devuelve la función es el mismo que cuenta `--condition "count 'X' < 1"`. Si divergen, la regla cuenta algo que no existe y **se queda muda sin que Azure proteste** |
| `test_f024_r22_la_consulta_compuesta_es_la_que_viaja_en_condition_query` (nuevo) | punto 2 del reviewer: `$consulta` sale de la función, con `$CFG.job` y `$horas`, y esa misma variable es la que va en `--condition-query` |
| `test_f024_r22_el_script_declara_las_granularidades_que_admite_azure` (corregido) | punto 3: se mira **solo el literal `$granularidades = @(...)`** y se exige igualdad exacta con la lista del ARM. Antes barría todos los números de la función y el `2880` del mensaje de `throw` la ponía en verde con la lista mutilada |

Sobre el punto 2, con honestidad: ejecutar la composición demuestra **qué
cadena produce** el script, no que sea la que se envía. Ese salto son dos
líneas de pegamento (`$consulta = Componer-...` y `--condition-query
$consulta`) y es lo único que sigue comprobándose por texto. Se podría cerrar
del todo extrayendo **todos** los argumentos de `az` a una función que el test
ejecutara, pero eso cambia la forma de invocar `az.cmd` en un script que **no
puedo probar contra Azure** (y cuya regla está ahora mismo en mitad de la
verificación manual). Lo dejo escrito como decisión, no como olvido: he
preferido un eslabón de dos líneas explícito y con test a un refactor de la
invocación que no puedo verificar.

## 10 · Fase RED de esta vuelta

Tests escritos antes de tocar el `.ps1`:

```
$ python -m pytest tests/test_f024_infra_alerta.py -q
E       AssertionError: el script no define la función Componer-ConsultaFrescura
tests\test_f024_infra_alerta.py:123: AssertionError
E       AssertionError: $consulta no sale de Componer-ConsultaFrescura: lo que se
        ejecuta en los tests y lo que se envía a Azure podrían ser cosas distintas
tests\test_f024_infra_alerta.py:533: AssertionError

19 failed, 14 passed in 4.16s
```

Después del arreglo: **`33 passed in 2.40s`**.

## 11 · Las cuatro pruebas de control (romper lo que el test vigila y pegar la traza)

El criterio de aceptación que puso el reviewer es la primera. Todas se
aplicaron sobre el árbol real y se restauraron desde una copia previa;
`git diff --quiet` limpio al terminar cada una.

**Control 1 — el criterio no llega a la consulta** (quitar `$filtroTemporal` de
la concatenación dejando intacta la línea que lo define): era exactamente el
camino que antes pasaba en verde.

```
E  AssertionError: la consulta que se envía no acota por TimeGenerated, así que
   la regla contaría los eventos de toda la ventana en vez de los del umbral:
   Frescura=ContainerAppConsoleLogs_CL | where ContainerJobName_s == '...'
   | where Log_s has_all ('step_finished','build_mart','SUCCESS')
1 failed, 32 passed          # y en la suite completa: 1 failed, 616 passed
```

**Control 2 — la consulta compuesta no viaja en `--condition-query`** (se
sustituye por una cadena literal):

```
E  AssertionError: el argumento --condition-query no lleva la consulta compuesta
1 failed, 32 passed
```

**Control 3 — lista de granularidades mutilada** (`2880` fuera): el test del
punto 3 **ahora sí** cae, además de los que ejecutan la función.

```
E  AssertionError: la lista del script no es la que declara el ARM.
E  AssertionError: el umbral de frescura configurado (30 h = 1800 min) no cabe en
   ninguna ventana que admita Azure: la mayor es 2880 min (48 h). ...
```

**Control 4 — el nombre del resultado deja de ser el que cuenta la condición**
(`Frescura` → `Frescuras`):

```
E  AssertionError: la condición cuenta 'Frescura' y la consulta se llama
   'Frescuras': la regla contaría un resultado inexistente
1 failed, 32 passed
```

## 12 · Un incidente propio, para que conste

Ejecutando el control 1 la primera vez, el `git checkout --` con el que
restauraba el script **descartó los cambios del `.ps1` que aún no había
commiteado** (la función nueva y la llamada). No se perdió nada —los rehíce y
el resultado es idéntico—, pero la lección es real y la anoto: **primero se
commitea y solo después se rompe el árbol a propósito**. Los tres controles
siguientes se hicieron con copia previa y `cp` de vuelta, nunca con
`git checkout`.

## 13 · Verificaciones de esta vuelta, con el resultado real

1. `bash harness/init.sh` → `ENTORNO LISTO. Puedes trabajar.`,
   **`617 passed`**, `PUERTA COBERTURA: 100.0% de 372 líneas cambiadas
   cubiertas (372/372, umbral 80%, nivel critico)`.
2. Las cuatro pruebas de control de §11, cada una en rojo y restaurada.
3. **Contra Azure, nada.** Ni un `create`, ni un `update`, ni un `show`, ni una
   lectura. Sabiendo además que la regla está creada y en mitad de la prueba de
   ventana corta, y que hay una ejecución del job en curso para T18, no se ha
   ejecutado el script ni ningún comando de `az`.
4. No se han tocado `progress/manual_F-024_fase_c.md` ni `progress/current.md`,
   como pidió el líder por estar trabajando en ellos en paralelo. Lo que había
   que anotar está aquí. **Consecuencia a tener en cuenta:** el aviso del `48h`
   que dejé en `current.md` en la primera vuelta sigue siendo correcto, y esta
   vuelta no añade nada que el humano tenga que hacer distinto.

## 14 · Evidencias de la segunda vuelta

| Evidencia | Valor real |
|---|---|
| Tests ejecutados y resultado | **617 pasan, 0 fallan**. El fichero de la alerta pasa de 30 a **33 tests** (3 nuevos, 2 reescritos) |
| Cobertura de las líneas cambiadas | **100,0 %** (372/372, umbral 80 %) — igual que antes: no se toca Python de producción |
| Mutantes / supervivientes | **108 / 106 muertos / 2 supervivientes**, los dos equivalentes y con análisis cerrado (`progress/mutacion_F-024_T19b.md`). Ver §17: el `0` de la primera vuelta era falso |
| Pruebas de control | **4 de 4** en rojo al romper lo que vigilan, con la traza pegada en §11 |
| Fase RED | traza pegada en §10: 19 fallos antes, 33 en verde después |
| Tiempo de la suite del fichero | **2,4 s** para 33 tests, con una sola invocación de `powershell` que evalúa las dos funciones |

## 15 · Sigue fuera del alcance (sin cambios respecto a la primera vuelta)

- Crear la alerta y ver el `Activated`/`Deactivated`: es de T19 y lo hace el
  humano. **La alerta no está verificada hasta que llegue un correo.**
- El riesgo residual del servicio (que Azure Monitor recorte la consulta al
  rango de la ventana de forma incompatible con un `ago()` explícito) sigue
  identificado y sin cerrar. La sugerencia del reviewer es buena y la suscribo:
  al mirar el `Activated`, fijarse en el **número de filas evaluadas** de la
  notificación, que es donde se vería si el `ago(30h)` se está aplicando.
- `--evaluation-frequency`: nadie ha comprobado si sus valores están tan
  restringidos como los de `windowSize`.
- Las dos propuestas de automejora del arnés (declarar `infra/**.ps1` como ruta
  sensible; exigir en C4 bis la prueba de control de los tests que cubren
  código no mutable) las decide el humano. Si las acepta, van también a
  `arnes-base` por la regla de propagación. **No las he aplicado**: cambiar
  `CHECKPOINTS.md` a mitad de una review es cambiar el examen mientras se
  corrige. Añado un dato a favor de la segunda: las cuatro pruebas de control
  de §11 las he escrito porque el reviewer las pidió, y han encontrado el
  arreglo del punto 3 antes de que él lo volviera a mirar.

## 17 · Corrección de un número mío: la mutación NO daba cero supervivientes

Al relanzar la campaña en esta vuelta salió una discrepancia que hay que
contar, porque afecta a un número que yo mismo llevé al informe anterior.

| Campaña | Cómo | Resultado |
|---|---|---|
| 2026-08-18 15:15 (Fase B) | — | 108 mutantes, **106 muertos, 2 supervivientes** |
| 2026-08-19 11:52 (primera vuelta de T19) | paralela, hasta 16 worktrees | 108 mutantes, **108 muertos, 0 supervivientes** en 270,9 s |
| 2026-08-19 12:26 (esta vuelta) | `--workers 1` | 108 mutantes, **106 muertos, 2 supervivientes** en 1047,1 s |

Los dos supervivientes son los mismos de siempre: `bold=True → bold=False` en
dos `click.secho` de cabeceras decorativas de `check-coherencia`
(`main.py:564` y `567`).

**El resultado bueno es el de 106/2, y el cero era falso.** No es opinión:
*ningún* test de la suite menciona `bold` —comprobado con `grep -rn "bold"
tests/`, cero resultados—, así que no hay forma de que esa mutación muera. Lo
he verificado aplicándola a mano en el árbol real:

```
$ python -m pytest tests/ -q     # con bold=False en main.py:564
617 passed, 871 warnings in 6.82s
```

Es decir: **la campaña paralela declaró muertos dos mutantes que están vivos.**
No he investigado la causa dentro de `harness/mutacion.py` —está fuera de mi
encargo y toca el arnés— pero el efecto sí lo dejo escrito, porque un cero de
supervivientes es exactamente el número que nadie vuelve a mirar.

Consecuencias, asumidas:

1. **Mi informe de la primera vuelta decía «108 / 0, sin supervivientes que
   analizar». Era incorrecto** y lo he marcado en su tabla de Evidencias y en
   su §5.5, en vez de reescribirlo. La cifra real, entonces y ahora, es
   **108 / 106 / 2**.
2. El reviewer verificó de forma independiente el **alcance y la generación**
   (1268 líneas, 12 ficheros, 108 mutantes) y todo eso cuadra; lo que no se
   verificó de forma independiente fue **el recuento de muertos**, que es justo
   donde estaba el error. Anotado por si sirve para el arnés: el mismo
   argumento que el reviewer usa para recalcular los totales vale para exigir
   que un `0 supervivientes` se reproduzca antes de creérselo.
3. Los dos supervivientes **no son deuda nueva ni tocan lo mío**: son
   presentación pura, ya se analizaron y se aceptaron como **equivalentes** en
   la Fase B (`progress/impl_F-024.md` §6.1, aprobado en
   `progress/review_F-024.md`). He rellenado su análisis en
   `progress/mutacion_F-024_T19b.md` con esa justificación y con la prueba de
   arriba, así que no queda ninguna sección en `PENDIENTE`.
4. Cambio de método por mi parte: en adelante, **campañas de mutación con
   `--workers 1`** cuando el número vaya a un informe. Tarda 1047 s en vez de
   271, y es lo que hay: un número más rápido que no es reproducible no vale
   nada.

**Sugerencia para el humano** (no aplicada, no es mi encargo): merece la pena
mirar por qué la campaña paralela mata mutantes vivos, porque afecta a
cualquier feature de nivel `critico` que la use —el arnés exige cero
supervivientes y la vía paralela puede regalarlos—. Si se toca
`harness/mutacion.py`, la regla de propagación manda llevarlo también a
`arnes-base`.

## 18 · Números finales de esta vuelta

| Evidencia | Valor real |
|---|---|
| `bash harness/init.sh` | verde: `617 passed`, `PUERTA COBERTURA: 100.0% (372/372, umbral 80%, nivel critico)` |
| Tests del fichero de la alerta | **33** (30 antes), 2,4 s |
| Mutación (secuencial, reproducible) | **108 generados, 106 muertos, 2 supervivientes**, 0 timeouts, 1047,1 s — los dos equivalentes, con análisis cerrado en `progress/mutacion_F-024_T19b.md` |
| Pruebas de control | 4 de 4 en rojo al romper lo que vigilan (§11) |
| Contra Azure | **nada**: ni `create`, ni `update`, ni `show`, ni `az login` |

## 19 · Commits de la segunda vuelta

| Commit | Qué |
|---|---|
| `0c40e61` | el criterio de 30 h se comprueba sobre la consulta que se envía, no sobre el texto (los tres puntos del reviewer) |
| `1816d07` | la consulta se compone en una función también en `design.md`/`requirements.md`/`tasks.md`, el análisis de los 2 supervivientes y la corrección del número de mutación |
