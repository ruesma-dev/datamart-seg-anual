<!-- specs/F-140-proyeccion-caja-ingredientes/design.md -->
# F-140 · Diseño (de devengo a caja: ingredientes e hipótesis)

Mediciones: `progress/spec_F-140.md`. Requisitos: `requirements.md`. Decisiones: §9.

## 1. Encaje y límite

Se amplía el esquema MÓDULO `tesoreria` de F-037 (D1): mismo paso `build_tesoreria`, mismo patrón
de tablas que no se dropean (`IF NOT EXISTS` + `TRUNCATE` + `INSERT`). Lo nuevo lee `raw`,
`maestro.centros_coste`, `tesoreria.efectos` (la general), `config/hipotesis_caja.yaml` y, por
primera vez, `mart` y `stg` de la MISMA noche: `build_stg` y `build_mart` van delante en `run-all`,
sin `depends_on` (si fallan, se lee lo de ayer: patrón de `build_retenciones`, F-110).

```
config/hipotesis_caja.yaml ───► hipotesis_caja (catálogo) + hipotesis_caja_manual ─┐
condiciones_contrato_cliente (SIGRID) ───────────────────────────────────────────┴► hipotesis_caja_obra
stg.plan_mensual (V) + mart REAL ─► devengo_pendiente_partida ─► devengo_pendiente_obra_mes
                                                              └► devengo_corte_obra ◄─ tesoreria.efectos
raw.auxpag ∪ auxcob ─► plazos_forma_pago · raw.ctr/ctrrec/prv ─► condiciones_contrato_compra
```

**La conversión a caja la hace la IA en vivo**, con los valores de cada hipótesis que le dé el
usuario o, si no, los de la obra o los por defecto, y declarándolos todos (`R-CAJA-HIPOTESIS`).
El ETL no aplica un solo plazo, retención o IVA (R6, R16). **Límite**: todo es ETL de este
repositorio; `auxcob`/`auxefc` se leen por `sigrid-api`; el MCP ya ve `tesoreria` (F-037). Un
editor de hipótesis por obra con interfaz (D14-C) sería de `portal`, no de aquí.

## 2. Ficheros

**Crear**: `etl_sigrid/domain/proyeccion_caja.py` (§3); `config/hipotesis_caja.yaml` (§6);
`etl_sigrid/infrastructure/config/hipotesis_caja_yaml.py` (lee el YAML y lo entrega al dominio);
`sql/tesoreria/04_plazos_forma_pago.sql`, `05_condiciones_contrato_compra.sql`,
`06_condiciones_contrato_cliente.sql`, `07_devengo_pendiente.sql`, `08_hipotesis_caja_obra.sql`;
`tests/test_f140_{dominio,sql,paso,hipotesis,diccionario}.py`.

**Modificar**
- `sql/tesoreria/00_setup.sql`: funciones de la fórmula (§4.1), las tablas nuevas `IF NOT EXISTS`
  con PK e índices y, si D10-A, `ADD COLUMN IF NOT EXISTS obra_via` en las dos `efectos`.
- Si D10-A: `domain/tesoreria.py` gana `VIA_CENTRO`/`VIA_CONTRATO`/`VIA_FACTURA_CABECERA`/
  `VIA_FACTURA_LINEAS` y `obra_del_efecto(obra_centro, tiene_centro, obras_contrato, obra_cabecera,
  obras_lineas)` (un conjunto con más de una obra no decide y pasa al escalón siguiente);
  `01_efectos_completo.sql` calcula, ANTES del `UNION ALL` y solo para documentos de pagos sin
  `cenide`, por `dcf.ide`: obras de sus contratos (`dcf.ctride` y `dcfpro.docoriide` cuando es un
  `ctr`), `NULLIF(dcf.obride, 0)` y obras de `dcfpro.obride`; un `CASE` en el orden del dominio da
  la obra y `obra_via` (COBRO: solo `CENTRO`, sin ventas); `02` copia `obra_via` al final.
  Sustituye `test_f037_r8_la_obra_sale_solo_del_centro`, con su porqué en el commit.
