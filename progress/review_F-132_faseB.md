<!-- progress/review_F-132_faseB.md -->
Revisión incremental desde a237288 (Fase B, pasada 1) · diff `a237288..d74c9fd` (T16, T17, T18, T20, T21) · 2026-10-09

# F-132 · Review · Fase B, rama BORRAR · APPROVED

**Veredicto: APPROVED.** Cubre la Fase B: R25, R26 y R28, y las tareas T16, T17, T18, T20 y T21. R27 y T19 (congelar) no aplican, por la decisión del humano del 2026-10-09 (`progress/spec_F-132.md` §8). La Fase A ya está aprobada y desplegada (`progress/review_F-132.md`) y no se vuelve a leer. El delta no la invalida: no toca `13_estado_documentos.sql`, `01_documentos.sql` ni `domain/documento_procesos.py`, y de `00_setup.sql` y `12_documento_procesos.sql` solo cambian comentarios (comprobado con el diff filtrado: ninguna línea ejecutable cambia).

**Nivel de rigor: `estandar`**, declarado en `features.json`. Exige fase RED, cobertura de lo cambiado ≥ 80 %, mutación muestreada a 20 con supervivientes analizados y la sección «Evidencias».

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `d74c9fd`, en el árbol principal: **EXIT 0, `ENTORNO LISTO`**. **7.143 passed, 228 skipped, 0 failed** en 774,48 s. `PUERTA COBERTURA` [OK] 100,0 % (42/42, diff desde `09bec58`, que es el merge-base con `main`). `PUERTA TAMAÑO` [OK]. Ruff: 255 avisos de deuda previa; `main.py` baja de 72 a 71 y los ficheros tocados salen limpios.
- **Mutación, recálculo puro** (`harness.alcance.alcance_de_feature` y `generar_mutantes`): **191 líneas en 6 ficheros y 18 mutantes**, lo mismo que el informe. Los 2 supervivientes existen tal cual: `main.py:4985` y `:5008`, operador `entero`, `120→121`. **Campaña no reejecutada**: según el informe duró 3.739,8 s (más de 60 s).
- **Diccionario contado por mi cuenta** desde el YAML: en `a237288` hay v46, **207 objetos, 1623 columnas y 98 de consumo**; en HEAD hay v47, **205, 1608 y 96**. Cuadra con la enmienda de `F-006/design_detalle.md` y con el informe. Las únicas menciones a `historial_estados` que quedan en `config/diccionario/` son la historia de versiones de `00_global.yaml`.
- `azure-apps` `8a8ac98` (sin push): F-067 aparece como RETIRADA, F-132 Fase B como «SIN DESPLEGAR» y el orden del despliegue está escrito.

## Lo que pidió mirar el líder

- **Sin `--confirmar` no se escribe nada.** Solo hay una lectura por `filas_solo_lectura` (`READ ONLY` y `statement_timeout` de 120 s) y no se abre conexión de escritura. Lo fija `test_f132_r26_sin_confirmar_dice_que_borraria_y_no_toca_nada` (`pg.conexiones == []`).
- **Con `--confirmar` se borran solo las dos tablas.** `SENTENCIAS_RETIRADA` contiene `SET LOCAL lock_timeout = '30s'` y `DROP TABLE IF EXISTS compras.historial_estados, compras.historial_estados_fotos`, sin `CASCADE`, en una sola conexión con un solo commit. `PostgresClient.connection()` hace rollback si algo falla. Después vuelve a leer y sale con código 1 si alguna tabla sigue. Los tests fijan el texto exacto, que no lleva `CASCADE`, el commit único y la salida con 1.
- **Nada del ETL las vuelve a crear.** Busqué `historial_estados` en `*.py`, `*.sql`, `*.ps1`, `*.sh`, `*.yaml` y el Dockerfile de todo el repositorio, fuera de `tests/`, `progress/`, `specs/` y `.venv`. Solo aparece en `retirar_foto_sql.py`, en docstrings y comentarios de historia, en el comentario l. 72 de `01_documentos.sql` y en el parche histórico `patches/main_py_patch_compras.py`, que no ejecuta nadie. En ningún sitio hay `CREATE` de esas tablas:
  - `00_setup.sql`: solo cambian comentarios.
  - `reset-compras`: ya no tiene `NOT IN` y borra todas las tablas.
  - `_auto_bootstrap`: solo crea esquemas y `_meta.etl_runs`.
  - `infra/sql/`: ninguna mención.
  - El veto `test_f132_r25_veto_…` lo mantiene en `etl_sigrid/`.
