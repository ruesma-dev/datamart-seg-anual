<!-- progress/spec_F-067.md -->
# F-067 · Spec: mediciones, decisiones y recomendaciones

Spec-author, 2026-10-06. Spec en `specs/F-067-compras-seguimiento-mcp/`. Absorbe
F-125 (código 2 y documento de necesidades). Todo en SOLO LECTURA y cero
escrituras: Sigrid por `sigrid-api` (`leer_sql`, ~45 consultas) y los esquemas
de consumo de Azure por el conector MCP (solo `SELECT`).

**Herramienta que falló, y cómo se rodeó sin improvisar nada que escriba**: la
conexión `psycopg` directa al Postgres de Azure dio `connection timeout` dos
veces (IP pública del puesto, probablemente fuera del firewall:
ver la memoria «IP del puesto y firewall del Postgres»). Lo de `raw` se midió
en el ORIGEN (Sigrid, del que `raw` es copia nocturna con `--full`), y lo de
`compras`/`descompuestos` por el MCP. Lo único que queda sin medir en `raw` es
el tipo exacto de `raw.con._ingested_at` (lo comprueba el implementer en
`postgres_client.py`). Si el humano quiere el contraste en `raw`, basta añadir
la IP y repetir las consultas de §1 en sesión `READ ONLY`.

## 1 · Lo medido (Sigrid, 2026-10-06, salvo donde se dice)

### Albarán → necesidad: el enlace es DIRECTO, no por `docoritip`

`dcapro` tiene **`dncide` y `dncproide`** (también `ctrpro`, `dcfpro`, `dcopro`;
`comlin` ya lo publica F-038). `docoritip` NO sirve: sus valores son 0 (766.035),
44 contrato (395.876), 14 albarán (821) y 13 (139).

| | líneas |
|---|---|
| `dcapro` total | 1.162.871 |
| con `dncproide` | **378.010 (32,5 %)**, casan con `dncpro` las 378.010 |
| con `dncide` | 378.102; coherente con el `dncide` de su línea de necesidad: 378.010 de 378.010 |
| `dncide` = el de la obra de la línea (`obr.dncide`) | 377.020 de 378.010 |
| albaranes (cabecera) con alguna línea con necesidad | 108.148 de 312.333 |

**El «~6 %» de Negocio** casa con las líneas que NO vienen de contrato:
`docoritip = 0` → 38.804 de 766.035 con necesidad (**5,1 %**). Entre las que
vienen de contrato es el 85,6 % (338.951 de 395.876). Por año la cobertura
total va del 33 % (2018) al 33-42 % (2024-2026). Se corrige el acceptance 8.

### El código 2 (`cod2`)

| tabla | filas | con `cod2` |
|---|---|---|
| `dcapro` | 1.162.871 | 357.349 (30,7 %), 20.488 valores |
| `ctrpro` | 246.103 | 151.082 (61,4 %) |
| `dcfpro` | 1.099.136 | 262.579 (23,9 %) |
| `dncpro` | 290.567 | 213.352 (73,4 %) |

En albaranes de 2026, el 41,6 % (55.590 de 133.604); por mes entre 39 % y 47 %
(«una de cada cinco» de Juan se queda corto). **Viaja de la necesidad al
albarán**: de las 378.010 líneas enlazadas, 295.210 traen código 2 y en 294.860
(**99,9 %**) es igual al de su línea de necesidad; 347 distintos. También hay
código 2 sin necesidad (62.139 líneas): se escribe a mano. Los valores son
libres y sin normalizar (`HORMIGON`, `HORM`, `HORM.`, `SUM HGÓN`...): la ficha
lo dice. El caso de Juan: albaranes **`AC26/28510`** y **`AC26/28514`** del
30-09-2026, proveedor MOMOSA CONSTRUCCIONES (ide 2765765), líneas con
`docoritip = 0` (sin contrato) y `cod2 = 'MOMOSA'`, casi todas con necesidad.

### El documento de necesidades (`dnc`) = el DPC de la obra

277 documentos, `con.tip = 36`, código `0727.0` (el de la obra), nombre = el de
la obra. **Uno por obra**: 274 con `obride` y 271 son el `obr.dncide` de su
obra. Estado: los 277 «En curso» (`E`), no informa. 290.567 líneas `dncpro`, 6
sin partida, 898 en un `dnc` al que no apunta ninguna obra (por eso
`v_pbi_planif_jo` tiene 289.408 y no 290.567).

### `descompuestos` (MCP, Azure)

- PLANIF_JO: 289.408 líneas, 213.043 con `codigo_alternativo` = `dncpro.cod2`.
- Master (obra de 5.290 líneas de planificación, todas sus versiones): de
  110.329 líneas de MASTER_PLANIF_JO con `dncpro_id`, 104.740 casan con una
  línea de PLANIF_JO y en **103.016 (98,4 %)** el código alternativo es el mismo;
  el resto, editados después de la versión. Es el código 2 de la fecha de la
  versión. MASTER_ESTUDIO y ESTUDIO: 12.160 de 107.061 y 7.763 de 11.783 con
  código. (Una consulta sobre todo el master excedió el tiempo del MCP: la tabla
  es grande y se midió por obra.)

### El contrato

- **Forma de pago**: `ctr.pagide` en 19.072 de 19.081.
- **Retención**: `ctrrec` con concepto `RET%` en 6.333 contratos (6.334 filas;
  uno con dos). 558368 «Retención garantía 5 % (sobre base imponible)» 6.172;
  `valpor` 0,05 en 6.135. Otros conceptos: IRPF (`190`, `180`), sin código.
