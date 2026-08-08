<!-- progress/impl_F-014.md -->
# F-014 · Arnés genérico versionado — informe de implementación

**Fecha:** 2026-08-09 · **Rama:** `feature/F-014-arnes-generico` · `sdd=false`
**Versión publicada del arnés:** 1.0.0

Feature en tres repositorios. Commits independientes en cada uno.

| Repositorio | Commit | Qué |
|---|---|---|
| `arnes-base` | `212179b` | Primer commit del repositorio (git init + arnés v1.0.0) |
| `azure-apps` | `74c72b0` | `arnes_base.md` + fila en el `README.md` |
| `datamart-seg-anual` | ver abajo | `CLAUDE.md` y `progress/` |

---

## 1. Qué se entrega

`arnes-base` deja de ser una carpeta suelta y pasa a ser un repositorio git
con versión, guía y un instalador que **sabe propagar mejoras**, no solo
instalar. El agujero que cierra tiene fecha y tamaño: cinco mejoras perdidas
el 2026-08-08 porque el instalador saltaba en silencio todo fichero ya
existente, es decir, exactamente los ficheros que hay que tocar para
propagar algo.

### Estructura resultante

```
arnes-base/                      <- repositorio git (rama main)
├── .gitignore  .gitattributes   <- coherentes con los de este proyecto
├── README.md                    <- qué es y por qué está versionado
├── GUIA_INSTALACION.md          <- los tres caminos
├── instalar_arnes.ps1           <- modos instalar y actualizar
└── arnes-base/                  <- PAYLOAD: lo que se copia al proyecto
    ├── CLAUDE.md  CHECKPOINTS.md
    ├── .claude/agents/{leader,spec-author,implementer,reviewer}.md
    ├── .claude/settings.json
    ├── docs/{ARCHITECTURE,CONVENTIONS}.md  docs/referencia/README.md
    ├── harness/{VERSION,init.sh,features.json,gitignore.arnes}
    ├── progress/{current,history}.md
    └── specs/SPECS.md
```

`GUIA_INSTALACION.md` se movió del payload a la raíz: es documentación de la
distribución, no del proyecto destino, y duplicarla contradecía la propia
regla de «una copia, no varias». Su función dentro del proyecto la cubre
ahora `harness/ARNES_VERSION.md`, que escribe el instalador.

## 2. Comparación de árboles y mejoras portadas

Se compararon los 14 ficheros comunes uno a uno (`diff -u`), no solo las
cinco mejoras del enunciado. **Nueve de los catorce divergían.** El snapshot
era más antiguo en unos ficheros y **más avanzado en otros**: la deriva iba
en los dos sentidos.

### Las cinco del enunciado (todas portadas)

| Mejora | Origen | Dónde queda |
|---|---|---|
| Dos paradas con el humano | `CLAUDE.md` §Ritmo de trabajo; `leader.md` PARADA 1/2; nota del `implementer` | los tres ficheros del payload |
| C3 bis (documentos de fuera) | `CHECKPOINTS.md` | `CHECKPOINTS.md` del payload |
| Nota de features `sdd=false` | cabecera de `CHECKPOINTS.md` | ídem |
| `.gitignore` de originales | `.gitignore` | `harness/gitignore.arnes` (fragmento) + `.gitignore` del propio repo |
| Convenciones de `docs/referencia/` | `docs/referencia/README.md` | payload, en versión genérica |

### Las que la lista no mencionaba y también se portaron

- **Autorización permanente de subagentes** (`CLAUDE.md`), incluida la
  aclaración de que no sustituye a la PARADA 1.
- **Regla de conversión con `markitdown`** para documentos que llegan de
  fuera: sin ella, C3 bis exige una cabecera que nadie sabe de dónde sale.
- **Regla de `azure-apps`** y **la propia regla de propagación a
  `arnes-base`** (ver decisión en §3).
- **`reviewer.md`**: se le añadió C3 bis al recorrido y qué hacer sin
  `tasks.md` en features `sdd=false`. Era el único agente que no se había
  enterado de dos cambios que le tocaban directamente.

### Deriva en sentido contrario: lo que el snapshot tenía mejor

Tres ficheros estaban **más avanzados en el snapshot** que en este proyecto,
y se conservó su versión:

