<!-- progress/impl_F-110.md -->
# F-110 · Informe del implementer (2026-09-25)

Rama `feature/F-110-fin-obra-cuatrimestral` (desde `main` 79a4505, que trae
F-108). `sdd: true`, rigor `critico`. Spec aprobada:
`specs/F-110-fin-obra-cuatrimestral/` + «APROBADA (humano, 2026-09-25)» de
`progress/spec_F-110.md` (D1-D6; D5: `ultimo_cierre` se QUEDA informativa). Un
commit por tarea (`F-110 T0` ... `T15`, mas `F-110: BACKLOG.md regenerado`). En
`azure-apps`, commit local `f087516` (rama `master`). Nada de push.

## Que cambio

**La regla** (decision del humano del 2026-09-25, cambia H1 de F-095):
`fecha_fin_obra` = inicio de garantia; si no, **ultimo dia del mes siguiente al
ultimo mes con importe planificado de la ultima version Cuatrimestral**; si no,
NULL. `fuente_fin_obra` = `INICIO_GARANTIA` / `ULTIMO_CUATRIMESTRAL_MAS_1_MES`;
`ULTIMO_CIERRE_MAS_1_MES` desaparece. Plazo y vencimiento, sin tocar.

| Fichero | Cambio |
|---|---|
| `sql/retenciones/05_fin_obra.sql` | Guarda `DO $$` con 4 `RAISE 'fin_obra: ...'` antes del `DROP` (tabla de versiones inexistente, sin ninguna `Cuatrimestral`, `stg.plan_mensual` sin ambitos 8/11, `cierre.fact_cierre_mensual` inexistente); se retira la de cierre VACIO. CTE `cuatrimestral` (`MAX(v.version)` con `tipo_master = 'Cuatrimestral'`) y `plan` (`MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0)`, `LEFT JOIN` por `obra_id` + `version` + ambitos 8/11); `base` une `plan` solo por `obra_id` y publica `version_cuatrimestral` y `ultimo_mes_planificado` detras de `ultimo_cierre`; `fin` con los dos `CASE` nuevos, sin `ELSE` y sin `ultimo_cierre`. CTE `cierres`, `constantes`, `oc`, plazo, vencimiento e informativas: sin cambio. Cabecera y `COMMENT ON TABLE` reescritos (regla, ejemplo literal, D1-D6, medidas) |
| `sql/retenciones/06_views_contables.sql` | Solo el comentario de `SIN_FIN_OBRA`; ni una linea de SQL |
| `application/steps/build_retenciones_step.py` | Docstring y comentario de `depends_on` con las tres lecturas; codigo, `SUB_PASOS`, `name`, `stage` y `depends_on` iguales |
| `config/diccionario/retenciones.yaml` | Ficha `fin_obra`: regla, ejemplo del humano, decision del 2026-09-25, cifras antes/despues, columnas `version_cuatrimestral` y `ultimo_mes_planificado`, `ultimo_cierre` INFORMATIVA, `valores` nuevos, las de F-095 como historicas con fecha. Ficha `v_retencion_contable_obra`: `valores` y SIN_FIN_OBRA |
| `config/diccionario/00_global.yaml` | `version: 34` y linea de historia |
| `docs/ARCHITECTURE.md` | Vineta de la retencion: regla, las dos lecturas de la misma noche, el cierre informativo con su noche de desfase |
| `azure-apps/datamart_seg_anual.md` | Fila de `retenciones.fin_obra` y parrafo F-110 (lecturas, guarda, que cambia para quien consume, version 34) |
| `tests/test_f110_fin_obra_cuatrimestral.py` (nuevo) | 33 casos, R1-R23, offline |
| `tests/test_f095_retenciones_contables.py` | T3: los 6 de la lista reescritos citando F-110, docstring de `r18`, cabecera y la entrada `fin_obra` de `CONTRATO_SQL` |
| `progress/current.md`, `harness/features.json`, `BACKLOG.md`, `tasks.md` | Estado |

## Decisiones de diseno y desviaciones

