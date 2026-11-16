# progress/review_F-164.md
Revisión incremental desde 73be7f8 (pasada 2, principal) · delta `73be7f8..d363587` · pasada 1: `95a7c022f3..8aa0e6a`

## Veredicto: APPROVED (APROBADO)

Pasada 1 (resumen): CHANGES_REQUESTED por H1 (cuatro mutaciones graves del `CASE` del SQL vivían en
la puerta) y H2 (papeleo); la regla en sí ya estaba verificada en Azure sobre los 16.088 enlaces.
Pasada 2: H1, H2 y H4 resueltos y comprobados por mí; H3 recogido en el informe. Nada fuera de lo pedido.

**Nivel de rigor:** `critico` (declarado; sin `rigor.local.json`). Exige fase RED, cobertura ≥ 90 %,
mutación con cero supervivientes sin justificar (T7, tras este APPROVED) y las MANUAL con su comando.

## Qué cambió desde 73be7f8 (`git diff 73be7f8..HEAD`, 7 commits)

| Commit | Ficheros | Valoración |
|---|---|---|
| `309e252` / `d363587` | `features.json` + `BACKLOG.md` (ida y vuelta a `in_review`, neto 0), `impl` | Estado y puerta |
| `d8b99e9` H1 | `tests/test_f164_sql.py` (+28) | El test propuesto, literal |
| `e5ac228` H4 | `domain/postventa.py` (1 línea + docstring), `test_f164_dominio.py` | Sin cambio de comportamiento (abajo) |
| `3c95df4` | `test_f164_dominio.py:62` (SIM300) | Cosmético |
| `acdc8f3` / `99d7f13` | `current.md`, `impl_F-164.md`, `tasks.md` (T12 `[x]`) | H2 |

Ningún otro fichero: ni SQL, ni diccionario, ni `docs/`, ni azure-apps. El delta no invalida nada de
lo aprobado en la pasada 1 (la equivalencia del dominio, abajo, lo cierra).

## Puerta (C1) y lo que he ejecutado yo

- **Puerta completa:** no la repito, por orden del líder. Doy por buena la suya sobre `99d7f13`
  (`13526 passed, 2532 skipped`, 1 h 32 min, `PUERTA COBERTURA` 24/24, `ENTORNO LISTO`); el delta
  hasta HEAD solo toca `impl`, `features.json` y `BACKLOG.md` (comprobado). 13526 = 13525 + el test nuevo.
- **Mis tests sobre HEAD:** `test_f164_*` (4 ficheros) + `test_f156_dominio` + `test_f006_contexto`:
  **365 passed, 6 skipped** (la sandbox, sin DSN); `test_f003_infra -k r4` (el que tumbó la ruta del
  scratchpad): **33 passed**. `ruff check` de los tres ficheros tocados: `All checks passed!`.
- Árbol limpio después: solo `?? progress/mutacion_F-163.json`, de F-163. Todo lo demás, en una copia.

## H1 · resuelto: la puerta ya protege la ESTRUCTURA del `CASE`

`test_f164_r9_el_case_entero_es_el_del_dominio` es el que pedí: `ORDEN_SQL` fijo, `set(ORDEN_SQL) ==
set(pv.LISTA_ABIERTA)` y el `CASE` entero armado con `pv.PATRON_SENAL_FIRMA` / `PATRON_SENAL_CODIGO`.
El RED del implementer (M1 con su salida real, M2-M4 `1 failed, 9 passed`) está en `impl_F-164.md`
«Ciclo 2». **Lo he reproducido** con `git archive HEAD` en el scratchpad y un script que muta solo el
`06_adjuntos.sql` de la copia (base: `10 passed`):

