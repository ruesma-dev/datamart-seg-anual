<!-- progress/review_F-067.md -->
Revisión incremental desde 1a6e40f (pasada 2): el delta es `e45fbad`, `b575935`, `6f08f97` y `9eeb9b5`. La pasada 1 revisó entero `main...b393c8b` y está íntegra en `git show 1a6e40f:progress/review_F-067.md`

# F-067 · Review · foto diaria de estados, condiciones del contrato y código 2

**Veredicto: APPROVED** (pasada 2). Los dos cambios de la pasada 1 están hechos.
`reset-compras` ya no puede borrar la historia: lo he comprobado **ejecutando su
SQL real** contra un Postgres 16 desechable, no solo leyendo el texto.

**Rigor:** `critico`, declarado: RED, cobertura, mutación, RM5, MANUAL.

## Pasada 2 · delta `1a6e40f..9eeb9b5`

- **Cambio 1, hecho.** Las MANUAL T16-T23 están en `current.md` en orden, cada
  una con su comando y lo que debe salir, copiadas de `impl` §6. El punto previo
  sobre `reset-compras` ya no hace falta: está decidido y hecho.
- **Cambio 2, hecho.** El comentario de `11:86-90` dice ahora que la excepción
  revierte SOLO ese fichero y que `00`-`10` ya están confirmados. Es lo que pasa
  en realidad, y no cambia nada ejecutable.
- **`reset-compras` (decisión del 2026-10-06, opción a).** El comando ejecuta
  `SQL_RESET_COMPRAS`, un `DO` que borra por catálogo, con `CASCADE`: primero
  vistas y materializadas, luego tablas `r`/`p` **menos** `TABLAS_PERSISTENTES`,
  y al final las funciones. No contiene `DROP SCHEMA`, `DROP INDEX`, `TRUNCATE`
  ni `DELETE`. Un `CASCADE` no puede arrastrar las dos tablas por ninguna vía:
  ellas no dependen de nada de `compras`, ni por FK ni por función en
  `CHECK`/`DEFAULT`. Un `CASCADE` sobre otra tabla o función solo se llevaría
  dependientes, y una tabla solo puede perder una FK o un `DEFAULT`, nunca
  desaparecer entera. Barrido del repo: los únicos `DROP SCHEMA` que quedan son
  `cierre` y `retenciones` (`main.py:4011` y `5205`). El `DROP DATABASE` de
  `scripts/extraer_planif_cuatrimestral.py` es de otra base (`sigrid_planif`),
  ya existía y no se toca. El parche histórico ya no borra nada: lanza
  `ClickException`.
- **Ejecutado de verdad** (Postgres 16.4 local en mi scratchpad, puerto propio,
  borrado al terminar; nada contra Azure). Corrí el **SQL REAL** de
  `11_historial_estados.sql` y de `SQL_RESET_COMPRAS` sobre un `raw.con` de
  prueba:
  - Noche 1: 100 tramos de línea base, y los comparativos (46) quedan fuera.
    Relanzada: no escribe nada.
  - Noche 2: 3 firmas más un estado a NULL dan 4 CAMBIO. Hay 2 DESAPARECIDO (el
    borrado y el del tipo viejo) y 3 altas (2 nuevas más el cambio de tipo). El
    tramo nuevo lleva `observado_antes` igual a la noche 1, y
    `es_linea_base` falso.
  - Noche 3, con 91 de 101: `RAISE EXCEPTION` y nada escrito. Noche 4, con 99
    de 101 (98,0 %): pasa.
  - **Reset**, con una FK `contrato_lineas → contratos`, una vista que une la
    foto con `contratos`, una materializada, una función y una vista de OTRO
    esquema que lee la foto: antes 107 tramos y 3 fotos, **después 107 y 3**.
    Siguen la PK, el `CHECK`, el índice único parcial y la vista del otro
    esquema. En `compras` no queda nada más.
  - Build tras el reset: no escribe (misma ingesta) y recrea
    `v_estado_documentos` (99 filas). El doble reset es idempotente.
- **Tests** (`test_f067_reset.py`, 8): fijan el texto del SQL, que no haya
  `DROP SCHEMA` ni `DROP INDEX`, el orden, que el comando ejecute exactamente
  ese SQL con un commit, y el veto a `DROP SCHEMA compras` en todo
  `*.py/sql/ps1/sh`. Es un doble mínimo de conexión y cursor: solo
  `connection`, `cursor`, `execute` y `commit`, que existen en el real.
- **Cobertura 97,4 % (74/76).** Las 2 líneas sin cubrir son el cuerpo nuevo de
  `reset_compras` en `patches/main_py_patch_compras.py`, un parche histórico que
  nada importa ni ejecuta: no es código vivo. El código vivo (módulo del reset,
  `main.reset_compras`, el dominio y el step) está al 100 %, y el total pasa el
  umbral. Lo acepto.
- **Mutación** (RM1): el alcance ha crecido a 329 líneas en 5 ficheros (el
  dominio, el step, `compras_reset_sql.py`, `main.py` y el parche).
  `generar_mutantes` sobre HEAD da 45 (todos del dominio) y 0 en las otras
  cuatro. Lo he recalculado: es cálculo puro. He reejecutado
  `mutacion_dominio_F-067.py` en una copia de HEAD: **45/45 muertos**, base 276
  passed. La campaña MANUAL del reset (R1-R6, 6/6) la he reproducido en una
  copia: **R1** (sin `NOT IN`), **R4** (sin `CASCADE`) y **R6** (una sola
  conservada) dan **+1 fallo cada uno sobre la base**. En la copia, la base ya
  traía 1 fallo, el test del comando: es del entorno, porque el worktree no
  tiene `.env`; en el árbol real pasan los 8. La tabla del informe no trae la
  línea de cada mutante, y es lo único que le falta; con el texto exacto se
  reproduce igual. El informe tampoco nombra el parche (8 líneas, 0 mutantes).
