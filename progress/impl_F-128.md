<!-- progress/impl_F-128.md -->
# F-128 · Informe del implementer: la cabecera entera de factura y albarán

Spec: `specs/F-128-importes-cabecera-factura/` (D1-A, D2-B, D3-A, D4-B, D5-A, humano 2026-10-17).
Rama `feature/F-128-importes-cabecera-factura`, `main` fusionado antes de empezar (`3c55cf9`:
F-139, F-141, F-144, diccionario v55; conflictos de `features.json`/`BACKLOG.md` resueltos
conservando F-143 y F-144). Rigor `estandar`. Solo lecturas contra Azure y Sigrid (columnas de
`dcf`/`dca` y su cobertura, ver «Decisiones»). Sin push, sin publicar el diccionario, sin desplegar.

## Qué cambió

| Fichero | Cambio |
|---|---|
| `etl_sigrid/domain/cabecera_compra.py` (nuevo) | Oráculo: `CLASES_RECARGO`, `clase_recargo`, `es_retencion_garantia` (D2-B, UN parámetro), `es_retencion_fiscal`, `MOTIVOS`, `INVENTARIO_DCF`/`INVENTARIO_DCA` (145 + 145 columnas de Sigrid), `publicadas`, `columnas_origen`, `errores_inventario` |
| `sql/compras/00_setup.sql` | `compras.fn_clase_recargo(INT)`, `compras.fn_es_retencion_garantia(INT)` con `COMMENT` (nombra `RETESP`) |
| `sql/compras/01_documentos.sql` | Bloque «F-128» en la cabecera; sección RECARGOS (`factura_recargos`, `albaran_recargos`, PK e índices) antes de ALBARANES; +34 columnas AL FINAL de `albaranes`; +27 AL FINAL de `facturas` (joins tras el lateral del estado); última sección entre marcas `>>> / <<< F-128 CUENTA BANCARIA`: `compras_restringida.documento_cuenta_bancaria` |
| `sql/retenciones/00_setup.sql` | `retenciones.fn_es_retencion_garantia`, copia deliberada (R19) |
| `sql/retenciones/07_cuadre_factura.sql` (nuevo) | `retenciones.retencion_factura` (tabla) y `retenciones.v_cuadre_factura_obra` (vista) |
| `build_retenciones_step.py`, `build_compras_step.py`, `main.py` | Sub-paso `cuadre_factura` el último; docstring y comentarios |
| `config/diccionario/*.yaml` | v56 + historia; fichas de las 61 columnas nuevas, de lo NO publicado por motivo, de los 8 objetos nuevos; `R-COMPRAS-RESTRINGIDA` (+ párrafo, mismo `ambito`) y `R-EMPRESA-POR-DEFECTO` (objetos nuevos en sus listas) |
| `docs/ARCHITECTURE.md`, `CLAUDE.md` | Semántica `totdoc`/`tot`/`totpag`, `reccla`, `RETESP`; `compras_restringida` guarda alarmas y cuentas; mapa |
| `azure-apps/datamart_seg_anual.md` | Lo expuesto (filas en «Qué expone» y sección propia), commit local `0865adb` en `azure-apps` |
| `tests/test_f128_{dominio,sql,restringida,diccionario}.py` (nuevos) | R1-R34 |
| `tests/test_f047_steps.py`, `test_f095_…`, `test_f110_…`, `test_f079_…`, `test_f073_sql.py` | Ajustes mecánicos (ver Desviaciones) |

Commits: `7d4f734` T1 · `b99fae3` T2 · `79f6947` T3 · `1a584ae` T4 · `390fe9e` T5 · `e0f80f0` T6 ·
`6450dab` T7 · `65d0f4c` T8 · `19696b9`+`348a031` T9 · `4125147` T10 · `0cd0543` T11 · `c5b48be` T12 ·
`486a64a` T13 · `0fa7305` (hash de F-073) · `109abce` T14.

## Decisiones de diseño y desviaciones (justificadas)

