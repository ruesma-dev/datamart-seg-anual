<!-- specs/F-006-mcp-azure/design.md -->
# F-006 · El diccionario semántico del datamart — Diseño técnico

## 1 · La idea en un párrafo

El datamart aprende a explicarse solo. El significado de cada objeto y cada
columna —más el grano, las claves de negocio, las relaciones, las trampas y el
régimen de refresco— se escribe como **YAML versionado** en
`config/diccionario/`, un fichero por esquema. Un **validador de dominio puro**
lo comprueba sin red ni BBDD, y un **paso del ETL lo publica dentro de la propia
base**, en tres tablas de `_meta` más una vista. A partir de ahí el MCP no
necesita conocer este repositorio: lee semántica **por SQL**, igual que lee
datos, y por eso el multi-base sale gratis (cada base publicará su semántica en
su propio `_meta`). Una **puerta de cobertura** que corre en cada
`bash harness/init.sh` impide que el modelo crezca y el conocimiento se quede
atrás. Y el rol de lectura del MCP deja de ver `raw` y `stg`, para lo cual hay
que construir algo que hoy no existe: los `REVOKE`.

Nada de esto añade una columna al modelo de datos. Es **metadato sobre lo que ya
hay**.

## 2 · Encaje hexagonal

| Pieza | Capa | Por qué ahí |
|---|---|---|
| Entidades del diccionario, validador, derivación de avisos, informe de cobertura | **domain** | Reglas puras sobre estructuras de datos. Sin YAML, sin SQL, sin ficheros |
| Extracción del inventario a partir de textos SQL y del YAML de tablas | **domain** | Recibe *texto* ya leído y devuelve objetos. Quien lee ficheros es infraestructura |
| Carga de los YAML y cálculo del hash | **infrastructure** | Toca el sistema de ficheros |
| Sentencias SQL de publicación y de grants/revokes | **infrastructure** | Genera texto SQL citado con `psycopg.sql`. Precedente exacto: `grants.py` |
| `PublicarDiccionarioStep` | **application** | Orquesta: carga → valida → publica → registra |
| Comandos `publicar-diccionario` y `check-diccionario`, y la composición del pipeline | **main.py** | La composición se hace en el punto de entrada, nunca dentro de los steps |

El `Orchestrator` no cambia. `domain/` sigue sin un solo import de
infraestructura.

---

## 3 · CONTRATO 1 · Formato exacto del YAML

Punto de partida: `config/diccionario_datos.yaml` del prototipo `mcp-bbdd`
(1.083 líneas, 34 fichas). Se conserva su espíritu —ficha con `descripcion`,
`grano`, `columnas`, `relaciones`, `ejemplos_preguntas`, más un bloque de notas
globales que se sirve entero— y se corrigen sus tres carencias: no distingue
capas ni régimen de refresco, no tiene noción de base de datos, y sus reglas
duras son prosa suelta sin código ni ámbito.

### 3.1 · Ficheros

```
config/diccionario/
├── 00_global.yaml        notas, reglas duras, esquemas, pendientes, batería
├── _meta.yaml
├── raw.yaml
├── stg.yaml
├── aux.yaml
├── mart.yaml
├── cierre.yaml
├── compras.yaml
├── maestro.yaml
└── retenciones.yaml
```

El orden de carga es el alfabético del nombre de fichero, y ese orden es el que
entra en el SHA-256 de `hash_fuente` (R22): así el hash es reproducible.

### 3.2 · `00_global.yaml` — estructura

```yaml
# config/diccionario/00_global.yaml
version: 1                    # DA-5: número manual, se sube a mano al cambiar
base: sigrid_dm
titulo: Datamart de seguimiento anual de obra
descripcion_negocio: >-
  Conocimiento de negocio de la obra de Construcciones Ruesma extraído de
  Sigrid: presupuesto, planificación mensual, producción, cierre económico,
  compras a proveedores y retenciones.

ejes:                         # los cuatro escenarios del seguimiento
  - eje: magnitud
    valores: [COSTE, VENTA]
  - eje: naturaleza
    valores: [REAL, PLANIFICADO]

convenciones:
  moneda: EUR
  importes_iva: >-
    Los importes de `compras` son SIN IVA. El único importe CON IVA del
    datamart es maestro.proveedores_obra.importe_contratado.
  fechas: >-
    En `raw` las fechas son enteros YYYYMMDD y el 0 significa NULL. En el
    resto de esquemas ya vienen tipadas.
  timestamps: >-
    Los timestamps de `_meta` son UTC SIN zona horaria.

esquemas:                     # R4: una entrada por cada uno de los NUEVE
  mart:
    titulo: Seguimiento mensual listo para consumo
    para_que_sirve: >-
      Es la superficie principal para preguntas de planificación y producción.
    consumo_recomendado: true
    refresco: nocturno
    pasos_etl: [build_mart]
  cierre:
    titulo: Cierre económico mensual
    para_que_sirve: >-
      Ejecutado y previsto por obra y mes, con beneficio derivado.
    consumo_recomendado: true
    refresco: manual
    pasos_etl: [build_cierre]
  # ... las siete restantes

reglas:                       # R9: las doce reglas duras
  - codigo: R-IMPORTE-MES
    titulo: importe_mes no se suma entre meses
    severidad: bloqueante
    ambito:
      - mart.fact_seguimiento_mensual
      - mart.fact_seguimiento_categoria
      - stg.plan_mensual
    regla: >-
      Para una serie temporal se suma `importe_mes` dentro de cada mes y
      NUNCA entre meses distintos. `importe_origen` YA es acumulado: sumarlo
      en el tiempo multiplica el resultado.
    motivo: >-
      Fue el bug de la Tanda 1.4 del cierre: multiplicaba por unas nueve
      veces (cierre/02_build_fact.sql:7-15).
  # ... las once restantes

ordenes_de_magnitud:          # R10: para detectar cifras absurdas
  - concepto: Retenido a proveedores (total empresa)
    valor_aproximado: 34700000
    unidad: EUR
  - concepto: Retenido de clientes (total empresa)
    valor_aproximado: 21900000
    unidad: EUR
  - concepto: Efectos de retención registrados
    valor_aproximado: 27300
    unidad: filas

ocultar:                      # patrones fnmatch de columnas técnicas
  - "_ingested_at"
  - "_source_tiemod"

pendientes: []                # R27: trinquete. Vacía al cerrar F-006

preguntas_aceptacion:         # R39: la batería de requirements.md §9
  - id: P11
    pregunta: Dame la evolución mensual del coste directo de la obra X en 2025
    objetos_esperados: [mart.fact_seguimiento_mensual]
    respuesta_correcta: >-
      Usa importe_mes. Si suma importe_origen en el tiempo, la respuesta es
      incorrecta aunque el número parezca razonable.
    estado: respondible
  - id: P4
    pregunta: ¿Cuál es el flujo de caja de la obra X?
    objetos_esperados: []
    respuesta_correcta: >-
      "El datamart no tiene tesorería." Cualquier número es incorrecto.
    estado: bloqueada
    bloqueada_por: F-037
```

