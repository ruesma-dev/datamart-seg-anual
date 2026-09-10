<!-- specs/F-073-tablas-nuevas-y-enriquecimiento/requirements.md -->
# F-073 · Requisitos (EARS)

**La frontera, primero.** El catálogo de F-072 propone diez construcciones y
enruta la mayoría a fichas que YA existen (F-055, F-056, F-057, F-058, F-067,
F-038, F-037, F-076). F-073 **no se las come**: se queda con **las dimensiones
transversales y el maestro de obra**, que es lo barato que desbloquea a las
demás, y deja **los hechos y su cableado** a la feature de dominio que ya los
declara en su `acceptance`. El porqué de cada caso está en `design.md` §1.

Se construye aquí: `maestro.centros_coste` (el puente), `maestro.obras`
enriquecida, `maestro.estados_documento` y `compras.formas_pago`.
NO se construye aquí: nada de `compras.contratos` / `compras.facturas`
(F-067), nada de `retenciones` (F-045), nada de `apa`/`apu` (F-056, F-058),
nada de `hmores` (F-057, F-061), nada de comparativos (F-038).

**Restricción dura que gobierna todos los requisitos: NO SE BORRA NI SE FILTRA
NADA.** Solo se añade información.

## A · El puente centro de coste → obra

- **R1.** El sistema debe publicar la vista `maestro.centros_coste` con **una
  fila por cada fila de `raw.cen`** (804 medidas el 2026-09-09), exponiendo
  `centro_coste_id`, `codigo_centro`, `nombre_centro`, `empresa`, y
  `obra_id`, `codigo_obra` y `nombre_obra` cuando el puente resuelve.
- **R2.** El sistema debe resolver el puente por **misma empresa y mismo
  código en `raw.con`** (`cen.ide → con` ↔ `con(emp, cod)` → `raw.obr`).
- **R3.** El sistema NO debe usar `cen.obride` (está a 0 en las 804 filas) ni
  aritmética sobre el `ide` (`obride + 1` acierta solo el 64 %).
- **R4.** SI un centro de coste no resuelve a ninguna obra (121 medidos:
  estructura, delegación y servicios generales), ENTONCES el sistema debe
  publicar igualmente su fila con `obra_id` a NULL. No se filtra.
- **R5.** El sistema debe garantizar que `centro_coste_id` es **único** en la
  vista: la resolución es 1:1 por construcción y no puede multiplicar filas
  aunque el origen deje de serlo.
- **R6.** La ficha del diccionario debe declarar que **683 de 804 centros
  resuelven a obra**, que la relación es 1:1 sin ambigüedad y que
  `cen.obride` no sirve.

## B · La obra enriquecida

- **R7.** `maestro.obras` debe publicar la dirección de la obra con los
  **mismos nombres de columna que `maestro.proveedores`**: `dir1`, `dir2`,
  `codigo_postal`, `provincia`, `municipio`, `direccion_completa`.
- **R8.** El sistema debe tomar la dirección **solo** de `obr.dir1`,
  `obr.dir2`, `obr.dircpo` y `obr.dir`.
- **R9.** El sistema NO debe publicar como dirección de la obra `obr.diride`
  (director de obra), `obr.perdir` (su persona de contacto) ni
  `obr.entdiride` (dirección del cliente).
- **R10.** El sistema debe publicar **municipio y provincia como ejes de
  agrupación**: el nombre legible desde `raw.auxmun` / `raw.auxpro` (vía
  `obr.munide` / `obr.proide`) **y** su identificador (`municipio_id`,
  `provincia_id`), para que agrupar no dependa del literal.
- **R11.** CUANDO una obra no tiene dirección informada, el sistema debe
  devolver NULL en esas columnas, y la ficha del diccionario debe decir que
  **«no consta» es la respuesta correcta para dos de cada tres obras**.
- **R12.** La ficha del diccionario debe declarar el **porcentaje informado
  medido en esta feature** de cada columna nueva. La referencia del censo
  (09-sep) es 294/921 = 31,9 % en municipio y 305/921 = 33,1 % en `dir1`;
  **ningún criterio de aceptación puede exigir una cobertura mayor**.
