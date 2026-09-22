<!-- progress/impl_F-094.md -->
# F-094 · Informe del implementer (2026-09-22)

Rama `feature/F-094-retenciones-estado-vivo` (desde `chore/fichas-2026-09-22`),
`sdd=false`, rigor `estandar`. Contrato: los 4 `acceptance` de la ficha + el plan
aprobado el 2026-09-22 + la ampliación H6 (resto de F-045) aprobada el mismo día.

Commits: `eeb01a2` T0 (in_progress + BACKLOG) · `0bb2e7b` T1 (estado) ·
`489d776` T2 (obra) · T3 este informe.

## Qué cambió

**T1 · Estado de PROVEEDOR** (`sql/retenciones/01_movimientos.sql`). Se une la
ficha `raw.con efe ON efe.ide = p.ide` (la del EFECTO; antes solo la del
documento origen) y `estado` pasa a tres valores, sin borrar filas:

| estado | condición | precedencia |
|---|---|---|
| `BAJA` | `efe.fecbaj <> 0` OR `efe.est IN (14, 15)` | 1ª |
| `LIQUIDADA` | `p.fecrea <> 0` OR `efe.est = 10` | 2ª |
| `VIVA` | resto (= `fecrea=0 AND fecbaj=0 AND est NOT IN (10,14,15)`) | — |

- **El `est 15` identificado** (solo lectura, `raw.conest` y
  `maestro.estados_documento`, tipo 25): `DIV` «Divididos», el padre de una
  división, sustituido por sus hijos. Casa con «anulado/sustituido»: su dinero
  cuenta en otro efecto, igual que el 14 `AGR` «Agrupados». Hoy **0 efectos** de
  retención lo tienen (en Sigrid vivo y en `raw`). Catálogo tipo 25: 1 PDT, 2
  APR, 3 EMI, 5 CAR, 7 REM, 10 PAG, 12 DEV, 14 AGR, 15 DIV, 20 ANT.
- **Precedencia BAJA > LIQUIDADA**, medida: solo **2 efectos (1.000,84 €)**
  tienen a la vez `fecbaj` y `fecrea`; ningún `est 10` tiene `fecbaj`; ningún
  `est 14` tiene `fecrea`. Si una baja con `fecrea` contara como LIQUIDADA, su
  importe se sumaría a lo liquidado junto al del efecto que la sustituye.
- Columnas nuevas en las dos mitades: `estado_sigrid` (`efe.est`) y
  `fecha_baja` (`fn_sigrid_date(efe.fecbaj)`). `VARCHAR(10)` basta (máx. 9).
- `vencida_sin_liquidar` de PROVEEDOR exige la misma condición que VIVA
  (`COALESCE(efe.est, 0)` para que un efecto sin ficha no sea NULL-inseguro).
- **CLIENTE: estado SIN CAMBIOS** (solo `fecrea`). Ver «Lado cliente».

**T1 · Vistas** (`02_views.sql`). BAJA no suma en ninguna lectura:
`neto_practicado`, `total_cargos` y `total_abonos` filtran `estado <> 'BAJA'`;
`saldo_vivo`/`importe_liquidado`/`num_*` ya filtraban por estado. Nuevas, AL
FINAL para no mover columnas: `num_bajas` e `importe_baja` en
`v_pbi_retencion_entidad` y `v_pbi_retencion_resumen`. Por obra, vivas y
vencidas no necesitan cambio (filtran VIVA o `vencida_sin_liquidar`).

**T2 · Obra (resto de F-045)**. `centro_coste_id = NULLIF(cenide,0)` nuevo;
`obra_id` = `CASE WHEN cenide THEN cc.obra_id WHEN od.num_obras = 1 THEN
od.obra_unica END` con `LEFT JOIN maestro.centros_coste cc` (F-073);
`codigo_obra`/`nombre_obra` de la misma cascada. Si el centro existe pero no es
obra, `obra_id` queda NULL (no se cae a las líneas: es estructura; hoy 0 casos).
- **Orden de pasos**: `build_maestros` corre antes en `run-all` (DFS en el orden
  de `build_pipeline_steps`). **NO se declara `depends_on`**, a propósito:
  `build_maestros` depende de `build_stg`; declararlo haría que un fallo de `stg`
  dejara SKIPPED las retenciones, que hoy sobreviven a eso. `maestro.centros_coste`
  es una VISTA sobre `raw` que existe desde F-073 y ningún SQL la dropea. Test
  `test_f094_obra_maestros_corre_antes_que_retenciones` lo fija. Comentado en el
  step y en `00_setup.sql`.

