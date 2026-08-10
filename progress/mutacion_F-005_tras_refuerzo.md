<!-- progress/mutacion_F-005_tras_refuerzo.md -->
# F-005 · Campaña de mutación — TRAS EL REFUERZO DE F-016

Generado por `python -m harness.mutacion --feature F-005` el 2026-08-10 13:02.

> **Qué es este fichero.** La **misma** campaña de la línea base
> `progress/mutacion_F-005.md`, sobre el **mismo** alcance y el **mismo**
> código, con una sola diferencia: la suite lleva los ocho tests nuevos de
> F-016. Es una comparación de una sola variable.
>
> **La línea base histórica NO se toca.** `progress/mutacion_F-005.md` sigue
> tal cual la dejó F-015: es la medición del estado anterior y reescribirla
> borraría la única prueba de que el problema existía.

## Veredicto

**Los seis mutantes de riesgo ALTO están muertos.** Ninguno aparece ya en la
lista de supervivientes de este informe:

| # | Mutante de riesgo ALTO (línea base) | Antes | Ahora | Test que lo mata |
|---|---|---|---|---|
| 1 | `config/settings.py:103` `True,` → `False,` | superviviente | **muerto** | `test_f016_h1_el_defecto_de_auto_create_db_en_la_configuracion_es_true` |
| 2 | `postgres_client.py:78` `auto_create_db: bool = True,` → `False,` | superviviente | **muerto** | `test_f016_h2_el_defecto_de_auto_create_db_en_el_cliente_crea_la_base` |
| 3 | `postgres_client.py:201` `autocommit=True` → `False` | superviviente | **muerto** | `test_f016_h3_la_conexion_administrativa_se_abre_en_autocommit` |
| 4 | `fingerprint.py:334` `==` → `!=` | superviviente | **muerto** | `test_f016_h4_la_comparacion_de_textos_distingue_iguales_de_distintos` |
| 5 | `fingerprint.py:405` `==` → `!=` | superviviente | **muerto** | `test_f016_h5_el_detalle_de_la_diferencia_corresponde_a_su_gravedad` |
| 6 | `main.py:388` `==` → `!=` | superviviente | **muerto** | `test_f016_h6_un_paso_fallido_hace_salir_al_cli_con_codigo_1` |

Y **dos de riesgo MEDIO caen de propina**, porque los tests nuevos pasan por
encima de ellos:

| Mutante | Por qué muere ahora |
|---|---|
| `main.py:389` `sys.exit(1)` → `sys.exit(2)` | el test de `apply-grants` no afirma «distinto de cero»: afirma **1** |
| `fingerprint.py:400` `or` → `and` | con `and`, un `count` deja de ir por la rama de igualdad exacta y cae en la comparación numérica con tolerancia. La diferencia se sigue reportando, pero el motivo pasa a ser `diferencia 1.000000 (margen 0.010000)`, y el test de F-016 afirma el **motivo**, no solo la gravedad |

| Métrica | Línea base (F-015) | Tras el refuerzo (F-016) | Δ |
|---|---|---|---|
| Mutantes generados | 101 | 101 | = |
| Muertos | 46 | **54** | **+8** |
| Supervivientes | 55 | **47** | **−8** |
| Puntuación de mutación | 45,5 % | **53,5 %** | **+8,0 pp** |
| Supervivientes de riesgo ALTO | 6 | **0** | **−6** |
| Tests de la suite | 65 | 73 | +8 |
| Tiempo de la campaña | 129,1 s | 134,6 s | +5,5 s |

## Cómo se obtuvo (para poder repetirlo)

**Árbol**: un `git worktree` desprendido en el commit de merge de F-005, NO el
árbol vivo. Motivo doble: (1) los números de línea del informe coinciden
exactamente con los de la línea base, que es lo que hace comparables los dos
informes —en el árbol de hoy `postgres_client.py` ha crecido y el mismo
mutante está en la línea 133, no en la 78—; y (2) mutar ficheros en el árbol
vivo mientras el `.env` apunta a producción es un riesgo que no hace falta
correr.

