<!-- specs/F-161-versiones-sin-reparto/design.md -->
# F-161 · Diseño · Catálogo completo, coste por versión y partida, y planificado de importe al lado del temporal

**Rigor: `estandar`** (el de `harness/features.json`). No cumple ningún disparador de `critico`: no
toca el servidor compartido, ni seguridad, ni dinero que se pague; por D4 ninguna cifra publicada
cambia, y R11 y R18 lo demuestran.

Cifras (§5): spec-author, Azure, solo lectura (MCP), 2026-11-13 00:05-00:20 UTC, `stg` del lote
`20261112T092908Z-8a4f1c` y `mart` del `20261112T102833Z-4a4b97`. Detalle: `progress/spec_F-161.md`.

## 1. Encaje, límite y frontera

Todo cabe en este ETL. `stg` resume lo que ya tiene (`stg.presupuesto`, `stg.plan_mensual`,
`raw.obrfasamb`) y `mart` publica. No hay ingesta nueva, ni llamada nueva a `sigrid-api`, ni
permisos nuevos: `apply-grants` da `SELECT` por esquema y el MCP ya sirve `stg` y `mart`.

**Frontera: ¿cruza la frontera del proyecto? Sí, solo en lo publicado.** Aparecen cuatro objetos
que lee el MCP (`mcp-bbdd`); su lista blanca es por esquema y no cambia, pero hay que reiniciarlo
para que coja el diccionario nuevo. Documento del ecosistema: `azure-apps/datamart_seg_anual.md`
(`pull` antes de editar, commit local, sin `push`). Power BI no cambia: ninguna `v_pbi_` se toca.

## 2. Ficheros

**Crear**
- `etl_sigrid/infrastructure/postgres/sql/stg/10_master_versiones.sql` (§3.1).
- `etl_sigrid/infrastructure/postgres/sql/mart/01b_master_versiones.sql` (§3.2 y §3.3).
- `etl_sigrid/domain/master_versiones.py`: el oráculo puro (§4).
- `etl_sigrid/infrastructure/postgres/master_versiones_sql.py`: `CATALOGO_ANTERIOR`, el `SELECT
  DISTINCT` de hoy copiado de `06_cp_tipologia.sql` (sección 1), y `sql_comparacion_catalogo()`,
  el `EXCEPT` en los dos sentidos de R11. Lo usan la sandbox y el paso MANUAL 4.
- `tests/test_f161_dominio.py`, `tests/test_f161_sql.py`, `tests/test_f161_diccionario.py` y
  `tests/test_f161_sandbox.py` (§6).

**Modificar**
- `sql/stg/01_ddl.sql`: `stg.master_versiones` (con PK `(obra_id, ambito_id, version)`) y la vista
  `stg.v_master_lineas` (§3.1), detrás de `plan_mensual_fase0`.
- `application/steps/build_stg_step.py`: `_SubStep("build_master_versiones",
  "10_master_versiones.sql", "stg", "master_versiones")` detrás de `build_plan_mensual_fase0`,
  ejecutado entero. No entra en `FICHEROS_DEL_SELLO` ni en `TABLAS_ACOTADAS`. Docstring al día.
- `application/steps/build_mart_step.py`: `_SubStep("master_versiones", "01b_master_versiones.sql")`
  entre `ddl` y `build_fact`, que cuenta `mart.master_versiones_tipadas`. `cp_tipologia` sigue el último.
- `sql/mart/02_build_fact.sql`: las CTE `versiones_master` y `versiones_tipadas` se sustituyen por
  una sola que lee `mart.master_versiones_tipadas` con el filtro de R10. La cabecera del fichero se
  corrige: el catálogo ya no se deduce de `plan_mensual`.
- `sql/mart/06_cp_tipologia.sql`: fuera la sección 1, sus dos `DROP` y la vista
  `v_master_versiones_tipadas`, que pasan a `01b`; `candidatos` añade `AND vt.tiene_reparto`.
