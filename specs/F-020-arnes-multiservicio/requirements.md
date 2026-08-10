<!-- specs/F-020-arnes-multiservicio/requirements.md -->
# F-020 · Arnés multi-servicio — Requisitos (EARS)

Marco: la entrada F-020 de `harness/features.json`. Las apps del ecosistema
(albaranes con 6 repos, partes, portal) van a unificarse en UN monorepo por
app vía git subtree, con servicios en subcarpetas (`services/email/`,
`services/api/`, `infra/`...) y UN arnés en la raíz. El arnés actual asume un
único proyecto Python en la raíz. Esta feature lo prepara para varios
servicios —cada uno con su venv, sus tests y posiblemente otro lenguaje—
**sin romper el caso mono-proyecto**: un repositorio como este datamart debe
seguir funcionando sin configurar absolutamente nada.

Es una mejora **GENÉRICA de arnés**: se porta a
`C:\Users\pgris\PycharmProjects\arnes-base` en el mismo trabajo, con subida
de versión a **1.3.0** y documentación en su `GUIA_INSTALACION.md`.

Restricción de entorno: el puesto del humano tiene **Windows PowerShell 5.1
(sin pwsh 7) y Git Bash**. Todo script nuevo o modificado debe funcionar en
ese entorno; nada puede exigir pwsh 7 ni bash de Linux con utilidades no
presentes en Git Bash.

## Convenciones de verificación

- Los requisitos **[AUTO]** se verifican con pytest, **sin red y sin BBDD**,
  con test trazable `test_f020_rN_*`. Los que validan `init.sh` lo hacen por
  **análisis textual** (mismo patrón que F-015 con los protocolos) y/o por
  unit test de los módulos Python que `init.sh` invoca.
- Las estructuras de monorepo se simulan con **fixtures en `tmp_path`**
  (directorios y ficheros creados por el propio test): ningún test depende de
  que este repositorio cambie de estructura, porque no la cambia.
- Los ejecutores de tests y de git se **mockean** (mismo patrón que F-015):
  prohibido que un unit test lance la suite real de forma recursiva, cree un
  venv real o abra conexión alguna.
- Los **[MANUAL]** los ejecuta el humano (o el implementer con evidencia real
  pegada en su informe, y el humano los repite si quiere); llevan el comando
  exacto.

---

## A. Declaración de servicios (`harness/servicios.json` + `harness/servicios.py`)

### R1 — [AUTO]
El arnés debe proporcionar el módulo `harness/servicios.py` con una función
`cargar_servicios()` que lea la declaración **opcional**
`harness/servicios.json`, donde cada servicio declara: `nombre` (único),
`ruta` (relativa a la raíz del repositorio), `lenguaje` (`python` u `otro`)
y, opcionalmente, `venv` (ruta relativa al venv del servicio) y
`comando_tests` (suite de un servicio no Python).

> Tests: `test_f020_r1_carga_servicios_validos`,
> `test_f020_r1_campos_opcionales_ausentes_valen`.

### R2 — [AUTO]
SI `harness/servicios.json` no existe, ENTONCES el arnés entero debe
comportarse **exactamente igual que hoy** (modo mono-proyecto):
`cargar_servicios()` devuelve lista vacía y las puertas de cobertura y
mutación siguen su camino actual sin ningún cambio observable. Un repositorio
mono-proyecto no configura nada.

> Tests: `test_f020_r2_sin_declaracion_lista_vacia`,
> `test_f020_r2_cobertura_sin_servicios_camino_actual`,
> `test_f020_r2_mutacion_sin_servicios_camino_actual`.

### R3 — [AUTO]
SI `harness/servicios.json` existe pero es inválido —JSON roto, `nombre` o
`ruta` duplicados, rutas solapadas (una dentro de otra), `lenguaje`
desconocido, o `ruta` que no existe en el disco—, ENTONCES
`cargar_servicios()` debe fallar con un error explícito que nombre el
problema, y `bash harness/init.sh` debe terminar en KO: una declaración rota
no puede degradar en silencio a mono-proyecto.

> Tests: `test_f020_r3_json_roto_error_explicito`,
> `test_f020_r3_rutas_duplicadas_o_solapadas_error`,
> `test_f020_r3_lenguaje_desconocido_error`,
> `test_f020_r3_ruta_inexistente_error`,
> `test_f020_r3_init_sh_hace_ko_si_declaracion_invalida` (textual).

