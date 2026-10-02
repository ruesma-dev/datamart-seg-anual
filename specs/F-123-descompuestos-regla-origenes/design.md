<!-- specs/F-123-descompuestos-regla-origenes/design.md -->
# F-123 · Diseño

Cambio de REGLA dentro del esquema `descompuestos`: no cambia la ingesta, el
troceado (`fn_trocear`), el incremental ni la fórmula del cuadre. Cambia qué
nombre lleva el master 0, cuándo se publica la «Descomposición» de la fase viva
y dónde se dice que Estudios no existe. Cifras y decisiones D1-D8:
`progress/spec_F-123.md`.

## 1. Lo medido que fija el diseño (2026-10-02, solo lectura)

- **170 obras tienen master 0** y las 170 tienen líneas en él (36.355 partidas,
  107.061 líneas). `_versiones_cargadas` solo guarda versiones con descompuesto,
  así que «obra con master 0» es `EXISTS` en esa tabla con `fase_num = 0`.
- De las 35.523 partidas con `ESTUDIO` hoy: 26.959 tienen también master 0 y en
  **26.833 (99,5 %) son las mismas líneas con la misma suma por unidad**: donde
  hay master 0, `ESTUDIO` no aporta nada.
- Otras 2.020 están en obras con master 0 pero sin descompuesto en él: **1.758 no
  existen en el master 0** (partidas creadas después en la fase viva: no son de
  Estudios), 249 están con precio y sin descompuesto y 13 con precio 0.
- Las 6.544 restantes están en **44 obras sin master 0** (11 con master pero sin
  versión 0 con descompuesto, la 0713 entre ellas; 33 sin ningún master). Ese es
  el respaldo por OBRA (D1): 11.783 líneas.
- El cuadre lo confirma: en las obras con master 0, `ESTUDIO` es NO_CUADRA en
  18.132 partidas de 24.855 (el precio de la fase viva ya se movió) mientras que
  `MASTER_INICIAL` cuadra en 34.174 de 34.849.

## 2. Ficheros

**A crear**

| Fichero | Qué es |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/descompuestos/07_estudios_partida.sql` | la tabla `descompuestos.estudios_partida` (§5) |
| `tests/test_f123_origenes.py` | los tests de §7 |

**A modificar**

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/domain/descompuestos.py` | `ORIGENES`; `VIAS_ESTUDIOS`, `MOTIVOS_NO_EXISTE`; `resolver_estudios()` (§3) |
| `.../descompuestos/02_lineas_coste.sql` | `CHECK` nuevos en el DDL; bloque de MIGRACIÓN; `DELETE` e `INSERT` de `ESTUDIO_RESPALDO` con el filtro de obra; cabecera (§4) |
| `.../descompuestos/03_lineas_master.sql` | `'MASTER_INICIAL'` -> `'MASTER_ESTUDIO'` en el `CASE` de `_atributos` y en el `IN` del `DELETE`; cabecera. **Cambia el sello** (§6) |
| `.../descompuestos/04_elementos.sql` | columnas `lineas_estudio_respaldo` y `lineas_master_estudio` (sustituyen a `lineas_estudio` y `lineas_master_inicial`) |
| `.../descompuestos/05_cuadre.sql` | `ESTUDIO_RESPALDO` solo en obras sin master 0; `PLANIF_JO` igual; cabecera |
| `.../descompuestos/06_views.sql` | `v_pbi_estudio`: `WHERE origen IN ('MASTER_ESTUDIO', 'ESTUDIO_RESPALDO')` y `origen` última columna |
| `.../descompuestos/00_setup.sql`, `01_troceado.sql` | SOLO comentarios (`n/7` -> `n/8`, `MASTER_INICIAL`); entran en el sello, que ya cambia por `03` |
| `etl_sigrid/application/steps/build_descompuestos_step.py` | octavo `_SubStep` (`estudios_partida`, cuenta filas de esa tabla) y docstring |
| `config/diccionario/descompuestos.yaml` | fichas de `lineas`, `cuadre_partida`, `elementos`, `v_pbi_estudio`; ficha nueva de `estudios_partida`; cabecera |
| `config/diccionario/00_global.yaml` | `version` 40; `R-DESCOMPUESTO-ORIGEN` reescrita; regla nueva `R-FASE-VIVA`; `R-FAS-AMBIGUO`; `esquemas.descompuestos`; cabecera |
| `config/diccionario/stg.yaml` | las dos menciones de «Previsto vivo» remiten a `R-FASE-VIVA` |
| `tests/test_f097_descompuestos.py`, `test_f097_planificador.py`, `test_f120_factor.py` | las aserciones que nombran `ESTUDIO`, `MASTER_INICIAL`, `lineas_estudio`, la nota D7 de F-120 y la versión 39 (§7) |
| `docs/ARCHITECTURE.md`, `CLAUDE.md`, `main.py` (ayuda de `build-descompuestos`) | la regla nueva |
| `../azure-apps/datamart_seg_anual.md` | orígenes, `estudios_partida`, `v_pbi_estudio` (repo propio, commit propio) |