- `spec-author.md`: regla de **LÍMITE DE MICROSERVICIO** y semántica de
  dominio genérica. Aquí se había reescrito en términos de Sigrid.
- `CLAUDE.md`: LÍMITE DE MICROSERVICIO y la regla de ejecutar `init.sh` sin
  pipes ni decoración.
- `specs/SPECS.md`: «capa/esquema» genérico frente a `stg/mart/cierre`.
- `docs/CONVENTIONS.md`: sección hexagonal y de patrón pipeline.

**Pendiente para el humano:** estas cuatro mejoras existen en el arnés
genérico pero **no** en este proyecto. Portarlas hacia aquí queda fuera del
alcance de F-014 (ver §7).

## 3. Genérico contra específico: qué se decidió

**Criterio aplicado:** ningún fichero del payload menciona un proyecto
concreto. Lo que un proyecto debe rellenar lleva marca `[ADAPTAR]` visible,
está tabulado en `GUIA_INSTALACION.md`, y `init.sh` **avisa en cada arranque**
mientras queden marcas sin resolver — un arnés sin adaptar no debe poder
pasar por adaptado.

| Fichero | Qué se quitó | Cómo quedó |
|---|---|---|
| `CLAUDE.md` | mapa del ETL, capas Sigrid, prohibiciones contra Sigrid/Postgres | mapa de ejemplo + `[ADAPTAR]`; prohibiciones como `[ADAPTAR]` con ejemplos |
| `CHECKPOINTS.md` | C3: «Semántica Sigrid (amb/fas, importe_origen vs importe_mes, fasnum)» | C3 `[ADAPTAR]`: «las 2-3 trampas del dominio». La forma del checkpoint es genérica; su contenido, no |
| `docs/ARCHITECTURE.md` | todo | cinco secciones `[ADAPTAR]`, con la de semántica de dominio marcada como «la valida el humano SIEMPRE» |
| `docs/CONVENTIONS.md` | `etl_sigrid/...`, structlog obligatorio | estructura genérica + subsección Python marcada «borrar si no aplica» |
| `docs/referencia/README.md` | manuales de Sigrid, índice real de 4 documentos | mismo formato de cabecera, índice `[ADAPTAR]` |
| `harness/features.json` | backlog real de 14 features | una feature de calentamiento de ejemplo |
| `harness/init.sh` | `main.py config etl_sigrid scripts tests` | `RUTAS_PYTHON` configurable, vacío = todo el árbol |
| `spec-author.md` | amb/fas, `importe_origen`/`importe_mes` | semántica de dominio genérica |
| `reviewer.md` | «SQL en su capa correcta», «PEP8, type hints» | «cada artefacto en su capa», «estilo del lenguaje» |

### La duda del enunciado: `azure-apps` y `arnes-base`

**Resuelta como se pedía: van en el genérico, aisladas.** Son convenios de la
organización, no de un proyecto; quitarlas habría hecho que cada instalación
en Ruesma naciera sin ellas, que es la clase de olvido que originó F-014.

Van en un bloque delimitado con marcas visibles en `CLAUDE.md` y
`docs/CONVENTIONS.md`:

```
<!-- ==================== INICIO · ENTORNO DE RUESMA ==================== -->
...
<!-- ===================== FIN · ENTORNO DE RUESMA ====================== -->
```

Se borra de un vistazo. `GUIA_INSTALACION.md` tiene una sección, «Si no usas
el entorno de Ruesma», que dice exactamente eso. Dentro del bloque: la regla
de `azure-apps`, la regla de propagación a `arnes-base`, el español
obligatorio, los tags de imagen fechados, el CSV para Excel ES y DAX sin
tildes. Ninguno de esos convenios cita un recurso concreto: el bloque nombra
`azure-apps` como repositorio, sin mencionar servidores, ACR ni hosts.

## 4. Versión explícita

- **`harness/VERSION`**: formato `clave=valor` para que `init.sh` lo lea con
  `source` y el instalador con una expresión regular, sin parsers ad hoc.
  Hoy: `ARNES_VERSION=1.0.0`, `ARNES_FECHA=2026-08-09`.
- **`init.sh` la imprime como primera línea**, antes que nada: si el arnés se
  comporta raro, lo primero que hay que saber es qué versión lleva el repo.
  Sin el fichero avisa «arnés anterior al versionado, actualízalo».