- `application/steps/build_tesoreria_step.py`: sub-pasos nuevos; el de hipótesis carga el YAML,
  lo valida con el dominio e inserta con parámetros (patrón de `publicar_diccionario`).
- `etl_sigrid/domain/reanudacion.py`: `"build_tesoreria": frozenset({"build_stg", "build_mart"})`.
- `config/tables_sigrid.yaml`: `auxcob` y `auxefc` (D7), exclusión estándar de textos.
- `config/diccionario/`: `tesoreria.yaml` (fichas nuevas; `efectos` deja de decir «la fase 2 no
  existe»), `raw.yaml` (`auxcob`, `auxefc`), `compras.yaml` (remisiones), `00_global.yaml`
  (`R-CAJA-HIPOTESIS`, `para_que_sirve` de `tesoreria`, `R-TESORERIA-ESTADO` remite a la regla
  nueva, `version` +1 sobre el real: hoy 60).
- Tests que fijan listas: `test_f037_paso.py`, `test_f037_sql.py` (si D10-A),
  `test_f148_reanudacion.py`, `test_f066_ingesta_raw.py` y `test_f081_yaml_ingesta.py` (78),
  `test_f147_presupuesto_contexto.py` (solo si se pasa, con su motivo).
- `docs/ARCHITECTURE.md` (capas, 78 tablas, nocturna), `CLAUDE.md` (mapa),
  `azure-apps/datamart_seg_anual.md`; commit local en `azure-apps`, sin push.

**No se tocan**: `sql/mart/*`, `sql/stg/*`, `sql/retenciones/*` (`retenciones.fin_obra` se cita
como ingrediente de H07/H11), `sql/compras/*` (los albaranes pendientes se citan, no se leen:
`compras` se construye después y se dropea), `03_efectos_restringidos_mes.sql`, permisos
(`grants.py`, `settings.py`, `02_roles.sql`: el esquema ya se concede y veta entero), `main.py`.

## 3. Dominio (`domain/proyeccion_caja.py`, sin infraestructura)

- Fórmula: `REGEX_TOKEN_DIAS = r"^[0-9]+$"`, `REGEX_TOKEN_RETENCION = r"^[0-9]+R$"`;
  `PlazoFormula(dias_vencimientos, dias_retencion, reconocida)`; `leer_formula_plazo(f)` (R7, R8):
  `"30 60 90"` → `((30,60,90), None, True)`, `"90  450R"` → `((90,), 450, True)`, `"450R"` →
  `((), 450, True)`, `"30 x"`/`"30R 450R"`/vacío → `((), None, False)`.
- Partida: `pendiente_partida(plan_desde_version, ejecutado_intervalo) -> (pendiente,
  sobre_ejecutado)` (R12); `repartir_pendiente(pendiente, perfil: [(mes, plan)], primer_mes) ->
  [(mes, importe, es_retraso)]` (R14): proporcional al plan de cada mes, redondeo a céntimos con
  el resto en el último mes del perfil; perfil vacío o a cero → todo a `primer_mes`, `es_retraso`.
- Hipótesis: `UNIDADES = ("DIAS", "MESES", "PORCENTAJE", "BOOLEANO", "OPCION", "MAPA_DIAS")`,
  `NIVELES = ("DEFECTO", "OBRA", "USUARIO")`, `FUENTES = ("DEFECTO", "SIGRID", "MANUAL")`;
  `Hipotesis` (dataclass congelada con los campos de R1 más `opciones`);
  `validar_catalogo(filas) -> list[str]` y `validar_valores_obra(filas, codigos) -> list[str]` (R2,
  R3: errores, vacío = válido); `resolver_hipotesis(defecto, sigrid, manual) -> (valor, nivel,
  fuente)` (R5: MANUAL > SIGRID > DEFECTO).
- `PATRON_COLUMNA_DE_CAJA = r"caja|flujo|previst|fecha_pago|fecha_cobro|con_iva"` (R16).

El SQL no llama a Python: lleva los mismos literales y los tests los comparan (patrón de F-135).

## 4. SQL de `tesoreria`

