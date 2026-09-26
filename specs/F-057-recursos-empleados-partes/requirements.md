<!-- specs/F-057-recursos-empleados-partes/requirements.md -->
# F-057 · Requisitos — el coste de personal por obra (esquema `personal`)

Notacion EARS. Cada R se traduce a >= 1 test `test_f057_rN_...`. Las cifras
vienen **medidas contra Sigrid vivo el 2026-09-18** en solo lectura
(`sigrid-api`); el detalle y el porque de cada decision, en `design.md`. Los
`raw` ya los traen F-066 y F-074: **aqui no se ingiere nada**. Los tres objetos
viven en un **esquema modulo propio `personal`**, hermano de `compras`,
`maestro` y `retenciones`, por decision del humano del 2026-09-18: no bloquea la
nocturna, y **los permisos se dan por esquema** (F-087).

## Maestro de recursos

R1. El sistema debe publicar `personal.recursos` con **una fila por fila de
`raw.res`** (2.618 el 2026-09-18) y `recurso_id` unico, tomando codigo y nombre
de `raw.con` (regla `R-SIGRID-CON`: `res` es propiedad de `con` 1:1, con el
mismo `ide`, y no tiene codigo ni nombre propios).

R2. El sistema debe clasificar cada recurso en `clase` a partir de `res.cla`: 1 =
PERSONA (1.354), 0 = CONSUMO (1.158), 2 = MEDIO (106). **`res` no es el maestro
de personal**: solo el 51,7 % de sus filas son personas.

R3. El sistema debe publicar el criterio de Juan Romero (correo «RECURSOS PARTES
TRABAJO», 2026-09-03) como la columna booleana `activo` = `raw.con.fecbaj = 0`
sobre el concepto del recurso. Medido: 1.722 de baja y 896 de alta; entre las
personas, **1.034 de baja y 320 de alta**. `raw.res` no tiene columna de baja
propia: la baja es la del CONCEPTO.

R4. MIENTRAS `personal.recursos` se construya, el sistema debe publicar
**todas** las filas, de alta y de baja, y no debe filtrar por `activo`: el
criterio de Juan Romero es BANDERA del maestro, no filtro.

R5. SI alguien filtra el hecho por `activo`, ENTONCES el sistema debe haber
dejado escrito en la ficha que eso descarta **539.774,87 de las 1.249.038,44
horas imputadas (43,2 %)**, de 287 de los 445 recursos que han imputado horas:
el recurso de baja de hoy trabajo ayer.

R6. El sistema debe resolver la relacion recurso-empleado por `res.conide` a
`emp.ide` en un `LEFT JOIN` que **no puede multiplicar filas**, y `emp` nunca
debe ser el grano ni un filtro de `personal.recursos`. Medido: no es 1:1 en
ninguna direccion — 824 de 2.618 recursos casan con empleado (31,5 %), 805 de
1.354 empleados casan con recurso, 797 pares reciprocos, 24 empleados sin
recurso, 3 discrepantes y **3 recursos comparten `conide`** (821 distintos).

R7. El sistema debe publicar los datos personales **nombre y DNI**:
`nombre_recurso` (de `con`), `nif` (`res.cif`, informado en 629 de 1.354
personas) y, cuando hay empleado, `dni` (`emp.dni`, informado en el 99,2 %) mas
el nombre estructurado (`emp.nomnom`, `nomape1`, `nomape2`). **El humano lo
autorizo expresamente el 2026-09-18: «el dni puede salir, no es un problema».**
No es un descuido ni un pendiente: es una decision del responsable del dato, y
por eso se cita aqui con su fecha.

R8. El sistema NO debe publicar ningun otro dato personal de `raw.emp`: ni
Seguridad Social, ni cuenta bancaria, ni domicilio, ni fecha de nacimiento, ni
sexo, ni estado civil, ni contacto, ni credenciales. La autorizacion de R7 cubre
nombre y DNI, no la ficha de 152 columnas.

R9. El sistema debe declarar en la ficha de `personal.recursos` que el objeto
**contiene datos personales** (nombre, NIF y DNI), para que quien consulte sepa
que esta mirando.

R10. El sistema debe publicar `es_externo` y `proveedor_id` desde `res.prvide`,
informado en 459 de las 1.354 personas (85 proveedores).

## El hecho: lineas de parte de trabajo

R11. El sistema debe publicar `personal.partes_lineas` con **una fila por fila
de `raw.hmores`** (330.638 el 2026-09-18) y `linea_id` unico.

R12. El sistema debe atribuir la obra por **`hmores.obride`, el de la LINEA**,
informado en 329.265 de 330.638 filas (99,58 %) sobre 536 obras. En 769 lineas
(0,23 %) la obra de la linea difiere de la de su cabecera `hmo` y manda la
linea; ninguna queda sin cabecera.

