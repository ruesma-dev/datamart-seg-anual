<!-- progress/review_F-042.md -->
Revisión incremental desde `bd8d5ea` (pasada 2) · `git diff bd8d5ea..HEAD` ·
HEAD `8169201`

# F-042 · Review · Un solo cierre por mes en los ámbitos reales

## Veredicto: **APROBADO**

Con una **condición de cierre** que no bloqueaba y que ya estaba prevista: la
reconstrucción, que es escritura en producción y autoriza el humano. **Cumplida
el 2026-08-30**; su verificación es la 3ª pasada del final.

**El SQL del build no se ha tocado** —`git diff bd8d5ea..HEAD -- .../sql/` sale
vacío—, así que sigue en pie lo verificado al céntimo en la pasada 1: las tres
CTE, el `COALESCE`, el `WHERE o.vive` delante de las ventanas, la rama master
intacta, `version` sin contaminar y la premisa oculta del `JOIN` (0 casos con
dos `anio_mes`).

## Nivel de rigor `critico`; **mutación N/A justificado**

Decisión del humano del **2026-08-29** («no me hacen falta mutation test»),
registrada en `features.json`, `requirements.md`, `tasks.md` e informe §7. La
sustituye la no-regresión antes/después (R22–R25). **Fase RED y cobertura sí se
exigen y están.** RM1–RM6 no aplican.

## Checkpoints

- **C1** `[x]` — `init.sh` código **0**: 2.802 pasados, 130 saltados.
- **C2** `[x]` — una sola `in_progress`; rama correcta; árbol limpio.
- **C3** `[x]` — el delta no añade dependencias ni imports de infraestructura en
  dominio (`itertools.pairwise`, stdlib). **Barrido de secretos repetido por mí**
  sobre las líneas añadidas: **cero hallazgos**. Sin `print()`, sin `pdb`, sin
  TODO nuevos. **C3 bis** y **C4 ter**, `N/A`.
- **C4** `[x]` — R16 y R18, los dos incumplimientos de la pasada 1, quedan
  cubiertos con tests que muerden (abajo). R13/R14/R15 sin test sigue siendo
  correcto: son la condición de cierre, **verificada en la 3ª pasada**.
- **C4 bis** `[x]` — fase RED de la pasada 1 intacta; cobertura `[OK] 100 % de
  **656** líneas` (no 631: el diff creció); mutación N/A justificada.
- **C5** `[x]` — `tasks.md` con las **25 de 25** marcadas y un commit por tarea
  (T14–T16 son MANUAL del humano y no llevan commit, correctamente).

## Los siete hallazgos, uno a uno

**H1 · CERRADO** (25 de 25 tareas marcadas). **H2 · CERRADO, y verificado a
fondo porque era el único que era código.** `sql_telescopio` ya no clasifica por
`version`: reconstruye `orden_fase` desde `publicado`, `candidato`, `descarte` y
`orden`, y `con_hueco` es `orden_previo <> orden_fase - 1`. *¿Reimplementa otro
nombre? **No**:* `descarte` es `candidato LEFT JOIN publicado … WHERE
p.numero_fase IS NULL`, no calcula acumulado ni elige ganador de mes; observa
**qué fases sostiene el origen y no llegaron a `plan_mensual`**, que es un hecho.
La comprobación de la regla es `contrastar(agrupar(…), plan_de_cierres(…))`,
oráculo independiente. Lo fija
`test_f042_r16_los_descartes_del_telescopio_son_un_hecho_no_una_regla`.

*Y lo que verifiqué por mi cuenta, porque un SQL correcto en la idea puede estar
mal en la aritmética (detalle íntegro en el commit `d43ecb2` de este fichero):*
`_AMBITOS` = **(3, 7)**, ni una fila master; `candidato` reproduce el universo de
`reales_base`, así que `publicado ⊆ candidato`, `descarte` es exactamente el
descartado y ambos son disjuntos y `DISTINCT` (el `UNION ALL` no repite y la
ventana no empata); `orden_fase` es **estrictamente creciente** en `numero_fase`,
así que `orden_fase DESC` no mueve `ultimo_acumulado`; y **`con_hueco` es
definicionalmente idéntico al predicado del `LAG`**: 0499 publicada 17/19/21/22
con 18 y 20 descartadas da `orden` 17/18/19/20 → **entra** en el recuento, que es
lo que fallaba, y 0471 `([4, 6], [5])` sale **False** frente a `([4, 6], [])`
**True** — el par que discrimina.

**H3 · CERRADO.** `design.md` §6.5 declara la desviación con la causa correcta
—la partida en las fases 4 y 6 y ausente de la 5, con 4.538,09 € en la 4— y la
conclusión honesta: **R8 no se cumple en esa celda**, se acepta porque corrige un
defecto preexistente. Coincide con lo que medí en la pasada 1.

