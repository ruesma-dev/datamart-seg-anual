<!-- progress/spec_F-123.md -->
# F-123 · Resumen de la spec, mediciones y decisiones abiertas

Spec: `specs/F-123-descompuestos-regla-origenes/` (requirements 29 requisitos,
design, tasks T1-T22). Todo medido el **2026-10-02** en solo lectura contra el
datamart de Azure por el MCP (diccionario v39, sello `7cad480aee614b2a`, 3.025
versiones cargadas en 197 obras). No se ha leído Sigrid ni escrito en ningún
sitio salvo este repositorio. `bash harness/init.sh` no se relanzó (verde hoy
antes de empezar, 6.251 passed; esta entrega solo añade Markdown).

## 0 · En una frase

El master 0 pasa a llamarse `MASTER_ESTUDIO` y ES Estudios; la «Descomposición»
de coste fase 0 deja de publicarse salvo como `ESTUDIO_RESPALDO` en las 44 obras
sin master 0; una tabla nueva, `descompuestos.estudios_partida`, dice partida a
partida de dónde sale Estudios o por qué no existe; y el diccionario gana la
regla `R-FASE-VIVA`.

## 1 · Foto de hoy (el «antes» de T16)

| Origen | Líneas | Obras | Partidas | Versiones |
|---|---|---|---|---|
| ESTUDIO | 99.049 | 174 | 35.523 | — |
| PLANIF_JO | 288.960 | 246 | 111.392 | — |
| MASTER_INICIAL | 107.061 | 170 | 36.355 | 170 |
| MASTER_PRE_ABC | 1.794.624 | 173 | 76.931 | 1.665 |
| MASTER_PLANIF_JO | 2.497.224 | 59 | 45.233 | 1.190 |

Cuadre (`origen`: CUADRA / NO_CUADRA / SIN_DESCOMPUESTO / SUSTITUIDO):
ESTUDIO 9.433 / 20.786 / 113.428 / 5.923 (149.570 filas) · PLANIF_JO 79.692 /
14.776 / 55.102 · MASTER_INICIAL 34.174 / 675 / 54.299 · MASTER_PRE_ABC 635.328 /
11.812 / 368.250 · MASTER_PLANIF_JO 792.922 / 12.301 / 246.232.

## 2 · Las 35.523 partidas con ESTUDIO, por lo que tiene su obra y su partida

| La obra | La partida en el master 0 | Partidas | Obras |
|---|---|---|---|
| con master 0 (130 obras) | con descompuesto | 26.959 | 128 |
| con master 0 | con precio y SIN descompuesto | 249 | 7 |
| con master 0 | con precio 0 | 13 | 4 |
| con master 0 | NO ESTÁ en el master 0 | 1.758 | 21 |
| con master, sin versión 0 con descompuesto (0713) | — | 1.863 | 11 |
| sin ningún master cargado | — | 4.681 | 33 |

- **Diferencia con lo medido por el líder** (25.799 / 249 / 9.475, 45 obras): yo
  cuento parejas (obra, partida) con LÍNEAS en `descompuestos.lineas` y me salen
  26.959 con master 0 y 8.564 sin él, en 44 obras sin master 0. El líder contó
  probablemente contra el cuadre (solo hojas con precio). Las 33 obras sin
  ningún master coinciden. No cambia ninguna conclusión; valen las de esta tabla
  porque el respaldo se publica por líneas.
- **Donde hay los dos, son lo mismo**: de las 26.959, 26.849 tienen el mismo
  número de líneas, 26.915 la misma suma por unidad y **26.833 (99,5 %) las dos
  cosas**. `ESTUDIO` no aporta nada donde hay master 0.
- **Pero su cuadre no**: en obras con master 0, ESTUDIO es NO_CUADRA en 18.132
  partidas y CUADRA en 6.723 (el precio de la fase viva ya se ha movido);
  MASTER_INICIAL, 34.174 CUADRA y 675 NO_CUADRA. Es la prueba de que la fase viva
  no es Estudios.
