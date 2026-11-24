<!-- specs/F-168-texto-largo-flujo-obra/design.md -->
# F-168 · Diseño · El texto largo de la partida y de cada línea del flujo de obra

**Rigor: `estandar`** (confirma el provisional de `harness/features.json`). No cumple ningún
disparador de `critico`: no mueve dinero, no escribe fuera del datamart (ni en Sigrid ni a nivel de
servidor del Postgres compartido: suma ~1,5 GB a la base, como F-097 sumó 4,6), no toca
autenticación ni permisos (D6: ningún `GRANT` ni esquema nuevo) y no cambia ningún contrato que
consuman otros (columnas y objetos NUEVOS; ninguna `v_pbi_` cambia). El dato personal medido (M7) es
contacto profesional de proveedores en unas decenas de textos técnicos, el mismo tipo de dato que ya
publica `compras.documento_texto` (F-080, `estandar`).

Cifras: spec-author, Sigrid (`sigrid-api`) y Azure, solo lectura, 2026-11-23. Detalle y tablas
completas: `progress/spec_F-168.md` (M1-M11).

## 1. Lo medido, en una tabla

| Dónde está el texto | Columna | Con texto | MB | Enlace a la partida | ¿Copia? |
|---|---|---:|---:|---|---|
| Partida (todos los ámbitos) | `obrparpar.tex` | 242.438 (60 %) | 165,6 (45 de basura) | es la partida | — |
| Planificación de compras | `dncpro.tex` | 164.012 | 97,6 | `paride` | 61 % de la partida |
| Oferta (comparativo) | `dcopro.tex` | 487.834 | 303,3 | `paride`, `dncproide` | 97 % de la planificación |
| Contrato | `ctrpro.tex` | 132.927 | 67,5 | `paride`, `dncproide` | 75 % de la planificación |
| Albarán | `dcapro.tex` | 305.869 | 158,5 | `paride`, `dncproide` | 99,9 % del contrato |
| Factura | `dcfpro.tex` | 229.090 | 108,7 | `paride`, `dncproide` | 99,6 % del albarán |
| Descompuesto de Estudios y master | campo 9 del `des` | 19 % / 53 % de los registros | ~0,9 GB repetido | ya en `descompuestos.lineas` | — |

Todo es texto plano (0 RTF). Deduplicado, lo de las seis tablas son **206.948 textos y 152 MB**.
**Fuera, con su motivo medido**: `obrparpre.tex` (0 de 14,3 M), `cerpro.tex` (0), `dvfpro.tex` (27),
`comlin`/`comprv` (no tienen columna de texto), `com.tex` (60 de 20.802), las cabeceras `dco`, `ctr`,
`dca`, `dcf`, `dnc` (< 4 % y su memo vive en `con.tex`), `obrctr` (cabecera de venta, 277 de 975,
≤ 682 B) y los pedidos `dcp`/`dcppro` (no ingeridos: 25 pedidos, 656 líneas, D8).

**¿En los comparativos está?** No en la tabla del comparativo: `comlin` no tiene texto. La línea del
comparativo lo tiene en su planificación (`comlin.dncproide`) y en cada oferta (`dcopro.comlinide`),
y el memo del comparativo entero en `con.tex` (5.902 de 20.802), ya en `raw` y sin publicar. Las tres
cosas se publican aquí (R17, R18).

## 2. Encaje, límite y frontera

Todo cabe en este ETL: lee Sigrid por `sigrid-api` en solo lectura y publica en `stg`, `compras` y
`descompuestos`, esquemas que ya sirve el MCP. No hay endpoint, tabla de Sigrid, esquema ni permiso
nuevos.

**Frontera: ¿cruza la frontera del proyecto? Sí, en lo que consumimos y en lo que publicamos.**
(1) Consumimos más de `sigrid-api`: ~856 MB más por noche en seis tablas que ya leíamos (mismo
endpoint, páginas de ~3 MB, ninguna cerca de los 230 s, M5 y M11). (2) La base crece ~1,5 GB en el
PostgreSQL compartido `psql-albaranes-rs9k2` (38 → ~39,5 GB de 64), sin tocar nada a nivel de
servidor. (3) Objetos nuevos que lee el MCP (`mcp-bbdd`): su lista blanca es por esquema y no cambia;
hay que reiniciarlo con el diccionario nuevo. Documento del ecosistema:
`azure-apps/datamart_seg_anual.md` (`pull --rebase` antes, commit aparte, sin `push`).

