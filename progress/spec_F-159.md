<!-- progress/spec_F-159.md -->
# F-159 · Hotfix 2: un mes negativo del plan de V se amplifica y tumba `build_tesoreria`

Spec-author, 2026-11-07 (09:25-11:50 UTC, fuera de 00:00-05:00). Todo en SOLO LECTURA contra Azure
(`filas_solo_lectura`, `READ ONLY`), con el código y el `.env` del checkout principal sin tocar
ningún fichero suyo; nada escrito. Sin código: va a la PARADA 1. Rama
`feature/F-159-hotfix-devengo-negativo-2` desde `main` `93fc38c`, en el worktree del agente. Spec
en `specs/F-159-hotfix-devengo-negativo-2/`.

## 1. El síntoma

Nocturna del 07-11 (imagen r20261106-1848, con F-158): `build_tesoreria` FAILED a las 04:52 y a
las 06:30 UTC, en `devengo_pendiente`: «el coste por contrato no cuadra con la obra-mes en 0 obras
o tiene 1 importes negativos» (R50 de `sql/tesoreria/07_devengo_pendiente.sql`). El resto de la
noche terminó (compras, contabilidad, cierre, diccionario: SUCCESS). `tesoreria` sigue con la
construcción del 06-11 08:38 (la manual de F-158).

## 2. La fila negativa (reproducida)

Reproducción en una sola `WITH` de los pasos 2, 3, 2 bis, 2 quinquies, 4, 5 y 5 bis de `07`
(rama de `main`, con F-158), solo COSTE, con la V de las 23 obras de hoy fijada por `VALUES` (paso
1 aparte: 102 s; el resto, 15 s). Da exactamente UNA fila negativa del agregado, la del error:

| obra | clave | mes | categoría | contrato | importe | partidas |
|---|---|---|---|---|---|---|
| 2605958 | 1-0710 | 2026-11 | CD | (sin contrato) | **-18.791.769,87** | 496 |

No son céntimos. Sale casi entero de la partida **404326 (03.02.11)**, V=13, cierre 2026-10:
`pendiente` 1.080,00, cuota de personal 0. Su plan de V tras el cierre es **2026-11: -1.079,94 y
2026-12: +1.080,00**, así que `total_perfil` = **0,06**. El paso 5 reparte en proporción con pesos
CON SIGNO: noviembre = `ROUND(1080 × -1079,94 / 0,06, 2)` = **-19.438.920,00** y diciembre absorbe
**+19.440.000,00**. Suma 1.080,00: R14 pasa; el paso 5 bis manda el negativo entero sin contrato
(T39 bis) y R50 lo caza. El mes del plan viene del `planif` de V13 en Sigrid:
`…|0|0.99994317|0|1|0…` (octubre 99,994 %, noviembre **0**, diciembre 100 %): un 0 INTERMEDIO,
que `stg/08_plan_mensual.sql` (caso B, validado contra Sigrid) trata como estorno.

Los 19 (partida, mes) con pendiente negativo de hoy, todos con personal 0 (no es el personal):

| obra | partidas | (partida, mes) negativos | peor |
|---|---|---|---|
| 1-0710 | 15 | 15 | 404326 2026-11 -19.438.920,00; 404744 -43.589,16 (pendiente 10.897,24, perfil 2.179,44) |
| 1-0678 | 2 | 3 | 407428 -4,07 (2026-12 y 2027-03); 370538 -0,56 |
| 1-0702 | 1 | 1 | 387660 2026-11 -0,11 (la de D2 de F-158, ahora en V21) |

Solo la de 1-0710 deja negativo el agregado: las demás se compensan en su (obra, mes, categoría).

## 3. ¿Es un borde ya declarado?

- **Es la clase de la D2 de F-158** (mes negativo del plan de V), **pero en una forma nueva y
  mucho peor**: no un céntimo que se cuela, sino la **amplificación**. Con pesos con signo, si los
  meses negativos casi anulan a los positivos, `total_perfil` tiende a 0 y cada mes recibe
  `pendiente × plan_mes / total_perfil`: millones positivos y negativos que solo suman bien al final.
  Máximo de hoy: un mes = **18.000 veces** el pendiente de su partida.
- **No es la observación 3** de `review_F-158.md`: 0 últimos meses negativos hoy. Pero está
  latente: con pesos ≥ 0 y el resto al último mes, el último mes mínimo es **0,00** y el desvío del
  último mes llega a **0,105 €**; basta un último mes de plan pequeño en una partida larga.
- **Alcance de la clase hoy.** COSTE: 353 (partida, mes) negativos en el perfil, 108 partidas, 10
  obras; 19 de ellas con pendiente > 0 (en 1-0678, 1-0702 y 1-0710). 102 partidas con
  Σ|plan| / Σplan > 1,5 o perfil neto negativo (máximo 35.999). VENTA: 12 obras con meses
  negativos; en 1-0710, 17 partidas, 15 amplificadas (máximo 50.833). **La venta no tiene R50**:
  su obra-mes publicaría los mismos millones sin que nada falle.

## 4. Por qué hoy (del 06-11 al 07-11)

