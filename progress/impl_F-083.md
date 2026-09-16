<!-- progress/impl_F-083.md -->
# F-083 · El estado de la FACTURA (y sus dos fechas) · informe de implementacion

Rama `feature/F-083-estado-de-la-factura`, rigor `estandar`, `sdd=false`: el
contrato son los **ocho criterios de `acceptance`** de la ficha, **mas la
ampliacion de alcance que el humano decidio a mitad de tarea**: entran tambien
las dos fechas de la factura, separadas y declaradas en el diccionario
(«la fecha metela, y separa las 2. Luego debe quedar muy claro en el
diccionario»).

## Plan de tareas (no hay `tasks.md`: esta es la lista)

- [x] **T1** · Medir en SOLO LECTURA contra `raw` lo que hace falta antes de
  escribir SQL: estado informado, reparto entre los 21 estados del tipo 15,
  huerfanos contra el catalogo, unicidad del par `(tip, est)` y —por la
  ampliacion— cobertura de `dcf.fecdoc` y separacion real entre las dos fechas.
- [ ] **T2** · Fase RED: `tests/test_f083_sql.py` y `tests/test_f083_diccionario.py`
  escritos ANTES del codigo, con la traza roja pegada aqui.
- [ ] **T3** · El SQL: bloque FACTURAS de `sql/compras/01_documentos.sql`
  —estado (id, codigo y literal) por `LATERAL ... LIMIT 1` con `tip = 15`, mas
  `fecha_factura` y `fecha_alta`—. Lo minimo, que el fichero es de F-067.
- [ ] **T4** · El diccionario: fichas de las seis columnas nuevas, la
  contraposicion con `compras.vencimientos` y `version` 22 -> 23.
- [ ] **T5** · `bash harness/init.sh` en verde, campana de mutacion, evidencias
  e informe cerrado.

## T1 · Lo medido (2026-09-16, solo lectura, `filas_solo_lectura` READ ONLY)

El MCP **no expone `raw`** (esquemas autorizados: mart, cierre, stg, compras,
maestro, retenciones, aux, _meta), asi que la medicion va con el cliente del
propio proyecto en transaccion `READ ONLY`. Script:
`scratchpad/medir_f083.py` (no se versiona).

**El universo**: 165.866 facturas en `raw.dcf`, las 165.866 con fila en
`raw.con` y **las 165.866 con `tip = 15`** (ni una con otro tipo). Y
`compras.facturas` publica hoy exactamente esas **165.866** filas: ese es el
numero que el criterio 3 obliga a conservar.

**El estado (criterio 4)**: informado en **165.866 de 165.866 (100 %)** —cero
nulos y cero ceros—, y **cero huerfanos**: los 18 valores presentes casan todos
con el catalogo `tip = 15`. Reparto medido:

| est | codigo | estado | facturas |
|----:|---|---|---:|
| 10 | APR | Aprobado pago | 151.668 |
| 30 | CONGG | Fra. GG Contabilizada | 10.607 |
| 105 | APR UTE | Aprobada pago final Ute Inesco | 856 |
| 50 | FRAAPR | Factura aprobada | 752 |
| 6 | APRADM | Aprobada Administracion | 653 |
| 5 | APRJG | Aprobada Jefe de grupo | 553 |
| 3 | CON | Contabilizada | 259 |
| 4 | APJO | Aprobada por jefe de obra | 193 |
| 15 | RECH | Rechazada | 164 |
| 1 | REC | Recibida | 69 |
| 115 | APR_DG | Aprobado Pago | 45 |
| 20 | RECGG | Fra. GG. Recibida | 25 |
| 2 | COM | Comprobada | 8 |
| 104 | APJGINE | Aprobada Jefe Grupo Inesco | 5 |
| 101 | APGER | Aprobada Gerente Grupo Mascaro | 4 |
| 113 | APR_JFAB | Aprobada Jefe Fabrica | 2 |
| 100 | APJGA | Aprobada Jefe de grupo (Aldara) | 2 |
| 25 | COMGG | Fra. GG Comprobada | 1 |

**Tres de los 21 estados del catalogo no los usa ninguna factura**: `FRARET`
(40, «Factura retenida»), `REC_ADM` (110) y `APR_ADM` (114). Importa decirlo
porque el correo pregunta explicitamente por las **retenidas**: la respuesta
honesta hoy es «cero facturas en `FRARET`», no «no se puede saber».

**La guarda de grano (criterio 3)**: `(tip, est)` es unico en `raw.conest`
—21 filas y 21 estados distintos para `tip = 15`— y **no hay un solo par
duplicado en todo el catalogo** (0 de 193). El `JOIN` no multiplica hoy; la
vista no puede depender de eso, y por eso va con `LATERAL ... LIMIT 1`.

**Las dos fechas (ampliacion, criterio 4 extendido)**:

- `dcf.fecdoc` informada en **165.786 de 165.866 (99,95 %)**; 80 sin ella.
- `con.fec` informada en **165.863 de 165.866**; 3 sin ella.
- **Coinciden en 36.771 (22,2 %) y se separan en 129.012 (77,8 %)**: cuatro de
  cada cinco facturas tienen dos fechas distintas. Esto solo ya justifica
  separarlas.
- Desfase `fecha_alta - fecha_factura`: **mediana 4 dias**, media 10,43, p95
  **42 dias**. Tramos: 1-7 dias 75.102; 8-30 38.922; 0 dias 36.771; 31-90
  8.762; **mas de 90 dias 3.352**; negativo 2.874.
- **Dato sucio declarado, no corregido**: el minimo es **-89.824 dias** y el
  maximo **3.804**. Hay `fecdoc` tecleados a mano imposibles. No se filtra
  nada —publicar es publicar— pero la ficha avisa de que la fecha del documento
  la teclea quien recibe la factura y admite valores absurdos.
