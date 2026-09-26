# F-072 · Censo semántico de `raw` — bloque COMPRAS Y PROVEEDORES

Las 8 tablas del bloque. **Solo lectura**: ni una escritura contra Sigrid ni contra
Postgres. Medido el **2026-09-09**. Fuente de cada afirmación: **[DOC]**
`azure-apps/sigrid_tablas.md` · **[SIG]** `SELECT` por sigrid-api contra el SQL Server
vivo · **[RAW]** medición sobre `raw` (escaneo completo; la mayor son 196.811 filas,
no hizo falta muestrear).

### `raw.com` — la cabecera del comparativo: una compra sacada a concurso

- **Cómo funciona** [DOC+SIG]: `com` **extiende `con`** (mismo `ide`, `con.tip`=46). Nace al convertir un documento de necesidad (`dnc`) en comparativo. Se invita a proveedores (`comprv`), cada uno con su oferta (`dco`); las líneas a cotizar son `comlin` y el precio de cada proveedor por línea vive en `dcopro`. Al adjudicar nace el contrato (`ctr`) y cada `comlin` apunta a él. Después recorre un circuito de firma (`confir` con `cod`='COMVAL', plantilla en `deffir`) que le cambia `con.est`. Cadena completa: `dnc` → **`com`** → `comprv`/`dco`/`dcopro` → `ctr`/`ctrpro` → `dca` → `dcf` → `pag`.
- **Grano**: una fila = un comparativo de ofertas de una obra.
- **Volumen**: **20.185** en `raw` · 20.186 en Sigrid (foto de la nocturna). Rango 2009-02-06 → 2026-09-08 [RAW vía `con.fec`]; 6.384 desde 2024, 3.881 desde 2025.
- **Se une por**: `ide` → **`raw.con`** (fecha, estado, código) · `obride` → `raw.obr`, **193 obras, 177 en `stg.obras`** · `natide` → `raw.auxpronat` (254 valores) · `dncide` → `raw.dnc` · `empide` → `raw.emp` · `comide` → `com` (revisiones) · `cocide` → `auxobrcoc`, **no ingerida**. Todos los demás destinos están en `raw`; **ninguno en la capa de consumo**.
- **Columnas que importan** (% informado [RAW]): `obride` 99,92 % (193 distintos) · `natide` **99,24 %, 254 distintos — la actividad**, el eje que pide Compras: DRENAJE Y URBANIZACIÓN 3.200, SUBCONTRATA CON APORTE DE MATERIALES 2.678, SUMINISTRO DE MATERIALES 2.186, OBRA COMPLETA 1.458 [SIG] · `dncide` 99,87 % pero **solo 190 distintos** (no hay una necesidad por comparativo: es un contenedor por obra) · `empide` 97,11 % (139) · `comide` 17,41 % (2.563: hay versionado real) · `cocide` 16,85 %, o sea **83 % sin tipo de contrato** [SIG: 16.783 de 20.186 a NULL]. Lo útil de verdad está en `con`: `fec` 100 % y `est` con **17 estados** — APROBADO 18.641, EN ELABORACIÓN 610, APROBADO UTE 256, Aprobado Dir. Compras 171, RECHAZADO JEFE GRUPO 141, RECHAZADO DIR. COMPRAS 125… [RAW vía `raw.conest`].
- **Columnas vacías o inútiles** [RAW, contadas]: `prmide`, `horlim`, `pexide`, `tipsub`, `fecdiv`, `ppoide`, `fecinirec`, `fecfinrec` — **0 de 20.185, las ocho**. Y sus cuatro fechas propias son papel mojado: `fecent` 44 (0,22 %), `feclim` 34, `fecsum` 32, `feccon` 26. **CONTRADICCIÓN DOC/DATO**: el documento promete fecha límite, fecha de contratación y ventana de recepción de ofertas; en Ruesma nadie las rellena. Quien fecha un comparativo usa `con.fec`.
- **Qué permitiría responder que hoy no se puede**: cuántos comparativos se lanzan por obra y actividad y cuánto tardan en aprobarse; qué porcentaje se rechaza y quién lo rechaza; qué obras compran sin comparativo previo.
- **Enrutado**: **F-038** (el modelo) y **F-067** (la pregunta literal de Compras, «comparativos por actividad»). Es la tabla ancla del bloque.

### `raw.comlin` — las líneas del comparativo: qué se pide y a qué precio se adjudicó

