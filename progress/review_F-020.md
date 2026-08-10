<!-- progress/review_F-020.md -->
# F-020 · Arnés multi-servicio — Informe de review

**Veredicto: APPROVED**

Rama `feature/F-020-arnes-multiservicio` (verificada con
`git branch --show-current`). Review del 2026-08-10.

## Nivel de rigor y puertas que exige

`harness/features.json` declara **`rigor: "estandar"`** para F-020 (no hay
omisión, no se aplica el `critico` por defecto). El nivel exige, según la tabla
de `CHECKPOINTS.md`: C1–C3, C3 bis, C5, tests trazables (C4), **fase RED** en
los requisitos centrales, **cobertura** de las líneas cambiadas ≥ umbral y
**campaña de mutación** con los supervivientes documentados y analizados. No
exige cero supervivientes (eso es `critico`), pero la campaña salió con cero
de todas formas.

Las cuatro puertas, resueltas:

| Puerta | Resultado verificado por el reviewer |
|---|---|
| `bash harness/init.sh` | **exit 0**, `ENTORNO LISTO` |
| Cobertura | `[OK] PUERTA COBERTURA: 99.4% de 168 líneas cambiadas cubiertas (167/168, umbral 80%, nivel estandar)` |
| Fase RED | Salida real pegada en `progress/impl_F-020.md` para R1–R5, R11–R12, R13–R14, R15–R16, R3+R6–R10 y R17 |
| Mutación | `progress/mutacion_F-020.md`: 46 generados / 46 evaluados / 46 muertos / **0 supervivientes** / 0 timeouts. **Totales recalculados de forma independiente** (ver abajo) |

## Verificaciones ejecutadas por el reviewer

### 1 · Entorno

`bash harness/init.sh` ejecutado **tres veces**. Segunda y tercera: verde, exit
0, `PUERTA COBERTURA` en `[OK]` al 99,4 %, `342 passed`. La **primera** salió en
`[KO] PUERTA COBERTURA: coverage.json no es JSON válido: Expecting value: line 1
column 1 (char 0)`, con `coverage.json` de 0 bytes en el instante de la lectura
y 456 KB válidos inmediatamente después. Causa: esa ejecución coincidió con la
del implementer cerrando T11 (los commits `2c49bf3` y `06b533d` son posteriores
a la foto de `git status` con la que arranqué), y `init.sh` hace `rm -f
coverage.json` antes de regenerarlo, así que dos ejecuciones simultáneas sobre
el mismo árbol se pisan el informe. **No es defecto de F-020**: el camino de
lectura y el mensaje de KO son anteriores a esta feature y su diff no toca esas
líneas. Queda como observación (ver «Automejora»).

`python -m pytest -q` completo: **342 passed**, 0 failed.

### 2 · Retrocompatibilidad (lo crítico de esta feature)

- `pytest -k "f015 or f004 or f003"` → **198 passed**, 0 failed: la suite previa
  pasa intacta.
- Este repositorio **no** declara `harness/servicios.json` (comprobado en el
  árbol y fijado por `test_f020_r2_este_repositorio_no_declara_servicios` y
  `test_f020_r17_este_repositorio_no_declara_servicios_ni_los_necesita`).
- En las tres ejecuciones de `init.sh` **no se imprimió ni una línea de la
  sección 7 bis**: sin declaración, la sección entera queda fuera. La salida del
  portero es la de siempre (mismos `[OK]`, mismos dos `[AVISO]` previos: F-003
  bloqueada y los 127 avisos de `ruff`, deuda anterior).
- El diff de `harness/cobertura.py` conserva el camino mono-proyecto
  explícitamente: `datos = fusionar_coberturas(...) if servicios else cov_raiz or {}`.

### 3 · Verificación INDEPENDIENTE de la mutación

Recalculado con cálculo puro (`harness.alcance.alcance_de_feature` +
`harness.mutacion.generar_mutantes`, sin ejecutar la suite ni escribir en
disco):

