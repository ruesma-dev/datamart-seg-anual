<!-- progress/review_F-038.md -->
Revisión incremental desde e9c5507 (Fase 2 · pasada 1): delta `e9c5507..ada7bec` (T11-T19)

# F-038 · Review · Fase 2 · pasada 1 · líneas, objetivo y firmas

**Veredicto: CHANGES_REQUESTED.** Código limpio y suite en verde, pero
contrastado en Azure el SQL publica `casa_base` NULL («sin descompuesto») en
**35.701** líneas OBJETIVO que la spec publica «no casa», y la desviación 3 deja
«casa con la ABC» un 12,7 % por debajo de la previsión.

**Fase 1**: APPROVED (pasadas 1 y 2), mergeada (`dda0dc5`) y desplegada. Su
review, íntegra, está en `progress/review_F-038_fase1.md` (movida para caber en
el tope de 140 líneas; no se ha borrado nada).

**Rigor:** `estandar`, declarado: fase RED, cobertura ≥ 80 % y mutación.

## Lo verificado por mí

- **Contra Azure, SOLO LECTURA** (`psycopg` directo, `transaction_read_only =
  on`, sin el cliente del ETL). El SQL de `09` tal cual, con la temporal como
  CTE y `fn_porcentaje_dto` en línea:
  - `EXPLAIN` de los SELECT de las tres tablas grandes: **OK** (columnas y
    tipos existen; `confir.fec` `integer` entra en `fn_sigrid_date(bigint)`).
    La D4 entera tarda 98-124 s: cabe en los +2-3 min previstos.
  - **Paridad del `dto`**: 453 textos en 786.864 líneas, 94.621 con %; SQL
    contra `parse_porcentaje_dto`: **0 discrepancias**, ninguno fuera del patrón.
  - **D4 con el SQL de la rama** (84.084 líneas OBJETIVO con %; spec 83.329):

| `base_regla` · `casa_base` | líneas | nota |
|---|---|---|
| ABC · cierto con la ABC | 9.955 | previsión 11.409 (**−12,7 %**) |
| ABC · cierto con anterior | 5.858 | 5.370 PRE_ABC + 474 MASTER_ESTUDIO + 14 ESTUDIO (prev. 5.468) |
| ESTUDIOS · cierto | 7.548 | prev. 7.386 |
| **Total cierto** | **23.361 (27,8 %)** | prev. 24.263 (29,1 %): −3,7 % |
| ABC / ESTUDIOS · falso | 14.275 / 10.747 | 1.064 de ABC casarían por precio en una versión admitida |
| ABC / ESTUDIOS · **NULL** | 11.624 / 24.077 | solo 83 / 6 sin descompuesto en ninguna versión |

  - **Buscando «el que case» por precio**, sin preferir `dncpro_id`: casan
    **24.425**, la cifra de la spec más el crecimiento. La spec midió por
    precio; R29 dice `dncpro_id` primero.
  - **Ejemplos**: A1 `ABC v3` 3.482 cierto · A2 `ABC v4` 131.926,58 cierto · B1
    `MASTER_PRE_ABC v2` 10,80 cierto · B2 `MASTER_PRE_ABC v2` 98 cierto · C1
    falso, sin elemento (nunca la posterior) · C2 `ABC v3` 4,20 falso · 0696:
    939265 y 952250 `ABC v3` 69,70 cierto; **962172 (26,60) NULL**, y la T25 de
    `current.md` espera **falso**.
- **D4 en el SQL = la decisión**: nunca posterior (`fase_num <= ob.fase_abc`,
  solo `es_primera_abc` o Estudios/PRE_ABC), sin ABC solo Estudios, desempate
  `casa DESC, fase_num DESC`. ESTUDIO y PLANIF_JO traen `es_primera_abc` NULL
  (`descompuestos/02_lineas_coste.sql:205`) y los `OR` los tratan bien.
- **Desviaciones (impl §2)**: 1 **aceptada**. 2 **aceptada**: ESTUDIO y
  MASTER_ESTUDIO nunca conviven en una partida (`02_lineas_coste.sql:170-211`) y
  su `fase_num` 0 precede a toda ABC; aporta 488 líneas. 3: cambio 2. 4: cambio
  1. 5 **comprobada**: `execute_sql_file` sin parámetros es un solo `execute` en
  conexión no-autocommit con `commit` al salir (`postgres_client.py:666-684`,
  `1454-1456`), como `_lote` de `descompuestos/03`. 6-9 **aceptadas**.
- **Lector cruzado de `descompuestos`**: declarado en la cabecera de `09`, el
  docstring del step, `ARCHITECTURE.md` y la ficha; sin `depends_on` a
  propósito y con su fallo nombrado en la MANUAL T21.
- **`comparativo_firmas`**: toda fila de `confir` con `conide` en `com` (los
  reenvíos son filas; 5.375 en la ficha), `pendiente` = definición de
  `n_firmas_pendientes`, `ord` = 0 y F-085 en la ficha; ni `deffir` ni `dbo.log`.
- **Tests de otras features**: `f047` pasa de «el último cuenta `comparativos`»
  a «los dos últimos, `comparativos` y `comparativo_oferta_lineas`»; `f123` r1
  de «nadie» a «exactamente `{09}`»; `f073`, `f080`, `f079` y `R-SIGRID-CON`
  solo añaden. **Ninguno rebaja nada.** `features.json`: el delta no lo toca.
  **`azure-apps` `f3dca46`**: Fase 1 desplegada y Fase 2 «sin desplegar»; sin push.

