Revisión completa (pasada 1), diff cd81ea6..942b444 (spec en b614db7, PARADA 1 en cd81ea6; merge-base con `main` 17b41ec)

<!-- progress/review_F-162.md -->
# F-162 · Review · el seguimiento lleva todas las fichas de obra, con `es_por_defecto`

**Veredicto: APPROVED**, condicionado a lo que solo puede hacer el líder en la copia con `.env`:
(1) la puerta completa `bash harness/init.sh` en verde sobre 942b444; (2) T12, la sandbox
`tests/test_f162_sandbox.py` con `F162_SANDBOX_DSN`, sin `skip`; (3) el `EXPLAIN (ANALYZE)` de
solo lectura de `03_obras.sql` antes del despliegue (ver la observación 1). Si cualquiera sale
rojo, el veredicto cae. Desplegar (T13/T14) es MANUAL del humano y no condiciona este review.

**Rigor:** `estandar`, declarado en `features.json`. Exige RED, cobertura ≥ 80 % de lo cambiado
y mutación muestreada (20 mutantes, semilla 20260820). RM5 no aplica.

## Lo que verifiqué yo

| Qué | Resultado |
|---|---|
| Tests de F-162 + afectados (f102, f073, f108, f052 ×2, f147 ×2), copia `git archive` en el scratchpad | 490 passed, 13 skipped, 1 failed: `f147_r8`, que llama a `git ls-files` y la copia no es repo (artefacto, como en F-157) |
| `f147_contenido`, `f006_contexto`, `f144*` en el worktree | 112 passed (incluye el `f147_r8` de arriba) |
| 23 ficheros que leen las vistas, el diccionario, `03_obras`, `maestro.obras` o `find-obra` (f006 ×5, f025, f038, f047, f056, f057, f067, f073 ×2, f083, f084, f094, f095, f101, f118, f147, f162, f102) | 2308 passed, 340 skipped, 0 failed |
| Cobertura de lo cambiado, medida por mí (`coverage` + `harness.alcance`) solo con `test_f162_fichas_por_empresa.py` | **49/49 = 100 %** (22 de `ficha_obra.py` y 27 de `main.py`) |
| `ruff` | ficheros nuevos limpios; en los tocados, 71 avisos frente a 73 en cd81ea6: no hay ninguno nuevo |
| `git status` al terminar | limpio |

No corrí `init.sh` ni la suite entera: el encargo lo prohíbe, porque el worktree no tiene `.env`.

## El modelo pedido por el humano

- **Todas las fichas, sin desempate (R1, R2).** `03_obras.sql` mantiene los filtros de hoy (lista
  cerrada, `!~ '[0-9]{5,}'`, nulos y vacíos), quita `WHERE rn = 1` y el `JOIN` a `conext`. El
  conjunto de antes (las `rn = 1`) está contenido en el de ahora, así que **ningún `obra_id`
  publicado cambia ni sale**, y sus columnas `codigo_obra`, `nombre_obra` y `activa` salen de las
  mismas expresiones.
- **`es_por_defecto` (R5, R6).** Lo da un `ROW_NUMBER() ... = 1` por `codigo_obra` con este
  orden: `empresa_id = 1` primero, `COALESCE(num_lineas,0) DESC`, `tiemod DESC NULLS LAST` y
  `obra_id DESC`. Va criterio a criterio con `clave_por_defecto` del dominio. Ninguna mención a
  `conext`.
- **La desviación de `dudosas` (`<> 1` en vez de `NOT bool_or`) es correcta y la acepto.** Con
  dos fichas de Ruesma en un código, R5 (1) no decide sola. Con `NOT bool_or`, el SQL desempataría
  por `tiemod` y el oráculo por líneas. Hoy no hay ningún caso y el coste no cambia.
