<!-- progress/current.md -->
# Estado actual · 2026-08-28

## EN CURSO: F-047 · la nocturna desfasada (absorbe F-044)

Rama `feature/F-047-nocturna-desfasada`. Implementación **terminada**, `bash
harness/init.sh` **en verde** (2.581 tests, 128 saltados; cobertura 100 % de 259
líneas cambiadas). Campaña de mutación **en serie**: 70 mutantes, 63 muertos,
**7 supervivientes, todos con test, 0 finales**. Informes:
`progress/impl_F-047.md` y `progress/mutacion_F-047.md`.

**La causa raíz, ya cerrada** (`progress/explore_F-047.md`): la nocturna no
dejaba de crear `cierre.v_pbi_planif_vs_real`, **la destruía**.
`mart/03_agg_categoria.sql` dropea `mart.fact_seguimiento_categoria` con
`CASCADE` y esa vista cuelga de la tabla; `build-cierre` no entraba en `run-all`,
así que nadie la recreaba.

### Verificado contra la base el 2026-08-28 (ya no está pendiente)

La conexión se recuperó: la IP del puesto no estaba en el firewall del
servidor; regla `datamart-puesto-pgris-2026-08-28` creada con autorización del
humano. Detalle en `progress/explore_F-047.md`.

- `check-diccionario`: **103 fichas y 102 construidas** en la base. La
  huérfana es esa **y solo esa**.
- `check-declarados` contra el servidor real: señala el objeto **y su fichero**,
  y sale con **código 1** (medido sin pipe: con `| tail` se lee el exit de `tail`).
- `_meta.etl_runs` **cierra el caso**: `build_cierre` último OK el **2026-08-21
  23:30** (la ejecución manual del humano), `build_mart` el **2026-08-28 04:56**
  (la nocturna). La vista nació el 21 y la nocturna del 22 se la llevó.

### LA CONDICIÓN DE CIERRE PRINCIPAL: el despliegue lleva congelado desde el 18

El job nocturno `caj-datamart-seg-dev` (cron `0 2 * * *`, grupo
`rg-datamart-seg-dev`) ejecuta la imagen
**`acralbaranesdev.azurecr.io/datamart-seg-anual:r20260818-2146`**, del 18 de
agosto, que además **es la más reciente del ACR**. Lleva diez noches terminando
`Succeeded` con código de hace diez días.

Lo delató que `publicar_diccionario` —paso de F-006— no dejara rastro nocturno
mientras `apply_grants`, que va justo después en el pipeline, sí lo dejaba.

**Nada de F-006 ni de F-047 corre hoy en producción.** La causa raíz tiene dos
capas: el `CASCADE` (destruye la vista) y el despliegue parado (impide que el
arreglo llegue). Enlaza con **F-033**. Desplegar lo decide el humano.

### La SECUENCIA de las acciones manuales (el orden IMPORTA)

Las tres son escrituras contra producción y las autoriza el humano una a una.
**Publicar el diccionario va el ÚLTIMO, y no es un detalle de estilo:**

1. **Construir y desplegar imagen nueva.** Sin esto, los otros dos pasos
   maquillan el síntoma y la nocturna vuelve a destruir la vista esa misma noche.
2. **Dejar correr una nocturna** (o lanzar `build-cierre` a mano para recrear la
   vista hoy; autorizado por el humano el 2026-08-28, **bloqueado por el
   clasificador de permisos de la sesión**, sin ejecutar).
3. **`publicar-diccionario`** (versión 10). El diccionario del árbol son hoy
   **103 objetos**, **798 columnas** documentadas y **46 fichas de consumo**: el
   contenido cambió (40 fichas y una regla dura), el inventario no. `R-FRESCURA` promete que la fecha de
   build de los cuatro «siempre es consultable», y `_meta.v_frescura` **no tiene
   hoy ninguna fila** de `build_compras` ni `build_retenciones`. Publicarlo antes
   de que corra una noche haría que el MCP sirviera una regla **bloqueante** que
   manda a una consulta vacía: una mentira nueva del tipo que F-047 vino a matar.
   Hoy no hay daño porque `_meta` sigue sirviendo la versión 9.

### La decisión de ventana, que tampoco toma el agente

La nocturna pasa de 2 h 46 a unas 3 h 24 (+37,5 min medidos el 2026-08-21).
Arrancando a las 02:00 UTC el final se mueve de 04:46 a ~05:24 UTC (07:24 hora
local). Entra, pero deja menos margen para un reintento. Adelantar el arranque o
recortar es decisión del humano.

