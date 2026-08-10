<!-- progress/impl_F-020.md -->
# F-020 · Arnés multi-servicio — Informe del implementer

Rama `feature/F-020-arnes-multiservicio`, rigor **`estandar`**, spec
`specs/F-020-arnes-multiservicio/` aprobada por el humano el 2026-08-10 con
**todas las DA aprobadas tal cual** (DA-1 fichero propio opcional, DA-2 patrón
F-015, DA-3 rigor `estandar`, DA-4 raíz por el camino mono-proyecto, DA-5
supervivientes en un servicio sin suite, DA-6 venv inexistente = KO).

## Qué cambió, en una frase

El arnés ya sabe que un repositorio puede alojar **varios servicios en
subcarpetas** —cada uno con su entorno virtual, sus tests y hasta otro
lenguaje— y comprueba cada uno con lo suyo; y **sin declarar nada se comporta
exactamente igual que antes**, que es el caso de este repositorio.

## Ficheros tocados

### En este repositorio (`datamart-seg-anual`)

| Fichero | Qué cambia |
|---|---|
| `harness/servicios.py` | **Nuevo.** Dataclass `Servicio`, `cargar_servicios` con validación dura, `servicio_de_ruta` (prefijo más largo), `interprete` (venv del servicio, sin fallback silencioso), `tiene_tests`, `linea_shell` y CLI `--validar` / `--shell` |
| `harness/alcance.py` | `es_produccion()` excluye `tests`/`specs`/`progress`/`docs` como **segmento** de ruta a cualquier profundidad, no solo como prefijo de la raíz |
| `harness/cobertura.py` | `fusionar_coberturas()`, `_leer_cobertura()`, `coberturas_de_servicios()` y carga opcional de servicios en `main()`: un solo porcentaje agregado |
| `harness/mutacion.py` | `EjecutorPytest(raiz, argumentos, ejecutable)`, `ejecutor_para()`, `PYTEST_SIN_TESTS = 5` ⇒ SUPERVIVIENTE, y parámetro `ejecutor_de` en `ejecutar_campania()` |
| `harness/init.sh` | Sección **«7 bis. SERVICIOS DEL MONOREPO»**, condicionada a que exista `harness/servicios.json` |
| `tests/test_f020_servicios.py` | **Nuevo.** R1–R5 y la salida de R6 (30 tests) |
| `tests/test_f020_alcance.py` | **Nuevo.** R11, R12 (6 tests) |
| `tests/test_f020_cobertura.py` | **Nuevo.** R13, R14 y el camino mono-proyecto de R2 (10 tests) |
| `tests/test_f020_mutacion.py` | **Nuevo.** R15, R16 y R2 (18 tests) |
| `tests/test_f020_init_multiservicio.py` | **Nuevo.** R3, R6–R10 por análisis textual (12 tests) |
| `tests/test_f020_genericidad.py` | **Nuevo.** R17 (4 tests) |
| `specs/F-020-arnes-multiservicio/tasks.md` | Tareas marcadas |

**No se crea `harness/servicios.json` en este repositorio**, ni `services/`,
ni se toca `main.py`, `config/`, `etl_sigrid/` o `infra/`: el datamart recibe
la mejora sin cambiar de forma (R2, R10, y punto 5 de la feature).

### En `arnes-base` (portado, commits locales, sin push)

`cef7857` y `6035bdd`:

- `arnes-base/harness/{servicios.py, alcance.py, cobertura.py, mutacion.py}`
  actualizados a lo de aquí.
- `arnes-base/harness/servicios.ejemplo.json` **nuevo** en el payload: ejemplo
  documentado que **no activa nada** al instalarse.
- `arnes-base/harness/init.sh`: la misma sección 7 bis, adaptada al portero
  genérico (degrada con AVISO si no hay Python en el PATH).
- `arnes-base/harness/VERSION`: `ARNES_VERSION=1.3.0`, `ARNES_FECHA=2026-08-10`.
- `GUIA_INSTALACION.md`: sección **«Monorepo multi-servicio (desde 1.3.0)»**.
- `instalar_arnes.ps1` **no necesitó cambios**: recorre el payload completo y
  los ficheros nuevos entran como `[NUEVO]` (verificado en T8).

### En `azure-apps` (commit local `ac5fad6`, sin push)

