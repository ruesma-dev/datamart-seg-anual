<!-- progress/spec_F-056.md -->
# F-056 · Spec escrita (spec-author, 2026-09-26)

Rama `feature/F-056-mayor-plan-contable` (desde `main` 6e3fcb0), `sdd=true`,
rigor `critico`. La spec: `specs/F-056-mayor-plan-contable/` (requirements
140/150, design 205/250, 26 tareas T0-T25). **Pendiente de aprobación**: ocho
decisiones D1-D8, cuatro de ellas las que pidió el líder (D1-D4).

## Qué se propone

Esquema nuevo `contabilidad` y paso `build_contabilidad` (tras `build_personal`,
antes de `build_cierre`, `depends_on = ["ingest_raw"]`), que lee `raw` y el puente
`maestro.centros_coste`. Tres tablas:

- `contabilidad.plan_cuentas` — el plan FINANCIERO como árbol: 44.778 grupos
  (`con.tip = 16`) + 34.196 cuentas auxiliares (`cua`, `con.tip = 17`), de las 38
  empresas, con nivel 1-5, padre por prefijo dentro de la empresa, padre
  declarado aparte, ruta y ancestros. No es `maestro.cuentas_analiticas` (`caa`).
- `contabilidad.mayor` — una fila por apunte (2.166.701), con fecha del apunte y
  del asiento, empresa, cuenta, debe/haber/importe, clase del asiento
  (NORMAL, APERTURA, SALDO_INICIAL, CIERRE, REGULARIZACION), `importe_saldo`,
  `saldo_acumulado`, obra por `cenide` y tercero.
- `contabilidad.saldos_cuenta_mes` — cuenta × ejercicio × mes (~400.316 filas),
  con el importe partido por clase y el saldo a fin de mes.

## Hallazgos de esta sesión (solo lectura; `raw` de la nocturna del 26-09)

1. **La jerarquía no es la que dicen F-066 y las fichas de `raw`.** `con.tip = 16`
   son los GRUPOS (1-4 dígitos: 321 / 2.673 / 15.017 / 26.767 en las 38 empresas)
   y son exactamente la tabla `cug` de Sigrid (44.778, leída por `sigrid-api`); `cua`
   son `con.tip = 17`, todas de 10 dígitos y las únicas con apuntes. El árbol es
   de prefijos: el 100 % de los grupos de 2-4 dígitos tiene su prefijo en la misma
   empresa, y el `cug.padide` declarado coincide con el prefijo en 34.369 de
   34.369 pero falta en 10.088 grupos (22,5 %). `cua.padide`: 33.838 coinciden,
   6 difieren (empresas 12, 17, 18), 352 a 0.
2. **Fecha**: `apu.fec` = fecha del asiento (`con.fec`) en 2.166.404 de 2.166.701;
   las 297 distintas son de 2017 (apunte a fin de mes, asiento a día 1). Empresa de
   la cuenta = empresa del asiento en el 100 %.
3. **`apu.cla` es la clase del apunte** (3 cierre, -1 apertura, 1 regularización),
   pero los cierres de 2020 / aperturas de 2021 (8.960) y 290 regularizaciones
   vienen con 0, y 124 aperturas en mayúsculas escapan a un `LIKE` sensible. Con la
   regla combinada: apertura = cierre del año anterior en 52.409 pares, 2 no casan,
   1.433 apuntes de saldo inicial. Sobre los 49.505 apuntes de F-095 la regla
   general da **0 diferencias** con la suya.
4. **Descuadres**: 3 asientos de 788.047 (224,52 €), para F-064. 294 apuntes con
   `cueide = 0`, todos de importe cero. 281 asientos sin apuntes.
5. **Obra por `cenide`** por grupo del PGC: 6 → 90,3 %; 7 → 61,4 %; 4 → 46,8 %;
   5 → 24,5 %; 1-3 → casi nada. **Tercero** (`empide`): 47,5 % de los apuntes,
   998.686 a proveedor (`con.tip = 5`).
6. **`apa` es el mayor analítico**: cuenta de `caa` en el 99,98 %; 629.982 filas
   (88 %) cuelgan de un apunte; 83.587 de un asiento analítico (`con.tip = 32`)
   sin apunte financiero. En cuentas de contrapartida de recursos: 167.135 filas y
   826 cuentas (lo de F-061).
7. **Caso testigo**: `1-4308000197` = AHORRAMAS, S.A., Retenciones (id 573009,
   padre 4308): 641 apuntes 2009-2026, debe = haber en cada ejercicio cerrado,
   apertura 2026 de 727.529,01, saldo 1.189.275,13. Sumando sin quitar los
   cierres: 7.742.538,38.
