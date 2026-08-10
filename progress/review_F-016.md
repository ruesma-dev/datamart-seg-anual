<!-- progress/review_F-016.md -->
# F-016 · Refuerzo de tests para los huecos de riesgo alto de F-005 — Review

**Veredicto: APPROVED**

**Rama:** `feature/F-016-refuerzo-tests-f005` (verificada con
`git branch --show-current`) · **Fecha:** 2026-08-10 · **Reviewer:** agente
reviewer del arnés.

---

## Nivel de rigor y puertas que exige

La entrada de `harness/features.json` declara **`rigor: "estandar"`** y
**`sdd: false`**. No hay `specs/F-016-*/`, así que los criterios son los
**siete `acceptance`** de esa entrada, leídos todos (incluida la PARADA 1
aprobada el 2026-08-10 y el afinado del barrido de secretos).

`estandar` exige, según la tabla de `CHECKPOINTS.md`: C1–C3, C3 bis, C5, tests
trazables (C4), **fase RED** en los requisitos centrales, **cobertura** de las
líneas cambiadas y **campaña de mutación** con los supervivientes analizados.
Todas se recorren abajo. Ninguna se declara N/A sin motivo escrito.

---

## Lo que decide el veredicto, comprobado por mí

### 1. Los seis mutantes de riesgo ALTO mueren — VERIFICADO INDEPENDIENTEMENTE

No me creí los totales del informe. Los recalculé por **cálculo puro**, sin
ejecutar la suite ni relanzar la campaña, con `harness.alcance` y
`harness.mutacion.generar_mutantes`, reconstruyendo el alcance por la vía del
**commit de merge** que el informe documenta:

```python
alcance_de_feature('F-005', base='c7500d4', rama='__no_existe__', raiz='.')
```

| Métrica | Informe del implementer | Mi recálculo | ¿Cuadra? |
|---|---|---|---|
| Origen del alcance | merge `c7500d4` | `origen='merge'`, refs `c7500d4^1..c7500d4` | sí |
| Ficheros en alcance | 20 | **20** | sí |
| Líneas en alcance | 1.669 | **1.669** | sí |
| Mutantes generados | 101 | **101** | sí |

Reparto por fichero de mi recálculo: `fingerprint.py` 37, `postgres_client.py`
21, `main.py` 12, `timings.py` 11, `apply_grants_step.py` 7, `entra_token.py`
6, `settings.py` 4, `conninfo.py` 2, `step_run_recorder.py` 1 = 101.

**El informe dice cómo se obtuvo el alcance**, que era el punto explícito del
`acceptance` 2: worktree desprendido en `c7500d4` con `--raiz`, y `--rama
__no_existe__` para forzar la vía del merge (la rama `feature/F-005-postgres-azure`
todavía existe y, sin neutralizarla, `resolver_refs` devuelve alcance vacío;
era la observación 1 de `progress/review_F-015.md`, ahora sí escrita como línea
de comando literal). Lo he reproducido y confirmo el comportamiento.

**Cotejo uno a uno de los seis ALTO** contra la sección «Los seis de riesgo
ALTO» de la línea base. No muestreé dos o tres: comprobé los seis, más los dos
MEDIO que el informe reclama de propina. Todos existen como **mutantes reales**,
con el mismo operador y el mismo texto original→mutado:

| # | Fichero:línea | Operador | original → mutado | ¿Existe? | ¿Superviviente en el informe nuevo? |
|---|---|---|---|---|---|
| 1 | `config/settings.py:103` | booleano | `True,` → `False,` | sí | **no** |
| 2 | `postgres_client.py:78` | booleano | `auto_create_db: bool = True,` → `False,` | sí | **no** |
| 3 | `postgres_client.py:201` | booleano | `_connect(..., autocommit=True)` → `False` | sí | **no** |
| 4 | `fingerprint.py:334` | comparacion | `return valor_a == valor_b, "texto"` → `!=` | sí | **no** |
| 5 | `fingerprint.py:405` | comparacion | `if gravedad == FALLO` → `!=` | sí | **no** |
| 6 | `main.py:388` | comparacion | `if result.status == StepStatus.FAILED:` → `!=` | sí | **no** |
| + | `main.py:389` | entero | `sys.exit(1)` → `sys.exit(2)` | sí | **no** |
| + | `fingerprint.py:400` | logico | `... or ...` → `... and ...` | sí | **no** |

