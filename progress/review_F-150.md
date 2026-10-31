<!-- progress/review_F-150.md -->
Revisión incremental desde b98c830 (pasada 5) · `git diff b98c830..de4c40b` · HEAD `de4c40b`

# F-150 · Review · la receta de la caja

**Veredicto: APROBADO** (pasada 5: cuarta tanda N16-N17, T36-T45, R44-R52). Pasadas 1-4 aprobadas
(la 4, N11-N15, ya en `main`) y resumidas al final; el delta no las invalida: no cambia firmas
públicas de tandas anteriores; en `07` solo amplía `_dev_real` a COSTE (con `concepto = 'VENTA'`
añadido en `_dev_contrato` y el hueco, que leen lo de antes) y añade columnas, tablas y guardas.

**Nivel de rigor:** `estandar` (declarado en `features.json`): fase RED en los requisitos
centrales, cobertura de lo cambiado ≥ 80 %, mutación con supervivientes analizados.

## Pasada 5 · lo que se verificó

- **`bash harness/init.sh` ejecutado por mí sobre `de4c40b`:** **verde**, exit 0, «ENTORNO LISTO»:
  9.924 passed, 269 skipped (3.009 s); `PUERTA COBERTURA` `[OK]` 100 % (35/35, diff desde
  `1cf5197a79`); `PUERTA TAMAÑO` `[OK]`. Coincide con lo que declara el implementer.
- **Alcance = `design.md` §5.10-§5.11:** dominio (`cuota_personal`, `fuente_personal`,
  `pendiente_personal`, `fracciones_contrato`, `repartir_por_contratos`), `00_setup` (columnas
  aditivas y tabla `devengo_pendiente_contrato_mes` con índice único `NULLS NOT DISTINCT`), `07`
  (§2 quinquies, §4, §5, §5 bis, corte), YAML de hipótesis, diccionario v67, ARCHITECTURE,
  CLAUDE.md, tests. Hexagonal respetada: dominio puro, SQL en `sql/tesoreria/`.
- **`double precision` de `raw`:** `_dev_personal` suma `h.tot::NUMERIC(18, 2)`; `_dev_ctr` castea
  `cl.tot`, `canser` y `can` antes de operar; `abs(cl.tot) < 1e8` no exige numeric. Los `ROUND`
  nuevos van sobre numeric (`pe.personal` ya casteado / `real_origen` del mart; `pendiente ×
  cuota`; fracciones numeric). Sandbox del implementer con tipos de Azure: 37 OK (§4 del informe).
- **Tablas raw:** `hmores`, `res`, `ctrpro`, `ctr` y `con` ya están en `config/tables_sigrid.yaml`
  (l. 20, 270, 385, 606, 651); no hace falta ingesta nueva y `current.md` lo dice en el paso 3 del
  redespliegue MANUAL de N11-N17, con comandos exactos. Guarda de entrada de `07` ampliada.
- **Cuadre del reparto por contrato (leído línea a línea):** `_dev_ctr` agrega por (contrato,
  partida) con suelo 0 (`GREATEST(0, …)`), misma obra, `k.est NOT IN (8, 9)` y solo contratos con
  condiciones publicadas. Fracción = `LEAST(np, S)/np × ps/S` con `np` = pendiente − personal, sin
  CP. El reparto mensual por ACUMULADO en orden de `contrato_id` y el resto (`importe_np −
  ROUND(importe_np × Σf, 2)`) a `contrato_id` NULL: la suma por (partida, mes) es exacta y la
  última acumulada del window coincide con `e.total_fraccion` (suma numeric exacta). Meses ≤ 0
  enteros sin contrato (T39 bis, = `design` §5.11 paso 3). Guarda R50 dentro de la transacción
  (el `TRUNCATE` vuelve atrás con el `RAISE`), por obra y con negativos. La desviación de R48
  (ROUND por acumulado en vez de contrato a contrato) está justificada y testada: el literal de R48
  podía dejar un resto negativo que el propio R48 prohíbe.
