<!-- progress/review_F-080.md -->
# F-080 · Revisión

**Revisión completa (pasada 1)** — `b6cfd6e..f9ac2b4`, 30 commits, 29 ficheros,
~4.578 inserciones. Árbol limpio en `f9ac2b4` al abrir y al cerrar.

## Veredicto: **APROBADO**

**Rigor `estandar`, DECLARADO** en `harness/features.json` (no por omisión):
exige trazabilidad (C4) + **fase RED** en los requisitos centrales +
**cobertura** ≥ 80 % + **mutación** con los supervivientes analizados. Las tres,
cumplidas y verificadas por mí aparte.

**`bash harness/init.sh` → exit 0**: `4677 passed, 179 skipped, 0 failed` en
654,7 s · `[OK] PUERTA COBERTURA 93.9 %` (825/879, umbral 80) · `[OK] PUERTA
TAMAÑO`. Los dos `[AVISO]` son deuda previa (F-052 `blocked`, ruff). **Las
cuatro cifras de «Evidencias» coinciden al dígito con lo que medí.**

## Lo que NO me creí y comprobé por mi cuenta

1. **Fase RED, reproducida dos veces** en `git worktree` desechables fuera del
   árbol: en `09ee04f` (T9) `05_vencimientos.sql` **no existe** y
   `pytest tests/test_f080_sql.py` da **55 failed**; en `37862ba` (T20),
   **26 failed, 3 passed**. Los dos recuentos, exactos. No es narrada.
2. **RM1**, el fallo que costó F-034: tras los dos SHA medidos solo cambian
   `progress/`, `tasks.md` y `tests/test_f080_texto.py` (+37). **Ningún fichero
   de producción cambió tras medir**: el alcance medido es el que reviso.
3. **Las campañas, recalculadas** con `harness.alcance` y `generar_mutantes`:
   3.789 líneas / **303 mutantes** y 317 / **27**, fichero a fichero; la prueba
   de control sale igual (0 sobre las 42 líneas de `build_compras_step.py`, 12
   sobre el fichero entero). Los **7** supervivientes existen como mutantes
   reales con su operador y su texto original→mutado, y el **muestreo
   determinista** (semilla `20260820`) reproduce los 6 dentro de la muestra de
   20. **No reejecutadas** (2.920 s y 3.241 s, muy por encima del umbral de
   60 s). **RM2** cuadra: descontada la línea base y repartido entre 4 workers
   salen ~490 s/mutante (1,05 × base) y ~403 s (0,97 × base), acorde con `-x`.
4. **El superviviente tapado, verificado en copia aislada**: con el mutante
   `or`→`and`, `tests/test_f080_texto.py` pasa de `29 passed` a `4 failed,
   25 passed`. Y **los 27 mutantes de los dos módulos mueren**: confirma el
   27/27/27/0 sin gastar los 54 min. **RM6**: en `git diff -- etl_sigrid/` solo
   se borran **3 líneas, las tres comentarios**; ninguna guarda `is None`.
5. **Lo intocable, en el diff y no en el informe**: `stg/06`, `stg/08` (SELLO) y
   `compras/01`, `02`, `03` (R21) —y `04`— **INTACTOS**.
6. **Sin regresión a la versión falsa**: ni `lpad` ni `CASE` sobre `fecrea`. Los
   dos aciertos son legítimos: `fecrea` se publica como fecha y el
   `row_number()` de `07_texto.sql:92` **renumera tras filtrar**, porque `WITH
   ORDINALITY` numera antes del `WHERE`. El estado se **lee** de `raw.conest`.

## Checkpoints

- **C1** `[x]` init.sh exit 0; documentos del arnés presentes.
- **C2** `[x]` una sola `in_progress` (F-080), la rama es la suya, árbol limpio.
- **C3** `[x]` dominio **puro** (`texto_comentarios.py` solo importa `datetime`,
  `re`, `dataclasses`); primera línea con ruta en los 6 ficheros nuevos y los 3
  SQL; sin `print()` de debug, sin TODOs, **sin secretos**. Las tres funciones
  que usa el SQL nuevo existen en `00_setup.sql`.
- **C3 bis** `N/A` **justificado**: no entra ningún documento externo (PDF ni
  ofimática); el diff no toca `docs/referencia/`.
- **C4** `[x]` ver tabla abajo. Los tests no tocan red ni BBDD.
- **C4 bis** `[x]` rigor declarado, RED con traza real, cobertura `[OK]`,
  mutación con **todos** los supervivientes analizados (ninguno en PENDIENTE),
  «Evidencias» con sus cuatro números, RM1–RM6 verificados arriba. **RM5 no
  aplica** (solo `critico`); el único equivalente —el `120` de
  `_veredicto_de_ventana`, un timeout en segundos— lo confirmé contra la firma
  de `main.py:1516`.
- **C4 ter** `N/A` **justificado por configuración**: no existe
  `harness/rutas_sensibles.json` (solo el `.ejemplo.json`), el caso mayoritario
  que `CHECKPOINTS.md` declara sin nada que justificar.
- **C5** `[x]` 30 tareas `[x]` y **cada T0–T29 con su commit** `F-080 Tn:`. La
  única sin marcar es **T0 bis**, MANUAL del humano y abierta a propósito.

