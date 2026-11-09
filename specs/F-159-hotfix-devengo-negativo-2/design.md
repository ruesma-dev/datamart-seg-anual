# F-159 · Diseño · Hotfix 2: el reparto del pendiente sobre el plan neto acumulado

Diagnóstico y alternativas: `progress/spec_F-159.md` (§§ 2-5). Recomendada: **A**, perfil =
envolvente neta del plan de V y reparto por acumulado. Rigor: `estandar` (RED, cobertura de lo
cambiado y mutación), como F-158.

## 1. Encaje y límite

Capa `tesoreria` (F-140/F-150/F-158): un fichero SQL de infraestructura y su espejo de dominio.
No cruza la frontera del servicio: ni `sigrid-api`, ni `stg` (el plan con signo es dato legítimo:
el estorno del 0 intermedio, caso B de `stg/08_plan_mensual.sql`), ni otro esquema, ni el MCP.
Sin DDL: columnas y clave iguales. `azure-apps/datamart_seg_anual.md` NO cambia (mismo contrato
publicado); se dice en el informe.

## 2. Ficheros a modificar

- `etl_sigrid/infrastructure/postgres/sql/tesoreria/07_devengo_pendiente.sql`:
  - paso 5 (`_dev_reparto`): `envolvente` nueva; `partes` y `repartido` reescritos (§3);
    `perfil`, `repartido_personal`, `sin_perfil` y el `UNION ALL` final, sin cambios;
  - guarda nueva tras `ANALYZE _dev_reparto` (R9, §3.2);
  - guarda R50: mismo `IF`, mensaje con la primera fila negativa (R10, §3.3);
  - cabecera, punto 5 de los pasos: «repartido por ACUMULADO sobre el plan NETO acumulado de V
    (un mes negativo se absorbe en los anteriores, F-159)»; y el comentario de 5 bis paso 3 que
    habla del mes negativo de 1-0702: con F-159 un (partida, mes) ya no puede ser negativo; la
    condición `importe_np > 0` se queda (protege el 0).
- `etl_sigrid/domain/proyeccion_caja.py`: `repartir_pendiente` reescrita (§4); `repartir_personal`
  sin cambios.
- Tests que fijan hoy la fórmula vieja y se actualizan SIN perder lo que defienden (suma exacta,
  sin perfil al primer mes, el último mes es el más tardío):
  `tests/test_f140_dominio.py` (`..._el_ultimo_mes_absorbe_el_redondeo` y `..._desordenado`: 100/3
  pasa a 33,33 / 33,34 / 33,33), `tests/test_f140_sql.py`
  (`test_f140_r14_el_reparto_proporcional_con_el_resto_al_ultimo_mes`),
  `tests/test_f150_sql.py` (línea ~384, `importe_con_coef`), `tests/test_f150_personal.py` (~228)
  y `tests/test_f158_reparto_personal.py` (`r7_el_pendiente_y_los_coeficientes_no_cambian`, ~222,
  y `r6_el_algoritmo_de_ayer_daba_el_negativo`, que pasa a usar una copia PRIVADA del algoritmo
  de `fbf43dd`, porque `repartir_pendiente` ya no lo es).
- `config/diccionario/tesoreria.yaml`: ficha de `importe_pendiente` de
  `devengo_pendiente_obra_mes` y párrafo «la fila sin contrato solo es negativa…» de
  `devengo_pendiente_contrato_mes` (R12). `config/diccionario/00_global.yaml`: `version` 73 → 74
  con su nota. Los tests de versión de F-158/F-157 que fijen `== 73` pasan a `>=`, como F-158 hizo.

Fichero nuevo: `tests/test_f159_reparto_envolvente.py` (§5).

## 3. El SQL

### 3.1 Paso 5

