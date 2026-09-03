<!-- progress/review_F-025.md -->
Revisión completa (pasada 1) · `905d13d..b4be5ee`, 30 commits.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto: **CHANGES_REQUESTED**

No es un rechazo del diseño: lo entregado es sólido y el requisito que manda
—«que no se reconstruyan, pero que no se borren»— está cumplido, verificado
camino a camino y no leyendo el informe. Lo bloquean **tres cosas concretas y
baratas** (§Cambios requeridos) más la **fase 7 entera**, del humano, sobre la
que no dictamino. **Rigor `critico`**: RED, cobertura ≥ 80 %, **cero
supervivientes** y las MANUAL con comando y resultado.

## ¿Puede algo de esto borrar una obra congelada? NO

Barrido propio de `TRUNCATE`/`DELETE`/`DROP` sobre `etl_sigrid/` y `main.py`:

- **El único `DELETE` sobre `stg`** lo compone `componer_borrado_derivado`
  (`build_stg_step.py:211-241`), y sus dos llamantes lo construyen **con la
  misma variable `obras`** que sustituye el marcador: no pueden divergir.
- **`TRUNCATE` desapareció de las dos tablas acotadas**: en `sql/stg/` solo
  queda en `03`, `04`, `05` y `07`, enteros (R7), y `truncate_table()` solo lo
  llama `ingest_raw_step.py:272`, sobre `raw`.
- **El aborto ya no vacía** (`_abortar_plan_mensual`, l. 986): registra qué obras
  quedaron sin rehacer y propaga. Invariante de F-019 invertida a propósito, con
  los tests reescritos y su porqué en cada docstring.
- **Escrituras nuevas: solo `_meta.obra_build`**, por upsert.

## Los cuatro hallazgos, juzgados

1. **`execute_sql_text` devolvía las filas BORRADAS** (`4667c6f`). Bien resuelto
   con `while cur.nextset()`. **No afecta a nadie más**: solo lo usan los dos
   sitios de F-025.
2. **La limpieza de sobrantes solo denuncia** (`8e9b1f2`): **cierto**,
   `_denunciar_obras_sobrantes` (l. 736) hace un `SELECT DISTINCT` y un
   `logger.warning`. Y el argumento es el correcto: el universo sale de
   `raw.obr JOIN raw.con`, y borrar por lo que ese `JOIN` no vea contradice R10.
3. **Código inalcanzable borrado** (`223cd1d`): correcto, la actividad es
   siempre día 1 y recortar días inventaba precisión. **El criterio sigue siendo
   el del humano**: tres reglas en unión, patrón anclado por los dos extremos,
   estados `[1, 11, 25]`, y el borde de doce meses cae del lado seguro.
4. **Los cinco supervivientes**: los tests **prueban algo real**; miran la
   propiedad (`marcador`, `de_tipo`, `codigo`) y no `MARCADOR_KO in output`, que
   era el agujero. **Verificado por mí (RM4)**: en un worktree aislado apliqué
   las cinco mutaciones equivalentes sobre HEAD, una a una, y **las cinco mueren**
   con `tests/test_f025_ventana.py`. **RM6 no aplica**: no se quitó guarda.

## Verificación independiente de la campaña

Recalculado con `harness.alcance` y `generar_mutantes` sobre el fichero **tal
como estaba en `8e9b1f2`**: **760 líneas, 83 mutantes**, lo mismo que el
informe, y los cinco supervivientes **existen como mutantes reales**, mismo
operador y mismo texto original→mutado: no está inventado. **RM2 coherente**
(83 × 42,9 s = 3.560 s; media × 4 workers = 171,6 s frente a una base de
209-214 s, por debajo por el `-x`). **Campaña NO reejecutada: 59,3 min según el
informe**, por encima del umbral de 60 s. **RM1 FALLA**: mide `8e9b1f2` y HEAD
es `b4be5ee`; en medio `3991076` modificó `domain/ventana.py`, **el único
fichero del alcance**, hoy de **779 líneas**.

## El arreglo de F-052

`Veredicto.no_ha_mirado_nada` mete `filas_miradas == 0` en `codigo` y en
`marcador`. **No rompe F-052**: el test que pasaba en falso recibe una
combinación sana, el de cero tiene el suyo y el de `run-all` sigue verde.

## Lo que NO reproduce: la contrapartida del censo

Medido por mí en solo lectura sobre `raw.obr JOIN raw.con` (920) y `stg.fases`,
con **el criterio tal y como lo implementa el código**:

| | Código (hoy) | Spec (R3, `decisiones`, `mediciones`) | Diccionario |
|---|---|---|---|
| Congeladas / vivas | **880 / 40** | 880 / 40 | — |
| Regla 2 (seis dígitos) | **226** | 222 | — |
| Sin actividad 12 m | **872** | 840 | — |
| Congeladas **con** actividad | **8** | **40** (39 CERRADAS + 1) | **7** |