- **`harness/ARNES_VERSION.md`** en cada destino: versión, fecha de la
  versión, fecha de instalación, modo y el comando exacto para actualizar.
  Lo reescribe el instalador en cada pasada. Es lo que permite responder «qué
  arnés lleva este repositorio» sin abrirlo entero.

## 5. El instalador

Modo `instalar` **conservado sin cambios de contrato**: copia lo que falta,
no pisa nada. Lo único que cambia es que ahora avisa al final de cuántos
ficheros distintos ha saltado y de cómo revisarlos.

Modo `actualizar` nuevo: ante un fichero existente y distinto muestra el diff
(`git diff --no-index`, con `Compare-Object` de reserva si no hay git) y
pregunta `[S]` sobrescribir / `[N]` conservar / `[T]` todos / `[C]` conservar
todos / `[Q]` salir. Con `-SoloDiff` no escribe nada (mirar antes de decidir)
y con `-Forzar` acepta todo sin preguntar.

Detalles que salieron de probarlo, no de pensarlo:

- **Guardarraíl anti-bucle**: sin consola interactiva `Read-Host` devuelve
  vacío indefinidamente. Tras 5 intentos conserva el fichero (lo seguro) y lo
  dice. Sin esto el instalador se colgaba en cualquier consola no interactiva.
- **`.gitignore` selectivo**: la primera versión añadía el bloque entero y
  **duplicaba las reglas que el proyecto ya tenía** (visto en la prueba 2a
  contra la copia de este repo). Ahora compara línea a línea y añade solo lo
  que falta; si no falta nada, lo dice y no toca el fichero.
- **Sin BOM** en `.md` y `.gitignore` generados: `Set-Content -Encoding UTF8`
  mete BOM en PowerShell 5.1 y ensucia diffs y `grep`.
- **Ruido de git suprimido**: `core.autocrlf`/`safecrlf` a false en la llamada
  del diff; el aviso «CRLF will be replaced by LF» tapaba el diff real.
- `harness/gitignore.arnes` se excluye de la copia: es material del
  instalador, no del arnés instalado.
- Se rechaza que el destino sea el propio `arnes-base`.

Requisitos cumplidos: PowerShell 5.1, sin dependencias externas, fichero en
UTF-8 con BOM y CRLF según `docs/CONVENTIONS.md` (verificado: BOM
`239,187,191`, `git ls-files --eol` da `w/crlf attr/text eol=crlf`).

## 6. `init.sh` fuera de un proyecto Python

**Decisión: degradar con elegancia.** No «Python-only con mensaje claro».

**Motivo:** lo que da valor al arnés —la máquina de estados de
`features.json`, los checkpoints, la memoria de `progress/`, el guardarraíl
de rama— no tiene nada de Python. Un portero que revienta en un repositorio
de Node acaba comentado, y con él se pierden también las comprobaciones que
sí valían. Se documenta en la cabecera del propio `init.sh` y en la sección
«Proyectos que no son Python» de la guía.

Cómo se comporta:

- Detección automática (`PROYECTO_PYTHON=auto`) por `pyproject.toml`,
  `requirements.txt`, `setup.py` o cualquier `.py` a profundidad ≤ 3.
  Forzable a `1` o `0`.
- Si no es Python: se saltan `compileall`, `ruff` y `pytest` **con aviso**, y
  se ejecuta `COMANDO_TESTS` si está definido. Si no lo está, avisa de que
  **nadie** está comprobando los tests. Es aviso, no fallo: bloquear ahí
  dejaría inservible el arnés en el minuto uno de un proyecto nuevo.
- **`features.json` se valida siempre**, con el primer intérprete disponible:
  `python`, `node` o `jq`. Sin ninguno, degrada a comprobación por texto que
  sigue detectando más de una feature `in_progress`, avisando de que está
  degradada. Este era el punto delicado: la validación estaba escrita en
  Python y era el único motivo real por el que el arnés «necesitaba» Python.
- Si un proyecto se declara Python y no hay intérprete, **sí falla**: eso no
  es degradar, es un entorno roto (venv sin activar).

Extras que aporta la versión genérica: `LINT_BLOQUEA` (0 por defecto, para
repos con deuda), `REQUIERE_ENV`, y el aviso de marcas `[ADAPTAR]` pendientes.

