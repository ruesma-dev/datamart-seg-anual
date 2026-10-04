<!-- progress/spec_F-038.md -->
# F-038 · Spec: mediciones nuevas, decisiones y recomendaciones

Spec-author, 2026-10-04. Spec en `specs/F-038-comparativos/`. Parte de
`progress/explore_F-038_comparativos.md` (2026-09-17) y
`progress/explore_coste_objetivo.md` (2026-09-18); aquí solo lo que hacía falta
**para decidir** o lo que podía haber cambiado. Todo en SOLO LECTURA: Sigrid por
`sigrid-api` (`leer_sql`, ~35 consultas) y el Postgres de Azure (tamaños de `raw`
y una consulta cronometrada en sesión `READ ONLY`). Cero escrituras. (Una de las
conexiones se abrió con el cliente del ETL, que al arrancar ejecuta su
`CREATE SCHEMA/TABLE IF NOT EXISTS` de `_meta`: no-op sobre objetos existentes;
las siguientes fueron con `psycopg` directo y sesión de solo lectura.)

## 1 · Lo que la medición CORRIGE de la ficha (y por qué se tocan dos acceptance)

**El «no cuadran» de las cuatro magnitudes era, sobre todo, el IVA.** La ficha
mide el ofertado por proveedor con `dco.totdoc`, que es CON IVA (lo mismo que
`R-COMPRAS-SIN-IVA` dice de `ctr.totdoc`). `dco` trae `totbas`, la base SIN IVA.
Medido hoy sin IVA, en los 17.876 comparativos con una sola ganadora:

| comparación (ganadora) | cuadran al euro |
|---|---|
| A documento (`dco.totbas`) = B líneas (`Σ dcopro.tot`) | **17.795 de 17.869 (99,6 %)** |
| A ganadora = C adjudicado (`Σ comlin.can×pre`) | **16.050 de 17.876 (89,8 %)**; al 1 %: 16.530 |
| A ganadora = D contratado (`Σ ctrpro.tot` del contrato) | **7.274 de 17.765 (41 %)** |

D no cuadra por grano: **un contrato sale de varios comparativos** (3.960
contratos con más de uno, ampliaciones COAVAL), y el contrato evoluciona.
Además `dcopro.tot = can × pre` en las 786.710 líneas: **`dto` NO se aplica en
`tot`**; el precio ya viene neto y `dto` es el porcentaje que lo produjo.

**Totales sin IVA (2026-10-04):** ofertas en comparativos 71.302 (20.060
comparativos), A total **2.888,1 M€** (con IVA eran 3.492,2); B total 2.889,6 M€;
C 1.246,2 M€ en 198.626 líneas; D **606,2 M€** en 11.756 contratos enlazados por
`comlin.ctride`. Ganadoras (`con.est = 6`, tip 12): 17.878, **589,1 M€**; sus
líneas 588,1 M€.

**EL ADJUDICADO NO TIENE «DOS ATÍPICOS»: TIENE 52, Y SON LA MITAD DEL TOTAL.**
Comparativos cuyo adjudicado supera **10 veces su mayor oferta** y 100.000 €:
**52, que suman 602,5 M€ de los 1.246,2**. El corte es estable: con 3 veces en
vez de 10 son 65 y 606,7 M€. Cabeza: 1610000 (363,2 M€ contra una oferta máxima
de 2.200 €), 2139264 (9,5 M€ / 3.150 €), 2202443 (26,2 M€ / 10.653 €), 2834916
(66,9 M€ / 100.575 €). **Adjudicado saneado: 641,0 M€.** Quedan sin poder
juzgarse 11 comparativos > 100.000 € sin ninguna oferta con importe (3,0 M€).
Siguen: 14.585 líneas con `pre = 0` y 4.206 negativas (−22,2 M€).

**EL AHORRO DEL CONCURSO SE MEDÍA CON LAS FICTICIAS DENTRO.** Los 15.597
comparativos y 186,5 M€ de la ficha comparaban también ofertas de OBJETIVO,
OFICINA TÉCNICA y PLANIFICACIÓN, y con IVA. Solo ofertas **reales** con
importe > 0, sin IVA: **6.904 comparativos con al menos dos, 72,7 M€** (mínimas
274,3, máximas 347,0). Las ficticias entre sí darían otros 63,5 M€ que no son
ahorro de nada. Las 8 diferencias mayores están entre 0,32 y 0,51 M€: el ahorro
sobre ofertas no necesita más saneado que excluir ficticias e importes ≤ 0.

