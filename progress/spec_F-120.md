<!-- progress/spec_F-120.md -->
# F-120 · Resumen de la spec, mediciones y decisiones abiertas

Fecha: 2026-10-01 · spec-author · rama `feature/F-120-factor-descompuesto`.
Spec: `specs/F-120-factor-descompuesto/`. Todo lo medido es **solo lectura**:
Postgres del `.env` (Azure, `sigrid_dm`) en transacciones `READ ONLY` con
`statement_timeout`, sobre el estado que dejó la nocturna del 2026-10-01
(`build_descompuestos` 07:31-07:42 UTC, sello `99f827a11969d59f`). El master se
recorrió en 27 trozos de 39-100 MB de obras **después** de terminar la nocturna
(10:33-10:50, 6-58 s por trozo). Ni un build, ni una escritura, ni una lectura de
Sigrid: no hizo falta. Dos consultas se cortaron por `statement_timeout` (un
recuento sobre `lineas` entera y una muestra de dos obras a la vez); se
repitieron más acotadas (por origen, por una versión), no igual.

## 0 · En una frase

El campo 14 es «factor x rendimiento» (orden comprobado contra `dncpro`, 0 casos
al revés) y con esa regla la 400854 v6 cuadra al céntimo. Se arreglan **~91.000
partidas-versión del master** que hoy salen NO_CUADRA. Dos sorpresas: **PLANIF_JO
tiene el mismo defecto por otra vía** (`dncpro.faccan` no se aplicaba; 6.920
partidas) y entra en la feature (D5); y **al menos 95.000 de las ~461.000 líneas
que contó el líder no son de factor** sino de campo 14 vacío (D10, fuera).

## 1 · Recuento del líder, reproducido

Su definición es `rendimiento IS NULL AND precio <> 0 AND cantidad_total <> 0`
en `descompuestos.lineas`: MASTER_PLANIF_JO **307.031** (igual), MASTER_PRE_ABC
153.981 (él 153.958), MASTER_INICIAL 273 (240), ESTUDIO 63 (32); la diferencia
es la nocturna de hoy. De ellas, con forma factor y precio y cantidad informados
hay como mucho 239.206, 126.845, 250 y 56: **al menos ~68.000, ~27.000, 23 y 7
tienen el campo 14 VACÍO** (D10).

## 2 · (a) Las formas del campo 14

4.520.416 registros `~D|` (todos los registros son `~D|`): ámbito 3 entero y las
3.025 versiones del master. Forma = el texto con cada racha de dígitos como `9`.

| Forma | Ámbito 3 | MASTER_INICIAL | MASTER_PRE_ABC | MASTER_PLANIF_JO | Tratamiento |
|---|---:|---:|---:|---:|---|
| número | 99.880 | 92.693 | 1.171.457 | 1.325.275 | factor 1 (R1) |
| vacío | 19.605 | 14.093 | 467.100 | 857.299 | NULL (R4, D1) |
| `a x b` (b >= 0) | 1.760 | 237 | 146.754 | 295.967 | factor a (R2) |
| `a x -b` | 165 | 34 | 2.862 | 8.625 | factor a, rend. negativo (R2) |
| `-a x ...` (factor negativo) | 0 | 0 | 1.518 | 2.368 | factor negativo (R2, R3) |
| `a x` (rend. vacío) | 97 | 4 | 4.933 | 7.675 | factor a, rend. NULL (R3) |
| de ellas, factor 0 (`0x...`) | 126 | 18 | 13.249 | 54.083 | factor 0 (R9) |
| `9.CDMA9` (`0678.CDMA15`) | 0 | 0 | 0 | 10 | raro: NULL (D2) |
| `9xF9` (`1963589xF321886`) | 0 | 0 | 0 | 5 | raro: NULL (D2) |

(Factor 0 va dentro de las filas `a x ...`; se cuenta aparte porque nunca trae
precio y cantidad a la vez: 0 de 67.350 en el master, 0 de 126 en el ámbito 3.) **Ninguna** `X`
mayúscula, coma decimal, blanco interno, más de un factor ni blanco en los
extremos. Porcentajes (tipos 4 y 13) con factor: 88 líneas (32 + 33 + 23), todas
`0.99765x-0.15`..`1.002x-0.05` (descuentos con factor): D6. El raro `1963589xF...`
es la línea de `dncpro` con `factip = 646` (`faccan = 1963589`): basura de Sigrid.
`0678.CDMA15` es un código en el campo del rendimiento (un `|` desplazado, riesgo
ya conocido de F-097). Ejemplos extremos: `0.0000005x384.721`, `54.73x15993.859`,
`-69.91x7.5`.

## 3 · (b) El orden: factor x rendimiento

