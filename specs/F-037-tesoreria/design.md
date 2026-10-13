<!-- specs/F-037-tesoreria/design.md -->
# F-037 · Diseño (fase 1)

Mediciones: `progress/spec_F-037.md`. Requisitos: `requirements.md`. Decisiones: §8.

## 1. Encaje y límite

Esquema MÓDULO nuevo, como `contabilidad`: lee solo `raw` y la vista
`maestro.centros_coste` (SQL puro sobre `raw`), y lo restringido vive FÍSICAMENTE en otro
esquema que el rol estándar nunca recibe (F-135). Sin ingesta nueva: `pag`, `cob`, `con`,
`conest`, `auxefp`, `auxnap`, `auxban`, `rpa`, `prv` y `dcf` ya se copian cada noche.

```
raw.pag ∪ raw.cob ─► tesoreria_restringida.efectos   (completa + restringido/motivo; autorizado y total)
                          │ NOT restringido
                          ▼
                     tesoreria.efectos ──► compras.vencimientos (VISTA: PAGO y factura de compra)
                     tesoreria.efectos_restringidos_mes (solo recuentos)
```

**Fase 2 fuera** (proyección de obra, devengo → caja): la ficha lo dice.
**Límite de microservicio.** Todo es ETL de este repositorio. Lo que NO es de aquí y se deja
escrito como contrato: que `mcp-bbdd` añada `tesoreria` a la lista blanca de sus dos
conexiones y `tesoreria_restringida` a la del total (su F-008; hoy un esquema nuevo no se ve
por el MCP sin cambiar su `config.yaml`, memoria «servidor MCP»), y el rol propio de Power BI
(F-087). Hasta entonces Power BI lee `tesoreria` y nadie lee la restringida.

## 2. Ficheros

**Crear**
- `etl_sigrid/domain/tesoreria.py` — oráculo del criterio y del estado (§3).
- `etl_sigrid/infrastructure/postgres/sql/tesoreria/00_setup.sql`, `01_efectos_completo.sql`,
  `02_efectos_general.sql`, `03_efectos_restringidos_mes.sql` (§4).
- `application/steps/build_tesoreria_step.py` — `SUB_PASOS` como `build_contabilidad_step.py`.
- `config/diccionario/tesoreria.yaml` y `tesoreria_restringida.yaml`.
- `tests/test_f037_{dominio,sql,paso,grants,diccionario}.py`.

**Modificar**
- `sql/compras/05_vencimientos.sql` — de `CREATE TABLE AS` a `CREATE VIEW` sobre
  `tesoreria.efectos` (§4.4). La cabecera conserva el porqué de F-080 (DA-9, trampas).
- `main.py` — `BuildTesoreriaStep` en `build_pipeline_steps` DELANTE de `BuildComprasStep`
  (con su comentario) y comando `build-tesoreria` (patrón `build-contabilidad`).
- `config/settings.py` — `tesoreria` en `DEFAULT_CONSUMPTION_SCHEMAS`;
  `DEFAULT_VETOED_SCHEMAS = "contabilidad_restringida,tesoreria_restringida,raw"`;
  `DEFAULT_RESTRICTED_SCHEMAS = "contabilidad_restringida,tesoreria_restringida"`, y sus
  comentarios. `.env.example` igual.
- `infra/sql/02_roles.sql` — §6.
- `etl_sigrid/domain/diccionario.py` — los dos esquemas en `ESQUEMAS_DEL_DATAMART`.
- `config/diccionario/00_global.yaml` — entradas de los dos esquemas, regla
  `R-TESORERIA-ESTADO`, `R-CONTABILIDAD-RESTRINGIDA` ampliada a tesorería (o hermana
  `R-TESORERIA-RESTRINGIDA`, lo decide el implementer por longitud), `version` +1 (hoy 50:
  comprobar el valor real). `compras.yaml`: `compras.vencimientos` pasa a `vista` y cita su
  origen y que su frescura es la de `build_tesoreria`.
- Tests que fijan listas que cambian: `test_f047_steps.py` (pasos de `run-all`),
  `test_f006_formato.py` y `test_f057_personal.py` (recuento de esquemas),
  `test_f135_grants.py`/`test_f136_*` (listas de `settings` y de `02_roles.sql`),
  `test_f080_sql.py`/`test_f080_diccionario.py` (05 pasa a vista; las aserciones de
  semántica se trasladan a `test_f037_sql.py`, no se borran).
