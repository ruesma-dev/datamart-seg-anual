<!-- specs/F-102-obra-duplicada-empresa-28/requirements.md -->
# F-102 · Requisitos — la obra dada de alta en dos empresas: empresa y ficha principal en `maestro.obras`

EARS; cada R >= 1 test `test_f102_rN_...` offline salvo las **MANUAL**. Rigor
`estandar`. Cifras **medidas en solo lectura el 2026-09-23** (`raw` de las 00:48
UTC en sesion `read_only`, Sigrid por `sigrid-api`, `mart`/`cierre` por MCP):
`design.md` §1. **[Dn]** = decision del humano del 2026-09-23 (`design.md` §8).

## Una sola definicion de "ficha principal" (`stg`)

R1. El sistema debe publicar `stg.v_obra_fichas`, una fila por ficha de obra
(922) con `obra_id`, `codigo_obra`, `empresa_id` (`con.emp`), `marcada_vigente`,
`num_cierres`, `en_universo_seguimiento`, `num_fichas_codigo`, `rango_ficha`,
`es_ficha_principal` y `obra_principal_id`.

R2. [D1: «la ficha principal es la de Construcciones Ruesma»] El sistema debe
ordenar las fichas de un codigo por estos campos, y solo estos, en este orden:
(1) **empresa 1 antes que cualquier otra**; (2) marcada en `raw.conext` con
`cod = '15'`; (3) `num_cierres` (`raw.obrfas`) DESC; (4) `con.tiemod` DESC; (5)
`ide` DESC, solo como desempate: **ninguna regla elige por `obra_id` menor**.

R2b. SI un codigo no tiene ninguna ficha de la empresa 1, o tiene mas de una,
ENTONCES el sistema debe decidir entre ellas con (2)-(5) de R2. Hoy: 5 codigos
sin empresa 1 (0001-0005, fuera del universo) y 0 con dos fichas de la 1.

R3. `es_ficha_principal` (`rango_ficha = 1`): una por codigo, 846 de 846.

R4. SI una ficha tiene varias filas `cod = '15'` en `raw.conext`, ENTONCES no
debe multiplicarse: la marca se evalua con `EXISTS`, no con `JOIN`.

R5. `en_universo_seguimiento` debe usar los filtros de hoy de `stg/03_obras.sql`
sin cambiar ninguno, escritos en un unico sitio.

R6. `obra_principal_id` debe ser la principal de su codigo MIENTRAS la ficha
este en el universo, y su propio `obra_id` fuera (alli las empresas reutilizan
codigos para obras distintas: 0001-0005, CM, CP, GG, POSTV2, VAR).

R7. `stg.obras` debe salir de `stg.v_obra_fichas` con `en_universo_seguimiento
AND es_ficha_principal`, sin cambiar sus columnas ni su grano.

R8. **MANUAL (lectura)**. Contra el `raw` actual, `stg.obras` sigue con 584
filas y cambia solo 0720, 0581, 0606 y 0671, a la empresa 1 (`design.md` §1.2).

## `maestro.obras`: empresa y ficha principal, sin perder filas

R9. El sistema debe anadir a `maestro.obras`, AL FINAL y en este orden,
`empresa_id`, `nombre_empresa`, `es_ficha_principal`, `num_fichas_codigo` y
`obra_principal_id`, conservando todas las columnas anteriores en su orden.

R10. El sistema debe seguir publicando una fila por ficha (922), uniendo
`stg.v_obra_fichas` con `LEFT JOIN` por `obra_id` y sin filtrar nada.

R11. [D3] `nombre_empresa` debe salir de `raw.auxemp` por `numemp = con.emp`
con `LATERAL ... ORDER BY ... LIMIT 1`, para no multiplicar filas.

R12. Las tres marcas deben salir de `stg.v_obra_fichas`, sin recalcularse.

R13. **MANUAL (lectura)**. Una fila por `codigo_obra` con `es_ficha_principal`,
y las principales del universo son exactamente `stg.obras`.

R14. **MANUAL (lectura)**. Principales de cuatro digitos `>= '0672'`: 57, todas
de la empresa 1, 48 con `dir1` (la cifra de Juan Romero).

## Ingesta del nombre de la empresa [D3]

R15. El sistema debe declarar `auxemp` en `config/tables_sigrid.yaml` (38 filas
el 2026-09-23, refresco completo) y subir `TOTAL_TABLAS` en uno.

R16. `raw.yaml` debe tener ficha de `auxemp`: `numemp` es lo que guarda `con.emp`.

## Diccionario

R17. La ficha de `maestro.obras` debe documentar las cinco columnas y dar la
cobertura de direccion sobre las principales, por tramo y con fecha, en vez de
«un tercio»; y declarar que las 103 fichas de la 28 no traen direccion ni cliente.

