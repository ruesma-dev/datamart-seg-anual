<!-- specs/F-102-obra-duplicada-empresa-28/requirements.md -->
# F-102 · Requisitos — la obra y el recurso son de una empresa: claves legibles y ficha de Ruesma

EARS; cada R >= 1 test `test_f102_rN_...` offline salvo las **MANUAL**. Rigor
`estandar`. Cifras **medidas en solo lectura el 2026-09-23** (`raw` de las 00:48
UTC en sesion `read_only`, Sigrid por `sigrid-api`, `mart`/`cierre` por MCP):
`design.md` §1. Decisiones finales del humano del 2026-09-23: `design.md` §8.
**Modelo** (humano): las obras son por empresa; el mismo codigo es la misma obra
vista desde cada empresa, sin consolidar. Este hotfix solo publica
IDENTIFICADORES; cambiar el seguimiento es F-106.

## La ficha de Ruesma, en un solo sitio (`maestro`)

R1. El sistema debe publicar `maestro.v_obra_fichas`, una fila por ficha de obra
(922), leyendo solo `raw`, con `obra_id`, `codigo_obra`, `empresa_id`
(`con.emp`), `clave_obra`, `marcada_vigente`, `num_cierres`,
`num_fichas_codigo`, `rango_ficha`, `es_ficha_principal` y `obra_principal_id`.

R2. El sistema debe ordenar las fichas de un codigo por estos campos, y solo
estos, en este orden: (1) **empresa 1 (Ruesma) antes que cualquier otra**; (2)
marcada en `raw.conext` con `cod = '15'`; (3) `num_cierres` (`raw.obrfas`) DESC;
(4) `con.tiemod` DESC; (5) `ide` DESC, solo como desempate: **ninguna regla elige
por `obra_id` menor**.

R3. SI un codigo no tiene ficha de la empresa 1, o tiene mas de una, ENTONCES
el sistema debe decidir con (2)-(5) de R2. Hoy: 0001-0005 sin ficha de la 1, y
ningun codigo con dos.

R4. `es_ficha_principal` (`rango_ficha = 1`): exactamente una por codigo, 846 de
846. SI una ficha tiene varias filas `cod = '15'` en `raw.conext`, ENTONCES no
debe multiplicarse: la marca se evalua con `EXISTS`.

R5. `obra_principal_id` debe ser la ficha de la empresa 1 de su codigo, y la
propia si el codigo no la tiene. Solo se publica en `maestro` (referencia).

R6. `clave_obra` debe ser `empresa_id::text || '-' || codigo_obra` (p. ej.
`1-0581`, `27-0581`) y ser unica: 922 claves para 922 fichas, 0 codigos vacios.

## `stg.obras` no cambia

R7. El sistema NO debe cambiar `stg/03_obras.sql` ni la eleccion de ficha de
`stg.obras`: el fichero queda identico al de `main` (test por hash) y
`test_f073_r26` sigue como esta. Pasar el seguimiento a «solo Ruesma» es F-106.

## `maestro.obras`: empresa y claves, sin perder filas

R8. El sistema debe anadir a `maestro.obras`, AL FINAL y en este orden,
`empresa_id`, `nombre_empresa`, `clave_obra`, `num_fichas_codigo`,
`es_ficha_principal` y `obra_principal_id`, conservando las anteriores en orden.

R9. El sistema debe seguir publicando una fila por ficha (922), uniendo
`maestro.v_obra_fichas` con `LEFT JOIN` por `obra_id` y sin filtrar nada; las
marcas salen de esa vista, sin recalcularse.

R10. [D3] `nombre_empresa` debe salir de `raw.auxemp` por `numemp = con.emp`
con `LATERAL ... ORDER BY ... LIMIT 1`, para no multiplicar filas.

R11. **MANUAL (lectura)**. Una fila por `codigo_obra` con `es_ficha_principal`;
`clave_obra` unica; y la principal difiere de la ficha de `stg.obras`
exactamente en 0581, 0606, 0671 y 0720.

R12. **MANUAL (lectura)**. Principales de cuatro digitos `>= '0672'`: 57, todas
de la empresa 1, 48 con `dir1` (la cifra de Juan Romero).

## Ingesta del nombre de la empresa [D3]

R13. `auxemp` en `config/tables_sigrid.yaml` (38 filas, refresco completo) y `TOTAL_TABLAS` +1.

R14. `raw.yaml` debe tener ficha de `auxemp`: `numemp` es lo que guarda `con.emp`.

## Diccionario

R15. La ficha de `maestro.obras` debe documentar las seis columnas, explicar el
modelo (misma obra vista desde cada empresa, sin consolidar), dar la cobertura de
direccion sobre las principales por tramo y con fecha en vez de «un tercio», y
declarar que las 103 fichas de la empresa 28 no traen direccion ni cliente.

