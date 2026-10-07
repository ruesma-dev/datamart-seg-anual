<!-- progress/spec_F-085.md -->
# F-085 · Mediciones del spec-author (2026-10-07)

Todo medido el 2026-10-07 en **solo lectura**: Sigrid por `sigrid-api`
(`POST /api/sql/read`, `truncated = false` en todas las respuestas) y el
Postgres de Azure por el MCP (`SELECT`). Ninguna escritura. Los scripts de
medición quedaron en el scratchpad de la sesión, no en el repositorio.

## 0. Lo que cambia la ficha, en una frase

**`rac` («Contabilización de documentos») es el registro de PROCESOS de Sigrid
—la ventana «Procesos» de la captura de Carmen Calle—, y responde «quién hizo
qué y cuándo» para las CUATRO familias con una sola fuente**: cada fila es un
paso con su proceso, el estado de ORIGEN (`est1`) y DESTINO (`est2`), el login
(`usu`), la fecha (`fec`) y la hora (`hor`). Hoy se ingiere filtrada
(`asiide <> 0`) y por eso se tiran justo los pasos de comprobar y aprobar.
**`dbo.log` deja de hacer falta para esta pregunta** y `confir` queda como el
detalle del circuito de firmas del comparativo, que ya publica F-038.

## 1. `rac` sin filtro

| Medida | Valor |
|---|---|
| Filas | **2.517.791** (con `asiide <> 0`: 758.927; en `raw` anoche: 758.699) |
| Documentos distintos | 922.075 |
| Rango de `fec` | 2008-11-22 → 2026-10-07 |
| `fec` vacía / `hor` vacía / `usu` vacío | 0 / 2 / 0 |
| Logins distintos | 228 |
| `conproide` = 0 (proceso fuera de catálogo) | 215.865 (8,6 %; 138.932 son de efectos) |
| `fir` <> 0 | **0** (la firma digital NO está en `rac`) |
| `tex` informado | 49.258 (45.982 son cierres por lotes, tipo 306) |
| `datpro`, `conaccide`, `dogide` <> 0 | 0, 0, 0 |
| `nodesa` <> 0 | 266.825 (casi todo en pasos de contabilizar; significado sin confirmar) |

**Por tipo de documento** (`con.tip`), filas / documentos:
factura 15: 873.527 / 166.838 · albarán 14: 613.983 / 305.813 · efecto 25:
552.050 / 233.527 · oferta 12: 148.932 / 68.406 · **contrato 44: 69.065 /
18.539** · **comparativo 46: 63.190 / 19.822** · 11: 47.074 · 306 (cierres):
45.982 · 708: 37.432 · 24: 18.288 · 5: 14.629 · 35: 11.938 · 54: 9.555 ·
**obra 42: 4.491 / 666** · resto < 5.000. 84 filas huérfanas (sin `con`).

**Por proceso**, los principales (tipo, proceso, `est1`→`est2`, filas):

- Factura: Comprobar factura 1→2 (130.462), Contabilizar 2→3 (130.048, el
  único con asiento: 129.074), Aprobar 3→4 (127.863), 4→5 (124.191), 5→6
  (124.471), 6→10 (120.632); serie GG: Comprobar 20→25 (33.725), Contabilizar
  25→30 (33.084), Aprobar 30→10 (22.462); Aprobación directa Dirección, Rechazar
  factura (238+233+104), Pasar a aprobación, y las variantes Aldara, Mascaró,
  Inesco, Ruesma, maquinaria y Jefe Fábrica (desde 2026-07).
- Contrato: Enviar para la firma 1→3 (18.534), Recibido 3→5 (17.603),
  Comprobar documentación 5→6 (12.721), Firmado 6→7 (12.489; y 5→7, 4.345,
  antes de 2016-02), Terminado 7→8 (3.183), Anular enviado 3→9 (124),
  Rescindir 7→9 (54).
- Comparativo: Validar 1→2 (19.950), Aprobación Jefe Grupo 2→3 (18.777),
  Adjudicación compras 3→5 (18.080), Adjudicación directa 2→5 (792), rechazos,
  vueltas a elaboración, cancelación de firmas, y los circuitos de
  instalaciones (100→…) y UTE (11→…, 111→…).
- Obra: Presentada 1→3, Adjudicada provisional 3→7, definitiva 7→9, En curso
  9→15, Terminada 15→19, Recibida provisional 19→21, definitiva 21→23, Cerrada
  23→25 (~470-625 cada uno).