- **Personal:** cuota solo en COSTE, CP → 0, `LEAST(1, ROUND(personal/real, 6))` = dominio; filtro
  de `_dev_personal` igual al de `10` (test de texto). Reparto con su residuo al último mes y la
  guarda de la suma ampliada. Receta y fichas: fin de mes, sin IVA ni retención ni H06, H13 sobre
  la base SIN personal (`importe_pendiente_personal`); N13-b fuera. **Catálogo: 30 hipótesis**
  (contado en el YAML).
- **Contraste Azure (R52, solo lectura):** personal 5,65 (spec ~5,64), 0686 0,21; enlazado 48,90 de
  112,84 (43,3 %), 0686 1,64 de 2,39; 0608 y 0715 a 0. Dentro del 5 %: sin PARADA.
- **Diccionario y ecosistema:** v67 con su nota; ficha nueva y columnas; tabla en el ámbito de
  `R-CAJA-HIPOTESIS` y en la lista F-141 (`test_f141_perfil_restringido.py:1535`);
  `PRESUPUESTO_MAX` con historia; inventario F-006 enmendado. `azure-apps` `9488087` (local).
- **Sin secretos ni `print`**; primera línea con ruta en los ficheros nuevos.

### Observaciones (no bloquean)

1. La guarda R50 filtra `obra_mes` con `categoria <> 'CP'` (un `categoria` NULL queda fuera),
   mientras `_dev_fraccion`/`_dev_ctr_reparto` usan `COALESCE(categoria, '') <> 'CP'` (lo meten).
   Una partida del plan ausente de `stg.partidas` tumbaría la noche por descuadre. Hoy
   `stg.partidas` siempre da categoría (`ELSE 'OTRO'`) y el fallo sería ruidoso, no silencioso;
   conviene unificar a `COALESCE` en una próxima tanda.
2. `_dev_ctr_reparto` descarta las filas con `pendiente = 0`; si un residuo dejara personal ≠ 0 en
   un mes con pendiente 0 (solo posible con pesos negativos en el plan), la guarda R50 saltaría.
   Mismo carácter: ruidoso; la sandbox (mes de −100 y −500) cubre los negativos conocidos.
3. T44 cita `progress/mutacion_F-150.md` como verificación; el fichero real es
   `mutacion_F-150_n16_n17.md` (el informe lo enlaza bien).

## Mutación (C4 bis) · `progress/mutacion_F-150_n16_n17.md`

- **Recálculo puro** (`alcance_de_feature('F-150', base='b98c830', rama='ddbc54f')` +
  `generar_mutantes`): **98 líneas** (414-511 de `proyeccion_caja.py`) y **33 mutantes**, igual
  que el informe. Los dos supervivientes existen tal cual (`:472 <= 0→<= 1` [entero], `:474 >
  0→>= 0` [comparacion]).
- **Campaña no reejecutada:** 6.888,7 s según el informe (> 60 s).
- **RM1:** medido en `ddbc54f`; hasta HEAD cambian `progress/`, `tasks.md` y un test, nada de
  producción. **RM2:** bases ~1.555 s (3 workers), media 861,1 s, `8 × 861,1 = 6.888,7`; media <
  base por `-x`, sin salto de orden de magnitud. **RM3:** ningún equivalente sale muerto (los dos
  supervivientes no son equivalentes: cambian la salida del dominio).
- **RM4 (copia `git archive` en el scratchpad, ya borrada):** sin mutar, 84 passed en
  `test_f150_contrato_compra.py` + `test_f150_personal.py`; los dos supervivientes con los tests
  nuevos → 1 failed cada uno; y dos no supervivientes elegidos por mí, `repartir_por_contratos`
  `importe <= 0 → < 0` y `cuota_personal` `real <= 0 → < 0` → 1 failed cada uno.
