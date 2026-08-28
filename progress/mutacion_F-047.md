<!-- progress/mutacion_F-047.md -->
# F-047 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-047` el 2026-08-28 06:52.

## Alcance

Origen del diff: **rama** (`7dd010dc252fc379a07ed9c433405ea4f900a633` .. `feature/F-047-nocturna-desfasada`).

| Fichero | Líneas en alcance |
|---|---|
| `etl_sigrid/application/steps/build_cierre_step.py` | 15 |
| `etl_sigrid/application/steps/build_compras_step.py` | 135 |
| `etl_sigrid/application/steps/build_retenciones_step.py` | 131 |
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | 12 |
| `etl_sigrid/domain/diccionario.py` | 1 |
| `etl_sigrid/infrastructure/inventario_repositorio.py` | 67 |
| `etl_sigrid/infrastructure/postgres/catalogo.py` | 188 |
| `harness/mutacion.py` | 29 |
| `harness/mutacion_paralela.py` | 101 |
| `harness/rigor.py` | 2 |
| `harness/tamano.py` | 7 |
| `main.py` | 143 |
| **Total** | **831** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 70 |
| Mutantes evaluados | 70 |
| Muertos | 63 |
| Supervivientes | 7 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 9117.3 s |
| SHA de HEAD medido | `977b957da76f7c3fd6c893dd6583518405c07d0e` |
| Línea base (s) — `.` | 185.7 |
| Media por mutante evaluado (s) | 130.2 |
| Timeout efectivo por mutante (s) | 372 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 1 |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/application/steps/build_compras_step.py:97` [entero]

- Original: `total_rows = 0`
- Mutado:   `total_rows = 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 2. `etl_sigrid/infrastructure/postgres/catalogo.py:200` [entero]

- Original: `declarados: int = 0`
- Mutado:   `declarados: int = 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 3. `etl_sigrid/infrastructure/postgres/catalogo.py:202` [entero]

- Original: `construidos: int = 0`
- Mutado:   `construidos: int = 1`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 4. `harness/mutacion_paralela.py:331` [comparacion]

- Original: `if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):`
- Mutado:   `if len(valor) > 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 5. `harness/mutacion_paralela.py:331` [entero]

- Original: `if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):`
- Mutado:   `if len(valor) >= 3 and valor[0] == valor[-1] and valor[0] in ("'", '"'):`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 6. `harness/tamano.py:157` [booleano]

- Original: `"--feature", required=True, help="Identificador de la feature, formato F-XXX"`
- Mutado:   `"--feature", required=False, help="Identificador de la feature, formato F-XXX"`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?

### 7. `main.py:553` [booleano]

- Original: `fg="red", err=True,`
- Mutado:   `fg="red", err=False,`

#### Análisis (PENDIENTE del implementer)

> Por qué ningún test lo caza: PENDIENTE.
> Decisión: ¿test nuevo o mutante equivalente justificado?


---

# Analisis de los 7 supervivientes (F-047, implementer)

Anadido a mano al informe que genera `harness/mutacion`. Campana **EN SERIE**
(`--workers 1`, `--max-mutantes 0`), 70 mutantes, 2 h 32 min. Se lanzo en serie
a proposito: la regla operativa de F-041 obliga a reverificar en serie lo que
una campana PARALELA declare muerto, y con 70 mutantes salia mas barato no
tener que hacerlo.

## Uno era FALSO SUPERVIVIENTE, y es un hallazgo nuevo

| Mutante | Veredicto de la campana | Reverificado a mano |
|---|---|---|
| `build_compras_step.py:97` `total_rows = 0 -> 1` | superviviente | **MUERTO**: `assert 23 == (11 * 2)` y `assert 1 == 0`, dos tests caidos |

**La campaña EN SERIE tambien miente**, y esto no esta en la ficha de F-041.
Lo que alli se documenta son falsos MUERTOS del modo paralelo (defecto 4) y
bytecode mutado que sobrevive entre ejecuciones (defecto 2). Esto es un falso
SUPERVIVIENTE con un solo worker, y el sospechoso es el mismo `__pycache__`: el
mutante 4/70 llego justo detras de otros tres sobre el mismo fichero, y si
pytest importo el bytecode SIN mutar, la suite paso y el mutante se declaro
vivo. **Direccion inofensiva** —un falso superviviente solo cuesta un test de
mas—, pero conviene anotarlo en F-041: el defecto del bytecode no es exclusivo
del modo paralelo.

Control: reverificado dos veces, con `__pycache__` borrado antes de cada
ejecucion. Muere las dos.

## Los otros seis eran reales, y los seis tienen ya su test

Reverificados uno a uno **en serie y con el bytecode limpio** antes de tocar
nada: los seis sobrevivian de verdad. Los seis son del mismo tipo —**nadie
comprobaba lo que el codigo DEJA DICHO ni sus valores por defecto**—, ninguno
cambia un numero de negocio, y los seis son ahora un test.

| Superviviente | Por que nadie lo cazaba | Test que lo mata |
|---|---|---|
| `catalogo.py:200` `declarados: int = 0 -> 1` | `evaluar_construccion` siempre pasa el campo; el defecto no lo miraba nadie. Una evaluacion vacia afirmaria un objeto declarado | `test_f047_r7_una_evaluacion_recien_construida_no_cuenta_nada` |
| `catalogo.py:202` `construidos: int = 0 -> 1` | igual | el mismo |
| `main.py:553` `err=True -> False` | el aviso «no se pudo comprobar lo declarado» salia por stdout y nadie miraba por donde | `test_f047_r5_run_all_no_se_traga_un_fallo_al_leer_el_catalogo`, ahora contra `resultado.stderr` |
| `mutacion_paralela.py:331` `len(valor) >= 2 -> > 2` | la parametrizacion del parseo de `.env` no tenia el caso del valor entrecomillado VACIO | `test_el_parseo_entiende_las_lineas_raras`, casos `CLAVE=""` y `CLAVE=''` |
| `mutacion_paralela.py:331` `>= 2 -> >= 3` | igual | el mismo |
| `tamano.py:157` `required=True -> False` | nadie comprobaba que `--feature` sea obligatoria. Sin ella la puerta mediria «la feature None», ningun fichero, y saldria en verde | `test_sin_feature_el_cli_no_adivina_cual_medir` |

**Control final**: los seis mutantes aplicados de nuevo a mano, con
`__pycache__` borrado y la suite entera. **Los seis MUEREN** (`1 failed` cada
uno). Salida en `SIGUEN VIVOS: NINGUNO`.

Los tres ultimos son del **arnes generico**, y estan en el alcance de esta
campana solo porque la rama nace de `feature/F-006-mcp-azure`. Sus dos tests se
portaron a `arnes-base` en el mismo trabajo (commit `f097e62`), como manda la
regla de propagacion.

## Una pasada anterior, para que conste

La primera campana en serie se interrumpio en el mutante 29/70 (la paro el
gestor de tareas, no un fallo suyo) y dio **8 supervivientes**, todos en los dos
steps nuevos y todos del mismo tipo: `exc_info`, `rows`, el guardian
`target_schema AND target_table` y el redondeo de `duration_s`. Los ocho tienen
test desde el commit `977b957`, verificados uno a uno a mano, y la campana
completa los da muertos.

**Total sobre esta feature: 15 supervivientes encontrados, 15 con test. Cero
justificados como equivalentes.**
