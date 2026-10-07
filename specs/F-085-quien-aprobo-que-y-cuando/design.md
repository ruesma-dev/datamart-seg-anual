<!-- specs/F-085-quien-aprobo-que-y-cuando/design.md -->
# F-085 · Diseño · Quién aprobó qué y cuándo

Cifras y pruebas: `progress/spec_F-085.md`. Requisitos: `requirements.md`.
Decisiones D1-D8 cerradas por el humano el 2026-10-07 (§8); D4 cambió.

## 1. Encaje y límite

- **Dentro del límite del servicio**: dos tablas de Sigrid (`rac` sin filtro y
  `usu` sin credenciales) y dos objetos publicados. Nada cruza a `sigrid-api`,
  `albaranes` ni `partes`.
- **`compras.documento_procesos`**: tres de las cuatro familias son de compras
  y se cruzan por `documento_id` con `compras.facturas`, `contratos`,
  `comparativos` y `v_estado_documentos`. La obra entra por «que afecte a todo»:
  partir por esquema obligaría a saber a cuál preguntar según el tipo.
- **`personal.usuarios_sigrid`**: el DNI y el enlace al empleado van al único
  esquema autorizado para datos personales (F-057), bajo su GRANT por esquema.
  En `compras` solo login y nombre (D4).
- **Fuera**: `dbo.log` (F-105), la antigüedad del estado de F-067 (D7), el
  enlace factura→asiento con importes (F-091).

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/documento_procesos.py` | `FAMILIAS`, `COLUMNAS_CREDENCIALES_USU`, `Paso`, `PasoEncadenado`, `hora_sigrid`, `normalizar_login`, `encadenar`, `empleado_de_usuario` (§4) |
| `etl_sigrid/infrastructure/postgres/sql/compras/12_documento_procesos.sql` | `compras.documento_procesos` (§5) |
| `etl_sigrid/infrastructure/postgres/sql/personal/06_usuarios_sigrid.sql` | `TRUNCATE` + `INSERT` de `personal.usuarios_sigrid` (§6) |
| `tests/test_f085_dominio.py` | oráculo caso a caso: R3, R10-R15, R18 |
| `tests/test_f085_sql.py` | texto de SQL y YAML, sub-pasos: R1, R2, R4-R9, R11-R21 |
| `tests/test_f085_diccionario.py` | fichas y documentos: R22-R28 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | `rac`: `where: null`, comentario nuevo (R1). Entrada nueva `usu` (`id_column: ide`, sin `incremental_column`, `where: null`, las diez exclusiones de R2 con su motivo) junto a las de personal. Bloque «LO QUE SIGRID NO GUARDA»: el historial de procesos SÍ está, en `rac` (R28) |
| `etl_sigrid/application/steps/build_compras_step.py` | `SUB_PASOS` + `12` DETRÁS de `11` (si el `12` falla, la foto de esa noche ya está tomada); docstring |
| `etl_sigrid/infrastructure/postgres/sql/personal/00_setup.sql` | `CREATE TABLE IF NOT EXISTS personal.usuarios_sigrid` (patrón del esquema: aquí no se dropea nada) |
| `etl_sigrid/application/steps/build_personal_step.py` | `SUB_PASOS` + `06_usuarios_sigrid.sql` (cuenta `personal.usuarios_sigrid`) al final |
| Tests del censo 71 → 72 | `tests/test_f066_ingesta_raw.py` y `tests/test_f074_ingesta_censo.py` (`TOTAL_TABLAS`), `tests/test_f097_ingesta_descompuestos.py:189` (`== 71`), `tests/test_f095_retenciones_contables.py` r31 («71 tablas» en ARCHITECTURE y azure-apps), comentarios de `tests/test_f107_contrapartidas_cuentas.py` (su `>= 70` no cambia) |
| `tests/test_f095_retenciones_contables.py` | `test_f095_r9_rac_declarada_con_filtro` → `where is None` (renombrado `..._sin_filtro_desde_f085`); `..._el_filtro_explica_sus_cifras` sigue valiendo |
| `tests/test_f047_steps.py` | lista de sub-pasos de compras (~l. 56) + `12`; el test de ~l. 169-187 pasa a «`12` es el último y `11` justo antes». Es de F-067 pero fija el ORDEN del paso, no su objeto |
| `tests/test_f057_personal.py` | `FICHEROS_PERSONAL` + `06_usuarios_sigrid.sql` |
| `config/diccionario/compras.yaml` | ficha nueva `documento_procesos` (R22, R23); `comparativos.fecha_aprobacion` y `comparativo_firmas` (R26) |
| `config/diccionario/personal.yaml` | ficha nueva `usuarios_sigrid` (R24) |
| `config/diccionario/raw.yaml` | fichas `rac` (sin filtro) y `usu` (nueva); «Son 71 tablas» → 72 (R25) |
| `config/diccionario/00_global.yaml` | `version` +1 con comentario; «las 71 tablas» → 72 (R27) |
| `docs/ARCHITECTURE.md` | título y cuerpo de «Qué se copia de Sigrid» (72, `rac` sin filtro, `usu` sin credenciales); «Lo que Sigrid NO guarda», primera viñeta (R28) |
| `../azure-apps/datamart_seg_anual.md` | 72 tablas, `rac` sin filtro, `usu`, los dos objetos nuevos (R28); commit local en ese repositorio |

## 4. Ficheros que NO se tocan

- `sql/compras/11_historial_estados.sql`, `domain/historial_estados.py` y las
  fichas de `historial_estados`, `historial_estados_fotos`, `v_estado_documentos`
  (F-067, D7). Hallazgo y propuesta: `progress/spec_F-085.md` §2.
- `sql/retenciones/03_apuntes_contables.sql`: ya filtra `asiide <> 0` (R5).
- `sql/compras/09_comparativos_detalle.sql`, `compras.comparativo_firmas` (D6).
- `config/settings.py`: `raw.usu` queda legible por el MCP como el resto de
  `raw` (sin credenciales, sin DNI, sin correo; login y nombre ya salen en
  `compras`); `personal` ya está en los esquemas concedidos.

## 4 bis. Dominio: `etl_sigrid/domain/documento_procesos.py`

Capa `domain`, sin imports de infraestructura; la regla la ejecuta el SQL y aquí
vive una vez (patrón de `domain/historial_estados.py`).

```python
FAMILIAS: Final[dict[int, str]] = {15: "FACTURA", 44: "CONTRATO",
                                   46: "COMPARATIVO", 42: "OBRA"}
