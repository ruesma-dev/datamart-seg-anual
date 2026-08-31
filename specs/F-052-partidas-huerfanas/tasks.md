<!-- specs/F-052-partidas-huerfanas/tasks.md -->
# F-052 · Tareas

Rama `feature/F-052-partidas-huerfanas`. Un commit por tarea (`F-052 Tn: ...`).
Rigor `critico`: **fase RED obligatoria** (test que falla antes del código, con
su traza en el informe), **cobertura de las líneas cambiadas** y **campaña de
mutación completa con cero supervivientes**. Si el humano la exime, como hizo en
F-042, debe quedar escrito y el reviewer la declara N/A citando esa decisión.

**Las tareas marcadas MANUAL las ejecuta el humano.** Son escrituras contra el
Postgres compartido con `albaranes` y `partes` **en producción**, o lecturas
completas de tablas de varios GB. Un agente no escribe en producción.

## Bloque A · La regla del árbol, en dominio puro

- [ ] T1: Escribir `tests/test_f052_arbol.py` con las fixtures reales del informe —el subárbol `CD → 280353/280354/280356 (cod='') → hijos` de la 0599, los auto-bucles 310512 (0630) y 375474 (0686) y el bucle mutuo 279988 ↔ 279997 (0565)— contra una API que aún no existe | Verificación: `pytest tests/test_f052_arbol.py` **falla** (fase RED, traza al informe)
- [ ] T2: Crear `etl_sigrid/domain/arbol_partidas.py` con `Nodo`, `Arbol` y `construir_arbol()`: desciende a través de los nodos sin código, colapsa el nodo no publicable (padre = ancestro publicado, ruta y nivel no avanzan) y corta ciclos con la lista de visitados | Verificación: `pytest tests/test_f052_arbol.py` en verde (R1, R2, R3, R5)
- [ ] T3: Añadir a `tests/test_f052_arbol.py` los casos de borde: dos nodos vacíos encadenados, nodo vacío como hoja, rama sin ningún vacío que debe salir idéntica, e invariante `len(ruta.split(' > ')) == nivel + 1` en toda partida publicada | Verificación: `pytest tests/test_f052_arbol.py` (R4, R6)

## Bloque B · El SQL

- [ ] T4: Escribir `tests/test_f052_sql.py` afirmando sobre el texto de `sql/stg/04_partidas.sql` que la rama recursiva ya no lleva `h.cod <> ''`, que existen `publicable`, `padre_publicado_id` y `visitados`, que hay tope de profundidad, y que el `INSERT` filtra por `publicable` | Verificación: `pytest tests/test_f052_sql.py` **falla** (fase RED)
- [ ] T5: Modificar `sql/stg/04_partidas.sql` según §1 del diseño (descenso relajado, columnas propagadas, ruta/nivel condicionales, corta-ciclos, filtro de publicación en el `INSERT`) y reescribir el bloque de cabecera que hoy documenta el filtro al revés | Verificación: `pytest tests/test_f052_sql.py` en verde; revisión visual del diff
- [ ] T6: Comprobar que el cambio no necesita marcador de tramo nuevo ni tocar `build_stg_step.py`: el CTE ya particiona por obra a través de `padide`, que nunca sale de su obra (medido: causa (c) = 0 casos) | Verificación: `grep -n F019_FILTRO_OBRAS` sobre `04_partidas.sql` sigue dando lo mismo; `pytest tests/test_f019_tramos.py`

## Bloque C · El guardián `check-cobertura`

