<!-- progress/mutacion_F-006_prueba.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-26 15:08.

## Alcance

Origen del diff: **ficheros** (alcance declarado en la orden).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 190 |
| `etl_sigrid/domain/diccionario.py` | 1089 |
| `etl_sigrid/domain/inventario.py` | 288 |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | 468 |
| `etl_sigrid/infrastructure/postgres/catalogo.py` | 166 |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | 332 |
| `etl_sigrid/infrastructure/postgres/relaciones_sql.py` | 319 |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | 274 |
| **Total** | **3126** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 256 |
| Mutantes evaluados | 4 |
| Muertos | 3 |
| Supervivientes | 1 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 1043.2 s |
| SHA de HEAD medido | `c541c23723c9cf6fdbd77b1c6d4f095dae9d3d29` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_iceu0lig/wk_0` | 335.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_iceu0lig/wk_1` | 331.0 |
| Media por mutante evaluado (s) | 260.8 |
| Timeout efectivo por mutante (s) | 671 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 2 |
| Muestreo | sí — 4 de 256 mutantes, semilla `None`, nivel `critico` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/inventario.py:234` [not]

- Original: `if informe.ok and not informe.avisos_columnas and not informe.pendientes_declarados:`
- Mutado:   `if informe.ok and informe.avisos_columnas and not informe.pendientes_declarados:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

