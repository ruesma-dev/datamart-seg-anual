# F-040 · Diseño (fase 1)

Requisitos: `requirements.md`. Cifras: `progress/spec_F-040.md`. Precedentes que se copian:
`postventa` (F-156: esquema módulo, `SUB_PASOS`, dominio oráculo, enmascarado), `tesoreria`
(F-037: `fn_fecha`, precedencia de estado) y `compras` (F-128: clases de recargo).

## 1. Encaje y límite del microservicio

Es lectura de Sigrid y publicación en el datamart: dentro del límite. No cruza a `sigrid-api`,
`albaranes` ni `partes`. Cruza a `mcp-bbdd` solo en su lista blanca (`config.yaml`: un esquema
nuevo no aparece sin tocarla) → aviso al humano en T15, sin pliego (no hay herramienta nueva).
Módulo nuevo **`ventas`** (D3), el DÉCIMO build de negocio: lee `raw`, la vista
`maestro.centros_coste` y, SOLO en vistas que se resuelven al consultar, `tesoreria.efectos` y
`tesoreria.devengo_corte_obra` (las dos son tablas que `tesoreria` no dropea: R14 de F-037).
Nadie depende de él.

## 2. Ingesta: `config/tables_sigrid.yaml` (+7 tablas, 93 → 100; `dvf` ampliada)

Todas `incremental_column: null`, `where: null`, comentario con cifras del 2026-11-06.

| Tabla | Cómo | Columnas |
|---|---|---|
| `cli` | `include_columns` | `ide, tipcif, cifpai, cif, raz, perfis, cenide, taride, secide, pagide, efeide, cueide, cueretide` |
| `cer` | `include_columns` | `ide, cla, entide, cenide, obride, ctride, expide, fas, fecdoc, fecfac, estfac, idefac, docoriide, pagide, efeide, ivaide, impbru, impnet, impdes, imprec, totbas, totiva, totdoc, tot, totpag, totproori, totprcori` |
| `cerpro` | `include_columns` | `ide, docide, pos, res, can, pre, tot, ivaide, ivacuo, cenide, obride, paride, docoritip, docoriide, linoriide, imporiori, imporiant, canoriori` |
| `dvfpro` | `include_columns` | `ide, docide, pos, res, can, pre, tot, ivaide, ivacuo, cenide, obride, paride, docoritip, docoriide, linoriide, unimed, proide` |
| `cerrec`, `dvfrec` | `exclude_columns: [tex]` | las 20 restantes |
| `cerprodes` | entera | `ide, docproide, can, docdestip, docdescod, docdeside, lindeside` |
| `dvf` (D6) | `include_columns` 9 → 24 | las 9 de F-150 + `obride, fas, tot, totpag, impbru, impnet, impdes, imprec, ivaide, pagide, efeide, estfac, docoriide, expide, cueide` |

`dvfpro` lleva `docide` y `obride`: es lo que lee `retenciones.v_src_lineas_venta` (R25).
`config/tables_sigrid_venta_snippet.yaml` queda obsoleto: T3 lo borra (lo dice el commit).
`res` de `dvfpro`/`cerpro` entra en `raw` (vetado a todos los perfiles, F-135) y se enmascara en
`ventas` para personas físicas (R7). `obrcer`, `cerpropar`, `dvfpropar`: vacías, no entran.

## 3. Dominio: `etl_sigrid/domain/ventas.py` (nuevo, sin dependencias)

Oráculo de las reglas que el SQL repite; los tests comparan los LITERALES compartidos
(patrón, clases, estados) entre el módulo y el SQL, como F-156.

