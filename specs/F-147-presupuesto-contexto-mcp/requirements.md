# F-147 · Requisitos

> Presupuesto del contexto que `mcp-bbdd` sirve con `contexto_bbdd()`: cada regla
> publica un resumen corto que basta por sí solo, el detalle viaja bajo demanda y
> una puerta impide que lo servido crezca en silencio.
>
> **Medido (Azure, v58, 2026-10-22)**: ~86.000 caracteres por conversación.
> Reglas 50.831, enrutado ~20.400 (283 preguntas de 114 objetos), bloques de
> `_meta.diccionario_contexto` ~13.700 (`esquemas` 10.549).
> Revisión regla a regla, DECIDIDA: [`revision_reglas.md`](revision_reglas.md).

## Reparto de responsabilidad

- **CUÁNTO se publica** es de este repositorio: el texto de `config/diccionario/`,
  las columnas de `_meta` y la puerta.
- **CÓMO se sirve** es de `mcp-bbdd` (su F-029: índice de reglas en
  `contexto_bbdd`, texto entero con `describir_tabla` de su `ambito`, recorte del
  enrutado). Aquí no se diseña su código; se le ofrece un contrato aditivo.

## Decisiones del humano (2026-10-22)

- **D1** La tabla de `revision_reglas.md` tal cual: resúmenes, recortes,
  fusiones, `R-COSTE-CONSULTA` eliminada y repartida a fichas, `R-SIGRID-CON`
  fuera del MCP.
- **D2** Campo `entrega` en cada regla: `resumen` (por defecto), `entera` o
  `fuera_mcp`. `severidad` no cambia.
- **D3** Códigos nuevos: `R-PERFILES` (funde `R-CONTABILIDAD-RESTRINGIDA`,
  `R-TESORERIA-RESTRINGIDA`, `R-COMPRAS-RESTRINGIDA`, `R-PERFIL-RESTRINGIDO`) y
  `R-COMPRAS-LINEA` (funde `R-COMPRAS-TIPO-DOC`, `R-ABONO-NEGATIVO`,
  `R-LINEA-ID-NO-UNICA`).
- **D4** Las reglas `fuera_mcp` NO se publican en `_meta.diccionario_reglas`.
- **D5** `R-ALBARAN-ABSURDO` se mantiene DE MOMENTO (Administración corregirá las
  dos líneas en Sigrid y entonces se retira), ocupando lo mínimo y sin cifras
  que envejezcan en el texto servido.
- **D6** `R-OBRA-ACTIVA` se reescribe con el criterio de obra VIVA de F-025
  (`config/business_rules.yaml` → `ventana`), sin inventar otro.
- **D7** La corrección de `R-COMPRAS-SIN-IVA`, `convenciones.importes_iva` y la
  cabecera de `compras.yaml` entra en F-147.
- **D8** Enrutado: 2 preguntas por objeto. Mecanismo (b): las 2 PRIMERAS de
  `ejemplos_preguntas`; el recorte lo hace `mcp-bbdd` en su F-029. Justificación
  en `design.md`.
- **D9** El bloque `esquemas` se acorta dentro de F-147.
- **D10** Tope de la puerta = el tamaño tras la feature, con trinquete.

## Requisitos

### Resumen y entrega por regla (contrato aditivo)

- **R1.** El sistema debe aceptar en cada regla de `00_global.yaml` las claves
  `resumen` (texto) y `entrega` (`resumen` | `entera` | `fuera_mcp`; si falta,
  `resumen`).
- **R2.** SI una regla no declara `resumen`, o lo declara con menos de 40 o más
  de 300 caracteres, ENTONCES la validación del diccionario debe fallar nombrando
  la regla. Vale también para las `fuera_mcp`.
- **R3.** SI una regla declara una `entrega` fuera del vocabulario, ENTONCES la
  validación debe fallar nombrando la regla y el vocabulario.
- **R4.** CUANDO se publica el diccionario, el sistema debe escribir `resumen` y
  `entrega` en dos columnas nuevas de `_meta.diccionario_reglas`, AÑADIDAS AL
  FINAL, sin cambiar nombre, tipo ni contenido de las que `mcp-bbdd` lee hoy
  (`codigo, titulo, severidad, ambito, regla, motivo`, por `orden, codigo`).
- **R5.** El DDL debe añadir esas columnas de forma idempotente y, MIENTRAS ya
  existan, no debe ejecutar ningún `ALTER TABLE` (corre en cada publicación y el
  `ALTER` bloquea a los lectores del MCP).
- **R6.** CUANDO se publica, el sistema NO debe escribir en
  `_meta.diccionario_reglas` las reglas `fuera_mcp`, y `n_reglas` de
  `_meta.diccionario_publicacion` debe contar solo las publicadas; la validación
  (obligatorias, ámbitos, resumen) debe seguir aplicándose a todas.

### Contenido (D1, D3, D5–D7)

- **R7.** Las reglas, sus `resumen`, `entrega`, recortes de `regla`/`motivo`,
  fusiones y eliminaciones deben ser las de `revision_reglas.md`; `R-SIGRID-CON`
  con `entrega: fuera_mcp`; `version: 59` en `00_global.yaml`.
