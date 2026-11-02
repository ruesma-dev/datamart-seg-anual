<!-- specs/F-153-estado-albaranes/design.md -->
# F-153 · Diseño técnico

## 1. Mediciones (resumen; detalle en `progress/spec_F-153.md`)

Azure, solo lectura, 2026-11-02 ~08:36 UTC. **Sin ingesta nueva:** `raw.con.est`
y `dca.fecfac` ya están (`con` usa `exclude_columns`, no `include_columns`).

| Estado (tipo 14) | ALBARAN | PROFORMA | NOTA | OTRO | Total | Último paso de `rac` = estado |
|---|---:|---:|---:|---:|---:|---:|
| 0 fuera de catálogo | 5 | 5 | 0 | 0 | 10 | 0 |
| 1 PDT Pendiente | 7.564 | 49 | 76 | 0 | 7.689 | sin pasos |
| 2 COM Comprobado | 379 | 31 | 0 | 0 | 410 | 410 |
| 3 CON Contabilizado | 37.186 | 214 | 198 | 0 | 37.598 | 37.491 |
| 10 FAC Facturado | 267.512 | 2.660 | 4 | 1 | 270.177 | **2.257** |

- **F-133:** el tipo 14 tiene 0 filas en `documento_procesos`, y además `rac` casi
  nunca registra el paso a FACTURADO: F-133 no fecharía esos ~268.000.
- **`fecfac`:** 235.254 de 270.177 FAC; ≥ último paso en el 99,8 %. Es de día y
  no es la fecha de la factura.
- **Resultado esperado hoy:** `FACTURACION` 235.254 (74,5 %), `ALTA` 7.689 (2,4 %),
  `SIN_HISTORIAL` 72.941 (23,1 %: 37.598 CON, 410 COM, 34.923 FAC sin `fecfac`, 10
  sin estado).
- **Consumidores:** cuelgan de la tabla `v_control_forma_pago`,
  `v_pbi_albaranes_sin_facturar` y `v_pbi_contrato_consumo`; de la vista, nada.
  Sin `SELECT *` y sin lecturas en otros repositorios. `config.yaml` del MCP no
  cambia. **Power BI no se puede inspeccionar desde aquí.**
- **Coste:** la tabla ya se recrea cada noche; `LATERAL` ~1 s; vista de 0,32 s a
  0,81 s (524k filas frente a 208k; timeout del MCP, 30 s).

## 2. Ficheros a modificar

| Fichero | Cambio |
|---|---|
| `etl_sigrid/infrastructure/postgres/sql/compras/01_documentos.sql` | §4; nota F-153 en la cabecera |
| `etl_sigrid/infrastructure/postgres/sql/compras/13_estado_documentos.sql` | §5; cabecera y `COMMENT ON VIEW` |
| `etl_sigrid/domain/estado_documentos.py` | §3 |
| `etl_sigrid/application/steps/build_compras_step.py` | Solo el comentario del sub-paso `estado_documentos` |
| `config/diccionario/compras.yaml` | §6 |
| `config/diccionario/00_global.yaml` | `version: 70`, nota, frase del esquema `compras` (línea ~1867) |
| `config/diccionario/raw.yaml` | Solo si `conest` dice que el estado traducido no llega al albarán (comprobar) |
| `docs/ARCHITECTURE.md` | Bloque «LA ANTIGÜEDAD DEL ESTADO» (línea ~519) |
| `../azure-apps/datamart_seg_anual.md` | Fila nueva: `compras.albaranes` +3 y la vista; commit local en `azure-apps` |
| `tests/test_f132_sql.py`, `test_f132_dominio.py`, `test_f132_diccionario.py` | §10: ajustar lo fijado a tres familias y tres orígenes |
| `tests/test_f128_sql.py` | `ALBARANES_F153` tras `ALBARANES_NUEVAS` en la igualdad de columnas |

**A crear:** `tests/test_f153_sql.py`, `tests/test_f153_dominio.py`,
`tests/test_f153_diccionario.py`.

**NO se tocan:** `config/tables_sigrid.yaml`, `00_setup.sql` (la función ya
sirve), `12_documento_procesos.sql` y `domain/documento_procesos.py` (F-133),
`domain/cabecera_compra.py` (`con.est` no es de `dca`), `grants.py`,
`15_alarmas_liquidatoria.sql`, `mcp-bbdd`.

## 3. Dominio (`domain/estado_documentos.py`)

