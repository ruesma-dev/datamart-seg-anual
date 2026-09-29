<!-- progress/impl_F-084.md -->
# F-084 · El estado del CONTRATO · informe de implementacion

Rama `feature/F-084-estado-del-contrato`, rigor `estandar`, `sdd=false`: el
contrato son los **siete criterios de `acceptance`** de la ficha. **Plan** (sin
`tasks.md`; un commit por tarea): **T1** medir en solo lectura · **T2** fase
RED · **T3** el SQL factorizado · **T4** el diccionario · **T5** guardianes,
`init.sh` y evidencias.

**Ficheros tocados**: `sql/compras/{00_setup,01_documentos}.sql`;
`config/diccionario/{compras,00_global}.yaml`; `tests/test_f084_{sql,diccionario}.py`
(nuevos); `tests/{test_f083_sql,test_f073_sql,test_f079_stg_consultable}.py`
(guardianes); `progress/current.md`; `specs/F-006-mcp-azure/design{,_detalle}.md`.

## T1 · Lo medido (2026-09-16, `filas_solo_lectura`, transaccion READ ONLY)

El MCP **no expone `raw`**, asi que la medicion va con el cliente del propio
proyecto en transaccion `READ ONLY` (script en el scratchpad, no se versiona).
**El universo**: 18.978 contratos en `raw.ctr`, todos con fila en `raw.con` y
**todos con `tip = 44`**; `compras.contratos` publica hoy esas mismas **18.978**
filas y **doce** columnas, que es lo que el criterio 2 obliga a conservar. **El
estado (criterio 1)** esta en **18.978 de 18.978 (100 %)**, con **0 huerfanos**.

**El reparto real entre los 7 estados del tipo 44 (criterio 3)**, como
`estado_id` / codigo / literal / cuantos:

> 7 FIR «Firmado» **13.459** · 8 TER «Terminado» **3.179** · **3 EPF
> «Enviado» 818** · 1 PFP «Pdt. envio de firma» **564** · 5 RFP «Recibido»
> **550** · 6 COMD «Comprobada documentación» **232** · 9 RES «Rescindido»
> **176**

Suman **18.978 exactas**, y **los siete se usan**, al reves que en las facturas
del tipo 15: aqui, si uno sale vacio, el sospechoso es el filtro y no el
catalogo, y la ficha lo dice. Ojo al unico literal con tilde, «Comprobada
documentación». **Guarda de grano (criterio 2)**: `(tip, est)` es unico —7 de 7
en el tipo 44, **0 pares duplicados** en las 193 filas—; hoy el `JOIN` no
multiplica, y la tabla no puede depender de eso.

**Las firmas, que es el hallazgo (criterio 5)**: de las **70.308** filas de
`raw.confir` hoy, **CERO son de contrato** —por las DOS vias, `docide` y
`conide`, y por `EXISTS` contra `raw.ctr`—; reparto por `conide`: comparativo
(46) 66.060, factura (15) 3.452, obra (42) 796. La ficha declara la cifra que
pide el criterio, **70.346**, medida el mismo 2026-09-16 antes de la reingesta:
el reparto se movio en 38 firmas y **el cero no**.

**El proxy de antiguedad (criterio 4)**: `con.tiemod` esta informado en las
18.978, pero es `double precision` en **epoca Delphi** (dias desde 1899-12-30),
no el `YYYYMMDD` de `fn_sigrid_date`. Convertido a mano, de los 818 «Enviado»
hay 799 con `tiemod` de hace mas de 21 dias. **NO se publica**: ver T4.

## T2 · Fase RED (obligatoria en nivel `estandar`)

Los dos ficheros se escribieron **antes** de tocar el SQL y el YAML. Comando
exacto y salida real, con el arbol aun sin implementacion (`367af44`):

```
$ python -m pytest tests/test_f084_sql.py tests/test_f084_diccionario.py -q
...
FAILED tests/test_f084_sql.py::test_f084_c1_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id
FAILED tests/test_f084_sql.py::test_f084_c6_los_dos_bloques_llaman_a_la_misma_funcion
FAILED tests/test_f084_diccionario.py::test_f084_c4_la_ficha_declara_el_proxy_de_antiguedad_y_su_trampa
FAILED tests/test_f084_diccionario.py::test_f084_c5_la_ficha_declara_que_no_hay_firmas_de_contrato
   (y otros 27, entre ellos las tres columnas sin ficha y los siete estados)
31 failed, 26 passed in 0.87s

--- y la traza completa de los criterios centrales, sin resumir:

______ test_f084_c1_la_union_es_por_la_pareja_y_nunca_solo_por_estado_id ______
>       cuerpo = _cuerpo_de_la_funcion()
    def _cuerpo_de_la_funcion() -> str:
        marca = f"CREATE OR REPLACE FUNCTION {FUNCION}"
>       assert marca in texto, (
E       AssertionError: `compras.fn_estado_documento` no esta definida en
E       `compras/00_setup.sql`: sin ella la traduccion del estado tendria que
E       copiarse en cada bloque, que es justo lo que el criterio 6 prohibe
E       assert 'CREATE OR REPLACE FUNCTION compras.fn_estado_documento' in
E       "\nCREATE SCHEMA IF NOT EXISTS compras;\n\n...fn_sigrid_date...$$;"
tests\test_f084_sql.py:95: AssertionError

___________ test_f084_c6_los_dos_bloques_llaman_a_la_misma_funcion ____________
>       assert f"{FUNCION}(44, con.est)" in _bloque_contratos(), (
            "el bloque CONTRATOS tiene que traducir con la funcion compartida"
        )
E       AssertionError: el bloque CONTRATOS tiene que traducir con la funcion
E       compartida
E       assert 'compras.fn_estado_documento(44, con.est)' in 'DROP TABLE IF
E       EXISTS compras.contratos CASCADE; CREATE TABLE compras.contratos AS
E       SELECT c.ide AS contrato_id, ... NULLIF(c.entide, 0); '
tests\test_f084_sql.py:337: AssertionError
(c2_..._no_puede_multiplicar_filas cae en el mismo assert de :95: no hay funcion)
```

