<!-- specs/F-153-estado-albaranes/requirements.md -->
# F-153 · El estado de cada albarán (con proformas y notas)

Pedida por el humano el 2026-10-28: «está publicada la tabla del catálogo de
estados pero no sé el estado por albarán». Spec escrita el 2026-11-02, con
`raw` de esa noche; mediciones en `progress/spec_F-153.md`.

Rigor `estandar`. Nada de ingesta nueva. Los tests no tocan red ni BBDD; lo que
exige Azure es MANUAL (`design.md` §9).

## La cabecera: `compras.albaranes`

- **R1.** El sistema debe publicar en `compras.albaranes` `estado_id`
  (`con.est`), `estado_codigo` y `estado`, en ese orden y AL FINAL de la tabla,
  sin mover ninguna de las 46 columnas actuales.
- **R2.** El sistema debe traducir el estado con
  `compras.fn_estado_documento(14, con.est)`, por la PAREJA tipo-estado, con
  `LEFT JOIN LATERAL ... ON TRUE`, sin un catálogo escrito a mano.
- **R3.** SI `con.est` no casa con el catálogo del tipo 14, ENTONCES el sistema
  debe publicar el documento igual, con `estado_id` tal cual y `estado_codigo`
  y `estado` a NULL. El grano no cambia: una fila por fila de `raw.dca`, sin
  `WHERE` externo y sin más `JOIN` interno que `raw.con`.
- **R4.** El sistema debe indexar `compras.albaranes (estado_id)` como
  `compras.facturas` (`idx_com_alb_est`).

## La vista: `compras.v_estado_documentos`

- **R5.** El sistema debe publicar en la vista una fila por documento de
  `compras.albaranes` con el tipo 14 y el estado de la cabecera, sin cambiar las
  15 columnas, su orden ni las filas de contratos, facturas y comparativos.
- **R6.** La vista debe dar en `tipo_documento`, para el tipo 14, el mismo valor
  que `compras.albaranes.tipo_documento` (ALBARAN, PROFORMA, NOTA u OTRO): la
  familia entera se filtra por `tipo_documento_codigo = 14` (D2).
- **R7.** La vista debe decidir `origen_fecha` en este orden, y el dominio
  (`fecha_estado`) en el mismo:
  1. `PASO`: hay último paso y su destino es el estado actual;
  2. `FACTURACION`: tipo 14, estado 10 y `fecha_facturacion` informada; la fecha
     es ese día a las 00:00 (D1);
  3. `ALTA`: sin último paso y en estado inicial; para el tipo 14, el estado 1;
  4. `SIN_HISTORIAL`: tipo 14 y sin último paso; `en_estado_desde`,
     `dias_en_estado` y `cambio_posterior_a` a NULL (D3);
  5. `FUERA_DE_PROCESO`: cualquier otro caso.
- **R8.** MIENTRAS `compras.documento_procesos` no traiga el tipo 14 (F-133), el
  sistema debe publicar los albaranes sin leer `raw.rac`. CUANDO lo traiga, la
  regla de R7 debe valer sin reescribirse: los COM y CON pasarán solos a `PASO`.
- **R9.** La vista debe seguir sin leer `raw`: el estado y las fechas salen de
  `compras.albaranes`.
- **R10.** Los literales de la vista (familias, tipos del 14, estados iniciales,
  orígenes y los números 14 y 10) deben ser los del dominio
  (`domain/estado_documentos.py`), y un test debe fijar que son los mismos.

## Lo declarado en las fichas

- **R11.** La ficha de `compras.albaranes` debe describir las tres columnas y
  declarar: los cuatro estados del tipo 14, el reparto por `tipo_documento`, los
  10 fuera de catálogo (`estado_id` 0, sin literal) y la diferencia con
  `facturado_sigrid` (185 con `estfac` = 1 y estado no 10).
- **R12.** La ficha de la vista debe declarar: los cinco orígenes; que el tipo 14
  se filtra por `tipo_documento_codigo = 14`; qué parte de los albaranes tiene
  fecha (77 %) y cuál no; que COMPROBADO y CONTABILIZADO no tienen fecha hasta
  F-133 aunque el paso exista en `rac`; que FACTURADO no sale de `rac` y que su
  fecha es de día, no al segundo; y la relación con `compras.albaranes`.
- **R13.** SI una ficha afirma «contrato, factura y comparativo» como universo
  de la vista, ENTONCES debe corregirse: `compras.yaml` (cabecera y fichas),
  `00_global.yaml` y `docs/ARCHITECTURE.md`.
- **R14.** El diccionario debe subir a la versión 70 con su nota en
  `00_global.yaml`: 256 objetos (ninguno nuevo) y 2.243 columnas.
- **R15.** `azure-apps/datamart_seg_anual.md` debe recoger el cambio en el mismo
  trabajo (commit local, sin push).

## Lo que se responde

- **R16.** CUANDO se pregunte por el MCP «¿qué albaranes llevan más de 30 días
  pendientes de comprobar?», debe responderse con
  `compras.v_estado_documentos` (tipo 14, `estado_codigo = 'PDT'`,
  `dias_en_estado > 30`), sin explicarle nada al agente y avisando de los
  antiguos sin cerrar (6.612 de los 7.689 pendientes son anteriores a 2026).
- **R17.** CUANDO se pregunte «¿desde cuándo está contabilizado el albarán X?»,
  debe responderse el estado y decir que no hay fecha hasta F-133, sin
  sustituirla por `fecha_ultima_modificacion`.
- **R18.** CUANDO se pregunte por proformas pendientes, debe filtrarse
  `tipo_documento = 'PROFORMA'` en la vista o en `compras.albaranes`, con el
  mismo resultado por las dos vías.

## Coste y cierre

- **R19.** El sistema debe mantener `build_compras` dentro de su ventana: el
  sobrecoste de la cabecera (medido, ~1 s) y la consulta entera de la vista
  (medida, de 0,3 a 0,8 s, frente a los 30 s del MCP) se recalculan en MANUAL.
- **R20.** `bash harness/init.sh` debe terminar en verde y el reviewer dar
  APROBADO contra `CHECKPOINTS.md`.

## Decisiones que valida el humano (PARADA 1)

Recomendación escrita; alternativas en `design.md` §7.

- **D1 = A.** La fecha de FACTURADO sale de `dca.fecfac` (235.254 documentos).
- **D2 = A.** `tipo_documento` de la vista distingue ALBARAN, PROFORMA y NOTA.
- **D3 = A.** Origen nuevo `SIN_HISTORIAL`, en vez de reutilizar
  `FUERA_DE_PROCESO`.
- **D4 = A.** No se absorbe F-133.

## Fuera de alcance

- F-133 (`compras.documento_procesos` con el tipo 14): su familia, sus pasos y
  quién comprueba o contabiliza. **Su criterio «la vista de estados da lo mismo
  antes y después» deja de valer tras F-153**: los COM y CON pasarán a `PASO`, a
  propósito (`design.md` §8).
- F-134 (empleado y hora del albarán), F-105 (`dbo.log`, los pasos deshechos).
- Corregir en Sigrid los 10 sin estado o los 185 con `estfac` distinto.
