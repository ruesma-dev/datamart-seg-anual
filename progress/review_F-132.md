<!-- progress/review_F-132.md -->
Revisión completa (pasada 1) · FASE A · diff `4d25fcb..ef67f4e` (implementer) sobre base `main` 43a50b9 · 2026-10-09

# F-132 · Review · Fase A · APPROVED

> **Fase B (rama BORRAR): APPROVED el 2026-10-09** sobre `d74c9fd`, en `progress/review_F-132_faseB.md`.

**Veredicto: APPROVED** (solo la Fase A: T1-T13 y T15. T14 es MANUAL del humano. La Fase B, T16-T21, NO está revisada ni empezada).

**Nivel de rigor: `estandar`** (declarado en `features.json`). Exige fase RED, cobertura ≥ 80 % de lo cambiado, mutación muestreada (20, semilla del nivel) y la sección «Evidencias».

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `ef67f4e`, árbol principal: **EXIT 0, `ENTORNO LISTO`**. **7.245 passed, 229 skipped, 0 failed** en 938,66 s. `PUERTA COBERTURA` [OK] 100,0 % (142/142). `PUERTA TAMAÑO` [OK] (requirements 150/150, design 246/250, impl 218/220). Ruff sigue en 255 avisos, deuda previa: `main.py` daba 73 antes (`4d25fcb`) y da 73 ahora, y los ficheros nuevos salen limpios.
- **Mutación, recálculo puro e independiente** (`harness.alcance` + `generar_mutantes`): **546 líneas, 79 mutantes**, igual que el informe. Rehecho el sorteo (`random.Random(20260820)`): salen los mismos 20, y entre ellos los 2 supervivientes declarados, con el mismo operador y el mismo texto (`main.py:4955 default=300→301`, `:4956 show_default=True→False`). La campaña **no se ha reejecutado**: según el informe tardó 5.596 s (más de 60 s), así que me quedo en el recálculo puro y RM1-RM6.
- **La foto no cambia ni una línea ejecutable**: reconstruí `11_historial_estados.sql` de `4d25fcb` quitándole el bloque de la vista, sin comentarios y compactado. El texto coincide y su sha256 es `dce136a1…865f8`, la `HUELLA_FOTO` que fija el test.

## Lo que pedía mirar el líder

- **Nada de la Fase B se ha colado.** El diff no añade ningún `DROP`, `TRUNCATE` ni `DELETE` sobre `compras.historial_estados*`. El único `DROP` nuevo es `DROP VIEW IF EXISTS compras.v_estado_documentos` en `13`. `compras_reset_sql.py` solo cambia su docstring y `SQL_RESET_COMPRAS` sigue con `NOT IN (TABLAS_PERSISTENTES)`. No hay comando `retirar-foto-estados`. `domain/historial_estados.py` solo cambia su docstring.
- **El contraste es de solo lectura y no corre de noche.** Las cuatro consultas son `SELECT` y van por `filas_solo_lectura`, que abre una transacción `READ ONLY` con `SET LOCAL statement_timeout`. Hay tests que comprueban que ningún SQL escribe y que todas las lecturas pasan por ese método. `contraste` no aparece en `run-all`, en ningún step ni en `infra/`. Desviación aceptada: la spec pedía `read_only=True` en la conexión y se usa la vía única del repositorio, que da la misma garantía porque la impone el motor.
- **La premisa falsa ha desaparecido.** El test R22 tiene 12 frases sobre lo vigente. Además hice un grep propio más amplio («no existe en Sigrid», «Sigrid no guarda», «no hay copia», «ninguna tabla guarda», «lo único que sabe cuándo», «tiemod…aproxim») sobre `main.py`, `etl_sigrid`, `config`, `docs` y `README*`. No queda ninguna afirmación sobre el estado; los aciertos que salen son de otros temas (F-118, `reshor`, nulos). Sitios de la spec revisados uno a uno: fichas de `compras.yaml`, `raw.conest`, `00_global` (v46, P23, P24, esquema), `tables_sigrid` C3, `ARCHITECTURE`, `README_COMPRAS_C1_C2` y `azure-apps` (`89f63d5`: F-067 «DESPLEGADA», sección F-132 nueva, sin «Sigrid no la guarda» ni «no hay copia»).
- **`compras.documento_procesos` (F-085) no cambia.** Ni `12_documento_procesos.sql` ni `domain/documento_procesos.py` están en el diff. La vista lee `es_ultimo` tal cual. `01_documentos.sql` se tocó y se revirtió: queda idéntico a `4d25fcb`.
- **No hubo escrituras contra Azure ni contra Sigrid.** Mis lecturas fueron locales (git y ficheros). Según el informe, las del implementer fueron `SELECT` por el MCP.

## Checkpoints

