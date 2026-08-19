<!-- progress/mutacion_F-011.md -->
# F-011 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-011` el 2026-08-20 00:53.

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
| `main.py` | 247 |
| **Total** | **1522** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 192 |
| Mutantes evaluados | 192 |
| Muertos | 122 |
| Supervivientes | 70 |
| Timeouts | 0 |
| Tiempo total | 1065.5 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/domain/extraccion.py:58` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/domain/extraccion.py:58` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/domain/extraccion.py:73` [entero]

- Original: `if self.segundos <= 0 or self.filas <= 0:`
- Mutado:   `if self.segundos <= 1 or self.filas <= 0:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/domain/extraccion.py:73` [comparacion]

- Original: `if self.segundos <= 0 or self.filas <= 0:`
- Mutado:   `if self.segundos <= 0 or self.filas < 0:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/domain/extraccion.py:73` [entero]

- Original: `if self.segundos <= 0 or self.filas <= 0:`
- Mutado:   `if self.segundos <= 0 or self.filas <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `etl_sigrid/domain/extraccion.py:80` [entero]

- Original: `if self.peticiones <= 0:`
- Mutado:   `if self.peticiones <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 7. `etl_sigrid/domain/extraccion.py:85` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 8. `etl_sigrid/domain/extraccion.py:85` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 9. `etl_sigrid/domain/extraccion.py:106` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 10. `etl_sigrid/domain/extraccion.py:106` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 11. `etl_sigrid/domain/extraccion.py:128` [logico]

- Original: `m.cap_devuelto for m in lista if m.rechazada and m.cap_devuelto is not None`
- Mutado:   `m.cap_devuelto for m in lista if m.rechazada or m.cap_devuelto is not None`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 12. `etl_sigrid/domain/extraccion.py:260` [comparacion]

- Original: `if resumen.latencia_max_s >= timeout_s * UMBRAL_AVISO_TIMEOUT:`
- Mutado:   `if resumen.latencia_max_s > timeout_s * UMBRAL_AVISO_TIMEOUT:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 13. `etl_sigrid/domain/extraccion.py:263` [aritmetico]

- Original: `f"{resumen.latencia_max_s / timeout_s * 100:.0f} % del timeout de "`
- Mutado:   `f"{resumen.latencia_max_s / timeout_s // 100:.0f} % del timeout de "`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 14. `etl_sigrid/domain/extraccion.py:263` [entero]

- Original: `f"{resumen.latencia_max_s / timeout_s * 100:.0f} % del timeout de "`
- Mutado:   `f"{resumen.latencia_max_s / timeout_s * 101:.0f} % del timeout de "`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 15. `etl_sigrid/domain/perfil_carga.py:70` [entero]

- Original: `if self.segundos <= 0:`
- Mutado:   `if self.segundos <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 16. `etl_sigrid/domain/perfil_carga.py:75` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 17. `etl_sigrid/domain/perfil_carga.py:91` [entero]

- Original: `if self.total_segundos <= 0:`
- Mutado:   `if self.total_segundos <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 18. `etl_sigrid/domain/perfil_carga.py:96` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 19. `etl_sigrid/domain/perfil_carga.py:96` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 20. `etl_sigrid/domain/perfil_carga.py:155` [entero]

- Original: `ahorro_pct=(0.0 if total <= 0 else p.segundos / total * 100.0),`
- Mutado:   `ahorro_pct=(0.0 if total <= 1 else p.segundos / total * 100.0),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 21. `etl_sigrid/domain/perfil_carga.py:171` [entero]

- Original: `if not 0 < pct <= 100:`
- Mutado:   `if not 1 < pct <= 100:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 22. `etl_sigrid/domain/perfil_carga.py:178` [entero]

- Original: `if objetivo <= 0:`
- Mutado:   `if objetivo <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 23. `etl_sigrid/domain/perfil_carga.py:216` [logico]

- Original: `if not perfil.pasos and not perfil.tablas:`
- Mutado:   `if not perfil.pasos or not perfil.tablas:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 24. `etl_sigrid/domain/perfil_carga.py:266` [aritmetico]

- Original: `acumulado += t.segundos`
- Mutado:   `acumulado -= t.segundos`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 25. `etl_sigrid/domain/perfil_carga.py:267` [comparacion]

