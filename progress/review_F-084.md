<!-- progress/review_F-084.md -->
Revisión completa (pasada 1), desde `367af44` (merge-base con `main`) hasta `1bef0d2`. Los
cuatro commits del líder de la rama —`b7e1b20`, `e4b3f08`, `80429e1`, `faea29e`— quedan
**fuera del juicio** (solo tocan `history.md`, `features.json`, `BACKLOG.md` y un `explore_*`) pero se cuentan al medir alcances.

# F-084 · El estado del CONTRATO · review

**Veredicto: APROBADO**, con el criterio 4 partido: su mitad de ficha está cumplida y
verificada; su mitad de «se responde por el MCP» queda **pendiente del humano**, porque
exige construir en la base. Igual que se cerró F-083.

**Nivel de rigor: `estandar`**, declarado en `harness/features.json` (no por omisión):
fase RED, cobertura ≥ 80 % y campaña de mutación. `sdd=false`: la spec son los **siete
criterios `acceptance`**, y lo que dependa de `tasks.md` es N/A por la nota de cabecera de
`CHECKPOINTS.md`.

## Verificado por mí, no leído del informe

`bash harness/init.sh` **tal cual**, exit 0: **4.938 pasan, 188 saltados** en 396,8 s;
`PUERTA COBERTURA [OK] 94,3 % de 955 líneas (901/955, umbral 80 %)`; `PUERTA TAMAÑO [OK]
impl 217/220`. Los avisos (`blocked` F-052, 228 de ruff) son deuda previa.

**Criterio 1 · ¿de verdad no se puede escribir la unión mal?** Copié los dos SQL y
`tests/test_f084_sql.py` al scratchpad y rompí la pareja **nueve veces**: las nueve salen
en **ROJO**. (M1) el `WHERE` pierde el tipo y (M3) la firma pierde el tipo → cae
`c1_la_union_es_por_la_pareja`; (M2) vuelve el lateral escrito a mano unido solo por
`est` → caen 5, con `c6_el_catalogo_no_se_vuelve_a_leer_a_mano`; (M4) se borra
`proveedor_cif` y (M5) se renombra `nombre_obra` → `c2_ninguna_columna_desaparece` y el de
orden; (M6) `estado_id` intercalado 2.º → `c2_las_columnas_van_primero`; (M7) CONTRATOS
traduce con `15` → `c1_la_traduccion_filtra_el_tipo` y `c6_los_dos_bloques`; (M8) sin `ORDER BY` → `c2_no_puede_multiplicar_filas`; (M9)
`STABLE` → `IMMUTABLE` → `c1_la_funcion_lee_el_catalogo`.

**Matiz, porque el informe se pasa de rotundo.** La firma solo hace imposible **omitir**
el argumento (M3: falla PostgreSQL). Las dos formas que **sí compilarían** —recopiar el
lateral uniendo solo por `est` (M2) y pasar el tipo equivocado (M7)— las caza el TEXTO,
no la base: que nadie retire esos dos tests creyendo lo contrario.

**Criterio 2 · medido contra la tabla VIVA, en `READ ONLY`.** Extraje el `SELECT` nuevo
del fichero, inliné el cuerpo literal de la función (que aún no existe en la base) y lo
comparé con `compras.contratos` en una consulta agregada: `filas_nuevo 18.978 ·
ids_distintos 18.978 · filas_vivas 18.978 · union_de_ids 18.978` (FULL JOIN: los dos
conjuntos son el MISMO) · `doce_que_no_casan 0 · sin_literal 0 · sin_codigo 0`. **El
grano no cambia, el lateral no multiplica y las doce columnas devuelven el mismo valor
contrato a contrato**: la prueba del implementer mide lo que dice medir y su cifra se
reproduce exacta. Por el MCP confirmé que la tabla publica hoy **18.978 filas y
exactamente esas doce columnas, en el orden** que fija `COLUMNAS_DE_SIEMPRE`.

