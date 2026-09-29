# Exploración · meses que faltan en `stg.plan_mensual` (caso Juan Romero, 0686)

Fecha: 2026-09-22 · Solo lectura · Sin commit · Rama activa ajena (F-057), no se ha tocado.

## Veredicto en tres líneas

1. **Causa**: `etl_sigrid/infrastructure/postgres/sql/stg/08_plan_mensual.sql`, **línea 515**,
   `AND pct_acumulado <= 2.5` (el «sanity check» de la línea 512, commit `f14e443` del 2026-05-23).
   Juan acierta en la forma y falla en el umbral: no se descarta lo que pasa del 100 %, sino lo que pasa del **250 %**.
2. **El origen está bien**: Sigrid y `raw` traen 460,29 % en ene, feb y mar-26 y 100 % en abr-26. El fallo es nuestro.
3. **No es un caso aislado**: 2.785 series partida-versión, 84 obras y **89,09 M€ netos** de `importe_mes`
   que faltan en `stg.plan_mensual`. En `mart` (meses donde la versión afectada es la vigente) el daño es mucho menor: 40 filas y 46.889 €.

## Cómo se ha consultado

- MCP `bbdd-ruesma-azure` (`contexto_bbdd`, `describir_tabla` de `stg.plan_mensual`, `stg.presupuesto`, `stg.partidas`) para `stg`.
- `raw` y `mart`: **psycopg directo** con `make_conninfo_provider(settings.postgres)` y `conn.read_only = True`.
  **No se ha usado `build_postgres_client`**, así que no ha corrido `_auto_bootstrap` ni `SET ROLE`. Cero escrituras.
- Sigrid: un único `SELECT TOP 10` por `sigrid-api` (`leer_sql`).
- Script: `scratchpad/alcance.py` (fuera del repo). **Toma las líneas 149-328 del SQL de producción tal cual**
  (la rama master entera hasta `master_con_pct_mes`) y solo cambia el filtro de obras por uno de presupuestos candidatos.
  Luego marca cada fila con `pasa_tope = pct_acumulado <= 2.5` y `pasa_cero = NOT (pct_acumulado = 0 AND pct_mes = 0)`.
  Candidatos: filas de `raw.obrparpre` con `amb IN (8,11)` y algún valor del `planif` > 2,5 → **2.787 filas**.
  2.785 de ellas llegan a `stg.presupuesto`; las 2 que faltan son filas de `raw` que `06_presupuesto.sql` no publica.

## 1 · La causa, demostrada

Así funciona la rama master (líneas 292-328 y 505-515):
- `master_pct_efectivo` aplica la regla de ceros y deja `pct_acumulado = 4,602878` en ene, feb y mar-26 (posiciones 17-19, literal positivo).
- `master_con_pct_mes` calcula `pct_mes = pct_acumulado − LAG(pct_acumulado)` **sobre la serie completa**.
- **Después**, el `WHERE` final (línea 515) tira las filas con `pct_acumulado > 2.5`.

Resultado: se borra la subida (ene: +3,602507 → +387,97 €) y se conserva la bajada, cuya `pct_mes` se calculó
contra un marzo que ya no existe (abr: 1 − 4,602878 = −3,602878 → −388,01 €).

Reproducción exacta con el SQL de producción. Versión 28, en v27, v29 y v30 idéntica:

| mes | pct_acum | pct_mes | importe_mes | importe_origen | pasa_tope | en `stg` |
|---|---|---|---|---|---|---|
| dic-25 | 1,000371 | 0 | 0,00 | 107,74 | sí | sí (igual) |
| ene-26 | 4,602878 | 3,602507 | **387,97** | 495,71 | **no** | **no** |
| feb-26 | 4,602878 | 0 | 0,00 | 495,71 | **no** | **no** |
| mar-26 | 4,602878 | 0 | 0,00 | 495,71 | **no** | **no** |
| abr-26 | 1,000000 | −3,602878 | −388,01 | 107,70 | sí | sí (igual) |

Las filas que pasan el filtro coinciden **al céntimo** con lo publicado en `stg` (MCP: `stg.plan_mensual`, obra 2313811, ámb. 8,
partida `03.02.18`, versiones 22-28). En toda la obra 0686, MCP con `sum(pct_mes) ≠ último pct_acumulado`:
**4 series descuadradas de 122.899**, las versiones 27-30 de esta partida, −387,97 € cada una (−1.551,88 € en total).
**No hay ninguna otra partida de la 0686 afectada.**

