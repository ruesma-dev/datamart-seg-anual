# F-104 · Detalle del diseño (SQL de referencia, columnas y mapa de tests)

Complemento de `design.md` (2026-11-16, D10 = b). Lo que aquí se fija es normativo para el
implementer; el porqué está en `design.md`.

## 1. `retenciones.cuentas_cliente` (al principio de `retenciones/01_movimientos.sql`)

```sql
DROP TABLE IF EXISTS retenciones.cuentas_cliente CASCADE;
CREATE TABLE retenciones.cuentas_cliente AS
WITH declaradas AS (SELECT cl.cueretide::BIGINT AS cuenta_id, cl.ide AS cliente_id
                    FROM raw.cli cl WHERE COALESCE(cl.cueretide, 0) <> 0),
     prefijo AS (SELECT cue.ide AS cuenta_id FROM raw.con cue
                 WHERE cue.tip = 17 AND cue.cod ~ '^43[0-9]8')
SELECT COALESCE(d.cuenta_id, p.cuenta_id) AS cuenta_id, d.cliente_id,
       cue.cod AS codigo_cuenta, cue.res AS nombre_cuenta, LEFT(cue.cod, 4) AS familia,
       (CASE WHEN d.cuenta_id IS NOT NULL THEN 'CUERETIDE' ELSE 'PREFIJO_43X8' END)::VARCHAR(16)
           AS criterio_seleccion
FROM declaradas d FULL JOIN prefijo p ON p.cuenta_id = d.cuenta_id
LEFT JOIN raw.con cue ON cue.ide = COALESCE(d.cuenta_id, p.cuenta_id);
ALTER TABLE retenciones.cuentas_cliente ADD PRIMARY KEY (cuenta_id);
-- y después: DO $$ ... IF NOT EXISTS (SELECT 1 FROM retenciones.cuentas_cliente)
--            THEN RAISE EXCEPTION 'retenciones.cuentas_cliente vacia: ...'
```

## 2. Columnas de `ventas` (en este orden)

**`ventas.retencion_factura`** (PK `factura_id`): `factura_id`, `codigo_factura`,
`fecha_factura`, `cliente_id`, `nombre_cliente`, `obra_id`, `codigo_obra`, `cuenta_id`,
`retencion`, `retencion_garantia`, `retencion_retesp`, `efectos`, `num_efectos`, `efectos_viva`,
`efectos_liquidada`, `efectos_agrupada`, `diferencia`, `motivo` (`VARCHAR(24)`).
- `retencion` = Σ `raw.dvfrec.cuo::NUMERIC` con `cueide IN (SELECT cuenta_id FROM
  retenciones.cuentas_cliente)`, agrupado por `docide` (D12 = a).
- Efectos: `retenciones.movimientos` con `sentido = 'CLIENTE'` y `documento_id` = factura;
  `efectos_viva` / `_liquidada` / `_agrupada` = `SUM(importe) FILTER (WHERE estado = 'VIVA' |
  'LIQUIDADA' | 'BAJA')`. Sin efectos: `efectos` 0, `num_efectos` 0.
- Universo: `retencion <> 0 OR retencion_garantia <> 0 OR retencion_retesp <> 0 OR num_efectos > 0`.
- `motivo`: `CASE WHEN num_efectos = 0 AND retencion <> 0 THEN 'SIN_EFECTO' WHEN num_efectos > 0
  AND retencion = 0 THEN 'EFECTO_SIN_RETENCION' WHEN num_efectos > 0 AND abs(retencion - efectos)
  < 0.01 THEN 'CUADRA' WHEN num_efectos > 0 THEN 'DIFIERE' ELSE 'SIN_CUENTA_RETENCION' END`.

**`ventas.retencion_cuenta`** (PK `cuenta_id`): `cuenta_id`, `codigo_cuenta`, `nombre_cuenta`,
`cliente_id`, `criterio_seleccion`, `saldo_contable`, `viva_efectos`, `diferencia`, `categoria`
(las cuatro de `retenciones.v_cuadre_cliente`, 0 / NULL si la cuenta no está allí),
`retencion_facturas`, `retencion_sin_efecto`, `num_facturas_sin_efecto`, `viva_sin_factura`,
`diferencia_sin_explicar`.

**`ventas.v_retencion_cliente`** (una fila por `cliente_id`): `cliente_id`, `nombre_cliente`,
`num_facturas`, `retencion`, `efectos`, `retencion_sin_efecto`, `diferencia_facturas` (Σ
`diferencia` de DIFIERE y EFECTO_SIN_RETENCION), `saldo_contable`, `viva_efectos`, `diferencia`,
`viva_sin_factura`, `diferencia_sin_explicar` (estas cinco, Σ de `retencion_cuenta` con su
`cliente_id`).

## 3. Mapa requisito → test (sin red ni base)

| R | Fichero de test | Qué comprueba |
|---|---|---|
| R1, R2 | `test_f104_retenciones_cliente.py` | CASE de CLIENTE = el de PROVEEDOR con `c.`; `vencida_sin_liquidar` con `fecbaj` y `NOT IN (10, 14, 15)` |
| R3 | idem | la cabecera nombra `est 1`, `fecbaj`, `AGR`, `57.973,72` |
| R4, R5 | idem | `cuentas_cliente` antes de `CREATE TABLE retenciones.movimientos`; `cueretide`, `tip = 17`, `'^43[0-9]8'`, `FULL JOIN`, los dos literales, PK y `RAISE EXCEPTION` que la nombra |
| R6-R8, R10 | idem | `retide <> 0 OR ... cuentas_cliente`; las dos mitades terminan en `origen_retencion, cuenta_id`; PK |
| R11-R13 | idem | `deb - hab`, cinco clases en orden, sin `contabilidad.` ni `apuntes_contables`; la vista lee `estado = 'VIVA'` y no nombra `fecbaj`/`fecrea`/`est` |
| R14, R15, R24 | idem + `test_f040_frontera.py` | `TOCADOS_DESPUES` = los dos de F-104 + el de F-161; `git diff --quiet` en la tarea |
| R23 | idem | `NULL::VARCHAR(24) AS entidad_cif` en CLIENTE, sin `cli.cif`; la ficha nombra `ventas.clientes` |
| R27, R28 | `test_f104_ventas_retencion.py` | columnas en orden; el CASE de `motivo` con sus cinco valores en orden |
| R29, R30 | idem | lee `retenciones.movimientos` por `documento_id` y `estado`; no nombra `reccla`, `fn_clase_recargo`, `fecbaj`, `fecrea` ni `raw.cob` |
| R31, R32 | idem | `retencion_cuenta` lee `retenciones.v_cuadre_cliente`; `diferencia_sin_explicar` NULL en `CUADRA`; la vista solo lee `ventas.` |
| R33, R34 | idem + `test_f040_pipeline.py` | guarda con los dos nombres antes del primer `DROP`; dos `CREATE TABLE` y una `CREATE VIEW`; `06b` entre `06` y `07` en `SUB_PASOS`; `depends_on` sigue `["ingest_raw"]` |
| R35 | idem | ninguna columna empieza por un prefijo de `PREFIJOS_PROHIBIDOS_EN_VENTAS` ni contiene `cif` |
| R16-R18, R25, R26, R36 | los dos ficheros nuevos + `test_f040_diccionario.py` | fichas presentes; sin «SIN VERIFICAR» ni 21.900.000; `version` = `main` + 1; los textos de `ventas.yaml` y `ARCHITECTURE.md` nombran `retencion_factura` y siguen nombrando `F-104`, sin «hasta F-104» ni «lo explicara F-104» |
