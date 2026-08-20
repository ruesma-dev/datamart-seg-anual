<!-- progress/explore_F-006_mcp_bbdd.md -->
# F-006 · El prototipo local `mcp-bbdd` (2026-08-20)

> Informe del subagente explorador (solo lectura). Lo guarda el líder.
> Ruta explorada: `C:\Users\pgris\PycharmProjects\mcp-bbdd`.

## 1. Git y arnés: no hay ni lo uno ni lo otro

**No es repositorio git**: no existe `.git`. Sin rama, sin commits, sin remoto,
sin copia fuera del disco local. Sí hay un `.gitignore` preparado (ignora `.env`,
`.venv/`, `logs/`, `*.png`, `config/diccionario_generado.yaml`).

**No hay arnés**: no existen `CLAUDE.md`, `.claude/`, `harness/`, `features.json`,
`BACKLOG.md` ni `progress/`. 52 ficheros en total. Cero features declaradas.

## 2. Qué es, técnicamente

Python 3.12, arquitectura hexagonal, ~5.400 líneas. SDK `mcp` 1.28.1 instalado
(`requirements.txt` pide `mcp[cli]>=1.9.0`), usando `mcp.server.fastmcp.FastMCP`.

**Transporte: solo stdio** (`main.py:35`, `transport="stdio"`, único del
proyecto). Arranca desde `claude_desktop_config.json` (server `bbdd-ruesma`).
`starlette` y `uvicorn` ya están en el `.venv` como transitivas: el salto a HTTP
no añade dependencias.

Piezas: `domain/` (entidades, puertos, 7 códigos de error), `application/`
(pipeline + servicios de catálogo, consulta y gráfico), `infrastructure/`
(pool psycopg3, repositorio por `pg_catalog`, diccionario YAML, matplotlib,
logging a fichero y stderr **nunca a stdout**), `interface_adapters/mcp/`
(fábrica = composition root, servidor, presentadores).

**Está vivo**: `logs/mcp_bbdd.log` registra uso continuado del 2026-07-27 al
2026-08-19, 14 días distintos, **88 consultas**. No es código desechable.

## 3. El pipeline de validación de solo lectura

`fabrica.py:60-79`, orden barato-antes-que-caro:
`normalizar_sql -> validar_solo_lectura -> validar_objetos -> aplicar_limite -> ejecutar -> auditar`.
Todo pasa por `ServicioConsulta`: no hay forma de saltárselo.

1. **Normalizar**: rechaza SQL vacío; sustituye comentarios por espacios (no los
   borra, para no fusionar tokens); `;` intermedio fuera de cadena = multisentencia
   bloqueada; `;` final se recorta.
2. **Solo lectura**: primera palabra en `SELECT`/`WITH`; ninguna de las 35
   palabras prohibidas (INSERT, UPDATE, DELETE, DROP, GRANT, COPY, SET, DBLINK,
   `PG_READ_FILE`...). El propio docstring avisa: «la defensa efectiva es el rol
   SELECT-only más `default_transaction_read_only = on`».
3. **Objetos**: bloquea `pg_catalog`/`information_schema`/`pg_toast`; exige
   esquema en la lista blanca; avisa (no bloquea) si hay tablas sin cualificar.
4. **Límite**: **envuelve** la consulta (`SELECT * FROM (...) AS _mcp_sub LIMIT n+1`)
   en vez de concatenar; pide una fila de más para distinguir «hay n» de
   «está truncado». Default 200, techo 2000.
5. **Ejecutar**: recorte por límite y por volumen (`max_celdas_respuesta=20000`).
6. **Auditar**: log con filas, ms, truncado y SQL aplanado.

El **analizador** (`analizador_sql.py`) es un tokenizador léxico escrito a mano:
cadenas con escape `''`, identificadores entrecomillados, dollar-quoting,
comentarios de bloque anidados. Por eso acepta `WHERE nombre = 'DROP TABLE x'`
y bloquea `SELECT 1; DELETE FROM t`.

**Barrera real**: `pool.py:25-37` fija por conexión
`default_transaction_read_only=on`, `statement_timeout`,
`idle_in_transaction_session_timeout=30000`, `application_name=mcp-bbdd`.
El pool abre con `wait=False` a propósito: si Postgres está caído, el servidor
arranca igual y falla con mensaje legible.

**Tests**: no hay pytest. Hay `scripts/probar_salvaguardas.py`, banco offline de
**27 casos** (11 que deben pasar, 16 que deben fallar). El README dice 25:
desactualizado.

## 4. `config/diccionario_datos.yaml` — el activo real

**1.083 líneas**, cuatro claves raíz: `notas_globales` (9-143), `convenciones`
(145-180), `ocultar` (182-197, 16 patrones fnmatch) y `tablas` (199-1083,
**34 fichas**). Deriva de un `ESQUEMA_BBDD_SEGUIMIENTO.md` que ya no está.

`notas_globales` se entrega **entero** en cada `contexto_bbdd()`: ejes del modelo
(COSTE/VENTA × PLANIFICADO/REAL), categorías CD/CI/CP/OTRO, reglas críticas
(«NUNCA sumes `importe_origen` entre meses»), enrutado pregunta->tabla, la regla
de compras (filtrar `tipo_doc` o se triplica) y la de retenciones, esta última
escrita a partir de un error real: *salían 38,9 M€ en una sola obra siendo esa
la cifra total de la empresa*. Incluye órdenes de magnitud de referencia
(~34,7 M€ retenidos a proveedores, ~21,9 M€ de clientes, ~27.300 efectos) para
que el modelo detecte cifras absurdas.