**Diccionario** (`version` 25 → **26**; 158 objetos, **1022 columnas**, 69 de
consumo): `retenciones.yaml` (valor BAJA y reglas de estado por sentido,
`estado_sigrid`, `fecha_baja`, `centro_coste_id`, `obra_id` nuevo, relaciones
`obra_id -> maestro.obras.obra_id` y `centro_coste_id ->
maestro.centros_coste.centro_coste_id` en lugar de la de `cierre…centro_coste_ide`;
`importe` ya no dice que el SUM total sea el neto); `00_global.yaml` (orden de
magnitud 34.700.000 → **8.350.000** con su fuente; cliente 21.900.000 marcado
SIN VERIFICAR; P2 con `estado='VIVA'`); `cierre.yaml` (`centro_coste_ide` ya no
es «la única pasarela»). Además `config/tables_sigrid.yaml:509`,
`LEEME_RETENCIONES_R1.md` (nota de corrección) y `progress/current.md`.
Sin pendientes nuevos.

**Tests**: nuevos `tests/test_f094_retenciones_estado.py` (10) y
`tests/test_f094_retenciones_obra.py` (6), sobre el texto SQL y el YAML (patrón
de `test_f080_sql.py`). Ajustados: `test_f006_reglas.py::…cifras_de_retencion…`
(34700000 → 8350000) y `test_f006_fichas.py::…obra_id_no_es_la_obra` (los tres
hechos se exigen ahora en la columna donde son ciertos: el centro en
`centro_coste_id`, «262 de 262» en `obra_id`).

## Lo medido (solo lectura; `raw` de Azure ingerido 2026-09-22 00:47 UTC)

Ejecutado el SELECT NUEVO de `01_movimientos.sql` envuelto en agregados, por
`psycopg` con `default_transaction_read_only=on` (sin `build_postgres_client` ni
bootstrap), y contrastado contra Sigrid vivo por `sigrid-api` (mismas cifras).

| sentido | estado | efectos | importe (€) | vencidas en build |
|---|---|---|---|---|
| PROVEEDOR | **VIVA** | **7.752** | **8.345.506,03** | 3.857 / 3.163.487,46 |
| PROVEEDOR | LIQUIDADA | 2.368 | 12.754.011,79 | 0 |
| PROVEEDOR | BAJA | 15.511 | 18.691.779,56 | 0 |
| CLIENTE | VIVA | 2.196 | 22.157.642,75 | 2.096 / 21.078.647,40 |
| CLIENTE | LIQUIDADA | 42 | 322.851,50 | 0 |

- **Antes → después, PROVEEDOR**: VIVA 25.016 / 35.544.786,07 → 7.752 /
  8.345.506,03. De las 17.264 que dejan de ser VIVA: 15.509 (18.690.778,72) pasan
  a BAJA y 1.755 (8.508.501,32) a LIQUIDADA; 2 LIQUIDADA pasan a BAJA (1.000,84).
- **Filas: 25.631 PROVEEDOR + 2.238 CLIENTE = 27.869, las mismas antes y
  después**, y la clave `(sentido, movimiento_id)` sigue única (25.631 ids).
  El 25.124 del diccionario es el recuento de R1; hoy son 25.631 y se anota así.
- **FERMALUX (entidad 1958815)**: VIVA **64.201,96** (51 efectos) = saldo de su
  cuenta 4108005478. Además BAJA 17.246,76 (23 originales agrupados) y LIQUIDADA
  17.246,76 (los 3 AGR pagados): **el mismo dinero, ahora contado una vez**.
- **Neto practicado PROVEEDOR**: 21.099.517,82 sin BAJA frente a 39.791.297,38
  sumando todo (la diferencia es exactamente BAJA).