- **Lo que gana Estudios**: 9.396 partidas tienen master 0 con descompuesto y hoy
  NO tienen ESTUDIO (36.355 − 26.959). Entre las hojas con precio de la fase
  viva: 5.303 que hoy son SIN_DESCOMPUESTO y 1.401 SUSTITUIDO pasan a tener
  Estudios por el master 0.

## 3 · Previsión del «después», según D1

| | Por OBRA (recomendado) | Por PARTIDA |
|---|---|---|
| `MASTER_ESTUDIO` | 36.355 partidas, 170 obras, 107.061 líneas | igual |
| `ESTUDIO_RESPALDO` | **6.544 partidas, 44 obras, 11.783 líneas** | 8.564 partidas, 44 obras + hasta 30 con master 0 |
| Estudios en total | 42.899 partidas en 214 obras | 44.919 |
| Dejan de publicarse (eran ESTUDIO) | 2.020 partidas: 1.758 que no están en el master 0, 249 sin descompuesto en él, 13 con precio 0 | 0 |
| Cuadre `ESTUDIO_RESPALDO` | 51.206 filas (2.710 CUADRA, 2.654 NO_CUADRA, 45.739 SIN_DESCOMPUESTO, 103 SUSTITUIDO) | 149.570 como hoy |

Hoy `v_pbi_estudio` tiene 35.523 partidas en 174 obras; con la regla nueva,
42.899 en 214 (por obra).

## 4 · Las mediciones del master (punto 1 del humano, R29)

`sum(importe_total)` de las líneas frente a `stg.presupuesto.importe` de la misma
fila, en las partidas CUADRA:

| Qué | Partidas CUADRA | A 5 céntimos | Al 1 por mil (mín. 1 EUR) |
|---|---|---|---|
| Master 0, todas las obras | 34.174 | 26.534 (77,6 %) | 33.076 (96,8 %) |
| 0713 · Cuatrimestral (1 versión) | 1.872 | 1.724 | 1.861 (99,4 %) |
| 0713 · ABC (2) | 3.713 | 3.489 | 3.705 (99,8 %) |
| 0713 · Planif Inicial (1) | 1.849 | 1.755 | 1.847 (99,9 %) |
| 0713 · Cierre mensual (6) | 10.766 | 9.843 | 10.658 (99,0 %) |
| 0726 · Cierre mensual (2) | 2.498 | 2.390 | 2.466 (98,7 %) |

Las diferencias de céntimos son el redondeo línea a línea. **No he podido medir
el master entero por `tipo_version`**: la consulta sobre los 4,4 M de líneas la
corta el tiempo máximo del MCP (dos intentos). Queda como T20, por `psql`:

```sql
WITH s AS (SELECT presupuesto_id, min(tipo_version) AS tipo_version, sum(importe_total) AS suma
           FROM descompuestos.lineas WHERE ambito_id = 8 GROUP BY 1)
SELECT s.tipo_version, count(*) AS cuadra,
       count(*) FILTER (WHERE abs(s.suma - p.importe) <= greatest(1, abs(p.importe) * 0.001)) AS coincide
FROM s JOIN descompuestos.cuadre_partida c ON c.presupuesto_id = s.presupuesto_id
                                          AND c.ambito_id = 8 AND c.estado = 'CUADRA'
JOIN stg.presupuesto p ON p.presupuesto_id = s.presupuesto_id GROUP BY 1 ORDER BY 1;
```

## 5 · Testigos

- **0726** (obra 2817778), partida 419079: 10 líneas y 134,35 por unidad en
  ESTUDIO, en MASTER_INICIAL (v0) y en MASTER_PRE_ABC (v1). Sus 1.305 partidas con
  ESTUDIO son las mismas 1.305 del master 0. Después: solo `MASTER_ESTUDIO`.
