# F-040 · El lado de ingresos: certificaciones, facturas de venta, clientes y cobro

Mediciones (2026-11-06, solo lectura): `progress/spec_F-040.md`. Diseño: `design.md`.
Vocabulario: la **certificación** es `cer` (`con.tip` 54) con sus líneas `cerpro`; la **factura
de venta**, `dvf` (tip 11) con `dvfpro`; el **efecto de cobro**, `cob` (tip 24), ya publicado en
`tesoreria.efectos`. `obrcer`, `cerpropar` y `dvfpropar` están VACÍAS en Sigrid: no entran.

## Decisiones para el humano (la recomendada, marcada)

- **D1 · Partir en dos fases.** **A (recomendada)**: F-040 es la fase 1 (este documento); el
  contraste completo producido/certificado de TODAS las obras y los conceptos fuera de
  coeficiente pasan a una feature nueva (F-040 fase 2), porque Sigrid no los marca (`obrcer`
  vacía, `cerpro.paride` en 5 de 6.362 líneas, recargos `COEF_*` en 1.286 de 6.308
  certificaciones) y hace falta el criterio de Juan Romero. La fase 1 deja el contraste de las
  22 obras de la receta (R20). B: todo en F-040 (spec bloqueada hasta tener el criterio).
- **D2 · Clientes persona física** (571 NIF/NIE de persona, solo 26 con `perfis`; 3.631 facturas,
  16,5 M€: garajes, rentas, compraventas). **A (recomendada)**: fuera de `raw` no se publica su
  nombre, NIF ni la descripción de sus líneas (enmascarado en `ventas`). B: esquema nuevo
  `ventas_restringida` (grupo, `02_roles.sql`, perfiles). C: publicarlo todo.
- **D3 · Esquema `ventas`** (**recomendada**) frente a repartirlo en `tesoreria` y `maestro`.
- **D4 · Retención de garantía de venta.** **A (recomendada)**: el criterio D2-B de compras
  (clases 4 y 5) y el `RETESP` (clase 1, 16,78 M€ en 1.030 facturas, que en venta Sigrid llama
  «garantía») en su columna aparte, nunca sumado; F-104 decide si cuenta. B: sumar el `RETESP`.
- **D5 · Perfiles.** **A (recomendada)**: `ventas` lo leen el estándar y el total; NO el
  restringido (su vista de cobro lee la cartera, que F-141 le quita) ni el postventa.
- **D6 · `dvf` sigue en lista blanca**, ampliada de 9 a 24 columnas (**recomendada**), sin el
  CIF, el nombre ni las direcciones de la cabecera.

## Frontera con F-104 (retención de cliente, spec en paralelo)

F-040 **trae** a `raw` `cli`, `dvfpro`, `dvfrec`, `cer`, `cerpro`, `cerrec` y `cerprodes`, y
publica la retención por documento (`ventas.facturas`, `ventas.certificaciones`). **No toca** `sql/retenciones/` ni
`sql/tesoreria/`. **Deja a F-104** el estado de `retenciones.movimientos` CLIENTE, su
`entidad_cif`, el cuadre retención de factura de venta ↔ efectos ↔ contabilidad y la conciliación
22,16 / 13,81 / 2,2 M€. **F-104 necesita de F-040** `raw.cli`, `raw.dvfrec` y `ventas.facturas`.
**F-040 necesita de F-104** (no bloquea) qué les pasa a los efectos de `cob` con `fecbaj`: hasta
entonces lo cobrado vía agrupado `AGR` no se atribuye a la factura y se declara (R18).

## A · Ingesta (`config/tables_sigrid.yaml`)

- **R1.** El sistema debe declarar `cli` con `include_columns` = `ide`, `tipcif`, `cifpai`, `cif`,
  `raz`, `perfis`, `cenide`, `taride`, `secide`, `pagide`, `efeide`, `cueide`, `cueretide`; SI
  entra una dirección, teléfono, correo, cuenta bancaria, `fecnac`, `clamai` o `numseg`,
  ENTONCES un test debe fallar.
