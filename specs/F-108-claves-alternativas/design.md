<!-- specs/F-108-claves-alternativas/design.md -->
# F-108 · Diseno — claves alternativas en el diccionario

## 1. Contexto y medidas (solo lectura, MCP, 2026-09-24)

`check-unicidad` deriva sus consultas de `clave_negocio`
(`unicidad_sql.consultas_de_unicidad`), y `_es_unica_por` (dominio) solo da una
columna por unica si es la clave de negocio entera o una `clave_sustituta`. Por
eso F-102 dejo `clave_obra` / `clave_recurso` sin vigilancia en la base
(desviacion 6) y declaro `N:N` las cinco relaciones de `compras` por
`clave_obra` (desviacion 4). La opcion B del humano: declararlas como **claves
alternativas**, que el validador acepta y `check-unicidad` comprueba.

| Candidata | Filas | Distintas | NULL | Veredicto |
|---|---|---|---|---|
| `maestro.obras (clave_obra)` | 922 | 922 | 0 | declarar (R20) |
| `personal.recursos (clave_recurso)` | 2.619 | 2.619 | 0 | declarar (R20) |
| `maestro.v_obra_fichas (clave_obra)` | 922 | 922 | 0 | propuesta (D3) |
| `maestro.cuentas_analiticas (empresa_id, codigo_cuenta)` | 184.234 | 184.234 | 0 | propuesta (D3); el codigo solo: 163.247 |
| `maestro.centros_coste (empresa, codigo_centro)` | 804 | 804 | 0 | propuesta (D3); el codigo solo: 655 |
| `stg.obras (codigo_obra)` | 584 | 584 | 0 | propuesta (D3): su ficha dice «aqui es unico» |
| `maestro.obras (empresa_id, codigo_obra)` | 922 | 922 | — | NO: equivale a `clave_obra` |
| `maestro.centros_coste (obra_id)` | 683 no nulos | 683 | 121 | NO: nadie lo usa como lado 1 |
| `stg.partidas` / `mart.v_pbi_dim_partida (obra_id, codigo_partida)` | 394.018 | 385.084 | 0 | **NO ES UNICA**: hallazgo H1 (§8) |

Ninguna otra relacion del diccionario gana nada: barrido de las relaciones
`N:N`/`1:N` cuyo destino no es unico por la clave declarada; solo las cinco de
`compras` son unicas «de hecho» por una columna que no es su clave.

`check-unicidad` **no esta en `run-all`** (comprobado: ningun step ni `infra/`
lo invoca). «Avisa sin romper la nocturna» se cumple por construccion; su codigo
de salida 1 es el de un comando manual de auditoria, como hoy.

## 2. Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `etl_sigrid/domain/diccionario.py` | `Ficha.claves_alternativas`; `_validar_claves_alternativas`; `_es_unica_por` (tercer caso); mensaje de `_validar_cardinalidad` |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | `"claves_alternativas"` en `CLAVES_FICHA`; `_claves_alternativas(...)` que parsea y denuncia formas invalidas (R2) |
| `etl_sigrid/infrastructure/postgres/unicidad_sql.py` | `ConsultaUnicidad.tipo_clave`; una consulta por clave alternativa (R9-R11); veredictos con «clave alternativa» |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | `_ficha_json` publica `claves_alternativas` si no esta vacia (R18) |
| `main.py` (`check_unicidad_cmd`) | cabecera, rotulo en `--dry-run`, un solo «no existe» por objeto (R14-R15) |
| `config/diccionario/maestro.yaml`, `personal.yaml`, `stg.yaml` | `claves_alternativas` (R20, R22) y una frase en el `significado` de cada columna clave: «clave alternativa, la vigila `check-unicidad`» |
| `config/diccionario/compras.yaml` | cinco relaciones `N:N` -> `N:1`, `porque` reescrito (R21) |
| `config/diccionario/00_global.yaml` | `version: 31`; comentario de cabecera con F-108 |
| `tests/test_f102_obra_principal.py` | `test_f102_r22_la_relacion_por_clave_esta_declarada`: exige `N:1` y que el `porque` nombre la clave alternativa (R23) |
| `tests/test_f107_contrapartidas_cuentas.py` | `test_f107_r4_la_version_sube_a_30`: `>= 30` (R23) |
| `docs/ARCHITECTURE.md` | un parrafo en «El datamart se explica solo» (R24) |
| `azure-apps/datamart_seg_anual.md` (otro repo) | linea de `_meta.diccionario`: el JSONB `ficha` puede traer `claves_alternativas` (R24) |

**Fichero a crear**: `tests/test_f108_claves_alternativas.py` (R1-R24, offline).

## 3. Ficheros que NO se tocan

- **Ningun SQL** (`sql/**`): ni vistas ni indices. En particular, **nada de
  `CREATE UNIQUE INDEX`** (opcion A descartada); R16 lo vigila.
- `sql/ddl/01_diccionario.sql`, `_meta.v_diccionario` y la columna
  `clave_negocio`: la clave nueva viaja en el JSONB, contrato compatible.
