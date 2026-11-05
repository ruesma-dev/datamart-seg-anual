Revisión completa (pasada 1), `bec363c..119f9a1` (merge-base con `main`; implementación desde `028f366`)

# Review F-156 · Postventa

**Veredicto: CHANGES_REQUESTED** (reviewer, 2026-11-05)

Código, SQL, permisos y tests cumplen la spec. Se rechaza por la **vuelta atrás**, no
ejecutable tal como está (cambios 1-2), y por una promesa de la spec sobre datos personales
que la ficha no cumple (cambio 3). Todo es documentación o runbook: pasada 2 corta.

## Nivel de rigor

`estandar`, declarado en `features.json`. Exige fase RED, cobertura ≥ 80 % de lo cambiado y
mutación por muestreo. `bash harness/init.sh` **no lo he vuelto a ejecutar** (4 h 13 min):
el líder lo dispensó y el implementer lo dio en verde sobre `206fd57` (10509 passed, cobertura
100 % de 239 líneas). Desde entonces solo cambian `progress/` y `tasks.md` (comprobado con
`git diff --stat 206fd57..HEAD`). Los 196 tests de F-156, ejecutados por mí: **196 passed**.

## Checkpoints

- C1 [x] `init.sh` verde según el implementer (ver arriba); arnés completo.
- C2 [x] Una sola `in_progress` (F-156); rama `feature/F-156-postventa`; `current.md` con la
  sesión. Nota: dice presupuesto F-147 «34.212» y el informe «34.006» (cambio 5).
- C3 [x] Hexagonal: `domain/postventa.py` solo importa `re`, `collections`, `datetime`,
  `typing`. Primera línea con ruta en los 9 SQL, el paso, el dominio, las fichas y los 5 tests.
  Sin prints, sin TODO, sin secretos (`02_roles.sql` usa `\getenv`; test r31 lo vigila).
- C3 bis N/A: no entra ningún documento de fuera. C4 ter N/A: no hay `harness/rutas_sensibles.json`.
- C4 [x] Trazabilidad R1-R36 abajo; los tests de humo no tocan red ni BBDD; MANUAL (R17, R27,
  T16) listados en design §12 e impl §5. [ ] parcial en el **runbook MANUAL**: ver cambios 1-2.
- C4 bis [x] rigor declarado; RED con salida real (T1, T9, T12, T13 en impl §4); cobertura 100 %;
  mutación (detalle abajo); sección «Evidencias» con los cuatro números.
- C5 [x] T1-T15 y T17 `[x]` con commits `F-156 Tn`; T16 es MANUAL tras merge. Árbol limpio.
## Mutación (verificación independiente)

- Recalculado con `harness.alcance` + `generar_mutantes` (puro): **762 líneas, 77 mutantes**,
  igual que el informe. El superviviente (`build_postventa_step.py:137`, `2`→`3`, operador
  `entero`) existe tal cual. Es el redondeo de una duración que solo va al log: equivalente.
- «Tiempo total» 19.878 s > 60 s: **campaña no reejecutada** (5 h 31 min según el informe);
  recálculo puro + RM1-RM6.
- RM1 [x] SHA medido `9720e82`; de ahí a HEAD solo `progress/` y `tasks.md`.
- RM2 [x] media 993,9 s frente a base ~2.200 s con 19/20 muertos y `-x`: coherente; total = 20 ×
  media. RM3 [x] ningún equivalente muerto a la vista. RM5 N/A (rigor `estandar`). RM6 N/A
  (no se quitó código defensivo). Sin cabecera «CAMPAÑA NO VÁLIDA», «sin veredicto» 0.

## Lo que pidió mirar el líder