## 7. Verificación real

Todo en el scratchpad de la sesión. **Ningún repositorio real se tocó.**

### Prueba 1 — carpeta temporal vacía

`instalar_arnes.ps1 -Destino <vacía>` →
`Nuevos: 16 | Ya iguales: 0 | Actualizados: 0 | Conservados: 0 | Saltados: 0`,
más `[GITIGNORE] bloque añadido` y `[VERSION] harness/ARNES_VERSION.md ->
v1.0.0`. `harness/gitignore.arnes` correctamente **no** copiado (16 ficheros
de los 17 del payload).

`bash harness/init.sh` sobre esa instalación, salida real:

```
[OK] Arnés v1.0.0 (2026-08-09)
[AVISO] Proyecto no Python: se saltan compilación, lint y pytest
[OK] Existe CLAUDE.md ... (8 ficheros del arnés)
    1 features, 1 abiertas, en curso: ninguna, bloqueadas: ninguna
[OK] features.json válido
[KO] Falta .env — copiar de .env.example
[AVISO] Sin COMANDO_TESTS definido: NADIE está comprobando los tests.
[AVISO] Marcas [ADAPTAR] sin resolver en: CLAUDE.md CHECKPOINTS.md
        docs/ARCHITECTURE.md docs/referencia/README.md harness/features.json
        harness/init.sh
EXIT=1
```

El `[KO]` es correcto: `REQUIERE_ENV=1` por defecto y el proyecto recién
creado no tiene `.env`. Es lo que el camino A de la guía manda resolver.

**Los tres validadores de `features.json`, probados con >1 `in_progress`:**

| Validador | Cómo se forzó | Salida |
|---|---|---|
| python | normal | `Hay 2 features in_progress (F-001, F-002). Máximo 1.` → `[KO]` |
| node | `PATH` sin python | idéntica → `[KO]` |
| texto | `PATH` sin python/node/jq | `Hay 2 features in_progress. Máximo 1.` → `[KO]`, precedido del aviso de validación degradada |

Los tres detectan el fallo. La única pérdida al degradar es que no nombra las
features.

Un efecto colateral corregido durante la prueba: `ARNES_VERSION.md` aparecía
en la lista de marcas `[ADAPTAR]` pendientes porque su texto contenía esa
palabra literal. Reformulado a «marcas de adaptacion».

### Prueba 2 — copia de un proyecto existente

Copia de `datamart-seg-anual` al scratchpad (sin `.git`, `.venv`, cachés;
161 ficheros). El `.env` copiado se sobrescribió de inmediato con un
marcador: no se manipuló el `.env` real.

**2a, modo instalar** (salida real):

```
[SALTADO] .claude/agents/implementer.md (ya existe y es distinto; usa -Modo actualizar para verlo)
[SALTADO] .claude/agents/reviewer.md    [SALTADO] .claude/agents/spec-author.md
[SALTADO] .claude/settings.json         [SALTADO] CHECKPOINTS.md
[SALTADO] CLAUDE.md                     [SALTADO] docs/ARCHITECTURE.md
[SALTADO] docs/CONVENTIONS.md           [SALTADO] docs/referencia/README.md
[SALTADO] harness/features.json         [SALTADO] harness/init.sh
[SALTADO] progress/current.md           [SALTADO] progress/history.md
[SALTADO] specs/SPECS.md
[NUEVO]   harness/VERSION
[GITIGNORE] nada que anadir: el proyecto ya cubre .env y los originales
[VERSION] harness/ARNES_VERSION.md -> v1.0.0
Nuevos: 1 | Ya iguales: 1 | Actualizados: 0 | Conservados: 0 | Saltados: 14
Hay 14 fichero(s) distintos que NO se han tocado.
Para revisarlos uno a uno:  -Modo actualizar
```

«Ya iguales: 1» es `leader.md`, idéntico por venir de este proyecto. **Esos
14 `[SALTADO]` son, literalmente, el bug de F-014**: en la versión anterior
del instalador esa lista se perdía sin dejar rastro.

**2b, `-Modo actualizar -SoloDiff`**: 14 diffs completos, nada escrito. Un
ejemplo real (`reviewer.md`):