`arnes_base.md` estaba en 1.1.0 y se había saltado la 1.2.x entera. Anotadas la
1.3.0 con la capacidad multi-servicio, la garantía de «sin declarar nada, nada
cambia» y la corrección del código 5 de pytest. El detalle **no se duplica**:
se enlaza a `GUIA_INSTALACION.md`.

## Decisiones de diseño tomadas al implementar

1. **El cuarto campo de `--shell` es el intérprete YA RESUELTO**, no la ruta
   cruda del `venv`. `design.md` describía el campo como `venv` en la firma
   pero exigía en «Riesgos» que la resolución se hiciera en Python y que «el
   bucle de `init.sh` solo reciba la ruta ya resuelta». Se ha implementado lo
   segundo, que es lo que evita heurísticas de shell por sistema operativo.
   En un servicio que no es Python el campo va vacío.
2. **El intérprete se devuelve en ruta absoluta y con barras**
   (`Path.resolve().as_posix()`). El bucle ejecuta la suite con
   `( cd "$RUTA" && "$INTERPRETE" -m pytest ... )`: una ruta relativa a la raíz
   se rompería al cambiar de directorio, y Git Bash no ejecuta rutas con
   contrabarras.
3. **`--validar` resuelve también los intérpretes**, así que un `venv`
   declarado que no existe tumba `init.sh` en la validación (DA-6) en vez de
   más tarde y peor. El mensaje del portero lo dice: «harness/servicios.json,
   o el venv de algún servicio, no son válidos».
4. **La declaración prohíbe el carácter `|` en los campos**, que es el
   separador de `--shell`. Los espacios sí se toleran (el bucle lee con
   `IFS='|'`).
5. **`ejecutar_campania` mantiene el parámetro `ejecutor`** y añade
   `ejecutor_de` opcional: los tests de F-015 que inyectan un doble siguen
   valiendo sin tocarlos, y el caso mono-proyecto no cambia de forma.
6. **El bucle de `init.sh` no cuelga de una tubería.** Con `| while`, bash lo
   ejecuta en un subshell y los `ko` no sumarían a `FALLOS`: un servicio en
   rojo daría el veredicto en verde. Se lee con un here-doc (`done <<EOF`).
   Hay un test que lo vigila.
7. **`cargar_servicios(ruta, raiz)` resuelve la ruta relativa bajo `raiz`**,
   para que una campaña lanzada sobre un worktree (`--raiz`) lea la
   declaración de ESE árbol.

## Fase RED (rigor `estandar`) — salidas reales

### R1–R5 · `harness/servicios.py` (T1)

Test escrito antes que el módulo:

```
$ python -m pytest tests/test_f020_servicios.py -q --no-header
ImportError while importing test module 'tests\test_f020_servicios.py'.
Traceback:
tests\test_f020_servicios.py:17: in <module>
    from harness.servicios import (
E   ModuleNotFoundError: No module named 'harness.servicios'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.16s
```

Después de escribir el módulo: `26 passed in 0.18s`.

### R11, R12 · alcance por segmento de ruta (T2)

```
$ python -m pytest tests/test_f020_alcance.py -q --no-header
F..FFF                                                                   [100%]
________________ test_f020_r11_tests_de_servicio_quedan_fuera _________________
>       assert es_produccion("services/email/tests/test_flujo.py") is False
E       AssertionError: assert True is False
E        +  where True = es_produccion('services/email/tests/test_flujo.py')
__________ test_f020_r11_la_constante_declara_segmentos_no_prefijos ___________
>       assert set(DIRECTORIOS_EXCLUIDOS) == {"tests", "specs", "progress", "docs"}
E       AssertionError: assert {'docs/', 'pr...s/', 'tests/'} == {'docs', 'pro...ecs', 'tests'}
_____________ test_f020_r12_alcance_conserva_rutas_de_subcarpetas _____________
>       assert sorted(lineas) == ["harness/servicios.py", "services/email/app/flujo.py"]
E       AssertionError: assert ['harness/ser...ocs/notas.py'] == ['harness/ser...app/flujo.py']
E         Left contains 2 more items, first extra item: 'services/email/tests/test_flujo.py'
4 failed, 2 passed in 0.08s
```

Es exactamente el agujero que describía el diseño: **los tests de un servicio
entraban como código de producción a mutar y medir**. Después del cambio:
`6 passed`, y `pytest -k f015` sigue en `101 passed` (el cambio solo puede
*sacar* ficheros del alcance, nunca meter nuevos).

