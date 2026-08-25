<!-- progress/explore_F-006_datamart_casos_uso.md -->
# F-006 · Qué puede responder hoy el datamart (2026-08-20)

> Informe del subagente explorador (solo lectura). Lo guarda el líder.

## Veredicto sobre los seis casos de uso del humano

| # | Pregunta | Veredicto |
|---|---|---|
| 1 | Ranking de facturación por proveedor | **SÍ** (por año; mes derivable) |
| 2 | Retenciones de los proveedores de una obra | **SÍ** (detalle; falta vista obra×proveedor) |
| 3 | Proveedor de fontanería de la obra XXX | **PARCIAL** — no hay oficio/gremio |
| 4 | Flujo de caja de una obra | **NO** — nada construido |
| 5 | Facturado por contrato + albarán pendiente + comparativos | **CASI** — comparativo NO modelado |
| 6 | Planificación temporal mensual | **SÍ** — pero no por F-019 (eso es troceo de build) |

## AVISO OPERATIVO CRÍTICO PARA EL MCP

`run-all` construye solo `raw -> stg -> mart` + `apply_grants` (`main.py:405-443`).
**`cierre`, `compras`, `maestro` y `retenciones` NO están en el pipeline
nocturno**: se construyen a mano (`build-cierre`, `build-compras`,
`build-maestros`, `build-retenciones`). Cuatro de los ocho esquemas pueden estar
arbitrariamente desfasados respecto a `raw`. `_meta.v_frescura` lo delata paso a
paso. El diccionario semántico TIENE que decirlo.

## Inventario completo (materia prima del diccionario)

**8 esquemas · 31 tablas `raw` · 18 tablas derivadas · 33 vistas · 12 funciones.**

### `_meta`
- `etl_runs` (tabla): una fila por (stage, step): tiempos, status, filas, error, `batch_id`.
- `v_raw_state` (vista): de qué carga viene cada tabla de `raw`.
- `v_frescura` (vista): por paso, último OK y último intento por separado.

### `raw` — copia 1:1 de Sigrid (31 tablas)
`con`, `conext`, `obr`, `obrparpar`, `obrparpre`, `obrfas`, `obrfasamb`,
`obrctr`, `cen`, `auxobrtip`, `auxobrcla`, `auxobramb`, `auxobrtca`, `condir`,
`obrprv`, `prv`, `auxpro`, `auxmun`, `ctr`, `com`, `comlin`, `comprv`, `ctrpro`,
`dca`, `dcapro`, `dcf`, `dcfpro`, `dcfprodes`, `cob`, `pag`, `rec`.

### `stg`
- `obras`: una fila por obra real (excluye códigos administrativos y de 5+ dígitos).
- `partidas`: árbol de partidas reconstruido; `capitulo_raiz_cod`, `categoria`
  CD/CI/CP/OTRO (**por heurística sobre el código**), `ruta_capitulos`, `nivel`.
- `fases`: fases con fechas tipadas y `plazo_meses`; en reales `fase = mes`.
- `presupuesto`: (obra × partida × ámbito × fase), NUMERIC(20,6), `importe_oficial`.
- `version_master_vigente`: versión master vigente por obra (`conext.cod='15'`).
- `plan_mensual`: **núcleo temporal**, explosión mensual de ámbitos 3/7/8/11. ~29,4 M filas.
- `ambitos` (vista): los 14 ámbitos con `tipo` y `uso_seguimiento`.
- Funciones: `fn_sigrid_date_to_date`, `fn_master_mes_representado`, `fn_master_fecha_efectiva`.

### `aux`
- `periodificacion_partida`: reglas de periodificación. **Se crea VACÍA**: hoy no periodifica nada.

### `mart`
- `fact_seguimiento_mensual`: (obra × partida × mes × escenario). 4 escenarios Coste/Venta × Real/Planificado.
- `fact_seguimiento_categoria`: preagregado por categoría CD/CI/CP.
- `v_fact_periodificado`: hoy passthrough (aux vacía).
- `v_pbi_dim_obra`, `v_pbi_dim_partida`, `v_pbi_dim_partida_niveles` (nivel_1..6),
  `v_pbi_dim_escenario`, `v_pbi_dim_fecha` (calendario en castellano),
  `v_pbi_fact`, `v_pbi_fact_categoria`.
- `v_master_versiones_tipadas`, `v_master_vigente_anual`.
- `v_pbi_cp_tipologia`: CP anual por tipología (SEGUROS, AVALES, APORTE GG...).

