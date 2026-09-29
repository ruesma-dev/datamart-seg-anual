<!-- progress/spec_F-110.md -->
# F-110 · Spec escrita (spec-author, 2026-09-25) · APROBADA

Spec en `specs/F-110-fin-obra-cuatrimestral/` (rama
`feature/F-110-fin-obra-cuatrimestral`, desde `main` 4586916, en un worktree
aparte). Ficha en `spec_ready`. Rigor `critico`.

## APROBADA (humano, 2026-09-25)

- **D1 (A)**: la ultima version `Cuatrimestral` por numero.
- **D2**: «es el ultimo mes planificado en el cuatrimestral. Por ejemplo, el
  cuatrimestral de junio 26 puede tener planificada la obra hasta marzo 28;
  entonces el dia a partir del que contar las retenciones seria el 30 de abril».
  Escrito como el ultimo mes de ese cuatrimestral con importe planificado
  (`importe_mes <> 0` en coste o venta); los meses finales a cero no cuentan.
- **D3**: +1 mes = ultimo dia del mes siguiente (30-04-2028 en el ejemplo).
- **D4 (A)**: leer `mart.master_versiones_tipadas` + `stg.plan_mensual` sin tocar
  `depends_on`.
- **D5**: `ultimo_cierre` NO se retira: se QUEDA en `retenciones.fin_obra` como
  dato INFORMATIVO, sin intervenir en `fecha_fin_obra`, y su ficha lo dice.
- **D6**: aceptado: sin cuatrimestral, SIN FECHA (35 obras / 159.677,04 € de lo
  vivo y 102 / 643.734,57 € de saldo contable pasan a SIN_FIN_OBRA; `1-0692` pasa
  a VENCIDA).

**Consecuencia de D5 que decide el spec-author (revocable, `design.md` D5 y R14)**:
se conserva la lectura de `cierre.fact_cierre_mensual` y su guarda de EXISTENCIA,
pero se retira la de tabla VACIA: una columna informativa no debe tumbar el
vencimiento de toda la retencion. Si el humano quiere las dos, es una linea.

**La cola a cero (D2), para que el humano la vea.** 15 de las 117 obras con
cuatrimestral arrastran meses finales con `importe_mes = 0`. Solo pesan en 7
(las que toman fecha por cuatrimestral y tienen retencion viva, 2.006.420,81 €):
frente a tomar la ultima fila, su fin queda antes `1-0678` 5 meses (170.019,37 €),
`1-0686` 3 (1.058.925,82 €), `1-0696` 2 (676.656,98 €) y `1-0588`, `1-0619`,
`1-0697`, `1-0702` 1 mes (100.818,64 €). Ninguna cambia de estado por ello. Las
otras 8 tienen inicio de garantia (`1-0693`, la de 10 meses, entre ellas) o no
tienen retencion viva. Consulta Q7.

Cambios en la spec por la aprobacion: R5 con el ejemplo literal, R7 con la cola,
R10-R12/R14/R17/R19 por D5, `design.md` §Decisiones del humano y §Medidas, y
`tasks.md` T2-T6/T8/T10/T12/T13 (`test_f095_r18` ya no se reescribe).

## Que cambia

Solo `retenciones.fin_obra` (y por arrastre `v_retencion_contable_obra`, sin
tocar su SQL). Regla del humano del 2026-09-25: garantia -> ultimo mes
planificado de la ultima cuatrimestral + 1 mes -> sin fecha. El ultimo cierre
deja de intervenir y se queda como columna informativa (D5). El fin de obra pasa
a leer `mart.master_versiones_tipadas` (que version) y `stg.plan_mensual` (que
mes), los dos de la MISMA noche: el fin de obra ya no va con una noche de
desfase. `depends_on` sigue `["ingest_raw"]`.

## Lo medido (detalle en `design.md` §Medidas)

- **117 fichas de obra tienen cuatrimestral** (de 922; 131 con alguna master).
  Ultima por numero = por fecha efectiva = por creacion en las 117. La marca de
  Sigrid (`conext` 15) coincide en 107.
- **Ultimo mes** = mayor `anio_mes` con `importe_mes <> 0` en 8 y 11: difiere de
  la ultima fila en 15 obras (cola congelada, hasta 10 meses).
- **Viva de los efectos por fuente**, antes -> despues: garantia 97 / 5.026.655,18
  (igual); ultimo cierre 67 / 3.120.260,42 -> cuatrimestral **32 / 2.960.583,38**;
  sin fecha 15 / 100.351,55 -> **50 / 260.028,59**.
- **Se quedan sin fecha 35 obras (159.677,04 €)**: 29 terminadas (cierres de
  2015-2022), 4 en curso sin cuatrimestral (`1-0723`, `1-0721`, `1-0720`,
  `1-0719`, 45.577,49 €), 2 en estado 17.
- **VENCIDA -> PENDIENTE: 0 obras, 0 €.** El humano esperaba este efecto; hoy no
  existe porque el respaldo viejo ya daba fechas futuras en las obras en curso.
  Lo que cambia es la fecha: 15 obras en curso (2,72 M€) retrasan su fin +1 a +19
  meses (media +6,6).
- **PENDIENTE -> VENCIDA: 1 obra, `1-0692`, 43.476,54 €** (su ultima
  cuatrimestral acaba en 2025-02 y la obra cerro hasta 2026-02).