- **0713** (obra 2645007): 10 versiones cargadas, **ninguna es la 0**. 687
  partidas y 1.774 líneas ESTUDIO. Después: las mismas como `ESTUDIO_RESPALDO`.

## 6 · Decisiones abiertas (recomendación en negrita)

- **D1 · El respaldo, por obra o por partida.** **Por OBRA**: se publica solo en
  las obras sin master 0 (44 obras, 6.544 partidas). Por partida añade 2.020, de
  las que 1.758 son partidas que NO EXISTÍAN en el master 0: se crearon después
  en la fase viva, y publicarlas como Estudios sería falso. Coste de la
  recomendación: esas 2.020 dejan de tener líneas publicadas (el texto sigue en
  `_des_texto`) y salen en `estudios_partida` como `NO_EXISTE` con su motivo. La
  frase del humano («si en el master 0 no hay») admite las dos lecturas: decide él.
- **D2 · Con qué origen sale el respaldo, y `SUSTITUIDO_POR_PLANIFICACION`.**
  **Origen `ESTUDIO_RESPALDO`**, con ámbito 3 y fase 0 (de donde sale de verdad):
  el nombre dice que no es el master 0 y las fichas avisan de que su cantidad e
  importe total siguen la medición VIVA. `ESTUDIO` desaparece como origen.
  **El estado se conserva, solo en las filas `ESTUDIO_RESPALDO` del cuadre**
  (obras sin master 0), y además es un motivo de `NO_EXISTE`. Alternativas:
  conservar el nombre `ESTUDIO` (rompe menos a Juan, pero el mismo nombre pasaría
  a significar otra cosa) o `ESTUDIO_FASE_VIVA`.
- **D3 · Cómo se informa de que no existe.** **Tabla nueva
  `descompuestos.estudios_partida`**: una fila por partida con `via_estudios`
  (`MASTER_ESTUDIO`, `ESTUDIO_RESPALDO`, `NO_EXISTE`) y `motivo_no_existe`
  (`MASTER_0_SIN_DESCOMPUESTO`, `PARTIDA_FUERA_DEL_MASTER_0`,
  `SUSTITUIDO_POR_PLANIFICACION`, `SIN_DESCOMPUESTO`), con ficha de consumo.
  Alternativa barata: solo el cuadre (estado `SIN_DESCOMPUESTO` del origen que
  toque), pero entonces las partidas de la fase viva que no están en el master 0
  no tienen fila en ningún sitio y hay que saber en qué origen mirar.
- **D4 · Power BI.** **`v_pbi_estudio` pasa a ser Estudios ya resuelto**
  (`MASTER_ESTUDIO` + `ESTUDIO_RESPALDO`), con las 21 columnas de hoy y `origen`
  al final: no se rompe ningún informe y la cantidad pasa a ser la de Estudios
  donde hay master 0. **`elementos` renombra dos columnas**: `lineas_estudio` ->
  `lineas_estudio_respaldo` y `lineas_master_inicial` -> `lineas_master_estudio`
  (esto SÍ rompe a quien las lea por nombre). Alternativa: una vista nueva
  `v_pbi_master_estudio` y dejar `v_pbi_estudio` solo con el respaldo.
- **D5 · Despliegue.** **El sello cambia sin remedio** (el literal del origen
  está en `03_lineas_master.sql`): las 3.025 versiones quedan pendientes aunque
  el retroceo dé las mismas líneas. El «cambio barato» del bloque 5 no basta por
  sí solo, pero la migración de `02` deja el origen bien la primera noche, así
  que lo publicado no depende del retroceo. **Recomendado, como F-120: imagen
  primero y después `build-descompuestos --sin-tope` + `apply-grants` a mano**
  (27 min medidos en F-120: 1.619 s). Alternativa válida: dejar que la nocturna
  lo absorba en 8-11 noches. El orden imagen -> build es obligatorio: la imagen
  vieja fallaría contra el `CHECK` nuevo.
