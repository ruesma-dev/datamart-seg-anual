<!-- progress/review_F-042.md -->
Revisión completa (pasada 1) · `git diff 89a466c..HEAD` · HEAD `bd8d5ea`

# F-042 · Review · Un solo cierre por mes en los ámbitos reales

## Veredicto: **RECHAZADO**

**El SQL es correcto y la prueba que decide se sostiene**: verifiqué sus números
contra la base real, en solo lectura, y cierran **al céntimo**. No hay que
reejecutar ni volver a medir nada. Rechazo por otra cosa: **una de las puertas de
cierre que el humano va a ejecutar esta noche está ciega justo en las 9 obras que
F-042 cambia** (H2), R18 no está cumplido (H4) y tres afirmaciones del informe no
las sostiene la medición (H3, H5, H6). H2 es código, ~30 min; el resto es papeleo.

**Nivel de rigor `critico`** (declarado en `harness/features.json`). **Mutación:
N/A justificado.** Decisión del humano del **2026-08-29** («no me
hacen falta mutation test»), en la ficha de `features.json`, en `requirements.md`,
en `tasks.md` y en §7 del informe. La sustituye la no-regresión antes/después
(R22–R25). **Fase RED y cobertura sí se exigen, y están.** RM1–RM6 no aplican.

## Checkpoints

- **C1** `[x]` — `init.sh` código **0**: 2.791 pasados, 130 saltados, 420,69 s.
- **C2** `[x]` — una sola `in_progress`; rama correcta; `current.md` solo de esta
  sesión; `git status` limpio.
- **C3** `[x]` — hexagonal respetada (`domain/cierres.py` y `domain/huella.py`
  solo importan stdlib); ruta en la primera línea de los 12 ficheros nuevos.
  **Barrido de secretos ejecutado por mí** sobre las líneas añadidas (patrones
  `password|secret|token|api_key|client_secret|AccountKey|Uid=|Pwd=|bearer|
  credential|PRIVATE KEY`, GUID 8-4-4-4-12, IP 10./172./192., hosts Azure,
  `postgres(ql)://`, base64): **cero hallazgos**. Sin `print()`, sin `pdb`, sin
  TODO nuevos. **C3 bis** y **C4 ter**, `N/A`.
- **C4** `[ ]` — H2 (R16 cubierto en el oráculo, **ciego contra la base**) y H4
  (R18 incumplido). R13/R14/R15 sin test es correcto: condición de cierre.
- **C4 bis** `[x]` — fase RED con las cuatro trazas reales (§3); cobertura
  `[OK] 100,0 % de 649 líneas (649/649, umbral 80 %)`; mutación N/A justificada.
- **C5** `[ ]` — **`tasks.md`: 0 de 25 tareas marcadas `[x]`** (H1). Los commits
  sí están: T1–T25 (T20 y T23 combinados; T14–T16 son MANUAL, sin commit).

**Verificado a mano contra la base real (solo lectura).** Las tres CTE hacen lo
que dicen: `COALESCE(…,0)` es imprescindible (sin él `NULL <> 0` es falso y con
`DESC` los nulos irían **primero**) y `WHERE o.vive` precede a las ventanas, así
que el `LAG` solo ve supervivientes. **La master no se
toca**, y no solo por el hash: el `INSERT` es un `UNION ALL` de dos `SELECT`
independientes y el de master solo lee `master_con_pct_mes`. **`version` no se
contamina** —publica `mes_fase_num`—, así que los **seis** `JOIN ON
fm.numero_fase = pm.version` siguen alineados, y **desplazar y no `dense_rank()`
se sostiene**. Comprobé la **premisa oculta** del `JOIN`, que nadie declara: cruza
`USING (obra_id, ambito_id, mes_fase_num)` **sin `anio_mes`** y `stg.fases` no lo
garantiza (PK `fase_id`; `(obra_id, numero_fase)` es índice **no** único) —
**medido: 0** casos con dos `anio_mes`. Los fixtures cuadran con `explore` §4.2 y
el test reescrito **sí discrimina** (0545 Venta: gana la 6 con 157.760,75).

## Hallazgos
**H1 · `specs/F-042-clave-fact/tasks.md`: 0 de 25 tareas marcadas.** Es el
checkbox de C5: marcar las 25.

**H2 · GRAVE — `check-cierres` no puede ver R16 en las 9 obras que F-042 cambia.**
`cierres_sql.py:177-179`: `con_hueco = bool_or(version_previa IS NOT NULL AND
version_previa <> version - 1)`, calculado sobre **`version`**, que por R7 es el
número original de Sigrid **con los huecos que deja esta feature**. Tras el build,
la 0499 publicará versiones 17, 19, 21, 22 → `con_hueco = true` → la serie cae en
`series_con_hueco` y **se excluye de `series_rotas`**: la única comprobación de
R16 contra la base aparta las obras que hay que vigilar y devolverá un «0 series
rotas» que no las ha mirado. *Arreglo:* `plan_de_cierres()` ya devuelve
`descartadas`; clasificar como hueco de origen **solo** los saltos que los
descartes no expliquen, y añadir el test que falta.

