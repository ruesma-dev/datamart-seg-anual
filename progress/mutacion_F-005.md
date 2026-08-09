<!-- progress/mutacion_F-005.md -->
# F-005 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-005` el 2026-08-09 15:10.

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
| Muertos | 46 |
| Supervivientes | 55 |
| Timeouts | 0 |
| Tiempo total | 129.1 s |
| Muestreo | no: campaña completa |

## Cómo se obtuvo esta línea base

- **Alcance reconstruido desde el commit de merge** de F-005 (`c7500d4`,
  `Merge branch 'feature/F-005-postgres-azure' into dev`), diff entre su
  primer padre y el propio merge, tal y como exige R4 de F-015.
- **Ejecutada sobre un árbol de trabajo aparte** (`git worktree` en
  `c7500d4`), NO sobre el árbol vivo del repositorio: el 2026-08-09 había una
  carga `run-all --full` corriendo contra Azure desde este mismo directorio y
  un mutante escrito en disco podía acabar importado por ese proceso. Como
  efecto secundario, los números de línea del diff coinciden exactamente con
  los ficheros mutados.
- **Suite de referencia verde antes de empezar**: 65 tests en 1,6 s en ese
  árbol, sin `.env` y sin abrir red ni BBDD. Si la suite base fallara, todos
  los mutantes saldrían "muertos" y la medición no valdría nada.
- **Campaña completa, sin muestreo**: 101 mutantes en 129 s, muy por debajo
  del límite de ~45 min que habría obligado a muestrear (DA-5 de la spec).
- **Fuera de esta línea base**: el fix posterior `e9e80d6`
  (`fix/F-005-nosuperuser-azure`), mergeado aparte en `c9d8d23`. Nota para
  quien repita la medida: `git log --merges --grep "F-005" -n 1` devuelve
  **ese** merge, no el de la feature; por eso la campaña se lanzó acotando la
  búsqueda con `--base c7500d4`.

## Lectura de los resultados

**Puntuación de mutación: 46 / 101 = 45,5 %.** Incomoda, y debe incomodar:
más de la mitad de las mutaciones aplicadas a las líneas que F-005 escribió
pasan la suite sin que nadie se entere. Reparto de los 55 supervivientes:

| Veredicto | Nº | Qué significa |
|---|---|---|
| Equivalente en la práctica | 8 | `@dataclass(frozen=True, slots=True)` → garantías internas que ningún test afirma. Testearlas sería ruido |
| Hueco real, riesgo **ALTO** | 6 | Decisiones de las que depende que una carga mala se dé por buena, o interruptores de seguridad sin fijar |
| Hueco real, riesgo MEDIO | 27 | Mapeos fila→objeto, fronteras de comparación, agregados y opciones del CLI |
| Hueco real, riesgo BAJO | 14 | Valores por defecto y mensajes de diagnóstico |

Los seis de riesgo ALTO, por si se ataja la deuda por algún sitio:

1. `config/settings.py:103` y `postgres_client.py:78` — el valor por defecto
   de `auto_create_db`, que la propia F-005 declaró **puerta bloqueante**
   contra el servidor compartido de producción, no lo fija ningún test.
2. `postgres_client.py:201` — que la conexión administrativa se abra en
   autocommit (sin ello `CREATE DATABASE` falla) no lo comprueba nadie.
3. `fingerprint.py:334` y `fingerprint.py:405` — la igualdad de textos y la
   clasificación de una diferencia como FALLO: el corazón de la verificación
   de que las vistas responden igual en Azure que en local.
4. `main.py:388` — la detección de un paso fallido del pipeline; invertida, el
   CLI daría por buena una ejecución fallida.

**Estos huecos NO se parchean en F-015.** Los tests de F-005 son el *objeto*
de esta medición: taparlos aquí falsearía la línea base. Quedan como deuda
anotada para que el humano decida si abre una feature de refuerzo.

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

### 1. `config/settings.py:103` [booleano]

