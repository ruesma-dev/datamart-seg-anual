<!-- specs/F-120-factor-descompuesto/requirements.md -->
# F-120 · Requisitos

El campo 14 del registro `~D|` no es el rendimiento: es «factor x rendimiento».
F-097 solo aceptaba un número y dejaba sin rendimiento ni importe unitario las
líneas con factor, y su cuadre salía NO_CUADRA sin serlo. La planificación de
compras (`dncpro`) guarda el mismo factor en columnas propias, que F-097 tampoco
aplicaba. Mediciones (2026-10-01, solo lectura) y decisiones D1-D10 con su
recomendación: `progress/spec_F-120.md`. Los requisitos marcados **[Dn]**
siguen la recomendación de esa decisión; si el humano decide otra cosa, cambian.

## Glosario

- **Campo 14**: posición 14 (base 0) del registro, `split_part(reg, '|', 15)`.
- **Número**: lo que casa con `PATRON_NUMERO` de `domain/descompuestos.py`.
- **Forma factor**: `<número>x<número>` o `<número>x` (rendimiento vacío), con
  `x` minúscula y sin blancos dentro; el patrón `PATRON_FACTOR_RENDIMIENTO`.
- **Retroceo**: volver a trocear desde `descompuestos._des_texto` una versión
  del master ya cargada, sin releerla de Sigrid.

## Lectura del campo 14 (troceado SQL y espejo Python)

- **R1.** CUANDO el campo 14, sin blancos de los extremos, es un número, el
  sistema debe publicar `factor = 1` y `rendimiento` = ese número.
- **R2.** CUANDO el campo 14 tiene la forma factor `a x b`, el sistema debe
  publicar `factor = a` y `rendimiento = b`, cada uno con su signo (medido:
  `0.99765x-0.15`, `-1x1`, `-1.27x0.001`).
- **R3.** CUANDO el campo 14 tiene la forma `a x` (rendimiento vacío), el
  sistema debe publicar `factor = a` y `rendimiento` NULL.
- **R4.** [D1] SI el campo 14 está vacío, ENTONCES el sistema debe publicar
  `factor` y `rendimiento` NULL.
- **R5.** [D2] SI el campo 14 no está vacío y no es un número ni una forma
  factor, ENTONCES el sistema debe publicar `factor` y `rendimiento` NULL y el
  build no debe fallar (sigue valiendo R14 de F-097).
- **R6.** El sistema debe calcular `importe_unitario = ROUND(precio x factor x
  rendimiento, 2)`, NULL si falta alguno de los tres o si no cabe en
  NUMERIC(18,2), con el mismo tope que hoy (`LIMITE_IMPORTE`).
- **R7.** El sistema debe seguir calculando `importe_total = ROUND(cantidad_total
  x precio, 2)` sin aplicar el factor: el campo 4 ya lo incluye (0713, partida
  400854, v6: 1091,5 x 1,00021 x 1 = 1091,729).
- **R8.** [D6] En los tipos 4 y 13 (porcentajes), `porcentaje` debe seguir siendo
  `rendimiento x 100`, sin el factor, y `importe_unitario` debe llevar el factor
  como cualquier otra línea (R6).
- **R9.** Un factor 0 es un factor, no una ausencia: `0x1` debe publicar
  `factor = 0` e `importe_unitario = 0,00` si hay precio (D5).
- **R10.** El espejo `trocear_des` debe aplicar R1-R9 con la misma regla, y una
  función pura `factor_rendimiento(texto)` debe devolver `(factor, rendimiento)`.
- **R11.** El espejo debe multiplicar sin perder precisión frente al NUMERIC
  exacto de PostgreSQL (contexto decimal local con precisión suficiente).
- **R12.** El patrón de la forma factor del SQL debe ser literalmente
  `PATRON_FACTOR_RENDIMIENTO` del dominio, y el número de cada lado debe
  convertirse con `descompuestos.fn_num` (un test lo fija, como R14 de F-097).
- **R13.** CUANDO se trocean los 19 registros de la partida 400854 de la 0713,
  versión 6 (tabla en `progress/spec_F-120.md` §3), el espejo debe dar 9 líneas
  con forma factor, todas con rendimiento e importe unitario, la línea 13 con
  importe 1,24 (1,22 x 0,003 x 339,39) y una suma de `importe_unitario` de
  249,41, el precio de la partida.

