<!-- specs/F-085-quien-aprobo-que-y-cuando/design.md -->
# F-085 · Diseño · Quién aprobó qué y cuándo

Cifras y pruebas: `progress/spec_F-085.md`. Requisitos: `requirements.md`.

## 1. Encaje y límite

- **Dentro del límite del servicio**: es leer una tabla de Sigrid más (la misma,
  sin filtro) y publicar un objeto en `compras`. Nada cruza a `sigrid-api`,
  `albaranes` ni `partes`.
- **Esquema `compras`**: tres de las cuatro familias son suyas (factura,
  contrato, comparativo) y el objeto se cruza con `compras.facturas`,
  `compras.contratos`, `compras.comparativos` y `compras.v_estado_documentos`
  por `documento_id`. La obra entra por la decisión «que afecte a todo»; partir
  la tabla por esquema obligaría a saber a cuál preguntar según el tipo, que es
  lo que la ficha original quería evitar.
- **Datos personales**: solo el login, como ya publica `compras` (D4). Nada va a
  `personal`.
- **Fuera**: `dbo.log` (F-105), la antigüedad de estado de F-067 (D7), el enlace
  factura→asiento con importes (F-091), el nombre de la persona.

## 2. Ficheros a crear

| Ruta | Qué |
|---|---|
| `etl_sigrid/domain/documento_procesos.py` | `FAMILIAS`, `Paso`, `PasoEncadenado`, `hora_sigrid`, `encadenar` (§4 bis) |
| `etl_sigrid/infrastructure/postgres/sql/compras/12_documento_procesos.sql` | `compras.documento_procesos` (§5) |
| `tests/test_f085_dominio.py` | oráculo: R9-R13 caso a caso |
| `tests/test_f085_sql.py` | texto del SQL, ingesta y sub-paso: R1-R8, R10-R14 |
| `tests/test_f085_diccionario.py` | fichas y documentos: R15-R21 |

## 3. Ficheros a modificar

| Ruta | Cambio |
|---|---|
| `config/tables_sigrid.yaml` | `rac`: `where: null`; comentario reescrito (R1). Bloque «LO QUE SIGRID NO GUARDA» (~l. 784): el historial de procesos SÍ está, en `rac` (R20) |
| `etl_sigrid/application/steps/build_compras_step.py` | `SUB_PASOS` + `12_documento_procesos.sql` (cuenta `compras.documento_procesos`) DETRÁS de `11`: si el `12` falla, la foto de F-067 de esa noche ya está tomada (una noche sin foto es historia perdida); docstring con la línea del `12` |
| `tests/test_f095_retenciones_contables.py` | `test_f095_r9_rac_declarada_con_filtro`: `where is None` y el nombre pasa a `..._sin_filtro_desde_f085`; `test_f095_r9_el_filtro_explica_sus_cifras` sigue pidiendo sus cifras (el comentario las conserva) |
| `tests/test_f047_steps.py` | la lista de sub-pasos (~l. 56) gana `12`, y el test de ~l. 169-187 pasa de «`11` es el último» a «`12` es el último y `11` va justo antes». Es un test de F-067, pero lo que fija es el ORDEN del paso, no su objeto: D7 no lo cubre |
| `config/diccionario/compras.yaml` | ficha nueva `documento_procesos` (R15, R16); `comparativos.fecha_aprobacion.nulo_significa` y `comparativo_firmas.descripcion` (R18) |
| `config/diccionario/raw.yaml` | ficha `rac`: sin filtro, grano «una fila por paso», `usu` login (R17) |
| `config/diccionario/00_global.yaml` | `version` +1 y su comentario (R19) |
| `docs/ARCHITECTURE.md` | «Qué se copia»: `rac` deja de ser «la única que se trae filtrada»; «Lo que Sigrid NO guarda»: primera viñeta corregida (R20) |
| `../azure-apps/datamart_seg_anual.md` | objeto nuevo y `raw.rac` sin filtro (R21); commit local en ese repositorio |

## 4. Ficheros que NO se tocan

- `sql/compras/11_historial_estados.sql`, `domain/historial_estados.py` y las
  fichas de `historial_estados`, `historial_estados_fotos` y
  `v_estado_documentos` (F-067, D7). El hallazgo está en `progress/spec_F-085.md` §2.
- `sql/retenciones/03_apuntes_contables.sql`: ya filtra `asiide <> 0` (R3); un
  test lo fija (§7).
- `sql/compras/09_comparativos_detalle.sql` y `compras.comparativo_firmas` (D6).
- `config/settings.py` (`DEFAULT_EXCLUDED_TABLES`): `raw.rac` sigue legible por
  el MCP, como hoy.
