# F-104 · La retención de CLIENTE saneada — diseño

**Rigor: `estandar`.** No cumple ningún disparador de `critico` (`CHECKPOINTS.md`, «Niveles de
rigor»): no escribe en producción ni en lo compartido (el build lo lanza la nocturna de siempre),
no trata datos personales (con D9 = a; con D9 = b pasaría a `critico` por el disparador 3) y no
cambia ningún contrato salvo añadir columnas al final, como F-094 (`estandar`).

Mediciones y casos: `progress/spec_F-104.md`. Requisitos: `requirements.md` (R1-R26).
**[rev. 16-11]** marca lo que cambia frente a la versión aprobada el 2026-11-07; el porqué, §9.

## 1. Encaje y límite

Todo vive en el esquema `retenciones`, en el paso `build_retenciones` que ya existe (capa
infraestructura, SQL puro sobre `raw` + `maestro.centros_coste`). No hay lógica de dominio nueva:
el estado es el mismo CASE de F-094 que ya está en dos sitios (`01_movimientos.sql` PROVEEDOR y
`tesoreria/01_efectos_completo.sql`). Nada sale del límite del ETL: no se toca `sigrid-api` ni
otros proyectos, y solo se lee Sigrid por la ingesta de siempre.

**`retenciones` corre antes que `ventas` y que `contabilidad` en `run-all`**: por eso las cuentas
salen de `raw.cli` (no de `ventas.clientes`) y el saldo de `raw.apu` y `raw.con` (como
`03_apuntes_contables.sql`), nunca de `contabilidad.mayor`. **[rev. 16-11]** F-162 no afecta:
nada nuevo agrega por `codigo_obra` y `maestro.centros_coste` no cambió.

## 2. Ficheros

**Modificar**
- `etl_sigrid/infrastructure/postgres/sql/retenciones/01_movimientos.sql`: **[rev. 16-11]** al
  principio, `retenciones.cuentas_cliente` (R4) y su guarda R5 (§3); rama CLIENTE (R1, R2, R6,
  R7), columnas nuevas en las dos ramas (R7, R8), cabecera de CLIENTE reescrita (R3), `COMMENT ON
  TABLE` al día e índice `idx_ret_mov_cuenta` sobre `(sentido, cuenta_id)`.
- `etl_sigrid/application/steps/build_retenciones_step.py`: sub-paso nuevo `saldo_cliente`
  (fichero `08_saldo_cliente.sql`, `target_schema="retenciones"`,
  `target_table="saldo_contable_cliente"`), el ÚLTIMO de `SUB_PASOS`, y la línea del docstring.
- `config/diccionario/retenciones.yaml`: fichas (R16, R23).
- `config/diccionario/00_global.yaml`: orden de magnitud de CLIENTE (R17), `version` + nota (R18).
- **[rev. 16-11]** `config/diccionario/ventas.yaml` (cabecera, `v_factura_cobro`,
  `cobertura_enlace`) y `docs/ARCHITECTURE.md` (frontera de `ventas`): R25, solo texto.
- **[rev. 16-11]** `config/tables_sigrid.yaml`: el comentario de `cob` (R26), solo el comentario.
- **[rev. 16-11]** `tests/test_f040_frontera.py`: `TOCADOS_DESPUES` + `01_movimientos.sql` y
  `08_saldo_cliente.sql`, con el motivo «F-104 (R4-R12)» (R24).
- `tests/test_f094_retenciones_estado.py`: `test_f094_cliente_conserva_el_estado_por_fecrea` deja
  de ser cierto. Se SUSTITUYE por su contrario en el fichero nuevo y aquí se borra con una línea
  en el docstring que apunte a F-104 (no se relaja en silencio).
- Los tests que enumeran sub-pasos o tablas de `retenciones` (`tests/test_f047_steps.py` y los
  que salgan al ejecutar la suite): el sub-paso nuevo.
- `../azure-apps/datamart_seg_anual.md` (R19): commit aparte allí, sin push (protocolo de `CLAUDE.md`).

**Crear**
- `.../retenciones/08_saldo_cliente.sql`: `saldo_contable_cliente` y `v_cuadre_cliente`.
- `tests/test_f104_retenciones_cliente.py`: tests sobre el TEXTO del SQL y del diccionario, como
  `test_f094_*` y `test_f095_*` (sin red ni base).