## Cobertura requisito → test

**37 requisitos vigentes** (R13, R14 y R27 retirados; R37 fundido en R33): **30
con cobertura automática real**, 3 parciales y 4 sin test por ser MANUAL. Ni un
test de nombre bonito y assert vacío: R19 exige que **todo** `SUM(` lleve su
`FILTER (WHERE NOT efecto_anulado)` y R7 distingue `JOIN` de `LEFT JOIN`.

| Bloque | Requisitos | Dónde |
|---|---|---|
| Ingesta (`con.tex` + 3 tablas) | R1–R3, R6 | `test_f080_ingesta.py` |
| Vencimientos, forma de pago y control | R7–R12, R15–R19, R21, R28–R30, R38–R41 | `test_f080_sql.py` |
| Texto y comentarios | R22–R26 | `test_f080_sql.py`, `_texto.py` |
| Cableado del step | R20 | `test_f080_pipeline.py` |
| Fichas y versión 21 | R31, R32, R35 | `test_f080_diccionario.py` |
| **MANUAL, sin test** | R4, R5, R33, R34, R36 | `progress/current.md` |

**Las MANUAL están anotadas con su comando exacto y su valor esperado**, en
orden y con la dependencia explícita: T0 bis, T7, T26 (9) y T27 (3 al MCP).

## Los puntos con lupa, resueltos

- **Spec intacta**: `requirements.md` con multiset de palabras **idéntico**
  (1.586 = 1.586) y `design.md` con dos `>` menos: reflujo para entrar en el
  tope. `tasks.md`, casillas más **dos notas de ejecución** (T24, T25).
- **Los cuatro tests de otras features no relajan nada**: F-047/F-073 amplían la
  lista COMPLETA de sub-pasos de 5 a 8 y F-066/F-074 suben `TOTAL_TABLAS` de 65
  a 68, con asserts de **igualdad**. `ARCHITECTURE` y el `design_detalle.md` de
  F-006 **los exige un test** (`test_f074_ingesta_censo.py:570`,
  `test_f006_publicacion.py:1033`): no es contaminación.
- **Grano y unicidad**: PK `(vencimiento_id)` y la compuesta `(documento_id,
  orden)` declaradas; los `LEFT JOIN` van contra `ide` y el único por par,
  `conest (tip, est)`, es **único medido** (193/193), así que duplicar **haría
  fallar el build**. `v_facturas_pago` **agrega en un CTE antes de unirse**.
- **La trampa, con cifra**: `efecto_anulado` sale de `(c.fecbaj <> 0)` y ficha,
  `COMMENT` y `00_global.yaml` dicen **89.228 de 255.148 (34,97 %)** y 76.215 de
  195.510 (39 %) en factura. **Diccionario v21**, con ficha para los cinco
  objetos de `compras` (89 columnas) y las tres tablas de `raw`.

## Correcciones **no bloqueantes** (documentación; ningún número cambia)

1. `progress/mutacion_F-080.md:64-65` y `mutacion_F-080_modulos.md:47-48` dicen
   que el muestreo «no cogió **ninguno**» de los 15 mutantes de
   `texto_comentarios.py`. **Es falso: cogió uno** —línea 114, [booleano],
   `sello_reconocido=False`→`True`— y **murió** (por eso falta en la lista de
   supervivientes, de donde sale el desliz; la esperanza que el propio informe
   calcula, 0,99, era justamente 1). No cambia ningún total —14 de 15 siguen sin
   juzgar y la dirigida seguía haciendo falta— y va **en contra** del informe.
2. `progress/impl_F-080.md` §Fase RED dice que la traza íntegra está «en
   aquellos commits»: cierto en 5 de 7, pero `55a4713` (T5) y `09ee04f` (T9)
   solo declaran el recuento en prosa (la traza sí está en el informe, que es lo
   que la puerta exige). Ajustar la frase.
3. `progress/impl_F-080.md` §T29 llama a los 224 avisos de ruff «anteriores a
   esta feature». **Eran 216** (medido en worktree sobre `b6cfd6e`): F-080 añade
   8 `N802` por nombres de test con mayúsculas. Hay precedente (37 en el repo) y
   ruff no bloquea, pero la frase no es exacta.

## Propuesta (no aplicada) — merece ficha propia

**Cinco de los seis supervivientes de la canónica son de F-025**
(`postgres_client.py:1527/1528/1551/1643`, `ventana_sql.py:244`) y **dos
campañas seguidas los señalan**: F-073 ya marcó los mismos. Son huecos reales,
inalcanzables offline porque esos métodos necesitan cursor. Como con F-077 y
F-081, **propongo abrir ficha** para cubrirlos o declarar que solo los cubre la
MANUAL. F-080 hizo bien en no tocarlos: no son suyos. Dos apuntes para esa
ficha: **R36 no tiene guardián automático** y R21, del mismo tipo, sí lo tiene;
y las listas de columnas de `test_f080_diccionario.py` y `test_f080_sql.py`
están **cableadas a mano, no derivadas del SQL**, así que una columna añadida al
SQL y olvidada en la ficha pasaría los dos tests (la biyección real la impone
`check-diccionario`, MANUAL).