- **El orden del MANUAL** (`impl_F-132_faseB.md` §5) explica bien las tres inversiones, y comprobé dos de las afirmaciones en el código:
  - `check-diccionario` denuncia lo que está «publicado y sin ficha» (`main.py` l. 828).
  - El guardián nocturno `evaluar_construccion` **no** mira lo que la base tiene de más (`catalogo.py` l. 235). Por tanto, la noche siguiente a la imagen nueva **no** falla aunque las dos tablas sigan existiendo.
  - Le falta un matiz: la observación 1.
- **`compras.v_estado_documentos` y `compras.documento_procesos` dan el mismo resultado**: `13` no cambia y en `12` solo cambian comentarios (ver arriba).
- **`fecha_delphi` sigue sirviendo.** `EPOCA_DELPHI` vive en `domain/fecha_delphi.py`, que solo usa la biblioteca estándar. `test_f067_sql` (l. 85) comprueba que la época de `fn_sigrid_tiempo` es esa, y `fn_sigrid_tiempo` no cambia.
- **No hubo escrituras contra Azure ni contra Sigrid.** Mis lecturas fueron git, ficheros y cálculos locales. La única lectura externa del implementer fue el comando sin `--confirmar`, que va en `READ ONLY`.

## Checkpoints

**C1** [x] `init.sh` termina con exit 0 · [x] existen los ficheros del arnés.
**C2** [x] solo F-132 está en `in_progress` · [x] la rama es `feature/F-132-estado-desde-rac` · [x] `current.md` abre con la sesión activa (Fase B), mismo criterio que en la Fase A · [x] el resumen en `history.md` es N/A: la feature aún no está `done`.
**C3** [x] Hexagonal:
  - `fecha_delphi.py` es dominio puro (lo vigila un test).
  - `retirar_foto_sql.py` solo construye texto, en infraestructura.
  - El comando vive en `main.py`.
  - No se renumera el SQL, y el hueco del `11` está explicado.

[x] Primera línea con la ruta en los ficheros nuevos · [x] sin `print` (usa `click.echo`), sin TODO, sin secretos y sin dependencias nuevas · [x] semántica de Sigrid: no se toca.
**C3 bis** N/A: `docs/referencia/` no cambia.
**C4** [x] R25, R26 y R28 tienen test trazable y pasan (tabla abajo) · [x] los tests no tocan red ni BBDD: el SQL se lee como texto y `main._get_pg` se sustituye por un doble · [x] las MANUAL están en `impl_F-132_faseB.md` §5 con su comando exacto y su salida esperada; `current.md` (l. 18-29) apunta ahí · [x] dobles: `_PgFalso` declara `filas_solo_lectura(sql_text, timeout_s)` y `connection()`, que son un subconjunto compatible del cliente real (este tiene además `params=None`), y la puerta de dobles de la suite está en verde.
**C4 bis** [x] `rigor` declarado · [x] **fase RED** con salida real de T17 (13 failed), T18 (23 failed) y T20 (5 failed), en §3 · [x] cobertura 100 % (42/42) · [x] mutación en `progress/mutacion_F-132_faseB.md`, generada por la herramienta y con los totales recalculados (arriba). Campaña completa: 18 mutantes, menos que el tope de muestreo de 20 · [x] muertos comprobados: la campaña no se reejecutó porque pasa de 60 s; se hizo el recálculo puro y RM1-RM6 · [x] coste por mutante: 3.739,8 × 2 / 18 = 415,5 s, del orden de la línea base · [x] sin «⚠ CAMPAÑA NO VÁLIDA», con «Sin veredicto (base rota)» = 0 y una línea base de 427,2 y 425,8 s · [x] **RM1**: medida sobre `b0946ce` (SHA completo). Después solo cambian `tests/`, `progress/` y `tasks.md`, ningún fichero del alcance · [x] **RM2**: media 207,8 s × 2 workers = 415,6 s frente a unos 426 s de línea base, y 18 × 207,8 = 3.740 s cuadra. Que se acerque a la base se explica porque los tests que matan (`test_f132_retirada`, `test_f067_sql`) van tarde en el orden alfabético y `-x` corta tarde · [x] **RM3**: ninguno de los 16 muertos es equivalente. Todos cambian el comportamiento (la época, la guarda `<= 0`, la bandera `--confirmar`, el `+` de cadenas que revienta) · N/A **RM5**: solo aplica en rigor `critico` y aquí no hay equivalentes declarados · [x] **RM6**: no se quitó ninguna guarda; el `NOT IN` de `reset-compras` sale por requisito (R26), no para matar un mutante · N/A campaña manual: la automática dio 18 · [x] los 2 supervivientes tienen su análisis completo y quedan cerrados con un test nuevo (`…lecturas_llevan_su_statement_timeout`, que exige `[120, 120]`) · [x] «Evidencias» con los cuatro números y los workers (§6) · [x] ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] `tasks.md`: T16, T17, T18, T20 y T21 en `[x]` con su commit `F-132 Tn:`. T16 es un cierre documental (`02157ba`). T19 sigue en `[ ]` porque es la rama CONGELAR, que no se eligió (spec §8, `current.md`); ver la observación 2 · [x] `git status` limpio tras `init.sh` · [x] `features.json` en `in_progress`, que es lo correcto hasta que el líder cierre con las MANUAL.

