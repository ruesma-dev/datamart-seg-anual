<!-- specs/F-015-verificar-tests/design.md -->
# F-015 · Verificar que los tests son de verdad — Diseño técnico

## Visión general

Cuatro piezas, todas del arnés y ninguna del ETL:

1. **Mutador propio mínimo** (`harness/mutacion.py` + `harness/alcance.py`):
   calcula el alcance desde git, genera mutantes con `ast` sobre las líneas
   cambiadas, ejecuta pytest por mutante y escribe
   `progress/mutacion_F-XXX.md`.
2. **Puerta de cobertura** (`harness/cobertura.py`, invocada desde `init.sh`):
   cruza el JSON de `coverage.py` con el mismo alcance de diff y falla bajo el
   umbral de `harness/rigor.json`.
3. **Niveles de rigor** (`harness/rigor.py` + `harness/rigor.json` +
   `CHECKPOINTS.md`): tres niveles, campo `rigor` por feature, default el más
   exigente.
4. **Protocolos** (`implementer.md`, `reviewer.md`): fase RED con salida real,
   sección «Evidencias», validación contra el nivel declarado.

`harness/` pasa a ser un paquete Python (`__init__.py`) para poder invocar
`python -m harness.mutacion` y compartir el parser de diff entre mutación y
cobertura sin trucos de `sys.path`.

## Ficheros a crear

| Ruta | Contenido |
|---|---|
| `harness/__init__.py` | Marca de paquete (solo el comentario de ruta). |
| `harness/alcance.py` | Parser de diff y resolución del alcance de una feature. |
| `harness/mutacion.py` | Operadores de mutación, campaña, informe y CLI. |
| `harness/cobertura.py` | Puerta de cobertura de líneas cambiadas y CLI. |
| `harness/rigor.py` | Carga/validación de `rigor.json` y resolución de nivel. |
| `harness/rigor.json` | Configuración: umbral, timeout por mutante, niveles. |
| `tests/test_f015_alcance.py` | R2, R4. |
| `tests/test_f015_mutacion.py` | R1, R3, R5, R6, R7. |
| `tests/test_f015_cobertura.py` | R10, R11, R12, R13. |
| `tests/test_f015_rigor.py` | R14, R15, R16, R17, R19. |
| `tests/test_f015_protocolos.py` | R8, R9 (textual sobre los agentes) y R18. |
| `progress/mutacion_F-005.md` | Línea base generada por la herramienta (T11). |

## Ficheros a modificar

| Ruta | Qué cambia |
|---|---|
| `harness/init.sh` | (a) valida `harness/rigor.json` y el campo `rigor` de `features.json`; (b) sección 6: `compileall` incluye `harness`; (c) sección 7: si `coverage` está instalado, `coverage run -m pytest` + `coverage json`; después `python -m harness.cobertura` como puerta (KO/aviso según R10–R13). Sin ningún umbral numérico en el script. |
| `CHECKPOINTS.md` | Nueva sección «Niveles de rigor» (definición de los tres niveles y su tabla de exigencias) + nuevo bloque **C4 bis — El rigor declarado se cumple** + ampliación de la nota de N/A (R17). |
| `.claude/agents/implementer.md` | Protocolo: fase RED para los requisitos centrales (salida real del fallo en el informe) y sección «Evidencias» obligatoria con los cuatro números (R8, R9). |
| `.claude/agents/reviewer.md` | Protocolo: paso nuevo «resolver el nivel de rigor de la feature y validar contra él»: exigir `progress/mutacion_F-XXX.md`, evidencia RED y «Evidencias» según el nivel (R16). |
| `requirements-dev.txt` | Añadir `coverage>=7.4` (única dependencia nueva; ver DA-6). |
| `progress/current.md` | Rastro de sesión (protocolo del arnés). |

### Portado a arnes-base (mismo trabajo, R20)

En `C:\Users\pgris\PycharmProjects\arnes-base` (repositorio git propio):
copiar `arnes-base/harness/{__init__,alcance,mutacion,cobertura,rigor}.py` y
`rigor.json`; aplicar los mismos cambios a su `harness/init.sh`,
`CHECKPOINTS.md`, `.claude/agents/implementer.md` y `reviewer.md`; subir
`arnes-base/harness/VERSION` a `1.2.0` con la fecha; documentar en
`GUIA_INSTALACION.md` la sección «Verificación de que los tests son de verdad
(desde 1.2.0)». El commit es local en ese repositorio, sin push. Lo específico
de aquí (línea base F-005, `requirements-dev.txt`) NO se porta.

