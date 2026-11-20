<!-- specs/F-127-mayor-analitico/design.md -->
# F-127 · Diseño

**Rigor: `critico`** (confirmado). Disparadores de «Niveles de rigor» de `CHECKPOINTS.md`:
**3, seguridad / datos personales** —decide qué filas del mayor analítico lee cada rol, y las CP
son cuentas por trabajador con su nombre en la descripción (`progress/spec_F-127.md` §4)— y
**4, contrato público** —cinco tablas nuevas que leen el MCP (estándar y total) y Power BI—.

Mediciones: `progress/spec_F-127.md`. Requisitos: `requirements.md`.

## 1. Encaje y límite

Todo vive en `build_contabilidad` (esquema módulo, F-056) con el patrón de DOS esquemas de F-135:
la copia completa en `contabilidad_restringida` (grupo autorizado y login total) y la general
filtrada en `contabilidad` (estándar). Sin ingesta nueva: `raw.apa` ya se trae entera cada noche.

```
raw.apa ─┬─► contabilidad_restringida.mayor_analitico ──► .saldos_cuenta_analitica_mes   (completo)
         │      ▲ C1/C2: contabilidad_restringida.mayor (02)   C3: raw.res.caaconide
         │      │ restringido = false
         └──────┴─► contabilidad.mayor_analitico ──► .saldos_cuenta_analitica_mes        (general)
                                                └──► .apuntes_analiticos_restringidos_mes (recuentos)
```

Límite de responsabilidad: es publicar un dato de Sigrid que ya está en `raw`; nada sale del
repositorio. El coste real de mano de obra por obra (F-061) y el cuadre documental (F-126) son
consumidores, no parte de esta feature.

## 2. Ficheros

**Crear** (en `etl_sigrid/infrastructure/postgres/sql/contabilidad/`, numeración siguiente a 07):
- `08_mayor_analitico.sql` — `contabilidad_restringida.mayor_analitico` + guarda de recuento (R1-R11).
- `09_saldos_analitica.sql` — `contabilidad_restringida.saldos_cuenta_analitica_mes` (R12).
- `10_mayor_analitico_general.sql` — `contabilidad.mayor_analitico` + guarda (R14, R15).
- `11_saldos_analitica_general.sql` — `contabilidad.saldos_cuenta_analitica_mes` (R16).
- `12_apuntes_analiticos_restringidos_mes.sql` — `contabilidad.apuntes_analiticos_restringidos_mes` (R17).
- `tests/test_f127_mayor_analitico.py` — todos los tests unit (nombres `test_f127_rN_*`).

**Modificar**
- `etl_sigrid/domain/restriccion_personal.py` — oráculo del criterio analítico (§3).
- `etl_sigrid/application/steps/build_contabilidad_step.py` — cinco `_SubStep` al final de
  `SUB_PASOS` (R18) y el docstring con los trece ficheros.
- `etl_sigrid/infrastructure/postgres/sql/contabilidad/00_setup.sql` — solo la cabecera (lista de tablas).
- `config/diccionario/contabilidad_restringida.yaml` (2 fichas) y `contabilidad.yaml` (3 fichas);
  `00_global.yaml`: `version` + 1 y el texto `regla` (no el `resumen`) de `R-PERFILES` y
  `R-SALDO-CONTABLE` (D6); `raw.yaml`: ficha de `raw.apa` (los asientos `ANALITICO`, `con.tip = 32`).
- `config/tables_sigrid.yaml` — el comentario de `apa` (cifras de hoy y que lo publica F-127).
- `config/settings.py` — solo comentarios: el bloque del perfil restringido dice que F-127 nació en
  `contabilidad` y que no hay nada que excluir (D3). Ningún valor cambia.
- `docs/ARCHITECTURE.md` — párrafo de `contabilidad` y el punto «El mayor analítico y F-127».
- `C:\Users\pgris\PycharmProjects\azure-apps\datamart_seg_anual.md` — commit aparte (§7).

