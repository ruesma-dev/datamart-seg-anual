<!-- specs/F-102-obra-duplicada-empresa-28/requirements.md -->
# F-102 · Requisitos — la obra dada de alta en dos empresas: empresa y ficha principal en `maestro.obras`

Notacion EARS. Cada R se traduce a >= 1 test `test_f102_rN_...` (offline: texto
del SQL sin comentarios `--`, YAML del diccionario, `tables_sigrid.yaml`) salvo
las marcadas **MANUAL**. Rigor `estandar`. Cifras **medidas en solo lectura el
2026-09-23** sobre el `raw` de la ingesta de esa noche (00:48 UTC) con sesion
PostgreSQL `read_only`, contrastadas contra Sigrid por `sigrid-api` y contra
`mart`/`cierre` por el MCP: `design.md` §1. **[Dn]** = decision del humano del
2026-09-23 (`design.md` §8).

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

R3. El sistema debe marcar `es_ficha_principal = TRUE` en exactamente una ficha
por codigo (`rango_ficha = 1`): 846 principales para 846 codigos.

R4. SI una ficha tiene varias filas `cod = '15'` en `raw.conext`, ENTONCES no
debe multiplicarse: la marca se evalua con `EXISTS`, no con `JOIN`.

R5. El sistema debe calcular `en_universo_seguimiento` con los filtros de hoy de
`stg/03_obras.sql` sin cambiar ninguno (lista cerrada de administrativos, cinco o
mas digitos seguidos, codigo nulo o vacio), escritos en un unico sitio.

R6. El sistema debe publicar `obra_principal_id` = `obra_id` de la principal de
su codigo MIENTRAS la ficha este en el universo del seguimiento, y su propio
`obra_id` fuera de el (alli las empresas reutilizan codigos para obras
distintas: 0001-0005, CM, CP, GG, POSTV2, VAR).

R7. El sistema debe construir `stg.obras` leyendo `stg.v_obra_fichas` con
`en_universo_seguimiento AND es_ficha_principal`: ni el ranking ni los filtros
se escriben dos veces. Columnas y grano de `stg.obras` no cambian.

R8. **MANUAL (lectura)**. CUANDO se evalue la vista contra el `raw` actual,
`stg.obras` debe seguir teniendo 584 filas y cambiar de ficha solo en `0720`
(-> 2759241), `0581` (-> 1287408), `0606` (-> 1562946) y `0671` (-> 2154295),
las cuatro a la empresa 1; las otras 580 igual. Riesgo: `design.md` §1.2.

## `maestro.obras`: empresa y ficha principal, sin perder filas

R9. El sistema debe anadir a `maestro.obras`, AL FINAL y en este orden,
`empresa_id`, `nombre_empresa`, `es_ficha_principal`, `num_fichas_codigo` y
`obra_principal_id`, conservando todas las columnas anteriores en su orden.

R10. El sistema debe seguir publicando una fila por ficha (922), uniendo
`stg.v_obra_fichas` con `LEFT JOIN` por `obra_id` y sin filtrar nada.

R11. [D3] `nombre_empresa` debe salir de `raw.auxemp` por `numemp = con.emp`
con `LATERAL ... ORDER BY ... LIMIT 1`, para no multiplicar filas.

R12. Las tres marcas deben salir de `stg.v_obra_fichas`, sin recalcularse.

R13. **MANUAL (lectura)**. `SELECT codigo_obra, count(*) FROM maestro.obras
WHERE es_ficha_principal GROUP BY 1 HAVING count(*) > 1` debe devolver cero
filas, y toda principal del universo debe estar en `stg.obras` y al reves.

R14. **MANUAL (lectura)**. Sobre las fichas principales de codigo de cuatro
digitos `>= '0672'` debe reproducirse la cifra de Juan Romero: 57 de la empresa 1
y 48 con `dir1`.

## Ingesta del nombre de la empresa [D3]

R15. El sistema debe declarar `auxemp` en `config/tables_sigrid.yaml` (38 filas
el 2026-09-23, refresco completo) y subir `TOTAL_TABLAS` en uno.

R16. `raw.yaml` debe tener ficha de `auxemp`: `numemp` es lo que guarda `con.emp`.

## Diccionario

R17. La ficha de `maestro.obras` debe documentar las cinco columnas nuevas y
dejar de decir que la direccion esta en "un tercio de las obras": la cobertura
se da sobre las fichas principales, por tramo de codigo y con fecha, y declara
que las 103 fichas de la empresa 28 no traen ni direccion ni cliente.

R18. La ficha de `maestro.obras` debe avisar de que una busqueda por
`codigo_obra` filtra `es_ficha_principal` o fija `empresa_id`, y de que la
identidad de una obra es el par (`empresa_id`, `codigo_obra`).

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

R24. En `v_pbi_proveedor_obra` la union a `stg.v_obra_fichas` debe hacerse sobre
el resultado ya agregado, no dentro del `GROUP BY` sobre `fact_compras_linea`.

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

R28. El `COMMENT ON VIEW maestro.obras` y la cabecera de `01_obras.sql` deben
dejar de afirmar "un tercio" y seguir sin las frases vetadas por `test_f073_r11`.

## Documentacion y verificacion

R29. `docs/ARCHITECTURE.md` debe explicar que una obra puede estar dada de alta
en varias empresas y que la principal es la de la empresa 1, y actualizar el
recuento de tablas ingeridas.

R30. `azure-apps/datamart_seg_anual.md` debe recoger las columnas nuevas de
`maestro.obras` y de las vistas de `compras`, la regla y el cambio de 0720,
0581, 0606 y 0671 en `mart`/`cierre`, con commit en `azure-apps`. No hay aviso
al proyecto `facturas`, que es independiente (D4).

R31. **MANUAL (humano, tras la nocturna)**. `check-unicidad`,
`check-relaciones` y `check-declarados` sin errores nuevos atribuibles a F-102.

R32. `bash harness/init.sh` debe terminar en verde.
