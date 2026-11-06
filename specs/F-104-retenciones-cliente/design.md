# F-104 · La retención de CLIENTE saneada — diseño

Mediciones y casos: `progress/spec_F-104.md`. Requisitos: `requirements.md` (R1-R22).

## 1. Encaje y límite

Todo vive en el esquema `retenciones`, en el paso `build_retenciones` que ya existe (capa
infraestructura, SQL puro sobre `raw` + `maestro.centros_coste`). No hay lógica de dominio nueva:
el estado es el mismo CASE de F-094 que ya está en dos sitios (`01_movimientos.sql` PROVEEDOR y
`tesoreria/01_efectos_completo.sql`). Nada sale del límite del ETL: no se toca `sigrid-api` ni
otros proyectos, y solo se lee Sigrid por la ingesta de siempre.

**`retenciones` corre antes que `contabilidad` en `run-all`**: por eso el saldo se lee de
`raw.apu` y `raw.con` (como `03_apuntes_contables.sql`), nunca de `contabilidad.mayor`.

## 2. Ficheros

**Modificar**
- `etl_sigrid/infrastructure/postgres/sql/retenciones/00_setup.sql`: crea
  `retenciones.cuentas_cliente` (R4) y la guarda R5 (`DO $$ ... RAISE EXCEPTION`). Va en el setup
  porque `01` la necesita y es un catálogo, como `retenciones.tipos`.
- `.../retenciones/01_movimientos.sql`: rama CLIENTE (R1, R2, R6, R7), columnas nuevas en las dos
  ramas (R7, R8), cabecera reescrita en su apartado CLIENTE (R3), `COMMENT ON TABLE` al día e
  índice `idx_ret_mov_cuenta` sobre `(sentido, cuenta_id)`.
- `etl_sigrid/application/steps/build_retenciones_step.py`: sub-paso nuevo `saldo_cliente`
  (fichero `08_saldo_cliente.sql`, `target_schema="retenciones"`,
  `target_table="saldo_contable_cliente"`), el ÚLTIMO de `SUB_PASOS`, y la línea del docstring.
- `config/diccionario/retenciones.yaml`: fichas (R16).
- `config/diccionario/00_global.yaml`: orden de magnitud de CLIENTE (R17), `version` + nota (R18).
- `tests/test_f094_retenciones_estado.py`: `test_f094_cliente_conserva_el_estado_por_fecrea` deja
  de ser cierto. Se SUSTITUYE por su contrario en el fichero nuevo y aquí se borra con una línea
  en el docstring que apunte a F-104 (no se relaja en silencio).
- Los tests que enumeran sub-pasos o tablas de `retenciones` (`tests/test_f047_steps.py` y los
  que salgan al ejecutar la suite): el sub-paso nuevo.
- `../azure-apps/datamart_seg_anual.md` (R19): commit local en ese repositorio, sin push.

**Crear**
- `.../retenciones/08_saldo_cliente.sql`: `saldo_contable_cliente` y `v_cuadre_cliente`.
- `tests/test_f104_retenciones_cliente.py`: tests sobre el TEXTO del SQL y del diccionario, como
  `test_f094_*` y `test_f095_*` (sin red ni base).

**NO se tocan**: `02_views.sql` (R15), `03`-`07` (proveedor y fin de obra), todo `tesoreria/`
(R14), `config/tables_sigrid.yaml` (no se ingiere nada: `raw.cli` es de F-040), el dominio.

## 3. `00_setup.sql`: `retenciones.cuentas_cliente`

```sql
DROP TABLE IF EXISTS retenciones.cuentas_cliente CASCADE;
CREATE TABLE retenciones.cuentas_cliente AS
SELECT cue.ide AS cuenta_id, cue.cod AS codigo_cuenta, cue.res AS nombre_cuenta,
       LEFT(cue.cod, 4) AS familia, 'PREFIJO_43X8'::VARCHAR(16) AS criterio_seleccion
FROM raw.con cue
WHERE cue.tip = 17 AND cue.cod ~ '^43[0-9]8';
ALTER TABLE retenciones.cuentas_cliente ADD PRIMARY KEY (cuenta_id);
```

