# F-104 · La retención de CLIENTE saneada — diseño

**Rigor: `estandar`.** No cumple ningún disparador de `critico` (`CHECKPOINTS.md`, «Niveles de
rigor»): no escribe en producción ni en lo compartido (el build lo lanza la nocturna de siempre),
no publica datos personales (D9 = a; las tablas de `ventas` no llevan CIF y pasan su guarda) y
solo añade columnas al final de `movimientos`, como F-094 (`estandar`).

Requisitos: `requirements.md` (R1-R37). Mediciones: `progress/spec_F-104.md`. SQL de referencia,
columnas exactas y mapa de tests: `design_detalle.md`. **[rev. 16-11]** marca lo que cambia
frente a la versión aprobada el 2026-11-07; el porqué, en §9.

## 1. Encaje y límite

Dos esquemas, dos pasos que ya existen, SQL puro. **`retenciones`** (paso `build_retenciones`):
estado de CLIENTE, cuentas, saldo y cuadre por cuenta, sobre `raw` + `maestro.centros_coste`; corre
antes que `ventas` y `contabilidad`, por eso lee `raw.cli` y `raw.apu`, nunca `ventas.clientes` ni
`contabilidad.mayor`. **[rev. 16-11] `ventas`** (paso `build_ventas`): la conciliación por factura
(D10 = b), que lee `ventas.facturas` (la garantía y el RETESP ya clasificados por
`ventas.fn_clase_recargo`), `raw.dvfrec` y lo que `retenciones` construyó esa noche. No hay dominio
nuevo: el estado es el CASE de F-094. No se toca `sigrid-api` ni otro proyecto. F-161, F-162 y
F-163 no afectan (`progress/spec_F-104.md` §7).

## 2. Ficheros

**Crear**
- `etl_sigrid/infrastructure/postgres/sql/retenciones/08_saldo_cliente.sql`: `saldo_contable_cliente`, `v_cuadre_cliente`.
- **[rev. 16-11]** `etl_sigrid/infrastructure/postgres/sql/ventas/06b_retencion_cliente.sql`:
  `retencion_factura`, `retencion_cuenta`, `v_retencion_cliente` y su guarda R33 (§6).
- `tests/test_f104_retenciones_cliente.py` y **[rev. 16-11]** `tests/test_f104_ventas_retencion.py`:
  tests sobre el TEXTO del SQL y del diccionario, como `test_f094_*`, `test_f095_*`, `test_f040_*`.

**Modificar**
- `.../retenciones/01_movimientos.sql`: **[rev. 16-11]** al principio `cuentas_cliente` y su guarda
  (§3); rama CLIENTE (§4); columnas nuevas al final de las dos ramas; cabecera; `COMMENT`; índice
  `idx_ret_mov_cuenta (sentido, cuenta_id)`.
- `etl_sigrid/application/steps/build_retenciones_step.py`: sub-paso `saldo_cliente` (`08`), el último.
- **[rev. 16-11]** `etl_sigrid/application/steps/build_ventas_step.py`: sub-paso `retencion_cliente`
  (`06b_retencion_cliente.sql`, `target_table="retencion_factura"`) entre `restringida` y
  `guardas`, y el docstring (lee `retenciones` de la misma noche por POSICIÓN, sin `depends_on`).
- `config/diccionario/retenciones.yaml` (R16, R23), **[rev. 16-11]** `ventas.yaml` (R25, R36),
  `00_global.yaml` (R17, R18); `docs/ARCHITECTURE.md` (R25); comentario de `cob` en
  `config/tables_sigrid.yaml` (R26).
- Tests: `test_f094_retenciones_estado.py` (el de `fecrea` se sustituye, con nota a F-104);
  `test_f047_steps.py`; **[rev. 16-11]** `test_f040_frontera.py` (`TOCADOS_DESPUES`, R24) y
  `test_f040_pipeline.py` (`FICHEROS` con `06b`).
- `../azure-apps/datamart_seg_anual.md` (R19): commit aparte allí, sin push (protocolo de `CLAUDE.md`).

**NO se tocan**: `retenciones/00_setup.sql` (lo protege `test_f040_frontera.py`), `02`-`07` de
`retenciones`, `tesoreria/`, `ventas/00`-`07` (la garantía se lee de `ventas.facturas`: R30),
`infra/sql/02_roles.sql` (R35), las tablas de la ingesta, el dominio.