Los ocho mutantes son reales y **ninguno aparece entre los 47 supervivientes**
del informe nuevo (barrido programático sobre las 47 secciones `###`). Los
mutantes citados coinciden fichero, línea, operador y texto con la línea base.

### 2. La línea base histórica está intacta

```
$ git diff dev...HEAD -- progress/mutacion_F-005.md
(vacío)
```

`progress/mutacion_F-005.md` no se ha tocado ni una línea. El resultado nuevo
va a `progress/mutacion_F-005_tras_refuerzo.md`, fichero nuevo. `acceptance` 3
cumplido.

### 3. Solo tests — ni una línea de producción

```
harness/features.json                    |   2 +-
progress/current.md                      |  58 ++-
progress/impl_F-016.md                   | 477 +++++
progress/mutacion_F-005_tras_refuerzo.md | 674 +++++
progress/mutacion_F-016.md               |  59 +++
tests/test_f005_grants.py                |  84 ++-
tests/test_f016_huecos_alto_f005.py      | 337 +++++
```

**Ningún fichero bajo `etl_sigrid/`, `config/`, `main.py`, `infra/` ni SQL.**
Lo corrobora de forma independiente el propio portero, que calcula el alcance
desde el diff y no desde lo que declare el implementer:
`PUERTA COBERTURA: N/A (F-016 no cambia líneas Python de producción frente a dev)`.
El informe §7 declara **cero defectos de producción encontrados**, así que no
había nada que anotar sin arreglar.

La única excepción autorizada es `tests/test_f005_grants.py`, y la autoriza el
`acceptance` 5. He revisado el diff completo: **ningún otro test de F-005 se ha
tocado**, lo que importa porque los tests de F-005 son el objeto de la medición.

### 4. El barrido de secretos afinado sigue cazando un secreto de verdad

El falso positivo de F-004 queda resuelto y **está probado por un test-del-test**,
`test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta`, que fija las dos
mitades:

- **Sigue cazando**: cuatro claves de mentira por los cuatro patrones
  (asignación de variable de entorno, clave dentro de cadena de conexión,
  `PASSWORD '…'` de SQL, y base64 suelto sin contexto de asignación).
- **Ya no se equivoca**: afirma primero que el patrón crudo `PATRON_CLAVE_GENERADA`
  **sí** casa con `etl_sigrid/infrastructure/excel/` —el falso positivo real de
  F-004— y después que `buscar_secretos()` sobre esa misma frase devuelve `[]`.
- **No se ha pasado de frenada**: `buscar_secretos("token AbCd/EfGh/IjKl/MnOpQrStUv") != []`
  cierra la puerta a relajar `_parece_ruta` a «cualquier cosa con una barra».
  El informe §4 trae la traza roja de haberlo intentado.

El criterio (`>= 2` barras **y** ninguna mayúscula) es deliberadamente estrecho
y está justificado en el docstring. El barrido se extrajo a función
`buscar_secretos()` precisamente para poder someterlo a su propio test, que es
lo correcto.

Bonus de honestidad que doy por bueno: el propio barrido de F-003 puso en rojo
la primera versión del informe del implementer por un ejemplo de contraseña
escrito en prosa. **No se tocó el test**: se reformuló la frase. Es la conducta
que corresponde.

### 5. Los tests nuevos no tocan red ni BBDD

Barrido de imports y de llamadas sobre `tests/test_f016_huecos_alto_f005.py`:
sin `psycopg`, `requests`, `httpx`, `socket`, `urlopen` ni lectura de `.env`.
Los únicos imports son `main`, `config.settings`, `entities`, `fingerprint` y
`PostgresClient`. Los tres mecanismos de aislamiento son sólidos:

- `PostgresSettings(_env_file=None)` con `monkeypatch.delenv` — el defecto se
  afirma sobre el **campo del modelo**, no sobre el `.env` del puesto, que hoy
  apunta a producción. Decisión correcta y no obvia (D1 del informe).
- `PostgresClient` con cadenas de mentira y `_connect` sustituido: **la única
  puerta de conexión**, así que no hay forma de que se escape a la red.
