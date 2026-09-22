<!-- specs/F-095-retenciones-contabilidad-fin-obra/design.md -->
# F-095 · Diseno tecnico

`sql/` = `etl_sigrid/infrastructure/postgres/sql/`. Todo medido el 2026-09-22 en
solo lectura; las consultas exactas, en `progress/spec_F-095.md` §Consultas.
**Precondicion: F-094 `done`.** Si al empezar no lo esta, `blocked`.

## Medidas que fijan el diseno

| Hecho | Cifra |
|---|---|
| Apuntes en cuentas `prv.cueretide` (todas las familias) | 49.505 |
| Saldo contable total (todos los apuntes) | **8.760.524,49 €** |
| Idem excluyendo TODAS las aperturas y cierres | 8.117.748,99 € (pierde 642.775,50 = apertura 2008) |
| Apertura de 2016 (= saldo a 31-12-2015) | 1.427.463,67 € |
| Altas (haber) sin cierre/apertura | 27.504 / 24,55 M€; con obra 23,86 M€ (**97,2 %**) |
| Idem sin `rac` (solo `apu.cenide`) | 2,66 M€ (**10,8 %**) |
| Bajas (debe) sin cierre/apertura | 4.189 / 16,43 M€; con obra 12,16 M€ (**74,0 %**) |
| Bajas sin obra: proveedor con 1 obra / 2-3 / 4+ / sin efectos | 0,57 / 0,53 / 1,95 / 1,23 M€ |
| Viva de verdad en efectos (criterio F-094) | 8.345.506,03 € en 179 obras |
| FERMALUX: saldo cuenta 4108005478 = viva efectos | 64.201,96 € |
| `rac`: filas / con `asiide <> 0` / tocan cuentas de retencion | 2.505.089 / 755.086 / 30.204 |

En el agregado de estas cuentas la apertura de cada
ejercicio es exactamente el cierre del anterior (2009-2026, al centimo), y la de
2008 no tiene cierre previo. De ahi la clase `SALDO_INICIAL` de R4.

## Donde vive

En el esquema `retenciones` y en el mismo paso `build_retenciones` (D1). Cuatro
ficheros SQL nuevos detras de `02_views.sql`, que no se toca.

## Ficheros a crear

1. `sql/retenciones/03_apuntes_contables.sql` — `DROP TABLE IF EXISTS ... CASCADE`
   + `CREATE TABLE AS` de `retenciones.cuentas_proveedor` y
   `retenciones.apuntes_contables` (mismo patron que `01_movimientos.sql`). Lee
   `raw.prv`, `raw.con`, `raw.apu`, `raw.rac`, `raw.pag`, `maestro.centros_coste`.
2. `sql/retenciones/04_saldo_contable.sql` — `retenciones.saldo_contable`.
3. `sql/retenciones/05_fin_obra.sql` — `retenciones.fin_obra`. Lee `raw.obr`,
   `raw.obrctr`, `raw.con`. Constante `PLAZO_NEGOCIO` en un CTE de una fila **[H2]**.
4. `sql/retenciones/06_views_contables.sql` — `DROP VIEW IF EXISTS` + `CREATE VIEW`
   de `retenciones.v_cuadre_proveedor` y `retenciones.v_retencion_contable_obra`.
5. `tests/test_f095_retenciones_contables.py` — suite offline (R28): lee el texto
   del SQL (comentarios `--` aparte), el YAML del diccionario, `tables_sigrid.yaml`
   y el cableado del step, al estilo de `test_f057_personal.py`.

## Ficheros a modificar (la propagacion, patron F-057)

- `config/tables_sigrid.yaml` — entrada `rac`: `id_column: ide`,
  `incremental_column: null` (no tiene `tiemod`), `where: "asiide <> 0"` **[H4]**,
  `exclude_columns: [tex]`, comentario con las cifras de arriba. Decidir con
  F-091 que el filtro le sirve (su enlace factura->asiento es la fila con
  `asiide`); si no, se trae entera. `check-raw-recuentos` ya aplica el `where`.
- `tests/test_f074_ingesta_censo.py` y `tests/test_f080_ingesta.py` —
  `TOTAL_TABLAS` 68 -> 69 (el test de F-080 cambia de nombre y de cifra, no de
  intencion). Es el unico cambio en tests ajenos.
- `etl_sigrid/application/steps/build_retenciones_step.py` — cuatro `_SubStep`
  nuevos en `SUB_PASOS` (`apuntes` -> `apuntes_contables`, `saldo` ->
  `saldo_contable`, `fin_obra` -> `fin_obra`, `views_contables` sin tabla) y el
  docstring. `name`, `stage` y `depends_on = ["ingest_raw"]` no cambian (D3).
- `main.py` — **no cambia**: `build-retenciones` y `run-all` ya usan el step. Se
  verifica con test (R25).