- Saldo contable: **102 obras / 643.734,57 € pasan de VENCIDA a SIN_FIN_OBRA**.
- Coste: +15-40 s estimados al sub-paso `fin_obra`.

## Decisiones que se propusieron (ya decididas arriba; se conservan como rastro)

- **D1** version: (A, recomendada) ultima `Cuatrimestral` por numero; (B) ultima
  de Planif Inicial/ABC/Cuatrimestral: +3 obras con fecha (`1-0723`, `1-0630`,
  `1-0719`, +29.184,48 €); (C) marca de Sigrid, descartada.
- **D2** mes: (A, recomendada) ultimo con movimiento en coste o venta; (B) solo
  venta; (C) ultima fila, descartada.
- **D3** «+1 mes» = ultimo dia del mes siguiente (recomendada, como F-095) o dia 1.
- **D4** lectura: (A, recomendada) `mart.master_versiones_tipadas` + `stg.plan_mensual`
  sin tocar `depends_on`; (B) solo `stg` replicando el `CASE`; (C) declarar
  `build_mart`, descartada.
- **D5** retirar la columna `ultimo_cierre` (recomendada) o dejarla informativa.
- **D6** confirmar a la vista de las cifras: 35 obras vivas y 102 de saldo
  contable sin fecha, y `1-0692` adelantada a VENCIDA. No reabre la decision.

Coordinacion: `00_global.yaml` `version` +1 en carrera con F-108 y F-109 (la
siguiente libre al fusionar). Las fichas y tests de F-095 que fijan la regla
vieja se reescriben (lista cerrada en `tasks.md` T3).

## Consultas (solo lectura; MCP o conexion Python con `transaction_read_only`)

Las pesadas se lanzaron con `PostgresClient.filas_solo_lectura` (READ ONLY,
`statement_timeout` local) y sin bootstrap, desde el arbol principal y sin `.env`
en el worktree. El MCP corta a 30 s: con el las agregadas, no la de `plan`.

**Q1 · Base de la version y el mes** (reutilizada por Q2 y Q3):

```sql
WITH cuat AS (SELECT obra_id, MAX(version) AS version FROM mart.master_versiones_tipadas
              WHERE tipo_master = 'Cuatrimestral' GROUP BY obra_id),
plan AS (SELECT pm.obra_id, MAX(pm.anio_mes) FILTER (WHERE pm.importe_mes <> 0) AS ult_mes_plan
         FROM cuat c JOIN stg.plan_mensual pm ON pm.obra_id = c.obra_id
          AND pm.version = c.version AND pm.ambito_id IN (8, 11) GROUP BY pm.obra_id),
n AS (SELECT f.*, p.ult_mes_plan,
        CASE WHEN f.fecha_inicio_garantia IS NOT NULL THEN f.fecha_inicio_garantia
             WHEN p.ult_mes_plan IS NOT NULL
             THEN (p.ult_mes_plan + INTERVAL '2 months' - INTERVAL '1 day')::date END AS fin_new,
        CASE WHEN f.fecha_inicio_garantia IS NOT NULL THEN 'INICIO_GARANTIA'
             WHEN p.ult_mes_plan IS NOT NULL THEN 'ULTIMO_CUATRIMESTRAL_MAS_1_MES' END AS fuente_new
      FROM retenciones.fin_obra f LEFT JOIN plan p ON p.obra_id = f.obra_id)
```

**Q2 · Viva de los efectos por fuente antes y despues:**
`viva AS (SELECT obra_id, SUM(importe) imp FROM retenciones.movimientos WHERE
sentido='PROVEEDOR' AND estado='VIVA' AND obra_id IS NOT NULL GROUP BY obra_id)`
y `SELECT fuente_fin_obra, fuente_new, COUNT(*), SUM(imp) FROM viva JOIN n USING
(obra_id) GROUP BY 1, 2`.

**Q3 · Estados:** el mismo `CASE` de `v_retencion_contable_obra` (`fecha_vencimiento
< CURRENT_DATE`) sobre `f.fecha_vencimiento` y sobre `(fin_new +
make_interval(months => plazo_meses))::date`, por `retenciones.saldo_contable`
(`saldo <> 0`, con obra) y por la viva de Q2.

**Q4 · Ultima por numero frente a fecha y a la marca de Sigrid:** `DISTINCT ON
(obra_id)` sobre las `Cuatrimestral` ordenando por `version DESC`, por
`version_fec_efectiva DESC` y por `version_fec_creacion DESC`; y cruce con
`stg.version_master_vigente` y el `tipo_master` de su version.

**Q5 · Definiciones de mes:** sobre Q1, `MAX(anio_mes)` sin filtro, con
`importe_mes <> 0`, solo ambito 11, solo ambito 8 y con `importe_mes > 0`.
Resultado: 102/117 iguales, cola hasta 10 meses, coste despues de venta en 20.

**Q6 · Variante D1-B:** Q1-Q3 con `tipo_master IN ('Cuatrimestral', 'ABC',
'Planif Inicial')`.

**Q7 · La cola a cero, obra a obra:** sobre `cuat`, `MAX(anio_mes)` y
`MAX(anio_mes) FILTER (WHERE importe_mes <> 0)` por obra (8 y 11), las filas donde
difieren, con los meses de diferencia (`age`), si la obra tiene inicio de
garantia y su viva de los efectos. 15 filas, 48 s.
