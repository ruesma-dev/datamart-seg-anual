# F-040 · Diseño (fase 1)

Requisitos: `requirements.md`. Columnas, listas exactas y mapa de tests: `design_detalle.md`.
Cifras: `progress/spec_F-040.md`. Precedentes que se copian: `postventa` (F-156: módulo con dos
esquemas, `SUB_PASOS`, dominio oráculo, guarda `DO` de datos personales), `compras_restringida`
(F-138: esquema solo del total, sin login nuevo), `tesoreria` (F-037: `fn_fecha`, estados).

## 1. Encaje y límite del microservicio

Lectura de Sigrid y publicación en el datamart: dentro del límite. No cruza a `sigrid-api`,
`albaranes` ni `partes`. Cruza a `mcp-bbdd` solo en su lista blanca (`config.yaml`: un esquema
nuevo no aparece sin tocarla): aviso al humano (§ 9, paso 8), sin pliego (no hay herramienta ni
login nuevos). Módulo nuevo **`ventas`** (D3), el DÉCIMO build de negocio, que construye dos
esquemas: `ventas` (general) y `ventas_restringida` (lo personal del cliente). Lee `raw`,
`maestro.centros_coste` y, SOLO en vistas, `tesoreria.efectos` y `tesoreria.devengo_corte_obra`
(tablas que `tesoreria` no dropea: R14 de F-037). Nadie depende de él.

## 2. Ficheros

**Crear**: `etl_sigrid/domain/ventas.py`; `etl_sigrid/infrastructure/postgres/sql/ventas/00_setup.sql`
… `07_guardas.sql` (§ 5); `etl_sigrid/application/steps/build_ventas_step.py`;
`config/diccionario/ventas.yaml` y `ventas_restringida.yaml`; `tests/test_f040_*.py` (§ 10).

**Modificar**: `config/tables_sigrid.yaml` (§ 3); `main.py` (§ 5); `config/settings.py` y
`.env.example` (§ 6); `infra/sql/02_roles.sql` (§ 6); `etl_sigrid/domain/diccionario.py`
(`ESQUEMAS_DEL_DATAMART` 18 → 20); `config/diccionario/raw.yaml` y `00_global.yaml` (§ 7);
`docs/ARCHITECTURE.md`, `CLAUDE.md`, `docs/runbook_postgres_azure.md` (§ 15 nueva) y
`../azure-apps/datamart_seg_anual.md` (§ 8); los tests que fijan censos y listas (detalle § C).

**Borrar**: `config/tables_sigrid_venta_snippet.yaml` (obsoleto; lo dice el commit).

**NO se tocan**: `sql/retenciones/*` (`v_src_lineas_venta` se activa sola), `sql/tesoreria/*`
(07 sigue leyendo `raw.dvf.cenide`/`totbas`), `sql/compras/*`, `sql/mart/*`, `sql/cierre/*`,
`sql/postventa/*`, `grants.py` y `apply_grants_step.py` (son de listas desde F-135/F-136: veto,
concesión y verificación salen de `settings`, como en F-138) y `config/hipotesis_caja.yaml`.

## 3. Ingesta: `config/tables_sigrid.yaml` (+7 tablas, 93 → 100; `dvf` 9 → 35 columnas)

Todas `incremental_column: null`, `where: null` y comentario con cifras del 2026-11-06/07. Listas
exactas: detalle § A. `cli` lleva 13 columnas de negocio + 7 de contacto (D6): `dir1`, `dir2`,
`dircpo`, `dir`, `tel`, `tel2`, `ele`; quedan fuera las bancarias, `fecnac`, `numseg`, `clamai`,
`g3wpas` (contraseña), `fax`, `telsin`/`tel2sin` (duplicados), `dirtex`, `web`, `munide`/`proide`/
`paiide` (sus maestros no están en `raw`), los correos de facturación y `dniper`/`nom*` (vacíos).
`dvf` suma a las 24 de negocio `entcif`, `entres` y las nueve `dir*` (`diremp1-3`, `dircon1-3`,
`dirdir1-3`; `dircon*` vacías hoy, entran por ser «las `dir*`» de D6); nunca `ban*`, `emptex`.
`res` de `dvfpro`/`cerpro` entra en `raw` (vetado a todos los perfiles, F-135).