### R13, R14 · cobertura agregada (T3)

```
$ python -m pytest tests/test_f020_cobertura.py -q --no-header
ImportError while importing test module 'tests\test_f020_cobertura.py'.
tests\test_f020_cobertura.py:17: in <module>
    from harness.cobertura import fusionar_coberturas
E   ImportError: cannot import name 'fusionar_coberturas' from 'harness.cobertura'
1 error in 0.22s
```

Después: `10 passed in 0.16s`. El test que discrimina de verdad es
`test_f020_r13_porcentaje_agregado_contra_umbral_unico`: sin la re-prefijación,
el fichero del servicio no casa con el alcance y el porcentaje cae de
`83.3% (5/6)` a `66.7% (2/3)`.

### R15, R16 · mutación por servicio (T4)

```
$ python -m pytest tests/test_f020_mutacion.py -q --no-header
ImportError while importing test module 'tests\test_f020_mutacion.py'.
tests\test_f020_mutacion.py:18: in <module>
    from harness.mutacion import (
E   ImportError: cannot import name 'PYTEST_SIN_TESTS' from 'harness.mutacion'
1 error in 0.16s
```

Después: `17 passed in 0.30s`.

### R3, R6–R10 · sección multi-servicio de `init.sh` (T5)

```
$ python -m pytest tests/test_f020_init_multiservicio.py -q --no-header
E       ValueError: substring not found
    def seccion_multiservicio() -> str:
>       inicio = texto.index(MARCA)
FAILED ...::test_f020_r10_seccion_multiservicio_condicionada_a_la_declaracion
FAILED ...::test_f020_r3_init_sh_hace_ko_si_declaracion_invalida
FAILED ...::test_f020_r6_init_itera_servicios_y_agrega
FAILED ...::test_f020_r6_cada_servicio_puede_sumar_al_recuento_de_fallos
FAILED ...::test_f020_r6_el_interprete_de_cada_servicio_es_el_que_resuelve_la_herramienta
FAILED ...::test_f020_r6_la_suite_de_cada_servicio_corre_desde_su_directorio
FAILED ...::test_f020_r7_servicio_sin_tests_aviso_nominal
FAILED ...::test_f020_r8_servicio_no_python_degrada_con_aviso
FAILED ...::test_f020_r8_comando_tests_cuenta_en_el_agregado
FAILED ...::test_f020_r9_una_linea_por_servicio_y_veredicto_unico
10 failed, 2 passed in 0.13s
```

(Los dos que pasaban en rojo son los que comprueban que este repositorio
**no** declara servicios y que las secciones de siempre siguen ahí: pasan
antes y después, a propósito.) Después de escribir la sección: `12 passed`.

### R17 · genericidad (T6)

Aquí la fase RED fue un barrido, no un test que revienta al importar. El
barrido **cazó una mención real** en la primera línea del módulo nuevo:

```
$ python - <<'EOF'  (barrido de vocabulario propio del proyecto)
harness/servicios.py:2: """Servicios de un monorepo: qué partes del repositorio se validan por separado.
```

`partes` es una de las aplicaciones del ecosistema. Corregido a «zonas» y el
barrido queda limpio; el test `test_f020_r17_*` lo deja permanente.

## Verificaciones MANUAL de la spec, ejecutadas con salida real

Las tres son **puramente locales** (instalador contra un directorio temporal,
Git Bash, git local): sin Azure, sin base de datos y sin red salvo un
`pip install pytest coverage` dentro del venv del servicio de prueba. Se
ejecutaron aquí y **el humano solo tiene que revisar la salida**, o repetirla
con los mismos comandos.

### R18 — portado a `arnes-base` (Windows PowerShell 5.1.26100.8972)

```powershell
PS> git -C C:\Users\pgris\PycharmProjects\arnes-base log --oneline -5
6035bdd Arnes 1.3.0: el KO de la seccion multi-servicio nombra tambien el venv
cef7857 Arnes 1.3.0: monorepos multi-servicio
8bff6b2 Arnes 1.2.1: el reviewer verifica los totales de mutacion de forma independiente
5006ee8 Arnes 1.2.0: verificar que los tests son de verdad
aa6a495 Genericizar spec-author.md y anadir BOM al script de energia

PS> Select-String ARNES_VERSION ...\arnes-base\arnes-base\harness\VERSION
VERSION:6:ARNES_VERSION=1.3.0

PS> Get-ChildItem ...\arnes-base\arnes-base\harness\servicios*
Name   : servicios.ejemplo.json      Length : 1134
Name   : servicios.py                Length : 10130

PS> Test-Path ...\arnes-base\arnes-base\harness\servicios.json
False
```

