<!-- progress/review_F-101.md -->
Revisión incremental desde d28179c (pasada 2) · delta `d28179c..d7fe12b`

# F-101 · Review (reviewer, 2026-09-23)

**Veredicto: APPROVED** (APROBADO). Los tres cambios de la pasada 1 están
aplicados según las decisiones del humano del 2026-09-23. `init.sh` está en
verde. Lo aprobado en la pasada 1 no se vuelve a leer. El delta no cambia
firmas, ni ficheros de alcance medido, ni SQL ejecutable: solo un comentario de
`04_recursos_tipos_hora.sql`. El informe completo de la pasada 1 está en el
commit 0ea8358 (`git show 0ea8358:progress/review_F-101.md`).

**Rigor:** `estandar`, declarado en `harness/features.json`. Exige fase RED,
cobertura >= 80 % y mutación.

## Verificado en esta pasada

- `bash harness/init.sh` tal cual: **ENTORNO LISTO**, exit 0. `5113 passed,
  189 skipped` en 1.325,29 s. PUERTA COBERTURA [OK]: 94,7 % (968/1022). PUERTA
  TAMAÑO [OK]. Rama `hotfix/F-101-cabecera-del-parte`. Ruff: 232 avisos de
  deuda previa.
- **Cambio 1, opción (b):**
  - Las cuatro frases dicen ya la verdad y fechan la aceptación del
    2026-09-23:
    - `config/tables_sigrid.yaml`, bloque `hmores`: «NO vive solo en
      `personal`», el SELECT del rol, «ACEPTADA POR EL HUMANO EL
      2026-09-23», y cómo cerrarlo;
    - `personal.yaml`, `texto_linea`: «No vive solo aquí… `raw.hmores`…
      aceptada… el 2026-09-23». Desaparece «restringible»;
    - `raw.yaml`, `raw.hmores`: «puede llevar nombres de persona AQUI», con
      la aceptación y los dos atenuantes;
    - `azure-apps` **953e9fb**: nota nueva bajo «`hmores` recuperó `tex`».
      Verificado en ese repositorio: árbol limpio y sin push.
  - No se revoca nada: `raw.hmores` sigue fuera de `DEFAULT_EXCLUDED_TABLES`.
  - Test nuevo `test_f101_r16_la_exposicion_en_raw_esta_declarada_y_aceptada`.
    Exige la declaración con fecha en las tres fichas/configs y veta
    «restringible» y «se publica solo en el esquema». Además fija la no
    revocación, de modo que un cambio futuro obliga a reescribir la ficha. No
    toca red ni BBDD: solo importa una constante de `config.settings`.
- **Cambio 2, opción (b):** commit NUEVO 0ea8358, sin reescribir el
  historial.
  - `git grep` sobre HEAD de los dos literales de nombre: **0 coincidencias**
    en todo el árbol versionado.
  - Redactado en `requirements.md:78`, `design.md:195` y
    `progress/spec_F-101.md:34`.
  - También en este mismo informe. El literal venía de mi pasada 1: citar el
    nombre al pedir que se quitara fue un error mío. El implementer lo
    redactó al commitear y lo dejó anotado entre corchetes.
  - Los commits anteriores a 0ea8358 lo conservan. El humano lo asume.
- **Cambio 3:** `progress/current.md` cumple.
  - Lista M1–M10 con su comando exacto, M9 primero y con su motivo.
  - Ha desaparecido el bloque de decisiones abiertas y la frase «pasa a
    `spec_ready`».
  - Recoge las dos decisiones del humano.
  - M6 trae además una consulta concreta con `DISTINCT ON` para no duplicar
    los 17 pares repetidos.
- **Observaciones de la pasada 1, atendidas sin que fuera obligatorio:**
  - la ficha de `partes_lineas` solo cita 615 líneas en 14 partes, con fecha;
  - el SQL y el docstring de `r25` usan el código MO/0306 en vez del nombre.
  - La de `tipo_hora_de_baja` queda anotada y es razonable: Sigrid guarda 0,
    no NULL.
- **Mutación:** el Python de producción del alcance no cambia en el delta.
  Solo cambian YAML, SQL (un comentario), tests y documentos. Por eso sigue
  valiendo el recálculo de la pasada 1: 38 líneas, 0 mutantes, y la prueba de
  control da 12 y 949.

