<!-- progress/current.md -->
# Estado actual · 2026-08-29

## F-042 · `in_progress` — LISTA PARA EL REVIEWER

Rama `feature/F-042-clave-fact`, 27 commits (T1–T25). `bash harness/init.sh` en
verde. Informe: **`progress/impl_F-042.md`**.

**La prueba que decide, ya ejecutada.** `comparar-huellas` sale con **código 0**:
*«cambian exactamente las obras previstas y solo en lo previsto; el resto, ni un
céntimo»*. **19 cambios de importe, −30.424.662,34 €, todos a la baja y todos en
las 9 obras esperadas. Ámbitos master 8 y 11: 0 cambios.** La huella del después
se generó **sin escribir una fila** y el disco no se movió (58,06 % constante en
los 60 tramos).

Tres cosas del resultado que el reviewer va a mirar, todas en §5 del informe:

1. **El matiz de PUY DU FOU funcionó**: `0606 · ámbito 3 · 2021-02:
   [14|16] -> [14]`, y **0 € de cambio**. Sin él habría −18,24 M€ falsos ahí.
2. **El total no cuadra con la línea base por 1.219,22 €, y es correcto**: son
   **dos reglas distintas** y la diferencia es casi toda la 0246 (1.197,99).
   Eso corrigió el fixture de `test_f042_regla.py`, que tenía los dos importes
   de esa obra intercambiados.
3. **Un solo `importe_mes` se mueve** —`0471 · ámbito 7 · 2016-03, −4.538,09`—
   y se mueve para bien: el cierre descartado traía un acumulado **menor que el
   mes anterior** y el movimiento arrastraba ese tramo negativo espurio.

**Se corrigió una afirmación del diseño que la medición desmintió** (§6 del
informe y §5 de `design.md`): el agregado de `stg` es idéntico al de `mart` en
los ámbitos reales —desviación **0 en 8.243 celdas**— pero **no en los master**,
donde `stg` suma todas las versiones y `mart` solo la vigente. No invalida nada,
pero la frase habría hecho creer a alguien que encontró un defecto de 40
millones.

El diccionario sigue en **103 objetos, 798 columnas y 46 fichas de consumo**:
F-042 no añade ni quita ninguno, solo cambia lo que dicen seis. La lista de
pendientes no crece. Los CSV de la huella **no se versionan** (`.gitignore:27`,
precedente de F-019).

**Sin campaña de mutación**, por decisión del humano del 2026-08-29. El
**reviewer debe declararla N/A en C4 bis citándola**; sin ese motivo escrito, un
checkbox vacío ahí es CHANGES_REQUESTED. **Fase RED y cobertura sí se exigen y
están cumplidas**: cuatro trazas de rojo en §3 y **100 % de 649 líneas
cambiadas**.

### Lo que falta, y son ESCRITURAS EN PRODUCCIÓN que autoriza el humano

En `specs/F-042-clave-fact/tasks.md`: `stage` + `build-mart` + `build-cierre`
**sin `ingest`**, la huella del después ya materializada, `check-unicidad`
(debe dar **0** frente a 8.778), `check-cierres`, `check-diccionario`,
`publicar-diccionario` y `timings`. **Hasta entonces la base sigue con el
defecto**, y por eso `publicar-diccionario` va **después** del build.

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
