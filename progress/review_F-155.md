<!-- progress/review_F-155.md -->
Revisión completa (pasada 1) · `git diff main..aa2e780` (main = `1d65ca1`)

# F-155 · Review del hotfix «ofertas compartidas entre comparativos»

- **Veredicto: CHANGES_REQUESTED**, solo por el PASO MANUAL de `progress/current.md`.
  **El código, el SQL, el diccionario v68 y los tests quedan APROBADOS tal cual** (no
  hay que tocarlos): la imagen del job se puede construir ya desde `aa2e780`; el cambio pedido
  es solo de `progress/current.md`, que no va en la imagen.
- **Nivel de rigor:** `estandar` (declarado). Exige RED, cobertura y mutación.
- **init.sh (ejecutado por mí sobre `aa2e780`):** `9932 passed, 274 skipped ... (1:15:23)`, «ENTORNO
  LISTO»; `PUERTA COBERTURA: N/A (F-155 no cambia líneas Python de producción frente a main)`;
  `PUERTA TAMAÑO` OK; `Rama actual: feature/F-155-ofertas-compartidas`.

## Lo revisado con especial atención (pedido del líder)

| Consumidor | ¿Oferta compartida duplica? | Verificado |
|---|---|---|
| `comparativo_ofertas` (08) | No: una fila por invitación; B por invitación con `DISTINCT ON (lp.ide)` | sandbox + mutantes M1-M3 |
| `comparativos` (08): recuentos, ganadora, mín/máx, ahorro | No: todo agrega por `comparativo_id` y el grano ya no repite oferta dentro de un comparativo | sandbox (100,25/40,00 y 100,25/30,00) |
| `comparativo_oferta_lineas` (09) | No: cada línea a UNA invitación, misma regla que 08 (`comlin` del comparativo; si no, `invitacion_id` menor). `comparativo_lineas` es `raw.comlin` sin filtrar, así que 08 (`raw.comlin`) y 09 (`compras.comparativo_lineas`) reparten igual | sandbox + M4, M5 |
| `comparativo_objetivo` (09) | No: `con_porcentaje` por (`comparativo_id`,`oferta_id`) | sandbox + M6 |
| `documento_adjuntos` / índice F-090 (14) | No: subconsulta `DISTINCT ON (q.docide)`, una fila por enlace | sandbox + M7 |
| Otras capas (`mart`, `cierre`, `tesoreria`...) | No leen `comparativo_ofertas`: `grep` en `sql/` y `etl_sigrid/` solo da 08, 09, 14 | grep propio |
| MCP `mcp-bbdd` (`adjuntos.origenes.OFERTA`) | `fetchone` sobre un `LEFT JOIN ... oferta_id`: la fila de más no cambia permiso ni resultado | leído `repositorio_postgres.py` |
| Diccionario | Las 5 relaciones que prometían `oferta_id` única pasan a `N:N` con «une también por `comparativo_id`»; grano, clave `invitacion_id`, alternativa (`comparativo_id`,`oferta_id`), aviso de no sumar A sin agrupar; v68 | `test_f155_ninguna_relacion_promete_oferta_id_unica` |
| `ROUND` sobre `raw` sin cast | Ninguno nuevo. 08 hace `SUM(a.tot)::NUMERIC(18,2)` (sin ROUND); el único ROUND de 09 opera sobre `importe_ofertado_linea`, ya `NUMERIC(18,2)`. La sandbox usa `double precision` | leído + sandbox |

Semántica aceptada y documentada (no bloquea): `es_ganadora` es del documento (`con.est = 6`), así que la
ganadora del 0037 sale ganadora también en el COM26/0014; el importe A se repite en cada comparativo.
Decisión de Negocio fuera del hotfix (impl §8).

## Checkpoints

**C1** [x] init.sh exit 0 (ver arriba) · [x] ficheros del arnés presentes.
**C2** [x] una sola `in_progress` (F-150); F-155 en `spec_ready` justificado en `features.json` · [x] rama
`feature/F-155-ofertas-compartidas` (init.sh `[OK]`) · [x] `current.md` lleva F-150 y F-155, las dos vivas ·
[x] ninguna `done` nueva.
**C3** [x] hexagonal: solo SQL de infraestructura, YAML y tests · [x] primera línea con ruta en los ficheros
nuevos · [x] sin prints, sin secretos (la contraseña del contenedor sale como `***` en el informe) ·
[x] semántica Sigrid: `comprv.ide` como grano, documentado en `ARCHITECTURE.md`.
**C3 bis** N/A: no entra ningún documento de fuera.
**C4** [x] cada `acceptance` con test (tabla abajo) · [x] unit tests sin red ni BBDD: la sandbox solo corre
con `F155_SANDBOX_DSN` y se salta en init.sh · **[ ] verificaciones MANUAL listadas con lo esperado
CORRECTO y en orden seguro**: ver Cambios requeridos · [x] dobles: la sandbox usa los tipos de
`information_schema` de Azure (double precision, integer, varchar).
**C4 bis**
- [x] `rigor` declarado (`estandar`).
- [x] RED con salida real (impl §4: `UniqueViolation ... Key (oferta_id)=(11)`, 7 failed + 5 errors).
- [x] Cobertura: `N/A` impreso por init.sh con motivo (ninguna línea Python de producción cambiada).
- [x] Mutación: `harness.mutacion` da alcance vacío. **Recalculado por mí**: `alcance_de_feature('F-155',
  base='main')` → `lineas={}`. Control del cero: el diff no tiene ningún `.py` de producción (solo
  `progress/mutacion_sql_F-155.py` y tests), así que el cero es legítimo por construcción.
