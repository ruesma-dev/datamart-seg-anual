# progress/review_F-164.md
Revisión de evidencias desde 0311c39 · delta `0311c39..b934e11` (1 commit: `impl`, `mutacion`, `tasks.md` T7)

## Veredicto: APPROVED (APROBADO)

**Principal (resumen):** APPROVED en la pasada 2 sobre `0311c39` (pasada 1 `95a7c022f3..8aa0e6a`:
CHANGES_REQUESTED por H1/H2; pasada 2 `73be7f8..d363587`: H1, H2 y H4 resueltos). El detalle de las
dos pasadas principales vive en la versión de este fichero en `0311c39` (`git show 0311c39:progress/review_F-164.md`).

**Evidencias:** la campaña T7 es coherente con su estado, su log y mi recálculo; 10/10 muertos, cero
supervivientes, y 4 de los 10 los he reproducido yo en serie sobre una copia. Nada que pedir.

**Nivel de rigor:** `critico` (declarado; sin `rigor.local.json`). Mutación EXIGIDA, uno por línea,
tope `min(300, max(100, ceil(0,6·C)))`, semilla 20261030, cero supervivientes sin justificar.

## El delta (`git diff 0311c39..HEAD`)

| Fichero | Cambio | Valoración |
|---|---|---|
| `progress/mutacion_F-164.md` | nuevo (112 líneas): informe generado + «Análisis (implementer)» | Revisado abajo |
| `progress/impl_F-164.md` | Pendiente y fila «Mutantes» de Evidencias con los totales | Coinciden con el informe |
| `specs/.../tasks.md` | T7 `[ ]` -> `[x]` | Correcto |

Sin código de producción, ni tests, ni SQL, ni diccionario: nada invalida lo aprobado en la principal.
`progress/mutacion_F-164.json` sin versionar (estado de la herramienta), como debe.

## Puerta (C1)

- `ARNES_SIN_CACHE=1 bash harness/init.sh` sobre HEAD `b934e11`, ejecutado por mí: exit 0, **`13526 passed,
  2532 skipped` en 1 h 30 min**, `PUERTA COBERTURA` 100 % (24/24, umbral 90 %), `PUERTA TAMAÑO` en
  topes, `ENTORNO LISTO`. Sin servicios declarados: ninguna suite por caché.

## C4 bis · mutación

| Punto | Estado | Cómo lo he comprobado |
|---|---|---|
| Informe generado por la herramienta | [x] | Cabecera, tablas y «Cómo se juzgó» son las de `harness.mutacion`; sin «⚠ CAMPAÑA NO VÁLIDA»; «Sin veredicto (base rota)» = 0 |
| Línea base corrida y en verde | [x] | Log: `[base] wk_0/1/2: en verde (2990,6 / 3023,7 / 2995,2 s)`, iguales a las del informe |
| Informe = `.json` = log | [x] | Los tres dan el mismo SHA `0311c390…`, 15 generados, 10 candidatos y los mismos 10 `(línea, operador, original -> mutado)` con `muerto`; log `FIN rc=0` a las 14:06:52, 17065,2 s |
| Alcance (recalculado) | [x] | `alcance_de_feature("F-164", base="main")`: origen rama `95a7c022f3..`, **1 fichero, 72 líneas** (`domain/postventa.py`) |
| Mutantes (recalculados) | [x] | `generar_mutantes`: **15**; `reducir_por_linea` con `Random(20261030)` sobre la lista ordenada: **10**, exactamente los del informe |
| Los 5 no evaluados | [x] | Son los que el sorteo uno-por-línea deja fuera en 267, 270 y 272 (`veracidad`, `veracidad`, `negacion`, `comparacion`, `logico`); lo he obtenido yo con la semilla. 10 ≤ tope 100: campaña completa, sin muestreo |
| Cero supervivientes / cero timeouts | [x] | Informe, `.json` y log |
| RM1 · SHA medido | [x] | `0311c39…`, el aprobado por la principal; desde ahí solo cambian `progress/` y `tasks.md`, fuera del alcance |
| RM2 · coherencia del tiempo | [x] | Mapa 4901 s + base ~3000 s + 6 mutantes con suite entera (media 2761,7 s, 3 workers) + 4 con subconjunto (~75 tests) cuadra con 17065 s sin saltos de orden de magnitud. La «media por mutante» (1706,5) es total/evaluados; por debajo de la base, legítimo (con `-x` el muerto aborta) |
| RM3 · ningún equivalente muerto | [x] | Repasados los 10: los tres enteros cambian una pareja de `LISTA_ABIERTA`; 246 vacía el texto no nulo; 252/253/254/267/270/272 invierten una rama. Ninguno es equivalente |
| RM4 · tercera vía | [x] | Ver abajo |
| RM5 · equivalentes declarados | N/A | No hay supervivientes ni equivalentes declarados |
| RM6 · guardas quitadas | N/A | El delta no toca código; ningún mutante se mató quitando una guarda |
| RM7 · orden entre colaboradores | N/A | Como en la principal: el requisito central es una clasificación, no un orden de llamadas |
| Campaña no reejecutada | — | «Tiempo total» 17065 s (4 h 44 min) > 60 s: quedo en el recálculo puro + RM1–RM6 + la reproducción en serie |
| Capa e2e | N/A | Sin `servicios.json` ni requisitos `(capa: e2e)` |