**H3 · La causa que da el informe para el único `importe_mes` que se mueve es
FALSA.** `impl_F-042.md:196-201` y `current.md:24-26`: «el cierre descartado traía
acumulado menor que el mes anterior y el movimiento arrastraba ese tramo negativo
espurio». Eso no explica ninguna diferencia: un tramo negativo seguido del
positivo **telescopa**. La causa real, medida: hay **una** partida presente en las
fases **4 y 6** y **ausente de la 5**, con `importe_origen` en la fase 4 de
**4.538,09 €** — exactamente el delta. Antes, su fila de la fase 6 no tenía `LAG`
consecutivo y publicaba **el acumulado entero**; con la 5 descartada,
`orden_fase(6)=5` y pasa a publicar la diferencia. El valor nuevo **es el
correcto** y **repara el telescopio de R16**, roto ahí por +4.538,09. Consecuencia
hoy no escrita: **R8, tal como está redactado, NO se cumple en esa celda.**
Desviación aceptable y mejor que el statu quo, pero debe constar como decisión en
`impl_F-042.md` y en `design.md` §6.

**H4 · R18 no está cumplido: el aviso de doblado no se retiró, se reescribió en
pasado — y lo forzó un guardián que nadie revisó.** El recuento de `DOBLADO` en
`config/diccionario/mart.yaml` **sube de 5 a 6**, porque
`tests/test_f006_stg_trampas.py:674-692` sigue exigiendo la palabra literal en el
`significado` de cada columna acumulada: retirarla —lo que pide R18— lo pondría en
rojo. La verificación declarada en `tasks.md` T19 («`grep DOBLADO` no devuelve
nada vigente») **no se cumple**, y el mensaje de fallo de ese guardián ya es
falso. Elegir una de las dos y escribirla: retirar el aviso y adaptar el guardián,
o declarar que R18 se cumple describiendo el defecto **en pasado**, y reescribir
el guardián para que exija eso.

**H5 · Los 21,23 € residuales de la brecha no son «céntimos de redondeo»**
(`impl_F-042.md:194`). Son la **0462**: Venta 214.678,67 vs 214.657,72 = **20,95**;
Coste 197.654,80 vs 197.654,52 = **0,28**. Con los **1.197,99** de la 0246 (fase 12
= 753.433,05, acaba el 15-jun, frente a la 13 «AGOSTO 2010» = 754.631,04) suman
**1.219,22**, la brecha exacta. «Son dos reglas distintas» es correcto; redondeo, no.

**H6 · Dos frases afirman más de lo que se midió.** (a) **«0 cambios en los
ámbitos 8 y 11» es tautológico**: `huella_obras.py:317-322` **copia** esas filas
de la huella actual con `--propuesta`. El diseño lo dice (§5), pero §5 y §7 del
informe y `current.md:12` lo exhiben como medición y R24 los designa «la prueba de
que el arreglo no se desborda». La garantía real es que la master es byte a byte
la misma; decirlo así. (b) **`veredicto()` demuestra «y solo», no «exactamente… lo
previsto»** (`domain/huella.py:204-218`): comprueba que las obras movidas sean
**subconjunto** de las esperadas y cero cambios en 8/11; no que las 9 esperadas
**se hayan movido**, ni contrasta importes contra R14. (Lo son —el total cierra al
céntimo—, pero lo demuestra T17 a mano, no la herramienta.)

**H7 · La afirmación que el diseño corrigió sobrevive intacta en el código.**
`huella_obras.py:20-24` sigue diciendo que «el agregado de `stg` es
**exactamente** lo que `mart.fact_seguimiento_categoria` publicaría», sin el matiz
de que es falso en 8 y 11 (§6: 1.766 y 1.738 celdas difieren). Es el docstring del
módulo que **produce** la huella: copiar allí la corrección de `design.md` §5.

**Observaciones (no bloquean):**
- **O1** — R19 nombra `cierre.v_pbi_planif_vs_real`; el texto se escribió, pero
  `_objetos_que_agregan_el_fact()` filtra `esquema != "mart"` y nada lo guarda.
- **O2** — `test_f042_r16_el_telescopio_se_cumple_tras_renumerar` dice «vale sin
  excepción»; a grano de **partida** no lo es (H3): el oráculo simula el `LAG` a
  grano de obra y el SQL particiona por (obra, **partida**, ámbito). Por eso
  ningún test puede fallar por H3. Ningún fixture distingue tampoco «mayor
  `numero_fase`» de «el último de la lista».
- **O3** — Menores: 0545 no es «la única» colisión donde el moderno baja con
  líneas valoradas (`:234`), **0462 también**; la huella no graba el `_built_at`;
  acotar `test_f011_alcance.py` deja sin barrera viva el SQL de `stg`/`mart`.

**Condiciones de cierre (no bloquean el veredicto).** R13, R14 y R15 solo se comprueban **escribiendo en producción**. Con H1–H7
corregidos queda aprobable a la espera de: `stage` + `build-mart` + `build-cierre`
sin `ingest`; la huella del después contra las de T14; `check-unicidad` = **0**
(hoy 8.778, y es lo esperado); `check-cierres` **ya arreglado** (H2) y
`check-diccionario` en código 0. **Un orden que no se puede invertir:**
`mart.yaml:33,39,306` está en pasado («hoy devuelve **0** frente a las 8.778»),
falso hasta reconstruir: `publicar-diccionario` va **después** del build.

**Automejora propuesta (no aplicada):** C4 no distingue **cubierto** de **cubierto
con un alcance más estrecho del que el test declara** (H2, H3, O2). Sugiero en C4
bis: *«el reviewer nombra el caso real que pondría a prueba cada requisito de tipo
"esto NO cambia" y comprueba que el test lo alcanza»*.
