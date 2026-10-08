<!-- progress/spec_F-132.md -->
# F-132 · Mediciones del spec-author (2026-10-08)

Todo en **solo lectura**: el Postgres de Azure con una sesión `read_only` de
psycopg (credenciales del `.env`, solo `SELECT` y `EXPLAIN ANALYZE` de
`SELECT`) y el MCP. Sigrid no hizo falta: `raw.rac` y `raw.con` ya están en la
base. Ninguna escritura. Los scripts quedaron en el scratchpad de la sesión.

## 0. Lo que cambia la ficha, en tres frases

1. `rac` fecha al segundo el estado actual del **99,4 %** de contratos, facturas
   y comparativos; el 0,6 % sin pasos está en su estado inicial desde el alta, y
   solo **75** documentos (stock histórico, 2009-2026) cambiaron de
   estado fuera de un proceso y no se pueden fechar.
2. **Lo que solo ve la foto no es un stock de ~70: es un FLUJO.** En la única
   noche contrastable, 12 de los 230 cambios que vio la foto (5,2 %) son pasos
   DESHECHOS que `rac` ya no tiene, y 5 contratos se deshicieron y rehicieron el
   mismo día sin que la foto lo notara. Con la semántica de historia NETA los dos
   casos quedan explicados, pero retirar la foto pierde la FECHA del deshacer.
3. El contraste no necesita correr cada noche: las tablas de la foto son
   persistentes y `rac` es historia completa, así que se **recalcula entero el
   día que se quiera**, sobre todas las noches a la vez.

## 1. Las observaciones de la foto (corrige el encargo)

| `observado_en` (UTC) | `tomada_en` (UTC) | Línea base | Documentos | Cambios | Altas | Desaparecidos |
|---|---|---|---|---|---|---|
| 2026-10-07 00:03:00 | 2026-10-07 07:01:34 | sí | 185.942 | 0 | 185.942 | 0 |
| 2026-10-08 00:03:01 | 2026-10-08 03:26:34 | no | 186.042 | 230 | 100 | 0 |

**La segunda observación es la de la NOCTURNA del 08-10** (batch
`20261008T000020Z-dbddb2`), no la del `build-compras` a mano de las 10:19: ese
build no encontró `raw.con` más nueva (la última carga es de las 00:03) y no
escribió nada, como manda R7 de F-067. La del 09-10 aún no ha corrido (medido a
las 11:36 UTC del 08-10). Tramos vivos hoy: 185.712 de línea base y 330 vistos
cambiar o nacer (16 contratos, 314 facturas). Tamaño: 20 MB + 24 kB.

## 2. Último paso de `rac` frente a `con.est` (hoy)

`raw.con` es de las 00:03 UTC y `raw.rac` de las 10:05-10:08 UTC del 08-10
(ingesta a mano de F-085): los pasos de esa mañana adelantan a `con.est`.

| Familia | Documentos | Con pasos | Último destino = `con.est` | Distinto | …por paso posterior a `raw.con` | Fuera de proceso | Sin pasos |
|---|---|---|---|---|---|---|---|
| Factura 15 | 166.949 | 166.852 | 166.721 | 131 | 62 | **69** | 97 |
| Contrato 44 | 19.093 | 18.540 | 18.537 | 3 | 0 | **3** | 553 |
| Comparativo 46 | 20.426 | 19.828 | 19.819 | 9 | 6 | **3** | 598 |

- **Fuera de proceso: 75**, casi todas facturas que pasaron a 10 o 50 sin paso
  (28 desde 5→6, 11 desde 4→5, 11 desde 2→3…), con último paso entre 2009 y
  2026-08-31. Unos pocos al año: el flujo que se perdería es pequeño.
- **Desfase de ingesta: 68**, todos con el último paso del 08-10 por la mañana.
  En la nocturna `con` y `rac` se leen en la misma media hora de madrugada, y de
  madrugada (00:00-03:00 de Madrid) en 2026 hay 30 pasos de factura y ninguno
  de contrato o comparativo: es ruido, pero la vista lo tiene que aguantar.
- **Sin pasos: todos en un estado INICIAL** —factura 1 (72) y 20 (25), contrato
  1 (553), comparativo 1 (505), 11 (75) y 100 (18)—, como midió F-085. Todos
  tienen `con.fec` salvo 10 contratos (`fec` = 0) y ninguno tiene `con.hor`: la
  fecha de alta es solo DÍA.
- Un único paso sin hora en toda `documento_procesos` (`momento` NULL).

## 3. El contraste de la noche del 07-10 al 08-10

