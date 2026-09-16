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
- [x] **T2** · Fase RED: `tests/test_f083_sql.py` y `tests/test_f083_diccionario.py`
  escritos ANTES del codigo, con la traza roja pegada aqui.
- [x] **T3** · El SQL: bloque FACTURAS de `sql/compras/01_documentos.sql`
  —estado (id, codigo y literal) por `LATERAL ... LIMIT 1` con `tip = 15`, mas
  `fecha_factura` y `fecha_alta`—. Lo minimo, que el fichero es de F-067.
- [x] **T4** · El diccionario: fichas de las cinco columnas nuevas, la
  contraposicion con `compras.vencimientos` y `version` 22 -> 23.
- [x] **T5** · `bash harness/init.sh` en verde, campana de mutacion, evidencias
  e informe cerrado.

## T1 · Lo medido (2026-09-16, solo lectura, `filas_solo_lectura` READ ONLY)

El MCP **no expone `raw`** (esquemas autorizados: mart, cierre, stg, compras,
maestro, retenciones, aux, _meta), asi que la medicion va con el cliente del
propio proyecto en transaccion `READ ONLY`. Script:
`scratchpad/medir_f083.py` (no se versiona).

**El universo**: 165.866 facturas en `raw.dcf`, todas con fila en `raw.con` y
todas con `tip = 15`. `compras.facturas` publica hoy esas mismas **165.866**
filas: ese es el numero que el criterio 3 obliga a conservar.

**El estado (criterio 4)**: informado en **165.866 de 165.866 (100 %)** —cero
nulos y cero ceros—, y **cero huerfanos**: los 18 valores presentes casan todos
con el catalogo `tip = 15`. Reparto medido:

APR «Aprobado pago» 151.668, CONGG 10.607, APR UTE 856, FRAAPR 752, APRADM
653, APRJG 553, **CON «Contabilizada» 259**, **APJO 193**, **RECH
«Rechazada» 164**, REC 69, APR_DG 45, RECGG 25, COM 8, APJGINE 5, APGER 4,
APR_JFAB 2, APJGA 2 y COMGG 1. El reparto entero, con sus literales, queda
publicado en la ficha de `compras.facturas.estado` del diccionario.

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
- **Dato sucio declarado, no corregido**: el desfase va de **-89.824** a
  **+3.804 dias**. `fecdoc` la teclea una persona y admite fechas imposibles.
  No se filtra nada —publicar es publicar—: lo avisa la ficha.

## T2 · Fase RED (obligatoria en nivel `estandar`)

Los dos ficheros de test se escribieron **antes** de tocar el SQL y el YAML.
Comando exacto y salida real, con el arbol todavia sin una sola linea de
implementacion (commit `5f2ec80`):

```
$ python -m pytest tests/test_f083_sql.py tests/test_f083_diccionario.py -q
...
FAILED tests/test_f083_sql.py::test_f083_el_estado_id_se_lee_de_la_superclase_con
FAILED tests/test_f083_sql.py::test_f083_la_traduccion_filtra_el_tipo_de_documento_de_factura
FAILED tests/test_f083_sql.py::test_f083_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id
FAILED tests/test_f083_sql.py::test_f083_la_traduccion_del_estado_no_puede_multiplicar_filas
FAILED tests/test_f083_sql.py::test_f083_publica_la_fecha_de_la_propia_factura
FAILED tests/test_f083_diccionario.py::test_f083_cada_fecha_se_distingue_de_las_otras_dos[fecha]
   (y otros 24, entre ellos las cinco columnas sin ficha y las tres fechas)
30 failed, 23 passed in 0.82s
```

La traza completa de los tres criterios centrales, sin resumir:

```
_______ test_f083_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id ________
>       lateral = _lateral_del_estado()
tests	est_f083_sql.py:192:
    def _lateral_del_estado() -> str:
        bloque = _bloque_facturas()
>       assert "LEFT JOIN LATERAL" in bloque, (
E       AssertionError: `compras.facturas` no traduce el estado con un lateral:
E       sin el no hay guarda de grano (criterio 3)
E       assert 'LEFT JOIN LATERAL' in 'DROP TABLE IF EXISTS compras.facturas
E       CASCADE; CREATE TABLE compras.facturas AS SELECT f.ide AS factura_id,
E       ... FROM raw.dcf f JOIN raw.con con ON con.ide = f.ide LEFT JOIN
E       raw.con prv_con ON prv_con.ide = NULLIF(f.entide, 0); '
tests	est_f083_sql.py:238: AssertionError

________ test_f083_la_traduccion_del_estado_no_puede_multiplicar_filas ________
>       lateral = _lateral_del_estado()   # misma AssertionError: no hay lateral
tests	est_f083_sql.py:213 -> 238: AssertionError

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
tests	est_f083_diccionario.py:218: AssertionError
```

**23 de los 53 pasaban ya en rojo, y es lo que se buscaba**: son los que
vigilan que las diez columnas de siempre siguen ahi, en su orden y con su
expresion. Un test de no-regresion tiene que estar verde ANTES del cambio; si
hubiera fallado en esta pasada, el que estaria mal seria el test.

