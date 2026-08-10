<!-- specs/F-020-arnes-multiservicio/design.md -->
# F-020 · Arnés multi-servicio — Diseño técnico

## Contexto y hallazgos previos al diseño

Leído el arnés genérico 1.2.1 (`arnes-base`) y el de este repositorio, el
punto de partida real es este:

1. **`harness/alcance.py` ya funciona con subcarpetas… casi.** El diff se
   calcula con `git diff` en la raíz y las rutas son relativas a la raíz, así
   que `services/email/app/flujo.py` entra bien en el alcance. Pero
   `es_produccion()` excluye `tests/`, `specs/`, `progress/` y `docs/` solo
   como **prefijo** (`startswith`): `services/email/tests/test_x.py` NO
   empieza por `tests/` y entraría como código de producción a mutar y medir.
   Es el ajuste principal que exige el punto (2) de la feature.
2. **`harness/cobertura.py` cruza el alcance con UN `coverage.json` de la
   raíz.** En un monorepo cada servicio ejecuta su suite desde su directorio
   con su venv, y su `coverage.json` numera las rutas **relativas al
   servicio** (`app/flujo.py`, no `services/email/app/flujo.py`). Sin fusión
   con re-prefijado, ningún fichero de servicio casaría y saldría «no
   medido».
3. **`harness/mutacion.py` lanza `sys.executable -m pytest` con cwd en la
   raíz.** En un monorepo eso ejecutaría la suite equivocada (o ninguna) con
   el intérprete equivocado. Además, `EjecutorPytest` traduce cualquier exit
   code ≠ 0 como mutante MUERTO; pytest devuelve **5** cuando no recoge
   ningún test, así que en un servicio sin tests todos los mutantes
   «morirían» sin que nadie los cazara. Hay que corregirlo (R16).
4. **`init.sh` (arnes-base 1.2.1) ya degrada por lenguaje a nivel de
   repositorio** (`PROYECTO_PYTHON`, `COMANDO_TESTS`), pero es un interruptor
   único: no sabe que un mismo repo tenga un servicio Python y otro Node.
5. **`instalar_arnes.ps1` recorre el payload completo**: un fichero nuevo en
   `arnes-base/harness/` se instala solo como `[NUEVO]`. No necesita cambios
   de código para esta feature.

## Decisiones de diseño

### D1 — Declaración explícita en `harness/servicios.json`, no autodescubrimiento

Un monorepo declara sus servicios en un fichero **opcional** propio del
arnés:

```json
{
  "$doc": "Declaración de servicios del monorepo. Sin este fichero, el arnés es mono-proyecto.",
  "servicios": [
    { "nombre": "email", "ruta": "services/email", "lenguaje": "python",
      "venv": "services/email/.venv" },
    { "nombre": "api",   "ruta": "services/api",   "lenguaje": "python",
      "venv": "services/api/.venv" },
    { "nombre": "web",   "ruta": "services/web",   "lenguaje": "otro",
      "comando_tests": "npm test --silent" },
    { "nombre": "infra", "ruta": "infra",          "lenguaje": "otro" }
  ]
}
```

**Descartado el autodescubrimiento** (buscar subcarpetas con
`pyproject.toml`/`requirements.txt` o un fichero marcador): los monorepos
nacerán de git subtree con layouts heterogéneos; el descubrimiento no puede
adivinar ni el venv, ni el `comando_tests` de un servicio Node, ni distinguir
`infra/` (scripts sueltos) de un servicio con suite; y un falso positivo
convertiría avisos en KOs fantasma. La declaración explícita es un fichero de
seis líneas por servicio que se escribe una vez.

**Descartada la clave dentro de `harness/rigor.json`**: rigor responde a
«cuánta vigilancia merece una feature»; servicios responde a «qué forma tiene
el repositorio». Mezclarlos acopla dos ciclos de vida distintos y obligaría a
todo repo mono-proyecto a llevar una clave vacía. Fichero propio, ausente por
defecto: la ausencia ES la configuración del caso mayoritario.

En el payload de `arnes-base` viaja `harness/servicios.ejemplo.json`
(documentación ejecutable, no activa); el fichero activo `servicios.json` lo
crea cada monorepo. Así el instalador nunca convierte un mono-proyecto en
multi-servicio por accidente.

