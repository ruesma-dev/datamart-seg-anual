# F-138 · Diseño: las alarmas de los documentos de Sigrid y la marca «liquidatoria»

Mediciones: `progress/spec_F-138.md`. Decisiones (2026-10-14): `requirements.md`.

## Encaje y límite del servicio

- **Ingesta**: `conala` (todas las familias menos empleados) y `auxala` en
  `raw` por la vía de siempre (`ingest_raw` + `tables_sigrid.yaml`):
  `stream_table` compone `WHERE [ide] > ? AND (<where>)` y
  `check-raw-recuentos` cuenta con el mismo `where` (patrón F-090).
- **Negocio**: un fichero en `compras` (`build_compras`, sub-paso 15, el último)
  que escribe en `compras` y en el esquema nuevo `compras_restringida` (D9). Lee
  `raw` y lo que construye `01`. No toca ningún objeto existente.
- **Límite**: el ETL LEE las alarmas (solo lecturas de Sigrid). Publicar las de
  todos los documentos en `compras` vale porque el 86 % son de compras y el
  resto son pocas (ventas 4.647, proveedores 470, otras ~1.200).

## Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/liquidatoria.py` | Oráculo puro (R4-R10) |
| `etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql` | guarda, funciones, las dos `documento_alarmas` y los tres objetos de la marca |
| `config/diccionario/compras_restringida.yaml` | ficha de `compras_restringida.documento_alarmas` |
| `tests/test_f138_dominio.py` | R3-R10 |
| `tests/test_f138_ingesta_sql.py` | R1-R2, R11-R21 sobre el TEXTO del YAML, del SQL y de `SUB_PASOS` (no se ejecuta SQL) |
| `tests/test_f138_grants.py` | R22-R23: listas de `settings`, `.env.example` y `02_roles.sql` |
| `tests/test_f138_diccionario.py` | R24-R27 |

## Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | + `conala` y + `auxala` al final, con comentario (cifras, lista explícita, la 43 fuera, 33/35 restringidas aguas abajo, `fec1`/`fec2` vacías, `creusu` es un login) |
| `etl_sigrid/application/steps/build_compras_step.py` | + `_SubStep("alarmas_liquidatoria", "15_alarmas_liquidatoria.sql", "compras", "documento_alarmas")` al final, comentario y docstring |
| `sql/compras/00_setup.sql` | + `CREATE SCHEMA IF NOT EXISTS compras_restringida;` (como `contabilidad/00_setup.sql`) |
| `config/settings.py`, `.env.example` | `compras_restringida` en `DEFAULT_VETOED_SCHEMAS` y `DEFAULT_RESTRICTED_SCHEMAS` (y sus `PG_*`), con su línea en el comentario de cada lista |
| `etl_sigrid/domain/diccionario.py` | `ESQUEMAS_DEL_DATAMART` + `compras_restringida` (16) y su línea en el comentario |
| `infra/sql/02_roles.sql` | ver § Permisos |
| `config/diccionario/compras.yaml` | fichas `documento_alarmas` (general), `documento_liquidatoria`, `contrato_liquidacion`, `facturas_tras_liquidacion`, `fn_texto_normalizado`, `fn_clase_liquidacion`; relaciones en `facturas`, `albaranes`, `contratos` |
| `config/diccionario/raw.yaml` | fichas `conala` y `auxala`; «Son 76 tablas» |
| `config/diccionario/00_global.yaml` | esquema `compras_restringida`, regla `R-COMPRAS-RESTRINGIDA`, `version` +1, «las 76 tablas» (~522, ~1130) |
| `docs/ARCHITECTURE.md`, `CLAUDE.md` (mapa) | 76 tablas, `conala`/`auxala`, y `compras_restringida` junto a las otras dos restringidas |
| tests que fijan el censo 74 (`test_f085_sql`, `test_f085_diccionario`, `test_f090_diccionario`, `test_f090_ingesta_sql`, `test_f095_retenciones_contables`, `test_f097_ingesta_descompuestos`) y las listas de esquemas (`test_f006_formato`, `test_f037_diccionario`, `test_f037_grants`, `test_f057_personal`, `test_f135_grants`) | 74 -> 76; 15 -> 16; + `compras_restringida`. Nada más |
| `azure-apps/datamart_seg_anual.md` (otro repo, commit propio, sin push) | consume 76 tablas; expone los objetos; el contrato para `mcp-bbdd` (§ Despliegue, paso 7) |

