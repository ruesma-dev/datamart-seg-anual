# F-147 · Requisitos (BORRADOR: decisiones abiertas marcadas **[ABIERTA]**)

> Presupuesto del contexto que `mcp-bbdd` sirve con `contexto_bbdd()`: cada regla
> publica un resumen corto que basta por sí solo, el detalle viaja bajo demanda y
> una puerta impide que lo servido crezca en silencio.
>
> **Medido (Azure, v58, 2026-10-22)**: ~86.000 caracteres por conversación.
> Reglas 50.831, enrutado ~20.400 (283 preguntas de 114 objetos), bloques de
> `_meta.diccionario_contexto` ~13.700 (`esquemas` 10.549).
> Revisión regla a regla: [`revision_reglas.md`](revision_reglas.md).

## Reparto de responsabilidad (no se discute aquí, se respeta)

- **CUÁNTO se publica** es de este repositorio: el texto de `config/diccionario/`,
  las columnas de `_meta` y la puerta.
- **CÓMO se sirve** es de `mcp-bbdd` (su F-029: índice de reglas en
  `contexto_bbdd`, texto entero con `describir_tabla` de su `ambito`). Aquí no se
  diseña su código; se pacta el contrato.

## Decisiones abiertas (las cierra el humano antes de aprobar la spec)

- **D1 [ABIERTA]** Regla a regla: qué se funde, se acorta, sale del MCP o se
  elimina, y el texto exacto de cada `resumen`. Propuesta en `revision_reglas.md`.
- **D2 [ABIERTA]** Eje de entrega. Propuesta: campo nuevo `entrega` con
  `resumen` (por defecto: resumen en el contexto, detalle bajo demanda),
  `entera` (siempre entera; ¿alguna? candidata: `R-IMPORTE-MES`) y `fuera_mcp`
  (no se publica en `_meta`: guía del ETL). `severidad` no cambia.
  Alternativa: reutilizar `severidad` (`aviso` = bajo demanda); descartada en la
  propuesta porque mezcla «cuánto importa» con «cuándo se lee».
- **D3 [ABIERTA]** Códigos de las reglas fundidas: código nuevo (`R-PERFILES`,
  `R-COMPRAS-LINEA`) o conservar uno de los existentes. Afecta a los `avisos` de
  las fichas, a `CODIGOS_REGLAS_OBLIGATORIAS` (`R-ABONO-NEGATIVO`,
  `R-LINEA-ID-NO-UNICA` y `R-COMPRAS-TIPO-DOC` son obligatorias hoy) y a lo que
  cite `mcp-bbdd`.
- **D4 [ABIERTA]** `fuera_mcp`: la fila NO se publica en `_meta.diccionario_reglas`
  (ahorro inmediato, sin esperar a `mcp-bbdd`) o se publica con la marca y la
  filtra el MCP. Propuesta: no publicarla; quien la necesita lee el YAML.
- **D5 [ABIERTA]** `R-ALBARAN-ABSURDO`: seguir con la regla o marcar la anomalía
  en el ETL (columna) y dejarla en la ficha. Lo segundo es otra feature.
- **D6 [ABIERTA]** `R-OBRA-ACTIVA`: qué es «obra activa» para Negocio sobre
  `maestro.obras.estado`. Puede ir al glosario de F-054.
- **D7 [ABIERTA]** `R-COMPRAS-SIN-IVA` es falsa desde F-128: corregirla dentro de
  F-147 o en un arreglo inmediato aparte (recomendado: aparte, ya).
- **D8 [ABIERTA]** Enrutado: (a) campo propio en la ficha (`preguntas_enrutado`,
  lista de ≤N) que lee `mcp-bbdd`, o (b) las N primeras de `ejemplos_preguntas`,
  con N publicado en `_meta.diccionario_contexto` y el recorte hecho por el MCP.
  Valor de N: 1 (114 preguntas) o 2 (205). `describir_tabla` las sigue dando todas.
- **D9 [ABIERTA]** El bloque `esquemas` (10.549): dentro del alcance (acortar
  `para_que_sirve`) o fuera y solo vigilado por la puerta.
- **D10 [ABIERTA]** Tope inicial de la puerta: lo publicado hoy (mide la deuda y
  solo baja) o el objetivo tras la feature. Propuesta: el valor tras la feature,
  con la historia anotada junto al número como en `PENDIENTES_MAX`.

## Requisitos

### Resumen por regla (contrato aditivo con `mcp-bbdd`)

- **R1.** El sistema debe aceptar en cada regla de `00_global.yaml` una clave
  `resumen` de texto.
