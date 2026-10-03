<!-- specs/F-123-descompuestos-regla-origenes/requirements.md -->
# F-123 · Requisitos

Cambio de la regla de Estudios del esquema `descompuestos` (F-097, F-120),
decidido por el humano el 2026-10-02: «cambiar la regla de estudios cuando haya
descompuesto en el master inicial, que es casi siempre. En la fase 0 el
descompuesto es la planificación de compras». Segunda versión de la spec: la
primera (respaldo con origen propio, tabla `estudios_partida`, motivos de «no
existe») la rechazó el humano por complicada. Mediciones y las dos decisiones
abiertas (D1 → R19, D2 → R14, con su recomendación): `progress/spec_F-123.md`.

## Glosario

- **Master 0**: la versión 0 del master coste (ámbito 8, `fase_num` 0).
- **Obra con master 0**: la que tiene fila en `descompuestos._versiones_cargadas`
  con `fase_num = 0`. Esa tabla solo guarda versiones con descompuesto (medido el
  02-10: las 170 obras que la tienen publican líneas del master 0).
- **Fase viva**: coste fase 0 (ámbito 3, `fase_num` 0), el presupuesto de coste
  que el jefe de obra evoluciona día a día. Su descompuesto es `PLANIF_JO`.

## Alcance

- **R1.** Solo cambia el esquema `descompuestos`. Ningún SQL fuera de
  `sql/descompuestos/` lee sus tablas (comprobado el 02-10), así que `stg`,
  `mart` y `cierre` —medición y precio de las partidas— no cambian.
- **R2.** `ingest_descompuestos` no cambia, y ningún SQL de `sql/descompuestos/`
  hace `DELETE`, `DROP` ni `TRUNCATE` de `_des_texto` ni de `_versiones_cargadas`.
- **R3.** `PLANIF_JO`, `MASTER_PRE_ABC` y `MASTER_PLANIF_JO` no cambian: ni su
  regla, ni sus líneas, ni su cuadre, ni `v_pbi_planif_jo` ni
  `v_pbi_master_planif_jo`.

## El master 0 es Estudios

- **R4.** El sistema debe publicar las líneas y el cuadre del master 0 con
  origen `MASTER_ESTUDIO`.
- **R5.** `MASTER_INICIAL` no debe existir como valor de `origen` en
  `descompuestos.lineas` ni en `descompuestos.cuadre_partida` después del build,
  ni en `ORIGENES` del dominio, los dos `CHECK`, `elementos`, las vistas, el
  diccionario, `docs/ARCHITECTURE.md` ni la ayuda de `main.py`.
- **R6.** Los orígenes deben ser exactamente `ESTUDIO`, `PLANIF_JO`,
  `MASTER_ESTUDIO`, `MASTER_PRE_ABC` y `MASTER_PLANIF_JO`, iguales en `ORIGENES`
  del dominio y en los dos `CHECK` de origen del SQL.
- **R7.** `descompuestos.elementos` debe llamar `lineas_master_estudio` a la
  columna que hoy es `lineas_master_inicial`, en la misma posición. Las demás
  columnas, `lineas_estudio` incluida, no cambian.

## ESTUDIO solo donde no hay master 0

- **R8.** MIENTRAS una obra NO tiene master 0, el sistema debe publicar su
  origen `ESTUDIO` exactamente como hoy: la «Descomposición» de la fase viva de
  las partidas sin ningún registro enlazado a `dncpro`, mismas columnas.
- **R9.** MIENTRAS una obra tiene master 0, el sistema NO debe publicar ninguna
  línea `ESTUDIO` de esa obra, tenga o no descompuesto en el master 0 la partida.
- **R10.** El cuadre del ámbito 3 fase 0 debe tener una fila `PLANIF_JO` por
  partida hoja con precio (como hoy) y la fila `ESTUDIO` SOLO en las obras sin
  master 0, con los mismos estados que hoy, `SUSTITUIDO_POR_PLANIFICACION`
  incluido.
- **R11.** Ninguna pareja (obra, partida) debe tener a la vez líneas
  `MASTER_ESTUDIO` y `ESTUDIO`.
- **R12.** «No existe» no tiene objeto propio: si la partida no tiene
  descompuesto, el cuadre de su origen de Estudios (`MASTER_ESTUDIO` o `ESTUDIO`)
  ya dice `SIN_DESCOMPUESTO`. No se crea tabla ni estado nuevo.

## Consumo

- **R13.** `v_pbi_estudio` debe seguir publicando solo `ESTUDIO`, con las mismas
  columnas en el mismo orden.
- **R14.** El sistema debe publicar `descompuestos.v_pbi_master_estudio`, las
  líneas `MASTER_ESTUDIO` con las MISMAS columnas y orden que `v_pbi_estudio`
  (para poder unirlas: Estudios completo = las dos vistas).

## Migración de lo ya cargado

- **R15.** CUANDO `build_descompuestos` corre sobre una base con los orígenes de
  F-120, el sistema debe, sin `DROP` ni `TRUNCATE` de `lineas` ni de
  `cuadre_partida`: pasar a `MASTER_ESTUDIO` sus filas `MASTER_INICIAL` y
  sustituir los dos `CHECK` de origen, antes de cualquier `INSERT`.
- **R16.** La migración debe ser idempotente: una segunda ejecución no falla ni
  vuelve a tocar los `CHECK` si ya admiten `MASTER_ESTUDIO`.
- **R17.** El sello de troceado debe cambiar (deja de ser `7cad480aee614b2a`,
  porque el literal vive en `03_lineas_master.sql`): el retroceo no relee Sigrid
  ni toca `_des_texto`.

## Documentación

- **R18.** `version` de `config/diccionario/00_global.yaml` debe subir a 40.
- **R19.** `R-DESCOMPUESTO-ORIGEN` debe explicar la fase viva (coste fase 0, el
  presupuesto que el jefe de obra evoluciona día a día; su descompuesto es la
  planificación de compras, `PLANIF_JO`) y la regla de Estudios: el master 0
  (`MASTER_ESTUDIO`, con la medición de Estudios) en las obras que lo tienen, y
  `ESTUDIO` solo en las que no.
- **R20.** La entrada `descompuestos` de `esquemas` y las fichas de
  `descompuestos.yaml` (`lineas`, `cuadre_partida`, `elementos`, `v_pbi_estudio`
  y la nueva `v_pbi_master_estudio`) deben decir la regla nueva. El aviso de
  F-120 «ESTUDIO: precios de Estudios, medición actual» se conserva solo para
  las obras sin master 0, dicho en una frase; el ejemplo 0726 pasa a
  `MASTER_ESTUDIO`.
- **R21.** `docs/ARCHITECTURE.md`, la ayuda de `build-descompuestos` en `main.py`
  y `azure-apps/datamart_seg_anual.md` deben decir la regla nueva y la vista nueva.

## Verificación contra la base (MANUAL del humano)

- **R22.** Antes y después del despliegue debe medirse, por origen, líneas,
  obras y partidas (previsión en `progress/spec_F-123.md` §3).
- **R23.** Testigos: la 0726 (obra 2817778), partida 419079, con 10 líneas
  `MASTER_ESTUDIO` que suman 134,35 por unidad y ninguna `ESTUDIO`; la 0713 (obra
  2645007), sin `MASTER_ESTUDIO` y con sus 687 partidas (1.774 líneas) `ESTUDIO`.
- **R24.** Debe quedar medido, por `tipo_version`, en cuántas partidas CUADRA del
  master `sum(importe_total)` coincide con `stg.presupuesto.importe` de su
  versión (consulta en `progress/spec_F-123.md` §4, por `psql`).
