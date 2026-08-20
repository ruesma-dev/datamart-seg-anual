<!-- progress/impl_F-011.md -->
# F-011 · Carga incremental del datamart — Informe de implementación

> **Rama**: `feature/F-011-carga-incremental` · **Rigor**: `critico` ·
> **Fecha**: 2026-08-19 (noche) → 2026-08-20.
> **Qué se entrega**: el **bloque A completo** (T1–T6, T21, T22, T23) y **la
> parada de T9**.
> **Qué NO se entrega, a propósito**: el bloque B (ingesta incremental),
> porque la medición dice que no procede.
> **Leer antes que esto**: `progress/medicion_F-011.md`, que es la puerta de R8
> y trae los números con los que se decide.

## 1 · Lo que hay que saber en treinta segundos

- **La feature ha hecho el trabajo que pedía: medir.** El resultado es un
  **NO medido**, no un no por cansancio.
- **Hallazgo que cambia la feature**: `tiemod`, la columna sobre la que se
  apoyaba todo el bloque B, **no existe en 24 de las 31 tablas que ingerimos**,
  y entre ellas están las cuatro que se llevan el 86 % del tiempo de ingesta.
  `obrparpre` (13,8 M filas, 61 % del tiempo) tiene 22 columnas y **ninguna es
  una marca de modificación**. Comprobado en el catálogo de Sigrid, con dos
  consultas de lectura.
- **Los dos números de la puerta de DA-7**: ahorro máximo **2,25 min** (umbral
  20 min) y peso de la ingesta **19,9 %** (umbral 40 %). No se cumple ninguno,
  y no por poco.
- **Dónde está el tiempo de verdad**: `build_stg`, **110,7 min de 165,2
  (67,0 %)**, medido en tres cargas completas. Eso es **F-025**.
- **Se entregan tres comandos de solo lectura** —`perfil-carga`,
  `diagnostico-tiemod`, `bench-sigrid`— que dejan esta medición **repetible**,
  en vez de ser la cuenta a mano de una sesión.

## 2 · Ficheros tocados

### Nuevos

| Fichero | Qué es | Capa |
|---|---|---|
| `etl_sigrid/domain/perfil_carga.py` | `FilaPerfil`, `PerfilCarga`, `perfil_de_carga`, `techo_de_mejora`, `tablas_que_acumulan`, `format_perfil` (R1–R3) | domain |
| `etl_sigrid/domain/extraccion.py` | `MedicionPagina`, `resumen_bench`, `es_sentencia_de_lectura`, `comparar_cap`, `format_bench` (R4, R5, R5-bis, R23) | domain |
| `etl_sigrid/domain/tiemod.py` | `EstadoTiemod`, `Veredicto`, `veredicto_tiemod`, `comparar_tiemod`, formatos y el CSV de la huella (R6, R7) | domain |
| `etl_sigrid/infrastructure/sigrid/bench_extraccion.py` | El banco: construye la consulta, cronometra, captura el rechazo de la API | infrastructure |
| `tests/test_f011_{perfil,bench,tiemod,cli,alcance}.py` | **175 tests**, ninguno abre red ni BBDD | tests |
| `progress/medicion_F-011.md` | **T8**: la medición y la recomendación firmada | progress |
| `progress/mutacion_F-011.md` | La campaña de mutación (T22) | progress |

### Modificados

| Fichero | Qué cambia |
|---|---|
| `main.py` | Los tres comandos nuevos de solo lectura y su bloque en el docstring de la CLI. Ninguno llama a `_arrancar_ejecucion()` (R25) |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `fetch_perfil_carga`, `fetch_diagnostico_tiemod`, `fetch_filas_desde_tiemod`, el helper `_float_o_none` y cuatro constantes de SQL. Todo `SELECT` |
| `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py` | `leer_sql()` —la puerta pública que valida antes de enviar—, `SigridApiSentenciaNoDeLecturaError` y `LONGITUD_SQL_EN_ERROR` |

### Lo que NO se ha tocado, con test que lo fija (R22)

