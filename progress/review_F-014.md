<!-- progress/review_F-014.md -->
# F-014 · Arnés genérico versionado — informe de review

**Fecha:** 2026-08-09 · **Rama:** `feature/F-014-arnes-generico` · `sdd=false`
**Reviewer:** subagente `reviewer` · **Alcance:** tres repositorios
(`datamart-seg-anual`, `arnes-base`, `azure-apps`)

## Veredicto

**CHANGES_REQUESTED**

Cuatro cambios concretos, todos pequeños. Dos son de fondo:

1. Un fichero del arnés genérico sigue nombrando las capas `stg`/`mart`/
   `cierre` de este proyecto, que es literalmente lo que prohíbe el criterio
   `acceptance` nº 6.
2. El documento de `azure-apps` quedó en la versión 1.0.0 cuando el arnés
   subió a 1.1.0 con el añadido del final. Es la regla de propagación
   incumplida dentro de la propia feature que existe para que eso no pase.

El resto del trabajo es sólido y la mayor parte de lo afirmado en
`progress/impl_F-014.md` lo he reproducido y confirmado por mi cuenta.

---

## 1. Lo que he ejecutado yo (no leído del informe)

| Verificación | Resultado |
|---|---|
| `bash harness/init.sh` en este repo | **exit 0**, 65 tests, ruff 127 avisos (deuda previa, no bloquea) |
| Instalador contra carpeta vacía del scratchpad | `Nuevos: 18` (incluye `scripts/`), `.gitignore` con 8 reglas, `ARNES_VERSION.md -> v1.1.0` |
| `harness/init.sh` genérico sobre esa instalación (proyecto no Python) | Imprime `[OK] Arnés v1.1.0 (2026-08-09)` como **primera línea**, avisa «Proyecto no Python», valida `features.json`, `[KO]` solo por `.env` ausente → exit 1 esperado |
| Modo `instalar` sobre fichero divergente | `[SALTADO] CHECKPOINTS.md`, hash del destino **idéntico** antes y después: no pisa |
| Modo `actualizar -SoloDiff` | Muestra el diff real y **no escribe** (hash intacto) |
| `despierto_hook.sh`: 7 caminos de fallo | Todos **exit 0** en silencio (sin `.ps1`, sin `session_id`, stdin vacío, sin argumento, acción desconocida, `parar` sin PID, `PATH` sin PowerShell) |
| `mantener_despierto.ps1 -Prueba` en PowerShell 5.1 real | exit 0, activa y restaura; sin admin avisa y sigue |
| Banderas | `2147483649` y `2147483651`, correctas. Confirmado en 5.1 que `0x80000000` se parsea como `Int32 = -2147483648`: la trampa que el script documenta es real y está esquivada |
| Barrido de secretos sobre **todo el historial** de los tres repos | Sin hallazgos imputables a F-014 (detalle en §3) |
| Arnés instalado en algún proyecto real de `PycharmProjects` | **No.** Ni un solo `harness/VERSION` ni `ARNES_VERSION.md` fuera de `arnes-base`; los scripts `despierto_*` solo existen en `datamart-seg-anual` y en el payload |

## 2. Checkpoints (`CHECKPOINTS.md`)

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` exit 0. Ejecutado por mí.
- [x] Existen los ocho ficheros del arnés.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress` (F-014). Lo valida `init.sh`.
- [x] Rama `feature/F-014-arnes-generico`, no `main`.
- [ ] **`progress/current.md` NO describe el estado real.** Dice «Los 12
      criterios `acceptance` quedan cubiertos» y «arnés genérico v1.0.0»
      (líneas 19-24). Los criterios son 13 y la versión es 1.1.0. Ver cambio
      requerido nº 3.
- [x] F-005 tiene su resumen en `progress/history.md`.

### C3 — El código respeta arquitectura y convenciones

- [x] Dominio sin infraestructura: N/A funcional, la feature no toca
      `etl_sigrid/`. Los dos ficheros nuevos son scripts de utilidad en
      `scripts/`, su sitio correcto.
- [x] Primera línea con la ruta: `scripts/despierto_hook.sh:2` (tras el
      shebang, como `harness/init.sh`) y `scripts/mantener_despierto.ps1:1`.