| Fichero | Líneas (mío) | Líneas (informe) | Mutantes (míos) |
|---|---|---|---|
| `harness/alcance.py` | 11 | 11 | 2 |
| `harness/cobertura.py` | 60 | 60 | 7 |
| `harness/mutacion.py` | 59 | 59 | 7 |
| `harness/servicios.py` | 280 | 280 | 30 |
| **Total** | **410** | **410** | **46** |

Coincide con el informe al dígito: 4 ficheros, 410 líneas, **46 mutantes**, y el
origen del diff es `rama`. El informe no está escrito a mano.

**Muestreo de los cuatro supervivientes de la primera pasada** (los que el
implementer dice haber tapado). Los cuatro existen como mutantes reales, con el
mismo operador y el mismo texto original→mutado que declara:

```
harness/mutacion.py:603 [logico]     'ejecutor_de=factoria if servicios and ejecutor is None else None,'
                                  -> 'ejecutor_de=factoria if servicios or  ejecutor is None else None,'
harness/servicios.py:43  [booleano]  '@dataclass(frozen=True)'  -> '@dataclass(frozen=False)'
harness/servicios.py:101 [booleano]  '..._texto(entrada, "ruta", nombre, obligatorio=True)...'
                                  -> '..._texto(entrada, "ruta", nombre, obligatorio=False)...'
harness/servicios.py:271 [entero]    'return 0' -> 'return 1'
```

Y los cuatro tests nuevos atacan exactamente la propiedad mutada, leídos uno a
uno en el código: `test_f020_r1_un_servicio_es_inmutable` espera
`dataclasses.FrozenInstanceError`; `test_f020_r3_ruta_ausente_error` exige que
el error siga nombrando `el campo 'ruta'` **con la clave ausente** (no vacía,
que es el caso que ya pasaba por otro camino);
`test_f020_r2_validar_sin_declaracion_es_exito_y_lo_dice` afirma `codigo == 0`;
`test_f020_r15_main_con_servicios_respeta_el_ejecutor_inyectado` comprueba que
un ejecutor inyectado sigue mandando sobre la factoría.

**Mutaciones peligrosas vecinas de la misma línea** (el afinado que pidió el
review de F-004): en `harness/servicios.py:271`, `276` y `279` se generan
`return 0 -> return 1`, `return 0 -> return 1` y
`if __name__ == "__main__" -> if __name__ != "__main__"`. Las tres constan como
muertas en la campaña final y la traza de la segunda pasada pegada en el informe
las muestra nominalmente (`[44/46]`, `[45/46]`, `[46/46]` muertos). Ninguna
sección de análisis en `PENDIENTE`: no hay supervivientes que analizar.

### 4 · Trazabilidad requisito → test

80 tests `test_f020_*` en 6 ficheros. Todos los requisitos [AUTO] R1–R17 tienen
al menos un test trazable y todos pasan:

| Req | Tests que lo cubren |
|---|---|
| R1 | `r1_carga_servicios_validos`, `r1_campos_opcionales_ausentes_valen`, `r1_la_declaracion_se_busca_bajo_la_raiz`, `r1_las_rutas_se_normalizan_a_barras`, `r1_un_servicio_es_inmutable` |
| R2 | `r2_sin_declaracion_lista_vacia`, `r2_cobertura_sin_servicios_camino_actual`, `r2_mutacion_sin_servicios_camino_actual`, `r2_este_repositorio_no_declara_servicios`, `r2_la_campania_sin_factoria_usa_el_ejecutor_unico`, `r2_main_sin_declaracion_no_construye_factoria`, `r2_monorepo_sin_ninguna_medicion_pide_instalarlo`, `r2_sin_servicios_y_sin_coverage_json_pide_instalarlo`, `r2_solo_mide_el_servicio_si_la_raiz_no_tiene_informe`, `r2_validar_sin_declaracion_es_exito_y_lo_dice` |
| R3 | `r3_json_roto_error_explicito`, `r3_rutas_duplicadas_o_solapadas_error`, `r3_nombres_duplicados_error`, `r3_lenguaje_desconocido_error`, `r3_ruta_inexistente_error`, `r3_ruta_ausente_error`, `r3_nombre_o_ruta_vacios`, `r3_entrada_que_no_es_objeto`, `r3_esquema_de_la_raiz_invalido`, `r3_separador_prohibido_en_los_campos`, `r3_validar_por_cli_devuelve_0/1...`, `r3_init_sh_hace_ko_si_declaracion_invalida`, `r3_main_con_declaracion_rota_no_muta_nada` |
| R4 | `r4_resolucion_por_prefijo_mas_largo`, `r4_fuera_de_servicios_devuelve_none` |
| R5 | `r5_interprete_del_venv_windows_y_posix`, `r5_venv_declarado_inexistente_error`, `r5_sin_venv_interprete_del_arnes` |
| R6 | `r6_init_itera_servicios_y_agrega`, `r6_salida_shell_parseable`, `r6_cada_servicio_puede_sumar_al_recuento_de_fallos`, `r6_el_interprete_de_cada_servicio_es_el_que_resuelve_la_herramienta`, `r6_la_suite_de_cada_servicio_corre_desde_su_directorio`, `r6_linea_shell_de_un_servicio_sin_venv`, `r6_shell_falla_si_el_venv_no_existe` |
| R7 | `r7_servicio_sin_tests_aviso_nominal`, `r7_helper_tiene_tests` |
| R8 | `r8_servicio_no_python_degrada_con_aviso`, `r8_comando_tests_cuenta_en_el_agregado` |
| R9 | `r9_una_linea_por_servicio_y_veredicto_unico` |
| R10 | `r10_seccion_multiservicio_condicionada_a_la_declaracion`, `r10_las_secciones_de_siempre_siguen_estando`, `r10_este_repositorio_sigue_siendo_mono_proyecto` |
| R11 | `r11_tests_de_servicio_quedan_fuera`, `r11_codigo_de_servicio_queda_dentro`, `r11_prefijos_de_raiz_siguen_excluidos`, `r11_la_constante_declara_segmentos_no_prefijos` |
| R12 | `r12_alcance_conserva_rutas_de_subcarpetas`, `r12_el_alcance_de_una_feature_no_recorta_las_rutas` |
| R13 | `r13_fusion_reprefija_rutas_de_servicio`, `r13_porcentaje_agregado_contra_umbral_unico`, `r13_fusion_sin_cobertura_de_raiz_y_con_separadores_de_windows`, `r13_un_servicio_en_rojo_hunde_el_agregado`, `r13_declaracion_rota_tumba_la_puerta` |
| R14 | `r14_fichero_sin_medir_cuenta_como_no_cubierto` |
| R15 | `r15_mutante_de_servicio_usa_su_suite`, `r15_mutante_fuera_de_servicios_usa_la_raiz`, `r15_mutante_de_servicio_no_python_usa_la_raiz`, `r15_el_ejecutor_usa_su_cwd_y_su_interprete`, `r15_la_campania_pide_un_ejecutor_por_fichero`, `r15_la_restauracion_aguanta_aunque_la_factoria_falle`, `r15_venv_inexistente_no_cae_al_interprete_global`, `r15_generar_mutantes_no_cambia_con_las_rutas_de_servicio`, `r15_main_con_servicios_respeta_el_ejecutor_inyectado` |
| R16 | `r16_exit_5_es_superviviente`, `r16_exit_1_sigue_siendo_muerto`, `r16_exit_0_sigue_siendo_superviviente`, `r16_otros_codigos_de_error_siguen_siendo_muerto`, `r16_el_timeout_sigue_siendo_timeout` |
| R17 | `r17_herramientas_sin_menciones_especificas`, `r17_la_seccion_multiservicio_de_init_es_generica`, `r17_las_herramientas_no_dependen_del_codigo_del_proyecto`, `r17_este_repositorio_no_declara_servicios_ni_los_necesita` |
| R18 | MANUAL — **re-verificado por el reviewer** (ver §5) |
| R19 | MANUAL — **re-verificado por el reviewer** (ver §5) |
| R20 | MANUAL — salida real pegada en el informe (7 casos: verde, KO agregado, declaración rota, venv inexistente, servicio sin tests, cobertura agregada, mutación por servicio y exit 5). Comandos exactos en `requirements.md` para que el humano la repita |