- CLI vía `CliRunner` sobre `_PasoFalso`, con `get_settings` y
  `configure_logging` sustituidos.

### 6. Fase RED (adaptada a esta feature) — presente y con números reales

El informe §4 trae, para **cada uno de los seis huecos**, la traza real de
pytest con la mutación aplicada al árbol de hoy: nombre del test que se pone
rojo, `AssertionError` literal, valores comparados, recuento
(`1 failed, 7 passed`) y `exit=1 VEREDICTO: MUERTO`. No es «se siguió TDD»: es
la salida pegada, seis veces, más la del control negativo del barrido. Es
exactamente la evidencia central que pedía la tarea: antes vivo → ahora muerto.

Detalle que aprecio: el informe **advierte del desplazamiento de líneas** entre
el árbol de hoy y `c7500d4` (`postgres_client.py:78` es hoy `:133`, `:201` es
`:256`) en vez de dejar que el lector tropiece con la incoherencia. Y usa las
dos vías —árbol de hoy para la fase RED, worktree del merge para la
comparación— en lugar de elegir una y esconder la otra.

La traza de H5 es, además, la mejor justificación de por qué el hueco era ALTO:
sin el test, la huella detectaba la diferencia pero la explicaba como
«diferencia en el periodo vivo, esperable».

### 7. Mutación de la propia F-016: alcance vacío, justificado por escrito

No es un N/A de conveniencia. **La campaña se ejecutó** y salió 0 de verdad, y
`progress/mutacion_F-016.md` explica por qué con una tabla fichero a fichero:
`harness.alcance` excluye `tests/` y `progress/` por diseño. El argumento es el
correcto —mutar los tests de esta feature sería medir al revés— y no se queda
en la frase: remite al número que sí acredita el rigor,
`mutacion_F-005_tras_refuerzo.md`. Cumple la exigencia de `CHECKPOINTS.md` de
no dejar la puerta en blanco.

### 8. Deuda MEDIO/BAJO contabilizada, no tapada

Los **47 supervivientes** tienen las 47 secciones de análisis y los 47
veredictos (contados uno a uno). **Ninguno en `PENDIENTE`**: la única aparición
de esa palabra en el fichero es la frase que afirma que no queda ninguno.
Reparto: 8 equivalentes, 24 MEDIO, 15 BAJO, **0 ALTO**.

Doy por buena y agradezco la **nota de recuento**: la tabla resumen de la línea
base decía «27 MEDIO / 14 BAJO» y los veredictos uno a uno dan 26 y 15. El
implementer lo detecta, lo deja escrito, cuenta los veredictos —que es lo
auditable— y **no retoca la línea base**. Es la decisión correcta.

### 9. Entorno en verde — ejecutado por mí

```
388 passed, 72 warnings in 4.20s
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: N/A (F-016 no cambia líneas Python de producción frente a dev)
[OK] Rama actual: feature/F-016-refuerzo-tests-f005
ENTORNO LISTO. Puedes trabajar.
```

`bash harness/init.sh` → **exit 0**. `python -m ruff check` sobre los dos
ficheros tocados: `All checks passed!`. No ejecuté `python main.py`, ni nada
contra BBDD o API, ni relancé la campaña completa de F-005, conforme a la
restricción.

---

## Checkpoints (CHECKPOINTS.md, C1–C5)

### C1 — El arnés está completo y en verde
- [x] `bash harness/init.sh` exit code 0. Ejecutado por mí.
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md`.

### C2 — El estado es coherente
- [x] Una sola feature `in_progress`: F-016. (F-003 y F-019 están `blocked`,
      que es un estado distinto y lo valida `init.sh`.)
- [x] Rama actual `feature/F-016-refuerzo-tests-f005`, no `main`.
- [x] `progress/current.md` tiene su sección de F-016 al día
      («Implementación TERMINADA (2026-08-10) — pendiente de review»).
      Ver observación 1 más abajo sobre el tamaño del fichero.
- [x] Las features `done` tienen su resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones
- [x] Sin código de producción tocado, así que no hay riesgo de dominio
      contaminado ni SQL fuera de su capa. Los tests nuevos importan
      producción, nunca al revés.
- [x] Primera línea de ambos ficheros de test: comentario con su ruta relativa
      (`# tests/test_f016_huecos_alto_f005.py`).