```bash
# 1. árbol de trabajo aparte, en el merge de F-005
git worktree add --detach C:/Users/pgris/PycharmProjects/wt-f016-c7500d4 c7500d4

# 2. la ÚNICA diferencia respecto a la línea base: los tests nuevos
cp tests/test_f016_huecos_alto_f005.py C:/Users/pgris/PycharmProjects/wt-f016-c7500d4/tests/

# 3. suite de referencia verde en ese árbol ANTES de mutar nada
#    (65 tests sin el fichero nuevo, 73 con él; ambas en verde)
cd C:/Users/pgris/PycharmProjects/wt-f016-c7500d4 && python -m pytest -q

# 4. la campaña, lanzada DESDE el repositorio principal (el arnés y
#    harness/rigor.json son los de hoy; el código mutado es el de c7500d4)
cd C:/Users/pgris/PycharmProjects/datamart-seg-anual
python -m harness.mutacion --feature F-005 --base c7500d4 --rama __no_existe__ \
    --raiz C:/Users/pgris/PycharmProjects/wt-f016-c7500d4 \
    --salida progress/mutacion_F-005_tras_refuerzo.md
```

**`--rama __no_existe__` no es un adorno**: es la línea de comando literal que
pedía la observación 1 de `progress/review_F-015.md`. Sin ella,
`resolver_refs` encuentra la rama `feature/F-005-postgres-azure`, que todavía
existe, resuelve por rama en vez de por merge y devuelve **alcance vacío**.
Neutralizada la rama, cae en la vía del merge y sale el alcance correcto:
20 ficheros y 1.669 líneas, idéntico fichero a fichero al de la línea base
(comprobado antes de lanzar la campaña).

Al terminar, el worktree queda sin ningún fichero mutado (la campaña restaura
siempre) y se retira con `git worktree remove`.

## Deuda que queda viva

Los 47 supervivientes están **todos** analizados abajo, uno a uno. Ninguno
queda en `PENDIENTE`. El análisis de cada uno es el de la línea base —es
literalmente el mismo mutante— más una línea de estado en F-016.

| Veredicto | Nº | Qué se hace |
|---|---|---|
| Equivalente en la práctica | 8 | Nada. Son garantías internas (`frozen`, `slots`) que ningún comportamiento observable expone; testearlas sería ruido |
| Hueco real, riesgo MEDIO | 24 | **Deuda contabilizada.** Fuera del alcance que el humano fijó para F-016 (solo los seis de riesgo ALTO) |
| Hueco real, riesgo BAJO | 15 | **Deuda contabilizada.** Ídem |
| Hueco real, riesgo **ALTO** | **0** | — |

**Nota de recuento, para que nadie se pelee con los números.** La tabla resumen
de la línea base dice «27 MEDIO / 14 BAJO», pero si se cuentan sus **veredictos
uno a uno** salen 26 y 15. Es un desliz de la tabla resumen de aquel informe,
no de la medición: los 55 supervivientes y sus 55 veredictos están bien. Aquí
se cuentan los veredictos, que es lo que se puede auditar línea a línea. La
línea base **no se retoca**: se deja constancia y ya.

**Lo que esto significa.** F-005 está declarada `critico` y sigue sin pasar su
propio nivel: 53,5 % de puntuación de mutación no es una nota de aprobado. Lo
que sí ha cambiado es que **ya no queda ningún hueco de los que hacen que una
carga mala se dé por buena o que un interruptor de seguridad se caiga sin que
nadie se entere**. El resto es deuda visible, contada y priorizable, que es
exactamente donde tiene que estar.

## Alcance

