<!-- progress/impl_F-141.md -->
# F-141 · Informe del implementer (2026-10-17)

Rama `feature/F-141-perfil-restringido`, un commit por tarea (`e6b11e2` T1 … `557295c` T11, T12 aparte).
En `azure-apps`, commit propio sin push (`a520a62`). **Nada se ejecutó contra Azure**: ni
`02_roles.sql`, ni GRANT, ni Key Vault, ni `publicar-diccionario`. Ningún secreto, oid ni UPN.

## 1. Qué cambió

| Fichero | Cambio |
|---|---|
| `config/settings.py`, `.env.example` | `PG_PERFIL_RESTRINGIDO_GROUP/_LOGIN/_SCHEMAS/_EXCLUDED_TABLES` con los defectos de la spec y sus `*_list`; `DEFAULT_RESTRICTED_ROLE = sigrid_dm_autorizado_ro`; `NOMBRE_AUTORIZADO_RETIRADO`; comentario con la regla literal del humano (R1-R2) |
| `etl_sigrid/infrastructure/postgres/grants.py` | `EXCEPCIONES_FILTRACION_RESTRINGIDO` (D4), `PATRON_VIGILADO_RESTRINGIDO`, `ESQUEMAS_ORIGEN_DE_VISTAS` (`raw`), `TABLAS_ORIGEN_ADJUNTOS`; puras `perfil_restringido_en_conflicto`, `excluidas_invalidas`, `origenes_de_adjuntos_sin_leer`, `esquemas_ajenos`, `separar_excepciones`, `build_perfil_restringido_statements` |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `SQL_VISTAS_QUE_FILTRAN` (clausura recursiva `pg_rewrite` + `pg_depend`), `SQL_OBJETOS_VIGILADOS`, `SQL_PERTENENCIAS`; `vistas_que_filtran`, `objetos_vigilados`, `pertenencias`, `apply_perfil_restringido` |
| `etl_sigrid/application/steps/apply_grants_step.py` | Guarda R3 (nombre retirado); `_PerfilRestringido` (guardas R4-R8 sin conexión y bloque R9-R18, el ÚLTIMO); `_BloqueRestringido`; `metadata` y mensaje único (R19); docstring |
| `infra/sql/02_roles.sql` | Guarda `RESTRINGIDO_PWD`; punto 0 bis (renombre condicionado, falla con los dos nombres); alta del grupo y del login; `CONNECT` al grupo; 5 quinquies a) como dueño y b) como administrador; comprobación final de siete roles |
| `infra/15_provision_db.ps1` | `-Ejecutar` exige `RESTRINGIDO_PWD`; rótulo del perfil |
| `config/diccionario/*` (v54) | Regla `R-PERFIL-RESTRINGIDO`; frase de D7 en las tres `R-*-RESTRINGIDA`; aviso «No disponible para el perfil restringido» al principio de 10 fichas; «El perfil restringido SI la lee» en las tres vistas de pago; cabeceras de los tres YAML `*_restringida` |
| `docs/ARCHITECTURE.md`, `docs/runbook_postgres_azure.md` | Siete roles, el bloque del restringido, la obligación de F-127; tabla de roles y §13 P0-P9 + vuelta atrás |
| Renombre (texto) | dos docstrings de build, `contabilidad/00_setup.sql`, cinco tests de F-135/F-136/F-037/F-138 |
| `../azure-apps/datamart_seg_anual.md`, `mcp_bbdd.md` | Sección «El perfil RESTRINGIDO del MCP» con E1-E8 y fila en «Qué expone»; en `mcp_bbdd.md` una línea-enlace |
| `tests/test_f141_perfil_restringido.py` (nuevo) | 140 tests |

## 2. Decisiones y desviaciones (justificadas)

1. **`getattr` del grupo** en `_PerfilRestringido.desde`: una configuración sin los campos de
   F-141 (los `SimpleNamespace` de los tests de F-005/F-068/F-135/F-136) es «sin configurar»
   (R9). Así esos tests no cambian (R19); el resto de campos se leen por atributo.
2. **Orden en `02_roles.sql`**: las guardas de contraseña y la de «existen los dos» van ANTES
   del renombre (R21 pide fallar «antes de crear o cambiar nada»; el design §6 ponía el renombre
   primero). El renombre sigue antes de todo `CREATE`/`ALTER` (verificado en T11).
3. **5 quinquies partido en dos**: la mitad del DUEÑO (GRANT, privilegio por defecto en REVOKE,
   REVOKE de excluidos, veto) va dentro del tramo `SET ROLE sigrid_dm_etl` del 5 ter, porque los
   tests de F-135/F-136 exigen que el ÚLTIMO `SET ROLE sigrid_dm_etl;` sea el del veto del total;
   la del ADMINISTRADOR (veto con el otro concedente + la pertenencia) va tras el 5 quater. Todo
   dentro del mismo `BEGIN … COMMIT`. Se concede como dueño para que la nocturna pueda revocar.
