<!-- specs/F-139-leer-graficos-asociados/design.md -->
# F-139 · Diseño: la IA abre el original del adjunto por `mcp-bbdd`

Mediciones: `progress/spec_F-139.md` (solo lectura, 2026-10-15). Objetivo y decisiones
cerradas: `requirements.md` (cabecera). La versión anterior de esta spec (contraste en
`facturas`) queda **descartada** por el humano; su historia está en el commit `52ac5bf`.

## 1 · Límite de responsabilidad

| Pieza | Dónde vive | Por qué |
|---|---|---|
| El ÍNDICE (qué fichero cuelga de qué documento) | **Este ETL**, ya hecho (F-090) | Sale de Sigrid (`rcg`, `gra`) cada noche, como el resto de `compras` |
| Abrir el original y dárselo a la IA | **`mcp-bbdd`** (decidido) | Es quien habla con la IA y quien sabe qué perfil pregunta; el datamart no ve conversaciones |
| Servir el binario | **`sigrid-api`** (`documents/read`), ya existe | Único acceso a Sigrid; `ruesma_rep` no se replica (~81 GB en compras) |
| Leer o interpretar el contenido | **La IA**, en la conversación | Decisión del humano: escaneado o vectorizado, lo interpreta ella |
| Convertir `.doc`/`.xls` | F-142, aparte | Decisión del humano: se recibe el original |

Consecuencias para los otros proyectos (cada dueño actualiza su documento de `azure-apps`
cuando lo implemente; aquí no se tocan): `mcp-bbdd` **pasa a consumir `sigrid-api`** (hoy
declara expresamente que no lo hace, §1 de `mcp_bbdd.md`) y necesita su clave en
`kv-mcp-bbdd-dev`; `sigrid-api` gana un consumidor de `documents/read`.

## 2 · Cómo funciona la herramienta (contrato H1-H13, `requirements.md` §B)

```
IA ── consultar(SELECT … FROM compras.documento_adjuntos WHERE documento_id = …) ──▶ adjunto_id
IA ── abrir_adjunto(adjunto_id) ──▶ mcp-bbdd
   1. índice, con el login del perfil ............ NO_ENCONTRADO si no hay fila      (H2)
   2. tabla de origen de la familia, mismo login . PERMISO_DENEGADO si la base niega (H3)
   3. sigrid-api documents/read (filename_columns: ["cod"]) ... SIN_BINARIO / ORIGEN_NO_DISPONIBLE (H5, H9)
   4. respuesta: original sin convertir + texto (familia, documento, nombre, tamaño, avisos)   (H6-H8)
   5. traza de la apertura, sin contenido                                                     (H10)
```

**La comprobación de permiso (H3), en concreto.** Con el login del perfil y según la familia
leída en el paso 1:

```sql
SELECT a.adjunto_id, a.cod_repositorio, a.nombre_fichero, a.extension,
       (o.factura_id IS NOT NULL) AS origen_presente     -- columna de la tabla de origen
FROM compras.documento_adjuntos a
LEFT JOIN compras.facturas o ON o.factura_id = a.documento_id
WHERE a.adjunto_id = $1;
```

PostgreSQL comprueba el `SELECT` sobre **todas** las relaciones de la consulta antes de
ejecutarla, haya filas o no: sin permiso sobre `compras.facturas` la sentencia falla con
`permission denied` y el servidor lo traduce al `PERMISO_DENEGADO` que ya existe (F-008 de
`mcp-bbdd`). Se lee una columna de `o` a propósito: un `LEFT JOIN` por clave única cuyas
columnas no se usan es candidato a que el planificador lo elimine. El `LEFT` (y no `INNER`)
es para las 305 ofertas sin fila en `compras.comparativo_ofertas` (H4): quien lee la tabla
las abre, con `origen_presente = false` como aviso.

Alternativa descartada: `has_table_privilege(...)` en el servidor. Hace lo mismo, pero es el
servidor quien decide y sería una lógica más que mantener; con el `JOIN` niega la base, que es
el principio que `mcp-bbdd` ya sigue («quien niega el dato es PostgreSQL»).

**Familias y tablas de origen** (ya están en `relaciones` de la ficha del índice; R9 las fija):

| Familia | Tabla | Columna | Enlaces | Sin fila en origen |
|---|---|---|---|---|
| FACTURA | `compras.facturas` | `factura_id` | 134.047 | 0 |
| CONTRATO | `compras.contratos` | `contrato_id` | 38.169 | 0 |
| COMPARATIVO | `compras.comparativos` | `comparativo_id` | 4.452 | 0 |
| OFERTA | `compras.comparativo_ofertas` | `oferta_id` | 22.074 | 305 |
| ALBARAN | `compras.albaranes` | `albaran_id` | 690 | 0 |

**Sin caché (decidido).** Abrir cuesta mediana 0,20 s, media 0,41 s y máx. 4,3 s en 81
aperturas; un fichero de 47 MB (el mayor) son ~47 s a ~1 MB/s, dentro de los 230 s. No
compensa SharePoint. Si en producción el tiempo cambia, se revisa.

**Tamaño (decidido).** Sin tope; aviso por encima de 20 MB (17 ficheros hoy). Un recurso
incrustado va en base64 (+33 %): el riesgo de que el cliente rechace respuestas grandes es
parte de lo que verifica H13.

## 3 · Ficheros a crear (en este repositorio)