## 3. `retenciones.cuentas_cliente`, al principio de `01` [rev. 16-11, D3 a]

`FULL JOIN` de las cuentas declaradas (`raw.cli.cueretide`, con su `cliente_id`) y las de prefijo
(`raw.con`, `tip = 17`, `^43[0-9]8`), `criterio_seleccion` `CUERETIDE` si la declara un cliente;
PK `cuenta_id` (SQL en `design_detalle.md` §1). La PK es la guarda de «dos clientes, una cuenta»
(R5; hoy 1:1, 211 y 211, como `uq_ret_cuentas_proveedor_cuenta`); la de vacía, un `RAISE
EXCEPTION` justo después. La unión porque solo `cueretide` pierde UNEXUM (su ficha declara
4308001593 y sus 947.835,66 están en 4338001593) y solo prefijo pierde `cliente_id` y 4 cuentas
declaradas fuera de 43x8 (saldo 0). Ninguna es cuenta de retención de proveedor. **`tip = 17`**:
son las imputables; `03` dice «tip 16» y no filtra: no se toca, no se copia.

## 4. `01_movimientos.sql`: la rama CLIENTE

- Estado (R1), el de PROVEEDOR con `c.`: `CASE WHEN COALESCE(efe.fecbaj,0) <> 0 OR efe.est IN
  (14,15) THEN 'BAJA' WHEN COALESCE(c.fecrea,0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' ELSE 'VIVA' END`.
- `vencida_sin_liquidar` (R2): la condición de VIVA completa, como PROVEEDOR.
- Universo (R6): `WHERE COALESCE(c.retide,0) <> 0 OR c.cueide IN (SELECT cuenta_id FROM
  retenciones.cuentas_cliente)`; `tipo_id` = `NULLIF(c.retide, 0)`.
- `origen_retencion` (R7) y `cuenta_id` (R8, `NULLIF(cueide, 0)`) AL FINAL de cada rama, mismo
  orden en las dos (UNION ALL por posición); PROVEEDOR lleva el literal `'EFECTO_RETENCION'`.
- `entidad_cif` (R23, D9 = a): sigue `NULL::VARCHAR(24)`. Obra: sin cambios (respaldo por
  `dvfpro` ya activo; 0 filas CLIENTE sin obra). Un solo `UNION ALL` (`test_f094`).

Esperado (16-11): CLIENTE 2.256 → 3.461 filas (+1.205 `retide = 0` de las cuentas); VIVA 22,44 M
→ 10,53 M, de ellos `EFECTO_RETENCION` 2,40 M.

## 5. `retenciones/08_saldo_cliente.sql`

**`saldo_contable_cliente`** (R11): CTE sobre `raw.apu JOIN retenciones.cuentas_cliente`,
`importe = deb - hab` (activo: la 43x8 crece por el debe) y la clase con las reglas y el orden de
`03` (CIERRE, SALDO_INICIAL sin cierre el ejercicio anterior, APERTURA, ALTA > 0, BAJA ≤ 0); se
REPLICA el CASE (`apuntes_contables` es de proveedor). Medido: 16.002.697,94 € en 169 cuentas.
**`v_cuadre_cliente`** (R12, R13): `FULL JOIN` del saldo con `movimientos` CLIENTE `VIVA` por
`cuenta_id`, universo ≥ 1 €, `categoria` con el CASE y orden de `v_cuadre_proveedor`. Medido: 64
cuentas (20 CUADRA, 20 CONTABILIDAD_MAYOR, 3 EFECTOS_MAYOR, 16 SIN_EFECTOS_VIVOS, 5 SIN_SALDO).
`COMMENT`: «MANDA LA CONTABILIDAD; la explicación por factura está en `ventas.retencion_cuenta`».

## 6. `ventas/06b_retencion_cliente.sql` [rev. 16-11, D10 b]

**Por qué tablas y no vistas (R34)**: `retenciones/01` hace `DROP TABLE retenciones.movimientos
CASCADE` cada noche; una vista de `ventas` encima desaparecería con cada `build-retenciones` hasta
el siguiente `build-ventas`. Como tablas, se reconstruyen en `build_ventas`, que corre después en
`run-all` (posición; el `depends_on` sigue `ingest_raw` para que un fallo de `retenciones` no salte
`ventas`: precedente de `build_retenciones_step.py`). Si `retenciones` falló esa noche, leen la de
la anterior, y `R-FRESCURA` lo dice. **Guarda R33**, antes de ningún `DROP`: `to_regclass
('retenciones.v_cuadre_cliente')` y la columna `origen_retencion` en `information_schema`; si
falta, `RAISE EXCEPTION` con los dos nombres. Va antes de `07_guardas.sql`, que así ve sus columnas.

