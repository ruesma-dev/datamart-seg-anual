<!-- progress/review_F-024_T19_ventana.md -->
# F-024 · T19 bis — review del arreglo de la ventana de la alerta de frescura

Reviewer, 2026-08-19. Rama `feature/F-024-coherencia-cargas-truncadas`.
Alcance revisado: commits `0af5027`, `04d87a1`, `dbd84d0`, `69d8b79`.
**No se re-revisa la Fase B** (ya aprobada en `progress/review_F-024.md`,
sección «Re-review · 2026-08-18»).

**Contra Azure no se ha hecho nada**: ni `create`, ni `update`, ni `show`, ni
`az login`. Ninguna lectura tampoco.

---

## Veredicto

**CHANGES_REQUESTED**

Un solo motivo, y es exactamente el que el humano marcó como bloqueante: **el
criterio de 30 h dentro de la KQL no está protegido por ningún test**. La
suite entera (614 tests) sigue en verde con el filtro temporal desconectado de
la consulta, es decir, con la regla juzgando a 48 h. Es el mismo defecto de
clase que este trabajo venía a cerrar —validar la forma y no el valor—,
trasladado de la ventana al criterio.

Todo lo demás está bien, y bien hecho: la ventana sí está cerrada de verdad,
la spec sí lleva la enmienda, la campaña de mutación es real y los números del
informe cuadran con el recálculo independiente.

---

## Nivel de rigor

`harness/features.json` declara `"rigor": "critico"` para F-024. Puertas que
exige: C1–C5 + C3 bis + fase RED en los requisitos centrales + cobertura de
las líneas cambiadas ≥ 80 % + campaña de mutación con **cero supervivientes**
+ verificaciones `MANUAL (humano)` con comando exacto y resultado real.

---

## Las tres preguntas del humano

### 1 · ¿El agujero de la ventana está cerrado de verdad? — **SÍ**

Comprobado por mí, no leído del informe.

**Los tests ejecutan, no leen.** `_resolver_ventanas()`
(`tests/test_f024_infra_alerta.py:147`) extrae el cuerpo de
`Resolver-VentanaAdmitida` del `.ps1`, lo escribe en un fichero temporal junto
con un guion que lo invoca con 14 umbrales, y lo corre con
`subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-File", ...])`.
Es ejecución real del código del script, no lectura de texto. El resultado va
en `functools.lru_cache`, así que `powershell` arranca **una sola vez** para
los tres tests que lo usan — decisión correcta con la campaña de mutación
lanzando la suite 108 veces.

**Prueba de control ejecutada por mí (la que pidió el humano).** Estropeada la
lista de granularidades del script (`2880` → `1800`, el valor que el ARM
rechazó):

```
5 failed, 25 passed in 1.55s
FAILED test_f024_r23_la_ventana_del_umbral_configurado_es_una_granularidad_admitida
FAILED test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral[25]
FAILED test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral[30]
FAILED test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral[47]
FAILED test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral[48]
```

La suite **se pone roja**, y entre los fallos está el del umbral real
configurado (30). Coincide exactamente con los 5 fallos que declara el
implementer en su §5.3. Script restaurado con `git checkout --`;
`git diff --quiet` limpio.

**Observación menor (no bloqueante), detectada en esa misma prueba.** El test
`test_f024_r22_el_script_declara_las_granularidades_que_admite_azure`
(línea 364) **NO** falló al quitar el `2880` de la lista. Su comprobación es
`re.findall(r"\d+", funcion)` sobre el texto entero de la función, y `2880`
sigue apareciendo en el mensaje del `throw` («la mayor es 2880 min»), así que
el test se pone en verde con un número que ya no está en la lista efectiva.
No es bloqueante porque los tres tests que ejecutan la función sí lo cazan,
pero ese test concreto está midiendo menos de lo que su docstring promete.
Sugerencia: acotar la búsqueda a la línea de `$granularidades = @(...)`.

### 2 · ¿La ventana ancha relaja el criterio? — **EL CÓDIGO NO; LA SUITE SÍ LO PERMITE. BLOQUEANTE**

En el código de hoy el criterio es correcto. `infra/95_create_alert_frescura.ps1`
líneas 175-185: `$ventana` sale de `Resolver-VentanaAdmitida` (48h), el filtro
sale del mismo umbral y entra en la consulta:

```
$filtroTemporal = "| where TimeGenerated > ago({0}h)" -f $horas
$kql = ("ContainerAppConsoleLogs_CL " + ... + $filtroTemporal)
```

**El problema es que nada lo sujeta.** El test que debería cubrirlo,
`test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` (línea 388), busca
`TimeGenerated > ago(...)` en el **código del fichero** y comprueba que la
línea que lo contiene lleva `$horas`. Eso sólo verifica que la variable
`$filtroTemporal` **está definida**. No verifica que **llegue a la consulta**.

Prueba de control ejecutada por mí: dejando intacta la línea 176 y quitando
`$filtroTemporal` de la concatenación de `$kql` —una variable definida y no
usada, que es el resultado típico de un merge o un refactor—:

```
python -m pytest tests/test_f024_infra_alerta.py -q   ->  30 passed in 1.45s
python -m pytest tests/ -q                            ->  614 passed in 6.55s
```

