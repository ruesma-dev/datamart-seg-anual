<!-- progress/spec_F-158.md -->
# F-158 · Hotfix: un céntimo negativo en el coste por contrato tumba `build_tesoreria`

Spec-author, 2026-11-05 (11:10-11:40 UTC, fuera de 00:00-05:00). Todo en SOLO LECTURA contra
Azure (`filas_solo_lectura`, `READ ONLY`); nada escrito. Sin código: va a la PARADA 1.
Rama `feature/F-158-hotfix-devengo-negativo` desde `main` `fbf43dd`, en el worktree del agente.
Spec en `specs/F-158-hotfix-devengo-negativo/`.

## 1. El síntoma

Nocturnas del 04-11 y del 05-11: `build_tesoreria` falla en `devengo_pendiente` con «el coste por
contrato no cuadra con la obra-mes en 0 obras o tiene 1 importes negativos»: la guarda R50 de
`sql/tesoreria/07_devengo_pendiente.sql` (F-150 N17). La transacción entera vuelve atrás: las
cinco tablas de `07` siguen siendo las del 03-11 (última `build_tesoreria` SUCCESS: 03-11 03:02 UTC).

## 2. La fila negativa (reproducida)

Reproducción en una sola `WITH` de los pasos 2, 3, 2 bis, 2 quinquies, 4, 5 y 5 bis de `07`, solo
COSTE, con la versión V de las 21 obras fijada por `VALUES` (el paso 1, 151 s, se midió aparte;
el resto, 14 s). Da exactamente UNA fila negativa del agregado, la del error:

| obra | clave | mes | categoría | contrato | importe | partidas |
|---|---|---|---|---|---|---|
| 2563363 | 1-0707 | 2027-10 | CI | (sin contrato) | **-0,05** | 10 |

Viene de la partida **392521 (CI.1.1)**, V=16, `mes_version` = `mes_ultimo_cierre` = 2026-10:
`pendiente` 57.749,95; real a origen 23.850,02; partes de personal 23.850,00 → `cuota_personal`
= `ROUND(23850,00/23850,02, 6)` = **0,999999** → `pendiente_personal` = 57.749,89 (0,06 menos).
Perfil de 12 meses (2026-11 a 2027-10, plan 3.264 / 4.896 / 8.976 / 8.160 / 4.080).

## 3. Por qué: dos repartos redondeados por separado

El paso 5 (`_dev_reparto`) reparte `pendiente` y `pendiente_personal` **cada uno por su lado**
(`ROUND(x * plan_mes / total_perfil, 2)` y el resto al ÚLTIMO mes). Con una cuota de 0,999999, en
los 11 primeros meses el personal sale 0,01 por debajo del pendiente (3.300,00 frente a 3.299,99,
etc.): 0,11 en total. Pero a nivel de partida la diferencia es solo 0,06. El último mes absorbe
los dos restos y se invierte: **pendiente 8.249,97, personal 8.250,02**. El paso 5 bis reparte
`importe_np = pendiente - personal` = **-0,05**; como no es > 0, va entero a la fila sin contrato.
Reproducido con el dominio (`repartir_pendiente` dos veces) con los mismos céntimos.

Es un **fallo del reparto, no un dato legítimo de Sigrid**: no hay abono ni devolución; los dos
importes son positivos y el negativo es aritmética de redondeo. Hay más casos latentes hoy (siete
(partida, mes) con `importe_np` entre -0,01 y -0,06 en 1-0694, 1-0707, 1-0713, 1-0719 y 1-0724),
todos de cuota 0,999998-0,999999; seis quedan tapados porque suman con otros restos sin contrato
del mismo (obra, mes, categoría). 187 partidas tienen cuota 1 (sin riesgo: los dos repartos son
idénticos) y 83, cuota en (0, 1).

**Por qué saltó el 04-11 y no antes.** El 03-11 la misma partida ya tenía el -0,05, compensado en
la fila sin contrato de 1-0707/2027-10/CI (16,60 €, publicada así). Entre el 03 y el 04 entraron
partes de octubre en la partida 392522 (CI.1.2): su personal pasó de 90.320,85 a 91.068,43, cuota
1, y su resto sin contrato (que hacía de colchón) se fue a 0. Dato legítimo que destapa el fallo.

