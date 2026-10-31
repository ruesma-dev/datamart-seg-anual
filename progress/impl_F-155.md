<!-- progress/impl_F-155.md -->
# F-155 · Hotfix: ofertas compartidas entre comparativos rompen build_compras

Implementer, 2026-10-31. Rama `feature/F-155-ofertas-compartidas` desde `main` (`1d65ca1`).
`sdd=false`, rigor `estandar`. Commits `66a8dd9` (T1), `dc758b7` (T2), `5cb92c5` (T3),
`f1d7d06` (T4), `e51868d` (T5), `b1676db` (T6) y el de este informe. `azure-apps` `acb8a75` (local, sin push).

## 1. Qué pasó y causa (medido en Azure, SOLO LECTURA, `_bootstrap_done = True`)

La nocturna del 31-10 cayó dos veces en `build_compras` (`comparativo_ofertas_pkey`, `oferta_id`
2796053 duplicada). En Sigrid, el COM26/0014 (comide 2865169) reutiliza las 6 ofertas del
0697.0_0037 (comide 2793682). Medido:

| Medida | Valor |
|---|---|
| `raw.comprv`: filas / `ide` distintos / `docide` distintos / (`comide`,`docide`) distintos | 72.113 / **72.113** / 72.107 / 72.113 |
| Ofertas en dos comparativos | 6 (2795986, 2796015, 2796032, 2796039, 2796053, 2799121), invitaciones 77527-77717 en el 0037 y 80641-80646 en el COM26/0014 |
| Líneas de oferta (`dcopro`) de esas 6 | 6, todas a la `comlin` 240200 del **0037** |
| Líneas de oferta con el SQL viejo / únicas | **792.039 / 792.033**: 09 habría caído también (PK `linea_oferta_id`) |
| Adjuntos (`raw.rcg`) de las ofertas compartidas | **3** (293014, 293022, 293461): 14 habría caído también (PK `adjunto_id`) |
| Líneas de oferta cuya `comlin` no existe (comlinide > 0) | 329 (con el SQL viejo iban con su única invitación) |

`invitacion_id` (= `comprv.ide`) es único: la clave pedida vale; no hace falta la compuesta.

## 2. Qué cambió

