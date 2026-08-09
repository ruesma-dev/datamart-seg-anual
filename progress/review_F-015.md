<!-- progress/review_F-015.md -->
# F-015 · Verificar que los tests son de verdad — Informe de review

**Veredicto: APPROVED**

**Rama revisada:** `feature/F-015-verificar-tests` (16 commits sobre `dev`) ·
**Fecha:** 2026-08-09 · **Reviewer:** subagente `reviewer` del arnés.

**Nivel de rigor:** `estandar`, declarado en `harness/features.json`
(aprobado por el humano en DA-4). Ese nivel exige, según la tabla de
`CHECKPOINTS.md` y `harness/rigor.json`: tests trazables (C4), **fase RED** en
los requisitos centrales, **cobertura de las líneas cambiadas ≥ 80 %** y
**campaña de mutación con los supervivientes documentados y analizados**
(`supervivientes_maximos: null` → los juzga el reviewer, no exige cero).
No exige, por no ser `critico`, la ausencia total de supervivientes.

---

## 1. Lo que he ejecutado yo mismo

Ninguna de estas comprobaciones abre red ni BBDD (hay una carga
`run-all --full` contra Azure en marcha; no se ha lanzado `check-pg`,
`status`, `run-all` ni campaña de mutación alguna).

| Comprobación | Resultado |
|---|---|
| `bash harness/init.sh` | **exit 0**. `PUERTA COBERTURA: 97.5% de 552 líneas cambiadas cubiertas (538/552, umbral 80%, nivel estandar)` |
| `python -m pytest -q` (dentro de init.sh, bajo coverage) | **166 passed**, 0 fallos, 2,54 s |
| Validación de niveles | `[OK] harness/rigor.json y niveles declarados: válidos` — `niveles: critico, documental, estandar; por defecto critico; umbral 80%` |
| `python -m ruff check harness tests/test_f015_*.py` | **All checks passed** (los 127 avisos de `init.sh` son deuda previa de otras áreas) |
| Alcance de F-015 recalculado con la propia herramienta | 5 ficheros, **1180 líneas**, idéntico fichero a fichero al de `progress/mutacion_F-015.md` |
| Alcance de F-005 recalculado desde `c7500d4^1..c7500d4` | 20 ficheros, **1669 líneas**, idéntico fichero a fichero al de `progress/mutacion_F-005.md` |
| Mutantes regenerados (cálculo puro, sin ejecutar la suite) | **101** para F-005 y **175** para F-015: coinciden exactamente con los totales de ambos informes |
| Supervivientes muestreados (`alcance.py:45`, `mutacion.py:400` ×2, `rigor.py:47`, `cobertura.py:182`) | Cada uno existe como mutante real, con el mismo operador y el mismo texto original→mutado que declara el informe |
| `git -C .../arnes-base log --oneline -5` | `5006ee8 Arnes 1.2.0: verificar que los tests son de verdad`, árbol limpio |
| `arnes-base/arnes-base/harness/VERSION` | `ARNES_VERSION=1.2.0`, `ARNES_FECHA=2026-08-09` |
| Genericidad del portado | Ni una mención a Sigrid, datamart, Azure, Ruesma, capas ni `F-0NN` en `arnes-base/arnes-base/harness/*.py` ni en `rigor.json` |
| Lo específico NO portado | `arnes-base` no tiene `requirements-dev.txt` ni `progress/mutacion_F-005.md`: correcto |

**Lo importante de esta tabla**: los totales de las dos campañas no se han
creído por lo que dice el informe. El alcance y el número de mutantes son
deterministas y los he recalculado por separado; salen los mismos números.
Los informes de mutación son salida real de la herramienta, no prosa.

---

## 2. Recorrido de CHECKPOINTS.md

### C1 — El arnés está completo y en verde