El otro negativo de la reproducción, 1-0702/387660/2026-11 (-0,11), es distinto: un mes NEGATIVO
del plan de V (ya documentado en F-150, T39 bis). Hoy se compensa; ver D2.

## 4. Alternativas

- **A (recomendada). Repartir el personal sobre el pendiente ya repartido, por ACUMULADO.** En
  `_dev_reparto`, el personal del mes = `ROUND(pp * acum / p, 2) - ROUND(pp * (acum - imp) / p, 2)`,
  con `p` el pendiente de la partida, `pp` su personal, `imp` el pendiente del mes y `acum` el
  acumulado hasta ese mes (orden de mes). Es el mismo patrón que `repartir_por_contratos`. Con
  `pp ≤ p` (cuota ≤ 1) garantiza en cada mes de importe ≥ 0: `0 ≤ personal ≤ pendiente`, y la suma
  es `pp` exacta (telescópica). **Medido en solo lectura sobre los datos de hoy:** 0 filas
  negativas en el agregado, 0 meses con personal fuera de [0, pendiente], 0 partidas con la suma
  descuadrada; cambian 89 (partida, mes) en ≤ 0,06 € (1,20 € en total). La guarda R14 (suma por
  partida) y la R58 (dos tramos) no cambian. Queda solo el -0,11 de 1-0702 (D2).
- **B. Recortar en el paso 5 bis**: `GREATEST(0, importe_np)`. Descuadra la obra-mes (la otra
  mitad de R50) por los céntimos recortados. Descartada.
- **C. Relajar la guarda R50** a solo las filas con contrato. La nocturna pasa, pero se publica
  -0,05 de coste sin contrato (H02 lo convertiría en un cobro): esconde el fallo. Descartada,
  salvo como parche de emergencia si A no llegase.
- **D. Recortar el personal del mes a su pendiente y llevar el exceso al mes anterior.** Correcto
  pero más código y otra regla que explicar; A lo resuelve por construcción. Descartada.

## 5. Tests de regresión (sin red ni BBDD)

- Dominio, nueva `repartir_personal(reparto, pendiente, pendiente_personal)` en
  `etl_sigrid/domain/proyeccion_caja.py`: el caso REAL de 392521 (12 meses, 57.749,95 / 0,999999)
  con su RED documentado (el algoritmo de hoy da 8.249,97 / 8.250,02); invariantes con
  semillas fijas (cuota en [0, 1], perfiles de 1 a 24 meses): `0 ≤ personal ≤ pendiente`, suma
  exacta; cuota 1 → personal = pendiente; cuota 0 → ceros; sin perfil → una fila.
- SQL, sobre el texto de `07`: la fórmula por acumulado, la ventana `ORDER BY anio_mes` y que
  `repartido` ya no reparte el personal por `ROUND(d.pendiente_personal * pr.importe_mes ...)`.
  `test_f150_r46_el_reparto_lleva_la_parte_de_personal` fija hoy la fórmula del fallo: se
  actualiza sin borrar lo que defiende (el último mes absorbe el redondeo del pendiente).
- Opcional (D4): sandbox con PostgreSQL desechable, como F-155, sobre el bloque `_dev_reparto`.

## 6. Diccionario

`importe_pendiente_personal` de `devengo_pendiente_obra_mes` dice «(el mismo reparto)»: pasa a
«repartido por acumulado sobre `importe_pendiente`: nunca lo supera en un mes». La ficha de
`devengo_pendiente_contrato_mes` gana que la fila sin contrato solo es negativa por un mes
negativo del plan. Versión: `main` lleva la **v71** (F-156) SIN publicar; F-158 sube a **v72** (D3).

## 7. Decisiones abiertas para el humano

- **D1.** Alternativa A (recomendada) o C como parche inmediato.
- **D2.** El mes negativo del plan (1-0702, -0,11): hoy compensa y A no lo toca. ¿Se deja como
  está (recomendado: es dato del plan y F-150 ya lo trata) o se excluye del perfil (`> 0` en vez
  de `<> 0`), que cambia D19-A de F-140?
- **D3.** Diccionario: v72 tras publicar la v71 de F-156 (recomendado), o desplegar F-158 sin
  ficha y llevarla con la siguiente publicación.
- **D4.** Sandbox SQL (rigor `estandar` sin sandbox, como el resto de F-150) o con ella.
- Despliegue: los pasos MANUAL están en `design.md` §6, con la vuelta atrás a `fbf43dd`.
