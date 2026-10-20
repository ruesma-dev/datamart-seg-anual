<!-- progress/impl_F-145.md -->
# F-145 · Informe del implementer · la ficha de los adjuntos según la F-025 de `mcp-bbdd`

Fecha: 2026-10-20. Rama `feature/F-145-adjuntos-clave-empresa-codigo`. `sdd=false`, rigor `estandar`.
**Estado: `blocked`**. El trabajo de F-145 está hecho y sus tests están en verde. `bash harness/init.sh`
sale en rojo por un test de F-141 que **ya fallaba antes de empezar**: lo explica la sección 5.

## 1 · Qué cambió (solo texto, sus tests y la versión)

| Fichero | Cambio |
|---|---|
| `config/diccionario/compras.yaml` | Ficha de `compras.documento_adjuntos`: la petición a `documents/read` va con `key: {"emp": empresa_repositorio, "cod": cod_repositorio}`, sin `id_column` ni `id_value`. Párrafo nuevo **COMO LO PIDE (F-025 de `mcp-bbdd`, desplegada el 2026-10-19)**: un 400 `ValueError` o una empresa nula provocan UNA petición más, con la empresa 1, y un aviso al modelo (`respaldo=empresa_defecto` en la traza). El 409 da `ORIGEN_AMBIGUO`, sin reintentar. La columna `cod_repositorio` dice que va en la `key` junto a `empresa_repositorio`, nunca sola. La columna `empresa_repositorio` dice que es ENTERO, que renombrarla o cambiarle el tipo da `SIN_BINARIO` y que, si es nula, se usa el respaldo con la empresa 1 |
| `config/diccionario/00_global.yaml` | `version: 57` y su entrada `# version 57 (F-145, 2026-10-20)`. No nombra el código retirado, para que el barrido del test valga también sobre los comentarios |
| `config/diccionario/raw.yaml` | Ficha de `raw.gra`: «`documents/read` con `cod`» pasa a «con la pareja (`emp`, `cod`)» |
| `etl_sigrid/infrastructure/postgres/sql/compras/14_documento_adjuntos.sql` | Solo comentarios y el texto del `COMMENT ON TABLE`: «con la pareja (empresa_repositorio, cod_repositorio)», más un bloque de cabecera **CONTRATO CON `mcp-bbdd`** (la columna sale de `g.emp` tal cual y es ENTERA). No cambia ninguna sentencia. Ningún test fija el hash de este fichero (`test_f073_sql` fija el de `01_documentos.sql` y los del sello, no este) |
| `etl_sigrid/domain/documento_adjuntos.py` | Solo el docstring del módulo: decía «(`id_column` `cod`)» |
| `docs/ARCHITECTURE.md` | En el punto de F-090: la pareja, que `abrir_adjunto` está desplegada (F-023) y la F-025 con su respaldo. Se quita el «todavía sin desplegar», que ya era falso |
| `tests/test_f145_adjuntos_clave.py` | Nuevo: 41 tests (sección 3) |
| `azure-apps/datamart_seg_anual.md` (repo aparte, commit `4d77cbc`, solo ese fichero) | Párrafo de ~l.880 (la `key`, y `abrir_adjunto` ya existe). «Estado» de la sección F-139: de «CONTRATO ESCRITO, sin implementar» a «IMPLEMENTADO en `mcp-bbdd`». **H5** reescrito con la `key`, el respaldo, el 409 → `ORIGEN_AMBIGUO` y el código retirado. En «Qué se rompe si cambia», viñeta nueva con el contrato: `empresa_repositorio` es ENTERO, y renombrarla o cambiarle el tipo rompe `abrir_adjunto` (`SIN_BINARIO` y un WARNING); nula se tolera |

Commits en este repositorio: `b37768c` (T1, tests en RED), `599bf92` (T2, diccionario y v57),
`37aa832` (T3, SQL, dominio y ARCHITECTURE) y `e64231b` (T2 bis, la fecha de la F-025 es el 19 y no el 18,
según `azure-apps/mcp_bbdd.md`). No se tocó `mcp-bbdd`.

## 2 · Decisiones

- **«Entera en el SQL» se fija con un test estático**: los tests no tocan BBDD. La función
  `problemas_empresa_entera(sql)` exige tres cosas: que la única definición sea `g.emp AS empresa_repositorio`,
  sin `::`, `CAST` ni función; que el SELECT final pase `b.empresa_repositorio` sin conversión; y que `emp`
  no esté en las columnas excluidas de `gra`. El tipo entero viene de `raw.gra.emp` (`int` en Sigrid,
  `INTEGER` en `raw` según `ColumnSpec.postgres_type`). **No pude confirmarlo en Azure**: la lectura de
  `information_schema` desde el puesto no respondió en 100 s (`exit=124`), seguramente por el firewall con la
  IP nueva del puesto (memoria `ip-puesto-firewall-postgres`). Lo respalda la verificación de producción de
  `mcp-bbdd`: el 54066 y el 576 abren por su pareja, y eso exige un entero.
