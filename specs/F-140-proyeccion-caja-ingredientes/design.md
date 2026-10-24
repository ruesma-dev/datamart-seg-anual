<!-- specs/F-140-proyeccion-caja-ingredientes/design.md -->
# F-140 · Diseño (fase 2 de la cartera: los ingredientes)

Mediciones: `progress/spec_F-140.md`. Requisitos: `requirements.md`. Decisiones abiertas: §9.

## 1. Encaje y límite

Se amplía el esquema MÓDULO `tesoreria` de F-037 (D1): mismos dos esquemas, mismo paso
`build_tesoreria`, mismo patrón de tablas que no se dropean. Lo nuevo lee `raw`,
`maestro.centros_coste` (vista sobre `raw`) y, por primera vez, `mart` y `stg` de la MISMA noche:
en `run-all` `build_stg` y `build_mart` van delante de `build_tesoreria`, sin declararlos en
`depends_on` (si fallan, se lee el `mart` de ayer: el patrón de `build_retenciones`, F-110).

```
mart.fact_seguimiento_mensual ─► tesoreria.devengo_pendiente_obra_mes   (obra × mes × concepto × categoría)
stg.plan_mensual (por versión) ─► tesoreria.devengo_corte_obra          (obra × concepto: plan y real en el corte)
raw.auxpag ∪ raw.auxcob       ─► tesoreria.plazos_forma_pago (vista)    (la fórmula, leída)
raw.ctr + ctrrec + prv        ─► tesoreria.condiciones_contrato_compra  (plazo y retención pactados)
raw.obrctr + rec              ─► tesoreria.condiciones_contrato_cliente (forma de cobro y retención)
raw.dcf / dcfpro / ctr        ─► obra_via + obra de la cascada en las dos `efectos`
```

**Nada de esto es caja**: no hay una sola columna que resulte de aplicar un plazo, una retención o
un IVA a un devengo (R14). La conversión la hace quien consulta y la regla dura `R-CAJA-HIPOTESIS`
le obliga a declararla (R26). **Límite de microservicio**: todo es ETL de este repositorio; las
dos tablas nuevas de Sigrid (`auxcob`, `auxefc`) se leen por `sigrid-api` como las otras 76, y el
MCP ya tiene `tesoreria` en su lista blanca (F-037): solo hay que reiniciarlo para el diccionario.
**No es de aquí** —ni se diseña— un motor de escenarios o una tabla de previsiones precalculadas:
si Negocio la quisiera, sería un consumidor del datamart, no parte de él.

## 2. Ficheros

**Crear**
- `etl_sigrid/domain/proyeccion_caja.py` — oráculo de la fórmula y del devengo (§3).
- `sql/tesoreria/04_plazos_forma_pago.sql`, `05_condiciones_contrato_compra.sql`,
  `06_condiciones_contrato_cliente.sql`, `07_devengo_pendiente.sql` (§4).
- `tests/test_f140_{dominio,sql,paso,diccionario}.py`.