- **Cómo funciona** [DOC+SIG+RAW]: cada línea nace de una línea de necesidad (`dncproide`). **No es la matriz de ofertas**: es la línea del concurso, y su `can`/`pre` son **la cantidad y el precio adjudicados**. La oferta de cada proveedor para esa misma línea vive en `raw.dcopro`, que trae `comide` y **`comlinide`** apuntando aquí. Comprobado con un caso real [RAW]: comparativo 2832242 = 9 `comlin` × 3 ofertantes = **27 filas de `dcopro`**. Al adjudicar se rellena `ctride`.
- **Grano**: una fila = una línea del comparativo. `(comide, dncproide)` es único en las 196.811.
- **Volumen**: **196.811** en `raw` · 196.829 en Sigrid. 19.925 comparativos con línea.
- **Se une por**: `comide` → `raw.com` (100 %) · `dncproide` → `raw.dncpro` (100 %, 194.226 distintos) · `ctride` → **`raw.ctr`: 184.945 informados y casan los 184.945**; además tienen línea en `raw.ctrpro` **184.944 de 184.945**. Todo en `raw`; en la capa de consumo solo existe `compras.contratos`.
- **Columnas que importan**: `comide`/`dncproide`/`dncide`/`pos` 100 % · `ctride` **93,97 %** (11.621 contratos) · `can` 96,88 % · `pre` 92,63 % (34.132 precios distintos) · `numlin` 59,23 %. **Importe adjudicado medido**, `SUM(can*pre)`: **1.160 M€** totales, de ellos 1.127 M€ con contrato y 33 M€ sin. Por año: 2023 146,2 · 2024 107,8 · 2025 117,5 · 2026 (a 09-09) 75,9 M€.
- **Columnas vacías o inútiles** [RAW]: `rqsproide` y `dcoproide` **0 de 196.811** (`rqs` está vacía en Sigrid y el enlace a la línea de oferta va al revés, por `dcopro.comlinide`); `canant` 4,75 %.
- **Trampa medida, decirla antes de que alguien sume**: 14.513 líneas con `pre`=0, 6.136 con `can`=0, **4.100 con importe negativo** y 21 por encima de 1 M€. La mayor es **una sola línea de 363 M€** (comparativo 1610000) que dispara 2020 hasta 417 M€ frente a los 50-150 M€ del resto de años. Cualquier mart sobre `comlin` necesita saneado y criterio escrito para esos casos.
- **Qué permitiría responder que hoy no se puede**: cuánto se adjudica por obra, actividad y año **en fase de compra**, antes de que llegue la factura; qué porcentaje de lo comparado acaba en contrato (93,97 % de las líneas); y, con `dcopro`, **cuánto se ahorra entre la oferta más cara y la adjudicada**.
- **Enrutado**: **F-038** primero, **F-067** después. Es la tabla con más valor económico del bloque.

### `raw.comprv` — los proveedores invitados a cada comparativo y su oferta

- **Cómo funciona** [DOC+SIG]: al lanzar el comparativo se invita a N proveedores; cada invitación es una fila con su documento de oferta (`docide` → `dco`). El proveedor responde, la oferta recorre estados y una se acepta. Es lo que convierte un comparativo en un concurso con ganador y perdedores.
- **Grano**: una fila = un proveedor invitado a un comparativo (= una oferta).
- **Volumen**: **70.677** en `raw` · 70.683 en Sigrid. 19.873 comparativos con ofertantes. Ofertantes por comparativo [RAW]: 1→4.026, 2→3.113, 3→3.428, **4→4.345**, 5→1.830, 6→1.249, cola hasta 12+.
- **Se une por**: `comide` → `raw.com` (100 %) · `docide` → **`raw.dco`, casan 70.676 de 70.677** · `prvide` → `raw.prv` (casan las 12.799 informadas) · `refide` → `ref`, **tabla no ingerida**.
- **LA TRAMPA GORDA del bloque**: `prvide` está informado en **12.799 de 70.677 (18,11 %)**. Quien modele «proveedores del comparativo» uniendo por `comprv.prvide` **pierde el 82 % de las ofertas**. El proveedor real sale de **`dco.entide`**, informado en **70.579 (99,86 %)** con **8.742 proveedores distintos** [RAW]. Confirmado en origen [SIG]: `prvide` 12.801 de 70.683 y `docide` 70.683 de 70.683.
- **Y el oro**: el estado de la oferta está en `con.est` con `tip`=12 [RAW vía `conest`]: **Rechazada 45.533 · Aceptada definitivamente 17.655 · Pendiente 3.701 · Recibida 3.560 · Precios solicitados 227**. Importe ofertado (`dco.totdoc`): **3.467 M€** en 67.959 ofertas con importe. El ganador y los perdedores de cada concurso están medidos y hoy nadie los ve.
- **Columnas vacías o inútiles** [RAW y SIG coinciden]: `shrlst`, `tabtec`, `fecndaenv`, `fecndarec` — **0 de 70.677**. La short list y los NDA del documento no se usan.
- **Qué permitiría responder que hoy no se puede**: a cuántos proveedores se pide oferta de media por actividad y obra; qué proveedores ganan y cuáles solo se invitan («comparativos adjudicados a un mismo proveedor con distintas actividades», literal de Compras); la diferencia entre lo ofertado y lo adjudicado.
- **Enrutado**: **F-038** y **F-067**; también **F-055**, porque la tasa de éxito por proveedor es un eje de proveedor de primera.

