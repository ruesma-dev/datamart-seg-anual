<!-- progress/spec_F-095.md -->
# F-095 · Spec escrita (spec-author, 2026-09-22)

Rama `feature/F-095-retenciones-contabilidad-fin-obra`, `sdd=true`, rigor
`critico`. La spec: `specs/F-095-retenciones-contabilidad-fin-obra/`
(requirements 150/150, design 248/250, 27 tareas T0-T26). **Decisiones H1-H7
tomadas por el humano el 2026-09-22 e incorporadas** (segunda pasada). La ficha
sigue `pending` y va detras de F-094.

## Que se propone

Seis objetos nuevos en el esquema `retenciones`, dentro del paso
`build_retenciones` que ya existe (sin paso nuevo ni dependencia nueva):
`cuentas_proveedor`, `apuntes_contables` (una fila por apunte de las cuentas
`prv.cueretide`, con su clase y su obra), `saldo_contable` (proveedor x obra),
`fin_obra` (una fila por obra, con las candidatas por separado y el
vencimiento), y dos vistas: `v_cuadre_proveedor` y `v_retencion_contable_obra`.
Se ingiere `raw.rac` (recomendado con `where: asiide <> 0`). La contabilidad pasa
a ser la fuente que manda del saldo vivo; los efectos quedan como detalle.
**Va detras de F-094**: el cuadre lee `movimientos.estado` y no recalcula nada.

La decision del humano del 2026-09-22 esta escrita como R23: **el vencimiento es
fin de obra + plazo; la fecha de factura no interviene nunca**.

## Tres hallazgos nuevos de esta sesion (solo lectura)

1. **Excluir todas las aperturas pierde 642.775,50 €**: la apertura de 2008 es la
   historia anterior a Sigrid. Saldo total 8.760.524,49; sin cierres ni aperturas
   8.117.748,99. Por eso la clase `SALDO_INICIAL` (apertura sin cierre previo de
   la cuenta). La ficha de F-095 decia «sin asientos de cierre ni apertura» a
   secas: aplicado literal, habria dado una cifra falsa.
2. **Sin `rac` la obra de las altas cae al 10,8 %** (con `rac`, 97,2 %). Bajas:
   74,0 % con obra; 4,27 M€ sin obra, de ellos 0,57 M€ de proveedores con una
   sola obra.
3. **Lado cliente: tres cifras sin relacion** (contabilidad 13,81 M€, `cob`
   «VIVA» 22,16 M€, criterio de `pag` aplicado a `cob` 2,12 M€). El criterio de
   estados de `pag` no vale para `cob`: aviso para F-094.

## Decisiones del humano (2026-09-22), ya en la spec

- **H1** Fin de obra = **inicio del periodo de garantia** (`obrctr.fecinigar`,
  `MAX` no nulo, si no `obr.garfecini`): 44 obras, 20,9 % del vivo. **Respaldo:
  ultimo cierre con movimiento + 1 mes** (ultimo dia del mes siguiente): 118
  obras, 76,1 %. Total **97,0 %**; sin fecha 17 obras, 132.544,84 € (9
  terminadas), frente a las 83 de la primera version. Se publica siempre la
  fuente (`INICIO_GARANTIA` / `ULTIMO_CIERRE_MAS_1_MES`).
- **H2** Plazo = `plaret` -> `plagar` -> 12 meses fijos (una constante).
- **H3, H4, H5, H7** como se recomendaron: `PROVEEDOR_UNA_OBRA`; `rac` filtrada
  `asiide <> 0` acordada con F-091; cliente fuera; categoria de cuadre publicada
  y lista de descuadres a Administracion.
- **H6** F-059 se retira como absorbida; el resto de F-045 lo hace F-094.

**Hallazgo de la segunda pasada (define «ultimo cierre»)**: la ultima fase de
`stg.fases` (mes por `cierre.fn_mes_de_fase`) coincide con el ultimo `anio_mes`
de `cierre.fact_cierre_mensual` en las 330 obras, pero **124 tienen fases vacias
tras su ultimo movimiento** (84 acaban en diciembre, ~12 meses de media). Por eso
«ultimo cierre» = ultimo mes con `ejecutado_mes <> 0` (R18, D7). Precio: el
cierre se construye despues de retenciones, asi que el respaldo va con una noche
de retraso, y 5 obras con fases fuera del seguimiento (17.710,38 €) no lo tienen.
Guarda R21: si la tabla del cierre esta vacia, el sub-paso falla.

## Consultas (Sigrid por `sigrid-api`, T-SQL, solo lectura, 2026-09-22)

`R` = cuentas de retencion = `SELECT cueretide FROM prv WHERE cueretide<>0`.

- **B1** saldo total y sin cierre/apertura:
  `SELECT SUM(a.hab-a.deb), SUM(CASE WHEN a.res NOT LIKE 'Asiento de cierre%' AND
  a.res NOT LIKE 'Asiento de apertura%' THEN a.hab-a.deb ELSE 0 END) FROM apu a
  WHERE a.cueide IN (R)`. Por ejercicio: `GROUP BY a.fec/10000`.
- **K2** FERMALUX por centro: `SELECT a.cenide, SUM(a.hab-a.deb) FROM apu a WHERE
  a.cueide=1958889 GROUP BY a.cenide`.
- **C** cuadre por categoria: saldo por `cueide` (`apu`) frente a
  `SUM(tot)` de `pag` con `retide<>0 AND fecrea=0 AND con.fecbaj=0 AND con.est
  NOT IN (10,14,15)` por `entide`, unidos por `prv.cueretide`, proveedores con
  saldo o viva >= 1 €, clasificados en el orden de R15.
- **D** obra de altas y bajas: `apu` de `R` sin cierre/apertura, `LEFT JOIN`
  `(SELECT asiide, MIN(conide) FROM rac WHERE asiide<>0 GROUP BY asiide)`, efectos
  `pag` de la factura (`MIN(NULLIF(cenide,0))`) y `pag.ide = rac.conide`.
- **E** cliente: `cli.cueretide` por familia; `SUM(a.deb-a.hab)` de esas cuentas;
  `cob` con `retide<>0` con y sin el criterio de `pag`.
- **F** cobertura de fin de obra sobre los efectos vivos de verdad, centro ->
  obra por `con` (misma `emp` y `cod`), `obrctr` agregada con `MAX` por obra.
- **A** `rac`: columnas, `COUNT(*)`, `asiide<>0`, `AVG(DATALENGTH(res|usu))`.
- **G** (segunda pasada) vivo por obra desde Sigrid (179 obras, con
  `obr.garfecini`, `MAX(obrctr.fecinigar)`, `plaret`, `plagar`, `con.est`),
  cruzado fuera de la base (179 filas, sin sumar datos grandes) con el MCP:
  `MAX(cierre.fn_mes_de_fase(fecha_inicio, nombre_mes))` de `stg.fases` con
  `numero_fase >= 1`, y `MAX(anio_mes) FILTER (WHERE ejecutado_mes <> 0)` de
  `cierre.fact_cierre_mensual` por obra.
- MCP: `_meta.v_raw_state` (tiempos de `apu`, `asi`) y `pg_total_relation_size`
  de `raw.apu`/`raw.asi` para estimar el coste de `rac`.

Nada se construyo ni se escribio contra Sigrid ni contra Azure.
