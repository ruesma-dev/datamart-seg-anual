<!-- progress/review_F-135.md -->
Revisión incremental desde acd1d99 (pasada 2) · delta `acd1d99..7cf633b` · 2026-10-12

# F-135 · Review · APPROVED

**Veredicto: APPROVED** (pasada 2). Los tres cambios de la pasada 1 están resueltos y verificados. Lo
aprobado hasta `acd1d99` queda dado por bueno. Solo he vuelto a mirar lo que el delta toca: el criterio
de `02`, la guarda de `05`, la columna nueva de `07`, el oráculo de dominio y las fichas.

**Nivel de rigor: `critico`** (declarado). Exige fase RED, cobertura ≥ 80 %, mutación con cero
supervivientes y las MANUAL con su comando exacto.

## Pasada 2 · verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `7cf633b`, árbol principal: **EXIT 0, ENTORNO LISTO**. **7.492 passed, 238
  skipped, 0 failed** en 1.662 s. `PUERTA COBERTURA` [OK] 100,0 % (143/143). `PUERTA TAMAÑO` [OK].
- **Cambio 1, el criterio falla cerrado** (`632f59e`, opción b). En `02` hay dos `COALESCE(codigo ~ regex,
  cuenta_id IS NOT NULL)`, en `marcados` y en `asientos_personal`, y el motivo nuevo es
  `CUENTA_SIN_RESOLVER`. En `05` hay una guarda nueva: 0 apuntes con `cuenta_id` y sin código. En `07`
  hay un recuento nuevo, `num_apuntes_sin_resolver`, que solo cuenta y no lleva importes.
  - **Reproducido en PostgreSQL 16.15 local** (contenedor desechable, ya borrado). `prueba_local_sql.py`
    da **56/56 OK** contra el SQL de `ffadfb2`, así que la copia completa sigue idéntica a la de hoy.
  - Mi caso de la pasada 1 (una 465 en `raw.con` sin fila en `raw.cua`, más su banco) sale ahora
    `CUENTA_SIN_RESOLVER` y `ASIENTO_PERSONAL`, con **0 filas en el general**,
    `num_apuntes_sin_resolver = 1` y la cuenta sin fila en los saldos generales.
  - Si lo fuerzo al general con `restringido = false`, la guarda de `05` salta («1 apuntes con cuenta
    que no resuelve en el plan») y la tabla queda en 0 filas de ese apunte.
  - `cueide = 0` (`cuenta_id` NULL) sigue visible, como antes.
  - Ninguna cifra de hoy cambia: medí 0 casos en Azure en la pasada 1.
- **El oráculo de dominio va a la par del SQL.** `cuenta_sin_resolver`, `_cuenta_cerrada` y el campo
  opcional `ApunteContable.cuenta_id` tienen los mismos semánticos: el motivo `SIN_RESOLVER` va antes
  que `CUENTA`, y una cuenta sin código nunca es CR a la vez. Lo cubren 4 tests nuevos de dominio, el
  contrato `test_f135_r10_la_cuenta_sin_resolver_falla_cerrado` y los literales de `test_f056` y `r5`.
- **Cambio 2, `azure-apps` `b979a4a`.** La sección F-135 y las filas 130-131 dicen ahora **«Estado:
  implementada en la rama, SIN DESPLEGAR»**, y añaden que hasta el despliegue `contabilidad` sigue
  siendo la completa y el rol general sigue leyendo `raw`. El commit es local y sin push.
- **Cambio 3, el test de R23** (`71d4ad8`). `test_f135_r23_la_ficha_de_f127_hereda_el_criterio_de_apa`
  comprueba que la ficha cita `apuide`, `conide` y la CP, el rol y el esquema, y la cifra «100.502 de las
  716.007». También comprueba que el `status` sigue en `pending`.