- `sql/retenciones/05_fin_obra.sql`: `AND v.tiene_reparto` en la CTE `cuatrimestral` y en la comprobación
  del `DO` (D4: hoy se elige entre versiones con reparto; si no, una Cuatrimestral sin reparto dejaría
  `ultimo_mes_planificado` a NULL y la obra sin fecha de fin, la regresión del diagnóstico, §5, opción A).
- Tests que fijan el texto movido, con su motivo: `test_f078_sql.py` (`_cuerpo` del catálogo desde
  `01b`; dos tablas en `06`), `test_f110_fin_obra_cuatrimestral.py` y lo que dé `grep -rn
  "versiones_tipadas\|versiones_master" tests`. Diccionario (§7), `docs/ARCHITECTURE.md`, `CLAUDE.md`
  (mapa) y `../azure-apps/datamart_seg_anual.md`.

**No se tocan**
- `sql/stg/06_presupuesto.sql`, `08_plan_mensual.sql` y `09_plan_mensual_fase0.sql`, ni
  `00_functions.sql`: están en el sello y cambiarlos reconstruye las 634 fichas una noche. La marca
  se deduce de lo que ya hay.
- `sql/tesoreria/07_devengo_pendiente.sql`: busca el tipo y la fecha de una versión que sale del
  hecho, que siempre tiene reparto, y con una fila por clave (D13) el resultado no cambia.
- `cp_tipologia_sql.py` (la fotografía de `check-cp-tipologia`): sigue recalculando con la lógica
  de antes desde `stg.plan_mensual`, y por eso sirve de oráculo independiente para R18.
- `huella_obras.py`, `fingerprint.py`, `descompuestos/`, `cierre/`, `tables_sigrid.yaml`, `infra/`, `main.py`.

## 3. El SQL

### 3.1 `stg.master_versiones` y `stg.v_master_lineas` (capa `stg`)

`10_master_versiones.sql` hace `TRUNCATE` + `INSERT` entero: lee `stg.presupuesto` y
`stg.plan_mensual`, que tienen todas las obras (las congeladas también, F-025), y `raw.obrfasamb`.

1. `plan` = `SELECT DISTINCT ON (obra_id, ambito_id, version)` de las versiones de `stg.plan_mensual`
   de los ámbitos 8 y 11, con sus cinco atributos (`version_fec_creacion`, `version_fec_efectiva`,
   `version_descripcion`, `version_tex`), en orden `version_fec_efectiva DESC NULLS LAST,
   version_fec_creacion DESC NULLS LAST`. Hoy da una fila por clave (§5.1).
2. `lineas` = las líneas de `stg.presupuesto` de los ámbitos 8 y 11 con `fase_num` >= 1, más las de
   `fase_num` = 0 SOLO si su versión está en `plan` (D6), con `con_reparto` = su `presupuesto_id`
   aparece en `stg.plan_mensual` (D7).
3. `cabecera` = `raw.obrfasamb` de los ámbitos 8 y 11, sin duplicar: `DISTINCT ON (obride, amb, fas)
   ORDER BY obride, amb, fas, ide DESC`, como `descompuestos/03_lineas_master.sql` (D13), con el
   texto de coste unido para la venta (deduplicado igual). Expresiones copiadas de `08`.
4. Universo = claves de `lineas` ∪ claves de `plan` (D5). `LEFT JOIN` a las tres CTE. Atributos:
   `COALESCE` de `plan` y, si no, `cabecera` (R4). `tiene_reparto` = la clave está en `plan`.
   `reparto` según R3, sobre `importe` <> 0.

`stg.v_master_lineas` (vista, sin disco, D12): `presupuesto_id`, `obra_id`, `partida_id`, `ambito_id`,
`fase_num AS version`, `cantidad`, `precio`, `importe` y `tiene_reparto` = `EXISTS` en `stg.plan_mensual`
por `presupuesto_id` (índice: 210 ms para 12 versiones de la 0698); ámbitos 8 y 11, versión >= 1.