```sql
, envolvente AS (
    -- F-159: el plan NETO acumulado de V. Un mes negativo (estorno de un 0
    -- intermedio del planif) se absorbe en los meses anteriores: el peso
    -- acumulado es el minimo de lo que queda por delante, con suelo 0, y nunca
    -- baja. 1-0710/404326 (-1.079,94 y +1.080,00): todo a 2026-12, no
    -- -19.438.920,00 en 2026-11 (R50 en rojo el 07-11).
    SELECT a.*,
           GREATEST(0, MIN(a.plan_acumulado) OVER (PARTITION BY a.obra_id, a.concepto, a.partida_id
                       ORDER BY a.anio_mes DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS peso_acumulado,
           ROW_NUMBER() OVER (PARTITION BY a.obra_id, a.concepto, a.partida_id ORDER BY a.anio_mes DESC) AS desde_el_final
    FROM (SELECT pr.*,
                 SUM(pr.importe_mes) OVER (PARTITION BY pr.obra_id, pr.concepto, pr.partida_id
                                          ORDER BY pr.anio_mes) AS plan_acumulado
          FROM perfil pr) a
)
, partes AS (
    -- Lo repartido HASTA cada mes, al centimo; el ultimo mes, el pendiente entero.
    SELECT en.obra_id, en.concepto, en.partida_id, en.anio_mes,
           d.pendiente, d.pendiente_personal,
           CASE WHEN en.desde_el_final = 1 THEN d.pendiente
                ELSE ROUND(d.pendiente * en.peso_acumulado / d.total_perfil, 2) END AS hasta,
           CASE WHEN en.desde_el_final = 1 THEN d.pendiente_con_coeficientes
                ELSE ROUND(d.pendiente_con_coeficientes * en.peso_acumulado / d.total_perfil, 2) END AS hasta_con_coef
    FROM envolvente en
    JOIN _dev_partida d ON d.obra_id = en.obra_id AND d.concepto = en.concepto AND d.partida_id = en.partida_id
    WHERE d.pendiente > 0 AND d.total_perfil > 0
)
, repartido AS (
    -- Cada mes, lo de hasta el menos lo de hasta el anterior (`repartir_pendiente`).
    SELECT p.obra_id, p.concepto, p.partida_id, p.anio_mes,
           p.hasta - COALESCE(LAG(p.hasta) OVER w, 0) AS importe,
           p.hasta_con_coef - COALESCE(LAG(p.hasta_con_coef) OVER w, 0) AS importe_con_coef,
           p.pendiente AS pendiente_partida,
           p.pendiente_personal
    FROM partes p
    WINDOW w AS (PARTITION BY p.obra_id, p.concepto, p.partida_id ORDER BY p.anio_mes)
)
```

Por qué es correcto:

- `total_perfil` = `W(último)`. Si es > 0, la envolvente acaba en él (`min` de un solo valor):
  la fracción `peso_acumulado / total_perfil` está en [0, 1] y no decrece. Si es ≤ 0, la partida
  sigue en `sin_perfil` (la condición `COALESCE(d.total_perfil, 0) <= 0` no cambia): R5.
- `pendiente` es `NUMERIC(18,2)` (el plan y el real lo son): `ROUND(p x f, 2)` ≤ `p` para f ≤ 1,
  y `ROUND` es monótono. Cada mes ≥ 0 y la suma telescópica es `p` exacta (R3). Con coeficientes,
  igual (`pendiente_con_coeficientes` ya va redondeado al céntimo en el paso 4).
- Un mes de peso 0 (anulado por un negativo posterior) da una fila con 0: no cambia
  `num_partidas` (la fila del perfil ya existe) y 5 bis la salta (`rp.pendiente <> 0`).
- `(obra, concepto, partida, anio_mes)` es único en `perfil`: ninguna ventana tiene empates.
- `repartido_personal` (F-158) lee `importe` y su `SUM(...) ORDER BY anio_mes` = `hasta`: el
  personal sigue por acumulado sin tocarlo.

### 3.2 Guarda nueva (R9), tras `ANALYZE _dev_reparto`

