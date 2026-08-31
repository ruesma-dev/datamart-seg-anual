<!-- specs/F-052-partidas-huerfanas/decisiones.md -->
# F-052 · Las siete decisiones, con su razón

Anexo de `design.md` §5. Aquí vive el detalle: por qué se eligió cada
opción y qué se descartó. El diseño solo lleva el resumen.

Las siete estaban abiertas cuando se escribió esta spec. **Están cerradas**; se
dejan aquí con la opción elegida y su razón, porque la razón es lo que evita que
alguien las reabra dentro de seis meses sin saber qué se sopesó.

**DA-1 · ¿Se relaja también la rama raíz? → (a) SOLO EL DESCENSO.** La línea 58
no se toca. Criterio del humano: mínimo cambio sobre algo que «ahora mismo estaba
funcionando bien en general». Coincide con lo medido: los 7 nodos con `cod = ''`
son **todos intermedios**, no hay ni una raíz sin código, así que relajar la raíz
no recuperaría ni una fila hoy y obligaría a inventar reglas de
`capitulo_raiz_id` sin un solo caso real que las valide. El día que aparezca una,
la caza el guardián de §3.

**DA-2 · ¿Qué reciben `ruta_capitulos` y `codigo_partida`? → (a) COLAPSAR**, y
con una **condición bloqueante** que el humano puso con estas palabras: *«si eso
no va a cambiar nada en el resto de obras, que sí están funcionando; si cambia
algo, prefiero perder la 0599 porque no sigue el patrón correcto»*. Convertida en
R11: si la comparación de huellas revela que se mueve **una sola cifra** de una
obra fuera de las seis afectadas, la feature **se detiene y se consulta**, no se
publica.

*Por qué la condición se puede dar por cumplida, y no por optimismo.* Cada
partida tiene **un solo padre** en `raw.obrparpar`, luego **un solo camino** hasta
su raíz. Una partida que hoy se publica lo hace porque su camino entero está
formado por nodos con código; el algoritmo nuevo recorre **ese mismo camino** y
produce la misma ruta, el mismo nivel y el mismo padre. Relajar el filtro solo
**añade** caminos: no altera ninguno de los existentes. **El cambio es
estrictamente aditivo**, y para que una obra sana se moviera haría falta que una
de sus partidas tuviera dos padres, cosa que el modelo no permite.

Tres datos medidos que lo respaldan: fuera de la 0599 el movimiento máximo
posible son **226 filas de las 183.756**, a **0,00 €**; los nodos sin código son
**7 en 3 obras** y ninguna otra los tiene; y la profundidad máxima real de
`stg.partidas` es de **7 niveles, con cero partidas de nivel 8 o más sobre
389.178** (medido el 2026-08-31), lo que valida que el tope de 40 del corta-ciclos
no trunca nada legítimo. Aun así R11 se verifica empíricamente: el argumento
explica por qué se espera que salga limpio, no sustituye a la prueba.

**Contrapartida aceptada por el humano:** «FASE 1 - MOVIMIENTO TIERRAS Y
CIMENTACIÓN» y sus dos hermanas **desaparecen del árbol de Power BI** de la 0599
como agrupador. Los euros están todos; lo que se pierde es poder preguntar cuánto
costó una fase en esa obra. Va en el aviso a Negocio para que puedan objetar
antes de publicar.

**DA-3 · Corta-ciclos → (a) + (b).** Array de visitados, que es exacto, **más**
el tope de profundidad como respaldo. Los 12 nodos en ciclo siguen sin
publicarse —no son alcanzables desde ninguna raíz—, pero pasan de perderse en
silencio a quedar denunciados.

**DA-4 · El guardián → AVISA, NO BLOQUEA, Y AVISA POR CORREO.** La nocturna
termina en verde; el hallazgo sale por el marcador del log y una regla de alerta
lo convierte en correo. El diseño completo está en §3. Se instrumenta **solo el
guardián post-build**, no los nueve puntos de descarte: da el mismo veredicto sin
tocar el camino caliente de 5,3 M de filas, y dos de los nueve son descartes
**por diseño** que solo generarían ruido permanente.

**DA-5 · ¿La causa se lleva a Sigrid? → SÍ, SIN ESPERAR.** Como en F-050: aquí se
protege el ETL y se avisa a quien administra Sigrid. **Prioridad únicamente para
la 0686 VALDEBEBAS**, que sigue viva (última fase 2026-07-31) y arrastra un
auto-bucle creado en 2024; las demás (0599, 0613, 0618, 0630, 0565) son obras
cerradas entre 2020 y 2022 cuyo saneamiento en origen ya es cosmético. El texto
está redactado en `aviso_negocio.md`.

**DA-6 · El aviso a Negocio → AVISAR ANTES DE PUBLICAR, Y NOTA EN EL
DICCIONARIO.** El documento es
**`specs/F-052-partidas-huerfanas/aviso_negocio.md`**, ya escrito. Es paso manual
**bloqueante** (R27): el margen de la 0599 pasa de 66,3 % a 1,8 % y cualquier
informe anterior deja de cuadrar. La nota en la ficha (R21) es lo que responde a
esa misma pregunta dentro de seis meses.

**DA-7 · Alcance de F-053 → FEATURE PROPIA**, ya fichada con **prioridad 2**,
justo detrás de esta. Aquí solo se nombra y se declara como excepción aceptada en
`config/cobertura_excepciones.yaml` hasta que se cierre (R16, R24).

> **Matiz del humano que cambia el planteamiento de F-053**: que la ficha
> descartada tenga más filas **no demuestra** que la elección sea incorrecta. La
> marca de vigencia de Sigrid puede ser deliberada, y la ficha llena una versión
> jubilada a propósito; publicarla sería resucitar datos retirados, o doblarlos.
> F-053 empieza analizando **si de verdad es un error**, y cerrarla sin tocar
> código es un resultado válido.

### Bloqueo operativo conocido (2026-08-31)

**No hay conexión directa a la base desde el puesto de desarrollo**
(`connection timeout expired` contra `psql-albaranes-rs9k2`). La base está viva y
responde por la vía de solo lectura del MCP, pero **esa vía no expone el esquema
`raw`**, que es donde vive el árbol de partidas. Las tareas de verificación con
huella antes/después (T13-T16 y los pasos de cierre) **no se pueden ejecutar**
hasta restablecerlo; apunta a una regla de firewall, y ese servidor es
compartido con `albaranes` y `partes` en producción. **Bloquea la implementación,
no el diseño.**