### `cierre`
- `fact_cierre_mensual`: (obra × mes × concepto VENTA/INDIRECTOS/DIRECTOS/GENERALES).
- `v_pbi_cierre_resumen`: 6 filas por (obra × mes), GASTOS y BENEFICIO derivados.
- `v_pbi_dim_concepto`, `v_pbi_cierre_cabecera` (cliente, técnico, centro, fechas,
  presupuesto inicial/vigente/aprobado, modificados),
  `v_pbi_cierre_indirectos_detalle` (4 variantes de periodificación de INFRAESTRUCTURA),
  `v_pbi_cierre_generales_detalle`, `v_pbi_dim_subcategoria_ci` (**por obra**),
  `v_pbi_dim_tipologia_cp`, `v_pbi_planif_vs_real`.
- Funciones: `fn_parse_mes_fase`, `fn_mes_de_fase`, `fn_mes_de_version_master`.

### `compras`
- `contratos` (de `raw.ctr`+`con`, con `comparativo_id`), `contrato_lineas` (de `ctrpro`).
- `albaranes` (de `dca`, tip=14, ALBARAN/PROFORMA/NOTA), `albaran_lineas`
  (de `dcapro`, con `importe_pendiente_facturar`).
- `facturas` (de `dcf`, tip=15, FACTURA/ABONO), `factura_lineas` (de `dcfpro`,
  con trazabilidad a albarán (14) o contrato (44)).
- `fact_compras_linea`: hechos unificados por línea de los 6 tipos de documento.
- `v_pbi_contrato_consumo`, `v_pbi_proveedor_obra` (obra × proveedor × año),
  `v_pbi_albaranes_sin_facturar`, `v_pbi_partida_coste`.
- Funciones: `fn_sigrid_date`, `fn_serie`, `fn_tipo_documento`.

### `maestro`
- `obras` (vista), `proveedores` (vista, con CIF y dirección de `condir`),
  `proveedores_obra` (vista, derivada de contratos: `n_contratos`, `importe_contratado`).
- `fn_fecha`.

### `retenciones`
- `tipos`, `movimientos` (**un registro por efecto con `retide<>0`**: `sentido`
  PROVEEDOR/CLIENTE, obra, entidad, importe, fechas prevista/real, `estado`
  VIVA/LIQUIDADA, `vencida_sin_liquidar`).
- `v_src_lineas_compra`, `v_src_lineas_venta` (**esta siempre vacía**: `dvfpro` no se ingiere).
- `v_pbi_retencion_entidad`, `v_pbi_retencion_obra` (+`posicion_neta`),
  `v_pbi_retenciones_vivas`, `v_pbi_retenciones_vencidas`,
  `v_pbi_retencion_resumen` (+`sin_obra_asignada`).

## Detalle por pregunta

### 1 · Proveedores que más han facturado — SÍ
`compras.v_pbi_proveedor_obra` (`proveedor_nombre`, `anio`, `facturado`,
`albaranado`, `certificado_proforma`, `contratado`, `num_*`) y
`compras.fact_compras_linea` para grano mensual.
Falta: vista de ranking global sin obra; el periodo es **anual**; hay filas con
`obra_id IS NULL` (estructura/GG) que no se pueden perder. Importes **sin IVA**;
**los ABONOS entran en negativo** y restan.

### 2 · Retenciones de proveedores de una obra — SÍ
`retenciones.movimientos` filtrando `sentido='PROVEEDOR'`.
Falta la **vista cruzada obra × proveedor** (las dos agregadas cortan por un eje
cada una). Atribución a obra por `cenide` (~98 %); si la factura toca varias
obras, `obra_id` queda NULL y `num_obras_documento > 1` lo señala.
Dos lecturas del saldo (`saldo_vivo` por `fecrea=0` vs `neto_practicado` por
signo) que pueden divergir: por defecto `saldo_vivo`.

### 3 · Proveedor de fontanería — PARCIAL. **No hay clasificación por oficio.**
1. Lo único clasificado es CD/CI/CP/OTRO, **por heurística sobre el código del
   capítulo raíz** (`stg/04_partidas.sql:84-100`). No es taxonomía de oficio.
2. **`raw.auxobrtca` está ingerido y NO se usa**: el YAML lo declara como el
   catálogo de tipos de capítulo (`obrparpar.tcaide`) «para clasificar sin
   heurísticas» y ningún SQL lo mira. Hueco barato con valor inmediato.
