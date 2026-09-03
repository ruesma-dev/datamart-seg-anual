<!-- progress/review_F-025.md -->
Revisión incremental desde `b4be5ee` (pasada 2). La pasada 1 fue completa
(`905d13d..b4be5ee`); su informe entero vive en el commit `a34ed9b`.

# F-025 · Review · Las obras cerradas no se reconstruyen cada noche

## Veredicto: **CHANGES_REQUESTED**

**No es un rechazo del trabajo.** De los tres cambios que pedí: **campaña sobre
HEAD `[x]`** (RM1 cumplida), **MANUAL con su comando `[x]`**, y **censo remedido
pero mal propagado**. Lo que impide aprobar es: **la fase 7 entera sigue sin
ejecutar** (C5, y sobre ella no dictamino), **un hallazgo nuevo sobre el alcance
de la campaña de mutación** que se me pasó en la pasada 1, y **cuatro cifras
viejas del censo que sobrevivieron al remedido**. **Rigor `critico`**: RED,
cobertura ≥ 80 %, cero supervivientes y las MANUAL con comando y resultado.

**El delta no toca ni una línea de código:** `git diff --name-only b4be5ee..HEAD`
no devuelve ningún `.py` ni `.sql`, y en `business_rules.yaml` es **solo
comentarios**. Todo lo verificado en la pasada 1 —borrado derivado, `TRUNCATE`
retirado, hexagonal, convenciones, trazabilidad— sigue en pie sin re-mirarlo.

**El censo, comprobado:** 920 · 880 · 40 · 38 al fact · 693/226/872 · 48 con
actividad · **8** congeladas pese a tenerla (7 CERRADAS + la `180501`) son **las
cifras que medí yo contra la base en la pasada 1** —no he reconsultado el
`B1ms`—; cuadran en R2/R3, DA-1/DA-3, `mediciones.md` §2 y §5, `design.md`,
`maestro.yaml` y `business_rules.yaml`, y cierran solas (40 + 8 = 48). Fallan
cuatro residuos (§Cambios 3).

## Hallazgo nuevo: la campaña mide el 38 % de la feature

Recalculado con `harness.alcance`, el **alcance automático de F-025 son 10
ficheros, 2.610 líneas y 219 mutantes**. La campaña lo declaró a mano —«Origen
del diff: **ficheros**»— y midió **uno solo**. Los 136 que nunca se generaron no
son periferia: **`build_stg_step.py` (34), donde vive `componer_borrado_derivado`,
o sea LO QUE SE BORRA**; `main.py` (37); `postgres_client.py` (31, con
`SQL_ESTADO_OBRAS`); `ventana_sql.py` (15); `cobertura.py` (6). Sale de **DA-6**,
que acota la campaña a `domain/ventana.py` y que `decisiones.md` declara **«sin
pronunciamiento del humano»**. En `critico` `rigor.json` dice `max_mutantes:
null` = *«aquí se mide la campaña entera»*, y solo se exime con **justificación
escrita aceptada por el humano**: aquí se la concedió la spec a sí misma. **Es mi
fallo de la pasada 1**, por no recalcular el alcance. Cerrarlo: ~**2 h 40**.

## Verificación independiente de la campaña

Mide `073af30aec64992dd1b4b0183a8c2c1373808ee9` y **`ventana.py` no ha cambiado
desde entonces** (diff vacío): **RM1 cumplida**. **Recálculo puro:** 779 líneas y
**83 mutantes**, idénticos al informe; 79 muertos, **0 supervivientes, 0 sin
veredicto, ningún `PENDIENTE`**, sin «⚠ CAMPAÑA NO VÁLIDA». **Campaña NO
reejecutada: 7.720 s (2 h 8) según el informe**, muy por encima del umbral de
60 s. **RM2 coherente**: `83 × 93,0 = 7.720` y `media × 4 workers = 372 s` contra
una base de 467-473 s, por debajo como manda el `-x`. **RM3** sin caso; **RM5 y
RM6 `N/A` justificados**: ni equivalentes declarados ni código defensivo retirado.