- **R2.** El sistema debe declarar `cer`, `cerpro` y `dvfpro` con lista blanca (design § 2),
  `cerrec` y `dvfrec` enteras sin `tex`, y `cerprodes` entera; todas sin `incremental_column`
  (no tienen `tiemod`) y con un comentario con sus cifras del 2026-11-06.
- **R3.** La lista blanca de `dvf` debe ampliarse a las 24 columnas de design § 2 (D6) sin
  `entcif`, `entres`, `emptex` ni ninguna `dir*`/`ban*`; `tesoreria` debe seguir leyendo
  `cenide` y `totbas` de ella.
- **R4.** El censo de `raw` debe subir de 93 a 100 donde se fija (tests, fichas,
  `docs/ARCHITECTURE.md`, `CLAUDE.md`).

## B · Esquema `ventas` (paso `build_ventas`)

- **R5.** El sistema debe publicar `ventas.clientes`, una fila por `cli`: id, nombre, CIF tal
  cual y normalizado (mayúsculas, sin espacios, guiones ni puntos), tipo y país, `es_persona_fisica`,
  `cif_valido`, `cif_repetido` (cuántas fichas comparten CIF normalizado), y por cliente el número
  de obras, facturas y certificaciones, lo facturado (base) y la primera y última factura.
- **R6.** `es_persona_fisica` debe ser verdadero SI `perfis` <> 0 O el CIF normalizado tiene forma
  de NIF de persona (`[0-9KLMXYZ]` + 7 dígitos + letra); el dominio y la función SQL deben dar lo
  mismo en los mismos casos.
- **R7.** MIENTRAS un cliente sea persona física (D2 = A), `ventas` debe publicar su nombre como
  `PERSONA FÍSICA`, su CIF a NULL y la descripción de sus líneas de factura a NULL; SI se cuela
  uno, ENTONCES una guarda `DO` debe tumbar el paso.
- **R8.** `cif_valido` debe comprobar la letra de control en DNI y NIE y la forma en CIF de
  sociedad; un CIF vacío no es válido.
- **R9.** El sistema debe publicar `ventas.facturas`, una fila por `dvf`: id, código, empresa,
  fecha, clase (`cla`), estado (`conest` tip 11), anulada (`fecbaj`), cliente, obra, contrato de
  venta, base, IVA, total sin retención, total y a cobrar, más los recargos de R11.
- **R10.** La obra de una factura debe ser la de su centro de coste (`maestro.centros_coste`) y,
  sin centro, `dvf.obride`; `obra_via` debe decir `CENTRO`, `OBRA` o NULL.
- **R11.** Por factura y por certificación el sistema debe publicar, sin mezclarlos:
  `importe_coeficientes` (clase 0), `retencion_garantia` (clases 4 y 5, D4), `retencion_retesp`
  (clase 1) y `retencion_otras` (clases 2 y 3).
- **R12.** El sistema debe publicar `ventas.factura_lineas` (una por `dvfpro`: factura, posición,
  descripción, cantidad, precio, importe, IVA, obra, partida si la hay, línea de certificación de
  origen si `linoriide` es una `cerpro`) y `ventas.factura_recargos` (una por `dvfrec`, con clase,
  código y nombre del recargo y `es_garantia`).
- **R13.** El sistema debe publicar `ventas.certificaciones`, una fila por `cer`: id, código,
  número (`fas`), mes (primer día del mes de `fecdoc`), fecha, obra, contrato de venta (id y
  nombre), cliente, estado (`conest` tip 54), `facturada` (`estfac`), certificación anterior.
- **R14.** Cada certificación debe llevar el importe **a cuenta** (Σ `cerpro.tot`, sin recargos),
  **a origen** (Σ `cerpro.imporiori`, el de Sigrid), anterior (Σ `imporiant`), la base de
  cabecera (`totbas`, con los recargos de clase 0), IVA, total y los recargos de R11.
- **R15.** Cada certificación debe llevar además `base_origen_contrato`: la suma acumulada de
  `totbas` de su contrato por (`fas`, `ide`) contando solo los estados 2, 3 y 4; una Pendiente de
  emisión no suma (en su propia fila la columna es NULL).
