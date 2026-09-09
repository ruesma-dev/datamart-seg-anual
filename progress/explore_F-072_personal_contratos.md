# F-072 · Censo semántico de `raw` — bloque PERSONAL, CONTRATOS Y FIRMAS

2026-09-09. **Solo lecturas**: `SELECT` sobre `raw` en transacción `READ ONLY` y
`SELECT` contra Sigrid vivo por `sigrid-api`. Cero escrituras.
**Fuente de cada afirmación**: `[doc]` = `azure-apps/sigrid_tablas.md` · `[api]`
= medido contra Sigrid · `[raw]` = medido sobre Postgres.
**Datos personales**: de `emp` y `res` no sale ni un valor, ni por `raw` ni por
la pasarela. Solo recuentos, distintos, % informado y rangos de fecha.

Recuentos `raw`/Sigrid `[raw][api]`: `emp` 1.353/1.353 · `res` 2.616/2.616 ·
`conact` 7.095/7.096 · `conest` 193/193 · `confir` 70.063/70.072 · `auxpronat`
514/514. La deriva es la actividad del día.

---

### `raw.conest` — el catálogo que traduce el estado de CUALQUIER documento de Sigrid

- **Grano**: una fila por (tipo de documento, estado posible). 193 filas, 29 tipos.
- **Volumen**: 193 en `raw` y en Sigrid.
- **Se une por**: **`(tip, est)` → `(con.tip, con.est)`** `[doc]`, no por `ide`;
  pareja única, 0 duplicados `[raw]`. `con` YA está en el datamart, y de él
  cuelgan `ctr`, `dcf`, `com`, `dco` y `pag`, que toman de ahí tipo y estado.
- **Columnas que importan** `[doc]` + % `[raw]`: `tip` 100 % (29 valores) es el
  TIPO DE DOCUMENTO, no el tipo de estado; `est` 99,48 % (54 valores) es lo que
  aparece en `con.est`; `cod` y `res` 99,48 % la sigla y el nombre; `edi`/`edirol`
  41,97 % dicen si el documento se puede editar en ese estado y qué rol —28
  estados de comparativo quedan bloqueados salvo rol ADM y 10 de factura salvo
  DIRADM `[api]`—; `esigcod` 10,88 % es el código del portal.
- **Cobertura del `JOIN` declarado** `[raw]`: contratos tip 44 18.929/18.929 ·
  facturas tip 15 165.539/165.539 · comparativos tip 46 20.185/20.185 · ofertas
  tip 12 72.260/72.260 · albaranes tip 14 309.927/309.937 · efectos tip 25
  254.856/254.856. La relación de `[doc]` se cumple.
- **Lo que NO tiene catálogo, y no es un hueco**: tipos 20 (783.847 documentos),
  19 (184.230), 61 (58.280), 3 (55.179), 16 (44.778, plan de cuentas) y 17
  (34.148) tienen un solo valor de `est`: **no tienen estado** `[raw]`.
- **Catálogo con basura** `[api]`: de los 32 estados definidos para el
  comparativo solo 17 los usa algún documento; de los 21 de factura, 18; los 7
  del contrato, los 7.
- **Columnas vacías** `[raw]`: `cladef`, `format`, `cla`, `sitaso`, `comporweb` a
  cero en las 193 filas; `tab` en 2; `subtip` en 5.
- **Cómo funciona**: tabla de configuración que mantiene Administración, no la
  mueve el uso diario. El documento nace en `con` con un `est` inicial y cada
  acción lo **sobrescribe en el sitio**: `con.est` guarda un único valor, el
  actual. Quien lo empuja es la firma: `confir.estfin` es el estado al que salta
  el documento al alcanzar los puntos `[api]`. Contratos hoy: FIR firmado 13.424,
  TER terminado 3.179, EPF **enviado 809**, PFP pdte. de envío 559, RFP recibido
  551, COMD 232, RES rescindido 176 `[api]`.
