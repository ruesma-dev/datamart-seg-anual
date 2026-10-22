# F-147 · Revisión de las 27 reglas duras, una a una

> **MATERIAL PARA DECIDIR CON EL HUMANO. Nada de esto está decidido.** Cada fila
> es una propuesta con su evidencia; la decisión, regla a regla, entra después en
> `requirements.md` (D1) y la ejecuta el implementer en `config/diccionario/`.
> Escrita por el spec-author el 2026-10-22 sobre la v58 publicada en Azure.

## Cómo se ha medido

- **Tamaño servido**: lo que `_notas_de_reglas` de `mcp-bbdd`
  (`infrastructure/diccionario/diccionario_postgres.py`) pinta por regla —cabecera,
  «Afecta a», «Regla» y «Por qué»—, recalculado desde los YAML con el cargador del
  repositorio. **Total: 50.831 caracteres** (regla 29.401 + motivo 14.653 + títulos
  y ámbitos). Coincide con `_meta.diccionario_reglas` de Azure (v58, 27 filas).
- **Vigencia**: contra el SQL del repositorio y contra Azure en SOLO LECTURA
  (`filas_solo_lectura`, transacción `READ ONLY`), el 2026-10-22. Las dos vistas
  «inconsultables» se midieron con `EXPLAIN` sin ejecutar, para no cargar el
  Postgres compartido.
- **Ahorro**: lo servido hoy menos lo que costaría su línea de índice
  (`[CÓDIGO] resumen`, ~35 + longitud del resumen). Es el ahorro **cuando
  `mcp-bbdd` sirva el resumen** (su F-029); lo que se ahorra sin esperarla está
  en la columna «Propuesta» marcado **[ya]**.

## Hallazgos que valen con independencia del enfoque

1. **La severidad no discrimina**: las 27 son `bloqueante` (el vocabulario es
   `bloqueante | aviso`, `SEVERIDADES` en `etl_sigrid/domain/diccionario.py`).
   Propuesta: dejar la severidad como está y añadir un eje propio de ENTREGA
   (`entrega: resumen | entera | fuera_mcp`), porque la pregunta no es «cuánto
   importa» sino «qué hay que tener delante siempre». Ver D2 en `requirements.md`.
2. **`R-COMPRAS-SIN-IVA` es FALSA hoy** en su primera frase («todos los importes
   del esquema `compras` son SIN IVA»): desde F-128, `compras.facturas`
   (`total_factura`, `cuota_iva`, `total_a_pagar`) y `compras.albaranes`
   (`total_documento`) publican la cabecera CON IVA (columnas comprobadas en Azure;
   sus fichas lo dicen en `compras.yaml`). Lo mismo arrastran la convención
   `importes_iva` de `00_global.yaml` y el punto 1 de la cabecera de `compras.yaml`.
3. **`R-OBRA-ACTIVA` es falsa a medias**: las dos columnas siguen mintiendo (584 de
   584 `stg.obras.activa`, 924 de 924 `maestro.obras.es_activa`, 0 con
   `fecha_baja`), pero «el catálogo de estados no está ingerido» ya no es cierto:
   `maestro.obras.estado` trae el nombre (tipo 42 de `raw.conest`): 178 EN CURSO,
   467 CERRADA, 228 EN ESTUDIO, 31 ADJUDICADA DEFINITIVAMENTE, 7 PARADA... y un
   solo `estado_id` (2, una ficha) sin nombre. La regla aparta a la IA de un
   criterio que hoy existe.
4. **Cifras envejecidas** que la regla presenta como actuales: el albarán absurdo
   «260,6 M€ saneado» hoy es **277,0 M€**; el intragrupo «23,8 M€» hoy es **29,5
   M€**. Un resumen sin cifras de recuento no envejece; el detalle, sí.
5. **El MCP sirve las 27 reglas a los tres perfiles**: `_notas_de_reglas` no
   mira `visible` (F-027 solo filtra enrutado y estado por esquema). El
   restringido recibe cinco reglas de esquemas que no puede leer (contabilidad,
   tesorería). Es de `mcp-bbdd` (su F-029 puede usar el `ambito`), no de aquí.
