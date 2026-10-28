<!-- progress/mutacion_F-150.md -->
# F-150 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-150` el 2026-10-28 10:34.

## Alcance

Origen del diff: **rama** (`a80bb1b839c61f92a2476466eb7ede6b92987135` .. `feature/F-150-receta-caja`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/ingest_raw_step.py` | 30 |
| `etl_sigrid/domain/entities.py` | 4 |
| `etl_sigrid/domain/proyeccion_caja.py` | 291 |
| `etl_sigrid/infrastructure/postgres/hipotesis_caja_sql.py` | 4 |
| **Total** | **329** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 95 |
| Mutantes evaluados | 20 |
| Muertos | 17 |
| Supervivientes | 1 |
| Timeouts | 2 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 15325.8 s |
| SHA de HEAD medido | `e85a3d86a7ec61cd85cc6c7717f73d0a822ed199` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_iajjhflb/wk_0` | 1265.5 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-150_iajjhflb/wk_1` | 1281.1 |
| Media por mutante evaluado (s) | 766.3 |
| Timeout efectivo por mutante (s) | 2400 — fijado a mano con `--timeout`, sin derivar |
| Suelo configurado (s) | 2400 |
| Workers | 2 |
| Muestreo | sí — 20 de 95 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/proyeccion_caja.py:227` [entero]

- Original: `valor = campos[2].strip(_BLANCO_DE_BTRIM) if len(campos) > 2 else ""`
- Mutado:   `valor = campos[2].strip(_BLANCO_DE_BTRIM) if len(campos) > 3 else ""`

#### Análisis del implementer

> Por qué ningún test lo caza: todos los casos de `test_f150_contrato.py` traían líneas de cinco
> campos (`CODIGO|etiqueta|valor||base`) o de dos o menos; ninguna de TRES justos
> (`CODIGO|etiqueta|valor`), que es justo donde `> 2` y `> 3` difieren. No es equivalente: el SQL
> (`split_part(t, '|', 3)` en `tesoreria.fn_coeficientes`) sí lee el valor de una línea de tres
> campos, así que con el mutante dominio y SQL discreparían.
> Decisión: HUECO REAL, cerrado con un test nuevo,
> `test_f150_r7_una_linea_de_solo_tres_campos_se_lee_como_el_sql`. Comprobado a mano: con el
> mutante aplicado el test falla (`reconocido=False` frente a `True`, gg y bi distintos); sin él,
> pasa (41 passed en `test_f150_contrato.py`).

## Timeouts

Reevaluados EN SERIE por el implementer (un timeout es un superviviente hasta que se demuestre lo
contrario, F-041): mutante aplicado a mano sobre el árbol, `python -m pytest -q -x
tests/test_f150_perfil.py tests/test_f140_hipotesis.py tests/test_f150_receta.py
tests/test_f140_paso.py`, fichero restaurado con `git checkout` y `__pycache__` del dominio
borrado después. **Los dos MUEREN en 2 s**:

- `:485` (`and valor` -> `or valor`): `AssertionError: ('no es un PERFIL_MESES', 'H03:
  PERFIL_MESES: los porcentajes suman 0, no 100')` (`1 failed, 9 passed in 1.65s`).
- `:498` (`par[1] == par[1]` -> `par[2] == par[1]`): `IndexError: list index out of range`
  (`1 failed, 1 passed in 2.04s`).

Por qué la campaña los dio por timeout no está demostrado; hipótesis: la suite entera corre en
otro orden y algún test anterior que carga el YAML real con el dominio mutado se queda colgado o
reintenta (los dos rompen la validación del catálogo), con dos workers compitiendo (línea base
de 1.266-1.281 s). Veredicto que vale para el cierre: 19 muertos y 1 superviviente, cerrado.

- `etl_sigrid/domain/proyeccion_caja.py:485` [logico] if not (isinstance(valor, (list, tuple)) and valor): -> if not (isinstance(valor, (list, tuple)) or valor):
- `etl_sigrid/domain/proyeccion_caja.py:498` [entero] if suma is not None and _es_numero(par[1]) and par[1] == par[1]: -> if suma is not None and _es_numero(par[1]) and par[2] == par[1]:

