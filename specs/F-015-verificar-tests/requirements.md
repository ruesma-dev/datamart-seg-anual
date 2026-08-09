<!-- specs/F-015-verificar-tests/requirements.md -->
# F-015 · Verificar que los tests son de verdad — Requisitos (EARS)

Marco: la entrada F-015 de `harness/features.json`. Tesis (adoptada del arnés
de Uncle Bob y de old-coder): el humano no revisa código, revisa **evidencias**.
Hoy el arnés comprueba que los tests PASAN; nada comprueba que un test compruebe
lo que dice comprobar. Cuatro defensas: **mutación** sobre las líneas cambiadas,
**fase RED** obligatoria, **cobertura de líneas cambiadas** como puerta de
`init.sh`, y **niveles de rigor** por feature en `CHECKPOINTS.md`.

Es una mejora **GENÉRICA de arnés**: se porta a
`C:\Users\pgris\PycharmProjects\arnes-base` en el mismo trabajo, con subida de
versión y documentación en su `GUIA_INSTALACION.md`.

## Convenciones de verificación

- Los requisitos **[AUTO]** se verifican con pytest, **sin red y sin BBDD**,
  con test trazable `test_f015_rN_*`. Los que validan protocolos (`init.sh`,
  `implementer.md`, `reviewer.md`, `CHECKPOINTS.md`) lo hacen por **análisis
  textual**, igual que hizo F-003 con los `.ps1`.
- Los **[MANUAL]** los ejecuta el humano; llevan el comando exacto.
- Los tests del mutador y de la cobertura usan **fixtures y ejecutores de
  mentira** (diffs de texto, JSON de coverage inventado, runner de pytest
  mockeado). Prohibido que un unit test lance la suite real de pytest de forma
  recursiva o abra conexión alguna.

---

## A. Mutación sobre las líneas cambiadas

### R1 — [AUTO]
El arnés debe proporcionar el comando `python -m harness.mutacion --feature
F-XXX`, que aplica mutaciones **únicamente a las líneas de código de producción
que toca la feature** (nunca al repositorio entero), ejecuta los tests por cada
mutante y reporta cuántos sobrevivieron, terminando con exit code 0 si no hay
supervivientes y 1 si los hay.

> Tests: `test_f015_r1_campania_cuenta_muertos_y_supervivientes` (ejecutor de
> pytest mockeado), `test_f015_r1_exit_code_1_si_hay_supervivientes`,
> `test_f015_r1_no_genera_mutantes_fuera_del_alcance`.

### R2 — [AUTO]
El sistema debe calcular el alcance de la mutación **desde el diff de git de la
rama de la feature contra `dev`** (`git diff dev...<rama>`), nunca de una lista
mantenida a mano: un fichero nuevo entra entero, de un fichero modificado
entran solo las líneas añadidas o cambiadas, y quedan fuera del alcance
`tests/`, `specs/`, `progress/`, `docs/` y todo lo que no sea `*.py` de
producción.

> Tests: `test_f015_r2_parser_de_diff_extrae_lineas_por_fichero` (diff de texto
> como fixture), `test_f015_r2_fichero_nuevo_entra_entero`,
> `test_f015_r2_tests_y_no_python_quedan_fuera`.

### R3 — [AUTO]
CUANDO una campaña de mutación termina, el sistema debe escribir
`progress/mutacion_F-XXX.md` con: el alcance (ficheros y nº de líneas), los
totales (mutantes generados, muertos, supervivientes, timeouts, tiempo total) y,
**por cada superviviente**: fichero, línea, mutación aplicada (original →
mutado) y una sección de análisis «por qué ningún test la caza» que el
implementer debe completar (la herramienta la deja marcada como pendiente).

> Tests: `test_f015_r3_informe_contiene_totales_y_detalle_por_superviviente`,
> `test_f015_r3_cada_superviviente_lleva_seccion_de_analisis`.

### R4 — [AUTO]
CUANDO la rama de la feature ya no existe (feature mergeada en `dev`), el
sistema debe reconstruir el alcance desde su **commit de merge** — localizado
con `git log --merges --grep "F-XXX"` — usando el diff entre el primer padre y
el propio merge; y SI no encuentra ni rama ni merge, ENTONCES debe abortar con
mensaje explícito, sin mutar nada.

> Tests: `test_f015_r4_resolucion_rama_luego_merge_luego_error` (comandos git
> mockeados), `test_f015_r4_diff_de_merge_usa_primer_padre`.

### R5 — [AUTO]
SI la campaña de mutación se interrumpe por cualquier causa (excepción, timeout,
Ctrl-C), ENTONCES el sistema debe **restaurar todos los ficheros mutados a su
contenido original** antes de terminar: jamás puede quedar un mutante escrito en
el árbol de trabajo.

