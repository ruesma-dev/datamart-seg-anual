<!-- progress/review_F-074.md -->
Revisión completa (pasada 1) · delta `4b54da9..bf0ace4` (HEAD), rama
`feature/F-074-ingesta-tablas-del-censo`.

# F-074 · Review

**Veredicto: CHANGES_REQUESTED.** Lo que la feature entrega es correcto y está
verificado, la corrección de premisa incluida. Se rechaza **una pieza de la
evidencia: el análisis del superviviente 8 identifica mal la línea**, y con ella
cae la afirmación de que quedó cerrado. Barato de arreglar, no toca código.
**Rigor `estandar`** declarado: C1–C5, fase RED, cobertura ≥ 80 % y campaña con
supervivientes analizados, sin exigir cero; RM5 es N/A por nivel.

## 1 · Lo que he contrastado yo, con su resultado

| Qué | Resultado |
|---|---|
| `bash harness/init.sh` | **exit 0**. 4.162 passed, 168 skipped, 526,07 s |
| PUERTA COBERTURA / TAMAÑO | `[OK]` 93,6 % (788/842, umbral 80 %) · `[OK]` impl 220/220 |
| Alcance y mutantes recalculados (`harness.alcance`, `generar_mutantes`) | **3.527 líneas / 14 ficheros y 288 mutantes: idénticos al informe** |
| Muestra de 20 reproducida (semilla `20260820`) | **idéntica**; los 8 supervivientes están en ella, y los muestreados (1529 ×2, 1565, 1643, 215) reproducen texto y operador exactos |
| Duplicados en `tables_sigrid.yaml` · barrido de secretos/IP/GUID/`print(` | **0** (65 entradas, 65 únicas) · **sin hallazgos** |
| `git status` tras mis pruebas | limpio; worktree temporal eliminado |

**Campaña NO reejecutada: 1.563,8 s según el informe (> 60 s).** Vale el
recálculo puro más RM1–RM6, y así consta.

### 1.1 · La corrección de premisa: CONFIRMADA

Leído por mí: `Dockerfile` → `CMD ["run-all", "--full"]`;
`ingest_raw_step.py:271-275` → con `full_refresh` hace `truncate_table` y pone el
cursor a 0, o sea TRUNCATE y recarga entera **de todas** las tablas;
`incremental_column` solo se usa en la 279 para decidir si `copy_rows` rellena
`_source_tiemod`, **no el modo de carga**; y `infra/80_create_job.ps1` y
`85_update_job.ps1` **no sobrescriben el punto de entrada** (solo pasan
`--image`), así que el job ejecuta ese `CMD`. La premisa del líder era falsa.
**No se ha colado ningún mecanismo inventado**: el único `.py` de producción
tocado en la rama es `config/settings.py`, y solo `DEFAULT_EXCLUDED_TABLES`.

### 1.2 · Nómina fuera del MCP, las nueve altas y los arreglos

**Nómina.** La lista pasa a `raw.emp,raw.res,raw.reshor,raw.emphis` en los tres
sitios (`config/settings.py`, los tres `ARRAY[...]` de `02_roles.sql`,
`.env.example`). Leído `grants.py`: con las cuatro emite el `REVOKE ALL
PRIVILEGES ON TABLE` **después** del `GRANT SELECT ON ALL TABLES IN SCHEMA raw`,
y el `ALTER DEFAULT PRIVILEGES ... REVOKE` de `raw` —el agujero de F-068— **se
sigue emitiendo con `missing_tables`**, el caso real aquí: las dos tablas aún no
existen en Azure. Los tests lo comprueban sobre las sentencias, no sobre la
lista. Privacidad en origen: `cet` sin `repdni` ni `repnom/repno1/repap1/repap2/
repcar`, `emphis` sin `notas`.

**Las nueve** están, sin duplicados, con `id_column: ide` y `where: null`; solo
`auxdpt`, `auxhor` y `auxrestip` declaran `tiemod` y las seis restantes llevan
`null` con VERIFICADO y fecha en el YAML; todas con ficha en `raw.yaml` (65
objetos) y `pendientes: []` en los dos trinquetes. `com`, `comlin` y `comprv` ya
no declaran `tiemod`; `prvcer` baja de 13 a 12 exclusiones y `tex` entra;
`obrprv` se queda con el motivo escrito y un test que fija los dos SQL de
`maestro/` que dependen de su vacío (medición: `explore_F-074_las_nueve.md`).

### 1.3 · El superviviente 8: EL ANÁLISIS ES FALSO

El informe dice que `main.py:543 [booleano] is_flag=True, → is_flag=False,` es la
bandera `--full` de `run-all` y que el test nuevo la cierra. **No es esa línea:**

* `main.py:539` es `@click.option("--full", "full_refresh", is_flag=True,
  default=False)`; **`main.py:543` es el `is_flag=True,` de
  `--reconstruir-todo`** (F-025). Igual en HEAD y en el SHA medido `08832c4`.
* `generar_mutantes` sobre 539 da un mutante cuyo `original` es la línea
  `@click.option(...)` entera; sobre 543, uno cuyo `original` es exactamente
  `is_flag=True,` — el texto del informe. Y en la muestra de 20 reproducida con
  la semilla declarada **el mutante de 539 NO está**; el de 543, sí.
