<!-- specs/F-110-fin-obra-cuatrimestral/requirements.md -->
# F-110 · Requisitos — fin de obra por el ultimo cuatrimestral + 1 mes (sustituye al ultimo cierre + 1)

Notacion EARS. Cada R se traduce a >= 1 test `test_f110_rN_...`. Rigor `critico`.
Cifras **medidas en solo lectura el 2026-09-25** (MCP y una conexion Python
`READ ONLY`): `design.md` §Medidas; consultas en `progress/spec_F-110.md`.

**Cambia la decision H1 de F-095** (2026-09-22). **[H]** = decision del humano
del 2026-09-25, cerrada: el fin de obra es (1) el inicio del periodo de garantia;
(2) si no lo hay, el ultimo mes planificado de la ULTIMA version cuatrimestral de
la obra + 1 mes; (3) si tampoco, SIN FECHA. **El respaldo «ultimo cierre con
movimiento + 1 mes» deja de intervenir**. Plazo y vencimiento no cambian.
**APROBADA por el humano el 2026-09-25** con D1 (A), D2 (A, con su ejemplo), D3,
D4 (A), D5 = `ultimo_cierre` SE QUEDA como informativa, y D6 aceptada
(`design.md` §Decisiones del humano).

Sustituye a R19 (solo el respaldo) y R21 de F-095, y R18 de F-095 pasa a
informativa. R17, R20, R22, R23, R24 y R25 de F-095 siguen en vigor.

## La version cuatrimestral

R1. **[D1]** El sistema debe tomar como version cuatrimestral de una obra la de
MAYOR `version` entre las filas de `mart.master_versiones_tipadas` con ese
`obra_id` y `tipo_master = 'Cuatrimestral'`, en cualquiera de los dos ambitos
master (8 y 11). Medido: en las 117 obras que tienen alguna, la de mayor numero
es tambien la de mayor `version_fec_efectiva` y la de mayor `version_fec_creacion`.

R2. El sistema no debe reclasificar versiones por su cuenta: `05_fin_obra.sql`
no repite el `CASE` de `tipo_master`, no lee `version_tex` y no usa
`stg.version_master_vigente` (la marca de Sigrid no es la ultima cuatrimestral en
10 de las 117 obras: `design.md` §Medidas).

R3. El sistema debe emparejar version, plan y obra **solo por `obra_id`**, la
ficha de SU empresa (`R-CODIGO-POR-EMPRESA`): nunca por `codigo_obra` ni por
`clave_obra`, y sin pasar por `maestro.obras.obra_principal_id`. Medido: la ficha
de la UTE `31-0606` tiene sus propias 10 cuatrimestrales y la de Ruesma `1-0606` 2.

R4. El sistema debe publicar en `retenciones.fin_obra` la columna
`version_cuatrimestral` (INT): el numero de R1, o NULL si la obra no tiene
ninguna cuatrimestral.

## El ultimo mes planificado

R5. **[D2]** El sistema debe publicar `ultimo_mes_planificado` (DATE, dia 1) =
el ultimo mes del cuatrimestral con importe planificado: el mayor `anio_mes` de
`stg.plan_mensual` con el `obra_id` de la obra, `version =
version_cuatrimestral`, `ambito_id IN (8, 11)` e `importe_mes <> 0`, de coste o
de venta. Ejemplo del humano, literal: «el cuatrimestral de junio 26 puede tener
planificada la obra hasta marzo 28; entonces el dia a partir del que contar las
retenciones seria el 30 de abril» (`ultimo_mes_planificado` 2028-03-01,
`fecha_fin_obra` 2028-04-30).

R6. SI la version cuatrimestral no tiene ningun mes con `importe_mes <> 0`,
ENTONCES `ultimo_mes_planificado` queda NULL y la obra no toma fecha por esta via
(medido: 0 de 117 obras; el requisito cubre el caso, no lo inventa).

R7. El sistema no debe contar como planificados los meses finales a cero: la
cola que Sigrid arrastra con el porcentaje congelado (`importe_mes = 0`) no es
plan. Medido: 15 de 117 obras tienen cola; en las 7 que toman fecha por
cuatrimestral con retencion viva, el fin queda 1 a 5 meses antes que con la
ultima fila (`design.md` §Medidas).

## El fin de obra **[H]**

R8. **[D3]** El sistema debe calcular `fecha_fin_obra` = `fecha_inicio_garantia`
(regla de F-095, sin cambio); si es NULL, el **ultimo dia del mes siguiente** a
`ultimo_mes_planificado`; si tambien es NULL, NULL.