## 3. Ficheros

**Crear**
- `etl_sigrid/domain/texto_largo.py`: `TOPE_CARACTERES = 16000`, `PATRON_CONTROL`, `limpiar(texto)
  -> str | None`, `texto_id(texto) -> uuid.UUID | None` y `es_recortado(texto_raw) -> bool` (R5-R8).
  Puro, sin dependencias.
- `sql/stg/11_texto_largo.sql`: `stg.fn_texto_largo(TEXT) RETURNS TEXT` y `stg.fn_texto_id(TEXT)
  RETURNS UUID` (`md5(...)::uuid`), `IMMUTABLE PARALLEL SAFE`, con los literales del dominio. Solo
  funciones: es el fichero que entra en el sello de `descompuestos` (R22).
- `sql/stg/12_partida_texto.sql`: `stg.partida_texto` (§4.2).
- `sql/compras/16_textos_linea.sql`: `compras.linea_texto`, `compras.textos` y
  `compras.v_linea_texto` (§4.3).
- Tests: `tests/test_f168_dominio.py`, `test_f168_ingesta.py`, `test_f168_sql.py`,
  `test_f168_descompuestos.py`, `test_f168_diccionario.py` y `test_f168_sandbox.py` (§6).

**Modificar**
- `config/tables_sigrid.yaml`: en `obrparpar`, `dncpro`, `dcopro`, `ctrpro`, `dcapro` y `dcfpro` sale
  `tex` de `exclude_columns` y entra `recortar_columnas: {tex: 16000}`, con el comentario de lo medido
  (sustituye a «descripción larga, no usada en seguimiento»). Nada más cambia en el YAML.
- `etl_sigrid/domain/entities.py`: `TableSpec.recortar_columnas: dict[str, int]` (vacío por defecto).
- `etl_sigrid/application/steps/ingest_raw_step.py`: lee la clave y la valida contra las columnas de
  Sigrid y contra `exclude_columns`/`include_columns` (R4) antes de crear la tabla.
- `etl_sigrid/infrastructure/sigrid/sigrid_api_client.py`: `stream_table(..., recortes: Mapping[str,
  int] | None = None)` escribe la expresión de R3 para esas columnas; el resto, `[col]` como hoy. La
  expresión sale de una función pura `expresion_recorte(col, tope)` en `domain/texto_largo.py`.
- `application/steps/build_stg_step.py`: `_SubStep("texto_largo", "11_texto_largo.sql")` y
  `_SubStep("build_partida_texto", "12_partida_texto.sql", "stg", "partida_texto")` detrás de
  `build_master_versiones`, ejecutados enteros. Fuera de `FICHEROS_DEL_SELLO` y de `TABLAS_ACOTADAS`.
- `application/steps/build_compras_step.py`: `_SubStep(name="textos_linea",
  sql_file="16_textos_linea.sql", ...)` el último, que cuenta `compras.linea_texto`.
- `sql/compras/07_texto.sql`: `WHERE c.tip IN (15, 44)` pasa a `(12, 15, 44, 46)` en las dos tablas
  (R18). Revisar el `CHECK`/comentarios que nombren solo facturas y contratos.
- `sql/descompuestos/01_troceado.sql` y `domain/descompuestos.py`: `fn_trocear` devuelve además
  `texto_largo` = `NULLIF(btrim(split_part(g.reg, '|', 10)), '')`; `POSICIONES["texto_largo"] = 9`
  y `trocear_des` igual (R19). La columna va AL FINAL del `RETURNS TABLE`, para no mover las demás.