6. **`R-SIGRID-CON` y `R-PROVEEDOR-INTRAGRUPO` comparten `orden: 13`** (desempate
   por código). Inocuo, pero si se reordena conviene corregirlo.

## La tabla

Tamaño = servido hoy (regla / motivo). «≤250» es el objetivo orientativo del
resumen; los que lo pasan por poco van marcados.

| # | Código | Tamaño | ¿Vigente? Evidencia | Propuesta | Resumen propuesto | Ahorro |
|---|---|---|---|---|---|---|
| 1 | R-FRESCURA | 2.580 (1.201 / 1.105) | **Sí, pero duplicada.** Los ocho `build_*` siguen fuera de toda dependencia (`main.build_pipeline_steps`); `_meta.v_frescura` tiene los 15 pasos con fecha 2026-10-22. **El MCP ya sirve la fecha** en «ESTADO POR ESQUEMA» (`último build OK`, de `v_diccionario.ultimo_ok_finished_at`). El motivo (lista de pasos, historia de F-047) es nota de ETL, no de la IA. | Acortar. `motivo` fuera de lo servido (queda en YAML). Lo que la IA necesita es una orden: citar la fecha. | Cita la fecha del dato en toda respuesta de cierre, compras, maestro, retenciones, personal, contabilidad, tesorería o descompuestos: cada uno se construye aparte y puede ir una noche atrasado. Fecha: «ESTADO POR ESQUEMA» o `_meta.v_frescura`. | ~2.300 |
| 2 | R-IMPORTE-MES | 1.235 (505 / 312) | **Sí.** Pareja mes/origen en `mart`, `stg` y `cierre` (DDL). Protege del bug ×9 de la Tanda 1.4. | Mantener; resumen. Candidata a `entrega: entera` (el texto es corto y transversal). | Los importes van en pareja mes/acumulado (`importe_mes`/`importe_origen`; en `cierre`, `ejecutado_mes`/`ejecutado_origen`). Para series suma el del mes; el acumulado NUNCA se suma entre meses: de un periodo se toma su último mes. | ~970 |
| 3 | R-VENTA-COEFICIENTES | 1.685 (734 / 690) | **Sí** (F-118, 2026-09-29; `cierre` y `stg.presupuesto`). Error real: +1,7 M€ de beneficio donde había −0,8. | Mantener; resumen. El desglose del coeficiente por contrato (F-099) a la ficha. | Cierres, beneficio y análisis usan la venta SIN coeficientes (`importe`, `final_importe`). La CON coeficientes (`importe_oficial`, `*_con_coeficientes`) es lo facturado: nunca se suma ni compara con ejecutado, coste ni venta sin ellos. (~265) | ~1.385 |
| 4 | R-UNIVERSO-OBRA | 1.401 (809 / 433) | **Sí.** Hoy 584 obras en `stg.obras` y 924 fichas en `maestro.obras` (846 principales). Filtros en `sql/stg/03_obras.sql`; el maestro no filtra. | Mantener; resumen sin recuentos. Las cuatro obras de ficha distinta (0581, 0606, 0671, 0720) a la ficha de `stg.obras`. | Dos universos: `stg.obras` (seguimiento, sin códigos administrativos) y `maestro.obras` (todas las fichas, una por empresa y código). Al contar obras di cuál usas; `compras` y `retenciones` no filtran por `stg.obras`. | ~1.145 |
| 5 | R-CODIGO-POR-EMPRESA | 3.132 (1.194 / 1.349) | **Sí** (F-102, F-107, F-056). Ámbito de 19 objetos. El motivo es una serie de mediciones históricas. | Mantener; resumen. Motivo recortado a una frase (el resto, historia en `progress/`). **Opción**: fundir con 6 en una regla «empresa». | Un código de obra, recurso o cuenta solo es único dentro de su empresa: cruza, filtra y agrega con `empresa_id` o por `clave_obra`/`clave_recurso`/`clave_cuenta` (`1-0581`). Los hechos llevan el `obra_id` de la ficha de SU empresa. | ~2.860 |
| 6 | R-EMPRESA-POR-DEFECTO | **5.964** (4.886 / 791) | **Sí** (orden del humano 2026-10-18). Pero el 80 % de la regla es un **inventario** de qué objetos tienen `empresa_id`, cuáles solo `obra_id` y cuáles ninguna: eso es catálogo, que `describir_tabla` ya enseña columna a columna, y envejece con cada objeto nuevo. | Acortar a la orden. El inventario sale a las fichas: cada objeto SIN empresa ni obra dice en su ficha «mezcla las 38 empresas» y, si lo tiene, su camino comprobado (`compras.vencimientos` → `tesoreria.efectos`; retenciones por `retenciones.movimientos`). `maestro.centros_coste.empresa` (no `empresa_id`), en su ficha. | Sin empresa en la pregunta, filtra `empresa_id = 1` (Construcciones Ruesma) y dilo. Sin columna de empresa, llega por `obra_id` → `maestro.obras`; si tampoco hay obra, avisa de que la cifra mezcla todas. Nunca sumes empresas sin decirlo. | ~5.690 |
| 7 | R-SALDO-CONTABLE | 1.621 (814 / 486) | **Sí** (F-056; `clase_asiento` resuelta en el SQL). Error real medido: 7,7 M frente a 1,19 M. | Mantener; resumen. | Saldo = suma de `importe_saldo`, o `saldo_acumulado` del último apunte o mes. Nunca `SUM(importe)` sin filtrar `clase_asiento`: CIERRE y APERTURA duplican. El resultado del ejercicio, sin REGULARIZACION. | ~1.380 |
| 8 | R-CONTABILIDAD-RESTRINGIDA | 3.450 (2.435 / 820) | **Sí.** En Azure: `mcp_sigrid_dm_ro` sin USAGE en `contabilidad_restringida`, `mcp_sigrid_dm_total` con él. | **Fundir con 9, 10 y 11** en una regla de perfiles. Lo propio de la contabilidad (`incompleto`, `num_apuntes_restringidos`, `apuntes_restringidos_mes`, prefijos de cuentas de personal, excepción de `retenciones`) a las fichas de `contabilidad.saldos_cuenta_mes`, `contabilidad.apuntes_restringidos_mes` y `contabilidad.plan_cuentas`. | (fundida en 11) | en 11 |
| 9 | R-TESORERIA-RESTRINGIDA | 1.528 (913 / 435) | **Sí.** `mcp_sigrid_dm_ro` sin USAGE en `tesoreria_restringida`. | Fundir en 11. `tesoreria.efectos_restringidos_mes` a su ficha. | (fundida en 11) | en 11 |
| 10 | R-COMPRAS-RESTRINGIDA | 1.848 (1.239 / 403) | **Sí.** `mcp_sigrid_dm_ro` sin USAGE en `compras_restringida`. | Fundir en 11. La cuenta bancaria del proveedor (sin versión general, no reconstruirla desde `v_facturas_pago`) a la ficha de `compras_restringida.documento_cuenta_bancaria`. | (fundida en 11) | en 11 |
| 11 | R-PERFIL-RESTRINGIDO → **R-PERFILES** | 3.308 (1.717 / 1.223); **los cuatro: 10.134** | **Sí.** En Azure: `mcp_sigrid_dm_restringido` sin USAGE en `contabilidad`, `tesoreria`, `personal` ni ningún `*_restringida`; con USAGE en `retenciones`. Las cuatro repiten lo mismo: usa la general, la restringida es del total, «permission denied» no se rodea, nunca se suman. | Una sola regla. Qué ve cada perfil lo dice ya el propio MCP (`estado_servidor`) y las fichas de lo que el restringido no ve empiezan por el aviso. Código nuevo o se conserva uno de los cuatro: **D3**. | Usa siempre el esquema general; `*_restringida` es solo del perfil total y solo si piden personal (nóminas, embargos, cuentas, alarmas de recursos). General y restringida nunca se suman. «permission denied» no se rodea: di que el perfil no lo incluye. (~255) | ~9.840 |
| 12 | R-TESORERIA-ESTADO | 1.749 (973 / 569) | **Sí** (F-037, 2026-10-13). Error medido: 385 M€ de cobro previsto con las bajas frente a 47,5. | Mantener; resumen. | Filtra siempre `estado_tesoreria`: BAJA nunca se suma; REALIZADO es pagado o cobrado y PREVISTO pendiente. `fecha_real` vacía NO es pendiente. Caja = PREVISTO y NOT `previsto_antiguo`. En `compras.vencimientos`: `estado_pago` y `efecto_anulado`. | ~1.470 |
| 13 | R-DESCOMPUESTO-ORIGEN | 2.524 (1.446 / 791) | **Sí** (F-097, F-123). | Mantener; resumen. Lo de «Estudios es el master 0» (F-123) a las fichas de `v_pbi_master_estudio` / `v_pbi_estudio`. | Filtra o agrupa siempre por `origen`: ESTUDIO, MASTER_ESTUDIO, PLANIF_JO y los MASTER_* no se suman. En el master filtra una versión (`fase_num`) o `es_vigente`, o cada línea cuenta una vez por versión. Orígenes, lado a lado por partida. | ~2.250 |
| 14 | R-PROVEEDOR-INTRAGRUPO | 1.385 (829 / 326) | **Sí, con cifra vieja.** Hoy (FACTURA+ABONO) el nº 1 es A81873903 con **29,5 M€** (la regla dice 23,8), luego UTE VALDEBEBAS VI 9,7. No hay marca de grupo (`maestro.proveedores` no tiene columna; ningún otro YAML habla de intragrupo). | Mantener; resumen sin cifras. Las cifras, al motivo. | En un ranking de proveedores el nº 1 es la propia Ruesma (CIF A81873903) y detrás hay UTE del grupo. No hay marca de intragrupo: dalo tal cual diciendo cuáles son, o exclúyelos por CIF y dilo. | ~1.155 |
| 15 | R-SIGRID-CON | 4.469 (3.079 / 1.267) | **Verdad, pero no es para la IA del MCP.** Su ámbito es solo `raw`, que **no está** en `seguridad.esquemas_permitidos` de `mcp-bbdd/config/config.yaml` y sobre el que **ningún login del MCP tiene USAGE** (comprobado en Azure: `mcp_sigrid_dm_ro`, `_total`, `_restringido`, `sigrid_dm_autorizado_ro`, `sigrid_dm_perfil_restringido_ro`: false). Es la guía de quien escribe el SQL del ETL. | **Fuera de lo servido al MCP** (`entrega: fuera_mcp`), sigue en el YAML: la exigen `CODIGOS_REGLAS_OBLIGATORIAS` y tres tests (`test_f006_fuente_que_gobierna`, `test_f006_regla_de_oro`, `test_f006_reglas`). Arrastra la convención `identidad_sigrid` (servida, ~600, remite a esta regla) y el trozo de `raw` de `fechas`. **[ya]**: no depende de `mcp-bbdd` si la fila no se publica (D4). | (ninguno: no se sirve) | ~4.470 (+~600) |
| 16 | R-ALBARAN-ABSURDO | 1.395 (778 / 393) | **Sí.** Hoy siguen las dos líneas 588705 y 588733 de AC21/03345 (34.361.999.999.898,80 € cada una) en `compras.v_pbi_albaranes_sin_facturar`: total 68.724.277 M€, saneado **277,0 M€**. Cuatro filas ≥1e8 en `compras.fact_compras_linea` (ALBARAN) y cuatro en `compras.albaran_lineas` (con su espejo). | Mantener; resumen. **Alternativa a decidir (D5)**: que el ETL marque la línea (`es_anomalia_origen`) y la regla se reduzca a la ficha; el motivo dice que «no se corrige aguas abajo» a propósito. | Excluye las 2 líneas absurdas del albarán AC21/03345 (34 billones € cada una): toda suma de compras lleva `abs(importe…) < 1e8` y lo dice. Un total de compras por encima de 1.000 M€ es esta anomalía, no un hallazgo. | ~1.135 |
| 17 | R-COSTE-CONSULTA | 2.216 (1.312 / 686) | **(1) Sí**: `EXPLAIN ... LIMIT 5` da coste de arranque 62,4 M en `mart.v_fact_periodificado` y 4,9 M en `cierre.v_pbi_cierre_indirectos_detalle` (materializan su CTE entero antes de la primera fila). **Pero ya lo dicen sus fichas**: las dos son `consumo_recomendado = false` con `motivo_no_consumo` («NO SE PUEDE CONSULTAR HOY»; «HOY NO PERIODIFICA NADA»: `aux.periodificacion_partida` vacía). **(2)** es historia (F-078: ya son tablas). **(3)/(4)** tiempos del 2026-08-25. Las instrucciones del MCP ya dicen «agrega en SQL… corta por tiempo». | **Eliminar** y repartir: (1) ya está en las fichas; (3) a las fichas de `stg.plan_mensual` y `compras.fact_compras_linea`; (2) y (4) fuera. Si el humano prefiere conservarla, el resumen de la derecha. | `mart.v_fact_periodificado` y `cierre.v_pbi_cierre_indirectos_detalle` no se pueden consultar (más de 60 s): dilo. `stg.plan_mensual` y `compras.fact_compras_linea` son caras: una sola consulta, filtrada y agregada. | ~1.970–2.220 |
| 18 | R-OBRA-ACTIVA | 1.636 (984 / 464) | **A medias** (hallazgo 3). Las columnas mienten igual; el «no se puede responder» ya no es cierto del todo: hay `maestro.obras.estado` con nombre. Qué es «activa» para Negocio (¿EN CURSO? ¿+ ADJUDICADA? ¿PARADA?) no está escrito. | **Reescribir** (D6: el criterio de «activa» lo da el humano o Negocio; encaja en el glosario F-054). Mejor aún, a medio plazo: que `stg.obras.activa` y `maestro.obras.es_activa` dejen de existir o digan algo (feature aparte). | `stg.obras.activa` y `maestro.obras.es_activa` valen TRUE siempre: no sirven para «obras activas». Usa `maestro.obras.estado` (p. ej. 'EN CURSO') y di el criterio y a cuántas obras alcanza. | ~1.410 |
| 19 | R-VERSION-MASTER | 857 (390 / 208) | **Sí** (`tipo_master` en `sql/mart/01_ddl.sql`, elección en `02_build_fact.sql`). | Mantener; resumen. **Opción**: fundir con 20 (las dos hablan de `fas`/versión en `stg`). | En `stg.plan_mensual` conviven todas las versiones master: filtrar solo por obra y ámbito multiplica. El planificado vigente está en `mart.fact_seguimiento_mensual`; 'Cierre mensual' nunca es master vigente. | ~610 |
| 20 | R-FAS-AMBIGUO | 715 (349 / 175) | **Sí**, salvo lo de `raw` (`raw.obrfas`, `raw.obrfasamb`, `fasnum`): la IA no lo ve. | Mantener; resumen; quitar `raw` del texto servido (el ámbito puede quedarse). | `fas` es el MES en los ámbitos reales (3 coste, 7 venta; 0 = previsto vivo) y la VERSIÓN en los master (8, 11). Se llama `fase_num` en `stg.presupuesto` y `version` en `stg.plan_mensual`. No cruces las dos lecturas. | ~465 |
| 21 | R-CLAVE-SUSTITUTA | 965 (462 / 240) | **Sí** (BIGSERIAL en `mart/01_ddl.sql`, `cierre/01_ddl_fact.sql`, `stg/01_ddl.sql`). La excepción de `aux.periodificacion_partida.regla_id` no sirve a la IA (`aux`: 0 objetos recomendados, tabla vacía). | Resumen sin la excepción. **Opción**: llevarla a la columna de cada ficha y retirarla (riesgo bajo para la IA). | `fact_id`, `fact_cat_id`, `plan_id` y `cierre_id` se renumeran en cada build: no los enseñes ni los guardes como identificador; usa la clave de negocio. | ~775 |
| 22 | R-ABONO-NEGATIVO | 690 (268 / 145) | **Sí, con matiz**: en `compras.fact_compras_linea` hay solo 19 líneas ABONO (15 negativas, **4 positivas**); FACTURA trae 64.777 líneas negativas. La orden («no restes otra vez») sigue valiendo. | **Fundir con 23 y 27** en una regla de `compras.fact_compras_linea` (las tres tienen ese ámbito). | (fundida en 27) | en 27 |
| 23 | R-LINEA-ID-NO-UNICA | 602 (328 / 127) | **Sí.** Hoy: 0 repetidos por (`tipo_doc`, `linea_id`) y 1.180.614 filas de más por `linea_id` solo. | Fundir en 27. | (fundida en 27) | en 27 |
| 24 | R-PARTIDA-CODIGO-NO-UNICO | 1.867 (833 / 692) | **Sí.** Hoy 5.204 pares (`obra_id`, `codigo_partida`) repetidos en `stg.partidas` (5.202 el 2026-09-25). | Mantener; resumen. | Une y cuenta partidas por `partida_id`, nunca por obra + código: el mismo código se repite en la obra (bloques, fases, contratos) y multiplica importes. Agrupar por código vale si lo dices; al usuario, la ruta de capítulos. | ~1.605 |
| 25 | R-RETENCION-NO-JOIN-LINEAS | 729 (296 / 183) | **Sí** (error real de 38,9 M€ en una obra). | Mantener; resumen. | `retenciones.movimientos` lleva un registro por efecto con el total retenido: nunca lo unas a líneas de factura (multiplica por nº de líneas). Agrega antes por documento y une por documento. | ~500 |
| 26 | R-COMPRAS-SIN-IVA | 643 (286 / 190) | **No, tal como está** (hallazgo 2). | **Corregir** (y con ella `convenciones.importes_iva` y la cabecera de `compras.yaml`), y **fundir** la convención en la regla para no tener dos versiones. Ver D7: corregirlo es urgente aunque F-147 se retrase. | Los importes de línea de `compras` son SIN IVA; llevan IVA los totales de cabecera (`total_factura`, `total_documento`, `total_a_pagar`) y `maestro.proveedores_obra.importe_contratado`. No los compares: la diferencia es el impuesto. | ~370 |
| 27 | R-COMPRAS-TIPO-DOC → **R-COMPRAS-LINEA** | 637 (341 / 150); **las tres: 1.929** | **Sí.** Tipos presentes hoy: ABONO, ALBARAN, CONTRATO, FACTURA, NOTA, OTRO, PROFORMA. | Una regla con 22 y 23 (D3: código nuevo o conservar éste). | `compras.fact_compras_linea` mezcla CONTRATO, ALBARAN, PROFORMA, NOTA, FACTURA, ABONO y OTRO: filtra siempre `tipo_doc` (son el mismo coste en tres momentos). Su clave es (`tipo_doc`, `linea_id`). Los ABONO ya restan: no los restes otra vez. | ~1.650 |

