# F-147 · Diseño (BORRADOR: depende de D1–D10 de `requirements.md`)

## Encaje en la arquitectura

El diccionario ya es una tubería de tres piezas y la feature no añade ninguna:

```
config/diccionario/*.yaml ──cargador_yaml──▶ domain.Diccionario ──diccionario_sql──▶ _meta.*
        (contenido)            (infra)          (validación pura)       (infra)        (contrato)
                                                                                        │
                                                         mcp-bbdd lee por SQL ◀─────────┘
```

- **Dominio** (`etl_sigrid/domain/diccionario.py`, puro): `Regla` gana `resumen`
  (y `entrega` si D2); la validación los exige; y una función nueva mide el
  presupuesto. Es dominio porque solo mira el `Diccionario` ya cargado.
- **Infraestructura**: el cargador lee las claves nuevas; `diccionario_sql.py` las
  publica; el DDL añade la columna.
- **Puerta**: un test de pytest (lo ejecuta `bash harness/init.sh`), con el tope
  como constante comentada con su historia, igual que `PENDIENTES_MAX` en
  `tests/test_f006_cobertura.py`. No se toca `init.sh`: la puerta del diccionario
  ya vive en pytest y una segunda vía para lo mismo es la que diverge.

**Límite de microservicio.** Todo lo que se diseña aquí es de este repositorio
(qué se publica y cuánto). Cómo lo compone `contexto_bbdd` —el índice, llevar el
detalle a `describir_tabla`, recortar el enrutado, filtrar reglas por perfil— es
de `mcp-bbdd` (su F-029) y NO se diseña aquí. El contrato que se le ofrece va al
final y se pacta antes de implementar.

## Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `config/diccionario/00_global.yaml` | Contenido de D1: `resumen` en cada regla, fusiones, eliminaciones, textos acortados, `entrega` (D2); `convenciones.importes_iva` y `identidad_sigrid` según D1/D7; `version: 59` con su comentario. |
| `config/diccionario/{contabilidad,tesoreria,compras,compras_restringida,maestro,stg,descompuestos,cierre}.yaml` | Recibir el detalle que sale de las reglas (inventario de empresa, contadores de lo restringido, cuenta bancaria, coste de consulta...) en la ficha del objeto al que pertenece, y `avisos` actualizados si hay fusiones (D3). Lista exacta: tras D1. |
| `etl_sigrid/domain/diccionario.py` | `Regla.resumen: str = ""` (y `entrega: str = "resumen"` si D2) al final de la dataclass; `ENTREGAS` (vocabulario); `MINIMOS_TEXTO`/máximo del resumen; `_validar_reglas` exige resumen en las publicables; `CODIGOS_REGLAS_OBLIGATORIAS` según D3; función `presupuesto_contexto` (abajo). |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | `CLAVES_REGLA` admite `resumen` (y `entrega`); `_cargar_reglas` los lee. |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | `SQL_INSERT_REGLA` y `filas_reglas` con `resumen` (y `entrega`) AL FINAL; si D4 = no publicar, `filas_reglas` omite las `fuera_mcp`. |
| `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql` | Columna `resumen TEXT NOT NULL DEFAULT ''` (y `entrega`) en `_meta.diccionario_reglas`, tras el `CREATE TABLE`, con comentario de contrato aditivo y guardada por un `DO` (ver SQL). Lo ejecuta ya `publicar_diccionario_step` (`DDL_DICCIONARIO`) en cada publicación. |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | Nada salvo que `publicar_diccionario` necesite otra cosa (no se espera: usa `filas_reglas`). |
| `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md` | Sección del diccionario: resumen obligatorio y presupuesto (R16). |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` | Fila de `_meta.diccionario_reglas` (línea ~180): columna `resumen` y su semántica; nota del reparto con la F-029 de `mcp-bbdd` (R15). Commit local en `azure-apps`. |

## Ficheros a crear

| Fichero | Qué |
|---|---|
| `tests/test_f147_resumen_reglas.py` | R1–R6, R8, R9: carga, validación, publicación (filas y SQL), DDL aditivo, contrato de columnas de `mcp-bbdd` intacto. |
| `tests/test_f147_presupuesto_contexto.py` | R10–R14: la medida, el tope, el trinquete y que un bloque nuevo cuente. Con fixtures de diccionario mínimos, sin red ni BBDD. |

## Ficheros que NO se tocan

- **Nada de `C:\Users\pgris\PycharmProjects\mcp-bbdd`** (código, tests, `config.yaml`).
- `harness/init.sh` y `harness/rigor.json`: la puerta es un test (arriba).
- `etl_sigrid/application/steps/publicar_diccionario_step.py`: ya aplica el DDL
  y llama a `publicar_diccionario`; no necesita cambio.
- Las columnas existentes de `_meta.diccionario_reglas`, `_meta.v_diccionario` y
  `_meta.diccionario_contexto`: ni nombre, ni tipo, ni orden.
- El glosario de F-054 (`_meta.glosario`): es su feature.
- `tests/test_f006_fuente_que_gobierna.py` y `test_f006_regla_de_oro.py`: si D4
  saca `R-SIGRID-CON` del MCP, la regla sigue en el YAML y esos tests siguen
  valiendo sin cambio.

## Clases y funciones

```python
# etl_sigrid/domain/diccionario.py  (dominio, puro)
ENTREGAS = ("resumen", "entera", "fuera_mcp")          # [ABIERTA: D2]

