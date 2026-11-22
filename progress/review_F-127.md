# F-127 · Revisión (reviewer)

Revisión de evidencias desde b45f5ac: `git diff b45f5ac..9502df9` (solo `progress/`) y `progress/mutacion_F-127.md`.

**Veredicto (pasada de evidencias): APPROVED.**

**Pasadas anteriores:**
- **Pasada principal:** APPROVED en b45f5ac. Antes hubo dos CHANGES_REQUESTED. El de f920fb8 era por las
  CP del centro `CP` visibles, y lo resolvió D9 (c1). El de c49591e era por C1 (`test_f104_r18 == 80`), y lo
  resolvió fe92a67. Las pruebas de esas pasadas están en el historial de este fichero.
- **Mediciones de la pasada principal, en Azure y en solo lectura:** 722.704 filas en total, 181.804
  restringidas, 540.900 generales y 1.000 cuentas. El residuo visible del centro `CP`, de `CP%` y de asientos
  de personal da 0 con seis criterios propios. El barrido de nombres y NIF del diff da 0. RM4 a mano: 9/9 en
  la pasada 1 y 9/9 en la pasada 2.

**Nivel de rigor:** `critico` (declarado en `features.json`). Exige fase RED, cobertura del 90 % y mutación
uno por línea con fracción 0,6 y tope [100, 300], con cero supervivientes y RM1-RM7. La capa e2e es
informativa.

## C4 bis · la campaña (no reejecutada: 8.637 s según el informe, más de 60 s)

La lanzó el líder con `python -m harness.mutacion --feature F-127 --base main --rama puerta/F-127 --workers 3
--timeout 2400 --con-seleccion` sobre b45f5ac. Resultado: **30 generados, 19 evaluados, 19 muertos, 0
supervivientes, 0 timeouts y 0 sin veredicto**. No lleva la cabecera «CAMPAÑA NO VÁLIDA». Las tres líneas
base corrieron en verde (1.862-1.924 s), y el JSON dice `fiable: true` con el SHA de b45f5ac.

**Recálculo puro (independiente):**
- Alcance: con `alcance_de_feature("F-127", base="main", rama="b45f5ac")` salen **197 líneas**:
  `settings.py` 10, `build_contabilidad_step.py` 50 y `restriccion_personal.py` 137.
- Mutantes: `generar_mutantes` da **30**, los 30 en el dominio.
- Muestreo: `reducir_por_linea(Random(20261030))` deja **19 candidatos**. El tope del nivel es
  min(300, max(100, ⌈0,6·19⌉)) = 100, así que la campaña es completa: no hay muestreo y coincide con
  `rigor.json`.
- Los 19 que salen, con su línea, operador y texto original→mutado, son **exactamente** los 19 de la tabla
  del informe y del JSON. Los he cruzado todos, no solo una muestra.

**Ficheros sin mutantes, prueba de control:** sobre el fichero entero, `generar_mutantes` saca 40 mutantes de
`settings.py` y 18 de `build_contabilidad_step.py`. El generador funciona, así que el 0 del alcance es
legítimo.
- `settings.py`: las 10 líneas son comentarios.
- `build_contabilidad_step.py`: las 50 líneas son el docstring y cinco `_SubStep` de cadenas.

Ninguna de las dos declaraciones queda en `PENDIENTE`. El SQL no lo muta la herramienta (solo muta Python).
Lo cubren las mutaciones a mano: 39 del implementer y 9 + 9 mías.

## RM1-RM7

- **RM1** `[x]` Se midió `b45f5acc…` y HEAD es 9502df9. Entre los dos, `git diff b45f5ac..9502df9` solo toca
  `progress/impl_F-127.md` y `progress/mutacion_F-127.md`. El alcance es el mismo que se midió.
- **RM2** `[x]` Línea base ≈ 1.890 s y media por mutante de 454,6 s (24 %, no llega a ser un salto de orden de
  magnitud). Además 19 × 454,6 = 8.637 s, que es el «Tiempo total». Una media por debajo de la base es lo
  esperable con `-x`, con 19/19 muertos y con subconjuntos de 8,5 tests de media. Cuatro mutantes se
  juzgaron con la suite entera (1.139,5 s de media): son los de línea sin mapa (constantes y decorador).
