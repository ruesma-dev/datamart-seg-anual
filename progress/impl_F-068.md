<!-- progress/impl_F-068.md -->
# F-068 · El MCP deja de leer `raw.emp` y `raw.res` (y la nocturna no se lo devuelve)

Implementación del 2026-09-07. Feature `sdd: false`, **rigor `critico`**: se
trabaja contra los cuatro `acceptance` de la ficha, no contra una spec.

**La decisión ya venía tomada por el humano**: la salida (b) de la ficha,
revocar. Sus palabras: «de momento quita el permiso. Cuando pongamos límites o
guardarraíles por usuario, habrá que volver a ponerlo para algunos usuarios».
**La revocación es TEMPORAL y su reversión ya está decidida**, condicionada a
que el MCP tenga control por usuario. Está escrito, con esas palabras, en los
seis sitios donde alguien puede tropezarse con ella dentro de seis meses:
`settings.py`, `grants.py`, `apply_grants_step.py`, `02_roles.sql`,
`ARCHITECTURE.md` y las fichas del diccionario. Y hay test que lo comprueba
(`test_f068_r8_esta_escrito_que_es_temporal`).

## Lo que cambió

| Fichero | Qué |
|---|---|
| `config/settings.py` | `DEFAULT_EXCLUDED_TABLES = "raw.emp,raw.res"` + campo `excluded_tables` (`PG_EXCLUDED_TABLES`) + propiedad `excluded_table_list` |
| `etl_sigrid/infrastructure/postgres/grants.py` | `build_readonly_grant_statements(..., excluded_tables=())` y `partir_tabla_cualificada()` |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | `apply_readonly_grants(..., excluded_tables=())`, filtrando por existencia de la tabla |
| `etl_sigrid/application/steps/apply_grants_step.py` | pasa la lista al cliente y la deja en `metadata["tablas_excluidas"]` |
| `infra/sql/02_roles.sql` | punto «5 bis»: revoca las dos tablas y quita el `ALTER DEFAULT PRIVILEGES` de `raw`; consulta de verificación en el punto 6 |
| `.env.example` | documenta `PG_EXCLUDED_TABLES` |
| `config/diccionario/raw.yaml`, `00_global.yaml` | fichas de `emp` y `res` reescritas; diccionario a versión 15 |
| `docs/ARCHITECTURE.md`, `docs/runbook_postgres_azure.md` | decían lo contrario; ahora dicen qué ve y qué no ve el MCP |
| `tests/test_f068_exclusion_lectura_mcp.py` | **nuevo**, 23 tests |
| `tests/test_f005_grants.py` | doble de test y barrido de seguridad adaptados |
| `.gitignore` | ignora `.claude/worktrees/` (ver «Lo que estorbó») |

## Las cuatro decisiones de diseño

**1. La lista vive en `config/settings.py`.** Simétrica con
`DEFAULT_CONSUMPTION_SCHEMAS`, que ya vive ahí y ya es parametrizable por
entorno; y esa simetría es la que resuelve el día de la reversión: el humano
vacía `PG_EXCLUDED_TABLES` **sin tocar código ni desplegar imagen**. Y cuando
mañana aparezca otra tabla con datos personales, se añade una entrada a una
lista declarada tabla a tabla.

**2. Conceder y revocar después, en la misma tanda.** `GRANT SELECT ON ALL
TABLES IN SCHEMA raw` no sabe saltarse una tabla: no existe la forma de
conceder el esquema con una excepción. Así que el paso concede el esquema
entero y, **al final del todo**, emite un `REVOKE ALL PRIVILEGES ON TABLE` por
cada tabla excluida. El orden es lo único que hace que funcione, y por eso
tiene test propio (`test_f068_r1_el_revoke_va_despues_del_grant_del_esquema`):
al revés, el GRANT pisaría el REVOKE y las sentencias seguirían pareciendo
correctas leídas por separado. Es también por lo que el mecanismo **no puede
ser una revocación manual**: `apply_grants` corre cada noche, así que un
`REVOKE` suelto contra la base duraría hasta la nocturna siguiente.

**3. El `ALTER DEFAULT PRIVILEGES` sí aplicaba, y había que resolverlo.** Es una
regla del catálogo (`pg_default_acl`): mientras esté puesta, cualquier tabla que
**nazca** en `raw` es legible por el MCP sin que nadie ejecute un GRANT. Hoy la
ingesta usa `CREATE TABLE IF NOT EXISTS` + `TRUNCATE`, así que `raw.emp` no se
recrea sola, pero basta un `DROP` manual o una tabla de personal nueva. **Dejar
de emitir la regla no la borra**: hay que emitir su `REVOKE`. Por eso el esquema
con exclusiones cambia su `ALTER DEFAULT PRIVILEGES` de `GRANT ... TO` a
`REVOKE ... FROM`, y los demás conservan el suyo —`mart`, `cierre`, `compras` y
`retenciones` recrean vistas y sin él nacerían ilegibles (test `r3`).