- **HISTÓRICO: confirmado que NO existe** (responde a F-047/F-067). `conest` es
  catálogo, no log; no hay columna de fecha de cambio de estado en `con` ni en
  `ctr` `[doc]`; lo más cercano es `con.tiemod`, informada en 2.137.862 de
  2.184.663 documentos (97,9 %) `[raw]`, que dice cuándo se tocó el documento, no
  cuándo entró en su estado. **La foto diaria de F-067 hace falta y no hay atajo.**
- **Qué permitiría responder**: «¿cuántos contratos están enviados y sin firmar?»
  (809, hoy, sin esperar a la foto diaria); «¿qué facturas están rechazadas o
  retenidas?»; «los comparativos aprobados de esta obra». Hoy `compras.contratos`
  ni siquiera publica el estado.
- **Enrutado**: **F-067**, lo primero del bloque. También F-038 y F-055.

---

### `raw.confir` — el circuito de firma: quién aprueba, con cuántos puntos y en qué orden

- **Grano**: una fila por firma exigida a un rol sobre un documento, firmada o no.
  70.063 filas, 21.419 documentos, 23.610 bloques `[raw]`.
- **Volumen**: 70.063 en `raw`, 70.072 en Sigrid.
- **Se une por** `[doc]`: `conide` → `con.ide` (**en el datamart**) y por él a
  `com` y `dcf`, ya en `compras`; `docide` → `con.ide` de tipo 12, la **oferta de
  compra** (`dco`, en `raw` sin consumidor). Verificado `[api]`: de 64.592 firmas
  con destino, **64.369 (99,65 %) apuntan a una oferta del MISMO comparativo**,
  sobre 21.270 ofertas. Es el enlace comparativo → oferta adjudicada, y no está
  en ningún otro sitio del modelo.
- **Columnas que importan** `[raw]`: `cod` 100 %, 4 valores, es el proceso —
  COMVAL 55.467 y COAVAL 10.360 sobre comparativos, DOCVAL 3.440 sobre facturas,
  OBRHOJ 796 sobre obras—; `rol` 100 %, 12 valores; `fir` 85,10 %; `fec`/`hor`
  85,11 %; `usu` 85,11 % (135 usuarios); `totimp` 99,92 %; `idbloque` 100 %
  agrupa la ronda; `pun`/`puntot`/`estfin` son el motor (ver «cómo funciona»).
- **Dos circuitos están muertos** `[raw]`: **DOCVAL (facturas) no tiene ni una
  fecha ni una firma marcada** en sus 3.440 filas: declarado y jamás usado.
  **OBRHOJ (obras) se abandonó**: última firma 2020-01-29. Lo vivo es solo el
  comparativo: firmas del 2015-12-09 al 2026-09-08, de 731 en 2016 a 7.543 en 2024.
- **CONTRADICCIÓN doc / dato real** `[raw]`: `[doc]` describe un circuito con
  ventana temporal e intervinientes; `ord`, `fecdes`, `hordes`, `fechas`,
  `horhas`, `tipint` y `noenvcor` están **a cero en las 70.063 filas**. `fas`
  0,52 %; `firok` 27,47 %.
- **Cómo funciona** (cruzando `[doc]` con `[api]`): al abrir un comparativo
  Sigrid crea de golpe **un bloque `idbloque` con una fila por rol**, todas sin
  fecha. Cada rol aporta **puntos** al firmar y el documento salta a `estfin`
  cuando se alcanza `puntot`. Circuito estándar `puntot`=6 con JEFO 2, JG 3 y
  **DCOM 6** —dirección de compras puede aprobar sola— más variantes de 5, 7, 10
  y 13 puntos para UTEs, instalaciones y Aldara/Inesco `[api]`. **`pun` = -1 es
  el rechazo** (519 firmas). `estfin`=5 es «APROBADO» en el catálogo de
  comparativos: la firma es lo que escribe `con.est`.
  **Orden real, medido y no declarado** `[api]`: dentro del mismo bloque DCOM
  firma después de JEFO en 15.488 de 15.489 casos, después de JG en 14.721 de
  14.727, y JEFO antes que JG en 11.143 de 14.697. La cadena es **jefe de obra →
  jefe de grupo → dirección de compras**.
  **El contrato NO pasa por aquí**: 0 firmas de tip 44 `[api]`. Lo que se firma en
  Sigrid es el comparativo previo; el contrato cambia de estado a mano.
