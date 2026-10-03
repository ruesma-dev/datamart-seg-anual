<!-- specs/F-123-descompuestos-regla-origenes/design.md -->
# F-123 · Diseño

Cambio de REGLA dentro del esquema `descompuestos`. No cambian la ingesta, el
troceado (`fn_trocear`), el incremental, la fórmula del cuadre ni los orígenes
`PLANIF_JO`, `MASTER_PRE_ABC` y `MASTER_PLANIF_JO`. Cambian tres cosas: el
master 0 se llama `MASTER_ESTUDIO`; `ESTUDIO` solo se publica en las obras sin
master 0; y una vista nueva, `v_pbi_master_estudio`. Cifras:
`progress/spec_F-123.md`.

## 1. Lo medido que fija el diseño (2026-10-02, solo lectura)

- **170 obras tienen master 0**, todas con líneas (36.355 partidas, 107.061
  líneas). **44 no lo tienen**: 11 con master pero sin versión 0 con
  descompuesto (la 0713 entre ellas) y 33 sin ningún master cargado.
- De las 35.523 partidas con `ESTUDIO` hoy, 26.959 tienen también master 0 con
  descompuesto y en **26.833 (99,5 %) son las mismas líneas con la misma suma por
  unidad**: donde hay master 0, `ESTUDIO` no aporta nada.
- Otras 2.020 están en obras con master 0 sin descompuesto en él: **1.758 no
  existen en el master 0** (creadas después en la fase viva), 249 con precio y
  sin descompuesto (el cuadre `MASTER_ESTUDIO` las da `SIN_DESCOMPUESTO`) y 13
  con precio 0. Dejan de tener Estudios publicado: es la regla (no lo tenían).
- En obras con master 0 la «Descomposición» de la fase viva es NO_CUADRA en
  18.132 partidas de 24.855 (su precio ya se movió); el master 0 cuadra en
  34.174 de 34.849. Es la prueba de que la fase viva no es Estudios.

## 2. Ficheros

**A crear**: `tests/test_f123_origenes.py` (§6).

**A modificar**

| Fichero | Qué cambia |
|---|---|
| `etl_sigrid/domain/descompuestos.py` | `ORIGENES` con `MASTER_ESTUDIO` en el sitio de `MASTER_INICIAL` |
| `etl_sigrid/infrastructure/postgres/sql/descompuestos/02_lineas_coste.sql` | `CHECK` nuevos en el DDL; bloque de migración (§3); filtro de obra en el `INSERT` de `ESTUDIO`; cabecera |
| `.../descompuestos/03_lineas_master.sql` | `'MASTER_INICIAL'` -> `'MASTER_ESTUDIO'` en el `CASE` de `atributos` y en el `IN` del `DELETE`; cabecera. **Cambia el sello** (§5) |
| `.../descompuestos/04_elementos.sql` | `lineas_master_inicial` -> `lineas_master_estudio` (mismo sitio) |
| `.../descompuestos/05_cuadre.sql` | fila `ESTUDIO` solo en obras sin master 0; cabecera |
| `.../descompuestos/06_views.sql` | vista nueva `v_pbi_master_estudio`; cabecera (`tres` -> `cuatro`) |
| `etl_sigrid/application/steps/build_descompuestos_step.py` | docstring (lista de vistas). `SUB_PASOS` no cambia |
| `main.py` | ayuda de `build-descompuestos` (orígenes, «cuatro vistas») |
| `config/diccionario/00_global.yaml` | `version` 40; `R-DESCOMPUESTO-ORIGEN` (fase viva + regla de Estudios, `v_pbi_master_estudio` en `ambito`); `esquemas.descompuestos`; cabecera |
| `config/diccionario/descompuestos.yaml` | fichas `lineas`, `cuadre_partida`, `elementos`, `v_pbi_estudio`; ficha nueva `v_pbi_master_estudio`; cabecera (puntos 3 y 7) |
| `tests/test_f097_descompuestos.py`, `test_f097_planificador.py`, `test_f120_factor.py` | aserciones que nombran `MASTER_INICIAL`, `lineas_master_inicial`, el `CROSS JOIN` de `05`, la nota D7 de F-120 y la versión 39 (§6) |
| `docs/ARCHITECTURE.md` | tabla de pestañas y orígenes (§«Los descompuestos») y la regla de Estudios |
| `../azure-apps/datamart_seg_anual.md` | orígenes y vista nueva (repo propio, commit propio) |

**Que NO se tocan**: `ingest_descompuestos_step.py` y toda la ingesta; DDL y
datos de `_des_texto` y `_versiones_cargadas`; `00_setup.sql` y
`01_troceado.sql` (no nombran `MASTER_INICIAL`), con `fn_trocear`, `fn_num` y
`fn_fecha`; `FICHEROS_DEL_SELLO`, `planificar_*`, `trocear_des`; el bloque
`PLANIF_JO` de `02`; `v_pbi_estudio`, `v_pbi_planif_jo`,
`v_pbi_master_planif_jo`; `SUB_PASOS`; `config/settings.py`,
`business_rules.yaml`, `stg.yaml`; todo `stg`, `mart` y `cierre` (R1: ningún SQL
fuera de `sql/descompuestos/` lee este esquema). `CLAUDE.md` no nombra
`MASTER_INICIAL`: no se toca.