### D2 — Dónde se implementa y se prueba: patrón F-015

El código se desarrolla y testea **en este repositorio** (que es donde hay
suite, venv y puertas de rigor funcionando) y se porta a `arnes-base` con
subida a **1.3.0** en el mismo trabajo, igual que F-015. Motivo: `arnes-base`
no tiene infraestructura de tests propia (es el payload, no un proyecto con
arnés instalado), y montarla ahí para esta feature sería una segunda obra;
mientras que los `test_f020_*` en `tests/` de este repo quedan además como
guardia permanente de las herramientas, junto a los `test_f015_*`.

Esto encaja con el punto (5) de la feature: el datamart **no cambia de
estructura** (ni `services/`, ni `servicios.json`); «recibe la mejora» son
los ficheros de `harness/` e `init.sh` actualizados, cuyo comportamiento
mono-proyecto es idéntico por diseño (R2, R10). La fricción esperada es cero
y lo vigila la propia suite. — Ver decisión abierta DA-2.

### D3 — `init.sh`: bucle por servicio encima del flujo actual, no reescritura

Con `servicios.json` presente, `init.sh` añade una sección que:

1. Valida la declaración (`python -m harness.servicios --validar`); inválida
   ⇒ KO (R3).
2. Obtiene los servicios en formato parseable por shell
   (`python -m harness.servicios --shell`, una línea
   `nombre|ruta|lenguaje|venv|comando_tests` por servicio) y los recorre:
   - **Python**: resuelve el intérprete (venv del servicio o el global),
     ejecuta la suite desde el directorio del servicio bajo `coverage` si
     está disponible, y vuelca `coverage.json` **dentro del servicio**.
     Sin directorio de tests ⇒ AVISO nominal (R7). Fallo ⇒ KO del agregado.
   - **Otro lenguaje**: aviso de degradación; con `comando_tests`, lo ejecuta
     desde su ruta y su fallo es KO (R8).
   - Una línea `[OK]/[AVISO]/[KO]` por servicio (R9).
3. La suite de la **raíz** (si existe `tests/` en la raíz) se ejecuta como
   hoy: la raíz se comporta como un «servicio implícito» sin declararse.

Lo que NO cambia: `compileall` sigue siendo una pasada única desde la raíz
(la sintaxis no depende de venvs); `ruff` sigue siendo global e informativo;
las secciones de ficheros del arnés, features, rigor, `.env` y rama quedan
igual. Sin `servicios.json`, la sección nueva no ejecuta nada (R10).

Degradación sin Python en el PATH: la sección multi-servicio necesita Python
para leer la declaración; sin intérprete alguno degrada con AVISO explícito,
igual que hoy hace la validación de rigor.

### D4 — Cobertura: fusionar los `coverage.json` re-prefijando rutas

`harness/cobertura.py` gana una función pura
`fusionar_coberturas(cov_raiz, coberturas_servicios)` donde
`coberturas_servicios` es `[(ruta_servicio, dict_coverage), ...]`: produce un
único dict estilo coverage cuyo `files` re-prefija cada clave del servicio
con `ruta_servicio/`. El resto del cálculo
(`cobertura_lineas_cambiadas`) queda **intacto**: sigue cruzando un dict de
coverage con el alcance de rutas raíz-relativas. `main()` carga la
declaración; sin servicios, camino actual byte a byte (R2).

Un fichero cambiado que no aparece en ninguna cobertura sigue cayendo en el
mecanismo actual de `lineas_ejecutables()` (cuenta como no cubierto): eso
resuelve R14 sin código nuevo, solo con tests que lo fijen.

### D5 — Mutación: un ejecutor por servicio, resuelto por fichero

`EjecutorPytest` se generaliza: recibe `cwd` y `ejecutable` (hoy siempre
raíz + `sys.executable`). `ejecutar_campania` recibe una **factoría de
ejecutores** `ejecutor_para(fichero)` que, con servicios declarados, resuelve
el servicio del fichero (R4) y devuelve el ejecutor de ese servicio (su
intérprete R5, su cwd); sin servicios, siempre el de la raíz. La restauración
del árbol (finally + red de seguridad) no se toca: opera sobre rutas
raíz-relativas y es independiente de dónde corra la suite.