- **Qué permitiría responder**: **cuánto tarda en aprobarse un comparativo** —
  sobre 19.205 comparativos con más de una firma fechada, **mediana 6 días, media
  11,3, máximo 515** `[raw]`—; qué está atascado y en quién (pendientes: JG 3.124,
  DCOM 2.063, JEFO 1.017 `[raw]`); y qué oferta se llevó cada comparativo.
- **Enrutado**: **F-055** (el eje «quién aprueba» que buscaba en `PFfir`, vacía) y
  **F-067**. El enlace `docide` → oferta es material de **F-038**.

---

### `raw.conact` — qué hace cada proveedor: la actividad, que en Ruesma vive aquí

- **Grano**: una fila por pareja (proveedor, naturaleza de producto).
- **Volumen**: 7.095 en `raw`, 7.096 en Sigrid.
- **Se une por** `[doc]`: `conide` → `con.ide` / `prv.ide` (**las dos en el
  datamart**; `maestro.proveedores` se construye sobre `prv`), `actide` →
  `auxpronat.ide`. Verificado `[api]`: 7.086 de 7.096 cuelgan de un proveedor
  real (99,86 %) y **7.096 de 7.096 casan con `auxpronat`**.
- **Cobertura real** `[raw]`: 4.769 proveedores clasificados de los **9.563 de
  `prv` = 49,9 %**. Media 1,49 actividades: 3.482 con una, 782 con dos, 275 con
  tres, uno con 17. Cinco filas cuelgan de conceptos que no son proveedores.
- **CONTRADICCIÓN doc / dato real**: `[doc]` declara `homolo` «Homologada» y `tot`
  «Importe homologado»; **las dos están a cero en las 7.096 filas** `[raw][api]`:
  la homologación **no existe como dato en Ruesma**. Igual las cinco marcas de
  tipo (`tipfab`, `tipdis`, `tipsmo`, `tipsub`, `tipins`), informadas en 36 a 68
  filas, menos del 1 %: no clasifican a nadie.
- **Cómo funciona**: la fila la teclea Compras en la ficha del proveedor al darlo
  de alta o revisarlo; no la genera ningún documento y **no tiene marca de
  modificación** `[doc][raw]`, así que no hay forma de saber cuándo se clasificó a
  nadie. No es un paso del ciclo del contrato: es un atributo estable que el
  comparativo consulta.
- **Qué permitiría responder**: «¿qué proveedores de fontanería trabajan en la
  obra X?»; «¿cuánto gastamos por actividad?» cruzando con `compras.facturas`;
  «¿de cuántas actividades depende un solo proveedor?».
- **Enrutado**: **F-055**, con el aviso de que el eje es parcial: la mitad de los
  proveedores no está clasificada.

---

### `raw.auxpronat` — el catálogo de naturalezas de producto: el eje por el que Compras agrupa

- **Grano**: una fila por naturaleza de producto / actividad. 514 filas.
- **Volumen**: 514 en `raw` y en Sigrid. **105 (20,4 %) no las usa nadie** `[raw]`.
- **Se une por** `[doc]`: `ide` ← `conact.actide`. Sus códigos de cuenta enlazan
  con la contabilidad (`cua`, en `raw` sin consumidor, es de F-056).
- **Columnas que importan** `[raw]`: `cod` 100 % y único; `res` 100 % pero con
  **335 valores distintos de 514** (descripciones repetidas entre familias);
  `caagascod` (cuenta analítica de gasto) **79,77 %, 169 valores**; `cuacomcod`
  (cuenta de compras) **78,21 % pero solo 11 valores**; `tiemod` 85,60 %, de las
  pocas del bloque con marca de modificación.