## 3. SQL (esquema `descompuestos`)

**`02_lineas_coste.sql` — migración (R15, R16).** Las dos tablas persisten y
`CREATE TABLE IF NOT EXISTS` no cambia un `CHECK` ya instalado. El DDL lleva ya
los `CHECK` nuevos (instalación limpia); tras los dos `CREATE` y ANTES del
`DELETE`/`INSERT`:

```sql
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint
               WHERE conname = 'ck_lineas_origen'
                 AND conrelid = 'descompuestos.lineas'::regclass
                 AND pg_get_constraintdef(oid) LIKE '%MASTER_INICIAL%') THEN
        ALTER TABLE descompuestos.lineas DROP CONSTRAINT ck_lineas_origen;
        UPDATE descompuestos.lineas SET origen = 'MASTER_ESTUDIO' WHERE origen = 'MASTER_INICIAL';
        ALTER TABLE descompuestos.lineas ADD CONSTRAINT ck_lineas_origen CHECK (origen IN (...));
    END IF;
    -- lo mismo para descompuestos.cuadre_partida y ck_cuadre_origen
END $$;
```

Solo actúa la primera vez (107.061 líneas y ~89.000 filas de cuadre). No hay
choque de clave: no existe ninguna fila `MASTER_ESTUDIO` antes. El `UPDATE` es
necesario aunque el sello retrocee: sin él el `ADD CONSTRAINT` fallaría sobre
las versiones aún no retroceadas. `ESTUDIO` no necesita migración: `02` y `05`
ya lo borran y lo rehacen entero cada noche. Es el ÚNICO sitio del SQL donde
sigue escrito `MASTER_INICIAL`.

**`02` — `ESTUDIO` solo sin master 0 (R8, R9, R11).** El `INSERT` de `ESTUDIO`
gana una condición; el `DELETE` previo y el bloque `PLANIF_JO` no cambian:

```sql
WHERE NOT EXISTS (SELECT 1 FROM enlazadas e WHERE e.presupuesto_id = t.presupuesto_id)
  AND NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v
                  WHERE v.obra_id = t.obra_id AND v.fase_num = 0)
```

Contra `_versiones_cargadas` y no contra `lineas` a propósito: `02` corre ANTES
que `03`, y una versión 0 cargada esta noche aún no tendría líneas. R11 se cumple
por construcción. El troceado del ámbito 3 entero se mantiene (lo necesita
`enlazadas`).

**`03_lineas_master.sql`.** Solo el literal (dos sitios) y la cabecera.

**`04_elementos.sql`.** `COUNT(*) FILTER (WHERE origen = 'MASTER_ESTUDIO') AS
lineas_master_estudio`, en el mismo sitio. La tabla es `DROP + CREATE`: no
necesita migración.

**`05_cuadre.sql` (R10).** El `DELETE` y el `CASE` no cambian. La fila `ESTUDIO`
del `CROSS JOIN (VALUES ('ESTUDIO'), ('PLANIF_JO'))` se filtra:

```sql
WHERE o.origen = 'PLANIF_JO'
   OR NOT EXISTS (SELECT 1 FROM descompuestos._versiones_cargadas v
                  WHERE v.obra_id = h.obra_id AND v.fase_num = 0)
```

Previsión: 51.206 filas `ESTUDIO` (hoy 149.570); `PLANIF_JO` igual.

**`06_views.sql` (R13, R14).** `v_pbi_estudio` intacta. Nueva, al final:

```sql
CREATE OR REPLACE VIEW descompuestos.v_pbi_master_estudio AS
SELECT <las 21 columnas de v_pbi_estudio, en su orden>
FROM descompuestos.lineas WHERE origen = 'MASTER_ESTUDIO';
```

Mismas columnas para que Power BI o un agente puedan unirlas: «Estudios» = las
dos vistas (cada obra está en una sola). Su clave (`obra_id`, `partida_id`,
`orden`) es única: el master 0 es una sola versión por obra.

## 4. Dominio

`ORIGENES = ("ESTUDIO", "PLANIF_JO", "MASTER_ESTUDIO", "MASTER_PRE_ABC",
"MASTER_PLANIF_JO")`. Sin función nueva: la regla es un filtro de SQL y se prueba
por texto y en el contraste (§6). `ESTADOS_CUADRE` no cambia.

## 5. Sello y despliegue

- **El sello cambia sin remedio**: el literal está en `03_lineas_master.sql`,
  uno de los tres ficheros del sello. La primera ejecución ve las 3.025
  versiones pendientes aunque el retroceo dé las mismas líneas.
- **Lo que se ve no depende del retroceo**: la migración de `02` cambia el
  origen del master 0 entero la primera noche, y `02`/`05` quitan `ESTUDIO` de
  las obras con master 0 esa misma noche.
