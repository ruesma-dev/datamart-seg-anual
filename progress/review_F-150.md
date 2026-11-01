<!-- progress/review_F-150.md -->
Revisión incremental desde d03ecc9 (pasada 7) · `git diff d03ecc9..230a66b` · HEAD `230a66b`

# F-150 · Review · la receta de la caja

**Veredicto: APPROVED** (pasada 7). El delta (`230a66b`) solo toca `progress/current.md`,
`progress/spec_F-150.md` §12.4, `progress/impl_F-150.md` y `tasks.md`: nada de código ni del
alcance de la campaña. `init.sh` entero en verde sobre `230a66b` (ejecutado por mí): **10.042
passed**, 274 skipped (3.584 s), cobertura `[OK]` 100 % (30/30), tamaño `[OK]`.
- **Cambio 1 de la pasada 6, resuelto:** vuelta atrás en 4 pasos con comando exacto (job al tag del
  paso 0 y su `az`; `git switch --detach <merge>^1` + `publicar-diccionario` → v68 + `git switch
  main`, con el porqué: publica el ÁRBOL, no la imagen; `c9e4bbe` = merge-base real, comprobado;
  reinicio del MCP → «Versión 68»; la tabla y las 4 columnas se quedan sin escribir en producción).
  Igual en `current.md` y en la spec. C4 pasa a `[x]`.
- **Observación 1, resuelta:** paso 4 con `main._get_pg()` + `_bootstrap_done = True` +
  `filas_solo_lectura(sql, 120)` (firma comprobada en `postgres_client.py:1263`, `READ ONLY`).
- **Observación 2, resuelta:** T45 `[x]` con su resultado (imagen `r20261031-0933`, v67 → v68).
- Las observaciones 3 y 4 siguen como estaban (no bloquean). Lo de abajo es la pasada 6, vigente.

## Pasada 6 (bc4f54f..d03ecc9) · CHANGES_REQUESTED solo por la vuelta atrás, hoy resuelta

Pasadas 1-5 aprobadas (resumen al final); N18 no las invalida: no cambia firmas públicas, solo
añade al dominio y columnas/tabla aditivas; `importe_pendiente_personal` (N16) no se toca.

**Nivel de rigor:** `estandar` (declarado en `features.json`): RED en lo central, cobertura ≥ 80 %
de lo cambiado, mutación con supervivientes analizados.

## Pasada 6 · lo que se verificó

- **`bash harness/init.sh` ejecutado por mí sobre `d03ecc9`:** verde, exit 0, «ENTORNO LISTO»:
  **10.042 passed**, 274 skipped (2.771 s); `PUERTA COBERTURA` `[OK]` 100 % (30/30, desde
  `c9e4bbecba`); `PUERTA TAMAÑO` `[OK]`. Coincide con el informe.
- **Alcance = spec §12.2:** dominio (`cuota_irpf_ss`, `reparto_pago_personal`, `partir_personal` y
  constantes), `00_setup` (tabla y 4 columnas aditivas), `07` (2 sexies, pasos 5 y 6, guardas),
  `10` (R59), YAML de hipótesis (H01/H02/H06), diccionario v69, ARCHITECTURE, CLAUDE.md, tests,
  `azure-apps` `499defb` (local, sin push; comprobado). Hexagonal: dominio puro. Nada de
  `contabilidad/*` ni del orden de `run-all`; catálogo en 30.
- **`tesoreria` sin importes de nómina (punto pedido):** `reparto_pago_personal` solo lleva meses,
  recuentos, cocientes a 6 decimales, fuente, motivo y fecha (test r56 de nombres y del `INSERT`).
  Las sumas viven en `_dev_nomina` `ON COMMIT DROP`; los `RAISE` de las guardas no imprimen sumas
  de nómina. Umbral `personas_con_partes < 10` → `DEFECTO`/`POCAS_PERSONAS`, antes que la cuota,
  igual en SQL y dominio. La ficha es no recomendada y está en la lista F-141 (fuera del
  restringido, como el resto del esquema en esta feature). Las columnas por obra-mes son el
  personal de N16 partido por la cuota: no añaden dato de nómina.