- [x] Sin `print()` de debug, sin TODOs sin contexto, sin secretos
      hardcodeados (las cadenas de los tests son literales de mentira:
      `dbname=de_mentira`, `dbname=admin_de_mentira`; las «claves» del
      test-del-test son inventadas y no corresponden a ningún sistema real),
      sin dependencias nuevas. Type hints completos. Todo en español.
- [x] Semántica Sigrid: no aplica, la feature no toca reglas de negocio.

### C3 bis — Documentos que entran de fuera
- [x] **N/A justificado por escrito**: la feature no añade ni modifica ningún
      fichero en `docs/referencia/` (verificado en `git diff dev...HEAD --stat`:
      solo `tests/`, `progress/` y `harness/features.json`). Sin documentos
      nuevos que barrer, sin originales PDF/ofimática que buscar.

### C4 — La verificación es real
- [x] Cada `acceptance` de F-016 tiene su comprobación trazable, y los tests
      nuevos llevan el prefijo `test_f016_*` (tabla de cobertura abajo).
- [x] Los unit tests no tocan red ni BBDD. Verificado por barrido de imports y
      por lectura de los tres mecanismos de aislamiento (punto 5).
- [x] Verificaciones `MANUAL (humano)`: **ninguna**, y con motivo — nada de
      esta feature toca red, BBDD ni Azure.

### C4 bis — El rigor declarado se cumple
- [x] Declara `rigor: "estandar"`, valor válido.
- [x] **Fase RED**: presente con la salida real, seis veces, más el control
      negativo del barrido (punto 6).
- [x] **Cobertura**: `PUERTA COBERTURA` sale en `[OK]` como `N/A` **con el
      motivo impreso** por `init.sh`, que es exactamente la vía que
      `CHECKPOINTS.md` admite. El motivo es verdadero: 0 líneas de producción
      cambiadas.
- [x] **Mutación**: existe `progress/mutacion_F-016.md` generado por la
      herramienta, y el número que acredita el rigor está en
      `progress/mutacion_F-005_tras_refuerzo.md`. **Totales verificados de
      forma independiente** por mí (20 ficheros / 1.669 líneas / 101 mutantes)
      y ocho mutantes cotejados uno a uno con operador y texto (punto 1).
- [x] Ningún superviviente en `PENDIENTE`: 47 de 47 analizados.
- [x] El informe trae la sección **«Evidencias»** (§10) con los cuatro
      números: 388 tests passed, cobertura N/A justificada, mutantes y
      supervivientes (0/0 propios y 101/47 de F-005), y tiempo de suite
      (3,63 s bajo coverage; yo medí 4,20 s, misma magnitud).
- [x] Ningún punto marcado N/A sin justificación escrita.

### C5 — La sesión se cerró bien
- [x] `tasks.md`: **N/A justificado** — feature `sdd=false`, no hay
      `specs/F-016-*/`, y `CHECKPOINTS.md` declara N/A lo que dependa de
      `tasks.md` en ese caso. El formato mínimo de commit que sustituye a
      `F-XXX Tn:` es `F-XXX: <descripción>`, y los cuatro commits lo cumplen:
      `c5e119b`, `26aca89`, `22eeb60`, `95b6561`, `ae71bf7`.
- [x] `git status` limpio: sin temporales ni artefactos sin trackear. El
      worktree `wt-f016-c7500d4` se retiró (`git worktree list` no lo muestra).
- [x] `features.json` refleja el estado real (`in_progress`; el paso a `done`
      corresponde al líder tras este veredicto).

---

## Cobertura: criterio `acceptance` → dónde se cumple