Corrección R16: el veredicto distingue exit code **0 ⇒ SUPERVIVIENTE**,
**5 (sin tests recogidos) ⇒ SUPERVIVIENTE**, resto ⇒ MUERTO. Constante
`PYTEST_SIN_TESTS = 5` con comentario. Afecta también al caso mono-proyecto
y es una corrección honesta: hoy un repo sin tests mataría todos los
mutantes.

### D6 — Ficheros de raíz fuera de servicios: camino mono-proyecto

En un monorepo, el código de la raíz que no pertenece a ningún servicio
(p. ej. `harness/`, scripts de la raíz) se mide contra el `coverage.json` de
la raíz y se muta contra la suite de la raíz, como hoy. Alternativa
descartada: excluirlos del alcance (abriría el agujero de esconder código en
la raíz para esquivar las puertas).

## Ficheros a crear

| Ruta (este repo) | Contenido |
|---|---|
| `harness/servicios.py` | Declaración de servicios: dataclass, carga/validación, resolución de servicio e intérprete, CLI `--validar` / `--shell` |
| `tests/test_f020_arnes_multiservicio.py` | Tests trazables `test_f020_rN_*` (puede dividirse por bloque A–D si crece) |

En `arnes-base` (portado, R18): los mismos `harness/*.py` modificados y
nuevos, `arnes-base/harness/servicios.ejemplo.json`, `harness/VERSION` a
1.3.0, y la sección nueva de `GUIA_INSTALACION.md`.

## Ficheros a modificar

| Ruta | Qué cambia |
|---|---|
| `harness/alcance.py` | `es_produccion()`: exclusión por **segmento** de ruta (`tests`, `specs`, `progress`, `docs` en cualquier nivel), no solo prefijo (R11) |
| `harness/cobertura.py` | `fusionar_coberturas()` + carga opcional de servicios en `main()` (R13, R14); sin servicios, camino idéntico |
| `harness/mutacion.py` | `EjecutorPytest(cwd, ejecutable)`, factoría `ejecutor_para(fichero)`, `PYTEST_SIN_TESTS=5 ⇒ SUPERVIVIENTE` (R15, R16) |
| `harness/init.sh` | Sección multi-servicio condicionada a `harness/servicios.json` (R3, R6–R10); flujo mono intacto |

## Ficheros que NO se tocan

- `harness/rigor.py` y `harness/rigor.json`: los niveles de rigor son por
  feature, no por servicio; nada que cambiar.
- `harness/features.json` (lo actualiza el líder al cambiar estados, no esta
  spec), `CHECKPOINTS.md`, `.claude/agents/*`, `specs/SPECS.md`: el flujo SDD
  ya es agnóstico a rutas.
- `main.py`, `config/`, `etl_sigrid/`, `infra/`: el ETL no participa.
- En `arnes-base`: `instalar_arnes.ps1` (recorre el payload; los ficheros
  nuevos entran solos) y `scripts/mantener_despierto.ps1`.
- **Ningún `harness/servicios.json` activo en ningún sitio**: ni en este
  repo (mono-proyecto) ni en el payload de `arnes-base`.

## Funciones y firmas (todas en la capa de herramienta del arnés, sin capa hexagonal del ETL)

```python
# harness/servicios.py
RUTA_SERVICIOS = Path("harness/servicios.json")
LENGUAJES = ("python", "otro")

@dataclass(frozen=True)
class Servicio:
    nombre: str
    ruta: str                    # relativa a la raíz, separadores '/'
    lenguaje: str                # "python" | "otro"
    venv: str | None = None
    comando_tests: str | None = None

def cargar_servicios(ruta=RUTA_SERVICIOS, raiz=".") -> list[Servicio]
    # [] si el fichero no existe (R2); ValueError con motivo si es inválido (R3)

def servicio_de_ruta(ruta: str, servicios: list[Servicio]) -> Servicio | None
    # prefijo más largo, separadores normalizados (R4)

def interprete(servicio: Servicio, raiz=".") -> str
    # venv/Scripts/python.exe | venv/bin/python | sys.executable (R5)
    # ValueError si el venv declarado no existe

def main(argv=None) -> int
    # --validar (0/1 con errores a stderr) | --shell (línea por servicio:
    # nombre|ruta|lenguaje|venv|comando_tests, campos vacíos si no declarados)
```