1. **`diremp2`/`diremp3` como RESIDUAL.** El informe §5 no las clasificaba y R3 exige una entrada
   por columna. Medido el 2026-10-18 en `raw` (solo lectura): líneas 2-3 de la dirección del
   documento, 1,3/1,0 % en `dcf` y 1,5/1,7 % en `dca`. No se publican (como `dirdir*`); la nota
   lo dice. Las 145 columnas de cada tabla se leyeron de `INFORMATION_SCHEMA.COLUMNS` de Sigrid
   por `sigrid-api` y contrastadas con `information_schema` de `raw` (Azure, sin bootstrap).
2. **Alias `cpt` (concepto) y `dcon` en vez de `x` y `c`.** El guardián de nulos de F-006
   (`_alias_directos_de_raw`) es por fichero: `x` y `c` son `JOIN raw.con` inner en otros bloques
   de `01_documentos.sql` y acusaba a `codigo_concepto` y `codigo_documento` (que llegan por LEFT).
3. **Garantía en el cuadre = Σ `cuo::NUMERIC(18,2)`** (cada cuota redondeada), igual que
   `compras.factura_recargos.cuota`, para que `retencion_factura` = `importe_retencion_garantia`.
4. **Sin relación de una ficha general hacia `compras_restringida`**: la de R30 sale DESDE la
   tabla restringida hacia `facturas`/`albaranes` (lo fija un test). Una relación en sentido
   contrario invitaría al estándar a una consulta que acaba en «permission denied».
5. **`R-EMPRESA-POR-DEFECTO`** (F-144): `retencion_factura` y `v_cuadre_factura_obra` a la lista
   con empresa (la de la obra de CABECERA); `factura_recargos`, `albaran_recargos` y
   `documento_cuenta_bancaria` a la de sin empresa. Y una frase nueva: `facturas`/`albaranes`
   llevan ahora `obra_cabecera_id`, cuya empresa es la de la OBRA, no la del documento (`empide`,
   F-134); contar documentos por empresa sigue sin camino comprobado y, si el usuario acepta la
   aproximación, se dice. **Punto para el reviewer/humano**: es texto nuevo de la regla.
6. **`v_cuadre_factura_obra`** publica además `empresa_id`, `codigo_obra`, `clave_obra` y
   `nombre_obra` («nombres del lado que exista», R18), como `saldo_contable`.
