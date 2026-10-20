<!-- progress/impl_F-145.md -->
# F-145 · Informe del implementer · la ficha de los adjuntos según la F-025 de `mcp-bbdd`

Fecha: 2026-10-20. Rama `feature/F-145-adjuntos-clave-empresa-codigo`. `sdd=false`, rigor `estandar`.
**Estado: `in_progress`, pasada 2 hecha, al reviewer.** `bash harness/init.sh` en verde (sección 5).
La pasada 2 (review: H1, H2, H3 y O1) está en la sección 7; las secciones 1-4 son la pasada 1.

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
- En la pasada 1 los vecinos que leen `azure-apps` daban un único fallo, el ajeno de F-141 R30 (sección 5).

## 5 · `bash harness/init.sh` · resultado real

**Historia (pasada 1)**: `init.sh` salió en rojo por `test_f141_r30_mcp_bbdd_solo_enlaza_al_contrato`, ajeno
y previo a F-145 (`azure-apps` `2f28a8d`); la feature quedó `blocked` hasta que `mcp-bbdd` enlazó las tres
líneas (`408c007`) y el líder lo vio en verde sobre `d36bd09` (8479 passed, 254 skipped).

**Final (pasada 2)**, tal cual, sobre `@@HEAD@@`:

```
@@INIT@@
```

## 6 · MANUAL pendiente (tras APROBADO y merge, en este orden)

La secuencia con sus comandos exactos está en `progress/current.md` (entrada de F-145, C4): imagen
(`infra/70_build_image.ps1`), job a esa imagen con `infra/85_update_job.ps1 -Tag <tag>` **ANTES** de
publicar (la nocturna republica el diccionario de la imagen del job), `main.py publicar-diccionario` (v57),
`main.py check-diccionario`, reinicio del MCP (revisión vigente `ca-mcp-bbdd-dev--0000022`) y aviso a
`mcp-bbdd`. El `COMMENT ON TABLE` nuevo entra con la nocturna o un `build-compras`; sin ingesta.
`empresa_repositorio` ya está verificada `integer` en Azure (líder, solo lectura), lo que en la pasada 1 no
pude leer desde el puesto (sección 2).

## 7 · Pasada 2 · lo que pidió la review

| Punto | Qué se hizo | Commit |
|---|---|---|
| H1 / cambio 1 | `compras.yaml` (ficha de `compras.documento_adjuntos`), comentario de la v57 en `00_global.yaml` y `docs/ARCHITECTURE.md` separan los tres casos: empresa distinta de la 1 con 400 `ValueError` → UNA segunda petición con la 1 y el mismo `cod`; empresa nula → la única petición va directamente con la 1; en los dos, aviso y `respaldo=empresa_defecto`; empresa 1 con 400 → `SIN_BINARIO`, sin segunda petición (y lo mismo si con la 1 tampoco hay fichero) | `ac6ab44` (T4) |
| H1 / cambio 2 | `azure-apps/datamart_seg_anual.md` H5, el mismo ajuste; commit nuevo que toca solo ese fichero, encima de `5d47417` | `azure-apps` `5602198` |
| cambio 3 | Tests que exigen la distinción, con RED (abajo) | `ac6ab44` (T4) |
| O1 | La guarda `problemas_empresa_entera` ve también el renombrado en el SELECT final (`b.empresa_repositorio AS empresa,`): sabotaje nuevo y la comprobación del alias, con RED | `c3d5081` (T5) |
| H2, H3 / cambios 4 y 5 | Este informe al día y la secuencia MANUAL con sus comandos en `progress/current.md` | commit de papeleo |

**Contraste con la fuente.** No me quedé con el encargo: leí `mcp-bbdd/infrastructure/sigrid/cliente_documentos.py`
(`leer()`: `empresa = clave.empresa if clave.empresa is not None else EMPRESA_RESPALDO`; sin fila y
`empresa == EMPRESA_RESPALDO` → `raise SinBinario()`; si no, una petición más con la 1 y, si tampoco,
`SinBinario`; `por_respaldo` cuando se localizó con la 1 sin que la fila lo dijera), `domain/adjuntos.py`
(`AVISO_RESPALDO`), `servicio_adjuntos.py` (`traza["respaldo"] = "empresa_defecto"`) y `azure-apps/mcp_bbdd.md`
l.147. El texto nuevo no dice nada que no esté ahí. **Hallado de paso**: `mcp_bbdd.md` l.218-222 no distingue
la fila de la empresa 1; es documento de `mcp-bbdd` y no se toca (anotado en el aviso de `current.md`).
**Fuera de alcance**: la descripción de F-145 en `harness/features.json` (y el `BACKLOG.md` generado) repite
la forma mezclada; es el encargo, del líder.