- **RM3** `[x]` Ninguno de los 19 muertos es equivalente.
  - 180 y 181 cambian los literales `20`/`32`, que fija `r3_los_literales_de_con_tip`.
  - 209 (`slots=False`) se ve en `__slots__`, y lo caza `test_f006_toda_dataclass_del_paquete_usa_slots`.
  - 244 (el defecto `True`) cambia el resultado de C3.
  - El resto invierte comparaciones o ramas que tienen test.
- **RM4** `[x]` Hecha en las pasadas 1 y 2 (18 mutantes de SQL y dominio, todos muertos), y ahora RM5.
- **RM5** `[x]` Los tres «equivalentes» no son supervivientes de la campaña. Son 3 de los 11 generados que el
  uno por línea dejó fuera, y el implementer los pasó en serie por su cuenta. **He elegido el 265**
  (veracidad): `if fila.apunte_id is not None and not fila.apunte_resuelto` →
  `if fila.apunte_id and not fila.apunte_resuelto`.
  - Lo he reproducido en una copia `git archive` de b45f5ac con la batería del implementer más el barrido de
    F-006: **618 passed, rc 0, vivo**.
  - Con una fila que tiene `apunte_resuelto = False`, el original y el mutante solo difieren con
    `apunte_id = 0`. Con `None` los dos dan visible y con `7` los dos dan `APUNTE_SIN_RESOLVER`; con `0`,
    el original da `APUNTE_SIN_RESOLVER` y el mutante da visible.
- **RM6** `[x]` El 0 nunca llega, y está comprobado en **quien construye el dato**, que es el SQL. El oráculo
  no tiene ningún llamante de producción: es el espejo del SQL que prueban los tests.
  - **Medido en Azure (solo lectura).** `raw.apa` sí trae ceros: `apuide = 0` en 83.597 filas y
    `cueide = 0` en 127. Pero 08 los convierte en NULL con `NULLIF(a.apuide, 0)` y `NULLIF(a.cueide, 0)`, y
    esas dos líneas las fija `test_f127_r3_columnas_en_orden` (líneas 427 y 434 del test). El tipo `FilaAnalitica` declara
    además `apunte_id` = `NULLIF(apa.apuide, 0)`.
  - **No existe ninguna cuenta 0.** `raw.caa` y `raw.con` no tienen `ide = 0`, y la rama D9 y `cp_recurso`
    filtran `caaconide <> 0`.
  - **No existe ninguna obra 0.** `maestro.centros_coste` tiene 0 filas con `obra_id = 0`: la obra que no se
    resuelve sale NULL.
  - **Conclusión: los tres son equivalentes en el dominio declarado.** Un test con el 0 no lo recomiendo. En
    el 265 obligaría al oráculo a restringir un `apunte_id = 0` que el SQL publica como visible (NULL), así
    que fijaría un contrato distinto del SQL que corre. Tampoco hace falta una feature aparte.
  - No se ha quitado ninguna guarda: desde b45f5ac no ha cambiado el código.
- **RM7** `[x]` Hecha en la pasada 1: mover 10 delante de 08 pone en rojo F-127 y F-056. La cuarta
  comprobación no añade ningún orden nuevo.

## Checkpoints

- **C1** `[x]` La puerta completa del líder sobre **48849e9** salió con EXIT 0 (13.852 passed, 0 failed) y
  `PUERTA COBERTURA` al 100,0 % (48/48). Desde 48849e9 solo cambia `progress/`. En el worktree, que no tiene
  `.env`, `test_f127` da 188 passed y 1 skipped. Tamaño: review 135/140.
- **C2** `[x]` F-127 es la única feature activa (`in_review`) y va en su rama. **C3 bis**: N/A, no entra
  ningún documento de fuera.
