<!-- specs/F-132-estado-desde-rac/design.md -->
# F-132 · Diseño

Mediciones: `progress/spec_F-132.md`. Requisitos: `requirements.md`.

## 1. Encaje y límite

Todo vive en `build_compras` (capa `compras`) y en el dominio: la vista lee
tablas de `compras` que ya existen (`contratos`, `facturas`, `comparativos`,
`documento_procesos`). **Sin ingesta nueva, sin tabla nueva, sin esquema
nuevo**: `mcp-bbdd` no cambia (reiniciarlo tras publicar). No cruza la frontera
del servicio: `rac` ya se ingiere (F-085). La única pieza que podría tentar a
salir fuera —fechar los pasos DESHECHOS— es `dbo.log` (`ope` 30) y ya tiene
feature propia en este repositorio (F-105); aquí no se toca.

Fase A cambia la FORMA de una vista publicada hace un día (`v_estado_documentos`,
D4): cambia de columnas y gana una familia. Su único consumidor es el MCP.

## 2. Ficheros (Fase A)

**Crear**
- `etl_sigrid/domain/estado_documentos.py` — reglas y oráculos (§4).
- `etl_sigrid/infrastructure/postgres/sql/compras/13_estado_documentos.sql` — la
  vista (§3).
- `etl_sigrid/infrastructure/postgres/contraste_estados_sql.py` — SOLO texto
  SQL de lectura del contraste (§5), como `compras_reset_sql.py`.
- `tests/test_f132_dominio.py`, `tests/test_f132_sql.py`,
  `tests/test_f132_contraste.py`, `tests/test_f132_diccionario.py`.
- `progress/contraste_F-132.md` — lo escribe el líder con cada ejecución del
  contraste (§5); no es código.

**Modificar**
- `sql/compras/11_historial_estados.sql` — se le QUITA el bloque de la vista
  (desde el comentario de `v_estado_documentos` hasta el final) y su cabecera
  deja de decir «la fecha no está en Sigrid»: dice que es el RESPALDO de la
  vista de `rac` durante el contraste de F-132. La foto (tablas y `DO`) no
  cambia ni una línea ejecutable.
- `application/steps/build_compras_step.py` — sub-paso `estado_documentos`
  (`13_estado_documentos.sql`, sin `target_table`: es una vista) al final de
  `SUB_PASOS`; docstring con `13`.
- `main.py` — comando `contraste-estados` (§5).
- `config/diccionario/compras.yaml`, `raw.yaml` (`conest`), `00_global.yaml`
  (v46, P23, P24, descripción de `compras`): R18-R20.
- `config/tables_sigrid.yaml` (bloque C3, última frase), `docs/ARCHITECTURE.md`
  (viñeta de F-067 en ~l. 300, «Lo que Sigrid NO guarda» en ~l. 509, viñeta
  nueva de F-132), `README_COMPRAS_C1_C2.md` (~l. 53): R21.
- `azure-apps/datamart_seg_anual.md` (otro repositorio, commit propio): R23.
- Tests que fijan lo que cambia: `test_f067_sql.py` (los de la vista r9-r11
  pasan a F-132 y se borran de aquí; `QUIEN_PUEDE_NOMBRARLAS` gana
  `infrastructure/postgres/contraste_estados_sql.py`), `test_f067_diccionario.py`
  (r10, r11, p23 y P24), `test_f047_steps.py`, `test_f073_pipeline.py`,
  `test_f080_pipeline.py`, `test_f085_sql.py` (~l. 403: la lista de ficheros),
  y los recuentos del diccionario que fije `test_f006_*` (columnas: la vista
  pasa de 11 a 15; objetos, 207, no cambia).

**NO se toca**
- `12_documento_procesos.sql` ni `domain/documento_procesos.py`: la vista lee
  `es_ultimo` tal cual; sin índice nuevo (0,8 s la vista entera, §6).
- Las dos tablas de la foto, el `DO` de `11`, `domain/historial_estados.py`,
  `compras_reset_sql.py` y `reset-compras`: siguen igual en la Fase A.
- `01_documentos.sql`, `08_comparativos.sql`: el estado y la fecha de alta ya
  están en sus tablas. `con.tiemod` sigue fuera (D2 de F-067).
- `config/tables_sigrid.yaml` salvo el comentario: ninguna tabla nueva.

## 3. SQL · `13_estado_documentos.sql`

