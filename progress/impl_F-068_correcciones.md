<!-- progress/impl_F-068_correcciones.md -->
# F-068 · Correcciones del review (CHANGES_REQUESTED)

Origen: `progress/review_F-068.md`. Rama `feature/F-066-ingesta-raw-pendientes`
(compartida con F-066, ver punto 6). Rigor `critico`, `sdd: false`.
Puntos atendidos: **1, 2, 3, 5 y 6**. El **4 es del líder** (dos restos en
`azure-apps`, fuera de este repositorio).

## Qué cambió, por punto

### 1 · (BLOQUEANTE) La regla del catálogo ya no depende de que la tabla exista

El agujero, tal y como lo describió el reviewer: `postgres_client.py` sacaba de
la lista de exclusión las tablas inexistentes y `grants.py` derivaba de **esa
lista ya filtrada** qué esquemas cambian su `ALTER DEFAULT PRIVILEGES`. Con
`raw.emp` ausente, el esquema volvía a emitir su `GRANT` por defecto: tras un
`DROP` la nocturna reponía la regla del catálogo y la siguiente `raw.emp` nacía
legible. Justo el escenario para el que se diseñó la segunda mitad.

El arreglo son **dos listas separadas**, porque son dos preguntas distintas:

| Efecto | De qué lista sale | Por qué |
|---|---|---|
| `ALTER DEFAULT PRIVILEGES ... REVOKE` (catálogo) | lo **declarado** | se declara sobre el ESQUEMA; es lo que protege a la tabla que aún no ha nacido |
| `REVOKE ALL PRIVILEGES ON TABLE` | lo declarado **que existe hoy** | sobre una tabla ausente da error y tumba el paso |

- `grants.py`: `build_readonly_grant_statements` acepta `missing_tables`.
  `esquemas_con_exclusion` sigue saliendo de `aplicables` (lo declarado dentro
  de los esquemas concedidos) y el bucle final recorre `revocables`
  (`aplicables` menos `missing_tables`).
- `postgres_client.py`: `apply_readonly_grants` pasa la lista **entera** en
  `excluded_tables` y las ausentes en `missing_tables`, en vez de filtrarlas
  antes. El aviso `grants_tablas_excluidas_inexistentes` se conserva y el log
  de cierre añade `excluded_tables_missing`.

El **defecto es el seguro**: `missing_tables=()` revoca todo lo declarado.
Un llamante que se olvide del parámetro falla ruidosamente contra la BBDD; al
revés dejaría la tabla legible en silencio, que es el desenlace que no se
puede permitir.

**Cuatro tests nuevos (R9)**, uno de ellos de extremo a extremo con el
`PostgresClient` real (`table_exists` → False para todo), que es el que habría
cazado esto: comprueba que la nocturna **no** emite el `GRANT` por defecto de
`raw` y que no intenta revocar sobre tablas ausentes.

### 2 · `02_roles.sql`: la ventana entre el punto 5 y el 5 bis

Envueltos en `BEGIN; ... COMMIT;`. GRANT, REVOKE y ALTER DEFAULT PRIVILEGES son
transaccionales en PostgreSQL, así que las dos mitades entran juntas o no entra
ninguna. El comentario deja escrito **qué hacer si se corta**: el servidor hace
rollback, el rol se queda como estaba y se vuelve a ejecutar el fichero entero,
que es reejecutable; lo que no se puede es dar por buena una ejecución cortada.

### 3 · `02_roles.sql`: el esquema, derivado y no escrito a mano

El `ALTER DEFAULT PRIVILEGES` del 5 bis sale ahora de la misma lista de tablas
excluidas (`split_part(excluida, '.', 1)` sobre el `unnest` del array), igual
que hace `grants.py`. Con `to_regnamespace` por si el esquema no existiera. El
alias **no** puede llamarse `objeto`: plpgsql daría «column reference is
ambiguous» contra la variable del bloque, y está escrito ahí mismo.

### 5 · `config/diccionario/raw.yaml`