**La suite entera pasa en verde con la regla juzgando a 48 h.** Ese es el
camino que pedía el humano encontrar, y por tanto es bloqueante. Árbol
restaurado con `git checkout --`; `git diff --quiet` limpio.

El mismo eslabón flojo se repite un paso más allá: tampoco hay ningún test que
ate `$kql` → `$consulta` → `--condition-query`. Si esa cadena se rompiera, la
suite tampoco se enteraría.

Riesgo residual del servicio (que Azure Monitor recorte la consulta al rango
de la ventana de forma incompatible con un `ago()` explícito) **no cuenta como
defecto del implementer**: está identificado y escrito en su §7, y sólo se
cierra con el `Activated`/`Deactivated` de la prueba manual. Se anota, no se
imputa.

### 3 · ¿La enmienda está en la spec y no sólo en el código? — **SÍ**

Está escrita en los cinco sitios donde el siguiente la va a buscar, y con la
restricción real de Azure citada literal (el `InvalidRequestContent` completo
con la lista de granularidades):

| Documento | Qué dice |
|---|---|
| `requirements.md`, DA-4 | bloque «Enmienda (2026-08-19)» con el error del ARM literal, la decisión cerrada en dos puntos (ventana derivada / criterio en la KQL) y por qué no lo cazó nadie antes |
| `requirements.md`, R22 | punto (3) reescrito: las dos mitades derivadas del umbral, el tope de 48 h y el fallo antes de llamar a Azure |
| `requirements.md`, R23 | el comando de restaurar pasa a `48h`, con el motivo en línea |
| `requirements.md`, bloque T3 | marca explícitamente que `--help` confirmó la FORMA, no el VALOR |
| `design.md` §8 | pseudocódigo real actualizado, y el `--window-size 30h` de T3 marcado como **FALSO** conservando el texto original |
| `infra/README.md` | lista de granularidades, error del ARM, trampa de `--help`, y la distinción ventana/criterio |
| `infra/env/dev.json` | `$aviso_frescura` reescrito: el umbral es el criterio y de él salen tres cosas derivadas |
| `progress/current.md` | avisa del `48h` en los **dos** sitios donde el líder busca los pasos de T19 |

La corrección de fondo —dejar constancia de que «lo dice `--help`» no es una
confirmación— está tanto en la cabecera del script (líneas 52-64) como en la
spec. Bien hecho: es la lección, no sólo el parche.

---

## Checkpoints

### C1 — El arnés está completo y en verde — **[x]**

- [x] `bash harness/init.sh` termina en verde: `ENTORNO LISTO. Puedes trabajar.`,
      `614 passed`, `PUERTA COBERTURA: 100.0% de 372 líneas cambiadas cubiertas
      (372/372, umbral 80%, nivel critico)`.
- [x] Existen todos los ficheros obligatorios.

El `[AVISO]` de `ruff` (152, deuda previa) y el de features `blocked` (F-003)
no bloquean y no los introduce este trabajo.

### C2 — El estado es coherente — **[x]**

- [x] Una sola feature `in_progress` (F-024); lo valida `init.sh`.
- [x] Rama `feature/F-024-coherencia-cargas-truncadas`, la correcta.
- [x] `progress/current.md` describe la sesión activa y se actualizó con el
      aviso del `48h`.
- [x] N/A para `history.md`: F-024 no es `done` y no se cierra aquí.

### C3 — El código respeta arquitectura y convenciones — **[x]**

- [x] Arquitectura: N/A justificado — este trabajo **no toca ni una línea de
      Python de producción**. Sólo un `.ps1` de `infra/`, un fichero de tests,
      documentación y specs. No hay capa que violar.
- [x] Primera línea con la ruta: `# infra/95_create_alert_frescura.ps1`
      (verificado por `test_f024_r22_script_alerta_frescura_bom_crlf_cabecera`,
      que además comprueba BOM y CRLF byte a byte).
- [x] Estilo del `.ps1`: español sin tildes, comentarios que explican *por
      qué*. Los `Write-Host` son traza deliberada del script de despliegue, no
      prints de debug.
- [x] **Barrido de secretos ejecutado por mí** sobre las líneas añadidas del
      diff `0af5027^..69d8b79` (`infra/`, `tests/`, `specs/`, `progress/`).
      Patrones: GUID, dirección de correo, IP privada (10/172/192),
      `password|passwd|secret|api_key|token|connectionstring` seguido de valor,
      cadena base64 de ≥40 caracteres, `print(` añadido. **Resultado: 0
      hallazgos.** El único positivo de la base64 es
      `1f3d5df5a5519c84fc17b2a451cdce33526d5694`, el SHA base del diff en el
      informe de mutación: falso positivo.
      Aparte, el commit `0af5027` **elimina** un GUID que estaba versionado
      desde `e1ea3ed` en `progress/manual_F-024_fase_c.md`. Fuera del alcance
      pedido, pero correcto y bien justificado: sin él `init.sh` quedaba en
      rojo para cualquiera. Se sustituye por su nombre y no se pierde el dato.