```python
# harness/cobertura.py (añadidos)
def fusionar_coberturas(cov_raiz: dict | None,
                        coberturas_servicios: list[tuple[str, dict]]) -> dict
    # función pura: re-prefija files de cada servicio con su ruta (R13)
```

```python
# harness/mutacion.py (cambios)
PYTEST_SIN_TESTS = 5

class EjecutorPytest:
    def __init__(self, raiz=".", argumentos=None, ejecutable=None) -> None
    # returncode 0 o PYTEST_SIN_TESTS -> SUPERVIVIENTE; resto -> MUERTO (R16)

def ejecutor_para(fichero: str, servicios, raiz=".") -> EjecutorPytest
    # factoría: servicio del fichero -> su intérprete y su cwd; sin servicio,
    # el de la raíz (R15). ejecutar_campania la usa mutante a mutante.
```

## Riesgos y alternativas descartadas

- **Riesgo: cambiar `es_produccion()` altera alcances históricos.** Solo
  puede *sacar* ficheros del alcance (tests anidados que nunca debieron
  entrar), jamás meter nuevos. Los `test_f015_*` existentes vigilan la
  regresión; R11 añade el caso de raíz explícitamente.
- **Riesgo: exit 5 ⇒ superviviente cambia campañas mono-proyecto.** Solo si
  la suite no recoge tests, situación en la que hoy el veredicto era
  directamente falso. Se documenta en la guía como corrección de 1.3.0.
- **Riesgo: `--shell` y rutas con espacios o `|`.** La validación de R3
  rechaza `|` en los campos; los espacios se toleran usando `|` como
  separador y leyendo con `IFS='|'` en el bucle de `init.sh`.
- **Riesgo: venvs por servicio en Git Bash sobre Windows.** El intérprete se
  resuelve en Python (R5) probando `Scripts/python.exe` y `bin/python`, no
  con heurísticas de shell; el bucle de `init.sh` solo recibe la ruta ya
  resuelta. La prueba real R20 lo verifica en el entorno de verdad
  (PowerShell 5.1 + Git Bash).
- **Descartado: paralelizar las suites de servicios en `init.sh`.** Ganancia
  menor frente al coste de mezclar salidas y agregados en bash portable.
- **Descartado: rigor por servicio.** El nivel de vigilancia sigue siendo de
  la feature; una feature que cruza servicios exige lo mismo en todos.

## Decisiones abiertas (validar por el humano antes de implementar)

- **DA-1 · Forma de la declaración.** Se propone fichero propio
  `harness/servicios.json`, opcional, con autodescubrimiento y clave en
  `rigor.json` descartados (motivos en D1). ¿Conforme, o prefieres
  autodescubrimiento con marcador aunque cueste falsos positivos?
- **DA-2 · Dónde vive el trabajo.** El encargo dice «el trabajo vive en
  arnes-base»; este diseño lo matiza al patrón F-015: implementar y testear
  aquí (donde hay suite y puertas) y portar a `arnes-base` 1.3.0 en el mismo
  trabajo, quedando los `test_f020_*` como guardia permanente. La
  alternativa —dotar a `arnes-base` de infraestructura de tests propia— se
  pospone. ¿Conforme?
- **DA-3 · Rigor de F-020.** La feature no declara `rigor` en
  `features.json`, así que hoy hereda `critico` (cero supervivientes). Se
  recomienda declarar **`estandar`**: es herramienta del arnés, sin sistemas
  compartidos ni producción. Decidir antes de `in_progress` (el campo lo
  toca el líder, no esta spec).
- **DA-4 · Código de raíz fuera de servicios.** Propuesta D6: sigue el
  camino mono-proyecto (suite y coverage de la raíz). ¿Conforme, o prefieres
  exigir que en un monorepo todo código viva en algún servicio declarado?
- **DA-5 · Servicio Python sin suite ante la mutación.** Propuesta: sus
  mutantes sobreviven (R16), que es la verdad incómoda y empuja a crear la
  suite. Alternativa: abortar la campaña con error. ¿Conforme con
  supervivientes?
- **DA-6 · Venv declarado pero inexistente.** Propuesta: error explícito/KO
  (R5), nunca caer al intérprete global en silencio. Alternativa blanda:
  aviso + fallback. ¿Conforme con el KO?