**Diseño de los tests.** La forma mezclada entra en `CADUCADO` (una regex
que caza «o la fila trae `empresa_repositorio` nula», «o la fila no trae empresa» y «o la empresa es nula»), así que el barrido de siempre la busca en los YAML del diccionario, SQL, dominio,
ARCHITECTURE y `azure-apps`; cuatro sabotajes con las cuatro formas exactas que había (ficha, v57,
ARCHITECTURE y el docstring del propio test) y el control, ampliado con el texto nuevo, prueban que no
salta en falso. En positivo, la ficha y H5 tienen que decir `TRES_CASOS_DEL_RESPALDO` («distinta de la 1»,
«directamente con la empresa 1», `` `SIN_BINARIO` ``, «sin segunda petici») y un test nuevo exige a la v57 y a
ARCHITECTURE «distinta de la 1», «directamente» y `` `SIN_BINARIO` ``.

**RED de H1**, tests escritos antes que el texto:

```
$ .venv/Scripts/python.exe -m pytest tests/test_f145_adjuntos_clave.py -q -p no:cacheprovider
E   AssertionError: 00_global.yaml aún dice ['\bo la (?:fila (?:no )?trae (?:`?empresa_repositorio`? nula|empresa)|empresa es nula)']: ...
E   AssertionError: compras.yaml aún dice ['\bo la (?:fila (?:no )?trae (?:`?empresa_repositorio`? nula|empresa)|empresa es nula)']: ...
E   AssertionError: ARCHITECTURE.md aún dice ['\bo la (?:fila (?:no )?trae (?:`?empresa_repositorio`? nula|empresa)|empresa es nula)'] (F-145)
E   AssertionError: azure-apps/datamart_seg_anual.md aún dice ['\bo la (?:fila (?:no )?trae (?:`?empresa_repositorio`? nula|empresa)|empresa es nula)'] (F-145)
E       AssertionError: la ficha no dice «distinta de la 1» (F-145)
E       AssertionError: _comentario_v57 no dice «distinta de la 1» (F-145, H1)
E       AssertionError: _parrafo_del_limite_en_arquitectura no dice «distinta de la 1» (F-145, H1)
E       AssertionError: H5 no dice «distinta de la 1» (F-145)
8 failed, 39 passed in 3.19s
```

GREEN tras el texto: `tests/test_f145_adjuntos_clave.py tests/test_f090_diccionario.py tests/test_f139_limite.py`
→ `84 passed in 10.81s`.

**RED de O1**, el sabotaje antes que la comprobación:

```
$ .venv/Scripts/python.exe -m pytest tests/test_f145_adjuntos_clave.py -q -p no:cacheprovider -k sabotaje_la_guarda
E       AssertionError: no ve «b.empresa_repositorio AS empresa,»
FAILED tests/test_f145_adjuntos_clave.py::test_f145_sabotaje_la_guarda_ve_cada_forma_de_romperlo[b.empresa_repositorio,-b.empresa_repositorio AS empresa,]
1 failed, 6 passed, 41 deselected in 2.48s
```

GREEN: `tests/test_f145_adjuntos_clave.py` → `48 passed in 3.93s`.

## 8 · Evidencias

| Evidencia | Valor medido |
|---|---|
| Tests de F-145 | 48 en `tests/test_f145_adjuntos_clave.py` (41 de la pasada 1 + 7 de la 2): RED 10 (pasada 1), 8 (H1) y 1 (O1); GREEN 48/48 en 3,93 s |
| Suite en `init.sh` (final) | @@SUITE@@ |
| Cobertura de líneas cambiadas | @@COBERTURA@@ |
| Mutantes generados / supervivientes | **0 / 0, legítimo**: las únicas líneas de producción del alcance son el docstring de `documento_adjuntos.py` (pasada 1: `python -m harness.mutacion --feature F-145` → «CERO MUTANTES», salida 3; el reviewer lo recalculó con control). La pasada 2 solo toca texto y tests. Los dientes: 8 sabotajes del barrido (4 + 4 de la pasada 2) y 7 de la guarda del entero (6 + O1) |
| Tiempo de la suite | @@TIEMPO@@ |
