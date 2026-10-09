<!-- progress/mutacion_F-132_faseB.md -->
# F-132 · Campaña de mutación · Fase B (rama BORRAR)

La de la Fase A está en `progress/mutacion_F-132.md`. Lanzada con
`python -m harness.mutacion --feature F-132 --workers 2 --timeout 3600` (con los
4 workers por defecto la línea base no cupo en 600 s, como en la Fase A).

Generado por `python -m harness.mutacion --feature F-132` el 2026-10-09 14:19.

## Alcance

Origen del diff: **rama** (`09bec587584da3dcc1d3b383ace7b69437ab2b7a` .. `feature/F-132-estado-desde-rac`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_compras_step.py` | 17 |
| `etl_sigrid/domain/estado_documentos.py` | 6 |
| `etl_sigrid/domain/fecha_delphi.py` | 40 |
| `etl_sigrid/infrastructure/postgres/compras_reset_sql.py` | 14 |
| `etl_sigrid/infrastructure/postgres/retirar_foto_sql.py` | 51 |
| `main.py` | 63 |
| **Total** | **191** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 18 |
| Mutantes evaluados | 18 |
| Muertos | 16 |
| Supervivientes | 2 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 3739.8 s |
| SHA de HEAD medido | `b0946cec2f846f0a87773d7aa534ceb9e22e8942` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-132_avrsl6sd/wk_0` | 427.2 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-132_avrsl6sd/wk_1` | 425.8 |
| Media por mutante evaluado (s) | 207.8 |
| Timeout efectivo por mutante (s) | 3600 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 3600 |
| Workers | 2 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `main.py:4985` [entero]

- Original: `presentes = dict(pg.filas_solo_lectura(SQL_TABLAS_FOTO, 120))`
- Mutado:   `presentes = dict(pg.filas_solo_lectura(SQL_TABLAS_FOTO, 121))`

#### Análisis

> Por qué ningún test lo caza: el doble `_PgFalso` de `tests/test_f132_retirada.py`
> recibía `timeout_s` y no lo apuntaba; ningún test miraba con qué
> `statement_timeout` se lee. HUECO REAL: un `0` (sin límite) o un número
> desorbitado pasaría la suite, y la lectura cuenta ~186.700 filas en un
> servidor compartido con producción.
> Decisión: **test nuevo**, `test_f132_r26_las_dos_lecturas_llevan_su_statement_timeout`
> (el doble apunta los timeouts; se exige `[120, 120]`). Comprobado con el
> mutante aplicado a mano en cada línea: `1 failed` en las dos.

### 2. `main.py:5008` [entero]

- Original: `quedan = sorted(dict(pg.filas_solo_lectura(SQL_TABLAS_FOTO, 120)))`
- Mutado:   `quedan = sorted(dict(pg.filas_solo_lectura(SQL_TABLAS_FOTO, 121)))`

#### Análisis

> Por qué ningún test lo caza: el doble `_PgFalso` de `tests/test_f132_retirada.py`
> recibía `timeout_s` y no lo apuntaba; ningún test miraba con qué
> `statement_timeout` se lee. HUECO REAL: un `0` (sin límite) o un número
> desorbitado pasaría la suite, y la lectura cuenta ~186.700 filas en un
> servidor compartido con producción.
> Decisión: **test nuevo**, `test_f132_r26_las_dos_lecturas_llevan_su_statement_timeout`
> (el doble apunta los timeouts; se exige `[120, 120]`). Comprobado con el
> mutante aplicado a mano en cada línea: `1 failed` en las dos.