- `etl_sigrid/application/orchestrator.py`, `apply_grants_step.py`,
  `config/settings.py`, `etl_sigrid/domain/diccionario.py` — **no cambian**:
  `retenciones` ya es esquema de consumo y del datamart. Se verifica con test.
- `config/diccionario/retenciones.yaml` — seis fichas nuevas (2 tablas de cuentas y
  apuntes, `saldo_contable`, `fin_obra`, 2 vistas) con grano, `clave_negocio`,
  `relaciones`, `consumo_recomendado` (true: `saldo_contable` y las dos vistas) y
  preguntas; en `movimientos` y `v_pbi_*`, una linea: «el saldo vivo que manda es
  el contable (`saldo_contable`); `fecha_prevista_devolucion` es la de Sigrid,
  factura + 15 meses, no la de fin de obra» (R12, R23).
- `config/diccionario/raw.yaml` — ficha `rac` (patron de `apu`: sin columnas, DA-2,
  con el filtro y por que).
- `config/diccionario/00_global.yaml` — `version` +1; el orden de magnitud «34,7
  M€ vivos a proveedor» pasa a **saldo contable ~8,76 M€** (criterio
  `saldo_contable`); el de cliente queda como lo deje F-094. `pendientes` vacio.
- `docs/ARCHITECTURE.md` — «68 tablas» -> 69; parrafo en la semantica Sigrid:
  cuentas por `cueretide`, clase de apunte, saldo inicial de 2008, y que el
  vencimiento se cuenta desde el fin de obra.
- `azure-apps/datamart_seg_anual.md` — consume `rac`, expone seis objetos nuevos
  en `retenciones` y cambia la fuente del saldo vivo (R29).

## Ficheros que NO se tocan

- `sql/retenciones/00_setup.sql`, `01_movimientos.sql`, `02_views.sql`: son de
  F-094. Aqui se **leen** (`movimientos.estado`), no se reescriben.
- `sql/maestro/04_centros_coste.sql`: se consume tal cual (F-073).
- `sql/cierre/05_views_cabecera.sql`: su regla de fin real se **replica** en
  `05_fin_obra.sql` con test de igualdad textual (D5); no se referencia.
- `config/objetos_pendientes.yaml`, codigo de `check-declarados`/`-unicidad`/
  `-relaciones`: se alimentan del SQL y del diccionario.

## Objetos publicados

**`retenciones.cuentas_proveedor`** (TABLA, ~2.247) — `proveedor_id` PK
(`prv.ide`), `proveedor_nombre` (`con.res`), `cuenta_id` (`prv.cueretide`, unica),
`codigo_cuenta`, `nombre_cuenta` (`con` de la cuenta), `familia`
(`LEFT(codigo_cuenta,4)`).

**`retenciones.apuntes_contables`** (TABLA, ~49.505) — `apunte_id` PK (`apu.ide`),
`asiento_id`, `fecha` (`fn_sigrid_date(apu.fec)`), `ejercicio`, `cuenta_id`,
`proveedor_id`, `concepto` (`apu.res`), `importe_alta`, `importe_baja`,
`importe` (`hab - deb`), `clase` (R4), `es_prescripcion` (R6),
`centro_coste_id`, `obra_id`, `codigo_obra`, `via_obra` (R7), `documento_id`
(`rac.conide` si lo hay). Indices `(proveedor_id)`, `(obra_id)`, `(clase)`.
- R4 por cuenta: una apertura es `SALDO_INICIAL` si `NOT EXISTS` un cierre de
  la misma cuenta con `ejercicio = ejercicio - 1`.
- R7 `FACTURA`: `rac` pre-agregada por `asiide` (`MIN(conide)`: 1 fila por
  asiento, medido en F-091), y de la factura, sus efectos `pag` con `retide <> 0`
  **solo si todos tienen el mismo `cenide`** (el 97,2 % medido con `MIN` es cota
  superior; el implementer mide la real y la anota). `EFECTO`: `pag.ide =
  rac.conide`. Centro -> obra siempre por `maestro.centros_coste` (R10).
- `PROVEEDOR_UNA_OBRA` **[H3]**: CTE con los proveedores cuyos efectos de retencion
  (`pag.retide <> 0`, `cenide <> 0`) caen en un solo centro.

**`retenciones.saldo_contable`** (TABLA) — grano (`proveedor_id`, `obra_id`), con
la fila `obra_id` NULL. `altas` (`SUM importe` clase ALTA), `bajas` (BAJA),
`saldo_inicial` (SALDO_INICIAL), `saldo`, `saldo_anterior_2016`,
`num_apuntes`, `primer_movimiento`, `ultimo_movimiento`, `codigo_obra`,
`nombre_obra`, `proveedor_nombre`. `clave_negocio: [proveedor_id, obra_id]`.