**NO se tocan**: `01`-`07` de `contabilidad/` (ni una columna de F-056/F-135), `apply_grants_step.py`,
`infrastructure/postgres/grants.py`, `infra/sql/02_roles.sql` (ni esquemas ni roles nuevos),
`maestro/06_cuentas_analiticas.sql` (D5), el SQL de `personal/`, `harness/features.json` (estados del
líder) y `tests/test_f135_sql.py` (§8, nota al líder).

## 3. Dominio: el oráculo (`restriccion_personal.py`)

Constantes nuevas, con los literales que llevará el SQL (R10):
`TIPO_CON_ASIENTO = 20`, `TIPO_CON_ASIENTO_ANALITICO = 32`, `MOTIVO_CONTRAPARTIDA`,
`MOTIVO_APUNTE_SIN_RESOLVER`, `MOTIVO_APUNTE_RESTRINGIDO` (y reutiliza `MOTIVO_ASIENTO_PERSONAL`).

```python
@dataclass(frozen=True, slots=True)
class FilaAnalitica:
    apunte_id: int | None            # NULLIF(apa.apuide, 0)
    apunte_resuelto: bool            # el apunte existe en el mayor completo
    apunte_restringido: bool         # su `restringido` en el mayor completo
    asiento_personal: bool           # C2
    cuenta_es_contrapartida: bool    # C3 (y D7 si se aprueba)

def motivo_apunte_analitico(fila: FilaAnalitica) -> str | None: ...   # precedencia de R8
def es_apunte_analitico_restringido(fila: FilaAnalitica) -> bool: ...  # motivo is not None
```

Dominio puro. El SQL no lo llama; un test compara sus literales con los del SQL (patrón de R4 de F-135).

## 4. SQL

**`08_mayor_analitico.sql`** (una transacción; `DROP TABLE IF EXISTS … CASCADE` + `CREATE TABLE AS`):

```
cp        = SELECT DISTINCT caaconide FROM raw.res WHERE caaconide <> 0
            [D7-b: UNION cuentas con hab <> 0 en asientos con.tip = 32 cuyo centro es
             el de alguna CP actual]
ap        = asiento_id de contabilidad_restringida.mayor GROUP BY 1
            HAVING bool_and(clase_asiento = 'NORMAL') AND bool_or(restringido)
ana_obra  = por asiento con.tip = 32: la obra de sus filas NO cp; obra_imputada si count(DISTINCT obra) = 1
base      = raw.apa a
            LEFT JOIN raw.con asi ON asi.ide = a.conide                      -- empresa, tip
            LEFT JOIN contabilidad_restringida.mayor m ON m.apunte_id = NULLIF(a.apuide, 0)
            LEFT JOIN ap, cp, ana_obra
            LEFT JOIN maestro.centros_coste cc ON cc.centro_coste_id = NULLIF(a.cenide, 0)
            LEFT JOIN raw.con ca ON ca.ide = NULLIF(a.cueide, 0)            -- código y descripción
```

Todas las uniones van por clave primaria o por conjuntos `DISTINCT`/agrupados: nada multiplica
(medido: 722.631 filas = `count(DISTINCT ide)`). Columnas en este orden: `apunte_analitico_id`,
`asiento_id`, `tipo_asiento`, `codigo_asiento`, `posicion`, `fecha`, `ejercicio`, `mes`, `empresa_id`,
`centro_coste_id`, `codigo_centro`, `obra_id`, `codigo_obra`, `clave_obra`, `cuenta_analitica_id`,
`codigo_cuenta_analitica`, `descripcion_cuenta_analitica`, `es_contrapartida_recurso`, `concepto`,
`documento`, `punteo`, `debe`, `haber`, `importe`, `saldo_acumulado`, `apunte_id`, `cuenta_id`,
`codigo_cuenta`, `obra_imputada_id`, `clave_obra_imputada`, `restringido`, `motivo_restriccion`,
`saldo_acumulado_visible`. Importes `NUMERIC(18,2)` desde `double precision` (no `ROUND(double)`).
Fecha con `contabilidad.fn_fecha(a.fec)`. `clave_obra = empresa || '-' || codigo_obra` (F-056).
PK `apunte_analitico_id`; índices `(cuenta_analitica_id, fecha)`, `(empresa_id, codigo_cuenta_analitica, fecha)`,
`(obra_id)`, `(obra_imputada_id)`, `(apunte_id)`, `(asiento_id)` y parcial `(restringido) WHERE restringido`.
`COMMENT ON TABLE`. Al final, `DO $$` con la guarda de R2 (`count(*)` frente a `raw.apa`).