```sql
-- F-159: ningun mes del reparto es negativo ni su personal se sale de [0, mes].
DO $$
DECLARE fallo RECORD;
BEGIN
    SELECT obra_id, partida_id, anio_mes, pendiente, importe_personal INTO fallo
      FROM _dev_reparto
     WHERE pendiente < 0 OR importe_personal < 0 OR importe_personal > pendiente
     ORDER BY obra_id, partida_id, anio_mes LIMIT 1;
    IF FOUND THEN
        RAISE EXCEPTION 'devengo_pendiente: la partida % de la obra % reparte % en % (personal %): un mes no puede ser negativo',
            fallo.partida_id, fallo.obra_id, fallo.pendiente, fallo.anio_mes, fallo.importe_personal;
    END IF;
END $$;
```

Las filas del perfil llevan `pendiente` 0 e `importe_personal` NULL: no disparan.

### 3.3 Guarda R50 (R10)

Mismo `IF n_obras > 0 OR n_negativos > 0`. Antes del `RAISE`, `SELECT obra_id, anio_mes,
categoria, contrato_id, importe_pendiente INTO primera FROM tesoreria.devengo_pendiente_contrato_mes
WHERE importe_pendiente < 0 ORDER BY importe_pendiente LIMIT 1`, y el mensaje añade «primera
negativa: obra %, mes %, categoria %, contrato %, importe %» (NULL si no hay). El texto de hoy
(«el coste por contrato no cuadra con la obra-mes en % obras o tiene % importes negativos») se
conserva como prefijo: lo buscan los pasos MANUAL y los tests.

## 4. El dominio

`repartir_pendiente(pendiente, perfil, primer_mes) -> list[tuple[date, Decimal, bool]]`, misma
firma y capa (domain, pura). Meses a 0 fuera, en orden; sin meses o total ≤ 0 → `[(primer_mes,
pendiente, True)]`; sin pendiente → `[]` (sin cambios). Si no: `W` acumulado, envolvente
`W'(i) = max(0, min(W[i:]))` (barrido inverso), `hasta(i) = _redondear(pendiente * W'(i) / total)`
salvo el último (`pendiente`), y cada mes `hasta(i) - hasta(i-1)`. Multiplicar antes de dividir,
como el SQL. Docstring: el caso 404326, por qué la envolvente y no los positivos (D1) y la
garantía de R3.

## 5. Tests (sin red ni BBDD), `tests/test_f159_reparto_envolvente.py`

- `test_f159_r6_el_caso_1_0710`: 404326 → [(2026-11, 0,00), (2026-12, 1.080,00)].
- `test_f159_r6_el_algoritmo_de_ayer_amplificaba`: copia privada del reparto de `93fc38c` →
  -19.438.920,00 / +19.440.000,00 (el RED, escrito).
- `test_f159_r1_la_envolvente_absorbe_hacia_atras`: `100, -100, 100` → todo al tercer mes;
  `100, -40, 60` → la mitad, 0 y la mitad; `-50, 150` → todo al segundo.
- `test_f159_r3_invariantes`: `random.Random(semilla)`, ~2.000 perfiles de 1-24 meses CON SIGNO y
  total > 0: cada mes en [0, p], suma exacta; y `repartir_personal` encima en [0, mes] (R7).
- `test_f159_r4_sin_negativos_solo_cambia_el_redondeo`: perfiles positivos aleatorios, cada mes
  salvo el último a ≤ 0,01 € del algoritmo viejo.
- `test_f159_r5_neto_no_positivo_al_primer_mes`; los de F-140 de R14 siguen (actualizados en §2).
- `test_f159_r8_el_sql_sigue_al_dominio`: el texto de `07` tiene la envolvente (`MIN(a.plan_acumulado)
  OVER`, `ORDER BY a.anio_mes DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`,
  `GREATEST(0,`), `hasta`/`LAG` y ya no `r.pendiente - (r.suma_partes - r.parte)`.
- `test_f159_r9_r10_guardas`: la guarda nueva va antes de `TRUNCATE tesoreria.devengo_pendiente_obra_mes`
  y R50 conserva su condición y su prefijo.