- [x] Sin `print()` de debug, sin TODOs sueltos, sin secretos, sin
      dependencias nuevas.
- [ ] **Convención de PowerShell incumplida.** `docs/CONVENTIONS.md:41`
      exige «PowerShell: UTF-8 con BOM y CRLF».
      `scripts/mantener_despierto.ps1` **no tiene BOM** (primeros bytes
      `35 32 115`, o sea `# s`). Los seis `.ps1` de `infra/` sí lo llevan
      (`239 187 191`). Ver cambio requerido nº 4.
- [x] Semántica de dominio: N/A. La feature no toca datos ni esquemas de
      Sigrid; no hay regla de negocio en juego.

### C3 bis — Documentos que entran de fuera

- [x] **N/A justificado en cuanto a `docs/referencia/`**: la feature no añade
      ni modifica ningún documento de esa carpeta.
- [x] **Barrido de datos sensibles ejecutado por mí**, sobre los tres
      repositorios y su historial completo, no solo el árbol de trabajo.
      Patrones y resultado en §3. El barrido del implementer (§8 de su
      informe) es correcto en su conclusión pero **su patrón `stg/` falló**:
      no detectó la mención de `` `stg` ``/`` `mart` ``/`` `cierre` `` en
      `spec-author.md`. Es lo que se lleva el cambio requerido nº 1.

### C4 — La verificación es real

- [ ] **N/A parcial, justificado.** No existen tests `test_f014_rN_*` y no
      pueden existir para la mayoría de los 13 criterios: son ficheros en
      **otros** repositorios, un instalador PowerShell y un script de energía
      de Windows. La verificación equivalente es la ejecución real, y la he
      reproducido punto por punto (§1). Lo marco N/A y no `[x]`, porque sí
      había margen para al menos un test barato en este repositorio: ver
      recomendación R2. No es motivo de rechazo por sí solo.
- [x] Los unit tests no tocan red ni BBDD: los 65 existentes siguen en verde
      y la feature no añade ninguno.
- [x] Verificaciones `MANUAL (humano)` listadas en `progress/current.md`
      con su comando exacto (modo interactivo del instalador; remoto de
      `arnes-base`).

### C5 — La sesión se cerró bien

- [x] `tasks.md`: **N/A justificado**, feature `sdd=false` sin
      `specs/F-014-*/`, según la nota de cabecera de `CHECKPOINTS.md`. Los
      commits usan el formato mínimo `F-014: <descripción>` en los tres
      repositorios (`53d1127`, `be54b6c`, `e33d929`, `824e23f` aquí;
      `212179b`, `7d7205b`, `8f4d701` en `arnes-base`; `74c72b0` en
      `azure-apps`).
- [x] `git status` limpio, sin ficheros sin trackear. Las pruebas del
      instalador quedaron en el scratchpad de sesión, no en el repo.
- [ ] **`features.json` no refleja el estado real**: colateral del mismo
      desfase de C2 (13 criterios, versión 1.1.0 vs. lo escrito en
      `current.md`). El `status: in_progress` sí es correcto: lo cambia el
      líder tras el APPROVED.

## 3. Barrido de datos sensibles (ejecutado por el reviewer)

Patrones: GUID `8-4-4-4-12`; IPv4; correos; `password|passwd|api_key|
accountkey|client_secret|secret_key|bearer|BEGIN (RSA|OPENSSH|PRIVATE)|
subscription_id|tenant_id|connectionstring`; recursos (`psql-*`, `acr*dev`,
`*.ruesma.es`, `*.azure.com`, `*.database.windows.net`); específicos del
datamart (`sigrid`, `datamart`, `etl_sigrid`, `fasnum`, `importe_origen`,
`amb/fas`).

| Repositorio | Alcance | Resultado |
|---|---|---|
| `arnes-base` | **los 3 commits completos**, no solo HEAD | Limpio |
| `azure-apps` | **los 2 commits completos** | Limpio en lo aportado por F-014 (ver hallazgo previo abajo) |
| `datamart-seg-anual` | `git diff dev...HEAD` | Limpio |

