<!-- progress/review_F-102.md -->
Revisión completa (pasada 1) · `main...70d6fee`

# F-102 · Review (reviewer, 2026-09-24)

**Veredicto: CHANGES_REQUESTED** (RECHAZADO). El código es correcto: el SQL, las
fichas, los tests y las cifras cuadran, y las he medido yo en solo lectura. Lo que
falla es el papeleo que lee el humano, en tres puntos:
- `current.md` no lista las verificaciones MANUAL con su comando (C4). Es el mismo
  defecto que se rechazó en F-094 y en F-101.
- `current.md` arrastra bloques de la fase de spec que contradicen lo aprobado (C2).
- La spec aprobada prometía vigilar en la base la unicidad de las claves. No se
  cumple y la desviación no está declarada.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura
≥ 80 % y mutación.

## Verificado

- **`bash harness/init.sh`**, tal cual: ENTORNO LISTO, exit 0.
  - pytest: 5.246 passed, 191 skipped (1.017,30 s).
  - PUERTA COBERTURA [OK]: 94,7 % (968/1022). Se mide contra `dev`, así que son
    líneas de otras features: F-102 no toca Python de producción.
  - PUERTA TAMAÑO [OK]; la rama es la correcta; ruff da 232 avisos de deuda previa.
- **Fase RED reproducida** en copias hechas con `git archive` en el scratchpad:
  - T1 sobre f6e1ae4: 86 failed, 19 passed.
  - T15 (el test de HEAD sobre 00addaf): 9 failed, 1 passed, 1 skip (R29: en la
    copia no está `azure-apps`). Ambas cuadran con el informe.
- **Mediciones en solo lectura** (`default_transaction_read_only=on`, con
  `raw.auxemp` simulada):
  - `v_obra_fichas`: 922 filas, 922 claves, 846 principales y 846 códigos.
    Ningún código tiene dos principales. Difiere de `stg.obras` solo en 0581,
    0606, 0671 y 0720.
  - `maestro.obras` nueva: 922 filas, 922 `obra_id` y 922 `clave_obra`; la
    publicada tiene 922.
  - `personal.recursos`: 2.618 filas y 2.618 claves; la publicada tiene 2.618.
  - Las cinco vistas de `compras` devuelven las mismas filas que las publicadas
    (19.024 / 45.185 / 120.415 / 118.415 / 81.665), y ninguna fila tiene obra
    sin clave.

**Los siete puntos del líder**

1. `stg/03_obras.sql` no cambia: el test por hash (R7) está en verde y nada en
   `stg` lee la vista.
2. Las cinco vistas de `compras` acaban en `empresa_id, clave_obra`. Ningún SQL
   de `compras` nombra `obra_principal_id` (R21): la columna solo existe en
   `maestro`, con el aviso de que no sirve para agregar hechos de otras empresas.
3. Las claves son únicas (922/922 y 2.618/2.618) y el test vigila cómo se
   construyen (R6, R26). En la base no las vigila nadie: ver el cambio 3.
4. No se pierde ninguna fila: lo confirma la medición y lo garantiza el SQL
   (`LEFT JOIN` 1:1 y laterales `LIMIT 1`, sin `WHERE`).
5. Acepto las cinco desviaciones: vista en `00_setup.sql` (guarda de F-073), cierres
   agregados antes de unir, unión antes de agregar con el mismo grano (medido),
   `N:N` con `porque` honesto (validador de F-006) y vista recomendada (F-079).
6. Ningún nombre de persona de Sigrid en lo añadido. El barrido de mayúsculas y
   nombres propios solo encuentra obras, la razón social de Porsan y el
   solicitante, que ya estaba citado; los recursos se identifican por código.
7. `azure-apps` tiene los commits locales 511ffff y 4a14173, sin remoto ni push.
   Recogen las columnas nuevas, la regla, las 69 tablas, F-106 y la dependencia
   de `raw.auxemp`.

**Mutación.** `alcance_de_feature('F-102', base='main')` da 0 ficheros y 0
líneas, luego 0 mutantes, igual que el informe (la base es `main`, de donde sale
el hotfix). La prueba de control, `generar_mutantes` sobre los `.py` del diff sin
exclusión, da 138: el cero es legítimo, la feature solo cambia SQL, YAML y
documentación.

## Checkpoints