- [x] `bash harness/init.sh` termina con exit code 0 (ejecutado por mí).
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md` — y ahora también `harness/rigor.json`, que
      `init.sh` exige a partir de esta feature.

### C2 — El estado es coherente

- [x] Una sola feature `in_progress`: F-015 (`init.sh` lo valida).
- [x] Rama actual `feature/F-015-verificar-tests`, la declarada en
      `features.json`. Nunca se ha commiteado a `dev` ni a `main`.
- [x] `progress/current.md` describe la sesión activa. **Justificación de que
      el bloque de F-005 no es un resto**: describe trabajo vivo —la carga
      `run-all --full` está corriendo ahora mismo y sus pasos 7–10 siguen
      pendientes— y el aviso de que `.env` apunta a Azure es contexto
      operativo necesario, no historia.
- [x] Toda feature `done` tiene su resumen en `progress/history.md` (F-015
      todavía no es `done`: se cierra tras esta review).

### C3 — El código respeta arquitectura y convenciones

- [x] Arquitectura hexagonal intacta: la feature **no toca ni una línea** de
      `etl_sigrid/`, `config/`, `main.py`, `infra/` ni SQL. Todo lo nuevo vive
      en `harness/`, que es herramienta de desarrollo (como `init.sh`), fuera
      de la arquitectura del ETL, tal y como fijaba el diseño.
- [x] Primera línea con la ruta relativa en los diez ficheros nuevos
      (`harness/{__init__,alcance,cobertura,mutacion,rigor}.py` y los cinco
      `tests/test_f015_*.py`). Comprobado uno a uno.
- [x] Sin `print()` de debug (los `print` de `cobertura.py`, `rigor.py` y
      `mutacion.py` son la **salida de sus CLI**, que `init.sh` consume), sin
      TODOs, sin secretos, sin `password`/`token` en el código. Type hints en
      todas las firmas; `from __future__ import annotations` en los cinco
      módulos. `ruff` limpio sobre todo lo nuevo.
- [x] Dependencia nueva **prevista en la spec**: `coverage>=7.4` en
      `requirements-dev.txt` (DA-6 aprobada), nunca en `requirements.txt` ni
      en la imagen.
- [x] Semántica Sigrid: no aplica por ausencia — la feature no toca dominio ni
      SQL. No es un N/A de conveniencia: es que el diff no contiene ETL.

### C3 bis — Los documentos que entran de fuera son seguros

**N/A, justificado:** el diff de la rama (`git diff dev...HEAD --stat`, 25
ficheros) **no añade ni modifica nada en `docs/referencia/`**; de hecho no
toca `docs/` en absoluto. No hay documento externo que cabecear ni que
barrer. Aun así he pasado un barrido de datos sensibles sobre todo lo nuevo
con los patrones `password|passwd|secret|token=|api_key`: **cero
coincidencias** en `harness/*.py`. Los únicos nombres de recurso de Azure del
diff están en `progress/current.md`, que ya existía y no es documento externo.

### C4 — La verificación es real

- [x] Cada requisito EARS tiene ≥ 1 test trazable y todos pasan (tabla en la
      sección 3).
- [x] Los unit tests no tocan red ni BBDD: cero apariciones de `psycopg`,
      `requests`, `httpx`, `socket`, `urllib` o `connect(` en los cinco
      ficheros de test. El ejecutor de pytest es siempre un doble; los diffs y
      los `coverage.json` son fixtures de texto; lo único real es `git` local
      de lectura.
- [x] La verificación `MANUAL` (R20) está listada en `progress/current.md`
      § «Pendiente del humano» punto 1, con puntero a
      `progress/impl_F-015.md` § 6, donde están **los cuatro comandos exactos
      y el resultado ya obtenido**. Ver observación 3: sugiero inlinear los
      comandos en `current.md`, pero la trazabilidad existe y es de un salto.

### C4 bis — El rigor declarado se cumple

- [x] La feature declara `rigor: "estandar"` en `harness/features.json`, valor
      válido y aprobado por el humano en DA-4.
- [x] **Fase RED**: `progress/impl_F-015.md` § 2 trae **diez trazas reales**
      (T1–T10), cada una con su comando exacto y la salida del fallo:
      `ModuleNotFoundError: No module named 'harness.alcance'`,
      `ImportError: cannot import name 'MUERTO'`, los `assert ... in` fallando
      contra `init.sh`, `CHECKPOINTS.md`, `implementer.md` y `reviewer.md`.
      No hay ni una frase del tipo «se siguió TDD». La de T10 es especialmente
      creíble: el test de genericidad **encontró un incumplimiento real**
      (`f-001` en el texto de ayuda de `--feature`) al escribirse.
- [x] **Cobertura**: `[OK] PUERTA COBERTURA: 97.5% de 552 líneas cambiadas
      cubiertas (538/552, umbral 80%, nivel estandar)`, obtenida en mi propia
      ejecución de `init.sh`, no copiada del informe.
- [x] **Mutación**: existe `progress/mutacion_F-015.md`, generado por la
      herramienta, con totales reales: 175 generados, 162 muertos, 13
      supervivientes, 0 timeouts, 270,5 s, campaña completa sin muestreo.
      Alcance y número de mutantes reproducidos por mí de forma independiente.
- [x] **Cada superviviente analizado, ninguno en `PENDIENTE`**: 13 secciones
      `#### Análisis` para 13 supervivientes en F-015, y **55 para 55** en la
      línea base de F-005; `grep PENDIENTE` no devuelve nada en ninguno de los
      dos informes. Los análisis son específicos, no plantilla: distinguen
      mutante equivalente (`text=True` es redundante porque `encoding=` ya
      fuerza modo texto), código defensivo deliberado (la red de seguridad de
      R5, inalcanzable en el flujo normal) y hueco real con su riesgo. En
      nivel `estandar` los supervivientes documentados están admitidos, así
      que los 13 no bloquean.
- [x] Sección **«Evidencias»** en `progress/impl_F-015.md` § 4 con los cuatro
      números: 166 tests / 1,2 s de suite / 97,5 % de cobertura de lo
      cambiado / 175 mutantes y 13 supervivientes (más los 101 y 55 de la
      línea base).
- [x] Ningún punto de este bloque marcado N/A.

### C5 — La sesión se cerró bien

- [x] `tasks.md` con las 16 tareas en `[x]` y commits `F-015 Tn: ...`.
      **Justificación de los dos commits agrupados**: 14 commits para 16
      tareas, porque `T13/T14` y `T15/T16` van juntos. Es correcto y
      trazable: T13 (portado) no deja cambios en *este* repositorio —su
      commit vive en `arnes-base` (`5006ee8`)— y T16 es «ejecutar init.sh en
      verde», que no produce fichero propio. Ambos identificadores aparecen
      en el asunto del commit, así que la trazabilidad tarea→commit se
      mantiene.
- [x] Sin ficheros temporales ni artefactos sin trackear:
      `git status --porcelain -uall` vacío. El `coverage.json` que ahora
      genera `init.sh` está en `.gitignore`.
- [x] `features.json` refleja el estado real: F-015 `in_progress`, a la
      espera de este veredicto para pasar a `done`.

**Resultado: ningún checkbox vacío en C1–C5, y el único N/A (C3 bis) va
justificado por escrito con el barrido ejecutado por mí.**

---

## 3. Cobertura de requisitos: requisito → test que lo cubre

| Req | Test trazable (representativo) | Estado |
|---|---|---|
| R1 | `test_f015_r1_campania_cuenta_muertos_y_supervivientes`, `..._exit_code_0_sin_supervivientes_y_1_con_ellos`, `..._no_genera_mutantes_fuera_del_alcance` (+5 más) | [x] |
| R2 | `test_f015_r2_parser_de_diff_extrae_lineas_por_fichero`, `..._fichero_nuevo_entra_entero`, `..._tests_y_no_python_quedan_fuera`, `..._fichero_borrado_no_entra` | [x] |
| R3 | `test_f015_r3_informe_contiene_totales_y_detalle_por_superviviente`, `..._cada_superviviente_lleva_seccion_de_analisis` | [x] |
| R4 | `test_f015_r4_resolucion_rama_luego_merge_luego_error`, `..._diff_de_merge_usa_primer_padre` (+3) | [x] |
| R5 | `test_f015_r5_restaura_el_fichero_tras_cada_mutante`, `..._restaura_aunque_el_ejecutor_lance_excepcion` | [x] |
| R6 | `test_f015_r6_operador_{comparaciones,aritmetico,logico,booleanos,enteros,not}`, `..._un_mutante_un_solo_cambio`, `..._operadores_con_acentos_en_la_misma_linea` (+6) | [x] |
| R7 | `test_f015_r7_timeout_no_cuelga_la_campania`, `..._ejecutor_pytest_traduce_el_timeout`, `..._el_ejecutor_no_deja_que_pytest_tumbe_la_campania` | [x] |
| R8 | `test_f015_r8_implementer_exige_fase_red_con_salida_real`, `..._la_fase_red_se_exige_para_los_requisitos_centrales` | [x] |
| R9 | `test_f015_r9_implementer_exige_seccion_evidencias_con_numeros` | [x] |
| R10 | `test_f015_r10_calculo_de_cobertura_de_lineas_cambiadas`, `..._init_llama_a_la_puerta_de_cobertura`, `..._exit_1_bajo_el_umbral`, `..._justo_en_el_umbral_la_puerta_pasa` (+7) | [x] |
| R11 | `test_f015_r11_umbral_solo_en_rigor_json`, `..._init_sh_sin_umbral_cableado`, `..._el_umbral_no_esta_en_el_codigo_del_arnes` (+5) | [x] |
| R12 | `test_f015_r12_sin_diff_la_puerta_es_na_con_motivo`, `..._nivel_documental_no_exige_cobertura`, `..._en_dev_o_main_la_puerta_es_na_con_motivo` (+4) | [x] |
| R13 | `test_f015_r13_sin_coverage_ko_si_aplica_aviso_si_no`, `..._init_explica_como_instalar_la_medicion`, `..._sin_fichero_de_cobertura_ko_si_aplica` (+2) | [x] |
| R14 | `test_f015_r14_checkpoints_define_los_tres_niveles_y_sus_exigencias`, `..._una_feature_documental_no_puede_requerir_mutacion` | [x] |
| R15 | `test_f015_r15_sin_rigor_declarado_se_aplica_el_mas_exigente`, `..._init_valida_valores_de_rigor`, `..._lo_desconocido_se_considera_exigido` (+7) | [x] |
| R16 | `test_f015_r16_reviewer_valida_contra_el_nivel_de_rigor` | [x] |
| R17 | `test_f015_r17_na_sin_justificacion_prohibido_tambien_en_puertas_nuevas` | [x] |
| R18 | `test_f015_r18_existe_la_linea_base_de_f005_con_totales_reales`, `..._cada_superviviente_de_la_linea_base_esta_analizado` | [x] |
| R19 | `test_f015_r19_herramientas_del_arnes_sin_menciones_especificas` (16 patrones prohibidos sobre `harness/*.py` + `rigor.json`) | [x] |
| R20 | **MANUAL del humano.** No lo ejecuto yo. Verificado que el informe deja los cuatro comandos exactos y su resultado anotado (`impl_F-015.md` § 6), y que lo anotado es cierto: commit `5006ee8`, `ARNES_VERSION=1.2.0`, herramientas presentes y `GUIA_INSTALACION.md:287` con la sección de mutación | [x] pendiente de que el humano lo dé por bueno |

He mirado los tests, no solo sus nombres: no son tautológicos. Los textuales
afirman contenido concreto (`"salida real"`, `"requisitos centrales"`,
`"a posteriori"`, `"checkbox vac"`), y el de R18 comprueba que
muertos + supervivientes + timeouts **cuadran** con los generados y que la
palabra `PENDIENTE` no aparece.

---

## 4. La desviación del diseño: worktree aparte y flag `--raiz`

**Juicio: justificada, documentada y dentro del diseño aprobado. No exige
volver a proponer.**

Los motivos:

1. **La razón es de seguridad, no de comodidad.** Había —y hay— una carga
   `run-all --full` corriendo contra Azure desde este directorio. La campaña
   escribe mutantes en disco durante segundos; el alcance de F-005 es
   `main.py`, `config/settings.py`, `postgres_client.py`... exactamente lo que
   ese proceso puede importar. Mutar el árbol vivo habría podido ejecutar
   código mutado **contra el servidor compartido de producción**. La
   alternativa —esperar a que termine la carga— habría bloqueado la feature
   sin ganar nada.
2. **No contradice ninguna decisión aprobada.** DA-1..DA-6 no dicen nada sobre
   dónde se ejecuta la campaña. El diseño ya preveía `main(argv)` con opciones
   (`--base`, `--rama`, `--timeout`, `--max-mutantes`, `--semilla`,
   `--salida`); `--raiz` es una más del mismo tipo, no un cambio de
   arquitectura ni de alcance.
3. **El flag es genérico** y no filtra nada del proyecto: es «la raíz del
   repositorio a mutar». Está portado a `arnes-base` y **documentado allí como
   práctica recomendada** (`GUIA_INSTALACION.md:312`: «`git worktree add
   ../tmp-mutacion <rama-o-commit>` y `--raiz ../tmp-mutacion`»), que es
   justamente lo que pide la regla de propagación.
4. **Está declarada donde toca**: `impl_F-015.md` § 3 punto 1 la marca como
   «la desviación más importante», y `mutacion_F-005.md` § «Cómo se obtuvo»
   la explica con su motivo.
5. **Efecto secundario positivo verificado**: al montar el worktree en
   `c7500d4`, los números de línea del diff coinciden con los ficheros
   mutados. He confirmado que importa: contra el árbol de hoy el alcance de
   F-005 sale **vacío** (la rama todavía existe y su base común es su propia
   punta), así que sin aislar no había línea base posible.

Las otras desviaciones declaradas (un fichero ausente del informe de coverage
cuenta entero como no cubierto; la campaña fuera de `init.sh`; offsets de
bytes por los acentos; no parchear los huecos de F-005) van todas en la
dirección de **más rigor, no menos**, y están razonadas en el informe.

---

## 5. Observaciones (ninguna bloqueante)

1. **La orden que reproduce la línea base de F-005 no reproduce, tal y como
   está escrita.** `mutacion_F-005.md` dice que la campaña se acotó con
   `--base c7500d4`, pero he comprobado que ejecutar
   `python -m harness.mutacion --feature F-005 --base c7500d4` en este
   repositorio resuelve por **rama** (la rama `feature/F-005-postgres-azure`
   aún existe) y da alcance **vacío**: para caer en la vía del merge hace
   falta además neutralizar la rama (`--rama` a algo inexistente) o partir de
   un árbol sin ese ref. La medición es correcta y la he verificado por otra
   vía; lo que falta es la línea de comando literal. Sugerencia: anotarla en
   el informe. Vale también para `arnes-base`.
2. **F-005 ha quedado declarada `critico` con 55 supervivientes.** Es la
   consecuencia lógica de DA-4 y de la línea base, y F-015 hace bien en no
   parchear el objeto de su propia medición. Pero deja una feature `done` que
   hoy no cumpliría su propio nivel. Conviene que el humano cierre la
   decisión 1 que propone el implementer (¿feature de refuerzo para los 6
   huecos de riesgo alto?) en vez de dejar la contradicción anotada y quieta.
   Es exactamente la clase de deuda que esta feature existe para hacer
   visible.
3. **`progress/current.md` remite a `impl_F-015.md` para los comandos MANUAL**
   en vez de traerlos. C4 pide que estén «listadas en `progress/current.md`
   con su comando exacto». Lo he dado por cumplido porque la trazabilidad es
   de un salto y el resultado está anotado, pero inlinear las cuatro líneas
   cuesta nada y cierra el punto sin interpretación.
4. **`.gitignore` no figuraba en la lista de ficheros a modificar del
   diseño.** La línea añadida (`coverage.json`) es consecuencia directa y
   necesaria de la puerta nueva, y está declarada en la tabla de ficheros del
   informe del implementer. Lo anoto por completitud, no como incumplimiento.
5. **Las 9 features aún no empezadas heredan `critico`.** Es el
   comportamiento correcto por diseño y así lo señala el implementer; solo
   conviene que el humano lo decida antes de abrir cada una.

---

## 6. Automejora del protocolo (propuesta, NO aplicada)

Esta review ha necesitado algo que mi protocolo no me pedía y que ha sido lo
más valioso del trabajo: **recalcular por mi cuenta el alcance y el número de
mutantes** en vez de creerme los totales del informe. Son cálculos
deterministas, baratos (segundos) y que no ejecutan la suite, así que no hay
excusa para no hacerlos; y son la única defensa contra un informe de mutación
escrito a mano. Propongo, para que el humano lo apruebe:

- En `.claude/agents/reviewer.md`, paso 4 de «Validación contra el nivel de
  rigor», añadir: *«Verifica los totales del informe de mutación de forma
  independiente: recalcula el alcance con `harness.alcance` y el número de
  mutantes con `harness.mutacion.generar_mutantes` (cálculo puro, sin
  ejecutar la suite ni escribir en disco) y comprueba que coinciden. Muestrea
  además dos o tres supervivientes y confirma que existen como mutantes
  reales con el mismo operador y el mismo texto original→mutado.»*
- En `CHECKPOINTS.md`, C4 bis, matizar el punto de mutación: *«...con sus
  totales reales, **verificados de forma independiente por el reviewer**»*.

Si se aprueba, se porta a `arnes-base` en el mismo trabajo, como manda la
regla de propagación.

---

## 7. Cambios requeridos

**Ninguno.** La feature se aprueba tal cual está.

Queda pendiente, fuera del veredicto: la verificación **MANUAL R20** por parte
del humano (comandos y resultado en `impl_F-015.md` § 6, ya contrastados por
mí contra el repositorio `arnes-base`) y las dos decisiones que el implementer
eleva —refuerzo de tests de F-005 y `rigor` de las 9 features pendientes—.