Por eso se ajustan en `features.json` los acceptance **3** (las cifras de cuadre y
el sin IVA) y **4** (el universo del ahorro y el saneado del adjudicado). Los
demás no se tocan.

## 2 · Oferta ficticia: CIF falso SOLO NO SIRVE; nombre solo, casi

Cruce sobre las 71.302 ofertas (`dco.entcif` × nombre que casa una familia):

| CIF | nombre casa familia | ofertas | entidades | comparativos |
|---|---|---|---|---|
| falso (`A99999999`/`A00000000`) | sí | 9.641 | 5 | 6.060 |
| falso | no (`º`, `OBJE`, `TRANIDE`, `OFICINA TENICA`) | 180 | 2 | 179 |
| vacío | sí | **23.078** | **172** | 13.594 |
| vacío | no | 13.998 | 6.045 | 6.551 (proveedores reales sin CIF) |
| real | sí | 5 | 3 | `MAT PLANIFICACION DE ESPACIOS, S.L.`, `ABC INSTALACIONES…`, `3 DE 3 OFICINA TECNICA…` |
| real | no | 24.400 | 2.599 | — |

**El CIF falso cubre 9.821 de 32.899 ficticias (30 %)**: 172 entidades ficticias
tienen el CIF vacío. **Y la entidad tampoco sirve**: la 977371 (CIF
`A00000000`) firma ofertas como OFICINA TECNICA, OBJE, OBJETIVO, OBJETIVO RUESMA
y PLANIFICADO; la familia la dice el nombre DE LA OFERTA (`dco.entres`), no el
proveedor. **Criterio decidido**: ficticia = CIF falso **o** (CIF vacío **y**
nombre de familia); familia por el nombre normalizado (mayúsculas, sin tildes ni
signos), en orden OBJETIVO, OFICINA_TECNICA, CUATRIMESTRAL, FASE_0, ABC,
PLANIFICACION; CIF falso sin nombre reconocible → `A99999999` OBJETIVO,
`A00000000` OFICINA_TECNICA. Falsos positivos conocidos: 3 ofertas de «MAT
Planificación de Espacios» sin CIF → lista de exclusión. Resultado: **32.896
ficticias, 1.298,8 M€ sin IVA, el 45 % del ofertado total**. Ganadoras ficticias:
**4** (0,1 M€). Los 200 nombres medidos (con recuento) están en la consulta
`t4` de esta sesión; los casos de los tests salen de ahí.

## 3 · Coste objetivo: dónde está el % y sobre qué base

- **`dcopro.dto`** informado en 95.808 de 794.946 líneas; formato **siempre**
  `-?dígitos(,dígitos)?%` (0 casos raros: ni `+`, ni punto, ni doble `%`), con
  **negativos** (−99,57 %, −168 %…: recargos). Gramática POSIX:
  `^-?[0-9]+(,[0-9]+)?%$`.
- Por familia: OBJETIVO 83.605 de 143.475 líneas con `dto`; REAL 8.457; OFICINA
  TÉCNICA 1.562; el resto residual.
- **Ofertas OBJETIVO: 12.259** en 11.420 comparativos (1.126 con dos o tres:
  «OBJETIVO INICIAL», «REVISADO»). **7.399 con un único %** (2.235 de ellas con
  alguna línea sin `dto`), **48 con varios** y **4.813 sin ninguno** (objetivo
  tecleado a mano, sin % que publicar).
- **La base se puede OBSERVAR, no solo suponer**: de las 83.605 líneas objetivo
  con `dto`, **73.052 (87,4 %)** tienen en el mismo `comlinide` una oferta
  ficticia cuyo `pre × (1 − dto)` es su precio: solo planificación 22.211, solo
  OFICINA TÉCNICA 32.101, **las dos a la vez 18.740** (precios idénticos). El
  12,6 % restante no tiene base reconstruible.
- Familias presentes en los comparativos con objetivo (11.144): con ABC literal
  solo **283**; con OT y planificación 4.239; solo OT 3.273; solo planificación
  2.685; ninguna 664. **«ABC» como nombre de entidad apenas existe**: el ABC vive
  en las ofertas PLANIFICACIÓN/PLANIFICADO/CUATRIMESTRAL/FASE 0. → Decisión D2.

## 4 · Enlace comparativo → contrato