**Coste.** Hoy `06` barre los ámbitos master de `stg.plan_mensual` (8,6 GB de heap) para el catálogo y
`02` lo vuelve a barrer para el suyo. Con F-161 ese barrido se hace UNA vez, en `stg`, y se añade
uno de `stg.presupuesto` (2,4 GB). El saldo esperado es neutro o a favor, pero no está medido: los
sub-pasos de `build_mart` no dejan tiempo en `_meta.etl_runs`. T3 mide con `EXPLAIN (ANALYZE)` la
forma de la consulta antes de fijarla. Para los `presupuesto_id`, un recorrido solo de índice sobre
`idx_plan_mensual_presupuesto` puede bastar. Si no cabe en el margen de R19, PARAR.

### 3.2 El catálogo único (capa `mart`, `01b_master_versiones.sql`)

`DROP VIEW IF EXISTS mart.v_master_versiones_tipadas CASCADE`; `DROP TABLE IF EXISTS
mart.master_versiones_tipadas CASCADE`; `CREATE TABLE ... AS SELECT` las ocho columnas de hoy, con
la cascada de `tipo_master` literal, y después `tiene_reparto`, `reparto`, `n_lineas`,
`n_lineas_con_reparto`, `importe_total`, `importe_con_reparto`, `importe_sin_reparto`,
`tiene_cabecera` y `tiene_ancla`, `FROM stg.master_versiones`. La vista envuelve la tabla con esas
columnas y en ese orden (R8). La cabecera del fichero dice que es el ÚNICO catálogo y quién lo lee
(`02`, `06`, `retenciones/05`, `tesoreria/07`).

Consumidores (R10): `02_build_fact.sql` `versiones_tipadas AS (SELECT <las ocho> FROM
mart.master_versiones_tipadas WHERE tiene_reparto AND version_fec_creacion IS NOT NULL AND
version_fec_efectiva IS NOT NULL)`; el resto de `02` no cambia ni una línea.

### 3.3 El coste por partida y el planificado de importe (capa `mart`, mismo fichero)

`mart.v_master_version_partida` (vista): `stg.v_master_lineas` `JOIN` catálogo `JOIN` `stg.partidas`
`LEFT JOIN` `stg.obras` (`empresa_id`, `clave_obra`, F-162). Ámbitos 8 y 11, con `concepto` (D14). Sin
filtro de obra es cara: lo dice la ficha.

`mart.master_importe_mensual` (tabla), con `params` = `CURRENT_DATE` del build (R17):
- `meses`: por (obra, ámbito) del catálogo, `generate_series` desde el mes de la primera
  `version_fec_efectiva` elegible hasta `date_trunc('month', hoy)` (D9).
- `importe`: `ROW_NUMBER()` sobre las versiones >= 1 con `n_lineas` > 0 y fecha efectiva <
  `anio_mes + 1 mes`, por `version_fec_efectiva DESC, version DESC`, de cualquier tipo (D8).
- `temporal`: lo mismo con el filtro de R10 y `tipo_master IN ('Planif Inicial', 'ABC',
  'Cuatrimestral')`, el predicado de `02` copiado literal (R16 lo vigila en la sandbox).
- Columnas: `obra_id`, `empresa_id`, `clave_obra`, `ambito_id`, `concepto`, `anio_mes`,
  `version_importe`, `tipo_master_importe`, `version_tex_importe`, `importe_total_importe`,
  `version_temporal`, `tipo_master_temporal`, `importe_total_temporal`,
  `importe_con_reparto_temporal`, `diferencia_importe` y `es_misma_version`.
- Orden de magnitud: unas 370 parejas (obra, ámbito) con versiones, por sus meses; del orden de
  10^4 filas (T7 lo mide).