- **`lineas` se agrega antes de unir** y solo para `dudosas`. Hoy `dudosas` está vacía.
- **R8.** `maestro.obras.es_por_defecto` es `COALESCE(so.es_por_defecto, vf.es_ficha_principal)`,
  la última columna. El `LEFT JOIN stg.obras` es por PK (`obra_id`) y no multiplica filas.
  `maestro` ya leía `stg`. Así lo dicen R8 y design D1 (observación 3).
- **`clave_obra`** se calcula como en `maestro.v_obra_fichas` (`emp::text || '-' || cod`). Con
  `emp` nulo sale NULL, y `obra_label` lo cubre con un `COALESCE`.

## Nadie cruza ni agrega por `codigo_obra` sin `obra_id` (R10)

- **Barrido propio de `sql/`** (`GROUP BY`/`PARTITION BY`/`ON`/`USING` con `codigo_obra`). Todos
  llevan `obra_id`: `cierre/03`, `compras/03` ×2 y `retenciones/02`. Las excepciones son el
  ranking de `maestro/00_setup.sql` y el criterio de `03_obras.sql`, las dos intencionadas.
  `postventa/08` va por `empresa_id`.
- **Todas las lecturas de `stg.obras`** (mart `02_build_fact` ×4, cierre `02`/`04` ×2/`05`,
  maestro, personal, cobertura, huellas, mes-fase) unen por `obra_id`.
- **`v_pbi_dim_obra` y `v_pbi_cierre_cabecera`** leen `FROM stg.obras` sin agrupar: una fila por
  ficha y las tres columnas al final. Lo fija `test_f162_r10`.
- **`main.py`.** La única consulta a `stg.obras` por código es `_obra_de_stg`: con un código da la
  ficha por defecto y avisa de las demás; con la clave da esa ficha, y si no encuentra nada sale
  con 2. La usan los seis `inspect-*`/`list-master-cierre`. `find-obra` saca `emp`, `clave_obra` y
  `*`.
- **Fuera de alcance, declarado (desviación 4).** Los cinco comandos de compras y retenciones que
  filtran por código ya veían todas las fichas antes de F-162, porque leen de `raw`
  (`retenciones.movimientos`, vistas de compras), y no dependen de `stg.obras`. No es una
  regresión, es F-106.

## Guardas retiradas (R18, R19), sin relajar ninguna otra

- **`f102_r7` (hash y guarda de f073), los dos `f102_r18` y `f073_r26`.** Salen sustituidos por un
  comentario con su motivo, y `test_f162_r18` comprueba que el comentario está.
  `f102_r7_stg_no_lee_la_vista_de_fichas` sigue en pie.
- **Las adaptaciones no relajan nada:**
  - `f102_r8` exige la lista entera más `es_por_defecto`.
  - `f108` cambia la clave alternativa a `clave_obra` / (`empresa_id`, `codigo_obra`).
  - `f052_cobertura` pasa a exigir que los cuatro códigos de F-053 **no** estén.
  - `f052_cierre_excepciones` saca la 0606 de la línea base con su comentario. Las demás filas
    siguen.
- **`EXCEPCIONES_MAX` baja de 23 a 19.** Que las cuatro (0517, 0252, 0720, 0606) no salten se
  mide en el despliegue (design §7, paso 7).

## Diccionario v76 (R13-R17)

- **`R-EMPRESA-POR-DEFECTO`.** Su `ambito` llega a `stg`, `mart` y `cierre`. Dice todo lo que pide
  R13: el mismo código en varias empresas, la ficha `es_por_defecto` cuando no se dice empresa,
  avisar si esa ficha no tiene datos y otra sí, y no sumar fichas sin decirlo. Conserva
  «`empresa_id = 1`» (F-147 R7).
- **`R-UNIVERSO-OBRA`** ya no deduplica: dice 634 fichas para 585 códigos.
- **`R-CODIGO-POR-EMPRESA`** alcanza a las dos vistas.
- **P4, P6, P7, P10, P11 y P14** llevan la regla en `reglas_implicadas`. P9 cuenta fichas por
  defecto.
