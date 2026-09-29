# Exploración · organigrama de obra (delegado, jefe de grupo, jefe de obra) y forma de pago del contrato

Fecha: 2026-09-22 · solo lectura · Sigrid por `sigrid-api` y datamart (`psql-albaranes-rs9k2`, build del
2026-09-18) en transacción `READ ONLY` · sin commit. Peticiones de Juan Romero del 2026-09-16 y del 2026-09-17.

## A · Delegado, jefe de grupo y jefe de obra

### A1 · Dónde vive cada uno (medido)

**La pestaña «+DATOS» son los campos extendidos de obra** (`defext` con `tip = 42`, valores en `conext`).
`defext` define 5 campos de obra, y 4 de ellos son personas, **todas del tipo CONCEPTO** (`camtip = 6`,
`camtab = 'emp'`). El valor es un `ide` de empleado guardado en `conext.valn`:

| `conext.cod` | `defext.res` | obras (de 922 en Sigrid) | en `maestro.obras` (921) | en `stg.obras` (584) | personas distintas |
|---|---|---|---|---|---|
| `25` | **Delegado** | 35 | 35 | **34** | 3 (Posada 15, Vicente Herranz 14, Bernal 6) |
| `20` | **Jefe de grupo** | 36 | 36 | **35** | 10 |
| `5`  | Jefe Administración | 37 | 37 | 36 | 2 |
| `10` | Administrativo de obra | 454 | 454 | 447 | 36 |
| `15` | (versión de planificación, no es persona) | 123 | — | — | — |

- **Los cuatro campos solo se rellenan desde 2023**: el delegado va de la obra `0672` a la `0726` (altas del
  2023-07-06 al 2026-08-13). En las 106 obras «en curso» de la cabecera (inicio real sin fin real) hay
  **25 con delegado y 26 con jefe de grupo**. Cobertura baja porque el campo es reciente, no porque la
  lectura esté mal.
- **Hoy ya se ingieren**: `raw.conext` entra entera (el 2026-09-18 trae los cuatro códigos con las mismas
  cifras) y `raw.con` resuelve el nombre. **Publicarlos no pide ingesta nueva.** OJO: `conext.cod` se
  repite entre tipos de concepto (hay un `'10'` y un `'01'` de otras entidades), así que la unión tiene que
  filtrar `con.tip = 42` de la obra.
- **El nombre se resuelve** con `raw.con.res` del `valn` (R-SIGRID-CON): 100 % de los valores apuntan a un
  `con` de `tip = 43` (empleado) y existen en `raw.emp` (35/35, 36/36, 37/37, 454/454).

**La pestaña «gestión» es `obr`.** Columnas de persona que tiene (diccionario de `azure-apps/sigrid_tablas.md`
y conteo sobre las 922 fichas / las 584 de seguimiento):

| columna | qué es según Sigrid | apunta a | 922 | 584 |
|---|---|---|---|---|
| `empide` | Técnico responsable | `emp` | 493 | **479** (ya publicado) |
| `emp1ide` / `emp2ide` | Técnico responsable niv 1 / niv 2 | `emp` | **0 / 0** | 0 / 0 |
| `ageide` | Agente | `age` (propiedad de `con`, `tip = 7`) | 482 | **471** |
| `diride` | Director de obra | `ref` (tercero externo, `tip = 40`) | 8 | 5 (ya publicado) |
| `delide` | Delegación (catálogo `auxdel`, no persona) | `auxdel` | — | 26 |

`obrx` (extensión de obra, no se ingiere) repite `empide`/`diride`/`peride`: 5, 3 y 3 obras de 922. No aporta
nada. `obrctr` **no tiene ninguna columna de persona** (solo `cliide`, `pagide`, `retide`, `sitide`, `tipide`).
`condir` (803 filas en `raw`) **no tiene ni una dirección de obra**: 783 son de `tip = 5`, 14 de `tip = 4` y 6
de `tip = 40`. Aquí no hay nada del organigrama.

### A2 · El jefe de grupo tiene una segunda fuente con 13 veces más cobertura: `obr.ageide`

