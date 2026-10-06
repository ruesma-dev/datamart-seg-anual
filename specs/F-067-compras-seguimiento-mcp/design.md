<!-- specs/F-067-compras-seguimiento-mcp/design.md -->
# F-067 · Diseño · Compras por el MCP (con F-125)

Cifras y porqués: `progress/spec_F-067.md`. Requisitos: `requirements.md`.

## 1 · Encaje y límite

Todo vive en `build_compras` (lee `raw.*`, depende solo de `ingest_raw`) salvo
una columna en dos vistas de `descompuestos` (§6). **Sin ingesta nueva**: `cod2`,
`dncide` y `dncproide` ya entran en `raw.dcapro`/`ctrpro`/`dcfpro` (ninguno está
en `exclude_columns`), y `dnc`, `ctrrec`, `auxpag` y `con.tiemod` ya están en
`raw`. Dentro del límite del servicio: modelado de datos de Sigrid ya ingeridos.
Lo único nuevo en la arquitectura son **las dos primeras tablas persistentes de
`compras`** (§3): `--full` trunca `raw` y nada más, y el resto de `compras` se
reconstruye con `DROP` + `CREATE` sin tocarlas (no dependen de ninguna).

## 2 · Ficheros

**Crear**

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/historial_estados.py` | Literales y oráculo de la foto (§4) y de la fecha de Delphi |
| `etl_sigrid/infrastructure/postgres/sql/compras/10_necesidades.sql` | `compras.necesidades` (R19) |
| `etl_sigrid/infrastructure/postgres/sql/compras/11_historial_estados.sql` | Las dos tablas persistentes, la foto y `compras.v_estado_documentos` (R1-R11) |
| `tests/test_f067_dominio.py` | Oráculo puro: foto, guardas, días, fecha de Delphi |
| `tests/test_f067_sql.py` | Texto del SQL: literales = dominio, columnas, vetos |
| `tests/test_f067_diccionario.py` | Fichas, claves, relaciones, frases obligatorias |

**Modificar**

| Ruta | Qué cambia |
|---|---|
| `sql/compras/00_setup.sql` | + `compras.fn_sigrid_tiempo(DOUBLE PRECISION) RETURNS TIMESTAMP` (R14) |
| `sql/compras/01_documentos.sql` | Columnas AL FINAL: contratos (R12-R14), albaran_lineas (R17) y, con D3, contrato_lineas y factura_lineas (R18). Nada existente cambia ni se mueve |
| `sql/descompuestos/06_views.sql` | `necesidad_id` al final de `v_pbi_planif_jo` y `v_pbi_master_planif_jo` (R20) |
| `etl_sigrid/application/steps/build_compras_step.py` | `SUB_PASOS` + `10` (cuenta `necesidades`) y `11` (cuenta `historial_estados`); docstring |
| `tests/test_f047_steps.py` | Lista de ficheros de `build_compras` |
| `config/diccionario/compras.yaml` | Fichas nuevas y columnas nuevas; `contratos` (R15, R16), `comparativos` (R26) |
| `config/diccionario/descompuestos.yaml` | `codigo_alternativo` = código 2 (R23); `necesidad_id` en las dos vistas |
| `config/diccionario/00_global.yaml` | `version` +1; comentario de versión; preguntas (R27) |
| `docs/ARCHITECTURE.md` | Párrafo: tablas persistentes de `compras`, foto por tramos, `tiemod` de Delphi |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` | Objetos nuevos (commit propio en ese repositorio) |

**NO se tocan**: `config/tables_sigrid.yaml`; `sql/descompuestos/00_setup.sql`,
`01_troceado.sql`, `02_lineas_coste.sql`, `03_lineas_master.sql` (los tres del
sello retrocearían el master entero, R21) ni la tabla `descompuestos.lineas`;
`08`/`09` de F-038; `maestro`, `stg`, `mart`, `cierre`; `mcp-bbdd` (`compras` y
`descompuestos` ya están en su lista blanca); `.env`.

## 3 · Las tablas persistentes (`11_historial_estados.sql`)

Cabecera que diga, en mayúsculas, que estas dos tablas **no se reconstruyen**:
son historia que no existe en Sigrid y no se puede recuperar.

