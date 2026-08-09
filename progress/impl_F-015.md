<!-- progress/impl_F-015.md -->
# F-015 · Verificar que los tests son de verdad — Informe del implementer

**Rama:** `feature/F-015-verificar-tests` · **Nivel de rigor:** `estandar` ·
**Fecha:** 2026-08-09 · **Estado:** implementación terminada, `init.sh` en
verde, pendiente de review.

Las 16 tareas de `specs/F-015-verificar-tests/tasks.md` están `[x]`, con un
commit `F-015 Tn: ...` cada una.

---

## 1. Qué cambió

### Herramientas nuevas del arnés (`harness/`, paquete Python)

| Fichero | Qué hace |
|---|---|
| `harness/__init__.py` | Marca de paquete: permite `python -m harness.<módulo>` sin trucos de `sys.path` |
| `harness/alcance.py` | Calcula QUÉ LÍNEAS toca una feature, desde el diff de git. Parser del diff unificado, filtro de código de producción y resolución de referencias (rama → commit de merge → error explícito). **Una sola fuente de verdad** para cobertura y mutación |
| `harness/mutacion.py` | Mutador mínimo (`ast` + `subprocess`): seis operadores, un cambio por mutante, campaña con restauración garantizada, timeout, muestreo reproducible por semilla e informe Markdown. CLI con exit 0/1/2 |
| `harness/cobertura.py` | Puerta de cobertura de las líneas cambiadas: cruza el JSON de `coverage` con el alcance, decide sola si aplica y escribe el motivo cuando declara N/A |
| `harness/rigor.py` | Carga y valida `rigor.json`, resuelve el nivel de cada feature (el más exigente si no lo declara) y expone `--validar` para `init.sh` |
| `harness/rigor.json` | Configuración: umbral de cobertura (80 %), timeout por mutante (120 s) y qué exige cada nivel |

### Ficheros modificados

| Fichero | Qué cambia |
|---|---|
| `harness/init.sh` | Sección 2: exige `harness/rigor.json`. Sección **3b nueva**: `python -m harness.rigor --validar`. Sección 6: `compileall` incluye `harness`. Sección 7: la suite corre bajo `coverage` si está instalado. Sección **7b nueva**: `python -m harness.cobertura` como puerta. **Sin un solo número de umbral en el guion** |
| `CHECKPOINTS.md` | Sección **«Niveles de rigor»** con la tabla de exigencias, bloque **C4 bis — El rigor declarado se cumple**, y la nota de N/A ampliada a las tres puertas nuevas |
| `.claude/agents/implementer.md` | **Fase RED** obligatoria (salida real del fallo, para los requisitos centrales) y sección **«Evidencias»** con cuatro números comparables entre features |
| `.claude/agents/reviewer.md` | Paso nuevo: resolver el nivel de rigor y validar contra él (mutación, RED, evidencias, N/A justificados). El informe de review declara el nivel |
| `harness/features.json` | Campo `rigor` en las seis features de la lista que aprobó el humano (DA-4) |
| `requirements-dev.txt` | `coverage>=7.4` (DA-6). **Nunca** en la imagen: el `Dockerfile` solo lee `requirements.txt` |
| `.gitignore` | `coverage.json` |

### Tests nuevos (5 ficheros, 101 tests)

`tests/test_f015_alcance.py`, `test_f015_mutacion.py`, `test_f015_cobertura.py`,
`test_f015_rigor.py`, `test_f015_protocolos.py`. Ninguno abre red ni BBDD: el
ejecutor de pytest es siempre un doble, los diffs y los JSON de coverage son
fixtures de texto, y lo único real que se ejecuta es `git` local de lectura.

### Informes generados

- `progress/mutacion_F-005.md` — línea base sobre código ya cerrado (R18).
- `progress/mutacion_F-015.md` — autoaplicación sobre esta misma feature.

### Fuera de este repositorio

