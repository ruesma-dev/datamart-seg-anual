<!-- progress/spec_F-153.md -->
# F-153 · Mediciones de la spec

Consultas de solo lectura; el diseño está en `specs/F-153-estado-albaranes/design.md`.

## Mediciones (Azure, solo lectura, 2026-11-02 ~08:36 UTC, `raw` de esa noche)

**Disponibilidad.** `raw.con.est` (`integer`) ya está: `con` se ingiere con
`exclude_columns: [ima]`, no con `include_columns`. `dca.fecfac` también.
**No hay cambio en `config/tables_sigrid.yaml` ni ingesta.** Catálogo tipo 14:
4 estados (`raw.conest`).

| est | código | ALBARAN | PROFORMA | NOTA | OTRO | Total | Con paso en `rac` | Último paso = estado |
|---|---|---|---|---|---|---|---|---|
| 0 | (fuera de catálogo) | 5 | 5 | 0 | 0 | 10 | 10 | 0 |
| 1 | PDT Pendiente | 7.564 | 49 | 76 | 0 | 7.689 | **0** | - |
| 2 | COM Comprobado | 379 | 31 | 0 | 0 | 410 | 410 | 410 |
| 3 | CON Contabilizado | 37.186 | 214 | 198 | 0 | 37.598 | 37.598 | 37.491 |
| 10 | FAC Facturado | 267.512 | 2.660 | 4 | 1 | 270.177 | 270.132 | **2.257** |
| | **Total** | 312.646 | 2.959 | 278 | 1 | **315.884** | | |

- **F-133 no está y no daría fecha a FACTURADO.** `compras.documento_procesos`
  tiene los tipos 15, 42, 44 y 46; del 14, 0 filas. En `raw.rac` hay 618.680
  pasos de 308.150 albaranes, pero son «Comprobar» (1→2) y «Contabilizar» (2→3):
  el paso a FACTURADO casi nunca se registra. De los 270.177 FAC, 266.206 tienen
  «Contabilizar» como último paso y 1.668 «Comprobar». Con F-133 y la regla de
  F-132, ~268.000 saldrían `FUERA_DE_PROCESO`, que es falso.
- **`dca.fecfac` en FAC:** 235.254 de 270.177 (87,1 %), de 2016-05-23 a
  2026-10-30; los 34.923 sin ella son documentos sin ese dato. Es posterior o
  igual al último paso en 234.719 de 235.209 (99,8 %). De las 53.848 con
  `idefac`, no coincide con la factura ni en alta ni en `fecdoc` en 49.171: **es
  la fecha que guarda Sigrid al facturar, de día, y no la de la factura**.
- **PDT:** 0 con pasos y 0 sin `con.fec`: la fecha de alta es exacta. Por año,
  1.077 de 2026 y 6.612 anteriores (desde 2009): pendientes viejos sin cerrar.
- **`facturado_sigrid`:** `estfac = 1` con estado no 10 en 185 (1 PDT, 73 COM,
  111 CON); estado 10 con `estfac = 0`, ninguno.
- **Fuera de catálogo:** 10 (0,003 %), todos `est = 0`, de 2022 a 2025
  (AC22/01874, PROF25/00055...); su último paso es «Marcar albarán como
  facturado» a 10 y la cabecera dice 0.
- **Frescura:** con último paso de octubre o después, `con.est` nunca va por
  detrás de `rac` (3.494 casos).
- **Grano:** `raw.dca` = `compras.albaranes` = 315.884, `con.tip` = 14 en todas.

**Resultado esperado de la regla hoy (tipo 14):**

| `origen_fecha` | Filas | % | Qué son |
|---|---:|---:|---|
| `FACTURACION` | 235.254 | 74,5 | FAC con `fecfac` |
| `ALTA` | 7.689 | 2,4 | PDT |
| `SIN_HISTORIAL` | 72.941 | 23,1 | 37.598 CON + 410 COM + 34.923 FAC sin `fecfac` + 10 sin estado |
| `PASO`, `FUERA_DE_PROCESO` | 0 | 0 | hasta F-133 |

**Consumidores.**

- `pg_depend`: de `compras.albaranes` cuelgan `v_control_forma_pago`,
  `v_pbi_albaranes_sin_facturar` y `v_pbi_contrato_consumo`, las tres
  reconstruidas por `build_compras`; de `v_estado_documentos`, **nada**.
- Ningún `SELECT *` ni `a.*` en `sql/compras/`; ningún SQL fuera de `compras/`
  lee estos objetos. Las uniones de `02`, `03`, `06` y `15` no usan `estado` sin
  cualificar, así que las columnas nuevas no causan ambigüedad.
- Otros repositorios (portales, `retenciones`, `facturas`, `proformas`,
  `sigrid-api`...): 0 referencias. `mcp-bbdd`: solo el mapa de adjuntos
  (`ALBARAN: compras.albaranes.albaran_id`) y su `diccionario_datos.yaml`, el
  modo sin diccionario publicado, que aquí no se usa. El esquema ya está en la
  lista: **no hay que cambiar `config.yaml`**.
- **Power BI no se puede inspeccionar desde aquí.** Las columnas van al final,
  misma disciplina de F-128; una consulta externa que una `facturas` y
  `albaranes` con `estado` sin cualificar pasaría a ser ambigua (riesgo bajo).
- Tipos: `estado_id` `integer`, `estado_codigo` y `estado` `text`, los de
  `compras.facturas`; `codigo_albaran` es `varchar` como `codigo_documento`.
- Permisos: tabla y vista se rehacen cada noche y `ALTER DEFAULT PRIVILEGES` los
  conserva (hoy, SELECT a `mcp_sigrid_dm_ro` y al perfil restringido). No hay
  dato personal nuevo: `usuario` y `nombre_usuario` van a NULL en el tipo 14.

**Coste.**

- Recrear la tabla no es un coste nuevo: `01` ya hace `DROP ... CASCADE` y
  `CREATE` cada noche. El `LATERAL` añade ~1 s (`Memoize`: 5 fallos de 315.884;
  1,1 s toda la consulta). Tabla: +~8 MB sobre 148 MB; índice, ~7 MB (estimados).
- `build_compras`: 8,6 min y 9,2 min en manual, 20,5 min la nocturna del 02-11.
- Vista entera: 0,32 s hoy → 0,81 s con prototipo (`EXPLAIN ANALYZE`), con 524k
  filas en vez de 208k; timeout del MCP, 30 s. El prototipo leyó `est` de
  `raw.con`; la vista real lee `compras.albaranes`, más barata.