## Mutación

- **Arnés recalculado, no reejecutado** (3.665 s, > 60 s): `harness.alcance` 84
  líneas (dominio 65, step 19), `generar_mutantes` **13**, como el informe.
  **RM1**: medido `d2d1d34`; después solo cambian `progress/` y `tasks.md`.
  **RM2**: base 419,4 s, media 281,9 s × 1 worker; 13 × 281,9 = 3.665 s.
  **RM3**: ninguno de los 13 es equivalente. **RM6**: ninguna guarda quitada.
- **SQL manual reproducido** en un worktree desechable de HEAD (borrado; `git
  status` limpio), base 68 passed: **M33, M36 y M47 → 1 fallo** cada uno, como
  la tabla. **M47 es equivalente en ejecución** (cada fichero abre y cierra su
  conexión: la temporal muere igual sin `ON COMMIT DROP`) y muere porque el test
  fija el texto. No delata suite roja ni informe falso: es el límite que el
  propio informe declara. No bloquea (la campaña exigida es la del arnés).

## Checkpoints

**C1** [x] `init.sh`: 6.786 passed, cobertura `[OK]` 14/14; su única KO fue
`PUERTA TAMAÑO` por este informe en borrador (168); recortado, `harness.tamano` exit 0.
[x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama `feature/F-038-comparativos` · [x]
`current.md` es el estado real · [x] `history.md`: no aplica aún.
**C3** [x] hexagonal (dominio solo `re`/`Decimal`; SQL en `sql/compras/09_…`) ·
[x] primera línea con la ruta · [x] sin `print` de depuración, secretos ni
dependencias · [ ] **semántica**: `casa_base` NULL no dice lo que la spec
decide (cambio 1).
**C3 bis** N/A: no toca `docs/referencia/`. **C4 ter** N/A: sin `rutas_sensibles.json`.
**C4** [x] R25-R35 con `test_f038_rN_*` en verde; R36 MANUAL por naturaleza
(T22) · [x] sin red ni BBDD · [ ] MANUAL en orden y con comando, pero **la 4 y
la T25 prevén cifras que el SQL no da** (cambio 3) · [x] ningún doble nuevo.
**C4 bis** [x] rigor declarado · [x] RED con traza real T11-T17 · [x] cobertura
`[OK]` 14/14 · [x] alcance y mutantes recalculados · [x] > 60 s: recálculo y
tres filas reproducidas · [x] coste por mutante coherente · [x] sin «CAMPAÑA NO
VÁLIDA», «Sin veredicto» 0 · [x] RM1 · [x] RM2 · N/A RM5: `estandar`, sin
supervivientes · [x] RM6 · [x] SQL manual con línea, texto y nº de fallos · N/A
análisis de supervivientes: no hay · [x] «Evidencias» con workers · [x] ningún
N/A sin motivo.
**C5** [x] T11-T19 `[x]`, commits `F-038 T11`…`T19` · [x] árbol limpio · [x]
`features.json` refleja el estado real.

## Cobertura requisito → test (`tests/test_f038_*.py`)

R25 `r25_lineas_*` (3) · R26 `r26_*` (4, + F-047) · R27 `r27_*` (7) + mi
paridad real · R28 `r28_*` (2) · R29 `r29_*` (9) · R30 `r30_*` (4) · R31
`r31_*` (7) · R32 `r32_lineas_*` · R33 `r33_*` (5) · R34 `r34_*` · R35
`r35_*` (3) · R36 MANUAL T22.

## Cambios requeridos

1. **`casa_base` NULL solo «sin descompuesto»** (`09_comparativos_detalle.sql:177-181`,
   `:200`). `con_descompuesto` sale de `candidatas`, que ya filtra D4: una
   partida con descompuesto solo en versiones no admitidas sale NULL. Son 35.701
   líneas y **35.612 sí tienen descompuesto**; la spec las publica «no casa»
   (`spec_F-038.md` §7: «las otras 59.066 se publican "no casa"»; «sin
   descompuesto en la partida: 3») y tu T25 espera `falso` en la 962172. Calcula
   `con_descompuesto` contra `descompuestos.lineas` de su obra y partida **sin**
   filtro de versión; ajusta el `nulo_significa` de `casa_base`, el informe §2.4
   y su test. Si se prefiere la lectura actual, que la decida el humano y conste.
2. **Desviación 3, decisión del humano antes del merge** (vía líder): con
   `dncpro_id` primero (R29) casan 23.361 y «con la ABC» 9.955; por precio (como
   se midió la spec que aprobó D4), 24.425. 1.064 líneas casan por precio en una
   versión admitida y salen «no casa», y la MANUAL 4 pararía por su propia regla
   del 5 %. Lo decidido, en `impl` §2 y, si cambia, en `elemento` (`09:145-159`).
3. **Cifras con lo que el SQL produce**: la MANUAL 4 y la T25 de `current.md`
   (separando cierto / falso / NULL; 962172 según lo que resulte de 1) y el
   «Medido: casan 24.263 de 83.329» de las fichas de `comparativo_oferta_lineas`
   y `comparativo_objetivo`: que diga qué regla se midió o lleve la cifra de la
   regla publicada.

## Para el líder y el humano (no bloquea)

- **Automejora (propuesta, no aplicada)** de RM3 en `reviewer.md`: «en una
  campaña MANUAL cuyos tests fijan el TEXTO del SQL, un equivalente muerto no
  invalida la campaña: se anota como límite». M47 lo enseña.
