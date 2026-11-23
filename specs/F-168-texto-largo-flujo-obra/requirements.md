<!-- specs/F-168-texto-largo-flujo-obra/requirements.md -->
# F-168 · Requisitos · El texto largo de la partida y de cada línea del flujo de obra

Pedida por Juan Romero (Control de Costes) el 2026-11-23 y ampliada por el humano el mismo día. Las
cifras son las medidas por el spec-author (solo lectura) en `progress/spec_F-168.md` (M1-M10). Los
requisitos asumen las opciones recomendadas de las decisiones D1-D8 de `design.md`; si el humano
decide otra cosa, la spec se reescribe antes de implementar.

Glosario. **Texto largo**: el `tex` (tipo `text`, plano, 0 RTF) de la partida (`obrparpar`) o de una
línea del flujo: planificación de compras (`dncpro`, tipo NECESIDAD), oferta (`dcopro`, OFERTA),
contrato (`ctrpro`, CONTRATO), albarán (`dcapro`, ALBARAN) y factura (`dcfpro`, FACTURA). **TOPE**:
16.000 caracteres (D4). **Texto limpio**: el resultado de `stg.fn_texto_largo` (R5).

## Ingesta

R1. El sistema debe ingerir `tex` en `raw` para `obrparpar`, `dncpro`, `dcopro`, `ctrpro`, `dcapro` y
`dcfpro`, y cada una debe declarar en `config/tables_sigrid.yaml` `recortar_columnas: {tex: 16000}`.
(capa: unit)

R2. El sistema debe seguir excluyendo `tex` en las cabeceras (`dco`, `ctr`, `dca`, `dcf`, `com`,
`obrctr`) y `obs`, `desesp`, `texcom`, las direcciones y los demás textos de las tablas que hoy los
excluyen; solo cambian las seis de R1. (capa: unit)

R3. CUANDO una tabla declara `recortar_columnas`, el sistema debe pedir esa columna a Sigrid como
`CAST(REPLACE(SUBSTRING(CAST([col] AS VARCHAR(MAX)), 1, N) COLLATE Latin1_General_BIN, CHAR(0), '') AS
VARCHAR(MAX)) AS [col]` y el resto de columnas como hoy. (capa: unit)

R4. SI `recortar_columnas` nombra una columna excluida, ausente en Sigrid o fuera de
`include_columns`, o un tope no entero positivo, ENTONCES la tabla debe fallar antes de crear nada en
`raw`, con el nombre de la tabla y de la columna en el error. (capa: unit)

## Limpieza e identidad del texto

R5. El sistema debe tener UNA limpieza, `stg.fn_texto_largo(TEXT)`, con su espejo Python
`domain/texto_largo.limpiar`: cambia `\r\n` y `\r` por `\n`, quita los caracteres de control salvo
`\t` y `\n`, recorta los espacios y saltos de los extremos, corta a TOPE caracteres y devuelve NULL si
queda vacío. (capa: unit)

R6. El sistema debe identificar cada texto por `texto_id = md5(texto limpio)::uuid`
(`stg.fn_texto_id`, espejo `domain/texto_largo.texto_id`), igual en `stg`, `compras` y
`descompuestos`: mismo `texto_id`, mismo texto. (capa: unit)

R7. Los literales de TOPE, del patrón de control y del algoritmo deben estar UNA vez en
`domain/texto_largo.py`; un test debe comprobar que el SQL y el YAML usan esos mismos. (capa: unit)

R8. El sistema debe marcar `recortado` cuando el texto de `raw` mide TOPE caracteres o más.
(capa: integración)

## La partida

R9. El sistema debe publicar `stg.partida_texto`, una fila por partida de `raw.obrparpar` con texto
limpio no nulo, con `partida_id` (clave primaria), `obra_id`, `codigo_partida`, `descripcion_corta`,
`texto`, `texto_id`, `bytes` y `recortado`. (capa: integración)

R10. El sistema debe publicar el texto de la partida sin filtrar por ámbito, fase ni tipo: una
partida que solo tiene presupuesto de venta (7), de master (8 u 11) o de fase 0 sale igual que una de
coste (3), y un capítulo con texto también sale. (capa: integración)