- `harness/features.json` salvo el `acceptance` de F-085 (ya ajustado por el
  spec-author).

## 4 bis. Dominio: `etl_sigrid/domain/documento_procesos.py`

Capa `domain`, sin imports de infraestructura. Mismo patrón que
`domain/historial_estados.py`: la regla la ejecuta el SQL y aquí vive una vez.

```python
FAMILIAS: Final[dict[int, str]] = {15: "FACTURA", 44: "CONTRATO",
                                   46: "COMPARATIVO", 42: "OBRA"}

@dataclass(frozen=True, slots=True)
class Paso:            # una fila de raw.rac ya unida a su documento
    paso_id: int; documento_id: int; estado_origen_id: int
    estado_destino_id: int; fecha: date | None; hora: time | None

@dataclass(frozen=True, slots=True)
class PasoEncadenado:
    paso: Paso; orden: int; es_ultimo: bool
    encaja_con_anterior: bool | None; dias_desde_anterior: Decimal | None

def hora_sigrid(hhmmss: int | None) -> time | None: ...
def encadenar(pasos: Iterable[Paso]) -> list[PasoEncadenado]: ...
```

- `hora_sigrid`: `None`/0 → `None`; fuera de 1..235959 o con minutos o segundos
  ≥ 60 → `None`; si no, `time(h, m, s)`.
- `encadenar`: agrupa por `documento_id`, ordena por (`fecha` con `None` al
  final, `hora` con `None` al final, `paso_id`) —el mismo `NULLS LAST` que el
  SQL—, numera desde 1, marca `es_ultimo`, `encaja_con_anterior` (R11) y
  `dias_desde_anterior` = (momento − momento anterior) en días, redondeado a 2
  decimales, `None` si falta alguno de los dos momentos (R12).

## 5. SQL: `sql/compras/12_documento_procesos.sql`

Cabecera: qué construye, de qué lee (`raw.rac`, `raw.con`, `raw.conest` vía
`compras.fn_estado_documento`), que los literales son los del dominio y que no
es persistente (DROP + CREATE cada noche, como el resto de `compras`).