**Por qué el SQL no se muta y está bien.** `harness.alcance.es_produccion` solo admite `.py`: el
`06_adjuntos.sql` y los YAML del diccionario quedan fuera por diseño. Su estructura la fija
`test_f164_sql.py::test_f164_r9_el_case_entero_es_el_del_dominio`, que en la pasada 2 maté a mano
con diez mutaciones del `CASE` (tabla en la versión de `0311c39`). Prueba de control del cero no
aplica: la campaña no declara cero mutantes ni ficheros sin mutantes.

## RM4 · reproducción en serie sobre una copia

Copia de `0311c39` con `git archive` en mi scratchpad (comprobado que `etl_sigrid` se importa de la
copia); mismos tres ficheros de tests que el implementer, sin `-x`. Base: `270 passed, 1 skipped`
(el `skip` es R13, que busca `azure-apps` al lado y en la copia no está; el implementer, en el árbol,
da 271). Cada mutante, sustitución literal única y restauración por copia:

| Línea · operador | Mutación | Resultado |
|---|---|---|
| 216 · entero | `= 34` -> `= 35` | **muerto**, 18 failed |
| 246 · logico | `(texto or "")` -> `(texto and "")` | **muerto**, 91 failed |
| 254 · comparacion | `is not None` -> `is None` | **muerto**, 57 failed |
| 272 · not | quita el `not` de `senal_parte_firmado` | **muerto**, 62 failed |

Restaurado: `250 passed` en `test_f164_dominio.py` y `diff` idéntico al original. Cuatro de diez, con
los dos más sutiles (246 y 272) incluidos: la reverificación en serie del implementer es creíble, y
el modo paralelo no ha dado falsos muertos en esta campaña. El árbol de trabajo no se ha tocado.

## Papeles para `human_review`

- [x] `tasks.md`: T1–T7 y T12 `[x]`; T8–T11 son las MANUAL del despliegue, con su comando y su
  responsable (líder o humano), que solo caben después del OK humano. Correcto que sigan `[ ]`.
- [x] `impl_F-164.md`: «Evidencias» con los cuatro números y la fila «Capa e2e»; mutación al día.
- [x] `mutacion_F-164.md` con análisis escrito de los no evaluados y de la reverificación en serie.
- [x] Topes: este informe ≤ 140 líneas.

## Checkpoints (estado final, principal + evidencias)

- **C1** [x] (ver Puerta). **C2** [x] Una sola activa (F-164, `in_review`), en su rama.
- **C3** [x] Sin cambios de código en el delta. **C3 bis** N/A (no toca `docs/referencia/`).
  **C3 ter** [x] (principal). **C3 quater** [x] (principal; azure-apps sin cambios en el delta).
- **C4** [x] Requisito → test en la principal (tabla en `0311c39`); las MANUAL, con su comando.
- **C4 bis** [x] Nivel, RED, cobertura 24/24 (principal) y **mutación exigida: cumplida**, arriba.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`. **C5** [x] T7 con su commit `F-164 T7:`.

## Observaciones (no bloquean)

- **E1 · Cabecera del informe.** Dice `--base main --workers 3 --con-seleccion` y omite el
  `--timeout 5400` de la orden real; el timeout sí consta en la tabla («fijado a mano») y en el log.
  La herramienta reconstruye la orden en vez de copiarla: candidato a mejora en `arnes-base`.
- **E2 · `current.md`** aún no tiene entrada de la campaña T7: la escribe el líder al pasar a
  `human_review`.
- Las O1–O4 de la principal siguen vigentes (O4 ya cumplida: el 246 entró en el alcance y murió).

## Automejora (propuesta, no aplicada)

- Las RM8 y la de C4 de la principal (en `0311c39`) siguen propuestas.
- **Informe de mutación:** imprimir la orden tal como se lanzó (`sys.argv`) en la cabecera (E1), para
  que el reviewer no tenga que ir al log a saber si hubo `--timeout` o `--max-mutantes`.