- Constantes: `TIP_CERTIFICACION = 54`, `TIP_FACTURA_VENTA = 11`, `DOCDESTIP_FACTURA_VENTA = 11`,
  `ESTADOS_CERT_CUENTAN = (2, 3, 4)`, `PATRON_NIF_PERSONA = r"^[0-9KLMXYZ][0-9]{7}[A-Z]$"`,
  `NOMBRE_ENMASCARADO = "PERSONA FÍSICA"`, `CLASES_GARANTIA = (4, 5)`, `CLASE_RETESP = 1`,
  `CLASE_COEFICIENTES = 0`, `CLASES_OTRAS = (2, 3)`, `COLUMNAS_PROHIBIDAS_CLI` (prefijos `dir`,
  `tel`, `ban`, `fax` y `ele`, `web`, `fecnac`, `clamai`, `numseg`, `facpdfele`, `faceele`).
- `normalizar_cif(cif: str | None) -> str | None`: mayúsculas, sin espacios/guiones/puntos;
  vacío → `None`.
- `es_persona_fisica(cif_normalizado: str | None, perfis: int | None) -> bool` (R6).
- `cif_valido(cif_normalizado: str | None) -> bool` (R8): DNI con letra
  `TRWAGMYFPDXBNJZSQVHLCKE[n % 23]`; NIE con X/Y/Z → 0/1/2 y la misma letra; K/L/M y CIF de
  sociedad (`[ABCDEFGHJNPQRSUVW]` + 7 dígitos + `[0-9A-J]`) solo por forma.
- `clase_recargo(reccla: int | None) -> str`: `COEFICIENTES` | `RETESP` | `GARANTIA` | `OTRAS`
  (desconocida → `OTRAS`).
- `estado_seguimiento(estado_cert, num_facturas, num_efectos, emitido, cobrado) -> str` (R19),
  en este orden: estado fuera de `ESTADOS_CERT_CUENTAN` → `BORRADOR`; sin factura →
  `SIN_FACTURA`; sin efectos no BAJA → `FACTURADA_SIN_EFECTO`; cobrado ≤ 0 → `PENDIENTE_COBRO`;
  cobrado < emitido − 0,01 → `COBRADA_PARCIAL`; si no → `COBRADA`.

## 4. SQL: `etl_sigrid/infrastructure/postgres/sql/ventas/` (nuevo)

Patrón `DROP TABLE IF EXISTS ... CASCADE` + `CREATE TABLE AS` (nadie fuera de `ventas` depende
de sus tablas; las vistas se recrean en `05`). Cabecera con qué construye y de qué lee.

- **`00_setup.sql`** — `CREATE SCHEMA IF NOT EXISTS ventas`; funciones `IMMUTABLE`:
  `ventas.fn_fecha(BIGINT)` (COPIA deliberada de `tesoreria.fn_fecha`; un test compara los
  cuerpos), `ventas.fn_cif_normalizado(TEXT)`, `ventas.fn_es_persona_fisica(TEXT, INT)` (con el
  literal de `PATRON_NIF_PERSONA`), `ventas.fn_cif_valido(TEXT)`, `ventas.fn_clase_recargo(INT)`.
- **`01_clientes.sql`** — `ventas.clientes` (R5-R8). Desde `raw.cli` + `raw.con` (tip 4: código,
  empresa). Agregados por cliente desde `raw.dvf`, `raw.cer` y `raw.obr.entide`, agregados ANTES
  de unir (guarda de grano). Columnas: `cliente_id, codigo_cliente, nombre, cif, cif_normalizado,
  tipo_documento, pais, es_persona_fisica, cif_valido, cif_repetido, num_obras, num_facturas,
  num_certificaciones, facturado_base, primera_factura, ultima_factura`. Persona física:
  `nombre = 'PERSONA FÍSICA'`, `cif` y `cif_normalizado` NULL; `cif_valido` y `cif_repetido` se
  calculan antes de enmascarar (no delatan el dato).
