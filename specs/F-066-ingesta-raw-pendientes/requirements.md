<!-- specs/F-066-ingesta-raw-pendientes/requirements.md -->
# F-066 · Ingerir de Sigrid los raw que faltan — Requisitos (EARS)

Rigor **crítico**: fase RED, cobertura, campaña de mutación completa y cero
supervivientes sobre el Python nuevo. Alcance: **solo `raw`**; `stg` y `mart`
son F-057, F-056, F-055 y F-067. Ampliada el 2026-09-06 (10:40 UTC) con los
raw del seguimiento de COMPRAS por el MCP. Toda cifra de Sigrid se **midió el
2026-09-06** por `sigrid-api` en solo lectura (`design.md` §1).

## A · Alta de tablas (`config/tables_sigrid.yaml`)

- **R1.** El sistema debe declarar las **25** tablas nuevas de `design.md`
  §1 (grupos A personal, B contabilidad, C compras/proveedor), cada una con
  `source_table == target_table` en minúsculas, `id_column: ide` y
  `incremental_column` a `tiemod` solo si la tabla tiene esa columna
  (`auxpronat`, `auxpag`, `auxefp`); `null` en las demás.
- **R2.** El sistema debe ingerir `apu` **entera** (2.154.543 filas), sin
  `where` y con la recarga completa de la nocturna: no tiene `tiemod`, y
  partir por empresa o ejercicio ahorra ≤ 15 % (DA-1).
- **R3.** SI una tabla candidata tiene **0 filas** en Sigrid —`PFfir`,
  `logfirdoc`, `auxfam`, `act`, `auxacttip`, `actent`, `actseg`,
  `comlinpar`, `ctrrevpre`, `ctrproact`, `dcfproimp`, `verhis`, `auxtarprv`,
  `auxsec`, `confam`, `entfam`, `prvres`, `prvcalsel`, `rqs`—, ENTONCES el
  sistema **no** debe darla de alta; un test fija esa lista como constante y
  comprueba que ninguna está en el YAML (reabrirla = cambiar la constante).
- **R4.** El sistema no debe añadir nada para `con`: `raw.con` ya trae las
  44.778 filas `tip = 16` de 38 empresas con `emp`, `fec`, `cod`, `res`,
  `est` y `fecbaj`. Un test fija que `con`, `com`, `comlin`, `comprv`,
  `ctr`, `ctrpro` y `pag` siguen declaradas sin `where` nuevo.
- **R5.** CUANDO se ingiera `emp`, el sistema debe traerla **entera salvo
  las 11 exclusiones técnicas** de `design.md` §3 (`ima` binaria y diez
  columnas de texto ilimitado). **Ninguna columna se excluye por ser dato
  personal** (decisión del humano, 2026-09-06): `dni`, `tarseg`, bancarias,
  domicilio, contacto y credenciales entran. Un test fija que ninguna de
  `dni`, `tarseg`, `ban`, `bancue`, `fecnac`, `ele`, `tel`, `esigpas` está en
  `exclude_columns`.
- **R6.** CUANDO se ingiera `res`, el sistema debe traerla **entera**
  (`exclude_columns: []`): no tiene binarios ni texto ilimitado, y `cif`,
  `logacc`, `ideacc`, `ipacc`, `recema` entran como el resto.
- **R7.** El sistema debe excluir en cada tabla nueva las columnas de texto
  ilimitado que no se usan aguas abajo, con la **lista estándar de
  documentos** del YAML (`tex`, `med`, `des`, `obs`, `ima`, `emptex`,
  `dirtex`, `eiotex`, `desesp`, `texcom`, `serdesdat`, `texobs`, `coestr`)
  en las de compras y `tex` en las demás; `dco` añade además `dircon1..3`,
  `dirdir1..3`, `eittra` y `texent`. Excluir un nombre que la tabla no tiene
  es inofensivo (ya documentado en el YAML).
- **R8.** El sistema debe **dejar de excluir** `pagtex` y `pagfor` en `dcf`
  (condiciones de pago de la factura, informadas en 165.387 de 165.391) y
  **no** excluirlas en `dco`; `ctr` ya las trae. `dca` no cambia.
- **R9.** El sistema debe declarar `page_size: 5000` en `dcopro` (787.641
  filas, 71 columnas) y `dncpro` (286.432, 73), como `dcapro`; el resto usa
  el global (10.000).

## B · La puerta del diccionario (`config/diccionario/raw.yaml`)

- **R10.** El sistema debe tener **una ficha por tabla nueva** con el patrón
  de `rec`: `capa: origen`, `consumo_recomendado: false`,
  `clave_negocio: [ide]`, `paso_etl: ingest_raw`, `refresco: nocturno`,
  `columnas: {}`, la frase «recarga entera», el puntero a
  `azure-apps/sigrid_tablas.md` con el código de tabla y «No se traen N»
  con el número exacto si hay exclusiones (lo exigen ya
  `test_f006_raw_ingesta.py` y `test_f006_fuente_que_gobierna.py`).
- **R11.** La ficha de `raw.emp` debe **declarar qué datos personales
  contiene** (al menos «DNI», «cuenta bancaria», «domicilio» y «fecha de
  nacimiento») y la de `raw.res` que contiene el NIF (`cif`) de la persona;
  ninguna de las dos puede citar esas columnas tras «No se traen». La de
  `raw.dcf` pasa de «No se traen 23» a 21. Un test lo comprueba.
- **R12.** El sistema no debe usar `pendientes` de `00_global.yaml` ni
  `config/objetos_pendientes.yaml` para aplazar fichas de `raw` (el trinquete
  solo baja; la biyección ficha↔tabla ya se comprueba).
