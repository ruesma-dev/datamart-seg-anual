<!-- specs/F-110-fin-obra-cuatrimestral/design.md -->
# F-110 · Diseno tecnico

`sql/` = `etl_sigrid/infrastructure/postgres/sql/`. Todo medido el 2026-09-25 en
solo lectura sobre el build del 25 (diccionario v32); consultas en
`progress/spec_F-110.md` §Consultas. Cambio **acotado a `retenciones.fin_obra`**:
ni objetos nuevos ni objetos que desaparezcan.

## Medidas que fijan el diseno

**Las cuatrimestrales.** 131 fichas de obra tienen alguna version master y **117
alguna `Cuatrimestral`** (404 versiones por ambito), las 117 en `raw.obr` y 81 de
ellas ya con inicio de garantia; 805 de las 922 no tienen ninguna. En las 117, la de mayor numero = la de mayor fecha efectiva =
la de mayor fecha de creacion (0 discrepancias). La marca de Sigrid
(`stg.version_master_vigente`, `conext` 15) coincide en 107; en 7 apunta a una
version posterior que no es cuatrimestral (5 «Sin clasificar», 2 «Cierre
mensual») y 3 no tienen marca.

**El ultimo mes.** Ultimo mes con `importe_mes <> 0` frente a ultima fila de la
version: iguales en 102 de 117; en 15 la cola sin movimiento alarga hasta 10
meses (media 0,3). El coste acaba despues que la venta en 20 obras y nunca al
reves. Rango: 2019-11 a 2028-03.

**Efecto sobre la retencion viva de los efectos** (8.247.267,15 € con obra, 179
obras; la misma base que la ficha de F-095):

| Fuente | Antes (F-095) | Despues (F-110) |
|---|---|---|
| INICIO_GARANTIA | 97 obras · 5.026.655,18 € | 97 · 5.026.655,18 € (igual) |
| ULTIMO_CIERRE_MAS_1_MES | 67 · 3.120.260,42 € | — |
| ULTIMO_CUATRIMESTRAL_MAS_1_MES | — | **32 · 2.960.583,38 €** |
| Sin fecha | 15 · 100.351,55 € | **50 · 260.028,59 €** |

De las 67 del ultimo cierre, 32 toman fecha por cuatrimestral y **35 se quedan
sin fecha (159.677,04 €)**: 29 terminadas (111.389,14 €, con su ultimo cierre
entre 2015 y 2022, casi todas antes de que hubiera cuatrimestrales), 4 en curso sin
cuatrimestral (`1-0723`, `1-0721`, `1-0720`, `1-0719`: 45.577,49 €) y 2 en
estado 17 (2.710,41 €). `terminada_sin_fin_obra` sobre lo vivo: 8 obras /
42.647,96 € -> **37 / 154.037,10 €**. En las 922 obras: 198 / 150 / 574 ->
198 / **36** / **688** (34 del cierre y 2 que no tenian fecha).

**Como se mueve la fecha en las 32:** 15 obras EN CURSO (2.724.514,73 €) pasan a
un fin de obra **posterior**, +1 a +19 meses (media +6,6): es el caso que motivo
la decision. 16 pasan a uno **anterior** (211.549,15 €): 14 terminadas (-1 a
-20 meses, media -5,3) y 2 en curso (`1-0692`, `31-0606`), porque su ultima
cuatrimestral acaba antes que su ultimo cierre (la obra se alargo sobre el plan;
18 obras de las 36 estan asi). 1 igual.

**Estados de vencimiento, hoy (2026-09-25):**

| Cambio | Efectos vivos | Saldo contable (`v_retencion_contable_obra`) |
|---|---|---|
| VENCIDA -> PENDIENTE | **0** | **0** |
| PENDIENTE -> VENCIDA | 1 obra (`1-0692`) · 43.476,54 € | 1 obra · 3 filas · 43.476,54 € |
| VENCIDA -> SIN_FIN_OBRA | 31 · 114.099,55 € | 102 obras · 770 filas · 643.734,57 € |
| PENDIENTE -> SIN_FIN_OBRA | 4 · 45.577,49 € | 4 obras · 17 filas · 45.577,49 € |
| SIN_FIN_OBRA -> VENCIDA | 0 | 1 obra · 1 fila · -12.571,28 € |