- [x] Sin dependencias nuevas (`subprocess`, `shutil`, `tempfile`,
      `functools` son de la biblioteca estándar).
- [x] Semántica Sigrid: N/A justificado — no se toca dominio ni SQL.

### C3 bis — Documentos que entran de fuera — **N/A justificado**

No se añade ni se modifica ningún fichero en `docs/referencia/`. El barrido de
datos sensibles se ha hecho igualmente sobre todo el diff (ver C3).

### C4 — La verificación es real — **[x]**

- [x] Trazabilidad requisito → test: tabla más abajo, completa.
- [x] Ningún test toca red ni BBDD. Los que ejecutan `powershell` corren un
      fichero temporal escrito por el propio test, con `-NoProfile
      -NonInteractive`, sin entrada externa y sin tocar Azure. Verificado
      leyendo `_resolver_ventanas`.
- [x] Las verificaciones `MANUAL (humano)` están listadas en
      `progress/current.md` con su comando exacto y marcadas como pendientes,
      en los dos sitios, y con el `48h` corregido.

### C4 bis — El rigor declarado se cumple — **[x]**

- [x] `rigor: critico` declarado en `harness/features.json`.
- [x] **Fase RED**: el informe trae la traza real pegada (§4): `19 failed, 11
      passed in 1.57s` antes del arreglo, con los mensajes de assert de los
      cuatro grupos de fallo, y `30 passed` después. Es salida real, no «se
      siguió TDD». Además he reproducido yo dos de esos fallos por mutación
      controlada (ver §1 y §2 de este informe).
- [x] **Cobertura**: `PUERTA COBERTURA` en `[OK]`, 100,0 % de 372 líneas
      (umbral 80 %, nivel `critico`).
- [x] **Mutación — totales verificados de forma independiente.** Recalculado
      con `harness.alcance.alcance_de_feature("F-024")` +
      `harness.mutacion.generar_mutantes` (cálculo puro, sin ejecutar la suite
      ni escribir en disco):

      | | Informe | Mi recálculo |
      |---|---|---|
      | Líneas en alcance | 1268 | **1268** |
      | Ficheros | 12 | **12** |
      | Mutantes generados | 108 | **108** |

      Coincide además **fichero a fichero** (30 en `coherencia.py`, 26 en
      `postgres_client.py`, 20 en `main.py`, 14 en `frescura.py`, 7 en
      `timings.py`, 4+4 en los steps, 3 en `ejecucion.py`, 0 en los cuatro
      restantes). El origen del diff que declara el informe
      (`1f3d5df5…` .. `feature/F-024-coherencia-cargas-truncadas`) es el mismo
      que devuelve `alcance_de_feature`. El informe de mutación no está escrito
      a mano.
- [x] **Supervivientes**: cero, y por tanto ninguna sección en `PENDIENTE`.
      Nivel `critico` satisfecho. No aplica la prueba de control de «cero
      mutantes»: hay 108, no cero.
- [x] Sección **«Evidencias»** presente con los cuatro números: tests
      (614/0), cobertura (100 %), mutantes/supervivientes (108/0) y tiempo de
      la suite (con nota honesta de que 12,48 s y 45,05 s no son comparables
      por la carga de la máquina).
- [x] Ningún punto marcado N/A sin justificar.

**Nota sobre el alcance de la mutación, aceptada.** El implementer avisa de
que este trabajo no cambia Python de producción, así que los 108 mutantes son
los de F-024 completa y **la mutación no llega al `.ps1`**. Es correcto y está
bien declarado. La consecuencia es justamente la del cambio requerido: en
`infra/` la única red es la suite de tests, y ahí hay un hueco.

### C4 ter — Rutas sensibles — **N/A por configuración**

No existe `harness/rutas_sensibles.json` en el repositorio. Según
`CHECKPOINTS.md`, sin declaración el bloque es N/A y no hay nada que
justificar.

*(Propuesta de mejora al final de este informe: este caso es el argumento más
fuerte que ha dado el repositorio para declarar `infra/**.ps1` como ruta
sensible.)*

### C5 — La sesión se cerró bien — **[x] con matiz**

- [x] `tasks.md`: T19 sigue `[ ]`, que es lo correcto —la verificación manual
      contra Azure está en curso—, y `T19 bis` está `[x]` con su verificación.
      La exigencia de «todas las tareas `[x]`» es para el cierre de la feature,
      no para esta revisión parcial.
- [x] Un commit por unidad de trabajo, con el formato `F-024 T19: ...`. Los
      cuatro mensajes explican el porqué, en español.
- [x] Árbol de trabajo limpio: `git status --porcelain` sin salida. Los seis
      `huella_*.csv` sin trackear que había al abrir la sesión ya no están.
- [x] `features.json` refleja el estado real (`in_progress`).

---

## Cobertura: requisito → test

