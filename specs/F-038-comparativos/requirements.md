<!-- specs/F-038-comparativos/requirements.md -->
# F-038 · Requisitos · El comparativo de ofertas al completo

Mediciones y porqués: `progress/spec_F-038.md` (2026-10-04), sobre
`progress/explore_F-038_comparativos.md` y `progress/explore_coste_objetivo.md`.
Esta spec **no vuelve a abrir** lo cerrado por el humano: las cuatro magnitudes
con nombre propio, todas las ofertas con las ficticias marcadas y la regla «el
objetivo sobre el ABC; si no hay ABC, sobre Oficina Técnica».

## Decisiones que pide al humano (detalle en `progress/spec_F-038.md` §7)

- **D1 · Fases.** Recomendado: **dos**. Fase 1 = R1-R24 (comparativo, ofertas,
  importes, ahorro, contrato, aprobación). Fase 2 = R25-R36 (objetivo, líneas de
  los dos lados, firmas por escalón). Alternativa: todo en una entrega.
- **D2 · Qué cuenta como «ABC».** Recomendado: las cuatro familias de
  planificación (ABC, PLANIFICACION, CUATRIMESTRAL, FASE_0). Solo afecta a Fase 2.
- **D3 · Firmas por escalón.** Recomendado: aquí, en Fase 2 (R33-R34). Si van a
  F-085, R33-R34 salen de esta spec y el acceptance 5 se reparte.

## Fase 1 · El comparativo y sus ofertas

- R1. El sistema debe publicar `compras.comparativos` con una fila por
  comparativo de `raw.com` y `comparativo_id` (`com.ide`) como clave primaria.
- R2. El sistema debe publicar `compras.comparativo_ofertas` con una fila por
  oferta invitada (`raw.comprv`, cuyo `docide` es único) y `oferta_id`
  (`dco.ide`) como clave primaria, **incluidas las ficticias**.
- R3. El sistema debe tomar el proveedor de la oferta de `dco.entide` (código
  `entcod`, nombre `entres`, CIF `entcif`); SI el SQL de F-038 lee
  `comprv.prvide`, ENTONCES un test debe fallar.

- R4. El sistema debe publicar el estado del comparativo leyendo `con.est` y
  traduciéndolo con `compras.fn_estado_documento(46, …)`, y el de la oferta con
  `compras.fn_estado_documento(12, …)`; ninguna traducción une solo por estado.
- R5. El sistema debe publicar `fecha_alta` del comparativo desde `con.fec` y
  NO debe publicar ninguna de las siete fechas de `com` ni `ppoide`, `prmide`,
  `pexide`, `tipsub`, `horlim`.
- R6. El sistema debe publicar la actividad (`com.natide` → `raw.auxpronat`)
  con su identificador y su nombre.
- R7. El sistema debe publicar la obra (`com.obride`) con `empresa_id` y
  `clave_obra` de `maestro.v_obra_fichas`, como las demás vistas de `compras`.

- R8. El sistema debe marcar una oferta como ficticia CUANDO su CIF sea
  `A99999999` o `A00000000`, o CUANDO su CIF esté vacío y su nombre normalizado
  case una familia; con CIF real nunca es ficticia.
- R9. El sistema debe asignar `familia_ficticia` por el nombre normalizado
  (mayúsculas, sin tildes ni signos) en este orden: OBJETIVO, OFICINA_TECNICA,
  CUATRIMESTRAL, FASE_0, ABC, PLANIFICACION; con CIF falso y nombre no
  reconocible, `A99999999` → OBJETIVO y `A00000000` → OFICINA_TECNICA.
- R10. SI el nombre está en la lista de exclusiones (hoy «PLANIFICACION DE
  ESPACIOS»), ENTONCES la oferta es real.
- R11. La regla de R8-R10 debe vivir escrita una sola vez en
  `etl_sigrid/domain/comparativos.py`, probada con los nombres medidos, y el SQL
  debe usar exactamente esos literales (test que lo compruebe).

- R12. La oferta debe publicar `importe_ofertado_documento` (`dco.totbas`, base
  sin IVA) e `importe_ofertado_lineas` (`Σ dcopro.tot` de sus líneas con
  `comlinide > 0`); NO debe leer `dco.totdoc`.
- R13. El comparativo debe publicar, de su oferta ganadora,
  `importe_ofertado_documento_ganadora` e `importe_ofertado_lineas_ganadora`;
  además `importe_adjudicado_lineas` (`Σ comlin.can × comlin.pre`) e
  `importe_contratado` (`Σ compras.contrato_lineas.importe` de su contrato).
- R14. Ninguna columna de los objetos de F-038 debe llamarse `importe` a secas
  (test sobre el SQL y sobre la ficha).
- R15. La ganadora es la oferta con `con.est = 6` (tip 12). MIENTRAS un
  comparativo tenga más de una, el sistema debe publicar `n_ofertas_ganadoras`
  y dejar a NULL la ganadora y sus importes, en vez de elegir una.
- R16. El sistema debe marcar `adjudicado_atipico` CUANDO el adjudicado supere
  10 veces la mayor oferta del comparativo y 100.000 €, y dejarlo a NULL SI no
  hay oferta con importe > 0 con que compararlo; el importe se publica igual.
  Umbrales escritos una vez en el dominio, con test.
- R17. La ficha debe declarar que `importe_contratado` es del CONTRATO y se
  repite en los comparativos que comparten contrato (3.960 contratos): no se
  suma entre comparativos salvo por `contrato_id` distinto.

