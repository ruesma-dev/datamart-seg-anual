<!-- progress/review_F-136.md -->
Revisión completa (pasada 1) · `main...d3a3893` (merge-base `dc1797b`) · 2026-10-13

# F-136 · Review · CHANGES_REQUESTED (RECHAZADO)

**Veredicto: CHANGES_REQUESTED.** El código, `02_roles.sql`, los tests, la mutación y el diccionario v50
están bien y los he verificado por mi cuenta, también contra PostgreSQL 16 real. Lo que falla es el
**procedimiento MANUAL del runbook**: el paso P12 de la §12 no se puede seguir tal cual, y la §4 lee un
secreto que no crea. Son dos arreglos de documentación, sin tocar código (ver «Cambios requeridos»).

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
- **PostgreSQL 16.15 real** (contenedor desechable, ya borrado), administrador **no superusuario**
  (`CREATEROLE CREATEDB`), `psql.exe` 16.4 de Windows y opciones delante. Valores aleatorios de usar y
  tirar, que no salen de la máquina:
  - **R18** (base nueva, sin `TOTAL_PWD`): `exit=3`, error «falta TOTAL_PWD», **ningún rol creado**.
  - **1.ª ejecución**: `exit=0`, tres «fijada», `COMMIT`; el total con dos pertenencias (`hereda t`,
    `set_role f`), `raw f`, `contabilidad_restringida t`, `contabilidad t`, `conecta t`, 0 propios.
    **2.ª sin variables**: tres «SIN CAMBIOS»; los tres logins siguen entrando.
  - **R24** (login sin `CREATEROLE`, `-b -e`): `exit=3` y **0 apariciones** del valor en stdout+stderr.
    **Control** sin las tres `\set` de silencio: **1 aparición** (la prueba muerde). En el log del
    SERVIDOR sí aparece: riesgo residual de design §5, aceptado.
  - **Negativa** del total: `permission denied` en `raw` (apu, pag), CREATE en `contabilidad`, INSERT en
    `mayor` y `SET ROLE`. **Positiva**: `contabilidad_restringida.mayor` 5 = `raw.apu` 5.
  - **`apply_grants` con el cliente REAL**: normal → SUCCESS, 46 sentencias, tres «ok»; PUBLIC en `raw`
    → FAILED con las **dos** listas en un mensaje (R9); total sin el autorizado → SUCCESS y
    `acceso_total = [contabilidad_restringida]`; total miembro del dueño → FAILED solo con el total;
    concesión del dueño al total → el veto la quita, SUCCESS; deshecho → SUCCESS.
- **Secretos** (GUID, correo/UPN, IPv4, `user=` no genérico, cadenas tipo clave, `print(`, TODO) en el
  diff, los commits y `234fe9a` de `azure-apps` (`master`, sin push): **limpio**; ni oid, ni UPN, ni nombre
  del administrador. `.env` y `.env.azure.bak` sin leer ni tocar. **Nada contra Azure.**

## Lo pedido «con especial cuidado»

- **`02_roles.sql`**: correcto. `\set ON_ERROR_STOP`, `ECHO none`, `VERBOSITY terse` y `SHOW_CONTEXT
  never` van ANTES de `\getenv`. Las contraseñas son opcionales, con «fijada / SIN CAMBIOS». La guarda R18
  va antes de crear nada. Al total se le veta `raw` con los dos concedentes (5 ter). El 5 quater, con
  `WITH INHERIT TRUE, SET FALSE`, va dentro de la transacción y después del 5 ter. Ningún otro `GRANT …
  TO` al total. Ninguna contraseña viaja en la línea de órdenes de `psql`: todo por `\getenv`.
  `15_provision_db.ps1` y todo el runbook ponen las opciones delante; `-X`; exige `TOTAL_PWD`.
- **`apply_grants`**: total ausente = aviso y SUCCESS (D2); veto de `raw` tras las concesiones, sin
  GRANT al total; FAILED si lee lo vetado; R2/R3 sin conexión. F-135 igual: sus tests solo ganan dos
  campos en el settings falso, sin tocar aserciones, y el mensaje del estándar sale idéntico.