| Requisito | Test que lo cubre | Estado |
|---|---|---|
| R21 · el evento `step_finished`/`build_mart`/`SUCCESS` es estable por los dos lados | `test_f024_r21_orquestador_emite_step_finished_con_step_y_status`, `test_f024_r21_la_alerta_filtra_por_los_tres_terminos` | pasa |
| R21 · columna real del job | `test_f024_r21_la_alerta_mira_el_job_por_la_columna_real` | pasa |
| R22.1 · todo de `$CFG`, sin nombres ni correos | `test_f024_r22_script_alerta_frescura_lee_de_cfg_y_sin_nombres` | pasa |
| R22.2 · idempotencia | `test_f024_r22_la_alerta_es_idempotente` | pasa |
| R22.3a · **ventana** derivada, granularidad admitida, no ISO 8601 | `test_f024_r22_la_ventana_sale_del_umbral_y_no_es_iso_8601`, `test_f024_r23_la_ventana_del_umbral_configurado_es_una_granularidad_admitida` (**ejecuta**), `test_f024_r23_la_ventana_es_la_menor_granularidad_que_contiene_el_umbral` (**ejecuta**, 8 umbrales) | pasa · control verificado |
| R22.3a · la lista de granularidades está completa en el script | `test_f024_r22_el_script_declara_las_granularidades_que_admite_azure` | pasa, **pero débil** (ver §1) |
| R22.3b · **criterio** exacto dentro de la KQL | `test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` | pasa, **pero NO cubre el requisito** (ver §2) — **hueco bloqueante** |
| R22.3c · umbral que no cabe falla antes de llamar a Azure | `test_f024_r23_un_umbral_imposible_falla_antes_de_llamar_a_azure` (**ejecuta**, 4 umbrales) | pasa |
| R22.3d · evalúa cada hora | assert de `--evaluation-frequency 1h` | pasa |
| R22.4 · dispara por ausencia, severidad 2, auto-mitigación | `test_f024_r22_la_alerta_dispara_por_ausencia_y_se_desactiva_sola` | pasa |
| R22.5 · BOM, CRLF, cabecera con ruta | `test_f024_r22_script_alerta_frescura_bom_crlf_cabecera` | pasa |
| R22.6 · README documenta el script en orden | `test_f024_r22_readme_documenta_el_script_en_orden` | pasa |
| R22.7 · `dev.json` declara umbral y nombre | `test_f024_r22_dev_json_declara_umbral_y_nombre` | pasa |
| R23 · la documentación no manda restaurar una ventana inválida | `test_f024_r23_la_documentacion_no_manda_restaurar_una_ventana_invalida` | pasa |
| R23 · prueba de extremo a extremo (Activated/Deactivated) | **MANUAL (humano)** — en curso, evidencia pendiente | pendiente, no imputable |

Todos los requisitos tienen al menos un test. La fila de R22.3b es el motivo
del veredicto: **hay test, pero no cubre lo que dice cubrir**.

---

## Cambios requeridos

### 1 · (BLOQUEANTE) Atar el criterio de 30 h al valor que se envía, no a su forma

**Fichero:** `tests/test_f024_infra_alerta.py:388-415`
(`test_f024_r22_la_kql_acota_el_criterio_con_el_umbral`), y probablemente
`infra/95_create_alert_frescura.ps1:176-185`.

**Defecto.** El test comprueba que existe una línea con
`TimeGenerated > ago(...)` y `$horas`. Eso verifica que `$filtroTemporal`
**se define**, no que **entre en la consulta**. Reproducido: quitando
`$filtroTemporal` de la concatenación de `$kql` y dejando la línea 176
intacta, `pytest tests/ -q` da **614 passed**. La alerta juzgaría con 48 h y
la suite no se enteraría — el mismo defecto de clase que este trabajo cierra
para la ventana.

**Arreglo pedido** (la forma la elige el implementer, pero tiene que comprobar
el **valor**, no el texto):

- extraer la composición de la consulta a una función del `.ps1` —por ejemplo
  `Componer-ConsultaFrescura -Job <j> -UmbralHoras <h>`— y **ejecutarla con
  `powershell`** desde el test, exactamente como ya se hace con
  `Resolver-VentanaAdmitida`, reutilizando `_funcion_ps` y la misma pasada en
  caché de `_resolver_ventanas`;
- asertar sobre la cadena devuelta: que contiene `ago(30h)` con el umbral real
  de `dev.json`, los tres términos de `TERMINOS_DEL_EVENTO` dentro de un
  `has_all`, y `ContainerJobName_s`;
- asertar también que el número de horas del `ago(...)` **coincide con
  `frescuraUmbralHoras`** y **no** con los minutos de la ventana: es la
  comprobación que impide que ventana y criterio converjan por accidente.

**Criterio de aceptación de este punto**, que verificaré rehaciendo la prueba:
desconectar `$filtroTemporal` de `$kql` debe poner la suite **en rojo**.

### 2 · (Menor, mismo commit) Atar `$kql` → `$consulta` → `--condition-query`

**Fichero:** `infra/95_create_alert_frescura.ps1:185, 204`; test nuevo en
`tests/test_f024_infra_alerta.py`.

Ningún test comprueba que la consulta compuesta sea la que viaja en
`--condition-query`. Si se rompiera esa cadena, la regla se crearía con otra
consulta y la suite seguiría verde. Si el punto 1 se resuelve ejecutando la
composición completa, esto cae por su propio peso; si se resuelve de forma más
estrecha, hace falta un assert explícito.

### 3 · (Menor) El test de la lista de granularidades mide menos de lo que promete