**4.1 `00_setup.sql`** (al final): `fn_plazo_reconocido`, `fn_plazo_dias` (`INT[]`) y
`fn_plazo_dias_retencion` (`IMMUTABLE`, `regexp_split_to_array(btrim(f), '\s+')` y los regex de
§3); tablas `hipotesis_caja` (PK `codigo`), `hipotesis_caja_manual` (PK `clave_obra, codigo`),
`hipotesis_caja_obra` (PK `obra_id, codigo`), `condiciones_contrato_compra` (PK `contrato_id`),
`condiciones_contrato_cliente` (PK `contrato_cliente_id`), `devengo_pendiente_partida` (PK
`obra_id, partida_id, concepto`), `devengo_pendiente_obra_mes` (PK `obra_id, anio_mes, concepto,
categoria`) y `devengo_corte_obra` (PK `obra_id, concepto`), con índices por obra.

**4.2 `04`-`06`, las condiciones** (vista y dos tablas; columnas de R9-R11): `04` `UNION ALL` PAGO/COBRO sin filtro; `05` desde `raw.ctr`
con `raw.conest` (`tip = 44`), `raw.auxpag`, `raw.prv` (`pagdia`, `pagmes`), lateral de
`raw.ctrrec` con `reccla IN (4, 5)` (`ORDER BY pos, ide LIMIT 1`), `importe_base = totbas`,
`importe_iva = totiva`, sin terceros `tip = 43`; `06` desde `raw.obrctr` con `raw.auxcob`, `raw.rec`
(retención) y `plaret`/`plagar` (0 → NULL)/`fecinigar` tal cual.

**4.3 `07_devengo_pendiente.sql`**, una transacción, en este orden:
1. `ult` (obra, concepto) → `MAX(anio_mes)` real de `mart.fact_seguimiento_mensual`. `v`: la
   versión del último mes PLANIFICADO posterior a `ult`, y `mes_version` =
   `date_trunc('month', version_fec_efectiva)` de `mart.master_versiones_tipadas`.
2. Plan por partida: `stg.plan_mensual WHERE obra_id = v.obra_id AND ambito_id = (8|11) AND
   version = v.version` (único acceso a `stg`, R13): `plan_desde_version` (mes ≥ `mes_version`),
   `plan_intervalo` (entre `mes_version` y `ult`), `plan_restante` (mes > `ult`).
3. Ejecutado por partida: `SUM(importe_mes)` de las filas `tipo_dato = 'REAL'` del concepto con
   mes en el intervalo. Las partidas con ejecutado y sin plan de V NO entran en la partida (no
   tienen pendiente) y se suman en `ejecutado_sin_plan` del corte.
4. `devengo_pendiente_partida`: `pendiente = GREATEST(0, plan_desde_version −
   ejecutado_intervalo)`, `sobre_ejecutado = GREATEST(0, ejecutado_intervalo −
   plan_desde_version)`, la categoría de la partida en `mart` (F-113), V y meses.
5. `devengo_pendiente_obra_mes`: reparto de R14 en SQL (`pendiente × plan_mes /
   plan_restante`, `ROUND(…, 2)`, el resto al último mes por `ROW_NUMBER`), agregado por (obra,
   mes, concepto, categoría) con `importe_plan_restante`, `importe_pendiente`,
   `importe_retraso_sin_perfil`, `num_partidas`, V, `mes_ultimo_cierre`, `mes_pasado_sin_cierre`
   (mes < mes del build), empresa y `clave_obra` (`raw.con` de la obra). Guarda `DO`: la suma de
   `importe_pendiente` por (obra, concepto) iguala la de la partida al céntimo; si no, `RAISE`.
6. `devengo_corte_obra`: sumas de la partida (con `adelantado = Σ máx(0, ejecutado − plan del
   intervalo)` y `retrasado` el simétrico), `num_versiones_pendientes`, `real_origen_corte`,
   `plan_total` de V y, de `tesoreria.efectos` del sentido del concepto (COSTE → PAGO, VENTA →
   COBRO), `cartera_viva` (PREVISTO y no `previsto_antiguo`) y `cartera_emitida_tras_cierre`
   (`fecha_emision` posterior al fin del mes de `ult`). Todo con IVA y así lo dice la ficha.
