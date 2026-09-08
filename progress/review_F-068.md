<!-- progress/review_F-068.md -->
Revisión incremental desde `96bb7b9` (pasada 2) · rango `96bb7b9..f2fb04d`

# F-068 · Review

## Veredicto: APPROVED

Los seis puntos están cerrados. El bloqueante lo está **de verdad**: reproduje
el agujero sobre una copia y ahora muere. La exención de la campaña automática
de mutación es legítima, y la comprobé en vez de creérmela. **Rigor `critico`**:
C1–C5 + fase RED + cobertura ≥ 80 % + cero supervivientes + verificaciones
MANUAL. **Lo aprobado hasta `96bb7b9` queda dado por bueno**: el delta no cambia
firmas públicas ni mueve ficheros; sí amplía el alcance medido, y por eso lo
recalculé entero. **No cuento F-066.**

## Checkpoints

- **C1 [x]** — `bash harness/init.sh` sobre `f2fb04d`: **exit 0**, `3967 passed,
  159 skipped` en 417,04 s, `PUERTA COBERTURA 93.6 % (788/842, umbral 80 %,
  nivel critico)`. Clavado con lo que declara el informe.
- **C2 [x]** — punto 6 resuelto: la ficha declara
  `feature/F-066-ingesta-raw-pendientes`, que **existe y es la rama actual**, y
  dice por qué se comparte. Una feature `in_progress`: F-068.
- **C3 [x]** — el delta se queda en su capa: SQL puro en `grants.py` (sin
  conexión), el I/O en `postgres_client.py`, `02_roles.sql` en `infra/`. Sin
  `print()`, secretos ni dependencias nuevas. `ruff` deja **un** aviso, previo:
  idéntico contra la versión `96bb7b9` del fichero.
- **C3 bis N/A** — justificado: el delta no toca `docs/referencia/`.
- **C4 [x]** — trazabilidad abajo. Los seis tests nuevos son puros (función
  pura, `PostgresClient.__new__` con `connection`/`table_exists` sustituidos,
  texto del `.sql`): ni red ni BBDD. Verificado, 42 passed en 1,6 s.
- **C5 [x]** — `tasks.md` N/A por `sdd: false`; los siete commits usan
  `F-068 Tn: ...` y `features.json` dice el estado real.

## C4 bis · verificación del rigor

- **Fase RED [x]** — traza real pegada: `TypeError: ... unexpected keyword
  argument 'missing_tables'`, `ValueError: substring not found` del `BEGIN;` y
  el `assert ... in [...]` del catálogo, `5 failed, 1 passed`. El log de esa
  traza (`excluded_tables=[]`) **es el agujero en una línea**.
- **Cobertura [x]** — puerta en `[OK]`, 93,6 %. **Mutación [x]**, con exención
  razonada y verificada por mí (abajo). Cero supervivientes.
- **RM1 [x]** — `git log e78e1e5..HEAD --name-only` confirma que **ni
  `grants.py` ni `postgres_client.py` cambian después de T1**. Y da igual:
  reproduje los tres mutantes sobre `f2fb04d`, el HEAD de hoy.
- **RM2 N/A justificado** — no hay campaña automática que cronometrar (cero
  mutantes). **RM3 / RM5 N/A**: no se declara ningún equivalente.
- **RM4 [x], aplicado**: `git archive f2fb04d` a una **copia en el scratchpad**,
  nunca el árbol real; base 42 passed, copia borrada, `git status` sin código.
- **RM6 [x]** — no se mató nada quitando una guarda: lo retirado
  (`else: excluidas.append(...)`) **era** el defecto, y el filtro por existencia
  se conserva para el `REVOKE ... ON TABLE`. El invariante se comprueba en quien
  construye el dato: `apply_readonly_grants` calcula `sin_tabla`.

## La campaña de mutación: por qué acepto la exención

**El hueco es real y lo confirmé en el código**: `COMPARACIONES`
(`harness/mutacion.py:165`) trae `==`, `!=`, `<`, `<=`, `>`, `>=`, `is`,
`is not` y **no trae `ast.In` / `ast.NotIn`**. La única decisión del delta
(`par not in ausentes`) es justo eso. **Recálculo independiente**
(`harness.alcance` + `harness.mutacion`, `96bb7b9..f2fb04d`): **38 líneas de
producción** (24 + 14) y **0 mutantes**, idéntico al informe. **Prueba de
control del cero**, lo que distingue «no había nada que mutar» de «el generador
está roto»: `generar_mutantes` sobre esos mismos ficheros **ignorando el
alcance** da **6 y 237 mutantes**. El cero viene de las líneas, no de la
herramienta. **Los tres mutantes manuales los reproduje uno a uno** sobre la
copia: salen **exactamente** los números y los tests del informe.

| # | Sustitución | Declarado | Medido por mí |
|---|---|---|---|
| M1 | `grants.py:117` `revocables = [par for par in aplicables if par not in ausentes]` → `list(aplicables)` | 3 failed (r7, r9×2) | **3 failed**, mismos tests |
| M2 | `grants.py:113` `esquemas_con_exclusion` derivado de `revocables` (el agujero del review, reintroducido) | 2 failed (r9×2) | **2 failed**, mismos tests |
| M3 | `postgres_client.py:1314` `missing_tables=sin_tabla` → `missing_tables=()` | 2 failed (r7, r9) | **2 failed**, mismos tests |