```python
TIPO_ALBARAN: Final[int] = 14
ESTADO_FACTURADO_ALBARAN: Final[int] = 10
#: Los valores de `compras.fn_tipo_documento` para el tipo 14.
TIPOS_DOCUMENTO_ALBARAN: Final[tuple[str, ...]] = ("ALBARAN", "PROFORMA", "NOTA", "OTRO")
#: Familias cuyos pasos aún no están en `documento_procesos`. F-133 lo vacía.
FAMILIAS_SIN_HISTORIAL: Final[frozenset[int]] = frozenset({TIPO_ALBARAN})
ESTADOS_INICIALES[14] = frozenset({1})
ORIGENES_FECHA = ("PASO", "FACTURACION", "ALTA", "SIN_HISTORIAL", "FUERA_DE_PROCESO")
```

`FAMILIAS_ESTADO` no cambia. `fecha_estado` gana `fecha_facturacion: date | None = None`
al final, con defecto para no romper sus llamadas, y sigue el orden de R7; tras
`PASO`, el `ultimo is not None` restante da `FUERA_DE_PROCESO` con cota. `dias_en_estado`
no cambia. Capa `domain`.

## 4. SQL · `01_documentos.sql`, bloque ALBARANES

Al final de la proyección, tras `factura_cabecera_id`:

```sql
    NULLIF(a.idefac, 0)                     AS factura_cabecera_id,  -- la buena es por línea
    -- F-153: AL FINAL, como F-128. `con.est` y su traducción, por la pareja.
    con.est                                 AS estado_id,        -- código interno del tipo 14
    est.codigo_estado                       AS estado_codigo,    -- PDT, COM, CON, FAC
    est.nombre_estado                       AS estado            -- ya traducido (tipo 14)
```

Tras `LEFT JOIN raw.con prv_con`, y antes de los joins de F-128 (igual que en
FACTURAS): `LEFT JOIN LATERAL compras.fn_estado_documento(14, con.est) est ON TRUE`.
Tras los índices: `CREATE INDEX idx_com_alb_est ON compras.albaranes (estado_id);`.
El orden de los bloques no cambia: el catálogo se lee de `raw.conest`.

## 5. SQL · `13_estado_documentos.sql`

La vista sigue siendo `DROP VIEW IF EXISTS` + `CREATE VIEW`, tres sentencias.

Los tres bloques actuales de `documentos` ganan al final `NULL::TEXT AS
tipo_albaran, NULL::DATE AS fecha_facturacion` (el primero) y `NULL, NULL` (los
otros dos). Bloque nuevo:

```sql
    UNION ALL
    -- F-153. `a.fecha` = con.fec. Sin `raw`: todo sale de la cabecera.
    SELECT 14, a.albaran_id, a.codigo_albaran, a.estado_id, a.estado_codigo, a.estado,
           a.fecha, a.tipo_documento, a.fecha_facturacion FROM compras.albaranes a
```

`con_paso`, el `CASE` de `origen_fecha`:

```sql
CASE WHEN u.paso_id IS NOT NULL
          AND u.estado_destino_id IS NOT DISTINCT FROM d.estado_id
     THEN 'PASO'
     WHEN d.tipo_documento_codigo = 14 AND d.estado_id = 10
          AND d.fecha_facturacion IS NOT NULL
     THEN 'FACTURACION'
     WHEN u.paso_id IS NULL AND (d.tipo_documento_codigo, d.estado_id) IN
          ((14, 1), (15, 1), (15, 20), (44, 1), (46, 1), (46, 11), (46, 100))
     THEN 'ALTA'
     WHEN u.paso_id IS NULL AND d.tipo_documento_codigo IN (14)
     THEN 'SIN_HISTORIAL'
     ELSE 'FUERA_DE_PROCESO' END AS origen_fecha
```

`fechados`: `CASE p.origen_fecha WHEN 'PASO' THEN p.momento_ultimo WHEN 'FACTURACION'
THEN p.fecha_facturacion::TIMESTAMP WHEN 'ALTA' THEN p.fecha_alta::TIMESTAMP END`.

Proyección, solo cambia `tipo_documento`:
`CASE ... WHEN 46 THEN 'COMPARATIVO' WHEN 14 THEN f.tipo_albaran END::TEXT`.

`cambio_posterior_a` y el paso no cambian: `FACTURACION` y `SIN_HISTORIAL` dan
NULL. El `LEFT JOIN compras.documento_procesos` tampoco, y por eso F-133 encaja
sin tocar la vista (R8).

**Orden en `build_compras`:** no cambia. La vista ya dependía de tablas de `01`;
leer `compras.albaranes` no abre una ventana nueva sin vista.

## 6. Fichas del diccionario