Medido: la lectura de los pasos 1-4 ronda los 90 s; 39.366 partidas, ~740 filas mensuales.

**4.4 `08_hipotesis_caja_obra.sql`** (tras la carga del YAML, que hace el paso en Python): guarda
`DO` que falla si una `clave_obra` de `hipotesis_caja_manual` no existe (R3); después
`hipotesis_caja_obra` para (obras de `devengo_corte_obra` ∪ obras con valor manual) × códigos con
`admite_obra`: `MANUAL` si hay fila manual; si no, `SIGRID` para H09/H10/H11 cuando los
contratos con el cliente de la obra dan UN solo valor (D18); si no, el `DEFECTO`. El `CASE`
lleva el orden de `resolver_hipotesis` (test).

## 5. Paso, nocturna e ingesta

Sub-pasos detrás de los cuatro de F-037: `plazos_forma_pago` (04, vista), `condiciones_compra`
(05), `condiciones_cliente` (06), `devengo_pendiente` (07), `hipotesis_carga` (Python: lee y
valida el YAML; `TRUNCATE` + `INSERT` de `hipotesis_caja` y `hipotesis_caja_manual` en una
transacción; si hay errores, FAILED con la lista y no escribe) y `hipotesis_obra` (08). Cada
fichero es su transacción: si 07 falla, quedan las de ayer y la cartera ya está hecha.
`auxcob` (52 filas) y `auxefc` (8) entran en `tables_sigrid.yaml` como `auxpag`.

## 6. El catálogo de hipótesis (`config/hipotesis_caja.yaml`) y sus valores por defecto

Defectos PROPUESTOS, con `validado: false` hasta que Negocio los apruebe (D17); «medido» remite a
`progress/spec_F-140.md`. Todos `admite_obra: true` salvo H17.

| Código | Hipótesis | Unidad | Defecto propuesto y su fuente | Ingrediente |
|---|---|---|---|---|
| H01 | Plazo de pago con contrato | OPCION | `CONTRATO`: el de su forma de pago | `condiciones_contrato_compra` |
| H02 | Plazo de pago sin contrato, por categoría | MAPA_DIAS | 120 en CD/CI/CP/OTRO (forma más frecuente, medido) | `plazos_forma_pago` |
| H03 | Fecha de la factura del proveedor | MESES | 0: a fin del mes de devengo | `devengo_pendiente_obra_mes` |
| H04 | Días fijos de pago y meses sin pago | BOOLEANO | sí, si el proveedor los tiene | `condiciones_contrato_compra` |
| H05 | Retraso real sobre el plazo nominal | DIAS | 0 (medido: +7 a +22) | `plazos_forma_pago` (ficha) |
| H06 | Retención de garantía al proveedor | PORCENTAJE | la del contrato; sin contrato, 0 | `condiciones_contrato_compra` |
| H07 | Devolución de la retención al proveedor | OPCION | `FIN_OBRA` (`retenciones.fin_obra`, decisión 2026-09-22); alt. `SIGRID` (`NR` desde factura) | `retenciones.fin_obra`, `plazos_forma_pago` |
| H08 | Desfase producción → certificación | MESES | 1: se certifica el mes siguiente | `devengo_pendiente_obra_mes` |
| H09 | Plazo de cobro del cliente | DIAS | el del contrato con el cliente (OBRA·SIGRID); si no, 60 (`CF60`, medido) | `condiciones_contrato_cliente` |
| H10 | Retención de garantía del cliente | PORCENTAJE | la del contrato (OBRA·SIGRID); si no, 0 | `condiciones_contrato_cliente` |
| H11 | Devolución de la retención del cliente | MESES | tras fin de obra: `plaret` → `plagar` → 12 | `condiciones_contrato_cliente`, `retenciones.fin_obra` |
| H12 | IVA de venta | PORCENTAJE | 21 (vivienda 10: se personaliza por obra) | — |
| H13 | IVA efectivo de compra | PORCENTAJE | 5,5 (medido: cuota/base 12 meses; la marca de ISP no sirve) | `compras.facturas` |
| H14 | Liquidación del IVA | OPCION | `TRIMESTRAL` (día 20 del mes siguiente); alt. `MENSUAL`, `NO_MODELAR` | — |
| H15 | Reparto de vencimientos múltiples | OPCION | `PARTES_IGUALES` (`30 60 90`) | `plazos_forma_pago` |
| H16 | Cartera PREVISTA ya vencida | OPCION | `PRIMER_MES`; alt. `EXCLUIR` | `tesoreria.efectos` |
| H17 | Previsto antiguo (> 2 años) | BOOLEANO | excluido (F-037, D11) | `tesoreria.efectos` |
| H18 | Descuento de lo ejecutado | OPCION | `POR_PARTIDA` (`importe_pendiente`); alt. `SOLO_MESES_CERRADOS` | `devengo_pendiente_obra_mes` |
| H19 | Retraso sin perfil | OPCION | `PRIMER_MES`; alt. `REPARTIR`, `EXCLUIR` | `importe_retraso_sin_perfil` |
| H20 | Albaranes pendientes de facturar | OPCION | `MES_SIGUIENTE` al cierre; alt. `EXCLUIR` | `compras.fact_compras_linea` |
| H21 | Lo emitido tras el último cierre | OPCION | `DESCONTAR` del primer mes pendiente | `devengo_corte_obra` |
| H22 | Morosidad | PORCENTAJE | 0 | — |
| H23 | Día del devengo dentro del mes | OPCION | `FIN_DE_MES`; alt. `MITAD_DE_MES` | — |