## 4. Dominio: `etl_sigrid/domain/ventas.py` (nuevo, sin dependencias)

Oráculo de las reglas que el SQL repite; los tests comparan los LITERALES compartidos (patrón,
clases, estados, prefijos) entre el módulo y el SQL, como F-156.

- Constantes: `TIP_CERTIFICACION = 54`, `TIP_FACTURA_VENTA = 11`, `DOCDESTIP_FACTURA_VENTA = 11`,
  `ESTADOS_CERT_CUENTAN = (2, 3, 4)`, `PATRON_NIF_PERSONA = r"^[0-9KLMXYZ][0-9]{7}[A-Z]$"`,
  `CLASE_COEFICIENTES = 0`, `CLASE_RETESP = 1`, **`CLASES_GARANTIA = (4, 5)`** (D4, el ÚNICO punto
  de decisión: comentario con la pregunta pendiente a Juan Romero), `COLUMNAS_CLI_CONTACTO`,
  `COLUMNAS_PROHIBIDAS_CLI`, `COLUMNAS_PERSONALES_DVF` y `PREFIJOS_PROHIBIDOS_EN_VENTAS =
  ("direccion", "telefono", "correo", "cif_cabecera", "nombre_cabecera")`.
- `normalizar_cif(cif)`: mayúsculas, sin espacios/guiones/puntos; vacío → `None`.
- `es_persona_fisica(cif_normalizado, perfis) -> bool` (R6).
- `cif_valido(cif_normalizado) -> bool` (R8): DNI con letra `TRWAGMYFPDXBNJZSQVHLCKE[n % 23]`; NIE
  con X/Y/Z → 0/1/2 y la misma letra; K/L/M y CIF de sociedad (`[ABCDEFGHJNPQRSUVW]` + 7 dígitos +
  `[0-9A-J]`) solo por forma.
- `clase_recargo(reccla) -> str`, en este orden: `CLASE_COEFICIENTES` → `COEFICIENTES`; en
  `CLASES_GARANTIA` → `GARANTIA`; `CLASE_RETESP` → `RETESP`; resto o NULL → `OTRAS`. Si Juan dice
  que el `RETESP` es garantía, basta `CLASES_GARANTIA = (1, 4, 5)` (y el literal del SQL, que un
  test obliga a igualar, R12): el `RETESP` pasa de columna sola, `retencion_retesp` queda a 0 y las
  cuatro columnas siguen repartiendo el total sin solaparse (guarda R25).
- `estado_seguimiento(estado_cert, num_facturas, num_efectos, emitido, cobrado) -> str` (R18): estado
  fuera de `ESTADOS_CERT_CUENTAN` → `BORRADOR`; sin factura → `SIN_FACTURA`; sin efectos no BAJA →
  `FACTURADA_SIN_EFECTO`; cobrado ≤ 0 → `PENDIENTE_COBRO`; cobrado < emitido − 0,01 →
  `COBRADA_PARCIAL`; si no → `COBRADA`.

## 5. SQL: `etl_sigrid/infrastructure/postgres/sql/ventas/` y aplicación

`DROP TABLE IF EXISTS ... CASCADE` + `CREATE TABLE AS` (nadie de fuera depende de sus tablas; las
vistas se recrean en `05`). Cabecera con qué construye y de qué lee. Agregar ANTES de unir (guarda
de grano). Importes de `raw` en `double precision`: `::NUMERIC(18,2)` antes de `ROUND`/`SUM`.
Columnas de cada objeto: detalle § B.

- **`00_setup.sql`** — `CREATE SCHEMA IF NOT EXISTS ventas` y `ventas_restringida`; funciones
  `IMMUTABLE`: `ventas.fn_fecha(BIGINT)` (copia deliberada de `tesoreria.fn_fecha`; un test compara
  los cuerpos), `fn_cif_normalizado(TEXT)`, `fn_es_persona_fisica(TEXT, INT)`, `fn_cif_valido(TEXT)`
  y `fn_clase_recargo(INT)` (con los literales de `PATRON_NIF_PERSONA` y `CLASES_GARANTIA`).
