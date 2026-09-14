<!-- progress/impl_F-080.md -->
# F-080 · Informe de implementación

Vencimientos, forma de pago y texto de la factura de compra. Rigor `estandar`,
rama `feature/F-080-...`, un commit por tarea. Aquí va lo que no se lee en el
diff; el detalle de cada cambio, en su commit.

## T0 · Precondición dura de F-073 (R20): CUMPLIDA

`sql/compras/04_formas_pago.sql` existe en el árbol y `build_compras_step.py`
lo declara como sub-paso `formas_pago`. No se duplica la dimensión desde
`raw.auxpag`. **T0 bis** (que la vista esté construida en la base) es MANUAL
del humano y NO bloquea: queda en `progress/current.md`.
**El portero estaba en rojo ANTES de empezar, y no por el código**: `[KO]
PUERTA TAMAÑO`, `requirements.md` 152/150 y `design.md` 252/250. Se
recompusieron líneas y se comprobó palabra a palabra contra HEAD~1 que el
multiset de palabras de los dos ficheros es **idéntico** (commit `d0129a7`).

## T1 · Los nombres medidos, antes de una línea de SQL (solo lectura)

Medido el 2026-09-11 con el **cliente del ETL** (`SigridApiClient.leer_sql`,
que rechaza lo que no sea lectura), no con el MCP, que no ve `raw` ni Sigrid;
la tabla de las ocho tablas, en el commit `3fa6dfb`. Lo que **cambió de dónde
se lee el dato** —la trampa de DA-9, dos veces más—: **`rpa` ES un documento**
(`tip = 27`; no tiene `cod`, y `RP26/0254` vive en `con.cod`) y **`cua`
también** (`tip = 17`), así que cuenta y banco se resuelven contra `raw.con`. Y
**el bloque bancario, que «no constaba»**: `pag.banban` y `pag.bansuc` apuntan
los dos a **`auxban.ide`**, en dos joins y no al código (110.460/110.477 y
93.273/93.273), con `auxban.tipsuc` separando 442 entidades de 1.248
sucursales.

## T2 · Las cifras (2026-09-11, solo lectura)

| medida | valor |
|---|---|
| efectos cuyo `conide` es factura de compra (grano de `compras.vencimientos`) | **195.510** |
| reparto de `con.est` contra `raw.conest` `tip = 25` | Pagado 106.262 · Agrupados 55.476 · Aprobado 20.848 · Pendiente 10.436 · En cartera 2.319 · Emitido 169 |
| efectos de factura en remesa (`remide <> 0`) / con retención / con `fecrea = 0` | 40.090 / 23.180 / 120.843 (61,8 %) |
| documentos con `con.tex`: `tip = 15` y `tip = 44` | 108.527 de 165.759 (65,5 %), máx. 11.580 bytes, 30,3 MB · 1.614 de 18.965 (8,5 %), 0,35 MB |
| facturas que NO cuelgan de ningún contrato (R30) | **85.324 de 165.759 (51,5 %)** |

**`incremental_column` MEDIDO en `INFORMATION_SCHEMA`** (R3), no por analogía:
`auxnap.tiemod` y `auxban.tiemod` **sí**; **`rpa` no tiene `tiemod` ni ninguna
columna de fecha** (`fecrem` es un entero AAAAMMDD) y va con `null`. Es el
error que F-074 cometió declarando tres `tiemod` inexistentes. Recuentos de las
altas: `auxnap` **3**, `auxban` **1.690**, `rpa` **3.919**.

## T3 · Medición A del coste de ventana (R4a), solo lectura

Tres ventanas de `con` (`ide > 0`, `> 1.417.302`, `> 2.434.604`), las mismas
para las cuatro combinaciones; `con` tiene **2.186.880 filas** y «sin tex» son
18 columnas. Segundos y MB por página de 10.000 / 5.000 filas: **sin `tex`
1,78 / 1,02 s** y 3,98 / 1,99 MB; **con `tex` 2,24 / 1,04 s** y 4,57 / 2,25 MB
(tabla completa en el commit `a464f16`).

Página más pesada con `tex`: **1,71 MB**. Extrapolado a la tabla entera,
**2,2 → 2,7 min** y **290 → 333 MB**: traer `tex` cuesta **+26 % de tiempo y
+15 % de bytes, medio minuto**. El temor de DA-4 —«una página de 10.000
documentos habladores puede pesar cientos de MB»— **no se cumple**, así que
`page_size` de `con` se queda en el default global.

## T4 · La anulación, VERIFICADA (no investigada) · R39, R40

**(a) `FR25/04222`, la factura de los ocho efectos del correo.** Los tres con
`con.fecbaj <> 0` son exactamente los tres que la captura pinta en rojo con
aspa —`FR25/04222_01` (baja 20250908, 87.854,56), `DIV25/0156` (20251010,
57.435,88) y `DIV25/0169` (20251108, 50.354,99)—, los tres en estado
«Aprobado»: **el estado NO distingue**. Los cinco vivos suman **92.478,49** y,
quitando la retención viva (4.623,93), **87.854,56**: los **dos números de la
cabecera**. Los anulados suman 195.645,43, el fantasma que saldría sin filtrar.