**Modificar**
- `sql/tesoreria/00_setup.sql` — funciones de la fórmula (§4.1), tablas nuevas `IF NOT EXISTS`
  con PK e índices, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS obra_via` en las dos `efectos`.
- `sql/tesoreria/01_efectos_completo.sql` y `02_efectos_general.sql` — la cascada y `obra_via` (§4.2).
- `etl_sigrid/domain/tesoreria.py` — `obra_del_efecto` y las constantes de vía (§3).
- `application/steps/build_tesoreria_step.py` — cuatro `_SubStep` más y el docstring.
- `etl_sigrid/domain/reanudacion.py` — `"build_tesoreria": frozenset({"build_stg", "build_mart"})`.
- `config/tables_sigrid.yaml` — `auxcob` y `auxefc` (D7-A), con la exclusión estándar de textos.
- `config/diccionario/`: `tesoreria.yaml` (fichas nuevas, `obra_via`, la ficha de `efectos` deja
  de decir «solo del centro» y «la fase 2 no existe»), `tesoreria_restringida.yaml` (`obra_via`),
  `raw.yaml` (fichas de `auxcob` y `auxefc`), `compras.yaml` (`formas_pago.plazo_formula` y
  `contratos` remiten a `tesoreria`), `00_global.yaml` (`R-CAJA-HIPOTESIS`, el `para_que_sirve` de
  `tesoreria`, la frase de `R-TESORERIA-ESTADO` «convertir la planificación... declarar» remite a
  la regla nueva, `version` +1 sobre el valor real: hoy 60).
- Tests que fijan listas que cambian: `test_f037_sql.py` (columnas de las dos `efectos`;
  `test_f037_r8_la_obra_sale_solo_del_centro` se SUSTITUYE por los de R15-R16 en `test_f140_sql.py`,
  con su porqué en el commit), `test_f037_paso.py` (los ocho sub-pasos), `test_f148_reanudacion.py`
  (el dict), `test_f066_ingesta_raw.py` y `test_f081_yaml_ingesta.py` (78 tablas),
  `test_f147_presupuesto_contexto.py` (solo si se pasa el tope, con su motivo).
- `docs/ARCHITECTURE.md` (§ capas: tesorería fase 2; § «Qué se copia de Sigrid»: 78 tablas; §
  nocturna: `build_tesoreria` lee `stg` y `mart`), `CLAUDE.md` (mapa de `tesoreria/`),
  `azure-apps/datamart_seg_anual.md` (objetos nuevos, dos tablas más de `sigrid-api`). Commit local
  en `azure-apps`, sin push.

**No se tocan**: `sql/mart/*` y `sql/stg/*` (se leen, no se cambian), `sql/retenciones/*`
(`retenciones.fin_obra` se CITA como segunda fuente del plazo de retención, no se copia),
`sql/compras/*` (`compras.contratos` y `compras.formas_pago` siguen igual; solo sus fichas
remiten), `03_efectos_restringidos_mes.sql`, `domain/restriccion_personal.py`, `grants.py`,
`apply_grants_step.py`, `settings.py` e `infra/sql/02_roles.sql` (los objetos nuevos viven en un
esquema que ya se concede y se veta por esquema), `main.py` (el paso ya está en `run-all`).

## 3. Dominio (sin dependencias de infraestructura)

`domain/proyeccion_caja.py`:
- `REGEX_TOKEN_DIAS = r"^[0-9]+$"`, `REGEX_TOKEN_RETENCION = r"^[0-9]+R$"` (R mayúscula: la
  minúscula no se ha visto y falla cerrado), `SEPARADOR = r"\s+"`.
- `PlazoFormula(dias_vencimientos: tuple[int, ...], dias_retencion: int | None, reconocida: bool)`
  (dataclass congelada) y `leer_formula_plazo(formula: str | None) -> PlazoFormula` (R1, R2): sin
  texto, un token raro o dos `NR` → `PlazoFormula((), None, False)`. `"0"` → `((0,), None, True)`;
  `"30 60 90"` → `((30, 60, 90), None, True)`; `"90  450R"` → `((90,), 450, True)`;
  `"0 450R"` → `((0,), 450, True)`; `"450R"` (solo retención) → `((), 450, True)`.
- `es_mes_pendiente(anio_mes: date, mes_ultimo_cierre: date | None) -> bool` (mes posterior al
  cierre; sin cierre, todos) y `es_mes_pasado_sin_cierre(anio_mes, fecha_build) -> bool`.
- `PATRON_COLUMNA_DE_CAJA = r"caja|flujo|previst|fecha_pago|fecha_cobro|con_iva"` (R14).

`domain/tesoreria.py` (se amplía, no cambia lo de F-037):
- Vías `VIA_CENTRO = "CENTRO"`, `VIA_CONTRATO = "CONTRATO"`, `VIA_FACTURA_CABECERA`,
  `VIA_FACTURA_LINEAS`.
- `obra_del_efecto(obra_centro, tiene_centro, obras_contrato, obra_cabecera, obras_lineas)
  -> tuple[int | None, str | None]` (R15): el orden de R15; un conjunto con más de una obra no
  decide y se pasa al escalón siguiente; con centro que no es obra, `(None, None)` sin mirar más.

El SQL no llama a Python: lleva los mismos literales y `test_f140_sql.py` los compara (F-135).

## 4. SQL

### 4.1 `00_setup.sql` (se añade al final, todo idempotente)
- `tesoreria.fn_plazo_tokens(TEXT) RETURNS TEXT[]` (`regexp_split_to_array(btrim(f), '\s+')`,
  NULL si vacío), `fn_plazo_reconocido(TEXT) BOOLEAN`, `fn_plazo_dias(TEXT) INT[]` (NULL si no
  reconocida) y `fn_plazo_dias_retencion(TEXT) INT`, `IMMUTABLE`, con los regex de §3.
- `CREATE TABLE IF NOT EXISTS` de `condiciones_contrato_compra` (PK `contrato_id`),
  `condiciones_contrato_cliente` (PK `contrato_cliente_id`), `devengo_pendiente_obra_mes` (PK
  `obra_id, anio_mes, concepto, categoria`) y `devengo_corte_obra` (PK `obra_id, concepto`), con
  índices por obra (y proveedor / forma de pago). Columnas en §4.3-4.6; tipos explícitos.
- `ALTER TABLE tesoreria_restringida.efectos ADD COLUMN IF NOT EXISTS obra_via VARCHAR(16)`; ídem
  `tesoreria.efectos`. Queda al final de las dos (en la completa, tras `motivo_restriccion`): la
  general sigue siendo «la completa sin las dos de restricción, en el mismo orden» (R10 de F-037).

### 4.2 La cascada en `01_efectos_completo.sql` (solo la rama PAGO)
CTE `obra_factura` ANTES del `UNION ALL`, calculada SOLO para los documentos de pagos sin
`cenide` (rendimiento): por `dcf.ide`, `obras_contrato` (`ctr.obride` de `dcf.ctride` y de
`dcfpro.docoriide` cuando es un `ctr`, distintas y no nulas), `obra_cabecera` (`NULLIF(dcf.obride,
0)`) y `obras_lineas` (`dcfpro.obride` distintas). En la rama PAGO, un `CASE` en el orden del
dominio decide `obra_via` y la obra; `codigo_obra`/`nombre_obra` salen de `raw.con` de esa obra
(como `retenciones/01_movimientos.sql`). Con centro: lo de hoy, `obra_via = 'CENTRO'` si
resuelve a obra y NULL si no. COBRO: `obra_via = 'CENTRO'` o NULL (sin ventas no hay cascada,
F-040). `02` copia `obra_via` (columna nueva al final del `INSERT` y del `SELECT`). Coste: las
uniones se limitan a ~17 k documentos; se mide (R30).

### 4.3 `04_plazos_forma_pago.sql` → vista `tesoreria.plazos_forma_pago`
`CREATE OR REPLACE VIEW` de un `UNION ALL`: PAGO desde `raw.auxpag` + `raw.auxefp`, COBRO desde
`raw.auxcob` + `raw.auxefc` (D7-A). Columnas: `sentido, forma_pago_id, codigo, nombre, medio_id,
medio, plazo_formula, dias_vencimientos, num_vencimientos, dias_retencion, formula_reconocida,
fecha_baja`. Sin filtro (70 + 52 filas). Vista y no tabla: se rehace cada noche tras la ingesta,
como `compras.formas_pago`.

### 4.4 `05_condiciones_contrato_compra.sql`
`TRUNCATE` + `INSERT` desde `raw.ctr c JOIN raw.con con ON con.ide = c.ide`, con `raw.con` de la
obra y del proveedor, `raw.conest` (`tip = 44`, `LEFT`), `raw.auxpag` (`LEFT`, por `pagide`),
`raw.prv` (por `entide`) y un `LATERAL` sobre `raw.ctrrec` + `raw.con` del recargo con
`reccla IN (4, 5)` (D8; guarda de grano `ORDER BY pos, ide LIMIT 1`, como `compras/01`).
`WHERE NOT EXISTS` tercero `tip = 43` (R6). Columnas: `contrato_id, codigo_contrato, empresa_id,
fecha_contrato, estado_codigo, estado, obra_id, codigo_obra, nombre_obra, proveedor_id,
proveedor_nombre, importe_base, importe_iva, forma_pago_id, forma_pago, plazo_formula,
dias_vencimientos, num_vencimientos, dias_retencion, formula_reconocida,
proveedor_dias_pago, proveedor_meses_sin_pago, retencion_garantia_porcentaje,
retencion_garantia_concepto, retencion_garantia_clase`. `importe_base = totbas`, `importe_iva =
totiva` (en las 19.170, `totdoc = totbas + totiva`; `tot` es otra cosa y no se publica).

### 4.5 `06_condiciones_contrato_cliente.sql` (D7-A)
`TRUNCATE` + `INSERT` desde `raw.obrctr`: `contrato_cliente_id, obra_id, codigo_obra,
nombre_obra, empresa_id, codigo_contrato, descripcion_contrato, cliente_id, cliente_nombre,
forma_cobro_id, forma_cobro, plazo_formula, dias_vencimientos, num_vencimientos, dias_retencion,
formula_reconocida, cliente_dias_pago (obrctr.pagdia), retencion_garantia_porcentaje (`coegar` si
≠ 0, si no `rec.valpor × 100` de `retide`), retencion_garantia_fuente (`COEFICIENTE` /
`TIPO_RETENCION`), retencion_garantia_concepto, retencion_plazo_meses (`plaret`, 0 → NULL),
garantia_plazo_meses (`plagar`), fecha_inicio_garantia (`fecinigar`)`.

### 4.6 `07_devengo_pendiente.sql`
1. `ult`: por (obra, concepto), `MAX(anio_mes)` de `mart.fact_seguimiento_mensual` con
   `tipo_dato = 'REAL'` → `mes_ultimo_cierre`.
2. `TRUNCATE` + `INSERT INTO tesoreria.devengo_pendiente_obra_mes` de las filas `tipo_dato =
   'PLANIFICADO'` con `anio_mes > COALESCE(mes_ultimo_cierre, '-infinity')`, agrupadas por
   (obra, anio_mes, concepto, categoria, versión): `importe_devengo = SUM(importe_mes)::NUMERIC(18,2)`,
   `num_partidas = COUNT(DISTINCT partida_id)`, `version_master`, `tipo_master`,
   `version_fec_creacion`, `mes_ultimo_cierre`, `mes_pasado_sin_cierre = anio_mes <
   date_trunc('month', CURRENT_DATE)`; `empresa_id` y `clave_obra` (`emp-cod`) de `raw.con` de
   la obra. Si un mes tuviera dos versiones en una celda, la PK lo rompe: es la invariante de
   `mart` («una versión vigente por mes»), y que falle es lo correcto.
3. `TRUNCATE` + `INSERT INTO tesoreria.devengo_corte_obra`: por (obra, concepto) del paso 2,
   `num_versiones_pendientes`, la versión del último mes pendiente, `real_origen_corte =
   SUM(importe_mes)` real de mart, y `plan_hasta_corte` / `plan_total` = `SUM(importe_mes)` de
   `stg.plan_mensual WHERE obra_id = … AND ambito_id = (8 coste | 11 venta) AND version = …`
   (`anio_mes <= mes_ultimo_cierre` para el primero). Es el ÚNICO acceso a `stg` (R12, test).
Medido: el agregado del paso 2 lee en ~90 s (737 filas, 21 obras).

## 5. Paso, nocturna e ingesta

`SUB_PASOS` pasa de 4 a 8: `plazos_forma_pago` (04, vista: sin tabla destino),
`condiciones_contrato_compra`, `condiciones_contrato_cliente` y `devengo_pendiente` (07; cuenta
`devengo_pendiente_obra_mes`). Cada fichero es su transacción: si 07 falla (p. ej. un `mart` a
medias), FAILED con su nombre y quedan las tablas de ayer; la cartera ya se ha construido.
`LECTURAS_PARA_REANUDAR` (F-148): un reintento que rehaga `build_stg` o `build_mart` rehace la
tesorería. `auxcob` y `auxefc` entran en `tables_sigrid.yaml` como `auxpag` (`incremental_column:
tiemod`, misma lista de exclusión); 52 y 8 filas: coste de ingesta despreciable.

## 6. Diccionario y la regla dura

`R-CAJA-HIPOTESIS` (bloqueante, `entrega: resumen`). `resumen` (≤ 250, sin cifras que envejezcan):
«No hay caja proyectada: `tesoreria.devengo_pendiente_obra_mes` es devengo SIN IVA. Pasarlo a
caja es una hipótesis: di versión y mes de corte, plazo y su fuente, retención (%, plazo, fuente),
IVA y solape con la cartera PREVISTA.» `regla`: los ingredientes y dónde está cada uno; las dos
fuentes del plazo de retención (fórmula de Sigrid, días desde factura; `retenciones.fin_obra`,
criterio de Negocio); que el plazo real se alarga 7-22 días sobre el nominal (dato del `motivo`);
que el reparto del devengo entre contratos y entre vencimientos de `30 60 90` no está en Sigrid;
`plan pendiente` frente a `plan total − real` (`devengo_corte_obra`); y que la cartera PREVISTA y
no antigua ya es caja comprometida y no se suma dos veces con el devengo del mismo mes. `ambito`:
los cinco objetos nuevos, `tesoreria.efectos` y `mart.fact_seguimiento_mensual`. Las fichas
llevan cobertura medida (§1-§3 de `progress/spec_F-140.md`), `clave_negocio` y dos
`ejemplos_preguntas` que enrutan («qué caja necesitará la obra X», «plazo pactado con el
proveedor Y»). Presupuesto de F-147: se mide; si se pasa, se acorta o se sube con su motivo.

## 7. Despliegue (MANUAL, tras el review)

1. Imagen con tag fechado y job apuntado a ella (comprobar el tag del job).
2. Desde el puesto: `ingest --table auxcob --full`, `ingest --table auxefc --full`,
   `build-tesoreria` (anotar duración) y `build-compras` (la vista de vencimientos).
3. R13, R18, R31; `publicar-diccionario` con la imagen ya en el job (memoria «publicar el
   diccionario solo con su imagen»), `check-diccionario`, `check-declarados`, `check-unicidad`;
   reiniciar el MCP; R20 y R28. 4. Al día siguiente: la nocturna construye los ocho sub-pasos.

## 8. Riesgos

- **Leer `mart` sin `depends_on`**: si `build_mart` falla, el devengo es el de ayer y la ficha lo
  dice (`R-FRESCURA`); si `mart` quedara a medias, 07 publicaría a medias: se acepta como en
  `retenciones` (la puerta de `build_stg` protege la carga truncada, F-024).
- **Versión nueva entre el corte y hoy**: un mes pasado sin cierre puede regirse por la versión
  anterior (mart elige por mes); `num_versiones_pendientes` lo delata (hoy 1 en todas).
- **Un plan viejo rige**: 2 obras con `Planif Inicial` (una de 2020); `version_fec_creacion` va
  en cada fila y la regla manda decirlo.
- **No arregla** la obra de las agrupaciones (`AGR`, 88,56 M€) ni la de los cobros sin documento
  de venta (F-040): Sigrid no guarda el vínculo (`padide` vacío en origen).

## 9. Decisiones abiertas (las valida el humano; recomendada: A)

- **D1 · Dónde viven.** (A) En `tesoreria`, sub-pasos 04-07 de `build_tesoreria` leyendo `raw` y
  `mart`. (B) Esquema nuevo `proyeccion` con su paso: más fontanería (permisos, MCP, `run-all`)
  para lo mismo. (C) Repartido entre `compras` y `retenciones`: la IA no encontraría los
  ingredientes juntos, y `compras` se dropea cada noche.
- **D2 · Qué versión vale.** (A) La que `mart` ya elige por mes (para el futuro, la última
  `Planif Inicial`/`ABC`/`Cuatrimestral` vigente): coherente con `R-VERSION-MASTER` y con lo que
  ve Power BI. (B) La última Cuatrimestral (criterio de `retenciones.fin_obra`, F-110): dejaría
  fuera las 4 obras regidas por un ABC reciente (42,0 M€ de coste pendiente). (C) Todas.
- **D3 · Desde cuándo es pendiente.** (A) Desde el mes siguiente al último cierre real del
  concepto, con `mes_pasado_sin_cierre` (3 obras, 4,79 M€). (B) Desde el mes en curso: perdería lo
  planificado y no cerrado.
- **D4 · La cabecera del corte.** (A) Publicar `devengo_corte_obra` (plan hasta el corte, plan
  total, real a origen): sin ella la IA no puede ver el desfase de 14,06 M€ entre plan y real ni
  elegir «plan total − real». (B) No publicarla.
- **D5 · Grano.** (A) Obra × mes × concepto × categoría (CD/CI/CP/OTRO): la mano de obra propia no
  se paga como una subcontrata. (B) Sin categoría. (C) Por partida (25 veces más filas, sin uso).
- **D6 · La fórmula, leída.** (A) Columnas `dias_vencimientos`/`dias_retencion` con la gramática
  medida (122 de 122) y el verbatim al lado; cierra DA-5 de F-073 («quien necesite un plazo
  numérico lo decide en su feature»). (B) Solo verbatim: «30 450R» lo interpretaría cada consulta.
- **D7 · El lado de cobros.** (A) Ingerir `auxcob` (52) y `auxefc` (8) y publicar
  `condiciones_contrato_cliente` (19 de las 21 obras con devengo tienen forma de cobro). (B) Solo
  pagos hasta F-040: la venta pendiente (115 M€) quedaría sin plazo.
- **D8 · Qué es retención de garantía en el contrato.** (A) Clase de recargo 4 o 5 (F-128): 6.358
  contratos. (B) Código `RET%` (F-067, `compras.contratos`): 6.360 (incluye `RETESP`, clase 1).
  Con A, las dos tablas difieren en 2 contratos y la ficha lo dice.
- **D9 · El plazo de devolución de la retención.** (A) Publicar el de Sigrid (`dias_retencion`,
  días desde la factura, confirmado: mediana 457 para `450R`) y remitir a `retenciones.fin_obra`
  (fin de obra + plazo del cliente, criterio de Negocio); la regla obliga a decir cuál. (B) Solo el
  de Negocio: contradiría lo que Sigrid genera en los efectos.
- **D10 · La cascada de obra (D4-B de F-037).** (A) Implementarla como pide la aceptación, con
  `obra_via`: +113 pagos (0,23 M€), +2 en la cartera viva; 86,87 % → 86,95 %. (B) No implementarla
  y que el humano reescriba la aceptación con esta medida: la cascada no mueve la cobertura y el
  hueco real (las `AGR`) no tiene vínculo en Sigrid.
- **D11 · Días de pago del proveedor.** (A) Publicar `prv.pagdia`/`pagmes` tal cual (2.919 y 2.223
  de 9.638): explican parte del alargamiento de 7-22 días. (B) No.
- **D12 · La regla.** (A) Regla nueva `R-CAJA-HIPOTESIS` (§6). (B) Ampliar `R-TESORERIA-ESTADO`:
  mezclaría «cómo se lee la cartera» con «cómo se convierte el devengo», y su resumen no cabe.
