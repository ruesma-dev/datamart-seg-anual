<!-- progress/review_F-150.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` (merge-base `a80bb1b`) · HEAD `6efddfe`

# F-150 · Review · la receta de la caja (fase 1)

**Veredicto: RECHAZADO (CHANGES_REQUESTED)**, por UN solo punto de papeleo de C4: las
verificaciones MANUAL de T15 no están en `progress/current.md` con su comando exacto. El código,
el SQL, la ingesta, el diccionario, `azure-apps` y la campaña de mutación están bien y verificados
(ver abajo). Lo aprobado aquí vale para la pasada 2, que solo tiene que mirar el delta.

**Nivel de rigor:** `estandar`, declarado en `features.json`. Exige fase RED en los requisitos
centrales, cobertura de lo cambiado ≥ 80 % y campaña de mutación con los supervivientes analizados.

## Cambios requeridos

1. **`progress/current.md`, sección «2026-10-28 · F-150» (líneas 12-22)** (C4, «MANUAL con su
   comando exacto»): hoy es una línea («imagen, `ingest` de `iva` y `dvf`, build,
   `publicar-diccionario` v63, reiniciar `mcp-bbdd`, R30 y R31»), y `impl_F-150.md` §6 tampoco trae
   comandos. Hay que listar T15 en orden y con su orden exacta, como la sección de F-140 del mismo
   fichero (líneas 104-127; F-140 se rechazó en su pasada 1 por esto mismo). Como mínimo:
   - el tag de vuelta atrás (`r20261026-2111`), el build de la imagen, `infra/85_update_job.ps1
     -Tag <nuevo>` y la comprobación de que el job corre ESA imagen;
   - `python main.py ingest --table iva --full` y `--table dvf --full` ANTES de
     `python main.py build-tesoreria`, con su duración;
   - las consultas de R30, escritas (18.997 partidas, ~132,4 / ~143,3 M EUR, fuentes, IVA y
     retención ≥ 96 % en 19 obras, hueco ~15,69);
   - `publicar-diccionario` solo con la imagen ya en el job; `check-diccionario`,
     `check-declarados` y `check-unicidad`; reinicio de `mcp-bbdd`;
   - R31 en una conversación nueva (una obra a 1,19 y otra mixta).

   Sin secretos: el host va como `<host>`.

**Recomendaciones que no bloquean:**

- `impl_F-150.md` §1 pone `infrastructure/config/hipotesis_caja_yaml.py` entre los ficheros de
  producción, pero no está en el diff (no hacía falta tocarlo).
- `proyeccion_caja.py:498`, `par[1] == par[1]`: es una guarda contra NaN sin comentario que lo
  explique. Una línea que lo diga evita que alguien la tome por un error.
- Al integrar, `BACKLOG.md` choca con `main` (`7aabb13`). Es un fichero generado: se regenera.

## Cómo se ha verificado (solo lectura; ni Azure ni Sigrid se escriben)

- **`bash harness/init.sh` en esta pasada:** **verde**, exit 0, «ENTORNO LISTO»: 9.645 passed, 266 skipped (5.817 s); cobertura `[OK]` 100 % (143/143); tamaño OK.
- **SQL ejecutado de verdad:** el `sandbox_f150.py` del implementer, vuelto a correr sobre un
  `postgres:16` desechable lanzado por mí con el SQL de HEAD: **66 OK, 0 fallos**. El oráculo es el
  dominio. Cubre `00` aplicado dos veces, `06`, `07` (con la guarda D6) y `08`. Contenedor borrado.
- **Azure, solo lectura** (`filas_solo_lectura`):
  - las 21 obras de VENTA tienen un `cenide` propio, ni 0 ni compartido, así que el hueco no
    cuenta dos veces una factura;
  - las 19.005 partidas VENTA casan con `raw.obrparpar.ide`, y 0 son de otra obra;
  - existen las columnas fuente (`obr.ivaide`, `obrctr.coestr`/`ivaide`, `obrparpar.ctride`,
    `stg.presupuesto`);
  - `raw.iva` y `raw.dvf` aún no existen en Azure. Es lo esperado: llegan en T15.
- **Sigrid** (`azure-apps/sigrid_tablas.md`): `dvf` tiene las 9 columnas de la lista blanca y ni
  `dvf` ni `iva` tienen `tiemod`, como midió en vivo el implementer.
- **El código frente a la spec**, leído línea a línea:
  - `coestr` se lee por líneas `\r?\n` y por CÓDIGO; `RET*` va aparte y no suma; `COEF_DESADJ` va
    en cascada; un código desconocido o un valor no numérico fallan cerrado. Python y SQL son
    gemelos, incluido un `\r` suelto;
  - fuente del coeficiente: CONTRATO > 9 > 11 > SIN; la guarda D6 salta antes del `TRUNCATE`;
  - el hueco es neto por obra, con `GREATEST(0, …)`, `MEDIA_OBRA` (1 si la obra no tiene ningún
    coeficiente) y el IVA y la retención por el peso de cada contrato;
  - H12 SIGRID sale de la ficha de la obra; un MANUAL lo pisa.
- **Catálogo:** `cargar_hipotesis_caja()` da **27 hipótesis y 0 errores**, con los pasos de §6,
  los perfiles H03/H08/H24/H25, H14 `MENSUAL`, H20 `FIN_MES_ALBARAN` y H26/H27 como R24; ninguna
  validada. Los textos de H10, H12, H13, H15 y H20 son los de §6.
- **Reglas de producción:**
  - sin secretos: el barrido del diff solo encuentra el `127.0.0.1` local;
  - ni `DROP` ni `GRANT` (solo `ON COMMIT DROP` de tablas temporales);
  - ni `_des_texto` ni `_versiones_cargadas` aparecen en el diff;
  - `objetos_pendientes.yaml` sigue vacío y es coherente: lo nuevo son dos tablas `raw` de la
    ingesta y dos funciones de `00`.
- **Diccionario:** v63; fichas de `raw.iva` y `raw.dvf`; columnas nuevas con `significado` y
  `nulo_significa`; `R-CAJA-HIPOTESIS` remite a la receta y `R-VENTA-COEFICIENTES` cubre las tres
  `devengo_*`.
- **`azure-apps` `044beef`** (local, limpio): recoge `iva`, la cabecera de `dvf`, las 80 tablas, la
  lectura de `stg.presupuesto`, las columnas y funciones publicadas, la guarda D6, el despliegue
  y «SIN DESPLEGAR».
- **Tests de F-140 modificados:** solo se ajustaron recuentos (23 a 27, 78 a 80) y se pasó a
  `>= 2` / `>= 62` donde F-150 crece; los de F-150 fijan los valores exactos.

## Mutación (C4 bis)

- **Recálculo puro:** **329 líneas en 4 ficheros y 95 mutantes**, igual que el informe. La muestra
  (semilla `20260820`) contiene el superviviente (`:227`) y los dos timeouts (`:485`, `:498`), con
  el mismo texto original → mutado.
- **Campaña no reejecutada:** 15.325,8 s según el informe, por encima del umbral de 60 s.
- **RM4, sobre una copia (`git archive`, ya borrada):**
  - con `> 3` en `:227` falla `test_f150_r7_una_linea_de_solo_tres_campos_se_lee_como_el_sql`
    (1 failed / 40 passed), y sin el mutante pasan 41;
  - `:485` (`or valor`) y `:498` (`par[2]`) también mueren.
- **RM1:** medido en `e85a3d8`. Hasta HEAD no cambia nada de `etl_sigrid/`, así que el alcance es
  el mismo.
- **RM2:** base de 1.265 / 1.281 s y media de 766,3 s con 2 workers, es decir, 1.532 s reales por
  mutante, del orden de la base. `20 × 766,3` = 15.326, el tiempo total. Es coherente.
- **RM3:** ningún equivalente sale muerto. Lo comprobé en `:247` (`otros`) y `:468` (`1 <`): los
  matan casos que existen en los tests (`COEF_RECCC`, porcentajes 0,01 y 0,1).
- **RM5:** N/A, porque el rigor es `estandar`.
- **RM6:** no se quitó ninguna guarda.
- **Validez del informe:** sin la cabecera «CAMPAÑA NO VÁLIDA» y con 0 «Sin veredicto».

## Checkpoints

- **C1:** `[x]` `init.sh` con código 0 · `[x]` existen los ficheros base.
- **C2:** `[x]` una sola `in_progress` · `[x]` rama `feature/F-150-receta-caja` · `[x]`
  `current.md` con F-150 como sección activa (lo demás, como en F-140) · `history.md`: N/A, no es
  `done`.
- **C3:**
  - `[x]` hexagonal: dominio puro (`re`, `decimal`, `typing`), el SQL en `sql/tesoreria/NN_` y la
    ingesta en `application`;
  - `[x]` la primera línea es la ruta;
  - `[x]` sin `print`, TODO, secretos ni dependencias nuevas;
  - `[x]` semántica de Sigrid: `stg.presupuesto` con obra, ámbito 9/11 y `fase_num` = V (R10); lo
    real con `importe_mes` y tope en el cierre (la misma fuente que `real_origen_corte` de F-140).
- **C3 bis:** N/A, porque no toca `docs/referencia/`.
- **C4:** `[x]` trazabilidad (tabla de abajo) · `[x]` sin red ni BBDD · **`[ ]` MANUAL con su
  comando exacto en `current.md`** (cambio 1) · `[x]` dobles: comprobación automática en `init.sh`.
- **C4 bis:** `[x]` rigor declarado · `[x]` fase RED con salida real (`impl_F-150.md` §5: R1-R5,
  R7, R9, R12, R14, R15, R17, R20-R23, R25, R32) · `[x]` cobertura `[OK]` 100 % (143/143) · `[x]` mutación
  verificada · `[x]` «Evidencias» con los cuatro números y los 2 workers.
- **C4 ter:** N/A, porque no existe `harness/rutas_sensibles.json` (solo el `.ejemplo`).
- **C5:** `[x]` T1-T14 y T16 `[x]` con su commit; T15 es el despliegue MANUAL tras la review,
  como en F-140 · `[x]` `git status` limpio · `[x]` `features.json` al día.

## Cobertura · requisito → test (`tests/test_f150_*.py`)

| Requisitos | Tests |
|---|---|
| R1, R24-R28 | `receta`/`perfil` r1 (12), r24 (3), r25 (9), r26 (3), r27 (3), r28 (4) |
| R2-R6, R15, R32 | `diccionario` r2, r3 (2), r4, r5, r6 (2), r15, r32 (2) |
| R7, R9, R18, R22 | `contrato` r7 (17), r18; `coeficiente` r9 (10); `hueco` r22 (11) |
| R8, R10-R14, R19-R21, R23 | `sql` r8 (9), r10-r13 (2-3 cada uno), r14 (7), r19, r20 (2), r21 (4), r23 (7) |
| R16, R17 · R29 · R30-R31 | `ingesta` r16 (5), r17 (6) · MANUAL hecho (§4, 15,60 en 15,50-15,75) · MANUAL T15 (cambio 1) |

## Automejora (propuesta, no aplicada)

Sumar a `.claude/agents/implementer.md` (y a `arnes-base`): «las verificaciones MANUAL van a
`current.md` CON su comando exacto, no como resumen». Es el segundo rechazo por esto (F-140 en su
pasada 1 y F-150).
