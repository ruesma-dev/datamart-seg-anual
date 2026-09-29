<!-- progress/review_F-074.md -->
Revisión **incremental desde `bf0ace4` (pasada 2)**. La pasada 1 fue completa
sobre `4b54da9..bf0ace4`; su resultado, resumido en §3.

# F-074 · Review

**Veredicto: APPROVED.**

El único bloqueante de la pasada 1 —el análisis falso del superviviente 8— está
corregido, y corregido **midiendo**, no reescribiendo la frase. El delta de esta
pasada es **solo papeleo**: cuatro commits que tocan `BACKLOG.md`,
`harness/features.json`, `progress/current.md`, `impl_F-074.md`,
`mutacion_F-074.md` y este informe. **Ni una línea de código, de configuración
ni de tests**, así que nada de lo aprobado en la pasada 1 queda invalidado: el
alcance medido por la campaña no se mueve.

**Rigor `estandar`** declarado en `harness/features.json`: C1–C5, fase RED,
cobertura ≥ 80 % y campaña con supervivientes analizados, sin exigir cero; RM5
es N/A por nivel.

## 1 · Lo que he contrastado en esta pasada

| Qué | Resultado |
|---|---|
| `bash harness/init.sh` (entero, no incremental, sobre HEAD `7d2d8b9`) | **exit 0**. 4.162 passed, 168 skipped, 523,24 s · `BACKLOG.md` al día · PUERTA COBERTURA `[OK]` 93,6 % (788/842) · PUERTA TAMAÑO `[OK]` impl 220/220, review 133/140 |
| La tabla de los 20 mutantes que añade `mutacion_F-074.md` | **coincide fila a fila** con la muestra que reproduje yo en la pasada 1: fichero, línea, operador y los 12 muertos / 8 vivos |
| `main.py:539` no está en la muestra; el 14 es `main.py:543` | **confirmado** |
| El comportamiento medido del mutante (click) | **reproducido**: `--reconstruir-todo` → exit 2 «requires an argument»; con `--full` detrás → exit 2 «is not a valid boolean»; `run-all --full` y `run-all` a secas, **sin cambio**; `--help` muestra `--reconstruir-todo BOOLEAN` |
| Ficha F-077 (`7d2d8b9`) | existe, `pending`, prioridad 12, rigor `estandar`, con los tres criterios, el tercero el del patrón repetido en el CLI |
| `git status` | limpio |

### 1.1 · El superviviente 8, ahora bien analizado

`progress/mutacion_F-074.md` §8 retira por escrito lo que era falso —«CAZADO Y
CERRADO POR F-074», «el octavo sí era nuestro», «era el peor» y la traza, que
mutaba la 539—, dice de qué opción es (`--reconstruir-todo` de `run-all`,
código de F-025), **mide** qué hace el mutante en vez de suponerlo, y explica
por qué sus propios tests no lo ven: T15 de `tests/test_f025_cli.py` comprueba
el `--help` por substring y el cableado por `inspect.getsource`, y **nadie
invoca la opción por el parser de click**. `impl_F-074.md` §9 dice ya «los ocho
son de F-025» y «los ocho viven». Reproduje las cinco invocaciones de click y
salen exactamente los códigos y mensajes que el informe declara.

**La decisión del líder —aceptar el superviviente en F-074 y ficharlo como
F-077— es la correcta y es suya.** Rigor `estandar` no exige cero
supervivientes, exige que estén documentados y se puedan juzgar; y el arreglo
vive en `main.py` y `tests/test_f025_cli.py`, que esta feature no toca. Meterlo
aquí habría mezclado dos features y dejado una aserción sobre la ventana de
negocio colgando de un test sin criterio `acceptance` que la sostenga.
El test `test_f074_r2_la_bandera_full_de_run_all_es_un_flag_booleano` se queda,
como pedí: es correcto y mata un mutante real, el de la 539.

### 1.2 · Los otros dos cambios de la pasada 1

`progress/current.md` ya da F-072 como `done` (`e52c5f9`) en la tabla, en la
cabecera y en su sección. Corregido.

## 2 · CHECKPOINTS (recorridos enteros sobre HEAD `7d2d8b9`)

* **C1** [x] `init.sh` exit 0; los siete ficheros existen.
* **C2** [x] una sola `in_progress` (F-074); rama correcta; F-072 ya figura
  `done` y tiene su resumen en `history.md`. Único resto: el punto 6 de
  `current.md` dice del superviviente «sin fichar todavía… decidir si se ficha»,
  y ya está fichado como F-077 en el commit siguiente — una línea que el
  commit de cierre debe poner al día (observación 3).
* **C3** [x] el delta no trae código; lo revisado en la pasada 1 sigue igual.
* **C3 bis** N/A **justificado**: no se toca `docs/referencia/`. **C4 ter** N/A:
  no existe `harness/rutas_sensibles.json` (solo el ejemplo).