Origen del diff: **merge** (`c7500d4bf8494070a541fe1e4f73471a0bfa2580^1` .. `c7500d4bf8494070a541fe1e4f73471a0bfa2580`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 106 |
| `etl_sigrid/application/orchestrator.py` | 28 |
| `etl_sigrid/application/ports.py` | 29 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 101 |
| `etl_sigrid/application/steps/build_cierre_step.py` | 2 |
| `etl_sigrid/application/steps/build_maestros_step.py` | 2 |
| `etl_sigrid/application/steps/build_mart_step.py` | 2 |
| `etl_sigrid/application/steps/build_stg_step.py` | 2 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 2 |
| `etl_sigrid/infrastructure/azure/__init__.py` | 1 |
| `etl_sigrid/infrastructure/azure/entra_token.py` | 113 |
| `etl_sigrid/infrastructure/postgres/client_factory.py` | 48 |
| `etl_sigrid/infrastructure/postgres/conninfo.py` | 126 |
| `etl_sigrid/infrastructure/postgres/fingerprint.py` | 460 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 74 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 278 |
| `etl_sigrid/infrastructure/postgres/step_run_recorder.py` | 37 |
| `etl_sigrid/infrastructure/postgres/timings.py` | 77 |
| `main.py` | 179 |
| `scripts/refresh_presupuesto.py` | 2 |
| **Total** | **1669** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 101 |
| Mutantes evaluados | 101 |
| Muertos | 54 |
| Supervivientes | 47 |
| Timeouts | 0 |
| Tiempo total | 134.6 s |
| Muestreo | no: campaña completa |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `etl_sigrid/infrastructure/azure/entra_token.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que el dataclass sea inmutable.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 2. `etl_sigrid/infrastructure/azure/entra_token.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que el dataclass use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 3. `etl_sigrid/infrastructure/azure/entra_token.py:63` [entero]

- Original: `def __init__(self, credential: Any | None = None, margin_s: int = 300) -> None:`
- Mutado:   `def __init__(self, credential: Any | None = None, margin_s: int = 301) -> None:`

#### Análisis

- **Por qué ningún test lo caza:** El margen por defecto de renovacion del token (300 s) no lo fija ningun test; solo se ejercitan margenes pasados explicitamente.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 4. `etl_sigrid/infrastructure/azure/entra_token.py:74` [comparacion]

- Original: `if cache is not None and cache.expires_on - time.time() > self._margin_s:`
- Mutado:   `if cache is not None and cache.expires_on - time.time() >= self._margin_s:`

#### Análisis

- **Por qué ningún test lo caza:** La frontera exacta de caducidad del token (`>` frente a `>=`) no tiene test: nadie prueba el caso en que faltan exactamente los segundos del margen.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 5. `etl_sigrid/infrastructure/postgres/fingerprint.py:64` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad de la entidad de huella.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 6. `etl_sigrid/infrastructure/postgres/fingerprint.py:64` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 7. `etl_sigrid/infrastructure/postgres/fingerprint.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad de la entidad de diferencia.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 8. `etl_sigrid/infrastructure/postgres/fingerprint.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 9. `etl_sigrid/infrastructure/postgres/fingerprint.py:213` [booleano]

- Original: `for nombre, valor in zip(nombres, valores, strict=True)`
- Mutado:   `for nombre, valor in zip(nombres, valores, strict=False)`

#### Análisis

- **Por qué ningún test lo caza:** El `strict=True` del zip es una defensa contra cabeceras descuadradas; ningun test le pasa listas de distinta longitud.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 10. `etl_sigrid/infrastructure/postgres/fingerprint.py:246` [entero]

- Original: `return date(int(anio), int(mes), 1)`
- Mutado:   `return date(int(anio), int(mes), 2)`

#### Análisis

- **Por qué ningún test lo caza:** El dia del periodo (siempre 1) no lo comprueba ningun test: solo se verifica anio y mes.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 11. `etl_sigrid/infrastructure/postgres/fingerprint.py:302` [booleano]

- Original: `path.parent.mkdir(parents=True, exist_ok=True)`
- Mutado:   `path.parent.mkdir(parents=False, exist_ok=True)`

#### Análisis

- **Por qué ningún test lo caza:** Que se creen los directorios intermedios al escribir la huella no lo comprueba ningun test: todos escriben en un directorio que ya existe.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 12. `etl_sigrid/infrastructure/postgres/fingerprint.py:321` [entero]

- Original: `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[0])}"`
- Mutado:   `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[1])}"`

#### Análisis

- **Por qué ningún test lo caza:** El indice de la fila que se cita en el mensaje de error de cabecera no lo comprueba ningun test: se verifica que falla, no que el mensaje sea util.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 13. `etl_sigrid/infrastructure/postgres/fingerprint.py:333` [logico]

- Original: `if num_a is None or num_b is None:`
- Mutado:   `if num_a is None and num_b is None:`

#### Análisis

- **Por qué ningún test lo caza:** La decision entre comparar como numero o como texto cuando SOLO UNO de los dos valores no es numerico no tiene test: se prueban los dos numericos o los dos texto.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 14. `etl_sigrid/infrastructure/postgres/fingerprint.py:338` [comparacion]

- Original: `return diferencia <= margen, f"diferencia {diferencia:.6f} (margen {margen:.6f})"`
- Mutado:   `return diferencia < margen, f"diferencia {diferencia:.6f} (margen {margen:.6f})"`

#### Análisis

- **Por qué ningún test lo caza:** La frontera del margen de tolerancia (`<=` frente a `<`) no tiene test: nadie prueba una diferencia exactamente igual al margen.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 15. `etl_sigrid/infrastructure/postgres/postgres_client.py:46` [entero]

- Original: `TIMINGS_SIN_ANCLA = 100`
- Mutado:   `TIMINGS_SIN_ANCLA = 101`

#### Análisis

- **Por qué ningún test lo caza:** El valor de la constante de timings sin ancla no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 16. `etl_sigrid/infrastructure/postgres/postgres_client.py:97` [booleano]

- Original: `def _connect(self, conninfo: ConnInfo, *, autocommit: bool = False) -> psycopg.Connection:`
- Mutado:   `def _connect(self, conninfo: ConnInfo, *, autocommit: bool = True) -> psycopg.Connection:`

#### Análisis

- **Por qué ningún test lo caza:** El `autocommit` por defecto de las conexiones no lo fija ningun test; invertido, cada conexion normal pasaria a autocommit.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 17. `etl_sigrid/infrastructure/postgres/postgres_client.py:452` [entero]

- Original: `return [row[0] for row in cur.fetchall()]`
- Mutado:   `return [row[1] for row in cur.fetchall()]`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna con que se leen los nombres devueltos por la consulta no lo comprueba ningun test: los dobles devuelven filas donde el indice da igual.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 18. `etl_sigrid/infrastructure/postgres/postgres_client.py:479` [not]

- Original: `if not sentencias:`
- Mutado:   `if sentencias:`

#### Análisis

- **Por qué ningún test lo caza:** La guarda de lista de sentencias vacia no tiene test: nadie llama con una lista vacia.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 19. `etl_sigrid/infrastructure/postgres/postgres_client.py:614` [entero]

- Original: `def fetch_timings(self, last: int = 1) -> list[Timing]:`
- Mutado:   `def fetch_timings(self, last: int = 2) -> list[Timing]:`

#### Análisis

- **Por qué ningún test lo caza:** El numero de ejecuciones que se devuelven por defecto no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 20. `etl_sigrid/infrastructure/postgres/postgres_client.py:643` [entero]

- Original: `desde = row[0] if row else None`
- Mutado:   `desde = row[1] if row else None`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna del que sale la fecha de inicio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 21. `etl_sigrid/infrastructure/postgres/postgres_client.py:670` [entero]

- Original: `stage=fila[0],`
- Mutado:   `stage=fila[1],`

#### Análisis

- **Por qué ningún test lo caza:** El mapeo fila->objeto no esta verificado columna a columna: nadie comprueba que `stage` salga de la columna 0.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 22. `etl_sigrid/infrastructure/postgres/postgres_client.py:671` [entero]

- Original: `step=fila[1],`
- Mutado:   `step=fila[2],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `step`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 23. `etl_sigrid/infrastructure/postgres/postgres_client.py:672` [entero]

- Original: `started_at=fila[2],`
- Mutado:   `started_at=fila[3],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `started_at`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 24. `etl_sigrid/infrastructure/postgres/postgres_client.py:673` [entero]

- Original: `finished_at=fila[3],`
- Mutado:   `finished_at=fila[4],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `finished_at`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 25. `etl_sigrid/infrastructure/postgres/postgres_client.py:674` [entero]

- Original: `status=fila[4],`
- Mutado:   `status=fila[5],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `status`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 26. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [entero]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[6] or 0),`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `rows_processed`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 27. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [logico]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[5] and 0),`