Coincidencias revisadas y **legítimas**:

1. `arnes-base/harness/init.sh:266` — `127.0.0.1` en un ejemplo **comentado**.
   Es localhost.
2. `arnes-base/CHECKPOINTS.md:55` — la palabra «tokens» en la prosa de C3 bis.
3. `azure-apps/portal.md:291` — `AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET` como
   **nombres** de app settings, sin valores. Es lo que la regla 3 del
   `README.md` de `azure-apps` permite expresamente.

**Hallazgo ajeno a F-014, pero que hay que decir:**
`azure-apps/partes.md:273` contiene la IP pública `80.28.223.30` del SQL
Server on-premise. Entró en el commit `5726c5c`, **anterior** a esta feature,
así que no bloquea F-014; pero incumple la regla 3 del propio `README.md` de
`azure-apps` («ni IPs internas… lo que entra se queda en el historial») y esa
regla ya no se puede cumplir borrando la línea: hace falta reescribir el
historial, y conviene hacerlo **antes** de que ese repositorio tenga remoto.
Decisión del humano.

**Rutas locales**: `C:\Users\pgris\PycharmProjects\…` aparecen en
`arnes-base/GUIA_INSTALACION.md`, `arnes-base/CLAUDE.md` (2 veces) y
`azure-apps/arnes_base.md`. No son credenciales y son coherentes con la
práctica ya establecida; el implementer lo declara y lo deja como decisión
previa a publicar `arnes-base` en un remoto. **De acuerdo**: no bloquea, pero
es una decisión que caduca en cuanto haya `git push`.

## 4. Cobertura de los 13 criterios `acceptance`

| # | Criterio | Estado | Comprobación del reviewer |
|---|---|---|---|
| 1 | `arnes-base` repo git con primer commit, `.gitignore`, `.gitattributes` | **OK** | 3 commits, ambos ficheros presentes y coherentes; `git ls-files --eol` confirma que el arreglo de `7d7205b` funciona (`VERSION` → `attr/text eol=lf`) |
| 2 | Todas las mejoras vigentes portadas | **OK** | Comparé los dos árboles fichero a fichero. Las cinco del enunciado están: PARADA 1/2 (`leader.md:25,31,45,47,48`, `implementer.md:35`, `CLAUDE.md:23,26-48`), C3 bis (`CHECKPOINTS.md:44`, `reviewer.md:26`, `docs/referencia/README.md:83`), nota `sdd=false` (`CHECKPOINTS.md:8`, `reviewer.md:30`), `.gitignore` de originales (raíz + `harness/gitignore.arnes`), convenciones de `docs/referencia/`. Más las cuatro no listadas que declara el informe. Verificado también el sentido inverso: nada del arnés de este repo se quedó sin portar salvo lo que el informe declara como deliberado |
| 3 | `harness/VERSION` semántico + `init.sh` la imprime | **OK** | `ARNES_VERSION=1.1.0`, `ARNES_FECHA=2026-08-09`. Ejecutado: es la primera línea de la salida. Sin el fichero, avisa. (Este repositorio no lleva `VERSION` porque no se instaló el arnés genérico aquí; el criterio 12 es el que habla de «este repositorio» y se cumple aparte) |
| 4 | El instalador registra la versión en el destino | **OK** | `harness/ARNES_VERSION.md` generado en mi prueba con v1.1.0, fecha, modo y el comando de actualización |
| 5 | Modo `actualizar` con diff; `instalar` conservado | **OK** | Reproducidos los dos. `instalar` deja el hash intacto; `actualizar -SoloDiff` enseña el diff real sin escribir. Guardarraíl anti-bucle en `instalar_arnes.ps1:151-160` |
| 6 | Genérico separado de específico | **NO** | `arnes-base/arnes-base/.claude/agents/spec-author.md:25-27`. Cambio requerido nº 1 |
| 7 | `init.sh` degrada o declara Python-only | **OK** | Degrada, y la decisión está razonada en la cabecera del propio `init.sh:6-23` y en `GUIA_INSTALACION.md:148`. Ejecutado sobre un destino no Python: salta compilación/lint/tests con AVISO y sigue validando `features.json` |
| 8 | `GUIA_INSTALACION.md` con los tres caminos | **OK** | A (l.17), B (l.44), C (l.69), más `[ADAPTAR]` (115), no-Python (148), fuera de Ruesma (175) |
| 9 | Regla de propagación en ambos `CLAUDE.md` | **OK** | `CLAUDE.md:122-150` de este repo (con el comando concreto del modo actualizar) y `../CLAUDE.md:47-67` |
| 10 | Documento en `azure-apps` según su convención | **NO** | Existe y sigue el formato, pero quedó desfasado. Cambio requerido nº 2 |
| 11 | Probado contra carpeta vacía y contra copia de proyecto | **OK** | La constancia está en el informe §7 con salida real (seis pruebas). Reproduje las equivalentes a 1, 2a y 2b **ya sobre 1.1.0** y coinciden, con el matiz de que ahora se copian 18 ficheros y no 16 |
| 12 | `bash harness/init.sh` de este repositorio en verde | **OK** | exit 0, 65 tests |
| 13 | El equipo no se suspende (añadido 2026-08-09) | **OK con un pero** | Ver §5. Funciona y está bien construido; el «pero» es el BOM del `.ps1` (cambio requerido nº 4) |