- **Mutación del delta** (`progress/mutacion_F-135_pasada1.md`).
  - **Recálculo puro:** 1 fichero, 154 líneas, **19 mutantes**, igual que el informe. Incluye los 4
    nuevos en `cuenta_sin_resolver` y `_cuenta_cerrada`.
  - **Toda la rama:** sobre HEAD da 556 líneas y 29 mutantes. Las dos campañas juntas los cubren todos:
    fuera del dominio no cambió ningún `.py` desde `6ff4f16`.
  - **RM1:** medido sobre `d412e0a`, y después solo se añadió el informe.
  - **RM2:** 19 × 186,6 = 3.545 s. Sin la línea base (unos 630 s), el reloj da (3.545 − 630) × 4 / 19 =
    614 s por mutante, que cuadra con esa base.
  - **RM3:** ningún equivalente muerto. `frozen` y `slots` los mata el barrido de F-006.
  - **RM6:** no se quitó ninguna guarda. Se añadieron.
  - **Campaña no reejecutada:** 3.545 s, por encima de 60 s.
- **Fase RED de la pasada 1** en `impl_F-135.md` §3, con salida real: `ImportError` de
  `MOTIVO_CUENTA_SIN_RESOLVER` y los contratos SQL en rojo.
- **El MANUAL añade `raw.asi` y `raw.rac` al paso 8** (`impl_F-135.md` l. 197), como se sugirió.
- **Lecturas en Azure:** esta pasada no ha hecho ninguna.

**Observación (no bloquea):** la tabla «Evidencias» del informe (§7) sigue citando solo la campaña de
25. La de 19/19 vive en su propio fichero porque el implementer se cortó antes de enlazarla. Si se
toca el informe, conviene añadir esa fila.

## Pasada 1 (resumen; detalle en el historial de este fichero, `8470ae0`)

- `init.sh` sobre `782f226`: verde, 7.486 passed. La copia completa es idéntica a la `contabilidad` de
  hoy en PostgreSQL local (51/51). `02_roles.sql` y `apply_grants` con el cliente real dan 16/16 en local.
- El contraste T14 en Azure, repetido por mí en solo lectura, da **55.519 restringidos, 8.796 asientos,
  0 CR visibles y 521 cuentas CR**. El criterio V2 implementado es el medido.
- **Caminos al rol general.** `raw` y `contabilidad_restringida` están vetados cada noche y comprobados
  en el catálogo. No hay privilegios por defecto globales, ni funciones `SECURITY DEFINER`, ni vistas que
  lean el esquema restringido. El `.env` del puesto no lista `raw`. Los importes de lo restringido no
  salen. La única grieta, el cambio 1, ya está cerrada.
- **MANUAL** (`impl_F-135.md` §8): el orden es correcto. Primero Power BI sin `raw` (D3), luego el
  disco, la línea base, `02_roles.sql`, la imagen y el job, el build y `apply-grants`, la comprobación
  de la copia, la **prueba negativa con el login real**, la positiva y R28.
- **`progress/` no tiene datos personales**: solo recuentos.
- **Escrituras en Azure:** ninguna del implementer. **Aviso sobre mí mismo:** en la pasada 1 una lectura
  mía disparó el bootstrap del cliente. Ejecutó el DDL idempotente de `_meta` (sin cambios respecto a
  `main`): en la práctica no cambió nada, pero fue DDL. Lo dejo declarado.

## Checkpoints (estado en `7cf633b`)

**C1** [x] `init.sh` termina con exit 0 · [x] existen los ficheros del arnés.

**C2** [x] solo F-135 está `in_progress` · [x] la rama es la de la feature · [x] `current.md` abre con
la sesión activa · N/A `history.md`: la feature aún no está `done`.

**C3** [x] hexagonal: el dominio es puro y lo comprueba un test; el SQL está en `sql/contabilidad/` con
`NN_` · [x] primera línea con la ruta en todos los ficheros nuevos · [x] sin `print`, TODO, secretos ni
dependencias nuevas · [x] semántica de Sigrid: R-SALDO-CONTABLE se conserva.

