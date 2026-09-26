# F-072 · Censo semántico de `raw` — bloque DOCUMENTOS DE COSTE

`dco`, `dcopro`, `dcorec`, `dcarec`, `dcfrec`, `dcfprodes`, `ctrrec`, `dnc`, `dncpro`. Solo lectura, 2026-09-09.

**Aviso de nombre.** El bloque se llamó «albaranes, facturas y recepciones», pero `dco` es **oferta de compra**, no albarán (doc, pág. 140). Lo que hay es la **cadena previa al contrato** (necesidad → oferta) y las **condiciones económicas** (retenciones y recargos) de contrato, albarán, factura y oferta. Albaranes (`dca`) y facturas (`dcf`) ya los consume `compras`.

**Fuentes.** (D) `azure-apps/sigrid_tablas.md` · (S) sigrid-api contra Sigrid vivo · (R) medición sobre `raw`. Los porcentajes de `dco`, `dncpro` y las cuatro `*rec` son de **tabla completa**; los de `dcopro` (788.644 filas) de **`TABLESAMPLE SYSTEM (3)`, 24.522 filas**.

---

### `raw.dco` — la oferta que un proveedor manda para un comparativo

- **Grano**: una oferta de un proveedor para un comparativo de una obra. Extiende `con` con el mismo `ide` (D): **código, descripción, fecha y estado viven en `raw.con`, no aquí**.
- **Volumen**: 72.260 en `raw` (R) / 72.267 en Sigrid (S). Serie única `OC`, 2014-07-14 → 2026-09-08. Entre 6.000 y 9.000 ofertas al año.
- **Se une por** (S): `ide`→`con` al 100% (`con.tip`=12); `entide`→`con` proveedor 72.141 y `obride`→`obr` 72.239 — **ambos ya en el datamart**; `comide`→`com` comparativo 70.686 — `com` se ingiere y **no lo lee nadie**; `pagide`→`auxpag` y `efeide`→`auxefp` al 100% (R), también sin consumidor.
- **Columnas que importan** (R, informado/distintos): `pagide` 100%/47 y `pagtex` 100%/96 (forma de pago ofertada), `efeide` 100%/8, `obride` 100%/189 obras, `comide` 97,8%/19.874, `entide` 99,8%/8.801 proveedores, `totbas` 95,3%/50.351 (base ofertada: 275-487 M€/año en 2018-2026), `cenide` 99,9%, `empide` 97,0%/142, `tipgar` 59,0%/4, `cocide` 11,3%/21 (tipo de contrato de compra).
- **El estado NO está donde el documento sugiere.** (D) declara `estped`, `estser` y `estfac`; (S) los da los tres a cero en 71.554 de 72.267. El estado real es **`con.est`**, con nombre en `conest` para `tip`=12: **Rechazada 45.575 (63%), Aceptada definitivamente 17.668 (24%), Pendiente 5.032, Recibida 3.733, Precios solicitados 259**. Es el dato más valioso de la tabla y **contradice al documento**.
- **Columnas vacías o inútiles** (R): 60 de 134 a cero o nulo en las 72.260, entre ellas `ctride` (0%: la oferta **no** apunta al contrato), `caaide`, `ivaide`, `impdes`, `imprec`, `idefac`, `facoriide`, `docoriide`, `pasdeside`, las ocho de divisa, las ocho de centro administrativo y las ocho de cuenta de pago. `fecdoc` solo al 6,4% (la fecha buena es `con.fec`, al 100%); `entcif` al 48,0%.
- **Cómo funciona**: nace cuando Compras pide precio dentro de un comparativo para una obra; el proveedor contesta y sus líneas entran en `dcopro`, atadas a la necesidad (`dncproide`) y al comparativo (`comlinide`). Después **solo cambia `con.est`**: Precios solicitados → Recibida → Aceptada o Rechazada. El paso a contrato ya no se registra por línea: `dcoprodes` (oferta-línea → contrato) **dejó de escribirse en 2020** (S: 51 filas en 2015, 11.124 en 2020, **cero desde 2021**). Hoy la adjudicación se lee por el comparativo: de las 17.668 Aceptadas, 6.722 tienen un `ctr` con el mismo `comide` y el mismo `entide`; de las 45.575 Rechazadas, solo 1.027 (S).
- **Qué permitiría responder**: tasa de adjudicación por proveedor y su evolución; cuántos proveedores compiten por obra y actividad; qué forma de pago ofrece cada uno frente a la que acabamos firmando (`dco.pagide` vs `ctr.pagide`).
- **Solapamiento**: **ninguno**. `compras` arranca en el contrato; publica `comparativo_id` pero **no hay ningún objeto de ofertas ni de comparativos** en los ocho esquemas que ve el MCP.
- **Enrutado**: **F-067** (bloque 2 del correo de Compras). Pieza central de esa feature.

