<!-- progress/impl_F-097.md -->
# F-097 · Informe del implementer

Rama `feature/F-097-descompuestos-partidas`. Rigor `estandar`. Spec
`specs/F-097-descompuestos-partidas/`, aprobada por el humano el 2026-09-27;
PARADA 1 confirmada el 2026-09-28 con el cambio de orden (T0 bloquea la puesta
en producción, no el código). Alcance de esta sesión: T1-T16 y T20.

## T1 · Decisiones D12-D15

Comprobado en `progress/current.md` (sección de F-097) y en
`progress/spec_F-097.md` («APROBADA POR EL HUMANO (2026-09-27)»): D12, D13, D14
y D15 aprobadas **según la recomendación** («ok» del humano); D14 fichada como
F-115. Ninguna se aparta de la recomendación: no hay nada que devolver a la
spec. Siguen abiertas con Negocio, sin bloquear: D8 (tipos 3 y 11, se publican
con la traducción del diseño y la ficha lo dice provisional) y D11 (D05DF210).

## T2 · Fase RED (trazas reales, 2026-09-28)

Cuatro ficheros de test escritos ANTES que el código: `test_f097_planificador.py`
(dominio: plan de relectura, plan de troceado y el espejo en Python del
troceado), `test_f097_ingesta_descompuestos.py` (paso de ingesta con dobles de
Sigrid y Postgres, y `reemplazar_filas` contra un doble de la conexión),
`test_f097_descompuestos.py` (SQL, paso de build, cableado, diccionario,
documentación) y `test_f097_tiemod_obrparpre.py` (R29).

Comando: `python -m pytest tests/test_f097_planificador.py tests/test_f097_ingesta_descompuestos.py tests/test_f097_descompuestos.py tests/test_f097_tiemod_obrparpre.py -q -p no:cacheprovider`

```
E   ModuleNotFoundError: No module named 'etl_sigrid.domain.descompuestos'
ERROR tests/test_f097_planificador.py
ERROR tests/test_f097_descompuestos.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
```

Los otros dos ficheros, sueltos (`... test_f097_ingesta_descompuestos.py test_f097_tiemod_obrparpre.py -q`):
`34 failed, 2 passed in 2.49s` (los 2 que pasan fijan lo que NO debe cambiar:
la ingesta sigue en 71 tablas y la entrada `obrparpre` conserva sus demás campos).
Tres requisitos centrales, con `--tb=short`:

```
test_f097_r9_recuento_distinto_se_revierte_y_sigue
E   ImportError: cannot import name 'ingest_descompuestos_step' from 'etl_sigrid.application.steps'
test_f097_r8_reemplazar_filas_borra_copia_y_controla_en_una_transaccion
E   ImportError: cannot import name 'FilaControl' from 'etl_sigrid.infrastructure.postgres.postgres_client'
test_f097_r29_obrparpre_no_declara_tiemod
E   AssertionError: obrparpre no tiene tiemod en Sigrid (22 columnas, medido el 2026-09-27)
    assert 'tiemod' is None
```

## T3-T14 · Qué se hizo (un commit por tarea: `git log --oneline main..HEAD`)

| Tarea | Ficheros | Qué |
|---|---|---|
| T3 | `config/tables_sigrid.yaml` | `obrparpre`: `incremental_column: null` con lo medido (R29) |
| T4 | `etl_sigrid/domain/descompuestos.py` | `planificar_relectura` (R5-R7), `planificar_troceado` (R21), `trocear_des` (espejo del SQL, R13/R14/R19), `cod_version_vigente` |
| T5 | `postgres_client.py` | `reemplazar_filas` + `FilaControl`: `DELETE` + `COPY` + UPSERT/DELETE del control en UNA transacción (R8) |
| T6 | `sql/descompuestos/00_setup.sql` | esquema, `_des_texto`, `_versiones_cargadas` (sin `DROP`), `fn_num`, `fn_fecha` |
| T7 | `steps/ingest_descompuestos_step.py` | huella en una consulta, ámbito 3 entero, plan, versión a versión con recuento contra la huella (R2-R4, R8-R11) |
| T8 | `01_troceado.sql`, `02_lineas_coste.sql` | `fn_trocear` (una definición); `lineas` y `cuadre_partida` (DDL); ESTUDIO y PLANIF_JO |
| T9 | `03_lineas_master.sql` | lote por marcador, origen y flags, cuadre del lote, borrado de lo que ya no está, sincronización barata de flags, sello |
| T10 | `04_elementos.sql`, `05_cuadre.sql`, `06_views.sql` | catálogo con producto (dos vías), cuadre del ámbito 3, tres vistas |
| T11 | `steps/build_descompuestos_step.py`, `main.py` | paso por lotes; `ingest-descompuestos` y `build-descompuestos` con `--sin-tope`; los dos pasos tras `build_contabilidad` |
| T12 | `settings.py`, `diccionario.py`, `.env.example`, `infra/sql/02_roles.sql`, 9 tests | `DescompuestosSettings` (300, > 0); doce esquemas; listas cerradas |
| T13 | `config/diccionario/*`, design de F-006, `current.md` | 11 fichas, `R-DESCOMPUESTO-ORIGEN`, `R-FRESCURA` a siete, `R-SIGRID-CON` punto 3, version 37; 187 objetos / 1401 columnas / 85 de consumo |
| T14 | `docs/ARCHITECTURE.md`, `CLAUDE.md`, `azure-apps` (85356e6) | pestañas, formato, incremental, primera carga, corrupción, `tiemod` |