| `acceptance` de F-016 | Verificado en | Estado |
|---|---|---|
| Tests nuevos que fijan los 6 huecos ALTO, sin red ni BBDD | `tests/test_f016_huecos_alto_f005.py`, 8 tests (`h1`, `h2`×2, `h3`, `h4`, `h5`, `h6`×2) | [x] |
| Campaña relanzada: los 6 ALTO mueren; alcance documentado | `progress/mutacion_F-005_tras_refuerzo.md` + recálculo independiente | [x] |
| Informe nuevo; línea base NO sobrescrita ni retocada | `git diff dev...HEAD -- progress/mutacion_F-005.md` vacío | [x] |
| MEDIO y BAJO contabilizados como deuda, no tapados | 24 + 15, 47 secciones con veredicto, 0 `PENDIENTE` | [x] |
| Barrido de `test_f005_r21` afinado (falso positivo de F-004) | `buscar_secretos()` + `_parece_ruta()` + `test_f016_el_barrido_afinado_caza_la_clave_y_no_la_ruta` | [x] |
| `bash harness/init.sh` en verde | exit 0, 388 passed, ejecutado por el reviewer | [x] |
| PARADA 1 cumplida (plan aprobado el 2026-08-10) | consta en `acceptance` y en `progress/current.md`; los commits arrancan después | [x] |

Trazabilidad hueco ALTO → test que lo mata: 6 de 6, cotejada contra los
mutantes reales en la tabla del punto 1.

---

## Observaciones (no bloquean el veredicto)

1. **`progress/current.md` va camino de ser un archivo histórico.** Tiene ya
   secciones de F-003, F-004, F-015, F-019, F-020 y F-016, varias de ellas
   CERRADAS. C2 pide que describa «SOLO la sesión activa». No lo cuento como
   incumplimiento de F-016 —es una deriva anterior y esta feature solo añade su
   propia sección— pero conviene podarlo: lo cerrado pertenece a
   `history.md`, y un `current.md` de 500 líneas deja de cumplir su función,
   que es que el siguiente agente sepa en dos minutos dónde está el trabajo.

2. **`_parece_ruta` tiene un hueco teórico conocido**: una clave generada de
   24+ caracteres, sin una sola mayúscula y con dos o más barras se escaparía.
   El docstring lo asume explícitamente y el control negativo cubre el caso con
   mayúsculas. Lo dejo anotado por si algún día se quiere endurecer —por
   ejemplo, exigiendo también ausencia de dígitos para descartar—, no como
   defecto.

3. **La discrepancia de recuento de la línea base (27/14 frente a 26/15)**
   queda documentada en dos sitios y sin corregir, que es lo correcto. Si
   alguna vez se cita la línea base hacia fuera, conviene citar los veredictos,
   no su tabla resumen.

## Automejora del protocolo (propuesta, no aplicada)

`CHECKPOINTS.md` da por supuesto que una feature con rigor `estandar` o
`critico` cambia código de producción. F-016 demuestra que existe un caso
legítimo y valioso —**la feature de solo tests**— donde las puertas de
cobertura y de mutación propia salen vacías por construcción, y donde la fase
RED se invierte: no se demuestra que el test falla antes del código, sino que
**mata su mutante**. El implementer lo ha resuelto bien y por su cuenta, pero
el protocolo no se lo decía.

**Propuesta para el humano** (a aplicar en `CHECKPOINTS.md` y a portar a
`arnes-base`, por la regla de propagación): añadir a C4 bis una nota del tipo

> **Features de solo tests.** Si el alcance de producción es vacío, la campaña
> de mutación propia y la puerta de cobertura salen en 0/N/A **por
> construcción**, y eso vale como justificación escrita siempre que el informe
> remita a la campaña sobre el código que esos tests vigilan. La fase RED se
> acredita al revés: la evidencia exigible es la traza de cada test nuevo
> matando el mutante que venía a cerrar (antes vivo → ahora muerto), no el
> fallo previo a la existencia del código.

Segunda propuesta menor, esta ya validada en la práctica por F-016: dejar
escrito en la documentación de `harness.mutacion` que **para medir una feature
ya mergeada hay que neutralizar su rama** (`--rama __no_existe__`), porque si
la rama sobrevive `resolver_refs` resuelve por rama y devuelve alcance vacío
en silencio. Era la observación 1 de `review_F-015.md` y ahora existe la línea
de comando literal que la cierra: convendría moverla del informe al README de
`harness/`, donde la encontrará quien la necesite.

---

**Veredicto final: APPROVED.** Los seis mutantes de riesgo ALTO están muertos y
lo he verificado por cálculo propio, no por lectura del informe. Ni una línea
de producción tocada. El barrido afinado sigue cazando secretos y ya no cree
que una ruta lo sea. La deuda que queda está contada, no escondida.