- R18. El comparativo debe publicar `n_ofertas`, `n_ofertas_reales` y
  `n_ofertas_reales_con_importe` (reales con documento > 0).
- R19. CUANDO un comparativo tenga al menos dos ofertas reales con importe, el
  sistema debe publicar `oferta_real_minima`, `oferta_real_maxima` y
  `ahorro_concurso` (máxima − mínima, sobre el importe documento); en otro caso,
  las tres a NULL. Las ficticias nunca entran.

- R20. El comparativo debe publicar `contrato_id`, `codigo_contrato` y
  `fecha_contrato` desde `comlin.ctride` (un único contrato por comparativo,
  medido); NO debe usar `ctr.comide` para este enlace.
- R21. SI un comparativo trajera dos `ctride` distintos, ENTONCES el build debe
  fallar con mensaje claro (hoy 0): una guarda, no un `MIN` silencioso.
- R22. `compras.contratos` no cambia de columnas; la ficha de su
  `comparativo_id` debe decir que es `ctr.comide` (56 %) y remitir a
  `compras.comparativos.contrato_id` para «¿acabó en contrato?».

- R23. El comparativo debe publicar `n_firmas`, `n_firmas_pendientes`
  (`confir.fir = 0`), `fecha_aprobacion` y `aprobado_por` (usuario de la firma
  con mayor fecha y hora); `fecha_aprobacion` solo CUANDO `con.est` sea un
  `estfin` de sus firmas, y NULL en otro caso.

- R24. Cada objeto nuevo debe tener ficha en `config/diccionario/compras.yaml`
  con grano, clave, relaciones y: las cuatro magnitudes con su cuadre medido
  (A=B 99,6 %, A=C 89,8 %, A=D 41 %), el saneado del adjudicado (52, 602,5 M€),
  el criterio de ficticia, la fecha de aprobación que no existe fuera de los
  estados de firma, las siete fechas y cinco campos de `com` vacíos en origen,
  y las dos trampas de `dbo.log` (`log.ide` no es el documento; `log.res` no
  es la actividad). `version` sube y P5 de `00_global.yaml` pasa a respondible,
  con preguntas de aceptación nuevas para las cuatro del acceptance 13.

## Fase 2 · Objetivo, líneas de los dos lados y firmas

- R25. El sistema debe publicar `compras.comparativo_lineas`, una fila por
  `raw.comlin` (`linea_id` PK), con cantidad, precio, `importe_adjudicado`,
  contrato y la partida de su necesidad (`dncpro.paride`).
- R26. El sistema debe publicar `compras.comparativo_oferta_lineas`, una fila
  por línea de oferta de `raw.dcopro` con `comlinide > 0` de una oferta de R2
  (`linea_oferta_id` PK), con cantidad, precio, `importe_ofertado_linea`,
  `descuento_texto` (literal) y `porcentaje_descuento`.
- R27. `porcentaje_descuento` debe salir de UNA función SQL cuyo patrón
  (`^-?[0-9]+(,[0-9]+)?%$`) vive en el dominio con su oráculo y tests; SI el
  texto no casa, ENTONCES NULL, nunca un error ni un cero.
- R28. La ficha debe declarar que `dto` es texto con coma decimal y que tratarlo
  como número revienta; que el precio ya es neto (`tot = can × pre`); y que hay
  descuentos negativos (recargos).
- R29. CUANDO una línea OBJETIVO tenga porcentaje, el sistema debe publicar
  `familia_base` = familia de la oferta ficticia que, en el mismo `comlinide`,
  da su precio con `pre × (1 − %)` (tolerancia del dominio); si casan una de
  planificación (D2) y OFICINA_TECNICA, gana la de planificación; si no casa
  ninguna, NULL.
- R30. El sistema debe publicar `compras.comparativo_objetivo`, una fila por
  comparativo con oferta OBJETIVO (`comparativo_id` PK), con
  `oferta_objetivo_id`, `importe_objetivo` y `porcentaje_objetivo` de la más
  reciente (`con.fec`, luego `ide`); el porcentaje solo si es único en ella.
- R31. Esa fila debe publicar `base_objetivo` (`ABC` u `OFICINA_TECNICA` según
  D2) y `base_objetivo_familia` (la observada mayoritaria por importe); NULL si
  no se puede reconstruir, y la ficha dice por qué (12,6 % de líneas).
- R32. Ninguna oferta ficticia debe contar en el número de ofertantes, la
  mínima ni el ahorro (test sobre el SQL).
- R33. (D3) El sistema debe publicar `compras.comparativo_firmas`, una fila por
  `raw.confir` de un comparativo, con circuito (`cod`), escalón (`rol`),
  usuario, fecha, `pendiente` (`fir = 0`) y `firma_digital_valida` (`firok`).
- R34. (D3) La ficha debe declarar que un escalón se repite tras un rechazo
  (5.375 comparativos), que `ord` = 0 siempre, y que el circuito entre familias
  es F-085.
- R35. Cada objeto de Fase 2 debe tener ficha con grano, clave y relaciones.
- R36. `check-unicidad`, `check-relaciones`, `check-declarados` y
  `check-diccionario` deben pasar contra la base tras la nocturna (MANUAL).

## Fuera de alcance

Vistas por actividad y por proveedor adjudicatario (F-067). Circuito de firma
entre familias, `deffir`, `puntot`/`pun`/`totimp` y `dbo.log` (F-085). El
«planificado» de Aguado por presupuesto de partida (no sumable, medido).
`comlinpar` (0 filas). Nada de ingesta: todo está en `raw`.