**`compras.yaml`, `albaranes`:** las tres columnas al final (`estado_id` `agregacion:
no_sumable`, `nulo_significa` en las de texto; `valores: [PDT, COM, CON, FAC]`) y lo
de R11; relación con `compras.v_estado_documentos.documento_id` (1:1); ejemplo:
«Que albaranes estan pendientes de comprobar». El estado **NO** dice desde cuándo.

**`compras.yaml`, `v_estado_documentos`:** lo de R12, más: `tipo_documento_codigo`
`valores: [44, 15, 46, 14]`; `tipo_documento` con ALBARAN, PROFORMA, NOTA y OTRO y
el aviso de que ALBARAN no es toda la familia; `origen_fecha` con cinco valores; los
dos orígenes nuevos en cada `nulo_significa`; relación con
`compras.albaranes.albaran_id`, «solo `tipo_documento_codigo = 14`»; aviso de 208k
a 524k filas. Ejemplo detrás de los actuales: «Que albaranes llevan mas de un mes
pendientes de comprobar».

**`00_global.yaml`:** `version: 70` con `# version 70 (F-153, 2026-11-XX): ...`,
y «(`compras.v_estado_documentos`...)» del esquema con los albaranes.

**Presupuesto de `contexto_bbdd`:** sin cambio esperado, porque el enrutado sirve
dos preguntas por ficha y las nuevas van detrás. Si `test_f147` lo mide distinto,
subir `PRESUPUESTO_MAX` con su línea de motivo, como las anteriores.

## 7. Decisiones y alternativas

- **D1 · Fecha de FACTURADO.** **A (recomendada):** `dca.fecfac`, origen
  `FACTURACION`, de día; da fecha al 74,5 % del tipo 14 y ya se publica. B: sin
  fecha; más puro, pero deja sin dato al 97,6 % hasta F-133 y al 85 % después,
  porque F-133 no lo arregla. C: fecha de la factura por `idefac`: solo 53.848 y
  no es el momento del cambio.
- **D2 · `tipo_documento`.** **A (recomendada):** ALBARAN, PROFORMA, NOTA y OTRO,
  el vocabulario de `compras.albaranes`. B: `ALBARAN` para los 315.884: una misma
  columna con dos significados en dos objetos, y `tipo_documento = 'ALBARAN'`
  daría cifras distintas sin avisar. C: columna `subtipo_documento`: cambia la
  forma de la vista y mantiene la trampa.
- **D3 · Lo que no tiene fecha.** **A (recomendada):** `SIN_HISTORIAL`. B:
  `FUERA_DE_PROCESO`: afirma que el estado cambió sin un paso, y en los 38.008
  COM y CON el paso existe. Es falso de forma medible y contradice la ficha.
- **D4 · F-133.** **A (recomendada):** no se absorbe; lo manda la feature y son
  ~610.000 filas más de `documento_procesos` y su sub-paso. B: leer `raw.rac` en
  la vista: `rac` no tiene índice por `conide`, son 2,5 M de filas por consulta,
  y rompe R9.

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| La vista crece ×2,5 y una consulta sin filtrar por tipo devuelve otra cifra | Fichas (R12); nada depende de ella en la base; 0,8 s medidos |
| `fecfac` no es exactamente el paso a FACTURADO (490 anteriores al último paso) | `origen_fecha` lo distingue y la ficha lo declara; decide el humano en D1 |
| Un FAC sin `fecfac` tras F-133 | Sale `PASO` o `FUERA_DE_PROCESO` con cota, por R7 |
| **F-133 y su criterio «igual antes y después»** | Falso para el tipo 14 tras F-153. Quien la especifique excluye el 14 del contraste y mide: ~37.900 pasan a `PASO`, ~35.000 FAC sin `fecfac` a `FUERA_DE_PROCESO`. Anotado en `progress/current.md` |
| Un fallo de `build_compras` deja sin la vista | Igual que hoy; `check-declarados` lo detecta |
| Power BI con `estado` sin cualificar | §1; columnas al final, se revisa si un informe falla |

**Límite del servicio:** todo cabe en este repositorio. Nada toca `sigrid-api` ni
la configuración del servidor compartido.

## 9. Pasos MANUAL (tras APROBADO y merge a `main`; los lanza el humano)

Fuera de 00:00-05:00 UTC, desde la raíz del repositorio, en este orden.

0. Tag actual (vuelta atrás): `az containerapp job show -n caj-datamart-seg-dev -g
   rg-datamart-seg-dev --query "properties.template.containers[0].image" -o tsv`.
