<!-- progress/review_F-057_pasada1.md -->
<!-- Pasada 1 TAL CUAL se commiteo en 5588845 como progress/review_F-057.md; movida aqui en la pasada 2 solo para que la pasada 2 quepa en el tope de 140 lineas. Contenido sin tocar. -->
Revision completa (pasada 1), sobre HEAD `fe5fb9c`; diff de F-057 = `cf03dad..HEAD`.

# F-057 · Review del esquema `personal`

**Veredicto: CHANGES_REQUESTED.** El SQL es correcto: no filtra, no multiplica,
no lee de `emp` mas que lo autorizado y la vista corta por `unidad = 'HORA'`.
**Fallan dos guardas que dicen vigilar y no vigilan**, justo en los dos riesgos
que justifican la feature (unidad y datos personales), y hay tres puntos de
propagacion olvidados. Todo reproducible y barato; nada exige tocar la base.

**Rigor:** `estandar` (declarado): fase RED, cobertura >= 80 %, mutacion.

## Rompiendolo a mano (copia en scratchpad, arbol intacto)

| Mutacion del SQL | Suite F-057 |
|---|---|
| Quitar `WHERE pl.unidad = 'HORA'` / cambiarlo a `IN ('HORA','MES')` | cae |
| `WHERE pl.unidad = 'HORA' OR pl.unidad = 'MES'` | **pasa** |
| Quitar `ELSE 'DESCONOCIDA'`, o `ELSE 'HORA'`, o `CASE h.ext` | cae |
| Añadir `WHEN 4 THEN 'HORA'` / `WHEN 5 THEN 'KM'` al CASE | **pasa** |
| Anteponer `WHEN 3 THEN 'HORA'` (los MES pasan a horas) | **pasa** |
| Lateral lee `emp.tarseg` (Seg. Social), `ban`, `bancue`, `sexo`, `telmov`, `ele`, `dir1`, `dircpo`, `esigpas`, `g3wpas`, `clamai` | **pasa (11 de 11)** |
| Lateral lee `emp.fecnac` / `estciv` / `tel` | cae |
| Lateral `SELECT emp.*` | **pasa** |
| Fuga completa: `seg_social` y `cuenta_banco` en DDL + INSERT desde `e.tarseg`/`e.ban` | **pasa (45/45 tests SQL)** |

Nombres reales de `emp`: `azure-apps/sigrid_tablas.md` linea 12137, y la ficha
de F-068 en `BACKLOG.md` los cita medidos en Azure (`tarseg`, `ban`, `esigpas`).

## Checkpoints

- **C1** [x] `init.sh` exit 0 (Evidencias). [x] ficheros del arnes.
- **C2** [x] una `in_progress`. [x] rama. [ ] `current.md` arrastra F-073..F-080:
  deuda PREEXISTENTE del lider (cambio 8). [x] `history.md`.
- **C3** [x] hexagonal y `sql/personal/NN_*.sql`. [x] ruta en primera linea.
  [x] sin prints, secretos ni dependencias. [x] `R-SIGRID-CON`, obra de la linea.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [ ] **R8 y R17 trazados pero sin vigilar** (cambios 1-3). [x] offline.
  [x] MANUAL con comando exacto. [x] dobles: solo `execute_sql_file` y
  `count_rows`, existentes en `PostgresClient`.
- **C4 bis** [x] rigor. [x] fase RED real (65 failed / 3 passed, tres trazas).
  [x] cobertura `[OK]` 94,7 %. [x] mutacion verificada (abajo). [x] >60 s:
  **campaña no reejecutada entera** (4.084,7 s y 2.906,6 s segun el informe);
  recalculo puro + reproduccion completa de la dirigida. [x] coste por mutante
  817 s y 969 s frente a bases ~740 y ~620 s. [x] sin «NO VALIDA», sin
  veredicto 0. [x] RM1: SHA `f6547dd`; despues solo cambian el test de T22 y
  `progress/`. [x] RM2 coherente. N/A RM5 (nivel `estandar`). [x] RM6: no se
  quito defensa. N/A campaña manual. [x] sin `PENDIENTE`. [ ] «Evidencias» sin
  nº de workers (cambio 7). [x] ningun N/A sin motivo.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [ ] T25 sin marcar con `init.sh` en verde (T23-T24 MANUAL, bien
  abiertas). [x] commit por tarea. [x] sin temporales propios. [x] features.

## Mutacion: verificacion independiente

- `alcance_de_feature("F-057")` + `generar_mutantes`: **4.569 lineas, 21
  ficheros, 349 mutantes**. Dirigida: **145 lineas, 12 mutantes**. Coinciden.
- **Dirigida reejecutada entera** sobre `git archive HEAD` en el scratchpad
  (tests `r24` + barrido de dataclasses de F-006): **9 muertos, 3 vivos**
  (lineas 125 `exc_info`, 132 `rows = 0`, 139 `round(...,3)`). Identico.
  `slots`/`frozen` mueren por el barrido de F-006: RM3 limpio.
- **Los tres «equivalentes» lo son**: solo tocan argumentos de `logger`, y
  `rows` sin destino no entra en `total_rows`. Aceptados. S3 muere: reproducido.
- **Lo que la campaña no ve**: solo muta Python, y la logica de la feature es
  SQL. Ahi estan los huecos de la tabla de arriba.

## Propagacion