1. **R12 en dos tests.** T2 pide `-k "r11 or r12 or r13"` en verde ANTES de
   tocar el SQL, pero R12 veta tambien `ultimo_cierre`, que el SQL viejo usaba.
   `test_f110_r12_*` fija las tres informativas de Sigrid (verde antes) y
   `test_f110_r10_ultimo_cierre_no_interviene` fija que `ultimo_cierre` no
   entra en fin, terminada ni vencimiento (rojo antes). R12 queda entero.
2. **T3: `r20` y `r21_un_fallo` no llegaron a estar rojos.** Su cambio es de
   mensaje (el `assert` de `r20` y el texto del `RuntimeError` de `r21`), como
   dice la propia lista de T3; se reescribieron igual y citan F-110.
3. **Mensajes de la guarda**: los cuatro empiezan por `fin_obra:`; los de
   version y plan dicen que lanzar (`build-mart` / `build-stg`).
4. **T8 y T9 en un commit**: T9 (el test de R16) quedo escrito en T1 y pasaba
   ya; T8 solo toca docstring y comentario.
5. **`test_f110_r5_ejemplo_del_humano` ejecuta la aritmetica que esta escrita**:
   lee los dos `INTERVAL` del CTE `fin` y los aplica en Python (2028-03-01 ->
   2028-04-30; febrero bisiesto, noviembre y diciembre). Cambiar '2 months' o
   '1 day' lo rompe (S7, S8 de la campana).
6. **La campana de mutacion ejecuta tambien el test de R23**: cada copia lleva
   `azure-apps/datamart_seg_anual.md` al lado (sin eso, el test se salta).

## Verificacion real contra la base (solo lectura)

Script `verif.py` (scratchpad), transaccion `READ ONLY` sobre el Postgres del
`.env`, 263 s en total para 9 consultas. Ejecuta la **guarda `DO`** y el
**SELECT nuevo de `05_fin_obra.sql` tal cual esta en el fichero**:

- Guarda: pasa (las cuatro condiciones se cumplen hoy).
- **922 filas, 922 obras distintas = `raw.obr`** (922).
- Por fuente en las 922: **198 / 36 / 688** (INICIO_GARANTIA / cuatrimestral /
  sin fecha), exacto a `design.md`. `ultimo_cierre` informado en **304**,
  `version_cuatrimestral` y `ultimo_mes_planificado` en **117**.
- Viva de los efectos con obra: **97 / 5.026.655,18**, **32 / 2.960.583,38**,
  **50 / 260.028,59**: exacto. `terminada_sin_fin_obra` sobre lo vivo: **37 /
  154.037,10**: exacto.
- `1-0686`: version 28, `ultimo_mes_planificado` **2026-11-01**, fin
  **2026-12-31**, vencimiento **2027-12-31** (la cola a cero no cuenta).
  `1-0692`: 2025-02-01 -> 2025-03-31 -> 2026-03-31 (VENCIDA, D6). `31-0606`
  (version 21) y `1-0606` (version 3) con su propia cuatrimestral (R3).
- Frente a la tabla publicada hoy: **0 obras** con garantia, plazo,
  `fuente_plazo`, `ultimo_cierre`, fin real o contratos distintos.
- Saldo contable por estado (hoy): SIN_FIN_OBRA **186 obras / 903.839,72**
  (= `design.md`), PENDIENTE 33 / 5.673.882,21, VENCIDA 180 / 3.940.293,73.
- Coste: cada consulta con el SELECT entero tardo ~29 s de media (9 en 263 s),
  del orden de los +15-40 s estimados. La duracion real del sub-paso es MANUAL.

## Fase RED

**T1 (antes de tocar ningun SQL)**, comando `python -m pytest
tests/test_f110_fin_obra_cuatrimestral.py -q -p no:cacheprovider -W ignore
--tb=line` -> **27 failed, 6 passed** (los 6: `r11`, `r12`, `r13`, `r15`, `r16`,
`r22`, guardas de lo que no cambia). Requisitos centrales, `-k "r1_ or r5_ or
r7_ or r8_ or r9_ or r10_ or r14_"` -> **11 failed, 22 deselected in 0.86s**:

```
E   AssertionError: no encuentro el CTE «cuatrimestral» en 05_fin_obra.sql
E   AssertionError: no encuentro el CTE «plan» en 05_fin_obra.sql
E   AssertionError: no encuentro la aritmetica del +1 mes sobre ultimo_mes_planificado (D3)
E   AssertionError: no encuentro el CTE «plan» en 05_fin_obra.sql
E   AssertionError: garantia; si no, ultimo dia del mes siguiente al ultimo mes planificado; si no, NULL
E   assert "CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA' WHEN b.ultimo_mes_planificado IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES' END AS fuente_fin_obra" in " SELECT b.*
E   AssertionError: la ficha dice que ya no interviene
E   AssertionError: assert 'ultimo_cierre' not in ' SELECT b.*...FROM base b '
E   AssertionError: cuatro fallos, todos con el nombre del sub-paso
E   assert "IF to_regclass('mart.master_versiones_tipadas') IS NULL THEN RAISE EXCEPTION 'fin_obra: no existe la tabla mart.master_versiones_tipadas; lanza build-mart antes de build-retenciones';" in
E   AssertionError: una tabla del cierre VACIA ya no tumba el vencimiento: solo deja ultimo_cierre a NULL
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r1_la_ultima_cuatrimestral_por_numero
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r5_ultimo_mes_con_importe_planificado
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r5_ejemplo_del_humano
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r7_la_cola_a_cero_no_es_plan
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r8_fin_de_obra - ...
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r9_fuente_del_fin_de_obra
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r10_ultimo_cierre_informativo
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r10_ultimo_cierre_no_interviene
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r14_guarda_antes_del_drop
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r14_guarda_de_la_version_y_del_plan
FAILED tests/test_f110_fin_obra_cuatrimestral.py::test_f110_r14_guarda_del_cierre_solo_de_existencia
11 failed, 22 deselected in 0.86s
```

**T2**, `-k "r11 or r12 or r13"` antes de tocar el SQL -> `3 passed, 30 deselected`.

**T3** (F-095 reescritos, SQL aun viejo), `python -m pytest
tests/test_f095_retenciones_contables.py -q -p no:cacheprovider -W ignore
--tb=line` -> **5 failed, 68 passed in 10.16s**, solo los de la lista:

```
E   assert 'IF NOT EXIS...rre_mensual)' not in " BEGIN IF t...o'; END IF; "
E   AssertionError: garantia; si no, ultimo dia del mes siguiente al ultimo mes planificado (F-110)
E   AssertionError: assert set() == {'master_versiones_tipadas'}
E   AssertionError: la ficha de fin_obra no dice «ULTIMO_CUATRIMESTRAL_MAS_1_MES»
E   AssertionError: retenciones.fin_obra: cambio el numero de SELECT (CTE)
FAILED tests/test_f095_retenciones_contables.py::test_f095_r21_guarda_cierre_vacio
FAILED tests/test_f095_retenciones_contables.py::test_f095_r19_fin_obra_y_fuente
FAILED tests/test_f095_retenciones_contables.py::test_f095_d7_solo_fact_cierre
FAILED tests/test_f095_retenciones_contables.py::test_f095_r28_las_fichas_traen_las_cifras_medidas
FAILED tests/test_f095_retenciones_contables.py::test_f095_contrato_expresion_a_expresion[retenciones.fin_obra]
```

**VERDE**, por tarea: T4 `-k "r14 or r21"` 12 passed; T5 17 passed (los 2
rojos restantes eran de T6 y T10); T6-T13 cerrando cada una con sus tests
(`test_f110` + `test_f095`: **106 passed** tras T13). Un test se corrigio en el
verde, con motivo: la regex de `r9` no admitia el digito de
`ULTIMO_CUATRIMESTRAL_MAS_1_MES` (fallo del test, no del SQL; commit T6).

## Evidencias