- **Presupuesto de F-147.** `PRESUPUESTO_MAX` y los topes de `test_f147_contenido.py` dan verde.
  La versión sube con su nota.
- **D3 está documentado para Power BI** en tres sitios: la ficha de `mart.yaml` (`obra_label`,
  línea 758), la cabecera y el `COMMENT` de la vista, y `azure-apps`.
- **`azure-apps` `f2cd5eb`.** Commit local, sin push. Toca solo `datamart_seg_anual.md`
  (+22/−3), avisa de que el texto de todos los segmentadores cambia y lo marca «SIN DESPLEGAR».

## Fase RED (C4 bis)

- **El commit T1 (`0ee7c93`) solo trae los dos ficheros de test.** El informe trae la salida real:
  83 failed y 6 passed en `cd81ea6`, y los motivos (`ModuleNotFoundError ficha_obra`,
  `ImportError _obra_de_stg`, `assert 23 == 19`…).
- **La sandbox, en tres estados:** viejo/viejo da 9 failed por `UndefinedColumn`; DDL nuevo con el
  03 viejo da 8 failed (`KeyError: 2759553`, se pierde la de Ruesma), y el código nuevo, 9 passed.
- **Los 6 que ya pasaban en RED** son guardas de lo que no debe cambiar. Lo acepto.

## Mutación (C4 bis)

- **No hay `progress/mutacion_F-162.md`.** La línea base de la herramienta exige el `.env`, igual
  que en F-157/F-158.
- **Recálculo:** `alcance_de_feature(base=main)` da 2 ficheros y 140 líneas; `generar_mutantes`
  da **42**, que coincide con el informe (12 en el dominio y 30 en `main.py`).
- **Ejecuté yo los 20 de la muestra** (semilla 20260820) con `aplicar_mutante`, sobre una COPIA en
  el scratchpad (RM4) y con `test_f162_fichas_por_empresa` + `test_f102`: **20 muertos y 0
  supervivientes, en 70 s.** Por ejemplo:
  - `frozen=True, slots=True` → `slots=False` muere.
  - `0 if … RUESMA else 1` → `1 if …` muere: no es equivalente.
  - `f[2] == codigo_o_clave` → `!=` muere.
  - `err=True` → `err=False` del aviso muere.
- **El superviviente que declara el informe** (`else 1` → `else 2`) es equivalente: solo importa
  que 0 vaya delante, y 1 o 2 ordenan igual. No cayó en la muestra. Ningún equivalente sale muerto
  (RM3) y no se quitó ninguna guarda (RM6).
- **El SQL no lo muta la herramienta.** Lo cubren la sandbox (oráculo = SQL en 9 casos) y los
  tests de texto r5-r7, de ahí la condición (2).

## Checkpoints

- **C1:** [x] condicionado a la puerta del líder; en el worktree solo falla el `.env` (informe,
  §init.sh). [x] Ficheros base del arnés presentes.
- **C2:** [x] Una sola `in_progress` (F-162). [x] Rama `feature/F-162-obra-duplicada-ruesma`.
  [x] `current.md` con la sesión de F-162 al día. [x] Sin features `done` nuevas.
- **C3:**
  - [x] Hexagonal: `ficha_obra.py` es dominio puro, sin imports de infraestructura; el SQL va en
    sus capas y el CLI en `main.py`.
  - [x] Cabecera con la ruta en los ficheros nuevos.
  - [x] Sin `print`, sin TODO y sin secretos (barrido del diff).
  - [x] Semántica de Sigrid y `ARCHITECTURE.md` al día.
