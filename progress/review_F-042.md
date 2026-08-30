<!-- progress/review_F-042.md -->
Revisión incremental desde `bd8d5ea` (pasada 2) · `git diff bd8d5ea..HEAD` ·
HEAD `8169201`

# F-042 · Review · Un solo cierre por mes en los ámbitos reales

## Veredicto: **APROBADO**

Con una **condición de cierre** que no bloquea y que ya estaba prevista: la
reconstrucción (`stage` + `build-mart` + `build-cierre`) es escritura en
producción y la autoriza el humano. Hasta que corra, `check-unicidad` seguirá
dando **8.778**, que es lo esperado.

**El SQL del build no se ha tocado** —`git diff bd8d5ea..HEAD -- .../sql/` sale
vacío—, así que todo lo verificado al céntimo en la pasada 1 sigue en pie: las
tres CTE, el `COALESCE`, el `WHERE o.vive` delante de las ventanas, la rama
master intacta, `version` sin contaminar y la premisa oculta del `JOIN`
(medida: 0 casos con dos `anio_mes`). No se repite aquí.

## Nivel de rigor `critico`; **mutación N/A justificado**

Decisión del humano del **2026-08-29** («no me hacen falta mutation test»),
registrada en `features.json`, `requirements.md`, `tasks.md` e informe §7. La
sustituye la no-regresión antes/después (R22–R25), ya ejecutada. **Fase RED y
cobertura sí se exigen y están.** RM1–RM6 no aplican.

## Checkpoints

- **C1** `[x]` — `init.sh` código **0**: 2.802 pasados, 130 saltados.
- **C2** `[x]` — una sola `in_progress`; rama correcta; árbol limpio.
- **C3** `[x]` — el delta no añade dependencias ni imports de infraestructura en
  dominio (`itertools.pairwise`, stdlib). **Barrido de secretos repetido por mí**
  sobre las líneas añadidas de esta pasada: **cero hallazgos**. Sin `print()`,
  sin `pdb`, sin TODO nuevos. **C3 bis** y **C4 ter**, `N/A`.
- **C4** `[x]` — R16 y R18, que eran los dos incumplimientos de la pasada 1,
  quedan cubiertos con tests que muerden (abajo). R13/R14/R15 sin test sigue
  siendo correcto: son la condición de cierre.
- **C4 bis** `[x]` — fase RED de la pasada 1 intacta; cobertura `[OK] 100 % de
  **656** líneas cambiadas` (no 631: el diff medido creció); mutación N/A justificada.
- **C5** `[x]` — `tasks.md` con las **25 de 25** marcadas y un commit por tarea
  (T14–T16 son MANUAL del humano y no llevan commit, correctamente).

## Los siete hallazgos, uno a uno

**H1 · CERRADO.** 25 de 25 tareas marcadas.

**H2 · CERRADO, y verificado a fondo porque era el único que era código.**
`sql_telescopio` ya no clasifica por `version`. Reconstruye `orden_fase` desde
`publicado`, `candidato`, `descarte` y `orden`, y `con_hueco` pasa a ser
`orden_previo <> orden_fase - 1`.

*Lo que pediste mirar —¿reimplementa `plan_de_cierres()` con otro nombre?— y mi
respuesta: **no**, y el argumento del implementer se sostiene.* `descarte` es
`candidato LEFT JOIN publicado ... WHERE p.numero_fase IS NULL`: no calcula
acumulado, no ordena por `(acumulado <> 0) DESC, mes_fase_num DESC` y no elige
ganador de mes. Observa **qué fases sostiene el origen y no llegaron a
`plan_mensual`**, que es un hecho. Si el build descartara la fase equivocada,
`descarte` lo reflejaría fielmente y el telescopio seguiría valiendo — porque el
telescopio no es la comprobación de la regla: **esa es `contrastar(agrupar(...),
plan_de_cierres(...))`, que sí es un oráculo independiente**. Las dos
comprobaciones son complementarias y ninguna se cancela con la otra. Y lo fija
`test_f042_r16_los_descartes_del_telescopio_son_un_hecho_no_una_regla`, que
prohíbe `acumulado <> 0` y `DISTINCT ON` en el texto.

*Y lo que verifiqué por mi cuenta, porque un SQL correcto en la idea puede estar
mal en la aritmética:*

- `_AMBITOS` = **(3, 7)**: no entra ni una fila master por este camino.
- `candidato` reproduce el universo de `reales_base` (mismos tres `JOIN`, mismos
  `fase_num >= 1`, `anio`/`mes` no nulos), así que `publicado ⊆ candidato` y
  `descarte` es exactamente el conjunto descartado.
- `publicado` y `descarte` son **disjuntos** por construcción y ambos `DISTINCT`,
  así que el `UNION ALL` de `orden` no repite (obra, ámbito, fase) y el
  `ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING` no tiene empates.