Fuera, y lo dice la ficha: anticipos y acopios, avales, intereses, y el reparto del devengo de una
categoría entre sus contratos (no está en Sigrid; la IA lo pondera con `importe_base`).

## 7. La regla dura y el diccionario

`R-CAJA-HIPOTESIS` (bloqueante, `entrega: resumen`). `resumen` (≤ 250): «No hay caja proyectada.
Al pasar devengo a caja declara TODAS las hipótesis de `tesoreria.hipotesis_caja_obra`, cada una
con valor y nivel: DEFECTO, OBRA o USUARIO (la del usuario manda). Sin IVA el devengo; no repitas
la cartera.» `regla`: el orden USUARIO > OBRA > DEFECTO; las no validadas se avisan; las que no
aplican se dicen; el devengo pendiente ya descuenta lo ejecutado desde V (H18); la frontera con la
cartera (H16, H20, H21: `cartera_viva`, albaranes, emitido tras el cierre); IVA aparte (H12-H14).
`ambito`: los objetos nuevos, `tesoreria.efectos` y `mart.fact_seguimiento_mensual`. Las fichas
llevan cobertura medida, `clave_negocio` y dos `ejemplos_preguntas` que enrutan («qué caja
necesitará la obra X», «con qué plazo pagamos al proveedor Y»). Presupuesto de F-147: se mide.

## 8. Despliegue (MANUAL, tras el review) y riesgos

Imagen con tag fechado y job apuntado a ella; desde el puesto `ingest --table auxcob --full`,
`ingest --table auxefc --full` y `build-tesoreria` (duración, R27); R19, R28; `publicar-diccionario`
con la imagen ya en el job; `check-diccionario`, `check-declarados`, `check-unicidad`; reiniciar
el MCP y R25. **Riesgos**: leer `mart` sin `depends_on` (si falla, devengo de ayer, `R-FRESCURA`);
una versión nueva entre el cierre y hoy (`num_versiones_pendientes` lo delata; hoy 1 en todas);
un plan viejo que rige (2 obras `Planif Inicial`, una de 2020: V va en cada fila); un defecto sin
validar tomado por dato (`validado` y la regla); la obra de las `AGR` y los cobros sin venta
(F-040) siguen sin obra: Sigrid no guarda el vínculo.

## 9. Decisiones (CERRADAS por el humano el 2026-10-25: todas A, D10 incluida)