Correcto: `ARNES_VERSION=1.3.0`, están `servicios.py` y
`servicios.ejemplo.json` en el payload, y **no** hay `servicios.json` activo.

### R19 — `GUIA_INSTALACION.md`

```powershell
PS> Select-String -Pattern "servicios" -Path ...\arnes-base\GUIA_INSTALACION.md
345: servicios en subcarpetas —cada uno con su entorno virtual, sus tests y a veces
349: > ausencia de `harness/servicios.json` es la configuración del caso normal: sin
353: ### 1. Declarar los servicios — `harness/servicios.json`
355: Copia `harness/servicios.ejemplo.json` (que viaja en el payload y **no activa
360:   "servicios": [
387: —volver a mono-proyecto sin decir nada— dejaría servicios enteros sin
393: python -m harness.servicios --validar
394: python -m harness.servicios --shell   # lo que consume el bucle de init.sh
413: esquivar una puerta escondiendo código fuera de los servicios.
445: `harness/servicios.py` y `harness/servicios.ejemplo.json` entran como
448: `7 bis. SERVICIOS DEL MONOREPO` justo antes de la puerta de cobertura.
451: 4. Si es un monorepo, crea `harness/servicios.json` a partir del ejemplo y
```

La sección documenta el esquema y ejemplo, los venvs por servicio, los
servicios no Python con `comando_tests`, el servicio sin tests, la cobertura
agregada, la mutación por servicio y el aviso de «sin configurar nada =
mono-proyecto», más la guía de actualización desde 1.2.x.

### R20 — prueba real contra un monorepo de dos servicios

Monorepo temporal creado **fuera de los repositorios**, en el scratchpad de la
sesión (bajo `%TEMP%`):

```
<scratchpad>/monorepo-f020/
├── services/api/          (python: app/flujo.py, tests/test_flujo.py, .venv propio)
├── services/web/          (no python: package.json)
└── .env                   (de mentira, el portero solo comprueba que exista)
```

El venv del servicio se creó con el Python **base** del sistema
(`...\Programs\Python\Python312`), no con el del datamart, y lleva su propio
`pytest 9.1.1` y `coverage`: es un intérprete distinto del que corre el arnés,
que es justo lo que había que probar.

**Instalación con el instalador, desde Windows PowerShell 5.1:**

```powershell
PS> .\instalar_arnes.ps1 -Destino "<scratchpad>\monorepo-f020"

=== Arnes v1.3.0 (2026-08-10) -> ...\monorepo-f020
    El destino no tiene arnes versionado todavia.
    Modo: instalar
[NUEVO]    harness/servicios.ejemplo.json
[NUEVO]    harness/servicios.py
[NUEVO]    harness/init.sh
... (26 ficheros)
[GITIGNORE] 8 regla(s) anadida(s): .env, *.pdf, *.docx, ...
[VERSION]  harness/ARNES_VERSION.md -> v1.3.0
Nuevos: 26 | Ya iguales: 0 | Actualizados: 0 | Conservados: 0 | Saltados: 0
```

`instalar_arnes.ps1` no necesitó ningún cambio, como preveía el diseño.

**Caso 0 — recién instalado, sin declarar nada (mono-proyecto):**

```
$ bash harness/init.sh
[OK] Arnés v1.3.0 (2026-08-10)
[OK] Python: Python 3.12.7
...
[AVISO] No existe tests/ todavía — créala en la primera feature
[OK] PUERTA COBERTURA: N/A (rama (detached): solo aplica en ramas de feature)
----------------------------------------
ENTORNO LISTO. Puedes trabajar.
EXIT=0
```

Ni una línea de la sección multi-servicio: sin declaración no se ejecuta (R10).

**La herramienta, con los dos servicios declarados:**

```
$ python -m harness.servicios --validar
    2 servicio(s): api (python), web (otro)

$ python -m harness.servicios --shell
api|services/api|python|C:/.../monorepo-f020/services/api/.venv/Scripts/python.exe|
web|services/web|otro||sh -c "test -f package.json"
```

**Caso 1 — verde, con línea por servicio (R6, R8, R9):**