Los 29 agentes que usan las obras son **personas de Ruesma**. 26 de ellos tienen ficha de empleado en
`age.empide`. **Donde están los dos datos, el agente ES el jefe de grupo en 34 de las 36 obras.** Contra el
delegado solo coincide en 6 de 35. Así que `obr.ageide` hace de «jefe de grupo» con **471 de 584 obras**
(103 de las 106 en curso) frente a los 35 del campo extendido. Los dos que más obras llevan, Vicente Herranz
(128) y Posada (124), son también los delegados de los campos extendidos. Parece que en obras antiguas el
agente era el responsable de rango superior. **Es una deducción de los datos, no algo que diga el origen:
hay que confirmarlo con Juan.**
- **Nombre**: sale de `raw.con.res` sin ingestar nada nuevo. Para enlazarlo a un empleado hace falta
  `age.empide`, y **la tabla `age` NO se ingiere** (sería ingesta nueva, pequeña: 29 agentes en uso).
- **TRAMPA DE DATOS PERSONALES**: el `con.cod` de 17 agentes **tiene formato de número de afiliación a la
  Seguridad Social** (`28/10696480/36`). No se debe publicar el `codigo` del agente, solo su nombre.

### A3 · El jefe de obra: **no hay un campo que se llame así**

Lo hemos buscado en `defext`, en `obr`, en `obrx`, en `obrctr` y en `con`, y no existe ningún campo con esa
etiqueta. Hay dos candidatos, los dos medidos:
1. **`obr.empide`, el técnico responsable ya publicado.** Lo cruzamos con el tipo de recurso de la persona
   (`res.restipide` → `auxrestip`, clasificación de hoy). De las 479 obras: **JEFE DE OBRA 277**, JEFE DE
   GRUPO 160, AYTE. JEFE OBRA 15, DIRECTOR CONSTRUCCIÓN 15, sin recurso 8, ENCARGADO 3 y TÉCNICO COMPRAS 1.
   Es muy probable que la pestaña «gestión» de Sigrid llame «jefe de obra» a este campo. Pero **en una de
   cada tres obras quien figura es un jefe de grupo**, y eso explicaría por qué Juan no lo reconoce como tal.
2. **Deducido de los partes** (`hmores`, que F-057 publica): **332 de 584 obras** tienen horas imputadas
   por un recurso de tipo `JEFE DE OBRA` (98 recursos). Es «quién ha trabajado como jefe de obra», no
   «quién está asignado», y una obra puede tener varios.

**Hay que preguntarle a Juan, con captura de la pestaña «gestión»,** qué etiqueta tiene el campo que él
llama jefe de obra. Si es el técnico responsable, ya está publicado y lo que falta es explicarlo en la ficha.

### A4 · `director_obra_ide`: la columna es la correcta, pero no es un rol de Ruesma

`obr.diride` es el «Director de obra» **de la dirección facultativa**. Apunta a `ref` (terceros), y sus 8
valores son arquitectos o sociedades externas (p. ej. «ARPROMA», «GRUPO ZENA»). Su cobertura de 5 obras es
real: Ruesma casi no lo rellena. **No sirve para el organigrama de producción.** Si se deja, que sea con su
nombre (`con.res`, se resuelve en 8 de 8) y con la ficha diciendo que es un externo.

### A5 · El enlace con `personal` (F-057)

`personal.recursos` **todavía no existe en producción**: F-057 está en su rama. Su clave hacia el empleado
es `empleado_id = raw.emp.ide`, que es justo el `valn` de los campos extendidos. Hoy (medido sobre `raw.res`,
por `res.conide`) tienen recurso: **el delegado 35 de 35, el jefe de grupo 36 de 36, el administrativo de
obra 350 de 454 y el jefe de Administración 0 de 37**. Los recursos son el grano de F-057, así que quien no
tenga recurso no aparece. Además `empleado_id` **no es único** (3 recursos comparten `conide`), y la unión
necesita una guarda contra la multiplicación. Propuesta: publicar el `*_empleado_id` y el nombre de `con.res`
en la obra, que cubre al 100 %. `personal` queda como enlace opcional, no como fuente del nombre.

### A6 · Cómo se ficha

- Solo con `raw` actual: **delegado, jefe de grupo (campo extendido), jefe de Administración y
  administrativo de obra**, con su id y su nombre, en `cierre.v_pbi_cierre_cabecera` (donde ya están el
  técnico y el director) o en `maestro.obras`.
- **Jefe de grupo «ampliado»** con `obr.ageide`: el nombre sale sin ingesta nueva. El empleado necesita
  ingerir `age`. Y antes hay que confirmar con Juan que el agente es el jefe de grupo.
- **Jefe de obra**: queda bloqueado hasta que Juan diga qué campo es. El candidato fuerte es `obr.empide`.
- Frontera: si se publica en `cierre`, cae el `CREATE OR REPLACE` de la vista (hoy es `DROP ... CASCADE`).
  El dueño del diccionario es `config/diccionario/cierre.yaml` o `maestro.yaml`.