| Fichero | Cambio |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/compras/08_comparativos.sql` | PK `invitacion_id`; índice nuevo por `oferta_id`. B (`importe_ofertado_lineas`, `n_lineas`) por INVITACIÓN: cada línea de oferta va a UNA invitación, la del comparativo de su `comlin` y, si ninguna casa, la primera (`comprv.ide` menor). Cabecera y comentario de la ganadora explicados |
| `.../compras/09_comparativos_detalle.sql` | `lineas_oferta`: `DISTINCT ON (lp.ide)` con la misma regla (contra `compras.comparativo_lineas`). `comparativo_objetivo`: `con_porcentaje` agrupa por (`comparativo_id`, `oferta_id`) y une por los dos |
| `.../compras/14_documento_adjuntos.sql` | La oferta toma el comparativo de su PRIMERA invitación (`DISTINCT ON (q.docide) ... ORDER BY q.docide, q.ide`): una fila por enlace |
| `config/diccionario/compras.yaml` | `comparativo_ofertas`: descripción, grano, `clave_negocio: [invitacion_id]`, `claves_alternativas: [[comparativo_id, oferta_id]]`, `oferta_id`/`invitacion_id` explicados. Cinco relaciones que prometían `oferta_id` única (`1:N`/`N:1`) pasan a `N:N` con el `porque` «une también por `comparativo_id`»; `oferta_ganadora_id` lo dice |
| `config/diccionario/00_global.yaml` | **versión 68** con su nota |
| `docs/ARCHITECTURE.md` | Viñeta F-155 en el bloque de F-038 |
| `tests/test_f155_ofertas_compartidas.py` (nuevo) | 8 estáticos + 5 de sandbox |
| `tests/test_f038_sql.py`, `test_f038_diccionario.py`, `test_f090_diccionario.py`, `test_f090_ingesta_sql.py` | Ajustados a la nueva verdad (PK, B por invitación, `DISTINCT ON`, objetivo, relaciones `N:N`, R13 de 14) |
| `tests/test_f108_claves_alternativas.py` | T6: la alternativa nueva en `DECLARADAS` (init.sh la cazó: 10 frente a 9) |
| `harness/features.json` | F-155 registrada |
| `progress/current.md` | Sección F-155 con el PASO MANUAL |
| `progress/mutacion_sql_F-155.py` (nuevo) | Mutación manual del SQL contra la sandbox |
| `azure-apps/datamart_seg_anual.md` | Grano de `comparativo_ofertas` y nota del contrato con `mcp-bbdd` |

**Consumidores revisados** (`grep oferta_id` y `comparativo_ofertas` en `sql/`, `config/diccionario`,
`tests/`, `etl_sigrid/`, `mcp-bbdd`, `azure-apps`): solo 08, 09 y 14 los leen en SQL; ninguna otra
capa (`mart`, `cierre`, `tesoreria`...). `compras.comparativos` agrega por `comparativo_id`, así que
su ganadora y sus recuentos ya iban por comparativo: con el grano nuevo, una oferta compartida da una
fila en cada uno y nunca dos en el mismo (sandbox). `grants.py`, `test_f079`, `test_f141` solo nombran
la tabla. `check-unicidad` toma la clave del diccionario: `--dry-run` ya genera las consultas por
`(invitacion_id)` y por `(comparativo_id, oferta_id)`.

**`mcp-bbdd` no se toca**: su `abrir_adjunto` hace `LEFT JOIN compras.comparativo_ofertas ON
oferta_id = documento_id` y lee con `fetchone` (`infrastructure/db/repositorio_postgres.py`): la
columna existe y una fila de más no cambia el permiso ni el resultado. Contrato de F-139 intacto
(`test_f139_limite.py` verde).

## 3. Decisiones de diseño

1. **Reparto de líneas por invitación, no por documento.** La línea de oferta responde a una línea
   del concurso (`comlinide`) de UN comparativo: va a la invitación de ese comparativo. Desempate
   (línea sin `comlin`, 329 en Azure): la primera invitación. Con una sola invitación por oferta
   (72.107 de 72.113) el resultado es idéntico al de antes: medido en solo lectura, B cambia solo en
   las **6 invitaciones del COM26/0014** (80641-80646), que quedan sin líneas (NULL, 0), porque sus
   líneas son del 0037.
2. **El importe de documento (A) se repite en cada comparativo**: es la oferta que se presentó en los
   dos. El diccionario avisa de que sumar A de toda la tabla sin agrupar por comparativo cuenta dos
   veces la compartida.
3. **`es_ganadora` es del documento** (`con.est = 6`): la oferta ganadora del 0037 sale también
   ganadora en el COM26/0014. Es lo que dice Sigrid; no se inventa otra regla en un hotfix.
4. **Adjuntos**: una fila por enlace (clave `adjunto_id`) y la oferta compartida con el comparativo
   de su primera invitación, en vez de duplicar el enlace. El diccionario lo dice.
5. **Relaciones `N:N`**: el validador (`_validar_cardinalidad`) solo admite lado `1` si la columna
   es la clave sola o una alternativa de una columna; `oferta_id` ya no lo es.
6. **Estado `spec_ready`, no `in_progress`**: init.sh admite UNA sola `in_progress` (sección 3) y es
   F-150, que no se ha tocado. Por lo mismo, las puertas COBERTURA y TAMAÑO de init.sh miden F-150,
   no F-155 (ver «Evidencias»).

## 4. Fase RED (sandbox y estáticos, antes del código)

Sandbox: `docker run -d --name f155pg -e POSTGRES_PASSWORD=... -p 55155:5432 postgres:16`; el
fixture crea una BASE desechable (`f155_sandbox_<hex>`) y la borra al final (T5: la primera versión
hacía `DROP SCHEMA ... compras` y la vetó `test_f067_reset`, con razón); `raw`
con los tipos de `information_schema.columns` de Azure (ids y fechas `integer`, importes y
cantidades `double precision`, textos `character varying`). El test ejecuta `00_setup.sql`, `08`,
`09` y `14` REALES, cada uno en su transacción, como `execute_sql_file`.

```
$ F155_SANDBOX_DSN=postgresql://postgres:***@localhost:55155/postgres .venv/Scripts/python.exe -m pytest "tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_una_fila_por_invitacion" -q -p no:cacheprovider
E           psycopg.errors.UniqueViolation: could not create unique index "comparativo_ofertas_pkey"
E           DETAIL:  Key (oferta_id)=(11) is duplicated.
1 error in 1.84s
```

Es el MISMO error de la nocturna, con la oferta 11 de la miniatura. Fichero completo en RED:

```
$ F155_SANDBOX_DSN=... .venv/Scripts/python.exe -m pytest tests/test_f155_ofertas_compartidas.py -q -p no:cacheprovider
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_la_clave_de_las_ofertas_es_la_invitacion
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_las_lineas_de_la_oferta_se_reparten_por_invitacion
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_cada_linea_de_oferta_va_a_una_sola_invitacion
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_el_objetivo_agrega_por_comparativo_y_oferta
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_el_adjunto_de_una_oferta_toma_un_solo_comparativo
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_diccionario_declara_la_invitacion_como_clave
FAILED tests/test_f155_ofertas_compartidas.py::test_f155_ninguna_relacion_promete_oferta_id_unica
ERROR tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_una_fila_por_invitacion
ERROR tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_comparativos_sin_importes_duplicados
ERROR tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_cada_linea_de_oferta_una_vez_y_en_su_comparativo
ERROR tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_el_objetivo_de_cada_comparativo
ERROR tests/test_f155_ofertas_compartidas.py::test_f155_sandbox_un_adjunto_de_oferta_compartida_una_sola_fila
7 failed, 5 errors in 3.75s
```

En RED 08 cae primero, así que la sandbox no llega a 09 ni a 14; que también caerían lo dicen las
medidas de Azure (§1: 792.039 frente a 792.033 líneas; 3 adjuntos) y lo prueban los mutantes M3-M7
(§6), que devuelven 09 y 14 a un comportamiento incorrecto y los tests lo cazan.

**VERDE** después (mismo comando, sandbox incluida): `13 passed in 3.42s` (los 12 de RED + el de la
versión del diccionario; la sandbox ganó luego la línea 5005 sin `comlin`). Tras T5, con
`tests/test_f067_reset.py`: `21 passed in 22.87s`; mutación repetida: 7/7 muertos.

## 5. Lo que verifica la sandbox (miniatura del caso)

Comparativos 100 (original) y 200 (copia); ofertas 11 (real, ganadora) y 12 (OBJETIVO) invitadas
en los dos, 13 solo en el 100. Resultado verde:
- `comparativo_ofertas`: 5 filas, una por invitación; B de la 11 = 40,00 en el 100 y 30,00 en el
  200 (cada línea en su comparativo); la 12 = 47,00 en el 100 (incluida la 5005 sin `comlin`, a su
  primera invitación) y NULL/0 en el 200.
- `comparativos`: ganadora 11 en los dos, sin importes duplicados (100,25 / 40,00 y 100,25 / 30,00).
- `comparativo_oferta_lineas`: 5 líneas, cada una una vez.
- `comparativo_objetivo`: el 100 con 10 %; el 200 sin porcentaje (no hereda las líneas del 100).
- `documento_adjuntos`: el adjunto de la oferta compartida, una fila, con el comparativo 100.

## 6. Mutación del SQL (manual; `harness.mutacion` no muta SQL)

`python -m harness.mutacion --feature F-155 --base 1d65ca1 --max-mutantes 20` → **ALCANCE VACÍO**
(«ni una línea de producción que mutar»: el hotfix es SQL, YAML y tests). Por eso,
`progress/mutacion_sql_F-155.py` contra la sandbox:

```
MUERTO M1 08 orden del comparativo ASC: 2 failed, 3 passed, 8 deselected
MUERTO M2 08 desempate por la ultima invitacion: 1 failed, 4 passed, 8 deselected
MUERTO M3 08 B por documento otra vez: 2 failed, 3 passed, 8 deselected
MUERTO M4 09 orden del comparativo ASC: 2 failed, 3 passed, 8 deselected
MUERTO M5 09 desempate por la ultima invitacion: 1 failed, 4 passed, 8 deselected
MUERTO M6 09 objetivo sin comparativo en el JOIN: 1 failed, 4 passed, 8 deselected
MUERTO M7 14 primera invitacion -> ultima: 1 failed, 4 passed, 8 deselected
7 mutantes, 7 muertos, 0 supervivientes
```

M2 y M5 sobrevivían con la primera miniatura (no había línea sin `comlin`): por eso entró la 5005.

## 7. Verificaciones MANUAL pendientes (el humano; Azure)

En `progress/current.md` (sección F-155), con los comandos exactos, lo esperado y la vuelta
atrás (corregido tras `progress/review_F-155.md`). Orden: merge y push (humano) → imagen
(`infra/70_build_image.ps1`) → job (`infra/85_update_job.ps1 -Tag <tag>`, comprobado con
`az containerapp job show`) → `build-compras` (72.113 ofertas, 792.033 líneas) →
`check-declarados` (sin faltantes) → `publicar-diccionario` (v68) → `check-diccionario` (OK; **antes
de publicar devuelve 1**, compara el hash publicado con el del árbol) → reinicio del MCP. Vuelta
atrás: tag anterior `r20261031-0933`. Opcional: `check-unicidad`.

## 8. Fuera del alcance

- Decidir si una oferta reutilizada debe contar como ganadora en el segundo comparativo
  (`es_ganadora` es del documento, decisión 3): pregunta de Negocio, no del hotfix.
- Un aviso o `check` que vigile ofertas compartidas: hoy son 6 y el build ya las soporta.
- Construir la imagen y desplegar el job (humano).

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-155 (con sandbox, `F155_SANDBOX_DSN`) | **13 passed** en 3,42 s |
| Tests relacionados sin sandbox (f038, f090, f139, f006, f155) | 1287 passed, 268 skipped en 51,5 s |
| Suite completa (`bash harness/init.sh`) | **9932 passed, 274 skipped**, 0 failed, en 1 h 01 min 20 s |
| Cobertura de líneas cambiadas | N/A: F-155 no cambia líneas Python de producción (solo SQL, YAML y tests); la puerta de init.sh mide además la feature `in_progress` (F-150) |
| Mutantes generados / supervivientes | `harness.mutacion`: alcance vacío (0 líneas Python). SQL manual: **7 generados, 7 muertos, 0 supervivientes** |
| Medidas en Azure (solo lectura) | §1; impacto de B: solo las 6 invitaciones del COM26/0014 cambian de 72.113 |

### Resultado de `bash harness/init.sh` (tal cual, al terminar)

Tercera pasada, sobre `b1676db` (2026-10-31, ~13:55 UTC):

```
9932 passed, 274 skipped, 2570 warnings in 3680.42s (1:01:20)
[OK] pytest en verde (con medición de cobertura)
[OK] PUERTA COBERTURA: N/A (F-155 no cambia líneas Python de producción frente a main)
[OK] PUERTA TAMAÑO: F-155 dentro de los topes (impl 183/220)
[OK] Rama actual: feature/F-155-ofertas-compartidas
ENTORNO LISTO. Puedes trabajar.
```

Las dos primeras pasadas cayeron con 1 fallo cada una y se arreglaron (T5: el veto de
`DROP SCHEMA compras` de `test_f067_reset`; T6: `test_f108` cuenta las claves alternativas
declaradas). La sandbox se salta en init.sh (sin `F155_SANDBOX_DSN`); el contenedor `f155pg`
(puerto 55155) queda arrancado para que el reviewer la repita.