8. **Contra Sigrid**: subcuenta 434 (empresa 1) en 2026, saldo **5.345.557,80,
   idéntico** a la captura de Juan del 03-09. La 4308 hasta el 03-09 da 13.477.094,78
   de debe frente a 13.370.618,23 de la captura (+106.476,55 igual en debe y saldo:
   apuntes con fecha anterior dados de alta después de la captura).

## Volumen y coste

- Por empresa (apuntes, años): 1 → 1.948.503 (2008-2026); 28 → 26.775; 10 →
  24.252 (hasta 2016); 27 → 23.611; 13 → 19.534; 6 → 18.136 (hasta 2018)… 38
  empresas; 23 con apuntes en 2025-2026; las 15 restantes, 79.792 (3,7 %).
- Por ejercicio: de 47-73 k (2008-2016) a 196.991 en 2025; 154.324 en 2026 a 25-09.
- `raw.apu` ocupa 500 MB y solo tiene su PK. El SELECT completo del mayor (con
  asiento, cuenta, tercero y centro→obra) mide **18,8 s** en `EXPLAIN ANALYZE`,
  sin escribir. Una cuenta sobre `raw` en caliente: 0,6-1,7 s. Base: 27 GB de 64.
- Nocturna del 26-09: 00:00 → 04:07 UTC (`build_cierre` 44 min, `build_retenciones`
  2,8 min). SKU del servidor no verificado hoy (la memoria lo daba en B2s con
  bajada a B1ms pendiente): el implementer lo anota en T22.

## Decisiones abiertas (el detalle y las alternativas, en `design.md`)

- **D1 · Alcance por empresa**: recomendado las 38 con historia desde 2008.
- **D2 · Materializar o vista**: recomendado materializar (tabla); estimado 2-5
  min por noche y ~0,9 GB.
- **D3 · Objetos de consumo**: recomendado `plan_cuentas` + `mayor` +
  `saldos_cuenta_mes`; la vista de saldos por nodo del árbol, a F-058.
- **D4 · `apa`**: recomendado fuera, a F-061 (los movimientos de las cuentas de
  contrapartida son `apa`); el enlace `apa.apuide` → `mayor.apunte_id` queda listo.
- **D5 · Esquema nuevo `contabilidad`**: exige añadirlo a la lista blanca de
  `mcp-bbdd` (otro repositorio, despliegue de su imagen). Si no, el MCP no lo ve.
- **D6 · Fecha**: publicar las dos (`fecha` = `apu.fec`, `fecha_asiento` por los
  dos saltos). Se propone reformular el criterio 2 de la ficha con la cifra 297.
- **D7 · Árbol por prefijo, sin ingerir `cug`**.
- **D8 · Convergencia con F-095** (que `retenciones` lea la clase de
  `contabilidad.mayor`): ficha aparte, no aquí.

## Consultas de verificación (T23; solo lectura, contra la base del build)

- **C1** `SELECT count(*), min(fecha), max(fecha), sum(importe_saldo) FROM
  contabilidad.mayor WHERE empresa_id = 1 AND codigo_cuenta = '4308000197';`
  → 641 / 2009 / 2026 / 1.189.275,13 (a 26-09; se remide).
- **C2** `SELECT sum(importe) FROM contabilidad.mayor m JOIN contabilidad.plan_cuentas p
  USING (cuenta_id) WHERE p.empresa_id = 1 AND p.codigo_cuenta LIKE '434%' AND
  m.ejercicio = 2026 AND m.clase_asiento <> 'CIERRE';` → 5.345.557,80.
- **C3** `SELECT (SELECT count(*) FROM contabilidad.mayor) = (SELECT count(*) FROM raw.apu);`
- **C4** `SELECT cuenta_id FROM (SELECT cuenta_id, sum(importe_saldo) s FROM
  contabilidad.mayor GROUP BY 1) a FULL JOIN (SELECT cuenta_id, sum(importe_saldo)
  s FROM contabilidad.saldos_cuenta_mes GROUP BY 1) b USING (cuenta_id) WHERE
  a.s IS DISTINCT FROM b.s;` → 0 filas.

## Correcciones que la implementación deja hechas en otras fichas

- `raw.asi` y `raw.apu` dicen que fechar un apunte exige dos saltos: falso.
- `raw.cua` dice que la jerarquía vive en `con` tipo 16 y `cua` extiende
  «nivel 5 frente a nivel 0»: los grupos son tipo 16, las auxiliares tipo 17.
- El criterio 2 de la ficha de F-056 (dos saltos) queda cubierto por D6.

Scripts de medición (solo lectura): scratchpad de la sesión, `q.py` (Postgres con
`default_transaction_read_only`) y `s.py` (`sigrid-api`, `leer_sql`).