4. **Veto de lo ajeno derivado del catálogo** también en `02_roles.sql` (como R12 en la nocturna),
   no una lista escrita a mano.
5. **Tests de otras features que cambian algo más que el literal** (inevitable): F-136 `r12`
   (los cinco ⊆ los siete), `r17` (`PASSWORD` 3 → 4), `r31` («Cinco roles» → «Siete roles»);
   F-135 `r23` lee la ficha de F-127 en `features.json` (del líder): acepta el nombre nuevo o el
   retirado, por la constante. **Para el líder**: la ficha de F-127 aún nombra el grupo con el
   nombre retirado y debe decir que excluye su mayor analítico de
   `PG_PERFIL_RESTRINGIDO_EXCLUDED_TABLES`.
6. **`mcp_bbdd.md`**: además del enlace, el literal del nombre del grupo (3 apariciones), porque
   el test de F-135 lo exige y el nombre es nuestro. Ninguna cláusula del contrato copiada.
7. **`dataclass(..., slots=True)`**: lo exige `test_f006_dataclasses_inmutables`.
8. Barrido R25: la ruta `specs/F-141-perfil-restringido/` casa con el patrón de «clave
   generada» de F-005; se neutraliza solo esa ruta antes de barrer.

## 3. Fase RED (comando exacto y traza real, recortada)

Todas con `python -m pytest tests/test_f141_perfil_restringido.py -k "<selección de la tarea>" -q -p no:cacheprovider`
ANTES del código; después, la misma orden en verde. Trazas completas en el scratchpad de la sesión (`red/t*.txt`).

| Tarea | `-k` | Resultado RED (real) | Línea de fallo representativa |
|---|---|---|---|
| T1 | `r1 or r2` | `7 failed, 1 passed in 5.52s` | `ImportError: cannot import name 'NOMBRE_AUTORIZADO_RETIRADO' from 'config.settings'` |
| T2 | `r24` | `2 failed` | `AssertionError: solo entre la carga de variables y el primer CREATE ROLE: el renombre y su guarda` |
| T3 | `grants or excepciones or r11` | `16 failed, 3 passed in 0.98s` | `ImportError: cannot import name 'build_perfil_restringido_statements' from '…grants'` |
| T4 | `cliente` | `9 failed in 1.38s` | `AttributeError: 'PostgresClient' object has no attribute 'apply_perfil_restringido'` |
| T5 | `r3 or r4 or r5 or r6 or r7 or r8` | `17 failed, 12 passed in 1.15s` | `FAILED …test_f141_r3_el_nombre_retirado_para_en_seco` (el paso daba SUCCESS) |
| T6 | `r9 … r19 or paso` | `19 failed, 9 passed in 1.32s` | `FAILED …test_f141_r11_r12_camino_normal_en_orden_y_el_ultimo` |
| T7 | `r20 or r21 or r22 or r23` | `12 failed in 1.20s` | `FAILED …test_f141_r20_renombre_condicionado_y_antes_de_crear_nada` |
| T9 | `r26 or r27 or r28 or r29` | `27 failed in 4.38s` | `FAILED …test_f141_r26_la_regla_nueva_es_bloqueante_y_corta_de_titulo` |
| T10 | `r30` | `9 failed in 1.02s` | `FAILED …test_f141_r30_runbook_seccion_13_en_orden` |
| T12 | `anota_lo_revocado` (mutante 4 aplicado a mano) | `AssertionError: el existente, de un esquema concedido` / `assert [] == ['contabilidad.mayor']` | sin la mutación, en verde |

Los que pasaron en RED sin código eran hechos del árbol que ya se cumplían (p. ej. las tres
excepciones de D4 leen la cartera en `05_vencimientos.sql` y `06_pago_factura.sql`, o «sin rol
estándar no se mira nada»). T8 es un barrido (nada que implementar): en verde a la primera,
con su test de control que caza muestras sintéticas.

## 4. T11 · PostgreSQL 16 REAL local (`postgres:16` = 16.15, `psql.exe` 16.4)

Contenedor desechable `postgres:16` (16.15, `createrole_self_grant` vacío), administrador
`admin_f141` NO superusuario (`CREATEROLE CREATEDB`), `psql.exe` 16.4 con las opciones delante.
Estado de partida = Azure hoy: `01_create_database.sql`, el `02_roles.sql` de `386da30` (nombre
VIEJO) y el `apply_grants` de `386da30`; objetos mínimos de cada esquema (las tres vistas de pago
sobre `tesoreria.efectos`, `maestro.obras` sobre `raw` y `stg`). Scripts y salidas en el
scratchpad (`t11/`); contenedor y claves locales, BORRADOS al acabar.

