<!-- progress/explore_F-052.md -->
# Exploración F-052 · la obra 0599 y el silencio de los INNER JOIN

Medido el **2026-08-31** contra la base, en **solo lectura** (`pg.filas_solo_lectura`,
`READ ONLY` + `statement_timeout`). Ninguna consulta agotó su timeout: **todo está MEDIDO** salvo lo marcado NO COMPROBADO.

## 1 · El eslabón roto: NO es el que decía la hipótesis

La hipótesis del líder («la cadena no llega a una raíz») es **incorrecta**: en la 0599 la
cadena **sí llega a la raíz `CD`**. La corta un **nodo INTERMEDIO con `cod` = cadena
vacía** (no NULL: `length(cod)=0`), y el culpable es `AND h.cod <> ''` de la **línea 78**
de `stg/04_partidas.sql` (y su gemelo de la 58): el recursivo se niega a *descender a
través* de ese nodo y **amputa el subárbol entero**. Censo de `raw.obrparpar` (390.520)
contra `stg.partidas` (389.178): **1.335 partidas con `cod` válido no llegan**, más los
**7 nodos con `cod=''`** que el filtro descarta directamente → **1.342 perdidas**.

| Causa | Partidas | Obras |
|---|---|---|
| **(b) un ancestro tiene `cod=''`** → lo corta `cod <> ''` | **1.323** | 1 (0599) |
| **(d) ciclo en la cadena de `padide`** | **12** | 3 |
| (a) `padide` a un `ide` inexistente · (c) la cadena sale a otra obra | **0** | — |
| *el propio nodo tiene `cod=''`* (los 7) | 7 | 3 |

**El nodo cortante, con nombre y apellidos.** La raíz `CD COSTES DIRECTOS` de la 0599
(ide 274277, **sí está** en `stg.partidas`) tiene cuatro hijos: **280353** «FASE 1 -
MOVIMIENTO TIERRAS Y CIMENTACIÓN», **280354** «FASE 2 - OBRA CIVIL» y **280356** «FASE 2
- INSTALACIONES», los tres con `cod=''`; más 307427 `cod='999'`, el único que sobrevive.
Alguien montó el árbol de CD **por fases de obra** y dejó el código en blanco. De esos
tres cuelgan 36 hijos directos y **1.323 descendientes** hasta 5 niveles: de las **1.443**
partidas que la 0599 tiene en `raw` llegan **117**, repartidas **CD 3, CI 101, CP 13**.

Los **12 ciclos** son otra cosa: **2 auto-bucles** (`padide = ide`) —ide 310512 «CHIMENEA
IGNIFUGA» (0630) e ide 375474 «LEGALIZACIÓN Y PUESTA EN MARCHA» (0686)— y un bucle mutuo
en la 0565, 279988 (`20.12`) ↔ 279997 (`20.12.09`), que arrastra 9 hermanos. Hoy el
recursivo **no se cuelga** porque no son alcanzables desde ninguna raíz; **cualquier
arreglo que relaje el filtro necesita corta-ciclos**.

**Cómo se midió**: CTE recursivo que parte de las huérfanas y **sube** por `padide` acumulando `vis` (visitados), `cod_vacio`, `ciclo` (`pa.padide = ANY(vis||pa.ide)`) y `otra_obra`, con `WHERE NOT (pa.ide=ANY(vis)) AND pasos<40`; clasificado por el último salto de cada origen.

## 2 · ¿De la 0599 o general? Residuo histórico, no está creciendo

| Obra | Filas de `stg.presupuesto` sin ficha | Partidas | Filas de la obra |
|---|---|---|---|
| **0599 TANATORIO MAJADAHONDA** | **104.366** | 1.208 | 108.790 (**96 %**) |
| 0618 SOTOGRANDE · 0613 RICHMOND PARK | 180 · 103 | 3 · 1 | 40.087 · 123.914 |
| 0686 VALDEBEBAS · 0565 PORRASSA · 0630 EL PRADO | 86 · 1 · 1 | 1 · 1 · 1 | 242.700 · 130.131 · 5.624 |

**Es una forma de teclear en Sigrid de 2019-2021.** Los 7 nodos con `cod=''` van del `ide` 280353 al 297563 y el `ide` máximo de la tabla es **417053**: ~120.000 partidas creadas después **sin un solo caso**. Las obras afectadas arrancan entre 2018 y 2021 y **todas menos una están terminadas** (0565 2020-12, 0613 2022-04; 0599, 0618 y 0630 2022-12). Los de 0613 y 0618 no son fases sino comentarios («NO USAR», `----SOBRECOSTE GRUPO ELECTROGENO----`). **No crece, pero no está muerto**: la **0686 VALDEBEBAS sigue viva** (última fase 2026-07-31) y arrastra un auto-bucle creado en 2024 — hoy 86 filas a 0,00 €, mañana quizá dinero.

