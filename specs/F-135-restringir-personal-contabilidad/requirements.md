<!-- specs/F-135-restringir-personal-contabilidad/requirements.md -->
# F-135 · La información de personal de la contabilidad, solo para el rol autorizado

Mediciones: `progress/spec_F-135.md`. Origen: correo de Juan Romero del 2026-10-09
(ficha). Su criterio: «si se cuela algo, restringe DE MÁS y lo afinamos». Decisiones
D1-D12 en `design.md` §8: **los requisitos siguen la opción recomendada**.

Vocabulario:
- **CR**, cuenta restringida entera: código que empieza por `640 641 642 643 644 645
  649 465 466 476 460 461 544 4753` (D1).
- **AP**, asiento de personal: asiento cuyos apuntes son TODOS de clase `NORMAL` y que
  tiene algún apunte en CR o algún concepto que casa `\mn[oóÓ]minas?\M` (D1).
- **Apunte restringido**: apunte de un AP, o de una cuenta CR en cualquier clase.
  Medido: 55.504 apuntes (2,55 % del mayor), 8.791 asientos, 25 empresas.
- **Rol general**: `mcp_sigrid_dm_ro`, el que usan el MCP y Power BI.
- **Rol autorizado**: `sigrid_dm_restringido_ro`, grupo `NOLOGIN` nuevo (D7, D8).
- **Esquema restringido**: `contabilidad_restringida` (D7).

## El criterio (dominio puro)

R1. El sistema debe decidir si un código de cuenta es CR con una única función de
dominio, que acepta prefijos de 3 y de 4 dígitos (`4753` sí, `4751` y `4750` no).

R2. El sistema debe decidir si un asiento es AP a partir de sus apuntes (código de
cuenta, clase, concepto), y debe devolver «no» si ALGÚN apunte del asiento no es de
clase `NORMAL` (regularización, cierre, apertura, saldo inicial): medido, 243 asientos
de esas clases llevan cuentas 640-476 y arrastrarían todo el grupo 6 y 7.

R3. El patrón de concepto debe casar «nómina», «nomina», «NÓMINAS» y no debe casar
palabras que la contienen, como «denominación».

R4. El SQL del esquema restringido debe usar los MISMOS prefijos y el MISMO patrón que
el dominio: un test compara los literales del SQL con las constantes del dominio.

## La contabilidad completa, en el esquema restringido

R5. El sistema debe publicar `contabilidad_restringida.plan_cuentas`, `.mayor` y
`.saldos_cuenta_mes` con las filas, columnas y semántica que tienen hoy las tablas
homónimas de `contabilidad` (F-056), más en `mayor` las columnas `restringido` (bool),
`motivo_restriccion` (`CUENTA`, `ASIENTO_PERSONAL` o NULL) y `saldo_acumulado_visible`.

R6. `contabilidad_restringida.mayor` debe tener exactamente las filas de `raw.apu`; SI
no, ENTONCES el build debe fallar con las dos cifras (la guarda R14 de F-056, que se
traslada aquí).

R7. `motivo_restriccion` debe ser `CUENTA` cuando la cuenta es CR (aunque el asiento sea
también AP) y `ASIENTO_PERSONAL` cuando solo el asiento es AP.

## La contabilidad general, filtrada

R8. `contabilidad.mayor` debe contener los apuntes de `contabilidad_restringida.mayor`
con `restringido = false`, y ninguno más, con sus columnas de hoy en el mismo orden.

R9. En `contabilidad.mayor`, `saldo_acumulado` debe ser la suma de `importe_saldo` de
los apuntes VISIBLES de la cuenta hasta el apunte inclusive (no el acumulado del mayor
completo, que delataría lo restringido en 71 prefijos de cuentas mixtas).

R10. SI `contabilidad.mayor` contiene algún apunte de cuenta CR, o el número de sus
filas más el de restringidos difiere del mayor completo, ENTONCES el build debe fallar
y dejar intacta la tabla de la noche anterior.

R11. `contabilidad.saldos_cuenta_mes` debe calcularse solo sobre apuntes visibles,
debe omitir las filas (cuenta, empresa, ejercicio, mes) sin ningún apunte visible y
debe añadir `num_apuntes_restringidos` e `incompleto` (= `num_apuntes_restringidos >
0`). Medido: 6.063 filas parciales llevarían `incompleto = true` (D5: solo recuentos).

R12. `contabilidad.plan_cuentas` debe conservar todos los nodos y añadir `restringida`
(cuenta de nivel 5 con código CR); en esas 521 cuentas `nombre_cuenta` debe valer
`'(cuenta restringida)'` (D6).

R13. El sistema debe publicar `contabilidad.apuntes_restringidos_mes` (empresa,
ejercicio, mes, `num_apuntes`, `num_asientos`), sin importes, para que quien lea un
saldo sepa cuánto queda fuera (D5).