- **R2.** SI una regla publicable no declara `resumen`, o lo declara con menos de
  40 o más de 300 caracteres, ENTONCES la validación del diccionario debe fallar
  nombrando la regla. **[ABIERTA: los límites]**
- **R3.** CUANDO se publica el diccionario, el sistema debe escribir el `resumen`
  de cada regla en una columna nueva `resumen` de `_meta.diccionario_reglas`,
  AÑADIDA AL FINAL, sin cambiar el nombre, el tipo ni el contenido de las
  columnas que `mcp-bbdd` lee hoy (`codigo, titulo, severidad, ambito, regla,
  motivo`, por `orden, codigo`).
- **R4.** El DDL de `_meta.diccionario_reglas` debe añadir la columna de forma
  idempotente sobre una base que ya tiene la tabla y, MIENTRAS la columna ya
  exista, no debe ejecutar ningún `ALTER TABLE` (corre en cada publicación y el
  `ALTER` bloquea a los lectores del MCP).
- **R5.** DONDE una regla declare `entrega` (D2), el sistema debe validar su
  vocabulario y publicarla también como columna aditiva. **[ABIERTA: D2]**
- **R6.** DONDE una regla sea `fuera_mcp`, el sistema NO debe publicarla en
  `_meta.diccionario_reglas` y debe seguir validándola (obligatorias, ámbitos).
  **[ABIERTA: D4]**

### Contenido (decidido en D1)

- **R7.** El contenido de las reglas debe ser el decidido en D1: fusiones,
  eliminaciones, textos acortados y resúmenes, con `version` nueva en
  `00_global.yaml`.
- **R8.** CUANDO una regla se funde o se elimina, el sistema debe actualizar los
  `avisos` que la citan y `CODIGOS_REGLAS_OBLIGATORIAS`, y el detalle que salga
  de la regla debe quedar en la ficha del objeto al que pertenece (ninguna
  información de la regla se pierde sin decidirlo).
- **R9.** Ningún `resumen` publicado debe contener recuentos o importes medidos
  (envejecen); sí nombres de columna, valores literales y umbrales.
  **[ABIERTA: si se exige con test o queda a juicio del reviewer]**

### Enrutado (D8)

- **R10.** El enrutado que se publica debe tener como máximo N preguntas por
  objeto, sin quitar ninguna de las que `describir_tabla` sirve.
  **[ABIERTA: mecanismo y N]**

### La puerta de tamaño

- **R11.** El sistema debe calcular desde los YAML, sin red ni BBDD, el tamaño en
  caracteres de lo que `contexto_bbdd` servirá entero: el índice de reglas
  (código + título + resumen de las publicables, más regla y motivo de las
  `entera`), el enrutado (con el máximo de R10) y el `texto` de todos los bloques
  de `_meta.diccionario_contexto`.
- **R12.** SI ese tamaño supera el tope declarado en el repositorio, ENTONCES
  `bash harness/init.sh` debe acabar en rojo diciendo cuánto sobra y de qué parte.
- **R13.** El tope debe ser un trinquete: SI el tamaño medido queda por debajo
  del tope en más de un margen, ENTONCES la puerta debe pedir bajarlo.
  **[ABIERTA: margen; D10]**
- **R14.** SI el diccionario publica un bloque nuevo en
  `_meta.diccionario_contexto`, ENTONCES su texto debe contar en la puerta (el
  glosario de F-054 va a la tabla `_meta.glosario`, que se lee bajo demanda y no
  cuenta).

### Documentación y despliegue

- **R15.** `azure-apps/datamart_seg_anual.md` debe describir la columna nueva, su
  semántica (el resumen basta por sí solo; el detalle es `regla` + `motivo`) y
  el reparto con la F-029 de `mcp-bbdd`, en el mismo trabajo.
- **R16.** `docs/ARCHITECTURE.md` y `docs/CONVENTIONS.md` (sección del
  diccionario) deben decir que toda regla lleva resumen y que hay presupuesto.
- **R17.** La medida antes y después (las tres partes) debe quedar en
  `progress/impl_F-147.md`; el despliegue (imagen, publicar, `check-diccionario`)
  es MANUAL del humano y va en `progress/current.md` con sus comandos.

## Fuera de alcance

- El código de `mcp-bbdd` (su F-029) y cualquier cambio en su `config.yaml`.
- Filtrar las reglas por perfil al servirlas (hallazgo 5 de la revisión): es del
  MCP, que puede usar el `ambito` publicado.
- Corregir el dato del albarán absurdo o dar significado a `es_activa` (D5, D6).
- El glosario de F-054, salvo que su forma no cuente en el presupuesto (R14).
