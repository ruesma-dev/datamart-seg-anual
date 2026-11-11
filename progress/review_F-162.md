Revisión completa (pasada 1), diff cd81ea6..942b444 (spec en b614db7, PARADA 1 en cd81ea6; merge-base con `main` 17b41ec)

<!-- progress/review_F-162.md -->
# F-162 · Review · el seguimiento lleva todas las fichas de obra, con `es_por_defecto`

**Veredicto: APPROVED**, condicionado a lo que solo puede hacer el líder en la copia con `.env`:
(1) `bash harness/init.sh` en verde sobre 942b444; (2) T12, `tests/test_f162_sandbox.py` con
`F162_SANDBOX_DSN`, sin `skip`; (3) el `EXPLAIN (ANALYZE)` de solo lectura de `03_obras.sql`
antes de desplegar (obs. 1). Si alguno sale rojo, el veredicto cae. T13/T14 son del humano.
**Rigor:** `estandar` (declarado): RED, cobertura ≥ 80 % de lo cambiado y mutación muestreada
(20, semilla 20260820). RM5 no aplica.

## Lo que verifiqué yo

| Qué | Resultado |
|---|---|
| F-162 + f102, f073, f108, f052 ×2, f147 ×2, en copia `git archive` | 490 passed, 13 skipped, 1 failed: `f147_r8` (`git ls-files` en una copia sin repo; artefacto, como en F-157) |
| `f147_contenido`, `f006_contexto`, `f144*` en el worktree | 112 passed (incluido `f147_r8`) |
| 23 ficheros que leen las vistas, el diccionario, `03_obras`, `maestro.obras` o `find-obra` | 2308 passed, 340 skipped, 0 failed |
| Cobertura de lo cambiado (`coverage` + `harness.alcance`, solo con `test_f162_fichas_por_empresa`) | **49/49 = 100 %** (22 dominio, 27 `main.py`) |
| `ruff` | nuevos limpios; tocados 71 avisos frente a 73 en cd81ea6, ninguno nuevo |

No corrí `init.sh` ni la suite entera (encargo: el worktree no tiene `.env`). Árbol limpio al acabar.

## El modelo del humano

- **R1/R2.** `03_obras.sql` conserva los filtros de hoy y quita `WHERE rn = 1` y el `JOIN` a
  `conext`. Las `rn = 1` de antes están contenidas en el universo nuevo, con las mismas
  expresiones de columna: **ningún `obra_id` publicado cambia ni pierde filas**.
- **R5/R6.** `ROW_NUMBER() ... = 1` por código: empresa 1, líneas DESC, `tiemod DESC NULLS
  LAST`, `obra_id DESC`; criterio a criterio con `clave_por_defecto`; sin `conext`.
- **`dudosas` con `<> 1`** (desviación 1): correcta. Con dos fichas de Ruesma, `NOT bool_or`
  haría que el SQL desempatase por `tiemod` y el oráculo por líneas. `lineas` se agrega antes de unir.
- **R8.** `COALESCE(so.es_por_defecto, vf.es_ficha_principal)` como última columna. El `LEFT JOIN`
  es por PK y no multiplica; `maestro` ya leía `stg`. Es lo que dicen R8 y D1 (obs. 3).
- **`clave_obra`** como en `v_obra_fichas` (`emp::text || '-' || cod`). Con `emp` nulo sale NULL y
  el `COALESCE` de `obra_label` lo cubre.

## Nadie cruza ni agrega por `codigo_obra` sin `obra_id` (R10)

- **Barrido propio de `sql/`** (`GROUP BY`, `PARTITION BY`, `ON`, `USING`): todos llevan `obra_id`.
  Solo el ranking de `maestro/00_setup` y el criterio de `03_obras` no, y son intencionados.
  `postventa/08` va por `empresa_id`.
- **Toda lectura de `stg.obras`** (mart, cierre, maestro, personal, cobertura, huellas, mes-fase)
  une por `obra_id`. Las dos `v_pbi_*` no agrupan.
- **`main.py`.** La única consulta por código es `_obra_de_stg`, que usan los seis comandos de
  R12. Con un código da la ficha por defecto y avisa de las demás; con la clave da esa ficha; si
  no encuentra nada sale con 2. `find-obra` muestra `emp`, `clave_obra` y `*`.
- **Fuera de alcance (desviación 4):** cinco comandos de compras y retenciones. Leen vistas sobre
  `raw`, que ya traían todas las fichas antes de F-162: no es regresión, es F-106.

## Guardas retiradas (R18, R19), sin relajar otras

- **Retiradas:** `f102_r7` ×2, `f102_r18` ×2 y `f073_r26`, cada una con su motivo en un
  comentario que vigila `test_f162_r18`. Sigue en pie `f102_r7_stg_no_lee_la_vista_de_fichas`.
- **Adaptadas, sin relajar:** `f102_r8` (lista entera + `es_por_defecto`), `f108` (claves
  nuevas), `f052_cobertura` (exige que NO estén los 4 de F-053), `f052_cierre_excepciones` (0606).
- **`EXCEPCIONES_MAX`** baja de 23 a 19. Que no salten se mide en el despliegue (design §7, paso 7).

## Diccionario v76 (R13-R17), D3 y `azure-apps`

- **`R-EMPRESA-POR-DEFECTO`.** Su ámbito llega a `stg`, `mart` y `cierre`. Cubre R13 entero:
  mismo código en varias empresas, la ficha por defecto, el aviso si esa ficha no tiene datos y
  no sumar fichas sin decirlo. Conserva `empresa_id = 1`.