- Original: `True,`
- Mutado:   `False,`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de `auto_create_db` en la configuracion no lo fija ningun test. Es justo el interruptor que la propia F-005 declaro puerta bloqueante contra el servidor compartido: si alguien lo cambia a False por descuido, la suite sigue verde.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 2. `etl_sigrid/infrastructure/azure/entra_token.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que el dataclass sea inmutable.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 3. `etl_sigrid/infrastructure/azure/entra_token.py:44` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que el dataclass use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 4. `etl_sigrid/infrastructure/azure/entra_token.py:63` [entero]

- Original: `def __init__(self, credential: Any | None = None, margin_s: int = 300) -> None:`
- Mutado:   `def __init__(self, credential: Any | None = None, margin_s: int = 301) -> None:`

#### Análisis

- **Por qué ningún test lo caza:** El margen por defecto de renovacion del token (300 s) no lo fija ningun test; solo se ejercitan margenes pasados explicitamente.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 5. `etl_sigrid/infrastructure/azure/entra_token.py:74` [comparacion]

- Original: `if cache is not None and cache.expires_on - time.time() > self._margin_s:`
- Mutado:   `if cache is not None and cache.expires_on - time.time() >= self._margin_s:`

#### Análisis

- **Por qué ningún test lo caza:** La frontera exacta de caducidad del token (`>` frente a `>=`) no tiene test: nadie prueba el caso en que faltan exactamente los segundos del margen.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 6. `etl_sigrid/infrastructure/postgres/fingerprint.py:64` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad de la entidad de huella.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 7. `etl_sigrid/infrastructure/postgres/fingerprint.py:64` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 8. `etl_sigrid/infrastructure/postgres/fingerprint.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad de la entidad de diferencia.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 9. `etl_sigrid/infrastructure/postgres/fingerprint.py:83` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 10. `etl_sigrid/infrastructure/postgres/fingerprint.py:213` [booleano]

- Original: `for nombre, valor in zip(nombres, valores, strict=True)`
- Mutado:   `for nombre, valor in zip(nombres, valores, strict=False)`

#### Análisis

- **Por qué ningún test lo caza:** El `strict=True` del zip es una defensa contra cabeceras descuadradas; ningun test le pasa listas de distinta longitud.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 11. `etl_sigrid/infrastructure/postgres/fingerprint.py:246` [entero]

- Original: `return date(int(anio), int(mes), 1)`
- Mutado:   `return date(int(anio), int(mes), 2)`

#### Análisis

- **Por qué ningún test lo caza:** El dia del periodo (siempre 1) no lo comprueba ningun test: solo se verifica anio y mes.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 12. `etl_sigrid/infrastructure/postgres/fingerprint.py:302` [booleano]

- Original: `path.parent.mkdir(parents=True, exist_ok=True)`
- Mutado:   `path.parent.mkdir(parents=False, exist_ok=True)`

#### Análisis

- **Por qué ningún test lo caza:** Que se creen los directorios intermedios al escribir la huella no lo comprueba ningun test: todos escriben en un directorio que ya existe.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 13. `etl_sigrid/infrastructure/postgres/fingerprint.py:321` [entero]

- Original: `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[0])}"`
- Mutado:   `f"{';'.join(CABECERA_CSV)} y se encontró {';'.join(filas[1])}"`

#### Análisis

- **Por qué ningún test lo caza:** El indice de la fila que se cita en el mensaje de error de cabecera no lo comprueba ningun test: se verifica que falla, no que el mensaje sea util.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 14. `etl_sigrid/infrastructure/postgres/fingerprint.py:333` [logico]

- Original: `if num_a is None or num_b is None:`
- Mutado:   `if num_a is None and num_b is None:`

#### Análisis

- **Por qué ningún test lo caza:** La decision entre comparar como numero o como texto cuando SOLO UNO de los dos valores no es numerico no tiene test: se prueban los dos numericos o los dos texto.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 15. `etl_sigrid/infrastructure/postgres/fingerprint.py:334` [comparacion]

- Original: `return valor_a == valor_b, "texto"`
- Mutado:   `return valor_a != valor_b, "texto"`

#### Análisis

- **Por qué ningún test lo caza:** La igualdad de valores de texto al comparar dos huellas no tiene test que la caze. Es el nucleo de la verificacion de que las vistas responden igual en Azure que en local: invertida, la comparacion declararia iguales las huellas distintas.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 16. `etl_sigrid/infrastructure/postgres/fingerprint.py:338` [comparacion]