- **C3** `[x]` Dominio puro y SQL en `infrastructure/`, sin secretos ni prints, y `ruff` limpio en los
  ficheros de F-127 (de92958).
- **C3 ter** `[x]` D8 está contestada, con su fuente y su fecha.
- **C3 quater** `[x]` `azure-apps` 70a039a y 7586308 tocan solo `datamart_seg_anual.md`, van en commit aparte
  y **no están subidos**.
- **C4** `[x]` La tabla de abajo. **C4 bis** `[x]`: fase RED, cobertura, mutación (arriba), RM1-RM7 y la
  sección «Evidencias». La capa e2e es N/A: es un ETL sin interfaz y ningún requisito es `(capa: e2e)`.
- **C4 ter**: N/A, no hay `harness/rutas_sensibles.json`.
- **C5** `[x]` T1-T11 `[x]` (T11 en 9502df9). T12-T16 son MANUAL (humano) y T17 es la puerta del líder.

## Cobertura requisito → test (`tests/test_f127_mayor_analitico.py`)
| Req | Test(s) |
|---|---|
| R1-R2 | `r1_el_completo_es_una_tabla…`, `r1_sin_filtrar…`, `r1_nada_multiplica`, `r1_indices…`, `r2_la_guarda_de_recuento` |
| R3-R6 | `r3_*`, `r4_no_lee_los_campos_vetados_de_apa`, `r4_la_obra_solo…`, `r5_saldo_acumulado…`, `r6_*` |
| R7 | `r7_*` (C1-C3, D7-b) y, de D9, `r7_c3_d9_*`, `r7_c3_el_conjunto_cp_con_d7[centro_cp]` |
| R8-R11 | `r8_*`, `r9_*`, `r10_los_literales_del_sql_son_los_del_dominio` (con `'CP'`), `r11_*` · R13: MANUAL (T14) |
| R12, R14 | `r12_*`, `r14_*` |
| R15 | `r15_guarda_sin_cp`, `r15_guarda_sin_apunte…`, `r15_d9_guarda_sin_asientos_de_personal`, `r15_guarda_general_mas…` |
| R16-R19 | `r16_*`, `r17_*`, `r18_*`, `r19_*` · R20: MANUAL (T15) |
| R21-R23 | `r21_*`, `r22_*` (con `r22_d8_contestada_en_las_fichas_de_las_cp`), `r23_*` |
| R24 | `r24_*` (el de `azure-apps` se salta en el worktree) · R25, R26: MANUAL (T13, T16) |

## Para el líder y el humano

- Los tres mutantes vivos de fuera de la campaña (249, 265 y 283) los acepto como **equivalentes justificados
  por escrito**. Conviene que el humano lo vea en el resumen final. En `critico`, un superviviente necesita su
  aceptación, y aunque estos no lo son formalmente, son de la misma familia.
- Sigue abierto, sin bloquear: `test_f127_mayor_analitico.py:1156` fija la versión del diccionario con
  `== 81`.
- `progress/mutacion_F-127.json` queda sin versionar, como el de F-164.

## Automejora (propuesta, no aplicada)
- C4 bis: si una restricción se define por un CONJUNTO, medir el **residuo visible de su familia** (mismo
  centro, prefijo, código en otra empresa), no solo lo que el conjunto atrapa.
- `reviewer.md`: con fichas sobre datos personales, el barrido contra `raw.res`/`raw.emp` (en memoria y solo
  con recuentos) es obligatorio en cada pasada.
- `reviewer.md`/`implementer.md`: la batería que sustituye a la puerta debe incluir todo test que fije la
  versión del diccionario (`grep '"version"\] =='`), y esa versión se fija con `>=`.
- `reviewer.md` RM5: aclarar qué hacer con los mutantes que el «uno por línea» deja fuera cuando alguien los
  evalúa y salen vivos. Hoy no son supervivientes, pero se tratan como tales.

Azure: solo lecturas (`filas_solo_lectura`, READ ONLY) desde el checkout principal, sin cambiar su rama.