- **Σ personal conservada:** `neto = personal − ROUND(personal × cuota, 2)` → suma exacta por
  construcción; guarda fila a fila con `IS DISTINCT FROM` (también caza NULL) que nombra obra y mes.
  Azure (solo lectura, T49): 5,6481 = 3,1521 + 2,4959, 0 descuadres en 465 filas COSTE.
- **Defecto = N16:** `DEFECTO` publica cuota 0; la obra-mes y `10` hacen `COALESCE(cuota, 0)`
  (empresa sin fila también va a todo-en-el-mes). Sin IRPF o sin SS (suma NULL) →
  `CUOTA_FUERA_DE_RANGO`, igual que el dominio.
- **SQL leído línea a línea:** clase NORMAL letra a letra con `02_mayor.sql` (test r57); cuentas
  exactas con `tip = 17`; `hab` `double` → `NUMERIC(18,2)` por fila antes de sumar; ventana
  `[build−15, build)` y `mes_hasta ≥ build−3`; sin ventana → `meses_con_nomina` 0 →
  `SIN_NOMINA_RECIENTE`; `ROUND(numeric)` de Postgres = `ROUND_HALF_UP` del dominio (lejos del
  cero). Guarda R61 antes de cualquier `TRUNCATE`. `10`: `(cierre + 2 meses − 1 día) >=
  CURRENT_DATE` (= `fecha_corte`), NULL sin cierre; guarda de entrada exige el reparto.
- **Excepciones a guardas de F-140** (`INTERVAL` 15/3/11 una vez cada uno; 3 lecturas de
  `hmores`, la tercera solo cuenta recursos): acotadas y justificadas en el test. Aceptadas.
- **Diccionario y receta:** v69 con nota; ficha nueva; 4 columnas; textos de `importe_pendiente_
  personal`, `pendiente_personal` y `saldo_partida_obra`; receta paso 0 (pagado = partes −
  `personal_irpf_ss_pendiente`) y paso 1 (dos tramos, mes siguiente aunque la obra no devengue,
  declarar `fuente` y decir `DEFECTO`); `regla` y ámbito de `R-CAJA-HIPOTESIS`. Cumple R60.
- **Contraste Azure (R62):** cuota 0,441909 `CONTABILIDAD` 12 meses; 0686 0,2104 → 0,1174 +
  0,0930; saldo 0,1234 en 17 obras (0686 0,0289). **Personas 245, no ~273 (−10 %):** T49 pedía
  PARADA > 5 %; el implementer lo explica (273 = todas las empresas; 245 = obras de la empresa 1,
  que es lo que manda §12.2 punto 4) y no mueve ninguna cifra (umbral 10). Acepto; queda para el
  humano.
- **Sin secretos ni `print`**; primera línea con ruta en el test nuevo.

## Mutación (C4 bis) · `progress/mutacion_F-150_n18.md`

- **Recálculo puro** (`parsear_diff` + `filtrar_produccion` sobre `bc4f54f..aeb2c15` y
  `generar_mutantes`): **83 líneas, 28 mutantes**, igual que el informe.
- **Campaña no reejecutada:** 5.948,4 s según el informe (> 60 s).
- **RM1:** SHA medido `aeb2c15`; hasta HEAD solo cambian `progress/` (impl, mutación, spec):
  nada del alcance. **RM2:** bases 1.227-1.244 s, media 743,5 s, `8 × 743,5 = 5.948`; media <
  base por `-x`, sin salto de orden de magnitud. **RM3:** 0 supervivientes, ningún equivalente
  declarado. **RM5:** N/A (`estandar`). **RM6:** no se quitó ninguna guarda.
- Sin «CAMPAÑA NO VÁLIDA», 0 «Sin veredicto». Muestra 8 de 28 (semilla del nivel). El SQL no se
  muta: lo cubren los tests de texto y la sandbox (61 OK; no reejecutable por mí, ver automejora).

## Checkpoints (pasadas 6-7)

- **C1:** `[x]` `init.sh` exit 0 (ejecutado por mí) · `[x]` ficheros base.
- **C2:** `[x]` una sola `in_progress` · `[x]` rama `feature/F-150-receta-caja` · `[x]`
  `current.md` describe la sesión (N18) · `history.md`: N/A, la feature no es `done`.