`comlin.ctride`: 186.668 líneas, **18.633 comparativos**, 11.757 contratos, 0
huérfanos. **Ningún comparativo tiene dos contratos** (0); **3.960 contratos
vienen de varios comparativos**. `ctr.comide`: 11.482 comparativos; 151 contratos
cuyo `comide` no aparece en `comlin`. Consecuencia: el enlace bueno es N:1 desde
el comparativo (`compras.comparativos.contrato_id`) y **una columna por
contrato no puede contener N comparativos**: `compras.contratos.comparativo_id`
se queda como está (es la cabecera del contrato) y su ficha declara su límite y
remite al objeto nuevo. Decidido en la spec: no rompe nada publicado.

## 5 · Firmas, estado, actividad (refresco)

`com` 20.378 (era 20.261); APROBADO 18.801. 319 comparativos sin ofertas, 264 sin
líneas. Actividad informada en 20.225. Firmas tip 46: 66.469, **6.498 con
`fir = 0`** (de ellas 6 con fecha), 0 firmadas sin fecha. Roles: COMVAL DCOM
18.449 / JG 18.058 / JEFO 18.031; COAVAL 3.454 / 3.358 / 3.357; variantes UTE,
JEFINST, DIRGEN y DIRPRO. **5.375 comparativos repiten rol** (reenvíos tras un
rechazo): «la firma del jefe de grupo» no es una columna, son varias filas.

## 6 · Coste nocturno y MCP

- Ingesta: **nada nuevo**. `com`, `comlin`, `comprv`, `dco`, `dcopro`, `confir`,
  `conest`, `auxpronat`, `ctrpro`, `con` ya están en `raw` (tamaños en Azure:
  `dcopro` 378 MB / 794.556, `con` 422 MB, `ctrpro` 117 MB, `dco` 50 MB,
  `comlin` 25 MB, `confir` 16 MB, `comprv` 8 MB, `com` 3 MB).
- Build: la agregación de ofertas con sus líneas (`comprv`⨝`dco`⨝`con` +
  `dcopro` agrupado) tarda **10,1 s** en Azure. Estimación: Fase 1 < 1 min y
  < 30 MB (dos tablas de 20 k y 71 k filas); Fase 2 +1 a 2 min y ~150 MB (las
  ~787 k líneas de oferta son el grueso). Hoy `build-compras` va por ~4-7 min;
  margen de ventana declarado en F-085: 19 min.
- MCP: `compras` YA está en `esquemas_permitidos` de `mcp-bbdd/config/config.yaml`
  (línea 165). No hay que cambiar nada allí; solo **reiniciarlo** tras publicar el
  diccionario (cachea las fichas).

## 7 · Decisiones para el humano (con recomendación)

- **D1 · ¿Una entrega o dos?** Recomiendo **dos fases**. Fase 1: comparativo y
  ofertas con las cuatro magnitudes, el ahorro, las ficticias marcadas, el
  contrato, estado, actividad y fecha de aprobación (acceptance 2, 3, 4, 6, 7, 8,
  11, 12, 13 salvo el escalón). Fase 2: coste objetivo con su % y su base, las
  líneas de los dos lados (precio unitario de cada proveedor) y las firmas por
  escalón (acceptance 5, 9, 10). La Fase 1 no depende de D2 ni de D3.
- **D2 · ¿Qué es «ABC» en «el objetivo sobre el ABC; si no hay, sobre OT»?**
  Recomiendo: **cualquier oferta de planificación** (ABC, PLANIFICACIÓN,
  CUATRIMESTRAL, FASE 0), porque «ABC» literal solo está en 283 comparativos. La
  base se publica **observada** (la familia cuya oferta × (1 − %) da el
  objetivo) y la regla solo desempata cuando las dos casan (18.740 líneas).
- **D3 · ¿Las firmas por escalón aquí o en F-085?** Recomiendo **aquí, en Fase
  2**, como proyección fiel de `confir` tip 46 (una fila por firma, 66 k), que
  F-085 consumirá o absorberá al unificar familias. Si se dejan a F-085, el
  acceptance 5 pasa allí salvo la fecha de aprobación y quién cerró el circuito.

Ya decidido y NO se reabre: las cuatro magnitudes con nombre propio, todas las
ofertas con las ficticias marcadas, la regla ABC→OT. Decidido en la spec por
regla del datamart: los importes son **sin IVA** (`dco.totbas`, no `totdoc`).
