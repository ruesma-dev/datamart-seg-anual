<!-- specs/F-057-recursos-empleados-partes/requirements.md -->
# F-057 · Requisitos — el coste de personal por obra (stg + mart sobre raw)

Notacion EARS. Cada R se traduce a >= 1 test `test_f057_rN_...`.
Las cifras vienen **medidas contra Sigrid vivo el 2026-09-18** en solo lectura
(`sigrid-api`); el detalle y el porque de cada decision estan en `design.md`.
Los `raw` ya los trae F-066 (`res`, `emp`, `hmo`, `hmores`) y F-074
(`auxhor`, `auxrestip`): **aqui no se ingiere nada**.

## Maestro de recursos

R1. El sistema debe publicar `stg.recursos` con **una fila por fila de
`raw.res`** (2.618 el 2026-09-18) y `recurso_id` unico, tomando codigo y nombre
de `raw.con` (regla `R-SIGRID-CON`: `res` es propiedad de `con` 1:1, con el
mismo `ide`, y no tiene codigo ni nombre propios).

R2. El sistema debe clasificar cada recurso en `clase` a partir de `res.cla`:
`1` = PERSONA (1.354), `0` = CONSUMO (1.158), `2` = MEDIO (106). **`res` no es
el maestro de personal**: solo el 51,7 % de sus filas son personas.

R3. El sistema debe publicar el criterio de Juan Romero (correo «RECURSOS
PARTES TRABAJO», 2026-09-03) como la columna booleana `activo`, definida como
`raw.con.fecbaj = 0` sobre el concepto del recurso. Medido: 1.722 de baja y 896
de alta; entre las personas, **1.034 de baja y 320 de alta**. `raw.res` no tiene
columna de baja propia: la baja es la del CONCEPTO.

R4. MIENTRAS `stg.recursos` se construya, el sistema debe publicar **todas** las
filas, de alta y de baja, y no debe filtrar por `activo`. El criterio de Juan
Romero se aplica al maestro como BANDERA, no como filtro.

R5. SI alguien filtra el hecho por `activo`, ENTONCES el sistema debe haber
dejado escrito en la ficha del diccionario que eso descarta **539.774,87 de las
1.249.038,44 horas imputadas (43,2 %)**, de 287 de los 445 recursos que han
imputado horas: el recurso de baja de hoy trabajo ayer.

R6. El sistema debe resolver la relacion recurso-empleado por `res.conide` a
`emp.ide` en un `LEFT JOIN` que **no puede multiplicar filas**, y `emp` nunca
debe ser el grano ni un filtro de `stg.recursos`. Medido: no es 1:1 en ninguna
direccion — 824 de 2.618 recursos casan con un empleado (31,5 %), 805 de 1.354
empleados casan con un recurso, solo 797 pares son reciprocos, 24 empleados no
apuntan a ningun recurso, 3 discrepan y **3 recursos comparten el mismo
`conide`** (821 valores distintos en 824 filas).

R7. El sistema debe publicar los datos personales **nombre y DNI**:
`nombre_recurso` (de `con`), `nif` (`res.cif`, informado en 629 de 1.354
personas) y, cuando hay empleado, `dni` (`emp.dni`, informado en el 99,2 %) mas
el nombre estructurado (`emp.nomnom`, `nomape1`, `nomape2`). **El humano lo
autorizo expresamente el 2026-09-18: «el dni puede salir, no es un problema».**
No es un descuido ni un pendiente: es una decision tomada por el responsable del
dato, y por eso se cita aqui con su fecha.

R8. El sistema NO debe publicar ningun otro dato personal de `raw.emp`: ni
numero de la Seguridad Social, ni cuenta bancaria, ni domicilio, ni fecha de
nacimiento, ni sexo, ni estado civil, ni contacto, ni credenciales. La
autorizacion de R7 cubre nombre y DNI, no la ficha de 152 columnas.

R9. El sistema debe declarar en la ficha del diccionario de `stg.recursos` que
el objeto **contiene datos personales** (nombre, NIF y DNI), para que quien
consulte sepa que esta mirando.

R10. El sistema debe publicar `es_externo` y `proveedor_id` desde `res.prvide`,
informado en 459 de las 1.354 personas (85 proveedores distintos).

## El hecho: lineas de parte de trabajo

R11. El sistema debe publicar `stg.partes_lineas` con **una fila por fila de
`raw.hmores`** (330.638 el 2026-09-18) y `linea_id` unico.

R12. El sistema debe atribuir la obra por **`hmores.obride`, el de la LINEA**,
informado en 329.265 de 330.638 filas (99,58 %) sobre 536 obras. En 769 lineas
(0,23 %) la obra de la linea difiere de la de su cabecera `hmo`, y manda la
linea; ninguna linea queda sin cabecera.