**El titular cuadra al dedillo: 880 y 40.** Lo que no cuadra es la
contrapartida, el número con el que el humano aceptó la decisión.
`obras_congeladas_F025.csv` da a 36 obras una `ultima_actividad` de `2025-12`
que **`stg.fases` no confirma** (la 0620 la tiene en **2024-01**, y `raw.obrfas`
igual). El código usa la definición de `mediciones.md` §2: **va bien él y el CSV
no reproduce**. Va a favor, pero hay tres cifras publicadas y una la sirve el MCP.

## Checkpoints

- **C1** `[x]` — `init.sh` **exit 0**: 3.305 pasados, 134 saltados en 412,9 s;
  `PUERTA COBERTURA [OK] 91,7 % (578/630, umbral 80 %, critico)`; `PUERTA
  TAMAÑO [OK]`. Avisos previos: 207 de ruff y F-052 blocked.
- **C2** `[x]` — una `in_progress`, rama correcta, `current.md` al día.
- **C3** `[x]` — `domain/ventana.py` importa solo stdlib; `ventana_sql.py` no
  abre conexión; ruta en la primera línea de los 14 ficheros nuevos; sin `print`
  ni secretos. En `06_presupuesto.sql` el diff son dos líneas y el `DISTINCT ON`
  sigue particionando por obra.
- **C3 bis** y **C4 ter** `N/A` **justificados**: no toca `docs/referencia/` ni
  existe `harness/rutas_sensibles.json`.
- **C4** `[ ]` — trazabilidad buena (22 requisitos con `test_f025_rN_*`: R10 16,
  R14 20, R16 38, R17 19, R26 13, R27 23) y ningún test toca red ni BBDD. **Falla
  el tercer punto**: las MANUAL están en prosa, **sin comando exacto**.
- **C4 bis** `[ ]` — RED `[x]` (trazas de T3 y T10); cobertura `[x]`;
  **mutación `[ ]` y RM1 `[ ]`**; RM2, RM3 y RM4 `[x]` (el último, mío); RM5 y
  RM6 `N/A` **justificados** (ni equivalentes declarados ni código defensivo
  retirado); Evidencias `[x]`, con sus cuatro números y sus 4 workers.
- **C5** `[ ]` — `tasks.md` con T1, T2b y T27-T35 sin marcar: la fase manual.

## Cambios requeridos

1. **Reejecutar la campaña sobre HEAD y completar el informe.**
   `mutacion_F-025.md` mide `8e9b1f2` (760 líneas) y HEAD es `b4be5ee` (779),
   con el único fichero del alcance modificado en medio; y **los cinco
   supervivientes siguen con su análisis en `PENDIENTE`**, checkbox de C4 bis.
   En `critico` hacen falta **cero supervivientes**.
2. **Reconciliar la contrapartida del censo** en R3, `decisiones.md` DA-1,
   `mediciones.md` §2 y `config/diccionario/maestro.yaml` (7 vs 39 vs 8).
   Re-medir con la definición del código y **volver a enseñárselo al humano**:
   decidió con la cifra vieja. Y la regla 2 son **226**, no 222: «ninguna llega
   al fact» hay que recomprobarlo sobre esas 226.
3. **Listar las MANUAL con su comando exacto** en `progress/current.md` (C4).

## Observaciones (no bloquean; decidir antes de encender)

- **R5 al pie de la letra**: apagada la ventana, el `DELETE` derivado no alcanza
  a una obra con filas que no esté en el censo; el `TRUNCATE` sí. T30 lo detecta.
- **`registrada` se vuelve verdadera para todas** (la firma inserta fila por
  obra tras la ingesta): la segunda mitad de R18 deja de alcanzarse. La cubren
  `tiene_filas` y el sello nulo, pero ya no vigila nada.
- **Automejora propuesta**: C4 bis no dice qué hacer cuando el implementer
  arregla un superviviente —el arreglo toca el alcance y RM1 invalida la campaña
  siempre—. Añadir a RM1 que *el informe de mutación es el ÚLTIMO commit de la
  feature*. Va a `arnes-base`.

## Pendiente de la fase manual (no dictamino sobre ello)

| | Qué | Qué decide |
|---|---|---|
| **T1 / T2b** | Peso real por obra; coste de la firma sobre `raw.obrparpre` | Si merece la pena (bajo el 40 %, PARAR) y la forma de la firma (R20) |
| **T27-T31b** | Las cinco huellas del antes, la reconstrucción acotada, las del después **sin `--obras-esperadas`**, la 0599 (DIRECTOS 2.624.793 €) y `v_frescura_obra` | R11-R12, R21-R23. **Bloqueante**: una sola diferencia para la feature |
| **T32-T35** | Los `check-*`, el bloat contra T2, los créditos de CPU y desplegar `infra/97_create_alert_ventana.ps1` | R24, R29; **sin el `.ps1` el guardián es mudo** (DA-5) |
| — | Encender `PG_VENTANA_ACTIVA` | Del humano. Hasta entonces esto solo repara el `TRUNCATE` |