### `raw.obrprv` — Obras: Proveedores. **VACÍA. No construir nada encima.**

- **Cómo funciona** [DOC]: sería la lista de proveedores por obra, con `cod` y `res`, referenciada por `dncpro.obrprvide` y `obrpro.obrprvide`. En Ruesma no se usa.
- **Volumen**: **0 filas en `raw`** [RAW] y **0 en Sigrid** [SIG]. Triple comprobación en origen: `dncpro.obrprvide` está a 0 en sus **286.728** filas y `obrpro` tiene **0 filas**.
- **Enrutado**: **ninguno**. Residuo del ERP. Lo que el nombre promete —qué proveedores trabajan en qué obra— **ya lo responde `maestro.proveedores_obra`**, construido desde `ctr`. A `objetos_pendientes.yaml`, y candidata a salir de `tables_sigrid.yaml`.

### `raw.prvcer` — certificados del proveedor. **Dato muerto desde 2019.**

- **Cómo funciona** [DOC+SIG]: una fila por certificado presentado por un proveedor, dado de alta a mano en su ficha, con emisión, caducidad y marca de validez. **Dejó de alimentarse**: por año de emisión [SIG] 2013→327, 2015→319, 2017→280, 2018→155, **2019→30, 2020→2**, y nada después.
- **Grano**: una fila = un certificado de un proveedor. **Volumen**: **2.741** en `raw` y **2.741** en Sigrid, idénticos. 1.317 proveedores, **1.316 ya en `maestro.proveedores`** [RAW]: enriquecer sería barato.
- **Columnas que importan**: `conide` 100 % (1.317) · `fec` y `feccad` 99,89 % · `cadval` 48,60 % con **solo 2 valores: es un 0/1** (1.332 a 1) · `cod` 96,39 % con 2.589 valores distintos — el documento lo llama «Código contrato» pero el dato real son números y códigos opacos (`98CAA07A678A1BD7`, `221272`, `AEAT`). **CONTRADICCIÓN DOC/DATO.**
- **Columnas vacías o inútiles**: `pos` es **posición** (múltiplos de 64: 64→1.310, 128→572, 192→277…), **no un tipo de certificado** [SIG]. Ahí está el problema: **`prvcer` no tiene campo de tipo**. Lo único que dice qué es cada certificado es `tex`, **que el ETL excluye en la ingesta** y que en origen sí trae contenido («0327: REFORMA AEAT EN SAN BLAS (MADRID)») [SIG].
- **Vigencia medida** [RAW]: de los 2.741, **1 caduca en 2026 o después**, 32 entre 2020 y 2025 y **2.708 caducaron antes de 2020**. F-066 la dejó escrita como «lo más parecido a un proveedor homologado que Sigrid guarda de verdad»: **esa expectativa hay que corregirla, hoy no homologa a nadie.**
- **Qué permitiría responder que hoy no se puede**: qué proveedores llegaron a certificarse y cuándo dejaron de renovar (auditoría histórica); y, si Compras reactiva la práctica, alertar de caducidades.
- **Enrutado**: **F-055**, como histórico y con la advertencia escrita. Si se publica, hay que **recuperar `tex` en la ingesta** o no se sabe de qué es cada certificado.

