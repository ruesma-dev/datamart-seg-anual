<!-- progress/review_F-123.md -->
Revisión completa (pasada 1) · `main...5f59062` (merge-base `d4f58ea`)

# F-123 · Review · la regla de orígenes del descompuesto

**Veredicto (pasada 1): CHANGES_REQUESTED.** El código, el SQL, la migración y la
documentación están bien y hacen lo que dictó el humano. Falla papeleo que
`CHECKPOINTS.md` exige de forma explícita: la tabla de la campaña MANUAL de
mutación no es reproducible desde el propio informe (C4 bis), y `current.md` no
lista las MANUAL con su comando y arrastra frases caducadas de la spec (C2, C4).
Son dos arreglos de documentación: ni código ni mediciones caras.

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de
lo cambiado y mutación con supervivientes analizados. RM5, N/A por nivel.

## Lo verificado por mí (sin escrituras en Azure)

- **RED reproducida**: `git archive ee8fa3b` en el scratchpad -> `20 failed, 6
  passed, 1 skipped` (el de `azure-apps` se salta fuera del árbol; dentro son
  los 21 rojos de la traza).
- **«Obra con master 0» es el MISMO predicado en los tres sitios**: `NOT EXISTS
  (_versiones_cargadas v WHERE v.obra_id = … AND v.fase_num = 0)` en el `INSERT`
  de `ESTUDIO` de `02` y en el `WHERE` de `05`; `03` solo publica `MASTER_ESTUDIO`
  para filas de esa tabla con `fase_num = 0` (`_atributos`) y su paso 4 borra las
  líneas de versiones ya no cargadas. `_versiones_cargadas` es solo ámbito 8 (PK
  `obra_id, fase_num`). R11 se cumple por construcción; el único transitorio
  (versión 0 aplazada por el tope) está declarado en design §8.
- **Migración (02)**: un solo `DO` tras los `CREATE` y antes del primer
  `DELETE`/`INSERT`; guarda por tabla sobre `pg_get_constraintdef`; orden `DROP
  CONSTRAINT -> UPDATE -> ADD CONSTRAINT` correcto; sin `DROP`/`TRUNCATE` de
  tablas ni choque de PK. **Misma transacción**: `execute_sql_file` manda el
  fichero entero en un `cur.execute` sobre `connection()` (`autocommit=False`,
  `commit()` al salir, `rollback()` si falla: `postgres_client.py:666-684`,
  `:1454`). Después, la guarda es un `SELECT` de catálogo: no toma
  `AccessExclusiveLock` cada noche (a diferencia del `ADD COLUMN` de F-120).
- **T8**: `t8/t8_sin_tope.log` del scratchpad dice lo que el informe (build 2 con
  0 versiones y los mismos oid de `CHECK`, R11 = 0, testigos 0726/0713, md5 de lo
  intocado iguales, `CheckViolation` con el 03 de `main`).
- **Sello** en HEAD: `sello_de_troceado()` = `5c3fb64e292fa14d`.
- **Mutación del arnés**: `alcance_de_feature("F-123")` -> 3 ficheros, 16
  líneas; `generar_mutantes` -> **0**. **Control** sin la exclusión de alcance:
  39 / 92 / 978 mutantes. El cero es legítimo (cadenas y docstrings).
- **Campaña manual, tres filas reproducidas** en una copia (`git archive HEAD`)
  con los textos exactos de `t8/mutacion_sql.py` y SIN `-x`: base `280 passed, 3
  skipped`; M04 -> 2 fallos (`r15[lineas]`, `r16`); M08 -> 1 (`r9_r11`); M17 ->
  2 (`r10`, F-097 `r23`); base intacta al restaurar. Muertos reales.
- **Tests reescritos de F-097/F-120**: ninguna aserción se pierde sin sustituta.
  F-097 `r12`, `r17`, `r21` cambian el literal; `r23` GANA la del `WHERE` de 05;
  `r24` pasa a 4 vistas. F-120 `r25` cambia «MASTER_INICIAL solo existe…» por
  «sin master 0» + `MASTER_ESTUDIO` y endurece la negativa; `r26` baja a `>= 39`,
  pero `test_f123_r18` fija `== 40`.
- **Diccionario v40**: `R-DESCOMPUESTO-ORIGEN` con la fase viva y la regla (D1),
  `v_pbi_master_estudio` en `ambito` y con ficha de 21 columnas (D2), el aviso
  «medición ACTUAL» solo para obras sin master 0. `MASTER_INICIAL` sobrevive solo
  en la cabecera comentada de `00_global.yaml` y dentro del `DO`.
- **`azure-apps` `2288386`**: orígenes, vista nueva, lo que rompe y el orden del
  despliegue. Local, sin push.

## Checkpoints