`arnes-base` **1.2.0** (commit local `5006ee8`, sin push): las cinco
herramientas, `rigor.json`, los mismos cambios en su `init.sh`,
`CHECKPOINTS.md`, `implementer.md` y `reviewer.md`, `VERSION` a `1.2.0` y la
sección «Verificación de que los tests son de verdad (desde 1.2.0)» en
`GUIA_INSTALACION.md`. Lo específico de aquí (la línea base de F-005,
`requirements-dev.txt`) NO se portó.

---

## 2. Fase RED — salidas reales

Cada tarea T1–T10 empezó por el test. Estas son las salidas **reales** del
fallo, antes de que existiera el código.

### T1 · `harness/alcance.py` (R2, R4)

```
$ python -m pytest -q -k "f015_r2 or f015_r4" --tb=line
tests\test_f015_alcance.py:12: in <module>
    from harness.alcance import (
E   ModuleNotFoundError: No module named 'harness.alcance'
=========================== short test summary info ===========================
ERROR tests/test_f015_alcance.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
65 deselected, 1 error in 1.27s
```

### T2 · operadores de mutación (R6)

```
$ python -m pytest -q -k "f015_r6" --tb=line
tests\test_f015_mutacion.py:10: in <module>
    from harness.mutacion import Mutante, aplicar_mutante, generar_mutantes
E   ModuleNotFoundError: No module named 'harness.mutacion'
=========================== short test summary info ===========================
ERROR tests/test_f015_mutacion.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
72 deselected, 1 error in 0.92s
```

### T3 · campaña, restauración, timeout e informe (R1, R3, R5, R7)

```
$ python -m pytest -q -k "f015_r1 or f015_r3 or f015_r5 or f015_r7" --tb=line
tests\test_f015_mutacion.py:17: in <module>
    from harness.mutacion import (
E   ImportError: cannot import name 'MUERTO' from 'harness.mutacion'
=========================== short test summary info ===========================
ERROR tests/test_f015_mutacion.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
72 deselected, 1 error in 0.75s
```

### T4 · niveles de rigor (R11, R15)

```
$ python -m pytest -q -k "f015_r11 or f015_r15" --tb=line
tests\test_f015_rigor.py:14: in <module>
    from harness.rigor import (
E   ModuleNotFoundError: No module named 'harness.rigor'
=========================== short test summary info ===========================
ERROR tests/test_f015_rigor.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
93 deselected, 1 error in 0.78s
```

### T5 · puerta de cobertura (R10, R12, R13)

```
$ python -m pytest -q -k "f015_r10 or f015_r12 or f015_r13" --tb=line
tests\test_f015_cobertura.py:15: in <module>
    from harness import cobertura
E   ImportError: cannot import name 'cobertura' from 'harness'
=========================== short test summary info ===========================
ERROR tests/test_f015_cobertura.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
103 deselected, 1 error in 0.75s
```

### T6 · integración en `init.sh` (R10, R11, R13, R15 textuales)

```
$ python -m pytest -q -k "f015_r10 or f015_r11 or f015_r13 or f015_r15" --tb=line
E   assert 'harness.cobertura' in '#!/usr/bin/env bash\n# harness/init.sh\n...'
E   assert 'harness/rigor.json' in '#!/usr/bin/env bash\n# harness/init.sh\n...'
E   assert 'coverage' in '#!/usr/bin/env bash\n# harness/init.sh\n...'
E   assert 'harness.rigor' in '#!/usr/bin/env bash\n# harness/init.sh\n...'
=========================== short test summary info ===========================
FAILED tests/test_f015_cobertura.py::test_f015_r10_init_llama_a_la_puerta_de_cobertura
FAILED tests/test_f015_cobertura.py::test_f015_r11_init_sh_sin_umbral_cableado
FAILED tests/test_f015_cobertura.py::test_f015_r13_init_explica_como_instalar_la_medicion
FAILED tests/test_f015_rigor.py::test_f015_r15_init_valida_valores_de_rigor
4 failed, 20 passed, 97 deselected in 0.73s
```

### T7 · `CHECKPOINTS.md` (R14, R17)