- `sql/descompuestos/02_lineas_coste.sql`: `ALTER TABLE descompuestos.lineas ADD COLUMN IF NOT EXISTS
  texto_id UUID`; `CREATE TABLE IF NOT EXISTS descompuestos.textos (texto_id UUID PRIMARY KEY, texto
  TEXT NOT NULL)`; ESTUDIO pone `stg.fn_texto_id(stg.fn_texto_largo(t.texto_largo))` y PLANIF_JO
  `stg.fn_texto_id(stg.fn_texto_largo(p.tex))`; y un `INSERT ... ON CONFLICT DO NOTHING` de sus
  textos en la misma transacción (R20, R21).
- `sql/descompuestos/03_lineas_master.sql`: lo mismo dentro de cada lote (DELETE + INSERT de líneas
  + INSERT de textos en una transacción).
- `application/steps/build_descompuestos_step.py`: `FICHEROS_DEL_SELLO` suma
  `"../stg/11_texto_largo.sql"` (R22). El cambio de `01` y `03` cambia el sello: **retroceso de todo
  el master una vez** (§5).
- Diccionario (§7), `docs/ARCHITECTURE.md` («Qué se copia de Sigrid» y «Los descompuestos»),
  `CLAUDE.md` (mapa: `stg.partida_texto` y `compras.linea_texto`) y `../azure-apps/datamart_seg_anual.md`.

**No se tocan**
- `sql/stg/04_partidas.sql` y `stg.partidas` (D2): ensanchar la tabla que leen casi todos los builds
  con ~120 MB de texto encarecería cada lectura.
- `sql/compras/01_documentos.sql`, `02_fact_linea.sql`, `08` y `09`: las tablas de línea no cambian
  (D3); el texto se une por `(tipo_linea, linea_id)`.
- Las `descompuestos.v_pbi_*` (21 columnas fijas, Power BI), `00_functions.sql` de `stg` y lo que
  está en su sello, `ingest_descompuestos` y `_des_texto` (el texto ya está ahí).
- Los esquemas `*_restringida` y `apply_grants` (D6).

## 4. SQL

**4.1 Limpieza** (`stg/11`). `fn_texto_largo(t)`, en este orden: `\r\n` y `\r` → `\n`; quitar
`PATRON_CONTROL`; `btrim` de `' \t\n'`; `left(…, TOPE)`; `btrim` otra vez (el corte puede dejar
espacios al final); `NULLIF(…, '')`. `PATRON_CONTROL` = `[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]`
(sin `\t` ni `\n`). Python y SQL dan el mismo resultado en los casos del test (R5, R7).

**4.2 `stg.partida_texto`** (`stg/12`, DROP + CREATE en una transacción, R23):
`SELECT o.ide AS partida_id, o.obride AS obra_id, p.codigo_partida, p.descripcion_corta,
stg.fn_texto_largo(o.tex) AS texto, stg.fn_texto_id(...) AS texto_id, octet_length(texto) AS bytes,
char_length(o.tex) >= TOPE AS recortado FROM raw.obrparpar o LEFT JOIN stg.partidas p ON p.partida_id
= o.ide WHERE <texto no nulo>`. Sin filtro de ámbito, fase ni `tip` (R10): `obrparpre.tex` está vacío
y la partida es la misma en coste, venta, fase 0 y master (M7). `LEFT JOIN` porque `stg.partidas` no
publica todos los nodos (F-052); el código sale de `stg` cuando existe. PK `partida_id`; índices por
`obra_id` y `texto_id`. ~242.000 filas, ~120 MB.

**4.3 `compras`** (`compras/16`, una transacción):
1. `linea_texto` = `UNION ALL` de las cinco fuentes de `raw`, cada una con su `tipo_linea` literal,
   `paride`, `dncproide` (NULL en NECESIDAD), documento (`dncide` o `docide`), obra (`obride` de la
   línea; en NECESIDAD, `dnc.obride`), `fn_texto_id(fn_texto_largo(tex))` y `char_length(tex) >=
   TOPE`; solo filas con texto limpio. Luego `igual_a_partida` contra `stg.partida_texto.texto_id` e
   `igual_a_necesidad` contra la fila NECESIDAD de la misma tabla, con la semántica de R14 (un
   `CASE`, nunca `=` a secas, que daría NULL donde toca falso). ~1,32 M filas.