**Que NO se tocan**: `ingest_descompuestos_step.py` y todo lo de la ingesta
(R21); el DDL y los datos de `_des_texto` y `_versiones_cargadas`; el cuerpo de
`fn_trocear`, `fn_num` y `fn_fecha`; `FICHEROS_DEL_SELLO`;
`planificar_relectura`, `planificar_troceado`, `trocear_des`; el bloque
`PLANIF_JO` de `02`; `v_pbi_planif_jo` y `v_pbi_master_planif_jo`;
`config/settings.py`, `business_rules.yaml`; `stg`, `mart`, `cierre`. No se
introduce el término «fase viva» en el SQL de `cierre` ni de `mart`.

## 3. Dominio (`etl_sigrid/domain/descompuestos.py`, capa domain)

```python
ORIGENES = ("ESTUDIO_RESPALDO", "PLANIF_JO", "MASTER_ESTUDIO", "MASTER_PRE_ABC", "MASTER_PLANIF_JO")
VIAS_ESTUDIOS = ("MASTER_ESTUDIO", "ESTUDIO_RESPALDO", "NO_EXISTE")
MOTIVOS_NO_EXISTE = ("MASTER_0_SIN_DESCOMPUESTO", "PARTIDA_FUERA_DEL_MASTER_0",
                     "SUSTITUIDO_POR_PLANIFICACION", "SIN_DESCOMPUESTO")

def resolver_estudios(*, obra_tiene_master_0: bool, lineas_master_estudio: int,
                      lineas_respaldo: int, en_cuadre_master_0: bool,
                      sustituido: bool) -> tuple[str, str | None, int]:
    """(via_estudios, motivo_no_existe, num_lineas) de una partida (R13-R14)."""
```

Precedencia, la MISMA que el `CASE` de `07`: líneas de master 0 -> respaldo ->
`NO_EXISTE`; dentro de `NO_EXISTE`, con master 0 en la obra el motivo es
`MASTER_0_SIN_DESCOMPUESTO` si la partida tiene fila de cuadre en el master 0 y
`PARTIDA_FUERA_DEL_MASTER_0` si no; sin master 0, `SUSTITUIDO_POR_PLANIFICACION`
si `sustituido` y `SIN_DESCOMPUESTO` si no. `ESTADOS_CUADRE` no cambia. Un test
exige que las tres tuplas sean literalmente las listas del SQL.

## 4. SQL (esquema `descompuestos`)

**`02_lineas_coste.sql` — migración (R19, R20).** Las dos tablas persisten: el
`CREATE TABLE IF NOT EXISTS` no cambia un `CHECK` ya instalado. Tras los dos
`CREATE`, y ANTES de cualquier `INSERT`:

```sql
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'ck_lineas_origen'
                 AND conrelid = 'descompuestos.lineas'::regclass
                 AND pg_get_constraintdef(oid) NOT LIKE '%MASTER_ESTUDIO%') THEN
        ALTER TABLE descompuestos.lineas DROP CONSTRAINT ck_lineas_origen;
        UPDATE descompuestos.lineas SET origen = 'MASTER_ESTUDIO' WHERE origen = 'MASTER_INICIAL';
        DELETE FROM descompuestos.lineas WHERE origen = 'ESTUDIO';
        ALTER TABLE descompuestos.lineas ADD CONSTRAINT ck_lineas_origen CHECK (origen IN (...));
    END IF;
    -- lo mismo para descompuestos.cuadre_partida y ck_cuadre_origen
END $$;
```

Solo actúa la primera noche (107.061 + 99.049 líneas; el `ADD CONSTRAINT`
recorre la tabla una vez). El DDL de instalación nueva lleva ya los `CHECK`
nuevos. La forma exacta la decide el implementer; lo fijo es R19-R20.

**`02` — el respaldo (R6-R8).** El `INSERT` de `ESTUDIO` pasa a insertar
`'ESTUDIO_RESPALDO'` con una condición más; el `DELETE` previo pasa a `origen IN
('ESTUDIO_RESPALDO', 'PLANIF_JO')`:

```sql
  AND NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v
                  WHERE v.obra_id = t.obra_id AND v.fase_num = 0)
```

