<!-- specs/F-025-ventana-negocio-build/mediciones.md -->
# F-025 · Mediciones · La línea base, con sus fuentes

Todo lo de aquí está **medido el 2026-09-02**, en **solo lectura** y con
consultas ligeras: `stg.obras` (583 filas), `stg.fases` (4.551), `stg.partidas`
(390.501), `maestro.obras` (919), `cierre.v_pbi_cierre_cabecera` (583) y
`_meta.etl_runs` (2.303). **No se ha contado `stg.plan_mensual`, `stg.presupuesto`
ni el fact**: son millones de filas y el servidor está recuperándose sin créditos.
Las cifras de esas tres vienen de `_meta.etl_runs` y de `progress/current.md`.

## 1 · La avería, tramo a tramo (`_meta.etl_runs`)

| Ejecución | Tramos | Filas | Min/tramo (media) | Máx |
|---|---|---|---|---|
| 15 nocturnas del 19-ago al 01-sep | 60/60 | 29,6-29,8 M | **1,55-1,59** | ~5 |
| 2026-09-01 08:20 (stage manual de F-052) | 60/60 | 29.762.403 | **7,91** | 18,03 |
| **2026-09-02 02:00 (la que murió)** | **5 de 60 OK** | **6.436.281** | **40,77** | **49,21** |

Lecturas que importan:

- La nocturna sana cuesta **~94 min** solo en `plan_mensual` (60 × 1,57).
- El día 01 el servidor **ya venía castigado** (7,91 min/tramo): las 8 h 15 del
  stage manual de F-052 dejaron la hucha de créditos vacía y la nocturna del 02
  arrancó sin ella. La avería tiene dos causas, no una: **trabajo de más** y
  **hucha vacía**.
- 40,77 / 1,57 ≈ **26 veces más lento**, coherente con un `B1ms` capado al 20 %
  de un núcleo más la contención de `albaranes` y `partes`.

## 2 · El censo de obras (universo `stg.obras`, 583)

Actividad = mes más reciente con fase cerrada (`stg.fases.anio`/`mes`).

| Antigüedad de la última fase | Obras |
|---|---|
| ≤ 3 meses | 33 |
| ≤ 6 meses | 38 |
| **≤ 12 meses** | **44** |
| ≤ 18 meses | 59 |
| ≤ 24 meses | 77 |
| ≤ 36 meses | 89 |
| **Sin ninguna fase** | **217** |

Y los censos por criterio, que es lo que decide DA-1:

| Criterio | Congela | Falsos positivos (congelaría algo vivo) |
|---|---|---|
| Sin fase en **12 meses** | **322** | 0 (por construcción) |
| Sin fase en **24 meses** | 289 | 0 |
| `maestro.obras.estado_id = 25` | 462 | **7** obras con fase en los últimos 12 meses |
| **Fecha real de fin informada** (`cierre.v_pbi_cierre_cabecera.fecha_fin_real`) | 247 | **6**; y deja **298** obras paradas >12 m sin congelar |
| 12 meses **+ veto de `estado_id = 15`** | **319** | 0; el veto rescata 3 obras |

Reparto por estado de Sigrid (583 obras de `stg.obras`):

| `estado_id` | Obras | Sin fases | Con fase ≤12 m |
|---|---|---|---|
| 25 | 462 | 140 | **7** |
| 15 (EN CURSO) | 98 | 64 | 31 |
| resto (9 valores) | 23 | 12 | 6 |

**Conclusión de negocio:** ninguna marca de Sigrid es fiable por sí sola. `25`
congelaría 7 obras que siguen cerrando meses y la fecha de fin real falla en los
dos sentidos. La actividad medida es objetiva y se equivoca solo por exceso de
trabajo, nunca por dato viejo.

## 3 · El peso, estimado (no medido)

`stg.plan_mensual` no se puede contar hoy. **Estimación** con el proxy
`partidas × fases` por obra, que aproxima el peso de los ámbitos reales (3 y 7):

| Grupo | Obras | Partidas | Proxy de peso | % |
|---|---|---|---|---|
| Con fase ≤ 12 m | 44 | 52.279 | 1.122.729 | **26,2 %** |
| Entre 12 y 24 m | 33 | 34.990 | 940.108 | 21,9 % |
| Más de 24 m | 289 | 146.578 | 2.203.926 | 51,4 % |
| Sin fases | 217 | 25.231 | 25.231 | 0,6 % |

Con el criterio de 12 meses se congela el **73,3 %** del proxy. **Es una cota, no
una medición**: el proxy no cubre los ámbitos master (8 y 11), cuyo peso depende
de `cardinality(planif)` y se concentra en obras vivas, así que **el ahorro real
será menor**. Medirlo de verdad es **T1**, con la consulta de pesos que la
nocturna ya ejecuta cada noche (`SQL_PESOS_PLAN_MENSUAL`).

## 4 · Dos cifras que salen de restar, y hay que confirmar

- El build reconstruye **687 obras** (universo de `stg.presupuesto`), y `stg.obras`
  tiene **583**: hay del orden de **104 obras** que se construyen en
  `stg.plan_mensual` y que **el fact descarta** con su `INNER JOIN stg.obras`
  (`mart/02_build_fact.sql:232`). Son las administrativas (GG, CM, POSTV, VAR…).
  Su peso lo dará T1; es DA-3.
- `stg.plan_mensual` completa son **29.762.403** filas (01-sep). La avería la dejó
  en 6.436.281, el **21,6 %**.

## 5 · Las consultas exactas

Todas por el MCP de solo lectura (`mcp-bbdd`, rol `mcp_sigrid_dm_ro`).

```sql
-- Censo de actividad
WITH ult AS (
  SELECT o.obra_id,
         MAX(make_date(f.anio, GREATEST(f.mes,1), 1)) AS ultimo_mes_fase,
         COUNT(f.fase_id) AS n_fases
  FROM stg.obras o
  LEFT JOIN stg.fases f ON f.obra_id = o.obra_id AND f.anio BETWEEN 1990 AND 2100
  GROUP BY o.obra_id)
SELECT COUNT(*),
       COUNT(*) FILTER (WHERE n_fases = 0),
       COUNT(*) FILTER (WHERE ultimo_mes_fase >= date '2026-09-01' - INTERVAL '12 months')
FROM ult;

-- Peso proxy por grupo: partidas x fases (ver §3)
-- Estado de Sigrid: maestro.obras.estado_id LEFT JOIN stg.obras
-- Tramos de la avería: _meta.etl_runs, step LIKE 'build_stg.build_plan_mensual.tramo%'
```

## 6 · Lo que queda por medir (y bloquea decisiones)

| Qué | Cuándo | Decide |
|---|---|---|
| Peso real por obra (`SQL_PESOS_PLAN_MENSUAL`) | T1 | Si la feature merece la pena y DA-2/DA-3 |
| Tamaño de `stg.plan_mensual` y tuplas muertas | T2 y T33 | Si el `DELETE` selectivo aguanta o hay que particionar |
| Créditos de CPU al terminar la nocturna acotada | T34 | R29, el criterio de aceptación |
| Coste de hashear `raw.obrparpre.planif` por obra | opcional | Si la firma puede cubrir la laguna de R20 |
