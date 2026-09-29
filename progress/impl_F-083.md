<!-- progress/impl_F-083.md -->
# F-083 · El estado de la FACTURA (y sus dos fechas) · informe de implementacion

Rama `feature/F-083-estado-de-la-factura`, rigor `estandar`, `sdd=false`: el
contrato son los **once criterios de `acceptance`** de la ficha —ocho, mas los
tres que anadio el humano a mitad de tarea al meter en alcance las dos fechas
(«la fecha metela, y separa las 2. Luego debe quedar muy claro en el
diccionario»)—.

## Plan de tareas (no hay `tasks.md`: esta es la lista)

- [x] **T1** · Medir en SOLO LECTURA contra `raw` antes de escribir SQL: estado
  informado, reparto entre los 21 estados del tipo 15, huerfanos, unicidad del
  par `(tip, est)`, cobertura de `dcf.fecdoc` y separacion entre las dos fechas.
- [x] **T2** · Fase RED: `tests/test_f083_sql.py` y `test_f083_diccionario.py`
  escritos ANTES del codigo, con la traza roja pegada aqui.
- [x] **T3** · El SQL: bloque FACTURAS de `sql/compras/01_documentos.sql`, por
  `LATERAL ... LIMIT 1` con `tip = 15`. Lo minimo: el fichero es de F-067.
- [x] **T4** · El diccionario: las cinco columnas, la contraposicion con
  `compras.vencimientos` y `version` 22 -> 23 con su changelog.
- [x] **T5** · La frontera con F-067, `init.sh` en verde, evidencias e informe.

## T1 · Lo medido (2026-09-16, solo lectura, `filas_solo_lectura` READ ONLY)

El MCP **no expone `raw`**, asi que la medicion va con el cliente del propio
proyecto en transaccion `READ ONLY` (script en el scratchpad, no se versiona).

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

**Tres de los 21 estados no los usa ninguna factura**: `FRARET` (40, «Factura
retenida»), `REC_ADM` (110) y `APR_ADM` (114). Importa porque el correo
pregunta por las **retenidas**: la respuesta honesta es «cero en `FRARET`».

**La guarda de grano (criterio 3)**: `(tip, est)` es unico en `raw.conest` —21
de 21 en el tipo 15, y ni un par duplicado en las 193 filas—. El `JOIN` no
multiplica hoy; la tabla no puede depender de eso, y por eso va con `LATERAL`.

**Las dos fechas (ampliacion, criterio 4 extendido)**:

- `dcf.fecdoc` informada en **165.786 de 165.866 (99,95 %)**, 80 sin ella;
  `con.fec` en 165.863, 3 sin ella.
- **Coinciden en 36.771 (22,2 %) y se separan en 129.012 (77,8 %)**: cuatro de
  cada cinco facturas tienen dos fechas distintas. Esto ya justifica separarlas.
- Desfase `fecha_alta - fecha_factura`: **mediana 4 dias**, media 10,43, p95
  **42 dias**. Tramos: 1-7 dias 75.102; 8-30 38.922; 0 dias 36.771; 31-90
  8.762; **mas de 90 dias 3.352**; negativo 2.874.
- **Dato sucio declarado, no corregido**: el desfase va de **-89.824** a
  **+3.804 dias**. `fecdoc` la teclea una persona y admite fechas imposibles.
  No se filtra nada —publicar es publicar—: lo avisa la ficha.

## T2 · Fase RED (obligatoria en nivel `estandar`)

Los dos ficheros de test se escribieron **antes** de tocar el SQL y el YAML.
Comando exacto y salida real, con el arbol aun sin implementacion (`5f2ec80`):

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

**23 de los 53 pasaban ya en rojo, y es lo que se buscaba**: son los de
no-regresion de las diez columnas de siempre, que tienen que estar verdes ANTES
del cambio. Si hubieran fallado aqui, el que estaria mal seria el test.

## T3 · El SQL, y la verificacion del grano ANTES de construir nada

`sql/compras/01_documentos.sql`, **solo el bloque FACTURAS**: cinco columnas
nuevas al final, un `LEFT JOIN LATERAL` al catalogo y un indice por
`estado_id`. Las diez de siempre no se tocan. **El fichero es de F-067**, que
lo reescribira entero, asi que el cambio se acota a ese bloque y se anota en la
cabecera para que el merge de F-067 lo vea.

**Por que `estado_codigo` ademas del literal, que la ficha no pedia**: el
correo pregunta en mnemonicos, y **el literal no es unico** (`REC` y `REC_ADM`
son los dos «Recibida»). Filtrar por texto mezcla dos estados; por el
mnemonico, no.

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
cero**: esa es la respuesta correcta, no un «no se puede saber». El corte no
reproduce las 628 facturas / 3,84 M EUR del correo, de otro filtro.