**Ningun vencimiento pasa de VENCIDA a PENDIENTE hoy**: en las obras en curso el
respaldo viejo (agosto de 2026 + 1 + 12 meses = septiembre de 2027) ya caia en el
futuro; lo que cambia es la FECHA (medio ano mas tarde de media). Saldo contable
por fuente (filas con obra, 10.518.015,66 €): antes 178 / 6.496.375,95 ·
140 / 3.819.683,33 · 81 / 201.956,38; despues 178 / 6.496.375,95 ·
**35 / 3.117.799,99 · 186 / 903.839,72**.

**Coste.** El cruce version -> `stg.plan_mensual` de las 117 obras (1,23 M filas
de 30 M) tardo 11 s por el MCP y ~36 s la medicion completa por una conexion de
solo lectura: se estima **+15-40 s** al sub-paso `fin_obra` (hoy el paso entero
tarda 65 s).

## Decisiones abiertas (el humano valida; recomendada en negrita)

**D1 · Que version es «la ultima cuatrimestral».** **(A) La de mayor numero con
`tipo_master = 'Cuatrimestral'` en `mart.master_versiones_tipadas`**: literal a
la decision y sin ambiguedad medida (numero = fecha efectiva = creacion).
(B) La ultima entre `Planif Inicial`, `ABC` y `Cuatrimestral` —las que
`R-VERSION-MASTER` da por plan vigente—: fecha a 3 obras mas (`1-0723` y `1-0630`
solo tienen Planif Inicial, `1-0719` solo ABC; +29.184,48 € de lo vivo,
PENDIENTE -> SIN_FIN_OBRA baja de 4 a 2 obras). Coste: cambiar una lista `IN`.
(C) La vigente de Sigrid (`conext` 15): descartada, en 7 obras es un cierre
mensual o una version sin clasificar, y 3 no la tienen.

**D2 · Que es «el ultimo mes planificado».** **(A) El mayor `anio_mes` con
`importe_mes <> 0` en los ambitos 8 y 11** (R5): el ultimo mes con algo planificado,
de coste o de venta. (B) Solo venta (11): acaba antes en 20 obras, todas
terminadas y ya vencidas (no cambia ningun estado hoy). (C) La ultima fila con o
sin movimiento: descartada, 15 obras se alargan hasta 10 meses con meses que
Sigrid arrastra congelados.

**D3 · «+ 1 mes».** **El ultimo dia del mes siguiente**, la misma convencion que
el respaldo de F-095 (`(mes + INTERVAL '2 months' - INTERVAL '1 day')::DATE`).
Alternativa: el dia 1 del mes siguiente (29-30 dias antes).

**D4 · De donde se lee y la dependencia del paso.** **(A) La version de
`mart.master_versiones_tipadas` y los meses de `stg.plan_mensual`, con
`depends_on` intacto (`["ingest_raw"]`)**. `mart.master_versiones_tipadas` es la
tabla de 4.447 filas que ya clasifica las versiones (F-078); leerla evita una
tercera copia del `CASE` de `tipo_master` y barrer los ~12 M de filas master para
clasificar. En `run-all`, `build_stg` y `build_mart` van antes que
`build_retenciones` (orden topologico DFS sobre la lista, R16): **el fin de obra
sale de la MISMA noche y desaparece el desfase de una noche de F-095**. Si
`build_stg` o `build_mart` fallan, `build_retenciones` corre igual con las tablas
de la noche anterior (ninguna de las dos se dropea fuera de su propio build, y
`execute_sql_file` corre cada fichero en una sola transaccion). Es el patron de D3/D7 de F-095.
(B) Solo `stg`, replicando el `CASE` de `mart/06_cp_tipologia.sql` con test de
igualdad textual: sin lectura de `mart`, pero tercera copia de la regla y un
barrido de ~16 s mas. (C) Declarar `build_mart` en `depends_on`: descartada,
un fallo de `stg` dejaria sin construir TODO `retenciones` (saldo contable
incluido).

**D5 · La columna `ultimo_cierre`.** **Se retira** junto con la lectura de
`cierre` y la guarda de F-095 (R21): mantenerla informativa conservaria la
dependencia de `cierre`, el desfase de una noche y la guarda, para una columna
que ya no decide nada. `fin_obra` no es de consumo recomendado y ninguna vista
la lee. Alternativa: dejarla como informativa.