### `raw.dcopro` — la línea de oferta: el precio que dio cada proveedor

- **Grano**: una línea de oferta (producto o partida) dentro de un `dco`.
- **Volumen**: 788.644 en `raw` (R) / 788.796 (S). Unas 11 líneas por oferta.
- **Se une por** (S, tabla completa): `docide`→`dco` al 100%; `dncproide`→`dncpro` 787.118 (99,8%); `comlinide`→`comlin` 780.272 (98,9%), ingerida y sin consumidor; `paride`→`obrparpar` 787.821 (99,9%) — **ya en el datamart**; `natide`→`auxpronat` 99,8% (R); `proide`→`pro` 99,9% (R) pero **`pro` no se ingiere**: hoy el producto no tiene nombre.
- **Columnas que importan** (R, muestra del 3%): `pre` 84,9%/8.856 (precio ofertado), `can` 94,9%/6.610, `tot` 82,0%, `tar` 84,9% (bruto antes de descuento), `dto` 12,6%/145, `res` 100%/14.925, `unimed` 96,9%/83, `cod2` 74,3%, `cenide` 100%, `caaide` 99,0%/1.199, `ivacuo` 81,3%, `prepma` 30,7% (precio medio de almacén, comparable con el ofertado).
- **Columnas vacías o inútiles** (R): 32 de 67 — `docoritip`, `docoriide`, `linoriide`, `canorilin`, `canped`, `cancan`, `fec`, `pla`, `envide`, `taride`, `lintip` y `anades`, todas a cero. `canser` 3,5% y `canfac` 3,4%: en la oferta no se sirve ni se factura nada, coherente.
- **Cómo funciona**: se crea al cargar la oferta, copiando la línea de necesidad y la del comparativo, y es **inmutable en la práctica** (los campos con que Sigrid la movería al documento siguiente están a cero). La comparación entre proveedores se hace por `dncproide`: **mediana de 4 ofertas por línea de necesidad** (R: 45.501 líneas con 4 ofertas, 40.565 con 3, 26.269 con 2, 22.845 con 1; cola hasta 15).
- **Qué permitiría responder**: cuánto se abarató una partida entre la primera oferta y la adjudicada; qué proveedor es sistemáticamente el más caro por naturaleza de producto; cuántos precios distintos manejamos para el mismo producto en obras distintas el mismo año.
- **Solapamiento**: **ninguno**. `compras.fact_compras_linea` empieza en la línea de contrato; el precio ofertado y no adjudicado no existe en el datamart.
- **Enrutado**: **F-067**, junto con `dco`.

### `raw.dnc` — la necesidad de compra: la cabecera del pedido de la obra

