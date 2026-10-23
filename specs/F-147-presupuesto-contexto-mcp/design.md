# F-147 · Diseño

## Encaje en la arquitectura

El diccionario ya es una tubería de tres piezas y la feature no añade ninguna:

```
config/diccionario/*.yaml ──cargador_yaml──▶ domain.Diccionario ──diccionario_sql──▶ _meta.*
        (contenido)            (infra)          (validación pura)       (infra)        (contrato)
                                                                                        │
                                                         mcp-bbdd lee por SQL ◀─────────┘
```

- **Dominio** (`etl_sigrid/domain/diccionario.py`, puro): `Regla` gana `resumen`
  y `entrega`; la validación los exige; una función nueva mide el presupuesto.
- **Infraestructura**: el cargador lee las claves; `diccionario_sql.py` las
  publica y omite las `fuera_mcp`; el DDL añade las columnas.
- **Puerta**: un test de pytest (lo ejecuta `bash harness/init.sh`), con el tope
  como constante comentada con su historia, igual que `PENDIENTES_MAX` en
  `tests/test_f006_cobertura.py`. No se toca `init.sh`: la validación del
  diccionario ya vive en pytest y una segunda vía para lo mismo diverge.

**Límite de microservicio.** Todo lo de aquí es de este repositorio (qué se
publica y cuánto). Cómo lo compone `contexto_bbdd` —índice, detalle en
`describir_tabla`, recorte del enrutado, filtro por perfil— es de `mcp-bbdd` (su
F-029). Se le ofrece el contrato del final; no se diseña su código.

## Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `config/diccionario/00_global.yaml` | Las reglas de `revision_reglas.md` (R7): `resumen` y `entrega` en todas; `R-PERFILES` y `R-COMPRAS-LINEA` nuevas (ámbito = unión de las fundidas); fuera las siete fundidas y `R-COSTE-CONSULTA`; `regla`/`motivo` recortados (historia fuera, a `progress/` si hace falta); `R-OBRA-ACTIVA` reescrita (R10, R11), `R-COMPRAS-SIN-IVA` corregida (R12), `R-ALBARAN-ABSURDO` al mínimo y sin cifras (R13); `R-SIGRID-CON` `fuera_mcp`; `orden` sin repetidos; `convenciones.importes_iva` en una línea que remite a la regla, `identidad_sigrid` corta y `fechas` sin `raw` (R14); `esquemas.*.para_que_sirve` ≤ 350 (R16); `version: 59` con su comentario. |
| `config/diccionario/compras.yaml` | Cabecera, punto 1 (IVA, R12); fichas de `compras.fact_compras_linea` (coste de consulta, de `R-COSTE-CONSULTA`), de los objetos SIN empresa (inventario de `R-EMPRESA-POR-DEFECTO`: «mezcla las 38 empresas» y, si lo hay, el camino comprobado); 2 primeras `ejemplos_preguntas` (R15). |
| `config/diccionario/{contabilidad,contabilidad_restringida,tesoreria,tesoreria_restringida,compras_restringida}.yaml` | Lo propio de cada esquema que sale de las cuatro de perfiles (`incompleto`, `num_apuntes_restringidos`, `apuntes_restringidos_mes`, `efectos_restringidos_mes`, cuenta bancaria del proveedor) a la ficha que corresponde; códigos citados → `R-PERFILES`. |
| `config/diccionario/{maestro,retenciones,personal,stg,cierre,mart,descompuestos,_meta}.yaml` | Inventario de empresa donde toque (R9), ficha de `stg.plan_mensual` (coste de consulta), códigos retirados → los nuevos, 2 primeras preguntas (R15). |
| `config/diccionario/{personal,retenciones,cierre}.yaml` y el resto con citas | Sustituir códigos retirados (R8). Inventario de citas hoy: 116 en 23 ficheros (`Grep` de los ocho códigos). |
| `etl_sigrid/domain/diccionario.py` | `Regla.resumen: str = ""` y `Regla.entrega: str = "resumen"` al final de la dataclass; `ENTREGAS = ("resumen", "entera", "fuera_mcp")`; `RESUMEN_MIN = 40`, `RESUMEN_MAX = 300`, `PARA_QUE_SIRVE_MAX = 350`; `_validar_reglas` (R2, R3) y validación de esquemas (R16); `CODIGOS_REGLAS_OBLIGATORIAS` según R8; `presupuesto_contexto` (abajo). |
| `etl_sigrid/infrastructure/diccionario/cargador_yaml.py` | `CLAVES_REGLA` admite `resumen` y `entrega`; `_cargar_reglas` los lee. |
| `etl_sigrid/infrastructure/postgres/diccionario_sql.py` | `SQL_INSERT_REGLA` y `filas_reglas` con `resumen` y `entrega` AL FINAL y sin las `fuera_mcp`; `fila_publicacion` cuenta solo las publicadas (R6). |
| `etl_sigrid/infrastructure/postgres/sql/ddl/01_diccionario.sql` | Bloque `DO` tras el `CREATE TABLE`: si falta la columna en `information_schema.columns`, `ALTER TABLE _meta.diccionario_reglas ADD COLUMN resumen TEXT NOT NULL DEFAULT ''` (ídem `entrega TEXT NOT NULL DEFAULT 'resumen'`). Comentario de contrato aditivo. |
| `etl_sigrid/infrastructure/postgres/sql/compras/15_alarmas_liquidatoria.sql` | Solo el comentario que cita `R-COMPRAS-RESTRINGIDA` → `R-PERFILES`. Sin cambio de SQL ni de sello funcional. |
| Tests que citan códigos retirados (`test_f006_reglas`, `test_f006_fichas`, `test_f037_diccionario`, `test_f128_diccionario`, `test_f135_sql`, `test_f136_login_total`, `test_f138_diccionario`, `test_f141_perfil_restringido`, `test_f146_restringido_sin_contabilidad`) | Ajustar el código esperado al nuevo, sin rebajar lo que comprueban (el aviso sigue existiendo, con otro código). |
| `docs/ARCHITECTURE.md`, `docs/CONVENTIONS.md` | R22, y códigos citados → los nuevos. |
| `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` | Fila de `_meta.diccionario_reglas` (~línea 180): columnas `resumen` y `entrega`, semántica, `fuera_mcp` no se publica, enrutado = 2 primeras preguntas, reparto con la F-029 de `mcp-bbdd`; códigos citados → los nuevos (R21). Commit local en `azure-apps`. `mcp_bbdd.md` NO se toca (es de `mcp-bbdd`). |

## Ficheros a crear

| Fichero | Qué |
|---|---|
| `tests/test_f147_resumen_reglas.py` | R1–R6: carga, validación, filas publicadas, SQL, DDL guardado por `DO`, columnas que lee `mcp-bbdd` intactas, `n_reglas` sin las `fuera_mcp`. |
| `tests/test_f147_contenido.py` | R7–R16: códigos obligatorios y retirados (barrido del árbol), `R-OBRA-ACTIVA` atada a `business_rules.yaml`, IVA, albarán sin cifras, convenciones, esquemas ≤ 350, ≤ 2+ preguntas sin pérdida. |
| `tests/test_f147_presupuesto_contexto.py` | R17–R20: medida con fixtures mínimos, tope, trinquete, bloque nuevo cuenta, y el tope real sobre el diccionario del árbol. |

## Ficheros que NO se tocan

- **Nada de `C:\Users\pgris\PycharmProjects\mcp-bbdd`**: código, tests, `config.yaml`
  ni sus comentarios que citan `R-TESORERIA-RESTRINGIDA` o `R-COMPRAS-RESTRINGIDA`
  (son historia suya y sus tests usan fixtures propios; se le avisa en el pacto).
- `harness/init.sh`, `harness/rigor.json`, `harness/features.json` (salvo estado).
- `etl_sigrid/application/steps/publicar_diccionario_step.py`: ya aplica el DDL
  (`DDL_DICCIONARIO`) y llama a `publicar_diccionario`.