- Original: `return diferencia <= margen, f"diferencia {diferencia:.6f} (margen {margen:.6f})"`
- Mutado:   `return diferencia < margen, f"diferencia {diferencia:.6f} (margen {margen:.6f})"`

#### Análisis

- **Por qué ningún test lo caza:** La frontera del margen de tolerancia (`<=` frente a `<`) no tiene test: nadie prueba una diferencia exactamente igual al margen.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 17. `etl_sigrid/infrastructure/postgres/fingerprint.py:400` [logico]

- Original: `if bloque == BLOQUE_ESTRUCTURA or metrica == METRICA_COUNT:`
- Mutado:   `if bloque == BLOQUE_ESTRUCTURA and metrica == METRICA_COUNT:`

#### Análisis

- **Por qué ningún test lo caza:** La combinacion de condiciones que decide si una diferencia es estructural no tiene test para el caso en que solo se cumple una de las dos.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 18. `etl_sigrid/infrastructure/postgres/fingerprint.py:405` [comparacion]

- Original: `if gravedad == FALLO`
- Mutado:   `if gravedad != FALLO`

#### Análisis

- **Por qué ningún test lo caza:** La clasificacion de una diferencia como FALLO no tiene test que la caze invertida. De esta decision depende que la verificacion de la carga en Azure de por buena una carga mala.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 19. `etl_sigrid/infrastructure/postgres/postgres_client.py:46` [entero]

- Original: `TIMINGS_SIN_ANCLA = 100`
- Mutado:   `TIMINGS_SIN_ANCLA = 101`

#### Análisis

- **Por qué ningún test lo caza:** El valor de la constante de timings sin ancla no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 20. `etl_sigrid/infrastructure/postgres/postgres_client.py:78` [booleano]

- Original: `auto_create_db: bool = True,`
- Mutado:   `auto_create_db: bool = False,`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de `auto_create_db` en el cliente de base de datos tampoco lo fija ningun test. Mismo riesgo que el superviviente 1, en la otra punta del camino.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 21. `etl_sigrid/infrastructure/postgres/postgres_client.py:97` [booleano]

- Original: `def _connect(self, conninfo: ConnInfo, *, autocommit: bool = False) -> psycopg.Connection:`
- Mutado:   `def _connect(self, conninfo: ConnInfo, *, autocommit: bool = True) -> psycopg.Connection:`

#### Análisis

- **Por qué ningún test lo caza:** El `autocommit` por defecto de las conexiones no lo fija ningun test; invertido, cada conexion normal pasaria a autocommit.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 22. `etl_sigrid/infrastructure/postgres/postgres_client.py:201` [booleano]

- Original: `admin_conn = self._connect(self._admin_conninfo, autocommit=True)`
- Mutado:   `admin_conn = self._connect(self._admin_conninfo, autocommit=False)`

#### Análisis

- **Por qué ningún test lo caza:** Que la conexion administrativa se abra en autocommit no lo comprueba ningun test. Sin autocommit, CREATE DATABASE falla: es una condicion de correccion, no un detalle.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 23. `etl_sigrid/infrastructure/postgres/postgres_client.py:452` [entero]

- Original: `return [row[0] for row in cur.fetchall()]`
- Mutado:   `return [row[1] for row in cur.fetchall()]`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna con que se leen los nombres devueltos por la consulta no lo comprueba ningun test: los dobles devuelven filas donde el indice da igual.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 24. `etl_sigrid/infrastructure/postgres/postgres_client.py:479` [not]

- Original: `if not sentencias:`
- Mutado:   `if sentencias:`

#### Análisis

- **Por qué ningún test lo caza:** La guarda de lista de sentencias vacia no tiene test: nadie llama con una lista vacia.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 25. `etl_sigrid/infrastructure/postgres/postgres_client.py:614` [entero]

- Original: `def fetch_timings(self, last: int = 1) -> list[Timing]:`
- Mutado:   `def fetch_timings(self, last: int = 2) -> list[Timing]:`

#### Análisis

- **Por qué ningún test lo caza:** El numero de ejecuciones que se devuelven por defecto no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 26. `etl_sigrid/infrastructure/postgres/postgres_client.py:643` [entero]