`sql/stg/*`, `sql/mart/*`, `domain/tramos.py`, `build_stg_step.py`,
`domain/coherencia.py`, `config/business_rules.yaml`,
`config/tables_sigrid.yaml`, `_meta.v_frescura`, `azure-apps/*`,
`harness/features.json`.

## 3 · Decisiones de diseño, y cuatro desviaciones del diseño aprobado

1. **`fetch_perfil_carga` devuelve `(batch medido, filas)`** y no solo las
   filas, como apuntaba `design.md` §5. Motivo: **R8 exige que el informe diga
   de qué carga salen los números**; sin el batch de vuelta, el comando no
   puede imprimir cuál midió.
2. **`SigridApiClient` gana `leer_sql()`**, que el diseño no listaba en el
   bloque A. Motivo: R23 obliga a que **todo** el SQL que sale hacia
   `/api/sql/read` pase por el validador. Sin una puerta pública, el banco
   tendría que llamar al `_post_sql` privado y el validador sería decorativo.
   Hay un test que lo comprueba **sobre el cliente real**, con control negativo.
3. **`veredicto_tiemod` acepta un tercer dato opcional, `filas_avanzadas`**, y
   el comando lo mide con un `COUNT(*)` por tabla por encima del máximo de la
   fotografía anterior. Motivo: R7 pide «cuántas filas cambiaron» y con dos
   agregados no se puede saber. Si `tiemod` es una marca de modificación, toda
   fila tocada está por encima del máximo anterior; si no lo es, el recuento
   sale 0, que es justo la señal de `NO SIRVE`.
4. **El CSV de la huella vive en el dominio**, junto a la clase que serializa,
   como `Metrica`/`escribir_csv` en `fingerprint.py`. El formato de la huella
   es parte de R7 («la salida de una ejecución anterior»), no un detalle del
   adaptador. Solo stdlib.

Y tres criterios que conviene no perder:

- **`NO SIRVE` y `SIN EVIDENCIA` se distinguen con cuidado.** Dar por mala una
  columna porque esa noche nadie tocó la tabla mandaría a la basura la única
  marca que Sigrid tiene. Cuando hay recuento, se exige además que las dos
  señales coincidan: un máximo que crece con cero filas por encima es una
  contradicción, y ante una contradicción no se da la columna por buena.
- **El validador de R23 es deliberadamente estrecho**: tiene que empezar por
  `SELECT`, no puede llevar una segunda sentencia tras `;` y no puede contener
  ninguna palabra de escritura, **`INTO` incluida** —en SQL Server
  `SELECT … INTO otra FROM t` **crea una tabla**—. Un `WITH … SELECT` se
  rechaza aunque sea una lectura legítima: mejor ampliarlo a propósito el día
  que haga falta que dejarlo ancho por si acaso.
- **El banco mide la MISMA consulta que usa la ingesta** (keyset por `ide`,
  `TOP n`, columnas menos las excluidas del YAML) y sus repeticiones **avanzan
  el cursor**. Repetir la misma página mediría la caché del SQL Server y el
  número saldría bonito y falso.

## 4 · Fase RED (obligatoria en `critico`)

Trazas reales, con el comando exacto. En los cinco módulos nuevos el test se
escribió y se ejecutó **antes** de que existiera el código.

**T1** · `python -m pytest tests/test_f011_perfil.py -q`

```
tests\test_f011_perfil.py:20: in <module>
    from etl_sigrid.domain.perfil_carga import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.perfil_carga'
1 error in 0.25s
```

**T2** · `python -m pytest tests/test_f011_cli.py -q`

```
E       AssertionError: Usage: cli [OPTIONS] COMMAND [ARGS]...
E         Error: No such command 'perfil-carga'.
E       assert 2 == 0
...
E       ImportError: cannot import name 'SQL_PERFIL_CARGA' from
        'etl_sigrid.infrastructure.postgres.postgres_client'
7 failed in 1.14s
```

**T3** · `python -m pytest tests/test_f011_bench.py -q`

```
tests\test_f011_bench.py:18: in <module>
    from etl_sigrid.domain.extraccion import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.extraccion'
1 error in 0.24s
```