## 5. El añadido del 2026-08-09, punto por punto

**`.claude/settings.json` — fusión correcta, sin pérdidas.** Revisado el fichero
entero, no solo el diff:

- `SessionStart` (l.4-15) y `SessionEnd` (l.16-27) **añadidos**.
- `PostToolUse` con matcher `Edit|Write` y pytest (l.28-39): **intacto**.
- `Stop` con `bash harness/init.sh` (l.40-50): **intacto**.
- `permissions.allow` (l.53-61): **los 7 previos, intactos y en el mismo
  orden**. Ninguno borrado, ninguno reescrito.
- El diff `dev...HEAD` no contiene ni una sola línea `-`: son 24 líneas
  añadidas y nada más. No hay reemplazo de configuración.

**`scripts/despierto_hook.sh` — no puede romper el arranque.** Le busqué los
caminos de fallo y los ejecuté (§1). Además del resultado, el diseño lo
sostiene: `.ps1` ausente → `exit 0` en `l.36`; `session_id` ausente → cae a
`sin-sesion` en `l.29` en vez de fallar; PowerShell ausente → las tres
llamadas están blindadas (`l.47` dentro de un `if`, `l.53-55` y `l.61` con
`|| true`); `parar` sin fichero PID → `exit 0` en `l.58`; acción desconocida →
rama `*)` vacía y `exit 0` final. Sin `set -e`, con `set -u` y todas las
variables inicializadas. El saneado del `session_id` a `[A-Za-z0-9._-]`
(`l.32`) evita que un identificador raro se convierta en una ruta.

Un detalle que me gustó porque no es obvio: `l.47` usa
`exit (Get-Process …) -eq $null`, que devuelve 0 cuando el proceso **sigue
vivo** y 1 cuando ya no está. La lógica es correcta en los dos sentidos, y si
el PID guardado fuese basura, PowerShell falla y el hook cae al camino seguro
(borrar el PID y arrancar de nuevo).

**`scripts/mantener_despierto.ps1` — las banderas están bien.** No hay ningún
`0x80000000` suelto: `l.55-57` las declara en decimal y `l.59-61` las combina
en `[int64]` antes de convertir a `[uint32]`. Lo verifiqué en PowerShell 5.1
real: `2147483649` y `2147483651`, y confirmé que el literal hexadecimal
efectivamente se parsea como `Int32 = -2147483648`. Los dos comentarios de
`l.48-54` describen un fallo real, no una precaución teórica.

**Propagación:** `despierto_hook.sh` y `mantener_despierto.ps1` son
**byte a byte idénticos** entre este repositorio y el payload de
`arnes-base`. Documentado en `GUIA_INSTALACION.md:212-245`, con lo que no
cubre y con la salida en no-Windows. El instalador los copia (verificado: 18
ficheros, `scripts/` incluido).

## 6. Cambios requeridos

### 1. `spec-author.md` del arnés genérico nombra las capas de este proyecto

