<!-- specs/F-090-documento-adjunto/requirements.md -->
# F-090 · El índice de documentos adjuntos (facturas, contratos, comparativos, ofertas y albaranes)

Mediciones (todas en solo lectura, 2026-10-09): `progress/spec_F-090.md`.
Decisiones abiertas para el humano: D1-D7 al final de este fichero.

## Corrección de la ficha (lo que cambia respecto a la exploración del 2026-09-18)

La ficha decía que «el binario NO está en la base» y que faltaba «la raíz del
repositorio» que hay que pedir a Sistemas. **No es así**: el binario está en la
base DOCUMENTAL `ruesma_rep`, en su propia `dbo.gra`, y se casa con
`ruesma.dbo.gra` por `(emp, cod)` en el **99,75 %** (288.327 de 289.038). Lo
sirve `sigrid-api` con `POST /api/documents/read` (`id_column: "cod"`); probado
con una factura: 200, `application/pdf`, los bytes exactos. No hay raíz que
pedir ni gestión pendiente con Sistemas. El datamart publica el ÍNDICE; el
binario NO se replica (81 GB solo en compras, más que el disco de 64 GB).

## Ingesta

- R1. El sistema debe declarar `rcg` en `config/tables_sigrid.yaml` filtrada en
  origen a los enlaces cuyo documento (`con.tip`) es de una familia de
  `FAMILIAS_ADJUNTOS`, sin `incremental_column` (no tiene `tiemod`).
- R2. El sistema debe declarar `gra` filtrada en origen a los gráficos enlazados
  por `rcg` con un documento de esas familias, y EXCLUYENDO `ima`, `pul`
  (binario) y `tex`, `cam` (texto ilimitado).
- R3. Los dos filtros deben llevar exactamente las familias de
  `FAMILIAS_ADJUNTOS` (12, 14, 15, 44, 46), ni una más ni una menos.
- R4. SI alguna de `ima`, `pul`, `tex`, `cam` deja de estar en
  `exclude_columns` de `gra`, ENTONCES un test debe fallar nombrándola.
- R5. El sistema NO debe ingerir `auxgra` ni adjuntos de otras familias
  (personal: nóminas, DNI, embargos; posventa): un test lo vigila.
- R6. El censo de `tables_sigrid.yaml` debe pasar de 72 a **74** tablas, y los
  tests que fijan el 72 (F-085, F-095) se actualizan a 74.

## Dominio (`etl_sigrid/domain/documento_adjuntos.py`)

- R7. El sistema debe declarar `FAMILIAS_ADJUNTOS` = {15 FACTURA, 44 CONTRATO,
  46 COMPARATIVO, 12 OFERTA, 14 ALBARAN} como única fuente de las familias.
- R8. `extension(nombre)` debe devolver el sufijo tras el ÚLTIMO punto, en
  minúsculas y sin espacios; SI el nombre es nulo, vacío o no tiene punto (o
  acaba en punto), ENTONCES debe devolver `None`.
- R9. `clase_fichero(nombre)` debe devolver `PDF` (pdf), `EXCEL` (xls, xlsx,
  xlsm, xlsb, csv), `WORD` (doc, docx, rtf, odt), `CORREO` (msg, eml), `IMAGEN`
  (jpg, jpeg, png, tif, tiff, gif, bmp), `OTRO` (otra extensión) y
  `SIN_EXTENSION` (cuando `extension` es `None`).
- R10. Las extensiones de cada clase deben vivir en un único dict del dominio,
  sin una extensión repetida en dos clases.

## SQL (`compras.documento_adjuntos`)

- R11. `build_compras` debe construir `compras.documento_adjuntos` con UNA fila
  por enlace de `raw.rcg` (clave `adjunto_id` = `rcg.ide`), solo para
  documentos de `raw.con` de las familias y gráficos presentes en `raw.gra`
  (JOIN, no LEFT JOIN).
- R12. Cada fila debe publicar: `adjunto_id`, `documento_id` (`rcg.con`),
  `tipo_documento_codigo` (`con.tip`), `familia` (nombre de R7),
  `codigo_documento` (`con.cod`), `comparativo_id` (R13), `grafico_id`
  (`gra.ide`), `cod_repositorio` (`gra.cod`), `empresa_repositorio`
  (`gra.emp`), `nombre_fichero` (`gra.nom`), `extension` y `clase_fichero`
  (R8-R9 sobre `gra.nom`), `descripcion` (`gra.res`, NULL si vacía),
  `fecha_alta` (`compras.fn_sigrid_date(gra.fec)`), `subido_por` (`gra.usu`,
  sujeto a D3) y `posicion` (`rcg.pos`).
- R13. `comparativo_id` debe ser el propio documento en un COMPARATIVO, el
  `comprv.comide` de la oferta en una OFERTA (`comprv.docide` = documento) y
  NULL en el resto.
- R14. Los literales del SQL (familias del `IN` y del `CASE`, extensiones de
  cada clase) deben ser los del dominio: un test compara el texto.
- R15. SI más del 1 % de los enlaces de `raw.rcg` de las familias no encuentra
  su gráfico en `raw.gra` (ingesta a medias), ENTONCES el sub-paso debe fallar
  con `RAISE EXCEPTION` que nombre F-090 y la cifra.
- R16. El sub-paso `documento_adjuntos` debe ir en `SUB_PASOS` de
  `build_compras_step.py` detrás de `estado_documentos`, contando
  `compras.documento_adjuntos`.