- **Grano**: una necesidad de compra de una obra. Extiende `con` (`tip`=36, S).
- **Volumen**: 275 filas (R y S), **una por obra** (272 obras distintas en 275 filas, R). 2009-02-20 → 2026-08-04 (S), unas 20 al año.
- **Se une por**: `ide`→`con` al 100%; `obride`→`obr` 98,9% (R) — **ya en el datamart**; `empide`→`emp` 84,0% y **solo 10 empleados distintos** (R).
- **Columnas que importan**: tres — `ide`, `obride` y `empide`. Todo el contenido está en `dncpro`.
- **Columnas vacías o inútiles** (R): **10 de 14 a cero** (`estcer`, `cla`, `prmide`, `pexide`, `areide`, `depide`, `divcod`, `cenide`, `ambide`, `ppoide`); `fas` al 8,4%. **`estcer` («estado cerrada») vale 0 en las 275** y (S) confirma que las 275 están en `con.est`=1 «En curso»: la necesidad **nunca se cierra**.
- **Cómo funciona**: se abre una por obra al arrancarla y se queda abierta para siempre; lo que se mueve son sus líneas. Es un contenedor, no un documento con ciclo de vida.
- **Qué permitiría responder y solapamiento**: casi nada por sí sola, y no aporta nada que `obr` no dé ya; su valor es dar obra a las 286.698 líneas de `dncpro`.
- **Enrutado**: **F-067**, solo como dimensión de `dncpro`. Como objeto propio no vale la pena.

### `raw.dncpro` — la línea de necesidad: qué pide la obra y a qué contrato fue

- **Grano**: una línea de necesidad (partida o producto que la obra debe comprar).
- **Volumen**: 286.698 en `raw` (R) / 286.728 (S). Unas 1.170 líneas por obra.
- **Se une por** (S, tabla completa): `dncide`→`dnc` al 100%; **`adjctride`→`ctr` 185.117 (64,6%)** y **`adjctrlin`→`ctrpro` 184.123 (64,2%)** — el contrato adjudicado, **ya en el datamart**: los 185.072 de `raw` casan los 185.072 de `compras.contratos` (R); `paride`→`obrparpar` 286.722 (100%) — **ya en el datamart**; `proide`→`pro` 95,4% (`pro` no se ingiere); `entide`→`prv` solo 2,3% (proveedor recomendado, apenas se usa); `natide`→`auxpronat` 95,4%.
- **Columnas que importan** (R, tabla completa): `paride` 100%/110.219, `res` 98,5%/159.609, `can` 85,9%, `pre` 91,9%/46.744, `canref` 79,6%, `preref` 85,2%/43.953, `adjctride` 64,6%/11.734 contratos, `adjctrlin` 64,2%, `cenide` 95,7%, `caaide` 88,2%/4.575, `canren` 92,6% (rendimiento), `unimed` 92,8%, `cod2` 73,2%, `tipman` 85,8%, `factip` 14,5%, `faccan` 12,4%.
- **TRAMPA MEDIDA, y es lo más importante de la tabla.** (D) llama a `pre` «Precio» y a `preref` «Precio Referencia» sin decir cuál es cuál. Medido (S): de las 184.123 líneas adjudicadas, **180.813 (98,2%) tienen `pre` exactamente igual a `ctrpro.pre`**, y 134.510 (73%) además `can` igual a `ctrpro.can`. Al adjudicar, **Sigrid SOBREESCRIBE la línea de necesidad con el precio y la cantidad del contrato**: `pre` no es lo que la obra estimó, es lo que se firmó. La estimación original sobrevive en `preref`/`canref`, informadas en 165.094 de las adjudicadas (89,7%). Quien calcule «desviación de compra» comparando `pre` contra `ctrpro.pre` obtendrá cero y creerá que compramos perfecto.
- **Columnas vacías o inútiles** (R): **41 de 71 a cero** en las 286.698, incluidas `almide`, `nattippro`, `nattipcom`, `comcod`, `comtip`, `comaut`, `obrprvide`, `haymed`, `medfijdis`, `candis`, `predis`, `gpcide` (16 filas), `rqsproide`, `famide`, las seis de divisa y `coside`. `fec` en 5 filas, `com` en 459.
- **Cómo funciona**: la obra da de alta la línea con su medición y su precio de referencia; Compras la mete en un comparativo, recibe ofertas (`dcopro.dncproide`) y adjudica; al adjudicar se escriben `adjctride` y `adjctrlin` y **se pisan `can` y `pre`**. Las 101.611 líneas sin adjudicar (35,4%) suman **131,4 M€** a precio de referencia frente a **605,7 M€** adjudicados (S): es la **compra pendiente**, medible por obra y por partida.
- **Qué permitiría responder**: qué compra le queda pendiente a cada obra, por partida y en euros; cuánto se desvió el precio adjudicado del de referencia (`preref` → `ctrpro.pre`); qué partidas se compran siempre por encima de lo previsto.
- **Solapamiento**: **parcial y por el lado bueno**. `compras.contrato_lineas` publica la línea de contrato con `partida_id`; lo que no existe en ningún sitio es el **precio de referencia previo** ni la **necesidad no adjudicada**. `dncpro.paride` ↔ `mart` cierra el círculo presupuesto ↔ compra, hoy roto.
- **Enrutado**: **F-067** como fuente principal. Roza F-063, pero eso es analítica contra contabilidad y esto es compra contra presupuesto.

