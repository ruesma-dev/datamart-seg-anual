<!-- progress/review_F-107.md -->
Revisión incremental desde 68baedf (pasada 2) · delta `68baedf..f38a225`

# F-107 · Review (reviewer, 2026-09-24)

**Veredicto: APPROVED** (APROBADO).

- Los dos cambios de la pasada 1 están aplicados y `init.sh` está en verde.
- El delta toca solo papel: `config/diccionario/personal.yaml` (una frase),
  `progress/impl_F-107.md` y este informe. No hay SQL, código ni tests
  nuevos, así que no invalida nada de lo aprobado, que no se vuelve a leer.
- El informe completo de la pasada 1, con los diez puntos del encargo, los
  checkpoints C1–C5 y la tabla requisito → test, está en
  `git show f38a225:progress/review_F-107.md`.

**Rigor:** `estandar`, declarado en `features.json`. Exige fase RED,
cobertura ≥ 80 % y mutación con los supervivientes analizados.

## Verificado en esta pasada

- **`bash harness/init.sh`**, tal cual, lanzado sobre `f38a225`. La
  herramienta lo pasó a segundo plano y esperé a que terminara.
  - Resultado: **ENTORNO LISTO**, exit 0.
  - Tests: **5.300 passed, 193 skipped, 0 failed** en 1.638,28 s.
  - Puertas: COBERTURA [OK] 94,7 % (968/1022); TAMAÑO [OK] (impl 215/220).
  - Rama `feature/F-107-contrapartidas-cuentas-analiticas`. Avisos previos:
    ruff 232 y la feature `blocked` F-052.
- **Cambio 1: ficha `recursos` de `personal.yaml`, líneas 100-113.** [x]
  - La frase ambigua desaparece. Ahora dice «La contrapartida esta en
    `centro_coste_contrapartida_id` y `cuenta_analitica_contrapartida_id`».
  - El cargo queda al final y con sujeto explícito: «La cuenta del CARGO no
    esta en esta tabla: va en cada linea de parte
    (`personal.partes_lineas.cuenta_analitica_id`)».
  - Ya no hay lectura en la que el cargo parezca estar en las columnas de
    contrapartida.
  - Siguen las cifras que fija `test_f107_r1_la_ficha_dice_que_la_contrapartida_es_del_recurso`
    (1.979 y 2.619, «del recurso», «no por tipo de hora»), y el test pasa.
  - La versión sigue en 30, que es lo correcto porque no está publicada.
- **Cambio 2: tabla de la campaña manual en `progress/impl_F-107.md`.** [x]
  - Una fila por mutante, con fichero:línea, texto exacto original → mutado y
    número de tests en rojo.
  - Las líneas citadas (99-104, 100, 101 y 103) coinciden con
    `build_maestros_step.py` en HEAD.
  - **Reproduje las cuatro filas al pie de la letra** en una copia hecha con
    `git archive` en mi scratchpad, contra `tests/test_f073_pipeline.py` y
    `tests/test_f107_contrapartidas_cuentas.py`. El árbol de trabajo no se
    tocó.

    | # | Mutación | Declarado | Reproducido |
    |---|---|---|---|
    | 1 | `sql_file` → `"06_cuentas.sql"` | 4 | 4 failed |
    | 2 | `target_table` → `"cuentas"` | 1 | 1 failed |
    | 3 | `name` → `"cuentas"` | 1 | 1 failed |
    | 4 | borrar las líneas 99-104 | 3 | 3 failed |

  - Resultado: 4 generados, 4 muertos, 0 supervivientes.
  - Sigue valiendo la prueba de control de la pasada 1: `generar_mutantes`
    saca 12 mutantes del fichero entero y 0 de las 14 líneas del alcance.
    El cero de la herramienta es legítimo.
- `git status` limpio después de todo.

## Checkpoints (solo lo que cambia respecto a la pasada 1)

- **C1** [x] `init.sh` en verde sobre `f38a225`.
- **C4 bis**
  - [x] Tabla de la campaña MANUAL, con el texto exacto y cuatro filas
    reproducidas (el punto que quedaba vacío).
  - Se mantienen los N/A justificados de la pasada 1:
    - `mutacion_F-107.md`: la herramienta no lo escribe con 0 mutantes, y ese
      cero lo verificó la prueba de control;
    - reejecución, coste, RM1, RM2 y workers: no hay campaña automática;
    - RM5: nivel `estandar`;
    - RM6: no se quitó ninguna guarda.
- **Punto 10 del encargo** (cargo, no contrapartida) [x]:
  - la ficha de `partes_lineas` y la de `recursos` lo dicen ya sin
    ambigüedad;
  - la cifra de 309.182 líneas está reproducida en la pasada 1 (309.181 en
    `raw`, una línea menos que Sigrid hoy).
- **Punto 6** (mutación) [x].
- El resto de C1–C5 no cambia: queda marcado `[x]` o N/A justificado en la
  pasada 1.

## Cambios requeridos

Ninguno.

## Lo que queda para el humano (no bloquea el cierre)

- **M1–M8 y M5b** de `progress/current.md`, empezando por el orden de
  despliegue: `python main.py ingest --table caa --full` **antes** de
  cualquier `build-maestros` a mano.
- Después, `publicar-diccionario` (versión 30) y reiniciar el MCP.
- Push de la rama y de `azure-apps` (`6af6e2c` y `25cc649`, locales).
- Comprobar que la imagen del job es la nueva antes de dar F-107 por
  desplegada.

## Automejora (propuesta, no aplicada)

- En `reviewer.md`: si se para una revisión y el implementer retoma el árbol,
  la ejecución de `init.sh` en curso se descarta y se relanza sobre el HEAD
  nuevo. En la pasada 1 una suite a medias sobre un árbol que cambiaba dio un
  rojo falso (1 failed de 2.309), y se descartó por escrito.