**La 0713 (obra 2645007), partida 400854, versión 6** (la de los correos), los 19
registros (precio, cantidad total, campo 14; campo 36 = `dncpro.ide`):

| # | pre | cant | campo 14 | importe | # | pre | cant | campo 14 | importe |
|---|---:|---:|---|---:|---|---:|---:|---|---:|
| 1 | 262.25 | | (vacío) | | 11 | 0.26 | 81545.965 | 74.71 | 19,42 |
| 2 | 34.2 | 1091.729 | 1.00021x1 | 34,21 | 12 | 16.96 | 491.175 | 1x0.45 | 7,63 |
| 3 | 2 | 1091.729 | 1.00021x1 | 2,00 | 13 | 339.39 | 3.995 | 1.22x0.003 | 1,24 |
| 4 | 44.1 | 189.589 | 0.99825x0.174 | 7,66 | 14 | 339.39 | 7.025 | 0.9194x0.007 | 2,18 |
| 5 | 28 | 66.341 | 1.013x0.06 | 1,70 | 15 | 2.3 | 545.75 | 0.5 | 1,15 |
| 6 | 28 | 66.341 | 1.013x0.06 | 1,70 | 16 | 0.1 | 4366.917 | 1.00021x4 | 0,40 |
| 7 | 119 | 480.26 | 0.44 | 52,36 | 17 | 0.65 | 6956.13 | 6.373 | 4,14 |
| 8 | 3 | 480.26 | 0.44 | 1,32 | 18 | 15.68 | 1200.65 | 1.1 | 17,25 |
| 9 | 3 | 480.26 | 0.44 | 1,32 | 19 | 23.5 | 1091.5 | 1 | 23,50 |
| 10 | 0.94 | 81545.965 | 74.71 | 70,23 | | | | **suma** | **249,41** |

Precio de la partida en la v6: **249,41**. Cuadra al céntimo redondeando línea a
línea. Las líneas con forma factor son **9** (8 con factor distinto de 1, 7
formas distintas): el «7 líneas» del `acceptance` cuenta formas (D9). La
cantidad del campo 4 ya lleva el factor: 1091,5 x 1,00021 x 1 = 1091,729.

**Contra `dncpro`** (lo que enseña la pestaña «Planificación compras», FACTOR =
`faccan`, Rdto = `canren`), por el enlace del campo 36: en la 0713, todas sus
versiones, 1.319 líneas `a x b` con `a = faccan` y `b = canren`, **0 al revés**,
38 con valores distintos (la planificación cambió después de esa versión) y 12
con forma factor que hoy no tienen factor en `dncpro`. **En la última versión de cada obra** (197 obras, 124,5 MB): 20.197
líneas con `a = faccan` y `b = canren` en 83 obras, **0 al revés**, 1.224 con
valores distintos, 6 cuyo `dncpro` ya no tiene factor y 710 con forma `a x` o
rara, que no se comparan. El orden es factor x rendimiento sin excepción.

## 4 · (c) El efecto en el cuadre (previsión)

Simulación: a cada partida del cuadre se le suma `ROUND(precio x a x b, 2)` de
sus líneas con forma factor (hoy NULL) y se recalcula el estado con la misma
tolerancia de 0,01. PLANIF_JO, con `factor = faccan` si `factip = 1`.

| Origen | NO_CUADRA hoy | -> CUADRA | Sigue NO_CUADRA (con factor) | CUADRA -> NO_CUADRA |
|---|---:|---:|---:|---:|
| MASTER_PLANIF_JO | 96.307 | **54.024** | 12.847 | 280 |
| MASTER_PRE_ABC | 62.155 | **37.024** | 7.230 | 5 |
| MASTER_INICIAL | 781 | **86** | 35 | 0 |
| ESTUDIO | 20.687 | **5** | 37 | 0 |
| PLANIF_JO | 21.671 | **6.920** | 14.751 (1.898 con factor) | 25 |

- **PLANIF_JO, factor 0**: con el factor literal (0 -> importe 0) pasan 6.920; si
  el 0 se leyera como «sin factor» (1), solo 5.186. Sigrid multiplica por 0: la
  cantidad de esas líneas es 0 (6.096 de 6.188). R9.
- **Las 310 que dejan de cuadrar**: 265 son de una sola obra (2128229, trozo 15);
  en su v27 la 347800 cuadra en 149,34 sin sus 6 líneas `MA9999` con factor, que
  suman 92,93 más. Pinta a descompuesto con líneas de detalle de otra línea (el
  mismo fenómeno que explica las de campo vacío). No se arregla aquí (D10).
- ESTUDIO casi no se mueve: su NO_CUADRA tiene otra causa.

## 5 · (d) El coste de retrocear

- Hoy: 3.025 versiones, 2.043 MB de texto, 4.398.909 líneas de master; `lineas`
  1.967 MB, `cuadre_partida` 511 MB, `_des_texto` 1.713 MB; base 33 GB de 64.