- Original: `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0`
- Mutado:   `pct_ingesta = 0.0 if total_ingesta < 0 else t.segundos / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 26. `etl_sigrid/domain/perfil_carga.py:267` [entero]

- Original: `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0`
- Mutado:   `pct_ingesta = 0.0 if total_ingesta <= 1 else t.segundos / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 27. `etl_sigrid/domain/perfil_carga.py:267` [aritmetico]

- Original: `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta * 100.0`
- Mutado:   `pct_ingesta = 0.0 if total_ingesta <= 0 else t.segundos / total_ingesta // 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 28. `etl_sigrid/domain/perfil_carga.py:268` [comparacion]

- Original: `pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta * 100.0`
- Mutado:   `pct_acum = 0.0 if total_ingesta < 0 else acumulado / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 29. `etl_sigrid/domain/perfil_carga.py:268` [entero]

- Original: `pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta * 100.0`
- Mutado:   `pct_acum = 0.0 if total_ingesta <= 1 else acumulado / total_ingesta * 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 30. `etl_sigrid/domain/perfil_carga.py:268` [aritmetico]

- Original: `pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta * 100.0`
- Mutado:   `pct_acum = 0.0 if total_ingesta <= 0 else acumulado / total_ingesta // 100.0`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 31. `etl_sigrid/domain/perfil_carga.py:270` [logico]

- Original: `f"{t.tabla or t.step:<24} {t.segundos:>12.1f} "`
- Mutado:   `f"{t.tabla and t.step:<24} {t.segundos:>12.1f} "`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 32. `etl_sigrid/domain/perfil_carga.py:283` [comparacion]

- Original: `plural = "tabla" if len(cabeza) == 1 else "tablas"`
- Mutado:   `plural = "tabla" if len(cabeza) != 1 else "tablas"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 33. `etl_sigrid/domain/perfil_carga.py:283` [entero]

- Original: `plural = "tabla" if len(cabeza) == 1 else "tablas"`
- Mutado:   `plural = "tabla" if len(cabeza) == 2 else "tablas"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 34. `etl_sigrid/domain/perfil_carga.py:287` [logico]

- Original: `f"{pct:.0f} % del tiempo de ingesta: {', '.join(cabeza) or '-'}"`
- Mutado:   `f"{pct:.0f} % del tiempo de ingesta: {', '.join(cabeza) and '-'}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 35. `etl_sigrid/domain/tiemod.py:49` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 36. `etl_sigrid/domain/tiemod.py:63` [entero]

- Original: `if self.filas <= 0:`
- Mutado:   `if self.filas <= 1:`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 37. `etl_sigrid/domain/tiemod.py:69` [entero]

- Original: `return self.filas <= 0`
- Mutado:   `return self.filas <= 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 38. `etl_sigrid/domain/tiemod.py:77` [entero]

- Original: `return self.filas > 0 and self.nulos >= self.filas`
- Mutado:   `return self.filas > 1 and self.nulos >= self.filas`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 39. `etl_sigrid/domain/tiemod.py:80` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 40. `etl_sigrid/domain/tiemod.py:80` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 41. `etl_sigrid/domain/tiemod.py:162` [aritmetico]

- Original: `f"la tabla cambió de contenido ({ahora.filas - antes.filas:+,} filas) "`
- Mutado:   `f"la tabla cambió de contenido ({ahora.filas + antes.filas:+,} filas) "`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 42. `etl_sigrid/domain/tiemod.py:234` [comparacion]

- Original: `f"{(0.0 if filas <= 0 else nulos / filas * 100.0):>8.1f}"`
- Mutado:   `f"{(0.0 if filas < 0 else nulos / filas * 100.0):>8.1f}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 43. `etl_sigrid/domain/tiemod.py:234` [entero]

- Original: `f"{(0.0 if filas <= 0 else nulos / filas * 100.0):>8.1f}"`
- Mutado:   `f"{(0.0 if filas <= 1 else nulos / filas * 100.0):>8.1f}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 44. `etl_sigrid/domain/tiemod.py:234` [aritmetico]