**Fichero:** `tests/test_f024_infra_alerta.py:364-385`
(`test_f024_r22_el_script_declara_las_granularidades_que_admite_azure`).

`re.findall(r"\d+", funcion)` barre toda la función, incluidos comentarios y
mensajes de `throw`. Verificado: quitando `2880` de la lista efectiva, este
test **sigue en verde** porque `2880` aparece en el texto del `throw`. Acotar
la búsqueda a la línea de `$granularidades = @(...)`.

---

## Pendiente, no imputable al implementer

- **Evidencia manual de R23** (correo `Activated` con ventana corta, y
  `Deactivated` tras la siguiente carga buena). El nivel `critico` la exige
  para cerrar F-024, y el humano la anexa cuando llegue. La prueba de extremo
  a extremo estaba en curso al escribir esto. **No** cuenta como trabajo que
  el implementer dejara sin hacer: el alcance encargado era el defecto del
  script.
- **Riesgo residual del servicio**: si Azure Monitor recortase la consulta al
  rango de la ventana de forma incompatible con un `ago()` explícito, la regla
  contaría distinto de lo previsto. Identificado y escrito por el implementer
  (§7 de su informe). Se cierra con esa misma prueba manual. Al comprobar el
  `Activated`, conviene mirar en la notificación el número de filas evaluadas:
  es donde se vería si el `ago(30h)` se está aplicando o no.
- **`--evaluation-frequency`**: nadie ha comprobado si sus valores están tan
  restringidos como los de `windowSize`. Con `1h` y `5m` ya han pasado
  llamadas al ARM sin rechazo, así que no urge, pero queda anotado.

---

## Automejora (propuesta, no aplicada)

Este caso es el argumento más claro que ha dado el repositorio para dos
cambios en el arnés. Los dejo escritos para que el humano decida; **no los he
aplicado**.

1. **Declarar `infra/**.ps1` en `harness/rutas_sensibles.json`.** Hoy C4 ter
   es N/A porque el fichero no existe. Los `.ps1` de despliegue son el caso de
   libro que ese bloque describe: la mutación no los alcanza, la cobertura no
   los mide, y su único fallo real —el de hoy— sólo aparece contra el
   servicio. Una verificación declarada que exija «el informe de la feature
   dice qué función del `.ps1` se ha **ejecutado** y con qué valores» habría
   hecho visible el hueco del criterio antes de esta review.

2. **Añadir a `CHECKPOINTS.md`, en C4 bis, la prueba de control del test
   nuevo.** El arnés ya obliga al reviewer a verificar los totales de mutación
   de forma independiente, precisamente porque un informe puede escribirse a
   mano. Le falta la simétrica para los ficheros que la mutación no alcanza:
   cuando un test cubre código no mutable (`.ps1`, `.sql`, YAML, prompts), el
   reviewer debería **romper deliberadamente lo que ese test vigila, en el
   árbol y restaurándolo después, y pegar la traza roja**. Es lo que ha
   destapado el hueco de hoy, y lo he hecho por iniciativa propia, no porque
   el protocolo lo pidiera. Redacción propuesta para C4 bis:

   > - [ ] **Prueba de control de los tests que cubren código no mutable**
   >       (`.ps1`, `.sql`, YAML, plantillas): el reviewer rompe lo que el
   >       test vigila, comprueba que la suite se pone roja y pega la traza en
   >       su informe. Un test verde sobre código que la mutación no alcanza
   >       no es evidencia de nada hasta que se ha visto fallar.

Si el humano las acepta, van también a `arnes-base` en el mismo trabajo, por
la regla de propagación de `CLAUDE.md`.

---

## Nota de método

Todas las mutaciones de control de este informe se aplicaron en el árbol real
y se revirtieron con `git checkout --`. Estado final comprobado:
`git status --porcelain` sin salida y `git diff --quiet` en verde. El
repositorio queda exactamente como estaba en `69d8b79`.

---
---

# Re-review · 2026-08-19 (segunda pasada)

Reviewer, 2026-08-19, tarde. Alcance: commits `0c40e61` y `1816d07` (más
`2c64dae`, de una línea del informe). La primera pasada de arriba **no se
reescribe**: queda tal cual, y este bloque cuenta qué ha cambiado.

`bash harness/init.sh` en verde al abrir y al cerrar esta pasada:
**`617 passed`** (614 antes) y `PUERTA COBERTURA: 100.0% de 372 líneas
cambiadas cubiertas (372/372, umbral 80%, nivel critico)`.

**Contra Azure, nada**: ni `create`, ni `update`, ni `show`, ni `az login`.
Sabiendo que la alerta está restaurada a `48h`/`1h` esperando el
`Deactivated`, no se ha ejecutado ningún comando de `az` ni el script.

## Veredicto de la segunda pasada

**APPROVED**

Los tres puntos están corregidos, y el bloqueante está cerrado de verdad, no
movido de sitio: lo he comprobado repitiendo mi propio experimento contra el
árbol de ahora. Además, la corrección del número de mutación que trae el
implementer es **cierta**, y la he verificado de forma independiente
ejecutando la campaña completa yo mismo.