### 3.3 · Fichero de esquema — ejemplo de FICHA COMPLETA

Este es el contrato. Una ficha con todos los campos, opcionales incluidos:

```yaml
# config/diccionario/mart.yaml
version: 1
esquema: mart

objetos:

  fact_seguimiento_mensual:
    tipo: tabla                     # tabla | vista | funcion
    capa: consumo                   # origen | preparacion | consumo | operacion
    consumo_recomendado: true
    descripcion: >-
      El hecho central del seguimiento: cuánto se ha producido y cuánto se
      había planificado, mes a mes, para cada partida de cada obra, en las
      cuatro combinaciones de coste/venta y real/planificado.
    grano: >-
      Una fila por (obra, partida, mes, escenario). "Escenario" es la
      combinación de magnitud (COSTE o VENTA) y naturaleza (REAL o
      PLANIFICADO): cuatro escenarios posibles por celda.
    clave_negocio: [obra_codigo, partida_codigo, mes, escenario]
    paso_etl: build_mart            # coincide con _meta.v_frescura.paso
    refresco: nocturno              # nocturno | manual | estatico

    columnas:
      # forma abreviada (R6): equivale a {significado: "..."}
      obra_codigo: Código de obra tal y como se teclea en Sigrid.

      # forma completa
      importe_mes:
        significado: >-
          Importe imputado A ESE MES concreto, ya desacumulado.
        unidad: EUR
        agregacion: suma_solo_dentro_del_mes
      importe_origen:
        significado: >-
          Importe ACUMULADO desde el inicio hasta ese mes, tal y como viene
          de Sigrid.
        unidad: EUR
        agregacion: ultimo_valor
      escenario:
        significado: Combinación de magnitud y naturaleza.
        valores: [COSTE_REAL, COSTE_PLAN, VENTA_REAL, VENTA_PLAN]
      version_tex:
        significado: >-
          Texto de la versión master de la que sale el planificado.
        nulo_significa: >-
          La obra no tiene versión master vigente para ese mes.
      fact_id:
        significado: Clave técnica de la fila.
        agregacion: clave_sustituta

    relaciones:
      - de: obra_codigo
        a: maestro.obras.obra_codigo
        cardinalidad: "N:1"
        porque: >-
          Para poner nombre, cliente o estado a la obra. OJO: maestro.obras
          es superconjunto de stg.obras (ver R-UNIVERSO-OBRA).
      - de: partida_id
        a: compras.v_pbi_partida_coste.partida_id
        cardinalidad: "1:1"
        porque: >-
          Es el único eje que une el mundo del seguimiento con el mundo
          documental de compras. Hoy no lo explota ninguna vista: es F-039.

    ejemplos_preguntas:             # R40: al menos una
      - ¿Cuál es la planificación mensual de la obra 0704 en 2025?
      - ¿Qué obras se desvían más de su master vigente en coste directo?

    # avisos: NO se escribe a mano. Lo deriva el validador desde el ámbito de
    # las reglas de 00_global.yaml (R12). Si aparece escrito en el YAML, el
    # validador lo ignora y avisa.
```

### 3.4 · Reglas del formato

| Campo | Obligatorio | Vocabulario |
|---|---|---|
| `tipo` | sí | `tabla` \| `vista` \| `funcion` |
| `capa` | sí | `origen` \| `preparacion` \| `consumo` \| `operacion` |
| `consumo_recomendado` | sí | booleano |
| `motivo_no_consumo` | **sí si `consumo_recomendado: false`** (R3) | texto libre no vacío |
| `descripcion` | sí | texto de negocio |
| `grano` | sí para `tabla` y `vista`; no aplica a `funcion` | texto |
| `clave_negocio` | sí para `tabla` y `vista` | lista de columnas de la propia ficha |
| `paso_etl` | sí salvo `refresco: estatico` | valor de `_meta.v_frescura.paso` |
| `refresco` | sí | `nocturno` \| `manual` \| `estatico` |
| `columnas` | sí si `consumo_recomendado: true` (R26) | mapa |
| `columnas.<c>.agregacion` | no | `suma` \| `promedio` \| `no_sumable` \| `suma_solo_dentro_del_mes` \| `ultimo_valor` \| `clave_sustituta` (R7) |
| `relaciones` | no (lista vacía admitida) | `de` / `a` / `cardinalidad` / `porque`, con `a` resoluble (R5) |
| `ejemplos_preguntas` | sí si `consumo_recomendado: true` | lista no vacía |

**`raw` va a nivel de objeto** (DA-2): ficha con `descripcion`, `grano`,
`clave_negocio` y la relación con `con`, sin `columnas`. Todas sus fichas llevan
`consumo_recomendado: false` y `motivo_no_consumo` apuntando a
`azure-apps/sigrid_tablas.md`, que es el diccionario real de Sigrid y no se
duplica aquí.

---

## 4 · CONTRATO 2 · El esquema de publicación en `_meta`

Esto es **la mitad del contrato con el repositorio `mcp-bbdd`** y lo único que
este repositorio puede garantizarle (riesgo 5 de `requirements.md`). Se fija
aquí y se documenta en `azure-apps/datamart_seg_anual.md` (R38).

### 4.1 · Las tres tablas y la vista