**Los 4 timeouts, cerrados por mí (RM4).** Ni muertos ni supervivientes: son
**mutantes sin veredicto**, y un timeout tira hacia superviviente (el que muere
aborta pronto con `-x`). Los reproduje **sobre una copia de HEAD en mi
scratchpad** (`git archive`, sin tocar el árbol) y **los cuatro MUEREN** con
`pytest -k f025 -x` en 5-9 s: `ventana.py:207` (`not all`→`all`, y `and`→`or`),
`216` (`is None`→`is not None`) y `242` (`tiene_filas False`→`True`), cazados por
`test_f025_r10_el_build_NO_llama_a_truncate...` y `..._r30_ventana_plan_...`. Era
contención de máquina: **83 de 83 con veredicto**; `git status` limpio.

## Checkpoints

- **C1** `[x]` — `bash harness/init.sh` **EN VERDE**: 3.305 pasados, 134 saltados
  en 361 s; `COBERTURA [OK] 91,7 % (578/630, umbral 80 %, critico)`; `TAMAÑO
  [OK]`. *(La primera salida fue KO por `test_f015_r4_ejecutar_git_de_verdad...`:
  **interferencia mía** —lo corrí a la vez que mis pruebas de mutación y ese test
  lanza `git` de verdad, sin timeout, devolviendo `""` ante rc≠0—. Solo, pasa.)*
- **C2** `[x]` — una `in_progress`, rama correcta, `current.md` al día. **C3**
  `[x]`; **C3 bis** y **C4 ter** `N/A` justificados: sin código en el delta, el
  veredicto de la pasada 1 se mantiene entero.
- **C4** `[x]` — las once MANUAL de `current.md` ya traen su comando **literal**,
  la precondición delante y el criterio de parada de T1; la trazabilidad
  requisito→test de la pasada 1 sigue válida (ningún test cambió).
- **C4 bis** `[ ]` — RED `[x]`, cobertura `[x]`, RM1-RM4 `[x]` (RM4, mío),
  RM5/RM6 `N/A` justificados. **Falla por dos**: el **alcance** de la campaña
  (38 % de los mutantes, sin exención del humano) y la sección **«Evidencias»**,
  que publica los números de la campaña **descartada**.
- **C5** `[ ]` — `tasks.md`: 28 de 41. T1, T2b y T27-T35 son la fase manual;
  **T36 («init.sh en verde») está sin marcar y sí está hecho**.
- **Fase RED tras el recorte de `6f77759`: suficiente para `critico`.** Solo cayó
  la decoración; **las trazas siguen enteras** —fichero, línea y la línea `E`
  real— para los dos requisitos centrales, T3 y T10.

## Cambios requeridos

1. **Decidir el alcance de la campaña, y que lo decida el humano.** O se extiende
   a los 219 mutantes (`python -m harness.mutacion --feature F-025`), o **DA-6 se
   exime por escrito**, como el propio DA-6 previó. Lo que no vale es que la spec
   se autoexima en `critico`. Si no se hace entera, **al menos
   `build_stg_step.py`** (34), que es donde vive el borrado.
2. **Rehacer la tabla «Evidencias» de `impl_F-025.md`**: dice «Supervivientes
   **5**», «**0 timeouts**» y «59,3 min, base 210-214 s», los números de la
   campaña que este review invalidó. Los buenos: **0 supervivientes, 4 timeouts
   (cerrados aquí), 7.720 s, base 467-473 s, 4 workers**.
3. **Las cuatro cifras viejas del censo, dichas como hechos:**
   `business_rules.yaml:187-188` («**222** de seis digitos… 0 de **222**», contra
   el 226 de su propia línea 140), `business_rules.yaml:197` («**840** obras»,
   contra 872) y el «**80** de 920 con actividad» de `requirements.md:14` y
   `docs/ARCHITECTURE.md:165`, que es 920−840 y contradice las 48 que ambos
   declaran más abajo. `business_rules.yaml` **es** la regla de negocio: quien la
   lea se lleva 222. **Y marcar T36** en `tasks.md`.

