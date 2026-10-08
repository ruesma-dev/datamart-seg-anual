<!-- progress/review_F-085.md -->
Revisión incremental desde 4453a1d (pasada 2) · delta `1e0c9c3..3e97d78` (código del implementer en `0f7b79f`) · 2026-10-08

# F-085 · Review · APPROVED

**Veredicto: APPROVED.** Los tres cambios de la pasada 1 están hechos y los he
comprobado yo. Doy por bueno lo aprobado hasta `4453a1d`: dominio, SQL `12` y
`06`, ingesta, credenciales, diccionario, documentos, D1-D8 y desviaciones. El
informe completo de la pasada 1 está en el commit `1e0c9c3` de este mismo
fichero. El delta no invalida nada de eso: solo toca la ficha `raw.rac`, dos
tests, `impl_F-085.md` y `current.md`. No toca ningún fichero de producción,
ninguna firma pública ni el alcance de la campaña.

**Rigor:** `estandar`, declarado. Exige fase RED, cobertura ≥ 80 % de lo
cambiado y campaña muestreada (20 mutantes, semilla 20260820). No exige cero
supervivientes.

## Qué se ejecutó (resultados reales)

- `bash harness/init.sh` tal cual en `3e97d78`:
  - **exit 0**, **7.133 passed, 228 skipped** en 2.142 s (uno más que en la
    pasada 1: el `r15`);
  - `PUERTA COBERTURA [OK] 100,0 % (74/74)`;
  - `PUERTA TAMAÑO [OK]` (134/150, 245/250, impl 219/220);
  - ningún `[KO]`, `ENTORNO LISTO`;
  - árbol limpio después.
- `git diff 1e0c9c3..HEAD`, leído entero (46 líneas añadidas y 8 quitadas, en
  cinco ficheros).

## Los tres cambios pedidos

1. **[x] `config/diccionario/raw.yaml:1611`.** «, con el mismo filtro» pasa a
   «, sin filtro». En el diccionario ya no queda ningún «mismo filtro»
   (`grep`: 0). Ahora la ficha de `raw.rac` dice lo mismo en sus dos párrafos.
2. **[x] `tests/test_f085_diccionario.py:159`.** Añade
   `assert "mismo filtro" not in texto` dentro de
   `test_f085_r25_raw_rac_ya_no_va_filtrada`:
   - la fase RED está pegada en `impl_F-085.md` §8, con un `AssertionError`
     sobre el texto de `1e0c9c3`;
   - lo he cotejado: el texto de `1e0c9c3` contenía la cadena literal, así que
     la aserción fallaba antes y pasa ahora.
3. **[x] `impl_F-085.md`, «Evidencias».** Ahora dice que las 30 líneas de
   `SUB_PASOS` generan 0 mutantes y que los 49 son del dominio. Coincide con mi
   recálculo de la pasada 1 (18 + 12 + 191 líneas → 0 + 0 + 49).

**Extra, aceptado:** `test_f085_r15_los_dos_sql_remiten_a_su_oraculo_del_dominio`
da a R15 un test con su id.
- Es una guarda de texto: comprueba que cada SQL cita su oráculo.
- El literal real ya lo fijan `r6`, `r11`, `r14` y `r18`. Que no tenga fase RED
  está justificado en §8: verificaba algo que ya era verdad.
- Esto cierra la observación de la tabla de trazabilidad de la pasada 1.

**Observación, no bloquea.** Para quedarse en 219/220 líneas, el implementer
recortó seis líneas `FAILED` de los extractos RED de §3. Los extractos ya decían
«34 en total» y «extracto: 79 en total», y los totales y la salida real se
mantienen. Las líneas quitadas son del mismo tipo que las que quedan, así que
la evidencia no cambia.

## C4 bis sobre el delta

- **[x] RM1.** La campaña midió `aa5b10f`. Desde entonces, `aa5b10f..3e97d78`
  solo toca `progress/`, `specs/.../tasks.md`, `raw.yaml` y tests, nada de su
  alcance (`build_compras_step.py`, `build_personal_step.py`,
  `documento_procesos.py`). El informe de mutación sigue valiendo y no hace
  falta repetir la campaña.