| Mutante sobre la copia | Resultado de `tests/test_f164_sql.py` |
|---|---|
| M1 `OR TRUE` · M2 `OR b.clase_grafico_id IS NULL` · M3 S3 `AND FALSE` · M4 `OR`→`AND` entre S2 y S3 | **muertos** los cuatro, `1 failed`: solo el test nuevo (eran los vivos de la pasada 1) |
| M5 `IS FALSE`→`IS NOT TRUE` · M7 `ELSE b.familia_documento` · M8 `THEN 'INCIDENCIA'` | muertos (5 failed) |
| M9 `AND`→`OR` entre la lista y las señales · M11 `IS TRUE`→`IS NOT FALSE` | muertos (5 failed) |
| M10 quitar la pareja 707/39 | muerto (2 failed) |

Diez de diez. El `CASE` queda clavado al dominio, y el dominio lo protegen sus 250 tests y T7.

## H4 · resuelto: quitar el `strip` no cambia nada ni contradice la spec

- **Spec:** ningún requisito pide recortar en el dominio. El design §3 dice «nombre y descripción,
  tal y como los publica la tabla (`NULLIF(BTRIM(...), '')`)», que describe la entrada del SQL; la
  firma y el docstring de `senal_parte_firmado` / `familia_publicada` no cambian.
- **Razonamiento:** el recorte solo quita espacios de los bordes. En S2 (sobre `nombre + ' ' +
  descripción`) un espacio es no letra, igual que `^`/`$`, y el separador `' '` existe siempre; S3
  empieza por `RS` y acaba en cifra, así que un borde nunca entra en su coincidencia.
- **Comprobado:** la señal de 73be7f8 (con `strip(" ")`) contra la de HEAD sobre **400.000 pares**
  aleatorios (FIRMA/CONFIRMADO/RS…, tabuladores, U+00A0, acentos, `None`, bordes de 0-3 espacios):
  **0 distintos**. Y los 40 `CASOS` de la sandbox R10 (1 con bordes) por el oráculo viejo y el nuevo:
  0 distintos. La sandbox verde de la pasada 1 sigue valiendo sin repetirla.
- El test renombrado (`r4_los_espacios_de_los_bordes_no_cambian_la_senal`) gana S3 con bordes y el
  caso sin señal: bien. T7 ya no tendrá ese equivalente.

## H2 · resuelto: papeleo al día, comandos comprobados

- `current.md`: sin el BLOQUEO, con la puerta del líder y T8-T11 con su comando; `tasks.md` T12 `[x]`;
  `impl_F-164.md`: la fila del tiempo (1 h 32 min) y la línea de azure-apps (ya en `origin/main`, H3).
- **Comandos de T8-T11, contrastados con el repositorio:** `infra/70_build_image.ps1` (imprime
  «APUNTA ESTE TAG») y `infra/85_update_job.ps1 -Tag` existen con esos parámetros; `caj-datamart-seg-dev`
  y `rg-datamart-seg-dev` son los de `infra/env/dev.json`; `build-postventa`, `apply-grants` y
  `publicar-diccionario` son comandos de `main.py` (líneas 5492, 964 y 2343). La receta de la
  ejecución puntual remite a la memoria «job puntual sin ingesta, con --yaml», que es la vigente.
- **Vuelta atrás verificada en Azure (solo lectura):** `az containerapp job show … --query
  properties.template.containers[0].image` devuelve hoy `…/datamart-seg-anual:r20261116-1018`: el
  tag de la vuelta atrás es exactamente la imagen en producción.

## Checkpoints

- **C1** [x] Puerta del líder en verde sobre `99d7f13` (delta hasta HEAD: estado y papeleo).
- **C2** [x] Una sola feature activa (F-164, `in_review`), en su rama. `current.md` al día.
- **C3** [x] Hexagonal intacta (el delta de producción es una línea del dominio, sin imports
  nuevos). Cabeceras con ruta; sin `print`, TODO ni secretos; ruff limpio (el SIM300, corregido).
  `current.md` ya no lleva la ruta del scratchpad con el GUID de sesión.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C3 ter** [x] Las decisiones atribuidas llevan fecha y origen (design §9; H4 cita la review).