- Original: `f"{(0.0 if filas <= 0 else nulos / filas * 100.0):>8.1f}"`
- Mutado:   `f"{(0.0 if filas <= 0 else nulos / filas // 100.0):>8.1f}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 45. `etl_sigrid/domain/tiemod.py:278` [booleano]

- Original: `path.parent.mkdir(parents=True, exist_ok=True)`
- Mutado:   `path.parent.mkdir(parents=False, exist_ok=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 46. `etl_sigrid/domain/tiemod.py:310` [entero]

- Original: `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[0])}"`
- Mutado:   `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[1])}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 47. `etl_sigrid/domain/tiemod.py:318` [entero]

- Original: `minimo=None if fila[3] == "" else float(fila[3]),`
- Mutado:   `minimo=None if fila[4] == "" else float(fila[3]),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 48. `etl_sigrid/infrastructure/postgres/postgres_client.py:1077` [entero]

- Original: `filas=int(fila[0] or 0),`
- Mutado:   `filas=int(fila[0] or 1),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 49. `etl_sigrid/infrastructure/postgres/postgres_client.py:1078` [entero]

- Original: `nulos=int(fila[1] or 0),`
- Mutado:   `nulos=int(fila[1] or 1),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 50. `etl_sigrid/infrastructure/postgres/postgres_client.py:1079` [entero]

- Original: `minimo=None if fila[2] is None else float(fila[2]),`
- Mutado:   `minimo=None if fila[3] is None else float(fila[2]),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 51. `etl_sigrid/infrastructure/postgres/postgres_client.py:1080` [entero]

- Original: `maximo=None if fila[3] is None else float(fila[3]),`
- Mutado:   `maximo=None if fila[4] is None else float(fila[3]),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 52. `etl_sigrid/infrastructure/postgres/postgres_client.py:1081` [entero]

- Original: `distintos=int(fila[4] or 0),`
- Mutado:   `distintos=int(fila[4] or 1),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 53. `etl_sigrid/infrastructure/postgres/postgres_client.py:1097` [entero]

- Original: `return int(fila[0]) if fila else 0`
- Mutado:   `return int(fila[0]) if fila else 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 54. `etl_sigrid/infrastructure/sigrid/bench_extraccion.py:87` [entero]

- Original: `repeticiones: int = 1,`
- Mutado:   `repeticiones: int = 2,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 55. `etl_sigrid/infrastructure/sigrid/bench_extraccion.py:142` [entero]

- Original: `segundos=round(latencia, 3),`
- Mutado:   `segundos=round(latencia, 4),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 56. `etl_sigrid/infrastructure/sigrid/bench_extraccion.py:189` [booleano]

- Original: `path.parent.mkdir(parents=True, exist_ok=True)`
- Mutado:   `path.parent.mkdir(parents=False, exist_ok=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 57. `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py:62` [entero]

- Original: `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:200]!r}"`
- Mutado:   `f"admiten consultas que empiecen por SELECT. Recibido: {sql[:201]!r}"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 58. `main.py:130` [entero]

- Original: `CAP_DOCUMENTADO_SIGRID_API = 1_000`
- Mutado:   `CAP_DOCUMENTADO_SIGRID_API = 1001`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 59. `main.py:686` [booleano]

- Original: `click.secho(f"✗ No se pudo leer _meta.etl_runs: {e}", fg="red", err=True)`
- Mutado:   `click.secho(f"✗ No se pudo leer _meta.etl_runs: {e}", fg="red", err=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 60. `main.py:696` [booleano]

- Original: `type=click.Path(dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(dir_okay=True, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 61. `main.py:704` [booleano]

- Original: `type=click.Path(exists=True, dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(exists=False, dir_okay=False, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 62. `main.py:704` [booleano]

- Original: `type=click.Path(exists=True, dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(exists=True, dir_okay=True, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 63. `main.py:731` [booleano]

- Original: `click.secho(f"✗ No se pudo leer el estado de raw: {e}", fg="red", err=True)`
- Mutado:   `click.secho(f"✗ No se pudo leer el estado de raw: {e}", fg="red", err=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 64. `main.py:764` [logico]

- Original: `if e.tabla in previos and previos[e.tabla].maximo is not None`
- Mutado:   `if e.tabla in previos or previos[e.tabla].maximo is not None`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 65. `main.py:773` [booleano]

- Original: `required=True,`
- Mutado:   `required=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 66. `main.py:781` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 67. `main.py:789` [entero]

- Original: `default=1,`
- Mutado:   `default=2,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 68. `main.py:790` [booleano]

- Original: `show_default=True,`
- Mutado:   `show_default=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 69. `main.py:797` [booleano]

- Original: `type=click.Path(dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(dir_okay=True, path_type=Path),`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 70. `main.py:820` [booleano]

- Original: `click.secho("✗ --paginas no trae ningún tamaño.", fg="red", err=True)`
- Mutado:   `click.secho("✗ --paginas no trae ningún tamaño.", fg="red", err=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

