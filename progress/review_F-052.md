<!-- progress/review_F-052.md -->
# F-052 · Review de la FASE 1 (pasada 1, completa)

**Revisión completa (pasada 1)** del rango `f0d68a2..3c9826d`, 27 commits.

## Veredicto

**APROBADA LA FASE 1. El CIERRE queda PENDIENTE de la fase 2.** Ningún cambio
requerido. En términos del arnés, **CHANGES_REQUESTED al cierre** —C5 no puede
marcarse, T13/T14/T15 están sin hacer a propósito— y **APPROVED a todo lo que
hoy es juzgable**.

## Nivel de rigor: `critico` (declarado en `harness/features.json`)

**T21 (mutación) → N/A por decisión escrita del humano del 2026-08-31**,
registrada en `tasks.md` (bloque F) y en la ficha de `features.json`, como en
F-042. **El matiz consta y lo suscribo:** la campaña cubría los módulos
**Python**; el bloque B es **SQL** y nunca estuvo cubierto por ella, así que la
exención rebaja la red del dominio, no la de B. RM1, RM2, RM5 y RM6, N/A por no
haber campaña. Lo que la sustituye —las cuatro huellas— va abajo.

## Lo que verifiqué por mi cuenta, no leyendo el informe
| Comprobación | Resultado |
|---|---|
| `bash harness/init.sh` | **verde, exit 0**; 2.978 passed, 130 skipped, 273 s |
| PUERTA COBERTURA / TAMAÑO | **100,0 % de 504** líneas (umbral 80 %) · requirements 150/150, design 242/250, impl 220/220 |
| `harness.alcance` recalculado · `ruff` en los 13 ficheros nuevos | base `ab3f0f6`, 9 ficheros de producción: cubre el diff entero · **All checks passed** (los 239 avisos del repo son deuda previa ajena) |
| Dominio sin imports de infra · los 6 ficheros que la spec prohíbe tocar | limpio en los tres módulos nuevos · `git diff` **vacío** en los seis |
| **R30 · barrido de correos** en el diff entero (`…@…`, `mailto`, `AlertEmail`, `EmailReceiver`) | **cero direcciones**; el `.ps1` y el README solo llevan `<buzon>` |
| **DA-4** · `git status` | `run_all` llama al guardián y **su veredicto no entra en `sys.exit`**; a mano hace `SystemExit(resultado.codigo)`; `--dry-run` ejecutado: no abre conexión, exit 0 · árbol limpio |

### El SQL contra el motor (SOLO LECTURA, sin `TRUNCATE` ni `INSERT`)

CTE **literal** del fichero, acotado a la 0599 (legítimo: causa (c) = 0 casos):
**1.440 publicables** (R8 exacto), **1.326 CD** (hoy 3), 3 nodos sin código, **0**
filas rompen R4, **0** rutas con segmento en blanco, **0** `padre_publicado_id`
colgados (R3), **0** nodos con `nivel_bruto ≥ 39`.

**La prueba que más pesa: la huella 3, anticipada.** Ejecuté el CTE nuevo
**entero, todas las obras**, y comparé su `md5` de las seis columnas del sitio,
obra a obra, contra `stg.partidas` de HOY: **cambia UNA sola obra, la 0599
(117 → 1.440)**; las otras 734 salen idénticas al byte. Es **R6 cumplido y
R11-huella-3 pre-validado en solo lectura**, y da 389.178 − 117 + 1.440 =
**390.501**, R7 al nodo. Coincide con lo del líder del 2026-09-01, por otro
camino. No sustituye a T14: mira el árbol, no el dinero.

### Las cuatro huellas, revisadas con dureza

Ninguna de las tres consultas nuevas o cambiadas había tocado el motor: las
ejecuté en solo lectura y van (`dimension` 735×6 en 1,6 s; `cierre` 16.928×9 en
0,9 s; `mart` con `categoria` 24.684×9 en 0,7 s). El diseño aguanta: la 3 lleva
`ORDER BY p.partida_id` **dentro** del `string_agg` y `COALESCE` en las seis
columnas —sin lo primero el `md5` bailaría solo; sin lo segundo un
`capitulo_padre_id` NULL haría NULL el resumen entero de cualquier obra con raíz
y la comparación **parecería verde**—; `comparar_ampliada` recorre la **unión**
de claves, así que una obra que se cae entera sale como diferencia;
`veredicto_ampliado` da KO si **las dos** huellas están vacías; el formato lo
decide la **cabecera**, no el nombre del fichero; y la tolerancia **CERO** falla
del lado seguro, porque una obra sin ficha en `stg.obras` trae `codigo_obra`
vacío, que nunca está en la lista de esperadas.

### `sql/stg/04_partidas.sql`

R1 [x] la rama recursiva solo exige `h.cod IS NOT NULL`. R2 [x] el filtro vive
**una sola vez**, en el `WHERE publicable` del `INSERT`. R3 [x] el `CASE WHEN
a.publicable …` salta el nodo colapsado, y la raíz entra con `NULL::BIGINT`,
equivalente exacto al `NULLIF(p.padide, 0)` que sustituye. R4 [x] ruta y nivel
avanzan con el mismo `CASE`. R5 [x] `visitados` **y** `nivel_bruto < 40`, con el
tope mordiendo sobre los saltos y no sobre `nivel`, que es lo correcto. DA-1 [x]
la raíz conserva su `p.cod <> ''`. **La cabecera reescrita no promete nada
falso**: contrastada frase a frase.