### `raw.prvobrpag` — forma de pago pactada con un proveedor para una obra. **6 filas.**

- **Cómo funciona** [DOC]: excepción a la forma de pago general del proveedor (`prv.pagide`) cuando una obra pacta otra. Se rellena a mano.
- **Grano y volumen**: una fila = una excepción proveedor×obra. **6 filas** en `raw` y **6 en Sigrid**: seis proveedores, cinco obras.
- **Se une por**: `conide` → `prv` · `pagide` → `raw.auxpag` · `efeide` → `raw.auxefp` · `obr` es el **código** de obra en texto (`0221`, `0241`…), no un `ide`.
- **Columnas vacías** [RAW]: los siete campos bancarios (`banide`, `banban`, `bansuc`, `bandig`, `bancue`, `ban`) y `delide`, a 0 en las 6; `texF` (columna real en origen, distinta de `tex`) vacía en las 6.
- **Enrutado**: **ninguno con entidad propia**. Seis filas no sostienen un objeto publicado. Si F-067 modela condiciones de pago, esto es un `LEFT JOIN` de excepción de tres líneas. Se queda en `raw` y se declara pendiente.

### `raw.auxpag` — el catálogo de formas de pago. Pequeño, limpio y muy usado.

- **Cómo funciona** [DOC+SIG]: catálogo maestro que edita Administración. Cada forma combina un **medio** (`efeide` → `auxefp`) con un **plazo en días** (`formul`). Lo apuntan el contrato (`ctr.pagide`), la factura (`dcf.pagide`), la oferta (`dco.pagide`) y el proveedor (`prv.pagide`).
- **Grano y volumen**: una fila = una forma de pago del catálogo. **69** en `raw` y **69** en Sigrid, idénticos.
- **Se une por**: es la **dimensión** de `ctr`, `dcf`, `dco`, `prv` y `prvobrpag`. Cobertura medida [RAW]: **18.920 de 18.929 contratos** la tienen y **casan los 18.920**; **165.535 de 165.539 facturas** también. `compras.contratos` y `compras.facturas` ya están publicados y **no la traen**.
- **Columnas que importan**: `cod`, `res` y `formul` 100 % (`formul` son los días: `60`, `120`, `30 450R`…) · `efeide` 100 % con **9 medios** [SIG]: PAGARÉ 21 formas, CONFIRMING/PAGARÉ 13, SÓLO CONFIRMING 11, TRANSFERENCIA 7, LETRA 6, RECIBO 5, CHEQUE 4, EFECTIVO 1, TARJETA 1. Top en contratos [RAW]: Pagaré 120 (5.269), Pagaré 90 (2.367), Pagaré 120 + retención (2.284), Confirming TR 150 + ret (1.342).
- **Columnas vacías o inútiles** [RAW]: `fecbaj`, `reccod`, `can`, `cat`, `ser` — **0 de 69**; `pos` 44,93 %. `tiemod` 68,12 % (aquí sí existe y el incremental funciona).
- **Qué permitiría responder que hoy no se puede**: a cuántos días paga cada obra y cada proveedor; cuánto del gasto va por confirming y cuánto por pagaré; y, cruzando `formul` con `dcf.fecdoc`, el **vencimiento teórico** de la deuda con proveedores.
- **Enrutado**: **F-067** (las condiciones del contrato que pide Compras) y **F-037** (convierte una factura en un vencimiento previsto). **La tabla más barata del bloque**: 69 filas y cobertura del 99,95 % sobre objetos ya publicados.

### `raw.deffir` — la definición del circuito de firma. Configuración, no dato.