**`tip = 17`, no 16**: las cuentas imputables (las que llevan apuntes y efectos, p. ej. 1025308
«4308001150 FUNDACION TERTIO MILLENNIO, Retenciones») son `tip 17`; con `tip 16` (niveles
superiores) salen 0 cuentas con apuntes, medido. La cabecera de `03` dice «tip 16» y no filtra por
`tip` (une por `ide`): no se toca, pero no se copia. Sin filtro de «con apuntes»: un `EXISTS`
sobre `raw.apu` tardó más de 120 s en Azure, y una cuenta sin movimiento no suma nada.
Guarda R5 justo después: `IF NOT EXISTS (SELECT 1 FROM retenciones.cuentas_cliente) THEN RAISE
EXCEPTION 'retenciones.cuentas_cliente vacia: ...'`. Medido: 220 cuentas, 165 con apuntes (160
4308, 2 4328, 3 4338), 212 con «Retenc» en el nombre.

**Por qué prefijo, contra la regla R1 de F-095** («nunca por prefijo»): en proveedor existe
`prv.cueretide`; en cliente su gemelo `cli.cueretide` vive en `raw.cli`, que NO se ingiere (F-040).
Las alternativas medidas son peores: las cuentas de los efectos con `retide <> 0` mezclan 4300 y
5540 y dejan fuera 70 cuentas 4308 con 8,96 M. De las 165 cuentas 43x8 con apuntes, 162 se llaman
«…, Retenciones» (las otras 3 suman 926,88 €). `criterio_seleccion` y el `COMMENT` dicen que es
provisional: cuando F-040 ingiera `cli`, se cambia a `cli.cueretide` (D3) y la diferencia medida
(~1,03 M el 22-09) se declara. Que la `cuenta_id` de una cuenta 43x8 la compartan varios clientes
no rompe nada aquí: la clave es la cuenta, no el cliente.

## 4. `01_movimientos.sql`: la rama CLIENTE

- Estado (R1), idéntico al de PROVEEDOR:
  `CASE WHEN COALESCE(efe.fecbaj,0) <> 0 OR efe.est IN (14,15) THEN 'BAJA' WHEN
  COALESCE(c.fecrea,0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' ELSE 'VIVA' END`.
- `vencida_sin_liquidar` (R2): la condición de VIVA completa (fecrea, fecbaj, est), como PROVEEDOR.
- Universo (R6): `WHERE COALESCE(c.retide,0) <> 0 OR c.cueide IN (SELECT cuenta_id FROM
  retenciones.cuentas_cliente)`. Las filas que entran por la cuenta llevan `tipo_id` NULL y
  `tipo_descripcion` NULL (el `LEFT JOIN retenciones.tipos` ya lo da con `retide = 0`: usar
  `NULLIF(c.retide, 0)` en `tipo_id`).
- `origen_retencion` (R7): `CASE WHEN COALESCE(c.retide,0) <> 0 THEN 'EFECTO_RETENCION' ELSE
  'CUENTA_RETENCION' END::VARCHAR(16)`; en PROVEEDOR, el literal `'EFECTO_RETENCION'`.
- `cuenta_id` (R8): `NULLIF(c.cueide, 0)` y `NULLIF(p.cueide, 0)`.
- **Las columnas nuevas van AL FINAL de cada rama**, en el mismo orden en las dos (UNION ALL por
  posición), para no mover las que ya consumen Power BI y el MCP.
- Obra: sin cambios. Los efectos AGR/DIV llevan `cenide` (99,99 % con obra, §5 de mediciones); el
  fallback por líneas de venta sigue dependiendo de `v_src_lineas_venta` (vacía hasta F-040).
- El `test_f094` exige UN solo `UNION ALL`: se mantiene (el universo crece con un `OR` en el
  `WHERE`, no con una tercera rama).

Cifras esperadas (06-11): CLIENTE pasa de 2.254 filas a 3.458 (+1.204 efectos `retide = 0` de
las cuentas 43x8: AGR, DIV y efectos sin tipo, en cualquier estado). VIVA CLIENTE 22,41 M →
10,50 M; de ellos `EFECTO_RETENCION` 2,37 M.

## 5. `08_saldo_cliente.sql`