- **C3 bis:** N/A, no entra ningún documento de fuera.
- **C4:**
  - [x] Requisitos con test (tabla abajo).
  - [x] Sin red ni BBDD: la sandbox se salta sin DSN y el CLI se prueba con un PG falso.
  - [x] MANUAL listado en `tasks.md` T12-T15 y en el informe.
  - [x] Dobles: el cursor falso solo implementa `execute`/`fetchall`, con la firma real.
- **C4 bis:**
  - [x] Rigor declarado.
  - [x] RED real.
  - [x] Cobertura 100 % (49/49), medida por mí.
  - N/A justificado: no hay informe de la herramienta (línea base sin `.env`). Lo sustituyen el
    recálculo y los 20 mutantes de la muestra, ejecutados por mí: 20/20 muertos.
  - N/A justificado: RM1, RM2, «tiempo» y cabecera «⚠ CAMPAÑA NO VÁLIDA», porque sin informe no
    hay nada que juzgar. El SHA verificado es 942b444, el HEAD.
  - N/A RM5, por ser `estandar`. [x] RM6.
  - [x] El superviviente del pre-análisis está analizado.
  - [x] «Evidencias» con los cuatro números.
- **C4 ter:** N/A, no hay `harness/rutas_sensibles.json`.
- **C5:** [x] T1-T11 en `[x]` con commits `F-162 Tn:` (16 commits). T12-T15 son MANUAL o de la
  puerta, pendientes y justificadas. [x] Árbol limpio. [x] `features.json` en `in_progress`.

## Cobertura requisito → test

| Req. | Test |
|---|---|
| R1-R4 | `test_f162_r1_*` (3), `r2`, `r3_*` (5), `r4`; sandbox `r1`, `r2`, `r3` |
| R5-R7 | `r5_*` (oráculo parametrizado), `r6`, `r7_*`; sandbox `r5` ×2 y `r7` (SQL = oráculo) |
| R8 | `r8_*` (3) y `f102_r8` |
| R9 | sin test propio: el diff no toca `stg/04-09` (verificado) y lo mide R22 en el despliegue |
| R10, R11 | `r10`, `r11_*` (3) |
| R12 | `r12_*` (11, CLI con PG falso) |
| R13-R17 | `r13`-`r17` (11), `f144`, `f147_presupuesto_contexto`, `f147_contenido` |
| R18, R19 | `r18` (parametrizado), `r19_*`, `f052_cobertura` |
| R20, R21 | `r20_*` (3), `r21_*` (2) |
| R22-R24 | MANUAL (T12-T14) |

## Observaciones (no bloquean; para el líder)

1. **T4 está en `[x]` pero su `EXPLAIN (ANALYZE)` en Azure no se hizo**: es el MANUAL 2 del
   informe, con el script ya preparado. Hay que pasarlo antes de T14 y anotarlo en
   `impl_F-162.md`. Si el plan barre `obrparpre`, se aceptan los +48 s y se apunta (design §3.1).
2. **El MANUAL 6 de `impl_F-162.md` da mal los códigos retirados.** Pone «0581, 0606, 0671, 0720»
   y son **0517, 0252, 0720 y 0606**. El paso 7 del design trae los buenos.
3. **La nota de `features.json` y `current.md` resume D1 como «el MISMO criterio en todas las
   fichas».** Lo implementado es lo que dice el design, D1 incluido: **fuera del seguimiento** vale
   `es_ficha_principal`, que sí usa `conext` 15 y los cierres. Hoy coinciden en las 925 fichas.
   Conviene corregir esa nota para que nadie lo lea como un criterio único.
4. **Los cinco comandos de compras y retenciones por código** (desviación 4) quedan para F-106.
   Conviene que su enmienda los nombre.

## Automejora (propuesta, no aplicada)

- **Que `CHECKPOINTS.md` C5 diga que una tarea con una verificación MANUAL dentro no se marca
  `[x]` hasta que se haga.** Lo pendiente se parte en su propia tarea MANUAL. Aquí T4 incluía el
  `EXPLAIN` en Azure y se marcó hecha sin él.