**26 de los 57 pasaban ya en rojo, y es lo que se buscaba**: son los de
no-regresion de las doce columnas de siempre, que tienen que estar verdes ANTES
del cambio. Si hubieran fallado, el que estaria mal seria el test.

## T3 · El SQL, y la decision del criterio 6

**Se factoriza.** La traduccion vive ahora UNA vez en
`compras.fn_estado_documento(p_tip, p_est)`, en `compras/00_setup.sql` —con
`fn_serie` y `fn_sigrid_date`—, y la llaman los dos bloques: `(44, con.est)` en
CONTRATOS y `(15, con.est)` en FACTURAS.

Lo que se gana **no son las siete lineas** del lateral: es que **el tipo de
documento pasa a ser argumento obligatorio de la firma**. La union «solo por
`estado_id`» —la que publica el literal de otro documento SIN romper el build,
y la que el criterio 1 manda vigilar— deja de poder escribirse: PostgreSQL
falla al construir. Y la guarda (`ORDER BY ide LIMIT 1`) se escribe una vez y
protege a las **dos** tablas. La proyeccion de FACTURAS no cambia ni una letra:
la funcion devuelve los mismos nombres que tenia el lateral.

**Lo que NO se factoriza, a proposito.** (a) `maestro/01_obras.sql` repite el
patron para el tipo 42 y se queda: `compras` **solo lee de `raw.*`** y no
depende del orden de construccion de `maestro`; cada esquema tiene su copia
local de las auxiliares por esa regla. (b) `compras/05_vencimientos.sql` une el
catalogo a mano para `tip = 25` **y sin guarda de grano**; es de F-080 y R21
dice que es suyo: recomendacion al reviewer, no tocado.

**EL SELECT NUEVO, EJECUTADO EN SOLO LECTURA** —no se ha construido nada: es un
`SELECT` envuelto en agregados—. Es la prueba del criterio 2, no una promesa:

| Comprobacion | Resultado |
|---|---|
| Filas del SELECT nuevo | **18.978** |
| `contrato_id` distintos | **18.978** (el lateral no multiplica) |
| Filas que `compras.contratos` publica hoy | **18.978** (mismo grano) |
| Contratos con `estado` / `estado_codigo` sin traducir | **0** / **0** |
| **Las doce de siempre, columna a columna contra la tabla VIVA** | **0 filas que no casan** |

La ultima fila cierra el criterio 2 de verdad: no es que las doce columnas sigan
escritas, es que **devuelven el mismo valor** que la tabla en produccion,
contrato a contrato. Y la pregunta de Compras ya responde: **818 contratos
«Enviado», de 567 proveedores y 241 obras**.

**Sintaxis del `CREATE FUNCTION`, comprobada sin escribir**: lanzada en `READ
ONLY`, el motor responde `ReadOnlySqlTransaction: cannot execute CREATE FUNCTION
in a read-only transaction` —el parser la acepto, y la escritura la rechazo la
base y no la buena voluntad—. No valida el **cuerpo**: eso queda en MANUAL.

## T4 · El diccionario, y la mitad negativa

La ficha de `compras.contratos` gana las tres columnas con el reparto medido,
el orden del circuito (PFP -> EPF -> RFP -> COMD -> FIR -> TER, con RES como
salida) y el aviso de **filtrar por `estado_codigo` y no por el literal**.
`compras.fn_estado_documento` entra con su ficha; `version` 23 -> 24.

**La decision mas pensada: NO se publica ninguna columna de antiguedad.** El
criterio 4 exige que la ficha declare que la antiguedad solo se aproxima con
`con.tiemod` y que **no es la fecha del cambio de estado**. Cabian (a) publicar
`con.tiemod` convertido o (b) declarar el limite. Se elige (b): la conversion
de epoca Delphi **no existe en el repositorio**; la foto diaria que da la
antiguedad REAL es **de F-067**; y sobre todo, **publicar el proxy invita al
fallo que la ficha quiere impedir**. La ficha dice las tres cosas: que los
ENVIADOS si se listan (818), que el «cuanto llevan» **no se puede saber** hoy,
y que `con.tiemod` ni siquiera esta publicado porque vive en `raw`, que el MCP
no ve. **Si el humano prefiere el proxy, es una linea de SQL y una de ficha.**
El criterio 5 queda escrito con su cifra: **cero firmas sobre 70.346**.