## Checkpoints
- **C1** [x]. **C2** [x] (una sola `in_progress`, rama correcta; `current.md`
  conserva la sección de la spec de **esta misma** feature, no un resto ajeno).
  **C3** [x] hexagonal, SQL en su capa, ruta en la primera línea de los 13
  ficheros nuevos, sin `print` de debug ni secretos; semántica Sigrid intacta.
  **C3 bis N/A justificado**: no toca `docs/referencia/` (0 ficheros en el diff).
- **C4** [x] **en lo juzgable hoy**: R1-R6, R11, R13-R19 y R28-R30 tienen tests
  `test_f052_rN_*` que pasan; R20-R23 los cubren los tests de F-006, como pedía
  `tasks.md`; los unit tests no tocan red ni BBDD (doble `PgFalso`); las
  verificaciones MANUAL están listadas con su comando. **R7-R10, R12 y R24-R27
  no son juzgables hoy: fase 2.**
- **C4 bis** [x] con dos N/A escritos: **mutación N/A** por la exención citada y
  **RM1/RM2/RM5/RM6 N/A** por no haber campaña. Fase RED [x] con traza real en
  T1, T4, T7, T24, T28 y T30. **T29 sin RED propia: lo acepto**, porque prueba el
  mismo mecanismo de la huella 3, que entró tras la RED de T28, y la omisión está
  declarada en el informe **y** en la cabecera del fichero de test. Cobertura [x]
  100 %. «Evidencias» [x] con los cuatro números (mutantes, supervivientes y
  workers: N/A con cita). **C4 ter N/A**: no hay `harness/rutas_sensibles.json`.
- **C5** **[ ] — es el checkbox que impide el cierre**: T13, T14 y T15 sin marcar
  a propósito. Árbol limpio y `features.json` coherente. Dos commits agrupan
  tareas (`T8-T11`, `T25-T26`): trazable, lo doy por bueno.

## Las seis desviaciones de la sección 3, juzgadas
| # | Veredicto |
|---|---|
| 1 · cuarta lista `inalcanzables` | **aceptada**: no amplía alcance (dominio puro, no toca el SQL) y cierra el hueco de un nodo sin lista |
| 2 · `nombre_obra` en `FilaCobertura` | **aceptada y necesaria**: sin él la denuncia diría «obra 2824201» en las 19 sin ficha |
| 3 · excepción por `codigo_obra` O `patron_nombre` | **aceptada**; el `__post_init__` obliga a exactamente uno de los dos |
| 4 · sin tope de filas por excepción | **aceptada CON SEGUIMIENTO**: hoy la excepción de 0565, 0630 y 0686 tapa **cualquier** número de huérfanas en esas obras. **T15 fija la línea base y ahí se afina** |
| 5 · `FormatoHuella` compartido, comparación como texto | **aceptada**, mejor diseño que dos módulos calcados |
| 6 · `categoria` la última columna del CSV | **aceptada** |

## Tres observaciones que NO bloquean
1. **`check-cobertura` da verde sobre cero filas**: `Veredicto.codigo` es 0
   aunque `filas_miradas` sea 0, al revés del docstring de ese campo y de lo que
   sí hace `veredicto_ampliado`. Aquí cero filas **es** el estado sano —la
   consulta B ya filtra a `filas_mart = 0`—, así que exigirlas daría alarma
   falsa; pero un fallo que dejara las dos consultas sin resultados (tabla
   renombrada, esquema vacío) se leería como OK. Con la línea base de T15 cabe
   añadir el denominador: combinaciones (obra × ámbito) vistas en `stg`.
2. **Hay una décima excepción que T10 no pedía, la 0606 PUY DU FOU**, que la
   sección 3 del informe no declara. Justificada por escrito, marcada
   `feature: F-053` y ya en los `acceptance` de F-053: la doy por buena, pero
   debía haberse declarado.
3. **Un CSV de huella de F-042 anterior a T27** (8 columnas) ya no lo reconoce
   `comparar-huellas`: cae por la rama ampliada y muere con un mensaje confuso.
   Hoy no existe ninguno, pero conviene saberlo.

## Pendiente de la FASE 2, y hoy NO juzgable
1. **Aviso a Negocio (R27, DA-6): BLOQUEANTE.** Sin él no se publica.
2. **T14 antes de reconstruir** (el build pisa `stg.plan_mensual` y no hay vuelta
   atrás), **T13** coste real del guardián sobre producción, **T15** línea base.
3. **R11 con las cuatro huellas** y `--obras-esperadas 0599,0613,0618,0630,0565,0686`,
   más **R7-R10 y R12**. Yo pre-validé **una**, y solo el árbol: **faltan `stg`,
   `mart` con categoría y `cierre`, que son el dinero.**
4. **Desplegar `infra/96_create_alert_cobertura.ps1`**, añadir el buzón al grupo
   de acción y **comprobar que llega el correo**: sin eso el guardián es mudo,
   porque al no tumbar el job la alerta de fallo no se dispara. Riesgo (b), vivo.
5. `check-unicidad --timeout 300`, `check-cierres`, `check-diccionario`,
   `publicar-diccionario` y el aviso a quien administra Sigrid (prioridad 0686).

## Cambios requeridos: **ninguno**
## Automejora (propuesta, no aplicada)

`.claude/agents/reviewer.md` obliga a un veredicto binario y aquí no encaja: una
feature partida en dos fases por diseño —la segunda contra producción y del
humano— no es ni APPROVED ni CHANGES_REQUESTED. Propongo un tercero,
**`APPROVED_FASE_1`**, obligando a enumerar los checkpoints que quedan.