* **C4** [x] ocho de nueve criterios con test trazable (§3 de la pasada 1); los
  unit tests no tocan red ni BBDD; las MANUAL siguen en `current.md` con su
  comando exacto; sin dobles nuevos.
* **C4 bis** [x] rigor declarado; fase RED con traza real; cobertura `[OK]`;
  mutación verificada de forma independiente (alcance 3.527 y 288 mutantes
  recalculados en la pasada 1, muestra de 20 reproducida en las dos); sin
  «CAMPAÑA NO VÁLIDA» ni «sin veredicto». **RM1** [x] SHA `08832c4`, y los siete
  commits posteriores tocan solo `progress/`, `BACKLOG.md` y `features.json`.
  **RM2** [x] media 78,2 s × 4 workers = 312,8 s por mutante, por encima de la
  línea base de 232-236 s y ≫ 1 s. **RM3** [x] ningún equivalente declarado
  muerto —ninguno se declara equivalente—. **RM5** N/A por nivel. **RM6** [x] no
  se quitó código defensivo; el superviviente se cierra fichándolo, no borrando.
  **Los ocho supervivientes tienen análisis completado y ninguno en
  `PENDIENTE`**, que es lo que faltaba en la pasada 1.
* **C5** [x] `tasks.md` N/A por `sdd=false`; commits `F-074 Tn:` T1–T8; árbol
  limpio.

## 3 · Lo verificado en la pasada 1 (no repetido aquí, sigue válido)

* **La corrección de premisa, CONFIRMADA leyendo la fuente**: `Dockerfile` →
  `CMD ["run-all", "--full"]`; `ingest_raw_step.py:271-275` hace
  `truncate_table` con el cursor a 0 (TRUNCATE y recarga entera de **todas** las
  tablas); `incremental_column` solo decide, en la 279, si `copy_rows` rellena
  `_source_tiemod`, **no el modo de carga**; y `infra/80_create_job.ps1` y
  `85_update_job.ps1` **no sobrescriben el punto de entrada** de la imagen. La
  premisa del líder era falsa. **No se coló ningún mecanismo inventado**: el
  único `.py` de producción tocado en la rama es `config/settings.py`, y solo la
  constante `DEFAULT_EXCLUDED_TABLES`.
* **Nómina fuera del MCP, verificado sobre las sentencias**: con las cuatro
  tablas, `grants.py` emite el `REVOKE ALL PRIVILEGES ON TABLE` **después** del
  `GRANT SELECT ON ALL TABLES IN SCHEMA raw`, y el `ALTER DEFAULT PRIVILEGES ...
  REVOKE` de `raw` **se sigue emitiendo con `missing_tables`** —el caso real:
  las dos tablas aún no existen en Azure—. Privacidad en origen: `cet` sin
  `repdni` ni `repnom/repno1/repap1/repap2/repcar`, `emphis` sin `notas`.
* **Las nueve altas**: presentes, **sin duplicados** (65 entradas, 65 únicas),
  con `id_column: ide`; solo `auxdpt`, `auxhor` y `auxrestip` declaran `tiemod`
  y las seis restantes llevan `null` con VERIFICADO y fecha en el YAML; todas
  con ficha en `raw.yaml` y `pendientes: []` en los dos trinquetes.
* **Los arreglos y la limpieza**: `com`, `comlin` y `comprv` ya no declaran
  `tiemod`; `prvcer` baja de 13 a 12 exclusiones y `tex` entra; `obrprv` se
  queda con el motivo escrito y un test que fija los dos SQL de `maestro/`.
* **Barrido de secretos/IP/GUID/`print(`** sobre el diff: sin hallazgos.

## 4 · Observaciones para el cierre (no bloquean)

3. **`progress/current.md`, punto 6**: el superviviente ya está fichado como
   **F-077**; sustituir «sin fichar todavía / decidir si se ficha» por el número
   de ficha, en el mismo commit que cierre la feature.
4. **Criterio 4 (`check-raw-recuentos` en 0) no tiene test**: es MANUAL nº 2 de
   `current.md` y necesita la base, pero cabría uno barato que fije que el
   comando deriva su lista de `tables_sigrid.yaml`.
5. **La cobertura NO mide el alcance de F-074**: el porcentaje va sobre 842
   líneas de un alcance calculado contra el `merge-base` con `dev` (`cd18e09`),
   que arrastra F-025, F-066 y F-068 — el defecto ya fichado como **F-075**. Los
   ocho supervivientes de esta campaña son consecuencia directa de eso: ninguno
   está en código de F-074.
6. **Quedan las cinco verificaciones MANUAL** de `current.md`: desplegar la
   imagen y correr una nocturna comprobando el tag del job, `check-raw-recuentos`
   en 0, las cero filas de `information_schema.table_privileges`,
   `check-diccionario` y publicar la versión 17.
7. **Automejora propuesta** (no aplicada): que el informe de mutación imprima el
   **símbolo o bloque** de cada superviviente, no solo `fichero:línea`. Aquí, dos
   `is_flag=True` a cuatro líneas uno de otro en el mismo comando costaron una
   pasada entera de review.
