# F-102 · Informe del implementer (2026-09-23)

HOTFIX 2: la obra y el recurso son de UNA empresa. Spec APROBADA en
`specs/F-102-obra-duplicada-empresa-28/`; decisiones del humano en
`progress/spec_F-102.md`. Rama `hotfix/F-102-obra-duplicada-empresa-28` (arbol
principal), rigor `estandar`. T1-T15 y T17 hechas, un commit por tarea; **T16
es MANUAL del humano** (tras la primera nocturna). `azure-apps`: commits
locales `511ffff` y `4a14173`, **sin push**.

## Que cambio

| Fichero | Cambio |
|---|---|
| `sql/maestro/00_setup.sql` | Vista nueva `maestro.v_obra_fichas` (desviacion 1): una fila por ficha, `clave_obra` = `emp::text-cod`, ranking empresa 1 -> `conext` 15 -> cierres -> `tiemod` -> `ide` DESC, `es_ficha_principal` y `obra_principal_id` de la MISMA ventana |
| `sql/maestro/01_obras.sql` | Seis columnas al final (`empresa_id`, `nombre_empresa`, `clave_obra`, `num_fichas_codigo`, `es_ficha_principal`, `obra_principal_id`) leidas de la vista; lateral a `raw.auxemp`; cabecera, ejemplos y `COMMENT` sin «un tercio» |
| `sql/compras/03_views.sql`, `06_pago_factura.sql` | `empresa_id` y `clave_obra` al final de las cinco vistas de consumo, por `LEFT JOIN maestro.v_obra_fichas`; ninguna publica `obra_principal_id` |
| `sql/personal/00_setup.sql`, `01_recursos.sql` | `empresa_id`, `nombre_empresa`, `clave_recurso` al final: `ADD COLUMN IF NOT EXISTS` x3 (sin DROP), y en el `CREATE TABLE` detras de `_built_at`; lateral a `auxemp` DETRAS del de `raw.emp`; sin `WHERE` |
| `config/tables_sigrid.yaml` | `auxemp` (refresco completo, sin filtro): 69 tablas |
| `config/diccionario/*.yaml` | `raw.auxemp`; `maestro.obras` (modelo, seis columnas, direccion sobre la ficha de Ruesma, `condir`, 103 de la 28, codigos administrativos); ficha nueva `maestro.v_obra_fichas`; cinco vistas de `compras` (dos columnas, relacion por clave, aviso de «mezcla empresas»); texto de R23 en `contratos`, `albaran_lineas`, `factura_lineas`, `fact_compras_linea`, `retenciones.movimientos`, `v_pbi_retencion_obra`, `proveedores_obra`, `centros_coste`; `stg.obras`; `personal.recursos`; regla `R-CODIGO-POR-EMPRESA`; `R-UNIVERSO-OBRA`; `auxemp.res` en `R-SIGRID-CON`; `version` 28 -> **29** |
| `docs/ARCHITECTURE.md` | Bullet del modelo en «Semantica Sigrid»; 69 tablas |
| `specs/F-006-mcp-azure/design_detalle.md` | Enmienda de inventario: **163 objetos, 1.083 columnas**, 72 de consumo recomendadas (lo exige `test_f006_r24_...`) |
| `tests/test_f102_obra_principal.py` | 118 tests nuevos (R1-R10, R13-R29) |
| Tests de otras features | `TOTAL_TABLAS` 68 -> 69 (F-066, F-074); `test_f080_ingesta` (el censo es `TOTAL_TABLAS >= 68`); `test_f080_diccionario` (la lista de columnas de `v_control_forma_pago` gana las dos). Ninguno pierde lo que vigila |

**No se toca** (comprobado): `sql/stg/03_obras.sql` (test por hash, R7), todo
`stg`, `mart`, `cierre`, las tablas de `compras` (`01`, `02`, `05`, `07`), el
SQL de `retenciones`, `maestro/03_*`, `04_*`, `personal/02_*` y ningun step:
`git diff main --stat -- sql/stg sql/retenciones etl_sigrid/application/steps`
sale vacio. `facturas` y `mcp-bbdd` no se tocan (D4).

## Desviaciones respecto a la spec (justificadas; tambien en `current.md`)

