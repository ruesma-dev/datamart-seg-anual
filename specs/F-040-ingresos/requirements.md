# F-040 · El lado de ingresos: certificaciones, facturas de venta, clientes y cobro

Mediciones: `progress/spec_F-040.md`. Diseño: `design.md` + `design_detalle.md`. La certificación
es `cer` (tip 54) + `cerpro`; la factura de venta, `dvf` (tip 11) + `dvfpro`; el efecto de cobro,
`cob`, ya en `tesoreria.efectos`. `obrcer`, `cerpropar` y `dvfpropar`, VACÍAS: no entran.

## Decisiones del humano (PARADA 1, 2026-11-07)

- **D1 = A.** Dos fases. Esta es la 1; el contraste completo producido/certificado de todas las
  obras y los conceptos fuera de coeficiente van a **F-160** (`pending`; depende del criterio de
  Juan Romero). Aquí, solo el contraste de las 22 obras de la receta (R19).
- **D2 modificada (personas físicas).** El NOMBRE del cliente es público para todos (`ventas`). El
  NIF de la persona física, las direcciones, el teléfono, el correo y la descripción de las líneas
  de sus facturas, solo en `ventas_restringida`. El CIF de la persona jurídica, público en `ventas`
  («los diez mayores clientes», Juan Romero); sus direcciones, en `ventas_restringida`.
- **D3 = A.** Esquema `ventas`. **D5 = A.** `ventas`: estándar y total; ni restringido ni postventa.
- **D4 = A, provisional.** Garantía = clases 4 y 5, como compras; el `RETESP` (clase 1, 16,78 M€)
  en su columna, sin sumar. Juan Romero decide (correo del líder): el cambio es UNA constante.
- **D6 modificada.** `entcif`, `entres` y las nueve `dir*` de `dvf` SÍ entran, y se publican solo
  en `ventas_restringida`; lo mismo para lo personal de `cli`. Las cuentas bancarias, fuera.
- **`ventas_restringida`** (esquema nuevo): solo el perfil total (`R-PERFILES`), patrón de
  `compras_restringida` (F-138). Pasos MANUAL con `02_roles.sql`: design § 9.

## Frontera con F-104 (retención de cliente, en paralelo)

F-040 trae las tablas y publica la retención por documento; **no toca** `sql/retenciones/` ni
`sql/tesoreria/`. **F-104** se queda el estado, el `entidad_cif` y el cuadre de la retención de
cliente, necesita `raw.cli`, `raw.dvfrec` y `ventas.facturas`, y explicará el cobro vía `AGR`.

## A · Ingesta (`config/tables_sigrid.yaml`)

- **R1.** El sistema debe declarar `cli` con `include_columns` = las 13 de negocio (`ide`, `tipcif`,
  `cifpai`, `cif`, `raz`, `perfis`, `cenide`, `taride`, `secide`, `pagide`, `efeide`, `cueide`,
  `cueretide`) + las 7 de contacto (`dir1`, `dir2`, `dircpo`, `dir`, `tel`, `tel2`, `ele`); SI entra
  otra (`ban*`, `fecnac`, `numseg`, `clamai`, `g3wpas`, `fax`, `dirtex`, `facpdfele`, `faceele`,
  `dniper`, `nom*`...), ENTONCES un test debe fallar.
- **R2.** El sistema debe declarar `cer`, `cerpro` y `dvfpro` con lista blanca, `cerrec` y `dvfrec`
  sin `tex`, y `cerprodes` entera; sin `incremental_column` y con sus cifras del 2026-11-06.
- **R3.** La lista blanca de `dvf` debe pasar de 9 a 35 columnas (design § 2): las 24 de negocio +
  `entcif`, `entres` y las nueve `dir*`; nunca `ban*` ni `emptex` (`tesoreria` no cambia).
- **R4.** El censo de `raw` debe subir de 93 a 100 donde se fija (tests, fichas, ARCHITECTURE, CLAUDE).

## B · Esquema `ventas` (paso `build_ventas`)

- **R5.** El sistema debe publicar `ventas.clientes`, una fila por `cli`: id, nombre, CIF tal cual y
  normalizado (mayúsculas, sin espacios, guiones ni puntos), tipo, país, `es_persona_fisica`,
  `cif_valido`, `cif_repetido` y, por cliente, nº de obras, facturas y certificaciones, lo facturado
  (base) y la primera y última factura.
- **R6.** `es_persona_fisica` debe ser verdadero SI `perfis` <> 0 O el CIF normalizado tiene forma de
  NIF de persona (`[0-9KLMXYZ]` + 7 dígitos + letra); dominio y función SQL, iguales en los mismos casos.
  *Enmienda del humano 2026-11-10 (R2-a):* se normaliza quitando un prefijo de país de 2 letras solo si queda un NIF (R7, R24).