**Fichero:** `C:\Users\pgris\PycharmProjects\arnes-base\arnes-base\.claude\agents\spec-author.md`, **líneas 25-27**.

```
- `specs/F-XXX-slug/design.md` — diseño técnico: ficheros a crear/modificar
  (ruta exacta), clases/funciones, SQL nuevo y en qué capa (`stg`/`mart`/
  `cierre`...), qué NO se toca, y encaje en la arquitectura hexagonal +
  pipeline existente.
```

El criterio nº 6 prohíbe exactamente esto: «ningún fichero del arnés genérico
menciona Sigrid, **las capas stg/mart/cierre**, ni reglas propias de este
proyecto». No es un tecnicismo: es la única mención de las tres capas del
datamart que queda en todo el payload, y sobrevivió porque el patrón del
barrido del implementer (`stg/`, con barra) no casa con `` `stg` ``.

Agrava un poco que **el mismo texto ya está genericizado dos ficheros más
allá**: `arnes-base/specs/SPECS.md:35` dice «capa/esquema al que pertenece».
`spec-author.md` se quedó con la redacción vieja del snapshot.

**Arreglo sugerido** (no lo aplico): alinear con `SPECS.md`, algo del estilo
«SQL nuevo y en qué capa/esquema del proyecto», y bajar «arquitectura
hexagonal + pipeline existente» a «la arquitectura descrita en
`docs/ARCHITECTURE.md`». No hace falta tocar nada más del fichero.

### 2. `azure-apps/arnes_base.md` quedó en 1.0.0

**Fichero:** `C:\Users\pgris\PycharmProjects\azure-apps\arnes_base.md`,
**línea 4** (`> Origen: repositorio arnes-base, commit 212179b`) y
**línea 13** (`- **Versión actual:** 1.0.0 (2026-08-09)`).

`arnes-base` está hoy en **1.1.0**, commit **`8f4d701`**. El documento no
menciona la versión 1.1.0 ni los scripts de energía.

Esto no es un descuido cosmético: la regla 1 del `README.md` de `azure-apps`
dice que el documento «se actualiza en el mismo trabajo, no después», y la
regla 2 exige cabecera con el commit de origen precisamente para que se note
cuándo un documento ha dejado de ser de fiar. El añadido del 2026-08-09
cambió la versión y no refrescó el documento: es, en pequeño, la misma
mecánica que originó F-014.

**Arreglo:** actualizar commit de origen y versión, y añadir una línea sobre
lo que trae 1.1.0. Un commit en `azure-apps`.

### 3. `progress/current.md` describe un estado que ya no es el actual

**Fichero:** `C:\Users\pgris\PycharmProjects\datamart-seg-anual\progress\current.md`,
**líneas 19-24**: «Los **12** criterios `acceptance` quedan cubiertos» y
«el arnés genérico **v1.0.0**».

Son 13 criterios y la versión es 1.1.0. C2 exige que `current.md` describa la
sesión activa, y el líder lee este fichero antes que ningún otro al reanudar.
Añadir además el commit `824e23f` a la lista de commits de la feature.

### 4. `mantener_despierto.ps1` sin BOM

**Ficheros:** `C:\Users\pgris\PycharmProjects\datamart-seg-anual\scripts\mantener_despierto.ps1`
y `C:\Users\pgris\PycharmProjects\arnes-base\arnes-base\scripts\mantener_despierto.ps1`,
**byte 1**.

`docs/CONVENTIONS.md:41` exige «PowerShell: UTF-8 con BOM y CRLF». El fichero
empieza por `35 32 115` (`# s`), sin BOM. Los seis `.ps1` de `infra/` y el
propio `instalar_arnes.ps1` sí lo llevan (`239 187 191`).

Hoy no rompe nada porque el fichero es **100 % ASCII** (lo comprobé), así que
es una deuda latente, no un fallo: en cuanto alguien meta una tilde en un
`Write-Host`, PowerShell 5.1 lo leerá como ANSI y saldrá mojibake. Se arregla
reescribiendo el fichero con BOM. El `.gitattributes` de ambos repos ya
declara `*.ps1 text eol=crlf`, así que la parte de CRLF está cubierta.