2. `textos` = un `SELECT DISTINCT ON (texto_id)` de las mismas fuentes, para no guardar el texto en
   `linea_texto`. ≤ 207.000 filas.
3. `v_linea_texto` = `linea_texto JOIN textos USING (texto_id)`.
El literal del TOPE va una vez, en el dominio; el SQL usa `stg.fn_texto_largo`. **No se compara por
`linoriide`**: no dice a qué tabla apunta (M3, «factura ~ contrato» casa por casualidad); `paride` y
`dncproide` no son ambiguos.

**4.4 `descompuestos`**. `texto_id` en `lineas` (UUID, ~80 MB en 4,83 M filas) y el texto una vez en
`descompuestos.textos`. `textos` nunca se vacía: un texto que ya no usa ninguna línea queda, y por eso
la ficha manda leerlo siempre uniendo DESDE `lineas`. Su crecimiento es el de los textos nuevos.

## 5. Riesgos, coste y despliegue

- **Tiempo**: +6 a 8 min de ingesta (558 s de las seis tablas hoy) y +2 a 5 min de construcción, sobre
  una nocturna de 5 h 05 (M6, M10). Se mide en T15: si la ingesta pasa de +10 min o la base de +2 GB (R27), se para y se replantea D1.
- **Disco**: ~+1,5 GB (38 → ~39,5 de 64).
- **El retroceso de `descompuestos`**: cambia el sello, así que la primera noche con la imagen nueva
  retrocea a 300 MB por noche (unas 8 noches con el master a medio `texto_id`), salvo que se lance
  MANUAL `build-descompuestos --sin-tope` + `apply-grants` **después de desplegar la imagen** (como
  F-120; al revés, la imagen vieja retrocea hacia atrás). ~15-20 min, mirando antes los créditos de CPU.
- **Un NUL** haría caer el `COPY` de la tabla entera: hoy hay 0 (M7), y la expresión de R3 lo quita en
  origen. Los caracteres de control (≤ 111 por tabla) los quita la limpieza al publicar; en `raw`
  quedan tal cual.
- **El orden de la noche**: `compras` lee `stg.partida_texto` (build_stg va antes) y `descompuestos`
  usa las funciones de `stg/11`; lanzado suelto, cada paso lee lo de la noche anterior.

**Alternativas descartadas** (cada una es una decisión abierta abajo): ingesta incremental por huella
(D1-b), columna en `stg.partidas` (D2-b), columna de texto en cada tabla de línea (D3-b: ~900 MB más,
8 veces lo deduplicado), máscara de postventa (D6-b: de 12 «teléfonos» medidos, 10 eran referencias de
producto) y meter `obs` o cabeceras (ruido y lo personal está ahí).

## 6. Tests (sin red ni BBDD salvo el sandbox)

- `test_f168_dominio.py`: `limpiar` (CRLF, controles, extremos, vacío → None, corte a TOPE),
  `texto_id` (estable, `md5`), `es_recortado`, `expresion_recorte` (R3, R5-R8).
- `test_f168_ingesta.py`: el YAML (R1, R2, tope = `TOPE_CARACTERES`), la validación de R4 y el SQL
  de página de `stream_table` con un cliente HTTP simulado (R3).
- `test_f168_sql.py`: literales del dominio en `stg/11` (R7), `IN (12, 15, 44, 46)` en `07` (R18), las
  cinco fuentes y sus enlaces en `16` (R13), sin `linoriide`, y los `_SubStep` nuevos.
- `test_f168_descompuestos.py`: posición 9 en `fn_trocear` y en `POSICIONES`, `trocear_des` con
  texto multilínea en el campo 9 (R19), el sello cambia con `stg/11` (R22).
