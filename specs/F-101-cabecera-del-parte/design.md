<!-- specs/F-101-cabecera-del-parte/design.md -->
# F-101 · Diseño técnico

Módulo `personal` (F-057), esquema propio que **no bloquea la nocturna** y que
es el único con datos personales. Nada de esto cruza la frontera del proyecto:
no hay servicio nuevo ni responsabilidad de otro microservicio. **No se toca
`sigrid-api`**, solo se lee por ella.

## 1 · Ficheros a crear

| Ruta | Qué construye |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/personal/03_partes.sql` | `personal.partes` (6.886) |
| `etl_sigrid/infrastructure/postgres/sql/personal/04_recursos_tipos_hora.sql` | `personal.recursos_tipos_hora` (8.959) |
| `tests/test_f101_cabecera_parte.py` | los `test_f101_rN_*` de todos los requisitos |

## 2 · Ficheros a modificar

- `sql/personal/00_setup.sql` — DDL de las dos tablas nuevas con sus índices
  (`CREATE TABLE IF NOT EXISTS`, **nunca `DROP`**: un DROP se lleva los GRANT),
  las dos columnas nuevas de `partes_lineas` y la función
  `personal.fn_fecha_serie`.
- `sql/personal/02_partes_lineas.sql` — añade `codigo_parte` (y `texto_linea`
  si se ingiere `tex`). **Sigue sin nombrar `raw.hmo`.**
- `sql/personal/03_views.sql` → **renombrado a `05_views.sql`**. Contenido
  intacto; solo cambia el número para que el orden de ficheros siga siendo el
  orden de ejecución.
- `etl_sigrid/application/steps/build_personal_step.py` — `SUB_PASOS` pasa de 4
  a 6 entradas, en orden: `setup`, `recursos`, `partes_lineas`, `partes`,
  `recursos_tipos_hora`, `views`. Las dos nuevas declaran
  `target_schema`/`target_table` (cuentan filas); `views` sigue sin contarlas.
- `config/tables_sigrid.yaml` — **solo si se aprueba D-3**: sale `tex` de
  `exclude_columns` de `hmores`, con el comentario y las cifras, igual que hizo
  F-080 con `con.tex`.
- `config/diccionario/personal.yaml` — fichas de los dos objetos nuevos,
  columnas nuevas de `partes_lineas`, y `version: 1 → 2`.
- `config/diccionario/00_global.yaml` — `version: 26 → 27`.
- `tests/test_f057_personal.py` — se actualizan las constantes de ruta
  (`03_views.sql` → `05_views.sql`) y los asserts del step que cuentan 4
  sub-pasos. **El veto de R12 no se toca.**
- `azure-apps/datamart_seg_anual.md` — la tabla de objetos de `personal` pasa
  de 3 a 5 filas, más las trampas nuevas (código repetido, sin histórico de
  precios).

## 3 · Ficheros que NO se tocan

`sql/personal/01_recursos.sql` (la lista blanca de `raw.emp` y el `activo` de
F-057 se quedan como están); `sql/maestro/05_estados_documento.sql` (el
catálogo ya está publicado, aquí solo se lee `raw.conest`);
`config/objetos_pendientes.yaml` (sigue en `[]`);
`etl_sigrid/infrastructure/postgres/{unicidad_sql,relaciones_sql}.py` (los dos
comandos se alimentan del diccionario: lo que hay que escribir es el YAML);
`grants.py` / F-087 (los permisos son **por esquema**: una tabla nueva dentro
de `personal` no necesita nada); `main.py` (`build-personal` ya existe).

## 4 · SQL

### 4.1 `personal.partes` (capa `personal`, fichero `03_partes.sql`)

Grano: una fila por `raw.hmo` = `raw.con` con `tip = 35`. 6.886 filas.

```
FROM      raw.hmo h
JOIN      raw.con c ON c.ide = h.ide          -- R-SIGRID-CON
LEFT JOIN LATERAL (SELECT ce.res FROM raw.conest ce
                   WHERE ce.tip = 35 AND ce.est = c.est
                   ORDER BY ce.ide LIMIT 1) es ON TRUE
LEFT JOIN LATERAL (SELECT COUNT(*) n,
                          COUNT(*) FILTER (WHERE NULLIF(l.obride,0) IS NOT NULL
                                             AND NULLIF(h.obride,0) IS NOT NULL
                                             AND l.obride <> h.obride) d
                   FROM raw.hmores l WHERE l.hmoide = h.ide) ln ON TRUE
