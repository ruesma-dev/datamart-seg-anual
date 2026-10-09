<!-- progress/impl_F-132_faseB.md -->
# F-132 · Informe del implementer · Fase B, rama BORRAR · la foto diaria se retira

Anexo de `progress/impl_F-132.md` (la Fase A, que ya está en su tope de 220
líneas). Rama `feature/F-132-estado-desde-rac`, 2026-10-09. Rigor **estándar**.
Decisión del humano del 2026-10-09 (`progress/spec_F-132.md` §8): **D6 acortada**
(contraste cerrado con 2 noches) y **D7 = BORRAR**. Tareas T16, T17, T18, T20 y
T21; **T19 (congelar) no aplica**. Un commit por tarea, sin push:

| Tarea | Commit | Qué |
|---|---|---|
| T16 | `02157ba` | Cierre del contraste anotado en `progress/contraste_F-132.md` (sin relanzarlo) |
| T17 | `f4a30d8` | `build_compras` deja de tomar la foto; época de Delphi a `domain/fecha_delphi.py` |
| T18 | `b4f6a99` | `retirar-foto-estados [--confirmar]`; `reset-compras` sin conservadas; fuera `contraste-estados` |
| T20 | `b0946ce` | Diccionario **v47**, `ARCHITECTURE`, README, `tables_sigrid`; `azure-apps` **`8a8ac98`** (sin push) |
| T21 | (este informe) | Test del superviviente de la mutación, informe y `init.sh` final |

**Nada se escribió en Sigrid ni en Azure.** Única lectura externa: `python main.py
retirar-foto-estados` SIN `--confirmar` contra el Postgres del `.env` (el de
Azure), en transacción READ ONLY, para comprobar que su `SELECT` corre y para dar
al MANUAL la salida esperada (§5).

## 1 · Qué cambió

| Fichero | Qué |
|---|---|
| `sql/compras/11_historial_estados.sql` | **Borrado** (la foto: dos tablas persistentes y su bloque `DO`) |
| `application/steps/build_compras_step.py` | Fuera el sub-paso `historial_estados`; docstring explica el hueco del `11` (no se renumera: `12` y `13` los citan diccionario, tests y docs) |
| `domain/historial_estados.py` | **Borrado** (oráculo de la foto; en T17 quedó con 3 constantes hasta T18) |
| `domain/fecha_delphi.py` (nuevo) | `EPOCA_DELPHI` y `fecha_delphi`, que siguen usando `fn_sigrid_tiempo` y `test_f067_sql` r14 (R25) |
| `domain/estado_documentos.py` | Fuera el dominio del contraste (`clasificar_*`, `contrastar`, `discrepancias`, `formatear_contraste`, `CLASES_*`, `Contrastado`); quedan `fecha_estado` y `dias_en_estado` |
| `infrastructure/postgres/contraste_estados_sql.py` | **Borrado** |
| `infrastructure/postgres/retirar_foto_sql.py` (nuevo) | `TABLAS_FOTO`, `SQL_TABLAS_FOTO` (SELECT: cuáles existen y sus filas, con `query_to_xml` para no fallar si falta una) y `SENTENCIAS_RETIRADA` (`SET LOCAL lock_timeout = '30s'` + `DROP TABLE IF EXISTS` de las dos, **sin `CASCADE`**) |
| `infrastructure/postgres/compras_reset_sql.py` | Sin lista de conservadas (fuera el `NOT IN`); sigue sin `DROP SCHEMA` (R26) |
| `main.py` | Comando `retirar-foto-estados [--confirmar]`; `reset-compras` con su docstring y mensaje nuevos; **fuera `contraste-estados`** (y con él la observación 3 del review: las tres líneas en blanco) |
| `sql/compras/00_setup.sql`, `12_documento_procesos.sql` | Solo comentarios: la época vive en `fecha_delphi.py`; la antigüedad, en `rac` (observación 1 del review de la Fase A) |
| `config/diccionario/compras.yaml` | Fuera las fichas de `historial_estados` e `historial_estados_fotos` |
| `config/diccionario/00_global.yaml` | **v47** con su historia; P24 espera solo `documento_procesos` y dice que el deshacer no se fecha (F-105); descripción de `compras` sin la foto (R28) |
| `config/tables_sigrid.yaml`, `docs/ARCHITECTURE.md`, `README_COMPRAS_C1_C2.md` | La foto se RETIRÓ (y cómo se borran sus tablas); ARCHITECTURE separa lo que F-067 dejó y no era la foto (R28) |
| `specs/F-006-mcp-azure/design_detalle.md` | Enmienda del 2026-10-09: inventario **207 → 205**, columnas 1623 → 1608 |
| `../azure-apps/datamart_seg_anual.md` | F-067: foto RETIRADA; F-132: Fase B decidida, SIN DESPLEGAR, con el orden del despliegue. Commit `8a8ac98` |
| Tests nuevos | `test_f132_retirada.py` (32: R25, R26, el veto y el `statement_timeout` que pidió la mutación) |
| Tests reescritos | `test_f067_reset.py` (8, R26), `test_f132_contraste.py` (2: solo `filas_solo_lectura(params=...)`, que sigue en `PostgresClient`) |
| Tests retirados o ajustados | Borrado `test_f067_dominio.py`; `test_f067_sql` (fuera R1-R8 de la foto), `test_f132_sql` (fuera la huella y la cabecera de `11`), `test_f132_dominio` (fuera R13-R14), `test_f067_diccionario` y `test_f132_diccionario` (fichas fuera, P24, textos de la Fase B, v47); listas de sub-pasos de `f047`, `f073`, `f080`, `f085` |