- **Obra** (T2): `obra_id` distintos que casan en `maestro.obras`: **antes 0 de
  262, después 262 de 262** (los 262 antiguos eran centros, los 262 resuelven en
  `maestro.centros_coste`). Filas con obra: 27.336 antes y después (mismas 533
  PROVEEDOR sin centro ni obra única en líneas, 3.257.556,49 €; VIVA sin obra
  115.665,38). `codigo_obra` no cambia en ninguna fila; `nombre_obra` cambia en
  5.459 filas / 40 obras (nombre del centro → nombre de la obra, p. ej.
  «…VILLALVILLA(MADRID)» → «…VILLALBILLA(MAD»). Líneas y centro discrepan en 3 de
  23.199 efectos con ambos (manda el centro). `dcfpro.obride` es obra: 575 de 575
  en `raw.obr`. La vista por obra da 262 filas para 262 `obra_id`.

## Lado cliente (`cob`): medido y FUERA

Sigrid vivo, por estado: los 1.957 efectos con `fecbaj <> 0` (19,9 M€) están
**todos en `est 1` (Pendiente)** repartidos por series 16/ a 25/; ni un `est 14`
ni `15`. Aplicar el criterio de `pag` deja **2.122.847,33 €**, y la contabilidad
de sus cuentas de retención (medida por F-095, consulta E) da **13,81 M€**: tres
cifras sin relación. No es el mismo defecto → estado de CLIENTE sin cambios,
escrito en la cabecera del SQL, en la ficha y en el orden de magnitud. Propuesta:
feature propia (H5 de F-095).

## Verificaciones MANUAL pendientes (humano; no ejecutadas aquí)

```
python main.py build-retenciones
python main.py check-unicidad
python main.py check-relaciones
python main.py publicar-diccionario
```
`check-unicidad`: las claves de `retenciones` en OK (el comando sale con 1 por
`cierre.v_pbi_planif_vs_real`, que es F-051 y previo). `check-relaciones`:
`obra_id -> maestro.obras.obra_id` debe dar 262 de 262 (antes, con la relación
vieja, 0 de 261) y `centro_coste_id -> maestro.centros_coste` completo. Hasta que
corra el build, la relación nueva fallaría contra la tabla vieja: el orden es
build → checks → publicar.

Contraste tras el build (cifras del 2026-09-22; se moverán con la ingesta):
```sql
SELECT sentido, estado, count(*), sum(importe) FROM retenciones.movimientos GROUP BY 1,2 ORDER BY 1,2;
-- PROVEEDOR VIVA 7.752 / 8.345.506,03 · LIQUIDADA 2.368 / 12.754.011,79 · BAJA 15.511 / 18.691.779,56
SELECT saldo_vivo, importe_liquidado, importe_baja FROM retenciones.v_pbi_retencion_entidad
 WHERE sentido='PROVEEDOR' AND entidad_id=1958815;          -- 64.201,96 · 17.246,76 · 17.246,76
SELECT * FROM retenciones.v_pbi_retencion_resumen;          -- num_movimientos = vivas+liquidadas+bajas
SELECT count(DISTINCT m.obra_id), count(DISTINCT o.obra_id)
  FROM retenciones.movimientos m LEFT JOIN maestro.obras o USING (obra_id);   -- 262 · 262
```
Y por el MCP tras `publicar-diccionario`: `contexto_bbdd` ya no debe servir
34,7 M€ (versión 26). Recordar la memoria del MCP: cachea el diccionario hasta
reiniciar.

## `azure-apps/datamart_seg_anual.md` (NO commiteado allí)

El documento no lista columnas de `retenciones`, pero F-094 cambia lo que
exponemos y **rompe a quien una `obra_id` de retenciones con
`cierre…centro_coste_ide`** (Power BI incluido). Cambio exacto propuesto, un
párrafo nuevo tras la línea 447 («…retenciones de una obra…»):

> **F-094 (2026-09-22) cambia `retenciones`.** `obra_id` es ahora la obra de
> `maestro.obras` (antes era el `ide` del centro de coste, que pasa a
> `centro_coste_id`); un informe que uniera `obra_id` con
> `cierre.v_pbi_cierre_cabecera.centro_coste_ide` deja de casar y debe unir por
> `obra_id`. `estado` de PROVEEDOR gana el valor `BAJA` (agrupados, divididos y
> anulados, que no se suman) y el saldo vivo a proveedor baja de 35,5 a 8,35 M€.
> Columnas nuevas: `centro_coste_id`, `estado_sigrid`, `fecha_baja` en
> `movimientos`; `num_bajas`, `importe_baja` en las vistas de entidad y resumen.

## Fase RED (trazas reales)

`python -m pytest tests/test_f094_retenciones_estado.py -q` ANTES del SQL
(extracto; 9 failed, 1 passed):
```
E   AssertionError: la mitad PROVEEDOR tiene que unir `raw.con efe ON efe.ide = p.ide`
E   assert 'efe.fecbaj' in "CASE WHEN COALESCE(p.fecrea, 0) = 0 THEN 'VIVA' ELSE 'LIQUIDADA' END"
E     - CASE WHEN COALESCE(efe.fecbaj, 0) <> 0 OR efe.est IN (14, 15) THEN 'BAJA' WHEN COALESCE(p.fecrea, 0) <> 0 OR efe.est = 10 THEN 'LIQUIDADA' ELSE 'VIVA' END
E     + CASE WHEN COALESCE(p.fecrea, 0) = 0 THEN 'VIVA' ELSE 'LIQUIDADA' END
E   assert "SUM(importe) FILTER (WHERE estado <> 'BAJA') AS neto_practicado" in 'SELECT sentido, ...
E   AssertionError: assert ['VIVA', 'LIQUIDADA'] == ['VIVA', 'LIQUIDADA', 'BAJA']
E   assert 34700000 not in [34700000, 21900000, 25124, 2219, 113600000, 260600000, ...]
9 failed, 1 passed in 0.30s
```
`python -m pytest tests/test_f094_retenciones_obra.py -q` ANTES del SQL de T2
(5 failed, 1 passed; el que pasa es la guarda de orden de pasos, que ya se
cumplía):
```
E   AssertionError: assert 'NULLIF(p.cenide, 0) AS centro_coste_id' in 'DROP TABLE IF EXISTS ...
E   AssertionError: la mitad `p` no traduce el centro a obra con maestro.centros_coste
E   AssertionError: obra_id inesperado en la mitad `p`
E   AssertionError: assert 'CASE WHEN NULLIF(p.cenide, 0) IS NOT NULL THEN cc.codigo_obra ELSE obr_con.cod END AS codigo_obra' in ...
E   AssertionError: assert 'centro_coste_id' in {'sentido': {...
5 failed, 1 passed in 1.93s
```
Después: `16 passed` en los dos ficheros.

## Evidencias

- **`bash harness/init.sh`** tal cual en el worktree: todo OK **salvo `[KO] Falta
  .env`**. Un worktree no trae `.env` y el arnés prohíbe copiarlo (1.7.7,
  `volcar_variables`). Relanzado con las 25 variables del `.env` del árbol
  principal volcadas AL ENTORNO del proceso (sin copiar el fichero): `[OK]
  pytest en verde`, `[OK] PUERTA COBERTURA: 94.7% de 1022 líneas cambiadas
  (968/1022, umbral 80%)`, `[OK] PUERTA TAMAÑO`, rama correcta; única KO la del
  fichero `.env`. **En el árbol principal, con su `.env`, debe quedar verde.**
- **Tests**: 5.043 passed, 189 skipped, 0 failed; **suite 1.932,7 s (32 min 12 s)**.
  Nuevos de F-094: 16 (10 estado + 6 obra).
- **Cobertura**: 94,7 % medida contra `dev` (la base de init.sh, muy por detrás:
  el alcance incluye cambios de otras features ya en `main`).
- **Mutación**: `python -m harness.mutacion --feature F-094 --base main` →
  **CERO MUTANTES**: el único Python de producción tocado son 7 líneas de
  comentario en `build_retenciones_step.py`. No hay informe `mutacion_F-094.md`
  porque la herramienta no lo escribe con 0 generados. El cambio real es SQL y
  YAML, que la campaña no cubre; la evidencia sustitutiva es la medición del
  SELECT nuevo contra la base (arriba) y los 16 tests sobre el texto.
- Mediciones: scripts de solo lectura en el scratchpad de la sesión (`f094/`).