```sql
-- etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql

CREATE TABLE IF NOT EXISTS _meta.diccionario (
    esquema             TEXT    NOT NULL,
    objeto              TEXT    NOT NULL,
    tipo                TEXT    NOT NULL,   -- tabla | vista | funcion
    capa                TEXT    NOT NULL,   -- origen|preparacion|consumo|operacion
    consumo_recomendado BOOLEAN NOT NULL,
    motivo_no_consumo   TEXT    NULL,
    descripcion         TEXT    NOT NULL,
    grano               TEXT    NULL,
    clave_negocio       TEXT[]  NOT NULL DEFAULT '{}',
    paso_etl            TEXT    NULL,
    refresco            TEXT    NOT NULL,   -- nocturno | manual | estatico
    avisos              TEXT[]  NOT NULL DEFAULT '{}',  -- códigos de regla (R12)
    n_columnas          INTEGER NOT NULL DEFAULT 0,
    ficha               JSONB   NOT NULL,   -- columnas, relaciones, ejemplos
    PRIMARY KEY (esquema, objeto)
);

CREATE TABLE IF NOT EXISTS _meta.diccionario_reglas (
    codigo    TEXT    PRIMARY KEY,
    titulo    TEXT    NOT NULL,
    severidad TEXT    NOT NULL,             -- bloqueante | aviso
    ambito    TEXT[]  NOT NULL,
    regla     TEXT    NOT NULL,
    motivo    TEXT    NOT NULL,
    orden     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS _meta.diccionario_publicacion (
    id             SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version        TEXT         NOT NULL,
    hash_fuente    TEXT         NOT NULL,   -- SHA-256 de los YAML en orden
    publicado_en   TIMESTAMP    NOT NULL,   -- UTC sin zona, como el resto de _meta
    batch_id       TEXT         NULL,
    n_objetos      INTEGER      NOT NULL,
    n_reglas       INTEGER      NOT NULL,
    n_columnas     INTEGER      NOT NULL,
    cobertura_cols NUMERIC(5,2) NOT NULL
);
```

**Por qué `ficha JSONB` y no un modelo normalizado por columnas.** El MCP hace
exactamente dos cosas: listar objetos (necesita `descripcion` y `grano`, que son
columnas de verdad y se filtran barato) y describir uno (necesita la ficha
entera de una sola vez). Una tabla `diccionario_columnas` obligaría a un JOIN y
a mantener dos esquemas para no ganar ninguna consulta que alguien vaya a
escribir. `n_columnas` sale a columna porque es lo que mide la cobertura y no
debe exigir abrir el JSONB.

**Por qué una tabla de publicación de una sola fila.** El `CHECK (id = 1)` la
convierte en un singleton: no hay forma de que queden dos versiones publicadas.
Responde «¿el diccionario que estás leyendo es el del repositorio?» comparando
`hash_fuente` sin salir de SQL.

### 4.2 · La vista de consumo

```sql
CREATE OR REPLACE VIEW _meta.v_diccionario AS
SELECT d.esquema,
       d.objeto,
       d.tipo,
       d.capa,
       d.consumo_recomendado,
       d.descripcion,
       d.grano,
       d.clave_negocio,
       d.refresco,
       d.avisos,
       d.n_columnas,
       d.ficha,
       d.paso_etl,
       f.ultimo_ok_finished_at,
       f.horas_desde_ultimo_ok,
       f.ultimo_intento_status,
       p.version        AS diccionario_version,
       p.publicado_en   AS diccionario_publicado_en
FROM _meta.diccionario AS d
LEFT JOIN _meta.v_frescura AS f ON f.paso = d.paso_etl
LEFT JOIN _meta.diccionario_publicacion AS p ON TRUE;
```

Los dos `LEFT JOIN` son deliberados (R15). El de `v_frescura`, porque un objeto
cuyo paso nunca terminó bien tiene que seguir saliendo, con la frescura a nulo:
esconderlo sería justo el silencio que F-024 eliminó. El de
`diccionario_publicacion` —un `LEFT JOIN ... ON TRUE` y no un `CROSS JOIN`—
porque con la tabla vacía un `CROSS JOIN` devolvería **cero filas** y la vista
mentiría diciendo que no hay diccionario.

Con esta vista, **una sola consulta devuelve significado y fecha de build**, que
es lo que resuelve la pregunta P15 de la batería.

### 4.3 · Qué garantiza este contrato y qué no

| Garantiza | No garantiza |
|---|---|
| Nombres de tabla, columnas y tipos estables | Que el MCP los use (eso es de `mcp-bbdd`) |
| `_meta.v_diccionario` como punto de entrada único | El transporte, la autenticación ni la auditoría |
| Que la publicación es atómica (R18) | Que el diccionario sea correcto: eso lo garantiza la revisión humana |
| Que `hash_fuente` identifica la versión exacta | Que alguien lo compruebe |

**Cambios futuros del contrato**: añadir columnas al final de
`_meta.v_diccionario` es compatible (`CREATE OR REPLACE VIEW`). Quitar o
reordenar exige `DROP VIEW`, y eso **se lleva los GRANT** (§9.3): quien lo haga
debe ejecutar `apply-grants` inmediatamente después. Está escrito en R23 y va
como comentario de cabecera en el propio fichero SQL.

---

## 5 · Ficheros a crear

### 5.1 · El diccionario (el grueso del trabajo)

| Fichero | Contenido |
|---|---|
| `config/diccionario/00_global.yaml` | Notas, convenciones, los nueve esquemas, las doce reglas duras (R9), órdenes de magnitud (R10), `ocultar`, `pendientes` (R27) y la batería (R39) |
| `config/diccionario/mart.yaml` | ~11 objetos: 2 tablas de hecho + 9 vistas |
| `config/diccionario/cierre.yaml` | ~10 objetos: 1 tabla, 6 vistas, 3 funciones |
| `config/diccionario/compras.yaml` | ~14 objetos: 7 tablas, 4 vistas, 3 funciones |
| `config/diccionario/retenciones.yaml` | ~9 objetos: 2 tablas, 7 vistas |
| `config/diccionario/maestro.yaml` | ~4 objetos: 3 vistas, 1 función |
| `config/diccionario/stg.yaml` | ~11 objetos: 7 tablas, 1 vista, 3 funciones |
| `config/diccionario/aux.yaml` | 1 objeto (`periodificacion_partida`, hoy vacía por diseño) |
| `config/diccionario/_meta.yaml` | 6 objetos: `etl_runs`, `v_raw_state`, `v_frescura` y los tres nuevos |
| `config/diccionario/raw.yaml` | 31 fichas a nivel de objeto (DA-2), todas `consumo_recomendado: false` |