### R4 — [AUTO]
CUANDO se consulta a qué servicio pertenece una ruta del repositorio
(`servicio_de_ruta`), el sistema debe resolver por **prefijo más largo**
entre las rutas declaradas (separadores normalizados) y devolver `None` para
una ruta fuera de todo servicio.

> Tests: `test_f020_r4_resolucion_por_prefijo_mas_largo`,
> `test_f020_r4_fuera_de_servicios_devuelve_none`.

### R5 — [AUTO]
DONDE un servicio Python declara `venv`, el arnés debe usar el intérprete de
ESE venv (`Scripts/python.exe` en Windows, `bin/python` en POSIX) para sus
tests, su cobertura y su mutación; SI el `venv` declarado no existe en disco,
ENTONCES debe fallar con error explícito (no caer en silencio al intérprete
global, que probaría con dependencias equivocadas); y DONDE no declara
`venv`, debe usar el intérprete con el que corre el arnés.

> Tests: `test_f020_r5_interprete_del_venv_windows_y_posix`,
> `test_f020_r5_venv_declarado_inexistente_error`,
> `test_f020_r5_sin_venv_interprete_del_arnes`.

---

## B. `init.sh` multi-servicio

### R6 — [AUTO]
MIENTRAS `harness/servicios.json` declara servicios, `bash harness/init.sh`
debe ejecutar, **por cada servicio Python**, su suite de tests desde el
directorio del servicio y con el intérprete que resuelve R5, y **agregar el
resultado**: un KO en cualquier servicio hace KO el veredicto global. La
compilación (`compileall`) sigue siendo una sola pasada desde la raíz, que
cubre todos los servicios (la sintaxis no depende del venv).

> Tests: `test_f020_r6_init_itera_servicios_y_agrega` (textual sobre
> `init.sh`: existe la sección, consume `harness.servicios`, acumula
> `FALLOS`), `test_f020_r6_salida_shell_parseable`
> (unit de `python -m harness.servicios --shell`).

### R7 — [AUTO]
SI un servicio Python no tiene directorio de tests, ENTONCES `init.sh` debe
emitir un AVISO que **nombre al servicio** («nadie está comprobando los tests
de X») sin convertirlo en KO: igual que hoy hace el arnés mono-proyecto con
un repo sin `tests/`.

> Tests: `test_f020_r7_servicio_sin_tests_aviso_nominal` (textual + unit del
> helper que decide si el servicio tiene tests).

### R8 — [AUTO]
DONDE un servicio declara `lenguaje: otro`, `init.sh` debe degradar con
aviso las comprobaciones de Python para ese servicio; y DONDE además declara
`comando_tests`, debe ejecutarlo desde la ruta del servicio y su resultado
cuenta en el agregado (KO si falla). Sin `comando_tests`, aviso nominal de
que nadie comprueba ese servicio.

> Tests: `test_f020_r8_servicio_no_python_degrada_con_aviso` (textual),
> `test_f020_r8_comando_tests_cuenta_en_el_agregado` (textual).

### R9 — [AUTO]
CUANDO `init.sh` valida un monorepo, debe imprimir **una línea de resultado
por servicio** (nombre y veredicto) y mantener un único veredicto final
(`ENTORNO LISTO` / exit 0, o el recuento de fallos / exit 1), para que el
resultado por servicio quede visible en el mismo formato `[OK]/[AVISO]/[KO]`
que el resto del portero.

> Test: `test_f020_r9_una_linea_por_servicio_y_veredicto_unico` (textual).

### R10 — [AUTO]
MIENTRAS no existe `harness/servicios.json`, `init.sh` no debe ejecutar
ninguna sección multi-servicio: el flujo mono-proyecto actual (secciones de
compilación, lint, tests y puerta de cobertura) queda intacto. En este
repositorio datamart, `bash harness/init.sh` debe seguir en verde sin ningún
cambio de comportamiento tras adoptar la mejora.

> Tests: `test_f020_r10_seccion_multiservicio_condicionada_a_la_declaracion`
> (textual), más la tarea final de `tasks.md` (init.sh real en verde).