> Tests: `test_f015_r5_restaura_el_fichero_tras_cada_mutante`,
> `test_f015_r5_restaura_aunque_el_ejecutor_lance_excepcion`.

### R6 — [AUTO]
El mutador debe implementar como mínimo estos operadores, cada uno verificable
por separado: inversión de comparaciones (`==`↔`!=`, `<`↔`<=`, `>`↔`>=`),
intercambio aritmético (`+`↔`-`, `*`↔`//`), intercambio lógico (`and`↔`or`),
negación de constantes booleanas (`True`↔`False`), desplazamiento de constantes
enteras (`n`→`n+1`) y eliminación de `not`.

> Tests: `test_f015_r6_operador_comparaciones`, `test_f015_r6_operador_aritmetico`,
> `test_f015_r6_operador_logico`, `test_f015_r6_operador_booleanos`,
> `test_f015_r6_operador_enteros`, `test_f015_r6_operador_not`,
> `test_f015_r6_un_mutante_un_solo_cambio`.

### R7 — [AUTO]
SI un mutante hace que la suite de tests no termine (bucle infinito) o supere el
timeout configurado por mutante, ENTONCES el sistema debe matar la ejecución,
contabilizar el mutante como `timeout` (no como superviviente) y continuar con
el siguiente.

> Test: `test_f015_r7_timeout_no_cuelga_la_campania` (ejecutor mockeado que
> simula el timeout).

---

## B. Fase RED del implementer

### R8 — [AUTO]
El protocolo de `.claude/agents/implementer.md` debe exigir que, para los
requisitos centrales de la feature, el implementer demuestre que el test
**FALLABA antes de existir el código** (fase RED), pegando la **salida real del
fallo** en su informe `progress/impl_F-XXX.md`. Es la defensa directa contra el
test escrito a posteriori para que pase.

> Test: `test_f015_r8_implementer_exige_fase_red_con_salida_real` (análisis
> textual de `implementer.md`).

### R9 — [AUTO]
El protocolo del implementer debe exigir en su informe una sección
**«Evidencias»** con números reales y comparables entre features: nº de tests
ejecutados y resultado, cobertura de las líneas cambiadas (%), mutantes
generados y supervivientes, y tiempo de ejecución de la suite.

> Test: `test_f015_r9_implementer_exige_seccion_evidencias_con_numeros`.

---

## C. Cobertura de las líneas cambiadas en `init.sh`

### R10 — [AUTO]
MIENTRAS la rama actual es una rama de feature con líneas Python de producción
cambiadas frente a `dev` y el nivel de rigor de la feature exige cobertura,
`bash harness/init.sh` debe medir la **cobertura de las líneas cambiadas**
(no la global) y **fallar (KO)** si queda por debajo del umbral configurado.

> Tests: `test_f015_r10_calculo_de_cobertura_de_lineas_cambiadas` (JSON de
> coverage y diff como fixtures), `test_f015_r10_init_llama_a_la_puerta_de_cobertura`
> (textual sobre `init.sh`), `test_f015_r10_exit_1_bajo_el_umbral`.

### R11 — [AUTO]
El umbral de cobertura debe vivir en `harness/rigor.json`, no cableado en el
script: `init.sh` no debe contener ningún número de umbral, y cambiar el umbral
debe consistir en editar solo ese fichero.

> Tests: `test_f015_r11_umbral_solo_en_rigor_json`,
> `test_f015_r11_init_sh_sin_umbral_cableado` (textual).

### R12 — [AUTO]
MIENTRAS la rama actual es `dev` o `main`, o no hay líneas Python de producción
cambiadas frente a `dev`, o el nivel de rigor de la feature no exige cobertura,
la puerta de cobertura debe declararse **N/A con un aviso que explique el
motivo** y no fallar.

> Tests: `test_f015_r12_sin_diff_la_puerta_es_na_con_motivo`,
> `test_f015_r12_nivel_documental_no_exige_cobertura`.

### R13 — [AUTO]
SI `coverage` no está instalado, ENTONCES: cuando la puerta de cobertura
**aplica** (R10), `init.sh` debe fallar con el mensaje de instalación
(`pip install -r requirements-dev.txt`); cuando **no aplica** (R12), debe
degradar con aviso. La omisión de la herramienta no puede ser la vía fácil para
saltarse la puerta.

> Test: `test_f015_r13_sin_coverage_ko_si_aplica_aviso_si_no` (textual sobre
> `init.sh` + unit del helper con el módulo ausente simulado).

---

## D. Niveles de rigor

### R14 — [AUTO]
`CHECKPOINTS.md` debe definir los **niveles de rigor** (documental, estándar,
crítico) y qué exige exactamente cada uno respecto a: tests trazables, fase
RED, cobertura de líneas cambiadas, mutación y verificaciones manuales. Una
feature documental no puede requerir mutación; una que toca infraestructura
compartida en producción debe exigir más que el estándar actual.