Se decide contra `_versiones_cargadas` y no contra `lineas` a propósito: `02`
corre ANTES que `03`, y una versión 0 releída esta noche aún no tendría líneas.
Así R8 se cumple por construcción (las líneas `MASTER_ESTUDIO` solo salen de
versiones 0 cargadas). El troceado del ámbito 3 entero se mantiene para calcular
`enlazadas`.

**`03_lineas_master.sql`.** Solo el literal del origen (dos sitios) y la
cabecera. El paso 5 (huella de atributos) queda como red: si alguna versión 0
conservara el origen viejo, lo corrige sin retrocear.

**`04_elementos.sql`.** `COUNT(*) FILTER (WHERE origen = 'ESTUDIO_RESPALDO') AS
lineas_estudio_respaldo` y `... = 'MASTER_ESTUDIO' AS lineas_master_estudio`. La
tabla es `DROP + CREATE`: el cambio de columnas no necesita migración.

**`05_cuadre.sql` (R10, R11).** `DELETE ... WHERE origen IN ('ESTUDIO_RESPALDO',
'PLANIF_JO')`; el `CROSS JOIN (VALUES ...)` pasa a `('ESTUDIO_RESPALDO'),
('PLANIF_JO')` y la fila `ESTUDIO_RESPALDO` se filtra con el mismo `NOT EXISTS`
de obra. `SUSTITUIDO_POR_PLANIFICACION` sigue saliendo de `su`, solo en ese
origen. Previsión: 51.206 filas `ESTUDIO_RESPALDO` (hoy 149.570 `ESTUDIO`).

**`06_views.sql` (R16).** `v_pbi_estudio` con las mismas 21 columnas y `origen`
al final. Con D1 por obra su clave (`obra_id`, `partida_id`, `orden`) sigue
siendo única.

## 5. `07_estudios_partida.sql` (R12-R14)

Derivado, `DROP TABLE IF EXISTS` + `CREATE TABLE AS` cada noche (como
`elementos`), después de `05` porque lee el cuadre. Lee SOLO de su esquema:
`lineas`, `cuadre_partida`, `_versiones_cargadas`.

| Columna | Tipo | De dónde |
|---|---|---|
| `obra_id`, `partida_id` | BIGINT | PK. Universo: filas de `cuadre_partida` con (ámbito 3, fase 0, `PLANIF_JO`) o (ámbito 8, fase 0), más toda pareja con líneas `MASTER_ESTUDIO` o `ESTUDIO_RESPALDO`; `obra_id <> 0` |
| `via_estudios` | TEXT NOT NULL | R13-R14, `CHECK` con `VIAS_ESTUDIOS` |
| `motivo_no_existe` | TEXT | R14, `CHECK` con `MOTIVOS_NO_EXISTE`; NULL si existe |
| `obra_tiene_master_0` | BOOLEAN NOT NULL | `EXISTS` en `_versiones_cargadas` con `fase_num = 0` |
| `num_lineas` | INTEGER NOT NULL | líneas del origen elegido; 0 si `NO_EXISTE` |

`sustituido` se lee del cuadre (`ESTUDIO_RESPALDO` con estado
`SUSTITUIDO_POR_PLANIFICACION`), sin volver a trocear. No repite precio ni estado
de cuadre: están en `cuadre_partida` con el origen que dice `via_estudios`. Es
capa de consumo, con ficha y `consumo_recomendado: true`.

## 6. Sello y despliegue (D5)

- **El sello cambia sin remedio**: el literal del origen vive en
  `03_lineas_master.sql`, que es uno de los tres ficheros del sello. La primera
  ejecución con el código nuevo ve las 3.025 versiones pendientes aunque el
  retroceo produzca exactamente las mismas líneas.
- **Lo que el usuario ve no depende del retroceo**: la migración de `02` cambia
  el origen del master 0 y quita `ESTUDIO` la primera noche, entera. No hay
  estado mezclado visible, a diferencia de F-120.
- **Recomendado**: como F-120. Imagen del job PRIMERO; después, fuera de la
  nocturna y mirando los créditos de CPU, `python main.py build-descompuestos
  --sin-tope` y `python main.py apply-grants` (la tabla nueva necesita permisos)
  desde el MISMO commit. Medido en F-120: 1.619 s, 7 lotes.
- **Alternativa**: no hacer nada y dejar que la nocturna retrocee a 300 MB por
  noche (del tope comen antes las vigentes: 8-11 noches más largas). Correcta,
  pero gasta la hucha de CPU compartida durante más de una semana.
- **Descartado**: sacar el literal de `03` a un marcador (el texto de `03`
  cambia igual una vez) y poner el sello nuevo a mano con un `UPDATE` (escribir
  el estado del incremental a mano es justo lo que el sello evita).