Además `progress/mediciones/F-097_comparar_huellas.py`: el procedimiento de T0
hecho comando (solo lectura), para que el humano no tenga que componerlo.

## Desviaciones respecto a la spec (justificadas; las juzga el reviewer)

1. **La clave de `descompuestos.lineas` lleva `obra_id`** (R20 dice origen,
   partida, ámbito, fase, orden). Medido en solo lectura el 2026-09-28: las 227
   filas con `obride = 0` de la versión 26 del master repiten partida con OTRA
   obra, las 227 (`SELECT ... WHERE p.obride = 0`: 227 filas, 227 choques). Con
   la clave de la spec el build fallaría al cargarlas; la spec pide conservarlas
   en el troceado. `cuadre_partida` mantiene la clave de la spec (deja fuera
   `obride = 0`, como pide).
2. **`_versiones_cargadas` gana `atributos_troceado`** (md5 del origen y los
   flags que llevan sus líneas). Es lo que hace «barato» el UPDATE de flags del
   design: sin ella había que recorrer ~4,5 M líneas cada noche.
3. **El cuadre del master lo escribe `03`**, en la misma transacción que las
   líneas del lote (R8: «sus líneas y su cuadre»); `05` hace solo el ámbito 3.
   El DDL de `cuadre_partida` va en `02` porque `03` lo escribe antes que `05`.
4. `reemplazar_filas(schema, tabla, filtro, columnas, filas, control)`: la firma
   del design no traía `columnas`, sin las que no hay `COPY`.
5. La ingesta NO lee de Sigrid la primera ABC (design, paso 1): no la usa; el
   origen lo decide el build desde `raw.obrfasamb` (R26). La vigente sí: la
   necesita el plan (Sigrid) y los flags (`raw.conext`).
6. Las tablas `_` llevan **ficha con `consumo_recomendado: false`**, no
   pendiente: el trinquete de `pendientes` está en 0 y solo baja.
7. `es_ultima` = la mayor versión del master de la obra entre `obrfasamb` y las
   cargadas; `precio_partida` = `pre` redondeado a 2 (como lo muestra Sigrid).
8. Tamaño de lote del build = 300 MB (`MB_POR_LOTE`, no fijado en el design): una
   noche normal es un lote; la primera carga, ~8. Un error de Sigrid al leer UNA
   versión se trata como R9 (se registra, se sigue, `FAILED` al final).
9. `PATRON_NUMERO`/`fn_num` acotan el exponente a 3 cifras (`1e9999` sería un
   literal de 10.000 cifras). **Eso NO bastaba** (review 1): un número válido que
   no cabe en las columnas `NUMERIC(18,2)` de los importes tumbaba el build; desde
   R1-1 un importe con |x| >= 1e16 tras redondear sale NULL en SQL y en el espejo.
10. `infra/sql/02_roles.sql` gana `descompuestos` en sus tres listas: lo exige el
    test cerrado de F-057 (reaprovisionamiento del servidor). No se ejecuta.
11. Erratas de mis propios tests corregidas en su tarea (T4, T7, T10), dichas
    en cada commit; ninguna cambia un requisito.

## Riesgos que quedan a la vista

- **Una sola versión que no cuadra salta el build esa noche** (R9 manda
  `FAILED`; R25, `build_descompuestos` depende de la ingesta). Queda lo de la
  noche anterior; `R-FRESCURA` lo avisa. Literal de la spec, no se ha tocado.
- **Primera noche desplegada sin primera carga y con la ingesta `FAILED`**:
  `check-declarados` sale 1 (las tablas del build no existen). T17 va antes.
- El cuadre de cada lote hace una lectura secuencial de `raw.obrparpre`
  (13,7 M filas, sin índice en `raw`): una por lote, ~1 por noche, ~8 en la
  primera carga. **Sin medir contra Azure** (T17/T18).

## Verificaciones hechas, con su resultado real (2026-09-28)