- `test_f168_diccionario.py`: fichas y versión (R25), ningún `GRANT`/esquema restringido nuevo (R24).
- `test_f168_sandbox.py` (con `F168_SANDBOX_DSN`; si no, `skip`), patrón de `test_f161_sandbox.py`:
  `raw` mínimo con los tipos reales de la ingesta (`tex` como `text`), ejecuta los ficheros REALES
  `stg/11`, `stg/12`, `compras/07` y `compras/16` y el troceado de `02`; casos: partida solo de venta
  y capítulo con texto (R10), texto de 16.000 (R8), CRLF y control (R5), línea con partida sin texto y
  con necesidad editada (R14), dos líneas con el mismo texto → un `textos` (R15), comparativo con
  memo (R18), vista sin pérdida (R16), PLANIF_JO con el mismo `texto_id` que su NECESIDAD (R20, R21)
  y un fallo provocado que deja la tabla anterior (R23).

## 7. Diccionario (v81 → v82)

Fichas nuevas: `stg.partida_texto`, `compras.linea_texto`, `compras.textos`, `compras.v_linea_texto`,
`descompuestos.textos`; columnas nuevas `descompuestos.lineas.texto_id` y `raw` de las seis tablas
(`tex`). Fichas tocadas: `stg.partidas.descripcion_corta` («el texto largo está en
`stg.partida_texto`»), las de líneas de `compras` y `comparativo_*` (cómo llegar al texto) y
`compras.documento_texto` (ya no son solo facturas y contratos). Trampas que deben decir: el texto de
la partida es uno para todos los ámbitos; «igual a» compara el texto limpio; `recortado` es ≥ TOPE;
`descompuestos.textos` se lee desde `lineas`. Dos `ejemplos_preguntas` por ficha, como mucho, para no
pasar `PRESUPUESTO_MAX`.

## 8. Decisiones

| Decisión | Opciones | Recomendado | Decidido |
|---|---|---|---|
| D1 Cómo se trae el texto | (a) `tex` en `raw` de las seis tablas, con tope y sin NUL en origen: +856 MB y +6-8 min por noche; (b) paso INCREMENTAL por huella (como F-097): ~10 veces menos bytes por noche, pero un paso con estado propio y su primera carga | (a): el coste cabe y (b) duplica el trabajo || (a) (humano, 2026-11-23) |
| D2 Dónde va el texto de la partida | (a) tabla aparte `stg.partida_texto`; (b) columna en `stg.partidas` | (a) || (a) (humano, 2026-11-23) |
| D3 Dónde va el texto de las líneas | (a) catálogo deduplicado `compras.textos` + `compras.linea_texto` + vista; (b) columna `texto` en cada tabla de línea de `compras` (~900 MB) | (a) || (a) (humano, 2026-11-23) |
| D4 Tope | (a) 16.000 caracteres (no corta ninguna línea; corta 8 partidas de basura); (b) 32.000; (c) sin tope | (a) || (a) (humano, 2026-11-23) |
| D5 El campo 9 de los descompuestos | (a) en F-168, con un retroceso MANUAL del master; (b) feature aparte | (a): el humano lo pidió («descompuestos de obra y estudios») || (a) (humano, 2026-11-23) |
| D6 Datos personales | (a) sin máscara, en los esquemas generales (contacto profesional en unas decenas de textos); (b) la máscara de postventa (destroza referencias de producto); (c) máscara dirigida: correo y teléfono tras «tfno/tel/móvil» | (a) || (a) (humano, 2026-11-23) |
| D7 Memo de comparativos y ofertas (`con.tex`, 5.902 + 832) | (a) en `compras.documento_texto`; (b) no | (a) || (a), confirmada por el humano (humano, 2026-11-23) |
| D8 Pedidos (`dcp`/`dcppro`) | (a) fuera: 25 pedidos y 656 líneas, 99 % copia de la planificación; (b) ingerirlos y publicarlos | (a) || (a); albarán y factura SÍ entran (el humano: «Dentro») (humano, 2026-11-23) |
| D9 Historia del texto de la partida (Sigrid no la guarda: un cambio en fase 0 se ve en todos los master) | (a) solo el texto vigente; (b) guardar desde F-168 cada cambio con su fecha | (b) | **(a)** (humano, 2026-11-23): sin historia |