Queda **pendiente, no imputable**: la evidencia manual de R23 (correo
`Activated` / `Deactivated`), que lleva el líder con el humano y que el nivel
`critico` exige para cerrar F-024. Mi veredicto cubre código, tests y
documentación, y no depende de ella.

## Punto 1 · El bloqueante está cerrado, no desplazado

La composición de la consulta pasa a `Componer-ConsultaFrescura`
(`infra/95_create_alert_frescura.ps1:142-186`), que los tests **ejecutan** con
`powershell` y sobre cuyo valor devuelto afirman. El mecanismo se amplía sin
encarecerse: `_ejecutar_funciones_del_script()` evalúa en **una sola pasada**
las ventanas de los 14 umbrales *y* la consulta real, y la cachea.

Cinco experimentos sobre el árbol de ahora, todos aplicados al árbol real y
restaurados desde copia previa (nunca con `git checkout`, por la lección de
§12 del implementer):

| # | Manipulación | Resultado | Lectura |
|---|---|---|---|
| **E1** | quitar `$filtroTemporal` de la concatenación de `$kql`, dejando su definición intacta — **mi experimento de la primera pasada, literal** | **ROJO**: `1 failed, 616 passed` (`test_f024_r22_la_kql_acota_el_criterio_con_el_umbral`) | **el bloqueante está cerrado**: antes daba `614 passed` |
| **E2** | lista de granularidades mutilada (`2880` → `1800`) | **ROJO**: `7 failed, 26 passed` | punto 3 cerrado (antes eran 5 fallos y el test de la lista **no** estaba entre ellos; ahora sí) |
| **E3** | `-UmbralHoras ($horas + 18)` en la llamada | **VERDE**: `617 passed` | **agujero residual**, ver abajo |
| **E4** | `-UmbralHoras 48` literal | **ROJO**: `1 failed` (`...es_la_que_viaja_en_condition_query`) | el eslabón textual sujeta el caso realista |
| **E5** | `--condition-query $consultaVieja` | **ROJO**: `1 failed` (mismo test) | punto 2 cubierto |

**El agujero equivalente un paso más allá existe, pero es residual y está
declarado.** E3 pasa porque el test que ejecuta la función la llama con el
umbral de `dev.json`, mientras que lo que el *script* le pasa se comprueba por
texto (que la llamada lleve `$CFG.job` y `$horas`). Una aritmética deliberada
—`($horas + 18)`— satisface el texto y cambia el valor. No lo considero
bloqueante por tres razones: no es un accidente plausible (no es lo que deja
un merge mal resuelto, que es E1 y cae); los dos caminos realistas (E4, E5)
caen; y el implementer **declara el límite por escrito** en su §9, con el
motivo —cerrarlo del todo exigiría extraer la invocación de `az` a una función,
en un script que no puede probar contra Azure y cuya regla está ahora mismo en
mitad de la verificación manual—. Es una decisión razonada, no un olvido. Lo
dejo anotado para cuando la alerta esté verificada y el script se pueda tocar
con red.

Mención aparte para dos tests que van más allá de lo que pedí y que son los
que más valor añaden:

- `test_f024_r22_la_kql_acota_el_criterio_con_el_umbral` no solo comprueba que
  el `ago(...)` lleva las horas del umbral: comprueba que **no coinciden con
  las de la ventana**. Es la afirmación que impide que criterio y ventana
  converjan por accidente, que era el fondo del problema.
- `test_f024_r22_el_nombre_de_la_consulta_es_el_que_cuenta_la_condicion` cruza
  `--condition "count 'X' < 1"` con el nombre que devuelve la función. Ese
  fallo —la regla contando un resultado inexistente y quedándose muda sin que
  Azure proteste— no lo había pedido nadie y es de los que no se descubren
  hasta que falta un correo.

## Punto 2 · La corrección de la campaña de mutación: **confirmada**

### Lo que verifiqué, y cómo

**a) Ningún test puede matar esos mutantes.** `grep -rn "bold" tests/` →
**cero coincidencias**.

**b) Los dos mutantes están vivos.** Aplicados a mano en el árbol real
(`main.py:564` y `:567`, `bold=True` → `bold=False`), la suite entera pasa:
**`617 passed`**. Restaurado desde copia previa.

**c) La campaña completa, ejecutada por mí.**
`python -m harness.mutacion --feature F-024 --workers 1`:

```
108 mutantes evaluados, 106 muertos, 2 supervivientes, 0 timeouts en 970.8 s
```

Y los dos supervivientes de mi campaña son **exactamente** `main.py:564` y
`main.py:567`, los dos `bold=True → bold=False`. Los totales de mi informe y
los del implementer (`progress/mutacion_F-024_T19b.md`) son **idénticos**,
comprobado con `diff` sobre las líneas de totales.

> Mi campaña sobrescribe `progress/mutacion_F-024.md` (el informe de la Fase
> B). Lo he restaurado con `git checkout --` tras guardar mi resultado fuera
> del repositorio. El fichero queda como estaba.

**Conclusión: el `108 / 108 / 0` de la primera vuelta era falso y el número
bueno es `108 / 106 / 2`.** El implementer tiene razón, lo ha corregido por su
cuenta antes de que nadie se lo pidiera, y ha marcado el error en su informe
anterior en vez de reescribirlo. Eso es exactamente lo que hay que hacer con
un número publicado que resulta ser falso.

Los dos supervivientes son presentación pura (`bold` de dos cabeceras
decorativas), ya analizados y aceptados como **equivalentes** en la Fase B, y
su análisis está completo en `mutacion_F-024_T19b.md`: **ninguna sección en
`PENDIENTE`**. El nivel `critico` queda satisfecho con esa justificación
escrita, que es la que ya aceptó la review de la Fase B.

### Causa raíz del fallo del arnés, localizada y reproducida

No me quedé en confirmar el número, porque el coordinador señalaba que afecta
a cualquier feature `critico` que use la vía paralela. **La causa está
identificada, es determinista y no es una condición de carrera.**

Son dos defectos que se suman:

**1. En un worktree, la suite de este repositorio está rota de base.**
Creé un worktree igual que los que crea el modo paralelo
(`git worktree add --detach <ruta> HEAD`) y ejecuté la suite **sin mutar nada**:

```
3 failed, 614 passed          # exit code 1
FAILED tests/test_f015_cobertura.py::test_f015_r12_la_rama_actual_se_lee_de_git
FAILED tests/test_f024_cli.py::test_f024_r19_la_ayuda_ensena_el_umbral_y_el_paso_por_defecto
FAILED tests/test_f024_dominio.py::test_f024_r1_batch_id_tiene_forma_y_es_unico
```

Dos motivos, los dos consecuencia directa del diseño del modo paralelo: el
worktree está en **detached HEAD** (`rama_actual()` devuelve `""`, de ahí el
fallo de F-015) y **no tiene los ficheros no versionados**, empezando por
`.env` (comprobado: el árbol principal sí lo tiene, el worktree no).

**2. `harness/mutacion.py:312-314` cuenta cualquier suite roja como mutante
muerto.**

```python
if proceso.returncode in (0, PYTEST_SIN_TESTS):
    return SUPERVIVIENTE
return MUERTO
```

No distingue «la suite falló **por el mutante**» de «la suite estaba fallando
**de todas formas**». Con la suite base en rojo dentro del worker, **todo
mutante sale muerto**. De ahí el `108/108/0` exacto: no es que matara dos
mutantes de más, es que el modo paralelo **no puede dar otro resultado** en
este repositorio.

Lo más incómodo: la docstring de `harness/mutacion_paralela.py` **ya predice
este fallo** entre sus «limitaciones conocidas» («un proyecto que las viole
verá la suite roja en el worker y contará mutantes “muertos” de más»). Está
escrito y no se comprueba. Un aviso en un docstring no es una salvaguarda.

### Alcance del daño: acotado, y esta es la buena noticia

El modo paralelo entró en este repositorio el **2026-08-18** con la v1.5.0 del
arnés (`15676f7`). Todos los informes de mutación anteriores —F-003, F-004,
F-005, F-015, F-016, F-019, F-020— son de campañas **en serie** y **no están
afectados**. En particular `mutacion_F-020.md` (46/46/0), que a primera vista
tiene la misma huella sospechosa de «cero supervivientes», es del 2026-08-10 y
por tanto anterior al modo paralelo: **su cero es legítimo**.

El único informe afectado de todo el repositorio es
`progress/mutacion_F-024_T19.md`, que es justo el que el implementer ya ha
marcado como falso. **No hace falta revisión retroactiva de ninguna feature
cerrada.** Para otros repositorios con la v1.5.0 instalada, la conclusión no
se traslada sin comprobarlo.

## Checkpoints de la segunda pasada

Solo lo que cambia respecto a la primera pasada; el resto se mantiene.

- **C1** `[x]` — `init.sh` en verde, `617 passed`, cobertura 100 % (372/372).
- **C2** `[x]` — sin cambios: una feature `in_progress`, rama correcta.
- **C3** `[x]` — sigue sin tocarse Python de producción; el `.ps1` mantiene
  BOM, CRLF, cabecera con ruta y español sin tildes. **Barrido de secretos
  repetido por mí** sobre las líneas añadidas de `0c40e61` y `1816d07`, con
  los mismos patrones de la primera pasada: **0 hallazgos**.
- **C3 bis** — N/A justificado: no se toca `docs/referencia/`.
- **C4** `[x]` — trazabilidad completa; la fila que en la primera pasada
  marqué como «hay test pero no cubre el requisito» (R22.3b) queda cubierta
  por los cuatro tests nuevos. Ningún test toca red ni BBDD.
- **C4 bis** `[x]` — **el punto que más cambia**:
  - **Fase RED**: traza real pegada (§10), `19 failed, 14 passed` antes y
    `33 passed` después.
  - **Cobertura**: `[OK]`, 100 % de 372 líneas.
  - **Mutación**: totales **verificados de forma independiente por mí, esta
    vez incluyendo el recuento de muertos**, no solo el alcance y la
    generación. `108 / 106 / 2`, coincidentes con los del implementer.
  - **Supervivientes**: dos, equivalentes, con análisis completo. Ninguno en
    `PENDIENTE`.
  - **Evidencias**: sección presente con los cuatro números y, además, con la
    corrección del número anterior marcada en vez de borrada.
  - **Pruebas de control**: 4 declaradas por el implementer, y 5 ejecutadas
    por mí, de las cuales 4 en rojo.