Además de la suite offline (Evidencias), tres contrastes que un test sin base no
puede dar. **Sigrid: solo `SELECT` por `leer_sql`. Escrituras: SOLO en un
PostgreSQL 16 local desechable** (`initdb` en el scratchpad, puerto 55433),
nunca en Azure: los scripts sustituyen `build_postgres_client` por un cliente
cableado a `localhost`.

1. **La consulta de huella del paso contra Sigrid**: 3.023 versiones, las 3.023
   iguales a la toma del 2026-09-27, 0 nuevas, 0 desaparecidas, 26,8 s; 2.043,2
   MiB de master. Lectura paginada de la 0726 v1: 1.305 filas = su huella.
2. **Espejo Python ↔ SQL** (`trocear_des` frente a `fn_trocear`): 0 diferencias
   en 2.700 filas reales de Sigrid (8.582 registros, 3.798 enlazados; ámbito 3 y
   dos versiones de la 0695) y en los 14 casos sintéticos de la suite.
3. **De extremo a extremo con los pasos reales**: `IngestDescompuestosStep`
   (tope 25 MB) leyó de Sigrid el ámbito 3 entero, **42.958 filas** (la cifra de
   la spec), y la vigente de una obra; aplazó 3.022 versiones (2.039,9 MB);
   SUCCESS en 78,9 s. `BuildDescompuestosStep` sobre ese texto y un `raw` de
   juguete: SUCCESS en 6,8 s; **ESTUDIO 97.915 líneas** (spec: ~98.000), **7.866
   partidas sustituidas** (spec: 7.866), tipos idénticos a los de la spec (MANO_OBRA
   29.339, MATERIAL 19.451, PORCENTAJE 4.007, OTROS 3.578, MAQUINARIA 3.400,
   MEDIOS_AUXILIARES 1.322, SUBCONTRATA 373), 0 DESCONOCIDO, y la **419079: 10
   líneas ESTUDIO que suman 134,35** (C1, parte ESTUDIO). El cuadre y PLANIF_JO
   sobre el `raw` de juguete: los siete escenarios de la tabla de estados (CUADRA,
   NO_CUADRA, SIN_DESCOMPUESTO, SUSTITUIDO, capítulo y precio 0 fuera).
4. El `03` con lote vacío tras mover la vigente, meter una ABC en la v0 y borrar
   una versión: flags y origen actualizados solo donde cambiaron, líneas y cuadre
   de la borrada fuera. Todos los ficheros, dos veces seguidas: idempotentes.

Lo que NO se ha podido verificar aquí: tiempos y espacio en Azure, el `raw` real
en el build (PLANIF_JO, cuadre, flags) y la noche siguiente. Es T17-T18.

## T16 · Campaña de mutación (`progress/mutacion_F-097.md`)

`python -m harness.mutacion --feature F-097 --base main --workers 2`, sobre el
SHA `c1bf0bf`: 175 mutantes generados en 1.321 líneas de producción, 20
evaluados (muestreo del nivel `estandar`, semilla 20260820), **16 muertos y 4
supervivientes**, 0 timeouts, 0 sin veredicto. Los cuatro eran huecos reales del
dominio (registros cortados justo en una posición, uno de exactamente 36 campos,
un lote de menos de 1 MB y el tope del troceado a 0): cuatro tests nuevos que,
reproducidos sobre una copia aislada, matan cada mutación (análisis en el
informe de mutación). Un primer intento con 4 workers se abortó solo: la línea
base no cabía en sus 600 s con cuatro suites compitiendo; con 2, 439 s.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests ejecutados (T15, `bash harness/init.sh`) | **5.914 passed, 219 skipped, 0 failed** |
| Tests de F-097 | **180 passed** en los cuatro `tests/test_f097_*.py` tras T16 (88 del dominio) |
| Cobertura de las líneas cambiadas | **99,2 %** (510 de 514; `PUERTA COBERTURA` de `init.sh`, umbral 80 %) |
| Mutantes | **Vigente (review 2, `6ca684d`)**: 178 generados, 20 evaluados, 18 muertos, 2 supervivientes con test nuevo. La de T16 (`c1bf0bf`, 16/20) caducó con la review 1 |
| Workers de la campaña | **2** (vigente: 3.945,6 s; media 197,3 s × 2 = 394,6 s por mutante, línea base 448,4 s) |
| Tiempo de la suite | 18 min 31 s con cobertura (1.111 s, `init.sh`) |
| `bash harness/init.sh` final (T20, sobre `46a8762`) | **ENTORNO LISTO, exit 0**: 5.922 passed, 219 skipped, 0 failed en 16 min 0 s; cobertura **99,6 %** (512/514); tamaño impl 170/220 |

## Qué queda fuera y qué falta para cerrar

