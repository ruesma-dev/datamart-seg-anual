<!-- progress/mutacion_F-080.md -->
# F-080 · Campaña de mutación

Generado por `python -m harness.mutacion --feature F-080` el 2026-09-14 21:17.

## Alcance

Origen del diff: **rama** (`cd18e0962b63edcc0017907b8c69a29352e433c4` .. `feature/F-080-vencimientos-forma-pago-y-texto-factura`).

| Fichero | Líneas en alcance |
|---|---|
| `config/settings.py` | 108 |
| `etl_sigrid/application/steps/apply_grants_step.py` | 18 |
| `etl_sigrid/application/steps/build_compras_step.py` | 42 |
| `etl_sigrid/application/steps/build_maestros_step.py` | 76 |
| `etl_sigrid/application/steps/build_stg_step.py` | 613 |
| `etl_sigrid/application/steps/ingest_raw_step.py` | 70 |
| `etl_sigrid/domain/cobertura.py` | 35 |
| `etl_sigrid/domain/huella_ampliada.py` | 20 |
| `etl_sigrid/domain/recuentos.py` | 286 |
| `etl_sigrid/domain/texto_comentarios.py` | 141 |
| `etl_sigrid/domain/tramos.py` | 4 |
| `etl_sigrid/domain/ventana.py` | 784 |
| `etl_sigrid/infrastructure/postgres/grants.py` | 101 |
| `etl_sigrid/infrastructure/postgres/huella_ampliada.py` | 33 |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | 723 |
| `etl_sigrid/infrastructure/postgres/ventana_sql.py` | 246 |
| `main.py` | 489 |
| **Total** | **3789** |

## Totales

