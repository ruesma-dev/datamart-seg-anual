<!-- progress/mutacion_F-004.md -->
# F-004 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-004` el 2026-08-09 19:08.

## Alcance

Origen del diff: **rama** (`4741db17b8d82bc7faad094c1a66e9901fd625b9` .. `feature/F-004-etl-sin-dependencias-locales`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 34 |
| `etl_sigrid/application/steps/load_excel_aux_step.py` | 133 |
| `etl_sigrid/infrastructure/excel/aux_file_source.py` | 215 |
| `etl_sigrid/infrastructure/excel/blob_aux_file_source.py` | 145 |
| **Total** | **527** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 27 |
| Mutantes evaluados | 27 |
| Muertos | 21 |
| Supervivientes | 6 |
| Timeouts | 0 |
| Tiempo total | 53.1 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/application/steps/load_excel_aux_step.py:136` [booleano]

- Original: `libro = load_workbook(BytesIO(datos), read_only=True, data_only=True)`
- Mutado:   `libro = load_workbook(BytesIO(datos), read_only=False, data_only=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/application/steps/load_excel_aux_step.py:136` [booleano]

- Original: `libro = load_workbook(BytesIO(datos), read_only=True, data_only=True)`
- Mutado:   `libro = load_workbook(BytesIO(datos), read_only=True, data_only=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/infrastructure/excel/aux_file_source.py:49` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `etl_sigrid/infrastructure/excel/aux_file_source.py:49` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `etl_sigrid/infrastructure/excel/aux_file_source.py:81` [entero]

- Original: `return valor.split("?", 1)[0].split("#", 1)[0]`
- Mutado:   `return valor.split("?", 2)[0].split("#", 1)[0]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `etl_sigrid/infrastructure/excel/aux_file_source.py:81` [entero]

- Original: `return valor.split("?", 1)[0].split("#", 1)[0]`
- Mutado:   `return valor.split("?", 1)[0].split("#", 2)[0]`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