**Los tests no tocan red ni BBDD** (cómo lo comprobé, no me fío del informe):
barrido de imports sobre los seis `tests/test_f020_*.py` — no aparece `psycopg`,
`requests`, `httpx`, `socket`, `azure` ni cliente alguno; solo `pytest`,
`pathlib`, `json`, `dataclasses`, `re`, `subprocess` y `harness.*`. El único
`subprocess` es `test_f020_mutacion.py`, y ahí se sustituye con
`monkeypatch.setattr(subprocess, "run", RunFalso(...))`: ningún test lanza
pytest de verdad ni crea un venv. Las estructuras de monorepo son fixtures en
`tmp_path`.

### 5 · Portado a `arnes-base` (solo lectura, sin tocar nada)

- Commits locales `cef7857` y `6035bdd` («Arnes 1.3.0: monorepos
  multi-servicio» y el afinado del KO), **sin push**; árbol limpio.
- `arnes-base/harness/VERSION` → `ARNES_VERSION=1.3.0`, `ARNES_FECHA=2026-08-10`.
- En el payload están `harness/servicios.py` y `harness/servicios.ejemplo.json`;
  **no existe** `harness/servicios.json` activo (comprobado: el fichero no está).
- `GUIA_INSTALACION.md` línea 341: sección **«Monorepo multi-servicio (desde
  1.3.0)»**, 13 menciones a `servicios` a lo largo del documento.
- **Paridad exacta**: `diff` de `servicios.py`, `alcance.py`, `cobertura.py` y
  `mutacion.py` entre este repositorio y el payload → **idénticos**, sin
  divergencia.
- **Nada específico del datamart se portó**: barrido de
  `sigrid|datamart|obrparpre|stg\.|mart\.|acralbaranesdev|psql-albaranes|albaranes|partes|portal`
  sobre los cinco ficheros del payload más `servicios.ejemplo.json` → **cero
  coincidencias**.

### 6 · Higiene de git

- `progress/mutacion_F-042.md` **no está en el árbol final** (`ls progress/` lo
  confirma; solo queda en el historial de `0cc344f`, retirado por `628eb1d`).
  Correcto según lo pedido: el artefacto se retiró y no dejó rastro en el árbol.
- `git status --porcelain` **vacío**: sin ficheros temporales ni artefactos sin
  trackear.
- El diff `dev...HEAD` incluye `specs/F-019-plan-mensual-por-tramos/` (3
  ficheros) y `harness/features.json`, que **no son de F-020**: los primeros
  entraron por el `git add -A` del commit `9d58c09` (T8) y el resto es trabajo
  del líder y del spec-author (`bf60eb0`, `da04745`). La desviación **está
  declarada** por el implementer en `progress/impl_F-020.md` § «Desviaciones»,
  punto 5, con el motivo de no revertirla y la lección aplicada. Declarada y
  justificada: no bloquea, pero ver «Cambios recomendados» (no bloqueantes).
- Ficheros de producción tocados = exactamente los previstos por `design.md`:
  `harness/servicios.py` (nuevo), `alcance.py`, `cobertura.py`, `mutacion.py`,
  `init.sh`. Ni `main.py`, ni `config/`, ni `etl_sigrid/`, ni `infra/`.

## Checkpoints (`CHECKPOINTS.md`, C1–C5)

### C1 — El arnés está completo y en verde
- [x] `bash harness/init.sh` termina con exit code 0 (verificado dos veces
      consecutivas; el KO de la primera ejecución fue una colisión con el
      proceso del implementer, explicada en §1).
- [x] Existen `CLAUDE.md`, `harness/features.json`, `specs/SPECS.md`,
      `progress/current.md`, `progress/history.md`, `docs/ARCHITECTURE.md`,
      `docs/CONVENTIONS.md` (los comprueba el propio portero, todos `[OK]`).

### C2 — El estado es coherente
- [x] Una sola feature `in_progress` (`F-020`); lo valida `init.sh`.
- [x] Rama actual `feature/F-020-arnes-multiservicio`, nunca `main`.
- [x] `progress/current.md` describe la sesión activa: encabeza con el aviso de
      `.env`, F-003 bloqueada y F-020 implementada pendiente de review, con los
      números y la desviación declarada. Las secciones de features cerradas que
      arrastra son la memoria viva que este repositorio mantiene a propósito
      (mismo criterio que en reviews anteriores).