## B · Forma de pago en `compras.contratos` (criterio 1 de F-067)

### B1 · Cobertura y traducción (medido sobre `compras.contratos`, 19.005 filas)

- **`ctr.pagide` está en 18.996 de 19.005 contratos (99,95 %) y se traduce en 18.996 de 18.996** contra
  `compras.formas_pago` (`raw.auxpag`, 69 filas + `auxefp`). No hay huérfanos. Las más usadas: Pagaré 120
  (5.299), Pagaré 90 (2.374), Pagaré 120 días + retención (2.291) y CONFIRMING TR 150 + RET (1.355).
- **Comprobado con CTSB25/0126** (obra 0686, MINGROI INVERSIONES 2008, S.L.): `pagide = 39` →
  `CFTR90R` «**CONFIRMING TR 90 + RET**», fórmula «**90 450R**», medio CONFIRMING / PAGARÉ. Tiene **17
  facturas** en `v_control_forma_pago`. Todo coincide con lo que dice Juan.
- En `ctr` hay además `pagtex` y `pagfor`, que son la **copia congelada en el contrato**. `pagfor` coincide
  con la fórmula del catálogo en 18.986 de 18.996 (10 distintas), y `pagtex` con el nombre en 18.340 (656
  distintas, seguramente porque el catálogo se renombró después). `diapag` está vacío en todos. Hay que
  decidir en la spec qué columna es la verdad: propongo el catálogo por `pagide` (lo mismo que hace la vista
  de control) y `pagtex` como «texto en el contrato».

### B2 · La cifra que justifica la feature

**2.986 contratos (15,7 %) no tienen ninguna factura** y hoy no enseñan su forma de pago por ninguna vía.
2.977 de ellos tienen `pagide`. Por estado: FIR 1.879, TER 323, **PFP 309, EPF 258**, RES 147, RFP 47 y
COMD 23. **2.516 están vivos** (de PFP a FIR) y 551 son de 2025 o posteriores.

### B3 · Reutilización

`compras.v_control_forma_pago` (`sql/compras/06_pago_factura.sql`) hace
`LEFT JOIN raw.ctr ctr ON ctr.ide = pa.contrato_id` y `LEFT JOIN compras.formas_pago fpc ON
fpc.forma_pago_id = NULLIF(ctr.pagide, 0)`, y su comentario dice que llevarlo a `compras.contratos` «es
F-067». Se copia esa unión en `01_documentos.sql`, con `forma_pago_id`, `forma_pago`, `plazo_formula` y
`medio_pago` desde `compras.formas_pago`. Después la vista de control puede leer de `compras.contratos` y
dejar de tocar `raw.ctr`: la traducción queda en un único sitio. Las columnas nuevas van al final de la tabla.
Un detalle de orden: `formas_pago` es una vista del mismo esquema y tiene que existir antes que la tabla.

### B4 · La retención del contrato: barata y ya en `raw`

`raw.ctrrec` (F-066) tiene **6.363 filas para 6.355 contratos (33,4 %)**, como mucho 2 por contrato. El
`recide` se nombra con `con.res`. El 96,6 % es `558368` «Retención garantía 5 % (sobre base imponible)»; hay
además RET5T, RET2.5 y variantes. Trae `bas`, `valpor` y `cuo`. CTSB25/0126: 5 % sobre una base de
3.524.024,25 €, con cuota de 176.201,21 €. Por año, la cobertura va del 34 % al 40 % (2022-2026). Hay 6.596
contratos cuya forma de pago dice «+ RET», y 6.047 de ellos tienen `ctrrec`: **549 anuncian retención en el
nombre de la forma de pago y no tienen fila de retención**, lo que conviene declarar en la ficha. Como hay
hasta 2 filas por contrato, publicarla en `compras.contratos` exige agregar o elegir una (`pos`) para no
multiplicar el grano.

### B5 · Cómo se ficha

Es un trozo del criterio 1 de F-067, que está `pending`. F-084 ya se quedó con el estado. La forma de pago
(B1-B3) sale sola, sin ingesta nueva. La retención (B4) también, con la decisión de grano. La penalización
sigue sin campo en `ctr`. Conviene separarla como feature propia («condiciones del contrato») para no
esperar a la foto diaria, los comparativos y las actividades, que son el resto de F-067.