**(b)** Efectos de baja: **89.228 de 255.148 (34,97 %)**, y **76.215 de 195.510
(39,0 %)** ciñéndose a los de factura; coherente con los 89.095 / 255.074 del
2026-09-10. **(c)** `pag.padide` informado en **0 de 255.148** →
`efecto_origen_id` NO se publica; `con.serie` en **0** → la serie sale de
`compras.fn_serie`; `con.tip <> 25` en **0** → todo efecto es un documento de
tipo 25. Las tres salen: no hay nada que parar antes de T10.

## T7 y T8 · Medición B y el presupuesto de ventana · MANUAL (humano)

**T7 es una ESCRITURA y ningún agente la ejecuta.** Comando exacto, también en
`progress/current.md`: `python main.py ingest --table con --full`, y después la
duración de `ingest_raw.con` en `_meta.etl_runs` (`timings --last 10`). **T8**:
con la B pendiente, lo único contrastable hoy sale de la A —`con.tex` añade
**~0,5 min** y 43 MB a una ventana que hoy tarda **3 h 25 min**, o sea **~3 h
26 min frente a un presupuesto de 4 h: 34 min de margen**—. **No hay aviso que
dar**; si la B lo desmintiera, el aviso va por escrito y **la feature sigue**:
no es una puerta y el `page_size` lo decide el humano con el dato delante.

## Fase RED · la traza real, no «se hizo TDD»

Cada test se escribió y se ejecutó **antes** que su código. Las trazas están
**reproducidas el 2026-09-14** ejecutando cada fichero en su propio commit
rojo, en un `git worktree` desechable —nunca en el árbol real—, con
`python -m pytest <fichero> -q -p no:cacheprovider`; los recuentos coinciden
con los que declararon aquellos commits, donde está la traza íntegra.

```
##### T5 · la ingesta (55a4713) — tests/test_f080_ingesta.py
E   AssertionError: la ficha de `raw.rpa` tiene que decir sus 3.919 filas medidas el 2026-09-11 (R6)
E   assert '3.919' in ''
17 failed, 4 passed in 0.80s

##### T9 · los vencimientos (09ee04f) — tests/test_f080_sql.py
FAILED ...::test_f080_r10_el_estado_sale_de_conest_filtrando_el_tipo_del_efecto
55 failed in 2.21s

##### T12 · la forma de pago y el control (403fc01) — tests/test_f080_sql.py
FAILED ...::test_f080_r19_ningun_importe_agregado_suma_los_efectos_de_baja
54 failed, 58 passed in 1.66s

##### T14 · el parseo del memo (dc5d6c2) — tests/test_f080_texto.py
tests/test_f080_texto.py:32: in <module>
    from etl_sigrid.domain.texto_comentarios import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.texto_comentarios'
1 error in 0.49s

##### T16 · el texto en SQL (5ea7db1) — tests/test_f080_sql.py
FAILED ...::test_f080_r23_los_comentarios_son_una_TABLA_y_no_una_vista
27 failed, 112 passed in 1.47s

##### T18 · el cableado del step (fede5be) — tests/test_f080_pipeline.py
FAILED ...::test_f080_los_ocho_sub_pasos_van_en_el_orden_de_sus_ficheros
9 failed, 1 passed in 1.77s

##### T20 · el diccionario (37862ba) — tests/test_f080_diccionario.py
FAILED ...::test_f080_r31_cada_objeto_nuevo_tiene_ficha_con_clave_y_grano[los tres]
26 failed, 3 passed in 1.56s
```

## T24 · La suite entera destapó cinco defectos que `-x` escondía

El portero corre `pytest -x` y el primer fallo tapaba a los otros cuatro. La
suite completa los sacó; **ninguno se tapó ni se relajó ninguna puerta**
(commit `eb78eb0`). **Dos eran de F-080:**

1. `v_facturas_pago` proyectaba `f.pagfor` y `f.pagtex` **en crudo** desde
   `raw.dcf` —que entra por `JOIN`, no por `LEFT JOIN`— mientras sus fichas
   declaraban `nulo_significa`: prometían un NULL que nunca llegaba
   (`test_f006_r2_un_nulo_declarado_tiene_que_ser_posible`). **Medido contra
   Sigrid el 2026-09-14** sobre las 165.802 filas de `dcf`: `pagfor` llega NULL
   en 1 y vacío en 7; `pagtex`, NULL en 1 y vacío en 3. Se publica con
   `NULLIF(x, '')`, que no recorta ni reescribe ningún valor —solo manda la
   cadena vacía a NULL, así que el «tal cual» de R18 se respeta—, y **el assert
   de R18 pasa a exigirlo**: es **más estricto** que antes, no más laxo.
2. El `grano` de `v_control_forma_pago` decía «una fila por PAR (factura,
   contrato)» sin nombrar `contrato_id`, media `clave_negocio`: quien lo lea
   uniría por menos columnas y duplicaría.

