<!-- progress/review_F-149.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` · base `main` 18c1d11 · HEAD 89eb0f5

# F-149 · Review · lo que sirve el MCP no nombra reglas que no se publican

- **Veredicto: CHANGES_REQUESTED** (un cambio de fondo y uno de papeleo; ver al final).
- **Nivel de rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED, cobertura de
  líneas cambiadas y campaña de mutación (sin cero supervivientes obligatorio).
- `sdd=false`: se valida contra los tres `acceptance`; lo que depende de `tasks.md` es N/A.
- Revisado en el worktree de la rama (`.../scratchpad/wt_main`), no en el árbol principal.

## Lo que se verificó

- `bash harness/init.sh` desde el worktree: **exit 0, `ENTORNO LISTO`**; pytest con cobertura `8782 passed, 283 skipped` en 3.317 s; `PUERTA COBERTURA: N/A` con motivo; `PUERTA TAMAÑO` OK; único aviso ruff 275 (deuda previa).
- **RED reproducida por mí**: `git archive f127f1f` (commit T1, sin tocar los YAML) a una copia en el
  scratchpad y el test nuevo sobre ella: `4 failed, 9 passed`, los mismos cuatro que pega el informe.
- Sobre HEAD, el barrido mira 215 textos: 158 fichas (234 menos las 76 de `raw`), 20 reglas
  publicadas y 37 entradas de contexto. Cuadra con lo que publica `PublicarDiccionarioStep.run`
  (`cargar_diccionario` + `derivar_avisos`, l.123/131) y con `filas_reglas`, que ya excluye las
  `fuera_mcp`. Con una regex más laxa sobre lo servido no aparece ningún código extra.
- Otras superficies: las citas que quedan a `R-SIGRID-CON` están en comentarios `#` del YAML, en la
  ficha de `raw` y en comentarios `--` de cuatro `.sql` (`maestro/06`, `personal/01-03`): ninguna
  llega al MCP (FUERA según la feature). `preguntas_aceptacion` y `reglas` crudas de `global_raw` no
  están en `CONTEXTO_PUBLICADO`.
- Textos nuevos (punto 3): `identidad_sigrid` = «`raw` (la copia de Sigrid) no se consulta desde el
  MCP. Como se lee Sigrid -la clave `ide`, las tablas que son propiedades de `con` y de que lado sale
  cada campo- es guia interna del ETL.» Correcto para la IA: no promete nada que no pueda leer, y no
  repite el contenido de la regla (R26 de F-006). Las columnas, «(`con.cod`)», como su vecina
  `nombre_obra_cabecera` «(`con.res`)». v61 con su comentario de versión (punto 4).
- Tests que cambian de sentido (punto 2): R14 de F-147 conserva el tope de 300 y solo invierte la
  cita; R26 de F-006 invierte la cita, AÑADE «guia interna del ETL» y conserva «viven en `con`»
  prohibido. Nada se debilita más allá de lo que la feature revoca.
- Despliegue MANUAL (punto 5): `progress/current.md` trae tag actual y vuelta atrás, imagen, job con
  comprobación de la imagen ANTES de publicar, `publicar-diccionario` (n_reglas 20),
  `check-diccionario`, lectura de `latestReadyRevisionName` y reinicio de ESA revisión, y la
  comprobación final en `contexto_bbdd()`/`describir_tabla`. Completo y coherente con F-147/F-148.
- `.env` de marcador (punto 6): `git check-ignore` → `.gitignore:31:.env`; no está en `git ls-files`
  ni en ningún commit de `main..HEAD`; dos claves sin secretos. El junction `.venv` también ignorado.
- `ruff check` de los tres ficheros de test: limpio.

## Hallazgo de fondo: el detector no ve un código al principio de línea

`textos_al_mcp` serializa cada fila con `json.dumps`, y JSON escribe un salto de línea como `\n`
(barra + `n`). `CODIGO_DE_REGLA` empieza por `\b`, y entre la `n` del escape y la `R` del código no
hay frontera de palabra. Resultado: **un código que abre una línea o va tras un tabulador no se caza,
en ningún campo** (descripción, columna, bloque de contexto, regla). Probado con los propios helpers
del test (`_con`, `_ficha`, `_columna`):

| Texto servido | `citas_no_publicadas` hoy |
|---|---|
| `'Ver R-GUIA-ETL.'` (en línea) | cazado |
| `'Primera linea.\nR-GUIA-ETL manda.'` (descripción) | **`[]`** |
| `'x\nR-GUIA-ETL'` (significado de columna) | **`[]`** |
| `'linea\nR-GUIA-ETL dice'` (bloque `convenciones`) | **`[]`** |
| `'a\tR-GUIA-ETL'` | **`[]`** |