R13. El sistema NO debe usar `maestro.centros_coste` (F-073) ni
`res.cenconide` para atribuir la obra. La trampa de `apu` —atribucion por
centro de coste, pregunta abierta de F-045— **no aplica aqui**: el parte trae la
obra. `res.cenconide` esta informado al 75,5 % pero con solo 9 valores
distintos, asi que no atribuye nada.

R14. El sistema NO debe filtrar el universo de obra (regla `R-UNIVERSO-OBRA`) y
debe publicar la marca `en_seguimiento`. Medido: 523 obras del seguimiento
(318.892 lineas, 1.226.158,60 h, 93,24 M EUR = 94,9 %), 12 administrativas
(10.373 lineas, 4,93 M EUR, con GENERALES 2,59 M EUR y POSTVENTA 2 1,85 M EUR) y
1.373 lineas con la obra a cero.

R15. El sistema debe publicar `partida_id` desde `hmores.paride`, informado en
302.575 lineas (91,5 %). Medido: las 302.575 existen en `raw.obrparpar` y las
302.575 pertenecen a la MISMA obra de la linea; cero inconsistencias.

## La unidad, que es lo que hace falsa una suma

R16. El sistema debe publicar la UNIDAD de `hmores.can` derivandola de
**`auxhor.medide`**: `1` = HORA, `2` = DIA, `3` = MES, `19` = UD. El clasificador
NO es `auxhor.ext`, que esta a cero en las 60 filas del catalogo.

R17. SI una linea apunta a un `auxhor.medide` fuera de 1, 2, 3 y 19, ENTONCES el
sistema debe publicarla con `unidad = 'DESCONOCIDA'`, y un test debe fallar para
que un quinto valor en origen no se traduzca en silencio.

R18. El sistema debe dejar escrito en la ficha que **sumar `cantidad` sin
filtrar `unidad` es una cifra falsa**. Medido: HORA 241.004 lineas y
1.249.038,44 horas por 24,84 M EUR; DIA 9.723 lineas de incidencia (vacaciones,
bajas) por 1.809,20 EUR; MES 36.034 lineas, 18.009,38 meses y **70,46 M EUR, el
71,7 % del dinero**; UD 43.867 lineas y 565.927,95 unidades heterogeneas
(moviles, gasoil, kilometros, dietas, EPIs) por 2,98 M EUR. Diez lineas apuntan
a un tipo de hora que no esta en `auxhor`.

R19. El sistema debe publicar `importe` desde `hmores.tot` **con su signo**, sin
filtrar. Medido: `tot` cuadra con `round(can * pre, 2)` en 330.596 de 330.638
lineas (99,99 %); 11.036 lineas valen 0 y 9.119 son negativas (correcciones).

R20. El sistema debe declarar en la ficha los defectos de calidad medidos en
origen y no corregirlos: 5 lineas con fecha 0, una con fecha del ano 3103, 6 con
ano fuera de 1990-2030 y 5 con mes fuera de 1-12. En `hmo`, la fecha de cierre y
la clase estan a cero en las 6.884 cabeceras y el recurso solo viene en 6: el
recurso vive en la linea.

## Superficie de consumo

R21. CUANDO un agente pregunte las horas imputadas a una obra en un periodo, el
sistema debe responder por `mart.v_pbi_horas_obra_mes`, con grano obra x ano x
mes x tipo de recurso, **construida solo con `unidad = 'HORA'`** para que la
trampa de R18 no se pueda cometer desde ahi.

R22. CUANDO un agente pregunte quien ha trabajado en una obra, el sistema debe
poder responderlo cruzando `stg.partes_lineas` con `stg.recursos`. Ejemplo
medido de 2026: obra 0695, oficial 1a albanil, 7.366,00 h y 170.470,10 EUR.

R23. El sistema debe traer la ficha de diccionario de los tres objetos
publicados en `config/diccionario/` en el mismo trabajo, y subir `version` en
`00_global.yaml`. La lista de pendientes esta vacia y es un trinquete: aqui no
se aplaza ninguna ficha.

## Construccion

R24. CUANDO `build_stg` se ejecute dos veces seguidas, el sistema debe dejar el
mismo contenido en los dos objetos nuevos (idempotencia por `TRUNCATE` +
`INSERT`, como `stg.obras` y `stg.partidas`).

R25. Los tests de esta feature NO deben tocar red ni base de datos: se verifican
sobre el texto del SQL, el DDL y el cableado del step. Las cifras contra la base
viva son verificacion MANUAL del humano.
