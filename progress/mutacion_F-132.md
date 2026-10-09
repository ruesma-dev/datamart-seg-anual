<!-- progress/mutacion_F-132.md -->
# F-132 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-132` el 2026-10-09 02:55.

## Alcance

Origen del diff: **rama** (`43a50b9de7effa2c632811016b50aed0668b4472` .. `feature/F-132-estado-desde-rac`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 15 |
| `etl_sigrid/domain/estado_documentos.py` | 330 |
| `etl_sigrid/domain/historial_estados.py` | 7 |
| `etl_sigrid/infrastructure/postgres/compras_reset_sql.py` | 5 |
| `etl_sigrid/infrastructure/postgres/contraste_estados_sql.py` | 92 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 10 |
| `main.py` | 87 |
| **Total** | **546** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 79 |
| Mutantes evaluados | 20 |
| Muertos | 18 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 5596.2 s |
| SHA de HEAD medido | `82f0e0d4b74c1ebb49f13de618b6c1810ad047f4` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-132_1t8dsgp3/wk_0` | 506.0 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-132_1t8dsgp3/wk_1` | 511.6 |
| Media por mutante evaluado (s) | 279.8 |
| Timeout efectivo por mutante (s) | 3600 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3600 |
| Workers | 2 |
| Muestreo | sí — 20 de 79 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:4955` [entero]

- Original: `default=300,`
- Mutado:   `default=301,`

#### Análisis

> Por qué ningún test lo caza: todos los tests del comando pasaban `--timeout`
> explícito o no miraban el timeout que llega al cliente; el valor por defecto
> no lo comprobaba nadie. Hueco REAL: es el `statement_timeout` que protege al
> servidor compartido cuando el humano lanza el comando sin opciones.
> Decisión: test nuevo,
> `test_f132_contraste.py::test_f132_r17_sin_timeout_cada_consulta_lleva_300_s_y_la_ayuda_lo_dice`
> (sin `--timeout`, las cuatro lecturas llevan 300). Con el mutante aplicado a
> mano: `E   assert {301} == {300}` · `1 failed`. Sin él: `1 passed`.

### 2. `main.py:4956` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis

> Por qué ningún test lo caza: ningún test leía la ayuda del comando. Hueco
> menor pero real: quien lance `contraste-estados --help` no vería el tiempo
> por defecto, como sí lo ven `check-cobertura` y los demás `check-*`.
> Decisión: el mismo test nuevo comprueba `default: 300` en `--help`. Con el
> mutante aplicado a mano: `AssertionError: assert 'default: 300' in 'Usage:
> cli contraste-estados [OPTIONS]...'` · `1 failed`. Sin él: `1 passed`.