- **C3:** `[x]` hexagonal · `[x]` primera línea con ruta · `[x]` sin `print`, TODO ni secretos ·
  `[x]` semántica Sigrid (`apu.hab` double, clase del mayor, cuentas CR fuera del general).
- **C3 bis:** N/A, el delta no toca `docs/referencia/`.
- **C4:** `[x]` trazabilidad (tabla) · `[x]` tests sin red ni BBDD · `[x]` MANUAL con comando
  exacto (era `[ ]` en la pasada 6; resuelto en la 7) · `[x]` dobles: comprobación de `init.sh`.
- **C4 bis:** `[x]` rigor declarado · `[x]` RED con salida real T46-T48 (`impl_F-150.md` §5) ·
  `[x]` cobertura `[OK]` · `[x]` mutación verificada · `[x]` «Evidencias» con los cuatro números.
- **C4 ter:** N/A, no existe `harness/rutas_sensibles.json`.
- **C5:** `[x]` T46-T52 `[x]` con commit `F-150 Tn`; T53 abierta por ser MANUAL · `[x]` árbol
  limpio · `[x]` `features.json` al día.

## Cobertura · requisito → test (pasada 6, `tests/test_f150_personal_n18.py` salvo indicación)

| Req. | Tests |
|---|---|
| R53 | r53 (5 funciones, parametrizadas: medida, redondeo, cero, fuera de rango, extremos) |
| R54 | r54 (7: constantes, 12/1-11/0 meses, 9 y 10 personas, rango, orden, catálogo) |
| R55 | r55 (4: 0686, redondeo, Σ exacta parametrizada, cuota 0 y 1) |
| R56-R57 | r56 (7), r57 (5: clase = `02_mayor`, cuentas, ventana = dominio, filtro personas) |
| R58 | r58 (4: tramos por cuota de empresa, guarda fila a fila, corte, orden) + `test_f140_sql` |
| R59 | r59 (5, condición de fecha parametrizada) + `test_f150_saldo` |
| R60 | `test_f150_receta` / `test_f150_diccionario` r60 + `test_f140_hipotesis` (30) |
| R61 | r61 (guarda de entrada) |
| R62 | contraste de solo lectura en Azure (T49), `impl_F-150.md` §3 |

## Cambios requeridos (pasada 6; resueltos en la 7)

1. Vuelta atrás de `current.md`/spec §12.4 no ejecutable («`publicar-diccionario` con esa
   imagen»): resuelto en `230a66b` (arriba).

### Observaciones (no bloquean; 1 y 2 resueltas en la pasada 7)

1. Paso 4: `psql … $dsn` sin origen de `$dsn`. 2. T45 `[ ]` estando desplegada.
3. R59 solo mira los partes del `mes_ultimo_cierre`: si el build cae antes de fin del mes de
   cierre, el IRPF + SS del mes anterior al cierre (vence ese fin de mes) se da por pagado. Es lo
   que dice la spec; a validar por el humano si importa.
4. Los abonos de nómina de la empresa 1 (miles de EUR) están en `spec_F-150.md` §12.0 e
   `impl_F-150.md` §3: agregados de empresa, ya aprobados en la spec; no salen al datamart.

## Pasadas 1-5 · resumen

- **Pasada 1** (`6efddfe`): rechazo solo por C4 (MANUAL sin comando exacto). **Pasadas 2-3**:
  APROBADO (hotfix `totbas::NUMERIC(18, 2)` en `07`).
- **Pasada 4** (`1c54b31`, N11-N15): APROBADO; casts de `raw` leídos línea a línea; mutación 17.
- **Pasada 5** (`de4c40b`, N16-N17): APROBADO; 9.924 passed; mutación 33 recalculados, RM4 sobre
  los dos supervivientes; observaciones sobre NULL en la guarda R50 y la ruta de T44.

## Automejora (propuesta, no aplicada)

1. `CHECKPOINTS.md` C4 bis: cuando el SQL nuevo lea `raw`, exigir que la sandbox con tipos de
   Azure viva en el repo (`tests/sandbox/`, saltada sin Docker): sigue sin poder reejecutarse.
2. `CHECKPOINTS.md` C4: «la vuelta atrás de un redespliegue que publica diccionario dice cómo se
   vuelve a la versión anterior desde el puesto (rama o SHA) y qué objetos aditivos quedan».
