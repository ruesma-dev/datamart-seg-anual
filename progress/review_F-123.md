<!-- progress/review_F-123.md -->
Revisión incremental desde 5f59062 (pasada 2) · la pasada 1 fue completa sobre `main...5f59062`

# F-123 · Review · la regla de orígenes del descompuesto

**Veredicto (pasada 2): APPROVED.** Los dos cambios requeridos están hechos y las
dos observaciones que pidió el líder (bloqueo en T16, sin vuelta atrás en T15)
constan en `current.md` y en `impl_F-123.md`. No hay regresiones.

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de
lo cambiado y mutación con supervivientes analizados. RM5, N/A por nivel.

## Pasada 2 (delta `5f59062..3b9c3cd`)

Un commit, `3b9c3cd` («F-123: correcciones de la review 1»), que solo toca
`progress/current.md`, `progress/impl_F-123.md` y `progress/mutacion_F-123.md`
(`git diff 5f59062 3b9c3cd --stat -- etl_sigrid main.py tests config` vacío).
**Ni código, ni SQL, ni tests, ni diccionario**: el alcance de mutación, la
cobertura y el sello (`5c3fb64e292fa14d`) no cambian, y nada de lo aprobado en la
pasada 1 queda invalidado.

- **Cambio 1, hecho.** `mutacion_F-123.md` trae ahora una fila por mutante con
  `fichero:línea`, el texto EXACTO original -> mutado (`⏎` = salto de línea;
  «línea borrada» en M04 y M11), el nº de fallos SIN `-x` y los tests que caen;
  la fila «SHA de HEAD medido» con el SHA completo
  (`8d49a5f93edde44217bdbaa162c8cf4c0a7927d3`), la base en segundos (5,7 / 3,3
  s), el tiempo (96 s) y «Workers: 1». «Evidencias» de `impl_F-123.md`: 96 s y
  **1 worker**.
  - **Comprobado**: las líneas citadas existen tal cual en HEAD (M03/M04/M10 en
    `02:147-151`, M13 `03:131`, M16-M18 `05:75-77`, M21 `descompuestos.py:58`).
  - **Reproducidas al pie de la letra cinco filas** con los pares del informe,
    en una copia (`git archive HEAD`) y sin `-x`: **M04 2, M08 1, M13 2, M17 2,
    M21 4 fallos**, y los MISMOS tests que nombra cada fila; base `280 passed, 3
    skipped` antes y después. Coinciden las cinco.
  - RM1: el SHA medido no es HEAD, pero todo lo posterior (`e293c34`, `5f59062`,
    `3b9c3cd`) solo toca `progress/` y `tasks.md`: alcance idéntico.
  - RM2: 21 × 4,6 s ≈ 96 s; 1 worker; media frente a base 5,7 s, coherente
    (cada mutante corre la batería entera sin `-x`). > 60 s: recálculo puro más
    las cinco filas, sin reejecutar la campaña entera.
  - El `git worktree` que dice haber usado no ha quedado colgado (`git worktree
    list` sin entradas suyas).
- **Cambio 2, hecho.** La sección F-123 de `current.md` dice «IMPLEMENTADA
  (`in_progress`), en review», sin las frases caducadas («T1-T22», «No se
  implementa…», «pendiente de PARADA 1», «sigue en `spec_ready`», «Abierto para
  la spec…»); lo que vale de historia queda en un párrafo marcado «Historia
  (caducada, no es el estado)». Y lista T13-T18 EN ORDEN con su comando exacto y
  lo que debe salir, como F-120: aviso, foto de antes (las dos `SELECT`), imagen
  y comprobación del tag (`az containerapp job show … -o tsv`), `build-
  descompuestos --sin-tope` + `apply-grants` desde el mismo commit, foto de
  después con testigos y R24, `publicar-diccionario` + reinicio del MCP.
- **Observación del bloqueo (T16), añadida** en `current.md` (punto 4) y en
  `impl_F-123.md` T16: `AccessExclusiveLock` sobre `lineas` (~4,7 M filas,
  validadas por el `ADD CONSTRAINT`) y `cuadre_partida` hasta el commit de `02`;
  el MCP y Power BI esperan; después, solo un `SELECT` de catálogo.
- **Observación de la vuelta atrás (T15), añadida** en `current.md` (punto 3) y
  en `impl_F-123.md` T15: tras la migración, volver a la imagen anterior exige
  revertir los dos `CHECK` (y las filas `MASTER_ESTUDIO`); si no, `CheckViolation`.