Hipótesis descartadas, cada una con su prueba:
- **Meseta tratada como «sin movimiento»**: no. En v23-25 la meseta 0,95 de ene-abr-26 se publica con `pct_mes = 0`.
  El filtro `(0,0)` solo quita filas con acumulado 0.
- **`DISTINCT ON` o deduplicación**: no. El `presupuesto_id` de `stg` es el `ide` de `raw` (15250686 en v28) y hay una única fila por versión.
- **Ventana F-025 o código distinto según la versión**: no. Todas las versiones de la obra salen del mismo build y del mismo SQL.
  El filtro existe desde el 2026-05-23, antes de crearse la v23 (25-02-2026, construida después).
  La diferencia entre versiones está en el **dato**, no en el código.

## 2 · El dato en origen, y por qué v23-25 no fallan

`raw.obrparpre`, `obride 2313811`, `paride 368319`, `amb 8` (consulta 1 de `bc3/output/cierre/Diagnostico_raw_planificacion_0686.sql`).
Sigrid por `sigrid-api` devuelve el mismo `planif` para las versiones 25, 28 y 30; solo cambian los ceros de cola:

| versión | fecha / texto | can | pre | planif pos. 13-20 |
|---|---|---|---|---|
| 23-25 | 25-02 / 12-03 / 15-04-26 | 9,59 | **54,41** | 0,196·0,196·0,206·0,206·**0,950·0,950·0,950·0,950**·1 |
| 26 | 21-05-26 CIERRE ABRIL | 9,59 | **11,23** | igual que v23-25 (0,950) |
| 27-30 | 18-06 … 19-08-26 (v28 = CUATRIM. JUN-26) | 9,59 | 11,23 | 0,950·0,950·1,000·1,000·**4,603·4,603·4,603**·1 |

Por eso v23-25 no fallan. Con el precio antiguo (54,41), los mismos ~495,7 € de enero son un **95 %**, por debajo de 2,5.
Cuando el precio baja a 11,23 (v26 todavía con el % viejo: 102,32 €), Sigrid reexpresa el acumulado desde la v27 para conservar los euros: 495,71 / 107,70 = **4,6029**.
Queda confirmado el contraste que se pedía: enero vale **387,99 €** en v23-25 (0,743575 × 9,59 × 54,41) y **387,97 €** en v27-30.
Juan citó las versiones 27 y 28, pero **la 29 y la 30 también están afectadas**.

## 3 · El alcance, en todo el datamart

Todas las cifras son de `alcance.py` (modos `resumen`, `tramos` y `vigente`). «Ausente» es la suma de `importe_mes` de las filas que el filtro tira.
Como `pct_mes` se calcula antes del filtro, **eso es exactamente lo que le falta a `SUM(importe_mes)` de la serie** para cuadrar con `stg.presupuesto`.

**Total**: 2.785 series presupuesto-versión, 465 partidas, 727 obra-versión, **84 obras**, 8.646 filas-mes, **89.092.299,62 €** netos.
Por ámbito: coste (8) 2.244 series · 78 obras · 83.052.302,64 € · venta (11) 541 series · 37 obras · 6.039.996,98 €.

| caso | acumulado máx. | series | obras | obra-vers. | filas | importe ausente € |
|---|---|---|---|---|---|---|
| (a) sube y baja | (2,5 ; 5] | 1.910 | 65 | 563 | 5.473 | 10.291.457,30 |
| (a) | (5 ; 10] | 572 | 42 | 295 | 1.824 | 4.973.054,94 |
| (a) | (10 ; 100] | 221 | 33 | 133 | 827 | 3.850.772,85 |
| (a) | > 100 | 29 | 5 | 28 | 59 | 68.419.769,62 |
| **(a) total** | | **2.732** | **82** | **714** | **8.183** | **87.535.054,71** |
| **(b) termina > 2,5** | todos | **53** | **15** | **45** | **463** | **1.557.244,91** |

- **(a)** Pasa lo mismo que en la 0686: se publica la bajada y no la subida, y el total de la versión queda por debajo del presupuesto en ese importe.
- **(b)** El último mes sigue por encima de 2,5. Se pierde la cola entera, y el último `importe_origen` publicado es el de antes de la subida.
  Ejemplo: 0677 `02.02` v10, que sube hasta 6,47 sin volver (913.388 € ausentes).