- **C4 ter** — N/A por configuración: no existe `harness/rutas_sensibles.json`.
- **C5** `[x]` — `tasks.md` con `T19 bis` actualizado y T19 correctamente
  `[ ]` (la verificación manual sigue en curso). Árbol de trabajo limpio.
  `features.json` refleja `in_progress`.

## Lo que hice mal en la primera pasada

Lo dejo escrito porque es la parte útil de este episodio para el siguiente
reviewer. En la primera pasada verifiqué el alcance y la generación de la
campaña (1268 líneas, 12 ficheros, 108 mutantes) y los di por buenos, que es
literalmente lo que pide `CHECKPOINTS.md` en C4 bis. **Pero el error no estaba
en la generación: estaba en el recuento de muertos, que el protocolo no manda
verificar.** Recalcular los mutantes con `harness.alcance` y
`harness.mutacion.generar_mutantes` es un cálculo puro y barato, y por eso el
protocolo lo pide; comprobar los muertos exige volver a correr la campaña, que
son 16 minutos. Se me escapó por seguir el protocolo al pie de la letra en vez
de preguntarme qué número era el que sostenía el veredicto. Un
`0 supervivientes` en nivel `critico` es exactamente el número que hay que
desconfiar, porque es el que nadie vuelve a mirar.

## Automejora (propuestas, NO aplicadas)

Las dos de la primera pasada siguen en pie (declarar `infra/**.ps1` como ruta
sensible; exigir en C4 bis la prueba de control de los tests que cubren código
no mutable). Esta pasada añade tres más, todas sobre el mismo hueco: **un
número de mutación no vale nada si no es reproducible.**

**3 · Medir la línea base antes de repartir (`harness/mutacion_paralela.py`).**
Antes de crear worktrees y evaluar nada, correr la suite **sin mutar** en un
worker y exigir `returncode == 0`. Si sale roja, **abortar la campaña** con el
motivo, en vez de producir un informe de ceros. Es la comprobación que
convierte la «limitación conocida» ya escrita en el docstring en una
salvaguarda real. Coste: una ejecución de suite.

**4 · Distinguir «suite rota» de «mutante muerto» (`harness/mutacion.py`).**
Hoy cualquier `returncode` distinto de 0 y 5 es `MUERTO`. Los códigos de
pytest no son equivalentes: `1` es «tests fallaron» (mutante muerto de
verdad), pero `2` (interrumpido), `3` (error interno) y `4` (error de uso)
significan que la suite **no llegó a juzgar nada**. Tratarlos como un
resultado propio —`INVALIDO`— y hacer que la campaña se detenga si aparecen,
en vez de contarlos como éxitos.

**5 · Que una campaña interrumpida no deje el árbol mutado.** Lo aportó el
coordinador y lo he vivido en esta misma review: mi campaña quedó huérfana
tras una caída, siguió mutando ficheros de producción, y al matarla dejó un
mutante aplicado en `etl_sigrid/infrastructure/postgres/frescura.py`. El
riesgo real es **commitear un mutante creyendo que es código**. Dos medidas,
ninguna cara:
   - dejar una **marca en disco** mientras la campaña está viva (por ejemplo
     `progress/.mutacion_en_curso`, con el PID y el fichero que está mutado en
     ese momento), que `harness/init.sh` mire y convierta en `[ERROR]` con
     instrucciones de restaurar;
   - que la campaña, al arrancar, **compruebe esa marca** y se niegue a
     empezar si una anterior no cerró limpiamente.

   Un corolario para `CHECKPOINTS.md` o para el protocolo del reviewer:
   **mientras una campaña de mutación esté corriendo, nadie toca el árbol** —
   ni para restaurar lo que parece un resto abandonado, porque puede ser el
   mutante en vuelo, y entonces el recuento entero deja de valer. Es lo que
   invalidó mi primera campaña. Por eso, en esta pasada, no escribí ni este
   informe mientras la campaña estaba en marcha.

Si el humano acepta cualquiera de las cinco, la regla de propagación de
`CLAUDE.md` manda llevarlas también a `arnes-base`.

## Nota de método de la segunda pasada

Los cinco experimentos del punto 1 y la mutación manual de los dos `bold` se
aplicaron sobre el árbol real y se restauraron **desde copia previa**, no con
`git checkout`. Mi campaña de mutación sobrescribió
`progress/mutacion_F-024.md`, restaurado después con `git checkout --` tras
copiar la evidencia fuera del repositorio. Estado final comprobado:
`git status --porcelain` sin ficheros de producción modificados,
`bash harness/init.sh` en verde con **`617 passed`**.

Incidente propio, para que conste igual que el implementer anotó el suyo: una
caída a mitad de esta pasada dejó mi primera campaña huérfana y corriendo, y
el intento de sanear el árbol le quitó el mutante que estaba evaluando. Ese
recuento se descartó entero y la campaña se relanzó desde cero. El número que
sostiene este veredicto es el de la segunda, completa y sin interrupciones.