R13. El sistema NO debe usar `maestro.centros_coste` (F-073) ni `res.cenconide`
para atribuir la obra. La trampa de `apu` —atribucion por centro de coste,
pregunta abierta de F-045— **no aplica aqui**: el parte trae la obra.
`res.cenconide` esta informado al 75,5 % pero con 9 valores distintos.

R14. El sistema NO debe filtrar el universo de obra (`R-UNIVERSO-OBRA`) y debe
publicar la marca `en_seguimiento`, resuelta contra `stg.obras`. Medido: 523
obras del seguimiento (318.892 lineas, 1.226.158,60 h, 93,24 M€ = 94,9 %), 12
administrativas (10.373 lineas, 4,93 M€) y 1.373 lineas con la obra a cero.

R15. El sistema debe publicar `partida_id` desde `hmores.paride`, informado en
302.575 lineas (91,5 %). Medido: las 302.575 existen en `raw.obrparpar` y son de
la MISMA obra de la linea; cero inconsistencias.

## La unidad, que es lo que hace falsa una suma

R16. El sistema debe publicar la UNIDAD de `hmores.can` derivandola de
**`auxhor.medide`**: 1 = HORA, 2 = DIA, 3 = MES, 19 = UD. El clasificador NO es
`auxhor.ext`, que esta a cero en las 60 filas del catalogo.

R17. SI una linea apunta a un `auxhor.medide` fuera de 1, 2, 3 y 19, ENTONCES el
sistema debe publicarla con `unidad = 'DESCONOCIDA'` y un test debe fallar, para
que un quinto valor en origen no se traduzca en silencio.

R18. El sistema debe dejar escrito en la ficha que **sumar `cantidad` sin
filtrar `unidad` es una cifra falsa**. Reparto medido y trampa completa: la
tabla de `design.md`. Titular: el **71,7 % del euro esta en las lineas de MES**,
no en las de hora, y 10 lineas apuntan a un tipo de hora sin catalogo.

R19. El sistema debe publicar `importe` desde `hmores.tot` **con su signo**, sin
filtrar. Medido: `tot` cuadra con `round(can * pre, 2)` en 330.596 de 330.638
lineas; 11.036 valen 0 y 9.119 son negativas (correcciones).

R20. El sistema debe declarar en la ficha los defectos de calidad medidos en
origen y no corregirlos: 5 lineas con fecha 0, una con fecha del ano 3103, 6 con
ano fuera de 1990-2030 y 5 con mes fuera de 1-12.

## Superficie de consumo

R21. CUANDO un agente pregunte las horas imputadas a una obra en un periodo, el
sistema debe responder por `personal.v_pbi_horas_obra_mes`, con grano obra x ano
x mes x tipo de recurso, **construida solo con `unidad = 'HORA'`** para que la
trampa de R18 no se pueda cometer desde ahi, y **sin nombre ni DNI**.

R22. CUANDO un agente pregunte quien ha trabajado en una obra, el sistema debe
poder responderlo cruzando `personal.partes_lineas` con `personal.recursos`.
Ejemplo medido de 2026: obra 0695, oficial 1a albanil, 7.366,00 h, 170.470,10 €.

R23. El sistema debe traer la ficha de los tres objetos en el YAML nuevo
`config/diccionario/personal.yaml` y subir `version` en `00_global.yaml`. La
lista de pendientes esta vacia y es un trinquete: aqui no se aplaza ninguna.

## El esquema modulo y su propagacion

R24. El sistema debe construir los tres objetos en un paso propio
`build_personal`, con `depends_on = ["build_stg"]` —lee `stg.obras` para R14— y
que **no sea dependencia de ningun otro paso**: SI falla, ENTONCES la nocturna
debe continuar y terminar, como `compras` y `retenciones` (`R-FRESCURA`).

R25. El sistema debe dar de alta el esquema `personal` en los sitios que lo
hacen visible al resto del ETL: `ESQUEMAS_DEL_DATAMART`,
`DEFAULT_CONSUMPTION_SCHEMAS` (y `.env.example`), el comando propio y
`build_pipeline_steps` de `main.py`, y la lista de pasos nocturnos de `run-all`.
SI falta cualquiera de ellos, ENTONCES un test debe fallar.

R26. El sistema debe quedar cubierto por las tres puertas que ya existen:
`check-declarados`, `check-unicidad` y `check-relaciones`. Se alimentan del
diccionario: `personal.yaml` debe declarar `clave_negocio` y `relaciones`.

R27. CUANDO `build_personal` se ejecute dos veces seguidas, el sistema debe
dejar el mismo contenido en los tres objetos (`CREATE ... IF NOT EXISTS`,
`TRUNCATE` + `INSERT`, `CREATE OR REPLACE VIEW`).

R28. Los tests de esta feature NO deben tocar red ni base de datos: se verifican
sobre el texto del SQL, el DDL y el cableado del step. Las cifras contra la base
viva son verificacion MANUAL del humano.
