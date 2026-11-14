<!-- specs/F-161-versiones-sin-reparto/requirements.md -->
# F-161 · Requisitos · Versiones del máster sin reparto temporal: catálogo completo, coste por partida y planificado de importe al lado del temporal

Diagnóstico de partida: `progress/explore_0698_v24_coste.md`. Cifras medidas: `design.md` §5 y
`progress/spec_F-161.md`. La v24 de coste de la 0698 (CIERRE SEPTIEMBRE-26, 776 líneas,
2.107.662,97 €) no sale en el catálogo porque ninguna de sus líneas trae `obrparpre.planif`, y el
catálogo se deduce de `stg.plan_mensual`, que solo tiene las líneas con reparto.

**Decisiones del humano que no se discuten** (2026-11-11, `notes` de F-161 en `harness/features.json`):

- **D1.** Hay TRES referencias. (1) El VIVO, la fase 0 de coste (ya publicada, `stg.plan_mensual_fase0`,
  F-157). (2) El ÚLTIMO CIERRE, la última versión del máster de CUALQUIER tipo: es el planificado de
  IMPORTE total. (3) El ÚLTIMO PLANIFICADO TEMPORAL («valorada»), la versión que reparte en el tiempo.
- **D3.** El seguimiento enseña los dos POR SEPARADO: el mensual con el reparto de la temporal y, al
  lado, el total del último cierre y la diferencia, SIN reescalar.
- **D4** (sustituye a D2, revocada): «la parte temporal no quiero que cambie». La vigencia temporal y
  todo lo que cuelga de ella (`mart.fact_seguimiento_mensual`, `mart.master_vigente_anual`,
  `mart.fact_cp_tipologia`, `retenciones.fin_obra`, `tesoreria.devengo_*`) quedan EXACTAMENTE como hoy.
  El alcance es ADITIVO. La marca de reparto por línea y versión en `stg` se mantiene: solo informa.

Fuera: el glosario («valorada», F-054); reescalar el temporal al importe (D3); que una versión sin
reparto rija el mensual (D4); la venta con coeficientes (`R-VENTA-COEFICIENTES`: aquí `importe`);
el `.pbix` (lo decide el humano); el reparto incompleto DENTRO de una línea (su `planif` no llega al
100 %); las 6 versiones de la obra 1562946, fuera de `stg.obras` (punto 3d del diagnóstico).

## La marca de reparto, en `stg`

R1. El sistema debe publicar `stg.master_versiones` con UNA fila por (`obra_id`, `ambito_id`,
`version`) de los ámbitos 8 y 11 para toda versión >= 1 con líneas en `stg.presupuesto` y para toda
versión con filas en `stg.plan_mensual`, tenga o no cabecera en `raw.obrfasamb` (D5, D6). La clave no
se repite aunque `raw.obrfasamb` duplique la cabecera (D13). (capa: unitaria + sandbox)

R2. El sistema debe marcar cada línea master de `stg.presupuesto` (ámbitos 8 y 11, versión >= 1) con
`tiene_reparto` = TRUE si y solo si deja al menos una fila en `stg.plan_mensual`, y publicarlo en la
vista `stg.v_master_lineas` (D7, D12). (capa: sandbox)

R3. `stg.master_versiones` debe llevar `tiene_reparto` (la versión tiene filas en `stg.plan_mensual`),
`n_lineas`, `n_lineas_con_reparto`, `importe_total` (suma de `importe` de sus líneas),
`importe_con_reparto`, `importe_sin_reparto` (= total − con reparto) y `reparto`: NINGUNO si la
versión no tiene reparto; COMPLETO si lo tiene y ninguna línea con `importe` <> 0 queda sin él;
PARCIAL en el resto (D7). (capa: unitaria con oráculo + sandbox)

R4. CUANDO la versión tenga reparto, sus fechas, descripción y texto deben ser los de
`stg.plan_mensual`, como hoy. CUANDO no lo tenga, deben salir de su cabecera con las MISMAS
expresiones que `stg/08_plan_mensual.sql` (fecha efectiva con `stg.fn_master_fecha_efectiva` y el texto
de coste para la venta; descripción por defecto «Master coste/venta sin descripción»). (capa: sandbox)

R5. SI la versión no tiene cabecera, ENTONCES sus fechas y textos deben ser NULL y
`tiene_cabecera` = FALSE; `tiene_ancla` debe decir si la cabecera trae `plafec` > 0. (capa: sandbox)

R6. El sistema debe reconstruir `stg.master_versiones` ENTERA cada noche, en un sub-paso de
`build_stg` detrás de `build_plan_mensual_fase0`, fuera de `FICHEROS_DEL_SELLO` y de la ventana
(F-025); si falla, falla `build_stg`. (capa: unitaria)

## Un solo catálogo, en `mart`