```
$ bash harness/init.sh
    2 servicio(s): api (python), web (otro)
[OK] harness/servicios.json válido
.                                                                        [100%]
1 passed in 0.04s
[OK] servicio api (services/api): pytest en verde
[AVISO] servicio web (services/web): lenguaje 'otro', se saltan compilación, lint y pytest
[OK] servicio web (services/web): tests en verde (sh -c "test -f package.json")
[OK] PUERTA COBERTURA: N/A (rama (detached): solo aplica en ramas de feature)
----------------------------------------
ENTORNO LISTO. Puedes trabajar.
EXIT=0

$ python -c "import json;print(sorted(json.load(open('services/api/coverage.json'))['files']))"
['app\\flujo.py', 'tests\\test_flujo.py']
```

El `coverage.json` del servicio numera **respecto al servicio**
(`app\flujo.py`), que es exactamente el caso que `fusionar_coberturas` resuelve.

**Caso 2 — un test del servicio Python en rojo: KO agregado (R6):**

```
1 failed in 0.06s
[KO] servicio api (services/api): pytest en rojo
[AVISO] servicio web (services/web): lenguaje 'otro', se saltan compilación, lint y pytest
[OK] servicio web (services/web): tests en verde (sh -c "test -f package.json")
----------------------------------------
1 comprobaciones fallidas. NO empieces a trabajar.
EXIT=1
```

**Caso 3 — declaración rota: KO, no degradación silenciosa (R3):**

```
harness/servicios.json no es JSON válido: Expecting value: line 1 column 18 (char 17)
[KO] harness/servicios.json, o el venv de algún servicio, no son válidos: el arnés no degrada a mono-proyecto en silencio
----------------------------------------
1 comprobaciones fallidas. NO empieces a trabajar.
EXIT=1
```

**Caso 4 — venv declarado que no existe: KO explícito (R5, DA-6):**

```
servicio 'api': el venv declarado 'services/api/.venv-que-no-existe' no contiene
intérprete (Scripts/python.exe ni bin/python). No se usa el intérprete global en
su lugar: probaría con las dependencias equivocadas
[KO] harness/servicios.json, o el venv de algún servicio, no son válidos: ...
EXIT=1
```

Este caso es el que destapó que el mensaje del portero decía solo
«`servicios.json` inválido» cuando el problema era el venv: corregido aquí y en
`arnes-base`.

**Caso 5 — servicio Python sin `tests/`: AVISO nominal, no KO (R7):**

```
[AVISO] servicio api (services/api): sin directorio de tests — NADIE está comprobando los tests de api
[AVISO] servicio web (services/web): lenguaje 'otro', se saltan compilación, lint y pytest
[OK] servicio web (services/web): tests en verde (sh -c "test -f package.json")
----------------------------------------
ENTORNO LISTO. Puedes trabajar.
EXIT=0
```

**Caso 6 — puerta de cobertura AGREGADA, con git de verdad (R13, R14).** El
monorepo se convirtió en repositorio git (`dev` + `feature/F-001-calentamiento`)
y se le añadió una función nueva **en el servicio** con su test:

```
$ bash harness/init.sh
[OK] servicio api (services/api): pytest en verde
[OK] PUERTA COBERTURA: 100.0% de 2 líneas cambiadas cubiertas (2/2, umbral 80%, nivel estandar)
ENTORNO LISTO. Puedes trabajar.
EXIT=0
```

Las 2 líneas medidas son de `services/api/app/flujo.py`, y **la raíz no tiene
`coverage.json`**: sin la fusión con re-prefijado, la puerta habría dicho que
no hay nada medido. Añadiendo después una función **sin** test:

```
[KO] PUERTA COBERTURA: 75.0% de 4 líneas cambiadas cubiertas (3/4, umbral 80%, nivel estandar)
----------------------------------------
1 comprobaciones fallidas. NO empieces a trabajar.
EXIT=1
```

**Caso 7 — mutación con la suite DEL SERVICIO (R15) y código 5 (R16):**

```
$ python -m harness.mutacion --feature F-001 --base dev
F-001: 1 fichero(s), 4 línea(s) de producción (origen rama, 8855f5b..feature/F-001-calentamiento)
[1/1] muerto        services/api/app/flujo.py:10 [comparacion] return normalizar(texto) == "" -> return normalizar(texto) != ""
1 mutantes evaluados, 1 muertos, 0 supervivientes, 0 timeouts en 0.4 s
```

