# F-138 · Informe del implementer: las alarmas de Sigrid y la marca «liquidatoria»

Spec: `specs/F-138-facturas-liquidatorias/` (D1-D9 del 2026-10-14). Rama
`feature/F-138-facturas-liquidatorias`, rigor `estandar`. Un commit por tarea (T1-T11);
T12 (mutación), T13 (este informe) y T17 (`init.sh`) al final; T14-T16 son MANUAL.

## Qué cambió

| Fichero | Cambio |
|---|---|
| `etl_sigrid/domain/liquidatoria.py` (nuevo) | Oráculo puro: 17 familias en lista explícita (sin la 43), `FAMILIAS_MARCA` (14, 15), `FAMILIAS_RESTRINGIDAS` {33, 35}, traducción de 44 caracteres, los 5 patrones de R7, `PRECEDENCIA`, `CLASES_CIERRE`, `filtro_conala`, `es_restringida`, `normalizar`, `clasificar`, `marca_documento`, `fecha_hora_creacion` |
| `config/tables_sigrid.yaml` | + `conala` (`where` = `filtro_conala()`, sin `tiemod`, sin exclusiones) y + `auxala` (entera, `tiemod`): 76 tablas |
| `sql/compras/00_setup.sql` | `CREATE SCHEMA IF NOT EXISTS compras_restringida` |
| `sql/compras/15_alarmas_liquidatoria.sql` (nuevo) | Guarda de ingesta, `fn_texto_normalizado`, `fn_clase_liquidacion`, `compras_restringida.documento_alarmas` (completa), `compras.documento_alarmas` (general), guarda de la restricción, `documento_liquidatoria`, `contrato_liquidacion`, `facturas_tras_liquidacion` |
| `build_compras_step.py` | Sub-paso `alarmas_liquidatoria`, el último; cuenta `compras.documento_alarmas` |
| `config/settings.py`, `.env.example`, `domain/diccionario.py`, `infra/sql/02_roles.sql` | `compras_restringida` vetada al estándar, del autorizado, no vetada al total; 16 esquemas; `02_roles.sql` la crea como `sigrid_dm_etl`, la veta (dos concedentes), la concede y la comprueba |
| `config/diccionario/` | `compras.yaml` (4 fichas + 2 funciones + relaciones desde `facturas`, `albaranes`, `contratos`), `compras_restringida.yaml` (nuevo), `raw.yaml` (`conala`, `auxala`, «Son 76»), `00_global.yaml` v52 (esquema, `R-COMPRAS-RESTRINGIDA`, `R-FRESCURA` alcanza el esquema, `R-SIGRID-CON` con `auxala.cod/res`, «las 76 tablas») |
| `docs/ARCHITECTURE.md`, `CLAUDE.md`, `specs/F-006-mcp-azure/design_detalle.md` | 76 tablas, los objetos nuevos, el tercer esquema restringido; enmienda del inventario (226 objetos, 1864 columnas, 109 de consumo) |
| `azure-apps/datamart_seg_anual.md` | Commit local `0f45bbb` en `azure-apps` (rama `master`, sin push): consume 76 tablas, expone los objetos, contrato con `mcp-bbdd` (`compras_restringida` en su lista blanca común) |
| Tests nuevos | `test_f138_dominio.py` (102), `test_f138_ingesta_sql.py` (40), `test_f138_grants.py` (13), `test_f138_diccionario.py` (22) |
| Tests existentes ajustados | Censo 74 -> 76 (F-066, F-074, F-085, F-090, F-095, F-097); listas de esquemas 15 -> 16 y vetados/restringidos (F-006, F-037, F-057, F-135); listas de ficheros de `build_compras` + `15` (F-047, F-073, F-080) |

## Decisiones de diseño y desviaciones (justificadas)

1. **`fecha_hora_creacion`: 0 en CUALQUIERA de los dos campos -> `None`** (R10 «0 o imposible»).
   Medido en Sigrid (solo lectura, 2026-10-14): `crehor = 0` y `crefec = 0` en 0 de 46.245 filas,
   `crehor` máximo 235902: la elección no cambia ningún dato hoy. El SQL lo replica con
   `crehor BETWEEN 1 AND 235959` + minuto/segundo < 60 y `fn_sigrid_date`.
2. **La completa filtra también `c.tip IN (17 familias)`** (R11 decía «una fila por `raw.conala`
   con documento en `raw.con`»). Hoy es el mismo conjunto (la ingesta ya filtra); el `WHERE`
   repite el fallo CERRADO para que una ingesta manual sin filtro no publique alarmas de empleados.
3. **`liquidacion_creada_el` solo si el documento cierra** (NULL con marca NEGADA/DUDOSA/REMITE):
   con una alarma que niega al lado no hay fecha de liquidación que dar.
4. **`ultima_factura_cierra` es NULL si el contrato no tiene facturas** por la cadena (no FALSE):
   la ficha lo declara. `facturas_terminadas` y los cuatro `num_*` nunca son NULL (R18).
