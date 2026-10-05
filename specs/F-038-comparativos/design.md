<!-- specs/F-038-comparativos/design.md -->
# F-038 · Diseño · El comparativo de ofertas al completo

Cifras y porqués: `progress/spec_F-038.md`. Requisitos: `requirements.md`.

## 1 · Encaje y límite

Módulo `compras` (`docs/ARCHITECTURE.md`, «Capas PostgreSQL»): `build_compras`
lee `raw.*`, depende solo de `ingest_raw` y no bloquea a nadie. F-038 añade dos
ficheros SQL al final de su lista. Lee además dos cosas ya construidas por el
propio paso o por patrón existente: `compras.contrato_lineas` (01) y
`maestro.v_obra_fichas` (como hace `03_views.sql`); en Fase 2,
`descompuestos.lineas` **de la noche anterior** (`build_descompuestos` corre
después de `build_compras`; la primera ABC y el master 0 son versiones
congeladas, así que el desfase no cambia la base). **Sin ingesta nueva**. Dentro del límite del servicio: es modelado de datos
de Sigrid ya ingeridos; nada de otro dominio ni de otro proyecto.

## 2 · Ficheros

**Crear**

| Ruta | Fase | Qué |
|---|---|---|
| `etl_sigrid/domain/comparativos.py` | 1 (+2) | Literales y oráculo: familias ficticias, CIF falsos, exclusiones, umbrales del atípico; en Fase 2, patrón de `dto`, tolerancia y regla de la base |
| `etl_sigrid/infrastructure/postgres/sql/compras/08_comparativos.sql` | 1 | `compras.comparativo_ofertas` y `compras.comparativos` |
| `etl_sigrid/infrastructure/postgres/sql/compras/09_comparativos_detalle.sql` | 2 | `comparativo_lineas`, `comparativo_oferta_lineas`, `comparativo_objetivo`, `comparativo_firmas` |
| `tests/test_f038_dominio.py` | 1 (+2) | Oráculo puro con los nombres y textos medidos |
| `tests/test_f038_sql.py` | 1 (+2) | Texto del SQL: literales = dominio, columnas, vetos |
| `tests/test_f038_diccionario.py` | 1 (+2) | Fichas, claves, relaciones, frases obligatorias |

**Modificar**