```
$ python -m pytest -q -k "f015_r14 or f015_r17" --tb=line
E   AssertionError: mutaci
    assert 'mutaci' in '<!-- checkpoints.md -->\n# checkpoints — evaluación del estado final\n...'
=========================== short test summary info ===========================
FAILED tests/test_f015_rigor.py::test_f015_r14_checkpoints_define_los_tres_niveles_y_sus_exigencias
FAILED tests/test_f015_rigor.py::test_f015_r14_una_feature_documental_no_puede_requerir_mutacion
FAILED tests/test_f015_rigor.py::test_f015_r17_na_sin_justificacion_prohibido_tambien_en_puertas_nuevas
3 failed, 146 deselected in 0.66s
```

### T8 · `implementer.md` (R8, R9)

```
$ python -m pytest -q -k "f015_r8 or f015_r9" --tb=line
E   AssertionError: assert 'requisitos centrales' in '---\nname: implementer\n...'
E   AssertionError: assert 'evidencias' in '---\nname: implementer\n...'
=========================== short test summary info ===========================
FAILED tests/test_f015_protocolos.py::test_f015_r8_implementer_exige_fase_red_con_salida_real
FAILED tests/test_f015_protocolos.py::test_f015_r8_la_fase_red_se_exige_para_los_requisitos_centrales
FAILED tests/test_f015_protocolos.py::test_f015_r9_implementer_exige_seccion_evidencias_con_numeros
3 failed, 149 deselected in 0.62s
```

### T9 · `reviewer.md` (R16)

```
$ python -m pytest -q -k "f015_r16" --tb=line
E   AssertionError: assert 'nivel de rigor' in '--- name: reviewer model: opus description: aprueba o rechaza el trabajo del implementer...'
=========================== short test summary info ===========================
FAILED tests/test_f015_rigor.py::test_f015_r16_reviewer_valida_contra_el_nivel_de_rigor
1 failed, 152 deselected in 0.67s
```

### T10 · genericidad (R19)

Este es el más interesante de todos: el test **encontró un incumplimiento
real** nada más escribirse, en el único sitio donde se me había colado un
identificador de este proyecto.

```
$ python -m pytest -q -k "f015_r19" --tb=line
E   AssertionError: mutacion.py menciona f-0\d\d
     +  where <re.Match object; span=(17053, 17058), match='f-001'>
=========================== short test summary info ===========================
FAILED tests/test_f015_rigor.py::test_f015_r19_herramientas_del_arnes_sin_menciones_especificas
1 failed, 153 deselected in 0.60s
```

Era el ejemplo del argumento `--feature` (`p. ej. F-001`), cambiado a `F-XXX`.

---

## 3. Decisiones de diseño (y desviaciones)

Las seis decisiones abiertas (DA-1 … DA-6) las cerró el humano el 2026-08-09
tal y como las proponía `design.md`. Se implementaron así. Lo que se decidió
**durante** la implementación:

1. **La línea base de F-005 se ejecutó en un `git worktree` aparte, no en el
   árbol vivo.** No estaba en el diseño y es la desviación más importante.
   Motivo: había una carga `run-all --full` corriendo contra Azure desde este
   mismo directorio, y la campaña escribe mutantes en disco durante segundos.
   Un import perezoso de ese proceso podía haber ejecutado código mutado
   **contra producción**. Efecto secundario bueno: al montar el worktree en
   `c7500d4`, los números de línea del diff coinciden exactamente con los
   ficheros mutados, cosa que no ocurriría contra el árbol de hoy. Para
   soportarlo se añadió la opción `--raiz` a la CLI (genérica, portada).

2. **Un fichero que no aparece en el informe de coverage cuenta entero como
   no cubierto.** `coverage` solo reporta lo que se importa: un módulo nuevo
   que ningún test toca no aparecería, y la puerta daría 100 %. `cobertura.py`
   detecta ese caso y cuenta sus sentencias (vía `ast`) como no cubiertas. Se
   descartó `coverage run --source=.` porque arrastraría `.venv/` y `patches/`
   al informe y obligaría a meter listas de exclusión propias del proyecto en
   un fichero que tiene que ser genérico.

