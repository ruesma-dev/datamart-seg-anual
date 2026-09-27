<!-- progress/spec_F-097.md -->
# F-097 · Mediciones del spec-author y decisiones abiertas

Spec: `specs/F-097-descompuestos-partidas/`. Todo medido el **2026-09-27** en
solo lectura: Sigrid por `sigrid-api` (`leer_sql`, solo `SELECT`) y el datamart
por el MCP de solo lectura. Nada escrito en ningún sitio salvo este repositorio.

## (a) Qué tabla respalda cada pestaña, y cómo se distinguen

| Pestaña (según el humano) | Tabla en Sigrid | Cómo se reconoce en el dato |
|---|---|---|
| COSTE (3) «Descomposición» | `obrparpre.des` con `amb = 3`, `fas = 0` | Texto `~D|...`; solo existe en la fase 0 (1 fila con `haydes` en fases > 0) |
| COSTE (3) «Planificación compras» | `dncpro` del documento `obr.dncide` | `paride` de la partida; `ambide` y `fas` siempre 0 |
| MASTER COSTE (8) «Descomposición» | `obrparpre.des` con `amb = 8`, `fas` = versión | Una copia por versión |

- **No existe tabla de líneas de descompuesto.** Buscadas todas las tablas con
  `paride`/`preide` (54): solo `dncpro` tiene elemento + rendimiento por partida.
  `obrparaux` 0 filas; `ppo` (presupuestos de Estudios) **0 filas**, igual que
  `auxppoele`; `obrest.des` es de estrategias, no de partidas.
- **El formato del `des`**: registros `~D|` separados por salto de línea (el
  texto largo del campo 9 puede traer saltos dentro). Posiciones base 0: 1
  código, 2 descripción, 3 precio, 4 cantidad total (rendimiento × medición), 5
  unidad, 7 código alternativo (= `dncpro.cod2`), 11 código de naturaleza, 13
  obra.capítulo analítico, 14 rendimiento, 16 tipo, 17 naturaleza, **36 =
  `dncpro.ide`** (0 o vacío si no viene de la planificación). Variantes de 38
  (75.458 registros), 37 (29.056), 29 (10.334), 19 (3.095) y 35 (2.430) campos.
- **Tipo (campo 16)**, recuento en ámbito 3: vacío 58.903 (las sincronizadas),
  8 = mano de obra 29.339, 10 = material 19.451, 4 = % (descuentos, incrementos)
  4.007, 3 = ? 3.578, 9 = maquinaria 3.400, 13 = % medios auxiliares 1.322,
  11 = ? (códigos `SB...`, subcontrata) 373. No hay catálogo: `auxppoele` vacía.
- **Lo que CORRIGE al modelo del humano**: la «Descomposición» de COSTE **se
  reescribe** con la planificación. De las 42.958 partidas con `des` en ámbito 3,
  **7.866 son copia exacta de su `dncpro`** (7.611 las mismas líneas, 161
  subconjunto, 68 distintas) y 26.624 están planificadas pero conservan el de
  Estudios. Además 38.551 tienen `haydes = 1` sin texto, y 38.533 de ellas están
  planificadas. Caso: 0695, partida 03.05.02 (377070): su `des` de ámbito 3 son
  las 26 líneas de su planificación, con el `dncpro.ide` en el campo 36.
- **La foto de Estudios que sí es fija**: la versión 0 del master, rotulada
  «CIERRE INICIAL_ESTUDIO» (o variantes) en 104 obras (23.574 partidas, 16
  enlazadas) y «CIERRE INICIAL O.T.» en unas 30.

## (b) Volumen y coste de ingesta

Hoy **no se ingiere `des`** (excluido en `obrparpre` y en `obrparpar`). `dncpro` sí
(F-066): 287.282 líneas con partida en la necesidad de su obra, 245 obras, 110.146
partidas; 185.991 con contrato adjudicado, 6.493 con proveedor recomendado.

| Conjunto | Obras | Versiones | Filas (partidas) | MB de texto |
|---|---|---|---|---|
| Ámbito 3 fase 0 | 178 | — | 42.958 | 21,5 |
| Master, todo | 196 | 3.023 | 1.616.461 | 2.142 |
| Master desde la primera ABC | 59 | 1.191 | 882.152 | 1.244 |
| Master ABC + cuatrimestrales | 111 | 359 | 210.347 | 301 |
| Master solo vigente | 123 | 123 | 74.464 | 105 |
| Master primera ABC + vigente ≥ ABC | 59 | 113 | 64.726 | 93,5 |
| Master v0 + primera ABC + vigente | 181 | 345 | 131.513 | 146 |