R7. `mart.master_versiones_tipadas` debe construirse en `mart/01b_master_versiones.sql`, ANTES de
`02_build_fact.sql`, desde `stg.master_versiones`, con la cascada de `tipo_master` copiada literal y
las columnas de R3 y R5 al final de las ocho de hoy. (capa: unitaria)

R8. `mart.v_master_versiones_tipadas` debe proyectar las ocho columnas de hoy en el mismo orden y,
detrás, las nuevas. (capa: unitaria)

R9. Ningún otro fichero de `mart` debe repetir el catálogo ni la cascada del tipo:
`02_build_fact.sql` lee la tabla y `06_cp_tipologia.sql` deja de construirla (D11). (capa: unitaria)

R10. MIENTRAS una versión no tenga reparto, el sistema NO debe considerarla para la vigencia temporal:
`02_build_fact.sql` filtra `tiene_reparto AND version_fec_creacion IS NOT NULL AND
version_fec_efectiva IS NOT NULL`, `master_vigente_anual` y la Cuatrimestral de
`retenciones/05_fin_obra.sql` filtran `tiene_reparto` (D4). (capa: unitaria + sandbox)

R11. Las filas del catálogo con `tiene_reparto` y `version_fec_efectiva` no nula deben ser idénticas,
en las ocho columnas de hoy y en los dos sentidos (`EXCEPT`), al catálogo que da hoy el `SELECT
DISTINCT` sobre `stg.plan_mensual` de la misma noche. (capa: sandbox + manual)

## El coste por versión y partida

R12. El sistema debe publicar `mart.v_master_version_partida`: una fila por línea de
`stg.v_master_lineas` de una versión del catálogo, con `empresa_id`, `clave_obra`, ámbito, versión,
`tipo_master`, `reparto` de la versión, partida (código, descripción, categoría, ruta), cantidad,
precio, `importe` y `tiene_reparto` de la línea. No depende del reparto (D14). (capa: sandbox)

R13. CUANDO se consulte la versión 24 del ámbito 8 de la 0698, el sistema debe devolver 776 filas
que suman 2.107.662,97 €, con `reparto` = NINGUNO en el catálogo. (capa: manual)

## El planificado de importe, al lado del temporal (D1, D3)

R14. El sistema debe publicar `mart.master_importe_mensual`, una fila por (`obra_id`, `ambito_id`,
`anio_mes`), desde el mes de la primera versión con fecha hasta el mes del BUILD (D9), con:
`version_importe`, la última de cualquier tipo con `version_fec_efectiva` < mes + 1, por fecha
efectiva y versión descendentes, entre las versiones >= 1 con líneas (D8); `version_temporal`, la que
elige `02_build_fact.sql` para ese mes; el tipo y el `importe_total` de cada una, el
`importe_con_reparto` de la temporal y `diferencia_importe` = importe de la de importe − importe de
la temporal (D10). Sin reescalar. (capa: unitaria con oráculo + sandbox)

R15. SI en un mes no hay versión temporal, ENTONCES `version_temporal`, su importe y la diferencia
deben ser NULL y el importe de la de importe debe publicarse igual (la 0721). (capa: sandbox)

R16. Para todo (obra, ámbito, mes) con filas PLANIFICADO en `mart.fact_seguimiento_mensual`,
`version_master` debe ser `version_temporal` de `mart.master_importe_mensual`. (capa: sandbox + manual)

R17. «Hoy» debe ser la fecha del build, congelada como en `06_cp_tipologia.sql`. (capa: unitaria)

## Lo de hoy no cambia (D4)

R18. Con el mismo `raw`, antes y después del despliegue: `huella-obras --desde mart` sin ninguna
obra distinta; `fingerprint-views --schemas retenciones,tesoreria` idéntica; `check-cp-tipologia`
sin diferencias. (capa: manual)

R19. SI `build_stg` + `build_mart` crecen más de 5 minutos sobre la media de la última semana (medido
con `EXPLAIN (ANALYZE)` en solo lectura y en la primera nocturna), ENTONCES el implementer PARA y lo
anota. (capa: manual)

## Diccionario y documentos

R20. Fichas nuevas de los cuatro objetos; fichas de `master_versiones_tipadas` y su vista con el
grano verdadero («todas las versiones con líneas; solo las de reparto rigen»); la de `stg.plan_mensual`
corregida (hoy afirma que no hay versión 0 y la hay en 4 obras); `R-VERSION-MASTER` y P18 al día;
`version` siguiente; presupuesto de `contexto_bbdd` respetado. (capa: unitaria)

R21. `docs/ARCHITECTURE.md`, el mapa de `CLAUDE.md` y `azure-apps/datamart_seg_anual.md` (commit local
allí, sin `push`) deben nombrar los objetos nuevos. (capa: unitaria)
