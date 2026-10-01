<!-- progress/review_F-120.md -->
Revisión completa (pasada 1) · `git diff main...HEAD` hasta `f6d5eae`; código desde `e65fe5a` (T1)

# F-120 · Review · el factor del descompuesto

**Veredicto: CHANGES_REQUESTED.** El código es correcto y está bien verificado. Un
solo defecto lo impide cerrar, y es barato: el aviso caducado «el master está
INCOMPLETO hasta la primera carga» se sigue publicando en la ficha del ESQUEMA
`descompuestos` (hallazgo 1). Además, el `acceptance` 5 todavía lleva el texto
viejo de D7 (hallazgo 2, papeleo del líder).

**Nivel de rigor:** `estandar` (declarado). Exige fase RED, cobertura >= 80 % de lo
cambiado y una campaña de mutación con los supervivientes analizados. RM5 es N/A
por nivel.

## Hallazgos, por gravedad

1. **[MEDIA, bloquea] El aviso caducado sigue publicado** en
   `config/diccionario/00_global.yaml:1389-1390` (`esquemas.descompuestos.para_que_sirve`):
   «El master esta INCOMPLETO hasta la primera carga (MANUAL)…». Es la
   descripción del esquema que sirve `contexto_bbdd()`, lo primero que lee el MCP,
   y en v39 contradice a `lineas` y `cuadre_partida` («LA PRIMERA CARGA SE HIZO EL
   2026-09-29»). `test_f120_r25_sin_el_aviso_caducado_de_la_primera_carga` solo
   mira `descompuestos.yaml` y no lo detecta. Si se publica así en T18,
   arreglarlo costará una v40.
2. **[BAJA, líder] El `acceptance` 5** (`harness/features.json` y `BACKLOG.md`)
   todavía dice «la foto fija de Estudios es MASTER_INICIAL», la frase que la D7
   aprobada declara falsa (el implementer lo avisó en impl §T1). R25 de
   `requirements.md` dice lo mismo.
3. **[BAJA, no bloquea] El cerrojo nocturno del `ALTER`.** Medido en un PG16
   local: `ADD COLUMN IF NOT EXISTS` toma `AccessExclusiveLock` sobre `lineas`
   **incluso con la columna ya presente**, y lo mantiene hasta el commit de `02`
   (una sola transacción). Cada noche bloquea las lecturas de `lineas` y de sus
   vistas mientras se rehacen ESTUDIO y PLANIF_JO, y espera detrás de cualquier
   lector largo. Como el patrón ya existe (`personal/00_setup.sql`, `_meta`), lo
   acepto. Si molesta, la salida es un `DO` que mire `information_schema` antes.
4. **[BAJA, no bloquea] El superviviente `PRECISION_PRODUCTO` 60 -> 61**: lo acepto
   como equivalente en la práctica (en `estandar` basta lo escrito). En sentido
   estricto no lo es: `PATRON_NUMERO` no limita las cifras, y un producto de más
   de 60 cifras en el filo del medio céntimo cambiaría. Ningún dato real se acerca.
   RM3: el superviviente no salió muerto.
5. **[MENOR]** `docs/ARCHITECTURE.md:809`: el «Sin ella» viene detrás de la frase
   del retroceo y su referente (la primera carga) queda ambiguo.
6. **[MENOR, líder]** `progress/current.md`: la cabecera de F-118 todavía dice
   «SIN DESPLEGAR», pero `impl_F-118.md` la da desplegada (`r20260930-1715`) y
   verificada el 01-10. Puede confundir al leer T14.
7. **[INFO]** La nocturna publica el diccionario sola (v38 lo hizo), así que v39
   puede salir antes de T16. La ficha ya lo cubre («versión aún no retroceada»).

## Verificación propia (sin escrituras en Azure)

- **`bash harness/init.sh`**: ENTORNO LISTO, exit 0. **6.252 passed, 219
  skipped** (12 min 30 s). `PUERTA COBERTURA [OK] 100,0 %` (29/29). Tamaño [OK].
- **RED reproducida**: worktree temporal en `9769269` (solo tests) ->
  **99 failed, 3 passed, 1 skipped** (el skip es el de `azure-apps`). Worktree borrado.
- **Azure en SOLO LECTURA** (`transaction_read_only` = on, rollback):
  `dncpro.factip` es `integer` y `faccan` `double precision`, así que el `CASE`
  compila. `fn_trocear` no tiene dependientes en `pg_depend` y su ACL es la de
  por defecto: el `DROP` no rompe nada. Las 3.025 versiones llevan el sello
  `99f827a11969d59f` y quedarán todas pendientes. `lineas` aún no tiene `factor`.
- **Contraste en un PG16 local desechable** (ya parado): los 11 textos reales de la
  400854 de la 0713 (ámbito 3 y v2-v11) y 304 registros sintéticos (38 formas del
  campo 14 × 8 precios: signos, `0x`, `-0x-0`, `1e999x1e-999`, blancos, tabulador,
  `1X2`, `1,5`, `1x2x3`, `x`, 40 nueves, porcentajes 4/13). `fn_trocear` frente a
  `trocear_des`, las 19 columnas: **506 registros, 0 diferencias**.
- **La 400854 v6 real**: 19 registros, **9 con forma factor**, todos con factor,
  rendimiento e importe; **suma 249,41** en SQL y en Python. La línea 13 da
  1,22 × 0,003 × 339,39 = **1,24**.