**C1** [x] init.sh exit 0 (abajo) · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama de la feature · [ ] la sección F-123
de `current.md` se contradice: «IMPLEMENTACIÓN TERMINADA» arriba y, debajo, «29
requisitos, T1-T22», «No se implementa hasta que el humano la apruebe»,
«pendiente de PARADA 1», «sigue en `spec_ready`» (cambio 2) · [x] `history.md`.
**C3** [x] hexagonal (dominio con stdlib, SQL en `sql/descompuestos/NN_*`) · [x]
primera línea con ruta · [x] sin `print`, TODOs, secretos ni dependencias · [x]
semántica: no mezcla ámbitos (ámbito 8 v0 frente a ámbito 3 fase 0) ni orígenes.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R21 con `test_f123_rN_*` en verde (R22-R24 son MANUAL) · [x] sin
red ni BBDD · [ ] T13-T18 NO están en `current.md` con su comando: remite a
`impl_F-123.md` (F-120 sí las listó) (cambio 2) · [x] no añade dobles.
**C4 bis** [x] rigor declarado · [x] RED con traza real, reproducida · [x]
cobertura `[OK] 100 %` (1/1; el SQL no lo mide la puerta) · [x] alcance y nº de
mutantes recalculados (0, con control) · [x] > 60 s (241 s): no se reejecuta
entera, sí tres filas · [x] coste por mutante 241 × 1 / 21 = 11,5 s, base 4-8 s
medida por mí: coherente · [x] sin «CAMPAÑA NO VÁLIDA» · [ ] RM1: SHA corto
`8d49a5f`, no el completo (lo medido sí es lo revisado: `e293c34` y `5f59062`
solo tocan `progress/` y `tasks.md`) (cambio 1) · [x] RM2: 21 × 11,5 ≈ 241 · N/A
RM5: nivel `estandar` · [x] RM6: ninguna guarda quitada · [ ] **campaña MANUAL**:
la tabla no trae línea, ni texto exacto original -> mutado, ni nº de fallos;
describe con palabras («sin el UPDATE…», «sin `factor`») y los textos exactos
solo viven en un script del scratchpad, sin versionar (cambio 1) · [x] 0
supervivientes · [ ] «Evidencias» sin el nº de workers (cambio 1) · [x] ningún
N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T12 y T19 `[x]` con su commit `F-123 Tn:` (T13-T18 son MANUAL) ·
[x] árbol limpio · [x] `features.json` coherente (`in_progress`).

## Cobertura requisito -> test (`tests/test_f123_origenes.py`)

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1 | `r1_nadie_fuera_*` | R12 | `r12_sin_objeto_ni_estado_nuevo` |
| R2 | `r2_el_estado_*_intacto` | R13 | `r13_vistas_la_de_siempre_igual` |
| R3 | `r3_planif_jo_*` (huella) | R14 | `r14_vistas_la_nueva_*`, F-097 `r24` |
| R4 | `r4_master_0_*`, F-097 `r17`, `r21` | R15 | `r15_migracion_*` (x3) |
| R5 | `r5_ningun_sql_*` | R16 | `r16_migracion_idempotente` |
| R6 | `r6_dominio_*`, `r6_los_dos_check_*` | R17 | `r17_el_sello_cambia_*` |
| R7 | `r7_elementos_*` | R18 | `r18_diccionario_version_40` |
| R8 | `r8_estudio_igual_*` (huellas) | R19 | `r19_*_fase_viva` |
| R9, R11 | `r9_r11_estudio_excluye_*` | R20 | `r20_*` (2), F-120 `r25` (x3) |
| R10 | `r10_cuadre_*`, F-097 `r23` | R21 | `r21_docs_*` (3) |

R22-R24: MANUAL del humano (T14, T17), con su consulta en `impl_F-123.md`.

## Cambios requeridos

1. **`progress/mutacion_F-123.md`, tabla (líneas 38-60).** Una fila por mutante
   con `fichero:línea`, el **texto exacto original -> mutado** (los pares de
   `MUTANTES` en `t8/mutacion_sql.py`) y el **nº de fallos** de la suite SIN `-x`
   (mis tres: M04 2, M08 1, M17 2). Añadir la fila «SHA de HEAD medido» con el
   SHA completo (`8d49a5f93edde44217bdbaa162c8cf4c0a7927d3`) y la línea base en
   segundos. En «Evidencias» de `progress/impl_F-123.md` (líneas 206-216), el nº
   de workers (1, en serie); el tope de `impl` es 220 y va por 218.
2. **`progress/current.md`, sección F-123 (líneas 15-84).** (a) T13-T18 con su
   comando exacto y lo que debe salir, EN ORDEN (aviso; foto; imagen y tag del
   job; `build-descompuestos --sin-tope` + `apply-grants` desde el mismo commit;
   foto de después, testigos y R24; `publicar-diccionario` + reinicio del MCP),
   como F-120. (b) Quitar o marcar como historia las frases caducadas de C2 y el
   «Abierto para la spec: respaldo por obra o por partida…».

## Observaciones (no bloquean)

- **Bloqueo en la migración**: la primera vez toma `AccessExclusiveLock` sobre
  `lineas` (~4,7 M filas, que el `ADD CONSTRAINT` valida) y `cuadre_partida`
  hasta el `commit` de TODO `02`: el MCP y Power BI esperan. Es una vez y T16 va
  fuera de la nocturna; merece una línea en T16 (o `NOT VALID` + `VALIDATE`).
- **Sin vuelta atrás de imagen**: tras la migración, la imagen anterior falla
  (`CheckViolation`, visto en T8) hasta revertir los `CHECK`. Decirlo en T15.
- **`azure-apps`** dice aún «sin desplegar» de F-097 y F-120: para el líder.

## init.sh

Relanzado en `5f59062`: exit 0, `ENTORNO LISTO`, **6.285 passed, 221 skipped** (15 min 53 s), `PUERTA COBERTURA [OK] 100,0 %` (1/1), `PUERTA TAMAÑO [OK]`.

**Automejora (propuesta, no aplicada):** si la mutación del arnés da 0 y se hace
una campaña MANUAL, versionar su script en `progress/` o copiar sus pares al
informe: hoy la evidencia reproducible vivía solo en el scratchpad de una sesión.