- `docs/ARCHITECTURE.md` (§ capas, § nocturna: quince pasos), `CLAUDE.md` (mapa: el esquema
  y «quince pasos»), `azure-apps/datamart_seg_anual.md` (qué lee cada rol, objetos nuevos,
  contrato para `mcp-bbdd`), `azure-apps/mcp_bbdd.md` §2 (una línea que enlaza al contrato,
  sin copiarlo). Commit local en `azure-apps`, sin push.

**No se tocan**: `sql/retenciones/*` (su estado de CLIENTE sigue el de F-094; unificarlo es
otra feature), `sql/compras/06_pago_factura.sql` (lee la vista igual que la tabla),
`sql/contabilidad/*`, `domain/restriccion_personal.py` (se importa, no se cambia),
`config/tables_sigrid.yaml` (sin ingesta nueva), `grants.py`, `apply_grants_step.py` y
`postgres_client.py` (son de listas: basta `settings`), `stg`, `mart`, `cierre`.

## 3. Dominio (`domain/tesoreria.py`, sin dependencias de infraestructura)

- Constantes: `SENTIDO_PAGO = "PAGO"`, `SENTIDO_COBRO = "COBRO"`; `TIP_EFECTO_PAGO = 25`,
  `TIP_EFECTO_COBRO = 24`; `TIP_TERCERO_EMPLEADO = 43`; `TIP_DOCUMENTO_NOMINA = 306`;
  `EST_PAGADO = 10`; `EST_SUSTITUIDO = (14, 15)`; estados `PREVISTO`, `REALIZADO`, `BAJA`;
  motivos `NATURALEZA`, `CUENTA`, `CUENTA_SIN_RESOLVER`, `TERCERO_EMPLEADO`,
  `DOCUMENTO_NOMINA`. Importa `es_cuenta_restringida` y `REGEX_CUENTA_RESTRINGIDA` de
  `restriccion_personal` (R2).
- `EfectoTesoreria(natide, cuenta_id, codigo_cuenta, tip_tercero, tip_documento)` (dataclass
  congelada, `None` = no informado).
- `motivo_restriccion_efecto(e) -> str | None` (R1): primer motivo que casa en el orden de
  arriba; `cuenta_id` sin `codigo_cuenta` → `CUENTA_SIN_RESOLVER` (falla cerrado, hoy 0).
- `es_efecto_restringido(e) -> bool`.
- `estado_tesoreria(est, fecrea, fecbaj) -> str` (R3): `None` y 0 cuentan como «sin valor».
- `importe_flujo(sentido, importe) -> Decimal` (R4); sentido desconocido → `ValueError`.
  Si D11-A: `es_previsto_antiguo(estado, vencimiento, fecha_build) -> bool` (2 años).

El SQL no lo llama: lleva los mismos literales y `test_f037_sql.py` los compara (F-135).

## 4. SQL de `tesoreria` (un fichero, una transacción)

### 4.1 `00_setup.sql`
`CREATE SCHEMA IF NOT EXISTS tesoreria`, `tesoreria_restringida`; `tesoreria.fn_fecha` y
`tesoreria.fn_serie`, COPIAS de las de `compras` (un módulo no depende de otro que se
construye después; un test compara los cuerpos); `CREATE TABLE IF NOT EXISTS` de las tres
tablas con sus PK (`efecto_id`; `(empresa_id, sentido, anio, mes, estado_tesoreria)`) y
`CREATE INDEX IF NOT EXISTS` (sentido, estado, vencimiento, tercero, obra, documento,
remesa). Sin `ALTER DEFAULT PRIVILEGES` ni `GRANT`: los permisos son de `apply_grants`.
Columnas futuras: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (precedente F-101).