- **R13.** CUANDO cambie `raw.yaml`, el sistema debe subir `version` en
  `00_global.yaml` y actualizar las menciones a «31 tablas» de `raw.yaml`,
  `00_global.yaml` y `objetos_pendientes.yaml` a **56**. Un test compara el
  número de la cabecera de `raw.yaml` con `len(tables)` del YAML de ingesta.
- **R14.** Las fichas de `confir`, `conact`, `dco`, `ctrrec` y `dcfrec` deben
  decir, en una frase, qué pregunta de compras responden y cuál **no** (§6
  de `design.md`): p. ej. `confir` tiene fechas de firma solo para
  comparativos (`tip = 46`), no para facturas; ningún raw guarda la fecha de
  cambio de estado de un contrato. La ficha de `conest` debe decir que
  traduce `con.est` a nombre **por `tip`** (la misma cifra significa cosas
  distintas en contratos y facturas). Un test busca «cambio de estado» en la
  ficha de `confir` y «por `tip`» en la de `conest`.

## C · Recuento igual al de Sigrid, tabla a tabla

- **R15.** El sistema debe ofrecer `python main.py check-raw-recuentos`, de
  solo lectura, que para cada tabla del YAML compare `COUNT(*)` en Sigrid
  (con el mismo `where`) contra `COUNT(*)` en `raw`, imprima una línea por
  tabla y salga con código 1 si alguna difiere o falta en `raw`.
- **R16.** El veredicto debe ser dominio puro (`etl_sigrid/domain/
  recuentos.py`): dos mapas `tabla → filas | None` → informe con `iguales`,
  `distintas` (ambas cifras), `ausentes` y `sin_medir`, en el orden del YAML.
- **R17.** SI Sigrid rechaza o corta un `COUNT(*)`, ENTONCES esa tabla queda
  `sin_medir`, el barrido continúa y el comando sale con código 1: «no he
  podido mirar» no es «está bien» (`check-cobertura`, 2026-09-02).
- **R18.** MIENTRAS corre, el comando no debe escribir en Sigrid ni en
  `_meta.etl_runs`; un test con dobles comprueba que solo llama a
  `leer_sql`, `table_exists` y `count_rows`.

## D · Medición y rastro

- **R19.** El sistema debe dejar en `specs/F-066-ingesta-raw-pendientes/
  mediciones.md` la **primera nocturna** con las 25 tablas: por tabla, filas
  y segundos de `_meta.etl_runs`; total de `ingest_raw` frente a la línea
  base (20.148.546 filas, 1.832 s en B2s el 2026-09-05); créditos al empezar
  y al terminar (`cpu_credits_remaining`, `infra/README.md`) y el **SKU**.
- **R20.** Esa nocturna debe quedar anotada en la tabla de F-065 (fecha,
  acotada/completa, créditos, gastados, duración, estado, SKU); si F-065 aún
  no tiene documento, la fila vive en `mediciones.md` de esta feature.
- **R21.** CUANDO se cierre la feature, `azure-apps/datamart_seg_anual.md`
  debe decir que se consumen **56** tablas, listar las 25 nuevas y las
  descartadas por vacías, decir que `dcf` trae ya `pagtex`/`pagfor` y que
  `raw.emp`/`raw.res` llevan datos personales enteros.
- **R22.** El líder debe llevar a `harness/features.json` los hallazgos que
  cambian F-055, F-056, F-057 y F-067 (`design.md` §6): `hmores` como tabla
  de horas; `apu.fec` informada al 100 %; `apa` en `raw`; la actividad del
  proveedor es `conact`→`auxpronat`; Sigrid no guarda fechas de cambio de
  estado de contratos ni facturas, así que F-067 tendrá que construir ese
  histórico por foto diaria en el datamart, con `conest` para el nombre del
  estado y `con.tiemod` como proxy de su antigüedad mientras tanto.

## E · Cierre

- **R23.** `bash harness/init.sh` en verde con la campaña de mutación
  completa sobre `domain/recuentos.py` y el comando, con 0 supervivientes o
  cada uno justificado y aceptado por el humano.
- **R24.** La primera ingesta real y la comparación con `check-raw-recuentos`
  contra Azure son **MANUAL (humano)**.

## F · Reconciliar columnas de un `raw` preexistente (defecto, 2026-09-08)

Nace del fallo que R8 destapó: quitar `pagtex`/`pagfor` de `exclude_columns`
cambia el esquema de una tabla que **ya existía**, y `ensure_raw_table` solo
emitía `CREATE TABLE IF NOT EXISTS`. Tumbó dos nocturnas (`k251zrq` y
`29813760`) con `UndefinedColumn: column "pagtex" of relation "dcf"`.

- **R25.** CUANDO `ensure_raw_table` encuentre una tabla `raw` que ya existe,
  el sistema debe comparar sus columnas reales con las esperadas y **añadir
  con un solo `ALTER TABLE` todas las que falten**, aunque falten varias.
- **R26.** La columna añadida debe nacer **NULL** —la tabla ya tiene filas—
  y con el tipo Postgres de su `ColumnSpec`.
- **R27.** El sistema **nunca** debe borrar una columna ni cambiar un tipo:
  SI el origen deja de traer una columna, o su tipo ya no casa, ENTONCES
  registra un `warning` con tabla y columna y **sigue**. Las columnas
  técnicas (`_ingested_at`, `_source_tiemod`) quedan fuera de la comparación.
- **R28.** La reconciliación debe ir **antes** del `TRUNCATE` del
  full-refresh, y cada `ADD COLUMN` debe dejar su línea en el log.