- `relaciones_sql.py` / `check-relaciones`: no deriva unicidad, no cambia.
- `postgres_client.comprobar_unicidad`: ejecuta `consulta.sql` y le da igual de
  que clave sea.
- `main.build_pipeline_steps` y los steps: la nocturna no cambia (R16).
- `mcp-bbdd` (otro repositorio): lee el JSONB con `.get` y **ignora** la clave
  nueva sin romperse; servirla al agente es decision D4, fuera de aqui.
- `clave_negocio` de ninguna ficha: `maestro.obras` sigue en `[obra_id]` (sus
  relaciones `N:1` por `obra_id` dependen de ello).

## 4. Dominio (`etl_sigrid/domain/diccionario.py`)

```python
@dataclass(frozen=True, slots=True)
class Ficha:
    ...
    motivo_no_consumo: str | None = None
    #: F-108. Otras combinaciones de columnas que TAMBIEN identifican una fila.
    #: Las comprueba `check-unicidad`; una de UNA columna vale como lado 1.
    claves_alternativas: tuple[tuple[str, ...], ...] = ()
    avisos: tuple[str, ...] = ()
```

- `_validar_claves_alternativas(ficha) -> list[ErrorValidacion]`, regla `"R2"`,
  llamada desde `_validar_ficha` junto a `_validar_clave_negocio`. Errores:
  funcion con claves (R5); ficha sin `columnas` con claves; columna no
  documentada (R3); clave vacia o con columna repetida; clave igual como
  conjunto a `clave_negocio`; dos claves iguales como conjunto (R4).
- `_es_unica_por(ficha, columna)`: tras los dos casos de hoy,
  `if (columna,) in ficha.claves_alternativas: return True`. La guarda `None`
  (`not clave_negocio and not columnas`) **no cambia** (mutantes vivos de F-006,
  `test_f006_supervivientes_logica.py` §6-8). Docstring: «tres formas».
- `_validar_cardinalidad`: el texto `(su clave es [...])` pasa a
  `(su clave es [...]; claves alternativas: [...])` cuando las hay (R8). Su
  docstring conserva «check-unicidad» y «8.778» (lo exige F-042).

## 5. Carga (`cargador_yaml.py`)

`_claves_alternativas(fichero, nombre, valor, errores) -> tuple[tuple[str, ...], ...]`:
`None` -> `()`; lista cuyos elementos son listas no vacias de escalares -> tupla
de tuplas de texto; cualquier otra forma -> error `R1` (`_error`) con el texto
«`claves_alternativas` de `<ficha>` es una lista de claves, cada una una lista de
columnas: `[[clave_obra]]`» y devuelve `()`. `_cargar_ficha` la llama con
`cuerpo.get("claves_alternativas")`. `_tupla` NO se reutiliza: aplana un escalar
y aqui eso es justo lo ambiguo.

## 6. `check-unicidad` (`unicidad_sql.py` y `main.py`)

```python
@dataclass(frozen=True, slots=True)
class ConsultaUnicidad:
    objeto: str
    clave: tuple[str, ...]
    sql: str
    sql_detalle: str
    tipo_clave: str = "negocio"   # o "alternativa" (F-108)
```

`consultas_de_unicidad` (orden: ficha por nombre; negocio primero, luego las
alternativas en el orden del YAML):

```python
for ficha in sorted(dicc.fichas, key=lambda f: f.nombre):
    if ficha.tipo == "funcion":
        continue
    if solo_consumo and not ficha.consumo_recomendado:
        continue
    if ficha.clave_negocio and _clave_garantizada_por_el_motor(ficha) is None:
        consultas.append(_consulta(ficha, ficha.clave_negocio, "negocio"))
    for alternativa in ficha.claves_alternativas:
        consultas.append(_consulta(ficha, alternativa, "alternativa"))
```

`_consulta(ficha, clave, tipo_clave)` (privada) valida identificadores con
`_valida` y construye los dos textos. Para `"alternativa"` inserta, dentro de la
subconsulta y en la de detalle, `WHERE c1 IS NOT NULL AND c2 IS NOT NULL` entre
el `FROM` y el `GROUP BY` (R11). Para `"negocio"` el texto sale **byte a byte
igual que hoy** (lo fijan `test_f006_unicidad.py` y los supervivientes).

- `objetos_saltados`: sin cambio (habla de la clave de negocio). Una ficha
  saltada por `clave_sustituta` o sin clave puede tener aun consultas de
  alternativa: `check-unicidad` las cuenta aparte en la cabecera.
- `interpretar_resultado` y `veredicto_no_comprobado`: si
  `tipo_clave == "alternativa"`, el rotulo es «clave alternativa (c1, c2)» y el KO
  anade «las relaciones que la usan como lado 1 (`N:1`) producirian fan-out».
  Para `"negocio"`, el texto de hoy sin cambios.