- Por obra (ámbito 3): mediana 179 partidas y 458 líneas, p90 492 / 1.580, máx
  2.389 / 6.519. Master: mediana 14 versiones por obra (p90 33, máx 46), 422
  partidas por versión (p90 1.172), 2,6 MB por obra (p90 36,6, máx 78,7).
  0726: 1.305 partidas y 3.350 líneas en ámbito 3; 2 versiones. 0695: 1.569 y
  5.405; 30 versiones, 44,2 MB de master.
- **Líneas**: ámbito 3, 120.373 registros (2,8 por partida). Master, por muestra
  de 30.000 filas en seis tramos de `ide`: 1,4-3,9 registros por fila y 360-630
  caracteres por registro → **~4,5 M registros** en el master entero.
- **Lectura por la pasarela**: ámbito 3 entero, **25,7 s** (9 páginas de 5.000).
  Master, 6 páginas: 0,38-0,55 MB/s, y una de 10.000 filas / 11,3 MB tardó 66 s
  (por eso `page_size` 2000). Estimación: master entero 65-94 min; desde ABC
  38-55 min; **lo que propone la spec (~126 MB: 93,5 de ABC + vigente, 11,3 de la v0 y
  21,5 del ámbito 3) 4-6 min**.
- Postgres: estimado 250-400 MB con índices (27 de 64 GB ocupados el 26-09).

## (c) «Del ABC en adelante», en el dato

`obrfasamb.tex` de ámbito 8 con `ABC` (la regla de `mart`): 59 obras. Partidas
del master con algún registro enlazado a `dncpro`: **antes de la ABC 35,6 %**
(18.689 de 52.464), **la ABC 98,5 %** (22.108 de 22.441), **después 98,6 %**
(847.718 de 859.711). En las 137 obras sin ABC, 19,7 %. Es decir: desde la ABC
el descompuesto del master ES la planificación de compras del jefe de obra.
Patrón SQL calibrado contra el troceado en Python (7.866 = 7.866 en ámbito 3).

## (d) La partida de Juan, con el dato delante

- **D05DF210 no existe en Sigrid**: 0 filas en `obrparpar.cod`, `codobruni` y
  `numord` (todas las obras), en `con.cod`, en `ppopro.cod` y dentro del `des`
  de la 0726. La partida es la **04.02 «FORJ. RETICULAR 35+10»** de la 0726
  (`partida_id` 419079, `CD > 04 > 04.02`), la única de Sigrid con esa
  descripción, 3.926,79 m2 a **134,35**, igual en `stg.presupuesto` (ámbitos 3 y
  8, versiones 0 y 1).
- **ESTUDIO** (ámbito 3 fase 0, sin enlaces): casetones 10,50 × 1; HA-30 120 ×
  0,32; fluido 6 × 0,32; XA3 4 × 0,32; SR 10 × 0,32; bombeo 15 × 0,32; acero
  1,40 €/kg × 24,5; malla 1,41 × 1,2; MO reticular 32 × 1; PP pilares 417,55 ×
  0,015. Σ `ROUND(precio × rend, 2)` = **134,35: cuadra**.
- **PLANIF_JO: vacío.** La necesidad de la 0726 tiene 42 líneas, todas de la
  CI.02.02 (casetas). El jefe de obra aún no ha planificado el forjado.
- **MASTER**: versiones 0 «CIERRE INICIAL_ESTUDIO» y 1 «CIERRE INICIAL_OBRA»,
  las dos del 22-09-2026 y con las mismas 10 líneas. Sin ABC: no hay
  `MASTER_PLANIF_JO` para la 0726 todavía.
- **Comparación que sí se puede hacer hoy** (0695, 03.05.02 «Hormigón Armado
  Pilares»): v1 del master 2 líneas (HA25 Holcim 109,25 + fluido 3,30 = 112,55);
  ABC (v3) 12 líneas = 118,61; planificación y ámbito 3: 26 líneas = 177,95.