7. **R31 robusto al merge**: antes del merge exige versión ≥ `main` + 1; si `main` ya lleva la
   entrada «(F-128, » basta con no bajar de la de `main`. Es la lección de F-141/F-144 (el «+1» a
   secas puso `main` en rojo al fusionar).
8. **Tests ajenos tocados que el design §3 no listaba**, todos mecánicos: `test_f095` (lista de
   ficheros, y la de recuentos + `rows_processed` 15→18), `test_f047_steps` y `test_f110` (el
   sub-paso nuevo), `test_f079_stg_consultable` (las 3 funciones nuevas en su inventario de
   funciones) y `test_f073_sql` (hash de `01_documentos.sql` recalculado, con su nota, como
   hicieron F-084 y F-067).
9. El test de R22 que mira la vista nueva se movió a `test_f128_sql.py`
   (`test_f128_r18_r22_la_vista_lee_solo_retenciones`) para que T7 cerrase en verde.
10. El bloque de `ARCHITECTURE.md` entró en el commit de T11 (no en el de T12).
11. Tras la campaña de mutación se cambiaron tres `−` por `-` en textos del dominio (aviso
    RUF001 de ruff); no toca lógica.

**Guardas de F-141 que cubren la tabla nueva** (pedido del líder): `compras_restringida` está en
`PG_VETOED_SCHEMAS` y `PG_RESTRICTED_SCHEMAS`, fuera de `PG_TOTAL_VETOED_SCHEMAS` y de
`PG_PERFIL_RESTRINGIDO_SCHEMAS`; `esquemas_ajenos` la da por ajena al perfil restringido;
ningún objeto nuevo casa con `PATRON_VIGILADO_RESTRINGIDO` (`mayor`); la única vista nueva lee
solo `retenciones`, así que `filtraciones_restringido` no la ve como filtración. Ni `grants.py`
ni `settings.py` ni `02_roles.sql` cambian (test R22 contra `main...HEAD`).

## Qué quedó fuera (por la spec)

`empide`/`hor` (F-134), el desajuste cabecera-línea (F-093), `dca.pagfor`/`pagtex` (D3-A), los
catálogos `auxeio`, `alm`, `auxobrcoc` (F-143) y `auxcueban`, `bantipide` y `dca.banide`.

## Verificaciones MANUAL pendientes (humano, tras review y merge)

- **T16** (R35): imagen y job, o `python main.py build-compras`, `build-retenciones` y
  `apply-grants`; inventario contra `information_schema` (design §11.2); recuentos = `raw`;
  0 facturas con `importe_retenciones` ≠ fiscal + garantía; categorías del orden del informe §4;
  `documento_cuenta_bancaria` ≈ 35.460 filas; «permission denied» del login estándar y del
  restringido en ella; `apply_grants` ok; `python main.py check-diccionario`.
- **T17** (R36): `python main.py publicar-diccionario` (v56), reinicio del MCP y las dos preguntas
  por el conector. `mcp-bbdd` no necesita cambios (ya lista `compras_restringida`).
- No se ha ejecutado ningún SQL nuevo contra una base: solo tests de texto (Postgres compartido).

## Fase RED (trazas reales, recortadas; todas con el comando exacto)

```
T1  python -m pytest tests/test_f128_dominio.py -q
E   ImportError: cannot import name 'cabecera_compra' from 'etl_sigrid.domain'
1 error in 0.45s
T2  python -m pytest tests/test_f128_sql.py -q -k r14
E       AssertionError: no está la función compras.fn_clase_recargo
E       AssertionError: no está la función compras.fn_es_retencion_garantia
T3  python -m pytest tests/test_f128_sql.py -q -k "r12 or r13"
E       AssertionError: no está CREATE TABLE compras.factura_recargos
E       AssertionError: no está CREATE TABLE compras.albaran_recargos
E       AssertionError: assert 'F-128' in '-- etl_sigrid/infrastructure/postgres/sql/compras/01_documentos.sql ...
T4  python -m pytest tests/test_f128_sql.py -q -k "r6 or r7 or r8 or r10 or r11"
4 failed, 2 passed, 9 deselected in 0.43s
E       AssertionError: no está la columna importe_bruto
FAILED tests/test_f128_sql.py::test_f128_r10_albaranes_prefijo_intacto_y_nuevas_en_orden
T5  python -m pytest tests/test_f128_sql.py -q -k "r5 or r9 or r3 or r32 or facturas"
FAILED tests/test_f128_sql.py::test_f128_r5_facturas_prefijo_intacto_y_nuevas_en_orden
FAILED tests/test_f128_sql.py::test_f128_r9_facturas_grano_y_joins_tras_el_lateral
FAILED tests/test_f128_sql.py::test_f128_r3_inventario_igual_al_sql[dcf-compras.facturas-...]
5 failed, 4 passed, 15 deselected in 0.49s
T6  python -m pytest tests/test_f128_restringida.py -q -k "r20 or r21"
E       AssertionError: faltan las marcas de la sección
FAILED tests/test_f128_restringida.py::test_f128_r20_columnas_en_orden
FAILED tests/test_f128_restringida.py::test_f128_r20_es_la_ultima_seccion_del_fichero
T7  python -m pytest tests/test_f128_restringida.py tests/test_f138_grants.py -q
FAILED tests/test_f128_restringida.py::test_f128_r23_positivo_fabricado   (regex mal escrita: se corrigió)
2 failed, 33 passed, 8 warnings in 1.35s
T8  python -m pytest tests/test_f128_sql.py -q -k "r15 or r16 or r17 or r18 or r19"
FAILED tests/test_f128_sql.py::test_f128_r19_funcion_copiada_de_compras
FAILED tests/test_f128_sql.py::test_f128_r15_retencion_factura_columnas - FileNotFoundError
9 failed, 24 deselected in 0.53s
T9  python -m pytest tests/test_f128_sql.py -q -k r24
E       AssertionError: assert ('views_conta...', None, None) == ('cuadre_fact...cion_factura')
2 failed, 1 passed, 33 deselected in 1.46s
T11 (con `git stash` del diccionario) python -m pytest tests/test_f128_diccionario.py -q
36 failed, 2 passed in 5.77s
T12 (CLAUDE.md y ARCHITECTURE.md de antes) python -m pytest tests/test_f128_diccionario.py -q -k r34
2 failed, 38 deselected in 0.49s
```
En verde tras cada tarea con el mismo comando (p. ej. T5: `108 passed` con F-083/F-084/F-067;
T8: `55 passed`; T11: los 41 ficheros de tests de diccionario, `5360 passed, 253 skipped`).
T10 (R33) y T13 son guardas de «no cambia»: llevan positivo fabricado en vez de RED.

## Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-128 | `135 passed in 36.85s` (los cuatro `tests/test_f128_*.py`) |
| Suite completa (`bash harness/init.sh`) | `bash harness/init.sh` en VERDE el 2026-10-19 («ENTORNO LISTO»): **8437 passed, 254 skipped**, 0 failed; ruff 276 avisos (deuda previa, no bloquea) |
| Cobertura de las líneas cambiadas | **100,0 %** de 66 líneas cambiadas (66/66, umbral 80 %, línea `PUERTA COBERTURA`) |
| Mutación (`progress/mutacion_F-128.md`) | Pasada 2, sobre HEAD `546885a`: 22 generados, 20 evaluados (muestreo estándar, semilla 20260820), **20 muertos, 0 supervivientes**. Base 33,2 s y 20 mutantes 19,3 s (~1 s cada uno), con la MISMA suite acotada (los 4 importadores del módulo) en base y mutantes; la pasada 1 había medido la base sobre la suite entera |
| Tiempo de la suite | 1225,85 s (20 min 25 s) con medición de cobertura, según la propia suite |

## Pasada 2 (CHANGES_REQUESTED de `progress/review_F-128.md`, corregido)

1. `R-EMPRESA-POR-DEFECTO` ya no dice que la empresa del documento «es `empide`» (en `dcf`/`dca`
   `empide` es «Empleado», índice a `emp`; qué es, F-134): queda «no la del documento». Test nuevo
   `test_f128_r_empresa_no_atribuye_a_empide_la_empresa`, RED antes del cambio
   (`python -m pytest tests/test_f128_diccionario.py -q -k empide` → `1 failed`,
   `AssertionError: assert 'empide' not in 'Es un CRITE...VERSO-OBRA`.'`), verde después. `3382803`.
2. La misma regla distingue: `retencion_factura`, la empresa de la obra de CABECERA;
   `v_cuadre_factura_obra`, la de la obra del par (cabecera de sus facturas o, en los pares solo
   contables, la cascada de `retenciones.saldo_contable`), como dice su ficha. `546885a`.
3. Mutación repetida sobre HEAD `546885a` con la MISMA suite acotada en base y mutantes (subclase
   de `EjecutorPytest` en el script, sin tocar `harness/mutacion.py`; invocación exacta en
   `progress/mutacion_F-128.md`): base 33,2 s, 20 mutantes en 19,3 s, **20/20 muertos**. `1e697dd`.

`bash harness/init.sh` tras la pasada 2: **ENTORNO LISTO**, 8438 passed, 254 skipped en 1182,09 s;
PUERTA COBERTURA 100,0 % (66/66); PUERTA TAMAÑO dentro de los topes.