1. **`maestro.v_obra_fichas` vive en `maestro/00_setup.sql`, no en
   `01_obras.sql`.** `tests/test_f073_sql.py` lee las columnas de
   `maestro.obras` del PRIMER `CREATE OR REPLACE VIEW` de `01_obras.sql`
   (`test_f073_r18_las_columnas_de_siempre_van_primero...`): una vista antepuesta
   ahi rompe ese guarda, y T5 exige `test_f073_sql.py` en verde. `00_setup.sql`
   corre antes en el mismo paso, lee solo `raw` y no se dropea: cumple lo que el
   diseno pedia. Sin tocar el step (su docstring sigue diciendo «schema + helper
   de fecha»: tocarlo romperia el `git diff ... steps` vacio de T12).
2. **`num_cierres` agrega `raw.obrfas` por `obride` y une**, en vez de la
   subconsulta correlacionada del diseno. Mismo valor; medido con `EXPLAIN
   ANALYZE` en solo lectura: **22 ms frente a 529 ms**, y la vista la evaluan
   las cinco vistas de `compras` en cada consulta.
3. **`v_pbi_proveedor_obra` (y `v_pbi_partida_coste`) unen la vista de fichas
   ANTES de agregar** y agrupan tambien por `empresa_id`, `clave_obra`, no
   «sobre el resultado ya agregado» (R21). La puerta de F-006
   `test_f006_r2_control_el_group_by_se_lee_donde_se_puede_leer` exige leer su
   `GROUP BY` en el nivel 0; con el agregado en subconsulta deja de leerlo. El
   grano no cambia: la vista de fichas tiene una fila por `obra_id` y las dos
   columnas dependen solo de el (mismas filas medidas, abajo).
4. **La relacion `clave_obra -> maestro.obras.clave_obra` se declara `N:N`**, no
   `N:1` (R22), y su `porque` dice «DE HECHO ES N:1» (922 para 922). El
   validador R5 de F-006 (`_es_unica_por`) solo admite el lado «1» sobre la
   clave de negocio entera o una `clave_sustituta`; la de `maestro.obras` es
   `obra_id`. Marcar `clave_obra` como sustituta seria falso (no es BIGSERIAL y
   `check-unicidad` la daria por garantizada); cambiar la clave de negocio de
   `maestro.obras` romperia todas las relaciones N:1 a su `obra_id`. **Decision
   que conviene revisar**: si se quiere N:1 formal, hace falta que el validador
   admita claves alternativas (cambio de F-006, fuera de este hotfix).
5. **`maestro.v_obra_fichas` va con `consumo_recomendado: true`**, no «no
   recomendada» (design §3). F-079 (decision del humano) reserva el `false` a lo
   roto, vacio o de instrumentacion, nunca a una preferencia de enrutado, y
   `test_f079_r3_el_inventario_de_lo_que_no_se_toca_esta_completo` lo exige. La
   vista es correcta y consultable; su descripcion manda a `maestro.obras` para
   el contexto de una obra. Diccionario: **163 objetos, 1.083 columnas, 72 de
   consumo** recomendadas.
6. **`check-unicidad` NO vigila `clave_obra` ni `clave_recurso`** (declarada en
   la review, pasada 1). La spec prometia «un test lo vigila por la
   construccion y `check-unicidad` en la base» (`design.md` §6), pero
   `check-unicidad` sale de la `clave_negocio` de cada ficha
   (`unicidad_sql.consultas_de_unicidad`), que sigue en `[obra_id]` /
   `[recurso_id]`. Hoy las vigilan el test de su construccion (R6, R26) y, en la
   base, **solo** las consultas `count(DISTINCT ...)` de T16 (M1 y M6 en
   `current.md`). La vigilancia permanente NO se implementa: la decide el
   humano (indice unico en `personal.recursos (clave_recurso)`, o claves
   alternativas en el validador de F-006, que resolveria tambien la 4).

Ademas, las cifras de direccion de F-073 (33,1 %...) se conservan en las fichas
como HISTORIA («contando las 921 fichas... salia el 33,1 %: mezclaba las copias»),
porque `test_f073_r12_*` las exige y son ciertas para lo que midieron.

## Fase RED (trazas reales)

**T1** — tests escritos antes que el SQL y las fichas:

```
$ python -m pytest tests/test_f102_obra_principal.py -q -p no:cacheprovider --tb=line
E   AssertionError: 00_setup.sql no crea la vista maestro.v_obra_fichas
E   AssertionError: las de antes en su orden, y las seis nuevas DETRAS: el replace solo admite columnas al final (R8)
E   AssertionError: LEFT JOIN por obra_id: no se pierde ninguna de las 922 fichas (R9)
E   AssertionError: auxemp declarada una vez (R13)
E   AssertionError: compras.v_pbi_proveedor_obra: LEFT JOIN por obra_id, NULL si no hay obra (R21)
E   AssertionError: compras.v_control_forma_pago: empresa_id y clave_obra al final y en ese orden (R21)
E   AssertionError: stg.obras no dice «0581» (R18)
E   AssertionError: R-UNIVERSO-OBRA no dice «0581» (R18)
E   assert 'un tercio' not in 'vista consu... seguimiento'
E   AssertionError: ARCHITECTURE.md no dice «clave_obra» (R28)
86 failed, 19 passed in 1.87s
```

Los 19 que pasaban en RED son los guardas de «lo que NO cambia» (hash de
`stg/03_obras.sql`, SQL que no pueden nombrar `v_obra_fichas`, `depends_on` de
los siete pasos, ningun SQL de `compras` con `obra_principal_id`): vigilan un
invariante que ya se cumplia, y se cumplen antes y despues por diseno.

**T15** — `personal.recursos`, tests antes que el SQL:

```
$ python -m pytest tests/test_f102_obra_principal.py -q -p no:cacheprovider -k "r26 or r27 or recoge_personal" --tb=line
E   AssertionError: personal.recursos gana empresa_id con ADD COLUMN IF NOT EXISTS (R26)
E   AssertionError: personal.recursos gana clave_recurso con ADD COLUMN IF NOT EXISTS (R26)
E   AssertionError: en una base nueva nacen al final, igual que las anade el ALTER (R26)
E   AssertionError: auxemp por lateral con ORDER BY + LIMIT 1 (R26)
E   AssertionError: empresa_id sin ficha (R27)
E   AssertionError: la ficha no dice «`MO/0009`» (R27)
E   AssertionError: R29
10 failed, 1 passed, 107 deselected in 0.26s
```

(El que pasaba es el veto de D5: «no se publica marca de misma persona».)
Despues de cada tarea, su verificacion en verde; al final, **118 passed**.

## Verificaciones en SOLO LECTURA (sesion `default_transaction_read_only=on`)

Scripts en el scratchpad de la sesion, fuera del repositorio. `raw` aun no
tiene `auxemp` (la crea la ingesta), asi que donde hace falta se simula con un
`VALUES` de dos filas: el nombre de la empresa NO esta verificado contra base.

- **T3 (R11, R12)**: el cuerpo de `v_obra_fichas` como consulta da **922
  fichas / 922 `clave_obra` / 846 principales / 846 codigos**; 0 codigos con dos
  principales; difiere de `stg.obras` **exactamente en 0581, 0606, 0671 y
  0720**; cuatro digitos `>= '0672'`: **57 principales, todas de la empresa 1,
  48 con `dir1`**; 310 de 846 principales con `dir1`; 103 fichas de la 28 con 0
  `dir1` y 0 cliente; 59 fichas apuntan a otra, 11 de codigos administrativos
  (CM 1, CP 4, GG 4, POSTV2 1, VAR 1); `raw.condir` x `raw.obr` = 0. Todo casa
  con `design.md` §1.
- **T5**: el cuerpo de `maestro.obras` da 922 filas, 922 `obra_id`, 922
  `clave_obra`, 846 principales (grano intacto).
- **T6**: el cuerpo nuevo de cada vista de `compras` da las MISMAS filas que la
  vista publicada hoy: 19.024 / 45.185 / 120.415 / 118.415 / 81.665; 0 filas
  con obra y sin clave, 0 con clave y sin obra; de otra empresa, 495 / **1.880**
  (la cifra de T16) / 2.946 / 3.554 / 1.774.
- **T15**: el cuerpo de `personal.recursos` da 2.618 filas, 2.618 `recurso_id`,
  **2.618 `clave_recurso`**, 2.504 codigos, 119 recursos de fuera de la 1;
  clave mas larga 21 caracteres (la columna es `VARCHAR(40)`).
