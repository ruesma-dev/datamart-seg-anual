<!-- docs/referencia/05_caso_obrfasamb_version_duplicada.md -->
# Caso: versiones master duplicadas en `raw.obrfasamb`

> Origen: investigación interna sobre la BBDD local (T11 de F-019) · Fecha: 2026-08-13
> Redactado directamente en Markdown por el arnés; no procede conversión.
> Datos verificados contra el `raw` local ingerido de Sigrid el 2026-07-30.

## Qué pasa, en una frase

En Sigrid (tabla `obrfasamb`, fases por ámbito) hay **versiones master
guardadas DOS veces con el mismo número de versión**, y el ETL —que casa
presupuesto y fase por `(obride, amb, fas)`— duplica entonces **todas** las
posiciones mensuales de esas versiones en `stg.plan_mensual`.

## Las obras afectadas (a fecha del raw del 2026-07-30, las únicas)

| obra_id | código de obra | nombre | versión duplicada | registros duplicados (`ide` de `obrfasamb`) |
|---|---|---|---|---|
| 2403576 | **0694** | 31 VIVIENDAS DAZIA CALLE CANARIAS | v26 (ámbitos 8 y 11) | amb 8: 29916 (20/07/2026) y 29983 (23/07/2026) · amb 11: 29918 (20/07/2026) y 29985 (23/07/2026) |
| 2491656 | **0697** | AMPLIACIÓN PABELLÓN A COLEGIO EL PR… | v13 (ámbitos 8 y 11) | amb 8: 29949 (22/07/2026) y 29977 (23/07/2026) · amb 11: 29951 (22/07/2026) y 29979 (23/07/2026) |

Detalles relevantes:

- En ambas obras, la versión duplicada es **la siguiente a la vigente**
  (vigentes según `conext` cod=15: 0694→25, 0697→12). `stg.plan_mensual`
  lleva TODAS las versiones, así que las gemelas entran igual.
- El **segundo registro de las cuatro parejas es del 23/07/2026** y los
  `ide` son consecutivos (29977–29985): parece una misma acción en Sigrid
  ese día (¿un re-guardado de la versión por el JO? ¿una migración?).
- Dentro de cada pareja, los dos registros comparten `plafec` (mes ancla)
  pero difieren en `fec` (fecha de creación) y en el texto `res`
  («Versión 26 (20/07/2026)» vs «Versión 26 (23/07/2026)»).

## Cómo replicarlo a mano

Detector genérico de duplicados (cualquier obra, cualquier versión):

```sql
SELECT obride AS obra_id, amb, fas, count(*) AS n
FROM raw.obrfasamb
WHERE plafec IS NOT NULL AND plafec > 0
GROUP BY 1, 2, 3
HAVING count(*) > 1
ORDER BY 1, 2, 3;
```

Ver los registros duplicados con sus fechas (ejemplo con la obra 0697):

```sql
SELECT obride AS obra_id, amb, fas, ide, res,
       stg.fn_sigrid_date_to_date(fec)    AS fec_creacion,
       stg.fn_sigrid_date_to_date(plafec) AS plafec
FROM raw.obrfasamb
WHERE obride = 2491656 AND fas = 13
  AND plafec IS NOT NULL AND plafec > 0
ORDER BY amb, fec;
```

Ver las filas gemelas resultantes en `stg.plan_mensual` (misma clave
lógica duplicada):

```sql
SELECT presupuesto_id, ambito_id, anio_mes, posicion_mes, count(*) AS n
FROM stg.plan_mensual
WHERE obra_id IN (2403576, 2491656) AND ambito_id IN (8, 11)
GROUP BY 1, 2, 3, 4
HAVING count(*) > 1
LIMIT 20;   -- 16.980 claves gemelas, 30.860 filas de más en total
```

## Por qué el ETL las duplica

`stg/08_plan_mensual.sql`, CTE `master_planif`: el presupuesto
(`stg.presupuesto`) se casa con la fase por

```
ON fa.obra_id = pp.obra_id AND fa.ambito_id = pp.ambito_id
   AND fa.version_master = pp.fase_num
```

Si `raw.obrfasamb` tiene dos filas con el mismo `(obride, amb, fas)`, cada
fila de presupuesto de esa versión casa con LAS DOS y todas sus posiciones
mensuales salen duplicadas.

## Consecuencias conocidas

1. **Doble conteo**: el plan master de las versiones duplicadas está
   contado dos veces en `stg.plan_mensual` y en cualquier consumo que no
   deduplique (30.860 filas de más con el raw del 30-jul).
2. **No determinismo de reparto**: las ventanas del SQL
   (`MAX ... ROWS UNBOUNDED PRECEDING`, `LAG ... ORDER BY posicion_mes`)
   quedan subespecificadas cuando `posicion_mes` empata entre gemelas; el
   reparto de `pct_acumulado`/`pct_mes` entre las dos filas depende del
   plan de ejecución de Postgres (estable para un plan dado, distinto
   entre planes). Esto hizo fallar el checksum byte a byte del T11 de
   F-019 aunque los valores por clave fueran idénticos; el criterio quedó
   enmendado en la spec de F-019 (R13).

## Qué queda por decidir (feature F-022)

Pregunta de negocio, previa a tocar código: ¿el doble guardado es un error
de uso de Sigrid (y se corrige/purga allí), o debe el ETL desempatar por su
cuenta (p. ej. quedarse con el registro de `fec` más reciente por
`(obride, amb, fas)`)? Tras la decisión, el arreglo probable es un dedupe
determinista en la subconsulta `fa` de `08_plan_mensual.sql`, que elimina a
la vez el doble conteo y el no determinismo.