- **RED** de `reset`: `2 failed, 6 passed` según `impl` (el comando y el veto).
  Concuerda con lo que el veto cazaba antes, en `main.py` y en el parche.
- Los documentos `README_COMPRAS_C1_C2.md`, `LEEME_INTEGRACION.md`,
  `ARCHITECTURE.md`, las dos fichas y `azure-apps` (`e5ad1cb`) dicen ya que
  `reset-compras` conserva la foto.

## Checkpoints (pasada 2)

**C1** [x] `bash harness/init.sh` sobre `9eeb9b5`: **ENTORNO LISTO**, 6.984 passed (45 min) · [x]
ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-067-…` · [x]
`current.md` es el estado real · [x] `history.md`: no aplica todavía.
**C3** [x] hexagonal: el SQL vive en `infrastructure/postgres/`, que solo
construye texto, y el dominio solo da el literal · [x] primera línea con la
ruta · [x] sin `print`, secretos ni dependencias nuevas · [x] Sigrid: sin
cambios desde la pasada 1.
**C3 bis** N/A: no toca `docs/referencia/`. **C4 ter** N/A: no hay
`rutas_sensibles.json`.
**C4** [x] R1-R29 más el `reset` con tests en verde · [x] sin red ni BBDD · [x]
**MANUAL en `current.md` con su comando y lo que debe salir** · [x] el doble
nuevo solo imita métodos que existen en el real.
**C4 bis** [x] rigor declarado · [x] RED · [x] cobertura `[OK]` 97,4 % · [x]
alcance y mutantes recalculados · [x] la campaña del arnés no se ha
reejecutado (15.340 s, > 60 s); en su lugar, recálculo más RM4 sobre HEAD · [x]
coste por mutante coherente (pasada 1) · [x] sin «NO VÁLIDA» · [x] RM1 · [x]
RM2 · [x] RM5 (el equivalente `>= 0`, demostrado en la pasada 1, ya no existe)
· [x] RM6: nada defensivo se ha quitado en el delta · [x] tablas MANUAL con su
texto exacto, reproducidas (SQL 40/40 en la pasada 1; reset R1, R4 y R6 ahora)
· [x] 0 supervivientes · [x] «Evidencias» · [x] ningún N/A sin motivo.
**C5** [x] T1-T15 `[x]` con sus commits; el delta lleva `F-067:` (correcciones
de la review) · [x] árbol limpio (worktree y Postgres local borrados) · [x]
`features.json` refleja el estado real, y el delta no lo toca.

## Pasada 1 · resumen (íntegra en `1a6e40f`)

Verificado entonces, y el delta no lo toca: la foto (sin `DROP`/`TRUNCATE`/
`DELETE`, idempotente, cierre por `ide`+`tip` con `IS DISTINCT FROM`, índice
único parcial) igual que el oráculo; la guarda del 98 % sin debilitar (el SQL
se fija por su texto exacto; lo quitado del dominio era redundante, comprobado
por fuerza bruta); la época de Delphi; D2 (la antigüedad sale de la foto, nunca
de `tiemod`); las columnas al final y el sello de `descompuestos` intacto; las
cifras de T19 reproducidas en Azure en SOLO LECTURA (185.754 documentos,
6.333/19.072 contratos, 1.162.871/357.349/378.010 líneas, 277 DPC); la campaña
SQL 40/40 reproducida fila a fila; la RED de T4 reproducida.

## Cobertura requisito → test (`tests/test_f067_*.py`)

R1 (5) · R2 (8) · R3 · R4 (4) · R5 (7) · R6 (7) · R7 (4) · R8 (9, más 8 de
`reset`) · R9 (5) · R10 (4) · R11 (2) · R12 (3) · R13 (3) · R14 (9) · R15-R16 ·
R17-R18 (5) · R19 (5) · R20-R21 (3) · R22-R25 (7) · R26-R27 (4) · R28 (2) más
T18 · R29 por lectura · R30 MANUAL T21.

## Cambios requeridos

Ninguno. Quedan las MANUAL T16-T23 del humano (`current.md`).

## Para el líder y el humano (no bloquea)

- **R5 (de la spec)**: un documento ausente una noche, en una ingesta a medias
  que no llega a saltar la guarda (≤ 2 %), pierde `antiguedad_es_minima` al
  reaparecer. Con `--full` es improbable, pero no tiene vuelta atrás.
- T23 (`NOT h.es_linea_base`) cuenta también las altas. `reset-compras` borra las funciones con `CASCADE`. Si algún día una tabla
  persistente usa una función de `compras` en un `CHECK` o un `DEFAULT`, el
  reset le quitaría esa restricción en silencio. Hoy no pasa (verificado).
- **Automejora (propuesta)**: en `reviewer.md`, «tabla PERSISTENTE en un esquema
  que se reconstruye → buscar en todo el repo `DROP SCHEMA <esquema>` o un
  reset», y si hay un Postgres local, ejecutar el SQL destructivo de verdad.