«El rol `mcp_sigrid_dm_ro` **alcanza** `raw` entero, así que **hasta esa
fecha**…» → «**alcanzaba** … ; desde entonces YA NO la lee». Se publica en
`_meta` y lo lee el agente de IA: el presente le hacía creer que el permiso
sigue vivo.

### 6 · `harness/features.json` (checkpoint C2)

`branch` pasa de `feature/F-068-mcp-datos-personales-raw` —que no existe— a
`feature/F-066-ingesta-raw-pendientes`, la real. La descripción de la ficha
explica por qué se comparte rama (nace de esa ingesta y viajan en la misma
imagen). `BACKLOG.md` regenerado con `harness/backlog.py`.

## Ficheros tocados

| Fichero | Qué |
|---|---|
| `etl_sigrid/infrastructure/postgres/grants.py` | `missing_tables`; las dos listas separadas |
| `etl_sigrid/infrastructure/postgres/postgres_client.py` | pasa lo declarado y lo ausente por separado; log |
| `infra/sql/02_roles.sql` | transacción 5 + 5 bis; esquema derivado de la lista |
| `tests/test_f068_exclusion_lectura_mcp.py` | 6 tests nuevos (R9 ×4, R10 ×2) |
| `config/diccionario/raw.yaml` | el tiempo verbal de la ficha de `emp` |
| `harness/features.json`, `BACKLOG.md` | la rama real de F-068 |
| `progress/current.md` | estado de la sesión |

Commits: `e78e1e5` (T1, el bloqueante), `f918438` (T2, el SQL), `38e170c`
(T3, ficha y rama).

## Fase RED (obligatoria, nivel `critico`)

Comando: `python -m pytest tests/test_f068_exclusion_lectura_mcp.py -q -k "r9 or r10"`
sobre el árbol **anterior** al arreglo. Traza real, recortada a lo que no se
repite (`5 failed, 1 passed`):

```
FF.FFF                                                                   [100%]
________ test_f068_r9_el_catalogo_se_revoca_aunque_la_tabla_no_exista _________
>       sentencias = build_readonly_grant_statements(
            ROL, DUENO, TODOS_LOS_ESQUEMAS,
            excluded_tables=["raw.emp", "raw.res"],
            missing_tables=["raw.emp", "raw.res"],
        )
E       TypeError: build_readonly_grant_statements() got an unexpected keyword
        argument 'missing_tables'

___________ test_f068_r9_el_cliente_mantiene_el_catalogo_tras_un_drop _________
>       assert revoke_catalogo in ejecutadas
E       assert 'ALTER DEFAULT PRIVILEGES FOR ROLE "sigrid_dm_etl" IN SCHEMA
        "raw" REVOKE SELECT ON TABLES FROM "mcp_sigrid_dm_ro"' in [...]
---------------------------- Captured stdout call -----------------------------
2026-09-08 22:16:13 [warning ] grants_tablas_excluidas_inexistentes tables=['raw.emp', 'raw.res']
2026-09-08 22:16:13 [info    ] grants_aplicados excluded_tables=[] role=mcp_sigrid_dm_ro schemas=['raw', 'mart'] statements=7

__________ test_f068_r10_el_grant_y_su_revoke_van_en_una_transaccion __________
>       apertura = sql.index("\nBEGIN;")
E       ValueError: substring not found

________ test_f068_r10_el_esquema_del_catalogo_no_esta_escrito_a_mano _________
E       AssertionError: el esquema del ALTER DEFAULT PRIVILEGES del punto 5 bis
        sigue escrito a mano; hay que derivarlo de la lista de tablas excluidas

FAILED ...::test_f068_r9_el_catalogo_se_revoca_aunque_la_tabla_no_exista
FAILED ...::test_f068_r9_la_tabla_ausente_no_recibe_revoke_de_tabla
FAILED ...::test_f068_r9_el_cliente_mantiene_el_catalogo_tras_un_drop
FAILED ...::test_f068_r10_el_grant_y_su_revoke_van_en_una_transaccion
FAILED ...::test_f068_r10_el_esquema_del_catalogo_no_esta_escrito_a_mano
5 failed, 1 passed, 23 deselected in 0.60s
```