COLUMNAS_CREDENCIALES_USU: Final[frozenset[str]] = frozenset(
    {"cla", "fir", "feccla", "diascla", "sid", "cerid"})
EMPRESA_PREFERENTE: Final[int] = 1

@dataclass(frozen=True, slots=True)
class Paso:  # paso_id, documento_id, estado_origen_id, estado_destino_id,
             # fecha: date | None, hora: time | None
@dataclass(frozen=True, slots=True)
class PasoEncadenado:  # paso, orden, es_ultimo, encaja_con_anterior: bool | None,
                       # dias_desde_anterior: Decimal | None

def hora_sigrid(hhmmss: int | None) -> time | None: ...
def normalizar_login(login: str | None) -> str | None: ...   # BTRIM + UPPER; '' -> None
def encadenar(pasos: Iterable[Paso]) -> list[PasoEncadenado]: ...
def empleado_de_usuario(candidatos: Sequence[tuple[int, int]]) -> int | None: ...
```

- `hora_sigrid`: `None`/0 → `None`; fuera de 1..235959 o minutos/segundos ≥ 60
  → `None`; si no, `time(h, m, s)`.
- `encadenar`: agrupa por documento; ordena por (`fecha` NULLS LAST, `hora`
  NULLS LAST, `paso_id`); numera desde 1; `es_ultimo`; `encaja_con_anterior`;
  `dias_desde_anterior` = diferencia de momentos en días a 2 decimales, `None`
  si falta alguno.
- `empleado_de_usuario`: recibe `(empleado_id, empresa)` de las fichas de
  empleado cuyo código es el `codemp`; uno → ése; varios → el único de la
  empresa 1; ninguno, o varios sin uno único de la empresa 1 → `None`.

## 5. SQL: `sql/compras/12_documento_procesos.sql`

Cabecera: qué construye, de qué lee (`raw.rac`, `raw.con`, `raw.usu`,
`raw.conest` vía `compras.fn_estado_documento`), que los literales son los del
dominio y que se reconstruye cada noche (DROP + CREATE, como el resto de compras).

```sql
DROP TABLE IF EXISTS compras.documento_procesos;
CREATE TABLE compras.documento_procesos AS
WITH usuarios AS (                                  -- login normalizado, único (R20)
    SELECT UPPER(BTRIM(u.cod)) AS login_norm, MIN(u.res) AS nombre
    FROM raw.usu u WHERE BTRIM(u.cod) <> '' GROUP BY UPPER(BTRIM(u.cod))
), pasos AS (
    SELECT r.ide AS paso_id, r.conide AS documento_id, c.tip AS tipo_documento_codigo,
           c.cod AS codigo_documento, NULLIF(r.conproide, 0) AS proceso_id,
           BTRIM(r.res) AS proceso, r.est1 AS estado_origen_id, r.est2 AS estado_destino_id,
           r.usu AS usuario, NULLIF(BTRIM(us.nombre), '') AS nombre_usuario,
           compras.fn_sigrid_date(r.fec) AS fecha,
           CASE WHEN r.hor BETWEEN 1 AND 235959 AND (r.hor / 100) % 100 < 60
                     AND r.hor % 100 < 60
                THEN make_time(r.hor / 10000, (r.hor / 100) % 100, r.hor % 100) END AS hora,
           NULLIF(r.asiide, 0) AS asiento_id
    FROM raw.rac r
    JOIN raw.con c ON c.ide = r.conide                      -- R16
    LEFT JOIN usuarios us ON us.login_norm = UPPER(BTRIM(r.usu))   -- R14
    WHERE c.tip IN (15, 44, 46, 42)                         -- FAMILIAS
), ordenados AS (
    SELECT p.*, p.fecha + p.hora AS momento, ROW_NUMBER() OVER w AS orden,
           COUNT(*) OVER (PARTITION BY p.documento_id) AS n_pasos,
           LAG(p.estado_destino_id) OVER w AS destino_anterior,
           LAG(p.fecha + p.hora) OVER w AS momento_anterior
    FROM pasos p
    WINDOW w AS (PARTITION BY p.documento_id
                 ORDER BY p.fecha NULLS LAST, p.hora NULLS LAST, p.paso_id)
)
SELECT o.paso_id, o.documento_id, o.tipo_documento_codigo,
       CASE o.tipo_documento_codigo WHEN 15 THEN 'FACTURA' WHEN 44 THEN 'CONTRATO'
            WHEN 46 THEN 'COMPARATIVO' WHEN 42 THEN 'OBRA' END AS familia,
       o.codigo_documento, o.proceso_id, o.proceso,
       o.estado_origen_id, eo.codigo_estado AS estado_origen_codigo, eo.nombre_estado AS estado_origen,
       o.estado_destino_id, ed.codigo_estado AS estado_destino_codigo, ed.nombre_estado AS estado_destino,
       o.usuario, o.nombre_usuario, o.fecha, o.hora, o.momento, o.asiento_id, o.orden,
       (o.orden = o.n_pasos) AS es_ultimo,
       CASE WHEN o.orden = 1 THEN NULL ELSE o.estado_origen_id = o.destino_anterior END
           AS encaja_con_anterior,
       ROUND((EXTRACT(EPOCH FROM (o.momento - o.momento_anterior)) / 86400)::NUMERIC, 2)
           AS dias_desde_anterior