#### Análisis

- **Por qué ningún test lo caza:** El valor de respaldo cuando la columna viene a nulo no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 28. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [entero]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[5] or 1),`

#### Análisis

- **Por qué ningún test lo caza:** El cero de respaldo de filas procesadas no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 29. `etl_sigrid/infrastructure/postgres/postgres_client.py:687` [entero]

- Original: `rows_processed: int = 0,`
- Mutado:   `rows_processed: int = 1,`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto del parametro de filas procesadas no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 30. `etl_sigrid/infrastructure/postgres/postgres_client.py:711` [logico]

- Original: `started_at or datetime.utcnow(),`
- Mutado:   `started_at and datetime.utcnow(),`

#### Análisis

- **Por qué ningún test lo caza:** Que la fecha de inicio se rellene con la hora actual cuando no se pasa no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 31. `etl_sigrid/infrastructure/postgres/postgres_client.py:720` [entero]

- Original: `return int(row[0]) if row else 0`
- Mutado:   `return int(row[1]) if row else 0`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna del recuento no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 32. `etl_sigrid/infrastructure/postgres/postgres_client.py:720` [entero]

- Original: `return int(row[0]) if row else 0`
- Mutado:   `return int(row[0]) if row else 1`

#### Análisis

- **Por qué ningún test lo caza:** El cero de respaldo cuando no hay fila no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 33. `etl_sigrid/infrastructure/postgres/step_run_recorder.py:36` [logico]

- Original: `metadata=result.metadata or None,`
- Mutado:   `metadata=result.metadata and None,`

#### Análisis

- **Por qué ningún test lo caza:** Que los metadatos vacios se guarden como nulo no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 34. `etl_sigrid/infrastructure/postgres/timings.py:17` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad del registro de tiempos.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 35. `etl_sigrid/infrastructure/postgres/timings.py:17` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.
- **Estado en F-016:** sigue vivo y así debe seguir: testear una garantía interna que ningún comportamiento observable expone sería ruido.

### 36. `etl_sigrid/infrastructure/postgres/timings.py:70` [aritmetico]

- Original: `total_s += t.duration_seconds`
- Mutado:   `total_s -= t.duration_seconds`

#### Análisis

- **Por qué ningún test lo caza:** El total de segundos del resumen de tiempos no lo comprueba ningun test: se verifica que la tabla se pinta, no que sume.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 37. `etl_sigrid/infrastructure/postgres/timings.py:71` [aritmetico]

- Original: `total_filas += t.rows_processed`
- Mutado:   `total_filas -= t.rows_processed`

#### Análisis

- **Por qué ningún test lo caza:** El total de filas del resumen tampoco: mismo hueco que el 42.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 38. `main.py:237` [booleano]

- Original: `def build_pipeline_steps(settings, full_refresh: bool = False) -> list:`
- Mutado:   `def build_pipeline_steps(settings, full_refresh: bool = True) -> list:`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de la carga completa al construir el pipeline no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 39. `main.py:256` [booleano]

- Original: `@click.option("--full", "full_refresh", is_flag=True, default=False)`
- Mutado:   `@click.option("--full", "full_refresh", is_flag=False, default=False)`

#### Análisis

- **Por qué ningún test lo caza:** Que `--full` sea un interruptor sin valor no lo comprueba ningun test: ninguno invoca ese comando del CLI.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 40. `main.py:256` [booleano]

- Original: `@click.option("--full", "full_refresh", is_flag=True, default=False)`
- Mutado:   `@click.option("--full", "full_refresh", is_flag=True, default=True)`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de `--full` (carga incremental salvo que se pida lo contrario) no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 41. `main.py:287` [booleano]

- Original: `type=click.Path(dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(dir_okay=True, path_type=Path),`

#### Análisis

- **Por qué ningún test lo caza:** Que la ruta de salida no admita un directorio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 42. `main.py:288` [booleano]

- Original: `required=True,`
- Mutado:   `required=False,`

#### Análisis

- **Por qué ningún test lo caza:** Que la opcion sea obligatoria no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.
- **Estado en F-016:** **sigue vivo**. F-016 cierra solo los seis huecos de riesgo ALTO por decisión del humano; este queda como **deuda contabilizada**, no tapada.

### 43. `main.py:340` [booleano]

- Original: `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_a", type=click.Path(exists=False, dir_okay=False, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Que el fichero de huella deba existir no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 44. `main.py:340` [booleano]

- Original: `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=True, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Que no valga un directorio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 45. `main.py:341` [booleano]

- Original: `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_b", type=click.Path(exists=False, dir_okay=False, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para la segunda huella.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 46. `main.py:341` [booleano]

- Original: `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=True, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para la segunda huella.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

### 47. `main.py:362` [entero]

- Original: `default=1,`
- Mutado:   `default=2,`

#### Análisis

- **Por qué ningún test lo caza:** El numero de ejecuciones por defecto del comando de tiempos no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.
- **Estado en F-016:** **sigue vivo**. Fuera del alcance acordado (solo los seis de riesgo ALTO). Deuda contabilizada.

