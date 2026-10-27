# F-150 · La receta de la caja (fase 1)

Mediciones: `progress/spec_F-150.md`. Decisiones CERRADAS (27-10) en `design.md` §9, marcadas
«(Dn)». **Objetivo**: que la IA pase el devengo de una obra a caja SIEMPRE en el mismo orden (la
receta), cobrando la venta CON coeficientes por partida, repartiendo en varios meses con inicio
diferido, con la retención del cliente bien leída (D9) y el IVA de venta contrastado (D8). Sigue
sin haber caja proyectada (F-140): la función que la calcula es F-151.

Vocabulario:
- **Receta**: los siete pasos de `design.md` §3 (DEVENGO … CARTERA).
- **Coeficiente de venta de una partida**: `importe_oficial / importe` de `stg.presupuesto` en un
  master de venta (11) o de certificación (9), en la versión V de la partida (F-140).
- **Perfil**: lista de pares `[meses, porcentaje]` que reparte un importe entero en el tiempo.

## La receta (D1, D7)

R1. Cada hipótesis del catálogo debe declarar `paso_receta`, uno de los siete pasos; SI falta o
no es uno de ellos, ENTONCES `validar_catalogo` lo devuelve como error y el paso no publica nada.

R2. `tesoreria.hipotesis_caja` debe publicar `paso_receta`, y el YAML real asignar cada código al
paso de `design.md` §6 (test que fija la tabla entera).

R3. La `descripcion` de la ficha `tesoreria.hipotesis_caja` debe contener la receta: siete pasos
numerados del 1 al 7 en el orden de `PASOS_RECETA`, y en el tramo de cada paso los códigos de
las hipótesis cuyo `paso_receta` es ese (test que cruza el YAML con la ficha).

R4. La receta debe nombrar sus ingredientes (`tesoreria.devengo_pendiente_obra_mes`,
`tesoreria.devengo_pendiente_partida`, `importe_pendiente_con_coeficientes`,
`tesoreria.condiciones_contrato_compra`, `tesoreria.condiciones_contrato_cliente`,
`tesoreria.efectos`, `cartera_emitida_tras_cierre`) y decir: COSTE se paga y VENTA se cobra; los
perfiles reparten el importe entero; la retención va sobre la base sin IVA; el devengo va sin IVA;
nunca un coeficiente medio de obra; redondear solo al final (test por frases clave).

R5. El `resumen` de `R-CAJA-HIPOTESIS` debe nombrar la receta, `tesoreria.hipotesis_caja`,
`tesoreria.hipotesis_caja_obra`, la cartera y los niveles `DEFECTO`, `OBRA` y `USUARIO`, en 230
caracteres o menos (hoy mide 230); su `regla` debe empezar remitiendo a la receta.

R6. El presupuesto de F-147 no debe subir: `PRESUPUESTO_MAX` queda en 30.873 y la puerta del
árbol pasa (medida esperada 30.864).

R7. (D1) `docs/CONVENTIONS.md` y `docs/ARCHITECTURE.md` deben recoger la excepción acotada: una
receta que combina objetos del propio datamart para un dato que este no publica puede ir en una
ficha; los valores de negocio siguen en `config/hipotesis_caja.yaml`.

## El coeficiente de venta por partida (D2, D3, D4, D6)

R8. Una función de dominio `coeficiente_venta(importe_cert, oficial_cert, importe_venta,
oficial_venta)` debe devolver el coeficiente redondeado a 6 decimales y su fuente:
`CERTIFICACION` si el importe del 9 existe y no es 0; si no, `VENTA` si el del 11 existe y no es
0; si no, `(None, None)`. Un `oficial` ausente vale el importe.

R9. `07_devengo_pendiente.sql` debe leer `stg.presupuesto` solo filtrando obra, `ambito_id IN (9,
11)` y `fase_num` = la versión V de la obra (D3); un test rechaza cualquier lectura de
`stg.presupuesto` en `sql/tesoreria/` sin esos tres filtros.

R10. `tesoreria.devengo_pendiente_partida` debe publicar, en las filas VENTA,
`coeficiente_venta`, `fuente_coeficiente` y `pendiente_con_coeficientes =
ROUND(pendiente × coeficiente_venta, 2)`; en las de COSTE, las tres NULL.

R11. (D6) SI una partida VENTA con `pendiente > 0` no tiene coeficiente, ENTONCES el SQL debe
fallar con su recuento antes de vaciar las tablas de consumo.

R12. `tesoreria.devengo_pendiente_obra_mes` debe publicar `importe_pendiente_con_coeficientes`
(el `pendiente_con_coeficientes` de cada partida repartido con su mismo perfil y la regla de
`repartir_pendiente`) y `coeficiente_venta` (su cociente con `importe_pendiente`, 6 decimales,
NULL si este es 0); en COSTE, NULL. La guarda de la suma debe comprobar también que, por (obra,
concepto) VENTA, la suma mensual con coeficientes iguala la de la partida al céntimo.

R13. Ninguna columna nueva debe casar con `PATRON_COLUMNA_DE_CAJA`, y el SQL nuevo no puede
aplicar un valor de hipótesis (los tests R6/R16 de F-140 siguen pasando sobre `07`).

R14. `R-VENTA-COEFICIENTES` debe incluir en su `ambito` las dos tablas `devengo_*`, y sus fichas
deben decir que lo que lleva coeficientes no se suma ni compara con el coste, lo ejecutado ni la
venta sin ellos.

## El reparto en varios meses (D5)