```sql
CREATE TABLE IF NOT EXISTS compras.historial_estados_fotos (
    observado_en     TIMESTAMPTZ PRIMARY KEY,   -- max(raw.con._ingested_at)
    tomada_en        TIMESTAMPTZ NOT NULL DEFAULT now(),
    es_linea_base    BOOLEAN NOT NULL,
    n_documentos INTEGER NOT NULL, n_cambios INTEGER NOT NULL,
    n_altas INTEGER NOT NULL, n_desaparecidos INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS compras.historial_estados (
    documento_id          BIGINT NOT NULL,        -- con.ide
    tipo_documento_codigo INTEGER NOT NULL,       -- con.tip: 44 o 15
    estado_id             INTEGER,                -- con.est (crudo; se traduce en la vista)
    desde                 TIMESTAMPTZ NOT NULL,   -- primera foto que lo ve en este estado
    hasta                 TIMESTAMPTZ,            -- primera foto que ya no; NULL = vigente
    observado_antes       TIMESTAMPTZ,            -- foto anterior; NULL en la línea base
    es_linea_base         BOOLEAN NOT NULL,
    motivo_cierre         TEXT CHECK (motivo_cierre IN ('CAMBIO', 'DESAPARECIDO')),
    PRIMARY KEY (documento_id, desde));
CREATE UNIQUE INDEX IF NOT EXISTS ux_hist_est_abierto
    ON compras.historial_estados (documento_id) WHERE hasta IS NULL;
```

**Por tramos y no una fila por documento y día.** Es la foto diaria que decidió
el humano guardada sin repetir lo que no cambia: la de cualquier día se
reconstruye con `desde <= día < COALESCE(hasta, ∞)`. Medido: 185.754 documentos
(19.081 contratos y 166.673 facturas) y entre 30 y 130 documentos modificados
al día; por tramos son ~20 MB de línea base y < 50.000 filas al año; una fila
por día serían 68 M filas y ~6 GB al año en un disco compartido de 64 GB.

**La foto, en un bloque `DO` (una transacción con el fichero)**, con los
literales del dominio:

1. `v_obs := max(_ingested_at) FROM raw.con`; `v_ult := max(observado_en)` de
   `historial_estados_fotos`. SI `v_obs` es NULL o `v_obs <= v_ult` → `RAISE
   NOTICE` y `RETURN` (R7).
2. `n_actual` = documentos de `raw.con` con `tip IN (44, 15)`; `n_abiertos` =
   tramos con `hasta IS NULL`. SI `n_abiertos > 0 AND n_actual < 0.98 *
   n_abiertos` → `RAISE EXCEPTION` con las dos cifras (R6).
3. Cerrar cambiados: `UPDATE ... SET hasta = v_obs, motivo_cierre = 'CAMBIO'`
   donde el tramo está abierto y `con.est IS DISTINCT FROM estado_id` (R2).
4. Cerrar desaparecidos: igual con `'DESAPARECIDO'` donde ya no hay fila en
   `raw.con` con ese `ide` y ese `tip` (R5).
5. Abrir: `INSERT` de cada documento de `raw.con` (`tip IN (44, 15)`) sin tramo
   abierto, con `desde = v_obs`, `observado_antes = v_ult`, `es_linea_base =
   (v_ult IS NULL)` (R2-R4).
6. `INSERT` en `historial_estados_fotos` con los contadores (R8).

**Prohibido en el fichero**: `DROP`, `TRUNCATE` y `DELETE` (test, R8). Un
documento que reaparece abre un tramo nuevo sin línea base. Un estado `NULL`
se guarda tal cual.

**`compras.v_estado_documentos`** (`CREATE OR REPLACE VIEW`, después del `DO`):
del tramo abierto, `documento_id`, `tipo_documento_codigo`, `tipo_documento`
(`CASE tip WHEN 44 THEN 'CONTRATO' WHEN 15 THEN 'FACTURA' END`), `estado_id`,
`estado_codigo`, `estado` (`LEFT JOIN LATERAL compras.fn_estado_documento(tip,
estado_id)`), `en_estado_desde` y `cambio_observado_tras` (fechas en
`Europe/Madrid` de `desde` y `observado_antes`), `antiguedad_es_minima`
(`es_linea_base`), `dias_en_estado` (`CURRENT_DATE` de Madrid − `en_estado_desde`)
y `ultima_foto` (`max(observado_en)`, para la frescura). Se calcula al consultar:
los días avanzan solos, y `ultima_foto` dice si la historia se ha parado.

## 4 · Dominio: `etl_sigrid/domain/historial_estados.py`

Patrón de `domain/comparativos.py`: literales una vez aquí, funciones puras como
oráculo, y `test_f067_sql.py` comprueba que el SQL lleva **los mismos**.