## El círculo del `PG_VENTANA_ACTIVA`: NO, y no por prudencia

Encenderla antes de verificar **no es un atajo arriesgado: es la única acción que
empeora el problema que dice resolver.** Primero, **congelaría la corrupción**:
«congelar» es *conservar la última versión buena*, y hoy la de `stg.plan_mensual`
no lo es —está al 21,6 %—; encendida la ventana, las 880 dejan de reconstruirse
**conservando ese agujero**, y la única vía de repararlo —la completa del domingo
(R25)— choca con la misma pared de créditos que causó la avería: de una tabla
rota que se intenta rehacer cada noche a una **que ya nadie rehace**. Segundo,
**destruiría la prueba y para siempre**: T27/T30 —cinco huellas antes, cinco
después, **tolerancia cero**— son la única evidencia de que la ventana no cambia
ni una cifra publicada, y el «antes» solo existe mientras se reconstruyan las
920; encendida, ese estado no vuelve y la comparación pasa a dar miles de
diferencias que explicar una a una: **el defecto de F-052 con otra ropa**, dar
por bueno un veredicto que no tuvo nada válido que medir.

**Y el círculo no es tal.** La precondición no es «una nocturna completa», es
**una `stg.plan_mensual` completa y coherente**, y eso se logra **con la ventana
apagada**: retirado el `TRUNCATE`, una nocturna que muera en el tramo 5 ya no
vacía la tabla. Falta completarla a propósito y de día —**`python main.py stage`
con los 144 créditos llenos**, en una o varias sesiones, o subiendo el `B1ms` un
escalón una noche—, y luego `check-coherencia` y `status-stg` en verde.
**Propongo el orden de `current.md` con un paso 0 delante:** (0) completar
`plan_mensual` con la ventana apagada; (1) T27, las huellas del antes sobre ese
estado ya coherente; (2) T1 y T2b, que necesitan la misma base sana —si T1 baja
del 40 %, PARAR—; (3) T35, que el guardián no puede estar mudo al girar el
interruptor; (4) **entonces** `PG_VENTANA_ACTIVA=true`, T29 y T30 con tolerancia
cero. Al guion no le falta el orden: le falta **decir cómo** cumplir su propia
precondición, que hoy enuncia y deja en el aire.

## Pendiente de la fase manual (no dictamino sobre ello)

| Qué | Qué decide |
|---|---|
| **T1 / T2b** · peso por obra y coste de la firma | Si merece la pena (bajo el 40 %, PARAR) y la forma de la firma (R20) |
| **T27-T31b** · huellas del antes, reconstrucción acotada, huellas del después **sin `--obras-esperadas`**, la 0599 y `v_frescura_obra` | R11-R12, R21-R23. **Una sola diferencia PARA la feature** |
| **T32-T35** · los `check-*`, el bloat contra T2, los créditos de CPU y desplegar `infra/97_create_alert_ventana.ps1` | R24, R29; y **sin ese `.ps1` el guardián es mudo** (DA-5) |
| Encender `PG_VENTANA_ACTIVA` | Del humano, y **la última**, no la primera |

## Automejora propuesta (no aplicada)

A C4 bis de `CHECKPOINTS.md`, y de ahí a `arnes-base`. **(1) RM7 · el alcance de
la campaña es el de la feature**: el reviewer recalcula `harness.alcance`; si se
acotó a mano, la reducción exige **exención escrita del humano**, no de la spec.
Sin esto, en `critico` se aprueba una campaña que mide el 38 % y todos los
números cuadran. **(2) Los timeouts no son muertos**: C4 bis exige «cero
supervivientes» y calla sobre los mutantes sin veredicto por reloj; **cada uno se
cierra por RM4 o se repite la campaña con más reloj**.