`excluded_tables=[]` en el log es el agujero en una línea: la lista llegaba
vacía al generador y `raw` recuperaba su `GRANT` por defecto. El único que
pasaba en rojo es `r9_sin_lista_de_ausentes_se_revoca_todo_lo_declarado`, que
es un guardarraíl de no-regresión y ya se cumplía.

Traza íntegra guardada durante la sesión; reproducible con el comando de
arriba sobre `e2e2ad8`.

## Verificaciones MANUAL pendientes

1. **`infra/sql/02_roles.sql` no lo ejecuta ningún test**: solo se comprueba su
   texto. Los dos cambios (transacción y bloque `FOR ... IN SELECT`) solo los
   valida `psql`. Antes de volver a provisionar un rol desde cero, ejecutarlo
   contra una base de prueba con `-v ON_ERROR_STOP=1`.
2. **Nada se ha ejecutado contra Azure**: ni un `GRANT`, ni un `REVOKE`, ni
   `az`. La revocación viva en producción es la que ya aplicó el líder; estos
   cambios solo afectan a lo que hará la **próxima** nocturna y a la próxima
   provisión desde cero.

## Evidencias

| Evidencia | Valor |
|---|---|
| Tests ejecutados (suite completa, `harness/init.sh`) | **3.967 passed, 159 skipped**, exit 0 |
| Cobertura de las líneas cambiadas | **93,6 %** (788/842, umbral 80 %, nivel `critico`) |
| Mutantes generados / supervivientes (campaña automática) | **0 / 0** — ver abajo |
| Mutantes manuales aplicados / supervivientes | **3 / 0** |
| Tiempo de la suite | **457,33 s** (0:07:37) |
| Subconjunto directo (`test_f068_*` + `test_f005_grants.py`) | 42 passed en 1,15 s |
| Cobertura de `grants.py` con solo esos dos ficheros | **100 %** (35/35 sentencias, `coverage report -m`) |

### Por qué la campaña automática da cero mutantes, medido

`harness.alcance` sobre `e2e2ad8..HEAD` (el diff de ESTA corrección) da **38
líneas de producción**: 24 en `grants.py` y 14 en `postgres_client.py`.
`generar_mutantes` sobre esas líneas devuelve **0 mutantes**, y el motivo está
en el propio mutador: `COMPARACIONES` (`harness/mutacion.py:165`) cubre `==`,
`!=`, `<`, `<=`, `>`, `>=`, `is`, `is not`, y **no cubre `in` / `not in`**. El
resto del diff son docstrings, comentarios y asignaciones sin operador mutable.
Lanzar la campaña habría sido cero supervivientes de cero mutantes: un número
verdadero que no dice nada.

### Mutación manual, en su lugar (sobre una COPIA, nunca el árbol real)

`git archive HEAD | tar -x` en el scratchpad; base del subconjunto **42
passed**. Tres mutantes escritos a mano sobre lo que el mutador no sabe
expresar, cada uno una forma real de reabrir el agujero:

| # | Mutante | Veredicto |
|---|---|---|
| M1 | `revocables = [par for par in aplicables if par not in ausentes]` → `revocables = list(aplicables)` | **muerto**, 3 failed (r7, r9×2) |
| M2 | `esquemas_con_exclusion` derivado de `revocables` (el agujero del review, reintroducido) | **muerto**, 2 failed (r9×2) |
| M3 | el cliente pasa `missing_tables=()` en vez de `sin_tabla` | **muerto**, 2 failed (r7, r9) |

Cero supervivientes, y por tanto nada que analizar. El veredicto se tomó con el
subconjunto de tests que cubre esas líneas, no con la suite entera: es un
criterio **más exigente** para declarar «muerto» (si lo mata el subconjunto, lo
mata la suite), y no se usa para declarar superviviente a nadie.

Comprobado al terminar: `python -m harness.mutacion --estado` → «Sin campaña de
mutación en curso», copia borrada y `git status` sin cambios de código.

### Ruff

`ruff check` sobre los tres ficheros tocados deja **un** aviso, `I001` en
`postgres_client.py`, que es **previo**: sale igual sobre la versión `7d7c0f8`
del fichero. Cero avisos nuevos.