| Prueba | Resultado real |
|---|---|
| R21: login sin `RESTRINGIDO_PWD` | `exit=3`, `ERROR: F-141: mcp_sigrid_dm_restringido no existe y falta RESTRINGIDO_PWD…`; el nombre viejo sigue, nada creado |
| 1.ª ejecución con la variable (nombre viejo) | `exit=0`; «grupo autorizado renombrado»; restringido «contraseña fijada», las otras tres SIN CAMBIOS; `COMMIT`; siete roles `rolsuper = f`; login con UNA pertenencia (`hereda t`, `set_role f`, `admin f`); `t` en los diez, `f` en los seis; `mayor f`, `saldos f`, `plan_cuentas t`, `vencimientos t`, `conecta t`; 0 filas propias |
| 2.ª ejecución sin variables | `exit=0`; «sin renombre»; cuatro SIN CAMBIOS |
| R20: existen los dos nombres | `exit=3`, `ERROR: F-141: existen … decide cuál sobra`, nada cambiado |
| El total tras el renombre | miembro de `mcp_sigrid_dm_ro` y `sigrid_dm_autorizado_ro`; lee las tres `*_restringida` (`t t t t`) |
| `apply_grants` REAL, noche normal | SUCCESS, 112 sentencias; los ocho del restringido y los tres de antes a `ok` |
| Negativa con el login | `permission denied` en las ocho (tabla `mayor` y `saldos_cuenta_mes`, esquema en el resto), en `CREATE TABLE compras.…` y en `SET ROLE` al grupo |
| Positiva con el login | las tres vistas de pago, `plan_cuentas`, `retenciones.movimientos`, `mart.fact_seguimiento_mensual`, `maestro.obras`, `_meta.etl_runs`; `documento_adjuntos` 3 = 3 (admin) |
| R33 local | huella de 246 líneas del estándar y el total IGUAL antes y después (y al final) |
| Vista nueva `mart` → `tesoreria` | FAILED `… mart.v_f141_filtra -> tesoreria.efectos. Ya se le han revocado…`; después `has_table_privilege` = f |
| Tabla `contabilidad.mayor_x` | FAILED, `vigilados_restringido = ['contabilidad.mayor_x']`; revocada |
| `GRANT USAGE ON SCHEMA tesoreria TO PUBLIC` | FAILED, `tesoreria (USAGE)` para el grupo y el login, un mensaje |
| Login miembro del estándar | FAILED: `pertenencias_restringido` + las 7 lecturas heredadas |
| Tabla nueva en `mart` (privilegio por defecto) | grupo `false`, estándar `true` (REVOKE por defecto, como pide R11) |
| Fugas | 0 apariciones de cualquier contraseña en todas las salidas |

Hallazgo de entorno: `localhost` en Windows colgaba psycopg contra el puerto publicado solo en
IPv4; con `127.0.0.1`, inmediato (nada del código).

## 5. Fuera del alcance y pendiente

- **Review pasada 1 (CHANGES_REQUESTED, solo evidencia), resuelta el 2026-10-17**: el humano
  ACEPTA los equivalentes 1-3 («acepto», por chat con el líder) y las MANUAL T14-T17 quedan con
  su comando exacto en `progress/current.md` (sección de F-141). Sin cambios de código ni campaña nueva.
- **`init.sh` de la pasada del 2026-10-17 en ROJO por causa AJENA** (R30, una fila de
  `azure-apps/mcp_bbdd.md` sin enlace al contrato). Resuelto por la sesión de `mcp-bbdd`
  (`63e1bfa` en `azure-apps`); F-141 vuelve a `in_progress` el 2026-10-18 (§5 bis).
- **MANUAL del humano** (runbook §13, T14-T17): merge, imagen y `85_update_job` el MISMO día que
  `02_roles.sql` con `RESTRINGIDO_PWD` desde `kv-mcp-bbdd-dev/pg-password-restringido`; R31-R32
  con el login real; R33 con la huella; `publicar-diccionario` (v54) y reinicio del MCP; R34 en la
  nocturna siguiente; entregar E1-E8 a `mcp-bbdd`.
- **`.env` del puesto**: si fija `PG_RESTRICTED_ROLE` con el nombre retirado, `apply-grants` para
  (R3, a propósito). Lo corrige el humano.
- Hallazgo heredado (F-136): `01_create_database.sql` falla con un administrador no superusuario
  en PG16 local; en T11 se sorteó como en F-136.
- Push de `azure-apps` y de la rama: el humano.

## 5 bis. Ampliación del 2026-10-17: la ficha de adjuntos nombra `abrir_adjunto`

