<!-- progress/explore_F-047.md -->
# F-047 · Diagnóstico: qué borra `cierre.v_pbi_planif_vs_real`

**Fecha:** 2026-08-28 · **Autor:** líder · **Método:** lectura del código, sin
tocar la base (la base estaba inalcanzable, ver «Lo que falta verificar»).

## La respuesta

La nocturna **no deja de crear** la vista. **La destruye.**

```
etl_sigrid/infrastructure/postgres/sql/mart/03_agg_categoria.sql:17
    DROP TABLE IF EXISTS mart.fact_seguimiento_categoria CASCADE;
```

`cierre/06_views_planif_vs_real.sql` crea `cierre.v_pbi_planif_vs_real`
leyendo de `mart.fact_seguimiento_categoria` (líneas 17, 45 y 127 del propio
fichero). Es una vista, no una tabla: **cuelga** de esa tabla en `pg_depend`.
El `CASCADE` de la línea 17 se la lleva por delante.

`build_mart` corre **todas las noches** (`main.build_pipeline_steps`).
`build-cierre` **no** entra en `run-all` — se lanza a mano. Resultado: cada
noche la vista muere y nadie la recrea.

## Por qué encaja con toda la evidencia

| Hecho conocido | Lo explica |
|---|---|
| 2026-08-21: los cuatro build a mano → biyección exacta, 103 = 103 | `build-cierre` recreó la vista esa tarde |
| 2026-08-26 y 27: 103 fichas, 102 objetos, la huérfana **ha vuelto** | la primera nocturna posterior al 21 la borró |
| Falta **exactamente una** de 103, no un grupo | ver abajo: solo hay una víctima posible |

## Por qué solo cae esa vista, y no más

Barrido de dependencias cruzadas de los cinco esquemas manuales
(`cierre`, `compras`, `maestro`, `retenciones`, `auxiliar`):

- **`cierre` es el único** que lee de `mart`, y su única referencia es
  `mart.fact_seguimiento_categoria`, desde `06_views_planif_vs_real.sql`.
- `compras`, `maestro` y `retenciones` leen **solo de `raw`**.
- Las demás vistas de `cierre` (03, 04, 05) leen de `stg`, y **`stg` no
  dropea sus tablas**: el único `DROP` de todo `sql/stg/` es
  `stg/02_ambitos.sql:33`, sobre una vista propia. Por eso sobreviven.

Los `DROP ... CASCADE` de `sql/mart/` son siete (`01_ddl.sql:39`,
`03_agg_categoria.sql:17`, `05b:15`, `05_views_powerbi.sql` ×4). Solo el de
`03_agg_categoria.sql` tiene un dependiente fuera de `mart`.

## Lo que esto cambia respecto a la ficha

La ficha planteaba tres hipótesis —no entra en la nocturna, entra y falla en
silencio, se quedó fuera al añadirse—. **Ninguna es la buena.** El
`BuildCierreStep` sí ejecuta `06_views_planif_vs_real.sql` (es su séptimo
sub-paso, `views_planif_real`); el SQL está bien y el step está bien.

Consecuencia para el arreglo: meter `build-cierre` en la nocturna **no es
opcional ni cosmético**, y **el orden importa**: `cierre` tiene que ir
*después* de `build_mart`, porque `build_mart` destruye lo que `cierre`
construye. Por eso F-047 absorbe F-044.

## Lo que falta verificar contra la base

No pudo hacerse: `psql-albaranes-rs9k2` está `Ready`, pero el puerto 5432 no
acepta conexión desde este puesto (`TcpTestSucceeded: False`). La IP pública
de hoy no figura en ninguna regla de firewall del servidor. Pendiente de
decisión del humano.

Cuando haya conexión, queda por confirmar (todo lectura):

1. `python main.py check-diccionario` → la huérfana sigue siendo esa y solo esa.
2. `_meta.etl_runs` → última ejecución de `build_mart` y de `build_cierre`,
   para fechar el borrado contra la última nocturna.
3. `pg_depend` → que no haya en la base *otros* dependientes de
   `mart.fact_seguimiento_categoria` creados fuera del repositorio.