Hoy ningún texto servido lleva salto de línea (todos son `>-` de un párrafo), así que el veredicto
sobre el diccionario real es correcto. Pero el fichero promete «cerrar la clase, no el caso» y
cubrir «los campos que se añadan mañana», y un bloque `|` o un `>-` con dos párrafos que empiece por
el código pasaría en verde. Es exactamente el punto 1 del encargo («cubrir de verdad TODO»).

## Checkpoints

- C1: [x] init.sh exit 0 (esta pasada) · [x] ficheros del arnés presentes.
- C2: [x] una sola `in_progress` (F-149) · [x] rama `feature/F-149-mcp-sin-reglas-no-publicadas` ·
  [x] `current.md`: lo anterior que conserva son pendientes vivos (R31 de F-148), no restos ·
  [x] las `done` tienen su resumen en `history.md` (F-149 no cierra nada).
- C3: [x] hexagonal: sin cambios en `etl_sigrid/`; el detector vive en el test · [x] primera línea
  con ruta en el test nuevo · [x] sin prints, TODOs ni secretos; sin dependencias nuevas ·
  [x] semántica Sigrid: sin SQL ni importes tocados.
- C3 bis: N/A, no toca `docs/referencia/`.
- C4: [ ] acceptance 1 con test y RED: el test existe y su RED es real, pero tiene el agujero de
  arriba · [x] acceptance 2: `test_f149_version_61`; `check-diccionario` queda MANUAL tras publicar ·
  [x] tests sin red ni BBDD · [x] MANUAL en `current.md` con comandos exactos · [x] dobles: no
  añade ningún `Fake`/`Stub` (usa los constructores reales de `test_f006_formato`).
- C4 bis: [x] rigor declarado (`estandar`) · [x] fase RED con traza real, reproducida por mí ·
  [x] cobertura: `N/A` con motivo impreso por `init.sh` («no cambia líneas Python de producción») ·
  [x] mutación: N/A justificado. Recalculé con `harness.alcance` el diff `main...HEAD`: producción
  `{}`. **Prueba de control** (`generar_mutantes` ignorando la exclusión sobre los `.py` del diff):
  28 mutantes, así que el generador funciona y el cero es exclusión por diseño, no herramienta rota.
  Sin campaña no hay informe que reejecutar ni RM1/RM2 que medir (N/A por alcance vacío). ·
  RM5: N/A por nivel `estandar` · RM6: N/A, no se quitó código defensivo · campaña manual: N/A,
  no se sustituyó (la defensa del detector son sus tests sintéticos) · [x] «Evidencias» con los
  cuatro números.
- C4 ter: N/A, no hay `harness/rutas_sensibles.json`.
- C5: N/A `tasks.md` (`sdd=false`); commits `F-149 Tn:` presentes · [x] sin temporales trackeados ·
  [x] `features.json` en `in_progress`, que es el estado real.

## Cobertura acceptance → test

| Acceptance | Test |
|---|---|
| 1 · nada servido cita `fuera_mcp` o inexistente | `test_f149_nada_de_lo_que_llega_al_mcp_cita_una_regla_que_no_se_publica`, `..._r_sigrid_con_no_aparece_...`, `..._el_barrido_mira_...` y seis sintéticos (columna, contexto, regla, aviso, inexistente, exclusiones) |
| 2 · v61 con comentario; `check-diccionario` tras publicar | `test_f149_version_61`; `check-diccionario` MANUAL (paso 4) |
| 3 · init.sh verde, APROBADO, MANUAL en `current.md` | init.sh de esta pasada; `current.md` § «F-149 · Despliegue MANUAL» |

## Cambios requeridos

1. `tests/test_f149_mcp_sin_reglas_no_publicadas.py` l.55 (`CODIGO_DE_REGLA`) y l.84 (`_texto`):
   que un código tras salto de línea o tabulador se cace. Dos vías, a elegir: (a) recorrer los
   valores de la fila en vez de serializarla, decodificando los dos campos que ya son JSON
   (`ficha`, último de `filas_diccionario`; `datos`, último de `filas_contexto`), o (b) cambiar el
   `\b` por `(?:(?<![A-Za-z0-9_])|(?<=\x5c[nrt]))`; probé la (b) en el scratchpad y caza los cuatro
   casos de la tabla sin cambiar el veredicto real (`[]`). Añadir un test sintético, p. ej.
   `test_f149_caza_un_codigo_al_principio_de_linea`, con el código tras `\n` en una columna y en un
   bloque de contexto, y pegar en el informe su RED contra la regex de hoy.
2. `progress/current.md`, desviación 1 de F-149: nombra solo `test_f147_contenido.py` R14; añadir
   `test_f006_copias.py` R26, que también cambió de sentido (el informe ya lo dice).

## Propuesta de automejora (no aplicada)

Ninguna al protocolo.