**C1** [x] `init.sh` termina con exit 0 · [x] existen los ficheros del arnés.
**C2** [x] una sola feature `in_progress` (F-132) · [x] la rama es `feature/F-132-estado-desde-rac` · [x] `current.md` abre con la sesión activa · [x] el resumen en `history.md` es N/A: la feature aún no está `done`.
**C3** [x] hexagonal: `domain/estado_documentos.py` solo usa la librería estándar (lo comprueba un test de imports); `contraste_estados_sql.py` es solo texto, en infraestructura, e importa constantes del dominio; el comando está en `main.py` · [x] primera línea con la ruta en los 7 ficheros nuevos · [x] sin `print` (usa `click.echo`), sin TODO ni secretos · [x] semántica de Sigrid: estado de la cabecera por la pareja tipo-estado (F-084), `con.tiemod` fuera (D2 de F-067), `momento` en hora de Madrid sin zona y pasado a UTC solo en el contraste.
**C3 bis** N/A: no entra ningún documento de fuera (`docs/referencia/` no cambia).
**C4** [x] los 24 requisitos de la Fase A tienen test trazable y pasan (tabla abajo). R24 es MANUAL · [x] tests sin red ni BBDD: SQL y YAML se leen como texto y el comando usa un cliente falso · [x] las MANUAL están en `impl_F-132.md` §6 con su comando exacto, y `current.md` (l. 18) y T14 de `tasks.md` apuntan ahí, mismo criterio que se aceptó en F-085 · [x] dobles: `_PgContraste.filas_solo_lectura(sql_text, timeout_s, params=None)` tiene la firma del cliente real, y la puerta de dobles de `init.sh` está en verde.
**C4 bis** [x] `rigor` declarado · [x] **fase RED** con salida real de T1, T2, T3, T4, T6-T7 y T8-T10 (§3). Las únicas tareas sin RED son R23 y las constantes, y el informe lo explica · [x] cobertura 100 % · [x] mutación con `progress/mutacion_F-132.md`, 20 evaluados, 18 muertos, 2 supervivientes con análisis completo y cerrados con test · [x] muertos comprobados: no se reejecutó porque la campaña dura más de 60 s; recálculo puro hecho (arriba) · [x] la campaña tardó lo que tenía que tardar (5.596 s) · [x] sin cabecera «⚠ CAMPAÑA NO VÁLIDA» y «Sin veredicto (base rota)» = 0, con línea base de 506 y 511,6 s · [x] **RM1**: se midió sobre `82f0e0d` (SHA completo). Desde ahí solo cambian `tests/`, `progress/` y `tasks.md`; el alcance recalculado sobre HEAD da lo mismo · [x] **RM2**: media de 279,8 s frente a una línea base de unos 509 s, con 18 de 20 muertos con `-x`. Es la mitad, no un orden de magnitud, y 20 × 279,8 = 5.596 cuadra · [x] **RM3**: de los 20 sorteados ningún muerto es equivalente. El único dudoso, `Contrastado` con `frozen=True→False`, lo mata con razón el barrido `test_f006_dataclasses_inmutables.py` · N/A **RM5**: es solo para rigor `critico` y aquí no hay equivalentes declarados · [x] **RM6**: ningún mutante se mató quitando una guarda · N/A campaña manual: la automática dio 79 mutantes · [x] análisis de los supervivientes completos · [x] «Evidencias» con los cuatro números (§5) · [x] ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] `tasks.md`: T1-T13 y T15 en `[x]` con commit `F-132 Tn:` (T15 no tiene código). T14 MANUAL en `[ ]` como debe estar, igual que T16-T21 de la Fase B · [x] `git status` limpio y sin artefactos · [x] `features.json` en `in_progress`, que es lo correcto: la feature no se cierra hasta la Fase B.

## Cobertura · requisito → test

