# F-040 · Detalle del diseño (listas exactas, columnas y tests)

Complemento de `design.md` (que manda): aquí viven las listas que un test fija literalmente.

## A · Ingesta (`config/tables_sigrid.yaml`)

| Tabla | Cómo | Columnas |
|---|---|---|
| `cli` | `include_columns` (20) | negocio: `ide, tipcif, cifpai, cif, raz, perfis, cenide, taride, secide, pagide, efeide, cueide, cueretide`; contacto (D6, solo `ventas_restringida`): `dir1, dir2, dircpo, dir, tel, tel2, ele` |
| `cer` | `include_columns` | `ide, cla, entide, cenide, obride, ctride, expide, fas, fecdoc, fecfac, estfac, idefac, docoriide, pagide, efeide, ivaide, impbru, impnet, impdes, imprec, totbas, totiva, totdoc, tot, totpag, totproori, totprcori` |
| `cerpro` | `include_columns` | `ide, docide, pos, res, can, pre, tot, ivaide, ivacuo, cenide, obride, paride, docoritip, docoriide, linoriide, imporiori, imporiant, canoriori` |
| `dvfpro` | `include_columns` | `ide, docide, pos, res, can, pre, tot, ivaide, ivacuo, cenide, obride, paride, docoritip, docoriide, linoriide, unimed, proide` |
| `cerrec`, `dvfrec` | `exclude_columns: [tex]` | las 20 restantes |
| `cerprodes` | entera | `ide, docproide, can, docdestip, docdescod, docdeside, lindeside` |
| `dvf` | `include_columns` 9 → 35 | las 9 de F-150 (`ide, cla, entide, cenide, ctride, fecdoc, totbas, totiva, totdoc`) + 15 de negocio (`obride, fas, tot, totpag, impbru, impnet, impdes, imprec, ivaide, pagide, efeide, estfac, docoriide, expide, cueide`) + 11 personales (D6, solo `ventas_restringida`): `entcif, entres, diremp1, dircon1, dirdir1, diremp2, dircon2, dirdir2, diremp3, dircon3, dirdir3` |

Prohibidas (test de R1/R3; constantes del dominio): en `cli`, todo lo que no está arriba, y en
concreto los prefijos `ban`, `fax`, `telsin`, `tel2sin`, `fac`, `nom`, `g3w` y `fecnac`, `numseg`,
`clamai`, `dirtex`, `web`, `dniper`, `munide`, `proide`, `paiide`; en `dvf`, `ban*`, `emptex`,
`entcod`, `entref`, `entciftip`, `entcifpai`, `empcif`.

Medido el 2026-11-07 en Sigrid, solo lectura (`progress/spec_F-040.md` § 8): `dvf` 15.734 filas,
`entcif` en todas, `entres` en 15.733, `dirdir1` en 15.565, `dirdir2` 1.565, `dirdir3` 98,
`dircon1-3` en 0; 3.635 con `entcif` de forma de NIF de persona. `cli` 1.210: `dir1` 1.162, `dir`
1.151, `dircpo` 1.154, `tel` 73, `tel2` 55, `ele` 96; de las 572 personas físicas, 566 con
dirección, 24 con teléfono y 68 con correo.

## B · Columnas de cada objeto

**`ventas`**

- `clientes`: `cliente_id, codigo_cliente, nombre, cif, cif_normalizado, tipo_documento, pais,
  es_persona_fisica, cif_valido, cif_repetido, num_obras, num_facturas, num_certificaciones,
  facturado_base, primera_factura, ultima_factura`. `codigo_cliente` (`con.cod`) a NULL en persona
  física o con forma de NIF de persona (enmienda R1-H1 del review, 2026-11-09).
- `facturas`: `factura_id, codigo_factura, empresa_id, fecha_factura, clase, estado_codigo,
  estado_sigrid, anulada, cliente_id, nombre_cliente, cif_cliente, es_persona_fisica, obra_id,
  codigo_obra, obra_via, contrato_id, contrato_nombre, base, iva, total_sin_retencion, total,
  a_cobrar, importe_coeficientes, retencion_garantia, retencion_retesp, retencion_otras, num_lineas`.
- `factura_lineas`: `linea_id, factura_id, posicion, descripcion, cantidad, precio, importe,
  iva_id, iva_cuota, obra_id, partida_id, unidad, linea_certificacion_id`.
- `factura_recargos` / `certificacion_recargos`: `recargo_linea_id, factura_id` (o
  `certificacion_id`), `recargo_id, codigo_recargo, nombre_recargo, clase, clase_recargo,
  es_garantia, base` (`bas`), `porcentaje` (`valpor`), `importe` (`cuo`); código y nombre, de
  `raw.con` del recargo (`recide`).
