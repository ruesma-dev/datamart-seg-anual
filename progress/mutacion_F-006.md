<!-- progress/mutacion_F-006.md -->
# F-006 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-006` el 2026-08-26 17:38.

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
| Mutantes evaluados | 256 |
| Muertos | 204 |
| Supervivientes | 52 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 8368.3 s |
| SHA de HEAD medido | `99e23356a69a1bf79ac803a25fdf5a4f53393bf4` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_0` | 485.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_1` | 479.3 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_2` | 483.9 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_3` | 462.6 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_4` | 467.4 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-006_zlyp7bqc/wk_5` | 469.0 |
| Media por mutante evaluado (s) | 32.7 |
| Timeout efectivo por mutante (s) | 972 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 6 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/diccionario.py:200` [entero]

- Original: `"descripcion": 40,`
- Mutado:   `"descripcion": 41,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/domain/diccionario.py:202` [entero]

- Original: `"motivo_no_consumo": 30,`
- Mutado:   `"motivo_no_consumo": 31,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/domain/diccionario.py:237` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/domain/diccionario.py:253` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/domain/diccionario.py:268` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `etl_sigrid/domain/diccionario.py:299` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 7. `etl_sigrid/domain/diccionario.py:299` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 8. `etl_sigrid/domain/diccionario.py:314` [entero]

- Original: `orden: int = 0`
- Mutado:   `orden: int = 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 9. `etl_sigrid/domain/diccionario.py:317` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 10. `etl_sigrid/domain/diccionario.py:317` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 11. `etl_sigrid/domain/diccionario.py:341` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 12. `etl_sigrid/domain/diccionario.py:341` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 13. `etl_sigrid/domain/diccionario.py:774` [not]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if ficha.clave_negocio and not ficha.columnas:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 14. `etl_sigrid/domain/diccionario.py:774` [logico]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if not ficha.clave_negocio or not ficha.columnas:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 15. `etl_sigrid/domain/diccionario.py:774` [not]

- Original: `if not ficha.clave_negocio and not ficha.columnas:`
- Mutado:   `if not ficha.clave_negocio and ficha.columnas:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 16. `etl_sigrid/domain/inventario.py:69` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 17. `etl_sigrid/domain/inventario.py:69` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 18. `etl_sigrid/domain/inventario.py:146` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 19. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:50` [entero]

- Original: `| {f"com{i}" for i in range(1, 10)}`
- Mutado:   `| {f"com{i}" for i in range(2, 10)}`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 20. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:50` [entero]

- Original: `| {f"com{i}" for i in range(1, 10)}`
- Mutado:   `| {f"com{i}" for i in range(1, 11)}`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 21. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:51` [entero]

- Original: `| {f"lpt{i}" for i in range(1, 10)}`
- Mutado:   `| {f"lpt{i}" for i in range(2, 10)}`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 22. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:51` [entero]

- Original: `| {f"lpt{i}" for i in range(1, 10)}`
- Mutado:   `| {f"lpt{i}" for i in range(1, 11)}`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 23. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:245` [logico]

- Original: `problema = getattr(exc, "problem", None) or "YAML mal formado"`
- Mutado:   `problema = getattr(exc, "problem", None) and "YAML mal formado"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 24. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [aritmetico]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line - 1}, columna {marca.column + 1}: {problema}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 25. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [entero]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 2}, columna {marca.column + 1}: {problema}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 26. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [aritmetico]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column - 1}: {problema}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 27. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:248` [entero]

- Original: `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 1}: {problema}"`
- Mutado:   `return f"el YAML no parsea en la linea {marca.line + 1}, columna {marca.column + 2}: {problema}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 28. `etl_sigrid/infrastructure/diccionario/cargador_yaml.py:361` [comparacion]

- Original: `grano=cuerpo.get("grano") if cuerpo.get("grano") is None else _texto(cuerpo.get("grano")),`
- Mutado:   `grano=cuerpo.get("grano") if cuerpo.get("grano") is not None else _texto(cuerpo.get("grano")),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 29. `etl_sigrid/infrastructure/postgres/catalogo.py:35` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 30. `etl_sigrid/infrastructure/postgres/catalogo.py:35` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 31. `etl_sigrid/infrastructure/postgres/catalogo.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 32. `etl_sigrid/infrastructure/postgres/catalogo.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 33. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:142` [booleano]

- Original: `ensure_ascii=False,`
- Mutado:   `ensure_ascii=True,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 34. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:160` [logico]

- Original: `ficha.motivo_no_consumo or None,`
- Mutado:   `ficha.motivo_no_consumo and None,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 35. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:162` [logico]

- Original: `ficha.grano or None,`
- Mutado:   `ficha.grano and None,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 36. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:202` [entero]

- Original: `return round(100.0 * con_significado / len(de_consumo), 2)`
- Mutado:   `return round(100.0 * con_significado / len(de_consumo), 3)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 37. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:239` [entero]

- Original: `"version": fila[1],`
- Mutado:   `"version": fila[2],`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 38. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:277` [booleano]

- Original: `json.dumps(valor, ensure_ascii=False, default=str),`
- Mutado:   `json.dumps(valor, ensure_ascii=True, default=str),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 39. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:326` [comparacion]

- Original: `if bloque == "ejes":`
- Mutado:   `if bloque != "ejes":`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 40. `etl_sigrid/infrastructure/postgres/diccionario_sql.py:329` [comparacion]

- Original: `if bloque == "esquemas":`
- Mutado:   `if bloque != "esquemas":`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 41. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:72` [entero]

- Original: `TAMANO_MUESTRA = 500`
- Mutado:   `TAMANO_MUESTRA = 501`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 42. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 43. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 44. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:278` [comparacion]

- Original: `if cobertura < UMBRAL_AVISO_COBERTURA:`
- Mutado:   `if cobertura <= UMBRAL_AVISO_COBERTURA:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 45. `etl_sigrid/infrastructure/postgres/relaciones_sql.py:282` [entero]

- Original: `f"{int(UMBRAL_AVISO_COBERTURA * 100)} % desde el que esto avisa. La "`
- Mutado:   `f"{int(UMBRAL_AVISO_COBERTURA * 101)} % desde el que esto avisa. La "`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 46. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:62` [entero]

- Original: `TIMEOUT_POR_CONSULTA_S = 30`
- Mutado:   `TIMEOUT_POR_CONSULTA_S = 31`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 47. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:65` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 48. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:65` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 49. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:133` [logico]

- Original: `if ficha.tipo == "funcion" or not ficha.clave_negocio:`
- Mutado:   `if ficha.tipo == "funcion" and not ficha.clave_negocio:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 50. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:173` [booleano]

- Original: `dicc: Diccionario, *, solo_consumo: bool = True`
- Mutado:   `dicc: Diccionario, *, solo_consumo: bool = False`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 51. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:189` [logico]

- Original: `elif solo_consumo and not ficha.consumo_recomendado:`
- Mutado:   `elif solo_consumo or not ficha.consumo_recomendado:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 52. `etl_sigrid/infrastructure/postgres/unicidad_sql.py:189` [not]

- Original: `elif solo_consumo and not ficha.consumo_recomendado:`
- Mutado:   `elif solo_consumo and ficha.consumo_recomendado:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