### Estado de la review

**RECHAZADO el 2026-08-28** (`progress/review_F-047.md`), y con una distinción
que importa: **código, tests y campaña quedan APROBADOS y sin retoque**. El
rechazo es de documentación —seis afirmaciones en presente de
`azure-apps/datamart_seg_anual.md` que hoy son falsas en producción, la peor un
pretérito («la nocturna **destruía**») cuando la sigue destruyendo cada noche—,
más esta secuencia y este fichero. En corrección.

### Lo que hay que mirar sí o sí en la review

- **La regla dura `R-FRESCURA-MANUAL` pasa a llamarse `R-FRESCURA`.** Lo que
  decía —«el pipeline nocturno construye SOLO raw, stg y mart»— dejó de ser
  cierto, y es una regla **bloqueante** que el MCP sirve a los agentes. El
  peligro que queda, y que la regla nueva fija: el paso de esos cuatro no es
  dependencia de nadie, así que puede fallar sin tumbar la noche.
- **Los tests que cambiaron de veredicto.** No son rendiciones: el validador de
  frescura compara contra `main.build_pipeline_steps`, así que meter los cuatro
  build invierte R14 solo. El caso que merece más atención es
  `test_f006_r13_una_ficha_cuyo_paso_no_deja_rastro_lo_advierte`, que exigía
  ADVERTIR de un agujero y ahora exige que el agujero no exista.
- **La campaña de mutación se lanzó EN SERIE** (`--workers 1`), no en paralelo:
  con 70 mutantes salía a cuenta, y así no aplica la regla de reverificación de
  F-041 —la paralela produce falsos muertos—. Costó **2 h 32 min**.
- **HALLAZGO PARA F-041, y es nuevo**: uno de los siete supervivientes era
  **FALSO**, y la campaña era EN SERIE. F-041 solo documenta falsos MUERTOS del
  modo paralelo; esto es un falso superviviente con un solo worker, y el
  sospechoso es el `__pycache__` (defecto 2 de esa ficha, que se creía exclusivo
  del paralelo). Dirección inofensiva, pero **hay que añadirlo a la ficha**.

---

## F-006 · CERRADA el 2026-08-27

**APROBADA por el reviewer en su 21ª pasada** y marcada `done`. `bash
harness/init.sh` en verde: **2.505 tests**, cobertura 100 % de 33 líneas.

### Qué la desbloqueó, después de 21 pasadas

**La evidencia de mutación, que nunca había existido.** Las cuatro campañas
anteriores daban cero supervivientes porque la suite del worktree arrancaba
ROJA y `mutacion.py` contaba cualquier `returncode != 0` como muerto. El
2026-08-26 se arregló la causa —el `.env` no llega a un worktree— en el **arnés
1.7.7**, y la campaña midió de verdad: **256 mutantes, 52 supervivientes**, 49
matados con tests nuevos y 3 equivalentes aprobados por el humano.

### Lo que hay que llevarse de aquí

1. **La campaña paralela produce falsos muertos** (F-041, cuarto defecto). Un
   mutante dio veredictos opuestos el mismo día sobre el mismo commit.
   Evidencia: `progress/control_mutacion_F-006.md`. **Regla operativa mientras
   F-041 no esté: lo que una campaña paralela declare muerto se reverifica en
   serie antes de cerrar un `critico`.**
2. **F-034 recibe T29-T31 POR CONSTRUIR**, no construidas. Y el rol
   `mcp_sigrid_dm_ro` **lo comparten hoy el MCP y Power BI**: encender los
   `REVOKE` sin mirar qué lee Power BI le rompe los informes.
3. **F-048**, nueva: el guardián de secretos decide por el primer carácter del
   valor, así que `password=%x` o `password=#x` están exentos desde siempre.
4. **El objetivo de fondo sigue sin cumplirse**: el humano pidió «un MCP que
   pueda usar cualquier usuario desde cualquier puesto». Hoy corre en el puesto
   de pgris apuntando a Azure. Eso vive en el backlog de `mcp-bbdd`.

### Lo que esa feature enseñó sobre cómo se trabaja

- **Verifica contra la fuente, no contra tu resumen de ella.** Tres veces en dos
  días; las tres las cazó un barrido, nunca un recuento.
- **Un test rojo no dice por qué está rojo.** Un mutante se dio por muerto
  cuando lo que fallaba era un test caído por `.env` ausente.
- **Dos agentes no pueden commitear por separado sobre el mismo fichero.**
  Propuesto para `arnes-base`.