**`retenciones.fin_obra`** (TABLA, ~919) — `obra_id` PK, `codigo_obra`,
`estado_obra` (`con.est`), las cuatro candidatas de R17, `fecha_fin_obra`,
`fuente_fin_obra` (R18), `terminada_sin_fin_obra` (R19), `plazo_meses`,
`fuente_plazo` (`PLAZO_RETENCION_CLIENTE`, `PLAZO_GARANTIA_CLIENTE`,
`PLAZO_NEGOCIO`), `fecha_vencimiento` (R21), `num_contratos_obra`.

**`retenciones.v_cuadre_proveedor`** (VISTA) — proveedor: `saldo_contable`,
`viva_efectos`, `diferencia`, `categoria` (R15), `saldo_anterior_2016`,
`prescrito`. `FULL JOIN` sobre `proveedor_id` para no perder las dos colas.

**`retenciones.v_retencion_contable_obra`** (VISTA) — `saldo_contable` (saldo <> 0)
`LEFT JOIN fin_obra`: saldo, fin de obra y fuente, plazo, `fecha_vencimiento`,
`estado_vencimiento` (R22), `dias_hasta_vencimiento`. La vista del caso de uso 3.

## Riesgos y decisiones del spec-author

**D1 · Mismo esquema, mismo paso.** Los permisos (`GRANT` por esquema) y el
consumidor son los mismos que los de `movimientos`. Un paso nuevo solo anadiria
otra fila a `R-FRESCURA` para un build de segundos (49.505 + ~919 filas).

**D2 · Tablas, no vistas.** Cada consulta sobre una vista recorreria `apu`
(2,16 M filas) contra el Postgres compartido: tabla materializada en el build.

**D3 · `depends_on` sigue siendo `["ingest_raw"]`** aunque se lea
`maestro.centros_coste`. Es una vista `CREATE OR REPLACE` sobre `raw` que nunca
se dropea; anadir `build_maestros` (que depende de `build_stg`) haria que un
fallo de `stg` dejara sin retenciones la noche. Guarda: test de que
`maestro/04_centros_coste.sql` solo lee `raw.*`. En un despliegue en base vacia,
el orden de la lista ya pone `build_maestros` antes.

**D4 · Cierre/apertura por cuenta y no por fecha.** Filtrar «apertura de 2008»
fallaria con una cuenta nueva en otra empresa; la regla «apertura sin cierre
previo» es general.

**D5 · Fin de obra propio y no `cierre.v_pbi_cierre_cabecera`**: esa vista solo
cubre el universo del seguimiento (583 obras) y la construye `build_cierre`,
que va despues. Se replica la regla con test de igualdad.

**D6 · `SIN_OBRA` es una fila, no un hueco.** Repartir ~4,3 M€ por reglas
inventadas seria publicar un dato que Sigrid no tiene (R13).

**Riesgos.** (a) `rac` es nueva en la nocturna: +~1 min y ~100 MB filtrada (H4).
(b) `rac.usu` es un login: `raw` es legible por el rol del MCP; F-091 lo
publicara igual. (c) El cuadre depende de F-094: sin el, `viva_efectos` sale
inflada 4,3 veces (R14 y la precondicion lo impiden).

## Plan de verificacion antes / despues (MANUAL, humano; caso testigo FERMALUX)

**Antes** (solo lectura, fotos para comparar): (1) `sigrid-api`: saldo de la
cuenta 1958889 = 64.201,96 y su desglose por `cenide` (consulta K2 de
`progress/spec_F-095.md`); (2) total de cuentas = 8.760.524,49 (B1); (3) MCP:
FERMALUX en `retenciones.v_pbi_retencion_entidad` tras F-094 = 64.201,96.
**Despues** de `python main.py build-retenciones` en el entorno que autorice el
humano: (1) `apuntes_contables` ~49,5 mil filas y 0 cuentas que violen R5;
(2) `SUM(saldo)` de `saldo_contable` = total B1 ± deriva del dia; (3) FERMALUX
`CUADRA` 64.201,96 / 64.201,96 y sus filas por obra suman 64.201,96, con las
obras 0629/0635/0631/0650 cuadrando contra K2 en lo que venga por `APUNTE`;
(4) reparto de `via_obra` y de `categoria` contra la tabla de Medidas y H7;
(5) `fin_obra` = filas de `raw.obr`, y `terminada_sin_fin_obra` ~83 obras con
saldo; (6) `check-declarados`, `check-unicidad`, `check-relaciones`,
`check-diccionario`, `check-raw-recuentos` en verde; (7) por el MCP: «que
retenciones tengo de los proveedores de la obra 0635 y cuando vencen».

## Decisiones para el humano

Cobertura sobre los **8,35 M€ vivos de verdad** (179 obras) salvo que se diga.