## Cobertura · requisito → test

| Req. | Tests |
|---|---|
| R25 | `test_f132_retirada::r25_*` (12: fichero borrado, sub-paso fuera, `fecha_delphi` con casos y nulos, dominio puro, módulo de la foto borrado, veto) · `test_f067_sql` (época de `fn_sigrid_tiempo` = `EPOCA_DELPHI`) · `test_f047/f073/f080/f085` (listas de sub-pasos) |
| R26 | `test_f132_retirada::r26_*` (SQL de lectura y de borrado; comando sin y con `--confirmar`, `timeout`, código 1, sin tablas, con una sola tabla; `contraste-estados` y su SQL y dominio fuera) · `test_f067_reset::*` (8: sin conservadas, sin `DROP SCHEMA`, orden, veto) · `test_f132_diccionario::r26_las_fichas_de_la_foto_ya_no_estan` |
| R28 | `test_f132_diccionario::r28_ninguna_pregunta_espera_la_foto`, `::r28_architecture_describe_lo_que_queda`, `::r28_la_version_sube_a_47_con_su_historia`, y el test de `azure-apps` que exige `retirar-foto-estados --confirmar` (RED de T20) · recuento 205/1608/96 hecho a mano (arriba) |

## Cambios requeridos

Ninguno.

## Observaciones (no bloquean; para el líder al desplegar o cerrar)

1. **Matiz del MANUAL (§5).** La primera nocturna de la imagen NUEVA ya publica la v47 sola, porque `run-all` incluye `publicar_diccionario`. Si el paso 2 (`retirar-foto-estados --confirmar`) no se hace **antes de esa nocturna**, se abre por sí sola la ventana «3 antes de 2»: `check-diccionario` sale con 1 y el MCP ve dos tablas sin ficha hasta que se borren. No rompe la nocturna (el guardián no mira lo que sobra). Recomendación: lanzar el paso 2 el mismo día que el 1, antes de la nocturna. Así el paso 3 se queda en `check-diccionario` y reiniciar `mcp-bbdd`, y `publicar-diccionario` solo hace falta si la nocturna aún no ha corrido.
2. **`specs/F-132-estado-desde-rac/tasks.md` l. 29**: T19 sigue en `[ ]` sin decir por qué. Su cabecera dice «el líder ajusta esta lista a la rama elegida». Al cerrar, conviene anotarla como «no aplica: rama CONGELAR descartada (spec §8)», para que C5 no vuelva a parecer abierto.
3. **`01_documentos.sql` l. 71-72** (la observación 2 de la Fase A): ahora cita un fichero que ya no existe (`11_historial_estados.sql`). Está fijado por la huella de `test_f073_sql` r23 y el implementer lo deja pendiente para quien toque `01`. Me parece correcto.
4. **Cosmético** (`main.py` l. 5006): «Borradas: …» nombra siempre las dos tablas, aunque solo existiera una (`IF EXISTS`). El estado real ya se imprime antes, línea a línea.

## Automejora (propuesta, no aplicada)

- **A `.claude/agents/reviewer.md`**: cuando una feature retira objetos persistentes con un comando manual, añadir a la lista de lo que hay que mirar si la **nocturna de la imagen nueva** cambia por sí sola algo del orden del MANUAL: publicar el diccionario, aplicar grants, el guardián. Aquí la observación 1 solo salió al leer `run-all`.