- **`02_facturas.sql`** — `ventas.facturas` (R9-R11): `raw.dvf` + `raw.con` (código, empresa,
  `est`, `fecbaj`) + `raw.conest` (tip 11) + `maestro.centros_coste` + `raw.con` de la obra.
  Recargos por factura desde `raw.dvfrec` agregados antes de unir, `SUM(cuo)::NUMERIC(18,2)`
  filtrado por `ventas.fn_clase_recargo`. Columnas: `factura_id, codigo_factura, empresa_id,
  fecha_factura, clase, estado_codigo, estado_sigrid, anulada, cliente_id, nombre_cliente
  (enmascarado), obra_id, codigo_obra, obra_via, contrato_id, contrato_nombre, base, iva,
  total_sin_retencion, total, a_cobrar, importe_coeficientes, retencion_garantia,
  retencion_retesp, retencion_otras, num_lineas`.
  `ventas.factura_lineas` (R12) desde `raw.dvfpro`; `descripcion` NULL si el cliente de la
  factura es persona física; `linea_certificacion_id` = `linoriide` cuando existe en
  `raw.cerpro`. `ventas.factura_recargos` desde `raw.dvfrec` + `raw.con` del recargo (código y
  nombre), con `clase_recargo` y `es_garantia`.
- **`03_certificaciones.sql`** — `ventas.certificaciones` (R13-R15): `raw.cer` + `raw.con`
  (código, empresa, `est`) + `raw.conest` (tip 54) + `raw.obrctr` (nombre del contrato) + líneas
  de `raw.cerpro` y recargos de `raw.cerrec` agregados antes de unir. Columnas:
  `certificacion_id, codigo_certificacion, numero, mes, fecha_certificacion, empresa_id, obra_id,
  codigo_obra, contrato_id, contrato_nombre, cliente_id, nombre_cliente, estado_codigo,
  estado_sigrid, cuenta (estado en 2-4), facturada, certificacion_anterior_id, importe_a_cuenta,
  importe_a_origen, importe_anterior, base, iva, total, base_origen_contrato,
  importe_coeficientes, retencion_garantia, retencion_retesp, retencion_otras, num_lineas`.
  `base_origen_contrato` = `SUM(base) FILTER (WHERE cuenta) OVER (PARTITION BY contrato_id ORDER
  BY numero, certificacion_id)`, NULL en las que no cuentan y en las sin contrato.
  `ventas.certificacion_recargos` (R16), como `factura_recargos`.
- **`04_enlace.sql`** — `ventas.certificacion_factura` (R17): `raw.cerprodes` (`docdestip` = 11)
  → `raw.cerpro` (`docproide`) → par (`cerpro.docide`, `docdeside`) con `num_lineas` y `SUM(can)`;
  `JOIN raw.dvf` para no publicar destinos huérfanos. `ventas.cobertura_enlace` (R21): tres filas
  (`CERTIFICACION_FACTURA`, `FACTURA_EFECTO`, `EFECTO_FACTURA`) con `total`, `enlazados`,
  `importe_total`, `importe_enlazado` y `calculado_en = now()`; el eslabón de efectos lee
  `raw.cob` (no `tesoreria`: la tabla se construye aquí y no puede esperar a otro paso).
- **`05_vistas.sql`** — `ventas.v_factura_cobro` (R18): `ventas.facturas` ⟕ `tesoreria.efectos`
  (`sentido = 'COBRO'`, `documento_id = factura_id`) con `emitido` (Σ `importe` no BAJA),
  `cobrado` (REALIZADO), `pendiente` (PREVISTO), `num_efectos`, `ultima_fecha_cobro`.
  `ventas.v_seguimiento_certificacion` (R19): certificaciones ⟕ `certificacion_factura` ⟕
  `v_factura_cobro`, agregado por certificación; `factura_compartida` si alguna factura suya
  tiene más de una certificación; `estado_seguimiento` con un `CASE` que replica el dominio.
  `ventas.v_contraste_certificado_obra` (R20): `tesoreria.devengo_corte_obra` (`concepto =
  'VENTA'`) ⟕ Σ `base` de `ventas.certificaciones` con `cuenta` por obra; columnas
  `venta_real_origen_con_coeficientes, certificado_origen, facturado_origen,
  pendiente_certificar (= venta − certificado), certificado_sin_facturar (= certificado −
  facturado)`, con signo (sin suelo: el negativo es «certificado por delante»).
