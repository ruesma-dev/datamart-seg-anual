<!-- progress/review_F-107.md -->
Revisión completa (pasada 1) · `main...HEAD` = `8516878..68baedf`, ampliación T8-T11 incluida

# F-107 · Review (reviewer, 2026-09-24)

**Veredicto: CHANGES_REQUESTED** (RECHAZADO). Son dos cambios, los dos
baratos y los dos en papel: el SQL, los tests y las cifras están bien.
**Rigor:** `estandar`, declarado. Exige fase RED, cobertura ≥ 80 % y
mutación.

## Lo verificado por mi cuenta (solo lecturas)

- **`bash harness/init.sh`**, tal cual (la herramienta lo pasó a segundo plano
  y esperé a que terminara): **ENTORNO LISTO**, exit 0, **5.300 passed, 193 skipped, 0 failed** en 1.587,99 s. COBERTURA [OK] 94,7 % (968/1022); TAMAÑO [OK] (impl 212/220, review 133/140).
  Descarto una ejecución anterior mía: se lanzó sobre `8237038` mientras el
  implementer hacía la ampliación en el mismo árbol, y el rojo que dio salió
  de esa carrera.
- **Postgres de producción**: `psycopg` en `read_only`, sin `_get_pg()` y por
  tanto sin bootstrap.
  - `raw.res` 2.619 = `personal.recursos` 2.619.
  - `cenconide`/`caaconide`: 1.979 cada una, 8 centros, 847 cuentas;
    0 huérfanas y 0 con `tip ≠ 19`.
  - `reshor.caaide`: 3.199 filas, 50 cuentas, 0 huérfanas.
  - `hmores.caaide`: 310.552 de 331.002 líneas, 3.782 cuentas; 0 huérfanas y
    0 de otra empresa. En **309.181** el código empieza por
    `<código de obra>.` (`LIKE` y `split_part`), y **45** líneas llevan la
    contrapartida. Sigrid da hoy 309.182 y 310.553, como la ficha.
  - Las tres cuentas del correo salen en `raw.con` como en el correo, con
    `tip = 19` y empresa 1.
  - El cuerpo de `06_cuentas_analiticas.sql`, con `raw.caa` sustituida por un
    CTE de esas tres cuentas, compila y devuelve las 12 columnas traducidas.
- **Mutación**: alcance recalculado, 14 líneas de `build_maestros_step.py`.
  - `generar_mutantes` da **0**; sobre el fichero entero (prueba de control)
    da **12**, todos fuera del alcance. El cero es legítimo.
  - Manual reproducida en una copia (`git archive`, scratchpad): `sql_file` →
    `"06_cuentas.sql"` da **4 failed** y `target_table` → `"cuentas"`
    **1 failed**, igual que el informe. `git status` sigue limpio.

## Los diez puntos del encargo

1. [x] Contrapartida desde `res`, con `NULLIF … 0`, sin JOIN ni WHERE nuevos
   (el test cuenta 4 JOIN). No pierde filas: 2.619 = 2.619.
2. [x] El catálogo no filtra (lo fija un test). `R-CODIGO-POR-EMPRESA` lo
   recoge en `ambito` y en la ficha (14.063). Traduce las tres del correo.
3. [x] Padre desde `con`: justificado, porque `cag` no se ingiere. `LEFT JOIN`
   por PK: no multiplica ni pierde el nivel 1. Declarado (decisión 3).
4. [x] F-057 r13 descuenta **una** proyección literal (`count == 1`) y sigue
   vetando `cenconide`, `cenide` y `maestro.centros_coste` en los dos
   ficheros. F-102 r26/r27 **exigen** que la cola sean las columnas de F-107.
   r13/r20 pasan a `>=`, y «69 tablas» (r28/r29) lo vigilan ahora
   F-066/F-074/`test_f107_r4` con 70. Patrón F-102/F-080: no aflojan nada.
5. [x] Despliegue: la vista es el último sub-paso y ningún step depende de
   `build_maestros`. Documentado en el SQL, el docstring, ARCHITECTURE,
   `current.md` y `azure-apps`; el comando `ingest --table caa --full` existe.
6. [ ] Mutación: cero legítimo y muertos reales, pero sin la tabla que pide
   C4 bis (**cambio 2**).
7. [x] `azure-apps` `6af6e2c` + `25cc649`, locales, completos y sin push.
8. [x] Barrido `[A-ZÁÉÍÓÚÑ]{3,}( [A-Z…]{2,})+` y `'[A-Z][^']{3,}'` sobre las
   líneas añadidas: solo conceptos (JEFE DE OBRA, CENTRO PERSONAL). «Juan
   Romero» es el solicitante interno, ya citado 93 veces en `main`.