**`retenciones.saldo_contable_cliente`** (R11), una fila por cuenta. Un CTE `apuntes` sobre
`raw.apu JOIN retenciones.cuentas_cliente`, `importe = deb - hab` (signo de activo: la cuenta 43x8
crece por el debe, al revés que la 4008 de proveedor), y la clase con las mismas reglas y el mismo
orden que `03` (concepto `'Asiento de cierre%'` → CIERRE; `'Asiento de apertura%'` sin cierre de
la cuenta el ejercicio anterior → SALDO_INICIAL; con cierre → APERTURA; resto ALTA si > 0, BAJA si
≤ 0). Se REPLICA el CASE, no se lee de `apuntes_contables` (esa tabla es solo de proveedor y
cambiarle el grano tocaría `04`-`07`). Columnas como `saldo_contable` sin obra: `cuenta_id` (PK),
`codigo_cuenta`, `nombre_cuenta`, `familia`, `altas`, `bajas`, `saldo_inicial`, `saldo`,
`saldo_anterior_2016`, `num_apuntes`, `primer_movimiento`, `ultimo_movimiento`. Medido: Σ saldo =
15.485.863,29 € (debe cuadrar al céntimo con `contabilidad.mayor` de esas cuentas: R20).

**`retenciones.v_cuadre_cliente`** (R12, R13): `FULL JOIN` de `saldo_contable_cliente` con
`SELECT cuenta_id, SUM(importe), COUNT(*) FROM retenciones.movimientos WHERE sentido = 'CLIENTE'
AND estado = 'VIVA' GROUP BY cuenta_id`, universo `|saldo| >= 1 OR |viva| >= 1`, `categoria`
con el mismo CASE y orden que `v_cuadre_proveedor`. Columnas: `cuenta_id`, `codigo_cuenta`,
`nombre_cuenta`, `saldo_contable`, `viva_efectos`, `num_efectos_vivos`, `diferencia`
(contable − efectos), `categoria`. Una `viva` en una cuenta que no está en `cuentas_cliente` (un
efecto con `retide` en una 4300) sale con `codigo_cuenta` del `raw.con` y saldo 0: se ve, no se
pierde. Medido por cuenta (§3 de mediciones): 121 CUADRA, 25 descuadran, 14 solo saldo, 5 solo
efectos.

`COMMENT ON` en las dos, con «MANDA LA CONTABILIDAD; la lista de descuadres es para
Administración».

## 6. Tests (`tests/test_f104_retenciones_cliente.py`, sin red ni base)

Sobre el texto compacto del SQL (helpers como en `test_f094_retenciones_estado.py`):
- R1: el CASE de estado de la mitad CLIENTE es el de la mitad PROVEEDOR con `c.` por `p.`
  (comparar normalizado: matar a la vez «quitar fecbaj», «quitar est 10» y «BAJA tras LIQUIDADA»).
- R2: `vencida_sin_liquidar` de CLIENTE contiene `fecbaj` y `NOT IN (10, 14, 15)`.
- R3: la cabecera nombra `est 1`, `fecbaj`, `AGR` y `57.973,72`.
- R4/R5: `00_setup.sql` crea `cuentas_cliente` con `tip = 17`, `'^43[0-9]8'`, PK y la guarda
  `RAISE EXCEPTION` que la nombra, DESPUÉS del `CREATE`.
- R6/R7/R8: la mitad CLIENTE filtra `retide <> 0 OR ... cuentas_cliente`; las dos mitades terminan
  con `origen_retencion` y `cuenta_id` en el mismo orden; PROVEEDOR lleva el literal.
- R10: la PK sigue siendo `(sentido, movimiento_id)`.
- R11: `08` usa `deb - hab`, las cinco clases en orden, no lee `contabilidad.` ni
  `apuntes_contables`, y `saldo` suma solo ALTA, BAJA y SALDO_INICIAL.
- R12/R13: la vista lee `estado = 'VIVA'` de `movimientos`, `FULL JOIN`, las cinco categorías en
  orden, y no nombra `fecbaj`, `fecrea` ni `est`.
- R14/R15: `02_views.sql` y `tesoreria/` sin cambios respecto de `main` (huella del texto o
  `git diff --quiet` en la verificación de la tarea, no en el test).
