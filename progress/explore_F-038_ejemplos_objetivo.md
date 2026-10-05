<!-- progress/explore_F-038_ejemplos_objetivo.md -->
# F-038 · Ejemplos del coste objetivo para ver con Negocio (D4)

Spec-author, 2026-10-04. SOLO LECTURA: Postgres de Azure, sesión `READ ONLY` con
psycopg directo. Regla decidida por el humano el 2026-10-04 (D4): **la base es
la primera ABC si casa; si no, una versión ANTERIOR que case; nunca una
posterior** («de momento; lo veré con Negocio»). «Casa» = `base × (1 − dto)` da
el precio de la línea de la oferta OBJETIVO con 0,011 € + 0,2 % de tolerancia.
El elemento se busca en `descompuestos.lineas` de la misma obra y partida
(`dncpro.paride` de la línea del comparativo).

## Recuento (las 83.329 líneas OBJETIVO con `dto`, todas las obras)

| obra | clase | líneas |
|---|---|---|
| con primera ABC (41.629) | casa con la ABC | **11.409** |
| | no con la ABC, sí con una ANTERIOR | **5.468** |
| | ni ABC ni anterior, sí con una POSTERIOR | **12.351** |
| | solo con la planificación de hoy (`PLANIF_JO`) | 1.099 |
| | con ninguna | 11.302 |
| sin ABC (41.697) | casa con Estudios (`MASTER_ESTUDIO`/`ESTUDIO`) | 7.386 |
| | no con Estudios, sí con otra versión del master | 21.789 |
| | solo con `PLANIF_JO` de hoy | 1.362 |
| | con ninguna | 11.160 |
| sin descompuesto en la partida | — | 3 |

Con la regla: **24.263 líneas casan (29,1 %)** (ABC 11.409 + anterior 5.468 +
Estudios 7.386); **59.066** se publican con la base de la regla marcada «no
casa»: entre ellas, 12.351 que casarían con una posterior y 21.789 de obras sin
ABC que casarían con otra versión del master. **Decidido por el humano el
2026-10-04**: en una obra sin ABC la base es Estudios y, si no casa, «no casa»;
no se busca en otras versiones («dependerá de Negocio cambiarlo»).

En obras **≥ 0700** (todas con ABC): ABC 2.947 líneas (12 obras), anterior 440
(10 obras), solo posterior 1.888 (9 obras), ninguna 1.305. Hay ejemplos de sobra.

## Lo que enseñan los ejemplos (para la conversación con Negocio)

Las fechas de creación de las versiones (`mart.master_versiones_tipadas`) dicen
que **la base es la versión VIGENTE cuando se hizo el comparativo**, no la ABC
como tal: los dos «anterior» son comparativos hechos ANTES de que existiera la
ABC, y el primer «posterior» (0702) se hizo DESPUÉS de una versión posterior a la
ABC, que era la vigente ese día. Con «nunca posterior», ese caso sale «no casa».

## 1 · Casa con la ABC

**A1 · 0700 AHORRAMAS EN GETAFE (MADRID)** · comparativo `COMINST25/0026`
(`con.ide` 2538281, 29-05-2025) · partida 16.01.12 SISTEMA DE BOMBEO · proveedor
OBJETIVO · precio objetivo **3.228,16** · `dto` 7,29 %.
- ABC v3 «ABC» (creada 30-05-2025): 3.482,00 × (1 − 0,0729) = **3.228,16** → casa.
- Anterior que casa: ninguna (el elemento no está antes de la ABC).
- Posteriores: v4-v21 siguen a 3.482,00 (también casarían).

**A2 · 0707 88 VIVIENDAS "EL TOMILLAR" EL ESCORIAL (MADRID)** · comparativo
`0707.0_0022` (`con.ide` 2633121, 10-11-2025) · partida 31.01 SEGURIDAD Y SALUD ·
OBJETIVO · **124.367,21** · `dto` 5,73 %.
- ABC v4 «CIERRE DICIEMBRE-25/ ABC» (19-01-2026): 131.926,58 × 0,9427 =
  **124.367,19** → casa.
- Anterior que casa: ninguna. Posteriores: v5-v7 a 131.926,58 (casan); desde v8
  «CIERRE MARZO-26» baja a 122.500,00 (115.480,75, no casa).

## 2 · No casa con la ABC, sí con una ANTERIOR

**B1 · 0700 AHORRAMAS EN GETAFE** · comparativo `0700.0_0001` (`con.ide` 2503362,
26-03-2025) · partida 01.03 EXCAVACIÓN ZANJAS PARA CIMENTACIONES · OBJETIVO ·
**10,0127** · `dto` 7,29 %.
- ABC v3 «ABC» (30-05-2025): 17,50 × 0,9271 = 16,2243 → no casa.
- Anterior v2 «PLANIFICACION VALORADA INICIAL» (01-04-2025): 10,80 × 0,9271 =
  **10,0127** → casa.
- Posteriores (v4-v21): 17,50 → no casan.

**B2 · 0706 AHORRAMAS C/ISLA DE PERDIGUERA,17 HUMANES-MADRID** · comparativo
`0706.0_0005` (`con.ide` 2571506, 24-07-2025) · partida 03.08 H. ARM. HA-25/F/20/XC2
- MURO A UNA CARA · OBJETIVO · **90,1112** · `dto` 8,05 %.
- ABC v3 «ABC/ CIERRE AGOSTO-25» (19-09-2025), elemento HA-25/B/20/XC2: 92,50 ×
  0,9195 = 85,0538 → no casa.
- Anterior v2 «PLANIFICACION VALORADA INICIAL» (31-07-2025): 98,00 × 0,9195 =
  **90,1110** → casa.
- Posteriores (v4-v11): 92,50 → no casan.

## 3 · Ni ABC ni anterior; sí una POSTERIOR

**C1 · 0702 EDIF. HOTELERO Y OFICINAS Pº VIRGEN DEL PUERTO** · comparativo
`0702.0_0049` (`con.ide` 2606858, 29-09-2025) · partida 02.30.08 CARGA Y
TRANSPORTE TIERRAS LIMPIAS · OBJETIVO · **9,70** · `dto` 3 %.
- ABC v2 «ABC» (28-07-2025): 13,50 «M3 CARGA Y TRANSPORTE DE TIERRAS EXCAVACION»
  × 0,97 = 13,095 → no casa. No hay anterior con el elemento.
- Posterior v4 «CIERRE AGOSTO-25» (creada 23-09-2025, **seis días antes del
  comparativo**), «M3 TRANSPORTE TIERRAS VERTEDERO»: 10,00 × 0,97 = **9,70** →
  casa (igual v5-v19).

**C2 · 0709 AHORRAMAS TALAVERA - AV. PRINCIPE FELIPE** · comparativo
`0709.0_0051` (`con.ide` 2724023, 18-03-2026) · partida 05.01 CAPA COMPRESIÓN
HA-25/B/20/IIa #150x150x6 mm e=10 cm · OBJETIVO · **2,9533** · `dto` 7,71 %.
- ABC v3 «ABC/ CIERRE DICIEMBRE-25» (15-01-2026): «mallazo 15 15 6» 4,20 ×
  0,9229 = 3,8762 → no casa. No hay anterior con el elemento.
- Posterior v6 «CIERRE FEBRERO-26» (20-03-2026, dos días después del alta del
  comparativo), «mallazo 20x20x6 s/ planos»: 3,20 × 0,9229 = **2,9533** → casa;
  desde v7 baja a 1,47 (no casa).