**`09_saldos_analitica.sql`**: lee solo `contabilidad_restringida.mayor_analitico`.
`GROUP BY COALESCE(cuenta_analitica_id, 0), COALESCE(centro_coste_id, 0), empresa_id, ejercicio, mes`;
`saldo_acumulado` = ventana por (cuenta, centro, empresa) ordenada por ejercicio y mes. PK la clave de R12.
Sin columnas por clase: no hay cierres ni aperturas (medido; la ficha lo dice).

**`10_mayor_analitico_general.sql`**: `WHERE NOT restringido`, columnas de R14 en el mismo orden,
`saldo_acumulado_visible AS saldo_acumulado`, mismos índices salvo el parcial. Guarda `DO $$` de R15:
0 filas cuya cuenta esté en el conjunto CP (recalculado igual que en 08), 0 filas con `apunte_id` cuyo
apunte sea restringido o no exista en el mayor completo, y general + restringidas = completo.

**`11_saldos_analitica_general.sql`**: como `06_saldos_general.sql`: `FILTER (WHERE NOT restringido)`,
`HAVING` con algo visible, `num_apuntes_restringidos` e `incompleto` al final (R16).

**`12_apuntes_analiticos_restringidos_mes.sql`**: como `07`: por empresa, ejercicio y mes,
`num_apuntes`, `num_asientos` y una columna por motivo (`num_contrapartida`, `num_apunte_restringido`,
`num_asiento_personal`, `num_apunte_sin_resolver`). Sin importes (D5 de F-135: el importe por mes
sería la masa salarial).

## 5. Permisos (R19, R20)

Nada nuevo en `apply_grants`: `contabilidad_restringida` ya está en `PG_VETOED_SCHEMAS` y
`PG_RESTRICTED_SCHEMAS`; `contabilidad`, en el consumo y FUERA de `PG_PERFIL_RESTRINGIDO_SCHEMAS`
y del postventa (F-146), que la nocturna veta por catálogo. `objetos_vigilados` solo mira los
esquemas del perfil, así que «mayor» en el nombre no dispara nada. **No se añade a
`PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`**: R7 de F-141 rechaza excluir un objeto de un esquema que no
se le concede y la nocturna fallaría (D3). Los tests de R19 lo fijan sobre `config/settings.py`.

## 6. Riesgos y alternativas descartadas

- **Publicar en `personal`** (sugerido en la ficha): lo lee el rol estándar, contradice R23 de F-135. D1.
- **Vista en vez de tabla**: el MCP corta a 30 s y `raw.apa` no tiene índice por cuenta (motivo de F-056).
- **Partir por clase como el mayor financiero**: no hay cierres ni aperturas en `apa` (0 de 639.034
  apuntes enlazados); inventar columnas de clase vacías confundiría.
- **La CP histórica**: C3 mira la CP ACTUAL del recurso; 7 cuentas de los centros de CP con abonos
  de partes (324 filas, 481.679 €) no son CP hoy. D7. Otras 9 con abono en asientos `ANALITICO`
  están en centros de obra (22 filas): cargos corregidos, no CP; D7-b no las toca.
- **CP compartidas**: 430 de las 853 CP las comparten hasta 8 recursos; el cruce con partes va por
  CP (suma de sus recursos), no por recurso. Lo dice la ficha (R23).
- **El saldo de una CP en 2026 no significa lo mismo**: sin nómina desde abril y sin imputación de
  partes desde agosto. La ficha da las fechas; el sentido lo confirma Juan (`progress/spec_F-127.md`).
