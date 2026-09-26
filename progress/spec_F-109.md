<!-- progress/spec_F-109.md -->
# F-109 · Spec escrita (spec-author, 2026-09-25) · revisada con el analisis exhaustivo de causas

Spec en `specs/F-109-partidas-codigo-no-unico/` (requirements 131 lineas, design
250, tasks 11 tareas). Rama `feature/F-109-partidas-codigo-no-unico` desde `main`
(323910f), en un worktree aparte. Ficha: `sdd: true`, `status: spec_ready`;
`BACKLOG.md` regenerado. Segunda pasada a peticion del humano (via lider): las
causas se rehacen EXHAUSTIVAS con `ctride`/`expide` y el resto de campos de
`raw.obrparpar`, y la D1 se reformula con la unicidad de las claves candidatas.

## Medido (solo lectura, 2026-09-25)

MCP y consultas `SET TRANSACTION READ ONLY` desde el scratchpad. **5.202 pares
`(obra_id, codigo_partida)`, 8.933 filas de mas, 158 obras** (92 del
seguimiento, 2.177 pares); el dia 24 eran 5.203/8.934/159. Todas son partidas
activas y distintas. **No es la empresa**: cada par vive en una sola ficha de
obra (156 obras de la empresa 1, una de la 25, una de la 31). **No es F-052**: 0
de las 14.135 filas implicadas esta colapsada.

## Causas: excluyentes, en este orden, y cuadran al par

| # | Causa | Pares | Filas de mas | Obras (seg.) | Pares seg. | Ejemplo |
|---|---|---|---|---|---|---|
| 1a | contratos con el cliente distintos, todas las copias con contrato | 637 | 941 | 19 (19) | 637 | 0617 planta 1ª / planta baja (161 pares); 0317 `01` bajo `EDI`/`PIS`/`ACE`, un contrato cada uno |
| 1b | contrato distinto, alguna copia SIN contrato | 175 | 194 | 21 (17) | 59 | 0371 `02.06`: `CD > 02` (CONT_PPAL), `URB2` (CONT_URBANIZ), `URB1` (sin) |
| 2 | mismo contrato, expediente distinto | 61 | 70 | 3 (3) | 61 | 0410 `14.01.01` caldera bajo `14.01` (exp. -4) y `14.02` (-3) |
| 3 | mismo contrato y expediente, subarbol bajo otro capitulo de la misma raiz | 1.932 | 4.979 | 114 (55) | 871 | 0560 viviendas tipo Ibiza/Menorca; 0404 FASE 1..6; 0430 presupuesto base / anexos parcela |
| 4 | raices paralelas | 2.360 | 2.710 | 19 (4) | 519 | 0444 `CD`/`CD-FII`, `CI`/`CI-FII`; 0515 raices `2`,`3` que copian `CD > 2`,`CD > 3`; fuera: un `CI` entero duplicado (107 pares) |
| 5 | misma ruta, hermanas homonimas o marcador | 28 | 30 | 16 (16) | 28 | 0510 `04.04.14` vallado / demolicion; 0443 `N/A` |
| 6 | misma ruta, nada las distingue (solo `ide` y `pos`) | 9 | 9 | 2 (1) | 2 | 0446 `2.2.4.1.1` «NOTA PAVIMENTOS» x2 |
| | **Total** | **5.202** | **8.933** | **158 (92)** | **2.177** | |

- Cuadra con el lider: 812 pares con contrato distinto (767 una copia por
  contrato); 218 con expediente distinto (112 uno por expediente).
- En Sigrid (`azure-apps/sigrid_tablas.md`): `obrctr` es el contrato de obra con
  el cliente (cliente, importe adjudicado, coeficientes, plazos) y `obrctrexp` los
  expedientes de un contrato (tipo, situacion, importe, fechas de aprobacion).
  El jefe de obra abre un capitulo por contrato o lote y repite en el los
  codigos: en 1a, 552 de 637 pares ademas cambian de capitulo.
- `expide`: 0 en el 97,8 % de `raw.obrparpar`; 3.554 filas con expediente real
  (65, 41 obras) y **5.258 con -3 o -4**, centinelas sin significado documentado.
  `raw.obrctrexp` **no se ingiere**.