- [ ] T7: Escribir `tests/test_f052_cobertura.py` contra un cliente Postgres falso, con un caso conforme, uno de obra invisible, uno de filas huérfanas y uno cubierto por excepción declarada | Verificación: `pytest tests/test_f052_cobertura.py` **falla** (fase RED)
- [ ] T8: Crear `etl_sigrid/domain/cobertura.py` con `FilaCobertura`, `Excepcion` y `veredicto()`, que devuelve las dos listas completas y código distinto de 0 si algo cae fuera de lo declarado | Verificación: `pytest tests/test_f052_cobertura.py` en verde (R14, R15, R16)
- [ ] T9: Crear `etl_sigrid/infrastructure/postgres/cobertura_sql.py`, que **solo construye texto** con su `SET LOCAL statement_timeout` y no abre conexión, al estilo de `unicidad_sql.py` | Verificación: `pytest tests/test_f052_cobertura.py` (R18, R19)
- [ ] T10: Crear `config/cobertura_excepciones.yaml` con las excepciones aceptadas de hoy: las 12 partidas en ciclo, las 15 obras `OBRA PRUEBA`/`POSTVENTA`/`VAR` y las tres obras que dependen de F-053 (0517, 0252, 0720), cada una con motivo y feature que la cierra | Verificación: `pytest tests/test_f052_cobertura.py` (R16)
- [ ] T11: Añadir el test del trinquete: la lista de excepciones **solo puede bajar**, con la constante del recuento actual, como hace `objetos_pendientes.yaml` | Verificación: `pytest tests/test_f052_cobertura.py` (R16)
- [ ] T12: Añadir el comando `check-cobertura` a `main.py` (`--timeout`, `--dry-run`) y engancharlo en `run-all` junto a `check-declarados`, **sin hacer fallar el job**: dentro de `run-all` registra y sigue; lanzado a mano devuelve código distinto de 0 (DA-4) | Verificación: `python main.py check-cobertura --help`; `python main.py check-cobertura --dry-run`; un test cubre las dos salidas, dentro y fuera de `run-all`; `pytest tests/test_f052_cobertura.py` (R13, R17)

## Bloque C bis · Que el guardián se haga oír (DA-4)

Sin esto el guardián es **mudo**: al no bloquear el job, la alerta de fallo
existente no se dispara y el hallazgo se queda en el log.

- [ ] T24: Escribir `tests/test_f052_marcador.py`, que cruza el marcador `[F052-COBERTURA-KO]` emitido por el código con el que busca `infra/96_create_alert_cobertura.ps1`, al estilo de `test_f024_r19_umbral_por_defecto_coincide_con_dev_json` | Verificación: `pytest tests/test_f052_marcador.py` **falla** (fase RED)
- [ ] T25: Emitir el marcador desde `check-cobertura` cuando encuentre algo fuera de lo declarado, seguido del recuento de obras invisibles y de filas huérfanas | Verificación: `pytest tests/test_f052_marcador.py tests/test_f052_cobertura.py` en verde (R28)
- [ ] T26: Crear `infra/96_create_alert_cobertura.ps1`, hermano de `95_create_alert_frescura.ps1`: regla de consulta programada sobre `log-datamart-seg-dev` que busca el marcador y notifica a `ag-datamart-seg-dev`. **Ninguna dirección de correo en el fichero** (R30) | Verificación: `pytest tests/test_f052_marcador.py`; revisión visual; el despliegue es MANUAL

## Bloque D · La medida ANTES, contra la base

- [ ] T13: Medir el coste real de `check-cobertura` contra la base **antes** de dar por buena su entrada en la nocturna: `python main.py check-cobertura --timeout 600` | Verificación: MANUAL (humano) — anotar el tiempo de cada consulta; si supera los minutos aceptables sobre una nocturna de 3 h 45, volver a DA-4 antes de seguir
- [ ] T14: Capturar la huella actual de los cuatro ámbitos, **antes de tocar la base**: `python main.py huella-obras --desde stg --out huella_f052_stg_antes.csv` y `--desde mart --out huella_f052_mart_antes.csv` | Verificación: MANUAL (humano) — los dos CSV existen y traen los cuatro ámbitos
- [ ] T15: Guardar el veredicto de `check-cobertura` de HOY (en rojo) como línea base: debe nombrar la 0599 con ~183.530 filas huérfanas y las combinaciones 0599 × 7 y 0599 × 11 como obra invisible | Verificación: MANUAL (humano) — la salida cuadra con las secciones 3 y 4 del informe de exploración

## Bloque E · El diccionario y la documentación

- [ ] T16: Actualizar en `config/diccionario/stg.yaml` la ficha de `stg.partidas`: `codigo_partida` deja de decir que una partida sin código no llega, y `capitulo_padre_id` pasa a ser el ancestro **publicado**, no siempre el padre de Sigrid; `nivel` y `ruta_capitulos` cuentan solo nodos publicados | Verificación: `pytest tests/test_f006_fichas.py tests/test_f006_formato.py` (R20)
- [ ] T17: Añadir en `config/diccionario/mart.yaml` y `cierre.yaml` el aviso de que las cifras de la 0599 cambian a partir de esta reconstrucción, con la fecha y el margen antes/después | Verificación: `pytest tests/test_f006_fichas.py` (R21)
- [ ] T18: Subir `version` en `config/diccionario/00_global.yaml` y comprobar que la lista de pendientes no crece | Verificación: `pytest tests/test_f006_regla_de_oro.py tests/test_f006_cobertura.py` (R22)
- [ ] T19: Añadir a `docs/ARCHITECTURE.md`, en «Semántica Sigrid imprescindible», que un capítulo de Sigrid puede no tener código y que eso no puede cortar el árbol de partidas | Verificación: `pytest tests/test_f006_docs.py` (R23)
- [ ] T20: Fichar **F-053** en `harness/features.json` (desempate `rn = 1` de `stg/03_obras.sql:125`: 0517, 0252 y 0720 invisibles, ~10,65 M€ de coste y 10,94 M€ de venta) con la línea base de la sección 4 del informe | Verificación: `bash harness/init.sh` (R24, DA-7)