**Datos personales.** [x] `postventa` no publica nombre, teléfono ni correo de clientes: solo
`tiene_propietario`; propietario, reclamante y contacto van a `postventa_restringida` (07).
`per` entra con 5 columnas por lista blanca en la ingesta (`include_columns`) y el SQL solo lee
`nom`, `tel`, `tel2`, `ele` (test r3 y r24, con alias vigilados). `postventa_restringida`: vetada
al general (punto 5 ter y `DEFAULT_VETOED_SCHEMAS`), fuera del restringido (su veto de catálogo
la alcanza), concedida al grupo postventa y al autorizado (y por él al total). REPARACION: su
origen es `postventa_restringida.contactos_incidencia`, así que PostgreSQL niega el fichero al
estándar y al restringido; lo hará cumplir `mcp-bbdd` con el pliego P2. **Pero** la máscara
solo quita teléfonos y correos: los nombres que aparezcan en texto libre siguen en
`postventa`, y `ubicacion`, `urgencia`, `espacios`, `nombre_unidad` y, en adjuntos,
`nombre_fichero` y `descripcion` no se enmascaran. Lo aceptó el humano (D10), pero design §11
promete que «la ficha lo dice» y **no lo dice** (cambio 3).

**Perfil postventa.** [x] `perfil_postventa_en_conflicto` exige exactamente restringido +
`postventa_restringida`, que esta esté vetada y en lo restringido, y falla sin conectar; roles
propios distintos de todos los anteriores; mismo bloque nocturno que F-141 (concesión, veto del
catálogo, filtraciones, verificación de lecturas y pertenencias). `02_roles.sql`: grupo NOLOGIN,
login con `\getenv POSTVENTA_PWD` y guarda previa, CONNECT solo al grupo, pertenencia `INHERIT
TRUE, SET FALSE` tras los vetos, comprobaciones finales.

**Pasos MANUAL.** [x] En orden: roles (crea y veta el esquema) antes del primer build;
`apply-grants` tras `build-postventa` (paso 4); sin secretos (solo nombres de secreto).
[ ] Vuelta atrás: ver cambios 1 y 2.

**Histórico.** [x] `incidencia_procesos`: fecha y momento, estado de origen y destino (id,
código y nombre por la pareja tipo-estado), `usuario` (login) y `usuario_nombre`, de `rac` y de
los cierres de `raw.log`; `v_estado_incidencias` con `en_estado_desde`, `cambiado_por` y
`origen_fecha` en el orden de R15. Los cierres de la aplicación no traen estado de origen: lo
dice la ficha.

**Noche.** [x] `depends_on = ["ingest_raw"]`, nadie depende de `build_postventa`, en
`PASOS_CON_PERMISOS`; `R-FRESCURA` alcanza a los dos esquemas (errata en cambio 4).

**`azure-apps` `8dc4b04`.** [x] Local, sin push, árbol limpio; solo nombra el secreto
(`pg-password-postventa`), sin valores, IPs ni IDs.

## Cobertura requisito → test

| Req. | Test (`tests/test_f156_*.py`) |
|---|---|
| R1-R5 | `ingesta_sql`: `r1_*`, `r2_log_recortado_sin_res`, `r3_*`, `r4_*`, `r5_el_censo_pasa_a_93` |
| R6-R10 | `ingesta_sql`: `r6_unidades`, `r7_*`, `r8_*`, `r9_*`, `r10_tareas`; `dominio`: `r8_*` |
| R11 | `ingesta_sql`: `r11_ninguna_columna_*`, `r11_el_general_no_lee_per`; `dominio`/`diccionario`: `r11_*` |
| R12, R21 | `ingesta_sql`: `r12_guarda_de_cabeceras`, `r21_guarda_de_huerfanos` |
| R13 | `dominio`: `r13_enmascarar`, `r13_marcas`; `ingesta_sql`: `r13_la_mascara_del_sql_es_la_del_dominio` |
| R14-R16, R18 | `ingesta_sql`: `r14_*`, `r15_*`, `r16_*`; `dominio`: `r15_*`, `r16_*`, `r18_*` |
| R17, R27 | MANUAL (design §12 pasos 6-7) |
| R19-R20, R22 | `ingesta_sql`: `r19_*`, `r20_*`; `dominio`: `r20_*`; `diccionario`: `r22_*` |
| R23-R24 | `ingesta_sql`: `r23_*`, `r24_de_per_solo_salen_sus_cinco_columnas`; `diccionario`: `r23_*` |
| R25-R26 | `ingesta_sql`: `r25_*`, `r26_*`; `dominio`: `r25_*` |
| R28-R31 | `grants`: `r28_*`, `r29_*`, `r30_*`, `r31_*` |
| R32 | `pipeline`: `r32_*` (12 tests) |
| R33-R35 | `diccionario`: `r33_*`, `r34_*`, `r31_esquemas_del_datamart`, `r35_*` |
| R36 | `init.sh` del implementer |