- **`06_guardas.sql`** — un `DO` (R7, R22): recuentos frente a `raw.dvf`, `raw.dvfpro`,
  `raw.cer`; Σ `base` = Σ `raw.dvf.totbas` (al céntimo, `NUMERIC`); ningún cliente persona física
  con `cif` o `nombre` distinto del enmascarado; ninguna línea de factura de persona física con
  `descripcion`. `RAISE EXCEPTION` con las cifras.

Importes de `raw` en `double precision`: se castean a `NUMERIC(18,2)` antes de `ROUND`/`SUM`
(memoria «sandbox-tipos-raw-double»).

## 5. Aplicación y composición

- **Nuevo** `etl_sigrid/application/steps/build_ventas_step.py`: `BuildVentasStep`, `name =
  "build_ventas"`, `depends_on = ("ingest_raw",)`, `SUB_PASOS` con los siete ficheros (patrón de
  `build_postventa_step.py`, `target_schema="ventas"`).
- **`main.py`**: `BuildVentasStep` en `build_pipeline_steps` tras `BuildRetencionesStep`
  (comentario: décimo build, nadie depende de él), en `PASOS_CON_PERMISOS`, y comando
  `build-ventas`. La docstring de `build_pipeline_steps` y el mapa de `CLAUDE.md` pasan a
  diecisiete pasos.
- `LECTURAS_PARA_REANUDAR` (F-148): no cambia; `ventas` no lee `stg` ni `mart` en sus tablas.

## 6. Permisos (D5)

- `config/settings.py`: `ventas` en `DEFAULT_CONSUMPTION_SCHEMAS` (comentario F-040) y en
  `.env.example`. NO en la lista explícita del perfil restringido (F-141) ni en la del postventa
  (F-156): un test lo fija.
- `etl_sigrid/domain/diccionario.py`: `ventas` en `ESQUEMAS_DEL_DATAMART`.
- Sin `02_roles.sql`: ningún esquema restringido nuevo (D2 = A). Si el humano elige D2 = B, esta
  sección se reescribe (grupo, veto, `02_roles.sql`) y la spec vuelve a la PARADA 1.

## 7. Diccionario

- **Nuevo** `config/diccionario/ventas.yaml`: ficha de las 8 tablas y 3 vistas, con las trampas:
  certificado ≠ facturado ≠ cobrado; a cuenta sin recargos frente a base con coeficientes;
  N:M certificación-factura (no sumar lo cobrado por certificación si `factura_compartida`);
  `AGR` no atribuido; persona física enmascarada; contraste solo para obras de la receta.
- `raw.yaml`: fichas de `cli`, `cer`, `cerpro`, `cerrec`, `cerprodes`, `dvfpro`, `dvfrec` (qué
  NO trae cada una) y `dvf` actualizada a 24 columnas.
- `00_global.yaml`: versión +1 (v73 si F-158 sigue en v72), entrada del esquema `ventas`
  (`para_que_sirve` ≤ 350), regla `R-VENTAS-TRES-CIFRAS` con `resumen` de 40-250 caracteres y
  `entrega: resumen`; si el presupuesto de F-147 se pasa, se sube con su motivo.

## 8. Documentación

`docs/ARCHITECTURE.md` (párrafo de `ventas`, censo 100, «Lo que Sigrid NO guarda»: `obrcer`
vacía, `cer.idefac`/`feccob` a 0, `cli` sin clasificación), mapa de `CLAUDE.md`,
`../azure-apps/datamart_seg_anual.md` (consume 7 tablas más, publica `ventas`). Comentario de
cabecera de `tesoreria/01_efectos_completo.sql` («Sin documento de venta (F-040)») NO se toca
(R25): lo actualiza F-104 o una feature de tesorería.

## 9. Ficheros que NO se tocan