- [x] Campaña MANUAL del SQL: `progress/mutacion_sql_F-155.py` trae, por mutante, fichero y texto exacto
  original→mutado (con `assert` de unicidad); el informe da los fallos de cada uno. **Reproducidas las 7
  filas al pie de la letra** sobre una copia (`git archive HEAD`) en mi scratchpad, sin tocar el árbol:
  7/7 muertos con los MISMOS números de fallos (2,1,2,2,1,1,1). Falta el número de línea (ver Automejora).
- [x] Los muertos comprobados (reejecución completa, ~27 s) · [x] coste por mutante coherente (~3,8 s
  frente a ~3,7 s de la sandbox sola, en serie) · [x] sin cabecera de campaña no válida.
- N/A RM1/RM2: no hay informe de `harness.mutacion` (alcance vacío); la manual la reejecuté sobre HEAD.
- N/A RM5: rigor `estandar`, y no hay equivalentes. · [x] RM6: no se quitó código defensivo (la guarda
  R21 de 08 sigue). · [x] sin supervivientes. · [x] «Evidencias» con los cuatro números (workers: 1,
  campaña en serie por construcción del script).
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** N/A `tasks.md`: `sdd=false`, se valida contra `acceptance`; commits `F-155 T1..T6` presentes ·
[x] árbol limpio (`git status`) · [x] `features.json` refleja el estado.

## Cobertura acceptance → test

| Acceptance | Test |
|---|---|
| 1 Grano invitación, clave `invitacion_id` | `test_f155_la_clave_...`, `test_f155_sandbox_una_fila_por_invitacion`, `test_f038_ofertas_r2_grano...` |
| 2 Consumidores sin duplicar (08 ganadora, 09, 14, diccionario, check-unicidad) | `test_f155_sandbox_comparativos_sin_importes_duplicados`, `..._cada_linea_de_oferta_una_vez...`, `..._el_objetivo_de_cada_comparativo`, `..._un_adjunto_..._una_sola_fila`, `test_f155_ninguna_relacion_...`, `test_f108_claves_alternativas` |
| 3 RED→verde en sandbox con tipos reales | impl §4; reejecutado por mí: **13 passed** con `F155_SANDBOX_DSN` |
| 4 Paso MANUAL en `current.md` | presente pero con lo esperado incorrecto: **[ ]** |
| 5 Diccionario v68, init.sh verde | `test_f155_...version`, init.sh (arriba) |

## Cambios requeridos

1. **`progress/current.md`, paso 3 (`check-diccionario` → «esperado: código 0»)** es falso en el orden
   escrito: `main.py:990-1015` sale con código 1 si el hash publicado en `_meta` no es el del árbol, y
   hasta publicar v68 `_meta` sirve v67. El humano verá un KO que el documento le dice que no verá.
2. **El paso MANUAL no da los comandos de publicar el diccionario, de la imagen ni del MCP**, y no fija
   el orden. Reescribirlo con comandos exactos y este orden seguro (todo fuera de 00:00-03:15 UTC, desde
   la rama F-155 en `aa2e780` o posterior):
   1. Imagen del job con F-155: `infra/70_build_image.ps1` y `infra/85_update_job.ps1` (con sus
      parámetros reales), y comprobar que el job apunta a la imagen nueva. **Primero**, porque la
      nocturna republica el diccionario de SU imagen: publicar v68 desde el puesto con la imagen vieja
      dura hasta las 00:00 y la nocturna vuelve a caer.
   2. `.venv/Scripts/python.exe main.py build-compras` (esperado actual: 72.113 / 792.033).
   3. `.venv/Scripts/python.exe main.py check-declarados` → código 0.
   4. `.venv/Scripts/python.exe main.py publicar-diccionario` → v68 publicada.
   5. `.venv/Scripts/python.exe main.py check-diccionario` → código 0 y «lo publicado ES lo del árbol
      (version 68)».
   6. Reiniciar el servidor MCP (`mcp-bbdd` cachea el diccionario hasta reiniciar) y comprobar que sirve v68.
   7. Recordatorio: F-155 tiene que entrar en `main` antes de la próxima imagen construida desde `main`,
      o el arreglo se pierde.

## Automejora (propuesta, no aplicada)

- `CHECKPOINTS.md` C4 bis, campaña MANUAL: admitir explícitamente como «tabla» un script versionado que
  lleva el texto exacto original→mutado con `assert` de unicidad (es más reproducible que una tabla) y
  exigir que su salida imprima el número de línea del fichero mutado.
- `CHECKPOINTS.md` C4: un paso MANUAL que mande ejecutar `check-diccionario` debe ir DESPUÉS de
  `publicar-diccionario` cuando la feature sube la versión.