- **`01_clientes.sql`** — `ventas.clientes` (R5-R8) desde `raw.cli` + `raw.con` (tip 4) y
  agregados de `raw.dvf`, `raw.cer` y `raw.obr.entide`. Persona física: `nombre` tal cual (D2),
  `cif` y `cif_normalizado` NULL; `cif_valido` y `cif_repetido`, calculados antes de anular.
- **`02_facturas.sql`** — `ventas.facturas` (R9-R11): `raw.dvf` + `raw.con` (código, empresa,
  `est`, `fecbaj`) + `raw.conest` (tip 11) + `maestro.centros_coste` + `ventas.clientes` (nombre y
  `cif_cliente`, ya anulado para personas). Recargos de `raw.dvfrec` agregados antes de unir,
  `SUM(cuo)` filtrado por `ventas.fn_clase_recargo`. `ventas.factura_lineas` (R13; `descripcion`
  NULL si la factura es de persona física) y `ventas.factura_recargos`.
- **`03_certificaciones.sql`** — `ventas.certificaciones` (R14-R15) y `certificacion_recargos`:
  `raw.cer` + `raw.con` + `raw.conest` (tip 54) + `raw.obrctr` + líneas de `raw.cerpro` y recargos de
  `raw.cerrec` agregados antes de unir. `base_origen_contrato` = `SUM(base) FILTER (WHERE cuenta)
  OVER (PARTITION BY contrato_id ORDER BY numero, certificacion_id)`, NULL si no cuenta o sin contrato.
- **`04_enlace.sql`** — `ventas.certificacion_factura` (R16): `raw.cerprodes` (`docdestip` = 11) →
  `raw.cerpro` → par (`cerpro.docide`, `docdeside`), `JOIN raw.dvf` contra destinos huérfanos.
  `ventas.cobertura_enlace` (R20): tres filas (`CERTIFICACION_FACTURA`, `FACTURA_EFECTO`,
  `EFECTO_FACTURA`); el eslabón de efectos lee `raw.cob` (no espera a otro paso).
- **`05_vistas.sql`** — `v_factura_cobro` (R17: ⟕ `tesoreria.efectos` COBRO), `v_seguimiento_certificacion`
  (R18: `CASE` que replica el dominio; `factura_compartida`) y `v_contraste_certificado_obra` (R19:
  `tesoreria.devengo_corte_obra` VENTA ⟕ Σ `base` de las certificaciones que cuentan; sin suelo).
- **`06_restringida.sql`** — `ventas_restringida.clientes_contacto` (R21: `raw.cli`, CIF íntegro y
  contacto), `factura_cabecera` (R22: `raw.dvf` `entres`, `entcif` y `dir*`, con `cliente_id` y
  `es_persona_fisica`) y `factura_lineas_persona` (R23: `raw.dvfpro` de facturas de persona física,
  descripción íntegra). Ninguna vista: tablas que solo lee el total.
- **`07_guardas.sql`** — un `DO` (R24, R25), `RAISE EXCEPTION` con las cifras: recuentos frente a
  `raw` (5 tablas); Σ `base` = Σ `raw.dvf.totbas` al céntimo; reparto de recargos (4 columnas = Σ
  `cuo`, facturas y certificaciones); ningún `cif`/`cif_cliente` de persona física ni con forma de
  NIF de persona en `ventas.clientes`/`facturas`; ninguna `descripcion` de línea de persona física;
  ninguna columna de `information_schema.columns` del esquema `ventas` con un prefijo de
  `PREFIJOS_PROHIBIDOS_EN_VENTAS`.

**Aplicación.** Nuevo `build_ventas_step.py`: `BuildVentasStep`, `name = "build_ventas"`,
`depends_on = ("ingest_raw",)`, `SUB_PASOS` con los ocho ficheros (patrón `build_postventa_step.py`,
`target_schema` `ventas` o `ventas_restringida` según el sub-paso). **`main.py`**: el paso en
`build_pipeline_steps` tras `BuildRetencionesStep` (comentario: décimo build, nadie depende de él),
en `PASOS_CON_PERMISOS`, y el comando `build-ventas`; la docstring y el mapa de `CLAUDE.md` pasan a
diecisiete pasos. `LECTURAS_PARA_REANUDAR` (F-148) no cambia: no lee `stg` ni `mart`.