### 5.2 · Código

| Fichero | Contenido | Capa |
|---|---|---|
| `etl_sigrid/domain/diccionario.py` | Entidades y validación. Ver §8.1 | domain |
| `etl_sigrid/domain/inventario.py` | Extracción del inventario de objetos a partir de textos SQL y del YAML de tablas. Ver §8.2 | domain |
| `etl_sigrid/infrastructure/diccionario/__init__.py` | — | infrastructure |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | Lee `config/diccionario/*.yaml`, calcula el SHA-256, construye el `Diccionario` del dominio | infrastructure |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | Constructores puros de sentencias de publicación, con el mismo patrón que `grants.py` | infrastructure |
| `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql` | El DDL de §4 | infrastructure |
| `etl_sigrid/application/steps/publicar_diccionario_step.py` | `PublicarDiccionarioStep` | application |

### 5.3 · Tests

| Fichero | Requisitos |
|---|---|
| `tests/test_f006_formato.py` | R1–R8 (validador, con YAML sintéticos en `tmp_path`) |
| `tests/test_f006_reglas.py` | R9–R12 (reglas, ámbito, derivación de avisos) |
| `tests/test_f006_frescura.py` | R13, R14, R16 (y el cruce contra `build_pipeline_steps` real) |
| `tests/test_f006_publicacion.py` | R17–R23 con un doble de `PostgresClient` |
| `tests/test_f006_cobertura.py` | R24–R27, R29 — corre sobre el diccionario **real** del repositorio: es la puerta |
| `tests/test_f006_grants.py` | R30–R33 (generador de `GRANT`/`REVOKE`, función pura) |
| `tests/test_f006_docs.py` | R35–R38 (asertos sobre el runbook y `infra/README.md`) |

## 6 · Ficheros a modificar

| Fichero | Qué cambia |
|---|---|
| `config/settings.py` | `DEFAULT_CONSUMPTION_SCHEMAS` pasa a `_meta,mart,cierre,compras,maestro,retenciones,aux` (R30), con el comentario explicando por qué salen `raw` y `stg`. Nuevo campo `revoke_fuera_de_consumo: bool = False` (`PG_REVOKE_FUERA_DE_CONSUMO`, R32) y `diccionario_dir` con default `config/diccionario` |
| `etl_sigrid/infrastructure/postgres/grants.py` | `build_readonly_grant_statements(..., revocar_en: Sequence[str] = ())`: además de los `GRANT` de hoy, emite para cada esquema de `revocar_en` el trío `ALTER DEFAULT PRIVILEGES ... REVOKE SELECT ON TABLES`, `REVOKE ALL ON ALL TABLES IN SCHEMA`, `REVOKE USAGE ON SCHEMA`, en ese orden. Sigue siendo función **pura** |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `apply_readonly_grants(...)` acepta `revocar: bool = False` y calcula `revocar_en` = `list_schemas()` menos consumo menos `ESQUEMAS_SISTEMA` (R33). Métodos nuevos: `publicar_diccionario(dicc, hash, informe, batch_id) -> int` y `list_objetos_catalogo(schemas) -> list[tuple]` (para `check-diccionario`, R28). Constantes SQL a nivel de módulo, como `SQL_OCUPACION_DISCO`, para que los tests estáticos las lean |
| `etl_sigrid/application/steps/apply_grants_step.py` | Pasa `revocar=pg_settings.revoke_fuera_de_consumo` y lo deja en `result.metadata["revocado"]`. El resto del comportamiento (no-op sin rol, aviso si el rol no existe) no cambia |
| `main.py` | `build_pipeline_steps` inserta `PublicarDiccionarioStep(settings, batch_id=batch_id)` **entre** `BuildMartStep` y `ApplyGrantsStep` (R20). Comandos nuevos `publicar-diccionario` y `check-diccionario`, ambos por los helpers `_arrancar_ejecucion` / `_ejecutar_paso` de F-024 |
| `infra/sql/02_roles.sql` | El bucle de esquemas del bloque 5 pasa a los siete de consumo y el comentario deja de decir «el MCP lee TODOS los esquemas». Es solo el arranque: los GRANT reales los sigue reaplicando el ETL |
| `docs/ARCHITECTURE.md` | Sección nueva «El datamart se explica solo (F-006)»: el diccionario, las tres tablas de `_meta`, la puerta de cobertura, el estrechamiento del rol y el porqué del `REVOKE` |
| `docs/CONVENTIONS.md` | Regla nueva: **quien añade o cambia un objeto publicado actualiza su ficha en `config/diccionario/` en el mismo trabajo**. Misma familia que la regla de propiedad de `azure-apps/` |
| `docs/runbook_postgres_azure.md` | Procedimiento del firewall para el entorno del MCP (R35–R37) y procedimiento de activación del `REVOKE` con su rollback |
| `infra/README.md` | Nota de que la regla del MCP sigue el mismo patrón que la del job, con la advertencia de los nombres de parámetro ya documentada |
| `azure-apps/datamart_seg_anual.md` (repo `azure-apps`) | R38, **en este mismo trabajo**: lo que exponemos (`_meta.v_diccionario` y las tres tablas), el rol estrechado, y corregir que el MCP ya no es «un cliente de escritorio» |
| `harness/features.json` | `"rigor": "critico"` en F-006 (petición del §0 de `requirements.md`) |

## 7 · Ficheros que NO se tocan

- **Todo el SQL de negocio**: `sql/stg/`, `sql/mart/`, `sql/cierre/`,
  `sql/compras/`, `sql/maestro/`, `sql/retenciones/`, `sql/auxiliar/`. Esta
  feature no cambia ni una fila del modelo. Si al escribir una ficha se
  descubre un error en una vista, **se anota y se lleva a su feature**; no se
  arregla aquí. Es la tentación principal de este trabajo: se van a leer las 33
  vistas una por una.