Aprobada por el humano el 2026-10-17 (encargo del líder), dentro de la misma v54. Motivo:
`mcp-bbdd` desplegó `abrir_adjunto(adjunto_id)` (su F-023) el 2026-10-17 y el humano la verificó
con Claude y ChatGPT; la ficha seguía diciendo «NO ESTA DESPLEGADA todavia».

| Fichero | Cambio |
|---|---|
| `config/diccionario/compras.yaml` | Párrafo «EL LIMITE (F-139)» de `documento_adjuntos`: la IA localiza el `adjunto_id` en el índice y abre el ORIGINAL con `abrir_adjunto(adjunto_id)` del MCP, SIN CONVERTIR (imágenes visibles; PDF y ofimática como binario; conversión = F-142); permisos = regla D1 de F-139 («QUIEN PUEDE ABRIR EL FICHERO»). Siguen los 17 ficheros > 20 MB; el tope de 64 MB no figuraba y no se añade |
| `config/diccionario/00_global.yaml` | Una línea en la entrada de la versión 54 (sin subir versión) |
| `tests/test_f139_limite.py` | R2: fuera «NO ESTA DESPLEGADA» de lo exigido; `..._no_afirma_que_la_herramienta_exista` pasa a `..._nombra_la_herramienta_desplegada`: exige la firma, F-023, la fecha, el `adjunto_id` en el índice, imágenes y binario, la regla D1, y PROHÍBE «NO ESTA DESPLEGADA» y «ni el datamart ni el MCP abren». Ningún otro test (F-090 incluido) miraba ese texto |
| `harness/features.json`, `BACKLOG.md` | F-141 `blocked` → `in_progress` |

**Fase RED** (test cambiado antes que la ficha):
`python -m pytest tests/test_f139_limite.py -k r2 -q -p no:cacheprovider`
```
E           AssertionError: la ficha no dice «`abrir_adjunto(adjunto_id)`» (R2, F-141)
FAILED tests/test_f139_limite.py::test_f139_r2_la_ficha_nombra_la_herramienta_desplegada
1 failed, 1 passed, 13 deselected in 0.37s
```
Tras la ficha (y ajustar el literal esperado a «imagenes se ven directamente», el de la frase
escrita): `tests/test_f139_limite.py` + `tests/test_f141_perfil_restringido.py` → `156 passed`
en 5,32 s; `-k "f090 or f006 or diccionario or adjunto"` → `2935 passed, 246 skipped` en 216,60 s.

**`bash harness/init.sh` de esta pasada (2026-10-18)**: VERDE. `8225 passed, 249 skipped` en
1.024,34 s (17 min 04 s); `PUERTA COBERTURA: 100.0% de 227 líneas cambiadas cubiertas`; `PUERTA
TAMAÑO` dentro de los topes; `ENTORNO LISTO`. Sin campaña de mutación nueva: el cambio es texto
del diccionario y un test, sin código de producción.

## 6. Evidencias

| Evidencia | Valor real |
|---|---|
| Tests de F-141 | **140 passed** en 5,08 s (`tests/test_f141_perfil_restringido.py`; el barrido R25 suma este informe) |
| Suite completa (`bash harness/init.sh`) | **8225 passed, 249 skipped**, 0 fallos, `ENTORNO LISTO` el 2026-10-18 tras la ampliación (§5 bis); antes, 8224 sobre `de9656f` |
| Cobertura de líneas cambiadas | `PUERTA COBERTURA: 100.0% de 227 líneas cambiadas cubiertas (227/227, umbral 80%, nivel critico)` |
| Mutación (`python -m harness.mutacion --feature F-141 --workers 3 --timeout 9000`) | **56 generados, 56 evaluados, 52 muertos, 4 supervivientes, 0 timeouts**, 14.715,6 s (línea base 1.149-1.162 s por worker). Análisis en `progress/mutacion_F-141.md`: el 4 era un hueco real del LOG, cerrado con test nuevo (RED pegado arriba); los 1-3 son EQUIVALENTES (`split(".", 1)[0]` ≡ `split(".", 2)[0]`), **ACEPTADOS por el humano el 2026-10-17** (por chat con el líder: «acepto»; anotado bajo cada «Decisión» de `progress/mutacion_F-141.md`) |
| Tiempo de la suite | 1.024,34 s el 2026-10-18; 1.013,02 s (16 min 53 s) con medición de cobertura sobre `de9656f` (1.612,54 s en la pasada anterior): máquina compartida con otras sesiones |

La primera campaña (`rc=3`, sin veredictos) agotó los 600 s de la línea base con 4 workers en una
máquina compartida con otras sesiones; se relanzó con `--workers 3 --timeout 9000` (patrón de
F-136, que usó 2400). La campaña paralela puede dar FALSOS MUERTOS (F-041 pendiente): los 52
muertos NO se han reverificado en serie.