- **`bash harness/init.sh`** relanzado (el protocolo lo pide en cada pasada):
  exit 0, `ENTORNO LISTO`, **6.285 passed, 221 skipped** (38 min), `COBERTURA [OK] 100 %` (1/1), `TAMAÑO [OK]`.

## Pasada 1, resumen (detalle en `git show 909f14b:progress/review_F-123.md`)

Veredicto CHANGES_REQUESTED solo de papeleo: (1) la tabla de la campaña MANUAL
sin línea, texto exacto ni nº de fallos, SHA corto y sin workers; (2)
`current.md` sin las MANUAL con su comando y con frases caducadas. Todo lo demás
quedó verificado entonces, sin escrituras en Azure:
- **RED reproducida** (`git archive ee8fa3b`: 20 failed, 6 passed, 1 skipped).
- **«Obra con master 0» es el MISMO predicado** en `02` (`INSERT` de `ESTUDIO`),
  `05` (`WHERE` del cuadre) y lo que publica `03` (`_versiones_cargadas` con
  `fase_num = 0`, solo ámbito 8; su paso 4 borra versiones descargadas): R11 por
  construcción.
- **Migración**: un `DO` antes del primer `DELETE`/`INSERT`, guarda por tabla,
  `DROP CONSTRAINT -> UPDATE -> ADD CONSTRAINT`, sin `DROP`/`TRUNCATE` ni choque
  de PK, idempotente; **misma transacción** que el resto de `02`
  (`execute_sql_file` en un `cur.execute` con `autocommit=False`).
- **T8** (logs del PG16 local), **sello**, **mutación del arnés** (0, con control
  39 / 92 / 978) y **tests de F-097/F-120** sin aserciones perdidas.
- **Diccionario v40** (D1, D2, aviso de medición actual solo sin master 0) y
  **`azure-apps` `2288386`** (local, sin push).

## Checkpoints (estado tras la pasada 2)

**C1** [x] init.sh exit 0 (arriba) · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama de la feature · [x] la sección F-123
de `current.md` describe el estado real; la historia, marcada como tal (las
secciones antiguas del fichero son deuda previa que F-123 no amplía) · [x]
`history.md` sin cambios necesarios.
**C3** [x] hexagonal (dominio con stdlib, SQL en `sql/descompuestos/NN_*`) · [x]
primera línea con ruta · [x] sin `print`, TODOs, secretos ni dependencias · [x]
semántica: no mezcla ámbitos (ámbito 8 v0 frente a ámbito 3 fase 0) ni orígenes.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R21 con `test_f123_rN_*` en verde (R22-R24 son MANUAL) · [x] sin
red ni BBDD · [x] T13-T18 en `current.md` con su comando, lo que debe salir y el
ORDEN (imagen antes del build, con el porqué) · [x] no añade dobles.
**C4 bis** [x] rigor declarado · [x] RED con traza real, reproducida · [x]
cobertura `[OK] 100 %` (1/1; el SQL no lo mide la puerta) · [x] alcance y nº de
mutantes del arnés recalculados (0, con control) · [x] > 60 s (96 s): recálculo
más cinco filas reproducidas · [x] coste por mutante 96 × 1 / 21 = 4,6 s · [x]
sin «CAMPAÑA NO VÁLIDA» · [x] RM1: SHA completo, y lo posterior no toca el
alcance · [x] RM2 coherente · N/A RM5: nivel `estandar` · [x] RM6: ninguna
guarda quitada · [x] campaña MANUAL con línea, texto exacto y nº de fallos, dos
o más filas reproducidas (cinco) · [x] 0 supervivientes · [x] «Evidencias» con
los cuatro números y 1 worker · [x] ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T12 y T19 `[x]` con su commit `F-123 Tn:` (T13-T18 son MANUAL), y la
corrección en `3b9c3cd` · [x] árbol limpio · [x] `features.json` coherente.

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

R22-R24: MANUAL del humano (T14, T17), con su consulta en `current.md` e `impl`.

## Cambios requeridos

Ninguno. Para cerrar faltan las MANUAL del humano, T13-T18, en su orden: aviso,
foto de antes, imagen y tag del job, `build-descompuestos --sin-tope` +
`apply-grants`, foto de después con testigos y R24, y el diccionario v40 con el
reinicio del MCP. Sigue abierto, para el líder y fuera de F-123: `azure-apps`
dice aún «sin desplegar» de F-097 y F-120.

**Automejora (propuesta, no aplicada):** si la mutación del arnés da 0 y se hace
una campaña MANUAL, versionar su script en `progress/` o copiar sus pares al
informe (lo que hizo `3b9c3cd`): la evidencia reproducible vivía solo en el
scratchpad de una sesión.