## 6. Permisos (D5 y el esquema `ventas_restringida`)

Patrón «módulo + `_restringida`» de F-135/F-037/F-138: los permisos de PostgreSQL van por esquema,
así que lo que el estándar no debe leer vive en un esquema que nunca se le concede. Sin login ni
grupo nuevos: lo lee el grupo `sigrid_dm_autorizado_ro` y el total por pertenencia.

- **`config/settings.py`**: `ventas` en `DEFAULT_CONSUMPTION_SCHEMAS`; `ventas_restringida` en
  `DEFAULT_VETOED_SCHEMAS` y `DEFAULT_RESTRICTED_SCHEMAS`, con su línea en el comentario de cada
  lista (F-040, D2/D6 del humano). NO en `DEFAULT_TOTAL_VETOED_SCHEMAS` (solo `raw`). Las listas del
  perfil restringido y del postventa NO cambian: son explícitas y `apply_grants` les veta cada
  noche todo esquema del catálogo que no esté en ellas, `ventas` y `ventas_restringida` incluidos.
- **`.env.example`**: `PG_CONSUMPTION_SCHEMAS`, `PG_VETOED_SCHEMAS`, `PG_RESTRICTED_SCHEMAS` al día.
- **`etl_sigrid/domain/diccionario.py`**: los dos esquemas en `ESQUEMAS_DEL_DATAMART`.
- **`infra/sql/02_roles.sql`** (como F-138):
  1. Bloque de esquemas (con `SET ROLE sigrid_dm_etl`): `CREATE SCHEMA IF NOT EXISTS ventas` y
     `ventas_restringida`, con su comentario F-040. Tienen que existir antes del primer
     `build-ventas`: sin el veto, la ventana hasta la nocturna dejaría lo personal sin proteger.
  2. Punto 5: `'ventas'` en el `ARRAY` de consumo (un test ya lo compara con
     `DEFAULT_CONSUMPTION_SCHEMAS`). Punto 5 ter: `'ventas_restringida'` en los DOS `ARRAY` de
     vetados al estándar (administrador y `sigrid_dm_etl`); NO en el `ARRAY['raw']` del total.
  3. Concesión al autorizado: `GRANT USAGE`, `GRANT SELECT ON ALL TABLES` y `ALTER DEFAULT
     PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA ventas_restringida GRANT SELECT ON TABLES TO
     sigrid_dm_autorizado_ro`, con el comentario «F-040: y lo personal del cliente, igual».
  4. Comprobaciones finales: los dos esquemas en la consulta de propietarios;
     `ventas_restringida` en las dos consultas del estándar (`lee = f`, ahora seis filas); columna
     `ventas_restringida = t` del total; `ventas` y `ventas_restringida` = `f` en las del perfil
     restringido y del postventa; cabecera del fichero y comentario del 5 ter al día.
- **Tests** (`tests/test_f040_grants.py`, R27-R29): las listas de `settings` y `.env.example`; los
  `ARRAY` y los `GRANT` de `02_roles.sql` frente a `DEFAULT_VETOED_SCHEMAS` y
  `DEFAULT_RESTRICTED_SCHEMAS`; `ventas_restringida` fuera del consumo, del total vetado y de los
  perfiles; y que `build_veto_statements`/`build_restricted_grant_statements` de `grants.py` la
  incluyen sin tocar el código (dobles de cliente, sin BBDD).

## 7. Diccionario

- **Nuevo** `config/diccionario/ventas.yaml`: las 8 tablas y 3 vistas, con las trampas: certificado ≠
  facturado ≠ cobrado; a cuenta sin recargos frente a base con coeficientes; N:M
  certificación-factura (no sumar lo cobrado por certificación si `factura_compartida`); `AGR` no
  atribuido; `cif` NULL de persona física no es «sin CIF»; garantía provisional (D4) y el `RETESP`
  aparte; contraste solo para las obras de la receta (el completo, F-160).