- `test_f159_r11_lo_que_no_cambia`: `perfil` con `<> 0`, `sin_perfil`, `repartido_personal`,
  5 bis (`r.importe_np > 0` dos veces) y R14/R58 con su texto.
- `test_f159_r12_fichas`: las frases de R12 y `version: 74`.

RED: R6 (nuevo), R8, R9-R10 y R12 fallan sobre `93fc38c`; traza en `progress/impl_F-159.md`.
Mutación: alcance `repartir_pendiente`; manual del SQL al menos (M1) `MIN` → `MAX`, (M2) sin
`GREATEST(0,`, (M3) `DESC` → `ASC` en la envolvente, (M4) el último mes con `ROUND` en vez de
`d.pendiente`, (M5) quitar la guarda nueva.

## 6. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = el mismo
helper de solo lectura de F-158 §6. **Vuelta atrás**: la punta de `main` antes del merge (hoy
`93fc38c`) y el tag del paso 0.

0. Tag actual del job (`az containerapp job show … --query "properties.template.containers[0].image"`).
0 bis. Reproducción en solo lectura (la `WITH` de `progress/spec_F-159.md` §2 con el paso 5 nuevo):
   0 agregados negativos y 0 meses negativos con los datos del día.
1. `powershell -NoProfile -File infra/70_build_image.ps1` → tag nuevo.
2. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag nuevo>`; el paso 0 lo confirma.
3. `<PY> main.py build-tesoreria` → SUCCESS. **3 bis.** `<PY> main.py apply-grants`, siempre.
4. Con `<Q>`:
   - `SELECT count(*) FROM tesoreria.devengo_pendiente_contrato_mes WHERE importe_pendiente < 0` → 0.
   - `SELECT count(*) FROM tesoreria.devengo_pendiente_obra_mes WHERE importe_pendiente < 0` → 0.
   - `SELECT anio_mes, sum(importe_pendiente) FROM tesoreria.devengo_pendiente_obra_mes WHERE
     obra_id = 2605958 AND concepto = 'COSTE' GROUP BY 1 ORDER BY 1` → todos ≥ 0 y ninguno por
     encima de `SELECT sum(pendiente) FROM tesoreria.devengo_pendiente_partida WHERE obra_id =
     2605958 AND concepto = 'COSTE'`.
   - `SELECT max(started_at) FROM _meta.etl_runs WHERE step = 'build_tesoreria' AND status = 'SUCCESS'` → hoy.
5. `<PY> main.py publicar-diccionario` → **v74**; `check-diccionario`, `check-declarados` → OK;
   reinicio del MCP como en F-153 §9 paso 7.
6. La nocturna siguiente: `build_tesoreria` SUCCESS.

**Vuelta atrás**: `infra/85_update_job.ps1 -Tag <tag del paso 0>`; `git switch --detach <punta
previa>`; `build-tesoreria` + `apply-grants` (volverá a fallar R50 mientras V13 de 1-0710 siga así
y dejará `tesoreria` como esté: sin daño); `publicar-diccionario` → v73; `git switch main`.

## 7. Qué NO se toca

`stg/08_plan_mensual.sql` y el estorno del 0 intermedio; `perfil` (meses `<> 0`); `_dev_partida`
(pendiente, cuota, `pendiente_personal`); `repartir_personal` y `repartido_personal`;
`sin_perfil`; 5 bis (`_dev_ctr`, `_dev_fraccion`, `_dev_ctr_reparto`); las condiciones de R14,
R50 y R58; `importe_plan_restante`; `10_saldo_partida.sql`; `mart` y `cierre`.

## 8. Riesgos

- Cambian céntimos en ~3.000 (partida, mes) de 48.577 (≤ 0,11 €, 53,10 € fuera de 1-0710) y, por
  arrastre, el personal y el coste por contrato de esos meses: las sumas por partida no cambian.
- La venta cambia igual (mismo paso): en 1-0710 deja de publicar meses amplificados (15 partidas).
- D1 = P en vez de A: 42 filas y 4.639,30 € distintos hoy; es una línea (`> 0` en `perfil`) y
  sin envolvente.