## Ficheros que NO se tocan

- `harness/features.json`: el campo `rigor` de cada feature lo declara el
  humano (o el líder con su aprobación) al abrir cada feature; esta feature
  solo implementa el mecanismo y su validación. Excepción: si el humano cierra
  DA-4, el implementer añade los `rigor` retroactivos como tarea aparte.
- `main.py`, `config/`, `etl_sigrid/`, `infra/`, `Dockerfile`: la feature es
  del arnés, no del ETL. Ni una línea.
- `tests/test_f005_*.py`, `tests/test_smoke.py`, etc.: los tests existentes son
  el **objeto** de la línea base, no se retocan (si la mutación revela huecos,
  eso va al informe, no se parchea en esta feature).
- `.env`, `.env.example`, `specs/` de otras features, `docs/ARCHITECTURE.md`,
  `docs/CONVENTIONS.md` (la convención `test_fXXX_rN_*` ya está escrita).

## Clases y funciones

Todo vive en el arnés (fuera de la arquitectura hexagonal del ETL; son
herramientas de desarrollo, como `init.sh`). Python puro, stdlib salvo
`coverage`. Sin `click` (el arnés genérico no puede asumirlo): `argparse`.

### `harness/alcance.py`

- `@dataclass Alcance`: `feature: str`, `origen: str` (`"rama"` | `"merge"`),
  `ref_diff: tuple[str, str]`, `lineas: dict[str, set[int]]` (ruta relativa →
  líneas añadidas/cambiadas). Ficheros nuevos: todas sus líneas.
- `parsear_diff(texto: str) -> dict[str, set[int]]` — función pura sobre el
  formato unificado de `git diff`; es lo que se testea con fixtures.
- `es_produccion(ruta: str) -> bool` — `*.py` fuera de `tests/`, `specs/`,
  `progress/`, `docs/`.
- `resolver_refs(feature_id: str, rama: str, base: str, git=ejecutar_git) ->
  tuple[str, str, str]` — orden: la rama existe → (`base...rama`, origen
  `rama`); si no, merge commit por `git log --merges --grep` → (`M^1`, `M`,
  origen `merge`); si no, `SystemExit` con mensaje (R4). El ejecutor de git se
  inyecta para poder mockearlo.
- `alcance_de_feature(feature_id, base="dev", rama=None) -> Alcance`.

### `harness/mutacion.py`

- `@dataclass Mutante`: `fichero`, `linea`, `col`, `original`, `mutado`,
  `operador`.
- `generar_mutantes(fuente: str, lineas: set[int], fichero: str) ->
  list[Mutante]` — recorre el `ast` del fichero; para cada nodo cuyo `lineno`
  esté en el alcance aplica los operadores de R6 usando
  `col_offset`/`end_col_offset` para el empalme textual. **Un mutante = un solo
  cambio.**
- `aplicar_mutante(fuente: str, m: Mutante) -> str` / restauración por copia
  del contenido original en memoria + `try/finally` que reescribe el fichero
  (R5). También `signal`/`KeyboardInterrupt` cubiertos por el mismo `finally`.
- `class EjecutorPytest` — protocolo con
  `ejecutar(timeout_s: int) -> ResultadoTests` (`muerto` | `superviviente` |
  `timeout`); la implementación real usa `subprocess.run([sys.executable,
  "-m", "pytest", "-x", "-q", "--tb=no", "-p", "no:cacheprovider"],
  timeout=...)`. En tests se sustituye por un doble.
- `ejecutar_campania(alcance, ejecutor, timeout_s, max_mutantes=None,
  semilla=None) -> InformeMutacion` — bucle mutante a mutante; error de
  compilación del mutante cuenta como muerto.
- `escribir_informe(informe, ruta: Path)` — formato de R3, con la sección
  `### Análisis (PENDIENTE del implementer)` por superviviente.
- `main(argv)` — `--feature F-XXX`, `--base dev`, `--rama`, `--timeout`,
  `--max-mutantes`, `--semilla`, `--salida progress/mutacion_F-XXX.md`.
  Exit 0 sin supervivientes, 1 con ellos, 2 error de uso.

### `harness/cobertura.py`