[x] step (`build_aux`, `depends_on=["build_stg"]`). [x] orquestador: solo salta
dependientes de un FAILED (`orchestrator.py:59`) y nadie depende de
`build_personal`; va tras `build_stg`, fuera del camino del `mart`. [x] los tres
puntos de `main.py`. [x] `DEFAULT_CONSUMPTION_SCHEMAS` + `.env.example`; ningun
`.ps1` fija la variable. [x] `apply_grants` sin lista a mano.
[x] `ESQUEMAS_DEL_DATAMART` -> inventario real con los 4 objetos.
[x] `check-unicidad` / `check-relaciones --dry-run`: 3 claves y 5 relaciones de
`personal`. [x] `personal.yaml`, version 25. [x] puntos 13 y 14. [x] ARCHITECTURE,
CLAUDE.md, `azure-apps` (`5bd7742`).
[ ] **`infra/sql/02_roles.sql`**: tres listas de nueve esquemas sin `personal`.
[ ] **`docs/runbook_postgres_azure.md:149`** y **`00_global.yaml:6` y `:1082`**
(P4, publicada al MCP): «nueve esquemas».
Datos personales: [x] sin `SELECT *`; el lateral lee cinco columnas. [x] ficha
«CONTIENE DATOS PERSONALES: nombre, NIF y DNI» con fecha. Unidad: [x] la ficha
de `cantidad` lo advierte con 1.837.201,23.

## Cobertura requisito -> test

R1-R28 con `test_f057_rN_*` en verde. Huecos: **R8**, **R16/R17**, **R21**.

## Cambios requeridos

1. **`tests/test_f057_personal.py:320-341` (R8).** `COLUMNAS_VETADAS_DE_EMP`
   dice ser «nombres reales de Sigrid» y 14 de 19 no existen en `emp` (`nss`,
   `segsoc`, `iban`, `cuenta`, `banide`, `dirlin`, `codpos`, `movil`, `ema`,
   `logacc`, `ideacc`, `ipacc`, `recema`; `\bsex\b` no casa con `sexo`).
   Sustituir por **lista blanca**: el lateral sobre `raw.emp` selecciona
   EXACTAMENTE `{ide, dni, nomnom, nomape1, nomape2}`, sin `*`, y el `SELECT`
   exterior no usa otra `e.<col>`. Si se conserva lista negra, con nombres
   reales (`tarseg`, `ban`, `bancue`, `dir1`, `dircpo`, `sexo`, `telmov`,
   `ele`, `esigpas`, `g3wpas`, `clamai`...).
2. **`tests/test_f057_personal.py:451-497` (R16/R17).** Parsear todos los
   `WHEN n THEN 'X'` y exigir igualdad exacta con `{1:HORA, 2:DIA, 3:MES,
   19:UD}` + `ELSE 'DESCONOCIDA'`. Debe caer con `WHEN 4 THEN 'HORA'`,
   `WHEN 5 THEN 'KM'` y un `WHEN 3 THEN 'HORA'` antepuesto.
3. **`tests/test_f057_personal.py:518` (R21).** Exigir que entre `WHERE` y
   `GROUP BY` haya exactamente `pl.unidad = 'HORA'`.
4. **`infra/sql/02_roles.sql`**: `personal` en el `CREATE SCHEMA` (punto 4), en
   el `ARRAY` del GRANT (punto 5) y en la comprobacion del punto 6; «nueve» ->
   «diez». No rompe la nocturna, pero un reaprovisionamiento miente.
5. **`docs/runbook_postgres_azure.md:149`** y **`00_global.yaml` lineas 6 y
   1082**: «nueve esquemas» -> «diez».
6. **`sql/personal/01_recursos.sql`**, comentario del lateral: `raw` SI tiene
   `PRIMARY KEY (ide)` (`unicidad_sql.ESQUEMAS_CON_CLAVE_GARANTIZADA`).
7. **`impl_F-057.md`, «Evidencias»**: nº de workers (4) de las dos campañas.
8. **Al lider**: purgar de `current.md` las secciones de features cerradas.

Tras 1-3, pegar la salida de romper cada guarda, como en T22.

## Pendiente MANUAL del humano (no bloquea)

T23 y T24 de `impl_F-057.md`. `check-unicidad` y `check-relaciones` sin
`--todos` ya cubren `personal` (fichas de consumo). Confirmar que el `.env`
local, si fija `PG_CONSUMPTION_SCHEMAS`, incluye `personal`.

## Observaciones (no bloquean) y automejora

- `JOIN raw.con` INNER en `01_recursos.sql`: un `res` sin `con` se perderia.
- R17 ante un quinto `medide` EN ORIGEN no es testeable offline (R28).
  **Propuesta**: comprobacion nocturna que falle si `DESCONOCIDA` > 10 lineas.
- Incidente `git add -A` (`84e0ada`, `234b986`, `8a45f06`): declarado, no es
  defecto del entregable.
- **Automejora** (`CHECKPOINTS.md` C4, vale para `arnes-base`): una lista negra
  se valida contra nombres REALES del origen; para cerrar un conjunto, blanca.

## Evidencias

`bash harness/init.sh`: **exit 0, ENTORNO LISTO**; 5042 passed, 189 skipped
(427 s); cobertura 94,7 % (968/1022). La 1a pasada solo cayo en TAMAÑO por este
informe a medio escribir. Arbol sin tocar: lo no rastreado es de otros agentes.