R16. Esa ficha debe decir que por `codigo_obra` se cruza **siempre** con
`empresa_id` o por `clave_obra`, y que `obra_principal_id` es solo referencia de
cual es la ficha de Ruesma: no se usa para agregar hechos de otras empresas.

R17. El sistema debe publicar la regla dura `R-CODIGO-POR-EMPRESA` (bloqueante)
para obras y recursos, con ambito `maestro.obras`, `maestro.v_obra_fichas`,
`stg.obras`, `personal.partes_lineas`, `personal.recursos`,
`retenciones.movimientos`, `maestro.centros_coste` y las cuatro tablas de
`compras` con obra, con las cifras de `design.md` §1.

R18. La ficha de `stg.obras` y `R-UNIVERSO-OBRA` deben decir que `stg.obras`
sigue eligiendo como hasta hoy, en que cuatro codigos difiere de
`es_ficha_principal`, y que lo resuelve F-106.

R19. La ficha de `maestro.v_obra_fichas` (nueva) y la de `raw.condir` en
`maestro.obras` (0 de 922 fichas de obra con fila, tambien en Sigrid).

R20. `version` de `00_global.yaml` debe subir en uno sobre la de `main`.

## `compras` y las demas fichas que apuntan a `maestro.obras.obra_id`

R21. El sistema debe anadir `empresa_id` y `clave_obra`, al final y en ese
orden, a `compras.v_pbi_contrato_consumo`, `v_pbi_proveedor_obra`,
`v_pbi_albaranes_sin_facturar`, `v_pbi_partida_coste` y `v_control_forma_pago`,
tomadas de `maestro.v_obra_fichas` con `LEFT JOIN` por `obra_id` (NULL si
`obra_id` es NULL), sin cambiar su grano; en `v_pbi_proveedor_obra`, sobre el
resultado ya agregado. Ninguna vista de `compras` publica `obra_principal_id`.

R22. Las fichas de esas cinco vistas en `compras.yaml` deben documentar las dos
columnas, declarar la relacion `clave_obra -> maestro.obras.clave_obra` (N:1) y
advertir que **agregar por `codigo_obra` mezcla empresas** (la UTE dentro de la
obra de Ruesma, que no se consolida): se agrega por `clave_obra`.

R23. Las fichas de `compras.contratos`, `albaran_lineas`, `factura_lineas`,
`fact_compras_linea`, `retenciones.movimientos`, `v_pbi_retencion_obra`,
`maestro.proveedores_obra` y `maestro.centros_coste` deben decir, en `obra_id`
y en el `porque` de su relacion, que el `obra_id` es la ficha de la empresa del
documento (cifra medida), que su empresa y clave salen de `maestro.obras`, y que
`obra_principal_id` **no** sirve para agregar hechos de otras empresas.

R24. [D2 A] El sistema NO debe reescribir ningun `obra_id` publicado: los SQL de
las tablas de `compras` (`01`, `02`, `05`, `07`), de `retenciones`, de
`personal` y `maestro/03_*`, `04_*` no nombran `v_obra_fichas`, ningun SQL de
`compras` nombra `obra_principal_id` y ningun step cambia su `depends_on`.

R25. `01_obras.sql` (cabecera y `COMMENT`) sin «un tercio» ni las frases que
veta `test_f073_r11`.

## `personal.recursos` (correo de Juan, 23-09) — DEPENDE DE F-101 EN `main`

R26. DONDE F-101 este fusionado en `main`, `personal.recursos` debe publicar al
final `empresa_id`, `nombre_empresa` (lateral a `raw.auxemp`) y `clave_recurso`
= `empresa_id::text || '-' || codigo_recurso`, con `ADD COLUMN IF NOT EXISTS`,
sin perder filas (2.618) ni anadir `WHERE` (los vetos de `test_f057` en verde).

R27. La ficha de `personal.recursos` debe declarar que la clave legible unica es
`clave_recurso` —61 codigos repetidos, 0 dentro de una empresa, 2.618 claves
para 2.618 recursos— y que una persona puede tener una ficha por empresa
(`MO/0009`). [D5 A] No se publica marca de «misma persona».

## Documentacion y verificacion

R28. `docs/ARCHITECTURE.md` debe explicar el modelo (obras y recursos por
empresa, claves legibles, ficha de Ruesma, F-106) y el recuento de tablas.

R29. `azure-apps/datamart_seg_anual.md` debe recoger las columnas nuevas de
`maestro.obras`, de las vistas de `compras` y de `personal.recursos`, y la regla;
commit en `azure-apps`. Sin aviso a `facturas`, que es independiente (D4).

R30. **MANUAL (humano, tras la nocturna)**. `check-unicidad`,
`check-relaciones` y `check-declarados` sin errores nuevos atribuibles a F-102.

R31. `bash harness/init.sh` debe terminar en verde.