- Original: `desde = row[0] if row else None`
- Mutado:   `desde = row[1] if row else None`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna del que sale la fecha de inicio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 27. `etl_sigrid/infrastructure/postgres/postgres_client.py:670` [entero]

- Original: `stage=fila[0],`
- Mutado:   `stage=fila[1],`

#### Análisis

- **Por qué ningún test lo caza:** El mapeo fila->objeto no esta verificado columna a columna: nadie comprueba que `stage` salga de la columna 0.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 28. `etl_sigrid/infrastructure/postgres/postgres_client.py:671` [entero]

- Original: `step=fila[1],`
- Mutado:   `step=fila[2],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `step`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 29. `etl_sigrid/infrastructure/postgres/postgres_client.py:672` [entero]

- Original: `started_at=fila[2],`
- Mutado:   `started_at=fila[3],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `started_at`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 30. `etl_sigrid/infrastructure/postgres/postgres_client.py:673` [entero]

- Original: `finished_at=fila[3],`
- Mutado:   `finished_at=fila[4],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `finished_at`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 31. `etl_sigrid/infrastructure/postgres/postgres_client.py:674` [entero]

- Original: `status=fila[4],`
- Mutado:   `status=fila[5],`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `status`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 32. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [entero]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[6] or 0),`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para `rows_processed`.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 33. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [logico]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[5] and 0),`

#### Análisis

- **Por qué ningún test lo caza:** El valor de respaldo cuando la columna viene a nulo no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 34. `etl_sigrid/infrastructure/postgres/postgres_client.py:675` [entero]

- Original: `rows_processed=int(fila[5] or 0),`
- Mutado:   `rows_processed=int(fila[5] or 1),`

#### Análisis

- **Por qué ningún test lo caza:** El cero de respaldo de filas procesadas no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 35. `etl_sigrid/infrastructure/postgres/postgres_client.py:687` [entero]

- Original: `rows_processed: int = 0,`
- Mutado:   `rows_processed: int = 1,`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto del parametro de filas procesadas no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 36. `etl_sigrid/infrastructure/postgres/postgres_client.py:711` [logico]

- Original: `started_at or datetime.utcnow(),`
- Mutado:   `started_at and datetime.utcnow(),`

#### Análisis

- **Por qué ningún test lo caza:** Que la fecha de inicio se rellene con la hora actual cuando no se pasa no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 37. `etl_sigrid/infrastructure/postgres/postgres_client.py:720` [entero]

- Original: `return int(row[0]) if row else 0`
- Mutado:   `return int(row[1]) if row else 0`

#### Análisis

- **Por qué ningún test lo caza:** El indice de columna del recuento no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 38. `etl_sigrid/infrastructure/postgres/postgres_client.py:720` [entero]

- Original: `return int(row[0]) if row else 0`
- Mutado:   `return int(row[0]) if row else 1`

#### Análisis

- **Por qué ningún test lo caza:** El cero de respaldo cuando no hay fila no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 39. `etl_sigrid/infrastructure/postgres/step_run_recorder.py:36` [logico]

- Original: `metadata=result.metadata or None,`
- Mutado:   `metadata=result.metadata and None,`

#### Análisis

- **Por qué ningún test lo caza:** Que los metadatos vacios se guarden como nulo no tiene test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 40. `etl_sigrid/infrastructure/postgres/timings.py:17` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=False, slots=True)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba la inmutabilidad del registro de tiempos.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 41. `etl_sigrid/infrastructure/postgres/timings.py:17` [booleano]

- Original: `@dataclass(frozen=True, slots=True)`
- Mutado:   `@dataclass(frozen=True, slots=False)`

#### Análisis

- **Por qué ningún test lo caza:** Ningun test comprueba que use `slots`.
- **Veredicto:** **Equivalente en la practica.** Cambia una garantia interna, no el comportamiento observable del ETL. Testearlo seria ruido.

### 42. `etl_sigrid/infrastructure/postgres/timings.py:70` [aritmetico]

- Original: `total_s += t.duration_seconds`
- Mutado:   `total_s -= t.duration_seconds`

#### Análisis

- **Por qué ningún test lo caza:** El total de segundos del resumen de tiempos no lo comprueba ningun test: se verifica que la tabla se pinta, no que sume.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 43. `etl_sigrid/infrastructure/postgres/timings.py:71` [aritmetico]

- Original: `total_filas += t.rows_processed`
- Mutado:   `total_filas -= t.rows_processed`

#### Análisis

- **Por qué ningún test lo caza:** El total de filas del resumen tampoco: mismo hueco que el 42.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 44. `main.py:237` [booleano]

- Original: `def build_pipeline_steps(settings, full_refresh: bool = False) -> list:`
- Mutado:   `def build_pipeline_steps(settings, full_refresh: bool = True) -> list:`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de la carga completa al construir el pipeline no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 45. `main.py:256` [booleano]

- Original: `@click.option("--full", "full_refresh", is_flag=True, default=False)`
- Mutado:   `@click.option("--full", "full_refresh", is_flag=False, default=False)`

#### Análisis

- **Por qué ningún test lo caza:** Que `--full` sea un interruptor sin valor no lo comprueba ningun test: ninguno invoca ese comando del CLI.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 46. `main.py:256` [booleano]

- Original: `@click.option("--full", "full_refresh", is_flag=True, default=False)`
- Mutado:   `@click.option("--full", "full_refresh", is_flag=True, default=True)`

#### Análisis

- **Por qué ningún test lo caza:** El valor por defecto de `--full` (carga incremental salvo que se pida lo contrario) no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 47. `main.py:287` [booleano]

- Original: `type=click.Path(dir_okay=False, path_type=Path),`
- Mutado:   `type=click.Path(dir_okay=True, path_type=Path),`

#### Análisis

- **Por qué ningún test lo caza:** Que la ruta de salida no admita un directorio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 48. `main.py:288` [booleano]

- Original: `required=True,`
- Mutado:   `required=False,`

#### Análisis

- **Por qué ningún test lo caza:** Que la opcion sea obligatoria no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

### 49. `main.py:340` [booleano]

- Original: `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_a", type=click.Path(exists=False, dir_okay=False, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Que el fichero de huella deba existir no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 50. `main.py:340` [booleano]

