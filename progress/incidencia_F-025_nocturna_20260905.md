<!-- progress/incidencia_F-025_nocturna_20260905.md -->
# Incidencia · La primera nocturna con F-025 falló

**Ejecución** `caj-datamart-seg-dev-29809560` · arranque **2026-09-05 02:00:00 UTC**
· estado **Failed** · imagen **`r20260905-0034`** (la correcta, la de F-025).
17.486 líneas de log entre las 02:00:22 y las 04:19:13 UTC.

## El fallo, en una línea

```
AttributeError: 'PostgresClient' object has no attribute 'fetch_filas_por_obra'
```

Traza completa, idéntica en los dos intentos:

```
File "/app/etl_sigrid/application/steps/build_stg_step.py", line 438, in run
    self._build_presupuesto_acotado(pg, sql_path)
File "/app/etl_sigrid/application/steps/build_stg_step.py", line 735, in _build_presupuesto_acotado
    self._registrar_construidas(pg, obras, "presupuesto")
File "/app/etl_sigrid/application/steps/build_stg_step.py", line 628, in _registrar_construidas
    filas = pg.fetch_filas_por_obra(tabla, obras)
```

## Por qué 3.308 tests en verde no lo vieron

**El método no existe en el código de producción y no ha existido nunca.** El
barrido lo confirma en las dos direcciones:

- `grep -rn "fetch_filas_por_obra" --include=*.py .` fuera de `tests/` devuelve
  **una sola línea: la llamada**, `build_stg_step.py:628`. Ninguna definición.
- `git log -S "fetch_filas_por_obra" -- etl_sigrid/` devuelve **un único commit**,
  `49b631e` (F-025 · T11-T14), el que introdujo la llamada. La implementación no
  llegó a escribirse.

Lo que sí existe es el método **en tres dobles de test**, que lo declaran y
devuelven un valor plausible:

| doble | línea | devuelve |
|---|---|---|
| `tests/test_f019_tramos.py` | 540 | `dict[int, int]` |
| `tests/test_f024_steps.py` | 165 | `dict[int, int]` |
| `tests/test_f025_build.py` | 300 | `{int(o): 100 for o in obras}` |

`git log -S … -- tests/` los sitúa en `8e768e2` y `49b631e`: los dos commits de
F-025. O sea, **el método se añadió a los imitadores y no al imitado**.

**Nada en el árbol compara un doble con la interfaz que imita.** Sin esa
comprobación, un doble que declara de más produce verde sobre código que no
puede funcionar, y el único sitio donde eso sale es producción. Cuatro pasadas
de reviewer tampoco lo cazaron, porque leer el test y leer el step da coherencia
en ambos lados: la incoherencia sólo aparece al cruzar el doble con
`PostgresClient`.

## Qué llegó a hacer la nocturna (los dos intentos, idénticos)

| paso | resultado |
|---|---|
| `ingest_raw` | SUCCESS · 20.147.626 filas · 2.206 s y 1.782 s |
| `build_stg` | **FAILED** · 395.929 filas · 1.299,7 s y 1.463,7 s |
| `build_maestros` | SUCCESS · 26.170 |
| `build_compras` | SUCCESS · 2.500.592 · 488 s |
| `build_retenciones` | SUCCESS · 29.966 |
| `build_mart` · `build_cierre` · `publicar_diccionario` · `apply_grants` | **SKIPPED** |

## Estado real de la base tras el fallo: NO está rota

Comprobado con `python main.py status-stg` a las 09:15 UTC del 05:

```
stg.obras            583        stg.presupuesto    13.874.194
stg.partidas     390.788        stg.plan_mensual   29.767.052
stg.fases          4.558        stg.version_master_vigente 123
```

Son **las cifras de siempre**. El fallo cae *después* de construir el tramo, en
el registro de la traza en `_meta.obra_build`, así que no destruyó nada. Lo que
no hay es refresco: **`mart` y `cierre` siguen con lo que dejó la nocturna del
04**, y `_meta.obra_build` sigue vacía.

Consecuencia para la fase 7: **T29 no se ha ejecutado**, y por tanto **T30 (las
huellas del DESPUÉS) no se puede hacer todavía**. Las cinco huellas del ANTES en
`huellas/antes_*.csv` **siguen siendo válidas**: describen un `mart`/`cierre` que
nadie ha tocado.

## Cómo se leen los logs de una ejecución ya terminada

Esto costó dos intentos y conviene no volver a descubrirlo:

- `az containerapp job logs show --execution <nombre>` responde **`No replicas
  found for execution`** en cuanto la ejecución termina y sus réplicas se
  reciclan. Para una ejecución pasada **no sirve**.
- La vía buena es Log Analytics, y el filtro que funciona es
  **`ContainerGroupName_s startswith '<nombre de la ejecución>'`**. El README de
  `infra/` ya avisa de que `ContainerJobName_s` no existe para un job; lo que
  faltaba era cómo acotar a **una** ejecución.

```bash
WS=$(az monitor log-analytics workspace show -g rg-datamart-seg-dev -n log-datamart-seg-dev --query customerId -o tsv)
az monitor log-analytics query -w "$WS" --analytics-query \
  "ContainerAppConsoleLogs_CL | where ContainerGroupName_s startswith 'caj-datamart-seg-dev-29809560' | where Log_s has_any ('ERROR','Traceback','FAILED') | project TimeGenerated, Log_s | order by TimeGenerated asc" -o tsv
```

## El arreglo propuesto (pendiente de que lo ejecute el implementer)

1. **Implementar `fetch_filas_por_obra(tabla: str, obras: Sequence[int]) ->
   dict[int, int]`** en `etl_sigrid/infrastructure/postgres/postgres_client.py`,
   junto a `registrar_obras_construidas` (línea 1330), que es su pareja. Cuenta
   filas por `obra_id` en la tabla del tramo y alimenta la columna `filas` de
   `_meta.obra_build`. El nombre de tabla llega desde el step (`"presupuesto"`,
   …): **validarlo contra lista blanca**, no interpolarlo tal cual.
2. **Cerrar el modo de fallo, no sólo este caso**: un test que compruebe que
   **todo método público que un doble de `PostgresClient` declara existe en el
   cliente real y con la misma firma**. Y barrer si hay más métodos fantasma:
   este agujero no tiene por qué haber producido uno solo.
3. La lección va a `CHECKPOINTS.md` y, por la regla de propagación, a
   `arnes-base` en el mismo trabajo: **un doble que no se valida contra el
   original produce verde falso**.