9. [x] Ampliación: `ADD COLUMN IF NOT EXISTS` sin DROP, e INSERT con las
   columnas nombradas. Los guardas de F-057 (`\braw\.hmo\b` no casa con
   `raw.hmores`) y de F-101 siguen en verde sin tocarlos. `05_views.sql` usa
   columnas explícitas. La relación va en los dos sentidos y el criterio está
   en `acceptance`.
10. [ ] Cargo, no contrapartida: la cifra se reproduce y la ficha de
    `partes_lineas` lo dice bien. La de `personal.recursos` quedó ambigua
    (**cambio 1**).

## Checkpoints

- **C1** [x] `init.sh` · [x] ficheros base.
- **C2** [x] una `in_progress` · [x] rama · [x] histórico · [x]
  `current.md`: F-107 encabeza el fichero; lo viejo es deuda previa,
  aceptada en F-101/F-102.
- **C3** [x] capas (`maestro/`, `personal/`, dato en `application`) ·
  [x] ruta en primera línea · [x] sin prints, secretos ni dependencias ·
  [x] R-SIGRID-CON y NULLIF 0.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4** [x] trazabilidad (tabla abajo, 39 tests `test_f107_*`) · [x] sin red
  ni BBDD · [x] MANUAL M1–M8 y M5b con su comando · [x] sin dobles nuevos.
- **C4 bis**
  - [x] Rigor · [x] RED con la traza real (base y ampliación) ·
    [x] cobertura `[OK]` · [x] «Evidencias».
  - N/A justificados:
    - `mutacion_F-107.md`: con 0 mutantes la herramienta no lo escribe, y el
      cero está verificado con la prueba de control;
    - reejecución, coste, RM1, RM2 y workers: no hay campaña automática;
    - RM5: nivel `estandar`;
    - RM6: no se quitó ninguna guarda.
  - [ ] **Tabla de la campaña MANUAL** con el texto exacto original → mutado
    (**cambio 2**).
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5** N/A `tasks.md` (sdd=false): hay commits `F-107 Tn:` de T1 a T11 ·
  [x] sin temporales · [x] `features.json`.

## Cobertura requisito → test

| Criterio | Tests |
|---|---|
| 1 contrapartida | `test_f107_r1_*` (11) + `test_f057_r13_*` |
| 2 `caa` y catálogo | `test_f107_r2_*` (14) + `test_f073_*` |
| 3 casamiento y las tres del correo | `test_f107_r3_*` (6) |
| 4 diccionario, yaml, recuentos, azure-apps | `test_f107_r4_*`, `r2_las_cabeceras_cuentan_70`, F-066/F-074 |
| 5 ampliación | `test_f107_r5_*` (5) |

## Cambios requeridos

1. **`config/diccionario/personal.yaml:104-106`** (ficha `recursos`, párrafo
   «LA CONTRAPARTIDA ES DEL RECURSO»).
   - La frase «La cuenta del CARGO esta en cada linea (…).» va justo antes de
     «Esta en `centro_coste_contrapartida_id` y
     `cuenta_analitica_contrapartida_id`».
   - Leído de corrido, ese «Esta en» se refiere al CARGO: es justo la
     confusión que la ficha evita, y el MCP la lee tal cual.
   - Arreglo: llevar la frase del cargo al final del párrafo, o escribir «La
     contrapartida esta en…».
   - La versión 30 no está publicada: no hay que subirla.
2. **`progress/impl_F-107.md`, «Evidencias» → Mutación.** La campaña manual
   va como **tabla**, con una fila por mutante: fichero:línea, texto exacto
   original → mutado (p. ej. `sql_file="06_cuentas_analiticas.sql"` →
   `sql_file="06_cuentas.sql"`) y número de fallos.
   - Para «borrar el sub-paso», las líneas exactas: 99-104 de
     `build_maestros_step.py`.
   - Hoy es un párrafo, y C4 bis no lo admite. Los números son ciertos: solo
     cambia el formato.
   - El informe va por 212/220 líneas: hay que compactar otra cosa.

## Automejora (propuesta, no aplicada)

- En `reviewer.md`: si se para una revisión y el implementer retoma el árbol,
  la ejecución de `init.sh` en curso se descarta y se relanza sobre el HEAD
  nuevo. Hoy una suite a medias sobre un árbol que cambiaba dio un rojo falso.