- Paso: `SUB_PASOS` termina en `saldo_cliente` / `08_saldo_cliente.sql` / `saldo_contable_cliente`.
- R16-R18: fichas presentes de las tres tablas/vistas y columnas nuevas; ninguna ficha de CLIENTE
  dice «SIN VERIFICAR»; ningún orden de magnitud vale 21.900.000; `version` = la de `main` + 1.

Mutación (rigor `estandar`): los mutantes naturales son los del CASE de estado y del filtro de
universo; los tests de R1 y R6 deben matarlos. Si `harness.mutacion` no muta SQL, mutación manual
documentada como en F-158.

## 7. Riesgos, decisiones y fuera de alcance

**Decisiones para el humano** (recomendada marcada; detalle en `progress/current.md`):
- **D1** estado de CLIENTE: **A (recomendada)** la precedencia de F-094/`R-TESORERIA-ESTADO`,
  porque el mecanismo es el mismo (agrupación) aunque se registre con `est 1`; B dejarlo por
  `fecrea` (publica 19,93 M agrupados como vivos: descartada).
- **D2** el dinero agrupado: **A (recomendada)** meter en `movimientos` los efectos `retide = 0` de
  las cuentas de retención con `origen_retencion`; B no meterlos (VIVA quedaría en 2,37 M y faltaría
  el 77 % de lo vivo de la cartera: AGR24/0005, DIV20/0010...).
- **D3** universo de cuentas: **A (recomendada)** prefijo 43x8 ya, provisional, y pasar a
  `cli.cueretide` cuando F-040 ingiera `cli` (tarea para F-040); B esperar a F-040 (F-104 quedaría
  bloqueada); C ingerir `cli` aquí (pisa a F-040, que la redacta otro spec-author).
- **D4** fuente que manda: **A (recomendada)** la contabilidad (`saldo_contable_cliente`), como
  F-095 en proveedor; los efectos son el detalle y llevan la obra. B los efectos.
- **D5** obra del saldo contable: **fuera (recomendado)**; las altas casan con `raw.dvf` en el 70 %
  pero los cobros casi nunca llevan obra y repartirlos sería inventar. La obra de lo vivo sale de
  los efectos.
- **D6** confirmar que la «retención de 1,68 M€ de cliente pendiente de F-150» es la de ESPACIO
  PROMOCIÓN VIII (0686): saldo 1.679.407,38 frente a 622.160,33 en efectos. No hay rastro escrito
  en el repositorio; se identifica por el importe. Con F-104 la caja de F-150 sigue leyendo la
  cartera (`tesoreria.efectos`): esa diferencia la ve `v_cuadre_cliente`, no la caja (D7).
- **D7** ¿la receta de caja de F-150 debe sumar la retención contable sin efecto? **Fuera
  (recomendado)**: es una hipótesis de caja nueva (`R-CAJA-HIPOTESIS`), con su feature.
- **D8** la lista de descuadres (ESPACIO, LEVITT, MK MADRID II, ARCHER, SABINA, UNEXUM...) se
  entrega a Administración (Juan Romero) como en F-095 H7.

**Qué necesita de F-040**: `raw.cli` (para D3-A definitivo y el CIF de `entidad_cif`, hoy NULL) y
`raw.dvfpro` (para que `v_src_lineas_venta` deje de estar vacía: solo afecta a 16 efectos, 926,88 €,
sin centro). **F-104 puede ir sin F-040**: nada de lo que entrega depende de ella.

**Riesgos**: (1) `v_pbi_retencion_*` y el MCP cambian de cifra de cliente de golpe (22,4 → 10,5 M):
lo avisa la nota de versión. (2) Las filas AGR/DIV no tienen tipo de retención: quien filtre por
`tipo_id` las pierde; lo dice la ficha. (3) Un AGR de una cuenta 43x8 que agrupe efectos de varias
facturas no tiene documento (`documento_id` NULL): correcto, Sigrid no guarda el vínculo.
(4) Coordinar la `version` del diccionario con F-040 si se implementan a la vez.

**Fuera**: vencimiento de la retención de cliente desde el fin de obra (feature propia si se
pide); corregir datos en Sigrid; cambiar `tesoreria`.