**`ventas.retencion_factura`** (R27-R30), PK `factura_id`. CTE `retencion`: Σ `raw.dvfrec.cuo` por
factura de los recargos cuya `cueide` está en `retenciones.cuentas_cliente` (D12 = a), y su cuenta
(medido: ningún recargo reparte en dos cuentas). CTE `efectos`: `retenciones.movimientos` CLIENTE
por `documento_id`, `SUM(importe)` total y `FILTER` por `estado` (VIVA, LIQUIDADA, BAJA →
`efectos_agrupada`). Unión con `ventas.facturas` (factura, cliente, obra, `retencion_garantia`,
`retencion_retesp`), universo y `motivo` de R27-R28. `cuenta_id` = la del recargo, si no, la del
efecto. Casteos a `NUMERIC` sin `ROUND`. Ninguna columna lleva al AGR (D11).

**`ventas.retencion_cuenta`** (R31), PK `cuenta_id`: `retenciones.v_cuadre_cliente` `FULL JOIN`
las sumas de `retencion_factura` por cuenta, más `viva_sin_factura` (`movimientos` CLIENTE `VIVA`
con `documento_id` NULL) y `cliente_id` de `cuentas_cliente`. `diferencia_sin_explicar` es NULL en
`CUADRA` porque allí las facturas antiguas sin efecto, cobradas por asiento, no explican nada
(medido: 43 cuentas cuadradas tendrían 5,18 M de «resto» espurio). Medido en las 44 que
descuadran: 22 quedan explicadas al euro y la diferencia pasa de 9,47 M a 4,94 M en valor absoluto.

**`ventas.v_retencion_cliente`** (R32): VISTA sobre las dos tablas de `ventas` (sin dependencia de
`retenciones`), por `cliente_id`: importes por `motivo` y Σ de `retencion_cuenta` de sus cuentas.
Una cuenta `PREFIJO_43X8` no tiene cliente y queda solo por cuenta (UNEXUM: +947.835,66 en
4338001593 y −947.835,66 en 4308001593, que sí es suya: el cliente lo ve como diferencia propia).

**Permisos (R35)**: `ventas` la leen el perfil estándar y el total por los privilegios por defecto
de `02_roles.sql`; restringido y postventa no la ven, y los dos que la ven ya leen `retenciones`:
la copia no amplía nada. Verificación MANUAL con `has_table_privilege` (T10).

## 7. Tests, mutación y riesgos

Mapa completo requisito → test en `design_detalle.md` §3. Sobre el texto compacto del SQL y del
diccionario, sin red ni base. Puntos clave: el CASE de estado de CLIENTE = el de PROVEEDOR (R1);
`cuentas_cliente` antes de `CREATE TABLE retenciones.movimientos` (R4, R5); el `OR` del universo
(R6); `06b` no nombra `reccla` ni `fn_clase_recargo` ni `fecbaj`/`fecrea`/`est` (R29, R30); sus
objetos son `CREATE TABLE` salvo la vista de R32 (R34); `06b` va entre `06` y `07` en `SUB_PASOS`.

Mutación (rigor `estandar`, arnés 1.10.1): INFORMATIVA y muestreada, sin análisis obligatorio de
supervivientes; objetivo, el CASE de estado, los filtros de universo y el CASE de `motivo`.

**Riesgos**: (1) la cifra de cliente de `v_pbi_*` y del MCP baja de golpe (22,4 → 10,5 M): nota de
versión. (2) Las filas AGR/DIV no tienen tipo: quien filtre por `tipo_id` las pierde; lo dice la
ficha. (3) F-160 y F-099 también suben la `version`: la toma quien llegue antes (R18). (4) Desde
F-163, `raw` es incremental entre semana: afecta igual al saldo y a `contabilidad.mayor`, y el
cuadre de R20 no se rompe. (5) **[rev. 16-11]** Si Juan Romero cambia la D4 de F-040 (RETESP como
garantía), con D12 = a no cambia nada de `retencion_factura` salvo las dos columnas informativas.

## 8. Frontera