- **Hallazgo que no está en ninguna ficha: hay una jerarquía escondida en el
  prefijo del código**, un eje de agrupación de primer nivel que hoy no existe.
  Medido `[raw]` (naturalezas / asignaciones): MA 118/1.875, SM 106/2.521, SB
  102/1.179, QA 26/308, QC 25/26, QR 25/19, CICO 20/293, CIMO 16/36, CIMJ 13/144,
  CIMP 13/46, CIIN 11/49, XA 10/88, CITE 8/391, CISS 7/67, XC 7/31, CIOI 6/22.
  Las familias `CI**` (costes indirectos: notarios, técnicos, seguros) **no
  tienen ni cuenta analítica ni de compras**; MA, SM, SB, QA, QR y XA la tienen
  casi todas. Esa asimetría es información de negocio.
- **Columnas vacías** `[raw]`: 11 a cero, entre ellas `fecbaj` (**ninguna
  naturaleza está de baja**, confirmado `[api]`), `numemp`, `tippro`, `clapro`,
  `conide` y cinco de las siete cuentas.
- **Cómo funciona**: catálogo de Compras. Una naturaleza no se borra nunca —de
  ahí las 105 sin uso—; `tiemod` es lo único que dice cuándo se tocó. No
  participa en el ciclo del documento: se consulta desde `conact`.
- **Qué permitiría responder**: gasto por actividad y por familia; y, por
  `caagascod`, **cuadrar el gasto de compras contra la cuenta analítica de la
  contabilidad**, que sería la primera vez.
- **Enrutado**: **F-055** como dimensión; el puente de cuentas, a F-056/F-058.

---

### `raw.res` — «recursos»: y **un recurso no es una persona en casi la mitad de los casos**

- **Grano**: una fila por recurso, `ide` compartido con `con` tip 33 `[doc]`,
  2.616 de 2.616 `[raw]`. Código y nombre legibles salen de `con.cod`/`con.res`.
- **Volumen**: 2.616 en `raw` y en Sigrid. **1.723 (65,9 %) de baja** por
  `con.fecbaj` `[raw]`; el criterio de Juan Romero es que no se consideran.
- **EL HALLAZGO DEL BLOQUE**, medido `[api]` cruzando `res.cla` con el catálogo
  `auxrestip` (**no ingerido**, 37 filas): `cla`=1 son **1.353 personas** (oficial
  1ª albañil 177, encargado 119, gruista 111, jefe de obra 100, ayte. jefe de
  obra 78, capataz 62, peón 55…); `cla`=0 son **1.157 CONSUMOS imputables**
  (teléfono móvil 392, caja de obra 263, gasoil 184, kilómetros 140, vehículos
  123, viajes 26, alquiler de piso 6); `cla`=2 son **106 MEDIOS** (vehículos 36,
  casetas 13, maquinaria 6, grúas 2). Es decir: `res` **no es el maestro de
  personal**, es el maestro de todo lo imputable a obra por parte de trabajo. Y
  `hmores` no son solo horas: el catálogo `auxhor` (60 filas, **tampoco
  ingerido**) mezcla HORA LABORABLE OFICIAL (72.219 líneas) con MES VEHICULO
  (7.852), CONSUMOS TELEFONO MOVIL (20.299) y KILOMETROS (3.506) `[api]`.
  **Sumar `hmores` sin separar por `cla` da una cifra falsa.**
- **Se une por** `[doc]`, verificado `[api]` y `[raw]` con idéntico resultado:
  `ide` → `con` (en el datamart) y ← `hmores.reside` (en `raw`, sin consumidor):
  **1.982 recursos (75,8 %) aparecen en algún parte y solo 10 líneas de `hmores`
  quedan huérfanas** `[raw]`. `conide` → `emp.ide` en 823 filas, las 823 casan;
  `emp.reside` → `res` en 804, las 804 casan: **no es 1:1 en ninguna dirección**
  y F-057 tiene que elegir cuál manda. `prvide` → `prv` en 508 (87 proveedores)
  para el recurso externo; `restipide` → `auxrestip` 78,67 % y `horide` →
  `auxhor` 77,71 %, **ninguna de las dos ingerida**.