- Original: `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_a", type=click.Path(exists=True, dir_okay=True, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Que no valga un directorio no lo comprueba ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 51. `main.py:341` [booleano]

- Original: `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_b", type=click.Path(exists=False, dir_okay=False, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para la segunda huella.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 52. `main.py:341` [booleano]

- Original: `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=False, path_type=Path))`
- Mutado:   `@click.argument("huella_b", type=click.Path(exists=True, dir_okay=True, path_type=Path))`

#### Análisis

- **Por qué ningún test lo caza:** Mismo hueco para la segunda huella.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 53. `main.py:362` [entero]

- Original: `default=1,`
- Mutado:   `default=2,`

#### Análisis

- **Por qué ningún test lo caza:** El numero de ejecuciones por defecto del comando de tiempos no lo fija ningun test.
- **Veredicto:** **Hueco real, riesgo BAJO.** Deuda anotada; el coste de fijarlo con un test supera hoy su valor.

### 54. `main.py:388` [comparacion]

- Original: `if result.status == StepStatus.FAILED:`
- Mutado:   `if result.status != StepStatus.FAILED:`

#### Análisis

- **Por qué ningún test lo caza:** La deteccion de un paso fallido en el pipeline no tiene test que la caze invertida: con la comparacion al reves, el CLI daria por buena una ejecucion fallida y por fallida una correcta.
- **Veredicto:** **Hueco real, riesgo ALTO.** Deuda de test anotada contra F-005; NO se parchea aqui: los tests de F-005 son el objeto de esta medicion.

### 55. `main.py:389` [entero]

- Original: `sys.exit(1)`
- Mutado:   `sys.exit(2)`

#### Análisis

- **Por qué ningún test lo caza:** El codigo de salida concreto ante fallo no lo comprueba ningun test; si que se comprueba que sale distinto de cero en otros comandos.
- **Veredicto:** **Hueco real, riesgo MEDIO.** Deuda de test anotada contra F-005; NO se parchea aqui.