```python
TIPOS_HISTORIAL: tuple[int, ...] = (44, 15)          # contrato, factura
UMBRAL_PRESENCIA: Decimal = Decimal("0.98")
MOTIVOS_CIERRE: tuple[str, ...] = ("CAMBIO", "DESAPARECIDO")
EPOCA_DELPHI: date = date(1899, 12, 30)
@dataclass(frozen=True) class Tramo: documento_id, tipo, estado_id, desde, hasta, observado_antes, es_linea_base, motivo_cierre
class FotoIncompletaError(Exception)
def aplicar_foto(tramos: list[Tramo], actuales: dict[int, tuple[int, int | None]],
                 observado_en: datetime, ultima_foto: datetime | None) -> list[Tramo] | None
    # None si no hay foto nueva (R7); FotoIncompletaError (R6); si no, los tramos resultantes
def dias_en_estado(desde: date, hoy: date) -> int
def fecha_delphi(valor: float | None) -> datetime | None   # 46300.537627 -> 2026-10-05 12:54:10
```

`actuales` es `{con.ide: (tip, est)}` ya filtrado a `TIPOS_HISTORIAL`.
`fecha_delphi(0)` y `None` → `None`. En SQL, `compras.fn_sigrid_tiempo(v)`:
`CASE WHEN v > 0 THEN TIMESTAMP '1899-12-30' + v * INTERVAL '1 day' END`
(`IMMUTABLE`). **Ojo, medido**: SQL Server convierte el mismo número con época
1900-01-01 y da dos días más; la buena es la de Delphi (comprobado con la fila
modificada hoy).

## 5 · `01_documentos.sql` y `10_necesidades.sql`

**CONTRATOS**, al final y en este orden: `forma_pago_id` (`NULLIF(c.pagide,0)`),
`forma_pago` (`raw.auxpag.res`; no `compras.formas_pago`, que se construye en
`04`), `retencion_garantia_porcentaje` (`ROUND(valpor * 100, 4)`),
`retencion_garantia_concepto` (`con.res` del concepto) y
`fecha_ultima_modificacion` (`compras.fn_sigrid_tiempo(con.tiemod)`). La
retención: `LEFT JOIN LATERAL` a `raw.ctrrec r JOIN raw.con x ON x.ide =
r.recide WHERE r.docide = c.ide AND x.cod LIKE 'RET%' ORDER BY r.pos, r.ide
LIMIT 1` (R13; el `LIMIT 1` es la guarda de grano: hoy un solo contrato tiene
dos). Sin `WHERE` en el `FROM` externo (test de F-084 intacto).

**ALBARAN_LINEAS** (y con D3 **CONTRATO_LINEAS** y **FACTURA_LINEAS**), al final:
`NULLIF(btrim(l.cod2), '') AS codigo_alternativo`, `NULLIF(l.dncide, 0) AS
necesidad_id`, `NULLIF(l.dncproide, 0) AS necesidad_linea_id`. Índice en
`albaran_lineas (necesidad_linea_id)`.

**`compras.necesidades`** (`DROP TABLE IF EXISTS ... CASCADE` + `CREATE TABLE
AS`, como el resto): de `raw.dnc d JOIN raw.con c ON c.ide = d.ide`:
`necesidad_id` (PK), `codigo_necesidad` (`c.cod`), `nombre` (`c.res`),
`fecha_alta` (`fn_sigrid_date(c.fec)`), `obra_id` (`NULLIF(d.obride,0)`),
`codigo_obra`, `nombre_obra` (`raw.con` de la obra), `es_la_de_la_obra`
(`raw.obr.dncide = d.ide` para su obra) y `n_lineas` (`count` de `raw.dncpro`).
No publica estado: los 277 están en «En curso» (tip 36, `E`).

## 6 · `descompuestos/06_views.sql`

Al final de la lista de columnas de `v_pbi_planif_jo` y `v_pbi_master_planif_jo`:
`(SELECT NULLIF(n.dncide, 0) FROM raw.dncpro n WHERE n.ide = dncpro_id) AS
necesidad_id`. Subconsulta escalar por la PK de `raw.dncpro` y no `JOIN`, para
que el `FROM descompuestos.lineas WHERE origen = '...'` que fija
`test_f097_r24` no cambie. Lee `raw` y no `compras.necesidades` a propósito:
`build_compras` hace `DROP ... CASCADE` cada noche y se llevaría estas vistas
por delante. `06` no entra en el sello: no retrocea nada.

## 7 · Diccionario

`compras.yaml` (`paso_etl: build_compras`, `refresco: nocturno`):
- `historial_estados`: grano tramo, `clave_negocio: [documento_id, desde]`,
  que es historia que **no se reconstruye**, que empieza el día del despliegue,
  que `es_linea_base` = «ya estaba; desde cuándo, no se sabe» y la fórmula de la
  foto de un día. `historial_estados_fotos`: una fila por foto, clave
  `observado_en`; para saber si la historia tiene huecos.