- **El volumen lo dominan datos de origen absurdos, no reimputaciones.** 0571 `04.12` v23 lleva `planif …|60|378|…|2397|0.28|0.94|1`,
  que parece un % tecleado en unidades 0-100: faltan 62,97 M€ de una partida de 26.271 € y se publica una bajada de −62,97 M€.
  La zona que se parece al caso de Juan, entre 2,5 y 5, son **1.910 series, 65 obras y 10,29 M€**.
- **En `mart`**, que elige la versión vigente por mes (`mart/02_build_fact.sql`), la mayor parte no se ve.
  Los meses tirados casi nunca caen donde su versión es la vigente: en el caso de Juan, la v28 rige desde jun-26 y los meses tirados son ene-mar-26.
  Aplicando la regla de `version_vigente_por_mes` sobre `mart.master_versiones_tipadas`, el daño se queda en
  **40 filas-mes, 11 obras y 15 partidas, que publican 0 o no tienen fila**, con 46.889,16 € de `importe_mes` y 186.196,48 € de `importe_origen`.
  Obras: 0601, 0615, 0635, 0637, 0644, 0651, 0656, 0662, 0668, 0677 y 0695, meses entre mar-21 y ago-26.
  30 de esas 40 tienen fila en `mart` con importe 0. Las otras 10 no tienen fila, porque `meses_partida_master` no conoce el mes en ninguna versión.
  *Hipótesis sin demostrar*: que la réplica de la regla de vigencia a nivel de obra coincida fila a fila con la del build (no se ha comparado entera).
- `cierre` toma los importes master de `stg.presupuesto`, no de `plan_mensual` (`cierre/02_build_fact.sql`, líneas 8-40), así que su importe no se ve afectado.

## 4 · Qué habría que cambiar (no implementado)

**Dónde**: línea 515 de `08_plan_mensual.sql`, y el comentario de las líneas 512-513.
El filtro no protege de nada. Tira la fila pero ya ha contaminado la siguiente, y aun con datos corruptos (0571) publica la bajada de −62,97 M€.
Hay tres opciones:

1. **Quitar el tope** (recomendada). Se publica el literal de Sigrid, que es lo que Juan valida.
   Cada serie vuelve a cuadrar con `stg.presupuesto`, porque `pct_mes` telescopa exactamente.
2. **Filtrar antes de calcular `pct_mes`**, llevando el tope a `master_pct_efectivo`. El total cuadraría, pero enero-marzo de la 0686 saldrían a 0
   y abril también, lo que contradice a Sigrid mes a mes. No se recomienda.
3. **Quitar el tope y publicar una marca** (columna o aviso de `init.sh`/diccionario) para los acumulados > 2,5.
   Así se señalan los datos de origen absurdos sin esconderlos. Sería el mismo patrón que `R-ALBARAN-ABSURDO`.

**Riesgos del arreglo**:
- `stg.plan_mensual` gana 8.646 filas.
- Aparecen importes enormes y reales de Sigrid: 0571 v23 publicará ~63 M€ de `importe_origen` en varios meses.
  Quien sume `stg` sin filtrar versión los verá.
- En `mart` cambian las 40 filas vigentes: +46.889 € de `importe_mes`, más `fact_seguimiento_categoria`, `v_pbi_*` y `cp_tipologia` aguas abajo.
  Negocio tiene que saberlo: son meses cerrados, de 2021 a 2026.
- `08_plan_mensual.sql` está en `FICHEROS_DEL_SELLO` (`build_stg_step.py:96`), así que tocarlo fuerza la **reconstrucción completa de las 920 obras** esa noche.
  Eso pesa en los créditos de CPU del servidor compartido.
- Ningún test fija hoy el 2,5 (buscado en `tests/`). Haría falta uno que proteja el invariante `SUM(pct_mes) = último pct_acumulado` por serie.
- La ficha del diccionario de `stg.plan_mensual` debería decir que `pct_acumulado` puede pasar del 100 %, y por qué.
- Son 2.785 series en origen con % > 250 %. Las 29 con más de 10.000 % convendría pasárselas a Negocio para que las corrija en Sigrid,
  igual que las partidas que no cierran al 100 %.