`conpro` («Procesos de Conceptos», 302 filas, 29 tipos) es el **catálogo de
transiciones**: por tipo, `est`→`est2`, nombre (`res`) y `perniv` (los roles que
PUEDEN lanzarlo, p. ej. `JEFO,AYJEFO,ADM,DAOB,JGJO` en «Aprobar factura» 3→4).
No dice qué rol tenía quien lo lanzó. `rac.res` ya trae el nombre del proceso
en cada fila, también en las 215.865 sin catálogo: **`conpro` no hace falta**
para publicar el historial.

### La FR26/10025 sale tal cual (documento 2843469, `con.est` = 5)

| `rac.ide` | Proceso | `est1`→`est2` | Usuario | Fecha y hora | `asiide` |
|---|---|---|---|---|---|
| 2605997 | Comprobar factura | 1→2 (REC→COM) | jmvargas | 28/09/2026 16:52:11 | 0 |
| 2605998 | Contabilizar factura | 2→3 (COM→CON) | jmvargas | 28/09/2026 16:52:50 | 2843515 |
| 2612420 | Aprobar factura | 3→4 (CON→APJO) | ialvarez | 05/10/2026 16:23:32 | 0 |
| 2612564 | Aprobar factura | 4→5 (APJO→APRJG) | jmsanchez | 05/10/2026 16:58:15 | 0 |

Las cuatro filas de la captura, al segundo. Con el filtro actual en `raw` solo
está la segunda. Las horas son las de pantalla (hora local de Madrid).

## 2. ¿Es una HISTORIA de estados? Sí (sección para el líder: afecta a F-067)

Por documento, ordenando sus pasos por `fec`, `hor`, `ide`:

| Familia | Docs con pasos | Último `est2` = `con.est` | Cadena continua (`est1` = `est2` anterior) |
|---|---|---|---|
| Factura 15 | 166.840 | 166.771 (**99,96 %**) | 163.238 (97,8 %) |
| Contrato 44 | 18.539 | 18.537 (**99,99 %**) | 18.536 |
| Comparativo 46 | 19.822 | 19.819 (**99,98 %**) | 19.734 (99,6 %) |
| Obra 42 | 666 | 666 (100 %) | 666 |

**Documentos SIN pasos**: están en su estado inicial, nunca procesados —
facturas 99 (74 REC, 25 RECGG), contratos 554 (todos PFP), comparativos 604
(511 en 1, 75 en 11, 18 en 100) y obras 257 (229 en 1; 28 en 9, de 2015-2017,
la única excepción). Es decir: **cobertura ~100 % de lo que ha salido del estado
inicial**.

**Deshacer proceso BORRA el paso de `rac`** (ver §3): `rac` es la historia
NETA —el camino que el documento recorrió de verdad—, y `dbo.log` la bruta.

**Para el líder (NO se toca F-067 en esta spec):**

- La premisa de F-067, de la ficha de `compras.historial_estados` y de
  `docs/ARCHITECTURE.md` («la fecha en que un documento cambia de estado no
  está en Sigrid») **es falsa**: está en `rac` desde 2008, al segundo y con
  usuario. La foto diaria (línea base 2026-10-07) sigue siendo válida, pero ya
  no es la única fuente.
- Ejemplo de lo que cambia: **809 contratos en EPF** hoy; los 809 tienen en
  `rac` la fecha EXACTA del envío; **785 llevan más de 21 días** (media
  3.192 días: hay muchos zombis antiguos). `compras.v_estado_documentos` dirá
  «al menos 0 días» hasta el 2026-10-28.
- Contratos firmados desde 2025: 2.543, **42,9 días de media** del envío a la
  firma.
- Propuesta: tras F-085, una feature aparte (o reabrir F-067) para que
  `v_estado_documentos.en_estado_desde` salga del último paso de `rac` y la foto
  quede como respaldo. Decisión D7 de la spec.

## 3. Contraste con `dbo.log` y con `confir`

**`dbo.log`, las operaciones** (cotejadas con `rac` documento a documento):

| `ope` | Qué es | Evidencia |
|---|---|---|
| 1 | Alta del documento | primera fila de cada documento; `res` = proveedor (su nº) |
| 3 | Modificación (guardar) | sin cambio de estado; minutos después del alta o de un paso |
| **5** | **Ejecutar un proceso** | sep-2026: 6.906 de 7.514 de factura casan con `rac` al segundo (contrato 1.069/1.182, comparativo 832/879, obra 10/10); el resto, 1 s de desfase o pasos deshechos |
| 24 | Firma digital | 1 s antes del paso que firma; «ERROR al validar FIRMA DIGITAL» = la firma falló |
| **30** | **Deshacer proceso** | contrato CTSB25/0002: 4×30 y luego 4×5 tres veces; en `rac` solo quedan los 4 últimos. Factura FR26/09111: una aprobación del 21-09 deshecha el 23-09 no está en `rac` |
| 2 | ¿Baja? | 21 de 63 documentos ya no existen en `con` (sin confirmar) |

