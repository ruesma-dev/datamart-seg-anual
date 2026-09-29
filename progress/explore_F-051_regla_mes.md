# Exploración F-051 · de dónde sale el mes de las filas reales, la regla y el fan-out

Fecha: 2026-09-22 · Solo lectura de código, docs y git (no se ha consultado la
base). Encargada por el líder tras la corrección del humano: «el mes bueno es
el del nombre, revisa el código porque eso nos costó mucho esfuerzo decidir la
regla y no se puede cambiar».

## Veredicto

**El humano tiene razón y la hipótesis de la ficha F-051 está al revés.** La
regla del proyecto es que el mes de un cierre lo da el TEXTO de la fase, y está
implementada en `cierre`, **pero no en `stg` ni en `mart`**. En las filas
reales, `anio_mes` es el `ano`/`mes` que Sigrid archiva en `obrfas` (sin parsear
el texto ni mirar la fecha). Lo sospechoso es `anio_mes`, no `nombre_mes`.
Derivar `nombre_mes` de `anio_mes`, como proponía la ficha, **borraría el único
rastro del mes bueno** y publicaría el equivocado con cara de correcto.

## 1 · Cómo se calculan `anio_mes` y `nombre_mes` (comprobado en código)

- `stg/05_fases.sql:26-28`: `anio = obrfas.ano`, `mes = obrfas.mes`,
  `nombre_mes = NULLIF(TRIM(obrfas.res),'')`: el texto libre del cierre.
- `stg/08_plan_mensual.sql`, rama de reales (ámbitos 3 y 7):
  `:364` `f.nombre_mes AS res_descripcion`; `:365`
  `make_date(f.anio, f.mes, 1) AS anio_mes`; `:523`
  `res_descripcion AS version_descripcion`. Así desde `ba18868` (2026-05-19).
- F-042 (`08_plan_mensual.sql:381-397`, CTE `reales_vigente`) elige un cierre
  por `(obra, ámbito, anio_mes)` sobre ese `anio_mes` de `obrfas`.
- Rama master (8 y 11): `anio_mes` = `mes_ancla` + posición (`:482`). El parseo
  de texto solo existe ahí para las cuatrimestrales
  (`stg.fn_master_fecha_efectiva`, `stg.fn_master_mes_representado`,
  `stg/00_functions.sql:69, :226`), con los cierres excluidos (`:67`).
- `mart/02_build_fact.sql`: COSTE REAL (`:218-221`) y VENTA REAL (`:243-246`)
  ponen `anio_mes = pm.anio_mes` y `nombre_mes = pm.version_descripcion` (el
  texto), que además va a `version_descripcion` (`:229`, `:254`). Las ramas
  planificadas (`:272-275`, `:302-305`) derivan `nombre_mes` de `anio_mes` con
  el ARRAY de meses (`42e128d`, 2026-08-16, sin locale).
- `mart/03_agg_categoria.sql:61,73`: `MAX(nombre_mes)`, sin agrupar por él.

**La regla del texto solo vive en `cierre/00_setup.sql`**: `fn_parse_mes_fase`
(`:36-97`), `fn_mes_de_fase` (`:105-126`: «Si texto y fecha coinciden → fecha.
Si NO coinciden → manda TEXTO. Si solo uno → ese»; compara con `fecha_inicio`,
no con `ano`/`mes`) y `fn_mes_de_version_master` (`:141-156`). Se usan en
`cierre/02_build_fact.sql:64` (`mes_canonico`) y `cierre/04_views_detalle.sql:128, :508`.

## 2 · La regla decidida (citas literales)

- `config/diccionario/cierre.yaml:12-15`: «El mes al que pertenece un cierre lo
  decide el TEXTO de la fase o de la version, no su fecha. Si texto y fecha
  discrepan, manda el texto: es la regla que dictó el jefe de obra y esta
  implementada en `cierre.fn_mes_de_fase`.»
- `cierre.yaml:1048-1052`: «Si discrepan, MANDA EL TEXTO: es la regla que dicto
  el jefe de obra, porque la fecha se teclea mal con mas frecuencia que el nombre.»
- `cierre.yaml:66-69` y `stg.yaml:741-745` (`stg.fases.nombre_mes`: «Manda sobre
  la fecha cuando las dos existen y no coinciden»).
- Origen: `b0aebae` (2026-05-27, «cierre general, con master»).
- Regla complementaria de F-042 (humano, 2026-08-28): «el mes no se parte en 2,
  se coge el cierre mas moderno de ese mes». Implantada sobre `ano`/`mes` de
  `obrfas` (`08_plan_mensual.sql:88-115`, `docs/ARCHITECTURE.md:44-53`).
  `specs/F-042-clave-fact/design.md:167-170` ya avisaba de que `cierre` agrega
  por su `mes_canonico`; `progress/explore_F-042.md:365-380` planteó remapear al
  mes del texto (hipótesis 2) y no se adoptó.