3. **`git log --merges --grep "F-XXX" -n 1` devuelve el merge más reciente**,
   que para F-005 es el del fix posterior (`c9d8d23`), no el de la feature
   (`c7500d4`). La campaña se acotó con `--base c7500d4`. Queda anotado en
   `progress/mutacion_F-005.md` como limitación conocida de la herramienta.

4. **El empalme textual del mutador trabaja con offsets de BYTES**, porque
   `col_offset` de `ast` es un offset UTF-8. Con acentos en la misma línea
   (habitual aquí: todo el código está comentado en español) la aritmética por
   caracteres desalinea la mutación. Hay test específico.

5. **La campaña de mutación NO corre dentro de `init.sh`**, como fijaba el
   diseño: cuesta minutos y el portero tiene que seguir siendo rápido.

6. **Los huecos que la línea base reveló en F-005 no se han parcheado.** Los
   tests de F-005 son el *objeto* de la medición; taparlos aquí falsearía la
   línea base. Quedan analizados y anotados.

---

## 4. Evidencias

| Evidencia | Valor real |
|---|---|
| **Tests ejecutados** | **166 pasan**, 0 fallan (101 de ellos nuevos de F-015) |
| **Tiempo de la suite** | **1,2 s** (`166 passed, 6 warnings in 1.23s`) |
| **Cobertura de las líneas cambiadas** | **97,5 %** — 538 de 552 líneas, umbral 80 %, nivel `estandar` |
| **Mutación de F-015 (autoaplicación)** | **175 mutantes generados, 13 supervivientes** (162 muertos, 0 timeouts) en 270,5 s → **92,6 %** |
| **Mutación de F-005 (línea base)** | **101 mutantes generados, 55 supervivientes** (46 muertos, 0 timeouts) en 129,1 s → **45,5 %** |

Salida literal de la puerta de cobertura en `bash harness/init.sh`:

```
[OK] harness/rigor.json y niveles declarados: válidos
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: 97.5% de 552 líneas cambiadas cubiertas (538/552, umbral 80%, nivel estandar)
```

### La autoaplicación encontró huecos que la cobertura no vio

La campaña sobre F-015 se ejecutó **dos veces**, y ese es el resultado que
justifica la feature entera:

| Vuelta | Mutantes | Muertos | Supervivientes | Puntuación |
|---|---|---|---|---|
| 1ª — con los tests escritos tarea a tarea | 175 | 138 | **37** | 78,9 % |
| 2ª — tras añadir tests contra esos supervivientes | 175 | 162 | **13** | **92,6 %** |

Los 24 mutantes que pasaron de vivos a muertos eran huecos reales que **ni la
fase RED ni el 96,7 % de cobertura de aquel momento habían detectado**. El más
grave: nadie fijaba con un test que el ejecutor invoque pytest con
`check=False`. Con `check=True`, un mutante que hace fallar la suite —que es
el caso **normal**, el de un mutante muerto— habría lanzado una excepción y
tumbado la campaña entera en el primer mutante. Los demás: el parser del diff
contaba líneas sin cabecera de hunk válida inventándose el número; la
frontera exacta del umbral de cobertura (justo el 80 %) no estaba fijada; la
última línea de un fichero sin salto final no se mutaba; el código de salida 2
por error de uso no lo comprobaba nadie.

Los 13 supervivientes restantes quedan analizados en
`progress/mutacion_F-015.md`: 8 mutantes equivalentes, 2 de código defensivo
redundante (la red de seguridad de R5, que el `try/finally` por mutante hace
inalcanzable en el flujo normal) y 3 huecos de riesgo bajo. Ninguno de riesgo
medio o alto. El nivel `estandar` admite supervivientes documentados.

### La línea base de F-005 incomoda, y debe incomodar

**45,5 %**: más de la mitad de las mutaciones aplicadas a las líneas que F-005
escribió pasan la suite sin que nadie se entere. Reparto: 8 equivalentes, 6
huecos de riesgo **alto**, 27 medio y 14 bajo. Los seis de riesgo alto están
en `progress/mutacion_F-005.md` con nombre y línea; en resumen:

- El valor por defecto de `auto_create_db` —el interruptor que la propia
  F-005 declaró **puerta bloqueante** contra el servidor compartido de
  producción— no lo fija ningún test, ni en `config/settings.py` ni en
  `postgres_client.py`.
- Que la conexión administrativa se abra en autocommit (sin ello
  `CREATE DATABASE` falla) no lo comprueba nadie.
- La igualdad de textos y la clasificación de una diferencia como FALLO en
  `fingerprint.py`: el corazón de la verificación de que las vistas responden
  igual en Azure que en local.
- La detección de un paso fallido del pipeline en `main.py`: invertida, el
  CLI daría por buena una ejecución fallida.

### La restauración de R5, verificada sobre código real

Tras 101 mutantes en el worktree de F-005 y 175 en el árbol de trabajo de
F-015, `git status` quedó limpio de cambios no intencionados en ambos casos.
La garantía de que ningún mutante se queda escrito en disco no es solo un
unit test con un doble que lanza excepciones: se ha ejercitado 276 veces
sobre ficheros reales.

---

## 5. Lo que quedó fuera del alcance

Lo que ya declaraba `requirements.md` y se ha respetado: mutación de SQL,
PowerShell o YAML (solo Python de producción); Gherkin; poda de features por
el reviewer; cobertura global del repositorio como puerta; y ejecutar
cualquier cosa contra red o BBDD.

Añadido durante la implementación:

- **No se han corregido los huecos de test de F-005** (ver decisión 6).
- **No se ha declarado `rigor` en las features aún no empezadas** (F-002,
  F-003, F-004, F-006, F-007, F-010, F-011, F-012, F-013). Quedan sin declarar
  y por tanto en `critico`, el más exigente. Es el comportamiento correcto por
  diseño, pero conviene que el humano lo decida en vez de descubrirlo al abrir
  cada una.
- **El fix `e9e80d6`** (`fix/F-005-nosuperuser-azure`) queda fuera de la línea
  base de F-005, como fijaba el diseño.

---

## 6. Verificaciones MANUAL pendientes del humano

**R20 · Portado a `arnes-base`.** Único requisito MANUAL de la feature.

```bash
git -C C:/Users/pgris/PycharmProjects/arnes-base log --oneline -5
grep ARNES_VERSION C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/VERSION
grep -rl "mutacion" C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/
grep -n "mutaci" C:/Users/pgris/PycharmProjects/arnes-base/GUIA_INSTALACION.md | head
```

Resultado obtenido al ejecutarlos (queda al humano darlo por bueno):

```
5006ee8 Arnes 1.2.0: verificar que los tests son de verdad
ARNES_VERSION=1.2.0
arnes-base/harness/{alcance,mutacion,rigor}.py, rigor.json, init.sh
GUIA_INSTALACION.md:287  ### 3. Campaña de mutación — `python -m harness.mutacion --feature F-XXX`
```

**Dos decisiones que el humano debería tomar**, ninguna bloqueante para el
cierre:

1. ¿Se abre una feature de refuerzo de tests para los **6 huecos de riesgo
   alto** que la línea base destapó en F-005?
2. ¿Se declara `rigor` en las 9 features pendientes, o se deja que hereden
   `critico`?

---

## 7. Cómo comprobarlo

```bash
bash harness/init.sh                            # verde, con la puerta de cobertura
python -m pytest -q -k f015                     # 101 tests de esta feature
python -m harness.rigor --validar               # niveles declarados
python -m harness.mutacion --feature F-015      # ~4,5 min, 13 supervivientes
```

La campaña de mutación escribe mutantes en el árbol de trabajo mientras corre.
Sobre F-015 es seguro (solo toca `harness/*.py`, que ningún proceso del ETL
importa). Si alguna vez se lanza sobre código del ETL con una carga en marcha,
hágase en un `git worktree` aparte y con `--raiz`, como se hizo aquí para
F-005.