FROM ordenados o
LEFT JOIN LATERAL compras.fn_estado_documento(o.tipo_documento_codigo, o.estado_origen_id)  eo ON TRUE
LEFT JOIN LATERAL compras.fn_estado_documento(o.tipo_documento_codigo, o.estado_destino_id) ed ON TRUE;

ALTER TABLE compras.documento_procesos ADD PRIMARY KEY (paso_id);
CREATE INDEX ix_documento_procesos_documento ON compras.documento_procesos (documento_id, orden);
CREATE INDEX ix_documento_procesos_usuario   ON compras.documento_procesos (usuario);
CREATE INDEX ix_documento_procesos_fecha     ON compras.documento_procesos (fecha);
COMMENT ON TABLE compras.documento_procesos IS '...';   -- grano y fuente, en español
```

- ~1,01 M filas (873.527 + 69.065 + 63.190 + 4.491). `fn_estado_documento` hace
  `LIMIT 1`: no multiplica. 3 orígenes y 4 destinos no casan con `conest` y
  quedan con el literal a NULL. `usuarios` agrupa por login normalizado: no
  multiplica aunque Sigrid repitiera un login.
- **Materializada**, no vista: con dos ventanas por documento, «quién aprobó las
  facturas de la obra X este año» pasaría de los 30 s del MCP.

## 6. SQL: `personal.usuarios_sigrid`

`00_setup.sql`: `CREATE TABLE IF NOT EXISTS personal.usuarios_sigrid (usuario_id
INTEGER PRIMARY KEY, login TEXT NOT NULL, nombre TEXT, desactivado BOOLEAN NOT
NULL, codigo_empleado TEXT, empleado_id INTEGER, dni TEXT)`.
`06_usuarios_sigrid.sql`: cabecera (datos personales autorizados, regla de
`empleado_de_usuario`), `TRUNCATE` + `INSERT` desde `raw.usu`:

- `login` = `BTRIM(cod)`; `nombre` = `NULLIF(BTRIM(res), '')`; `desactivado` =
  `COALESCE(tipdes, 0) <> 0`; `codigo_empleado` = `NULLIF(BTRIM(codemp), '')`.
- `empleado_id`: `LEFT JOIN LATERAL` sobre `raw.con` (`tip = 43`, `cod =
  codemp`) que devuelve el `ide` si hay UNO, y si hay varios el único de
  `emp = 1` (`EMPRESA_PREFERENTE`); si no, NULL. Nunca multiplica: el lateral
  devuelve como mucho una fila.
- `dni` = `NULLIF(BTRIM(e.dni), '')` de `raw.emp e` con `e.ide = empleado_id`
  (lo mismo que `01_recursos.sql`).
- Esperado: 233 filas, 210 con `empleado_id` (189 + 21), ~204 con DNI.

## 7. El diccionario

- `compras.documento_procesos` (`tipo: tabla`, `capa: consumo`, `paso_etl:
  build_compras`, `clave_negocio: [paso_id]`): todas las columnas con
  `significado` (y `nulo_significa`/`valores` donde toque). Descripción, en
  orden: qué es (la ventana «Procesos»), cobertura por familia, historia NETA,
  estado actual = destino del último paso (99,96 / 99,99 / 99,98 / 100 %),
  `encaja_con_anterior` falso = cambio fuera de un proceso (2,2 % de facturas),
  login y nombre con su cobertura y que el DNI está en `personal`, DOCVAL (R23),
  `comparativo_firmas`. Relaciones `N:1` a `compras.facturas.factura_id`,
  `compras.contratos.contrato_id` y `compras.comparativos.comparativo_id`
  («filtrando antes `familia`»). Ejemplos: quién aprobó la factura X y cuándo;
  qué facturas aprobó Fulano este mes; cuánto tarda un contrato del envío a la
  firma; por qué estados pasó el comparativo C.
- `personal.usuarios_sigrid` (`paso_etl: build_personal`, `clave_negocio:
  [usuario_id]`, `claves_alternativas: [[login]]`): datos personales
  autorizados (nombre y DNI), lo que no sube, la regla del empleado con sus
  cifras, relación `N:1` a `personal.recursos` por `empleado_id`, y que el login
  casa con `compras.documento_procesos.usuario` en mayúsculas y sin espacios.
- `raw.usu`: qué es, las diez exclusiones y su motivo, sin DNI ni credenciales.

## 7 bis. Tests (sin red ni BBDD)

- `test_f085_dominio.py`: `hora_sigrid` (0, 165211, 240000, 126000, 125960,
  None); `normalizar_login` (' Magomez ', 'MAGOMEZ', '', None); `encadenar` con
  la FR26/10025 (4 pasos, todos encajan, `es_ultimo` el 4.º, días 0,00 / 6,98 /
  0,02), un salto, empate de fecha y hora, un paso sin fecha, dos documentos
  intercalados; `empleado_de_usuario` (uno, varios con uno de la empresa 1,
  varios sin empresa 1, ninguno).
- `test_f085_sql.py`: entradas `rac` y `usu` del YAML (las exclusiones de `usu`
  contienen `COLUMNAS_CREDENCIALES_USU` y son EXACTAMENTE las diez); censo 72;
  `FAMILIAS` = el `IN` y el `CASE`; el `ORDER BY` de la ventana; `UPPER(BTRIM(`
  en los dos lados del login; `NULLIF(r.conproide, 0)`, `NULLIF(r.asiide, 0)`,
  `BTRIM(r.res)`, `JOIN raw.con` (no `LEFT`), dos `fn_estado_documento` con el
  tipo primero, PK e índices; `SUB_PASOS` de compras acaba en `12` y los de
  personal en `06`; `06` no lee ninguna columna de credenciales; `03_apuntes_contables.sql`
  conserva `WHERE r.asiide <> 0 AND r.conide <> 0`.
- `test_f085_diccionario.py`: fichas nuevas con todas sus columnas; textos
  clave (coberturas, «NETA», login, nombre, DOCVAL, `comparativo_firmas`,
  `dbo.log`, DNI en `personal`); `raw.yaml` sin «ESTA FILTRADA»; R26; `version`
  subió; `pendientes` vacía; ARCHITECTURE y azure-apps con 72 (skip si
  azure-apps no está al lado, como F-095).

## 8. Decisiones (DECIDIDAS por el humano el 2026-10-07) y riesgos

| Id | Decisión | Alternativa descartada |
|---|---|---|
| D1 | Quitar el filtro de `raw.rac` | 2.ª entrada `rac_procesos`: dos tablas de lo mismo |
| D2 | Familias 15, 44, 46, 42 | Todas (2,5 M filas); ampliar es tocar `FAMILIAS` |
| D3 | `rac.tex` excluida | Ingerirla: legible en `raw` con datos de terceros |
| D4 | **Login + nombre en `compras`; DNI y empleado solo en `personal`; `usu` sin credenciales** (cambió: la propuesta era solo login) | Nombre sin ingerir `usu`: imposible; DNI en `compras`: fuera del esquema autorizado |
| D5 | `dbo.log` en F-105 | 8,5 M filas para la marca de firma digital |
| D6 | `confir` sin cambios | Publicar DOCVAL: 3.474 filas sin firma |
| D7 | F-067 intacta; el líder ficha la feature que saca la antigüedad de `rac` y retira la foto tras 1-2 semanas de contraste | Corregirla aquí |
| D8 | Sin `conpro` ni `rol` | Censo a 73-74 por un dato que `rac.res` ya trae |

Riesgos:
- **Ventana**: la nocturna del 07-10 duró 4 h 37 min 44 s, ya por encima de las
  4 h de referencia. F-085 suma ~3 min de ingesta (`usu` son 233 filas) y los
  sub-pasos `12` y `06` (a medir, R32). Se enseña al humano antes de desplegar.
- **Disco**: ~+260 MB en `raw` y ~150-200 MB la tabla nueva, sobre 64 GB.
- **Login sin ficha** (55 de 192, 7 % de las filas): `nombre_usuario` NULL; la
  ficha lo dice. **`nodesa`** no se publica (significado sin confirmar).
- **Despliegue**: reiniciar el MCP tras publicar el diccionario; `compras` y
  `personal` ya están en su lista blanca.