- `cobertura_lineas_cambiadas(cov: dict, lineas: dict[str, set[int]]) ->
  tuple[int, int]` — (cubiertas, totales) cruzando el JSON de `coverage json`
  con el alcance; función pura, testeada con fixtures.
- `main(argv)` — `--base dev`, `--config harness/rigor.json`,
  `--cov coverage.json`. Decide él mismo si la puerta aplica (rama, diff,
  nivel de rigor de la feature en curso): imprime `PUERTA COBERTURA: N/A
  (<motivo>)` y exit 0, o `X.X% de N líneas (umbral U%)` y exit 0/1 (R10–R12).
  Si la puerta aplica y falta `coverage.json` o el módulo `coverage`, exit 1
  con el mensaje de instalación (R13).

### `harness/rigor.py`

- `cargar_rigor(ruta: Path) -> dict` — valida esquema; errores con mensaje.
- `nivel_de_feature(feature: dict, rigor: dict) -> str` — devuelve
  `feature["rigor"]` si existe y es válido; si no, `rigor["nivel_por_defecto"]`
  (el más exigente) (R15).
- `exige(nivel: str, puerta: str, rigor: dict) -> bool` — consulta la tabla de
  niveles (`"cobertura"`, `"mutacion"`, `"fase_red"`).

### `harness/rigor.json` (contenido propuesto)

```json
{
  "$doc": "Niveles de rigor del arnés. El umbral y los niveles se editan aquí, nunca en init.sh.",
  "nivel_por_defecto": "critico",
  "cobertura": { "umbral_lineas_cambiadas": 80 },
  "mutacion": { "timeout_por_mutante_s": 120 },
  "niveles": {
    "documental": { "fase_red": false, "cobertura": false, "mutacion": false },
    "estandar":  { "fase_red": true,  "cobertura": true,  "mutacion": true, "supervivientes_maximos": null },
    "critico":   { "fase_red": true,  "cobertura": true,  "mutacion": true, "supervivientes_maximos": 0 }
  }
}
```

`supervivientes_maximos: null` = los supervivientes se documentan y el reviewer
juzga; `0` = cada superviviente exige o un test nuevo o justificación escrita
aceptada por el humano.

## Niveles de rigor en CHECKPOINTS.md (propuesta, cierra DA-3)

| Nivel | Para qué features | Exige |
|---|---|---|
| **documental** | Solo docs/specs/progress; ni código ni SQL | C1–C3, C3 bis, C5. Sin RED, sin cobertura, sin mutación |
| **estandar** | Código sin riesgo sobre sistemas compartidos | Todo lo anterior + fase RED en requisitos centrales + cobertura ≥ umbral + campaña de mutación con supervivientes documentados |
| **critico** | Infraestructura compartida, producción, seguridad, dinero | Todo lo anterior + 0 supervivientes sin justificación aceptada + verificaciones MANUAL listadas con comando exacto y resultado |

Nuevo **C4 bis — El rigor declarado se cumple**: la feature declara `rigor` en
`features.json` (o se le aplica el más exigente); existe
`progress/mutacion_F-XXX.md` si el nivel exige mutación; el informe del
implementer contiene la evidencia RED y la sección «Evidencias»; ningún N/A
sin justificación escrita.

## Integración en `init.sh` (orden de secciones)

1. Secciones 1–6 actuales (con `harness` añadido a `compileall` y la
   validación de `rigor.json` + campo `rigor` junto a la sección 3).
2. Sección 7 pasa a: `coverage run -m pytest` si `coverage` está disponible
   (si no, pytest a secas + la lógica de R13), luego `coverage json -q` y
   `python -m harness.cobertura --base dev --config harness/rigor.json`.
3. La campaña de **mutación NO corre dentro de `init.sh`**: es cara (minutos).
   Es un comando aparte que el implementer lanza al terminar y el reviewer
   comprueba por su informe. `init.sh` sigue siendo rápido y de solo lectura.

## Riesgos y decisiones

### Decisión: mutador propio mínimo, no mutmut ni cosmic-ray (cierra la elección, ver DA-1)

- **mutmut** (descartado): sus versiones actuales (3.x) dependen de `fork` y
  están explícitamente sin soporte en Windows; este arnés corre en Git Bash +
  PowerShell sobre Windows 11 y en el propio `init.sh`. Además muta por
  fichero, no por líneas de un diff: habría que envolverlo igualmente.