- **Sobre el estado de F-097** (local): el `01` de `main` y encima el `00`+`01` de
  la rama -> `DROP`+`CREATE` funciona, y repetido también. El DDL viejo con una
  fila, más el `ALTER` y el `06`: `factor` queda la última en la tabla y en las
  tres vistas, con la fila previa a NULL. En instalación nueva, una sola columna.
- **Mutación, recálculo puro** (`harness.alcance` + `generar_mutantes`): **83
  líneas** (9 + 65 + 9) y **9 mutantes**, como el informe; el superviviente
  `descompuestos.py:137` `entero` 60 -> 61 existe tal cual. **Campaña no
  reejecutada: 2.180,6 s según el informe** (> 60 s).

## Checkpoints

**C1** [x] init.sh exit 0 · [x] ficheros del arnés.
**C2** [x] una sola `in_progress` · [x] rama de la feature · [x] la sección de
F-120 en `current.md` está al día (las secciones antiguas son deuda previa que
F-120 no amplía; hallazgo 6) · [x] `history.md` sin cambios necesarios.
**C3** [x] hexagonal: el dominio solo usa stdlib y el SQL va en
`sql/descompuestos/NN_*` · [x] primera línea con ruta · [x] sin `print`, TODOs,
secretos ni dependencias nuevas. Barrido de IPs, GUID, `@`, `pwd=` y
`AccountKey`: solo falsos positivos (códigos de partida) · [x] semántica: no
mezcla orígenes ni versiones, `importe_total` no cambia, el factor del master
sale del texto de cada versión y no de `dncpro`.
**C3 bis** N/A: no toca `docs/referencia/`.
**C4** [x] R1-R27 con test `test_f120_rN_*` en verde (R28-R29 son MANUAL) · [x]
sin red ni BBDD · [x] T14-T18 en `current.md` con su comando, lo que debe salir y
el ORDEN OBLIGATORIO (imagen T14 antes que retroceo T16, con el porqué) · [x]
F-120 no añade dobles; la comprobación del árbol corre en la suite verde.
**C4 bis** [x] rigor declarado · [x] RED con traza real, y reproducida · [x]
cobertura 100 % · [x] alcance y mutantes recalculados · [x] > 60 s: recálculo
puro, dicho arriba · [x] coste por mutante 2.180,6 × 2 / 9 = 484,6 s · [x] sin
«CAMPAÑA NO VÁLIDA» y 0 sin veredicto (el intento con 4 workers se descartó por
escrito) · [x] RM1: SHA `68e1223`; después solo cambian `progress/` y
`tasks.md` · [x] RM2: 9 × 242,3 = 2.180,7, y media × 2 = 484,6 s frente a una
base de 370-373 s · N/A RM5: nivel `estandar` · [x] RM6: ninguna guarda quitada
(los mutantes de `texto is None` y `any(v is None)` mueren) · N/A campaña manual:
la automática dio 9 · [x] el superviviente está analizado · [x] «Evidencias» con
los workers (2) · [x] ningún N/A sin motivo.
**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
**C5** [x] T1-T13 y T19 `[x]` con su commit `F-120 Tn:` (T14-T18 son MANUAL) ·
[x] árbol limpio · [ ] `features.json`: el `acceptance` 5 contradice la D7 (hallazgo 2).

## Cobertura requisito -> test (`tests/test_f120_factor.py`)

| Req. | Test | Req. | Test |
|---|---|---|---|
| R1-R5, R9 | `r1_r5_forma_del_campo_14`, `r2_*`…`r5_*`, `r9_*` | R14-R16 | `r14_r16_planif_jo_*`, `r15_factip_raro_*` |
| R6 | `r6_*` (5) | R17 | `r17_ddl_y_alter_*`, `r17_estudio_*`, `r17_master_*` |
| R7, R8 | `r7_importe_total_*`, `r8_porcentaje_*` | R18, R19 | `r18_*` (3 vistas), `r19_troceado_drop_*` |
| R10, R11 | `r10_*` (2), `r11_multiplica_*` | R20-R23 | `r20_*`, `r21_*`, `r22_*`, `r23_*` |
| R12, R13 | `r12_*` (2), `r13_la_400854_v6_*` | R24-R27 | `r24_*` (2), `r25_*` (2), `r26_*`, `r27_*` (2) |

El diccionario v39 tiene lo pedido: el factor explicado (qué es, cómo viene, la
fórmula, 1 sin factor, `faccan`, F-122, el ejemplo 1,22 × 0,003 × 339,39 = 1,24);
la nota de ESTUDIO tal como se aprobó en `lineas`, `v_pbi_estudio` y
`cuadre_partida`, con la 0713 y la 0726; y la versión 39. Falta el hallazgo 1.

## Cambios requeridos

1. **Implementer** · `config/diccionario/00_global.yaml:1389-1390`: cambiar la
   frase «El master esta INCOMPLETO hasta la primera carga (MANUAL)…» por la
   vigente (primera carga hecha el 2026-09-29; qué versión está lo dice
   `_versiones_cargadas`). Y ampliar
   `test_f120_r25_sin_el_aviso_caducado_de_la_primera_carga` para que mire también
   `esquemas.descompuestos` de `00_global.yaml`. No toca el sello.
2. **Líder** · `harness/features.json`, `acceptance` 5 de F-120: poner la D7
   aprobada (importe de Estudios = medición × precio de la v0; MASTER_INICIAL
   solo donde la v0 guarda descompuesto). Recomendado: lo mismo en R25 de
   `requirements.md`.

Opcionales: hallazgos 3, 5 y 6.

**Automejora (propuesta para `CHECKPOINTS.md` C3, no aplicada):** «un texto
retirado del diccionario se busca en todos los YAML, `esquemas` incluido».