```
@@ -15,17 +15,20 @@
-   requisito debe tener al menos un test que lo cubra. Ejecuta
-   `python -m pytest -q` y comprueba que esos tests existen y pasan.
+   requisito debe tener al menos un test que lo cubra. Ejecuta la suite de
+   tests del proyecto y comprueba que esos tests existen y pasan.
...
-5. Recorre `CHECKPOINTS.md` completo (C1–C5) marcando `[x]` / `[ ]` en tu
+5. Recorre `CHECKPOINTS.md` completo (C1–C5, C3 bis incluido) marcando `[x]`,
```

### Prueba 3 — modo actualizar interactivo

Instalación limpia + dos ficheros divergentes introducidos a mano
(`CHECKPOINTS.md`, `specs/SPECS.md`). Respuestas `n` y `s` por stdin:

```
--- diff CHECKPOINTS.md ...
[CONSERVADO]  CHECKPOINTS.md (se queda el del proyecto)
--- diff specs/SPECS.md ...
[ACTUALIZADO] specs/SPECS.md
Nuevos: 0 | Ya iguales: 14 | Actualizados: 1 | Conservados: 1 | Saltados: 0
```

Después, `-Forzar` sobre dos divergencias → `Actualizados: 2`; y una tercera
pasada → `Ya iguales: 16 | Actualizados: 0`. **Idempotente.**

### Prueba 4 — `init.sh` genérico sobre un proyecto Python real

El `init.sh` del payload, copiado sobre la copia de este repositorio:

```
[OK] Arnés v1.0.0 (2026-08-09)
[OK] Python: Python 3.12.7
    14 features, 10 abiertas, en curso: ['F-014'], bloqueadas: ninguna
[OK] features.json válido        [OK] Existe .env (no versionado)
[OK] compileall: sin errores de sintaxis
[AVISO] ruff: 127 avisos (deuda previa, no bloquea)
65 passed, 6 warnings in 1.02s
[OK] pytest en verde
EXIT=0
```

Detecta Python solo, compila el árbol entero sin `RUTAS_PYTHON` configurado y
pasa los 65 tests. El `init.sh` genérico funciona **sin adaptar** en este
proyecto.

### Pruebas 5 y 6 — formato del bloque `.gitignore`

Con `.gitignore` previo sin salto de línea final: línea en blanco de
separación y bloque delimitado. Sin `.gitignore` previo: fichero creado sin
línea en blanco inicial y **sin BOM** (primeros bytes `10,35,32`, no
`239,187,191`).

## 8. Barrido de datos sensibles

Ejecutado con `git diff --cached` sobre el stage de **los tres**
repositorios, antes de cada commit. Patrones y resultado:

| Patrón | `arnes-base` | `azure-apps` | este repo |
|---|---|---|---|
| GUID (`8-4-4-4-12`) | 0 | 0 | 0 |
| IPv4 | 1 (ver abajo) | 0 | 0 |
| Correos | 0 | 0 | 0 |
| `password`, `api_key`, `AccountKey`, `client_secret`, `bearer`, `BEGIN RSA/PRIVATE` | 0 | 0 | 0 |
| Recursos Azure (`psql-*`, `acr*dev`, `rg-*`, `*.ruesma.es`, `*.azure.com`) | 0 | 0 | 0 |
| Específico del datamart (`sigrid`, `datamart`, `etl_sigrid`, `fasnum`, `importe_origen`, `amb/fas`, `stg/`) | 0 | n/a | n/a |

Únicas coincidencias, ambas revisadas y **legítimas**:

1. `arnes-base/harness/init.sh`: `127.0.0.1` en un ejemplo **comentado** de
   comprobación de Azurite. Es localhost, no una dirección de nadie.
2. `arnes-base/CHECKPOINTS.md`: la palabra «tokens» dentro de la prosa de
   C3 bis, que describe este mismo barrido.

Lo que **no** es un secreto pero conviene que conste: los tres repositorios
contienen rutas locales del tipo `C:\Users\pgris\PycharmProjects\...`, igual
que ya hacían `azure-apps` y el `CLAUDE.md` del directorio padre. Es el
nombre de usuario de Windows, no una credencial, y es coherente con la
práctica ya establecida. Si el humano quiere que desaparezcan, hay que
decidirlo antes de publicar el repositorio en cualquier remoto: **el
historial de git no suelta lo que entra**, y ese es justo el momento de
decidirlo, porque `arnes-base` aún no tiene remoto.