## 3 · El dinero, con una cuenta defendible

**La cuenta.** En los ámbitos reales cada `fase_num` de `stg.presupuesto` es el **acumulado
a origen** de ese cierre (base del telescopado de F-042): sumar todas las fases cuenta el
mismo euro N veces. Lo honesto es **quedarse con el último cierre** —la 0599 tiene 29
fases, la última es la **28, abr–dic 2022**— y sumar su `importe` por ámbito real:

```sql
WITH mx AS (SELECT ambito_id, max(fase_num) f FROM stg.presupuesto
            WHERE obra_id=1442383 AND ambito_id IN (3,7) GROUP BY 1)
SELECT s.ambito_id, EXISTS (SELECT 1 FROM stg.partidas p WHERE p.partida_id=s.partida_id),
       count(*), sum(s.importe) FROM stg.presupuesto s JOIN mx
  ON mx.ambito_id=s.ambito_id AND mx.f=s.fase_num WHERE s.obra_id=1442383 GROUP BY 1,2;
```

| 0599 · cierre 28 | Con ficha (se publica) | Sin ficha (se pierde) | Real |
|---|---|---|---|
| **3 COSTE REAL** | 1.369.592,93 € | **2.624.793,46 €** | 3.994.386,39 € |
| **7 VENTA REAL** | 0,00 € | **4.066.989,23 €** | 4.066.989,23 € |

**La cifra publicable: el datamart oculta 2.624.793,46 € de coste directo ejecutado de la 0599, el 65,7 % de su coste.** Y lo grave es el margen: hoy el datamart dice que la 0599 vendió 4.066.989,23 € y costó 1.369.592,67 € → **margen 66,3 %**. El real es **1,8 %** (72.602,84 €).

Tres comprobaciones cruzadas cuadran al céntimo: `mart.fact_seguimiento_mensual` publica de la 0599 `sum(importe_mes)` = **1.369.592,67 €** en el ámbito 3 y **cero filas** en el 7 y el 11; `cierre.fact_cierre_mensual` publica en sus 28 meses **DIRECTOS = 0,00 €**, INDIRECTOS 693.162,89, GENERALES 676.429,78 (suma = 1.369.592,67) y VENTA 4.066.989,23. **La misma base publica hoy una obra con 4 M€ de venta y 0 € de coste directo**, y nada chirría. **Las otras cinco obras: 0,00 €**, misma cuenta.

## 4 · Qué más se pierde en silencio (medido hoy)

| # | Fichero:línea | Qué descarta | Filas HOY |
|---|---|---|---|
| 1 | `stg/04_partidas.sql:57-58` y **`:77-78`** (`cod <> ''`) | 7 nodos + **1.335 descendientes** | **1.342 partidas** |
| 2 | `mart/02_build_fact.sql:233,258,288,318` `JOIN stg.partidas` | filas de `stg.plan_mensual` sin ficha de partida | **183.756** (0599: 183.530) |
| 3 | `mart/02_build_fact.sql:232,257,287,317` `JOIN stg.obras` | filas de `stg.plan_mensual` de obras ausentes de `stg.obras` | **82.815** en 19 obras |
| 4 | `stg/03_obras.sql:125` `WHERE rn = 1` | **48 obras** duplicadas por `codigo_obra` | ver abajo |
| 5 | `stg/03_obras.sql:106-116` (lista negra + `[0-9]{5,}`) | obras administrativas/prueba | **289**, correcto |
| 6 | `stg/06_presupuesto.sql:91` `JOIN raw.obr` | `obride` inexistente en `raw.obr` | **270** |
| 7 | `stg/08_plan_mensual.sql:373` `AND pp.fase_num >= 1` | cierres reales de fase 0 (estudio) | **399.519** |
| 8 | `stg/08_plan_mensual.sql:514` `NOT (pct=0 AND pct_mes=0)`, `pct<=2.5` | pre-arranque y acumulados > 250 % | **NO COMPROBADO** (barrer 7,7 GB) |
| 9 | ámbitos 1,2,4,5,9,10,12,13,14,15 nunca entran al fact | filas de `stg.presupuesto` que el fact no mira | **6.720.239**, por diseño |