## T3 · El SQL, y la verificacion del grano ANTES de construir nada

`sql/compras/01_documentos.sql`, **solo el bloque FACTURAS**: cinco columnas
nuevas al final, un `LEFT JOIN LATERAL` al catalogo y un indice por
`estado_id`. Las diez de siempre no se tocan. **El fichero es de F-067**, que
lo reescribira entero, asi que el cambio se acota a ese bloque y se anota en la
cabecera para que el merge de F-067 lo vea.

**Por que `estado_codigo` ademas del literal, que la ficha no pedia**: el
correo pregunta en mnemonicos («CON contabilizada, APJO aprobada por jefe de
obra, APRADM...»), y **el literal no es unico**: `REC` y `REC_ADM` se llaman
los dos «Recibida», y `APR` y `APR_DG` «Aprobado pago» / «Aprobado Pago».
Filtrar por el literal mezcla dos estados distintos; por el mnemonico, no.

**EL SELECT NUEVO, EJECUTADO EN SOLO LECTURA** (no se ha construido nada: es
un `SELECT` envuelto en `COUNT(*)`, en transaccion `READ ONLY`). Esto es la
prueba del criterio 3, no una promesa:

| Comprobacion | Resultado |
|---|---|
| Filas del SELECT nuevo | **165.866** |
| `factura_id` distintos en el SELECT nuevo | **165.866** (el lateral no multiplica) |
| Filas que `compras.facturas` publica hoy | **165.866** (mismo grano antes y despues) |
| Facturas con `estado` sin traducir | **0** |
| `fecha` distinta de `fecha_alta` | **0 de 165.866** (su significado no cambia) |
| Facturas sin `fecha_factura` / sin `fecha_alta` | 80 / 3 |

Y la pregunta del correo, ya respondida con el SELECT nuevo cruzado contra
`compras.vencimientos` (efectos vivos, vencidos y sin pago real): APR 32.408,
CONGG 2.677, APRJG 115, FRAAPR 65, **CON (contabilizada sin aprobar) 55**,
**RECH (rechazada) 27**, REC 27, APRADM 17, APJO 17... y **FRARET (retenida)
cero, porque ninguna factura esta en ese estado**: esa es la respuesta
correcta, no un «no se puede saber». El corte no reproduce las 628 facturas /
3,84 M EUR del correo, que salian de otro filtro.

## T4 · El diccionario, que es lo que el humano subrayo

`config/diccionario/compras.yaml`: la ficha de `compras.facturas` gana las
cinco columnas, una descripcion que abre con **las dos confusiones** y dos
`ejemplos_preguntas` nuevos con las palabras del correo. `version` 22 -> 23 en
`00_global.yaml` (comprobado: el valor real era 22, no el 21 publicado en la
base).

**La ficha no describe: impide.** Lo que cada columna tiene que dejar cerrado:

* `estado` dice **en su propia ficha** —no solo en la del objeto— que NO es el
  `estado_pago` del efecto, y trae el reparto medido. `estado_codigo` enumera
  los mnemonicos del correo y manda filtrar por el codigo y no por el literal.
  `estado_id` dice que solo significa algo dentro del tipo 15.
* Las **tres** fechas se nombran unas a otras: cada una dice de que campo de
  Sigrid sale y en que se diferencia de las otras dos, y `fecha` declara que es
  la de ALTA y que se conserva por compatibilidad.
* **La ficha de `compras.vencimientos.estado_pago` devuelve el aviso**: la
  confusion se puede entrar por cualquiera de las dos puertas.

**NO se declara una relacion `estado_id -> maestro.estados_documento`**, y es
deliberado: una relacion escrita por esa columna invita justo al `JOIN` que el
criterio 2 prohibe. La traduccion ya viene resuelta en la tabla; quien vaya al
catalogo tiene que ir por la pareja, y eso se dice en prosa.

### Tres guardianes de otras features que esto hizo saltar

No se han silenciado. Los tres estaban bien puestos y los tres se han atendido:

1. **`test_f073_r23_no_toca_el_sql_de_documentos_de_compra`** (hash de
   `01_documentos.sql`). Es el caso que el guardian preveia: el fichero cambia
   **a proposito y desde otra feature**. Hash recalculado, con el porque
   escrito al lado. `0a3ab862...` -> `572a185d...`.
2. **`test_f080_r21_los_ficheros_de_f067_no_publican_nada_de_f080`**. Saltaba
   porque la cabecera **nombra** `compras.vencimientos`. R21 prohibe
   **publicar** ahi un objeto de F-080; nombrarlo en un comentario es lo
   contrario, y es justo lo que el criterio 5 exige. El guardian pasa a mirar
   el **SQL ejecutable** (`_sin_comentarios`), que es lo que siempre quiso
   mirar. Alternativa descartada: callar la advertencia para no verlo en rojo.
3. **`test_f006_los_recuentos_de_current_son_los_de_hoy`**. El diccionario pasa
   de 964 a **969 columnas**; `progress/current.md` actualizado.