R9. El sistema debe publicar `fuente_fin_obra` = `INICIO_GARANTIA`,
`ULTIMO_CUATRIMESTRAL_MAS_1_MES` o NULL, en ese orden de precedencia y sin mas
valores. `ULTIMO_CIERRE_MAS_1_MES` deja de existir.

R10. **[D5]** El sistema debe seguir publicando `ultimo_cierre` con la regla de
F-095 (mayor `anio_mes` de `cierre.fact_cierre_mensual` con `ejecutado_mes <>
0`) como dato **INFORMATIVO**: no debe intervenir en `fecha_fin_obra`,
`fuente_fin_obra` ni `fecha_vencimiento`. De `cierre` solo se lee esa tabla.

R11. SI una obra no tiene ni inicio de garantia ni `ultimo_mes_planificado`,
ENTONCES `fecha_fin_obra` y `fecha_vencimiento` quedan NULL y no se inventan,
aunque tenga `ultimo_cierre`; `terminada_sin_fin_obra` sigue marcando las de
`con.est` 19, 21, 23 y 25.

R12. El sistema no debe usar en el fin de obra `ultimo_cierre`,
`fecha_fin_real`, `fecha_recepcion_provisional` ni `fecha_fin_prevista`, que
son informativas.

R13. El sistema no debe cambiar el plazo ni el vencimiento: `plazo_meses`,
`fuente_plazo`, la constante 12 y `fecha_vencimiento = fecha_fin_obra +
plazo_meses` quedan textualmente como en F-095, y la fecha de la factura sigue
sin intervenir.

## La guarda y la dependencia del paso

R14. SI al construir `fin_obra` no existe `mart.master_versiones_tipadas`, o no
tiene ninguna fila `Cuatrimestral`, o `stg.plan_mensual` no tiene ninguna fila de
los ambitos 8 u 11, o no existe `cierre.fact_cierre_mensual`, ENTONCES el
sub-paso debe fallar con un mensaje que empiece por `fin_obra:` ANTES de dropear
la tabla publicada. Una `cierre.fact_cierre_mensual` VACIA ya no hace fallar el
paso (sustituye a R21 de F-095): solo deja `ultimo_cierre` a NULL.

R15. **[D4]** `BuildRetencionesStep.depends_on` debe seguir siendo
`["ingest_raw"]`: un fallo de `build_stg`, `build_mart` o `build_cierre` no deja
la noche sin retenciones; `fin_obra` usa entonces las tablas de la noche
anterior, que no se borran.

R16. El orden topologico de `main.build_pipeline_steps` debe ejecutar
`build_stg` y `build_mart` ANTES de `build_retenciones`, y un test debe
comprobarlo sobre `Orchestrator(...)._topological_sort()` de la composicion real.

R17. `SUB_PASOS`, `name` y `stage` de `build_retenciones` no cambian; el
docstring del step y el comentario de `depends_on` citan las tres lecturas
(`mart.master_versiones_tipadas` y `stg.plan_mensual` de la misma noche para el
fin de obra; `cierre.fact_cierre_mensual` de la anterior, solo informativa).

## La vista y el diccionario

R18. `retenciones.v_retencion_contable_obra` no cambia de SQL; su comentario de
cabecera y su ficha dicen que `SIN_FIN_OBRA` es «ni inicio de garantia ni
cuatrimestral con plan», y su `fuente_fin_obra` publica los valores de R9.

R19. La ficha de `retenciones.fin_obra` en `config/diccionario/retenciones.yaml`
debe explicar la regla de R8 con el ejemplo de R5 y la decision del humano del
2026-09-25, publicar las dos columnas nuevas, decir que `ultimo_cierre` es solo
informativa, y traer las cifras antes y despues por fuente (las de F-095 quedan
como historicas y con fecha).

R20. `config/diccionario/00_global.yaml` debe subir `version` en uno con su
linea de historia; `check-declarados`, `check-unicidad` y `check-relaciones`
cubren `fin_obra` sin tocar su codigo.

## Pruebas y propagacion

R21. Los tests de F-095 que fijan la regla vieja se **reescriben** a la regla
nueva citando F-110 en su docstring, no se borran sin sustituto (lista en
`tasks.md` T3); el resto de la suite de F-095 debe seguir en verde sin tocarla.

R22. Los tests deben correr sin red ni BBDD (texto del SQL, YAML y cableado del
step); las cifras de §Medidas son verificacion MANUAL tras el build.

R23. `docs/ARCHITECTURE.md` (parrafo de la retencion) y
`azure-apps/datamart_seg_anual.md` (dependencias de `retenciones.fin_obra`)
deben recoger la regla y las lecturas nuevas en el mismo trabajo.