Resuelve las preguntas 7 y 9 de la ficha: **la 5 y la 3, las dos sin `res`
útil, son «proceso» y «modificación»**, y casar acción con estado lo hace
`rac` (`est1`→`est2`), no hace falta inferirlo. La pregunta 8 sigue igual:
`log.est` no es el estado del documento.

**`confir`** (70.883 filas en `raw` anoche), por circuito:

| Circuito (`cod`) | Familia | Filas | Firmadas (`est` 2, con fecha) | Sin firmar (`est` 0) |
|---|---|---|---|---|
| COMVAL | comparativo | 56.200 | 50.805 | 5.395 |
| COAVAL | comparativo (ampliación) | 10.438 | 9.328 | 1.110 |
| OBRHOJ | obra | 796 | 203 (2009-2020) | 593 |
| DOCVAL | factura | 3.474 (1.737 facturas) | **0** | 3.474 |

Las seis preguntas de `confir`:
1. `fir` = 1 firmada; `est` = 2 firmada / 0 sin firmar (coinciden); `firok` = 1
   marca la firma que CIERRA el bloque (16.139 COMVAL, 3.119 COAVAL).
2. `ord` vale **0 siempre**: no hay orden. El circuito es por **puntos**: cada
   rol aporta `pun` y el bloque (`idbloque`, uno por propuesta) se cierra al
   llegar a `puntot`.
3. `deffir` (17) = definición de cada ventana de firma: circuito, roles con sus
   puntos (`JEFO(2),JG(3),DCOM(6)`), `puntot`, estados desde los que se abre
   (`estini`) y estado al que lleva (`estfin`). `impmin`/`impmax` a 0 en todas.
4. **Las 3.474 de factura no son firmas pendientes**: 1.692 de sus 1.737
   facturas (97,4 %) ya están en APR (aprobado pago). Son peticiones de firma de
   Dirección (DOCVAL, DIRGEN/DIRPRO) que nunca se firmaron por esa vía: la
   factura se aprobó por proceso, y eso está en `rac`.
5. `estfin` no es un estado final por documento: es el destino del circuito,
   copiado de `deffir` en cada firma.
6. `pun`/`puntot` = puntos; `propu` = la propuesta (nº, oferta OC y
   proveedor); `totimp` = su importe. No hay escalado por importe.

**De qué fuente sale «quién aprobó qué y cuándo», por familia:**

| Familia | `rac` (pasos con usuario y fecha) | `confir` | `dbo.log` |
|---|---|---|---|
| Factura | **166.840 de 166.936 (99,94 %)**; 152.789 con paso de aprobación | 0 % fechadas: no sirve | 302.238 firmas digitales (ope 24): solo dice si se firmó digitalmente |
| Contrato | **18.539 de 19.093 (97,1 %; los 554 restantes, en PFP)** | nada | redundante (ope 5) |
| Comparativo | **19.822 de 20.426 (97,0 %)** | 60.133 firmas fechadas: detalle por escalón, pendientes, propuesta e importe (ya en `compras.comparativo_firmas`) | redundante |
| Obra | **666 de 923 (72,2 %; 229 sin procesar)** | 203 firmas de hoja de obra, 2009-2020 | redundante |

**`dbo.log` deja de hacer falta** para esta feature. Lo único suyo que `rac` no
tiene: la marca de firma digital (`ope` 24; 302.238 de factura frente a 537.474
pasos de aprobación en `rac`, o sea que no todas las aprobaciones se firman
digitalmente), el alta (1), las modificaciones (3) y los pasos deshechos (30).
Eso es la trazabilidad de F-105, que ya existe en el backlog para ingerir
`dbo.log`. Se propone dejarlo allí (D5).

## 4. Coste de quitar el filtro

- Anoche (`_meta.v_raw_state`): `raw.rac` 758.699 filas en **75 s**; 113 MB.
- Banco de lectura por la pasarela, 3 páginas de 10.000 filas en tres puntos
  del rango de `ide`: sin filtro y sin `tex`, **14.154 filas/s**; con `tex`,
  18.809; con el filtro actual, 10.195. Sin filtro: 2,52 M de filas ≈ **3 a 4
  min de ingesta (+2 a 3 min)** y ≈ **375 MB (+260 MB)** a 156 B/fila.