- **Trampa**: `cenconide` informada al 75,54 % pero con **9 valores distintos**:
  no sirve para atribuir a obra. La obra está en `hmores.obride`.
- **CONTRADICCIÓN doc / dato real** `[raw]`: 30 columnas a cero en las 2.616
  filas. `[doc]` describe control de acceso, validación de partes, fichajes y
  cesión de maquinaria; **todas vienen vacías** (`logacc`, `ideacc`, `ipacc`,
  `recema`, `hmoacc`, `valhmo`, `hmoval`, `hmoreside`, `hmoresside`, `ficacc`,
  `ficpun`, `maqide`, `maqobr`, `maqcen`). `res` **no dice quién valida un parte**
  ni **si el recurso es maquinaria**: eso solo se deduce de `cla` y `restipide`.
- **Cómo funciona**: el recurso nace como concepto `con` tip 33 cuando alguien lo
  necesita para imputar; si es persona se le ata su ficha por `conide`, si es
  externo se le ata el proveedor. Después **solo lo mueven los partes**: `hmo`
  abre la cabecera (obra, año, mes) y `hmores` cuelga la línea con recurso, tipo
  de hora, cantidad e importe. Cuando la persona causa baja, el que se marca de
  baja es el concepto `con`, no `res` `[raw]`. **No tiene `tiemod`**: se recarga
  entera cada noche.
- **Restricción de privacidad**: trae el NIF en `cif` (614 valores distintos).
  Publicable: clase, clasificación, si es externo, su proveedor y el alta/baja.
  **No** el NIF; si hace falta identificar a la persona aguas abajo, un
  identificador interno estable. **Cualquier objeto construido con esta tabla
  hereda la restricción**: no puede exponer datos personales identificativos.
- **Qué permitiría responder**: «¿cuántas horas de oficial y cuántas de peón
  lleva la obra X?»; «¿qué parte del coste imputado es personal, qué parte
  consumos y qué parte medios?» (por `cla`); «¿qué recursos activos no han
  imputado nada este año?».
- **Enrutado**: **F-057**, la pieza sin la cual `hmores` es una lista de
  identificadores; y **F-061**, a la que da el corte propio/externo y el corte
  persona/consumo/medio.

---

### `raw.emp` — la ficha de personal: 152 columnas de las que 62 vienen vacías

- **Grano**: una fila por empleado, `ide` compartido con `con` tip 43 `[doc][raw]`.
- **Volumen**: 1.353 en `raw` y en Sigrid. 152 columnas; en Sigrid son 161 y
  F-066 excluye 11 de binario o texto ilimitado, la foto incluida.
- **Se une por** `[doc]` + % `[raw]`: `ide` → `con` (**en el datamart**); `reside`
  → `res` 804 de 804; `cenide` → `cen` 66,52 % (**`cen` está**, 15 valores);
  `munide` → `auxmun` 73,24 % y `proide` → `auxpro` 73,32 % (**las dos están**);
  `cetide` 75,17 % → `cet` **no ingerida**; `dptide` 73,10 % → `auxdpt` **no
  ingerida**, cuyo contenido `[api]` es directamente el organigrama: personal
  operario 492, jefes de grupo/obra 178, oficina 109, encargados 98, capataces
  57, técnicos de prevención 30, administrativos de obra 25. `caaide` 66,52 % →
  `caa` **no ingerida**.
- **Columnas que importan y NO son personales** `[api][raw]`: `numemp` informada
  al 100 % pero con **17 valores** — 961 fichas en la empresa 1 (509 sin fecha de
  baja, altas de 1989-11-02 a 2026-03-09), 288 en la 28 (18 sin baja), y tres
  sociedades sin ninguna fecha de alta; `fecalt` 86,25 %, rango global
  1981-06-11 a 2026-03-09; `fecbaj` 57,72 %, rango 2010-03-21 a 2026-06-30, lo
  que deja **572 fichas sin fecha de baja**; `ulthis` 75,17 % es la fecha del
  último cambio de su historial laboral. **Ojo**: `con.fecbaj` marca de baja solo
  52 fichas —es la baja del CONCEPTO, no la laboral—; la buena es `emp.fecbaj`.