- `main.check_unicidad_cmd`: cabecera
  `N comprobacion(es) (K de clave alternativa), S saltado(s)`; en `--dry-run`,
  `-- <objeto>  clave alternativa: (...)`; en el bucle, un `set` de objetos
  inexistentes: tras el primer `NO_EXISTE` de un objeto, sus demas consultas no
  se lanzan ni se cuentan (R14). El resumen conserva las subcadenas que fijan
  los tests (`N con la clave rota`, `N sin comprobar`, `N fichados que no
  existen`); un KO de alternativa suma en `fallos` y sale con 1 (D2).

## 7. Diccionario

```yaml
# maestro.yaml, ficha obras (despues de clave_negocio)
    clave_negocio: [obra_id]
    claves_alternativas: [[clave_obra]]
```

Igual en `personal.recursos` (`[[clave_recurso]]`) y, con D3, en
`maestro.v_obra_fichas`, `maestro.cuentas_analiticas`
(`[[empresa_id, codigo_cuenta]]`), `maestro.centros_coste`
(`[[empresa, codigo_centro]]`) y `stg.obras` (`[[codigo_obra]]`).
Relacion de `compras` (x5):

```yaml
      - de: clave_obra
        a: maestro.obras.clave_obra
        cardinalidad: "N:1"
        porque: >-
          La ficha de obra por su clave legible (F-102): la misma union que por
          `obra_id`, pero legible. Es tambien la llave por la que agregar: por
          `codigo_obra` se juntan fichas de empresas distintas. `clave_obra` es
          clave alternativa de `maestro.obras` (F-108), unica (922 para 922 el
          2026-09-24) y vigilada por `check-unicidad`.
```

Sin `(...)` entre comillas invertidas en el `porque`: `_CLAVE_JOIN` exigiria que
fueran columnas propias. Cifras: las de §1.

## 8. Riesgos y decisiones

**Decisiones abiertas para el humano** (propuesta por defecto entre corchetes):

- **D1 · NULL en una clave alternativa** [se excluyen las filas con NULL]: es lo
  que haria el indice unico descartado y un NULL no casa en un JOIN. La de
  negocio conserva su criterio (agrupa los NULL), sin cambio.
- **D2 · un KO de alternativa sale con codigo 1** [si, igual que la de negocio]:
  el comando es auditoria manual y no esta en `run-all`.
- **D3 · las cuatro candidatas extra** de §1 [declararlas]: medidas unicas y sus
  fichas ya lo afirman en texto; coste de consulta bajo (la mayor, 184.234
  filas). Si no, R22 se cae entera y T6 se recorta.
- **D4 · `mcp-bbdd` no sirve las claves alternativas** al agente [feature aparte
  en `mcp-bbdd`]: hoy las ignora sin romperse.
- **D5 · version 31 del diccionario**: si F-095 (en curso) tambien la sube, quien
  fusione segundo toma la siguiente y ajusta `test_f108_r19`.

**Hallazgo H1 (fuera de alcance, propuesta: feature nueva)**:
`(obra_id, codigo_partida)` **no es unico** en `stg.partidas` ni en
`mart.v_pbi_dim_partida`: 5.203 pares repetidos (4.018 dos veces, 1.185 mas; max
22), 8.934 filas de mas, 159 obras, todas activas. Contradice textos publicados:
`stg.partidas.obra_id` y `mart.v_pbi_dim_partida.obra_id` («los codigos de
partida solo son unicos dentro de su obra») y
`mart.fact_seguimiento_mensual.codigo_partida` («unico por obra»). Posible
relacion con el colapso de capitulos en blanco de F-052; sin investigar. No se
declara como clave alternativa, evidentemente.

**Alternativas descartadas**:
- Indice unico en `personal.recursos (clave_recurso)` (opcion A): un duplicado
  tumbaria `build_personal` esa noche. Decision del humano.
- Marcar `clave_obra` como `clave_sustituta`: falso (no es BIGSERIAL) y
  `check-unicidad` la daria por garantizada sin mirar (F-102, desviacion 4).
- Cambiar la `clave_negocio` de `maestro.obras` a `clave_obra`: rompe todas las
  relaciones `N:1` por `obra_id`.
- Clave alternativa a nivel de COLUMNA (`agregacion` o bandera por columna): no
  expresa claves compuestas (`cuentas_analiticas`) y `agregacion` es vocabulario
  cerrado de contrato con el MCP.
- Columna nueva en `_meta.diccionario`: exige DDL y cambiar la vista (contrato
  por columnas al final); el JSONB crece sin DDL y el MCP lo tolera.

**Riesgos**: (1) el guarda de codigo muerto de `test_f006_unicidad.py` barre
`unicidad_sql.py`: `_consulta` es privada y se usa, sin riesgo; (2) el texto SQL
de la clave de negocio no puede cambiar ni un espacio (tests de F-006); (3)
`check-unicidad --todos` suma 2 a 6 consultas baratas (< 5 s medido).

## 9. Limite de microservicio

Todo vive en este repositorio: el diccionario y sus puertas son del dueno del
dato (ARCHITECTURE, F-006). Lo unico ajeno es servir la clave en `mcp-bbdd`
(D4), que se propone alli y no se disena aqui.