## Checkpoints (pasada 2)

- **C1** [x] init.sh en verde · [x] ficheros del arnés.
- **C2**
  - [x] una sola `in_progress`;
  - [x] la rama es la que declara `features.json`;
  - [x] `current.md` ya solo describe la sesión activa de F-101 (el bloque de
    F-094 es del mismo día y previo, y está cerrado);
  - [x] history.
- **C3** [x] hexagonal · [x] primera línea con ruta · [x] sin prints, TODOs ni
  secretos · [x] semántica Sigrid. Sin cambios de código en el delta.
- **C3 bis** N/A: el delta no toca `docs/referencia/`.
- **C4**
  - [x] R1–R30 trazados. R16 gana un test y `r29` sigue en verde;
  - [x] sin red ni BBDD;
  - [x] MANUAL en `current.md` con su comando exacto;
  - [x] dobles sin cambios (`_PgFalso` ya verificado en la pasada 1).
- **C4 bis**
  - [x] rigor declarado;
  - [x] fase RED: reproducida en la pasada 1 sobre 4233c72 (45 failed,
    5 passed, 1 skip). El test nuevo de R16 es una guarda documental que se
    añade junto con su corrección;
  - [x] cobertura [OK] 94,7 %;
  - N/A `progress/mutacion_F-101.md`: la herramienta no lo escribe con 0
    mutantes. Cero verificado por recálculo y prueba de control;
  - N/A reejecución, coste por mutante, cabecera NO VÁLIDA, RM1, RM2, RM6 y
    supervivientes: no hay mutantes que juzgar;
  - N/A RM5, por nivel `estandar`;
  - N/A campaña manual: no se hizo. Lo cambiado es SQL/YAML, cubierto por
    tests sobre el texto y por el step contra un doble;
  - [x] «Evidencias» actualizadas en `impl_F-101.md` con 5.113 tests, la
    cobertura y el tiempo.
- **C4 ter** N/A: no existe `harness/rutas_sensibles.json`.
- **C5**
  - [x] T1–T13 `[x]` con commits `F-101 Tn:`. Los cuatro commits de la
    pasada 2 van como `F-101: … cambio N de la review`, igual que F-094;
  - [x] árbol limpio antes de este informe;
  - [x] `features.json` en `in_progress`, a la espera de que el líder lo
    cierre.

## Requisito -> test

Sin cambios respecto a la pasada 1: R1–R30 tienen al menos un
`test_f101_rN_*` cada uno; la tabla completa está en 0ea8358. R16 suma
`test_f101_r16_la_exposicion_en_raw_esta_declarada_y_aceptada`. Todos están
en verde en la suite de init.sh.

## Lo que queda para el humano (no bloquea el APROBADO)

- **M1–M10** de `progress/current.md`, con **M9 antes que M1**. M10
  (`publicar-diccionario`, versión 28) es escritura contra Azure.
- **Push** de `azure-apps` (87dc629 y 953e9fb) y merge de la rama, cuando lo
  pida.
- **Historial:** el nombre redactado sigue en los commits de la rama
  anteriores a 0ea8358 (desde fd4f706). Si se mergea sin squash, llega a
  `main`. Está aceptado, y lo repito aquí para que se vea al mergear.

## Observación (no bloquea)

- `design.md:195` y `requirements.md` R16 siguen diciendo «vive en `personal`,
  el esquema restringible». Es la premisa con la que se aprobó la spec, y el
  humano no la incluyó entre las frases que había que corregir. Queda como
  registro histórico del diseño. La verdad vigente está en las tres
  fichas/configs y en `azure-apps`.

## Automejora (propuesta, no aplicada)

1. **Casilla nueva en C3:** «si se ingiere en `raw` una columna con datos
   personales, comprobar con `has_table_privilege` el acceso del rol de
   consumo a esa tabla». El diseño razonó por esquemas, y en `raw` los
   privilegios son por tabla.
2. **Regla nueva en `reviewer.md`:** «al pedir que se redacte un dato
   personal, no citar el literal en el informe de review». En la pasada 1 lo
   hice yo mismo, y el informe se versiona.