- `tests/test_f139_limite.py` — sin red ni BBDD. R1-R4 (texto de la ficha), R5 (la versión
  sube respecto a `main`, mismo patrón que `tests/test_f090_diccionario.py`), R6 (texto de
  `ARCHITECTURE.md`), R7 (recorre con `ast` los `.py` de `etl_sigrid/` y `main.py`, con un caso
  de sabotaje sobre un módulo temporal y la excepción única de `openpyxl` en
  `load_excel_aux_step.py`, con su control; decisión del humano del 2026-10-15) y R9 (las cinco tablas y columnas existen en
  `config/diccionario/compras.yaml` y están en `relaciones` del índice).

## 4 · Ficheros a modificar

- `config/diccionario/compras.yaml`, ficha `documento_adjuntos`: en «EL FICHERO NO ESTA EN EL
  DATAMART», `filename_columns: ["cod"]` y el 5,7 % (R1), el límite con `mcp-bbdd` sin afirmar
  que la herramienta exista (R2), los ficheros > 20 MB y las 305 ofertas (R4); párrafo nuevo
  «QUIEN PUEDE ABRIR EL FICHERO» con la regla y las cinco tablas (R3) y la regla del índice
  (D1, cerrada). Sin columnas nuevas.
- `config/diccionario/00_global.yaml`: `version` 52 → 53 (R5).
- `docs/ARCHITECTURE.md`: subpunto «El fichero NO se replica» del índice de F-090 (R6).
- `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md`: sección nueva «Abrir el
  original de un adjunto (contrato con `mcp-bbdd`, F-139)» con H1-H13, la tabla de §2, el
  riesgo de H13 y, en «qué se rompe si cambia», las columnas del índice y las cinco tablas de
  origen (R8). Commit local en `azure-apps`, sin push.
- `harness/features.json`: F-139 a `blocked` (R10, el líder tras el APROBADO).
- `progress/current.md`: entrada de la spec.

## 5 · Ficheros que NO se tocan

- Todo el SQL, en particular `sql/compras/14_documento_adjuntos.sql`: el índice no cambia.
- `config/tables_sigrid.yaml`, `etl_sigrid/domain/documento_adjuntos.py`, steps y orquestador.
- `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py`: este ETL no llama a `documents/read`.
- `infra/sql/02_roles.sql` y `apply_grants`: los permisos de hoy ya cumplen la regla
  (estándar y total leen `compras` entero); lo que cambie es de F-141.
- `requirements.txt`/`pyproject.toml`: ninguna dependencia (R7).
- `azure-apps/mcp_bbdd.md` y `azure-apps/sigrid_api.md`: sus dueños los actualizan.

## 6 · Riesgos

| Riesgo | Medida | Tratamiento |
|---|---|---|
| HTTP 500 de `documents/read` con nombre no ASCII | 5,7 % de enlaces; 6/6 fallos con tilde o eñe, 0/75 éxitos; la cabecera `X-Document-Filename` va sin codificar | `filename_columns: ["cod"]` (R1, H5). **Propuesta a `sigrid-api`** (decidido): codificarla como ya codifica `Content-Disposition` |
| El cliente MCP no entrega el PDF al modelo | Las imágenes sí llegan (`grafico` ya devuelve PNG) | H13: `mcp-bbdd` lo verifica con claude.ai y con ChatGPT antes de desplegar y lo resuelve (D2) |
| Formatos que la IA no lee | `.doc` 17.233 contratos, `.xls` 250 ofertas, clase correo (`.msg`) 546 | Aviso (H8); conversión en F-142 |
| Datos personales en el fichero | NIF de firmantes en 3/12 contratos; IBAN en 11/26 facturas | Regla de permisos (R3, H3); traza (H10); clientes de terceros como el resto del datamart (D2) |
| El índice delata al que no lee el origen | `nombre_fichero` (proveedor, número) y `subido_por` (login) | D1: misma regla que el fichero, la aplica F-141 |
| Carga sobre `sigrid-api` | Bajo demanda, un fichero por llamada | Sin barridos: la herramienta abre de uno en uno |
| Renombrar una tabla de origen rompe la herramienta | — | R9 (test) y «qué se rompe si cambia» (R8) |

## 7 · Decisiones cerradas por el humano el 2026-10-15 (la spec queda aprobada)

- **D1 · El índice sigue la regla de su tabla de origen.** «El que tenga acceso a la tabla
  puede acceder a la de los gráficos o su cabecera; si no, no.» Las filas de
  `compras.documento_adjuntos` de una familia (nombre del fichero, `subido_por`,
  `cod_repositorio`…) solo las ve quien lee la tabla de origen de esa familia. **Hoy no
  cambia nada** (estándar y total leen las cinco); aquí se escribe en la ficha (R3) y es un
  **requisito para F-141**, que elige cómo: vistas por familia con
  `security_barrier`/`security_invoker` o RLS. F-139 no crea vistas ni toca permisos.
- **D2 · Tiene que funcionar con ChatGPT.** Mismo tratamiento que el resto del datamart (lo
  consultado ya sale a ese proveedor; riesgo aceptado para `personal` y `contabilidad` el
  2026-09-22 y el 2026-09-26), dicho por escrito en el contrato (R8). H13 se verifica también
  con ChatGPT; si el recurso incrustado en base64 no le vale, `mcp-bbdd` lo comprueba y lo
  resuelve (p. ej. enlace temporal) sin que se decida aquí.
