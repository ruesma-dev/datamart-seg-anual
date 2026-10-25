<!-- progress/review_F-149.md -->
Revisión incremental desde af70115 (pasada 2) · `git diff af70115..5e09b8b` · HEAD 5e09b8b

# F-149 · Review · lo que sirve el MCP no nombra reglas que no se publican

- **Veredicto: APPROVED** (los dos cambios de la pasada 1, resueltos; init.sh en verde)
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json`: fase RED, cobertura de
  líneas cambiadas y campaña de mutación (sin cero supervivientes obligatorio).
- `sdd=false`: se valida contra los tres `acceptance`; lo que depende de `tasks.md` es N/A.
- Lo aprobado en la pasada 1 (todo menos los dos cambios requeridos) queda dado por bueno: textos
  nuevos, v61, R14/R26 invertidos sin debilitar, despliegue MANUAL completo, `.env` de marcador
  ignorado y fuera de todo commit. El delta solo toca `tests/test_f149_*`, `progress/current.md` e
  `progress/impl_F-149.md`: ni producción, ni YAML, ni firmas públicas, así que no reabre nada.

## Pasada 1 · resumen (`af70115`, CHANGES_REQUESTED)

1. El detector serializaba la fila a JSON; un salto de línea quedaba como `\n` y el `\b` de
   `CODIGO_DE_REGLA` no veía un código que abriera línea o siguiera a un tabulador.
2. `current.md` no nombraba el cambio de sentido de R26 en `tests/test_f006_copias.py`.

## Pasada 2 · verificación de los dos cambios

**Cambio 1, resuelto.** `_texto` ahora une con saltos reales las cadenas de la fila, recorriendo
tuplas, listas y dicts (claves incluidas) y decodificando los campos que son JSON (`ficha`,
`datos`). Es la vía (a) que se pidió. Comprobado:

- **RED reproducida por mí**: `git archive f938dae` a una copia del scratchpad y el fichero de test
  sobre ella da `1 failed, 13 passed`; falla justo
  `test_f149_caza_un_codigo_al_principio_de_linea_o_tras_un_tabulador` (l.250). Sobre HEAD,
  `14 passed`.
- **Sondas propias sobre HEAD**, con los helpers del test: un código tras `\t` en una descripción,
  tras `\n` en `nulo_significa`, en `ejemplos_preguntas`, en el `motivo` de una regla publicada y en
  una entrada de lista de un bloque de contexto (`esquemas`): los cinco cazados. El test nuevo cubre
  columna, descripción y bloque.
- **Sin falsos positivos ni pérdida de alcance**: sobre el diccionario real, `citas_no_publicadas`
  sigue en `[]` y el barrido mira los mismos 215 textos (158 fichas, 20 reglas, 37 de contexto).
  Conservar la cadena JSON original junto a la decodificada solo añade texto, nunca quita.
- `ruff check` del fichero: limpio.

**Cambio 2, resuelto.** La desviación 1 de `current.md` nombra ya los dos tests y lo que conserva
cada uno (R14: tope de 300; R26: «guia interna del ETL» y «viven en `con`» prohibido).

**Observación, no bloquea.** En `progress/current.md` l.23-24, la frase de la pasada 1 dice «a
JSON y `` ` ``⏎`` ` `` deja la `R`»: el `\n` del texto se escribió como un salto de línea real y el
span de código queda vacío. Es papeleo de sesión, no toca ningún `acceptance`; se arregla al cerrar
(«y el texto `\n` deja la `R` sin frontera de palabra»).

## `bash harness/init.sh` (pasada 2, sobre 5e09b8b)

**exit 0, `ENTORNO LISTO`**; pytest con cobertura `8783 passed, 283 skipped` en 2.530 s (42 min); `PUERTA COBERTURA: N/A` con motivo impreso; `PUERTA TAMAÑO` OK (impl 166/220, review 91/140); sin `[KO]`; único aviso ruff 275 (deuda previa).

## Checkpoints (estado tras la pasada 2)

- C1: [x] init.sh exit 0 (esta pasada) · [x] ficheros del arnés presentes.
- C2: [x] una sola `in_progress` (F-149) · [x] rama `feature/F-149-mcp-sin-reglas-no-publicadas` ·
  [x] `current.md`: lo que conserva de antes son pendientes vivos (R31 de F-148) · [x] las `done`
  tienen resumen en `history.md` (F-149 no cierra nada).
- C3: [x] sin cambios en `etl_sigrid/`; el detector vive en el test · [x] primera línea con ruta ·
  [x] sin prints, TODOs ni secretos; sin dependencias nuevas · [x] semántica Sigrid: sin SQL ni
  importes tocados.
- C3 bis: N/A, no toca `docs/referencia/`.
- C4: [x] acceptance 1 con test y RED real (T1 y T5, las dos reproducidas por mí) · [x] acceptance
  2: `test_f149_version_61`; `check-diccionario` queda MANUAL tras publicar · [x] tests sin red ni
  BBDD · [x] MANUAL en `current.md` con comandos exactos · [x] dobles: no añade ningún `Fake`/`Stub`.
- C4 bis: [x] rigor declarado · [x] fase RED con traza real en el informe (T1: 4 failed; T5:
  1 failed) · [x] cobertura `N/A` con motivo impreso por `init.sh` («no cambia líneas Python de
  producción») · [x] mutación N/A justificado: alcance de producción `{}` recalculado con
  `harness.alcance` en la pasada 1, y el delta no añade producción; prueba de control con
  `generar_mutantes` ignorando la exclusión (28 mutantes sobre los tests): el cero es por diseño ·
  sin campaña no hay informe, RM1/RM2 N/A por alcance vacío · RM5 N/A por nivel `estandar` ·
  RM6 N/A, no se quitó código defensivo · campaña manual N/A, no se sustituyó · [x] «Evidencias»
  con los cuatro números al día (14 tests, 8.783 en la suite).
- C4 ter: N/A, no hay `harness/rutas_sensibles.json`.
- C5: N/A `tasks.md` (`sdd=false`); commits `F-149 Tn:` (T0-T5) · [x] sin temporales trackeados ·
  [x] `features.json` en `in_progress`, el estado real hasta el merge.

## Cobertura acceptance → test

| Acceptance | Test |
|---|---|
| 1 · nada servido cita `fuera_mcp` o inexistente | `test_f149_nada_de_lo_que_llega_al_mcp_cita_una_regla_que_no_se_publica`, `..._r_sigrid_con_no_aparece_...`, `..._el_barrido_mira_...` y siete sintéticos (columna, contexto, regla, aviso, inexistente, exclusiones, principio de línea/tabulador) |
| 2 · v61 con comentario; `check-diccionario` tras publicar | `test_f149_version_61`; `check-diccionario` MANUAL (paso 4 de `current.md`) |
| 3 · init.sh verde, APROBADO, MANUAL en `current.md` | init.sh de esta pasada; `current.md` § «F-149 · Despliegue MANUAL» |

## Cambios requeridos

Ninguno. Al cerrar, corregir la observación de `progress/current.md` l.23-24.

## Propuesta de automejora (no aplicada)

Ninguna al protocolo.
