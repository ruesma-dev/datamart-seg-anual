<!-- progress/review_F-102.md -->
Revisión incremental desde 70d6fee (pasada 2) · delta `70d6fee..1be2672`

# F-102 · Review (reviewer, 2026-09-24)

**Veredicto: APPROVED** (APROBADO).

- Los tres cambios de la pasada 1 están aplicados y `init.sh` está en verde.
- El delta es solo papeleo: `progress/current.md`, `progress/impl_F-102.md` y
  este informe. No toca SQL, YAML, tests ni código, así que no invalida nada de lo
  aprobado, que no se vuelve a leer.
- El informe completo de la pasada 1 está en el commit 1be2672:
  `git show 1be2672:progress/review_F-102.md`.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED, cobertura
>= 80 % y mutación.

## Verificado en esta pasada

- **`bash harness/init.sh`**, tal cual. Lo lancé en primer plano con timeout
  600000; superó los 10 minutos y la herramienta lo pasó a segundo plano sin
  cortarlo, así que es la misma ejecución completa.
  - Resultado: **ENTORNO LISTO**, exit 0.
  - Tests: **5.246 passed, 191 skipped** en 1.076,15 s.
  - Puertas: COBERTURA [OK] 94,7 % (968/1022); TAMAÑO [OK] (impl 192/220).
  - Rama `hotfix/F-102-obra-duplicada-empresa-28`. Ruff: 232 avisos de deuda
    previa.
- **Cambio 1 (MANUAL con su comando)**, en `current.md`, apartado «F-102 · T16»:
  - **M1–M6** llevan la consulta SQL literal y el resultado esperado: 922/922;
    0 filas; 0581, 0606, 0671 y 0720; 1/57/48; 1.880/0; 2.618/2.618.
  - **M7**: `check-unicidad`, `check-relaciones` y `check-declarados`, con el
    recordatorio de que `check-unicidad` no mira las claves nuevas.
  - **M8**: `publicar-diccionario` v29, que lanza el humano.
  - **M9**: reinicio del MCP.
  - **Orden de despliegue** al principio: ingerir `raw.auxemp` antes de un
    `build-maestros` o `build-personal` a mano, y el riesgo de la primera noche
    en `03_views.sql`.
  - El comando que propone (`python main.py ingest --table auxemp --full`)
    existe: `main.py`, opciones `--table` y `--full` del comando `ingest`.
- **Cambio 2 (bloques de spec obsoletos)**:
  - Las líneas 1796–1857 se sustituyen por «SPEC APROBADA (resumen de la fase de
    spec)», coherente con la spec aprobada. Recoge el modelo, las columnas, que
    `compras` **no** publica `obra_principal_id`, que `stg.obras` no cambia
    (F-106), D2 A, D3, D4 y D5 A, y la regla. Remite a `spec_F-102.md`.
  - Ya no queda «pendiente de aprobacion», «T0 bloquea», «Abierta D5» ni la
    frase de `obra_principal_id` en `compras`.
- **Cambio 3 (desviación 6)**: declarada en `impl_F-102.md` (punto 6) y en
  `current.md`.
  - Dice lo que prometía la spec, por qué `check-unicidad` no lo cumple
    (`clave_negocio` = `[obra_id]`/`[recurso_id]`) y que en la base la unicidad
    la comprueban **solo** los `count(DISTINCT ...)` de M1 y M6.
  - La vigilancia permanente queda como decisión del humano, con los dos
    caminos, y no se implementa. Es lo que el líder fijó como exigible.
- **Nombres de persona**: el delta no añade ninguno; un bloque suprimido citaba al
  solicitante de negocio.
- **Mutación**: el delta no toca Python de producción. Vale el recálculo de la
  pasada 1: 0 líneas y 0 mutantes, con prueba de control de 138.

## Checkpoints (pasada 2)

- **C1** [x] init.sh en verde · [x] ficheros del arnés.
- **C2**
  - [x] una sola feature `in_progress`;
  - [x] la rama es la de `features.json`;
  - [x] `current.md` describe la sesión activa y ya no hay bloques
    contradictorios de F-102 (cambio 2). El bloque de F-101 es del mismo día y
    está cerrado, como se aceptó en F-101;
  - [x] history.
- **C3** [x] hexagonal · [x] primera línea con ruta · [x] sin prints, TODOs,
  secretos ni dependencias nuevas · [x] semántica Sigrid. Sin cambios de código
  en el delta.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4**
  - [x] R1–R10 y R13–R29 trazados y en verde; R11, R12 y R30 son MANUAL; R31 es
    init.sh;
  - [x] sin red ni BBDD;
  - [x] las MANUAL están en `current.md` (M1–M9) con su comando exacto;
  - [x] sin dobles nuevos.
- **C4 bis**
  - [x] rigor declarado;
  - [x] fase RED reproducida en la pasada 1 (86/19 y 9/1/1);
  - [x] cobertura [OK] 94,7 %;
  - N/A `mutacion_F-102.md`: la herramienta no lo escribe con alcance vacío. El
    cero está verificado por recálculo y prueba de control (pasada 1);
  - N/A reejecución, coste por mutante, cabecera NO VÁLIDA, RM1, RM2, RM6 y
    supervivientes: no hay mutantes;
  - N/A RM5, por nivel `estandar`;
  - N/A campaña manual: no se hizo. El SQL y el YAML los cubren los tests de
    texto y la medición en solo lectura de la pasada 1;
  - [x] «Evidencias» completas en `impl_F-102.md`.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5**
  - [x] T1–T15 y T17 `[x]` con commits `F-102 Tn:`. T16 es MANUAL del humano
    (M1–M9). El commit de la pasada 2 va como `F-102: cambios de la review`,
    igual que F-101;
  - [x] árbol limpio antes de este informe;
  - [x] `features.json` en `in_progress`, a la espera de que el líder cierre.

## Requisito -> test

Sin cambios respecto a la pasada 1. R1–R10 y R13–R29 tienen al menos un
`test_f102_rN_*` cada uno (118 casos) y están en verde en la suite de init.sh.
R11, R12 y R30 son MANUAL (T3, hecha; T16 = M1–M9).

## Lo que queda para el humano (no bloquea el APROBADO)

- **M1–M9** de `current.md`, empezando por el orden de despliegue. M8
  (`publicar-diccionario` v29) escribe contra Azure.
- **Decidir la vigilancia permanente** de `clave_obra` y `clave_recurso`
  (desviación 6).
- **Push** de la rama y de `azure-apps` (511ffff, 4a14173), cuando lo pida.
- **F-106**: `stg.obras` sigue eligiendo otra ficha en 0581, 0606, 0671 y 0720.

## Observaciones (no bloquean)

- Hay una línea huérfana en `current.md`: «`azure-apps`: commits `511ffff` y
  `4a14173`…». Quedó justo debajo de M9 y parece parte del reinicio del MCP. Se
  arregla al cerrar.
- Siguen en pie las dos de la pasada 1:
  - el docstring de `build_maestros_step.py` no menciona `v_obra_fichas`;
  - los `acceptance` de F-102 son anteriores a la spec. Conviene alinearlos o
    anotarlos al cerrar.

## Automejora (propuesta, no aplicada)

- Nueva casilla en C4 de `CHECKPOINTS.md`: «si la spec promete que una puerta
  de la base vigila una columna, comprobar que la puerta la lee de verdad».
- `reviewer.md` manda ejecutar `init.sh` en primer plano, pero la suite ya pasa
  de los 600 s que permite el timeout máximo. Conviene que diga «en segundo
  plano y esperar el resultado» cuando la suite supere ese límite.
