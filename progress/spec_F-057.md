<!-- progress/spec_F-057.md -->
# F-057 · Spec escrita (spec-author, 2026-09-18)

Entregado: `specs/F-057-recursos-empleados-partes/` con `requirements.md`
(150/150), `design.md` (246/250) y `tasks.md` (25 tareas, una por línea).
Puerta de tamaño en verde. **No se ha tocado código, ni el estado de la feature,
ni se ha hecho push.**

> **REVISADA EL MISMO DÍA.** El humano resolvió A1 —el único punto que dejé
> abierto— y los tres objetos pasan de `stg` a un **esquema módulo propio
> `personal`**. Ver «A1, ya cerrado» al final. Las tareas T10-T20 son la
> propagación de ese cambio: doce puntos, uno por tarea.

Todas las cifras de la spec se **midieron contra Sigrid vivo el 2026-09-18** por
`sigrid-api` en solo lectura, agregando en SQL. Nada supuesto. Los scripts de
medición quedaron en el scratchpad, sin versionar.

## El hallazgo que cambia el diseño, y que no estaba en ninguna ficha

`hmores.can` **no son horas, y el clasificador de la unidad no es el que parece**.
`auxhor.ext` está a **cero en las 60 filas** del catálogo —quien lo mire concluye
que no clasifica nada—; el que clasifica es **`auxhor.medide`**, referencia a
`auxmed` (38 filas): 1 = HORA, 2 = DIA, 3 = MES, 19 = ud.

| unidad | líneas | cantidad | euros | % del dinero |
|---|---|---|---|---|
| HORA | 241.004 | **1.249.038,44 h** | 24.837.178,20 | 25,3 % |
| DIA (incidencias) | 9.723 | 4.225,46 d | 1.809,20 | 0,0 % |
| MES | 36.034 | 18.009,38 m | **70.458.900,29** | **71,7 %** |
| UD | 43.867 | 565.927,95 ud | 2.977.303,43 | 3,0 % |
| sin catálogo | 10 | 0 | 0 | 0 % |

`SUM(can)` en bruto da 1.837.201,23 mezclando horas de albañil con meses de jefe
de obra, días de vacaciones y kilómetros. **Es exactamente la cifra falsa que
esta feature habría publicado** si se hubiera escrito sobre la ficha original.
El aviso de F-072 («`auxhor` mezcla») apuntaba al problema pero no al mecanismo.

## Decisiones tomadas, con su motivo

1. **El eje es el RECURSO, no el empleado.** Medido: `res` 2.618 filas (1.354
   personas `cla=1`, 1.158 consumos `cla=0`, 106 medios `cla=2`), `emp` 1.354.
   **No es 1:1 en ninguna dirección**: 824 recursos casan con empleado (31,5 %),
   805 empleados casan con recurso, solo **797 pares recíprocos**, 24 empleados
   sin recurso, 3 discrepantes y **3 recursos comparten el mismo `conide`** (821
   distintos en 824 filas) — por eso el `JOIN` a `emp` va como
   `LEFT JOIN LATERAL ... ORDER BY ide LIMIT 1`, como en `maestro/04`. `emp` es
   atributo opcional, nunca grano ni filtro. `emp` **no** se publica como
   dimensión de plantilla: 62 de sus 152 columnas vienen vacías.
2. **La obra se ata por `hmores.obride`, el de la LÍNEA.** Informado en 329.265
   de 330.638 (99,58 %), 536 obras. En **769 líneas (0,23 %) la obra de la línea
   contradice a su cabecera** `hmo`, y manda la línea. **La trampa de `apu` /
   F-045 no aplica aquí y `maestro.centros_coste` (F-073) no se usa**: el parte
   trae la obra. `res.cenconide` está informado al 75,5 % pero con 9 valores
   distintos: no atribuye nada. Queda escrito para que F-045 no herede una
   respuesta que no es suya.
3. **«En rojo» = `con.fecbaj > 0`, y es BANDERA, no filtro.** `raw.res` no tiene
   columna de baja: la baja es la del CONCEPTO. Medido: 1.722 de baja de 2.618;
   entre personas, **1.034 de baja y 320 de alta**. La medición que decide:
   filtrar el hecho por «de alta» borraría **539.774,87 de 1.249.038,44 horas
   (43,2 %)**, de 287 de los 445 recursos que han imputado horas. El recurso de
   baja de hoy trabajó ayer. Codificación «Apellidos, Nombre»: coma en 609 de
   1.354 (45,0 %); no se normaliza.
4. **Datos personales: se publican nombre y DNI**, con la autorización del humano
   del **2026-09-18** citada dentro del requisito R7 («el dni puede salir, no es
   un problema»). Sin ofuscación, ni hash, ni truncado, ni tabla aparte. Lo que
   **no** sube es el resto de `emp`: Seguridad Social, banco, domicilio,
   nacimiento, sexo, estado civil, contacto y credenciales. La ficha del
   diccionario declara que el objeto contiene datos personales. `res.cif`
   informado en 629 de 1.354 personas (46,5 %); `emp.dni` en el 99,2 %.