- `etl_sigrid/infrastructure/postgres/sql/ddl/00_meta.sql`: el DDL del
  diccionario va en un fichero nuevo. `00_meta.sql` lo ejecuta
  `_bootstrap_schemas_and_meta` en la **primera conexión de cada proceso**
  (`postgres_client.py:431-452`), y meter ahí tres tablas más encarece el
  arranque de todos los comandos para algo que solo necesita un paso.
- `etl_sigrid/application/orchestrator.py`: el paso nuevo es un `PipelineStep`
  más; el DAG no cambia.
- `etl_sigrid/domain/coherencia.py`, `domain/ejecucion.py`, `domain/tramos.py`:
  las puertas de F-024 y el troceo de F-019 no se rozan.
- `config/tables_sigrid.yaml`: se **lee** para inventariar `raw`, no se
  modifica. Ingerir tablas nuevas es F-036 a F-040.
- `config/business_rules.yaml`: las reglas de negocio ejecutables son otra cosa
  que las reglas-guía del diccionario. F-030 pide justamente separarlas.
- El repositorio `mcp-bbdd` entero: otro repositorio, otro arnés.

## 8 · Clases y funciones

### 8.1 · `etl_sigrid/domain/diccionario.py` (domain)

```python
@dataclass(frozen=True, slots=True)
class Columna:
    nombre: str
    significado: str
    unidad: str | None = None
    agregacion: str | None = None
    valores: tuple[str, ...] = ()
    nulo_significa: str | None = None

@dataclass(frozen=True, slots=True)
class Relacion:
    de: str; a: str; cardinalidad: str; porque: str

@dataclass(frozen=True, slots=True)
class Ficha:
    esquema: str; objeto: str; tipo: str; capa: str
    consumo_recomendado: bool
    descripcion: str
    grano: str | None
    clave_negocio: tuple[str, ...]
    paso_etl: str | None
    refresco: str
    columnas: tuple[Columna, ...]
    relaciones: tuple[Relacion, ...]
    ejemplos_preguntas: tuple[str, ...]
    motivo_no_consumo: str | None = None
    avisos: tuple[str, ...] = ()      # DERIVADO, no se escribe a mano

@dataclass(frozen=True, slots=True)
class Regla:
    codigo: str; titulo: str; severidad: str
    ambito: tuple[str, ...]; regla: str; motivo: str; orden: int = 0

@dataclass(frozen=True, slots=True)
class Diccionario:
    version: str; base: str
    fichas: tuple[Ficha, ...]
    reglas: tuple[Regla, ...]
    esquemas: Mapping[str, Mapping[str, object]]
    pendientes: tuple[str, ...]
    global_raw: Mapping[str, object]   # notas, convenciones, batería, ocultar

@dataclass(frozen=True, slots=True)
class ErrorValidacion:
    fichero: str; objeto: str | None; regla: str; detalle: str

def validar(dicc: Diccionario, pasos_nocturnos: Sequence[str]) -> list[ErrorValidacion]
def derivar_avisos(dicc: Diccionario) -> Diccionario
def formatear_errores(errores: Sequence[ErrorValidacion]) -> str
```

`validar` implementa R2–R7, R9, R11, R13 y R14, y devuelve **todos** los
errores, no el primero: con más de ochenta fichas, un validador que para en el
primer fallo obliga a ochenta vueltas. `pasos_nocturnos` se inyecta desde fuera,
leyéndolo de `build_pipeline_steps` — así R14 no depende de una lista copiada a
mano que se desincronizará el día que el pipeline cambie. `derivar_avisos`
implementa R12 y devuelve un `Diccionario` nuevo, porque las entidades son
inmutables.

### 8.2 · `etl_sigrid/domain/inventario.py` (domain)

```python
@dataclass(frozen=True, slots=True)
class ObjetoPublicado:
    esquema: str; objeto: str; tipo: str; origen: str   # fichero o "tables_sigrid.yaml"

def objetos_de_sql(textos: Mapping[str, str]) -> list[ObjetoPublicado]
def objetos_de_raw(tablas: Sequence[Mapping[str, object]]) -> list[ObjetoPublicado]

@dataclass(frozen=True, slots=True)
class InformeCobertura:
    sin_ficha: tuple[ObjetoPublicado, ...]
    fichas_huerfanas: tuple[str, ...]
    columnas_sin_significado: tuple[str, ...]   # solo en consumo_recomendado
    avisos_columnas: tuple[str, ...]            # el resto
    pendientes_declarados: tuple[str, ...]
    @property
    def ok(self) -> bool

def evaluar_cobertura(dicc, inventario, pendientes) -> InformeCobertura
def formatear_cobertura(informe: InformeCobertura) -> str
```

`objetos_de_sql` recibe un **mapa `ruta -> texto`**: quien lee ficheros es el
test o la CLI, no el dominio. Detecta `CREATE TABLE [IF NOT EXISTS]
<esq>.<obj>`, `CREATE [OR REPLACE] VIEW <esq>.<obj>` y `CREATE [OR REPLACE]
FUNCTION <esq>.<obj>(`, ignorando las líneas de comentario `--`. Su docstring
declara que es **heurística** (R29), que por eso `raw` se inventaría desde
`config/tables_sigrid.yaml` —sus tablas las crea `ensure_raw_table` desde
Python y no hay SQL que leer— y que por eso existe `check-diccionario` (R28).

### 8.3 · `infrastructure/diccionario/cargador_yaml.py` (infrastructure)

```python
def cargar_diccionario(directorio: Path) -> tuple[Diccionario, str]
```

Devuelve el diccionario y el `hash_fuente` (SHA-256 de los ficheros
concatenados en orden alfabético de nombre, R22). Normaliza la forma abreviada
de columna (R6) antes de construir las entidades. Un YAML que no parsea sale
como `ErrorValidacion` con su fichero y su línea, nunca como traza cruda de
`yaml`.

### 8.4 · `infrastructure/postgres/diccionario_sql.py` (infrastructure)