## La planificación de compras (PLANIF_JO) [D5]

- **R14.** CUANDO `dncpro.factip = 1`, el sistema debe publicar `factor =
  dncpro.faccan`; CUANDO `factip = 0`, `factor = 1`.
- **R15.** SI `factip` no es 0 ni 1, ENTONCES el sistema debe publicar `factor`
  e `importe_unitario` NULL.
- **R16.** En PLANIF_JO, `importe_unitario` debe ser `ROUND(pre x factor x
  canren, 2)`; `rendimiento` sigue siendo `canren` e `importe_total` no cambia.

## La columna publicada

- **R17.** `descompuestos.lineas` debe tener la columna `factor NUMERIC` al
  final de su DDL y, como la tabla persiste entre noches, añadida con `ALTER
  TABLE ... ADD COLUMN IF NOT EXISTS` (sin `DROP` de la tabla).
- **R18.** `v_pbi_estudio`, `v_pbi_planif_jo` y `v_pbi_master_planif_jo` deben
  publicar `factor` como su última columna (D8).
- **R19.** `descompuestos.fn_trocear` debe devolver `factor`. Como eso cambia su
  tipo de retorno, `01_troceado.sql` debe hacer `DROP FUNCTION IF EXISTS
  descompuestos.fn_trocear(TEXT)` antes del `CREATE`.

## El retroceo de lo ya cargado [D3, D4]

- **R20.** El sello de troceado debe cambiar con esta feature (deja de ser
  `99f827a11969d59f`, el de producción el 2026-09-30), de modo que la siguiente
  ejecución de `build_descompuestos` retrocee TODAS las versiones cargadas.
- **R21.** `00_setup.sql` debe formar parte de `FICHEROS_DEL_SELLO`: `fn_num`
  decide el rendimiento y hoy cambiarla no retrocea nada.
- **R22.** El retroceo no debe releer Sigrid ni tocar `_des_texto`, ni las
  columnas `filas`, `bytes`, `huella`, `batch_id` y `cargada_at` de
  `_versiones_cargadas`: solo cambian `sello_troceado`, `troceada_at` y
  `atributos_troceado`, como en cualquier troceado de F-097.
- **R23.** El cuadre (`cuadre_partida`) no cambia de regla: se recalcula con las
  líneas retroceadas, en la misma transacción de cada lote (F-097 R21).

## Documentación

- **R24.** La ficha de `descompuestos.lineas` y la de cada vista deben describir
  `factor` (1 sin factor, NULL sin campo) y decir que `rendimiento` es el limpio,
  `importe_unitario` lleva el factor y `cantidad_total` ya lo incluye.
- **R25.** [D7] La ficha de `lineas` (origen ESTUDIO), la de `v_pbi_estudio` y la
  de `cuadre_partida` deben avisar de que en ESTUDIO los precios son los de
  Estudios pero `cantidad_total` e `importe_total` siguen la medición ACTUAL del
  ámbito 3; de que el importe de Estudios es medición x precio del master v0 y lo
  que vale de ESTUDIO es el descompuesto por unidad; y de que MASTER_INICIAL solo
  existe donde la v0 guarda descompuesto (0713, partida 400857: 207,20 x 25,95 =
  5.376,84 frente a 207,20 x 24,03 = 4.979,02, sin MASTER_INICIAL). D7 reescrita
  y aprobada por el humano el 2026-10-01 (`progress/spec_F-120.md`).
- **R26.** `version` de `config/diccionario/00_global.yaml` debe subir en uno.
- **R27.** `docs/ARCHITECTURE.md` (formato del `des` y ficheros del sello) y
  `azure-apps/datamart_seg_anual.md` (la columna nueva) deben decirlo.

## Verificación contra la base (MANUAL del humano)

- **R28.** Tras desplegar la imagen y retrocear, en la 0713, partida 400854,
  versión 6, las 9 líneas con forma factor (D9: el `acceptance` dice 7) deben tener `factor`, `rendimiento` e
  `importe_unitario`, y su cuadre debe ser CUADRA con suma 249,41.
- **R29.** Tras el retroceo debe medirse cuántas partidas pasan de NO_CUADRA a
  CUADRA por origen y compararse con la previsión de `progress/spec_F-120.md` §4.
