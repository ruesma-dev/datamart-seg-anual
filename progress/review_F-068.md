<!-- progress/review_F-068.md -->
Revisión completa (pasada 1) · rango `120d327..7d7c0f8` · árbol en `96bb7b9`

# F-068 · Review

## Veredicto: CHANGES_REQUESTED

**No es un rechazo del enfoque.** El mecanismo es correcto, la campaña de
mutación es honesta y reproducible, y la revocación está verificada en
producción. Bloquea **un agujero real en la segunda mitad del mecanismo**
(cambio 1), que se desactiva sola justo en el escenario para el que se diseñó y
no la cubre ningún test. Los demás cambios son pequeños.

**Nivel de rigor: `critico`** (declarado en la ficha). Exige C1–C5 + tests
trazables + fase RED + cobertura ≥ 80 % + **cero supervivientes** en mutación +
verificaciones MANUAL listadas.

## Checkpoints

- **C1 [x]** — `bash harness/init.sh` sobre `96bb7b9`: **exit 0**, `3961 passed,
  159 skipped` en 450,8 s, `PUERTA COBERTURA 93.6 % de 841 líneas (787/841, umbral
  80 %, nivel critico)`. Existen los siete ficheros del arnés.
- **C2 [ ]** — La rama en curso es `feature/F-066-ingesta-raw-pendientes` y la
  ficha declara `branch: feature/F-068-mcp-datos-personales-raw`, **que no existe**
  (`git branch -a`). Compartir rama es defendible —van en la misma imagen—, pero
  entonces la ficha miente. Una feature `in_progress` ✓.
- **C3 [x]** — Hexagonal respetada: la lista en `config/settings.py`, el SQL puro
  en `grants.py` (sin conexión), el I/O en `postgres_client.py`, la orquestación
  en `application/steps/`. Primera línea con la ruta en los cinco ficheros. Sin
  `print()`, sin secretos, sin dependencias nuevas. Identificadores con
  `sql.Identifier`, con test antiinyección (`r5`).
- **C3 bis N/A** — justificado: el diff no toca nada bajo `docs/referencia/`, así que no hay documento de fuera que barrer.
- **C4 [x]** — Trazabilidad abajo. Los 18 tests son puros (función pura, un
  `_ClienteFalso` y un `PostgresClient.__new__` con `connection` sustituida): ni
  red ni BBDD. Doble contrastado con el original: `apply_readonly_grants`
  (línea 1262) y `role_exists` (1250) existen con la misma firma. Verificaciones
  MANUAL en `current.md` 31-42, con puntero al SQL exacto de `impl_F-068.md`.
- **C5 [x]** — `tasks.md` N/A por `sdd: false`; los tres commits de código usan
  `F-068 Tn: ...`. Sin artefactos sospechosos. `features.json` dice el estado real.

## C4 bis · verificación del rigor

- **Fase RED [x]** — traza real pegada (`23 failed`, más `TypeError: ... keyword argument 'excluded_tables'` e `ImportError: ... DEFAULT_EXCLUDED_TABLES`).
- **Mutación [x], recalculada por mí** (cobertura: puerta en `[OK]`, 93,6 %) — `harness.alcance` sobre
  `120d327..7d7c0f8` da **49/18/78/31 = 176 líneas**, idéntico al informe;
  `generar_mutantes` (cálculo puro) da **8 mutantes**, los mismos, mismo operador
  y mismo texto original→mutado. **Campaña NO reejecutada: 5.937,6 s**, muy por
  encima del umbral de 60 s.
- **RM1 [x]** — SHA medido `31d5085`; hasta `7d7c0f8` solo cambian dos ficheros
  de `progress/`. Lo posterior (F-066, F-025) toca `postgres_client.py` pero
  **no** `apply_readonly_grants`.
- **RM2 [x]** — base 256-263 s/worker, media 742,2 s, 8 × 742,2 = 5.937,6 s:
  coherente. Salió **más lenta**, no más rápida: contraria a la del fraude.
  **RM3 / RM5 N/A**: no se declara ningún mutante equivalente.
- **RM4 [x], reproducidos 5 de 8 sobre una COPIA en scratchpad** (`git archive
  7d7c0f8`, nunca el árbol real; base `36 passed`). Los cuatro timeouts «matados a
  mano» y el superviviente falso de la 1.ª pasada dan **exactamente** los números
  del informe: `grants.py:47 partes[0]→partes[1]` 7 failed; `partes[1]→partes[2]`
  10 failed; `grants.py:42 [not]` **13 failed**; `client:1119 and→or` y `[not]`,
  1 failed cada uno.
- **RM6 [x]** — nada se mató quitando guardas: la entrega **añade** (`partir_tabla_cualificada` revienta ante una entrada mal escrita).

## Trazabilidad `acceptance` → test

| Criterio | Cubierto por |
|---|---|
| 1 · `raw.emp` en Azure y el rol la lee | hecho histórico verificado por el líder el 06-09; sin test, no es código |
| 2 · queda escrito quién decide y por qué | ficha, `settings.py`, `02_roles.sql`, `ARCHITECTURE.md`; test `r8_esta_escrito_que_es_temporal` |
| 3 · vive en `02_roles.sql` y `apply_grants_step.py`, con test, y la nocturna no lo devuelve | `r1`(×4) `r2`(×2) `r3` `r4` `r5`(×3) `r6`(×3) `r7`(×2) `r8`(×2) |
| 4 · los dos documentos de `azure-apps` | commit `9bc3944`: lo esencial está; quedan dos restos (cambio 4) |

## Las cinco preguntas del encargo