```python
SQL_BORRAR_DICCIONARIO: str
SQL_BORRAR_REGLAS: str
SQL_BORRAR_PUBLICACION: str
SQL_INSERT_DICCIONARIO: str
SQL_INSERT_REGLA: str
SQL_INSERT_PUBLICACION: str

def filas_diccionario(dicc: Diccionario) -> list[tuple]
def filas_reglas(dicc: Diccionario) -> list[tuple]
def fila_publicacion(dicc, hash_fuente, ahora, batch_id, informe) -> tuple
```

Funciones puras que convierten entidades en tuplas listas para `executemany`.
El `ficha` JSONB se serializa aquí con `sort_keys=True`, para que dos
publicaciones del mismo YAML den exactamente el mismo texto y un `diff` sobre la
tabla sea legible.

### 8.5 · `application/steps/publicar_diccionario_step.py` (application)

```python
class PublicarDiccionarioStep(PipelineStep):
    name = "publicar_diccionario"
    stage = "diccionario"
    depends_on = ["build_mart"]
    def __init__(self, settings, client=None, batch_id: str | None = None) -> None
    def run(self) -> StepResult
```

`run()`, en este orden: (1) `cargar_diccionario`; (2) `validar` +
`derivar_avisos`; (3) `evaluar_cobertura`; (4) si hay errores, `FAILED` **sin
abrir conexión de escritura** (R19); (5) ejecutar el DDL idempotente
`ddl/01_diccionario.sql`; (6) `pg.publicar_diccionario(...)`. El `metadata`
lleva `version`, `hash_fuente`, `n_objetos`, `n_reglas` y `cobertura_cols`, así
que `_meta.etl_runs` y `python main.py timings` cuentan qué se publicó cada
noche. Igual que `apply_grants`, admite el cliente inyectado para poder probarse
sin BBDD.

## 9 · El paso de publicación en el pipeline

### 9.1 · Dónde encaja

```
IngestRaw -> LoadExcelAux -> BuildStg -> BuildMart -> PublicarDiccionario -> ApplyGrants
```

Entre `build_mart` y `apply_grants` (R20). **El orden no es cosmético**:
`apply_grants` concede `GRANT SELECT ON ALL TABLES IN SCHEMA _meta`, que es una
foto del instante en que se ejecuta. Si la publicación fuese después, las tres
tablas nuevas dependerían únicamente del `ALTER DEFAULT PRIVILEGES` —que existe
y sí las cubriría, porque las crea `sigrid_dm_etl`—, pero solo mientras nadie
toque esa regla. Publicar antes hace que el `GRANT` masivo de la noche las
alcance siempre.

`depends_on = ["build_mart"]` es formal: el diccionario **no depende de los
datos**. Eso es justamente lo que permite la recomendación de DA-1 —publicarlo
solo en `run-all` y por comando suelto, no al final de cada build manual—:
publicar cinco veces el mismo texto no añade nada y sí superficie de fallo.

### 9.2 · Qué pasa si falla

| Fallo | Qué ocurre | Por qué |
|---|---|---|
| El YAML no parsea o no valida | `FAILED` **antes** de abrir transacción de escritura; el diccionario anterior sigue publicado íntegro (R19) | Debería ser imposible en producción: la puerta offline (§10) lo caza en `init.sh`. Si llega a la noche, es que alguien se saltó el arnés |
| Error de BBDD durante la publicación | `ROLLBACK`: queda publicado el diccionario anterior **completo** (R18) | Son unos cientos de filas en una sola transacción. Nada que ver con `stg.plan_mensual`, que se trocea a propósito (F-019) |
| Cualquiera de los dos, dentro de `run-all` | El paso queda `FAILED`, `run-all` sale con código 1 y la alerta de Azure dispara. **`mart` no se toca ni se deshace** (R21) | Un fallo de publicación es una noticia, no una catástrofe: los datos de la noche son correctos y el diccionario es el de ayer |
| El proceso muere antes de que el paso termine | Su fila queda `RUNNING` y la marca de huérfanas de F-024 la cierra como `ABORTED` en el arranque siguiente | Mecanismo heredado; no se reimplementa nada |

El riesgo residual —diccionario de ayer con datos de hoy— es **aceptable y
mucho menor que la alternativa**: un diccionario a medias, o vacío, dejaría al
MCP inventando significados, que es exactamente lo que esta feature existe para
impedir. Por eso R18 exige atomicidad y no «mejor esfuerzo».

### 9.3 · Relación con `apply-grants`

`apply-grants` se reaplica en **cada** ejecución porque siete ficheros SQL de
`mart`, `cierre` y `compras` recrean vistas con `DROP VIEW ... CASCADE`, y un
`DROP` se lleva por delante los `GRANT` concedidos sobre la vista
(`grants.py`, docstring; `docs/ARCHITECTURE.md` §F-005; `progress/history.md`
:152-157). Tres consecuencias para el diseño de esta feature:

1. **Las tablas del diccionario NUNCA se hacen `DROP`.** El DDL es
   `CREATE TABLE IF NOT EXISTS` y el reemplazo del contenido es `DELETE` +
   `INSERT` (R18). Un `DROP TABLE` + `CREATE` funcionaría igual de bien para los
   datos y dejaría al MCP sin permiso hasta el `apply-grants` siguiente.
2. **`_meta.v_diccionario` se crea con `CREATE OR REPLACE VIEW`**, que permite
   *añadir* columnas al final pero no quitarlas ni reordenarlas. El día que el
   contrato tenga que romperse hará falta `DROP VIEW` y, acto seguido,
   `python main.py apply-grants`. Va como comentario de cabecera del fichero SQL
   y como R23.
3. **La publicación va antes que los grants** (§9.1).

## 10 · La puerta de cobertura

Dos niveles, con propósitos distintos y honestidad sobre lo que vale cada uno.

| | Puerta offline (R24–R27) | `check-diccionario` (R28) |
|---|---|---|
| Dónde | `tests/test_f006_cobertura.py`, dentro de `bash harness/init.sh` | Comando de CLI contra la base real |
| Contra qué compara | El inventario derivado del **repositorio**: regex sobre `sql/**` + `config/tables_sigrid.yaml` | `information_schema` de `sigrid_dm` |
| Coste | Cero: sin red, sin BBDD | Una conexión de lectura |
| Fiabilidad | **Heurística** (R29): puede no ver un objeto creado dinámicamente | La verdad |
| Cuándo corre | En cada `init.sh`, siempre | `MANUAL (humano)`, y al desplegar |
| Qué hace al fallar | `init.sh` en rojo | Sale con código 1 y lista las discrepancias |

