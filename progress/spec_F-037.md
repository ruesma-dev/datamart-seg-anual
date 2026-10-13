<!-- progress/spec_F-037.md -->
# F-037 · Informe del spec-author (fase 1: la cartera de cobros y pagos)

Fecha: 2026-10-13. Rama `feature/F-037-tesoreria` desde `main` (`41b40f7`). Spec en
`specs/F-037-tesoreria/` (requirements 149 líneas, design 247, tasks 17 tareas).

Todas las cifras salen de lecturas de SOLO LECTURA contra Azure
(`main._get_pg()`, `_bootstrap_done = True`, `filas_solo_lectura`), sobre la nocturna del
2026-10-13. Solo agregados: ni nombres, ni NIF, ni identificadores de personas.

## 1. Mediciones

### Volumen y bajas
| | efectos | de baja (`con.fecbaj <> 0`) | `con.tip` del efecto |
|---|---|---|---|
| `raw.pag` | 256.952 | 89.779 (34,9 %) | 25 en todos |
| `raw.cob` | 21.914 | 8.548 (39,0 %) | 24 en todos |

`compras.vencimientos` hoy: 197.190 filas = los pagos cuyo documento origen es `con.tip = 15`
(factura de compra). Ocupa 60 MB. Base: 36 GB.

### Cómo se identifica un pago de personal (lo que pidió el humano)
- **`raw.auxnap` (naturaleza del pago) tiene tres filas: NOMINAS, EMBARGO, CUOTAS.** Es el
  identificador directo. `natide`: 0 → 219.899; NOMINAS 33.990; EMBARGO 3.062; CUOTAS 1.
- **Cuenta del efecto** (`cueide` → `con.cod`): 465 → 37.048 (todos con naturaleza), 475 → 3,
  466 → 1. Ningún 460, 461, 544 ni 640-649 en `pag`.
- **Tercero empleado** (`con.tip = 43` del `entide`; los 50 de `raw.emp` mirados son tip 43):
  33.991 efectos, todos con naturaleza.
- **Documento origen nómina** (`con.tip = 306`, códigos `NOaa…`, estados Generada/Cerrada):
  35.863 efectos, todos con naturaleza.
- **Cruce de los cuatro criterios**: el conjunto de cualquiera de ellos es EXACTAMENTE el de
  `natide <> 0`: **37.053 pagos** (32.807 cumplen los cuatro; 3.056 sin tercero empleado —
  los embargos, con tercero vacío—; 1.184 sin documento 306; 5 solo por naturaleza y cuenta;
  1 solo por naturaleza). Ningún pago fuera de ese conjunto cumple alguno.
- **Cobros**: 0 con naturaleza, 0 a tercero empleado, 0 en cuentas restringidas (todos 43x/554).
- Cuentas sin resolver: 0 (161 pagos y 60 cobros sin cuenta, `cueide = 0`).
- Importes del conjunto de personal: BAJA 11.107 (15,5 M€), REALIZADO 19.733 (34,9 M€),
  PREVISTO 6.213 (6,7 M€) con **0 vencimientos futuros**: la cartera futura no pierde nada al
  restringirlos; los 6.213 previstos son pagos de nómina pasados sin puntear.
- **Lo que se cuela** (D7 del design): 429 pagos, 1,08 M€, a 16 proveedores (tip 5) cuyo NIF
  coincide con el DNI de un empleado. Son facturas de compra; recomendado no restringirlos.
- **Remesas**: 3.921 con pagos; 997 solo de personal; **1 mixta** (2 efectos de nómina): su
  `importe_remesa` delataría esos dos (D8: a NULL en la general).

### Estado (criterio de F-094: BAJA > REALIZADO > PREVISTO)
| sentido | personal | BAJA | REALIZADO | PREVISTO | previsto con vencimiento futuro |
|---|---|---|---|---|---|
| PAGO | no | 78.672 (244,9 M€) | 127.677 (826,6 M€) | 13.550 (80,1 M€) | 7.933 (55,0 M€) |
| PAGO | sí | 11.107 | 19.733 | 6.213 | 0 |
| COBRO | — | 8.548 | 12.349 | 1.017 (40,2 M€) | 204 (18,9 M€) |