Diccionario del árbol: **205 objetos, 1608 columnas, 96 de consumo** (versión 47,
sin publicar).

## 2 · Decisiones y desviaciones (también en `progress/current.md`)

- **Fichas, P24 y descripción de `compras` en T17, no en T18/T20**: al borrar
  `11_historial_estados.sql` la puerta de F-006 (`test_f006_fichas`) rompe con
  una ficha sin SQL que la cree. Es «ficha en el mismo commit que el objeto»,
  al revés. La subida a v47 y su historia sí van en T20.
- **`domain/historial_estados.py` vive en T17 con tres constantes** (las leían el
  contraste y el reset) y muere en T18: cada commit deja la suite en verde.
- **El dominio del contraste sale con el comando**: solo le servía a él.
- **`test_f132_contraste.py` se conserva con los dos tests de `params`** (la T18
  lo cita como verificación); lo de la Fase B va en `test_f132_retirada.py`.
- **El comando lee antes y después** con `filas_solo_lectura` (READ ONLY): dice
  qué hay, y tras el `DROP` comprueba que no queda nada (código 1 si queda).
  Repetirlo es inocuo (`IF EXISTS`; sin tablas, «nada que borrar», código 0).
- **Sin `CASCADE` y con `lock_timeout` de 30 s**: si algo dependiera de las
  tablas, el `DROP` falla entero; si la nocturna de una imagen vieja las tuviera
  bloqueadas, falla a los 30 s en vez de quedarse colgado.
- **`01_documentos.sql` NO se toca**: su cabecera (l. 71-72) aún dice que la
  antigüedad «la da la foto diaria (`11_historial_estados.sql`)», pero el
  fichero está fijado por la huella de `test_f073_sql` r23 (observación 2 del
  review de la Fase A). El veto nuevo mira lo EJECUTABLE del SQL. **Queda
  pendiente** para quien toque `01` (recalcular su huella en ese trabajo).
- **El veto busca la TABLA** (`compras.historial_estados` o el nombre entre
  comillas), no el nombre del fichero: los docstrings que cuentan que `11`
  existió no la tocan.
- `patches/main_py_patch_compras.py` (parche histórico, fuera de lo vigente que
  mira R22) sigue diciendo que `reset-compras` conserva la foto: no se toca.