- **Nuevo** `config/diccionario/ventas_restringida.yaml`: las 3 tablas; cabecera como la de
  `postventa_restringida.yaml` (qué es personal, quién lo lee, cómo se cruza con `ventas` por
  `cliente_id`/`factura_id`/`linea_id`).
- `raw.yaml`: fichas de `cli`, `cer`, `cerpro`, `cerrec`, `cerprodes`, `dvfpro`, `dvfrec` (qué traen
  de personal y qué NO) y `dvf` a 35 columnas.
- `00_global.yaml`: versión +1 (hoy v73 → v74; si F-104 o F-159 suben antes, la siguiente),
  entradas de esquema `ventas` y `ventas_restringida` (`para_que_sirve` ≤ 350; la segunda, «solo
  perfil total»); `R-VENTAS-TRES-CIFRAS` y `R-VENTAS-RESTRINGIDA` (bloqueantes, `resumen` 40-250,
  `entrega: resumen`; la segunda: el nombre es público, lo demás del cliente persona y toda
  dirección solo en `ventas_restringida`; «permission denied» no se rodea, nunca se cruza por
  nombre para sacar un NIF); `ventas` y `ventas_restringida` en el ámbito de `R-PERFILES` (y su
  texto: el restringido tampoco lee `ventas`); `R-FRESCURA` con `build_ventas` (diez esquemas,
  catorce con los restringidos). Si el presupuesto de F-147 se pasa, se sube con su motivo.

## 8. Documentación

`docs/ARCHITECTURE.md` (párrafo de `ventas` y `ventas_restringida`, censo 100, «Lo que Sigrid NO
guarda»: `obrcer` vacía, `cer.idefac`/`feccob` a 0, `cli` sin clasificación), mapa de `CLAUDE.md`,
`docs/runbook_postgres_azure.md` **§ 15 «Alta de `ventas_restringida` (F-040)»** (pasos 2 y 5 del §
9, sin secretos: ningún `*_PWD`, todos los logins SIN CAMBIOS; esperado y vuelta atrás) y
`../azure-apps/datamart_seg_anual.md` (consume 7 tablas más, publica dos esquemas).

## 9. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz. `<PY>` = `.venv/Scripts/python.exe`; `<Q>` = consulta de
solo lectura (`main._get_pg()`, `_bootstrap_done = True`, `filas_solo_lectura`); `$dsn`, la del
administrador (cabecera de `02_roles.sql`).

0. Anotar el tag de la imagen del job y `git rev-parse main`. Comprobar (solo nombres) si el job
   fija `PG_CONSUMPTION_SCHEMAS`, `PG_VETOED_SCHEMAS` o `PG_RESTRICTED_SCHEMAS`: si los fija, se
   cambian allí con el valor de `.env.example` en el paso 1. Anotar `retenciones.movimientos`
   CLIENTE por estado (recuento e importe) con `<Q>`.
1. `infra/70_build_image.ps1` y `infra/85_update_job.ps1 -Tag <tag nuevo>`; comprobar el tag.
2. **Humano, como administrador**: `psql -X -v ON_ERROR_STOP=1 -f infra/sql/02_roles.sql $dsn`
   SIN ninguna variable `*_PWD` (runbook § 15). Esperado: los cinco logins SIN CAMBIOS; `COMMIT`;
   `ventas` y `ventas_restringida` con dueño `sigrid_dm_etl`; el estándar `lee = f` en las seis
   vetadas; el total `ventas_restringida = t`; el restringido y el postventa `f` en las dos.
3. `<PY> main.py ingest --table <t> --full` para `cli`, `cer`, `cerpro`, `cerrec`, `cerprodes`,
   `dvfpro`, `dvfrec` y `dvf`; `<PY> main.py check-raw-recuentos` → sin filas de menos.
4. `<PY> main.py build-ventas` → SUCCESS (anotar duración, < 60 s) y `<PY> main.py apply-grants` →
   `verificacion`, `verificacion_total`, `verificacion_restringido` y `verificacion_postventa` ok.