- **Coste**: +1-3 min estimados y ~0,5 GB en el PostgreSQL compartido (`psql-albaranes-rs9k2`, sin
  cambios de servidor). Se mide en T13 antes de cerrar.

## 7. Frontera

**¿Cruza la frontera del proyecto? Sí**, solo por lo que publica: cinco tablas nuevas en dos esquemas
que ya existen y que el MCP ya tiene en su lista blanca (`contabilidad` y `contabilidad_restringida`
aparecen en `contexto_bbdd`). Sin esquemas, roles, grants, variables de entorno ni endpoints nuevos;
sin cambios en `mcp-bbdd` (su diccionario se refresca al publicar y reiniciar, como siempre). Se
actualiza `azure-apps/datamart_seg_anual.md` (tabla de objetos por perfil y sección de contabilidad),
en commit aparte, con `git pull --rebase` antes; el push lo hace el humano.

## 8. Nota al líder (no es tarea del implementer)

Pasar F-127 a `spec_ready` pone en rojo `tests/test_f135_sql.py::test_f135_r23_…` (exige `pending`
o `todo`). Hay que arreglarlo en `dev` antes de lanzar el implementer, como el 2026-11-19.

## Decisiones

Spec aprobada por el humano el 2026-11-20 («ok» al resumen de la spec), con todas las opciones recomendadas. D5 se da de alta como F-167 y las preguntas de D8 se envían a Juan Romero sin esperar respuesta.

| Decisión | Opciones | Recomendado | Decidido |
|---|---|---|---|
| D1. Dónde se publica | (a) completo en `contabilidad_restringida` y general filtrado en `contabilidad` (R23 de F-135); (b) en `personal` (lo lee el estándar); (c) solo el completo | (a) || (a) · 2026-11-20, humano: «ok» |
| D2. Nombres | (a) `mayor_analitico`, `saldos_cuenta_analitica_mes`, `apuntes_analiticos_restringidos_mes`; (b) otros | (a) || (a) · 2026-11-20, humano: «ok» |
| D3. Perfil restringido (obligación de F-141) | (a) por el veto de esquema de F-146, fijado por test y comprobado con `has_table_privilege`; el acceptance «excluido en su lista» se lee así; (b) añadirlo a `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES` (hace FALLAR la nocturna) | (a) || (a) · 2026-11-20, humano: «ok» |
| D4. La obra de un abono de CP | (a) `obra_imputada_id` / `clave_obra_imputada`: la única obra de cargo del asiento `ANALITICO` (37.202 de 38.612 filas CP); (b) sin columna, la ficha explica unir por `asiento_id` | (a) || (a) · 2026-11-20, humano: «ok» |
| D5. La descripción de 758 CP lleva el nombre del trabajador y ya la publica `maestro.cuentas_analiticas` (estándar y perfil restringido) | (a) ficha nueva aparte, priorizada por el humano; (b) enmascararla en F-127 (cambia F-107); (c) aceptarlo | (a) || (a (F-167)) · 2026-11-20, humano: «ok» |
| D6. Regla dura | (a) sin regla nueva: frontera en las fichas y una línea en la `regla` de `R-PERFILES` y `R-SALDO-CONTABLE` (presupuesto de F-147); (b) regla `R-MAYOR-ANALITICO` | (a) || (a) · 2026-11-20, humano: «ok» |
| D7. Qué cuenta es CP (C3) | (a) solo `raw.res.caaconide` actual (853); (b) además las cuentas de un centro de CP con abono en un asiento `ANALITICO` (7 más, 324 filas): falla cerrado, «restringe DE MÁS» | (b) || (b) · 2026-11-20, humano: «ok» |
| D8. Preguntas a Juan (nómina desde abril, partes desde agosto, qué es «por repartir») | (a) enviarlas y publicar sin esperar: la ficha da las fechas medidas; (b) esperar respuesta | (a) || (a) · 2026-11-20, humano: «ok» |