## 4. El oráculo (`etl_sigrid/domain/master_versiones.py`, sin dependencias)

- `tipo_master(tex: str | None) -> str`: la cascada (ABC > Planif Inicial > Cuatrimestral > Cierre
  mensual > Sin clasificar).
- `clasificar_reparto(lineas: Sequence[tuple[Decimal, bool]], tiene_reparto: bool) -> str`, con las
  líneas como (`importe`, `con_reparto`): NINGUNO, COMPLETO o PARCIAL (R3).
- `version_vigente(versiones, mes, *, temporal: bool) -> VersionMaster | None`: D8 si `temporal` es
  FALSE y R10 si es TRUE. `VersionMaster` es un `dataclass` congelado con número, fecha efectiva,
  tipo, `n_lineas`, `tiene_reparto` e `importe_total`.

La sandbox compara el SQL con el oráculo, como en F-157.

## 5. Medido (Azure, solo lectura, 2026-11-13 00:05-00:20 UTC)

Durante la ingesta (no toca `stg` ni `mart`); cuatro consultas de 20-30 s. Detalle y consultas:
`progress/spec_F-161.md`.
**5.1 Hoy.** 4.534 filas (2.270 + 2.264), 133 obras, 0 claves repetidas, 0 `version_fec_creacion`
nulas (el de `02` y el de `06` coinciden). 8 filas son de la versión 0 (0578, 0613, 0578-B, 1338614)
y 10 de obras fuera de `stg.obras`. La ficha de `stg.plan_mensual` niega la versión 0: falso (R20).

**5.2 Lo que entra** (versiones >= 1 con líneas, obras de `stg.obras`):

| Ámbito | En el catálogo hoy | Entran | Obras | Líneas que entran | Importe que entra |
|---|---|---|---|---|---|
| 8 coste | 2.262 | **722** | 168 | 537.199 | 2.917,07 M€ |
| 11 venta | 2.256 | **726** | 164 | 488.231 | 2.928,91 M€ |

Unas 5.990 filas (+1.448). Las v0 sin reparto (219 + 214) siguen fuera (D6). El motivo de cada una
solo está en `raw`, que el MCP no sirve; el diagnóstico (2026-11-10) dio 49 sin `planif` (0698 v24,
0722 v7, 0705 v17-v18, 0693 v17-v20), 927 por ámbito sin `plafec` y 2 sin cabecera. T7 lo repite.

**5.3 Importe frente a temporal, a hoy** (orden por número de versión; T7 lo rehace con la fecha).
Coste / venta: 58 / 54 obras sin ninguna versión en el catálogo (0714, 0718, 0721, 0725, 0727...);
8 / 3 cuya última versión no está (0685, 0698, 0705, 0722); 25 / 25 con temporal 2026 ≠ última.

| Obra (coste) | Temporal hoy | Importe hoy (último cierre) | `diferencia_importe` |
|---|---|---|---|
| 0698 | v20 Cuatrimestral · 2.165.726,69 | v24 · 2.107.662,97 | −58.063,72 |
| 0705 | v16 Cuatrimestral · 3.026.987,39 | v18 · 2.882.351,55 | −144.635,84 |
| 0722 | v3 Cuatrimestral · 1.094.131,22 | v8 · 1.073.686,01 | −20.445,21 |
| 0721 (F-162 D6) | ninguna | v1 · 13.523.755,74 (850 líneas) | NULL |

**La 0721** (F-162 D6): su v1 entra con `reparto` = NINGUNO, por partida y en
`master_importe_mensual`. El mensual sigue sin planificado: no tiene `planif`, y D4 manda.

**5.4 Línea con reparto.** La v23 de coste de la 0698 tiene 751 líneas con `planif` y solo 690 dejan
filas (su `planif` no deja ningún mes): de ahí D7. Sale PARCIAL (56.059,64 € sin reparto); la v20,
COMPLETO (sus 95 líneas sin reparto están a 0 €). **5.5 Tiempos**: `build_stg` 5.024 s y `build_mart`
5.033 s de media (9 noches); el catálogo no tiene tiempo propio en `_meta.etl_runs` (T3).