- **Cuadre general**: `ESTUDIO` 12.967 de 35.710 partidas con precio (36,3 %);
  `PLANIF_JO` 71.643 de 93.320 (76,8 %) más 5.399 a menos del 1 %.
  Sin descompuesto ni planificación y con precio (tanto alzado): 49.204
  partidas hoja de ámbito 3 fase 0 en 672 obras.

## (e) El catálogo de elementos y el producto de compras

- Los códigos del `des` de Estudios son **libres por obra**: 31.726 códigos
  distintos en ámbito 3, **solo 253 son códigos de producto** (`pro` → `con.cod`;
  5.713 códigos distintos para 55.179 productos, uno por empresa).
- El enlace fiable al producto es el de la planificación: registro enlazado →
  `dncpro.proide` (274.966 líneas con producto). 21.588 registros enlazados, el
  100 % con código de producto; 91.276 sin enlazar no lo son.
- Con F-092: `producto_id` es el `pro.ide`; F-092 le pondrá nombre y
  naturaleza. Con F-038: `dncpro` es la necesidad que adjudica el comparativo
  (`comlin.dncproide`) y lleva el contrato (`adjctride`, `adjctrlin`), así que
  planificado → comparativo → contrato → albarán/factura se cierra por llaves
  que esta feature publica. Aviso heredado de F-038: `dncpro.pre` es el precio
  adjudicado.

## (f) El master entero, incremental por versión (revisión del 2026-09-27)

Pedido por el humano al cambiar D5: el master ENTERO entra, y releerlo con
`run-all --full` cada noche serían 65-94 min. Medido en solo lectura:

- **No hay marca de cierre utilizable.** `obrfasamb` de ámbito 8 (3.188 filas):
  `est = 2` y `act = 1` en casi todas, `feccie` informado en 28, `estgra = 0`
  siempre; ni `obrparpre` ni `obrfasamb` tienen `tiemod`. La vigente (`conext`
  cod 15) no es la última: **357 versiones son posteriores a la vigente**
  (trabajo en curso) y 555 son de obras sin vigente.
- **Evidencia histórica por rangos de `ide`**: en 80 de 2.151 versiones
  anteriores a la vigente hay filas con `ide` mayor que el primero de la versión
  siguiente, es decir, insertadas después de cerrarse. Son **155 filas y las 155
  vienen sin `des`, con `can = 0` y `pre = 0`**: partidas nuevas que Sigrid da de
  alta en todas las versiones. Ninguna inserción tardía ha traído descompuesto a
  una versión cerrada. Un `UPDATE` en sitio no deja rastro: no se puede
  descartar hoy.
- **Huella por versión** (`progress/mediciones/F-097_huella_master.sql`):
  SQL Server 2012, así que `HASHBYTES` solo admite 8.000 bytes; la huella es
  `CHECKSUM_AGG` de (ide, longitud, SHA-256 del primer y último tramo de 8.000,
  can, pre). Ciega a un cambio en mitad de un `des` de más de 16.000 bytes: 9.541
  filas (0,6 %). Tarda **24 s** para las 3.023 versiones. Toma 1: 18:25 UTC →
  `progress/mediciones/F-097_huella_master_2026-09-27.csv`. Toma 2: 18:51 UTC,
  **0 diferencias, 0 nuevas, 0 desaparecidas**: prueba que la huella es estable,
  no que las versiones no cambien (domingo, 26 min). **La prueba de verdad es T0**.
- **Conjunto de relectura nocturna**: vigente de las 123 obras = **105 MB**
  (3,2-4,6 min); vigente de las 34 obras con versión en los últimos 12 meses, 42
  MB; vigente + posteriores + última = 552 versiones / 440 MB (13-19 min,
  descartado: la huella cubre las posteriores). Nuevas: 21-43 versiones al mes,
  27-62 MB/mes (~1,3 MB/día).
- **Reparto por origen** (D13): `MASTER_INICIAL` 169 versiones, 35.924 filas,
  11,3 MB; `MASTER_PRE_ABC` 1.664 / 698.401 / 887 MB (172 obras);
  `MASTER_PLANIF_JO` 1.190 / 882.136 / 1.244 MB (59 obras). Una versión con
  `des` no tiene fila en `obrfasamb`, y hay filas con `obride = 0` (versión 26,
  227 filas): el troceado las conserva y el cuadre las deja fuera.