Cabecera: qué construye, que lee `compras.contratos`, `facturas`,
`comparativos` y `documento_procesos` (nunca la foto), y que `12` la tira cada
noche con su `DROP TABLE ... CASCADE` (por eso va detrás). Forma:

```sql
DROP VIEW IF EXISTS compras.v_estado_documentos;
CREATE VIEW compras.v_estado_documentos AS
WITH documentos AS (          -- el estado de la CABECERA (R3), uno por documento
    SELECT 44 AS tipo_documento_codigo, c.contrato_id AS documento_id,
           c.codigo_contrato AS codigo_documento, c.estado_id, c.estado_codigo,
           c.estado, c.fecha AS fecha_alta                 -- c.fecha = con.fec
    FROM compras.contratos c
    UNION ALL SELECT 15, f.factura_id, f.codigo_factura, f.estado_id,
           f.estado_codigo, f.estado, f.fecha_alta FROM compras.facturas f
    UNION ALL SELECT 46, m.comparativo_id, m.codigo_comparativo, m.estado_id,
           m.estado_codigo, m.estado, m.fecha_alta FROM compras.comparativos m
),
con_paso AS (
    SELECT d.*, u.paso_id, u.proceso, u.usuario, u.nombre_usuario,
           COALESCE(u.momento, u.fecha::TIMESTAMP) AS momento_ultimo,   -- R4
           CASE WHEN u.paso_id IS NOT NULL
                     AND u.estado_destino_id IS NOT DISTINCT FROM d.estado_id THEN 'PASO'
                WHEN u.paso_id IS NULL
                     AND (d.tipo_documento_codigo, d.estado_id) IN
                         ((15, 1), (15, 20), (44, 1), (46, 1), (46, 11), (46, 100))
                     THEN 'ALTA'                                            -- R5
                ELSE 'FUERA_DE_PROCESO' END AS origen_fecha                 -- R6
    FROM documentos d
    LEFT JOIN compras.documento_procesos u
           ON u.documento_id = d.documento_id AND u.es_ultimo
)
SELECT documento_id, tipo_documento_codigo,
       CASE tipo_documento_codigo WHEN 44 THEN 'CONTRATO' WHEN 15 THEN 'FACTURA'
            WHEN 46 THEN 'COMPARATIVO' END AS tipo_documento,
       codigo_documento, estado_id, estado_codigo, estado,
       CASE origen_fecha WHEN 'PASO' THEN momento_ultimo
                         WHEN 'ALTA' THEN fecha_alta::TIMESTAMP END AS en_estado_desde,
       origen_fecha,
       ((now() AT TIME ZONE 'Europe/Madrid')::date - <en_estado_desde>::date) AS dias_en_estado,
       CASE WHEN origen_fecha = 'FUERA_DE_PROCESO' THEN momento_ultimo END AS cambio_posterior_a,
       paso_id, proceso, usuario, nombre_usuario      -- NULL salvo en PASO (R4-R6)
FROM con_paso;
```

- `<en_estado_desde>` se repite como expresión (o va en un `CROSS JOIN
  LATERAL`): el implementer elige; los tests miran el resultado de la regla
  sobre el texto, no la forma.
- Las columnas del paso se anulan con `CASE WHEN origen_fecha = 'PASO'` en
  `FUERA_DE_PROCESO`: allí el «último paso» no explica el estado.
- `en_estado_desde` es `TIMESTAMP` sin zona en hora de Madrid, igual que la de
  F-067 y que `documento_procesos.momento`. `fecha_alta` NULL (R8) da NULL.
- Los literales de familias, estados iniciales y orígenes son los del dominio
  y `test_f132_sql.py` lo vigila (R11), con el patrón de `test_f085_sql.py`.

## 4. Dominio · `etl_sigrid/domain/estado_documentos.py`

Sin imports de infraestructura (stdlib: `dataclasses`, `datetime`).

- `FAMILIAS_ESTADO: Final[dict[int, str]] = {44: "CONTRATO", 15: "FACTURA",
  46: "COMPARATIVO"}`.
- `ESTADOS_INICIALES: Final[dict[int, frozenset[int]]]` = {15: {1, 20}, 44: {1},
  46: {1, 11, 100}} — medidos (§2 de `progress/spec_F-132.md`).
