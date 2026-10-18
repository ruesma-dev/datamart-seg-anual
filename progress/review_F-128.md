<!-- progress/review_F-128.md -->
Revisión completa (pasada 1) · `git diff main...HEAD`, HEAD `9ddc2f7`, merge-base `5f7db50` (= `main`)

# F-128 · Review: la cabecera entera de factura y albarán

- **Veredicto: CHANGES_REQUESTED (RECHAZADO)**. Tres cambios, todos de texto o de papeleo; el
  código, el SQL, los tests y la protección de la cuenta bancaria están bien.
- **Nivel de rigor:** `estandar` (declarado en `features.json`). Exige fase RED, cobertura de las
  líneas cambiadas y campaña de mutación con supervivientes analizados. RM5 N/A por nivel.

## Cambios requeridos

1. **`config/diccionario/00_global.yaml:915`, `R-EMPRESA-POR-DEFECTO` (afirma de más):** «no la
   del documento (que es `empide`, pendiente de F-134)». `empide` **no es la empresa**: en `dca`
   y `dcf` es «Empleado», índice a `emp` (`azure-apps/sigrid_tablas.md`, las tablas `dca` y
   `dcf`), y F-134 es justo «quién registró el documento». Las fichas de la propia rama dicen lo
   correcto (`compras.yaml:585` y `:1075`: «que son exige leer `dbo.log`»). Quita el paréntesis
   (basta con «no la del documento») y añade un test que impida que la regla presente `empide`
   como la empresa. No escribas cuál es la empresa del documento: nadie lo ha medido.
2. **`00_global.yaml:866`, el mismo paréntesis aplicado a las dos:** «(estas dos, la empresa de la
   obra de CABECERA de la factura)». Vale para `retencion_factura`, pero **no para
   `v_cuadre_factura_obra`**: sus pares que solo están en contabilidad (SOLO_CONTABILIDAD) toman
   la obra y la empresa de `saldo_contable`, es decir, de la cascada contable de F-095
   (`07_cuadre_factura.sql`, `COALESCE(f.empresa_id, c.empresa_id)`). Su propia ficha lo dice
   bien (`retenciones.yaml:1927`). Corrígelo, por ejemplo: «`retencion_factura`, la de la obra de
   cabecera; `v_cuadre_factura_obra`, la de la obra del par (cabecera de la factura o cascada
   contable)».
3. **`progress/mutacion_F-128.md`: el tiempo no es coherente (RM2) y no se midió sobre HEAD
   (RM1).** La campaña, en serie, declara «Tiempo total» 593,9 s y «Línea base» 573,3 s. El total
   **incluye** la línea base (`harness/mutacion.py:1263` y `:1388`), así que el informe dice que
   juzgó 20 mutantes en 20,6 s, unos 1 s cada uno. Además la media (29,7 s) no llega a la décima
   parte de la línea base, que es el supuesto en que RM2 manda rechazar sin reejecutar. Y 1 s por
   mutante es imposible: solo recoger los 4 ficheros cuesta unos 17 s (mi tercera vía, abajo).
   Lo más probable es que la línea base corriera la suite ENTERA: `EjecutorPytest.linea_base`
   sustituye los `argumentos` por `ARGUMENTOS_LINEA_BASE`, de modo que si la acotación iba en
   `argumentos` se pierde. Los mutantes, en cambio, se juzgaron con los 4 ficheros. Además el SHA
   medido es `0fa7305` y no HEAD: después se tocó `cabecera_compra.py`, solo 3 caracteres en
   literales. **Qué hacer:** repetir la campaña sobre HEAD con línea base y mutantes sobre la
   MISMA suite acotada (los 4 `tests/test_f128_*.py`) y poner en la nota del informe la
   invocación exacta (el código Python), para que se pueda reproducir. Resultado esperado: 20 de
   20 muertos, con una línea base de unos 45 s y un coste por mutante de 20 a 45 s.

## Los cinco puntos que pidió el líder