## Ficheros que NO se tocan

- `sql/compras/01_documentos.sql` y `07_texto.sql` (D7; F-128 y F-093 tocarán `01`).
- `sql/compras/03_views.sql`: se COPIA su cadena factura -> contrato.
- `grants.py` y `apply_grants_step.py`: son de listas desde F-135/F-136; con
  `settings` cambiado conceden, vetan y VERIFICAN el esquema nuevo solos (F-037 § 6).
- `ingest_raw_step.py`, `sigrid_api_client.py`, `objetos_pendientes.yaml`.

## Dominio · `etl_sigrid/domain/liquidatoria.py`

```python
FAMILIAS_ALARMAS: Final[dict[int, str]] = {1: "INFORME", ..., 54: "CONTRATO_VENTA"}  # R4, sin la 43
FAMILIA_EMPLEADOS: Final[int] = 43
FAMILIAS_MARCA: Final[tuple[int, ...]] = (14, 15)
FAMILIAS_RESTRINGIDAS: Final[frozenset[int]] = frozenset({33, 35})   # D9
TRADUCCION_ORIGEN / TRADUCCION_DESTINO: Final[str]                   # 44 caracteres cada una
PATRON_MENCION, PATRON_NEGADA, PATRON_CARTA, PATRON_DUDOSA, PATRON_REMITE: Final[str]
PRECEDENCIA = ("NEGADA", "LIQUIDATORIA", "CARTA_LIQUIDACION", "DUDOSA", "REMITE")
CLASES_CIERRE = frozenset({"LIQUIDATORIA", "CARTA_LIQUIDACION"})
def filtro_conala() -> str; def normalizar(t) -> str; def clasificar(t) -> str | None
def marca_documento(clases) -> str | None; def es_restringida(tip: int) -> bool
def fecha_hora_creacion(crefec, crehor) -> datetime | None
```

`normalizar` = `translate` -> `re.sub(r"[^A-Za-z0-9]+", " ")` -> `.upper()` ->
`.strip()`: el `upper` DESPUÉS de dejar solo ASCII, para que Python y
PostgreSQL coincidan con cualquier `LC_CTYPE`. La regla vive UNA vez aquí y los
tests comparan sus literales con el SQL y el YAML (patrón de F-090 y F-080).

**Lista explícita y no `tip <> 43`** (D3): ante una familia NUEVA con alarmas la
lista falla CERRADA (no entra hasta que alguien la añade y decide si es
restringida); la exclusión fallaría ABIERTA (una alarma en una nómina entraría
sola en `raw` y en `compras`). La ficha de `raw.conala` deja escrita la consulta
de censo (`SELECT c.tip, COUNT(*) ... GROUP BY c.tip`) para revisarla.

**Precedencia**. Por alarma (R6): NEGADA primero (la negación es explícita);
CARTA antes que DUDOSA (Negocio dijo qué significa); DUDOSA antes que
LIQUIDATORIA («PREVISIÓN DE LIQUIDACIÓN» no lo es aún). Por documento (R9): la
declarada gana a la carta porque la carta se pide justo cuando la factura NO lo
decía; si otra alarma lo dice, es liquidatoria declarada. Las dos cierran el
contrato (`cierra_contrato`); `pendiente_carta_liquidacion` las distingue.

## SQL · `sql/compras/15_alarmas_liquidatoria.sql`

Una sola llamada a `execute_sql_file`, o sea UNA transacción (como `tesoreria`):
si una guarda salta, se deshace todo y quedan las tablas de la noche anterior.