Que el mutante muera **solo es posible si se ejecutó la suite del servicio**:
la raíz no tiene `tests/`. Y sacando los tests del servicio fuera del árbol:

```
$ ( cd services/api && ./.venv/Scripts/python.exe -m pytest -q --tb=no -p no:cacheprovider )
no tests ran in 0.00s
EXIT_PYTEST=5

$ python -m harness.mutacion --feature F-001 --base dev
[1/1] superviviente services/api/app/flujo.py:10 [comparacion] ...
1 mutantes evaluados, 0 muertos, 1 supervivientes, 0 timeouts en 0.4 s
EXIT=1
```

Antes de esta feature, ese mutante habría contado como **muerto**: la ausencia
de verificación parecía verificación. Es la corrección de R16, y afecta también
a los repositorios de un solo proyecto.

## Campaña de mutación de la propia feature

Lanzada sobre un **worktree aislado** (`git worktree add -b tmp-mutacion-F020
../tmp-mutacion-F020 HEAD`), como recomienda la guía, para no escribir mutantes
en el árbol de trabajo mientras se trabaja en él. La suite pasa allí sin `.env`
(los tests no tocan red ni base de datos), así que **no se copió ningún
secreto** al worktree.

```
python -m harness.mutacion --feature F-020 --raiz ../tmp-mutacion-F020 \
    --salida progress/mutacion_F-020.md
```

**Primera pasada: 46 mutantes, 42 muertos, 4 supervivientes** (133,3 s). Los
cuatro se analizaron uno a uno y **los cuatro eran huecos reales de
verificación, ninguno equivalente**; a cada uno se le escribió su test (commit
`F-020 T10`):

| Superviviente | Por qué ningún test lo cazaba | Test que lo caza ahora |
|---|---|---|
| `mutacion.py:603` `and`→`or` | Nadie comprobaba que, con servicios declarados, un **ejecutor inyectado** siga mandando sobre la factoría. Con la mutación, un doble de test acabaría lanzando suites de verdad, servicio por servicio | `test_f020_r15_main_con_servicios_respeta_el_ejecutor_inyectado` |
| `servicios.py:43` `frozen=True`→`False` | Nadie comprobaba que un `Servicio` sea inmutable, que es lo que impide reescribir una declaración a mitad de ejecución | `test_f020_r1_un_servicio_es_inmutable` |
| `servicios.py:101` `obligatorio=True`→`False` | Los tests usaban `"ruta": ""`, que falla igual por el otro camino de validación. Faltaba el caso de la **clave ausente**, donde la mutación degrada el error a «la ruta 'None' no existe» | `test_f020_r3_ruta_ausente_error` |
| `servicios.py:271` `return 0`→`1` | Nadie comprobaba el código de salida de `--validar` **sin declaración**, que es precisamente el caso mayoritario (mono-proyecto) | `test_f020_r2_validar_sin_declaracion_es_exito_y_lo_dice` |

**Segunda pasada, con los cuatro tests dentro:**

```
[44/46] muerto        harness/servicios.py:271 [entero] return 0 -> return 1
[45/46] muerto        harness/servicios.py:276 [entero] return 0 -> return 1
[46/46] muerto        harness/servicios.py:279 [comparacion] if __name__ == "__main__": ...
46 mutantes evaluados, 46 muertos, 0 supervivientes, 0 timeouts en 122.9 s
Informe: progress/mutacion_F-020.md
```

`progress/mutacion_F-020.md` (el generado por la herramienta, no editado a
mano) recoge **46 generados / 46 evaluados / 46 muertos / 0 supervivientes /
0 timeouts**, campaña completa sin muestreo. No queda ninguna sección de
análisis: no hay supervivientes que analizar. El rigor `estandar` no exige cero
—los admite documentados—, pero salieron cero después de tapar los cuatro
huecos, que es mejor sitio donde estar.

## Desviaciones respecto a la spec

1. **`--shell` emite el intérprete resuelto, no la ruta del venv.** Justificado
   arriba (decisión 1); es lo que exige la sección «Riesgos» del propio
   `design.md`.
2. **Se añadieron helpers no previstos en las firmas de `design.md`**:
   `tiene_tests()` y `linea_shell()` en `servicios.py` (los pedía R7 y la
   salida de R6), y `_leer_cobertura()` / `coberturas_de_servicios()` en
   `cobertura.py`. Ninguno cambia el contrato descrito.