`sql/retenciones/*` (la vista `v_src_lineas_venta` se activa sola), `sql/tesoreria/*` (07 sigue
leyendo `raw.dvf.cenide`/`totbas`), `sql/compras/*`, `sql/mart/*`, `sql/cierre/*`,
`infra/sql/02_roles.sql`, `grants.py`, `apply_grants_step.py` y `config/hipotesis_caja.yaml`.

## 10. Tests (sin red ni BBDD)

- `tests/test_f040_dominio.py` — R6, R8, `clase_recargo`, `estado_seguimiento` (tabla de casos
  con cada frontera: 0,01 de tolerancia, emitido 0, BAJA).
- `tests/test_f040_ingesta.py` — R1-R4 sobre el YAML (listas exactas, prohibidas de `cli`,
  `dvf` sin `entcif`/`entres`/`dir*`/`ban*`, censo 100).
- `tests/test_f040_sql.py` — R5-R22 sobre el texto SQL: tablas y columnas, filtros (`docdestip =
  11`, `tip = 54`/`11`, `ESTADOS_CERT_CUENTAN`), literales compartidos con el dominio,
  `fn_fecha` = `tesoreria.fn_fecha`, agregación antes de unir, `DO` con sus cuatro guardas.
- `tests/test_f040_pipeline.py` — R23 (posición, `depends_on`, `PASOS_CON_PERMISOS`, comando).
- `tests/test_f040_grants.py` — R24.
- `tests/test_f040_diccionario.py` — R26 (fichas de cada objeto y columna, regla, versión).
- `tests/test_f040_frontera.py` — R25: `git diff main -- sql/retenciones sql/tesoreria` vacío
  (salta con aviso si no hay git).
- Al día: `test_f150_ingesta.py` (`COLUMNAS_DVF`, lista blanca de `cer`, `cerpro`, `cli`, `dvf`,
  `dvfpro`, `log`, `per`), `TOTAL_TABLAS` de `test_f066`/`test_f074`, `test_f085` y
  `test_f156_r5` (censo), listas de esquemas de F-135/F-138/F-156/F-057, `test_f047`/`f148`.

## 11. Riesgos y alternativas descartadas

- **Enlace por `cer.idefac` / `cer.feccob`**: descartado, a 0 en las 6.308 (medido).
- **Enlace por `dvfpro.linoriide`** como fuente principal: 4.452 frente a 4.349 de `cerprodes`,
  pero no dice el tipo de destino; se publica como columna de la línea y `cerprodes` es el
  enlace (100 % con destino válido).
- **Repartir lo cobrado de una factura entre sus certificaciones**: descartado (N:M, sin regla de
  negocio); se marca `factura_compartida`.
- **Esquema restringido para personas físicas (D2 = B)**: +1 esquema, +1 bloque de
  `02_roles.sql` y un permiso que mantener para 16,5 M€ de alquileres y compraventas que hoy
  nadie ha pedido ver con nombre. Reversible: el dato sigue en `raw`.
- **Rellenar `tercero_cif` de `tesoreria.efectos` y `entidad_cif` de retenciones**: fuera; se
  llega por `ventas.clientes` con el `tercero_id`/`entidad_id`. Lo segundo es de F-104.
- **Cobro vía `AGR`**: no atribuible hasta que F-104 explique los efectos con `fecbaj`; la
  cobertura lo cuantifica cada noche (R21).
- **Ventana**: < 1 % (`progress/spec_F-040.md` § 1). Riesgo real: la nocturna termina a las
  04:56; cualquier feature que sume minutos la empuja a la jornada. F-040 suma segundos.
- **Despliegue y vuelta atrás** (T16): imagen nueva → `ingest` de las 7 tablas → `build-ventas`
  → `apply-grants` → `check-diccionario` → `publicar-diccionario` (escritura en Azure: la
  autoriza el humano) → aviso a `mcp-bbdd`. Vuelta atrás: imagen anterior + `DROP SCHEMA ventas
  CASCADE`; las tablas nuevas de `raw` sobran sin daño.