`est = 10` («Pagado»/«Cobrado») sin `fecrea`: 41.884 pagos (312,4 M€) y 2.106 cobros
(467,2 M€). Sin el `est` en el criterio, todos contarían como previstos.

**Contraste con la contabilidad general** (`contabilidad.mayor`, `importe_saldo`): saldo de
40+41 = −78,8 M€ frente a 80,1 M€ de PAGO previsto; saldo de 43 = +47,5 M€ frente a
40,2 M€ de COBRO previsto. **Con las bajas de cobro sumadas serían 385,4 M€**: en cobros la
baja también es fantasma en el conjunto. Excepción medida: cobros previstos CON retención,
2,2 M€ sin baja y 19,9 M€ de baja; F-094 vio 13,8 M€ en la contabilidad de retención de
cliente, así que ahí la baja puede no ser fantasma (declarado en D2, no resuelto).

### Obra, empresa, cobertura
- `cenide` informado: 201.791 pagos y 17.342 cobros; con obra por `maestro.centros_coste`
  (805 centros, 805 claves, sin ambigüedad): **200.143 pagos (77,9 %) y 17.102 cobros (78,0 %)**.
- Empresa (`con.emp` del efecto): 0 vacíos; 36 empresas en pagos, 26 en cobros.
- Documento origen: pagos 197.190 facturas de compra, 35.863 nóminas, 23.897 sin documento
  (22.707 no personales, 167,2 M€: pagos sueltos, nuevos para el datamart), 2 otros.
  Cobros: 20.420 con documento `tip = 11`, 1.493 sin documento. `raw.rco` NO se ingiere: las
  279 remesas de cobro solo tienen código (de `con`).
- 111.450 pagos traen cuenta bancaria del tercero: no se publica (R9).

### Coste en la ventana
- Nocturna del 13-10: **4 h 52 min** (292 min); `build_compras` 1.058 s,
  `build_retenciones` 227 s, `build_contabilidad` 1.087 s.
- La unión `pag ∪ cob` con todas las uniones del diseño: **278.866 filas en 2,0 s** (lectura).
- Estimado: **+1-3 min y +0,2 GB**. Se mide en el primer build manual (R29, T13).

## 2. Lo que la spec decide (opción recomendada en cada D del design §8)

D1 `tesoreria` tabla única y `compras.vencimientos` vista suya (0 personales en facturas de
compra) · D2 bajas publicadas y marcadas, mismo criterio en los dos sentidos, regla dura ·
D3 esquema propio `tesoreria_restringida` · D4 obra solo por el puente centro → obra ·
D5 cobros publicados ya con su cobertura declarada · D6 el estándar ve solo recuentos ·
D7 unión de los cuatro criterios + fallo cerrado; los 429 autónomos-empleados quedan
visibles · D8 `importe_remesa` NULL en la remesa mixta · D9 `build_tesoreria` delante de
compras sin `depends_on` · D10 nombres.

Hallazgo de diseño que condiciona D1: si `tesoreria.efectos` se recreara con `DROP ...
CASCADE` cada noche, se llevaría la vista `compras.vencimientos` y todo lo que cuelga de ella.
Por eso las tablas de `tesoreria` siguen el patrón de `personal` (`CREATE IF NOT EXISTS` +
`TRUNCATE` + `INSERT`, R14).

## 3. Decisiones abiertas que necesita validar el humano

1. **D1-D10** del design §8, en especial D2 (las bajas de cobro con retención), D3 (esquema
   propio frente a meterlo en `contabilidad_restringida`), D6 (solo recuentos para el
   estándar) y D7 (los 429 pagos a autónomos con NIF de empleado).
2. **Fuera del repositorio**: `mcp-bbdd` tiene que añadir `tesoreria` a su lista blanca (y
   `tesoreria_restringida` a la conexión total) para que la IA la vea; aquí solo se escribe
   el contrato en `azure-apps/datamart_seg_anual.md`.
3. **Comprobar en el despliegue** que el job no fija `PG_*_SCHEMAS` en su entorno (design §7.1).