## 7. Recomendaciones (no bloquean)

- **R1 — El payload no distribuye `.gitattributes`.** Salió al comparar los
  árboles. El arnés genérico instala un `.ps1` y una convención que exige
  CRLF, pero el mecanismo que la hace cumplir (`*.ps1 text eol=crlf`) se
  queda en `arnes-base` y no llega al destino. Existe el patrón para
  resolverlo: `harness/gitignore.arnes` hace justo eso con el `.gitignore`.
  Un `harness/gitattributes.arnes` cerraría el hueco.
- **R2 — Un test barato que no existe.** Este repositorio tiene pytest y el
  añadido nº 13 cambia `.claude/settings.json` y un script de shell sin
  ninguna red de seguridad. Un `tests/test_f014_arnes.py` con dos
  aserciones —que `settings.json` es JSON válido, tiene los 4 eventos de
  hook y los 7 permisos; y que `despierto_hook.sh` sale 0 sin el `.ps1`—
  convertiría en regresión detectable justo el fallo que más caro sale (un
  hook que rompe el arranque de sesión). Es lo que impide marcar C4 con `[x]`
  limpio.
- **R3 — `scripts/` no está en el mapa de `CLAUDE.md`.** La feature añade dos
  ficheros a una carpeta que el mapa del repositorio no menciona. Una viñeta.
- **R4 — El instalador deja `$LASTEXITCODE = 1` tras enseñar un diff**, porque
  `git diff --no-index` devuelve 1 cuando hay diferencias
  (`instalar_arnes.ps1:78`). Con `-SoloDiff` el resultado «correcto» parece un
  fallo. Da igual a mano; molestará el día que se llame desde un script.
- **R5 — `docs/CONVENTIONS.md` del payload, líneas 11-14**, impone
  arquitectura hexagonal y patrón pipeline sin marca `[ADAPTAR]` ni bloque
  «borrar si no aplica», al contrario que las secciones de Python y SQL que
  están justo debajo. No incumple el criterio 6 (no nombra capas de este
  proyecto), pero es una opinión de arquitectura viajando como si fuera
  universal.
- **R6 — Sobre `azure-apps/partes.md:273`** (§3): decidirlo antes de que ese
  repositorio tenga remoto.

## 8. Propuesta de mejora del protocolo (para que la apruebe el humano)

No la aplico; la dejo escrita.

**El propio informe del implementer (§11) señala el agujero y esta review lo
confirma con un caso real.** El cambio requerido nº 2 es exactamente eso: una
feature que mejora el arnés y deja sin refrescar el documento que lo
describe. Propongo añadir a `CHECKPOINTS.md`, dentro de C5, un punto que el
reviewer recorra:

```
- [ ] Si la feature tocó ficheros del arnés (`CLAUDE.md`, `.claude/agents/`,
      `CHECKPOINTS.md`, `harness/`, `specs/SPECS.md`, `docs/CONVENTIONS.md`):
      lo genérico está portado a `arnes-base` y `harness/VERSION` subido; si
      la versión cambió, el documento de `azure-apps` lo refleja. Si no tocó
      ninguno, N/A.
```

Y, ya que se toca: convertirlo también en el checkpoint del propio arnés
genérico, dentro del bloque `ENTORNO DE RUESMA` de su `CHECKPOINTS.md`.

Segunda propuesta, más pequeña, sobre este mismo fichero de rol
(`.claude/agents/reviewer.md`): el paso 2 manda verificar trazabilidad
requisito→test, pero no dice qué hacer cuando la feature **no produce código
testeable** (documentación, herramientas en otro repositorio). He resuelto
marcando C4 como N/A justificado y sustituyendo los tests por ejecución
reproducida, que creo que es lo correcto, pero convendría que estuviera
escrito en vez de dejarlo al criterio de cada review.

---

**Veredicto: CHANGES_REQUESTED.** Los cuatro cambios son acotados y ninguno
obliga a rehacer nada. Con ellos resueltos, F-014 cierra: el arnés genérico
está bien construido, el instalador hace lo que promete —lo he ejecutado— y
el añadido del 2026-08-09 está mejor verificado que la media.
