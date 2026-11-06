<!-- specs/F-158-hotfix-devengo-negativo/design.md -->
# F-158 · Diseño · Hotfix del céntimo negativo en el coste por contrato

Diagnóstico y alternativas: `progress/spec_F-158.md` (§§ 2-4). Recomendada: **A**, el personal
del mes por acumulado sobre el pendiente ya repartido. Rigor propuesto: `estandar` (RED,
cobertura de la función nueva y mutación), como F-155.

## 1. Encaje

Capa `tesoreria` (F-140/F-150), un solo fichero SQL de infraestructura más su espejo de dominio.
No cruza la frontera del servicio: ni `sigrid-api`, ni otro esquema, ni el MCP (solo cambian
céntimos de una columna que ya publica). Sin DDL: las columnas y la clave no cambian.

## 2. Ficheros a modificar

- `etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql`, paso 5
  (`_dev_reparto`): `repartido` deja de calcular `importe_personal` con su propio resto;
  se añade una capa que lo saca por acumulado (§3). `sin_perfil` y la rama `perfil` no cambian.
  Comentario de cabecera (F-150 N16, punto 5) y el del paso 5: «el personal, por acumulado sobre
  el pendiente del mes (F-158)».
- `etl_sigrid/domain/proyeccion_caja.py`: función nueva `repartir_personal` (§4).
- `tests/test_f150_personal.py`: `test_f150_r46_el_reparto_lleva_la_parte_de_personal` fija hoy la
  fórmula del fallo; pasa a fijar la nueva sin perder lo que defiende (el último mes absorbe el
  redondeo del PENDIENTE; sin perfil, entero al primer mes).
- `config/diccionario/tesoreria.yaml`: las dos fichas de R10; `00_global.yaml`: `version` 71 → 72.
- `azure-apps/datamart_seg_anual.md`: NO cambia (mismo contrato publicado). Se dice en el informe.

## 3. El SQL (paso 5)

Hoy `repartido` calcula, para el último mes, `pendiente_personal - (suma_partes_personal -
parte_personal)`, y para el resto `parte_personal`. Pasa a:

```sql
, repartido AS (            -- pendiente y con coeficientes: como hoy
    SELECT r.obra_id, r.concepto, r.partida_id, r.anio_mes,
           CASE WHEN r.desde_el_final = 1 THEN r.pendiente - (r.suma_partes - r.parte) ELSE r.parte END AS importe,
           CASE ... importe_con_coef (sin cambio) ...,
           r.pendiente AS pendiente_partida, r.pendiente_personal
    FROM (...) r
)
, repartido_personal AS (   -- F-158: el personal, por ACUMULADO sobre el pendiente del mes
    SELECT q.*,
           ROUND(q.pendiente_personal * q.acumulado / q.pendiente_partida, 2)
         - ROUND(q.pendiente_personal * (q.acumulado - q.importe) / q.pendiente_partida, 2) AS importe_personal
    FROM (SELECT x.*, SUM(x.importe) OVER (PARTITION BY x.obra_id, x.concepto, x.partida_id
                                           ORDER BY x.anio_mes) AS acumulado
          FROM repartido x) q
)
```

y la rama del `UNION ALL` que hoy lee `repartido r` lee `repartido_personal r`.

- `pendiente_partida` > 0 siempre aquí (`partes` filtra `d.pendiente > 0`): sin división por 0.
- En VENTA `pendiente_personal` es NULL → `importe_personal` NULL, como hoy.
- Orden de operaciones: multiplicar antes de dividir, como `_dev_ctr_reparto`; el dominio igual.
- `(obra, concepto, partida, anio_mes)` es único en `perfil` (`_dev_plan` agrupa por mes): la
  ventana con `ORDER BY anio_mes` no tiene empates.
- `parte_personal` y `suma_partes_personal` salen de `partes`/`repartido` (código muerto fuera).

Verificado en solo lectura con los datos del 05-11 (spec_F-158 §4): 0 negativos en el agregado,
0 meses con personal fuera de [0, pendiente], 0 sumas descuadradas, 89 filas cambian ≤ 0,06 €.

## 4. El dominio

```python
def repartir_personal(
    reparto: Sequence[tuple[date, Decimal, bool]],   # la salida de repartir_pendiente
    pendiente: Decimal,
    pendiente_personal: Decimal,
) -> list[tuple[date, Decimal]]:
```

Capa domain, pura. Por cada mes en orden, `_redondear(pp * acumulado / pendiente) -
_redondear(pp * anterior / pendiente)`. `pendiente == 0` → lista vacía (como `repartir_pendiente`).
Docstring: por qué no dos repartos independientes (el caso 392521) y la garantía de R2-R3.

## 5. Tests (sin red ni BBDD)

Fichero nuevo `tests/test_f158_reparto_personal.py`:

- `test_f158_r6_el_caso_1_0707_no_da_personal_mayor_que_pendiente`: fixture con los 12 meses y
  plan reales de 392521 (spec_F-158 §2); con el nuevo, `pendiente - personal` ≥ 0 en cada mes.
- `test_f158_r6_el_algoritmo_de_ayer_daba_el_negativo`: documenta el RED con dos
  `repartir_pendiente` independientes (8.249,97 / 8.250,02): el fallo queda escrito.