- [x] Toda feature `done` tiene su resumen en `progress/history.md` (F-020 aún
      no es `done`: lo escribirá el líder al cerrarla).

### C3 — El código respeta arquitectura y convenciones
- [x] Dominio sin infraestructura y SQL en su capa: **N/A justificado** — la
      feature no toca `etl_sigrid/` ni `sql/`; es herramienta del arnés
      (`harness/`), que no tiene capa hexagonal, como fija `design.md`.
- [x] Primera línea con la ruta relativa en los siete ficheros nuevos
      (verificado uno a uno: `# harness/servicios.py`,
      `# tests/test_f020_*.py`).
- [x] Sin `print()` de debug, sin TODOs, sin secretos hardcodeados. Los cuatro
      `print()` de `servicios.py` son la salida del CLI `--validar`/`--shell`
      (mismo patrón que `cobertura.py` y `mutacion.py`), no depuración.
      `python -m ruff check harness/ tests/` → **All checks passed**.
- [x] Type hints y docstrings en español en todas las funciones nuevas.
- [x] Semántica Sigrid: **N/A justificado** — la feature no toca el ETL ni sus
      reglas de negocio.

### C3 bis — Documentos que entran de fuera
- [x] **N/A justificado**: el diff `dev...HEAD` no añade ni modifica ningún
      fichero bajo `docs/referencia/` (ni ningún `docs/`), así que no hay
      documento externo que auditar, ni original ofimático que buscar, ni
      barrido de datos sensibles que aplicar sobre documentación nueva.

### C4 — La verificación es real
- [x] Cada requisito EARS [AUTO] (R1–R17) tiene ≥ 1 test trazable
      `test_f020_rN_*` y todos pasan (tabla arriba; 80 tests).
- [x] Los unit tests no tocan red ni BBDD: comprobado por barrido de imports y
      por la sustitución de `subprocess.run` (detalle en §4), no por lectura del
      informe.
- [x] Verificaciones MANUAL: R18, R19 y R20 están en `requirements.md` con su
      comando exacto y anotadas en `progress/current.md`; el implementer las
      ejecutó con salida real pegada, y el reviewer ha **re-ejecutado por su
      cuenta** las de R18 y R19 (§5). R20 queda disponible para el humano con
      los comandos exactos.

### C4 bis — El rigor declarado se cumple
- [x] La feature declara `rigor: "estandar"`, valor válido de `harness/rigor.json`.
- [x] **Fase RED** con salida real pegada para los requisitos centrales que pedía
      `tasks.md` (R2, R3, R11, R13, R15, R16): `ModuleNotFoundError: No module
      named 'harness.servicios'`, `ImportError: cannot import name
      'fusionar_coberturas'`, `ImportError: cannot import name
      'PYTEST_SIN_TESTS'`, los 4 fallos de aserción de alcance y los 10 fallos
      de la sección de `init.sh`. Trazas, no promesas.
- [x] **Cobertura**: `[OK] PUERTA COBERTURA: 99.4% ... (167/168, umbral 80%,
      nivel estandar)`, reproducida por el reviewer.
- [x] **Mutación**: `progress/mutacion_F-020.md` generado por la herramienta,
      con totales **recalculados de forma independiente** y coincidentes (§3).
- [x] Ningún superviviente en `PENDIENTE`: la campaña final tiene cero
      supervivientes, y los cuatro de la primera pasada están analizados uno a
      uno con el test que los caza (muestreados y confirmados como mutantes
      reales).
- [x] Sección **«Evidencias»** con los cuatro números: 342 tests en verde,
      99,4 % de cobertura de lo cambiado, 46/46 mutantes con 0 supervivientes,
      3,74 s de suite (122,9 s la campaña).
- [x] Ningún punto de este bloque marcado N/A.