- `etl_sigrid/infrastructure/postgres/postgres_client.py`: usa `filas_reglas`.
- `config/business_rules.yaml` y `etl_sigrid/domain/ventana.py`: `R-OBRA-ACTIVA`
  los cita y un test los lee; no se cambian.
- Las columnas existentes de `_meta.diccionario_reglas`, `_meta.v_diccionario` y
  `_meta.diccionario_contexto`: ni nombre, ni tipo, ni orden.
- `tests/test_f006_fuente_que_gobierna.py`, `test_f006_regla_de_oro.py` y
  `test_f006_copias.py`: `R-SIGRID-CON` sigue en el YAML entera, e
  `identidad_sigrid` sigue citándola sin repetir dónde vive cada campo.

## Clases y funciones

```python
# etl_sigrid/domain/diccionario.py  (dominio, puro)
ENTREGAS = ("resumen", "entera", "fuera_mcp")
MAX_PREGUNTAS_ENRUTADO = 2        # contrato con mcp-bbdd (D8)

@dataclass(frozen=True, slots=True)
class Regla:
    ...                           # campos actuales, sin tocar su orden
    resumen: str = ""
    entrega: str = "resumen"

    @property
    def publicable(self) -> bool: return self.entrega != "fuera_mcp"

@dataclass(frozen=True, slots=True)
class PresupuestoContexto:
    reglas: int
    enrutado: int
    bloques: int
    @property
    def total(self) -> int: ...

def presupuesto_contexto(dicc: Diccionario, bloques: Sequence[str]) -> PresupuestoContexto:
    """Lo que `contexto_bbdd` servirá ENTERO, medido desde el diccionario."""
```

- **Qué mide** (R17): por regla publicable, `codigo + titulo + resumen` (más
  `regla + motivo` si `entera`); por ficha recomendada con preguntas, su
  `esquema.objeto` y sus 2 primeras; y la longitud de cada `texto` de
  `bloques`. El test le pasa `[fila[3] for fila in filas_contexto(dicc)]`: la
  misma función que publica, para no tener otra lectura. El dominio no importa
  infraestructura; por eso recibe los textos ya hechos.
- **Qué no mide**: rótulos y epígrafes de `mcp-bbdd`. Son suyos y constantes;
  copiarlos sería una segunda copia de su código. El tope se fija sobre esta
  misma medida, así que compara igual con igual.
- **Estimación** con esta fórmula: hoy ~78.000 (reglas ~46.200, enrutado ~18.100
  con todas las preguntas, bloques ~13.700); tras la feature ~29.000 (reglas
  ~6.600, enrutado ~13.900, bloques ~8.800). El valor exacto lo fija el
  implementer al medir tras T7 (D10).
- **El tope**: `PRESUPUESTO_MAX` en `tests/test_f147_presupuesto_contexto.py`,
  con la historia de cada bajada al lado. Falla si `total > tope` (cuánto sobra y
  desglose) y si `total < tope − 1.000` (pide bajarlo). 1.000 ≈ cuatro resúmenes:
  bastante para no saltar por una coma, poco para que se acumule holgura.

## Por qué el enrutado es (b): las 2 primeras de `ejemplos_preguntas` (D8)

- **(a) campo propio** (`preguntas_enrutado`) obliga a `mcp-bbdd` a leer una
  clave nueva de la ficha, a decidir qué hace si falta, y deja dos listas de
  preguntas que pueden divergir.
- **(b)** no añade nada al contrato salvo un número: `mcp-bbdd` ya construye el
  enrutado desde `ejemplos_preguntas`, y su F-029 ya incluye «revisar también el
  tamaño del enrutado»; recortar a las 2 primeras es un cambio dentro de ese
  alcance. Este lado solo ordena (R15) y mide con 2.
- **N no se publica como fila** de `_meta.diccionario_contexto`: el MCP de hoy
  sirve los bloques que no conoce como texto al final, así que publicar el número
  añadiría contexto en vez de quitarlo. N = 2 queda escrito en
  `azure-apps/datamart_seg_anual.md` y en `MAX_PREGUNTAS_ENRUTADO`.

