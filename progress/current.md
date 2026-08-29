<!-- progress/current.md -->
# Estado actual · 2026-08-29

## F-042 · `in_progress` — CÓDIGO TERMINADO, ESPERANDO LAS 4 TAREAS DEL HUMANO

Rama `feature/F-042-clave-fact`, 16 commits (T1 a T13 y T18 a T23).
`bash harness/init.sh` en verde. Informe: **`progress/impl_F-042.md`**.

### Qué está hecho

- **El arreglo**, en `sql/stg/08_plan_mensual.sql`: tres CTE nuevas en la rama
  de reales y el `LAG` mirando `orden_fase`. La rama master **no cambia ni un
  byte**, y eso lo fija un **hash** en `tests/test_f042_sql.py`.
- **El oráculo**, en `etl_sigrid/domain/cierres.py`, y el comando de solo
  lectura `check-cierres` que lo contrasta contra `stg.plan_mensual`.
- **La huella antes/después**: `etl_sigrid/domain/huella.py` +
  `infrastructure/postgres/huella_obras.py` + los comandos `huella-obras` y
  `comparar-huellas`. El SQL del «después» **se recorta del propio fichero del
  build**, no es una copia.
- **El diccionario** (versión 11): retirado el aviso de dato doblado, escrita
  la regla, y el aviso llevado a `v_pbi_fact_categoria` y
  `cierre.v_pbi_planif_vs_real`, que eran la superficie de consumo y no lo
  llevaban. Sigue en **103 objetos, 798 columnas y 46 fichas de consumo**:
  F-042 no añade ni quita ninguno, solo cambia lo que dicen seis de ellas. La
  lista de pendientes no crece.

### LO QUE FALTA, y lo lanza el HUMANO (T14 a T17)

Son lecturas contra `sigrid_dm` en producción; T15 no escribe nada. **El orden
importa: la huella de ANTES se saca antes de reconstruir nada**, porque el
build pisa `stg.plan_mensual` y no hay vuelta atrás.

```
python main.py huella-obras --desde stg  --out huella_f042_stg_antes.csv     # T14
python main.py huella-obras --desde mart --out huella_f042_mart_antes.csv    # T14
python main.py huella-obras --desde stg --propuesta --out huella_f042_stg_despues.csv   # T15
python main.py comparar-huellas huella_f042_stg_antes.csv huella_f042_stg_despues.csv \
    --obras-esperadas 0246,0310,0433,0462,0471,0499,0545,0571,0606          # T16
```

- **T14**: los dos CSV existen, con ~11.883 celdas y los cuatro ámbitos.
- **T15**: termina **sin escribir en la base** y la ocupación de disco no se
  mueve.
- **T16**: código 0; **cero diferencias en los ámbitos 8 y 11**; ninguna obra
  fuera de la lista se mueve.
- **T17**: contrastar el informe de T16 contra la tabla de
  `progress/explore_F-042.md` §4.2, obra a obra, y pegarlo en el hueco que
  `progress/impl_F-042.md` deja reservado.

Verificado en seco: los tres comandos existen, `--help` responde y la lógica
está cubierta por 188 tests propios de F-042.

### Los pasos de cierre, después de T17

Son **escrituras en producción** y también los autoriza el humano: `stage` +
`build-mart` + `build-cierre` **sin `ingest`**, luego la huella del después ya
materializada, `check-unicidad` (debe dar 0), `check-cierres`,
`check-diccionario` y `publicar-diccionario`. Están en `specs/F-042-clave-fact/tasks.md`.

### Sin campaña de mutación, y el reviewer tiene que saberlo

Decisión del humano del 2026-08-29: «no me hacen falta mutation test».
`CHECKPOINTS.md` la exige en C4 bis para rigor `critico`, así que **el reviewer
debe declararla N/A citando esta decisión**; sin ese motivo por escrito, un
checkbox vacío en C4 bis es CHANGES_REQUESTED. **Fase RED y cobertura sí se
exigen y están cumplidas**: las trazas de los cuatro rojos están en el informe.

---

## F-042 · FASE 1: la evidencia (2026-08-28)

`progress/explore_F-042.md`, medido contra la base real en solo lectura. Lo que
hay que llevarse:

1. **Los tres conjuntos están encajados: 22 ⊃ 9 ⊃ 7.** 22 obras con fases que
   chocan, 9 que llegan a duplicar filas, y **7 —no 8— con dinero mal
   publicado**. **0433** y **0606** duplican filas pero su gemela vale 0 €.
2. **NO hay un patrón, hay dos.** Patrón 1 (14 obras): dos cierres de quincena
   dentro del mismo mes. Patrón 2 (8 obras): la fase abarca varios meses y
   `ano/mes` se quedó en el de arranque, **y eso hace desaparecer meses
   enteros** (la 0246 no tiene jul ni ago 2010). F-042 arregla el doblado; **el
   patrón 2 sigue abierto** y su investigación está fichada como F-050.
3. **La cifra de la ficha no reproduce.** 39,07 M€ en 37 celdas de 8 obras no
   se puede repetir —su consulta nunca se publicó—. La cifra honesta es
   **30.425.881,56 € en 35 celdas de 7 obras**, y es la que va al diccionario.
4. **0462 · RETAMAR** tiene el mes en conflicto como ÚLTIMO mes: su total
   definitivo está publicado al doble **de forma permanente**.
5. **No está creciendo**: cero colisiones en 2022–2026. Es residuo histórico,
   pero cada `build-mart` lo reescribe igual.

---

## F-047 · CERRADA el 2026-08-28 (absorbió F-044)

Aprobada por el reviewer en la 3ª pasada y desplegada el mismo día. La causa
raíz no era ninguna de las tres que proponía la ficha: la nocturna no dejaba de
crear `cierre.v_pbi_planif_vs_real`, **la destruía** (`mart/03_agg_categoria.sql`
dropea con `CASCADE` la tabla de la que cuelga). Detalle en
`progress/explore_F-047.md`, `impl_F-047.md` y `review_F-047.md`.

**La lección que vale para cualquier feature futura: el repositorio en verde no
es producción.** El despliegue llevaba congelado desde el 18 de agosto, diez
noches terminando `Succeeded` con código de hace diez días.

### Lo que quedó abierto

- **F-044** sigue `in_progress`: el tiempo real de la ventana completa y el pico
  de disco solo se pueden medir observando una nocturna con los diez pasos.
- **F-041**: el `__pycache__` opera también en serie, y es bidireccional.
- **F-049**: `mutacion.py` deja el sello `PENDIENTE` puesto tras resolverse.
- **F-048**: el guardián de secretos decide por el primer carácter del valor.
- **F-012**: siete reglas de firewall de puestos sueltos acumuladas.

## LO SIGUIENTE

**Lanzar T14 a T17** (arriba, con los comandos exactos) y devolver los
resultados al implementer para que cierre `progress/impl_F-042.md`. Después, el
reviewer contra `CHECKPOINTS.md`, con la excepción de mutación declarada N/A.