| Ruta | Qué cambia |
|---|---|
| `sql/compras/00_setup.sql` | + `compras.fn_normalizar_nombre`, `compras.fn_familia_ficticia` (F1); + `compras.fn_porcentaje_dto` (F2). Nada existente cambia |
| `etl_sigrid/application/steps/build_compras_step.py` | `SUB_PASOS` + `08` (cuenta `comparativos`) y, en F2, `09` (cuenta `comparativo_oferta_lineas`); docstring |
| `tests/test_f047_steps.py` | La lista completa de `build_compras` gana `08` (y `09`) |
| `config/diccionario/compras.yaml` | Fichas nuevas; ficha de `contratos.comparativo_id` y relaciones de `contratos`/`albaranes` hacia `comparativos` |
| `config/diccionario/00_global.yaml` | `version` +1; P5 → `respondible`; preguntas nuevas del acceptance 13 |
| `docs/ARCHITECTURE.md` | Un párrafo en «Semántica Sigrid»: ficticias, sin IVA (`totbas`), atípicos |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` | Los objetos nuevos de `compras` (otro repositorio: commit propio allí) |

**NO se tocan**: `sql/compras/01_documentos.sql` (R22 es solo de ficha),
`config/tables_sigrid.yaml`, `sql/descompuestos/`, `maestro`, `stg`, `mart`,
`cierre`, `mcp-bbdd` (`compras` ya está en su lista blanca), `.env`.

## 3 · Dominio: `etl_sigrid/domain/comparativos.py`

Mismo patrón que `domain/texto_comentarios.py` (F-080): los literales se escriben
UNA vez aquí como regex **POSIX** (los ejecuta Postgres: nada de lookarounds), las
funciones son el oráculo ejecutable, y `test_f038_sql.py` comprueba que el SQL
lleva **los mismos** literales. Capa `domain`: cero imports de infraestructura.

```python
CIF_FALSOS: dict[str, str]            # {'A99999999': 'OBJETIVO', 'A00000000': 'OFICINA_TECNICA'}
PATRONES_FAMILIA: tuple[tuple[str, str], ...]   # (familia, regex POSIX) EN ORDEN (R9)
EXCLUSIONES: tuple[str, ...]          # ('PLANIFICACION DE ESPACIOS',) sobre el nombre normalizado
FACTOR_ATIPICO: int = 10 ; MINIMO_ATIPICO: Decimal = Decimal('100000')
def normalizar_nombre(texto: str | None) -> str
def familia_ficticia(cif: str | None, nombre: str | None) -> str | None   # None = real
def es_adjudicado_atipico(adjudicado: Decimal, mayor_oferta: Decimal | None) -> bool | None
# Fase 2
PATRON_DTO: str = r'^-?[0-9]+(,[0-9]+)?%$'
TOLERANCIA_ABS = Decimal('0.011'); TOLERANCIA_REL = Decimal('0.002')
def parse_porcentaje_dto(texto: str | None) -> Decimal | None
def casa_con_base(precio: Decimal, precio_base: Decimal, pct: Decimal) -> bool
def base_regla(obra_tiene_primera_abc: bool) -> str     # 'ABC' o 'ESTUDIOS' (D2 del humano)
```

- `normalizar_nombre`: mayúsculas; `ÁÉÍÓÚÜÑ` → `AEIOUUN`; todo lo que no sea
  `A-Z0-9` → un espacio; espacios colapsados y recortados. En SQL:
  `btrim(regexp_replace(translate(upper(x), 'ÁÉÍÓÚÜÑ', 'AEIOUUN'), '[^A-Z0-9]+', ' ', 'g'))`.
- Patrones (sobre el nombre ya normalizado; el implementer los afina **solo con
  los nombres medidos** en `progress/spec_F-038.md` §2 y los fija en tests):
  OBJETIVO `(^| )OBJE` · OFICINA_TECNICA `OFICINA TE` · CUATRIMESTRAL `CUATRIM` ·
  FASE_0 `FASE ?0|PLANIFICACION 0$` · ABC `(^| )ABC( |$)` · PLANIFICACION
  `PLANIF`. Solo construcciones que ejecutan igual Postgres y `re` de Python
  (nada de `\m`/`\M`, que `re` no tiene; el nombre normalizado separa palabras
  con un espacio, así que `(^| )` hace de frontera).
- `familia_ficticia`: CIF real (no vacío y no falso) → `None`; excluido → `None`;
  primera familia que case; si no casa ninguna y el CIF es falso →
  `CIF_FALSOS[cif]`; si no → `None`.
- Fixtures obligatorias de `test_f038_dominio.py` (medidas): `OBJETIVO-RUESMA`,
  `*OBJETIVO*`, `OBJE` con `A00000000`, `º` con `A99999999` → OBJETIVO;
  `OFICINA TÉCNICA`, `oficina tecnica`, `OFICINA TENICA` con `A99999999` →
  OFICINA_TECNICA; `PLANIFICACION CUATRIMESTRAL` y `CUATRIMESTRAL JUNIO 2023` →
  CUATRIMESTRAL; `PLANIFICACION " FASE 0 "`, `PLANIFICADO FASE "0"`,
  `PLANIFICACION "0"` → FASE_0; `PLANIFICACIÓN ABC`, `ABC DEF MASTER COSTE 3` →
  ABC; `PLANIFICADO_RUESMA` → PLANIFICACION; y reales: `MAT PLANIFICACION DE
  ESPACIOS, S.L.` (con CIF y sin él), `ABC INSTALACIONES…` con CIF, `CERRAJERIA
  RIANSA` sin CIF. `dto`: `'15%'`→15, `'10,08%'`→10.08, `'-168%'`→−168,
  `''`/`None`/`'5'`/`'5.5%'`/`'10+5%'`→None.

## 4 · SQL Fase 1: `08_comparativos.sql`

Cabecera con qué construye y de qué lee. `DROP TABLE IF EXISTS … CASCADE` +
`CREATE TABLE … AS`, como el resto del módulo (se reconstruye cada noche).

**Guarda (R21), lo primero del fichero**: bloque `DO` que hace `RAISE EXCEPTION`
si algún `comide` tiene dos `ctride` distintos > 0, con el número de casos. El
paso falla con el nombre del sub-paso (lo hace ya `BuildComprasStep`).

**`compras.comparativo_ofertas`** — de `raw.comprv p` ⨝ `raw.dco d`
(`d.ide = p.docide`) ⨝ `raw.con c` (`c.ide = d.ide`), `LEFT JOIN` a las líneas
agregadas (`raw.dcopro`, `comlinide > 0`, `GROUP BY docide`) y `LEFT JOIN LATERAL
compras.fn_estado_documento(12, c.est)`. Columnas, en este orden:

`oferta_id` (PK, `d.ide`), `invitacion_id` (`p.ide`), `comparativo_id`
(`p.comide`), `posicion` (`p.pos`), `codigo_oferta` (`c.cod`), `fecha_oferta`
(`fn_sigrid_date(c.fec)`), `proveedor_id` (`NULLIF(d.entide,0)`),
`proveedor_codigo`, `proveedor_nombre`, `proveedor_cif` (`NULLIF(TRIM(…),'')`),
`es_ficticia` (`familia_ficticia IS NOT NULL`), `familia_ficticia`
(`compras.fn_familia_ficticia(d.entcif, d.entres)`), `estado_id`,
`estado_codigo`, `estado`, `es_ganadora` (`c.est = 6`),
`importe_ofertado_documento` (`d.totbas::NUMERIC(18,2)`),
`importe_ofertado_lineas` (`Σ dcopro.tot`, NULL si no tiene líneas),
`n_lineas`. Índices: `comparativo_id`, `proveedor_id`, `familia_ficticia`.

**`compras.comparativos`** — de `raw.com m` ⨝ `raw.con c` (`c.ide = m.ide`),
con `LEFT JOIN`s a: `raw.auxpronat` (`ide = NULLIF(m.natide,0)`),
`raw.con` de la obra, `maestro.v_obra_fichas`, `fn_estado_documento(46, c.est)`,
y cuatro agregados por `comparativo_id`:

1. **ofertas** (de `compras.comparativo_ofertas`): `n_ofertas`,
   `n_ofertas_reales`, `n_ofertas_reales_con_importe`, `n_ofertas_ganadoras`,
   `MIN/MAX` del documento **con `FILTER (WHERE NOT es_ficticia AND
   importe_ofertado_documento > 0)`**, `MAX` del documento de todas (para el
   atípico) y, si `n_ofertas_ganadoras = 1`, la ganadora y sus dos importes.
2. **líneas** (`raw.comlin`): `Σ COALESCE(can,0)*COALESCE(pre,0)` y `MAX(NULLIF(ctride,0))`
   (la guarda ya garantizó que es único).
3. **contrato**: `raw.con` del contrato (código, fecha) y
   `Σ compras.contrato_lineas.importe` por `contrato_id`.
4. **firmas** (`raw.confir` por `conide`): `COUNT(*)`, `COUNT(*) FILTER (WHERE
   fir = 0)`, la última firmada por `(fec, hor)` con `DISTINCT ON` y si `c.est`
   está entre sus `estfin`.

Columnas, en este orden: `comparativo_id` (PK), `codigo_comparativo`,
`nombre_comparativo` (`c.res`), `fecha_alta`, `obra_id`, `codigo_obra`,
`nombre_obra`, `empresa_id`, `clave_obra`, `actividad_id`, `actividad`,
`estado_id`, `estado_codigo`, `estado`, `contrato_id`, `codigo_contrato`,
`fecha_contrato`, `n_ofertas`, `n_ofertas_reales`,
`n_ofertas_reales_con_importe`, `n_ofertas_ganadoras`, `oferta_ganadora_id`,
`proveedor_ganador_id`, `proveedor_ganador_nombre`,
`importe_ofertado_documento_ganadora`, `importe_ofertado_lineas_ganadora`,
`importe_adjudicado_lineas`, `adjudicado_atipico`, `importe_contratado`,
`oferta_real_minima`, `oferta_real_maxima`, `ahorro_concurso`, `n_firmas`,
`n_firmas_pendientes`, `fecha_aprobacion`, `aprobado_por`.
Índices: `obra_id`, `contrato_id`, `actividad_id`, `estado_id`.

`adjudicado_atipico` en SQL:
`CASE WHEN max_oferta > 0 THEN adj > 10 * max_oferta AND adj > 100000 END`
(literales = `FACTOR_ATIPICO`, `MINIMO_ATIPICO`; NULL sin oferta con importe).

## 5 · SQL Fase 2: `09_comparativos_detalle.sql`

- **`compras.comparativo_lineas`** (`raw.comlin`, PK `linea_id`):
  `comparativo_id`, `numero_linea` (`numlin`), `posicion`, `contrato_id`,
  `linea_necesidad_id` (`dncproide`), `partida_id` (`raw.dncpro.paride`, LEFT),
  `linea_oferta_ganadora_id` (`dcoproide`), `cantidad`, `precio`,
  `importe_adjudicado` (`can × pre`, NUMERIC(18,2)). Índices: `comparativo_id`,
  `contrato_id`, `partida_id`.
- **`compras.comparativo_oferta_lineas`** (`raw.dcopro` con `comlinide > 0` y
  `docide` en `comparativo_ofertas`; PK `linea_oferta_id`): `oferta_id`,
  `comparativo_id`, `comparativo_linea_id` (`comlinide`), `producto_id`,
  `descripcion`, `unidad_medida`, `cantidad`, `precio`,
  `importe_ofertado_linea` (`tot`), `descuento_texto` (`dto` literal),
  `porcentaje_descuento` (`compras.fn_porcentaje_dto(dto)`), `es_ficticia` y
  `familia_ficticia` (de su oferta) y, solo en líneas OBJETIVO con %, la base
  (R29-R30): `base_regla`, `precio_base`, `origen_base` (p. ej. `ABC v3`,
  `MASTER_PRE_ABC v2`, `MASTER_ESTUDIO v0`) y `casa_base`. `LEFT JOIN LATERAL`
  sobre `descompuestos.lineas` por `obra_id` y `partida_id` (índices
  `ix_lineas_version`, `ix_lineas_partida`), D4: con ABC, la ABC que case y si
  no la de `fase_num` < ABC más reciente que case; sin ABC, solo Estudios; si no
  casa, la de la regla y `casa_base` falso. **Nunca `fase_num` > ABC** (test). Índices: `oferta_id`, `comparativo_linea_id`.
- **`compras.comparativo_objetivo`** (PK `comparativo_id`): `oferta_objetivo_id`
  (la OBJETIVO más reciente por `fecha_oferta`, luego `oferta_id` DESC),
  `n_ofertas_objetivo`, `importe_objetivo` (su documento),
  `porcentaje_objetivo` (si sus líneas con % tienen uno solo), `base_regla`
  (`ABC`/`ESTUDIOS` de la obra) y `pct_importe_casa_base` (parte del importe de
  sus líneas con % cuya base casa).
- **`compras.comparativo_firmas`** (`raw.confir` con `conide` en
  `raw.com`; PK `firma_id`): `comparativo_id`, `circuito` (`cod`), `escalon`
  (`rol`), `usuario`, `fecha` (`fn_sigrid_date(fec)`), `hora` (`hor`),
  `pendiente` (`fir = 0`), `firma_digital_valida` (`firok = 1`),
  `estado_final_id` (`estfin`). Índices: `comparativo_id`, `usuario`.
- `compras.fn_porcentaje_dto(t TEXT) RETURNS NUMERIC`, `IMMUTABLE`: si `t ~
  PATRON_DTO` → `replace(replace(t,'%',''),',','.')::numeric`; si no, NULL.
  Sin `EXCEPTION`: el patrón ya garantiza el cast.

## 6 · Diccionario

Fichas en `compras.yaml` (`paso_etl: build_compras`, `refresco: nocturno`,
`capa: consumo`). Lo que cada una DEBE decir, además del significado por
columna (`agregacion` y `nulo_significa` donde aplique):

- `comparativos`: las cuatro magnitudes y cómo cuadran (A=B 99,6 %, A=C 89,8 %,
  A=D 41 %, sin IVA); `importe_contratado` es del contrato y se repite
  (`agregacion: no_sumable`, sumar por `contrato_id` distinto); el atípico (52,
  602,5 M€, cifras de 2026-10-04) y que «el adjudicado total» se da con y sin
  ellos; `ahorro_concurso` solo con reales; `fecha_aprobacion` no existe fuera
  de los estados de firma; las siete fechas y cinco campos de `com` vacíos en
  origen; y las dos trampas de `dbo.log`.
- `comparativo_ofertas`: criterio de ficticia con sus cifras (§2 del informe),
  `dco.totbas` y no `totdoc`, el proveedor de `dco.entide` y no de
  `comprv.prvide` (18 %).
- Relaciones: `comparativo_ofertas.comparativo_id` → `comparativos` N:1;
  `comparativos.contrato_id` → `compras.contratos.contrato_id` N:1;
  `compras.contratos.comparativo_id` y `compras.albaranes.comparativo_id` →
  `comparativos` N:1; `comparativos.obra_id` → `maestro.obras.obra_id` N:1.
- Fase 2: fichas de los cuatro objetos; `dto` texto y negativo; la base y su
  cobertura de D4 (29,1 % casan; 12.351 solo con una posterior).
- `00_global.yaml`: `version` +1; P5 a `respondible` (sin `bloqueada_por`);
  preguntas nuevas: comparativos por actividad, ahorro del concurso, quién
  aprobó el comparativo X y cuándo, ¿acabó en contrato el comparativo X?

## 7 · Tests (sin red ni BBDD)

- `test_f038_dominio.py`: las fixtures de §3, una por familia y por exclusión;
  `es_adjudicado_atipico` en los bordes (10×, 100.000, mayor oferta 0/None).
- `test_f038_sql.py` (lectura del texto, patrón de `test_f084_sql.py`): los
  patrones, CIF, exclusiones y umbrales del SQL **son** los del dominio; `08` no
  contiene `prvide` ni `totdoc` ni `ctr.comide`; usa `fn_estado_documento(46` y
  `(12`; usa `ctride`; existe la guarda `RAISE EXCEPTION`; el `MIN/MAX` del
  ahorro lleva `NOT es_ficticia`; ninguna columna proyectada se llama
  `importe`; columnas = §4/§5; `09` filtra `origen` y `es_primera_abc`.
- `test_f038_diccionario.py`: ficha por objeto con su `clave_negocio`; ninguna
  columna `importe`; frases obligatorias de §6 presentes; relaciones válidas.
- `test_f047_steps.py`: la lista de ficheros de `build_compras`.
- Rigor `estandar`: fase RED en R3, R8-R11, R12, R14, R15, R16, R19, R20, R21,
  R27, R29, R32 con la traza en `progress/impl_F-038.md`; cobertura de líneas
  cambiadas; campaña de mutación del arnés sobre `domain/comparativos.py`.

## 8 · Coste y riesgos

- **Coste**: Fase 1 < 1 min y < 30 MB; Fase 2 +2-3 min y ~150 MB (`timings`).
- **El atípico es un corte, no una lista de ids**: una lista de comparativos se
  queda vieja la noche que entra otro; el corte 10×/100.000 € es estable (con 3×
  salen 65 en vez de 52).
- **Nombres nuevos de ficticia**: una entidad ficticia con nombre nuevo y CIF
  vacío entraría como real. Mitigación: la ficha da la consulta de control
  (ofertas con CIF vacío por nombre) y el dominio es el único sitio que cambiar.
- **La base del objetivo lee `descompuestos`**, otro esquema y otro paso:
  primer SQL fuera de `sql/descompuestos/` que lo lee (F-123 R1 lo daba por
  hecho). Si `build_descompuestos` falla, la base se queda con la de otra noche.
- **`maestro.v_obra_fichas`** es de `build_maestros`, que corre antes en
  `run-all`; si falta, el `CREATE` falla como ya fallaría `03_views.sql`.
- **Descartado**: `comprv.prvide` (18 %); `ctr.comide` (56 %); `dco.totdoc`
  (IVA); solo CIF falso (30 %); por entidad; presupuesto de partida como
  «planificado» (×25); vistas por actividad (F-067); `dbo.log` (F-085).
