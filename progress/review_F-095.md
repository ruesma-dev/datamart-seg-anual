<!-- progress/review_F-095.md -->
Revisión incremental desde 215addc (pasada 2) · delta `215addc..bdf7c7a` · 2026-09-25

# F-095 · Review · APPROVED (APROBADO)

**Veredicto: APROBADO.** Los cinco cambios de la pasada 1 están hechos y
verificados por mi cuenta:

- el contrato del SQL fija ahora cada fórmula;
- la campaña es sistemática (264 generados, 264 muertos);
- mi muestra S1-S11 muere;
- una segunda muestra mía, independiente, muere entera.

Lo aprobado en la pasada 1 (SQL, spec, H1-H7, desviaciones, diccionario,
`azure-apps`, MANUAL) se da por bueno. El delta **no toca el SQL, el step ni la
spec**: solo `tests/test_f095_retenciones_contables.py` (+479) y `progress/`.
Nada de lo ya aprobado queda invalidado.

**Rigor:** `critico`, declarado. Exige fase RED, cobertura ≥ 80 %, campaña
entera con 0 supervivientes y verificaciones MANUAL con su comando.

## Qué se ejecutó (resultados reales)

- `bash harness/init.sh` tal cual, en `bdf7c7a`. El resultado está en
  «Puertas», al final de este informe.
- **Trazabilidad del delta.** Por `git diff --stat`: `215addc..528c2eb` toca el
  test y `review_F-095.md`; `528c2eb..HEAD` solo toca `progress/`.
- **RM1.** La campaña mide `528c2eb`, y de ahí a HEAD no cambia nada del
  alcance. OK.
- **RM2.** 1.212 s × 3 workers / 264 mutantes = 13,8 s por mutante, frente a
  una base de 10,5-17,2 s por copia. Es coherente.
- **Sistemática.** Crucé la tabla con el contrato (`CONTRATO_SQL`: 21 SELECT,
  165 expresiones, 21 JOIN, de los que 20 llevan ON):

  | Tipo de mutante | En la campaña | Lo que cabía esperar |
  |---|---|---|
  | Expresiones | 164 | 165: falta solo `b.*` del CTE `fin`, que no admite `NULL` |
  | Tipo de JOIN | 20 | 21 JOIN menos el `CROSS JOIN` |
  | Condiciones de ON | 22 | 20 ON con 22 condiciones |
  | WHERE / HAVING / FILTER / DISTINCT | 19 / 1 / 8 / 1 | todos los que hay |
  | Step | 11 campos, 3 esquemas y 4 sub-pasos quitados | — |

  No los eligió quien escribió los tests: los genera un script, y la tabla
  trae `fichero:línea`, el texto exacto y el número de fallos.
- **Reproducción literal de dos filas.** En una copia `git archive HEAD` del
  scratchpad:
  - #33 (`r.conide <> 0` → `TRUE`): 1 fallo, igual que la tabla;
  - #190 (`a.clase IN ('ALTA', 'BAJA')` → `TRUE`): 1 fallo, igual que la tabla.
- **S1-S11 y los 5 muertos de mi muestra anterior**, reejecutados sobre HEAD:
  mueren los 16 (entre 1 y 2 fallos cada uno).
- **Segunda muestra independiente, 12 mutantes**, de tipos que el generador
  del implementer no produce: fuente del FROM, GROUP BY, orden del COALESCE de
  la cascada, `UPPER`, `INTERVAL '1 day'`, la constante 12 → 15, un filtro
  nuevo en `obrctr`, los bordes `<` → `<=` y `>` → `>=` de `categoria`, un
  filtro nuevo en el CTE `contable` y un JOIN nuevo en `prescripciones`.
  **Mueren los 12.** Base: 94 passed. Total: 204 s, en serie. Script:
  `scratchpad/mut_review2.py`.
- Control del 0 automático: sigue siendo el de la pasada 1 (12 mutantes fuera
  de alcance). El 0 es legítimo.
- El árbol queda limpio (`git status`). Nada escrito en Sigrid ni en Postgres.

