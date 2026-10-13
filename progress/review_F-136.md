<!-- progress/review_F-136.md -->
Revisión incremental desde e8c9e21 (pasada 2) · delta `e8c9e21..fa4f52a` · 2026-10-13

# F-136 · Review · APPROVED (APROBADO)

**Veredicto: APPROVED** (pasada 2). Los dos cambios de la pasada 1 están resueltos y las recomendaciones
de §12, aplicadas. Lo aprobado hasta `d3a3893` queda dado por bueno. El delta solo toca el runbook,
`tests/test_f136_login_total.py` y `progress/impl_F-136.md`: **ningún fichero del alcance de la mutación**
(RM1: la campaña de `974ff68` sigue valiendo, como la cobertura de 60/60).

## Pasada 2 · verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `fa4f52a`: **exit 0, ENTORNO LISTO**. **7.587 passed, 238 skipped, 0
  failed** (843 s). `PUERTA COBERTURA` [OK] 100,0 % (60/60). `PUERTA TAMAÑO` [OK].
- **Cambio 1, P12 con `--yaml`** (`1d2761d`). He ejecutado el bloque de P12 **tal cual**, extraído del
  runbook, en **Windows PowerShell 5.1.26100** con un `az` simulado (sin Azure) que devuelve una plantilla
  ficticia con nulos, un `env` con `value` y otro con `secretRef`, `resources` y `probes`. Resultado:
  - `Sin-Nulos` quita los nulos de primer nivel y los de dentro de los contenedores y del `env`;
  - `command = ["python"]` y `args = ["main.py","check-pg"]` salen como **arrays JSON**, sin el
    envoltorio `value/Count` de PS 5.1;
  - el fichero sale **sin BOM** y **se borra** después del `start`;
  - el secreto va solo como `secretRef`. Una plantilla de Container Apps no lleva valores secretos (viven
    en `configuration.secrets`, que no se lee).
  `-o none` en el `start`, sin `--command`/`--args`. Los tests nuevos `r25_p12_*` y
  `r25_ningun_job_start_con_command_*` también barren el informe. RED pegada en `impl_F-136.md` §8.
- **Cambio 2, §4** (`3b81ac5`). La §4 ya no toca `kv-mcp-bbdd-dev`, `pg-password` ni `TOTAL_PWD`, y
  remite a «§12, P2-P3» (test `r25_la_seccion_4_*`). Una provisión desde cero no queda rota: si falta
  `TOTAL_PWD`, `15_provision_db.ps1 -Ejecutar` para con «APP_PWD, MCP_PWD y TOTAL_PWD ... runbook
  secciones 4 y 12», y §12 P1-P3 carga las tres.
- **Recomendaciones** (`4492b4e`): P3 `-cne`; P10 `BEGIN` / `CREATE TABLE` / `ROLLBACK`; P0 lee
  `shared_preload_libraries` con `parameter show`, solo lectura (un test veta `parameter set`); P6 y P12
  avisan de una espera «del orden de 30 minutos». Quedan fuera, con razón: `infra/README.md` y el
  `$LASTEXITCODE` de `15_provision_db.ps1`.
- **Secretos**: barrido del delta y de sus mensajes de commit (GUID, correo/UPN, IPv4, cadenas tipo
  clave): **limpio**. El barrido R23 de los tests pasa, también sobre este informe. Nada contra Azure.
- **Checkpoints**: los de la pasada 1 siguen en `[x]`. C4: los MANUAL de P12 traen ahora su comando
  correcto. C5: un commit por cambio, árbol limpio.

## Pasada 1 (completa, `main...d3a3893`): CHANGES_REQUESTED

**Nivel de rigor: `critico`** (declarado en `features.json`). Exige fase RED, cobertura ≥ 80 % de lo
cambiado, mutación con cero supervivientes y las MANUAL con su comando exacto.

## Verificación ejecutada (resultado real)

- `bash harness/init.sh` sobre `d3a3893`: **exit 0, ENTORNO LISTO**. **7.582 passed, 238 skipped, 0
  failed** (849 s). `PUERTA COBERTURA` [OK] **100,0 % (60/60)**. `PUERTA TAMAÑO` [OK] (148/150, 244/250,
  220/220). Ruff: 273 avisos de deuda previa, no bloquean. El barrido de dobles (`test_f025`) pasa.
