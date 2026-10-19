<!-- progress/review_F-128.md -->
Revisión incremental desde 9ddc2f7 (pasada 2) · delta `9ddc2f7..4afc6bf` (commits `3382803`, `546885a`, `1e697dd`, `4afc6bf`)

# F-128 · Review: la cabecera entera de factura y albarán

- **Veredicto: APPROVED (APROBADO)**.
- **Nivel de rigor:** `estandar` (declarado en `features.json`). Exige fase RED, cobertura y
  campaña de mutación con supervivientes analizados. RM5 no aplica: es solo para `critico`.
- **`bash harness/init.sh` (pasada 2, 2026-10-19):** ENTORNO LISTO, exit 0, **8438 passed, 254
  skipped** en 1190 s. PUERTA COBERTURA 100,0 % (66/66); PUERTA TAMAÑO dentro de los topes.
- Lo aprobado en la pasada 1 —SQL, permisos de `compras_restringida`, tests ajenos y simulación
  del merge— se da por bueno. El delta solo toca `00_global.yaml`, un test nuevo y dos informes de
  `progress/`, sin firmas públicas ni ficheros movidos. El alcance de mutación no cambia: 528
  líneas y 22 mutantes, recalculados sobre HEAD. La simulación del merge sigue valiendo: la
  versión del diccionario sigue en v56 y el delta no toca ningún test de versión.

## Los tres cambios de la pasada 1

1. **`empide` ya no se presenta como la empresa del documento** (`3382803`). El paréntesis ha
   desaparecido de `00_global.yaml` (~:918) y queda «no la del documento», sin afirmar cuál es.
   Hay un test nuevo, `test_f128_r_empresa_no_atribuye_a_empide_la_empresa`, que exige que
   `empide` no aparezca en la regla, con su fase RED pegada en `impl_F-128.md` (`1 failed`).
   **[x]**
2. **La empresa de las dos tablas de `retenciones`** (`546885a`). `00_global.yaml:866-870`
   distingue ahora entre:
   - `retencion_factura`, que lleva la empresa de la obra de CABECERA: `ob.emp` de
     `NULLIF(f.obride,0)`.
   - `v_cuadre_factura_obra`, que lleva la de la obra del par: la de cabecera, o la de la
     cascada contable de `saldo_contable` en los pares que solo están en contabilidad.

   Lo he contrastado con `07_cuadre_factura.sql`, donde se ve `COALESCE(f.empresa_id,
   c.empresa_id)` y el `FULL JOIN` por `obra_id`, y con la ficha `retenciones.yaml:1927`. Es
   cierto. **[x]**
3. **La campaña de mutación, repetida** (`1e697dd`). SHA medido `546885a`; desde ahí solo cambian
   `progress/*.md`, así que RM1 se cumple. La línea base y los mutantes usan la MISMA suite
   acotada mediante una subclase de `EjecutorPytest` en el script, con la invocación exacta
   escrita en el informe y sin tocar `harness/`. Resultado: base 33,2 s, total 52,5 s y 20 de 20
   muertos. **[x]**, con la verificación de la sección siguiente.

## Punto 3: por qué ~1 s por mutante ahora y 17-58 s en mi medición

**Rectifico la pasada 1.** Escribí que «solo recoger los 4 ficheros cuesta unos 17 s». Era falso.
La diferencia está en el **ORDEN de los ficheros con `-x`**:

- **En mi tercera vía (pasada 1)** puse primero `test_f128_diccionario.py`, que es el lento
  (~30 s). Con `-x`, cada mutante corría primero sus ~40 tests en verde y caía después, en
  `test_f128_dominio.py`: de ahí el «1 failed, 40 passed» de cada fila. Además coincidía con un
  `init.sh` en marcha.
- **En la invocación del implementer** va primero `test_f128_dominio.py` (dura ~1 s), y cada
  mutante cae en él.

No hay ejecución dentro del proceso ni caché: el ejecutor lanza un `python -m pytest` en un
proceso aparte con `PYTHONDONTWRITEBYTECODE=1` y `-p no:cacheprovider`
(`harness/mutacion.py:572-596`).

**Lo he comprobado yo** sobre un worktree de HEAD `4afc6bf` en mi scratchpad, con el orden del
implementer, `-x -rf --tb=line`, sin bytecode y sin la caché de pytest:

- La línea base sale verde: 135 passed y 1 skipped en 44,5 s.
- Los 20 mutantes de la muestra (semilla 20260820) mueren en **25,7 s**, entre **1,2 y 1,4 s**
  cada uno.
- Todos salen con **rc=1** («tests caídos»), con un test **FAILED** con nombre propio y por una
  aserción. **Ningún ERROR de colección ni de importación.** El código 2 (colección interrumpida)
  lo habría clasificado el arnés como INDETERMINADO y nunca como muerto.

| Mutante | Test que lo mata |
|---|---|
| L50-53 claves de `CLASES_RECARGO` | `test_f128_r1_clases_recargo_exactas` |
| L58 `{4,5}` y L61 `CLASE_FISCAL` | `test_f128_r2_garantia_y_fiscal[4/5/3-…]` |
| L66 `is None` → `is not None` | `test_f128_r1_clase_recargo[0-RECARGO]` |
| L73 (comparación y lógico), L78 | `test_f128_r2_garantia_y_fiscal[…]` |
| L489, L493, L503, L504 ×3 | `test_f128_r3_publicadas_por_objeto` |
| L519 ×2, L522 | `test_f128_r4_inventarios_reales_sin_errores` |