- **Como F-120**: aviso a Juan Romero y Elena Díaz; imagen del job PRIMERO;
  después, fuera de la nocturna y mirando los créditos de CPU, `python main.py
  build-descompuestos --sin-tope` y `python main.py apply-grants` (la vista nueva)
  desde el MISMO commit (F-120 midió 1.619 s). Alternativa: que la nocturna
  retrocee a 300 MB por noche (8-11 noches más largas, gastando la hucha de CPU).
- **El orden importa**: si el código nuevo corre contra la base y después la
  imagen VIEJA, esta inserta `MASTER_INICIAL` contra el `CHECK` nuevo:
  `build_descompuestos` FAILED. Nunca construir contra Azure desde la rama antes
  de desplegar la imagen.
- Después: `publicar-diccionario` (versión 40) y **reiniciar el MCP**, que
  cachea el diccionario. El esquema ya está en su lista blanca; la vista nueva
  entra con él.

## 6. Tests (sin red ni BBDD)

`tests/test_f123_origenes.py`:

- Dominio: `ORIGENES` exacto (R6).
- Texto SQL: ningún `.sql` de la carpeta contiene `MASTER_INICIAL` fuera del
  bloque `DO` de `02` (R5); los dos `CHECK` = `ORIGENES` (R6); el `CASE` y el
  `DELETE` de `03` con `MASTER_ESTUDIO` (R4); el bloque de migración con su
  condición, su `UPDATE` de las dos tablas y ANTES del primer `INSERT` (R15,
  R16); el `NOT EXISTS` de `_versiones_cargadas` con `fase_num = 0` en el
  `INSERT` de `ESTUDIO` de `02` y en `05` (R8-R10); el bloque `PLANIF_JO` de `02`
  y el `DELETE` de `05` sin cambios (R3); `elementos` con `lineas_master_estudio`
  en la posición de antes (R7); `v_pbi_estudio` igual y `v_pbi_master_estudio`
  con sus mismas columnas y `WHERE origen = 'MASTER_ESTUDIO'` (R13, R14); ningún
  `DELETE`/`DROP`/`TRUNCATE` de `_des_texto` ni `_versiones_cargadas` (R2); el
  sello difiere de `7cad480aee614b2a` (R17); ningún SQL fuera de
  `sql/descompuestos/` nombra el esquema `descompuestos` (R1).
- Diccionario y docs: versión 40; `R-DESCOMPUESTO-ORIGEN` con «fase viva»,
  `PLANIF_JO`, `MASTER_ESTUDIO`, `ESTUDIO` y «master 0»; ficha de
  `v_pbi_master_estudio`; ninguna ficha ni `ARCHITECTURE.md` ni la ayuda de
  `main.py` con `MASTER_INICIAL` (R18-R21).

Tests existentes que se reescriben, ninguno se borra sin sustituto: en
`test_f097_descompuestos.py` `COLUMNAS_ELEMENTOS`, `VISTAS_POR_ORIGEN` (gana
`v_pbi_master_estudio`), el `CASE` y el `IN` de `03` y el cuadre de `05`; en
`test_f097_planificador.py` la tupla `ORIGENES`; en `test_f120_factor.py` la
nota D7 (`test_f120_r25_*`: el ejemplo 0713 sigue en `ESTUDIO`; el 0726 pasa a
`MASTER_ESTUDIO`) y la versión (`test_f120_r26_*`).

**Contraste en un PostgreSQL 16 desechable** (scratchpad, como F-097 y F-120;
nunca contra Azure): base creada con el SQL de `main` más una muestra de
`_des_texto` copiada en solo lectura (0713, 0726 y una obra sin master), y el
build de la rama DOS veces. Comprueba la migración (una sola vez), R11 y los
testigos de R23.

## 7. Encaje y límites

Todo queda en `descompuestos`, esquema módulo: lee solo `raw` y su propio
esquema, y ningún paso depende de él. Sin responsabilidad nueva ni contacto con
`sigrid-api`: no se relee nada. **Fuera de alcance**: la medición de Estudios en
las líneas `ESTUDIO` (F-120 decidió que no); el término «fase viva» en
`stg`/`mart`/`cierre`; la fase 0 de VENTA (ámbito 7); F-122.

## 8. Riesgos y alternativas descartadas

- **Consumidores**: quien filtre `origen = 'MASTER_INICIAL'` o lea
  `elementos.lineas_master_inicial` (la herramienta de Juan Romero) recibe 0
  filas o un error de columna; quien lea `ESTUDIO` deja de ver las 170 obras con
  master 0. Aviso ANTES de desplegar (tasks T13).
- **Transitorio**: una versión 0 cargada cuyo troceado quede aplazado por el
  tope deja a su obra una noche sin `ESTUDIO` y sin `MASTER_ESTUDIO`. Solo con
  más de 300 MB pendientes, y se cura solo.
- **Obra que estrena master 0**: su `ESTUDIO` desaparece esa noche y lo sustituye
  `MASTER_ESTUDIO`. Es la regla; la ficha lo dice.
- **Descartado `v_pbi_estudio` con los dos orígenes**: cambiaría su contenido y
  obligaría a una columna `origen`; una vista nueva no rompe a nadie.
- **Descartado decidir por partida** en vez de por obra: publicaría como Estudios
  1.758 partidas que no existen en el master 0.