- `test_f158_r2_r3_invariantes`: `random.Random(semilla)` fija, ~2.000 casos (cuota en [0, 1] a
  6 decimales, 1-24 meses, plan positivo): `0 ≤ personal ≤ pendiente` y suma exacta.
- `test_f158_r4_cuota_uno_y_cero`, `test_f158_r5_sin_perfil_una_fila`.
- `test_f158_r7_el_sql_sigue_al_dominio`: el texto de `07` tiene la fórmula de §3, la ventana
  `ORDER BY x.anio_mes` y ya no `r.pendiente_personal - (r.suma_partes_personal`.
- `test_f158_r8_un_mes_negativo_sigue_sin_contrato`: las dos condiciones `r.importe_np > 0` de
  5 bis siguen (ya las fija `test_f150_r49_...`; se cita, no se duplica).
- `test_f158_r9_las_guardas_no_cambian`: R14, R50 y R58 con su texto de hoy.
- `test_f158_r10_fichas`: las dos frases nuevas en `tesoreria.yaml` y `version: 72`.

RED: los tests de R6 (nuevo), R7 y el actualizado de F-150 fallan sobre `fbf43dd`; traza en
`progress/impl_F-158.md`. Mutación: alcance = `repartir_personal`; manual del SQL, al menos:
(M1) volver a `parte_personal` con resto propio, (M2) quitar el `ORDER BY` de la ventana, (M3)
`acumulado - importe` → `acumulado`. Sandbox (D4): opcional.

## 6. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Vuelta atrás: **`fbf43dd`**, `main` antes de F-158; si `main` se mueve antes del merge, la punta
previa al merge. Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`;
`<Q>` = `<PY> -c "import main, sys; pg = main._get_pg(); pg._bootstrap_done = True;
print(pg.filas_solo_lectura(sys.argv[1], 60))" "<consulta>"`. **Antes**: que el despliegue de F-156
del humano haya terminado (comparte imagen y diccionario).

0. Tag actual: `az containerapp job show -n caj-datamart-seg-dev -g rg-datamart-seg-dev --query
   "properties.template.containers[0].image" -o tsv`.
1. `powershell -NoProfile -File infra/70_build_image.ps1` → anotar el tag nuevo.
2. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag nuevo>`; el `az` del paso 0
   debe acabar en `:<tag nuevo>`.
3. `<PY> main.py build-tesoreria` (suelto, sin ingesta) → SUCCESS; sin «coste por contrato no
   cuadra». **3 bis.** `<PY> main.py apply-grants`, siempre: el build recrea objetos.
4. Comprobaciones con `<Q>`:
   - `SELECT count(*) FROM tesoreria.devengo_pendiente_contrato_mes WHERE importe_pendiente < 0` → **0**.
   - `SELECT count(*) FROM tesoreria.devengo_pendiente_obra_mes WHERE concepto = 'COSTE' AND
     importe_pendiente_personal > importe_pendiente` → **0**.
   - `SELECT importe_pendiente FROM tesoreria.devengo_pendiente_contrato_mes WHERE obra_id =
     2563363 AND anio_mes = '2027-10-01' AND categoria = 'CI' AND contrato_id IS NULL` → ≥ 0
     (hoy daría ~0,00; el 03-11 eran 16,60).
   - `SELECT max(started_at) FROM _meta.etl_runs WHERE step = 'build_tesoreria' AND status =
     'SUCCESS'` → la de hoy.
5. `<PY> main.py publicar-diccionario` → **v72** (solo tras la v71 de F-156; D3).
6. `check-diccionario`, `check-declarados` → OK. Reinicio del MCP como en F-153 §9 paso 7.
7. La nocturna siguiente: `build_tesoreria` SUCCESS en `_meta.etl_runs`.

**Vuelta atrás**: (1) `infra/85_update_job.ps1 -Tag <tag del paso 0>`; (2) `git switch --detach
fbf43dd`; (3) `<PY> main.py build-tesoreria` + `apply-grants` (volverá a fallar R50 y dejará las
tablas del 03-11: es el estado de partida, sin daño); (4) `publicar-diccionario` → v71; (5)
`git switch main`. Sin DDL: no queda nada en Azure.

## 7. Qué NO se toca

`cuota_personal`, `pendiente_personal` de la partida, `_dev_ctr`, `_dev_fraccion`,
`_dev_ctr_reparto`, las guardas R14/R50/R58, `partir_personal` (los dos tramos), `10_saldo_partida.sql`,
el perfil (D19-A: los meses a cero no son perfil; D2 deja los negativos como están).

## 8. Riesgos

- Cambian céntimos (≤ 0,06 € por fila, 1,20 € en total el 05-11) en `importe_pendiente_personal`
  y, por arrastre, en `importe_personal_neto`/`_irpf_ss` y en el coste por contrato: es el
  objetivo, y las sumas por partida no cambian.
- Un mes NEGATIVO del plan (1-0702) puede volver a tumbar R50 si un día no compensa: fuera de
  este hotfix por D2; si el humano lo quiere dentro, es una línea (`> 0` en el perfil) y su test.