1. **¿Ventana entre GRANT y REVOKE en la nocturna? NO.** `_connect` abre con
   `autocommit=False` y `connection()` hace un solo `commit`: las 20+ sentencias
   van en **una transacción** y un fallo a mitad hace `rollback`. Ventana sí la
   hay en `02_roles.sql` — cambio 2.
2. **`ALTER DEFAULT PRIVILEGES`: razonamiento correcto, implementación con agujero.** Cambio 1.
3. **Los dos concedentes: correcto y bien resuelto.** Un `REVOKE` solo anula lo
   del mismo concedente. El 5 bis emite dos bloques: uno como administrador (el
   punto 4 dejó `RESET ROLE`) y otro tras `SET ROLE sigrid_dm_etl`, con su
   `RESET ROLE`. Y la nocturna concede y revoca siempre como `sigrid_dm_etl`:
   `_connect` emite `SET ROLE` como primera sentencia de cada sesión.
4. **`raw.res` entra con razón.** Su ficha, escrita por F-066 con el dato
   delante, declara NIF en `cif` (626 filas) y credenciales `logacc`, `ideacc`,
   `ipacc`, `recema`, contrastado con `azure-apps/sigrid_tablas.md`.
5. **Temporalidad: bien cubierta.** `settings.py` (banner + cita literal),
   `grants.py`, `apply_grants_step.py`, `02_roles.sql`, `ARCHITECTURE.md`, el
   runbook, `.env.example` y las dos fichas del diccionario, que son lo que lee
   el agente por `_meta`. Nadie lo confundirá con algo permanente.

## Cambios requeridos

1. **(BLOQUEANTE) El `ALTER DEFAULT PRIVILEGES` se desactiva solo si la tabla
   excluida no existe.** `postgres_client.py:1296-1301` saca de `excluidas` la
   tabla inexistente y `grants.py:88-90` deriva `esquemas_con_exclusion` de esa
   lista ya filtrada, así que el esquema **vuelve a emitir su `GRANT`**.
   Demostrado con el código de la entrega (`table_exists` → False): emite
   `ALTER DEFAULT PRIVILEGES ... IN SCHEMA "raw" GRANT SELECT ON TABLES TO
   "mcp_sigrid_dm_ro"`. Es justo el caso que el informe dice cubrir («basta un
   DROP manual o una tabla de personal nueva»): tras un `DROP` la nocturna repone
   la regla del catálogo y la siguiente `raw.emp` **nace legible**; con `main.py
   ingest` suelto —que no corre `apply_grants`, y es como F-066 la ingirió desde el
   puesto— sigue legible hasta la nocturna. La regla de catálogo no necesita que la
   tabla exista: el filtro solo hace falta para el `REVOKE ... ON TABLE`. Separar
   las dos listas y **añadir el test que falta**.
2. **`infra/sql/02_roles.sql`: ventana entre el punto 5 y el 5 bis.** `psql` sin
   `BEGIN` explícito confirma cada `DO` por separado: entre el `GRANT` del 5 y el
   primer `REVOKE` del 5 bis las tablas quedan legibles, y si el script muere ahí
   con `ON_ERROR_STOP`, legibles **y commiteadas**. Envolverlos en un `BEGIN …
   COMMIT`, o decir qué hacer si se corta.
3. **`02_roles.sql`, 5 bis: `raw` está escrito a mano** en el `ALTER DEFAULT PRIVILEGES`, mientras `grants.py` lo deriva. Con una exclusión de otro esquema por `PG_EXCLUDED_TABLES`, la nocturna lo resuelve y este fichero no.
4. **`azure-apps` (lo cierra el líder), dos restos que contradicen lo nuevo:**
   `mcp_bbdd.md` §6.3 (466-473) habla de los `REVOKE` en futuro y «en el backlog»
   cuando ya se aplicaron; `red_postgresql_compartido.md:175` dice que el rol «ve
   todos los esquemas», sin excepción ni puntero.
5. **`config/diccionario/raw.yaml:1395`**: «el rol **alcanza** `raw` entero, así que **hasta esa fecha** …» mezcla presente y pasado. `alcanzaba`. Va publicado en `_meta` y lo lee el agente.
6. **Alinear `branch` en `harness/features.json`** con la rama real, o crear la
   de F-068 (C2).

## Observaciones no bloqueantes

- **O1** — `test_f068_r8_esta_escrito_que_es_temporal` vigila 3 de los 9 sitios
  donde está escrita la temporalidad; los otros seis pueden envejecer sin aviso.
- **O2** — `00_global.yaml` trae la nota de F-068 como comentario YAML (no llega
  a `_meta.v_diccionario`) y dice «version 15» con el fichero ya en `version: 16`.
  **No lo cuento contra F-068**: el salto a 16 lo hizo una feature posterior.
- **O3** — `current.md` 31-42 sigue dando por pendientes la revocación y `azure-apps`, que el líder ya ejecutó. Territorio del líder.
- **O4** — `a961a9f` y `ae7e3de` arrastraron ficheros ajenos (`specs/F-070/`,
  `features.json`, `BACKLOG.md`): confesado en `current.md`, ensucia el diff.

## Automejora (propuesta, no aplicada)

`CHECKPOINTS.md`, C4 bis: la regla del coste por mutante solo caza campañas
**demasiado rápidas**. La de F-068 es 11 veces su línea base y eso tampoco se
explica solo con la carga. Propongo anotar en el review, con su explicación, todo
coste **por encima de 10 × la línea base**: no como rechazo, sino para que no se
normalice un dato que nadie entiende.