- `certificaciones`: `certificacion_id, codigo_certificacion, numero, mes, fecha_certificacion,
  empresa_id, obra_id, codigo_obra, contrato_id, contrato_nombre, cliente_id, nombre_cliente,
  estado_codigo, estado_sigrid, cuenta, facturada, certificacion_anterior_id, importe_a_cuenta,
  importe_a_origen, importe_anterior, base, iva, total, base_origen_contrato, importe_coeficientes,
  retencion_garantia, retencion_retesp, retencion_otras, num_lineas`.
- `certificacion_factura`: `certificacion_id, factura_id, num_lineas, cantidad`.
- `cobertura_enlace`: `eslabon, total, enlazados, importe_total, importe_enlazado, calculado_en`.
- `v_factura_cobro`: `factura_id, emitido, cobrado, pendiente, num_efectos, ultima_fecha_cobro`.
- `v_seguimiento_certificacion`: `certificacion_id, num_facturas, facturado, emitido, cobrado,
  pendiente, factura_compartida, estado_seguimiento`.
- `v_contraste_certificado_obra`: `obra_id, codigo_obra, venta_real_origen_con_coeficientes,
  certificado_origen, facturado_origen, pendiente_certificar, certificado_sin_facturar`.

**`ventas_restringida`**

- `clientes_contacto`: `cliente_id, codigo_cliente, nombre, cif, cif_normalizado, es_persona_fisica, direccion,
  direccion_linea1, direccion_linea2, codigo_postal, telefono, telefono2, correo` (`codigo_cliente`
  íntegro: enmienda R1-H1).
- `factura_cabecera`: `factura_id, cliente_id, es_persona_fisica, nombre_cabecera, cif_cabecera,
  direccion_empresa_1, direccion_contacto_1, direccion_completa_1` (y lo mismo para 2 y 3).
- `factura_lineas_persona`: `linea_id, factura_id, cliente_id, descripcion`.

Los nombres de `ventas_restringida` empiezan por los prefijos de `PREFIJOS_PROHIBIDOS_EN_VENTAS` a
propósito: la guarda de R24 busca esos prefijos en el esquema `ventas` y nunca deben aparecer allí.

## C · Tests (sin red ni BBDD)

| Fichero | Cubre |
|---|---|
| `tests/test_f040_dominio.py` | R6, R8, R11-R12 (`clase_recargo` con `CLASES_GARANTIA` de hoy y con `(1, 4, 5)` parcheado: el `RETESP` cambia de columna y el reparto sigue completo), R18 (tabla de casos: 0,01 de tolerancia, emitido 0, BAJA) |
| `tests/test_f040_ingesta.py` | R1-R4 (listas exactas de § A, prohibidas, censo 100) |
| `tests/test_f040_sql.py` | R5-R25 sobre el texto: tablas y columnas de § B, filtros (`docdestip = 11`, `tip = 54`/`11`, `ESTADOS_CERT_CUENTAN`), literales del dominio (`PATRON_NIF_PERSONA`, `CLASES_GARANTIA`, prefijos), `fn_fecha` = `tesoreria.fn_fecha`, agregación antes de unir, `06_restringida.sql` en `ventas_restringida` y ningún `entcif`/`entres`/`dir*`/`tel`/`ele` en `01`-`05`, y el `DO` con todas sus guardas |
| `tests/test_f040_pipeline.py` | R26 (posición, `depends_on`, `PASOS_CON_PERMISOS`, comando, `SUB_PASOS` y sus esquemas) |
| `tests/test_f040_grants.py` | R27-R29 (§ 6 de `design.md`) |
| `tests/test_f040_diccionario.py` | R31-R32 (fichas de cada objeto y columna de los dos esquemas, reglas, ámbitos, versión) y R33 (`ARCHITECTURE`, `CLAUDE.md`, runbook § 15) |
| `tests/test_f040_frontera.py` | R30 |

Tests existentes que fijan censos o listas y hay que poner al día (cambio esperado, con comentario
`F-040`): `test_f150_ingesta.py` (`COLUMNAS_DVF` 35 y listas de `cer`, `cerpro`, `cli`, `dvfpro`),
`test_f066_ingesta_raw.py`, `test_f074_ingesta_censo.py`, `test_f085_*` y `test_f156_ingesta_sql.py`
(censo 100); `test_f037_grants.py`, `test_f135_grants.py`, `test_f138_grants.py` (`ESQUEMAS_DEL_DATAMART`
18 → 20), `test_f156_grants.py`, `test_f136_login_total.py`, `test_f141_perfil_restringido.py`,
`test_f146_restringido_sin_contabilidad.py` y `test_f057_personal.py` (listas de vetados,
restringidos y consultas de `02_roles.sql`); `test_f006_formato.py` (esquemas),
`test_f006_frescura.py` (`R-FRESCURA`), `test_f047_*`, `test_f148_permisos_por_paso.py`,
`test_f024_cli.py` (pasos y comando); `test_f006_fichas.py`, `test_f006_reglas.py`,
`test_f147_*` y `test_f149_*` (fichas, reglas y presupuesto). Ninguno se relaja: se actualiza el
valor fijado y se explica el porqué en el commit.