- Descartados (0 pares que difieran): `tipdes`, `tipcon`, `numord`,
  `fecini`/`fecfin`, `proide`, `obrcalide`, `codobruni`, `parideori`;
  `parcoside`/`parvenide` no enlazan copias; `tipvis` (8) y `tip` (193) no
  explican ningun par.

## Claves candidatas (repetidos / filas de mas / obras; seguimiento)

| Clave | Repetidos | Filas de mas | Obras | Seg. (obras) |
|---|---|---|---|---|
| `(obra, codigo)` | 5.202 | 8.933 | 158 | 2.177 (92) |
| `(obra, contrato, codigo)` | 4.437 | 7.858 | 140 | 1.527 (74) |
| `(obra, contrato, expediente, codigo)` | 4.372 | 7.779 | 139 | 1.462 (73) |
| `(obra, ruta)` | 155 | 162 | 25 | 38 (21) |
| `(obra, expediente, ruta)` | 155 | 161 | 25 | 38 (21) |
| `(obra, contrato, ruta)` | 150 | 156 | 22 | 34 (19) |

**Lo que distingue las copias es el CAPITULO, no el contrato.** El contrato
explica por que se abrio otro capitulo en 812 pares, pero es redundante con la
ruta. Solo `partida_id` es unico.

## Consumidores (sin cambios respecto a la primera pasada)

Hoy ningun importe se duplica en el repositorio (todo une por `partida_id`).
Unir hecho y dimension por `(obra, codigo)` infla la 0437 de 883.460,55 a
3.474.491,83 EUR (x3,9). Los nombres de escalon de `v_pbi_dim_partida_niveles`
y de la dimension CI se resuelven por codigo: 10.593 filas con algun nombre ajeno.

## Decisiones abiertas para el humano (`design.md` §8)

- **D1 · clave legible (reformulada)**: el contrato NO desambigua (5.202 ->
  4.437) y apenas mejora la ruta (155 -> 150). Recomendada **(a) ninguna; solo
  `partida_id`**, con `ruta_capitulos` documentada como direccion CASI unica.
  Descartadas: (b) `(obra, ruta)` como clave alternativa de F-108 (KO permanente,
  38 en el seguimiento, salvo limpieza en Sigrid de las causas 4-6); (b')
  `(obra, contrato, ruta)` (150, igual de rota); (c) clave sintetica.
- **D2** regla dura `R-PARTIDA-CODIGO-NO-UNICO`: si.
- **D3** nombres por codigo en niveles y CI: documentar aqui, arreglar en feature
  aparte.
- **D4** version: la siguiente a `main` al fusionar (33; 34 si F-108 va antes).
- **D5** 2 codigos de solo espacios: solo texto.

## Relacion con F-099 (expedientes de obra, `pending`)

F-109 NO publica `ctride`/`expide`. Para F-099 quedan tres entradas: el enlace
partida -> contrato/expediente debe ir por `partida_id` (en 812 pares el mismo
codigo existe una vez por contrato); los centinelas -3/-4 de `expide` (5.258
partidas) hay que explicarlos; y hay que ingerir `raw.obrctrexp`. Conviene que
el lider lo anote en la ficha de F-099.

## APROBADA (humano, 2026-09-26)

D1-D5 con la recomendacion. **D2 con esta redaccion** (la propuso el lider tras
explicar al humano las consecuencias y los contras de la regla, y el humano la
aprobo): «No cruces tablas por obra + codigo de partida: usa `partida_id`.
Agrupar por codigo es valido si se quiere sumar todas las copias del concepto
(por ejemplo, la misma partida en todos los bloques o fases), y hay que decirlo.
Para identificar una partida ante el usuario, ensena su ruta de capitulos.» Es
decir: lo prohibido es UNIR por (obra, codigo); AGRUPAR por codigo se permite
declarandolo. **D3**: los nombres por codigo de niveles y CI se fichan como
feature aparte (F-111). **D4**: la version del diccionario es la siguiente a la
de `main` al fusionar (hoy `main` esta en la 34, asi que F-109 sube a la 35).
Las entradas para F-099 (enlace por `partida_id`, centinelas -3/-4 de `expide`,
ingerir `obrctrexp`) las anota el lider en su ficha.