### C5 — La sesión se cerró bien
- [x] `tasks.md` con T1–T11 todas `[x]` y un commit `F-020 Tn: ...` por tarea
      (T1 `6e6b1ab`, T2 `58b37ff`, T3 `2f70998`, T4 `0cc344f` + `628eb1d`,
      T5 `250c98c`, T6 `99f07e2`, T7 `f9c1a3d`, T8 `9d58c09`, T9 `5f6058b`,
      T10 `2c49bf3` + `06b533d`, T11 `06b533d`).
- [x] Sin ficheros temporales ni artefactos sin trackear: `git status` limpio y
      `mutacion_F-042.md` fuera del árbol.
- [x] `features.json` refleja el estado real: `F-020` en `in_progress` con su
      rama, a la espera de que el líder la cierre tras esta aprobación.

## Valoración del trabajo

Lo importante de esta feature no es lo que añade, sino lo que **no** rompe, y
eso está demostrado y no afirmado: 198 tests previos intactos, cero líneas de la
sección nueva ejecutadas en este repositorio y el camino mono-proyecto de
`cobertura.py` conservado explícitamente en el código.

Dos aciertos que merecen constar:

1. **La corrección del exit 5 de pytest (R16) es una deuda descubierta, no una
   funcionalidad pedida.** Hasta hoy, un repositorio sin tests recogidos mataba
   todos sus mutantes: la ausencia de verificación parecía verificación. Afecta
   a todos los repositorios con arnés, no solo a los monorepos, y está
   documentada como tal en el informe y en la guía.
2. **La honestidad de la primera pasada de mutación.** Cuatro supervivientes,
   cuatro análisis, cuatro tests, y ninguno declarado «equivalente» para salir
   del paso. Los cuatro tests atacan la propiedad exacta que la mutación rompía;
   los he leído para comprobarlo.

## Cambios requeridos

Ninguno bloqueante.

## Observaciones no bloqueantes (para el humano, no condicionan la aprobación)

1. **El `git add -A` de T8** metió `specs/F-019-plan-mensual-por-tramos/` en un
   commit de F-020. Está declarado y la decisión de no reescribir historia con
   commits encima es correcta. Solo conviene que el líder lo tenga presente al
   mergear la rama a `dev`: esos tres ficheros de F-019 viajan con ella.
2. **`init.sh` es frágil ante dos ejecuciones simultáneas** sobre el mismo
   árbol: `rm -f coverage.json` deja al otro proceso leyendo un fichero vacío y
   la puerta de cobertura da un KO falso (me pasó en la primera ejecución). Es
   previo a F-020 y no lo agrava; ver «Automejora».
3. **`harness/features.json` sigue con `F-020` en `in_progress`**: es lo
   correcto ahora mismo; el paso a `done` y el resumen en `progress/history.md`
   los hace el líder tras esta aprobación.

## Automejora (propuesta, NO aplicada — decide el humano)

1. **`harness/init.sh`, puerta de cobertura: distinguir «informe vacío» de
   «informe corrupto».** Hoy un `coverage.json` de 0 bytes produce
   `[KO] ... no es JSON válido: Expecting value: line 1 column 1 (char 0)`, que
   apunta al sitio equivocado cuando la causa real es que otro proceso está
   regenerando el fichero. Propuesta: si el fichero existe pero está vacío,
   emitir un KO con un mensaje que nombre la causa probable («¿hay otra
   ejecución de `init.sh` en curso sobre este árbol?»). Es genérico: iría a
   `arnes-base`.
2. **`.claude/agents/implementer.md`: prohibir `git add -A`.** El defecto de T8
   no fue de criterio sino de comando. Una línea en el protocolo del implementer
   —«`git add` de ficheros concretos; `-A` nunca»— lo cierra para siempre y vale
   para cualquier proyecto.
3. **`.claude/agents/reviewer.md`, paso 4: dejar por escrito el muestreo de las
   mutaciones vecinas.** El afinado que propuso el review de F-004 se aplicó en
   esta review pero sigue sin estar en el protocolo. Propuesta: añadir al paso 4
   que, al muestrear supervivientes, se contraste además que las mutaciones
   peligrosas de la **misma línea** constan como muertas.