Formato de ficha:

    <esquema>.<tabla>:
      descripcion: >- ...
      grano: >- ...
      columnas:
        <col>: "<significado de negocio>"
      relaciones:
        - "<col> -> <esquema>.<tabla>.<col>"
      ejemplos_preguntas:
        - "..."

`listar_tablas` sirve solo `descripcion` y `grano`; la ficha completa va en
`describir_tabla`.

**Cobertura: una sola base, `sigrid_dm`.** No hay noción de «base de datos» en el
YAML (las claves son `esquema.tabla` a secas). Esquemas cubiertos: `mart` (4),
`cierre` (6), `stg` (6), `compras` (11), `retenciones` (7).
**`maestro` y `auxiliar`/`aux`: cero apariciones en todo el proyecto**, y no
están en `esquemas_permitidos` (`mart, cierre, stg, compras, retenciones`): hoy
una consulta a `maestro.*` sería rechazada antes de llegar a Postgres. `raw`
está excluido a propósito.

**Deuda**: `pendiente.yaml` (446 líneas, UTF-16 LE, generado por
`scripts/auditar_diccionario.py --plantilla`) lista **37 tablas con columnas sin
describir**, incluidas las principales. No incluye `retenciones` porque se generó
antes de que entrara en ámbito.

## 5. Qué expone

**7 tools**, todas con un decorador `@_controlado` que convierte cualquier
excepción en texto accionable para el modelo:

| Tool | Qué hace |
|---|---|
| `contexto_bbdd()` | Fecha del servidor, periodos relativos, esquemas, límites y convenciones. «Llámala UNA VEZ al principio» |
| `listar_tablas(esquema?)` | Catálogo con descripción de negocio, sin columnas |
| `describir_tabla(tabla)` | Ficha completa. «Inventar nombres de columna es la causa número uno de respuestas erróneas» |
| `buscar_valor(tabla, columna, texto, limite)` | Búsqueda difusa (trigram o ILIKE): «Pepito» -> `PEREZ GOMEZ, JOSE` |
| `consultar(sql, limite?)` | Ejecuta SELECT/WITH; JSON con columnas, filas, `truncado`, `avisos` |
| `grafico(sql, tipo, ...)` | Devuelve resumen + PNG. 6 tipos de gráfico |
| `estado_servidor()` | Diagnóstico + **recarga en caliente del diccionario** |

**Prompts MCP: NO.** **Resources MCP: NO.** Cero `@servidor.prompt(` y cero
`@servidor.resource(`. El sustituto es `servidor.instrucciones` en
`config/config.yaml:9-58`: 50 líneas de prosa pasadas como `instructions=` a
`FastMCP`. Texto estático, no parametrizable.

**Multi-base: no está modelado en ningún nivel.** Un `ConnectionPool` (min 1,
max 4) contra una sola `conninfo`, un `RepositorioPostgres`, ninguna tool con
parámetro de conexión, y el diccionario indexa por `esquema.tabla`. Añadir una
segunda base es refactor de `Contenedor` + `pool.py` + las 7 firmas.

## 6. Credenciales — y el agujero

`pydantic-settings` con `env_prefix="PG_"`: variables de entorno > `.env` >
defaults. Rutas resueltas contra `BASE_DIR`, nunca contra el cwd.

Apunta a **PostgreSQL local** `localhost:5432/sigrid_dm`, `sslmode=prefer`,
**usuario `postgres` (superusuario)**, con la contraseña en claro en `.env` **y
repetida en `claude_desktop_config.json`** (que además gana por precedencia).

El README y `scripts/crear_rol_lectura.sql` describen un rol `mcp_lectura`
(NOSUPERUSER, solo SELECT, `default_transaction_read_only` a nivel de rol,
`statement_timeout` 15s) que **no se está usando**, y ese script sigue escrito
para la base `partes` y el esquema `public` de la POC original: nunca se adaptó
a `sigrid_dm`. **La barrera que el propio código llama «la real» está apagada.**

## 7. Hoja de ruta que ya escribió el autor (`README.md:236-248`)

| Fase | Qué cambia | Impacto declarado |
|---|---|---|
| 1 (hoy) | POC stdio local | — |
| 2 · Móvil | Servidor remoto **HTTP** | «Solo el adaptador de entrada: `transport="streamable-http"` y añadir autenticación. Dominio y aplicación intactos» |
| 3 · Azure | Container App + PostgreSQL gestionado | Dockerfile, ACR, Key Vault, `PG_SSLMODE=require` |
| 4 · Apps propias | Tools sobre la API REST de cada app | **Un microservicio `mcp-<app>` por aplicación** |
| 5 · Escritura | Crear/modificar por voz | Rol acotado, confirmación por operación, auditoría **en tabla, no en fichero** |

Nota final del autor: si el SQL genérico sale lento o poco fiable, el paso
intermedio son **herramientas de negocio** (`horas_por_trabajador(...)`,
`importe_albaranes(...)`) que encapsulen el SQL correcto.

## Implicaciones para F-006

1. **Sin git y sin arnés**: el trabajo en ese repositorio empieza por `git init`
   más instalación del arnés desde `arnes-base`. No hay historial que preservar.
2. **El diccionario es el activo portable**, y sus reglas están escritas a partir
   de errores reales. Es lo único que no se puede regenerar solo.
3. **`maestro` y `aux` son terreno virgen** en el prototipo.
4. **Multi-base es refactor, no configuración.**
5. **La defensa efectiva está desactivada** (conecta como superusuario).
6. **El camino a cloud ya está pensado y es barato** según el autor: transporte
   HTTP + autenticación, sin tocar dominio ni aplicación.
