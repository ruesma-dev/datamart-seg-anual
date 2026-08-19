<!-- progress/mutacion_F-011.md -->
# F-011 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-011` el 2026-08-20 01:14.

## Alcance

Origen del diff: **rama** (`30efd28f1675a8400dee1d708a4d3b6597c7f9a2` .. `feature/F-011-carga-incremental`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/domain/extraccion.py` | 267 |
| `etl_sigrid/domain/perfil_carga.py` | 289 |
| `etl_sigrid/domain/tiemod.py` | 324 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 152 |
| `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` | 206 |
| `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py` | 37 |
| `main.py` | 250 |
| **Total** | **1525** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 194 |
| Mutantes evaluados | 194 |
| Muertos | 174 |
| Supervivientes | 20 |
| Timeouts | 0 |
| Tiempo total | 907.4 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/extraccion.py:58` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/domain/extraccion.py:73` [comparacion]

- Original: `if self.segundos <= 0 or self.filas <= 0:`
- Mutado:   `if self.segundos <= 0 or self.filas < 0:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/domain/extraccion.py:85` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/domain/extraccion.py:106` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/domain/perfil_carga.py:40` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `etl_sigrid/domain/perfil_carga.py:75` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 7. `etl_sigrid/domain/perfil_carga.py:96` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 8. `etl_sigrid/domain/perfil_carga.py:266` [aritmetico]

- Original: `acumulado += t.segundos`
- Mutado:   `acumulado -= t.segundos`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 9. `etl_sigrid/domain/perfil_carga.py:267` [entero]

- Original: `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0`
- Mutado:   `pct_ingesta = 0.0 if total_ingesta <= 1 else t.segundos / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 10. `etl_sigrid/domain/perfil_carga.py:267` [aritmetico]

- Original: `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0`
- Mutado:   `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta // 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 11. `etl_sigrid/domain/perfil_carga.py:268` [entero]

- Original: `pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta * 100.0`
- Mutado:   `pct_acum = 0.0 if total_ingesta <= 1 else acumulado / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 12. `etl_sigrid/domain/tiemod.py:49` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 13. `etl_sigrid/domain/tiemod.py:80` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 14. `etl_sigrid/infrastructure/postgres/postgres_client.py:1079` [entero]

- Original: `minimo=None if fila[2] is None else float(fila[2]),`
- Mutado:   `minimo=None if fila[3] is None else float(fila[2]),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 15. `etl_sigrid/infrastructure/sigrid/bench_extraccion.py:142` [entero]

- Original: `segundos=round(latencia, 3),`
- Mutado:   `segundos=round(latencia, 4),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 16. `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py:62` [entero]

- Original: `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:200]!r}"`
- Mutado:   `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:201]!r}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 17. `main.py:704` [booleano]

- Original: `type=click.Path(exists=True, dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(exists=False, dir_okay=False, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 18. `main.py:704` [booleano]

- Original: `type=click.Path(exists=True, dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(exists=True, dir_okay=True, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 19. `main.py:792` [entero]

- Original: `default=1,`
- Mutado:   `default=2,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 20. `main.py:793` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