La offline es un **trinquete barato**: no demuestra que el diccionario esté
completo, demuestra que nadie ha añadido una vista al repositorio sin
documentarla. La online es la que dice la verdad. Están las dos porque la barata
corre siempre y la cara no.

**Umbrales, y por qué esos** (R25, R26): 100 % de objetos y 100 % de columnas
**dentro de la superficie de consumo**; fuera de ella, aviso. La justificación
larga está en `requirements.md` §5; en corto: un porcentaje del 95 % permite que
la columna que falte sea la importante, porque nadie audita cuál es el 5 %.
Acotar el 100 % a `consumo_recomendado: true` hace el trabajo finito —unas 25 a
30 vistas, no las 31 tablas de `raw` con sus cientos de columnas de Sigrid— y
pone la decisión donde debe estar: en una decisión editorial visible en el diff.
El antídoto contra la trampa evidente (bajar `consumo_recomendado` para esquivar
la puerta) es R3: exige `motivo_no_consumo` escrito.

**El trinquete de `pendientes`** (R27) existe solo para poder entregar por
bloques: mientras se escriben las fichas, los objetos aún sin ficha se declaran
ahí y la puerta los tolera. La puerta falla si la lista **crece** respecto a la
constante declarada en el propio test, y esa constante solo baja, tarea a tarea.
**Al cerrar F-006 la lista debe estar vacía** y ese es un criterio de aceptación
del reviewer.

## 11 · El rol de lectura y los `REVOKE`

### 11.1 · El hallazgo que cambia el diseño

`apply_readonly_grants` **solo concede; nunca revoca** (`postgres_client.py`
:656-694, `grants.py:24-74`). Es decir: cambiar
`DEFAULT_CONSUMPTION_SCHEMAS` para quitar `raw` y `stg` **no le quita nada al
rol**. Los `GRANT` que ya están concedidos siguen ahí hasta que alguien los
revoque explícitamente. Sin R31 esta parte de la feature sería un cambio
cosmético que además daría una falsa sensación de seguridad, que es peor que no
hacer nada.

### 11.2 · Cómo se construye

`build_readonly_grant_statements` gana un parámetro `revocar_en` y emite, por
cada esquema de esa lista y en este orden:

1. `ALTER DEFAULT PRIVILEGES FOR ROLE <owner> IN SCHEMA <e> REVOKE SELECT ON TABLES FROM <ro>`
2. `REVOKE ALL ON ALL TABLES IN SCHEMA <e> FROM <ro>`
3. `REVOKE USAGE ON SCHEMA <e> FROM <ro>`

El orden importa: retirar primero la regla por defecto y después lo concedido.
Al revés, cualquier objeto creado entre ambas sentencias volvería a quedar
concedido. Sigue siendo una **función pura** con identificadores citados por
`psycopg.sql`, comprobable sin BBDD, exactamente como hoy.

`PostgresClient.apply_readonly_grants` calcula la lista:

```
revocar_en = list_schemas() - consumption_schema_list - ESQUEMAS_SISTEMA
ESQUEMAS_SISTEMA = {"public", "pg_catalog", "information_schema", "pg_toast"}
```

Solo esquemas que **existen** en la conexión activa (R33), igual que ya hace el
`GRANT`. La frontera con `albaranes` y `partes` es la propia base: PostgreSQL no
cruza bases y esta feature no toca nada a nivel de servidor.

### 11.3 · Por qué va apagado por defecto

`PG_REVOKE_FUERA_DE_CONSUMO=false` (R32). El pipeline nocturno **no empieza a
revocar permisos por un cambio de valor por defecto**. El motivo es concreto:
hoy `mcp_sigrid_dm_ro` es el único rol de lectura y **Power BI también lo usa**.
Si algún informe lee de `stg` o de `raw`, el `REVOKE` lo deja sin datos y no
salta ninguna alerta: los informes simplemente dejan de refrescar. Por eso R34
exige la verificación manual **antes** de activarlo, y por eso el rollback es un
único cambio de variable de entorno más un `apply-grants`.

### 11.4 · Encaje con F-034 y F-032

- **F-034** (Power BI deja de leer de local, con su propio rol
  `pbi_sigrid_dm_ro`): esta feature **no crea el segundo rol**. Lo que le
  entrega es la lista de consumo ya estrechada y el mecanismo de `REVOKE`
  construido y probado, que es exactamente la pieza que F-034 necesitaría y que
  hoy no existe. Si la verificación de R34 sale sucia, la activación se pospone
  y pasa a ser trabajo de F-034 (DA-3, opción B).
- **F-032** (retirar copias viejas de secretos, incluido
  `pg-mcp-sigrid-dm-ro`, y las reglas de firewall del puesto): **aquí no se
  retira ningún secreto ni ninguna regla**. Esta feature *añade* una regla de
  firewall (la del entorno del MCP) y F-032 seguirá siendo quien limpie las del
  puesto al final.

## 12 · Conectividad

No hay código: es documentación y una autorización que ejecuta el humano.

El patrón bueno ya existe y está probado. El entorno de Container Apps del ETL
(`cae-datamart-seg-dev`) se creó **sin integración de red virtual a propósito**,
y por eso tiene IP de salida estática (`68.221.221.85`), autorizada en el
firewall de `psql-albaranes-rs9k2` como regla `caj-datamart-seg-dev`. El MCP
repite ese patrón: entorno propio sin VNet, se lee su `properties.staticIp` y se
crea una regla con el nombre del entorno.

Lo que el runbook tiene que dejar escrito (R35–R37):

- Que la regla se crea sobre un **recurso de otro proyecto**
  (`rg-albaranes-dev`), que exige autorización explícita del humano recurso a
  recurso y que la ejecuta él.
- Que **el entorno se crea sin VNet**, porque es esa decisión —y no otra— la que
  da IP estática. Escrito como decisión, no como detalle.