```sql
DROP TABLE IF EXISTS compras.documento_procesos;
CREATE TABLE compras.documento_procesos AS
WITH pasos AS (
    SELECT r.ide AS paso_id, r.conide AS documento_id, c.tip AS tipo_documento_codigo,
           c.cod AS codigo_documento, NULLIF(r.conproide, 0) AS proceso_id,
           BTRIM(r.res) AS proceso, r.est1 AS estado_origen_id, r.est2 AS estado_destino_id,
           r.usu AS usuario, compras.fn_sigrid_date(r.fec) AS fecha,
           CASE WHEN r.hor BETWEEN 1 AND 235959 AND (r.hor / 100) % 100 < 60
                     AND r.hor % 100 < 60
                THEN make_time(r.hor / 10000, (r.hor / 100) % 100, r.hor % 100) END AS hora,
           NULLIF(r.asiide, 0) AS asiento_id
    FROM raw.rac r
    JOIN raw.con c ON c.ide = r.conide              -- R14: sin documento, fuera
    WHERE c.tip IN (15, 44, 46, 42)                 -- FAMILIAS del dominio
), ordenados AS (
    SELECT p.*, p.fecha + p.hora AS momento,
           ROW_NUMBER() OVER w AS orden,
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
       o.usuario, o.fecha, o.hora, o.momento, o.asiento_id, o.orden,
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

- Volumen esperado: ~1,01 M filas (873.527 + 69.065 + 63.190 + 4.491).
- `fn_estado_documento` hace `LIMIT 1` por (tipo, estado): no multiplica filas.
  112 pares (tipo, est1, est2) distintos; 3 orígenes y 4 destinos no casan con
  `conest` y quedan con el literal a NULL (la ficha lo dice).
- **Por qué materializada y no vista**: ~1 M filas con dos ventanas por
  documento; como vista, «quién aprobó las facturas de la obra X este año»
  pasaría de los 30 s del MCP.

## 6. El diccionario

Ficha `compras.documento_procesos` (`tipo: tabla`, `capa: consumo`,
`consumo_recomendado: true`, `paso_etl: build_compras`, `clave_negocio:
[paso_id]`), todas sus columnas con `significado` y, donde toca,
`nulo_significa` y `valores` (`familia`: las cuatro). La descripción lleva, en
este orden: qué es (la ventana «Procesos» de Sigrid), la tabla de cobertura por
familia, que es la historia NETA, que el estado actual es el destino del último
paso (99,96 / 99,99 / 99,98 / 100 %), que un paso con `encaja_con_anterior`
falso es un cambio de estado hecho fuera de un proceso (2,2 % de las facturas),
R16 (DOCVAL) y la relación con `comparativo_firmas`. Relaciones `N:1` a
`compras.facturas.factura_id`, `compras.contratos.contrato_id` y
`compras.comparativos.comparativo_id`, cada una «filtrando antes `familia`».
`ejemplos_preguntas`: quién aprobó la factura X y cuándo; qué facturas aprobó el
usuario U este mes; cuánto tarda de media un contrato del envío a la firma; por
qué estados pasó el comparativo C.

## 7. Tests (sin red ni BBDD)

- `test_f085_dominio.py`: `hora_sigrid` (0, 165211, 240000, 126000, 125960,
  None); `encadenar` con la FR26/10025 de §1 de `progress/spec_F-085.md`
  (4 pasos, orden 1-4, todos encajan, `es_ultimo` el 4.º, días 0,00 / 6,98 /
  0,02); un documento con un salto (`encaja_con_anterior` falso); empate de
  fecha y hora (desempata `paso_id`); un paso sin fecha (va al final y su
  `dias_desde_anterior` es `None`); dos documentos intercalados.
- `test_f085_sql.py`: la entrada `rac` del YAML (`where` None, `tex` excluida,
  cifras en el comentario); el censo sigue en 71; `FAMILIAS` del dominio = el
  `IN (...)` y el `CASE` del SQL; el `ORDER BY` de la ventana es el del dominio;
  `NULLIF(r.conproide, 0)`, `NULLIF(r.asiide, 0)`, `BTRIM(r.res)`, `JOIN raw.con`
  (no `LEFT`), dos `fn_estado_documento` con el tipo como primer argumento, PK
  y los tres índices; `SUB_PASOS` termina en `12`; `03_apuntes_contables.sql`
  conserva `WHERE r.asiide <> 0 AND r.conide <> 0` (R3).
- `test_f085_diccionario.py`: la ficha existe y cubre todas las columnas del
  `SELECT`; dice las cuatro coberturas, «NETA», «login», «DOCVAL»,
  `comparativo_firmas` y `dbo.log`; `raw.yaml` ya no dice «ESTA FILTRADA»;
  `comparativos`/`comparativo_firmas` ya no dicen «no guarda cuando cambio el
  estado»; `version` subió; `pendientes` vacía; ARCHITECTURE y azure-apps (este
  último con `pytest.skip` si no está al lado, como F-095).
- Se ajustan `test_f095_r9_*` (where) y, si aplica, `test_f047_steps.py`.

## 8. Riesgos y decisiones

| Id | Decisión | Recomendación | Alternativas descartadas |
|---|---|---|---|
| D1 | Filtro de `raw.rac` | **Quitarlo**: una tabla, mismo nombre, F-095 ya filtra en SQL | 2.ª entrada `rac` → `rac_procesos` con `asiide = 0`: dos tablas de lo mismo y el censo a 72 |
| D2 | Familias | **15, 44, 46, 42** | Todas (2,5 M): oferta, albarán y efecto no los ha pedido nadie; ampliar es tocar `FAMILIAS` |
| D3 | `rac.tex` | **Excluida** | Ingerir sin publicar: queda legible en `raw` por el MCP con datos de terceros |
| D4 | Usuario | **Login** | Nombre vía `usu`: contraseñas y DNI en la misma tabla; sería `personal` + F-105 |
| D5 | `dbo.log` | **A F-105** | Ingerirlo aquí: 8,5 M filas para una marca (firma digital) que no responde la pregunta |
| D6 | `confir` | **Sin cambios** | Publicar DOCVAL: 3.474 filas sin una firma, inducen a error |
| D7 | F-067 | **No se toca**; feature aparte para sacar `en_estado_desde` de `rac` | Corregirlo aquí: amplía el alcance y toca historia persistente |
| D8 | `conpro`, `rol` | **No se ingieren** | Ingerirlas: censo a 72-73 y cinco tests de recuento para un dato que `rac.res` ya trae |

Riesgos:
- **Ventana nocturna**: anoche 4 h 37 min 44 s, ya por encima de las 4 h de
  referencia. F-085 suma ~3 min de ingesta y el `12` (a medir, R25). No es
  causa del exceso, pero lo agrava: se enseña al humano antes de desplegar.
- **Disco**: ~+260 MB en `raw` y ~150-200 MB la tabla nueva con índices, sobre
  64 GB.
- **`nodesa`** no se publica: su significado no está confirmado.
- **Pasos con `hor` = 0** (2) quedan sin hora ni momento; lo dice la ficha.
- **Despliegue**: el MCP cachea el diccionario; tras publicarlo, reiniciarlo
  (memoria «El servidor MCP»). `compras` ya está en su lista blanca.