- Ningún test prueba el comportamiento de la regla: `tests/test_f006_fichas.py:423-425`
  solo exige que las funciones estén documentadas.

## 3 · El fan-out de `cierre.v_pbi_planif_vs_real`

`cierre/06_views_planif_vs_real.sql`: `base` (`:34-49`) agrupa por `obra,
anio_mes, nombre_mes, categoria, concepto`; `producc` (`:61`) y `total_costes`
(`:92`) incluyen `nombre_mes`; `beneficio` (`:102-105`) los une solo por
`(obra_id, anio_mes)`.

**Mecanismo (inferido, cuadra con código y cifras)**: en un `(obra, anio_mes)`
con planificado y real, el planificado lleva la etiqueta derivada ('Mayo 2020')
y el real el texto del cierre ('Agosto 2020'); `base` los parte en dos grupos,
`producc` y `total_costes` salen con 2 filas y `beneficio` con 2×2 = 4. Caso
0571 (`progress/explore_F-042.md:78, :135`): fase 21 «Enero 2020-Abril 2020» y
22 «Agosto 2020», las dos archivadas en mayo-2020; F-042 se queda con la 22. Las
186 filas de 2024+ etiquetadas 'Diciembre 2025' son lo mismo. Precedente:
`42e128d` («las vistas que agrupan por nombre_mes partian cada grupo en dos»).

**Duda sobre la ficha (sin medir)**: con este SQL no solo BENEFICIO; también
PRODUCCIÓN, CD, CI, CP y TOTAL COSTES saldrían ×2 (204 combinaciones / 36 pares
≈ 5,7 renglones por par). Si es así, `diferencia` y `desviacion_pct` están mal en
todos los renglones de esos meses. Se confirma con `GROUP BY concepto_cuadro
HAVING count(*) > 1` sobre la vista.

**Raíz según la regla**: real y planificado caen en el mes de `obrfas`, no en el
del texto; y la vista agrupa por una columna descriptiva y une por una clave
más corta que la de sus CTE.

## 4 · Arreglo que respetaría la regla (propuesta, sin validar)

1. **En `stg`, rama de reales**: `anio_mes` = mes de la fase por la regla del
   texto (equivalente a `cierre.fn_mes_de_fase(f.fecha_inicio, f.nombre_mes)`,
   llevando el parser a `stg/00_functions.sql`, porque `cierre.*` se crea
   después). En `mart`, `nombre_mes` derivado de ese `anio_mes` con el ARRAY y
   el texto del cierre en `version_descripcion`, que ya se publica.
2. **Blindar la vista**: no agrupar por `nombre_mes` en `base`/`producc`/
   `total_costes` (o `MAX`) y unir el beneficio en CTE del mismo grano. Quita el
   fan-out por sí solo y sin mover dinero, pero sin el punto 1 sigue publicando
   el mes de `obrfas`.

**Riesgos del punto 1**: **mueve dinero y el eje temporal** (la ficha prometía
«no se mueve ni un importe»): aparecen meses que hoy faltan (jul-ago 2010 en la
0246, jun-ago 2020 en la 0571); cambia el conjunto de colisiones de F-042;
`fn_parse_mes_fase` toma el PRIMER mes y año del texto («Enero 2020-Abril 2020»
→ enero, que chocaría con el cierre real de enero) y un texto sin año cae a
`fecha_inicio`. El `LAG` de `importe_mes` va por `orden_fase` (`:430-457`), así
que no se rompe, pero hay que rehacer el contraste con `huella-obras
--propuesta` de F-042.

## 5 · Relación con F-050 y con los tests

- **F-050** (`BACKLOG.md`, patrón 2: fase de varios meses archivada en su mes
  de arranque; 0246, 0462, 0464, 0514, 0515, 0516, 0571, 0606) **es este mismo
  problema**. La ficha de F-051 decía que no dependía de F-050; con la regla del
  texto sí: decidir el mes de esas fases ES aplicar la regla.
- Tests afectados: `tests/test_f019_t13_portabilidad.py` (ARRAY sin locale),
  `tests/test_f042_sql.py` (estructura de `reales_base`, marcadores
  `F042_INICIO/FIN_REALES`), `test_f078_sql.py:371-375`.

**Límites**: comprobado lo que lleva `fichero:línea` o hash; inferidos el 2×2,
la repetición de los otros renglones, el origen de 'Mayo 2020' en la 0571 y los
efectos del remapeo. No se ha ejecutado ninguna consulta contra la base.