### 4.2 `01_efectos_completo.sql` → `tesoreria_restringida.efectos`
`TRUNCATE` + `INSERT ... SELECT` de un `UNION ALL` de dos ramas (PAGO desde `raw.pag`, COBRO
desde `raw.cob`) con las mismas uniones que `compras/05_vencimientos.sql` de hoy:
`JOIN raw.con c ON c.ide = x.ide` (el EFECTO: `cod`, `res`, `emp`, `est`, `fecbaj`),
`LEFT JOIN raw.con d` (documento origen: `cod`, `tip`), `raw.con t` (tercero: `res`, `tip`),
`raw.prv` (CIF, solo PAGO), `raw.con cue` (cuenta: `cod`, `res`), `raw.conest` con
`tip = 25` o `24` según rama, `raw.auxefp`, `raw.auxnap`, `raw.auxban` ×2, `raw.rpa` (solo
PAGO) y `raw.con` de la remesa, `maestro.centros_coste` por `cenide`. `es_factura_compra =
EXISTS (SELECT 1 FROM raw.dcf WHERE ide = p.conide)` en PAGO, `false` en COBRO.
`restringido`/`motivo_restriccion` con un `CASE` en el orden del dominio, con
`REGEX_CUENTA_RESTRINGIDA`, 43 y 306 literales. Las expresiones de las columnas que hereda
`compras.vencimientos` se copian TAL CUAL de su SQL de hoy (mismos tipos: `p.ide`, `c.est`,
`COALESCE(p.tot,0)::NUMERIC(18,2)`, `r.imptot::NUMERIC`), con `tesoreria.fn_fecha` y
`tesoreria.fn_serie` en vez de las de `compras` (§4.1). Orden de columnas (el del setup):

`efecto_id, sentido, empresa_id, codigo_efecto, descripcion_efecto, serie_efecto,
documento_id, codigo_documento, tipo_documento, es_factura_compra, tercero_id,
tercero_nombre, tercero_cif, fecha_emision, fecha_vencimiento, fecha_real, importe,
importe_flujo, estado_tesoreria, estado_codigo, estado_sigrid, efecto_anulado,
fecha_anulacion, medio_pago_id, medio_pago, naturaleza_pago_id, naturaleza_pago,
cuenta_contable_id, cuenta_contable, cuenta_contable_nombre, banco_id, banco, sucursal_id,
sucursal, retencion_id, centro_coste_id, obra_id, codigo_obra, nombre_obra, remesa_id,
codigo_remesa, fecha_remesa, importe_remesa, [previsto_antiguo, si D11-A,] restringido,
motivo_restriccion`

### 4.3 `02_efectos_general.sql` y `03_efectos_restringidos_mes.sql`
`02`: `TRUNCATE tesoreria.efectos; INSERT ... SELECT` de todas las columnas salvo las dos
últimas `WHERE NOT restringido`, con `importe_remesa = CASE WHEN remesa_id IN (remesas con
algún restringido) THEN NULL ELSE importe_remesa END` (R11). Guarda R12 en un `DO`: 0 filas
de la general que cumplan el criterio recalculado desde `raw` (natide, cuenta, tip 43/306) y
`general + COUNT(*) FILTER (WHERE restringido) = completa`; si no, `RAISE EXCEPTION`.
`03`: `TRUNCATE` + `INSERT` de `COUNT(*)` por empresa, sentido, año y mes de
`fecha_vencimiento` y estado, `WHERE restringido` (sin vencimiento: año y mes NULL → la PK
no admite NULL: se usa 0, y la ficha lo dice).

### 4.4 `compras/05_vencimientos.sql` (vista)
Un `DO` borra `compras.vencimientos` sea tabla (`DROP TABLE ... CASCADE`) o vista (`DROP
VIEW ... CASCADE`) consultando `pg_class.relkind`; `CREATE VIEW compras.vencimientos AS
SELECT efecto_id AS vencimiento_id, documento_id AS factura_id, codigo_documento AS
codigo_factura, ..., estado_codigo AS estado_pago_codigo, estado_sigrid AS estado_pago, ...
FROM tesoreria.efectos WHERE sentido = 'PAGO' AND es_factura_compra`, en el orden exacto de
hoy. `COMMENT ON VIEW` con las dos trampas de F-080. Los `CREATE INDEX` de 05 desaparecen
(los lleva `tesoreria.efectos`). `06` la reconstruye detrás, como hoy.

## 5. Paso y nocturna

`BuildTesoreriaStep`: `name = "build_tesoreria"`, `stage = "build_aux"`, `depends_on =
["ingest_raw"]` (lee la vista `maestro.centros_coste`, SQL puro sobre `raw`: mismo motivo
que contabilidad). En `build_pipeline_steps` va entre `BuildMaestrosStep` y
`BuildComprasStep`. **`build_compras` NO lo declara en `depends_on`** (D9): la vista solo
necesita que `tesoreria.efectos` EXISTA, y existe desde el primer build; si una noche
`build_tesoreria` falla, su `TRUNCATE` se deshace y compras sigue leyendo la de ayer.

