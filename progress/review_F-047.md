<!-- progress/review_F-047.md -->
Revisión completa (pasada 1) de `aea1307..82b58cf`, 7 commits, 33 ficheros.

# F-047 (absorbe F-044) · Review · rigor `critico`

## Veredicto: **RECHAZADO**

**Código, tests y campaña quedan APROBADOS y no necesitan retoque.** Rechazo por
**seis afirmaciones en presente** del commit `ca0bc9e` en
`azure-apps/datamart_seg_anual.md`, hoy **falsas en producción**, más la secuencia
de publicación del diccionario. Arreglo de minutos, en documentación.

No rechazo por el despliegue congelado —decisión del humano, y el dato llegó
después de implementar—, sino porque el documento que el ecosistema lee para
saber **qué está desplegado** afirma que la vista de Power BI ya no se destruye,
y **se sigue destruyendo cada noche**.

`critico` exige C1–C5 + fase RED + cobertura + **cero supervivientes** +
verificaciones `MANUAL` con comando y resultado.

## Puertas y checkpoints

`bash harness/init.sh` **VERDE**: 2.581 pasados, 128 saltados, 421 s. `PUERTA
COBERTURA` **[OK] 100,0 % de 259 líneas cambiadas** (umbral 80 %). `PUERTA TAMAÑO`
**[OK]**. `ruff` 238 = 237 de base **+1** (`noqa: E402` inerte). **Fase RED**:
trazas reales pegadas para los dos alcances en `impl_F-047.md`.

| | | Nota |
|---|---|---|
| **C1** | `[x]` | exit 0; los siete ficheros obligatorios existen |
| **C2** | `[x]` | una sola `in_progress`; rama correcta |
| **C3** | `[x]` | ruta en la 1ª línea de los 8 ficheros nuevos; sin `print()` de debug; `inventario_repositorio.py` es adaptador en `infrastructure/` e importa de `domain/`, nunca al revés; sin dependencias nuevas |
| **C3 bis** | `N/A` | **justificado**: el diff no toca `docs/referencia/` y `git log --diff-filter=A` no añade ningún PDF/ofimática en la rama |
| **C4** | `[x]` | 9 criterios → 48 funciones (77 casos); ninguno toca red ni BBDD |
| **C4 bis** | `[x]` | ver abajo |
| **C4 ter** | `N/A` | **justificado**: no existe `harness/rutas_sensibles.json`; sin declaración el bloque es N/A por diseño |
| **C5** | `[~]` | commits `F-047 Tn:` correctos; `tasks.md` N/A (`sdd=false`). Ver cambio 3 |

**Barrido de secretos**, dos pasadas (líneas añadidas y contenido completo de los
37 ficheros). Patrones: contraseñas y cadenas de conexión, claves y tokens
(`api[_-]?key|secret|token|bearer|-----BEGIN|eyJ|sk-`), GUID, IPs, correos y
base64 largo. **CERO secretos**: los hits son prosa, nombres de rol, rutas y
dos SHA de git; `.env` no trackeado y el diff no lo añade.

## Mutación · C4 bis

**Recalculado, no leído del informe.** `harness.alcance` da **831 líneas en 12
ficheros**, idénticas fichero a fichero; `generar_mutantes` da **exactamente 70**.
Muestreé **los 7 supervivientes**: existen como mutantes reales, con el mismo
operador y el mismo texto original→mutado.

- **Campaña NO reejecutada**: «Tiempo total» **9.117,3 s (2 h 32 min)**, muy por
  encima de los 60 s. Aplico recálculo puro + RM1–RM6, y lo digo como pide C4 bis.
- **RM1.** Mide `977b957`; HEAD es `82b58cf`. **Verificado, no supuesto**: ese
  commit toca solo `progress/` y cuatro ficheros de test, y el alcance recalculado
  **hoy en HEAD** sale idéntico (831/12). Añadir tests solo mata.
- **RM2.** Workers **1** → coste real por mutante **130,2 s** contra línea base
  **185,7 s**: sin salto de orden de magnitud (0,70×), y la media bajo la base es
  el caso de libro (con `-x`, 63 de 70 muertos abortan al primer fallo).
  `70 × 130,2 = 9.114 ≈ 9.117,3` ✓. Timeout 372 = 185,7 × 2,0 ✓.
- Sin «⚠ CAMPAÑA NO VÁLIDA»; «Sin veredicto (base rota): 0» ✓. **Cero
  supervivientes finales**. **RM3** y **RM5** N/A: cero equivalentes declarados.
- **RM6.** Las únicas guardas que el diff borra (`if not (sql_dir/f).exists()`,
  `except Exception`) caen con el bloque en línea de `build-compras`/
  `build-retenciones`, y **reaparecen en los steps nuevos** con test propio.
- **RM4 · falso superviviente.** El test citado existe y hace lo que dice:
  `_r4_cuenta_las_filas...:121` afirma `rows_processed == 11 * len(contados)` (2
  tablas → 22; el mutante da 23). Falso superviviente EN SERIE: nuevo en F-041.

## Trazabilidad · criterio → test (`sdd=false`: los 9 de F-047 **y** F-044)