- R17. El sistema NO debe modificar `compras.facturas` ni ningún otro objeto
  existente de `compras` (D6): un test comprueba que `01_documentos.sql` no
  nombra `raw.gra` ni `raw.rcg`.
- R18. El SQL debe ser idempotente (`DROP TABLE IF EXISTS ... CASCADE` +
  `CREATE TABLE ... AS`), crear índices por `documento_id` y por
  `comparativo_id`, y no leer nada de `ruesma_rep` ni de binarios.

## Diccionario y documentación

- R19. `config/diccionario/compras.yaml` debe tener la ficha de
  `documento_adjuntos` con grano, clave, todas sus columnas y la COBERTURA
  MEDIDA por familia: facturas 62,8 % en total, **96,1 % desde 2019** y cero
  antes de 2017; contratos 92,4 %; ofertas 25,1 %; comparativos 14,3 % (21,4 %
  desde 2022); albaranes 0,2 %.
- R20. La ficha debe declarar que la AUSENCIA de fila es «Sigrid no tiene
  adjunto para ese documento» (no un fallo del ETL), con la salvedad de la
  cobertura histórica de R19.
- R21. La ficha debe declarar dónde está el binario (`ruesma_rep`, no el
  datamart), que `cod_repositorio` es la clave con la que `sigrid-api` lo sirve
  (`documents/read`, `id_column` `cod`), que el 0,23 % de los enlaces de compras
  no tiene binario en la base documental y que el 11 % de las filas documentales
  tiene el nombre vacío (el nombre bueno es `nombre_fichero`).
- R22. La ficha debe declarar que la clase de fichero sale de la EXTENSIÓN y no
  de la clase de gráfico de Sigrid (`gratipide` = 0 en el 100 % de los enlaces
  de compras), y que la fecha de alta trae 2 valores imposibles (año 2250).
- R23. La ficha debe declarar el dato personal: `subido_por` y el sufijo de
  `cod_repositorio` son el LOGIN de quien subió el fichero (99,8 %).
- R24. `raw.yaml` debe tener fichas de `gra` y `rcg` (filtro, columnas excluidas
  y motivo) y decir «Son 74 tablas»; `00_global.yaml` sube a `version: 47` y
  dice «las 74 tablas»; `pendientes` sigue `[]`.
- R25. `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` deben decir
  «74 tablas», nombrar `gra`, `rcg` y `compras.documento_adjuntos`, y que abrir
  el fichero es cosa de `sigrid-api` (`documents/read`), no de este ETL.

## Verificación en Azure (MANUAL, humano o líder tras el despliegue)

- R26. CUANDO se construye `compras` en Azure, `check-raw-recuentos` debe dar OK
  en `gra` y `rcg`, y `compras.documento_adjuntos` debe tener ~199.000 filas.
- R27. CUANDO se pregunta al MCP, debe responder: (a) los adjuntos de una
  factura dada; (b) cuántas facturas de un periodo no tienen adjunto; (c) qué
  comparativos de la obra 0720 tienen un Excel adjunto, en el comparativo o en
  alguna de sus ofertas.
- R28. CUANDO corre la primera nocturna con F-090, el coste añadido
  (`ingest_raw.gra` + `ingest_raw.rcg` + el sub-paso) debe quedar medido en
  `progress/` contra la ventana (hoy 4 h 39 min, 39 min sobre las 4 h).
- R29. CUANDO se pide a `sigrid-api` `documents/read` con el `cod_repositorio`
  de una fila publicada, debe devolver 200 y el fichero (una sola prueba, sin
  guardar el fichero).

## Fuera de alcance (y a qué proyecto iría)

- Abrir el fichero desde el MCP: herramienta nueva en **`mcp-bbdd`** que llame a
  `documents/read`. Desde un portal: **`portal`**. Ninguno se diseña aquí.
- Que `documents/read` ponga el nombre de negocio cuando el documental lo tiene
  vacío (31.720 filas): **`sigrid-api`**.
- Leer el CONTENIDO de los PDF y contrastarlo con lo registrado: feature futura.
- Replicar binarios en el Postgres compartido: descartado (81 GB, disco 64 GB).

## Decisiones abiertas para el humano (recomendación entre corchetes)

- D1. Familias: [las cinco, 199.042 enlaces]; mínimo pedido: 15, 46 y 12 (160.242).
- D2. Filtrar en origen [sí: fuera nóminas, DNI y embargos de `raw`] o traerlas
  enteras (289.451) y revocarlas al MCP con `PG_EXCLUDED_TABLES`.
- D3. Publicar `subido_por` (login) [sí, sin nombre: el login ya va dentro de
  `cod_repositorio` y F-085 publica login y nombre de quien aprueba].
- D4. No ingerir `auxgra` [no: compras no usa clases y su catálogo es de RR. HH.].
- D5. Marcar si hay binario consultando `ruesma_rep` cada noche [no: 0,23 %,
  se declara en la ficha; obligaría a un segundo cliente contra otra base].
- D6. Objeto propio y `compras.facturas` intacta [sí: F-132 trabaja en
  `compras`, y `facturas` la consumen Power BI y el MCP].
- D7. Aceptar el `acceptance` reescrito de `harness/features.json` (detalle en
  `progress/spec_F-090.md` § 7).