R18. Esa ficha debe avisar de que buscar por `codigo_obra` exige filtrar
`es_ficha_principal` o fijar `empresa_id`: la identidad es (`empresa_id`,
`codigo_obra`).

R19. El sistema debe publicar la regla dura `R-OBRA-FICHA-PRINCIPAL`
(bloqueante) con ambito `maestro.obras`, `stg.obras`, `stg.v_obra_fichas`,
`personal.partes_lineas`, `retenciones.movimientos`, `maestro.centros_coste` y
las cuatro tablas de `compras` con obra, con las cifras de `design.md` §1.3.

R20. La regla `R-UNIVERSO-OBRA` y las fichas de `stg.obras` y de
`stg.v_obra_fichas` (nueva, en `stg.yaml`) deben describir la regla de D1.

R21. La ficha de `maestro.obras` debe declarar que `raw.condir` no aporta
direcciones de obra (0 de 922 fichas, tambien en Sigrid).

R22. `version` de `00_global.yaml` debe subir en uno sobre la de `main`.

## `compras` y las demas fichas que apuntan a `maestro.obras.obra_id` [D4]

R23. El sistema debe anadir `obra_principal_id`, al final, a
`compras.v_pbi_contrato_consumo`, `v_pbi_proveedor_obra`,
`v_pbi_albaranes_sin_facturar`, `v_pbi_partida_coste` y `v_control_forma_pago`,
tomada de `stg.v_obra_fichas` por `obra_id` con `LEFT JOIN` (NULL si `obra_id`
es NULL), sin cambiar su grano ni sus columnas anteriores.

R24. En `v_pbi_proveedor_obra` esa union va sobre el resultado ya agregado.

R25. La ficha de cada una de esas cinco vistas en `compras.yaml` debe documentar
`obra_principal_id` y declarar la relacion `obra_principal_id ->
maestro.obras.obra_id` (N:1) como la que usa quien agrega por obra.

R26. Las fichas de `compras.contratos`, `albaran_lineas`, `factura_lineas`,
`fact_compras_linea`, `retenciones.movimientos`, `v_pbi_retencion_obra`,
`maestro.proveedores_obra` y `maestro.centros_coste` deben decir, en `obra_id`
y en el `porque` de su relacion con `maestro.obras`, que el `obra_id` puede ser
de una ficha no principal (con su cifra medida) y como traducirlo:
`JOIN maestro.obras USING (obra_id)` -> `obra_principal_id`.

R27. [D2 A] El sistema NO debe reescribir ningun `obra_id` publicado: los SQL de
las tablas de `compras` (`01`, `02`, `05`, `07`), de `retenciones`, de
`personal` y `maestro/03_*`, `04_*` no nombran `v_obra_fichas` ni
`obra_principal_id`. `build_compras` no gana dependencia de `build_stg`.

R28. `01_obras.sql` (cabecera y `COMMENT`) sin «un tercio» ni las frases que
veta `test_f073_r11`.

## `personal.recursos`: el codigo es unico por empresa (correo de Juan, 23-09)

R29. DONDE F-101 este ya fusionado en `main` (precondicion: F-101 toca
`personal/00_setup.sql`), `personal.recursos` debe publicar al final
`empresa_id` (`con.emp`) y `nombre_empresa` (`raw.auxemp`, lateral con
`LIMIT 1`), con `ADD COLUMN IF NOT EXISTS` y sin perder filas (2.618) ni anadir
ningun `WHERE` (los vetos de `test_f057` siguen en verde).

R30. La ficha de `personal.recursos` debe declarar que la clave legible unica es
(`empresa_id`, `codigo_recurso`) —61 codigos repetidos, 0 dentro de una
empresa— y que una persona puede tener una ficha por empresa, con `MO/0009`
como ejemplo. [D5, abierta] No se publica marca de «misma persona».

## Documentacion y verificacion

R31. `docs/ARCHITECTURE.md` debe explicar que una obra y un recurso pueden estar
en varias empresas, que la principal es la de la 1, y el recuento de tablas.

R32. `azure-apps/datamart_seg_anual.md` debe recoger las columnas nuevas de
`maestro.obras`, de las vistas de `compras` y de `personal.recursos`, la regla y
0720, 0581, 0606 y 0671 en `mart`/`cierre`; commit en `azure-apps`. Sin aviso a
`facturas`, que es independiente (D4).

R33. **MANUAL (humano, tras la nocturna)**. `check-unicidad`,
`check-relaciones` y `check-declarados` sin errores nuevos atribuibles a F-102.

R34. `bash harness/init.sh` debe terminar en verde.
