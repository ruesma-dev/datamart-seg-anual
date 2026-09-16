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

## T2 · Fase RED (obligatoria en nivel `estandar`)

Los dos ficheros de test se escribieron **antes** de tocar el SQL y el YAML.
Comando exacto y salida real, con el arbol todavia sin una sola linea de
implementacion (commit `5f2ec80`):

```
$ python -m pytest tests/test_f083_sql.py tests/test_f083_diccionario.py -q
...
FAILED tests/test_f083_sql.py::test_f083_publica_el_estado_de_la_factura[estado_id]
FAILED tests/test_f083_sql.py::test_f083_el_estado_id_se_lee_de_la_superclase_con
FAILED tests/test_f083_sql.py::test_f083_la_traduccion_filtra_el_tipo_de_documento_de_factura
FAILED tests/test_f083_sql.py::test_f083_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id
FAILED tests/test_f083_sql.py::test_f083_la_traduccion_del_estado_no_puede_multiplicar_filas
FAILED tests/test_f083_sql.py::test_f083_publica_la_fecha_de_la_propia_factura
FAILED tests/test_f083_sql.py::test_f083_publica_la_fecha_de_alta_con_nombre_inequivoco
FAILED tests/test_f083_diccionario.py::test_f083_la_ficha_nombra_las_dos_columnas_que_se_confunden
FAILED tests/test_f083_diccionario.py::test_f083_cada_fecha_se_distingue_de_las_otras_dos[fecha]
30 failed, 23 passed in 0.82s
```

La traza completa de los tres criterios centrales, sin resumir:

```
_______ test_f083_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id ________
>       lateral = _lateral_del_estado()
tests\test_f083_sql.py:192:
    def _lateral_del_estado() -> str:
        bloque = _bloque_facturas()
>       assert "LEFT JOIN LATERAL" in bloque, (
E       AssertionError: `compras.facturas` no traduce el estado con un lateral:
E       sin el no hay guarda de grano (criterio 3)
E       assert 'LEFT JOIN LATERAL' in 'DROP TABLE IF EXISTS compras.facturas
E       CASCADE; CREATE TABLE compras.facturas AS SELECT f.ide AS factura_id,
E       ... FROM raw.dcf f JOIN raw.con con ON con.ide = f.ide LEFT JOIN
E       raw.con prv_con ON prv_con.ide = NULLIF(f.entide, 0); '
tests\test_f083_sql.py:238: AssertionError

________ test_f083_la_traduccion_del_estado_no_puede_multiplicar_filas ________
>       lateral = _lateral_del_estado()
tests\test_f083_sql.py:213:
E       AssertionError: `compras.facturas` no traduce el estado con un lateral:
E       sin el no hay guarda de grano (criterio 3)
tests\test_f083_sql.py:238: AssertionError

_______________ test_f083_publica_la_fecha_de_la_propia_factura _______________
>       assert "compras.fn_sigrid_date(f.fecdoc) AS fecha_factura" in _bloque_facturas(), (
E       AssertionError: `fecha_factura` es la fecha que el proveedor pone en su
E       documento y sale de `dcf.fecdoc`, informada en el 99,95 % de las facturas

________ test_f083_la_ficha_avisa_de_que_las_dos_fechas_casi_nunca_coinciden ___
>       assert "77,8" in texto, (
E       AssertionError: la ficha tiene que traer la cifra medida el 2026-09-16:
E       las dos fechas se separan en el 77,8 % de las facturas (129.012 de
E       165.783), con mediana de 4 dias y p95 de 42
E       assert '77,8' in 'Cabecera de las facturas recibidas de proveedor. ...'
tests\test_f083_diccionario.py:218: AssertionError
```

**23 de los 53 pasaban ya en rojo, y es lo que se buscaba**: son los que
vigilan que las diez columnas de siempre siguen ahi, en su orden y con su
expresion. Un test de no-regresion tiene que estar verde ANTES del cambio; si
hubiera fallado en esta pasada, el que estaria mal seria el test.