## 6. Tests (sin red ni BBDD salvo la sandbox)

- `test_f161_dominio.py`: la cascada (los cinco textos de la cabecera de `02`), `clasificar_reparto`
  (la v20, la v23 y la v24 de la 0698 en pequeño; una versión con reparto y sin líneas da COMPLETO),
  y `version_vigente` en los dos modos (empate de fecha → mayor versión; fecha NULL fuera; v0 fuera
  en importe).
- `test_f161_sql.py`: el `01_ddl` (PK y vista); el sub-paso de `stg` detrás de `fase0` y fuera del
  sello; el de `mart` entre `ddl` y `build_fact`; que `02` y `06` no tengan la cascada ni `FROM
  stg.plan_mensual` para el catálogo (R9); los tres filtros de R10; las columnas de R7, R8 y R14;
  `CURRENT_DATE` solo en `params` (R17); `CATALOGO_ANTERIOR` igual, salvo espacios, a la sección 1 de
  `06` en `491fbf1` (texto fijado en el test).
- `test_f161_diccionario.py`: las cuatro fichas, las columnas nuevas, `R-VERSION-MASTER`, P18,
  `version` y la corrección de `stg.plan_mensual` (R20); los textos de R21.
- `test_f161_sandbox.py` (`F161_SANDBOX_DSN`, base nueva que se borra al final, como
  `test_f157_sandbox.py`, con los tipos de la ingesta): `raw.obrfasamb` (una cabecera duplicada, una
  sin `plafec`), `stg.presupuesto`, `stg.plan_mensual`, `stg.obras` y `stg.partidas` mínimas. Ejecuta
  `stg/01_ddl.sql`, `10`, `mart/01_ddl.sql`, `01b` y `02` reales y comprueba R1-R5, R11 (contra
  `CATALOGO_ANTERIOR`), R12, R14-R16, y el oráculo igual al SQL en todos. La ejecuta el líder con DSN.

## 7. Diccionario

`stg.yaml`: fichas de `master_versiones` y `v_master_lineas`; la de `plan_mensual`, corregida (5.1).
`mart.yaml`: `master_versiones_tipadas` y su vista, con el grano nuevo y las nueve columnas;
`v_master_version_partida` y `master_importe_mensual`, que dicen que la de importe y la temporal no
se suman ni se mezclan (D3). `00_global.yaml`: `R-VERSION-MASTER` (`resumen` incluido: «solo las de
`tiene_reparto` rigen el mensual; el último cierre está en `master_importe_mensual`»), P18 con
`reparto = 'NINGUNO'` y `version` siguiente. `tests/test_f147_presupuesto_contexto.py`: si
`PRESUPUESTO_MAX` no basta, se acorta o se sube con su motivo.

## 8. Pasos MANUAL (tras APROBADO y merge; los lanza el humano, fuera de 00:00-05:00 UTC)

`<Q>` = `filas_solo_lectura` con `_bootstrap_done = True`. El patrón es el de F-162 §7.

0. ANTES, mismo `raw`: la imagen del job; `huella-obras --desde mart --out antes_mart.csv`;
   `fingerprint-views --schemas retenciones,tesoreria --periodo-hasta <mes cerrado> --out antes_rt.csv`.
1. `infra/70_build_image.ps1` y `infra/85_update_job.ps1 -Tag <nuevo>`.
2. Job puntual SIN ingesta (`--yaml`): `stage && build-mart && build-cierre && build-tesoreria &&
   build-retenciones && apply-grants`.
3. Huellas otra vez: `comparar-huellas` sin ninguna obra y `compare-fingerprints` sin fallos; y
   `check-cp-tipologia` con 0 diferencias (R18). Si sale cualquier diferencia, PARAR y volver a la imagen anterior.