**H4 · CERRADO, y el guardián nuevo muerde.** `mart.yaml` pasa de 6 apariciones
de `DOBLADO` a **0**: R18 se cumple ya literalmente. El viejo exige lo que no
caduca (citar la feature, decir que es un acumulado); el nuevo,
`test_f042_r18_ninguna_ficha_describe_el_doblado_como_vigente`, barre el
diccionario **cargado** —no el YAML crudo, donde el plegado `>-` dejó ciegas a
otras comprobaciones— con su control de mordida.

**H5, H6, H7 · CERRADOS.** Los 21,23 € atribuidos a la 0462 (Venta 20,95 + Coste
0,28), que es lo que medí. El cero de los ámbitos 8 y 11 dicho **cierto por
construcción**, con el hash de la rama master como garantía y la nota de que
**sí** medirá cuando el «después» venga de una reconstrucción.

**O1 y O3 · atendidas.** Derivador nuevo para los consumidores del fact fuera de
`mart` (con test de control sobre `cierre.v_pbi_planif_vs_real`) y un fixture que
alimenta los cierres **desordenados**.

## Condiciones de cierre · **las cuatro, cumplidas el 2026-08-30**

`stage` + `build-mart` + `build-cierre` corrieron dentro de `run-all --full`
(job `caj-datamart-seg-dev-d8y5q10`, imagen `r20260830-0924`), con
`publicar-diccionario` **después** del build. `check-unicidad` da **0** en
`fact_seguimiento_mensual` (eran 8.778), `check-cierres` **0 discrepancias** en
8.540 cierres y `check-diccionario` biyección **103/103**. La huella del después
la sustituye la medición directa de la 3ª pasada.

**Observaciones (no bloquean):** `_EN_PRESENTE` es una lista de siete formas y
una redacción nueva («el dato viene al doble») se le escaparía; y
`test_f006_r19_…` importa `_bloque_del_objeto` de otro módulo de tests dentro de
la función, un acoplamiento que merece un helper compartido cuando haya calma.

## 3ª pasada · verificación del criterio 5 contra la base reconstruida (2026-08-30)

Revisión incremental desde `d43ecb2`, acotada al **criterio 5**
(«`importe_origen` deja de venir doblado»). **SOLO LECTURA** con
`pg.filas_solo_lectura()` (`SET LOCAL transaction_read_only`): ni una escritura,
árbol limpio. Fact reconstruido, `_built_at` **2026-08-30 10:50:39**.
**Método · oráculo independiente del build.** Recompongo el acumulado por
`(obra, ámbito, mes, fase, categoría)` desde `stg.presupuesto ⨝ stg.fases ⨝
stg.partidas` —las tres intactas en F-042— y aplico R14: el «antes» es la SUMA de
las dos fases, el «después» la ganadora sola. **El oráculo se valida sin usar la
línea base:** sus 18 sumas «antes» reproducen **al céntimo** los 18 «Publicado
hoy» de `explore_F-042.md` §4.2 (total **64.418.038,26 €**).

| Barrido de la tabla ENTERA | Valor |
|---|---|
| Celdas cruzadas oráculo ↔ `mart` / desvío máximo | **17.289** / **0,00 €** |
| Celdas que cambian / obras / retirado | **35** / **7** / **30.424.662,34 €** |
| Claves duplicadas en el fact por categoría | **0** |

**35 celdas y 7 obras: exactamente la línea base honesta**, y fuera de ellas no
se mueve ninguna otra celda. El retirado es el que T16 predijo al céntimo y
difiere de los 30.425.881,56 € en los **1.219,22 €** ya explicados (regla del
humano vs exploratoria: 0246 fase 13, 0462 fase 7). Los
casos que decidían: **0606 · PUY DU FOU** conserva la fase **14** (6.511.852,72 €
CD, ámbito 3) y cambia **0,00 €** —R2/R11 medido en la base, no en un fixture—, y
0433 igual; **0462 · RETAMAR**, cuyo mes en conflicto era el ÚLTIMO de la obra,
publica ya **197.654,80 €** de coste (era 395.309,32); y la joroba de **0246 CD**
desaparece: abr 498.650,13 · may 498.650,13 · **jun 499.586,06** · sep 499.832,38.
El eje temporal sigue con huecos (jul-ago 2010, jun-ago 2020): es F-050.

### Criterio 5: **APROBADO**

**Dos observaciones, ninguna bloquea.** (1) El diccionario publicado dice «35
celdas de 7 obras — **30.425.881,56 €**»: celdas y obras son exactas, pero lo
retirado son **30.424.662,34 €** — ese importe describe la regla exploratoria, no
la implantada; una línea a corregir en el próximo `publicar-diccionario`.
(2) Ajena a F-042 y previa: 1.152 filas de `stg.presupuesto` de la obra **0599**
(2,6 M€ en abr-2022) no llegan al fact porque su `partida_id` no tiene ficha en
`stg.partidas`.