**Coste.** Nocturna del 13-10: 4 h 52 min (tope del job 7 h). La unión con todas sus
uniones lee 278.866 filas en 2,0 s; `compras.vencimientos` ocupa 60 MB. Estimado +1-3 min
(dos `INSERT` de ~279 k y ~242 k filas con índices) y +0,2 GB; `build_compras` ahorra su
`CREATE TABLE` de 05. Se mide en el build manual del despliegue (R29).

## 6. Permisos (`settings`, `apply_grants`, `02_roles.sql`)

`apply_grants` ya es de listas (F-135/F-136): con `settings` cambiado, cada noche concede
`tesoreria` al estándar, veta `tesoreria_restringida` (REVOKE de esquema, tablas y
privilegio por defecto), concede la restringida al autorizado y verifica en el catálogo que
el estándar no la lee (FAILED si la lee). El total la hereda por pertenencia. Ningún cambio
de código en `grants.py` ni en el paso; los tests de F-135/F-136 se amplían con el esquema.

`infra/sql/02_roles.sql`: allí donde hoy aparece `ARRAY['contabilidad_restringida','raw']`
(veto al estándar, veto al total, comprobaciones finales) entra `tesoreria_restringida`
(salvo en el veto al total: el total SÍ la lee); al bucle de consumo, `tesoreria`; y para el
autorizado `GRANT USAGE`, `SELECT ON ALL TABLES` y `ALTER DEFAULT PRIVILEGES FOR ROLE
sigrid_dm_etl` sobre `tesoreria_restringida`, igual que con la contable. Crea los dos
esquemas con `SET ROLE sigrid_dm_etl`. El test de listas iguales a `settings` lo fija.
No hace falta para que funcione (lo hace `apply_grants`); se re-ejecuta para que no diverjan.

## 7. Despliegue (MANUAL, en este orden, tras el review)

1. Que el job no fije `PG_CONSUMPTION_SCHEMAS`, `PG_VETOED_SCHEMAS` ni `PG_RESTRICTED_SCHEMAS`
   (`az containerapp job show`, solo nombres); si los fija, hay que cambiarlos allí.
2. Imagen con tag fechado y job apuntado a ella (comprobar el tag del job).
3. `02_roles.sql` como administrador.
4. Desde el puesto: `build-tesoreria` (anotar duración), `build-compras`, `apply-grants`.
5. R16, R23 y R30; `publicar-diccionario` y los tres `check-*`; reiniciar el MCP y avisar a
   `mcp-bbdd` del contrato. 6. Al día siguiente, sin tocar nada: `apply_grants` ok y R23 negativa.

## 8. Decisiones

**Aprobación del humano (2026-10-13)**, por el líder: «la obra se puede sacar de los
contratos, revisa si asi ayuda a machear mas obras. amplia la explicacion del contraste con
contabilidad. puede ser que venga de que los efectos antiguos no estaban bien (nos paso antes
con las retenciones) lo demas ok». **D1, D2, D3, D5, D6, D7, D8, D9 y D10 APROBADAS con la
opción A** (tabla única + vista de compras; bajas marcadas con regla dura; esquema
`tesoreria_restringida`; cobros ya con su cobertura; solo recuentos para el estándar; unión
de los cuatro criterios y los 429 autónomos visibles; remesa mixta a NULL; delante de compras
sin `depends_on`; nombres). Texto íntegro con las alternativas: `progress/spec_F-037.md` §4.
**Abiertas: D4 (remedida) y D11 (nueva).**

**D4 · Obra, remedida con el contrato** (`progress/spec_F-037.md` §5). Escalones probados en
pagos no personales: 1) centro → obra; 2) contrato de la factura (`dcf.ctride` y los de sus
líneas, directo o por albarán, como `compras.fact_compras_linea`) → `compras.contratos.obra_id`;
3) obra de la cabecera o de las líneas de la factura.