1. **Versión y merge.** `main` (`5f7db50`) es el merge-base: el merge es fast-forward. Diccionario
   en **v56** (main en v55). Simulé el merge en un clon de mi scratchpad (`main` +
   `git merge` de la rama → `9ddc2f7`) y pasé allí los tests de versión de R31 (F-128), R29
   (F-141) y F-144, R22/R23 de F-128 y los que dependen de git (`test_f015_*`, `test_f112_*`):
   **53/53 y 132 passed (2 skipped)**. R31 aguanta el merge: si `main` ya trae «(F-128, », basta
   con `>=`. R22 y R23 quedan vacíos tras el merge (el diff contra `main` es nulo), sin romper
   nada. Clon borrado.
2. **`documento_cuenta_bancaria`.** Defectos de `settings.py`: `compras_restringida` está en
   `DEFAULT_VETOED_SCHEMAS` (:138) y en `DEFAULT_RESTRICTED_SCHEMAS` (:156), no está en
   `TOTAL_VETOED` (`raw`) y tampoco en `DEFAULT_PERFIL_RESTRINGIDO_SCHEMAS` (:191).
   `esquemas_ajenos` la da por ajena al perfil restringido. Ningún objeto nuevo casa con
   `PATRON_VIGILADO_RESTRINGIDO` (`mayor`). La única vista nueva, `v_cuadre_factura_obra`, lee
   solo `retenciones.*`, así que `filtraciones_restringido` no tiene nada que ver.
   `retencion_factura` es TABLA (lee `raw`, como el resto de `retenciones`). `git diff
   main...HEAD` de `grants.py`, `settings.py` y `02_roles.sql`: **vacío**. La tabla va en la
   última sección de `01_documentos.sql` y el esquema lo crea `compras/00_setup.sql:16`. R21
   barre todo el SQL con positivos fabricados, y R23 no encuentra ninguna cadena con forma de
   IBAN o CCC en los ficheros de la rama.
3. **`R-EMPRESA-POR-DEFECTO`.** Lo que es cierto contra el SQL:
   - `retencion_factura.empresa_id` = `ob.emp` de la obra de cabecera, igual que
     `apuntes_contables` y `maestro.v_obra_fichas`.
   - `factura_recargos`, `albaran_recargos` y `documento_cuenta_bancaria` no tienen ni empresa
     ni `obra_id`, y están bien en la lista de «sin».
   - `obra_cabecera_id` cubre el 95,98 % de las facturas («un 4 % no la tiene», correcto) y se
     relaciona con `maestro.obras.obra_id`.

   Las dos afirmaciones de más son los **cambios 1 y 2**.
4. **Tests ajenos.** Todos son ajustes mecánicos y ninguno quita una aserción:
   - `test_f047`, `test_f095` y `test_f110` añaden el fichero o el sub-paso nuevo a sus listas
     exactas.
   - `rows_processed` pasa de 15 a 18 porque es 6 recuentos × 3 del doble.
   - `test_f079` añade las 3 funciones nuevas a su inventario.
   - `test_f073` recalcula el hash de `01_documentos.sql`, con su nota, como hicieron F-084 y
     F-067; el prefijo de columnas lo siguen fijando `test_f083` y `test_f128_sql`.
5. **Mutación y evidencias.** Recálculo puro sobre HEAD: alcance de 528 líneas y **22 mutantes**,
   que cuadra con el informe. La campaña dura más de 60 s, así que no la reejecuté por la vía del
   arnés. **Tercera vía (RM4)** sobre una copia (worktree de HEAD en el scratchpad, sin bytecode,
   `-x` sobre los 4 `test_f128_*`, línea base verde: 134 passed y 1 skipped en 47 s): **los 22
   mutantes mueren**, entre ellos los 20 de la muestra con la semilla 20260820, con 17 a 58 s por
   mutante y 929,7 s en total. Worktree borrado y árbol limpio. El veredicto 20/20 es real; lo
   que falla es el informe (cambio 3). RM3: ningún mutante es equivalente; los de las líneas 66
   y 73 cambian lo que devuelven las funciones para 4 y 0. RM6: no se quitó ninguna guarda.
   `init.sh` tiene los números reales (los míos, abajo).

## Checkpoints

| Checkpoint | Estado | Nota |
|---|---|---|
| C1 `init.sh` exit 0 y ficheros del arnés | [x] | 2026-10-19: **8437 passed, 254 skipped** en 1504,7 s; ENTORNO LISTO |
| C2 una sola `in_progress` | [x] | solo F-128 |
| C2 rama | [x] | `feature/F-128-importes-cabecera-factura` |
| C2 `current.md` | [x] | la entrada de F-128 encima; lo de debajo es anterior a la rama (deuda heredada) |
| C2 `done` con history | [x] | F-128 no se marca `done`. Aparte, en `main`: F-044, F-047, F-141 y F-144 están `done` sin entrada en `history.md`, deuda que no es de esta rama |
| C3 hexagonal | [x] | dominio solo con stdlib; SQL `NN_nombre.sql` en `compras/` y `retenciones/` |
| C3 ruta en la 1.ª línea; sin prints, secretos ni dependencias | [x] | ficheros nuevos comprobados; R23 pasa |
| C3 semántica Sigrid | [x] | `totdoc`/`totpag`/`reccla`, grano protegido (agregado por documento antes del JOIN, sin `WHERE` externo); amb/fas, origen/mes y `obrfasamb` no aplican |
| C3 bis | N/A | no toca `docs/referencia/` |
| C4 trazabilidad | [x] | R1-R34 con tests `test_f128_rN_*`, 135 en verde; R35-R36 son MANUAL |
| C4 sin red ni BBDD | [x] | solo texto, el dominio y git local |
| C4 MANUAL listadas | [x] | T16 y T17 en `current.md` y en `impl_F-128.md` |
| C4 dobles contra el original | [x] | la puerta de `init.sh` en verde; F-128 no añade dobles |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | trazas reales T1-T12; T10 y T13 con positivo fabricado |
| C4 bis cobertura | [x] | `PUERTA COBERTURA` [OK]: 100,0 % de 66/66 |
| C4 bis mutación, informe de la herramienta | [x] | totales recalculados: 22 generados, alcance 528 |
| C4 bis muertos comprobados | [x] | más de 60 s: recálculo puro más RM4 independiente (22/22) |
| C4 bis la campaña tardó lo debido | [ ] | **cambio 3**: 20 mutantes en ~20 s una vez descontada la base |
| C4 bis sin «CAMPAÑA NO VÁLIDA» | [x] | «Sin veredicto» = 0 |
| C4 bis RM1 SHA de HEAD | [ ] | **cambio 3**: `0fa7305` ≠ HEAD (diferencia trivial, pero hay que repetir de todos modos) |
| C4 bis RM2 tiempo coherente | [ ] | **cambio 3** |
| C4 bis RM5 | N/A | rigor `estandar` y sin supervivientes |
| C4 bis RM6, supervivientes, campaña MANUAL, N/A sin motivo | [x] | no se quitó ninguna guarda; no hay supervivientes; la campaña fue automática (no aplica la MANUAL); ningún N/A sin motivo |
| C4 bis «Evidencias» | [x] | los cuatro números y los workers (en serie, explicado) |
| C4 ter | N/A | sin `harness/rutas_sensibles.json` |
| C5 `tasks.md` | [x] | T1-T15 y T18 `[x]` con sus commits; T16-T17 son MANUAL del humano, tras el merge |
| C5 sin temporales | [x] | `git status` limpio |
| C5 `features.json` | [x] | `in_progress` |

## Cobertura requisito → test (resumen; detalle en `tests/test_f128_*.py`)

| Req. | Test |
|---|---|
| R1-R4 | `test_f128_dominio.py` (`r1`-`r4`, más el inventario) |
| R5-R19, R24, R32, R33 | `test_f128_sql.py` (`test_f128_rN_*` de cada uno; R13 en `r12_r13_*`, R7 en `r6_r7_*`) |
| R20-R23 | `test_f128_restringida.py` |
| R25-R31, R34 | `test_f128_diccionario.py` |
| R35-R36 | MANUAL (humano), T16-T17 |

## Propuesta de automejora (para el humano, no aplicada)

- `CHECKPOINTS.md`, RM2: añadir que el «Tiempo total» **incluye la línea base**, y que el número
  que hay que comparar es `(total − base) × W / mutantes`. Sin eso, una base de otra suite pasa
  la regla del «coste por mutante ≥ 1 s» (aquí da 29,7 s, cuando el real implícito es ~1 s).
- `harness/mutacion.py`: que `EjecutorPytest.linea_base` conserve la acotación de los
  `argumentos` (o que la rechace) para que la base no mida una suite distinta de la que juzga a
  los mutantes. Vale para cualquier proyecto: va a `arnes-base`.