```

Columnas: `parte_id` (PK), `codigo_parte`, `descripcion`, `fecha`, `anio`,
`mes`, **`obra_cabecera_id`**, **`centro_coste_cabecera_id`**, `estado_id`,
`estado`, `activo`, `fecha_baja`, `fecha_modificacion`, `num_lineas`,
`lineas_en_otra_obra`, `_built_at`.

El `LATERAL` del catálogo es el patrón ya usado en `maestro/01_obras.sql`; el
del recuento lee `raw.hmores`, **no `personal.partes_lineas`**, para no atar
este fichero al orden de los anteriores.

Índices: `(obra_cabecera_id, anio, mes)`, `(codigo_parte)` —no único— y
`(estado_id)`.

### 4.2 `personal.recursos_tipos_hora` (fichero `04_recursos_tipos_hora.sql`)

Grano: una fila por `raw.reshor`. 8.959 filas, 2.063 recursos, 58 tipos.

```
FROM      raw.reshor rh
LEFT JOIN raw.auxhor a ON a.ide = rh.horide   -- LEFT: 3 filas sin catalogo
LEFT JOIN raw.res    r ON r.ide = rh.reside   -- solo para es_por_defecto
```

Columnas: `reshor_id` (PK), `recurso_id`, `tipo_hora_id`, `codigo_tipo_hora`,
`tipo_hora`, `unidad`, `precio_coste`, `precio_venta`, `cantidad_defecto`,
`cuenta_analitica_id`, `es_por_defecto`, `orden`, `tipo_hora_de_baja`,
`_built_at`. **No entran `prenom`, `cuaide` ni `proide`.**

`unidad` sale del **mismo `CASE` sobre `auxhor.medide`** que
`02_partes_lineas.sql` (1 HORA / 2 DIA / 3 MES / 19 UD / ELSE 'DESCONOCIDA').
Un test compara los dos `CASE` carácter a carácter: dos traducciones que
divergen son peor que una sola equivocada.

Índices: `(recurso_id)`, `(tipo_hora_id)`.

### 4.3 `personal.partes_lineas`

Se añade `codigo_parte VARCHAR(24)` con `LEFT JOIN raw.con c ON c.ide =
l.hmoide` (0 huérfanos medidos, pero `LEFT` por la misma razón que el resto del
fichero). **No se añade obra ni fecha de la cabecera**: eso es lo que F-057
vetó y lo que resuelve `personal.partes`. Si se aprueba D-3, además
`texto_linea TEXT` desde `l.tex`.

### 4.4 `personal.fn_fecha_serie(DOUBLE PRECISION) RETURNS DATE`

`DATE '1899-12-30' + FLOOR(d)::INT`, NULL para 0/NULL/inválido. Local al
esquema como `personal.fn_fecha`, por la misma razón: `personal` se construye
aunque `stg` no exista. **La época está verificada, no supuesta**:
`MAX(con.tiemod)` global = 46287,88 → 2026-09-22 (el sistema está vivo) y el
parte más antiguo, 39784,75 → 2008-11-21, con `con.fec = 20081130`.

## 5 · Capa hexagonal

Nada nuevo en `domain` ni en `application` salvo la tabla de datos `SUB_PASOS`
de `build_personal_step.py`, que crece de 4 a 6 entradas. Todo lo demás es
`infrastructure/postgres/sql/`. El step no aprende SQL: sigue encadenando
ficheros.

## 6 · Tests (sin red ni BBDD)

`tests/test_f101_cabecera_parte.py`, con el patrón de `test_f057_personal.py`:
asserts sobre el **texto** de los SQL (`_compacto`, `_sin_comentarios`), sobre
`SUB_PASOS` y sobre las fichas del diccionario cargadas del YAML real.

- R1–R11: DDL, columnas, PK, `tip = 35`, el `LEFT JOIN LATERAL` del catálogo,
  y que `feccie`/`cla`/`caaide`/`reside` **no aparecen** en `03_partes.sql`.
- R6: `03_partes.sql` no puede declarar una columna llamada exactamente
  `obra_id` ni `centro_coste_id` — el sufijo `_cabecera_` es obligatorio.
- R14: se relanza el veto de F-057 sobre `02_partes_lineas.sql` desde el nuevo
  fichero de tests, para que borrar `test_f057_personal.py` no lo apague.
- R19: los dos `CASE medide` son idénticos.
- R22: `prenom` no aparece en `04_recursos_tipos_hora.sql` (ni en comentario
  ejecutable), igual que el veto de `auxhor.ext` en F-057.
- R28: `_ficha_de("partes").clave_negocio == ("parte_id",)`,
  `_ficha_de("recursos_tipos_hora").clave_negocio == ("reshor_id",)` y las
  relaciones declaradas; y que la ficha contiene las cifras que la hacen útil
  (569 códigos repetidos, 56,2 %, sin histórico).

Lo que **no** se puede verificar sin base va a `tasks.md` como MANUAL.

## 7 · Riesgos y decisiones

- **D-1 · La obra de cabecera se llama `obra_cabecera_id`, nunca `obra_id`.**
  Descartado publicarla en `personal.partes_lineas`: es exactamente lo que
  F-057 vetó con cifras (615 líneas de 14 partes contradicen su cabecera) y lo
  que convierte una auditoría en una atribución equivocada. Patrón F-093: la de
  la línea imputa, la de cabecera audita. El sufijo va también en el centro de
  coste.
- **D-2 · `lineas_en_otra_obra` se materializa en la cabecera.** Alternativa
  descartada: dejar que cada consumidor escriba el `JOIN`. Es una columna
  barata (6.886 filas, un `LATERAL` sobre una tabla ya indexada por `hmoide`)
  y convierte el criterio de aceptación «se puede ver en cuántos partes
  discrepan» en un `WHERE`. Se calcula contra `raw.hmores`, no contra
  `personal.partes_lineas`, para no crear una dependencia de orden.
- **D-3 · `hmores.tex` se ingiere. RECOMENDADO, pendiente del humano.**
  Es la decisión con coste real y va en «Decisiones para el humano» abajo.
- **D-4 · La clave de `recursos_tipos_hora` es `reshor_id`, no el par.** Con
  17 pares repetidos, declarar `(recurso_id, tipo_hora_id)` como
  `clave_negocio` pondría `check-unicidad` en rojo la primera noche. Se declara
  `reshor_id` y la ficha dice por qué, con el caso concreto (recurso 947513,
  tipo 27, dos precios).
- **D-5 · No se publica la vigencia del precio porque no existe.** `reshor` no
  tiene ninguna columna de fecha ni `tiemod`. Inventar una vigencia a partir de
  las líneas de parte sería una construcción del datamart presentada como dato
  de origen. La ficha lo declara y remite a `partes_lineas.precio` para el
  desfase que Juan persigue (56,2 % de 279.034 líneas comparables).
- **D-6 · El usuario que crea el parte queda FUERA.** No está en `con` ni en
  `hmo`; está en `dbo.log`, 8.472.098 filas no ingeridas. Traerlo es una
  feature de ingesta con su propio coste de ventana y su propia conversación
  sobre datos personales, no un hotfix. Se declara en la ficha y se propone
  como feature nueva.
- **D-7 · Renumerar `03_views.sql` a `05_views.sql`** en vez de meter los
  ficheros nuevos como `02b`/`02c`. La convención de `docs/CONVENTIONS.md` es
  `NN_nombre.sql` y el test de F-057 exige que el orden de los sub-pasos sea el
  de los nombres: dos ficheros con el mismo `03` lo rompen. El renombrado es
  `git mv` y toca dos constantes de test.
- **Riesgo · `anio`/`mes` de la cabecera traen basura** (27 años fuera de
  1990-2030, entre ellos 201831 y 11226; 2 meses fuera de 1-12). **No se
  corrigen**, igual que en las líneas: se publican y la ficha lo advierte.
  Corregir en silencio es peor que publicar el defecto.
- **Riesgo · `texto_linea` es texto libre y puede traer nombres de persona**
  (medido: un nombre y dos apellidos). Vive en `personal`, el esquema restringible, y
  la ficha lo declara. Es un argumento a favor de D-3, no en contra.
- **Riesgo · `raw.reshor` está fuera del rol del MCP por F-068** y esta feature
  publica un objeto curado derivado de ella. La revocación sobre `raw.reshor`
  **sigue en pie**: lo que se abre es `personal.recursos_tipos_hora`, sin
  `prenom`, que es exactamente lo que el humano decidió el 2026-09-22.

## 8 · Decisiones para el humano

**D-3 · ¿Se ingiere `hmores.tex`?**

| | Ingerir (recomendado) | No ingerir |
|---|---|---|
| Coste en disco | +284.080 B (277 KiB) sobre los 111 MB de `raw.hmores`: **+0,27 %** | 0 |
| Coste por fila | +0,86 B de media sobre 320,3 B/fila | 0 |
| Qué se gana | El comentario de 13.390 líneas (4,05 %) en 2.306 de los 6.873 partes | Juan sigue sin el texto que pidió |
| Riesgo | Texto libre con nombres de persona (queda en `personal`) | — |

Recomendación: **ingerirlo**. Es tres órdenes de magnitud más barato que
`con.tex` en F-080 (que se aprobó pesando mucho más) y es la mitad de lo que
Juan pidió en el punto 2 de su correo. La verificación del coste de ventana
—cronometrar `ingest --table hmores --full` antes y después— va como tarea
MANUAL, no como suposición.

**D-8 · El tipo de hora por defecto del recurso: ¿solo bandera o también
columna en `personal.recursos`?** Está en **`res.horide`** (2.035 de 2.618
recursos, 850 de 1.354 personas, 0 huérfanos contra `auxhor`).

- **Opción A (recomendada, en el alcance)**: solo `es_por_defecto` en
  `recursos_tipos_hora`. Coste cero. Pega: **4 recursos** tienen un defecto sin
  fila en `reshor`, así que en ellos ninguna fila lo marca y el dato se pierde.
- **Opción B**: además `tipo_hora_defecto_id` / `tipo_hora_defecto` en
  `personal.recursos`. Recupera esos 4 casos, pero toca `01_recursos.sql`, que
  esta feature dejaba intacto.

Recomendación: **A**, con la ficha declarando los 4 casos. Si el humano quiere
B, es una tarea más de 20 líneas y se puede añadir sin rehacer nada.

**D-9 · `precio_venta` está informado en 3 de 8.959 filas.** Se publica igual,
porque Juan lo pidió y porque una columna vacía declarada como vacía informa;
una columna ausente, no. Alternativa si el humano prefiere: omitirla. La ficha
lo avisa en cualquier caso.
