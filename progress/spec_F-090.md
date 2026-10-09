<!-- progress/spec_F-090.md -->
# F-090 · Mediciones de la spec (spec-author, 2026-10-09)

Todo en SOLO LECTURA: Sigrid por `sigrid-api` (`POST /api/sql/read`, todas las
respuestas con `truncated: false`), una sola llamada a `documents/read` sin
guardar el fichero. Ninguna consulta al Postgres de Azure (no hizo falta).
Spec: `specs/F-090-documento-adjunto/`.

## 1 · `ruesma.dbo.gra` y `rcg` (base de negocio)

- `gra`: **289.036 filas** (285.735 el 2026-09-18), 29 columnas, **sin `tiemod`**.
  `cod` varchar(128), 289.035 distintos: **un `cod` repetido** en las empresas 1
  y 31. `vin <> 0` en 288.998. Binario en la propia base: 71 filas, 12,8 MB
  (`ima`); `pul` vacía; `tex` en 370 filas (máx. 1.025 bytes); `cam` vacía.
  `gratipide <> 0` en 60.982 (todas fuera de compras). `fec` AAAAMMDD,
  20081212 → 22501101 (fechas imposibles). 27 empresas, 201 logins.
- `rcg`: **289.451 filas**, 203.248 documentos, 289.035 gráficos; **0
  huérfanos** contra `gra` y contra `con`. `fecalt` vacía casi siempre
  (34 informadas en compras), `feclee` vacía. 102 gráficos cuelgan de varios
  documentos (máx. 33): la clave del enlace es `rcg.ide`.

Enlaces por familia (`con.tip`): 15 factura 133.738 · 44 contrato 38.111 ·
306 (nóminas) 28.481 · 12 oferta 22.056 · 20 asiento 17.408 · 43 empleado
15.917 · 708 (posventa) 14.302 · 5 proveedor 5.362 · 42 obra 5.139 · 46
comparativo 4.444 · 14 albarán 690 · resto < 1.600.
**Las cinco de compras (12, 14, 15, 44, 46): 199.042 enlaces**; fuera quedan
90.409, de ellos 44.398 de personal.

## 2 · `auxgra` (clases de gráfico): no sirve para compras

48 clases. Casi todas de RR. HH. («Nómina», «DNI», «EMBARGOS», «JUZGADO
FAMILIA», «CV» con nombre propio), seis de posventa y siete generales de obra.
**`gratipide = 0` en el 100 % de los 199.042 enlaces de compras**: el «tipo»
que pide Juan sale de la extensión del fichero.

## 3 · Cobertura (documentos con ≥ 1 adjunto / documentos), por año de `con.fec`

| Familia | Total | Detalle |
|---|---|---|
| Factura (15) | 104.952 / 167.169 = **62,8 %** | ≤2016: 4/40.121; 2017 491/7.921; 2018 1.545/12.072; **desde 2019 102.912/107.055 = 96,1 %** (93-99 % cada año) |
| Contrato (44) | 17.666 / 19.110 = **92,4 %** | 86-98 % todos los años |
| Oferta (12) | 18.383 / 73.116 = **25,1 %** | 21-29 % cada año |
| Comparativo (46) | 2.931 / 20.436 = **14,3 %** | desde 2022: 2.271/10.612 = **21,4 %** |
| Albarán (14) | 606 / ~313.600 = **0,2 %** | práctica no implantada |

Ficheros por clase en compras: facturas 99,5 % PDF; contratos 53 % PDF y 47 %
Word; comparativos 72 % PDF y **25 % Excel (1.122)**; ofertas 91 % PDF y 5,5 %
Excel (1.224).

**El concurso en Excel (punto 4a de Juan)**: 1.053 comparativos con Excel en el
propio comparativo (925 desde 2022) y 1.130 ofertas con Excel (685 desde 2022).
Uniendo oferta → comparativo por `comprv` (`docide` único, 0 repetidos):
**1.980 comparativos de 20.436 (9,7 %) tienen un Excel**, 1.055 en el
comparativo y 1.024 en alguna oferta.