| Req. | Tests (`tests/test_f132_*`) |
|---|---|
| R1 | `sql::r1_no_lee_la_foto_ni_raw`, `sql::r1_una_fila_por_documento_de_las_tres_cabeceras` |
| R2 | `sql::r2_publica_sus_columnas_en_orden`, `diccionario::r18_vista_ficha_con_las_columnas_de_la_vista_en_orden` |
| R3 | `sql::r3_el_estado_es_el_de_la_cabecera` |
| R4 | `dominio::r4_*` (3), `sql::r4_el_momento_del_paso_o_su_dia_a_las_cero`, `sql::r4_r6_el_paso_solo_se_publica…` |
| R5, R8 | `dominio::r5_alta_cuenta_desde_el_dia_de_alta`, `dominio::r8_alta_sin_fecha…`, `sql::r4_r5_r8_en_estado_desde…` |
| R6, R7 | `dominio::r6_*` (4), `dominio::r7_cambio_posterior_a_solo_en_fuera_de_proceso`, `sql::r6_r7_la_cota_solo_fuera_de_proceso` |
| R9 | `dominio::r9_*` (2), `sql::r9_los_dias_se_cuentan_al_consultar_en_madrid` |
| R10 | `sql::r10_*` (6, incluida la huella de `11`), `test_f047/f073/f080/f085` (listas de sub-pasos) |
| R11 | `dominio::r11_*` (4), `sql::r11_*` (4), `sql::r4_r5_r6_el_origen_en_el_orden_del_dominio` |
| R12 | `contraste::r12_*` (4) |
| R13 | `dominio::r13_*` (12, con casos reales del 07-10 al 08-10), `contraste::r13_los_pasos_se_comparan_en_utc` |
| R14 | `dominio::r14_*` (4), `contraste::r14_los_no_vistos…` |
| R15 | `contraste::r15_*` (5: tabla, código 1, tope de 50, justo 50, orden) |
| R16 | `contraste::r16_*` (3) |
| R17 | `contraste::r17_*` (7: solo `SELECT`, una sentencia, sesión `READ ONLY`, `params`, `timeout` por defecto) |
| R18 | `diccionario::r18_*` (12) |
| R19 | `diccionario::r19_conest_ya_no_dice_que_nadie_guarde_el_cuando` |
| R20 | `diccionario::r20_*` (4), `test_f006_reglas` (22/2/2) |
| R21 | `diccionario::r21_*` (3) |
| R22 | `diccionario::r22_ningun_texto_vigente_afirma…` |
| R23 | `diccionario::r23_azure_apps_recoge_f132…` (y comprobado a mano el commit `89f63d5`) |
| R24 | MANUAL (humano), T14 / `impl_F-132.md` §6 paso 6 |
| R25-R28 | Fase B: fuera de esta revisión |

## Revisión del código (sin defectos bloqueantes)

- **SQL `13`.** Las columnas de las cabeceras existen (`01` l. 96-115 y 270-289, `08` l. 185-198), igual que las de `documento_procesos` (`12` l. 52-119). Las comparaciones de estado son homogéneas: `con.est` frente a `rac.est2`, los dos en bruto. Los literales coinciden con el dominio y la regla `PASO`/`ALTA`/`FUERA_DE_PROCESO` es la misma que en `fecha_estado`. En el primer despliegue la vista vieja (que lee la foto) no la arrastra el `CASCADE` de `12`, y por eso hace falta el `DROP VIEW IF EXISTS` de `13`: correcto, porque `CREATE OR REPLACE` fallaría al cambiar de columnas.
- **SQL del contraste.** El `JOIN` de `SQL_CAMBIOS` (`n.desde = v.hasta` + `CAMBIO`) y la ventana de `SQL_NO_VISTOS` (`LAG`, `momento AT TIME ZONE` frente a `TIMESTAMPTZ`, `NOT EXISTS` sobre los cambios de esa noche) se corresponden con R12 y R14.
- **Dominio.** `clasificar_cambio` respeta el orden de prioridad de R13. Que salga DISCREPANCIA cuando no hay pasos previos y el estado no es inicial es la lectura literal de R13 («FUERA_DE_PROCESO si el último paso ≤ fin lleva a otro estado»).

## Cambios requeridos

Ninguno.

## Observaciones (no bloquean; para quien toque estos ficheros)

1. `etl_sigrid/infrastructure/postgres/sql/compras/00_setup.sql` l. 167-169, cabecera de `fn_sigrid_tiempo`: dice «La antigüedad del estado sale de la foto diaria (`11_historial_estados.sql`)». Desde F-132 eso es falso, aunque no repite la premisa que vigila R22, y la spec no lista este fichero. Su ficha (R18) ya lo dice bien. Cambiarlo es una línea de comentario; conviene hacerlo en la Fase B o antes, si a `00_setup` no lo fija ninguna huella.
2. `01_documentos.sql` l. 71-72 («la da la foto diaria»): el implementer ya lo dejó anotado. Está fijado por la huella de `test_f073_sql` r23 y la spec dice que no se toca.
3. `main.py` l. 4949-4951: tres líneas en blanco antes de `@cli.command("contraste-estados")` (PEP 8 pide dos). Ruff no lo marca con la configuración actual; es cosmético.

## Automejora (propuesta, no aplicada)

- **A `.claude/agents/spec-author.md` (o a `specs/SPECS.md`)**: cuando una feature RELEVA una fuente (aquí, la foto por `rac`), el test anti-premisa (R22) debería buscar también la frase «sale de <fuente vieja>», no solo la premisa. Las observaciones 1 y 2 son textos vigentes que siguen señalando la fuente vieja y no los caza ningún test.