- Direccion sobre las 846 principales (2026-09-23), la que publican las fichas:
  `dir1` 310, `dir2` 46, CP 307, `dir` 276, municipio 298, provincia 309.

## Riesgos y lo que falta (para el humano)

- **T16 MANUAL, tras la primera nocturna con la imagen nueva** (y reiniciar el
  MCP por su cache): las consultas de `tasks.md` T16 y `python main.py
  check-unicidad`, `check-relaciones`, `check-declarados` sin errores nuevos
  (`check-unicidad` no mira las claves nuevas: desviacion 6). Lista completa,
  con comando y resultado esperado, en `progress/current.md` (M1-M9).
  Esperado: 922/922; 0 filas; 0581, 0606, 0671, 0720; 1/57/48; 1.880/0;
  2.618/2.618. **Despues, `publicar-diccionario` (version 29)**: escritura
  contra Azure, solo el humano.
- **Orden de despliegue**: `maestro.obras` y `personal.recursos` leen
  `raw.auxemp`, que crea `ingest_raw`. La nocturna ingiere antes de construir;
  un `build-maestros` o `build-personal` a mano ANTES de la primera ingesta con
  esta version falla por `raw.auxemp` inexistente.
- **Primera noche**: las vistas de `compras` leen `maestro.v_obra_fichas`;
  `build_compras` no depende de `build_maestros` (R24, patron de F-094). Si esa
  primera noche `build_maestros` se salta (falla `build_stg`) la vista aun no
  existe y `03_views.sql` falla; a partir de la segunda, la vista persiste.
- `v_obra_fichas` NO la usa `stg.obras`: hasta F-106, en 0581, 0606, 0671 y 0720
  el `obra_id` de `mart`/`cierre` no es el de `es_ficha_principal` (declarado).
- Push de `azure-apps` y de esta rama: del humano.
- **Fuera de alcance**: seguimiento por empresa y las obras de Porsan en
  `stg.obras` (F-106); marca de misma persona (D5); aviso a `facturas` (D4).

## Evidencias

- **`bash harness/init.sh`** tal cual, en el arbol principal: **ENTORNO LISTO** (exit 0). `[OK] pytest en verde`, `[OK] PUERTA COBERTURA`, `[OK] PUERTA TAMAÑO` (impl 173/220 en esa pasada), `[OK] Rama actual`; unico aviso, ruff 232 (deuda previa). Hubo dos pasadas en rojo antes: (1) `test_f015_r4_ejecutar_git_de_verdad...` en una suite de 4 h 43 min con la maquina saturada (una llamada a git devolvio vacio; el test pasa solo en 0,9 s y en la pasada verde), y (2) `test_f079_r3_el_inventario_de_lo_que_no_se_toca_esta_completo`, arreglada con la desviacion 5; antes, `test_f006_los_recuentos_de_current_son_los_de_hoy` pidio los recuentos en `current.md`
- **Tests**: **5.246 passed, 191 skipped, 0 failed**; `tests/test_f102_obra_principal.py`: **118 passed**.
- **Tiempo de la suite**: **850,82 s (14 min 11 s)**, el que imprime pytest dentro de `init.sh`.
- **Cobertura de lineas cambiadas**: **94,7 %** (968/1022, umbral 80 %). `init.sh` la mide contra
  `dev`, que va por detras de `main`: la cifra incluye lineas de otras
  features; F-102 no cambia ninguna linea de produccion Python.
- **Mutacion**: `python -m harness.mutacion --feature F-102 --base main` ->
  **ALCANCE VACIO**: «0 fichero(s), 0 linea(s) de produccion». F-102 no toca
  codigo Python de produccion (solo SQL, YAML, docs y tests), asi que no hay
  mutantes y la herramienta no escribe `progress/mutacion_F-102.md`. Evidencia
  sustitutiva: (a) los 118 tests sobre el texto del SQL y las fichas, con fase
  RED arriba; (b) las verificaciones en solo lectura de cada cuerpo nuevo
  contra la base (mismas filas, claves unicas); (c) los guardas de otras
  features que siguen en verde (F-006, F-057, F-073, F-080, F-101).
- **Lo que no se ha verificado aqui**: que los SQL corran como DDL contra una
  base (crear vistas escribe en el Postgres compartido: T16, del humano) y el
  nombre de empresa leido de `raw.auxemp` real.
