<!-- progress/current.md -->
# Estado actual · 2026-08-28

## F-042 · `in_progress` — FASE 1 (evidencia) ENTREGADA, spec EN ESPERA

Rama `feature/F-042-clave-fact`. El humano pidió **antes que la spec** un
resumen de las obras afectadas y del problema exacto, para contrastarlo con los
números que él conoce de cada obra. Está en **`progress/explore_F-042.md`**,
medido hoy contra la base real **en solo lectura** (`default_transaction_read_only
= on`, cierre con `ROLLBACK`; ni una escritura).

**Lo que hay que llevarse de la evidencia:**

1. **Los tres conjuntos están encajados: 22 ⊃ 9 ⊃ 7.** 22 obras con fases que
   chocan, 9 que llegan a duplicar filas, y **7 —no 8— con dinero mal
   publicado**. **0433** y **0606** duplican filas pero su gemela vale 0 €.
2. **NO hay un patrón, hay dos**, y se separan con «¿la fase termina dentro del
   mes que declara?». **Patrón 1** (14 obras, 16 colisiones): dos cierres de
   quincena dentro del mismo mes, el `mes` es correcto en las dos. **Patrón 2**
   (8 obras, 8 colisiones): la fase abarca varios meses y `ano/mes` se quedó en
   el de arranque —el ejemplo de la ficha, la 0246 «AGOSTO 2010» con `mes = 6`—.
   **Cada patrón pide un arreglo distinto: una sola hipótesis para las 22 no se
   sostiene.**
3. **La cifra de la ficha no reproduce.** 8.778 / 17.556 / 9 obras / 22 obras
   salen **clavados**; los **39,07 M€ en 37 celdas de 8 obras, no**, y no hay
   forma de repetirlos porque esa consulta nunca se publicó. Medido hoy con la
   regla que se sostiene («manda la fase que termina dentro del mes»):
   **30.425.881,56 € en 35 celdas de 7 obras**. La regla ingenua («la fase de
   número mayor») da 48,67 M€ e incluye 18,24 M€ falsos de la 0606.
4. **Hallazgos nuevos que la ficha no traía**, y que la spec debe recoger:
   - **El patrón 2 hace desaparecer meses**: la 0246 no tiene jul ni ago 2010;
     la 0571 no tiene jun, jul ni ago 2020.
   - **La 0462 · RETAMAR tiene el mes en conflicto como ÚLTIMO mes**: su total
     definitivo está publicado al doble **para siempre** (395.309,32 € cuando
     costó 197.654,52 €). No hay mes posterior que lo corrija.
   - **`cierre.v_pbi_planif_vs_real` también cuelga** de
     `mart.fact_seguimiento_categoria` —la ficha solo nombraba
     `v_pbi_fact_categoria`—. Se salva del doblado porque usa `importe_mes`,
     pero el patrón 2 le mete tres meses de real en uno.
   - **El aviso del diccionario NO llega al consumidor**: está en la ficha de
     `mart.fact_seguimiento_categoria` pero **no** en la de
     `mart.v_pbi_fact_categoria`, que es la vista que Power BI y el MCP abren.
     Es la lección de F-006 repetida un nivel más abajo.
   - Los **seis** objetos afectados tienen `SELECT` para `mcp_sigrid_dm_ro`, rol
     **compartido hoy por el MCP y Power BI**.
5. **No está creciendo: cero colisiones en 2022, 2023, 2024, 2025 y 2026**,
   mientras el volumen de fases pasaba de 297 a 462 al año. La última es de
   feb-2021 y es justo la que no cuesta dinero. Todas las obras afectadas están
   terminadas (la más reciente cerró en sep-2020). Es residuo histórico: no hay
   prisa de nocturna, pero cada `build-mart` lo reescribe igual.

**DECISIÓN DE NEGOCIO PENDIENTE, y el spec-author PARA aquí.** En las 14 obras
de patrón 1, ¿los dos cierres del mes son dos medidas que Negocio quiere
conservar por separado —y entonces la clave necesita el número de fase,
publicado— o son un apaño de obra que a efectos de seguimiento anual sobra? De
eso depende el diseño entero, y **no lo decide ningún agente**. Consecuencias
numéricas de cada hipótesis, en el §8 de `explore_F-042.md`.