- `v_estado_documentos`: clave `documento_id`; R10 y R11 con esas palabras;
  «más de tres semanas enviado» = `estado_codigo = 'EPF' AND dias_en_estado >
  21` (cierto también con `antiguedad_es_minima`, porque es un mínimo);
  relaciones `contratos.contrato_id` y `facturas.factura_id` → aquí (1:1).
- `contratos`: las cinco columnas; `fecha_ultima_modificacion` con la frase «NO
  es la fecha del cambio de estado» y la medición de D2; penalización (R15);
  descripción reescrita (R16) y la pregunta de «tres semanas» ya sin el «NO».
- `albaran_lineas` (y D3): `codigo_alternativo` = «código 2» (R22, cifras de
  cobertura), `necesidad_id`, `necesidad_linea_id`; relaciones de R25.
- `necesidades`: R24. `comparativos`: R26.
- `descompuestos.yaml`: `codigo_alternativo` (R23) en `lineas` y vistas;
  `necesidad_id` en las dos vistas.
- `00_global.yaml`: `version` +1, comentario de versión que corrige el de la 43
  («no se puede saber» pasa a «se sabe desde el despliegue»), preguntas: P23
  contratos enviados hace más de tres semanas (`parcial`, `bloqueada_por:
  F-067` hasta 21 días después del despliegue), P24 cuándo cambió de estado la
  factura X, P25 comparativos por actividad y adjudicatarios con varias
  actividades, P26 albaranes por código 2.

## 8 · Tests (sin red ni BBDD)

- `test_f067_dominio.py`: `aplicar_foto` con línea base, cambio, alta, baja,
  reaparición, foto vieja (None) y guarda del 98 % en el borde (97,9 / 98,0);
  `dias_en_estado`; `fecha_delphi(46300.537627)`, 0 y None.
- `test_f067_sql.py` (patrón de `test_f084_sql.py`): los tipos, el 0.98, los
  motivos y la época del SQL **son** los del dominio; `11` no contiene `DROP`,
  `TRUNCATE` ni `DELETE`; usa `CREATE TABLE IF NOT EXISTS` y `RAISE EXCEPTION`;
  columnas nuevas AL FINAL y las de siempre en su orden (contratos y las tres
  de líneas); `LIMIT 1` y `LIKE 'RET%'` en la retención; `06_views.sql`
  conserva sus `FROM ... WHERE origen` y su recuento de vistas. R21 (sello
  intacto) lo verifica el reviewer con `git diff main --stat`, no un test: la
  imagen no lleva `.git`.
- `test_f067_diccionario.py`: ficha y clave por objeto nuevo; frases de R10,
  R11, R14, R15, R22-R24; relaciones de R25.
- `test_f047_steps.py`: lista de `build_compras` con `10` y `11`.
- Rigor **crítico**: fase RED de cada R con test, traza en
  `progress/impl_F-067.md`; cobertura de líneas cambiadas; campaña de mutación
  COMPLETA sobre `domain/historial_estados.py`, 0 supervivientes o justificación
  aceptada por el humano.

## 9 · Coste y riesgos

- **Coste nocturno**: foto < 10 s (anti-joins sobre 186 k filas, cientos de
  escrituras); `necesidades` 277 filas; columnas nuevas, despreciable.
- **Una foto perdida no se recupera**: si `build_compras` falla o se salta una
  noche (también si falla `08`/`09`, que van antes), el tramo siguiente lleva
  `observado_antes` de dos noches atrás y la ventana del cambio se ensancha. Se
  ve en `historial_estados_fotos`. Se prefiere a un paso propio por simplicidad;
  si pasa a menudo, la foto sale a su paso.
- **Ingesta a medias**: R6 lo para. Un `raw.con` viejo: R7.
- **Si alguien borra las tablas, la historia se pierde**: lo dice la cabecera,
  la ficha y `ARCHITECTURE.md`. No hay copia en Sigrid.
- **`tiemod` engaña** (D2): por eso nunca entra en `dias_en_estado`.
- **F-085** podrá reconstruir hacia atrás desde `dbo.log` (149.010 registros de
  contrato): sustituiría tramos de línea base, no los de la foto.
- **Descartado**: una fila por documento y día (×365 en disco); `con.tiemod`
  como antigüedad; columnas en `descompuestos.lineas` (cambia el sello y
  retrocea el master); vistas de `descompuestos` leyendo `compras` (el
  `CASCADE` nocturno las borraría); objetos nuevos para el acceptance 3.