- **[x] RM2, RM3, cobertura y «Evidencias»:** sin cambios desde la pasada 1.
  - Coste por mutante: 887 s con 2 workers, frente a 1.550 s de línea base.
  - 20 de 20 muertos, ninguno equivalente en la muestra.
  - La campaña **no se reejecutó**: el informe declara 8.873,9 s, por encima del
    umbral de 60 s.
- **RM5:** N/A, nivel `estandar`.
- **RM6:** N/A, no se quitó ninguna guarda.

## Checkpoints

- **C1** [x] `init.sh` exit 0 · [x] ficheros del arnés.
- **C2**
  - [x] una sola `in_progress` (F-085);
  - [x] rama `feature/F-085-quien-aprobo-que-y-cuando`;
  - [x] `current.md` solo añade lo de F-085;
  - [x] `history.md`: N/A hasta cerrar.
- **C3** [x] hexagonal, rutas en primera línea, sin `print`, TODOs, secretos ni
  dependencias nuevas, y semántica Sigrid: aprobado en la pasada 1. El delta no
  añade código de producción.
- **C3 bis** N/A: no toca `docs/referencia/`.
- **C4**
  - [x] R1-R28 con test trazable y en verde. R15 y R25 ya cerrados (tabla de la
    pasada 1, en `1e0c9c3`).
  - [x] tests sin red ni BBDD.
  - [x] MANUAL de R29-R32 con su comando en `impl_F-085.md` §6, enlazado desde
    `current.md`.
  - [x] dobles verificados por la suite verde.
- **C4 bis**
  - [x] `rigor: estandar` declarado.
  - [x] fase RED, la de las tareas y la de §8.
  - [x] cobertura 100 %.
  - [x] mutación: 221 líneas y 49 mutantes, recalculados; campaña no
    reejecutada (8.873,9 s, por encima de 60 s).
  - [x] sin «CAMPAÑA NO VÁLIDA»; «Sin veredicto» = 0.
  - [x] RM1 y RM2.
  - RM5 y RM6 N/A, con su motivo arriba.
  - [x] 0 supervivientes.
  - [x] «Evidencias» con los cuatro números y los 2 workers.
- **C4 ter** N/A: no hay `harness/rutas_sensibles.json`.
- **C5**
  - [x] T1-T11, T15 y T16 en `[x]`, cada una con su commit `F-085 Tn:`, más los
    commits de ajuste y de la review.
  - **T12-T14 son MANUAL del humano**, pendientes y bien descritas.
  - [x] árbol limpio.
  - [x] `features.json` en `in_progress`. El líder lo pasa a `done` cuando se
    cumpla lo de la sección siguiente.

## Lo que falta para `done` (humano)

1. **T12-T14 de `impl_F-085.md` §6, en el Postgres LOCAL/dev, nunca en Azure:**
   - R29: la FR26/10025 con sus 4 pasos y `nombre_usuario` en los cuatro;
   - R30: coberturas por familia y 233 / 210 / ~204 en `personal.usuarios_sigrid`;
   - R31: `retenciones.apuntes_contables` idéntica antes y después, y
     `check-raw-recuentos` en verde para `rac` y `usu`;
   - R32: tiempos de ingesta y de los dos sub-pasos.
2. **En T12, vigilar `usu.delO`**: el nombre lleva una mayúscula. Si la ingesta
   falla en esa columna, se añade a `exclude_columns`.
3. **Antes de desplegar**, enseñar al humano el coste estimado: +4 a +7 min
   sobre una nocturna que ya va 38 min por encima de las 4 h.
4. **Al desplegar:**
   - publicar el diccionario (versión 45);
   - reiniciar `mcp-bbdd`;
   - comprobar que el job corre la imagen nueva.

## Automejora (propuesta, no aplicada)

- **C4:** decidir si las MANUAL pueden vivir en `impl_F-XXX.md` con un puntero
  desde `current.md` (lo que se hace) o si el comando tiene que estar en
  `current.md` (lo que dice el checkbox).
- **C2:** `current.md` arrastra ~3.600 líneas de sesiones cerradas. O se purga,
  o se reescribe el criterio «solo la sesión activa».
- **El tope del informe del implementer (220 líneas)** empujó a recortar trazas
  RED para meter las de la review. Propuesta: que las trazas de una pasada de
  review vayan a un anexo (`impl_F-XXX_rN.md`) que no cuente para el tope.