- **Cómo funciona** [DOC+SIG+RAW]: define, por **proceso** (`cod`) y **escalón** (`pos`), qué **roles con qué peso** firman, cuántos **puntos** hacen falta y de qué **estados iniciales** a qué **estado final** salta el documento. Es la plantilla que explica las 70.063 firmas reales de `raw.confir`.
- **Grano y volumen**: una fila = un escalón del circuito de un proceso. **17** en `raw` y **17** en Sigrid.
- **Se une por**: `cod` ↔ `raw.confir.cod`; **los 4 códigos casan** [SIG]: **COMVAL** 55.476 firmas / 16.250 documentos (comparativos), **COAVAL** 10.360 / 3.334, **DOCVAL** 3.440 / 1.720 (facturas, `contip`=15), **OBRHOJ** 796 / 118 (obras).
- **Columnas que importan**: `cod`, `pos`, `roles` y `puntot` 100 % (`roles` con 7 combinaciones: `JEFO(2),JG(3),DCOM(6)`, `JEFOUTE(1),JGINE(2),JGUTE(3),DCOM(4)`…) · `estini` y `estfin` 94,12 % · `contip` 35,29 % (solo las 6 de DOCVAL).
- **Columnas vacías o inútiles** [RAW]: `impmin`, `impmax`, `fil`, `filxjs`, `ord`, `tipele`, `impdivcod`, `numemp`, `tipint`, `noenvcor` — **0 de 17**. Es decir: **el circuito NO depende del importe**, que es justo lo que el documento sugiere con `impmin`/`impmax`. **CONTRADICCIÓN DOC/DATO.**
- **Qué permitiría responder que hoy no se puede**: quién tenía que firmar un comparativo y quién firmó; cuántos escalones y cuánto tarda cada uno; qué documentos están parados a mitad de circuito.
- **Enrutado**: **F-055** y **F-067**, siempre **junto a `confir`**. Sola no responde nada: es la **leyenda** de `confir`, una vista de decodificación y no un mart.

## Lo que yo construiría, y en qué orden

1. **`auxpag` como dimensión de condiciones de pago, ya.** 69 filas, catálogo limpio, cobertura del 99,95 % sobre `ctr` y `dcf`, y los dos objetos que la necesitan (`compras.contratos`, `compras.facturas`) **ya están publicados**: es añadir forma de pago y días a lo que existe. Coste casi nulo y tapa una de las cuatro carencias del correo de Compras. → **F-067**.
2. **El hecho del comparativo: `com` + `comlin` + `comprv`, con `con`, `dco` y `auxpronat`.** Es el bloque con contenido real: 20.185 comparativos, 196.811 líneas, **1.160 M€ adjudicados**, 70.677 ofertas con **estado ganador/perdedor** y 3.467 M€ ofertados, cruzable por **obra** (177 de 193 ya en `stg.obras`) y por **actividad** (`natide`, 99,24 %). Responde literalmente las dos preguntas de Compras sobre comparativos. → **F-038**, y **F-067** encima. Tres condiciones que la spec debe recoger o el mart mentirá: el proveedor sale de **`dco.entide` (99,86 %)** y **no** de `comprv.prvide` (18,11 %); la fecha y el estado salen de **`con`**, no de `com`; y `comlin` necesita **saneado** (14.513 precios a 0, 4.100 negativos y una línea de 363 M€ que por sí sola duplica 2020).
3. **`dcopro` cerrando la matriz oferta×línea.** No es de mi bloque, pero sin ella el comparativo no compara: `dcopro.comlinide` es lo que permite decir «se pidieron 4 ofertas para esta línea, la más cara era X y se adjudicó Y». Ya está en `raw` desde F-066; debe entrar con el punto 2 o F-038 queda a medias.
4. **`deffir` + `confir` como una sola pieza.** Juntas responden «quién tenía que firmar, quién firmó y qué está parado». → **F-055**.
5. **`prvcer`, solo como histórico y con advertencia.** 2.708 de 2.741 certificados caducaron antes de 2020 y la práctica murió en 2019: sirve para auditar el pasado, no para homologar hoy. Si se publica, **recuperar `tex` en la ingesta**. → **F-055**, prioridad baja, y **corregir la expectativa que dejó escrita F-066**.
6. **`obrprv` y `prvobrpag`: no construir.** `obrprv` tiene **0 filas en origen** y sus dos referencias también a cero; lo que promete ya lo da `maestro.proveedores_obra`. `prvobrpag` tiene **6 filas**. Las dos a `config/objetos_pendientes.yaml` con el motivo escrito, y `obrprv` es candidata a salir de `tables_sigrid.yaml`.

**Un arreglo aparte, que no depende de ninguna feature de negocio**: quitar `incremental_column: tiemod` de `com`, `comlin` y `comprv` en `config/tables_sigrid.yaml`. **Esa columna no existe en Sigrid** (comprobado en `INFORMATION_SCHEMA` y con el error 42S22 del servidor), `_source_tiemod` está a NULL en las tres y el ETL degrada en silencio (`ingest_raw_step.py:279`): la declaración es falsa y oculta que esas 287.673 filas se recargan enteras cada noche.