- `ORIGENES_FECHA = ("PASO", "ALTA", "FUERA_DE_PROCESO")`.
- `CLASES_CAMBIO = ("PASO", "DESHECHO", "VUELTA_AL_INICIAL",
  "FUERA_DE_PROCESO", "DISCREPANCIA")`; `CLASES_NO_VISTO = ("ALTA",
  "IDA_Y_VUELTA", "DISCREPANCIA")`.
- `@dataclass(frozen=True, slots=True) class PasoEstado: orden: int;
  destino: int | None; momento: datetime | None` (el oráculo de la vista usa
  hora de Madrid sin zona; el del contraste, `datetime` con zona UTC: el SQL de
  §5 ya entrega `momento AT TIME ZONE 'Europe/Madrid'`, así el dominio no
  necesita `zoneinfo` ni `tzdata`).
- `@dataclass(frozen=True, slots=True) class FechaEstado: en_estado_desde:
  datetime | None; origen: str; cambio_posterior_a: datetime | None`.
- `fecha_estado(tipo: int, estado: int | None, ultimo: PasoEstado | None,
  fecha_paso: date | None, fecha_alta: date | None) -> FechaEstado` — R4-R8.
- `dias_en_estado(desde: datetime | None, hoy: date) -> int | None` — R9.
- `clasificar_cambio(tipo, estado_nuevo, inicio, fin, pasos) -> str` — R13, en
  el orden de prioridad del requisito; `pasos` en cualquier orden (ordena por
  `orden`).
- `clasificar_no_visto(estado_foto, abierto_en_la_foto: bool, fin, pasos) ->
  str` — R14.

## 5. El contraste · `contraste-estados`

**Por qué un comando y no un paso de la nocturna (D8)**: la foto guarda TODAS
sus noches y `rac` es la historia completa, así que el contraste se recalcula
entero sobre todas las noches cada vez que se lanza. Coste en la nocturna: 0.
Matiz: un paso deshecho DESPUÉS de una noche cambia la clase de esa noche al
recalcular (de `PASO` a `DESHECHO`); es la historia neta y se dice en el informe.

`contraste_estados_sql.py` declara tres consultas de solo lectura:

1. `SQL_CAMBIOS` — tramo cerrado por `CAMBIO` unido al tramo que abre la misma
   foto: `documento_id`, `tipo_documento_codigo`, `estado_nuevo`, `inicio` =
   `observado_antes`, `fin` = `desde` (TIMESTAMPTZ).
2. `SQL_NO_VISTOS` — documentos 44/15 con algún paso en (línea base, última
   foto] que no tienen tramo cerrado por `CAMBIO` en esa ventana: su estado en
   la foto de `fin` y si esa foto les abrió tramo no de línea base.
3. `SQL_PASOS` — los pasos de una lista de documentos (`= ANY(%s)`):
   `documento_id`, `orden`, `estado_destino_id`, `momento AT TIME ZONE
   'Europe/Madrid' AS momento_utc`.

`main.py contraste-estados`: abre la conexión con `read_only = True` (R17),
ejecuta las tres, clasifica con el dominio, imprime con `click.echo` una tabla
`observado_en | tipo | clase | documentos` y las `DISCREPANCIA` (≤ 50 ids por
noche), y sale con 1 si hay alguna (R15) o 0 con «sin cambios que contrastar»
(R16). Logging estructurado como el resto de comandos `check-*`. Test: cliente
falso que devuelve las filas medidas el 08-10 (§3 de las mediciones) y comprueba
la tabla, el código de salida y que ningún SQL lleva `INSERT|UPDATE|DELETE|
CREATE|DROP|ALTER|TRUNCATE`.

**Cómo se lleva el contraste**: el líder (o el humano) lo lanza cuando quiera,
mínimo al terminar el plazo (D6), y pega la salida, fechada, en
`progress/contraste_F-132.md`. **Criterio para proponer la retirada** (D6): 0
`DISCREPANCIA` sin explicar en todo el plazo y el reparto de clases delante.

## 6. Riesgos

- **La forma de la vista cambia** (D4): desaparecen `cambio_observado_tras`,
  `antiguedad_es_minima` y `ultima_foto`. Consumidor único, el MCP, que lee la
  ficha nueva tras publicar v46 y reiniciar. Nadie la consume por posición.
- **La vista cae cada noche con `12`** (`CASCADE`) y la levanta `13`: si un
  sub-paso entre medias falla, esa noche no hay vista hasta el siguiente build
  bueno. Igual que cualquier otro objeto de `compras`.