**T4** · `python -m pytest tests/test_f011_bench.py -q`

```
tests\test_f011_bench.py:27: in <module>
    from etl_sigrid.infrastructure.sigrid.bench_extraccion import (
E   ModuleNotFoundError: No module named 'etl_sigrid.infrastructure.sigrid.bench_extraccion'
1 error in 0.35s
```

**T5** · `python -m pytest tests/test_f011_tiemod.py -q`

```
tests\test_f011_tiemod.py:20: in <module>
    from etl_sigrid.domain.tiemod import (
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.tiemod'
1 error in 0.29s
```

**T21** · `python -m pytest tests/test_f011_alcance.py -q` — esta fase RED
encontró algo de verdad, no solo un módulo que faltaba:

```
E  AssertionError: etl_sigrid/infrastructure/sigrid/bench_extraccion.py parece
   contener un secreto: ['SigridApiPageSizeTooLargeError',
   'SigridApiPageSizeTooLargeError', 'SigridApiPageSizeTooLargeError']
1 failed, 6 passed in 2.11s
```

El barrido de secretos de F-005 confunde un identificador de 30 letras con una
clave base64. Es el **tercer** falso positivo de la misma familia (F-004 dio el
de las rutas, que arregló F-016). Se afinó **en el test de F-011**, no en el de
F-005, y con control negativo: sin él, el filtro se ensancharía solo hasta
dejar de cazar nada.

## 5 · Qué se verificó, y con qué resultado real

| Qué | Cómo | Resultado real |
|---|---|---|
| Los tres comandos no escriben en `_meta` (R25) | test parametrizado sobre la lista, con un doble de cliente que **revienta** ante cualquier escritura | verde: los tres pasan sin llamar a ningún método de escritura, y `_arrancar_ejecucion` no se llama |
| `perfil-carga` contra Azure | **ejecutado de verdad** desde el puesto | **salida 2** y el mensaje de «no se pudo leer»: la IP del puesto ha rotado y ninguna regla de firewall la cubre. El camino de error queda probado en real; el de éxito, MANUAL (§6) |
| Dónde se va el tiempo (R1, R2) | logs del job en Log Analytics, **tres cargas completas** | ingesta 32,9 min · `build_stg` 110,7 · `build_mart` 21,6 · **total 165,2** |
| Qué tablas cuestan (R3) | los mismos logs | **3 tablas = 79,7 %** de la ingesta; 4 llegan al 86 % |
| ¿Sirve `tiemod`? (R6, R7) | catálogo de Sigrid, en solo lectura | **24 de 31 tablas NO tienen la columna**. Donde existe (`con`), es una marca completa de fecha y hora y está mantenida |
| `bench-sigrid` (R4, R5, R5-bis) | — | **no ejecutado**: va contra producción de Sigrid y la spec lo reserva al humano (T7) |
| Alcance (R22) | `git diff dev...HEAD` dentro de un test | ni una línea de `sql/stg`, `sql/mart`, `tramos.py`, `build_stg_step.py` ni `coherencia.py` |
| Secretos (R24) | barrido de F-016 sobre lo nuevo | limpio, con dos afinados propios y su control negativo |
| Suite completa (T23) | `bash harness/init.sh` | **798 tests en verde**, cobertura 100 % de las 469 líneas cambiadas |

### Lo que se leyó de Sigrid, exactamente

Cuatro consultas, todas de lectura y todas acotadas:

1. `SELECT TOP 5 [ide], [tiemod] FROM [dbo].[obr] ORDER BY [ide] DESC`, que
   devolvió el error que abrió el hallazgo (`El nombre de columna 'tiemod' no
   es válido`).
2. Una consulta a `INFORMATION_SCHEMA.COLUMNS` por las 31 tablas declaradas.
3. `SELECT TOP 5` sobre `con` y sobre `auxobrtip`, para ver los valores.
4. Los esquemas de cinco tablas (`fetch_table_schema`), que es exactamente lo
   que la ingesta pide cada noche antes de cada tabla.

