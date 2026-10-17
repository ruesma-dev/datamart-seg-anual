<!-- progress/mutacion_F-141.md -->
# F-141 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-141` el 2026-10-17 15:41.

## Alcance

Origen del diff: **rama** (`16723839e56e8d79ca4126ffc1b5f1617d54d27b` .. `feature/F-141-perfil-restringido`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 66 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 306 |
| `etl_sigrid/application/steps/build_contabilidad_step.py` | 1 |
| `etl_sigrid/application/steps/build_tesoreria_step.py` | 1 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 218 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 160 |
| **Total** | **752** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 56 |
| Mutantes evaluados | 56 |
| Muertos | 52 |
| Supervivientes | 4 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 14715.6 s |
| SHA de HEAD medido | `557295c21b00950d7c17c5d26e8b745b5e704901` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-141_pmqm78t1/wk_0` | 1149.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-141_pmqm78t1/wk_1` | 1162.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-141_pmqm78t1/wk_2` | 1150.6 |
| Media por mutante evaluado (s) | 262.8 |
| Timeout efectivo por mutante (s) | 9000 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 9000 |
| Workers | 3 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/postgres/grants.py:393` [entero]

- Original: `if tabla in fuera or tabla.split(".", 1)[0] not in concedidos`
- Mutado:   `if tabla in fuera or tabla.split(".", 2)[0] not in concedidos`

#### Análisis (implementer, 2026-10-17)

> Por qué ningún test lo caza: es un mutante EQUIVALENTE. `s.split(".", n)[0]` es lo que
> hay antes del PRIMER punto para todo `n >= 1` y toda cadena `s` (también con dos o más
> puntos, o sin ninguno): el límite de cortes solo cambia los trozos de detrás. Ningún
> test, ni ninguna entrada, puede distinguir `n = 1` de `n = 2`.
> Decisión: mutante equivalente justificado; queda a la ACEPTACIÓN DEL HUMANO (rigor
> crítico, T12). Si no se acepta, la alternativa sin cambiar el comportamiento es
> `s.partition(".")[0]`, que no tiene literal entero que mutar.

### 2. `etl_sigrid/infrastructure/postgres/grants.py:426` [entero]

- Original: `esquema_objeto = objeto.split(".", 1)[0]`
- Mutado:   `esquema_objeto = objeto.split(".", 2)[0]`

#### Análisis (implementer, 2026-10-17)

> Por qué ningún test lo caza: es un mutante EQUIVALENTE. `s.split(".", n)[0]` es lo que
> hay antes del PRIMER punto para todo `n >= 1` y toda cadena `s` (también con dos o más
> puntos, o sin ninguno): el límite de cortes solo cambia los trozos de detrás. Ningún
> test, ni ninguna entrada, puede distinguir `n = 1` de `n = 2`.
> Decisión: mutante equivalente justificado; queda a la ACEPTACIÓN DEL HUMANO (rigor
> crítico, T12). Si no se acepta, la alternativa sin cambiar el comportamiento es
> `s.partition(".")[0]`, que no tiene literal entero que mutar.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1633` [entero]

- Original: `if e.split(".", 1)[0] in aplicables and e not in ausentes],`
- Mutado:   `if e.split(".", 2)[0] in aplicables and e not in ausentes],`

#### Análisis (implementer, 2026-10-17)

> Por qué ningún test lo caza: es un mutante EQUIVALENTE. `s.split(".", n)[0]` es lo que
> hay antes del PRIMER punto para todo `n >= 1` y toda cadena `s` (también con dos o más
> puntos, o sin ninguno): el límite de cortes solo cambia los trozos de detrás. Ningún
> test, ni ninguna entrada, puede distinguir `n = 1` de `n = 2`.
> Decisión: mutante equivalente justificado; queda a la ACEPTACIÓN DEL HUMANO (rigor
> crítico, T12). Si no se acepta, la alternativa sin cambiar el comportamiento es
> `s.partition(".")[0]`, que no tiene literal entero que mutar.

### 4. `etl_sigrid/infrastructure/postgres/postgres_client.py:1633` [entero]

- Original: `if e.split(".", 1)[0] in aplicables and e not in ausentes],`
- Mutado:   `if e.split(".", 1)[1] in aplicables and e not in ausentes],`

#### Análisis (implementer, 2026-10-17)

> Por qué ningún test lo caza: HUECO REAL, pero solo del LOG. El único test del evento
> `grants_perfil_restringido_aplicados` usaba un excluido AUSENTE, así que `revocados` era
> `[]` con el original y con el mutante. Las sentencias ejecutadas no dependen de esta línea.
> Decisión: test nuevo `test_f141_cliente_apply_perfil_restringido_anota_lo_revocado`
> (un excluido existente de un esquema concedido, uno ausente y uno de un esquema ajeno).
> Con la mutación aplicada a mano falla (`assert [] == ['contabilidad.mayor']`); sin ella,
> en verde. Superviviente CERRADO.