## Cambios requeridos

1. **Vuelta atrás con un commit concreto.** `progress/impl_F-156.md` §5 («`git switch --detach`
   a la punta previa») y `specs/F-156-postventa/design.md` §12, vuelta atrás paso 2
   («`<punta de main previa al merge>`») no dan un SHA. Añadir al paso 0 `git rev-parse main`
   (anotarlo) y escribir el SHA de hoy: **`9dcd0aa`** (`main` avanzó tras crear la rama: «Cierre
   de F-153»), con la instrucción de sustituirlo si `main` se mueve antes del merge.
2. **`DROP OWNED BY` ejecutable por el administrador de Azure.** Design §12 vuelta atrás paso 3
   y `docs/runbook_postgres_azure.md` §14 «Vuelta atrás» lo lanzan con el administrador, que en
   Azure PG16 no es superusuario. En PG16 `DROP OWNED BY` exige tener los privilegios del rol, y
   quien lo crea con `CREATEROLE` recibe por defecto la pertenencia solo con ADMIN (sin
   INHERIT). Si es así, falla y, con `ON_ERROR_STOP` en un `-c` multisentencia, no hace nada.
   Demostrarlo en el PostgreSQL 16 desechable con un administrador NO superusuario con
   `CREATEROLE` y, si falla, anteponer `GRANT sigrid_dm_perfil_postventa_ro TO CURRENT_USER
   WITH INHERIT TRUE;` (o la vía que funcione) en los dos sitios, con la salida en el informe.
3. **La ficha debe decir que la máscara es heurística** (design §11 lo promete y R11/R13 se
   apoyan en ello). En `config/diccionario/postventa.yaml` (`fn_enmascarar`, `incidencias`,
   `tareas`, `documento_adjuntos`) y en `R-POSTVENTA-RESTRINGIDA` de `00_global.yaml` («sin
   personas»): que solo quita teléfonos y correos con patrón, que un nombre propio en el texto
   libre NO se quita, y qué columnas de texto van sin máscara (`ubicacion`, `urgencia`,
   `espacios`, `nombre_unidad`, `nombre_fichero` y `descripcion` de adjuntos). Sin eso, «sin
   personas» le promete al agente algo que el dato no cumple.
4. **`R-FRESCURA`** (`00_global.yaml`): «y los ocho registran paso» → «y los nueve».
5. **`progress/current.md`**: presupuesto de F-147 «34.212» frente a «34.006» del informe y de
   `PRESUPUESTO_MAX`; dejar la cifra real.

## Observaciones (no bloquean; para el líder y el humano)

- **El grupo autorizado lee `postventa_restringida`** (R28, como las otras `*_restringida`). Hoy
  solo lo usa el total, pero quien Negocio meta en él para la contabilidad completa verá
  también los datos de clientes de postventa. Conviene que el humano lo sepa antes de dar
  altas en ese grupo.
- **`main` va por `9dcd0aa`** y toca `features.json`, `BACKLOG.md` y `history.md`: el merge
  probablemente choque en la entrada de F-156; resolver antes de cerrar.

## Automejora (propuesta, no aplicada)

`CHECKPOINTS.md` C4: «la vuelta atrás MANUAL nombra commits y tags concretos y sus sentencias
privilegiadas están probadas con un rol como el de producción (no superusuario en Azure)».