5. **`num_albaranes_liquidatorios` cuenta `es_liquidatoria`** de AC y PROF por la cadena de
   `lineas_alb` de la vista (cabecera o línea con contrato).
6. **`texto` = `NULLIF(a.tex, '')` y `tipo_alarma` = `NULLIF(btrim(x.res), '')`**: la puerta de
   F-006 (`test_f006_fichas`) exige que un NULL declarado sea posible; el texto sigue íntegro.
7. **«comparativos (veintidos)»** en la ficha de `documento_alarmas`: la heurística de
   `test_f006_stg_trampas` lee todo «22» como las 22 obras de `stg.fases`.
8. **`00_global.yaml` l. ~522** (entrada histórica de la v48 de F-090) se deja en «74»: es
   historia. «las 76 tablas» va en la entrada de la v52 y en `R-SIGRID-CON` (punto 1).
9. **Censo**: además de los cuatro que lista la spec, `test_f066_ingesta_raw.py` y
   `test_f074_ingesta_censo.py` fijan `TOTAL_TABLAS = 74`; subidos a 76 en T3.
10. **Orden de las listas**: `compras_restringida` va detrás de `tesoreria_restringida` y delante
    de `raw` en vetados (cronológico, como hizo F-037); en `ESQUEMAS_DEL_DATAMART`, alfabético.

## Verificación real

- **El SQL entero se ejecutó en un PostgreSQL 16 DESECHABLE** (`initdb` en el scratchpad, puerto
  54399, `en_US.UTF-8`; ninguna base real): `00_setup.sql` + `15` sobre tablas falsas de `raw` y
  `compras`, **dos veces seguidas** (idempotente). Resultado: `TODO OK 0`: las 15 filas de la
  completa, la general (sin 33/35; la 43 fuera), la marca de 9 documentos (NEGADA gana, carta,
  memo aparte, nota), los 4 contratos (cierre LIQUIDATORIA y CARTA, sin facturas, NEGADA) y las 3
  facturas posteriores, con sus días. **`fn_texto_normalizado` y `fn_clase_liquidacion` dan lo
  mismo que el oráculo Python en 46 textos** (acentos, `ß`, `ǅ`, combinantes, tabuladores,
  saltos de línea, `€`, `ª`) y `creada_el` en 8 parejas. La guarda de ingesta salta (`F-138
  R14: raw.conala no tiene ninguna alarma de factura...`) y la transacción se deshace: la general
  sigue con sus 13 filas. Script: `valida_f138.py` del scratchpad de la sesión (no versionado).
- Sigrid, solo lectura: recuento de `crehor`/`crefec` a 0 (arriba) y columnas de `conala`/`auxala`.
- Contra Azure: nada (ni lectura) en esta sesión.

## Fase RED (trazas reales)

**T1** · `python -m pytest tests/test_f138_dominio.py -q -p no:cacheprovider` con
`liquidatoria.py` reducido a un esqueleto (constantes vacías, funciones con `NotImplementedError`):
```
96 failed, 6 passed in 1.32s
     90 E   NotImplementedError
      1 E       assert None == 43
      1 E       assert () == (14, 15)
      1 E       AssertionError: assert {} == {1: 'INFORME'...A_VENTA', ...}
      1 E       AssertionError: assert 0 == 44
      1 E       AssertionError: assert () == ('NEGADA', 'L...SA', 'REMITE')
```
(los 6 que pasaban: «patrón válido» sobre la cadena vacía). Con el módulo: `102 passed in 0.20s`.

**T2** · `... tests/test_f138_ingesta_sql.py -k "r1 or r2 or r3"` con el YAML de `HEAD`:
```
E       KeyError: 'conala'
E       KeyError: 'auxala'
E       AssertionError: assert 74 == 76
7 failed in 0.57s
```
Con el YAML nuevo: 6 passed (el séptimo, «la 43 tampoco en el SQL», esperaba al SQL de T5).

**T4** · `... tests/test_f138_grants.py`:
```
E         - stringida,compras_restringida,raw
E         + stringida,raw
E       AssertionError: assert 'compras_restringida' in ('_meta', 'aux', 'cierre', 'compras', ...
E       AssertionError: assert 'CREATE SCHEMA IF NOT EXISTS compras_restringida;' in '\nCREATE SCHEMA ...
E           AssertionError: falta: GRANT USAGE ON SCHEMA compras_restringida TO sigrid_dm_restringido_ro;
10 failed, 3 passed, 8 warnings in 4.16s
```
(los 3 que pasaban: «no se veta al total» y dos de listas que ya cumplían). Después: 13 passed.

**T5** · `... -k "r10 or r11 or r12 or r13 or r14 or r20"` sin el fichero `15`: los 11 FAILED
visibles con `AssertionError: no encontrado: ...\sql\compras\15_alarmas_liquidatoria.sql` y
`assert 'CREATE SCHEMA IF NOT EXISTS compras_restringida;' in "-- .../00_setup.sql..."` (el
resumen lo cortó el `head -40`; ninguno pasaba). Después: 22 passed.

