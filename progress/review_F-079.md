<!-- progress/review_F-079.md -->
# F-079 · Review — todo lo publicado es consultable

**Revisión completa (pasada 1)**, delta `880b4fe..HEAD` (`a407fdd`).

## Veredicto: APPROVED

**Rigor `estandar`**, declarado en `harness/features.json` (no heredado por
omisión): exige C1–C5, fase RED, cobertura y campaña de mutación con los
supervivientes analizados; **no** exige cero supervivientes. `sdd=false`: se
revisa contra los seis `acceptance`, y `tasks.md` es N/A por la cabecera de
`CHECKPOINTS.md`.

## Los seis criterios, con lo que contrasté yo

1. **Los 7 de `stg`, recomendados y sin motivo** `[x]`. Cargué el diccionario y
   conté: **7/7 en `true`**, ninguno conserva `motivo_no_consumo`; fuera de `raw`
   quedan **20** = **11 funciones + 9 rotos** (el reparto del encargo, 10+10,
   estaba mal; lo corrigió el implementer y lo confirmo). Consumo: **54** fichas.
2. **Ninguna advertencia de corrección se pierde** `[x]`. Sección propia.
3. **Grupos B y C inventariados, y lo no tocado justificado** `[x]`. En
   `config/` **solo cambian `stg.yaml` y `00_global.yaml`**: `mart.yaml` está
   intacto, luego **`mart.v_pbi_cp_tipologia` NO se tocó** — es de F-078, otra
   sesión. Los 20 conservan su motivo, como exige R3.
4. **`check-diccionario` en 0 y biyección** — **MANUAL (humano)**: exige
   conexión. Offline sí verifiqué que `validar(dicc,
   pasos_del_pipeline_nocturno())` sobre el diccionario real da **0 errores**.
5. **La versión sube y se publica** `[x]` / pendiente. Árbol en **18**,
   `hash_fuente` `4af4c3bb60d4`, changelog en la cabecera; **publicar sigue
   pendiente** (§Despliegue).
6. **El MCP enruta a `stg`** — **MANUAL (humano)**: no se puede medir antes de
   publicar. Declarado pendiente, no cumplido. El 4 y el 6 no tienen test propio
   **y no pueden tenerlo**; están en `current.md` con su comando exacto, que es
   lo que C4 pide de una MANUAL.

## Las advertencias, una a una (el riesgo entero de la feature)

Comprobado cargando el diccionario y **derivando los avisos con `derivar_avisos`**
—lo que hace `publicar_diccionario` antes de escribir—. `descripcion`, `avisos`,
`motivo_no_consumo` y `ficha` son **todas** columnas de `SQL_INSERT_DICCIONARIO`.

| Advertencia | Llega desde (verificado por mí) |
|---|---|
| `plan_mensual` multiplica importes | **tres vías**: `descripcion` («MULTIPLICA», con «sin filtrar version» y el puntero a `mart.fact_seguimiento_mensual`); `avisos` derivados = `R-VERSION-MASTER` (bloqueante, `ambito` incluye la tabla) **y** `R-COSTE-CONSULTA`; `para_que_sirve` del esquema `stg` |
| `obras.activa` no significa nada | **tres vías**: `descripcion`; `significado` de la columna («NO SIGNIFICA NADA»); `avisos` = `R-OBRA-ACTIVA` |
| `version_master_vigente` GLOBAL, y `ambitos.uso_seguimiento` desfasada | la primera solo por `descripcion` (esa ficha **no tiene avisos derivados**); la segunda por `descripcion` + `significado` de la columna. **Son las dos que solo vivían en el motivo**: se habrían perdido |

**Confirmo el hallazgo: eran cuatro, no dos.** Repasé los siete motivos borrados
frase a frase: lo único que desaparece es «es capa intermedia» y «es un catálogo
de apoyo del build» —preferencia pura—, y **todos los punteros aguas abajo se
conservan como navegación**. Ninguna frase que se quedó es preferencia
disfrazada, y los `ejemplos_preguntas` tampoco invitan a la consulta peligrosa.

## Checkpoints

- **C1** `[x]` — `bash harness/init.sh` lanzado por mí, **exit 0**: arnés
  v1.7.7, **4215 passed, 168 skipped en 463,29 s**, `PUERTA COBERTURA [OK]`,
  `PUERTA TAMAÑO [OK]`; los siete ficheros existen. Avisos preexistentes y
  ajenos: 216 de `ruff` y **F-052 en `blocked`**.
- **C2** `[x]` — una `in_progress`; rama correcta; `current.md` es de la sesión
  activa; árbol limpio salvo este informe.
- **C3** `[x]` — `git diff --name-only 880b4fe..HEAD -- '*.py'` devuelve **solo
  dos ficheros de `tests/`**: cero Python de producción y cero SQL, la
  arquitectura hexagonal no se toca. Primera línea con ruta; sin prints, sin
  secretos, sin dependencias. **Semántica Sigrid: verifiqué contra el SQL las dos
  afirmaciones nuevas que se publican** — `06_presupuesto.sql` no filtra por
  ámbito (único `WHERE`: `obride IS NOT NULL`) y `08_plan_mensual.sql` solo
  construye 3, 7, 8 y 11—, luego «la certificación solo está aquí» es cierto.
- **C3 bis** `N/A` justificado — `git diff ... -- docs/` vacío: no entra ningún
  documento de fuera, luego no hay cabecera ni barrido de sensibles que hacer.