Worktree borrado y `git status` limpio.

- **RM2:** la media del informe (2,6 s) incluye la base; descontándola salen ~1,0 s por mutante,
  lo mismo que medí yo. El informe lo explica y es coherente. El coste por mutante está por
  encima de 1 s (1,2-1,4 s medidos). No es el caso que la regla del segundo marca como sospechoso,
  porque el veredicto de cada mutante está comprobado test a test.
- **RM3:** ningún mutante es equivalente.
- **RM6:** no se quitó ninguna guarda.

## Checkpoints (pasada 2; lo que no cambia, como en la pasada 1)

| Checkpoint | Estado | Nota |
|---|---|---|
| C1 `init.sh` y ficheros del arnés | [x] | 8438 passed, ENTORNO LISTO |
| C2 una sola `in_progress` / rama | [x] | F-128 / `feature/F-128-importes-cabecera-factura` |
| C2 `current.md` | [x] | la entrada de F-128 encima; lo de debajo es deuda anterior a la rama |
| C2 `done` con history | [x] | F-128 todavía no es `done`. Aparte, en `main`: F-044, F-047, F-141 y F-144 están `done` sin entrada en `history.md`, deuda que no es de esta rama |
| C3 hexagonal / ruta en la 1.ª línea / sin prints ni secretos | [x] | el delta es YAML, un test y `progress/` |
| C3 semántica Sigrid | [x] | regla de empresa ya cierta contra el SQL (cambios 1 y 2) |
| C3 bis | N/A | no toca `docs/referencia/` |
| C4 trazabilidad R1-R34 | [x] | tests `test_f128_rN_*`; R35-R36 son MANUAL (T16-T17) |
| C4 sin red ni BBDD / dobles | [x] | la puerta de dobles en verde; F-128 no añade dobles |
| C4 MANUAL listadas | [x] | `current.md` e `impl_F-128.md` |
| C4 bis rigor declarado | [x] | `estandar` |
| C4 bis fase RED | [x] | T1-T12 y la del test nuevo de la pasada 2 |
| C4 bis cobertura | [x] | 100,0 % (66/66) |
| C4 bis mutación, totales recalculados | [x] | alcance 528 y 22 generados, recalculados sobre HEAD |
| C4 bis muertos comprobados | [x] | total de 52,5 s, menos de 60: reejecutada por mí (20/20, test a test) |
| C4 bis la campaña tardó lo debido | [x] | 1,2-1,4 s por mutante, medido; explicado por el orden con `-x` |
| C4 bis sin «CAMPAÑA NO VÁLIDA» | [x] | «Sin veredicto» = 0 |
| C4 bis RM1 / RM2 | [x] | SHA `546885a` (después solo cambia `progress/`) / coherente una vez descontada la base |
| C4 bis RM5 | N/A | rigor `estandar` y sin supervivientes |
| C4 bis RM6, supervivientes, campaña MANUAL | [x] | ninguna guarda quitada; no hay supervivientes; la campaña es automática |
| C4 bis «Evidencias» | [x] | actualizadas en la pasada 2 (en serie; la fila «Workers 4» se explica en la nota) |
| C4 ter | N/A | sin `harness/rutas_sensibles.json` |
| C5 `tasks.md` | [x] | T1-T15 y T18 `[x]`; T16-T17 son MANUAL del humano, tras el merge |
| C5 sin temporales / `features.json` | [x] | árbol limpio / `in_progress` |

## Cobertura requisito → test (resumen)

| Req. | Test |
|---|---|
| R1-R4 | `test_f128_dominio.py` |
| R5-R19, R24, R32, R33 | `test_f128_sql.py` (R13 en `r12_r13_*`, R7 en `r6_r7_*`) |
| R20-R23 | `test_f128_restringida.py` |
| R25-R31, R34 y la regla de empresa | `test_f128_diccionario.py` |
| R35-R36 | MANUAL (humano), T16-T17 |

## Después de la aprobación (humano)

- Merge a `main`. Después, T16 (build en Azure, `apply-grants`, `check-diccionario`, comprobar
  que el login estándar recibe «permission denied» en `documento_cuenta_bancaria`) y T17
  (`publicar-diccionario` v56 y reinicio del MCP).

## Propuesta de automejora (para el humano, no aplicada)

- `CHECKPOINTS.md`, RM2: añadir que el «Tiempo total» **incluye la línea base**, y que el número
  que hay que comparar es `(total − base) × W / mutantes`.
- `harness/mutacion.py`: que `EjecutorPytest.linea_base` conserve la acotación de los
  `argumentos` (el implementer tuvo que escribir una subclase para conseguirlo). Vale para
  cualquier proyecto: va a `arnes-base`.
- `reviewer.md`, RM4: escribir en el informe con qué ORDEN de ficheros se reejecuta. Con `-x`,
  el orden cambia el tiempo en un factor de 30 (mi error de la pasada 1).