4. `<Q>`: `sql_comparacion_catalogo()` da 0 filas en los dos sentidos (R11); la v24 de la 0698 de R13;
   el recuento de §5.2; R16 contado en SQL (0 discrepancias); tiempos de `build_stg` y `build_mart` (R19).
5. Publicar el diccionario con su imagen y reiniciar el MCP.

## 9. Riesgos

- **El barrido de `plan_mensual` cambia de sitio**: si `stg` se alarga, la nocturna también (R19, T3,
  medido fuera de la nocturna por los créditos de CPU).
- **Cabecera duplicada** (D13): hoy 0. Si vuelve, el catálogo da una fila y `plan_mensual` sigue
  duplicando (`docs/referencia/05_caso_obrfasamb_version_duplicada.md`), como ya hace `descompuestos`.
- **Congeladas**: con reparto, atributos de `plan_mensual` (hasta 6 días); sin él, de la cabecera de
  esta noche. A propósito (R4). **`02` es el hecho central**: cambia una CTE; R11, R16 y la huella lo cubren.

## 10. Decisiones para la PARADA 1

| Id | Pregunta | Opciones | Recomendación | Decidido |
|---|---|---|---|---|
| D5 | Universo del catálogo | (a) líneas de `stg.presupuesto` ∪ versiones de `plan_mensual`, cabecera opcional · (b) solo cabeceras con líneas | (a): no se pierde ningún importe (2 versiones sin cabecera) y contiene el de hoy por construcción | |
| D6 | Versión 0 de los ámbitos 8 y 11 | (a) fuera, salvo las 8 filas que hoy ya están por tener reparto · (b) fuera todas · (c) dentro todas | (a): (b) cambia la vista de hoy y (c) mete el vivo de F-157 en el catálogo | |
| D7 | Qué es una línea con reparto | (a) deja filas en `plan_mensual` · (b) tiene `planif` escrito | (a): (b) da 751 donde hay 690 en la 0698 v23. Y COMPLETO/PARCIAL se mira sobre `importe` <> 0 | |
| D8 | Qué versiones cuentan para el último cierre | (a) >= 1 con líneas y fecha, de cualquier tipo (incluye la v1 «CIERRE INICIAL_OBRA») · (b) además fuera las «CIERRE INICIAL_*» | (a): es D1 literal y da importe a la 0721 | |
| D9 | Grano de `master_importe_mensual` | (a) obra × ámbito × mes, hasta el mes del build · (b) solo la foto de hoy | (a): es el «al lado del mensual» de D3, y la foto es su último mes | |
| D10 | `diferencia_importe` | (a) total del último cierre − total de la temporal · (b) contra lo que la temporal reparte (`importe_con_reparto`) | (a), y se publica también (b) como columna: las dos cifras sin mezclarlas | |
| D11 | Un solo catálogo | (a) `02` lee `mart.master_versiones_tipadas` · (b) `02` no se toca y un test vigila que los dos coinciden | (a): es el alcance (4), y R11, R16 y la huella lo prueban | |
| D12 | La marca por línea | (a) vista con `EXISTS` (sin disco) · (b) tabla de ~4,6 M de filas | (a): el disco es compartido y por obra va por índice | |
| D13 | Cabecera duplicada en `obrfasamb` | (a) la de `ide` mayor, como `descompuestos` · (b) dos filas, como hoy | (a): hoy hay 0 casos y el grano queda único | |
| D14 | Ámbitos de la vista por partida | (a) coste y venta · (b) solo coste | (a): la venta sin reparto (0693 v20) también se pierde hoy | |

Queda fuera, y se avisa al humano: que la temporal se elija por TENER reparto en vez de por tipo (era
D2, revocada); el reparto incompleto dentro de una línea; la obra 1562946; y el `.pbix`.