3. **`ejecutar_campania` no cambió de firma**: se añadió `ejecutor_de` como
   parámetro opcional en vez de sustituir `ejecutor`, para no tocar los tests
   de F-015.
4. **Se documentaron las 1.2.x en `azure-apps/arnes_base.md`**, además de la
   1.3.0 que pedía T9: el documento se había quedado en 1.1.0 y anotar solo la
   1.3.0 habría dejado un hueco de dos versiones.
5. **Defecto propio, declarado: el commit `9d58c09` (T8) arrastró ficheros
   ajenos.** Se usó `git add -A` y entraron en el commit los ficheros de
   `specs/F-019-plan-mensual-por-tramos/`, que son de otra feature y de otro
   agente. **No se ha revertido** (deshacerlo ahora reescribiría historia que
   ya tiene commits encima, `bf60eb0` entre ellos, y los ficheros están donde
   deben estar); queda declarado para que el reviewer y el humano lo sepan al
   mirar el diff de la rama. Lección aplicada desde entonces: `git add` de
   ficheros concretos, nunca `-A` a ciegas.

## Verificaciones MANUAL pendientes del humano

Ninguna bloqueante: R18, R19 y R20 se ejecutaron enteras y su salida real está
arriba. El humano puede repetirlas con los comandos exactos de
`specs/F-020-arnes-multiservicio/requirements.md`. El monorepo de prueba sigue
en el scratchpad de la sesión por si quiere mirarlo; es desechable.

## Lo que queda fuera (y no se ha hecho, a propósito)

- La **migración de cada app a su monorepo** (subtrees, reorganización de
  repositorios, sus documentos de `azure-apps/`): esta feature es el
  prerrequisito, no la migración.
- **Pipelines CI/CD**, **mutación o cobertura de servicios no Python**,
  **creación de venvs** y **cambios de estructura en este repositorio**.
- **Instalar la 1.3.0 en otros repositorios**: la decisión es del humano, no se
  propaga sola.

## Estado final del entorno (T11)

```
$ bash harness/init.sh
[OK] Python: Python 3.12.7
[OK] Existe CLAUDE.md ... docs/CONVENTIONS.md
    20 features, 13 abiertas, en curso: ['F-020'], bloqueadas: ['F-003']
[OK] features.json válido
    niveles: critico, documental, estandar; por defecto critico; umbral de cobertura 80%
[OK] harness/rigor.json y niveles declarados: válidos
[AVISO] Hay features en estado blocked: revisa progress/current.md
[OK] Existe .env (no versionado)
[OK] compileall: sin errores de sintaxis
[AVISO] ruff: 127 avisos (deuda previa, no bloquea). Detalle: python -m ruff check .
342 passed, 24 warnings in 3.74s
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 99.4% de 168 líneas cambiadas cubiertas (167/168, umbral 80%, nivel estandar)
[OK] Rama actual: feature/F-020-arnes-multiservicio
----------------------------------------
ENTORNO LISTO. Puedes trabajar.
EXIT=0
```

Los dos AVISO son previos a esta feature: F-003 sigue bloqueada esperando a
F-019, y los 127 avisos de `ruff` son deuda del repositorio (ninguno en los
ficheros de F-020: `python -m ruff check harness/ tests/` sale limpio). **No se
ejecutó la sección multi-servicio**, porque este repositorio no declara
servicios: es la garantía de R10 comprobada sobre el propio arnés.

## Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados y resultado** | **342 passed**, 0 failed (`342 passed, 24 warnings in 3.74s`) |
| **Tests de esta feature** (`pytest -k f020`) | **80 passed** en 6 ficheros |
| **Cobertura de las líneas cambiadas** | **99,4 %** (167/168), umbral 80 %, nivel `estandar` — línea `PUERTA COBERTURA` de `bash harness/init.sh` |
| **Mutantes generados / evaluados** | **46 / 46** (campaña completa, sin muestreo) |
| **Supervivientes** | **0** (42 muertos y 4 supervivientes en la primera pasada; los cuatro analizados y con test propio) |
| **Timeouts de la campaña** | 0 |
| **Tiempo de la campaña de mutación** | **122,9 s** (primera pasada: 133,3 s) |
| **Tiempo de ejecución de la suite** | **3,74 s** (el que imprime pytest dentro de `init.sh`) |
| **Lint de los ficheros de la feature** | `ruff check harness/ tests/` → *All checks passed* |