Los nueve tienen cobertura y los `test_f047_rN_*` siguen esa numeración:
**F-047·1** `explore_F-047.md` + `_r2_build_cierre_corre_despues_de_build_mart`;
**·3** `_r5_*` (4), `_r7_*` (6), `_r8_*` (10); **·4** `_r8_cli_*`. **F-044·1**
`_r1_*`, `_r2_*`, `_r3_*`; **·2** `_r4_*` (8). Los otros cuatro son **MANUAL**:
**F-044·3** y **·4** medidos el 2026-08-21 (+37,5 min, 2 h 46 → 3 h 24; disco
57,92 → 57,93 %); **F-047·2** y **F-044·5** los verificó el líder (103/102).

## Los cinco puntos del encargo

1. **Decisión 2 bien pagada**, con red doble. `test_f005_grants.py` **no se tocó**
   (`--stat` vacío) y sigue fijando `depends_on == ["build_mart"]` y **`orden[-1]
   == "apply_grants"`**; `_r3_publicar_y_grants_van_despues_de_los_cuatro_build`
   añade que los cuatro le preceden **en el orden topológico**, no en la lista.
   Verifiqué el mecanismo (DFS post-order sobre `self._steps`: nadie depende de
   `apply_grants` y va última) y lo que nadie declaraba: los cuatro esquemas
   **están** en `DEFAULT_CONSUMPTION_SCHEMAS`, luego sus `GRANT` se reaplican.
2. **Los nueve ficheros de test, contra el diff y no contra el resumen.** Ninguno
   se tocó para que pasara: el veredicto lo dicta la composición real, porque
   `_validar_frescura` compara contra `main.build_pipeline_steps`. Tres merecían
   mirada y la aguantan: `_una_ficha_cuyo_paso_no_deja_rastro_lo_advierte` se
   **invierte a un contrato más fuerte** (ningún `paso_etl` fuera de los
   registrables) en vez de relajarse; `f006_formato` fija que `aux` sigue siendo el
   único `estatico`; `f024_cli` ancla el `== 6` a `len(build_pipeline_steps(...))`.
3. **`R-FRESCURA` dice la verdad contra el código.** Enumera los **diez** pasos con
   el nombre que tienen en `_meta.v_frescura.paso`, y
   `test_f006_r9_la_regla_de_frescura_cita_el_pipeline_real` lo fija solo. La vista
   **no** tiene lista cableada (`ddl/00_meta.sql:70`, genérica sobre
   `etl_runs.step`), luego la consulta que manda hacer funcionará. **40** fichas a
   `nocturno` (cierre 12, compras 14, maestro 4, retenciones 10) + 4 bloques de
   esquema = las 44 del diff, y coinciden con el inventario por esquema.
4. **Guardián correcto, y el `pendientes: []` vacío es REAL** — no me fié del
   comentario del YAML: contrasté el parser contra un regex independiente sobre
   `sql/**` y da **72 objetos idénticos, cero diferencia en ambos sentidos** (el 76
   del grep crudo son tres declarados dos veces). No hay `CREATE` sin esquema
   cualificado ni tablas temporales que perder; 72 + 31 de `raw` = **103**. El
   trinquete rompe la puerta en ambos sentidos, y un fallo **leyendo** da `False`.

## Cambios requeridos

1. **`azure-apps/datamart_seg_anual.md` (`ca0bc9e`): añadir la salvedad del
   despliegue.** Ese repositorio documenta lo **desplegado** y lo leen otros
   equipos. Falsas hoy: `:194` «ejecuta **diez pasos**» (ejecuta seis), `:202`,
   `:216-217` «el final se mueve a 05:24 UTC» (sigue en 04:46), `:220` «los cuatro
   registran fila en `_meta.etl_runs`» (no registran ninguna) y `:243-245` «sale
   con código 1». **La más grave es `:210`**: «la nocturna la DESTRUÍA cada noche
   y nadie la recreaba», en pretérito, cuando **la sigue destruyendo**; quien
   investigue el hueco de Power BI cerrará el caso en falso. Basta un párrafo
   separando «lo que hace el código» de «lo que hará al redesplegarse», nombrando
   la imagen que corre hoy (`datamart-seg-anual:r20260818-2146`).
2. **Escribir la SECUENCIA de las acciones manuales en `current.md`.**
   `R-FRESCURA` promete que la fecha de build de los cuatro «siempre es
   consultable», y `_meta.v_frescura` **no tiene hoy ninguna fila** de
   `build_compras` ni `build_retenciones`. Publicarlo **antes** de desplegar y
   correr una noche haría que el MCP sirviera una regla bloqueante que manda una
   consulta vacía — mentira nueva del tipo que F-047 mata. Orden: imagen →
   nocturna → `publicar-diccionario`. Hoy no hay daño (`_meta` sirve la 9).
3. **`current.md` al día y `features.json` sin ensuciar.** `current.md` dice
   «pendiente de conexión» cuando el líder ya verificó contra la base, y no cita el
   despliegue congelado, hoy la condición de cierre principal. Y `features.json`
   perdió el salto de línea final.

**Ninguna conclusión mía depende de la base.** Para **cerrar** faltan, y son del humano: `build-cierre` (sin lanzar), `publicar-diccionario` e **imagen nueva**.

## Automejora (propuesta, no aplicada)

`harness/mutacion.py` debería **borrar el bloque `Análisis (PENDIENTE del
implementer)`** cuando el implementer añade el suyo: aquí los 15 supervivientes
están resueltos y el informe sigue diciendo siete veces `PENDIENTE`, que es justo
lo que C4 bis manda buscar. Trampa para el próximo reviewer con `grep`.