1. **Guarda de ingesta** (`DO`): sin alarmas de factura en `raw.conala`, `RAISE`.
2. **Funciones** `IMMUTABLE`: `compras.fn_texto_normalizado(t)` =
   `btrim(upper(regexp_replace(translate(COALESCE(t, ''), '<ORIGEN>', '<DESTINO>'), '[^A-Za-z0-9]+', ' ', 'g')))`;
   `compras.fn_clase_liquidacion(t)` = `CASE` en el orden de R6.
3. **`compras_restringida.documento_alarmas`** (la completa): `raw.conala a JOIN
   raw.con c ON c.ide = a.conide LEFT JOIN raw.auxala x ON x.ide =
   NULLIF(a.alaide, 0)`. `familia` = `CASE c.tip WHEN 1 THEN 'INFORME' ...`;
   `restringido` = `c.tip IN (33, 35)`; `motivo_restriccion` = la familia si
   restringido. `creada_el` = `fn_sigrid_date(crefec) + make_interval(...)` con
   `CASE` que deja NULL las horas imposibles (oráculo R10); `creada_por` =
   `NULLIF(btrim(creusu), '')`. PK `alarma_id`; índices `documento_id`, `familia`.
4. **`compras.documento_alarmas`** (la general): las mismas columnas salvo
   `restringido` y `motivo_restriccion`, `WHERE NOT restringido` sobre la
   completa. PK e índices iguales.
5. **Guarda de la restricción** (`DO`, como R12 de F-037): recalcula desde
   `raw.con` que ninguna fila de la general es de 33 o 35 y que general +
   restringidas = completa; si no, `RAISE EXCEPTION 'F-138: ...'`.
6. **`compras.documento_liquidatoria`**: CTE `al` sobre la GENERAL con
   `tipo_documento_codigo IN (14, 15)` (`marca` por `bool_or` en el orden de
   `PRECEDENCIA`, `string_agg(... ORDER BY alarma_id)`, `min(creada_el)` de las
   que cierran); CTE `memo` de `raw.con` (`tip IN (14, 15) AND tex ILIKE
   '%liq%'`); universo = las dos UNION; booleanos con `COALESCE(..., FALSE)`.
7. **`compras.contrato_liquidacion`**: CTE `fac_ctr` = `DISTINCT factura_id,
   COALESCE(fl.contrato_id_directo, alb.contrato_id, alb_l.contrato_id_linea)`
   con los `LEFT JOIN` de `fact_por_ctr` de `v_pbi_contrato_consumo`; `alb_ctr`
   para ALBARAN y PROFORMA; factura de cierre con `DISTINCT ON (contrato_id)
   ORDER BY fecha, factura_id` entre las de `cierra_contrato`; base
   `compras.contratos` con LEFT JOIN (19.127 filas, `facturas_terminadas` FALSE
   y no NULL sin cierre). PK `contrato_id`; índice `obra_id`.
8. **`compras.facturas_tras_liquidacion`**: `fac_ctr` JOIN contratos con cierre
   JOIN `compras.facturas` con `fecha > fecha_cierre`. PK (`contrato_id`,
   `factura_id`); ~1.170 filas. Es el AVISO (c), consultable sin cruzar nada.

Coste: ~45.750 + ~45.720 alarmas y unas decenas de miles de filas más; segundos.

## Ingesta · `config/tables_sigrid.yaml`

`conala`: `id_column: ide`, `incremental_column: null`, `exclude_columns: []`,
`where: "conide IN (SELECT ide FROM dbo.con WHERE tip IN (1, 4, 5, 11, 12, 14,
15, 17, 20, 25, 33, 35, 40, 42, 44, 46, 54))"`. `auxala`: entera, `tiemod`.
Medido: 45.747 filas y 1,79 MB en ~2 s en una petición (5 páginas de 10.000; la
subconsulta se repite por página, como en `gra`: estimado < 15 s). `auxala`, 4.
`raw` ya está vetado al estándar y al total (F-135, F-136): las alarmas de
recursos y partes en `raw.conala` no abren nada.