- **R13.** `maestro.obras` debe publicar `tiene_presupuesto` y
  `tiene_seguimiento`, dos booleanos **NOT NULL**.
- **R14.** `tiene_presupuesto` debe ser cierto si y solo si la obra tiene al
  menos una fila en `stg.presupuesto`; `tiene_seguimiento`, si y solo si la
  tiene en `stg.plan_mensual`.
- **R15.** La ficha debe declarar que `tiene_seguimiento` se mide en `stg` y
  es **superconjunto** del hecho publicado: medido el 2026-09-10, 368 obras
  con plan mensual frente a 349 con filas en
  `mart.fact_seguimiento_mensual`, 19 de diferencia y ninguna al revés.
- **R16.** `maestro.obras` debe publicar `estado` —el nombre del estado— junto
  a `estado_id`, traducido desde `raw.conest` **filtrando el tipo de
  documento de obra (`tip = 42`)**.
- **R17.** SI la traducción del estado pudiera devolver más de una fila para
  un `(tipo, estado)`, ENTONCES el sistema debe quedarse con una sola de
  forma determinista: `maestro.obras` conserva **921 filas**, ni una más.
- **R18.** `maestro.obras` debe conservar **todas** las columnas que publica
  hoy, con el mismo nombre y el mismo significado.

## C · Las dos dimensiones transversales

- **R19.** El sistema debe publicar `maestro.estados_documento` con las
  **193 filas** de `raw.conest`, exponiendo el tipo de documento, el código
  del estado y su nombre.
- **R20.** La ficha de `maestro.estados_documento` debe advertir de que **la
  traducción va por tipo de documento** y que la misma cifra significa cosas
  distintas en un contrato y en una factura.
- **R21.** El sistema debe publicar `compras.formas_pago` con las **69 filas**
  de `raw.auxpag`, resolviendo su medio de pago desde `raw.auxefp` (10
  filas): código, nombre, medio y clase de medio.
- **R22.** El sistema debe publicar `auxpag.formul` **verbatim**, como
  `plazo_formula`, y la ficha debe decir que **NO es un número de días**
  (`30 450R` es un valor real del catálogo).
- **R23.** El sistema NO debe modificar `compras.contratos` ni
  `compras.facturas`. **Corregido el 2026-09-10, y la versión anterior de este
  requisito era imprecisa**: el criterio 1 de `acceptance` de **F-067** nombra
  **solo `compras.contratos`** («publica el estado actual con su nombre
  (`conest`), forma de pago y retención»). El de facturas es el criterio 5, que
  habla de estado, fecha de cambio de estado, fecha de la propia factura y
  cruce con `raw.pag`, y **no menciona la forma de pago**. La forma de pago de
  la **factura** no la promete F-067: la reclama **F-080**, nacida el mismo día
  del correo de Administración. F-073 no toca ninguno de los dos objetos.

## D · Lo que no se rompe, y el papeleo

- **R24.** El sistema NO debe borrar ni filtrar ninguna fila existente: las
  472.890 huérfanas de `stg.presupuesto` (390.028) y `stg.plan_mensual`
  (82.862) siguen donde están, y el censo de la ventana no se acota.
- **R25.** El sistema NO debe modificar `sql/stg/06_presupuesto.sql` ni
  `sql/stg/08_plan_mensual.sql`: son los ficheros del SELLO y tocarlos fuerza
  la reconstrucción completa de todas las obras la noche siguiente.
- **R26.** El sistema NO debe tocar el desempate `rn = 1` de
  `sql/stg/03_obras.sql` (es F-053).
- **R27.** MIENTRAS `maestro.obras` lea de `stg`, el paso `build_maestros`
  debe declarar `build_stg` entre sus dependencias.
- **R28.** Cada objeto nuevo o ampliado debe llevar su ficha en
  `config/diccionario/`, con grano y significado de cada columna, y
  `00_global.yaml` debe subir a **versión 19**.
- **R29.** `bash harness/init.sh` debe terminar en verde, y
  `python main.py check-declarados` no debe reportar objeto declarado y no
  construido.
