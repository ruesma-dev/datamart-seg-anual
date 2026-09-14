<!-- progress/impl_F-080.md -->
# F-080 · Informe de implementación

Vencimientos, forma de pago y texto de la factura de compra. Rigor `estandar`.
Rama `feature/F-080-vencimientos-forma-pago-y-texto-factura`. Un commit por
tarea; el detalle de cada cambio vive en su commit y aquí va lo que no se lee
en el diff.

## T0 · Precondición dura de F-073 (R20): CUMPLIDA

`sql/compras/04_formas_pago.sql` existe en el árbol y `build_compras_step.py`
lo declara como sub-paso `formas_pago`. No se duplica la dimensión desde
`raw.auxpag`. **T0 bis** (que la vista esté construida en la base) es MANUAL
del humano y NO bloquea: queda en `progress/current.md`.

**El portero estaba en rojo ANTES de empezar, y no por el código**: `[KO]
PUERTA TAMAÑO`, `requirements.md` 152/150 y `design.md` 252/250. Se
recompusieron líneas y se comprobó palabra a palabra contra HEAD~1 que el
multiset de palabras de los dos ficheros es **idéntico**: ni un requisito, ni
una decisión, ni una cifra tocada. Commit `d0129a7`.

## T1 · Los nombres medidos, antes de una línea de SQL (solo lectura)

Medido el 2026-09-11 contra Sigrid con el **cliente del ETL**
(`SigridApiClient.leer_sql`, que rechaza lo que no sea lectura), no con el MCP,
que no ve `raw` ni Sigrid. La tabla de las ocho tablas medidas, en el commit
`3fa6dfb`. Lo que cambió de dónde se lee el dato —la trampa de DA-9, dos veces
más—: **`rpa` ES un documento** (`tip = 27`, las 3.919 remesas tienen fila en
`raw.con`, y el código `RP26/0254` y la descripción viven en `con.cod`/`con.res`
porque `rpa` **no tiene `cod`**) y **`cua` también** (`tip = 17`, 34.158
cuentas), así que la cuenta y el banco del efecto se resuelven contra `raw.con`.
**El bloque bancario, que «no constaba»**: `pag.banban` y `pag.bansuc` apuntan
los dos a **`auxban.ide`**, en dos joins distintos y no al código —medido,
110.460/110.477 (99,98 %) y 93.273/93.273—, y `auxban.tipsuc` separa 442
entidades (0) de 1.248 sucursales (1). `con` trae `cod` varchar(24), `res`
varchar(128), `est` int y **`fecbaj` int**; `conest` se une por **`tip` + `est`**
y su `cod` es el rótulo de tres letras de la pantalla (PDT, APR, EMI…).

## T2 · Las cifras (2026-09-11, solo lectura)

| medida | valor |
|---|---|
| efectos cuyo `conide` es factura de compra (grano de `compras.vencimientos`) | **195.510** |
| facturas distintas con efectos | 165.737 |
| reparto de `con.est` contra `raw.conest` `tip = 25` | 10 Pagado 106.262 · 14 Agrupados 55.476 · 2 Aprobado 20.848 · 1 Pendiente 10.436 · 5 En cartera 2.319 · 3 Emitido 169 |
| efectos de factura en remesa (`remide <> 0`) / con retención / con `fecrea = 0` | 40.090 / 23.180 / 120.843 (61,8 %) |
| documentos con `con.tex`: `tip = 15` y `tip = 44` | 108.527 de 165.759 (65,5 %), máx. 11.580 bytes, 30,3 MB · 1.614 de 18.965 (8,5 %), 0,35 MB |
| facturas que NO cuelgan de ningún contrato (R30) | **85.324 de 165.759 (51,5 %)** |
| series del código del efecto | `FR` 192.444 · `DI` 3.016 · `AG` 25 · `AB` 13 · `VA` 10 · `FC` 2 |

**`incremental_column` MEDIDO en `INFORMATION_SCHEMA`** (R3), no por analogía:
`auxnap.tiemod` float **sí**, `auxban.tiemod` float **sí**, y **`rpa` no tiene
`tiemod` ni ninguna columna de fecha** (`fecrem` es un entero AAAAMMDD), así
que va con `incremental_column: null`. Es el error que F-074 cometió
declarando tres `tiemod` inexistentes. Recuentos de las tres altas: `auxnap`
**3**, `auxban` **1.690**, `rpa` **3.919**.

## T3 · Medición A del coste de ventana (R4a), solo lectura

Tres ventanas de `con` repartidas por la tabla (`ide > 0`, `> 1.417.302`,
`> 2.434.604`), las mismas para las cuatro combinaciones. `con` tiene
**2.186.880 filas**; «sin tex» son 18 columnas (se excluye `ima`).