- **R8.** `CODIGOS_REGLAS_OBLIGATORIAS` debe contener `R-PERFILES` y
  `R-COMPRAS-LINEA` y no los tres códigos que funde `R-COMPRAS-LINEA`; y ningún
  fichero del repositorio fuera de `progress/`, `specs/` y `BACKLOG.md` debe
  citar un código retirado (los cinco fundidos, los tres de compras y
  `R-COSTE-CONSULTA`).
- **R9.** El detalle que sale de una regla al acortarla, fundirla o eliminarla
  debe quedar en la ficha del objeto al que pertenece, según la columna
  «Propuesta» de `revision_reglas.md` (inventario de empresa, contadores de lo
  restringido, cuenta bancaria del proveedor, coste de consulta).
- **R10.** `R-OBRA-ACTIVA` debe definir «obra activa» como la obra VIVA de F-025,
  citar `config/business_rules.yaml` (`ventana`), dar en su `regla` la consulta
  equivalente sobre `maestro.obras` y `stg.fases`, y decir que
  `_meta.v_frescura_obra` (`motivo = 'ventana' AND NOT congelada`) no es
  equivalente.
- **R11.** SI cambian `estados_que_congelan`, `patron_codigo_administrativo` o
  `meses_sin_actividad` en `config/business_rules.yaml` y `R-OBRA-ACTIVA` no,
  ENTONCES un test debe fallar.
- **R12.** Ni `R-COMPRAS-SIN-IVA`, ni `convenciones.importes_iva`, ni la cabecera
  de `config/diccionario/compras.yaml` deben afirmar que todos los importes de
  `compras` son sin IVA ni que `importe_contratado` es el único con IVA; la
  regla debe nombrar `total_factura`, `total_documento` y `total_a_pagar`.
- **R13.** `R-ALBARAN-ABSURDO` no debe contener en `resumen`, `regla` ni
  `motivo` ningún importe ni total medido (ni «M€», ni «billones», ni cifras con
  separador de miles); sí el albarán `AC21/03345`, el filtro `< 1e8` y el umbral
  de 1.000 M€; y `regla` + `motivo` deben sumar como mucho 400 caracteres.
- **R14.** `convenciones.identidad_sigrid` debe quedar en una entrada corta que
  remita a `R-SIGRID-CON` como guía del ETL, y `convenciones.fechas` no debe
  hablar de `raw`.

### Enrutado (D8)

- **R15.** Toda ficha recomendada con más de 2 `ejemplos_preguntas` debe tener
  como 2 primeras las que mejor enrutan; ninguna pregunta se borra (siguen
  saliendo en `describir_tabla`).

### Bloque `esquemas` (D9)

- **R16.** SI el `para_que_sirve` de un esquema en `00_global.yaml` supera 350
  caracteres, ENTONCES la validación debe fallar nombrando el esquema.

### La puerta de tamaño (D10)

- **R17.** El sistema debe calcular desde los YAML, sin red ni BBDD, lo que
  `contexto_bbdd` servirá entero: reglas (código + título + `resumen` de las
  publicables, más `regla` + `motivo` de las `entera`), enrutado (clave y 2
  primeras preguntas de cada ficha recomendada) y el `texto` de todas las filas
  de `_meta.diccionario_contexto`.
- **R18.** SI el total supera `PRESUPUESTO_MAX`, ENTONCES `bash harness/init.sh`
  debe acabar en rojo diciendo cuánto sobra y el desglose por parte.
- **R19.** SI el total queda más de 1.000 caracteres por debajo de
  `PRESUPUESTO_MAX`, ENTONCES el test debe fallar pidiendo bajar el tope
  (trinquete).
- **R20.** CUANDO el diccionario publique un bloque nuevo en
  `_meta.diccionario_contexto`, su texto debe contar en el total.

### Documentación y despliegue

- **R21.** `azure-apps/datamart_seg_anual.md` debe describir las dos columnas, su
  semántica (el resumen basta; el detalle es `regla` + `motivo`; `fuera_mcp` no
  se publica), las 2 primeras preguntas como enrutado y el reparto con la F-029
  de `mcp-bbdd`, en el mismo trabajo.
- **R22.** `docs/ARCHITECTURE.md` y `docs/CONVENTIONS.md` deben decir que toda
  regla lleva resumen, qué es `entrega` y que hay presupuesto con trinquete.
- **R23.** La medida antes y después (las tres partes, con la fórmula de R17) debe
  quedar en `progress/impl_F-147.md`; el despliegue (imagen, `publicar-diccionario`,
  `check-diccionario`, medida de `contexto_bbdd` en Azure) es MANUAL del humano y
  va en `progress/current.md` con sus comandos.

## Fuera de alcance

- El código de `mcp-bbdd` (su F-029), su `config.yaml` y sus comentarios que
  citen códigos retirados (se le avisa; los arregla quien es dueño).
- Filtrar las reglas por perfil al servirlas: es del MCP (hallazgo 5).
- Marcar en el ETL el albarán absurdo o dar valor real a `es_activa` (D5, D6).
- El glosario de F-054: va a la tabla `_meta.glosario`, que no cuenta (R20 solo
  mide `_meta.diccionario_contexto`).