**Criterio 3 · recontado por mí** con la misma consulta: 7 FIR 13.459 · 8 TER 3.179 ·
**3 EPF 818** · 1 PFP 564 · 5 RFP 550 · 6 COMD 232 · 9 RES 176. Suman 18.978 y
**coinciden uno a uno** con la ficha. Por el MCP verifiqué el catálogo del tipo 44 en
`maestro.estados_documento`: los siete pares, los mnemónicos y los literales, **con la
tilde de «Comprobada documentación»** que el test fija (y `tests/_texto.normalizado` no borra tildes: la pinta de verdad).

**Fase RED · reproducida.** `git archive 1b3ac05` al scratchpad —el árbol del commit RED,
sin `fn_estado_documento` y con el diccionario en `version: 23`— y pytest allí: **31 failed, 26 passed**, exactamente los números del informe. Los dos retoques posteriores a
los tests **no aflojan**: T3 cambia `_sin_comentarios` por `_compacto` (insensibilidad al
alineado) y T4 **aprieta** poniendo la tilde correcta.

**Mutación · el cero es legítimo, y queda declarado.** `alcance_de_feature('F-084',
base='main')` devuelve `lineas={}`; `git diff --name-only main...HEAD | grep '\.py$' |
grep -v '^tests/'` sale **vacío**; el motor imprime «ALCANCE VACÍO … No se escribe
informe» y **no hay** `progress/mutacion_F-084.md`, que es lo correcto. **Prueba de
control (ENCARGO 1.7.11)**: `generar_mutantes` sobre los `.py` del diff **ignorando la
exclusión de alcance** da **136 mutantes**, y 41 sobre `harness/alcance.py`. El generador
funciona, así que el cero es **exclusión por diseño** —el diff es SQL, YAML, Markdown y tests—, no un generador roto ni un informe inventado.
RM1–RM6 y las puertas de tiempo y coste por mutante: **N/A por alcance vacío**,
justificado aquí; en su lugar valen las nueve mutaciones de texto de arriba. Y **el
94,3 % de cobertura no habla de F-084** —son las 955 líneas del diff contra `dev`, que
arrastra F-073/F-078/F-080/F-081—, cosa que el implementer dice en vez de apropiarse.

## Checkpoints

- **C1** [x] exit 0; los siete documentos existen.
- **C2** [x] una sola `in_progress`; rama correcta; `current.md` describe la sesión activa; `history.md` al día.
- **C3** [x] SQL en su capa y numerado; primera línea con ruta en los cuatro ficheros; sin prints ni TODO real (los dos «TODO» son prosa: «TODO LO QUE AÑADE F-084»); sin dependencias nuevas. Semántica Sigrid respetada: el estado se lee de **`con.est`**, la superclase, y se traduce por la pareja, que es la trampa polimórfica de `R-SIGRID-CON`.
- **C3 bis** N/A **justificado**: no toca `docs/referencia/`. Aun así barrí el diff entero (password/secret/api_key/token/connstring/GUID/IP): **cero coincidencias**.
- **C4** [x] los siete criterios trazados (tabla abajo); ningún test toca red ni BBDD (leen texto del árbol); las MANUAL están en `current.md` con su comando. Sin dobles nuevos.
- **C4 bis** [x] rigor declarado; RED reproducida; cobertura `[OK]`; alcance vacío verificado más prueba de control; «Evidencias» con sus cuatro números.
- **C4 ter** N/A: el repositorio **no declara** `harness/rutas_sensibles.json` (solo el `.ejemplo.json`).
- **C5** [x] `tasks.md` N/A por `sdd=false`; commits `F-084 T2..T5` (T1 fue medición en solo lectura y no produjo fichero: legítimo y declarado); árbol limpio antes y después de mi verificación; `features.json` sigue `in_progress`, correcto hasta que cierre el líder.

## Trazabilidad criterio → test