- **R7.** MIENTRAS un cliente sea persona física, `ventas` debe publicar su nombre tal cual, pero su
  CIF (`cif`, `cif_normalizado`, `cif_cliente` de la factura) y la descripción de sus líneas de
  factura a NULL; `cif_valido` y `cif_repetido` se calculan antes de anularlo. *Enmienda del humano
  2026-11-10 (R2-b):* la factura cuyo cliente no está en `cli` (o sin cliente) cuenta como persona física.
- **R8.** `cif_valido` debe comprobar la letra de control en DNI y NIE y la forma en CIF de sociedad;
  un CIF vacío no es válido.
- **R9.** El sistema debe publicar `ventas.facturas`, una fila por `dvf`: id, código, empresa, fecha,
  clase, estado (`conest` tip 11), anulada (`fecbaj`), cliente (id, nombre y `cif_cliente` de
  `cli`), obra, contrato de venta, base, IVA, total sin retención, total y a cobrar, y R11. Ni
  `entcif`, ni `entres`, ni direcciones.
- **R10.** La obra de una factura debe ser la de su centro de coste (`maestro.centros_coste`) y, sin
  centro, `dvf.obride`; `obra_via` ∈ {`CENTRO`, `OBRA`, NULL}.
- **R11.** Por factura y por certificación, cuatro columnas que reparten TODOS los recargos sin
  solaparse: `importe_coeficientes` (clase 0), `retencion_garantia` (clases de `CLASES_GARANTIA`, hoy
  4 y 5), `retencion_retesp` (clase 1 mientras no esté en `CLASES_GARANTIA`) y `retencion_otras`.
- **R12.** SI `CLASES_GARANTIA` del dominio y el literal de `ventas.fn_clase_recargo` difieren,
  ENTONCES un test debe fallar: es el ÚNICO punto de decisión de D4.
- **R13.** El sistema debe publicar `ventas.factura_lineas` (una por `dvfpro`: factura, posición,
  descripción, cantidad, precio, importe, IVA, obra, partida, línea de `cerpro` de origen) y
  `ventas.factura_recargos` (una por `dvfrec`: clase, código, nombre, `clase_recargo`, `es_garantia`).
- **R14.** El sistema debe publicar `ventas.certificaciones`, una fila por `cer`: id, código, número
  (`fas`), mes, fecha, obra, contrato de venta (id y nombre), cliente (id y nombre), estado (`conest`
  tip 54), `facturada` (`estfac`) y certificación anterior.
- **R15.** Cada certificación debe llevar el importe **a cuenta** (Σ `cerpro.tot`, sin recargos), **a
  origen** (Σ `imporiori`), anterior (Σ `imporiant`), base (`totbas`, con los recargos de clase 0),
  IVA, total y R11; y `base_origen_contrato`: Σ acumulada de `totbas` de su contrato por (`fas`,
  `ide`) solo en estados 2, 3 y 4 (NULL en las demás y en las sin contrato). Sus recargos, en
  `ventas.certificacion_recargos` (una fila por `cerrec`).

## C · El enlace hasta el cobro

- **R16.** El sistema debe publicar `ventas.certificacion_factura`, una fila por par (certificación,
  factura) de `cerprodes` con `docdestip` = 11, con nº de líneas y Σ `can`; N:M, sin repartir importes.
- **R17.** El sistema debe publicar la vista `ventas.v_factura_cobro`, una fila por factura: emitido,
  cobrado (REALIZADO), pendiente (PREVISTO) y nº de efectos COBRO de `tesoreria.efectos` con
  `documento_id` = factura; BAJA no suma (`R-TESORERIA-ESTADO`) y lo cobrado por un `AGR` no se atribuye.
- **R18.** El sistema debe publicar la vista `ventas.v_seguimiento_certificacion`, una fila por
  certificación: sus facturas, lo facturado y cobrado, `factura_compartida` y `estado_seguimiento` ∈
  {`BORRADOR`, `SIN_FACTURA`, `FACTURADA_SIN_EFECTO`, `PENDIENTE_COBRO`, `COBRADA_PARCIAL`,
  `COBRADA`}, con la precedencia del dominio.
- **R19.** El sistema debe publicar `ventas.v_contraste_certificado_obra` para las obras VENTA de
  `tesoreria.devengo_corte_obra`: venta real a origen con coeficientes, certificado (estados 2-4),
  facturado y las dos diferencias, con signo.
- **R20.** El sistema debe publicar `ventas.cobertura_enlace` (por noche y eslabón: certificaciones
  emitidas con factura, facturas con efecto, efectos con factura y, R2-b, facturas con cliente), recuentos e importes.

## D · Esquema `ventas_restringida` (mismo paso)