## 3 · Fase RED (trazas reales; `.venv/Scripts/python.exe -m pytest ... -q -p no:cacheprovider`)

**T17 (R25), `tests/test_f132_retirada.py` antes del código** — 13 failed:
```
E       AssertionError: assert not True                 # 11_historial_estados.sql existe
E       AssertionError: assert 'historial_estados' not in ['setup', 'documentos', 'fact_linea', 'views', 'formas_pago', 'vencimientos', ...]
E       AssertionError: assert ModuleSpec(name='etl_sigrid.domain.historial_estados', ...) is None
E       ModuleNotFoundError: No module named 'etl_sigrid.domain.fecha_delphi'      (x8)
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\etl_sigrid\\domain\\fecha_delphi.py'
E       AssertionError: assert {'etl_sigrid/...tos.sql', ...} == {'etl_sigrid/..._foto_sql.py'}
13 failed in 8.74s
```
(El veto y «el dominio de la foto ya no existe» se movieron a T18: con el
contraste aún vivo no podían pasar en T17.) GREEN tras T17: `11 passed in 2.27s`.

**T18 (R26), `tests/test_f132_retirada.py tests/test_f067_reset.py` antes del código** — 23 failed:
```
E       Error: No such command 'retirar-foto-estados'. Did you mean 'contraste-estados'?   (x6)
E       ImportError: cannot import name 'retirar_foto_sql' from 'etl_sigrid.infrastructure.postgres'   (x3)
E       AssertionError: assert 'contraste-estados' not in {'version': <Command version>, ...}
E       AssertionError: assert ModuleSpec(name='etl_sigrid.infrastructure.postgres.contraste_estados_sql', ...) is None
E       AssertionError: assert ModuleSpec(name='etl_sigrid.domain.historial_estados', ...) is None
E       AssertionError: assert not True        # hasattr(estado_documentos, 'clasificar_cambio'...)  (x7) y TABLAS_PERSISTENTES
E       AssertionError: assert "WHERE n.nspname = 'compras' AND c.relkind IN ('r', 'p') LOOP EXECUTE format('DROP TABLE ..." in " DO $$ ... AND c.relname NOT IN ('historial_estados', 'historial_estados_fotos') LOOP ..."
E       AssertionError: assert 'historial_estados' not in 'compras vac...-compras`.\n'
E       AssertionError: assert {'etl_sigrid/...tados_sql.py'} == {'etl_sigrid/..._foto_sql.py'}
23 failed, 16 passed in 5.48s
```
GREEN tras T18: `31 passed` + `8 passed`; suite entera sin cobertura `7141 passed, 228 skipped in 309.86s`.

**T20 (R21, R28), `tests/test_f132_diccionario.py` antes de los textos** — 5 failed:
```
E       AssertionError: assert 'se retiro' in ', medido el 2026-09-06 y corregido por f-085 ...'
E       AssertionError: assert 'retirar-foto-estados --confirmar' in '<!-- docs/architecture.md --> ...'
E       AssertionError: assert 'retirar-foto-estados --confirmar' in '# tandas c1 + c2 — modulo compras ...'
E       AssertionError: assert 46 >= 47
E       AssertionError: assert 'retirar-foto-estados --confirmar' in '\n\n**Estado: Fase A DESPLEGADA el 2026-10-09** ...'
5 failed, 20 passed in 2.61s
```
GREEN tras T20: `159 passed` (`f132_diccionario`, `f067_diccionario`, `f006_reglas`, `f006_contexto`, `f006_docs`).

## 4 · Fuera del alcance

- T19 (congelar): no aplica. `contraste-estados` no se relanzó (T16, decisión).
- `01_documentos.sql` (§2). R24 (la pregunta al MCP) sigue siendo MANUAL de la Fase A.
- Fechar los pasos deshechos: F-105 (`dbo.log`).

## 5 · MANUAL, EN ESTE ORDEN (humano y líder)

1. **Imagen y job (humano).** Construir la imagen desde la rama ya integrada y
   apuntar el job a ella; **comprobar el tag del job** (la nocturna corrió una
   imagen vieja diez días en agosto). Hasta que la imagen nueva corra, la
   nocturna sigue tomando la foto.
2. **`python main.py retirar-foto-estados` (humano), primero SIN `--confirmar`.**
   Leído hoy (2026-10-09 10:42 UTC, solo lectura) sale:
   ```
   Retirada de la foto diaria de estados (F-132, Fase B) · SIN --confirmar: solo lectura
     compras.historial_estados: 186705 filas
     compras.historial_estados_fotos: 3 filas
   NO se ha borrado nada. Para borrarlas, en UNA transacción: `python main.py retirar-foto-estados --confirmar`.
   ```
   (`historial_estados_fotos` con 4 filas si la nocturna del 10-10 corre aún con
   la imagen vieja.) Después **CON `--confirmar`**: las mismas dos líneas,
   `Borradas: compras.historial_estados, compras.historial_estados_fotos` y
   `Comprobado: ya no queda ninguna de las dos.`, código 0. Repetirlo da
   «Ninguna de las dos tablas existe: nada que borrar.».
3. **Diccionario y MCP (líder).** `python main.py publicar-diccionario` (v47),
   `python main.py check-diccionario` en verde (205 objetos) y reiniciar
   `mcp-bbdd`.

**Si se invierte el orden:**
- **2 antes de 1**: la nocturna de la imagen vieja ejecuta `11_historial_estados.sql`,
  que las vuelve a crear con `CREATE TABLE IF NOT EXISTS` y toma una LÍNEA BASE
  nueva (~186.700 tramos). Hay que volver a lanzar el paso 2 tras desplegar.
- **3 antes de 2**: `check-diccionario` sale con 1 («publicado sin ficha»: las dos
  tablas existen y v47 ya no las describe), y el MCP las ve sin ficha.
- **3 antes de 1**: la nocturna de la imagen vieja vuelve a publicar SU
  diccionario (v46, `run-all` incluye `publicar_diccionario`) y pisa la v47:
  el MCP describiría como «respaldo en contraste» unas tablas que van a morir.
- La imagen nueva sin el paso 2 no rompe nada: nadie escribe ni lee las tablas, y
  un `reset-compras` las borraría también (ya no conserva ninguna).

## 6 · Evidencias

| Evidencia | Valor real |
|---|---|
| Tests ejecutados (`init.sh` sobre `b0946ce`) | **7.142 passed, 228 skipped, 0 failed** (antes de la Fase B: 7.245 / 229; 103 menos en neto: se van los de la foto y del contraste). De la Fase B: `test_f132_retirada` 32, `test_f067_reset` 8, `test_f132_contraste` 2 |
| Cobertura de las líneas cambiadas | **100,0 %** (42/42, umbral 80 %, nivel estándar; `PUERTA COBERTURA`, diff desde `09bec58`) |
| Mutantes generados y supervivientes | **18 generados, 18 evaluados (campaña completa: menos de los 20 del muestreo), 16 muertos, 2 supervivientes, 0 timeouts**, 3.739,8 s con 2 workers. Los dos (el `120` del `statement_timeout` de las dos lecturas) eran un hueco real y los cierra un test nuevo, comprobado con el mutante aplicado a mano: `progress/mutacion_F-132_faseB.md` |
| Tiempo de la suite | **1.362,92 s (22 min 42 s)** con cobertura; 309,86 s sin ella |
| `init.sh` | Arranque sobre `a237288`: VERDE (7.245 passed). Final sobre `b0946ce`: **VERDE** («ENTORNO LISTO», tamaño impl 218/220). Tras el test de T21, ver `progress/current.md` |
| Lectura real (solo lectura) | `retirar-foto-estados` sin `--confirmar` contra el Postgres del `.env`: 186.705 tramos y 3 fotos (§5) |