**Lo siguiente en F-042**: con la respuesta del humano, escribir
`specs/F-042-clave-fact/` (requirements + design + tasks). Sin la respuesta, la
spec no se puede cerrar: patrón 1 y patrón 2 no admiten el mismo arreglo.

---

## F-047 · CERRADA el 2026-08-28 (absorbio F-044)

Aprobada por el reviewer en la 3ª pasada y **desplegada en producción el mismo
día**. Rama `feature/F-047-nocturna-desfasada`, `bash harness/init.sh` en verde
(2.581 tests, 128 saltados; cobertura 100 % de 259 líneas), campaña de mutación
en serie de 70 mutantes con 0 supervivientes finales.

**La causa raíz, y no era ninguna de las tres que proponía la ficha**: la
nocturna no dejaba de crear `cierre.v_pbi_planif_vs_real`, **la destruía**.
`mart/03_agg_categoria.sql` dropea `mart.fact_seguimiento_categoria` con
`CASCADE` y esa vista cuelga de la tabla. Detalle en
`progress/explore_F-047.md`; el trabajo, en `impl_F-047.md` y `review_F-047.md`.

### Lo que se hizo en producción el 2026-08-28, en este orden

| # | Acción | Resultado |
|---|---|---|
| 1 | `70_build_image.ps1` + `85_update_job.ps1` | imagen **`r20260828-1942`**, el job ya apunta a ella (venía de la del **18 de agosto**) |
| 2 | los cuatro build + `apply-grants` a mano | 37 min: maestros 0,8 · compras 7,3 · retenciones 1 · cierre 27,9 · grants 0,1 |
| 3 | `publicar-diccionario` | **versión 10**: 149 filas, 103 objetos, 798 columnas, 16 reglas y 46 fichas de consumo |

**El orden no fue casual.** Publicar el diccionario antes de los build habría
dejado al MCP sirviendo `R-FRESCURA` —regla **bloqueante**— apuntando a una
consulta vacía, porque `_meta.v_frescura` no tenía ninguna fila de
`build_compras` ni `build_retenciones`. Lo advirtió el reviewer; el humano
eligió lanzar los cuatro build a mano el mismo día en vez de esperar.

**Verificación final**: `check-declarados` **103 declarados / 103 construidos**,
código 0. `check-diccionario` **biyección exacta 103 = 103** y «lo publicado ES
lo del árbol». **La vista ha vuelto.** Disco **57,81 %** (18 GB de 32), contra
57,92 % del 21: no se mueve.

### La segunda capa, que nadie buscaba

El despliegue llevaba **congelado desde el 18 de agosto**: diez noches
terminando `Succeeded` con código de hace diez días, y todo F-006 fuera. Lo
delató que `publicar_diccionario` no dejara rastro nocturno mientras
`apply_grants`, el paso siguiente, sí lo dejaba. **La lección, y vale para
cualquier feature futura: el repositorio en verde no es producción.** Ver
`azure-apps/datamart_seg_anual.md` y **F-033**.

### Lo que quedó abierto

- **F-044 sigue `in_progress`**, y no por descuido: tres de sus cinco criterios
  están cumplidos y verificados, pero **el tiempo real de la ventana completa y
  el pico de disco solo se pueden medir observando la primera nocturna con los
  diez pasos**, la del **29 de agosto a las 02:00 UTC**. Lo de hoy fueron cuatro
  build a mano sobre un `stg`/`mart` ya construidos, que no es lo mismo.
  Previsión a confirmar: ~3 h 24, final hacia las 05:24 UTC.
- **F-041** recibió un quinto defecto: el `__pycache__` opera **también en
  serie**, y es bidireccional. La serie no es inmune a los falsos muertos; solo
  no se ha visto uno todavía.
- **F-049**, nueva: `mutacion.py` deja el sello `PENDIENTE` puesto después de
  resolverse, trampa para el próximo reviewer con `grep`. Se porta a
  `arnes-base` en el mismo trabajo.
- **F-012** tiene material nuevo: siete reglas de firewall de puestos sueltos
  acumuladas en `psql-albaranes-rs9k2`, una por día que cambió la IP.

## LO SIGUIENTE

**Mirar la nocturna del 29** y cerrar F-044 con las dos mediciones que le
faltan. Si termina antes de las 05:24 UTC y el disco no se mueve, se marca
`done`; si invade la mañana, la decisión de recortar es del humano y enlaza con
F-035 (las cuatro palancas) y F-025 (la ventana de negocio).

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