## T4 · El diccionario, que es lo que el humano subrayo

`config/diccionario/compras.yaml`: la ficha de `compras.facturas` gana las
cinco columnas, una descripcion que abre con **las dos confusiones** y tres
`ejemplos_preguntas` con las palabras del correo. `version` 22 -> 23 en
`00_global.yaml`, con su entrada de changelog (el valor real era 22, no el 21
que hay publicado en la base).

**La ficha no describe: impide.** Lo que cada columna tiene que dejar cerrado:

* `estado` dice **en su propia ficha** —no solo en la del objeto— que NO es el
  `estado_pago` del efecto, y trae el reparto medido. `estado_codigo` enumera
  los mnemonicos del correo y manda filtrar por el codigo y no por el literal.
  `estado_id` dice que solo significa algo dentro del tipo 15.
* Las **tres** fechas se nombran unas a otras: cada una dice de que campo de
  Sigrid sale y en que se diferencia de las otras dos, y `fecha` declara que es
  la de ALTA y que se conserva por compatibilidad.
* **La ficha de `compras.vencimientos.estado_pago` devuelve el aviso**: a esta
  confusion se entra por cualquiera de las dos puertas.

**NO se declara una relacion `estado_id -> maestro.estados_documento`**, y es
deliberado: invitaria justo al `JOIN` que el criterio 2 prohibe. La traduccion
ya viene resuelta en la tabla, y la pareja se exige en prosa.

### Cuatro guardianes de otras features que esto hizo saltar

No se han silenciado: los cuatro estaban bien puestos y se han atendido.

1. **`test_f073_r23_no_toca_el_sql_de_documentos_de_compra`** (hash de
   `01_documentos.sql`). Es el caso que el guardian preveia: el fichero cambia
   **a proposito y desde otra feature**. Hash recalculado con el porque al
   lado: `0a3ab862...` -> `572a185d...`.
2. **`test_f080_r21_los_ficheros_de_f067_no_publican_nada_de_f080`**. Saltaba
   porque la cabecera **nombra** `compras.vencimientos`. R21 prohibe
   **publicar** ahi un objeto de F-080; nombrarlo en un comentario es lo
   contrario, y es lo que el criterio 5 exige. El guardian pasa a mirar el
   **SQL ejecutable**, que es lo que siempre quiso mirar. Alternativa
   descartada: callar la advertencia para no verlo en rojo.
3. **`test_f006_los_recuentos_de_current_son_los_de_hoy`**. El diccionario pasa
   de 964 a **969 columnas**; `progress/current.md` actualizado.
4. **`test_f079_r5_el_changelog_del_global_explica_la_version_nueva`**. Pedia
   la entrada de changelog de la version 23: escrita. Y partia el fichero por
   la primera aparicion del texto «version:», que cae **dentro de la prosa de
   F-078**: no veia el changelog nuevo aunque estuviera escrito y delante. Pasa
   a partir por la CLAVE `^version:`.

**`azure-apps/datamart_seg_anual.md` no cambia**: describe la ingesta y los
pasos, no las columnas de `compras.facturas`.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| **Tests ejecutados** | **4.879 pasan, 188 saltados, 0 fallos** (`bash harness/init.sh`). De ellos **53 son de F-083** |
| **Cobertura de lineas cambiadas** | **94,3 %** (901/955), umbral 80 %, nivel `estandar` — linea `PUERTA COBERTURA` de `init.sh`. Esas 955 lineas son las del diff contra `dev`, que arrastra F-073/F-078/F-080/F-081: **F-083 no cambia ni una linea de Python de produccion**. Tiempo de la suite: **464,4 s** con cobertura |
| **Mutantes y supervivientes** | **NO APLICA, y esta medido**: `python -m harness.mutacion --feature F-083 --base main` responde «ALCANCE VACIO: ni una linea de produccion que mutar» y **se niega a escribir informe**. No hay `progress/mutacion_F-083.md` a proposito |
| **Tamano del papeleo** | `PUERTA TAMANO: F-083 dentro de los topes` |

**Sobre la mutacion, que hay que explicar y no dejar en «no aplica».** F-083
cambia **SQL y YAML** mas cuatro ficheros de tests; el motor muta **Python de
produccion**, y de eso hay cero. La primera campana, con la base por defecto
(`dev`), sí veia 19 ficheros y 4.337 lineas: son de F-073, F-078, F-080 y F-081
—`dev` lleva meses de retraso— y ya las midieron sus campanas. La base real de
esta rama es **`main` (`d6809a1`, el merge-base)**, y contra ella el alcance es
cero: se aborto la primera, se relanzo con `--base main` y los cuatro worktrees
quedaron retirados. Lo que defiende este cambio son los **53 tests sobre el
TEXTO** y la **verificacion en solo lectura** del SELECT contra la base real,
que es la unica que puede probar el grano.