## 9. Cambios en este repositorio

- **`CLAUDE.md`**:
  - Se corrigió un **defecto estructural preexistente**: las viñetas de
    `CHECKPOINTS.md` e `infra/` habían quedado huérfanas *después* de la
    sección «Los otros proyectos», fuera del mapa del repositorio al que
    pertenecen. Se detectó al comparar los árboles. Es una corrección
    documental de tres líneas, ajena al alcance estricto de F-014, y se
    declara aquí para que el reviewer la juzgue.
  - Sección `arnes-base` actualizada: ya es un repositorio git versionado, y
    se añade el comando concreto del modo actualizar, porque la regla de
    propagación sin la herramienta para cumplirla es lo que falló el
    2026-08-08.
- **`../CLAUDE.md`** (directorio padre, no versionado): cómo saber qué
  versión lleva cada repositorio y los dos modos del instalador.
- `progress/impl_F-014.md` (este fichero) y `progress/current.md`.

## 10. Verificaciones MANUAL pendientes (humano)

1. **Modo interactivo en consola real.** Se probó con respuestas por stdin,
   no tecleando. Recomendado antes de usarlo sobre un repositorio de verdad:
   ```powershell
   cd C:\Users\pgris\PycharmProjects\arnes-base
   .\instalar_arnes.ps1 -Destino "C:\ruta\copia-de-pruebas" -Modo actualizar
   ```
2. **Remoto de `arnes-base`.** El repositorio no tiene remoto. Los agentes no
   hacen `push`. Decidir dónde va y, antes, si las rutas locales deben salir.

## 11. Qué queda fuera y qué falta

**Fuera del alcance, deliberadamente:**

- **No se instaló el arnés en ningún proyecto real.** El enunciado lo prohíbe
  expresamente: lo decide el humano.
- **No se portaron hacia este repositorio** las cuatro mejoras que el arnés
  genérico tiene y este proyecto no (LÍMITE DE MICROSERVICIO en `CLAUDE.md` y
  `spec-author.md`, regla de ejecutar `init.sh` sin decoración, `init.sh` con
  `LINT_BLOQUEA`/`REQUIERE_ENV`/aviso de `[ADAPTAR]`). Es una mejora del
  arnés **de este proyecto**, no de F-014, y merece su propia feature con su
  PARADA 1.

**Falta, y conviene no olvidarlo:**

- La regla de propagación es hoy una norma escrita, **no un mecanismo**:
  nada impide cerrar una feature que mejore el arnés sin tocar `arnes-base`.
  El candidato natural es un punto en `CHECKPOINTS.md` («si la feature tocó
  ficheros del arnés, ¿se portó lo genérico?») que el reviewer recorra. No se
  añadió porque no está en los `acceptance` y tocaba decidirlo con el humano.
- `harness/VERSION` se sube a mano. Con una versión al año no compensa
  automatizarlo; si el arnés coge ritmo, sí.

## 12. Estado de los criterios `acceptance`

| # | Criterio | Estado |
|---|---|---|
| 1 | `arnes-base` repo git con primer commit, `.gitignore`, `.gitattributes` | OK — commit `212179b` |
| 2 | Todas las mejoras vigentes portadas | OK — §2, incluidas cuatro no listadas |
| 3 | `harness/VERSION` e `init.sh` la imprime | OK — §4, primera línea de la salida |
| 4 | El instalador registra la versión en el destino | OK — `harness/ARNES_VERSION.md` |
| 5 | Modo actualizar con diff; modo instalar conservado | OK — §5, probado en §7 |
| 6 | Genérico separado de específico, con marcadores explicados | OK — §3, barrido en §8 sin coincidencias |
| 7 | `init.sh` degrada o declara Python-only | OK — degrada; decisión y motivo en §6 |
| 8 | `GUIA_INSTALACION.md` con los tres caminos | OK — A, B y C |
| 9 | Regla de propagación en ambos `CLAUDE.md` | OK — ya estaba; ampliada con el cómo |
| 10 | Documento en `azure-apps` según su convención | OK — commit `74c72b0` |
| 11 | Probado contra carpeta vacía y copia de proyecto | OK — §7, seis pruebas con salida real |
| 12 | `bash harness/init.sh` de este repositorio en verde | OK — 65 tests, exit 0 |