- **Primera carga**: 2,14 GB a 0,38-0,55 MB/s = 65-94 min, más ~4.700 llamadas
  → **1,5-2 h**; troceado inicial en Postgres 20-40 min (sin medir).
- **Noche normal**: 24 s de huella + 26 s de ámbito 3 + 3,2-4,6 min de vigentes
  + nuevas y cambiadas → **4-6 min**; build 2-4 min.
- **Espacio**: texto 1,0-2,2 GB (TOAST, sin medir), líneas ~4,9 M → 1,2-1,7 GB,
  cuadre ~0,3 GB: **2,5-4,2 GB**. Disco de 27 a ~30-31 GB de 64 (47-49 %).

## El `tiemod` que no existe (ahora en el alcance, R29)

`obrparpre` declara `incremental_column: tiemod` y la columna **no existe** en
Sigrid (22 columnas; `_source_tiemod` a NULL, degradado en silencio en
`ingest_raw_step.py:279`). Se corrige aquí como F-074 hizo con `com`/`comlin`/
`comprv`. **Y no es la única**: comprobado contra `INFORMATION_SCHEMA`, de las 23
entradas que declaran `tiemod`, **14 no lo tienen**: `cob`, `ctr`, `ctrpro`,
`dca`, `dcapro`, `dcf`, `dcfpro`, `obr`, `obrctr`, `obrfas`, `obrfasamb`,
`obrparpar`, `obrparpre`, `pag` (D14).

## Consultas de verificación manual (T18)

- **C1** `SELECT origen, count(*), sum(importe_unitario) FROM descompuestos.lineas WHERE partida_id = 419079 GROUP BY 1;` → ESTUDIO 10 / 134,35; MASTER_INICIAL 10 / 134,35 (v0); MASTER_PRE_ABC 10 / 134,35 (v1); sin PLANIF_JO.
- **C2** `SELECT origen, estado, precio_partida, suma_descompuesto FROM descompuestos.cuadre_partida WHERE partida_id IN (419079, 377070) ORDER BY 1;` → 419079 ESTUDIO CUADRA; 377070 PLANIF_JO CUADRA 177,95 y ESTUDIO SUSTITUIDO_POR_PLANIFICACION.
- **C3** `SELECT origen, count(*) FROM descompuestos.lineas GROUP BY 1;` → ESTUDIO ~98.000 (120.373 menos las copias), PLANIF_JO ~287.000, las tres de master ~4,5 M en total.
- **C4** `SELECT count(*), sum(filas) FROM descompuestos._versiones_cargadas;` → 3.023 versiones (más las nuevas desde el 27-09) y 1.616.461 filas, igual que `count(*)` de `descompuestos._des_texto WHERE ambito_id = 8`.

## DECISIONES DEL HUMANO (2026-09-27)

- **Aprobadas según la recomendación**: D1, D2, D3, D6, D8, D9, D10, D11.
- **D5 CAMBIA**: no se parte; no hay F-097b. El master ENTERO (3.023 versiones)
  entra en F-097.
- **D4 se ajusta**: se ingieren todas las versiones; la v0, la primera ABC y la
  vigente se MARCAN (flags), no se filtran.
- **D7 queda sustituida por D12**: con el master incremental, una segunda
  entrada del YAML la truncaría `--full`.
- **Nuevo en el alcance**: el `tiemod` de `obrparpre` (R29).

## DECISIONES NUEVAS (D12-D15, para el humano)

- **D12. Vía de ingesta** (sustituye a D7). Recomendación: **paso propio
  `ingest_descompuestos`** con estado en `descompuestos._des_texto` y
  `_versiones_cargadas`, que `--full` no trunca, releyendo por noche: vigentes,
  nuevas y las de huella distinta, más el ámbito 3 entero. Ventaja añadida: no
  toca la identidad de la ingesta ni la puerta de F-024. Coste: el texto no pasa
  por `check-raw-recuentos`; el paso cuadra el recuento de cada versión con su
  huella y revierte si no casa.
- **D13. Origen de las versiones entre la v0 y la primera ABC** (y de las obras
  sin ABC): 1.664 versiones, 887 MB. Recomendación: origen propio
  **`MASTER_PRE_ABC`**, para que no se confundan con `MASTER_PLANIF_JO`; todas
  las versiones llevan además los flags de D4.