En Sigrid se crearon el **2026-11-06** tres versiones «PLANIFICACION CUATRIMESTRAL OCT-26» (fecha
efectiva 2026-10-01), que la ingesta del 07-11 trajo: **1-0710 V13** (era V8, de 2026-06),
1-0702 V21 (era V16) y 1-0676-B V26 (era V22; su VENTA entra hoy en el universo: 23 obras en
venta frente a 22). La V13 de 1-0710 trae el `planif` con el 0 intermedio de 404326 y quince partidas más con
meses negativos tras el cierre. Dato legítimo de Sigrid (el estorno es la regla validada); el fallo
es del reparto, que no soporta pesos con signo.

## 5. Alternativas (medidas en solo lectura sobre los datos de hoy, COSTE)

Base: 48.577 (partida, mes) repartidos en 12.737 partidas.

- **A (recomendada). Perfil = ENVOLVENTE NETA + reparto por ACUMULADO.** El mes negativo se
  absorbe en los meses anteriores: con `W(m)` el plan acumulado tras el cierre, el peso acumulado es
  `W'(m) = max(0, min_{k ≥ m} W(k))` (no decreciente, acaba en `total_perfil`). Cada mes recibe
  `A(m) - A(m-1)`, con `A(m) = ROUND(p × W'(m) / total_perfil, 2)` y `A(último) = p`. El personal
  (F-158) no cambia: sigue por acumulado sobre ese pendiente. Por construcción, con `p` ≥ 0: cada
  mes ≥ 0, la suma es `p` exacta y ningún mes supera `p`. **Medido: 0 meses negativos, 0 personal
  fuera de [0, mes], 0 sumas descuadradas, 0 agregados negativos, 0 obras descuadradas en R50.**
  404326: todo (1.080,00) a 2026-12. Cambian 3.090 (partida, mes): en 1-0710, lo absurdo; fuera de
  1-0710, 53,10 € en total; en las partidas sin meses negativos, 3.040 filas de ≤ 0,11 € (el
  redondeo por acumulado reparte el resto que hoy se queda el último mes).
- **P. Solo los meses positivos** (`importe_mes > 0`, la línea que F-158 D2 ofrecía). También 0
  negativos y 0 descuadres, pero cuenta lo anulado como actividad: un `100 % → 0 → 100 %` futuro
  pone la mitad en el mes que luego se estorna. Difiere de A en 11 partidas, 42 filas, 4.639,30 €.
- **A sin acumulado** (envolvente y resto al último mes). Cambia menos filas, pero deja abierto el
  borde de la observación 3 (último mes mínimo hoy 0,00). Descartada: no cierra la clase.
- **B. Recortar en 5 bis** (`GREATEST(0, importe_np)`). Descuadra R50 y deja publicados en la
  obra-mes ±19 M€ en noviembre y diciembre. Descartada.
- **C. Relajar R50** (permitir negativos sin contrato). La noche pasa y publica -18,8 M€ de coste
  sin contrato en 1-0710/2026-11 (H02 lo volvería un cobro), +19,4 M€ en diciembre y lo mismo en
  la venta. Peor que no publicar: hoy `tesoreria` está un día atrasada pero correcta
  (`R-FRESCURA`). Descartada también como parche.

## 6. Tests de regresión (sin red ni BBDD)

Dominio: `repartir_pendiente` con la envolvente y el acumulado; el caso REAL de 404326 (perfil
-1.079,94 / +1.080,00, pendiente 1.080,00) con su RED documentado (-19.438.920,00 con el
algoritmo de `93fc38c`, escrito como copia privada en el test); invariantes con semilla fija y
perfiles con signo (cada mes ≥ 0, suma exacta, ninguno > `p`, personal en [0, mes]); y los casos de
F-140 que cambian de céntimo (100/3 → 33,33 / 33,34 / 33,33). SQL sobre el texto de `07`: la
envolvente, el acumulado y la guarda nueva. Detalle: `design.md` §5.

## 7. Decisiones abiertas para el humano

- **D1.** Forma del perfil: **A, envolvente neta (recomendada)** o P, solo meses positivos.
- **D2.** Redondeo: **por acumulado (recomendado, cierra la observación 3)** o resto al último mes.
- **D3.** Diagnóstico: **guarda nueva en el paso 5** (ningún mes negativo ni personal fuera de
  rango, con obra, partida y mes en el mensaje) **y R50 nombra su primera fila negativa**, con su
  condición intacta (recomendado), o dejar las guardas como están.
- **D4.** Hasta el despliegue: **dejar `tesoreria` con lo del 06-11 (recomendado)**; la nocturna
  seguirá fallando solo en `build_tesoreria`. La alternativa C como parche queda descartada (§5).
- **D5.** Diccionario: `main` lleva la **v73** (F-157); F-159 sube a **v74** (fichas de
  `importe_pendiente` y de `devengo_pendiente_contrato_mes`).
- **D6.** Sin sandbox PostgreSQL (rigor `estandar`, como F-158); la reproducción en solo lectura
  antes del despliegue es la verificación MANUAL (`design.md` §6, paso 0 bis).

`bash harness/init.sh` en este worktree: ver `progress/current.md` (rojo esperado solo por el `.env`).