R15. El dominio debe admitir la unidad `PERFIL_MESES`: lista no vacía de pares `[meses,
porcentaje]`, `meses` entero de 0 a 120 y estrictamente creciente, `porcentaje` > 0 y ≤ 100 con
2 decimales como mucho, suma exacta 100; SI no, ENTONCES un error por cada fallo, igual en
`valor_defecto` y en la sección `obras`.

R16. H03 (PAGO) y H08 (COBRO) deben pasar a `PERFIL_MESES` con defecto `[[0, 100]]` y `[[1,
100]]`, y nacer H24 (PAGO) y H25 (COBRO) en `PERFIL_MESES` con defecto `[[0, 100]]`, paso
PLAZO, `validado: false` y `admite_obra: true`: 25 hipótesis.

R17. CUANDO la sección `obras` del YAML dé un perfil a una obra, el paso debe cargarlo en
`tesoreria.hipotesis_caja_manual` y `tesoreria.hipotesis_caja_obra` debe publicarlo tal cual
(JSON), con nivel `OBRA` y fuente `MANUAL` (test del cargador y del `08` sin cambios).

R18. `tesoreria.hipotesis_caja.unidad` debe admitir `PERFIL_MESES` en una tabla ya existente
(`ALTER COLUMN ... TYPE VARCHAR(20)` idempotente en `00_setup.sql`, test del DDL).

R19. `tesoreria.hipotesis_caja_obra` debe publicar las 25 hipótesis por obra (fichas y tests de
F-140 que fijaban 23, al día).

## Lo que sale de R25 de F-140 (D8-D10)

R25. (D9) `valor_h10_sigrid` debe devolver: el valor único SI todos los contratos con el cliente
de la obra dan valor y el mismo (regla de F-140, su motivo); SI NO, el valor único de los
contratos con retención (> 0) CUANDO su `importe_adjudicado` suma al menos el 50 % del de todos
(nulo = 0), con un motivo propio; SI NO, nada. El orden de `resolver_hipotesis` no cambia.

R30. (D9) `tesoreria.condiciones_contrato_cliente` debe publicar `importe_adjudicado`
(`raw.obrctr.impadj`, NUMERIC(18,2), `ADD COLUMN IF NOT EXISTS`), y la rama H10 de `08` llevar
los literales del dominio (`50`, los dos motivos; test que los compara). H09 y H11 no cambian.

R26. (D10) La `descripcion` de H15 debe decir que solo aplica a formas de Sigrid con varios
vencimientos.

R27. (D8) El `fuente_defecto` de H12 debe decir que Sigrid no da el 10 % de la vivienda, que lo
fija Control de Costes por obra en la sección `obras` y que, si sale DEFECTO, la receta lo
contrasta; la cabecera del YAML da el ejemplo sin ninguna obra real (test por frases clave).

R28. (D8) `contraste_iva_venta(emitido, producido, coeficiente)` debe devolver el IVA implícito
`100 × (e / (p × k) − 1)` a 2 decimales y `GENERAL` si >= 17, `REDUCIDO` si <= 14,
`SIN_CONTRASTE` entre medias o si `p` o `k` faltan o son <= 0 o `e` <= 0; y el paso 6 de la
receta debe nombrar `tesoreria.efectos`, `mart.fact_seguimiento_mensual`, `Venta Real`,
`devengo_pendiente_obra_mes` y los dos umbrales iguales a las constantes (test que los cruza).

R29. (D8) La `regla` de `R-VENTA-COEFICIENTES` debe acabar con la única excepción: el contraste
de H12, que da un veredicto sobre el IVA sin enseñar, sumar ni comparar cifras de venta.

R31. (D8) SI Control de Costes entrega las obras de vivienda, ENTONCES entran en `obras` con H12
= 10, motivo y fecha, y R17 las publica en OBRA/MANUAL: MANUAL (humano). Ninguna obra se fija sin
esa lista; si no llega antes del cierre, queda pendiente en `progress/current.md`.

## Diccionario, documentación y verificación

R20. Contraste MANUAL de solo lectura tras el build frente a `progress/spec_F-150.md` §2: 18.997
partidas VENTA, pendiente 132,37 y con coeficientes 143,20 M EUR (± la variación diaria), fuente
`CERTIFICACION` en ~17.200 partidas y `VENTA` en las demás con coeficiente, 0 fallos de la guarda;
H10: 3 obras más en OBRA/SIGRID 5 (§6 de las mediciones).

R32. (D8) Antes de escribir la receta (T9), el contraste de R28 debe medirse en solo lectura en
las 21 obras: SI las 5 obras con `impiva / impadj` al 21 % no salen `GENERAL`, ENTONCES el
implementer PARA y el líder lo vuelve a proponer al humano (sin retocar umbrales).

R21. Duración medida del primer `build-tesoreria` (estimado +10-60 s en `devengo_pendiente`).

R22. CUANDO se pregunte al MCP, en una conversación nueva, por la caja de una obra con venta
con coeficientes, la respuesta debe seguir los siete pasos en orden, cobrar con
`importe_pendiente_con_coeficientes`, contrastar H12 si sale DEFECTO y declarar las 25
hipótesis: MANUAL (humano), anotado.

R23. Fichas al día (`paso_receta`, columnas nuevas, «25»), `version` del diccionario 63;
`CLAUDE.md` (mapa), `docs/ARCHITECTURE.md` y `azure-apps/datamart_seg_anual.md` al día.

R24. `bash harness/init.sh` en verde (pytest, cobertura y mutación de rigor `estandar`).