- **D6 · Diccionario.** **Versión 40.** **Regla nueva `R-FASE-VIVA`** (texto
  propuesto abajo), `R-DESCOMPUESTO-ORIGEN` reescrita, y `R-FAS-AMBIGUO` y
  `stg.yaml` remiten a ella donde dicen «Previsto vivo». No afirma nada de la
  fase 0 de VENTA: el humano habló de coste. ¿Severidad `bloqueante`?
  Recomiendo que sí, como las demás de lectura.
- **D7 · Aviso a Juan Romero** (y Elena Díaz), ANTES de desplegar (T15). Texto
  propuesto abajo. Corrige de paso lo de `MASTER_INICIAL` del correo del 01-10.
- **D8 · Las 2.020 partidas de D1**: si el humano elige por obra, ¿le vale que
  desaparezcan de `lineas`? Si las quiere ver, la salida es por partida (D1) y
  no un tercer origen.

### Texto propuesto de `R-FASE-VIVA` (D6)

> **Coste fase 0 es la FASE VIVA, no una foto.** En el ámbito 3 (COSTE),
> `fase_num = 0` no es un mes: es el presupuesto de coste en curso, el que el jefe
> de obra va evolucionando día a día (mediciones, precios, partidas nuevas). Es lo
> que otras fichas llaman «Previsto vivo». No guarda historia: lo que se lee hoy
> es el estado de hoy. Las fotos fijas son las versiones del master (ámbito 8): la
> 0 es Estudios (`MASTER_ESTUDIO`) y las demás, los cierres. El descompuesto de la
> fase viva es la planificación de compras del jefe de obra (`PLANIF_JO`); su
> pestaña «Descomposición» no se publica como descompuesto de esa fase, y solo
> sirve de respaldo de Estudios (`ESTUDIO_RESPALDO`) en las obras sin master 0.
> Nunca se compara la fase viva con Estudios como si fueran la misma medición.

Motivo, con lo medido: 1.758 partidas con descompuesto en la fase viva no existen
en el master 0, y en las obras con master 0 la «Descomposición» de la fase viva
cuadra con su precio en 6.723 partidas y no en 18.132.

### Texto propuesto del aviso (D7)

> Cambia la lectura de `descompuestos.lineas` (fecha: la del despliegue).
> `MASTER_INICIAL` pasa a llamarse `MASTER_ESTUDIO`: es Estudios, con la medición
> de Estudios. `ESTUDIO` desaparece: donde la obra tiene master 0, Estudios es
> `MASTER_ESTUDIO`; donde no lo tiene (la 0713), sale como `ESTUDIO_RESPALDO`,
> con precios de Estudios y medición de hoy. La vista `v_pbi_estudio` ya da la
> que toque, con una columna `origen`. Si filtráis por el nombre antiguo
> recibiréis 0 filas sin error. `descompuestos.estudios_partida` dice, por
> partida, de dónde sale Estudios o por qué no existe. `PLANIF_JO` y los otros
> dos orígenes del master no cambian.

## 7 · Avisos para el implementer y el reviewer

- `02` corre antes que `03`: por eso el respaldo se decide contra
  `_versiones_cargadas` y no contra `lineas` (design §4).
- La tabla `lineas` persiste: los `CHECK` no se cambian con `CREATE TABLE IF NOT
  EXISTS`, hace falta la migración (R19-R20).
- Los comentarios de `00` y `01` entran en el sello: tocarlos en el mismo commit
  que `03`.
- `test_f120_factor.py` fija la versión 39 y el texto de la nota D7 de F-120:
  hay que reescribirlos, no borrarlos.
- El MCP cachea el diccionario: sin reiniciarlo seguirá sirviendo la v39.

## 8 · Lo que queda MANUAL del humano

T15 aviso · T16 foto de antes · T17 imagen · T18 build `--sin-tope` +
`apply-grants` · T19 foto de después y testigos · T20 medición de R29 por `psql`
· T21 `publicar-diccionario` (v40) y reinicio del MCP.