## 4 · `ruesma_rep.dbo.gra` (base documental) y `documents/read`

- `sql/read` SÍ admite `ruesma_rep` (está en `ALLOWED_DATABASES`), y también el
  nombre de tres partes desde `ruesma`.
- **364.906 filas, todas con binario, `cod` único** (364.906 distintos).
  **169.001 MB (~165 GB)**, media 474 KB, máximo 157 MB.
- **Casa con `ruesma.gra` por `(emp, cod)`: 288.327 de 289.038 (99,75 %)**; 711
  sin binario. El `ide` coincide solo en 426 (lo que ya avisa
  `azure-apps/sigrid_api.md` §2.2: nunca unir por `ide`).
- **El nombre**: en 31.833 casadas difiere; en **31.720 el documental lo tiene
  VACÍO** (11 %). `Content-Disposition` saldría sin nombre: el bueno es el de
  negocio (`gra.nom`).
- Compras (enlaces / sin binario / MB / media KB / máx. MB): oferta 22.056 /
  89 / 8.666 / 403 / 24 · albarán 690 / 0 / 122 / 181 / 2 · factura 133.740 /
  127 / 54.636 / 418 / 32 · contrato 38.111 / 220 / 17.435 / 471 / 47 ·
  comparativo 4.444 / 25 / 1.837 / 425 / 45. **Total ~82.700 MB (~81 GB); 461
  enlaces sin binario (0,23 %)**.
- **Prueba única de `documents/read`** (la factura con adjunto más reciente):
  `{database: ruesma_rep, table: gra, id_column: cod, id_value: <cod>,
  blob_column: ima, filename_columns: [nom], disposition: inline}` → **200,
  `application/pdf`, `inline` con `filename`, 145.984 bytes = `DATALENGTH`,
  firma `%PDF-`**. No se guardó nada en disco.

## 5 · Datos personales

- `gra.cod` = sello temporal + **login** de quien subió el fichero en 198.627 de
  199.042 (99,8 %); `gra.usu` es ese login (sufijo = `usu` en 198.600). El login
  ya se publica en `compras.documento_procesos` (F-085, D4, con nombre).
- `gra.nom` en compras: nombres de proveedor y número de factura. Patrón de NIF
  en 584 nombres (550 en facturas, la mayoría números de factura) y «dni» o
  «nómina» en 20 nombres de facturas. El proveedor y su CIF ya se publican.
- Lo realmente personal (nóminas, DNI, embargos, CV de empleados) está en las
  familias 43 y 306: el filtro en origen (D2) lo deja fuera.

## 6 · Coste de ingesta (medido desde el puesto, 10.000 filas por página)

`rcg` filtrada: 199.042 filas, 20 páginas, **7,2 s**, 7,9 MB de JSON. `gra`
filtrada sin `ima/pul/tex/cam`: 199.042 filas, 20 páginas, **41,5 s**, 38,3 MB.
Estimación con escritura: **1-2 min** por noche. Referencia: nocturna del
09-10 **4 h 39 min**; `ingest_raw.rac` (2,5 M filas) 132 s. Disco: ~100 MB
entre `raw` y `compras`.

## 7 · Acceptance reescrito en `harness/features.json` (D7, pendiente del humano)

Cambios sobre el anterior: (1) objeto propio decidido, con las cinco familias;
(2) ingesta FILTRADA en origen y sin `auxgra`; (3) cobertura de las cinco
familias con las cifras de hoy; (4) **fuera** el criterio de «el identificador
no es una ruta abrible mientras Sistemas no dé la raíz»: era falso, el binario
está en `ruesma_rep` y lo sirve `sigrid-api`; en su lugar, la ficha declara
dónde está y que el datamart no lo replica; (5) el criterio de comparativos y
ofertas se concreta (Excel en el comparativo o en sus ofertas); (6) la ventana
ya no tiene «19 min de margen»: va 39 min por encima. La descripción de la
ficha se corrige en el párrafo del binario.
