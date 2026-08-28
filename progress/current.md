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

### Lo que queda para cerrarla

1. **Verificación contra la base, pendiente de conexión.** El puesto no llega a
   `psql-albaranes-rs9k2` (puerto 5432 cerrado desde esta IP). Todo lo de abajo
   es LECTURA salvo donde se diga:
   - `python main.py check-declarados` → debería dar los 103 declarados y decir
     cuántos faltan de verdad hoy;
   - `python main.py check-diccionario` → la huérfana sigue siendo esa y solo esa;
   - `_meta.etl_runs` → fechar el borrado contra la última nocturna;
   - `pg_depend` → que no haya otros dependientes de
     `mart.fact_seguimiento_categoria` creados fuera del repositorio.
2. **La decisión de ventana la toma el humano, no el agente.** La nocturna pasa
   de 2 h 46 a unas 3 h 24 (+37,5 min medidos el 2026-08-21). Arrancando a las
   02:00 UTC el final se mueve de 04:46 a ~05:24 UTC. Entra, pero deja menos
   margen para un reintento. Adelantar el arranque o recortar es decisión suya.
3. **Publicar el diccionario versión 10** (`publicar-diccionario` es una
   ESCRITURA contra Azure: la autoriza el humano). Hasta entonces `_meta` sirve
   la versión 9, que dice que `cierre`, `compras`, `maestro` y `retenciones` son
   de refresco manual, y ya no lo son. El diccionario del árbol son hoy **103
   objetos**, **798 columnas** documentadas y **46 fichas de consumo**; el
   contenido cambió (40 fichas y una regla dura), el inventario no.

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