**Hallazgo nuevo (fila 4), de la misma familia que F-052.** El desempate `rn=1` de
`stg/03_obras.sql` elige, en tres obras reales, **el `ide` vacío**:

| Código | `ide` que gana | Presupuesto | `ide` que pierde | Presupuesto |
|---|---|---|---|---|
| **0517** COLEGIO SESEÑA II | 1060846 | **207** | 1088657 | **158.737** |
| **0252** C.P. PRIMO DE RIVERA | 587639 | **22** | 650280 | **28.511** |
| **0720** PROMIRIS (viva) | 2824201 | **0** | 2759241 | **7.317** |

Las tres tienen **0 filas en `mart.fact_seguimiento_mensual`**: **tres obras más invisibles**, por otra causa. Con la cuenta de la sección 3: **0517 = 6.105.401,62 € de coste y 6.814.253,09 € de venta; 0252 = 4.547.711,35 € y 4.129.990,44 €**. La 0606 PUY DU FOU tiene además un `ide` perdido con 1.811.434,92 / 1.890.560,92 mientras el ganador **sí** publica. Las otras 15 obras de la fila 3 son `OBRA PRUEBA`, `POSTVENTA` y `VAR`: descarte correcto.

## 5 · Qué se rompería si se arregla

1. **Cambian totales publicados de la 0599, y mucho**: coste real ×2,9 (1.369.592,67 → ~3.994.386 €), venta de 0 a 4.066.989,23 €, margen del 66,3 % al 1,8 %. Informes o capturas previas **dejarán de cuadrar**: hay que avisar, no colarlo.
2. **Entran ~183.756 filas** en `mart.fact_seguimiento_mensual` (+3,5 % sobre 5.297.341) y aparecen dos combinaciones que hoy no existen: 0599 × ámbito 7 y 0599 × 11. Hay que **repasar `check-unicidad`** (con `--timeout 300`).
3. **`ruta_capitulos` queda rara**: si el recursivo atraviesa el nodo vacío heredando de `CD`, sale `'CD >  > 01.01'` y `mart.v_dim_partida_niveles` (`05b`, `string_to_array(...,' > ')`) genera un nivel en blanco en «Árbol Presupuesto».
4. **La capa `cierre` se mueve entera para la 0599**: `cierre/02_build_fact.sql` filtra por `p.categoria` (líneas 100/114/128 y 220/234/248), las 1.323 partidas heredarían `CD` y **DIRECTOS pasaría de 0,00 € a ~2,62 M€** en 28 meses, arrastrando `v_pbi_cierre_cabecera`, `v_pbi_planif_vs_real` y las de detalle; `mart.fact_seguimiento_categoria` gana filas `CD` donde hoy no hay ninguna.
5. **Riesgo de bucle infinito** si se relaja el filtro sin corta-ciclos. Y el **coste**: toca `stg.partidas` y de ahí abajo todo — nocturna completa (**3 h 45**, F-044).

## 6 · Lo que la spec tiene que decidir

- **(a) Cómo se atraviesa un capítulo sin código.** Recomendación medida: el filtro `cod <> ''` debe decidir **qué se publica, no por dónde se desciende**.
- **(b) Qué `ruta_capitulos` y `codigo_partida`** reciben esos nodos, para no romper `v_dim_partida_niveles` (efecto 3). Y **(c) corta-ciclos obligatorio** en el CTE: 12 casos vivos, uno en obra en curso; sin él, relajar (a) cuelga el build.
- **(d) Si el desempate `rn=1` de `stg/03_obras.sql:125` debe mirar quién tiene datos**, y si entra aquí o es feature propia: **tres obras más invisibles**, ~10,65 M€ de coste + 10,94 M€ de venta. *Recomendación: feature propia, fichada en el mismo trabajo.*
- **(e) La denuncia.** La tabla de la sección 4 es la lista de sitios a instrumentar. Guardián mínimo que habría cazado esto: **filas de `stg.plan_mensual` por (obra, ámbito) contra las del fact, con umbral y fallo por obra**.
- **(f) Si la causa se lleva a Sigrid.** Los 3 nodos sin código y los 2 auto-bucles son dato mal metido en el origen; como en F-050 aquí se protege el ETL, pero **no se puede esperar** al saneamiento: son obras cerradas de 2022 que nadie va a volver a tocar.
- **(g) Aviso a Negocio antes de publicar** el cambio de margen de la 0599: no es un arreglo silencioso, es un número que alguien pudo usar.