- **Trampa medida** `[raw]`: `paiide` informada al 57,87 % con **2 valores
  distintos**; `bantipide` al 26,16 % con 3. Informado no es informativo.
- **CONTRADICCIÓN doc / dato real** `[raw]`: `[doc]` describe una ficha de RRHH
  completa —disponibilidad para viajar, poderes, i-Sigrid, MenfisNet, Gestiona3W,
  teléfonos y despacho de empresa—. **62 de las 152 columnas están a cero o nulo
  en las 1.353 filas**, incluidas las tres de contraseña (`esigpas`,
  `esigpasmnet`, `g3wpas`, **vacías**), las diez de `tra*`, `cargo`, `telmov`,
  `teldir`, `delide`, `retpor`, `legajo`, `numtar`, `modtrab`, `estocu` y
  `podact`. En Ruesma el módulo de RRHH de Sigrid está mayoritariamente sin usar.
- **Cómo funciona**: la ficha nace con el alta y **se sobrescribe**; lo que
  guarda historia no está aquí sino en `emphis` (ver el cierre). `ulthis` y
  `ulthco` son punteros a la fecha del último cambio de ese histórico y de sus
  complementos. No participa en el ciclo del contrato de compras: el `emp` de
  `ctr.empide` es solo quién tramitó el documento. **No tiene `tiemod`**: se
  recarga entera cada noche.
- **Restricción de privacidad**: informadas y sensibles —descritas por lo que
  son, sin un solo ejemplo— la columna del DNI (99,19 %), la del número de la
  Seguridad Social (86,55 %), la de la cuenta bancaria completa (72,80 %, más
  banco, sucursal y dígitos de control), domicilio y código postal (82 %), fecha
  de nacimiento (85,81 %), correo (45,31 %), teléfono (49,45 %), sexo (75,24 %) y
  estado civil (45,97 %) `[raw]`. **Nada de eso sube a la capa de consumo.**
  Publicable: recuentos por empresa, centro y departamento, antigüedad y
  condición de alta o baja, **agregado y nunca por persona**. **Cualquier objeto
  construido con esta tabla hereda la restricción**, y eso incluye no publicar
  cruces que permitan reidentificar (empresa + centro + fecha de alta con un solo
  empleado detrás).
- **Qué permitiría responder**: «¿cuánta plantilla activa hay por empresa y por
  departamento?»; «¿cuál es la rotación por año?»; «¿qué parte de la plantilla
  imputa horas a obra?», cruzando con `res` y `hmores`.
- **Enrutado**: **F-057** para la dimensión despersonalizada y **F-061** para el
  reparto del coste; no antes de que F-057 escriba la política de publicación.

---

## El ciclo del contrato, de punta a punta

Reconstruido cruzando `[doc]` con `[api]`; no sale de mirar columnas.

1. **El proveedor se clasifica** en `conact` → `auxpronat`: dato estable, sin
   fecha, y solo lo tiene el 49,9 %.
2. **Nace el comparativo** (`com`, `con` tip 46) en estado CURS «en elaboración».
   Sus ofertas son documentos aparte (`dco`, `con` tip 12, 72.260, con estados
   propios: Pendiente, Precios solicitados, Recibida, Rechazada, Aceptada
   definitivamente `[api]`).
3. **Se abre el bloque de firma**: `confir` crea de golpe una fila por rol, sin
   fecha. Firman en orden **jefe de obra → jefe de grupo → dirección de compras**
   (medido sobre ~15.000 bloques `[api]`), sumando puntos hasta `puntot` —6 en el
   circuito estándar, y DCOM sola ya vale 6—. `pun` = -1 es rechazo. Mediana del
   recorrido completo: **6 días** `[raw]`.