- **`bash harness/init.sh`** tal cual, rama en `cab45cd` (todo el codigo, el
  SQL, el diccionario y la campana ya commiteados): `[OK] pytest en verde (con
  medicion de cobertura)`, **5.519 passed, 203 skipped, 0 failed** en
  **658,68 s** (10 min 58 s, lo que imprime la suite); `[OK] PUERTA COBERTURA:
  95.1% de 1106 lineas cambiadas cubiertas (1052/1106, umbral 80%, nivel
  critico)`; `[OK] PUERTA TAMANO` (requirements 142/150, design 237/250);
  `[OK] Rama actual`; **ENTORNO LISTO**, exit 0. Avisos previos, no de F-110:
  ruff 233 (deuda; los ficheros de F-110 pasan limpios) y F-052 `blocked`. La
  cobertura se mide contra la rama de integracion y cuenta lineas de otras
  features; las lineas Python de F-110 son docstring y comentario.
- **Tests de F-110**: `test_f110_fin_obra_cuatrimestral.py` 33 casos y
  `test_f095_retenciones_contables.py` 73 casos, **106 passed** en ~2-4 s.
- Tras escribir este informe y cerrar T14/T19 se relanzo `bash harness/init.sh`
  para que la puerta de tamano mida tambien este informe: resultado en la
  ultima linea de `progress/current.md` §F-110.

- **Mutacion** (T15): `python -m harness.mutacion --feature F-110 --base main`
  -> **CERO MUTANTES** (27 lineas de docstring y comentario; exit 3); control
  con `generar_mutantes` sobre el fichero entero -> 12. Sustituta, como pidio
  el reviewer en F-095: **campana SISTEMATICA** generada por script sobre el
  CREATE entero de `fin_obra` (expresion, FILTER, WHERE, tipo y ON de cada
  JOIN), la guarda (condicion, IF quitado, prefijo, orden frente al DROP), 16
  semanticos de la regla y 16 de propagacion. SHA `5d06b28`, 3 workers, linea
  base 11-18 s (146 passed, 0 skipped), **517 s**. **114 generados, 114
  muertos, 0 supervivientes, 0 timeouts, 0 mortinatos**. Detalle y tabla:
  `progress/mutacion_F-110.md`.
- `ruff check` de los ficheros tocados: limpio.

## Lo que queda fuera del alcance

Nada de `sql/retenciones/00`-`04`, `sql/mart`, `sql/stg`, `sql/cierre`,
`main.py`, orquestador, grants ni `objetos_pendientes.yaml` (verificado por
test). No se ha construido, ingerido ni publicado nada: contra la base, solo
lecturas. `specs/F-109-*` sin tocar.

## Lo que falta (MANUAL, humano; T16-T18)

Con el `.env` del entorno que el humano autorice:

1. **Foto ANTES** (opcional: ya la tomo `verif.py` hoy, arriba): las Q1-Q3 de
   `progress/spec_F-110.md` §Consultas por el MCP.
2. `python main.py build-retenciones` y `python main.py apply-grants`. En el
   log, duracion del sub-paso `fin_obra` (< 2 min; hoy el paso entero 65 s).
3. `SELECT fuente_fin_obra, COUNT(*) FROM retenciones.fin_obra GROUP BY 1`
   -> ~198 / ~36 / ~688 (922 filas); `SELECT COUNT(ultimo_cierre) FROM
   retenciones.fin_obra` -> ~304.
4. `SELECT estado_vencimiento, COUNT(DISTINCT obra_id), COUNT(*), SUM(saldo)
   FROM retenciones.v_retencion_contable_obra WHERE obra_id IS NOT NULL GROUP
   BY 1` -> SIN_FIN_OBRA ~186 / ~903.839,72.
5. `SELECT * FROM retenciones.fin_obra WHERE clave_obra = '1-0686'` ->
   2026-11-01 / 2026-12-31 / 2027-12-31.
6. `python main.py check-declarados`, `python main.py check-unicidad`,
   `python main.py check-relaciones`, `python main.py check-diccionario`.
7. `python main.py publicar-diccionario` (version 34), reinicio del MCP
   (`mcp-bbdd` cachea el diccionario) y **despliegue de imagen nueva**: sin
   ella la nocturna sigue con la regla vieja.