---

### Las cuatro tablas de recargos: `ctrrec`, `dcfrec`, `dcarec`, `dcorec`

Comparten estructura exacta (20 columnas de negocio, D) y el mismo catálogo `recide`→`rec`, que el datamart **ya publica como `retenciones.tipos`**.

**`reccla` es una copia denormalizada de `rec.cla`** (S: coinciden en 26.418 de 26.418 filas de `dcfrec`). Significado sacado del catálogo `rec` (S): **0** recargo (financiero, portes, gastos generales, beneficio industrial) · **1** descuento o retención especial · **2** anticipos y suplidos · **3** retención fiscal (IRPF, arrendamientos) · **4** garantía sobre el total · **5** garantía sobre la base imponible.

Seis columnas vienen **a cero en las cuatro tablas y en todas sus filas** (R): `valcan`, `reqcuo`, `refide`, `frasupide`, `resalt` e `item`. `ivaide` e `ivacuo` rondan el 0,1-0,6%.

**Cómo funciona el ciclo** (D + S + R): la condición se pacta al firmar el contrato (`ctrrec`), se arrastra al albarán (`dcarec`), se aplica en la factura (`dcfrec`) y de ahí sale el efecto en `pag`, que es lo que `retenciones.movimientos` ya publica (27.817 filas). **Sumar `dcarec` + `dcfrec` es doble conteo**: 20,4 + 25,8 M€ no son 46 M€, el mismo importe pasa por los dos documentos.

#### `raw.ctrrec` — la retención de garantía tal y como la pacta el contrato

- **Grano y volumen**: una condición de un contrato de compra. 6.343 filas (R y S), 6.335 contratos, de 2008 a 2026-09-08 (S).
- **Se une por**: `docide`→`compras.contratos`, **6.343 de 6.343 (100%, R)**.
- **Columnas que importan** (R): `bas` 93,0%, `valpor` 99,8%/30, `cuo` 92,8%/5.685, `reccla` 99,7%/5, `cueide` 83,6%/1.155 (cuenta contable).
- **La cifra**: `reccla`=5 son 6.257 contratos, **base 460,3 M€ y cuota 22,8 M€**, al 5,00% de media (R); y solo **6.257 de los 18.930 contratos (33%)** llevan retención pactada (S): no es una regla general, es una decisión por contrato.
- **Qué permitiría responder**: qué contratos llevan retención pactada y cuáles no; si lo pactado (22,8 M€) coincide con lo efectivamente retenido; qué porcentaje firmamos con cada proveedor.
- **Solapamiento**: **complemento exacto de `retenciones`**, que se construye sobre efectos (`pag`/`cob`/`rec`) y cuyo propio comentario dice que «la regla contractual vive en `raw.obrctr.coegar`» — esa es la del **cliente**. La del **proveedor** está aquí y no la publica nadie.
- **Enrutado**: **F-067** (condiciones del contrato, punto 1 del correo de Compras). Poca tabla y mucho valor.