- Primera carga del 29-09 (`--sin-tope`, tabla vacía): **916,9 s en 7 lotes**
  (paso entero 15 min 17 s). Nocturna normal (123 versiones, 121 MB): 8 min 42 s
  a 10 min 53 s el paso entero.
- **Estimado del retroceo completo: 20-30 min** (el troceado de la primera carga
  más el `DELETE` de 4,4 M líneas y su cuadre, lote a lote) y hasta ~2 GB de
  tuplas muertas en `lineas` hasta que pase el autovacuum. Cabe en disco.
- Por la nocturna sola: 300 MB por noche, **~7 noches** con el master mezclado.

## 6 · Decisiones abiertas (recomendación en negrita)

- **D1 · La columna `factor`.** Nombre `factor`, `NUMERIC`. **1 si el campo 14 es
  un número; el valor de delante de la `x` si tiene forma factor; NULL si el
  campo está vacío o es raro** (sin campo no hay nada que afirmar; las líneas sin
  rendimiento siguen sin importe igual). PLANIF_JO: 1 con `factip = 0`. Alternativa:
  1 también con campo vacío (lo que sugería la ficha de la feature).
- **D2 · Las formas raras** (15 registros en 4,5 M). **NULL en factor y
  rendimiento, sin fallar, sin columna de texto en bruto**; la consulta de §2 se
  puede repetir para vigilar formas nuevas.
- **D3 · El mecanismo del retroceo.** **Ninguno nuevo: el sello de F-097** (cambian
  `01` y `03`) deja pendientes las 3.025 versiones, **y el humano lo fuerza de una
  vez con `build-descompuestos --sin-tope` + `apply-grants`** tras desplegar la
  imagen. Invalidar `atributos_troceado` no serviría (solo actualiza flags); un
  flag nuevo o un `UPDATE ... sello_troceado = NULL` sobran.
- **D4 · `00_setup.sql` en el sello.** **Sí**: `fn_num` decide el rendimiento y hoy
  cambiarla no retrocea nada (mismo arreglo que F-118 hizo con `stg`).
- **D5 · PLANIF_JO dentro.** **Sí**, con `factor = faccan` si `factip = 1`, 1 si
  `factip = 0` y NULL (sin importe) con cualquier otro `factip` (1 línea, 646); el
  factor 0 y el negativo (628 líneas), literales.
- **D6 · Porcentajes con factor** (88 líneas). **`porcentaje = rendimiento x 100`
  sin factor; el importe, con él**, como el resto.
- **D7 · La ficha de ESTUDIO.** **Avisar en `lineas`, `v_pbi_estudio` y
  `cuadre_partida`**: en ESTUDIO el precio es el de Estudios, pero `cantidad_total`
  e `importe_total` siguen la medición ACTUAL del ámbito 3 (Sigrid la actualiza);
  la foto fija de Estudios es MASTER_INICIAL. Ejemplo: 0713, 400857 HORMIGÓN EN
  ESCALERAS, 207,20 x 25,95 = 5.376,84 frente a 207,20 x 24,03 = 4.979,02 del
  cierre inicial (medido por el líder).
- **D8 · Dónde va la columna.** **Al final** de la tabla y de las tres vistas: la
  tabla persiste (`ALTER TABLE ADD COLUMN` la pone al final) y `CREATE OR REPLACE
  VIEW` solo admite columnas nuevas al final. Alternativa: `DROP VIEW` + `CREATE`
  para ponerla junto a `rendimiento`.
- **D9 · El `acceptance` dice «7 líneas con factor»**: son **9** líneas (7 formas).
  **Corregir el criterio a 9** al aprobar la spec.
- **D10 · Fuera de alcance, proponer feature nueva**: (1) las líneas con campo 14
  VACÍO y precio y cantidad distintos de 0 (al menos ~95.000 entre los cuatro
  orígenes del líder; ejemplo en el ámbito 3, partida 214971: `0.8 x 2309.95` sin
  rendimiento ni tipo, entre bloques separados por registros vacíos); y (2) las
  310 partidas que dejan de cuadrar (§4). **Las dos parecen descompuestos con
  líneas de detalle anidadas**; hay que mirarlo en la pantalla de Sigrid antes de
  diseñar nada.

## 7 · Lo que queda MANUAL del humano

Imagen nueva del job ANTES del retroceo (si no, la imagen vieja retrocea hacia
atrás y su `CREATE OR REPLACE FUNCTION fn_trocear` falla contra la nueva), foto
del cuadre antes, `build-descompuestos --sin-tope` + `apply-grants`, la 400854 v6
y el cuadre después, `publicar-diccionario` (versión 39). Tareas T14-T18.