R11. La partida 419079 (04.02 «FORJ. RETICULAR 35+10» de la 0726) debe salir con su texto completo.
(capa: integración; verificación MANUAL en Azure, tasks T14)

## Las líneas del flujo (compras)

R12. El sistema debe publicar `compras.linea_texto`, una fila por línea con texto limpio no nulo de
las cinco fuentes, con `tipo_linea` (NECESIDAD, OFERTA, CONTRATO, ALBARAN, FACTURA), `linea_id` (el
`ide` de su tabla), `documento_id`, `obra_id`, `partida_id`, `linea_necesidad_id`, `texto_id`,
`igual_a_partida` e `igual_a_necesidad`; clave primaria `(tipo_linea, linea_id)`. (capa: integración)

R13. El sistema debe tomar `partida_id` de `paride` y `linea_necesidad_id` de `dncproide` (en
NECESIDAD, NULL), con 0 como NULL, y `documento_id` de `dncide` (NECESIDAD) o `docide` (el resto).
(capa: integración)

R14. `igual_a_partida` debe ser verdadero si el `texto_id` de la línea es el de su partida en
`stg.partida_texto`, falso si los dos existen y difieren, y NULL si la línea no tiene partida o la
partida no tiene texto. `igual_a_necesidad`, lo mismo contra la línea de planificación; NULL siempre
en NECESIDAD. (capa: integración)

R15. El sistema debe publicar `compras.textos`, una fila por `texto_id` que use alguna fila de
`compras.linea_texto`, con `texto`, `bytes` y `recortado`, y ninguno que no use. (capa: integración)

R16. El sistema debe publicar la vista `compras.v_linea_texto`: las filas de `compras.linea_texto`
con su `texto`, sin perder ni repetir ninguna. (capa: integración)

R17. CUANDO se pide el texto de una línea de comparativo, el sistema debe darlo por
`compras.comparativo_lineas.linea_necesidad_id` (tipo NECESIDAD) y por la línea de
`compras.comparativo_oferta_lineas` (tipo OFERTA) sin más tablas intermedias. (capa: integración)

R18. El sistema debe publicar en `compras.documento_texto` y `compras.documento_comentarios` también
el memo de los comparativos (`con.tip` 46) y de las ofertas (12), con la misma regla de partir que
facturas y contratos. (capa: integración)

## Los descompuestos

R19. `descompuestos.fn_trocear` y su espejo `trocear_des` deben devolver el campo 9 del registro
(`texto_largo`), y `POSICIONES` debe incluirlo. (capa: unit)

R20. El sistema debe rellenar `descompuestos.lineas.texto_id` en todos los orígenes: ESTUDIO y
MASTER_* con el campo 9 limpio; PLANIF_JO con el `dncpro.tex` limpio de su línea, que es el mismo
`texto_id` que su fila NECESIDAD de `compras.linea_texto`. (capa: integración)

R21. El sistema debe guardar cada texto en `descompuestos.textos` (`texto_id` clave primaria) en el
mismo lote que sus líneas, sin repetirlo; toda `lineas.texto_id` no nula debe tener su texto.
(capa: integración)

R22. CUANDO cambia el texto de `stg/11_texto_largo.sql`, el sello de `build_descompuestos` debe
cambiar. (capa: unit)

## Robustez, datos personales y documentación

R23. SI falla la construcción de un fichero nuevo, ENTONCES deben seguir publicadas las tablas de la
noche anterior: cada fichero nuevo es una sola transacción. (capa: integración)

R24. El sistema debe publicar el texto sin máscara, en `stg`, `compras` y `descompuestos` (D6), y
ningún esquema restringido debe cambiar. (capa: unit)

R25. Cada objeto y columna nuevos deben tener ficha en `config/diccionario/` (la de
`stg.partidas.descripcion_corta` y las de las líneas de compras apuntan al texto largo), con la
versión del diccionario subida, sin pasarse de `PRESUPUESTO_MAX`. (capa: unit)

R26. `azure-apps/datamart_seg_anual.md` debe decir qué texto se ingiere y dónde se publica.
(verificación del reviewer)

R27. Tras el despliegue, la ingesta y la base deben quedar dentro de lo estimado en M10 (+10 min de
ingesta, +2 GB de base como máximo) y los recuentos deben casar con los de Sigrid. (MANUAL, T14-T16)