## Permisos (D9): el patrón «módulo + `_restringida`»

Mismo patrón que `contabilidad_restringida` (F-135) y `tesoreria_restringida`
(F-037): los permisos de PostgreSQL se dan POR ESQUEMA, así que lo que el
estándar no debe leer vive en un esquema que nunca se le concede. **Descartado**:
`REVOKE` por tabla en `compras` (`PG_EXCLUDED_TABLES`) —quitaría la tabla entera
también al total, que hereda del estándar— y una vista con filtro por usuario
—el MCP conecta con dos logins fijos, no con el de quien pregunta—.

- **`settings`**: `compras_restringida` en VETADOS (el estándar y Power BI no lo
  leen; `apply_grants` lo revoca cada noche y FALLA si lo sigue leyendo) y en
  RESTRINGIDOS (lo lee `sigrid_dm_restringido_ro`; el total, por pertenencia).
  No en `DEFAULT_TOTAL_VETOED_SCHEMAS` (`raw` solo).
- **`02_roles.sql`**: `CREATE SCHEMA IF NOT EXISTS compras_restringida` con `SET
  ROLE sigrid_dm_etl`; `compras_restringida` en los dos `ARRAY` de vetados al
  estándar del 5 ter (NO en el del total); `GRANT USAGE`, `SELECT ON ALL TABLES`
  y `ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl` al autorizado; y en las
  comprobaciones finales (propietario, `lee = f` del estándar, columna
  `compras_restringida = t` del total). Un test compara estas listas con `settings`.
- **Diccionario**: `R-COMPRAS-RESTRINGIDA` (bloqueante, ámbito los dos
  `documento_alarmas`): por defecto `compras`; la restringida solo para el
  perfil total, sin rodear el «permission denied», nunca se suman. La ficha de la
  general dice que le faltan las alarmas de recursos y partes (27 hoy).

## Despliegue (MANUAL, en este orden, tras el review)

1. El job no fija `PG_VETOED_SCHEMAS` ni `PG_RESTRICTED_SCHEMAS` (`az containerapp
   job show`, solo nombres); si los fija, cambiarlos allí. Imagen con tag fechado
   y job apuntado a ella (comprobar el tag).
2. Humano, como administrador: `psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn` (cabecera del fichero)
   ANTES del build (crea el esquema con dueño `sigrid_dm_etl`).
3. `python main.py ingest --table conala --full` y `... --table auxala --full`.
4. `python main.py build-compras` (anotar duración) y `python main.py apply-grants`
   (`verificacion`, `verificacion_total`, `acceso_total` = ok, R30).
5. `python main.py check-raw-recuentos` y los recuentos de R28-R29 por SQL de solo lectura.
6. `python main.py publicar-diccionario` (lo autoriza el humano) y los tres
   `check-*` (`check-diccionario`, `check-declarados`, `check-unicidad`).
7. Pedir a `mcp-bbdd` que añada `compras_restringida` a su lista blanca común y
   reinicie (cachea el diccionario); después, las preguntas de R31 con la cuenta
   total y la negativa con la estándar.
8. Primera nocturna: `python main.py timings` (ingesta de `conala`/`auxala` y sub-paso).

## Riesgos

- **Regla heurística sobre texto libre** (697 variantes): se publica el texto
  íntegro y la clase de cada alarma; los casos raros van en la ficha.
- **`\b` en PostgreSQL es RETROCESO**: por eso `(^| )` sobre el texto normalizado.
- **El prefiltro `ILIKE '%liq%'` del memo** no ve «LÍQ…»: ninguna variante medida.
- **Familia 25 en la general**: medido que sus 88 efectos con alarma son de la
  cartera general de F-037; si un día un efecto de personal tuviera alarma, la
  regla se ampliaría con el criterio de `domain/tesoreria.py`, no a mano.
- **Versión del diccionario**: la siguiente libre al implementar (hoy 51 -> 52).