1. `powershell -NoProfile -File infra/70_build_image.ps1` → anotar el tag nuevo.
2. `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag nuevo>` y el `az`
   del paso 0 → debe acabar en `:<tag nuevo>`.
3. `.venv/Scripts/python.exe main.py build-compras` (sin ingesta) → SUCCESS, con
   `estado_documentos` sin error, ~9 min.
4. Cifras, cada una con `.venv/Scripts/python.exe -c "import main, sys; pg =
   main._get_pg(); pg._bootstrap_done = True; print(pg.filas_solo_lectura(sys.argv[1],
   60))" "<consulta>"` (cambian poco cada noche):
   - `SELECT estado_codigo, count(*) FROM compras.albaranes GROUP BY 1 ORDER BY 2 DESC`
     → FAC ~270.200, CON ~37.600, PDT ~7.700, COM ~410, NULL 10.
   - `SELECT origen_fecha, count(*), count(en_estado_desde) FROM
     compras.v_estado_documentos WHERE tipo_documento_codigo = 14 GROUP BY 1` →
     FACTURACION ~235.300 (todas con fecha), ALTA ~7.700 (todas), SIN_HISTORIAL
     ~72.900 (0).
   - `SELECT tipo_documento_codigo, tipo_documento, count(*) FROM
     compras.v_estado_documentos GROUP BY 1, 2 ORDER BY 1, 2` → ALBARAN ~312.650,
     PROFORMA ~2.960, NOTA 278, OTRO 1; 44, 15 y 46, los de sus tablas.
   - `SELECT count(*) FROM information_schema.column_privileges WHERE table_schema
     = 'compras' AND table_name = 'albaranes' AND grantee = 'mcp_sigrid_dm_ro'`
     → 49. Si no: `.venv/Scripts/python.exe main.py apply-grants`.
5. `.venv/Scripts/python.exe main.py publicar-diccionario` → **v70, 256 objetos**.
6. `.venv/Scripts/python.exe main.py check-diccionario` → OK (antes del paso 5
   devuelve 1, y es lo esperado); `.venv/Scripts/python.exe main.py check-declarados`
   → sin faltantes; `.venv/Scripts/python.exe main.py check-unicidad --timeout 300`
   → sin duplicados.
7. Reinicio del MCP: `az containerapp show -g rg-mcp-bbdd-dev -n ca-mcp-bbdd-dev
   --query properties.latestReadyRevisionName -o tsv` y `az containerapp revision
   restart -g rg-mcp-bbdd-dev -n ca-mcp-bbdd-dev --revision <revision> -o none` →
   `contexto_bbdd()` abre con «Versión 70».
8. R16-R18 por el MCP, sin explicarle nada; anotar en `progress/impl_F-153.md`.
9. `bash harness/init.sh` en verde sobre `main`.

**Vuelta atrás** (desde el puesto, en este orden):

1. Job: `powershell -NoProfile -File infra/85_update_job.ps1 -Tag <tag del paso 0>`,
   comprobado con el `az` del paso 0.
2. `git switch --detach <sha del merge de F-153>^1`.
3. `.venv/Scripts/python.exe main.py build-compras`: el SQL viejo rehace la tabla
   sin las columnas y la vista sin el tipo 14 (lee el árbol local). Si se omite,
   lo hace la nocturna, y entre tanto los datos llevan más que la ficha v69.
4. `.venv/Scripts/python.exe main.py publicar-diccionario` → **v69**, 256 objetos:
   publica las fichas del ÁRBOL local, no las de la imagen.
5. `git switch main` (`check-diccionario` dará 1 desde `main`: compara con la v70
   del árbol).
6. Reinicio del MCP (paso 7) → «Versión 69».

No queda nada en Azure: el DDL es `DROP` + `CREATE`, sin columnas añadidas por
`ALTER`, y `idx_com_alb_est` cae con la tabla.

## 10. Tests de humo (sin red ni BBDD)

- `test_f153_sql.py`, sobre el texto: R1-R7, R9 y R10, incluidos los
  `TIPOS_DOCUMENTO_ALBARAN` contra `fn_tipo_documento` en `00_setup.sql`.
- `test_f153_dominio.py`: cada rama de R7 y su orden. FAC con y sin fecha, con y
  sin paso, con paso a 10 (`PASO` gana) y a 3; COM con y sin paso (R8); PDT; 0.
- `test_f153_diccionario.py`: R11-R14 y `valores` contra el dominio.
- `test_f132_*`: lo fijado a tres familias o tres orígenes se actualiza, sin
  borrar lo que defiende.