## Juicio sobre el contrato (RM3)

`test_f095_contrato_expresion_a_expresion` compara cada SELECT contra una
tabla **escrita en el test**, no generada desde el SQL que vigila, así que no es
tautológico. El control `..._el_parser_ve_lo_que_debe` impide que pase en vacío
(≥ 150 expresiones y ≥ 35 cláusulas, más dos fórmulas testigo).

El precio es explícito: es un contrato de texto. Cualquier cambio de fórmula
obliga a cambiar la tabla delante del reviewer, y por eso muere todo mutante
de texto. **Lo que valida la SEMÁNTICA con datos sigue siendo MANUAL (M4)**:
R5, FERMALUX, reparto de `via_obra` y categorías.

El #13 de la pasada 1 (`NULLS NOT DISTINCT`) queda declarado como equivalente
semántico, muerto por un test de texto, como se pidió. No invalida la campaña.

## Checkpoints

- **C1** [x], si `init.sh` sale con exit 0 (ver «Puertas»).
- **C2** [x] · **C3** [x], sin cambios desde la pasada 1.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x]:
  - R1-R31 trazables (tabla de la pasada 1, más el contrato por objeto);
  - offline;
  - MANUAL M1-M6 en `current.md`;
  - dobles: sin cambios.
- **C4 bis**:
  - [x] rigor · [x] RED · [x] cobertura;
  - [x] **Mutación**: `progress/mutacion_F-095.md` existe, con 264/264/0. Recalculé el
    alcance y el control del 0.
  - [x] Muertos comprobados (el total pasa de 60 s): reproduje dos filas y
    reejecuté 28 mutantes propios. No reejecuté los 264 por mi cuenta.
  - [x] Coste por mutante coherente · [x] sin «CAMPAÑA NO VÁLIDA», base en verde.
  - [x] RM1 (SHA completo) · [x] RM2 (base, media y workers) · N/A RM5
    (0 supervivientes, ningún equivalente dentro de la campaña) · [x] RM6.
  - [x] Tabla manual: `fichero:línea`, texto exacto y fallos; el #6 mortinato,
    sustituido por sub-pasos quitados enteros que compilan.
  - [x] 0 supervivientes · [x] «Evidencias» actualizadas.
- **C4 ter** N/A: no hay `rutas_sensibles.json`.
- **C5** [x] T0-T22 y T26 con commit. **T23-T25 son MANUAL del humano**: las
  siguientes, pendientes y bien descritas, NO hechas.

## Lo que falta para `done` (humano)

M1-M6 de `progress/current.md` §F-095, en este orden:

1. foto ANTES (K2, B1, FERMALUX);
2. `ingest --table rac --full`;
3. `build-retenciones` y después `apply-grants`;
4. las cifras (R5 = 0, FERMALUX `CUADRA`, repartos);
5. los `check-*` y la pregunta al MCP, y después `publicar-diccionario`;
6. la imagen nueva.

**Sin `rac` en `raw`, `build-retenciones` falla en `apuntes`.**

## Observaciones (no bloquean)

- `current.md` arrastra 2.064 líneas de sesiones anteriores. Es deuda previa;
  al cerrar, lo purga el líder.
- El generador del implementer no muta GROUP BY ni la fuente del FROM. Los
  cubre el contrato, y mi segunda muestra lo confirma.

## Automejora (propuesta, no aplicada)

- Mantengo la de la pasada 1: en C4 bis, que la campaña MANUAL de SQL sea
  sistemática (script, uno por expresión, filtro o join) y el reviewer añada
  su muestra.
- Además, que la campaña cubra GROUP BY y la fuente del FROM. Este generador
  no los muta.

## Puertas

`bash harness/init.sh` en `bdf7c7a`: **exit 0**, `5424 passed, 203 skipped`
(1.620 s), `[OK] PUERTA COBERTURA 94.7% (968/1022)`, `[OK] PUERTA TAMAÑO`,
**ENTORNO LISTO**. C1 [x].