---

## C. Alcance, cobertura y mutación con subcarpetas de servicios

### R11 — [AUTO]
`harness.alcance.es_produccion` debe excluir `tests/`, `specs/`, `progress/`
y `docs/` como **segmento de ruta en cualquier nivel**, no solo como prefijo
de la raíz: `services/email/tests/test_x.py` queda fuera del alcance y
`services/email/app/flujo.py` queda dentro. (Hoy solo se excluye el prefijo:
los tests de un servicio entrarían como código de producción a mutar y
medir, que es exactamente lo contrario de lo que son.)

> Tests: `test_f020_r11_tests_de_servicio_quedan_fuera`,
> `test_f020_r11_codigo_de_servicio_queda_dentro`,
> `test_f020_r11_prefijos_de_raiz_siguen_excluidos` (no romper F-015).

### R12 — [AUTO]
CUANDO el diff de la feature contiene ficheros bajo subcarpetas de servicios,
el alcance debe conservarlos con su **ruta relativa a la raíz del
repositorio** (tal como los da `git diff` ejecutado en la raíz): es el
candado que garantiza que alcance, cobertura y mutación comparten la misma
noción de «qué cambió» también en un monorepo.

> Test: `test_f020_r12_alcance_conserva_rutas_de_subcarpetas` (diff de texto
> como fixture, sin git real).

### R13 — [AUTO]
MIENTRAS hay servicios declarados, la puerta de cobertura debe **fusionar**
el `coverage.json` de cada servicio Python re-prefijando sus rutas con la
ruta del servicio (el JSON de coverage de un servicio numera respecto al
directorio del servicio; el alcance numera respecto a la raíz), sumarle el
`coverage.json` de la raíz si existe, y medir **un único porcentaje
agregado** de las líneas cambiadas contra el umbral de `harness/rigor.json`.

> Tests: `test_f020_r13_fusion_reprefija_rutas_de_servicio`,
> `test_f020_r13_porcentaje_agregado_contra_umbral_unico` (JSONs de coverage
> inventados como fixtures).

### R14 — [AUTO]
SI un fichero cambiado de un servicio Python no aparece en ningún
`coverage.json` (servicio sin tests, o módulo que ningún test importa),
ENTONCES sus líneas ejecutables deben contar como **no cubiertas** en el
agregado: pertenecer a un servicio sin suite no puede salir gratis, igual
que hoy no sale gratis un módulo nuevo sin importar.

> Test: `test_f020_r14_fichero_sin_medir_cuenta_como_no_cubierto`.

### R15 — [AUTO]
CUANDO la campaña de mutación evalúa un mutante cuyo fichero pertenece a un
servicio declarado, debe ejecutar **la suite de ese servicio** (su
intérprete según R5, su directorio como cwd), no la de la raíz; y CUANDO el
fichero no pertenece a ningún servicio, debe ejecutar la suite de la raíz
como hoy. La garantía de restauración del árbol (R5 de F-015) se mantiene
intacta en ambos casos.

> Tests: `test_f020_r15_mutante_de_servicio_usa_su_suite` (ejecutores
> mockeados), `test_f020_r15_mutante_fuera_de_servicios_usa_la_raiz`.

### R16 — [AUTO]
SI la suite invocada para un mutante no recoge ningún test (pytest exit code
5), ENTONCES el mutante debe contabilizarse como **SUPERVIVIENTE**, nunca
como muerto: hoy cualquier código de salida distinto de 0 cuenta como
muerto, y en un servicio sin tests eso daría por cazados mutantes que nadie
caza. Es el mismo principio de F-015: la ausencia de verificación no puede
parecer verificación.

> Tests: `test_f020_r16_exit_5_es_superviviente`,
> `test_f020_r16_exit_1_sigue_siendo_muerto`.

---

## D. Genericidad, portado a `arnes-base` y prueba real

### R17 — [AUTO]
Las herramientas nuevas o modificadas del arnés (`harness/servicios.py` y los
cambios en `alcance.py`, `cobertura.py`, `mutacion.py`, `init.sh`) no deben
mencionar nada específico de este proyecto —ni Sigrid, ni las capas
`stg`/`mart`/`cierre`, ni recursos de Azure— ni de las apps concretas
(albaranes, partes, portal): son portables tal cual a cualquier repositorio.