- **R16.** El sistema debe publicar `ventas.certificacion_recargos` (una fila por `cerrec`).

## C · El enlace hasta el cobro

- **R17.** El sistema debe publicar `ventas.certificacion_factura`, una fila por par
  (certificación, factura) de `cerprodes` con `docdestip` = 11, con el número de líneas y la
  suma de `can` del par; el par es N:M y ningún importe se reparte.
- **R18.** El sistema debe publicar la vista `ventas.v_factura_cobro`, una fila por factura, con
  lo emitido, cobrado (REALIZADO), pendiente (PREVISTO) y el número de efectos de
  `tesoreria.efectos` COBRO con `documento_id` = factura; BAJA no suma (`R-TESORERIA-ESTADO`) y
  lo cobrado por un `AGR` no se atribuye.
- **R19.** El sistema debe publicar la vista `ventas.v_seguimiento_certificacion`, una fila por
  certificación, con sus facturas, lo facturado y cobrado de ellas, `factura_compartida` y
  `estado_seguimiento` ∈ {`BORRADOR`, `SIN_FACTURA`, `FACTURADA_SIN_EFECTO`, `PENDIENTE_COBRO`,
  `COBRADA_PARCIAL`, `COBRADA`}, con la precedencia del dominio (`estado_seguimiento`).
- **R20.** El sistema debe publicar la vista `ventas.v_contraste_certificado_obra` para las obras
  de VENTA de `tesoreria.devengo_corte_obra`: venta real a origen con coeficientes, certificado
  (base de las certificaciones en estado 2, 3 y 4), facturado y las dos diferencias.
- **R21.** El sistema debe publicar `ventas.cobertura_enlace` (una fila por noche y eslabón:
  certificaciones emitidas con factura, facturas con efecto, efectos de cobro con factura), con
  recuentos e importes, para que la cobertura se lea y no se suponga.

## D · Guardas, pipeline y permisos

- **R22.** SI el recuento de `ventas.facturas`, `factura_lineas` o `certificaciones` no es el de su
  tabla de `raw`, o Σ base de `ventas.facturas` ≠ Σ `raw.dvf.totbas`, ENTONCES el paso debe
  terminar FAILED con la cifra.
- **R23.** `build_ventas` debe depender solo de `ingest_raw`, ir en `run-all` tras
  `build_retenciones`, existir como `python main.py build-ventas`, estar en `PASOS_CON_PERMISOS`
  y no ser dependencia de nadie: si falla, la noche sigue.
- **R24.** `ventas` debe entrar en `DEFAULT_CONSUMPTION_SCHEMAS`, `.env.example` y
  `ESQUEMAS_DEL_DATAMART`, y NO en las listas del perfil restringido ni del postventa (D5).
- **R25.** El SQL de `sql/retenciones/` y `sql/tesoreria/` no debe cambiar (test sobre el diff de
  la rama); `retenciones.v_src_lineas_venta` debe pasar a leer `raw.dvfpro` solo porque existe.

## E · Diccionario y documentación

- **R26.** Todo objeto de `ventas` debe tener ficha en `config/diccionario/ventas.yaml`, y las siete
  tablas nuevas de `raw` (y `dvf` ampliada) la suya en `raw.yaml`; `00_global.yaml` debe subir
  la versión, declarar el esquema y la regla dura `R-VENTAS-TRES-CIFRAS` (certificado, facturado y
  cobrado no se suman ni se restan sin declararlo; las personas físicas van enmascaradas).
- **R27.** `docs/ARCHITECTURE.md`, el mapa de `CLAUDE.md` y `../azure-apps/datamart_seg_anual.md`
  deben describir `ventas`, las tablas nuevas y la frontera con F-104 (commit local en
  `azure-apps`, sin push).

## F · Despliegue (MANUAL, humano)

- **R28.** Tras el despliegue, la ingesta de las tablas nuevas debe medirse en < 60 s, el paso
  `build_ventas` en < 60 s, y `retenciones.movimientos` CLIENTE debe dar las mismas cifras que la
  víspera (medido: 0 efectos de retención sin centro).