- **Sin `::INTEGER` explícito en el SQL**: el encargo era «nada que no sea texto». El cast queda como
  posible endurecimiento futuro, que hoy no hace falta.
- **El barrido de lo caducado** normaliza el ajuste de línea (`tests/_texto.py`) y quita los `#` de los
  comentarios YAML. Recorre todos los YAML del diccionario, el SQL, el dominio, ARCHITECTURE y `azure-apps`
  (este último con `skip` si falta). Cuatro sabotajes con las formas exactas que había lo demuestran, y un
  control comprueba que no salta con `id_column: ide`.
- **La versión es robusta al merge**, con el patrón de la R31 de F-128: antes del merge, la de `main` + 1;
  si `main` ya lleva «(F-145, », basta con no bajar.
- **Lo que retoqué además de lo listado en el encargo**, porque contradecía la F-025: el docstring del
  dominio, `raw.yaml`, ARCHITECTURE y el «Estado» de la sección F-139 en `azure-apps`. Todo es texto.

## 3 · Fase RED (obligatoria en `estandar`)

Los tests se escribieron antes que el texto (commit `b37768c`). Comando y salida real:

```
$ python -m pytest tests/test_f145_adjuntos_clave.py -q -p no:cacheprovider -rf
FAILED tests/test_f145_adjuntos_clave.py::test_f145_ninguna_ficha_dice_lo_caducado[compras.yaml]
FAILED tests/test_f145_adjuntos_clave.py::test_f145_ni_el_sql_ni_el_dominio_ni_la_arquitectura[documento_adjuntos.py]
FAILED tests/test_f145_adjuntos_clave.py::test_f145_ni_azure_apps - Assertion...
FAILED tests/test_f145_adjuntos_clave.py::test_f145_la_ficha_dice_la_pareja_el_respaldo_y_el_409
FAILED tests/test_f145_adjuntos_clave.py::test_f145_la_columna_cod_repositorio_dice_la_pareja
FAILED tests/test_f145_adjuntos_clave.py::test_f145_la_columna_empresa_repositorio_dice_el_contrato
FAILED tests/test_f145_adjuntos_clave.py::test_f145_el_comment_de_la_tabla_dice_la_pareja
FAILED tests/test_f145_adjuntos_clave.py::test_f145_azure_apps_dice_la_pareja_y_el_contrato
FAILED tests/test_f145_adjuntos_clave.py::test_f145_version_la_siguiente_a_la_de_main
FAILED tests/test_f145_adjuntos_clave.py::test_f145_historia_de_versiones - a...
10 failed, 31 passed in 2.60s
```

Errores representativos de esa ejecución:

```
E   AssertionError: compras.yaml aún dice ['id_column`?\\s*:?\\s*`?\\s*\\"?cod\\b']: desde la F-025 de `mcp-bbdd` ...
E   AssertionError: `empresa_repositorio` no dice «ENTERO»
E   AssertionError: H5 no dice «"emp": empresa_repositorio» (F-145)
E   assert 56 >= (56 + 1)
```

Los 31 que pasaban en RED son la guarda del entero (el SQL ya cumplía), sus seis sabotajes, los cuatro
sabotajes del barrido, su control, los YAML sin nada caducado y el SQL/ARCHITECTURE (sin `id_column`).
Son guardas de regresión: el test pasa sobre lo que ya era correcto y los sabotajes demuestran que tiene
dientes.

GREEN, tras T2 y T3 y el commit en `azure-apps`:

```
$ python -m pytest tests/test_f145_adjuntos_clave.py -q -p no:cacheprovider
41 passed in 1.26s
```

## 4 · Verificación de los vecinos

- `tests/test_f090_diccionario.py`, `test_f090_ingesta_sql.py`, `test_f090_dominio.py`, `test_f139_limite.py`,
  `test_f128_diccionario.py` y `test_f145_*`: verdes (`155 passed`).
- Todos los tests que leen `azure-apps` (`grep -l "azure-apps|AZURE_APPS|datamart_seg_anual.md"`) más
  `test_f145`: `1 failed, 2200 passed`. El único fallo es el de F-141 R30 (sección 5).
- Tests que `init.sh` no llega a correr porque para en el primer fallo (`test_f141_*` entero y todo lo que
  ordena detrás: `test_f144`, `test_f145`, `test_mutacion_*`, `test_smoke`, `test_sql_split`,
  `test_tamano`): `1 failed, 505 passed, 1 skipped`. El mismo fallo de F-141 R30, ninguno más.

## 5 · `bash harness/init.sh` · resultado real y motivo del bloqueo

**Inicial**, lanzado al empezar y en paralelo con la lectura del encargo (antes de que yo cambiara nada):

```
FAILED tests/test_f141_perfil_restringido.py::test_f141_r30_mcp_bbdd_solo_enlaza_al_contrato
1 failed, 8113 passed, 253 skipped, 2215 warnings in 3257.71s (0:54:17)
[KO] pytest en rojo   ·   1 comprobaciones fallidas. NO empieces a trabajar.
```

Lo vi cuando T1 ya estaba escrito: lancé el `init.sh` en segundo plano y seguí leyendo. Debí esperar su
resultado antes de escribir. El fallo no depende de F-145, así que terminé el trabajo aprobado en vez de
dejarlo a medias sin commit, y lo declaro aquí.

**Final**, tal cual, sobre `e64231b`:

```
FAILED tests/test_f141_perfil_restringido.py::test_f141_r30_mcp_bbdd_solo_enlaza_al_contrato
1 failed, 8113 passed, 253 skipped, 2215 warnings in 1685.95s (0:28:05)
[KO] pytest en rojo (¿pytest instalado en el venv?)
[OK] PUERTA COBERTURA: N/A (F-145: las líneas cambiadas no contienen sentencias ejecutables)
[OK] PUERTA TAMAÑO: F-145 dentro de los topes (ningún fichero de papeleo todavía)
[OK] Rama actual: feature/F-145-adjuntos-clave-empresa-codigo
1 comprobaciones fallidas. NO empieces a trabajar.
```

**La causa**: R30 de F-141 exige que toda línea de `azure-apps/mcp_bbdd.md` que nombre
`mcp_sigrid_dm_restringido` o «F-141» enlace a `datamart_seg_anual.md`. El commit `2f28a8d` de `azure-apps`
(«mcp-bbdd F-027: tres perfiles...») añadió tres que no enlazan: **l.410**
(`> mcp_sigrid_dm_restringido (PG_RESTRINGIDO_USER, ...`), **l.650** (fila de `PG_RESTRINGIDO_USER`) y
**l.651** (fila de `PG_RESTRINGIDO_PASSWORD`). Ese documento es de `mcp-bbdd`, y F-145 no lo toca.

**Las opciones, para el humano** (ninguna aplicada):
1. Que `mcp-bbdd` añada en esas tres líneas el enlace a `datamart_seg_anual.md`. Es lo que pide R30 y lo más
   barato: tres referencias en el documento de su dueño.
2. Reformular R30 en este repositorio para que solo vigile que no se copian las cláusulas E1-E8 (la
   segunda mitad del test), aceptando que `mcp_bbdd.md` nombre su propio login. Así sería una feature o un
   ajuste de F-141, no de F-145.

En cuanto se resuelva cualquiera de las dos, `init.sh` debería quedar verde sin tocar F-145: todo lo que
corre detrás del fallo está medido en la sección 4.

## 6 · MANUAL pendiente (tras APROBADO y merge, en este orden)

1. **Imagen nueva y job** `caj-datamart-seg-dev` actualizado a ella **ANTES** de publicar la v57. La nocturna
   republica el diccionario de la imagen (lección del 19-10, memoria `publicar-diccionario-solo-con-imagen`).
2. `python main.py publicar-diccionario` (v57) y `python main.py check-diccionario`.
3. Reiniciar el MCP (`mcp-bbdd`), que cachea el diccionario hasta reiniciar.
4. Opcional: confirmar en Azure, en solo lectura, que `compras.documento_adjuntos.empresa_repositorio` es
   `integer`, lo que no pude leer desde el puesto (sección 2).

El SQL solo cambia en comentarios y en el `COMMENT`: el `COMMENT ON TABLE` nuevo entra con la nocturna o con
un `build-compras`. No hace falta ingesta.

## 7 · Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests nuevos | 41 (`tests/test_f145_adjuntos_clave.py`): 10 en RED, 41/41 en GREEN, 1,26 s |
| Suite en `init.sh` (final) | `1 failed, 8113 passed, 253 skipped` en 1685,95 s; para en el fallo ajeno de F-141 R30 |
| Suite de lo que `init.sh` no alcanza | `1 failed, 505 passed, 1 skipped` en 61,75 s; el mismo fallo ajeno |
| Cobertura de líneas cambiadas | **N/A**: `PUERTA COBERTURA: N/A (F-145: las líneas cambiadas no contienen sentencias ejecutables)`. La única línea Python tocada es un docstring |
| Mutantes generados / supervivientes | **No aplica**: `python -m harness.mutacion --feature F-145` → «CERO MUTANTES en F-145: el alcance tiene 3 línea(s) de producción pero no se ha generado ni un mutante» (las 3 líneas son docstring), código de salida 3 y sin informe, a propósito. Los dientes los demuestran los 10 sabotajes de la sección 3 (6 de la guarda del entero y 4 del barrido) |
| Tiempo de la suite | 1685,95 s (0:28:05), el que imprime pytest dentro de `init.sh` |