Fuera de esta sesión (MANUAL del humano, con su comando en `progress/current.md`):
**T0** (segunda toma de huellas desde el 2026-10-05; bloquea la puesta en
producción), **T17** (primera carga), **T18** (C1-C4 y la noche siguiente) y
**T19** (puertas, `apply-grants`, `publicar-diccionario` v37, imagen nueva y la
lista blanca de `mcp-bbdd`). Abiertas con Negocio: D8 (tipos 3 y 11, publicados
como PROVISIONALES) y D11 (el código D05DF210). Sin push en ningún repositorio.

## Review 1 atendida (`progress/review_F-097.md`, CHANGES_REQUESTED)

**Fase RED** de los tests nuevos, antes del arreglo (`python -m pytest tests/test_f097_planificador.py tests/test_f097_descompuestos.py -q -k "fuera_de_rango or limite_del_importe or r19_importes_y or r19_planif or salto_de_linea"`):

```
FAILED test_f097_r14_importe_fuera_de_rango_es_null_sin_excepcion[1e300]   E decimal.InvalidOperation
FAILED test_f097_r14_importe_fuera_de_rango_es_null_sin_excepcion[12345678901234567]
       E assert (Decimal('12345678901234567.00') is None)
FAILED test_f097_r14_importe_fuera_de_rango_es_null_sin_excepcion[-99999999999999999]
FAILED test_f097_r14_el_limite_del_importe_es_1e16_tras_redondear  E assert Decimal('10000000000000000.00') is None
FAILED test_f097_r14_numero_seguido_de_salto_de_linea_es_null      E assert Decimal('12') is None
FAILED test_f097_r17_cod_de_la_vigente_con_salto_de_linea_se_rechaza  E Failed: DID NOT RAISE ValueError
FAILED test_f097_r19_importes_y_porcentajes / test_f097_r19_planif_jo_con_sus_importes (texto del SQL)
8 failed, 1 passed
```

| Cambio | Commit | Qué | Verificación real |
|---|---|---|---|
| 1 · rango | `057b8d1` R1-1 | `01_troceado.sql`: `CASE WHEN abs(ROUND(x, 2)) < 1e16 THEN ROUND(x, 2)::NUMERIC(18,2) END` en los dos importes; el mismo patrón en PLANIF_JO (`02`, misma clase de fallo con los `float` de `dncpro`); espejo con `LIMITE_IMPORTE` y sin `InvalidOperation`. `00_setup.sql` no cambia: `fn_num` sigue devolviendo el número (el precio se publica); lo que no cabe es el importe | PostgreSQL 16 local desechable: `1e300`, 17 cifras, `-99999999999999999`, `1e999` y `.995` que redondea a 1e16 -> importes NULL; 16 cifras + 2 decimales -> caben; SQL y espejo iguales en los 11 casos límite |
| 2 · `$` | `c2b1b53` R1-2 | `_NUMERO` y `_ENLACE` con `fullmatch`; también el cod de la vigente y el sello del build (misma trampa) | Los casos `12
` y enlace `55
`, iguales a SQL (NULL); 14 casos de la suite y 2.700 filas reales de Sigrid (solo lectura), 0 diferencias |
| 3 · título | R1-3 | Sección F-097 de `current.md`: «EN REVISIÓN», no «PARADA 1 pendiente» | Lectura |

Tests de F-097: **186 passed**. El hallazgo 3 (un error de Postgres al escribir
UNA versión aborta la ingesta en vez de registrarse y seguir, como R9) NO se
arregla aquí: **candidato a ficha menor** (hipotético: un `ide` que cambie de
versión chocaría con la PK de `_des_texto`). Los hallazgos 4-6 son INFO; el 6
es el cambio 3.

`bash harness/init.sh` tras la review 1 (sobre `e366d05`): **ENTORNO LISTO, exit 0**;
5.928 passed, 219 skipped, 0 failed (11 min 39 s); cobertura 99,6 % (516/518).

## Review 2 atendida (detalle en `progress/mutacion_F-097.md`)

R2-1 `afc6448`: informe de mutación = campaña del reviewer en `6ca684d` (el código del alcance no cambia desde entonces), con S1 y S2 analizados; R2-2 `323b3e5` y R2-3 `a110ce7`: tests de S1 (lote justo) y S2 (`sin_tope=False` sin la opción, `CliRunner`), que PASAN contra el código (cubren mutantes, no bugs) y FALLAN con cada mutante aplicado a mano en una copia (`assert [True, True] == [False, True]`, `assert (((1, 0),), ((1, 1),)) == ...`); R2-4 `7e4f426` (commit vacío: la nota vive en el informe de R2-1): el equivalente de `_redondeo`. Tests de F-097: 189 passed.
