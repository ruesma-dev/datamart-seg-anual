Revisión incremental desde af7c363 (pasada 2), delta `af7c363..a3edf21`

# Review F-156 · Postventa

**Veredicto: APPROVED** (reviewer, 2026-11-05)

Lo aprobado en la pasada 1 (`bec363c..119f9a1`: código, SQL, permisos, tests, mutación) queda
dado por bueno. Es el commit `af7c363` y su informe está en el historial de este fichero
(`git show af7c363:progress/review_F-156.md`). El delta, `a21c786` y `a3edf21`, solo toca
fichas del diccionario, el runbook, design §12, `current.md`, el informe y el presupuesto de
F-147. No cambia ninguna firma, ningún SQL ni el alcance de la mutación. Las líneas de
producción siguen siendo 239 y la campaña sigue valiendo (RM1).

## Nivel de rigor

`estandar` (declarado). Exige fase RED, cobertura y mutación. Las tres quedaron verificadas en
la pasada 1 y el delta no las altera.

## Verificación de esta pasada

- `bash harness/init.sh`, ejecutado **entero por mí** sobre `a3edf21`: **exit 0**, `10509 passed,
  312 skipped` (43 min 56 s), `PUERTA COBERTURA` OK 100 % de 239 líneas, `PUERTA TAMAÑO` OK.
- Antes, la batería afectada por las fichas: f156 (los 5 ficheros), f147 (presupuesto y
  contenido), f006 (fichas, reglas y formato) y f149: `1561 passed, 301 skipped`.

## Cambios requeridos de la pasada 1

1. [x] **Commit concreto en la vuelta atrás.** El paso 0 anota `git rev-parse main`. Design §12
   (vuelta atrás, paso 2) e impl §5 dicen `git switch --detach 9dcd0aa`, con la instrucción de
   cambiarlo si `main` se mueve. He comprobado que `9dcd0aa` es hoy la punta de `main`.
2. [x] **`DROP OWNED BY` ejecutable.** La impl §5 trae la traza real del PostgreSQL 16
   desechable. El administrador de prueba se crea `LOGIN NOSUPERUSER CREATEROLE` y los roles los
   crea él, como en `02_roles.sql`.
   - Su pertenencia al grupo sale con `admin_option t`, `inherit_option f` y `set_option f`.
   - Sin el GRANT, la vuelta atrás falla con `permission denied to drop objects` y el detalle
     propio de PG16 («Only roles with privileges of role …»). Sale con `exit=1` y los roles
     siguen, porque el `-c` es una sola transacción.
   - Con `GRANT … TO CURRENT_USER WITH INHERIT TRUE` delante, sale con `exit=0`, sin roles
     restantes y con `pg_default_acl` a 0.

   La traza encaja con lo que da PG16: es una evidencia creíble, no un párrafo. El GRANT queda
   en los tres sitios: design §12 (paso 3), impl §5 y runbook §14. El orden también está bien:
   primero se borra el login, luego el GRANT, luego `DROP OWNED` y por último `DROP ROLE` del
   grupo.
3. [x] **La máscara, declarada heurística.**
   - `R-POSTVENTA-RESTRINGIDA` cambia título, resumen y regla. Ya no promete «sin personas»:
     dice que un nombre propio en el texto libre no se quita, lista las seis columnas que van sin
     máscara y pide no citar esos nombres.
   - Lo mismo en la cabecera de `postventa.yaml` y en las fichas `incidencias`, `tareas`,
     `documento_adjuntos` (`nombre_fichero` y `descripcion` «pueden llevar el nombre del
     cliente») y `fn_enmascarar`. Esta última dice a qué columnas se aplica y a cuáles no.
   - La ficha del esquema `postventa` en `00_global.yaml` cambia «sin personas» por «sin fichas
     de clientes».
4. [x] `R-FRESCURA`: «los nueve registran paso».
5. [x] `current.md` da la cifra real: 34.056, que es 34.006 más los 50 de esta corrección.

**Presupuesto de F-147.** `PRESUPUESTO_MAX` sube 34.006 → 34.056 (+50) con el motivo en la
historia del test: reglas +16 y bloques +34, medidos. Es el sitio y la forma que exige ese
trinquete. La subida se justifica: la regla tenía que dejar de prometer algo falso.

## Checkpoints (estado final)

- C1 [x] `init.sh` verde, ejecutado por mí en esta pasada.
- C2 [x] Una sola `in_progress` y la rama de la feature. `current.md` coherente con el informe.
- C3 [x] El delta no toca código. Las fichas conservan la primera línea con su ruta. Sin
  secretos: el runbook y design §12 solo nombran roles y el secreto, nunca valores.
- C3 bis N/A: no entra ningún documento de fuera.
- C4 [x] Requisitos R1-R36 cubiertos (tabla en la pasada 1, sin cambios). Los MANUAL (R17, R27,
  T16) y la vuelta atrás quedan concretos y la parte privilegiada está probada.
- C4 bis [x] RED, cobertura 100 % y mutación (77 mutantes, 20 evaluados, 19 muertos, 1
  superviviente equivalente) verificadas en la pasada 1. RM1: el SHA medido, `9720e82`, sigue
  sin diferencias de producción con HEAD. RM5 y RM6: N/A, como en la pasada 1.
- C4 ter N/A: no hay `harness/rutas_sensibles.json`.
- C5 [x] T1-T15 y T17 `[x]` con commits. T16 es MANUAL del humano tras el merge. Árbol limpio.

## Cobertura requisito → test

Sin cambios respecto a la pasada 1 (`git show af7c363:progress/review_F-156.md`, sección
«Cobertura»). La regla y las fichas reescritas las vigilan `test_f156_diccionario.py`
(`r34_regla_postventa_restringida`, `r33_*`), `test_f006_reglas.py` y
`test_f147_presupuesto_contexto.py`, que pasan.

## Pendiente para el líder y el humano (no bloquea)

- **Merge**: `main` va por `9dcd0aa`, que toca `features.json`, `BACKLOG.md` y `history.md`.
  Probablemente choque en la entrada de F-156: hay que resolverlo al integrar. Si `main` se
  mueve otra vez, hay que actualizar el SHA de la vuelta atrás.
- **El grupo autorizado lee `postventa_restringida`.** Quien Negocio meta en él para la
  contabilidad completa verá también los datos de clientes de postventa. El humano debe
  saberlo antes de dar altas.
- **T16 (MANUAL)** según la impl §5 y design §12. Después, el pliego a `mcp-bbdd`: hasta que se
  despliegue, el MCP no ve `postventa` y los ficheros REPARACION no se abren para nadie.
- Una errata en `postventa.yaml`, ficha `tareas` («lA MASCARA»). Es cosmética: se puede
  arreglar en la próxima edición de la ficha.

## Automejora (propuesta, no aplicada)

En `CHECKPOINTS.md` C4, añadir: «la vuelta atrás MANUAL nombra commits y tags concretos, y sus
sentencias privilegiadas están probadas con un rol como el de producción (no superusuario en
Azure)». En F-156 fue lo único que hizo falta corregir, y sin la prueba en PG16 la vuelta atrás
habría fallado justo el día en que hiciera falta.