- **Mutación, recálculo puro**: `alcance_de_feature('F-136', base='main')` da 3 ficheros y **183 líneas**,
  y `generar_mutantes` da **15** (settings 0, paso 12, cliente 3): coincide con el informe. **Campaña no
  reejecutada: 3.189 s según el informe** (> 60 s). En su lugar, **RM4** sobre una copia (`git archive`) en
  mi scratchpad, con `test_f136` y `test_f135`: `l.161 or→and` (R3), `l.244 ==→!=` y `l.1455
  fila[0]→fila[1]`, los tres **MUERTOS** (1 fallo cada uno). Control sin mutar: 128 passed.
- **PostgreSQL 16.15 real** (contenedor desechable, ya borrado; administrador no superusuario; `psql.exe`
  16.4). R18: sin `TOTAL_PWD` da `exit=3` y no crea ningún rol. 1.ª ejecución: tres «fijada»; el total
  con dos pertenencias (`hereda t`, `set_role f`), `raw f` y 0 propios. 2.ª: tres «SIN CAMBIOS». **R24**:
  0 apariciones del valor con `-b -e` y 1 en el control sin las `\set` (el log del servidor sí lo guarda:
  riesgo de design §5). Negativa y positiva del total: OK. `apply_grants` con el cliente real: ok ×3;
  PUBLIC → FAILED con las dos listas; sin el autorizado → `acceso_total`; miembro del dueño → FAILED.
- **Secretos** (GUID, correo/UPN, IPv4, `user=` no genérico, cadenas tipo clave, `print(`, TODO) en el
  diff, los commits y `234fe9a` de `azure-apps` (`master`, sin push): **limpio**; ni oid, ni UPN, ni nombre
  del administrador. `.env` y `.env.azure.bak` sin leer ni tocar. **Nada contra Azure.**

## Lo pedido «con especial cuidado»

- **`02_roles.sql`**: silencio antes de `\getenv`, contraseñas opcionales, guarda R18, `raw` vetado al
  total con dos concedentes, 5 quater `WITH INHERIT TRUE, SET FALSE` dentro de la transacción y ningún
  otro GRANT al total; ninguna contraseña en la línea de órdenes; opciones de `psql` delante en todo.
- **`apply_grants`**: D2 (aviso y SUCCESS), veto tras las concesiones, FAILED si lee lo vetado, R2/R3
  sin conexión; F-135 sin cambios de aserción y con el mensaje idéntico.
- **Diccionario v50**: cumple R32-R33. **«Correo de Juan Romero» en `motivo`: aceptable**: es la
  procedencia de F-135, ya publicada en la v49, y no dice quién tiene el perfil total (lo que R32 protege).

## Checkpoints

- **C1** [x] `init.sh` en verde · [x] existen los ficheros del arnés.
- **C2** [x] una sola `in_progress` (F-136) · [x] rama `feature/F-136-usuario-mcp-total` · [x] `current.md`
  con la sesión activa (formato de registro del repositorio, igual que en F-135) · [x] F-135 en `history.md`.
- **C3** [x] hexagonal: la lógica en el paso (aplicación) y el SQL de catálogo en el cliente
  (infraestructura); sin dominio nuevo · [x] primera línea con ruta (el `.ps1` lleva BOM, como antes) ·
  [x] sin prints, TODOs, secretos ni dependencias nuevas · [x] semántica Sigrid: no toca capas de datos.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x] R1-R33 trazables (tabla) · [x] los unit tests no tocan red ni BBDD (cliente falso y conexión
  simulada; R30 lee ficheros de `azure-apps` y hace skip si no están) · [x] MANUAL listadas: `current.md`
  remite a `impl_F-136.md` §5 y al runbook §12, que traen los comandos (P12, mal: cambio 1) · [x] dobles
  contra el original: barrido automático en verde.