| pagos no personales | efectos | importe | cartera viva futura |
|---|---|---|---|
| 1 · centro | 200.143 (91,0 %) | 1.024,9 M€ | 7.665 · 52,9 M€ (96,6 %) |
| 2 · contrato (si el centro no da) | **6** | 0,07 M€ | 0 |
| 3 · cabecera o líneas | 112 (+3 ambiguas) | 0,26 M€ | 0 |
| sin obra | 19.635 | 126,4 M€ | 268 · 2,1 M€ |

Los sin obra NO tienen obra que encontrar: 12.891 pagos sin documento (94,4 M€),
1.612 facturas a centros de estructura (`GG`, `0001`...: 22,2 M€) y 5.129 facturas sin
centro, sin contrato y sin obra en cabecera ni líneas (9,7 M€). Discrepancias cuando hay dos
fuentes: centro ≠ contrato en 323 efectos (25 más con contratos de varias obras) y centro ≠
cabecera en 495 de 190.255; manda el centro, que es la imputación del propio efecto.
**Cobros**: sin vía; las ventas no se ingieren (F-040), `con.obr` está vacío en efectos y documentos,
y «cliente con una sola obra» resolvería 38 efectos, ninguno previsto (y es una conjetura).
**Recomendación: A, solo el centro** (el contrato no ayuda: +6 efectos y una regla de
precedencia más). (B) Centro y después contrato: +6 efectos, +66 k€.

## 8 bis. El contraste con la contabilidad (ampliado; detalle en `progress/spec_F-037.md` §6)

**PAGO previsto 80,1 M€ frente a 78,8 M€ de 40+41 no es un cuadre: son dos errores que se
compensan.** (+) 3,9 M€ de previstos **vencidos hace más de 2 años** (3,1 M€ de más de 5) que
la contabilidad ya no sostiene: en 223 cuentas de proveedor el saldo cuadra al céntimo SOLO si
se quitan (2,77 M€); son la hipótesis del humano, medida, y el mismo patrón de F-094 (efectos
no punteados; «los grandes descuadran: historia anterior a 2016»). (−) Saldo sin efecto:
anticipos (407), 415, 419 y facturas aún sin efectos. La comparación cuenta a cuenta solo
vale en 815 cuentas (8,2 M€, cuadre exacto): al emitir un pagaré la deuda pasa de 400/410 a
401/411 (29,6 M€ de saldo) y el efecto conserva la cuenta de origen; por eso el contraste es
del grupo 40+41 entero. **COBRO previsto 40,2 M€ frente a 47,5 M€ de 43**: 433+434 (empresas
del grupo y asociadas) suman 12,0 M€ en contabilidad y 1,1 M€ en efectos (se facturan sin
efecto), y en sentido contrario 2,2 M€ de previstos vencidos hace más de 2 años.
**Otro hallazgo con fecha**: desde 2020 el pago por remesa deja `est = 10` SIN `fecrea`
(41.884 pagos y 2.106 cobros; con vencimiento anterior a 2020, 27): `fecha_real` vacía en un efecto
REALIZADO no es una falta, y por eso el estado lee `est` (R3). La ficha lo dice.

**D11 · NUEVA, para que la decida el humano: el previsto antiguo.** (A) **Recomendada**:
columna `previsto_antiguo` (PREVISTO con vencimiento anterior a la fecha del build menos 2
años; hoy 2.361 pagos, 3,9 M€, y 398 cobros, 2,2 M€) y regla dura: la cartera de un flujo de
caja es `PREVISTO AND NOT previsto_antiguo`; lo antiguo es deuda por depurar en Sigrid, no
caja. Precedente: `retenciones.movimientos.vencida_sin_liquidar`. (B) Solo la regla: la IA
filtra con `CURRENT_DATE` y puede olvidarlo. (C) Un estado `SOSPECHOSO`: reclasificaría un
hecho de Sigrid con un criterio nuestro. Umbral de 2 años: el de las 223 cuentas que cuadran.

## 9. Riesgos

- **Primer despliegue**: `05` necesita `tesoreria.efectos`; si se lanza `build-compras`
  antes que `build-tesoreria`, falla en 05 y deja la tabla de ayer (transacción). Orden §7.
- **Listas de esquemas fijadas en un `.env` o en el job**: la restringida no se concede a nadie (falla cerrado).
- **Bajas de cobro con retención** (D2) y **previstos antiguos** (D11): declarados, no resueltos.
- **Lo que no arregla**: hasta que `mcp-bbdd` amplíe su lista blanca el MCP no ve `tesoreria`.