- **C3 quater** [x] azure-apps sin cambios en este ciclo; `f61570b` ya en `origin/main` (H3).
- **C4** [x] Cada requisito con su test, y pasan (tabla abajo). Unit tests sin red ni BBDD.
  [x] Las MANUAL (T9, T11 humano; T8, T10 líder) en `current.md` con su comando (ver O3).
- **C4 bis**
  - [x] Nivel declarado. [x] Cobertura 24/24 (umbral 90 %). [x] «Evidencias» al día.
  - [x] RED con salida real: la de la pasada 1 y, para H1, M1-M4 en «Ciclo 2» (reproducido aquí).
  - **Mutación, RM1–RM6 y supervivientes:** pendiente, pasada de evidencias (T7 tras este APPROVED).
    Los mutantes del SQL no los ve `harness.mutacion`: quedan cubiertos por la tabla de H1.
    RM7: N/A (el requisito central no es un orden entre colaboradores). Capa e2e: N/A, sin
    `servicios.json` ni requisitos `(capa: e2e)`.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5** [x] T1-T6 y T12 `[x]`, con sus commits `F-164 Tn:` y los del ciclo 2 (`F-164 H1/H4/H2`).
  T7 tras el APPROVED; T8-T11, MANUAL del despliegue.

## Cobertura: requisito → test (`tests/test_f164_*.py`)

| Req. | Tests |
|---|---|
| R1, R5, R6 | `dominio::r1_*` (23 parejas × 6 textos), `r5_una_clase_nueva…` (0-199 × 3), `r6_la_extension…` |
| R2, R3, R4, R7 | `dominio::r2_*` (5), `r3_*` (7), `r4_*` (4, con `r4_los_espacios_de_los_bordes…`) + `sql::r4_*`, `r7_*` (2) |
| R8 | `dominio::r8_los_siete…` (7, con su RED) y `r8_la_regla_de_hoy…` |
| R9, R11 | `dominio::r9_*`, `sql::r9_*` (4, **con `r9_el_case_entero_es_el_del_dominio`**), `sql::r11_*` (5) |
| R10 | `sandbox::r10_*` (6), verde con DSN en la pasada 1; equivalencia sobre los 16.088 de Azure |
| R12, R13 | `diccionario::r12_*` (9), `r13_*` (2) |
| R14-R16 | MANUAL (T10, T11). La previsión de R14, reproducida en la pasada 1: 3.349 |

## Observaciones (no bloquean)

- **O1 · Espacios Unicode** (de la pasada 1): el `\s` de `re` casa U+00A0 y el del ARE con libc no;
  hoy, 0 casos. El cambio de H4 no lo toca (el `strip(" ")` tampoco quitaba U+00A0).
- **O2 ·** `postventa.yaml:797` «Cuantos partes firmados…» contará los falsos positivos aceptados.
- **O3 · T8/T10 dependen de un fichero efímero.** `current.md` los da como `.venv/Scripts/python.exe
  <huella> antes|despues`, con el script en el scratchpad de la sesión del líder, que muere con ella.
  La consulta sí está versionada (design §7, paso 1, y T8 de `tasks.md` remite ahí), así que es
  reconstruible; recomiendo que el líder añada en `current.md` «la consulta, en design §7 paso 1».
- **O4 · Para el líder, en T7:** la campaña solo ve el dominio (el SQL ya lo cubre H1); el
  `return (texto or "").upper()` nuevo es línea cambiada y entra en el alcance.

## Automejora (propuesta, no aplicada)

- **RM8** (de la pasada 1): si en `critico` la lógica decisiva vive en SQL y su sandbox hace `skip` en
  la puerta, mutarla a mano sobre una copia (como RM7) y exigir un test de la expresión entera. En
  esta feature costó un ciclo y se resolvió con 28 líneas.
- **C4:** un comando MANUAL que dependa de un fichero fuera del repositorio debe nombrar dónde está
  versionado su contenido (O3). Una ruta de scratchpad no es un comando reproducible, y además lleva
  un GUID de sesión que `test_f003_r4` caza (`99d7f13`).