| variante | `page_size` | filas | segundos | MB |
|---|---|---|---|---|
| sin `tex` | 10.000 / 5.000 | 30.000 / 15.000 | **1,78** / 1,02 | 3,98 / 1,99 |
| con `tex` | 10.000 / 5.000 | 30.000 / 15.000 | **2,24** / 1,04 | 4,57 / 2,25 |

Página más pesada con `tex` a 10.000 filas: **1,71 MB**. Extrapolado a la tabla
entera: **2,2 → 2,7 min** y **290 → 333 MB**. Traer `tex` cuesta **+26 % de
tiempo y +15 % de bytes: medio minuto** sobre el total de `con`. El temor de
DA-4 —«una página de 10.000 documentos habladores puede pesar cientos de MB»—
**no se cumple**. Por eso `page_size` de `con` se queda en el default global.

## T4 · La anulación, VERIFICADA (no investigada) · R39, R40

**(a) `FR25/04222`, la factura de los ocho efectos del correo.** Los tres con
`con.fecbaj <> 0` son exactamente los tres que la captura pinta en rojo con
aspa: `FR25/04222_01` (baja 20250908, 87.854,56), `DIV25/0156` (20251010,
57.435,88) y `DIV25/0169` (20251108, 50.354,99), los tres en estado
«Aprobado» —**el estado NO distingue**—. Los cinco vivos suman **92.478,49** y,
quitando la retención viva `FR25/04222_02` (4.623,93), **87.854,56**: los **dos
números de la cabecera** de la captura. Los anulados suman 195.645,43, el
fantasma que aparecería sin filtrar.

**(b)** Efectos de baja: **89.228 de 255.148 (34,97 %)**; ciñéndose a los de
factura de compra, **76.215 de 195.510 (39,0 %)**. Coherente con los 89.095 /
255.074 del 2026-09-10 (el sistema sigue vivo).

**(c)** `pag.padide` informado en **0 de 255.148** → `efecto_origen_id` NO se
publica. `con.serie` informado en **0 de 255.148** → la serie sale de
`compras.fn_serie`. Y `con.tip <> 25` en **0 de 255.148**: todo efecto es un
documento de tipo 25. Las tres salen; no hay nada que parar antes de T10.

## T7 y T8 · Medición B y el presupuesto de ventana · MANUAL (humano)

**T7 es una ESCRITURA y ningún agente la ejecuta.** Comando exacto, también en
`progress/current.md`: `python main.py ingest --table con --full`, y después la
duración de `ingest_raw.con` en `_meta.etl_runs` frente a las noches anteriores
(`python main.py timings --last 10`).

**T8.** Con la medición B pendiente, lo único contrastable hoy sale de la
medición A: traer `con.tex` añade **~0,5 min** (2,2 → 2,7 min) y 43 MB a una
ventana que hoy tarda **3 h 25 min**, o sea **~3 h 26 min frente a un
presupuesto de 4 h: unos 34 min de margen**. **No hay aviso que dar.** Si la
medición B lo desmintiera, el aviso va por escrito y **la feature sigue**: no
es una puerta y el `page_size` lo decide el humano con el dato delante.

## Fase RED · la traza real, no «se hizo TDD»

Cada test se escribió y se ejecutó **antes** que su código, y su commit lleva
el recuento de fallos. Las trazas de abajo están **reproducidas el 2026-09-14**
ejecutando cada fichero en su propio commit rojo, en un `git worktree`
desechable (nunca en el árbol real), con
`python -m pytest <fichero> -q -p no:cacheprovider`. Los recuentos coinciden
con los que declararon los commits de entonces.