- **D14. Las otras 13 tablas con `tiemod` falso.** Recomendación: ficha propia
  (corregir el YAML y ampliar el test de F-074), fuera de F-097; aquí solo
  `obrparpre`, como se ordenó.
- **D15. Primera carga y presupuesto nocturno.** Recomendación: primera carga
  MANUAL (`--sin-tope`, 1,5-2 h más el troceado) un fin de semana por la
  mañana, mirando antes los créditos de CPU del servidor; y un tope nocturno de
  **300 MB** releídos (`DESCOMPUESTOS_PRESUPUESTO_MB`), con el que, sin primera
  carga, la nocturna converge sola en unas 8 noches.

## DECISIONES DE LA PRIMERA VERSIÓN DE LA SPEC (D1-D11)

- **D1. Qué se publica como ESTUDIO.** El dato no casa del todo con «la
  Descomposición de COSTE es la referencia de Estudios»: en 7.866 partidas es
  copia de la planificación. Opciones: (a) el `des` de ámbito 3 tal cual; (b) solo
  las partidas sin enlaces, y las copias marcadas `SUSTITUIDO_POR_PLANIFICACION`;
  (c) la versión 0 del master. **Recomendación: (b) como `ESTUDIO` y además (c)
  como origen propio `MASTER_INICIAL`**, que recupera Estudios para las partidas
  planificadas en 169 obras por 11 MB.
- **D2. Nombres de origen.** Recomendación: los de Juan (`ESTUDIO`, `PLANIF_JO`,
  `MASTER_PLANIF_JO`) más `MASTER_INICIAL` de D1.
- **D3. Dónde se publica.** Recomendación: **esquema nuevo `descompuestos`**
  con paso propio que solo lee `raw` (no bloquea `mart`, permisos por esquema).
  Alternativa: `stg`, descartada porque un fallo tumbaría el seguimiento.
- **D4. Qué versiones del master.** Recomendación: **v0 + primera ABC +
  vigente si es ≥ ABC** (~105 MB de master, 3-5 min; con el ámbito 3, 4-6). Alternativas: solo vigente (105 MB,
  pero sin ABC); ABC + cuatrimestrales (301 MB, 9-13 min); todo desde la ABC
  (1,24 GB, 38-55 min).
- **D5. Partir la feature.** Recomendación: **sí, así**: F-097 con lo de esta spec
  y **F-097b** para el histórico completo del master desde la ABC con ingesta
  incremental por versión (antes hay que medir si una versión cerrada cambia).
  Si el humano prefiere recortar más, F-097 solo COSTE (21,5 MB, 26 s) y el
  master entero a F-097b.
- **D6. Partidas auxiliares anidadas.** No existen en el dato (`des` plano,
  `obrparaux` vacía, 23 líneas con nivel en `dncpro`). Recomendación: publicar
  `nivel` y `es_nivel_padre` de `dncpro` tal cual, sin recursión ni columna de
  línea padre.
- **D7. Vía de ingesta.** Recomendación: **segunda entrada de `obrparpre` en el
  YAML con destino `obrparpre_des`**, pasando la identidad de la ingesta a
  `target_table` (idéntico para las 71 actuales). Alternativa: paso de ingesta
  propio fuera del YAML, sin puerta ni recuentos.
- **D8. Tipo de elemento.** Recomendación: la traducción del diseño, **validando
  con Negocio los códigos 3 y 11**; las líneas sin tipo se clasifican por
  naturaleza.
- **D9. Grano del catálogo de elementos.** Recomendación: `(obra_id,
  codigo_elemento)`, porque los códigos de Estudios son libres por obra, con
  `producto_id` cuando lo haya.
- **D10. Proveedor, contrato y mes en PLANIF_JO.** Recomendación: publicar
  proveedor recomendado, contrato y línea adjudicados y `fecha_maxima` (5 líneas
  informadas: la ficha dice que el mes previsto no existe en la práctica), y
  `precio` con el aviso de F-038 (es el adjudicado).
- **D11. El código D05DF210.** No está en Sigrid. Recomendación: confirmar con
  Juan que es la 04.02 de la 0726 y que el código viene del programa de Estudios;
  la feature identifica la partida por `partida_id` y ruta, como manda F-109.