- **R21.** El sistema debe publicar `ventas_restringida.clientes_contacto`, una fila por `cli`: id,
  nombre, CIF íntegro (también el de la persona física), `es_persona_fisica`, `dir`, `dir1`, `dir2`,
  código postal, `tel`, `tel2` y `ele`.
- **R22.** El sistema debe publicar `ventas_restringida.factura_cabecera`, una fila por `dvf`: id,
  cliente, `es_persona_fisica`, `entres`, `entcif` y las nueve `dir*` (empresa, contacto y completa, 1-3).
- **R23.** El sistema debe publicar `ventas_restringida.factura_lineas_persona`, una fila por línea
  de `dvfpro` cuya factura es de persona física (R7, con R2-b): línea, factura y descripción íntegra.
- **R24.** SI tras el build queda en `ventas` un CIF de persona física (o con forma de NIF de persona)
  en `clientes` o `facturas`, una descripción de línea de persona física, o una columna cuyo nombre
  empieza por `direccion`, `telefono`, `correo`, `cif_cabecera` o `nombre_cabecera`, ENTONCES una
  guarda `DO` debe tumbar el paso con la cifra.

## E · Guardas, pipeline y permisos

- **R25.** SI el recuento de `ventas.facturas`, `factura_lineas`, `certificaciones`,
  `ventas_restringida.clientes_contacto` o `factura_cabecera` no es el de su tabla de `raw`, Σ base
  de `ventas.facturas` ≠ Σ `raw.dvf.totbas`, o las cuatro columnas de R11 no suman Σ `cuo` de los
  recargos, ENTONCES el paso debe terminar FAILED con la cifra.
- **R26.** `build_ventas` debe depender solo de `ingest_raw`, ir en `run-all` tras
  `build_retenciones`, existir como `python main.py build-ventas`, estar en `PASOS_CON_PERMISOS` y no
  ser dependencia de nadie: si falla, la noche sigue.
- **R27.** `ventas` debe entrar en `DEFAULT_CONSUMPTION_SCHEMAS`, `.env.example` y
  `ESQUEMAS_DEL_DATAMART`, y NO en las listas del perfil restringido ni del postventa.
- **R28.** `ventas_restringida` debe entrar en `DEFAULT_VETOED_SCHEMAS`, `DEFAULT_RESTRICTED_SCHEMAS`
  (y sus `PG_*` de `.env.example`) y `ESQUEMAS_DEL_DATAMART`, y NO en el consumo, en
  `DEFAULT_TOTAL_VETOED_SCHEMAS` ni en las listas del restringido o del postventa.
- **R29.** `infra/sql/02_roles.sql` debe crear `ventas` y `ventas_restringida` con dueño
  `sigrid_dm_etl`, vetar `ventas_restringida` al estándar en los dos `ARRAY` del 5 ter (no al
  total), concederla al autorizado (USAGE, SELECT y privilegio por defecto) y comprobarlo en sus
  consultas finales; un test compara sus listas con `settings`.
- **R30.** El SQL de `sql/retenciones/` y `sql/tesoreria/` no debe cambiar (test sobre el diff);
  `retenciones.v_src_lineas_venta` pasa a leer `raw.dvfpro` solo porque existe.

## F · Diccionario y documentación

- **R31.** Todo objeto de `ventas` y `ventas_restringida` debe tener ficha (`ventas.yaml`,
  `ventas_restringida.yaml`), y las siete tablas nuevas de `raw` (y `dvf` ampliada) la suya en
  `raw.yaml`, que diga qué traen de personal.
- **R32.** `00_global.yaml` debe subir la versión, declarar los dos esquemas, añadir
  `R-VENTAS-TRES-CIFRAS` (certificado, facturado y cobrado no se suman ni restan sin declararlo) y
  `R-VENTAS-RESTRINGIDA` (lo personal del cliente, solo en `ventas_restringida`), y meter los dos
  esquemas en el ámbito de `R-PERFILES` y `build_ventas` en `R-FRESCURA`.
- **R33.** `docs/ARCHITECTURE.md`, el mapa de `CLAUDE.md`, `docs/runbook_postgres_azure.md` (§ 15)
  y `../azure-apps/datamart_seg_anual.md` deben describir `ventas`, `ventas_restringida`, las tablas
  nuevas y la frontera con F-104 (commit local en `azure-apps`, sin push).

## G · Despliegue (MANUAL, humano)

- **R34.** Tras `02_roles.sql` y el despliegue, `apply-grants` debe dar `verificacion` y
  `verificacion_total` ok, el estándar `permission denied` en `ventas_restringida`, la ingesta nueva
  < 60 s, `build_ventas` < 60 s y `retenciones.movimientos` CLIENTE las mismas cifras que la víspera.