- **El orden importa**: si el código nuevo corre contra la base y después la
  imagen VIEJA, esta ve otro sello, retrocea e inserta `MASTER_INICIAL` contra
  el `CHECK` nuevo: `build_descompuestos` FAILED. Nunca construir contra Azure
  desde la rama antes de desplegar la imagen.
- Después: `publicar-diccionario` (versión 40) y **reiniciar el MCP**, que
  cachea el diccionario. El esquema ya está en su lista blanca.

## 7. Tests (sin red ni BBDD)

`tests/test_f123_origenes.py`:

- Dominio: `ORIGENES`, `VIAS_ESTUDIOS`, `MOTIVOS_NO_EXISTE`; `resolver_estudios`
  con una tabla parametrizada que cubra las seis salidas y la precedencia
  (master 0 gana a respaldo) (R3, R13-R15).
- Texto SQL: ningún `.sql` de la carpeta contiene `MASTER_INICIAL` ni `'ESTUDIO'`
  como origen fuera del bloque de migración (R2); los dos `CHECK` son `ORIGENES`
  (R3); el `CASE` de `03` (R1, R4); el `NOT EXISTS` de obra en el `INSERT` de `02`
  y en `05` (R6, R7, R10); el bloque de migración con sus cuatro sentencias y su
  condición (R19, R20); `v_pbi_estudio` con `origen` última (R16) y las otras dos
  vistas intactas (R17); columnas de `elementos` (R18); `07` con sus `CHECK`
  iguales al dominio y sin leer de `raw` (R12-R14); ningún `DELETE`, `DROP` ni
  `TRUNCATE` de `_des_texto`/`_versiones_cargadas` y la ingesta sigue pidiendo
  el ámbito 3 (R21); el sello difiere de `7cad480aee614b2a` (R22).
- Step: `SUB_PASOS` con ocho entradas, `07` la última y `estudios_partida` como
  tabla contada.
- Diccionario y docs: `R-FASE-VIVA` con sus términos, `R-DESCOMPUESTO-ORIGEN`,
  fichas, versión 40, y los cuatro documentos de R26 (R23-R26).

Tests existentes que se reescriben (no se borran): en `test_f097_descompuestos.py`
los de orígenes, R15, R17, R22 (columnas de `elementos`), R23 y R24; en
`test_f097_planificador.py` la tupla `ORIGENES`; en `test_f120_factor.py` la
nota D7 de las fichas (ahora habla de `ESTUDIO_RESPALDO` y `MASTER_ESTUDIO`) y
la versión.

**Contraste en un PostgreSQL 16 desechable** (scratchpad, como F-097 y F-120;
nunca contra Azure): base creada con el SQL de `main` y una muestra de
`_des_texto` copiada en solo lectura (0713, 0726 y una obra sin master); después
el build de la rama DOS veces. Comprueba la migración, R8, los testigos de R28 y
que `estudios_partida` coincide con `resolver_estudios` fila a fila.

## 8. Encaje y límites

Todo queda en `descompuestos`, esquema módulo (lee solo `raw` y su esquema;
ningún paso depende de él). Sin responsabilidad nueva ni contacto con
`sigrid-api`: no se relee nada. **Fuera de alcance**: llevar la medición de
Estudios a las líneas del respaldo (decidido en F-120: no); el nombre «fase
viva» en `cierre`/`mart`; si la fase 0 de VENTA (ámbito 7) es también «viva»
(el humano habló de coste: la regla no lo afirma); F-122.

## 9. Riesgos y alternativas descartadas

- **Respaldo por PARTIDA** (D1): publicaría 2.020 partidas más, pero 1.758 no
  existen en el master 0: llamarlas Estudios sería falso. Descartado salvo que el
  humano lo pida; cambia solo el `NOT EXISTS` de `02` y `05`.
- **Conservar el nombre `ESTUDIO`** para el respaldo (D2): rompe menos a quien
  lee por origen, pero deja un origen llamado igual que antes con otro alcance.
- **«No existe» solo en el cuadre** (D3): las partidas de la fase viva que no
  están en el master 0 no tendrían fila en ningún sitio.
- **Riesgo, consumidores**: quien filtre `origen = 'ESTUDIO'` o `'MASTER_INICIAL'`
  (la herramienta de Juan Romero) recibe 0 filas sin error. Aviso ANTES de
  desplegar (D7).
- **Riesgo, transitorio**: una versión 0 recién cargada cuyo troceado quede
  aplazado por el tope deja a su obra una noche sin respaldo y sin
  `MASTER_ESTUDIO`; `estudios_partida` dirá `NO_EXISTE`. Solo con más de 300 MB
  pendientes, y se cura solo.
- **Riesgo, obra que estrena master 0**: su respaldo desaparece esa noche y la
  sustituye `MASTER_ESTUDIO`. Es la regla, no un fallo; la ficha lo dice.