- **D1 · Dónde** (sin cambio). (A) En `tesoreria`. (B) Esquema nuevo. (C) Repartido.
- **D2 · Qué versión** (reformulada). (A) V = la que `mart` elige para el último mes pendiente,
  con su `mes_version` para el descuento. (B) La última Cuatrimestral (F-110): deja fuera 4 obras ABC.
- **D3 · Descuento de lo ejecutado** (nueva, sustituye a «desde cuándo»). (A) Por partida,
  `máx(0, plan desde V − ejecutado en el intervalo)`: +19,2 M€ de coste y +16,9 de venta sobre el
  plan restante, porque las obras van retrasadas. (B) Solo quitar los meses cerrados (114,0 M€):
  da por ejecutado lo planificado. (C) Por categoría: compensa adelantos y retrasos entre partidas.
- **D4 · Cabecera del corte** (ampliada). (A) `devengo_corte_obra` con plan, ejecutado, adelanto,
  retraso, real a origen y frontera con la cartera. (B) No.
- **D5 · Grano** (reformulada). (A) Partida (39.366 filas) para auditar + obra × mes × concepto ×
  categoría para consumir. (B) Solo el mensual. (C) Partida × mes (~250 k filas, sin uso claro).
- **D6** la fórmula leída, **D7** ingerir `auxcob`/`auxefc`, **D8** garantía por clase 4/5 y
  **D11** días de pago del proveedor: sin cambio, A.
- **D9 · Plazo de devolución de la retención** (reformulada). (A) Publicar los dos ingredientes
  y que sea la hipótesis H07/H11 con defecto `FIN_OBRA`. (B) Solo el de Negocio.
- **D10 · Cascada de obra (abierta, sin recomendación).** Medida: +113 pagos y 0,23 M€ (86,87 %
  → 86,95 %), +2 en la cartera viva; las `AGR` (11.378 pagos, 88,56 M€) no tienen vínculo en
  Sigrid. (A) Implementarla con `obra_via`, como pide la aceptación. (B) No, y reescribir la aceptación.
- **D12 · La regla** (reformulada). (A) `R-CAJA-HIPOTESIS` con todas las hipótesis y su nivel. (B)
  Ampliar `R-TESORERIA-ESTADO`: no cabe en su resumen.
- **D13 · Dónde vive el catálogo con sus defectos** (nueva). (A) `config/hipotesis_caja.yaml`:
  versionado, revisado y testeado. (B) Excel auxiliar. (C) Tabla editable.
- **D14 · Dónde viven los valores por obra** (nueva). (A) La sección `obras` del mismo YAML:
  auditable, sin infraestructura nueva; cada cambio es un commit y una imagen. (B) Un 4.º Excel
  auxiliar en Blob (`AUX_EXCEL_HIPOTESIS_CAJA`) cargado a `aux`: sin despliegue, pero exige
  construir la carga a `aux` que F-004 dejó abierta (DA-1); propuesto como feature aparte si los
  cambios se hacen frecuentes. (C) Tabla editable desde una aplicación: sería de `portal`.
- **D15 · Quién mantiene** (nueva). (A) Control de Costes propone, el humano aprueba (`validado` y
  fecha en el YAML), el ETL publica. (B) Cada jefe de obra los suyos (exige B o C en D14).
- **D16 · Frontera con la cartera** (nueva). (A) Columnas de `devengo_corte_obra` desde
  `tesoreria.efectos` y la ficha remite a `compras` para los albaranes. (B) Tabla en `build_compras`.
- **D17 · Los defectos propuestos** (nueva). (A) Publicarlos con `validado: false` hasta que
  Negocio los valide (la IA lo avisa). (B) No publicar defecto hasta validar: la IA preguntaría todo.
- **D18 · Valores de obra leídos de Sigrid** (nueva). (A) H09-H11 de los contratos con el cliente,
  nivel `OBRA`, fuente `SIGRID`, solo si dan un único valor. (B) Solo manuales.
- **D19 · Reparto del pendiente en el tiempo** (nueva). (A) Proporcional al perfil restante de V
  en cada partida; el retraso sin perfil (5,99 M€ de coste) al primer mes, marcado. (B) FIFO
  (lo adelantado consume los primeros meses). (C) No repartir: solo totales por partida.