- **RM5:** N/A, rigor `estandar`. **RM6:** no se quitó ninguna guarda.
- Sin «CAMPAÑA NO VÁLIDA», 0 «Sin veredicto». Muestra de 8 (semilla del nivel); el SQL no se muta
  y lo cubren los tests de texto y la sandbox.

## Checkpoints (pasada 5)

- **C1:** `[x]` `init.sh` código 0 (ejecutado por mí) · `[x]` ficheros base.
- **C2:** `[x]` una sola `in_progress` · `[x]` rama `feature/F-150-receta-caja` · `[x]`
  `current.md` al día (redespliegue N11-N17) · `history.md`: N/A, la feature no es `done` (falta
  el despliegue MANUAL).
- **C3:** `[x]` hexagonal · `[x]` primera línea con ruta · `[x]` sin `print`, TODO, secretos ni
  dependencias nuevas · `[x]` semántica de Sigrid (`hmores.tot` con el filtro de `10`; contratos 8
  y 9 fuera; `R-ALBARAN-ABSURDO` a 1e8; CP fuera de la caja).
- **C3 bis:** N/A, el delta no toca `docs/referencia/`.
- **C4:** `[x]` trazabilidad (tabla) · `[x]` sin red ni BBDD en los tests · `[x]` MANUAL (T45) con
  comando exacto en `current.md` · `[x]` dobles: comprobación automática de `init.sh`.
- **C4 bis:** `[x]` rigor declarado · `[x]` RED con salida real para T36-T42 (`impl_F-150.md` §5)
  · `[x]` cobertura `[OK]` · `[x]` mutación verificada (arriba) · `[x]` «Evidencias» con los
  cuatro números.
- **C4 ter:** N/A, no existe `harness/rutas_sensibles.json` (solo el `.ejemplo`).
- **C5:** `[x]` T36-T44 `[x]` con su commit `F-150 Tn`; T45 (y T15/T25/T31/T35) abiertas solo por
  el despliegue MANUAL del humano · `[x]` árbol limpio · `[x]` `features.json` al día.

## Cobertura · requisito → test (pasada 5)

| Req. | Tests (nº de `test_f150_rNN_*`) |
|---|---|
| R44-R46 | `personal` r44 (9), r45 (10), r46 (4) + sandbox `07` |
| R47 | `receta`/`diccionario` r47 (7) |
| R48-R50 | `contrato_compra` r48 (17), r49 (13), r50 (1) + sandbox (guarda con mes de −500) |
| R51 | `receta`/`diccionario` r51 (4) |
| R52 | contraste de solo lectura en Azure (T40), tabla en `impl_F-150.md` §3 |

## Pasadas 1-4 · resumen

- **Pasada 1** (`6efddfe`): rechazo solo por C4 (MANUAL sin comando exacto). Sandbox 66 OK, Azure
  en solo lectura, catálogo 27, mutación 20 mutantes con RM1-RM6.
- **Pasada 2** (`7eed62e`): APROBADO. **Pasada 3** (`289fedb`): APROBADO; hotfix
  `totbas::NUMERIC(18, 2)` en `07`.
- **Pasada 4** (`1c54b31`, N11-N15): APROBADO; `init.sh` 9.813 passed; casts de `raw` en `09`,
  `10`, `07`, `08` leídos línea a línea; mutación 17 mutantes recalculados, RM4 en `:405`, `:408`.

## Automejora (propuesta, no aplicada)

1. `CHECKPOINTS.md` C4 bis: cuando el SQL nuevo lea `raw`, exigir que la sandbox con tipos de
   Azure viva en el repo (p. ej. `tests/sandbox/`, saltada sin Docker): hoy el reviewer no puede
   reejecutarla (pasadas 4 y 5).
2. `reviewer.md`: en guardas de cuadre SQL, comprobar que los dos lados filtran con la misma
   semántica de NULL (observación 1 de la pasada 5).