#### `raw.dcfrec` — la retención y el recargo aplicados en la factura

- **Grano y volumen**: una condición de una factura de compra. 32.680 en `raw` (R) / 32.685 (S), 32.608 facturas, de 2008-10-01 a 2026-09-08 (S).
- **Se une por**: `docide`→`compras.facturas`, **32.680 de 32.680 (100%, R)**; 99 tipos de `rec` distintos usados.
- **Columnas que importan** (R): `bas` 99,9%, `valpor` 100%/58 porcentajes, `cuo` 99,9%/24.130, `cueide` 99,9%/1.659 cuentas, `reccla` 99,8%.
- **El reparto medido** (R): garantía del 5% sobre base **26.274 líneas y 23,1 M€**; IRPF de profesionales y autónomos unas 3.400 líneas y 0,5 M€; arrendamientos del 19-21% unas 2.400 líneas y 0,76 M€; garantía sobre total 158 líneas y 0,29 M€. **Es el único sitio del modelo donde la retención fiscal aparece con su base y su cuota.**
- **Qué permitiría responder**: cuánto IRPF hemos retenido por año; qué facturas llevan retención que su contrato no pactaba (`dcfrec` sin `ctrrec`); si la retención de la factura cuadra con el efecto de `pag` (26.413 líneas de garantía por 23,4 M€ aquí frente a 27.817 movimientos publicados, R).
- **Solapamiento**: **alto en garantía, nulo en fiscal**.
- **Enrutado**: **F-067** para el contraste con `ctrrec`; el bloque fiscal encaja mejor en **F-063**, porque su destino natural es la cuenta contable de `cueide`.

#### `raw.dcarec` — la misma retención, pero en el albarán

- **Grano y volumen**: una condición de un albarán. 40.967 en `raw` (R) / 40.972 (S), 40.920 albaranes, de 2008-10-31 a 2026-09-04 (S). **Es la mayor de las cuatro.**
- **Se une por**: `docide`→`compras.albaranes`, **40.967 de 40.967 (100%, R)**.
- **Columnas que importan** (R): `bas` 96,6%, `valpor` 99,4%/43, `cuo` 95,5%/30.047, `cueide` 87,5%, `reccla` 99,3%.
- **El reparto** (R): garantía del 5% sobre base **39.441 líneas y 20,0 M€**; el resto es residual (IRPF 371+142+133 líneas, garantía del 2,5% 146, del 10% 69). **262 filas con `recide`=0 y cuota 0**: basura de captura.
- **Qué permitiría responder**: cuánta retención hay comprometida en albaranes **aún no facturados** — `compras.v_pbi_albaranes_sin_facturar` identifica esos albaranes pero no dice qué retención llevan encima. Es lo único nuevo que trae.
- **Solapamiento**: alto con `dcfrec` (mismo importe, un documento antes).
- **Enrutado**: **F-067**, y solo por esa vía. Publicarla al mismo nivel que `dcfrec` sería una trampa de doble conteo.

#### `raw.dcorec` — la retención pactada ya en la oferta

- **Grano y volumen**: una condición de una oferta. **751 filas** (R y S), 750 ofertas de 72.267 (**el 1,0%**).
- **Columnas que importan** (R): las **748 filas de garantía del 5% sobre base, por 0,98 M€ de cuota**; `bas` 96,8%, `valpor` 98,0%, `cuo` 94,8%. Vivas (S: la última, OC26/6197, del 2026-09-08). `valmod` al 7,5%.
- **Cómo funciona**: el 1% de las ofertas trae ya escrita la retención; en el 99% restante aparece por primera vez en el contrato. **La retención se negocia al firmar, no al ofertar.**
- **Solapamiento y enrutado**: total con `ctrrec`, con 100 veces menos filas. **No vale la pena construir nada**; como mucho, columna opcional de la línea de oferta si F-067 la quiere.

---

### `raw.dcfprodes` — el enlace del abono con la factura original