## Lo que sale si se acepta todo

| | Hoy | Propuesta |
|---|---|---|
| Reglas | 27 | 21 en el YAML y 20 servidas (cuatro de perfiles → 1; tres de `fact_compras_linea` → 1; `R-COSTE-CONSULTA` fuera; `R-SIGRID-CON` solo en el YAML) |
| Servido por las reglas en `contexto_bbdd` | 50.831 | ~5.000–5.400 (índice con resumen) |
| Ahorro | — | **~45.400 (≈ 89 %)**, del que **~5.000 no espera a `mcp-bbdd`** (`R-SIGRID-CON` + `identidad_sigrid` sin publicar) y el resto llega con su F-029 |

Lo que **no** cubre esta tabla y también pesa en `contexto_bbdd`: el enrutado
(~20.400; con 2 preguntas por objeto, 205 de 283; con 1, 114) y el bloque
`esquemas` de `_meta.diccionario_contexto` (10.549 de los ~13.700 de bloques).
Ver D8 y D9 en `requirements.md`.

## Riesgos de la divulgación progresiva (para pesar antes de decidir)

- **El detalle no llega si la IA no pide la ficha.** Hoy `describir_tabla` solo
  da los códigos de los avisos «(su texto completo está en contexto_bbdd)». Por eso
  el resumen tiene que bastar SOLO, y por eso F-029 de `mcp-bbdd` tiene que llevar
  el texto entero a `describir_tabla`: sin las dos cosas, se pierde protección.
- **El detalle se paga en cada `describir_tabla`**: `compras.fact_compras_linea`
  tiene 9 avisos; con el texto de hoy serían ~15.000 por ficha. Acortar `regla` y
  sacar la historia del `motivo` sigue valiendo la pena aunque haya resumen.
- **Un resumen que no basta es peor que una regla larga**: da la sensación de
  estar protegido. Por eso cada resumen propuesto es una ORDEN con los nombres de
  columna exactos, no un titular; revisarlo es la parte que el humano no puede
  delegar.