- `orden_fase` es **estrictamente creciente** en `numero_fase` dentro de la
  (obra, ámbito), así que cambiar `desde_el_final` de `version DESC` a
  `orden_fase DESC` **no mueve `ultimo_acumulado`**.
- El `JOIN ... AND o.es_descarte = 0` no pierde filas: `publicado` sale de
  `plan_mensual`, así que toda fila publicada tiene su entrada en `orden`.
- **`con_hueco` es ahora definicionalmente idéntico al predicado del `LAG` del
  build.** Esa es la propiedad correcta: aparta exactamente las series en las que
  el build publicó el acumulado entero en vez de la diferencia.
- Comprobado a mano: 0499 publicada 17/19/21/22 con 18 y 20 descartadas da
  `orden` 17/18/19/20 → **entra en el recuento**, que es lo que fallaba; 1/2/4 sin
  descartes → apartada; y el caso de la 0471 (`[4, 6]` con la 5 descartada) sale
  **False**, mientras `([4, 6], [])` sale **True** — el par que discrimina.

`domain.cierres.hay_hueco_de_origen` hace la misma aritmética y su docstring
acierta en la asimetría que importa: `publicadas` es de UNA partida y
`descartadas` de la (obra, ámbito) entera, que es justo como lo calcula el SQL.

**H3 · CERRADO.** `design.md` §6.5 declara la desviación con la causa correcta
—la partida presente en las fases 4 y 6 y ausente de la 5, con 4.538,09 € en la
4— y con la conclusión honesta: **R8 no se cumple en esa celda**, se acepta
porque corrige un defecto preexistente y repara el telescopio. Coincide con lo
que yo medí contra la base en la pasada 1.

**H4 · CERRADO, y el guardián nuevo muerde.** `mart.yaml` pasa de 6 apariciones
de `DOBLADO` a **0**: R18 se cumple ya literalmente. El guardián viejo dejó de
exigir la palabra de alarma y exige lo que no caduca (citar la feature y decir
que es un acumulado); el nuevo,
`test_f042_r18_ninguna_ficha_describe_el_doblado_como_vigente`, barre el
diccionario **cargado** —no el YAML crudo, que es donde el plegado `>-` ya dejó
ciegas a otras comprobaciones—, en minúsculas y campo a campo. Y trae su control
de mordida: comprueba que la redacción vieja **sí** se detecta y que la nueva, en
pasado, pasa limpia. No veo debilitamiento: donde antes había una palabra, ahora
hay dos exigencias más un detector de tiempo verbal.

**H5, H6, H7 · CERRADOS.** Los 21,23 € atribuidos a la 0462 (Venta 20,95 +
Coste 0,28), que es lo que yo medí. El cero de los ámbitos 8 y 11 dicho **cierto
por construcción** en el informe y en el docstring de `veredicto()`, con el hash
de la rama master como garantía real y la nota de que **sí** medirá cuando el
«después» venga de una reconstrucción. `veredicto()` describe con precisión que
demuestra el «y solo» y no el «exactamente lo previsto». Y el docstring de
`huella_obras.py` ya lleva el matiz de los master.

**O1 y O3 · atendidas.** Hay derivador nuevo para los consumidores del fact
fuera de `mart`, con su test de control que exige que
`cierre.v_pbi_planif_vs_real` aparezca; y un fixture nuevo que alimenta los
cierres **desordenados**, que era lo que separaba «gana el de mayor
`numero_fase`» de «gana el último de la lista».

## Condiciones de cierre (las autoriza y lanza el humano)

1. `stage` + `build-mart` + `build-cierre` **sin `ingest`**, sobre el mismo `raw`.
2. La huella del después ya materializada, contra las de T14.
3. `check-unicidad` → **0** (hoy 8.778, y es lo esperado); `check-cierres` y
   `check-diccionario` en código 0. **`check-cierres` es ahora más caro**: el
   telescopio añade el barrido de `stg.presupuesto ⨝ raw.obrparpre ⨝ stg.fases`
   dentro de un `statement_timeout` de 300 s. Si salta, no es un fallo del dato:
   relanzarlo con `--obras` sobre las 9 afectadas.
4. **`publicar-diccionario` va DESPUÉS del build**, nunca antes: `mart.yaml`
   afirma en presente que la consulta «hoy devuelve 0», y eso es falso en la base
   hasta que se reconstruya.

**Observaciones (no bloquean):** `_EN_PRESENTE` es una lista de siete formas y
una redacción nueva («el dato viene al doble») se le escaparía — heurística
razonable, con control de mordida, pero conviene saberlo; y `test_f006_r19_…`
importa `_bloque_del_objeto` de otro módulo de tests dentro de la función, un
acoplamiento que merece subir a un helper compartido cuando haya calma.