**4. `raw.res` entra también, contra lo que decía la ficha.** La ficha afirmaba
«`raw.res` NO trae columnas de ese tipo». **Es falso, y se comprobó antes de
dejarla dentro**: su ficha del diccionario, escrita por F-066 con el dato
delante, dice que trae **el NIF de la persona en `cif`, informado en 626 filas,
y las credenciales de acceso a Sigrid**. Contrastado con el bloque `res` de
`azure-apps/sigrid_tablas.md`: `cif` («CIF/NIF»), `logacc` («Login de Acceso
email»), `ideacc`, `ipacc` y `recema`. Y coincide con la letra de la salida (b),
que hablaba de «`raw.emp` y `raw.res`».

### Un hallazgo que casi deja el agujero abierto: hay DOS concedentes

En PostgreSQL **un `REVOKE` solo quita la concesión hecha por el mismo
concedente**: la ACL guarda una entrada por cada uno (`mcp=r/admin` y
`mcp=r/sigrid_dm_etl` son dos entradas distintas). Y aquí hay dos concedentes
reales: el punto 5 de `02_roles.sql` concede **como el administrador** que
ejecuta el fichero, mientras que la nocturna concede como `sigrid_dm_etl` (que
es además el propietario, y por tanto el concedente de lo que nace por
privilegio por defecto). Revocar con uno solo deja la tabla legible **sin
ningún error a la vista**: PostgreSQL emite un `NOTICE` y sigue.

Consecuencia: `02_roles.sql` revoca dos veces, una bajo cada concedente, y el
SQL manual de abajo hace lo mismo. Sobre estas dos tablas lo que existe hoy
debería ser solo la entrada de `sigrid_dm_etl` —nacieron el 2026-09-06, mucho
después de que corriera `02_roles.sql`—, pero la verificación (b) está puesta
para no fiarse de ese razonamiento.

## Fase RED (obligatoria en rigor `critico`)

Los 23 tests se escribieron **antes** que el código. Traza real del fallo:

```
$ python -m pytest tests/test_f068_exclusion_lectura_mcp.py -q --no-header -p no:cacheprovider
...
23 failed, 2 warnings in 1.11s
```

Dos representativos, con `--tb=short` (los 21 restantes fallan con uno de
estos dos errores o con el `AssertionError` del texto que aún no existía):

```
$ python -m pytest "tests/test_f068_exclusion_lectura_mcp.py::test_f068_r1_la_tabla_excluida_recibe_su_revoke" \
    "tests/test_f068_exclusion_lectura_mcp.py::test_f068_r6_el_defecto_excluye_emp_y_res" \
    -q --no-header -p no:cacheprovider --tb=short

_______________ test_f068_r1_la_tabla_excluida_recibe_su_revoke _______________
tests\test_f068_exclusion_lectura_mcp.py:71: in test_f068_r1_la_tabla_excluida_recibe_su_revoke
    sentencias = build_readonly_grant_statements(
E   TypeError: build_readonly_grant_statements() got an unexpected keyword argument 'excluded_tables'
__________________ test_f068_r6_el_defecto_excluye_emp_y_res __________________
tests\test_f068_exclusion_lectura_mcp.py:262: in test_f068_r6_el_defecto_excluye_emp_y_res
    from config.settings import DEFAULT_EXCLUDED_TABLES
E   ImportError: cannot import name 'DEFAULT_EXCLUDED_TABLES' from 'config.settings'
=========================== short test summary info ===========================
3 failed in 0.93s
```

(y `test_f068_r8_esta_escrito_que_es_temporal` fallaba con
`AssertionError: config/settings.py no dice que la exclusión es temporal`)

Tras el código: `36 passed` (los 23 de F-068 más los 13 de F-005, que se tocan).

## LO QUE TIENE QUE EJECUTAR EL LÍDER (yo no lo he hecho, a propósito)

**No he lanzado ni un `REVOKE`, ni un `GRANT`, ni un `az`, ni un `.ps1`.**
Mientras esto no se ejecute, `raw.emp` sigue siendo legible por el rol.

**Vía preferida** (una orden, y usa exactamente el código de esta entrega):

```
python main.py apply-grants        # con el perfil Azure en .env
```

**Vía manual**, con `psql` conectado a `sigrid_dm` **con el administrador del
servidor**:

```sql
\set ON_ERROR_STOP on

-- 1) La concesión hecha por el ADMINISTRADOR (la del punto 5 de 02_roles.sql).
REVOKE ALL PRIVILEGES ON TABLE raw.emp FROM mcp_sigrid_dm_ro;
REVOKE ALL PRIVILEGES ON TABLE raw.res FROM mcp_sigrid_dm_ro;

-- 2) Y la hecha por el PROPIETARIO, que es la que de verdad existe sobre estas
--    dos: nacieron con el privilegio por defecto de sigrid_dm_etl.
SET ROLE sigrid_dm_etl;
REVOKE ALL PRIVILEGES ON TABLE raw.emp FROM mcp_sigrid_dm_ro;
REVOKE ALL PRIVILEGES ON TABLE raw.res FROM mcp_sigrid_dm_ro;

-- 3) La regla que devolvería el permiso sola a cualquier tabla recreada.
ALTER DEFAULT PRIVILEGES FOR ROLE sigrid_dm_etl IN SCHEMA raw
    REVOKE SELECT ON TABLES FROM mcp_sigrid_dm_ro;
RESET ROLE;
```

### Cómo verificar que el permiso ya no está

```sql
-- (a) CERO FILAS es el resultado correcto.
SELECT table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'mcp_sigrid_dm_ro'
  AND table_schema = 'raw' AND table_name IN ('emp', 'res');

-- (b) Si (a) devuelve algo, aquí se ve QUIÉN concedió lo que queda: no debe
--     quedar ninguna entrada 'mcp_sigrid_dm_ro=r/...'.
SELECT c.relname, c.relacl
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'raw' AND c.relname IN ('emp', 'res');

-- (c) La regla de privilegios por defecto de raw ya no nombra al rol.
SELECT pg_get_userbyid(d.defaclrole) AS creador, d.defaclacl
FROM pg_default_acl d JOIN pg_namespace n ON n.oid = d.defaclnamespace
WHERE n.nspname = 'raw';
```

**La prueba de verdad**, conectando como `mcp_sigrid_dm_ro`: `SELECT 1 FROM
raw.emp LIMIT 1;` debe responder `ERROR: permission denied for table emp`.

**Y después de la primera nocturna con la imagen nueva, repetir (a).** Ahí es
donde se demuestra lo único que esta feature promete de verdad: que la carga no
devuelve el permiso.

## Lo que queda fuera y lo que falta

- **`azure-apps/mcp_bbdd.md` y `red_postgresql_compartido.md` NO se han
  tocado**: cruzan la frontera del proyecto y los actualiza el líder. Es el 4.º
  criterio de aceptación de la ficha y es lo único de ella que sigue abierto.
- **Matiz para esos documentos**: el servidor MCP tiene además su propia lista
  de esquemas y `raw` **no** está en ella (comprobado: `consultar()` contra
  `raw.res` responde «El esquema 'raw' está fuera del ámbito autorizado»). O
  sea, la exposición iba **por la credencial**, que cualquier cliente puede
  usar contra la base, no por la superficie de consulta de este MCP.
- **No se ha desplegado nada.** F-066 y F-068 van juntas en la misma imagen. El
  `.env` no se ha tocado y contra la base solo hubo lecturas.

**Lo que estorbó**: la campaña de mutación se negó a arrancar dos veces por
tener el árbol sucio —la reordenación del backlog del líder, commiteada aparte,
y un `.claude/worktrees/` olvidado de otro subagente, ahora en `.gitignore`.

## Mutación: dos pasadas, 0 supervivientes

La 1.ª campaña dio **1 superviviente** (`grants.py:42 [not]`) y la 2.ª lo mató,
más 4 timeouts que la 1.ª había matado. Como un timeout no es un veredicto,
**los 8 mutantes se han matado además a mano**, con su salida pegada. Aquel
superviviente era un **veredicto falso**: con esa mutación
`partir_tabla_cualificada` revienta ante una entrada válida, y reproducirla da
`13 failed, 23 passed`. **Todo el análisis, en `progress/mutacion_F-068.md`**,
sin nada en PENDIENTE.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados y resultado | **3.895 passed, 159 skipped** en `bash harness/init.sh` (0 fallos). De ellos, **23 nuevos** de F-068 |
| Tiempo de la suite | **601,50 s (10 min 01 s)** en la pasada final; 435,70 s en la anterior |
| Cobertura de las líneas cambiadas | **100,0 % — 36/36** líneas (`python -m harness.cobertura --base 120d327`), umbral 80 %, nivel `critico`. La puerta de `init.sh` mide la rama entera y da 92,8 % de 752 líneas, porque ahí van también las de F-066 |
| Mutantes generados y supervivientes | **8 generados, 8 evaluados, 0 supervivientes**. Hicieron falta dos pasadas y los 8 se mataron además a mano: el análisis completo, en `progress/mutacion_F-068.md` |
| `bash harness/init.sh` | **ENTORNO LISTO**, exit 0. La puerta de tamaño de `init.sh` mide F-066 (va por el nombre de la rama); la de F-068 se midió aparte: `python -m harness.tamano --feature F-068` -> **impl 220/220** |