**C3 bis** N/A: `docs/referencia/` no cambia.

**C4** [x] R1-R24 con test trazable y en verde (R23 ya lo tiene); R25-R28 son MANUAL · [x] los tests
no tocan red ni BBDD · [x] las MANUAL están en `impl_F-135.md` §8 con comando exacto, y `current.md`
remite allí · [x] la puerta de dobles está en verde.

**C4 bis** [x] `rigor` declarado · [x] fase RED real (pasadas 0 y 1) · [x] cobertura 100 % (143/143) ·
[x] mutación recalculada (25 + 19) · [x] no reejecutada: las dos pasan de 60 s · [x] coste por mutante
coherente · [x] sin «⚠ CAMPAÑA NO VÁLIDA», «Sin veredicto» = 0 · [x] RM1, RM2 (arriba) · [x] RM3:
`frozen`/`slots` muertos con razón · N/A RM5: sin equivalentes · [x] RM6: no se quitó ninguna guarda ·
N/A campaña manual: las automáticas dieron 25 y 19 · [x] 0 supervivientes · [x] «Evidencias» (ver la
observación) · [x] ningún N/A sin motivo.

**C4 ter** N/A: no existe `harness/rutas_sensibles.json`.

**C5** [x] T1-T14 y T19 en `[x]`. T15-T18 son MANUAL y siguen pendientes, como deben. Los commits de la
pasada 1 citan su cambio · [x] `git status` limpio · [x] `features.json` en `in_progress` hasta las
MANUAL.

## Cobertura · requisito → test (`tests/test_f135_*`)

| Req. | Tests |
|---|---|
| R1, R3 | `dominio::r1_*` (6), `dominio::r3_*` (3) |
| R2, R7 | `dominio::r2_*` (9), `dominio::r7_*` (9, con `cuenta_sin_resolver`), `sql::r7_la_cuenta_gana_al_asiento` |
| R4 | `sql::r4_*` (3), `dominio::r1_la_regex_del_sql_se_construye_desde_la_tupla` |
| R5, R6 | `sql::r5_*` (9), `sql::r6_la_guarda_de_recuento_va_sobre_el_completo`, `test_f056_*` adaptados |
| R8-R14 | `sql::r8_*`, `r9_*`, `r10_*` (2, con `la_cuenta_sin_resolver_falla_cerrado`), `r11_*` (2), `r12_*`, `r13_*`, `r14_*` (2), `sub_pasos_*` (2) |
| R15-R18 | `grants::r15_*` (4), `r16_*` (4), `r17_*` (4), `r18_*`, `cliente_*` (7), `paso_*` (4) |
| R19, R20 | `grants::r19_*` (2), `settings_*` (5), `grants::r20_*` (8) |
| R21, R22 | `sql::r21_retenciones_declara_la_excepcion`, `sql::r22_*`, `sql::diccionario_*` (5) |
| R23 | `sql::r23_la_ficha_de_f127_hereda_el_criterio_de_apa` |
| R24 | `sql::docs_*` (2) |
| R25-R28 | MANUAL (§8, pasos 8, 9 y 11) |

## Cambios requeridos

Ninguno. Para cerrar la feature quedan las MANUAL T15-T18 del humano, en el orden de §8 y el mismo día
para los pasos 3-6. Al desplegar hay que cambiar a «DESPLEGADA» la línea de estado de `azure-apps`.

## Automejora (propuesta, no aplicada)

- `build_postgres_client` ejecuta el bootstrap (DDL) antes de la primera lectura, también en un
  diagnóstico por `filas_solo_lectura`, y en la pasada 1 me pasó a mí. Propongo un cliente de solo
  lectura sin bootstrap, y que `reviewer.md` lo exija para cualquier lectura de Azure. Vale para
  cualquier proyecto con auto-bootstrap: habría que portarlo a `arnes-base`.