* Aplicado el mutante 543 en un **git worktree aislado** (borrado después): la
  suite da los mismos fallos que su línea base, ni un test cambia de veredicto —el
  único `is_flag` que la suite asegura es el de `--full`—. Mutando 539 en ese
  mismo worktree, el test nuevo **sí** falla: es bueno, pero mata otro mutante,
  uno que la campaña nunca evaluó.

El superviviente 8 **sigue vivo y sin análisis correcto**: «el octavo sí era
nuestro», «era el peor» y «CAZADO Y CERRADO POR F-074» son falsas — es código de
F-025, como los otros siete, cuyos análisis sí son correctos y sin `PENDIENTE`.

## 2 · CHECKPOINTS

* **C1** [x] exit 0; los siete ficheros existen.
* **C2** [~] una sola `in_progress`, rama correcta, F-072 resumida en
  `history.md`; **pero `current.md` la da «en curso, review pasada 2»** → cambio 2.
* **C3** [x] no hay código nuevo; primera línea con ruta en el test; sin prints,
  secretos ni dependencias; no se toca `amb`/`fas` ni importes.
* **C3 bis** N/A **justificado**: no se toca `docs/referencia/`. **C4 ter** N/A:
  no existe `harness/rutas_sensibles.json` (solo el ejemplo).
* **C4** [x] ocho de nueve criterios con test trazable (§3); los unit tests no
  tocan red ni BBDD; las MANUAL, en `current.md` con su comando; sin dobles.
* **C4 bis** [ ] rigor declarado, fase RED con traza real, cobertura `[OK]`,
  mutación verificada de forma independiente y sin «CAMPAÑA NO VÁLIDA»: [x].
  **RM1** [x] SHA `08832c4`, y los tres commits posteriores tocan solo
  `progress/`, `BACKLOG.md` y `features.json`. **RM2** [x] media 78,2 s × 4
  workers = 312,8 s por mutante, por encima de la línea base de 232-236 s y ≫ 1 s.
  **RM3** [x]; **RM5** N/A por nivel; **RM6** [x] no se quitó código defensivo;
  «Evidencias» completa [x]. **Falla «cada superviviente con su análisis
  completado»** → cambio 1.
* **C5** [x] `tasks.md` N/A por `sdd=false`; commits `F-074 Tn:` T1–T7; árbol limpio.

## 3 · Criterio `acceptance` → test (prefijo `test_f074_`; hay más de uno cada uno)

1 → `r1_las_nueve_tablas_estan_dadas_de_alta` · 2 →
`r2_solo_declara_tiemod_la_tabla_que_lo_tiene` · 3 →
`r3_el_revoke_se_emite_de_verdad_para_esa_tabla` y
`r3_el_revoke_sobrevive_a_que_la_tabla_no_exista_aun` · **4 → sin test**: MANUAL
nº 2 de `current.md` (observación 3) · 5 →
`r5_cada_tabla_nueva_tiene_ficha_con_el_patron_de_raw` · 6 →
`r6_ya_no_declaran_una_columna_que_no_existe` · 7 → `r7_prvcer_ya_no_excluye_tex`
· 8 → `r8_obrprv_se_queda_en_la_ingesta` · 9 → `r9_la_arquitectura_declara_las_
nueve_y_lo_que_cuestan`.

## 4 · Cambios requeridos

1. **`progress/mutacion_F-074.md` §8 y `progress/impl_F-074.md` §9: rehacer el
   análisis del superviviente `main.py:543`.** Es el `is_flag` de
   `--reconstruir-todo`, no el de `--full`. (a) Decir de qué opción es y por qué
   sobrevive; (b) retirar «CAZADO Y CERRADO POR F-074», «el octavo sí era
   nuestro», «era el peor» y la traza pegada, que muta la 539 y no el
   superviviente; (c) decidir por escrito si se tapa —bastaría extender el test
   nuevo a `--reconstruir-todo`— o se ficha con los otros siete. El test
   `r2_la_bandera_full_de_run_all_es_un_flag_booleano` **se queda**: es correcto y
   mata un mutante real (539).
2. **`progress/current.md`:** F-072 figura «en curso, review pasada 2» y está
   `done` (`e52c5f9`). Corregir la tabla y el párrafo de cabecera.

## 5 · Observaciones (no bloquean)

3. **Criterio 4 sin test.** Defendible —`check-raw-recuentos` necesita la base—,
   pero cabría uno que fije que deriva la lista de `tables_sigrid.yaml`.
4. **La cobertura NO mide el alcance de F-074**: el 93,6 % es sobre 842 líneas de
   un alcance calculado contra el `merge-base` con `dev` (`cd18e09`), que arrastra
   F-025, F-066 y F-068 — el defecto ya fichado como **F-075**.
5. **Criterio 9 es una estimación** (+3 a 6 min, +155 MB) sobre tiempos por
   página sí medidos y declarada como tal; la real la da la primera nocturna.
6. **Automejora propuesta** (no aplicada): que el informe de mutación imprima el
   **símbolo o bloque** de cada superviviente, no solo `fichero:línea`. Aquí —dos
   `is_flag=True` a cuatro líneas, en dos opciones del mismo comando— bastaba.