**¿Cruza la frontera del proyecto? No en lo técnico**: ningún endpoint, base ni recurso compartido
cambia; solo se lee `raw`. **Sí en lo publicado**: `retenciones` (Power BI y MCP) gana tres
objetos y cambia la cifra de CLIENTE, y `ventas` gana tres. Se actualiza
`azure-apps/datamart_seg_anual.md` (R19). `retenciones` ya está en la lista blanca de `mcp-bbdd`;
`ventas` no (su F-034, fuera de este repo): la IA no verá la conciliación hasta entonces.

## 9. Decisiones y revalidación 2026-11-16

| Decisión | Opciones | Recomendado | Decidido |
|---|---|---|---|
| D1 estado de CLIENTE | (a) precedencia de F-094; (b) solo `fecrea` | (a) | (a), humano 2026-11-07 |
| D2 dinero agrupado | (a) efectos `retide = 0` de las cuentas, con `origen_retencion`; (b) no | (a) | (a), humano 2026-11-07 |
| D3 universo de cuentas [rev. 16-11] | (a) unión `cueretide` ∪ 43x8 con `criterio_seleccion` y `cliente_id`; (b) solo `cueretide` (pierde UNEXUM 0,95 M); (c) solo prefijo | (a) | (a), humano 2026-11-16 |
| D4 fuente que manda | (a) la contabilidad; (b) los efectos | (a) | (a), humano 2026-11-07 |
| D5 obra del saldo contable | (a) fuera; (b) repartir | (a) | (a), humano 2026-11-07 |
| D6 la retención pendiente de F-150 | ¿ESPACIO PROMOCIÓN VIII, 0686? (hoy 1,74 M de saldo, 0,62 M en efectos) | sí | sí (0686), humano 2026-11-07 |
| D7 caja de F-150 con la retención sin efecto | (a) fuera, hipótesis nueva; (b) dentro | (a) | (a), humano 2026-11-07 |
| D8 lista de descuadres | (a) a Administración (Juan Romero), ahora desde `ventas.retencion_cuenta` | (a) | (a), humano 2026-11-07 |
| D9 `entidad_cif` de CLIENTE [nueva] | (a) NULL, el CIF por `ventas.clientes`; (b) de `cli.cif` (pasa a `critico`) | (a) | (a), humano 2026-11-16 |
| D10 conciliación por FACTURA [nueva] | (a) feature aparte; (b) dentro, en `ventas` | (a) | **(b)**, humano 2026-11-16 |
| D11 lo cobrado por un AGR [nueva] | (a) explicar, no atribuir; (b) atribuir por (cuenta, fecha de baja) | (a) | (a), humano 2026-11-16 |
| **D12 qué retención de la factura se concilia [nueva, 16-11]** | (a) los recargos de `dvfrec` que van a una cuenta de `cuentas_cliente`, sea cual sea su clase (lo que ve la contabilidad); garantía y RETESP de `ventas.facturas` como columnas informativas; (b) garantía + RETESP de `ventas.facturas`; (c) solo la garantía de `ventas.facturas` (clases 4 y 5, D4 provisional de F-040) | (a) | |

**D12, el dato**: los tres mayores descuadres (ESPACIO 0686, LEVITT, MK MADRID II) llevan la
retención como RETESP (clase 1, «Retención 5% garantía (sin iva)»), contra 4308, y su suma es
EXACTAMENTE el saldo de cada cuenta. Hay 1.067 recargos RETESP a cuentas de retención (17,71 M);
con (a), 1.114 facturas sin efecto (17,78 M, 17,50 de RETESP; 783 de 2024-2026). Con (c) quedan
fuera y no se explica ningún gran descuadre (sus 654 sin efecto son casi todas de 2008-2015). (b)
casi coincide con (a), pero suma 0,93 M de recargos que van a otras cuentas y depende de la D4 de
F-040, pendiente de Juan Romero. (a) sigue a la contabilidad (D4 de F-104) y no copia ni discute
la clasificación: la deja en `fn_clase_recargo`.

**Qué cambió desde el 06-11** (detalle y cifras viejas y nuevas: `progress/spec_F-104.md` §7-§12):
F-040 ingiere `raw.cli` (D3 se reabrió) y dejó tres promesas a F-104 (D9-D11);
`test_f040_frontera.py` protege `00_setup.sql` (`cuentas_cliente` va a `01`); diccionario v78;
arnés 1.10.1. Cifras: VIVA publicado 22,41 → 22,44 M; vivo real 10,50 → 10,53 M; saldo contable
15,49 → 16,00 M; 0686 1,68 → 1,74 M de saldo.