| # | Criterio | Cubierto por |
|---|---|---|
| 1 | estado por la pareja (44) | `test_f084_c1_*` (6) + `test_f083_la_union_es_por_la_pareja` |
| 2 | grano y doce columnas | `test_f084_c2_*` (8) + mi medición en `READ ONLY` |
| 3 | reparto medido | `test_f084_c3_*` (8) + mi recuento independiente |
| 4 | antigüedad / `con.tiemod` | `test_f084_c4_*` (3) · **el MCP: MANUAL (humano)** |
| 5 | cero firmas sobre 70.346 | `test_f084_c5_*` (2: ficha y cabecera del SQL) |
| 6 | factorizar, no duplicar | `test_f084_c6_*` (3) |
| 7 | init.sh en verde | ejecutado: exit 0 |

## Las decisiones de diseño

**Criterio 6 · acertada.** La función va al sitio correcto (`SUB_PASOS` ejecuta
`00_setup` antes de `01_documentos`: existe cuando se usa), es `STABLE` y no `IMMUTABLE`,
y la guarda `ORDER BY ide LIMIT 1` protege ahora a las **dos** tablas. **F-083 no se
rompe**: su proyección no cambia ni una letra —la función devuelve `codigo_estado` y
`nombre_estado`, los mismos alias— y los cuatro tests ajenos cambian **dónde miran, no lo
que exigen**: siguen pidiendo la pareja, el `ORDER BY`, el `LIMIT 1` y el `LEFT ... ON
TRUE`, y **añaden** que la factura llame con su `15`. Revisado línea a línea y confirmado
con M1/M7/M8.

**Criterios 4 y 5 · acertada, y es la parte valiosa.** No publicar columna de antigüedad
cumple el criterio 4 tal como está escrito: la ficha **nombra `con.tiemod`**, dice con
esas palabras que **no es la fecha del cambio de estado**, añade que **ni está publicado**
(vive en `raw`, que el MCP no ve) y remite a **F-067**. Publicar el proxy invitaba al
«lleva X días enviado» que el criterio quiere impedir. Y los `ejemplos_preguntas` traen la
pregunta trampa con su OJO, que es como el MCP llega a la tabla sin explicárselo.

## Pendiente del humano

Nadie ha escrito en la base y **eso es correcto**. Queda `build-compras` (única validación
real del **cuerpo** de la función y del grano en la base), `status` y
`publicar-diccionario` si procede; luego, por el MCP y sin explicarle nada: «qué contratos
están enviados y sin firmar» debe dar **818**, y «cuántos llevan más de tres semanas
enviados» debe responder **que no se puede saber**.

## Recomendaciones (no bloquean)

1. **`current.md` sostiene una frase falsa que F-084 dejó en pie**: «Lo publicado en
   `_meta` es la **versión 18** … publicar contra Azure es una escritura y la autoriza el
   humano». La base viva dice **versión 21, publicada 2026-09-16 03:31 UTC, 150 objetos**:
   desde F-047 `publicar_diccionario` es un paso de `run-all` y **la nocturna publica
   sola**; F-084 editó la línea de al lado (22 → 24) y no esta.
2. **Confirmado el verde falso que anota el implementer.** En `main` la única aparición de
   «153» en `design_detalle.md` era `infra/README.md:153-170`:
   `test_f006_r24_el_diseno_declara_el_recuento_real_de_objetos` hace `str(total) in
   texto` sobre el fichero entero, así que **acertaba por casualidad**; su gemelo
   `test_f006_los_recuentos_de_current_son_los_de_hoy` tiene el mismo defecto. Propongo
   exigir el número **en su contexto** (línea tipo `Inventario a **N** objetos`).
3. **Duplicación residual**: `compras/05_vencimientos.sql:75` une `raw.conest` a mano para
   `tip = 25` —con la pareja, pero **sin guarda `LIMIT 1`**—. Es de F-080 (R21) y F-084
   hizo bien en no tocarlo; candidato a migrar a la función en la ficha de F-080.
4. **Aviso para el arnés**: medir con `build_postgres_client` dispara `_auto_bootstrap`,
   que emite `CREATE SCHEMA IF NOT EXISTS` y `CREATE TABLE IF NOT EXISTS _meta.etl_runs`
   **antes** de la transacción `READ ONLY`: idempotente y sin escribir nada, pero «solo
   lecturas» con este cliente no es literal. Me pasó a mí y al implementer.
