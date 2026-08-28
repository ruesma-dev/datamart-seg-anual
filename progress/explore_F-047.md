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

## Verificado contra la base el 2026-08-28

Conexión recuperada (la IP del puesto no estaba en el firewall; regla
`datamart-puesto-pgris-2026-08-28` creada con autorización del humano).

**1. El síntoma sigue ahí, y es uno solo.** `check-diccionario`: 103 fichas,
102 objetos. Única huérfana: `cierre.v_pbi_planif_vs_real`.

**2. El guardián nuevo lo caza.** `check-declarados` contra el servidor real:
103 declarados, 102 construidos, señala el objeto **y su fichero de origen**
(`cierre/06_views_planif_vs_real.sql`). Código de salida **1**.

**3. `_meta.etl_runs` fecha el borrado y cierra el caso:**

| paso | último OK |
|---|---|
| `build_cierre` | **2026-08-21 23:30** — la ejecución manual del humano |
| `build_mart` | **2026-08-28 04:56** — la nocturna de esta madrugada |

`build_cierre` no ha vuelto a correr desde el 21. `build_mart` ha corrido
todas las noches. La vista nació el 21 a las 23:30 y la nocturna del 22 se la
llevó con el `CASCADE`. **El diagnóstico queda confirmado contra la base.**

## SEGUNDA CAPA: el despliegue lleva congelado desde el 18 de agosto

Encontrada tirando de un hilo suelto de la tabla de frescura:
`publicar_diccionario` tiene su último OK el **26**, mientras `apply_grants`
—que va justo después en el pipeline— registró el **28**. El código no tiene
atajo por hash: si corriera, registraría. Luego no corría.

**El job nocturno `caj-datamart-seg-dev` ejecuta la imagen
`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146`**, construida el
**18 de agosto a las 21:46**. Y es la más reciente del ACR: nadie ha construido
imagen desde entonces. El cron (`0 2 * * *`) corre y termina `Succeeded` todas
las noches, ~2 h 45, con código de hace diez días.

Consecuencias, y son serias:

1. **`publicar_diccionario` no está en esa imagen** (es de F-006, cerrada el
   27). Por eso no deja rastro nocturno. La fila del 26 fue una publicación a
   mano.
2. **Meter los cuatro build en `build_pipeline_steps` no cambia nada en
   producción hasta que se construya y despliegue una imagen nueva.** El
   criterio de aceptación de F-044 se cumple en el repositorio y **no** en la
   nocturna real.
3. La causa raíz de F-047 tiene por tanto **dos capas**: el `CASCADE` (lo que
   destruye la vista) y **el despliegue congelado** (lo que impide que el
   arreglo llegue). El título de la ficha —«la base va por detrás del
   repositorio»— era más literal de lo que parecía.
4. Enlaza con **F-033** («el documento de este proyecto en `azure-apps` miente
   sobre lo que hay desplegado»), que existe justamente por esto.

Decisión pendiente del humano: construir y desplegar imagen nueva. No la toma
el agente.

## Lo que queda por hacer contra la base

- Lanzar `build-cierre` para recrear la vista hoy (autorizado por el humano el
  2026-08-28; **bloqueado por el clasificador de permisos de la sesión**, sin
  ejecutar todavía).
- `publicar-diccionario` tras el cambio de fichas de esta feature: el
  `check-diccionario` avisa de que `_meta` sirve la versión 9 y los YAML ya dan
  otro hash.
**Comprobado el 2026-08-28** (`pg_depend`): la tabla
`mart.fact_seguimiento_categoria` tiene **un solo dependiente** en la base,
`mart.v_pbi_fact_categoria`, que está en el repositorio
(`sql/mart/05_views_powerbi.sql`) y se recrea en el mismo build. **No hay nada
creado fuera del repositorio colgando de ella**, así que el `CASCADE` no se
lleva por delante nada más que lo ya sabido.