> Test: `test_f020_r17_herramientas_sin_menciones_especificas`.

### R18 — [MANUAL]
El sistema debe quedar portado a `C:\Users\pgris\PycharmProjects\arnes-base`
en el mismo trabajo: los ficheros genéricos actualizados, un
`harness/servicios.ejemplo.json` en el payload (ejemplo documentado que **no
activa nada** al instalarse: el fichero activo es `servicios.json` y lo crea
cada monorepo a mano), `ARNES_VERSION>=1.3.0` en
`arnes-base/harness/VERSION`, y un commit local en ese repositorio (sin
push). `instalar_arnes.ps1` no necesita cambios de código (recorre el
payload completo), y cualquier ajuste que sí necesitara debe funcionar en
Windows PowerShell 5.1.

```powershell
git -C C:\Users\pgris\PycharmProjects\arnes-base log --oneline -5
Select-String ARNES_VERSION C:\Users\pgris\PycharmProjects\arnes-base\arnes-base\harness\VERSION
Get-ChildItem C:\Users\pgris\PycharmProjects\arnes-base\arnes-base\harness\servicios*
```
Correcto si `ARNES_VERSION>=1.3.0`, existe `harness/servicios.py` y
`harness/servicios.ejemplo.json` en el payload, y NO existe un
`harness/servicios.json` activo en el payload.

### R19 — [MANUAL]
`GUIA_INSTALACION.md` de `arnes-base` debe ganar la sección del camino
**monorepo multi-servicio**: cómo declarar `harness/servicios.json` (esquema
y ejemplo), venvs por servicio, servicios no Python con `comando_tests`, qué
pasa con un servicio sin tests, y la garantía de que **sin declarar nada el
arnés es mono-proyecto** como siempre.

```powershell
Select-String -Pattern "servicios" -Path C:\Users\pgris\PycharmProjects\arnes-base\GUIA_INSTALACION.md
```
Correcto si la guía documenta la declaración, la degradación de servicios no
Python y el caso «sin configurar = mono-proyecto».

### R20 — [MANUAL]
El arnés multi-servicio debe probarse **de verdad** contra una estructura de
varios servicios: un monorepo temporal (fixture fuera de este repositorio,
p. ej. en el scratchpad) con al menos un servicio Python con venv y tests
propios y un servicio no Python, instalado con
`.\instalar_arnes.ps1` desde **Windows PowerShell 5.1**, con su
`harness/servicios.json` configurado, y con `bash harness/init.sh` (Git
Bash) detectando y validando ambos servicios con el agregado correcto. La
salida real (instalador e init.sh) se pega en el informe del implementer; el
humano puede repetirla con los mismos comandos.

```powershell
# desde arnes-base, contra el monorepo temporal creado para la prueba
.\instalar_arnes.ps1 -Destino "<monorepo-temporal>"
```
```bash
cd <monorepo-temporal> && bash harness/init.sh
```
Correcto si init.sh imprime una línea por servicio, el servicio Python pasa
sus tests con su venv, el no Python degrada con aviso, y el veredicto global
agrega bien (se comprueba también el caso KO rompiendo un test del servicio
Python).

---

## Fuera de alcance (explícito)

- **La migración de cada app a su monorepo** (subtrees, reorganización de
  repos, sus documentos de `azure-apps/`): es trabajo de los repos de cada
  app, con esta feature como prerrequisito.
- **Pipelines CI/CD**: el despliegue del ecosistema es manual por consola y
  así se queda; el arnés no adquiere integración continua.
- **Mutación o cobertura de servicios no Python**: se degrada con aviso,
  igual que hoy en un repo no Python. Solo se ejecuta su `comando_tests` si
  lo declaran.
- **Creación o gestión de venvs por servicio**: el arnés usa el venv que el
  servicio ya tiene; crearlo es responsabilidad de cada servicio.
- **Cambios de estructura en este repositorio datamart**: no se crea
  `services/`, no se declara `servicios.json`; solo recibe la mejora de las
  herramientas, cuyo comportamiento mono-proyecto es idéntico (R2, R10).
- **Features que cruzan servicios en las specs**: el flujo SDD ya es agnóstico
  a rutas; no requiere cambios.