- **Grano y volumen**: una línea de factura de compra que se «pasa» a otro documento. **276 filas** (R y S): 276 líneas origen y 86 documentos destino.
- **Se une por**: `docproide`→`dcfpro` al 100%; `docdeside`→`con` al 100% (R).
- **Qué es de verdad** (S, y el documento no lo dice): `docdestip` vale **15 (factura) en las 276** y **`can` es negativa en las 276** (de -1 a -1.749 al año); los destinos son abonos («BANESTO RENTING, abono fra.41608»; «TELEFONICA, ABONO»). **Es el rastro de abonos y rectificativas de factura de compra**, no un «destino» genérico. 18 años, unas 15 filas al año, sin patrón (57 en 2011, 1 en 2021 y 2025, 16 en 2026): un mecanismo que casi nadie usa.
- **HALLAZGO GRANDE, más allá de esta tabla.** `dcfprodes` es la **peor de sus cuatro hermanas** y es justo la única ingerida. Medido (S): **`dcaprodes` 850.977 filas** (albarán → factura, `docdestip`=15 en 850.156), **`ctrprodes` 424.454** (contrato → albarán 392.950 y → factura 31.455), **`dcoprodes` 43.758** (oferta → contrato, muerta desde 2020). **Ninguna de las tres está en `raw`.** La trazabilidad línea a línea de contrato → albarán → factura vive ahí; hoy `compras` la reconstruye por `linoriide`+`docoritip`, que es aproximada.
- **Qué permitiría responder y solapamiento**: qué facturas se han abonado y por cuánto, poco más; `compras.facturas` ya tipa abonos (serie AB) por el código y esto solo añade a qué factura concreta corrige.
- **Enrutado**: **no vale la pena** por sí sola. Sí vale llevar el hallazgo a **F-066/F-067**: dar de alta `dcaprodes` y `ctrprodes`.

---

## Lo que yo construiría, y en qué orden

1. **`compras.condiciones_documento`** — unifica `ctrrec`, `dcfrec` y `dcarec` (80.000 filas) con el tipo resuelto por `retenciones.tipos`, el documento tipado y **una marca explícita de nivel** (contrato = regla, albarán = comprometido, factura = aplicado) para que nadie sume los tres. Es la construcción más barata del bloque —tres tablas pequeñas, joins verificados al 100% contra `compras`— y la que más agujero tapa: hoy el datamart publica el **efecto** de la retención y no su **regla**, y la retención fiscal no existe en ningún objeto. Alimenta **F-067**.

2. **`compras.necesidad_linea`** sobre `dncpro` + `dnc` — con `preref`/`canref` como precio y medición de referencia, `pre`/`can` marcados **explícitamente como «valor adjudicado, sobreescrito por Sigrid»**, y `adjctride` resuelto a `compras.contratos`. Da dos respuestas que hoy no existen: la **compra pendiente por obra y partida** (101.611 líneas, 131,4 M€) y la **desviación entre el precio de referencia y el adjudicado**. `paride` casa al 100% con `obrparpar`, así que enlaza con `mart` sin inventar nada. Alimenta **F-067**.

3. **`compras.ofertas` + `compras.oferta_linea`** sobre `dco`/`dcopro` — con **`con.est` traducido por `conest`** como columna de primera clase, que es lo que responde «tasa de adjudicación por proveedor». Las 788.644 líneas son la parte cara, y por eso va tercera, no porque valga menos. Alimenta **F-067** y absorbe la mitad de **F-038**.

4. **Nada sobre `dcorec` ni `dcfprodes`.** 751 y 276 filas, ambas cubiertas por hermanas mejores. Decirlo por escrito vale más que construirlas.

5. **Fuera de F-072, pero hay que decirlo**: dar de alta `dcaprodes` (850.977) y `ctrprodes` (424.454). Son la trazabilidad línea a línea de contrato → albarán → factura, la cadena que este bloque debía documentar, y hoy `compras` la aproxima por `linoriide`. Es una decisión de **F-066**.