4. **La firma escribe el estado**: `confir.estfin` = 5 = «APROBADO» en el
   catálogo de comparativos, y `confir.docide` apunta a la **oferta adjudicada**
   (99,65 % del mismo comparativo `[api]`).
5. **Se genera el contrato** (`ctr`, `con` tip 44): 11.439 de 18.930 (60,4 %)
   traen `comide` al comparativo de origen, 18.920 traen obra y 18.888 proveedor
   `[api]`. **El contrato NO entra en `confir`**: 0 firmas de tip 44. Su estado lo
   mueve una persona a mano: PFP → EPF enviado → RFP recibido → COMD → FIR
   firmado → TER terminado, o RES rescindido.
6. **Y ahí se pierde el rastro**: no queda registro de CUÁNDO ocurrió cada salto.
   Además `ctr.fecvig1`/`fecvig2`, que `[doc]` llama vigencia del contrato, están
   informadas en **5 de 18.930** `[api]`: no sirven ni de aproximación.

---

## Lo que yo construiría, y en qué orden

1. **`stg` de estados de documento sobre `conest`** (193 filas, clave
   `(tip, est)`). Lo más barato del bloque y lo que más desbloquea: responde hoy
   la primera pregunta del correo de Compras —809 contratos enviados y sin
   firmar— y da nombre al estado de 165.539 facturas y 20.185 comparativos.
   **F-067.** Dos avisos obligatorios en la ficha: la traducción va por
   `(tip, est)` y usar la fila de un contrato para una factura da un nombre
   plausible y falso; y 15 de los 32 estados de comparativo no los usa nadie.
2. **La actividad del proveedor: `auxpronat` + `conact`**, con la **familia por
   prefijo del código** como nivel superior, que hoy no existe. **F-055.** La
   ficha debe decir que solo el 49,9 % de los proveedores está clasificado y que
   la homologación no se informa.
3. **Las firmas de comparativo desde `confir`**: plazo de aprobación, atasco por
   rol y enlace `docide` a la oferta adjudicada. **F-055 + F-067 + F-038.**
   Publicar **solo** el circuito de comparativos: el de facturas nunca se usó y
   el de obras murió en 2020; publicarlos invita a la IA a contar ceros y
   llamarlos «pendiente».
4. **`res` como maestro de recursos despersonalizado**, sin `cif` y **con `cla`
   como corte de primer nivel**. **F-057.** Es lo que convierte las 328.760
   líneas de `hmores` en horas por obra; sin `cla` y `auxhor`, sumar `hmores`
   mezcla horas de albañil con recibos de móvil.
5. **`emp` en último lugar y solo agregado.** Es el mayor volumen de dato
   personal del datamart y 62 de sus 152 columnas están vacías: el trabajo es
   decidir qué se publica, no escribir SQL.

**Lo que hay que pedir aunque no sea de F-072** (todo `[api]`, todo fuera de la
ingesta actual): **`auxrestip`** (37 filas) y **`auxhor`** (60) son las que
convierten un índice en «oficial 1ª albañil» y «hora extra gruista», y sin ellas
el punto 4 no se puede escribir; **`cet`** (40 filas; y su columna `cod`, que
`[doc]` declara, **no existe** en Sigrid) y **`auxdpt`** (7) nombran centro de
trabajo y departamento. Y dos hallazgos mayores del bloque «contratos», que
aparecieron buscando el histórico de estados: **`emphis`, 1.633 filas, es el
histórico laboral del empleado** —1.017 empleados, de 1989-11-02 a 2026-06-01,
tipo de contrato al 100 %, fecha de vencimiento en el 38,8 %, horas contratadas
en el 22,5 %—, **el único sitio de Sigrid con historia de contrato de verdad**; y
**`reshor`, 8.949 filas, es el precio de coste por recurso y tipo de hora**,
justo el multiplicador que a F-061 le falta para pasar de horas a euros. Las dos
son datos de nómina: entran, si entran, con la misma restricción que `emp`.