- **Penalización**: no hay campo en `ctr`. En el texto del contrato (`con.tex`,
  ya publicado en `compras.documento_texto`) aparece «penaliz» en **9** de los
  1.624 contratos con texto. Pregunta para Compras: dónde la escriben.
- **Estado**: 807 contratos en EPF hoy (F-084 publicó 818 el 16-09).

### `con.tiemod` y la foto diaria

- `tiemod` es un **número de Delphi** (días desde 1899-12-30): 46300,537627 =
  2026-10-05 12:54. SQL Server con `CAST(... AS datetime)` usa época 1900-01-01
  y da **dos días más** (2026-10-07, imposible hoy): trampa para quien mida.
- **La firma no mueve `tiemod`**: de 19.778 comparativos con firma fechada, solo
  en **3.032 (15 %)** `tiemod` es igual o posterior a la última firma (y eso
  con los dos días de más a su favor). Así que `tiemod` ni siquiera es una cota
  de la fecha del cambio de estado. Base de D2.
- 795 de los 807 EPF no se han modificado en 21 días por `tiemod`; 778 en 90.
  Con lo anterior, ese número no se puede leer como «lleva 21 días enviado».
- Volumen de la foto: 19.081 contratos + 166.673 facturas = **185.754**
  documentos. Documentos (15/44) modificados por día, 24-09 a 05-10: 31-131
  facturas y 0-15 contratos. Los cambios de estado son un subconjunto.

### Comparativos (acceptance 3, MCP)

`compras.comparativos`: 20.380 comparativos, `actividad_id` en 20.227 (253
actividades), ganadora única en 17.866, 2.503 sin ganadora, 1 con dos. Con
contrato y sin ganadora: 877. Proveedores ganadores: 4.188, de ellos **1.535 con
comparativos de más de una actividad** (14.637 comparativos; máximo 50
actividades). Las dos preguntas de Compras se responden hoy con una consulta.

## 2 · Lo que la medición cambia de la ficha

1. Acceptance 2: el proxy `tiemod` no es proxy de la antigüedad del estado; la
   antigüedad sale de la foto, y «más de tres semanas» es cierto desde el día
   21 tras el despliegue (el tramo de línea base es un mínimo).
2. Acceptance 3: ya resuelto por F-038; solo fichas y preguntas.
3. Acceptance 8: cobertura medida (32,5 % total, 5,1 % sin contrato) y enlace
   directo `dcapro.dncproide`, no `docoritip`/`linoriide`.
4. Acceptance 12: el caso de Juan tiene códigos (`AC26/28510`).

## 3 · Decisiones de diseño tomadas aquí (no del humano)

- La foto se guarda **por tramos** (desde/hasta): es la foto diaria decidida,
  sin repetir lo que no cambia; ~20 MB y < 50.000 filas/año frente a 68 M
  filas y ~6 GB/año de una fila por documento y día.
- Convivencia con `--full`: `--full` solo trunca `raw`; las dos tablas son las
  primeras persistentes de `compras` (`CREATE TABLE IF NOT EXISTS`, nunca
  `DROP`/`TRUNCATE`/`DELETE`), con guardas contra ingesta a medias (98 %) y
  contra relanzar sin ingesta nueva.
- Tipos en la foto: contrato (44) y factura (15). El comparativo no: sus firmas
  ya tienen fecha (F-038).
- `codigo_alternativo` se llama igual en `compras` y en `descompuestos`; la
  ficha lo rotula «código 2».
- `necesidad_id` en `descompuestos` solo en las dos vistas, por subconsulta a
  `raw.dncpro`: tocar `lineas` o `03` cambia el sello y retrocea el master.

## 4 · Decisiones que son del humano (recomendación)

- **D1 · Una entrega o dos.** Recomiendo **una**, con la foto como primera
  tarea: la historia empieza el día del despliegue y cada noche de retraso no
  se recupera. Si prefiere dos, al revés de lo que sugería el encargo: **Fase 1
  = foto + contratos**, Fase 2 = código 2 + necesidades (que no pierden nada
  por esperar).
- **D2 · `tiemod` como `fecha_ultima_modificacion` del contrato.** Recomiendo
  **publicarla** (el humano la pidió como mínimo aceptable el 2026-09-09) con la
  advertencia medida, y **no usarla nunca para la antigüedad del estado**.
  Alternativa: no publicarla.
- **D3 · Código 2 y necesidad también en líneas de contrato y de factura.**
  Recomiendo **sí** (61 % y 24 % con código 2; mismo SQL).
- **D4 · Acceptance 4 (proveedores por actividad «validada») a F-055.**
  Recomiendo **sí**: `conact` es de F-055 y «validada» no existe (`homolo = 0`).
  Si se aprueba, el líder ajusta el acceptance 4 de F-067 y el de F-055.

## 5 · Frontera con otras features

- F-083/F-080/F-084: no se reimplementa nada; `contratos` gana columnas al final.
- F-038: no se toca su SQL; solo ficha y preguntas de `comparativos`.
- F-055: proveedores por actividad (D4).
- F-085: «quién aprobó». Además, `dbo.log` (149.010 registros de contrato) podría
  rellenar la historia ANTES del despliegue; sustituiría tramos de línea base.