- **La ventana de referencia de la ficha está desfasada**: la nocturna del
  2026-10-07 (batch `20261007T000024Z-1d969c`) duró **4 h 37 min 44 s**
  (00:00:24 → 04:38:08 UTC): `ingest_raw` 47 min, `build_stg` 53, `build_mart`
  86, `build_compras` 15, `build_cierre` 51. Ya está 38 min POR ENCIMA de las 4
  h de referencia, no 19 por debajo. F-085 añade ~3 min de ingesta y lo que
  tarde el nuevo SQL de compras (a medir en T de verificación). Riesgo a
  enseñar al humano, no causado por esta feature.
- **Quién depende del `where`**: `retenciones/03_apuntes_contables.sql` ya
  filtra en SQL (`WHERE r.asiide <> 0 AND r.conide <> 0`, CTE `rac_asiento`):
  no cambia de resultado. F-091 está `pending` y su enlace factura→asiento será
  `WHERE asiide <> 0` en su propio SQL. `check-raw-recuentos` aplica el `where`
  declarado, así que contará la tabla entera sin tocar código. Tests que fijan
  el filtro: `tests/test_f095_retenciones_contables.py::test_f095_r9_rac_declarada_con_filtro`
  (`where == "asiide <> 0"`) y `test_f095_r28_raw_rac_y_orden_de_magnitud`
  (la ficha menciona `asiide <> 0`).
- Recuentos: ingerir `conpro`, `usu` o `rol` subiría el censo de 71 tablas, que
  fijan cinco tests (`TOTAL_TABLAS` en f066 y f074, f097, f095 r31, f107) y tres
  documentos. **No hace falta ninguna** (§1 y §5): el censo se queda en 71.

## 5. Datos personales: `tex` y `usu`

- **`rac.tex`** (texto ilimitado; máx. 374 bytes en lo medido): en facturas es
  el MOTIVO de un rechazo o de un «pasar a aprobación» (561 y 373 filas) y
  «Recontabilizada». Barrido de patrones: 0 NIF, 1 correo, 3 teléfonos en 2.890
  filas de factura; el del correo es **un email pegado entero con nombres,
  cargos y direcciones de correo de terceros** (no se transcribe aquí). En
  proveedores (tipo 5) «Cambiar CIF a entidad» lleva CIF, que en un autónomo es
  un NIF. **Recomendación: seguir excluyéndolo** (D3).
- **`usu` es un login** (`jmvargas`): dato personal leve, ya publicado en
  `compras.comparativo_firmas.usuario`, `compras.comparativos.aprobado_por` y
  `compras.documento_comentarios.usuario`, y legible hoy en `raw.rac` y
  `raw.confir`. Se resuelve a persona en la tabla `usu` de Sigrid (233 filas:
  `cod` login, `res` nombre, `codemp` empleado… **y `cla` contraseña y `dni`**):
  137 de los 192 logins de estas familias están en ella (93 % de las filas).
  `usu` no se ingiere y no se propone ingerirla aquí: si se quiere el nombre, es
  `personal` y F-105 (D4).
- `rol` (49 filas) traduce los códigos de rol (`JEFO` jefe de obra, `JG` jefe de
  grupo, `DCOMPRAS`…), pero `rac` no dice con qué rol actuó cada usuario: el rol
  sale del NOMBRE del proceso («Aprobar factura Jefe Grupo Aldara») y del estado
  destino (APJO, APRJG, APRADM…). No se ingiere.

## 6. Propuesta de modelo (detalle en la spec)

Una tabla, `compras.documento_procesos`: **una fila por paso de `rac`** de
factura, contrato, comparativo y obra, con documento, código, proceso, estado
de origen y destino traducidos (`compras.fn_estado_documento`), usuario,
momento, asiento, orden dentro del documento, si encaja con el paso anterior y
si es el último. Clave `paso_id` (`rac.ide`). Se reconstruye cada noche, como el
resto de `compras`. `raw.rac` pasa a ingerirse sin filtro y sin `tex`.
`confir` y `dbo.log` no cambian.

Decisiones abiertas para el humano (con recomendación, en `design.md`):
D1 quitar el filtro de `raw.rac` · D2 qué familias · D3 `tex` · D4 login sin
nombre · D5 `dbo.log` a F-105 · D6 `confir` como está · D7 F-067 y su premisa ·
D8 `conpro`/`rol` sin ingerir.

## 7. `acceptance` de F-085: lo que la medición contradice

1. El criterio 3 («si se ingiere `dbo.log`… con 19 min de margen») parte de dos
   premisas falsas: `dbo.log` no hace falta (lo cubre `rac`), y el margen ya es
   negativo (4 h 38 min anoche). Se reescribe.
2. El criterio 2 pedía declarar la fuente de cada familia: se mantiene, ahora
   con `rac` como fuente de las cuatro.
3. Se añade la reproducción de la FR26/10025 como prueba de aceptación.

El `status` NO cambia (`pending`): la spec la aprueba el humano.