**H1 · Que fecha es «fin de obra».** (a) fin real (`MAX(obrctr.fecreafin)`, si
no `obr.fecfinrea`): **25,3 %**; (b) (a) y si no recepcion provisional
`obrctr.fecprorec`: **30,6 %** (2,56 M€); (c) (b) + inicio de garantia: 31,2 %;
(d) (c) + fin previsto de respaldo: 80,5 %, pero una prevision no es un fin.
Fila de `obrctr` (165 obras con varias): `MAX` no nulo, como `cierre`;
`obrctr` manda sobre `obr` (difieren en 4 de 44). En 5 de 37 obras la recepcion
es anterior al fin real. **Obras terminadas sin fecha** con (b): **83 obras,
2,09 M€** (43 con fin previsto): (i) sin vencimiento, `SIN_FIN_OBRA` declarado y
la lista a Administracion para completarla en Sigrid; (ii) previsto como
respaldo marcado `FIN_PREVISTO`. **Recomiendo (b) + (i)**: la prevision de una
obra ya terminada es la fecha que no se cumplio.

**H2 · Que plazo se suma.** (a) del contrato con el cliente, `plaret` y si no
`plagar` (meses): con fin de obra (b) cubre 1,94 de 2,56 M€; es garantia **del
cliente** (back-to-back), no dato del subcontrato; (b) plazo fijo de Negocio para
todas (valor dominante en `obrctr`: 12 meses; Sigrid hoy aplica 15 desde
factura); (c) (a) y si no (b). **Recomiendo (c), y que Negocio fije el valor
de `PLAZO_NEGOCIO`** (el SQL no lleva uno por defecto hasta entonces).

**H3 · Obra de las bajas sin centro** (4,27 M€ con `rac`, 26 % de las bajas).
(a) fila `SIN_OBRA`; (b) (a) + `PROVEEDOR_UNA_OBRA`: +0,57 M€ (bajas con obra
77,5 %), regla segura porque el proveedor solo tiene esa obra; (c) FIFO contra
las altas por obra: resolveria ~3 M€ mas inventando el reparto. De las sin obra,
1,23 M€ son de proveedores sin ningun efecto (historia < 2016). **Recomiendo (b).**

**H4 · Ingerir `rac`.** Sin ella la vista por obra no sirve (altas con obra
10,8 %). Coste **estimado** por proporcion con la nocturna del 2026-09-22 (`apu`
2.164.160 filas, 36 col., 4,0 min, 499 MB; `asi` 787.225, 7 col., 0,7 min,
80 MB) y la forma de `rac` medida (15 col. sin `tex`: 13 enteras, `res` 18 B y
`usu` 7,5 B de media): **entera 2,5-4,5 min y 300-400 MB; con `asiide <> 0`
(755.086 filas) ~1 min y 90-120 MB**, <0,5 % del disco. **Recomiendo filtrada**,
acordado con F-091; si F-091 necesita el log completo, entera.

**H5 · Lado cliente.** Medido: 208 cuentas `cli.cueretide` (200 de 4308, y 4328,
4338, 4380, 5540), saldo deudor **13,81 M€**; `cob` «VIVA» hoy 22,16 M€; con el
criterio de `pag` 2,12 M€. Tres cifras sin relacion: el criterio de estados de
`pag` no se traslada a `cob`. **Recomiendo fuera**, feature propia tras F-094.

**H6 · F-059 y F-045.** F-059 (retenciones antes de 2016 desde contabilidad)
queda cubierta entera: apuntes desde 2008 y `SALDO_INICIAL`. **Recomiendo
retirarla como absorbida** (la regla `ctrrec` sigue en F-067). F-045 (caso de uso
3) se responde con `v_retencion_contable_obra`; lo que le queda es traducir
`movimientos.obra_id` (hoy un centro) a obra, que toca el SQL de F-094.
**Recomiendo absorber ese resto en F-094** y retirar F-045.

**H7 · Los 3,28 M€ que no cuadran.** 761 proveedores con saldo o viva >= 1 € (la
exploracion contaba 1.268 con otro filtro): `CUADRA` 520 / 5,07 M€;
`SIN_EFECTOS_VIVOS` 81 / 0,99 M€ en libros (0,27 de antes de 2016);
`SIN_SALDO_CONTABLE` 38 / 0,20 M€ en efectos (0,04 ya prescritos);
`CONTABILIDAD_MAYOR` 41 / +0,10 M€; `EFECTOS_MAYOR` 81 / -0,47 M€. (a) publicar
la categoria por proveedor, manda la contabilidad; (b) no publicar el saldo por
obra de los que no cuadran; (c) esperar a que Administracion los explique.
**Recomiendo (a)**, y entregar a Administracion la lista de mayores descuadres.