**T6** · `... -k "r15 or r16 or r9"`: `ValueError: substring not found` ×7 ->
`7 failed, 22 deselected in 0.71s`. Después: 29 passed en el fichero.

**T7** · `... -k "r17 or r18 or r19"`: `ValueError: substring not found` ×6 ->
`6 failed, 29 deselected in 0.74s`. Después: 35 passed.

**T8** · `... -k "r20 or r21"`:
```
E       AssertionError: assert ('documento_a...nto_adjuntos') == ('alarmas_liq...ento_alarmas')
E       AssertionError: assert '14_documento_adjuntos.sql' == '15_alarmas_liquidatoria.sql'
3 failed, 3 passed, 34 deselected, 30 warnings in 1.46s
```
(los 3 que pasaban: R21, la frontera, que se cumple desde antes). Después: 40 passed.

**T9-T11 (documentación)**: los tests de `test_f138_diccionario.py` se escribieron DESPUÉS de las
fichas; no hay traza RED propia. Sí la hubo de los tests de censo ajustados en T3 (rojos hasta
T9-T11: `ARCHITECTURE.md no dice «76 tablas»`, `azure-apps no dice «76 tablas»`) y de la puerta
de F-006 (cinco rojos reales sobre las fichas recién escritas, corregidos en T9: decisiones 6 y 7,
el recuento de `current.md` y la enmienda del diseño de F-006).

## Verificaciones MANUAL pendientes (T14-T16, tras el APROBADO y el merge)

En `progress/current.md`, con su comando exacto y en orden: comprobar el job y la imagen;
`02_roles.sql` (humano) ANTES del build; ingesta de `conala` y `auxala`; `build-compras` y
`apply-grants`; `check-raw-recuentos` y R28-R29 por SQL de solo lectura; `publicar-diccionario`
(v52) y los tres `check-*`; lista blanca y reinicio de `mcp-bbdd` y las preguntas de R31; la
primera nocturna (`timings`). **Ninguna se ha ejecutado.**

## Fuera del alcance / lo que falta

- R28-R31 (recuentos en Azure, permisos reales, preguntas al MCP, coste nocturno): MANUAL.
- La regla es heurística sobre texto libre; los casos raros van en la ficha, no en código.
- `mcp-bbdd` debe añadir `compras_restringida` a su lista blanca: otro repositorio.

## Evidencias

Medidas el 2026-10-15 (hora local de la máquina).

| Evidencia | Resultado real |
|---|---|
| `bash harness/init.sh` (sobre `6183ba7`, código final, y de nuevo sobre `7244084`, con los informes) | **ENTORNO LISTO** (salida 0) las dos veces: 8.065 passed, 249 skipped; la segunda en 1.002 s |
| Tests ejecutados (suite completa, dentro de `init.sh`) | **8.065 passed, 249 skipped, 0 failed** |
| Tiempo de la suite | **1.244 s (20 min 44 s)** con medición de cobertura |
| Tests de la feature | `test_f138_{dominio,ingesta_sql,grants,diccionario}.py`: 102 + 40 + 13 + 22 = **177 passed** |
| Cobertura de líneas cambiadas | **PUERTA COBERTURA: 100,0 % de 66 líneas (66/66)**, umbral 80 %, nivel estándar |
| Tamaño | requirements 150/150, design 190/250, impl dentro de 220 |
| Mutación (`domain/liquidatoria.py`, muestreada 20 de 37, semilla 20260820) | **17 muertos, 3 supervivientes, 0 timeouts, 0 sin veredicto**, 5.598 s con 2 workers (`--timeout 2400`, línea base 585-588 s por worktree). Los 3 supervivientes son **EQUIVALENTES** y están analizados en `progress/mutacion_F-138.md`: la guarda `crefec < 0 or crehor < 0` es redundante con `not crefec`/`not crehor` y con el `ValueError` de `datetime()` sobre un componente negativo |

**La campaña cazó dos fallos reales antes de evaluar nada.** Primer intento (4 workers): la
línea base no cupo en 600 s (contención). Segundo: el árbol tenía `current.md` sin commitear. Tercero:
**LÍNEA BASE EN ROJO** con dos tests que mi cambio había roto y que no estaban en mis ejecuciones
parciales: `test_f025_contrato_cliente` (el doble `_Pg` de `test_f138_ingesta_sql.py` nombraba
`ruta`/`esquema` donde el cliente real dice `path`/`schema`) y `test_f079_stg_consultable` r3 (el
inventario de funciones desaconsejadas no tenía `fn_texto_normalizado` ni `fn_clase_liquidacion`).
Corregidos en `6183ba7`; `init.sh` en verde después, y la cuarta campaña, válida.

**Comandos**: `python -m harness.mutacion --feature F-138 --ficheros etl_sigrid/domain/liquidatoria.py --workers 2 --timeout 2400`
(lanzada desacoplada de la sesión con `SetThreadExecutionState`, como F-037);
`bash harness/init.sh`.