### Cuatro guardianes ajenos que esto hizo saltar (ninguno silenciado)

1. **F-073 R23** (hash de `01_documentos.sql`): segunda vez en el dia, y es el
   caso que preve —cambia **a proposito y desde otra feature**—. Recalculado
   con el porque al lado: `572a185d…` -> `5cc72676…`.
2. **F-079 R3**: `compras.fn_estado_documento` entra en `GRUPO_B_FUNCIONES`,
   por lo mismo que las otras tres (se llama desde el build, no se consulta).
3. **F-006 recuentos de `current.md`**: 153 -> **154** objetos, 969 -> **972**
   columnas; las de consumo siguen en **66** (la funcion no es de consumo).
4. **F-006 R24**: enmienda nueva en `design_detalle.md`, y un hallazgo anotado
   alli: el guardian solo busca la cifra en el fichero, y el **153 se lo daba por
   casualidad** `infra/README.md:153-170`. F-078 y F-083 no escribieron la suya.

**Los cuatro tests de F-083 que miraban el texto del lateral** se adaptan al
sitio nuevo: cambia **donde miran, no lo que exigen** —siguen exigiendo la
pareja, el `ORDER BY`, el `LIMIT 1` y el `LEFT`, y ahora ademas que la factura
llame con su `15`—, y la comprobacion del cuerpo queda **duplicada a
proposito** entre F-083 y F-084. **`azure-apps/datamart_seg_anual.md` no
cambia**: describe la ingesta y los pasos, no estas columnas.

## Evidencias

| Evidencia | Valor medido |
|---|---|
| **Tests ejecutados** | **4.938 pasan, 188 saltados, 0 fallos** (`bash harness/init.sh`, exit 0). De ellos **57 son de F-084** |
| **Cobertura de lineas cambiadas** | **94,3 %** (901/955), umbral 80 %, nivel `estandar` — linea `PUERTA COBERTURA`. Mismo matiz que en F-083: esas 955 lineas son del diff contra `dev`, que arrastra F-073/F-078/F-080/F-081, asi que **ese 94,3 % no habla de F-084**, que no cambia ni una linea de Python de produccion |
| **Mutantes y supervivientes** | **NO APLICA, y esta medido**: `python -m harness.mutacion --feature F-084 --base main` responde «ALCANCE VACÍO en F-084: ni una línea de producción que mutar» y **se niega a escribir informe**. No hay `progress/mutacion_F-084.md` a proposito |
| **Tiempo de la suite** | **185,9 s** sin cobertura (`pytest -q`); **392,8 s** dentro de `init.sh`, con ella |
| **Tamano del papeleo** | `PUERTA TAMAÑO [OK]: F-084 dentro de los topes (impl 217/220)` |

**Sobre la mutacion, que hay que explicar y no dejar en «no aplica».** F-084
cambia **SQL, YAML y Markdown** mas cuatro ficheros de tests; el motor muta
**Python de produccion**, y de eso hay cero. La **prueba de control** no es la
palabra del motor: `git diff --name-only <merge-base> HEAD | grep '\.py$' |
grep -v '^tests/'` sale **vacio**, asi que el cero es estructural. Lo defienden
los **57 tests sobre el TEXTO** y la verificacion en solo lectura del SELECT.
(La rama lleva ademas **cuatro commits del lider** hechos durante la
implementacion: `b7e1b20`, `e4b3f08`, `80429e1`, `faea29e`. No son de F-084 ni
tocan Python, pero entran en el diff y en el alcance.)

## Verificaciones MANUAL pendientes (no las hace un agente)

**F-084 no pasa a `done` con esto**: el criterio 4 exige respuesta por el MCP y
el MCP lee la tabla **construida**. Nadie ha escrito en la base —todo lo de
arriba son `SELECT` en `READ ONLY`—. Lo ejecuta el humano:

```
python main.py build-compras          # construye la funcion y las dos tablas
python main.py status                 # o check-unicidad, si se prefiere
python main.py publicar-diccionario   # sube la version 24 a _meta
```

- `build-compras` es **la unica verificacion real del cuerpo de la funcion** —el
  `CREATE FUNCTION` lo valida al ejecutarse y aqui solo se pudo validar el
  parseo (T3)— y lo unico que confirma **en la base** el grano.
- Despues, por el MCP y **sin explicarle nada**: «que contratos estan enviados y
  sin firmar» debe listar los **818** de `estado_codigo = 'EPF'`. Y la que prueba
  la ficha: «cuantos llevan mas de tres semanas enviados» — la respuesta correcta
  es **que no se puede saber**; si da un numero de dias, la ficha ha fallado.