## `R-OBRA-ACTIVA` (D6)

- Criterio: el de la ventana, sin inventar otro. Fuente: `config/business_rules.yaml`
  (`ventana`: `estados_que_congelan [1, 11, 25]`, `patron_codigo_administrativo
  ^[0-9]{6}$`, `meses_sin_actividad 12`), `domain/ventana.py`
  (`motivo_de_congelacion`, `meses_transcurridos`) y `SQL_ESTADO_OBRAS`.
- La `regla` lleva la consulta equivalente sobre objetos legibles por el MCP:
  `maestro.obras` (las mismas 924 fichas que `raw.obr`) unida a
  `MAX(make_date(anio, GREATEST(mes, 1), 1))` de `stg.fases` (años 1990–2100), con
  `estado_id NOT IN (1, 11, 25)`, `codigo_obra !~ '^[0-9]{6}$'` y diferencia en
  meses enteros ≤ 12; más `R-EMPRESA-POR-DEFECTO`. Hoy da 41.
- Aviso: `_meta.v_frescura_obra` (`motivo = 'ventana' AND NOT congelada`) da 40:
  la 0726 viva va como `sin_filas` y los domingos todo va como `completa`.
- El test de R11 lee `business_rules.yaml` y exige sus tres valores en la `regla`.

## SQL

Solo `ddl/01_diccionario.sql` (`_meta`). `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
toma `ACCESS EXCLUSIVE` aunque la columna ya exista, y ese DDL corre en CADA
publicación: es el bloqueo que `diccionario_sql.py` evita a propósito al vaciar
con `DELETE`. Por eso el `ALTER` va dentro de un `DO` que mira antes
`information_schema.columns`: el bloqueo se toma una sola vez. Con valor por
defecto constante es un cambio de catálogo (PostgreSQL ≥ 11), sin reescribir.

## Contrato con `mcp-bbdd` (se pacta en T1, antes de implementar)

1. `_meta.diccionario_reglas` gana `resumen` y `entrega` al final. Su lectura de
   hoy no cambia: un MCP sin F-029 sigue sirviendo `regla` y `motivo` enteros.
2. `resumen` es una ORDEN que basta sola; `regla` + `motivo` son el detalle, para
   `describir_tabla` de cada objeto del `ambito` y para quien lo pida.
3. `entrega = 'entera'` se sirve entera siempre. `fuera_mcp` no llega a la tabla.
4. Enrutado: las 2 primeras `ejemplos_preguntas` por objeto; `describir_tabla`,
   todas.
5. Códigos retirados: los ocho de R8; los nuevos, `R-PERFILES` y `R-COMPRAS-LINEA`.
6. Sugerencia para su F-029 (decide `mcp-bbdd`): no servir a un perfil las reglas
   cuyo `ambito` no puede leer.

**Orden de despliegue**: primero este repositorio (un MCP viejo ignora las
columnas y ya ahorra lo que se funde, acorta o deja de publicarse), después la
F-029 de `mcp-bbdd`.

## Riesgos y decisiones

- **Protección perdida en silencio** si un resumen no basta y la IA no pide la
  ficha. Mitigación: resúmenes como orden con columnas exactas, decididos por el
  humano; el detalle en `describir_tabla` llega con la F-029.
- **Ahorro diferido**: con el MCP de hoy, lo servido baja por fusiones, recortes,
  `R-SIGRID-CON`, `R-COSTE-CONSULTA` y `esquemas` (≈ 15.000–20.000); el resto (el
  índice en lugar del texto, y el enrutado a 2) llega con la F-029. Se mide y se
  dice así en `progress/`.
- **Códigos retirados en 23 ficheros**: el barrido de R8 lo vigila.
- **Descartado**: acortar `regla` sin `resumen` (obliga a elegir entre una regla
  que basta y una que cabe); reutilizar `severidad` (mezcla importancia y
  entrega); la puerta como script de `init.sh` (dos vías divergen).
- **Publicar es una escritura en Azure** que autoriza el humano, y la nocturna
  republica el diccionario de la imagen del job: imagen primero, publicación
  después.