**NO se tocan**: **[rev. 16-11]** `retenciones/00_setup.sql` (lo protege `test_f040_frontera.py`,
y `cuentas_cliente` no lo necesita: va al principio de `01`), `02_views.sql` (R15), `03`-`07`,
todo `tesoreria/` (R14), el SQL de `ventas/` (sus comentarios ya apuntan a F-104, que es donde
queda la explicación), las tablas y columnas de la ingesta, el dominio.

## 3. `retenciones.cuentas_cliente`, al principio de `01_movimientos.sql` [rev. 16-11]

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
```

La PK es la guarda de «dos clientes, una cuenta» (R5): hoy 211 clientes y 211 cuentas distintas,
1:1 como en proveedor (`uq_ret_cuentas_proveedor_cuenta`); si Sigrid compartiera una, el sub-paso
falla aquí con el nombre de la tabla en vez de duplicar apuntes. Guarda de vacía justo después:
`IF NOT EXISTS (SELECT 1 FROM retenciones.cuentas_cliente) THEN RAISE EXCEPTION
'retenciones.cuentas_cliente vacia: ...'`. Ninguna es cuenta de retención de proveedor (0 medido).

**Por qué la unión (D3 = a)**: la regla de F-095 es que la cuenta la declara la entidad
(`cueretide`), y ya se ingiere (F-040). Pero solo con `cueretide` se pierde UNEXUM: su ficha
declara 4308001593 y su saldo, 947.835,66 €, está en 4338001593 («UNEXUM REAL ESTATE S.L.,
Retenciones»), que no declara nadie; el prefijo la recoge. A la inversa, 4 cuentas declaradas
están fuera de 43x8 (3 `5540` «retenciones suplidos» de UTE y 1 `4380` «Anticipos»), saldo 0.
`criterio_seleccion` dice por qué entra cada una, y la lista de `PREFIJO_43X8` con saldo es para
Administración (D8). **`tip = 17`, no 16**: las imputables son `tip 17` (todas las `cueretide`
también); `03` dice «tip 16» y no filtra por `tip`: no se toca, pero no se copia.

## 4. `01_movimientos.sql`: la rama CLIENTE

- Estado (R1), idéntico al de PROVEEDOR:
  `CASE WHEN COALESCE(efe.fecbaj,0) <> 0 OR efe.est IN (14,15) THEN 'BAJA' WHEN
  COALESCE(c.fecrea,0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' ELSE 'VIVA' END`.
- `vencida_sin_liquidar` (R2): la condición de VIVA completa (fecrea, fecbaj, est), como PROVEEDOR.
- Universo (R6): `WHERE COALESCE(c.retide,0) <> 0 OR c.cueide IN (SELECT cuenta_id FROM
  retenciones.cuentas_cliente)`. Las filas que entran por la cuenta llevan `tipo_id` NULL
  (`NULLIF(c.retide, 0)`) y `tipo_descripcion` NULL.
- `origen_retencion` (R7): `CASE WHEN COALESCE(c.retide,0) <> 0 THEN 'EFECTO_RETENCION' ELSE
  'CUENTA_RETENCION' END::VARCHAR(16)`; en PROVEEDOR, el literal `'EFECTO_RETENCION'`.
- `cuenta_id` (R8): `NULLIF(c.cueide, 0)` y `NULLIF(p.cueide, 0)`.
- `entidad_cif` (R23, D9 = a): sigue `NULL::VARCHAR(24)`; la rama no lee `cli.cif`.
- **Las columnas nuevas van AL FINAL de cada rama**, en el mismo orden en las dos (UNION ALL por
  posición), para no mover las que ya consumen Power BI y el MCP.
- Obra: sin cambios. **[rev. 16-11]** El respaldo por líneas ya está activo (`raw.dvfpro`, 29.285
  filas en `v_src_lineas_venta`) y hoy 0 filas CLIENTE quedan sin obra.
- El `test_f094` exige UN solo `UNION ALL`: se mantiene (el universo crece con un `OR`).

**[rev. 16-11]** Cifras esperadas (16-11): CLIENTE pasa de 2.256 filas a 3.461 (+1.205 efectos
`retide = 0` de las cuentas de `cuentas_cliente`, en cualquier estado). VIVA CLIENTE 22,44 M →
10,53 M; de ellos `EFECTO_RETENCION` 2,40 M.

## 5. `08_saldo_cliente.sql`

**`retenciones.saldo_contable_cliente`** (R11), una fila por cuenta. Un CTE `apuntes` sobre
`raw.apu JOIN retenciones.cuentas_cliente`, `importe = deb - hab` (signo de activo: la cuenta 43x8
crece por el debe, al revés que la 4008 de proveedor), y la clase con las mismas reglas y el mismo
orden que `03` (concepto `'Asiento de cierre%'` → CIERRE; `'Asiento de apertura%'` sin cierre de
la cuenta el ejercicio anterior → SALDO_INICIAL; con cierre → APERTURA; resto ALTA si > 0, BAJA si
≤ 0). Se REPLICA el CASE, no se lee de `apuntes_contables` (esa tabla es solo de proveedor y
cambiarle el grano tocaría `04`-`07`). Columnas: `cuenta_id` (PK), `codigo_cuenta`,
`nombre_cuenta`, `familia`, `altas`, `bajas`, `saldo_inicial`, `saldo`, `saldo_anterior_2016`,
`num_apuntes`, `primer_movimiento`, `ultimo_movimiento`. **[rev. 16-11]** Medido: Σ saldo =
16.002.697,94 € en 169 cuentas con apuntes (R20: al céntimo con `contabilidad.mayor`).

**`retenciones.v_cuadre_cliente`** (R12, R13): `FULL JOIN` de `saldo_contable_cliente` con
`SELECT cuenta_id, SUM(importe), COUNT(*) FROM retenciones.movimientos WHERE sentido = 'CLIENTE'
AND estado = 'VIVA' GROUP BY cuenta_id`, universo `|saldo| >= 1 OR |viva| >= 1`, `categoria`
con el mismo CASE y orden que `v_cuadre_proveedor`. Columnas: `cuenta_id`, `codigo_cuenta`,
`nombre_cuenta`, `saldo_contable`, `viva_efectos`, `num_efectos_vivos`, `diferencia`
(contable − efectos), `categoria`. Una `viva` en una cuenta fuera de `cuentas_cliente` sale con
`codigo_cuenta` de `raw.con` y saldo 0 (hoy ninguna). **[rev. 16-11]** Medido: 64 cuentas, 20
CUADRA, 20 CONTABILIDAD_MAYOR, 3 EFECTOS_MAYOR, 16 SIN_EFECTOS_VIVOS, 5 SIN_SALDO_CONTABLE.

`COMMENT ON` en las dos, con «MANDA LA CONTABILIDAD; la lista de descuadres es para
Administración».

## 6. Tests (`tests/test_f104_retenciones_cliente.py`, sin red ni base)

Sobre el texto compacto del SQL (helpers como en `test_f094_retenciones_estado.py`):
- R1: el CASE de estado de la mitad CLIENTE es el de la mitad PROVEEDOR con `c.` por `p.`
  (comparar normalizado: matar a la vez «quitar fecbaj», «quitar est 10» y «BAJA tras LIQUIDADA»).
- R2: `vencida_sin_liquidar` de CLIENTE contiene `fecbaj` y `NOT IN (10, 14, 15)`.
- R3: la cabecera nombra `est 1`, `fecbaj`, `AGR` y `57.973,72`.
- R4/R5 **[rev. 16-11]**: `01` crea `cuentas_cliente` ANTES de `CREATE TABLE
  retenciones.movimientos`, con `cueretide`, `tip = 17`, `'^43[0-9]8'`, `FULL JOIN`, los dos
  literales de `criterio_seleccion`, la PK y la guarda `RAISE EXCEPTION` que la nombra.
- R6/R7/R8: la mitad CLIENTE filtra `retide <> 0 OR ... cuentas_cliente`; las dos mitades terminan
  con `origen_retencion` y `cuenta_id` en el mismo orden; PROVEEDOR lleva el literal.
- R10: la PK sigue siendo `(sentido, movimiento_id)`.
- R11: `08` usa `deb - hab`, las cinco clases en orden, no lee `contabilidad.` ni
  `apuntes_contables`, y `saldo` suma solo ALTA, BAJA y SALDO_INICIAL.
- R12/R13: la vista lee `estado = 'VIVA'` de `movimientos`, `FULL JOIN`, las cinco categorías en
  orden, y no nombra `fecbaj`, `fecrea` ni `est`.
- R14/R15: `00_setup.sql`, `02_views.sql`, `tesoreria/` y `ventas/*.sql` sin diff contra `main`
  (lo vigila ya `test_f040_frontera.py` para los dos primeros; `git diff --quiet` en la tarea).
- R23: la mitad CLIENTE proyecta `NULL::VARCHAR(24) AS entidad_cif` y no contiene `cli.cif`; la
  ficha nombra `ventas.clientes`.
- R24: `TOCADOS_DESPUES` contiene exactamente los dos ficheros de F-104 más el de F-161.
- R25/R26: los tres textos de `ventas.yaml` y el de `ARCHITECTURE.md` no dicen «hasta F-104» ni
  «lo explicara F-104» y siguen nombrando `F-104`; el comentario de `cob` no dice «sin verificar».
- Paso: `SUB_PASOS` termina en `saldo_cliente` / `08_saldo_cliente.sql` / `saldo_contable_cliente`.
- R16-R18: fichas presentes de las tres tablas/vistas y columnas nuevas; ninguna ficha de CLIENTE
  dice «SIN VERIFICAR»; ningún orden de magnitud vale 21.900.000; `version` = la de `main` + 1.

**[rev. 16-11]** Mutación (rigor `estandar`, arnés 1.10.1): campaña INFORMATIVA y muestreada, sin
análisis obligatorio de supervivientes. Los mutantes naturales son los del CASE de estado y del
filtro de universo; los tests de R1, R4 y R6 deben matarlos. Si `harness.mutacion` no muta SQL,
mutación manual documentada como en F-158.

## 7. Riesgos y fuera de alcance

**Riesgos**: (1) `v_pbi_retencion_*` y el MCP cambian de cifra de cliente de golpe (22,4 → 10,5
M): lo avisa la nota de versión. (2) Las filas AGR/DIV no tienen tipo de retención: quien filtre
por `tipo_id` las pierde; lo dice la ficha. (3) Un AGR que agrupe efectos de varias facturas no
tiene documento (`documento_id` NULL): correcto, Sigrid no guarda el vínculo. (4) **[rev. 16-11]**
F-160 y F-099 van detrás y también suben la `version`: la toma quien llegue antes a `main` (R18
dice «`main` + 1» al implementar). (5) **[rev. 16-11]** Desde F-163 las noches de diario son
incrementales por `tiemod`: una fila borrada en Sigrid sigue en `raw` hasta la completa del fin de
semana; afecta igual a `saldo_contable_cliente` y a `contabilidad.mayor` (los dos leen `raw.apu`),
así que el cuadre de R20 no se rompe por ello.

**Fuera**: vencimiento de la retención de cliente desde el fin de obra; atribuir el saldo contable
a obra (D5); corregir datos en Sigrid; cambiar `tesoreria`; D9-D11 según se decidan.

## 8. Frontera

**¿Cruza la frontera del proyecto? No en lo técnico**: no cambia ningún endpoint, base ni
recurso compartido; solo lee `raw` de la ingesta de siempre. **Sí en lo publicado**: el esquema
`retenciones` que leen Power BI y el MCP (`mcp-bbdd`) gana tres objetos y cambia la cifra de
CLIENTE. Se actualiza `azure-apps/datamart_seg_anual.md` (R19). `retenciones` ya está en la lista
blanca de `mcp-bbdd`: no hay que tocar su `config.yaml`; sí reiniciarlo tras publicar el diccionario.

## 9. Decisiones y revalidación 2026-11-16

| Decisión | Opciones | Recomendado | Decidido |
|---|---|---|---|
| D1 estado de CLIENTE | (a) precedencia de F-094 / `R-TESORERIA-ESTADO`; (b) solo `fecrea` (19,93 M agrupados como vivos) | (a) | (a), humano 2026-11-07 |
| D2 dinero agrupado | (a) efectos `retide = 0` de las cuentas de retención con `origen_retencion`; (b) no meterlos (VIVA 2,40 M, falta el 77 %) | (a) | (a), humano 2026-11-07 |
| **D3 universo de cuentas [rev. 16-11, se REABRE]** | (a) unión `cli.cueretide` ∪ 43x8 `tip 17`, con `criterio_seleccion` y `cliente_id` (225 cuentas, 16,00 M); (b) solo `cueretide`, el patrón literal de F-095 y lo que preveía la D3 aprobada (211, 15,05 M: pierde UNEXUM 0,95 M); (c) solo prefijo, lo aprobado sin cambiar (221, 16,00 M, sin `cliente_id`) | (a) | |
| D4 fuente que manda | (a) contabilidad (`saldo_contable_cliente`), como F-095; (b) los efectos | (a) | (a), humano 2026-11-07 |
| D5 obra del saldo contable | (a) fuera; la obra de lo vivo sale de los efectos; (b) repartir | (a) | (a), humano 2026-11-07 |
| D6 la retención pendiente de F-150 | ¿es ESPACIO PROMOCIÓN VIII (0686, 4308001634)? Hoy 1,74 M de saldo frente a 0,62 M en efectos | sí | sí (0686), humano 2026-11-07 |
| D7 caja de F-150 con la retención sin efecto | (a) fuera, hipótesis nueva con su feature; (b) dentro | (a) | (a), humano 2026-11-07 |
| D8 lista de descuadres | (a) a Administración (Juan Romero), como F-095 H7; hoy suma UNEXUM (`cueretide` mal puesta), VÍA CÉLERE, REDES 2, IDS ALJARAFE, CUYAM y BTS | (a) | (a), humano 2026-11-07 |
| **D9 `entidad_cif` de CLIENTE [nueva]** | (a) sigue NULL y la ficha manda a `ventas.clientes` por `entidad_id` (100 % de CLIENTE está en `raw.cli`; 18 filas, 26.334,49 €, son de persona física); (b) rellenarlo de `cli.cif` con copia de `ventas.fn_es_persona_fisica` (datos personales: pasa a `critico`) | (a) | |
| **D10 conciliación por FACTURA de cliente [nueva]** | (a) fuera: feature nueva que da de alta el líder, y los textos dejan de prometerla a F-104; (b) dentro, como vista de `ventas` que lea `retenciones.movimientos` (`ventas` corre después) | (a) | |
| **D11 lo cobrado por un AGR en `ventas.v_factura_cobro` [nueva]** | (a) explicar, no atribuir: Sigrid no guarda el vínculo y la casación por (cuenta, fecha de baja) cubre el 90,4 % con 44 grupos que suman otra cosa; (b) atribuir por esa casación | (a) | |

**Qué cambia y por qué.** Desde el 06-11 entraron en `main` F-040, F-162, F-161 y F-163, y el
arnés pasó a 1.10.1. (1) **F-040 ingiere `raw.cli` con `cueretide`**: la D3 aprobada era
«prefijo provisional, `cueretide` cuando llegue `cli`», y aplicar eso al pie de la letra pierde
0,95 M (UNEXUM); por eso se reabre con la unión como recomendación. (2) **F-040 dejó escritas
tres promesas a F-104** (diccionario de `ventas`, `ARCHITECTURE.md` y su frontera): el
`entidad_cif`, la conciliación por documento y el cobro vía AGR; la spec aprobada no las
cubría: D9-D11. (3) **`test_f040_frontera.py` protege `00_setup.sql`**: `cuentas_cliente` se
muda al principio de `01` (decisión técnica, sin cambio de sentido). (4) Versión del diccionario
v72 → v78, mutación informativa (1.10.1), y las secciones «Frontera» y «Decisiones» de `SPECS.md`.
F-161 y F-163 no tocan nada de lo que F-104 lee o escribe; F-162 tampoco (§1).

**Cifras, 06-11 → 16-11**: VIVA publicado 22.406.732,96 → 22.438.322,16; `retide` vivos 245 /
2.371.937,54 → 247 / 2.403.526,74; con baja 1.956 / 19.928.538,74 (igual); efectos vivos de las
cuentas 345 / 10.495.108,25 → 347 / 10.526.697,45; saldo contable 43x8 15.485.863,29 →
16.002.697,94; 0686 saldo 1.679.407,38 → 1.735.233,86 (diferencia ≈ 1,06 → 1,11 M). Detalle:
`progress/spec_F-104.md`, «Revalidación 2026-11-16».