## Bloque F · Cierre del trabajo del agente

- [ ] T21: Ejecutar la campaña de mutación sobre los módulos nuevos de dominio y analizar por escrito cada superviviente | Verificación: `python -m harness.mutacion --feature F-052` con **cero supervivientes**, o la exención escrita del humano
- [ ] T22: Escribir el informe en `progress/impl_F-052.md` (≤220 líneas) con la traza de cada fase RED, la cobertura de las líneas cambiadas y la línea base de T15 | Verificación: `python -m harness.tamano --feature F-052`
- [ ] T23: Ejecutar `bash harness/init.sh` en verde | Verificación: `bash harness/init.sh` termina con código 0

---

## Pasos de cierre que NO ejecuta el agente

Escrituras contra el Postgres compartido **en producción**, más un aviso a
personas. Los autoriza y lanza el humano. Coste: una **nocturna completa,
3 h 45** (F-044), porque el cambio toca `stg.partidas` y de ahí abajo todo.

1. **El aviso a Negocio ANTES de publicar (R27, DA-6)**: la 0599 pasa de margen
   66,3 % a 1,8 %, de 0 € a 4.066.989,23 € de venta y de 0,00 € a ~2,62 M€ de
   DIRECTOS. Cualquier informe o captura anterior deja de cuadrar. **Sin este
   paso no se publica.**
2. **La reconstrucción con el MISMO `raw`**, sin `ingest`: `python main.py stage`
   + `build-mart` + `build-cierre`. Requiere que T14 se haya ejecutado antes: el
   build pisa las tablas.
3. **La huella de después**: `huella-obras --desde stg --out
   huella_f052_stg_despues.csv` y `--desde mart --out
   huella_f052_mart_despues.csv`.
4. **La prueba que decide (R11)**: `python main.py comparar-huellas
   huella_f052_stg_antes.csv huella_f052_stg_despues.csv --obras-esperadas
   0599,0613,0618,0630,0565,0686`, y lo mismo con las de `mart`. Debe dar
   **código 0**: ninguna obra fuera de esas seis mueve ni una celda en los cuatro
   ámbitos. Si se mueve una sola, la feature **no se cierra**.
5. **Los recuentos de R7-R10**, obra a obra, contra la línea base del informe:
   `stg.partidas` 389.178 → 390.501; 0599 de 117 a 1.440 partidas; el fact gana
   ~183.756 filas y aparecen 0599 × 7 y 0599 × 11; DIRECTOS de la 0599 de 0,00 €
   a ~2,62 M€.
6. **`python main.py check-cobertura`** → código 0 lanzado a mano, con solo las
   excepciones declaradas de T10 (R13-R17).
6 bis. **Desplegar el aviso por correo (R29, DA-4)**: ejecutar
   `infra/96_create_alert_cobertura.ps1` y **añadir el buzón de desarrollo al
   grupo de acción** con `-AlertEmail` de `infra/90_create_alert.ps1`. **Sin este
   paso el guardián no avisa a nadie**, porque al no bloquear el job la alerta de
   fallo existente no se dispara. Verificar de punta a punta provocando el
   marcador una vez y comprobando que llega el correo.
7. **`python main.py check-unicidad --timeout 300`** → **0 claves duplicadas**
   en `mart.fact_seguimiento_mensual` con las 183.756 filas nuevas (R12).
8. **`python main.py check-cierres`** y **`check-diccionario`** → código 0.
9. **`python main.py publicar-diccionario`** → escritura contra Azure, la
   autoriza el humano (R20-R22).
10. **El aviso a quien administra Sigrid (R26, DA-5)**: los 3 capítulos sin
    código y los 2 auto-bucles. Prioridad real solo en la **0686 VALDEBEBAS**,
    que sigue viva; las demás son obras cerradas entre 2020 y 2022.