- **C4** `[x]` — **53 tests** propios (`--collect-only`: 53 collected),
  `test_f079_rN_*`, trazables a los criterios 1, 2, 3 y 5; el 4 y el 6 son
  MANUAL. Nada toca red ni BBDD. **Ningún doble de test nuevo**: ese punto no
  aplica a este delta.
- **C4 ter** `N/A` sin nada que justificar: no hay `harness/rutas_sensibles.json`.
- **C5** `[x]` — `tasks.md` **N/A por `sdd=false`**; cinco commits `F-079 Tn:
  ...`; sin artefactos sueltos; `features.json` refleja el estado real.

## C4 bis · el rigor declarado, comprobado y no creído

- **Fase RED** `[x]` — el test se commiteó **solo y en rojo** en `ee2e9bf` (412
  líneas, un fichero, antes de tocar el YAML) y el informe pega la salida real:
  19 fallos de 54. **Corroborado**: en `ee2e9bf` el árbol declaraba `version: 17`
  —de ahí el `assert 17 >= 18`— y `stg.yaml` tenía **10** `false`. Los mensajes
  pegados son los de las aserciones del fichero.
- **Cobertura** `[x]` — `[OK] 93.6 % de 842 líneas cambiadas (788/842, umbral
  80 %)`. Mide alcance heredado, no el de F-079 (defecto F-075); verde igual.
- **Mutación** `[x]` — **recalculado por mí**: `harness.alcance` da **3.527
  líneas en los mismos 14 ficheros y con el mismo reparto**, y `generar_mutantes`
  sobre ellos, **288 mutantes**: coinciden. El muestreo de 20 con semilla
  `20260820` es el que `rigor.json` fija para `estandar`.
- **Muertos** `[x]` con salvedad escrita: **campaña NO reejecutada** —«Tiempo
  total» **2.239 s**, muy por encima del umbral de 60 s—, así que aplico
  recálculo puro + RM1–RM6. **Muestreé los ocho supervivientes: los ocho existen
  como mutantes reales**, mismo operador y mismo texto original→mutado
  (`postgres_client.py` 1529 [entero] y [logico], 1551, 1565, 1585, 1643;
  `ventana_sql.py:215`; `main.py:543`). Sin «CAMPAÑA NO VÁLIDA»; base rota = 0.
- **Coste por mutante y RM2** `[x]` — 2.239 s × 4 workers ÷ 20 = **447,8 s**, y
  media 111,9 × 4 = 447,6 s, contra una línea base de 354,6 s: por encima de la
  base, sin salto de orden de magnitud. Timeout efectivo 710 s, derivado.
- **RM1** `[x]` — SHA `bc1ce726…`; `git diff --name-only bc1ce72..HEAD` da
  `stg.yaml` y tres ficheros de `progress/`: **ni una línea de Python**, el
  alcance medido sigue siendo el de HEAD.
- **RM3** `[x]` — **ningún superviviente se declara equivalente**, luego ninguno
  equivalente sale muerto; el nº 4 argumenta por qué **no** lo es (con `or`, la
  tabla vacía revienta con `TypeError` justo en el caso que la guarda cubre) y
  comparto el razonamiento. **RM4** `N/A`: no dudo de ningún veredicto. **RM5**
  `N/A` por nivel y porque no hay equivalentes. **RM6** `N/A` justificado: no se
  quitó código defensivo, no hay Python de producción.
- **Supervivientes** `[x]` — los ocho analizados, ninguno en `PENDIENTE`, y
  ninguno es de F-079: el alcance viene inflado por **F-075** y siete apuntan a
  la misma causa —adaptadores probados por el texto de su SQL y nunca por lo que
  devuelven—. **Verifiqué el dato más fuerte del informe**: `grep -rn
  "ventana_sql\|hallazgos_de" tests/` no devuelve **una sola línea**, con 246
  líneas de ese fichero en alcance. El octavo es **F-077**. La ficha que propone
  el informe de mutación es pertinente: la traslado. **Evidencias** `[x]`, con los cuatro números y los workers.

## Despliegue: lo que falta, y lo que no me cuadra

**Publicar es del líder** y el informe no da por hecho nada que dependa de ello.

1. **Lo publicado no parece ser la 16.** Consulté el MCP **en solo lectura**
   (`contexto_bbdd`): dice **versión 13, publicada el 2026-09-07 10:48 UTC, 105
   objetos** —el árbol tiene 139— y su bloque de esquemas todavía reza que `stg`
   «NO es superficie de consulta» (`stg: 0/10`). El «16» viene heredado de la
   sesión de F-074, no lo inventa F-079, pero el par de hashes que el informe
   ofrece como prueba se apoya en un número que no me cuadra: lo resuelve la
   MANUAL 2, y conviene corregirlo luego en `current.md`.
2. **Riesgo de que la publicación no dure.** Si lo vivo es la 13 del 07-09 y la
   nocturna corre `publicar_diccionario` dentro de `run-all`, **la imagen
   desplegada republica su propio diccionario cada noche** y puede pisar la 18
   publicada a mano: comprobar de qué commit es la imagen del job.
3. **Apunte barato para la MANUAL 3.** El bloque «ENRUTADO POR PREGUNTA» del MCP
   se arma **solo con `ejemplos_preguntas`**, y `stg.presupuesto` no tiene
   ninguno sobre certificación, que es justo la pregunta de esa MANUAL (sí está
   en su `descripcion`). Si falla, es lo primero que añadir; no lo pido como
   cambio porque la calidad de las fichas es **F-070**.

**Sin cambios requeridos.** Apunte menor: el informe del implementer está clavado
en el tope (220/220).