```
##### T5 · la ingesta (55a4713) — tests/test_f080_ingesta.py
E   AssertionError: la ficha de `raw.rpa` tiene que decir sus 3.919 filas medidas el 2026-09-11 (R6)
E   assert '3.919' in ''
FAILED ...::test_f080_r1_a_con_solo_le_queda_fuera_la_imagen
FAILED ...::test_f080_r3_rpa_no_finge_una_columna_de_fecha_que_no_tiene
FAILED ...::test_f080_r3_el_censo_de_tablas_ingeridas_sube_a_68
17 failed, 4 passed in 0.80s

##### T9 · los vencimientos (09ee04f) — tests/test_f080_sql.py
FAILED ...::test_f080_r10_el_estado_sale_de_conest_filtrando_el_tipo_del_efecto
FAILED ...::test_f080_r10_el_estado_NO_se_deriva_de_la_fecha_real
FAILED ...::test_f080_r38_la_serie_se_deriva_con_la_funcion_del_repositorio
FAILED ...::test_f080_r40_la_anulacion_es_la_fecha_de_baja_del_documento
FAILED ...::test_f080_r41_el_codigo_de_la_remesa_se_lee_de_con_porque_rpa_no_lo_tiene
55 failed in 2.21s

##### T12 · la forma de pago y el control (403fc01) — tests/test_f080_sql.py
FAILED ...::test_f080_r18_las_condiciones_y_la_formula_del_documento_van_tal_cual
FAILED ...::test_f080_r19_el_resumen_de_efectos_agrega_ANTES_de_unir
FAILED ...::test_f080_r19_ningun_importe_agregado_suma_los_efectos_de_baja
FAILED ...::test_f080_r21_f080_no_redefine_las_tablas_de_f067[compras.facturas]
54 failed, 58 passed in 1.66s

##### T14 · el parseo del memo (dc5d6c2) — tests/test_f080_texto.py
tests\test_f080_texto.py:32: in <module>
    from etl_sigrid.domain.texto_comentarios import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.texto_comentarios'
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.49s

##### T16 · el texto en SQL (5ea7db1) — tests/test_f080_sql.py
FAILED ...::test_f080_r22_el_memo_sale_de_con_tex_y_solo_de_facturas_y_contratos
FAILED ...::test_f080_r23_los_comentarios_son_una_TABLA_y_no_una_vista
FAILED ...::test_f080_r24_el_sql_usa_LOS_MISMOS_literales_que_el_oraculo
FAILED ...::test_f080_r25_sin_sello_se_publica_el_bloque_entero_como_cuerpo
FAILED ...::test_f080_r26_el_bloque_integro_se_publica_para_poder_reconstruir
27 failed, 112 passed in 1.47s

##### T18 · el cableado del step (fede5be) — tests/test_f080_pipeline.py
FAILED ...::test_f080_los_ocho_sub_pasos_van_en_el_orden_de_sus_ficheros
FAILED ...::test_f080_cada_sub_paso_nuevo_declara_su_fichero_y_su_objeto[vencimientos/pago_factura/texto]
FAILED ...::test_f080_los_tres_van_detras_de_la_dimension_de_f073
9 failed, 1 passed in 1.77s

##### T20 · el diccionario (37862ba) — tests/test_f080_diccionario.py
FAILED ...::test_f080_r31_cada_objeto_nuevo_tiene_ficha_con_clave_y_grano[los tres]
FAILED ...::test_f080_r11_la_ficha_avisa_de_que_fecha_real_vacia_no_es_vivo
FAILED ...::test_f080_r40_la_ficha_explica_por_que_no_hay_enlace_al_efecto_de_origen
FAILED ...::test_f080_r32_el_diccionario_sube_al_menos_a_la_version_21
26 failed, 3 passed in 1.56s
```

## T24 · La suite entera destapó cinco defectos que `-x` escondía

El portero corre `pytest -x`: el primer fallo tapaba a los otros cuatro. La
suite completa los sacó, y **ninguno se tapó ni se relajó ninguna puerta**.
Commit `eb78eb0`. **Dos eran de F-080:**

1. `v_facturas_pago` proyectaba `f.pagfor` y `f.pagtex` **en crudo** desde
   `raw.dcf`, que entra por `JOIN` y no por `LEFT JOIN`, mientras sus fichas
   declaraban `nulo_significa`: prometían un NULL que nunca llegaba
   (`test_f006_r2_un_nulo_declarado_tiene_que_ser_posible`). **Medido contra
   Sigrid el 2026-09-14** sobre las 165.802 filas de `dcf`: `pagfor` llega NULL
   en 1 y vacío en 7, `pagtex` NULL en 1 y vacío en 3. Se publica con
   `NULLIF(x, '')` —que no recorta ni reescribe ningún valor, solo manda la
   cadena vacía a NULL, así que el «tal cual» de R18 se respeta— y **el assert
   de R18 pasa a exigirlo**: `NULLIF\(f\.pagfor, ''\) AS …` es **más estricto**
   que el `f\.pagfor[^,]*` de antes, no más laxo.
2. El `grano` de `v_control_forma_pago` decía «una fila por PAR (factura,
   contrato)» sin nombrar `contrato_id`, media `clave_negocio`: quien lea el
   grano uniría por menos columnas y duplicaría.

**Tres eran recuentos que el alta de tres tablas y cinco objetos deja viejos:**
`TOTAL_TABLAS` de `tests/test_f066_ingesta_raw.py` seguía en 65 (T6 lo subió a
68 solo en el fichero de F-074); el punto 3 de `R-SIGRID-CON` no declaraba
`auxban.res` ni `auxnap.res`, que el SQL nuevo lee sin pasar por `con`; y el
inventario de `specs/F-006-mcp-azure/design_detalle.md` seguía en 142 objetos
cuando son **150, con 941 columnas y 62 fichas de consumo**.

Y un sexto arreglo que no es de datos sino de **vigilancia**:
`compras.documento_comentarios` había dejado de ser legible para el guardián de
proyecciones de F-006 —los corchetes de la regex del sello descuadran su
contador de paréntesis—, y un objeto ilegible deja de estar vigilado. Las ramas
del sello se mueven a un CTE `publicados` y el `SELECT` final queda en columnas
desnudas. **No cambia ni una columna publicada.**