- **C1** [x] init.sh en verde · [x] ficheros del arnés.
- **C2** [x] una sola feature en curso · [x] la rama es la de `features.json` ·
  [x] history · **[ ] `current.md`**: los bloques de spec de F-102
  (l. 1796–1857) están obsoletos y se contradicen (cambio 2).
- **C3** [x] hexagonal, SQL en su capa con `NN_` · [x] primera línea con ruta ·
  [x] sin prints, TODOs, secretos ni dependencias nuevas · [x] semántica Sigrid.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x] R1–R10 y R13–R29 con tests en verde; R11, R12 y R30 son MANUAL y R31
  es init.sh · [x] tests offline · [x] sin dobles nuevos · **[ ] las MANUAL no
  están en `current.md` con su comando**: la l. 26 solo dice «T16» (cambio 1).
- **C4 bis** [x] rigor declarado · [x] RED reproducida · [x] cobertura [OK] ·
  [x] «Evidencias». Los N/A, con su motivo:
  - `mutacion_F-102.md`: la herramienta no lo escribe con alcance vacío; el cero
    está verificado por recálculo y control.
  - Reejecución, coste por mutante, NO VÁLIDA, RM1, RM2, RM6 y supervivientes:
    no hay mutantes.
  - RM5: el nivel es `estandar`.
  - Campaña manual: no se hizo; el SQL lo cubren los tests de texto y mi
    medición.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1–T15 y T17 `[x]` con commits `F-102 Tn:` (T16 es la MANUAL del
  humano tras la nocturna) · [x] árbol limpio · [x] `features.json` en
  `in_progress`.

## Requisito -> test (todos en verde, prefijo `test_f102_`)

R1–R10 y R13–R29 tienen cada uno al menos un `test_f102_rN_*` (118 casos en total,
incluidos 13 de R21, 15 de R22 y 16 de R23); R11, R12 y R30 son MANUAL (T3/T16).

## Cambios requeridos

1. **`progress/current.md:26` · MANUAL de T16 con su comando exacto.**
   - Las seis consultas de T16 en `tasks.md`, cada una con su resultado esperado.
   - `python main.py check-unicidad`, `check-relaciones` y `check-declarados`.
   - `publicar-diccionario` (versión 29), que escribe en Azure y lanza el humano.
   - El reinicio del MCP.
   - El orden de despliegue, que hoy solo consta en `impl_F-102.md`:
     `raw.auxemp` se ingiere antes de cualquier `build-maestros` o
     `build-personal` a mano, y si la primera noche se salta `build_maestros`,
     `build_compras` falla en `03_views.sql`.
2. **`progress/current.md:1796-1857` · bloques de la fase de spec.**
   - Siguen diciendo «pendiente de aprobacion», «Decisiones que necesita validar
     el humano», «T0 bloquea», «Abierta D5» y «(T16-T17)».
   - La línea 1845 añade «mas `obra_principal_id` en las cinco vistas de consumo
     de `compras`», justo lo que el humano descartó.
   - Hay que sustituirlos por un resumen coherente con la spec aprobada y
     remitir a `progress/spec_F-102.md`.
3. **Desviación 6, sin declarar: la base no vigila `clave_obra` ni
   `clave_recurso`.**
   - La spec aprobada prometía «un test lo vigila por la construccion y
     `check-unicidad` en la base» (`design.md` §6; `spec_F-102.md:48-50`).
   - Pero `check-unicidad` sale de `clave_negocio`
     (`unicidad_sql.consultas_de_unicidad`), que sigue siendo `[obra_id]` /
     `[recurso_id]`.
   - Hay que declararlo en `impl_F-102.md` y en `current.md`, y escribir en la
     lista MANUAL que esa unicidad en base la comprueban **solo** las consultas
     `count(DISTINCT ...)`.
   - La vigilancia permanente no bloquea y la decide el humano. Hay dos caminos:
     un índice único en `personal.recursos (clave_recurso)`, o admitir claves
     alternativas en el validador de F-006, que resolvería también la
     desviación 4.

Pasada 2: incremental desde 70d6fee, solo papeleo.

## Observaciones (no bloquean) y automejora

- El docstring de `build_maestros_step.py` no dice que `00_setup.sql` crea ahora
  `v_obra_fichas` (T12 exigía no tocar `steps`; que se corrija con F-106). Los
  `acceptance` de F-102 son de antes de la spec: al cerrar, alinearlos o anotarlo.
- Propuesta para C4 de `CHECKPOINTS.md`: «si la spec promete que una puerta de la
  base vigila una columna, comprobar que la puerta la lee de verdad».
