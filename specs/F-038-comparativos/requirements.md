<!-- specs/F-038-comparativos/requirements.md -->
# F-038 · Requisitos · El comparativo de ofertas al completo

Mediciones y porqués: `progress/spec_F-038.md`. No se reabre lo cerrado por el
humano: las cuatro magnitudes con nombre propio y todas las ofertas.

## Decisiones (detalle y cifras en `progress/spec_F-038.md` §3 y §7)

Aprobado por el humano el 2026-10-04: **D1** dos fases (Fase 1 = R1-R24, tal
cual; Fase 2 = R25-R36) y **D3** firmas por escalón aquí, en Fase 2. **D2
cambia**: la base del objetivo es el **descompuesto** (`descompuestos.lineas`) de
la **primera ABC** del master y, si la obra no tiene ABC, el de **Estudios**
(`MASTER_ESTUDIO` o `ESTUDIO`). **D4 decidida el 2026-10-04**: la primera ABC si
casa; si no, la ANTERIOR más reciente que case; nunca una posterior; en obras
sin ABC, solo Estudios; si no casa, la de la regla marcada «no casa». Casan
24.263 de 83.329 líneas (29,1 %). Ejemplos: `progress/explore_F-038_ejemplos_objetivo.md`.

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
- R28. La ficha debe declarar que `dto` es texto con coma decimal (tratarlo como
  número revienta), que el precio ya es neto y que hay % negativos (recargos).
- R29. CUANDO una línea OBJETIVO tenga porcentaje, el sistema debe buscar su
  base en `descompuestos.lineas` de su obra (`com.obride`) y partida
  (`dncpro.paride` de su `comlin`): `base_regla` = `ABC` si la obra tiene primera
  ABC (`es_primera_abc`), si no `ESTUDIOS` (`MASTER_ESTUDIO`/`ESTUDIO`); dentro
  de la partida, el elemento es el de igual `dncpro_id` y, si no lo hay, el que
  cumpla `precio × (1 − %)` con la tolerancia del dominio.
- R30. La línea debe publicar `precio_base`, `origen_base` (origen y versión
  usados) y `casa_base`, con D4: la ABC si casa; si no, la versión anterior a la
  ABC más reciente que case; nunca una posterior; sin ABC, solo Estudios; si no
  casa, la de la regla con `casa_base` falso. Sin descompuesto: NULL.
- R31. El sistema debe publicar `compras.comparativo_objetivo`, una fila por
  comparativo con oferta OBJETIVO (`comparativo_id` PK): la oferta más reciente
  (`con.fec`, luego `ide`), su importe, su porcentaje (si es único), `base_regla`
  y el % de su importe cuyas líneas casan con la base; la ficha da las cifras de
  D4 (29,1 % casan) y dice que la tabla lee `descompuestos` de la noche anterior.
- R32. Ninguna oferta ficticia debe contar en el número de ofertantes, la
  mínima ni el ahorro (test sobre el SQL).
- R33. El sistema debe publicar `compras.comparativo_firmas`, una fila por
  `raw.confir` de un comparativo, con circuito (`cod`), escalón (`rol`),
  usuario, fecha, `pendiente` (`fir = 0`) y `firma_digital_valida` (`firok`).
- R34. La ficha debe declarar que un escalón se repite tras un rechazo
  (5.375 comparativos), que `ord` = 0 siempre, y que el circuito entre familias
  es F-085.
- R35. Cada objeto de Fase 2 debe tener ficha con grano, clave y relaciones.
- R36. Las cuatro puertas `check-*` deben pasar tras la nocturna (MANUAL).

**Fuera de alcance**: vistas por actividad y proveedor (F-067); circuito entre
familias, `deffir` y `dbo.log` (F-085); `comlinpar` (0 filas); ingesta nueva.