- **`R-UNIVERSO-OBRA`** ya no deduplica: 634 fichas y 585 códigos.
- **`R-CODIGO-POR-EMPRESA`** alcanza a las dos vistas.
- **Preguntas:** P4, P6, P7, P10, P11 y P14 llevan la regla; P9 cuenta fichas por defecto.
- **F-147:** `PRESUPUESTO_MAX` y topes en verde. **D3.** El cambio de `obra_label` para Power BI está documentado en tres sitios: `mart.yaml`
  (l. 758), la cabecera y el `COMMENT` de la vista, y `azure-apps`.
- **`azure-apps` `f2cd5eb`.** Commit local sin push. Solo toca `datamart_seg_anual.md`, marcado
  «SIN DESPLEGAR», y avisa del cambio de texto de los segmentadores.

## Fase RED

- **El commit T1 (`0ee7c93`) solo trae tests.** El informe trae la salida real: 83 failed y 6
  passed en cd81ea6, con los motivos (`ModuleNotFoundError`, `ImportError _obra_de_stg`,
  `23 == 19`).
- **Sandbox en tres estados:** 9 failed por `UndefinedColumn`, después 8 failed (`KeyError:
  2759553`, se pierde la de Ruesma) y al final 9 passed.

## Mutación

- **No hay `progress/mutacion_F-162.md`:** la línea base exige el `.env`, como en F-157/F-158.
- **Recálculo:** `alcance_de_feature(base=main)` da 2 ficheros y 140 líneas, y `generar_mutantes`
  da **42**, igual que el informe.
- **Ejecuté yo los 20 de la muestra** (semilla 20260820), con `aplicar_mutante` sobre una COPIA en
  el scratchpad (RM4) y con `test_f162` + `test_f102`: **20 muertos, 0 supervivientes, 70 s**.
  Por ejemplo, mueren `slots=True` → `False`, `0 if … RUESMA` → `1 if …` (no es equivalente),
  `f[2] == codigo_o_clave` → `!=` y `err=True` → `False`.
- **El superviviente del informe** (`else 1` → `else 2`) es equivalente: 1 o 2 ordenan igual
  detrás del 0. No cayó en la muestra. RM3 y RM6 limpios.
- **El SQL no lo muta la herramienta:** lo atan la sandbox (oráculo = SQL) y r5-r7, de ahí la
  condición (2).

## Checkpoints

- **C1** [x] condicionado a la puerta del líder (en el worktree solo falla el `.env`); arnés completo.
- **C2** [x] una sola `in_progress`, rama correcta, `current.md` al día, sin `done` nuevas.
- **C3** [x] hexagonal (`ficha_obra.py` dominio puro; SQL en su capa; CLI en `main.py`); cabecera
  con ruta; sin `print`, TODO ni secretos; semántica Sigrid y `ARCHITECTURE.md` al día.
- **C3 bis** N/A: no entra ningún documento de fuera.
- **C4** [x] requisito → test (tabla); sin red ni BBDD (sandbox con `skip`, PG falso en el CLI);
  MANUAL en T12-T15; el doble de cursor solo tiene `execute`/`fetchall` con la firma real.
- **C4 bis** [x] rigor declarado; [x] RED real; [x] cobertura 100 % medida por mí. N/A justificado:
  sin informe de la herramienta (línea base sin `.env`), lo sustituyen el recálculo y los 20
  mutantes ejecutados por mí (20/20); por lo mismo no hay RM1, RM2, tiempo ni cabecera «⚠ CAMPAÑA
  NO VÁLIDA» que juzgar (SHA verificado: 942b444). N/A RM5 (`estandar`). [x] RM6, superviviente
  analizado, «Evidencias» completas.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] T1-T11 en `[x]` con 16 commits `F-162`; T12-T15 MANUAL o puerta (justificado);
  árbol limpio; la feature sigue `in_progress`.

## Cobertura requisito → test

| Req. | Test |
|---|---|
| R1-R4 | `test_f162_r1_*`, `r2`, `r3_*`, `r4`; sandbox `r1`, `r2`, `r3` |
| R5-R7 | `r5_*` (oráculo), `r6`, `r7_*`; sandbox `r5` ×2 y `r7` (SQL = oráculo) |
| R8 | `r8_*`, `f102_r8` |
| R9 | sin test propio: el diff no toca `stg/04-09` (verificado) y lo mide R22 |
| R10-R12 | `r10`, `r11_*`, `r12_*` (11, CLI con PG falso) |
| R13-R17 | `r13`-`r17`, `f144`, `f147_presupuesto_contexto`, `f147_contenido` |
| R18-R21 | `r18`, `r19_*`, `f052_cobertura`, `r20_*`, `r21_*` |
| R22-R24 | MANUAL (T12-T14) |

## Observaciones (no bloquean; para el líder)

1. **T4 está en `[x]` sin su `EXPLAIN (ANALYZE)` en Azure.** Es el MANUAL 2 del informe y el
   script ya está preparado. Pasarlo antes de T14 y anotarlo; si barre `obrparpre`, se aceptan los
   +48 s (design §3.1).
2. **El MANUAL 6 de `impl_F-162.md` da mal los códigos.** Pone «0581, 0606, 0671, 0720» y son
   0517, 0252, 0720 y 0606.
3. **La nota de `features.json` y `current.md` resume D1 como «el MISMO criterio en todas las
   fichas».** Lo implementado es lo del design D1: fuera del seguimiento vale
   `es_ficha_principal`, que sí usa `conext` 15 y los cierres (hoy coinciden en las 925 fichas).
   Corregir la nota.
4. **La enmienda de F-106** debería nombrar los cinco comandos de la desviación 4.

**Automejora (propuesta, no aplicada).** C5 de `CHECKPOINTS.md`:** una tarea que lleva dentro una verificación MANUAL no se marca `[x]`
  hasta hacerla; lo pendiente va a su propia tarea MANUAL (caso T4).
