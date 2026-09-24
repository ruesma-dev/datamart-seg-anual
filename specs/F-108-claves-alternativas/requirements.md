<!-- specs/F-108-claves-alternativas/requirements.md -->
# F-108 · Requisitos — claves alternativas en el diccionario, vigiladas por `check-unicidad`

EARS; cada R >= 1 test `test_f108_rN_...` en `tests/test_f108_claves_alternativas.py`,
**sin red ni BBDD** salvo las marcadas **MANUAL**. Rigor `estandar`. Origen: las
desviaciones 4 y 6 de F-102 (`progress/impl_F-102.md`). Decision del humano del
2026-09-24: **opcion B** (claves alternativas declaradas; se descarta el indice
unico). Cifras **medidas en solo lectura el 2026-09-24** por MCP: `design.md` §1.

## El diccionario admite claves alternativas

R1. El sistema debe admitir en una ficha la clave opcional `claves_alternativas`:
una lista de claves, cada una una lista NO vacia de columnas
(`claves_alternativas: [[clave_obra]]`, `[[empresa_id, codigo_cuenta]]`). Sin la
clave, la ficha vale `()` y se comporta como hoy.

R2. SI `claves_alternativas` no es una lista de listas de textos (un escalar, una
lista plana `[clave_obra]`, una clave vacia `[[]]`), ENTONCES la carga debe
fallar con un error `R1` que nombre la ficha y muestre la forma correcta
`[[columna]]`. La lista plana es ambigua (una clave compuesta o dos simples) y
no se adivina.

R3. SI una clave alternativa nombra una columna no documentada en la propia
ficha, o la ficha no documenta columnas, ENTONCES `validar` debe devolver un
error `R2` que nombre la columna (misma regla que `clave_negocio`).

R4. SI una clave alternativa repite columna, coincide (como conjunto) con la
`clave_negocio`, o repite otra clave alternativa de la ficha, ENTONCES `validar`
debe devolver un error `R2` que lo diga.

R5. SI una ficha de `tipo: funcion` declara `claves_alternativas`, ENTONCES
`validar` debe devolver un error `R2`: una funcion no tiene filas.

## El validador de relaciones (R5 de F-006) las acepta como lado 1

R6. El sistema debe tratar una columna como unica en `_es_unica_por` cuando es,
ELLA SOLA, una clave alternativa declarada (`(col,)` en `claves_alternativas`),
ademas de los dos casos de hoy (clave de negocio entera y `clave_sustituta`).
Vale para los dos lados (`1:N` y `N:1`).

R7. MIENTRAS una columna solo forme parte de una clave alternativa COMPUESTA, el
sistema debe seguir sin darla por unica: una relacion `N:1` hacia
`maestro.cuentas_analiticas.codigo_cuenta` sigue siendo error R5.

R8. CUANDO `_validar_cardinalidad` rechace un lado 1, el mensaje debe citar,
ademas de la clave de negocio, las claves alternativas del extremo si las tiene.

## `check-unicidad` las comprueba, y avisa sin romper la nocturna

R9. El sistema debe generar en `consultas_de_unicidad` UNA consulta por cada
clave alternativa de cada ficha del alcance (mismo filtro `solo_consumo`, mismo
salto de funciones), ademas de la de la clave de negocio. Se generan AUNQUE la
clave de negocio se salte por estar garantizada (`clave_sustituta`) o por no
existir.

R10. Cada `ConsultaUnicidad` debe decir de que clave es (`tipo_clave`:
`"negocio"` o `"alternativa"`); por defecto `"negocio"`, para no romper a quien
la construye hoy.

R11. La consulta de una clave alternativa debe tener la forma de la de negocio
(`GROUP BY <clave> HAVING count(*) > 1`, sin `count(DISTINCT)`) y **excluir las
filas con algun NULL en la clave** (`WHERE c1 IS NOT NULL AND ...`), en la
consulta y en la de detalle: es la semantica del indice unico descartado, y un
NULL no casa en un JOIN, asi que no produce fan-out.