3. Hoy la única vía es texto libre (`LIKE '%FONTANER%'` sobre
   `contratos.descripcion`, `fact_compras_linea.descripcion`,
   `stg.partidas.descripcion_corta`). Funciona, pero no es determinista.
4. Existe en Sigrid y no se ingiere: el maestro de productos `pro` (hoy solo
   guardamos `producto_id` desnudo) y sus familias.

### 4 · Flujo de caja — NO. **Cero objetos de tesorería.**
El dato **está en `raw` y se tira**: `raw.pag` (252.189 filas) y `raw.cob`
(21.643) traen TODOS los efectos con `tot`, `fecven` (vencimiento previsto),
`fecrea` (real; 0 = pendiente), `conide`, `entide`, `cenide`. El módulo
`retenciones` los filtra con `WHERE retide <> 0` y descarta el resto, **que es
exactamente el flujo de caja**. Un `tesoreria.movimientos` sin ese filtro es casi
el mismo SQL que `retenciones/01_movimientos.sql`: la palanca más barata.
No se ingieren las ventas (`dvf`/`dvfpro`); hay un
`config/tables_sigrid_venta_snippet.yaml` preparado y sin integrar.
`stg.plan_mensual` es **devengo, no caja**: no tiene plazos de pago.

### 5 · Contratos, albaranes y comparativos
| Concepto | ¿Modelado? | Origen |
|---|---|---|
| Contrato | SÍ | `raw.ctr` + `ctrpro` -> `compras.contratos`/`contrato_lineas` |
| Albarán | SÍ | `raw.dca` + `dcapro` -> `compras.albaranes`/`albaran_lineas` |
| **Comparativo** | **NO** | `raw.com`, `comlin`, `comprv` **ingeridos**, ningún SQL los lee |

`compras.v_pbi_contrato_consumo` da contratado / albaranado / certificado /
facturado / **`importe_albaranado_sin_facturar`** / disponible / `pct_consumido`.
Del comparativo solo sobrevive `comparativo_id` como FK. Reconstruirlo es
`com.obride -> obra`, `comprv -> proveedor`, `comlin -> líneas`.
Trampa: el pendiente sale de `dcapro.canfac`; **la sobrefacturación conserva
signo negativo**. Solo ALBARAN y PROFORMA cuentan como pendientes; las NOTA sí
suman en `importe_consumido` como `otros_docs`.
El proyecto `albaranes` es otra base: **PostgreSQL no cruza bases** y esa
frontera es deliberada.

### 6 · Planificación temporal — SÍ (y F-019 no es lo que parece)
`specs/F-019-plan-mensual-por-tramos/` **no es negocio**: los «tramos» son lotes
de obras para trocear el build (incidente del disco al 93,4 % el 2026-08-09).
Dejó `etl_sigrid/domain/tramos.py`, la puerta de disco por tramo y una fila por
tramo en `_meta.etl_runs`. **El modelo no cambió.**
La planificación vive en `stg.plan_mensual` -> `mart.fact_seguimiento_mensual` ->
`cierre.v_pbi_planif_vs_real`, con `mart.v_master_versiones_tipadas`.
Trampas que el diccionario DEBE recoger:
1. **`importe_mes` jamás se suma entre meses**; `importe_origen` ya es acumulado.
2. `stg.plan_mensual` trae **todas** las versiones master: consultarla sin filtrar
   versión **multiplica los importes**. `mart` ya elige la vigente.
3. Filas gemelas de `raw.obrfasamb` (F-022 abierta): ~0,035 % no determinista.
4. **No existe serie única «plan vigente»**: es F-002, pendiente.
5. La periodificación está apagada (`aux` vacía).

## Recomendaciones para el diccionario semántico

1. **Marcar la frescura por esquema** y exponer `_meta.v_frescura` como recurso.
2. **Cuatro reglas antisuma**: `importe_mes` entre meses; versión en
   `plan_mensual`; abonos ya negativos; nunca unir un efecto de retención a las
   líneas de su factura (multiplica).
3. **Tres huecos baratos**: (i) `tesoreria` sobre `raw.pag`/`cob` sin el filtro
   de `retide` -> pregunta 4; (ii) modelar `com`/`comlin`/`comprv` -> pregunta 5;
   (iii) usar `raw.auxobrtca` en `stg.partidas` -> sustituye la heurística y abre
   la pregunta 3.
4. **Un hueco caro pero estructural**: ingerir `dvf`/`dvfpro` (ventas).