**Ni una escritura, ni una carga, ni un barrido.** El `bench-sigrid`, que sí
lanza peticiones sostenidas, no se ha ejecutado.

## 6 · Verificaciones MANUAL pendientes (todas del humano)

Detalle y comandos en `progress/medicion_F-011.md` §7. En corto:

1. **`perfil-carga` contra Azure.** Necesita una regla de firewall para la IP
   del puesto: es una **escritura sobre un recurso compartido** con
   `albaranes` y `partes`, y la decide el humano.
2. **`diagnostico-tiemod --out`.** Confirmaría desde el datamart lo que el
   catálogo ya dijo. **Ojo al coste**: recorre las tablas de `raw` enteras
   (20 M filas) con un `COUNT(DISTINCT)`. Lanzarlo fuera de la ventana de carga.
3. **`bench-sigrid`** (R4 y R5-bis siguen sin acreditar).
4. **T8-bis**: avisar al dueño de `sigrid-api` de que su documento sigue
   diciendo 1.000 filas y 120 s. **Este proyecto no lo edita**, y no lo ha
   hecho: `git -C ../azure-apps status --porcelain` está limpio.
5. **T9 · la PARADA**: firmar el SÍ o el NO sobre `progress/medicion_F-011.md`.

## 7 · Lo que queda fuera del alcance

- **Todo el bloque B (R9–R19).** T9 es una parada y la recomendación es NO. Si
  el humano decidiera seguir, **hay que volver a la spec antes de escribir
  código**: R11, R12, R12-bis, R15, R17 y R19 están escritos sobre un watermark
  que no existe.
- **La ventana de negocio (R22)**: es F-025 y depende de DA-1, sin decidir.
- **Corregir `config/tables_sigrid.yaml`**, que declara `incremental_column:
  tiemod` en 17 tablas que no la tienen. Propuesto en `medicion_F-011.md` §8;
  **no hecho**, porque toca la configuración de la ingesta y la feature está en
  su parada.
- **`azure-apps/sigrid_api.md`**: no se toca; su dueño es `sigrid-api`.

## 8 · Evidencias

| Evidencia | Valor | De dónde sale |
|---|---|---|
| **Tests ejecutados y resultado** | **798 pasan, 0 fallan** (175 nuevos de F-011) | `bash harness/init.sh` |
| **Cobertura de las líneas cambiadas** | **100,0 % de 469** (469/469, umbral 80 %) | línea `PUERTA COBERTURA` de `init.sh` |
| **Mutantes generados / muertos / supervivientes** | **189 / 189 / 0** | `python -m harness.mutacion --feature F-011 --workers 1` → `progress/mutacion_F-011.md` |
| **Tiempo de ejecución de la suite** | **8,2 s** (10,2 s bajo `coverage`) | salida de pytest |
| **Tiempo de la campaña de mutación** | 808,4 s (la última de cuatro) | informe de mutación |

### 8.1 · Por qué este cero de supervivientes SÍ es creíble

La ficha **F-029** avisa de que la campaña de mutación no es de fiar y de que
**hay que repetir toda campaña que declare cero**. Aquí el cero no aparece de
golpe: es el final de **cuatro campañas en serie** (`--workers 1`, nunca en
paralelo), y cada bajada corresponde exactamente a los tests que se añadieron
en medio.

| Campaña | Generados | Muertos | Supervivientes | Qué cambió antes |
|---|---|---|---|---|
| 1ª | 192 | 122 | **70** | — |
| 2ª | 194 | 174 | **20** | tests de bordes: el valor 1 donde el código compara con 0, inmutabilidad, opciones de `click` |
| 3ª | 189 | 187 | **2** | porcentajes comprobados por posición, `slots`, mensajes de `click`, páginas completas en el doble |
| 4ª | 189 | **189** | **0** | los dos últimos, de formato: decimales del log y truncado del SQL |

Esa correspondencia entre «qué test añadí» y «qué mutante murió» es la
comprobación cruzada que F-029 echa en falta en un cero suelto. Además:

- **El árbol quedó limpio tras cada campaña** (`git status --porcelain` sin
  ficheros de producción modificados, `git worktree list` con una sola entrada).
- **Se observó en vivo el defecto (3) de F-029**: un `bash harness/init.sh`
  lanzado justo cuando la cuarta campaña terminaba salió **en rojo con 1 test
  fallando y solo 631 recogidos**; repetido con el árbol ya quieto, **798 en
  verde**. Es exactamente el falso negativo que describe la ficha. Queda aquí
  como evidencia observada, no como sospecha.

### 8.2 · Lo que costó de verdad la mutación

Los 70 supervivientes de la primera campaña **no eran mutantes equivalentes**:
eran huecos reales. Los tres patrones que más se repitieron, por si sirven en
la próxima feature:

1. **`in` sobre texto formateado miente.** `assert "100.0" in linea` pasa
   igual con `-100.0`, y `assert "1 tabla" in texto` pasa con `1 tablas`. Los
   asserts sobre tablas de consola hay que hacerlos **por posición de columna**.
2. **Los bordes se prueban con el valor del borde.** Media docena de mutantes
   `<= 0` → `<= 1` sobrevivieron porque ningún test usaba exactamente 1 s, 1
   fila o 1 petición.
3. **Un doble demasiado cómodo esconde el código.** El doble de la API
   devolvía páginas cortas, así que el bucle de repeticiones **nunca se
   ejecutaba dos veces** y el valor por defecto daba igual.

Y dos mutantes señalaron **código que sobraba**, no tests que faltaban:
`filas_por_segundo` comprobaba `filas <= 0` cuando la división ya da 0,0 sola,
y el mapeo del diagnóstico repetía `fila[N] is None` de forma que confundir dos
índices no lo detectaba ningún dato posible (MIN y MAX son nulos a la vez). Los
dos se simplificaron.

## 9 · Commits de la feature

```
c0f7a81 F-011 T1: perfil de carga en el dominio (R1, R2, R3)
d06095e F-011 T2: fetch_perfil_carga y el comando perfil-carga (R1, R23, R25)
5fa10da F-011 T3: dominio del banco de extraccion (R4, R5, R5-bis, R23)
211df06 F-011 T2 (cierre): test del mapeo de fetch_perfil_carga sin BBDD
a3450a0 F-011 T4: banco de extraccion y comando bench-sigrid (R4, R5, R5-bis, R23)
4412654 F-011 T4 (cierre): tests de los dos bordes que faltaban por cubrir
f75643c F-011 T4 (cierre): control negativo de la puerta leer_sql
fb6bcb5 F-011 T5: dominio del diagnostico de tiemod (R6, R7)
655ceeb F-011 T6: fetch_diagnostico_tiemod y el comando diagnostico-tiemod (R6, R7, R25)
eb4a99f F-011 T6 (cierre): delta de filas de una tabla nueva y fuera una rama muerta
26254f1 F-011 T21: test de alcance (R22) y barrido de secretos (R24)
67ccaba F-011 T8: informe de medicion con la puerta de DA-7 y la recomendacion firmada
7edd058 F-011 T22: tests que matan a los supervivientes de la primera campana
871c1c1 F-011 T22 (2a vuelta): de 70 supervivientes a 20, y de 20 a los que quedan
f4f5cbf F-011 T22 (3a vuelta): los dos supervivientes cosmeticos, muertos tambien
```

Ni `git push` ni PR: todo commits locales en la rama de la feature, como manda
el protocolo.

> **Aviso para el reviewer**: entre los commits de F-011 hay uno que **no es de
> esta feature**, `bcb2fd6` («F-034 y D10: Power BI pasa a leer de Azure»),
> hecho a las 00:02 del 2026-08-20 desde otra sesión que trabajaba en paralelo
> sobre esta misma rama. Toca **solo** `BACKLOG.md`, `harness/features.json` y
> `progress/decisiones_abiertas.md`: ni una línea de código ni de tests, así
> que no afecta a la medición, a la cobertura ni a la campaña de mutación de
> F-011. Se deja constancia para que no parezca un cambio de alcance.