- **cosmic-ray** (descartado): funciona en Windows y tiene filtro por git,
  pero arrastra sesión en base de datos propia, configuración TOML y varios
  CLI; demasiado peso para portarlo a `arnes-base` como pieza genérica, y su
  filtro git también habría que adaptarlo a nuestro flujo rama-contra-dev.
- **Propio** (elegido): ~300 líneas de stdlib (`ast` + `subprocess`),
  exactamente el alcance que necesitamos (líneas del diff), portable tal cual,
  y testeable con dobles sin ejecutar pytest de verdad. Coste: los operadores
  son pocos (R6) y hay que mantenerlos; asumido y acotado.

### Decisión: cálculo de cobertura propio sobre `coverage json`, sin diff-cover

`diff-cover` haría el cruce diff×cobertura, pero ya tenemos que escribir el
parser de diff para la mutación (R2): reutilizarlo para la cobertura deja una
sola implementación del alcance y una sola dependencia nueva (`coverage`).
Dos fuentes de verdad del «qué cambió» sería un bug esperando fecha.

### Decisión: alcance de features mergeadas por commit de merge

Para F-005 la rama puede no existir: se localiza el merge
(`git log --merges --grep "F-005" -n 1` sobre `dev`, para F-005 es `c7500d4`)
y el alcance es `git diff M^1 M`. Nota asumida: el fix posterior
(`e9e80d6`, mergeado aparte) queda fuera de la línea base; se anota en el
informe.

### Riesgo: duración de la línea base de F-005

F-005 tocó mucho Python: la campaña puede generar cientos de mutantes y cada
uno ejecuta la suite (hoy ~segundos). Mitigación: `-x -q --tb=no`, timeout por
mutante, y si la estimación supera ~45 min, ejecutar con `--max-mutantes N
--semilla 20260809` (muestra reproducible) y **decir en el informe que es una
muestra y de qué tamaño**. Qué opción se prefiere: DA-5.

### Riesgo: mutantes equivalentes

Algunos supervivientes no son huecos de tests sino mutantes semánticamente
equivalentes (p. ej. `<` → `<=` en un rango imposible). No se resuelve
automáticamente: la sección de análisis de R3 existe para eso, y el nivel
`critico` admite «justificación aceptada» precisamente por esto.

### Riesgo: `init.sh` más lento y con una dependencia más

`coverage run` añade sobrecoste (~x1.5–x2 sobre pytest). Aceptado: la suite es
de segundos. En un proyecto sin `coverage` instalado y sin feature en curso,
todo degrada a aviso (R12/R13), así que `arnes-base` sigue instalable en
proyectos mínimos.

### Riesgo: el propio F-015 se autoaplica

Esta feature es de nivel `critico`-en-espíritu pero su código es del arnés.
Propuesta: declararla `estandar` (DA-4). Sus tests deben pasar la fase RED y
su propia campaña de mutación (`python -m harness.mutacion --feature F-015`),
que además sirve de prueba de fuego de la herramienta sobre sí misma.

## Decisiones abiertas que el humano debe validar (ANTES de implementar)

- **DA-1 · Herramienta de mutación**: se propone mutador propio mínimo
  (stdlib). Alternativas mutmut/cosmic-ray descartadas arriba. ¿Conforme?
- **DA-2 · Umbral de cobertura por defecto**: se propone **80 %** de las
  líneas cambiadas. ¿Otro valor?
- **DA-3 · Definición de los niveles**: se proponen `documental` / `estandar`
  / `critico` con la tabla de arriba y default `critico`. ¿Nombres y
  exigencias conformes?
- **DA-4 · Rigor retroactivo de features cerradas y de la propia F-015**:
  propuesta: F-001 `estandar`, F-008 `documental`, F-009 `documental`,
  F-005 `critico`, F-014 `estandar`, F-015 `estandar`. Declararlo en
  `features.json` es una tarea del implementer SOLO si el humano aprueba esta
  lista; si no, todo queda al default (`critico`) por omisión.
- **DA-5 · Línea base completa o muestreada**: si la campaña F-005 supera
  ~45 min, ¿se acepta muestra reproducible con semilla (constará el tamaño en
  el informe) o se exige campaña completa aunque tarde horas?
- **DA-6 · Dependencia nueva**: `coverage>=7.4` en `requirements-dev.txt`
  (nunca en la imagen). ¿Conforme?
