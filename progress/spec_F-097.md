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

## Hallazgo lateral (no es de esta feature)

`tables_sigrid.yaml` declara `incremental_column: tiemod` en `obrparpre`, y la
tabla **no tiene esa columna** en Sigrid (22 columnas, medido). Es el mismo caso
que `com`/`comlin`/`comprv` en F-074: `_source_tiemod` a NULL. Candidata a ficha
propia; no se toca aquí.

## Consultas de verificación manual (T20)

- **C1** `SELECT origen, count(*), sum(importe_unitario) FROM descompuestos.lineas WHERE partida_id = 419079 GROUP BY 1;` → ESTUDIO 10 / 134,35; MASTER_INICIAL 10 / 134,35; sin PLANIF_JO.
- **C2** `SELECT origen, estado, precio_partida, suma_descompuesto FROM descompuestos.cuadre_partida WHERE partida_id IN (419079, 377070) ORDER BY 1;` → 419079 ESTUDIO CUADRA; 377070 PLANIF_JO CUADRA 177,95 y ESTUDIO SUSTITUIDO_POR_PLANIFICACION.
- **C3** `SELECT origen, count(*) FROM descompuestos.lineas GROUP BY 1;` → ESTUDIO ~98.000 (120.373 menos las copias), PLANIF_JO ~287.000, master ~0,3-0,4 M.
- **C4** `python main.py check-raw-recuentos` → `obrparpre_des` sin filas de menos.

## DECISIONES ABIERTAS (para el humano)

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