@dataclass(frozen=True, slots=True)
class Regla:
    ...                      # campos actuales, sin tocar su orden
    resumen: str = ""
    entrega: str = "resumen"  # [ABIERTA: D2]

@dataclass(frozen=True, slots=True)
class PresupuestoContexto:
    reglas: int              # caracteres del índice de reglas
    enrutado: int            # caracteres del enrutado con el máximo por objeto
    bloques: int             # `texto` de los bloques publicados en _meta.diccionario_contexto
    @property
    def total(self) -> int: ...

def presupuesto_contexto(dicc: Diccionario, max_preguntas: int) -> PresupuestoContexto:
    """Lo que `contexto_bbdd` servirá ENTERO, medido desde el diccionario cargado."""
```

- **Qué mide y qué no.** Una aproximación declarada, no una réplica de
  `mcp-bbdd`: suma `codigo + titulo + resumen` de cada regla publicable (más
  `regla + motivo` de las `entera`); por objeto recomendado, su clave y sus N
  primeras preguntas (D8); y el `texto` de cada fila que daría `filas_contexto`
  (la misma función que publica, para no tener otra lectura). Los rótulos y
  epígrafes del MCP no cuentan: son suyos y constantes. Copiar su formato aquí
  sería una segunda copia de su código, que es justo lo que este contrato evita.
- **El tope** vive en el test como constante (`PRESUPUESTO_MAX`), con la historia
  de cada bajada comentada al lado. Trinquete: el test falla si `total > tope`
  (dice cuánto sobra y en qué parte) y también si `total < tope − margen` (pide
  bajarlo) **[ABIERTA: margen y valor inicial, D10]**.

## SQL

Solo `ddl/01_diccionario.sql` (`_meta`, capa de contrato), idempotente. Ojo:
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` toma `ACCESS EXCLUSIVE` **aunque la
columna ya exista**, y ese DDL corre en CADA publicación (nocturna incluida). Es
el bloqueo que `diccionario_sql.py` evita a propósito al vaciar con `DELETE` y no
con `TRUNCATE`. Por eso el `ALTER` va dentro de un bloque `DO` que primero mira
`information_schema.columns` y solo altera si falta: el bloqueo se toma una vez,
en la primera publicación. Con valor por defecto constante es un cambio de
catálogo (PostgreSQL ≥ 11), sin reescribir la tabla.

## Contrato con `mcp-bbdd` (se pacta antes de implementar)

1. `_meta.diccionario_reglas` gana `resumen` (y `entrega` si D2) **al final**. Lo
   que lee hoy (`SELECT codigo, titulo, severidad, ambito, regla, motivo ... ORDER
   BY orden, codigo`) no cambia; un MCP sin F-029 sigue sirviendo lo de siempre.
2. Semántica: `resumen` es una ORDEN que basta sola para no cometer el error;
   `regla` + `motivo` son el detalle, para `describir_tabla` de cada objeto del
   `ambito` y para quien lo pida.
3. Si D4 = no publicar, una regla `fuera_mcp` simplemente no está en la tabla.
4. Enrutado (D8): o un campo de ficha que el MCP lee, o N publicado como dato en
   `_meta.diccionario_contexto` (bloque y clave a pactar) y el recorte en el MCP.
5. Sugerencias para su F-029, que decide `mcp-bbdd`: no servir a un perfil las
   reglas cuyo `ambito` no puede leer (hallazgo 5) y llevar el detalle a
   `describir_tabla`.

**Orden de despliegue**: primero este repositorio (columna y contenido; un MCP
viejo ignora la columna y ya ahorra lo que se funde, acorta o deja de publicarse),
después la F-029 de `mcp-bbdd`. Al revés, su F-029 no tendría `resumen` que leer.

## Riesgos y decisiones

- **Protección perdida en silencio** si el resumen no basta y la IA no llama a
  `describir_tabla`. Mitigación: resúmenes como orden con columnas exactas
  (D1, revisados por el humano); el detalle en `describir_tabla` es de F-029.
- **Ahorro diferido**: la mayor parte (≈ 40.000 de ≈ 45.000) solo llega con la
  F-029 de `mcp-bbdd`. Sin ella, F-147 ahorra lo que funde, acorta y deja de
  publicar (≈ 5.000–15.000 según D1). Se mide y se dice así en `progress/`.
- **Alternativa descartada: servir menos acortando `regla` y sin `resumen`.**
  Ahorra sin depender de `mcp-bbdd`, pero obliga a elegir entre una regla que
  basta (larga) y una que cabe (insuficiente). El resumen separa las dos cosas.
- **Alternativa descartada: reutilizar `severidad`** para decidir la entrega (D2).
- **Alternativa descartada: la puerta en `init.sh`** con un script propio: la
  validación del diccionario ya vive en pytest; dos vías divergen.
- **La medida es aproximada** (sin rótulos del MCP): el tope se fija sobre esa
  misma medida, así que compara siempre igual con igual. La cifra real servida se
  mide aparte, en Azure, antes y después (R17, MANUAL).
- **Publicar es una escritura en Azure** que autoriza el humano, y la nocturna
  republica el diccionario de la imagen del job: el despliegue es imagen primero,
  publicación después (memoria «publicar el diccionario solo con su imagen»).