> Test: `test_f015_r14_checkpoints_define_los_tres_niveles_y_sus_exigencias`
> (textual).

### R15 — [AUTO]
El sistema debe resolver el nivel de rigor de una feature leyendo el campo
`rigor` de su entrada en `harness/features.json`; SI la feature no lo declara,
ENTONCES debe aplicarse el nivel **más exigente**: la omisión no puede ser la
vía fácil. `init.sh` debe validar que los valores declarados son válidos.

> Tests: `test_f015_r15_sin_rigor_declarado_se_aplica_el_mas_exigente` (unit de
> la función de resolución), `test_f015_r15_init_valida_valores_de_rigor`
> (textual + `features.json` inválido como fixture).

### R16 — [AUTO]
El protocolo de `.claude/agents/reviewer.md` debe exigir validar la feature
**contra su nivel de rigor declarado**: comprobar que existe
`progress/mutacion_F-XXX.md` cuando el nivel exige mutación, que el informe del
implementer contiene la evidencia RED y la sección «Evidencias», y que ningún
checkpoint se marca N/A sin justificación escrita.

> Test: `test_f015_r16_reviewer_valida_contra_el_nivel_de_rigor` (textual).

### R17 — [AUTO]
La nota de `CHECKPOINTS.md` sobre N/A debe cubrir también las puertas nuevas:
ninguna puerta de esta feature (mutación, RED, cobertura) puede saltarse
marcando N/A sin justificación escrita en el informe de review; un N/A sin
motivo se trata como checkbox vacío.

> Test: `test_f015_r17_na_sin_justificacion_prohibido_tambien_en_puertas_nuevas`
> (textual).

---

## E. Línea base sobre código real

### R18 — [AUTO]
El sistema debe haber ejecutado la mutación sobre **al menos una feature ya
cerrada del repositorio** (F-005, reconstruyendo el alcance según R4) y dejar
constancia en `progress/mutacion_F-005.md` de cuántos mutantes se generaron y
cuántos **sobreviven hoy**, con el detalle por superviviente de R3. Ese número
es la línea base del repositorio, aunque incomode.

> Test: `test_f015_r18_existe_la_linea_base_de_f005_con_totales_reales`
> (existencia y campos del informe; la ejecución en sí es la tarea T11 y puede
> ser larga — ver riesgos del diseño).

---

## F. Genericidad y portado al arnés base

### R19 — [AUTO]
Las herramientas nuevas del arnés (`harness/*.py`, `harness/rigor.json`) no
deben mencionar nada específico de este proyecto — ni Sigrid, ni las capas
`stg`/`mart`/`cierre`, ni nombres de recursos de Azure — para ser portables tal
cual a cualquier repositorio.

> Test: `test_f015_r19_herramientas_del_arnes_sin_menciones_especificas`.

### R20 — [MANUAL]
El sistema debe quedar portado a `C:\Users\pgris\PycharmProjects\arnes-base` en
el mismo trabajo: los ficheros genéricos (herramientas de `harness/`,
`rigor.json`, cambios de `init.sh`, `CHECKPOINTS.md`, `implementer.md`,
`reviewer.md`), la versión subida en `arnes-base/harness/VERSION`
(≥ `1.2.0`) y la verificación de tests documentada en `GUIA_INSTALACION.md`,
con un commit en ese repositorio.

```
git -C C:/Users/pgris/PycharmProjects/arnes-base log --oneline -5
grep ARNES_VERSION C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/VERSION
grep -l "mutacion" C:/Users/pgris/PycharmProjects/arnes-base/arnes-base/harness/ -r
grep -n "mutaci" C:/Users/pgris/PycharmProjects/arnes-base/GUIA_INSTALACION.md | head
```
Correcto si `ARNES_VERSION>=1.2.0`, las herramientas están en
`arnes-base/arnes-base/harness/` sin menciones al datamart y la guía documenta
la verificación de tests. El commit lo hace el implementer (local, sin push);
el humano lo revisa.

---

## Fuera de alcance (explícito)

- **Mutación de SQL, PowerShell o YAML**: solo se muta Python de producción.
  El SQL del datamart se defiende con los tests de contrato existentes; mutarlo
  exigiría un motor propio y BBDD (ver decisiones del diseño).
- **Gherkin** y **poda de features por el reviewer**: descartados en la propia
  descripción de la feature.
- **Cobertura global del repositorio** como puerta: solo las líneas cambiadas.
  La deuda previa se ve (como ruff), no bloquea.
- **Asignar retroactivamente nivel de rigor a todas las features cerradas**:
  decisión abierta DA-4 del diseño; aquí solo se define el mecanismo y el
  default (el más exigente).
- **Ejecutar nada contra red o BBDD**: la campaña de mutación y la cobertura
  corren sobre la suite de humo existente, que no abre conexiones.