- **Diccionario v50**: el título de la regla dice cuál usar; manda `contabilidad` por defecto, prohíbe
  rodear el `permission denied`, cita `incompleto`, `num_apuntes_restringidos` y
  `apuntes_restringidos_mes`, y no va a lo restringido sin petición expresa de personal. Las tres fichas
  EMPIEZAN por «ACCESO RESTRINGIDO» y la del esquema nombra el login total. **«Correo de Juan Romero»
  en `motivo`: aceptable**: es la procedencia de la decisión de F-135, ya publicada en la v49, y no dice
  quién tiene el perfil total, que es lo que R32 protege (el test que veta a los tres pasa).
- **Runbook §12**: el resto de pasos son seguibles en PS 5.1. Cada `set` lleva `-o none`, cada `show`
  está asignado y las líneas miden ≤ 100. P9 ordena en PowerShell (`ConvertFrom-Json` + `Sort-Object`),
  y P3 compara las dos copias y mide 64 (lo que además caza un `\r` colado). **Fallan P12 y la §4**:
  cambios 1 y 2.

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

## Cambios requeridos

1. **`docs/runbook_postgres_azure.md` §12 P12 (≈ l. 670)**, y lo mismo en `progress/impl_F-136.md` §5,
   punto 3. El runbook escribe `az containerapp job start ... --command "python" --args
   "main.py,check-pg"` sin `--image`. Con la CLI de este puesto eso **falla** con «must have an 'Image'
   property» (medido el 2026-10-02 en este proyecto: memoria «job puntual sin ingesta, con --yaml»). Y una
   CLI que ignore los overrides sin `--image` haría algo peor: lanzaría el comando por defecto del job, la
   nocturna completa con ingesta, en pleno día. Design §6 P12 y D14 mandan el patrón **`--yaml`**. Hay que
   reescribir P12 con él, en PS 5.1 y en líneas ≤ 100: `job show --query properties.template -o json`
   → `ConvertFrom-Json` → cambiar solo `containers[0].command`/`args` → fichero sin BOM
   (`[IO.File]::WriteAllText`) → `job start --yaml <fichero> -o none` → borrar el fichero (solo lleva
   `secretRef`, nunca valores). Y un test en `r25_*`/`r22_*` que falle si P12 usa `--command` sin `--yaml`.
2. **`docs/runbook_postgres_azure.md` §4 (l. 130)**: lee `pg-password-total` de `kv-mcp-bbdd-dev`,
   pero la §4 no lo crea, ni tampoco la copia `pg-password` del estándar. En una provisión desde cero,
   `TOTAL_PWD` llegaría vacía y `15_provision_db.ps1 -Ejecutar` pararía. Dos salidas: generar y guardar
   esos dos secretos en la propia §4 (con `-o none` y el mismo valor del estándar en los dos vaults), o
   quitar esa línea y remitir de forma explícita a §12 P2-P3 para todo lo del vault del MCP.

## Recomendaciones (no bloquean)

- P3: `-cne` en vez de `-ne` (PowerShell compara sin mayúsculas). P10: el `CREATE TABLE` negativo entre
  `-c "BEGIN"` y `-c "ROLLBACK"`. P0: mirar en lectura si carga `pgaudit` (`shared_preload_libraries`).
- P6/P12: una referencia a Key Vault sin versión puede tardar del orden de 30 min, no «un par de minutos».
- Para otra feature: `infra/README.md` l. 313 y 322 usan el mismo `job start --command` sin `--yaml`, y
  `15_provision_db.ps1` no mira `$LASTEXITCODE` tras `01_create_database.sql`.

## Automejora (propuesta, no aplicada)

C4 podría exigir que todo `az ... start/update` de un procedimiento MANUAL nuevo copie un patrón ya usado
con éxito en el repositorio: los tests textuales miran la forma (`-o none`, longitud), no que funcione.