R12. CUANDO una clave alternativa se repita, `check-unicidad` debe imprimir un
`KO` que diga objeto, «clave alternativa», columnas, cuantas combinaciones y
filas, que las relaciones que la usan como lado 1 producirian fan-out, y la
consulta de detalle; y contarlo en «con la clave rota» y salir con codigo 1,
igual que la de negocio.

R13. CUANDO no se repita, el `OK` debe decir «clave alternativa» y conservar la
advertencia de que no prueba que la clave sea correcta. Timeout (`NO
COMPROBADO`, nunca OK) igual que la de negocio.

R14. SI el objeto no existe en la base, ENTONCES `check-unicidad` debe informarlo
UNA sola vez por objeto (no por clave), no lanzar sus demas consultas y contarlo
una vez en «fichados que no existen».

R15. `--dry-run` debe imprimir tambien las consultas de claves alternativas,
rotuladas `clave alternativa: (...)`, sin abrir conexion; la cabecera debe decir
cuantas comprobaciones son de clave alternativa.

R16. La nocturna no debe cambiar: `run-all` no ejecuta `check-unicidad` y ningun
SQL del repositorio crea un indice unico sobre `clave_obra` ni `clave_recurso`
(guarda de la opcion B).

R17. El sistema debe comprobar offline que toda columna que sostiene un lado 1
POR una clave alternativa tiene su `ConsultaUnicidad` de tipo `alternativa` con
esa clave exacta, al menos con `solo_consumo=False` (la premisa del R20 de F-042,
a nivel de columna y no de objeto).

## Publicacion

R18. `filas_diccionario` debe publicar `claves_alternativas` dentro del JSONB
`ficha` (lista de listas, en el orden del YAML) SOLO cuando la ficha las tenga;
sin DDL nuevo, sin tocar `_meta.v_diccionario` ni la columna `clave_negocio`.

R19. `00_global.yaml` sube `version` 30 -> 31.

## Las claves declaradas

R20. El diccionario debe declarar `claves_alternativas: [[clave_obra]]` en
`maestro.obras` y `[[clave_recurso]]` en `personal.recursos` (922/922 y
2.619/2.619 el 2026-09-24).

R21. Las cinco relaciones `clave_obra -> maestro.obras.clave_obra` de `compras`
(`v_pbi_proveedor_obra`, `v_pbi_partida_coste`, `v_pbi_contrato_consumo`,
`v_pbi_albaranes_sin_facturar`, `v_control_forma_pago`) deben pasar a `N:1`, y su
`porque` deja de decir «DE HECHO ES N:1 ... se declara N:N» y dice que
`clave_obra` es clave alternativa vigilada por `check-unicidad`.

R22. DONDE el humano lo confirme (decision D3), el diccionario debe declarar
tambien: `maestro.v_obra_fichas` `[[clave_obra]]` (922/922),
`maestro.cuentas_analiticas` `[[empresa_id, codigo_cuenta]]` (184.234/184.234),
`maestro.centros_coste` `[[empresa, codigo_centro]]` (804/804) y `stg.obras`
`[[codigo_obra]]` (584/584). Sus fichas ya afirman esa unicidad en texto.

R23. `test_f102_r22_la_relacion_por_clave_esta_declarada` debe pasar a exigir
`N:1` (la desviacion 4 que documentaba queda resuelta), y
`test_f107_r4_la_version_sube_a_30` a `>= 30`; ningun otro test pierde lo que
vigila.

## Documentacion

R24. `docs/ARCHITECTURE.md` («El datamart se explica solo») debe explicar las
claves alternativas en un parrafo: que son, quien las comprueba y que el
validador las acepta como lado 1; y `azure-apps/datamart_seg_anual.md` la clave
nueva del JSONB `ficha` (commit local alli, sin push).

## Verificacion contra la base (MANUAL, humano, solo lectura)

R25. **MANUAL**: `python main.py check-unicidad` con el `.env` del humano debe
dar `OK` en las claves alternativas declaradas y el mismo resultado de hoy en
las de negocio. Luego `publicar-diccionario` (version 31), escritura que
autoriza el humano.
