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
   `progress/mutacion_F-024_T19.md`. La campaña del 18-ago tenía 2
   supervivientes; los tests añadidos después los matan. **Ningún
   superviviente que analizar.**
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
| Mutantes generados / supervivientes | **108 / 0** (0 timeouts) — `progress/mutacion_F-024_T19.md`. Sin supervivientes que analizar |
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