- **C4 bis** [x] rigor `critico` declarado · [x] fase RED con salida real para T1-T7, T9 y T10 bis; la de
  T8 se hizo rompiendo a propósito, como pide la regla · [x] cobertura [OK] 100 % · [x] mutación
  recalculada (183 líneas, 15 mutantes) · [x] muertos: campaña > 60 s, no reejecutada; RM4 sobre 3 ·
  [x] coste por mutante 3.189 × 4 / 15 ≈ 850 s, muy por encima de 1 s · [x] sin «CAMPAÑA NO VÁLIDA» y
  0 sin veredicto · [x] **RM1**: medido en `974ff68`; hasta `d3a3893` solo cambian tests, specs y
  progress, nada del alcance · [x] **RM2**: media × W = 850 s frente a una base de unos 605 s, sin salto
  de orden de magnitud · [x] **RM3**: revisé los 15 y ninguno es equivalente (`+=`/`+` → `-` sobre
  listas da `TypeError`, que el paso convierte en FAILED) · N/A **RM5**: no hay equivalentes declarados ·
  N/A **RM6**: no se quitó ninguna guarda defensiva · N/A campaña manual: la automática dio 15 · [x] sin
  supervivientes · [x] «Evidencias» con los cuatro números y los workers (4) · [x] cada N/A, justificado.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** [x] T1-T13 en `[x]` y T14-T17 pendientes por ser MANUAL de despliegue (justificado). Un commit
  por tarea, salvo `T11-T13` juntas: T12 y T13 son verificaciones sin cambios, y lo acepto · [x] árbol
  limpio · [x] `in_progress` coherente.

## Cobertura requisito → test (`tests/test_f136_login_total.py`)

| R | Test / evidencia |
|---|---|
| R1 | `r1_settings_*`, `r1_env_example_*`, `r1_el_job_no_necesita_*` |
| R2-R4 | `r2_total_igual_a_otro_rol_*`, `r2_un_total_vacio_*`, `r3_*` (2), `r4_sin_rol_estandar_*` |
| R5-R11 | `r5_*`, `r6_*`, `r7_camino_normal_*`, `r8_*` (2), `r9_*` (2), `r10_*` (2), `r11_*`, `paso_*` (4) + `cliente_*` (7) |
| R12-R19 | `r12_*` (2), `r13_*`, `r14_*`, `r15_*`, `r16_*` (2), `r17_*`, `r18_*`, `r19_*`, `r12_r19_*` + PG real (arriba) |
| R20-R22 | `r20_*` (3), `r21_*`, `r22_*` (4) |
| R23 | `r23_*` (3, el barrido incluye este informe) |
| R24 | PG real: 0 apariciones y el control con 1 (T10 del implementer y esta review) |
| R25 | `r25_*` (4), `r26_r28_las_pruebas_del_procedimiento` |
| R26-R29 | MANUAL (T15-T16); reproducidas en local las negativas y las positivas |
| R30-R31 | `r30_*` (2), `r31_*` |
| R32-R33 | `r32_*` (3), `r33_*` (2), `r32_r33_sin_nombres_oid_ni_upn` |

## Cambios requeridos de la pasada 1 (resueltos en la pasada 2)

1. Runbook §12 P12: `job start --command/--args` sin `--image` falla en esta CLI («must have an 'Image'
   property») o lanzaría la nocturna completa; design §6 y D14 mandan `--yaml`.
2. Runbook §4: leía `pg-password-total` del vault del MCP sin crearlo; remitir a §12 P2-P3.

## Recomendaciones de la pasada 1 (las de §12, aplicadas en la pasada 2)

- P3: `-cne` en vez de `-ne` (PowerShell compara sin mayúsculas). P10: el `CREATE TABLE` negativo entre
  `-c "BEGIN"` y `-c "ROLLBACK"`. P0: mirar en lectura si carga `pgaudit` (`shared_preload_libraries`).
- P6/P12: una referencia a Key Vault sin versión puede tardar del orden de 30 min, no «un par de minutos».
- Para otra feature: `infra/README.md` l. 313 y 322 usan el mismo `job start --command` sin `--yaml`, y
  `15_provision_db.ps1` no mira `$LASTEXITCODE` tras `01_create_database.sql`.

## Automejora (propuesta, no aplicada)

C4 podría exigir que todo `az ... start/update` de un procedimiento MANUAL nuevo copie un patrón ya usado
con éxito en el repositorio: los tests textuales miran la forma (`-o none`, longitud), no que funcione.