Ventana de cada cambio: `(observado_antes, desde]` = (07-10 00:03, 08-10 00:03]
UTC; `rac.momento` es hora de Madrid y se pasa con `AT TIME ZONE`.

**Los 230 cambios que vio la foto**:

| Clase | Facturas | Contratos | Qué es |
|---|---|---|---|
| PASO (hay un paso al estado nuevo en la ventana) | 214 | 4 | explicado |
| DESHECHO (el último paso ya lleva al estado nuevo, y es anterior a la ventana) | 7 | 2 | explicado |
| VUELTA AL INICIAL (sin ningún paso y estado nuevo inicial) | 0 | 3 | explicado |
| FUERA DE PROCESO | 0 | 0 | explicado, sin fecha |
| DISCREPANCIA | 0 | 0 | — |

- Las 7 facturas pasan de 6 a 5; en `rac` su último paso es 4→5, fechado entre
  el 08-09 y el 05-10: alguien deshizo el 5→6 el 07-10.
- Los 3 contratos FIR (7) → PFP (1) sin un solo paso: se deshizo la cadena
  entera. Los otros 2: 7→5 (deshechos 5→6 y 6→7) y 5→3 (deshecho 3→5, el
  contrato vuelve a «enviado» con su envío del 21-09).

**Los pasos de `rac` en la ventana que la foto NO vio como cambio**: 88
facturas y 1 contrato son ALTAS de ese día (la foto los ve nacer ya en su
estado; `rac` da la hora de cada paso). **5 contratos** (17 pasos) son
IDA Y VUELTA: la cadena 1→3→5→6→7 deshecha y rehecha en segundos el 07-10
(como el CTSB25/0002 de F-085), con el mismo estado a las dos fotos.

## 4. Lo que da `rac` para la pregunta de Compras

809 contratos en EPF; **785 con más de 21 días** desde el envío; mediana
**3.051 días**; ninguno sin paso. Solo **47** se enviaron desde 2025, y de esos
**23** llevan más de 21 días: hay ~760 «zombis» enviados entre 2008 y 2024 que
nadie cerró. La respuesta correcta da la fecha real del envío y avisa de los
zombis; esto es un dato para Compras, no un error.

## 5. Coste

- La vista sobre `compras.contratos`/`facturas` + `documento_procesos` con
  `es_ultimo`: **0,8 s** la vista entera (186.042 filas, sin índice nuevo);
  contra `raw.con`, 5,2 s en frío. Se hace sobre las tablas de `compras`.
- En la nocturna, la vista nueva cuesta lo que un `CREATE VIEW` (< 1 s). La
  foto: el sub-paso `11` entre `tomada_en` (03:26:34) y el fin de
  `build_compras` (03:27:32) = **< 1 min**. Retirarla ahorra < 1 min y 20 MB.
- La nocturna del 08-10 duró **4 h 40 min 21 s** (00:00:21 → 04:40:42): 40 min
  por encima de las 4 h, sin F-085 todavía (+4 a +7 min previstos el 09-10).
  Esta feature no añade nada medible a la ventana; el contraste no corre de noche.

## 6. `acceptance` de F-132: lo que la medición contradice

1. «con la fecha exacta»: exacta para los 205.145 con paso que casa (99,4 %,
   contando el desfase de ingesta de hoy como casado); para los que no tienen pasos es el DÍA de alta, y los 75 fuera de proceso no tienen fecha (se
   dice y se da la cota: «cambió después de X»). Se reescribe.
2. «~70 documentos que solo ve la foto»: son 75 de stock, pero los deshechos son
   un flujo diario (~5 % de los cambios vistos) que la vista de `rac` resuelve
   con historia NETA. El criterio 2 los nombra como clase explicada.
3. La premisa falsa vive también en la ficha de `raw.conest` (`raw.yaml`), en
   `README_COMPRAS_C1_C2.md` y en la P24, y `azure-apps` aún pinta F-067 «SIN
   DESPLEGAR». Se añaden al criterio 4.

El `status` NO cambia (`pending`).

## 7. Aprobada por el humano (2026-10-08)

El humano aprobó la spec el 2026-10-08 («ok») con D1-D8 tal como las recomienda
`design.md` §8: D1 dos fases (A ahora; B tras el contraste) · D2 historia NETA de
`rac` · D3 comparativos dentro, obras fuera · D4 columnas de R2 · D5 los 75 fuera de
proceso sin fecha y con la cota `cambio_posterior_a` · D6 14 noches (hasta el
2026-10-22) y 0 `DISCREPANCIA` sin explicar · D7 recomendación previa BORRAR, que se
decide al final con el contraste delante · D8 contraste a demanda, no en la nocturna.
Se implementa la FASE A; la B espera a la decisión del humano.