**Tres eran recuentos que el alta de tres tablas y cinco objetos deja viejos:**
`TOTAL_TABLAS` de `tests/test_f066_ingesta_raw.py` seguía en 65 (T6 lo subió a
68 solo en el fichero de F-074); el punto 3 de `R-SIGRID-CON` no declaraba
`auxban.res` ni `auxnap.res`, que el SQL nuevo lee sin pasar por `con`; y el
inventario de `specs/F-006-mcp-azure/design_detalle.md` seguía en 142 objetos
cuando son **150, con 941 columnas y 62 fichas de consumo**.

Y un sexto arreglo que no es de datos sino de **vigilancia**:
`compras.documento_comentarios` había dejado de ser legible para el guardián de
proyecciones de F-006 —los corchetes de la regex del sello descuadran su
contador de paréntesis— y un objeto ilegible deja de estar vigilado. Las ramas
del sello pasan a un CTE `publicados`. **No cambia ni una columna publicada.**

## T25 · Dos campañas de mutación, porque una sola no juzgaba a F-080

**La canónica** (`--feature F-080`, informe `progress/mutacion_F-080.md`): 303
generados, **20 evaluados** (muestreo `estandar`, semilla `20260820`), **14
muertos, 6 supervivientes**, 0 timeouts, 0 sin veredicto, **2.920,3 s con 4
workers**, SHA `eb78eb0`. **Y no dice nada del código de F-080**: su alcance
son 3.789 líneas porque se calcula contra `dev`, con 242 commits de retraso, y
solo **15 de los 303 mutantes caen en `texto_comentarios.py` (4,95 %)**, de los
que el muestreo no cogió ninguno (esperanza 0,99). Sus seis supervivientes son
de **F-025** —dos, los mismos que ya señaló F-073— y van analizados uno a uno
en su informe: cinco son huecos reales inalcanzables offline (leen de cursor) y
el sexto es **equivalente** (el `120` de `_veredicto_de_ventana` es un timeout
en segundos, no un umbral).

**La dirigida** (`--ficheros` a los dos módulos, `--max-mutantes 0`, informe
`progress/mutacion_F-080_modulos.md`): **27 generados, 27 evaluados sin
muestreo, 26 muertos, 1 superviviente**, 3.241,5 s con 4 workers, SHA
`2ff8bab`; base 412–422 s y media 120,1 s → **480 s reales por mutante**,
coherente (RM2). **Prueba de control del cero** de `build_compras_step.py`: 0
mutantes sobre las 42 líneas que F-080 cambia ahí y **12 sobre el fichero
entero** —el motor sabe mutarlo, así que el cero es del alcance y no una
avería: lo que F-080 añade ahí son cadenas, y este motor no muta cadenas—.

**El superviviente es de F-080 y se tapó.** `texto_comentarios.py:103`,
`if casado is None or fecha is None:` → `and`: las dos ramas solo se distinguen
cuando el sello **casa con el patrón y su fecha no existe** (`31/02/2026`), y
con `and` el bloque saldría con `sello_reconocido = True` y la fecha a NULL. El
caso estaba probado **en el SQL y no en el oráculo**. Entra
`test_f080_r25_una_fecha_que_no_existe_no_cuenta_como_sello` (31/02, 31/04,
30/02, 29/02), y **está comprobado que lo mata**: con el mutante aplicado en
copia aislada —nunca en el árbol—, `pytest tests/test_f080_texto.py` pasa de
`29 passed` a `4 failed, 25 passed` con `assert True is False` sobre
`sello_reconocido=True, fecha=None`. **No se quitó ninguna guarda** (RM6).

## Evidencias

| Evidencia | Valor medido |
|---|---|
| **Tests ejecutados y resultado** | **4.677 pasan, 179 saltados, 0 fallos** (`bash harness/init.sh`, T29); 4.673 antes del test nuevo de T25 |
| **Cobertura de las líneas cambiadas** | **[OK] 93,6 % (823/879)**, umbral 80 %, nivel `estandar` |
| **Mutantes generados / supervivientes** | canónica **303 / 20 evaluados / 6** (todos de F-025) · dirigida **27 / 27 / 1**, tapado con un test |
| **Tiempo de la suite** | **810,1 s** con medición de cobertura; **412–422 s** sin ella (línea base de la campaña, con `-x`) |
| **Workers de las campañas** | **4** en las dos (coste real por mutante: 584 s y 480 s) |

## T29 y lo que falta

`bash harness/init.sh` termina en **exit 0**, sin un solo `[KO]`. Los dos
`[AVISO]` son deuda previa y no bloquean: F-052 sigue `blocked` y ruff arrastra
224 avisos anteriores a esta feature.

Queda fuera **todo lo MANUAL (humano)** —T0 bis, T7, T26 y T27—, con su comando
exacto en `progress/current.md`: ningún agente escribe contra Azure ni contra
Sigrid, y de la verificación 2 en adelante nada significa nada sin la 1.

**DEUDA DECLARADA, no descubierta luego**: `azure-apps/datamart_seg_anual.md`
dice que el ETL ingiere **56 tablas** de Sigrid. Ya estaba viejo antes de F-080
—F-074 lo dejó en 65 sin tocarlo— y F-080 lo deja en **68**. Se actualiza al
desplegar, que es cuando la cifra se vuelve cierta en Azure.