R14. Las tablas generales deben seguir materializadas, con los índices de hoy: el MCP
consulta con 30 s de ventana (motivo de F-056 para no usar vistas).

## Los permisos, cada noche

R15. `apply_grants` debe conceder al rol autorizado `USAGE` y `SELECT` sobre el esquema
restringido y su privilegio por defecto; SI el rol no existe, ENTONCES debe avisar en
el log y seguir (su ausencia no expone nada).

R16. CUANDO corre `apply_grants`, el sistema debe emitir para cada esquema VETADO
(`PG_VETOED_SCHEMAS`, por defecto `contabilidad_restringida,raw`, D3) `REVOKE USAGE`,
`REVOKE ALL ON ALL TABLES` y `ALTER DEFAULT PRIVILEGES ... REVOKE` contra el rol
general, después de todos los GRANT.

R17. SI la lista de esquemas de consumo comparte algún esquema con la de vetados (por
ejemplo un `.env` viejo que aún lista `raw`), ENTONCES `apply_grants` debe terminar en
FAILED sin ejecutar ninguna sentencia y nombrar el esquema.

R18. CUANDO `apply_grants` ha ejecutado sus sentencias, el sistema debe comprobar con
`has_schema_privilege` y `has_table_privilege` que el rol general no lee ningún esquema
vetado ni tabla excluida; SI lee alguno, ENTONCES el paso debe terminar en FAILED con
la lista (también ante concesiones hechas por otro concedente, que la nocturna no puede
revocar: la lección de F-068).

R19. `raw` debe salir de `DEFAULT_CONSUMPTION_SCHEMAS` (D3). `PG_EXCLUDED_TABLES` se
conserva tal cual (F-068 sigue valiendo el día que `raw` vuelva).

R20. `infra/sql/02_roles.sql` debe crear el rol autorizado (`NOLOGIN`) y el esquema
restringido, no conceder `raw` ni el esquema restringido al rol general, y revocarlos
como administrador Y como `sigrid_dm_etl` en una sola transacción; un test comprueba
que sus listas coinciden con las de `config/settings.py`.

## Derivados, F-127 y documentación

R21. `retenciones` no cambia (D4): sus 8 apuntes de AP son de cuentas de retención de
proveedor (`prv.cueretide`), ninguna CR ni con concepto de nómina. La excepción queda
escrita en su ficha y en la regla global.

R22. El diccionario debe llevar ficha de los objetos de `contabilidad_restringida`, las
columnas nuevas de `contabilidad` y una regla `R-CONTABILIDAD-RESTRINGIDA` en
`00_global.yaml` (qué falta en la contabilidad general, cómo saber si un saldo está
recortado y que el resto vive en un esquema que el rol general no lee), con `version`
subida.

R23. La ficha de F-127 debe recoger el criterio que hereda: un apunte analítico (`apa`)
está restringido si su `apuide` es un apunte restringido, si su `conide` es un AP o si
su cuenta analítica es la contrapartida (CP) de un trabajador; medido, 100.502 de las
716.007 filas de `raw.apa` caen por las dos primeras.

R24. `docs/ARCHITECTURE.md`, `azure-apps/datamart_seg_anual.md` y el apartado de lo que
ve la credencial en `azure-apps/mcp_bbdd.md` §2 deben decir qué lee cada rol tras el
cambio, y que lo que exige a `mcp-bbdd` y a F-087 está fuera de este repositorio.

## Aceptación en producción (MANUAL, humano)

R25. CUANDO el humano ejecuta como rol general (`SET ROLE mcp_sigrid_dm_ro` desde la
sesión de administrador) `SELECT` sobre `contabilidad_restringida.mayor`, `raw.apu`,
`raw.apa`, `raw.pag`, `raw.con` y `raw.hmores`, cada uno debe fallar con «permission
denied», y el mensaje se anota en el informe.

R26. Como rol general, `contabilidad.mayor` debe devolver 0 apuntes de cuentas CR y
`contabilidad.saldos_cuenta_mes` 0 filas de cuentas CR.

R27. Como rol autorizado, `contabilidad_restringida.mayor` debe devolver las mismas
filas que `raw.apu` y los 55.504 ± la variación diaria con `restringido = true`.

R28. CUANDO pasa la primera nocturna tras el despliegue, R25 y R26 deben seguir
cumpliéndose sin que nadie ejecute nada a mano (la prueba que valió en F-068).

## Fuera de alcance (anotado, no implementado aquí)

- Que el MCP conecte con otro rol según quién pregunte, y su lista blanca (`mcp-bbdd`
  F-008); el rol propio de Power BI (F-087); quién es «ese rol» y su canal (Juan, D8).
- El coste por persona que ya publica `personal` (D10) y los ajustes del criterio que
  pida Juan tras verlo funcionar (D9, D12).
