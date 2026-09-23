<!-- specs/F-102-obra-duplicada-empresa-28/requirements.md -->
# F-102 · Requisitos — la obra dada de alta en dos empresas: empresa y ficha principal en `maestro.obras`

Notacion EARS. Cada R se traduce a >= 1 test `test_f102_rN_...` (offline: texto
del SQL sin comentarios `--`, YAML del diccionario, `tables_sigrid.yaml`) salvo
las marcadas **MANUAL**. Rigor `estandar`. Cifras **medidas en solo lectura el
2026-09-23** sobre el `raw` de la ingesta de esa noche (00:48 UTC) con sesion
PostgreSQL `read_only`, contrastadas contra Sigrid por `sigrid-api` y contra
`mart`/`cierre` por el MCP: `design.md` §1. **[Dn]** = decision abierta del
humano (`design.md` §8); la spec se escribe con la opcion recomendada.

## Una sola definicion de "ficha principal" (`stg`)

R1. El sistema debe publicar `stg.v_obra_fichas`: una fila por ficha de obra
(`raw.obr JOIN raw.con`, 922 el 2026-09-23) con `obra_id`, `codigo_obra`,
`empresa_id` (`con.emp`), `marcada_vigente`, `num_cierres`,
`en_universo_seguimiento`, `num_fichas_codigo`, `rango_ficha`,
`es_ficha_principal` y `obra_principal_id`.

R2. [D1] El sistema debe ordenar las fichas de un mismo codigo por estos campos
y solo por estos, en este orden: (1) marcada vigente en `raw.conext` con
`cod = '15'`; (2) mas cierres en `raw.obrfas` (`num_cierres` DESC); (3) empresa 1
antes que cualquier otra; (4) `con.tiemod` DESC; (5) `ide` DESC. El quinto es
solo desempate determinista: **ninguna regla elige por `obra_id` menor**.

R3. El sistema debe marcar `es_ficha_principal = TRUE` en exactamente una ficha
por codigo (`rango_ficha = 1`): 846 principales para 846 codigos.

R4. SI una ficha tiene mas de una fila `cod = '15'` en `raw.conext`, ENTONCES el
ranking no debe multiplicarla: la marca se evalua con `EXISTS`, no con `JOIN`.

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
`stg.obras` debe seguir teniendo 584 filas y cambiar de ficha solo en `0252`
(-> 650280, empresa 12), `0517` (-> 1088657, empresa 25) y `0720` (-> 2759241,
empresa 1); las otras 581 igual.

## `maestro.obras`: empresa y ficha principal, sin perder filas

R9. El sistema debe anadir a `maestro.obras`, AL FINAL y en este orden,
`empresa_id`, `nombre_empresa`, `es_ficha_principal`, `num_fichas_codigo` y
`obra_principal_id`, conservando todas las columnas anteriores en su orden.

R10. El sistema debe seguir publicando una fila por ficha (922): la vista se une
a `stg.v_obra_fichas` con `LEFT JOIN` por `obra_id` y no filtra nada.

R11. [D3] El sistema debe resolver `nombre_empresa` desde `raw.auxemp` por
`numemp = con.emp` con `LATERAL ... ORDER BY ... LIMIT 1`, para no multiplicar
filas el dia que el catalogo repita numero.

R12. El sistema debe tomar `es_ficha_principal`, `num_fichas_codigo` y
`obra_principal_id` de `stg.v_obra_fichas`, sin recalcularlos en `maestro`.

R13. **MANUAL (lectura)**. `SELECT codigo_obra, count(*) FROM maestro.obras
WHERE es_ficha_principal GROUP BY 1 HAVING count(*) > 1` debe devolver cero
filas, y toda principal del universo debe estar en `stg.obras` y al reves.

R14. **MANUAL (lectura)**. Sobre las fichas principales de codigo de cuatro
digitos `>= '0672'` debe reproducirse la cifra de Juan Romero: 57 de la empresa 1
y 48 con `dir1` (hoy, sin la marca, la copia de la 28 de la 0720 cuenta sin ella).

## Ingesta del nombre de la empresa [D3]

R15. El sistema debe declarar `auxemp` en `config/tables_sigrid.yaml` (catalogo
de empresas de Sigrid, 38 filas el 2026-09-23, refresco completo) y subir
`TOTAL_TABLAS` en uno en los tests que lo fijan.

R16. El sistema debe tener ficha de `raw.auxemp` en `config/diccionario/raw.yaml`
diciendo que `numemp` es lo que guarda `con.emp`.

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
`personal.partes_lineas`, `compras.fact_compras_linea`, `retenciones.movimientos`
y `maestro.centros_coste`, con las cifras medidas de §1.4 del diseno.

R20. La regla `R-UNIVERSO-OBRA` debe describir el ranking nuevo y remitir a
`stg.v_obra_fichas`; las fichas de `stg.obras` y `stg.v_obra_fichas` (esta
nueva, en `stg.yaml`) deben decir lo mismo.

R21. El sistema debe declarar en la ficha de `maestro.obras` que
`raw.condir` no aporta direcciones de obra (0 de 922 fichas, medido tambien en
Sigrid), para que nadie vuelva a buscarlas alli.

R22. `version` de `00_global.yaml` debe subir en uno sobre la de `main`.

## Lo que NO se hace [D2]

R23. El sistema NO debe reescribir el `obra_id` publicado por `personal`,
`compras`, `retenciones` ni `maestro.centros_coste`: sus SQL no nombran
`v_obra_fichas` ni `obra_principal_id`. La traduccion se hace al leer, uniendo
con `maestro.obras`.

R24. El `COMMENT ON VIEW maestro.obras` y la cabecera de `01_obras.sql` deben
dejar de afirmar "un tercio" y seguir sin contener las frases vetadas por
`test_f073_r11`.

## Documentacion y ecosistema

R25. `docs/ARCHITECTURE.md` debe explicar que una obra puede estar dada de alta
en varias empresas de Sigrid y actualizar el recuento de tablas ingeridas.

R26. `azure-apps/datamart_seg_anual.md` debe recoger las columnas nuevas de
`maestro.obras`, la regla de la ficha principal y el cambio de ficha de 0252,
0517 y 0720 en el seguimiento, con commit en el repositorio `azure-apps`.

R27. El informe `progress/impl_F-102.md` debe llevar el aviso al proyecto
`facturas` (su F-036) listo para pegar; su repositorio no se toca [D4].

## Verificacion

R28. **MANUAL (humano, tras la nocturna)**. `check-unicidad`,
`check-relaciones` y `check-declarados` sin errores nuevos atribuibles a F-102.

R29. `bash harness/init.sh` debe terminar en verde.