5. **Sí sube a la superficie de consumo**, con tres objetos:
   `personal.recursos`, `personal.partes_lineas` y **una sola vista**
   `personal.v_pbi_horas_obra_mes` con
   `unidad = 'HORA'` cableado, para que la trampa de la unidad no se pueda
   cometer desde ahí. El material lo justifica: 20 años (2002-2026), **100 % de
   `paride` existe y es de la misma obra** (302.575 de 302.575, cero
   inconsistencias) y **94,9 % del euro en obras del seguimiento** (523 obras,
   1.226.158,60 h, 93,24 M€) frente a 12 administrativas (4,93 M€: GENERALES
   2,59 y POSTVENTA 2 1,85) y 1.373 líneas sin obra. No se filtra el universo
   (`R-UNIVERSO-OBRA`): se marca con `en_seguimiento`, resuelto por `EXISTS`
   contra `stg.obras` y no replicando su lista de códigos.
6. **`auxmed` no se ingiere**: la unidad va en un `CASE` sobre `medide`, con
   precedente `stg/02_ambitos.sql` y el seguro de R17 (un quinto valor sale como
   `DESCONOCIDA` y el test-guarda falla). Ingerir 38 filas obligaría a tocar
   `tables_sigrid.yaml`, `check-raw-recuentos` y la ficha de `raw` para traducir
   cuatro literales estables, y el mandato de esta feature es `stg` y `mart`.
7. **Importe con signo**: `tot` cuadra con `round(can*pre,2)` en 330.596 de
   330.638 (99,99 %); 11.036 líneas a cero y **9.119 negativas** (correcciones),
   que no se filtran.

## A1, ya cerrado: esquema módulo `personal` (decisión del humano, 2026-09-18)

Lo dejé abierto —`stg` o esquema propio— y el humano eligió **esquema módulo
propio `personal`**, hermano de `compras`, `maestro` y `retenciones`. Sus dos
razones, por orden de peso:

1. **Permisos por esquema**, el argumento decisivo. F-087 crea un rol propio
   para Power BI con acceso solo a los esquemas de consumo. Con nombre y DNI en
   un esquema propio, «acceso a Power BI pero no a los datos de personal» es un
   `GRANT`; mezclados en `stg` —que además F-079 declaró consultable— esa
   distinción exigiría trocear permisos tabla a tabla.
   **CORREGIDO EL 2026-09-22 por el humano: Power BI SÍ ve `personal`**, y el
   rol propio de F-087 lo incluye. El esquema propio sigue sirviendo para
   quitar el acceso a un rol concreto con un `GRANT`.
2. **No bloquea.** `build_stg` es la puerta de F-024: un fallo del SQL de
   personal dentro de `build_stg` dejaría al `mart` sin construir esa noche. Los
   esquemas módulo fallan solos y `R-FRESCURA` avisa al consumidor.

**El SQL no cambia**; cambia dónde vive y qué step lo ejecuta:
`sql/personal/00_setup.sql` … `03_views.sql`, un
`build_personal_step.py` calcado de `build_retenciones_step.py` (131 líneas),
`depends_on = ["build_stg"]` —lee `stg.obras` para `en_seguimiento`— y **ningún
paso lo declara como dependencia**. En `run-all` va con los otros build de
negocio, detrás de `build_retenciones` y delante de `build_cierre`.

**La propagación son doce puntos, y cada uno es una tarea** (T10-T20): el step,
el orquestador, los tres puntos de `main.py` (comando propio,
`build_pipeline_steps`, `run-all`), `apply_grants_step.py` +
`DEFAULT_CONSUMPTION_SCHEMAS` + `.env.example`, `ESQUEMAS_DEL_DATAMART` (que es
lo que hace que `catalogo.py` mire el esquema), `check-declarados`,
`check-unicidad`, `check-relaciones`, el YAML nuevo
`config/diccionario/personal.yaml`, y los tests de cada uno.

**Efecto colateral aceptado**: `personal.v_pbi_horas_obra_mes` no lleva datos
personales pero vive en el esquema restringible. Si algún día Power BI necesita
las horas sin las personas, esa vista se mueve a `mart` y es un fichero; no se
parte el esquema por adelantado.

## Lo que sigue abierto

**A2 · Declarado y no resuelto, a propósito (D8 del diseño).** El coste de
personal por obra **completo no es `SUM(importe)` de HORA**: el **71,7 % del
euro está en las líneas de MES** (estructura de obra: MES JEFE DE OBRA solo,
18,80 M€). La vista publica horas; el euro por obra sale de
`personal.partes_lineas` sin filtrar unidad, y la ficha lo dice. Pasar de horas
a euros con el precio de coste por recurso (`raw.reshor`, 8.949 filas) es
**F-061**, no esto.

**A3 · Defectos de origen que se declaran y no se corrigen**: 5 líneas con fecha
0, una con fecha del año 3103, 6 con `ano` fuera de 1990-2030, 5 con `mes` fuera
de 1-12; `hmo.feccie` y `hmo.cla` a cero en las 6.884 cabeceras y `hmo.reside`
informado en 6.

## Ejemplo medido de lo que se podrá responder y hoy no

Obra **0695**, año 2026, oficial 1ª albañil: **7.366,00 h y 170.470,10 €**.
2026 completo (a 17-sep): 18.509 líneas, 87.768,40 h, 2.162.826,34 €, 59 obras y
100 recursos.