- Que **perseguir la IP del puesto no funciona**: D11, la IP rota por CGNAT.
  Está resuelta solo en parte, con una regla única reescrita antes de cada
  tanda, y esa vía no sirve para un servicio desplegado.
- Que **no se debe depender** de la regla que autoriza a cualquier recurso de
  Azure, porque autoriza también a suscripciones ajenas
  (`infra/README.md:172-174`).
- Los nombres de parámetro de `az postgres flexible-server firewall-rule`, que
  no son los que uno espera y ya costaron media hora y una regla de más
  (`infra/README.md:153-170`). Se **enlazan**, no se copian.

## 13 · Límite de microservicio

Se ha evaluado explícitamente, como exige `CLAUDE.md`. **El diccionario semántico
pertenece a este repositorio y el servidor MCP no.** El criterio es el de la
propia ficha de F-006: *el MCP sabe de conexiones, permisos, validación y
auditoría; el significado del dato es del dueño del dato*.

| Responsabilidad | Dónde vive | Por qué |
|---|---|---|
| Qué significa `mart.fact_seguimiento_mensual`, cuál es su grano y qué trampa tiene | **aquí** | Lo sabe quien escribió el SQL que la construye. Nadie más puede mantenerlo sin desincronizarse |
| Publicar ese conocimiento dentro de la base | **aquí** | Es un paso del ETL, y el ETL es este proyecto |
| El rol de lectura y su alcance sobre `sigrid_dm` | **aquí** | `sigrid_dm` es de este proyecto; sus roles se provisionan con `infra/sql/` |
| Transporte HTTP, Entra, grupos, multi-base, auditoría, despliegue | `mcp-bbdd` | Nada de eso es específico de este datamart y va a servir a `albaranes` y `partes` |
| Reglas de negocio como procedimiento en lenguaje natural | repositorio propio, dueño en Negocio | **F-030**. Son guía para decidir, no descripción del dato |
| Dónde se persiste una planificación hecha por la IA | sin decidir | **D8**. El MCP es de solo lectura por diseño y lo que no se hará es relajarlo para que escriba |

La línea es nítida y conviene enunciarla porque se va a poner a prueba: **el
diccionario describe lo que el dato ES; F-030 describe cómo se DECIDE con él.**
Cuando al escribir una ficha aparezca la tentación de explicar cómo se aborda
una planificación, eso es F-030 y no entra en el YAML.

## 14 · Riesgos y alternativas descartadas

### 14.1 · Alternativas descartadas

| Alternativa | Por qué se descarta |
|---|---|
| **Dejar el diccionario en `mcp-bbdd`** (como hoy) | Lo mantendría quien no conoce el modelo, se desincronizaría a la primera, y no habría forma de poner una puerta de cobertura: el repositorio del MCP no sabe qué objetos publica el datamart. Decisión ya tomada por el humano |
| **Publicarlo por HTTP o por fichero compartido** | Obligaría al MCP a conocer una segunda fuente además de la conexión SQL que ya tiene, y rompería el multi-base: cada base publica su semántica en su propio `_meta` y el MCP no necesita saber de dónde salió |
| **Generar el diccionario automáticamente desde `pg_catalog`** | Daría nombres y tipos, que es justo lo que el MCP ya obtiene solo. Lo que falta es el significado y las trampas, y eso no está en ningún catálogo |
| **Un único YAML monolítico** | 34 fichas ya son 1.083 líneas en el prototipo; aquí hay más de 80 objetos. Un fichero por esquema hace el diff revisable y permite entregar por bloques |
| **Modelo normalizado con tabla de columnas** | Un JOIN más y dos esquemas que mantener, para no ganar ninguna consulta que alguien vaya a escribir (§4.1) |
| **Umbral de cobertura porcentual (95 %)** | Permite que la columna que falte sea la importante. Ver §10 |
| **Atomicidad por `DROP TABLE` + `CREATE`** | Se lleva los `GRANT` y deja al MCP ciego hasta el `apply-grants` siguiente (§9.3) |
| **Revocar por defecto** | Power BI usa hoy el mismo rol. Ver §11.3 |
| **Resolver aquí F-036 a F-040** | Son features propias, con su rigor y su prueba de equivalencia. Meterlas aquí convertiría una feature de metadato en un cambio del modelo |

### 14.2 · Riesgos

1. **Volumen.** Es el riesgo principal y no tiene truco: ~50 fichas con
   columnas descritas una a una, más 31 fichas de `raw` a nivel de objeto.
   Mitigación: entrega por bloques (`tasks.md`) con el trinquete de
   `pendientes`, empezando por los esquemas que responden preguntas.
2. **Desincronización.** Un diccionario que miente es peor que no tenerlo,
   porque el agente escribe SQL con aplomo sobre una descripción caducada.
   Mitigación: la puerta doble (§10) y la regla nueva de `docs/CONVENTIONS.md`.
   **Residual asumido**: la puerta offline es heurística; el día que alguien
   cree un objeto por una vía que la regex no ve, el trinquete falla en
   silencio hasta el siguiente `check-diccionario`.
3. **Alcance honesto.** Sin F-036, F-037 y F-038 hay casos de uso que seguirán
   sin respuesta. Si el criterio de cierre se lee como «responde los seis casos
   del humano», **F-006 no puede cerrar**. Se cierra con R41: 13 preguntas bien
   respondidas y 5 bien rechazadas.
4. **El `REVOKE`.** Corre contra un servidor compartido con dos aplicaciones en
   producción y su fallo es silencioso. Mitigado por el default apagado, la
   lista blanca de esquemas del sistema, la verificación manual previa y un
   rollback de una sola variable. **No se ejecuta sin firma del humano.**
5. **Este repositorio no controla al consumidor.** Todo esto sirve solo si el
   servidor MCP lee `_meta.diccionario` en vez de su YAML local. Esa mitad del
   contrato vive en `mcp-bbdd`. Lo único que se puede hacer aquí es fijar y
   documentar el contrato (§4), y eso es exactamente lo que hace §4.3.
6. **Escribir las fichas obliga a leer las 33 vistas.** Es la mejor auditoría
   del datamart que se habrá hecho nunca, y va a destapar errores. La disciplina
   es anotarlos y no arreglarlos aquí (§7).