**Mi juicio: exención razonable, no hueco de rigor.** (a) El delta son 38 líneas
y las leí todas: la única lógica de decisión es la separación de las dos listas,
y los tres mutantes atacan las tres formas de colapsarlas otra vez en una.
(b) **M2 es literalmente el defecto que rechacé en la pasada 1**, y muere. (c) La
automática no habría dicho «verde por poco» sino «0 de 0», ceguera con pinta de
verde, y el informe lo dice con esas palabras. Pero **una campaña manual es
autoseleccionada** —prueba lo que el implementer eligió atacar, no la ausencia
de puntos ciegos—: solo la acepto por ser el alcance pequeño y revisable.

## Los tres puntos que el encargo pedía mirar de cerca

1. **El bloqueante (punto 1): cerrado.** `esquemas_con_exclusion` sale de
   `aplicables` (lo **declarado** dentro de los esquemas concedidos) y ya no de
   la lista filtrada; `revocables = aplicables - ausentes` manda solo sobre el
   `REVOKE ... ON TABLE`. Con `raw.emp` y `raw.res` ausentes la nocturna emite
   `ALTER DEFAULT PRIVILEGES ... IN SCHEMA "raw" REVOKE SELECT` y **no** el
   `GRANT` por defecto: comprobado con el cliente real en
   `r9_el_cliente_mantiene_el_catalogo_tras_un_drop`, el test que habría cazado
   esto en la pasada 1. **El defecto ES el seguro, verificado**:
   `missing_tables: Sequence[str] = ()` → `ausentes = set()` → se revoca todo lo
   declarado, y el olvidadizo se lleva un error ruidoso de PostgreSQL, no una
   tabla legible en silencio (`r9_sin_lista_de_ausentes_...`).
2. **Punto 2, la ventana de `02_roles.sql`: cerrada, no solo documentada.**
   `BEGIN;` en la 112 (antes del `DO` del punto 5) y `COMMIT;` en la 236 (tras
   el `RESET ROLE` del 5 bis). Dentro solo hay `DO`, `SET ROLE` y `RESET ROLE`,
   todo transaccional —ni `VACUUM`, ni `CREATE DATABASE`, ni `CONCURRENTLY`—:
   las dos mitades entran juntas o no entra ninguna. El test lo ata por posición
   **y** falla si alguien mete un `COMMIT` intermedio.
3. **Punto 3: el esquema se deriva.** `split_part(excluida, '.', 1)` sobre el
   `unnest` de la lista, con `to_regnamespace` y el alias renombrado. Correcto.

## Trazabilidad `acceptance` → test (delta)
| Criterio | Cubierto por |
|---|---|
| 3 · la nocturna no devuelve el permiso al día siguiente | `r9`×4 (uno de extremo a extremo con el cliente) |
| 3 · el arranque desde cero tampoco lo devuelve | `r10`×2 sobre el texto de `02_roles.sql` |
| 4 · los dos documentos de `azure-apps` | commit `02025db`, leído: los dos restos corregidos, más el matiz de que los `REVOKE` no cegaron al MCP **por suerte** y el aviso pasa a «avisad antes» |

## Lo que NO he verificado yo, y las observaciones

- **Los privilegios vivos en Azure.** El MCP rechaza `information_schema`
  (`OBJETO_NO_PERMITIDO`) y un `SELECT count(*) FROM raw.emp` responde «el
  esquema 'raw' está fuera del ámbito autorizado»: **corrobora el matiz del
  punto 4** —el MCP no ve `raw` por su lista, no por el `REVOKE`—, no lo prueba.
  Lo verificó el líder; el delta solo cambia la próxima nocturna.
- **`02_roles.sql` no lo ejecuta nadie**: solo se comprueba su texto y sus dos
  cambios solo los valida `psql`. Suscribo la verificación MANUAL del informe:
  antes de reprovisionar un rol, ejecutarlo con `-v ON_ERROR_STOP=1` contra una
  base de prueba.
- **O1** — `ARRAY['raw.emp','raw.res']` sigue escrito **tres veces** en
  `02_roles.sql`; anterior, y el fichero dice que la fuente es `settings.py`.
- **O2** — efecto lateral del punto 6: con la rama compartida, `PUERTA TAMAÑO`
  de `init.sh` mide **F-066**, no F-068. Medí F-068 a mano: dentro de topes.
- **O3** — sin commitear `harness/features.json` y `BACKLOG.md` (anotación de
  F-069, del líder): `init.sh` pide incluir el `BACKLOG.md` regenerado.
- **O4** — la tabla de mutación manual no da `fichero:línea` por fila.

## Automejora (propuesta, no aplicada)

`CHECKPOINTS.md`, C4 bis: subir a la lista dos exigencias que hoy solo viven en
`.claude/agents/reviewer.md`, para que el implementer las conozca **antes** de
escribir el informe: (1) una campaña de **cero mutantes** trae su **prueba de
control** —generar sobre los mismos ficheros ignorando el alcance—, porque si no
«0 de 0» y «el generador está roto» son el mismo número; y (2) toda fila de una
campaña **manual** lleva `fichero:línea` y el texto exacto `original → mutado`,
lo único que la hace reproducible por otro.