- **Desfase de ingesta** (`con` y `rac` no se leen en el mismo instante): un
  paso lanzado entre las dos lecturas sale `FUERA_DE_PROCESO` un día. Hoy son 68
  por la ingesta a mano de F-085 a las 10:05; de madrugada, ~30 pasos al año.
- **Historia NETA** (D2): el deshacer no se fecha; un documento devuelto a un
  estado cuenta desde el paso que llevó allí la primera vez (7 facturas y 2
  contratos en una noche). Con la foto retirada no habrá forma de verlo hasta
  F-105.
- **Envíos antiguos sin cerrar**: 785 de 809 contratos EPF pasan de 21 días,
  pero solo 23 son de 2025 en adelante. Es dato, no error; P23 obliga a decirlo
  y la carta a Compras (ya pendiente de F-067, T22) debería contarlo.
- **Coste**: la vista, < 1 s de build y 0,8 s entera al consultar; el
  contraste no corre de noche. La nocturna (4 h 40 min el 08-10) no cambia.

## 7. Fase B (solo tras D7; el diseño depende de la rama)

Común a «retirar»: borrar `11_historial_estados.sql` y su sub-paso; mover
`EPOCA_DELPHI` y `fecha_delphi` a `etl_sigrid/domain/fecha_delphi.py` (la usan
`fn_sigrid_tiempo` y `test_f067_sql` r14) y borrar el resto de
`domain/historial_estados.py`, `test_f067_dominio.py` y los tests de la foto de
`test_f067_sql.py`; ajustar `test_f047`/`f073`/`f080`/`f085`; v47 del diccionario.
- **Borrar**: comando `retirar-foto-estados [--confirmar]` (un `DROP TABLE`
  de las dos en una transacción; sin `--confirmar`, solo imprime); lo lanza el
  HUMANO contra Azure tras desplegar. `compras_reset_sql.py` pierde la lista de
  conservadas (el `NOT IN ()` vacío es error de sintaxis: se quita la cláusula).
  Fuera fichas, `contraste-estados` y `contraste_estados_sql.py`; inventario de
  `specs/F-006-mcp-azure/design_detalle.md` 207 → 205.
- **Congelar**: las tablas se quedan, nadie las escribe; `reset-compras` las
  sigue conservando; fichas «CONGELADA: foto del 07-10 al <fecha>».
- **Conservar como detector**: no hay Fase B de código; solo las fichas.

## 8. Decisiones abiertas para el humano (recomendación en negrita)

- **D1** Dos fases → **sí**: A ahora (vista + contraste + textos); B tras el
  contraste. Una sola obligaría a esperar 2 semanas para publicar la vista.
- **D2** Semántica de la fecha → **historia NETA de `rac`** («en EPF desde el
  envío», aunque un «recibido» se deshiciera después). Alternativa: la foto
  manda cuando vio un cambio posterior al último paso; ata la vista a la foto y
  B tendría que deshacerlo.
- **D3** Comparativos en la vista → **sí** (20.426, 99,98 % casan, mismo
  coste). Obras no: su estado es de `maestro` y no lo pregunta Compras.
- **D4** Columnas → **las de R2**: fuera las tres de la foto, dentro
  `origen_fecha`, `cambio_posterior_a`, `codigo_documento` y quién dio el paso.
- **D5** Los 75 fuera de proceso → **sin fecha y con la cota**
  `cambio_posterior_a`. Alternativa: la fecha de la foto mientras exista (solo
  sirve para los de después del 07-10, hoy 0).
- **D6** Plazo y criterio del contraste → **14 noches (hasta el 2026-10-22) y 0
  `DISCREPANCIA` sin explicar**. Con una sola noche medida (230 cambios: 218
  PASO, 9 DESHECHO, 3 VUELTA_AL_INICIAL, 0 DISCREPANCIA) una semana basta para
  ver la frecuencia; dos cubren cierres de mes de facturas.
- **D7** Qué hacer con la foto → se decide al final; **recomendación previa:
  BORRAR** (no hay copia en Sigrid de lo que añade, pero lo que añade es solo la
  fecha de los deshechos —~9 al día— y eso lo da F-105 con `dbo.log`; congelar
  deja dos tablas publicadas que suenan a fuente de verdad). Ahorro: < 1 min por
  noche y 20 MB. Si el humano quiere fechar los deshechos ANTES de F-105:
  conservarla como detector.
- **D8** Contraste a demanda y no en la nocturna → **sí** (0 min de ventana).