5. Negativa y positiva con los logins reales (runbook § 15): estándar → `permission denied` en
   `ventas_restringida.clientes_contacto` y una fila en `ventas.clientes`; total → una fila en las
   dos; restringido → `permission denied` en las dos.
6. Cifras con `<Q>`: `ventas.facturas` ~15.734, `certificaciones` ~6.308, `clientes` ~1.210;
   `ventas.cobertura_enlace`; `retenciones.movimientos` CLIENTE igual que en el paso 0 (R34).
7. `<PY> main.py publicar-diccionario` (escritura en Azure: la autoriza el humano);
   `check-diccionario`, `check-declarados` y `check-unicidad --timeout 300` → OK.
8. Aviso a `mcp-bbdd`: `ventas` (estándar y total) y `ventas_restringida` (solo total) a su lista
   blanca y reinicio (cachea el diccionario). Anotado en `progress/current.md`.
9. Primera nocturna: `<PY> main.py timings` (ingesta nueva y `build_ventas`).

**Vuelta atrás**: `85_update_job.ps1 -Tag <tag del paso 0>`; como `sigrid_dm_etl`, `DROP SCHEMA IF
EXISTS ventas_restringida CASCADE; DROP SCHEMA IF EXISTS ventas CASCADE; DROP TABLE IF EXISTS
raw.cli, raw.cer, raw.cerpro, raw.cerrec, raw.cerprodes, raw.dvfpro, raw.dvfrec;` y `ingest --table
dvf --full` con la imagen anterior (vuelve a 9 columnas, sin lo personal). El veto de
`02_roles.sql` puede quedarse: está guardado por `to_regnamespace`.

## 10. Tests (sin red ni BBDD)

`tests/test_f040_dominio.py`, `_ingesta.py`, `_sql.py`, `_pipeline.py`, `_grants.py`,
`_diccionario.py` y `_frontera.py` (R30: `git diff main -- sql/retenciones sql/tesoreria` vacío;
salta con aviso sin git). Qué requisito cubre cada uno y los tests existentes que hay que poner al
día: detalle § C.

## 11. Riesgos y alternativas descartadas

- **Enlace por `cer.idefac`/`feccob`**: a 0 en las 6.308. **Por `dvfpro.linoriide`**: no dice el
  tipo de destino; queda como columna y `cerprodes` es el enlace (100 % con destino válido).
- **Repartir lo cobrado entre certificaciones**: N:M sin regla; se marca `factura_compartida`.
- **Enmascarar el nombre de la persona física** (D2 = A original): descartado por el humano; el
  nombre es público y lo demás va a `ventas_restringida`.
- **`REVOKE` por columna o tabla en `ventas`**: el total hereda del estándar y lo perdería también,
  y Power BI no distingue; un esquema aparte es el patrón probado (F-138).
- **Nombre de la factura**: `ventas.facturas` publica el nombre ACTUAL del cliente (`cli.raz`); el
  de la cabecera (`entres`, distinto en 571 facturas: renombres) solo en `ventas_restringida` (D6).
- **Rellenar `tercero_cif` de `tesoreria.efectos` y `entidad_cif` de retenciones**: fuera; se llega
  por `ventas.clientes`. Lo segundo es de F-104.
- **Cobro vía `AGR`**: no atribuible hasta que F-104 explique los efectos con `fecbaj`; la cobertura
  lo cuantifica cada noche (R20).
- **Ventana**: < 1 % (`progress/spec_F-040.md` § 1); las columnas nuevas de `dvf` y `cli` son texto
  corto (máx. 148 caracteres medido en `dirdir1`). La nocturna termina a las 04:56: F-040 suma segundos.
- **Ventana de exposición**: si el build corriera antes que `02_roles.sql`, `ventas_restringida`
  nacería sin la concesión al autorizado hasta `apply-grants` (el estándar no la lee: sin USAGE);
  por eso el paso 2 va antes del 4, el 4 lanza `apply-grants` a mano y, en `run-all`, el paso está
  en `PASOS_CON_PERMISOS` (permisos al terminar, F-148).