**D6 · Confirmacion, no reapertura.** La regla [H] deja sin fecha 35 obras con
retencion viva (y 102 de saldo contable, 643.734,57 €, que hoy salen VENCIDAS),
casi todas cerradas antes de 2021, y adelanta `1-0692` a VENCIDA porque su ultima
cuatrimestral es de 2025-02. Se aplica tal cual; el humano lo confirma a la vista
de las cifras. Si quisiera un paso mas, es otra decision y otra ficha.

## Ficheros a crear

1. `tests/test_f110_fin_obra_cuatrimestral.py` — suite offline por requisito
   (texto del SQL sin comentarios `--`, YAML, cableado del step y orden
   topologico de `main.build_pipeline_steps`), al estilo de `test_f095_*`.

## Ficheros a modificar

- `sql/retenciones/05_fin_obra.sql` — cabecera reescrita (regla [H], D1-D5,
  medidas); guarda nueva (abajo); fuera el CTE `cierres`, dentro `cuatrimestral`
  y `plan`; en `base`, `version_cuatrimestral` y `ultimo_mes_planificado` donde
  estaba `ultimo_cierre`; en `fin`, los dos `CASE` nuevos; `COMMENT ON TABLE`
  al dia. `constantes`, `oc`, plazo, vencimiento e informativas, **sin tocar**.
- `sql/retenciones/06_views_contables.sql` — solo el comentario de la linea
  `SIN_FIN_OBRA` (R18). Ni una linea de SQL.
- `etl_sigrid/application/steps/build_retenciones_step.py` — docstring y
  comentario de `depends_on` (R17). Codigo, `SUB_PASOS`, `name`, `stage` y
  `depends_on`, iguales.
- `tests/test_f095_retenciones_contables.py` — los tests que fijan la regla vieja,
  reescritos a la nueva (R21; lista cerrada en `tasks.md` T3), y la entrada
  `fin_obra` del contrato `CONTRATO_SQL`.
- `config/diccionario/retenciones.yaml` — ficha `fin_obra` (descripcion, cifras
  antes/despues, columnas `version_cuatrimestral` y `ultimo_mes_planificado`,
  fuera `ultimo_cierre`, valores de `fuente_fin_obra`); ficha
  `v_retencion_contable_obra` (`fuente_fin_obra.valores`, texto de SIN_FIN_OBRA).
- `config/diccionario/00_global.yaml` — `version` +1 y linea de historia. **Si
  F-108 o F-109 suben antes la version, se toma la siguiente al fusionar.**
- `docs/ARCHITECTURE.md` — el vineta «La retencion de proveedor la manda la
  contabilidad»: fin de obra = garantia -> ultimo cuatrimestral + 1 mes; lee
  `mart.master_versiones_tipadas` y `stg.plan_mensual` de la misma noche.
- `azure-apps/datamart_seg_anual.md` — fila de `retenciones.fin_obra` y parrafo de
  dependencias: deja de leer `cierre.fact_cierre_mensual`, lee
  `mart.master_versiones_tipadas` y `stg.plan_mensual`. Commit en `azure-apps`.

## Ficheros que NO se tocan

- `sql/retenciones/00`-`04`: movimientos, apuntes y saldo no cambian.
- `sql/mart/06_cp_tipologia.sql` y `sql/mart/02_build_fact.sql`: se LEE la
  tabla que construye el primero; la regla de `tipo_master` no se toca.
- `sql/stg/08_plan_mensual.sql`, `sql/stg/07_version_master_vigente.sql`.
- `sql/cierre/*`: `retenciones` deja de leerlo; `cierre` no cambia.
- `main.py`, `orchestrator.py`, `apply_grants_step.py`: la composicion ya pone
  `build_stg` y `build_mart` antes; se verifica con test (R16).
- `tests/test_f047_nocturna.py`: `depends_on == ["ingest_raw"]` sigue siendo cierto.
- `config/objetos_pendientes.yaml`: ningun objeto nuevo ni retirado.

## SQL de `05_fin_obra.sql` (capa `retenciones`, mismo numero de fichero)