| Métrica | Valor |
|---|---|
| Mutantes generados | 303 |
| Mutantes evaluados | 20 |
| Muertos | 14 |
| Supervivientes | 6 |
| Timeouts | 0 |
| Sin veredicto (base rota) | 0 |
| Tiempo total | 2920.3 s |
| SHA de HEAD medido | `eb78eb0254f9ed897aa932f411b885cd339f921f` |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_jonmptsd/wk_0` | 464.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_jonmptsd/wk_1` | 469.8 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_jonmptsd/wk_2` | 473.1 |
| Línea base (s) — `C:/Users/pgris/AppData/Local/Temp/mutacion_F-080_jonmptsd/wk_3` | 466.7 |
| Media por mutante evaluado (s) | 146.0 |
| Timeout efectivo por mutante (s) | 947 — derivado de la línea base × 2.0 |
| Suelo configurado (s) | 120 |
| Workers | 4 |
| Muestreo | sí — 20 de 303 mutantes, semilla `20260820`, nivel `estandar` |

## Supervivientes

Cada superviviente es una línea que ningún test comprueba de verdad, o una mutación equivalente. Distinguirlo es trabajo del implementer: ningún análisis puede quedarse sin completar al cerrar la feature.

> **LEER ESTO ANTES QUE LOS SEIS ANÁLISIS.** El alcance de esta campaña son
> **3.789 líneas**, y de F-080 solo hay **141**: las de
> `etl_sigrid/domain/texto_comentarios.py`. El resto entra porque el alcance se
> calcula contra `dev`, que lleva 242 commits de retraso, así que arrastra
> features ya cerradas —F-025 sobre todo—. Cálculo puro sobre los 303 mutantes
> generados: **15 caen en `texto_comentarios.py` (4,95 %)** y **0 en
> `build_compras_step.py`**; el muestreo de 20 con semilla `20260820` no cogió
> **ninguno** de esos 15 (la esperanza era 0,99). Por eso los seis
> supervivientes de abajo son de OTRAS features, y por eso F-080 lanza además
> una **segunda campaña dirigida a sus dos módulos**, sin muestreo, cuyo
> informe es `progress/mutacion_F-080_modulos.md`. Esta de aquí no dice nada
> sobre el código que F-080 escribió, y decirlo es parte de la evidencia.

### 1. `etl_sigrid/infrastructure/postgres/postgres_client.py:1527` [entero]

- Original: `estado_id=int(fila[2]) if fila[2] is not None else None,`
- Mutado:   `estado_id=int(fila[3]) if fila[2] is not None else None,`

#### Análisis

> **Por qué ningún test lo caza**: la línea está en `fetch_censo_de_obras`,
> que ejecuta `SQL_ESTADO_OBRAS` contra el Postgres real y arma `ObraCensada`
> con la fila del cursor. Por convención del proyecto (`docs/CONVENTIONS.md`)
> los unit tests **no tocan BBDD**, así que ninguno puede fabricar esa fila:
> los de F-025 construyen `ObraCensada` a mano. Con datos reales el mutante
> moriría en cuanto `fila[3]` —una marca de tiempo— no fuera casteable a
> `int`.
> **Decisión**: hueco real pero **inalcanzable desde la suite offline**, y de
> **F-025**, no de F-080. Lo cubre la verificación MANUAL contra la base
> (`python main.py huella-obras`). No se tapa aquí: F-080 no toca ese fichero.

### 2. `etl_sigrid/infrastructure/postgres/postgres_client.py:1528` [entero]

- Original: `ultima_actividad=fila[3],`
- Mutado:   `ultima_actividad=fila[4],`

#### Análisis

> **Por qué ningún test lo caza**: mismo método y mismo motivo que el 1 —dos
> líneas más abajo—. `ultima_actividad` pasaría a traer `fila[4]`, que es el
> `tiene_filas` de la tabla siguiente, y la ventana decidiría con una fecha
> que no es una fecha. Solo se ejecuta con cursor real.
> **Decisión**: hueco real, inalcanzable offline, de **F-025**. No se tapa
> aquí.

### 3. `etl_sigrid/infrastructure/postgres/postgres_client.py:1551` [entero]

- Original: `int(fila[0]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))`
- Mutado:   `int(fila[1]): dict(zip(COLUMNAS_FIRMA_ORIGEN, fila[1:], strict=True))`

#### Análisis

> **Por qué ningún test lo caza**: `fetch_firma_origen` lee `SQL_FIRMA_ORIGEN`
> del cursor. Con datos reales el mutante moriría **de inmediato**: la clave
> del diccionario pasaría a ser la primera columna de la firma en vez del
> `obra_id`, y las firmas se atribuirían a obras que no son. Sobrevive solo
> porque el método no se ejecuta en la suite.
> **Decisión**: hueco real, inalcanzable offline, de **F-025**. Es la misma
> línea que ya analizó `progress/mutacion_F-073.md` (superviviente 4, con otro
> operador): sigue sin taparse porque sigue sin ser de la feature en curso.

### 4. `etl_sigrid/infrastructure/postgres/postgres_client.py:1643` [not]

- Original: `if not registros:`
- Mutado:   `if registros:`

#### Análisis

> **Por qué ningún test lo caza**: `registrar_obras_construidas` abre conexión.
> Invertir la guarda hace que una lista NO vacía salga con 0 sin registrar
> nada —y una vacía intente conectarse—, que es un defecto serio; pero el
> método no se ejecuta en la suite offline.
> **Decisión**: hueco real, inalcanzable offline, de **F-025**. Idéntico al
> superviviente 7 de `progress/mutacion_F-073.md`: dos campañas seguidas lo
> señalan, y sigue siendo deuda de F-025, no de F-080.

### 5. `etl_sigrid/infrastructure/postgres/ventana_sql.py:244` [comparacion]

- Original: `if valor is None:`
- Mutado:   `if valor is not None:`

#### Análisis

> **Por qué ningún test lo caza**: `_fecha(valor)` traduce una marca de tiempo
> a texto y devuelve `"nunca"` cuando no hay ninguna. Invertida, devuelve
> `"nunca"` para las fechas informadas y el `str(valor)[:19]` de `None` —es
> decir, `"None"`— cuando no la hay. Solo se ve en el **detalle** de un
> hallazgo de ventana, y los tests de `ventana_sql` comprueban el TIPO y el
> recuento de hallazgos, no el texto del detalle.
> **Decisión**: hueco real y **barato de tapar con un assert sobre el
> detalle**, pero es código de **F-025**. Queda anotado, no se toca aquí: es
> el mismo hallazgo que el superviviente 8 de `progress/mutacion_F-073.md`,
> otra línea del mismo fichero y de la misma familia.

### 6. `main.py:1607` [entero]

- Original: `veredicto = _veredicto_de_ventana(pg, settings, sello, 120)`
- Mutado:   `veredicto = _veredicto_de_ventana(pg, settings, sello, 121)`

#### Análisis

> **Por qué ningún test lo caza**: ese `120` **no es un umbral de negocio, es
> un timeout en segundos** para las cuatro lecturas de
> `_veredicto_de_ventana`. Ningún test puede distinguir 120 de 121 segundos
> sin dejar que las lecturas caduquen de verdad, y el propio parámetro existe
> para no colgar la nocturna, no para decidir nada.
> **Decisión**: **mutante equivalente**, justificado por escrito (rigor
> `estandar`, RM5 no aplica). No hay test que escribir: un assert sobre el
> literal comprobaría que el número es el que es, no que haga algo.