Guarda, antes del `DROP` (R14), en el mismo `DO $$` que hoy:
`to_regclass('mart.master_versiones_tipadas') IS NULL` -> `RAISE EXCEPTION
'fin_obra: no existe mart.master_versiones_tipadas; lanza build-mart antes de
build-retenciones'`; `NOT EXISTS (... WHERE tipo_master = 'Cuatrimestral')` ->
`'fin_obra: ...'`; `NOT EXISTS (SELECT 1 FROM stg.plan_mensual WHERE ambito_id IN
(8, 11))` -> `'fin_obra: ...'`. Tres `RAISE`, los tres con el prefijo.

```sql
cuatrimestral AS (   -- D1 (A): la ultima por numero, en 8 u 11
    SELECT v.obra_id, MAX(v.version) AS version_cuatrimestral
    FROM mart.master_versiones_tipadas v
    WHERE v.tipo_master = 'Cuatrimestral'
    GROUP BY v.obra_id
),
plan AS (            -- D2 (A): ultimo mes con movimiento de esa version
    SELECT c.obra_id, c.version_cuatrimestral,
           MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ultimo_mes_planificado
    FROM cuatrimestral c
    LEFT JOIN stg.plan_mensual pm
           ON pm.obra_id = c.obra_id
          AND pm.version = c.version_cuatrimestral
          AND pm.ambito_id IN (8, 11)
    GROUP BY c.obra_id, c.version_cuatrimestral
),
```

En `base`: `LEFT JOIN plan pl ON pl.obra_id = obr.ide` (solo `obra_id`, R3) y
`pl.version_cuatrimestral`, `pl.ultimo_mes_planificado`. En `fin`:
`CASE WHEN b.fecha_inicio_garantia IS NOT NULL THEN b.fecha_inicio_garantia WHEN
b.ultimo_mes_planificado IS NOT NULL THEN (b.ultimo_mes_planificado + INTERVAL
'2 months' - INTERVAL '1 day')::DATE END AS fecha_fin_obra`, y su gemelo con
`'INICIO_GARANTIA'` / `'ULTIMO_CUATRIMESTRAL_MAS_1_MES'`, sin `ELSE`. Columnas
publicadas: las de hoy con `version_cuatrimestral, ultimo_mes_planificado` en
lugar de `ultimo_cierre`. La PK `(obra_id)` no cambia.

## Riesgos

**(a) Cuatrimestral vieja.** La ultima cuatrimestral puede ser antigua y acabar
antes que la obra (18 de 36 obras): el fin de obra ADELANTA respecto al cierre
(`1-0692`, D6). Es la regla decidida; la ficha lo dice. **(b) Frescura de
`stg.plan_mensual`** (F-025): una obra congelada lleva hasta 6 dias; congelar
exige no tener actividad, y una cuatrimestral nueva es actividad. **(c) Coste**
+15-40 s de la nocturna sobre el Postgres compartido (creditos de CPU); se mide
en la verificacion. **(d) Orden sin `depends_on`**: si alguien moviera
`build_retenciones` delante de `build_mart` en la lista, leeria la tabla de la
noche anterior sin error; el test de R16 lo impide. **(e) Version del
diccionario** en carrera con F-108/F-109 (se resuelve al fusionar).

## Plan de verificacion (MANUAL, humano, en el entorno que autorice)

**Antes** (solo lectura): las tres consultas de `progress/spec_F-110.md`
§Consultas reproducen §Medidas. **Despues** de `python main.py
build-retenciones` y `python main.py apply-grants`: (1) `fin_obra` = 922 filas
(= `raw.obr`), sub-paso `fin_obra` < 2 min en el log; (2) por fuente en las 922:
~198 / ~36 / ~688; (3) sobre la viva de los efectos, ~97 / 5,03 M,
~32 / 2,96 M y ~50 / 0,26 M; (4) `SELECT estado_vencimiento, COUNT(*),
SUM(saldo) FROM retenciones.v_retencion_contable_obra GROUP BY 1` frente a
§Medidas; (5) `1-0686`: `ultimo_mes_planificado` 2026-11-01, fin 2026-12-31,
vencimiento 2027-12-31; (6) `check-declarados`, `check-unicidad`,
`check-relaciones`, `check-diccionario` verdes; `publicar-diccionario` y
reinicio del MCP; (7) nueva imagen desplegada (sin ella la nocturna sigue con la
regla vieja).
